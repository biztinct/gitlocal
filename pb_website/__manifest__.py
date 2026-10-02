{
    'name': 'Payobook Website',
    'version': '19.0.1.3.0',
    'category': 'Website',
    'summary': 'Intelligent global payroll marketing homepage (served at /)',
    'description': """
Intelligent global payroll marketing homepage, focused on Southeast Asia and India.
Native animated globe, payroll command centre, accessible PayAI capability previews,
interactive formula examples, intelligent mappings and Payslip Studio illustrations.
""",
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': ['website'],
    'data': [
        'views/homepage_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_website/static/src/js/globe-land.js',
            'pb_website/static/src/scss/landing.scss',
            'pb_website/static/src/js/landing.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
