# RECORDS Phase R1 — "This run only" pay data

Program: RECORDS. Phase 1 of 3. Modules: `pb_hr_payroll_formula` (batch flag + branch + tests),
`pb_payrun_wizard` (kwarg + Pay-data choice + summary), `pb_import_batch` (badge).
Read `docs/handovers/RECORDS_LEDGER.md` (standing rules) and CLAUDE.md's deploy contract first.
`docs/handovers/NETROLE_PHASE3_RUNWIZARD_EXCEL.md` is the phase that built the Pay-data step —
skim it for the vocabulary; do not re-derive its plumbing.

## The ask (owner's words, 2026-08-29)

> "In the pay run wizard give an option to use the excel pay component values only one time for
> that pay run. This would mean you would not have to update the Payobook database for this
> particular use case. So this could be used for use cases where there's only one time
> requirement to add a bonus or any other component, without changing the default values."

Owner rulings: a row for an employee who is not in Payobook is **skipped and listed as an
exception** — one-time means *nothing* is saved, newcomers included.

## Scope

- One Boolean on `hr.payroll.import.batch`; one guarded branch in `action_process`; one kwarg on
  `pb.payrun.wizard.attach_spreadsheet`; one choice on the wizard's Pay-data step; one sentence
  in the summary; one badge on the batch cockpit + the native batch form.

**Non-goals (binding):** no change to the resolver ladder or `_transform_data_to_formula_inputs`;
no change to the Import door (`pb_import_wizard`) — that is a later candidate; no change to feed
(API) batches — `one_time` is meaningful for `source_type='excel'` only and the wizard is the only
writer of it in R1; no Records Desk work (R2).

## Design bar (binding — score the report against it)

> "Extreme WOW, intuitive, out-of-this-world experience, best in class." Every surface names its
> hero moment; zero dead-ends (empty/loading/error/partial/huge states designed, every failure
> names its reason and next step); plain language over code vocabulary; motion with purpose;
> keyboard + bulk ergonomics; measured against the best SaaS tool in the category, not stock Odoo.
> Lucide icons, never emoji. Chrome-MCP walk every flow. Never the word "Odoo" in a user-visible
> string.

**R1's hero moment:** choosing "This run only" visibly *locks* Payobook — the coverage panel's
chip becomes a shield reading "Payobook stays exactly as it is", the primary button changes its
verb, and the summary says in one sentence that nothing was saved. A person should never be
unsure which mode they ran.

## Verified plumbing — do NOT re-derive

Batch — `pb_hr_payroll_formula/models/payroll_import_batch.py`:
- Options block `:253-279` (`auto_create_employees`, `auto_create_contracts`, `match_by_*`,
  `create_payslips`). The new Boolean sits here.
- `action_process` `:1378-1514`. Per line: find/create employee `:1418-1433` (error text
  "No employee found and auto-create is disabled" `:1432`); `raw_data = line.get_raw_data()`
  `:1435`; `_stamp_source_ref` `:1440`; `_update_employee_from_raw_data` `:1441`; bank
  `_sync_employee_bank_account` `:1447` (own try/except); contract `_get_latest_contract` `:1454`,
  `_create_contract` `:1456`, else `_update_contract_from_raw_data` `:1459-1460`;
  `_sync_contract_components` `:1463` (may return a NEW contract — skipping it keeps the latest);
  payslip `_create_payslip` `:1466-1472`.
- `_create_payslip` `:3217` → `_transform_data_to_formula_inputs` `:3649`; the excel rung reads the
  line blob via `_declared_source_walk` `:2632` (`if hits: return hits` `:2714`). **The payslip
  never reads the record for a component present in the file** — so skipping every writeback
  leaves file-fed components byte-identical. Components ABSENT from the file resolve at rank 4/5
  from the (now untouched) record — which is exactly the one-time semantics.
- `contract_component_amounts` is built at `:3676` from the contract as it is when step 4 runs;
  with the sync skipped it carries the OLD amounts. Intended.
- `action_recompute_formula_lines` (`hr_payslip_formula.py:752-804`) re-reads the file through the
  batch and writes no record — nothing to change there; test it stays that way.
- Existing counter precedent for the neutrality rail: `_sourcing_reset_branch_counter` /
  `_sourcing_shared_counter` (see `tests/test_journey_j10_writeback.py:124-130`). Fixtures to
  reuse from that file: `_config`, `_batch`, `_map_field`, `_map_bank`, `_employee`, `_blobs`.
- `pb_hr_fullandfinal/models/payroll_import_batch.py:14-17` wraps `action_process`; untouched.

Wizard — `pb_payrun_wizard/models/pb_payrun_wizard.py`:
- `attach_spreadsheet(run_id, config_id, file_b64, filename, date_start, date_end)` `:918-1010`;
  batch vals `:950-960`; the four `action_*` calls `:961-964` inside a savepoint; error list
  `:981-985` reads `line.state == 'error'` + `line.error_message`; return dict `:999-1010`.
