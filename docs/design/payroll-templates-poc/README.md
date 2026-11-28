# Payroll templates design preview

An interactive proof of concept in Payobook's existing Inter, indigo, navy,
white-card and semantic-status style. It uses fictional data only, processes
workbooks in the browser and makes no payroll API calls.

The entry point is a **Templates** action on each payroll configuration card.
The configuration-specific workspace includes Downloads, Monthly layout and
Import history. Pay Run links to the same monthly workbook.

- Employee workbook: existing sample details, salary and fixed allowances;
  Employee ID and email are locked and validated on import. Blank editable
  cells are ignored; numeric 0 is an explicit update.
- Monthly workbook: exactly two visible worksheets, Time and Monthly
  adjustments. Both include Employee ID and name. Downloads show only the
  selected month's values. New months suggest working days and leave paid
  days and one-off adjustments blank.
- Layout: drag and drop within or between worksheets; keyboard-accessible
  field menus offer the same moves. Optional saved context is read-only.
  Layouts are remembered independently for Vietnam, India, Indonesia and
  Singapore in the browser. A visible draft must be saved before it becomes
  the download layout.
- Review: current and incoming values, selected changes, ignored blanks,
  explicit zeros, duplicate/missing identities, month/layout mismatches and
  stale-record conflicts. The latest values are rechecked before applying.
  Applying changes updates the fictional preview and creates a receipt.
- Excel downloads are real .xlsx files with frozen identity columns, styled
  headings, unlocked editable cells, protected identities and hidden metadata.
  Sheet protection prevents accidental edits; authoritative import validation
  also blocks identifier changes.

## Build and checks

    node docs/design/payroll-templates-poc/tests/run.mjs
    node docs/design/payroll-templates-poc/build.mjs

The build produces the self-contained file
docs/design/payroll-templates-poc.html. It works without external fonts, scripts
or services. Inter's OFL and SheetJS's Apache 2.0 licenses are included here.
SheetJS 0.20.3 was obtained from the vendor's official CDN.

Commit the latest bundle and nginx fragment before deployment:

    python3 docs/design/payroll-templates-poc/deploy.py

The deployment preserves the existing payobook.com nginx configuration,
backups the previous route and preview, checks nginx, and reloads it. It does
not restart Odoo or modify any database. The route is
https://payobook.com/preview/payroll-templates/.

## Recommended production behavior after design review

Keep existing Records Desk and payroll import services as the write paths.
Add a small configuration-owned template layout and explicit ownership for
each input: recurring record, monthly quantity, monthly amount, or read-only
context. Infer defaults from component metadata, units, bindings and names;
ask for a review of ambiguous classifications. Moving a field changes its
worksheet and order, never its earnings/deduction treatment.

Employee imports must resolve existing employees within the active company
and configuration; identity columns cannot be written. Export an authenticated
snapshot reference rather than trusting workbook metadata. Apply selected
changes atomically after a server-side comparison with current values, using
the existing Records Desk permissions, approval workflow, audit and undo.
Blank means no change; 0 is a numeric value. Clearing text or dates should use
an explicit reviewed action rather than interpreting blanks as deletion.

Monthly values need storage keyed by company, configuration, employee and pay
period. Patch only supplied nonblank cells; blank retains that same month's
value, and 0 overwrites it. Never fall back to the previous month's amounts.
The Time worksheet is the pay-run roster; adjustment rows must match it.
Reject duplicate identities, unknown people, mismatched periods and obsolete
layouts before applying. Recheck paid-day coverage and mandatory inputs before
Compute, and preserve the existing payroll approval workflow.

Use current record data for recurring salary and allowances at payroll time.
Optional context exported in monthly workbooks is read-only and does not
override stored records. Calendar values are suggestions, not confirmed
attendance. Proration, statutory calculations and component treatment remain
the configuration's existing rules. Singapore CPF and self-help amounts
remain reviewed monthly inputs, as agreed.

The current preview demonstrates these interactions. Production mappings,
database storage, permissions, approvals and payroll calculations await design
approval and their implementation and deployed tests.
