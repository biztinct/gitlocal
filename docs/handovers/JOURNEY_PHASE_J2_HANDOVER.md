# JOURNEY Phase J2 — The Excel on-ramp

**Read first:** `docs/handovers/JOURNEY_LEDGER.md` (programme frame, J1 outcome, gotchas MJ1–MJ7 —
MJ2 warm-server, MJ5 libsass min/calc, MJ6 version-bump-after-late-edit and MJ7 overlap-sweep
especially), then the standing rules of `MAPFIX_LEDGER.md` (deploy ritual, MF12/MF17/MF23/MF35/
MF37/MF41, CR6/CR20) and `SOURCING_LEDGER.md`. **White-label absolute: no user-visible string may
say "Odoo".** Branch 19.1. One feature-scoped commit at the end (explicit staging, ledger + this
handover included). **Do not push.**

## Mission

The Spreadsheet side of sourcing is built but unreachable: the `Spreadsheet columns → Scheme` tab
can only show columns that already sit in a saved import batch — otherwise the user types header
names blind, which is why the board has never written a value in production. Meanwhile a
scheme-derived template generator exists with zero callers, and five unlabelled doors lead into
"import". J2 gives Excel a real on-ramp: **drop a file to read its headers (not its data), wire it,
download a template built from the scheme, and hand the same file off as a pay run — one door.**

## Scope

1. **Header discovery.** A dropzone/upload on the `Spreadsheet columns → Scheme` tab of the
   Mapping home (the J1 full-screen host): parse the workbook's headers + one row of sample
   values, persist them on the scheme, fill the board's left lane with them. The copy must say it
   reads headers, not data, and nothing may create an import batch or write any pay value.
2. **Scheme-built template.** "Download a template built from this scheme" on the same tab:
   revive `ExcelConnector.generate_template` (or replace it — see Architecture) so the workbook's
   headers are exactly what the resolver will match on re-import.
3. **One-door handoff.** A primary action on the same tab — "Load this file as a pay run…" — that
   takes the stored file (or a fresh upload) into the EXISTING guided import flow and lands the
   user on the batch it created. No new import pipeline.
4. **Door consolidation (labels + routing, no demolition).** Every legacy door into data-import
   routes to the one guided flow; every door is labelled so "set up columns (structure)" and
   "load this month's numbers (data)" cannot be confused. No model or action deletions.

**Non-goals (binding):** no resolver/precedence change (J-D5); no conflict dialog or two-way arrows
(J3); no Transformations tab (J4); no Journey tab (J5); no change to the multisheet STRUCTURE
import wizard's detection behaviour (MF23's colour convention stays — that wizard defines columns,
not data, and is out of scope beyond labelling); no new parsing engine (see the parity rule below);
no API/connector-side changes. `om_hr_payroll` untouched (CR1).

## Verified plumbing (do not re-derive)

**The Excel mapping board (all `pb_formula_studio/models/pb_formula_studio.py`):**
`import_mapping_data` `:5416` (its docstring records the board "has never written a value" — update
that comment when it stops being true, test 13); left lane built by `_import_left_columns` `:5515`
from three sources — first line of an existing batch (`_import_batch_columns` `:5404`), existing
`source_binding_key`s, legacy `data_source_field`s — with free-typed `can_add` fallback
`:5504-5508`; `import_mapping_create` `:5543` writes `set_source_binding('excel', col,
origin='board')`; `import_mapping_delete` `:5583-5586`. NOTE: J1 moved the host to the full-screen
`mapping_studio.js/.xml` — line numbers in those files have shifted from pre-J1 surveys; the server
file's numbers above were taken pre-J1 and the J1 report says server adapters got **zero changes**,
so they should hold. Verify an edit target if it doesn't match.

