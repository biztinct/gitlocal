# JOURNEY — one mapping home, the Excel on-ramp, honest two-way sourcing, the Journey view

**STATUS: COMPLETE — J1–J5 delivered and live on abm · acme · payobook · payobook_template
(2026-08-26). The Journey is the Mapping cockpit's landing tab and its cold-start default.**
**Defect round J6 (2026-08-26): four defects the owner reported against the live J4
Transformations board — one of which destroyed a live wire — repaired, fixed and live on all
four. The programme stays COMPLETE; J6 is a defect round, not a sixth scope.**

Follow-on programme to SOURCING (see `docs/handovers/SOURCING_LEDGER.md` + `SOURCING_CLOSEOUT.md`)
and MAPFIX (`docs/handovers/MAPFIX_LEDGER.md`, which itself binds COLROLES CR1–CR33). **All standing
rules and gotchas from those ledgers STILL BIND** — re-read at minimum: the deploy ritual
(MAPFIX "Standing rules", incl. `sudo -u odoo`, CR6 chmod, MF12 asset purge, MF17 `sudo -u postgres`),
CR20 websocket shutdown hang, MF37 "the oracle is the DATABASE", MF41 Chrome-MCP facts, and the
white-label absolute (no user-visible "Odoo", ever — state it in every sub-prompt).
This file adds MJ-numbered entries; append per phase.

Live databases: **abm · acme · payobook · payobook_template** on ssh alias **Payobook19v2**.
Live validation uses **abm** (payobook's role-bearing configs are company 2, invisible to apex admin).
Commit per phase, explicit staging, **do not push** (branch 19.1; SOURCING/MAPFIX commits are
part-pushed — owner decides pushes).

## The programme

Where every pay value comes from, made visible and operable in ONE place. Owner brief 2026-08-25,
validated against the code by a three-agent survey (full findings in the phase handovers; the
as-built flow: five source kinds → one resolver ladder in `payroll_import_batch.py:2633` → payslip
with provenance, plus import-time writeback into Employee/Contract/Bank).

- **J1 — One Mapping home.** Merge the two shells of the mapping board (Formula Studio overlay
  "Mapping canvas" + full-screen "Mapping Studio") into the full-screen shell, presented as
  **"Mapping"**. Port the overlay-only Employee/Contract toolkit + template save/delete. Retire the
  overlay chrome. → `JOURNEY_PHASE_J1_HANDOVER.md`
- **J2 — Excel on-ramp.** Header-discovery upload on the Spreadsheet tab (read headers, not data),
  scheme-built template download (revive the dead `ExcelConnector.generate_template`), a single
  "load this file as a pay run" handoff; consolidate the five import doors.
- **J3 — Truth & guardrails.** Two-way presentation on Employee & contract (the same mapping row
  writes records on import AND is read back when the file/feed is empty); source-conflict dialog
  (replace / keep as fallback / cancel) killing the silent connector-beats-binding trap; run
  transformation rules on per-feed pulls; close the live-payrun API TODO
  (`hr_payslip_formula.py:398-405`); delete the dead `source_type='connector'` and dead grid code.
- **J4 — Transformations tab.** fields → rule → output → component canvas over existing lineage
  RPCs; Rule Composer opened in place; "unread output" health state.
- **J5 — The Journey.** Live five-lane flow landing tab (Systems · Feeds/files · Transformations ·
  Scheme · Pay run) fed by stored provenance + lineage; every node a filtered door into its tab;
  health glow for conflicts, fallbacks, unfed components; per-system lanes make the one-connector
  limit visible.

## Owner decisions (locked 2026-08-25)

- **J-D1** Merge the two mapping shells; the **full-screen shell survives** and is renamed
  **"Mapping"** everywhere a user sees it. Formula Studio's Mapping button opens it **pre-scoped to
  the scheme being edited**. The Settings → Integrations card STAYS but opens the unified surface
  (do not delete the door; two test suites assert it).
- **J-D2** Adopt the Studio's nomenclature (FROM…TO sentence, "Spreadsheet columns → Scheme",
  "System fields → Scheme", …).
- **J-D3** The either-API-or-Excel rule is enforced by an **explicit user choice**, not silently:
  wiring a second live source onto a fed component asks replace / keep-as-fallback / cancel (J3).
- **J-D4** Employee & contract mappings are presented as genuinely **two-way** (⇆), with per-card
  plain-language direction sentences (J3).
- **J-D5** Resolver ladder order is **not** changed anywhere in this programme — precedence becomes
  visible and chosen, never reordered.
- **J-D6** Whole-programme delivery runs the phased Fable↔Opus cycle, phases back-to-back.

## Verified facts (do not re-derive — surveyed 2026-08-25 on this tree)

- Both mapping surfaces live in `pb_formula_studio` and mount the SAME `MappingCanvas`
  (`static/src/js/mapping/mapping_canvas.js`, 1656 lines; xml 507; geometry kernel
  `mapping_geometry.js`) and call the SAME server adapters in
  `pb_formula_studio/models/pb_formula_studio.py`. Overlap ~85%; neither shell is a superset.
  The non-fork rule is stated at `mapping_studio.js:24-34`.
- The five adapters/tabs: `mapTabs` `formula_studio.js:4386-4393` (overlay labels) vs
  `mapping_studio.js:54-65` (Studio labels). Overlay defaults `cycle`; Studio defaults `api`.
- Source vocabulary: 8 kinds, only `excel|feed|rule` wirable (`pb_formula_studio.py:284`); binding
  lives on `hr.formula.rule.source_binding{,_key,_origin}` (`formula_rule.py:179-271`); people
  mappings on `hr.payslip.import.mapping`; live API wires on `hr.integration.field.mapping`.
- THE resolver: `payroll_import_batch.py:2633` (`_transform_data_to_formula_inputs`). Ladder:
  0 connector-wire pre-pass (`:2902-2926`, outranks all — the loop skips codes already present
  `:2978`) → 1 explicit binding (`:3071-3102`) → 2 other-blob fallback (`:3084-3110`) → 3 name
  ladder (`:3000-3054`) → 4 mapped employee/contract field read (`:2843-2872`, `:3122-3125`) →
  5 contract component amount → 6 default/constant. Provenance via `input_provenance.py` into
  `hr.payslip.formula_input_sources`.
- WRITEBACK is real: import writes `hr.employee` (`:2131-2215`), `hr.contract` (`:2217-2241`),
  bank (`:2070-2129`), m2o auto-create (`:1310-1315`) — primary blob only, never top-up.
- Known holes (programme targets). **The first two were CLOSED by J2** — kept here with their
  original wording because the next phase's survey will meet the same lines: Excel board header
  source = existing batch only (`_import_batch_columns` `pb_formula_studio.py:5404`, free-typed
  fallback `:5504-5508` — its docstring said it had never written a value in production; J2 added
  a dropped-file lane in front of both and the docstring is now past tense); `generate_template`
  (`integrations/excel_connector.py:575`) had zero callers **and could not have survived one**
  (MJ8) — rewritten and called by `hr.formula.config._build_pay_data_template`;
  `source_type='connector'` has no loader
  (self-documented `payroll_import_batch.py:2874-2887`); per-feed pull skips transformation rules
  (`_execute_for_records` only runs from `action_pull_data` `integration_connector.py:1475` and
  `:1579`); batch-free payslips never read API data (`hr_payslip_formula.py:398-405` TODO/pass);
  one connector per scheme/batch, `_api_active_connector` heuristic (`pb_formula_studio.py:4757`)
  documented picking the wrong connector on abm (`:571-576`).

## Phase status

