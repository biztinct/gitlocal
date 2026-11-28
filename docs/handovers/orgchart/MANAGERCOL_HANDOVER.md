# MANAGERCOL — the pay data file keeps managers up to date

Owner ruling 2026-11-05: Rize's pay data file carries a **"Reporting Manager"**
column ("Master Reporting Manager" in the Indonesia and Singapore files). The
file wins each import: every import sets the manager (`hr.employee.parent_id`)
where the name resolves cleanly, and lists the rows it could not match. A
one-off seed of the current values is being done separately
(`tools/seed_rize_managers_from_payfile.py`, `RIZE_MANAGERS_SEED_REPORT.md`);
this handover makes it ongoing.

Read `ORGCHART_LEDGER.md` §0 (rules, incl. 11–13), §3 G16 and G20, and
`docs/handovers/fillin/FILLIN_LEDGER.md` §0 (deploy/test recipes) first.

## 1. Scope

In `pb_orgchart` (bump to `19.0.1.4.0`), which already depends on the
employee model and may add a dependency on `pb_hr_payroll_formula` (check
`pb_orgchart/__manifest__.py`; adding the dependency is fine — the import
batch is where the hook lives and `pb_orgchart` is installed everywhere the
formula engine is):

1. **Header recognition.** Add `'reporting manager'`, `'master reporting
   manager'`, `'reporting manager name'`, `'direct manager'`, `'người quản
   lý'`, `'quản lý trực tiếp'`, `'atasan langsung'` to `PROFILE_HEADERS`
   (`pb_hr_payroll_formula/models/column_role_classifier.py:119-141`), so the
   column classifies as a profile column like `'manager'`/`'reports to'`
   already do. (`'reporting manager mail id'` and `'hiring manager'` must NOT
   be recognised as the manager — add a unit test that they are not.)
2. **A dedicated writeback step** `_sync_employee_manager(employee, raw_data,
   line)` on `hr.payroll.import.batch` (`_inherit`, in
   `pb_orgchart/models/import_manager.py`), called right after
   `_update_employee_from_raw_data` at
   `payroll_import_batch.py:1650` — inside its own try/except exactly like the
   bank step at `:1652-1660`. The generic mapping path must NOT also write
   `parent_id`: in `_get_mapping_updates`-driven updates, skip a mapping whose
   `target_field_id` is `hr.employee.parent_id` (smallest change: filter it out
   in your inherited `_update_employee_from_raw_data` before calling super, or
   drop the key from the updates dict — read `:2322-2362` and
   `_get_mapping_updates` to pick the cleaner seam; say which).
   Why dedicated: the generic path resolves a many2one with
   `search([(name, '=ilike', value)], limit=1)` (`_coerce_mapped_value`), which
   silently takes the FIRST of two "Nithya"s, is not accent-insensitive
   ("Ho Huu Du" ≠ "Hồ Hữu Dư"), and writes through `employee.write`, which
   drags coach and approvers (G16).
3. **How the value is read.** The column is the one mapped to
   `hr.employee.parent_id` for the batch's scheme (`hr.payslip.import.mapping`
   with `destination_type='field'`, `target_model_id=hr.employee`,
   `target_field_id=parent_id`, `component_id` = the scheme's rule for that
   column — `payslip_import_mapping.py:34-79`). Read the cell through
   `_writeback_raw_value(raw_data, mapping.component_id, mapping=…, line=…)`
   so top-up payloads work. **No mapping → the step does nothing** (no header
   guessing at write time; the mapping is the contract). Optionally, when a
   batch has NO such mapping but its file has a recognised manager header,
   add a one-line batch note "This file has a Reporting Manager column that is
   not mapped yet — map it to Manager to keep managers up to date" (only if
   there is an existing batch-level notes/advisory surface; if there is none,
   skip and say so).
4. **Matching, in order, all within the batch's allowed companies, active
   employees only, never the person themself:**
   a. exact `name` (case-insensitive);
   b. accent-insensitive casefold match (`strip_accents` from
      `column_role_classifier.py:211`, collapse whitespace);
   c. if more than one candidate after (b) and the file ALSO carries a
      reporting-manager email column (header contains "manager" and "mail"
      / "email"), keep the candidate whose `work_email` equals it;
   d. employee code match if the cell looks like a code the company uses
      (`employee_id` field; only when no name match).
   Exactly one candidate → set. Zero or several → do not set, record why.
   A blank cell → leave the current manager (never clear from a blank).
   A would-be loop (`_loop_in`) → do not set, record why.
