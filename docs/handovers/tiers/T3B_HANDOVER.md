# TIERS T3b — clock in/out on My Payobook + the notice board + photo/download leftovers (handover for Opus)

Read first: `TIERS_PROGRAM.md`, `TIERS_LEDGER.md` (rules T-R1…R12, rows T1–T23+), `T2_REPORT.md`, `T3A_HANDOVER.md`
+ `T3A_REPORT.md` (T3a added the needs-you registry `_pbme_needs_extra`, the generic need row, tiles for Ask HR /
My requests — build on those hooks, do not re-create them). Repo `CLAUDE.md` applies (one addons dir; never "Odoo"
in a user-visible string). You do not deploy; Fable does. Plain words in every string a person can see.

## What T3b is, in the owner's words
"Features should be provided in the portal itself, e.g. entering timesheet." After T3b every employee (employee
login or full account) can **clock in and out from My Payobook** (today `/driver` needs a full account and a driver
group), sees **company notices** on their home and on a notice board page, and the employee-login leftovers from
T2 (colleague photos, two download links) are closed.

## Design (binding — the owner's bar, verbatim)
"**extreme WOW, intuitive, out-of-this-world experience, best in class.**" Not "clean and functional" — the screen
should make someone stop. Every surface you build must state and satisfy: a **hero moment** (name it in the
report); **zero dead-ends** (every state designed, every failure names its reason and next step);
**plain-language over code vocabulary**; **motion with purpose**; **keyboard + bulk ergonomics** where rows are
involved; measured against the best consumer/SaaS tool in that category (Deputy / When I Work clock-in, Workplace
/ Staffbase notice feeds), not against stock. Look = MEHOME's (`pbme-*`, pbim tokens, Inter, Lucide SVG; no emoji,
no gradients, no stock portal tables).
Hero moments for T3b: (1) **the clock** — one large round button that reads "Clock in" at rest and, once in,
turns into a live timer ("3 h 12 m · since 08:02") with a soft breathing ring; the first press animates the ring
closed; under it today's total and a 7-day strip of worked hours; the "This week" card on the home carries the same
state and a one-tap button. (2) **the notice board** — the newest notice is a full-width card with the poster image
(when there is one), the rest a quiet list with an unread dot that fades when read; the home shows the latest 3 in
a "Notices" card. Empty states say what will appear ("No notices yet. When HR posts one, it lands here.").

## Decisions already taken (do not re-open)
- **D1 Clock in/out lives in `pb_ess_workforce`** (owns `/my/work/*`, depends on hr_attendance via
  pb_attendance_flow / pb_hr_workforce). Route `/my/work/clock`. pb_me_portal only gets a tile row and a soft read
  for the home card.
- **D2 The punch is stock's own method under sudo after the ownership guard**:
  `emp.sudo()._attendance_action_change(geo)` (`hr_attendance/models/hr_employee.py:208-245` has no group check;
  stock calls it on sudo records from public kiosk routes `hr_attendance/controllers/main.py:193-211`). The row is
  tagged `pb_entry_source = 'portal'` (`selection_add` in pb_ess_workforce on `hr.attendance`; the base selection is
  pb_hr_workforce's `grid`, extended by pb_attendance_flow at `pb_attendance_flow/models/hr_attendance.py:33-35` —
  clone that exact shape, `ondelete={'portal': 'set null'}`). A `'portal'` row is NOT a device punch
  (`_is_device_row` reads blank source) — so the delete guard treats it like a grid row; say so in a comment.
- **D3 Per-company switch, no stored field**: `ir.config_parameter` `pb_ess_workforce.portal_clock.<company_id>`
  (`'1'` = on; **default on when unset**), a `res.config.settings` boolean "Employees can clock in from My
  Payobook" with help "When off, the Clock page and the home button are hidden; devices and the field app still
  work." Geolocation is optional and never required: the page asks the browser once; if refused the punch still
  goes through, tagged without coordinates.
- **D4 Notices = pb_hr_comm's delivery rows** (`pb.hr.comm.delivery`, `pb_hr_comm/models/delivery.py:25-50`: one
  row per post + employee, `sent_on`; post `state == 'sent'`, `subject`, `body_html`, `poster_ids`). That is the
  audience truth; nothing re-computes audiences. Read receipts are a NEW table in a NEW glue module
  `pb_me_portal_comm` (depends `pb_me_portal`, `pb_hr_comm`; `auto_install: True`; precedent `pb_me_portal_website`):
  `pb.me.notice.read` (`post_id`, `employee_id`, `read_on`, unique pair via `models.Constraint` — Odoo 19 ignores
  `_sql_constraints`, see the comment in `delivery.py:46-50`). No field is added to pb_hr_comm.
