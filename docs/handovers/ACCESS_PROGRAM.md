# ACCESS program — one home for access management

Status: DESIGN (started 2026-09-02). Owner picked **Option A "One home, three lenses"** from the
prototype artifact "Access, one home" (3 options, Chrome-validated). Phased Fable-designs / Opus-builds
cycle confirmed by owner.

## Vision (owner-approved)

Replace the three scattered access surfaces with ONE Access home:

1. Settings → Access & delegation (pb_vendor_access board — loved, kept as the front door)
2. Settings → Navigation → Sidebar items/sections (raw allowed-groups list — absorbed)
3. Cybrosys `access_roles` app (unused island — **retired/uninstalled**)

The home has three lenses over the same truth plus a builder:

- **Roles lens** — today's plain-English role cards, each expandable into: screens it opens /
  what it lets them do / who holds it.
- **People lens** — person picker → passport: a live miniature of the left rail exactly as that
  person sees it, roles held with why (held / lent-until), grant & take-back.
- **Screens lens** — the rail drawn as the rail; each entry shows the roles that unlock it, who
  sees it and why, sub-screen gates, active toggle, reorder.
- **"See it as…" simulator** — header person picker repaints all lenses to that person's reality.
- **Role Composer** — new role = name + one honest sentence + tick plain-English abilities
  (each ability maps to curated res.groups); live mini-rail preview lights up as you tick.

Reference prototype: https://claude.ai/code/artifact/fdd1a0ca-d731-4481-ac8f-4492bff0953c
(demo data, but the interaction model and layout are the spec).

## Owner rulings (binding)

