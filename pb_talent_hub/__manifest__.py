# -*- coding: utf-8 -*-
{
    'name': 'Payobook Talent',
    'summary': 'Goals, growth plans and praise in one place on the left menu',
    'description': """
Talent — one place for how people grow.

Goals, growth plans and praise used to live in three places (People and the
Lifecycle hub). The revised menu puts them side by side under GROW, above
Learning:

    goals · growth · praise

Training was a fourth tab until LEARNING L0 (2026-10-21) gave it its own
entry, GROW › Learning; an old link that still asks Talent for the training
tab is sent there.

This module is only the shell. Each tab is the existing board, added by the
module that owns it, so a company without one of them simply has one tab
fewer. Nothing here stores data or decides who may see what: every board keeps
its own access rules.
""",
    'version': '19.0.1.1.0',
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
        'views/pb_talent_hub_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_talent_hub/static/src/js/talent_hub.js',
            'pb_talent_hub/static/src/js/talent_hub_palette.js',
            'pb_talent_hub/static/src/xml/talent_hub.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
