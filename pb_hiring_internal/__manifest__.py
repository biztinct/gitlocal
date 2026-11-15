# -*- coding: utf-8 -*-
{
    # The opening line of the description is what the Apps list prints, so it
    # is a USER-VISIBLE string and carries no programme code.
    'name': 'Payobook Jobs Inside the Company',
    'summary': 'Staff see open roles on their own pages, apply with their '
               'record and follow where it is',
    'description': """
Staff apply for open roles inside the company.

  * **Who can apply, per role.** Outside candidates only (what every role
    does today), staff and outside candidates, or staff only. A staff-only
    role never reaches the careers page.
  * **Jobs inside the company** on the employee's own pages: the roles open
    to staff in their company, the advert, and one press to apply with the
    record they already have. A note and a CV are optional.
  * **Their manager is told only when an offer is near.** Until then only
    the hiring team for that role sees the application. If their manager is
    on that hiring team, the employee is told so before they apply.
  * **A move, never a second person.** Confirming an internal candidate
    joined makes no new employee record, no new contract, no new login and
    no joining checklist: it opens the Change job flow when the system has
    it, and otherwise leaves HR a calm "job change to do".
  * **Paused roles stay hidden** when hiring is paused for them.

Built as WDGAP Step 6, phase S6-B.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hiring',            # the roles, the candidates, the offer
        'pb_me_portal',         # the employee pages kit and their hooks
        'hr_recruitment',
        'utm',
    ],
    'data': [
        'views/requisition_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_hiring_internal/static/src/scss/internal_jobs.scss',
            'pb_hiring_internal/static/src/js/internal_jobs.js',
        ],
        'web.assets_backend': [
            'pb_hiring_internal/static/src/scss/staff_moves.scss',
            'pb_hiring_internal/static/src/js/staff_moves.js',
            'pb_hiring_internal/static/src/xml/staff_moves.xml',
            'pb_hiring_internal/static/src/js/board_patch.js',
            'pb_hiring_internal/static/src/xml/board_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
