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

PENDING exploration (two agents out): settings-hub gating mechanics + tenant provisioning +
debug seams; full custom res.groups inventory + role-coverage cross-reference. Their findings
land in this file before Phase 1's handover is written.

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
