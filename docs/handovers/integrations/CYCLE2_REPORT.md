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
| 6 | `<sample-fix>` | fix(pb_formula_studio): a wire drawn on the board remembers its sample |
| 7 | `<docs>` | docs: Cycle 2's ledger (W131–W136) + this report |

Nothing pushed. `.claude/settings.json`, `thaco/` and `ABM/` never staged.

## Deploy

| window | unit | EXIT | notes |
|---|---|---|---|
| main upgrade (designer-run, after my stall) | `i2fix` | **0** | 6 modules; service restarted, `/web/login` 200, `acme` 200 |
| scoped test run + `pb_import_kit` catch-up | `i2test` | n/a — ended by PID | tests PASSED (below); the process kept serving 8069 → **W131** |
| self-review fixes | `i2fix2` | **0** | `pb_formula_studio` 19.0.1.70.1, `pb_integrations` 19.0.1.4.1 |
| sample fix | `i2fix3` | *(pending)* | |

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
