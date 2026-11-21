# WDGAP QF5 — report: two-step sign-in required by role; sign-out when idle

Branch `wdgap-qf5` (from `origin/19.1`), pushed, NOT merged, NOT deployed. No live server or
live database was touched. Built, tested and self-reviewed by the implementation agent.

## 1. What was built

**A. "Two-step sign-in is required for…"** — a switch on the Access home (People list,
beside "Close leavers' logins", in both the classic board and the Studio people list): Nobody
(default) / These roles… / Every staff login. A covered staff login with no authenticator app
is sent, on its next page, to a setup page `/web/two-step` (picture to scan + typed setup key,
6-digit code, current password when the login has one). Turning the rule on signs out the people
it newly covers who have no app yet (never the administrator saving it). The card shows
"N of M set up" and an amber "K to set up" chip; the dialog lists who has not set it up and says
how many people saving will sign out. The desk's "Turn off two-step sign-in" now says "They will
be asked to set it up again the next time they sign in." for a covered person.

**B. "Sign people out after … minutes without activity"** — same card/dialog: Off (default) /
15 / 30 / 60 / 120 minutes. A browser service (web client and My Payobook pages) watches pointer,
keyboard and touch, shares the last moment across tabs (localStorage), tells the server at most
once a minute while the person is active, shows a one-minute warning with "Stay signed in", then
signs out and comes back to the same screen after sign-in. The server keeps its own clock
(`pb_last_active` in the session, refreshed only by that call and by a page the person opens) and
signs a session out on its next request once it is idle past the limit + 2 minutes.

Files (all in `biz_access`; version **19.0.1.12.1 → 19.0.1.13.0**; no other module touched):

| File | What |
|---|---|
| `models/two_step_rule.py` (new) | the whole kernel for A: parameter read, coverage, exemptions, setting API, preview, sign-out of newly covered, History rows |
| `models/idle_rule.py` (new) | the whole kernel for B: parameter, expiry test, page-navigation test, setting API |
| `models/ir_http.py` | the two gates (idle check in `_authenticate`, two-step door in `_pre_dispatch` after the first-password door), page stamp, `pb_idle_minutes` in both session infos |
| `controllers/two_step.py` (new) | `GET/POST /web/two-step`, `GET /web/two-step/qr` |
| `controllers/alive.py` (new) | `POST /web/session/alive` |
| `views/two_step_templates.xml` (new) | the setup page (sign-in layout, classes only) |
| `static/src/js/idle_watch.js` (new) | one service, both bundles |
| `static/src/scss/sign_in_rules.scss` (new) | warning, card, setup page (both bundles) |
| `static/src/js/access_board.js`, `xml/access_board.xml`, `xml/access_studio.xml` | the card + dialog; A7 confirm line |
| `models/account_desk.py` | A7: passport flag + message |
| `i18n/vi_VN.po` | 61 new Vietnamese entries + 4 amended (markers/occurrences) |
| `tests/test_wdgap_qf5_two_step.py`, `tests/test_wdgap_qf5_idle.py` (new) | 21 tests, tag `wdgap_qf5` |

## 2. Tests

Local: `qf5_base` (a copy of `qf3_base`: 273 modules incl. auth_totp, website, pb_demo,
pb_tenancy, pb_me_portal, biz_deroute, pb_zoho_sso, pb_clock), runs IN PLACE (disk full, ledger W6).