- Client `static/src/js/payrun_wizard.js`: `state.sheet` `:43-68`; `runWithoutSheet` /
  `continueWithSheet` `:255-265`; `_compute` `:294-425` — attach call `:370-373`, summary
  assembly `:405-424` (`summary.sheet = batch`).
- Template `static/src/xml/payrun_wizard.xml`: data step `:142-209` (drop zone `:151-157`,
  coverage panel `:167-208`); summary sheet sentence `:241-246`; footer data-step buttons
  `:293-294`. SCSS `static/src/scss/payrun_wizard.scss` (`.pw-*`), icons via
  `import { ic } from "@pb_import_kit/js/import_icons"` (the `js/` segment is required).
- `pb_demo` overrides `prepare_run`/`compute_batch` (not `attach_spreadsheet`) — the new kwarg
  is additive and the demo DB must behave exactly as before.

Batch cockpit — `pb_import_batch/models/batch_cockpit.py`: `get_batch_detail` `:60`, source label
`:95-96`, excel branch `:125`. Find the OWL template that renders `source` and add the badge beside
it.

## Build

### 1. `hr.payroll.import.batch.one_time`

```python
one_time = fields.Boolean(
    string="Use these values once",
    default=False,
    help="The file feeds this pay run only. Nothing is saved to employee, contract or bank "
         "records, and no new employees or contracts are created.")
```

`action_process`, inside the per-line loop:
- Employee step: when `self.one_time`, do the `_find_employee` lookup but never `_create_employee`;
  an unmatched line gets `state='error'`, `error_message = "Not in Payobook yet — a one-time file
  saves nothing, so this row was not paid"` and `continue`. (Also force the batch's
  `auto_create_employees`/`auto_create_contracts` False at the wizard's create — belt and braces —
  but the branch must not depend on it.)
- Skip `:1440`, `:1441`, `:1447`, `:1459-1460`, `:1463` when `one_time`. Keep
  `contract = self._get_latest_contract(employee)`; if no contract → `state='error'`,
  `error_message = "No contract to pay against — a one-time file creates none"`, `continue`.
- Increment a module-level counter `_one_time_branch_entered` whenever the one-time branch is
  taken; expose `_records_one_time_counter()` / `_records_reset_one_time_counter()` on the model
  (copy the `_sourcing_*` counter shape). A normal batch must leave it at 0.
- `_log(...)` at completion adds "one-time — no record was updated" when set.

### 2. `attach_spreadsheet(..., one_time=False)`

- Batch vals add `'one_time': bool(one_time)`, and when one_time: `auto_create_employees: False`,
  `auto_create_contracts: False`.
- Return adds `'one_time': bool`, `'unmatched': [{'emp', 'why'}]` (the lines with the one-time
  error sentence; also fold them into `errors` so the existing exceptions path shows them) and
  `'unmatched_count'`.

### 3. Pay-data step (the WOW half)

Below the drop zone, once a file is chosen (`state.sheet.file_name`), a two-card segmented choice
`state.sheet.mode` ∈ `'update' | 'once'` (default `'update'`):

- **Update Payobook** — icon `database`/`save` — "Values are saved to employee and contract
  records and used from now on."
- **This run only** — icon `shield` (or `lock`) — "Used just this once. Nothing in Payobook
  changes — good for a one-off bonus or a correction."

