# -*- coding: utf-8 -*-
{
# The opening line of this description is what the Apps list prints, so it is
# a USER-VISIBLE string and carries no programme code (ledger GR7, TIDY T10).
# Built as LEARNING phase L7 (owner decision LD9).
    'name': 'Payobook Training Drafts by PayAI',
    'summary': 'Upload a procedure and PayAI drafts a course from it: an '
               'outline, short lessons and a ten-question quiz, for a trainer '
               'to read, edit and publish',
    'description': """
PayAI drafts a course from a document.

On Learning › Courses, "New course" offers a second way to start: upload a
procedure (a PDF, a Word file or a text file, up to 10 MB) and PayAI returns
an outline, three to eight short reading lessons and a ten-question quiz. The
result is a DRAFT course: unpublished, open to nobody, with a line on top that
says it was drafted from that file and must be read before it is published.
A trainer edits it and publishes it; nothing is ever published by PayAI.

It uses the PayAI provider the administrator set up under Settings › PayAI.
With none, it says so in a sentence and nothing is sent anywhere.

PayAI's chat can also be asked to "draft a course from <a file>": it opens the
same drawer with that file picked, and the draft is made from there.

It installs by itself on a database that has both PayAI's actions and
training, and is never needed anywhere else.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_training',          # courses, lessons, the Courses board
        'pb_payai_actions',     # PayAI's action catalogue (and its provider)
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_training_payai/static/src/scss/draft_way.scss',
            'pb_training_payai/static/src/js/draft_way.js',
            'pb_training_payai/static/src/xml/draft_way.xml',
        ],
    },
    'installable': True,
    'application': False,
    # THE BRIDGE RULE: present exactly when both sides are.
    'auto_install': True,
}
