{
    'name': 'Change pay',
    'summary': 'Compare a pay change and send it for approval with its start date.',
    'version': '19.0.1.0.0',
    'author': 'Payobook',
    'license': 'LGPL-3',
    'depends': ['pb_pay_builder', 'pb_job_change', 'pb_contracts'],
    'assets': {'web.assets_backend': ['pb_pay_builder_change/static/src/js/change_pay.js',
                                      'pb_pay_builder_change/static/src/xml/change_pay.xml']},
    'auto_install': True,
    'installable': True,
}
