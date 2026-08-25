# JOURNEY Phase J3 — Truth & guardrails

> **DELIVERED 2026-08-25.** Live on abm · acme · payobook · payobook_template at
> pb_hr_payroll_formula 19.0.1.81.0 · pb_formula_studio 19.0.1.136.0 ·
> pb_import 19.0.1.4.0 · pb_import_wizard 19.0.1.2.0. Full outcome, numbers and the
> empty-feed-guard reasoning are in `JOURNEY_LEDGER.md` (phase status + MJ14–MJ19).
>
> **Deviations from this document, all deliberate:**
> 1. **The resolver line numbers below are pre-J2 and shifted ~+199** (the function is at
>    `payroll_import_batch.py:2832`, the pre-pass at `:3101`). The internals were as
>    described; only the offsets moved, exactly as the Pre-flight clause anticipated.
> 2. **The empty-feed guard tests the SOURCE, not the transformed result.** This document
>    assumed testing the output would do. It cannot: `transform_value` short-circuits an
>    empty input to `default_value`, which is a `fields.Float(default=0.0)` — a column with
>    no null — so every empty feed value came back as a perfectly good `0.0`. A non-zero
>    default is the only "somebody stated this" signal available, and it is what makes a
>    `default_if_empty` wire count as a delivery. See MJ15.
> 3. **The conflict choice is a separate read-only `source_conflict_probe` adapter** plus an
>    optional trailing `resolve=` on the two existing `*_mapping_create` calls, rather than a
>    flag on create. That is what makes the cancel path provably zero-write: no writing RPC
>    is ever sent. `resolve=None` is byte-identical to pre-J3 behaviour.
> 4. **`provenance_token(..., origin=...)` was fixed** beyond the listed scope (one word). It
>    was hardcoded to `'excel'` with a comment saying it should change once a run could carry
>    two sources — S3 made that true and the line did not follow, so the name ladder reported
>    `src='excel'` about values that arrived in a feed. Excel runs are unaffected. See MJ17.
> 5. **Test 11's `add_rule` grep was narrowed to the manifest's LIVE bundles.** A folder-wide
>    grep also hits `grid_actions.js`, a SECOND uncalled file calling the same nonexistent
>    method, already commented out of the manifest. Recorded, not swept — see MJ18; a J4+
>    broom should take the whole commented-out grid bundle as its own scoped decision.
> 6. **Test cases 4 and 5 (replace / keep) were proved differently.** Keep was exercised LIVE
>    on abm (rule 581, diffed, restored). Replace unlinks live `hr.integration.field.mapping`
>    rows, which cannot be restored with their original ids, so it is proved by
>    `test_03d`/`test_03f` — which assert the unlink precisely — rather than by mutating
>    abm's 59 real wires. Cancel was proved live with an empty MF37 diff.
> 7. **Chip labels are short pills with the full sentence in the tooltip.** This document's
>    example wording ("Also wired to ⟨connector⟩ — the feed wins on system runs") clipped
>    mid-word on a 280px card when tried live; it is now the `title`, and the pill reads
>    `Wired twice` / `Feed wins` / `Spreadsheet fallback`.

**Read first:** `docs/handovers/JOURNEY_LEDGER.md` (programme frame, J1+J2 outcomes, ALL MJ
gotchas), then the standing rules of `MAPFIX_LEDGER.md` (deploy ritual, MF12/MF17/MF35/MF37/MF41,
CR6/CR20) and `SOURCING_LEDGER.md`. **White-label absolute: no user-visible string may say
"Odoo".** Branch 19.1. One feature-scoped commit (explicit staging, ledger + this handover
included; leave `ABM/ABM Template.xlsx` unstaged as found). **Do not push.**

**Pre-flight (this handover was drafted while J2 was in flight):** before editing anything, read
J2's phase-status entry and MJ gotchas in the ledger, then re-verify every file:line target below
against the tree as it stands — J1/J2 shifted lines in `pb_formula_studio` JS/XML and J2 touched
`pb_hr_payroll_formula` (shared parser helper, template builder). The RESOLVER internals cited
below were surveyed pre-J2 and no phase was allowed to change them, so they should hold exactly.

## Mission

The engine already tells the truth internally — provenance records who fed every value, imports
write people-data back into records, and empty sources fall back to the record. J3 makes the UI
tell the same truth and closes the four places the plumbing silently lies:

