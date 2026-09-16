# -*- coding: utf-8 -*-
{
    'name': 'Leave Command Center',
    'summary': 'Org-wide HR leave cockpit — approval queue, month heatmap, '
               'balance board, apply-on-behalf — over core hr.leave',
    'description': """
Sudima Phase K — Leave Management (#8) as a bespoke HR Command Center.

A FACADE-ONLY cockpit over the existing hr_holidays engine — pb_timeoff adds NO
leave logic. Every mutation rides core hr.leave's own gated actions AS THE REAL
USER (C18.17); there is no sudo anywhere in the module.

  * Who's out today · pending KPIs · this-week out-by-day
  * Approval queue (To approve / 2nd approval) with one-click approve/refuse
    (required note on refuse) — company-scoped (C18.11/18)
  * Department × day month heatmap (density tint, weekend shading, today marker)
  * Paged employee × leave-type balance board (validated allocations − taken)
  * Apply-on-behalf — a plain hr.leave create as the real user; core validation
    (overlap, balance) surfaces verbatim

HR/officer gated (hr_holidays.group_hr_holidays_user | hr.group_hr_manager |
om_hr_payroll.group_hr_payroll_manager). No ESS/self-service (Phase I).
""",
    'post_init_hook': 'post_init_hook',
    # 19.0.1.4.0 — RIZE W2 D1: public holidays for everybody (a Mission
    # Control lens + `/my/holidays`), escalation to the HR lead, the
    # backdating rules, the past-leave lock and the carry-forward watch.
    'version': '19.0.1.4.0',
    'category': 'Human Resources/Time Off',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'biz_approval_workflow',   # the configurable route its ladder now runs on
        'hr_holidays',
        'om_hr_payroll',   # hr.leave.type.code, payroll-manager group
        'pb_sidebar',
        'pb_import_kit',
        'pb_hub',          # the ⌘K palette registry
        'pb_me_portal',    # the .pbme employee-page kit (/my/holidays)
        'portal',
        'website',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_timeoff_security.xml',
        'views/pb_timeoff_action.xml',
        'views/hr_leave_type_views.xml',
        'views/portal_holidays.xml',
        'data/pb_sidebar.xml',
        'data/mail_template.xml',
        'data/pb_timeoff_config.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_timeoff/static/src/scss/pb_timeoff.scss',
            'pb_timeoff/static/src/scss/pb_holidays.scss',
            'pb_timeoff/static/src/js/pbto_icons.js',
            'pb_timeoff/static/src/js/pb_timeoff.js',
            'pb_timeoff/static/src/js/pb_holidays.js',
            'pb_timeoff/static/src/js/timeoff_palette.js',
            'pb_timeoff/static/src/xml/pb_timeoff.xml',
            'pb_timeoff/static/src/xml/pb_holidays.xml',
        ],
        'web.assets_frontend': [
            'pb_timeoff/static/src/scss/portal_holidays.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
