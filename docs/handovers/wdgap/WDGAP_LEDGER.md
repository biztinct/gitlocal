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
| QF4 | Goal scores into the pay review. Benefits: enrol joiners, end cover for leavers | designing |
| QF5 | Compulsory two-step sign-in by role, idle sign-out | built + tested on branch `wdgap-qf5` (not merged, not deployed); report `WDGAP_QF5_REPORT.md` |

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
| W1 | QF5 | `get_param` is cached in the `stable` ORM cache (`ir_config_parameter.py:72`). A psql `UPDATE ir_config_parameter` is NOT seen by running workers until the cache is signalled: add `INSERT INTO orm_signaling_stable DEFAULT VALUES;` in the same psql session. Every "kill switch by psql" needs both statements. |
| W2 | QF5 | The web client page `/odoo` is `auth='none'` in core (`web/controllers/home.py:46`), and on our databases `/odoo` answers **301** to `/bizapp` (biz_deroute). A request hook that skips `auth='none'` never sees the web client page; an HttpCase that expects 200 from `/odoo` gets 301 — use `/bizapp` where biz_deroute is installed. |
| W3 | QF5 | A JSON call that ends in `SessionExpiredException` is an error response and the framework does NOT save the session afterwards: a server-side `session.logout()` in `_authenticate` must be followed by `root.session_store.save(request.session)` or the next call finds the old session again. |
| W4 | QF5 | `HttpCase.authenticate` sets `_trace_disable` on the session, so no `res.device.log` row is ever written in tests; anything that signs people out through devices (`res.device._revoke`) needs the test to create the device row for the session itself (`sid[:STORED_SESSION_BYTES]`). |
| W5 | QF5 | `assertLogs('odoo', level='DEBUG')` captures `odoo.sql_db` query lines, which print written values (a second-factor secret included). Assert "never in the logs" at INFO, the level the servers run at. |
| W7 | QF5 | Local walk: after an asset purge the first request for a not-yet-built bundle answered **301**, and the browser CACHED that redirect — the My Payobook pages then ran no JavaScript at all (no error in the console). Fetch the bundle once with `cache:'reload'` (or clear the browser cache) before judging a frontend change. Also: file edits to a JS/XML asset are not picked up locally until the `/web/assets/%` attachments are purged. |
| W6 | QF5 | Local disk was full (under 1 GB free, 207 local databases ≈ 63 GB): a second 2.3 GB copy of a base database cannot be made, and a full suite run failed half-way with "No space left on device". Run in place on the phase's own copy and keep local copies to one per phase. |
