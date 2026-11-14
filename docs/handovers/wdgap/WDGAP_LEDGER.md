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
| QF1 | Approvals inbox: approve selected. Home: PayAI's daily alerts | built + merged into `19.1` (branch `wdgap-qf-merge`): biz_approval_workflow 19.0.1.8.0, pb_approval_config 19.0.1.9.0, pb_payroll_ai_insights 19.0.3.13.0, pb_dashboard 19.0.2.3.0; report `WDGAP_QF1_REPORT.md` |
| QF2 | Explorer: named saved views + share, Excel download, send regularly by email | built + merged: pb_explorer 19.0.2.7.0; report `WDGAP_QF2_REPORT.md` |
| QF3 | Leave on My Payobook: half days/hours, withdraw / ask to change, attach certificate, balance after | built + merged: pb_ess_workforce 19.0.1.4.0, pb_timeoff 19.0.1.11.0, pb_me_team 19.0.1.2.0, pb_attendance_flow 19.0.1.4.0, pb_today 19.0.1.6.0, pb_schedule 19.0.1.10.0; report `WDGAP_QF3_REPORT.md` |
| QF4 | Goal scores into the pay review. Benefits: enrol joiners, end cover for leavers | built + merged: pb_goals 19.0.1.5.0, pb_pay 19.0.3.8.0, pb_comp_ben 19.0.1.8.0, pb_hiring 19.0.2.23.8, pb_probation 19.0.1.6.0, pb_offboarding 19.0.1.6.0; B5 board line and B6 lens not built (owner questions); report `WDGAP_QF4_REPORT.md` |
| QF5 | Compulsory two-step sign-in by role, idle sign-out | built + merged: biz_access 19.0.1.13.0 (both settings ship OFF); report `WDGAP_QF5_REPORT.md` |
| PR-B | Loans and salary advances with a running balance — new module `pb_loans` | built on branch `wdgap-prb` (not merged, not deployed): pb_loans 19.0.1.0.0; report `WDGAP_PR_B_REPORT.md` |
| QF-deploy | Merge QF1–QF5, prove the combination, live on all five databases (risky tier) | handover `WDGAP_QF_DEPLOY_HANDOVER.md`; report `WDGAP_QF_DEPLOY_REPORT.md` |

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

Row ids carry their phase (`QF1-W1`, `QF4-W1`, `QF5-W1` …): the five phases were built in
parallel and each numbered its own rows from W1, so the merge prefixed them. A phase report
that says "W3" means that phase's row.

