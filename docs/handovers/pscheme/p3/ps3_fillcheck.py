# PSCHEME P3 D (odoo-bin shell, read-only, rolled back): the fill's before/after check on one database.
#   PS3_OUT=<file.json>  writes, per company and active person: the "who pays them" answer for the main
#   question (the company's main kind, MAIN_QUESTION - what "Paid by" and the screens ask) and for the
#   mid-month advance; the stored Paid by / advance / "needs working out again" flag; next month's pay-run
#   population per active scheme; the person-row count; the Mapping banner figures.
#   PS3_BEFORE=<file.json> (optional) compares with an earlier run and prints PROBE verdicts:
#     main same for everyone, advance same where it was a real mid-month scheme (ledger A13 / PS6), nobody in
#     two main runs next month, nobody missing who was in a main run before.
import json, os
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from odoo import fields
from odoo.addons.pb_scheme_map.models.pb_scheme_map import MAIN_QUESTION
assert not env.cr.dbname.startswith('abm'), 'never this database'
Map = env['pb.scheme.map'].sudo()
Config = env['hr.formula.config'].sudo().with_context(active_test=False)
out = {}
for company in env['res.company'].sudo().search([], order='id'):
    emps = env['hr.employee'].sudo().with_context(active_test=True).search([('company_id', '=', company.id)])
    if not emps:
        continue
    M = Map.with_company(company).with_context(allowed_company_ids=[company.id])
    main_kind = env['hr.employee']._pb_main_cycle(company.id)
    main = M.with_context(**{MAIN_QUESTION: True}).resolve_many(emps.ids, main_kind)
    adv = M.resolve_many(emps.ids, 'mid_cycle')
    today = fields.Date.context_today(M)
    nxt = today.replace(day=1) + relativedelta(months=1)
    W = env['pb.payrun.wizard'].sudo().with_company(company).with_context(allowed_company_ids=[company.id])
    runs = defaultdict(list)
    for cfg in Config.search([('state', '=', 'active'), ('company_id', 'in', [company.id, False])], order='id'):
        covered = W._scheme_population(cfg.id, emps.ids, nxt)
        covered = covered[0] if isinstance(covered, tuple) else covered
        for e in (covered.ids if hasattr(covered, 'ids') else covered):
            runs[str(e)].append([cfg.id, cfg.cycle_type])
    stored = {str(r['id']): [r['pb_paid_by_id'] and r['pb_paid_by_id'][0] or 0,
                             r['pb_paid_by_advance_id'] and r['pb_paid_by_advance_id'][0] or 0, r['pb_paid_by_stale']]
              for r in emps.read(['pb_paid_by_id', 'pb_paid_by_advance_id', 'pb_paid_by_stale'])}
    env.cr.execute("select count(*), count(distinct employee_id) from pb_person_scheme where company_id = %s and active",
                   [company.id])
    rows, people_with_rows = env.cr.fetchone()
    banner = env['pb.scheme.board'].with_company(company).with_context(
        allowed_company_ids=[company.id])._board_persons({'company_id': company.id, 'segments': []})
    out[str(company.id)] = {
        'month': str(nxt), 'rows': rows, 'people_with_rows': people_with_rows,
        'banner': {k: banner.get(k) for k in ('people', 'own', 'without', 'mismatch', 'latest_fill')},
        'main': {str(e): (a or {}).get('config_id') or 0 for e, a in main.items()},
        'advance': {str(e): (a or {}).get('config_id') or 0 for e, a in adv.items()},
        'stored': stored, 'runs': runs,
        'mid_ids': Config.search([('cycle_type', '=', 'mid_cycle')]).ids,
    }
json.dump(out, open(os.environ['PS3_OUT'], 'w'), default=str)
for cid, c in out.items():
    print('PROBE company', cid, 'person rows', c['rows'], 'people with rows', c['people_with_rows'], 'banner', c['banner'],
          'stale', sum(1 for v in c['stored'].values() if v[2]))
before = os.environ.get('PS3_BEFORE')
if before:
    b = json.load(open(before))
    for cid, c in out.items():
        o = b.get(cid) or {}
        filled = [e for e in c['main'] if c['rows'] and e in c['main']]
        main_moved = [e for e in c['main'] if o.get('main', {}).get(e) != c['main'][e]]
        mid = set(c['mid_ids'])
        adv_moved = [e for e in c['advance'] if (o.get('advance', {}).get(e) in mid or c['advance'][e])
                     and o.get('advance', {}).get(e) != c['advance'][e]]
        adv_dropped_artefact = [e for e in c['advance'] if o.get('advance', {}).get(e) and o['advance'][e] not in mid
                                and not c['advance'][e]]
        main_runs = lambda r: [x for x in r if x[1] != 'mid_cycle']
        twice = [e for e, r in c['runs'].items() if len(main_runs(r)) > 1]
        missing = [e for e, r in o.get('runs', {}).items() if main_runs(r) and not main_runs(c['runs'].get(e, []))]
        moved_run = [e for e, r in o.get('runs', {}).items() if main_runs(r) and e in c['runs']
                     and sorted(map(tuple, main_runs(r))) != sorted(map(tuple, main_runs(c['runs'][e])))]
        adv_runs_moved = [e for e in set(o.get('runs', {})) | set(c['runs'])
                          if sorted(tuple(x) for x in o.get('runs', {}).get(e, []) if x[1] == 'mid_cycle')
                          != sorted(tuple(x) for x in c['runs'].get(e, []) if x[1] == 'mid_cycle')]
        stored_main_moved = [e for e in c['stored'] if o.get('stored', {}).get(e, [0])[0] != c['stored'][e][0]]
        print('PROBE compare company', cid, '| main answer changed', len(main_moved), '| real advance changed', len(adv_moved),
              '| advance display artefact dropped (PS6, expected)', len(adv_dropped_artefact),
              '| next month: in two main runs', len(twice), 'missing', len(missing), 'main run moved', len(moved_run),
              'advance run moved', len(adv_runs_moved), '| stored Paid by changed', len(stored_main_moved),
              '| stale', sum(1 for v in c['stored'].values() if v[2]))
env.cr.rollback()
