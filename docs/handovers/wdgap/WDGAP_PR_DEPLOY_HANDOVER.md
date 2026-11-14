# WDGAP PR — merge, go live ×5, verify (step "Pay-run extras": PR-A, PR-B, PR-C, PR-D)

Read first: `WDGAP_LEDGER.md` (deploy rules + gotchas QFM-1..3), repo `CLAUDE.md` (deploy
contract), `WDGAP_QF_DEPLOY_REPORT.md` (the proven command sequence from the previous
step — reuse it, do not re-derive), then the four phase reports, each with "Deploy notes":
`WDGAP_PR_A_REPORT.md` (branch `wdgap-pra`, date functions + one function list),
`WDGAP_PR_B_REPORT.md` (`wdgap-prb`, NEW module `pb_loans`),
`WDGAP_PR_C_REPORT.md` (`wdgap-prc`, hold pay), `WDGAP_PR_D_REPORT.md` (`wdgap-prd`, extra run).
Memory notes that bind deploys (in
`/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/memory/`):
`payobook-deploy.md`, `tiered-deploy-rule.md`, `deploy-notes-file.md`,
`cron-snapshot-boolean-trap.md`, `copy-db-runs-live-crons.md`, `payobook-qa-login.md`,
`keep-demo-data-payobook.md`, `never-deploy-abm.md`, `usage-limit-pause.md`,
`tenant-module-sync-rule.md`, `wdgap-program.md`.

Owner decision (ledger D4): live on all five — `payobook`, `payobook_template`, `p0clone`,
`rize`, `sudima`. Never `abm`, `pbf_preview` or any other database. Standing approval to
deploy/restart; never during an owner demo, never over another deployer's open START.

White-label rule (binding): the word "Odoo" never appears in anything an end user can
see. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

This step is ALL RISKY tier: pay calculation engine (PR-A), a new module that feeds pay
runs (PR-B), the money-out path (PR-C), the pay-run path and bridges (PR-D).

## 1. Merge

1. New worktree from `origin/19.1`, branch `wdgap-pr-merge`. Merge `origin/wdgap-pra`,
   `-prd`, `-prc`, `-prb` one at a time (`--no-ff`), in that order. Expected conflicts:
   `docs/handovers/wdgap/WDGAP_LEDGER.md` (UNION of gotcha rows, keep D1–D6 and the phase
   map), `.po` headers, and possibly `pb_payslip_review/models/review_flags.py` (PR-B and
   PR-C may both add a flag — keep both blocks) and its `vi_VN.po`. Any other code
   conflict: stop and report rather than guess.
2. **Cross-phase seams to check by reading and by test after the merge** (the builders
   could not see each other):
   a. PR-B takes a loan instalment only in `regular` runs; PR-D added the `extra` kind →
      an Extra run takes NO loan instalment (write/extend one test on the merged tree).
   b. PR-C hold + PR-D extra run: a held payslip in an Extra run is left out of the bank
      file and delivery like any other (one test).
   c. PR-B review flags and PR-C "on hold" flag both show on one run (one test or walk).
   d. PR-A reserved names: no component code shipped by `pb_loans` or the demo catalogue
      now collides with a function name; PR-A's golden conversion fixture still passes on
      the merged tree (formulas added by PR-B/PR-D tests are new, not golden).
   e. PR-D made the bridges feed regular runs only; PR-B's "only regular" rule and the
      one-off paid-once tests still pass together.
   Fix small seam bugs yourself (smallest change, with a test, noted in the report); a
   design-level clash → stop and report.
3. Combined gates: py_compile on every changed `.py`, XML well-formed, PO parse gate,
   "Odoo" grep on the merged diff's user-visible strings (and "Payobook" must not appear
   in `biz_*` generic modules — QFM lesson).
4. Combined local run on a fresh local copy with the demo world: install `pb_loans`, `-u`
   every module the four reports list; the four phases' new test files together (all must
   pass); full suites of the touched modules — failure set must equal the union of the
   recorded baselines; PR-A R5 demo recompute (every demo scheme's regular run lines
   identical before/after, `pb_balance_ok` true) on the MERGED tree. The Mac's disk is
   nearly full: one test database at a time, drop each when done, and drop leftover
   `wdgap_pr*` databases from the builders (list first).
5. Update the ledger phase map (PR-A..D → built, versions), commit; bring `origin/19.1`
   up to date (merge it in if it moved, re-run gate 3), push to `origin 19.1` (never force).

## 2. Read-only checks on live BEFORE anything changes (report each number)

a. `/opt/deploy-notes.md` — an open START by someone else → stop and report.
b. Disk and memory; room for five backups.
c. Cron snapshot per database (id, name, active — boolean trap). Note: on `payobook`,
   job 156 "Payobook: send saved Explorer views" is OFF by owner choice (2026-11-14) and
   must be OFF after this deploy too; on `payobook_template` 8 jobs were re-activated by
   the last upgrade and switched off again — expect the same and repair from the snapshot.
