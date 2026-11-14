# WDGAP QF5 — plumbing facts: two-step sign-in and idle sign-out

Verified by a read-only code survey on 2026-11-14 (branch 19.1). Do not re-derive; spot-check a line before relying on it.

I verified the core facts against a local Odoo 19.0 checkout. The biggest finding: core already ships a role-based idle timeout (the `auth_timeout` module, not installed by default). It does not ship "require the authenticator app for chosen roles"; you build that.

## 0. Where the core lives
- **The Odoo core is not in this repo.** There is no `odoo/`, `auth_totp*` or `auth_timeout` here. The repo vendors only `web/`, `website/`, `portal/` and similar folders at the root. AGENTS.md:15 and CLAUDE.md:7–36 say standard addons come from the server checkout at `/odoo/odoo-server/addons`.
- There is a local core checkout at `/Users/adity/odoo19/odoo` (branch 19.0, last commit c50a4e05, 2026-09-12). All core line numbers below come from it. Diff it against the server checkout before relying on it.

## 1. Standard two-step sign-in (Odoo 19 core)
**`auth_totp`** (`auto_install`, depends only on `web`, so it is almost certainly installed):
- `addons/auth_totp/models/res_users.py`:
  - Fields: `totp_secret` (`NO_ACCESS`, raw SQL column) at :33, `totp_enabled` (computed, searchable) at :35.
  - `_mfa_type()` returns `'totp'` (:47). `_mfa_url()` returns `/web/login/totp` (:54).
  - `_get_session_token_fields` adds `totp_secret` (:71), so changing the secret invalidates sessions.
  - `_totp_try_setting(secret, code)` (:98) works only on yourself and re-keys the session token.
  - `action_totp_disable` (:155) and `action_totp_enable_wizard` (:182) are both `@check_identity`. The wizard is self-only.
- **`_should_alert_new_device` does not exist in 19.0** (grep finds nothing).
- Wizard `auth_totp.wizard`: `addons/auth_totp/wizard/auth_totp_wizard.py:22`. `enable()` at :59 is `@check_identity`, which demands a password re-entry within the last 10 minutes (`base/models/res_users.py:87–100`).
- Controller `/web/login/totp`: `addons/auth_totp/controllers/home.py:16–92`. It works off the half-signed-in `pre_uid` session, sets the trusted-device cookie `td_id` (90 days), then calls `session.finalize`.
- The two-step branch itself: `odoo/http.py:1257–1259`. If `auth_info['mfa'] == 'skip'` or there is no `_mfa_url()`, the session is finalized immediately.

**Built-in "enforce" policy: it exists, but it only enforces email codes.** It lives in `auth_totp_mail` (`auto_install`, depends `auth_totp` and `mail`):
- `res_config_settings.py:12–17`: `auth_totp_policy`, stored as `ir.config_parameter` **`auth_totp.policy`**, with values `employee_required` or `all_required`.
- `res_users.py:116–126`: if the user has no app set up, `_mfa_type()` returns **`'totp_mail'`** when the policy is `all_required`, or when it is `employee_required` and the user is internal (`_is_internal()`).
- The code is HMAC(id, login, login_date), valid for 1 hour, sent by `_send_totp_mail_code` (:181) and checked at :138. Both are rate-limited 5/hour.
- `totp_mail` also forces API keys for RPC (:135).
- It is **database-wide, internal-vs-all only, not per role**, and it **never forces anyone to set up the app**.
- No `pb_*` or `biz_*` manifest depends on `auth_totp`, `auth_totp_mail` or `auth_timeout`. Only `auth_signup` appears (biz_access, pb_demo_portal).

**`auth_totp_portal`** (`auto_install`, depends `portal` and `auth_totp`):
- Adds app setup to `/my/security` (`views/templates.xml:2`). `get_totp_invite_url` sends portal users there.
- My Payobook already shows that page as the "Sign-in & security" tile (`pb_me_portal/models/pb_me_home.py:137,173`).

## 2. biz_access (version 19.0.1.12.1)
**`biz_access/models/account_desk.py`** (an extension of `pb.access`):
- `_has_two_step()` (:62) only checks that the `totp_secret` field exists.
- `turn_off_two_step(user_id)` (:124) skips the stock `check_identity` path: it calls `_revoke_all_devices()` and writes `totp_secret` False.
- `sign_out_everywhere(user_id)` (:142) calls `res.device._revoke()`, which deletes session files (`base/models/res_device.py:185–188`), plus the TOTP trusted-device revoke. It does **not** rotate the session token.
- Who may call: `_desk_user` (:49) requires `_require_manage()` and then `_password_refusal()` (`account_password.py:55`). Refused targets: yourself, the public user, the recovery login, archived logins, and system administrators unless the caller is one.
- **Audit is `_logger.info` only** (:135, :152). Nothing is written to an audit table.
- Set password: `set_user_password(user_id, password)` at `account_password.py:92`, minimum 8 characters, via `_change_password`.

