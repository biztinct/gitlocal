# WDGAP QF — merge, go live ×5, verify (step "Quick fixes")

Read first: `WDGAP_LEDGER.md` (deploy rules section), repo `CLAUDE.md` (deploy contract),
the five phase reports — each has a "Deploy notes" section and new gotchas:
`WDGAP_QF1_REPORT.md` (branch `wdgap-qf1`), `…QF2…` (`wdgap-qf2`), `…QF3…` (`wdgap-qf3`),
`…QF4…` (`wdgap-qf4`), `…QF5…` (`wdgap-qf5`) — and
`docs/handovers/updates/UPDATES_LEDGER.md` G12, G19, G35, G93–G99, plus the latest UPDATES
deploy reports for the proven command sequences (`UPDATES_P6_REPORT.md`, `UPDATES_P5E_REPORT.md`).
Memory notes that bind deploys (read them in
`/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/memory/`):
`payobook-deploy.md`, `tiered-deploy-rule.md`, `deploy-notes-file.md`,
`cron-snapshot-boolean-trap.md`, `copy-db-runs-live-crons.md`, `payobook-qa-login.md`,
`keep-demo-data-payobook.md`, `never-deploy-abm.md`, `usage-limit-pause.md`.

Owner decision (ledger D4): every finished phase goes live on all five databases —
`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`. Never `abm`, `pbf_preview`,
or any other database. Standing approval to deploy/restart exists; still never during an
owner demo and never over another deployer's open START.

Fable has read the QF5 sign-in kernel (gates, rules, setup page) and found nothing to
change. QF5 ships with both settings OFF; you must leave them OFF everywhere.

## 1. Merge

1. New worktree from `origin/19.1`, branch `wdgap-qf-merge`. Merge `origin/wdgap-qf1` …
   `origin/wdgap-qf5` one at a time (`--no-ff`). The modules are disjoint by design; the
   expected conflicts are `docs/handovers/wdgap/WDGAP_LEDGER.md` (take the UNION of all
   gotcha rows and keep D1–D6) and possibly `.pot`/`.po` headers. Any code conflict:
   stop and report rather than guess.
2. Combined gates on the merged tree: py_compile on every changed `.py`, XML well-formed,
   PO parse gate, and grep the merged diff vs `origin/19.1` for "Odoo" in user-visible
   strings (none allowed).
3. Combined local test run on a fresh local copy: `-u` every module the five reports list
   and run the five phases' new test files together (all must pass), then the full suites
   of the touched modules and confirm the failure set equals the union of the baselines
   the five reports recorded (no new failure from the combination). The Mac's disk is
   nearly full (≈6 GB free): drop each local test database as soon as you are done with
   it, and drop any leftover `wdgap`/phase test databases you find from the five builders
   (list them first; only ones clearly created today by these phases).
4. Update the ledger phase map (QF1–QF5 → built, with versions), commit, then bring
   `origin/19.1` up to date: if it moved, merge it into your branch and re-run gate 2;
   push the result to `origin 19.1` (no force, ever).

## 2. Read-only checks on live BEFORE anything is changed (report each number)

a. `ssh Payobook19v2 cat /opt/deploy-notes.md` — someone else's START without DONE → stop
   and report.
b. Disk and memory on the server (`df -h`, `free -m`); room for five backups.
c. Cron snapshot per database (id, name, active — mind the boolean trap).
d. **Benefits** (QF4): per database, count `pb.benefit.enrollment` rows with
   `state='active'` and `end_date < today`. These would flip to "Ended" on the new nightly
   job's first run.
e. **Mail** (QF2): per database, is there an active `ir.mail_server` row? And for
   `payobook`: is outgoing mail configured only in `/etc/odoo-server.conf` (smtp_*)? Report
   facts only — do not configure anything.
f. **Leave units** (QF3): per database, `hr.leave.type` counts by `request_unit`
   (day / half_day / hour), with the names of the non-day ones on `rize`.
g. PayAI (QF1): per database, count of `payroll.ai.pulse` rows in state new/acknowledged
   (they have no company and will simply not show on Home — confirm that is what happens
   after deploy).
h. Which of the touched modules are installed on which database (some are not installed
   everywhere — upgrade only where installed; never install a module that is not there).

## 3. Go live — RISKY tier (sign-in path + new tables + new scheduled jobs)

