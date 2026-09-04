# Integrations Program — Cycle 1: the endpoint model + navigation streamlining

Program: streamline the Integrations experience (fewer clicks, legible source→target story), model **multiple APIs per system** ("one connector, many endpoints" — owner-locked), then prepopulate Zoho People from the legacy ABM inventory (Cycle 3) and seed the abm tenant (Cycle 4). This cycle lays the schema + fixes the navigation.

Conventions: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` is **binding through W119** (operating model W0.x, design laws W1–W6, engineering rails W7–W13.1, and the whole ledger — especially W10 deploy ritual, W118 asset-bundle staleness, W119 stop/upgrade race). Cross-program deploy ritual + C18.x gotchas: `docs/FORMULA_ENGINE_CONVENTIONS.md`. **Append new W-rules (W120+) for every new gotcha, in the same commit.**

## Environment facts (verified 2026-08-20 — do not re-derive)
- Repo: `/Users/adity/Documents/GitHub/gitlocal`, branch `19.1`. Live box: ssh alias **`Payobook19v2`**, Odoo 19 CE as user `odoo` via `sudo service odoo-server {stop,start}`, conf `/etc/odoo-server.conf`, log `/var/log/odoo/odoo-server.log`, addons `/odoo/odoo-server/addons`, apex DB **`payobook`** (dbfilter `^%d$`, other DBs = tenants `acme`, `abm`, `payobook_template` — NEVER touch tenants this cycle). Registry load ~50s. Prod-mode asset cache: after SCSS/JS changes either scoped `-u` or `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` + reload; Chrome-MCP page-load check is mandatory after any SCSS deploy (compile errors surface only at runtime).
- Deploy ritual (proven): rsync to a **fresh session-unique staging dir** (W118/W119 discipline: `/tmp/i1stage.$RANDOM`, verify empty, delete after) → `sudo rsync -a --chown=odoo:odoo` into addons → stop service → **poll for zero `odoo-bin` procs** (never `pkill -f odoo-bin`; kill stragglers BY PID) → detached `systemd-run` unit running `odoo-bin -d payobook -u <changed> --stop-after-init` writing a sentinel + `EXIT=$?` → grep EXIT + ERROR/CRITICAL → start service → `systemctl is-active` + "Registry loaded" in log. **Version-diff repo↔server manifests for the whole reverse-dep closure of what you touch (W118), not just the edited modules.**
- Chrome MCP: standing approval to run/restart it. Live backend `https://payobook.com` — admin `ash@biztinct.com` / `admin1234` (company 5 "Payobook Vietnam JSC" is the demo world; companies 2/6/7 archived). Demo user `demo@payobook.com` / `demo1234`.
- Tests: never bare `--test-tags` without a scoping `-u` (W9/C18.40). Two known pre-existing failures elsewhere (pb_timeoff test_05, pb_today hex) — not yours, don't fix.
- Commits: per feature, explicit staging (W0.3). NEVER stage `.claude/settings.json`, `thaco/`, or the untracked `ABM/` dir. Never push.

## Verified plumbing map (file:line, current as of this morning — do not re-derive)

**Connector model** `hr.integration.connector` — `pb_hr_payroll_formula/models/integration_connector.py:18`. `connector_type` selection `zoho/excel/sap/workday/oracle/darwin/demo` `:33`; single `api_endpoint` Char `:68`; `auth_type` `oauth2/api_key/basic/bearer` `:78`; credential fields `client_id/client_secret/api_key/username/password/access_token/refresh_token/token_expiry` all `groups="base.group_system"` `:88-126`; `field_mapping_ids` `:146`; `data_store_ids` `:160`; `connection_status` `:178`; `last_sync`/`last_sync_status`/`last_sync_message` `:185-195`; `total_synced_employees/records` `:212-217`. `action_pull_data(data_types=…)` `:564` branches per data_type at `:611` (employee), `:629` (salary), `:669` (dependent), `:699` (attendance), `:728` (leave) via `hasattr` probes on the connector class. `action_test_connection` `:404`, `action_view_mappings` `:525`, `action_view_data_store` `:542`, `_get_connector_instance` `:918`.

**Field mapping** `hr.integration.field.mapping` — `pb_hr_payroll_formula/models/integration_field_mapping.py:15`. `connector_id` `:23`, `source_field` dot-path `:39`, `target_rule_id` (domain input) `:69`, transformation ladder `:91-127`, `active_state` active/suggested/ignored `:174`. **No endpoint/data_type axis — that's this cycle's gap to close.**