1. **Two-way ⇆ presentation** on Employee & contract — the same mapping row writes the record on
   import AND feeds the pay run when the file/feed is empty; today the board only says "send to".
2. **The source-conflict guardrail** (owner decision J-D3) — wiring a second live source onto a
   fed component asks **replace / keep as fallback / cancel**; today an API wire and an Excel
   binding coexist silently and the wire wins without a word.
3. **Per-feed pulls run transformation rules** — today only the legacy "Pull Data" button does,
   so rule-fed components quietly read empty after a per-feed sync.
4. **Batch-free payslips read API data** — today the live-payrun path hits a literal
   `TODO … pass` and API sourcing works only through an import batch.

Plus the broom: the dead `source_type='connector'` selection value and the dead grid code go.

## Scope & the one delicate decision

### S1 — Two-way ⇆ on Employee & contract (presentation only)

- Tab label → **`Employee & contract ⇆`** (all doors/palette references that name it follow).
- Wires on THIS adapter render double-headed (⇆) — a canvas capability keyed off an adapter flag
  (e.g. `bidirectional: true` in the employee adapter's data payload), not a global change.
- Every mapped card gets a plain-language direction note derived from what the row actually does:
  - `destination_type='field'` (employee/contract): *"On import: fills ⟨Model › Field⟩. On pay
    run: used when the file or feed leaves this empty."* — both halves are true
    (writeback `payroll_import_batch.py:2131-2241`; read-back `:2843-2872` + `:3122-3125`).
  - `destination_type='bank_account'` rows: *"On import: builds the bank account."* — write-only;
    the resolver never reads bank parts back (`get_mapped_input_value` covers employee/contract
    fields only). Do NOT print the read-back half here.
  - Contract-component cards keep their existing wording.
- Server: extend `employee_mapping_data`'s per-item payload additively (a `direction` /
  `direction_note` key). No signature changes.

### S2 — The conflict guardrail (J-D3)

**The trap being killed:** a component can hold an `excel` binding while a live
`hr.integration.field.mapping` wire targets it; on a `connector`/`api_data_store` batch the
connector pre-pass (`payroll_import_batch.py:2902-2926`) fills the value FIRST and the loop skips
any code already present (`:2978`) — the Excel binding never applies, nothing warns anyone.

- **At draw time (both boards):** when a wire/binding is drawn onto a component that already has a
  DIFFERENT live source (excel binding vs API wire, or an API wire on another connector), open a
  three-way choice — this extends the existing `_binding_replaced` swap-toast machinery
  (`pb_formula_studio.py:5108-5126`), it does not replace it:
  - **Replace** — remove the other source (unlink the wire / clear the binding via the existing
    delete paths `api_mapping_delete` `:5138-5141` / `import_mapping_delete`), set the new one.
  - **Keep as fallback** — keep both, with honest wording fixed by the ladder: the SYSTEM FEED is
    primary on API runs and the spreadsheet column is the fallback (never the reverse — J-D5).
    The dialog must say exactly that.
  - **Cancel** — no write at all (MF37: prove it).
  Same-source redraws (excel→excel, same-connector feed rewires) keep today's silent-swap + toast.
- **Conflict chips:** any component in the dual state (however it arose — including pre-existing
  live rows) renders a chip on both boards: e.g. *"Also wired to ⟨connector⟩ — the feed wins on
  system runs"* / *"Also bound to spreadsheet ⟨key⟩ — used when the feed is empty"*. Server-side
  detection lives in ONE helper reused by both adapters' data payloads.
- **The empty-feed guard (the delicate one, read carefully):** "keep as fallback" is only honest
  if an EMPTY feed value actually falls through. Verify what the pre-pass does when
  `mapping.source_field` is absent/empty in `raw_data` (`:2902-2926`): if it writes None/''/0 into
  `input_values`, the loop's `if rule.code not in input_values` skip (`:2978`) means the binding
  and every fallback rung are dead even when the feed delivered nothing. If so, guard the
  pre-pass: **an empty extracted value does not claim the slot** (mirror the resolver's own
  emptiness test used at `:3071-3110`; a transform's `default_if_empty` output counts as
  non-empty). This is NOT a ladder reorder (J-D5 intact — the pre-pass still outranks everything
  when it HAS a value); it is what makes the owner's "API empty → fall back" requirement true on
  the pre-pass path, matching what the bound branch already does. Treat as in scope; flag
  prominently in the report; prove with resolver-level tests and the batteries.