| # | Case | Test | Result |
|---|---|---|---|
| 1 | Defaults change nothing; no idle value in session info | `TestQf5TwoStep.test_01`, `TestQf5Idle.test_01` | PASS |
| 2 | Setting API: non-manager refused; Nobody/roles/all; bad ids dropped; idle 1–4 refused; card counts | `test_02_setting_api` | PASS |
| 3 | Roles mode: holder gated from `/odoo`, `/bizapp`, `/my` (with `redirect=`); non-holder, holder with app, removed assignment not; lent holder gated | `test_03_roles_mode` | PASS |
| 4 | `all` covers every staff login, not a portal login | `test_04_all_mode` | PASS |
| 5 | Exemptions: recovery login (by its setting), support session, exempt-logins parameter (case-insensitive), demo-group member; exempt people not counted on the card | `test_05_exemptions` | PASS |
| 6 | Reachable while gated: setup page, its picture, its POST, a static file, `/web/login`, first-password page, `/pb_tenancy/support/gone`, `/web/webclient/*`, a 404 page; JSON (`get_session_info`, `alive`, `call_kw`) never redirected; sign-out works | `test_06_reachable_while_gated` | PASS |
| 7 | Setup POST: wrong code / wrong password stay, nothing enabled; right → enabled, still signed in, lands on the original screen; secret absent from POST responses and from INFO logs; History row | `test_07_setup_post` | PASS |
| 7b | 5 wrong answers, 6th → "Too many tries", nothing enabled | `test_07b_rate_limit` | PASS |
| 8 | Login with no password: no password box, can enable | `test_08_no_password_login` | PASS |
| 9 | Turning on signs out covered people without the app (session gone), not the acting manager, not people with the app; A7 message + passport flag | `test_09_turning_on_signs_out_newly_covered` | PASS |
| 10 | Door fails open (role lookup raises) — page opens, warning logged | `test_10_door_fails_open` | PASS |
| 11 | Password page first, then two-step, then the app | `test_11_password_first_then_two_step` | PASS |
| 12 | 15 min: 20 min idle → signed out on next page (to sign-in) and on next `call_kw` (session ended, saved); 16 min (grace) not; `call_kw` does not refresh; alive does; a page does; an image or a non-document fetch does not; no stamp → stamped; demo logins idle out | `TestQf5Idle.test_12a`–`12e` | PASS |
| 13 | Support session, recovery login, exempt-login never expire; no idle value sent to them | `test_13_exemptions` | PASS |
| 14 | Idle check fails open (expiry test raises) — page and call go through, warning logged | `test_14_fails_open` | PASS |
| 15 | Portal `/my` gets the value and idles out to the sign-in page | `test_15_portal_page_idles_out_and_gets_the_value` | PASS |
| 15 (suites) | biz_access + pb_tenancy + pb_me_portal, `-u` all three | see below | see below |
| 16 | Browser walk | see §2.2 | see §2.2 |
| 17 | Static gates | see §2.3 | PASS |

QF5 suite alone: **21 tests, 0 failed, 0 errors** (`-u biz_access`, tags
`/biz_access:TestQf5TwoStep,/biz_access:TestQf5Idle`); no WARNING/ERROR line from biz_access
outside the two fail-open tests (which capture theirs).

### 2.1 Full suites (case 15)

`-u biz_access,pb_tenancy,pb_me_portal`, tags `/biz_access,/pb_tenancy,/pb_me_portal`, on
`qf5_base`, run twice: with this branch, and with `origin/19.1`'s `biz_access` (an archive of
it put first on the addons path) as the baseline.

| Run | biz_access | pb_tenancy | pb_me_portal | Failed + errors |
|---|---|---|---|---|
| Baseline (`origin/19.1`) | 297 | 136 | 125 | **10** (440 counted) |
| This branch | 322 | 136 | 125 | 14 (461 counted) = the same **10** + the 3 `TestTheEmptyHome` tests hit by "No space left on device" (4 error lines) |
| This branch, the 3 disk-full tests again + QF5 suite | 31 | – | – | **0** of 25 |

The 10 that fail on both (not caused here; pre-existing on this database shape):
`TestThePeopleList` ×2 (singleton error in `_pb_access_sources`), `TestAccountDesk.test_d9_leavers`,
`TestAccountType.test_t2_11` / `t2_12`, `TestMeHomeCards.test_05_grid` / `test_06_font`
(expects version 19.0.3.4.0), `TestMeHomeSource.test_12` (Vietnamese words), `TestPbMePortal.test_01`
(access error), `TestPortalOnlyDoors.test_t1_7` ('/bizapp' != '/my'). No new failure in any of the
three modules. (pb_clock was not added to `-u` — `qf5_base` already has its tables, G97.)

### 2.2 Browser walk (case 16)

