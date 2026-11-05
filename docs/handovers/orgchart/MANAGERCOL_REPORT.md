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
