# IMPORT-GENDER — Gender / Marital Status cells fail the whole import row

Found by MANAGERCOL (ledger G43). Fixed 2026-11-05.

## 0. In one paragraph

**Rize's last real imports were not affected.** Every Rize import since
2026-10-19 (the four latest real files and the four test runs on the focused
schemes) was a **"use once"** import (`one_time = true`), which skips the
employee writeback where the failure lives; all their rows processed. The
fault is **long-standing and latent, not a recent regression**: reachable
since **2026-08-31, commit `3bc032f62` (SC-5)**, and armed for Rize when the
Gender / Marital Status columns were wired on 2026-10-19 / 10-21. The first
**updating** import on Rize's current schemes would have failed every Vietnam
and India row that carries a value (payslip included). Fixed in
`pb_hr_payroll_formula` 19.0.1.163.2; replay on a copy of rize: 213 failed
rows before, 0 after.

## 1. Facts (live, read-only SQL)

| Batch | File | Scheme at import | Mode | Rows | Result |
|---|---|---|---|---|---|
| 2072 | Vietnam, Oct 2026 | 4760 master-data | use once | 63 | 63 processed |
| 2260 | India, Oct 2026 | 6382 master-data | use once | 27 | 27 processed |
| 2284 | Indonesia, Aug 2026 | 7096 master-data | use once | 122 | 122 processed |
| 2285 | Singapore, Aug 2026 | 7095 master-data | use once | 2 | 2 processed |
| 2286–2289 | test runs on the focused schemes, 2026-10-22 | 7120/7119/7121/7118 | use once | 2/27/122/60 | all processed |

* No import line in rize, payobook, payobook_template or p0clone has ever
  carried the error text.
* Rize's 24 **updating** imports were 2026-09-11 … 09-23, on schemes
  3921/3938/3939/3941/3942 — none has a Gender or Marital wire.
* What the files say: Gender `Male`/`Female` (VN 48/8 + 7 blank; IN 11/16;
  ID 95/23 + 4 blank; SG 1/1). Marital `Single` wherever filled (the VN
  October file leaves it blank; the VN focused file fills it). No Vietnamese
  spellings in any file.
* Wires: Gender on 4760/6382/7095/7096 (since 10-21); Marital on all eight
  schemes (master-data 10-19, focused 10-21).
* Source order: VN `api,excel,records` and IN `excel,records,api` → the file
  wins → every row with a value failed; SG/ID `records,excel,api` → the record
  wins where it already has a value → only people with an empty box failed
  (MANAGERCOL's "Indonesia 16/122, Singapore none").

### History of the failing line

* `field.selection(record.env) if callable(field.selection) else …` — in the
  file since January (`d0ba67359`, 2026-01-10).
* **2026-08-31 `3bc032f62` (SC-5)** started resolving the mapping's
  `ir.model.fields` row to the Python field at the top of
  `_coerce_mapped_value`. Before that the row's `selection` Char was empty →
  the cell was silently NOT written; after it, a related selection is
  callable → the call raised → the row failed.
* Live code at the time of every 2026-10 Rize import already had it (no
  change to these lines since); live tree before this deploy = `503279518^`
  (hash `19f0699c1fb5`).

## 2. Cause

Odoo 19 `hr.employee` inherits `sex`/`marital` from `hr.version`
(`_inherits`), so on the employee they are related fields, and a related
Selection's `selection` is `lambda model: field._description_selection(model.env)`
(`odoo/orm/fields_selection.py:81`). `_coerce_mapped_value` called it with an
Environment → `'Environment' object has no attribute 'env'` → the line loop's
`except` marked the whole row `error`, so no payslip. A selection declared by
method name (`hr.version.marital` itself) is a str and was walked one
character at a time (silent refusal).

## 3. Fix (`pb_hr_payroll_formula/models/payroll_import_batch.py`, `_coerce_mapped_value`)

* Ask the field: `field._description_selection(record.env)` — handles a list,
  a method name and a callable; it is what `_mapped_record_value` already uses.
* When neither the stored value nor the label in the user's language matches,
  a label in any language the database has switched on is also accepted
  (exact, case/space-insensitive), so a Vietnamese file's "Nữ" lands for an
  English-language user. An unknown word is still refused (`None`), never
  raised.
* Version 19.0.1.163.1 → 19.0.1.163.2. No user-visible string added.

## 4. Evidence

### Unit tests — p0clone, scratch addons dir, scoped `-u pb_hr_payroll_formula --test-tags /pb_hr_payroll_formula`

| Run | Code | Result |
|---|---|---|
| t2 (`/tmp/igf_run/t2.log`) | fix | **4 failed, 0 errors of 667 tests**; all 6 new tests pass |
| base (`/tmp/igf_run/base.log`, ports 8197/8196) | unchanged live code | **4 failed, 0 errors of 661 tests** — the same 4 |

The 4 are pre-existing and environmental, not touched by this change:
`test_rd49_sync_cost` 02ab/02i (the sync job is off on p0clone),
`test_records_r1_one_time` 07b (the default call now returns use-once),
`test_schemectx_currency` 04 (p0clone's company currency makes the fixture
degenerate). Scheduled jobs on p0clone 33 → 33 both runs.

New file `tests/test_import_gender_marital.py`:

| # | Case | Result |
|---|---|---|
| 01 | "Male"/"Female"/" FEMALE "/"Single"/"Married" coerce on the employee (related selection) | PASS |
| 02 | unknown word → refused, no exception | PASS |
| 03 | the `ir.model.fields` row shape (what `_get_mapping_updates` passes) | PASS |
| 04 | method-name selection (`hr.version.marital`) | PASS |
| 05 | Vietnamese label ("Nữ"/"NAM") while working in English | PASS |
| 06 | full `action_process`, updating import, scheme ordered like Rize Vietnam (file first): 4 rows incl. a blank Marital cell → all processed, payslips made, Gender/Marital set, blank keeps the record | PASS |

### Replay on a throwaway copy of rize (`igf_test`, jobs and logins off, dropped)

Each latest file copied into a new **updating** batch (`one_time = false`,
no new people, the original row-to-person matches), processed with
`action_process` as the admin, rolled back after each, so every replay starts
from rize's real state. Script `/tmp/igf_test/igf_replay.py` (kept out of the
repo; it refuses any database not named `igf_test`).

