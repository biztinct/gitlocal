# IA Redesign — Cycle 1: audit fixes + `pb_hub` shell kit + global ⌘K

Program: product-wide IA redesign (approved Option A "Six Missions" + period tracker + global ⌘K).
Mockup of the target: `docs/PAYOBOOK_IA_REDESIGN_OPTIONS.html` (open it in a browser — Option A demo IS the spec for look & feel).
Conventions: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` is **binding** (one-accent law W1, no chrome gradients W3, sequence-uniqueness W8/W18, etc.). Append any new gotcha you hit to its ledger.

## Scope

Three workstreams, in order:
- **A. Fix three live sidebar bugs** found by the audit (data + migrations).
- **B. New module `pb_hub`** — the reusable Mission-Control shell kit that every later cycle builds hubs from.
- **C. Global ⌘K palette** mounted app-wide.

### Binding non-goals
- Do NOT change the rail's sections/items beyond the three fixes (cutover is Cycle 5).
- Do NOT refactor `pb_mission` to consume `pb_hub` — Mission Control keeps working exactly as-is.
- Do NOT build any actual hub content (Pay Run hub etc. are later cycles).
- Planning section: touch nothing.

## Verified plumbing facts — do not re-derive

Sidebar system:
- Rail OWL component: `pb_sidebar/static/src/js/pb_sidebar.js` (icons dict :15–55 — **closed set**, unknown icon silently renders a circle; `_buildIndex` :160–177 builds a FLAT last-writer-wins map for active-item matching; restricted-item AlertDialog :195–211).
- WebClient mount precedent: `pb_sidebar/static/src/js/webclient_patch.js:7–12`.
- Models: `pb.sidebar.section` / `pb.sidebar.item` in `pb_sidebar/models/pb_sidebar.py` (:5–23 / :26–57); server tree builder `get_sidebar_data()` :62–137 (restricted items get action stripped :96–97).
- Master data: `pb_sidebar/data/pb_sidebar_data.xml` (428 lines).
- Migration precedent (clear noupdate / renumber): `pb_timeoff/migrations/19.0.1.0.3/post-migrate.py`, `pb_business_trip/migrations/19.0.1.0.5/post-migrate.py`.

Mission Control shell (the DNA you are generalizing):
- Shell: `pb_mission/static/src/js/pb_mission.js` (LENSES array :128–184, labels+group gating :381–421, deep-link arrival protocol `pb_lens`/`pb_focus`, lens persistence key `pbms.lens.v1` :51, QUICK_ACTIONS :70–89), template `pb_mission/static/src/xml/pb_mission.xml` (lens rail :54–68, embedded cockpit mounts :82–113), SCSS `pb_mission/static/src/scss/pb_mission.scss` (command bar :34–230, lens rail :240–286, responsive :322–331, z-discipline :12–16).
- Embedded cockpits accept `embedded="true"` and suppress their own header (e.g. `pb_today/static/src/xml/pb_today.xml:14`).
- ⌘K palette to clone: `pb_wf_kit/static/src/xml/wf_kit.xml:194–252`, `pb_wf_kit/static/src/scss/wf_kit.scss:478–630`, JS in `pb_wf_kit/static/src/js/`.
- Person drawer (needed later, not C1): `wf_kit.scss:169–235`.
- Design tokens: `pb_import_kit/static/src/scss/import_tokens.scss` (mixin `pbim-root-vars`; primary #5A4BB0, command-bar #241F52, ink #1B1733, line #E2E8F0, soft #EDEAF8, radii 10/14/18px, shadows). Icon helper: `pb_import_kit/static/src/js/import_icons.js` (`ic(name, size)`).
- Other ⌘K owners that must keep working: Mission Control's palette (`pb_mission.js`), Formula Studio's Command Center (⌘K) and old text palette (⌘⇧K).

## Workstream A — the three fixes

**A1 — "Employee/Contract Mapping" never retired.** `pb_sidebar/data/pb_sidebar_data.xml:270` sets `<field name="active">False</field>` — the *string* `"False"`, which Odoo coerces to True, so the item still renders in SETUP (comment at :263–265 says it was retired). Fix the data to `eval="False"`, and add a `pb_sidebar` migration (version bump + post-migrate) that deactivates the existing DB record by xmlid so live DBs heal on upgrade.

**A2 — ADMIN sequence collision.** `pb_audit.item_audit_console` and `pb_sidebar.item_menu_cfg` both sit at sequence 30 (order becomes install-order dependent — violates W8/W18). Renumber the pb_sidebar config items (Menu & Sidebar → 50, Sidebar Sections → 55; leave pb_audit at 30) in data + same migration for existing DBs.

**A3 — highlight steal.** Both `item_import` (`pb_sidebar_data.xml:82`) and `item_integrations` (:196) claim `hr.integration.connector` in `match_models`; the flat index makes Integrations steal the highlight from Import Data. Remove `hr.integration.connector` from **item_import**'s match_models (Import keeps `hr.payroll.import.batch`); migration updates existing DB rows.

Verify the actual xmlids/nearby lines before editing; the line numbers are from an audit a few hours old.

## Workstream B — `pb_hub` module

New module `pb_hub` (depends: `web`, `pb_import_kit`, `pb_wf_kit`; assets in `web.assets_backend`). It generalizes the pb_mission shell into reusable OWL components with `.pbhub-*` class names, cloning the exact metrics and tokens (do not invent new visuals — copy pb_mission's SCSS values):

1. **`HubShell`** — props:
   ```js
   {
     config: {
       key: "pay",                        // localStorage: `pbhub.<key>.lens.v1`
       brand: { label: "Pay Run", icon: "zap" },
       lenses: [ { key, icon, label, groups?: [xmlids], Component?, props? } ],
       dock?: Component,                  // optional right dock (268px), rendered as sibling of canvas
       tracker?: { label, stage, total }, // period tracker chip (see 3)
       cog?: () => {},                    // optional callback → renders cog button in command bar (wired Cycle 3)
     }
   }
   ```
   Layout = pb_mission's: dark command bar (#241F52, brand chip, slot for context segments, ⌘K launcher button that opens the global palette, optional cog, avatar) / white 76px lens rail (60px buttons, 17px icon over 9px uppercase label, active #EDEAF8/#5A4BB0) / canvas. Lens gating via `user.hasGroup` like `pb_mission.js:418–421` (denied lenses absent, not disabled). Deep-link arrival: honor `action.context.pb_lens` + `pb_focus` exactly like pb_mission. Embedded lens components get `embedded: true`.
2. **`HubBackChip` + deep-link helper** — `openHub(actionService, { tag, lens, focus?, back?: {label, tag, lens} })` passes `pb_back` in context; `HubBackChip` (rendered by HubShell in the command bar when `pb_back` present) navigates back. This is the foundation of the one-door law used from Cycle 3 on.
3. **`HubTracker`** — small command-bar chip, "AUG CYCLE · STAGE 2/5" style per the Option B demo in the mockup (uppercase 9.5px/800, `rgba(255,255,255,.06)` pill on the dark bar). C1 builds the component + props only; real period data arrives in Cycle 2.
4. **Demo action** — hidden client action `pb_hub.action_pb_hub_demo` (tag `pb_hub_demo`, no menu/sidebar entry) rendering HubShell with 3 dummy lenses + tracker + dock placeholder. This is your test surface and stays as the kit's living documentation.

## Workstream C — global ⌘K

1. `HubPalette` mounted app-wide via `registry.category("main_components")` (or the webclient patch precedent `pb_sidebar/static/src/js/webclient_patch.js` — pick the cleaner one and note why). UI cloned from the wf_kit palette (same classes metrics, `.pbhub-pal-*` names): search input, grouped rows, ↑↓ / ↵ / esc, footer hints.
2. Global keydown Meta+K / Ctrl+K. **Yield rule**: Mission Control and Formula Studio keep their own ⌘K. Detect and yield — check `event.defaultPrevented` first (verify whether their handlers preventDefault; if not, add a narrow guard, e.g. do nothing when `document.querySelector('.pbms')` / the Studio root is present) — verify both still work, report the mechanism you chose.
3. Entries from `registry.category("pb_hub_palette")`: `{ id, label, sublabel?, icon, group: "Surfaces"|"Admin", action: {tag?|xmlid?, lens?}, groups?: [xmlids] }`, gated with cached `user.hasGroup`. Seed with today's surfaces (audit-verified tags): Dashboard `pb_dashboard`, Approvals `pb_approval`, Run Payroll `pb_payrun_wizard`, Pay Runs xmlid `pb_payruns.action_pb_payruns_kanban`, Payslips `pb_payslip_review`, Results Grid `pb_payrun_results`, Import `pb_import`, Pay & Deliver `pb_pay_delivery`, Full & Final `pb_fullfinal`, Proration `pb_proration`, Retro `pb_retro`, Mission Control `pb_workforce` (+ its 8 lenses as sub-entries via `pb_lens`: today/schedule/time/timeoff/overtime/trips/approvals/close), Formula Engine `pb_formula_studio`, Structures `pb_structures`, Statutory `pb_statutory`, Integrations `pb_integrations`, Insights `pb_insights`, Explorer `pb_explorer_cockpit`, Workforce Analytics `pb_workforce_insights`, Govt Reports `pb_govt_reports`, Bank Verification `pb_bank_ocr`, Young Workers `pb_young_worker`, Learn `learn_journey`, Audit `pb_audit` (payroll-manager group), Tenants `pb_tenants` (Admin group `base.group_system`), Roles & Access xmlid `base.action_res_users` (Admin).
4. Fuzzy-ish filter (substring on label+sublabel is fine), max ~12 visible, keyboard-first.

## Safety rails
- Icons ONLY via `ic()` from pb_import_kit (SVG Lucide) — never emoji, never FontAwesome. New icon names may be added to import_icons.js if missing (report which).
- No gradients on chrome (W3); indigo #5A4BB0 is the only accent (W1); numbers get `font-variant-numeric: tabular-nums`.
- After JS/SCSS changes remember the asset-cache gotcha: bump/regenerate assets on the dev server or hard-reload with assets dev mode — a stale bundle looks like "my code does nothing".
- Odoo 19 gotchas that have bitten before: `res.users` uses `group_ids` (not `groups_id`) in several new-API spots; recordsets are stateless across env rebuilds; writing `ir.ui.view` while the server runs can deadlock — prefer module upgrade; `safe_eval` context needs `nocopy` for mutables.
- Dev/verify ritual: use the same local dev server + DB and the registry-sync gate the Workforce cycles used — the ritual is in the conventions doc / W-ledger (`docs/`). If anything is undocumented, find how the last workforce cycle verified (git log the W-ledger) and do the same; report what you used.

## Tests (run all, paste evidence)
1. Upgrade `pb_sidebar` on the dev DB → SETUP no longer contains "Employee/Contract Mapping" (assert via `get_sidebar_data()` output or UI).
2. SQL/ORM check: no two active `pb.sidebar.item` rows in one section share a sequence (ADMIN now deterministic).
3. Open the connector cockpit (or native connector action) → the rail highlights **Integrations**, not Import Data.
4. `pb_hub` installs clean; `pb_hub.action_pb_hub_demo` renders shell with 3 lenses; switching lens persists across reload (localStorage key `pbhub.demo.lens.v1`).
5. Tracker chip and dock placeholder render in the demo shell; lens gating hides a lens for a user lacking the group.
6. ⌘K on any ordinary screen (e.g. Dashboard) opens the global palette; typing "res" filters to Results Grid; ↵ navigates there; esc closes.
7. Palette deep-link: "Schedule" entry opens Mission Control with the schedule lens active (`pb_lens` protocol).
8. Inside Mission Control, ⌘K opens the *Workforce* palette — not the global one, no double overlay. Same check in Formula Studio (Command Center wins).
9. `pb_mission` smoke: lenses render, Close lens loads, no console errors.
10. Registry-sync gate / server log clean after all upgrades (no tracebacks, no missing-asset 404s).

## Self-review (you are the reviewer — no one else reviews this)
Re-read every new/changed file against this spec after tests pass; specifically check: assets wired in `__manifest__.py`; no `window.confirm`; class prefix `.pbhub-` consistent; palette yield rule can't swallow ⌘K entirely (typing in inputs unaffected — don't hijack when focus is in an editable field unless modifier held… ⌘K with modifier is fine); localStorage keys namespaced. Fix what you find, re-run affected tests.

## Commits
Per feature (explicit staging): (1) fix(pb_sidebar): the three audit fixes + migration; (2) feat(pb_hub): shell kit + demo; (3) feat(pb_hub): global command palette. Reviewer-focused messages. Do NOT push.

## Report back
- pb_hub public API as implemented (props/registry names) — Cycle 2 builds on it verbatim.
- The ⌘K yield mechanism chosen and proof both local palettes still win.
- Any icon names added; any deviations from spec + why; new gotchas appended to the conventions ledger.
- Test evidence for all 10 tests.
