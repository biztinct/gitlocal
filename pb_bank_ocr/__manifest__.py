# -*- coding: utf-8 -*-
{
    'name': 'Bank Account Verification (OCR)',
    'summary': 'AI/OCR bank-document extraction, validation, and approved master update',
    'description': """
Sudima Phase D — AI Bank Account Validation (#3).

Upload a bank document (confirmation letter / statement / passbook / cheque) →
AI vision OR offline OCR extracts the bank, branch, holder, account number, IBAN
and SWIFT → a deterministic VN layer normalizes the bank, recovers the account
number from prose, scores name similarity (stdlib difflib, diacritic-folded) and
flags duplicates → Employee → HR → Finance approval → an ATOMIC write to the
employee master with full version history.

Never auto-writes the master: extraction and validation are advisory; only the
finance-tier approval writes the four vietnam_bank_* fields, via a
context-flagged path, in one transaction, with a history row. A direct edit on
the employee logs a 'manual' history row.
""",
    'version': '19.0.1.0.3',
    'category': 'Human Resources',
    'post_init_hook': '_add_finance_reviewer_groups',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'biz_doc_ocr',
        'biz_approval_chain',
        'pb_hr_payroll_vietnam',
        'pb_sidebar',
        'pb_import_kit',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_bank_ocr_security.xml',
        'data/ir_sequence_data.xml',
        'data/vn_bank_registry_data.xml',
        'views/pb_bank_ocr_views.xml',
        'views/pb_bank_ocr_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_bank_ocr/static/src/scss/pb_bank_ocr.scss',
            'pb_bank_ocr/static/src/js/pb_bank_ocr.js',
            'pb_bank_ocr/static/src/xml/pb_bank_ocr.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
