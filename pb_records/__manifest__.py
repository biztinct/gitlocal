# -*- coding: utf-8 -*-
{
    'name': 'Payobook Records Desk',
    'summary': 'Update the employee, contract and bank details a pay scheme '
               'reads — one person or hundreds at once',
    'description': """
RECORDS phase R2 — the Records Desk.

One spreadsheet-feeling surface over the records a pay scheme actually reads.
The picker offers MAPPED destinations only (the scheme's own
`hr.payslip.import.mapping` rows plus its contract components), because a field
the scheme does not read is a field changing it cannot change the pay.

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
""",
    'version': '19.0.1.1.0',
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
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/pb_records_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_records/static/src/scss/records_desk.scss',
            'pb_records/static/src/js/records_cells.js',
            'pb_records/static/src/js/records_grid.js',
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
    'installable': True,
    'application': False,
    'auto_install': False,
}
