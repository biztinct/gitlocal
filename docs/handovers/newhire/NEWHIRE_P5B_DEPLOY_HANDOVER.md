# NEWHIRE P5b — merge to 19.1 and go live (RISKY tier: new module install)

Read first: `NEWHIRE_LEDGER.md`, `NEWHIRE_P5A_REPORT.md` §0 and §5 (the go-live table — your module list; verify it
against `git diff origin/19.1...newhire --stat`, do not trust it blind), `NEWHIRE_FACTS_ONBOARD.md` §M (the recipe, M2,
is binding step by step — **do not re-derive**), and as the worked precedent
`docs/handovers/wfsetup/WFSETUP_P5B_DEPLOY_HANDOVER.md` + its report. Root `CLAUDE.md` deploy contract binds.

## Scope
1. One small fix first (worktree `gitlocal-worktrees/newhire`): step 2's summary line names only what is still missing
   (today it says "Team, job and country needed" even when two are filled). Test + commit.
2. Merge `origin/19.1` into `newhire` again (others ship all day), re-run `pb_new_hire` + touched-module suites
   (same-before/after rule), then merge `newhire` into `19.1` (no fast-forward games: a normal merge commit) and push
   `origin/19.1`. If the push is rejected, fetch, merge, re-test, retry. Never force-push.
3. Deploy from `git archive` of the pushed commit:
   - **Shared modules whose manifest version changed** (P5A §5 table: `pb_scheme_map`, `pb_probation`,
     `pb_hr_payroll_formula`, `pb_people`, `pb_learn`, and any other the diff shows): files to the one addons dir,
     `-u` on ALL FIVE databases (`payobook_template → p0clone → sudima → rize → payobook`).
   - **`pb_new_hire`**: files to the one addons dir; `-i` on **payobook ONLY** (ledger decision: payobook first; the
     other four get it after the owner has seen it). On the other four the module must stay uninstalled and the old
     Add employee window must keep working — verify on rize after the restart.
   - Before staging, diff every module you ship against the server's copy and confirm the only differences are ours:
     other sessions deploy uncommitted or newer work; never roll a module back. If the server copy of a shared module
     is NEWER than 19.1, stop and report.

## Binding non-goals / rails
- Never touch any database named `abm`, nor `_test_sudima_policy_20261119`. Never `rsync --delete` into the addons root.
  Never deploy vendored standard addons.
- `/opt/deploy-notes.md`: read it first; an open START or a HOLD from anyone (a WFSETUP P10b clock-pay deploy is in
  progress today in another session) → wait and re-check every 10 minutes, up to 2 hours, then report instead of
  deploying. Append START / DONE / NOTE in the house format. Take the flock.
- Quiet check, job snapshot (compare COUNTS), backups ×5 (`/odoo/backups/newhire-<ts>/`, again right before the stop),
  rehearsal on a hidden copy of **payobook** AND of **rize** (jobs + mail servers off at once; separate addons path;
  rehearse the exact `-u`/`-i` commands; on the rize copy prove the old window still opens and no row changed;
  `dropdb --force` both afterwards). Any rehearsal error → stop, report, deploy nothing.
- Rollback plan written in the report BEFORE the stop: restore files from the pre-deploy tar of each module dir +
  `pg_restore` only if data changed; decide per failure, and never restore a database without reporting first unless
  the site is down.
- Tenants rize / sudima / p0clone have outgoing mail off on purpose — do not fix, do not mention as a fault. The
  studio's reminder job exists only where the module is installed (payobook). payobook is a demo site with reminder
  jobs locked off: after install set the studio's reminder job **inactive** on payobook and say so; keep demo data.
- payobook_template: jobs an upgrade re-activated go off again (M2 step 8).
- No credential, client name or client data in any commit or report. QA login details come from the server/owner
  memory, never written into the repo.

## Verify (all of it)
Hashes both sides per shipped module; manifest vs `latest_version` ×5 (normalised) + `tools/deploy_status.py`; job
counts vs snapshot; server log 0 ERROR since start; all five sites 200.
Browser (Claude-in-Chrome, QA login on payobook.com; console clean):
L1 People › Employees › Add employee opens the seven-step screen; L2 fill steps 1–3 for a DEMO-named person on an
Indonesian and a Vietnamese team — currency, pay scheme and the payslip example are right; L3 step 5 and step 6 render;
L4 **send one DEMO hire and approve it** (demo data is welcome on payobook; name starts "DEMO"), then: employee record,
contract in the right currency, joining checklist, New joiners row, welcome page reachable; contract letter PDF is
produced (it could not be tested locally — NH: no PDF tool on the Mac); L5 is a document reader configured? report
yes/no per database (drives the bank-paper default); L6 Hiring › "Confirm they joined" opens the studio; L7 the Learn
lesson "Add your first employee" plays; L8 org chart "add a person here"; L9 Vietnamese user sees Vietnamese (report
which of the five databases have vi_VN / id_ID active); L10 on **rize** (read-only look, create nothing): Add employee
still opens the old window, Employees list wage column shows each contract's own currency.
Add a row to `docs/deploy/PENDING.md`: `pb_new_hire` live on payobook only; pending on the other four.

## Report back — `NEWHIRE_P5B_REPORT.md`
Timeline, downtime seconds, per-database exit codes, verification table, L1–L10 results with what was seen, anything
left behind (rehearsal copies dropped? backups path), deviations, open items. Commit report + PENDING row on 19.1 and
push. Final message to the architect: short plain summary — live or not, per database, what failed, open questions.
