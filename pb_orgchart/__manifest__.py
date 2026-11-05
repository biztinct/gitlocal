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
  * CHANGE IT LIVE: drag someone onto their new manager, pick several people
    and give them all one manager, add a dotted-line manager, add an open
    role under a manager, fill or close a role, swap places with a manager —
    each with one-tap Undo and a History tab on the person.
  * PLAN CHANGES FIRST: press Plan changes and the chart becomes a sandbox.
    Drag people, add roles, swap places; amber outlines and dashed lines show
    every change. Send the plan to the HR team in one tap; it goes live on
    the day you pick, once approved.
  * TIME MACHINE: slide back to see who reported to whom on any day of the
    last year, or forward to see approved plans, leavers and new starters.
  * SUGGEST A CHART: for a company where few managers are set, a starting
    chart worked out from the team records, ready to adjust and send.
  * EXPORT AND SHARE: a picture of the whole chart or one team, ready for a
    slide; a PDF with one page per team; a spreadsheet of everyone with
    their title, team, manager and location; a link that opens the same
    view for a colleague who can see the chart; print as you see it.
  * QUICK SEARCH: Org chart, Who reports to me?, Plan org chart changes and
    Suggest a chart are in the ⌘K search.
  * THE PAY DATA FILE KEEPS MANAGERS UP TO DATE: whenever the file has a
    Reporting Manager column, every import (a "this run only" file too)
    sets each person's manager from it, and lists the rows whose name it could not match on the import's
    last step and on the batch page.

Only HR users can change the chart; everyone else sees it read-only. Every
change is recorded on the employee record.
""",
    'version': '19.0.1.6.0',
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
        'pb_people_advanced',     # P3: the new-starter form lowers a role's to-hire count
        'biz_approval_chain',     # P3: the plan's status ladder and its guard
        'biz_approval_workflow',  # P3: the route a plan is approved on (orgplan)
        'pb_hr_payroll_formula',  # MANAGERCOL: the import batch the manager step hooks
        'pb_import_wizard',       # MANAGERCOL: the manager line on the import's last step
        'pb_import_batch',        # MANAGERCOL: the manager line on the batch page
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_orgchart_security.xml',
        'data/approval_process.xml',
        'data/ir_cron.xml',
        'views/pb_orgchart_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_orgchart/static/src/scss/orgchart.scss',
            'pb_orgchart/static/src/js/orgchart_layout.js',
            'pb_orgchart/static/src/js/orgchart_edit.js',
            'pb_orgchart/static/src/js/orgchart_dialog.js',
            'pb_orgchart/static/src/js/orgchart_plan.js',
            'pb_orgchart/static/src/js/orgchart_arrival.js',
            'pb_orgchart/static/src/js/orgchart_export.js',
            'pb_orgchart/static/src/js/orgchart.js',
            'pb_orgchart/static/src/js/orgchart_lens.js',
            'pb_orgchart/static/src/js/orgchart_palette.js',
            'pb_orgchart/static/src/xml/orgchart.xml',
            'pb_orgchart/static/src/scss/import_manager.scss',
            'pb_orgchart/static/src/xml/import_manager.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
