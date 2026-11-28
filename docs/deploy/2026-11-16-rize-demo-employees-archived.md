# Rize demo employee archive — 16 November 2026

Applied the owner's authorised archive of the seven confirmed demo employees to
`rize` on `Payobook19v2`, serving `https://rize.payobook.com`.
This was a production data operation, with no application code, schema or
configuration change. No other database was changed or required deployment.
Concurrent working-tree changes were preserved.

## Scope and outcome

The exact employee records were verified against the application's demo-data
register, rather than selected for mutation by name prefix:

| Record | Demo employee | Outcome |
|---|---|---|
| 3407 | DEMO Lifecycle Manager | Archived |
| 3408 | DEMO Probation Colleague | Archived |
| 3122 | Demo Le Thi Hoa | Archived |
| 3265 | Demo Nguyen Thi Mai | Archived |
| 3123 | Demo Pham Minh Quan | Archived |
| 3266 | Demo Tran Van Hung | Archived |
| 3124 | Demo Vo Thanh Son | Archived |

Their five contracts (1700–1704) were cancelled and archived. Their original
dates and wage values were retained. This prevents both current and historical
pay-run selection from admitting demo contracts. Employee archiving alone would
not have been sufficient because payroll eligibility reads contracts directly.
No departure dates were invented and no employee or contract was deleted.
None of these employees had a saved payslip or linked login.

The application's contract-change hook rebuilt salary-position analytics,
removing the four demo salary positions. The existing headcount report was
refreshed and now shows 229 active employees, down from 236. Historical test
records remain linked to the archived profiles; this operation did not remove
the wider demo worlds, departments, assets, hiring examples or other fixtures.
Archived profiles remain available through an explicit archive search.

## Validation and recovery

A rollback rehearsal passed before the production transaction was committed.
An independent fresh database session verified all seven profiles archived,
all five contracts cancelled and archived, zero demo payslips, zero demo salary
positions and the refreshed headcount of 229.

Every real employee and contract was compared before and after the operation.
Thirteen protected business tables retained identical hashes, including
payslips and lines, payroll runs and inputs, import lines, leave and allocations,
formula configuration/rules, contract advantages, bank approval records,
departments and final settlements. Real employees' payroll eligibility for
October, November and December remained unchanged in all four active schemes.
The pay-run wizard also excluded all seven demo employee IDs for those months.

Permanent restricted archive on the server:
`/odoo/archives/rize-demo-archive-20261116/`.
It contains `rize-before.dump`, the maintenance script, rehearsal and applied
receipts, and independent verification. The database backup was validated with
`pg_restore -l`; Rize backups have permanent retention. The before receipt
retains the original employee and contract states for targeted recovery.

Chrome verification completed after the owner made the browser available.
The live employee directory at `rize.payobook.com/bizapp/action-779` showed
229 headcount and 197 running contracts. Searching for `Demo` returned
`0 of 229 employees` and `No employees match these filters`.
No test screenshots or PNG files were created.
