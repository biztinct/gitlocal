# -*- coding: utf-8 -*-
{
    'name': 'Payobook Dashboard',
    'summary': 'Smashing command-centre home dashboard for Payobook',
    # LOOK P4. The home page names the payroll month its figures are about and
    # offers a strip to change it. Python and assets both change; a code change
    # with no version bump is invisible to the deploy-time version-diff gate.
    # 1.6.0: get_user_roots is pruned alongside load_web_menus, so website's
    # frontend corner widget stops raising KeyError on an action-less root.
    # 1.6.1: the formula-engine figures read inside `safe()`, so a person who
    # may read configs but not their test results gets zeros, not an error.
    # 2.0.0: HOME P1 — `get_home_data()`, the new Home's one call (period,
    # needs-you, 12 months from the stored run totals, runs, steps, upcoming,
    # people, hiring, learn, schemes), every foreign read through optional().
    # 2.1.0: HOME P2 — the new Home front end on get_home_data(): the hero
    # sentence + journey + one primary, needs-you chips, the 12-month chart
    # that is the month picker, the month panel, steps and coming up; Lucide
    # and tokens from pb_import_kit (now a dependency); months carry
    # `foreign_runs` (H21).
    'version': '19.0.2.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_import_kit'],
    'data': [
        'views/pb_dashboard_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_dashboard/static/src/scss/pb_dashboard.scss',
            'pb_dashboard/static/src/js/pb_dashboard.js',
            'pb_dashboard/static/src/xml/pb_dashboard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
