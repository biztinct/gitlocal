# JOURNEY Phase J5 — The Journey view

**Read first:** `docs/handovers/JOURNEY_LEDGER.md` (programme frame, J1–J4 outcomes, ALL MJ
gotchas), then the standing rules of `MAPFIX_LEDGER.md` (deploy ritual, MF12/MF17/MF35/MF37/MF41,
CR6/CR20) and `SOURCING_LEDGER.md`. **White-label absolute: no user-visible string may say
"Odoo".** Branch 19.1. One feature-scoped commit (explicit staging, ledger + this handover
included; leave `ABM/ABM Template.xlsx` unstaged as found). **Do not push.**

**Pre-flight (mandatory — drafted while J4 was in flight):** read J4's phase-status entry and MJ
gotchas first. J4 added the Transformations tab (`TransformFlowBoard`, a `transform_flow_data`
RPC, the shared unread-output predicates) — J5's Transformations lane MUST reuse those exact
predicates and deep-link into that tab. Re-verify every file:line below against the current tree;
take suite baselines yourself on abm (MJ11/MJ14) and note the two pre-existing red Python tests
(owner debt, not yours).

## Mission

The programme's showpiece and the owner's original ask: open Mapping and see the whole story of
where pay values come from — five lanes, live counts, problems glowing, every node a door. All
the data already exists (declared sources, lineage, conflict detection, unread-output predicates,
stored per-payslip provenance); J5 composes it into a **Journey** landing tab. The diagram is
REAL — every number on it is a count the database can defend — and it is navigation, not
decoration: clicking any node lands on the relevant tab, already scoped.

## Scope

1. **A `Journey` tab, first in the MODES strip, and the cold-start default.** Cold-start arrivals
   (Settings card, palette) land on Journey; any arrival with an explicit `pb_mode` keeps its
   mode (all existing deep links unchanged). Scheme picker as on other tabs; header sentence:
   `⟨scheme⟩ — N components · N wired · N fallback · N need attention`.
2. **Five lanes** (left → right), each node a card in the house pill/chip language:
   - **Systems** — one node per connector (status dot, last-sync age); one node for the stored
     spreadsheet file (J2's sample: filename · read date), or a "no file read yet" ghost node
     that deep-links to the Spreadsheet tab's dropzone; one **Payobook records ⇆** node
     (Employee · Contract · Bank, mapping count).
   - **Feeds & files** — per-endpoint nodes under their connector (field count, last_sync,
     "N not sent last sync" drift note where the catalogue says so); per-sheet nodes under the
     file (column counts from the stored sample JSON).
   - **Transformations** — one node per transformation rule (inputs → output key), amber when
     its output is unread (J4's predicate — same helper, not a copy).
   - **Scheme** — the component picture: wired / fallback-capable / constant / calculated /
     unfed counts (from `_declared_source`-family helpers + `binding_dangling`), plus one
     health node per problem class present: **conflicts** (J3's dual-source helper — abm's real
     dual components must appear), **dangling bindings**, **severed wires**.
   - **Pay run** — the last PROCESSED batch for this scheme, summarised from stored provenance:
     payslip count, values by source kind (feed/rule/excel/employee/contract/default), fallback
     count, plus a **records updated ⇆** note if writeback numbers are derivable. No run yet →
     an honest ghost node ("no pay run yet — the wiring above is what will happen").
3. **Wires between lanes** reflect reality: connector→endpoint containment, endpoint/sheet→scheme
   only where live wires/bindings exist (widths/counts from the mapping counts), rule→scheme per
   J4's edges, records ⇆ scheme double-headed (J3's language). The scheme's active connector is
   marked **primary — the one this scheme reads on system runs**; other connectors' lanes render
   dimmed with a tooltip saying their wires are ignored by this scheme's runs (the ledger's
   one-connector limit, made visible — runtime unchanged).
4. **Every node is a door**: `doAction`/tab-switch into the owning tab, pre-scoped
   (`pb_connector`/`pb_endpoint`/`pb_config`/`pb_mode`) and — additively — pre-filtered (e.g. a
   `pb_focus` ctx key the target tab's existing search/filter honours; wire it through the host's
   arrival reader once, not per tab).
