# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Privacy notice and consent',
    'summary': "Employees read the company's privacy notice on My Payobook and give their answer; HR sees who has answered",
    'description': """
WDGAP S6-A item 3 (owner ruling E3) — consent for personal data.

A company publishes a privacy notice (its own wording, a version number,
per language). The first time an employee opens My Payobook after that, they
read it and answer "I have read and agree" or "I do not agree". Both answers
are recorded per EMPLOYEE record (one person can have several), with the
exact wording shown, the language, when, and by which login. Nobody is locked
out: either answer continues to My Payobook. A new version asks again; the
same version never asks twice.

HR sees, on People > Privacy, who has agreed, who has not answered yet, who
said no, and records paper consent for people without a login (with who and
when). Managers see nothing.

SILENT INSTALL. No notice published means nobody is asked, no board numbers,
no job, no email.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'mail',
        'portal',
        'pb_me_portal',      # My Payobook: the hooks, the kit, the session employee
        'pb_import_kit',     # pbim tokens + the quiet glance on the HR board
        'pb_filter_kit',     # pbfIcon (cached icon markup)
        'pb_people_hub',     # the People hub hosts the HR board as a lens
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_me_privacy_security.xml',
        'views/notice_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_me_privacy/static/src/scss/privacy_portal.scss',
        ],
        'web.assets_backend': [
            'pb_me_privacy/static/src/scss/privacy_lens.scss',
            'pb_me_privacy/static/src/js/privacy_lens.js',
            'pb_me_privacy/static/src/xml/privacy_lens.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
