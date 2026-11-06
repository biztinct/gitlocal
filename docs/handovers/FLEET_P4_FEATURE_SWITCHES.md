# FLEET P4 — Feature switches (deploy is not release)

Program doc: `docs/handovers/FLEET_PROGRAM.md` (READ FIRST, incl. ledger). Stands on P2A
(`pb_tenancy` on every DB, `pb.tenancy.state()`, `session_info.pb_tenancy`, `push_tenancy`).
Gap 6 from `docs/SAAS_RELEASE_STRATEGY.html`.

## What this phase makes true (plain words)

1. The platform has a **catalogue of switchable features** (Insights, Explorer, Workforce, Lifecycle,
   Compliance, Learn, Bank statement scanning, Young workers, Full & Final, Retro & Proration, AI
   insights…). Each is on or off **per customer**, with a plain reason and a date, changed from
   the Tenants cockpit in one click and pushed to that customer within seconds.
2. A feature that is off **disappears cleanly** for that customer's users: its rail entry, its hub
   tile, its command-palette rows and its Settings card are gone — or, when the owner chooses, shown
   locked with a one-line "Ask Payobook to switch this on" (the upsell teaser the rail already
   knows how to draw). Nothing dead-ends; nothing errors.
3. The hero moment: on the cockpit, a **feature matrix** — customers down, features across, each
   cell a switch — with a live "as this customer's admin sees the rail" preview beside it. Flip a
   switch, the preview's rail entry fades out. Bulk: select a column and turn a feature on for
   everyone, with one confirmation.
4. Code can now ship dark: a new part of the product can be installed everywhere (P1) and opened to
   one customer first (P4). P5 will tie switches to plans; P4 keeps them manual.

## Binding NON-goals

- No plans/entitlements — P5 (P4 leaves a `source` field: `manual` now, `plan` later).
- No server-side data blocking beyond what the door already enforces: a switch hides doors, it
  does not add record rules. A feature's own permissions still apply behind the door. (State this
  on the cockpit so nobody mistakes a switch for a security control.)
- No per-user switches. Per customer only.
- Do not restyle the hubs; only add the gate.

## Verified facts for this phase

- **Rail (server-side, tenant):** `pb_sidebar/models/pb_sidebar.py` — `_state_for(item,
  is_admin, user_groups)` :85 is the ONE visibility rule; `visibility_for` :92 and
  `get_sidebar_data` :121 both call it; `restricted` renders a locked teaser with
  `restriction_reason` (JS `pb_sidebar/static/src/js/pb_sidebar.js:373`). The live rail on the
  master is 8 missions + Settings: Home (`pb_home_hub`), Pay Run (`pb_pay_hub`), People
  (`pb_people_hub`), Lifecycle (`pb_lifecycle_hub`), Workforce (`pb_workforce`, module
  `pb_mission`), Insights (`pb_insights_hub`), Compliance (`pb_compliance_hub`), Learn
  (`learn_journey`, module `pb_learn`), Settings (`pb_settings_hub`). Items carry `action_tag`.
- **Hub tiles (client-side, shared):** `pb_hub/static/src/js/hub_shell.js` — lens descriptors
  carry `groups?: [xmlid]` (:66); `allowed` is computed once at :166–180 via `user.hasGroup` and
  filtered at :191–193; a disallowed default lens falls to the first allowed (:183). Palette
  rows: `pb_hub/static/src/js/hub_palette_service.js` :186–205 (`requires` tag existence,
  `groups`). So ONE change in the kit gates every hub and every palette row.
- **Lens keys today:** Pay Run `run, runs, payslips, results, import, deliver, adjust (retro,
  proration), settle (fullfinal)`; People `employees, contracts, plan`; Home `pulse, approvals`;
  Insights `pulse, explorer, workforce, payroll`; Compliance `filings, bank, young, audit`;
  Lifecycle `journeys`; Workforce (pb_mission) `today, schedule, time, timeoff, overtime, trips,
  approvals, close`.
- **Settings cards:** `pb_settings/static/src/js/settings_hub.js` `CATEGORIES` :126 + the soft
  registry; server `resolve_gates` (`pb_settings/models/pb_settings.py:110`) is the place a
  `feature` on a card/category is refused server-side.