**Data store** `hr.api.data.store` — `pb_hr_payroll_formula/models/api_data_store.py:25`. `data_type` selection (8 values: employee/salary/attendance/leave/dependent/benefit/tax/custom) `:36` — **reuse this exact selection for endpoints**. `state` raw/extracted/consumed/archived/error `:122`.

**Vendor mapping template** `hr.integration.mapping.template` — `pb_hr_payroll_formula/models/integration_mapping_template.py:27` (`_VENDORS` `:18`). This is the **precedent to clone** for the endpoint template model. Onboarding wizard same file `:52`.

**ACL file** `pb_hr_payroll_formula/security/ir.model.access.csv` — connector lines `:10-11` (user=read, admin=CRUD), mapping `:12-13`, mapping.template `:103-104`. Clone these shapes for the two new models.

**Settings hub** — `pb_settings/static/src/js/settings_hub.js`. `CATEGORIES` const `:108`; Integrations category `:139-148` (ONE card, tag `pb_integrations`, groups `G_INTEGRATIONS` `:93`); `openCard(card)` `:366` → `openHub(actionService, {tag: card.tag, back: this.backToSettings})` `:371-372` (or `doAction(card.xmlid)` `:377`); `backToSettings` `:353`; `_cardPresent` `:304` probes the actions registry; `categories` getter `:319`. `openHub` (`pb_hub/static/src/js/hub_nav.js:52`) already merges an arbitrary `opts.context` at `:63` and writes the `pb_back` chip at `:67-82` — **the deep-link machinery exists; only forwarding is missing**.

**Integrations cockpit** — `pb_integrations`. Facade `pb.integrations` `pb_integrations/models/pb_integrations.py:96`: `get_board()` `:110` (kpis/types/connectors), `get_ledger` `:182`, `_ledger_store` filters by connector `:338`. OWL `pb_integrations/static/src/js/integrations.js:56`: reads arrival context `pb_ledger`/`pb_connector`/`pb_connector_name`/`pb_back` at `:69-86`; `openConnector` `:291` → `doAction` tag `pb_import_connector_cockpit` with `params:{connector_id, back_to, back_label}`. Template `pb_integrations/static/src/xml/integrations.xml`: KPI row `:27-34`, connector card `:83-89`.

**Connector cockpit** — `pb_import_advanced`. Facade `pb.import.connector.cockpit` `pb_import_advanced/models/connector_cockpit.py:32`: `get_connector_detail` `:62`, `run_connector_action` `:114` (verb whitelist `LIFECYCLE` `:19`), `get_link` `:131` (whitelist `LINKS` `:23`). OWL `connector_cockpit.js`: params-over-context merge `:41-48`, `openLedger` `:106` (deep-links into pb_integrations with `pb_ledger`/`pb_connector` + `pb_back`), **`openAdvancedForm` `:150`** → native form `target:"current"`. **"Open record" button: `connector_cockpit.xml:20`.**

**Demo world** — `pb_demo/models/demo_integrations.py`: seeds ~25 connectors (rows incl. "ADP Workforce Now"; Zoho at `:26-28`), adds `is_demo` to connector `:62` and mapping `:67`, fake endpoint URL generator `:96`. The demo generates `hr.api.data.store` rows (the 85k "synced records" on the live board).

**Tests that constrain you**: `pb_integrations/tests/test_one_door.py` — `test_the_connector_cockpit_links_land_in_the_ledgers` `:105` asserts the literal `'Open record'` at `:115`; `test_the_door_enumeration_is_exactly_the_agreed_list` `:138`. `pb_settings/tests/test_settings.py`. `pb_sidebar/tests/test_ia_c5.py`. Amend them IN THE SAME COMMIT as the behavior change, with the reasoning in the commit message.

## Work packages

### WP-1 — `hr.integration.endpoint` + `hr.integration.endpoint.template` (pb_hr_payroll_formula)
New file `models/integration_endpoint.py`, two models, precedent = `integration_mapping_template.py`.

