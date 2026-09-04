# Integrations Cycle 2 — implementation report (the Mapping Studio)

> Written incrementally during the cycle. Read with
> `docs/handovers/integrations/CYCLE2_MAPPING_STUDIO.md` (the spec) open.

## Commits

| # | hash | what |
|---|---|---|
| 1 | `741f345c` | feat(pb_hr_payroll_formula): source-field discovery narrows to one feed |
| 2 | `c8f19083` | feat(pb_formula_studio): the Mapping Studio — FROM and TO, as a sentence |
| 3 | `e4a8421c` | feat(pb_settings\|pb_import_advanced\|pb_hub): the four doors into the studio |
| 4 | `d0e5d1f3` | feat(pb_integrations): the feed a mapping belongs to, and a count that opens |
| 5 | `16cdb38b` | fix(pb_formula_studio): an arrival id is asked politely, and Suggest only offers |
| 6 | `3ba96e59` | fix(pb_formula_studio): a wire drawn on the board remembers its sample |
| 7 | `fcafda54` | fix(pb_formula_studio): the picker opens below what it is changing |
| 8 | `0bb66ac0` | fix(pb_formula_studio): a connector link lands on the scheme it actually feeds |
| 9 | `98feeb22` | docs(integrations): Cycle 2 report — evidence through test 9f |
| 10 | *(this commit)* | docs: Integrations Cycle 2's ledger — W131-W136, and the report |

Nothing pushed. `.claude/settings.json`, `thaco/` and `ABM/` never staged.

## Deploy

| window | unit | EXIT | notes |
|---|---|---|---|
| main upgrade (designer-run, after my stall) | `i2fix` | **0** | 6 modules; service restarted, `/web/login` 200, `acme` 200 |
| scoped test run + `pb_import_kit` catch-up | `i2test` | n/a — ended by PID | tests PASSED (below); the process kept serving 8069 → **W131** |
| self-review fixes | `i2fix2` | **0** | `pb_formula_studio` 19.0.1.70.1, `pb_integrations` 19.0.1.4.1 |
| sample fix + picker polish | `i2fix3` | **0** | `pb_formula_studio` 19.0.1.70.3 |
| resolver fix | `i2fix4` | **0** | `pb_formula_studio` **19.0.1.70.4** — the live version |

`i2fix3` and `i2fix4` used the **stall-proof** pattern adopted mid-cycle (W136):
the unit itself stops the service, polls for zero `odoo-bin`, upgrades, records
`EXIT=$?`, and starts the service again — so an operator-side stall can never
leave the site down. Both windows ended with `payobook` and `acme` at 200.

Final live versions, all equal to the repo: `pb_formula_studio` 19.0.1.70.4,
`pb_integrations` 19.0.1.4.1, `pb_import_kit` 19.0.1.5.0, `pb_hr_payroll_formula`
19.0.1.50.0, `pb_settings` 19.0.1.2.0, `pb_import_advanced` 19.0.1.3.0,
`pb_hub` 19.0.1.3.0.

`pb_import_kit` had been left out of the designer's `-u` list (its only change was
the `gitMerge` icon + a version bump), so the DB lagged the disk at 19.0.1.4.0
against 19.0.1.5.0. Closed in the `i2test` window; all seven modules now report
repo versions in `ir_module_module`.

## Test suites (handover test 8)

One scoped run, `-u pb_import_kit,pb_hr_payroll_formula,pb_formula_studio,pb_settings,pb_import_advanced,pb_hub,pb_integrations`
with `--test-tags /pb_formula_studio,/pb_hr_payroll_formula,/pb_integrations,/pb_settings,/pb_import_advanced`:

```
pb_formula_studio:     13 tests  1.10s   742 queries
pb_hr_payroll_formula: 17 tests  0.92s   666 queries
pb_import_advanced:    13 tests  1.57s  1045 queries
pb_integrations:       41 tests  0.49s   276 queries
pb_settings:           25 tests  0.12s   153 queries
0 failed, 0 error(s) of 85 tests when loading database 'payobook'
```

Cycle 1's baseline on the same scoping was `0 failed, 0 error(s) of 71 tests`.
The two known pre-existing failures (`pb_timeoff` test_05, `pb_today` hex) are in
modules outside this scoping and did not run — not fixed, per the non-goal.

## Numbered tests 1–6 (server contract)

Gated by `pb_formula_studio/tests/test_mapping_studio.py` (13 tests), all green in
the run above.

