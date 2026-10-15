# Payroll template workspace — 15 October 2026

Implemented the approved design in `pb_payroll_templates` 19.0.1.0.0 on
**payobook.com / payobook**. The entry point is **Templates** on each payroll
configuration card and in Formula Studio. The native configuration form also
has a Templates button. Pay Run offers the selected month's download and a
link back to the layout. The standalone HTML preview remains a separate POC.

Implementation starts at `a8c6413ae`; final functional/build commit is
`c9725d4e7`. Other sessions' mail, access, portal, onboarding and demo work was
preserved and excluded from these commits. Each deployment re-read the branch
and synchronized the combined custom module tree, excluding the server's own
standard Odoo addons. Final content verification covers 4,683 custom files.

## Behavior

- Employee workbook: current payroll population, standard employee/contract
  fields, mapped details and recurring contract components. Employee ID and
  email are locked and validated; the employee name appears once and is
  editable. Changed values use Records Desk's existing coercion, permission,
  approval, audit and Undo path. No employee import creates a person.
- Monthly workbook: exactly two visible worksheets, **Time** and **Monthly
  adjustments**, with Employee ID and employee name on both. Values come only
  from the selected month's saved inputs or completed imports for that exact
  period. A new month has blank attendance and adjustments. Standard working
  days use the existing pay-run weekday suggestion and need review for holidays
  and policy. Recurring salary/allowances are read fresh from records.
- Layout: suggestions use component types, units, names and record mappings.
  Payroll Managers can drag/reorder fields or use field menus, inspect the live
  preview and save a layout per configuration/company. Saved record context is
  read-only in monthly files. Moving fields does not change formulas, component
  treatment or their original source keys. Manual and connected-system inputs
  are available alongside spreadsheet inputs.
- Import: server-owned download references and per-row tokens validate
  identities and the original snapshot. Blanks are ignored; numeric zero is a
  supplied value. Reviews show selected changes, ignored blanks, unchanged
  values and issues. Duplicate identities, mismatched months/layouts,
  cross-tab omissions, formulas and invalid numbers are refused. Values changed
  since download/review require another review. Confirmation rechecks current
  values and serializes template writes per configuration/company.
- Monthly inputs are stored by company/configuration/employee/period. The run
  adapter joins the two tabs by employee identity and regenerates the input file
  on the server. Original source-key aliases preserve formulas. Old recurring
  record fallbacks cannot replace monthly quantities/adjustments in this path.
  Nothing is written back to employee/contract/bank records by a monthly run.
- An unchanged monthly workbook can continue with current saved inputs.
  Required attendance is checked before computation. Draft/unassigned schemes
  cannot silently open a run on a different active scheme. Template-prefilled
  runs discard a stale demo division so the chosen configuration is preserved.
- Workbooks are .xlsx, at most 10 MB / 10,000 employees. Period exports are
  calendar-month workbooks. Text/date clearing uses Records Desk's explicit edit
  flow; an Excel blank never deletes a value. Import history shows confirmed
  workbook receipts, while employee approvals and Undo remain in Records Desk.

Storage is in three new models, with no direct user ACL; the facade enforces
existing Records Desk and payroll-run abilities, company scope and reference
ownership. Other databases have not installed the module and need no new
columns on existing models. Shared code is present; feature activation on
`rize`, `payobook_template`, `abm` and `p0clone` awaits the owner's rollout.

## Verification

- Python/JavaScript syntax, XML parsing and whitespace checks pass.
- Deployed Odoo suite: **18 passed, 0 failed, 0 errors**. Covers real workbook
  round trips, name edits, locked identities, blank/zero semantics, month
  isolation, duplicate/cross-tab checks, stale layouts/records, source aliases,
  required time, old-record fallbacks, configuration/company scoping and the
  stale-demo-division regression.
- Chrome: opened Templates from a configuration card; verified the connected
  workspace, drag/drop, preview, saved layout and real Excel download/upload.
- Chrome monthly review showed four changes for two fictional employees:
  paid days 22 each, one explicit zero bonus and one bonus of 125. Confirmation
  saved four monthly values and produced an import-history receipt. Reimporting
  blank paid-day/bonus cells showed **0 changes, 2 blanks ignored**.
- Chrome continued an unchanged monthly workbook through Pay Run and computed
  **2 of 2 draft payslips**. Stored formula results were exactly **S$1,000** and
  **S$2,125**; contracted wages remained 1,000 and 2,000. Existing workforce-close
  and connector advisories remained visible. Nothing was approved or paid.
- Chrome employee review showed a salary change with blanks ignored; changing
  Employee ID produced an issue and disabled confirmation. The final employee
  workbook has Employee ID/email protected and one editable Employee Name
  column; a name edit returned one valid change. These employee previews were
  cancelled, so no real approval notifications were submitted.
- A fresh next-month download contained blank attendance and bonuses with
  current saved salary context. Chrome verified the draft Singapore scheme's
  Pay Run action is disabled until activation and population assignment.

The live draft Rize Singapore/Indonesia configurations retain their existing
activation/population state. This feature does not publish those configurations,
change statutory rules or introduce automated Singapore CPF/SHG calculations.

Backup: `/odoo/backups/payroll-workspace-20261015-124333` on **Payobook19v2**
contains the pre-install database dump and previous custom addons. The final
suite log, code manifest and deployment receipt are retained there. Temporary
fictional employees/configuration/draft payroll and downloaded test workbooks
were removed after verification. Browser images were inspected in memory;
no test PNG or screenshot files were retained.
