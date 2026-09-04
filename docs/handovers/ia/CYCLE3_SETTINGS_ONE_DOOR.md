# IA Redesign — Cycle 3: Settings hub + cog + one-door Integrations

Program: Option A "Six Missions" (mockup `docs/PAYOBOOK_IA_REDESIGN_OPTIONS.html` — the cog overlay in the Option A demo is the visual spec for the Settings hub; flow-doctrine cards 1 & 3 are the spec for onboarding + one-door).
Prior cycles: C1 `pb_hub` kit (API in `docs/handovers/ia/CYCLE1_SHELL_AND_FIXES.md` §pb_hub + C1 report), C2 `pb_payhub` + in-lens ledger mode (commits 306d4f8b…744d6ecb).
Conventions `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` binding through **W94**.

## ⚠ Production discipline (read first)
The verification box serves **payobook.com — production**. Cycle 2 caused an 8-minute live outage via `rsync --delete` into shared addons (now W93/W94). Non-negotiable this cycle:
- Deploy ONLY by the ledger's documented ritual; never `--delete` on the shared addons hop; count files & diff checksums before any server restart; never restart/kill a server you didn't start (W68).
- Treat every server operation as a production change: smallest possible steps, verify between steps, stop and mark tests UNVERIFIED rather than improvise recovery.

## Scope
1. **`pb_settings` module** — full-screen Settings hub (client action tag `pb_settings_hub`, xmlid `pb_settings.action_pb_settings_hub`; no menu/rail entry — cog + ⌘K only until C5).
2. **Cog wiring** — the pay hub (and demo hub) get `config.cog` → opens Settings hub with a back chip.
3. **One-door Integrations** — `pb_integrations` becomes the only connectors home; Import's duplicate doors close; the onboarding modal becomes a full-screen stepped flow; the three raw-list satellites become in-cockpit ledgers with drawers.

### Binding non-goals
- NO rail/sidebar data changes (C5). NO Home/Insights/Compliance hubs (C4/C5). NO Planning changes. NO Formula-Studio-internal changes (its own modals are a later item). Statutory's five legacy VN tiles: OPTIONAL stretch (see §Stretch) — skip cleanly if risky.

## Verified plumbing facts (audit + C1/C2 reports; re-verify lines you edit)
- **Settings hub look**: clone the mockup's cog panel — left category nav (`.d-cognav` pattern), right pane of cards (icon square, title, sublabel, Open button). Tokens/primitives from `pb_import_kit` (`pbim-root-vars`, `.pbim-card`); class prefix `.pbst-*`.
- **HubShell cog**: C1 API — `config.cog?: () => {}` renders the cog button in the command bar. Wire in `pb_payhub`'s config; use `openHub(action, {tag:"pb_settings_hub", back:{label:"Pay Run", tag:"pb_pay_hub"}})` so the chip returns to the hub.
- **Integrations cockpit**: `pb_integrations/static/src/js/integrations.js` — board :97; connector card → `pb_import_connector_cockpit` :81–86; "Connect an HR system" → `pb_hr_payroll_formula.action_hr_integration_onboarding` :90–94 (transient modal `hr.integration.onboarding.wizard`, `target=new`, `pb_hr_payroll_formula/wizards/integration_onboarding_views.xml:72–77`); 3 link tiles from `pb_integrations/models/pb_integrations.py:21–25` → raw `list,form` on `hr.integration.field.mapping` / `hr.api.data.store` / `hr.api.transformation.rule` (`action_field_mapping`, `action_api_data_store`, `action_api_transformation_rule`).
- **Import cockpit's duplicate doors**: KPI tile + Connectors panel `pb_import/static/src/xml/import.xml:22,102–104`; server launch-tile list `pb_import/models/pb_import.py:24–35` includes `pb_hr_payroll_formula.action_integration_connector` (raw list). Import opens the connector cockpit **without back context** (`pb_import/static/src/js/import.js:96–102`) — the "same cockpit, different back button" bug.
- **Connector cockpit**: `pb_import_advanced/static/src/js/connector_cockpit.js` (:81 action tag `pb_import_connector_cockpit`; `openAdvancedForm()` :72–77); its 3 link buttons come from `pb_import_advanced/models/connector_cockpit.py:23–25` → `pb_hr_payroll_formula/models/integration_connector.py:525–556` returning raw lists.
- **In-lens ledger mode (C2)**: `pb_payrun_ledgers` — descriptor-driven cockpit `js/ledger.js`, hub mode with tabs + 320px drawer, per-click `get_detail(id)` honoring caller rights, styles `.pbl-*`, escape suppressed by `t-if="!props.embedded"`. Read commit `306d4f8b` for the exact seam before deciding reuse-vs-clone (see §Architecture 3c).
- **Payroll defaults**: `om_hr_payroll` config action `om_hr_payroll/views/res_config_settings_views.xml:31–44` (`res.config.settings`) — currently unreachable in-product; native settings form is deliberately excluded from the VU skin (`vu_form_renderer.js:17`), leave it native.
- **Admin actions**: Roles `base.action_res_users`; Companies `base.action_res_company_form`; Tenants tag `pb_tenants`; Navigation editors `pb_sidebar.action_pb_sidebar_item` / `action_pb_sidebar_section` (`pb_sidebar/views/pb_sidebar_views.xml:115–125`).
- Cockpit launch targets: Formula Studio tag `pb_formula_studio`, Structures tag `pb_structures`, Statutory tag `pb_statutory`.

