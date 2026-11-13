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

UPDATES P3a: a file is split into three lanes — personal details (applied at
once where the company allows it), pay and contract (the records approval
route) and bank details (always a second person). A manager or coach whose
login is employee self-service only can be named without their login
changing. Every pay data file a person uploads for a pay run is used for that
run only. The old employee import is retired; its doors open Updates. The
demo pay runs on the demo database read one-off pay items from Updates.

UPDATES P3b: rows that match nobody can be added as new employees with a
first contract — only when switched on for that file, and only through the
existing new-hire path and its approval; a "Pay scheme" column is a check
against the team. An unfinished update is saved as a private draft and can be
continued or discarded from the Updates home. A pay run's "Review pay data"
says which people had changes since their last finished pay run.

UPDATES P4: a third kind of sheet, "Leave opening balances" — many people's
balances as at one date, in the same four steps, with drafts, history and
approval on the records route. Where a person is on an absence policy the
balance is written only through that policy's own opening-balance step;
otherwise as one approved allocation. A balance is set once per person and
leave type; undo takes back only what nothing has been taken against. The
Start screen also carries a tile to the existing attendance file screen.

UPDATES P5: a fourth kind of sheet, "Year-to-date figures before Payobook"
— what each person was paid and taxed this tax year before the company
started on Payobook, approved on the pay route and kept in one store. A
year-to-date view shows before Payobook + paid in Payobook = total per
person, with a download; the employee's own tax summary includes them. A pay
run receives a figure only where a payroll manager has chosen which input pay
item of a scheme gets it; a run from application data gets a "Download for
the pay run" sheet instead. No tax calculation is changed.

UPDATES programme, phases 1-5. Ledger: docs/handovers/updates/UPDATES_LEDGER.md.
""",
    'version': '19.0.1.7.4',
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
        # UPDATES P3a (D1): the guided "Load Pay Data" screen carries the
        # month-only line. Already in this module's dependency tree on every
        # live database (through pb_import).
        'pb_import_wizard',
        # UPDATES P3a: the old employee import's doors lead to Updates.
        'pb_hr_payroll_base',
        # UPDATES P3b: new employees from a sheet go through the existing
        # new-hire path (`pb.people.onboard.wizard.create_employee`) and its
        # approval. Installed on every live database.
        'pb_people_advanced',
        # UPDATES P4: leave opening balances are written as time-off
        # allocations. Installed on every live database. The leave policy
        # layer (pb_timeoff) is reached by soft checks only.
        'hr_holidays',
        # UPDATES P5: the employee's own tax summary (/my/taxsheet) shows the
        # year-to-date figures before Payobook — a small controller and
        # template override. Installed on every live database.
        'pb_me_portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/updates_rules.xml',
        'views/updates_action.xml',
        'views/ytd_portal.xml',
    ],
    'assets': {
        # UPDATES P5d (D29) — the employee tax summary's mid-month advance pill.
        'web.assets_frontend': [
            'pb_updates/static/src/scss/ytd_portal.scss',
        ],
        'web.assets_backend': [
            'pb_updates/static/src/scss/updates_desk.scss',
            'pb_updates/static/src/js/updates_review.js',
            'pb_updates/static/src/js/updates_desk.js',
            'pb_updates/static/src/xml/updates_desk.xml',
            # UPDATES P2d — one line and the D11 choice on the Run Payroll screen.
            'pb_updates/static/src/js/payrun_oneoff.js',
            'pb_updates/static/src/xml/payrun_oneoff.xml',
            # UPDATES P3a (D1) — the month-only line on the pay-file screens.
            'pb_updates/static/src/js/monthonly.js',
            'pb_updates/static/src/xml/monthonly.xml',
            # UPDATES P3b — "Since the last pay run" on Review pay data.
            'pb_updates/static/src/js/payrun_since.js',
            'pb_updates/static/src/xml/payrun_since.xml',
            # UPDATES P5 — year-to-date figures: the view and its set-up.
            'pb_updates/static/src/js/updates_ytd.js',
            'pb_updates/static/src/xml/updates_ytd.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
