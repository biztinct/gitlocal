# -*- coding: utf-8 -*-
{
    # The opening line of this description is what the Apps list prints, so
    # it is a USER-VISIBLE string. Built as DOCSTUDIO phase R (study line 900).
    'name': 'Payobook Report Builder',
    'summary': 'Build your own report from people, contracts, time off, attendance, '
               'hiring, assets, training, expense claims and goals',
    'description': """
Build a report: a tab of Insights.

  * Pick what each row is (people, contracts, time off requests, attendance,
    open roles, applicants, assets, training, expense claims, goals), then
    click the fields you want. The table fills with real rows at once.
  * Add facts about the person to any row, and counts from other areas
    (time off taken, days attended, assets held, training finished, open
    expense claims, goals set) to a list of people.
  * Filter, sort, group by up to two fields with totals; money is totalled
    per currency, never added across two.
  * Save, share with everyone who can open reports, download to Excel.
  * Every read happens as the person reading: a shared report never shows
    anybody more than their own screens would.

Nothing is created when the module is installed: no records, no jobs, no
emails.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'web',
        'hr',
        'pb_hub',
        'pb_insights_hub',
        'pb_sidebar',
        'pb_hr_payroll_base',
        'pb_group',
        'pb_import_kit',
        'pb_filter_kit',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_report_builder_rules.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_report_builder/static/src/scss/report_builder.scss',
            'pb_report_builder/static/src/js/report_builder.js',
            'pb_report_builder/static/src/xml/report_builder.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