`hr.integration.endpoint` (the per-connector feed):
- `connector_id` M2o `hr.integration.connector` required ondelete=cascade index; `name` Char required; `code` Char required (slug, e.g. `zoho_employees`); `data_type` Selection — **the exact 8-value list from `api_data_store.py:36`** (single source: import/share the list, don't retype); `http_method` Selection get/post default get; `path` Char (relative path or absolute URL); `params_note` Char (human note: "sIndex, limit=200, dateFormat"); `description` Text; `sequence` Integer; `active` Boolean default True; `is_legacy_abm` Boolean (help: "Used by the legacy ABM application"); `last_sync` Datetime; `last_sync_status` Selection success/partial/failed; `last_error` Char.
- Computed (non-stored): `synced_count` / `staged_count` from `hr.api.data.store` grouped by `(connector_id, data_type)` — staged = `state='raw'` (mirror however `pb.integrations._ledger_store`/board KPIs count "staged" — read `pb_integrations.py:110-180` and match its definition exactly so numbers agree across screens); `mapping_count` = field mappings with `endpoint_id = self`.
- `_sql_constraints`: unique `(connector_id, code)`.
- `mail.thread` NOT needed. `_order = 'sequence, name'`.

`hr.integration.endpoint.template` (the vendor catalog, data-XML-seedable — rows arrive in Cycle 3):
- `connector_type` Selection (same vendor list as `integration_mapping_template.py:18` plus `demo`/`excel` if trivial — match the connector's own selection `:33`), `code`, `name`, `data_type`, `http_method`, `path`, `params_note`, `description`, `sequence`, `is_legacy_abm`, `active`.

Instantiation machinery on `hr.integration.connector`:
- `endpoint_ids` O2m + `endpoint_count` compute.
- `action_sync_endpoint_catalog()` — idempotent, two sources, **create-only, never overwrite user edits** (mirror the never-overwrite semantics of `mapping_template_apply`): (a) template rows matching `connector_type` → create endpoints missing by `code`; (b) distinct `data_type` values present in the connector's `data_store_ids` with no covering endpoint → create a generic endpoint (`code = data_type`, name = the selection label). Returns `{created, skipped}` counts.
- `create()` override calls it (so new connectors self-populate once Cycle 3 data lands).
- `action_pull_data` (`integration_connector.py:564`): after each data_type branch completes, stamp the matching endpoint row's `last_sync`/`last_sync_status`/`last_error` (create-if-missing via the same catalog-sync path). Keep the seam small — one private helper `_stamp_endpoint(data_type, status, error=False)`.

Schema wiring:
- `hr.integration.field.mapping` += `endpoint_id` M2o `hr.integration.endpoint` optional, index, ondelete='set null'.
- `hr.integration.mapping.template` += `endpoint_code` Char (Cycle 3 stamps it; apply-paths that instantiate mappings from vendor templates should resolve `endpoint_code` → the connector's endpoint and stamp `endpoint_id` when present — find those apply sites: `action_apply_mapping_template` `integration_connector.py:283` and the onboarding wizard `integration_mapping_template.py:159`).
- ACLs in `ir.model.access.csv`: endpoint — user=read only, admin=CRUD (clone connector lines 10-11); endpoint.template — clone mapping.template lines 103-104.
- Manifest: register the file, bump version.

### WP-2 — Settings deep-link (pb_settings)
1. `openCard` (`settings_hub.js:366`): forward an optional per-card `context` — `openHub(this.actionService, { tag: card.tag, context: card.context || {}, back: this.backToSettings })`.
2. **Single-card auto-open**: wherever the rail item / category selection renders the section page, if the category's *visible* cards (post group-resolution `_resolveGroups` `:265` and presence-probe `_cardPresent` `:304`) number exactly 1, skip the section page and `openCard` that card directly. The Settings `pb_back` chip (already written by `openHub`) is the way back. This is a generic rule — today it fires for Integrations; when Cycle 2 adds a second card to the category, the section page naturally returns.
3. Respect `STORAGE_KEY`/category persistence (`:45`) — don't break remembered rail state.
4. Amend `pb_settings/tests/test_settings.py` if it pins the old behavior; Chrome-MCP validates the click count (see tests).

### WP-3 — Connector cockpit: endpoints strip, inline credentials, demote "Open record" (pb_import_advanced)
Backend (`connector_cockpit.py`):
- `get_connector_detail` `:62` gains: `endpoints: [{id, name, code, data_type, icon, last_sync (humanized + iso), status, synced, staged, mapping_count, is_legacy_abm}]` and `credentials: {auth_type, editable (bool: caller in base.group_system), fields: [{key, label, is_set}]}` — **NEVER return secret values, not even masked prefixes; `is_set` booleans only.** Field sets per auth_type: oauth2 → client_id/client_secret/refresh_token (+ oauth urls/scope as plain-text extras); api_key → api_key; basic → username/password; bearer → access_token.
- New RPCs: `sync_endpoint(connector_id, endpoint_id)` → `action_pull_data(data_types=[ep.data_type])`, returns refreshed endpoint row; `sync_catalog(connector_id)` → `action_sync_endpoint_catalog()`; `save_credentials(connector_id, vals)` — hard-gate `base.group_system` (raise AccessError otherwise; the fields' `groups=` will also enforce, but fail loud and friendly), whitelist writable keys to the credential field names + api_endpoint + auth_type, ignore empty strings (empty ≠ clear; provide explicit `clear: [keys]` list for deletion), return the fresh masked credential block.
- Keep `run_connector_action` whitelist semantics; add the new verbs to whatever registration pattern `LIFECYCLE`/`LINKS` uses if they fit it, else standalone methods — match the file's existing style.

Frontend (`connector_cockpit.js` / `.xml` / SCSS):
- **Endpoints strip** under the header: one chip/card per endpoint — Lucide data-type icon via the `IC` registry (`pb_import_kit/static/src/js/import_icons.js`, W2 — ADD missing icons to the registry, no new icon files), name, relative last-sync, status dot (pbim tokens only, W1), `staged · synced · mapped` counts, buttons **Sync** (spinner while running, refresh chip after) and **View data** (reuse `openLedger('store', …)` `:106` pattern — deep-link into pb_integrations Data tab filtered to this connector; if the ledger can't filter by data_type yet, pass `pb_data_type` in context and implement the small filter in `pb.integrations._ledger_store` `:338` + facade + JS state — keep it minimal). NO "Map fields" button this cycle (it arrives with Cycle 2's Mapping Studio — don't ship a dead button).
- Empty state: "No feeds catalogued yet" + a **"Detect feeds"** button → `sync_catalog` (labels it for what it does: derive from synced data / vendor catalog).
- **Inline credentials panel** (visible only when `credentials.editable`): per-field rows with `Set ✓ / Not set` state, write-only inputs (blank placeholder "unchanged"), Save → `save_credentials`, toast on success. Flat pbim styling, no new hexes.
- **Demote "Open record"**: remove the top-level button (`connector_cockpit.xml:20`); add a kebab (⋮) overflow menu at the header's right with a single admin-only item "Open native record" calling the existing `openAdvancedForm` `:150`. Gate its visibility on the same `credentials.editable` flag (system admin).
- Bump `pb_import_advanced` manifest version (asset cache, W118).

### WP-4 — Board feeds summary (pb_integrations)
- `get_board()` `:110`: each connector row gains `feeds` (endpoint count) and `feeds_stale` (endpoints whose `last_sync` is older than the connector's `sync_interval`, or never). Card sub-line (`integrations.xml:89`) becomes "N feeds · M mappings · staged · synced" (keep it one quiet line, no layout blowup).
- If you add the `pb_data_type` ledger filter in WP-3, wire its facet/chip here too.

### WP-5 — Demo endpoints (pb_demo)
- After demo integration data generation (`demo_integrations.py`), loop demo connectors → `action_sync_endpoint_catalog()` so every demo connector derives endpoints from its store rows; stamp plausible `last_sync` mirroring the connector's, mark `is_demo` (add the field to the endpoint model the same way `:62/:67` did for connector/mapping) so demo cleanup cascades stay clean (endpoints cascade-delete with connectors anyway — verify the demo clean path).
- Deploy note: demo seeding methods run via JSON-RPC against the live registry, NOT `-u pb_demo` (post_init only runs on install — see the workforce precedent) — a restart reloads method-only changes.

### Binding non-goals
- NO Mapping Studio / canvas work (Cycle 2). NO vendor catalog data XML rows (Cycle 3). NO abm/tenant work, no SSH into tenant DBs (Cycle 4). NO touching `om_hr_payroll` (secrets question is a Cycle 4 report item). NO changes to `api_transform_save`'s python whitelist, no sudo widening (W12), no new hexes (W1), no FontAwesome/emoji (W2).
- Don't rework the onboarding wizard flow beyond the `endpoint_code` resolution hook.
- Don't fix the 2 known pre-existing test failures.

## Numbered test cases (evidence for each in the report)
1. **Endpoint instantiation**: create an `hr.integration.endpoint.template` row (test data) for type `zoho`; create a zoho connector → endpoint exists with matching code; re-run `action_sync_endpoint_catalog` → `{created:0}`, user-edited endpoint name survives (create-only proven).
2. **Store-derived detection**: connector with store rows of 2 data_types and no templates → catalog sync creates exactly 2 generic endpoints; counts (`synced_count`/`staged_count`) equal the store-row math used by the board (same definition, assert equality against `get_board` KPIs for that connector).
3. **Unique constraint**: duplicate `(connector_id, code)` raises.
4. **ACL**: a plain `group_payroll_base_user`-ish user (use the group the connector user-ACL row names) can read endpoints, cannot create/write (AccessError).
5. **Mapping wiring**: field mapping accepts `endpoint_id`; deleting the endpoint nulls it (not the mapping); vendor-template apply with `endpoint_code` set stamps `endpoint_id` on the created mapping.
6. **Pull stamps**: on a demo/stub connector, `action_pull_data(data_types=['employee'])` → the employee endpoint's `last_sync`/`last_sync_status` updated (create-if-missing path exercised).
7. **Cockpit payload**: `get_connector_detail` includes endpoints + credentials block; assert **no credential value appears anywhere in the payload** (serialize and grep for a known secret set in the test).
8. **save_credentials**: non-system user → AccessError; system user sets api_key → `is_set` flips true, empty-string field is ignored, `clear` list clears; response contains no secret.
9. **sync_endpoint** RPC pulls only the endpoint's data_type (assert store rows created for it, not others — demo connector).
10. **test_one_door.py** amended and green: door enumeration updated if doors changed; the `'Open record'` literal assertion replaced by the kebab equivalent (assert the native-form door still exists, admin-gated).
11. **Settings suite** green with the single-card auto-open change; `pb_settings`, `pb_integrations`, `pb_import_advanced`, `pb_hr_payroll_formula` test suites in one scoped run (W9: with `-u` scoping), exit 0 (modulo the 2 known failures elsewhere).
12. **Chrome-MCP live validation** (after deploy, admin login): (a) Settings rail → click "Integrations" → **lands directly on the Integrations cockpit in ONE click**, back-chip "Settings" present and working; (b) open a connector with data (e.g. ADP Workforce Now) → endpoints strip renders with icons/counts/status; (c) click Sync on one endpoint → chip refreshes with new last-sync; (d) credentials panel: as ash set a dummy api_key on a Demo/Stub connector → "Set ✓"; (e) "Open record" absent from the toolbar, present under kebab, opens the native form; (f) board cards show "N feeds"; (g) `demo@payobook.com` login: no credentials panel, no kebab native-form item, endpoints visible read-only; (h) zero console errors, zero non-warmup ≥400 network responses on all screens; (i) screenshot each state.
13. **Feeds summary math**: a connector with an endpoint never synced shows it stale ("M stale") — assert in the payload test, spot-check in UI.

## Deploy + verify
Standard ritual (Environment facts above): rsync changed modules (`pb_hr_payroll_formula`, `pb_import_advanced`, `pb_integrations`, `pb_settings`, `pb_demo`, `pb_import_kit` if the icon registry changed) with fresh staging dir; version-diff the reverse-dep closure (W118); stop → poll-zero-odoo-bin → detached `-d payobook -u <list> --stop-after-init` sentinel unit → EXIT=0 + clean log → start → Registry loaded; asset purge only if an OWL/SCSS change doesn't appear (then re-check pages, W118 rule 2); demo endpoint seeding via JSON-RPC; Chrome-MCP validation per test 12; `payobook` health + `acme` untouched (grep the log window).

## Self-review (mandatory, W0.1)
Read your whole diff against this handover before reporting. Check twice: (1) no RPC path can return a credential value; (2) the endpoint counts use the SAME staged/synced definitions as the board (no two truths on screen); (3) create-only semantics in catalog sync; (4) every amended test's assertion still tests something real (not weakened to pass).

## Commits
Per feature, explicit staging: (1) feat(pb_hr_payroll_formula): the endpoint model — one connector, many feeds; (2) feat(pb_import_advanced): endpoints strip + inline credentials, native form demoted to the kebab; (3) feat(pb_settings): single-card categories deep-link straight through; (4) feat(pb_integrations): feeds on the board (+ data_type ledger filter if built); (5) feat(pb_demo): demo connectors grow endpoint rows; (6) docs: ledger entries + this cycle's notes. Tests ship WITH their feature commit (W9).

## Report back
- Per-test evidence (numbers, payload excerpts, screenshot paths), commit hashes, EXIT codes of the deploy unit.
- The exact `action_pull_data` branch behavior you found at `:611-728` (any surprises vs this doc), and where `_stamp_endpoint` landed.
- The staged/synced definitions you matched (board vs endpoint) — state them.
- Any W-rules appended (W120+).
- Deviations from this handover, with reasoning. Anything that felt too risky to decide alone.
