# -*- coding: utf-8 -*-
{
    'name': 'Payobook Insights Cockpit',
    'summary': 'Executive analytics cockpit — cost story, department split, '
               'statutory load, workforce pulse, snapshots and report gallery',
    'description': """
Sudima Phase M — Executive Dashboard & Payroll Analytics.

A READ-ONLY analytics cockpit over the existing payroll data. pb_insights adds
no models and no stored fields: every figure comes from an existing stored
roll-up or one bounded aggregate.

  * Hero — latest-run net headline, delta vs the previous run, 12-run sparkline
  * Cost story — per-run net / gross / total cost over 3, 6 or 12 months, read
    from the STORED pb_total_* roll-ups (no payslip-line loop)
  * Department leaderboard — net by department from real payslip lines, with a
    contract-wage fallback badged as approximate
  * Statutory split — employee vs employer contributions (+ tax withheld)
  * Workforce pulse — attendance exceptions, time off, overtime and bonus
    hours; every tile soft-dep gated so a missing phase never breaks the board
  * Analytics snapshots — the payroll.analytics rows, company-filtered, READ ONLY
  * Report gallery — the single path to every analytics report (this replaces
    the retired pb_hr_payroll_analytics menu forest)

Gated to the payroll analytics tier; bonus hours carry the payroll-manager
tier. All assets are local — no CDN, no external chart library.
""",
    # C2: bump on EVERY asset-file change — the compiled bundle URL hash is
    # keyed on module versions, so without this browsers keep the stale CSS.
    'version': '19.0.3.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_import_kit supplies the shared --pbim-* design tokens + primitives.
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_payruns',
                'pb_import_kit'],
    'data': [
        'views/pb_insights_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_insights/static/src/scss/insights.scss',
            'pb_insights/static/src/js/pbin_icons.js',
            'pb_insights/static/src/js/insights.js',
            'pb_insights/static/src/xml/insights.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
