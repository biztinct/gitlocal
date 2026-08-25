# JOURNEY — one mapping home, the Excel on-ramp, honest two-way sourcing, the Journey view

**STATUS: IN FLIGHT — designed 2026-08-25. J1 delivered 2026-08-25; J2 next.**

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
- Known holes (programme targets): Excel board header source = existing batch only
  (`_import_batch_columns` `pb_formula_studio.py:5404`, free-typed fallback `:5504-5508` — its
  docstring says it has never written a value in production); `generate_template`
  (`integrations/excel_connector.py:575`) has zero callers; `source_type='connector'` has no loader
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
