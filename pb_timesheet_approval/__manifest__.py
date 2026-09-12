# -*- coding: utf-8 -*-
{
    'name': 'Weekly Timesheet Approval',
    'summary': 'A week of hours, sent in once, signed off once, and read by '
               'payroll exactly as it was signed off',
    'description': """
The week is the thing that gets approved.

WHAT THIS MODULE ADDS

  * A WEEKLY TIMESHEET PACKET. One durable record per person per week, built
    from the punches and the overtime already recorded for those seven days. It
    carries the day-by-day picture, the totals, and a stamp of the hours it was
    built from — so an approval covers hours nobody moved afterwards.
  * SEND THE WEEK IN. From the weekly grid, for one person or for a whole
    department. It follows the route the business published: their manager, then
    the HR lead, by default.
  * A FROZEN WEEK. While a week is waiting for its approval, or once it has one,
    its days cannot be edited. Sending it back thaws it.
  * PAYROLL READS THE APPROVED WEEK. Hours, worked days and overtime come from
    approved weeks rather than from whatever is in the system at the moment the
    run happens — and every figure says which week it came from.

WHAT IT NEVER DOES

  It does not decide overtime. Ceilings, bonus hours and the overtime rules are
  exactly what they were; the packet records what those rules decided and asks
  for one sign-off on the week as a whole.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_hr_workforce owns the weekly grid and overtime; pb_attendance_flow owns
    # the other punch sources; pb_close owns the day lock and the pay-run
    # advisory seam; pb_workforce_payroll_bridge owns the hours that reach
    # payroll — this module sits ABOVE it in the MRO on purpose, so the approved
    # week can answer for the overtime codes the bridge would otherwise read
    # live.
    'depends': [
        'pb_hr_workforce',
        'pb_attendance_flow',
        'pb_close',
        'biz_approval_workflow',
        'pb_approval_config',
        'pb_workforce_payroll_bridge',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/timesheet_packet_rules.xml',
        'views/res_config_settings_views.xml',
        'views/timesheet_packet_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_timesheet_approval/static/src/scss/week_approval.scss',
            'pb_timesheet_approval/static/src/js/week_approval.js',
            'pb_timesheet_approval/static/src/xml/week_approval.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