1. Append START to `/opt/deploy-notes.md`; take the flock.
2. Backups of all five databases (from root, `pg_dump -Fc` — see memory for the path trap).
3. Rehearsal: copy `rize` to a throwaway database with jobs and mail servers switched off
   BEFORE the live service can run them (memory `copy-db-runs-live-crons`); upgrade the
   module set there; confirm EXIT=0 and no ERROR/CRITICAL/Traceback beyond the known
   harmless warning; confirm sign-in still works on it by a session authenticate call;
   `dropdb --force` it afterwards.
4. Stage from the pushed commit (`git archive` of it — never the shared working tree,
   G93/G94): clean staging dir; rsync only OUR modules that changed; per-module scoped
   `rsync -a --delete` into `/odoo/odoo-server/addons/<module>/`. Never `--delete` into
   the addons root. Never deploy vendored standard addons.
5. Stop the service; confirm zero `odoo-bin` processes; `-u <modules installed there>` on
   each database one at a time, stopping at the first failure (if one fails: restore that
   database from its backup, put the previous module files back from the previous commit,
   start the service, report — do not continue to the next database).
6. Per database: asset purge, `web.assets.version` bump, signaling row.
7. **Benefits guard**: on any database where check 2d was not zero, set the new benefits
   nightly job (name in the QF4 report) to inactive right after the upgrade and before
   the service starts; report the database and the count. Leave it active elsewhere.
8. Start the service; wait for the registry; warm each of the five sites with one curl.
9. Verify: hash every deployed module tree both sides (skip `__pycache__`, `*.pyc`,
   `.DS_Store`); manifest version vs `ir_module_module.latest_version` ×5; cron snapshot
   diff (only the new jobs added; nothing re-activated that was off — fix any that an
   upgrade switched back on, using the snapshot); log grep since start.
10. Confirm on all five: `biz_access.two_step_required` empty/absent and
    `biz_access.idle_minutes` 0/absent.
11. Append DONE (or FAILED) to `/opt/deploy-notes.md`; release the flock.

## 4. Check it on the real system (payobook.com, QA login from memory; Claude in Chrome)

One calm walk, console open, nothing destructive, DEMO people only, undo what you create:
1. Home: the page loads; the "PayAI noticed" card shows or is quietly absent; no error.
2. Approvals inbox: tick boxes appear only on cards that are the QA login's turn and of
   an allowed kind; a money kind shows a disabled box with its reason. Approve two DEMO
   leave requests together only if suitable ones exist; otherwise do not create any — say so.
3. Insights › Explorer: save a view, find it under My views, download Excel (opens, one
   block per currency), open "Send regularly" and read what it says about email; delete
   the view afterwards.
4. My Payobook as a DEMO employee if a login is available in memory: the leave form shows
   the "after this request" line; do not send a request unless you withdraw it straight after.
5. Pay review: the "Read scores from Goals" button shows; open the preview; do not press
   "Use these scores".
6. Access home: the new "Two-step sign-in is required for" and "Sign people out after"
   card shows with Nobody / Off selected. Do NOT change either setting.
7. Sign out and sign in again: normal, no extra page.
Then the cheap automated checks on the other four sites (login page 200, served bundle
contains one string from each phase).

## 5. Rules

- If anything on live looks wrong after start and you cannot explain it within a few
  minutes, the kill switches are: QF5 SQL in its report; set the new jobs inactive;
  restore-from-backup is the last resort and needs the service stopped. Report honestly.
- Never change customer data beyond what the upgrade itself does. No setting changes.
- Usage-limit error mid-deploy: finish the database you are on, START the service so
  nobody is left down, write DONE/FAILED in the deploy notes, then PAUSED in your report.
  Never leave the service stopped.
- Commit messages end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  (the builders used this line; keep it consistent).

## 6. Report back — `docs/handovers/wdgap/WDGAP_QF_DEPLOY_REPORT.md` (commit + push)

Merge result (conflicts, combined test counts); the numbers from every check in §2;
versions before → after per module ×5; downtime in minutes; hash/version/cron
verification; the walk, step by step, with what you saw; anything left off or held (e.g.
the benefits job on a database); owner questions as plain real-world questions; new
gotchas → ledger rows.

Final message to the orchestrator: under 300 words — pushed commit, live or not on each
of the five, downtime, test counts, the §2 numbers (benefits rows, mail servers, leave
units on rize), anything held, anything that failed.
