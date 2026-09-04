# ACCESS P3 — People lens (the passport) + the "See it as…" simulator

STATUS: FINAL — P2 deltas appended at the bottom; build on pb_vendor_access 19.0.1.2.0
(commit b83ecf42).

Read FIRST: `docs/handovers/ACCESS_PROGRAM.md` (program + LEDGER — A-items binding),
`ACCESS_P1_ROLE_BUNDLES.md`, `ACCESS_P2_HOME_ROLES_COMPOSER.md`. Reference prototype
(Option A, owner-approved): https://claude.ai/code/artifact/fdd1a0ca-d731-4481-ac8f-4492bff0953c
— People lens + the header "See it as…" control.

Design bar (verbatim, binding): **extreme WOW, intuitive, out-of-this-world, best in class** —
hero moment, zero dead-ends, plain language, purposeful motion, bulk ergonomics; Lucide not
emoji; Chrome-MCP validate.
White-label rule (binding): "Odoo" never in a user-visible string; plain English only.

## Scope

1. **People lens** in the Access home shell (second tab goes live):
   - Left pane: searchable list of internal users (name, job title if available, role count,
     a "1 lent" tag when they have a running hand-over). Ordered: current user first, then
     alphabetical. Server-side search (name), debounced.
   - Right pane, the **passport** for the selected person:
     - Header: avatar (initials, deterministic hue), name, subtitle "sees X of Y menu
       entries · N roles", buttons: "Their history" (opens the existing Access history list
       action filtered to this person) and "Give a role" (existing grant dialog, person
       pre-selected).
     - **The menu, as <first-name> sees it** — the reusable mini-rail component from P2, fed
       by a per-person visibility RPC (see below), with the see/locked/hidden legend.
     - **Roles they carry** — one row per role: area-tinted icon, name, the sentence, source
       tag (held / lent until <date> by <name>), and Take back (existing remove/revoke flows;
       surface refusal messages verbatim — ledger A4).
     - Empty state (no roles): honest and actionable — "No roles yet. They see only the
       entries every account gets." + Give-a-role button. Zero dead-ends.
2. **"See it as…" simulator** in the home header (visible on every lens):
   - A person picker defaulting to "you". Selecting someone repaints the lenses to that
     person's reality: Roles lens cards gain a "<name> holds this" tag where true; the People
     lens jumps to that person's passport. (Screens lens joins in P4 — build the simulator
     state so P4 can subscribe without rework.)
   - Gate: MANAGE_GROUPS see the full picker; everyone else sees no picker (their own reality
     only). The simulator is a VIEW — it must never change what the viewer can actually do.

## Binding NON-goals

- No Screens lens (P4). No editing of roles/abilities. No new grant/delegate/revoke logic —
  reuse the existing dialogs and facade methods; P3 only adds read RPCs + entry points.
- No portal/external users in the list (internal share=False users only).
- No timeline/fix-access flow from prototype Option C (not part of Option A's P3).
- No changes to pb_sidebar models or data. Cybrosys untouched.

## Verified plumbing (do not re-derive)

- Visibility derivation server-side, mirroring pb_sidebar's own rules
  (pb_sidebar/models/pb_sidebar.py get_sidebar_data :63): admin sees all (base.group_system
  short-circuit), empty groups_id = everyone, else intersect the person's `all_group_ids`;
  no access + restricted ⇒ "locked"; no access + not restricted ⇒ "hidden". Implement the
  per-person RPC by REUSING that model's logic (call it as the target user via with_user or
  factor a shared helper INSIDE pb_sidebar — prefer the small shared helper; do not fork the
  rules into pb_vendor_access, they must never drift). pb_vendor_access may gain a dependency
  on pb_sidebar ONLY if it doesn't already reach it via the dependency chain — check the
  manifest chain first and report what you found.
