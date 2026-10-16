{
    'name': 'Payobook Payroll Templates',
    'summary': 'Current employee records and reviewed monthly workbooks',
    'version': '19.0.1.0.5',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'depends': ['pb_records', 'pb_payrun_wizard', 'pb_formula_studio'],
    'data': ['views/templates.xml'],
    'assets': {'web.assets_backend': [
        'pb_payroll_templates/static/src/templates.scss',
        'pb_payroll_templates/static/src/templates.js',
        'pb_payroll_templates/static/src/templates.xml',
    ]},
    'installable': True,
}
