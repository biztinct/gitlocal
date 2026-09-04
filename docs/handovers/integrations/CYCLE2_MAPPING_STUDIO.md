# Integrations Program — Cycle 2: the Mapping Studio

> STATUS: FINAL — reconciled against Cycle 1's shipped commits (745d736d, c8aca58a, 2a68bb78, 3d1d7023, 3217c3fc + fixes cf2d197a/5e9bbb5a, ledger W127–W130, deployed & live-verified: payobook module 19.0.1.49.0, 53 endpoint rows, /web/login 200). Remaining "⟲C1" markers mean: the FACT is confirmed shipped, but read the named file for exact symbol names/lines — Cycle 1's edits drifted the pre-C1 line numbers quoted below in the files it touched.

## Cycle 1 shipped reality (confirmed — build on this)
- `hr.integration.endpoint` + `.template` live in `pb_hr_payroll_formula/models/integration_endpoint.py`; the data-type vocabulary is ONE list, `api_data_store.DATA_TYPES`, imported by the endpoint model — reuse it, never retype.
- `hr.integration.field.mapping.endpoint_id` (ondelete='set null') and `hr.integration.mapping.template.endpoint_code` exist; `action_apply_mapping_template` resolves `endpoint_code` against the connector's endpoints and leaves the mapping unstamped when unresolvable.
- `action_sync_endpoint_catalog()` is CREATE-ONLY (matches on `code` with `active_test=False`); `_stamp_endpoint(data_type, status, error)` is called from all five `action_pull_data` branches incl. except-arms.
- Count semantics are contractual: `staged_count` = the board's `_compute_data_store_count` domain (`state != 'archived'`) narrowed by data type; `synced_count` = all rows ever, archived included — feeds sum to the board card's number (test_02 asserts it). **Do not introduce a third definition in the studio; reuse these.**
- Connector cockpit: endpoints strip + inline credentials + kebab'd native form shipped (`pb_import_advanced/models/connector_cockpit.py` grew ~228 lines of RPCs — read the file for the exact RPC names before extending); `test_one_door.py` already amended.
- Settings: `openCard` forwards per-card `context`; single-card auto-open shipped with tests.
- Board: feeds on cards + **a feed scope for the data ledger** shipped (`pb_integrations` 3d1d7023) — the ledger deep-link filter WP below may largely exist; extend, don't duplicate.
- **Degrade rail (fix cf2d197a): a database WITHOUT the feeds table (tenants not yet upgraded) must keep degrading gracefully, not abort its transaction — every new server-side read you add must live behind the same guard pattern (read the fix before writing queries).**
- Ledger is now binding through **W130**. Three that bite this cycle: **W127** — the JS pre-rsync gate is `node --input-type=module --check < file` (the plain file form is a no-op on OWL files); **W129** — `ash@biztinct.com/admin1234` is STALE since 2026-08-12; for live validation create a temporary SINGLE-company system user via `odoo-bin shell` (`company_ids` and `company_id` in the SAME write), use it, remove it in the same session — never touch existing users' passwords; **W130** — a second session drives its OWN Chrome over CDP with `--remote-allow-origins`, and a browser doesn't have to log in through the form (session cookie via shell-minted key works when the form is unavailable).

The owner's core complaint this cycle exists to kill: **"the user gets confused on what he is mapping to what — source and destination"**, "how to change the payroll template", "how to make the source more intuitive and visible", "multiple APIs". The Mapping canvas today is a scrim inside Formula Studio whose target is invisible (the studio-loaded config) and whose source is a bare `<select>`. This cycle gives mapping its own front door and makes the FROM → TO story impossible to misread.

