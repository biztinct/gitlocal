# MANAGERCOL — report (2026-11-05)

The pay data file keeps managers up to date. Handover: `MANAGERCOL_HANDOVER.md`.
Seed it continues: `RIZE_MANAGERS_SEED_REPORT.md`.

## 1. What shipped

| Commit | What |
|---|---|
| `50a6cbf4d` | pb_orgchart 19.0.1.4.0: manager step, generic-path filter, line/batch fields, screens, 18 tests, vi_VN; classifier headings in pb_hr_payroll_formula (file sync, version unchanged); `tools/map_rize_reporting_manager.py` |
| `6e2ab1d6c` | fix: the step reads the FILE's cell, never the record's (found by the dry import, §3) + test 13 |
| (this commit) | this report, ledger G40–G46 |

Seams chosen (handover §1.2 asked to say which):
* **Generic path** — `_get_mapping_updates` is overridden and the `parent_id`
  mapping is filtered out BEFORE `super()` (not dropped from the result
  after): the generic many2one resolver would otherwise run `=ilike … limit=1`
  and, since `m2o_creates_missing(hr.employee)` is true, CREATE an employee
  named after an unmatched cell ("Board"). An empty remainder returns `{}`
  directly — `super()`'s `mappings or …` would re-fetch all of them (G40).
* **The hook** — `_update_employee_from_raw_data` is overridden: `super()`
  then `_pb_manager_step` (own savepoint + try/except + log with traceback).
  That method is called only from the line loop (`payroll_import_batch.py:1650`)
  and from `_create_employee`, so matched people and new starters both get
  their manager; a one-time file never reaches it. No edit to the formula
  module's loop.
* **Review surface** — both screens exist, both got it: the import wizard's
  last step (after the outcome cards) and the batch page (above the action
  bar), via OWL template inheritance from pb_orgchart; the words come from
  `hr.payroll.import.batch._pb_manager_summary()` (translated server-side),
  the rows fold out with a native `<details>`. Line "Managers from the file ·
  N updated · N already up to date · N not matched (· N left blank)", amber
  only when something is not matched, grey at zero.
* **"Not mapped yet" note** — shown on the same panel when the scheme maps no
  manager but the file's first row carries a manager heading (test 08).
  No rize batch shows it today (none of their files sits on an unmapped
  scheme with the column).

Matching (= the seed's): accent-insensitive; tiers full name → same words
reordered → short name; first tier that finds anyone decides; written only
for exactly one current person with nobody who has left at that tier; ties
settled by the file's manager-email column, which also vetoes a short name
that contradicts it — **only when the file's emails are consistent**: a file
where one address sits beside names sharing no word (rize Vietnam: du.ho@
beside five people) is not trusted. That replaces the seed's "never Vietnam"
with a rule on the file itself and gives identical answers (§3). Then an
employee code (`employee_id`) if no name fits. Never: blank clears, loops
(`_loop_in`), self, leavers, other companies. Writes only through
`pb.orgchart._set_managers`, as the importing user; unchanged → no write.

## 2. Tests — 78 of 78 pass (18+1 new)

p0clone, scratch addons dir first, SCHEMECTX §0.13 recipe on ports
8193/8192 (8199 was briefly taken, G45); log `/tmp/mgrcol_test/t3.log`:
`0 failed, 0 error(s) of 78 tests`. Scheduled jobs on p0clone 32 → 32.
The one ERROR line in the log is test 10's deliberate failure.

| # | Case | Test | Result |
|---|---|---|---|
| 1 | "Reporting Manager", "Master Reporting Manager", VN/ID headings → profile + manager; "Reporting manager Mail ID", "Hiring Manager" are not the manager | test_01 | PASS |
| 2 | exact name (and case-insensitive) sets the manager; coach / time-off / expense approver unchanged (G16); one history row | test_02 | PASS |
| 3 | "Ho Huu Du" → Hồ Hữu Dư; reordered and short names | test_03 | PASS |
| 4 | two "Nithya"s: email settles it; without email → not set, note, count 1; untrusted file never settles; short name vs contradicting email refused; leaver at the same tier blocks, leaver never picked; other company / self; employee code | test_04, 04b–04f | PASS |
| 5 | blank (and a missing column) keeps the manager; unknown name → note | test_05 | PASS |
| 6 | would-be loop → not set, note | test_06 | PASS |
| 7 | re-import unchanged → no history row; a different name replaces (file wins) | test_07 | PASS |
| 8 | no mapping → nothing, no note; panel shows the "not read" sentence | test_08 | PASS |
| 9 | the generic resolver never sees `parent_id`, other mapped columns still flow, no employee created from a cell, exactly one history row; empty-remainder trap | test_09, 09b | PASS |
| — | a failing write never fails the row (note instead) | test_10 | PASS |
| — | summary chips/rows/toggle; wizard + batch page payloads | test_11 | PASS |
| — | a new starter made by an earlier row can be a later row's manager | test_12 | PASS |
| — | the file wins over the record when the column is a declared source | test_13 | PASS |

Gates: libsass on the box OK (`import_manager.scss`); PO parse gate 641 rows,
none empty (+31).

## 3. Dry import on a copy of rize (evidence; copy dropped)

`pg_dump rize` → throwaway `mgrcol_test` (jobs off, logins off), the four
mappings made the product's way, then (script kept out of the repo, output
`/tmp/mgrcol_dry2.out` on the box):