- **J1 — DONE, live on abm · acme · payobook · payobook_template (2026-08-25).**
  Versions: pb_formula_studio **19.0.1.131.0** · pb_settings **19.0.1.4.0** ·
  pb_hub **19.0.1.5.0** · pb_integrations **19.0.1.13.0** · pb_import_advanced **19.0.1.10.0**
  (`pb_hr_payroll_formula` and `biz_theme` untouched; `om_hr_payroll` untouched — CR1).
  **The overlay is gone.** `studio.xml` lost 297 lines (the scrim, its tab strip, its lane
  chips, its two field pickers, its template panel and the reconciliation dialog);
  `formula_studio.js` lost ~600 (every `map*`/`rcn*`/`tmpl*` method and all 19 state keys),
  and no longer imports `MappingCanvas` at all. `mapping.scss` lost its `.pbfs-map*` shell
  (169 lines) and `reclass.scss` its `.rcn` variant; the board itself
  (`.mapping-canvas`, 605 lines) is untouched, which is the point — it was never the
  problem. All eight overlay-only capabilities landed in the full-screen host: lane chips
  + filter, the "Add a field to map…" autocomplete, Employee ▾ / Contract ▾ (173 + 59 + 4
  bank = 236 on abm), remove-unwired-right, the four `⋮` verbs, the unresolved footer and
  its dialog, the payroll reveal (`employee_mapping_data`'s third argument was simply never
  passed before), and template **save + delete** with the overlay's per-line apply
  breakdown. Server adapters: **zero changes** — signatures and return shapes as found.
  Renamed to **"Mapping"** in the action record, the Settings card, the palette entry, the
  connector cockpit button, the header wordmark and the Formula Studio tool card/⌘K entry;
  every technical id (`pb_mapping_studio`, `action_pb_mapping_studio`, `openMappingStudio`)
  untouched, so `test_settings.py` and `test_one_door.py` stayed green without edits.
  Formula Studio's Mapping button is now a **pre-scoped door** (`pb_config` + `pb_mode`,
  back chip carrying `config_id`), and `pbfs_open_people_mapping` re-routes to it.
  The role vocabulary moved down to `mapping/mapping_roles.js` so the chips and the outline
  lens read ONE list.
  Tests: Python **74/74** on abm (baseline 63 + 11 new `TestOneMappingHome`), 0 failed,
  0 errors; hoot **62/62** at `/web/tests?filter=mapping_canvas` (baseline 60 + 2 new).
  15/15 numbered cases pass. 0 console errors; 0 bounding-box overlaps over 542 same-layer
  pairs at 1440 and 366 at 1024, with the chips, both pickers and an open popover on screen.
  abm left exactly as found — `hr_payslip_import_mapping` diffed byte-for-byte before and
  after (21 rows, ids `1,2,30,31,32,33,36,37,38,50…60,108`), `hr_formula_rule` for config 14
  diffed on both `source_binding*` and `column_role`/`is_contract_component` (99 rows), and
  the one promote→detach probe that DID move two rows was restored and re-diffed clean.

- **J2 — DONE, live on abm · acme · payobook · payobook_template (2026-08-25).**
  → `JOURNEY_PHASE_J2_HANDOVER.md`.
  Versions: pb_hr_payroll_formula **19.0.1.80.0** · pb_formula_studio **19.0.1.134.0** ·
  pb_import **19.0.1.3.0** · pb_import_wizard **19.0.1.1.0** ·
  pb_import_advanced **19.0.1.11.0** (`biz_theme` untouched; `om_hr_payroll` untouched — CR1).
  **The Spreadsheet board has written its first value on a live database.** S12's
  "never written a value" is now false, deliberately and provably: on abm the board
  bound `BASESALARY` (rule 674) to the key `SEVL|Base Salary`, `origin='board'`, and the
  binding was then removed to leave abm as found. Its docstring is past tense (test 13).
  **One parser, two consumers.** `action_load_file`'s branch became
  `_parse_source_file` + `_raw_data_from_row` (`payroll_import_batch.py`), and
  `peek_source_columns` runs them over an in-memory `new()` probe carrying a real
  batch's `default_get` values. So the board's keys are the loader's keys *because
  there is one function*, not because two agree. Proven live on the real fixture:
  **360 keys peeked == 360 keys loaded, 0 either way** (and the sample the board
  printed, `SEVL|Base Salary → e.g. 19,510,000`, is the value the import line holds).
  abm's config 14 takes the MULTISHEET branch (all 99 rules carry `source_sheet_name`
  = `SEVL`), so the invariant was exercised on the harder path, not the easy one.
  **The template generator is alive and has callers.** `generate_template` was
  rewritten in place (one generator, `excel_connector.py:575`): one column per INPUT
  component headed by `template_slot_for` (the binding key when there is one, else the
  name — what the resolver actually matches), the employee-identifier column FIRST on
  every sheet, one sheet per `source_sheet_name`, and **no data row at all**. Round trip
  on live config 14: **54/54 input components matched, 0 missing**.
  **One door.** `hr.payroll.import.batch.action_open_guided_import` is the single
  router; the scheme stat button, the connector stat button, the "New Import" menu (now
  a server action, `action_payroll_load_pay_data`) and the connector cockpit all return
  it, and `pb_import_wizard` now reads `default_formula_config_id` /
  `default_connector_id` / `default_source_type` off the arrival context so a
  pre-scoped door stays pre-scoped (verified live: scheme door → `pb_import_wizard`
  with config 14 selected; connector door → connector 1). Nothing was deleted — the raw
  batch form survives as "Pay Data Load (advanced form)" and is nobody's destination.
  Labels: menu `Payroll Import`→**Pay Data**, `Import Batches`→**Past Pay Data Loads**,
  `New Import`→**Load Pay Data…**, both `Payroll Import` stat buttons→**Load pay data**,
  and the structure door `Import from Excel`→**Set up columns from Excel** (behaviour
  untouched — it defines columns, it does not load numbers).
  Tests: Python **95/95 on abm**, 0 failed, 0 errors (**baseline 76** — see MJ11, the
  ledger's J1 figure of 74 was stale — plus 19 new `TestExcelOnRamp`); hoot **64**
  at `/web/tests?filter=mapping_canvas` (baseline 62 + 2). 14/14 numbered cases pass.
  0 console errors; **0 bounding-box overlaps** over 496 same-layer pairs at 1440 and
  351 at 1024, with the empty dropzone, a filled lane, a live wire and an open picker
  layer on screen.
  abm left exactly as found — `hr_payslip_import_mapping` 21 rows, ids
  `1,2,30,31,32,33,36,37,38,50…60,108`; `hr_formula_rule` config 14 back to its
  opening fingerprint `b63d9ac9cfc25d970aac346931de3779` (99 rules, 0 bound);
  `hr_payroll_import_batch` and `hr_payroll_import_line` back to **0**; 3 employees,
  0 payslips, unchanged. `action_process` was never called.

- **J3 — DONE, live on abm · acme · payobook · payobook_template (2026-08-25).**
  → `JOURNEY_PHASE_J3_HANDOVER.md`.
  Versions: pb_hr_payroll_formula **19.0.1.81.0** · pb_formula_studio **19.0.1.136.0** ·
  pb_import **19.0.1.4.0** · pb_import_wizard **19.0.1.2.0** (`biz_theme` untouched;
  `om_hr_payroll` untouched — CR1).
  **The board now says what the row does, and the guardrail asks before it writes.**
  S1: the tab is **`Employee & contract ⇆`**, its 18 wires render with a head at BOTH
  ends (`wireGeometry(..., bidi)` — opt-in, defaulted off, so the four other boards
  are byte-identical), and every mapped card carries the sentence its row actually
  performs: `⇆ On import: fills Employee › Employee Id. On pay run: used when the
  file or feed leaves this empty.` for a `field` row, and `→ On import: builds the
  bank account.` — **the import half only** — for a `bank_account` row, because
  `get_mapped_input_value` reads employee/contract fields back and never bank parts.
  `bidirectional` is read off the PAYLOAD, not off the mode id.
  S2: drawing a second live source now opens a three-way dialog (replace /
  keep-as-fallback / cancel) whose every sentence comes from the server, beside the
  ladder it describes. **Cancel makes no writing RPC at all** — `source_conflict_probe`
  is a separate read-only adapter, so there is nothing to roll back. Conflict chips
  (`Wired twice` / `Feed wins` / `Spreadsheet fallback`, full sentence in the tooltip)
  render on BOTH boards from ONE detector, including for state that predates the
  guardrail: abm's seven real dual-connector components wear them on load.
  **S2's empty-feed guard is the load-bearing half** — see below.
  S3: `action_pull_endpoint` runs the transformation rules, via a
  `_run_transformation_rules` helper that is now the ONLY `_execute_for_records` call
  site in the module. S4: the live-payrun `TODO … pass` is closed — a batch-free
  payslip reads the employee's data-store rows through the SAME `_feed_values_for`
  the import pre-pass uses, with `via='connector_mapping'` (no new vocabulary needed).
  S5: `source_type='connector'` is gone from the selection, both resolver gates, the
  form gate, the search filter, `pb_import`'s label map and `pb_import_wizard`'s source
  list (where a user could pick it and get a batch nothing could load);
  `excel_grid_widget.js` deleted.
  **The empty-feed guard, exactly (J-D5 holds).** BEFORE: the pre-pass did
  `raw_data.get(source_field)` then `if source_value is not None`. An ABSENT key
  already fell through; a key PRESENT AND EMPTY did not — it ran the transform,
  assigned `input_values[code]`, and the loop's `if rule.code not in input_values`
  skip then locked out every rung below (binding, cross-blob top-up, name ladder,
  mapped employee field, contract amount). NOW: `_feed_values_for` returns only wires
  that DELIVERED — key present, transform run, result non-empty by the resolver's own
  test — so a wire with nothing to say does not assign and the rungs below run exactly
  as on an Excel run. **This is not a reorder:** when the pre-pass HAS a value it still
  outranks everything including an explicit binding (`test_02a`, the neutrality proof),
  and `test_02f` is a source gate asserting pre-pass < loop < bound-branch order is
  unchanged. What changed is only what counts as *having a value* — and it changed to
  the definition the bound branch has always used. Without it, J-D3's "keep as
  fallback" was unimplementable: the fallback could never fire.
  Tests: Python **246 on abm, 1 failed + 1 error — both PRE-EXISTING and neither
  J3's** (`TestBankDestinations.test_09_make_text_component`,
  `TestEndpointFieldCatalogue.test_05c_...`; see MJ14 — the J2 ledger figure of 95 was
  a different `-u` SCOPE, and the true pre-J3 baseline measured on the machine was
  **202 with the same two red**). +44 new (`TestJourneyTruth` 25, `TestJourneyGuardrails`
  19). hoot **68/68 green in 24s** at `?filter=mapping_canvas` (baseline 64 + 4), after
  a cold-server run showed 63/5 — **MJ2, verbatim, a third time**. All three batteries
  RUN and pass (MF7): provenance green, excel_semantics 78/78, import_resolution 23/23.
  15/15 numbered cases pass. 0 console errors; **0 bounding-box overlaps** over 3421
  same-layer pairs at 1440 and 1032 at 1024, with the conflict dialog open, chips
  visible and no horizontal body scroll.
  Migration `19.0.1.81.0/post-a_source_nothing_could_load.py`: **0 rows converted on
  all four** (abm 0 batches, acme 0, payobook 6 — all `excel`, payobook_template 0).
  abm left exactly as found — `hr_payslip_import_mapping` 21 rows, ids
  `1,2,30,31,32,33,36,37,38,50…60,108`; `hr_formula_rule` config 14 fingerprint
  `b892dfa2f03801824f0cf0d3d639cb12` (99 rules); `hr_integration_field_mapping` 59 rows,
  fingerprint `f6876d63475c17a1f7e4e8d78e66ddfb`; 0 batches, 0 lines, 3 employees,
  0 payslips. The cancel-path probe diffed EMPTY; the one keep-as-fallback probe that
  DID move a row (rule 581 gained an `excel` binding, both its wires intact) was
  restored and re-diffed clean. `action_process` was never called.

