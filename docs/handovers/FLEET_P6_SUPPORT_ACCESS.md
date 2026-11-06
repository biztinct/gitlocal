# FLEET P6 — Support access with a trail

Program doc: `docs/handovers/FLEET_PROGRAM.md` (READ FIRST, incl. ledger). Stands on P2A
(`pb_tenancy`, `push_tenancy`, state poll), P3 (`pb.alert`), P5 (paused door exempts the
recovery account). Gap 10 from `docs/SAAS_RELEASE_STRATEGY.html`.

## What this phase makes true (plain words)

1. From a customer's page in the cockpit, the owner presses **Open as support**, types a reason,
   and is inside that customer's Payobook in a new tab as the platform's recovery account — for a
   fixed time (default 2 hours), after which the session ends by itself.
2. **Every access is written down on the customer's side**: who, when, why, for how long, from
   where — and the customer's administrator can read that log in their own Settings ("Support
   access"), and can **switch support access off** for their company. When it is off, the button on
   the cockpit says so and does nothing else.
3. While a support session is open, the customer's users see nothing; the support user sees a
   thin bar "You are in AB Mauri as Payobook support · ends 16:02 · Leave" on every page (so
   nobody forgets which database they are in — the mistake this bar exists to prevent).
4. No password ever exists for the recovery account, still. Entry is a **one-time token** the apex
   writes into the tenant, valid for 60 seconds, used once.
5. Hero moment: the customer-side **Support access** page — a clean audit trail (date, who,
   reason, duration, what screens were opened) with the big switch at the top. Trust made visible.

## Binding NON-goals

- No impersonation of a specific customer user. Support is always the recovery account (system
  administrator on that database) — that is what "help me with my data" needs.
- No screen recording; "what screens were opened" = the client actions/URLs visited, recorded by
  the tenant-side bar's route listener, nothing more.
- No change to the rails: the recovery account keeps `base.group_system`; the customer admin
  keeps not having it.

## Verified facts

- Recovery account per tenant: `platform.recovery@payobook.com` (param
  `pb_tenants.break_glass_login`), active, `base.group_user + group_system + group_erp_manager`,
  no password, no email (`service.py:792–856`). On abm it exists (rails ran); the template has
  it too (`prepare_template_for_rails`). Verify on both; create via `_ensure_break_glass` if not.
- Login seam (Odoo 19, server copy `odoo/addons/base/models/res_users.py`): `_check_credentials
  (self, credential, env)` :312 — override, call `super`, catch `AccessDenied`, validate your own
  credential type, return `auth_info = {'uid', 'auth_method', 'mfa': 'skip'}`. `authenticate`
  :784 / `_login` :760. HTTP: `odoo/http.py` `Session.authenticate(env, credential)` :1201 stores
  `pre_uid` and calls `finalize` when `mfa == 'skip'` (:1229–1235). A credential is a dict with
  `type` (`'password'` today) and `login`.
- Request seams for the bar/route log: `ir.http.session_info` (P2A already extends it),
  `_pre_dispatch`/`_post_dispatch`.