**Parsing (the loader's own path — this is what the board must agree with):**
`hr.payroll.import.batch.action_load_file` `payroll_import_batch.py:404` — multisheet branch when
any rule has `source_sheet_name` (`:426` → `_load_multisheet_data` `:725`, keys shaped
`"Sheet|Header"` and `"Sheet|Letter"`), else `ExcelConnector.load_file`
(`integrations/excel_connector.py:71`) producing `{header: value, ColLetter: value}` dicts
(`:459-465`). The multisheet STRUCTURE analyzer (`load_workbook_multisheet` `:618`,
`header_detector.py`) refuses plain workbooks (MF23) — it is the WRONG tool for reading a filled
pay file's headers; the loader path above is the right one.

**The dead template generator:** `ExcelConnector.generate_template(rules)`
`integrations/excel_connector.py:575` — zero callers repo-wide. Existing precedents:
`formula_import_wizard.action_download_template` `:1134` (hardcoded 5-column sample — leave it, it
belongs to structure import) and `pb.formula.studio.export_test_template` `:9083` (real headers
from input component names, feeds `import_test_samples` `:9294` — a good pattern to mirror, not to
reuse in place).

**The guided import flow (reuse, don't rebuild):** `pb.import.wizard.create_and_load`
(`pb_import_wizard/models/pb_import_wizard.py:111`), surfaced from the Import cockpit
(`pb_import/models/pb_import.py:30` LAUNCH_CANDIDATES); batch cockpit `pb_import_batch/models/
batch_cockpit.py`. Follow pb_import_wizard's existing discard-and-re-read orchestration; JS imports
from the kit use the `@pb_import_kit/js/…` path (and per MJ2, never let a host/kit import leak into
the canvas hoot bundle).

**The five data-import doors to consolidate:** menu "New Import"
(`pb_hr_payroll_formula/views/menu_views.xml:70` → `payroll_import_views.xml:432`), menu "Import
Batches" (`menu_views.xml:64` — this one is history/browse, label it so), scheme stat button
`formula_config.action_launch_payroll_import` (`formula_config.py:1426`), connector stat button
`integration_connector.action_launch_payroll_import` (`integration_connector.py:1593`), and the
guided wizard itself. Plus the sixth CONFUSER: the structure import button "Import from Excel"
(`formula_config.action_import_from_excel_multisheet` `formula_config.py:1294`,
`views/formula_config_views.xml:41`) — relabel it so it reads as scheme setup (e.g. "Set up columns
from Excel"), do not change its behaviour.

**Known-good fixture:** `ABM/ABM Template.xlsx` (MF23: 99 components, single sheet `SEVL`, PK
header "Employee Code") — abm's config 14 (AB Mauri, 99 components) matches it. Note the working
tree carries an uncommitted modification to this file — leave it unstaged, as J1 did.

## Architecture

- **One parser, two consumers (the load-what-you-saw guarantee).** The header reader MUST run the
  loader's own parsing (the `action_load_file` branch logic: multisheet keys when the scheme is
  multisheet, else `ExcelConnector.load_file` keys) over the first data row(s), and take the keys
  as columns + first-row values as samples. Refactor the branch into a small shared helper on the
  batch model or connector rather than copying it. If the board shows a column, the loader will
  produce that key for the same file — this invariant is test 5 and is the entire point.
- **Persistence.** Store on `hr.formula.config`: the uploaded file (binary, `attachment=True`),
  filename, read date, and the parsed columns as JSON (`[{key, sheet, header, letter, sample}]`).
  New server RPC (e.g. `import_mapping_read_headers(config_id, file_b64, filename)`) analyzes,
  stores, returns the columns; `_import_left_columns` merges them as a first-class source (with
  `e.g.` samples and a provenance line "filename · read <date>") ahead of the free-typed fallback.
  Keep `can_add` — typing a header must still work.
- **Template.** Build from the scheme's `input` components: one column per component, header =
  **the resolver-matchable key** (`source_binding_key` when `source_binding == 'excel'`, else the
  component name), plus the employee-identifier PK column first. Multisheet schemes: one sheet per
  `source_sheet_name`, headers under their own sheet. Rework `generate_template` rather than
  writing a parallel generator — or replace its body if it's unsalvageable; either way exactly one
  generator exists afterwards and it has callers and tests.
- **Handoff.** The tab's primary button calls the EXISTING `create_and_load` flow with the stored
  file + the scheme, then `doAction`s to the batch cockpit on the created batch. Fresh-upload
  variant re-reads headers too (one gesture updates both).
- **Doors.** Retarget the "New Import" menu action to the guided flow (or the Import cockpit door
  that hosts it — inspect `pb_import`'s LAUNCH_CANDIDATES and follow the cockpit's own idiom);
  scheme/connector stat buttons keep working but arrive in the same flow pre-scoped. Labels:
  data doors say "pay data" / "pay run", the structure door says "columns"/"set up". Audit every
  touched label for white-label compliance.
- **UI restraint.** This is the J1 host — reuse its `.pbim.pbms` design language and the import
  kit's dropzone patterns (`pb_import_kit` SCSS + Lucide icons); no new visual system. MJ5: no
  `min(len, calc(…))` in SCSS. MJ7's sweep method for layout proofs.

## Safety rails

- **NEVER run `action_process` on a live database during validation.** Processing triggers
  writeback into employees/contracts/bank. Test 8 stops at load/match; the created draft batch and
  its lines are deleted afterwards and the MF37-style diff proves the cleanup.
- **The database is the oracle (MF37).** On abm, before/after every live session: row-diff
  `hr_payslip_import_mapping`, `hr_formula_rule` (config 14: `source_binding*`, plus the new
  sample-columns storage), and `hr_payroll_import_batch`/`hr_payroll_import_line` counts+ids.
  Restore anything that moved; the final diffs in the report must be clean (the stored sample
  columns on the config may remain ONLY if left in a state the owner would want — prefer removing
  test residue).
- CR20/MF9 for server stop/start; MJ2 — re-run any red hoot suite on a warm server before
  believing it; MJ6 — bump the module version and re-`-u` after late asset edits.
- Server adapter changes must be additive (new RPC, extended left-lane payload); existing
  signatures and return shapes unchanged.
- Screenshots to `.journey-shots/J2/`.

## Numbered test cases (abm unless said; all pass before commit)

1. Spreadsheet tab with no batch/bindings/sample shows the dropzone empty state; copy says it
   reads the headers, not the data; free-typed add still available.
2. Upload `ABM/ABM Template.xlsx` → left lane fills with the sheet's real headers + `e.g.`
   samples; count matches the workbook; **no** `hr_payroll_import_batch` row created (DB diff).
3. Reload the page: columns persist; provenance line shows filename + read date.
4. Wire a discovered column → component: existing `import_mapping_create` path writes the excel
   binding; undo and restore; MF37 diff clean.
5. **Parser parity (the invariant):** for the same file, the header reader's keys == the keys
   `action_load_file` produces — asserted programmatically for a single-sheet file AND a
   multisheet fixture (build a tiny one in the test).
6. Template download for config 14: headers = resolver-matchable key for every input component,
   PK column first; the file opens (openpyxl); **round-trip**: re-uploading it through header
   discovery matches 100% of input components.
7. Binding-aware headers: a component with `source_binding='excel'` + key `X` emits header `X`,
   not the component name.
8. Handoff: "Load this file as a pay run…" creates a batch via the existing guided flow, lands on
   the batch cockpit, line raw_data matches the file; STOP before process; delete the draft batch
   + lines; DB diff clean.
9. Doors: all five data doors reach the one guided flow (screenshot each); the structure button
   reads as scheme setup; menu "Import Batches" reads as history.
10. Grep gates: no user-visible "Odoo"; no user-visible "Studio" on this surface.
11. Suites: record the pre-phase baselines on abm first (J1 reported Python 74/74 per ledger and
    hoot 62/62), then finish ≥ baselines with your new tests added on top — 0 failed, 0 errors.
12. Layout + console: MJ7-style sweep (clip-aware, layer-aware) at 1440 and 1024 with the
    dropzone, a filled left lane and an open dialog; 0 overlaps, 0 console errors.
13. Truth pass: `import_mapping_data`'s "never written a value" docstring updated; any comment the
    phase falsifies is corrected in the same commit.
14. Deploy per MAPFIX ritual (`-u` list = every touched module) over abm acme payobook
    payobook_template; `latest_version` verified in psql on all four.

## Report back

Versions shipped · per-case results (1–14) · suite tallies vs recorded baselines · MF37/cleanup
diffs · doors checklist with labels as shipped · screenshots index · deviations with reasoning ·
new MJ gotchas appended to `JOURNEY_LEDGER.md` (+ phase-status entry) · the single commit hash.
Do not push.
