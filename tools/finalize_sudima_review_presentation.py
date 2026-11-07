"""Use the existing Rename component UI service for the guided tax summary.

The formula and monetary results stay unchanged. Default is rollback; set
SUDIMA_PRESENTATION_APPLY=1 to commit after saved scenarios and preview pass.
"""
import json
import os

assert env.cr.dbname=='sudima'
e=env(user=2,context=dict(env.context,allowed_company_ids=[1],lang='en_US'))
cfg=e['hr.formula.config'].search([('code','=','SUDIMA_SEP_2026_AUDIT')])
assert len(cfg)==1 and cfg.state=='draft' and not cfg.application_data_enabled
old=cfg.rule_ids.filtered(lambda r:r.code=='VNTAX')
if old:
    renamed=e['pb.formula.studio'].rename_component(old.id,'PIT')
    assert renamed.get('ok'),renamed
else:
    assert len(cfg.rule_ids.filtered(lambda r:r.code=='PIT'))==1
tests=cfg.run_sample_tests()
assert tests['total']==tests['passed']==650 and tests['failed']==0,tests
sample=next(s for s in cfg.sample_data_ids if json.loads(s.expected_values_json or '{}').get('PIT',0)>0)
preview=e['pb.blueprint.studio'].bp_preview(cfg.id,sample.id)
assert preview.get('ok'),preview
tax=next(line for line in preview['lines'] if line['key']=='tax')
assert tax['value']==json.loads(sample.expected_values_json)['PIT']
assert preview['take_home']['value']==json.loads(sample.expected_values_json)['VNNET']
result={'configuration':cfg.id,'tests':tests,'income_tax_preview_verified':True,
        'applied':os.getenv('SUDIMA_PRESENTATION_APPLY')=='1'}
if result['applied']:e.cr.commit()
else:e.cr.rollback()
print('SUDIMA_PRESENTATION',json.dumps(result))