d. PR-A: re-count per database stored formulas that use `TODAY(`, `NOW(`, `IFS(`,
   `LEFT(`, `RIGHT(`, `MID(`, `COUNT(`, `YEAR(`, `MONTH(`, `DAY(`, `INT(`, `DATE(`
   (checked 2026-11-14: zero everywhere). Non-zero → list them and STOP before go-live
   (their result could change or their next edit would be refused — owner must know).
   Also list component codes equal to a new function name (existing ones keep working;
   report only).
e. PR-C: per database, count payslips in runs that have a prepared-but-not-released bank
   file, and done payslips with no paid date in runs that have a released file (the
   "who gets marked paid" change — these are the people whose status the new rule reads
   differently). Report facts; change nothing.
f. PR-D: per database, count top-up runs in draft/computed state (the bridge change means
   a recompute of an open top-up no longer re-feeds overtime/trip values). Non-zero on
   `rize` or `sudima` → report the run names prominently; do not block.
g. Which touched modules are installed where; `pb_loans` is new — install it on every
   database where its dependencies are all installed (tenant module-sync rule), skip and
   report where they are not.

## 3. Go live — RISKY tier

Same sequence as `WDGAP_QF_DEPLOY_REPORT.md`: START line + flock → five `pg_dump -Fc`
backups → rehearsal on a copy of `rize` AND a copy of `payobook` (jobs + mail servers off
before the live service can run them; upgrade + install there; EXIT=0, no
ERROR/CRITICAL/Traceback; on the payobook copy recompute one finished demo regular run in
a rolled-back shell transaction and confirm every payslip line is identical to the stored
one; on the rize copy do the same for the most recent finished regular run — figures must
be identical; `dropdb --force` both) → stage from the pushed commit with `git archive` →
per-module scoped `rsync -a --delete` (never into the addons root; never vendored
standard addons) → stop service, zero `odoo-bin` → per database `-u <installed touched
modules>` + `-i pb_loans` where §2g says, stopping at the first failure (restore that
database, put the previous trees back, start, report) → asset purge + `web.assets.version`
bump + signaling row per database → cron repair from the snapshot (incl. job 156 OFF on
payobook) → start, registry wait, warm five sites → verify hashes both sides, manifest vs
`latest_version` ×5, cron diff, log grep → DONE/FAILED line, release flock.

If a rehearsal recompute differs by even one line: do NOT go live; report the scheme,
person, line and both figures.

## 4. Check it on the real system (payobook.com; QA login from memory `payobook-qa-login`)

The last walk was look-only because the browser was signed in as the owner. This time
open a private/incognito window or a separate browser profile via the Chrome tools if
possible and sign in as the QA login; if you cannot, do the look-only walk and say so.
DEMO people only; undo what you create; nothing sent to a real person.
1. Formula Studio: the function list shows DATEDIF with help; type a formula using it and
   preview on a demo person; type `TODAY()` and read the refusal. Do not save.
2. Loans board opens from the palette (empty, well-designed). Create a DEMO loan, send for
   approval, see it in the inbox (no tick box — money), then cancel it.
3. Run payroll: step 1 shows Regular / Top-up / Extra run with the new wording; pick Extra
   run, see the people picker; stop before computing (or compute for one DEMO person in a
   demo scheme and delete the draft run afterwards — only if the delete is clean).
4. Payslip review of a demo run: "Hold pay" action shows with the reason box; do not hold
   on a real tenant; on payobook hold one DEMO person, see the chip and the Pay & deliver
   group, then release the hold.
5. Finish the checks owed from the QF step if signed in as QA: approve two DEMO leave
   requests together (only if suitable ones exist), save and delete an Explorer view,
   sign out and in again.
Then the cheap checks on the other four sites (login page 200; served bundle contains one
new string from each phase).

## 5. Rules

- Kill switches: uninstalling is not one. For PR-B: no loan exists on any database, so
  it feeds nothing; if the seam itself misbehaves, restore from backup with the service
  stopped. For any wrong pay figure seen after start: stop, restore that database, put
  the previous trees back, report.
- Never change customer data beyond the upgrade itself. No setting changes.
- Usage-limit error mid-deploy: finish the database you are on, START the service, write
  DONE/FAILED in the deploy notes, then PAUSED. Never leave the service stopped.

## 6. Report back — `docs/handovers/wdgap/WDGAP_PR_DEPLOY_REPORT.md` (commit + push)

Merge result and seam checks 2a–e; combined test counts; §2 numbers; rehearsal recompute
proof; versions before → after ×5; downtime; hash/version/cron verification; the walk;
anything held; owner questions as plain real-world questions; new gotchas → ledger.

Final message: under 300 words.
