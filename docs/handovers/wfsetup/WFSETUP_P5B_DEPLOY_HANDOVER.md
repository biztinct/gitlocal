# WFSETUP P5b — merge, rehearse, go live on sudima + payobook, verify

You are the deploy agent. Read first: the repo `CLAUDE.md` "Deploy contract" (binding, word for word), `WFSETUP_LEDGER.md`,
`WFSETUP_OWNER_RULINGS.md` (R2: **sudima + payobook first**), `WFSETUP_FACTS.md` §J.2, `WFSETUP_P5A_REPORT.md` (the
module/version table is your manifest of what ships), the "payroll person should double-check" list in `WFSETUP_P3_REPORT.md`.
Clone the scripts and structure of the most recent comparable go-lives rather than inventing new ones:
`/Users/adity/Documents/GitHub/gitlocal/docs/handovers/formstudio/FS_DEPLOY_HANDOVER.md`,
`/Users/adity/Documents/GitHub/gitlocal/docs/handovers/docstudio/DOCSTUDIO_W2_DEPLOY_HANDOVER.md` and the Codex release notes
`docs/handovers/workforce-workspace/RELEASE_STATUS.md` (prep → rehearsal on a hidden tenant copy → go-live → verify).

Tier: **RISKY** (new module install, a new install of the rules module on payobook, a pay-rate resolution fix, an access
widening for holidays). Full ritual: backups, rehearsal on a copy, then the real databases.

## 0. Hard rules
- Server alias `Payobook19v2`. ONE addons directory `/odoo/odoo-server/addons`. Never `--delete` into the addons root; only
  per-module scoped `rsync -a --delete`. Never deploy the repo's vendored standard addons. **Never touch `abm`.**
- Read `/opt/deploy-notes.md` first. Another deployer's START without DONE → stop and report. Append START before and
  DONE/FAILED after (format in that file). Take `flock /tmp/payobook-studio-deploy.lock`.
- Announce to other live sessions (ListAgents → SendMessage) before any restart; a peer's reply is not owner approval, and
  none is needed (standing owner OK to deploy/restart) — but WAIT if a peer says a deploy is in progress.
- Never deploy during customer activity: 15 quiet minutes on sudima and rize (activity check as in the precedent scripts).
- A database copy on the live server gets its scheduled jobs run by the live service within a minute: create the copy,
  and IMMEDIATELY switch off every scheduled job and outgoing mail server in it, before anything else. Never leave a login
  usable on a copy; `dropdb --force` it at the end. (Ledger of past incidents: memory notes "copy DB runs live crons",
  "clone DBs are internet-reachable".)
- Cron snapshot per database before and after (count of active jobs; the boolean-print trap: compare counts, do not grep
  `,f$`). Expected NEW active jobs: the rules module's 15-minute calculation job on payobook (first install there) and
  whatever `pb_workforce_setup` itself adds (see its `data/`); anything else that flips → restore it. payobook's reminder
  jobs are intentionally OFF and locked — they must still be off afterwards. payobook_template's jobs are intentionally all off.
- No credentials in any file you commit. Evidence goes under `/tmp/wfsetup-<date>/` on the server and a non-sensitive
  receipt in the repo.
- **On the live databases you do not press "Confirm" on the rules step and you do not publish a roster.** Those are the
  customer's decisions. Your live walk is read-only plus one harmless edit that you undo (below).

## 1. What ships
From `WFSETUP_P5A_REPORT.md` module table. Expected shape (verify against the table; the table wins):
| Module | sudima | payobook | rize, payobook_template, p0clone |
|---|---|---|---|
| `pb_workforce_setup` (new) | install | install | **not installed** (row in `docs/deploy/PENDING.md`) |
| `pb_attendance_policy` (unchanged code) | already installed | installed as a dependency | not installed |
| `pb_hr_workforce` (rate fix, version bump) | upgrade | upgrade | upgrade |
| `pb_workforce_workspace` (takeover/trim, version bump) | upgrade | upgrade | upgrade |
Code for every changed module lands on disk for all five databases at once (one addons dir), so the two upgraded modules
MUST be upgraded on all five in the same window; only the install of the new module is limited to sudima + payobook.

