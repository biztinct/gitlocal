# Vietnam information-only Contract Text components

The owner approved adding all 22 previously excluded, non-calculated VN sheet
headings to **Rize Vietnam Payroll HC Oct 2026**, Draft configuration **4639**,
code `RIZE_VIETNAM_HC_202610`. This includes the four Indonesia-labelled headings.
The changes are confined to the **rize** database; shared application code is
verified/deployed across all existing Payobook19v2 application databases.

| VN columns | Component labels |
| --- | --- |
| N–O | Blood Type; Religion |
| AS–AV | NPWP Number (Tax Number)-Indo; Family Card Number-Indo; BPJS Keternagakerjaan Number-Indo; BPJS Kesehatan Number-Indo |
| AX–AZ | Background Check Completed; Background Check/Ref Check status; Background Check/Ref Check Links |
| BA–BC | Signed Offer Letter; NDA/Employment Agreement; Personal Document Link |
| CI–CK | IT Asset type; IT Asset number; Software access given |
| CL–CO | Last Appraisal Date; Performance Rating; Promotion Date (if any); PIP History (if any) |
| CT–CV | University/School; Major; Education Level |

Each component preserves the spreadsheet label and binds to its exact
`VN|<heading>` key. It is an input of value kind **text**, stored as a
**Contract Text** component, column role **contract**, report group
**Employee information**, pay role **information only**, not required, and hidden
from payslips. Dates and identifiers deliberately remain text under the owner's
instruction. No new Employee or Contract SQL columns are introduced. Actual
values, when separately reviewed/imported, use the existing contract-component
line model. This change does not import any source employee values.

The scoped migration appends components without renumbering any existing
immutable component letter or changing any formula. It retains the owner's
current source priority, native mappings, all 11 recurring placeholders, all
17 monthly bindings, separate registered-tax-dependent setting and native
dependent-count transformation. Draft state, roster and payroll assignments
remain unchanged. The original workbook/sample metadata is preserved; the
18 calculated/generated source columns remain hidden.

New fields are selected in the **Employee records** layout lane. They appear in
the fully protected third sheet of the monthly download and in the separate
Employee/Contract records workbook. Existing Time/Monthly adjustments selections
and record-field order are preserved. Downloaded values come from current saved
records, so new contract-text values are initially blank.

`tools/add_rize_vietnam_hr_context.py` defaults to a rollback dry run, refuses any
database other than `rize`, checks the expected Draft/code and verifies existing
rows instead of overwriting them on rerun. Full hashes of Employee, Contract,
contract advantage, payslip and run rows prove that business values do not
change. The non-personal definition and its read-only extractor also include the
22 fields so a future new configuration keeps these mappings.

## Preparation checks

The production rollback dry run passed: **22 source wires**, **22 Contract Text
destinations**, **138 components / 115 inputs**, **30 of 30 payroll scenarios**,
zero configuration errors, and both actual workbook generators containing every
new heading. Monthly Time/adjustment selections remain **4 / 13**. The Records
lane grows **75 → 97** fields (plus pinned Employee Name); the review download
still contains **63 existing Employee records out of 70 approved source people**.
All existing rule/source/native-mapping snapshots and business-row hashes match.

## Deployed result

Implementation commit **6546960d5** was pushed on branch `19.1`. The latest
combined **149 custom modules / 4,878 source files**, including the concurrent
configuration-card styling fix, were synchronized and verified byte-for-byte on
Payobook19v2. Shared targets are **payobook, payobook_template, abm, p0clone and
rize**. Application source already matched the latest combined tree; no new
application schema, model field or asset code was needed for this configuration.

The deployment audit also found 17 previously pending module versions on
**p0clone**. Those generic upgrades were completed under the deployment lock,
active cron IDs were restored, and all installed custom module versions now
match the repository on all five targets. Business counts and aggregate wages
match the pre-deployment baselines on every database. The service is active.
An asset notification retry used Odoo 19's signalling-table insert after the
first attempt used sequence syntax; final validation passed.

Only **rize** received the 22 new component definitions, source bindings and
layout entries. SQL verification confirms **zero** of these component codes in
the other four databases. The configuration remains Draft. A second rollback
verification created **zero** components and passed all invariants and all
30 payroll scenarios again. The original 116 rules, letters, formulas, sources,
native mappings and Employee/Contract/advantage/payslip/run row hashes are
unchanged. There are no new stored values or advantage lines for these fields.

Deployed tests: **74 passed per database, 370 total, zero failures/errors** for
the template workspace and native dependent-count regressions. Local syntax,
definition, diff and four database-isolation guard checks also passed.

Chrome verification on Rize confirmed **138 components / 115 inputs**, the
Blood Type spreadsheet wire, Contract Text storage, Information only pay role,
and saved-record placement restrictions. The mapping board shows **114 Excel
connections**; Dependent/Children continues to use the saved dependent-count
transformation. All **18 calculated/generated Excel columns** remain hidden.

Both actual Chrome downloads contain all 22 headings exactly once across the
63-person review roster. The monthly workbook has three visible sheets and a
fully protected Employee records sheet; new fields are absent from the editable
Time/Monthly adjustments tabs. The separate records workbook exposes the new
text cells for reviewed updates. Re-uploading that unmodified workbook returned
**0 changes, 5,733 blanks ignored, 441 unchanged values and 0 issues**; the review
was cancelled. The browser saw one expected connection warning during the
shared service restart; the completed checks passed after reload.

Updated private deliverables are in `outputs/rize-vn-context-20261018/` and are
excluded from Git. New text values are initially blank; their population is a
separate reviewed records import. The roster remains 63 existing profiles out
of the 70 approved source people. No test PNGs were written to disk; all
test-generated PNG files are absent.

Protected backups, before-database dumps, migration definition/script and
receipts, combined-tree manifest and final test logs:
`Payobook19v2:/odoo/backups/vn-hr-context-20261018-133224/`.
