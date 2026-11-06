# Part of Payobook. See LICENSE file for full copyright and licensing details.
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name (ledger T-R4 / E-R13).
    'name': 'Employee Self-Service Portal — project time',
    'summary': 'Your hours by project, week by week, from My Payobook',
    'description': """
ETP E3 — project time, the week on one screen.

WHAT IT IS. Every employee (an employee login or a full account) enters the
hours they spent on each project, for a whole week, on one screen at
`/my/project-time`: projects down, Monday to Sunday across, totals both ways,
arrow keys, autosave per cell, "Copy last week"; on a phone, one day at a time.
This is PROJECT time (stock `account.analytic.line` on projects and tasks). It
is not the attendance "My Timesheet" page (`/my/work/timesheet`).

NO NEW TABLE (D1). Hours are stock timesheet lines, one per project / task /
day, written under sudo AFTER the ownership guard (ledger E-R2 / E-R3, E9):
the employee is resolved from the session and is never a request parameter;
only `project_id, task_id, date, unit_amount, name, employee_id` are passed to
stock `create()`, which derives the company and the analytic accounts. Lines
made by time off or public holidays are shown read-only and never written.

WHO MAY LOG WHERE (D2, ledger E10) is the stock internal-user rule re-stated in
Python: active, timesheets allowed, not a template, the employee's company or
none, visible to all employees or followed by the employee; never the time-off
task.

A PER-COMPANY SWITCH (D3), an `ir.config_parameter`
(`pb_me_project_time.enabled.<company id>`, unset = on) behind a settings box
in the Timesheets settings — no column on res.company.

No approval, no lock, no manager view in this release (D9).
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    # project_timesheet_holidays is a SOFT check ('global_leave_id' in
    # Line._fields): without it there are simply no leave lines to protect.
    'depends': ['pb_me_portal', 'hr_timesheet'],
    'data': [
        'views/portal_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        # the lean frontend bundle only (after pb_me_portal's tokens + .pbme
        # kit); nothing is added to the backend bundle
        'web.assets_frontend': [
            'pb_me_project_time/static/src/scss/project_time.scss',
            'pb_me_project_time/static/src/interactions/project_time.js',
        ],
    },
    'auto_install': True,
    'installable': True,
    'application': False,
}
