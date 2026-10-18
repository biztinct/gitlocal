# Vietnam dependents and three-tab payroll templates

The owner approved importing the Dependent worksheet by normalized employee name,
creating five missing inactive Employee profiles as archived records, and using
the imported detail count for Dependent/Children (VNHCQ). Registered tax dependents
(VNREGISTER) remains a separate verified contract setting under the owner's final choice. Eligibility dates and registration evidence are not
in the source; imported detail records remain Pending, without invented dates or
allowances. Pending imported details do not populate the registered-tax count.

`tools/import_rize_vietnam_dependents.py` is an idempotent Odoo-shell migration.
Its private JSON source/receipts are outside Git. Dry-run is the default; apply
and archived-profile creation require separate explicit environment flags. The
placeholder row is skipped. Unique normalized/accent-folded names determine the
parent; duplicate names require the VN dependent count and that row's identity.
Source Country-Based IDs identify newly archived profiles. Two old Employee IDs
are already used by different existing people, so those IDs are left blank rather
than reassigned. No contracts or payroll assignments are created.

A visible Guided Count transformation, Dependents count / VNDEPCOUNT, reads the
current Employee dependent relationship at calculation time. Only Dependent/Children
is mapped to that output and the read-only native dependent count. Registered tax
dependents retains its separate contract amount component and existing values. All eleven
Recurring settings Excel placeholder bindings, including VNREGISTER's Excel
binding, remain present. All seventeen monthly bindings remain. Sheet4 is unused.

Monthly downloads now have three visible sheets: Time, Monthly adjustments and
Employee records. The third sheet is a fully locked, password-protected snapshot.
Employee, Contract, Contract component and Bank headers/cells use distinct colours,
with an explanatory comment on A1. The server ignores the entire snapshot during
monthly review, even when cells or formulas are altered, or the sheet is deleted.
Calculations refresh current master values from the database.

The layout has three destination lanes plus Available fields. Eligibility follows
actual persisted record mappings, including aliases of the same saved field;
monthly quantities and adjustments cannot enter Employee records. Server validation
and UI menus/drop handling enforce the same rule. Old master-context placements
migrate into the new lane. The separate editable Employee & contract records
workbook uses that lane's field selection/order and the existing review/approval
flow. Monthly pay inputs is the first download card; Employee & contract records
is second. The Records Desk link is removed from that download card.

The approved 70-person source roster is used only as Draft download scope where
Employee records exist: 63 people currently resolve. Seven source people have no
Employee profile and are reported for review. Configuration 4639 stays Draft;
actual payroll activation and assignments are unchanged.

Predeployment checks: 72 isolated workbook/native-transformation tests passed;
an additional saved-field-alias regression passed after the final alias change.
The real configuration on an isolated Rize copy passed three-sheet export,
protection and four-category colour checks, 63-row roster export, standalone
selection/order parity and all 43 dependent records, and an entirely tampered master sheet ignored on monthly review.
Local placement/restriction checks, Python/XML syntax and diff checks passed.

Deployment scope: latest combined custom addons on Payobook19v2 and all five
currently existing application databases: payobook, rize, payobook_template, abm,
p0clone. The former lrp4clone database is no longer present. Back up each database
and the shared addon tree, upgrade the three changed installed modules, preserve
business aggregates and existing cron activation, refresh assets, then test the
deployed application and Chrome flows. Source/receipts remain private.

## Rize-only client-data boundary

The owner clarified that updated application code must be deployed everywhere,
but Rize employee and payroll data must exist only on rize.payobook.com. The
new 43-dependent import, five archived profiles, native count transformation,
Draft configuration and review-roster scope were applied only to rize.

The cross-database audit found two older Draft import-review copies on payobook:
602 (Rize Indonesia) and 613 (Rize Singapore), created 14 October. Neither has
employee assignments, payslips, pay runs or import batches. The scoped cleanup
script `tools/remove_rize_review_copies.py` backs up and removes those definitions,
their source/sample children and attached workbooks. It also removes an older
masked Rize payslip attachment copied to a demo recruitment test, retaining the
demo applicant itself. Employee, contract, payslip and run counts must remain
unchanged. Two common Vietnamese-name matches were created in June and belong
to generic Corporate/IT demo payrolls, without matching Rize IDs or email; they
are not identified as Rize copies and are preserved.

The other application databases have no Rize-labelled payroll configuration,
Rize company, imported dependent rows or VNDEPCOUNT transformation. The isolated
codex_vn_records_20261018 database is temporary test data and must be dropped
before completion. Restricted recovery backups are retained outside live databases.

## Final records-workbook alias correction

Chrome round-trip testing exposed two selected payroll labels referring to one
saved destination. Exports now give each alias a distinct workbook column ID,
while retaining its native write destination in the server-owned snapshot.
Read-only alias cells are checked separately. Matching edits to an editable
destination become one reviewed change; conflicting supplied values are refused.
Existing ordinary column IDs and older valid export receipts remain compatible.
Two staged regressions passed for separate alias columns and conflict handling.
The final Python-only correction is pb_payroll_templates 19.0.1.2.9. It needs no
schema, XML or application-data changes; deploy the combined addon tree, update
installed-version metadata on all five databases and restart the shared service.

The owner's last count-policy change removes the shared VNDEPCOUNT source and
native count-field mapping from VNREGISTER only, restores its contract-amount
flag, and preserves all existing contract values and eleven Excel placeholders.
The import tool is now guarded to run only on rize.
