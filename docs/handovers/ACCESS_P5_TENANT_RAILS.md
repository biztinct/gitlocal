# ACCESS P5 — Tenant-administrator rails (debug block, settings split, the demotion switch)

STATUS: FINAL — P4 deltas appended at the bottom; build on pb_vendor_access 19.0.1.4.0 /
pb_sidebar 19.0.3.1.0 / pb_settings 19.0.1.5.0 (commits a347407a…2f7a7a4a).

Read FIRST: `docs/handovers/ACCESS_PROGRAM.md` — especially the "Tenant provisioning ⚠ KEY
FINDING" section (every tenant admin today IS base.group_system via the template), the
"Debug-mode + chrome seams" section, owner ruling 4 (Rails A/B/C), and the LEDGER (A/B/C
items + this phase's P4 deltas). Then the P1-P4 handovers.

Design bar (verbatim, binding): **extreme WOW, intuitive, out-of-this-world, best in class**.
White-label rule (binding): "Odoo" never in a user-visible string; plain English only.

## The autonomy principle of this phase (Fable ruling)

Nothing owner-visible changes for EXISTING tenants in this phase. The rails ship complete and
armed; the flip for existing tenants sits behind an explicit switch only the owner throws:
- **New tenants** (provisioned after P5): rails ON by default — this is the owner-approved
  design ("tenant administrator is restricted to this application").
- **Existing tenant DBs** (abm, acme): untouched until the owner flips the switch — listed as
  the owner decision at phase close, NOT a blocker for the build.
- The platform DB (`payobook`) and the owner's own accounts are NEVER demoted by any path.

## Scope

1. **The "Tenant administrator" bundle** (data, in pb_vendor_access): a seeded role —
   plain-English name/sentence — bundling the abilities a tenant's own admin needs: manage
   access (Access team), full payroll administration, people/lifecycle administration,
   budgets, reporting, integrations. Exact ability list from the seeded 35 — pick the
   administrator tier of each area, write it down in the report. Shipped with a migration
   (ledger A2). It must pass Rail B by construction (no forbidden groups anywhere in its
   closure).
2. **Rail A — hard server-side debug block**: an `ir.http` extension so that for any user
   who is not base.group_system, `?debug=` is ignored: `request.session.debug` is cleared in
   `_handle_debug`/`_pre_dispatch` and `session_info['bundle_params']['debug']` is suppressed.
   Facts + seams: program doc (web/models/ir_http.py :46/:58/:133/:193; biz_theme's existing
   session_info override at biz_theme/models/ir_http.py:7 is the natural host — but READ
   biz_deroute/models/ir_http_session_guard.py FIRST for the registry-ordering hazard it
   documents, and decide inherit-vs-monkey-patch accordingly; report the decision).
   Where to put it: a small module or biz_theme — prefer **biz_theme** (it already owns the
   session_info seam and is installed everywhere), NOT pb_vendor_access (tenant DBs without
   the access module still need the block). Also remove/neutralize the user-menu "developer
   mode" items for non-system users (program doc: nothing removes them today).
3. **Rail C — settings hub split, server-authoritative**: extend `pb.settings` with a
   `resolve_gates` RPC (program doc facts: gating today is client-only, ANY-of, fails OPEN)
   so category visibility for the four ADMIN categories is answered server-side; tenant
   admins (the bundle, not group_system) see the app-level categories their roles allow
   (Access, Navigation, payroll/org config per the bundle) while platform-only categories
   (Companies & Tenants; anything technical) require base.group_system. Keep the registry
   shape; fail CLOSED for the platform-only set. The Sidebar "Settings" entry itself is
   already teaser-gated from P4.
4. **Provisioning rails** (pb_tenants, platform DB only): `_step_admin` gains the demote
   step for NEW tenants — the clone's admin user: (a) gets the Tenant administrator role's
   groups (via the access module present in the template), (b) loses base.group_system /
   base.group_erp_manager, (c) a second, ARCHIVED break-glass platform account is preserved
   in the clone for the owner (document its handling; never shown to the tenant).
   Behind `ir.config_parameter` `pb_tenants.tenant_admin_rails` (default ON for new
   provisioning after P5; the parameter exists so the owner can revert instantly).
5. **Template readiness**: install pb_vendor_access (+ its dependency chain) on
   `payobook_template` so clones carry the access module and the seeded bundle. FIRST assess
   what the template is missing (it has ~197 modules vs payobook's ~224 and only 3 active
   rail items — program ledger C6), rehearse the install on a CLONE of the template
   (ledger A8 hygiene: drop promptly), fix what breaks, then do the real template. Report the
   before/after module delta. This also clears ledger A9 for the template.
6. **The existing-tenant flip, built but NOT executed**: a management routine (server action
   or facade method, platform DB) that applies the demotion to a named existing tenant DB —
   written, tested on a clone of `acme` or `abm`, and then NOT run against the real ones.
   Its existence + how to run it goes in the report and the closeout for the owner.
7. **Rail B extension**: the audit test now also asserts the Tenant administrator bundle
   reaches no forbidden group, and a new test proves a demoted admin user cannot reach:
   debug mode (Rail A), the apps/technical settings actions (stock group_system ACLs), the
   platform-only settings categories (Rail C), or the Tenants cockpit.

## Binding NON-goals

- Do NOT demote any existing user on payobook, abm, or acme. Do NOT run the flip routine
  against a real tenant. Do NOT touch the owner's accounts anywhere.
- No genericization/extraction, no Cybrosys uninstall (P6 — but nothing new may depend on it).
- No changes to the Access home UI beyond what Rail C requires (this is a rails phase).
- The debug block must not break website/public routes or the owner's own debug use.

## Numbered test cases

1. Rail A: a non-system user with `?debug=1` gets a session with debug off and no debug
   bundle (assert server-side + browser check); base.group_system keeps full debug; public
   pages unaffected.
2. Rail C: platform-only categories invisible to a tenant-admin-bundle user even with the
   client registry tampered (server refuses — fail CLOSED); app categories their roles allow
   appear; base.group_user sees what today's rules give them (no regression on payobook).
3. Bundle: Rail B passes; the seeded Tenant administrator role appears on the board with an
   honest sentence; granting it to a test user yields the intended reach and NOTHING
   platform-level (automated closure assertion).
4. Provisioning rehearsal: clone the template, run provisioning end-to-end against it (or the
   closest safe equivalent — document the method): the new tenant's admin holds the bundle,
   NOT group_system; login works; the Access home works in the clone; the break-glass account
   is archived and platform-holdable only.
5. The flip routine: rehearsed on a clone of one existing tenant DB; before/after group diff
   of its admin captured for the report; real tenants untouched (prove: their admin group
   memberships unchanged after the whole phase).
6. Full suites green on payobook (pb_vendor_access, pb_settings, pb_sidebar, pb_tenants) —
   plus the C6 pre-existing template failures either fixed here (if trivial) or explicitly
   unchanged in count.
7. Chrome MCP: debug blocked live for a non-system user (URL attempt), settings hub as
   tenant-admin-bundle user vs owner; screenshots; asset ritual per B5 where JS changed.
8. Copy audit: every new string plain English, no "Odoo".

## Deploy + verify + report

Same contract (CLAUDE.md; B5 ritual; per-DB verification table). Feature-scoped commits
(this phase may naturally split into 2: rails module work / template+provisioning), no push.
Report: per-test evidence, the bundle's ability list, the inherit-vs-patch decision for
Rail A, the template module delta, the flip routine's name + how the owner runs it, decisions
beyond spec.

## P4 deltas (binding facts from the P4 build — see program ledger D1-D9)

- The live payobook rail is GATED (D1); Settings is restricted=True with an honest reason —
  Rail C builds on top, and the Tenant administrator bundle MUST include the "Access team"
  ability so a tenant admin can open Settings and the Access home (D8: today only the owner's
  account holds it on payobook — leave payobook's grants alone, this is about the bundle).
- pb_settings has the replace-by-key category seam (D6) — use it for any Rail C category
  adjustments rather than editing shipped entries where a push can do it; resolve_gates is
  still yours to add server-side.
- If any step of this phase gates a new entry on payobook: remember the second `-u pb_demo`
  pass (D4) and the `(4, ref)` rule for shipped XML (D2).
- Archived-role gates stay hidden by design (D3) — the flip routine must not archive roles as
  a side effect.
- Rail refresh is bus-driven (D5) — if provisioning or the flip touches gates, no extra work
  needed client-side.
- Template state: ~197 modules, 3 active rail items, 2 pre-existing sidebar test failures
  (C6). Your template install (scope item 5) will change its module set substantially —
  capture the before/after module delta and re-run the sidebar tests there; if the C6 pair
  turns green as a side effect, say so.
- Pre-existing live failure that is NOT yours: pb_learn anchor-registry (D9).
