# NETROLE Phase 3 — the Run Payroll wizard asks for the month's spreadsheet

Program: NETROLE. Phase 3 of 4 (runs after Phase 2). Modules:
`pb_payrun_wizard` (+ small server surface in `pb_hr_payroll_formula`).
Read `docs/FORMULA_ENGINE_CONVENTIONS.md` C1, C2 (asset cache!), C7, C10, and
CLAUDE.md's deploy contract first.

## The defect

A scheme can bind components to spreadsheet columns
(`hr.formula.rule.source_ids` rows with `kind='excel'`; summarised on the rule
as `source_binding='excel'` + `source_binding_key` —
[formula_rule.py:205-233](../../pb_hr_payroll_formula/models/formula_rule.py#L205)).
The Run Payroll wizard (`pb.payrun.wizard`) never asks for a file, and the
batchless compute path (`_get_formula_input_values`,
[hr_payslip_formula.py:412+](../../pb_hr_payroll_formula/models/hr_payslip_formula.py#L412))
has NO spreadsheet branch — contract, worked days and connected-system feeds
only. So every excel-bound component silently falls back to contract/default,
and nothing on screen says a file was ever expected. The owner's words:
"otherwise silently it does not want any excel to be used."

## Verified plumbing — do NOT re-derive

- The whole import pipeline already handles spreadsheets end to end:
  `hr.payroll.import.batch` with `source_type='excel'` (selection at
  [payroll_import_batch.py:108](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L108)),
  file in `import_file` (Binary, attachment) + `import_filename`, then
  `action_load_file()` (line 624) → `action_validate()` (1348) →
  `action_process()` (1377).
- If `batch.payslip_run_id` is set BEFORE processing, created payslips land in
  THAT run (lines 1487–1498) — no second run is created.
- `peek_source_columns(config, file_content, filename)` (line 486) reads a
  file's headers without creating anything — use it for the pre-flight
  coverage check.
- The wizard (`pb_payrun_wizard/models/pb_payrun_wizard.py`) flow:
  `prepare_run(vals)` creates the draft run, adopts loose slips
  (`_adopt_loose_slips`), returns `emp_ids`; the client then chunks
  `compute_batch(payload)`. `compute_batch` SKIPS employees who already have a
  slip in the run (the `already` set) — this is what makes "batch first, then
  wizard compute for the rest" idempotent.
- Client: `pb_payrun_wizard/static/src/js/payrun_wizard.js` — OWL, `STEPS`
  array, `_compute(force)` drives prepare→chunks→summary via `orm.silent`;
  templates in `static/src/xml/payrun_wizard.xml`; step 1 is the period form,
  step 2 compute/result, step 3 exceptions.
- `pb_demo` OVERRIDES `prepare_run`/`compute_batch` for demo divisions
  (memory/CLAUDE: any new wizard entrypoint must not break that path — the
  demo DB `payobook` must behave exactly as before; the spreadsheet step must
  simply not appear there unless a scheme actually has excel bindings).
- Uploads of a few MB as base64 through `call_kw` are fine (the import batch
  form does the same); do not invent a controller.

## Build

### Server (`pb.payrun.wizard`)

1. `@api.model spreadsheet_gate(vals)` → for the period's resolving config(s)
   (reuse how compute finds a config — `hr.payslip._find_formula_config`
   precedent; for the wizard, the company's active configs):
   `{wanted: bool, components: [{code, name, key}], filename_hint, config_id}`.
   `wanted` = the scheme has ≥1 rule with an excel source row (kind='excel',
   non-empty key). Never raises; `{wanted: False}` on any doubt (C7: but log).
2. `@api.model preflight_spreadsheet(config_id, file_b64, filename)` → calls
   `peek_source_columns`; returns per-component coverage:
   `{ok, columns: n, fed: [codes], missing: [{code, key}], employees_col: bool}`.
   Pure read — creates nothing (test proves by row-count diff).
3. `@api.model attach_spreadsheet(run_id, config_id, file_b64, filename,
   date_start, date_end)` → creates the batch
   (`source_type='excel'`, `payslip_run_id=run_id`, config, period, file),
   runs load→validate→process inside a savepoint, returns
   `{ok, batch_id, created, matched, errors: [...], fed_components: [...]}`.
   On failure: rollback to savepoint, `{ok: False, msg}` with the server's own
   words (the Phase-June lesson: pass refusals through, never 'Compute error').
4. `prepare_run` gains `vals['spreadsheet_skipped']` (bool, default False):
   when the gate wanted a file and the user explicitly skipped, the returned
   payload carries `skipped_components: [codes]` so the summary can say what
   ran on fallbacks. No other behaviour change; `pb_demo`'s override is
   untouched (new keys are additive).

### Client (wizard UI — this is a WOW surface, respect the design system)

- New step between period and compute, shown ONLY when `spreadsheet_gate`
  says wanted: **"Pay data"**. Contents:
  - A drop zone (drag or click, .xlsx/.xls/.csv) styled like the Import
    cockpit's (`pb_import_kit` classes are available — `pb_payruns` already
    depends on the kit; check `pb_payrun_wizard`'s manifest and add the dep if
    missing). Lucide icons via the kit's `ic()` registry — NO emoji.
  - After preflight: a coverage card — "This file feeds N of M spreadsheet
    components", green check rows for fed, amber rows for missing (component
    name + the column it expects). A bad file is refused with the reason.
  - A deliberate, visible escape hatch: "Run without a spreadsheet" button
    (secondary style) with the affected components listed right there.
    Skipping is a CHOICE the user makes looking at the list — never a silent
    default. If they skip, the compute step's summary shows an amber note:
    "N components used fallback values — no spreadsheet was loaded."
  - While the batch processes: reuse the existing progress affordance
    (`state.busyMsg`/progress bar patterns already in the file).
- Step flow: on "Continue with this file" → prepare_run → attach_spreadsheet
  → then the normal chunked compute for REMAINING employees (the `already`
  guard makes this correct); summary merges batch results
  (`created`/`matched` counts) + notes the batch's error lines as exceptions.
- The period step's existing fields/labels are not restyled in this phase.

### What this phase must NOT do

- No changes to `_get_formula_input_values` (no new excel branch — the batch
  IS the excel path; one implementation, per C12's spirit).
- No changes to Phase 1/2 files beyond reading `source_binding`.
- Demo DB behaviour byte-identical when no scheme has excel bindings.
- White-label: never "Odoo" in any user-visible string.

## Tests (`pb_payrun_wizard/tests/test_spreadsheet_step.py`)

1. Gate false for a scheme with no excel sources; true once a rule has an
   excel source row; the demo-shaped config without bindings stays false.
2. `preflight_spreadsheet` reports fed/missing correctly for a tiny in-test
   xlsx (build with openpyxl in-memory) and creates zero batches/lines.
3. `attach_spreadsheet` creates payslips INTO the given run (no second run),
   and a following `compute_batch` for the same employees creates nothing new.
4. A broken file (garbage bytes) → `{ok: False}` with a message, no batch left
   behind (savepoint proven by row counts).
5. `spreadsheet_skipped` round-trips: prepare_run returns the affected codes.
6. Existing suites still green (`TestRunAdoptsThePeriod` etc.).

Run everything on `payobook_template` (detached-unit pattern, bump manifest
versions: `pb_payrun_wizard` and `pb_hr_payroll_formula` if touched). Deploy
all modules changed, upgrade all four DBs, **purge asset bundles** per DB
(`DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`) because JS/XML
changed, restart, and validate on live ABM with Chrome MCP if available — if
the Chrome MCP server is down, validate via JSON-RPC (the `/tmp/probe2.py`
pattern) + report that visual validation was skipped and why.

## Commit

`feat(payrun): the wizard asks for the month's spreadsheet instead of silently
running without it` — explicit staging, no push.

## Report back

Gate/coverage behaviour on live ABM (does ABM's scheme have excel bindings?
state the count), test counts + EXITs, per-DB upgrade EXITs, screenshots or
the JSON-RPC evidence, deviations.
