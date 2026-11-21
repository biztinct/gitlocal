# WDGAP Step 5 go-live — merge, go live ×5, verify (S5-A, S5-B, S5-C)

Method: EXACTLY as `WDGAP_W2B_DEPLOY_HANDOVER.md` → `WDGAP_W2_DEPLOY_HANDOVER.md` /
`WDGAP_PR_DEPLOY_HANDOVER.md` and the command sequence proven in
`WDGAP_W2B_DEPLOY_REPORT.md` (all in `origin/19.1` or the main checkout's
`docs/handovers/wdgap/`). Read those, `WDGAP_LEDGER.md`, `WDGAP_WAVE_RULES.md`,
`WDGAP_S5_HANDOVER.md` ("Step go-live note"), `WDGAP_S5_FACTS.md` ("Shared files inside
S5"), and the three phase reports on their branches:
`WDGAP_S5A_REPORT.md` (`origin/wdgap-s5a` 2daa86a7d, NEW `pb_leave_setup`, edits
`pb_timeoff`), `WDGAP_S5B_REPORT.md` (`origin/wdgap-s5b` 9b3ed4379, NEW `pb_time_pay`),
`WDGAP_S5C_REPORT.md` (`origin/wdgap-s5c` a8c34597f, NEW `pb_shift_patterns`). Each
report has its own deploy notes — follow them. Only the differences are written here.

Databases: `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima` ONLY (never
`abm`, `pbf_preview`, `recruit_connect_20261023`). RISKY tier (S5-B touches what can
reach a payslip; three new modules). ONE addons dir `/odoo/odoo-server/addons` on ssh
alias `Payobook19v2`; clean staging; per-module scoped `rsync -a --delete` (NEVER
`--delete` into the addons root); never deploy vendored standard addons; deploy from the
pushed commit via `git archive`; verify hashes + `latest_version` ×5; asset purge +
`web.assets.version` bump; read/append `/opt/deploy-notes.md` START/DONE; never go live
over another deployer's open START ("Claude WORKFLOW-2", "Codex" also deploy); never
leave the service stopped. White-label: the word "Odoo" never in anything an end user
can see. Never commit passwords, `outputs/`, `SUDIMA/`, `RIZE/`. Explicit-path staging,
no `git stash`, no force-push. Commit messages end with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never touch `pb_lifecycle/`
or `pb_pack_*`.

## 1. Merge (branch `wdgap-s5-merge` from `origin/19.1`; order: s5a, s5b, s5c)

Expected conflicts: ledger (UNION), report files, possibly `.po` headers. Version
raises the builders left for you (S5-B stayed in lane): `pb_hr_payroll_formula`
19.0.1.168.0 → 19.0.1.169.0, `pb_source_atlas` 19.0.1.14.0 → 19.0.1.15.0, `pb_mission`
19.0.1.13.1 → 19.0.1.14.0 (check current values on `origin/19.1` first; raise from
whatever is there), plus any others the three reports list (`pb_timeoff`, `pb_close`,
`pb_schedule` …). Seams to test on the merged tree:
a. S5-B creates a "Time off in lieu" kind without knowing S5-A's new fields → with
   `pb_leave_setup` installed the kind is created with defaults, shows correctly on the
   Kinds of leave screen, never builds up, never expires (owner ruling L4).
b. S5-A "balances ignore expired days" + S5-B in-lieu hours: an in-lieu balance is
   never reduced by expiry.
c. S5-C generated drafts + S5-B overtime suggestions: a draft (unpublished) pattern
   shift is NOT used as the published shift for the comparison; once published it is.
d. Mission Control: S5-C "Patterns" lens and S5-B Close-lens section load in one assets
   bundle; ⌘K rows of all three present; browser smoke on the local copy, console clean,
   also at phone width for the Kinds of leave screen and the employee leave page (S5-A
   could not check phone width).
Combined local run: install the three new modules on one test database
(`wdgap_s5m_t`); all three phases' new tests together; full suites of every touched
module — failure set equals the union of the recorded baselines. Remove leftover
`wdgap_s5*` databases (list first; touch no other builder's database — seven other
builders are running on this Mac, use your own port and browser address). Never wait
silently on a background run — poll with a bounded loop. Ledger phase map; push to
`origin 19.1` (never force; if 19.1 moved, merge it in and re-run the gates).

## 2. Rehearsal — short, by owner agreement (rize/sudima not in real use yet)

Backups of all five first (mandatory). Practice upgrade on a `rize` copy (jobs + mail
off before the live service can touch it; `dropdb --force` after): install/upgrade
cleanly, and old-vs-new recompute of ONE recent rize pay run — identical line for line
(rize has trial runs only; use the most recent computed run; if none can be recomputed,
say so and use the sample below instead). `payobook` copy NOT needed; instead on the
rize copy also check that nothing new appears: no leave kinds created, no build-up
posted, no overtime suggestion rows written, no job that sends anything. Any payslip
difference → do NOT go live; report scheme, person, line, both figures.

## 3. Read-only live checks before anything changes

Deploy notes (open START by anyone → wait/hold and report), disk, cron snapshot (job
156 OFF on payobook and the 8 template jobs — compare after), dependencies of the three
new modules installed ×5 (if a dependency is missing on a database, do not
force-install it: report and skip that module on that database).

## 4. Go live — same RISKY sequence

`-u` the edited modules and `-i pb_leave_setup,pb_time_pay,pb_shift_patterns` ×5; asset
purge + restart. After: hashes, `latest_version` ×5, cron counts equal the snapshot
(new quiet jobs from these modules listed by name; none sends mail), silent-install
proof per database (no new leave kinds, no allocations posted, no rows in the new
tables). Tenant email is off on purpose on rize/sudima/p0clone — do not raise or fix.

## 5. Check on the real system (payobook.com, QA login; look-only where it would email
a real person; keep demo data — add only, delete nothing)

Settings › HR → Kinds of leave opens; ready-made kinds for Vietnam offered as "A
starting point" (look, do not apply on a real tenant; on payobook apply for ONE demo
company only if cleanly reversible by switching off — else look only). Employee leave
page shows balances. Mission Control → Patterns tab opens empty; ⌘K rows. Weekly Close
shows the "Time into pay" section; Overtime desk shows "Pay it / Give time off". One
existing demo payslip PDF still opens. Then the cheap open-the-screen checks on the
other four sites.

## 6. Report — `docs/handovers/wdgap/WDGAP_S5_DEPLOY_REPORT.md` (commit + push to 19.1)

Merge + seams; combined test counts; §3 numbers; rehearsal proof and duration; versions
before → after ×5; downtime; verification; the walk; anything held; gotchas → ledger.
Carry forward ALL owner questions from the three phase reports as plain real-world
questions in one list. Final message under 300 words, plain English (screen words, no
code names). Usage-limit error mid-deploy: finish the database you are on, START the
service, write DONE/FAILED in the deploy notes, then PAUSED at the top of the report.
