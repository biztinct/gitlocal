# -*- coding: utf-8 -*-
{
    'name': 'Payobook Plan to Hiring',
    'summary': 'An approved Decision Room plan becomes draft hiring requests',
    'description': """
WDGAP step 8, phase S8-C. Glue between the Decision Room and Hiring.

On an APPROVED plan, "Hiring requests" lists every hire the plan adds
(team, role, how many, the month they arrive). The person ticks the lines
they want and presses "Make the hiring requests": each becomes a DRAFT hiring
request (never sent in by itself), linked to the plan and to its line.
Pressing again never makes a second request for a line that has one — the
link is unique per plan and line. The plan shows "3 of 5 lines have a
request"; the request names the plan it came from.

Leavers in a plan (negative lines) are listed as "not handled here". A line
for "other roles" asks for a job title. A team where hiring is paused (when
the Organisation module is installed) says so and makes nothing.

Nothing here changes a payslip, a contract or an employee. No demo data, no
email, no scheduled job.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'pb_decision_room',   # the approved plan and the room's screen
        'pb_hiring',          # hiring requests
        'pb_import_kit',      # icons
    ],
    'data': [
        'views/plan_hiring_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_plan_hiring/static/src/scss/plan_hiring.scss',
            'pb_plan_hiring/static/src/js/plan_hiring.js',
            'pb_plan_hiring/static/src/xml/plan_hiring.xml',
        ],
    },
    'installable': True,
    'application': False,
}
