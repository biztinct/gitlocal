# -*- coding: utf-8 -*-
{
    'name': 'Time into Pay',
    'summary': 'Overtime suggested from clock punches, confirmed late and '
               'early minutes as pay items, and time off instead of '
               'overtime pay',
    'description': """
WDGAP step 5, phase S5-B.

WHAT THIS MODULE ADDS

  * OVERTIME SUGGESTED FROM CLOCK PUNCHES. In the weekly Close, each person-day
    whose punches run past the published shift — or, where no shift was
    published, past the person's normal working hours — shows a suggestion.
    A manager accepts suggestions (one or many) and they become ordinary
    overtime requests on the existing route. Nothing is ever paid from a
    suggestion itself.
  * LATE AND EARLY MINUTES FROM REAL PUNCHES. Worked out live from the first
    punch-in and the last punch-out against the shift (or the working hours),
    after the company's grace minutes. Shown in the weekly Close with Confirm
    and Excuse. ONLY confirmed minutes become the pay items LATEMIN / EARLYMIN,
    and only for a scheme that declares them; a scheme without them computes
    exactly as before. Each confirmed row is held by one payslip (paid once).
  * PAY IT OR GIVE TIME OFF. A manager decides, per overtime request, whether
    it is paid or given as time off, hour for hour, into the company's
    "Time off in lieu" kind of leave. Hours given as time off are taken back
    out of the overtime the payslip would otherwise receive, in all three
    places overtime reaches pay. Time off in lieu never runs out.
  * Public-holiday overtime in the weekly grid reads the company's real public
    holidays (company closures) instead of a list that does not exist on this
    version.

WHAT IT NEVER DOES

  Payslips made from a pay data file are not changed: those runs never took
  overtime from requests, and they do not take late minutes either. The Close
  says so on screen and lists what to put in the file.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_timesheet_approval sits above pb_workforce_payroll_bridge in the MRO;
    # depending on it puts this module above BOTH overtime producers, which is
    # the only place a subtraction of time-off hours can see what they added.
    'depends': [
        'hr_holidays',
        'pb_timesheet_approval',
        'pb_workforce_payroll_bridge',
        'pb_close',
        'pb_attendance_flow',
        'pb_hr_workforce',
        'pb_ess_workforce',
        'pb_import_kit',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/time_pay_rules.xml',
        'views/overtime_request_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_time_pay/static/src/scss/time_pay_close.scss',
            'pb_time_pay/static/src/js/time_pay_close.js',
            'pb_time_pay/static/src/xml/time_pay_close.xml',
            'pb_time_pay/static/src/js/ot_desk_time_off.js',
            'pb_time_pay/static/src/xml/ot_desk_time_off.xml',
        ],
        # WDGAP S5-F (TP3): the late and early minutes page on My Payobook
        'web.assets_frontend': [
            'pb_time_pay/static/src/scss/time_pay_portal.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