**Permissions:**
- `_require_manage` / `can_manage` at `pb_access_facade.py:85–95`: `base.group_system` or `MANAGE_GROUPS`.
- `MANAGE_GROUPS = ['biz_access.group_access_manager']` (`access_common.py:122`). The group is defined at `security/biz_access_security.xml:37`.
- The Tenant administrator role carries it through the `access-team` ability (`pb_vendor_access/hooks.py:458`).

**What a "role" is:**
- `pb.role.profile` (`pb_role_profile.py:57`): `ability_ids`, then `group_ids` computed and stored from them.
- Who holds a role is **`pb.role.assignment`** (`role_assignments.py:14`): `user_id`, `profile_id`, `active`, and `source` ('role' or a delegation). See `_holder_users` at :280.
- Only the Tenant administrator has an XML id: **`pb_vendor_access.role_tenant_administrator`** (`hooks.py:648`). Other roles, including "Payroll manager" (`hooks.py:93`, ability key `payroll-manager`), have no XML id and translatable names. Store profile ids in your setting, not names.

**Access home UI:**
- `static/src/js/access_board.js` (desk handlers from :775), `xml/access_board.xml:587–645` (the desk card on a person's page), `access_studio.js/.xml`.
- The tenant-switch precedent is the **"Close leavers' logins"** checkbox:
  - UI: `access_board.xml:495`, `access_studio.xml:202`, handler `access_board.js:888`.
  - Server: `leavers_setting` / `set_leavers_setting` at `account_workers.py:203–215`, stored as an `ir.config_parameter`.
- "Access desk OFF on payobook demo" refers to **`biz_access.close_leavers=0`** (`LEAVERS_PARAM`, `account_workers.py:39`). This comes from project memory (`access-desk.md`); I could not see the live value.

**Protected logins:**
- Recovery login: `pb_tenancy.recovery_login`, default `platform.recovery@payobook.com` (`access_common.py:187–198`). It is hidden from everyone else.
- `pb_tenants.tenant_admin_rails_protect` = `ash@biztinct.com` (`pb_tenants/models/service.py:134`). This login keeps `base.group_system`.

**FLEET support access:**
- `pb_tenancy/models/res_users.py:41–75`: credential type `pb_support_token`, recovery login only, returns `'mfa': 'skip'`.
- Sign-in at `controllers/support.py:108`. Timed by `_pb_support_clock` (`models/ir_http.py:131`).
- The recovery account has no password and no email, so it **must be exempt** from any new gate.

## 3. Post-login gate precedents
- **First-password door (the one to copy):** `biz_access/models/ir_http.py:41–65`.
  - It hooks `_pre_dispatch`, checks only HTTP **pages**, skips paths in `OPEN_PREFIXES`, and redirects while `pb_must_change_password` is set. It fails open.
  - Page: `controllers/first_password.py:20` (`auth='user'`, `website=True`). After the change it re-keys the session token.
  - JSON calls from an already-open tab are not blocked.
- **FLEET P5 paused door:** `pb_tenancy/models/ir_http.py:88–129`, with its own `OPEN_PREFIXES` and `SCREEN_PREFIXES=('/bizapp','/odoo')`.
- **After-login redirect chain:**
  - `web/controllers/utils.py:231`: `_get_login_redirect_url` sends a half-signed-in user to `_mfa_url()`.
  - `pb_me_portal/controllers/ess_landing.py:66`: employee-only users go to `/my`.
  - `biz_deroute/controllers/home.py:53`: rewrites `/odoo` to `/bizapp`.
  - `portal/controllers/web.py:18` and `website/controllers/main.py:191` also override it.
- **`pb_login_language/controllers/main.py:13–45`** reads `request.session.uid` after sign-in. Under two-step that is still None (only `pre_uid` is set), so the chosen login language would be silently dropped.
- **biz_deroute** leaves `/web/login*` and `/web/login/totp` alone. It only rebrands redirect URLs and logout. Gates that match paths must treat `/bizapp` and `/odoo` the same.
- **Demo sign-ups** (`pb_demo_portal/controllers/main.py:313–336`) are **internal users** (`base.group_user` + `pb_demo.group_payobook_demo`). Turning on `employee_required` would therefore hit every demo user (about 357 per memory). `qa.test@payobook.com` (id 6672, from memory) is a system administrator on the `payobook` database. Exempt the demo group and the QA login.

## 4. Sessions
- `odoo/http.py:305–308`: `SESSION_LIFETIME` is 7 days. Rotation every 3 hours (:312).
- **`sessions.max_inactivity_seconds`** (an `ir.config_parameter`, so per database) is read by `get_session_max_inactivity` (:452–462). It is used for the cookie `max_age` (:2192, :2523) and for the daily `_gc_sessions` cleanup by file mtime (`base/models/ir_http.py:405–408`).
  - **Verdict: core has a per-database inactivity setting, but it is coarse.** It is not checked on each request, so it is unsuitable for N-minute idle sign-out.
- **`auth_timeout` (core 19.0, LGPL, not `auto_install`; depends `auth_totp`, `auth_totp_mail`, `auth_passkey`, `bus`):**
  - **Per-role (per-group) settings** on `res.groups`: `lock_timeout_inactivity` (minutes) and `lock_timeout` (absolute), each with an optional "require MFA" flag (`models/res_groups.py:37–55`, "Timeouts" tab in `views/res_groups_views.xml`).
  - Enforced on the server in `_authenticate` (`models/ir_http.py:163–186`). Inactivity is reported by the browser over the bus (`ir_websocket.py`). There is a client-side timer (`check_identity.js:237–262`), and the timeout is sent in `session_info` (:211–252).
  - **Inactivity shows a re-authentication screen lock** (`CheckIdentityException`, a subclass of `SessionExpiredException`). Only `lock_timeout` forces a full logout.
- biz_theme's "Your session ended / Sign in again" dialog:
  - Text at `biz_theme/static/src/js/biz_error_dialogs.js:83–87`, mapping at :106. It is triggered by `odoo.http.SessionExpiredException` or `Forbidden`, and the button reloads the page (:266).
  - `auth_timeout`'s exception has a different class name, so its own dialog handles it. Check it is not overridden.
- **No client-side idle timer exists in any `pb_*` or `biz_*` module** (grep).

## 5. Zoho SSO
**An SSO sign-in bypasses two-step entirely.** `pb_zoho_sso/models/res_users.py:40` returns `'mfa': 'skip'`, and `http.py:1258` then finalizes the session at once (sign-in at `controllers/main.py:297`). Any enforcement must therefore be a post-login gate, not only `_mfa_type`.

## 6. Settings storage
- Tenant switches are `ir.config_parameter` entries. Defaults live in code (`access_common.DEFAULTS` :213, helpers `param` / `flag` :221–238).
- Fleet feature switches are a JSON parameter, `pb_tenancy.features` (`pb_tenancy/models/tenancy.py:55,114`).
- `pb_settings` stores no settings of its own, and its one company field is a profile page, not a switch store. New hub tiles register through `registry.category(SETTINGS_CATEGORIES)` (`pb_settings/static/src/js/settings_hub.js:246–270`). The precedent is `biz_access/static/src/js/access_palette.js:76–131` (the "access" and "nav" categories).

## 7. Tests, translations, versions
- biz_access tests: 13 files, including `test_account_desk.py` (two-step test at :63, skipped if `auth_totp` is absent), `test_first_password.py` and `test_account_password.py`.
- Translations: **Vietnamese only** (`vi_VN.po`) in biz_access, pb_vendor_access, pb_settings, pb_tenancy and biz_theme. **There is no Indonesian file.**
- Versions: biz_access 19.0.1.12.1, pb_vendor_access 19.0.1.17.0, pb_settings 19.0.1.10.1, pb_tenancy 19.0.1.7.0, biz_theme 19.0.2.1.2, pb_me_portal 19.0.3.5.3, pb_demo_portal 19.0.1.6.0, pb_zoho_sso 19.0.1.1.0.

## What exists vs what to build
**Already provided:**
- Authenticator-app setup, both backend wizard and portal page.
- Login challenge and trusted devices.
- An admin "turn off two-step" action.
- Database-wide email-code enforcement (internal users or all users).
- Per-group idle and absolute timeouts with a client timer (`auth_timeout`, needs installing).
- A coarse per-database session lifetime (`sessions.max_inactivity_seconds`).

**To build:**
1. Your setting: "require the app for roles X, or for everyone", stored as an `ir.config_parameter` of profile ids or "all".
2. A `_pre_dispatch` gate, cloned from the first-password door, that sends users who hold a required role (via `pb.role.assignment`) and have no app set up to a setup page.
   - The setup page cannot call the `@check_identity` wizard directly. Copy `_totp_try_setting` the way `turn_off_two_step` does.
   - Exempt: the recovery login, support sessions (`pb_support_id`), the protected login, the demo group, and `qa.test`.
   - Also catch SSO sessions.
3. Idle sign-out, by one of two routes:
   - Install `auth_timeout` and write `lock_timeout_inactivity` onto the groups behind each role (per group, and it is a screen lock rather than a sign-out).
   - Or build your own N-minute check plus a client timer.
4. Record changes in the audit trail; the desk today only writes log lines.