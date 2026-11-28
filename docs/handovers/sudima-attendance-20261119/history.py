"""Odoo shell: opt in with SUDIMA_HISTORY_APPLY=1. Same History from field as connector UI."""
import json,os
from datetime import date
assert env.cr.dbname=='sudima'
company=env['res.company'].search([('name','=','Sudima Panels Vietnam')]);assert len(company)==1
actor=env['res.users'].search([('login','=','ash@biztinct.com')]);assert len(actor)==1
records=env['pb.clock.connector'].with_user(actor).with_company(company).browse([5,6,7,8]).exists()
assert len(records)==4 and all(r.company_id==company and not r.publish_punches for r in records)
before=records.read(['name','history_from','interval_minutes','source_group','publish_punches'])
for r in records:
 assert r.history_from in (date(2026,11,18),date(2026,10,1)),(r.id,r.history_from)
 if r.history_from!=date(2026,10,1):r.write({'history_from':date(2026,10,1)})
receipt={'before':before,'after':records.read(['name','history_from','interval_minutes','source_group','publish_punches']),'apply':os.getenv('SUDIMA_HISTORY_APPLY')=='1'}
if receipt['apply']:env.cr.commit()
else:env.cr.rollback()
print('HISTORY_RECEIPT '+json.dumps(receipt,default=str))
