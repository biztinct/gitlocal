# -*- coding: utf-8 -*-
{
    'name': 'Payobook Records Desk',
    'summary': 'Review and update master records independently of payroll',
    'description': """
A spreadsheet interface for employee, contract, compensation and bank records.
Master records is available without payroll configurations or mappings.
Optional scheme views narrow the catalogue to a payroll configuration.
All changes retain record permissions, review, approval and audit history.

What it is:

  * `pb.records.desk` — an AbstractModel RPC facade. It reads and writes through
    the SAME helpers the import batch uses (`_mapped_record_value`,
    `_coerce_mapped_value`, `_get_latest_contract`, the bank assembly and the
    contract-advantage helpers), on a `.new()` probe of
    `hr.payroll.import.batch`, so the desk and an import can never disagree
    about what a mapped field means.
  * `pb.records.apply` / `pb.records.change` — one audit row per apply and one
    per written value, with the before and after as JSON. That is what makes
    Undo possible, and what makes it honest: a value somebody else changed since
    is reported and left alone rather than overwritten.

Safety rails, all of them tested:

  * nothing is written before Apply, and Apply re-validates server-side;
  * a field id the scheme does not map raises before any write (the whitelist
    rail);
  * every search and every write is scoped to the active companies;
  * the ACL of the model being written is checked, and a refusal is a sentence
    rather than an access dialog;
  * `hr.payslip` is never touched.

Contract fields are written IN PLACE on the person's current contract — no new
contract version. That is an owner ruling (2026-08-29), not a shortcut.

RECORDS phase R3 adds the round trip. `export_records` writes the current view
as an `.xlsx` — the same columns, the same values in the same words, a hidden
`_payobook` sheet and a header comment per column carrying the technical
identity so a retyped heading still lands on the right field. `import_peek`
reads such a file (or any `.xlsx`/`.csv` whose headings match) and answers what
it WOULD do, through `preview_changes`; applying it is `apply_changes` with
`source='import'` — the same whitelist, the same audit row, the same Undo. A
row that matches nobody is listed and can be bound by hand; it is never turned
into an employee. A blank cell is left alone, never treated as a clear.

RECORDS phase R4 is the defect round: the review drawer folds a change that
lands on three or more people into one counted row, the drawer's footer keeps
clear of the floating helpers other modules pin to the same corner, the header's
export/import controls fold into one File menu under 1440px, and a dropped file
says how many rows it is matching while it matches them.

UPDATES P1 adds two read-only seams for the Updates front door (`pb_updates`):
`import_columns` says what each column of a file is and where the desk would
put it, and `import_peek(columns=...)` lets a person's own column matching
replace the desk's five automatic ways. Neither writes; Apply is unchanged.

UPDATES P2a: a typed name for a linked record (department, manager, working
hours) no longer guesses — the current value first, one exact match inside
the companies in use, a department's full path; two records with the name are
refused, and a slashed path never becomes a new record. Look-ups, labels and
component lines are remembered for one call only, which takes a full-roster
review from about 110 s to about 11 s with identical answers.

UPDATES P2c: a change can carry a start date. A past date is written now and
recorded as starting that day (nothing is recalculated); a future date is
approved as usual and then held as "Scheduled" until an hourly job writes it
on the day, through the same all-or-none write. "Start now" writes it early;
"Cancel" stops a change that has not been written (and an Undo pressed on one
now cancels it for real). A manager or coach can be typed as a name, an
employee code or a work email; a name that matches nobody is refused, never
created. A pay run's preparation mentions a scheduled change that starts
inside its pay period.

UPDATES P3a: one proposal is split into lanes — personal details, pay and
contract, bank details. Bank details travel their own approval route and are
never approved by the person who proposed them (a second person, always,
whatever the records route says). Through Updates, personal details apply at
once where the company's records route is the shipped one or "No approval
needed" (a company switch turns that off); a route a company set up itself is
always followed.

UPDATES P3c: the platform's own support login and demo-role logins are never
asked to approve a bank-details change and can never approve one, whatever
seat or group they hold; a bank route that names its approvers is never
widened to Finance or the records managers.
""",
    'version': '19.0.1.10.1',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'om_hr_payroll',
        'pb_hr_payroll_base',
        'pb_hr_payroll_formula',
        'pb_import_kit',
        'pb_people',
        'pb_people_hub',
        'biz_approval_workflow',
        # FILTER W6: WHO is the shared filter panel
        'pb_filter_kit',
    ],
    'data': [
        'security/records_groups.xml',
        'security/ir.model.access.csv',
        'security/records_approval_rules.xml',
        'views/pb_records_action.xml',
        'data/records_cron.xml',
        'data/records_bank_process.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_records/static/src/scss/records_desk.scss',
            'pb_records/static/src/js/records_cells.js',
            'pb_records/static/src/js/records_grid.js',
            'pb_records/static/src/js/records_review.js',
            'pb_records/static/src/js/records_import.js',
            'pb_records/static/src/js/records_desk.js',
            'pb_records/static/src/js/records_palette.js',
            'pb_records/static/src/xml/records_desk.xml',
        ],
        # Loaded only by /web/tests — never part of the backend bundle.
        'web.assets_unit_tests': [
            'pb_records/static/tests/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
