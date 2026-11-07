{
    'name': 'Sudima Website',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Sudima Panels staff welcome and sign-in screens',
    'author': 'Payobook',
    'license': 'LGPL-3',
    'depends': ['website'],
    'data': ['views/portal_templates.xml'],
    'assets': {
        'web.assets_frontend': [
            'sudima_website/static/src/scss/portal.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