### S3 — Per-feed pulls run transformation rules

`action_pull_endpoint` (`integration_connector.py:1114`) must run
`hr.api.transformation.rule._execute_for_records` over the stores it created/updated, exactly as
`action_pull_data` does (`:1475`) and `action_recompute_transformations` does (`:1579`). Reuse the
same invocation (extract a small helper if the two call sites differ); scope it to the pulled
records, not the whole store.

### S4 — Batch-free payslips read API data

`hr_payslip_formula._get_formula_input_values` (`hr_payslip_formula.py:340-416`): the connector
branch (`:398-405`) is `# TODO … pass`. Close it: when the payslip's config has `connector_id` and
live field mappings, read the employee's latest relevant `hr.api.data.store` rows (match via the
store's employee matching, `data_type` in employee/salary, prefer `state='extracted'`/latest
`version`), build the merged blob with `get_mappable_data()` (`api_data_store.py:406` — computed
overrides extracted), and apply the SAME mapping+transform application as the batch pre-pass —
extract a shared helper on the connector/mapping model rather than duplicating the loop, and apply
the S2 empty-value guard identically. Provenance: record these with the existing `feed`/`rule`
source kinds and a `via` value consistent with `input_provenance.py`'s vocabulary (reuse an
existing `via` if one fits; if a new one is genuinely needed, add it to the vocabulary file, its
JS mirror `source_vocab.js`, AND the battery — one vocabulary, three mirrors, MF-style).
Empty result → the existing fallback tail (contract wage / worked-days / default) unchanged.

### S5 — The broom

- Remove `source_type='connector'` from `hr.payroll.import.batch` (`payroll_import_batch.py:89`)
  — no loader exists and `action_load_from_data_store` refuses it (`:645`, self-documented
  `:2874-2887`). Migration: any existing batch rows with that value (count them per DB first —
  expected 0) → `api_data_store`. Update the resolver's `source_type in ('connector', …)` gates to
  match, and the comment block that documents the dead branch.
- Delete the dead `excel_grid_widget.js` `addColumn` path (calls nonexistent
  `hr.formula.config.add_rule`; widget registration already commented out) — remove the dead file
  if nothing imports it, else just the dead method.

**Non-goals (binding):** no resolver ladder REORDER (J-D5 — S2's guard is an emptiness fix on one
rung, not a reorder; nothing else in the ladder moves); no Transformations tab (J4); no Journey
tab (J5); no multi-connector-per-scheme runtime (the J5 lanes will only make the limit visible);
no writeback changes; no changes to J2's on-ramp beyond the conflict chips it may now display.
`om_hr_payroll` untouched (CR1).

## Verified plumbing (surveyed pre-J2 — re-verify per Pre-flight; resolver lines should hold)

- Resolver: `_transform_data_to_formula_inputs` `payroll_import_batch.py:2633`; pre-pass
  `:2902-2926`; skip-if-present `:2978`; bound branch `:3071-3102`; cross-blob fallback
  `:3084-3110`; `binding_empty` tail `:3111-3115`; employee-field read `:2843-2872` used
  `:3122-3125`. Three provenance writers that must stay in sync: import run `:2252-2277`,
  recompute `hr_payslip_formula.py:508-526`, live payrun `:340-416`.
- Conflict state today: `api_mapping_create` unlinks conflicts only within the same connector
  (`pb_formula_studio.py:5087-5088`); `import_mapping_create` (`:5543-5572`) touches no wire;
  swap-report `_binding_replaced` `:5108-5126`; delete paths `:5138-5141` / `:5583-5586`.
  Known live dual state: abm has components wired on two connectors (SOURCING closeout item 7).
- Transformation rules: `_execute_for_records` `api_transformation_rule.py:508/:556-572` writes
  `computed_data`; callers `integration_connector.py:1475`, `:1579`; per-feed pull
  `action_pull_endpoint` `:1114` (does NOT call it); store merge `get_mappable_data`
  `api_data_store.py:406`; store lifecycle `action_extract` `:198`, employee match `:370`.
- Vocabulary: `input_provenance.py:35-44` (8 kinds) + labels `pb_formula_studio.py:436-462` + JS
  mirror `source_vocab.js`; batteries `pb_hr_payroll_formula/tools/{provenance,excel_semantics,
  import_resolution}_battery.py` — ALL must run and pass (MF7: check they actually run).
