# ACCESS P2 — The Access home: shell, Roles lens, Role Composer

STATUS: FINAL — P1 deltas appended at the bottom; build on pb_vendor_access 19.0.1.1.0
(commit a347407a).

Read FIRST: `docs/handovers/ACCESS_PROGRAM.md`, then `docs/handovers/ACCESS_P1_ROLE_BUNDLES.md`
(the model layer this builds on). Reference prototype (THE spec for look & interactions,
Option A): https://claude.ai/code/artifact/fdd1a0ca-d731-4481-ac8f-4492bff0953c — Roles lens
+ New role composer. People/Screens lenses are P3/P4: the shell must be lens-ready but ships
with only the Roles lens visible.

Design bar (verbatim, binding): **extreme WOW, intuitive, out-of-this-world, best in class** —
hero moment, zero dead-ends, plain language, purposeful motion, bulk ergonomics; Lucide not
emoji; Chrome-MCP validate.
White-label rule (binding): "Odoo" never in a user-visible string. Plain-English copy only.

## Scope

1. **Home shell**: the existing `pb_access_board` client action becomes the Access home —
   page header ("Access", plain-English headline), KPI strip (existing 4 KPIs + "entries on
   the left menu"), a lens tab bar (segmented control) with an internal lens registry so P3/P4
   drop in without rework. Only "Roles" renders in P2.
2. **Roles lens**: today's cards, upgraded — area chips keep working; each card expands
   (accordion, one open at a time) into three columns:
   - *Opens on the left menu* — chips derived server-side (see Derivation below) + the
     "Plus Home and Learn, which everybody sees" footnote when applicable.
   - *Lets them* — the role's abilities (name + description), check-marked list.
   - *Held by* — existing holders line, expanded to rows (avatar, name, source: held /
     lent-until) + the existing Give/Take-back actions relocated into the column.
3. **Role Composer**: "New role" (gated: MANAGE_GROUPS) opens a modal — name field, one-
   sentence description field, ability checklist grouped by area (each row: name, "opens X"
   hint), and a LIVE mini-rail preview (dark rail miniature; on/locked/hidden states; newly-lit
   entries highlighted) that updates per tick. Footer: "Start from an existing role instead"
   (pre-fills from a picked role), Cancel, Create. Creating writes a pb.role.profile with the
   ticked abilities and lands the new card on the board with a success toast.
4. Guard-rail copy in the composer (the shield note from the prototype) — always visible.

## Binding NON-goals

- No "See it as…" simulator (P3). No People or Screens lens (P3/P4). No sidebar model changes.
- No role editing UI beyond create + duplicate-prefill (editing an existing role's abilities
  ships with P4's screens work; note as known-next). No role deletion.
- No diff-vs-role comparison view (prototype teaser — deferred, owner debt list).
- No changes to grant/delegate dialogs beyond relocation (their logic is P1's, untouched).
- Cybrosys untouched. pb_sidebar untouched.

## Derivation rule (the important design decision)

"Which menu entries does this role open?" is NEVER stored on the role. It is DERIVED:
match the role's `group_ids` against `pb.sidebar.item.groups_id` (an item with empty
groups_id = everyone = not listed as "opened by this role"; item.restricted noted as locked
teaser). Same rule powers the composer preview (union of ticked abilities' groups). One
source of truth — when P4 re-gates sidebar items, this lens updates for free. Implement as
facade helpers, computed server-side, never in JS.

## New facade RPCs (extend pb.access; keep existing methods' shapes frozen)

- `role_detail(profile_id)` → {opens: [{label, icon, locked}], abilities: [{name, description}],
  holders: [{id, name, avatar_hint, source, until}]} — gate BOARD_GROUPS.
- `composer_options()` → {areas, abilities by area (id, name, description, opens_hint),
  rail_skeleton (sections/items with icon + everyone/restricted flags)} — gate MANAGE_GROUPS.
- `preview_rail(ability_ids)` → per-item state on/locked/off + newly_lit — gate MANAGE_GROUPS.
- `create_role(name, description, area, ability_ids)` → profile id; validates non-empty
  abilities, forbidden-closure (reuse P1 constraints), duplicate-name warning — gate
  MANAGE_GROUPS. Area: default from the dominant ability area, overridable in the modal.

## UI conventions (follow, don't reinvent)

- Same component: extend `PbAccessBoard` (static/src/js/access_board.js, xml/access_board.xml,
  scss/vendor_access.scss). Keep `.pbva-*` prefix; pbim tokens ONLY (ink #1B1733, muted
  #64748B, line #E6E8F0, surface #FFF, bg #F8F9FC, primary #6355C7, radii 12/8); state colours
  via the `$pbva-states` map pattern; flat fills, no gradients/emoji; Lucide via the shared
  `ic()` registry from pb_import_kit; motion inside prefers-reduced-motion guards.
- Mini-rail preview: build it as a reusable OWL sub-component (P3's passport reuses it).
- Keyboard: cards expandable via Enter/Space; modal Esc closes; focus-visible states.
- All numbers tabular-nums; toasts via the standard notification service.

## Numbered test cases

1. Board loads for a plain base.group_user: Roles lens renders, chips filter, card expands,
   3 columns populated; "New role" button ABSENT (not just disabled) without MANAGE_GROUPS.
2. role_detail derivation: a role whose group gates ≥1 sidebar item lists exactly those items;
   a role whose groups gate nothing shows an honest empty state (no dead-end: explain why).
3. Composer: ticking/unticking abilities updates the preview (on/locked/off + highlight);
   0 abilities disables Create with inline explanation.
4. create_role: new role appears on the board without reload; holds nobody; grant flow works
   on it end-to-end; its card expands correctly.
5. Duplicate-prefill fills name ("Copy of …"), description, abilities from the source role.
6. Forbidden rail: attempting create_role with a hand-crafted RPC containing an ability that
   reaches a forbidden group is rejected server-side (constraint fires).
7. Existing suites green (pb_vendor_access, pb_settings) + new RPC tests.
8. Chrome MCP on live payobook DB: full visual pass of shell/lens/composer at ≥2 widths
   (~1440 and ~1100); screenshot evidence; asset purge done (JS/SCSS changed ⇒ mandatory,
   per repo CLAUDE.md step 6).
9. i18n: new strings translatable; spot-check no "Odoo" and no technical vocabulary in any
   new user-visible string.

## Deploy + verify + report

Same contract as P1 (CLAUDE.md + the two memory files). Upgrade all 4 DBs; asset purge per DB
(JS/SCSS change); verify latest_version per DB. Feature-scoped commit, no push. Report per
numbered test with evidence + any spec gaps you had to decide.

## P1 deltas (binding facts from the P1 build — see program ledger A1-A9)

- Model layer as specced and live on `payobook` (23 roles bundled, 35 abilities: 23 role-backing
  + 12 dormant). `group_ids` is the stored-computed union; use it for the derivation rule.
- Transitive maths: use `vendor_common.implied_closure()` / `all_implied_ids` (reflexive) —
  do NOT hand-roll closure walks (ledger A3).
- **Any ability/role/seed data you add must ship its own migration step** — post_init does not
  fire on upgrade (ledger A2). P2 adds no seeds by design; if a fix forces one, migration it.
- `create_role` must ALSO run `ensure_bundles()` semantics? No — created roles get ability_ids
  directly, so no sweep needed; but never attach an existing ability just because it contains
  a wanted group (ledger A6 — widening hazard). The composer only offers whole abilities, which
  makes this structural; keep it that way.
- `remove()` is the safe shared-group version with a plain-English refusal (ledger A4) — the
  Held-by column's Take-back must surface that refusal message verbatim, not swallow it.
- A plain fallback role form/list now shows abilities read-only (ledger A7) — "Edit the list of
  roles" keeps opening it; the composer is for CREATION only in P2, don't wire it into edit.
- Deploy note: pb_vendor_access exists only on `payobook` (ledger A9) — the other 3 DBs will
  no-op on upgrade; that is expected, still run the ritual against all 4 and say so.
- If you rehearse on a DB clone: clone briefly and DROP it promptly — server crons pick up
  every database on the cluster (ledger A8).
