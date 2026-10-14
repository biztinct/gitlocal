"""Configure and verify an imported Singapore review through application APIs.

Run in the Odoo shell with SG_SETUP_DIR pointing to the three generated files.
SG_SETUP_DATABASE defaults to payobook; SG_SETUP_CONFIG_ID selects the imported
draft. This does not create employees or payslips or activate the configuration.
"""
import base64
import json
import math
import os
from pathlib import Path

import openpyxl

assert env.cr.dbname == os.environ.get('SG_SETUP_DATABASE', 'payobook')
root = Path(os.environ['SG_SETUP_DIR'])
config = env['hr.formula.config'].browse(int(os.environ['SG_SETUP_CONFIG_ID'])).exists()
assert len(config) == 1 and config.state in ('draft', 'testing')
assert config.country_code == 'SG' and config.currency_id.name == 'SGD'
assert len(config.rule_ids) == 41, len(config.rule_ids)
by_col = {r.column_letter: r for r in config.rule_ids if not r.tax_table_id}
assert len(by_col) == 38
for col, code in {'AL': 'PIT', 'AA': 'NET', 'AJ': 'GROSS', 'AI': 'EEDED', 'AK': 'ERCOST'}.items():
    if by_col[col].code != code:
        result = env['pb.formula.studio'].rename_component(by_col[col].id, code)
        assert result.get('ok'), result

text_cols = {'B', 'C', 'D', 'G', 'J', 'AB', 'AD', 'AF', 'AG'}
date_cols = {'E', 'F', 'R', 'S'}
identifier_cols = {'A', 'AC', 'AE'}
day_cols = {'T', 'U', 'V', 'W'}
profile_cols = {'A', 'B', 'C', 'D', 'E', 'F', 'G', 'J', 'AF', 'AG'}
setup = {}
for rule in config.rule_ids:
    col = rule.column_letter
    group, role, detail, kind = 'Calculation steps', 'info', False, 'money'
    if rule.tax_table_id:
        group = 'SDL parameters'
        kind = 'rate' if rule.tax_parameter_code == 'SDLRATE' else 'money'
    else:
        if col in profile_cols:
            group = 'Employee details'
        elif col in {'AB', 'AC', 'AD', 'AE'}:
            group = 'Bank details'
        elif col in {'H', 'R', 'S', 'T', 'U', 'V'}:
            group = 'Payroll inputs'
        elif col in {'I', 'K'}:
            group = 'Full-month contribution inputs'
        elif col in {'AH', 'Y', 'Z'}:
            group, role, detail = 'Earnings', 'earning', True
        elif col == 'AJ':
            group, role = 'Totals', 'earning'
        elif col in {'AI', 'AL'}:
            group, role = 'Deductions', 'deduction'
        elif col in {'L', 'M'}:
            group, role, detail = 'Employer contributions', 'employer_cost', True
        elif col == 'AK':
            group, role = 'Totals', 'employer_cost'
        elif col == 'AA':
            group, role = 'Totals', 'net'
        elif col in {'O', 'P', 'Q'}:
            group = 'Contract CTC reference'
        if col in text_cols:
            kind = 'text'
        elif col in identifier_cols:
            kind = 'identifier'
        elif col in date_cols:
            kind = 'date'
        elif col in day_cols:
            kind = 'quantity'
    setup[rule.code] = {'group': group, 'pay_role': role, 'rollup': detail, 'kind': kind, 'signal': False}
config.set_component_setup(setup)
config.rule_ids.write({'net_role_source': 'user', 'net_role_confidence': 'certain',
    'net_role_reason': 'Reviewed for the Rize Singapore client monthly-input workflow.',
    'value_kind_source': 'user',
    'value_kind_reason': 'Reviewed against the Singapore input field definitions.'})
for rule in config.rule_ids:
    show = not rule.tax_table_id and rule.column_letter in {'AH', 'Y', 'Z', 'AJ', 'AI', 'AA', 'L', 'M', 'AK'}
    rule.appears_on_payslip = show
    rule.number_format = {'money': 'currency', 'rate': 'percentage'}.get(rule.value_kind, 'number')
    if rule.column_type == 'input':
        rule.set_source_binding('excel', 'Payroll|%s' % rule.name)