- Dead code: `source_type` selection `payroll_import_batch.py:89`; refusal `:645`; dead-branch
  self-documentation `:2874-2887`; `excel_grid_widget.js:543`.

## Safety rails

- **NEVER run `action_process` on a live database** (writeback). Resolver behaviour is proved in
  Python tests (transient/demo fixtures) and the batteries, not on live batches.
- **No live external API pulls.** S3 is validated with the demo connector type / recompute path
  and unit tests — do not trigger real Zoho/Darwinbox syncs on live DBs.
- MF37 oracle diffs on abm around all live board probes: `hr_payslip_import_mapping`,
  `hr_integration_field_mapping`, `hr_formula_rule` (config 14 `source_binding*`). Conflict-dialog
  probes must include the cancel path proving zero writes.
- Migrations per ledger convention (`migrations/<version>/post-<slug>.py`, idempotent,
  `table_exists` guard, per-DB counts logged).
- MJ2 (warm server before believing red hoot), MJ5 (no `min(len, calc())`), MJ6 (version-bump
  after late asset edits), MJ7 (clip/layer-aware overlap sweeps).
- Screenshots to `.journey-shots/J3/`.

## Numbered test cases (abm for live UI; Python/batteries for resolver; all pass before commit)

1. Employee & contract tab: label reads `Employee & contract ⇆`; wires render double-headed on
   this adapter ONLY (API/Excel/cycle/scheme wires unchanged).
2. A `field` mapping card shows both direction sentences; a `bank_account` card shows only the
   import half; wording matches §S1 (screenshot each).
3. Python: direction payload is additive — pre-J3 keys of `employee_mapping_data` unchanged
   (assert against a recorded shape).
4. Conflict dialog, replace path: component with an API wire + drawing an excel binding →
   choosing Replace unlinks the wire and sets the binding (DB diff shows exactly that, then
   restore).
5. Conflict dialog, keep-as-fallback path: both rows survive; both boards now show the conflict
   chips with the honest wording; DB diff shows no other change; restore.
6. Conflict dialog, cancel path: zero writes (MF37 diff empty).
7. Pre-existing dual state (no dialog involved): chips render on load for a component that
   already had both sources (abm has real subjects — find one, screenshot, touch nothing).
8. Resolver, empty-feed guard: Python test — connector batch where the feed delivers (a) a value
   → pre-pass wins, provenance `feed`; (b) empty/absent for a component with an excel binding +
   employee mapping → value falls through to the topup/binding path or employee field, provenance
   shows the fallback (`via='fallback'`/`'binding_empty'` family); (c) `default_if_empty`
   transform → counts as non-empty, pre-pass wins. All three batteries green.
9. S3: after a per-feed pull (demo connector), `computed_data` is populated and a rule-bound
   component resolves — proved in a Python test; `action_pull_data` and
   `action_recompute_transformations` behave exactly as before.
10. S4: a payslip computed with NO import batch, config with connector + mappings + a staged demo
    data-store row → component gets the feed/rule value with correct provenance; with the store
    empty → existing fallback tail unchanged (both as Python tests).
11. Broom: `source_type='connector'` gone from the selection and all gates/comments consistent;
    migration logged 0 (or N→converted) rows per DB; dead grid code gone; a grep for
    `add_rule`/`'connector'` in the touched files finds no orphan.
12. Grep gates: no user-visible "Odoo"; conflict/direction strings translated (`_t`/`_lt` per
    house style) and MJ3-safe (no module-scope `_t` stringified in hoot).
13. Suites: record pre-phase baselines on abm first (post-J2 numbers from the ledger), finish
    at-or-above with new tests on top — 0 failed, 0 errors; hoot additions cover the ⇆ rendering
    and chip rendering (translation-free facts only, MJ3).
14. Layout + console: MJ7-style sweep at 1440 and 1024 with a conflict dialog open and chips
    visible; 0 overlaps, 0 console errors.
15. Deploy per MAPFIX ritual (`-u` every touched module) over abm acme payobook
    payobook_template; `latest_version` verified in psql on all four.

## Report back

Versions shipped · per-case results (1–15) · suite + battery tallies vs recorded baselines ·
MF37 diffs (incl. the cancel-path zero-write proof) · migration counts per DB · the empty-feed
guard decision as implemented (what the pre-pass did before, what it does now, why J-D5 holds) ·
screenshots index · deviations with reasoning · new MJ gotchas appended to `JOURNEY_LEDGER.md`
(+ phase-status entry) · the single commit hash. Do not push.
