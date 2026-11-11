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

Phase 2b: pay items are judged against each person's own pay scheme
(worked out by the scheme map, the pay run's own resolver); a value for a
pay item that is not in that person's scheme is greyed out and skipped.
A cell saying CLEAR empties that value.

Phase 2c: an update can carry a start date — for the whole file, or per row
from a start-date column. A past date is written now and recorded as starting
that day (finished pay runs are not recalculated, no back pay); a future date
is held as "Scheduled" and written on the day, with "Start now" and "Cancel"
on the Updates home. A manager or coach can be given by name, employee code
or work email.

Phase 2d: a second kind of sheet, "One-off pay items for a pay month" — a
bonus, a one-time deduction, an overtime amount — entered any day before the
pay run exists, approved like any records change, read by every kind of pay
run (with or without a pay data file, and monthly-template runs; not runs from
application data, which say so), paid once and released when the payslip or
run is cancelled or deleted. When the pay data file carries a different
amount for the same person, item and month, the pay run stops and asks.

UPDATES programme, phases 1-2d. Ledger: docs/handovers/updates/UPDATES_LEDGER.md.
""",
    'version': '19.0.1.3.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'pb_records',
        'pb_people_hub',
        'pb_import_kit',
        # UPDATES P2b: each person's pay scheme comes from the scheme map
        # (`pb.scheme.map.resolve_many`). Installed on every live database.
        'pb_scheme_map',
        # UPDATES P2d: one-off pay items are read by every kind of pay run —
        # the Run Payroll screen (and its pay data files) and monthly
        # templates. Installed on every live database.
        'pb_payrun_wizard',
        'pb_payroll_templates',
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
            # UPDATES P2d — one line and the D11 choice on the Run Payroll screen.
            'pb_updates/static/src/js/payrun_oneoff.js',
            'pb_updates/static/src/xml/payrun_oneoff.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