- **Tenant state:** `pb.tenancy.state()` (P2A) is in `session_info` → add `features: {key: bool}`
  and `feature_mode: {key: 'hide'|'lock'}`; `push_tenancy` writes `pb_tenancy.features` (JSON).
- Everything above is installed on abm and the template (P2A verified `pb_tenancy`; hubs and
  `pb_sidebar` were there already).

## Architecture

### Catalogue (apex, `pb_tenants/models/feature.py`)

- `pb.feature`: `key` (Char, unique, snake), `name`, `blurb` (one sentence, plain), `area`
  (Selection: pay/people/insights/compliance/workforce/learn/platform), `default_on` (Boolean),
  `mode` (`hide`/`lock` — how an OFF feature shows), `lock_text` (the teaser line), `sequence`,
  `active`. Seeded (noupdate=0 so edits land on `-u`) with this starting catalogue — verify each
  target exists before seeding and drop any that do not, reporting which:
  | key | name | gates |
  |---|---|---|
  | `insights` | Insights & Explorer | rail `pb_insights_hub`; lenses insights:* |
  | `workforce` | Workforce (schedule, time, overtime, trips) | rail `pb_workforce`; pb_mission missions |
  | `lifecycle` | Lifecycle journeys | rail `pb_lifecycle_hub` |
  | `compliance` | Compliance (filings, audit) | rail `pb_compliance_hub`; lenses filings, audit |
  | `bank_ocr` | Bank statement scanning | lens compliance:bank |
  | `young_workers` | Young workers | lens compliance:young |
  | `learn` | Learn | rail `learn_journey` |
  | `fullfinal` | Full & Final settlement | lens pay:settle |
  | `retro_proration` | Retro & Proration | lens pay:adjust |
  | `people_plan` | Workforce planning | lens people:plan |
  | `ai_insights` | AI insights | whatever `pb_payroll_ai_insights` exposes (verify; skip if none) |
- `pb.tenant.feature` (per tenant × feature): `tenant_id`, `feature_id`, `on` (Boolean),
  `source` (`manual`/`plan`, default manual), `reason` (Char), `changed_by`, `changed_at`. Missing
  row = the feature's `default_on`. ACL `base.group_system`.
- Pure `effective_features(catalogue, overrides) -> {key: {'on', 'mode', 'lock_text'}}` (T1).

### Push (apex)

- `features_set(tenant_id, key, on, reason)` and `features_bulk(feature_key, on, tenant_ids,
  reason)` → write rows, then `push_tenancy(db, {'pb_tenancy.features': json})` (P2A) — one push
  per tenant, refuses decommissioned. `features_for(tenant_id)` read. Also push on provisioning
  (`_step_configure`) so a new tenant starts with the catalogue's defaults, and re-push after
  `sync_bring_in_step` (a newly installed part may be off by default).
- The master pushes to itself too (the owner sees the same switches on the master — all on).

### Tenant side (`pb_tenancy`)

- `pb.tenancy.state()` adds `features` + `feature_mode` + `feature_lock_text` from the param;
  missing param = everything on (a tenant that has never been pushed loses nothing — fail OPEN,
  and say so in a comment; the cockpit shows "never pushed" so the owner knows).
