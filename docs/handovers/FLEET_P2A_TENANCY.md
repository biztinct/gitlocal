# FLEET P2A — `pb_tenancy`: the tenant-side agent, notices, and "What's new"

Program doc: `docs/handovers/FLEET_PROGRAM.md` (READ FIRST). Previous phase: `FLEET_P1_DRIFT.md`
(its report is in the ledger F7+; its fields on `pb.tenant` — `release_id`, `release_state`,
`last_sync_at`, `last_sync_result` — and facade `sync_bring_in_step`, `release_cut`, `pb.release`
with `notes`/`snapshot`/`is_current` are the ground this phase stands on. If P1 named anything
differently, the ledger says so; follow the ledger).

## What this phase makes true (plain words)

1. Every customer's database carries a small part of the product, **`pb_tenancy`**, that knows
   which release it is on and can show its users a message from the platform. It is the seam
   every later phase pushes through (feature switches, plan limits, support access).
2. A customer's users **see a notice before an update** ("Payobook will be updated tonight between
   22:00 and 01:00. You may notice a short pause.") and **during** one ("Payobook is being updated
   right now — a minute or two.") — as a top bar, not a modal, on every page.
3. After an update lands, users get one quiet toast: "Payobook was updated to release 2026.09.03 —
   see what's new", and Settings gains an **About Payobook → What's new** page: a timeline of
   releases with the owner's notes, newest first. That page is the hero moment.
4. The platform owner can **send a notice to one customer or all of them** from the Tenants
   cockpit (title, text, until when), and clear it. This is the manual half of gap 9; P2B adds the
   automatic half (notices tied to rollouts).
5. The apex pushes state to a tenant through ONE method, `push_tenancy(tenant, values)`, which
   writes through the tenant's ORM (rail R5) — never raw SQL.

## Binding NON-goals

- No rings, no rollout job, no health gate, no windows — P2B.
- No feature switches, plans, seat limits, suspend door, support login — later phases; but the
  agent's `state()` payload is a dict and later keys are simply added.
- No bus/websocket push. A notice appears on next page load and within 60 s on open pages via a
  poll (below). Real-time is not worth a bus channel per tenant here.
- `pb_tenancy` seeds NO data, creates NO crons, adds NO rail item. It is a quiet module.

## Verified facts for this phase

- WebClient template: `biz_theme/static/src/xml/biz_sidebar_menu.xml:8` extends `web.WebClient`
  and REPLACES `//ActionContainer` with a wrapper. Do not xpath the ActionContainer. The banner
  mounts via your own `t-inherit="web.WebClient"` extension inserting `<PbTenancyBanner/>`
  **after `//NavBar`** (verify the base template first:
  `sudo cat /odoo/odoo-server/addons/web/static/src/webclient/webclient.xml`) and a
  `patch(WebClient, {components: {...}})` exactly like `biz_sidebar_menu.js:217`.
- `session_info` seam: `addons/web/models/ir_http.py:79` (`ir.http` model, `session_info(self)`
  returns a dict) — extend it in `pb_tenancy/models/ir_http.py` to add `pb_tenancy: {...}`.
- Tenant identity: `pb.tenant.slug` param is set on every provisioned tenant (`service.py:677`);
  the master has none (treat "no slug" as the master).
- Settings hub soft registry: `settings_hub.js:256–271` — `registry.category("pb_settings_category")
  .add(key, descriptor, {sequence})`; descriptor = a `CATEGORIES` entry (`:126`); a single-card
  category opens its one door directly; a card with `tag` opens a client action via `openHub`
  (`:640`) with a back chip. Gates: `groups` list on the category; empty = everybody. "What's new"
  is for EVERY logged-in user (empty groups).
- Cross-DB write from the apex: `pb.tenants._tenant_env(db)` (`service.py:353`) — ORM env as
  SUPERUSER, commits on exit. `ir.config_parameter.set_param` through it invalidates the tenant
  registry's cache (rail R5 / ledger). Live tenant: `abm` only; template `payobook_template`.
- Icons: shared kit registry `pb_import_kit/static/src/js/import_icons.js` (`IC` :6, `ic()`
  :194, 102 glyphs). `pb_import_kit` IS installed on abm and the template. Add new glyphs there
  (rule W2), not a per-module icon file.
- Logins for live checks: abm admin `ash@biztinct.com` (password in the JOURNEY memory:
  `J5validate!2026`) — if it fails, reset via the runbook's hash recipe and REPORT that you did.
