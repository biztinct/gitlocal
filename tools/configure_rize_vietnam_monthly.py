"""Simplify the Rize Vietnam allowance and monthly layout, rollback by default.

Run in the rize Odoo shell with VN_MONTHLY_PLAN pointing at the metadata-only
definition. VN_MONTHLY_APPLY=1 commits after calculation and storage checks.
This step does not activate payroll, assign employees, import data or run pay.
"""
import hashlib
import json
import os
from pathlib import Path

assert env.cr.dbname == 'rize'
plan = json.loads(Path(os.environ['VN_MONTHLY_PLAN']).read_text())
cfg = env['hr.formula.config'].browse(plan['config_id']).exists()
assert cfg.code == plan['code'] and cfg.company_id.name == 'Rize Farms'
e = env(context=dict(env.context, allowed_company_ids=cfg.company_id.ids))
cfg = cfg.with_env(e)
api = e['pb.payroll.templates']
api._lock(cfg)


def business_hashes():
    result = {}
    for table in ('hr_employee', 'hr_contract', 'hr_contract_advantage',
                  'vietnam_employee_dependent', 'res_partner_bank',
                  'hr_payslip', 'hr_payslip_run', 'pb_payroll_month_inputs'):
        e.cr.execute('SELECT row_to_json(t)::text FROM ' + table + ' t ORDER BY id')
        result[table] = hashlib.sha256('\n'.join(row[0] for row in e.cr.fetchall()).encode()).hexdigest()
    return result


baseline = business_hashes()
by = {r.code: r for r in cfg.rule_ids}
old_codes = set(plan['remove_codes'])
assert old_codes <= by.keys(), 'Already migrated or concurrently changed; inspect first.'
assert by['VNTECH'].column_type == 'formula'
assert not e['hr.payslip'].search_count([('formula_config_id', '=', cfg.id)])
assert not e['pb.payroll.month.inputs'].search_count([('config_id', '=', cfg.id)])
before = {r.code: (r.column_letter, r.excel_formula, r.column_type,
                    r.is_contract_component, r.is_text_component)
          for r in cfg.rule_ids if r.code not in old_codes | {'VNTECH'}}
state = cfg.state
layout_row = e['pb.payroll.template.layout'].search([
    ('config_id', '=', cfg.id), ('company_id', '=', cfg.company_id.id)])
old_layout = dict(layout_row.payload)
assert len(old_layout.get('preview_employee_ids', [])) == 70

# Keep the old allowance's stable code/column and its downstream references.
# It is now a monthly earning; no employee/contract write destination is added.
by['VNTECH'].with_context(formula_version_note='Owner requested one manually entered monthly technical advisory allowance.').write({
    'name': plan['advisory_name'], 'column_type': 'input', 'excel_formula': False,
    'python_formula': False, 'value_kind': 'money', 'column_role': 'payroll',
    'net_role': 'earning', 'net_role_detail': True, 'net_role_source': 'user',
    'net_role_confidence': 'certain', 'component_type': 'Earnings',
    'is_contract_component': False, 'is_text_component': False,
    'default_value': 0, 'source_sheet_name': 'Monthly adjustments',
    'original_column_letter': False,
})
by['VNTECH'].set_source_binding('excel', plan['advisory_source'], origin='user')
for sample in cfg.sample_data_ids:
    assert not sample.input_line_ids
    values = json.loads(sample.input_values_json or '{}')
    values['VNTECH'] = sum(values.pop(code, 0) or 0 for code in plan['remove_codes'])
    expected_inputs = json.loads(sample.expected_inputs_json or '{}')
    if expected_inputs:
        expected_inputs['VNTECH'] = sum(expected_inputs.pop(code, 0) or 0 for code in plan['remove_codes'])
    sample.write({'input_values_json': json.dumps(values),
                  'expected_inputs_json': json.dumps(expected_inputs)})
old_letters = {by[code].column_letter for code in old_codes}
columns = {r.column_letter: r for r in cfg.rule_ids}
for rule in cfg.rule_ids.filtered(lambda r: r.column_type == 'formula'):
    refs = e['pb.formula.studio']._expand_refs(rule.excel_formula, columns)
    assert not set(refs) & old_letters, (rule.code, refs)
by['VNTECH1'].union(by['VNTECH2'], by['VNTECH3'], by['VNTECH4']).unlink()
cfg.invalidate_recordset(['rule_ids'])
catalog = api._catalog(cfg)
code_ids = {c['code']: c['id'] for c in catalog if c['code']}
layout = dict(time=[code_ids[c] for c in plan['time_order']],
              adjustments=[code_ids[c] for c in plan['adjustment_order']],
              records=old_layout['records'], available=old_layout['available'])
assert api.save_layout(cfg.id, layout)['ok']
by = {r.code: r for r in cfg.rule_ids}
assert len(by) == 181 and not old_codes & by.keys()
assert before == {r.code: (r.column_letter, r.excel_formula, r.column_type,
                           r.is_contract_component, r.is_text_component)
                  for r in cfg.rule_ids if r.code != 'VNTECH'}
assert by['VNTECH'].column_type == 'input' and not by['VNTECH'].excel_formula
assert cfg.state == state
assert len(api._roster(cfg, '2026-10')) == 70
assert layout_row.payload['preview_employee_ids'] == old_layout['preview_employee_ids']
health = cfg.value_kind_board()
assert health['review_count'] == health['role_conflict_count'] == health['drift_count'] == 0, health
tests = cfg.run_sample_tests()
assert tests['total'] == tests['passed'] == 96, tests
assert len(api._layout(cfg, api._catalog(cfg))['time']) == 5
assert len(api._layout(cfg, api._catalog(cfg))['adjustments']) == 23
assert business_hashes() == baseline, 'This definition step must not change business records.'
report = dict(database='rize', config_id=cfg.id, rules=len(by),
              inputs=sum(r.column_type == 'input' for r in cfg.rule_ids),
              formulas=sum(r.column_type == 'formula' for r in cfg.rule_ids),
              scenarios=tests, advisory_name=by['VNTECH'].name,
              time_fields=5, adjustment_fields=23,
              committed=os.getenv('VN_MONTHLY_APPLY') == '1')
if report['committed']:
    env.cr.commit()
else:
    env.cr.rollback()
print('VN_MONTHLY_RESULT ' + json.dumps(report, ensure_ascii=False))
