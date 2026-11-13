# JOURNEY Phase J4 — The Transformations tab

**Read first:** `docs/handovers/JOURNEY_LEDGER.md` (programme frame, J1–J3 outcomes, ALL MJ
gotchas), then the standing rules of `MAPFIX_LEDGER.md` (deploy ritual, MF12/MF17/MF35/MF37/MF41,
CR6/CR20) and `SOURCING_LEDGER.md`. **White-label absolute: no user-visible string may say
"Odoo".** Branch 19.1. One feature-scoped commit (explicit staging, ledger + this handover
included; leave `ABM/ABM Template.xlsx` unstaged as found). **Do not push.**

**Pre-flight (mandatory — this handover was drafted while J3 was in flight):** read J3's
phase-status entry and MJ gotchas first. J3 touched the Mapping host's MODES list (tab renames),
added conflict-chip helpers and a `bidirectional` adapter flag, guarded the connector pre-pass for
empty feed values, and swept dead code in `payroll_import_batch.py` — re-verify every file:line
below against the current tree before editing. Take suite baselines yourself on abm (MJ11).

## Mission

Transformation rules are first-class sources — a rule's output can feed a scheme component by
binding or by wire — but the picture the owner asked for (*fields in → rule → output → component*)
exists nowhere. Transforms hide in a per-wire popover; rules are authored in a separate cockpit;
outputs nothing consumes rot silently. J4 gives transformations an address: a **Transformations
tab** in the Mapping home showing the full three-lane flow, with the Rule Composer opened in place
and an "unread output" health state.

## Scope

1. **A new `Transformations` tab** in the Mapping home's MODES list (between the API and
   Spreadsheet tabs), FROM…TO sentence: `FROM ⟨connector⟩ ══ N rules ══▶ TO ⟨scheme⟩`. Connector
   picker + scheme picker reuse the host's existing pickers; deep-link ctx (`pb_connector`,
   `pb_config`, `pb_mode:"transform"`) honoured like every other mode.
2. **The three-lane flow board.** Left lane: the feed fields each rule reads. Middle lane: one
   sealed card per `hr.api.transformation.rule` on the connector (name, plain-language summary,
   output key, state). Right lane: the scheme components its outputs feed. Wires: field → rule
   (read edges) and rule → component (feed edges — these are real `hr.integration.field.mapping`
   rows or `rule` bindings).
3. **Interactions, deliberately few:**
   - Click/⋮ on a rule card → **open the Rule Composer on that rule, in place** (the existing
     composer surface; do not rebuild authoring). "New transformation rule…" does the same empty.
   - Draw/remove a wire **only** on the rule→component side, through the EXISTING
     `api_mapping_create` / `api_mapping_delete` adapters (an output key is already a legal
     `source_field`; the boards already classify such wires as kind `rule`). Field→rule edges are
     READ-ONLY in J4 — inputs are edited in the composer, and the board says so on hover.
   - The J3 conflict dialog fires here exactly as on the API board when a wired component already
     has another live source (same helper, no second implementation).