- **J4 — DONE, live on abm · acme · payobook · payobook_template (2026-08-26).**
  → `JOURNEY_PHASE_J4_HANDOVER.md`.
  Versions: pb_formula_studio **19.0.1.139.0** (`pb_hr_payroll_formula`, `pb_integrations`,
  `biz_theme` untouched; `om_hr_payroll` untouched — CR1).
  **Transformations have an address.** A sixth tab sits between the API and
  Spreadsheet tabs and renders the whole sentence at once: on abm's connector 3,
  **6 feed fields → 8 sealed rule cards → 99 scheme components**, with 21 dashed
  read edges and 8 solid feed wires. The header says
  `FROM Zoho People (ABM) · 8 rules · 1 reads a field not seen ══ 8 rules ══▶
  TO AB Mauri Payroll`.
  **A new thin board, and the kernel finally earned its extraction.**
  `TransformFlowBoard` (JS 500 lines, its own XML + SCSS) is a SIBLING of
  `MappingCanvas`, not a mode of it — the canvas' two-lane contract carries five
  tabs, four of which have nothing to do with rules, and a middle lane none of
  them can render would have arrived on all of them at once. `MappingCanvas` has
  **zero changes this phase.** The geometry is `mapping_geometry.js` unforked:
  `wireGeometry`, `clampY`, `aggregateDocks`, `spreadHubs` and `itemMatches` are
  arithmetic over points and do not care how many columns exist, which is why
  they were extracted two cycles ago — J4 is the first phase to collect on it.
  **One RPC, composed from what already existed.** `transform_flow_data` defines
  nothing new. In particular it does NOT define "unread": that predicate is
  `pb.integrations._rule_consumers`, beside the cockpit hint that first said it
  out loud, and it is CALLED (`_tf_consumers`). The test asserts the two AGREE ON
  A FIXTURE rather than grepping for the method name — a second definition would
  pass a grep and fail that. The right lane is `_mc_right_column(board='api')`,
  the same cards/chips/sealing/lineage/conflict pills the API board renders.
  **No new write path.** An output key is already a legal `source_field`, so
  `prefix` maps `transform → "api"` and the board draws through
  `api_mapping_create` and cuts through `api_mapping_delete`. J3's conflict
  dialog therefore fires here because it fires for `api`, not because a second
  implementation remembered to — proven live on `EMPLOYEECODE`, cancel diffed
  EMPTY. A drawn wire binds `rule/WORKEDHRS/board`, i.e. classifies as kind
  `rule`; a plain feed field on the same adapter still binds `feed`.
  **Field → rule edges are READ-ONLY**, and the board says so three ways: the
  cursor (`cursor: default`), the lane note ("Read-only — edited in the rule")
  and the hover sentence. They are `consumed_field_paths`, a DERIVED fact — there
  is no row a drag could write, so no gesture is offered that would have to fail.
  **The Rule Composer is opened, not rebuilt** — see the reuse note below.
  Tests: Python **334 on abm, 2 failed + 1 error — all three PRE-EXISTING and
  none J4's** (baseline measured on the machine before starting: **295 with the
  same three**, `-u pb_hr_payroll_formula,pb_formula_studio,pb_integrations`; see
  MJ20 for the third). +39 new (`TestJourneyTransformations` 37, +2 into
  `TestOneMappingHome`). hoot **+14** J4 tests at `?filter=mapping_canvas`.
  15/15 numbered cases pass. 0 console errors; **0 bounding-box overlaps** over
  **5106** same-layer pairs at 1440 and **2541** at 1024, with a lineage popover
  open and no horizontal body scroll.
  abm left exactly as found — `hr_integration_field_mapping` back to its opening
  fingerprint `a62e14bdfb100f20989d0281345e7717` (59 rows),
  `hr_api_transformation_rule` `4de854155fd5e2f6ba49260134b55567` (8),
  `hr_formula_rule` config 14 `4330c9f9d2c06db7be267ef0cad10a90` (99),
  `hr_payslip_import_mapping` 21 rows ids `1,2,30…108`, 0 batches, 0 payslips.
  The delete→redraw probe DID move rows (mapping 36 deleted, recreated as 3207;
  component 584 gained a `rule` binding it never had) and was restored to id 36
  with its original `endpoint_id`/timestamps and a cleared binding, then
  re-diffed clean. `action_process` was never called; no live API pull was made.
  Owner debt: the admin password on abm was reset to log in at all (CR33's
  family) — it is now `J4validate!2026`.