- **Rail:** `pb.sidebar.item` gains `feature_key` (Char); `pb.sidebar.section` too. `_state_for`
  consults `self.env['pb.tenancy'].features()` — OFF + `hide` → hidden (for admins too: this is
  not a permission, the product is not sold to them); OFF + `lock` → locked teaser with the
  feature's `lock_text`. Seed `feature_key` on the eight mission items via a data file in
  `pb_tenancy` (xml `<record id="pb_insights_hub.item_insights" …>` cross-module writes are
  allowed with the full xmlid; noupdate=0). `visibility_for` (the Access home's passport) inherits
  it automatically because it is the same rule — say so in the report and verify in the Access home.
- **Hubs:** in `hub_shell.js` the lens descriptor gains `feature?: "key"`; `allowed` becomes
  `groupsOk && featureOn` using a new `pb_tenancy` JS service `features.isOn(key)` /
  `features.mode(key)` seeded from `session.pb_tenancy`. OFF + `lock` → the tile renders locked
  (kit draws it: lock glyph, muted, click → a small dialog with `lock_text`); OFF + `hide` →
  absent. Add `feature:` to the lens descriptors listed in the catalogue table. Palette
  service: an entry whose action's lens (or tag) maps to an OFF feature is dropped (hide) or
  shown with a lock suffix (lock) — mirror the shell.
- **Settings cards:** descriptor `feature?:` on categories/cards; `resolve_gates` refuses server-
  side when OFF (hide) and the hub draws locked (lock).
- Live update: the P2A poll already refreshes `state`; when `features` changes, the service
  emits an event; the rail and open hub recompute without reload.

### Cockpit (apex)

- Sync screen sibling view **Features** (fleet head button "Features" with a count of customers
  with any custom override): the matrix (customers × features), header cells = feature name +
  blurb tooltip + column bulk switch; body cells = switch (on/off), tone by `source`, cell menu:
  reason, changed-by/when, "Reset to default". Right pane: **preview** — the selected customer's
  rail as its admin sees it (reuse the rail-preview component the Access home has, if importable
  from `pb_vendor_access`; otherwise a faithful 8-item mock fed by `effective_features`) that
  animates entries out/in as switches flip. Top: "Last pushed to <customer> 12 s ago" and a
  "Push again" for a tenant showing "never pushed". Catalogue editing: a "Catalogue" tab (name,
  blurb, default, mode, lock text, sequence) — plain forms, no native list views on-menu.
- Tenant detail → Overview: "Features" row: "9 of 11 on · 2 custom" → opens the matrix filtered to
  that customer.
- Keyboard: arrows move across cells, `space` toggles, `shift+click` selects a range in a column,
  `Esc` closes menus. Bulk confirm names the count.

### Tests

- **T1** `effective_features` defaults/overrides/modes; **T2** `_state_for` with a feature OFF
  hide/lock and ON; admins hidden too; **T3** `visibility_for` reflects it; **T4** `pb.tenancy`
  fail-open when the param is missing; **T5** apex `features_set` writes + pushes (capture
  `push_tenancy`), refuses decommissioned; **T6** `resolve_gates` refuses an OFF card; **T7** a
  JS unit test (QUnit/hoot per Odoo 19) for `allowed` with `feature` in `hub_shell` — if the
  harness is too costly, a documented Chrome-MCP check instead, stated as such; **T8** existing.

### Live validation

- **L1** Deploy `pb_tenants`, `pb_tenancy`, `pb_hub`, `pb_sidebar`, `pb_settings`, and every hub
  whose descriptors you edited; `-u` on master; Bring in step on template and abm (rehearse on
  staging first — rail R4); asset ritual on all three.
- **L2** On abm as the customer admin: switch `insights` OFF (hide) from the cockpit → within 60 s
  the Insights rail entry is gone without reload; the Insights hub URL opened directly shows the
  kit's "This part of the product is not switched on for your company" page (design it — zero
  dead-ends); the palette has no Insights rows; the Access home's passport for a person no longer
  lists Insights. Switch to `lock` → locked teaser with the text; ON → back.
- **L3** Bulk column on/off with 1 tenant + template (template shows as a row too? NO — the
  template gets the catalogue DEFAULTS only; show it as a read-only row "defaults for new
  customers").
- **L4** Master unaffected (all on); provisioning path pushes defaults (verify on `abm-staging`
  restored: it inherits abm's pushed params — fine — and a dry note explains).
- **L5** Chrome-MCP screenshots: matrix, preview animation frames, locked tile, dialog, hidden
  state, palette. To `docs/handovers/fleet_p4_shots/`.

## Design (verbatim bar)

"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero: the matrix with the
live rail preview (LaunchDarkly-grade clarity, Linear-grade feel). Zero dead-ends (the direct-URL
page, never-pushed state, lock text). Plain language: "switched on for", "shown locked", "hidden";
never "flag", "gate", "param". Motion with purpose (entry fade). Keyboard/bulk ergonomics as
listed. No "Odoo".

## Deploy + verify — as before. Manifests: `pb_tenants` → 19.0.1.9.0, `pb_tenancy` → 19.0.1.1.0,
`pb_hub`/`pb_sidebar`/`pb_settings` + touched hubs patch-bumped. All DBs.

## Report back — standard list, plus: the final catalogue as seeded (with any dropped keys and
why), the exact descriptors you added `feature:` to, and the Access-home passport check.