## Architecture
1. **Settings hub** — categories (order fixed; per-category `groups` gating, hidden not disabled):
   | key | label | opens | gate |
   |---|---|---|---|
   | formula | Formula Engine | tag `pb_formula_studio` (back chip) | payroll manager |
   | structures | Salary Structures | tag `pb_structures` (back chip) | payroll manager |
   | statutory | Statutory | tag `pb_statutory` (back chip) | payroll manager |
   | integrations | Integrations | tag `pb_integrations` (back chip) | payroll manager |
   | payroll | Payroll defaults | xmlid `om_hr_payroll.action_hr_payroll_configuration` (verify xmlid) | payroll manager |
   | roles | Roles & Access | `base.action_res_users` | `base.group_system` |
   | org | Companies & Tenants | two cards: `base.action_res_company_form`, tag `pb_tenants` | `base.group_system` |
   | nav | Navigation | two cards: sidebar items / sections editors | `base.group_system` |
   Left nav switches the right pane; each pane holds 1–2 cards (icon, one-line "what lives here", Open). Verify each gate group actually exists (`om_hr_payroll.group_hr_payroll_manager` per audit) — report what you used. All Opens carry `back:{label:"Settings", tag:"pb_settings_hub"}` so every cockpit can return.
2. **Cog + palette**: pay-hub config gets `cog`; palette entries "Settings" (payroll manager) and keep everything else intact. Demo hub gets the cog too (living documentation).
3. **One-door Integrations**:
   a. `pb_import`: remove the connector KPI tile + Connectors panel + the connector launch tile from the server list; add one quiet link-row/button "Manage connectors" → `openHub` to tag `pb_integrations` with `back:{label:"Import", tag:"pb_import"}`. Import wizard untouched.
   b. `pb_integrations` connector card + `pb_import_advanced` cockpit stay, but every entry into the connector cockpit now passes an explicit `back` (from Integrations: back to Integrations; nothing else opens it after (a)).
   c. The 3 raw-list satellites (field mappings / data store / transformation rules) become **in-cockpit ledgers with drawers** inside `pb_integrations` (a "Data" section on the board or per-connector view — your call, report it). Reuse the C2 ledger seam if it's cleanly importable across modules; if the import would drag pay-domain deps, clone the minimal grid+drawer pattern into `pb_integrations` (`.pbig-*`) and say so. Descriptors: mapping (source field → target field, transform, connector, active), data store (key, connector, fetched_at, payload summary in drawer), transformation rule (name, code lang, in/out, connector). Row click = drawer, never navigation; no "open full list" anywhere. The legacy actions themselves stay registered (hidden menus, other callers) — you're replacing the *doors*, not deleting the models.
   d. Connector cockpit's 3 link buttons → the new in-cockpit ledgers (with back), not raw lists (`connector_cockpit.py:23–25`). `openAdvancedForm` stays but relabel to "Open record" if it isn't already.
   e. **Onboarding stepped flow**: new full-screen client action in `pb_integrations` (clone the `pb_import_wizard` 4-step pattern — its files are the precedent) wrapping the existing `hr.integration.onboarding.wizard` server logic: steps ≈ Choose system → Connect/auth → Field mapping preview → Confirm & test. Reuse the transient model's fields/buttons server-side (drive it via RPC; do not fork its logic). "Connect an HR system" opens this flow; the old `target=new` modal action stays registered but nothing in Payobook opens it.
