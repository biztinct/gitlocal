# Records Desk column order — 15 October 2026

Records Desk columns can now move to first, left, right or last from their
column-actions menu. This includes Person, Code and Department: Employee Id
can be the first visible column after the selection checkbox. The first column
stays pinned while the other columns scroll horizontally.

The layout is remembered per payroll configuration in the browser. Existing
picked fields are preserved. Reordering preserves the focused/editor field,
staged edits, selection and undo history by field identity. It needs no record
write or server round trip. Picked fields also follow the new order in Excel
exports; the export's three mandatory matching columns remain at the front.

Implementation: `3771484d2`; menu positioning: `0c7622589`; browser-test timing:
`48101c8c6`. Module `pb_records` is `19.0.1.5.0`.

## Deployment

Upgraded payobook first, checked its deployed browser suite and live Records
Desk, then upgraded rize, payobook_template, abm and p0clone on Payobook19v2.
All five databases report installed version `19.0.1.5.0`. The shared addons
directory is `/odoo/odoo-server/addons`.

The branch was rechecked before deployment. All 4,662 deployed custom files
match the combined local working tree byte for byte, including concurrent
biz_mail_debrand work; that work and unrelated workbook deletions were excluded
from these commits. Standard Odoo addons and undeployed modules were not
overwritten.

The existing MEHOME/Import Kit per-database upgrade gate in PENDING.md remains
pending. The Singapore payroll configuration rollout also remains gated on
the owner's approval. This rollout changes Records Desk only.

Database dumps, previous Records Desk files, original cron states and upgrade
logs are retained at `/odoo/backups/records-columns-20261015-3771484d2` with
restricted permissions. Original cron states match in all five databases;
ABM has zero active scheduled jobs. The Odoo service is active.

## Verification

- JavaScript syntax, XML parsing and whitespace checks pass.
- Local behavioral checks pass for order restoration, focus/editor identity,
  staged values, paste and undo.
- Deployed Chrome HOOT suite: **51 passed, 0 failed**, using the exact filter
  `"@pb_records"`. Four new regressions cover moving Employee Id ahead of
  Person, preserving edits and paste targets, restoring layouts and moving
  identity columns with boundary controls. The initial two new menu tests
  needed an animation-frame wait before clicking the newly rendered menu;
  they pass after that correction. An earlier fuzzy filter also selected an
  unrelated core tag-label test affected by uppercase styling; the final run
  uses the exact module filter.
- Chrome live checks pass on payobook and Rize: Employee Id moves to first,
  survives reload and matches the correct row's Code. Rize's existing seven
  picked fields are preserved. Nothing is staged for review.
- Rize horizontal scrolling: scrollLeft changes from 0 to 597 px while the
  first column's left edge remains at 609 px.
- Rize's blank Excel export follows both tested picked-field orders. Header
  identity comments and hidden metadata preserve the correct field ids in
  both orders; importing each blank export reports an empty file. These
  checks run read-only and roll back; no employee or payroll values are
  changed.
- Browser images were inspected in memory; no test PNG or screenshot files
  were written. Temporary staging and upgrade-log files were removed after
  verification.

## Monthly payroll clarification

Time and monthly variable amounts belong in the workbook uploaded during Pay
Run. Two worksheets are optional. A single sheet containing both is supported
by the existing country templates. Separate Time and Monthly Adjustments tabs
would require matching country-specific source bindings and deployed tests
before replacing those templates. Fixed salary, recurring allowances and
employee/contract changes can use Records Desk when they change; one-off
payments and deductions should be supplied for the current run.