- `pb_tenancy` must be installed on: master (`-i pb_tenancy -d payobook`), then the template and
  abm via P1's **Bring in step** (that is the designed path and it dogfoods P1). Rail R8 on the
  template afterwards (P1's unit already does it — verify it did).

## Architecture

### 1. Module `pb_tenancy` (new, installed everywhere; NOT on the never-list)

Manifest: name "Payobook Platform Link" (user-visible in the apps list — no "Odoo"), version
19.0.1.0.0, depends `['web', 'pb_import_kit', 'pb_settings']`, assets in `web.assets_backend`:
`static/src/scss/tenancy.scss`, `static/src/js/tenancy_service.js`, `static/src/js/tenancy_banner.js`,
`static/src/js/whats_new.js`, `static/src/xml/*.xml`, plus a `pb_settings`-registry file that
registers the "About Payobook" category (`static/src/js/tenancy_settings.js`).

**Parameters (the contract — the apex writes, the tenant reads):**
| key | value |
|---|---|
| `pb_tenancy.release` | release name, e.g. `2026.09.03` |
| `pb_tenancy.release_date` | ISO date |
| `pb_tenancy.releases` | JSON list of the last 10 `{name, date, notes}` newest first |
| `pb_tenancy.notice` | JSON `{kind: 'maintenance'|'info', title, text, starts_at, ends_at, id}` or empty |
| `pb_tenancy.pushed_at` | ISO datetime of the last push |

`pb.tenancy` AbstractModel (`models/tenancy.py`):
- `@api.model state()` → `{'release', 'release_date', 'releases', 'notice', 'pushed_at',
  'is_master'}` — read-only, `sudo()` param reads, notice dropped when `ends_at` has passed.
  Every logged-in user may call it (it is chrome).
- `ir.http.session_info()` override adds `'pb_tenancy': self.env['pb.tenancy'].state()` — so the
  banner renders on first paint with no RPC.
- Controller `GET/JSON /pb_tenancy/state` (auth `user`) → same payload, for the 60 s poll.

**JS:**
- `tenancy_service.js`: a `pb_tenancy` service holding reactive state seeded from `session.pb_tenancy`;
  polls `/pb_tenancy/state` every 60 s ONLY while a notice is showing or `document.visibilityState`
  flips to visible after > 60 s hidden (cheap, no polling storm).
- `tenancy_banner.js` + xml: top bar. `maintenance` = amber (`#D97706` promoted semantic), `info` =
  indigo soft. Content: title bold, text, time range rendered in the USER's locale
  ("tonight 22:00–01:00"). Dismiss (x) hides for this browser until the notice `id` changes
  (localStorage `pb_tenancy.dismissed`). Slides in/out (purposeful motion). Respects
  `prefers-reduced-motion`.
- Release toast: on service start, if `release` differs from localStorage `pb_tenancy.seen_release`
  → one notification ("Payobook was updated to release 2026.09.03", button "See what's new" →
  opens the What's new action) → store seen. Never on the master when `is_master`? Show it on the
  master too — the owner is a user of the product.
- `whats_new.js` client action `pb_tenancy_whats_new`: timeline of `releases` (name, date, notes as
  paragraphs; simple markdown-lite: blank line = paragraph, `- ` = bullet), newest first, current
  one badged "You are on this release"; empty state: "No release notes yet. Payobook will list what
  changed here after each update." Back chip via `hubBack` (pb_hub is on tenants — verify; if not,
  a plain back button to Settings).
- `tenancy_settings.js`: registers category `about` — icon `info`, label "About Payobook", blurb
  "Which release you are on and what changed.", groups `[]`, one card `{id:'whats_new',
  tag:'pb_tenancy_whats_new', icon:'sparkles', label:'What's new'}`, sequence 40. Server gates:
  nothing platform-only about it; confirm `resolve_gates` returns true for a tenant admin.

### 2. Apex side (`pb_tenants`)

- `push_tenancy(db, values: dict)` on the facade: opens `_tenant_env(db)`, `set_param` each key,
  writes `pb_tenancy.pushed_at`; refuses the never-list databases; logs a line in the tenant's
  `provision_log` (step `notice`/`release`). Skips (with a clear message) when `pb_tenancy` is not
  installed on that DB ("Install the Platform Link on this customer first — Bring in step does it").
- `release_cut` (P1) additionally builds `releases` (last 10 with notes) and pushes release params
  to the MASTER's own params (so the master shows What's new) — NOT to tenants; tenants get release
  params only when they are actually brought onto it: extend P1's `sync_bring_in_step` step 8: when
  the tenant ends `on` the current release → `push_tenancy(db, release params)`.