- **J5 — DONE, live on abm · acme · payobook · payobook_template (2026-08-26).**
  → `JOURNEY_PHASE_J5_HANDOVER.md`.
  Versions: pb_formula_studio **19.0.1.146.0** (`pb_hr_payroll_formula`, `pb_integrations`,
  `biz_theme` untouched; `om_hr_payroll` untouched — CR1).
  **The programme's question now has one screen that answers it.** A seventh tab
  sits FIRST in the strip and is the cold-start default, and on abm it renders
  the whole sentence at once: `AB Mauri Payroll — 99 components · 26 wired ·
  18 fallback · 8 need attention`, over five lanes holding 30 nodes and 34
  edges (2 connectors · 14 feeds · 8 rules · the scheme + 2 health nodes · the
  pay-run ghost).
  **Every number is defended from the database, and the sum is the proof.**
  99 = 26 wired + 36 calculated + 9 fixed + 19 contract + 6 record + 3 unfed,
  checked against SQL: `wired` 26 is `count(distinct target_rule_id)` on the
  field mappings (abm has ZERO non-empty bindings, so all 26 come from S6's
  tier-3 wires), `fallback` 18 is the non-bank people-mapping components, and
  the scheme lane's bar is a tally of six disjoint named counts rather than a
  score. The `_declared_source` family, `_source_conflicts` (J3) and
  `_tf_consumers` (J4, i.e. `pb.integrations._rule_consumers`) are CALLED, not
  re-implemented — the tests assert agreement on a fixture, which a second
  implementation would fail and a grep would not.
  **The tab's best sentence is one nobody had asked for.** `config.connector_id`
  is unset on every scheme on all four databases (S20), and the resolver's
  pre-pass is gated on exactly that field — so abm's **33 drawn feed wires are
  inert** and always have been. The Journey says so: both connectors dim, each
  carries a `Not read` chip explaining why, and the scheme lane raises
  `33 feed wires are not read · This scheme names no connection, and a pay run
  only reads the one it is set to.` The one-connector limit made visible (scope
  3) had to include the case where the limit has never been exercised.
  **A fourth bucket, deliberately.** The via→bucket contract is
  `_JOURNEY_VIA_BUCKETS`, written once server-side and pinned SET-WISE against
  `input_provenance.VIAS` in both directions. It ships FOUR families, not the
  handover's three: `proration`/`retro`/`carryover` appear as a `via` only when
  the adjustment INVENTED the code, and such a value carries `src='calculated'`
  — it was not wired, did not fall back and is not a default, so it gets
  `computed`. A fourth honest column costs less than a wrong one.
  **"Records updated" is not shown, because nothing stores it.** `action_process`
  calls `_update_employee_from_raw_data`, `_sync_employee_bank_account`,
  `_update_contract_from_raw_data` and `_sync_contract_components` per line and
  counts none of them; the batch stores only `created_*_ids`. So the run lane
  shows what was CREATED plus the mapping-count ⇆ note, exactly as the handover
  specified for the else-branch. Owner debt, recorded, not invented.
  **`MappingCanvas` gained ONE additive command kind and nothing else.** `search`
  rides the existing token-guarded one-shot channel (`pulse`, `suggested`,
  `armLeft`), so the canvas' props contract is byte-identical and the four other
  boards are untouched.
  Tests: Python **373 on abm, 2 failed + 1 error — all three PRE-EXISTING and
  none J5's** (baseline taken on the machine before a line was written:
  **334 with the same three**, `-u pb_hr_payroll_formula,pb_formula_studio,pb_integrations`).
  +39 new (`TestJourneyView`). hoot **98** at `?filter=mapping_canvas`, 0 failed
  (baseline 82 + 16). 16/16 numbered cases pass. 0 console errors on a clean
  load; **0 bounding-box overlaps** over **21298** same-layer pairs at 1440 and
  **13514** at 1024, with a chip layer on screen and no horizontal body scroll.
  `journey_data` on abm config 14: **166 ms / 11.3 KB**, one round trip.
  **The read-only proof: the MF37 diff across the ENTIRE live session is EMPTY,
  with no restore step** — `hr_payslip_import_mapping` 21 rows ids
  `1,2,30…108`, `hr_integration_field_mapping` 59, `hr_formula_rule` config 14
  99, `hr_api_transformation_rule` 8, 0 batches, 0 lines, 0 payslips, 3
  employees, all fingerprints byte-identical before and after. Two throwaway
  configs were created AND deleted (abm 3001 and 3254; config count 1→1 both
  times) and the empty world was exercised on acme in a rolled-back shell
  (0 configs → 0). `action_process` was never called; no live API pull was made.
  Owner debt: the abm admin password had to be reset again to log in (CR33's
  family) — the login is **`ash@biztinct.com`**, not `admin`, and the password
  is now **`J5validate!2026`**; acme's `lan@acme.com` was set to the same and
  **still lacks the Formula Engine groups**, which is why acme's Journey was
  proven by payload rather than on screen.

