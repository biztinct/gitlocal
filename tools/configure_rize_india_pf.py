"""Owner-authorised uniform Rize India PF, run with Odoo shell.

RIZE_PF_DIR contains live.json from the read-only preflight and a permanent
database backup. Default: rollback rehearsal. RIZE_PF_APPLY=1 commits after
checks. RIZE_PF_VERIFY=1 checks the saved configuration without modifying it.
Only the active Rize India scheme changes; existing payroll is never recomputed.
"""
import json
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

assert env.cr.dbname == 'rize'
root = Path(os.environ['RIZE_PF_DIR'])
apply = os.getenv('RIZE_PF_APPLY') == '1'
verify = os.getenv('RIZE_PF_VERIFY') == '1'
assert not (apply and verify)
e = env(user=2, context=dict(env.context, allowed_company_ids=[1]))
cfg = e['hr.formula.config'].search([('code', '=', 'RIZE_IN_FOCUSED_2026')])
assert len(cfg) == 1 and cfg.state == 'active' and cfg.country_code == 'IN'
api, studio = e['pb.payroll.templates'], e['pb.formula.studio']
api._lock(cfg)
by = {r.code: r for r in cfg.rule_ids}

# Existing whole-rupee rounding is retained. Monthly basic is the annual
# contract basic divided by 12, exactly the salary basis used in the response.
changes = {
    'INPFEE': dict(column_type='formula', excel_formula='=ROUND(MIN(P2/12,EC2)*EA2,0)',
                   is_required=False, is_editable=False),
    'INPFANN': dict(excel_formula='=ROUND(MIN(P2/12,EC2)*EA2,0)*12'),
    'INPFER': dict(excel_formula='=ROUND(S2/12,0)'),
    'INCONVANN': dict(excel_formula='=L2-P2-Q2-S2'),
    'INPFRATE': dict(name='PF contribution rate', constant_value=0.12),
    'INPFCAP': dict(name='Monthly PF contribution cap', constant_value=3000.0),
    'INPFBASE': dict(name='Monthly PF basic salary ceiling', constant_value=25000.0),
    'INPFMODE': dict(name='Previous PF basis (not used)', is_required=False),
    'INREADY': dict(excel_formula='=IF(OR(O2<=0,N2<L2,ABS(T2-L2)>1,I2<=0,J2<0,J2>I2,AH2<0),"Review salary or days",IF(AND(K2<>0,AJ2=0),"Review arrears payment","Ready"))'),
}
description = ('<p>Rize India payroll. Employee and employer PF each equal 12% '
               'of monthly contract basic salary, with basic capped at INR 25,000 '
               '(maximum INR 3,000 per month). Whole-rupee rounding is retained. '
               'This shared rule applies to every employee on this scheme, '
               'without an effective-date restriction, as instructed by the owner '
               'on 17 November 2026.</p><p>Monthly basic is annual contract basic '
               'divided by 12. Annual CTC includes employer PF; the annual '
               'conveyance balance reconciles CTC after employer PF. Previous '
               'PF-basis selections and imported employee-PF amounts do not '
               'override the formula. TDS and profession tax remain monthly '
               'inputs. Annual variable remains a target, not automatic payment. '
               'Existing payslips are not recalculated by this configuration change.</p>')


def digest(table, where='TRUE'):
    e.cr.execute('SELECT md5(coalesce(string_agg(md5(row_to_json(t)::text),chr(10) '
                 'ORDER BY id),\'\')) FROM ' + table + ' t WHERE ' + where)
    return e.cr.fetchone()[0]


