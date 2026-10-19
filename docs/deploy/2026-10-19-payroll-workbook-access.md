# Payroll workbook access

Thao's monthly download failed because standard employee/contract columns used
an in-memory import mapping without elevated metadata access. Reading its
`ir.model.fields` destination failed for payroll staff. Transaction tests had
hidden this behind an administrator-warmed field cache. Synthetic mappings now
use the same metadata access as persisted mappings; user roles are unchanged.

Monthly uploads also required the original downloader to upload the workbook.
Authorized payroll staff with Records export permission can now review another
colleague's download for the same company and configuration. Current population,
identity, layout, source and period checks still apply. A fresh review belongs
to the uploader. Review and applied tokens remain owner-only, as do separate
Employee records imports. No direct access to the receipt storage models or
technical Fields model is granted.

Both reported paths were reproduced: the new cold-cache download and shared
monthly review tests produced two errors on the old code. All 142 selected
template and mapping regressions passed on the staged fix. Four new tests also
cover confirmation ownership, non-payroll callers, cross-company and wrong
configuration references, and isolation of records/review/applied receipts.

Implementation commit: `d289ed52d`.

The shared combined rollout upgraded **payobook, payobook_template, abm,
p0clone and rize** on Payobook19v2 to Payroll Templates `19.0.1.2.15`.
It also carried the concurrent dated-contract changes from `bd7ea8e3c`.
Independent post-deployment verification matched every one of the 149 custom
modules / 4,904 files against the latest committed application state, and
checked every installed custom module's database version. The rollout was
staged before this access fix's commit, so its receipt labels `bd7ea8e3c`;
full content hashes independently prove the deployed access fix is identical
to `d289ed52d`. Backups and the rollout receipt are under
`/odoo/backups/rize-india-payrun-code-20261019-124438/`.

All **158 deployed tests passed**: 142 template/mapping regressions on Rize,
and the four new access regressions on each of the other four databases.
Authenticated HTTP checks using Thao's existing session downloaded 63 rows and
reviewed an Ash-owned workbook with zero issues. An attempted confirmation by
the other account was refused. Direct technical Fields access remained denied.
Hashes of employee, contract, contract component, dependent, payslip and run
records stayed identical during these live checks.

Chrome downloaded the monthly workbook, then uploaded a Thao-owned workbook
from Ash's account using the normal file picker. The monthly review displayed
1,764 Excel values and 6,426 system/default values, zero inputs needing
attention and an enabled **Use reviewed inputs** button. The test review was
cancelled without applying inputs or creating another pay run. Full accessibility
inspection timed out on the large grid; a viewport screenshot and a focused
DOM check verified the rendered review. No screenshot or PNG files were saved
or retained. Temporary test workbook downloads were removed.