5. **The write** goes through `pb.orgchart._set_managers` (ledger §0.12) as
   the batch's user, so tracking names the importer and coach/approvers
   keep their value. Unchanged value → no write.
6. **Reporting the rows it could not match.** Per line: append one sentence
   to `line.error_message`? No — that field marks a failed row and this is
   not a failure. Add a `pb_manager_note` Char on
   `hr.payroll.import.line` ("Manager not set: 'Nithya' matches 2 people")
   and a computed `pb_manager_unmatched_count` on the batch; show the count
   and the list on whatever screen shows the batch's review today (the
   Import wizard's results step / the batch form — find it, and add ONE line
   + a fold-out list in the product's own words: "Managers: 118 set, 4 not
   matched — see rows"). If a review surface is genuinely absent, log at
   INFO and put the counts in the batch's chatter message instead; say which.
7. **rize configuration**: create the four mappings (one per scheme: Vietnam,
   Indonesia, India, Singapore) through the product's own mapping RPC or a
   small idempotent script in `tools/` (never raw SQL), so the NEXT monthly
   import keeps managers in step. Report the mapping ids. Do not re-run any
   past batch.
8. Unit tests (§4), vi_VN strings, report.

### Non-goals
* No change to how any other column is written. No change to the seed script
  or its results. No "Hiring Manager" handling. No chart changes.

## 2. Plumbing — verified, do not re-derive
* Line loop and the bank-step precedent: `payroll_import_batch.py:1644-1665`.
* `_update_employee_from_raw_data` `:` (grep) → `_get_mapping_updates` →
  `_writeback_raw_value` → `_coerce_mapped_value` (many2one branch:
  `=ilike`, `limit=1`, `m2o_creates_missing`).
* Mapping model `payslip_import_mapping.py:13-79`; `_get_model_mappings`,
  `_get_mappings_by_field` on the batch.
* Import line fields `payroll_import_line.py:20-125` (`raw_data_json`,
  `employee_id`, `state`, `error_message`).
* Classifier header lists `column_role_classifier.py:99-175`;
  `strip_accents :211`.
* `pb.orgchart._set_managers`, `_loop_in` (pb_orgchart, P2).
* rize facts: 214 rows across the latest batches 2072/2284/2260/2285; VN
  emails unreliable (one email beside five names) — hence email only as a
  tie-break; 6 ambiguous rows today.

## 3. Safety rails
* The step never fails a line: own try/except, log with traceback.
* Never clear a manager; never set a loop; never match archived or
  other-company people; never match the person to themself.
* Only via `_set_managers`. Never `coach_id`.
* A re-import of the same file is idempotent (no writes when unchanged).

## 4. Test cases (`pb_orgchart/tests/test_import_manager.py`)
1. Header "Reporting Manager" / "Master Reporting Manager" classify as
   profile; "Reporting manager Mail ID" and "Hiring Manager" do not resolve
   to a manager mapping.
2. With a mapping to `parent_id`, an import row naming an existing employee
   exactly sets `parent_id`; coach/approvers unchanged (G16).
3. Accent-insensitive: "Ho Huu Du" resolves "Hồ Hữu Dư".
4. Two people named alike + an email column → the email breaks the tie;
   without the email → not set, note written, count = 1.
5. Blank cell → manager untouched. Unknown name → not set, note.
6. Would-be loop → not set, note.
7. Re-import unchanged → no tracking row written.
8. No mapping → nothing happens, no note.
9. The generic path does not also write `parent_id` (assert exactly one
   tracking row per changed person).
Live: run the next rize import only when Rize sends it — not now. Evidence
instead: a dry import of the latest Vietnam file on **p0clone** or a test DB
with the mapping in place, showing "Managers: n set, m not matched".

## 5. Deploy / report
Ledger §0.4 (`full`: new field + classifier change), §0.11, §0.13. Do not
deploy while the seed script is running on rize (ask the coordinator /
check `/opt/deploy-notes.md` for a running START without DONE). Report
`MANAGERCOL_REPORT.md`: files/commits, tests, the mapping ids on rize, the
review surface chosen, deploy table, gotchas appended to the ledger.