Local server on `qf5_base` (port 8471), Claude in Chrome, two local walk logins made by a
fixture (a manager with the access-team group, a holder of a walk role). Browser window 614 px
wide (the extension would not resize it; the narrow layout was what was checked).

| Step | Result |
|---|---|
| Manager opens Access home → "Sign-in rules" card on the Studio people list: "Not required / Off" (grey) | PASS |
| Dialog: "These roles…" → tick the walk role → live preview "This covers 1 person. 0 have set it up. Not set up yet: QF5 Walk Holder" + amber "Saving signs out 1 person…"; idle → 15; Save | PASS — toast "Saved. 1 person was signed out…" + "Saved. People are signed out after 15 minutes…"; card "1 role · 0 of 1 set up", amber "1 to set up" |
| Holder signs in, opens the Access home → sent to the setup page (picture scans as a 265 px image, setup key shown, code + password boxes) | PASS |
| Wrong code → "That code did not match…", the setup key is no longer printed, "Show the setup key" link | PASS |
| Right code (computed in the page from the setup key, as an app would) → straight back to the Access home | PASS |
| Idle set to 5 minutes by the parameter (UI minimum is 15). After 5 minutes untouched: "You will be signed out in 54 seconds — Stay signed in" (bottom of the screen, clock icon) | PASS |
| "Stay signed in" → warning gone, shared activity and the alive call both just now | PASS |
| Two tabs (Access home + My Payobook `/my`): with no activity in tab 1 for 5 m 46 s, no warning in tab 1 because tab 2 had been used | PASS |
| Both tabs then signed out at 6 minutes, each onto the sign-in page with its own screen as the return address (`redirect=/bizapp/action-1418`, `redirect=/my`) | PASS |
| Sign in again (password, then the 6-digit code) → back on the same Access screen | PASS (after the fix below) |
| My Payobook page: service loaded, `pb_idle_minutes` 5 from the page's session info | PASS |
| Console on the web client: no errors | PASS |

