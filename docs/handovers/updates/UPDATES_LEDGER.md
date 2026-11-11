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
| D5 | The user never picks a pay scheme. The scheme is read per person from their contract; the match drop-down offers employee/contract fields plus the components of the schemes present in the file; a value for a component that is not in that person's scheme is greyed and skipped; new joiners need a "Pay scheme" column (P2). |
| D7 | **Sudima gets Updates** (owner, 2026-11-11). UPDATES deploy set = `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`. Never `abm`, `pbf_preview`, `recruit_connect_20261023`. |
| D8 | **QA login**: the owner approved resetting the payobook.com QA password from the server (2026-11-11). The password lives only in the memory note `payobook-qa-login`, never in the repo. Live write walks use DEMO people and are always undone. |
| D6 | A blank cell means "leave alone" (already the desk's rule). Removing a value is explicit (`CLEAR`, P2). |

## Phase map

| Phase | Scope | Status |
|---|---|---|
| P1 | Front door: home, download sheet, upload own file, remembered column matching, review grid with on-screen fixes, apply via the desk, named batches, history, undo | LIVE ×4 2026-11-11 (pb_records 19.0.1.8.4, pb_updates 19.0.1.0.1); report UPDATES_P1_REPORT.md |
| P2a | Safe name look-ups in the desk (G11), full-roster speed, stale test, Sudima, QA reset + live write walk | LIVE ×5 2026-11-11 (pb_records 19.0.1.8.5; pb_updates 19.0.1.0.1 now also on sudima); report UPDATES_P2A_REPORT.md |
| P2b | Scheme-aware pay items (D5): per-person scheme via `pb.scheme.map.resolve_many`, greyed cells, CLEAR | not started |
| P2c | "Starts from" dates incl. future-dated, pay history, one-offs into a named pay month | not started |
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
  rsync, four DBs `payobook`, `payobook_template`, `p0clone`, `rize`, never `abm`), plus
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
| G16 | 2026-11-11 | The export picks a person's contract with `_io_contracts` (latest start date, HIGHEST id on a tie); the desk's evaluation uses `_get_latest_contract` (latest start date, LOWEST id on a tie, because `contract_ids` is in id order and the reverse sort is stable). Two contracts with the same start date can therefore show one contract in the sheet and judge against another. | Not changed in P2a (no tie on payobook's untouched round trip: 0 changes). Fix by making the two agree before P2c touches contracts. |
| G17 | 2026-11-11 | `hr.employee` "creates when missing" (it has a `name` field), so a typed manager or coach name that matches nobody is proposed as a NEW employee "(new)". | Existing behaviour, kept by P2a rule 5 of the ladder; owner decision in UPDATES_P2A_REPORT §8. |
| G18 | 2026-11-11 | A local `--no-http` test run still refused to start because another local server held port 8069. | Pass `--http-port`/`--gevent-port` on a free port as well. |
| G19 | 2026-11-11 | Odoo 19 starts the web listener whenever `--test-enable` is set, `--no-http` or not (`odoo/service/server.py:659`). In a stopped-service window the P2a test process bound 8069, served live requests (a sudima websocket) and hung 6 minutes in shutdown, stretching the downtime to 10 min. | Always pass `--http-port`/`--gevent-port` on free ports for test runs on the live box; better, run the suites AFTER the service is started, on those ports (TransactionCase only). |
