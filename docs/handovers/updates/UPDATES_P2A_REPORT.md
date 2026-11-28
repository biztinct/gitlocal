# UPDATES — Phase 2a report (safe name look-ups, speed, Sudima, live walk)

Implemented, tested, deployed ×5 and walked live on 2026-11-11 by the Opus implementation
agent, against `UPDATES_P2A_HANDOVER.md` and `UPDATES_LEDGER.md`.

**Shipped:** `pb_records` 19.0.1.8.5 (live on `payobook`, `payobook_template`, `p0clone`,
`rize`, `sudima`); `pb_updates` 19.0.1.0.1 unchanged, newly installed on `sudima`.
Never `abm` (database absent).

Commits: `8ef43b54d` (ladder + golden fixture, before any speed work) · `4e3ba89ca`
(speed + version + translations) · `d586ad7fd` (item 3 corrected after the live run) · the
report/ledger commit that carries this file.

---

## R1. Tests

### New: `pb_records/tests/test_records_p2a_lookups.py` (13 tests)

| # | Case | Result |
|---|---|---|
| A1 | `test_A1_namesake_never_displaces_the_current_value` — person in the 2nd "P2A Twin"; "P2A Twin" and "  p2a   twin " both `same` | PASS |
| A2 | `test_A2_namesake_for_somebody_in_neither_is_refused` — `refused`, "2 department records are called 'P2A Twin'. Pick the right one on the Records screen, or use a name that is unique."; nothing planned | PASS |
| A3 | `test_A3_full_path_resolves_to_the_child_without_a_create` — "P2A Root / P2A Ops" → the child, no "(new)"; somebody already there → `same`; applied; department count unchanged | PASS |
| A4 | `test_A4_full_path_matching_nothing_is_refused_never_created` — slash sentence; apply writes nothing, no department created; a plain new name (no slash) is still proposed "(new)" (unchanged) | PASS |
| A5 | `test_A5_another_companys_namesake_is_not_seen` — company A's record picked; with A's archived, B's is still never picked | PASS |
| A6 | `test_A6_unique_name_any_case_and_stray_spaces` — "p2a lone", "  P2A LONE  " resolve | PASS |
| A7 | `test_A7_the_on_screen_picker_is_exact` — `{id}` exact incl. a namesake id; missing id refused "That choice no longer exists." | PASS |
| A8 | `test_A8_manager_named_by_a_shared_name_is_refused` — refused; the person already under that namesake stays `same`; a unique manager name resolves | PASS |
| — | `test_working_hours_namesake_keeps_the_current_one` (the live G11 case) | PASS |
| A9 | `test_A9_golden_preview_is_identical` — 262 Master + 60 scheme items (322 changes) covering `f:` char / number / date / selection / boolean / many2one, `b:` all four roles, `c:` amount and text, no-contract people and an out-of-company person; compared with `tests/data/p2a_golden_preview.json` captured in `8ef43b54d` BEFORE the speed work | PASS (identical) |
| A9b | `test_A9b_memoised_reads_equal_direct_reads` — every Master card × 21 people, twice: memoised read == direct read; label == the shared helper on the REAL mapping | PASS |
| A10 | `test_A10_memo_dies_with_the_evaluation` — a rename between two previews is seen by the second | PASS |
| — | `test_memo_is_shared_inside_one_evaluation` — 20 people naming one department: exactly 1 search | PASS |

Golden provenance: the same fixture captured on the pre-phase code differs from the
committed golden in exactly 28 of 322 items, all of them namesake / full-path /
already-current cases (e.g. "P2A Root / Nope" was "ok … (new)", now refused; a person
already under the 2nd "P2A Same" was "ok", now "same"). Every unambiguous value is identical.

### A11 — item 3 (`test_01a…`) and the full `pb_records` suite

