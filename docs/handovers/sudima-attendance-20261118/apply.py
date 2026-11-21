"""Run in Odoo shell with SUDIMA_RULES_APPLY=1 to save; default is rollback.
Uses the same model/fields as Workforce / Shift Templates. Add-only, tenant scoped.
UI undo: archive the template (it starts archived); no employee is assigned.
"""
import json
import os
from pathlib import Path

assert env.cr.dbname == 'sudima', 'This configuration is Sudima-only'
company = env['res.company'].search([('name', '=', 'Sudima Panels Vietnam')])
assert len(company) == 1
actor = env['res.users'].search([('login', '=', 'ash@biztinct.com')])
assert len(actor) == 1 and company in actor.company_ids
Model = env['hr.shift.template'].with_user(actor).with_company(company).with_context(active_test=False)
vals = {
    'code': 'SD-DAY-0730-1630',
    'name': 'Sudima day 07:30-16:30 - pending assignment',
    'start_hour': 7.5, 'end_hour': 16.5, 'break_duration': 1.0,
    'shift_type': 'morning', 'is_overnight': False, 'active': False,
    'company_id': company.id,
    'note': (
        'PREPARED ONLY - archived and not assigned to employees.\n'
        'Source: Attendance_Machine_Questions_EN_VI (SUDIMA), Q34: 07:30-16:30. '
        'Q4 lists lunch 11:30-12:30 or 11:45-12:45; Q36 says unpaid. '
        'This template records the common one-hour lunch duration only.\n'
        'Confirm employee/date assignments, applicable working days and whether '
        'break taps or a fixed deduction should be used before activation. '
        'Do not deduct a recorded break twice. Q41 says no time rounding.\n'
        'Extended day and night shifts require their own confirmed unpaid breaks '
        'and normal/OT boundaries. Round 2 answer fields in the supplied file are blank.\n'
        'This template alone does not calculate payable time from punches. '
        'The shared shift-based calculation feature is pending owner approval. '
        'Attendance requires General Manager approval (Q44); account not confirmed. '
        'No extra overtime-linked bonus is implemented.'
    ),
}
protected_models = ['hr.attendance', 'hr.shift.planning', 'pb.timesheet.packet', 'hr.overtime.request']
before = {m: env[m].search_count([]) for m in protected_models}
connectors = env['pb.clock.connector'].search([])
publish_before = {c.id: c.publish_punches for c in connectors}
existing = Model.search([('company_id', '=', company.id), ('code', '=', vals['code'])])
assert len(existing) <= 1
if existing:
    for k, value in vals.items():
        actual = existing[k].id if k == 'company_id' else existing[k]
        assert actual == value, 'Existing template changed; preserve it: %s' % k
    rec = existing
else:
    rec = Model.create(vals)
assert rec.duration == 8.0 and not rec.active and not rec.resource_calendar_id
assert not env['hr.shift.planning'].search_count([('shift_template_id', '=', rec.id)])
assert before == {m: env[m].search_count([]) for m in protected_models}
assert publish_before == {c.id: c.publish_punches for c in connectors}
receipt = {'database': env.cr.dbname, 'template_id': rec.id, 'created': not bool(existing),
           'active': rec.active, 'duration': rec.duration, 'protected_counts': before,
           'publish_punches': publish_before,
           'applied': os.environ.get('SUDIMA_RULES_APPLY') == '1'}
if receipt['applied']:
    env.cr.commit()
else:
    env.cr.rollback()
print('SUDIMA_SHIFT_RECEIPT ' + json.dumps(receipt))
