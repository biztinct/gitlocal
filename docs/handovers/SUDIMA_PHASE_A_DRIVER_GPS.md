# SUDIMA Phase A — Driver GPS Check-in PWA + Manager Live Map

**Scope item:** Sudima demo requirement **#5 Driver GPS Check-in** (docs/SUDIMA_PANELS_GAP_ANALYSIS.html — verdict *Not Built*).
**Modules:** NEW `biz_geo_tracking` (generic engine) + NEW `pb_driver_checkin` (Payobook overlay).
**Ledger:** read `docs/FORMULA_ENGINE_CONVENTIONS.md` — **C1, C2, C18 are binding** for this phase.
**Design authority:** this doc. Do not re-derive any fact marked ✓; they were verified against the tree on 2026-07-22.

---

## 1. Scope

Build a production-grade driver check-in system:

1. A **mobile PWA** (installable, HTTPS at https://payobook.com) where a driver logs in with their Odoo account, checks in/out with GPS capture, optionally attaches a selfie, and — while checked in — streams a location ping every ~15 s.
2. A **manager Live Map cockpit** in the Payobook backend: live markers per active driver, driver rail with freshness states, check-in history, availability metrics.
3. A **server-side demo simulator** that replays Hanoi/HCMC routes through the *real* ping pipeline so the map moves during a client demo.

### Binding non-goals
- **NO face matching / biometric verification** — selfie is photo evidence only.
- **NO background tracking claim** — tracking runs only while the PWA is foregrounded and checked in (platform limit). Do not attempt Background Sync / background geolocation hacks.
- **NO bus.bus / websockets** — polling only (see C18.5).
- **NO payroll changes** — check-ins land in `hr.attendance`, which payroll already consumes; nothing else.
- **NO route optimization / geofencing** — out of scope for this phase.
- **NO modification of `hr_attendance_geolocation`** — it stays untouched; we use core `hr.attendance` lat/long fields.

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **Programmatic check-in seam:** `hr_attendance/models/hr_employee.py:166-203` — `_attendance_action_change(geo_information)` creates the `hr.attendance` on check-in / closes it on check-out, writing `in_latitude/in_longitude/in_mode` etc. Core fields on `hr.attendance` (`hr_attendance/models/hr_attendance.py:27+`): `check_in`, `check_out`, `worked_hours`, `in_latitude/in_longitude` Float digits (10,7), `in_mode/out_mode` Selection (`kiosk|systray|manual|technical`) — **extendable via `selection_add`**. Systray precedent for an authenticated JSON check-in endpoint: `/hr_attendance/systray_check_in_out` (`hr_attendance/controllers/main.py:220-228`).
  ⚠ Verify the exact `_attendance_action_change` signature/mode handling before coding the controller — if mode isn't a parameter, write `in_mode='gps'` on the returned attendance record right after the call.
- ✓ **PWA controller template:** `website_event_track/controllers/webmanifest.py:14-58` — serves a JSON manifest via `request.make_response`, and the service worker via `file_open()` + `Service-Worker-Allowed` response header. Clone this pattern; **drop the `website=True` / website dependency**.
- ✓ **Cockpit pattern:** clone `pb_people` — `ir.actions.client` tag + OWL class registered via `registry.category("actions").add(tag, Class)` (`pb_people/static/src/js/people.js:22-157`, action XML `pb_people/views/pb_people_action.xml:3-11`); backend data via an AbstractModel `get_*_data()` returning a plain dict, every metric wrapped `_safe()`, queries scoped to `self.env.companies.ids`. Launch/test URL: `/odoo/action-<tag>`.
- ✓ **Sidebar:** data-driven `pb.sidebar.section`/`pb.sidebar.item` (`pb_sidebar/data/pb_sidebar_data.xml:86-93` shows the item pattern; `workforce` section exists). Items point at cockpits via `action_tag` + `match_action_tags`. **Lucide icons are a fixed inlined `ICONS` const in `pb_sidebar/static/src/js/pb_sidebar.js`** — this phase adds ALL icons for phases A–E in one touch: `map-pin, truck, table, plane, scan, shield` (Lucide 24×24 stroke paths).
- ✓ **Theme tokens:** `--pbim-*` custom props from `pb_import_kit/static/src/scss/import_tokens.scss`; cockpits use the `.pbim` kit root + a per-cockpit tint class. Design system: locked palette, white + rail hero, **no gradients, no emoji, Lucide SVG only**.
- ✓ **HTTPS:** live at **https://payobook.com**, nginx reverse proxy, `proxy_mode=True`, Let's Encrypt (memory `payobook-deploy`). Geolocation + camera + Wake Lock APIs work. `web.base.url` is frozen to the domain.
- ✓ **No map library exists anywhere in the tree** — Leaflet must be vendored.
- ✓ Odoo 19 gotchas: bump manifest `version` on every asset change (C2); prod asset cache needs `-u` or `ir_attachment` bundle purge; `res.users` uses `group_ids`.

---

## 3. Architecture

### 3.1 `biz_geo_tracking` — generic engine (NO Payobook deps; depends on `base`, `web` only)

**Reusable beyond drivers**: delivery tracking, field service, sales-visit logging. Nothing in this module may reference `hr.*`, `pb_*`, or Vietnam.

```
biz_geo_tracking/
├── __manifest__.py            (depends: base, web; assets: leaflet lib + map widget in web.assets_backend)
├── models/
│   ├── biz_geo_ping.py        biz.geo.ping
│   ├── biz_geo_route_sim.py   biz.geo.route.sim (+ cron)
│   └── biz_geo_service.py     biz.geo.tracker (AbstractModel API)
├── controllers/pwa_shell.py   helper mixin to serve manifest + SW for a named app
├── data/cron.xml              GC cron + simulator cron
├── security/                  ir.model.access (base.group_user read own via record rule; see overlay)
└── static/
    ├── lib/leaflet/           vendored Leaflet 1.9.x (leaflet.js + leaflet.css + images/)
    └── src/js/geo_map.js      thin ES-module wrapper: initMap(el, opts), upsertMarker(), drawTrail()
```

**`biz.geo.ping`** (append-only; `_log_access = True`, no mail.thread — volume!):
- `user_id` m2o `res.users` required index ondelete=cascade
- `session_model` Char, `session_id` Integer — polymorphic binding to whatever "session" record owns the ping (Phase A binds to `hr.attendance`)
- `latitude`, `longitude` Float digits (10,7) required; `accuracy_m`, `speed_mps`, `heading_deg`, `battery_pct` Float optional
- `source` Selection `[('real','Real'),('sim','Simulated')]` default `real` index
- `ping_time` Datetime required default now index
- `company_id` m2o default current
- Composite SQL index `(user_id, ping_time DESC)` via `init()` (`CREATE INDEX IF NOT EXISTS`).
- `_check_coords` constrains lat ∈ [-90,90], lon ∈ [-180,180].

**`biz.geo.tracker`** (AbstractModel `biz.geo.tracker`, the public API — all reuse goes through it):
- `register_ping(vals)` — validates coords/throttle (reject if the same user posted < 5 s ago — one `search_count` on the index), stamps `user_id = self.env.uid` **server-side (never trust client identity)**, creates the ping.
- `get_live_positions(user_ids)` — latest ping per user in one query (`SELECT DISTINCT ON (user_id) … ORDER BY user_id, ping_time DESC`), excludes nothing by source (caller decides).
- `get_trail(user_id, date_from, date_to, include_sim=False)` — ordered [lat,lon,t] list for polylines.
- `gc_pings()` — cron daily; deletes pings older than `ir.config_parameter` **`biz_geo.retention_days`** (default `90`).

**`biz.geo.route.sim`** (the demo/testing utility — quarantined by design, see C18.7):
- `name`, `user_id` m2o, `route_geojson` Text (GeoJSON LineString), `speed_kmh` Float default 30, `progress_m` Float, `loop` Boolean default True, `active`, `session_model/session_id` (so sim pings bind like real ones)
- Cron `*/1 min`: for each active sim, advance `progress_m` by `speed_kmh` over the elapsed minute, emit **4 interpolated pings back-dated 15 s apart** (`source='sim'`) via `register_ping`-equivalent internal create (bypass throttle), wrapping at line end when `loop`. Include a pure-python haversine + linear interpolation helper (no external deps).

**PWA shell helper** (`controllers/pwa_shell.py`): a plain mixin class `GeoPwaShell` with `_make_manifest(name, short_name, scope, start_url, theme_color, bg_color, icons)` → JSON response, and `_make_service_worker(scope)` → serves `static/src/js/geo_sw.js` with `Content-Type: text/javascript` + `Service-Worker-Allowed: <scope>` (clone `website_event_track/controllers/webmanifest.py:14-58`). `geo_sw.js` does **app-shell caching only** (cache-first for the shell bundle, network-first for JSON) — no Background Sync.

**Leaflet**: vendor 1.9.x into `static/lib/leaflet/`. Tile URL from `ir.config_parameter` **`biz_geo.tile_url`** (default `https://tile.openstreetmap.org/{z}/{x}/{y}.png`) + `biz_geo.tile_attribution`, so a keyed provider (MapTiler/Mapbox) is a config swap. `geo_map.js` reads them via a `get_map_config()` method on `biz.geo.tracker`.

### 3.2 `pb_driver_checkin` — Payobook overlay (depends: `biz_geo_tracking`, `hr_attendance`, `pb_sidebar`, `pb_import_kit`)

```
pb_driver_checkin/
├── __manifest__.py            two asset bundles: web.assets_backend (cockpit) + pb_driver_checkin.assets_pwa
├── models/
│   ├── hr_attendance.py       in_mode/out_mode selection_add [('gps','GPS')] (ondelete 'set default'); pb_selfie_attachment_id m2o ir.attachment
│   └── pb_driver_map.py       pb.driver.map AbstractModel (cockpit + PWA JSON API)
├── controllers/driver_app.py  all /driver/* routes
├── security/
│   ├── driver_security.xml    group_pb_driver + record rules
│   └── ir.model.access.csv
├── data/
│   ├── pb_sidebar.xml         sidebar item(s)
│   └── demo_routes.xml        2 biz.geo.route.sim seeds (Hanoi ring, HCMC loop) — active=False
├── views/
│   ├── actions.xml            ir.actions.client tag pb_driver_map
│   └── driver_pwa_templates.xml  QWeb page for GET /driver
└── static/src/
    ├── js/driver_map.js|.xml  manager cockpit OWL component
    ├── js/driver_app.js       phone app (plain ES module, no OWL/webclient import)
    └── scss/ driver_map.scss (cockpit, pbim tokens) · css/driver_app.css (standalone, pbim VALUES copied — cannot @import backend scss)
```

**Security** (`driver_security.xml`):
- `group_pb_driver` "Driver" in category Payroll (implied: `base.group_user`).
- Record rules on `biz.geo.ping`: drivers → `[('user_id','=',user.id)]` read/create, no write/unlink (append-only); `hr_attendance.group_hr_attendance_officer` and up → all read. `biz.geo.route.sim`: system-admin only.
- Drivers get NO other Payobook access — cockpit sidebar items stay hidden for them (existing groups gating).

**Controller `/driver/*`** (`driver_app.py`):
| Route | Type/Auth | Behavior |
|---|---|---|
| `GET /driver` | http, `auth='user'` | Require `group_pb_driver` OR attendance officer (managers may preview); require `env.user.employee_id`, else friendly error page. Renders the PWA QWeb page pulling `pb_driver_checkin.assets_pwa`. |
| `GET /driver/manifest.webmanifest` | http, `auth='public'` | Via `GeoPwaShell._make_manifest` — name "Payobook Driver", scope `/driver`, theme `#0b1f3a`, module-static icons (192/512 PNG, generate simple navy square + white truck glyph). |
| `GET /driver/service-worker.js` | http, `auth='public'` | Via `_make_service_worker('/driver')`. |
| `POST /driver/state` | jsonrpc, `auth='user'` | Returns `{employee, attendance_state, checked_in_since, today_hours, last_ping_age}` for app boot/refresh. |
| `POST /driver/check_in_out` | jsonrpc, `auth='user'` | Validates driver group; calls `employee._attendance_action_change({'latitude':…,'longitude':…})` (seam §2); ensures `in_mode`/`out_mode` = `'gps'` (write post-hoc if not settable via the call); returns new state. |
| `POST /driver/ping` | jsonrpc, `auth='user'` | Rejects unless `employee.attendance_state == 'checked_in'`. Delegates to `biz.geo.tracker.register_ping` with `session_model='hr.attendance'`, `session_id=employee.last_attendance_id.id`. Validates numeric fields server-side. |
| `POST /driver/selfie` | jsonrpc, `auth='user'` | base64 JPEG/PNG, ≤ 5 MB, only while a check-in is in flight/just made; creates `ir.attachment` (`res_model='hr.attendance'`, `res_id`), links `pb_selfie_attachment_id`. |

**Phone app** (`driver_app.js`, plain JS ~300 lines): login handled by Odoo session (page is `auth='user'` — unauthenticated hits get Odoo's login redirect, which is fine on mobile). Flow: boot → `/driver/state` → render. Check-in button → `navigator.geolocation.getCurrentPosition` (highAccuracy, 10 s timeout; on failure show retry sheet — never check in without coords) → `/driver/check_in_out` → optional selfie sheet (`<input type="file" accept="image/*" capture="user">` — simpler + more compatible than getUserMedia) → start tracking: `navigator.geolocation.watchPosition` cached into a var + `setInterval` 15 s posting the freshest fix to `/driver/ping`; request `navigator.wakeLock.request('screen')` while checked in (re-acquire on `visibilitychange`); offline: failed pings pushed to a localStorage queue (cap 200), flushed FIFO on next success/`online` event. Check-out stops everything and releases the wake lock. All strings through a tiny `_t` dict (EN/VI) since the page doesn't load the webclient l10n stack.

**Manager cockpit** (`pb.driver.map` + `driver_map.js`, tag `pb_driver_map`):
- `get_live_data()` → `{drivers:[{id, name, avatar_url, job, checked_in (bool), since, last_lat/lon, last_ping_age_s, source, today_hours}], kpis:{active, idle_5m, checked_out, avg_hours}, map_config}`. Drivers = employees whose `user_id` has `group_pb_driver` (query via `group.users`), companies-scoped. Latest positions via `biz.geo.tracker.get_live_positions`. `_safe()` every metric.
- `get_driver_trail(employee_id, date)` → today's polyline (for the playback drawer).
- OWL component: Leaflet map (via `@biz_geo_tracking` `geo_map.js`) + right rail. Poll `setInterval(5000)` with `{silent:true}` context on the orm call (keep the global loading indicator quiet — same trick as the payrun wizard, memory `payobook-deploy`); `clearInterval` in `onWillUnmount`.
- **Demo mode** button (visible to system admins only): RPC `pb.driver.map.toggle_demo(active)` → checks the 2 seed sim routes' users in via the real `_attendance_action_change` path and sets `biz.geo.route.sim.active`; off = check out + deactivate. Seed routes: two `biz.geo.route.sim` data records with hand-plausible GeoJSON LineStrings (~30 points each) along Hanoi (Hoàn Kiếm → Long Biên loop, ~21.03 N 105.85 E) and HCMC (District 1 loop, ~10.77 N 106.70 E); attach to two demo driver employees created in the same data file (`noupdate="1"`).

### 3.3 Sidebar + icons (batched for phases A–E)
- Add to `ICONS` in `pb_sidebar/static/src/js/pb_sidebar.js`: `map-pin, truck, table, plane, scan, shield` (Lucide 24×24 paths, stroke-based like existing entries).
- New `pb.sidebar.item` "Driver Tracking" in the existing `workforce` section (icon `map-pin`, `action_tag='pb_driver_map'`, `match_action_tags`, groups: attendance officer+).

---

## 4. WOW-UX specification

**Design mandate applies** (memory `design-mandate` / `payobook-design-system`): locked palette, white surfaces + navy rail accents, no gradients, no emoji, Lucide icons, generous whitespace, real empty states.

1. **Driver PWA home** (single screen, thumb-first): navy header (`#0b1f3a`) with avatar + name + live status chip (grey "Off duty" / green pulse "On duty · 2h 14m"); dominant centered **circular check-in button** (~160 px, white on navy when off, navy on white ring when on, subtle shadow — no gradient); beneath it a **mini Leaflet map card** with own position; footer stats row (today's hours, pings sent, GPS accuracy). Selfie step = bottom sheet after check-in ("Add photo evidence — optional · Skip"). Status of the ping stream shown as a tiny heartbeat dot + "Last sent 12 s ago". Offline banner (amber) when queueing.
2. **Manager Live Map cockpit**: full-height Leaflet canvas; left rail (320 px, white card) listing drivers with avatar-initial markers matching map pins, freshness dot (green < 30 s, amber < 2 min, grey stale/off), "since 08:02 · 3.1 km today"; KPI strip on top (Active now / Idle >5 min / Off duty / Avg hours) in `pbim` KPI cards; clicking a driver flies the map to them and opens a popover (selfie thumbnail if any, check-in time, last ping, phone); "Demo mode" pill top-right (admin only, amber outline while active + "SIMULATED" watermark chip on sim markers).
3. **Route playback drawer** (stretch, only if the rest is done): bottom drawer with a time scrubber replaying today's trail polyline for the selected driver.
4. Map pins: circular avatar-initial markers in Payobook navy with white ring; sim markers get a dashed ring. Trail polyline in `--pbim-primary` at 60 % opacity.

---

## 5. Safety rails

1. **Never trust client identity or coords**: `user_id` from session server-side; numeric range validation; ping throttle ≥ 5 s server-side.
2. **Append-only pings**: no write/unlink for drivers (record rule) — audit integrity.
3. **Selfie privacy**: attachment `res_model='hr.attendance'` inherits attendance ACLs; drivers can see only their own (attachment access follows record access). No public URLs.
4. **Sim quarantine**: `source='sim'` never mixes into real analytics — any aggregate the cockpit shows must either exclude sim or label it SIMULATED; sim routes ship `active=False`, admin-gated toggle (C18.7).
5. **PWA page must not import the webclient bundle** — keep `assets_pwa` under ~150 KB gzipped (Leaflet + app). The phone page renders in < 2 s on 3G-fast.
6. **`selection_add` on `in_mode`/`out_mode` must pass `ondelete={'gps': 'set default'}`** or the module becomes un-uninstallable.
7. **Do not touch** `hr_attendance_geolocation`, `pb_hr_workforce`, or any payroll module in this phase.
8. Battery courtesy: the app sends pings at 15 s, not on every `watchPosition` fire.

---

## 6. Test cases (all must pass before report-back)

**Server (odoo shell / pytest-style):**
1. `register_ping` rejects lat 91 / lon 181 / sub-5 s repeat; accepts a valid ping and stamps session uid even when a different `user_id` is passed in vals.
2. Record rules: driver A (new test user in `group_pb_driver`) reads own pings, `search` as driver A on driver B's pings returns empty; driver cannot unlink own ping.
3. `/driver/check_in_out` as a driver creates `hr.attendance` with `in_mode='gps'`, coords set; second call closes it with `out_mode='gps'`.
4. `/driver/ping` while checked out → error payload, no ping row.
5. `get_live_positions` returns exactly one (latest) row per user with 3 pings inserted.
6. GC cron with `biz_geo.retention_days=1` deletes a back-dated ping, keeps today's.
7. Sim cron advances an active route: 4 new `source='sim'` pings, 15 s apart, positions strictly along the LineString; `loop` wraps.
8. Selfie endpoint rejects >5 MB and non-image mimetypes; success links `pb_selfie_attachment_id`.

**Chrome MCP (mandatory, memory `chrome-mcp-standing-approval`):**
9. `resize_page` to 390×844, navigate `https://payobook.com/driver` as a driver user → login → home renders; `emulate` geolocation (Hanoi coords) → tap check-in → status chip flips, mini-map centers; verify via RPC that the attendance row exists.
10. Wait ≥ 35 s → at least 2 pings exist; `emulate` new coords → marker moves on the manager map within 5 s poll (second page as Mitchell Admin at `/odoo/action-pb_driver_map`).
11. Manager cockpit: rail lists the driver, freshness dot green; click-to-follow flies the map; screenshot for the report.
12. Demo mode ON as admin → sim markers appear with dashed ring + SIMULATED chip and move over 2 minutes; OFF → they check out.
13. Manifest + SW: DevTools-equivalent check (`navigator.serviceWorker.getRegistrations()` via `evaluate_script`) shows the SW registered with `/driver` scope; page is installable (manifest fetch 200, correct `start_url`).
14. Driver user cannot open `/odoo/action-pb_driver_map` (access error) and sees no Payobook sidebar items.

---

## 7. Deploy & verify (live: Payobook19v2)

Follow memory `payobook-deploy` ritual exactly: rsync both modules → stop service → detached `systemd-run` install `-i biz_geo_tracking,pb_driver_checkin -u pb_sidebar` (sidebar icon/JS change ⇒ `-u`; never put `pb_hr_payroll_formula` in `-u`) → poll sentinel → grep log for ERROR → start service → Chrome-MCP verify (§6.9-14) on https://payobook.com. Bump manifest versions (C2). nginx: no new config needed (routes ride the existing proxy; SW + manifest are plain Odoo routes). If assets look stale: purge `/web/assets/%` attachments per the deploy memory.

---

## 8. Report back (numbered, in your final message)

1. Exact `_attendance_action_change` signature found and how `gps` mode was applied.
2. Final `assets_pwa` bundle size (gzipped) and page-load time on the throttled Chrome MCP run.
3. Any deviation from this doc (what + why), file list, and manifest versions shipped.
4. Results of test cases 1–14 (pass/fail each, with the two screenshots: driver PWA home, manager map with a live + a sim marker).
5. New gotchas hit → propose the C18 ledger addendum wording.
6. Confirmation that `pb_hr_workforce`, `hr_attendance_geolocation`, and payroll modules are untouched (`git status` scoped).

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_A_DRIVER_GPS.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding), then implement Phase A exactly as specified: new modules `biz_geo_tracking` + `pb_driver_checkin`, sidebar icons batch, tests §6, live deploy §7. Report back with the six numbered items in §8. Do not modify any module not listed in the doc.
