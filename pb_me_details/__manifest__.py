# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'My details on My Payobook',
    'summary': 'Employees propose changes to their family, ID papers, photo, marital status and bank account; nothing changes until approved',
    'description': """
WDGAP S6-A item 1 — "change my personal details, with approval".

On My Payobook (/my/details) an employee sees all their details in one place
— identity, ID papers, family and bank (masked) — and proposes a change to
any of them. Nothing changes on the record until the change is approved
through the one Approvals inbox; the person sees "waiting", "approved" or
"sent back" with the approver's reason.

FAMILY AND TAX (owner ruling E1). An approved family change never reaches pay
by itself. For a Vietnam company a family member who counts for tax waits as
"waiting for HR to confirm for tax" on People > Family; only HR's one tick
writes the tax dependant record pay reads.

BANK. A bank change goes through the bank-document check (pb_bank_ocr): the
document is read and checked, and ONE second person approves it — never the
person who proposed it (the Updates sheet's bank approvers).

ID PAPERS are approved with their scan: the number is written to the
employee record and the scan is filed in their documents as verified.
""",
    'version': '19.0.1.0.1',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'mail',
        'portal',
        'biz_approval_chain',      # the chain mixin
        'biz_approval_workflow',   # the one approval engine
        'pb_approval_config',      # the catalogue's roles + the one inbox
        'pb_me_portal',            # My Payobook: the hooks, the kit
        'pb_employee_vault',       # ID scans are filed as documents
        'pb_bank_ocr',             # the bank-document check (and VN tax dependants)
        'pb_import_kit',
        'pb_filter_kit',
        'pb_people_hub',           # People > Family (the HR tax tick)
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_me_details_security.xml',
        'data/ir_sequence_data.xml',
        'data/approval_process.xml',
        'views/family_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_me_details/static/src/scss/me_details.scss',
        ],
        'web.assets_backend': [
            'pb_me_details/static/src/scss/family_lens.scss',
            'pb_me_details/static/src/js/family_lens.js',
            'pb_me_details/static/src/xml/family_lens.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