1. **Pickers RPC** — `mapping_pickers()` returns readable connectors with their
   feeds and configs with column counts. **Scope semantics: `search([])`**, i.e.
   exactly `pb.integrations._readable_connectors`' answer — the record rules make
   the decision and the method does not catch an AccessError into a
   plausible-looking empty list. Asserted by comparing the payload's connector
   ids against `self.Conn.search([]).ids`.
   Also gated: arrival resolution (1b), a feed belonging to another connector
   refused (1c), and six shapes of junk in the context answered rather than
   raised (1d).
2. **Endpoint filter** — `api_mapping_data(cfg, conn, endpoint_id)` returns only
   that feed's fields; a legacy NULL-endpoint mapping survives and its source
   appears under an `Unassigned` group header; `api_mapping_create` stamps
   `endpoint_id`, and refuses an id naming another connector's feed (2b).
3. **Sample values** — present where payloads exist; an empty feed on a
   connector that has rows returns `[]` rather than the `hr.employee` schema; a
   connector with no rows still offers the employee schema. `_sample_text`
   trims, JSON-encodes structures, and keeps `0` (3b).
4. **Config switching** — two configs on one connector return disjoint wire
   sets; creating on B does not leak to A.
5. **Transform round-trip** — preview writes nothing, `divide/3600` persists,
   and `python` is refused with the record unchanged.
6. **Template apply** — the `{applied, skipped_existing, unmatched_sources,
   unmatched_targets}` shape on the studio's own path (with a connector, which
   the overlay never passed); a hand-drawn wire and its transform survive.
7. **Doors** — `pb_integrations/tests/test_one_door.py` +3 tests; `pb_settings`
   suite amended (2-card category asserted, single-card rule asserted still
   generic).

## Chrome-MCP live validation (handover tests 9–10)

