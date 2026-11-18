"""Apply the 18 November client confirmations to Rize; rollback by default.

RIZE_CONFIRM_DIR holds the private source plan and permanent database backup.
RIZE_CONFIRM_APPLY=1 commits. Bank changes retain the second-person workflow.
Existing formulas and payslips are verified and never rewritten.
"""
import fcntl
import json
import os
from datetime import date
from pathlib import Path
from markupsafe import Markup, escape
from odoo.addons.pb_hr_payroll_formula.formula_engine import FormulaEvaluator

assert env.cr.dbname == 'rize'
root = Path(os.environ['RIZE_CONFIRM_DIR'])
apply = os.getenv('RIZE_CONFIRM_APPLY') == '1'
assert (root / 'rize-before.dump').stat().st_size > 1000000
assert not (root / 'applied.json').exists(), 'Already applied; inspect receipt.'
plan = json.loads((root / 'plan.json').read_text())
lock = open('/tmp/payobook-studio-deploy.lock', 'r')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
e = env(user=2, context=dict(env.context, allowed_company_ids=[1],
    mail_create_nosubscribe=True, mail_notrack=True))
assert e.user.login == 'ash@biztinct.com' and not e.su
cfg = e['hr.formula.config'].browse(7118)
assert cfg.code == 'RIZE_VN_FOCUSED_2026' and cfg.state == 'active'
e['pb.payroll.templates']._lock(cfg)
by = {r.code: r for r in cfg.rule_ids}
E, C = e['hr.employee'], e['hr.contract']
people = E.browse([3281,3873,3876,3291,3304,3308,3318])
assert {p.barcode for p in people} == set(plan['employees'])
assert all(p.active and p.company_id.id == 1 and p.payroll_country == 'VN' for p in people)

def digest(table, where='TRUE'):
    e.cr.execute("SELECT count(*),md5(coalesce(string_agg(row_to_json(t)::text,chr(10) ORDER BY id),'')) FROM " + table + ' t WHERE ' + where)
    return list(e.cr.fetchone())

protected = ['hr_payslip','hr_payslip_line','hr_payslip_run','pb_payroll_month_inputs',
    'hr_formula_config','hr_formula_rule','res_partner_bank','res_bank',
    'vietnam_employee_dependent','hr_leave','hr_leave_allocation']
e.flush_all()
before = {t:digest(t) for t in protected}
other_contracts = digest('hr_contract','id NOT IN (1734,3700,2199)')
other_lines = digest('hr_contract_advantage','contract_id != 2199')
wages = C.search([]).read(['wage'])
bank_before = E.browse(3873).read(['vietnam_bank_name','vietnam_bank_account_name','vietnam_bank_account_number','bank_account_ids'])
# These four managers already have the confirmed values, including Loc's
# preceding contract covering October. Do not duplicate or redate their pay.
manager_contracts = C.browse([1757,1761,1771,3712,3716])
for c in manager_contracts:
    vals = e['hr.payroll.import.batch']._contract_component_values(c, config=cfg)
    assert vals['vntransport'] == 960000 and vals['vnphone'] == 360000, c.id

old, renewal = C.browse(1734), C.browse(3700)
assert old.employee_id == renewal.employee_id == E.browse(3281)
assert str(old.date_end) == '2025-11-15' and str(renewal.date_start) == '2025-11-16'
assert renewal.pb_renewed_from_id == old and not renewal.date_end
old.write({'date_end':'2024-11-15'})
renewal.write({'date_start':'2024-11-16', 'name':'Client confirmed RIZ017 — 2024-11-16',
              'vietnam_contract_type':'indefinite','type_id':13,'contract_type_id':1})
assert old.date_end < renewal.date_start
assert not C.search_count([('employee_id','=',3281),('id','not in',[1734,3700]),
    ('state','!=','cancel'),('date_start','<=','2024-11-16'),'|',('date_end','=',False),('date_end','>=','2024-11-16')])

han = C.browse(2199)
assert han.employee_id == E.browse(3876) and str(han.date_start) == '2026-10-01'
assert han.vietnam_other_allowances == 1320000
changes = [{'emp_id':3876,'field_id':'c:'+code,'value':value}
    for code,value in [('VNTRANSPORT',960000),('VNPHONE',360000),('VNHCBQ',0)]]
allowance = e['pb.records.desk'].apply_changes(cfg.id, changes, start_date='2026-10-01',
    note=plan['allowance_note'],source='import')
assert allowance.get('ok') and not allowance.get('refused'), allowance
assert allowance.get('written') == 3 and not allowance.get('pending'), allowance
# Keep the HR contract fields consistent with the actual payroll components.
han.write({'vietnam_transport_allowance':960000,'vietnam_phone_allowance':360000,
           'vietnam_other_allowances':0})
assert han.wage == 18000000
for code,value in [('VNTRANSPORT',960000),('VNPHONE',360000),('VNHCBQ',0)]:
    line = han.advantages_ids.filtered(lambda a:a.advantage_template_code == code)
    assert len(line) == 1 and line.amount == value
    log = e['hr.contract.advantage.change'].search([('contract_id','=',han.id),
        ('advantage_template_code','=',code)],order='id desc',limit=1)
    assert log.effective_date == date(2026,10,1) and log.new_amount == value