def rounded(value):
    return float(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def calculate(inputs):
    sample = e['hr.formula.sample.data'].new({'config_id': cfg.id})
    errors = {}
    result = sample._evaluate_rules_with_dependencies(inputs, readonly=True, errors=errors)
    assert not errors, errors
    return result


protected = ['hr_employee', 'hr_contract', 'hr_contract_advantage', 'hr_payslip',
             'hr_payslip_line', 'hr_payslip_run', 'hr_payroll_import_line',
             'pb_payroll_month_inputs', 'vietnam_employee_dependent',
             'hr_formula_sample_data', 'hr_formula_scheme_assignment']
before = {t: digest(t) for t in protected}
other_rules = digest('hr_formula_rule', 'config_id != %s' % cfg.id)
other_configs = digest('hr_formula_config', 'id != %s' % cfg.id)
rosters = {p: api._roster(cfg, p).ids for p in ['2026-08', '2026-11', '2026-12']}
baseline = [(s.get_input_values(), calculate(s.get_input_values()))
            for s in cfg.sample_data_ids]

if not verify:
    assert not (root / 'applied.json').exists(), 'Already applied; use verify mode.'
    expected = json.loads((root / 'live.json').read_text())
    assert cfg.id == expected['id']
    assert json.loads(json.dumps(cfg.rule_ids.read(list(expected['rules'][0])), default=str)) == expected['rules'], 'Scheme changed since preflight.'
    assert cfg._scheme_route()[0] in ('open', 'fast'), 'Use the published approval route.'
    if apply:
        assert (root / 'rize-before.dump').stat().st_size > 1000000
    by['INPFEE'].write({'application_source_key': False, 'application_source_required': False})
    by['INPFEE'].clear_source_binding()
    for code, vals in changes.items():
        result = studio.save_component(by[code].id, vals)
        assert result.get('ok'), (code, result)
        assert by[code].column_type != 'formula' or result.get('is_valid'), (code, result)
    by['INPFEE'].write({'application_source_key': False, 'application_source_required': False})
    cfg.description = description
    # The old contract values remain as historical data, out of the normal
    # monthly worksheet. They no longer select a different PF calculation.
    catalog = api._catalog(cfg)
    layout = api._layout(cfg, catalog)
    old_basis = 'rule:%s' % by['INPFMODE'].id
    for lane in layout:
        layout[lane] = [fid for fid in layout[lane] if fid != old_basis]
    layout['available'].append(old_basis)
    assert api.save_layout(cfg.id, layout).get('ok')

for code, vals in changes.items():
    for key, value in vals.items():
        assert by[code][key] == value, (code, key)
assert not by['INPFEE'].application_source_key
assert str(cfg.description) == description
assert not any('AV2' in (r.excel_formula or '') for r in cfg.rule_ids)
catalog = api._catalog(cfg)
assert not any(c.get('code') == 'INPFEE' for c in catalog)
layout = api._layout(cfg, catalog)
assert 'rule:%s' % by['INPFMODE'].id in layout['available']

checks = []
for monthly_basic in [0, 10000, 15000, 20375, 24999, 25000, 25001, 100000]:
    for old_mode in ['', 'Capped', 'Full basic']:
        inputs = dict(INANNFIX=monthly_basic * 24, INWDAYS=30, INPDAYS=30,
                      INPFMODE=old_mode, INPFEE=99999)
        result = calculate(inputs)
        expected = rounded(min(monthly_basic, 25000) * .12)
        assert result['INPFEE'] == result['INPFER'] == expected
        assert result['INPFANN'] == expected * 12
        assert abs(result['INCTCTOTAL'] - inputs['INANNFIX']) < .001
        if monthly_basic:
            assert result['INREADY'] == 'Ready'
        checks.append({'monthly_basic': monthly_basic, 'prior_basis': old_mode, 'pf': expected})

# Existing samples include lower salaries, full-basic exceptions, arrears and
# rounding adjustments. Only PF and its dependent totals may change.
allowed_deltas = {'INPFEE', 'INPFANN', 'INPFER', 'INCONVANN', 'INCTCTOTAL',
                  'INDEDTOTAL', 'INNET', 'INPFCAP', 'INPFBASE', 'INREADY'}
for inputs, previous in baseline:
    result = calculate(inputs)
    expected = rounded(min(result['INBASICANN'] / 12, 25000) * .12)
    assert result['INPFEE'] == result['INPFER'] == expected
    assert abs(result['INCTCTOTAL'] - result['INANNFIX']) < .001
    assert abs(result['INNET'] - (result['INGROSS'] - result['INDEDTOTAL'])) < .001
    assert all(result.get(k) == v for k, v in previous.items() if k not in allowed_deltas)

people = api._roster(cfg, '2026-11')
cards = api._cards(cfg)
records = api._record_values(cfg, people, cards, '2026-11')
tested_people = []
client_expected = {'RZFT300': 2445, 'RZFT301': 3000, 'RZFT302': 3000}
for person in people:
    annual = records[person.id]['c:INANNFIX']
    assert annual and float(annual) > 0, (person.id, 'Missing annual basic source')
    result = calculate(dict(INANNFIX=float(annual), INWDAYS=30, INPDAYS=30,
                            INPFMODE='', INPFEE=99999))
    expected = rounded(min(rounded(float(annual) * .5) / 12, 25000) * .12)
    assert result['INPFEE'] == result['INPFER'] == expected
    assert result['INREADY'] == 'Ready'
    if person.employee_id in client_expected:
        assert expected == client_expected[person.employee_id], person.employee_id
    tested_people.append({'employee_id': person.id, 'code': person.employee_id, 'pf_each': expected})
assert set(client_expected) <= {p['code'] for p in tested_people}

release = studio.release_approve(cfg.id, narrative='Owner authorised uniform India PF for all scheme employees, both employee and employer: 12% of monthly contract basic capped at INR 25,000; maximum INR 3,000 each. No effective-date restriction; not yet production payroll. Manual PF input and old basis no longer control calculation. CTC reconciliation and all roster/sample checks passed.') if not verify else {}
assert verify or release.get('ok'), release
e.flush_all()
assert {t: digest(t) for t in protected} == before, 'Payroll, employee or historical data changed.'
assert digest('hr_formula_rule', 'config_id != %s' % cfg.id) == other_rules
assert digest('hr_formula_config', 'id != %s' % cfg.id) == other_configs
assert {p: api._roster(cfg, p).ids for p in rosters} == rosters
receipt = dict(database='rize', config_id=cfg.id, applied=apply, verified=verify,
               rule_changes=changes, boundary_checks=len(checks), sample_checks=len(baseline),
               roster_checks=len(tested_people), people=tested_people, release=release,
               protected_tables=before, unrelated_schemes_unchanged=True, rosters_unchanged=True)
name = 'verification.json' if verify else 'applied.json' if apply else 'rehearsal.json'
if apply:
    e.cr.commit()
else:
    e.cr.rollback()
(root / name).write_text(json.dumps(receipt, indent=2, default=str))
(root / name).chmod(0o600)
print('INDIA_PF_RESULT', json.dumps({k:v for k,v in receipt.items() if k not in ('people', 'protected_tables','rule_changes')}))
