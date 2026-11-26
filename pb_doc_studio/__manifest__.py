# -*- coding: utf-8 -*-
{
    'name': 'Payobook Document studio',
    'summary': 'Design the wording, languages and page of every letter',
    'description': """
Document studio foundation (DOCSTUDIO programme, phase F).

One place in Settings where HR designs every letter the letter engine makes
(`pb.letter.template` / `pb.hr.letter`): a three-pane designer with field
chips, "Show only when..." paragraphs, a live preview with a real person,
one wording per language, page design (letterhead, margins, font, size,
signatory) and copies of a letter for a company and/or countries of work
that every caller then uses.

Nothing changes for a letter until somebody edits it in the studio: an
untouched letter renders byte for byte as before (rail R1). Silent install:
no data written to existing letters, no job, no mail.
See docs/handovers/docstudio/DOCSTUDIO_F_REPORT.md.
""",
    # 1.4.1: Learn anchors (data-coach) for the DOCSTUDIO lessons, no behaviour change.
    'version': '19.0.1.4.1',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_lifecycle owns the letter engine and already brings pb_hub (palette),
    # pb_settings (the Settings hub), pb_import_kit (tokens, icons) and
    # pb_employee_vault (filing). Form builder fields, contracts and pay are
    # probed at run time — never a hard dependency.
    'depends': ['web', 'hr', 'mail', 'pb_lifecycle'],
    'data': [
        'security/ir.model.access.csv',
        'security/doc_studio_security.xml',
        'report/doc_report.xml',
        'views/doc_studio_actions.xml',
        'views/letter_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_doc_studio/static/src/scss/doc_studio.scss',
            'pb_doc_studio/static/src/js/doc_icons.js',
            'pb_doc_studio/static/src/js/doc_words.js',
            'pb_doc_studio/static/src/js/doc_editor.js',
            'pb_doc_studio/static/src/js/rule_builder.js',
            'pb_doc_studio/static/src/js/doc_studio.js',
            'pb_doc_studio/static/src/js/settings_card.js',
            'pb_doc_studio/static/src/js/doc_palette.js',
            'pb_doc_studio/static/src/xml/doc_editor.xml',
            'pb_doc_studio/static/src/xml/rule_builder.xml',
            'pb_doc_studio/static/src/xml/doc_studio.xml',
        ],
        'web.report_assets_common': [
            'pb_doc_studio/static/src/scss/report_fonts.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
