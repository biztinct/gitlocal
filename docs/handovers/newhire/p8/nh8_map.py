# NEWHIRE P8 B.2 (odoo-bin shell): map rize's teams to the pay scheme of their country of work through the
# Mapping board's own write (pb.scheme.board.accept_country_suggestions - the same path as "Suggest who pays
# each team" -> Set; run as the shell's system user). Only the clean suggestions (state 'suggest': every person
# of the team is paid by that scheme today, or by none); never a team already mapped. Architect ruling 2: a team
# where ANY person's paying scheme would differ after the mapping drops out (and joins the owner's list).
# Env: NH8_MODE=dry|apply  NH8_OUT=<folder>  (dry: everything is rolled back; apply: committed + undo file)
# Writes <out>/map-result.json (counts + ids) and <out>/map-detail.json (names: CLIENT DATA, never committed).
import csv, json, os
assert env.cr.dbname not in ('abm', '_test_sudima_policy_20261119'), 'never this database'
mode = os.environ.get('NH8_MODE', 'dry')
out = os.environ['NH8_OUT']
company = env['res.company'].browse(1)
Map = env['pb.scheme.map'].sudo()
Board = env['pb.scheme.board'].with_company(company).with_context(allowed_company_ids=[company.id])
Assign = env['hr.formula.scheme.assignment'].sudo().with_context(active_test=False)
Emp = env['hr.employee'].sudo()


def snapshot():
    env.flush_all()
    q = {}
    for t in ('hr_payslip', 'hr_payslip_run', 'hr_contract', 'hr_payslip_line'):
        env.cr.execute('SELECT count(*), max(write_date) FROM %s' % t)
        n, w = env.cr.fetchone()
        q[t] = [n, str(w)]
    env.cr.execute('SELECT count(*), max(write_date) FROM hr_formula_scheme_assignment')
    q['map_rows'] = list(map(str, env.cr.fetchone()))
    env.cr.execute('SELECT count(*) FILTER (WHERE pb_paid_by_stale), count(*) FROM hr_employee WHERE company_id = 1')
    q['stale_of_people'] = list(env.cr.fetchone())
    return q


def paying(ids):
    return {e: (a.get('config_id') or 0) for e, a in Map.resolve_many(ids, 'any').items()}


roster = Map._departments_for(company_ids=[company.id])
people = sorted(roster)
before_snap = snapshot()
before = paying(people)
sugg = Board.country_suggestions(company.id)
rows = sugg['rows']
clean = [r for r in rows if r['state'] == 'suggest']
dropped = []
created_ids = []
for attempt in range(3):
    sp = env.cr.savepoint()
    rows_before = set(Assign.search([]).ids)
    res = Board.accept_country_suggestions([r['department_id'] for r in clean], company.id)
    env.flush_all()
    after = paying(people)
    changed = [e for e in people if after.get(e) != before.get(e)]
    bad_teams = sorted({roster[e][0] for e in changed})
    if not changed:
        created_ids = sorted(set(Assign.search([]).ids) - rows_before)
        sp.close(rollback=False)
        break
    sp.close(rollback=True)
    env.invalidate_all()
    dropped += [r for r in clean if r['department_id'] in bad_teams]
    clean = [r for r in clean if r['department_id'] not in bad_teams]
else:
    raise SystemExit('could not reach a mapping that changes nobody')
if clean and len(created_ids) != len(clean):
    # a route that needs a second person: nothing was written - say so, write nothing
    env.cr.rollback()
    raise SystemExit('NOT APPLIED: %s of %s rows written (the change waits for approval: %s)' % (
        len(created_ids), len(clean), res.get('state')))
after_snap = snapshot()
new_rows = Assign.browse(created_ids)
labels = dict(env['hr.formula.config']._fields['country_code']._description_selection(env))
by_country = {}
for r in clean:
    by_country.setdefault(r['country'] or '-', {'mapped': 0, 'left': 0})['mapped'] += 1
for r in rows:
    if r not in clean and r['people']:
        by_country.setdefault(r['country'] or '-', {'mapped': 0, 'left': 0})['left'] += 1
result = {
    'mode': mode, 'db': env.cr.dbname,
    'teams_listed': len(rows), 'already_mapped': sugg['mapped'], 'states': sugg['counts'],
    'mapped': len(clean), 'dropped_after_check': len(dropped), 'rows_created': created_ids,
    'proposal': {k: res.get(k) for k in ('applied', 'state', 'reference', 'created', 'replaced')},
    'people_checked': len(people),
    'people_changed_scheme': len([e for e in people if after.get(e) != before.get(e)]),
    'before': before_snap, 'after': after_snap, 'by_country': by_country,
    'empty_teams': len([r for r in rows if r['state'] == 'none']),
}
names = {d.id: d for d in env['hr.department'].sudo().with_context(active_test=False).browse(
    [r['department_id'] for r in rows])}
cfg_names = {c.id: c.name for c in env['hr.formula.config'].sudo().search([])}
detail = {'mapped': [], 'mixed': [], 'others': []}
for r in rows:
    team = names[r['department_id']].name
    if r in clean:
        detail['mapped'].append({'team': team, 'scheme': r['config'], 'people': r['people']})
        continue
    ids = [e for e, (d, _c) in roster.items() if d == r['department_id']]
    counts = {}
    for e in Emp.browse(ids):
        counts[e.payroll_country or ''] = counts.get(e.payroll_country or '', 0) + 1
    if len([c for c in counts if c]) > 1:
        # a team with people in several countries: one row per person
        top, n = max(counts.items(), key=lambda kv: kv[1])
        if n * 2 <= len(ids):
            top = ''                                # no single country for most of them
        schemes = Map._country_schemes(company.id, top) if top else env['hr.formula.config']
        major = schemes[:1].name if len(schemes) == 1 else ''
        for e in Emp.browse(ids).sorted('name'):
            today = cfg_names.get(before.get(e.id) or 0, '')
            detail['mixed'].append({
                'team': team, 'person': e.name, 'country': labels.get(e.payroll_country or '', '') or 'Not set',
                'paid_today': today or 'Nobody yet', 'majority': major or 'No single scheme',
                'would_change': 'Yes' if major and today != major else 'No'})
    else:
        detail['others'].append({'team': team, 'people': r['people'], 'reason': r['reason']})
os.makedirs(out, exist_ok=True)
json.dump(result, open(os.path.join(out, 'map-result.json'), 'w'), indent=1, default=str)
json.dump(detail, open(os.path.join(out, 'map-detail.json'), 'w'), indent=1, default=str)
if mode == 'apply':
    with open(os.path.join(out, 'rize_team_map_undo.csv'), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['assignment_id', 'department_id', 'config_id', 'cycle_type', 'source', 'undo'])
        for row in new_rows:
            w.writerow([row.id, row.department_id.id, row.config_id.id, row.cycle_type, row.source,
                        "env['hr.formula.scheme.assignment'].browse(%s).unlink()" % row.id])
    env.cr.commit()
    print('PROBE committed', len(created_ids))
else:
    env.cr.rollback()
    print('PROBE rolled back')
print('PROBE', json.dumps({k: result[k] for k in ('mapped', 'dropped_after_check', 'people_checked',
                                                  'people_changed_scheme', 'by_country', 'states')}))
