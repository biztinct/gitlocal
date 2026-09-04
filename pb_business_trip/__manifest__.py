# -*- coding: utf-8 -*-
{
    'name': 'Business Trips',
    'summary': 'Business-trip requests, multi-tier approval, and virtual attendance presence',
    'description': """
Sudima Phase C — Business Trip Management (#6) + Attendance Integration (#7).

Employees (or HR on their behalf) raise a trip request — destination, purpose,
timeline, estimated costs, cash advance — through a 4-tier approval chain
(Employee → Manager → Finance → HR → Authorized), driven by the generic
biz_approval_chain engine and shown as a live stepper.

During an authorized trip the employee is automatically "Business Trip
(Present)": a VIRTUAL overlay injects indigo trip bars into the Timecards Gantt,
locks the Weekly Entry REG cell, and counts the traveller as present on the
Workforce dashboard — with NO materialized hr.attendance rows (C18.4).

Money flows land through two thin bridges (kept OUT of this core so it installs
without payroll or hr_expense): per-diem/trip-days → formula inputs
(pb_trip_payroll_bridge), and receipted lines → draft expenses
(pb_trip_expense_bridge). Per-diem is paid via payroll XOR expense, never both.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'mail',
        'biz_approval_chain',
        'pb_sidebar',
        'pb_import_kit',
        'pb_hr_workforce',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_business_trip_security.xml',
        'data/ir_sequence_data.xml',
        'data/pb_trip_expense_category_data.xml',
        'data/pb_trip_policy_data.xml',
        'views/pb_business_trip_views.xml',
        'views/pb_trip_policy_views.xml',
        'views/pb_trips_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_business_trip/static/src/scss/pb_trips.scss',
            'pb_business_trip/static/src/scss/trip_composer.scss',
            'pb_business_trip/static/src/js/pb_trips.js',
            'pb_business_trip/static/src/js/trip_composer.js',
            'pb_business_trip/static/src/xml/pb_trips.xml',
            'pb_business_trip/static/src/xml/trip_composer.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
