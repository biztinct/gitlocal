{
    'name': 'Attendance Calculation Policies',
    'summary': 'Reviewed shift schedules, fixed breaks and configurable lateness deductions',
    'version': '19.0.1.2.0',
    'license': 'LGPL-3',
    'depends': ['pb_clock', 'pb_schedule', 'pb_timesheet_approval', 'pb_hr_payroll_formula', 'pb_attendance_flow', 'pb_settings', 'pb_shift_patterns'],
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'views/policy.xml', 'data/cron.xml'],
    'assets': {'web.assets_backend': ['pb_attendance_policy/static/src/js/settings.js']},
    'installable': True,
    'auto_install': False,
}
