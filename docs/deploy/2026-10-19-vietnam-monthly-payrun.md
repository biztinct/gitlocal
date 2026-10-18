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

Deployment and end-to-end validation receipts are added after execution.
