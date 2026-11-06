# -*- coding: utf-8 -*-
{
    'name': 'Payobook Learning',
    'summary': 'Courses, tests, certificates and who is on what',
    'description': """
Learning — one place for everything a company teaches its people.

Training used to be one tab inside Talent. The LEARNING programme gives it its
own entry on the left menu, under GROW, between Talent and Help:

    overview · my learning · courses · assigned · required · tests ·
    claims · numbers

This module is only the shell. Each tab is a board added by the module that
owns it (the training module today), so a company without it simply has an
empty rail with an honest sentence. Nothing here stores data or decides who
may see what: every board keeps its own access rules. The entry itself is
everybody's — every member of staff has "My learning" — and the training
team's tabs gate themselves.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hub',                   # the shell kit + the global palette registry
        'pb_settings',              # the cog in the command bar opens Settings
        'pb_sidebar',               # this module ships a left-menu entry
        'pb_learn',                 # the GROW section the entry sits in
    ],
    'data': [
        'views/pb_learning_hub_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_learning_hub/static/src/js/learning_hub.js',
            'pb_learning_hub/static/src/js/learning_hub_palette.js',
            'pb_learning_hub/static/src/xml/learning_hub.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
