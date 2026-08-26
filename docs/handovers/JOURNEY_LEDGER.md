# JOURNEY — one mapping home, the Excel on-ramp, honest two-way sourcing, the Journey view

**STATUS: COMPLETE — J1–J5 delivered and live on abm · acme · payobook · payobook_template
(2026-08-26). The Journey is the Mapping cockpit's landing tab and its cold-start default.**
**Defect round J6 (2026-08-26): four defects the owner reported against the live J4
Transformations board — one of which destroyed a live wire — repaired, fixed and live on all
four. Defect round J7 (2026-08-26): two legibility defects reported against the live
`System fields → Scheme` board — a dock chip painted over the top card, and component names
truncated with no way to read them — fixed in the SHARED canvas, so all five two-lane adapters
and the transform board inherit them. Defect round J8 (2026-08-26): the board's single
most-used destination was the only one it did not draw — a `Contract components` lane now
sits between Contract terms and Bank account, wirable both ways — plus the arrowhead that was
being painted under the column's scrollbar. The programme stays COMPLETE; J6, J7 and J8 are
defect rounds, not further scopes. Scope round J9 (2026-08-26): the owner WITHDREW
the either/or source restriction — a component may declare a connected-system key, a
spreadsheet column and the contract component at once, every card shows all of them
with a superscript rank, and the resolver walks them in the order that was already in
the file. J-D5 is untouched: what changed is arity, not precedence.
Scope round J10 (2026-08-26): the owner reported that a component's RECORD
destination — Employee record, Contract record, Bank account — was shown only
when it was the sole source, and asked that the WRITEBACK follow the same
priority as the payslip. Both are answered by one thing: the record joins the
ranked list at rank 4, where the resolver's tail has always read it, and ONE
function now decides that order for the resolver and for all four writeback
seams. J-D5 still untouched; nothing moved.**

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

- **J7 — DONE, live on abm · acme · payobook · payobook_template (2026-08-26).**
  → `JOURNEY_PHASE_J7_HANDOVER.md`.
  Version: pb_formula_studio **19.0.1.151.0** (`pb_hr_payroll_formula`, `pb_integrations`,
  `biz_theme` untouched; `om_hr_payroll` untouched — CR1). **Presentation only: the
  MF37 diff across the whole session is EMPTY, with no restore step.**
  **D1's cause was that two numbers were one number.** A dock chip was placed at
  `bandTop`/`bandBot` — the CLAMP BAND, which is a line INSIDE the column's
  scrollport, i.e. the exact place the first and the last visible card sit. The
  chips paint at `z-index: 4` over `.mc-cols`' 2, so the chip covered the card.
  Measured before the fix on abm at 1440: **167.9 × 23.8px** of "Last Working
  Day" behind "4 hidden by filter above", and in the plain scrolled state **all
  four chips over five cards at once** — it was never filter-specific.
  **The strip is a transparent BORDER, and that is the whole design.** Padding
  is inside the scrollport and scrolls away, in the exact state ("11 above") in
  which the chip exists at all; a border is outside it and no card can be
  painted there at any offset. It is UNCONDITIONAL because a strip that appears
  with the chip moves every card, which moves which cards fall outside the band,
  which changes whether there is a chip — a placement wired into its own
  predicate. And because `box-sizing: border-box` means a border does not move a
  BORDER BOX, `getBoundingClientRect` on the column body is unchanged — so the
  clamp band is unchanged and **wire geometry is byte-identical by construction**
  (MJ30's hazard closed by arithmetic, not by re-measurement). `maxErr` was
  **0** before and **0** after, at 1440 and at 1024, in every state measured.
  Live: chip 507.5–531.3, first card 538.4 — 7.1px clear.
  **The gap was measured and rejected, which is why this is not J6's fix.** J6
  put the transform board's chips over its LANE GAPS ("cannot collide by
  construction", MJ33) — that board has three lanes and therefore two gaps, one
  per side. The canvas has ONE gap: at 1024 it is **284px** between the column
  bodies and the two chips are **174.9 + 167.9 = 342.8px**, so the same fix
  would have recreated MJ33 exactly. The strip costs 60px of column height and
  cannot collide with anything.
  **D1 had a second cause, and it is what made it intermittent.** `_sig` carried
  a dock's key, count and filtered count and NOT its coordinates, so a pure
  layout shift never reassigned `ui.docks`. Turning a filter on grows the column
  head by the "N wires hidden by this filter" row and moves the body ~31px; the
  chip stayed at the previous layout's coordinate — measured live at 483.6px
  against a true 514.4px. The rounded x/y are in the signature now.
  **D2's cause was not `white-space: nowrap`.** The label row is **252px** and a
  **142px** "Contract component" source pill (`.mc-src`, `flex-shrink: 0`) sits
  ON THE NAME'S LINE, so the name was offered **104px** and **23 of the right
  column's 73 cards** were ellipsised. MF13/MF26 a third time, in its original
  form. `flex-wrap: wrap` is the entire fix and it works because flex wraps on
  BASE sizes before it shrinks anything: a name that cannot fit beside its chips
  sends the chips to the next line and keeps the whole row. After: **0 of 99
  right-column names clipped**, widest 252, and only the two 40-character
  "Actual Working Hours including/excluding Paid leave" names take a second
  line. Cards grow only where they had to. `overflow-wrap: break-word`
  deliberately, never `anywhere` — `anywhere` feeds min-content and is the road
  back to MF13's one-character label (asserted).
  **The residual is measured, not guessed.** A name that fills both lines gets
  `-webkit-line-clamp`'s ellipsis plus `title`, `cursor: help` and a dotted
  underline, applied by `_clipPass()` — which asks `scrollHeight` against
  `clientHeight`, the same question the browser answered when it clamped, on
  patch and on resize and never on the scroll path. Exercised live on a
  131-character typed column (client-only, `addLeftColumn` makes no RPC): the
  53-character name wrapped clean with no title, the 131-character one clamped
  WITH the full name in its title and the affordance visibly different.
  **Why five phases of sweeps ran over D1.** MJ7 taught the sweep to skip pairs
  that do not share a layer; "layer" was implemented as the nearest positioned
  ancestor's `z-index`, and `.mc-docks` is 4 where `.mc-cols` is 2 — so every
  dock-versus-card pair was skipped as an intentional overlay. The sweep is now
  a committed artefact (`pb_formula_studio/tools/mapping_overlap_sweep.js`) with
  a NAMED, closed list of things a user opens, and it asserts dock-versus-card
  separately so a refactor of `layerOf` cannot silently stop testing it. It also
  gained a second correction found in the same run — see MJ38.
  Tests: Python **436 on abm, 2 failed + 1 error — all three PRE-EXISTING and
  none J7's** (baseline taken on the machine first: **420 with the same three**,
  `-u pb_hr_payroll_formula,pb_formula_studio,pb_integrations`,
  `--test-tags /pb_hr_payroll_formula,/pb_formula_studio,/pb_integrations`).
  +16 new (`TestJourneyJ7Legibility`). hoot **119**, 0 failed (baseline taken on
  a warm server: 113 + 6 J7). 12/12 numbered cases pass.
  **0 bounding-box overlaps and 0 dock-over-card pairs in 5 states at 1440 and
  4 at 1024** — both columns, above AND below chips, resting / scrolled /
  the owner's filtered state / filtered-and-scrolled / suggested-only — with
  `elementFromPoint` at each chip's centre agreeing, and no horizontal body
  scroll. The transform board inherits the name fix (113 cards, 0 clipped) and
  keeps J6's alignment (`maxErr 0`).
  Two caveats, both recorded rather than smoothed over. (a) Case 4 asked that a
  docked wire "still fade and lose its arrowhead" — that is the TRANSFORM
  board's behaviour (J6 deviation 3). The canvas has always marked a parked end
  with a `.mc-park` dot and KEPT its head, and J7 did not change it: 45–49 park
  dots render in the scrolled states. Changing it would be a redesign of the
  canvas' wire vocabulary, not a J7 defect. (b) Case 7 asked for a wrapped card
  in EACH column carrying a wire. abm's feed catalogue has no name long enough
  to wrap (widest 236px of 252), so the wrapped-LEFT case was proven for layout,
  sweep, centring and the clip affordance — via a client-only typed column,
  `addLeftColumn` makes no RPC — but not with a wire on it, because drawing one
  would have been a write. The wrapped-RIGHT case IS proven with wires
  (`maxErr 0` with both wrapped cards on screen), and anchoring reads the card's
  rect, which does not know which column it is in.
  **MF37 on abm: byte-identical before and after, no restore step** —
  `hr_integration_field_mapping` 42 rows `115857ac9ba1762a425d83fc493331c5`,
  `hr_formula_rule` config 14 99 rows `ce6602578d9e6971d85b6f3028761fe3` with 8
  non-empty bindings, `hr_payslip_import_mapping` 21, `hr_api_transformation_rule`
  8, 0 batches, 0 lines, 0 payslips. `action_process` was never called; no live
  API pull was made.
  **The opening state was NOT J6's closing state, and the log said why** (MJ35's
  method, second use): the table read 42 rows against J6's recorded 41 and config
  14 had 8 non-empty bindings against J6's recorded 0. `odoo.models.unlink` shows
  User #2 deleting one rival row per draw between **01:24 and 01:30**, eight
  times, each paired with a create — the owner drawing wires on the live board
  eight minutes before this session began. Nothing was "repaired"; today's state
  was taken as the baseline and returned unchanged.

