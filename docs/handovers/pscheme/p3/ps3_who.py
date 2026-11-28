# PSCHEME P3 (odoo-bin shell, read-only, rolled back): "who pays each active person" - the answer the pay
# run and the screens read - per company: the map's answer per kind of run (any, end of month, regular,
# mid-month advance) on today, and next month's pay-run population per active scheme. Runs on the OLD code
# (before the stop) and the NEW code (after): with no pb.person.scheme rows the two must be identical.
# Env: PS3_OUT=<file>  -> JSON {company: {...}} written there (ids only, no names). Prints PROBE + md5.
import hashlib, json, os
from dateutil.relativedelta import relativedelta
from odoo import fields
assert not env.cr.dbname.startswith('abm'), 'never this database'
Map = env['pb.scheme.map'].sudo()
W = env['pb.payrun.wizard'].sudo()
Config = env['hr.formula.config'].sudo()
out = {}
rows = 'n/a'
if 'pb.person.scheme' in env:
    env.cr.execute("select count(*) from pb_person_scheme")
    rows = env.cr.fetchone()[0]
for company in env['res.company'].sudo().search([], order='id'):
    emps = env['hr.employee'].sudo().with_context(active_test=True).search([('company_id', '=', company.id)])
    if not emps:
        continue
    M = Map.with_company(company).with_context(allowed_company_ids=[company.id])
    today = fields.Date.context_today(M)
    nxt = today.replace(day=1) + relativedelta(months=1)
    c = {'people': len(emps)}
    for kind in ('any', 'end_cycle', 'regular', 'mid_cycle'):
        ans = M.resolve_many(emps.ids, kind)
        c[kind] = {str(e): (a or {}).get('config_id') or 0 for e, a in sorted(ans.items())}
    pop = {}
    Wc = W.with_company(company).with_context(allowed_company_ids=[company.id])
    for cfg in Config.search([('state', '=', 'active'), ('company_id', 'in', [company.id, False])], order='id'):
        covered = Wc._scheme_population(cfg.id, emps.ids, nxt)
        covered = covered[0] if isinstance(covered, tuple) else covered
        pop[str(cfg.id)] = sorted(covered.ids if hasattr(covered, 'ids') else covered)
    c['population_next_month'] = pop
    out[str(company.id)] = c
blob = json.dumps(out, sort_keys=True)
with open(os.environ['PS3_OUT'], 'w') as fh:
    fh.write(blob)
print('PROBE who-pays md5', hashlib.md5(blob.encode()).hexdigest(), 'companies', len(out),
      'people', sum(v['people'] for v in out.values()), 'person scheme rows', rows)
env.cr.rollback()
