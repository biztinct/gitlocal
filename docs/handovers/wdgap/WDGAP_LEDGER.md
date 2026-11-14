# WDGAP programme — ledger (conventions, decisions, gotchas)

Every WDGAP handover references this file. Add a row whenever a new gotcha is hit.

## What the programme is

Closing the gaps found by the Workday-vs-Payobook study of 2026-11-14
(`outputs/workday-gap-study-2026-11-14/payobook-vs-workday.html`, research rows in
`outputs/workday-gap-study-2026-11-14/research-data/*.json`, build order in `roadmap.json`
beside it — `outputs/` is never committed). 1,172 features compared; 75 open "must" items.
The programme works through the study's build order, one step at a time.

## Owner decisions — do not re-ask

| # | Decision |
|---|---|
| D1 | **Phased workflow** (owner, 2026-11-14): Fable designs and writes the handover, an Opus agent implements, tests and self-reviews in the same session, phases back to back. Fable does not bulk-review code. |
| D2 | **Build-order Step 1 (country tax/insurance numbers in the packs) is POSTPONED** (owner, 2026-11-14). Do not touch `pb_pack_*` rates or tax methods in this programme until the owner re-opens it. |
| D3 | **Start with the quick fixes (study Step 3)**, then the later steps in order. Step 2 (government tax files, year-end certificates, fund files) waits with Step 1, because those files print the numbers Step 1 corrects. Bank payment files for other countries do not depend on tax and may be built. (owner, 2026-11-14) |
| D4 | **Every finished phase goes live on all customers**: `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`. Never `abm`. (owner, 2026-11-14) |
| D5 | **Step by step with a short plain report between steps**; carry straight on unless the owner says otherwise. Stop only for a destructive/irreversible action or a real scope decision. (owner, 2026-11-14) |
| D6 | **Back-ups copied off the server: later.** Build compulsory two-step sign-in by role and idle sign-out now; back-ups stay as they are until the owner chooses where copies go. (owner, 2026-11-14) |

## Phase map

| Phase | Scope | Status |
|---|---|---|
| QF1 | Approvals inbox: approve selected. Home: PayAI's daily alerts | designing |
| QF2 | Explorer: named saved views + share, Excel download, send regularly by email | designing |
| QF3 | Leave on My Payobook: half days/hours, withdraw / ask to change, attach certificate, balance after | designing |
| QF4 | Goal scores into the pay review. Benefits: enrol joiners, end cover for leavers | built + tested on `wdgap-qf4` (report `WDGAP_QF4_REPORT.md`); B5 board line and B6 lens not built (owner questions) |
| QF5 | Compulsory two-step sign-in by role, idle sign-out | designing |

## Binding conventions (every phase)

1. **White-label**: the word "Odoo" never appears in anything a user can see or receive
   (labels, help, errors, toasts, emails, exports, `.po` msgstr). Technical identifiers,
   comments, logs and these docs keep the real name.
2. **Plain words on screen**: use the vocabulary already on Payobook's screens. No model
   names, codes or jargon in user-visible text. Lucide icons, never emoji. Design mandate
   (owner, verbatim): "extreme WOW, best in class". Palette and component rules:
   memory `payobook-design-system` — primary indigo `#5A4BB0`, white cards, no gradients,
   quiet boards (grey at zero, colour only to act).
3. **Translations**: every new user-visible string gets `vi` and `id` entries in the
   module's `i18n/*.po` where those files exist. A PO entry needs the three things in the
   PO loading rules (see `docs/handovers/updates/UPDATES_LEDGER.md` and the LOOK ledger:
   a translation fix is TWO fixes — the `.po` and any stored value).
4. **Inherited gotcha ledgers — read before coding in the area**:
   `docs/handovers/updates/UPDATES_LEDGER.md`, `docs/handovers/workflow2/WF2_LEDGER.md`,
   `docs/handovers/APPROVAL_MATRIX_LEDGER.md`, `docs/handovers/NAV_LEDGER.md`, and
   `CLAUDE.md` (deploy contract). Known traps that recur: `t-out` of a NEW `markup()`
   re-inserts DOM every redraw; hub lenses must be tested inside their hub (no-scroll
   trap); OWL imports from `@pb_import_kit/js/`; v19 `group_ids` not `groups_id`;
   `safe_eval` limits; asset purge alone does not refresh browsers.
