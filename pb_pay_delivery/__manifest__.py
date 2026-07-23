# -*- coding: utf-8 -*-
{
    'name': 'Pay & Deliver',
    'summary': 'Real bank payment files (data-driven layouts) + password-PDF payslip delivery',
    'description': """
Sudima Phase F — Pay & Deliver (#15 Bank Payment Processing + #16 Payslip Distribution).

The run is approved → the money files and the payslips go out, from one bespoke
full-screen experience on the Pay Runs cockpit:

  * Money out  — real per-bank transfer files. Bank layouts are DATA records
    (pb.bank.file.layout + pb.bank.file.column): 7 banks seeded (Vietcombank,
    BIDV, Techcombank, MB, VietinBank, ACB, generic). Adding a bank is a data
    file, zero code. Every row is validated (account_ok + registry match +
    holder) BEFORE generation — a failing row is never silently dropped, it is
    surfaced in an exclusion drawer with a reason.
  * Payslips out — themed PDF, password-protected per employee (pattern from
    config; resolved in memory, never logged or stored), attached to a mail
    template, queued to mail.mail with a per-slip delivery log and one-click
    resend of failures.

Reads the employee master (vietnam_bank_*); never writes it — the only master
write path stays pb.bank.change.request._apply_to_master.
""",
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'om_hr_payroll',
        'pb_hr_payroll_vietnam',
        'pb_hr_payroll_formula',
        'pb_bank_ocr',
        'pb_import_kit',
        'pb_sidebar',
    ],
    'data': [
        'security/pb_pay_delivery_security.xml',
        'security/ir.model.access.csv',
        'data/bank_file_layouts.xml',
        'data/mail_template.xml',
        'views/pb_pay_delivery_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_pay_delivery/static/src/scss/pb_pay_delivery.scss',
            'pb_pay_delivery/static/src/js/pb_pay_delivery.js',
            'pb_pay_delivery/static/src/xml/pb_pay_delivery.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
