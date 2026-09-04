{
    'name': 'Login Language Selector',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Choose language at login screen',
    'description': """
        Adds a language dropdown to the Odoo login page.
        Users can select their preferred language (e.g. English, Vietnamese)
        before logging in. On successful login, the user's language preference
        is automatically updated.
    """,
    'author': 'Biztinct',
    'depends': ['web'],
    'data': [
        'views/login_language.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_login_language/static/src/css/login_language.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