| # | Phase | Gotcha |
|---|---|---|
| QF1-W1 | QF1 | After an asset purge the browser kept serving the OLD stylesheet: the bundle address (`/web/assets/5513470/web.assets_web.min.css`) did not change although the file did, so the cached copy won. A `fetch(url, {cache: 'reload'})` (or a `web.assets.version` bump on the server) refreshed it. Check a CSS fix by asking the stylesheet for the new rule, not by reloading. |
| QF1-W2 | QF1 | `pb_approval_config/static/src/scss/inbox.scss` ends with the `.pbam-drawer { … }` block, not the inbox root: rules appended before the final `}` compile as `.pbam-drawer .x` and never reach the cards. New inbox rules go in their own `.pbim.pbam-inbox { … }` block. |
| QF1-W3 | QF1 | A local server started on a copy runs the overdue PayAI daily job within seconds and (since QF1) resolves alerts a fixture made by hand. For browser walks start the server with `--max-cron-threads=0`. |
| QF1-W4 | QF1 | Local copies of the template (`upd_p6_t_tpl`): `admin` (uid 2) is ARCHIVED — sign-in says "Access Denied" and engine decisions by uid 2 say "Your account is no longer in use" (the cause of the pb_timeoff test errors there). A pay run inserted by SQL also needs `active = true` or Home keeps the first-payroll checklist (which hides the row of cards). |
| QF1-W5 | QF1 | Home's row of cards (People, Pay runs, Hiring, PayAI noticed) is not drawn while the "Get your first payroll out" checklist shows (no pay run yet). A database with no pay run never shows the PayAI card. |
| QF2-G1 | QF2 | `records.with_context(some_dict)` CARRIES OVER `allowed_company_ids` from the old context when the new dict leaves it out (Odoo 19 `BaseModel.with_context`). Popping the key and passing the dict does not remove it: a job's or caller's companies became the recipient's and `env.companies` raised "Access to unauthorized or invalid companies". **Fix:** Set `allowed_company_ids` explicitly to the target user's own companies (default first) when running `with_user(other)`. |
| QF2-G2 | QF2 | A module-level helper that calls `_()` (pb_explorer `_measure_words` etc.) has no language in a scheduled job (no web request): English text and one "no translation language detected" WARNING per word. **Fix:** `_get_lang` reads a local called `context` from the calling frame first: give the helper `context = {'lang': …}` from a context variable the job sets (`pb_explorer.WORDS_LANG`), or use `env._()`. |
| QF2-G3 | QF2 | In Odoo 19 tests `threading.current_thread().testing` is not set, so a "skip `cr.commit()` in tests" guard on it lets the commit through and the test fails ("Cannot commit or rollback a cursor from inside a test"). **Fix:** Check `odoo.modules.module.current_test`. |
| QF2-G4 | QF2 | `pb_explorer` `test_look_p4.test_w8b` greps explorer.js for `[A-Za-z]\(s\)` (bracketed plurals): a JS parameter named `s` (`editSchedule(s)`) trips it. **Fix:** Never name a parameter `s` in explorer.js. |
| QF2-G5 | QF2 | The local Mac disk is nearly full (0.5–3 GB free on 2026-11-14): a four-module test run with `--log-level=test` (≈400k log lines) hit "No space left on device"; a 2 GB walk-copy database cannot be made. **Fix:** `--log-level=info`, run suites in halves, drop scratch databases at once, seed a small database for the browser walk. |
| QF2-G6 | QF2 | Local server keeps compiled asset bundles in memory: purging `/web/assets/%` attachments alone still served the old CSS. **Fix:** Purge AND restart the local server after an SCSS change. |
| QF2-G7 | QF2 | Claude in Chrome cannot make the window narrower than 614 px and the app refuses iframes (X-Frame-Options), so 390 px cannot be checked there. 614 px is under the Explorer's 620 px phone breakpoint, so phone rules do run. **Fix:** Check phone layout at 614 px; a true 390 px check needs device emulation (chrome-devtools, when free). |
| QF3-1 | QF3 | Parallel phase agents of one session SHARE the scratchpad folder: a generic `shell.sh` / `run_suite.sh` / `logs/` was overwritten by another phase mid-run. Keep every phase's scripts, configs and logs in a subfolder named after the phase (`scratchpad/qf3/`). |
| QF3-2 | QF3 | The local disk is nearly full (≈200 databases). Copies of the 2.3 GB test templates (`upd_p5e_y9`, `upd_p5e_pay`) failed with "No space left on device"; two `createdb -T <same template>` at once failed with "buffer is pinned". Use the ~150 MB templates (`upd_p6_t_tpl`, `upd_p5_t_full2`; vi + id installed), one createdb at a time, and drop your own databases AND `~/odoo19/data/filestore/<db>` when done. |
| QF3-3 | QF3 | `sudo()` on the employee pages made every request look like HR's own entry: `pb_timeoff`'s past-date refusal never fired AND a late sick-leave request never alerted HR. The rule is now one method (`hr.leave._pb_backdate_verdict(vals, as_officer=False)`) that the employee path asks explicitly before the sudo create. |
| QF3-4 | QF3 | hr_holidays' `can_cancel`, computed `with_user(plain internal login)`, raises AccessError ("not available for employee public profiles"): `_check_approval_update` reads `employee_id.leave_manager_id`. Catch it and restate the own-leave rule (approved, starts in the future). |
| QF3-5 | QF3 | hr_holidays refuses a request over the balance unless the kind "allows going below zero" (`_check_validity`), so a preview may only say "you can still send it" for those kinds. |
| QF3-6 | QF3 | `biz.approval.engine.cancel` calls the record's `_approval_withdraw` inside a bare try/except (no savepoint). A hook that writes must hold its own savepoint, or a database error there leaves the withdrawal's transaction aborted. |
| QF3-7 | QF3 | Locally, a running server kept serving the previous frontend CSS after `DELETE … /web/assets/%`; only a restart picked up the changed SCSS (same lesson as "asset purge alone does not refresh browsers"). |
| QF4-W1 | QF4 | The local test template `upd_p3c_t_tpl` is behind HEAD: a `-u` run with the 19.1 tree logs "Model pb.updates.ytd.* has no table" as ERROR. Add `pb_updates` (and `pb_clock`, UPDATES G97) to the first `-u` of a new local base copy, then copy that base for test runs. The admin user on that template is archived — activate it on the LOCAL copy before a browser walk. |
| QF4-W2 | QF4 | Odoo 19's `hr.employee.action_unarchive` writes `departure_date=False` right after un-archiving, and the departure wizard archives FIRST then writes the date. Anything hooked on `hr.employee.write` for exits sees two writes, in that order; make the second one "follow" rather than refuse. |
| QF4-W3 | QF4 | `.pbim-badge` has `text-transform: capitalize` — a sentence put in it reads "3 Have A Score". Override `text-transform: none` locally for count/sentence badges. List `widget="badge"` chips are upper-cased by the theme: give the column a `width` or they truncate ("START…"). |
| QF4-W5 | QF4 | The Mac's data volume sits at ~99% (5 GB free): a full six-module suite hit `psycopg2.errors.DiskFull` mid-run and one pb_hiring test errored for that reason only. Check `df -h /System/Volumes/Data` before a full run, drop your scratch copies (`dropdb --force`) as you go, and re-run any test that shows DiskFull before calling it a failure. |
| QF4-W4 | QF4 | `pb_goals` cycle form button `action_close` is an xpath ANCHOR for `view_pb_goal_cycle_form_b2` (`goal_year_views.xml:446`). Removing it breaks the inherited view; hide it (`invisible="1"`) instead. |
| QF5-W1 | QF5 | `get_param` is cached in the `stable` ORM cache (`ir_config_parameter.py:72`). A psql `UPDATE ir_config_parameter` is NOT seen by running workers until the cache is signalled: add `INSERT INTO orm_signaling_stable DEFAULT VALUES;` in the same psql session. Every "kill switch by psql" needs both statements. |
| QF5-W2 | QF5 | The web client page `/odoo` is `auth='none'` in core (`web/controllers/home.py:46`), and on our databases `/odoo` answers **301** to `/bizapp` (biz_deroute). A request hook that skips `auth='none'` never sees the web client page; an HttpCase that expects 200 from `/odoo` gets 301 — use `/bizapp` where biz_deroute is installed. |
| QF5-W3 | QF5 | A JSON call that ends in `SessionExpiredException` is an error response and the framework does NOT save the session afterwards: a server-side `session.logout()` in `_authenticate` must be followed by `root.session_store.save(request.session)` or the next call finds the old session again. |
| QF5-W4 | QF5 | `HttpCase.authenticate` sets `_trace_disable` on the session, so no `res.device.log` row is ever written in tests; anything that signs people out through devices (`res.device._revoke`) needs the test to create the device row for the session itself (`sid[:STORED_SESSION_BYTES]`). |
| QF5-W5 | QF5 | `assertLogs('odoo', level='DEBUG')` captures `odoo.sql_db` query lines, which print written values (a second-factor secret included). Assert "never in the logs" at INFO, the level the servers run at. |
| QF5-W7 | QF5 | Local walk: after an asset purge the first request for a not-yet-built bundle answered **301**, and the browser CACHED that redirect — the My Payobook pages then ran no JavaScript at all (no error in the console). Fetch the bundle once with `cache:'reload'` (or clear the browser cache) before judging a frontend change. Also: file edits to a JS/XML asset are not picked up locally until the `/web/assets/%` attachments are purged. |
| QF5-W6 | QF5 | Local disk was full (under 1 GB free, 207 local databases ≈ 63 GB): a second 2.3 GB copy of a base database cannot be made, and a full suite run failed half-way with "No space left on device". Run in place on the phase's own copy and keep local copies to one per phase. |
| PRB-W1 | PR-B | A chain consumer's `register_chain(date_field=…)` is the date the engine asks "who holds this responsibility ON that date" (`responsibility.resolve` → `_covers(on_date)`). With `date_field='first_month'` a loan whose first pay month was before the Head of pay's start date found nobody and the request went **blocked** with no seat. **Fix:** pb_loans registers no date field (the holder today decides). Check any consumer whose date can be in the past. |
| PRB-W2 | PR-B | In application-data mode a source answering `consumption_required=True` is blocked UNCONDITIONALLY (`application_payroll_source.py:838`: status forced to missing, "needs a paid-once reservation") — nothing ever lifts it, so the awards source (`awards.*`) can never be paid in that mode. **Fix (PR-B):** `loans.instalment` answers `resolved` with the amounts in its evidence and reserves in `hr.payslip._application_resolve_inputs` (the period-input pattern). |
| PRB-W3 | PR-B | Pay data file path: an input pay item with NO column in the file still received another column's value (a "Holiday gift" item got the basic salary, 10,000,000) — the resolver's column-letter / loose header binding (UPDATES G32 family). Test files must carry a column (0) for every input of the scheme. Importer behaviour, not changed here. |
| PRB-W4 | PR-B | The no-file path reads the contract wage only for the codes `BASIC` / `WAGE` / `BASE`; a fixture basic pay coded otherwise computes 0. |
| PRB-W5 | PR-B | A `t-att-*` expression `'%s%% paid back' % x` in a portal QWeb template rendered as `%s% …` and raised "not enough arguments for format string" — the whole `/my/loans` page became the error page while every Python test passed. **Fix:** build such strings with `str(x) + '…'`; browser-walk every new portal page. Also: the employee home's root is `.pbme-home`, not `.pbme` — styles for a `_pbme_extra_cards` card scoped under `.pbme` never apply. |
| PRB-W6 | PR-B | `pb_payruns` `TestRunScreen` fails 5 tests on any local copy during a close week: `pb_close` adds two `close_week` items to the run checklist the tests do not expect. Date-dependent baseline, not a regression (proven on a copy without the new module). |
| QFM-1 | QF deploy | `biz_access` is the product-agnostic layer: `tests/test_access_generic.py` (`TestNoProductNameInTheGenericLayer`) fails if any of its markup names the product. QF5 added "My Payobook logins are not included yet." to `access_board.xml`; the phase run missed it, the combined full suite caught it (the only new failure). Changed to "Employee self-service logins are not included yet." (vi too). **Fix:** in `biz_*` modules use neutral words, never the product name; run `/biz_access` in full after any change there. |