- Cross-DB push: `push_tenancy` (P2A). The tenant's poll (P2A) refreshes `state()` within 60 s.
- The customer's admin identity: the Tenant administrator role (`pb_vendor_access.role_tenant_
  administrator`) — gate the customer-side page on the `access-team` ability's group (required by
  the role, hooks.py:375) or on `pb.company.profile`'s existing editor gate (`COMPANY_EDITOR` in
  `settings_hub.js:112`); pick the former and say why.
- Sessions in Odoo 19 are filesystem sessions keyed by sid; expiring a session early = the tenant
  side checks `pb.support.session.expires_at` on each request for the recovery uid and logs out
  (`request.session.logout(keep_db=True)`) when past — cheap (one small read per request for that
  one uid only).

## Architecture

### Tenant side (`pb_tenancy`)

- `pb.support.access` (on the tenant): `token_hash` (sha256 of the one-time token; the token
  itself is never stored), `issued_at`, `token_expires_at` (issued + 60 s), `used_at`,
  `session_expires_at`, `ended_at`, `support_name` (who on the platform side — the apex user's
  name), `reason` (required), `source_ip`, `route_log` (Text JSON list of `{ts, action}`), `state`
  (`issued`/`active`/`ended`/`expired`/`refused`). ACL: read for the tenant-admin gate group,
  no create/write for anyone but sudo.
- Param `pb_tenancy.support_allowed` (`1` default; the customer switch writes `0`), pushed BACK to
  the apex? No — the apex READS it before issuing (via `_pg_cursor`, read-only) and shows it.
- `res.users._check_credentials` override: accepts `credential['type'] == 'pb_support_token'`
  when `login` is the recovery login, the hashed token matches an `issued` row whose
  `token_expires_at` is in the future, and `support_allowed` is on → marks the row `active`
  (`used_at`, `session_expires_at = now + duration`), returns `{'uid', 'auth_method':
  'pb_support', 'mfa': 'skip'}`. Any other outcome → `AccessDenied` and the row `refused` with the
  reason (expired token / support off / reuse).
- Controller `GET /pb_tenancy/support/<token>` (auth `none`): builds the credential and calls
  `request.session.authenticate(request.env, credential)`, then redirects to `/odoo` (the
  deroute alias if `biz_deroute` maps it — verify the entry URL that works on abm, e.g. `/bizapp`).
  Failure → a clean page "This support link has expired or was already used" (no stack, no
  "Odoo"). Rate-limit: 5 attempts / minute / IP (in-memory dict is fine on one process; say so).
- `ir.http._pre_dispatch` override: if the session uid is the recovery account and its active
  `pb.support.access` row is past `session_expires_at` or `ended_at` → logout + redirect to the
  "session ended" page. Also appends `{ts, action}` to `route_log` for `/odoo/action-*` and
  `/bizapp/*` navigations (client actions and models only; skip assets/RPC).
- `session_info` adds `support_session: {ends_at, tenant_name}` for the recovery uid only.
- **Support bar** (JS, mounted like the P2A banner, above it): rose-tinted thin bar, "You are in
  <company> as Payobook support · ends 16:02 · Leave" → `Leave` calls `/pb_tenancy/support/leave`
  (ends the row, logs out). Countdown ticks; at 5 minutes left it pulses once.
- **Customer page** `pb_tenancy_support` client action, Settings → About Payobook → "Support
  access": the switch (with a sentence: "When off, Payobook support cannot open your company's
  data, even if you ask us to — switch it on first."), then the trail table (date, who, reason,
  duration, screens opened as chips, state). Empty state: "Payobook support has never accessed
  your company." Gate: the tenant-admin group above.

### Apex side (`pb_tenants`)

- `support_open(tenant_id, reason, minutes=120)` → refuses: decommissioned; `support_allowed`
  off on that tenant (message quotes the customer's switch); missing `pb_tenancy`; empty reason.
  Otherwise: generates `secrets.token_urlsafe(32)`, writes the hashed row on the tenant through
  `_tenant_env` (rail R5), logs a `provision_log` line (`support` step: who/why/how long), creates
  a `pb.alert` info "Support session opened on AB Mauri by <name>" (P3 — so it is in the emailed
  digest, by design: access to customer data is never quiet), and returns the URL
  `https://abm.payobook.com/pb_tenancy/support/<token>` — the cockpit opens it in a new tab
  immediately (the token has 60 s).
- `support_history(tenant_id)` reads the trail (read-only SQL) for the cockpit; `support_end(id)`
  ends a session from the cockpit (writes `ended_at` through `_tenant_env`).
- Tenant detail → Overview: **Open as support** button → dialog: reason (required), duration
  (30 min / 2 h / 8 h segmented), the sentence "This is written on the customer's side and emailed
  in the daily summary." → Open. Below: this customer's last sessions; a rose "Support access is
  switched OFF by the customer" state when applicable, with the button disabled — and nothing
  else (rail: no override, by design; say so on screen).

### Tests

- **T1** Pure `token_check(row, token, now, allowed) -> ('ok'|'expired'|'used'|'off'|'mismatch')`;
  **T2** `_check_credentials` accepts a fresh token once and refuses the second use (tenant-side
  TransactionCase creating the row directly); refuses when `support_allowed` is off; refuses a
  wrong login; **T3** HttpCase: the `/pb_tenancy/support/<token>` route logs in and redirects;
  expired → the clean page; **T4** `_pre_dispatch` ends a session past `session_expires_at` and
  the next request is logged out; **T5** `session_info` carries `support_session` only for the
  recovery uid; **T6** apex `support_open` refusals + the row/alert/log written (capture
  `_tenant_env` with a fake); **T7** the customer page gate: tenant-admin group sees it, a plain
  user does not (`resolve_gates`); **T8** existing.

### Live validation

- **L1** Deploy master + template + abm (Bring in step; rehearse on staging). Asset ritual.
- **L2** On the cockpit, Open as support on **abm-staging** first (restore it; the recovery
  account exists there by inheritance): new tab lands inside as Payobook support, bar shows with
  countdown, navigate two screens, Leave → logged out; the trail on the customer page shows the
  session with the two screens. Reuse the same link → "expired or already used" page.
- **L3** On live abm: the customer admin switches support OFF → cockpit button disabled with the
  message; switch ON → open a 30-minute session, verify the bar, end it from the cockpit
  (`support_end`) → the tab's next click lands on "session ended". Daily digest (P3) run by hand
  lists the session.
- **L4** Suspended + support: on staging, suspend (P5), open as support → allowed (door exempts
  the recovery account); ordinary user still paused. Resume. Drop staging.
- **L5** Chrome-MCP screenshots: dialog, bar (normal + last 5 min), customer page (switch on/off,
  trail), expired page, ended page, cockpit history. To `docs/handovers/fleet_p6_shots/`.

## Design (verbatim bar)

"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero: the customer-side
trail page (the trust surface — 1Password/Intercom-grade clarity). Zero dead-ends (expired link,
ended session, switch off — each a calm page or sentence with a next step). Plain language:
"support access", "session", "reason"; never "token", "impersonate", "sudo". Motion with purpose
(countdown, one pulse). No "Odoo".

## Deploy + verify — as before. Manifests: `pb_tenants` → 19.0.2.1.0, `pb_tenancy` → 19.0.1.3.0.

## Report back — standard list, plus: the entry URL used on abm, the rate-limit implementation,
the exact `auth_info` returned, and a copy of one trail row as the customer sees it.