## 2. Steps
1. **Merge**: in a fresh worktree from `origin/19.1` (never the shared checkout), merge `wfsetup`; resolve conflicts
   conservatively (if `pb_workforce_workspace` or `pb_hr_workforce` changed upstream since `8067b4834`, re-run the affected
   suites locally before going on); run the full wfsetup suite + the suites in the P4/P5a reports once on the merge result;
   push to `origin/19.1`. Stage from `git archive` of the pushed commit, named modules only.
2. **Prep on server**: deploy-notes START; lock; quiet check; cron snapshots; backups ×5 (`pg_dump -Fc` into
   `/odoo/backups/`, sizes recorded; keep sudima's and rize's).
3. **Rehearsal** on a hidden copy of **sudima** (copy → jobs + mail off at once → stage to a SEPARATE addons path for the
   rehearsal run only, as the precedent scripts do, so live code is untouched): install/upgrade exactly as §1 for sudima;
   then on the copy, signed in as a throwaway manager you create and delete:
   - all seven steps open with real data: 678 people in step 3 (time to first paint, typing in search, tick a team);
   - step 2 shows the three existing working weeks as editable weeks; step 6 shows the six clocks;
   - step 7 check: time for the plan with 678 people; numbers plausible against 12,384 existing planned shifts;
   - ON THE COPY ONLY: add VN 2027 holidays; set the unconfirmed worker 1–9 minute late line to 0 hours and Confirm the
     rules → people count 678, shifts re-pointed count; publish 2 weeks → published counts equal the confirm panel, zero
     duplicates per person/day, nothing of another company touched; the 15-minute calculation job run ONCE by hand on the
     copy produces attendance for a past published day without errors (record the count), then stop;
   - the existing suites listed in the P5a report with `--test-tags` on the copy, baseline failures only.
   Drop the copy (`dropdb --force`), its filestore, the rehearsal addons path and the throwaway login. Any failure here
   stops the go-live: report, do not improvise.
4. **Go-live**: clean staging dir; per-module scoped rsync; stop the service; per database, one at a time, detached unit with
   an exit sentinel (precedent): sudima and payobook `-i pb_workforce_setup -u pb_hr_workforce,pb_workforce_workspace`;
   rize, payobook_template, p0clone `-u pb_hr_workforce,pb_workforce_workspace`. Stop at the first failure and restore that
   database from its backup before starting the service. Allow only the known pre-existing log ERROR lines (precedent list).
   Asset purge + `web.assets.version` bump per database; start; warm each site with one request.
5. **Verify**: hash every changed module tree on both sides (skip `__pycache__`, `*.pyc`, `.DS_Store`) — byte identical;
   manifest versions vs `ir_module_module.latest_version` in all five (normalise the `19.0.` prefix); `pb_workforce_setup`
   state installed on exactly sudima + payobook; cron counts vs snapshot (+ the expected new ones); sites HTTP 200.
6. **Live walk (Chrome tools)**:
   - payobook.com with the QA login (it may lack attendance rights — if so use the demo manager login the precedent used and
     say so): Settings › HR › Workforce setup opens the studio; walk steps 1–7; one harmless edit and undo (rename a working
     week and rename it back; tick three people → Give a working week → Apply → **Undo**); Workforce menu shows the four tabs.
   - sudima.payobook.com: open the studio; steps 1–7 render with 678 people, three working weeks, six clocks; the Workforce
     menu is trimmed; NO writes at all. Console clean on both. Save two or three screenshots of each site to the evidence folder.
7. **Close**: deploy-notes DONE with downtime seconds; add the PENDING row (install `pb_workforce_setup` on rize,
   payobook_template, p0clone when the owner says); commit a non-sensitive receipt `WFSETUP_P5B_REPORT.md`; release the lock.

## 3. Report back (`WFSETUP_P5B_REPORT.md`)
Timeline with UTC times; downtime seconds; backup files and sizes; rehearsal numbers (paint time for 678 people, plan time,
confirm counts, publish counts, calculation job result); per-database versions table; hash result; cron before/after;
live walk results; anything you were unsure about and what you chose; what the owner should look at first.
If anything fails after the service is stopped: restore, start, verify sites are up, THEN report. On a usage limit: leave
the server in a consistent running state first, then "Where I stopped", end with PAUSED.