for col, role in {'A': 'identity', 'C': 'identity', 'E': 'profile', 'F': 'contract',
                  'AB': 'bank', 'AC': 'bank', 'AD': 'bank', 'AE': 'bank'}.items():
    by_col[col].write({'column_role': role, 'column_role_source': 'user'})

formula_path = root / 'Rize_Singapore_Payroll_Configuration_Aug2026.xlsx'
monthly_path = root / 'Rize_Singapore_Monthly_Inputs.xlsx'
source = openpyxl.load_workbook(formula_path, data_only=False)['Payroll']
cached = openpyxl.load_workbook(formula_path, data_only=True)['Payroll']
inputs_cols = [c for c in range(1, 39) if source.cell(13, c).data_type != 'f']
formulas_cols = [c for c in range(1, 39) if source.cell(13, c).data_type == 'f']
assert len(inputs_cols) == 25 and len(formulas_cols) == 13
for c in formulas_cols:
    rule = by_col[source.cell(13, c).column_letter]
    desired = source.cell(13, c).value
    for constant in config.rule_ids.filtered('tax_table_id'):
        letter, row = openpyxl.utils.cell.coordinate_from_string(constant.tax_source_cell)
        desired = desired.replace('$%s$%s' % (letter, row), '%s2' % constant.column_letter)
    if rule.excel_formula != desired:
        saved = env['pb.formula.studio'].save_formula(rule.id, desired)
        assert saved.get('ok'), saved
blank = openpyxl.load_workbook(monthly_path, data_only=False)
assert blank.sheetnames == ['Payroll', 'Instructions']
assert [c.value for c in blank['Payroll'][1]] == [source.cell(12, c).value for c in inputs_cols]
assert not any(c.value is not None for row in blank['Payroll'].iter_rows(min_row=2) for c in row)
assert not any(c.data_type == 'f' for sheet in blank for row in sheet for c in row)

Batch = env['hr.payroll.import.batch']
probe = Batch.new({'formula_config_id': config.id, 'company_id': config.company_id.id,
    'file_header_row': 1, 'file_data_start_row': 2, 'file_sheet_name': 'Payroll'})
parsed = probe._parse_source_file((root / 'monthly-probe.xlsx').read_bytes(), 'monthly-probe.xlsx')
assert parsed['multisheet'] and len(parsed['rows']) == 8, parsed.keys()
Wizard = env['pb.payrun.wizard'].with_company(config.company_id)
preflight = Wizard.preflight_spreadsheet(config.id, base64.b64encode((root / 'monthly-probe.xlsx').read_bytes()).decode(), 'monthly-probe.xlsx')
assert preflight['ok'] and preflight['columns'] == 25 and preflight['fed'] == 25 and not preflight['missing'], preflight
def sample_input(rule, value):
    # People/bank fields travel beside calculation inputs in a real run.
    # Preserve them as the typed parser delivered them, rather than passing
    # reference codes through the older amount-only contract normalizer.
    if rule.value_kind in {'text', 'identifier', 'date'}:
        return probe._normalize_component_text(value)
    return probe._normalize_rule_input_value(rule, value) if value is not None else ''

