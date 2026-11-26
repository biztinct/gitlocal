# PSCHEME P3 D (odoo-bin shell): "Give everyone their own pay scheme" - the one-time fill - per company,
# through the Mapping board's own calls (pb.scheme.board.fill_plan / fill_apply / fill_undo: the same path
# as the drawer and its Undo button; run as the shell's system user). Clone of
# ../../newhire/p8/nh8_map.py.
#   PS3_MODE=dry       every company: the plan's groups + fill_apply(dry=True); ROLLED BACK (writes nothing)
#   PS3_MODE=apply     every company: fill_apply(ready + from Country of work) COMMITTED; undo file written
#   PS3_MODE=rehearse  REHEARSAL COPY ONLY: the real fill, next month's pay-run population per scheme
#                      (everyone in exactly one main run, nobody who was in a run before missing), then the
#                      Undo path (fill_undo) and the population back to before; rolled back at the end
# Only Ready and From-Country-of-work are ticked (the drawer's default); Check these / Needs your choice
# stay for a person on screen. "Fill empty Country of Work" is NEVER run here: its plan is only READ.
# Env: PS3_MODE, PS3_OUT=<folder>. Writes <out>/fill-<db>.json (counts, ids; schemes as "scheme N") and
# <out>/fill-detail-<db>.json (team and scheme NAMES: CLIENT DATA, never committed); apply also writes
# <out>/person_scheme_fill_<db>.csv (one line per created row, with its undo).
import csv, json, os
from collections import Counter, defaultdict
from dateutil.relativedelta import relativedelta
from odoo import fields
assert not env.cr.dbname.startswith('abm') and env.cr.dbname != '_test_sudima_policy_20261119', 'never this database'
mode = os.environ.get('PS3_MODE', 'dry')
assert mode in ('dry', 'apply', 'rehearse'), mode
if mode == 'rehearse':
    assert env.cr.dbname.startswith('ps3_rh_'), 'rehearse runs on a rehearsal copy only'
out = os.environ['PS3_OUT']
os.makedirs(out, exist_ok=True)
db = env.cr.dbname
Row = env['pb.person.scheme'].sudo().with_context(active_test=False)
Fill = env['pb.person.scheme.fill'].sudo()
Config = env['hr.formula.config'].sudo().with_context(active_test=False)
MAIN = ('end_cycle', 'regular')


def snap():
    env.flush_all()
    env.cr.execute("select count(*), coalesce(max(id), 0) from pb_person_scheme")
    r = env.cr.fetchone()
    env.cr.execute("select count(*) from pb_person_scheme_fill")
    f = env.cr.fetchone()[0]
    env.cr.execute("select count(*), coalesce(max(id), 0) from hr_formula_scheme_assignment")
    m = env.cr.fetchone()
    env.cr.execute("select md5(coalesce(string_agg(row(id, payroll_country, company_id, active)::text,"
                   " chr(10) order by id), '')) from hr_employee")
    e = env.cr.fetchone()[0]
    env.cr.execute("select count(*), md5(coalesce(string_agg(row(id, state, wage)::text, chr(10) order by id),''))"
                   " from hr_contract")
    c = env.cr.fetchone()
    return {'person_rows': list(r), 'fills': f, 'map_rows': list(m), 'people_md5': e, 'contracts': list(c)}


def population(company, emp_ids, day):
    """{employee: [main scheme ids]} and {employee: [advance ids]} of the pay runs of `day`'s month."""
    W = env['pb.payrun.wizard'].sudo().with_company(company).with_context(allowed_company_ids=[company.id])
    main, adv = defaultdict(list), defaultdict(list)
    for cfg in Config.search([('state', '=', 'active'), ('company_id', 'in', [company.id, False])], order='id'):
        covered = W._scheme_population(cfg.id, emp_ids, day)
        covered = covered[0] if isinstance(covered, tuple) else covered
        for e in (covered.ids if hasattr(covered, 'ids') else covered):
            (adv if cfg.cycle_type == 'mid_cycle' else main)[e].append(cfg.id)
    return main, adv


