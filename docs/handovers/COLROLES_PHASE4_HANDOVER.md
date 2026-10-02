# COLROLES Phase 4 — Review polish + future-proofing (final phase)

Read `docs/handovers/COLROLES_LEDGER.md` FIRST — standing rules, CR-A decisions, ALL gotchas
(CR1–CR14 from Phases 1-2, plus whatever Phase 3 appended). CR6 (rsync chmod + psql version
verification) and the payobook-company-2 CR (live role validation on abm, not apex) bind every
deploy/validation step. Phases 1-3 are live on all 4 DBs — check `git log --oneline -5` for their
commits and read the three prior handovers' scope sections if you need orientation; do NOT redo
their work.

## Scope — closing the guided end-to-end story

1. **Single-sheet import completion → mapping deep-link**: after a successful single-sheet Excel
   import (both color-coded and plain paths), the completion notification/action carries a role-count
   summary ("41 payroll · 2 identity · 4 bank · 6 people/reference columns") and — when the import
   ran from the studio — reopens Formula Studio with a context flag that auto-opens the mapping
   overlay in employee mode. Studio side: honour a `pbfs_open_people_mapping` (or ctx-param) signal
   in the load path.
2. **Multisheet review polish**: count chips in the Review Components step header (per-role totals)
   and a subtle "likely" dot on rows whose classification tier was fuzzy (carry `column_role_tier`
   on the transients if Phase 1 didn't; display-only, no schema on hr.formula.rule).
3. **Reclassify review dialog** (studio): a small dialog on the config Settings surface (or Tools
   lane) that calls the existing `pb.formula.studio.reclassify_roles(config_id)` and presents the
   diff (code, name, from→to, tier, reason) with per-row accept/skip; Apply writes ONLY accepted
   rows (extend the RPC with an optional `apply_ids` arg or a second `apply_reclassify` RPC —
   choose one, keep `column_role_source` semantics: applying is a human act ⇒ source='user'...
   NO — keep source='auto' when applying an auto-suggestion wholesale; set 'user' only for rows the
   user individually toggled differently from the suggestion. Simpler locked rule: accepted rows
   keep source='auto' (still auto-derived), skipped rows untouched. Document in help text.)
   Never list/overwrite source='user' rows (the RPC already guarantees this — verify).
4. **Flag-gated identity-role-driven export columns** (om_hr_payroll/models/hr_payslip.py — the
   payroll Excel export): today `base_columns` (:1381-1410 pre-Phase-1 numbering; re-locate by
   symbol `base_columns`) hardcodes MSNV / Full name / Unit / Type of labor contract / OT-subject
   with hardcoded lookup keys, plus `_get_mapped_field_value` (+ mapping_cache ~:1444-1450,
   :1507-1520). Add an opt-in boolean on hr.formula.config (e.g. `export_identity_columns`,
   default False, help text white-labelled): when True, the export's leading identity columns are
   built from the config's identity/profile-role rules (in sequence order) instead of the hardcoded
   list; when False (default) the output must remain BYTE-IDENTICAL to today. This touches
   om_hr_payroll — per CR1 the field lives on hr.formula.config (pb_hr_payroll_formula) and the
   export override goes via _inherit IN pb_hr_payroll_formula if hr_payslip's export method is
   cleanly overridable; only touch om_hr_payroll directly if _inherit is impossible, and in that
   case do NOT add om to the -u list without checking the reverse-dep cascade risk (CR1) — prefer
   the _inherit route strongly.
5. **vi_VN.po completeness sweep** for all Phase 1-4 strings (msgfmt --check clean; spot-translate
   sensibly).
6. **Program docs**: update COLROLES_LEDGER.md status header (all 4 phases done) and append final
   gotchas.

**Binding non-goals**: no new models; no batch behavior changes beyond the export flag path; no
promote-to-custom-field (explicitly future); nothing that alters default-off export output.

## Verified facts

- Single-sheet wizard completion: `_import_from_excel_color_coded` returns a client action/dict at
  its end (symbol: end of the method, past the rule-creation loop — re-locate; it builds a message
  with counts `_('%d rules imported…')` around old :476). The wizard is launched from the studio
  via the import tool; the studio reload path is `load()` (formula_studio.js, symbol) and the
  overlay opener for employee mapping is the design-lane "mapping" tool / `openMapping`-style
  method (symbol — find how Phase 3 opens employee mode; reuse exactly that).
- Multisheet transients + Review list: see Phase 1/3 handovers; `hr.formula.multisheet.column.selection`
  and `...component.preview` models in wizards/multisheet_import_wizard.py; Review list in
  wizards/multisheet_wizard_views.xml. Phase 1 added `column_role` to both transients — check
  whether a tier field exists; add to TRANSIENTS ONLY if missing.
- `reclassify_roles` RPC: pb_formula_studio.py (Phase 1; symbol) returns
  {ok, changed:[{id, code, from, to, tier, reason}], counts}. `_can_edit()` gate.
- Settings surface: state.view === 'settings' blocks in studio.xml (symbol: settingsTab); Tools
  lane: `commandLanes` getter (formula_studio.js, symbol) — add the "Review classification" tool in
  the govern lane with a T(...) entry + CmdIco branch (see Phase 2's icon additions as precedent).
- Export: om_hr_payroll/models/hr_payslip.py symbols `base_columns`, `_get_mapped_field_value`,
  `_lookup_input_value`. The export entry method — locate it (the xlsx builder using
  report_visible_string_payload, symbols around :1465-1566 pre-Phase-1).
- Versions: bump both manifests one step above Phase 3's values (verify current first).

## Numbered test cases

1. Single-sheet import (fixture): completion payload contains per-role counts; with studio context,
   reopening auto-opens the mapping overlay (Chrome-MCP tour on abm using the ABM Template.xlsx in
   /Users/adity/Documents/GitHub/gitlocal/ABM/ against a THROWAWAY test config created for the tour
   and deleted afterwards via the Phase-0 delete path — the config-level delete guard allows it
   since no payslips reference it).
2. Multisheet Review: chips match per-role counts; likely-dot renders only on fuzzy-tier rows.
3. Reclassify dialog: shows diff on abm config 7 (expect ≥0 rows), accept-some writes only accepted
   ids, skip leaves rows untouched, source='user' rows never listed (craft one to prove).
4. Export flag OFF: xlsx export of an existing payobook payslip batch is byte-identical to
   pre-change output (download twice, hash compare — run the export before your change lands and
   after, same slip set).
5. Export flag ON (demo config): leading columns = identity+profile role rules in sequence order,
   values resolved; flag help text white-labelled.
6. msgfmt --check clean; no "Odoo" in any new string.
7. Full module test suites still green (pb_hr_payroll_formula + pb_formula_studio Odoo tests as
   runnable in CI form; local pure-python tests pass).

## Deploy + verification

Ledger ritual (CR6 chmod + psql latest_version) ×4 DBs; restart; Chrome-MCP validation on abm
(tour test 1, dialog test 3) and payobook (export tests 4-5 — export runs server-side, validate via
downloaded files/hashes); screenshots. Self-review; ONE feature-scoped commit, no push. Update the
ledger status header.

## Report back

Per-test results (incl. export hashes equal/differ as expected), screenshots taken, deviations, new
CRs, files touched, final manifest versions, commit hash — plus a 5-line program wrap summary
(what a payroll admin can now do that they couldn't before Phase 1).