5. **Honesty rules:** a number that cannot be defended from the DB is not shown (no invented
   percentages, no fake liveness); stale data says its age; health states reuse the existing
   vocabularies (pill + tooltip sentence, MJ-style) — no new severity system.

**Non-goals (binding):** Journey performs NO writes (read + navigate only); no resolver changes
(J-D5); no multi-connector runtime change; no animation system beyond the house transitions; no
dashboards/charts — this is a flow picture, not analytics (pb_explorer owns analytics).

## Verified plumbing (surveyed pre-J2 — re-verify per Pre-flight; J3 shifted resolver lines ~+199)

- **Declared source + labels:** `_declared_source` `pb_formula_studio.py:398`, source labels
  `:436-462`, JS mirror `source_vocab.js`; `binding_dangling` compute `formula_rule.py:204-247`.
- **Lineage:** `_lineage_by_output_key` `:474-525`, `_lineage_for_config` `:561+`.
- **Conflict detection:** J3's shared helper behind `source_conflict_probe` (find it — post-J3).
- **Unread-output predicate:** J4's shared helper (post-J4; ancestry `_rule_consumers`
  `pb_integrations.py:733-751`, `_sourcing_hints` `:649-701`).
- **Connectors/endpoints:** `hr.integration.connector` (`status`, `last_sync`), endpoints +
  per-feed `last_sync`/`last_error` (`integration_endpoint.py:119`), field catalogue + "not sent"
  drift (endpoint fields provenance, `integration_field_mapping.py:507-522` + catalogue lanes).
- **Stored spreadsheet sample (J2):** on `hr.formula.config` — file, filename, read date, columns
  JSON (post-J2 field names — read J2's entry).
- **Per-payslip provenance:** `hr.payslip.formula_input_sources` (`hr_payslip_formula.py:58-62`),
  entry shape `input_provenance.py:112-134` (`src`, `via`, adjustments). Batches:
  `hr.payroll.import.batch` (state, `source_type` now `{excel, api_data_store, manual}`),
  lines' `source_origin`. Writeback traces: check what `action_process` persists (batch
  stats/logs) — derive "records updated" ONLY from what is stored; else show the mapping-count ⇆
  note instead.
- **Active connector:** `hr.formula.config.connector_id` (`formula_config.py:302`) — the
  PRIMARY marker. Do NOT use `_api_active_connector`'s most-mappings heuristic
  (`pb_formula_studio.py:4757`) for the primary label; the config field is the truth the runtime
  uses (`payroll_import_batch` gate) and the heuristic is documented wrong on abm.
- **Host:** MODES strip + arrival reader in `mapping_studio.js/.xml` (post-J4 positions);
  geometry kernel `mapping/mapping_geometry.js`; J4's `TransformFlowBoard` is the structural
  precedent for a multi-lane thin board.

## Architecture

- **`JourneyBoard`** under `static/src/js/mapping/` — a five-lane thin board like J4's (own
  XML/SCSS in the `.pbim.pbms` language, geometry kernel for wires, pill chips, Lucide icons via
  the kit, no emoji, no gradients). `MappingCanvas` untouched.
- **One read-only RPC** `journey_data(config_id)` composing the existing helpers server-side.
  Target one round-trip; if the provenance aggregate over the last batch is heavy, aggregate in
  SQL (read-only) and note the cost in the report (the MAPFIX boards report RPC ms/KB — do the
  same).
- **Aggregation contract:** last-run lane numbers come from ONE processed batch (the latest for
  this config); aggregate `formula_input_sources` across its payslips by `src` and by
  `via`-family (wired = feed/rule/excel via binding/mapping; fallback = the fallback/
  binding_empty/employee_mapping family; default = default/constant tails). Write the mapping
  from `via` values to these three buckets ONCE, server-side, with a Python test pinning it to
  the vocabulary file — if the vocabulary gains a value later, the test must fail loudly rather
  than silently misbucket.
