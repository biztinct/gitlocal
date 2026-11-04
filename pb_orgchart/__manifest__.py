# -*- coding: utf-8 -*-
{
    'name': 'Payobook Org Chart',
    'summary': 'Who reports to whom, drawn from the employee records — '
               'a live chart in People',
    # A manifest description is shown to a person in the Apps list, so it is a
    # USER-VISIBLE string and keeps this product's own vocabulary. The
    # engineering account lives in docs/handovers/orgchart/.
    'description': """
The organisation chart, drawn from each person's manager.

WHAT THIS MODULE ADDS

  * AN ORG CHART TAB in People, right after Employees. Everyone, with their
    manager, team, location and title, laid out top-down or sideways, as
    team cards or as an indented list.
  * SIX NUMBERS THAT FOCUS: people per manager, open roles, people with no
    manager yet, wide teams, dotted lines and new joiners. Press one and the
    chart shows only those people.
  * FIND ANYONE: search by name, title or team and jump straight to them;
    follow their chain of managers to the top.
  * SPREADSHEET AND PRINT: the chart as a list of names, titles, teams,
    managers and locations, or printed as you see it.

It reads the employee records and changes nothing. The chart updates itself
whenever an employee record changes.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'mail',
        'pb_import_kit',    # pbim tokens/primitives + the shared ic() set
        'pb_hub',           # hub_nav (openHub) for the Employees door
        'pb_people',        # the Employees cockpit and its drawer registry
        'pb_people_hub',    # the lens host (EMPLOYEE_GATE, PEOPLE_LENSES)
    ],
    'data': [
        'views/pb_orgchart_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_orgchart/static/src/scss/orgchart.scss',
            'pb_orgchart/static/src/js/orgchart_layout.js',
            'pb_orgchart/static/src/js/orgchart.js',
            'pb_orgchart/static/src/js/orgchart_lens.js',
            'pb_orgchart/static/src/xml/orgchart.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
