# Vietnam monthly workbook and October Draft validation

The owner requested one manually entered **Trợ cấp tư vấn kỹ thuật (Technical
advisory allowance)** instead of the four supporting payment buckets, a filled
October workbook, and a Draft payroll exercise using the normal monthly process.
All employee/configuration data belongs only to `rize.payobook.com / rize`.

## Configuration change

`docs/configuration/rize-vietnam-monthly-202610.json` defines the single monthly
earning `VNTECH` and the reusable layout: five Time fields, 23 Monthly adjustments,
and the unchanged protected employee/contract/bank snapshot. Monthly adjustments
follow the source Salary order, then the net adjustments and optional comparison
inputs. The eleven recurring placeholders remain. Registered tax dependents and
imported dependent-detail counts remain separate.

`tools/configure_rize_vietnam_monthly.py` is Rize-only and rolls back unless
`VN_MONTHLY_APPLY=1`. It preserves permanent component letters and every other
formula, migrates all 96 test inputs to the sum already agreed against the master,
removes the four obsolete components, and retains all independent expected
outputs. The dry run passes all 96 scenarios with no treatment conflicts.

The shared workbook exporter now sizes the header row for wrapped bilingual
component names. It preserves worksheet layout, protections, identity metadata,
column order and the blank defaults of a reusable monthly template.

## Data readiness

At the initial audit there are 70 review employees, 63 open contracts with salary
and historical variable data, and seven Draft contracts without salary or paid
days. No existing payroll uses configuration 4760. The consolidated file combines
October master data and historical August attendance/payments; it is not evidence
of approved October actuals. The owner has been asked how to handle these test
inputs and seven incomplete records. No salary, attendance or eligibility is to
be invented.

The owner confirmed using historical inputs and testing 63 complete employees,
with the seven incomplete people retained as blank reference rows.

## Monthly upload correction

A downloaded Draft-review workbook can include employees who are outside the
current run's eligible population. The monthly importer now accepts those rows
as reference only when the server-owned download receipt identifies them, their
identity remains unchanged, and every editable monthly input is blank. It warns
which identities were excluded. An entered zero or amount, a changed identity,
an unknown row or a cross-company person still blocks the upload. Three
regressions cover blank references and these refusals.

The first shared deployment (`a0439170c`) upgraded Payroll Templates to
`19.0.1.2.11` on all five databases. All 131 selected template/mapping regressions
passed on each database (655 total). The Rize-only definition update then
committed 181 components: 135 inputs, 41 formulas, five constants, with 96/96
calculation scenarios passing and all employee/contract/bank/dependent/payroll
records unchanged.

An attempted department-wide population correctly failed its scope check:
seven historical leavers still have open contracts in those departments. The
configuration therefore uses the existing advanced employee-domain assignment
model to scope the owner's 70 approved RIZ identities. Normal contract
eligibility admits 63; the seven unsalaried Draft contracts remain pending.
No old contract is closed and no unrelated department map is replaced.

## Generated monthly file validation

The first Chrome run exposed a mismatch after monthly review: the generated
workbook restores stable declared source keys such as `Consolidated|...`, but
required-field validation only searched component codes, names and letters. All
63 rows were rejected even though their reviewed inputs were present. The
monthly import-line adapter now uses the same declared-key lookup as the
resolver, including when the persisted batch no longer has its upload context.
It leaves the stored raw row unchanged and preserves missing-required errors.

The pay-run input gate also counts only fields selected in Time and Monthly
adjustments. Generic review warnings are labelled “review notes” rather than
incorrectly claiming saved records were refreshed.

A new integration regression exercises download → fill → review → confirm →
generated file → match → validate without upload context → Draft payslip, with
required identity, salary and paid-days bindings from another worksheet. It
checks that removing the required paid-days input still fails. The selected
layout gate has its own regression. All 136 selected tests passed against an
isolated staged module before deployment; live business changes were rolled
back by the test transactions.

Deployment and end-to-end validation receipts are added after execution.


## Monthly records are context, not future-record proposals

The completed run exposed 54 false Department proposals in the durable input
review. The server-generated workbook carries the saved department's display
name. Where duplicate department names exist, the generic record-update coercer
can resolve that name to another ID despite identical before/after labels.

Monthly-template snapshots now present mapped record fields as read-only
context, without mutating the captured audit payload. Equal labels on saved
record context do not become changes. Explicit month-only overrides remain
labelled as this-month-only, and a direct API request to save a monthly snapshot
for future payrolls is refused. The separate Employee & contract records process
remains the way to make lasting changes. Ordinary uploaded payroll files retain
their existing reviewed future-record decisions.

Two regressions cover duplicate department labels and refusal to promote a
month-only record override. The UI explains the monthly context and omits
permanent-record decision controls for a monthly-only run.

All 138 selected regressions, including both new monthly-record cases and the
ordinary-upload decision tests, passed against the staged module before rollout.


## Final deployed verification

Implementation commit `c815037be` (including `0eef74b6a`'s qualified-source
validation) is deployed to **payobook, payobook_template, abm, p0clone and rize**
on Payobook19v2. Payroll Templates is `19.0.1.2.14` on every target. The latest
combined application snapshot contains 149 custom modules / 4,901 files. Full
backups and the rollout receipt are protected under
`/odoo/backups/vn-october-payrun-code-20261019-105048/`.

All **138 selected regressions passed on each database — 690 total**, with no
failures or errors. Chrome completed the normal monthly upload, review,
confirmation and calculation. Run **1247**, **Vietnam October 2026 TEST —
historical inputs**, has 63 computed Draft payslips. Batch 1783 matched all 63
rows with zero errors, used the file once and created no employees or contracts.
The earlier empty Draft test was replaced through the normal Clean and Run flow.
No payroll was submitted, approved or paid.

The independent August replay passed 2,205 controls for 70 source employees.
October passed 2,583 independent formula controls, 756 posted-line amount/total
controls and exact preservation of all 1,764 uploaded input cells. All 96 stored
calculation scenarios pass. The only PIT differences from the source month
belong to the three October salary changes selected by the owner. Existing
whole-dong payslip line rounding reconciles separately from raw formula values;
the run totals balance. No formula or rounding policy was changed to hide a
comparison difference.

Chrome on the final deployed code shows zero mapped record changes to decide,
zero record updates in approval, read-only Department context and no permanent
record decision controls for the monthly workbook. The November reusable export
has 28 blank monthly fields, a protected Employee records sheet, and no saved
November monthly-input rows.

Business-field audits confirm the run changed no employee, contract, contract
component, dependent or bank values. The initial computation only populated
salary-rule back-references on formula definitions; formula contents and
component treatment were unchanged. The final rollout preserved all protected
rows. Post-test comparison found only advanced write timestamps on 21 existing
Payobook employee rows; every business field and record ID remained identical.
Those timestamps were preserved. All 63 Draft payslip inputs/results are
byte-for-byte unchanged after the final records-review deployment.

The filled workbook and private owner review report are in
`outputs/rize-vietnam-october-test-20261019/` and are excluded from commits.
They identify the seven pending employees, nine historical Probation tax
classifications, three salary changes and missing bank account requiring owner
review. Historical quantities/payments are explicitly TEST inputs. No Sheet4
values were introduced, the eleven recurring settings remain, and dependent
record counts remain separate from registered tax dependents.

Session-generated spreadsheet test PNGs were removed. Chrome proof is JPEG;
pre-existing product assets and unrelated session files were left untouched.