- **Empty-world behaviour:** every lane has a designed ghost/empty node with a door (no
  connector → Integrations; no file → Spreadsheet dropzone; no rules → Transformations "New
  rule…"; no run → the honest sentence). A scheme with nothing configured still renders a
  coherent, inviting Journey — this is the novice's first screen.
- **Keyboard/a11y:** tab-order along lanes (MJ10), Enter opens the focused node's door (MF33
  guard pattern), `/` filters nodes, Escape ladder consistent with the host.

## Safety rails

- Journey itself writes NOTHING — assert it: the MF37 diff around the entire live validation
  session (`hr_payslip_import_mapping`, `hr_integration_field_mapping`, `hr_formula_rule` config
  14, batches/lines) must be empty with no restore step needed.
- NEVER `action_process` on a live DB; no live external pulls. Provenance-aggregate tests build
  their own fixtures in the Python test env.
- MJ2 (warm server), MJ5 (SCSS math), MJ6 (version bump after late asset edits), MJ7+MJ12
  (clip/layer/SVG-aware sweeps), MJ13 (`innerWidth` after emulation), MJ19 (no Python-style
  string concatenation in JS — and don't trust a green from a checker you haven't verified).
- Screenshots to `.journey-shots/J5/`.

## Numbered test cases (abm for live UI; all pass before commit)

1. Cold-start (Settings card / palette) lands on Journey; every pre-existing deep link with an
   explicit `pb_mode` still lands on its own tab (regression-check each documented door).
2. abm, config 14: Systems lane shows both connectors with the config's `connector_id` marked
   primary and the other dimmed with the ignored-wires tooltip; the records ⇆ node shows the
   real mapping count; the file node reflects J2's stored sample (or its ghost if none stored —
   leave abm's state as found either way).
3. Feeds lane: endpoint nodes with real field counts + last-sync ages; drift notes match the
   catalogue's "not sent" data.
4. Transformations lane: rule nodes match the DB; an unread output renders amber using J4's
   predicate (assert both surfaces agree on the same rule).
5. Scheme lane: wired/fallback/constant/calculated/unfed counts each defended by a direct DB/RPC
   assertion; abm's real dual-source components produce the conflicts health node with the J3
   pill vocabulary.
6. Pay run lane: with no processed batch on abm, the honest ghost renders; the aggregate path is
   proved in Python — synthetic batch + payslips with provenance blobs → bucket counts exactly
   match the via-mapping contract (including an unknown-`via` value failing loudly).
7. Doors: clicking every node type lands on the right tab, scoped and (where specced) focused —
   one click, no picker re-selection; back chip returns to Journey.
8. Wires: endpoint/sheet→scheme edges exist only where live wires/bindings do (counts asserted
   against the DB); records ⇆ scheme edge is double-headed; dimmed-lane wires render dimmed.
9. Empty world: on a throwaway/empty config (acme or a fresh config created AND deleted with
   diff proof), all five ghost nodes render with working doors.
10. Read-only proof: the MF37 diff across the whole live session is EMPTY (no restore step) —
    Journey never wrote.
11. RPC budget: `journey_data` on abm config 14 reported as ms / KB in the report (target the
    same order as the mapping boards: ~100-150 ms; if materially heavier, say why).
12. Keyboard: lane tab-order, Enter-opens-door with the MF33 guard, `/` filter, Escape.
13. Suites: self-taken baselines, finish at-or-above with new tests on top (0 new failures; the
    two pre-existing reds noted, untouched); hoot additions translation-free (MJ3).
14. Layout + console: MJ7/MJ12 sweep at 1440 and 1024 with tooltips open; 0 overlaps; 0 console
    errors; no horizontal body scroll.
15. Grep gates: no user-visible "Odoo"; no emoji in UI strings; every new string translated.
16. Deploy per MAPFIX ritual over abm acme payobook payobook_template; `latest_version` verified
    in psql on all four.

## Report back

Versions shipped · per-case results (1–16) · suite tallies vs self-recorded baselines · the
empty MF37 diff (read-only proof) · `journey_data` ms/KB · the via→bucket mapping as shipped ·
screenshots index · deviations with reasoning · new MJ gotchas appended to `JOURNEY_LEDGER.md`
(+ phase-status entry, and flip the header STATUS line to reflect J5) · the single commit hash.
Do not push.