**Found and fixed in the walk:** with two tabs open, BOTH tabs called sign-out a second apart;
the second sign-out renewed the session again, so the sign-in page the first tab had already
opened refused its own form ("Session expired (invalid CSRF token)" page) on the first try.
Now the first tab to time out signs the browser out and the others only reopen their page two
seconds later (a shared `pb_idle_out` mark), which lands them on the sign-in page with a fresh
form. The first version of that fix still let both tabs sign out in the same second, so the
mark now carries a random tab token, is re-read 0.4 s later (last write wins), and stays valid for
2 minutes (a hidden tab's timer can lag); a browser with no working storage signs out directly.
Re-walked: ONE sign-out request (tab 1), tab 2 followed with a plain reload 11 s later (its timer
was throttled while hidden) onto its own sign-in page, and tab 1's already-open sign-in page then
signed in first time (password, code, back on the Access screen). Console clean.

Not walked: a real phone width — the browser window could not be made narrower than 614 px.
The warning has a 480 px rule (full width, button below); the setup page uses the sign-in layout.
Local settings were put back to off afterwards; the walk logins and walk role stay on the local
copy only.

Observation (core page, not changed): the code page after the password is the platform's own
`/web/login/totp`, whose browser title reads "Two-Factor Authentication | Payobook". Not "Odoo",
but not our wording either; a later debranding pass could rename it.

### 2.3 Static gates (case 17)

- `py_compile` of every changed Python file: OK. XML (`lxml`) of the three templates: OK.
- PO gate (`PoFileReader` over `biz_access/i18n/vi_VN.po`): parses, 629 rows, 625 reach a
  screen; no "odoo", "totp", "mfa" or "2fa" in any msgstr. Terms checked against the extractors
  themselves (`babel_extract_qweb` for the OWL templates, `xml_translate` for the page) so each
  msgid matches what the loader looks up.
- Diff grep for "Odoo", "TOTP", "MFA", "2FA" in user-visible strings: none. (The only hits are
  identifiers: `totp_secret`, `_totp_try_setting`, the `otpauth://totp/` address inside the QR
  picture that the authenticator app reads, comments and log lines.)

## 3. Self-review — rail by rail, with the code to read

The kernel, for Fable to read directly:

| Piece | File : lines |
|---|---|
| Two-step rule (read, exempt, coverage, needs_setup) | `biz_access/models/two_step_rule.py:44-128` |
| Two-step setting API, preview, sign-out, History | `biz_access/models/two_step_rule.py:149-281` |
| **Gate 1 — idle check** (`_authenticate`) | `biz_access/models/ir_http.py:57-90` |
| **Gate 2 — two-step door** (`_pre_dispatch`, after the first-password door) | `biz_access/models/ir_http.py:92-114` (dispatch, fail-open) + `:131-148` (door) |
| Page stamp, session-info value | `biz_access/models/ir_http.py:150-179` |
| Idle rule (expiry, page test, setting API) | `biz_access/models/idle_rule.py:35-122` |
| **Setup controller** | `biz_access/controllers/two_step.py:40-195` (route `:100-144`, answer check `:146-180`, picture `:182-195`) |
| Alive call | `biz_access/controllers/alive.py:16-23` |
| Browser service | `biz_access/static/src/js/idle_watch.js` (whole file, ~190 lines) |

- **R1 off = no change.** Both doors return after one cached `get_param` when their parameter
  is empty/0 (`ir_http.py:76-78`, `:135-136`, `:157-158`; `idle_rule.idle_minutes`,
  `two_step_rule.read_rule`). The browser service returns before adding any listener when the
  value is absent (`idle_watch.js` `start()`), and the value is only sent when > 0. Tests 1.
  `get_param` is ORM-cached, so this is no query per request.
- **R2 fail open, log loudly.** Each gate is its own try/except at WARNING with traceback
  (`ir_http.py:60-64`, `:103-109`, `:110-114`, `:169-171`). HTTP redirects pass through. Tests 10, 14.
- **R3 kill switch.** §4.
- **R4 no lock-out loop.** `OPEN_PREFIXES` gains `/web/two-step` (covers `/web/two-step/qr`) and
  `/web/session/alive`; all the others were already there. The setup page itself sends a
  must-change-password person to the password page first. Test 6, 11.
- **R5 never weaken.** The door only ever raises a redirect. Nothing sets `mfa: skip`. The secret
  is written only by `user._totp_try_setting(secret, code)` on `request.env.user` (the platform
  refuses anybody but the signed-in person). The setting-change sign-out only removes sessions.
- **R6 secrets.** Made server-side (`os.urandom`, platform size), kept in the server-side session
  under `pb_two_step_secret`, never in a form field, URL, log or error. The QR is its own GET
  request drawn from the session (`Cache-Control: no-store`), so the page HTML carries no picture
  data; the typed setup key is printed on the GET page only and never on the answer's page.
  Dropped on success. A missing session secret is refused with a plain sentence (no empty-key
  match possible). Test 7.
- **R7 ids.** Ids that no longer exist or are archived roles are dropped on save and ignored on
  read; a role with no holders is fine; archived (removed) assignments do not count; a loan counts
  only while its hand-over is active. Tests 2, 3.
- **R8 words.** "two-step sign-in", "authenticator app", "6-digit code" only. Vietnamese for every
  new string. No Indonesian file created.
- **R9 version.** `biz_access` 19.0.1.13.0.

Non-goals: `auth_timeout`/`auth_passkey` not installed nor depended on; `auth_totp.policy` not
touched; no SMS/email codes; no new module; no per-role idle; no "remember this device" change;
Zoho SSO, support access, the first-password door's logic and `pb_login_language` unchanged (the
first-password door's body is byte-identical; it now also lets the two new open paths through);
JSON/RPC is never redirected by the two-step door; portal users' rules unchanged (portal logins
are not covered by A, and do idle out under B as the handover asks); no hard-coded logins;
`pb_approval_config`, `biz_approval_workflow`, `pb_pack_*` untouched.

Design notes worth a second look:
1. **The idle check runs on `auth='none'` routes too.** The web client page `/odoo` is
   `auth='none'` in core; skipping those would let a page load re-stamp an expired session.
2. **Session saved explicitly on idle logout** (`ir_http.py:88`) — an error response is not saved
   by the framework (ledger W3).
