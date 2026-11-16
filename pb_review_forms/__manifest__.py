# -*- coding: utf-8 -*-
{
# The opening line of this description is what the Apps list prints, so it is
# a USER-VISIBLE string and carries no programme code (pb_goals GR7).
# Built as WDGAP S9-A.
    'name': 'Payobook Review Forms',
    'summary': 'One end-of-year review form for each goal year: the employee '
               'gives their own view, then the manager',
    'description': """
The end-of-year review, written once by HR for the whole company.

  * **One form for each goal year.** The goals score the year already works
    out, a few skills or company values rated from "Well below" to "Well
    above", and up to eight questions HR writes.
  * **The employee first.** They give their own view on My Payobook; their
    manager reads it, rates the same lines in the Goals screen and writes the
    overall comment.
  * **One overall result.** HR sets how much each part counts (for example
    70% goals, 30% skills), and the pay review starts from that result.
  * **Shown when HR says.** As soon as the manager finishes, or from a date
    HR chooses. The employee says they have read it, or asks to talk about
    it, and a PDF is filed in their documents.
  * **Locked once used.** The first review sent in locks the year's form; a
    new version is next year's form.

Installing it changes nothing: there is no form until HR writes one.
""",
    'version': '19.0.1.0.1',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_goals',             # the goal year, the review rows, the score
        'pb_me_portal',         # My Payobook pages and the "Needs you" hook
        'pb_employee_vault',    # where the finished review PDF is filed
        'pb_settings',          # the Settings › HR card
        'pb_hub',               # ⌘K and the back chip
        'pb_import_kit',        # pbim tokens and the shared ic() icons
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/review_forms_rules.xml',
        'data/review_forms_data.xml',
        'report/review_form_report.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_review_forms/static/src/scss/review_forms.scss',
            'pb_review_forms/static/src/js/review_forms_studio.js',
            'pb_review_forms/static/src/js/goals_drawer_patch.js',
            'pb_review_forms/static/src/xml/review_forms_studio.xml',
            'pb_review_forms/static/src/xml/goals_drawer.xml',
        ],
        'web.assets_frontend': [
            'pb_review_forms/static/src/scss/portal_review_forms.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
