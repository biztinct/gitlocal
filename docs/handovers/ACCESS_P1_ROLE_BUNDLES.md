# ACCESS P1 — Role bundles + the ability layer (model groundwork)

Read FIRST: `docs/handovers/ACCESS_PROGRAM.md` (vision, owner rulings, verified plumbing,
group inventory context). This phase is pure model/data groundwork: after it ships, the
existing Access & delegation board must look and behave EXACTLY as before — but underneath,
a role is now a bundle of abilities, each ability wrapping one or more res.groups.

Design bar (verbatim, binding on all phases): **extreme WOW, intuitive, out-of-this-world,
best in class**. P1 has no UI, so the bar lands on the quality of the plain-English ability
copy and the invisibility of the migration.

White-label rule (binding): the word "Odoo" must NEVER appear in any user-visible string
(field `string=`/`help=`, labels, messages, logs shown to users). Technical identifiers
(`from odoo import`, xmlids) are untouched. All new user-visible copy in plain English —
the screen's vocabulary, no internal jargon.

## Scope

1. New model `pb.role.ability` in `pb_vendor_access`.
2. `pb.role.profile` grows `ability_ids`; `group_ids` stored compute (union of ability groups).
3. Facade + delegation logic updated to bundles; **RPC response shapes unchanged**.
4. Seed: 23 abilities backing the existing 23 roles (1:1) + 12 new dormant abilities.
5. Migration for existing DBs (4 of them) — zero visible change on the board.
6. Rail B: the catalogue audit test (forbidden-group closure).
7. Deploy to the live server, upgrade all 4 DBs, verify.

## Binding NON-goals (do not touch)

- NO UI changes: `access_board.js/.xml/.scss` stay byte-identical unless a facade rename
  forces a call-site change (it must not — keep the facade API stable instead).
- NO pb_sidebar changes, NO settings hub changes, NO debug/session work (P4/P5).
- NO removal of `access_roles` (Cybrosys) — P6. Do not depend on it either.
- NO new roles (the 23 stay 23; new abilities stay dormant until the P2 composer).
- NO retyping/unification of the two payroll ladders or country "Enabled" groups (owner debt).
- Do NOT drop `pb.role.profile.group_id` or its unique constraint — freeze it (nullable stays
  as-is, no new code reads it after migration).

## Verified plumbing (do not re-derive)

- `pb.role.profile` — pb_vendor_access/models/pb_role_profile.py:41. Fields: name :46,
  `group_id` M2o res.groups required :50 (make optional, frozen), description translate :55,
  area :59, sequence :62, visible_group_id :64, holder_count computed non-stored :73
  (`_compute_holders` :83 uses `group.all_user_ids`; `_search_holder_count` :105; `holders(cap)` :167).
  `_group_uniq` unique(group_id) :77. Forbidden-group constraint
  `_check_group_is_not_the_keys_to_the_building` :135.
- `pb.access.delegation` — models/pb_access_delegation.py:51 (mail.thread). `profile_ids` m2m :65,
  `applied_group_ids` (exactly what was added, measured at activation) :89, `unlink()` refused :148,
  `action_activate` :162, `_groups_to_hand` "lend only what you hold" :214, forbidden re-check :225,
  `action_revoke` :257, `cron_auto_revert` :349.
- Facade `pb.access` (AbstractModel) — models/pb_access_facade.py:51. BOARD_GROUPS :42,
  MANAGE_GROUPS :44, base.group_system gate :57. get_board :92, _profiles :107, _areas :147,
  _mine :156, _delegations :167, _kpis :212, _headline :225, grant :235, remove :273,
  delegate :346, revoke :393, user_options :420, exports :437/:442.
- Constants — models/vendor_common.py: PROFILE_AREAS :48, DELEGATION_KINDS :57,
  FORBIDDEN_GROUP_XMLIDS = ('base.group_system','base.group_erp_manager') :83, HOLDER_CAP=40 :95.
- Seed — hooks.py: CATALOGUE :51-165, tuples `(group_xmlid, area, sequence, name, description,
  visible_xmlid)`; `ensure_catalogue()` :168 (skips missing xmlids with a log); post_init_hook :213.
  ⚠ Verify how ensure_catalogue re-runs on module UPGRADE (post_init only fires on install);
  if it doesn't, add an upgrade path (migration script calling it) — report what you found.
