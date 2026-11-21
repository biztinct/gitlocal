# WDGAP QF5 — Compulsory two-step sign-in by role; sign-out when idle

Read first: `WDGAP_LEDGER.md`, then `WDGAP_QF5_FACTS.md` (verified plumbing, file:line —
do not re-derive; core line numbers are from the local checkout `/Users/adity/odoo19/odoo`,
branch 19.0 — spot-check), then `docs/handovers/ACCESS_CLOSEOUT.md` and
`docs/handovers/updates/UPDATES_LEDGER.md` G54 (recovery login), G94–G99.

You are the implementer AND tester/self-reviewer. You do NOT deploy. This is a SECURITY
phase on the sign-in path of five live customer databases: a bug here either locks people
out or silently does nothing. Fable will read the gate code itself before deploy — keep
the kernel small, in ONE file per feature, with no cleverness.

Everything ships OFF. With both settings at their defaults nothing changes for anybody.

## 1. Scope

### A. "Two-step sign-in is required for…"
A1. **Setting** on the Access home, beside "Close leavers' logins"
    (`biz_access/static/src/xml/access_board.xml:495`, `access_studio.xml:202`; server
    precedent `leavers_setting`/`set_leavers_setting`, `account_workers.py:203-215`):
    "Two-step sign-in is required for": `Nobody` (default) / `These roles…` (tick list of
    `pb.role.profile`) / `Every staff login`. Stored as `ir.config_parameter`
    `biz_access.two_step_required` = `''` | `all` | comma-separated profile ids. Only
    `_require_manage()` may change it. The card shows a live count: "7 of 12 people this
    covers have set it up", and lists who has not.
A2. **Who it covers**: active INTERNAL logins (`_is_internal()`) that hold a required role
    through an active `pb.role.assignment` (any `source`, so a lent role counts while it
    is lent), or every internal login for `all`. Employee self-service (portal) logins are
    NOT covered in this phase — say so on the card ("My Payobook logins are not included yet").
A3. **Exempt, always** (one function `_two_step_exempt(user, session)`):
    the public user; the recovery/support login (`access_common.py:187-198`) and any
    support session (`pb_support_id` in session, `pb_tenancy`); members of the demo group
    `pb_demo.group_payobook_demo` when that group exists (probe by xmlid, no dependency);
    logins listed in `ir.config_parameter` `biz_access.two_step_exempt_logins`
    (comma-separated, platform-only, no UI).
A4. **The door**: a `_pre_dispatch` gate cloned from the first-password door
    (`biz_access/models/ir_http.py:41-65`): HTTP pages only, skip `OPEN_PREFIXES` plus the
    setup route, static and logout; when the signed-in user is covered, not exempt and has
    no authenticator app (`totp_enabled` false) → redirect to `/web/two-step` (treat
    `/bizapp` and `/odoo` alike). It runs AFTER the first-password door (password first).
    It **fails open**: any exception → log and let the request through.
    This also catches Zoho SSO sessions (which skip the code challenge, FACTS §5) — they
    are asked to set the app up once like everyone else.
A5. **The setup page** `/web/two-step` (`auth='user'`, `website=True`, clone
    `controllers/first_password.py:20` for layout and branding): plain explanation, QR
    code + the secret as text, a 6-digit code box, and the person's current password when
    their login has one (check `password` is set with one SQL as the first-password code
    does; SSO-only logins have none → no password box). On submit: verify the password
    with `_check_credentials` (password type), then enable with the platform's own
    `_totp_try_setting(secret, code)` (self-only; it re-keys the session token — follow
    what `first_password.py` does after its change so the person stays signed in). The
    secret is generated server-side, kept in the session between GET and POST (never in a
    hidden form field that could be replaced), and discarded on success. Wrong code /
    wrong password → same page, plain sentence, rate-limited (5 tries then a 60-second
    wait, counted in the session). Success → continue to where they were going.
A6. **Turning the rule on signs out the people it newly covers who have no app yet**
    (`sign_out_everywhere` machinery, `account_desk.py:142`), never the administrator who
    is changing the setting — so no already-open tab keeps working without two-step. The
    confirm dialog says how many people will be signed out.
A7. **Turn off two-step for someone** (existing desk action) on a covered person: the
    confirm text gains "They will be asked to set it up again the next time they sign in."
A8. **Record it**: setting changes, and each forced setup completed, are written where
    the Access desk's other actions should be auditable. If `biz_audit_trail`/`pb_audit`
    offers a one-call way to add an entry, use it; if not, `_logger.info` like the desk
    does today and say so in the report (do not build an audit table here).

### B. "Sign people out after … minutes without activity"
B1. **Setting** on the same card: Off (default) / 15 / 30 / 60 / 120 minutes, stored as
    `ir.config_parameter` `biz_access.idle_minutes` (integer, 0 = off; refuse 1–4).