- **J8 — DONE, live on abm · acme · payobook · payobook_template (2026-08-26).**
  → `JOURNEY_PHASE_J8_HANDOVER.md`.
  Version: pb_formula_studio **19.0.1.153.0** (`pb_hr_payroll_formula`, `pb_integrations`,
  `biz_theme` untouched; `om_hr_payroll` untouched — CR1).
  **The commonest destination on the board was the only one it never drew.** A contract
  component is not a field of `hr.contract` — it is a row of `hr.contract.advantage`
  pointing at a template matched by CODE — so it could never have come out of
  `ir.model.fields`, and the only thing that said where Gas Allowance goes was a badge
  on the left card. There is now a **`Contract components` lane** between Contract terms
  and Bank account carrying two synthetic cards on the `b:` precedent, `c:amount` and
  `c:text`, and abm's **20 flagged rules draw 20 wires into them (17 + 3)**, asserted
  against the badge programmatically rather than by eye. `_ec_right_column` splices BOTH
  synthetic lanes off the lane index now, because a second remembered key is how the
  second lane lands in the wrong place the day a third arrives.
  **Two cards, and the reason is in the resolver rather than in the taxonomy.**
  `_transform_data_to_formula_inputs` builds `contract_component_amounts` from the
  contract's advantage lines and **SKIPS `value_type == 'text'` outright** — letting a
  text component in would feed a permanent 0.0 into any formula naming it. So an amount
  is genuinely two-way (⇆, "read back from the contract when the file or feed leaves
  this empty") and text is `to_record` and says only the import half — J3's refusal to
  print a confident falsehood, one destination over.
  **Nothing was reimplemented.** Drawing to `c:amount` ROUTES to
  `employee_mapping_make_component`, which already refused a calculated column, already
  unlinked any rival field/bank row and already set the role per CR-A2; the wire's
  Remove verb routes to `employee_mapping_detach_component`, whose refusal ("N contracts
  already carry a value for CODE") is SHOWN, with no force path. There is no
  `hr.payslip.import.mapping` row behind a component, so the wires are synthesised with
  their own id namespace (`cc<id>`), their own `kind`, and **`ref: False`** — the client
  branches on `kind`, and even a careless path hands `employee_mapping_delete` an empty
  recordset instead of a stranger's row.
  **Undo is one helper with two arguments, not a second copy.** J6's
  `_removeWireUndoable` now takes the cut and restore RPC names; a component's snapshot
  is the two booleans plus `column_role`/`column_role_source`, and
  `employee_component_restore` deliberately does NOT route through the promotion, which
  would re-derive the role (MJ32, one board over — proven: a component detached with
  role `reference`/source `auto` comes back with `reference`/`auto`, not `payroll`/`user`).
  **The card answers "does this exist yet?"** — one indexed template search, plus a
  `contract_id:count_distinct` aggregate per kind that actually has templates. On abm
  (0 templates) that is one search and no aggregate, and the card reads *"Created on the
  first import — nothing on any contract yet."* `employee_mapping_data` measured live,
  warmed, median of 7: **90.5 ms before → 93.5 ms after (+3.0 ms), 127 KB → 134 KB**,
  the before taken by putting the pre-J8 model file back on the same machine and DB.
  **A type clash is refused at wire time**, because `_get_or_create_advantage_template`
  never flips an existing template's `value_type` — it logs a warning where no user will
  see it, so accepting would be a promise the import quietly declines.
  **The card cannot vanish under the hand that wired it** (MF15's trap by a second
  gesture): a wire to `c:amount` sets `column_role = 'payroll'`, which the board hides,
  so the draw turns the payroll chip on through the SAME state flag the menu verb uses
  and the toast says so — proven live from a cold board with the chip off:
  *"J8 probe column is now kept on the contract as an amount. Pay columns are shown so
  you can see it."*
  **D2's cause was OCCLUSION, not clipping, and it was one pixel.** An arrowhead spans
  `ANCHOR_GAP + HEAD` = 15px from a card's edge and `.mc-col-body` gave it 14px of
  padding; the sixteenth pixel is the column's SCROLLBAR, which belongs to `.mc-cols`
  (`z-index: 2`) and paints over `.mc-wires` (`z-index: 1`). Measured live at 1440
  before the fix: head box 375→386, painted pixels stopped at **384**, and what was lost
  was the flat BASE of the triangle — its widest, most recognisable edge. `.mc-board`'s
  `overflow: clip` was never involved (proved by `scrollbar-width: none`, which made the
  head whole at once). The gutter is now `WIRE_GUTTER = ANCHOR_GAP + HEAD + 3` in the
  kernel and the same number in the stylesheet, pinned together by a test; the empty-
  column anchor fallback reads it instead of its own literal 14. Cards narrow 8px —
  measured after: label row 252→**244px**, widest name 223.8px, **0 of 357 names
  clipped**, so J7's fix holds with 20px to spare.
  **The arrival comb, and why it is in the shared canvas.** Twenty curves converging on
  one port is a knot, and the component lane makes that the normal case. `combOffsets`
  (pure, in the kernel) spreads arrivals down the card's own edge, BOUNDED by it, at
  `min(9px, room/(n−1))`; `n <= 1` returns `[0]`, so every board without a pile-up is
  byte-identical. Measured at 1440 and at 1024 with the payroll chip ON: 17 arrivals on
  the 119px amount card at a uniform **6.56px**, all 17 distinct and all inside the card;
  the 3 text wires get the full 9px. `_recompute` is three passes now because the comb
  has to know how many wires reach a card before it can place any of them.
  **The sweep can finally see an arrowhead.** MJ12 drops every `SVGElement`, which is
  correct and is exactly why no sweep has ever measured a wire (MJ30). Heads are
  re-admitted BY NAME (`polygon.mc-head`, never `<path>`) and tested against the derived
  clip box plus the named opaque boxes of the column layer — cards, dock chips, and the
  **scrollbar gutter**, which is not an element and which no rect-versus-element pass
  could ever have found. Proof it could not have fired before: forcing the old 14px
  padding back on the live board and recomputing reports **3 `mc-head back` occluded by
  `scrollbar-gutter`, 1.0 × 12.0px each**; at 18px it reports 0.
  `wireEndpointError` is a committed artefact at last — `.mc-w` carries
  `data-wire/left/right/dockl/dockr`, read only by the harness.
  Tests: Python **467 on abm, 2 failed + 1 error — all three PRE-EXISTING and none
  J8's** (baseline taken on the machine first: **436 with the same three**,
  `-u pb_hr_payroll_formula,pb_formula_studio,pb_integrations`,
  `--test-tags /pb_hr_payroll_formula,/pb_formula_studio,/pb_integrations`). +31 new
  (`TestJourneyJ8Components`). hoot **126**, 0 failed (baseline 119 + 7 J8).
  15/15 numbered cases pass. **0 bounding-box overlaps, 0 dock-over-card pairs and 0
  occluded or clipped arrowheads in 6 states at 1440 and 5 at 1024** — resting, left
  scrolled, right parked on the component lane, both mid, filtered, filtered-and-
  scrolled — with `maxErr 0` in every one, 82 heads measured each time, and no
  horizontal body scroll. The Transformations board is clean on the same sweep (19
  heads, 0 occlusions) and does NOT share D2's cause: its heads carry no `+4` anchor
  offset, so 11px fits its 14px padding.
  **MF37 on abm: byte-identical before and after** — `hr_integration_field_mapping` 41
  rows `8c41d0953db14c8c6a6ade05476ade84`, `hr_payslip_import_mapping` 21 rows ids
  `1,2,30…108` `07792a486d5d74400f63e2606599383e`, `hr_formula_rule` config 14 99 rows
  `8a0d5bdc8e5439b40769ac61887d9ec7`, the flagged set the SAME twenty ids
  `582,593,594,595,596,597,598,599,602,603,604,605,638,669,670,675,676,677,678,679`, and
  **`hr_contract_advantage_template` and `hr_contract_advantage` both still 0 rows**.
  Every live write went through a throwaway rule (`J8PROBE`, id 13584) that was created,
  promoted by mouse, cut, undone, cut again, expired and then deleted; no live column was
  touched. `action_process` was never called; no live API pull was made.
  **One finding worth the owner's attention.** The transform/API board shows 19 of the 20
  flagged columns with a `Contract component` source pill, and Gas Allowance with
  `Already fed by Spreadsheet "SEVL|Gas Allowance"`. The two boards are not disagreeing:
  the source pill names the rung of the resolver ladder that WINS (an explicit binding,
  rung 1, outranks a contract component, rung 5) and the new lane names where the value
  is KEPT. Gas Allowance is the one flagged column that also carries a binding — one of
  the eight the owner drew on 2026-08-26 (J7's opening note).

- **J9 — DONE, live on abm · payobook · payobook_template (2026-08-26).**
  → `JOURNEY_PHASE_J9_HANDOVER.md`. **acme was removed from the deploy scope by the
  owner mid-phase — it is a redundant database and was not upgraded.**
  Versions: pb_hr_payroll_formula **19.0.1.82.0** · pb_formula_studio **19.0.1.158.0**
  (`pb_integrations`, `biz_theme` untouched; `om_hr_payroll` untouched — CR1).
  **The restriction is gone, and what was missing was never the order.** The owner
  withdrew J3's either/or rule: API and spreadsheet may both map to a Payroll Schema
  component, the contract component may sit beside them, and the card shows all of
  them with a superscript rank. J-D5 still binds and nothing moved — the precedence
  the owner asked for (feed → spreadsheet → contract component) is the order that was
  already in `payroll_import_batch.py`. **What was missing was ARITY:** the binding
  was a single pair of Chars, so a second source could only be an unnamed heuristic
  (`side_o`) and no screen could name it.
  **`hr.formula.rule.source`, one row per KIND**, ranked `feed → rule → excel`; the
  five `source_binding*` Chars became COMPUTED, STORED, READONLY views of the
  highest-ranked row, so all seventy-odd references — including two `search()`
  domains in `pb_integrations` that need them stored — keep working untouched.
  `set_source_binding(kind, key)` keeps its signature and now UPSERTS the row for
  that kind; `clear_source_binding(kind=None)` is the removal it never had.
  **The neutrality rail held, and it is the whole of the risk.** A component with one
  declared source takes S3's branch verbatim, `side_o` heuristic and fallback
  provenance included; `_multi_source_walk_entered` is a class counter that a
  single-source run must leave at **0**, and it does (`test_01a`–`test_01d`). The
  multi walk is entered only by `len(declared) > 1`, and with two kinds declared there
  is no undeclared blob left for the heuristic to cover — a run carries at most two
  payloads.
  **T1 held: exactly ONE card on abm renders two chips.** All nine feed-bound rules
  carry a connector wire whose `source_field` is character-for-character the binding
  key (`api_mapping_create` writes both in one gesture), and the `(kind, key)` fold
  makes them one source: measured live on both boards, `BANKNAME=1 … WORKEMAIL=1`,
  and the only multi-source card is **GASALLOWANCE → Spreadsheet¹ · Contract
  component²**.
  **The dialog stopped being an ultimatum.** `source_conflict_probe` still writes
  nothing and still fires on the same predicate; it now returns the resulting RANKED
  LIST and the primary action is **Add source**, with Replace kept as the secondary
  and the alert triangle swapped for a list glyph. Two CONNECTIONS is still a genuine
  conflict (a run reads only the one the scheme is set to) and keeps its old wording.
  **Six pre-existing tests asserted the withdrawn restriction and were inverted, not
  silenced** — `TestJourneyGuardrails` 02e/03e/04a, `TestJourneyJ8Components` 05c,
  `TestMappingCatalogue` 07/08 — each with a comment saying what the owner changed.
  One asymmetry is deliberate and recorded: wiring a component to a NATIVE FIELD still
  demotes it (MAPFIX B2's `_ec_demote_component`), because that is a different
  mechanism with its own sentence and the owner did not ask about it.
  Tests: Python **515 on abm, 2 failed + 1 error — all three PRE-EXISTING and none
  J9's** (baseline taken on the machine first: **467 with the same three**,
  `-u pb_hr_payroll_formula,pb_formula_studio,pb_integrations`). +48 new
  (`TestJourneyJ9Sources` 25, `TestJourneyJ9Display` 23). hoot **135**, 0 failed
  (baseline 126 + 9 J9). 23/23 numbered cases pass.
  **0 bounding-box overlaps, 0 dock-over-card pairs and 0 occluded or clipped
  arrowheads in 7 states at 1440 and 6 at 1024**, `maxErr 0` in every one, and
  **0 names clipped** on all four boards (568 at 1440, 386 at 1024) — MJ40's gate held
  with the chips a line taller.
  `employee_mapping_data` measured live, warmed, median of 8, with the pre-J9 model
  file put back on the same machine and DB for the "before": **84 ms → 85 ms**, 102 KB
  both (its right column is employee/contract fields and carries no source chips).
  The boards that DID change: `import_mapping_data` **92 → 67 ms**, 36 → 42 KB;
  `api_mapping_data` **134 → 131 ms**, 50 → 56 KB.
  **MF37 on abm: byte-identical before and after** — `hr_formula_rule` config 14 99
  rows `1b95d661069834dff8701ce4a2b9e3fd`, `hr_integration_field_mapping` 41 rows
  `787b99f56c00a7a349986fcc0a7f60d2`, `hr_payslip_import_mapping` 21 ids `1,2,30…108`,
  `hr_api_transformation_rule` 8, 0 batches, 0 lines, 0 payslips, and
  **`hr_contract_advantage_template` and `hr_contract_advantage` both still 0 rows**.
  The new `hr_formula_rule_source` holds exactly the 13 rows the migration converted.
  Every live write went through the throwaway rule `J9PROBE` (id 15832), created →
  bound by mouse → wired by mouse through the new dialog → cut → undone → cut →
  deleted. One collateral deletion was made and repaired: see **MJ46**.
  `action_process` was never called; no live API pull was made.

- **J10 — DONE, live on abm · payobook · payobook_template (2026-08-26).**
  → `JOURNEY_PHASE_J10_HANDOVER.md`. **acme is redundant and was NOT upgraded**
  (owner ruling, standing since J9): it stays at 19.0.1.153.0 / 19.0.1.81.0.
  Versions: pb_hr_payroll_formula **19.0.1.83.0** · pb_formula_studio
  **19.0.1.160.0** (`pb_integrations`, `biz_theme` untouched; `om_hr_payroll`
  untouched — CR1).
  **The owner's bug report was one line.** `if out: return out` at
  `pb_formula_studio.py:615` made the record tier reachable only when nothing
  else was declared, which is exactly *"you are showing EMPLOYEE RECORD or
  CONTRACT RECORD only if that is the only source"*. The contract component two
  lines below had been APPENDED unconditionally since J9 and that is the
  treatment the record now gets. `_source_employee_dest_ids` returned a bare
  `set()` of rule ids, so neither WHICH record nor WHICH FIELD was available to
  render even if the early return had gone: it is `_source_record_dests` now,
  `{rule_id: {kind, key, label}}`, in **one SQL statement** joining `ir_model`
  and `ir_model_fields` (measured: `assertQueryCount(__system__=1)` on a
  99-rule config).
  **Three spellings, one rung.** `employee_field` / `contract_field` /
  `bank_account` join `_SOURCE_RANK` at position 4 and **nothing moved**
  (J-D5): that is where `get_mapped_input_value` has always sat, after the
  spreadsheet and before `contract_component_amounts`. A component carries at
  most one `hr.payslip.import.mapping` row so the three never compete.
  **Request (a): the writeback obeys the order, and the ordering constraint is
  why.** The writebacks run at steps 1-3 of `action_process` and the resolver
  runs inside step 4, so a writeback cannot reuse `input_values` — it does not
  exist yet. Nothing was reordered; the ORDER was extracted instead of the
  RESULT. `_declared_source_walk` is the single implementation and J9's two
  bound branches moved into it verbatim (the "search the other side" heuristic
  is unconditional for ONE declared kind, because S3 reports the loser as
  `ignored` even when the binding wins, and `if not hits` for two or more,
  because J9 wrote it that way). `_shared_resolution_entered` is the instrument
  — a counter, because a source grep is satisfiable by a second copy that
  spells the method name in a comment.
  **FOUR seams, not three** (a handover discrepancy, resolved by covering
  both readings): `_update_employee_from_raw_data`,
  `_update_contract_from_raw_data` (+ its `_sync_employee_contract_mirror_fields`
  half), `_sync_employee_bank_account` and `_sync_contract_components` all
  resolve through `_writeback_raw_value`. §2.5's snippet named steps 1b-3; §1
  and §3.2 said "employee, contract and bank", which is a different three. All
  four now share one order.
  **The no-op rail.** A winner whose tier is `record` or `component` makes the
  writeback a no-op: the record already holds it and a self-assign only dirties
  `write_date`. Proven by `write_date` equality, not by value equality.
  **The neutrality rail.** A component that declares NOTHING takes
  `_get_rule_raw_value` unchanged, which is the ~40 mapped-but-unbound
  components on the live databases. `_multi_source_walk_entered` is **0** on a
  single-source run (`test_15a`), and S3's fallback provenance survives
  byte-for-byte (`test_15b`, `test_15c`).
  Tests: Python **559 on abm, 2 failed + 1 error — all three PRE-EXISTING and
  none J10's** (baseline taken on the machine first: **515 with the same
  three**, `-u pb_hr_payroll_formula,pb_formula_studio,pb_integrations`,
  `--test-tags /pb_hr_payroll_formula,/pb_formula_studio,/pb_integrations`).
  +44 new (`TestJourneyJ10Writeback` 24, `TestJourneyJ10RecordSource` 20).
  hoot **141**, 0 failed, 541 assertions (baseline **135** measured on the same
  server before a line was written). 24/24 numbered cases pass, with three
  measured deviations from §2 recorded below.
  **The abm picture: 2 cards with two chips became 16, not 1 → 11.** Both ends
  of the handover's number were wrong and both were measured rather than
  argued — see **MJ50**. `DESIGNATION` reads **Connected system¹ · Contract
  record²** and `BANKNAME` reads **Connected system¹ · Bank account²**, with
  the FIELD LABEL in the tooltip ("Reads “Job Position” from Contract record")
  and never `job_id`.
  Sweep: **0 overlaps, 0 dock-over-card, 0 occluded/clipped heads, maxErr 0 and
  0 names clipped** across all four boards at 1440 and 1024 in resting and
  mid-scroll states (157 / 152 / 260 / 113 names). Two pre-existing overlap
  families were found by widening it and are recorded in **MJ48**; both were
  disproved as J10's by hiding `.mc-src` and re-sweeping.
  Round trips, warmed, median of 8, with the pre-J10 model files put back on
  the same machine and DB for the "before": `employee_mapping_data`
  **105 → 85 ms** (110.7 KB both — its right column is the field catalogue and
  carries no source chips), `import_mapping_data` **79 → 73 ms**, 45.7 → 50.0 KB,
  `api_mapping_data` **124 → 125 ms**, 61.2 → 65.5 KB.
  **MF37 on abm: byte-identical before and after, with no restore step** —
  `hr_payslip_import_mapping` 21 rows ids `1,2,30…108`
  `07792a486d5d74400f63e2606599383e`, `hr_integration_field_mapping` 41
  `c62ec8dfc9a24a42e0b978fb23eebef3`, `hr_formula_rule` config 14 99
  `e269041b4312d60d0ff3ec2063a8eea7`, `hr_formula_rule_source` 13
  `4a4b916d79d9591d068b0f92c179cacb`, `hr_api_transformation_rule` 8, 0
  batches, 0 lines, 0 payslips, and **`hr_contract_advantage_template` and
  `hr_contract_advantage` both still 0 rows**. This is the first phase that
  could silently touch employee data, so it is also proved: `hr_employee`
  content fingerprint `1ad9bc974a863804712aa50d5cd978ae` unchanged, 3 rows,
  `hr_contract` 0 rows, `res_partner_bank` 0 rows. The only `hr_employee`
  `write_date` movement all session was **`HR Presence: cron`**, hourly,
  `lastcall` matching the stamp to the microsecond — MJ35's method applied to a
  timestamp instead of a deletion. Every live write went through the throwaway
  rule **`J10PROBE`** (id 20685, mapping 2214), created → rendered on the live
  board (**Spreadsheet¹ · Contract record²**) → deleted; **no connector wire
  was drawn**, because MJ46 says `api_mapping_create` unlinks a rival on the
  SOURCE end too. `action_process` was never called; no live API pull was made.

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

- MJ36 (J7): **a reserved band has to be reserved against SCROLLING, and only one CSS box is —
  the border.** D1's chip sat on the first card, and the obvious fix is "push the content down".
  Padding on a scroller does that at rest and only at rest: padding is INSIDE the scrollport, so
  the moment the column moves the cards ride up through it. That is not a corner case here, it is
  the main case — an "↑ 11 above" chip exists *because* the column is scrolled, so the one state
  where padding protects nothing is the only state the chip appears in. A border is outside the
  scrollport and content can never be painted in it at any offset. The corollary is the half that
  makes it safe: `box-sizing: border-box` means a border does not change the element's BORDER BOX,
  and the wire clamp band is measured from `getBoundingClientRect` — so 30px of border moved every
  card and not one wire, and `maxErr` was 0 before and after without a single coordinate being
  re-derived. **When you must reserve space inside a scroller, ask which box the reservation lives
  in before choosing the property.**
- MJ37 (J7): **a placement that depends on what it displaces will oscillate, so the reservation
  has to be unconditional.** The tempting version of MJ36 is a `.has-dock-up` class that grows the
  strip only when there is a chip. Follow it round: the strip appears → every card moves 30px down
  → the card whose centre was just above the band is now just inside it → it stops being docked →
  the chip's count drops, possibly to zero → the strip goes → the cards move back. Two frames, a
  new signature each time, forever, on a scroll handler. The same shape as MJ27's replayed
  one-shot, in geometry rather than in state. **A layout that is a function of its own output is
  a loop; pay the fixed cost instead.** (60px of column height here, and no jolt when a filter
  changes either — which is a second win nobody asked for.)
- MJ38 (J7, testing): **the sweep's clip box was a NAME, and the name was of the wrong element —
  so it invented eleven defects in the same run it was fixed to find one.** MJ7 says "compare each
  card's rect intersected with the clip box" and names `.mc-board`. `.mc-board` does not clip a
  card: `.mc-col-body` does, and its scrollport is its PADDING box. So a card at either end of a
  scrolled column reports a layout rect running past where it is painted, and the first corrected
  run reported the column's own filter chips, the "N wires hidden" row and the dock chips all
  "overlapping" cards that are invisible where they were said to collide. J7's 30px strip is a
  BORDER, which widens that gap to exactly the band the chips live in — so a border-box sweep would
  have reported every chip as covering a card forever, and a phase that trusted it would have
  "fixed" a working board. `clip()` now DERIVES the box: walk the ancestors, intersect with the
  padding box of each one that is not `overflow: visible`. **A clip box is a property of the
  element, never a selector you remember** — and MJ7's own disproof (`elementFromPoint` at the
  chip's centre) is kept as a positive assertion beside the rects, because the two disagreeing is
  the signal that the arithmetic is wrong.
- MJ39 (J7): **`_sig` decides what a human is allowed to see move, and a coordinate left out of it
  is a coordinate that goes stale silently.** The recompute writes `ui.docks` only when its
  signature changes, and the signature carried each chip's key, count and filtered count — not its
  x/y. So a pure LAYOUT shift repositioned nothing: turning a filter on grows the column head by
  the "N wires hidden by this filter" row, moves the body 31px down, and the chip stayed where the
  previous layout had put it (483.6px against a true 514.4px, measured live). It is a nasty bug to
  meet because it makes the real defect INTERMITTENT — the first probe of the owner's exact state
  showed the chip 1px clear of the card and passing, and only forcing a fresh recompute put it back
  on top. **A memo-guard is a claim about what can change; anything you place with a number has to
  be in it.** Rounded to integers so sub-pixel jitter cannot start a render loop.
- MJ40 (J7): **MF13's real subject was never the hover verbs — it is any fixed-width neighbour on
  the name's line, and the biggest one shipped two programmes later.** MF13 (three hover buttons)
  and MF26 (the same three, floated) were both diagnosed as affordance problems. D2 is the same
  failure with no affordance in it at all: SOURCING S4's `.mc-src` source pill — 142px,
  `flex-shrink: 0`, `white-space: nowrap` — sits in `.mc-item-label` beside the name, on a 252px
  row, and left the name 104px. Twenty-three of seventy-three cards on the owner's board were
  ellipsised by a chip that was itself perfectly correct. The fix is not a width negotiation but
  `flex-wrap: wrap`, because flex wraps on BASE sizes BEFORE it shrinks anything: the name keeps
  the whole row and the pill takes the next line, and a card whose name was always short does not
  grow at all. **State the rule as "nothing of fixed width shares the name's line unless both
  fit", not as "affordances go out of the flow"** — and note that `overflow-wrap: anywhere` would
  quietly undo it by feeding min-content, which is MF13's one-character label arriving by a new
  road.

- MJ41 (J8): **the defect was one pixel, and the pixel it was in belonged to a SCROLLBAR — which
  is not an element, so nothing this codebase measures could ever have seen it.** An arrowhead is
  a triangle spanning `ANCHOR_GAP` (4) to `ANCHOR_GAP + HEAD` (15) from a card's edge, and
  `.mc-col-body` reserved **14px** of padding for it. That is not a rounding error, it is a
  constant in a stylesheet that had to agree with a constant in a pure kernel and had no way to,
  and for the whole life of the board it has been one short. The sixteenth pixel is the column's
  scrollbar gutter: `.mc-cols` is `z-index: 2` and `.mc-wires` is `1`, so the head is drawn
  UNDER the scrollbar, and what it loses is the flat BASE of the triangle — the widest and most
  recognisable part, which is why a 1px geometric overlap reads on screen as a head chopped in
  half. Measured live on abm at 1440: layout box 375→386, painted pixels stopped at 384.
  Two things this taught. (a) **`overflow: clip` was the obvious suspect and was innocent** —
  `scrollbar-width: none` made the head whole instantly, which is a ten-second experiment that
  settles occlusion-versus-clipping and should be the first move every time. (b) A bounding-box
  sweep cannot find it, because a scrollbar has no rect to compare against and
  `elementFromPoint` in that band answers `.mc-col-body` whether or not the scrollbar is there.
  The gutter has to be DERIVED — `(paddingBoxWidth - clientWidth)` — and named as an opaque box
  in its own right. **When a layer paints over another, its opaque parts include things that are
  not elements.**
- MJ42 (J8, testing): **`node --check` on a `.js` file containing ES-module syntax exits 0
  without parsing it, so MJ19's "check the exit code" is satisfiable by a check that is not
  running.** MJ19's lesson was that `node --check "$f" | head -2` reports on `head`, not on the
  code. J8 fixed that — every file was checked by exit code — and every file passed, including
  one deliberately corrupted probe copy. Node 24 treats a `.js` file as CommonJS and, on this
  build, a top-level `import` makes `--check` return 0 for ANY content that follows. Copy the
  file to **`.mjs`** and it fails as it should. So the harness lied a second time, in the same
  place, in a new way — and the thing that caught it was, again, fetching the SERVED bundle and
  parsing that (MJ19's other half).
- MJ43 (J8): **a `//` comment inside an `import { … }` destructuring list kills the whole asset
  bundle, and only in the SERVED file.** Odoo's ES-module → `odoo.define` transform is textual;
  a comment between the braces makes it emit `require({)`, and the entire bundle then dies with
  `SyntaxError: Unexpected token ')'`. On the hoot runner that is a red banner and **zero tests
  executed** — not a failure list, a suite that never started. The source file is perfectly valid
  JavaScript and passes a real `.mjs` parse; the transform is what cannot read it. Same shape as
  MJ19 and MJ21: a syntax family your editor colours correctly and the pipeline does not. Put the
  comment ABOVE the `import`, never inside it — and after any change to an import list, parse the
  bundle the browser is actually served.

- MJ44 (J9): **turning a plain stored column into a COMPUTED stored one is a bet on a detail of
  `_auto_init`, and the cheap way to stop betting is a temporary table.** `source_binding` and its
  four siblings became `compute=` + `store=True` views of the new `hr.formula.rule.source` rows,
  and the post-migration seeds those rows FROM the columns. Whether Odoo flags an existing column
  for recomputation when its field gains a `compute` decides whether that post-migration reads
  thirteen bindings or thirteen nulls — and on a live database the wrong answer is silent, total
  and unrecoverable, because the recompute would have run before the migration that needed the old
  values. On this build it does not recompute (recomputation is flagged for columns that are NEW),
  which was verified after the fact and would have been worthless to verify before: the question is
  not "does it" but "what does it cost me to stop caring". A **pre-**migration `CREATE TABLE
  j9_binding_backup AS SELECT …` costs twenty lines, makes the post-migration independent of the
  columns it is about to rewrite, and makes it idempotent for free (`WHERE NOT EXISTS` on the copy,
  then `DROP TABLE`). It ran on abm as `preserved 13 → converted 13, skipped_non_input 0,
  realigned 0, cleared_unbacked 0`, and the `hr_formula_rule` fingerprint was byte-identical
  before and after. **When a migration's input is a thing the same upgrade might overwrite, copy it
  in a pre-script; do not reason about the ORM's order of operations.**
- MJ45 (J9): **the derived head of a plural field is not a substitute for its rows, and every guard
  written as `if x == 'excel'` stops seeing the state it was written for the moment a second row can
  outrank it.** `source_binding` now computes to the HIGHEST-RANKED source. Three guards read it and
  all three broke in the same way, only one of them loudly: `_source_conflicts` classified
  excel-versus-feed by `b_kind == 'excel'`, so the instant a component declared a feed beside its
  spreadsheet column the detector reported no conflict (caught by an existing test);
  `import_mapping_delete` cleared the spreadsheet binding only `if rule.source_binding == 'excel'`,
  so removing a spreadsheet wire from a feed-reading component would have taken the wire off the
  board and left the component still reading the column (caught only by writing the test);
  `api_mapping_snapshot` captured the undo binding by the same test, so cutting a `rule` wire off a
  component that also read a feed would have lost it (caught by neither — found by asking the
  question a third time). All three now ask `rule.source_ids.filtered(kind == …)`. **When a scalar
  becomes the first of a list, grep for every comparison against it and assume each one meant "is
  there one of these", not "is this the one".**
- MJ46 (J9, live): **`api_mapping_create` unlinks a rival on the SOURCE end as well as the target
  end, so a probe that draws a catalogue field onto a throwaway component deletes whatever that
  field was already wired to.** The J9 probe drew `Aadhaar_Number` onto `J9PROBE`; the create's
  `search(['&', connector, '|', source_field, target_rule_id]).unlink()` removed
  `hr.integration.field.mapping` **28**, a live `suggested` row, and the row count went 41 → 40 with
  nothing on screen saying so. MF37 caught it (the fingerprint moved) and **MJ35's method named the
  cause in one grep**: `odoo.models.unlink` showed the deletion timestamped 20ms BEFORE the
  `api_mapping_create` POST completed — so it was the create, not the mouse click that followed a
  minute later. It was rebuilt at its original id by `INSERT … SELECT` cloning sibling row 27
  (`UAN_Number`, the same template-derived shape) with the two text fields changed, and the
  fingerprint returned to `787b99f5…` exactly. Two lessons: **a throwaway RULE is not a throwaway
  GESTURE** — J8's `J8PROBE` convention protects the target end and says nothing about the source
  end, so pick a source field that is genuinely unused, or snapshot the row first; and **the log's
  timestamp is what distinguishes "my RPC did this" from "my click did this"** when both are in the
  same minute.
- MJ47 (J9, testing): **a source assertion that greps for a CHARACTER must strip comments first, or
  it fails on the prose that documents the rule it is enforcing.** J9 renders the source rank as a
  real `<sup>` element rather than `¹`, and the test that pins that greps the templates and the
  canvas for `¹²³`. It failed on the canvas — on a doc-comment reading *"Spreadsheet¹ · Contract
  component², never ²·³"*, which is exactly the sentence a reader needs and the only place those
  codepoints are correct. MJ25's family: a source assertion is a parser you wrote in a hurry, and
  the parse it most often gets wrong is "is this a string or a comment". Strip, then assert — and
  say in the test WHY comments are exempt, or the next phase will "fix" it by deleting the comment.

- MJ48 (J10, testing): **the sweep found two real overlaps and neither was mine, and the
  ten-second experiment that proved it is worth more than the finding.** Widening the sweep to
  states nobody had covered — both columns scrolled to the MIDDLE and to the END, and the
  `Employee & contract ⇆` board at 1024 — produced 2-4 overlaps where every prior phase reported
  zero. The phase had just added a second chip to fourteen more cards, which changes card height,
  which moves every wire endpoint, so "my chips did this" was the obvious reading and it was
  wrong. The disproof is one line of CSS: inject `.mc-src { display: none !important }`, fire a
  `resize`, re-sweep, remove it, re-sweep. Identical counts in all three passes (4 / 4 / 4)
  settles it in fifteen seconds, and on the `Employee & contract` board it settled it twice over —
  `document.querySelectorAll('.mc-src').length` is **0** there, so the board that overlapped has no
  source chips at all. The two families, recorded and NOT fixed (both are geometry this phase does
  not own): (a) `.mc-hub.suggested` confidence chips ("80%", "85%") pile on top of each other when
  both columns are scrolled far enough that many wires clamp into one band — `spreadHubs` spreads
  hubs along their own wire, not against each other; (b) the `.mc-gone` footer note ("20 mappings
  point at a field this source is not known to deliver.") wraps to a second line at 1024 and rides
  over the cards and dock chips above it. **Widening a regression sweep is worth doing for the
  defects nobody reported (MJ33) — and the first thing to establish about one is whether it is
  yours, with an experiment rather than an argument.**
- MJ49 (J10): **`False` is how Odoo spells NULL in a Char, a Date and a many2one, so MJ15's "`0`
  and `False` are real values" is a rule about a PAYLOAD and not about a COLUMN.** MJ15 is right
  and is restated as a non-goal in every handover since: a connector reporting zero overtime has
  answered the question, and only `None` or whitespace is silence. Applying the same test to a
  RECORD read inverts it. `getattr(employee, 'job_title')` on an empty field returns `False`, which
  is not "the record says false" but "there is nothing here" — and `False in (None, '')` is `False`,
  so the pre-existing `get_mapped_input_value` has always let it through. Consequence once the
  record became a ranked source: **every mapped component would report "the record already holds
  it"**, the tier below would never be reached, and the writeback would decline to write a field
  that was empty. The walk therefore applies its own emptiness rule at rank 4 — `False` is nothing
  unless the mapped field's `ttype` is `boolean`, which is the one case where it is an answer — and
  `get_mapped_input_value` itself is untouched, so the resolver is byte-identical. A test asserting
  "blank feed + blank record → the contract component wins" fails against correct-looking code
  until you notice the blank record is not blank. **When a sentinel crosses from a message into a
  column, re-derive what emptiness means on the other side.**
- MJ50 (J10): **a count in a handover is a query somebody wrote, and this one was missing a JOIN —
  render the real database before treating it as a gate.** §2.4 predicted abm would go from **1**
  card with two or more chips to **11**, with "if you measure 1 the early return is still there; if
  you measure 21 the fold has broken" as the diagnostic. The measurement was **2 → 16**, and both
  ends were wrong for reasons that are ordinary rather than careless. The BEFORE was 2 because
  `COSTCENTEFOR` carries an excel binding *and* `is_contract_component` — J9 recorded exactly one
  such component (`GASALLOWANCE`) and the owner has drawn another since, so a ledger figure about a
  set of rows aged out the moment somebody used the product. The AFTER was 16 because the
  handover's ten hidden destinations were derived from `hr_formula_rule_source` alone, and the
  studio's display side ALSO folds in the live connector wire (`_source_wire_dests`, S6): four more
  components — `EMPLOYEECODE`, `DATEOFJOININ`, `EMPSTATUS`, `LOCATION` — declare nothing but are
  wired and mapped, so they gain a second chip too. MJ29's lesson, one programme later: **a spec
  written against the code can still be silent about the state the data is actually in.** The safe
  move is to run the projection as SQL against the live database before starting, which cost ten
  minutes here and turned a "the fold has broken" panic into a footnote.
- MJ51 (J10, environment): **there are three copies of every module on this server and the one you
  rsync to is probably not the one that loads.** `addons_path=/odoo/odoo-server/addons,/odoo/custom/addons`,
  and there is a third at `/odoo/c6addons`. The first entry WINS. A deploy into `/odoo/custom/addons`
  alone completed with no error, logged `Loading module pb_formula_studio`, restarted the service
  cleanly, returned HTTP 303 — and ran the OLD code: `ir_module_module.latest_version` stayed at the
  previous number and the suite reported **515 tests, exactly the baseline**, with none of the
  forty-four new ones collected. Every signal except the version and the count said success. Two
  rules: rsync to **every** directory on `addons_path` that already holds the module (they were
  in sync before you arrived, and leaving them divergent is the next phase's mystery), and treat
  `latest_version` and the TEST COUNT as the deploy's only receipts — a version that did not move
  after `-u` means the upgrade you watched happened somewhere else.
- MJ52 (J10, testing): **hoot has no `toBeTruthy`, and an unknown matcher fails as "called once
  without calling any matchers" plus "1 unverified error".** `expect(x).toBeTruthy()` throws
  `expect(...).toBeTruthy is not a function`, and the report names neither the matcher nor the
  line — it says the expectation was never completed, which reads as a bug in the code under test.
  Use `expect(!!x).toBe(true)`. And the run's SUMMARY is only in the console
  (`[HOOT] Passed 141 tests (541 assertions…)`, a `dir` message): hoot tears its UI out of the DOM
  when it finishes, so `document.body.innerText` is empty and `document.title` carries only a ✔ or
  a ✖. Read the count from `list_console_messages`, last page, not from the page.
