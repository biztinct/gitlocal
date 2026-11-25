# NEWHIRE P7 (odoo-bin shell, read-only, rolled back; rehearsal copy or live): what step 2 and step 5 now
# say for this database - for every Country of work: the default, how many teams are the country's /
# other / no signal, jobs held there, the time places() takes; the bank row's boxes for IN, SG, MY, AU.
import time
assert not env.cr.dbname.startswith('abm'), 'never abm'
NH = env['pb.new.hire']
for company in env['res.company'].sudo().search([], order='id'):
    people = env['hr.employee'].sudo().search_count([('company_id', '=', company.id), ('active', '=', True)])
    if not people:
        continue
    nh = NH.with_company(company).with_context(allowed_company_ids=[company.id]).sudo()
    line = ['company %s (%s people): default %s' % (company.id, people, nh._default_country())]
    for code, _label in nh._countries():
        t0 = time.perf_counter()
        p = nh.places(code)
        ms = (time.perf_counter() - t0) * 1000
        line.append('%s mine %s other %s none %s jobs %s %.0f ms cur %s' % (
            code, len(p['teams']['mine']), len(p['teams']['other']), len(p['teams']['unknown']), len(p['jobs']),
            ms, ((p['decides'] or {}).get('currency') or {}).get('name')))
    print('PROBE', ' | '.join(line))
Docs = NH.sudo()
for code in ('IN', 'SG', 'MY', 'ID', 'VN'):
    item = next(i for i in Docs._detail_items(code, 'DEMO') if i['key'] == 'bank')
    print('PROBE bank', code, [f['label'] for f in item['fields']])
print('PROBE bank AU', [f['label'] for f in item['bank']['fields']['AU']])
env.cr.rollback()
