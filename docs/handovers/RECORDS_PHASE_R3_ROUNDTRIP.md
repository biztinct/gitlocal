# RECORDS Phase R3 — export · import round trip, and the remaining doors

Program: RECORDS. Phase 3 of 3. Module **`pb_records`** (built in R2) + doors in
`pb_formula_studio` (Journey) and `pb_payrun_wizard` (Pay-data step). Read
`docs/handovers/RECORDS_LEDGER.md` (standing rules + every `RD` entry R1/R2 added), then
`RECORDS_PHASE_R2_DESK.md` for the desk's API (`get_fields`, `search_people`, `preview_changes`,
`apply_changes`, `undo_apply`) — R3 reuses it and adds nothing to the write path. R1 and R2 are
committed; do not change their behaviour.

## The ask (owner's words, 2026-08-29)

> "Provide easy excel import facility to update the database directly … let user select the
> fields — employee or contract or bank etc which are already mapped — then provide an export
> utility to export the template or even data inside. And then import it back so employee field
> values go to the employee model, contract field values go to the contract table etc."

## Scope

- **Export** the current desk view (filters + picked fields) as `.xlsx`, with values or as a
  blank template.
- **Import** such a file (or any `.xlsx`/`.csv` whose headings match) back into the SAME review
  drawer → the SAME `apply_changes` → the same audit + Undo. Routing to employee / contract /
  bank / contract component is by column id; the person never chooses a table.
- Doors: Journey landing's "Payobook records" card gets **Open Records Desk**; the pay-run
  Pay-data step gets a quiet link; the desk's no-mappings empty state links to Mapping (R2 did
  this if `pb_formula_studio` is installed — verify).

**Non-goals (binding):** native `base_import` (unused anywhere in the repo; cannot express
label-typed selections, bank-role assembly or component routing; would bypass audit/undo);
creating employees from a file (a row that matches nobody is LISTED, never created — the Import
door exists for onboarding); any change to `hr.payroll.import.batch`.

## Design bar (binding — score the report against it)

> "Extreme WOW, intuitive, out-of-this-world experience, best in class." Every surface names its
> hero moment; zero dead-ends (empty/loading/error/partial/huge states designed, every failure
> names its reason and next step); plain language over code vocabulary; motion with purpose;
> keyboard + bulk ergonomics; measured against the best SaaS tool in the category, not stock Odoo.
> Lucide icons, never emoji. Chrome-MCP walk every flow. Never the word "Odoo" in a user-visible
> string.

**R3's hero moment:** drop the file you exported back onto the desk and, before anything is
saved, see *"This file changes 41 values on 19 people · 3 rows match nobody · 2 values need a
look"* — the same review drawer as the grid, every row `old → new`, refused cells explained in a
sentence, unmatched rows named — then one Apply, one toast, one Undo. The file feels like a
detached view of the grid, not a separate import system.

## Verified plumbing — do NOT re-derive

- Workbook precedents: `pb_hr_payroll_formula/integrations/excel_connector.py:616
  generate_template` — bold header row, `EAF1FB` fill, **header cell `comment` carrying the
  technical identity** (`:703-707`, author "Payobook"), `freeze_panes='A2'`, column widths
  `:708`; `pb_formula_studio/models/pb_formula_studio.py:12032 export_living_workbook` (styled
  headers, `DefinedName`, number-format gotcha at `:12020`); reader precedent
  `import_test_samples` `:12197` (header → field by name/code/letter, `{'ok': False, 'msg'}` on
  every failure, never raises). openpyxl is the declared dependency
  (`pb_hr_payroll_formula/__manifest__.py:52`); `.csv` via the stdlib.
- Row identity: `payroll_import_batch.py:814 _identity_from_file_row(raw)` (code / name / email
  header candidates, `_normalize_code`) and `_find_employee(line)` `:1183` (ladder:
  `pb_source_ref` → code fields → email → name). Do not build a batch line: reuse the header
  candidate lists and `_normalize_code` through a probe (`Batch.new({'formula_config_id'})`),
  and match in `pb_records` with the same order — `barcode`/`employee_id`/`pb_source_ref`
  (whichever exist on `hr.employee`) → `work_email` (case-insensitive) → exact `name` (unique
  only; a duplicate name is "ambiguous — 2 people called X", not a guess).
- Desk API (R2): `get_fields(config_id)` cards (`id`, `label`, `ttype`, `selection`), `search_people`
  (values with key + label), `preview_changes(config_id, changes)` (`changes = [{emp_id,
  field_id, value}]`), `apply_changes(config_id, changes, note, source)`, audit `pb.records.apply`
  (`source` — add `'import'`).
- Selection round-trip: R2's `_selection_key(field, value)` accepts label or key. Export writes
  LABELS (what a person reads) — the import must therefore go through that helper; test it.