1. **Role = bundle.** `1 role = 1 group` (today's pb.role.profile) grows to a named bundle of
   one or more res.groups + the screens it unlocks, fronted by one plain-English sentence.
   Raw group names never appear in any user-visible string.
2. **Cybrosys `access_roles` is retired.** Recommend uninstall on all DBs (unused; role-apply
   hard-SETs users' groups wiping out-of-role groups; ACL grants base.group_user full CRUD on
   access.role/role.management). Nothing new may depend on it. Its useful *ideas* (menu hiding,
   debug kill) are rebuilt natively where a phase calls for them.
3. **Generic module.** The home ships product-agnostic (neutral strings, soft registries, seeds
   nothing); the product overlay (Payobook) seeds the role catalogue, ability→group map, and
   area vocabulary. Owner will reuse it in another left-rail application.
4. **Two-tier admin rails** (owner Q&A 2026-09-02):
   - Tenant walls are structural (DB-per-tenant SaaS) — not this program's job.
   - A tenant administrator holds ROLES only (e.g. Access manager + Navigation editor), never
     base.group_system / base.group_erp_manager. The master key can never be put inside a role
     (constraint + facade checks + seed audit — pb_vendor_access already enforces this 3-way,
     carry it forward to bundles: NO group in a bundle may be or imply a forbidden group).
   - **Rail A: hard server-side block on debug mode** for anyone but the master key.
   - **Rail B: automated catalogue audit test** — no seeded ability may map to (or imply) a
     platform-level group.
   - **Rail C: Settings hub split** — tenant admins see only the cards their roles allow;
     platform-level cards (Companies & Tenants, technical) remain super-admin only.
5. Safety rails carried over from pb_vendor_access: lend-only-what-you-hold, delegation
   audit trail (no unlink), auto-revert cron, transitive holder counts (`all_group_ids`).
6. Standing rules apply: no "Odoo" in any user-visible string; plain-English UI copy (the
   screen's vocabulary); Lucide icons via shared `ic()` registry; pbim design tokens; no
   gradients/emoji; WOW bar verbatim in every phase handover.

## Existing plumbing (verified 2026-09-02 — do not re-derive)

- **pb_vendor_access** (RIZE P11): `pb.role.profile` (models/pb_role_profile.py:41) — name,
  `group_id` M2o res.groups unique, description translate, area, visible_group_id, computed
  holder_count via transitive all_user_ids. `pb.access.delegation` (models/pb_access_delegation.py:51)
  — lend/auto-revert/audit. Facade `pb.access` (models/pb_access_facade.py:51) — get_board :92,
  grant :235, remove :273, delegate :346, revoke :393. 23-role seed in hooks.py CATALOGUE :49.
  Forbidden groups in models/vendor_common.py FORBIDDEN_GROUP_XMLIDS :83. Cockpit
  `pb_access_board` (static/src/js/access_board.js, xml/access_board.xml, scss/vendor_access.scss
  — 1226 lines, pbim tokens, `.pbva-*` prefix).
- **pb_sidebar**: `pb.sidebar.section`/`pb.sidebar.item` (models/pb_sidebar.py:6/:27); item
  `groups_id` m2m :45, `restricted` upsell :51; server-side visibility in get_sidebar_data() :63
  (admin sees all; empty groups = everyone; locked teaser vs hidden; locked items' actions
  blanked :96-98). Rail is action-xmlid/tag based, NO ir.ui.menu link; native menus CSS-hidden
  (scss :9-10). Settings hub entry pb_settings/static/src/js/settings_hub.js:192-204.
- **access_roles** (Cybrosys): access.role m2m groups (models/access_role.py:67); DANGER
  _update_users_groups :268 Command.set wipes non-role groups; role.management hides menus via
  _visible_menu_ids subtraction (ir_ui_menu.py:48), injects ir.rule domains (ir_rule.py:32),
  is_debug/chatter kills via JS patches. ACL hole: security/ir.model.access.csv grants
  base.group_user full CRUD. Nothing in pb_*/biz_* depends on it.
- Odoo 19: `groups_id`→`group_ids` on res.users; use `all_group_ids`/`all_user_ids` for
  transitive membership (see docs + odoo19 gotchas ledger).

### Settings hub gating (verified 2026-09-02)
- Soft registry `SETTINGS_CATEGORIES = "pb_settings_category"` (settings_hub.js:232); descriptor
  `{key, icon, label, blurb, groups:[xmlids], cards:[…]}`; shipped CATEGORIES :108; only
  pb_vendor_access/vendor_palette.js pushes extras (:78 vendors, :95 access).
- Gating is 100% CLIENT-side: `_resolveGroups()` :322 via `user.hasGroup`, ANY-of semantics,
  **fails OPEN** for unresolvable xmlids (:329). ADMIN = ['base.group_system'] (:88/:94), used by
  payroll :161, roles :172, org :182, nav :195 categories. No server-side category filter; the
  hub is explicitly not a security boundary (header :22-24) — target actions' ACLs are.
- Card existence probe: client action registry + `pb.settings.resolve_actions` RPC
  (pb_settings/models/pb_settings.py:33). `soleCard()` :409 collapses 1-card categories.
- To gate on "holds role X": a role wraps a group, so it drops into `groups` unchanged. AND-gates
  or server-authoritative gating need `_resolveGroups` edit or a `resolve_gates` RPC (Rail C work).

### Tenant provisioning (verified 2026-09-02) — ⚠ KEY FINDING
- pb_tenants provisioning (models/service.py, PROVISION_STEPS ~:82) creates NO user and assigns
  NO groups. `_step_admin` :583-609 re-writes the clone's pre-existing `base.user_admin`
  (name/login/email/generated password/active:True + action_id). Template DB (`payobook_template`)
  ships that admin ARCHIVED (comment :592-596).
- **Therefore every tenant administrator today IS base.group_system + base.group_erp_manager**
  (inherited from the template's admin user). The two-tier rail does not exist yet — Rail work
  must change what the tenant admin account holds (template change + provisioning step), not just
  hide UI. Platform super-admin vs tenant admin are distinguished ONLY by which DB they're in;
  pb_tenants itself is platform-DB-only and _require_admin-guarded (:138).

### Debug-mode + chrome seams (verified 2026-09-02)
- Debug is decided in vendored core web/models/ir_http.py: `_handle_debug()` :46 writes
  `request.session.debug` from `?debug=` (called from `_pre_dispatch` :58); session_info
  `bundle_params.debug` at :133/:193. **Rail A = ir.http override clearing session.debug for
  non-super-admins** (+ optionally suppress in session_info). No custom module touches either today.
- Natural host: biz_theme/models/ir_http.py:7 already overrides session_info (adds biz_* keys).
  ⚠ Before adding any new ir.http inherit, read biz_deroute/models/ir_http_session_guard.py —
  it monkey-patches hr_timesheet's session_info instead of inheriting, to avoid dragging that
  class into the registry (ordering hazard documented in-file).
- Cybrosys is_debug kill is client-only cosmetic (alert + pushState in debug.js) — NOT a model.
- Apps menu is NOT hidden — biz_theme restyles it (apps_menu.xml); visibility is stock
  base.group_system. pb_sidebar CSS hides only o_menu_sections/o_menu_brand. The user-menu
  "Activate developer mode" items are NOT removed anywhere. /bizapp routes have no group checks
  (?debug=1 survives the /odoo→/bizapp 301) — enforcement is (and stays) action/model ACLs +
  the new Rail A.
- pb_sidebar `_has_access` :76: base.group_system SHORT-CIRCUITS every item gate (admin sees all).
  The Settings rail item carries NO groups_id (pb_settings/data/pb_sidebar.xml:28) — visible to
  all; only the hub's empty state guards it today.

### Group inventory (verified 2026-09-02) — full detail in the P1 handover
- 64 custom groups across 21 modules. Odoo 19: grouping is `privilege_id` (res.groups.privilege),
  NOT category_id — the 5 country payroll modules still set category_id directly (legacy/broken).
- The 23-role CATALOGUE (pb_vendor_access/hooks.py:51-165) wraps exactly 23 groups; **41 custom
  groups are uncovered**, including the ones most screens actually gate on.
- ⚠ **Two disconnected payroll ladders**: `om_hr_payroll.group_hr_payroll_user/manager`
  (implies hr.group_hr_user + hr_contract.group_hr_contract_manager) vs
  `pb_hr_payroll_base.group_payroll_base_*` ladder. Neither implies the other. The role catalogue
  covers the pb_hr_payroll_base ladder, but per-module sidebar items + most record rules gate on
  om_hr_payroll.* and hr_attendance.* → a role-only user sees a partial sidebar today.
- Sidebar gating split: master data file uses pb_hr_payroll_base.*; per-module contributions use
  om_hr_payroll.* / hr_attendance.*; 10 of 15 per-module items are UNGATED; `item_roles`
  (Roles & Access) gates on base.group_system, not pb_vendor_access.group_access_manager.
- pb_payroll_ai_insights makes base.group_user imply group_payai_user (every internal user,
  deliberate, reapplied on upgrade — payroll_ai_security.xml:92).
- base.group_erp_manager is never granted anywhere; FORBIDDEN_GROUP_XMLIDS already covers it.
- Load-bearing standard groups: base.group_user, base.group_system (~15 ACL files + 4 sidebar
  items + facade gates), hr.group_hr_user/manager, hr_contract.group_hr_contract_manager,
  hr_attendance.group_hr_attendance_officer/manager, base.group_portal, hr_holidays user.

### P1 design decisions (Fable, 2026-09-02)
1. Evolve pb_vendor_access IN PLACE (extraction to a generic biz_access module stays P6).
2. **Ability layer**: new model `pb.role.ability` = plain-English ability wrapping ≥1 res.groups.
   Roles hold `ability_ids`; role `group_ids` = stored compute (union of ability groups). Legacy
   `group_id` column kept but frozen (nullable, no new reads). No raw-group escape hatch — odd
   groups become abilities (abilities are data).
3. Migration: each of the 23 roles → one same-named ability wrapping its old group. Plus ~12 new
   abilities covering the load-bearing uncovered groups (om_hr_payroll ladder, hr_attendance
   officer/manager, audit reader, analytics manager, integration user, formula tiers, workforce
   demand tiers, learn author). NOT covered in P1 (owner debts): country "Enabled" toggles,
   hr_development_ai/BFSI, pb_demo, driver, pb_hr_workforce_planning second ladder, payai
   (auto-granted), and any ladder unification.
4. Rail B lands in P1: audit test walking the transitive implied closure of every seeded
   ability — none may reach base.group_system / base.group_erp_manager.
5. Facade RPC shape unchanged in P1 — the existing board must keep working untouched.
   Holder of a bundle = holds ALL its groups (transitive); lend requires holding ALL.

### Design implication of the key finding (for P5, decided by Fable)
The "tenant administrator" must become a defined ROLE BUNDLE (access-manager + nav-editor +
payroll/people admin abilities…) and the golden template's admin user must stop carrying
base.group_system for tenant clones — either a demote step in provisioning (_step_admin writes
group memberships) or a second, non-system "customer admin" user in the template. This touches
provisioning + template DB + every base.group_system gate that tenant admins currently rely on
(sidebar short-circuit, settings hub ADMIN categories, native Settings app access). P5's handover
must enumerate those reliance points and re-gate them on the tenant-admin bundle. Owner-visible
consequence to confirm before P5 ships: existing tenants' admin accounts get demoted by a
migration — needs owner sign-off at that phase (listed as a deploy-time decision).

## Phase map (draft — refined per phase as reports come back)

- **P1 — Role bundles.** `pb.role.profile.group_id` → `group_ids` bundle (migration keeps the
  23 seeds as 1-group bundles), abilities model + ability→group catalogue, facade + constraints
  updated (forbidden check over implied closure), catalogue audit test (Rail B).
- **P2 — The home, Roles lens + Composer.** Board becomes the three-lens home shell; role cards
  gain the 3-column expansion; Role Composer with live mini-rail preview.
- **P3 — People lens + simulator.** Passport (mini-rail as-they-see-it, roles with why,
  grant/take-back inline), "See it as…" simulator across lenses.
- **P4 — Screens lens.** Rail editor drawn as the rail (role chips, who-sees-and-why,
  sub-screen gates, reorder, active/teaser) — replaces the raw Sidebar items/sections lists;
  pb_sidebar items gain role-aware gating UI (storage stays res.groups underneath).
- **P5 — Tenant-admin rails.** Debug block (Rail A), Settings hub split (Rail C), tenant-admin
  role bundle definition, verification against a tenant DB.
- **P6 — Genericize + retire.** Extract/rename generic layer (biz_access) with product overlay
  seeding; Cybrosys uninstall across DBs (owner confirmed direction; actual uninstall is a
  deploy-time step with its own backup); full 4-DB deploy + validation + closeout.

Exact module architecture (evolve pb_vendor_access in place vs. new biz_access from P1) is a
P1 design decision, taken after the group-inventory report.

## Ledger

(gotchas and rulings appended as phases run; every handover references this file)

### P1 CLOSED 2026-09-02 — role bundles + ability layer (commit a347407a, not pushed)
All 8 numbered tests PASS; deployed pb_vendor_access 19.0.1.1.0; live board byte-identical
(before/after get_board() diff SAME on a rehearsal clone). Facts now true:
- A1. `pb.role.ability` exists; roles hold ability_ids; `group_ids` stored-computed union.
  35 abilities seeded (23 role-backing derived from CATALOGUE via ROLE_ABILITY_GROUPS —
  one source of truth per sentence — + 12 dormant). Seed still writes frozen group_id for
  single-group roles (keeps fresh == migrated).
- A2. **post_init_hook does NOT fire on `-u`** (loading.py update_operation=='install' only).
  Catalogue changes need their OWN migration each time — P1 added
  migrations/19.0.1.1.0/post-role_bundles.py (calls ensure_catalogue + SQL sanity count).
  EVERY later phase that adds abilities/roles must ship a migration step.
- A3. Transitive maths: use `res.groups.all_implied_ids` (REFLEXIVE closure, includes self)
  via `vendor_common.implied_closure()` (has a hand-walk fallback); `all_user_ids` =
  all_implied_by_ids.user_ids; `res.users.all_group_ids` = group_ids.all_implied_ids.
- A4. `remove()` is now the safe version: keeps groups still required by another FULLY-held
  role; refuses (plain-English error) when nothing would change. Pre-P1 the hazard couldn't
  arise (unique group_id).
- A5. `_activate_one` subtracts what the delegate already transitively holds at WRITE time;
  applied_group_ids stays exactly-what-was-added.
- A6. `ensure_bundles()` sweep: admin-created roles get their own 1-group ability (matched by
  own key only — never reuse an ability that merely contains the group: it would widen access).
- A7. Plain fallback role form/list shows abilities + worked-out permissions read-only; ability
  list/form views exist (no menu/action/rail entries added).
- A8. ⚠ Server cron loop picks up EVERY database on the cluster — test clones get crons run
  against them. Clone briefly, drop promptly.
- A9. ⚠ OWNER DEBT/DECISION (for P5/P6): pb_vendor_access is installed on `payobook` ONLY —
  abm/acme/payobook_template don't have it. For the Access home to reach tenants it must be
  installed on the template (+ existing tenant DBs). Product decision, parked.

### P2 CLOSED 2026-09-02 — home shell + Roles lens + Composer (commit b83ecf42, not pushed)
All 9 numbered tests PASS; pb_vendor_access 19.0.1.2.0 live; 37 new tests (suite 79/79).
- B1. Shell has `LENS_REGISTRY` — Roles + Hand-overs are lenses (Hand-overs kept, good call);
  P3/P4 add one entry each. Mini-rail is a reusable OWL sub-component in the module.
- B2. Derivation live and proven (temporary gated entry → exact chip). Holder rows use
  `avatar` (existing R82 convention) + `by` + `delegation_id`.
- B3. Lent roles show "End the hand-over" (revoke), never "Take back" — removing a role from
  a borrower would orphan the loan record. Keep this pattern everywhere.
- B4. Composer: area picker is CHIPS (select re-render unreliable in OWL); Escape bound on
  CAPTURE (web client hotkeys swallow bubble-phase Escape); duplicate name = plain refusal;
  preview/create report how many people already hold everything the bundle grants.
- B5. ⚠ DEPLOY RITUAL ADDITION: after JS/SCSS deploy, attachment purge alone is NOT enough on
  this box — the immutable /web/assets/<unique>/ URL gets reused, browsers keep old bundles.
  **Bump `web.assets.version` ir.config_parameter per DB** after the purge. (Done on payobook.)
- B6. ⚠ FINDING: the 9 ACTIVE left-menu entries carry ZERO allowed-groups (the 104 group links
  sit on entries archived in the IA redesign). Every role's "opens" column shows the honest
  empty state until P4 re-gates the live rail. Also means today: every internal user sees the
  whole rail.
- B7. ⚠ DEBT (fix in P4): mutual-cover removal deadlock — two roles with identical effective
  groups both refuse removal ("take the other away instead"); workaround archive. P4: composer
  warns on creating an identical-effective-bundle role + improve the mutual-cover message.
- B8. Raw group names no longer appear anywhere on role cards (old "This is the permission
  group X" line removed).
- B9. Validation leftovers on payobook: 2 un-deletable audit rows (by design) from the
  temporary P2 validation role (archived). Cosmetic, known.

### P3 CLOSED 2026-09-02 — People lens + passport + simulator (commit 86cafc69, not pushed)
9/9 tests PASS (one caveat: 2 PRE-EXISTING pb_sidebar data-assertion failures on
payobook_template only — module-set drift, not logic; debt below). pb_vendor_access 19.0.1.3.0
live; suite 105/105 on payobook.
- C1. pb_sidebar now has ONE structural visibility rule: `_access_of` + `_state_for` methods +
  public `visibility_for(user)` (returns every item incl. hidden + section locks);
  get_sidebar_data uses the same methods. Anything touching visibility goes THROUGH these.
  pb_vendor_access already depends on pb_sidebar (P2). pb_sidebar left un-`-u`'d on payobook
  (Python-only change; manifest version unchanged, repo==DB).
- C2. ⚠ **pb_sidebar data files are `noupdate="0"` — any `-u` of a module shipping rail rows
  RE-ASSERTS those rows from the shipped XML.** Proven on payobook_template (48 items + 10
  sections re-asserted during test runs). Consequence for gate changes: new gates MUST be
  written into the owning modules' shipped data XML as well as applied to live rows, or a
  future upgrade wipes them.
- C3. Passport grant dialog is person-first (role picked from not-yet-held list, sentence
  shown before the button). `callName()` handles Vietnamese call-names + strips bracketed
  suffixes. PEOPLE_CAP=200 (search past it). Mini-rail gained a section-level lock marker.
- C4. SCSS gotchas: `.pbva-pick/.pbva-picker` styles are scoped UNDER `.pbva-modal-scrim`
  (W66) — header/other contexts must carry their own row styles; media queries measure the
  WINDOW while the pane is 256px narrower — set breakpoints generously.
- C5. Non-manager lockdown is server-side in `_person()` (people() returns self only; passport/
  as_user for others raise). Simulator is view-only — proven by a grant-while-simulating test.
- C6. DEBT: 2 pre-existing pb_sidebar test failures on payobook_template (missing
  payroll_report_dashboard claim + pb_import tag — module-set drift 197 vs ~224 modules).
  Fix or scope the tests in a later phase.
- C7. More un-deletable audit residue on payobook (RIZE P6 Plain grant/take-back validation) —
  same class as B9, cosmetic.

### P4 CLOSED 2026-09-02 — Screens lens + the live re-gate + the B7 fixes (commit 2f7a7a4a, not pushed)
10/10 numbered tests PASS. pb_vendor_access 19.0.1.4.0; pb_sidebar 19.0.3.1.0; pb_settings
19.0.1.5.0; the hub modules bumped. Live payobook rail GATED (7 entries, 28 role links; the
per-user diff and entry-xmlid/file map are in the P4 report). Additional owner note: only
ash@biztinct.com holds "Access team", so every non-administrator sees Settings as a locked
teaser; granting the role is two clicks in the lens. Pre-existing failures unchanged (pb_learn
anchor-registry on live; the C6 template pair). Facts now true:
- D1. `pb.sidebar.item.role_ids` (m2m `pb_sidebar_item_role_rel`) is added by
  **pb_vendor_access**, not by pb_sidebar — the left menu stays generic. The lane plugs
  into the ONE rule (C1) by overriding `_state_for`; passport, Screens lens, simulator and
  the real rail all move together. Two lanes, read as an OR.
- D2. ⚠ **`active_test` does NOT reach into a many-to-many read.** An archived role went on
  opening its entry until `.filtered('active')` was added by hand. And "is this entry gated
  at all" must be asked of the RAW list (archived included) — asking the ACTIVE list makes
  archiving the last role on an entry open it to the whole company, because the rule
  underneath is "no permissions and no roles means everybody". Two helpers on purpose:
  `_gate_roles_raw` (is it gated) and `_gate_roles` (who gets through).
- D3. Shipped gate XML uses `(4, ref(...))`, never `(6, 0, ...)`. A REPLACE would drop the
  demo group `pb_demo` joins onto every gated entry on each `-u`. Taking a permission back
  off an entry is therefore a migration — the only direction that can fail is the safe one.
- D4. ⚠ **pb_demo's `_pb_demo_rewire` runs at pb_demo's turn in the cascade**, so on the run
  that FIRST gates an entry it may see that entry still ungated and skip the demo join
  (People/Lifecycle got it, Pay Run/Workforce/Insights/Compliance did not). Fix: a SECOND
  `-u pb_demo` pass after the main upgrade. Idempotent; needed once per newly-gated entry.
- D5. Settings is gated on the "Access team" ROLE ALONE (no permission lane — the hub is
  explicitly not a security boundary) + `restricted=True`, so everybody else sees it locked
  with an honest note shipped in `pb_settings/data/pb_sidebar.xml`. Consequence on payobook:
  every non-admin now sees Settings as a teaser. base.group_system still short-circuits.
- D6. Settings → Navigation is re-pointed by a new generic seam: a registered category whose
  key matches a shipped one REPLACES it in place (`allCategories`). pb_vendor_access
  registers `nav` → one card opening the Access home on the Screens lens (`pb_lens` context,
  hub_nav's own key). On a database without pb_vendor_access the two raw lists stay.
- D7. Rail refresh = `env.bus.trigger("PB_SIDEBAR:RELOAD")`; pb_sidebar listens and re-asks
  `get_sidebar_data`. A bus event, not an import — pb_sidebar knows nothing about roles.
- D8. B7 closed: identical-effective-bundle create refused by name; the mutual-cover removal
  refusal now NAMES the other role and offers archiving; `archive_role` refuses at >0 holders
  (naming them) or a running hand-over, and reports the entries it was the only key to.
- D9. ⚠ Two pre-existing gate tests had to be amended, and both were maintenance landmines:
  `pb_sidebar` asserted its manifest was literally `19.0.3.0.0` (now an inequality over the
  migration directories), and `pb_settings` asserted the literal `...CATEGORIES` spread.
  `pb_learn`'s payroll-manager reachability probe now also holds `hr.group_hr_user`, which is
  what every real payroll manager on this product holds.
- D10. Per-user before/after diff on live payobook: 15 of 45 people lose an entry, all of
  them holding NONE of that entry's permissions (0 violations, proven); 26 demo-group holders
  keep everything after the D4 pass; only the 2 administrators keep Settings open.

### P5 CLOSED 2026-09-02 — tenant rails (commits f53d9d2e rails, cc58cf34 bundle+provisioning; not pushed)
8/8 tests PASS. biz_theme 19.0.1.5.0 (×4 DBs), pb_settings 19.0.1.6.0, pb_vendor_access
19.0.1.5.0 (payobook+template), pb_tenants 19.0.1.3.0. Real tenants proven untouched
(payobook's 326 user-group links byte-identical; no group_system holder's write_date moved).
- E1. Rail A = `_inherit ir.http` in biz_theme (outermost is correct here; biz_deroute's
  hazard was about patching INTO another module's class — didn't apply). TWO extra seams the
  spec missed: (a) at `_pre_dispatch` the env may not be on the user on /bizapp — read
  `request.session.uid`; (b) ⚠ web's login controller copies `?debug=` into the page and
  could render a "Log in as superuser" button on the white-labelled sign-in — closed via a
  second seam in `ir.qweb._prepare_environment`. No user-menu dev-mode item exists on 19.
- E2. Rail C is server-authoritative (`resolve_gates`), fails CLOSED on platform categories —
  proven against a forged RPC. pb_settings NOT installed on acme → Rail C absent there (debt).
- E3. Tenant administrator bundle = 16 abilities incl. access-team (required) — growth-plan
  abilities DELIBERATELY excluded (coaching-plan privacy; tenant admin can grant them
  explicitly, audited). Seeding is CREATE-ONLY: an upgrade never widens a role somebody holds.
- E4. Template readiness: 197→203 modules (pb_assets/pb_budget/pb_insights_hub/pb_lifecycle/
  pb_vendor_access/pb_zoho_bridge), rail entries 3→5, A9 CLEARED for the template. ⚠ The
  template had NO active administrator (ships archived) — user creation was impossible in
  clones (87 test errors); `prepare_template_for_rails()` fixed it repeatably. C6 pair now
  ONE failure (pb_import claim), not two.
- E5. Recovery account: ACTIVE but passwordless + no email (an archived one can't exist —
  a DB must have an active admin; nothing to guess, resets have nowhere to go).
- E6. The flip = `pb.tenants.apply_tenant_admin_rails(dbname, dry_run=True)` on the platform
  DB. Nothing calls it. Refuses: platform DB, template, protected logins (owner's address;
  on abm that IS the customer admin), DBs without the Access home. Rehearsed on an acme clone
  (lan@acme.com demoted cleanly). ⚠ OWNER DECISION OPEN: when/whether to flip abm + acme.
- E7. OWNER QUESTION (later): Companies & Tenants stays platform-only, so a tenant admin
  cannot rename their own company — revisit if customers ask.
- E8. Residue: p5.tenantadmin@/p5.systemadmin@ archived throwaway accounts on payobook
  (B9/C7 class).

### P6 CLOSED 2026-09-02 — the generic split, the retirement, the debt sweep
(commits 3d43001b split, d68ed290 retire, 4457756c debts; not pushed)
All 8 numbered tests PASS. `biz_access` 19.0.1.0.0 NEW (payobook + template);
pb_vendor_access 19.0.1.6.0. 517 tests green on a payobook clone; 494/499 on a
template clone (the 5 are pre-existing pb_learn drift). Closeout:
`docs/handovers/ACCESS_CLOSEOUT.md`. Facts now true:
- F1. ⚠ **A `pre_init_hook` is the ONLY place a module extraction can re-home
  `ir_model_data`.** `loading.py:171` runs pre-migrations for `to upgrade`
  only, so the NEW module never gets one; but `:180` runs its `pre_init_hook`
  before `registry.load()` and before any data file. Left unmoved, the new
  module's data load CREATES DUPLICATES of every moved record (a second
  access-team group with nobody in it) and `_process_end` then deletes the
  originals. `biz_access.hooks.pre_init_hook` moves 28 named xmlids by an
  EXPLICIT LIST (never a prefix — the old module still owns records whose
  names start the same way), plus model_/field_/constraint_ ids by shape, plus
  `ir_model_relation.module` for the 6 m2m tables (an uninstall DROPS relation
  tables registered to the module being removed).
- F2. `ir.model.data._process_end` has a safety worth knowing:
  "if the record has other associated xids, only remove the xid". So
  auto-generated `model_*`/`field_*` ids self-heal on an extraction even
  without F1 — but XML-defined records (groups, rules, ACLs, views, actions,
  crons, mail templates) do NOT, which is what F1 exists for.
- F3. Making `area` a CALLABLE Selection deletes its `ir.model.fields.selection`
  rows on upgrade (10 of them here). Harmless — the stored varchar values are
  untouched and group-by/export read the live registry — but it shows up as
  "Deleting …" in the log and should not be mistaken for data loss.
- F4. The soft-registration pattern for an extracted module, both halves:
  server `register_areas` / `register_manager_groups` / `register_catalogue` in
  `access_common.py` + `hooks.py`, browser `registerAccessManagerGroups()` in
  `access_palette.js`. Gate lists are MUTABLE MODULE-LEVEL LISTS read at call
  time, so a registration made after the facade was imported still counts.
- F5. SCSS split at top-level selector boundaries only. The shell, the dialogs,
  the mini-rail and the area/state colour maps stay in the generic file (loaded
  first by dependency order); the overlay ships only its own block and
  re-declares `$pbva-states` with `!default` so it is a no-op when the two are
  compiled together and still correct if they ever are not.
- F6. ⚠ **`odoo-bin --test-enable` without `--http-port` STEALS PORT 8069** and
  serves the wrong database to the live domain (real users got 500s for ~14
  min). Always pass `--http-port=8099 --gevent-port=8098` for any test or
  one-off run while the service is up.
- F7. ⚠ `sudo service odoo-server stop` can leave an ORPHAN `odoo-bin` holding
  connections (the documented LSB/systemd hazard). Check `ps` and kill BY PID
  before starting an upgrade; `dropdb` also fails while the cron worker holds a
  clone, so `pg_terminate_backend` first (ledger A8 again).
- F8. Cybrosys retirement measured: `role.management` had ZERO rows on all four
  DBs (nothing was hiding a menu or injecting a domain); 1 `access.role` row on
  payobook only. Uninstall dropped 23 tables + the `res_users.access_role_id`
  column, left 0 external ids, and removed only its own 2 groups — no user lost
  an effective permission. 4 orphaned `access_roles.sync.*` config params had to
  be deleted BY HAND afterwards (an uninstall does not clean `ir_config_parameter`).
- F9. Boot delta was small (7.45s→6.66s wall, 5.60s→5.14s registry) because the
  F4 registry-sync gate had already removed the expensive part.
- F10. ⚠ **A brand-new database cannot be built from this repo at all** (found
  while proving the generic module stands alone). Three independent pre-existing
  breakages: `hr_contract/data/hr_contract_data.xml` references
  `resource.resource_calendar_std_38h`, which lives in resource's DEMO file;
  `om_hr_payroll` needs `report_xlsx` without declaring it; and
  `om_hr_payroll/views/hr_contract_views.xml` references
  `pb_hr_flow.action_hr_flow_wizard` — a module that DEPENDS on om_hr_payroll,
  so the reference can never resolve on a fresh install. The generic-install
  proof was therefore done on a clone of a tenant with no product overlay
  (`biz_access` alone → empty neutral home, 0 roles, 0 abilities).
- F11. `biz_access` still depends on the Payobook chassis (`pb_settings` →
  `om_hr_payroll` + `pb_hr_payroll_base`), so "generic" today means "no product
  vocabulary", not "no product dependencies". Owner debt D4 in the closeout.
- F12. The composer comparison (P2 deferral B7-adjacent) is derived ENTIRELY in
  the browser from `composer_options` — every role's ability list is already in
  what the builder read to open itself, so it costs no round trip. Anchor on
  `fromId` when the role was started from another one; otherwise the greatest
  Jaccard overlap; silence when nothing is shared.