# Use the production source resolver, then evaluate the live formulas at full,
# half and zero days. No payslip or pay-run is created or recomputed.
tests=[]
for c in manager_contracts | han:
    slip = e['hr.payslip'].new({'employee_id':c.employee_id.id,'contract_id':c.id,
        'date_from':max(c.date_start,date(2026,10,1)),'date_to':date(2026,11,30),
        'formula_config_id':cfg.id})
    sources={}
    saved = slip.with_context(pb_application_data_mode=True)._get_formula_input_values(cfg,provenance=sources)
    assert saved['VNTRANSPORT'] == 960000 and saved['VNPHONE'] == 360000
    for code in ['VNTRANSPORT','VNPHONE']:
        assert sources[code]['src'] == 'contract_component',sources[code]
    for days in [22,11,0]:
        inputs=json.loads(cfg.sample_data_ids[:1].input_values_json)
        inputs.update(VNHCBK=c.wage,VNINSBASE=c.wage,VNTRANSPORT=saved['VNTRANSPORT'],
            VNPHONE=saved['VNPHONE'],VNHCBQ=0,VNSTDDAYS=22,VNPAIDDAYS=days,
            VNPTYPE='Probation' if c.pb_payroll_contract_type=='probation' else 'Permanent')
        actual=FormulaEvaluator().evaluate_all(cfg.rule_ids.sorted('sequence'),inputs)
        zero=FormulaEvaluator().evaluate_all(cfg.rule_ids.sorted('sequence'),dict(inputs,VNTRANSPORT=0,VNPHONE=0))
        expected=1320000*days/22
        assert actual['VNREADY']=='Ready',actual['VNREADY']
        assert actual['VNTRANSPAY']==960000*days/22
        assert actual['VNPHONEPAY']==360000*days/22
        for code in ['VNTOTALINC','VNTAXABLE','VNCASHGROSS']:
            assert abs(actual[code]-zero[code]-expected)<0.01,(c.id,days,code)
        for code in ['VNEFFINS','VNSIEMP','VNHIEMP','VNUIEMP','VNSIER','VNHIERR','VNUIERR','VNBASIC']:
            assert actual[code]==zero[code],(c.id,days,code)
        assert actual['VNPITDUE'] >= zero['VNPITDUE']
        tests.append({'employee':c.employee_id.barcode,'contract':c.id,'days':days,
            'transport':actual['VNTRANSPAY'],'phone':actual['VNPHONEPAY'],
            'taxable_increase':expected,'insurance_unchanged':True})

# A supplied bank correction is submitted by Ash, never approved as another
# person. The site's named independent approvers remain authoritative.
assert not e['res.partner.bank'].sudo().search_count([('acc_number','=',plan['bank']['acc_number'])])
bank_changes=[{'emp_id':3873,'field_id':'b:'+k,'value':v} for k,v in plan['bank'].items()]
bank=e['pb.records.desk'].apply_changes(0,bank_changes,source='import',
    note='Client confirmed RIZ232 bank details on 18 November 2026. Replace missing-information placeholders. Private source retained in permanent archive.')
assert bank.get('ok') and not bank.get('refused') and bank.get('pending') and not bank.get('written'),bank
assert E.browse(3873).read(list(bank_before[0])) == bank_before

notes=[]
for code,body in plan['notes'].items():
    p=people.filtered(lambda x:x.barcode==code)
    msg=e['mail.message'].sudo().create({'model':'hr.employee','res_id':p.id,
        'body':Markup('<p>')+escape(body)+Markup('</p>'),'message_type':'comment',
        'subtype_id':e.ref('mail.mt_note').id,'author_id':e.user.partner_id.id})
    notes.append(msg.id)
e.flush_all()
assert before == {t:digest(t) for t in protected}, 'Protected payroll/configuration/bank data changed'
assert other_contracts == digest('hr_contract','id NOT IN (1734,3700,2199)')
assert other_lines == digest('hr_contract_advantage','contract_id != 2199')
assert wages == C.search([]).read(['wage'])
receipt={'database':'rize','applied':apply,'contract_start':'2024-11-16',
    'old_contract_end':'2024-11-15','indefinite':True,'allowance_result':allowance,
    'bank_result':bank,'calculation_tests':tests,'protected':before,'wages_unchanged':True,
    'existing_manager_allowances_verified':True,'note_ids':notes}
path=root/('applied.json' if apply else 'rehearsal.json')
path.write_text(json.dumps(receipt,default=str,ensure_ascii=False,indent=2));path.chmod(0o600)
if apply:e.cr.commit()
else:e.cr.rollback()
print('CONFIRMATIONS_RESULT',json.dumps({'applied':apply,'calculation_tests':len(tests),
    'allowance_reference':allowance['reference'],'bank_reference':bank['reference'],
    'bank_waiting_for':bank['with_whom'],'formulas_and_payslips_unchanged':True},default=str))
