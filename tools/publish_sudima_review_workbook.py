"""Replace the draft's source workbook through the existing mapping upload UI.

Requires the tested, colour-coded template.xlsx in SUDIMA_REVIEW_DIR.
No employee values or monthly inputs are imported by this service.
"""
import base64
import hashlib
import json
import os
from pathlib import Path

assert env.cr.dbname=='sudima'
e=env(user=2,context=dict(env.context,allowed_company_ids=[1],lang='en_US'))
cfg=e['hr.formula.config'].search([('code','=','SUDIMA_SEP_2026_AUDIT')])
assert len(cfg)==1 and cfg.state=='draft'
raw=(Path(os.environ['SUDIMA_REVIEW_DIR'])/'template.xlsx').read_bytes()
studio=e['pb.formula.studio']
result=studio.import_mapping_read_headers(cfg.id,base64.b64encode(raw).decode(),
    'Sudima_September_Payroll_Review_Template.xlsx')
assert not result.get('msg') and result.get('read',{}).get('columns',0)>=55,result.keys()
assert base64.b64decode(cfg.with_context(bin_size=False).import_sample_file)==raw
assert len(cfg.rule_ids)==55 and not cfg.application_data_enabled
env.cr.commit()
print('SUDIMA_WORKBOOK_PUBLISHED',json.dumps({'configuration':cfg.id,
    'sha256':hashlib.sha256(raw).hexdigest(),'headers':result['read']['columns']}))
