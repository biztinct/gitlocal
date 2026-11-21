# Rize department consolidation

The premium Job lookup exposed existing October department duplicates. Rize had
209 active departments, representing 32 exact translated-name/company/parent
keys. Twelve keys had duplicates; the 177 redundant records have identical
business metadata, no department managers, parent departments or cost centres.
Similar names such as “Carbon & Innovation” and “Carbon & Innovations” remain
separate. Existing shared departments span countries; this repair does not
introduce a new country hierarchy.

`tools/consolidate_rize_departments.py` uses the explicit dated JSON plan and
runs in a single serializable transaction. Dry-run is the default. It archives
redundant departments, retaining their IDs, original metadata and chatter. It
remaps existing foreign keys, verifies every non-department field unchanged,
and refuses unreviewed dependencies or numeric department access rules.

Auto-generated budget rows with the same resulting department/month/type are
consolidated, with exact per-currency/month totals and headcounts preserved.
Only generated rows with no forecast, scenario, reference or conversation are
eligible. Complete before-images and the ID map are saved with the permanent
Rize backup. Payslips, payslip lines, contracts, employee master records and
payroll scheme assignments are hashed before/after and must remain identical.
Employee version IDs, effective dates, managers and job titles remain unchanged.

Rehearsal must verify native department lookup, repeated import name resolution,
and that the budget actuals refresh produces no change after consolidation.
Existing import lookup already resolves departments by name; this repair does
not add a global uniqueness rule to other tenants or merge future records
silently. New differently scoped departments should use the appropriate
company/parent hierarchy.

The accompanying Form builder stylesheet makes read-only Job field values use
the same dark 600-weight typography as the premium Workplace summary. Links
retain click behaviour and hover colour; empty values and labels remain muted.
