# -*- coding: utf-8 -*-
{
    'name': 'Approval Matrix',
    'summary': 'One place to decide who signs off what, and one inbox where '
               'every decision is made',
    # A manifest description is read by a PERSON in the Apps list, so it keeps
    # this product's own vocabulary. The engineering account — the facades, the
    # scope keys and the registry seams — is in the module's docstrings.
    'description': """
Every check your business makes, in one place.

WHAT THIS MODULE ADDS

  * THE APPROVAL MATRIX. One screen listing every process that can need a
    sign-off, grouped the way you see the product: Pay, Money out, Pay data,
    People, Time, Setup & rules, Platform. Each row says who signs it off, in
    words, where it applies, and whether it is in use yet.
  * A WORKFLOW BUILDER. Purpose, then people, then safeguards, then review and
    publish. A sentence at the top says what the route does in plain English
    and changes as you edit. "Try an example" runs the route against facts you
    choose and names the real people it would reach — before anything is
    published. "Check whole coverage" does the same for every part of the
    business at once.
  * PEOPLE & BACKUPS. Who fills each responsibility, in each part of the
    business, with a backup and a hand-over for when somebody is away. Filling
    a responsibility never grants anybody access; the picker says so and points
    at the place where access is given.
  * ONE INBOX. Everything waiting for a decision, from every part of the
    product, on one screen: the facts as they were when it was sent in, what is
    attached, who has decided and who is next. Approve, send back or turn down,
    always with a reason where one is owed.
  * ASK FOR A SIGN-OFF. A request for anything that has no process of its own.

WHAT IT NEVER DOES

  Nothing is ever approved automatically. Being late reminds, then escalates,
  and hands over to a named backup only where the business asked for that. A
  route that checks nothing is a published choice, said out loud on the Matrix
  row, and every use of it is still recorded.
""",
    'version': '19.0.1.4.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'biz_approval_workflow',   # the engine: routes, people, requests
        'pb_hub',                  # the shared back chip + the global palette
        'pb_settings',             # the cog this screen lives behind
        'pb_sidebar',              # the rail, matched by tag only (no new item)
        'pb_import_kit',           # pbim tokens/primitives + the shared ic()
        'pb_group',                # divisions — the parts of the business
        'hr',
        'mail',
    ],
    'data': [
        'data/roles.xml',
        'data/roles_p6.xml',
        'data/processes.xml',
        'data/processes_p6.xml',
        'views/actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_approval_config/static/src/scss/approval_matrix.scss',
            'pb_approval_config/static/src/scss/inbox.scss',
            # the shared helpers first, then the components that import them,
            # then the rows that name their actions
            'pb_approval_config/static/src/js/sentence.js',
            'pb_approval_config/static/src/js/picker_drawer.js',
            'pb_approval_config/static/src/js/builder.js',
            'pb_approval_config/static/src/js/people_tab.js',
            'pb_approval_config/static/src/js/history_tab.js',
            'pb_approval_config/static/src/js/scheme_panel.js',
            'pb_approval_config/static/src/js/matrix_room.js',
            'pb_approval_config/static/src/js/request_drawer.js',
            'pb_approval_config/static/src/js/inbox.js',
            'pb_approval_config/static/src/js/palette.js',
            'pb_approval_config/static/src/xml/matrix_room.xml',
            'pb_approval_config/static/src/xml/builder.xml',
            'pb_approval_config/static/src/xml/people.xml',
            'pb_approval_config/static/src/xml/scheme_panel.xml',
            'pb_approval_config/static/src/xml/inbox.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