5. **Work in the phase's own git worktree/branch.** Other sessions ship from the shared
   folder. Stage explicit paths only (never `git add .` / `-A`). One feature-scoped commit
   per validated feature. Never commit anything under `outputs/`, `SUDIMA/`, or a
   password. Commit message ends with the attribution line given in the handover.
6. **Version bump** every module whose Python/XML/data changes (so `latest_version`
   proves the upgrade ran); looks-only changes keep the version.
7. **Build agents do not deploy.** One deploy-and-verify agent per step ships the merged
   work, under the deploy rules below.
8. **Demo data**: never delete demo data on payobook.com; test records use DEMO people and
   are undone; no "RIZE" in demo names; no ZZ records.
9. **Tenant email is off on purpose** on `rize`, `sudima`, `p0clone`. Anything that sends
   mail must behave well with no outgoing mail server: say so on screen, never error,
   never raise it as a fault.
10. **Never upgrade or restart during an owner demo**; read `/opt/deploy-notes.md` first.

## Deploy rules (the deploy agent)

Server alias `Payobook19v2`. ONE addons directory `/odoo/odoo-server/addons`. Full contract
in `CLAUDE.md`; tiers in memory `tiered-deploy-rule`:
- looks-only: rsync + asset purge + `web.assets.version` bump + `orm_signaling_assets` row;
- normal: stop → `-u` each DB one at a time → purge/bump → start;
- risky (stored-data rewrite, new module install, pay calculation, security/access):
  backups first (`sudo -u postgres pg_dump -Fc db > /odoo/backups/...` from root),
  rehearse on a clone with jobs and mail servers switched off (`copy-db-runs-live-crons`),
  then the real DBs.
Always: clean staging dir; per-module scoped `rsync --delete`; never `--delete` into the
addons root; never deploy vendored standard addons; hash-compare every module both sides;
compare manifest version to `ir_module_module.latest_version` in all five DBs; append
START/DONE lines to `/opt/deploy-notes.md`; cron snapshot before/after a base-module
upgrade (`cron-snapshot-boolean-trap`); warm each site with one curl after restart; one
browser walk on payobook.com with the QA login (memory `payobook-qa-login`), console
clean.

## Gotchas hit in this programme

| # | Phase | Gotcha |
|---|---|---|
| W1 | QF4 | The local test template `upd_p3c_t_tpl` is behind HEAD: a `-u` run with the 19.1 tree logs "Model pb.updates.ytd.* has no table" as ERROR. Add `pb_updates` (and `pb_clock`, UPDATES G97) to the first `-u` of a new local base copy, then copy that base for test runs. The admin user on that template is archived — activate it on the LOCAL copy before a browser walk. |
| W2 | QF4 | Odoo 19's `hr.employee.action_unarchive` writes `departure_date=False` right after un-archiving, and the departure wizard archives FIRST then writes the date. Anything hooked on `hr.employee.write` for exits sees two writes, in that order; make the second one "follow" rather than refuse. |
| W3 | QF4 | `.pbim-badge` has `text-transform: capitalize` — a sentence put in it reads "3 Have A Score". Override `text-transform: none` locally for count/sentence badges. List `widget="badge"` chips are upper-cased by the theme: give the column a `width` or they truncate ("START…"). |
| W5 | QF4 | The Mac's data volume sits at ~99% (5 GB free): a full six-module suite hit `psycopg2.errors.DiskFull` mid-run and one pb_hiring test errored for that reason only. Check `df -h /System/Volumes/Data` before a full run, drop your scratch copies (`dropdb --force`) as you go, and re-run any test that shows DiskFull before calling it a failure. |
| W4 | QF4 | `pb_goals` cycle form button `action_close` is an xpath ANCHOR for `view_pb_goal_cycle_form_b2` (`goal_year_views.xml:446`). Removing it breaks the inherited view; hide it (`invisible="1"`) instead. |
