# -*- coding: utf-8 -*-
{
    'name': 'Payobook Updates',
    'summary': 'Update many people at once from one spreadsheet, reviewed first and undoable',
    'description': """
People › Updates — the front door for bulk spreadsheet changes.

Download a ready-to-fill sheet, or upload a file of your own with your own
headings; match the columns once (remembered per company); review every change
as before → after in a person × column grid and fix problems on screen; name the
update and apply it; find it again in Past updates with the original file kept,
and undo it.

It is NOT a second write engine. Every value is evaluated, written, audited,
routed for approval and undone by the Records Desk (`pb.records.desk`, module
`pb_records`), through `import_peek`, `preview_changes`, `apply_changes` and
`undo_apply`. This module adds the guided screens, the column memory
(`pb.updates.layout`) and the named batch (`pb.updates.batch`) that groups an
apply with the file it came from.

UPDATES programme, phase 1. Ledger: docs/handovers/updates/UPDATES_LEDGER.md.
""",
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'pb_records',
        'pb_people_hub',
        'pb_import_kit',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/updates_rules.xml',
        'views/updates_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_updates/static/src/scss/updates_desk.scss',
            'pb_updates/static/src/js/updates_review.js',
            'pb_updates/static/src/js/updates_desk.js',
            'pb_updates/static/src/xml/updates_desk.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