labels = dict(env['hr.formula.config']._fields['country_code']._description_selection(env))
kinds = {'end_cycle': 'end of month', 'regular': 'regular', 'mid_cycle': 'mid-month advance',
         'full_final': 'final settlement'}
before = snap()
result = {'mode': mode, 'db': db, 'before': before, 'companies': []}
detail = {'db': db, 'companies': []}
undo_lines = []
ok = True
for company in env['res.company'].sudo().search([], order='id'):
    emps = env['hr.employee'].sudo().with_context(active_test=True).search([('company_id', '=', company.id)])
    if not emps:
        continue
    B = env['pb.scheme.board'].with_company(company).with_context(allowed_company_ids=[company.id])
    plan = B._fill_plan(company.id)
    reasons = Counter(r['reason'] for r in plan['rows'] if r['group'] == 'choice')
    # schemes named generically, numbered in the order of the plan's own scheme list
    order = sorted(plan['schemes'].values(), key=lambda s: (s['country'], s['name'], s['id']))
    num = {s['id']: i + 1 for i, s in enumerate(order)}
    sname = lambda sid: 'scheme %s (%s, %s)' % (num[sid], plan['schemes'][str(sid)]['country'] or '-',
                                               Config.browse(sid).cycle_type and kinds.get(Config.browse(sid).cycle_type, '') or '-') if sid else '-'
    target = Counter()
    for r in plan['rows']:
        if r['group'] in ('ready', 'country') and r['target_id']:
            target[(r['target_id'], r['advance_id'] or 0)] += 1
    # people with no Country of work: on the plan (no own row) and in the company; and what the
    # "Fill empty Country of Work" plan WOULD fill (read only - _pb_plan writes nothing)
    no_country_all = len(emps.filtered(lambda e: not e.payroll_country))
    cow = {'available': 'pb.cow.fill.wizard' in env}
    if cow['available']:
        W = env['pb.cow.fill.wizard'].with_company(company).with_context(allowed_company_ids=[company.id])
        cplan = W._pb_plan()
        pay, comp, fill, why, two = W._pb_summary(cplan, True)
        cow.update({'empty': cplan['empty'], 'from_pay_setup': sum(pay.values()),
                    'from_company_country': sum(comp.values()), 'would_fill': sum(fill.values()),
                    'left': dict(why)})
    dry = B.fill_apply(company.id, ['ready', 'country'], dry=True)
    c = {'company': company.id, 'people_active': len(emps), 'people_on_roster': plan['people'],
         'without_own': plan['without'], 'counts': plan['counts'], 'choice_reasons': dict(reasons),
         'no_country_on_plan': reasons.get('no_country', 0), 'no_country_in_company': no_country_all,
         'country_of_work_fill': cow,
         'dry': {'people': dry['people'], 'left': dry['left'], 'by_group': dry['by_group']},
         'would_get': sorted([[sname(t), sname(a) if a else '', n] for (t, a), n in target.items()]),
         'check_today_scheme': sorted(Counter(sname(r['today_id']) for r in plan['rows']
                                              if r['group'] == 'check').items()),
         'date': plan['date']}
    dc = {'company': company.name, 'schemes': {sname(s['id']): s['name'] for s in order},
          'teams': defaultdict(Counter)}
    for r in plan['rows']:
        key = r['group'] + ('/' + r['reason'] if r['reason'] else '')
        dc['teams'][plan['teams'].get(str(r['team_id']), 'No team')][key] += 1
    dc['teams'] = {k: dict(v) for k, v in dc['teams'].items()}
    if mode in ('apply', 'rehearse') and dry['people']:
        day = fields.Date.to_date(plan['date'])
        nxt = day + relativedelta(months=1)
        if mode == 'rehearse':
            main0, adv0 = population(company, emps.ids, nxt)
        max_before = snap()['person_rows'][1]
        res = B.fill_apply(company.id, ['ready', 'country'])
        env.flush_all()
        created = Row.search([('id', '>', max_before)], order='id')
        c['applied'] = {'people': res.get('people'), 'pending': bool(res.get('pending')),
                        'fill_id': res.get('fill_id') or (res.get('result') or {}).get('fill_id'),
                        'rows_created': len(created), 'rows_source': dict(Counter(created.mapped('source'))),
                        'message': str(res.get('message') or '')[:200]}
        for row in created:
            undo_lines.append([company.id, row.id, row.employee_id.id, row.config_id.id, row.cycle_type,
                               str(row.date_from), row.source])
        if mode == 'rehearse':
            main1, adv1 = population(company, emps.ids, nxt)
            twice = [e for e, s in main1.items() if len(s) > 1]
            missing = [e for e in main0 if e not in main1]
            moved = [e for e in main0 if e in main1 and sorted(main0[e]) != sorted(main1[e])]
            gained = [e for e in main1 if e not in main0]
            # people the fill gave a row: in exactly one main run of next month
            filled = set(created.mapped('employee_id').ids)
            filled_not_one = [e for e in filled if len(main1.get(e, [])) != 1]
            c['rehearse_runs'] = {'month': str(nxt), 'in_a_main_run_before': len(main0),
                                  'in_a_main_run_after': len(main1), 'in_two_main_runs': len(twice),
                                  'missing_after': len(missing), 'scheme_moved': len(moved),
                                  'gained': len(gained), 'filled_people': len(filled),
                                  'filled_not_in_exactly_one': len(filled_not_one),
                                  'advance_before': len(adv0), 'advance_after': len(adv1)}
            if twice or missing or filled_not_one:
                ok = False
            # the on-screen Undo path: "Undo this fill" (fill_undo, the button's call)
            fill_id = c['applied']['fill_id']
            u = B.fill_undo(fill_id, company.id) if fill_id else {}
            env.flush_all()
            left = Row.search_count([('id', 'in', created.ids)])
            main2, adv2 = population(company, emps.ids, nxt)
            c['rehearse_undo'] = {'answer': {k: u.get(k) for k in ('ok', 'applied', 'removed', 'people', 'kept')
                                             if k in u}, 'rows_left': left,
                                  'population_back_to_before': (dict(main2) == dict(main0)
                                                                and dict(adv2) == dict(adv0))}
            if left or not c['rehearse_undo']['population_back_to_before']:
                ok = False
    result['companies'].append(c)
    detail['companies'].append(dc)
