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
