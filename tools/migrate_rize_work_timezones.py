"""Run in the Rize Odoo shell after backup; default is rollback rehearsal.

PB_TZ_APPLY=1 commits. Uses existing scheme membership, never nationality.
Indonesia defaults to Asia/Jakarta, per owner instruction; location overrides win.
"""
import json
import os
from collections import Counter

assert env.cr.dbname == 'rize', 'Rize-only data correction; generic defaults ship in the module.'
codes = ['RIZE_VN_FOCUSED_2026', 'RIZE_IN_FOCUSED_2026',
         'RIZE_SG_FOCUSED_2026', 'RIZE_ID_FOCUSED_2026']
configs = env['hr.formula.config'].search([('code', 'in', codes)])
assert len(configs) == 4, 'Expected four focused payroll configurations.'
assert len(configs.company_id) == 1
company = configs.company_id
env = env(context=dict(env.context, allowed_company_ids=company.ids,
                       tracking_disable=True, mail_notrack=True))
all_people = env['hr.employee'].search([('company_id', '=', company.id)])
memberships = {}
for config in configs:
    ids, _ = env['pb.payrun.wizard']._scheme_population(config.id, all_people.ids)
    assert ids, 'Empty scheme population: %s' % config.code
    for eid in ids:
        assert eid not in memberships or memberships[eid] == config.country_code
        memberships[eid] = config.country_code
people = env['hr.employee'].browse(sorted(memberships))
contracts = env['hr.contract'].search([('employee_id', 'in', people.ids)])
contract_facts = contracts.read(['employee_id', 'state', 'date_start', 'date_end', 'wage'])
leaves = env['hr.leave'].search([('employee_id', 'in', people.ids)])
leave_facts = leaves.read(['state', 'date_from', 'date_to', 'number_of_days'])
original = company.resource_calendar_id
original_facts = original.read(['name', 'tz', 'attendance_ids', 'global_leave_ids'])
report = {'employees_updated': Counter(), 'contracts_updated': 0,
          'country_filled': 0, 'pending_location': [], 'custom_calendar_preserved': []}
for employee in people:
    country = memberships[employee.id]
    assert not employee.payroll_country or employee.payroll_country == country
    if not employee.payroll_country:
        employee.payroll_country = country
        report['country_filled'] += 1
    tz = employee._pb_default_work_timezone()
    if not tz:
        report['pending_location'].append(employee.id)
        continue
    current = employee.resource_calendar_id
    if current != original and current.pb_timezone_origin_id != original:
        report['custom_calendar_preserved'].append(employee.id)
        continue
    target = original._pb_in_work_timezone(tz, company)
    changed = employee.tz != tz or current != target
    for contract in contracts.filtered(lambda c: c.employee_id == employee):
        if contract.resource_calendar_id == original:
            contract.resource_calendar_id = target
            report['contracts_updated'] += 1
    employee.write({'resource_calendar_id': target.id, 'tz': tz})
    if changed:
        report['employees_updated'][country] += 1
env.flush_all()
assert contract_facts == contracts.read(['employee_id', 'state', 'date_start', 'date_end', 'wage'])
assert leave_facts == leaves.read(['state', 'date_from', 'date_to', 'number_of_days']), 'Leave records changed; review before committing.'
assert original_facts == original.read(['name', 'tz', 'attendance_ids', 'global_leave_ids'])
report['calendars'] = env['resource.calendar'].search([
    ('pb_timezone_origin_id', '=', original.id)]).read(['name', 'tz', 'hours_per_day', 'hours_per_week'])
report['phong'] = env['hr.employee'].search([('barcode', '=', 'RIZ055')]).read(['tz', 'resource_calendar_id', 'payroll_country'])
report['apply'] = os.environ.get('PB_TZ_APPLY') == '1'
print('TIMEZONE_MIGRATION ' + json.dumps(report, default=str))
if report['apply']:
    env.cr.commit()
else:
    env.cr.rollback()
