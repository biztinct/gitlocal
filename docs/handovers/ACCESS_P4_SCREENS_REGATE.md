# ACCESS P4 — Screens lens + re-gating the live rail + the B7 fix

STATUS: FINAL — P3 deltas appended at the bottom; build on pb_vendor_access 19.0.1.3.0
(commits a347407a, b83ecf42, 86cafc69).

Read FIRST: `docs/handovers/ACCESS_PROGRAM.md` (program + LEDGER — A/B items binding, B6/B7
are this phase's reason to exist), then the P1-P3 handovers. Reference prototype (Option A):
https://claude.ai/code/artifact/fdd1a0ca-d731-4481-ac8f-4492bff0953c — Screens lens.

Design bar (verbatim, binding): **extreme WOW, intuitive, out-of-this-world, best in class** —
hero moment, zero dead-ends, plain language, purposeful motion, bulk ergonomics; Lucide not
emoji; Chrome-MCP validate.
White-label rule (binding): "Odoo" never in a user-visible string; plain English only.

## Scope

1. **Role gates on rail entries** (model): pb_vendor_access EXTENDS `pb.sidebar.item` with
   `role_ids` M2m pb.role.profile (new file, e.g. models/pb_sidebar_item_ext.py) and overrides
   the item's access check so an entry is visible when EITHER its `groups_id` matches
   (existing ANY-of rule) OR the user FULLY holds any role in `role_ids` (transitive,
   ledger A3). pb_sidebar itself stays generic — the override lives in pb_vendor_access.
   The P2 derivation rule extends: a role "opens" an entry if role ∈ item.role_ids OR
   role.group_ids ∩ item.groups_id ≠ ∅. The P3 passport/no-drift path must keep matching the
   real sidebar answer (the shared helper from P3 is the single place to touch).
2. **Screens lens** (third tab live): the rail drawn as the rail —
   - Rows grouped by section: icon, name, gate summary chips (role chips; "everyone" tag when
     ungated; teaser tag when restricted), per-simulated-person state (sees/locked/hidden —
     subscribes to P3's simulator), active toggle, drag-handle reorder (persists `sequence`).
   - Click a row → detail panel: who sees it today (people + via-which-role), unlocked-by
     roles (add/remove role gates right there — MANAGE-gated), child entries with their own
     gates, restricted-teaser toggle with its plain-English explanation.
   - Zero dead-ends: an entry gated on a role nobody holds says so and offers "Give this
     role to somebody".
3. **Re-gate the live rail** (data migration — the B6 fix). Apply BOTH lanes per entry
   (role_ids for the new world + groups_id for load-bearing legacy groups, so nobody with any
   relevant permission loses an entry):
   | Entry | role_ids (by role name) | groups_id kept/added (legacy lane) |
   |---|---|---|
   | Home, Learn | — (everyone) | — |
   | Pay Run | all payroll-area roles except "Pay reporting — can look" | om_hr_payroll.group_hr_payroll_user |
   | People | all people-area roles + all lifecycle-area roles | hr.group_hr_user |
   | Lifecycle | all lifecycle-area roles | hr.group_hr_user |
   | Workforce | all money-area roles | hr_attendance.group_hr_attendance_officer, hr_attendance.group_hr_attendance_manager |
   | Insights | "Pay reporting — can look" + payroll manager/administrator roles | pb_hr_payroll_base.group_payroll_analytics_user |
   | Compliance | payroll manager/administrator roles | pb_hr_govt.group_pb_hr_govt_user, om_hr_payroll.group_hr_payroll_manager |
   | Settings | "Access team" | (keep as-is) + set `restricted=True` so others see the teaser |
   Resolve live entry xmlids yourself (the 9 active entries; hub modules own them) and report
   the mapping. Migration is idempotent and additive (never strips an existing groups_id link
   on an ACTIVE entry). Remember ledger A2: seed/data changes ship as a migration.
   **MANDATORY: produce a per-user before/after visibility diff table on live `payobook`
   (every internal user × every entry) and include it in your report** — the owner reviews
   what changed for whom after the fact. base.group_system short-circuit means the owner's
   own view never changes.
4. **B7 fix**:
   - Composer refuses creating a role whose effective group set exactly equals an existing
     active role's (plain-English refusal naming that role, offering duplicate-prefill
     instead).
   - The mutual-cover removal refusal message now also offers the way out ("…or archive one
     of the two roles").
   - Role cards (MANAGE only) get an overflow action "Archive role": allowed when it has no
     holders and no running hand-over, otherwise refused with a plain sentence saying who
     still holds it. Archived roles vanish from the board and from item gates' effect
     (verify: an entry gated only on an archived role behaves as "role nobody can hold" —
     decide and report whether that should fall back to hidden-with-explanation in the lens).
5. **Settings → Navigation re-point**: the settings hub "Navigation" category's cards now open
   the Access home on the Screens lens (client-action context). The old raw list views stay
   registered (super-admin fallback, reachable from the lens via a quiet "advanced list"
   link) — nothing deleted.

## Binding NON-goals

- No tenant-admin rails, no debug work, no provisioning changes (P5). No genericization/
  extraction, no Cybrosys removal (P6). No section CRUD (reorder of items only; section
  editing stays in the fallback list — noted debt). No changes to grant/delegate logic beyond
  the two B7 message/refusal items. Existing RPC shapes frozen.

## Plumbing (do not re-derive — and reuse, don't fork)

- pb.sidebar model + visibility rules: ACCESS_P1/P3 handovers + ledger. The P3 shared helper
  is the ONLY place visibility logic may be touched; passport, Screens lens, and the real
  rail must stay provably identical (extend the P3 no-drift test to cover role-gated items).
- Facade write pattern: follow the existing facade's sudo+gate pattern (MANAGE_GROUPS) for
  set-gates/toggle/reorder/archive; verify how grant/remove do it and mirror.
- Rail reload: after gate edits the live rail (left of the screen) must refresh without a
  full page reload if the current user is affected — check how pb_sidebar's JS loads
  (`_load()` via orm.call, ACCESS_PROGRAM facts) and trigger a reload of it; report the
  mechanism you used.
- New RPCs (gate BOARD for reads, MANAGE for writes): `screens_board()`, `screen_detail(id)`,
  `set_screen_roles(id, role_ids)`, `set_screen_flags(id, active, restricted)`,
  `reorder_screens(section_id, item_ids)`, `archive_role(profile_id)`.

## Numbered test cases

1. Role-gate visibility: user fully holding a gated role sees the entry; a partial holder
   (one group of a 2-group bundle) does NOT; groups_id legacy lane still works; both lanes
   OR together.
2. No-drift proof extended: passport rail == get_sidebar_data() as-user == Screens lens
   states, for a role-gated item and a legacy-gated item (automated test).
3. Migration on a rehearsal clone (ledger A8 hygiene): gates applied per the table; the
   before/after per-user diff table generated; NO user with a relevant legacy group loses an
   entry; role-holders' views unchanged or widened only where the table says so.
4. Reorder persists across reload and changes the real rail order; active toggle hides an
   entry live; restricted toggle shows the teaser (locked) for a non-holder.
5. Detail panel: who-sees list matches reality for 3 users (SQL cross-check); gate add/remove
   from the panel updates the row chips, the real rail, and the Roles lens "opens" column
   without reload.
6. B7: identical-bundle create refused with the existing role named; mutual-cover removal
   message offers archiving; archive works at 0 holders and refuses (naming holders) above 0.
7. Simulator: switching person repaints Screens lens states; view-only (no write RPC carries
   the simulated user — verify like P3 test 6).
8. Existing suites green (pb_vendor_access, pb_settings, pb_sidebar) + new tests.
9. Chrome MCP live pass at ~1440/~1100: lens, detail panel, gate editing, teaser, reorder;
   screenshots; asset purge + web.assets.version bump per DB (B5) + restart; zero console
   errors.
10. i18n + copy audit: no "Odoo", no raw group names anywhere in the lens (roles and plain
    words only), translatable strings.

## Deploy + verify + report

Same contract (CLAUDE.md authoritative; 4 DBs, 3 no-op expected; B5 ritual). Feature-scoped
commit, module files only, no push. Report: per-test evidence, the live entry-xmlid mapping,
the FULL per-user before/after diff table, the archived-role-gate decision, the rail-refresh
mechanism, decisions beyond the spec.

## P3 deltas (binding facts from the P3 build — see program ledger C1-C7)

- **Visibility has ONE home now** (C1): pb_sidebar's `_access_of`/`_state_for`/
  `visibility_for(user)`. Your role-gate lane plugs in by overriding `_access_of` (and, if
  needed, `_state_for`) in pb_vendor_access's pb.sidebar.item extension — passport, Screens
  lens, simulator and the real rail then all update through the same rule automatically.
  Extend the existing no-drift test rather than writing a parallel one.
- ⚠ **C2 changes your migration design**: pb_sidebar data is noupdate="0", so an `-u` of any
  module shipping rail rows re-asserts them from XML. Therefore the re-gate must land in TWO
  places: (a) the owning hub modules' shipped `data/pb_sidebar.xml` files (groups_id legacy
  lane; role_ids CANNOT go in those files — the hub modules must not depend on
  pb_vendor_access — so shipped XML carries only the groups lane), and (b) a pb_vendor_access
  migration that sets role_ids on the live rows (and re-runs idempotently). Check which live
  entries' shipped XML already specifies groups_id (those get edited in-file); report the
  file list. Consequence to state in your report: role_ids on template-less DBs is a no-op
  (module not installed there — ledger A9).
- Simulator state, callName(), section-lock marker on the mini-rail exist — reuse (C3).
- SCSS: don't put reusable row styles under `.pbva-modal-scrim` (C4/W66); media queries
  measure the window, pane is ~256px narrower — generous breakpoints.
- pb_sidebar tests: 2 PRE-EXISTING failures on payobook_template (C6) — not yours to fix
  unless trivial; do not let them mask new failures (compare counts).
- Deploy: pb_sidebar WILL need an `-u` this phase if you touch its Python/data — remember C2's
  re-assert effect on payobook's live rows (your in-file gate edits make that safe: shipped
  XML == desired state BEFORE you run the -u).
