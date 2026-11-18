# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Tax details on My Payobook',
    'summary': 'Employees see their tax details and propose changes with proof; nothing changes until HR approves',
    'description': """
WDGAP Step 2, phase S2-D (owner ruling G4).

On My Payobook (/my/tax) an employee sees the tax details their company keeps
for the country of the scheme that pays them — Vietnam, Indonesia, India,
Singapore — and proposes a change with a proof file. Nothing changes on the
employee record until HR approves it in the one Approvals inbox (the
"My details changes" route of pb_me_details); then exactly what was proposed
is written and the proof is filed in the person's documents, verified.

Vietnam: personal tax code; the tax dependants and their state (the family
flow of My details, not duplicated). Indonesia: NPWP (or the NIK used as
NPWP), PTKP status, BPJS numbers (view only). India: PAN, tax regime, UAN
(view only). Singapore: NRIC/FIN (masked) and tax residency (view only),
self-help group fund.

Nothing here changes a payslip. Each approved detail is a registered source
a pay scheme CAN read; no existing scheme is wired to any of them. For
Vietnam, HR sees a read-only "does not match" note when the dependants HR
confirmed differ from the contract's registered-dependants component, which
is never changed here.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_me_details',           # the request model, its route, the portal kit
        'pb_employee_vault',       # NPWP / BPJS fields, documents, Full details
        'pb_hr_payroll_formula',   # scheme country, application sources
    ],
    'data': [
        'data/document_category.xml',
        'views/portal_templates.xml',
        'views/hr_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_me_tax/static/src/scss/me_tax.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
