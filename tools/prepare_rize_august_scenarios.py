"""Idempotent, Rize-only setup for the owner's August 2026 scenario validation.

Run with Odoo shell; RIZE_AUGUST_APPLY=1 commits, otherwise rolls back.
No payroll values, contract dates, approvals or payment state are changed.
"""
import ast
import json
import os

assert env.cr.dbname == 'rize', 'This historical coverage correction is Rize-only'
e = env(user=2, context=dict(env.context, allowed_company_ids=[1]))
codes = ['RIZE_%s_FOCUSED_2026' % country for country in ('VN', 'IN', 'SG', 'ID')]
configs = e['hr.formula.config'].search([('code', 'in', codes), ('company_id', '=', 1)])
assert len(configs) == 4
report = {'configuration': [], 'coverage': {}}
for config in configs:
    old = str(config.application_effective_from or '')
    assert old and config.application_data_enabled
    if old > '2026-08-01':
        config.write({'application_effective_from': '2026-08-01'})
    report['configuration'].append({'code': config.code, 'before': old,
                                    'after': str(config.application_effective_from)})

# Seven August employees have valid historical contracts but were omitted from
# the October roster. Keep every existing roster entry; add only these seven.
extra = {'RIZ002', 'RIZ023', 'RIZ056', 'RIZ080', 'RIZ084', 'RIZ220', 'RIZ226'}
vn = configs.filtered(lambda c: c.code == 'RIZE_VN_FOCUSED_2026')
assignment = e['hr.formula.scheme.assignment'].search([
    ('config_id', '=', vn.id), ('active', '=', True), ('cycle_type', '=', 'regular'),
    ('date_from', '=', False), ('date_to', '=', False)])
assert len(assignment) == 1 and not assignment.department_id and not assignment.division_id
domain = ast.literal_eval(assignment.domain)
clause = next(c for c in domain if isinstance(c, (tuple, list)) and c[:2] == ('barcode', 'in'))
old_roster = set(clause[2])
people = e['hr.employee'].search([('company_id', '=', 1), ('barcode', 'in', sorted(extra))])
assert len(people) == len(extra)
contracts = e['hr.contract'].search([
    ('employee_id', 'in', people.ids), ('state', 'in', ['open', 'close']),
    ('date_start', '<=', '2026-08-31'), '|', ('date_end', '=', False), ('date_end', '>=', '2026-08-01')])
assert set(contracts.employee_id.ids) == set(people.ids)
# Undo only this task's earlier undated expansion, identified by its exact note.
marker = ' August 2026 validation: also cover seven historical August employees with valid contracts; preserve the existing roster.'
if marker in (assignment.note or ''):
    assert extra.issubset(old_roster)
    restored = old_roster - extra
    assignment.write({'domain': repr([('barcode', 'in', sorted(restored)) if c == clause else c for c in domain]),
                      'note': assignment.note.replace(marker, '')})
    old_roster = restored
historical = e['hr.formula.scheme.assignment'].search([
    ('config_id', '=', vn.id), ('date_from', '=', '2026-08-01'), ('date_to', '=', '2026-08-31'),
    ('note', '=', 'August 2026 client payroll historical coverage; existing standing roster unchanged.')])
values = {'config_id': vn.id, 'domain': repr([('company_id', '=', 1), ('barcode', 'in', sorted(extra))]),
          'cycle_type': 'regular', 'sequence': 9, 'active': True,
          'date_from': '2026-08-01', 'date_to': '2026-08-31',
          'note': 'August 2026 client payroll historical coverage; existing standing roster unchanged.'}
if historical:
    assert len(historical) == 1
    historical.write(values)
else:
    historical = e['hr.formula.scheme.assignment'].create(values)
report['coverage'] = {'standing_roster': len(old_roster), 'august_only_additions': len(extra),
                      'historical_mapping': historical.id}
# Check both boundaries: historical coverage must not expand another month.
for day in ('2026-07-31', '2026-09-01'):
    resolved = e['pb.scheme.map'].resolve_many(people.ids, 'regular', day)
    assert all(resolved[p.id]['config_id'] != vn.id for p in people)
# The ten expired-contract employees are intentionally excluded by owner decision.
eligible = e['pb.payrun.wizard']._eligible_employees(formula_config_id=vn.id,
    date_start='2026-08-01', date_end='2026-08-31')
assert len(eligible) == 60, 'Review any concurrent workforce changes before applying'
report['vietnam_august_employees'] = len(eligible)
if os.environ.get('RIZE_AUGUST_APPLY') == '1':
    env.cr.commit()
    report['committed'] = True
else:
    env.cr.rollback()
    report['committed'] = False
print(json.dumps(report, sort_keys=True))