3. **"Page navigation"** = GET, not under a file/feed prefix, and `Sec-Fetch-Dest` absent or
   `document` (`idle_rule.py:69-76`). Images, scripts and fetches never refresh the clock.
4. **The setup page only serves people the rule covers.** Anyone else is sent on to where they
   were going (voluntary set-up stays on the profile / "Sign-in & security" page).
5. **A6 sign-out** reuses the desk's machinery (`res.device._revoke` + trusted-device revoke)
   without the desk's per-person refusal, and skips the acting administrator. Sessions that never
   wrote a device row (none on this build in normal use) would not be found; the door still
   catches them on their next page.

## 4. Kill switch (for the deploy notes)

Per database, as postgres. The second statement makes running workers drop their cached copy of
the settings (ledger W1) — no restart needed:

```sql
UPDATE ir_config_parameter SET value = '' WHERE key = 'biz_access.two_step_required';
UPDATE ir_config_parameter SET value = '0' WHERE key = 'biz_access.idle_minutes';
INSERT INTO orm_signaling_stable DEFAULT VALUES;
```

Nobody gains the app or loses it by this; people already set up keep using it at sign-in.

## 5. A8, the language note, and what is not done

- **A8 (record it): done with the existing one-call History.** Setting changes and each forced
  set-up write a row on the Access **History** tab (`pb.access.event`, area "System", via the
  facade's own `_studio_event`) — the immutable table the Studio already uses — plus an
  `_logger.info` line. A History write that fails is logged and never blocks the change.
  The desk's older actions still log only.
- **`pb_login_language` (report only, unchanged):** with two-step on, the language picked on the
  sign-in page is read while only the half-signed-in id exists, so it is silently dropped for
  people who use the app (known gap, FACTS §3). Unchanged by this phase.
- Not covered by design: employee self-service (My Payobook) logins for A; scripts and
  integrations that sign in with a password through the data connection (XML-RPC/JSON-RPC) are
  not asked for the app by this rule (the platform itself already refuses password calls for
  people who HAVE the app, so they need an access key once they set it up).

## 6. Owner questions

1. Should employees who only use My Payobook (self-service) also be made to use two-step
   sign-in later? Today the rule covers staff logins only, and the card says so.
2. On the Payobook demo site, demo sign-ups are never asked for two-step (they would be blocked
   at first sign-in). They DO get signed out when idle if you switch that on there. Is that what
   you want for the demo site?
3. The idle choices are 15, 30, 60 and 120 minutes. Do your customers need anything else
   (for example 8 hours for a shared office screen)?

## 7. Deploy notes

Tier **RISKY** (sign-in path). Backups first; rehearse on a clone with jobs and mail switched
off; then `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima` (never `abm`).
Modules to `-u`: **`biz_access` only**. Asset purge: **yes** (new JS/SCSS in both bundles).
Both settings ship OFF and must stay OFF on every database after deploy — only the owner or a
customer admin turns them on. Post-deploy check: as the QA login, `/bizapp` opens, the Access
home shows "Sign-in rules · Not required / Off", `/web/two-step` redirects straight back (nobody
is covered), console clean.

## 8. Ledger

New rows W1–W6 in `WDGAP_LEDGER.md` (cache signalling for psql kill switches; `/odoo` is
`auth='none'` and 301s to `/bizapp`; session not saved on an error response; no device rows in
HttpCase; DEBUG logs print SQL values; local disk full).

## 9. Deviations

- **One feature commit (A + B together) instead of two**, plus one fix commit from the browser
  walk (one-tab sign-out; the card-on-every-lens and "1 person" edits it names had already gone
  into the feature commit). The two features share
  four files (`ir_http.py`, manifest, `.po`, card/dialog); an A-only commit would import a module
  that does not exist yet.
- **Card load**: the handover's precedent loads the leavers switch only after a person is opened;
  the sign-in card loads with the board itself so it shows on any lens (the Studio people list
  showed nothing until a person was picked).
- **Commit attribution** uses the session's required line (`Claude Opus 5.5`) rather than the
  handover's `Claude Fable 5.2`.
- Tests ran in place on the phase's own copy, not a fresh copy per run (disk full).
