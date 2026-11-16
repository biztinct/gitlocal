# -*- coding: utf-8 -*-
{
    # The opening line of this description is what the Apps list prints, so
    # it is a USER-VISIBLE string (ledger GR7, TIDY T10).
    'name': 'Payobook Change Job',
    'summary': 'Promotion, transfer and pay change in one request, one sign-off '
               'and one start date',
    'description': """
One guided "Change job": a new job or title, another team, manager, place of
work, working hours or company, and new pay, all in ONE request with ONE start
date, ONE reason, ONE sign-off route (their manager, then HR, then Finance only
when the rise is above the guidance) and ONE letter.

Nothing is written before the start date: a future change is approved and then
held as "Scheduled" until a quiet hourly job writes it on the day. A change that
starts in a month already paid is allowed; pay-line changes are written as dated
contract amount changes so the Past-month re-work can find them, and the finished
request offers to open that re-work. No back pay is written here.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'om_hr_payroll',          # hr.contract + pay lines (hr.contract.advantage)
        'biz_audit_trail',        # one event on the person's trail
        'biz_approval_workflow',  # the one sign-off route
        'pb_approval_config',     # the responsibility catalogue (HR lead, Finance)
        'pb_hr_payroll_formula',  # dated contract amount changes (the re-work reads them)
        'pb_import_kit',          # pbim tokens + quiet glance
        'pb_filter_kit',          # the filter panel on the board
        'pb_hub',                 # the palette registry
        'pb_pay',                 # pb.pay.apply (24-hour take-back) + the guidance %
        'pb_lifecycle',           # letters
        'pb_employee_vault',      # the person's side panel + timeline
        'pb_orgchart',            # the org chart person panel
        'pb_scheme_map',          # "Paid by" before and after
        'pb_records',             # the company-time "today" every dated change uses
    ],
    'data': [
        'security/job_change_security.xml',
        'security/ir.model.access.csv',
        'data/approval_process.xml',
        'data/job_change_cron.xml',
        'views/job_change_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_job_change/static/src/scss/job_change.scss',
            'pb_job_change/static/src/js/job_change.js',
            'pb_job_change/static/src/js/job_change_palette.js',
            'pb_job_change/static/src/js/job_change_patches.js',
            'pb_job_change/static/src/xml/job_change.xml',
            'pb_job_change/static/src/xml/job_change_patches.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