result['after'] = snap()
result['ok'] = ok
json.dump(result, open(os.path.join(out, 'fill-%s.json' % db), 'w'), indent=1, default=str)
json.dump(detail, open(os.path.join(out, 'fill-detail-%s.json' % db), 'w'), indent=1, default=str,
          ensure_ascii=False)
if mode == 'apply':
    with open(os.path.join(out, 'person_scheme_fill_%s.csv' % db), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['company_id', 'person_scheme_id', 'employee_id', 'config_id', 'cycle_type', 'date_from',
                    'source', 'undo'])
        for line in undo_lines:
            w.writerow(line + ["env['pb.person.scheme'].sudo().browse(%s).unlink()" % line[1]])
    env.cr.commit()
    print('PROBE committed', len(undo_lines), 'rows')
else:
    env.cr.rollback()
    print('PROBE rolled back; dry run changed anything before the rollback:', mode == 'dry' and result['after'] != result['before'])
for c in result['companies']:
    print('PROBE company', c['company'], 'people', c['people_on_roster'], 'counts', c['counts'],
          'choice', c['choice_reasons'], 'dry gives', c['dry']['people'],
          'no country', c['no_country_in_company'], 'cow would fill', c['country_of_work_fill'].get('would_fill'),
          'applied', c.get('applied'), 'runs', c.get('rehearse_runs'), 'undo', c.get('rehearse_undo'))
print('PROBE ok', ok)
