# Pending work close-out — 16 October 2026

The owner ended the demo freeze and requested completion of the pending work.
The queued employee self-service rollout was completed demo-first, followed by
Rize, the clone, the golden template and retired ABM. All custom addon files
were synchronized from the combined repository state; unrelated client files
and workbook deletions were preserved outside the commits.

## Commits and scope

- `fdf202e50`: queued T3b clock, notices, colleague photos and download work.
- `c59dae7ff`: queued T3c buddy stand-in guard and tokened training links.
- `f73f307f0`: commit the already-deployed reserved-domain mail protection.
- `0aa1a90fe`: preserve driver/field access and active roles during migration;
  create rollback records with mode 0600; four local guard tests.

The application snapshot contains **4,733 custom addon files**. Its delta was
11 files: three held portal template/style changes and eight onboarding/training
files. No vendored standard addon was copied. The later migration-tool commit
changed no addon content; its deployed copy and migration evidence are stored
with the rollout backup.

All targets explicitly install missing `pb_ask_hr` / `pb_me_portal_comm` glue,
upgrade any installed custom module whose version differs, and reload the
portal modules even where their manifest versions already match. This loads
the held QWeb edits. Training is upgraded where installed; it remains absent
on ABM. Assets are purged and their version bumped on each database.

## Deployed verification

| Database | Targeted tests | Payroll/record aggregates | Active jobs |
|---|---|---|---|
| `payobook` | 83 passed, 0 failed/errors | Unchanged | 37 |
| `rize` | 83 passed, 0 failed/errors | Unchanged | 69 |
| `p0clone` | 83 passed, 0 failed/errors | Unchanged | 26 |
| `payobook_template` | 83 passed, 0 failed/errors | Unchanged | 0 |
| `abm` | 82 passed, 0 failed/errors | Unchanged | 0 |

**Total: 414 deployed tests passed**, plus four local migration guard tests.

Tests cover payroll workbook patches and recurring salary precedence, reserved
test-recipient blocking, Ask HR, portal clock model/HTTP flows, colleague photos,
notices and read receipts, buddy boundaries and tokened training-claim links.
The logged duplicate notice-read key is the intentional race test; it is caught
and the result summaries contain zero failures/errors. These are targeted tests,
not a claim that every test in the repository was run. Historical clone-only
failures in unrelated broader suites are recorded in the tiers ledger.

Employee, contract, total contract wage, configuration and payslip counts match
the pre-upgrade snapshots on every database. Pre-existing job activation is
restored; golden-template and retired-ABM scheduled jobs are all disabled.

## Chrome end-to-end check

On the demo, an isolated Employee login completed home → clock in → home clock
state → clock out after the debounce window → timesheet (0.02 worked hours).
It read a seeded verification notice (one unread → zero), loaded its same-company
colleague image through the guarded photo route, downloaded a valid tokened
training receipt PDF, opened Ask HR, and was redirected from `/bizapp` to `/my`.
Browser console errors: zero. The notice was seeded only for this test employee;
no announcement email was sent.

The temporary user, two employees, attendance, notice/delivery/read receipt,
training claim/attachments and downloaded PDF were removed. No screenshot or
PNG file was generated for this check.

On Rize, Chrome opened the current October Vietnam run. It is in the owner's
existing **Rejected** state (reason “test”, 15 October 20:38 Sydney), so its cards
exclude the cancelled payslips. A comparison against the pre-deployment dump
proved run 685 and India run 686 states, totals and write timestamps unchanged;
all 70 Vietnam input, computed-value and provenance payloads are unchanged.
The 70 contract salaries still total VND 1,814,978,020. No rejection was undone.

The workspace shows the 70 assigned Vietnam employees. Fresh October downloads
have editable Time and Monthly adjustments sheets, matching sets of 70 Employee
IDs and 70 positive recurring salaries totaling VND 1,814,978,020. Native XML
inspection confirms neither sheet is protected and the workbook structure is
unlocked. Both test downloads were removed; earlier user downloads were kept.

## Approved account migration

The owner approved the exact 12 demo account conversions and five existing
joiner links after reviewing the preview. All were applied and rechecked through
the existing business facade. Every converted account has exactly the portal
group and passes the portal-only rule. All other users' login/type/group data
is fingerprint-identical. Drivers, field staff, managers and HR retain access.
A final audit found no remaining eligible conversion or missing joiner link on
any target. Rize needed no account change.

See [the tiers close-out](../handovers/tiers/TIERS_CLOSEOUT.md) for the account
list, decisions and optional follow-ups outside this rollout.

## Backup and cleanup

On `Payobook19v2`, protected evidence is retained in:

`/odoo/backups/payroll-templates-rollout-20261016-082135/`

It contains all five pre-upgrade database dumps, addon rollback archive,
manifest, deployment receipt, per-database logs, account migration receipt and
both rollback lists. Account rollback filenames use UTC on 15 October; the
work was performed on 16 October in Sydney.

The deployment stage and temporary test files/downloads were removed. No PNG
or screenshot was generated by this session, and pre-existing images and user
downloads were preserved.

## Concurrent work preserved

While the queued rollout finished, another session committed `3c204362f` (with
test follow-up `e6816bc29`), the
formula-studio loading and dependency-ordering performance change. The owner
explicitly confirmed that the other session handles its deployment. Its rollout
covers the same five databases under
`/odoo/backups/screen-loading-20261016-3c204362f/`; it was still running at this
close-out. It is tracked separately from the completed 414-test tiers batch.

The final content check matched **4,734 combined custom-addon files**, including
the added dependency-ordering regression file. All queued tiers/template/mail
module versions match on all five targets. Only the separately owned performance
module upgrades were pending in `deploy_status.py` during that concurrent run.
Seven local dependency-ordering tests and the updated JavaScript syntax check
also pass. No concurrent performance source, rollout process or job flags were
overwritten by this session.
