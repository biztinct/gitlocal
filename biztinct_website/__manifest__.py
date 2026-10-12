{
    'name': 'Biztinct Website',
    'summary': 'Premium public website and reliable contact enquiries',
    'version': '14.0.2.1.0',
    'category': 'Website',
    'author': 'Biztinct',
    'license': 'LGPL-3',
    'depends': ['website', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail.xml',
        'views/contact_views.xml',
        'views/templates.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