- Delegations for source tags: pb.access.delegation state=='active', delegate_user_id ==
  person; date_end + delegator name for the "lent until" tag (fields: handover model in
  ACCESS_P1 spec's plumbing block).
- Existing facade: `user_options` (pb_access_facade.py :420) already lists grantable people —
  reuse/extend for the person list rather than a new duplicate query; keep its shape frozen if
  other callers exist.
- Holder maths, closures: ledger A3 (implied_closure / all_group_ids). Take-back semantics:
  ledger A4/A5.

## New facade RPCs (shapes for the cockpit; gate BOARD_GROUPS unless noted)

- `people(search='')` → [{id, name, title, role_count, lent_count}] — MANAGE_GROUPS get all
  internal users; non-managers get only themselves (the lens then renders single-person).
- `passport(user_id)` → {header:{name, title, sees_x, of_y, role_count}, rail:[per-item
  state on/locked/hidden + icon + label + section], roles:[{profile_id, name, description,
  area, source:'held'|'lent', lent_by, lent_until, can_take_back}]} — non-managers may only
  request their own id (server-enforced, not just UI).
- `as_user(user_id)` → the minimal overlay P2's Roles lens needs for "holds this" tags
  (profile_ids held transitively) — same self-only rule for non-managers.

## Numbered test cases

1. Manager opens People lens: list renders, search narrows server-side, selecting a person
   fills the passport; counts (sees X of Y, role count) match a SQL cross-check for 2 users.
2. Passport rail states match pb_sidebar's real behaviour: for one test user, diff the
   passport rail against get_sidebar_data() called AS that user — identical on/locked/hidden
   for every item (this is the no-drift proof; automate it as a python test).
3. Lent role shows the lent-until tag with delegator name; after revoke it disappears and the
   rail updates (the group is gone).
4. Take back from the passport: shared-group refusal message surfaces verbatim in a toast/
   dialog (ledger A4 scenario), and a successful take-back updates rail + roles + KPIs
   without reload.
5. Non-manager (plain base.group_user): People lens shows only themselves; passport(other_id)
   and as_user(other_id) raise AccessError server-side; no picker in the header.
6. Simulator: picking a person tags Roles-lens cards correctly ("<name> holds this") and
   switching to People selects them; switching back to "you" restores; simulator state does
   NOT leak into any write RPC (grant/delegate ignore it — verify by granting while
   simulating someone else).
7. Existing suites green (pb_vendor_access, pb_settings, pb_sidebar tests) + new RPC tests.
8. Chrome MCP live visual pass at ~1440 and ~1100: lens, passport, simulator; screenshots;
   asset purge + restart done (JS changed); zero console errors.
9. i18n + copy audit: no "Odoo", no technical vocabulary, Vietnamese-diacritic names render
   (the live DB has them).

## Deploy + verify + report

Same contract (CLAUDE.md + memory files; 4 DBs, 3 no-op expected — run and report; ledger A8
clone hygiene if you rehearse). Feature-scoped commit, no push. Report per numbered test with
evidence, the pb_sidebar helper decision (shared helper vs with_user + manifest chain finding),
and any decisions beyond the spec.

## P2 deltas (binding facts from the P2 build — see program ledger B1-B9)

- The shell's `LENS_REGISTRY` exists; People is one new entry. The mini-rail is already a
  reusable OWL sub-component in pb_vendor_access — find it and feed it, don't rebuild it.
- Holder/people rows: use the `avatar` field convention (B2). Lent roles get **"End the
  hand-over"** (revoke flow), NEVER "Take back" (B3) — the passport's roles column follows
  the same rule.
- ⚠ The live rail is currently UNGATED (B6): every internal user sees all 9 entries, so on
  `payobook` every passport will read "sees 9 of 9" and rails look identical until P4. This is
  CORRECT behaviour — do not fake variety. Your no-drift test (numbered test 2) still stands;
  for visual variety in screenshots you may add a TEMPORARY gated entry like P2 did (create,
  screenshot, delete, report it).
- Mutual-cover removal deadlock exists (B7) — surface the refusal verbatim; do NOT fix
  remove() (stays a non-goal; P4 handles it).
- Modal/UI gotchas that also apply to your panes: Escape on capture, chips over selects,
  duplicate-name refusals in plain English (B4).
- Deploy: after asset purge, ALSO bump `web.assets.version` per DB (B5 — now part of the
  ritual). 3 of 4 DBs still no-op (A9) — run and report anyway.
