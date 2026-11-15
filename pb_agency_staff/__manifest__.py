# -*- coding: utf-8 -*-
{
    # The opening line of this description is what the Apps list prints, so
    # it is a USER-VISIBLE string (ledger GR7, TIDY T10).
    'name': 'Payobook Agency Staff',
    'summary': 'People an agency supplies, kept apart from your employees and '
               'never in a pay run',
    'description': """
A light record for each person an agency supplies: name, agency, site, team,
manager, dates, role, notes and documents. They have their own list under
People and are shown as a separate figure beside the headcount ("+ 12 agency
staff").

They are NOT employees: there is no employee record, no contract and no login,
so they can never be put in a pay run, get a payslip or clock in.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'pb_import_kit',
        'pb_filter_kit',
        'pb_hub',
        'pb_people',          # the headcount line the separate figure sits beside
        'pb_people_hub',      # the "Agency staff" lens
        'pb_vendor_access',   # the agency is a vendor in the register
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/agency_staff_security.xml',
        'views/agency_staff_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_agency_staff/static/src/scss/agency_staff.scss',
            'pb_agency_staff/static/src/js/agency_staff.js',
            'pb_agency_staff/static/src/js/agency_staff_patches.js',
            'pb_agency_staff/static/src/xml/agency_staff.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