- **D5 Colleague photos**: an employee login may see colleagues' photos (that is what stock `hr.employee.public`
  exists for). The T2 route `/my/photo/<id>/<size>` (pb_me_portal) widens from "own employee only" to "own
  employee, or an ACTIVE employee of one of the companies the person's own employee records belong to"; anything
  else 404. Modules that already depend on pb_me_portal switch their colleague-photo URLs to it; modules that do
  not are listed, not edited.
- **D6 Tokened downloads** for pb_pay (`controllers/portal.py:102`, the pay letter) and pb_timeoff
  (`pb_timeoff.py:203`): the same `generate_access_token` + `?access_token=` pattern T2 used (ledger T20). Both
  modules depend on pb_me_portal (check their manifests; if one does not, leave it and list it).
- **D7 Portal seams stay sudo after an ownership guard (T-R11)**; no `base.group_portal` ACL rows; no new stored
  field on an existing model; new tables only in the new glue module.

## Scope (binding)

### 1. Clock in/out — `pb_ess_workforce`
Read `pb_ess_workforce/models/ess_workforce.py` whole (`_own_employee` `:64`, `_require_own_employee` `:77`,
`get_my_week` `:285`, `get_my_counters` `:570`, `_tzinfo`), `controllers/portal.py` (`/my/work/timesheet` `:98`
and its template as the shape precedent), the module's SCSS/JS, and stock `hr_attendance/models/hr_employee.py:208-245`.
- Facade `pb.ess.workforce`:
  - `portal_clock_enabled(company)` → bool from the parameter (D3).
  - `get_my_clock()` → `{enabled, state: 'in'|'out', since (iso, employee tz), open_attendance_id, today_minutes,
    week: [{day, iso, minutes, first_in, last_out, source}], last_punch: {when, kind}}`. Reads `hr.attendance` sudo
    for the employee only; minutes from `worked_hours`; "today"/"week" in the employee's tz (`_tzinfo`).
  - `clock_toggle(lat=None, lng=None, accuracy=None, nonce=None)` → `_require_own_employee()`; if not enabled →
    UserError "Clocking in from My Payobook is switched off for your company. Use your usual device."; **debounce**:
    if the last punch is < 60 s old → return the current state with `already=True` (a double tap never creates a
    second row); geo = `{'mode': 'systray' or 'gps', 'latitude', 'longitude'}` only when both coordinates parse
    (read how `_attendance_action_change` maps keys at `:208-245`; pass `browser=…`/`ip_address` as the method
    expects); `att = emp.sudo()._attendance_action_change(geo)`; `att.sudo().write({'pb_entry_source': 'portal'})`
    when the field exists; return `get_my_clock()` + `{'punched': 'in'|'out'}`.
- Routes (`controllers/portal.py`): `GET /my/work/clock` (auth user, website) — 404-style quiet page when disabled
  (not a stock 404: the `pbme` empty block "Clocking in from My Payobook is off for your company"); `POST
  /my/work/clock/toggle` (form: `lat`, `lng`, `accuracy`, `nonce`) → redirect to `/my/work/clock?done=in|out|already`
  and the page renders the toast. Also `type='jsonrpc'` `POST /my/work/clock/state` returning `get_my_clock()` so
  the timer can refresh after a punch without reload (optional; the form flow must work without JS).
