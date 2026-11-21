# TIERS T3b — clock in / out, the notice board, photos and downloads — implementation report (Opus)

Handover: `T3B_HANDOVER.md`. Ledger: `TIERS_LEDGER.md`. Not committed, not deployed.
Clone runs: `p0clone`, port 8099, staged from a clean `/tmp/deployMH` (final full run 2026-10-15 09:28–09:35 server
time, then a short re-run 09:37–09:39 after the last template tweak). Staged set: `pb_me_portal pb_me_portal_website
biz_access pb_zoho_bridge pb_demo pb_ess_workforce pb_ask_hr pb_sidebar pb_hr_comm pb_me_portal_comm pb_pay pb_timeoff
pb_onboarding pb_rnr pb_schedule pb_import_kit`. Before staging, every module I did not edit was hashed against the
server's copy (identical: pb_hr_comm, pb_sidebar, biz_access, pb_zoho_bridge, pb_demo, pb_me_portal_website, pb_ask_hr,
pb_schedule, pb_import_kit, pb_attendance_flow, pb_hr_workforce, pb_time_hub, pb_close, pb_lifecycle), and for the six
edited modules the file-level diff against the server was exactly my edits (T3a is already on the server).
`pb_schedule` and `pb_import_kit` were staged (unedited, identical) only so the two "reads a neighbour's file" suites
(TestP8Badges, pb_pay's static contract) stop failing as staging artefacts.

## 1. Files changed / added

| File | What |
|---|---|
| `pb_ess_workforce/models/hr_attendance.py` (new) | `pb_entry_source` `selection_add=[('portal', 'Self-service')]`, `ondelete set null` (pb_attendance_flow's exact shape); docstring: a portal row is not a device row, so HR deletes it like a grid row. |
| `pb_ess_workforce/models/ess_workforce.py` | `CLOCK_PARAM`, `CLOCK_DEBOUNCE_SECONDS = 60`, `CLOCK_WEEK_DAYS = 7`; `portal_clock_enabled(company)` (unset = on, exception-safe); `get_my_clock()` (state, since / since_label / since_date / since_ms, open minutes, today, today_closed, 7-day week with first-in / last-out / source / open, week total + max, last punch, tracking flag, server clock); `_clock_coords`; `clock_toggle(lat, lng, accuracy, nonce, ip_address=, browser=)` — own-employee guard, switch, 60 s debounce (`already=True`), stock `_attendance_action_change` under sudo, tag `portal` on the row it created. Module docstring gains "THE ONE PUNCH". |
| `pb_ess_workforce/models/res_config_settings.py` (new), `views/res_config_settings_views.xml` (new) | Non-stored boolean "Employees can clock in from their self-service pages" ↔ parameter per company; placed in the stock Attendances → Modes block. |
| `pb_ess_workforce/controllers/portal.py` | `GET /my/work/clock`, `POST /my/work/clock/toggle` (savepoint; errors render the page with the reason), `jsonrpc /my/work/clock/state`; the stale clock-in sentence is built here as ONE translatable sentence. |
| `pb_ess_workforce/views/portal_templates.xml` | Clock page (hero button, ring, timer, toast, error line, switched-off block, today card, 7-day strip, location note), "Clock" pill in the My Work nav (only when on), breadcrumb, home tile (only when on), 5 Lucide glyphs. |
| `pb_ess_workforce/static/src/interactions/clock.js` (new), `static/src/scss/ess_workforce.scss` | Live timer (server-clock corrected), press → ring closes, double-press lock, one-time location ask (≤ 4 s, only when the company keeps location), re-sync after the tab was hidden; styles + reduced-motion block. |
| `pb_ess_workforce/__manifest__.py` | 19.0.1.1.0 → **19.0.1.2.0**; settings view + clock.js registered. |
| `pb_ess_workforce/i18n/vi_VN.po` | 35 new entries + 2 existing entries gained the Clock page occurrence. |
| `pb_ess_workforce/tests/test_t3b_clock.py` (new), `tests/__init__.py` | T3b.1–T3b.5. |
| `pb_me_portal/models/pb_me_home.py` | Tiles `/my/work/clock` (time, timer, green) and `/my/notices` (people, megaphone, amber) + words; `week['clock']` via `_pbme_clock` (soft `optional`); `extra_cards` in `get_home_data`; hook `_pbme_extra_cards(emp)` + isolated `_pbme_extra_cards_safe`; `_pbme_photo_allowed` (the one D5 rule), `_colleague_photo_url`, `PHOTO_PLACEHOLDER`. |
| `pb_me_portal/controllers/portal.py` | `/my/photo` widened per D5 through `_pbme_photo_allowed`; 404s kept. |
| `pb_me_portal/views/portal_templates.xml` | This week card: clock line (live dot, "Clocked in since 08:02 · 3 h 12 m" + Clock out / "Not clocked in" + Clock in); bento renders extra cards after Needs you (`t-call="{{ card['template'] }}"`, `pbme-bento--extra`); icons megaphone, log-in, image, arrow-right. |
| `pb_me_portal/static/src/scss/me_portal.scss` | Clock line styles, extra-card placement (desktop: full row after Needs you, Me strip follows; phone order), breathing dot, reduced motion. |
| `pb_me_portal/__manifest__.py`, `tests/test_me_home_cards.py` | **19.0.3.3.0** + `test_06_font` pin. |
| `pb_me_portal/i18n/vi_VN.po` | 11 new entries (4 tile words, 7 card words). |
| `pb_me_portal/tests/test_t3b_photos.py` (new), `tests/__init__.py` | T3b.8, extra-card hook, tile registry. |
| `pb_me_portal/tests/test_portal_accounts.py`, `test_me_home.py`, `test_me_home_cards.py` | T2.6: a same-company colleague's photo is now 200, another company's 404; payload shape gains `extra_cards`; slot order allows extra cards between Needs you and Me. |
| `pb_me_portal_comm/` (new module, 19.0.1.0.0) | Manifest (spec name/summary, depends pb_me_portal + pb_hr_comm, auto_install, Hidden/Tools); `pb.me.notice.read` (unique pair via `models.Constraint`, company stored related); facade `pb.me.notices` (`get_my_notices`, `get_my_notice` with newer/older, `notice_counts`, `unread_count`, `mark_read`, `_notice_read_create` swallowing the constraint race); home hooks (Notices card + quiet needs-you row); controller (`/my/notices`, `/my/notices/<id>`, `notice_count` counter, styled 404); templates (tile, breadcrumbs, ago, home card, board, one notice, 404); scss; notices.js (j/k/arrows on the board, ←/→ newer/older); security (base.group_user 1110 + own rule, hr.group_hr_user 1111 + all rule, global company rule, **no portal row**); `i18n/vi_VN.po` (40 entries); tests T3b.6, T3b.7, T3b.11. |
| `pb_onboarding/models/hr_employee.py`, `controllers/portal.py`, `__manifest__.py` | `_pb_card` avatar → `_colleague_photo_url`; HR partner (a user) → their employee's photo route or the grey silhouette (`_ob_user_photo`). 19.0.1.0.6 → **19.0.1.1.0**. |
| `pb_rnr/controllers/portal.py`, `models/pb_rnr_wall.py`, `__manifest__.py` | `_rnr_card` avatar → photo route; `/my/recognition` rewrites the wall's story/winner avatars (`_rnr_portal_photos`) so the backend wall keeps `/web/image`; winners rows carry `employee_id` (additive). 19.0.1.1.1 → **19.0.1.2.0**. |
| `pb_pay/controllers/portal.py`, `__manifest__.py`, `tests/test_t3b_letter_token.py` (new), `tests/__init__.py` | Pay letter redirect carries the attachment's access token. 19.0.3.5.4 → **19.0.3.6.0**. |
| `pb_timeoff/models/pb_timeoff.py`, `__manifest__.py`, `tests/test_t3b_papers_token.py` (new), `tests/__init__.py` | Leave card papers carry the access token. 19.0.1.5.3 → **19.0.1.6.0**. |

## 2. Test results

Final full run (`-u pb_me_portal_comm,pb_me_portal,pb_ess_workforce,pb_pay,pb_timeoff,pb_onboarding,pb_rnr,pb_hr_comm,pb_ask_hr,pb_me_portal_website --test-tags /pb_me_portal,/pb_me_portal_website,/pb_me_portal_comm,/pb_ess_workforce,/pb_ask_hr,/pb_hr_comm,/pb_pay,/pb_timeoff,/pb_onboarding`; `pb_me_portal_comm` was `-i` on the first run):
```
odoo.tests.stats: pb_ask_hr: 23 tests · pb_ess_workforce: 120 tests · pb_hr_comm: 98 tests · pb_me_portal: 125 tests
                  pb_me_portal_comm: 14 tests · pb_me_portal_website: 6 tests · pb_onboarding: 4 tests
                  pb_pay: 128 tests · pb_timeoff: 80 tests
odoo.tests.result: 0 failed, 3 error(s) of 484 tests when loading database 'p0clone'
ERROR: TestPbMePortal.test_01_profile_change_flow_and_audit   <- pre-existing M19
ERROR: TestTimeoff.test_03_approve_and_refuse                  <- pre-existing, clone data (below)
ERROR: TestTimeoff.test_05_balance_math                        <- pre-existing, clone data (below)
```
The two pb_timeoff errors: those tests use `base.user_admin` as the approving officer, and on p0clone the admin login
is archived (`res_users id=2 active=f`), so the approval engine refuses with "Your account is no longer in use"
(`biz_approval_workflow/models/engine.py:1219`). Nothing in T3b touches approvals; my pb_timeoff change is the
papers link only. pb_rnr has no test folder (nothing to run; its code was loaded with `-u`). No new warning from
the T3b modules (the two "home section failed" warnings are pb_me_portal's deliberate `test_05_optional`).
Short re-run after the last template tweak (minutes under an hour shown as "N m"): `pb_ess_workforce` TestT3bClockModel +
TestT3bClockPages, `pb_me_portal` TestMeHomeCardsPage + TestMeHomeSource + TestT3bPhotoRule → `0 failed, 0 error(s) of 21
tests`, EXIT=0.

The first two runs found and I fixed: two existing pb_me_portal pins (payload keys, bento slot order — expected
updates), a 500 on the Clock page (`ValueError: incomplete format` from `'%g%%' % x` in a `t-att-style`), and two test
mistakes (the language switcher links to the current page; a regex that also matched the strip's `<ol>`).

| # | Test(s) | Result |
|---|---|---|
| T3b.1 | `test_t3b_1_punch_debounce_and_tag`, `_1b_` (check-out never relabels a device punch), `_1c_` (no employee → plain refusal) | pass. out/zeros → one row, `check_in`, `pb_entry_source='portal'`, `create_uid` = employee login → second press `already=True`, still one row → check-in moved back 2 min → `check_out` set, state out, "today 2 min". |
| T3b.2 | `test_t3b_2_location_…`, `_2b_no_tracking_no_location` | pass. With the company's "Device & Location Tracking" on: `in_latitude 10.77 / in_longitude 106.70`, `in_mode systray`; `lat='x'` → row created, no coordinates, no error. Tracking off → nothing kept even when sent. |
| T3b.3 | `test_t3b_3_switch_off_…` (facade + settings), `test_t3b_3b_switch_off_page_and_home` | pass. UserError "…switched off for your company. Use your usual device."; settings field writes '1'/'0'; page 200 with the off block, no button, no Clock pill; a POST renders "That did not go through." + reason, no row; home has no clock line. |
| T3b.4 | `test_t3b_4_…employee_login`, `_4b_…full_account`, `_4c_toggle_is_post_only` | pass. Page 200 (hero button "Clock in", 7 strip days) → POST → `?done=in`, `is-in is-just-in`, toast, timer → POST → `?done=already`, still one row → `/my` "Clocked in since", Clock out, Clock tile → JSON state `in` → 90 min later clock out → `/my/work/timesheet` shows 1.5 h → home "Not clocked in". GET on the toggle → 405, no row. |
| T3b.5 | `test_t3b_5_hr_removes_a_portal_row_like_a_grid_row` | pass. A non-admin attendance manager unlinks the portal row; a blank-source device punch still raises UserError. |
| T3b.6 | `TestT3bNoticesModel` (4) | pass. Own sent delivery only (another employee's and a scheduled post's rows excluded), excerpt, tokened poster URL, read False → `mark_read` → True, second `mark_read` OK, the raced writer (`_notice_read_create`) swallowed, one receipt, `create_uid` = employee; not-theirs/not-sent → False/None; another person's employee refused; newest first, newer/older links; home card + needs-you row "2 unread notices" (tone slate); archived post gone; no portal ACL. |
| T3b.7 | `test_t3b_7_board_notice_and_home` | pass. Empty board + empty card words → after a delivery: board hero with "New", home card with the subject, needs-you "1 unread notice" → notice page 200 with subject + body, dot fading, tokened poster → board without any unread mark → another employee's notice and a junk id → styled 404 → home without the row. |
| T3b.8 | `TestT3bPhotoRule`, `TestT3bPhotoRoute` (+ T2.6 updated) | pass. Own 200, same-company colleague 200, other company 404, archived 404, unknown 404, other size 404; `_colleague_photo_url` = route or the grey silhouette; `/my/orgchart` and `/my/recognition` as an employee login contain no `/web/image/hr.employee`. |
| T3b.9 | `TestT3bLetterToken`, `TestT3bPapersToken` | pass. Letter redirect `Location` carries `access_token`, the follow-up GET as the employee login returns the bytes; another person's letter never redirects to content. Leave card papers URL carries the token and opens for an employee login. |
| T3b.10 | the run above | pb_me_portal 125, pb_me_portal_website 6, pb_ess_workforce 120 (TestP8Badges green now that pb_schedule is staged), pb_ask_hr 23, pb_hr_comm 98, pb_pay 128, pb_timeoff 80, pb_onboarding 4 — only the 3 pre-existing errors above. |
| T3b.11 | `TestT3bPoGate` (3) + pb_me_portal's `test_12` | pass. All three files parse with `PoFileReader`; every entry has the module line, an occurrence, the `odoo-python` marker for code, a msgstr, no vendor name; every word of the notice board pages and of the Clock page/nav/tile/settings view has a Vietnamese line **for that very view** (occurrence-checked). Live: `/vi/my/work/clock` "Vào ca · Chạm để bắt đầu ngày làm việc", "7 NGÀY QUA"; `/vi/my/notices` "2 chưa đọc · 3 tổng cộng"; `/vi/my` "Chưa vào ca · Hôm nay 1 phút · Vào ca", card "THÔNG BÁO · 2 mới". |
| T3b.12 | browser walk | done, below. |

### T3b.12 — browser walk (clone, staged code, port 8099 local-only, tunnelled)
Own headless Chrome over DevTools (ledger T26). One temporary employee login `t3b.ui.employee@example.com` (portal
account) with three earlier days of punches and three sent notices (one with a poster), seeded with pb_hr_comm's own
`_hc_move` states + delivery rows. Now **archived with a scrambled password**; the UI server is stopped, the tunnel closed.
Walk: sign-in → `/my` → Clock page at rest (button, today card, 7-day strip) → press → `?done=in`, toast "You are clocked
in. Have a good day.", ring closed green, timer, address bar cleaned → `/my` week card "Clocked in since 20:25 · 0 m" +
Clock out, needs-you "3 unread notices · Town hall on Friday at four", Notices card with three items → phone width (390 px)
home and Clock page → notice board (hero card with poster, quiet list) → open the newest (dot fades) → board shows 2
unread → phone board → after 62 s (debounce) Clock out from the home card → Clock page "You are clocked out…" → timesheet →
`/my/notices/999999999` styled 404 → Vietnamese pages. CSS bundle has no error banner (T24 check). Console: nothing from
these pages; only the clone's website-logo 500 (filestore lacks the file, every page) and the intended 404.
(Times read as Sydney: signing in from the headless browser set the user's timezone to the browser's.)
Fixed after the walk: an empty ring arc drew a dot at rest (hidden now); the strip showed "22:45 h", which reads like a
clock time — it now shows decimal hours like the timesheet ("22.8 h", "6.5 h"; under an hour "1 m").
Screenshots (21): scratchpad `walk/shots/` (not versioned).

## 3. Design self-score against the bar
- **Hero moment 1 — the clock.** One 244 px round button: primary "Clock in / Tap to start your day" at rest (hover
  previews the arc), pressed → the ring draws closed while the page goes; the page that comes back finishes closing it
  and pops the face; clocked in → white face, big "3 h 12 m", "since 08:02", a Clock out pill, a green ring with a soft
  breathing halo, a live dot and one sentence under it. Clock-out unwinds the ring. Beside it: today's total ("In at
  08:02, out at 17:00") and the last 7 days as bars (today in brand colour, an open day green). The home's This week card
  carries the same state, live, with a one-tap button.
- **Hero moment 2 — the notice board.** The newest notice is a full-width card with its poster (image left, words right,
  "New" tag, "Read the notice →"); the rest a quiet list with an unread dot that is gone once read; opening a notice draws
  its dot once and fades it. The home shows the latest three side by side in a "Notices" card with "3 new".
- **Zero dead-ends.** Off for the company → a page that says so and points to the timesheet; a refused punch → the page
  with the reason and the next step; a double press → "already done a moment ago"; still clocked in from an earlier day →
  one sentence with the day and time and "Ask for a fix"; no punches yet → "Your first tap starts today's count"; no
  notices → "No notices yet. When HR posts one, it lands here."; a notice not theirs → styled 404 with the way back; no
  employee → the module's existing styled page.
- **Motion with purpose**: ring close/unwind, face pop, breathing halo (the one loop), bars grow, toast slides, dot fades;
  all off under reduced motion (the dot still disappears, without motion).
- **Keyboard**: the button is a real form button (Enter/Space); j/k/arrows/Home/End on the board; ←/→ newer/older on a
  notice. **Plain words** throughout; no vendor or product name in new strings (see decision 3).
- Self-score **8.5/10**. Short of 10: the punch is a full-page round trip (the ring animation bridges it, but it is not an
  in-place update); no "breaks"; the poster thumbnail on the home card makes the first card taller than its neighbours.

## 4. Learn impact
Grepped `learn_content.json`, `anchors.json`, `engine/screens.js`, `engine/fixture.js`, `docs/tutorial_poc/author/data.js`
for the home's This week card, `/my/work/*`, clock and notices: no lesson describes them (the only `/my` mention is
"Only an employee? You start on My Payobook"). **Nothing in Learn is affected.**

## 5. Decisions the handover did not make + proposed ledger rows
1. **Only the row we create is tagged `portal`.** A clock-out closes whatever row is open — possibly a device check-in —
   and relabelling it would strip that device punch of its delete guard. Tested (T3b.1b).
2. **Location follows stock's "Device & Location Tracking" switch** (default off): with it off nothing is kept and the
   browser is never asked; with it on, coordinates/IP/browser are kept like stock's systray punch. Mode is `systray`
   (stock has no `gps` mode value). `accuracy` and `nonce` are accepted and not stored (no stock field; the debounce is
   the double-submit guard).
3. **No product name in new user-visible strings** (white-label tenants): the refusal says "Clocking in from these pages
   is switched off…", the off page "Clocking in here is off for your company", the setting "Employees can clock in from
   their self-service pages", the selection label "Self-service". The handover's manifest summary "Company notices on
   My Payobook" was kept verbatim as specified — Fable may want it neutral too.
4. **`_colleague_photo_url` is not a bare alias**: it returns the route when the reader may see that face and the grey
   silhouette (`/base/static/img/avatar_grey.png`) otherwise, so an archived or other-company person never shows as a
   broken image. One rule (`_pbme_photo_allowed`) serves the route and the helper.
5. **pb_rnr's wall feeds the backend too**, so `/my/recognition` rewrites the wall's avatars in its own controller
   (backend keeps `/web/image`); winners rows gained an `employee_id` key for that.
6. **pb_timeoff's papers link is the Leave desk's approval queue** (backend, officers only — no employee login reaches it).
   Tokened anyway per D6 for one link shape (it is a harmless write of a token on read).
7. **Notices**: an archived announcement disappears from the board (archive is pb_hr_comm's "instead of delete"); a person
   without a work email has no delivery row and so no notice (D4: the delivery row is the audience truth). Posts in
   `sending` are not shown until `sent` (handover wording).
8. **Read receipts rule**: besides the global company rule, a full-account employee reads only their own receipts and the
   HR team all (group rules) — tighter than "company rule only".
9. **Extra cards sit after Needs you** (full width on desktop, the Me strip follows; phone after Leave); the Notices card is
   always drawn (with the empty words) so the door exists from day one.
10. **Minutes and hours words**: the timer uses "h" / "m"; Vietnamese keeps pb_ess_workforce's existing "h" and adds
    "phút"; the home card uses "giờ / phút". Small hours are shown as decimal hours like the timesheet ("6.5 h").

### Proposed ledger rows
| # | Gotcha / fact | How to apply |
|---|---|---|
| T29 | A QWeb attribute expression `'--x: %g%%' % v` 500s the page with `ValueError: incomplete format`. | Write `'--x: %g' % v + '%'` (the MEHOME bars already do). |
| T30 | Every website page carries the language switcher, which links to the CURRENT URL: "page X has no link to X" is always false. | Assert on the component's own markup (`<span>Clock</span>`, a class), never on a bare `href`. |
| T31 | p0clone's `base.user_admin` is archived: pb_timeoff `TestTimeoff.test_03/test_05` error "Your account is no longer in use" there. | Known clone-data errors; do not chase them in a phase run. |
| T32 | Suites that read a neighbour's files by path (pb_pay static contract → pb_import_kit, TestP8Badges → pb_schedule) fail when the neighbour is not staged. | Stage `pb_import_kit` and `pb_schedule` (unedited, hash-checked) in `/tmp/deployMH`. |
| T33 | Signing in from a headless browser sets the user's timezone to the browser's (the walk login became Australia/Sydney). | Read times in a walk in the browser's zone, or set the tz after the first sign-in. |
| T34 | Stock keeps punch location / IP / browser only when the company's "Device & Location Tracking" is on (default off). | The portal clock follows the same switch; tests turn it on to see coordinates. |

## 6. "Left" — not edited, and why
- All four photo modules and both download modules depend on pb_me_portal, so none had to be left for that reason.
- **Backend-only / e-mail-only photo lines, unchanged on purpose** (an internal user loads `/web/image` fine):
  pb_onboarding `buddy_nomination.py:195`, `pb_onboarding.py:148` (backend board), `journey_ext.py:351` (welcome
  e-mail, absolute URL); pb_rnr `celebration.py:130` (the portal template draws no avatar from it), `digest.py:122,168,205`
  (digest e-mail), `cycle.py:103`, `pb_rnr.py:176,349` (backend boards); pb_timeoff `pb_timeoff.py:92` (Leave desk);
  pb_hiring `pb_hiring.py:282` (backend board).
- **Other tokenless downloads from T2 §3** (pb_training `claim.py`, pb_hiring `facade_p6.py`, `offer.py`, `board_p1.py`,
  `forms_p2.py`) were not in T3b's scope (D6 names pb_pay and pb_timeoff only).
- **Found, not fixed (outside scope)**: pb_onboarding's `/my/buddy/handover` passes `temp_id` to `set_temp_buddy` without
  checking it against the offered options, so any employee id (any company, archived or not) could become a joiner's
  stand-in; and its team strip shows the manager without a company check. The photo route now refuses those faces
  (silhouette), but the cards themselves are a pb_onboarding fix.

## 7. Self-review
**Scope**
1. Clock (facade, switch, debounce, stock punch under sudo, tag, routes incl. JSON, page, script, home line + tile, VI,
   version 19.0.1.2.0; pb_me_portal 19.0.3.3.0 + pin): done. Deviations: decisions 1–3.
2. Notice board (glue module, model with Constraint, facade, routes, extra-card registry + Notices card, needs-you row,
   tile, VI, no portal ACL): done. Deviation: decision 8 (tighter rules).
3. Photos (route widened, `_photo_url` unchanged, `_colleague_photo_url`, portal-facing lines in pb_onboarding and pb_rnr)
   and tokened downloads (pb_pay, pb_timeoff), minor bumps: done. Deviations: decisions 4–6.
4. Translations (three rules, parse gate, per-view coverage) and Learn (nothing affected): done.
5. Tests T3b.1–T3b.12: done; only the three pre-existing clone errors remain.

**Non-goals**
- No selfie, geofence, kiosk/device change, `/driver` change, breaks: done (untouched).
- No posting/comments/reactions on notices, no field on `pb.hr.comm.post` / `pb.hr.comm.delivery`, scheduled posts never
  show: done (tested).
- No edits to modules without the pb_me_portal dependency: done (none needed).
- No portal ACL rows (tested), no vendor name in any user-visible string (gates + decision 3): done.

**Safety rails**: every sudo write follows `_require_own_employee` / `_own` / the session employee, and no route reads an
employee id; the toggle is POST-only (405 on GET), runs in a savepoint, never raises past the route; the debounce makes a
double submit harmless (tested); the notice page prints only the Html field's stored value.

**Side effects on the clone only**: p0clone has pb_me_portal_comm 19.0.1.0.0 installed and the bumped modules upgraded;
three sent test announcements ("Town hall on Friday at four", "New parking rules from Monday", "Payslips now arrive on the
25th") with deliveries for the archived walk login, and that login's punches. Live service, port 8069 and the payobook
database were not touched.