- Notices: `notice_send(tenant_id | 'all', kind, title, text, starts_at, ends_at)` and
  `notice_clear(tenant_id | 'all')`. `pb.tenant` gains `notice` (Text JSON mirror of what was
  pushed, for the cockpit) and `notice_until`.
- Cockpit: Fleet head gets "Send a notice" (fleet-wide) → dialog: kind (segmented: Planned update /
  Information), title, text, from/until (date-time pickers, defaults now → +6 h), preview of the
  exact bar the users will see (hero-adjacent: live preview as you type), confirm lists the
  customers it reaches. Tenant detail → Overview gets a "Notice" row: current notice (with "Clear")
  or "Send a notice to this customer". Zero dead-ends: when a tenant lacks `pb_tenancy`, the row
  says so and links to the Sync screen.

### 3. Tests

- **T1** `pb.tenancy.state()` drops an expired notice; returns `is_master` when no slug param.
- **T2** `session_info` carries `pb_tenancy` (HttpCase or a direct call with a fake request —
  choose what Odoo 19 allows; document).
- **T3** `/pb_tenancy/state` requires login (HttpCase: 401/redirect when anonymous, JSON when
  logged in).
- **T4** Pure: `notice_payload(kind, title, text, starts, ends)` validation — title required, ends
  > starts, kind in set; `render_range(starts, ends, tz)` → "tonight 22:00–01:00" / "Thu 22:00 –
  Fri 01:00".
- **T5** Pure: `releases_list(all_releases)` → last 10, newest first, notes trimmed.
- **T6** Apex: `push_tenancy` refuses never-list names and the master DB name.
- **T7** Existing pb_tenants tests still pass.

### 4. Live validation

- **L1** Deploy `pb_tenancy` + `pb_tenants` to the server. `-i pb_tenancy -d payobook`, `-u
  pb_tenants -d payobook`. Asset ritual on payobook.
- **L2** Cut release (P1) with notes "Payobook now tells you before an update and shows what
  changed." Bring the **template** in step (installs pb_tenancy there; verify crons re-disabled
  and the param extended). Then abm (rehearse on `abm-staging` first — rail R4).
- **L3** On abm, logged in as the customer admin: Settings shows "About Payobook → What's new";
  the page shows the release with the note; the toast appeared once and not again after reload.
- **L4** Send a fleet notice (Planned update, tonight) → within 60 s the amber bar is on abm's open
  page WITHOUT reload (poll), correct local time range, dismiss works, reappears for a NEW notice
  id; clear removes it within 60 s.
- **L5** Master: What's new visible; the notice is NOT shown on the master unless sent to it
  (design choice: "all" = all live tenants, not the master; say so on the dialog).
- **L6** Chrome-MCP screenshots of: bar (both kinds), toast, What's new (filled + empty), the send
  dialog with live preview, the tenant Notice row. To `docs/handovers/fleet_p2a_shots/`.
- **L7** Asset ritual on abm and template after JS lands there (purge + version bump per DB).

## Design (verbatim bar)

"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero: the What's new
timeline (Linear changelog quality) and the live-preview notice composer. Zero dead-ends. Plain
language ("release", "update", "notice"; never "parameter", "session", "push"). Motion with purpose
(bar slide, toast). No "Odoo" anywhere users read — including the module's name in the apps list.

## Deploy + verify

Repo `CLAUDE.md` contract. `pb_tenancy` goes to master, template, abm (via P1's screen — never by
hand `-i` on a tenant, that is the point). Manifest bumps: `pb_tenants` → 19.0.1.6.0. Verify tree
hashes + versions on all three DBs; 0 skipped; cron window clean.

## Report back

1. Where the banner mounts (the xpath you used and why) and the poll behaviour measured.
2. L2–L5 evidence with numbers (versions per DB, seconds to appear).
3. Screenshots list.
4. Self-score against the bar.
5. Beyond-spec choices; anything left out and why.
6. Ledger entries (F-numbers) appended.
7. Commits (feature-scoped, not pushed).
