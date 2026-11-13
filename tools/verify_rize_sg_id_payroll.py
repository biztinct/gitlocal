"""Read-only arithmetic checks for the deployed Rize client definitions.

Run in the Rize Odoo shell with RIZE_MASTER_DIR holding private definitions
and fixtures. Does not create payslips or write employee/monthly records.
"""
from decimal import Decimal, ROUND_HALF_UP
import json
import os
from pathlib import Path

assert env.cr.dbname=='rize'
root=Path(os.environ['RIZE_MASTER_DIR'])
e=env(user=2,context=dict(env.context,allowed_company_ids=[1]))
report={}
rounded=lambda x:float(Decimal(str(x)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
for key in ('sg','id'):
    definition=json.loads((root/(key+'-definition.json')).read_text())
    fixtures=json.loads((root/(key+'-fixtures.json')).read_text())
    cfg=e['hr.formula.config'].search([('code','=',definition['code'])])
    assert len(cfg)==1
    bycol={s['column']:s['code'] for s in definition['rules']}
    sample=e['hr.formula.sample.data'].new(dict(config_id=cfg.id))
    base=dict(fixtures[0]['values'])
    count=0
    def check(values,expected):
        global count
        errors={}
        actual=sample._evaluate_rules_with_dependencies(values,readonly=True,errors=errors)
        assert not errors,errors
        for code,value in expected.items():
            if isinstance(value,(int,float)):assert abs(float(actual.get(code))-value)<.00001,(key,code,actual.get(code),value)
            else:assert actual.get(code)==value,(key,code,actual.get(code),value)
        count+=1
        return actual
    if key=='sg':
        for salary,sdl in [(609.5,2),(2000,5),(4500,11.25),(4502.03,11.25)]:
            values=dict(base,**{bycol['H']:salary,bycol['I']:0,bycol['K']:0,bycol['L']:0,
                bycol['T']:20,bycol['U']:0,bycol['V']:0,bycol['Y']:0,bycol['Z']:0})
            check(values,{bycol['M']:sdl,bycol['AA']:rounded(salary),'SGREADY':'Ready'})
        values=dict(base,**{bycol['U']:20,bycol['I']:0,bycol['K']:0,bycol['L']:0,bycol['Y']:0,bycol['Z']:0})
        check(values,{bycol['M']:0,bycol['AA']:0,bycol['AJ']:0,'SGREADY':'Ready'})
        values=dict(base,**{bycol['H']:4000,bycol['I']:0,bycol['K']:0,bycol['L']:0,
            bycol['T']:20,bycol['U']:2,bycol['V']:0,bycol['Y']:100,bycol['Z']:25})
        check(values,{bycol['AA']:3725,bycol['AJ']:3725,'SGREADY':'Ready'})
        check(dict(base,**{bycol['U']:-1}),{'SGREADY':'Review payable days'})
    else:
        # Simplify independent TER controls to uncovered ordinary wages, with
        # no premium, allowances or already-paid deductions.
        for s in definition['rules']:
            if s['tab'] and s['kind'] not in ('text','identifier','date'):base[s['code']]=0
        base.update({bycol['AT']:31,bycol['AU']:31,bycol['AS']:8000000,bycol['AW']:0,
            bycol['AX']:0,bycol['AY']:0,bycol['AZ']:0,bycol['BA']:0,bycol['BB']:0,
            bycol['J']:'S/0'})
        bands=json.loads((root/'id-controls.json').read_text())['bands']
        for category,status in [('A','S/0'),('B','M/2'),('C','M/3')]:
            cap=bands[category][0][0]
            for gross in (cap-1,cap,cap+1):
                rate=next(rate for upper,rate in bands[category] if not upper or gross<=upper)
                check(dict(base,**{bycol['AS']:gross,bycol['J']:status}),
                    {bycol['AN']:rounded(gross*rate),bycol['AQ']:gross-rounded(gross*rate),'IDREADY':'Ready'})
        values=dict(base,**{bycol['AS']:10000000,bycol['BA']:2,bycol['BB']:1,
            bycol['BC']:110000000,bycol['BD']:0,bycol['BE']:12,bycol['BF']:2750000,
            'IDFINALALLOW':294100,'IDYTDREVIEW':1})
        # 120,294,100 annual gross - 6m job expenses - 54m PTKP ->
        # 60,294,000 rounded PKP. Annual tax 3,044,100 - prior 2,750,000.
        check(values,{bycol['M']:294100,bycol['AN']:294100,bycol['AQ']:10000000,bycol['BS']:0,'IDREADY':'Ready'})
        check(dict(values,IDYTDREVIEW=0),{'IDREADY':'Review final-period YTD'})
        check(dict(values,IDFINALALLOW=0),{'IDREADY':'Review annual net gross-up'})
        check(dict(base,**{bycol['Y']:100000}),{'IDREADY':'Confirm severance eligibility'})
        check(dict(base,**{bycol['AT']:32}),{'IDREADY':'Review payable days'})
        check(dict(base,**{bycol['BA']:3}),{'IDREADY':'Review coverage and tax flags'})
    report[key]=dict(config_id=cfg.id,future_scenarios=count,all_passed=True)
env.cr.rollback()
print('RIZE_FUTURE_SCENARIOS '+json.dumps(report),flush=True)
