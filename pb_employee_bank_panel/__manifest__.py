# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Bank details on the employee side panel',
    'summary': "The employee side panel and Home read the approved bank account",
    'description': """
FORM STUDIO, phase FS-9 (deferred WDGAP item "Side panel and Home 'paid with
bank'").

* The employee side panel (Pay & tax) shows one compact Bank block: the
  APPROVED account (bank, account holder, account number with the last four
  digits only), its status (Approved / Waiting for approval / None), a change
  still waiting for approval with a link to it, and the "in another person's
  name" notice with its existing "Mark as seen".
* Home's "people have no bank account" figure reads the same approved
  account as Payroll-ready (one rule).
* The joining checklist's "Bank account" reads the same approved account; a
  change waiting for approval reads "Sent, waiting for HR", not missing.
* The old free-text Bank and Account Number boxes are no longer read by these
  screens nor offered as Mapping destinations (a saved mapping keeps
  working); they leave Full details through the employee form clean-up
  module. Their values stay.

Bridge module: it reaches the side panel and Home from outside (inheritance
and patches only) and writes nothing at install.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_employee_form_tidy',   # the approved-account helper Payroll-ready reads
        'pb_employee_vault',       # the side panel (Employee360Drawer)
        'pb_pay_delivery',         # "another person's name" + the waiting-change rule
        'pb_dashboard',            # Home
        'pb_onboarding',           # the joining checklist (follow-on A)
        'pb_formula_studio',       # Mapping destinations (follow-on C)
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_employee_bank_panel/static/src/scss/bank_panel.scss',
            'pb_employee_bank_panel/static/src/js/bank_panel.js',
            'pb_employee_bank_panel/static/src/xml/bank_panel.xml',
            'pb_employee_bank_panel/static/src/xml/onboarding_board.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