- **J6 — DONE, live on abm · acme · payobook · payobook_template (2026-08-26).**
  → `JOURNEY_PHASE_J6_HANDOVER.md`.
  Version: pb_formula_studio **19.0.1.149.0** (`pb_hr_payroll_formula`, `pb_integrations`,
  `biz_theme` untouched; `om_hr_payroll` untouched — CR1).
  **A defect round that began by putting a row back.** The owner double-clicked the
  `OTHRS300` wire on the live board and it was deleted: `hr.integration.field.mapping`
  **39**, "Overtime 300% hours → OT 3 Hours". D0 recreated it through the ORM as
  **8551** with its original business fields, recovered from
  `tools/abm_seed_integrations.py:113-115` — the seed that minted it — so the label
  reads "Overtime 300% hours" and the notes still cite
  `hr_zoho_staging.py:522-530`, rather than the `Othrs300` a redraw would have
  produced. Every computed field landed on its sibling's pattern unaided
  (`BA`, `OT3HOURS`, decimals 2, sequence 10). **No binding was restored, deliberately:**
  abm has ZERO non-empty `source_binding`s (J5's recorded state), so component 609 had
  none to lose and writing one would have invented a decision nobody made.
  **The 19-row scare, and what settled it.** The table read **40** rows against J5's
  recorded **59** — nineteen missing, not one. The log named all of them:
  `odoo.models.unlink` shows User #2 deleting ids 109-126 one at a time between
  23:53 and 23:56 and then archiving connector 1 ("Zoho People") at 23:59:50 — the
  owner tidying a legacy connection on purpose — and then, separately, **id 39 at
  00:03:32**, the last deletion on the table. 59 − 18 − 1 = 40 reconciles exactly.
  Only the accident was repaired; the housekeeping was left alone. (MJ35.)
  **D1's root cause was one number: 49.75.** The board measured its geometry against
  `.tfb` — the whole tab, search bar included — and painted it into `.tfb-wires`,
  which is `inset: 0` of `.tfb-board`, one search bar lower. Every wire was drawn
  exactly the bar's height too low, measured live on abm at **49.75px**. Both owner
  screenshots are that one fact: a wire whose target is on screen misses its port by
  50px (sloppy, not obviously broken), and a wire whose target is scrolled away is
  clamped to a band that is shifted with it, so the "edge" it parks on is 49.75px
  INSIDE the lane and lands on whatever card sits there — which is how solid wires
  came to appear to feed "Actual Parking" and "Actual Taxi allowance", two sealed
  Calculated components no rule feeds. Proven before the fix (wires w41/w42, the two
  unclamped ones, measured `+49.8`) and after (**maxErr 0** at 1440 and 1024).
  `.tfb-board` is now the origin for the wires, the dock chips and the wire verb; the
  MENU still measures against the root, because it is a sibling outside the clip.
  A parked end also lost its **arrowhead** (`dockend`): an arrowhead is the symbol for
  "it ends here", and the honest reading of a clamped wire is "it runs off this way,
  and the chip beside it says how many".
  **D2** double-click centres both ends of either wire family, reusing the canvas'
  sentence ("Clear the filter and show me") rather than a second reveal mechanism;
  read edges gained a hit area for that ONE gesture and stayed uneditable
  (`cursor: default`, no selection, no verb).
  **D3** double-click is never destructive, and the mechanism was geometric: the
  Remove pill rendered at the hub point — the Bézier MIDPOINT — so selecting a wire
  put a delete button under the cursor that had just selected it, and the second click
  of a double-click pressed it. `VERB_DY = 34` lifts it clear (measured live: **19px**
  above the click point, with the wire's own hit path still the element under that
  point), flipping below when the top of the board is in the way. Every delete on the
  Transformations AND the `System fields → Scheme` boards now goes through ONE helper,
  `MappingStudio._removeWireUndoable`, and raises a **"Wire removed — Undo"** toast
  whose lifetime IS the undo window (`UNDO_MS = 10000`, not sticky — a safety net,
  not an undo system).
  **The undo is the delete's inverse, not a second draw.** `api_mapping_restore` does
  NOT route through `api_mapping_create`, because a create DRAWS: it re-derives the
  label, discovers a fresh sample, unlinks rivals and writes a binding. Proven live on
  the API board — cutting `Employeestatus` (id 19) and undoing gave back a row whose
  `source_field_label` is still **"Employment status"**; a redraw would have written
  "Employeestatus". The binding is restored with its ORIGIN intact
  (`rule|OTHRS150|board`, verified live).
  **D4 was discoverability, not a regression** — the arming path worked the whole
  time. It was a 22px icon-only button carrying the board's only write gesture, on a
  card whose entire body opens the Rule Composer, and `armOutput` already stopped the
  event. The output ROW is now the button: key, sentence and glyph, always visible,
  "Wire this output to a component…". Mouse-only creation verified end to end on the
  live board (armed banner = the canvas' sentence, 99 targets lit, composer stayed
  shut, wire written), plus a keyboard path (`keyComponent`) whose targets are
  tabbable only while something is armed.
  Tests: Python **420 on abm, 2 failed + 1 error — all three PRE-EXISTING and none
  J6's** (baseline taken on the machine first: **373 with the same three**,
  `-u pb_hr_payroll_formula,pb_formula_studio,pb_integrations`,
  `--test-tags /pb_hr_payroll_formula,/pb_formula_studio,/pb_integrations`). +47 new
  (`TestJourneyJ6Defects`). hoot **113**, 0 failed (baseline 98 + 15 J6).
  14/14 numbered cases pass. **0 bounding-box overlaps** at 1440 and 1024 over 144
  same-layer pairs each, in the filtered-with-chips state the sweep had never
  covered — which is where it caught a defect of its own (MJ33).
  **The MF37 diff is EMPTY against the post-repair state**, with the ids restored
  (J4's precedent): `hr_integration_field_mapping` 41 rows,
  `478c051b85e20e4d0e1c832376d3e0ed`; `hr_api_transformation_rule` 8,
  `e0b1b917e424db79a66f2a731813232d`; `hr_formula_rule` config 14 99 rows, **0**
  non-empty bindings, `a922a60cab34e716d37cb7ad4ccdc427`. Row 37 was rebuilt column
  for column against the dump taken before any probe. `action_process` was never
  called; no live API pull was made.

## Gotchas discovered (append per phase, MJ-numbered)

- MJ1 (J1): **`groupFilter` filters the LEFT column only, and always did.** The handover's
  test 5 asked that a lane chip "filters both columns"; the shared canvas' prop is
  documented at `mapping_canvas.js:61-66` as "a PARENT-OWNED display filter over the LEFT
  column's `group` key", and `_passes` only consults it for `side === "left"`
  (`:589`, `:615`). The overlay behaved identically, so parity is met and the phrase
  described an intent the component never had. Filtering the right column too would mean
  filtering the 236-card DESTINATION catalogue by a SOURCE column's role, which is not a
  narrowing anybody asked for — and it is a redesign of the board, a binding non-goal.
  Left as-is deliberately; if J3+ wants it, it is a canvas change with its own tests.
- MJ2 (J1, testing): **eight hoot tests "failed" and the cause was a COLD SERVER — the
  first three diagnoses were all wrong, including a tidy one that survived an experiment.**
  Every `mountWithCleanup` test in `mapping_canvas.test.js` timed out at 5000ms with
  "1 unverified error", 60/60 → 58/8. The names are all canvas behaviours (scroll
  coalescing, provenance chips, drift sentences), so it reads as a canvas regression from
  the phase that had just touched mapping code. The trail:
  (1) blamed the new `mapping_studio.js` import in the test file — plausible, since it
  drags `@pb_hub/js/hub_nav` and `@pb_import_kit/js/import_icons` into the bundle;
  (2) **tested it** by deploying the pristine pre-J1 test file: 60/60 green. That looked
  like proof, and it was not — the pristine run happened on a server that had been up 3h40m;
  (3) removed the import anyway, redeployed after a RESTART: **still 8 failures.** Same
  eight, no host import. What actually differed was the clock: the failing runs took 31-44s
  and the green ones 8-12s, with individual passing tests at 409ms where they are normally
  113ms. The server was compiling asset bundles at 64% CPU behind the suite. Waiting for
  load average to fall gave **62/62 in 12s**, unchanged code.
  Lessons, in order of how much they cost: a hoot timeout is a measurement of the SERVER,
  not only of the code; "I changed X and Y broke" plus "I reverted X and Y healed" is still
  not causation when an uncontrolled variable (uptime) moved between the two runs; and
  **re-run a red suite on a warm server before you believe it.**
  The import was removed regardless and the file now says why — this suite tests the CANVAS
  and the pure kernel, never a host; host invariants live in `test_one_mapping_home.py`,
  where they are source assertions and cannot be perturbed by bundle mechanics or load.
- MJ3 (J1, testing): **a module-scope `_t()` cannot be stringified in hoot.**
  `MODES[].label` is built with `_t()` at module scope; `String(label)` inside a hoot test
  throws "Cannot translate string: translations have not been loaded", because the runner
  never loads them. Two of the first-cut J1 tests failed on this alone. Assert
  user-visible label TEXT from Python (against the source) and keep hoot to
  translation-free facts — ids, ordering, icons, geometry.
- MJ4 (J1, testing): **`Object.getOwnPropertyDescriptor(C.prototype, g).get.call({state})`
  only works for a getter that reads nothing but `state`.** `empLaneFilter` delegates to
  `this.isEmp`, another prototype getter, which a bare object does not have — so it
  returned `""` for an employee-mode fixture and the test failed against correct code. If a
  getter composes other getters, either build the fixture with
  `Object.create(C.prototype)` or assert it live; do not hand-roll a `this`.
- MJ5 (J1, environment): **libsass rejects `min(<len>, calc(…))`.** `width: min(780px,
  calc(100vw - 48px))` compiled as SASS' own numeric `min()` and failed the WHOLE backend
  bundle — `Error: "calc(100vw - 48px)" is not a number for 'min'` — which serves the
  previous stylesheet under a red "A css error occured" banner, i.e. every screen on the
  database looks broken, not just this one. Two properties (`width` + `max-width`) say the
  same thing and cannot be mistaken for a Sass call. Check the server log for
  `assetsbundle: Error` after any new CSS math.
- MJ6 (J1, environment): **an asset-bundle URL hash can stay the same while the content
  changes, and then the BROWSER cache is the culprit after all** — the one case MF12's
  "the browser cache is never the culprit; the attachment is" does not cover. After a late
  edit to `static/tests/**`, `ir_attachment` held zero `/web/assets/%` rows (Odoo 19
  regenerates on request), `curl` of the bundle URL returned the NEW content, and the page
  loading that same URL kept running the OLD 60 tests — including through
  `navigate(ignoreCache: true)`. The fix is MF12's other half: bump the module version and
  re-`-u`, which mints a new hash and therefore a new URL.
- MJ7 (J1, testing): **a bounding-box sweep must know about `overflow: clip` and about
  popovers, or it invents defects.** `.mc-board` clips its columns, so a card scrolled past
  the bottom still reports a rect 36px inside the footer — one "overlap" that
  `document.elementFromPoint` disproves at every probe (the footer answers, never the
  card). And a dropdown is SUPPOSED to cover the chips beneath it. The sweep now compares
  each card's rect intersected with the clip box, and only tests pairs sharing a layer:
  0 overlaps at 1440 and at 1024. A layout assertion that cannot tell "covered on purpose"
  from "collided" will fail every honest popover you ever ship.

- MJ8 (J2): **the dead template generator was not merely uncalled — it was
  UNCALLABLE, and the two facts look identical in `grep`.** `ExcelConnector.generate_template`
  had zero callers for its whole life (the J2 handover's premise). What the handover could
  not know, and what no amount of reading the call graph reveals, is that its body read
  `rule.description` — and `hr.formula.rule` has no `description` field. The first call it
  ever received, in a test, died with `'hr.formula.rule' object has no attribute
  'description'`. So "revive the dead generator" was never a matter of adding a caller;
  the code had never executed once, and the same is true of everything else it asserted
  about rules. **Dead code does not rot — it was frequently born wrong, and the absence of
  callers is exactly what let it stay that way.** When a phase plans to revive something
  with no callers, budget for it being broken rather than stale, and give it a test before
  giving it a button. (Two more of its assumptions were wrong in the same way: component
  CODES are not what the resolver tries first, and a multisheet scheme's columns do not
  live on one sheet. The rewrite fixed all three.)
- MJ9 (J2): **a workbook with headings and no rows had no SHAPE, and the feature that
  needed it most was the one this phase shipped.** `_load_multisheet_data` derives its
  `headers` from the merged data rows, so a template — headings only, deliberately empty
  (a pre-filled row is a row somebody imports by accident) — parsed to `headers=[]`,
  `rows=[]`, and the header reader found nothing. The round trip that is the entire point
  of a scheme-built template could not close. The fix had to preserve the one-parser rule,
  so it does NOT reimplement the key shape: it seeds a single phantom row keyed on
  `_SHAPE_PROBE`, runs it through the identical merge, and drops it before returning
  (`shape_only`). `rows` stays empty, so `action_load_file` still refuses the file with
  "No data found" and loading is bit-identical; only `headers` — which the loader uses for
  a log line and, on dict rows, for nothing at all — gains the truth it always should have
  had. **When you need a derived value that only exists on the data path, put a fake datum
  through the real path rather than a real datum through a fake one.**
- MJ10 (J2, testing): **the keyboard found the only defect the screenshots could not.**
  A `<label>`-wrapped `input[type=file]` is how every file picker in this codebase is
  styled, and the input is 1px and transparent by necessity. `.pbms-drop` had
  `:focus-within`; `.pbms-ramp__swap` ("Replace file…") did not — so tabbing onto it gave
  `boxShadow: "none"` and no ring anywhere on screen. The control was **reachable and
  invisible**, which is worse than unreachable: the next Enter opens a file dialog the
  user did not know they were on. Nothing in a mouse-driven session shows this, and a
  bounding-box sweep cannot: the geometry is perfect. Probe every custom affordance with
  `el.focus()` + `getComputedStyle`, not just with a click. (MF26's family: an affordance
  that is not a `<button>` has to re-earn every `<button>` behaviour, one at a time.)
- MJ11 (J2, testing): **a recorded suite baseline goes stale the moment the tree moves,
  and a phase that trusts the ledger's number reads a pass as a regression.** The J2
  handover said abm's Python baseline was 74 (J1's report, and true when written). The
  last pre-J2 run on abm was **76** — commit `1fb21315` had landed two more tests after
  J1 reported. Had J2 finished at 93 it would have looked like +19 on 74 and green, while
  actually having lost two. **Take the baseline yourself, on the machine, immediately
  before you start** — the ledger figure is a claim about a past tree, not a measurement
  of this one. (Read it out of the log: `grep "odoo.tests.result" /var/log/odoo/odoo-server.log`
  carries every historical run with its timestamp, which is how the drift was spotted.)
- MJ12 (J2, testing): **a bounding-box sweep must exclude SVG internals, or the icons
  fail it.** MJ7 taught the sweep about `overflow: clip` and layers; the first J2 run still
  reported 5 "overlaps", every one of them a `<path>` inside a Lucide glyph overlapping its
  sibling `<path>` — which is what a drawing IS. They are unmistakable in the output only
  because `String(el.className)` on an SVG node yields `[object SVGAnimatedString]`, so the
  offenders had no names. `.filter(e => !(e instanceof SVGElement))` took it to 0 at both
  widths. Same lesson a third time: **a layout assertion that does not know what it is
  measuring invents defects, and an invented defect costs the same as a real one until you
  have disproved it.**
- MJ13 (J2, environment): **Chrome-MCP's viewport emulation can enter a state where every
  resize silently no-ops.** After a `resize_page` to 1024 that reported success but left
  `innerWidth` at 1440, subsequent calls returned `Emulating viewport: {…,"width":null}`
  and `emulate` failed with `Failed to deserialize params.width`. The page was fine; the
  emulation override was corrupt. **Opening a NEW page re-establishes it** — the 1024
  sweep ran on a fresh tab. Always assert the width you asked for
  (`() => ({w: innerWidth})`) before trusting a responsive check; a screenshot at the
  wrong width is a screenshot of a layout you did not test. (MF41's family.)
- MJ14 (J3, testing): **a suite baseline is a measurement of a SCOPE, not of a tree — and
  J2's "95" and J3's "202" are both true.** MJ11 said to take the baseline yourself because
  the tree moves. It moves less than the COMMAND does. `--test-tags /module` runs the tests
  of modules the same run is UPGRADING, so J2's `-u pb_formula_studio` reported
  `0 failed of 95` and J3's `-u pb_hr_payroll_formula,pb_formula_studio` reported
  `1 failed, 1 error of 202` on the identical commit, minutes apart. The 107 extra tests are
  `pb_hr_payroll_formula`'s, which J1 and J2 never ran — and two of them have been red for
  some time (`TestBankDestinations.test_09_make_text_component`, a `KeyError: 'wirable'` from
  SOURCING S6's one-pill rewrite, and
  `TestEndpointFieldCatalogue.test_05c_rule_outputs_are_catalog_not_live`, `'computed' !=
  'catalog'`, abm data drift). Neither is J3's and neither was ever hidden — nobody had run
  them since the code under them changed. **Record the `-u` list beside the number, or the
  next phase compares two different questions and calls the difference a regression.**
- MJ15 (J3): **the transform could not tell the resolver that the feed had said nothing,
  because `default_value` is a Float with a default of 0.0.** The empty-feed guard (S2) was
  first written the obvious way — run `transform_value` and test the RESULT for emptiness.
  It did not work, and the reason is a schema detail three files away:
  `transform_value` short-circuits an empty input to `self.default_value`
  (`integration_field_mapping.py:382-387`), and that field is
  `fields.Float(default=0.0)` — **a column with no null**. So a wire that says nothing and a
  wire that says "when empty, use zero" are the same row, and every empty feed value came
  back as a perfectly good `0.0` that claimed the component's slot exactly as before. The
  guard has to ask the SOURCE (`_feed_value_is_empty(raw) and not mapping.default_value`),
  and a non-zero default is the only "somebody stated this" signal the schema can carry.
  **When a sentinel has to survive a coercion, check that the type it lands in has room for
  it.** Four resolver tests failed on this and every one of them looked like the guard was
  simply not wired in.
- MJ16 (J3): **`self.env.get('some.model')` returns an EMPTY RECORDSET, which is FALSY —
  `if Model:` is a bug that reads as a null check.** `_source_conflicts` guards with
  `if FM is None`, which is right; the first cut of `source_conflict_probe` guarded with
  `... if FM else []` and therefore took the else branch on *every* call, reporting "no
  conflict" forever. The dialog would simply never have opened, on a live database, silently
  and permanently — and the RPC would have returned a well-formed successful payload while
  doing it. `env.get` is `None`-or-model, and the only correct test is `is None`.
- MJ17 (J3): **`provenance_token(..., origin='excel')` was hardcoded, with a comment saying
  it would be fixed "when a run can carry two sources" — and then S3 gave a run two sources
  and this line did not follow.** A component resolved by the NAME LADDER on an
  `api_data_store` run reported `src='excel'` about a number that had arrived in the feed:
  the chip named the wrong source, the lineage pointed at the wrong screen, and every
  provenance test passed because none of them exercised a feed run through the unbound
  ladder. `primary_origin` had been computed two hundred lines above for exactly this since
  S3. **A comment that says "this will need to change when X happens" is a bug with a
  timer on it; grep for its own words when you ship X.**
- MJ18 (J3, scope): **there is a SECOND dead file calling the same nonexistent method, and
  the phase deliberately did not sweep it.** S5 removed `excel_grid_widget.js`, whose
  `addColumn` called `hr.formula.config.add_rule` (no such method). A folder-wide grep for
  `add_rule` then failed the broom test on `grid_actions.js` — a different uncalled file,
  also commented out of the manifest, calling the same nonexistent method in the same way.
  It is recorded rather than deleted: nothing J3 touched imports it, and MF39's rule is that
  deleting live-untested code to chase a grep is how a phase acquires a regression it did
  not need. The broom test now sweeps the manifest's LIVE bundles instead of the folder,
  which is the assertion that actually matters ("no loaded asset calls a method that does
  not exist"). **A J4+ broom should take `grid_actions.js` and the rest of the commented-out
  grid bundle together, as its own scoped decision.**

- MJ19 (J3, environment): **Python's implicit string concatenation is a SYNTAX ERROR in
  JavaScript, it survives every check that is not a real parse, and it takes the entire
  backend bundle down.** A two-line `_t("… records — "\n"and read them back …")` in
  `MODES` — written by hand in the same session as a hundred lines of Python, where that
  form is correct and idiomatic. The consequences, in the order they were met:
  every screen on the database rendered as a BLANK BODY (`document.body.innerText === ""`,
  `readyState: complete`, HTTP 200, no server error, one console line reading
  `Uncaught SyntaxError: missing ) after argument list`). It is MJ5's shape with a different
  compiler: one malformed token anywhere in a bundle kills the bundle, so the failure never
  points at the feature that caused it.
  **The part worth the entry is how it was nearly missed.** `node --check` was run over all
  four modified JS files and reported PASS for every one of them — because the shell loop
  was `if node --check "$f" | head -2; then echo PASS; fi`, and `head` exits 0 whether or not
  the parse failed. The harness reported on itself, not on the code. The error was finally
  located by fetching the SERVED bundle
  (`curl /web/assets/<hash>/web.assets_web.min.js`) and running `node --check` on that, which
  is also the only check that covers what the minifier does — it joined the two adjacent
  literals onto one line, turning an ambiguous newline into an unambiguous `"a" "b"`.
  Lessons: never write a multi-line string in JS without `+`; check the EXIT CODE, not the
  output, of a validator; and when a page comes back blank with a clean 200, `node --check`
  the bundle before believing anything about your feature.

- MJ20 (J4, testing): **MJ14 again, one module further out — a THIRD long-standing red
  was hiding behind the `-u` list, and finding it cost nothing only because the baseline
  was taken first.** J3 recorded 246 tests with two reds under
  `-u pb_hr_payroll_formula,pb_formula_studio`. J4 needed `pb_integrations` in the list
  (the composer and `_rule_consumers` both live there), and the baseline — taken on the
  machine, before a line was written — came back **295 tests, 2 failed + 1 error**. The
  extra red is `pb_integrations` `TestLedgers.test_the_ledgers_never_sudo`, a SOURCE
  assertion that `pb_integrations/models/pb_integrations.py` contains no `sudo(`; some
  later change added one. It is nobody's regression and it has been red for as long as
  nobody ran it. Had J4 not measured first, its own run would have shown "2 failed, 1
  error" against a remembered "1 failed, 1 error" and the phase would have spent an hour
  hunting a failure in a file it never opened. **MJ11 says take the baseline yourself;
  MJ14 says record the `-u` list beside it; MJ20 is the corollary — when a phase WIDENS
  the `-u` list, the widening itself is a measurement, and everything it newly touches
  has to be re-baselined before it can be blamed.**
- MJ21 (J4, environment): **`--` inside an XML comment is not a comment style, it is a
  parse error, and OWL reports it as a template that does not exist.** Two J4 lane
  headers were written `<!-- ==== LANE 2 — the rules ----- -->`, and `--pbim-z-modal` was
  quoted inside a prose comment in `mapping_studio.xml`. XML forbids `--` in a comment
  body outright; `xml.dom.minidom.parse` refuses the file and Odoo's loader refuses it
  the same way — which surfaces as "Missing template" for every `t-name` in it, i.e. as a
  component that was never registered rather than as a broken comment. It was caught
  before deploy only because the well-formedness check was run with its EXIT CODE tested,
  which is the half of MJ19 that generalises: **the value of a validator is its exit
  code, and a syntax family you have never hit before is exactly the one your editor will
  not colour differently.** Use `====` in decorative rules, and parse every XML file you
  touch before shipping it.
- MJ22 (J4): **the default connector is a per-BOARD question, and the shared heuristic
  answers a different one.** `_api_active_connector` picks the connector this scheme's
  WIRES point at — right for the API board, and on abm it answers connector 1 while all
  eight transformation rules on the database live on connector 3. So the Transformations
  tab opened on an empty state over a database with eight rules in it, which reads as the
  feature being broken rather than as the connector being wrong. Two rules settle it and
  both matter: a **chosen** connector (the picker, or a deep link that names one) is
  never second-guessed — hence `state.connectorPicked`, because "the user picked this"
  and "we guessed this" had been the same variable; and an unchosen one is re-derived by
  `_tf_active_connector`, which DELEGATES to the old heuristic and overrides it only when
  it lands on a connector with no rules. The heuristic itself is untouched: changing a
  shared helper under four other callers to suit one board is the fork this programme
  keeps refusing. **And the board must then ADOPT what the adapter chose** — a header
  naming Zoho People over lanes showing Zoho People (ABM) is W76.3's bug class, which
  looks right and describes the wrong thing. (An archived connector is never the default
  either: a rule outlives its connector being archived, so without that guard the board
  would open on a system somebody deliberately retired.)
- MJ23 (J4, testing): **a live gesture that fires three RPCs needs a probe window sized
  for three RPCs, and a short one reads exactly like a broken handler.** The arm-output →
  click-component draw runs `source_conflict_probe`, then `api_mapping_create`, then a
  full `transform_flow_data` reload over 99 components. A 2500ms wait showed the wire
  count unchanged and the armed state cleared — the precise signature of "the handler ran
  and the callback is not wired", and the next stretch went into a prop chain that was
  correct all along. The DATABASE settled it (MF37, again): one row, created by the
  direct call, none by the gesture — so the gesture really had not written, but only
  because the read happened before it landed. Re-run at 7000ms it wrote, and the wire
  bound `rule/WORKEDHRS/board` exactly as designed. **When a UI probe disagrees with the
  code, suspect the clock before the wiring — and count the round trips before choosing
  the timeout.**

- MJ24 (J5, environment): **`--stop-after-init` hung in "Initiating shutdown" and the NEXT
  run started anyway, so two upgrades ran concurrently on one database — and both
  reported success.** CR20 says a browser tab holding a websocket hangs a detached
  `odoo-bin`; what it does not say is what that costs the run AFTER it. The baseline
  unit finished its tests at 16:26 and its pid was still alive at 16:44; the deploy
  unit, dispatched meanwhile, upgraded the same database underneath it and wrote
  `EXIT[abm]=0`. Nothing looked wrong anywhere: the sentinel was green, the version
  bumped, the tests had a number. **A `systemd-run` dispatcher returns immediately, so
  "the unit was launched" and "the unit finished" are different facts and only the
  second one is safe to build on.** The runner now polls the LOG for
  `odoo.tests.result` and then kills by pid rather than waiting for a shutdown that
  may never come — `--stop-after-init` is a request, not a guarantee. Before every
  run: `pgrep -af odoo-bin` and prove it is empty BY PID. And the service does not
  always come back: `/etc/init.d/odoo-server start` at the end of a script that has
  just `kill -9`'d its own children silently no-ops often enough that the live
  databases were down three separate times in this phase. Verify with
  `curl -o /dev/null -w '%{http_code}' /web/login` and expect 303, not the exit code
  of `start`.
- MJ25 (J5, testing): **four of the first seven test failures were the ORACLE being
  wrong, not the code — and three of them were the same mistake: an ambiguous
  `split()` anchor.** `test_05c` split on `case "journey":` and got `fromSlot`'s
  copy instead of the loader's; `test_07b2` split on `_applyFocus()` and got the CALL
  SITE instead of the definition; `test_04c` asserted the literal `pb_mode: "employee"`
  against a door that spells it `pb_mode: mode || "employee"`; `test_06c` guessed at
  the first characters of a payload value and rejected
  `ep.name or ep.code or _("Unnamed feed")`. Every one of them failed against
  perfectly correct code, and each cost a diagnosis. **A source assertion is a
  parser you wrote in a hurry.** Anchor on the most specific string that can only
  occur once (`_applyFocus() {`, `async load()`), and when you find yourself
  encoding "the value probably starts with one of these characters", ask the precise
  question instead — `test_06c` became "is this key assigned a BARE QUOTED STRING",
  which is the only thing that can actually ship untranslated, and it stopped having
  opinions about correct code.
- MJ26 (J5, testing): **two of J5's own tests asserted a fact that was only true of
  abm, and the phase's own feature is what exposed the difference.** `test_03k2`
  demanded that all five lanes ghost on an empty scheme. That is true on acme (no
  connectors, no rules) and FALSE on abm, where the Systems, Feeds and
  Transformations lanes describe the DATABASE rather than the scheme — abm has two
  connectors and eight rules, so a brand-new scheme there is empty and those lanes
  are still rightly full. The fix was to state the invariant that is actually true:
  per-SCHEME lanes (the file, the records, the run, the scheme itself) always ghost
  on an empty scheme; database-wide lanes ghost exactly when the database is empty
  of that thing. **"All five" was a description of one database, mistaken for a
  rule** — the same shape as MJ14's `-u` scope lesson, one axis over: a test can be
  scoped to a DATABASE as silently as a suite can be scoped to a module list.
- MJ27 (J5): **a one-shot order that is REPLAYED at mount stops being one-shot, and
  the bug is invisible on the door you are testing.** J5's pre-filter rides
  `MappingCanvas`' existing `command` channel, which fires from
  `onWillUpdateProps` — so an order issued in the same turn as the tab switch that
  MOUNTS the board is swallowed by the token capture in `setup`. Replaying it at
  mount fixes that, and introduces the opposite defect: a door with NO focus
  returned early, left the PREVIOUS door's order sitting in the prop, and the next
  mount re-applied it. Live, opening "Payobook records" after opening a feed called
  Employees mounted the people board filtered to `Employees` — a board that has lost
  most of its cards, for a reason nothing on screen explains. **An empty order is
  still an order.** `_applyFocus` now always writes the command, `""` included, and
  the canvas honours empty text as "filter by nothing". Only `search` is replayed at
  mount; replaying `pulse` would flash every wire on every tab open and `armLeft`
  would arm a card nobody clicked.
- MJ28 (J5): **MJ1, restated for the door protocol, and caught only by looking at the
  screenshot.** The pre-filter seeded BOTH columns with the door's focus. Every
  focus a Journey node carries is a SOURCE-side name — a feed, a sheet, a rule
  output — so arriving from the feed "Employees" filtered the 99-component
  DESTINATION catalogue by it and the right column read `0 of 99 · Nothing matches
  that`. The board had hidden the ninety-nine components the reader clicked through
  to see, and every RPC, count and door assertion was green while it did.
  MJ1 settled this two years of phases ago for `groupFilter` ("filtering the
  destination catalogue by a SOURCE column's role is not a narrowing anybody asked
  for") and the lesson did not transfer because the mechanism was different. The
  door narrows what you arrived FROM and clears what you are aiming AT.
- MJ29 (J5): **the tab's most valuable sentence was one the handover did not ask for,
  and it was only findable by rendering the real database.** Test 2 expected the
  scheme's `connector_id` marked primary and the others dimmed. On abm — and on all
  four databases — `connector_id` is UNSET (S20 recorded it as a tie-break nuisance),
  and the resolver's pre-pass is gated on that exact field: `if self.source_type ==
  'api_data_store' and config.connector_id:`. So abm's 33 drawn feed wires have
  never been read by anything, and no screen in the product said so. The handover's
  case could not pass as written; the honest reading of it — make the one-connector
  limit visible — REQUIRED covering the case where the limit has never been set.
  **A spec written against the code can still be silent about the state the data is
  actually in; render the real database before deciding a case is unpassable.**

- MJ30 (J6): **the wires were measured in one element and painted in another, and every
  automated check this codebase owns is structurally blind to it.** `_recompute` took its
  origin from `.tfb` (the tab) while `.tfb-wires` is `inset: 0` of `.tfb-board` (the tab
  minus its search bar), so every wire was drawn **49.75px** too low — the bar's exact
  height. It survived J4's whole validation, and the reason is worth more than the bug:
  **MJ12 taught the bounding-box sweep to exclude SVG nodes**, because Lucide `<path>`
  siblings overlapping each other invented five defects. That exclusion is correct and it
  means the sweep has never once measured a wire. Screenshots did not catch it either,
  because 50px on a dense board reads as loose drawing rather than as breakage. What
  finally caught it was asking a question no existing check asks: **how far is this wire's
  endpoint from the port it claims to end on** — 0px is the only right answer, and it is
  cheap to assert. The compounding half is nastier: `clampY`'s band is measured in the same
  wrong space, so a scrolled-away target parks the wire 49.75px INSIDE the lane, where it
  lands on a real card and reads as a termination. The owner reported it as "wires anchor to
  the wrong cards"; it was one offset, twice. **When a component computes coordinates for a
  child it does not own, the origin is a contract — assert that the measured element IS the
  positioning ancestor.**
- MJ31 (J6): **the delete button was rendered at the midpoint of the thing you click to
  select, which turns a double-click into a delete — and no test that mounts nothing can see
  it.** `.tfb-wireact` was placed at `(hx, hy)`, the Bézier midpoint, i.e. dead centre of the
  wire's own stroke. Click one selects the wire; the pill materialises under the cursor;
  click two of a double-click presses **Remove**. That is how the owner destroyed a live
  mapping on a production database, and every unit test, every RPC probe and every source
  grep passes while it is true: the handler is correct, the RPC is correct, the affordance is
  labelled and titled. **The defect is a coincidence of coordinates between two elements that
  never reference each other.** The fix is arithmetic (`VERB_DY`, with a flip when the clip
  would eat the pill) and the test is the one the defect suggests: assert the verb's box does
  not contain the point that selected it, and that `elementFromPoint` there is still the
  wire. Generally: **a destructive verb must never be positioned by the geometry of the
  gesture that reveals it.**
- MJ32 (J6): **`api_mapping_create` is a DRAW, and an undo routed through it silently
  degrades the row it claims to restore.** The obvious implementation of "put the wire back"
  is to call the create adapter with the same three ids. It returns `ok`, the wire reappears,
  the board looks right — and the row has lost its `source_field_label` (re-derived from the
  source field: "Overtime 300% hours" becomes "Othrs300"), its `notes`, its `endpoint_id` and
  its transform settings, because create also unlinks rivals, discovers a fresh sample and
  writes a binding. All of those are correct for a person drawing a wire and wrong for an
  inverse. `api_mapping_restore` therefore recreates from a server-side snapshot of the
  business fields, intersected with `fields_get` so no DERIVED column is ever written back.
  Proven live: cutting `Employeestatus` and undoing returns a row still labelled "Employment
  status". **An undo is the inverse of the delete, not a replay of the create — and the test
  that catches the difference is field-by-field equality, never "a row exists again".**
- MJ33 (J6): **`left: 34%` and `right: 34%` are two points that MEET as the container
  narrows, and the sweep that was extended to find the reported defect found this one
  instead.** The two dock chips cleared each other at 1440 and overlapped by 32px at 1024 —
  invisible at the width everything is designed at, live for anyone on a laptop. It was
  caught only because D1 required adding the filtered-with-chips state to the MJ7/MJ12 sweep,
  which is the state that renders both chips at once; the sweep then failed on a pair nobody
  had gone looking for. Each chip is now placed over the LANE GAP its wires cross, which
  cannot collide by construction. **A percentage pair is a coincidence, not a layout — and
  the value of widening a regression sweep is mostly the defects it finds that nobody
  reported.**
- MJ34 (J6): **"I cannot do X" from an owner is not evidence that X is broken, and checking
  which one it is costs ten minutes.** D4 arrived as "creating a mapping by mouse is
  impossible". The arming path was intact: the button existed, was always visible, carried a
  `title`, and `armOutput` already called `stopPropagation` so the card's open-composer click
  could never swallow it. What was true is that a 22px unlabelled icon carried the board's
  ONLY write gesture, on a card whose entire body opens the Rule Composer — so every
  exploratory click landed on the composer and the owner concluded the feature was missing.
  MF26 with the sign flipped: **an affordance nobody can find is indistinguishable from an
  affordance that does not work, and the two have completely different fixes.** Establish
  which before writing either. (The fix was discoverability only: the output ROW became the
  button. No handler changed.)
- MJ35 (J6, environment): **`odoo.models.unlink` in the server log is the only oracle that can
  tell an accident from a decision, and without it this phase would have "repaired" nineteen
  rows the owner deleted on purpose.** The table was 19 rows short of J5's recorded closing
  state, against an owner report of ONE lost wire. The log named every deletion with its id,
  its user and its timestamp: eighteen of them were ids 109-126, removed one at a time over
  three minutes and followed by `action_archive` on connector 1 — a person retiring a legacy
  connection deliberately — and one was id 39, four minutes later, alone. 59 − 18 − 1 = 40,
  exactly. **A row count tells you something is missing; only the log tells you whether
  putting it back is a repair or a regression.** Read `grep -a 'deleted <model>'` before
  restoring anything, and reconcile the arithmetic out loud.