formula_checks = 0
for i, raw in enumerate(parsed['rows']):
    inputs = probe._transform_data_to_formula_inputs(raw)
    for c in inputs_cols:
        rule = by_col[source.cell(13, c).column_letter]
        value = raw.get('Payroll|%s' % source.cell(12, c).value)
        inputs[rule.code] = sample_input(rule, value)
    if i == 0:
        assert inputs[by_col['A'].code] == '000001', inputs[by_col['A'].code]
        assert inputs[by_col['AC'].code] == '0000123456', inputs[by_col['AC'].code]
    expected = {by_col[source.cell(13, c).column_letter].code: cached.cell(13 + i, c).value
                for c in formulas_cols}
    name = 'Singapore template example %s' % (i + 1)
    vals = {'config_id': config.id, 'name': name, 'sequence': i + 1,
            'source_type': 'import', 'source_date': '2026-08-01',
            'description': cached.cell(13 + i, 33).value,
            'input_values_json': json.dumps(inputs), 'expected_inputs_json': json.dumps(inputs),
            'expected_values_json': json.dumps(expected)}
    sample = config.sample_data_ids.filtered(lambda s: s.name == name)
    if sample:
        sample.write(vals)
    else:
        sample = env['hr.formula.sample.data'].create(vals)
    errors = {}
    values = sample._evaluate_rules_with_dependencies(inputs, readonly=True, errors=errors)
    assert not errors, errors
    for code, value in expected.items():
        assert isinstance(values.get(code), (int, float)) and math.isclose(values[code], value, rel_tol=0, abs_tol=1e-7), (i, code, values.get(code), value)
        formula_checks += 1
    earned = sum(values.get(r.code, 0) for r in config.rule_ids if r.net_role == 'earning' and not r.net_role_detail)
    deducted = sum(values.get(r.code, 0) for r in config.rule_ids if r.net_role == 'deduction' and not r.net_role_detail)
    assert math.isclose(earned - deducted, values['NET'], abs_tol=1e-7)
    costs = sum(values.get(r.code, 0) for r in config.rule_ids if r.net_role == 'employer_cost' and not r.net_role_detail)
    assert math.isclose(costs, values['ERCOST'], abs_tol=1e-7)

# Reconcile the client controls through the same deployed engine without
# persisting confidential values in the delivered fictional samples.
source_controls = json.loads((root / 'source-controls.json').read_text())['controls']
for control in source_controls:
    inputs = {by_col[source.cell(13, c).column_letter].code:
              sample_input(by_col[source.cell(13, c).column_letter], cached.cell(13, c).value)
              for c in inputs_cols if cached.cell(13, c).value is not None}
    inputs.update({by_col[col].code: value for col, value in control['inputs'].items()})
    errors = {}
    values = sample._evaluate_rules_with_dependencies(inputs, readonly=True, errors=errors)
    assert not errors, errors
    for col, value in control['expected'].items():
        assert math.isclose(values[by_col[col].code], value, rel_tol=0, abs_tol=1e-7), (control['source_row'], col)

config.sample_data_ids.filtered(lambda s: s.name == 'Sample employee'
    and not json.loads(s.expected_values_json or '{}')).write({'active': False})
test_results = config.run_sample_tests()
assert test_results['passed'] >= 8 and not test_results['failed'], test_results
board = config.value_kind_board()
assert not board['review_count'] and not board['role_conflict_count'], board
statutory = config.rule_ids.filtered('tax_table_id')
assert len(statutory) == 3 and all(statutory.mapped('tax_aligned'))
blueprint = env['pb.blueprint.studio']
mapping = blueprint.bp_task_set(config.id, 'mapping', 'configured')
assert mapping.get('ok'), mapping
checks = blueprint.bp_run_checks(config.id)
assert checks.get('ok'), checks
finished = blueprint.bp_finish(config.id)
assert finished.get('ok'), finished
health = env['pb.formula.studio'].get_problems(config.id)
assert health['counts']['error'] == 0, health['problems']
attachment_ids = []
for path in [formula_path, monthly_path]:
    attachment = env['ir.attachment'].search([('res_model', '=', 'hr.formula.config'),
        ('res_id', '=', config.id), ('name', '=', path.name)], limit=1)
    vals = {'name': path.name, 'type': 'binary', 'res_model': 'hr.formula.config',
        'res_id': config.id, 'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'datas': base64.b64encode(path.read_bytes())}
    if attachment:
        attachment.write(vals)
    else:
        attachment = env['ir.attachment'].create(vals)
    attachment_ids.append(attachment.id)
env.cr.commit()
print(json.dumps({'database': env.cr.dbname, 'config_id': config.id, 'state': config.state,
    'components': len(config.rule_ids), 'inputs': len(inputs_cols), 'mapped_constants': len(statutory),
    'monthly_rows_tested': 8, 'formula_checks': formula_checks, 'tests': test_results,
    'client_controls': len(source_controls) * 8,
    'monthly_preflight': {'columns': preflight['columns'], 'fed': preflight['fed'], 'missing': len(preflight['missing'])},
    'health': health['counts'], 'treatment_review': board['review_count'],
    'type_conflicts': board['role_conflict_count'], 'attachments': attachment_ids}))
