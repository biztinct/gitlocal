# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Certificates on My Payobook',
    'summary': 'Employees ask for an employment certificate (at once, as a PDF) or a salary certificate (after one HR click)',
    'description': """
WDGAP S6-A item 2 (owner ruling E2).

On My Payobook (/my/certificates) an employee asks for:
  * an EMPLOYMENT certificate — no pay figures — which comes out at once as a
    PDF;
  * a SALARY certificate — their agreed monthly salary — which waits for one
    HR click in the Approvals inbox; the employee is then told on their home
    page and downloads it.

Every certificate is numbered, filed in the employee's documents and logged.
The letters are printed by the letter engine (pb_lifecycle), by inheritance
only: two letter kinds added to the letter library, the company's own
wording wins when it has one. The figures are worked out by the server;
nothing the employee types reaches the letter except the purpose they chose.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'mail',
        'portal',
        'om_hr_payroll',           # contracts (the agreed wage) and payslips
        'biz_approval_chain',
        'biz_approval_workflow',
        'pb_approval_config',
        'pb_employee_vault',       # every certificate is filed as a document
        'pb_lifecycle',            # the letter engine (inherited, never edited)
        'pb_me_portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_me_letters_security.xml',
        'data/ir_sequence_data.xml',
        'data/approval_process.xml',
        'data/letter_template_data.xml',
        'views/certificate_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_me_letters/static/src/scss/me_letters.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
