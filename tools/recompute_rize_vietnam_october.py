"""Recompute only the repaired, still-draft October Rize Vietnam payroll.

Checks the owner's August salary baseline, preserves October inputs and August
history, independently checks the existing client formulas, and commits only
with VN_RECOMPUTE_APPLY=1. Never submits or approves payroll.
"""
import hashlib
import json
import math
import os

assert env.cr.dbname == 'rize'
run = env['hr.payslip.run'].browse(685).exists()
cfg = run.pb_formula_config_id
previous = env['hr.payslip.run'].browse(681).exists()
assert cfg.id == 3942 and cfg.country_code == 'VN' and cfg.currency_id.name == 'VND'
env.cr.execute('SELECT id FROM hr_payslip_run WHERE id=%s FOR UPDATE', (run.id,))
env.cr.execute('SELECT id FROM hr_payslip WHERE payslip_run_id=%s ORDER BY id FOR UPDATE', (run.id,))
assert run.state == 'draft' and len(run.slip_ids) == 70
assert all(s.state == 'draft' for s in run.slip_ids)
assert env['ir.module.module'].search([('name', '=', 'pb_payroll_templates')]).latest_version == '19.0.1.0.2'
target = env(context=dict(env.context, allowed_company_ids=cfg.company_id.ids))
run = run.with_env(target)
previous = previous.with_env(target)
api = target['pb.payroll.templates']
baseline = {s.employee_id.id: json.loads(s.formula_input_values)['LUONGHOPVND'] for s in previous.slip_ids}


def stamp(records, field):
    return hashlib.sha256(json.dumps([(r.id, r[field]) for r in records.sorted('id')],
                                    sort_keys=True, default=str).encode()).hexdigest()


rows = target['pb.payroll.month.inputs'].search([('config_id', '=', cfg.id), ('period', '=', '2026-10')])
month_stamp = stamp(rows, 'payload')
history_stamp = stamp(previous.slip_ids, 'formula_computed_values')
old_ids = run.slip_ids.ids
before = {'gross': run.pb_total_gross, 'deductions': run.pb_total_deductions, 'net': run.pb_total_net}
before_time = {s.id: {k: json.loads(s.formula_input_values).get(k)
    for k in ('NGAYCONGCHUA', 'SONGAYLAMVIE', 'GIOLAMVIEC')} for s in run.slip_ids}
run.slip_ids.action_recompute_formula_lines()
checks = 0
round_vnd = lambda v: math.floor(v + 0.5) if v >= 0 else -math.floor(-v + 0.5)
tax_codes = ('BHXH8BHXHSI8', 'BHYT15BHYT15', 'BHTN1BHTNUI1', 'THUETNCNPIT')
sums = {k: 0 for k in tax_codes}
for slip in run.slip_ids:
    inputs = json.loads(slip.formula_input_values)
    values = json.loads(slip.formula_computed_values)
    assert not slip.has_formula_errors, slip.id
    assert inputs['LUONGHOPVND'] == baseline[slip.employee_id.id]
    assert {k: inputs.get(k) for k in before_time[slip.id]} == before_time[slip.id]
    expected_salary = round_vnd(inputs['LUONGHOPVND'] / inputs['NGAYCONGCHUA'] * inputs['SONGAYLAMVIE'])
    assert values['LUONTHANACTU'] == expected_salary
    checks += 1
    # These are the existing workbook formulas, not a statutory-policy change.
    insured = inputs['THAMBHXHSHUI'] == 'Yes'
    insurance_salary = values['LUONGBAOHIEM']
    for code, rate in [('BHXH8BHXHSI8', .08), ('BHYT15BHYT15', .015)]:
        expected = round_vnd(min(insurance_salary, values['CONSTCAPBHXH']) * rate) if insured else 0
        assert values[code] == expected, (slip.id, code)
        checks += 1
    expected_ui = round_vnd(min(insurance_salary, values['CONSTCAPBHTN']) * .01) if insured and inputs['QUOCTICHNATI'] != 'Expat' else 0
    assert values['BHTN1BHTNUI1'] == expected_ui
    checks += 1
    assessable = values['THUNHAPTINH']
    if inputs['LOAITYPE'] == 'Permanent':
        if assessable <= 10000000:
            tax = assessable * .05
        elif assessable <= 30000000:
            tax = assessable * .10 - 500000
        elif assessable <= 60000000:
            tax = assessable * .20 - 3500000
        elif assessable <= 100000000:
            tax = assessable * .30 - 9500000
        else:
            tax = assessable * .35 - 14500000
        tax = round_vnd(tax)
    else:
        tax = 0 if assessable < 2000000 else round_vnd(assessable * .10)
    assert values['THUETNCNPIT'] == tax, (slip.id, 'PIT')
    checks += 1
    for code in sums:
        sums[code] += values[code]
    assert json.loads(slip.formula_input_sources)['LUONGHOPVND']['src'] == 'contract_field'
run._compute_pb_totals()
after = {'gross': run.pb_total_gross, 'deductions': run.pb_total_deductions, 'net': run.pb_total_net}
assert math.isclose(after['gross'] - after['deductions'], after['net'], abs_tol=.01)
assert after['gross'] > before['gross'] and after['deductions'] > before['deductions']
assert set(run.slip_ids.ids) == set(old_ids)
assert month_stamp == stamp(rows, 'payload')
assert history_stamp == stamp(previous.slip_ids, 'formula_computed_values')
assert run.state == 'draft' and all(s.state == 'draft' for s in run.slip_ids)
report = {'database': 'rize', 'run_id': run.id, 'state': run.state, 'employees': len(run.slip_ids),
          'before': before, 'after': after, 'deduction_components': sums,
          'independent_formula_checks': checks, 'october_time_and_adjustments_unchanged': True,
          'august_payroll_unchanged': True, 'same_payslip_ids': True}
if os.environ.get('VN_RECOMPUTE_APPLY') == '1':
    env.cr.commit()
    report['committed'] = True
else:
    env.cr.rollback()
    report['committed'] = False
print('VN_RECOMPUTE_RESULT', json.dumps(report, sort_keys=True))