**Deviation, found live:** the handover's premise ("scheme mode = mapped destinations only")
is true for `pb_records` alone, but `pb_payroll_templates` — installed on every live database
and NOT a `pb_records` dependency — deliberately adds nine standard employee/contract fields
to every scheme's view (`pb_payroll_templates/models/templates.py:1298-1333`,
`TemplateRecordFields._cards`). The OLD expectation was right on live; the Phase 1 "failure"
was a bare-build artefact (the local test database had no `pb_payroll_templates`). My first
rewrite (scheme = mapped only) passed locally and FAILED on p0clone. The final test
(`d586ad7fd`) expects the standard fields in a scheme's view exactly when that module is
present, and always asserts Master records carries them plus all four bank roles.
Commit 2e9777879's message ("Separate master records from focused payroll inputs") is
consistent with this: it separated Master records from schemes; it did not strip the
template module's standard fields.

| Run | pb_records | pb_updates (A12) |
|---|---|---|
| Local, isolated tree, bare build | 94/94 (81 existing + 13 new) | 27/27 |
| Local, with `pb_payroll_templates` installed (`test_01a` + 13 new) | 14/14 | — |
| Live p0clone, inside the deploy | 93/94 — `test_01a` (first rewrite) | 27/27 |
| Live p0clone, after `d586ad7fd`, site up, `--http-port=8471` | **94/94** | **27/27** — 0 ERROR lines |

### A13 — untouched full sheet round trip, large roster

