# IMPORT-GENDER — Gender / Marital Status cells fail the whole import row

## PAUSED HERE (2026-11-05, owner asked to pause)

**Was Rize's last real import affected? No.** All four latest real imports
(2072 Vietnam Oct, 2260 India Oct, 2284 Indonesia Aug, 2285 Singapore Aug), and
every Rize import since 2026-10-19 (up to 2289), were run as **"use once"**
imports (`one_time = true`). That mode skips the employee writeback entirely,
so the failing code was never reached: 63/63, 27/27, 122/122, 2/2 rows
`processed`, no `error_message`. No line in rize, payobook, payobook_template
or p0clone has ever carried the error text. Rize's last **updating** import was
2026-09-23, on schemes that had no Gender / Marital wire.

**Long-standing, latent — not a recent regression.** The failing line
(`field.selection(record.env)`) dates from January; it became reachable for
`hr.employee` selection fields on **2026-08-31, commit `3bc032f62` (SC-5)**,
which started resolving the mapping's `ir.model.fields` row to the Python
field. Before that the same cells were silently not written. It turned into a
loaded gun for Rize when the Gender/Marital wires were drawn (Marital on the
master-data schemes 2026-10-19, Gender + the focused schemes 2026-10-21). The
first **updating** import on those schemes fails every row that carries a
value the file outranks the record on.

### Done
* Facts above (read-only SQL on the live box).
* Fix written in `pb_hr_payroll_formula/models/payroll_import_batch.py`
  (`_coerce_mapped_value` selection branch) + version 19.0.1.163.2.
* New test file `pb_hr_payroll_formula/tests/test_import_gender_marital.py`
  (6 cases, registered in `tests/__init__.py`). **Not yet run.**
* Scratch addons dir staged on the box: `/tmp/igf_test/addons/pb_hr_payroll_formula`
  (= this commit's module) and the replay script `/tmp/igf_test/igf_replay.py`
  (asserts it runs only on a DB named `igf_test`).

### Not done
1. Unit tests (scoped `-u pb_hr_payroll_formula --test-tags /pb_hr_payroll_formula`
   on p0clone, scratch addons dir first; ports 8193/8192). Was waiting for the
   CLOCK-1 deploy, which finished 02:22 UTC.
2. Proof on a throwaway copy of rize (none was created).
3. Deploy (none started; no START line written).
4. Browser check on rize.payobook.com.
5. Final commit (this one is WIP) + deploy table below.

### Exact next step
On the box: run the unit tests with the SCHEMECTX §0.13 recipe from
`/tmp/igf_test/addons` (re-stage from the repo if `/tmp` was cleared). Then
`pg_dump rize` → `createdb igf_test` → `pg_restore --no-owner --role=odoo`,
crons off, logins off (G46); run `igf_replay.py` via `odoo-bin shell -d igf_test
--no-http` **twice** — once with the live addons path (old code: expect the
failures) and once with `--addons-path=/tmp/igf_test/addons,/odoo/odoo-server/addons`
(new code: every row `processed`) — then `dropdb igf_test`. Then
`filter_deploy.sh full` for pb_hr_payroll_formula ×4 DBs (no abm).

---

## 1. Facts

| Batch | File | Scheme at import | Mode | Rows | Result |
|---|---|---|---|---|---|
| 2072 | Vietnam, Oct 2026 | 4760 master-data | use once | 63 | 63 processed |
| 2260 | India, Oct 2026 | 6382 master-data | use once | 27 | 27 processed |
| 2284 | Indonesia, Aug 2026 | 7096 master-data | use once | 122 | 122 processed |
| 2285 | Singapore, Aug 2026 | 7095 master-data | use once | 2 | 2 processed |
| 2286–2289 | test runs on the focused schemes, 2026-10-22 | 7118–7121 | use once | 2/27/122/60 | all processed |

Rize's 24 updating imports were 2026-09-11 … 09-23, on schemes 3921/3938/3939/
3941/3942 — none has a Gender or Marital wire.

What the files say: Gender `Male`/`Female` (VN 48/8, 7 blank; IN 11/16;
ID 95/23, 4 blank; SG 1/1). Marital `Single` everywhere it is filled (VN file
blank). No Vietnamese spellings in any file.

Wires today: Gender on 4760/6382/7095/7096 (since 10-21); Marital on all eight
(master-data 10-19, focused 10-21). Source order: VN `api,excel,records`,
IN `excel,records,api` (file wins → every row with a value fails),
SG/ID `records,excel,api` (record wins where it already has a value → only
people with an empty box fail; explains MANAGERCOL's "Indonesia 16/122,
Singapore none").

## 2. Cause

Odoo 19 `hr.employee` inherits `sex`/`marital` from `hr.version`
(`_inherits`), so they are related fields; a related Selection's `selection`
is `lambda model: field._description_selection(model.env)`
(`odoo/orm/fields_selection.py:81`). `_coerce_mapped_value` called it with an
Environment → `'Environment' object has no attribute 'env'` → the line loop's
`except` marks the whole row `error`, payslip included. A method-name
selection (`hr.version.marital`) was a str and was walked character by
character (silent refusal).

## 3. Fix

`_coerce_mapped_value` asks the field: `field._description_selection(record.env)`
(handles list / method name / callable; the same call `_mapped_record_value`
already uses). When neither value nor label in the user's language matches,
labels in every language the database has switched on are also accepted
(exact, case/space-insensitive) — so a Vietnamese file's "Nữ" lands for an
English-language user. Unknown words are still refused, never raised.

## 4. Evidence — PENDING (see PAUSED HERE)

## 5. Deploy — PENDING
