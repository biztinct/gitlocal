# NEWHIRE P6 (payobook ONLY, demo database): the contract letter of the existing demo hire from P5b, made with
# the new PDF tool through the same call the studio's letter leg ends in, as the download (`contract_document_pdf`
# files NOTHING), as the QA login with the studio's one-contract pay gate key. The PDF bytes go to the evidence
# folder for a look; the transaction is rolled back. odoo-bin shell; OUT env var = target file.
import base64, os
assert env.cr.dbname == 'payobook', 'payobook only'
QA = 6672
u = env['res.users'].browse(QA)
assert u.exists() and u.login.startswith('qa.'), 'not the QA login'
e = env['hr.employee'].sudo().search([('name', '=', 'DEMO NH P5b Live Check')], limit=1)
assert e, 'demo hire missing'
c = e.contract_ids[:1]
r = env['pb.contracts'].with_user(u).with_context(allowed_company_ids=[e.company_id.id], lang='en_US',
                                                  pb_nh_letter_contract_id=c.id).contract_document_pdf(c.id)
if r.get('ok'):
    data = base64.b64decode(r['data'])
    with open(os.environ['OUT'], 'wb') as f:
        f.write(data)
    print('PROBE letter ok', r.get('name'), len(data), 'bytes; starts', data[:8])
else:
    print('PROBE letter refused', r.get('msg'))
env.cr.rollback()