Local copy of payobook (fresh dump this morning), 4,575 people × 73 columns:
**0 changes, 0 cells needing attention, 60,074 cells "stays the same"**. The desk ITSELF now
also counts 0 changes (before this phase it counted 9,953 — the Updates guard was hiding
them). 1,499 rows cannot be matched to a person: 1,497 demo people with no employee code
whose name another person shares, 2 sharing an email — a data fact, unchanged from P1.
Live (QA login's company, 4,547 people × 73): 0 changes, 59,707 same, 1,498 unmatched.

### Other gates
- `.po` gate: `pb_records/i18n/vi_VN.po` read by `PoFileReader` (286 rows); the two new
  sentences are `code` rows of `pb_records`; checked against `odoo-bin i18n export -l pot`;
  no "Odoo" in any msgstr. (57 older model-field strings are untranslated — pre-existing.)
- No new user-visible string contains "Odoo"; the new sentences use screen words only.

## R2. Speed (item 2)

Same machine, same data, same input file, two runs each; "before" = the pre-phase
`pb_records` on the same isolated tree.

| Step (4,575 × 73) | Before | After | Target |
|---|---|---|---|
| Build the sheet | 44.2 s / 44.4 s | 16.8 s / 17.1 s | ≤ 20 s ✔ |
| Read the columns | 3.8 s / 5.0 s | 3.4 s / 3.4 s | — (unchanged code) |
| Review | 115.9 s / 105.0 s | 13.3 s / 13.6 s | ≤ 25 s ✔ |

**Live (payobook, QA login, 4,547 × 73, server-side, server also serving traffic):**
cold first call in a fresh process 26.3 s / 5.1 s / 17.3 s; warm 12.2 s / 3.5 s / 16.7 s and
11.7 s / 2.6 s / 12.9 s (sheet / columns / review). Phase 1's live numbers were 37.1 s /
4.5 s / 71–87 s. **The sheet misses ≤ 20 s on the very first call after a restart** (cold
caches); warm, both targets are met with room.

**Proof of identical:** A9 golden (322 items) identical; A9b; the large sheet's cell
contents hash-identical before/after (`78a9fc2f85e53aec`); the large review answer
hash-identical between the ladder-only run and the optimised run (`cf0f275ff4471878`).

What changed (all per-call, dies with the call — no cross-request cache):
1. Name look-ups memoised per (model, text) (item 1's memo) — this alone took review
   111 s → 13 s: 23,536 searches (111.8 s of a 153 s profile) became ~30.
2. The label of a read cell is asked of `_mapped_record_value` once per (column, value);
   that helper stays the only place a label is made (`pb_records_desk.py:955-1000`).
3. `_LightRow` (`pb_records_desk.py:69`): the mapping handed to the shared read helpers
   answers the four attributes they read per cell from plain attributes; anything else goes
   to the real record. Every record attribute passes through `biz_access`'s
   `__getattribute__` hook (ledger G14), which made re-reading one mapping row 333,000 times
   the cost. Record VALUES are still read through the guarded path.
4. A contract's component lines walked once per call, not once per cell (`:921`).
5. The in-scope employee search gets one id per person (`:1372`).

Profile, review on the 4,575-row file — top lines by cumulative time:

Before (153.1 s under the profiler): `preview_changes` 141.0 · `_evaluate` 141.0 ·
`_coerce` ×60,074 117.1 · `search` ×23,536 111.8 · `search_fetch` 111.5 · `_fetch_query`
89.8 · `browse` 89.4 · `Query.__bool__` 88.7 · `get_result_ids` 88.7 · `execute_query` 86.1 ·
`sql_db.execute` 84.6 · psycopg2 `execute` 84.1 · `hr_employee.search_fetch` ×5,265 66.2 ·
`studio_policy._search` 21.4 · `models._search` 20.8 · `studio_policy.__getattribute__`
×10.0 M 20.1 · `_read_cell` 14.9 · templates `_mapped_record_value` 11.2 · formula
`_mapped_record_value` 10.8 · `fields.__get__` 8.7 · `hr_employee._search` 7.9 ·
`domains.optimize_full` 7.4 · `domains._optimize` 7.4 · `_io_open` 7.3.

After (31.0 s under the profiler; 13.3 s without): `preview_changes` 18.0 · `_evaluate` 18.0 ·
`studio_policy.__getattribute__` ×5.0 M 8.0 · `_io_open` 7.8 · `_io_read_xlsx` 7.7 ·
`_coerce` 6.1 · openpyxl `load_workbook` 5.7 · `read` 5.7 · `read_worksheets` 5.7 ·
`bind_all` 5.6 · `bind_cells` 5.6 · `studio_policy.__getitem__` 5.6 · `_reader.parse` 5.0 ·
`_read_cell` 4.2 · `parse_row` 4.1 · `parse_cell` 4.0 · `_studio_attribute_check` 3.8 ·
`fields.__get__` 3.6 · `translate.get_text_alias` 2.5 · `serialisable.from_tree` 2.5 ·
`models.__getitem__` 2.2 · `_studio_field_allowed` 2.2 · `_get_latest_contract` 2.1 ·
`_studio_policy_sources` 2.1 · `_cells_by_row` 2.0.

What is left: reading the workbook (openpyxl full load, needed for the header comments) and
the access-guard hook on every value read — both safe to leave; not touched.

## R3. Item 1 — the ladder as built

`pb.records.desk._coerce` many2one text path (`pb_records_desk.py:1289-1310`), helpers
`:1110-1205`:
1. `_m2o_is_current` — text equal (case/space-insensitive) to the current value's display
   name, key, or full path → current id.
2. `_m2o_ladder` — `=ilike` on the key, scoped `['|', company_id = False, company_id in
   env.companies]`, default active filter, `limit=3`.
3. Nothing found and the model has a searchable `complete_name` → the same on the full path.
4. One hit → it. Two or more → refused; the count is the real one (`search_count` when the
   limit was hit).
5. Nothing: slashed text on a model with a full path → refused (never a create); otherwise
   the old behaviour (refuse, or propose "(new)").
Memo `('m2o', model, text)` in a dict `_evaluate` creates (`:1380`); `_coerce(..., memo=None)`
stays backward compatible. The Updates "text equal to today is no change" guard is kept as a
second belt.

## R4. Deploy evidence (five databases)

Unit `updates-p2a-20261111T034245Z`, under `flock /tmp/payobook-studio-deploy.lock`,
START 03:43 / DONE 03:58 / NOTE 04:08 UTC in `/opt/deploy-notes.md`. Evidence
`/tmp/updates-p2a-20261111T034245Z/` on the server.

- Dry run first: only this phase's `pb_records` files differed (manifest, `.po`, desk, io,
  three test files + golden); `pb_updates` identical; the server's six changed files were
  byte-identical to the pre-phase commit (nobody's newer work overwritten).
- Backups: `sudima.dump` (28.9 MB) + previous `pb_records`/`pb_updates` trees in
  `/odoo/backups/updates-p2a-20261111T034245Z/`.
- Upgrades: `payobook`, `payobook_template`, `p0clone`, `rize` `-u pb_records`; `sudima`
  `-u pb_records -i pb_updates` — all EXIT=0, no ERROR/CRITICAL in any upgrade log.
- QA password reset on `payobook` (shell, service stopped): OK; user 6672 active,
  `write_date` 03:44:49.
- Active scheduled jobs before → after: payobook 49→49, payobook_template 31→31,
  p0clone 38→38, rize 81→81, sudima 80→80; none newly active.
- Assets: `sudima` only (new bundle): signal row + purge (6 rows) + `web.assets.version`.
  No JS/SCSS changed for the other four.
- **Downtime 10 min 11 s** (03:43:21–03:53:32). See R6.3: about 8 minutes were a test
  process hung in shutdown.
- Sites after start: payobook.com 200, rize 200, p0clone 200, sudima 200.
- Server log from the restart line on: **0 ERROR/CRITICAL, 0 Traceback**. (One earlier
  ERROR today, 03:03 on `rize`, is `pb_probation` "could not consolidate review 34" — 40 min
  before this deploy, not this change.)

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_records` latest_version | 19.0.1.8.5 | 19.0.1.8.5 | 19.0.1.8.5 | 19.0.1.8.5 | 19.0.1.8.5 |
| `pb_updates` latest_version | 19.0.1.0.1 | 19.0.1.0.1 | 19.0.1.0.1 | 19.0.1.0.1 | 19.0.1.0.1 (new) |
| state | installed | installed | installed | installed | installed |

Tree hashes (sha256 of sorted per-file sha256, skipping `__pycache__`, `*.pyc`,
`.DS_Store`), repo = server after the test-file sync: `pb_records` cec6fa807ff67cec =
cec6fa807ff67cec; `pb_updates` 5585afce2c7e8322 = 5585afce2c7e8322.

## R5. Live write walk (payobook)

**How it was done (deviation):** the QA password was reset and is in the memory note, but
the agent's operating rules forbid it from signing in with a password on a live (non-test)
host, even with the owner's approval. So the walk ran ON THE SERVER as the QA user
(uid 6672, company "Payobook Vietnam JSC"), through exactly the `pb.updates.desk` methods
the Updates screen calls (`download_sheet`, `read_columns`, `review`, `apply`,
`get_history`, `undo`). It was rehearsed first on the local copy. The browser was used to
LOOK only, through its existing session (the owner's admin account — nothing applied with it).

Steps and results (log: `outputs/updates-p2a/live-walk-log.txt`, not committed):
1. Before: DEMO Nguyen Van An job title "DEMO Senior Agronomist", pay item MCLNGHL 0;
   DEMO Tran Thi Binh job title "DEMO Senior Agronomist", work phone empty.
2. Downloaded a sheet (2 people, 99 columns, 0.6 s); changed An's job title →
   "DEMO Lead Agronomist P2a", Binh's work phone → "+84 900 000 222", An's MCLNGHL → 500000.
3. Uploaded: recognised as a Payobook sheet; review: 3 changes, 0 refused, 0 unmatched.
4. Applied "P2a live check - sheet": written 3, people 2, not pending (company 5 publishes
   "No approval needed" for Records changes), reference RD00168. Values changed as typed.
5. Past updates: the update with its file, 3 changes for 2 people, "Applied", can undo.
6. Undo: restored 3, 0 skipped. **All values back exactly** (snapshot equal to step 1).
7. Own-headings CSV ("Ho va ten P2a", "Chuc danh P2a", "Ghi chu P2a"): nothing auto-placed;
   matched name + job title, notes left out; 1 change; applied (Binh → "DEMO Field Lead
   P2a"); undone (restored 1). Re-reading the same file: every column "memory"
   (= "Remembered from last time"), layout known.
8. Final snapshot equal to step 1 — **RESTORED**.
9. Untouched full sheet for everyone the QA login sees (4,547 × 73): 0 changes.
10. Browser, payobook People › Updates: Past updates shows both updates as "Undone · Put
    back … by QA Test" with their files (both download 200); console: no errors on load.
    Screenshot `outputs/updates-p2a/01-payobook-past-updates-undone.jpg`.
11. Browser, sudima People › Updates (look only): home loads, "No updates yet", console
    clean. Screenshot `outputs/updates-p2a/02-sudima-updates-home.jpg`.

Left behind on purpose (audit, not data): 2 named updates marked Undone with their files,
the matching Records Desk apply/undo rows and per-value audit rows, 2 component history rows
for MCLNGHL on An's contract (0→500000, 500000→0), chatter tracking on the two DEMO people,
and 1 remembered heading layout ("Ho va ten P2a"…). No demo data deleted.

**What the QA role can do:** read, export, write employee and contract records, apply and
undo through Updates (all confirmed by the walk). Not confirmed: signing in with the new
password through the browser (agent may not), so the owner should do one sign-in.

## R6. Deviations from the handover, and why

1. **Item 3 premise wrong** (R1/A11): the test now follows whether `pb_payroll_templates`
   is installed instead of asserting "scheme = mapped only".
2. **Refusal sentence wording**: "%(n)s %(what)s records are called '…'" instead of
   "%(n)s %(what)s are called" — the existing code's `what` is singular ("department"), so
   "2 department are called" would be ungrammatical; "records" matches the existing
   sentence "…and %(what)s records are not created here".
3. **`complete_name` is not stored** in Odoo 19 (`hr.department`, computed with a custom
   search); rung 3 tests "searchable" (`store or search`), not "stored" (ledger G15).
4. **Wildcards**: `=ilike` treats `%`/`_` as wildcards; when the text holds one, every
   candidate is fetched and only exact matches kept (no change for normal text).
5. **Speed beyond the handover's list**: the label memo and `_LightRow` (R2 items 2-3) were
   needed to reach the sheet target; the batched contract look-up was NOT used for the
   evaluation because export and evaluation disagree on ties (ledger G16).
6. **Live walk server-side as the QA user** (R5) — agent sign-in rule.
7. **Deploy: tests ran inside the stopped-service window and hung** — `--no-http` does not
   stop the web listener when tests are enabled (Odoo `server.py:659`); the test process
   served live requests (sudima websocket) and hung 6 min in shutdown; stopped by PID after
   its results were written. Ledger G12's rule was wrong; corrected (G19). The re-run used a
   free `--http-port` with the site up.
8. `pb_updates` files unchanged → version stays 19.0.1.0.1 (as the handover allows).

## R7. Phase 2b/2c research (from the code)

**1. What happens at approval time; where "hold until a date" attaches.**
`PbRecordsApply._approval_apply` (`pb_records/models/records_approval.py:323`) re-checks
that nobody changed the values since the proposal (`Desk._plan_moved_since`,
`pb_records_desk.py:1771`), then calls `Desk._write_plan(self)` (`records_approval.py:343`
→ `pb_records_desk.py:1797`), which re-runs `_evaluate` on `changes_json` and writes each
step with `_write_cell` / `_write_bank`, then marks the apply `applied`. Under "No approval
needed" this runs inside `apply_changes` → `biz.approval.engine.submit`
(`pb_records_desk.py:1891` → `biz_approval_workflow/models/engine.py:842`). A "hold until a
date" attaches in `_approval_apply` between the moved-since check and `_write_plan`: a new
state on the selection at `records_approval.py:59` (e.g. "Scheduled"), a stored start date
on `pb.records.apply`, and a scheduled job that calls the same `_write_plan` on the day.
Note `_component_log` stamps `effective_date = today` (`pb_records_desk.py:1701`) — it would
need the start date instead.

**2. How the pay run reads a contract component amount.** It reads the CURRENT line value,
never the history by date. Chain (run without a pay file): `pb_payrun_wizard.py:1181`
(`create_and_compute`) / `:1388` (`compute_batch`) → `slip.compute_sheet()` →
`pb_hr_payroll_formula/models/hr_payslip_formula.py:1063` → `:1102` →
`_pb_compute_sheet_with_formulas` `:154/:163` → `_get_formula_input_values` `:199` →
`:710` `Batch._contract_component_values(contract)` → `payroll_import_batch.py:2239` →
`_contract_component_amounts` `:2212`, which loops `contract.advantages_ids` and reads
`advantage.amount` (`:2236`; text `:2258`). With a pay file: `attach_spreadsheet`
(`pb_payrun_wizard.py:2036`) → `action_process` (`payroll_import_batch.py:1545`) →
`_create_payslip` `:1676` → `_transform_data_to_formula_inputs` → `:4227` (same
`_contract_component_values`); only on this path, and only when the scheme has proration /
auto-retro on (`formula_config.py:80/:102`), the history is consulted afterwards (below).

**3. Who reads `hr.contract.advantage.change.effective_date`.** Besides history screens
(`pb_contracts/models/pb_contract_360.py:1151-1153, 1188-1189`, the model's default order
`contract_component_change.py:9`, its views), exactly two places, both feeding pay and both
only on the pay-file path with the scheme flag on: `_apply_proration`
(`payroll_import_batch.py:2563`, search `effective_date` within the period `:2578-2583`,
segments `:2618-2640`, overwrites the input `:2659`) and `_prepare_retro_adjustments`
(`:2716`, search `effective_date < date_from` `:2725-2729`, adds to the retro component
`:2714`). `payroll_proration_line.py` / `payroll_retro_adjustment.py` hold copies, they do
not read the change rows.

**4. One-off pay items for a month.** Three separate stores:
`hr.payroll.period.input` (`pb_hr_payroll_formula/models/payroll_period_input.py:35`) —
per employee × component × period, own `state` draft/approved/superseded, approved by a pay
formulas manager via `action_approve` (`:253`), not the approval engine; READ by runs in
application-data mode (`payroll_period_input.py:417-420` search, `:450` value; drafts block
the payslip as a conflict). `pb.payroll.month.inputs` (`pb_payroll_templates/models/templates.py:69`)
— JSON per employee × scheme × month, no state, no approval; READ by the monthly-template
pay-file path (`templates.py:525-530`, `input_review.py:64-71`, `templates.py:1211`).
`pb.oneoff.feed` (`pb_comp_ben/models/oneoff_feed.py:101`) — an AbstractModel service, stores
nothing: approved awards (`pb.incentive`, approval engine via `biz.approval.chain.mixin`,
`incentive.py:41`) are pushed into an already-computed run's payslips (`oneoff_feed.py:440`,
`:459`). So which one a run reads depends on its mode; there is no single one-off store.
(Unverified risk noted by the search: a pushed award may be dropped if the slip is
recalculated from its sources, `hr_payslip_formula.py:1150-1184`.)

## 8. Needs an owner decision / owner action

1. **Sign in once with the QA login** on payobook.com (password in the memory note) to
   confirm it works in the browser — the agent may not sign in with a password on a live host.
2. **A typed manager or coach name that matches nobody is proposed as a NEW employee**
   ("Nobody P2A (new)") — existing behaviour, kept by the ladder's rule 5 (ledger G17). Should
   a file be allowed to create an employee this way? Recommend: refuse, like the department slash case.
3. **Sheet build on the first call after a restart** is 26 s on live (12 s once warm).
4. **Export and evaluation pick different contracts when a person has two with the same
   start date** (ledger G16) — fix before P2c touches contracts.
5. **Test-run deploy rule**: every deployer's scripts that run `--test-enable` inside a
   stopped-service window must pass a free `--http-port` (noted in `/opt/deploy-notes.md`).
6. The live walk left two "Undone" updates titled "P2a live check …" in payobook's Past
   updates and one remembered heading layout; say if you want them removed.