* **Parity with the seed, all four files, 214 rows:** 204 resolve to exactly
  the manager the seed wrote, 0 disagree, the same 6 problem rows as the seed
  report's table (with the same reasons), 4 blank. The first run read 124
  Indonesia/Singapore rows as blank — the shared reader, handed the employee,
  let the record's own manager win (G41) → fixed in `6e2ab1d6c`.
* **Latest Vietnam file (63 rows), managers cleared on the copy:**
  first import "Managers from the file: 59 updated · 0 already up to date ·
  4 not matched", 59 history rows, coach/approvers moved: none;
  re-import "0 updated · 59 already up to date · 4 not matched", 0 history
  rows. 59 of 59 back to the seed's values.
* **Found, not caused, by this work (G43):** on the same copy 56 of those 63
  rows crash in the EXISTING employee writeback before the manager step runs
  (`'Environment' object has no attribute 'env'`, `_coerce_mapped_value`'s
  selection branch on `marital` / `sex`). Probe of every latest rize batch
  replayed today: focused Vietnam 60/60 rows, focused India 27/27, master-data
  Vietnam 56/63, Indonesia 16/122, India 27/27 crash; Singapore and focused
  Indonesia none. Reproduced with a direct call, independent of pb_orgchart.

## 4. Deploy

| When (UTC) | Commit | Module → version | EXIT ×4 | Jobs before/after | Evidence |
|---|---|---|---|---|---|
| 01:49:03–01:51:28 | 50a6cbf4d | pb_orgchart → 19.0.1.4.0 (-u); pb_hr_payroll_formula files (19.0.1.163.1 unchanged) | 0/0/0/0, errors 0 | 32/29/75/43 → same | `/tmp/mgrcol-run-20261105014837`, backups `/odoo/backups/mgrcol-run-20261105014837` |
| 02:02:59–02:04:26 | 6e2ab1d6c | pb_orgchart 19.0.1.4.0 (-u) | 0/0/0/0, errors 0 | same | `/tmp/mgrcol-run-20261105020203`, backups `/odoo/backups/mgrcol-run-20261105020203` |

`filter_deploy.sh full`, staged from `git archive HEAD`, lock free before each,
live trees equalled the pre-change HEAD; sites 200; tree hash OK; START/DONE in
`/opt/deploy-notes.md`. `ListAgents` is not available in this session (no
other session could be told). No ABM.

