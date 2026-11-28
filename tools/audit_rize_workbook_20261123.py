"""Read-only ORM snapshot for reconciliation with the client's private workbook.

Run in the Rize Odoo shell; RIZE_AUDIT_OUTPUT is a private JSON file.
No account, leave, payroll or configuration writes are committed.
"""
import json
import os
from pathlib import Path

assert env.cr.dbname == 'rize'
result = {}
for model in ['hr.employee', 'hr.contract', 'vietnam.employee.dependent',
              'pb.resignation', 'pb.asset.assignment']:
    if model not in env:
        continue
    M = env[model].sudo().with_context(active_test=False, lang='en_US')
    names = [n for n,f in M._fields.items() if
             f.type in ('char','text','selection','boolean','date','datetime',
                        'integer','float','monetary','many2one')
             and (f.store or n in ['department_id','country_id','marital','sex',
                 'work_location_id','address_id','identification_id','private_street',
                 'departure_date','currency_id'])]
    records = M.search([])
    result[model] = records.read(names)
    result[model + '.fields'] = M.fields_get(names, attributes=['string','type','selection','relation'])
path = Path(os.environ['RIZE_AUDIT_OUTPUT'])
path.write_text(json.dumps(result, default=str, ensure_ascii=False))
path.chmod(0o600)
env.cr.rollback()
print('AUDIT_SNAPSHOT', {k:len(v) for k,v in result.items() if not k.endswith('.fields')})
