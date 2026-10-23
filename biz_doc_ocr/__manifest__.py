# -*- coding: utf-8 -*-
{
    'name': 'Document OCR Engine',
    'summary': 'Generic schema-driven document field extraction (vision + OCR) with retry',
    'description': """
Sudima Phase D — the generic half of AI Bank Account Validation (#3).

A reusable, product-neutral document extraction service (biz.doc.ocr) that
resolves a purposed AI provider from pb_payroll_ai_insights, builds a strict-JSON
prompt from a caller-supplied field schema, calls the provider's vision method,
and normalizes the result to {fields:{name:{value,confidence}}, doc_kind,
raw_text, provider}. A deterministic post-processor callable always runs last
(the no-AI fallback / normalization layer). biz.doc.ocr.job wraps a run for a
*/5-min retry cron. Ships a DocDrop drag-drop upload widget (--bdo-* props, zero
Payobook deps). Reusable for invoices, ID cards, contracts — the bank overlay is
pb_bank_ocr.
""",
    'version': '19.0.1.0.3',
    'category': 'Tools',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['base', 'web', 'pb_payroll_ai_insights'],
    'data': [
        'security/ir.model.access.csv',
        'security/biz_doc_ocr_security.xml',
        'data/cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_doc_ocr/static/src/scss/doc_drop.scss',
            'biz_doc_ocr/static/src/js/doc_drop.js',
            'biz_doc_ocr/static/src/xml/doc_drop.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
