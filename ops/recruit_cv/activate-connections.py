"""Run inside an Odoo shell for each in-scope database, after service acceptance.

RECRUIT_CV_KEY is supplied through the protected environment file; no secrets
are printed. Only CV connections are changed. Other providers stay unchanged.
"""
import json
import os

key = os.environ['RECRUIT_CV_KEY']
url = 'https://payobook.com/_internal/recruit-cv'
assert len(key) >= 32
results = []
for company in env['res.company'].sudo().search([]):
    facade = env['pb.hiring'].sudo().with_company(company).with_context(allowed_company_ids=company.ids)
    row = env['pb.hiring.connection']._for_company('cv', company)
    if not row or row._config().get('url') != url or row._secret('api_key') != key:
        facade.connection_save('cv', {'url': url, 'api_key': key})
    checked = facade.connection_check('cv')
    assert checked['check_ok'], (company.id, checked['note'])
    enabled = facade.connection_enable('cv', True)
    assert enabled['enabled']
    results.append({'company_id': company.id, 'checked': True, 'enabled': True})
env.cr.commit()
print(json.dumps({'database': env.cr.dbname, 'cv_connections': results}))
