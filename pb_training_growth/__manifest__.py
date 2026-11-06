# -*- coding: utf-8 -*-
{
# The opening line of this description is what the Apps list prints, so it is
# a USER-VISIBLE string and carries no programme code (ledger GR7, TIDY T10).
# Built as LEARNING phase L3.
    'name': 'Payobook Growth Plans and Learning Paths',
    'summary': 'Point a growth-plan objective at a learning path, see how far '
               'the person has got, and put them on it in one press',
    'description': """
The join between growth plans and learning paths.

An objective on a growth plan may point at a learning path ("Leading a line").
The plan then shows how far the person has got on that path, and HR can put
them on it straight from the objective. Nothing else in either side changes:
growth plans keep their own permissions, and learning paths keep theirs.

It installs by itself on a database that has both growth plans and training,
and is never needed anywhere else.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_pip',               # growth plans: the objective and its board
        'pb_training',          # learning paths (LEARNING L3)
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_training_growth/static/src/scss/growth_path.scss',
            'pb_training_growth/static/src/js/growth_path.js',
            'pb_training_growth/static/src/xml/growth_path.xml',
        ],
    },
    'installable': True,
    'application': False,
    # THE BRIDGE RULE: present exactly when both sides are. Neither side
    # depends on the other, so a database with only one of them never sees
    # this module.
    'auto_install': True,
}
