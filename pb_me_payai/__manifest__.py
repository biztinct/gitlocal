# -*- coding: utf-8 -*-
{
    # The opening line of the description is what the Apps list prints, so it
    # is a USER-VISIBLE string and carries no programme code.
    'name': 'Payobook PayAI for Employees',
    'summary': 'Employees ask PayAI about company policies, answered only '
               'from the policy files HR uploads',
    'description': """
PayAI on the employee's own pages, for company policies only.

  * **Answers only from the company's own policy files.** HR uploads the
    handbook and policy files and publishes them. PayAI answers from those
    words and nothing else: no general knowledge, and no personal figures
    (no leave balance, no payslip).
  * **Always says which policy it used.** Every answer names the policy and
    the section it came from.
  * **"Ask HR" when it cannot answer**, with the question already filled in.
  * **Off until the company switches it on**, with a daily limit per person
    and per company, and a count HR can see. It uses the AI account the
    system already has for this company; without one, HR sees "not set up
    yet" and employees see nothing.
  * **Private by design.** Only the question (with names, contact details
    and amounts taken out) and the matching policy words leave the system.
    Never the employee's name, record or figures.
  * **HR reads the questions, never who asked.** The questions are kept with
    names taken out, by day only, with nothing that points at a person; a
    "Could not answer" list and an Excel file show HR where the policies
    have gaps. In a company with fewer than five people who could ask, HR
    sees numbers only.

Built as WDGAP Step 6, phase S6-B.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'pb_me_portal',             # the employee pages kit and their hooks
        'pb_payroll_ai_insights',   # the AI account and the name scrub
        'pb_ask_hr',                # "Ask HR" with the question filled in
        'pb_home_hub',              # HR's Policies tab on Home
        'pb_import_kit',            # the backend icon set
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_me_payai_security.xml',
        'views/res_config_settings_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_me_payai/static/src/scss/ask_policy.scss',
            'pb_me_payai/static/src/js/ask_policy.js',
        ],
        'web.assets_backend': [
            'pb_me_payai/static/src/scss/policy_desk.scss',
            'pb_me_payai/static/src/js/policy_desk.js',
            'pb_me_payai/static/src/xml/policy_desk.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