Conventions: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` binding through **W130**; C18.x in `docs/FORMULA_ENGINE_CONVENTIONS.md`. Same environment facts, deploy ritual, commit rules as `docs/handovers/integrations/CYCLE1_ENDPOINTS_AND_NAV.md` §Environment — read that section — EXCEPT its login line: the admin credential quoted there is stale (W129); use the temporary-validation-user procedure above. `demo@payobook.com / demo1234` is still valid for the non-admin persona.

## Verified plumbing (file:line as of 2026-08-20 pre-C1; line numbers may have drifted where C1 touched files ⟲C1)

**The canvas is already a generic, reusable component** — `pb_formula_studio/static/src/js/mapping/mapping_canvas.js:10` (`MappingCanvas`), props `leftItems/rightItems/wires/leftTitle/rightTitle/canEdit/busy/onAccept/onReject/onDelete/onDraw/onSuggest/onTransformPreview/onTransformSave/onRemoveRight` `:12-28`; SVG bezier wires `:68-117`; transform glyph vocabulary (`× ÷ + − ≈ |x| ? ƒ`) `:132-147`; transform popover with 260ms-debounced live preview + supersede token `:176-241`. Template `pb_formula_studio/static/src/xml/mapping_canvas.xml`; SCSS `pb_formula_studio/static/src/scss/mapping.scss`. **Reuse it — do not fork.**

**Current host** — the Formula Studio scrim overlay: `pb_formula_studio/static/src/xml/studio.xml:1761-1935` (header `:1765`, employee/contract pickers `:1774-1817`, context `<select>` `:1819`, template buttons `:1832-1835`, 5 tabs `:1843-1848`, `<MappingCanvas>` `:1867-1881`, template panel `:1884-1935`). Opened from toolbar `studio.xml:137` (`openMapping`).

**Client dispatch** — `pb_formula_studio/static/src/js/formula_studio.js`: `mapTabs` `:4152-4159` (cycle/api/import/scheme/employee), `_mapPrefix` `:4162`, `openMapping` `:4264`, `setMapMode` `:4273`, `setMapContext` `:4282`, `_loadMapping` `:4289` (dispatches `${prefix}_mapping_data`), accept/reject/delete/draw/suggest/acceptAll `:4308-4356`, transform preview/save `:4359-4370`, template machinery `:4372-4416` (`mapTemplatable` = api+cycle only), employee/contract right-column picker `:4174-4262`, state keys `:187-196`.

**Server adapters** — all on `pb.formula.studio` (`pb_formula_studio/models/pb_formula_studio.py`), target config resolved by `_pick_config(config_id)` `:125`:
| adapter | data | create | delete | persists to |
|---|---|---|---|---|
| cycle | `mapping_canvas_data` :3666 | :3738 | :3760 | `hr.payroll.cycle.component.mapping` |
| api | `api_mapping_data` :3797 | :3873 | :3891 | `hr.integration.field.mapping` |
| import | `import_mapping_data` :4170 | :4233 | :4244 | `hr.formula.rule.data_source_field` |
| scheme | `scheme_mapping_data` :4256 | :4300 | :4314 | `hr.formula.scheme.assignment` |
| employee | `employee_mapping_data` :4361 | :4417 | :4440 | `hr.payslip.import.mapping` |

Also: `api_transform_preview` :3921 / `api_transform_save` :3931 (**whitelist excludes `python` — keep it that way, W12**), template list/save/apply/delete :3982-:4141 (apply is never-overwrite, returns `{applied, skipped_existing, unmatched_sources, unmatched_targets}`), `_api_active_connector` :3773 (source heuristic), right column = `config.rule_ids.filtered(column_type=='input')` :3816.

**Source fields** — `hr.integration.field.mapping.get_available_source_fields(connector_id)` (`pb_hr_payroll_formula/models/integration_field_mapping.py:409`): flattens last-20 `hr.api.data.store` payloads to dot-paths (`_flatten_source` :431, depth 6), fallback `hr.employee` fields capped 200 (:467). `source_sample_value` field exists on mappings :61. `action_auto_map` :632, `test_mappings_batch` :540.

**Cycle 1 shipped (⟲C1 — confirm from its report)**: `hr.integration.endpoint` (+ `.template`) with `data_type`, counts, `last_sync`; `endpoint_id` on `hr.integration.field.mapping`; connector cockpit endpoints strip (`pb_import_advanced`, with Sync/View-data but NO Map-fields button — this cycle adds it); Settings single-card auto-open; board feeds summary.

**Settings** — `pb_settings/static/src/js/settings_hub.js` `CATEGORIES` :108, integrations category :139 (⟲C1 openCard now forwards card.context). **Doors/tests**: `pb_integrations/tests/test_one_door.py` enumerates the agreed door list — adding the Mapping Studio door means amending it deliberately. Palette: `pb_hub/static/src/js/hub_palette_entries.js` (Integrations entry ~:189) — add a "Mapping Studio" entry alongside.

## The design (binding)

### WP-1 — `pb_mapping_studio` client action (module: pb_formula_studio)
A **full-screen cockpit**, not a dialog. New action tag `pb_mapping_studio` + `ir.actions.client` record (follow `pb_integrations/views/pb_integrations_action.xml` shape), OWL component in `pb_formula_studio/static/src/js/mapping/mapping_studio.js` (new) reusing `MappingCanvas` untouched and the existing `pb.formula.studio` RPCs. No new persistence models.

**The story bar (the WOW seam — this is the fix for "what maps to what"):** a permanent header reading left→right as a sentence:

```
[FROM]  ⬡ Zoho People  ▸ Employees feed        ══ 34 mapped ══▶   [TO]  ▦ Payobook Scale Demo — 250 columns
        vendor icon + connector picker              animated           config (scheme) picker
        endpoint picker · "200 fields · synced 3d ago"                 "250 input columns · VN · active"
