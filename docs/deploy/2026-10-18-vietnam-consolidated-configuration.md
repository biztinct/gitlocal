# Vietnam configuration from the consolidated workbook

Update existing Rize configuration 4760, `RIZE_VIETNAM_MASTER_V3`, using
`Rize_Vietnam_Consolidated_Payroll_and_Master.xlsx`, sheet `Consolidated`.
The source SHA-256 is
`80b1edd51a032029d1090875c2ded91bd47ad20c8f703b075ca07c2df96e2a80`.
Its 129 unique RIZ identities represent the union of the approved source files.
October master values take precedence for overlapping fields.

All 118 business fields receive exact-name Excel connections. Four join/review
columns are source metadata rather than extra pay components. Keep the 11
recurring-setting placeholders and nine additional monthly inputs, all 42 tested
calculation formulas, five fixed parameters, 65 contract text components and 14
contract amount components. Component names remain aligned with the consolidated
headings. No employee, contract, dependent, bank, payroll or monthly input values
are imported by this change.

Correct the monetary Phone allowance's erroneous Employee Work Phone mapping:
Work Contact Number maps to that field, while Phone remains a monthly earning
already included in the cash total. The remaining 26 native mappings and all
79 contract component definitions are retained. Group time quantities together,
require the RIZ identity and name, identify the employment-status signal, treat
Last Appraisal Date as a date, and mark the unused unpaid-leave reference as
information. The employee/contract board has 106 connections and no unresolved
components. Treatment has no pending type/role/group decisions or conflicts.

The saved-dependent transformation remains authoritative for Dependent/Children;
its spreadsheet count is a visible fallback. Registered tax dependents stay
separate. Source order is saved transformation, spreadsheet, then saved records;
the only configured transformation counts the employee's stored dependent rows.
A deliberate conflicting-count check verifies this separation.

Return the configuration to Draft for the previously approved 70-person review
roster, with no live population assignment. Monthly layout contains five Time
inputs, 26 Monthly adjustments and 105 saved-record fields. The employee snapshot
is protected and color coded; monthly inputs begin blank. The separate editable
records download uses the same saved-record layout and round-trips unchanged.
The remaining unpaid-leave reference stays in Available fields.

Formula Studio `19.0.1.202.8` also draws a configured spreadsheet fallback when
another source has priority. The workbook banner counts physical columns rather
than multiplying them by their stored aliases. This preserves source precedence
while making the complete mapping visible. Formula-column suppression from
`19.0.1.202.7` remains in force for fresh upload and replacement.

The Rize-only installer and source definition are committed separately from the
private workbook and review receipts. It defaults to rollback and checks source
hash, scoped destinations, unchanged business records, all source mappings,
all 129 input rows, the 70-person review roster, 96 calculation scenarios and
both application-generated workbook types before committing.

Staged validation: 167 Odoo regression tests pass. The rollback configuration
check passes all mapping, treatment and workbook invariants. A fresh-month test
with representative full paid days and zero adjustments yields 63 Ready employees
and seven salary review cases; no test values are saved. Implementation commit `805418178` is applied. The latest combined 149 modules /
4,901 application files are synchronized, with Formula Studio upgraded to
`19.0.1.202.8` on Rize, Payobook, Payobook Template, ABM and p0clone. The client
configuration is applied only to Rize. Protected backups and deployment evidence
are at `/odoo/backups/vn-consolidated-code-20261018-233617/`.

All five deployed databases pass 167 regression tests each, 835 total, with zero
failures or errors. The committed installer passes its live invariants before
committing: 118 mappings, 106 storage connections, no unresolved components, all
96 calculation scenarios, 129 source rows, the 70-person roster and both workbook
types. A post-commit read confirms the persisted configuration and source hash.

Chrome verifies 118 mapped fields / 122 physical columns, the corrected Work
Contact Number → Work Phone connection, no BHXH (SI) 8% formula card under All,
and the 70-person three-tab template layout with 31 monthly inputs. The template
download RPC returns HTTP 200; the browser download-event capture timed out, so
workbook contents are verified from the application export payloads instead.
Both decoded workbook types pass row, sheet protection and round-trip checks.
Browser warning/error logs are empty. Screenshots were inspected in memory;
no test PNG files were written. The detailed private review report lists all
138 input treatments, the 20 additional sources and the seven salary cases.
