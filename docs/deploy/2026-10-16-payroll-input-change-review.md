# Payroll input-change review — deployment receipt

Implemented the durable workbook review described in
[the design and implementation handover](../handovers/PAYROLL_INPUT_CHANGE_REVIEW.md).
The review opens after computation and from the payroll batch, retaining
per-cell decisions and their history after the wizard closes.

## Commits and combined state

Feature commits: `c4ab34194`, `6fdd431c1`, `4b60dacbb`, `e3730f109`,
`2a6709dca`, and `7568f1259`.

Concurrent workbook compatibility/readiness changes in `61cf0e87a` were preserved
and included in deployment. Their files were excluded from this feature's
commits. The owner's existing workbook deletions and `RIZE/SINGAPORE/` work were
left untouched and unstaged.

Final application versions: **pb_payroll_templates 19.0.1.2.5** and
**pb_payrun_wizard 19.0.1.32.3**. The live target is `Payobook19v2`, using the
single `/odoo/odoo-server/addons` directory. Standard vendored addons were not
copied. A final comparison of 4,442 files across 140 installed custom addons
found no local/server content differences. The combined rollout also verified
its broader 4,799-file custom-addon snapshot.

## Deployment and tests

| Database | Expanded deployed server tests | Final versions verified | Active jobs restored |
| --- | --- | --- | --- |
| payobook | 66 passed, 0 failures/errors | Yes | 37 |
| rize | 66 passed, 0 failures/errors | Yes | 69 |
| p0clone | 66 passed, 0 failures/errors | Yes | 26 |
| payobook_template | 66 passed, 0 failures/errors | Yes | 0 |
| abm | 66 passed, 0 failures/errors | Yes | 0 |

**330 server checks passed** in the combined rollout. These include the 15 new
input-decision tests, the expanded workbook regression suite, and the selected
wizard lane/access checks. Before implementation, the existing 41-test workbook
suite also passed. The final 1.2.5 increment changes only explanatory UI text;
its backend Python is identical to the expanded-suite build. All five databases
were reloaded for that increment and the final assets were checked in Chrome.

Tests cover mapped versus Excel-only fields, before-value capture, explicit zero,
blank handling, record/source conflicts, stale revisions, duplicate/forged keys,
company and access checks, approval handoff/return, durable decisions, preservation
of computed payslips, and safe, color-coded Excel export. These are targeted
checks, not a claim that every repository test was run.

Independent final checks match the pre-deployment fingerprints on every target:
employee counts, contract counts and total wages, payslip states and input/computed
JSON, and payroll-run states. Scheduled-job activation matches its original set,
including zero active jobs on the golden template and retired ABM. The service
was restarted and the Rize login endpoint returned HTTP 200.

## Chrome end-to-end verification

An isolated Rize fixture completed the actual wizard flow:

1. Open the selected synthetic scheme and period; upload a workbook through the
   file picker and pass the three-component preflight.
2. Compute one draft payslip (synthetic net 1,330), then open **Review input
   changes** from the computation result. Both mapped changes appear beside
   their captured record values; the Excel-only bonus is marked separately.
3. Verify filtering clears hidden selections and disables the action button.
4. Keep salary specific to the payroll. Leave the wizard through its final
   review step and **Open Payroll**, then reopen **Input changes** on the batch.
   The salary decision remains and the phone field remains undecided.
5. Save the phone value through the existing record-update route. Reopen after
   a full reload: history contains exactly two events, salary remains unchanged
   on the contract, phone is saved, and the computed payslip inputs/net remain
   unchanged. Final browser console errors: **zero**.
6. Download Excel and verify its values, grey/green/amber fills, on-record/status
   comments, and `C2` freeze panes. Visual inspection confirms the comparison
   values are visible in the compact desktop layout.

A deployment restart interrupted one test request. Refresh recovered the saved
review and the retry recorded one decision, with no duplicate event. A separate
fixture also checked the native batch door and the confirmation for future
record updates before the complete wizard walkthrough.

## Backup and cleanup

Protected receipts and rollback artifacts remain on `Payobook19v2`:

- `/odoo/backups/payroll-input-review-20261016/`: all five original database
  dumps, addon backups, per-database logs, original state, final fingerprints,
  and the Chrome result.
- `/odoo/backups/payroll-upload-fix-20261016-134859/`: the combined rollout's
  deployment receipt and expanded per-database test logs. Progress/test logs are
  also under `/tmp/payroll-upload-fix-20261016-134859/`.

All disposable employees, contracts, schemes, draft runs/payslips, import batches,
approval/audit fixture records, temporary actions, and generated workbook files
were removed. No test PNG or screenshot files were retained. Pre-existing product
assets, user images, workbooks, and unrelated working-tree changes were preserved.
