# Approved payroll template rollout — 15 October 2026

The owner approved deployment after the payobook.com demo checks. The template
workspace is now installed as `pb_payroll_templates` **19.0.1.0.0** on
**payobook, rize, payobook_template, abm and p0clone**. Implementation is documented
in [the workspace report](2026-10-15-payroll-template-workspace.md).

The deployed repository snapshot is `c42ed3eb7`, including the payroll feature's
final functional commit `c9725d4e7`. Before each pass the combined custom tree
was re-read. The first pass's **4,683 files** already matched the shared server
addons, including concurrent mail work. A subsequent combined pass included
the later PayAI/Learn updates and synchronized two concurrent PayAI test files;
all **4,683 files** were verified against that snapshot again. Standard Odoo
addons were excluded. Other sessions' source changes and workbook deletions
were preserved and excluded from this rollout's documentation commit.

## Database operations

The new module was installed on rize, payobook_template, abm and p0clone, and
upgraded/retested on payobook. Pending installed module versions were upgraded
in the same batch: `biz_access` 19.0.1.6.0, `pb_ess_workforce` 19.0.1.1.0,
`pb_import_kit` 19.0.1.22.0, `pb_me_portal` 19.0.3.1.0 and `pb_zoho_bridge`
19.0.1.2.0. The portal website companion `pb_me_portal_website` 19.0.1.0.0 was
installed where missing. The final combined pass also upgraded `pb_learn`
19.0.20.5.4 and `pb_payroll_ai_insights` 19.0.3.12.2 on the four databases behind
the demo. Demo-only modules were not installed on tenants.

Each database received its own asset purge and `web.assets.version` bump.
The service was restarted and is active. `python3 tools/deploy_status.py`
reports **Nothing pending** across all five databases.

| Database | Template module | Template tests | Active scheduled jobs after |
|---|---|---|---|
| p0clone | installed, 19.0.1.0.0 | 18 passed, 0 failures/errors | 26 |
| payobook | installed, 19.0.1.0.0 | 18 passed, 0 failures/errors | 37 |
| rize | installed, 19.0.1.0.0 | 18 passed, 0 failures/errors | 69 |
| payobook_template | installed, 19.0.1.0.0 | 18 passed, 0 failures/errors | 0 |
| abm | installed, 19.0.1.0.0 | 18 passed, 0 failures/errors | 0 |

Existing job activation was preserved on the live databases and clone. The
golden template and retired ABM were explicitly left dormant, following the
deployment runbook. Pre-upgrade cron flags are retained with the backups.
Employee, contract, configuration and payslip counts, and the aggregate
contracted wage, are identical before and after the batch on every database.

## Deployed Chrome verification

Opened Rize's Settings → Formula Engine → Templates on the Vietnam configuration,
then opened the connected workspace for India. Rize India has **16 currently
eligible employees**. Both workbook downloads were inspected and uploaded back
through the UI:

- Monthly: two visible worksheets, Time and Monthly adjustments, with the same
  16 unique Employee IDs. Review: **0 changes, 112 blanks ignored, 0 issues**.
- Employee records: 16 rows, protected Employee ID/email, one editable Employee
  Name column. Review: **0 changes, 199 blanks ignored, 249 unchanged values,
  0 issues**.
- The monthly configurator shows time quantities, business units, recurring
  context, mandatory identity columns and the live workbook preview. Browser
  error log is empty.

Both reviews were cancelled. No employee changes, approvals or payroll runs
were submitted on Rize. The earlier payobook.com download/edit/confirm/compute
test remains documented in the workspace report; the feature code is unchanged.
The Rize tab is left open at
`https://rize.payobook.com/bizapp/pb_formula_studio/action-1103`.

Rize Vietnam currently resolves to **zero** employees through the existing
pay-run population map, despite historical payslips appearing in the gallery's
employee count. Its header-only workbook downloads correctly and Pay Run is
disabled. Assignments were not inferred or changed by this deployment. The
country configuration activation/population setup is separate from installing
this workspace.

## Recovery and cleanup

Restricted backups and logs are retained on Payobook19v2 at
`/odoo/backups/payroll-templates-rollout-20261015-133527` (initial batch) and
`/odoo/backups/payroll-templates-rollout-20261015-161337` (final combined pass).
Each holds five pre-upgrade database dumps, the file manifest, original cron
flags and per-database test logs/deployment receipt. The final pass also holds
the previous PayAI Actions module files for the two synchronized test files.

The rollout staging directories and three downloaded test workbooks were removed
after verification. No test PNG or screenshot file was saved. Pre-existing
screenshots, product assets and client workbooks were untouched.
