# Monthly input workbook editing

Fix commit **86a85258a**; `pb_payroll_templates` **19.0.1.0.1**.

Monthly **Time** and **Monthly adjustments** worksheets no longer enable Excel
sheet protection. In particular, a zero-employee export previously contained only
protected headers and Excel's default locked blank cells, making the whole file
appear locked. Users can now edit/paste normally. Existing downloaded files must
be downloaded again to receive the fix.

The employee-records workbook retains protected ID/email cells. Monthly imports
still validate identity, roster membership, read-only context, schema and period
against the server-owned download snapshot. Changing an Employee ID is refused;
blanks still mean keep and numeric zero still updates.

## Deployment

Deployed the latest combined working-tree snapshot to the shared custom addons
directory, excluding standard Odoo modules. Snapshot started at `86a85258a`;
the concurrent T3a commit `18e0f666a` subsequently committed content already
included in that snapshot. Other-session work was preserved and excluded from
the fix commit. No deployed file changed relative to the snapshot at closeout.

Upgraded/tested **payobook** first, then **rize**, **p0clone**,
**payobook_template** and **abm**. The combined snapshot also includes the current
portal changes; the already installed Ask HR module's missing shared files were
restored and upgraded on p0clone. Ask HR was not installed in additional DBs.

- **20 tests passed per database, 100 total; zero failures/errors.** Regression
  checks cover unprotected populated and empty monthly worksheets, server-side
  rejection of changed IDs, and retained employee-record protection.
- Employee/contract/configuration/payslip counts and aggregate contracted wages
  were unchanged on every database.
- All **4,707** combined file hashes verified. Installed module versions match
  the repository across all five databases (`tools/deploy_status.py`).
- Existing job activation restored; all jobs remain disabled on retired ABM
  and the golden template. Application service active after deployment.
- Chrome administrator check on Rize: selected **Rize Vietnam Payroll v2**,
  clicked **Download month**, and received a successful download. The resulting
  `.xlsx` has no `sheetProtection` XML on either monthly sheet and no workbook
  structure lock. Browser errors: zero.
- Vietnam currently has zero eligible employees, so its workbook has headers
  only. This fix does not change payroll population assignments.
- No PNG/screenshots generated. Removed only the test-created suffixed workbook;
  the user's pre-existing download was preserved.

Backup/receipt: SSH `Payobook19v2`,
`/odoo/backups/payroll-templates-rollout-20261015-193554/`.
Contains pre-upgrade dumps for all five databases, prior changed addons,
snapshot manifest, database test logs and deployment receipt.
