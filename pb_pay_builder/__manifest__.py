{
    'name': 'Pay Builder',
    'summary': 'Agree pay and see how the pay scheme works out a full month.',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',
    'category': 'Human Resources',
    'author': 'Payobook',
    'depends': ['pb_formula_studio', 'pb_hr_payroll_formula', 'pb_import_kit', 'pb_scheme_map', 'pb_pay'],
    'assets': {'web.assets_backend': [
        'pb_pay_builder/static/src/js/pay_format.js',
        'pb_pay_builder/static/src/js/pay_builder.js',
        'pb_pay_builder/static/src/js/studio.js',
        'pb_pay_builder/static/src/xml/pay_builder.xml',
        'pb_pay_builder/static/src/xml/studio.xml',
        'pb_pay_builder/static/src/scss/pay_builder.scss',
    ]},
    'installable': True,
}
