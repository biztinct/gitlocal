# Integrations Program — Cycle 6: the fields a source is *expected* to deliver (and a header you can see)

> STATUS: FINAL. Verified facts below — do not re-derive. Conventions binding through **W150**; prior reports `CYCLE2_REPORT.md`, `CYCLE4_REPORT.md`, `CYCLE5_REPORT.md`.

Two owner asks from the live abm board (2026-08-21).

## Ask 1 — a never-synced connector must show the fields it is EXPECTED to deliver, not Odoo's internals

**The evidence, verified.** `hr.integration.field.mapping.get_available_source_fields(connector_id, data_type=None)` (`pb_hr_payroll_formula/models/integration_field_mapping.py:445`) flattens the connector's most recent stored payloads; its own docstring (`:447-448`) says it *"Falls back to hr.employee's own fields (ir.model.fields) when nothing is stored yet"* — `_odoo_source_fields()` (`:529-533`), returned at `:489-490`.

On abm the Zoho People (ABM) connector has **0 `hr.api.data.store` rows** (verified by query — it is disconnected by design, per the owner's Cycle-4 ruling). So the studio's FROM column lists **206 Odoo employee fields** — `account_number`, `active`, `activity_calendar_event_id`, `activity_exception_decoration` — presented under the heading "FROM — ZOHO PEOPLE (ABM)". The user believes they are mapping Zoho; they are looking at Odoo internals.

Worse, it makes correct data look broken: Cycle 4 seeded **15 mappings whose `source_field` values are genuine Zoho keys** (`EmployeeID`, `Dateofjoining`, `Nick_Name`, `Full_Name_Vietnamese`, `Employeestatus`, `LocationName`, …). None appear in the Odoo fallback, so Cycle 5's honesty line reports *"15 mappings point at a field this source no longer delivers"* — accurate about the discovery list, misleading about the mappings, which are right.

**The fix: layered discovery with visible provenance.**

### WP-1 — the catalog-field layer (new)
New model **`hr.integration.endpoint.field`** — the fields a feed is known to deliver — plus **`hr.integration.endpoint.field.template`** (vendor catalog, data-XML seeded), cloning exactly the shape Cycle 1 established for `hr.integration.endpoint(.template)` (`pb_hr_payroll_formula/models/integration_endpoint.py`) — same create-only sync semantics, same ACL shape (user=read, admin=CRUD), same `is_legacy_abm` flagging convention.

Fields: `endpoint_id` (M2o, cascade) / `connector_type`+`endpoint_code` on the template side, `path` (the dot-path used as `source_field` — this is the join key to mappings), `label`, `data_type` (reuse the shared `api_data_store.DATA_TYPES` vocabulary for the feed; field-level type reuses `hr.integration.field.mapping.source_data_type`'s selection), `sample_value` (Char — so the studio can show a sample before any sync), `is_required`, `notes`, `sequence`, `active`.

**Seed data** (`data/integration_endpoint_fields.xml`, noupdate — W13.1 discipline, proof-read before deploy):
- Zoho `zohoemployees`: every `source_path` already shipped in `data/mapping_templates.xml` for connector_type `zoho` (31 rows, endpoint-stamped in Cycle 3) **plus** the legacy-ABM employee keys tabulated in `CYCLE3_ZOHO_CATALOG.md` §3.1 (`FirstName`, `LastName`, `Nick_Name`, `Full_Name_Vietnamese`, `EmailID`, `Department`, `Designation`, `Employeestatus`, `Employee_type`, `LocationName`, `Pan_Number`, `PIT_Number`, `UAN_Number`, `Aadhaar_Number`, `Bank_Name`, `Bank_Account_Number_VND`, `Insurance_Book_Number`, `Zoho_ID`, `Gender`, `Date_of_birth`, `Dateofjoining`, `Mobile`, `EmployeeID`), de-duplicated by path.
- Zoho `zohoattsummary`: `emailId`, `employeeId`, `expectedWorkingHours` (seconds), `totalWorkedHours` (seconds), `paidLeaveHours` (`"H:MM"`), `date` — with the unit noted in `notes`, since Cycle 3's transforms depend on it.
- Zoho `zohoovertime`: `OT_Type`, `ApprovalStatus`, `Actual_Pay_Hour`, `OT_Date`, `EMPLOYEEMAILALIAS`.
- Zoho `zoholeave` / `zohosalary`: the keys the modern connector reads (`pb_hr_payroll_formula/integrations/zoho_connector.py` — `_parse_employee_record` :341-356 and the salary/leave paths).
- Darwin parity: the keys `_parse_employee` / `_parse_salary` coalesce (`integrations/darwin_connector.py:194-238`).
Instantiate per connector through the SAME hook Cycle 1/3 use for endpoints and rule templates (create-only, by `(endpoint_id, path)`).

### WP-2 — layered discovery, with provenance the UI can show
Rework `get_available_source_fields` into an ordered merge, **keeping its existing signature and return shape plus one new key per item, `provenance`**:
1. **`live`** — flattened from `hr.api.data.store` payloads (today's primary path, unchanged, still `data_type`-filtered per Cycle 3).
2. **`catalog`** — `hr.integration.endpoint.field` rows for the connector's feed(s) that live discovery did not already yield.
3. **`odoo`** — `_odoo_source_fields()` **only when both above are empty**, and it must be *labelled* as such, never presented as the source system's own schema.
Merge key is the dot-path. Live wins on conflict (a live field carries a real sample); a catalog field also present live upgrades to `live` and keeps the live sample. Catalog fields absent from a live sync are marked `expected_missing` once the feed HAS synced (so real drift is visible) — never before a first sync.

### WP-3 — the studio speaks provenance
- Left-column cards get a quiet provenance chip: nothing for `live`; **"expected"** for `catalog`; **"Odoo field"** for `odoo`. Sample line uses the catalog `sample_value` when there is no live sample.
- FROM sub-line stops lying: `206 fields · never synced` becomes e.g. **`31 expected fields · Zoho People catalog · not yet synced`** (and `N fields · synced 3d ago` when live). Wording is yours to finalise; the rule is that the count and its origin agree.
- A first-run hint on a never-synced connector: *"These are the fields Zoho People is expected to deliver. Map now — the first sync will confirm them."* with the existing "Connect / Sync" affordance where one exists.
- Cycle 5's honesty line must now distinguish the two cases it currently conflates: a mapping pointing at a **catalog** field is normal (say nothing); a mapping pointing at a path in **neither** live nor catalog keeps today's warning.
- **`Fetch field list`** action on the connector cockpit's feed strip, enabled only when credentials exist: calls the connector class's existing metadata path (Zoho: `forms/{form}/components`, `zoho_connector.py:216`; the base class declares `get_available_fields` `integrations/base_connector.py:56`) and upserts catalog rows for that feed (create-only on path; refresh label/type). Report which connectors implement it and stub the rest honestly.

### WP-4 — the abm payoff (validate, don't re-seed)
After deploy + `-u` on abm: the Zoho People (ABM) board must show **named Zoho fields** in FROM and the **15 Cycle-4 mappings drawn as real wires** (they already carry the right `source_field`s). Do NOT re-seed or edit those mappings. If any of the 15 still fails to resolve, report the exact paths — that is a genuine catalog gap, and the fix is a catalog row, not a mapping edit.

## Ask 2 — the back control and the wordmark are invisible

**Verified causes.**
- The wordmark: `mapping_studio.xml:14-16` → `.pbms-brand { … color: var(--pbim-muted) }` (`mapping_studio.scss:50`), 12px/800/uppercase (`:52`). Muted grey on a light bar = the owner cannot find it.
- The back control is the **shared** `HubBackChip` (`pb_hub/static/src/xml/hub_shell.xml:118`, rendered by the shell at `:23`; component in `pb_hub/static/src/js/hub_nav.js`), styled `.pbhub-back` (`pb_hub/static/src/scss/hub_shell.scss:459-491`) with a `--lite` variant (`:492+`) and a responsive text-hiding rule (`:426`).

**What to do.**
1. **Measure first**: report the computed contrast ratios (text and border) for the back chip and the wordmark as they ship today, on the surfaces they actually sit on. Target **WCAG AA: ≥4.5:1 for text, ≥3:1 for interactive boundaries**, in both the light shell and any dark chrome behind them.
2. **Make "back" read as a control, not a caption**: a solid token-based surface with a real border, an obvious hover/active state, adequate hit area, and a focus ring. It must be legible against BOTH the light cockpit bar and dark chrome. Use `--pbim-*` tokens; **no new hexes** (W1), Lucide via the IC registry (W2), flat (W3).
3. **It is shared — so validate it everywhere.** Changing `.pbhub-back` changes every cockpit's back door. Screenshot at least four hosts (Mapping Studio, Integrations, connector cockpit, Settings-launched cockpit) plus the `--lite` variant's host and the narrow-viewport rule at `:426`, before/after. If a host regresses, prefer adding a variant over weakening the shared fix.
4. **The wordmark**: give it enough contrast to be found, without competing with the page title — and decide honestly whether it should be a *control* (a home/overview affordance) or remain a label; if it stays a label, it must not look clickable. Report the choice.
5. While you are there: the floating support/coach widget overlaps the TO column's cards at this viewport (visible bottom-right in the owner's screenshot). Check whether it is ours; if it is, keep it clear of the right column (offset or reflow), else note it and move on.

## Binding non-goals
No new RPC contracts beyond WP-3's fetch action; no transform-whitelist change (python stays server-refused, W12); no re-seeding or editing of abm's Cycle-4 mappings; no changes to Cycle 5's wire geometry, hub, dock chips or filters beyond the provenance additions; no virtualization; don't touch the ⌘K fold question; don't fix the two known pre-existing failures; never stage `.claude/settings.json`, `thaco/`, `ABM/`; never push.

## Numbered tests
1. Catalog templates instantiate create-only per connector; re-run creates 0; a renamed/deactivated catalog row survives re-sync.
2. `get_available_source_fields` on a connector with **no store rows** returns catalog fields with `provenance='catalog'` and **no** Odoo fields; with store rows, live wins and duplicates collapse by path; with neither, Odoo fallback returns and is marked `provenance='odoo'`.
3. Samples: catalog `sample_value` surfaces when no live sample exists; a live sample overrides it.
4. `expected_missing` is set only after a feed has synced at least once — never on a virgin connector.
5. The 15 abm-shaped mappings (fixture replicating their `source_field`s) resolve against the catalog and produce wires; the "no longer delivers" warning does NOT fire for catalog-backed paths, and still fires for a genuinely unknown path.
6. Fetch-field-list: upserts on a connector whose class implements metadata; a clean, honest error on one that doesn't; no credential value ever returned in the payload.
7. ACLs: read for the user tier, CRUD for admin, on both new models.
8. Contrast: automated or scripted computation of the before/after ratios for the back chip and wordmark, asserting AA thresholds.
9. Regression: Cycle 5's wires, hub, dock chips, search/filters, story bar unchanged; the legacy Formula-Studio overlay host still renders; Cycles 1–4 suites green — one scoped run across the five modules plus pb_hub, exit 0 modulo the two known pre-existing failures.
10. Live validation (Chrome MCP; W129 temp single-company user, W130 own Chrome over CDP), on **abm** and payobook: the owner's exact scene before/after — FROM column showing named Zoho fields, the 15 wires drawn, the sub-line telling the truth, the back chip and wordmark clearly visible (screenshots at the same viewport as the owner's, ~1900px wide), the four-host back-chip sweep, zero console errors, zero non-warmup ≥400s.

## Deploy + verify
Standard ritual, **W136 stall-proof unit** (the unit restarts the service itself), on payobook **and** abm (abm needs the `-u` to load the new models + noupdate data; remember W121's second-pass rule if any unfreeze migration is involved, and verify data rows by count + per-XMLID). Version-diff the reverse-dep closure (W118). JS gate is `node --input-type=module --check < file` (W127). Asset-heavy modules: Chrome-load a page after the SCSS deploy.

## Self-review
Check twice: (1) no path can present Odoo internals as a source system's schema; (2) provenance can never claim `live` for a field no payload contained; (3) the shared back-chip change is validated on every host you could find, not just the Mapping Studio; (4) abm's Cycle-4 mappings are untouched on disk and in the DB.

## Commits
Per feature, explicit staging: (1) feat: the fields a feed is expected to deliver — the catalog model; (2) feat: the Zoho and Darwin field catalogs, as data; (3) feat: discovery is layered, and says where each field came from; (4) feat: the studio stops calling Odoo's schema "Zoho"; (5) feat: fetch the field list from the vendor; (6) fix(pb_hub): the way back is a control you can see; (7) docs: ledger + report. Tests with their feature (W9). Write `CYCLE6_REPORT.md` incrementally, committing at milestones.

## Report back
Per-test evidence; before/after screenshots of the owner's scene and the back-chip sweep; the measured contrast ratios; the resolution result for all 15 abm mappings (path by path); which connectors implement metadata fetch; commit hashes; deploy EXIT codes for both databases; deviations with reasoning; new W-rules (W151+).