4. **Health.** A rule whose output feeds nothing renders the amber **"unread output"** state
   (wording consistent with the Integrations cockpit's existing sourcing hints); a rule reading a
   field its connector is not known to deliver renders the existing drift warning vocabulary; a
   severed target (`is_severed`) renders the severed state. Counts surface in the tab's header
   sentence ("2 rules · 1 output unread").
5. **Lineage popovers** on rule cards reuse the existing lineage payload (summary · reads ·
   fallback · feeds · "Open rule") — one vocabulary with the chips the other boards already show.

**Non-goals (binding):** no new authoring UI (the Rule Composer IS the editor — J4 gives it an
address, not a successor); no editing of rule inputs from the board; no resolver changes of any
kind (J-D5); no Journey tab (J5); no multi-connector runtime; no changes to how rules execute
(J3 owns the per-feed execution fix). `om_hr_payroll` untouched (CR1).

## Verified plumbing (surveyed pre-J2/J3 — re-verify per Pre-flight)

- **Lineage payload (the board's data spine):** `_lineage_by_output_key`
  `pb_formula_studio.py:474-525` (`summary`, `reads`, `fallback`, `feeds` — feeds includes both
  live wires and `('rule', key)` bindings `:508-513`); `_lineage_for_config` `:561+`; rendered
  today in `mapping_canvas.xml:470-476`.
- **Rules:** `hr.api.transformation.rule` (`api_transformation_rule.py:307`), `output_key`
  contract + constraint `:882-896`, execution `_execute_for_records` `:508/:556-572` →
  `computed_data`. Output-key catalogue `_computed_output_keys`
  (`integration_field_mapping.py:507-522`); "Derived here" lane provenance `:666-672`.
- **Wires:** `hr.integration.field.mapping` — `source_field` may be an output key; draw-time
  classification `kind = 'rule' if src in _computed_output_keys(conn) else 'feed'`
  (`pb_formula_studio.py:5102`). Adapters `api_mapping_data` `:4798`, `api_mapping_create`
  `:5041` (same-connector conflict unlink `:5087-5088`), `api_mapping_delete` `:5129`.
- **Health sources:** `pb_integrations/models/pb_integrations.py` — `_rule_consumers` `:733-751`,
  `_mapping_producer` `:754-761`, `_sourcing_hints` `:649-701` (incl. "Rule outputs nothing
  reads"). Reuse the predicates (extract/share if needed); do not write a second definition of
  "unread".
- **Rule Composer:** `pb_integrations/models/rule_composer.py` (`rule_composer_data` /
  `rule_preview` / `rule_save` fail-closed / `rule_propose`), JS `pb_integrations/static/src/js/
  rule_composer.js`, XML `static/src/xml/rule_composer.xml`. It currently mounts inside the
  Integrations cockpit — opening it from the Mapping host must reuse the component, not copy it
  (check its props/service assumptions; if it needs a thin wrapper action, build that once).
- **Host:** the J1 full-screen Mapping home — MODES list + FROM…TO header + pickers in
  `mapping_studio.js/.xml` (line numbers moved in J1/J2/J3 — re-find). The two-lane
  `MappingCanvas` stays untouched; the three-lane board is a NEW sibling component (see
  Architecture). Geometry kernel `mapping/mapping_geometry.js` is pure and reusable.

## Architecture

- **A new thin board, not a canvas fork.** Build `TransformFlowBoard` under
  `static/src/js/mapping/` (own XML + SCSS in the host's `.pbim.pbms` language): three columns,
  wires via `mapping_geometry.js` (`wireGeometry`/`clampY`/`aggregateDocks` handle the geometry;
  they don't care how many columns exist). Reuse the canvas' visual vocabulary — card chrome,
  chips (`srcChip`/`provChip` classes), dashed-amber suggestion/warn styling, dock chips — via
  shared SCSS, not copied markup. `MappingCanvas` itself is NOT modified (its two-lane contract
  is load-bearing for four other tabs; MJ1's lesson).
- **One data RPC** (e.g. `transform_flow_data(config_id, connector_id)`) composed server-side
  from the existing pieces: rules + `_computed_output_keys` + lineage + field catalogue +
  consumer/producer predicates. Additive, read-only; writes go through the existing
  `api_mapping_create/delete` only.
- **Keyboard + a11y parity:** `/` search (filters all three lanes), arrows, Enter-on-button guard
  (MF33), Escape ladder, `w` wire-walk if cheap — else document the diff. MJ10: tab-order must
  match visibility.
- **Empty states:** no connector → point at Integrations; connector with no rules → "New
  transformation rule…" hero; rules but no wires → suggest drawing from an output dock.

## Safety rails

- MF37 oracle on abm around all live probes: `hr_integration_field_mapping`,
  `hr_api_transformation_rule`, `hr_formula_rule` (config 14 `source_binding*`) — diff clean at
  end; the composer must NOT be driven to save a rule on a live DB unless the test creates AND
  deletes its own throwaway rule with the diff proving restoration.
- No live external API pulls; rule execution is J3's territory — nothing here triggers it.
- MJ2 (warm server), MJ5 (SCSS math), MJ6 (version bump after late asset edits), MJ7 + MJ12
  (clip/layer/SVG-aware sweeps), MJ13 (assert `innerWidth` after viewport emulation).
- Screenshots to `.journey-shots/J4/`.

## Numbered test cases (abm for live UI; all pass before commit)

1. The Transformations tab appears in the MODES strip in position, with the FROM…TO sentence and
   both pickers working; deep-link `pb_mode:"transform"` + `pb_connector` arrives scoped.
2. abm connector with rules: every rule renders one sealed mid-card with name, summary, output
   key; left lane shows exactly the fields the rules read; right lane the components fed.
3. Wire truth: every rule→component edge on the board corresponds 1:1 to a live
   `hr.integration.field.mapping` row with that output key OR a `('rule', key)` binding — assert
   counts against the DB, not the eye.
4. Draw a rule→component wire → `api_mapping_create` writes it (classified kind `rule`);
   delete it; MF37 diff clean.
5. J3's conflict dialog fires when the target already has another live source; cancel path
   proves zero writes.
6. Rule card click opens the Rule Composer on that rule IN PLACE; saving is NOT exercised against
   a live rule (or uses a throwaway rule, restored + diffed); "New transformation rule…" opens it
   empty.
7. Health: a rule with an unconsumed output renders the amber "unread output" state and the
   header counts it; wire it → state clears without a full reload (or with one — state the
   behaviour); severed and drift states render with the existing vocabulary.
8. Field→rule edges are read-only: no gesture can create/delete them from the board; hover says
   where inputs ARE edited.
9. Empty states: connector-less, rule-less, wire-less — all three render their guidance
   (screenshots).
10. Keyboard: `/` filters all three lanes; Enter-on-button guard holds (MF33); tab-order sane
    (MJ10).
11. Python: `transform_flow_data` payload asserted (shape, counts, health flags) on abm's real
    connector; additive-only check on existing adapter payloads.
12. Suites: baselines taken first (MJ11), finish at-or-above with new tests on top — 0 failed,
    0 errors; hoot additions translation-free (MJ3).
13. Layout + console: MJ7/MJ12-style sweep at 1440 and 1024 with a popover and the composer open;
    0 overlaps, 0 console errors.
14. Grep gates: no user-visible "Odoo"; the tab and every new string audited.
15. Deploy per MAPFIX ritual over abm acme payobook payobook_template; `latest_version` verified
    in psql on all four.

## Report back

Versions shipped · per-case results (1–15) · suite tallies vs self-recorded baselines · MF37
diffs · the Rule Composer reuse mechanics as implemented (wrapper? props?) · screenshots index ·
deviations with reasoning · new MJ gotchas appended to `JOURNEY_LEDGER.md` (+ phase-status
entry) · the single commit hash. Do not push.