- Journey door: `pb_formula_studio.py:6940-6952` builds the "Payobook records" system node
  (`'door': {'mode': 'employee'}`); `journey_board.js:530 openDoor(node)` → `mapping_studio.js:819
  openDoor(door)` switches TAB only (`MODES` guard `:820`). A Records Desk door is NOT a mode — add
  a secondary action on that node (`node.actions = [{label, xmlid, params}]`) rendered as a small
  button, opened via `this.env.services.action.doAction(xmlid, {additionalContext/params})`; guard
  on `registry.category("actions").contains("pb_records_desk")` so a database without
  `pb_records` renders no dead button (the `plan_launcher.js:204` probe pattern).
- Pay-data step: `pb_payrun_wizard/static/src/xml/payrun_wizard.xml` data step (R1 added the mode
  cards); a quiet link under the coverage panel.
- Access: exports must respect the same read scoping as `search_people` (company, ACL); import
  must go through `apply_changes` (its whitelist + ACL rails).

## Build

### Server — `pb.records.desk` additions

- `export_records(config_id, filters, field_ids, mode='data'|'template')` →
  `{ok, file_b64, filename, mimetype, rows, columns}`; `filename = "<scheme code or 'records'>_
  records_<YYYY-MM-DD>.xlsx"`. Workbook:
  - Sheet "Records": row 1 headings — `Employee code`, `Name`, `Work email` (identity, grey
    fill `EEF2F6`, **cell comment "Identity — used to match the row; not imported"**), then one
    column per picked card: heading = card label (e.g. `SHUI participation`), comment =
    `id: f:hr.contract:shui_participation` + a plain hint line (allowed values / "Yes or No" /
    "Must already exist" / date format). Row 2+ = one row per person in the current filter (or
    identity only when `mode='template'`). Values: selection LABEL, m2o display name, booleans
    `Yes`/`No`, dates as real Excel dates (`number_format = 'yyyy-mm-dd'`), numbers as numbers.
    Selection and boolean columns get an openpyxl `DataValidation(type='list')` dropdown of the
    labels (skip when the joined list exceeds Excel's 255-char formula limit — then rely on the
    comment). `freeze_panes='D2'`, widths as `generate_template`, autofilter on the header row.
  - Hidden sheet `_payobook` (`sheet_state='hidden'`): `column_index | field_id | label` plus
    `config_id` — the durable identity when a person retypes a heading. Never the primary key
    for anything; comments and this sheet are BOTH read on import.
  - Cap: 10,000 rows per export (the desk's `search_people` paging loop); say so in the return
    when truncated (`truncated: true`) — never silently.
- `import_peek(config_id, file_b64, filename)` → `{ok, msg?, summary: {rows, people_matched,
  people_unmatched, changes_ok, changes_same, changes_refused, columns_used, columns_ignored:
  [heading]}, changes: [{emp_id, field_id, value}], unmatched: [{row, code, name, email, why}],
  refused: [...] (from preview), identity: 'code'|'email'|'name'}`. Steps: parse (`.xlsx` via
  openpyxl `read_only=True, data_only=True`; `.csv` via `csv.Sniffer`); resolve columns — comment
  `id:` → hidden sheet → heading equals a card label (case/space-insensitive) → else *ignored and
  named*; identify people per row (ladder above); build `changes`; call `preview_changes`; return
  everything the drawer needs. Creates **no** batch, line, employee or payslip. Every failure is
  `{'ok': False, 'msg': <plain sentence>}`: "This file has no heading row", "None of the
  headings match a field this scheme maps — export a template from this desk first", "This
  is not a spreadsheet (.xlsx or .csv)". Size guard 10 MB.
- `apply_changes(..., source='import')` — the existing method; `pb.records.apply.source` selection
  gains `import`; the History row shows the filename in `note` when none was typed.

### Client — desk additions

- Header gains **Export** (split button: *Export with data* / *Export blank template*; while
  building, the button shows a progress spinner and the toast says "Exporting 1,240 people…").
  Download through a `Blob` from `file_b64` (the `pb_people.bulkExport` precedent) — no
  controller.
- **Import**: a drop zone in the header ("Drop a records file, or click") AND drag-anywhere over
  the grid (overlay "Drop to review changes" — the `.pw-drop` precedent from the pay-run
  wizard). On drop → `import_peek` with a busy state "Reading <file>…" → the review drawer opens
  in *file mode*: summary line, three tabs **Changes · Unmatched · Ignored columns**, the
  identity method ("matched by employee code"), Apply button "Apply 41 · leave 2". Cancel discards
  — nothing was written. After Apply the grid reloads and the History row reads
  "Imported <file> — 41 values on 19 people".
- Unmatched rows are actionable: each has *Find person…* (typeahead over `lookup`-style search
  by name/code/email) to bind the row by hand, which moves its values into `changes` live.
- Empty/edge states: a template with no data rows ("This file has headings only — fill it in and
  drop it again"); a file for a different scheme (the hidden sheet's `config_id` differs → warn
  and offer to switch scheme); every row already equal ("Nothing to change — every value in
  this file already matches"); a huge file (progress by rows; the 10k cap explained).
- Keyboard: the drawer's tabs are arrow-key navigable; Apply on ⌘/Ctrl+Enter.

### Doors

- Journey (`pb_formula_studio`): the "Payobook records" node gets `actions: [{label: "Open
  Records Desk", icon: 'database', tag: 'pb_records_desk', params: {config_id}}]`; the board
  renders it as a small secondary button on the node (does not change the node's existing door);
  probe the actions registry before rendering. Bump `pb_formula_studio`.
- Pay-data step (`pb_payrun_wizard`): under the coverage panel, a muted line with a link
  *"Need to change what's on record instead? Open Records Desk"* → `doAction` on
  `pb_records.action_pb_records_desk` with `config_id`; rendered only when the action exists.
  Bump `pb_payrun_wizard`.

## Safety rails

- Import never writes outside `apply_changes`; the R2 whitelist, company and ACL rails apply
  unchanged. No employee/contract is created from a file. `hr.payslip` untouched (count + md5).
- Export reads through `search_people` semantics only (no wider domain).
- No "Odoo" in UI/exported files (the workbook's comments and sheet names included — the hidden
  sheet is `_payobook`); no emoji; plain language.

## Numbered test cases (`pb_records/tests/test_records_r3_roundtrip.py`)

Fixtures: R2's scheme + three people (reuse R2's helpers).

1. **Round-trip identity** — `export_records(mode='data')` → `import_peek` on the same bytes
   → `changes_ok == 0`, `changes_same == total cells`, `people_unmatched == 0`; selections and
   dates survive (label written, key resolved; Excel date → `YYYY-MM-DD`).
2. **One edited cell** — change one value in the workbook (openpyxl) → exactly one `ok` change
   with the right `emp_id`/`field_id`/coerced value; Apply → record updated; audit row has
   `source='import'`.
3. **Unmatched row** — a row with an unknown code AND email → listed in `unmatched` with the
   sentence; not created; the rest of the file still previews.
4. **Ambiguous name** — two employees with the same name, a row carrying only the name →
   unmatched with "2 people called X — add the employee code".
5. **Unknown heading** — an extra column "Shoe size" → `columns_ignored` names it; nothing else
   affected.
6. **Retyped heading, hidden sheet intact** — heading renamed to "SHUI?" → still resolved via
   the hidden sheet / comment.
7. **Bank routing** — `Account number` + `Bank name` columns → one `res.partner.bank` on apply
   (R2's rule: add-never-replace).
8. **Component routing** — a contract-component column → advantage line amount + `hr.contract.
   advantage.change` row.
9. **CSV** — the same data as `.csv` → same preview.
10. **Bad files** — an empty file, a `.docx` renamed `.xlsx`, a workbook with no heading row →
    `{'ok': False}` with the specific sentence each time; no exception leaks.
11. **Template** — `mode='template'` has identity rows and empty value cells; the data
    validations exist on the selection/boolean columns; comments carry `id:`; hidden sheet
    present and hidden.
12. **Cap** — 10,001 people → `truncated: True` and 10,000 rows.
13. **Neutrality** — `hr.payslip` count + md5 unchanged across the suite; no employee created
    anywhere in the suite (count before/after).
14. **Source assertion** — no "Odoo"/emoji in the new XML/py strings AND in the exported
    workbook's text (sheet names, headings, comments).

Hoot (`records_grid.test.js` additions): the drop overlay appears on dragenter and hides on
dragleave; the drawer's file mode renders the three tabs and the Apply label counts.

## Deploy + verify

1. Baseline on abm (`/pb_records,/pb_formula_studio,/pb_payrun_wizard`) then after.
2. Bump `pb_records` → 19.0.1.1.0, `pb_formula_studio`, `pb_payrun_wizard`; assets changed ⇒
   restart + clear `/web/assets/%`.
3. Deploy abm → `-u` → Chrome-MCP (ash@biztinct.com / J5validate!2026): export with data for one
   department → open the file locally with openpyxl and change 3 values (one selection by label,
   one boolean to "Yes", one number) + add an unknown-person row → drop it on the desk → read
   the summary line and each tab → Apply → verify by `call_kw` → History → Undo → verify.
   Then export a blank template and drop it back unchanged ("headings only" state). Then the
   Journey door and the Pay-data link. Screenshot every state. **Restore anything you changed.**
4. payobook + payobook_template: deploy, `-u`, assets cleared, smoke export on payobook's 4.5k
   roster (time it; report the number).
5. Tree hashes + `latest_version` on the three DBs.
6. Commit (explicit paths): `feat(records): export the desk to Excel and import it back through
   the same review + apply path (R3)`.

## Report back (in this order)

- Test counts baseline vs after per DB; payslip md5; employee-count proof.
- Each numbered case + hoot: pass/fail with the evidence line.
- Chrome walk with exact strings, screenshot paths, the payobook export timing, what you
  restored.
- Design-bar self-score and what you would still improve.
- `RD` entries appended.
- Anything left out and why.