- Frontend (`static/src/...` in `web.assets_frontend`, interaction style as pb_me_portal's `me_home.js`): the live
  timer (counts from `since`), the ring animation on state change, the one-time `navigator.geolocation` ask that
  fills the hidden fields and never blocks submit (timeout 4 s), prefers-reduced-motion respected.
- Home: pb_me_portal's "This week" card (`pbme_card_week`, `portal_templates.xml:311-341`) gets a clock line and
  button when `week.clock` is present: `pb.me.home` reads `pb.ess.workforce.get_my_clock` through `optional()`
  (soft — pb_me_portal does not depend on pb_ess_workforce) and puts it under `week['clock']`; the card shows
  "Clocked in since 08:02 · 3 h 12 m" + "Clock out" (form POST to the toggle route) or "Not clocked in" + "Clock in".
  Tile row `/my/work/clock` in `_TILE_ROWS` (group `time`, icon `timer`), `_TILE_WORDS` "Clock in / out" ·
  "Start and end your day", VI in `pb_me_portal/i18n/vi_VN.po`.
- Versions: `pb_ess_workforce` → `19.0.1.2.0`; `pb_me_portal` → `19.0.3.3.0` (+ `test_06_font` pin).

### 2. Notice board — new glue module `pb_me_portal_comm`
Manifest: name "Employee Self-Service Portal — notices", summary "Company notices on My Payobook", depends
`['pb_me_portal', 'pb_hr_comm']`, `auto_install: True`, category Hidden/Tools, version `19.0.1.0.0`, data:
security csv (the read model: `base.group_user` 1,1,1,0 + `hr.group_hr_user` 1,1,1,1; company rule; **no portal
rows** — the portal writes under sudo), views (portal templates), `i18n/vi_VN.po`.
- Model `pb.me.notice.read` (D4). Facade `pb.me.notices` (AbstractModel): `get_my_notices(emp, limit=None,
  unread_only=False)` → rows `{post_id, subject, sent_on, excerpt (first 160 chars of the text of body_html), has_poster,
  poster_url (tokened `/web/content/<att>?access_token=`), read (bool)}` from `pb.hr.comm.delivery` sudo
  `[('employee_id','=',emp.id), ('post_id.state','=','sent')]` ordered `sent_on desc`; `mark_read(emp, post_id)`
  (sudo create-if-missing); `unread_count(emp)`.
- Routes: `GET /my/notices` (list, unread first? no — newest first, unread dot), `GET /my/notices/<int:post_id>`
  (ownership = a delivery row for the session's employee, else 404; renders `subject`, `sent_on`, `body_html`
  sanitized as-is, posters as images/links with tokens; marks read on open).
- Home: a "Notices" card — T3a's hooks give needs-you rows, not cards; add the small card registry now:
  `pb.me.home._pbme_extra_cards(emp)` → list of `{'key', 'template', 'data'}` (no-op base), rendered by
  `pbme_bento` after the three cards with `t-call="{{card.template}}"`; pb_me_portal_comm overrides it to add
  `pbme_card_notices` (latest 3: subject, "2 d ago", unread dot; footer link "All notices"; empty state words).
  Needs-you row via `_pbme_needs_extra`: "2 unread notices" → `/my/notices` (tone quiet, not `act`).
- Tile `/my/notices` in `_TILE_ROWS` (group `people`, icon `megaphone`), words "Notices" · "What the company
  announced", VI.

### 3. Photos and downloads (D5, D6)
- `pb_me_portal` photo route (`controllers/portal.py`, the T2 `/my/photo/<id>/<size>` handler and
  `pb.me.home._photo_url`): widen per D5; keep the 404s; keep `_photo_url` the single URL builder. Add
  `pb.me.home._colleague_photo_url(employee, size)` = the same route (alias for readability).
- Replace colleague-photo URLs with the route in modules that depend on pb_me_portal: check manifests of
  pb_onboarding, pb_rnr, pb_timeoff, pb_hiring (T2_REPORT §3 lists the exact lines: pb_onboarding
  `models/hr_employee.py:199`, `buddy_nomination.py:195`, `journey_ext.py:351`, `pb_onboarding.py:148`,
  `controllers/portal.py:455`; pb_rnr `pb_rnr_wall.py:88,126`, `celebration.py:130`, `digest.py:122,168,205`,
  `cycle.py:103`, `pb_rnr.py:176,349`, `controllers/portal.py:228`; pb_timeoff `pb_timeoff.py:92`; pb_hiring
  `pb_hiring.py:282`). **Only portal-facing lines** (what a `/my` page renders) change; backend/digest e-mail lines
  stay. A module without the dependency: list it under "left".
- Tokened downloads: pb_pay `controllers/portal.py:102`, pb_timeoff `pb_timeoff.py:203` (D6).
- Versions: bump the minor of every module you touch here.

### 4. Translations and Learn
Same rules as T3a §3 (three PO rules + the parse gate) and §4 (Learn: grep for the home's "This week" card and
the `/my/work/timesheet` page; update lesson words if a lesson describes them; report).

### 5. Tests (numbered; clone run T-R9, ledger T17 log trick)
Fixtures as T3a (`share_emp`, `plain`, `hr`).
- **T3b.1** `get_my_clock()` for `share_emp` with no rows → `state='out'`, zeros; `clock_toggle()` → one
  `hr.attendance` for their employee, `check_in` set, `pb_entry_source='portal'`, `create_uid` = the share user;
  immediate second `clock_toggle()` → `already=True`, still one row; after patching the debounce window (or moving
  `check_in` back 2 min) → `check_out` set, `state='out'`, `today_minutes` > 0.
- **T3b.2** geo: `clock_toggle(lat='10.77', lng='106.70', accuracy='12')` → the row's `in_latitude/in_longitude`
  (whatever stock names them) set; `clock_toggle(lat='x')` → row created without coordinates, no error.
- **T3b.3** parameter off for the company → `clock_toggle` raises UserError with the plain message; `GET
  /my/work/clock` 200 shows the "switched off" block, no button; home card shows no clock line.
- **T3b.4** HttpCase as `share_emp` and `plain`: `GET /my/work/clock` 200 (hero button, "Clock in"); `POST
  …/toggle` → redirect `?done=in`, page shows the timer; `POST` again within 60 s → `?done=already`; the home `/my`
  shows "Clocked in since …" in the week card; `/my/work/timesheet` shows the day with the punch.
- **T3b.5** the delete guard: a `'portal'` row can be unlinked by HR like a grid row (read
  `pb_attendance_flow/models/hr_attendance.py:42+` and assert the documented behaviour).
- **T3b.6** notices: a sent post with a delivery row for `share_emp`'s employee and one for another employee →
  `get_my_notices(emp)` returns one row, `read=False`; `mark_read` → `read=True`, second `mark_read` → no
  duplicate (constraint path handled, no error); a draft/scheduled post's delivery row (if such a row can exist)
  is excluded; `unread_count`.
- **T3b.7** HttpCase as `share_emp`: `GET /my/notices` 200 with the unread dot; `GET /my/notices/<post>` 200
  shows subject + body; after it, the dot is gone; another employee's post → 404; home `/my` shows the Notices
  card with the subject and the needs-you row "1 unread notice"; with no deliveries: the empty-state words.
- **T3b.8** photo widening: `share_emp` can fetch `/my/photo/<colleague same company>/avatar_128` 200; an
  employee of another company → 404; an archived colleague → 404; own → 200 (T2 test still passes).
- **T3b.9** tokened links: `/my/pay/letter/<id>` redirect carries `access_token` and the follow-up GET as
  `share_emp` is 200; pb_timeoff's link likewise (skip when the module is absent).
- **T3b.10** Existing suites green: pb_me_portal (T1/T2/T3a tests), pb_me_portal_website, pb_ess_workforce (the
  `TestP8Badges` staging artefact is known), pb_ask_hr, pb_hr_comm. Clone: `-i pb_me_portal_comm -u
  pb_me_portal,pb_ess_workforce,<touched modules> --test-tags /pb_me_portal,/pb_me_portal_website,/pb_me_portal_comm,
  /pb_ess_workforce,/pb_ask_hr,/pb_hr_comm,<touched>`; stage everything T3a staged plus `pb_me_portal_comm`,
  `pb_hr_comm`, `pb_pay`, `pb_timeoff` and any module you edited.
- **T3b.11** PO gate on every `.po` you wrote or edited.
- **T3b.12** Browser check on the clone as a temporary employee login: clock in → timer → clock out; home card;
  notice board (a sent post seeded through pb_hr_comm's own flow or a direct sudo create of post + delivery);
  console clean; archive the temporary logins after.

## Non-goals (do not do)
- No selfie, no geofence, no device/kiosk changes, no change to `/driver` (drivers keep it). No break tracking.
- No posting of notices from the portal; no comments/reactions on notices; no new fields on `pb.hr.comm.post` or
  `pb.hr.comm.delivery`; scheduled (not yet sent) posts never show.
- No edits to modules that do not depend on pb_me_portal for the photo/download leftovers — list them.
- No portal ACL rows; no vendor name in any user-visible string.

## Safety rails
- Every sudo write sits after `_require_own_employee()` / the session-employee guard; `employee_id` is never read
  from the request.
- The punch path never raises past the route: errors render the page with the reason and the next step.
- The debounce makes a double submit harmless; the toggle route is POST-only.
- The notices page renders `body_html` as pb_hr_comm stored it (already sanitized by the Html field); never
  `t-raw` anything else.

## Report back (write `docs/handovers/tiers/T3B_REPORT.md`)
1. Files changed/added. 2. T3b.1–T3b.12 results with the clone log's summary lines and the browser walk. 3. Design
self-score against the bar (hero moments named). 4. Learn impact. 5. Decisions + proposed ledger rows. 6. "Left"
list (modules not edited and why). 7. Self-review per Scope and Non-goal item.
