# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Payobook Kinds of Leave',
    'summary': 'Set up kinds of leave, how they build up each month, '
               'extra days for long service and ready-made kinds by country',
    'description': """
WDGAP S5-A — kinds of leave and how they are earned.

* A "Kinds of leave" screen (Settings > HR and the command palette) that the
  customer's own HR team can reach: list, add, edit, switch on and off, with a
  guided drawer, a preview of what the employee will see, and a set-up check
  (kinds whose pay is still undecided, people with no start date).
* How a kind is earned: given by HR (today's behaviour, the default), all at
  once each year, or a share each month — with a waiting period, extra days
  for long service, a most-you-can-hold limit, a "take days before they are
  earned" switch (off by default) and an optional "days run out" date. A daily
  job posts each month's share into ONE allocation per person, kind and leave
  year, with one audit row per person, kind and month (never twice).
* Ready-made kinds for Vietnam, Indonesia, India, Singapore, Thailand,
  Cambodia and Malaysia, as reviewed data inside this module, offered on
  demand as a starting point: created switched off, every figure with its
  source, never twice.
* Balances ignore days that have run out (employee page and HR board).

Nothing is created or switched on by installing it.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Time Off',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'hr_holidays',
        'pb_timeoff',        # pay treatment fields, the HR board, the country rule
        'pb_ess_workforce',  # My Leave (get_my_leave, _my_appliable_types)
        'pb_filter_kit',     # the shared filter panel on the list
        'pb_import_kit',     # icons + quiet board pieces
        'pb_hub',            # the command palette registry
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/leave_setup_actions.xml',
        'views/portal_templates.xml',
        'data/ir_cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_leave_setup/static/src/scss/leave_setup.scss',
            'pb_leave_setup/static/src/js/leave_setup.js',
            'pb_leave_setup/static/src/js/leave_setup_palette.js',
            'pb_leave_setup/static/src/xml/leave_setup.xml',
        ],
        'web.assets_frontend': [
            'pb_leave_setup/static/src/scss/leave_setup_portal.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