| File → scheme | Rows | Old code: failed rows | Fixed code: processed / payslips | Gender / Marital boxes written (cells with a value) |
|---|---|---|---|---|
| VN Oct (2072) → 7118 Vietnam focused | 63 | 0 (no values in the mapped column) | 63 / 63 | — |
| VN Oct (2072) → 4760 Vietnam master-data | 63 | **56** | 63 / 63 | Gender 56/56 |
| VN focused file (2289) → 7118 | 60 | **60** | 60 / 60 | Marital 60/60 |
| IN Oct (2260) → 7119 India focused | 27 | **27** | 27 / 27 | Marital 27/27 |
| IN Oct (2260) → 6382 India master-data | 27 | **27** | 27 / 27 | Gender 27/27, Marital 27/27 |
| IN focused file (2287) → 7119 | 27 | **27** | 27 / 27 | Marital 27/27 |
| ID Aug (2284) → 7096 Indonesia master-data | 122 | **16** | 122 / 122 | Gender 118/118, Marital 122/122 |
| ID focused file (2288) → 7121 (old-code run only) | 122 | 0 | — | — |

Old code: **213 failed rows**, every one `'Environment' object has no attribute 'env'`.
Fixed code: **0 failed rows**, every Gender/Marital cell written.
rize itself was never imported into. Copy made 03:57 UTC, dropped 07:14 UTC
(the replay itself finished 05:30; three earlier runs were killed by other
sessions' full deploys, which `kill -9` every odoo-bin — see §6).

## 5. Deploy

`filter_deploy.sh full`, staged from **`git archive 503279518 -- pb_hr_payroll_formula`
only** — HEAD already carried another session's unproven WIP in the same
module (`f253c2942`, PDR P1), which was NOT deployed. Before the deploy the
live tree equalled `503279518^` (hash `19f0699c1fb5`); staged vs live differed
in exactly: `__manifest__.py` (163.1 → 163.2), `models/payroll_import_batch.py`,
`tests/__init__.py`, and the new `tests/test_import_gender_marital.py`.

| When (UTC) | Commit | Module → version | EXIT ×4 | Jobs before/after | Evidence |
|---|---|---|---|---|---|
| 07:31:46–07:37:42 (stop 07:32:39, start 07:37:32) | 503279518 | pb_hr_payroll_formula 19.0.1.163.1 → **19.0.1.163.2** (-u) | 0/0/0/0 | 33/29/76/44 → same | `/tmp/igf-run-20261105073146`, backups `/odoo/backups/igf-run-20261105073146` |

* `errors=3` in every database = three `payroll_analytics … contains null
  values` schema notes that every `-u` cascade prints (same lines in the
  fillin, gates, perf and myhome runs) — not from this change.
* After: `latest_version` 19.0.1.163.2 in p0clone, payobook_template, rize,
  payobook; live tree hash `e982f9f6364a` = staged; sites 200. No ABM.
* Notes: START line 510, DONE 512, then "live pb_hr_payroll_formula =
  19.0.1.163.2 = 503279518 only; f253c2942 NOT deployed". The deploy waited
  for the CLOCK-2, HIRING-MENU, MYTEAM-tests and PDR P1 lines; PDR P1's proof
  posted DATA DONE (07:31) and its pdr_test server shut itself down (07:31:26)
  before this run started, so the restart interrupted no one's work.
  `ListAgents` is not available in this session; coordination went through
  the coordinator and the notes file.

### Browser check (rize.payobook.com, signed-in session, Chrome)

Import page (`/bizapp/action-769`), 07:41 UTC after a fresh load: the
"Import data" wizard opens with its four steps (Source & file, Review &
match, Validate, Commit) and the Load & match button; **no console errors or
warnings**, no error dialog, the page never says "Odoo". (A load at 07:39
logged "connection lost" errors — that was the MYTEAM deploy's own server
restart, 07:38–07:40, not this change; the reload after it was clean.) No
credentials were typed; the existing signed-in session was used. Nothing was
imported on rize.

## 6. Gotchas

* **A full deploy kills every odoo-bin on the box**, shells and test runs
  included (`filter_deploy.sh:71`, `pkill … kill -9`; the job exits 137).
  A long proof replay needs its own START line in `/opt/deploy-notes.md` so
  other sessions hold their deploys until its DATA DONE.
* **Run shells detached** (`systemd-run`, output to a file). An ssh drop broke
  the stdout pipe of a foreground shell mid-replay.
* `/tmp/<dir>` chowned to `odoo` is no longer writable by the ssh user —
  stage the runner scripts in a 777 run dir.
* **Never stage a shared module from HEAD without checking it for other
  sessions' commits.** HEAD had an unproven WIP commit in
  `pb_hr_payroll_formula` by the time of this deploy; staging was done from
  this fix's own commit and the staged-vs-live diff listed in §5 (ledger G54).