B2. **Activity is what the person does, not what the page does in the background.**
    A small browser service (web client `web.assets_backend` AND portal
    `web.assets_frontend`) records the last pointer/keyboard/touch time in `localStorage`
    (shared by all tabs, throttled to once every 15 s), and while the person is active
    tells the server at most once a minute (`POST /web/session/alive`, JSON, `auth='user'`,
    tiny). When `now − last activity ≥ idle minutes` in EVERY tab (read the shared
    `localStorage` value), it shows a calm one-minute warning ("You will be signed out in
    60 seconds — Stay signed in") and then goes to `/web/session/logout?redirect=<here>`.
B3. **Server backstop** (so a closed laptop or a script cannot keep a session forever):
    the session stores `pb_last_active` (epoch). It is refreshed ONLY by the alive call
    and by a full page navigation that passes the gate — never by background JSON/RPC or
    the websocket. In `_pre_dispatch` (pages) and in the JSON dispatch path used by
    `/web/dataset/*` (find the narrowest hook; `_authenticate` in `ir.http` is the
    precedent used by core `auth_timeout`, FACTS §4): if idle minutes > 0 and
    `now − pb_last_active > idle minutes + 2 minutes grace` → `request.session.logout()`
    and let the standard "session ended" path run (biz_theme's dialog, FACTS §4). A
    session with no `pb_last_active` yet is stamped, not expired. Fails open.
B4. Exempt: support sessions and the recovery login (same function as A3 minus the demo
    group — demo logins DO idle out when a database turns it on).
B5. The setting value reaches the browser through `session_info` (backend) and a data
    attribute or tiny inline-free config on portal pages (CSP: no inline script/style —
    ledger G95); 0/absent → the service does nothing at all (no listeners).

## 2. Binding non-goals

- Do NOT install or depend on `auth_timeout`, `auth_passkey`, or change the
  `auth_totp.policy` email-code setting. No SMS/email codes. No new module.
- No per-role idle times. No "remember this device" changes. No change to the Zoho SSO
  flow, the support-access flow, the first-password door, or `pb_login_language`
  (its known gap under two-step, FACTS §3, is a report item only).
- Do not gate JSON/RPC for two-step (A6 handles open tabs). Do not touch portal users' rules.
- No hard-coded login names or emails anywhere.
- Do not edit `pb_approval_config`, `biz_approval_workflow`, `pb_pack_*`.

## 3. Safety rails

R1. **Default off, and off means zero behaviour change**: with both parameters empty/0
    the gates return before doing any query beyond one cached parameter read. Use the
    existing `param`/`flag` helpers (`access_common.py:221-238`); cache per request.
R2. **Fail open, log loudly** in both gates; a broken gate must never take a database down.
R3. **Kill switch**: blanking the two parameters (psql) switches everything off with no
    restart. State the exact SQL in the report for the deploy notes.
R4. **No lock-out loop**: the setup page, its POST, static assets, `/web/login*`,
    `/web/session/logout`, `/web/session/alive`, the first-password page, the support
    sign-in routes and website breakdown pages are all reachable while gated. Test each.
R5. **Never weaken**: the gate only ever ADDS a redirect; it never marks anybody as
    having two-step, never sets `mfa: skip`, never writes `totp_secret` except through
    `_totp_try_setting` on the signed-in user themself.
R6. **Secrets**: the pending secret lives only in the server-side session; never logged,
    never in a URL, never in an error message. QR rendered as the platform does it.
R7. Role ids in the parameter that no longer exist are ignored; a required role with no
    holders is fine. Archived assignments do not count.
R8. White-label and plain words (no "TOTP", "MFA", "2FA" on screen — "two-step sign-in",
    "authenticator app", "6-digit code"). Vietnamese entries for every new string in
    `biz_access/i18n/vi_VN.po` (no Indonesian file exists — do not create one). PO gate.
R9. Version-bump `biz_access` (and any other module touched).

## 4. Architecture — exact seams

- `biz_access/models/two_step_rule.py` (new, the whole kernel for A): parameter read,
  `_two_step_required_for(user)`, `_two_step_exempt`, `two_step_setting()` /
  `set_two_step_setting(mode, profile_ids)` on `pb.access` (facade, `_require_manage`),
  coverage counts, sign-out of newly covered people.
- `biz_access/models/ir_http.py`: call the two gates from `_pre_dispatch` after the
  first-password door; add to `OPEN_PREFIXES`; `session_info` gains `pb_idle_minutes`.
- `biz_access/controllers/two_step.py` (new): GET/POST `/web/two-step`.
  `biz_access/views/two_step_templates.xml` (new): the page.
- `biz_access/models/idle_rule.py` (new, the whole kernel for B) +
  `biz_access/controllers/alive.py` + `biz_access/static/src/js/idle_watch.js` (one file
  used by both bundles; plain JS service for backend, frontend interaction for portal).
- `biz_access/static/src/xml/access_board.xml` / `access_studio.xml` + js handlers
  (`access_board.js:888` precedent): the card.
- `biz_access/models/account_desk.py:124`: A7 text only.

## 5. Numbered test cases (T = Odoo test, HttpCase where a redirect is asserted; write and run)

`biz_access/tests/test_wdgap_qf5_two_step.py`, `test_wdgap_qf5_idle.py`, tagged.
Skip cleanly when `auth_totp` is absent (precedent `test_account_desk.py:63`).

1. T Defaults: both parameters unset → a role holder with no app reaches the app; no
   redirect; `session_info` has no idle value (or 0).
2. T Setting API: non-manager refused; manager can set Nobody / roles / all; bad ids
   dropped; refuses idle 1–4.
3. T Roles mode: holder of a required role without the app → redirected to `/web/two-step`
   from `/odoo`, `/bizapp` and `/my`; a non-holder is not; a holder WITH the app is not;
   a holder through a lent (delegated) role is; an archived assignment is not.
4. T `all` mode covers every internal login, not a portal login.
5. T Exemptions: recovery login, a support session, a demo-group member, a login in the
   exempt parameter → never redirected.
6. T Reachability while gated (R4): each listed route returns its own page/200, not a
   redirect loop; JSON calls are not redirected.
7. T Setup POST: right password + right code → `totp_enabled` true, still signed in,
   lands on the original target; wrong code → stays, nothing enabled; wrong password →
   stays; 6th quick attempt → wait message; secret never appears in the response of the
   POST or in logs (assert on captured log output).
8. T A login with no password (SSO-only shape) sees no password box and can enable.
9. T Turning the rule on signs out covered people without the app (their session becomes
   invalid) and not the acting administrator; people with the app keep their session.
10. T Gate fails open: patch the role lookup to raise → request proceeds, error logged.
11. T Order: a user who must change password AND set up two-step sees the password page
    first, then two-step, then the app.
12. T Idle: with 15 minutes set, a session whose `pb_last_active` is 20 minutes old is
    logged out on the next page and on the next `/web/dataset/call_kw`; 16 minutes old
    (inside grace) is not; background RPC does not refresh the stamp; the alive call
    does; a page navigation does; no stamp yet → stamped, not expired.
13. T Idle exemptions: support session and recovery login never expire by this rule.
14. T Idle gate fails open (patch to raise).
15. T Existing `biz_access` suites all green (13 files), plus `pb_tenancy` and
    `pb_me_portal` suites (they share the dispatch path): `-u` each (ledger G35).
16. Browser, local copy (Claude in Chrome per G99): turn on for one role → sign in as a
    holder → setup page (use an authenticator code computed in a script from the secret
    shown) → in; idle set to 5 minutes via the parameter for the walk (the UI minimum is
    15): warning appears, "Stay signed in" works, second time it signs out and returns
    to the same screen after sign-in; two tabs — activity in one keeps the other alive;
    portal `/my` page idles out too; console clean; phone width.
17. Static gates: py_compile, XML, PO gate, grep the diff for "Odoo", "TOTP", "MFA", "2FA"
    in user-visible strings (none).

## 6. Working rules

- NEW git worktree from `origin/19.1`, branch `wdgap-qf5`. Local test recipe: latest
  UPDATES reports + ledger G12, G19, G35, G97.
- Two feature-scoped commits (A, B), explicit paths; push `wdgap-qf5`. Do NOT merge. Do
  NOT deploy. Do not change any parameter on any live database.
- Commit messages end with: `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
- Usage-limit error → one WIP commit, "Where I stopped" in the report, end with PAUSED.

## 7. Report back — `docs/handovers/wdgap/WDGAP_QF5_REPORT.md` (commit it)

1. What was built; files; version bumps. 2. Test table + full-suite counts.
3. Self-review rail by rail (R1–R9) and non-goal by non-goal, with the file:line of each
   gate so Fable can read the kernel directly (list the exact files and line ranges).
4. The kill-switch SQL. 5. A8 outcome; the `pb_login_language` note; anything not done.
6. Owner questions as plain real-world questions.
7. Deploy notes: tier RISKY (sign-in path): backups, rehearsal on a clone, modules to
   `-u`, asset purge yes; both settings stay OFF on every database after deploy — only
   the owner or a customer admin turns them on.
8. New gotchas → rows in `WDGAP_LEDGER.md`.

Final message to the orchestrator: under 250 words — branch, last commit, test counts,
failures or deviations, kernel file:line ranges, owner questions.
