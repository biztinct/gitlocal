{
    'name': 'Payobook Payroll Templates',
    'summary': 'Current employee records and reviewed monthly workbooks',
    'version': '19.0.1.1.3',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'depends': ['pb_records', 'pb_payrun_wizard', 'pb_formula_studio'],
    'data': ['views/templates.xml'],
    'assets': {'web.assets_backend': [
        'pb_payroll_templates/static/src/templates.scss',
        'pb_payroll_templates/static/src/monthly_review.js',
        'pb_payroll_templates/static/src/templates.js',
        'pb_payroll_templates/static/src/monthly_review.xml',
        'pb_payroll_templates/static/src/templates.xml',
    ], 'web.assets_unit_tests': ['pb_payroll_templates/static/tests/monthly_review.test.js']},
    'installable': True,
}
