# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Payobook Employee Voice',
    'summary': 'Anonymous employee surveys, results by group, action plans',
    'description': """
WDGAP S9-C — employee voice (owner rulings P4, P5).

HR sets up a survey round (who is asked, which questions — from a small
library in English, Vietnamese and Indonesian, or their own — and when it
closes). People answer on My Payobook only; people without email get a
sign-in slip from the Access screen's "Logins for workers".

FULLY ANONYMOUS BY CONSTRUCTION (see models/voice_box.py): no answer row
exists; answers wait sealed outside the database and go in once, as counts,
when the round closes. "Who has answered" is a separate list of one-way
codes whose key lives outside the database and is destroyed at close.
Results and comments show only for groups of 5 or more answers, with
secondary suppression so nothing can be worked out by subtraction — on
screen and in the Excel download. Managers see their own team's card on
My Payobook (or their department's, when the team is too small).

Simple action plans (owner, due date, theme) follow up the results.
Installing changes nothing for anybody: no round, no email, no card.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'mail',
        'pb_me_portal',      # My Payobook: page, home card, Needs you
        'pb_me_team',        # the manager's card on /my/team (inherited)
        'pb_talent_hub',     # the Voice tab
        'pb_settings',       # the Settings card
        'pb_import_kit',     # icons + quiet board pieces
        'pb_filter_kit',     # cached icons
        'biz_access',        # "Logins for workers" (linked, not called)
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/voice_security.xml',
        'data/voice_library_data.xml',
        'data/ir_cron.xml',
        'views/voice_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_voice/static/src/scss/voice_board.scss',
            'pb_voice/static/src/js/voice_board.js',
            'pb_voice/static/src/js/voice_palette.js',
            'pb_voice/static/src/xml/voice_board.xml',
        ],
        'web.assets_frontend': [
            'pb_voice/static/src/scss/voice_portal.scss',
        ],
    },
    'installable': True,
    'application': False,
}