Environment: W130 applied in full — the shared `chrome-devtools-mcp` profile was
held by another session ("The browser is already running for
…/chrome-profile"), so this session drove **its own Chrome over CDP** with
`--headless=new --remote-allow-origins=*` and a private `--user-data-dir`.
Driver in the session scratchpad (`cdp.mjs` / `pb.mjs`), not in the repo.

Persona: W129 applied — `ash@biztinct.com/admin1234` is stale, so a **temporary
single-company system user** was minted through `odoo-bin shell`
(`ig-c2-validator@payobook.local`, uid **2085**, company 5 only, groups
`base.group_system` + `base.group_user` + formula manager/admin) and removed at
the end of the pass. `company_ids` and `company_id` written in the same `write`.
Authentication via `/web/session/authenticate` (W130's corollary).

Backend prefix is `/bizapp` (`biz_deroute`); `/odoo` 301s to it.

*(evidence appended below as each test lands)*

### 9a — Settings → Integrations → Mapping Studio ✅
Two clicks from the Settings hub. The Integrations category now renders a
**section page with two cards** ("Integrations", "Mapping Studio") — Cycle 1's
single-card auto-open self-retired exactly as designed, with `soleCard`
unedited. Studio mounts; back chip reads **"Settings"**.
Screenshots: `03-settings-integrations-two-cards.png`, `04-studio-story-bar.png`.

Story bar on arrival:
`FROM · ADP Workforce Now · 20 fields · [All feeds] ══ 0 mapped ══▶ TO · Payobook Retail — End-Month Payroll · 10 input columns · VN · active`
20 left items, **20 of 20 carrying a sample line**, 10 right items. Five
plain-language modes, "System fields → Scheme" active.

### 9b — FROM picker: connector and feed ✅
Connector dropdown: 26 options, each with a status dot and a status line
(`"BambooHR — 3 feeds · 5 mappings · synced 6h ago"`,
`"Excel Workbook — 2 feeds · 4 mappings · never synced"`). Switching to BambooHR
reloads the left column. Feed dropdown then offers `All feeds` + 3 feeds;
picking "Dependents / Family" narrows the board 20 → **3 fields**, the FROM
sub-line becomes `3 fields · synced 6h ago`, and the left column grows the
group header `DEPENDENTS / FAMILY`.
Screenshots: `06-from-picker-connectors.png`, `08-feed-picker.png`, `09-feed-scoped.png`.

### 9c — TO picker: change the payroll template ✅
Two clicks total (open the picker, pick) — the picker is the single affordance
the handover asked for. 15 configs, each with `N columns · M inputs · country`.
Switching to **"Payobook Scale Demo — 250 Columns"** reloads the right column
and the wires. The longest realistic name renders in full without breaking the
story bar (self-review point 3).
Screenshots: `10-to-picker-configs.png`, `11-config-switched.png`.

### 9d — draw, transform, preview, delete
Drawing works: arming a left card raises the draw hint, clicking a right card
creates the wire, the bezier paints, the count moves to **"1 mapped"**, and the
first-run strip disappears. The transform popover offers exactly the eight
whitelisted operations — **`python` is absent from the UI as well as from the
server** (W12 proven at both ends).
Screenshots: `12-armed-drawhint.png`, `13-wire-drawn.png`, `14-transform-popover.png`.

**Defect found and fixed in this cycle** — see "Sample on create" below.

**Sample on create (defect found live, fixed — `3ba96e59`).** Every left card
prints its sample, but `api_mapping_create` discarded it, so the transform
popover on a freshly drawn wire answered "No sample value stored" about a field
whose sample was on screen beside it. The create now stamps
`source_sample_value` and `source_data_type` from the discovered field, mapped
through an explicit table (the store infers `list` and the mapping field has no
such value; `source_data_type` decides whether the preview parses as float, so a
guess there is a preview that disagrees with sync). Re-verified live:

```
DREW  external_id (sample 5)  →  Basic Salary
PREVIEW direct : =      5 → 5
PREVIEW ÷3600  : ÷3600  5 → 0.001388888888888889
SAVED  glyph   : ÷3600            DELETED → 0 wires, "0 mapped"
```
Screenshots: `15-transform-live-preview.png`, `16-transform-saved.png`.

The transform popover offers **exactly eight operations and `python` is not one
of them** — W12 proven at the UI as well as the RPC.

### 9e — auto-suggest, dashed wires, confidence, Accept-all ✅
The API adapter has no name matches in this demo world (probed 6 configs × 10
connectors → 0 suggestions; the demo's source paths are `bank_account`,
`department`… and the scheme's input codes are `BASIC`, `OTWD`… — no overlap),
so this was validated on the **cycle** adapter, which has a real generating
engine. Mode "Mid ↔ End cycle", scheme "Payobook Construction — Mid-Month
Advance":

* before: 53 left, 50 right, 1 wire;
* "Suggest mappings" → **49 dashed `suggested` wires, 49 confidence chips, all
  100%**, header reads `1 mapped · 49 suggested`;
* "Accept all ≥90%" → 50 solid wires, 0 dashed, header `50 mapped`.

Screenshots: `17-cycle-mode.png`, `18-cycle-pair.png`, `19-suggestions-dashed.png`, `20-accept-all.png`.
**Reverted:** the 49 `hr.payroll.cycle.component.mapping` rows the pass created
were deleted through the studio's own `mapping_delete` RPC (49 of 49); the pair
is back to its original single mapping.

The FROM/TO grammar survives the mode swap:
`FROM · Payobook Construction — Mid-Month Advance · Mid-cycle configuration ══▶ TO · … End-Month Payroll · End-cycle configuration`,
with the scheme picker present as a chip beside the modes (the design's rule:
the scheme is always one click away, even in the modes where it is not half of
the sentence).

### 9f — connector cockpit → "Map fields" ✅
Feed buttons are now `Sync · View data · Map fields`; the header gained
`Open Mapping Studio`. Clicking "Map fields" on the **Employee Master Data**
feed lands:
`FROM · ADP Workforce Now · 20 fields · synced 7h ago · [Employee Master Data] ══ 0 mapped ══▶ TO · Payobook Retail — End-Month Payroll`
— connector, feed and mode all preset, back chip **"ADP Workforce Now"**.
Screenshots: `22-cockpit-map-fields.png`, `23-mapfields-preconfigured.png`.

### WP-4 — the board count is a door ✅
All 26 connector cards render the mappings count as a link
(`6 mappings · 2 feeds · 16 staged · 5 synced`). Clicking it opens the studio on
that connector; back chip "Integrations" returns to the board.
Screenshots: `21-board-maplink.png`, `24-count-is-a-door.png`.

**Second defect found here, fixed — `0bb66ac0`.** The door landed on the DEFAULT
scheme, so clicking "6 mappings" produced a story bar reading **0 mapped** — the
board and the studio contradicting each other on the click that joins them. The
handover had specified "the config with most mappings for it" and the first
implementation shipped the plain default. `_config_for_connector` now resolves
it (ties → lowest id, so the answer is stable), with explicit `pb_config` still
winning over the derived one — that precedence is now asserted, not commented.

### 9g — the Formula Studio overlay still works, and graduates ✅
The overlay opens from the Studio toolbar unchanged: five tabs, cycle canvas
56 left / 53 right / 1 wire. Its header gained one quiet
**"Open in Mapping Studio"** button beside "Auto-suggest". Clicking it lands the
studio with the configuration preset and a back chip reading **"Formula
Studio"**.

This screen is also where **W134** was confirmed live: switching the overlay to
its API tab now shows **20 left items with 20 sample lines**. Nobody asked for
that. It follows from `api_mapping_data` — a SHARED adapter — gaining a `sample`
key, which both hosts of `MappingCanvas` render. It is an improvement and it is
recorded rather than discovered later by someone diffing the studio.
Screenshots: `26-overlay-still-works.png`, `27-overlay-api-tab.png`, `28-graduated-to-studio.png`.

### 9h — the ⌘K palette entry ⚠️ ENTRY PRESENT, NOT LANDED
The palette opens on **⌘K** (Meta; `control+k` in Odoo's hotkey vocabulary maps
to ⌘ on macOS — Ctrl did not open it) and is `.pbhub-pal-*`, not Odoo's
`.o_command_palette`. Typing "Mapping" returned **"Nothing matches that."**

**This is not specific to the new entry.** "Integrations" — shipped in an
earlier cycle, gated on the *identical* group array
`[INTEGRATION, MANAGER, SUPER]` — is equally absent, as are "Formula Engine"
and the rest of the gated 2000-block deep links, while an ungated entry
("Government Reports") resolves and renders normally. Reproduced on two
personas: the temporary system user (server-side confirmed to hold *Payroll
Manager*, *Payroll Integration User*, *Formula Manager*, *Formula
Administrator*, *Administrator*) and `demo@payobook.com`.

So: the entry is committed and correctly gated (it mirrors its neighbour by
construction), but **I could not land it from the palette**, and the reason
appears to be a pre-existing `pb_hub` palette group-resolution behaviour that
predates this cycle. I did not chase it — it is outside Cycle 2's scope and
fixing `pb_hub`'s gating blind would have been the rabbit hole. **Recommended as
a Cycle 3 opener**, with the diagnostic above as the starting point.

### 9i — read-only persona, and how `canEdit` is derived ✅
`demo@payobook.com` could not serve this test: on this database that persona
lands in the Learning journey and never reaches the action. So a **second**
temporary single-company user was minted (`ig-c2-readonly@payobook.local`, uid
2086) holding `base.group_user` + `pb_hr_payroll_formula.group_formula_user` +
`pb_hr_payroll_base.group_payroll_base_user` — a genuine read-only payroll
persona. Shell-verified before the browser ran:
`is_system False · formula_mgr False · formula_user True · CAN_EDIT False`.

**How `canEdit` is derived:** the client reads `state.data.can_edit`, which is
`pb.formula.studio._can_edit()` on every adapter payload —
`base.group_system OR pb_hr_payroll_formula.group_formula_manager`, failing
OPEN on exception so a missing group never locks an admin out. That is the
*same function* the Formula Studio overlay gates on; the studio adds no second
notion of permission.

Observed for that persona:

| affordance | result |
|---|---|
| story bar, 20 left items, 10 right items | **visible** (read access preserved) |
| mode-bar buttons (Suggest / Apply template) | **0** |
| first-run action buttons | **0** |
| wire delete / accept badges | **0** |
| draw hint after arming a source | **0 — arming refused** |
| wires before → after clicking a target | **0 → 0** |
| forged `api_mapping_create` over raw RPC | **`{"ok": false, "msg": "No permission."}`** |

The last row is the one that matters: the gate is server-side, and bypassing the
client buys nothing. Screenshot: `33-readonly-persona.png`.

### 9j — console and network health ✅
Final sweep, four surfaces, freshly loaded:

```
settings       | console errors: 0 | >=400: 0
integrations   | console errors: 0 | >=400: 0
studio         | console errors: 0 | >=400: 0
formula        | console errors: 0 | >=400: 0
```

**Clean across all four surfaces.** Two things were excluded from the count and
both are named rather than hidden: `payroll.ai.conversation.rpc_get_history`
("Load history error"), which belongs to `pb_payroll_ai_insights` — a module
this cycle never touched — and a `handleBarcode` TypeError provoked by my own
synthetic CDP keystrokes, which is an artefact of the harness and not of the
product.

### Test 10 — the confused-user walkthrough: **6 clicks** ✅

Cold start at the Settings hub. FROM and TO are legible in **every frame from
click 2 onward**; frames 0–1 are the Settings hub itself, which correctly has no
story bar.

| click | state | FROM → TO on screen |
|---|---|---|
| 0 | Settings hub | *(no story bar yet)* |
| 1 | Integrations — **two cards** | *(no story bar yet)* |
| 2 | Mapping Studio open | ADP Workforce Now · 20 fields · All feeds — **0 mapped** → Payobook Retail — End-Month Payroll · 10 input columns · VN · active |
| 3 | source armed | …unchanged, **0 mapped** |
| 4 | **wire drawn** | …**1 mapped** |
| 5 | transform popover open, **previewing live** | …1 mapped |
| 6 | **operation chosen, preview recomputed** | …1 mapped |

Live preview at click 5: `=  5678901234567 → 5678901234567`.
At click 6: `×1  5678901234567 → 5678901234567`.

**Total: 6 clicks** from Settings to a drawn, transformed, previewed mapping —
at the handover's ≤6 budget. Persisting it (the Save button) would be a 7th;
the handover asked for "previewed", which is complete at 6 because the popover
previews before it saves.

Screenshots `T10-00-settings-hub.png` … `T10-06-transformed-and-previewed.png`.
The wire the walkthrough created was deleted afterwards; the board is back to 0.

## Live state left behind

* Both temporary users removed in the same session (W129) —
  `REMAINING ig-c2: 0`.
* The 49 cycle mappings created by test 9e's Accept-all were reverted through
  `mapping_delete` (49 of 49); the Construction pair is back to its original
  single mapping.
* The wires drawn by tests 9d and 10 were deleted.
* `payobook` and `acme` both 200; service active; no `-u` pending.

## Self-review (against the handover's four checks)

1. **The overlay's five adapters at the RPC contract level.** `api_mapping_data`
   and `api_mapping_create` each gained ONE optional trailing argument;
   `import_`, `scheme_`, `employee_` and the cycle adapter are untouched.
   `test_07` asserts all five still return `{ok, left, right, wires, can_edit}`
   (or `{ok: False, reason}`), which is the shape the canvas mounts on and the
   failure no other python test would see. Verified live in 9g: the overlay
   opens and all five tabs work.
2. **No client path to a `python` transform.** `api_transform_save`'s whitelist
   is unchanged and the studio calls that same RPC. Proven twice: `test_05`
   asks for `python` and is refused with the record unchanged, and the live
   popover offers exactly eight operations with `python` absent.
3. **The story bar under stress.** The 250-column config name
   ("Payobook Scale Demo — 250 Columns") renders in full without breaking the
   bar; never-synced endpoints read "never synced" (Excel Workbook, Microsoft
   Dynamics 365) rather than a NaN or a blank.
4. **Arrival precedence.** Explicit > derived > default, asserted in
   `test_01e`, and anything unhonoured is REPORTED through
   `defaults.fell_back` and raised as a warning toast. `test_01d` covers junk
   in the context (six shapes) answering rather than raising.

## Final RPC signatures

```python
pb.formula.studio.mapping_pickers(arrival=None)
  arrival -> {connector_id, endpoint_id, config_id}   (all optional, all coerced)
  returns -> {ok, connectors[{id,name,type,status,mapping_count,last_sync,
                              endpoints[{id,name,code,data_type,data_type_label,
                                         mapping_count,staged,synced,last_sync,status}]}],
              configs[{id,name,code,country,state,active,column_count,input_count}],
              batches[{id,name}],
              defaults: {connector_id, endpoint_id, config_id, fell_back[]},
              can_edit}

pb.formula.studio.api_mapping_data(config_id=None, connector_id=None, endpoint_id=None)
  returns -> ...as before, plus endpoints[] and endpoint_id;
             left items gain `sample` and `group`

pb.formula.studio.api_mapping_create(config_id, connector_id, source_field,
                                     target_rule_id, endpoint_id=None)

# internal, used by the resolver
pb.formula.studio._config_for_connector(connector_id) -> int
pb.formula.studio._discovered_sample(conn, path, endpoint=None) -> dict
pb.formula.studio._as_id(value) -> int
pb.formula.studio._sample_text(value) -> str

hr.integration.field.mapping.get_available_source_fields(connector_id, data_type=None)
```

## Deviations from the handover, with reasoning

1. **`MappingCanvas` is not byte-untouched.** WP-1 said reuse it untouched;
   WP-2 said its left payload gains a `sample`. Both cannot hold — a sample
   nothing renders is not a feature. Resolved with two OPT-IN keys (`sample`,
   `group`) that render only when present, so every other adapter is
   pixel-identical. Consequence recorded as **W134** and confirmed live in 9g:
   the Formula Studio overlay's API tab shows samples now too.
2. **The feed picker shows counts, not a field count.** The design sketch wanted
   "200 fields" per endpoint option. Computing that means flattening every
   feed's payloads for every connector in the dropdown — the N+1 the same
   paragraph forbids. The options carry `data type · N mapped · when` instead,
   and the true field count appears in the FROM sub-line and the column header
   the moment a feed is selected, where it is one query.
3. **"Suggest mappings" renders on three modes, not five.** `scheme` and
   `employee` have no matching notion, so the button's only honest answer there
   was "nothing found" (W64). Shipped in `16cdb38b`.
4. **Test 9e was validated on the cycle adapter, not the API adapter.** The demo
   world has no name overlap between source paths and input codes (probed 6
   configs × 10 connectors → 0 suggestions), so the API board legitimately has
   nothing to suggest. The cycle adapter has a real generating engine and
   exercised the same UI contract: dashed wires, confidence chips, Accept-all
   ≥90%.
5. **Test 9h could not be landed** — see 9h above. Entry shipped and gated;
   palette group-resolution looks pre-existing and is proposed as a Cycle 3
   opener.
6. **Two defects found live and fixed in-cycle** rather than deferred, because
   both were inside this cycle's own seam: the missing sample on create
   (`3ba96e59`) and the connector-link resolver the handover had specified and
   I had not implemented (`0bb66ac0`).

## Known, NOT fixed — for Cycle 3

* **A connector's mapping count and the studio's can legitimately differ, and
  nothing says so.** The demo connectors' `hr.integration.field.mapping` rows
  have **no `target_rule_id` at all** (verified in SQL: all six ADP rows have a
  NULL target), so the board's "6 mappings" can never appear on any scheme's
  board — the studio correctly shows "0 mapped" and the two numbers look like a
  contradiction. `_config_for_connector` is right and simply has no data to work
  with here. The honest fix is a quiet line in the studio ("N mappings on this
  connector are not wired to a scheme yet"), which is small but needed a payload
  key, a template line, a test and a fifth deploy window; Cycle 3 is where those
  vendor mappings get wired anyway.
* **`preview_transform` leaks raw Python exception text** to the popover
  ("unsupported operand type(s) for /: 'str' and 'int'" when dividing a text
  field). Pre-existing, shipped before this cycle, correct in substance and
  user-hostile in wording.
* **The ⌘K palette's gated deep links** (see 9h).

## New W-rules

**W131–W136**, appended to `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` in this
commit:

* **W131** — a `--test-enable` run binds `http_port` for HttpCase, keeps serving
  after the tests pass, and `--stop-after-init` does not end it; with the real
  service stopped, nginx routes PRODUCTION traffic into the test process. Found
  live: the run logged `0 failed, 0 error(s) of 85 tests` and one second later
  was answering `/websocket` and `call_kw` for `payobook` **and** `abm` from the
  same pid, with `PoolError` tracebacks beside them. Ended by PID.
* **W132** — `odoo-bin`'s logger does not write to stdout when the conf sets
  `logfile`, so a sentinel that captures stdout captures docutils warnings and
  nothing else. The verdict lives in `odoo.tests.result` in the configured log —
  and needs `grep -a`, because that log has binary in it.
* **W133** — `systemd-run --property=Type=oneshot` BLOCKS the caller;
  `--no-block` is what makes the detached deploy detached. This was the cause of
  the cycle's first stall.
* **W134** — "reuse it untouched" and "its payload gains a field" cannot both
  hold; the resolution is an opt-in key, and its effect is visible in EVERY host
  of that adapter.
* **W135** — narrowing a discovery function must not inherit the unfiltered
  fallback, or an empty feed answers with another API's schema, stated
  confidently.
* **W136** — the deploy unit owns the WHOLE window (stop → poll → upgrade →
  `EXIT=$?` → start), so an operator-side stall can never leave the site down.
  Adopted mid-cycle after two stalls and used for `i2fix3` and `i2fix4`.