## 5. rize configuration

`tools/map_rize_reporting_manager.py`, dry run then `PB_MGR_APPLY=1`, as the
admin through `pb.formula.studio.employee_mapping_create` (no SQL):

| Scheme | Column (rule) | Mapping id |
|---|---|---|
| 4760 Rize Vietnam Payroll — archived master-data scheme | Reporting Manager (20964) | **4078** |
| 7096 Rize Indonesia Payroll — archived master-data scheme | Master Reporting Manager (30186) | **4079** |
| 6382 Rize India Payroll — archived master-data scheme | Reporting Manager (27327) | **4080** |
| 7095 Rize Singapore Payroll — archived master-data scheme | Master Reporting Manager (29737) | **4081** |

No employee changed (209 with a manager before and after); no batch re-run.
Undo: remove those four wires on the mapping board.

**Why these four and not the active ones (G44):** rize's ACTIVE schemes are the
four "focused payroll" schemes (7118–7121, live since 2026-10-21), which were
trimmed to pay columns by the owner-approved plan and **carry no Reporting
Manager column at all** — there is nothing to map. The column exists only on
the master-data schemes every real client file was loaded against (the seed's
batches). An import against a focused scheme of a file that has the column
shows the "not read" sentence on the panel.

Browser check (rize, signed-in session, Chrome): a scratch batch holding
copies of the October Vietnam rows, manager step only (script compared every
manager and the history count and would have refused a change), opened on the
batch page and on the import's last step: "Managers from the file · 0 updated
· 59 already up to date · 4 not matched", fold-out with the 4 rows and their
reasons; no console errors; the import wizard opens normally with the
inherited template. Scratch batch deleted. Screenshots (real names, so not in
the repo): `outputs/rize-managers-2026-11-05/01_batch_page_rize.jpg`,
`02_import_last_step_rize.jpg`.

## 6. Open items

1. **G43 — the existing employee writeback crashes on Marital status / Gender
   cells** (one-word fix in `pb_hr_payroll_formula`:
   `field.selection(record)` instead of `field.selection(record.env)`).
   Out of scope here (non-goal: no change to how other columns are written),
   but it fails the WHOLE row — payslip included — and on today's data every
   row of the focused Vietnam and India files. Needs its own small change +
   test before Rize's next import.
2. **Owner decision:** to keep managers updated from Rize's MONTHLY imports,
   the four focused schemes need the Reporting Manager column back (one
   column each) and then a mapping (the tool can be pointed at them).
3. Hourly row rewrite (G20) and the seed's undo table are untouched.

## Part 2 — read by header (2026-11-05) — DONE

Owner ruling 2026-11-05: read the manager column whenever the file has it,
even when the scheme maps nothing to Manager (rize's four focused schemes
7118–7121 have no Reporting Manager column, G44). No change to Rize's file or
schemes. (Paused once mid-way on the owner's request — WIP `c751b07a1` — and
resumed the same day.)

### What shipped

| Commit | What |
|---|---|
| `c751b07a1` | WIP (PAUSED): the by-heading reader in `import_manager.py` |
| `7096f6af3` | pb_orgchart **19.0.1.5.0**: tests 08/08b/08c/08d + test_01 rewritten, the "not mapped yet" sentence removed (code + vi_VN), manifest description |
| (this commit) | this section, ledger G47–G49 |

* **One list.** The headings are the classifier's existing `MANAGER_HEADERS`
  (`column_role_classifier.py:125-131`, the tuple `PROFILE_HEADERS` is built
  from), so the two cannot drift; it already holds every heading the ruling
  names, and the accent-free forms match because both sides go through
  `_index_key` (casefold, accents off, punctuation and spacing collapsed).
  **No change to pb_hr_payroll_formula** — which kept this work clear of the
  IMPORT-GENDER builder's files and deploy.
