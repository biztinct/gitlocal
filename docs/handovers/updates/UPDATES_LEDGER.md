# UPDATES programme — ledger (conventions, decisions, gotchas)

Every UPDATES handover references this file. Add a row whenever a new gotcha is hit.

## What the programme is

One front door, **Updates** (People › Updates), for bulk spreadsheet changes to employee
details, contract fields, ongoing pay components, bank details and (later) one-off pay
items — usable any day, separate from the pay run. Prototype (the visual and interaction
reference): `docs/design/updates-desk-prototype.html`.

It is **not a new write engine**. Every value is evaluated, written, audited, routed for
approval and undone by `pb.records.desk` (`pb_records`). UPDATES adds a guided front door,
column matching for files the desk did not export, a person × column review grid, named
batches with the original file kept, and — in later phases — dates, scheme-aware
components, new joiners and split approval.

## Owner decisions (2026-11-11) — do not re-ask

| # | Decision |
|---|---|
| D1 | The pay run's pay data file becomes **month-only**; lasting changes come through Updates (enforced in P3, not before). |
| D2 | **One contract + dated pay history.** No new contract per pay change. Consistent with the Records Desk ruling of 2026-08-29 (contract written in place). |
| D3 | **Approval split by type**: person details apply at once; pay changes go to approval; bank details always need a second person (P3). |
| D4 | Phased workflow: Fable designs, Opus implements and self-tests, phases back to back. |
| D5 | The user never picks a pay scheme. The scheme is worked out per person by the scheme map (`pb.scheme.map.resolve_many`, the pay run's own resolver) — it is NOT a contract field (corrected 2026-11-11); the match drop-down offers employee/contract fields plus the components of the schemes present in the file; a value for a component that is not in that person's scheme is greyed and skipped; new joiners need a "Pay scheme" column (P2). |
| D7 | **Sudima gets Updates** (owner, 2026-11-11). UPDATES deploy set = `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`. Never `abm`, `pbf_preview`, `recruit_connect_20261023`. |
| D8 | **QA login**: the owner approved resetting the payobook.com QA password from the server (2026-11-11). The password lives only in the memory note `payobook-qa-login`, never in the repo. Live write walks use DEMO people and are always undone. |
| D6 | A blank cell means "leave alone" (already the desk's rule). Removing a value is explicit (`CLEAR`, P2). |
| D9 | **Unknown manager / coach name is refused, never created** (owner, 2026-11-11). Namesakes stay refused; the person can type an employee code or work email instead of a name (P2c). |
| D10 | The undone live-check entries on payobook's Past updates stay (owner, 2026-11-11). Do not remove them. |

## Phase map

| Phase | Scope | Status |
|---|---|---|
| P1 | Front door: home, download sheet, upload own file, remembered column matching, review grid with on-screen fixes, apply via the desk, named batches, history, undo | LIVE ×4 2026-11-11 (pb_records 19.0.1.8.4, pb_updates 19.0.1.0.1); report UPDATES_P1_REPORT.md |
| P2a | Safe name look-ups in the desk (G11), full-roster speed, stale test, Sudima, QA reset + live write walk | LIVE ×5 2026-11-11 (pb_records 19.0.1.8.5; pb_updates 19.0.1.0.1 now also on sudima); report UPDATES_P2A_REPORT.md |
| P2b | Scheme-aware pay items (D5): per-person scheme via `pb.scheme.map.resolve_many`, complete pay-item list grouped by scheme, greyed cells, CLEAR, one contract definition (G16) | LIVE ×5 2026-11-11 (pb_records 19.0.1.8.6, pb_updates 19.0.1.1.0); report UPDATES_P2B_REPORT.md |
| P2c | Start dates (past = recorded, future = scheduled and written on the day), Start now, a real cancel for unwritten changes, pay-run awareness, employee look-ups by code/email (D9) | LIVE ×5 2026-11-11 (pb_records 19.0.1.9.0, pb_updates 19.0.1.2.0, pb_payrun_wizard template line); new hourly job on all five; report UPDATES_P2C_REPORT.md |
| P2d | One-off pay items into a named pay month (three stores today, U16; research first) | research running 2026-11-11 |
| P3 | Split approval by type + bank second check (D3), new joiners, drafts, "what changed since last run" line in the pay run, pay data file month-only (D1), retire the old employee import | not started |
| P4 | More sheet types: attendance/timesheets in the same four steps, leave balances, year-to-date figures | not started |

## Standing rules that bind every phase

- **White-label**: the word "Odoo" never appears in any user-visible string (labels, toasts,
  errors, help, `string=`, `.po` msgstr, exported files). Technical identifiers stay as they are.
- **Plain language on screen**: screen words, not code words. "pay scheme", "pay item",
  "employee record" — never model names, card ids or rule codes in a sentence a user reads.
- **Design**: indigo design system (`#5A4BB0` primary, white cards, Lucide icons via
  `@pb_import_kit/js/import_icons`, never emoji, no gradients, one solid primary button per bar).
- **Deploy contract**: repo `CLAUDE.md` § Deploy contract (one addons dir, per-module scoped
  rsync, the five DBs of D7, never `abm`), plus
  `/opt/deploy-notes.md` START/DONE lines and the flock `/tmp/payobook-studio-deploy.lock`.
- **Other sessions are live in this tree** (WORKFLOW-2 touches `pb_lifecycle`, `pb_hiring`,
  `pb_me_expense`, `pb_timeoff`). Never stage, edit, revert or deploy their files. Stage
  explicit paths only.
- **Demo data naming**: no "RIZE" in demo records; never delete demo data on `payobook`.
- **No credentials in the repo.** The repo is public.

## Verified plumbing facts (do not re-derive)

| # | Fact | Where |
|---|---|---|
| U1 | `config_id = 0` on the desk means **Master records**: a scheme-free catalogue of chosen `hr.employee` / `hr.contract` fields + four bank roles + every contract component that already has a line on some contract (`c:<CODE>` cards built from `hr.contract.advantage.template`). No scheme rules are consulted. | `pb_records/models/master_records.py:11-87` |
| U2 | Card ids: `f:<model>:<field>` · `b:<role>` · `c:<CODE>`; groups `employee`, `contract`, `bank`, `component`. Private keys start with `_` and are stripped by `_public_card`. | `pb_records/models/pb_records_desk.py:248-373` |
| U3 | `import_peek(config_id, file_b64, filename)` parses, places columns with `_io_columns`, matches rows with `_io_match`, and returns `changes` (`{emp_id, field_id, value}`), `items` (preview rows with `status` ok/same/refused + `why`), `unmatched` (with their `values`) and a `summary`. Writes nothing. Blank cells are skipped, never a clear. | `pb_records/models/pb_records_io.py:725-856` |
| U4 | `_io_columns` places a column five ways (header comment id, hidden `_payobook` sheet, the desk's own identity headings, a heading equal to a card label, the batch's looser identity spellings). Anything else is ignored. There is **no** user-driven mapping today. | `pb_records/models/pb_records_io.py:456-521` |
| U5 | Row matching ladder: code (across `barcode`, `employee_id`, `pb_source_ref`, `identification_id`, case-insensitive) → work email → exact normalised name; ambiguity is refused in a sentence. | `pb_records/models/pb_records_io.py:90,542-623` |
| U6 | `preview_changes(config_id, changes)` → `{items, counts}`; `apply_changes(config_id, changes, note, source)` re-evaluates server-side, creates `pb.records.apply` (`RD%05d`), and calls `biz.approval.engine.submit`; the answer carries `pending`, `with_whom`, `route`, `refused`, `written`, `people`. `source` accepts only `desk` / `import`. | `pb_records/models/pb_records_desk.py:1339,1659-1723` |
| U7 | `undo_apply(apply_id)` restores each stored before-value unless somebody changed it since; an undo is itself an apply (`source='undo'`) and takes no approval route. | `pb_records/models/pb_records_desk.py:1747-1845` |
| U8 | `export_records(config_id, filters, field_ids, mode)` writes the xlsx (hidden `_payobook` sheet + header comments carrying card ids); limits 10,000 rows / 10 MB; needs `_may_export()`. | `pb_records/models/pb_records_io.py:61-63,255` |
| U9 | Gates: `_may_read`, `_may_export`, `_may_write(model)`; groups `pb_records.group_records_viewer/editor/exporter`. | `pb_records/models/pb_records_desk.py:81-120`, `pb_records/security/records_groups.xml` |
| U10 | The desk is mounted in the People hub as a bolted-on lens through the registry category `pb_people_hub_lens`; the hub must never import the lens module (dependency cycle). | `pb_people_hub/static/src/js/people_hub.js:83-102` |
| U11 | A contract component's catalogue row is global, keyed by rule code (`hr.contract.advantage.template.code`), shared by every scheme that uses that code. | `pb_hr_payroll_formula/models/contract_fill_in.py:289-318` |
| U12 | JS import path needs the `js/` segment: `@pb_import_kit/js/import_icons`. Omitting it breaks the whole backend bundle. | memory: payobook-import-redesign |
| U13 | At approval time `PbRecordsApply._approval_apply` re-checks nothing moved (`_plan_moved_since`) then `Desk._write_plan` re-evaluates `changes_json` and writes. A "hold until a date" attaches between the two (new state, stored start date, daily job). `_component_log` stamps `effective_date = today`. | `pb_records/models/records_approval.py:59,323,343`; `pb_records_desk.py:1701,1771,1797` |
| U14 | The pay run reads a contract component's CURRENT line amount, never the dated history (`_contract_component_amounts` loops `contract.advantages_ids`). | `pb_hr_payroll_formula/models/payroll_import_batch.py:2212-2258`; `hr_payslip_formula.py:199,710` |
| U15 | `hr.contract.advantage.change.effective_date` is read only by history screens and by proration / automatic back pay, both only on the pay-file path with the scheme flag on. | `payroll_import_batch.py:2563-2659,2716-2729`; `formula_config.py:80,102` |
| U17 | Updates reaches the desk through `pb.updates.desk._desk()` = `pb.records.desk.with_context(records_scheme_items=True, records_strict_clear=True)`. The first adds a `c:<CODE>` card for every pay item of every visible scheme to Master records; the second switches on CLEAR's rules (required field refused, bank refused, amount → 0, empty → same). An apply linked to an Updates batch reopens the same context at approval and undo (`PbRecordsDeskUpdatesDoor._updates_door`). | `pb_updates/models/updates_desk.py` (`DOOR_CONTEXT`), `pb_records/models/master_records.py` (`_add_scheme_items`), `pb_records_desk.py` (`_coerce`, `_evaluate`), `pb_updates/models/updates_schemes.py` |
| U18 | "Is this pay item in this person's scheme" lives in ONE place, `pb.updates.desk._is_off_scheme(ctx, emp_id, field_id)` over `_scheme_context` (people's scheme ids from `resolve_many` for `any` + every cycle type on the map, the schemes' pay-item codes, and lines already on the contract). `review`, `recheck`, `apply` (`_drop_off_scheme`) and the sheet all ask it. | `pb_updates/models/updates_schemes.py` |
| U19 | Withdrawing an approval request = `biz.approval.engine.cancel(request, reason)`: submitter or approval admin only (call it under `sudo()` after your own gate), open states `pending`/`blocked` only, closes seats, then calls the record's `_approval_withdraw`. `pb.records.apply._approval_withdraw` (P2c) sets `cancelled`. | `biz_approval_workflow/models/engine.py:1458-1493`; `pb_records/models/records_approval.py` |
| U20 | P2c dates: `pb.records.apply.start_date` (empty = today's path), states `scheduled`/`cancelled`, hourly job `ir_cron_records_start_scheduled` → `_cron_start_scheduled` → `_start_scheduled` (row lock, moved-since, `_plan_drift`, `_write_plan` in a savepoint). "Today" for a start date is the COMPANY's (`_today_for`: company address tz → user tz → UTC; clock seam `_records_now`). Effective date of written values: `_effective_date` (context `records_effective_date` › past start date › today). | `pb_records/models/records_approval.py`, `pb_records_desk.py` |
| U16 | One-offs for a month live in three stores: `hr.payroll.period.input` (own draft/approved state, read in application-data mode), `pb.payroll.month.inputs` (JSON, no approval, read by the monthly-template pay-file path), `pb.oneoff.feed` (stores nothing; pushes approved `pb.incentive` awards into a computed run). No single store. | `payroll_period_input.py:35,253,417-450`; `pb_payroll_templates/models/templates.py:69,525-530`; `pb_comp_ben/models/oneoff_feed.py:101,440` |

## Gotcha ledger

| # | Date | Gotcha | Rule |
|---|---|---|---|
| G1 | 2026-11-11 | Odoo 19 ignores `_sql_constraints` silently. | Use `models.Constraint` class attributes. |
| G2 | 2026-11-11 | A `.po` entry needs `#. module:`, `#. odoo-python`/`#. odoo-javascript` and `#: code:addons/...:0`, or the load crashes or drops it silently. | Run a parse gate on every `.po` before deploy. |
| G3 | 2026-11-11 | A wrong name in a JS service's `dependencies` blanks the entire web client with no server error. | Chrome MCP + console read before calling any screen done. |
| G4 | 2026-11-11 | The desk refuses EVERY cell of a field that is read-only on the record (`_coerce` checks `editable` before `_same`), even when the file holds exactly today's value. A Master-records sheet includes such fields (e.g. dependent count, currency), so a sheet sent straight back showed 26 "needs attention" cells. | Updates never offers a read-only field (sheet + "Goes to" list) and shows a refused cell whose file value equals the value on record as "stays the same". Desk unchanged. |
| G5 | 2026-11-11 | A heading such as "Employee Name" / "Employee ID" matches the NAME / CODE field by label in `_io_columns` step 4, i.e. as a value to WRITE, before the looser identity spellings of step 5. | `read_columns` re-reads a label match onto an identity field (barcode, employee_id, identification_id, pb_source_ref, name, work_email) as "finds the person" when that identity is still free. |
| G6 | 2026-11-11 | Odoo's string extractor misses `_t(...)` inside a JS template-literal placeholder (`` `${_t("…")}` ``) and `_()` called on a variable; both stay English with no warning. | Literal calls only; build the `.po` from `odoo-bin i18n export -l pot` so the extractor's own view is the source of truth. |
| G7 | 2026-11-11 | A class name reused between two screens of the same root (`.pbu-who` on the start screen and on the grid's person cells) turned table header cells into flex boxes. | One class, one meaning per root; pin `display: table-cell` on grid cells. |
| G8 | 2026-11-11 | `--logfile=<dir>` fails when the folder was created by root and odoo-bin runs as `odoo`: it logs to stdout instead ("couldn't create the logfile directory"). | Create evidence folders writable by `odoo`, or grep the captured stdout. |
| G9 | 2026-11-11 | Tests that count ALL batches/layouts break on any database that already holds some (seen on a local copy after a browser walk). | Count before/after; look a layout up by its own heading fingerprint. |
| G10 | 2026-11-11 | The QA login in memory (`payobook-qa-login`) was refused on 2026-11-11 (user active, no 2FA, write_date 2026-10-27). An agent may not reset it or sign in with a password on the live host. | Owner resets or re-issues the QA password; until then live walks are read-only through an existing session. |
| G11 | 2026-11-11 | The desk resolves a named reference (working hours, schedule, department, manager, coach) by NAME (`=ilike`, `limit=1`). On payobook an untouched full sheet read as 9,933 changes: namesake records picked instead of the current one, and a department's full path ("A / B") proposed as a NEW department. | Updates treats file text equal to what is shown on record today as no change (server `_same_text` + screen `sameText`). The ambiguity itself was a desk defect — FIXED in P2a (`_coerce` name ladder: current value, company scope, full path, namesakes refused); the Updates guard stays as a second belt. |
| G12 | 2026-11-11 | A `--test-enable` run on the live box while the service is stopped binds the web port, so live requests reach the test process; on its shutdown they log "Failed to load registry" / "bad query" (8 ERROR lines in the follow-up test log, all after the tests finished). | SUPERSEDED by G19: `--no-http` does NOT help when tests are enabled. Use `--http-port`/`--gevent-port` on free ports. |
| G13 | 2026-11-11 | A local test run against the working tree failed to load the registry ("Model 'pb.me.home' does not exist") because ANOTHER session had uncommitted, half-done work in other modules of the same tree. | Test from an isolated snapshot: `git archive HEAD` into a scratch folder, overlay only your own modules, point a copy of the local config's `addons_path` at it. |
| G14 | 2026-11-11 | Every attribute of every record passes through `biz_access`'s `__getattribute__` hook (14-25 million calls on one full-roster sheet). Re-reading the same mapping row per cell, and asking the label helper the same question per cell, cost more than the reads themselves. | In bulk paths: copy the few attributes a shared helper reads into a `_LightRow` once per call, and memoise answers that depend only on (column, value) for that call. Never bypass the guarded value read itself. |
| G15 | 2026-11-11 | `hr.department.complete_name` is NOT stored in Odoo 19: it is computed with a custom search that loads every department and, for `=ilike`, treats `%` and `_` as wildcards. | Search it through the ORM (it is searchable), never `store`-gate it; filter wildcard hits exactly in Python. |
| G16 | 2026-11-11 | The export picks a person's contract with `_io_contracts` (latest start date, HIGHEST id on a tie); the desk's evaluation uses `_get_latest_contract` (latest start date, LOWEST id on a tie, because `contract_ids` is in id order and the reverse sort is stable). Two contracts with the same start date can therefore show one contract in the sheet and judge against another. | FIXED in P2b: `_io_contracts` keeps the lower id on a tie (test B11). `_get_latest_contract` unchanged. |
| G17 | 2026-11-11 | `hr.employee` "creates when missing" (it has a `name` field), so a typed manager or coach name that matches nobody is proposed as a NEW employee "(new)". | Existing behaviour, kept by P2a rule 5 of the ladder; owner decision in UPDATES_P2A_REPORT §8. |
| G18 | 2026-11-11 | A local `--no-http` test run still refused to start because another local server held port 8069. | Pass `--http-port`/`--gevent-port` on a free port as well. |
| G19 | 2026-11-11 | Odoo 19 starts the web listener whenever `--test-enable` is set, `--no-http` or not (`odoo/service/server.py:659`). In a stopped-service window the P2a test process bound 8069, served live requests (a sudima websocket) and hung 6 minutes in shutdown, stretching the downtime to 10 min. | Always pass `--http-port`/`--gevent-port` on free ports for test runs on the live box; better, run the suites AFTER the service is started, on those ports (TransactionCase only). |
| G20 | 2026-11-11 | The Chrome DevTools MCP browser profile was held by another session ("browser is already running for …chrome-devtools-mcp/chrome-profile"); killing it would break that session. | Use the Claude-in-Chrome tools for the walk instead; never kill another session's browser. |
| G21 | 2026-11-11 | A helper file that `_inherit`s `pb.updates.desk` and is imported (for a constant) by `updates_desk.py` gets its class defined BEFORE the model's own class: registry load fails "Model 'pb.updates.desk' does not exist". | Keep shared constants in the file that defines the model; helper files import from it, never the reverse. |
| G22 | 2026-11-11 | Pay schemes and pay items are per COMPANY in scope (`env.companies` / the `cids` cookie). With "Your Company" active the catalogue had no pay items at all; schemes of another company show their items as "Kept on contracts only". | Test and walk Updates in the company the people belong to (payobook: Payobook Vietnam JSC, id 5). |
| G23 | 2026-11-11 | On payobook every demo-world contract carries a line for every saved pay item (most at 0), so the "already on the contract" exception makes almost no demo value greyed; and no scheme in company 5 has a pay item of its own. | To see greying, use a person with a scheme and no contract line (e.g. no contract), or a scheme pay item no contract has yet (local copies only). |
| G25 | 2026-11-11 | A cron method that commits per record (`env.cr.commit()`) raises "Cannot commit or rollback a cursor from inside a test" in a TransactionCase; `threading.current_thread().testing` is NOT set in Odoo 19. | Guard the commit with `odoo.modules.module.current_test`. |
| G26 | 2026-11-11 | A real second database connection opened inside a TransactionCase (to prove a two-cursor race) blocks for ever on the test transaction's own uncommitted fixture rows (an `INSERT INTO resource_resource` waiting on a lock). | Prove races in a standalone `odoo-bin shell` script on a throwaway local copy that commits its own fixture (`c10_race.py`). |
| G27 | 2026-11-11 | An AbstractModel recordset (`env['pb.records.desk']`) is EMPTY, so `desk or default` silently picks the default — a test passed the wrong desk and failed for a reason that looked like a code bug. | Never `or` a model; use `x if x is not None else default`. |
| G28 | 2026-11-11 | `pb.records.apply` is not a mail thread: `mail.activity.create` calls `message_subscribe` on the target model and fails. | Put a proposer's activity on the apply's approval request (`biz.approval.request`, a mail thread), with `mail_activity_quick_update` so no email goes out. |
| G29 | 2026-11-11 | The approval engine marks a request "applied" (and logs "was carried out") as soon as `_approval_apply` returns True — so a SCHEDULED change's request reads as carried out on the approvals screen while nothing is written yet. | The apply's own state is the truth (`scheduled`); Updates and Records read that. Fixing the engine's word is a separate, engine-wide change. |
| G30 | 2026-11-11 | With a person's own column choice, `import_peek` lists every headed column that is not a value or an identity as "Not brought in" — a column the caller reads itself (the start date) showed up there. | `import_peek(extra_columns=…)` drops those columns from the ignored list (Records screen never passes it). |
| G24 | 2026-11-11 | The P1 cases ran with whatever scheme the test database's main company resolves to; on a company with one active scheme, T18's "pay item for a contract without that line" would be greyed by design. | `test_updates.py` pins `_people_schemes` to "nobody known"; scheme behaviour has its own cases in a company of its own (`test_updates_p2b.py`). |