4. **No sudo / rights**: any new server helpers follow C2's pattern — caller's rights, `check_access`, no create/write on config models from the hub glue.

## Stretch (only if everything above is green and time remains)
Convert `pb_statutory`'s 5 legacy VN launch tiles (`pb_statutory/models/pb_statutory.py:20–31`) to the same in-cockpit ledger+drawer pattern. If skipped: write it explicitly in the report as C4/C5 hand-back.

## Safety rails
- Icons via `ic()` only; add missing names to import_icons.js and report. One accent, no gradients, tabular-nums, no `window.confirm`, whole-sentence toasts (W80).
- Standalone regressions: `pb_import` cockpit minus its connector doors must otherwise render identically; `pb_integrations` board keeps its KPIs.
- Demo fixtures: to test onboarding end-to-end, use/extend the existing demo connectors if present; if you must create one, name it clearly (e.g. "IA-C3 Sandbox"), verify nothing schedules against it, and archive it after evidence — report its ids. Never touch real connector credentials.
- W68/W93/W94 as above. Asset-cache bump after JS changes.

## Tests (evidence for each)
1. Settings hub opens via ⌘K "Settings" and via the pay-hub cog; back chip from cog returns to the pay hub with its lens intact.
2. Category gating: payroll-manager persona sees formula…payroll only; admin sees all 8. (Two personas, screenshots/DOM.)
3. Every category card opens its target; each opened cockpit shows a back chip returning to Settings. **Payroll defaults opens the previously unreachable `res.config.settings`** and saves a no-op edit cleanly.
4. Import cockpit: connector tile/panel gone; "Manage connectors" → Integrations with back chip → returns to Import. No other visual change to Import (diff screenshot vs pre-change acceptable).
5. Integrations: the 3 satellite ledgers render real rows; row click = drawer (no navigation); drawer shows the descriptor fields; ESC/X close.
6. Connector cockpit: 3 links land on the in-cockpit ledgers with back chips; no raw `list,form` reachable from any Payobook door (grep the runtime configs + click-test).
7. Onboarding flow: complete Choose→Connect→Preview→Confirm against a sandbox/demo connector; a connector record results; the old modal action is no longer opened by any Payobook button (grep evidence).
8. One-door audit repeat: enumerate every remaining door to `hr.integration.connector` & satellites — must be exactly: Settings·Integrations (home), Import's back-chipped deep-link, connector cockpit internals, hidden legacy menus (documented). List them in the report.
9. Standalone regression: pb_import full flow (wizard 4 steps) still works; pb_integrations board KPIs unchanged; pay hub 8 lenses unaffected.
10. ⌘K yield matrix re-run (ordinary / Mission Control / Formula Studio / pay hub / settings hub).
11. Unit tests: prior 53 stay green + new pb_settings/pb_integrations tests (gating table, one-door door-enumeration gate, descriptor sanity) — one combined run, exit 0.
12. Server log clean; no ≥400 asset responses across settings hub + integrations + import.

## Self-review (mandatory)
Diff-read all changes; verify no import-cockpit functional regressions beyond the removed doors; verify gating can't hide the whole settings hub from an admin-only persona; check drawer z-order inside pb_integrations; verify the onboarding flow can't double-create connectors on double-click (guard like C1's `opening` flag); re-run affected tests after fixes.

## Commits (per feature, explicit staging, do NOT push)
Suggested: (1) feat(pb_settings): settings hub + cog wiring + palette; (2) feat(pb_integrations): satellite ledgers + one-door rewiring (+pb_import door removal, pb_import_advanced links); (3) feat(pb_integrations): onboarding stepped flow; (4) docs: ledger + handover updates. Never stage `.claude/settings.json`, `thaco/`, `ABM/`.

## Report back
- Category table as shipped (gates verified against real groups).
- The reuse-vs-clone decision for the ledger seam and why.
- Door enumeration (test 8) — the definitive post-C3 list.
- Onboarding flow → wizard-model mapping (step → fields/buttons driven).
- Stretch outcome (done or hand-back), per-test evidence, commit hashes, deviations, new W entries.