- Security — security/pb_vendor_access_security.xml (rule_profile_visible :187 on visible_group_id;
  untouched) + security/ir.model.access.csv (add lines for the new model; perm_unlink pattern:
  delegations are 0 for everyone — abilities may allow unlink only for group_access_manager).
- Odoo 19: use `all_group_ids` / `all_user_ids` for anything transitive; res.users m2m is
  `group_ids` (NOT groups_id). `res.groups` has `implied_ids`; full closure = `all_implied_ids`
  if present on this build — verify which transitive field exists and use it (report back).
- Existing tests to keep green: pb_vendor_access/tests/ (whole dir), pb_settings/tests/test_settings.py.

## Architecture

### `pb.role.ability` (new file models/pb_role_ability.py)
- `name` Char required translate — plain-English label ("Approve a pay run" style: verb first).
- `description` Char translate — one honest sentence, same voice as role descriptions.
- `area` Selection(PROFILE_AREAS) required; `sequence` Integer.
- `group_ids` M2m res.groups required — what this ability actually grants.
- `technical_key` Char required, unique — stable key for seeds/migrations (kebab-case).
- `active` Boolean default True.
- Constraint (clone of the profile's): no group in `group_ids` nor anywhere in its transitive
  implied closure may be a FORBIDDEN_GROUP_XMLIDS group. Same guard again at the facade layer
  for anything that writes abilities.
- _order: 'area, sequence, name'.

### `pb.role.profile` changes
- `ability_ids` M2m pb.role.ability.
- `group_ids` M2m res.groups, **stored compute** from ability_ids (union), depends on
  ability_ids and ability.group_ids; readonly in UI terms (no direct writes outside the compute).
- `group_id`: required=False; after migration nothing reads it. Keep the constraint + column.
- `_compute_holders` / `_search_holder_count` / `holders()`: holder = user in the transitive
  holders of EVERY group in group_ids (intersection). Empty-bundle role ⇒ 0 holders, never crash.
- Forbidden-group constraint now also walks group_ids (belt and braces on top of the ability
  constraint).

### Delegation + facade on bundles
- `_groups_to_hand`: union over `profile_ids.group_ids`, minus what the delegate already has
  (transitively), and the delegator must hold ALL of every profile's groups (transitively) —
  keep the current error style/wording.
- `applied_group_ids` semantics unchanged (exactly-what-was-added, measured at activation) —
  bundles fit naturally; revoke removes only applied_group_ids (verify this is current
  behaviour and preserve it).
- Facade grant/remove: add/remove `profile.group_ids` (grant adds only missing groups; remove
  removes the role's groups — keep current semantics for shared groups between roles: if two
  roles share a group and the user holds both, removing one role must NOT strip the shared
  group. If the current single-group code has the same hazard, mirror its behaviour and report
  it; if it doesn't handle it, implement remove as "remove groups not required by their other
  held roles" and note it in the report).
- `_headline`, `_kpis`, `_profiles`, `user_options`: same output shapes; only internal group
  math changes.

### Seeds (hooks.py rework)
- New `ABILITIES` list of tuples `(technical_key, area, sequence, name, description,
  group_xmlids_tuple)`. `ensure_catalogue()` seeds abilities first (skip-with-log per missing
  group xmlid, like today), then roles referencing ability technical_keys.
- The 23 existing roles each get one same-named ability wrapping their current group
  (technical_key = slug of the role name). Role tuples change from group_xmlid to ability key.
- 12 NEW dormant abilities (no role references them yet — the P2 composer will):

| technical_key | area | groups (xmlids) | name (plain English) |
|---|---|---|---|
| payroll-ops-work | payroll | om_hr_payroll.group_hr_payroll_user | Work the payroll desk |
| payroll-ops-manage | payroll | om_hr_payroll.group_hr_payroll_manager | Manage the payroll desk |
| pay-reporting-manage | payroll | pb_hr_payroll_base.group_payroll_analytics_manager | Manage pay reporting |
| integrations-run | payroll | pb_hr_payroll_base.group_payroll_integration_user | Run connected-system syncs |
| formula-view | payroll | pb_hr_payroll_formula.group_formula_user | Open pay formulas and read them |
| formula-build | payroll | pb_hr_payroll_formula.group_formula_manager | Build and change pay formulas |
| formula-admin | payroll | pb_hr_payroll_formula.group_formula_admin | Administer the formula engine |
| time-attendance-work | people | hr_attendance.group_hr_attendance_officer | Work time and attendance |
| time-attendance-manage | people | hr_attendance.group_hr_attendance_manager | Manage time and attendance |
| workforce-plan | money | pb_hr_payroll_demand.group_pb_workforce_user | See workforce plans |
| workforce-plan-manage | money | pb_hr_payroll_demand.group_pb_workforce_manager, pb_hr_payroll_demand.group_pb_workforce_admin | Plan and approve the workforce |
| audit-read | system | biz_audit_trail.group_audit_reader | Read the audit trail |

  (Write each description yourself in the catalogue's voice — one sentence, what it lets
  someone do AND what it cannot do. No "Odoo", no module names.)

### Migration (pb_vendor_access/migrations/<new version>/)
- Bump the manifest version (next minor).
- post-migrate: for every existing `pb.role.profile` with a `group_id`, ensure/create the
  matching ability (by technical_key; reuse ensure_catalogue idempotency) and link it, so
  `group_ids == [old group_id]` for all 23. Idempotent — safe to run twice. No user/group
  membership changes AT ALL in this phase.

### Rail B — catalogue audit test (tests/test_access_p1.py or similar)
- Test 1: walk EVERY seeded ability's groups and their full transitive implied closure —
  assert no forbidden group reachable. This is the permanent tripwire for future seeds.
- Test 2: constructing an ability wrapping base.group_system (and one wrapping a group that
  *implies* it, e.g. create a throwaway test group implying it) raises ValidationError.

## Numbered test cases (run + report each)

1. Fresh-ish upgrade on each DB: all 23 role profiles have ability_ids set and
   group_ids == [former group_id]; board RPC `get_board()` returns the same roles/areas/KPIs
   as before migration (capture before/after on one DB and diff).
2. Grant a 2-group bundle role (create a throwaway ability pair in test, not in seed) to a
   test user → user transitively holds both groups; holder_count counts them; a user holding
   only one of the two groups is NOT a holder.
3. Delegate a bundle role: applied_group_ids records exactly the groups newly added;
   revoke removes exactly those and nothing else.
4. Shared-group removal semantics: user holds role A and role B sharing group G; remove A →
   user still in G (or: mirror of current behaviour, explicitly reported).
5. Forbidden closure: Rail B tests pass; the deliberate-bad-ability test raises.
6. Lend-only-what-you-hold: delegator missing one group of a bundle cannot activate the
   hand-over; error message unchanged in style.
7. Full existing suites green: pb_vendor_access/tests/, pb_settings/tests/test_settings.py.
8. Board smoke in the browser (Chrome MCP): open Settings → Access & delegation on the live
   payobook DB, confirm 23 roles render, expand one, KPIs sane. Pixel-identical intent.

## Deploy + verify

- Follow the repo CLAUDE.md deploy contract EXACTLY (single addons dir, clean staging dir,
  per-module scoped rsync --delete, never --delete at the addons root). Ritual details and
  server access: read `/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/memory/payobook-deploy.md`
  and `/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/memory/deploy-rsync-delete-incident.md`
  (also has the server-side test-run flags).
- Upgrade ALL 4 DBs: payobook, abm, acme, payobook_template. Verify per DB:
  ir_module_module.latest_version matches the new manifest (normalise the 19.0 prefix), and
  the 23 profiles' group_ids migration ran (SQL count check).
- No JS/SCSS changes expected ⇒ no asset purge needed; if you did touch assets, purge per
  contract and say why.
- Commit per the standing rule: one feature-scoped commit, explicit file staging, reviewer-
  focused message, do NOT push.

## Report back

1. Per numbered test: pass/fail + one-line evidence (counts, diffs).
2. The ensure_catalogue-on-upgrade finding (how it re-runs, what you added).
3. Which transitive-implied field exists on res.groups in this build and what you used.
4. Shared-group removal: what the pre-existing behaviour was, what P1 does.
5. Any seed ability skipped for a missing module, per DB.
6. Deploy verification table (module hash match + latest_version per DB).
7. Anything you had to decide that this handover didn't cover.