Behaviour when `'once'`: the coverage panel's headline gains a chip `Payobook stays exactly as it
is` (shield icon, teal); the note under the coverage list says "Anyone in the file who is not in
Payobook yet will be listed, not paid."; the primary footer button reads **"Continue — this run
only"**; the choice animates (a 160ms card lift + chip fade — motion with purpose, no jitter).
Keyboard: the two cards are radio-like (`role="radio"`, arrow keys switch, Enter/Space select).

`_compute` passes `sheet.mode === 'once'` as the 7th positional arg to `attach_spreadsheet`.

Summary (compute step): when `summary.sheet.one_time`, the sheet sentence becomes
*"<file> fed N component(s) across N row(s) — **used once; nothing was saved to any employee,
contract or bank record.**"* plus, if `unmatched_count`, *"N row(s) were for people not in Payobook
and were not paid — see Review exceptions."* Exceptions carry the plain sentence per person.

Empty/edge states to design: file chosen then mode switched (chip toggles live); mode chosen
then "Choose a different file" (mode persists); upload fails (existing error path, mode
untouched); `wantsSheet` false (nothing new renders at all).

### 4. Batch surfaces

- Native batch form (`pb_hr_payroll_formula/views/…import_batch…`): the field in the Options
  group with its help; list view optional filter "Used once".
- Batch cockpit (`pb_import_batch`): `get_batch_detail` returns `one_time`; the header shows a
  shield badge "This run only — no records were updated" when set.

## Safety rails

- Default False everywhere; a batch created anywhere else (Import door, API, tests) behaves
  byte-identically. Prove with the md5 + counter test below.
- `one_time` is never read outside `action_process` and the two display surfaces. The resolver
  is untouched.
- No user-visible "Odoo". No emoji. Lucide via `ic()`.

## Numbered test cases (`pb_hr_payroll_formula/tests/test_records_r1_one_time.py`)

Build fixtures the J10 way (records this transaction creates; never `action_process` on live
data — but here `action_process` on a batch of test-created records IS the subject, so drive it
on your own fixtures with `create_payslips=True` and a minimal scheme: one input component mapped
to `hr.employee.job_title` (Char), one to `hr.contract.wage`, one bank `acc_number`, one contract
component rule; a file blob via `import_line_ids` with `raw_data_json`).

1. **Neutrality** — a normal batch: md5 of every created payslip's `formula_input_values` is
   identical to the same fixture run on a checkout without R1 (record the pre-change md5 as a
   constant, computed in the same test before your code change — MJ11) AND
   `_records_one_time_counter() == 0`.
2. **Nothing written** — a `one_time` batch: `write_date` of the employee, the contract, its
   `res.partner.bank` and every `hr.contract.advantage` line is unchanged; `hr.employee`,
   `hr.contract`, `hr.contract.advantage.template` counts unchanged; counter > 0.
3. **File-fed components identical** — payslip line totals for components present in the file
   equal the normal batch's, line for line.
4. **Absent component reads the OLD record** — a contract component absent from the file
   resolves to the pre-existing advantage amount (normal batch would have synced the file's).
5. **Unmatched row** — an unrecognised employee row: `state='error'`, the exact plain sentence,
   no employee created; the batch still finishes `done`.
6. **Recompute stays clean** — `action_recompute_formula_lines` on a one-time payslip re-reads
   the file, same lines, no `write_date` moves.
7. **Wizard return shape** — `attach_spreadsheet(..., one_time=True)` on a draft run returns
   `one_time=True`, `unmatched` list populated, `created` counts matched rows only; the batch has
   `auto_create_employees == False`.
8. **Source assertion** — `payrun_wizard.xml` and the batch views contain no "Odoo" and no emoji
   (grep the way J10's `_src` helper does).

Hoot (`pb_payrun_wizard/static/tests/payrun_mode.test.js`, register
`web.assets_unit_tests`): the mode choice defaults to `update`, arrow keys switch it, the button
label follows it, and `attach_spreadsheet` receives the 7th arg.

## Deploy + verify

1. Baseline first on the box: `-u pb_hr_payroll_formula,pb_payrun_wizard,pb_import_batch
   --test-enable --test-tags /pb_hr_payroll_formula,/pb_payrun_wizard,/pb_import_batch` on abm,
   backgrounded, kill by PID (C18.54). Record counts + the 3 known reds.
2. Bump manifests: `pb_hr_payroll_formula` → 19.0.1.101.0, `pb_payrun_wizard` → 19.0.1.14.0,
   `pb_import_batch` → 19.0.2.1.0.
3. Deploy per CLAUDE.md (clean `/tmp/deployX`, per-module rsync) → `-u` on **abm** → service
   start → clear `/web/assets/%` on abm.
4. Chrome-MCP on abm (ash@biztinct.com / J5validate!2026): Run Payroll for a period that does
   not collide with the owner's runs (use a draft-safe month, and **delete the draft run you
   create when done** — deleting a run orphans its payslips, so delete the payslips first, see
   memory `abm-june-payrun`). Walk: choose file → both modes → chip/button text → run once →
   summary sentence → Review exceptions → open the batch cockpit badge → verify via
   `call_kw` that the contract's SHUI flag / wage did NOT change. Then the same file in Update
   mode on a fresh draft → verify it DID change → restore the value. Screenshot each state.
5. Then payobook + payobook_template: deploy, `-u`, assets cleared, one smoke load each of the
   wizard (the demo DB must show NO new UI unless a scheme binds excel columns).
6. Verify tree hashes + `latest_version` on the three DBs.
7. Commit (explicit paths): `feat(payrun): use a pay-data file once without updating records (R1)`.

## Report back (in this order)

- Test counts (baseline vs after) per DB, the md5, the counter proof.
- Each numbered case: pass/fail with the evidence line.
- Chrome walk: what each state showed (paste the strings), screenshots' paths.
- Design-bar self-score (hero moment, dead-ends, plain language, motion, keyboard) with what
  you would still improve.
- Gotchas → append `RD1…` entries to `docs/handovers/RECORDS_LEDGER.md`.
- Anything you left out and why.
