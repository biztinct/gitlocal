"""Verify the owner-authorized August Drafts against private source controls.

Run in the Rize Odoo shell. RIZE_MASTER_DIR is private working storage.
RIZE_RECONCILE_PHASE=baseline records business hashes before the Chrome runs;
the default compares the two completed Drafts without modifying them.
"""
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path

assert env.cr.dbname=='rize'
root=Path(os.environ['RIZE_MASTER_DIR'])
e=env(user=2,context=dict(env.context,allowed_company_ids=[1]))
phase=os.environ.get('RIZE_RECONCILE_PHASE','compare')
tables=('hr_employee','hr_contract','hr_contract_advantage','res_partner_bank','vietnam_employee_dependent')


def digest(table,ids=None):
    if ids is None:e.cr.execute('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY id')
    else:e.cr.execute('SELECT row_to_json(t)::text FROM '+table+' t WHERE id=ANY(%s) ORDER BY id',[ids])
    return hashlib.sha256('\n'.join(r[0] for r in e.cr.fetchall()).encode()).hexdigest()


if phase=='baseline':
    before=dict(hashes={t:digest(t) for t in tables},payroll={})
    for table in ('hr_payslip','hr_payslip_run'):
        e.cr.execute('SELECT id FROM '+table+' ORDER BY id');ids=[r[0] for r in e.cr.fetchall()]
        before['payroll'][table]=dict(ids=ids,sha256=digest(table,ids))
    (root/'before-chrome.json').write_text(json.dumps(before,indent=2))
    print('RIZE_CHROME_BASELINE '+json.dumps(dict(protected_tables=len(tables),existing_slips=len(before['payroll']['hr_payslip']['ids']))))
else:
    before=json.loads((root/'before-chrome.json').read_text())
    assert {t:digest(t) for t in tables}==before['hashes'],'Master records changed during the monthly/payroll test.'
    for table,record in before['payroll'].items():assert digest(table,record['ids'])==record['sha256'],'Existing payroll history changed.'
    reports={}
    for key in ('sg','id'):
        definition=json.loads((root/(key+'-definition.json')).read_text())
        fixtures={r['code']:r for r in json.loads((root/(key+'-fixtures.json')).read_text())}
        fills=json.loads((root/(key+'-fill-plan.json')).read_text())['cells']
        expected_inputs={(r['employee_code'],r['code']):r['value'] for r in fills}
        cfg=e['hr.formula.config'].search([('code','=',definition['code'])])
        assert len(cfg)==1 and cfg.state=='active'
        bycol={r.column_letter:r.code for r in cfg.rule_ids}
        runs=e['hr.payslip.run'].search([('pb_formula_config_id','=',cfg.id),('date_start','=','2026-08-01'),('date_end','=','2026-08-31')])
        assert len(runs)==1,runs.ids
        run=runs.ensure_one()
        assert run.state=='draft' and len(run.slip_ids)==len(fixtures)
        assert {s.employee_id.barcode for s in run.slip_ids}==set(fixtures)
        assert all(s.state=='draft' for s in run.slip_ids)
        comparisons=0;input_checks=0;totals=defaultdict(float);evidence=[]
        cols={'gross':'AJ','deduction':'AI','net':'AA','tax':'AL','employer_cost':'AK'} if key=='sg' else {'gross':'Z','deduction':'AP','net':'AQ','tax':'AN','employer_cost':'BT'}
        for slip in run.slip_ids:
            code=slip.employee_id.barcode;actual=json.loads(slip.formula_computed_values or '{}');inputs=json.loads(slip.formula_input_values or '{}')
            assert not slip.has_formula_errors and actual[definition['country']+'READY']=='Ready',code
            for component,value in fixtures[code]['expected'].items():
                if isinstance(value,(int,float)):assert abs(float(actual[component])-value)<.00001,(code,component,actual[component],value)
                else:assert actual[component]==value,(code,component,actual[component],value)
                comparisons+=1
            for (person,component),value in expected_inputs.items():
                if person!=code:continue
                if isinstance(value,(int,float)):assert abs(float(inputs[component])-value)<.00001,(code,component)
                else:assert inputs[component]==value,(code,component,inputs.get(component),value)
                input_checks+=1
            counted=[l for l in slip.line_ids if not l.component_detail]
            for role,metric in [('earning','gross'),('deduction','deduction'),('net','net'),('employer_cost','employer_cost')]:
                expected=actual[bycol[cols[metric]]]
                assert abs(sum(l.total for l in counted if l.pay_role==role)-expected)<.01,(code,role)
            for metric,col in cols.items():totals[metric]+=actual[bycol[col]]
            evidence.append(dict(id=slip.id,code=code,state=slip.state,inputs=inputs,computed=actual))
        assert abs(run.pb_total_gross-totals['gross'])<.01
        assert abs(run.pb_total_deductions-totals['deduction'])<.01
        assert abs(run.pb_total_net-totals['net'])<.01
        assert abs(totals['gross']-totals['deduction']-totals['net'])<.01
        batches=e['hr.payroll.import.batch'].search([('payslip_run_id','=',run.id)])
        assert len(batches)==1 and batches.one_time and batches.error_lines==0 and batches.total_lines==len(fixtures)
        assert not batches.created_employee_ids and not batches.created_contract_ids
        assert not e['pb.payroll.month.inputs'].sudo().search_count([('config_id','=',cfg.id),('period','=','2026-10')])
        problems=e['pb.formula.studio'].get_problems(cfg.id)
        reports[key]=dict(config_id=cfg.id,run_id=run.id,run_name=run.name,state=run.state,employees=len(fixtures),
            exact_value_comparisons=comparisons,uploaded_input_comparisons=input_checks,totals=dict(totals),
            batch_id=batches.id,batch_errors=batches.error_lines,no_records_created_by_payroll=True,
            other_payroll_and_master_data_unchanged=True,october_inputs_not_carried=True,
            stored_scenarios=dict(total=len(cfg.sample_data_ids),passed=len(cfg.sample_data_ids.filtered('all_passed'))),
            problems=problems,slips=evidence)
        assert reports[key]['stored_scenarios']['total']==reports[key]['stored_scenarios']['passed']==len(fixtures)
    (root/'payrun-reconciliation.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2,default=str))
    print('RIZE_PAYRUN_RECONCILIATION '+json.dumps({k:{a:b for a,b in v.items() if a not in ('slips','problems')} for k,v in reports.items()},default=str),flush=True)
e.cr.rollback()