* `is_manager_name_header(key)` (pb_orgchart): exact heading from that list,
  "Sheet|Heading" judged by its heading part, and refused when the heading has
  any of the WORDS mail / email / hiring / id.
* `_pb_manager_cell(raw_data, mapping, line, primary_only)`: a mapping still
  wins (unchanged read: `_writeback_raw_value`, never `employee=`, G41; a
  blank mapped cell is "left blank", the other heading is NOT consulted).
  Without one: the primary payload, then the top-up one (`_writeback_blobs`,
  the same two payloads and lane switches `_writeback_raw_value` uses); the
  first manager heading **with a value** wins; headings present but all empty
  → "left blank" (the manager is kept); no heading → the step says nothing.
* Same matching, same `_set_managers` write, same email tie-break (now also
  judged per file without a mapping), same summary line and "See the n rows".
  The "this scheme does not read it — map the column" sentence and
  `_pb_manager_unmapped_header` are gone; the template's hint slot stays (it
  renders nothing).

### Tests — 81 of 81 pass

p0clone, scratch addons dir first, SCHEMECTX §0.13 recipe on 8193/8192 (after
the IMPORT-GENDER builder's own run on the same ports had finished — G48);
log `/tmp/mgrcol2_test/t2.log`: `0 failed, 0 error(s) of 81 tests`; jobs on
p0clone 33 → 33. The one ERROR line is test 10's deliberate failure.

| # | Case | Test | Result |
|---|---|---|---|
| a | no mapping + "Master Reporting Manager" (plain and "Consolidated\|…") → manager set, one history row; summary shows, no hint | test_08 | PASS |
| b | no mapping + only "Reporting manager Mail ID" and "Hiring Manager" → nothing set, no note, nothing on screen | test_08b | PASS |
| c | mapping present + a "Manager" heading too → the mapping wins; mapped cell blank → "left blank", the other heading ignored | test_08c | PASS |
| — | no mapping: the top-up payload is read; an empty first heading falls through to a filled one; a blank cell never clears | test_08d | PASS |
| — | heading rules: VN/ID/EN headings with and without accents are the name; mail / hiring / "Manager ID" / column letters are not | test_01 | PASS |
| d | every earlier MANAGERCOL test (02–07, 09–13) | — | PASS |

Gates: PO parse gate on the box 640 rows, none empty (−1: the removed
sentence). No SCSS change.

### Proof on a throwaway copy of rize (copy dropped)

`mgrcol2_test` from `pg_dump rize` (jobs off, logins off), G46 recipe. Rize's
**September Vietnam file** (`Payobook-month-2026-09.xlsx`, batch 2072's file,
copied from rize's file store because a copy has none — G49) imported through
the real import (`action_load_file` → `action_match_employees` →
`action_process`) as an **updating** import on the **current Vietnam scheme
7118**, which has no manager mapping. Script kept out of the repo
(`/tmp/mgrcol2_test/replay.py`, asserts the DB name); outputs `r1.out`,
`r2.out` on the box.

| Run | Rows processed | Managers line | History rows | Coach / approvers moved |
|---|---|---|---|---|
| 1 — managers as rize has them (seeded) | 63 / 63 | 0 updated · **59 already up to date** · 4 not matched | 0 | 0 |
| 2 — the 63 people's managers cleared on the copy first | 63 / 63 | **59 updated** · 0 already up to date · **4 not matched** | 59 | 0 |

59 of 59 end on exactly the seed's manager, 0 differ. The 4 not matched are
the seed report's Vietnam problem rows: "Indra" fits 2 people, "Nithya" fits 2
people (×2), "Shreya" fits 2 people and 1 has left. That is the Vietnam share
of the seed's 204 / 6 / 4 (Vietnam: 59 clean, 4 problem, 0 blank).
**The Gender / Marital bug did not block any row** on this file and scheme
(all 63 processed with the fix not yet live) — every row reached the manager
step.

### Deploy

| When (UTC) | Commit | Module → version | EXIT ×4 | Jobs before/after | Evidence |
|---|---|---|---|---|---|
| 04:15:26–04:19:10 | 7096f6af3 | pb_orgchart → 19.0.1.5.0 (-u) | 0/0/0/0, errors 0 | 33/29/76/44 → same | `/tmp/mgrcol2-run-20261105041526`, backups `/odoo/backups/mgrcol2-run-20261105041526` |

`filter_deploy.sh full`, staged from `git archive HEAD`; live tree equalled
`6e2ab1d6c` (the last deployed pb_orgchart) before; lock free; START/DONE in
`/opt/deploy-notes.md`; tree hash equal after; sites 200; `ListAgents` not
available in this session. No ABM. The ACCESS-GAPS looks deploy (START 04:16)
queued on the lock behind this one and ran after it; the coordinator's "wait
for it" message arrived after this deploy had already started.

### Browser check (rize, signed-in session)

The import wizard opens normally (no console errors on load). Its last step
was shown for the existing September Vietnam batch by loading that batch's own
summary into the open wizard — nothing sent to the server, no button pressed:
"Import complete … 63 rows processed" with the outcome cards; the manager line
is correctly absent (that batch was a "use once" import, so it has nothing to
say). The same step with the replay's numbers placed in the page's memory
shows "Managers from the file · 59 updated · 0 already up to date · 4 not
matched · See the row", no "map the column" sentence. No console errors.
Page reloaded afterwards. Screenshot (real tenant, so not in the repo):
`outputs/rize-managers-2026-11-05/03_import_last_step_part2_rize.jpg`.

### Open — for the owner

1. **"Use once" imports never touch managers.** Every Rize import since
   2026-10-19 (2072, 2260, 2284–2289) was run as **use once**, which by design
   updates no employee record at all (RECORDS R1) — so the manager step does
   not run either, mapping or not. This change makes managers follow the file
   on an **updating** import. If Rize keeps importing "use once", managers
   will not change from the file. Owner choice: import monthly files as
   updating imports, or ask for "use once" to still update managers (a scope
   change to R1).
2. **Rize's August test file for the focused Vietnam scheme (batch 2289) has
   no Reporting Manager column at all.** The real September client file does.
   Managers follow only files that carry the column.
3. The Gender / Marital fix (IMPORT-GENDER) is a separate change by another
   builder; it did not affect this file.

## Part 3 — a "use once" file still updates managers (2026-11-05)

Owner ruling 2026-11-05 (recorded as ruling 6 in `ORGCHART_LEDGER.md`): a
"use once" ("this run only") import must STILL update managers from the
manager column; every other employee field, bank account and contract stays
untouched exactly as before (RECORDS R1).

### What shipped

| Commit | What |
|---|---|
| `9e6c2baf3` | pb_orgchart **19.0.1.6.0**: `action_process` override + `_pb_manager_one_time_pass`, tests 14–16, manifest text |
| (this commit) | this section, ledger ruling 6 and G50–G51 |

* **Seam: after the processing loop, not inside it.** The ONE_TIME branch
  (`payroll_import_batch.py:1627-1643`) lives in pb_hr_payroll_formula, which
  the IMPORT-GENDER builder was changing at the same time; pb_orgchart instead
  overrides `action_process`. Its override is the OUTERMOST (pb_orgchart loads
  after the approval gate in `payroll_import_approval.py:74-105`), and the
  gate's apply step (`_approval_apply`, `:302-307`) calls `action_process`
  again, so the pass runs exactly when the body has run: the batch is `done`.
  A press that only sent the file for approval does nothing; the approval
  that later carries it out runs the pass.
* **What it runs:** `_pb_manager_step` — the same step, savepoint, matching,
  `_set_managers` write and notes as an updating import — for every row whose
  state is `processed`, in file order. A row that failed (no contract, a
  person not found) changes no manager, the same outcome as an updating
  import, where a failed row's savepoint rolls the manager back with it.
  Rows already looked at are skipped, so the gate's nested call (no approval
  needed → applied in the same press) does not run the step twice; a batch
  about to be processed has its old manager notes cleared first.
* Nothing else in the one-time path is touched: no source stamp, no employee
  field, no bank account, no contract, no new person or record.

### Tests — 84 of 84 pass

p0clone, scratch addons dir, ports 8193/8192; log `/tmp/mgrcol2_test/t3.log`:
`0 failed, 0 error(s) of 84 tests`; jobs 33 → 33 (the one ERROR line is test
10's deliberate failure).

| # | Case | Test | Result |
|---|---|---|---|
| 1 | use-once row with a manager AND Gender / Marital Status / Department / Work email values, all of them wired to the employee → manager set (one history row), gender, marital, department, work email, job title, coach, time-off approver unchanged; no department created; summary shows | test_14 | PASS |
| 2 | use-once row with no manager column (only the manager's email and "Hiring Manager") plus Gender / Marital → nothing changes, no history row, no note, nothing on screen | test_15 | PASS |
| 3 | use-once: a row that fails (no contract) changes no manager; the next row's manager is set | test_16 | PASS |
| — | all 81 earlier tests | — | PASS |

### Proof on a throwaway copy of rize (copy dropped)

`mgrcol3_test` from `pg_dump rize` (jobs off, logins off). Rize's September
Vietnam file (batch 2072's file, read from rize's file store, G49) imported
through the real import (`action_load_file` → `action_match_employees` →
`action_process`) as a **use-once** import on the current Vietnam scheme
7118, after clearing the managers of its 63 people. Script outside the repo
(`/tmp/mgrcol2_test/replay3.py`, asserts the DB name); output `r3.out`.

| | Result |
|---|---|
| Rows | 63 / 63 processed, 63 payslips, 0 employees created |
| Managers line | **59 updated · 0 already up to date · 4 not matched** (Indra ×1, Nithya ×2, Shreya ×1 — the seed's Vietnam rows) |
| Managers vs the seed | 59 of 59 equal, 0 differ |
| History rows on the 63 people | 59 — every one of them the manager |
| Coach / time-off / expense approver moved | 0 |
| Any other value changed on the 63 people's employee, version (gender, marital, …) or contract rows | **none** (full row compare before/after, manager and write stamps excluded), bank accounts unchanged |

### Deploy

| When (UTC) | Commit | Module → version | EXIT ×4 | Jobs before/after | Evidence |
|---|---|---|---|---|---|
| 04:41:42–04:45:18 | 9e6c2baf3 | pb_orgchart → 19.0.1.6.0 (-u) | 0/0/0/0, errors 0 | 33/29/76/44 → same | `/tmp/mgrcol3-run-20261105044142`, backups `/odoo/backups/mgrcol3-run-20261105044142` |

`filter_deploy.sh full`, staged from `git archive HEAD`; live tree equalled
`7096f6af3` before; lock free and no other START open (no IMPORT-GENDER
deploy had started); START/DONE in `/opt/deploy-notes.md`; tree hash equal
after; sites 200; `ListAgents` not available. No ABM.

### Browser check (rize, signed-in session)

After the deploy the import wizard opens with no console errors, and
pb_orgchart reads 19.0.1.6.0. The last step was shown for the latest
"use once" Vietnam batch (2289) by loading its own summary into the open
wizard (nothing sent, no button pressed): "Import complete · 60 rows
processed", outcome cards, and — correctly — no manager line, because that
file has no manager column. Page reloaded afterwards. Screenshot (real
tenant, not in the repo):
`outputs/rize-managers-2026-11-05/04_import_last_step_part3_rize.jpg`.

### Open — for the owner

1. **The "this run only" screens still promise nothing changes.** The pay run
   wizard's choice says "Used just this once. Nothing in Payobook changes",
   its coverage chip "Payobook stays exactly as it is", its result box
   "nothing was saved to any employee, contract or bank record", and the
   batch page chip "This run only — no records were updated". With this
   ruling, managers from the file DO change. Rewording those (pay run wizard,
   batch page, their Vietnamese and any lesson that quotes them) is outside
   pb_orgchart and was not done — say if you want e.g. "Nothing in Payobook
   changes except managers, when the file has a manager column."

## Part 4 — the "this run only" screens tell the truth (2026-11-05)

Owner ruling 2026-11-05 (standing rule: plain, honest words on every screen):
every place that promised a "this run only" / "use once" file changes
nothing now says, in one sentence, that each person's manager still follows
the file when it has a manager column. Both languages.

### Search

`grep -rniE` over pb_payruns, pb_payrun_wizard, pb_import_wizard,
pb_import_batch, pb_import_kit, pb_hr_payroll_formula (views, wizards,
models, i18n), pb_learn, pb_records — and, found on the way, pb_payroll_templates
(its review dialog now sits on the pay run screen on all four databases) —
for "Nothing in Payobook changes", "stays exactly as it is", "no records were
updated", "nothing was saved", "this run only", "use once", "values once",
"stay unchanged", "read-only context". 70 raw hits; the ones that are NOT a
no-change promise and were left alone: labels ("This run only", "Use these
values once", "Used once" filter, "Continue — this run only"), engineer
comments/docstrings, the busy message "Computing … for this run only…",
Records Desk's "nothing is saved until you apply" (a different feature), and
Learn lines that only say "uses them once". **No hit in pb_import_wizard,
pb_import_kit or pb_payruns** — the import wizard has no use-once option and
no such step text.

### Every place reworded

| # | Where (screen) | Before | After | VI |
|---|---|---|---|---|
| 1 | Pay run screen, "This run only" choice (`pb_payrun_wizard` payrun_wizard.xml) | Used just this once. Nothing in Payobook changes — good for a one-off bonus or a correction. | Used just this once — good for a one-off bonus or a correction. Nothing in Payobook changes except each person's manager, when the file has a manager column. | new entry |
| 2 | Pay run screen, Coverage chip | Payobook stays exactly as it is | Payobook stays as it is, except managers | new entry |
| 3 | Pay run screen, result box after computing | used once; nothing was saved to any employee, contract or bank record. | used once; nothing was saved to any employee, contract or bank record, except each person's manager when the file has a manager column. | new entry |
| 4 | Import batch page chip (`pb_import_batch` batch_cockpit.xml) | This run only — no records were updated | This run only — nothing saved but managers | new entry |
| 5 | Same chip, tooltip | The values in this file fed one pay run and were then forgotten. | The values in this file fed one pay run and were then forgotten — except each person's manager, when the file has a manager column. | new entry |
| 6 | Pay run "Input changes" review heading, monthly template (`pb_payroll_templates` run_input_review.xml) | This month's inputs. Saved records stay unchanged. | This month's inputs. Saved records stay unchanged, except managers from the file. | module's first vi_VN.po |
| 7 | Learn practice replica of the choice (`pb_learn` engine/screens.js) | = #1 | = #1 | inline bilingual |
| 8 | Learn glossary "This run only" (data.js → learn_content.json) | Use the file's values once, for this run, and change nothing in Payobook. … | … and change nothing in Payobook except each person's manager, when the file has one. … | inline bilingual |
| 9 | Learn lesson "what it affects" (two lessons) | This run only changes nothing in Payobook[: right for a one-off bonus or a correction]. | This run only changes nothing in Payobook except managers from the file[: …]. | inline bilingual |
| 10 | Learn lesson prose (Update vs This run only) | … uses them once, for this run, and changes nothing in Payobook — the batch then says "This run only — no records were updated". | … and changes nothing in Payobook except managers from the file. The batch then says "This run only — nothing saved but managers". | inline bilingual |
| 11 | Native batch form, "Use these values once" field help (`pb_hr_payroll_formula`) | The file feeds this pay run only. Nothing is saved to employee, contract or bank records, and no new employees or contracts are created. | PENDING — see below | |
| 12 | Native batch form, processing log line (`pb_hr_payroll_formula`) | … — one-time — no record was updated | PENDING — see below | (log is English-only) |

Vietnamese entries carry all three markers (`#. module:`, `#. odoo-javascript`,
`#: code:addons/<module>/<path>:0`); none of these modules ships a `.pot`. The
exact msgids were taken from the server's own extractor
(`babel_extract_qweb`), PO parse gate on the box: pb_payrun_wizard 124 rows,
pb_import_batch 37, pb_payroll_templates 1 — none empty. Learn content was
edited in the authoring source (`docs/tutorial_poc/author/data.js`) and
regenerated (`gen_learn_data.py`, `--check` clean; one sentence was split to
stay under the 28-word lint). `check_contract.py`: the same single
pre-existing failure as before the change (`c1-cockpit-anchors`, missing
`pe-filters`), nothing new.

### Commits and deploys

| Commit | What | Deploy |
|---|---|---|
| `a922ef13f` | #1–#5, #7–#10 — pb_payrun_wizard 19.0.1.41.1, pb_import_batch 19.0.2.2.2, pb_learn files | `full` 04:59:57–05:06:31 UTC, EXIT=0 ×4, errors 0, crons 33/29/76/44 unchanged, tree hash OK, sites 200; run dir `/tmp/mgrcol4-run-20261105045957` |
| `07c365468` | #6 — pb_payroll_templates 19.0.1.6.2 | waiting (deploy hold, below) |

**Deploy hold.** At ~05:10 the coordinator held every deploy: the
IMPORT-GENDER builder's replay on its own throwaway copy had been killed three
times by full deploys (the deploy script kills every `odoo-bin`, shells
included — G52). This work's own 04:59 deploy stopped the server at 05:01:48,
before that builder's 05:03 relaunch, but it may have been one of the earlier
interruptions. #6 and the two pb_hr_payroll_formula lines (#11, #12) wait for
"IMPORT-GENDER proof | DATA DONE" and that builder's own deploy DONE; nothing
was committed into pb_hr_payroll_formula before then.

### Browser check (signed-in sessions; texts placed in each open screen's memory, nothing sent, no button pressed, page reloaded after)

| Database | Screen | Seen |
|---|---|---|
| payobook (demo) | Pay run · Pay data · Coverage chip | "Payobook stays as it is, except managers" |
| payobook | Pay run · Compute result box | "… used once; nothing was saved to any employee, contract or bank record, except each person's manager when the file has a manager column." |
| payobook | Import batch page, use-once batch 24 | chip "This run only — nothing saved but managers", tooltip as #5 |
| payobook | Import's last step (batch 24) | renders, outcome cards, no manager line (the file has no manager column) |
| payobook | Vietnamese terms served (`/web/webclient/translations`, no-store) | #1, #2, #4, #5 present with their Vietnamese |
| rize | Pay run chip / result box | "Rize stays as it is, except managers" (the brand rewrite applies) / result box as above |
| rize | Import batch page, batch 2289 | "This run only — nothing saved but managers" |
| rize | Import's last step (batch 2072) | renders, "63 rows processed" |

No console errors on any of them. Screenshots (not in the repo):
`outputs/rize-managers-2026-11-05/05_payrun_chip_payobook.jpg`,
`06_payrun_result_box_payobook.jpg`, `07_batch_page_chip_payobook.jpg`.

Found on the way: on all four databases the pay run screen's "What should
these values do?" choice (#1) is currently replaced by pb_payroll_templates'
"Compute now. Choose what to keep afterwards" flow, which always makes the
file a use-once batch — so with part 3, every pay run file with a manager
column now updates managers. #1 is still corrected for any database without
that module.
