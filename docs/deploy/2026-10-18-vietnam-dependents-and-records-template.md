# Vietnam dependents and three-tab payroll templates

The owner approved importing the Dependent worksheet by normalized employee name,
creating five missing inactive Employee profiles as archived records, and using
all imported dependent records for both Dependent/Children (VNHCQ) and Registered
tax dependents (VNREGISTER). Eligibility dates and registration evidence are not
in the source; imported detail records remain Pending, without invented dates or
allowances. The payroll count policy is the owner's explicit instruction, separate
from the native eligible-dependent status.

`tools/import_rize_vietnam_dependents.py` is an idempotent Odoo-shell migration.
Its private JSON source/receipts are outside Git. Dry-run is the default; apply
and archived-profile creation require separate explicit environment flags. The
placeholder row is skipped. Unique normalized/accent-folded names determine the
parent; duplicate names require the VN dependent count and that row's identity.
Source Country-Based IDs identify newly archived profiles. Two old Employee IDs
are already used by different existing people, so those IDs are left blank rather
than reassigned. No contracts or payroll assignments are created.

A visible Guided Count transformation, Dependents count / VNDEPCOUNT, reads the
current Employee dependent relationship at calculation time. Both payroll inputs
are mapped to that output and the read-only native dependent count. All eleven
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
selection/order parity, all 43 dependent records, both payroll counts for every
matched employee, and an entirely tampered master sheet ignored on monthly review.
Local placement/restriction checks, Python/XML syntax and diff checks passed.

Deployment scope: latest combined custom addons on Payobook19v2 and all five
currently existing application databases: payobook, rize, payobook_template, abm,
p0clone. The former lrp4clone database is no longer present. Back up each database
and the shared addon tree, upgrade the three changed installed modules, preserve
business aggregates and existing cron activation, refresh assets, then test the
deployed application and Chrome flows. Source/receipts remain private.