```

- **Both pickers are rich dropdowns** (search box, status line per option), built flat with pbim tokens (W1), Lucide icons via the IC registry (W2). Connector options come from `hr.integration.connector` readable set; endpoint options from the connector's endpoints (⟲C1); config options = `hr.formula.config` active-first (reuse whatever config-listing RPC the studio already has — find it; else a small `mapping_pickers()` RPC on `pb.formula.studio` returning `{connectors:[{id,name,type,icon,endpoints:[{id,name,data_type,field_count,last_sync}]}], configs:[{id,name,column_count,country,state}]}`).
- The center connector is an **animated wire with an arrowhead** and the live mapped-count; direction is unmistakable. FROM column header repeats the kicker ("FROM — Zoho People · Employees"); TO header likewise. Left cards neutral surface, right cards accent-tinted — two visibly different families.
- **Changing the target config is one click on the TO picker** — the direct answer to "how do I change the payroll template in this screenshot".

**Modes** (replacing the 5 cryptic tabs) — a segmented control with plain-language labels, same adapters underneath (`_mapPrefix` dispatch preserved):
1. "System fields → Scheme" (api — DEFAULT)
2. "Spreadsheet columns → Scheme" (import; context picker = import batch, as today :4174)
3. "Employee & Contract fields" (employee)
4. "Scheme assignment" (scheme)
5. "Mid ↔ End cycle" (cycle)
Each mode swaps the FROM zone contents appropriately (import mode: batch picker instead of connector; cycle mode: mid-config picker) — the FROM/TO grammar stays constant.

**Canvas body**: left fields show `source_sample_value` (or a sample from the latest store payload) as a quiet second line — "what the data actually looks like"; right cards show column letter + label; selecting a wire shows sample-in → transform → sample-out in the existing popover. Endpoint grouping headers on the left when >1 endpoint is loaded.

**First-run guidance**: when the pair (source, target) has zero wires — a 3-step strip ("1 Pick your source · 2 Pick your scheme · 3 Draw or auto-suggest") + a hero **"Suggest mappings"** button (`action_auto_map` / `mapSuggest` path) and **"Apply vendor template"** when one matches the connector_type (list via `mapping_template_list`). Auto-suggest results arrive as `suggested` wires (dashed) with confidence chips + Accept-all ≥0.9 (existing `mapAcceptAll` semantics).

**Arrival context keys** (read from `props.action.context`, mirroring `integrations.js:69-86`): `pb_connector`, `pb_endpoint`, `pb_config`, `pb_mode`, `pb_back`. All optional; sensible defaults (most-recently-mapped connector via `_api_active_connector`, its first endpoint, the config with most mappings for it — small resolver RPC is fine).

### WP-2 — Endpoint-aware API adapter (pb_hr_payroll_formula + pb_formula_studio)
- `get_available_source_fields(connector_id, data_type=None)` (:409): filter store payloads by data_type when given (⟲C1 endpoint.data_type); keep the fallback behavior when None.
- `api_mapping_data` (:3797): accept optional `endpoint_id`; left items filtered per above; wires filtered to that endpoint's mappings (`endpoint_id` OR legacy NULL-endpoint mappings shown under an "unassigned" group so nothing vanishes); `api_mapping_create` (:3873) stamps `endpoint_id` when provided.
- Left-item payload gains `sample` (from the newest store payload value at that dot-path, if cheap — reuse `_flatten_source`'s walk; cap work, no N+1 per field).

### WP-3 — Doors (pb_settings, pb_import_advanced, pb_hub, pb_formula_studio)
1. **Settings card**: integrations category gains card 2 — `{id:"mapping", tag:"pb_mapping_studio", icon: (Lucide 'git-merge' or 'shuffle' from IC registry), label:"Mapping Studio", sub:"Wire any source — API feeds, spreadsheets — onto your payroll schemes."}`. The category now has 2 cards, so Cycle 1's single-card auto-open naturally yields the section page again — correct.
2. **Connector cockpit**: the endpoints strip (⟲C1) gains the **"Map fields"** button per endpoint → `openHub`/`doAction` tag `pb_mapping_studio`, context `{pb_connector, pb_endpoint, pb_mode:'api', pb_back:<cockpit>}`. Also a header-level "Open Mapping Studio" quiet button (connector-scoped, no endpoint).
3. **Formula Studio**: keep the overlay fully working (scheme-centric flows depend on it); add to its mapping header a quiet "Open in Mapping Studio" link carrying `{pb_config, pb_mode, pb_connector}` so users can graduate to the big surface. Do NOT rebuild the overlay header this cycle beyond that link (the shared-picker-bar idea is cut for scope — record as a possible later cycle).
4. **Command-K palette**: add a "Mapping Studio" entry next to the Integrations one in `hub_palette_entries.js`.
5. **test_one_door.py**: the door-enumeration test gets the new door added deliberately (same commit, reasoning in message).

### WP-4 — Board/ledger coherence (pb_integrations)
- The mapping ledger (`get_ledger('mapping')` / `_ledger_mapping` :259) gains an endpoint column + facet (⟲C1 if not already), so the cockpit's numbers and the studio agree.
- Connector cards: clicking the "M mappings" fragment deep-links to Mapping Studio for that connector (context as WP-3.2) — the board becomes a door to the fix, not just a count.

### Binding non-goals
- **No python-transform editing from any UI** (whitelist stays; python transforms are backend-seeded only — W12).
- No changes to mapping persistence models beyond WP-2's `endpoint_id` stamping (schema shipped in C1). No vendor catalog data (C3). No abm (C4). No removal of the studio overlay or its 5 adapters' RPC contracts — additive only. No new hexes/icons outside the IC registry (W1/W2). Existing `hr.formula.mapping.template` semantics (never-overwrite) untouched.
- Don't fix the 2 known pre-existing test failures.

## Numbered test cases
1. **Pickers RPC**: `mapping_pickers()` (or the reused equivalent) returns readable connectors with endpoints + configs with column counts; a non-integration user gets a clean AccessError or filtered-empty result (match `_readable_connectors` semantics from pb_integrations :163 — state which).
2. **Endpoint filter**: `api_mapping_data(config_id, connector_id, endpoint_id)` returns only that endpoint's fields+wires; legacy NULL-endpoint mappings appear in the "unassigned" group; `api_mapping_create` with endpoint stamps `endpoint_id`.
3. **Sample values**: left items carry `sample` where store payloads exist; absent (not crashing) when no store rows.
4. **Config switching**: two configs, same connector — mapping_data returns disjoint wire sets per config_id; creating a wire on config B doesn't leak to A.
5. **Transform round-trip** (regression): draw wire → save `divide/3600` → preview shows sample-in/out → `api_transform_save` persists; `python` type from the RPC still rejected.
6. **Template apply regression**: vendor template apply on the new surface path returns the `{applied, skipped_existing, …}` shape; never overwrites an existing wire.
7. **Door tests**: test_one_door enumeration updated + green; settings suite green (2-card category renders section page again — assert).
8. **Suites**: pb_formula_studio, pb_hr_payroll_formula, pb_integrations, pb_settings, pb_import_advanced in one scoped run, exit 0 modulo the 2 known failures.
9. **Chrome-MCP live flows** (admin, then demo user): (a) Settings → Integrations shows 2 cards; open Mapping Studio; (b) FROM picker: switch connector and endpoint — left column + counts update; (c) TO picker: switch config — right column updates, wires reload; **change-the-template is one visible click** (screenshot); (d) draw a wire on a Demo/Stub connector, attach ÷3600 transform, see live preview, delete it; (e) auto-suggest → dashed suggested wires + confidence → Accept-all ≥0.9; (f) connector cockpit endpoint → "Map fields" lands preconfigured (FROM+TO+mode preset, back chip returns to cockpit); (g) Formula Studio overlay still opens and functions; its "Open in Mapping Studio" link lands with config preset; (h) ⌘K palette entry lands; (i) demo user: read-only behavior consistent with `canEdit` (no draw/save affordances) — verify how canEdit is derived and enforce manager-gating like the overlay does; (j) zero console errors / non-warmup ≥400s; screenshots of every state incl. the story bar.
10. **The confused-user test** (the point of the cycle): cold-start walkthrough screenshotted — from Settings to a drawn, transformed, previewed mapping in ≤6 clicks, with FROM/TO legible in every frame. Count the clicks in the report.

## Deploy + verify
Same ritual as C1 §Deploy (fresh staging dir, version-diff reverse-dep closure incl. `pb_formula_studio`'s big asset bundle, detached `-u` sentinel, asset purge if OWL changes don't appear, Chrome-MCP after). `pb_formula_studio` is asset-heavy — expect the bundle rebuild; W118 rules apply in full.

## Self-review (mandatory)
Diff vs handover. Check twice: (1) the overlay's 5 adapters still work byte-for-byte at the RPC contract level; (2) no path lets `python` transforms in from the client; (3) the story bar renders correctly with a longest-realistic config name (250-column demo) and a never-synced endpoint; (4) arrival-context precedence (explicit context > defaults) can't land on a wrong config silently (cf. W76.3/W117 nonce lesson — deep links that silently land wrong are the worst bug class in this codebase).

## Commits
(1) feat(pb_formula_studio): Mapping Studio — a front door where FROM and TO read as a sentence; (2) feat(pb_hr_payroll_formula): endpoint-aware source fields + mapping data; (3) feat(pb_settings)+feat(pb_import_advanced)+feat(pb_hub): the doors (card, Map fields, palette); (4) feat(pb_integrations): ledger endpoint facet + board deep-links; (5) docs: ledger + notes. Tests WITH their feature commits.

## Report back
Per-test evidence + screenshots, click-count of test 10, commit hashes, deploy EXIT codes, the exact RPC signatures you ended with (pickers/resolver), how canEdit/manager gating is derived, deviations + reasoning, new W-rules.
