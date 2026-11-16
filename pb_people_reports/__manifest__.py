# -*- coding: utf-8 -*-
{
    # The opening line of this description is what the Apps list prints, so
    # it is a USER-VISIBLE string (ledger GR7). Built as WDGAP S9-B.
    'name': 'Payobook People Reports',
    'summary': 'Turnover, joiners and leavers, why people leave, age, gender '
               'and length of service — small groups hidden',
    'description': """
People reports, as a tab of People › Insights.

  * Headcount and turnover, joiners and leavers, why people leave, age and
    gender, length of service — by company, department and year.
  * For HR only, for the companies they already see.
  * Any group under 5 people is hidden, on screen, in the totals and in the
    download, and so is any figure that would let someone work one out.
  * No money figures. Nothing is stored and nothing is scheduled: figures
    are worked out from the employee records when the screen opens.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'pb_hub',
        'pb_people_hub',
        'pb_insights',
        'pb_group',
        'pb_import_kit',
        'pb_filter_kit',
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_people_reports/static/src/scss/people_reports.scss',
            'pb_people_reports/static/src/js/people_reports.js',
            'pb_people_reports/static/src/xml/people_reports.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
