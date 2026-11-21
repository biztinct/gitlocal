# TIERS T2 — portal accounts: the Employee tier becomes real (handover for Opus)

Read first: `TIERS_PROGRAM.md` (strategy, verified plumbing), `TIERS_LEDGER.md` (rules T-R1…R12, rows T1–T13),
`T1_HANDOVER.md` + `T1_REPORT.md` (what T1 built — it is live on payobook since 2026-10-15), then the files you
extend. Repo `CLAUDE.md` rules apply (one addons dir; never "Odoo" in a user-visible string). You do not deploy;
Fable does. Plain words in every string a person can see (ledger T-R4/T-R5); engineering words in code comments,
docstrings, commits.

## What T2 is, in the owner's words
"Ideally a general employee should not have access to backend functionality; features should be provided in the
portal itself." After T2 an employee can have an **employee login** (a portal/share account — `base.group_portal`,
no `base.group_user`) and every My Payobook page still works for them: home, profile + change request, documents +
upload, payslips (list, page, PDF), tax sheet, schedule, timesheet fix, leave apply, overtime. A share user cannot
load the backend at all (stock), holds no backend permission, and cannot hold a role (biz_access constraint). The
Access screen gains an **Employee / Staff** switch so HR can move a person between the two tiers in one click, and
new joiners' automatic accounts become real employee logins. The demo generator makes the demo employee logins
employee logins (Fable flips the live ones through the new switch after deploy — that is the live walk).

## Decisions already taken (do not re-open)
- **D1 One link.** `hr.employee.user_id` is the employee's login, whatever its type. No `/my` page, record rule or
  helper ever looks at `pb_portal_user_id`; instead the joiner pipeline also sets `user_id` (item 5). Reason:
  ~15 helpers in 13 modules and every own-record rule key on `user_id` (explorer facts in §Verified plumbing).
- **D2 Portal seams run under `sudo()` after an explicit ownership guard** — the pattern 12 sibling modules already
  use (pb_assets, pb_onboarding, pb_pay, …). No new `base.group_portal` ACL rows or record rules, except where
  stock portal mechanics need the record (none found). The guard is always "the record's employee is
  `_ess_employee()`" (or the request's own employee for creates). `sudo()` keeps `env.user` — the submitter stays
  the employee on chatter and approval seats.
- **D3 The rule family grows, not multiplies (T-R1).** `_pb_employee_only()` becomes true for a share user with an
  employee; `_pb_portal_only()` is then true for them by construction (share users cannot hold roles; the
  reports/open-seat exclusions apply to *internal* users only — a share user has no backend to keep).
- **D4 Demotion is refused, never forced, when the person still runs people or decisions** (T-R8): any active direct
  report, any open approval seat, admin/system, the recovery login, or yourself. Active roles: if the roles approval
  route is live (`pb_access_approval._roles_route_live()`), refuse with "remove their roles first" so removal goes
  through approvals; otherwise end the roles through the board's own removal path (audit rows), then demote.
- **D5 No new stored field anywhere** (so the batch to other databases can wait; `docs/deploy/PENDING.md` rule).
- **D6 Modules touched:** `pb_me_portal`, `biz_access`, `pb_zoho_bridge`, `pb_demo`. Nothing else (pb_ess_workforce
  is reached only through its facade, which you call under sudo from pb_me_portal's side — see item 3; if a facade
  write cannot be made safe from outside, say so in the report rather than editing pb_ess_workforce).

## Scope (binding)

### 1. The rule — `pb_me_portal/models/ess_landing.py`
- `_pb_employee_only()`: replace the `not user._is_internal()` early-return with: `if user._is_public() or
  user._is_admin() or user._is_system(): return False`; then the existing employee `search_count`; then
  **`if user.share: return True`** (a share user with an employee is an employee, full stop); then the existing
  Pay Run sidebar + hiring checks for internal users. Update the docstring (who is an employee now).
- `_pb_portal_only()`: inside the try, after `_pb_employee_only()`: `if self.sudo().share: return True` before
  the three exclusion probes. Docstring: the exclusions are for internal users.
- `session_info`: unchanged (share users never load the web client).
- `_login_redirect` (controllers): unchanged — stock portal lands share users on `/my`.

### 2. pb_me_portal's own seams — `pb_me_portal/controllers/portal.py`
Read `pb_me_portal/controllers/portal.py` whole first. Keep every route path, auth and template. Changes:
- **Profile change request** (`/my/profile/request` POST, `:162-184`; `/my/profile/request/<id>` GET `:186`;
  `/submit` POST `:199`): create under `request.env['pb.profile.change.request'].sudo()` with
  `employee_id = emp.id` explicit (the model's own `create` at `models/pb_profile_change_request.py:203-208`
  searches the employee from `self.env.uid` — keep that working: it runs under sudo now, so pass `employee_id`
  yourself and make sure the model does not overwrite it). `_own_request` (`:212-220`) browses under sudo and
  guards `req.employee_id == emp`; `can_submit` and `action_submit()` run on that sudo record. The comment at
  `:178` ("deliberately as the user") is replaced by one that names D2.
- **Documents** (`/my/documents` GET `:226`, `/my/documents/upload` POST `:254-316`): `ir.attachment` create
  (`:287`) and `pb.employee.document` create (`:302`) under sudo, after the route checks (own employee, category
  `ess_uploadable`, size/type checks already there). The model guard `models/employee_document_ext.py:26-43`
  skips under `self.env.su` — so the route **must** keep the category check itself (it does; keep it, and add a
  test that a non-uploadable category is refused for a share user). Download links (`:250`): append
  `&access_token=<token>` where token = `att.sudo().generate_access_token()[0]` if the attachment has none
  (`ir.attachment.access_token`); use the same tokened URL for internal users (one code path).
- **Payslips** (`/my/payslips` `:368-399`, `/my/payslips/<id>` `:401-424`): om_hr_payroll's
  `_prepare_my_payslips_values` (`om_hr_payroll/controllers/portal.py:61`) searches `hr.employee` as the user
  (`:30`) → AccessError for a share user. In `PbMePortal` (the `CustomerPortal` subclass) override
  `_get_payslips_domain()` to build the domain from `self._ess_employee()` (sudo) and return
  `[('employee_id', '=', emp.id), ('state', 'in', ('done', 'paid'))]` (read om_hr_payroll's original to keep the
  same state filter); override `_prepare_my_payslips_values` only if the search at `:83-84` still runs as the user —
  it does (`check_access_rights` then `search`) → the cleanest fix is to run the payslip search under sudo in
  pb_me_portal's `portal_my_payslips` itself (you already compute `slips` there `:372`): replace the call with your
  own sudo search + pager using the same values keys the template expects. Line reads `:375-390` and
  `line_ids.pb_net_line()` (`:53`) then run on sudo slips. Override `_document_check_access(model_name,
  document_id, access_token=None)`: when `model_name == 'hr.payslip'`, browse sudo, require
  `slip.employee_id == self._ess_employee()` (else `super()`), return the sudo record — this makes the payslip page
  and `?report_type=pdf` work for share users and internal users alike.
- **Tax sheet** (`:318-366`): already sudo; verify by test only.
- **Photos**: `portal.py:126` (`/web/image/hr.employee/<id>/avatar_256`) and `models/pb_me_home.py:321`
  (`/web/image/hr.employee.public/<id>/avatar_128`) are fetched by the browser as the user → a share user gets
  the placeholder. Add one route `/my/photo/<int:employee_id>/<string:size>` (auth user, GET): size in
  `('avatar_128', 'avatar_256')`, sudo browse, **only the person's own employee** (else 404), stream via
  `request.env['ir.binary']._get_image_stream_from(emp_sudo, field_name=size).get_response()`. A helper
  `pb.me.home._photo_url(employee, size)` returns that route for every user (one code path). Use it in both
  places. Other modules' avatar URLs (pb_onboarding org chart, pb_rnr) are **not** in scope — list them in the
  report under "left for T3".
- **Home** (`_prepare_portal_layout_values` `:56-79`, `pb.me.home.get_home_data`): read-only sudo already;
  the `pbme-employee` class now applies to share users too (via item 1). Verify by test (T2.6).

### 3. The workforce seams reached from My Payobook — `pb_ess_workforce` facade, called from pb_me_portal side
`pb_ess_workforce/models/ess_workforce.py` writes as the user: `hr.attendance.correction` create + `action_submit`
(`:363-366`) and `hr.leave` create + `action_confirm` (`:498-509`). Its routes live in
`pb_ess_workforce/controllers/portal.py` (`/my/work/timesheet/fix` `:110`, `/my/work/leave/apply` `:137`) and
call the facade on `request.env['pb.ess.workforce']`. **pb_me_portal does not depend on pb_ess_workforce** — do
not add the dependency. Instead: check whether pb_ess_workforce's own `_own_employee` (`:64-74`, sudo search on
`user_id`) already finds the share user's employee (it does, D1) and whether the two writes fail for a share
user (they will: no ACL on `hr.leave` / `hr.attendance.correction`). The fix belongs in pb_ess_workforce and D6
forbids editing it in T2 → **do not fix it; prove it** (T2.9 expects the failure and marks it `expectedFailure`
with the reason) and put the two-line fix (`self.env[...]` → `self.env[...].sudo()` after `_own_employee()`
guard) in the report under "T2b: pb_ess_workforce". Fable will run T2b as a 20-minute follow-up. Same for
`pb_goals` (`kr.py:172` write as user — but pb_goals already grants portal ACLs; test it, expect pass), and the
read-only pages of pb_timeoff, pb_pay, pb_assets, pb_onboarding, pb_training, pb_hiring (`/my/hiring`,
`/my/refer`), pb_offboarding, pb_pip, pb_rnr, pb_comp_ben, pb_probation: T2.10 smoke-GETs each as a share user
and records status + whether the body contains an error page; failures are listed, not fixed.

### 4. The Access screen — `biz_access`
Read `biz_access/models/pb_access_facade.py` (`people` `:1258-1293`, `_person_row` `:1369-1381`, `passport`
`:1479-1508`, `_internal_user` `:501-513`, `_person` `:1198-1209`, `create_user` `:1295-1367`),
`biz_access/models/role_editor.py` (`_assign_role` `:22-50`, `remove` `:81-102`, passport override `:312-320`),
`biz_access/models/role_assignments.py` (`_check_safe` `:36-44`, `AccessUser.write` `:179-218`),
`biz_access/models/pb_access_approval.py` (`_roles_route_live` `:32-42`), `pb_access_delegation.py:105-110`
(`origin` selection), `static/src/js/access_board.js` (`loadPeople` `:426`, `loadPassport` `:462`, `createPerson`
`:566`, `reload` `:277-294`), `static/src/xml/access_board.xml` (people list `:425-482`, passport header
`:499-527`, "Add a person" modal `:1082-1120` — clone its shape for the confirm modal), the SCSS the board uses
(`pbva-*`, `pbim-btn` classes — reuse, add only what the chip and the switch need).
- **`people()`**: domain becomes `['&', ('active','=',True), '|', ('share','=',False),
  ('employee_ids','!=',False)]` (hr's `res.users.employee_ids`, `hr/models/res_users.py:63`); never agency /
  vendor portal logins (they have no employee). `_person_row` adds `'kind': 'employee' | 'staff'`
  (`employee` ⇔ `user.share`) and `'has_employee': bool(user.employee_ids)`.
- **`passport()`**: for a share user return `header` (with `kind`, `has_employee`, `switch` — see below), empty
  `rail`, empty `roles`, `can_manage`. Do it by giving `_person()` an `allow_share=True` path used only by
  `passport`; every role operation keeps `_internal_user` (constraint `_check_safe` stays). The `header` for
  everyone gains `'kind'`, and `'switch': {'to': 'employee'|'staff', 'allowed': bool, 'why': str, 'roles_ending':
  int, 'reports': int, 'open_seats': int}` computed by a new `_account_switch_preview(user)`.
- **`set_account_type(user_id, kind, reason=None)`** on `pb.access` (`@api.model`): `_require_manage()`;
  `kind in ('employee', 'staff')`; refuse (UserError, plain words) when: target is you; target `_is_admin()` /
  `_is_system()` / holds `base.group_system`; target is the recovery login (`recovery_login(self.env)` as
  `_internal_user` does); `kind == 'employee'` and (any active direct report — `hr.employee` sudo
  `search_count([('parent_id.user_id','=',uid)])`; any open seat — `biz.approval.request.seat`
  `[('|'), ('acting_user_id','=',uid), ('user_id','=',uid), ('status','=','open')]` (biz_access does not depend
  on biz_approval_workflow → `'biz.approval.request.seat' in self.env` soft read); has active roles while
  `_roles_route_live()`). Then:
  - to **employee**: end active `source='role'` assignments through the same path `remove()` uses (`active=False`
    under the `_pb_access_internal` sentinel + reconcile + audit `pb.access.delegation` row — add a selection value
    `('account_switch', 'Account type changed')` to `origin` if `board_removal` reads wrong; a selection value is
    not a stored *column*, D5 holds); loans (`source='loan:…'`) are ended via `pb.access.revoke` for each live
    delegation; then `user.sudo().write({'group_ids': [Command.set([base.group_portal])]})`. This passes
    `res.users._check_disjoint_groups` (one user type) and biz_access's `AccessUser.write` baseline logic
    (`role_assignments.py:179-218`) — read it: a `(6,…)` set without the sentinel updates the baseline and
    deactivates sources whose closure meets removed groups; make sure nothing raises for a user with zero
    sources.
  - to **staff**: `user.sudo().write({'group_ids': [Command.set([base.group_user])]})` exactly as `create_user`
    does (`:1326-1337`). No roles are given; the passport reloads and "Give a role" appears.
  - Both: `user.sudo()._pb_reconcile_access()` if the write did not already; `access_revision()` bump if the board
    uses it for cache busting (`role_editor.py:322-325`); return `{'ok': True, 'kind': kind, 'message': …}`.
  - Log one `_logger.info` line per switch (who, whom, from→to).
- **UI** (design mandate: the board's own quiet, premium look — Lucide icons via the board's `ic()` helper, no emoji,
  no gradients; Payobook palette; no "Odoo"):
  - People list row: a small chip after the name — "Employee" (muted) or nothing for staff (staff is the default
    look; do not chip 200 rows). Search still matches login and name.
  - Passport header `pbva-pass-actions`: a segmented control `Employee | Staff` showing the current kind, enabled
    only when `passport.can_manage` and `switch.allowed`; when not allowed, the control is disabled and a one-line
    reason sits under it (`switch.why`, e.g. "3 people report to Khang. Move them to another manager first." /
    "2 decisions are waiting with Khang." / "Remove their roles first." / "You cannot change your own account.").
  - Confirm modal (clone the "Add a person" modal shape): title "Make Khang an employee?" / "Make Khang staff?";
    body in plain words: what they keep (My Payobook: payslips, leave, documents, requests), what they lose or gain
    (the backend; "2 roles end today" when roles_ending > 0; "They get the backend; give them a role next"), a
    "Reason (optional)" input, buttons "Make employee" / "Make staff" (primary) and "Keep as is" (ghost).
  - For an Employee passport, the roles column shows one quiet line: "Employee login — no roles. Make them staff
    to give a role." and "Give a role" is hidden.
  - Toast on success through the board's existing notification path; then `reload()`.
- **Tests** (biz_access): see T2.11–T2.13.

### 5. Joiners — `pb_zoho_bridge/models/zoho_pipeline.py:586-624` `_auto_create_login`
After the account is created (`:613-621`) or an existing one linked (`:605-607`): if `not employee.user_id` and the
account is a share user (`user.share`) → `employee.sudo().write({'user_id': user.id})`. Keep `pb_portal_user_id`
exactly as is (other code reads it). Update the module docstring in `pb_zoho_bridge/models/hr_employee.py:16-18`
(the "It is NOT `user_id`" sentence: now it is also `user_id` once the account exists — the joiner's employee login
is their login, D1). hr's `_sync_user` (`hr/models/hr_employee.py:1340`, called from `write` at `:1433`) copies
name/email/image from the user to the employee on linking — the account was made from the employee's own name and
work email, so nothing changes; assert that in T2.14. Do **not** backfill existing employees (T4 does that with a
rollback list).

### 6. The demo generator — `pb_demo/models/demo_ess.py`
`_ensure_demo_login` (`:64-90`) and its callers (`:167-171`, `:289`, `demo_workforce_current.py:1216`): the
manager login (`manager=True`) stays internal; every other demo login (employee, minor, ess1–ess10) is created
with `group_ids = [(6, 0, [base.group_portal])]` and linked on `employee.user_id` as today. Refreshing an existing
login (`:83`) must not change its type (the live ones are flipped by Fable through the switch, not by regen) — add
a comment saying so. Read `employee-only-landing` notes in the file (`:46-47`) and keep the "only the manager keeps
the demo visitor group" rule.

### 7. Versions
`pb_me_portal` → `19.0.3.0.0` (+ `test_06_font` pin, ledger T7); `biz_access`, `pb_zoho_bridge`, `pb_demo`: bump
the minor (read each manifest). `pb_me_portal_website` unchanged.

### 8. Tests (numbered). Fixture: `share_emp` = `res.users` with `group_ids=[(6,0,[base.group_portal])]` + an
`hr.employee` with `user_id` = that user (clone `pb_me_portal/tests/test_portal_only.py:21-52` `_make_people`
for the shape; HttpCases pin `dbfilter` as there, ledger T6). `plain` and `staff` as in T1.
- **T2.1** `share_emp._pb_employee_only()` is True; `share_emp._pb_portal_only()` is True; a share user *without*
  an employee: both False; `plain`/`lead`/`staff` unchanged from T1 (T1.1–T1.5 still pass; update T1.5's share
  assertion to "share user without employee → False").
- **T2.2** HttpCase as `share_emp`: `GET /my` 200, body has `pbme-home` and `pbme-employee`, the greeting carries
  the employee's name, no `o_frontend_to_backend_nav`, no `o_backend_user_dropdown_link`; `GET /bizapp` ends on
  `/my` (stock); `GET /web/login` while signed in ends on `/my`.
- **T2.3** HttpCase as `share_emp`: `POST /my/profile/request` with one editable field → a
  `pb.profile.change.request` exists for their employee with `create_uid == share_emp` and the new value; GET its
  page 200; POST `/submit` → state advanced (read the model's states). Another share user's request → 404/redirect
  (ownership guard), never 500.
- **T2.4** HttpCase as `share_emp`: upload a small PDF into an `ess_uploadable` category → `pb.employee.document`
  for their employee, attachment bound, `/my/documents` 200 lists it, the download link carries `access_token`
  and `GET` of it returns 200 with the bytes; upload into a non-uploadable category → refused (message shown,
  no record).
- **T2.5** HttpCase as `share_emp` with two `done` payslips (make them with the demo-independent minimal fixture
  used in `test_pb_me_portal.py:43-194`; if payslip creation needs a structure, reuse that test's helper) and one
  belonging to someone else: `/my/payslips` 200 lists exactly two; `/my/payslips/<own>` 200;
  `/my/payslips/<own>?report_type=pdf` 200 `application/pdf`; `/my/payslips/<other>` → redirect to `/my` or 403,
  never 500. Same four for `plain` (internal) still pass.
- **T2.6** `/my/taxsheet` 200 as `share_emp`; `/my/photo/<own>/avatar_128` 200 image; `/my/photo/<other>/…` 404.
- **T2.7** TransactionCase: `pb.me.home.get_home_data(emp)` returns a dict for `share_emp` (person/pay/leave keys).
- **T2.8** T1's suite + `test_me_home*` + `test_pb_me_portal` still green (known M19 error named).
- **T2.9** (expected failure, documented) HttpCase as `share_emp`: `POST /my/work/leave/apply` → today raises /
  shows an error for a share user. Mark `@unittest.expectedFailure` with the reason in the docstring and the
  two-line fix in the report. Skip if pb_ess_workforce is not installed.
- **T2.10** Smoke, HttpCase as `share_emp`: GET each of `/my/holidays`, `/my/pay`, `/my/assets`, `/my/journey`,
  `/my/buddy`, `/my/orgchart`, `/my/training`, `/my/hiring`, `/my/refer`, `/my/resignation`, `/my/growth`,
  `/my/recognition`, `/my/compensation`, `/my/goals`, `/my/work/schedule`, `/my/work/timesheet`, `/my/work/leave`,
  `/my/work/overtime` (skip those whose module is not installed): record `(path, status, 'error page' if the body
  contains 'o_error_detail' or 'Access Error'/'AccessError' else 'ok')` and `assertNotEqual(status, 500)` only.
  The table goes in the report.
- **T2.11** biz_access TransactionCase (as an access manager): `people()` includes `share_emp` with
  `kind='employee'`, excludes a vendor-style share user with no employee; `passport(share_emp)` returns header
  `kind='employee'`, empty roles, `switch.to == 'staff'`, `switch.allowed` True.
- **T2.12** `set_account_type(plain, 'employee')` → `plain.share` True, `plain.group_ids` = `{group_portal}`,
  `_pb_portal_only()` True, an audit row exists; then `set_account_type(plain, 'staff')` → share False,
  `group_ids` = `{group_user}`. With an active role on `plain` and the roles route not live → role ends
  (`active=False`), audit row, then demoted. With the roles route live (patch `_roles_route_live` → True) → refused
  with the "remove their roles first" message, nothing changed.
- **T2.13** refusals: self; admin (`base.user_admin`); `lead` (has a report) — message names the count; a user with
  an open seat (patch or real seat as T1.3b) — refused; promoting a public user — refused; non-manager caller →
  the `_require_manage` error.
- **T2.14** pb_zoho_bridge: `_auto_create_login(employee, company, summary)` on an employee with `work_email` and
  no `user_id` → user created share, `employee.user_id == user`, `employee.pb_portal_user_id == user`, employee
  name/email unchanged; with an existing internal account on that email → linked on `pb_portal_user_id` only
  (`user_id` untouched — D1 is for *employee* logins); with `auto_create_logins` off → nothing.
- **T2.15** pb_demo: `_ensure_demo_login('t2x.demo@example.com', 'T2 X', company)` → share user;
  `manager=True` → internal; calling it again on the existing login does not change its groups.
- **T2.16** Run on the clone (ledger T-R9, T11): `-u pb_me_portal,biz_access,pb_zoho_bridge,pb_demo --test-tags
  /pb_me_portal,/pb_me_portal_website,/biz_access,/pb_zoho_bridge,/pb_demo`. Paste the summary lines.
  biz_access and pb_demo have their own suites — they must stay green (name pre-existing errors if any, with proof
  from a run on the untouched code if unsure).

## Non-goals (do not do)
- No backfill of existing employees' `user_id` from `pb_portal_user_id` (T4). No flipping of live demo logins (Fable).
- No change to pb_ess_workforce, pb_goals, pb_timeoff, pb_pay, pb_onboarding, pb_training, pb_hiring, pb_offboarding,
  pb_pip, pb_rnr, pb_comp_ben, pb_probation, pb_driver_checkin, om_hr_payroll, pb_hr_payroll_base, hr, portal, website.
- No `/driver` or clock-in work for share users (T3). No "Ask HR", no "My requests", no announcements (T3).
- No new `base.group_portal` ACL/record-rule rows (D2) — if you believe one is unavoidable, stop and say why in the
  report instead of adding it.
- No removal of `base.group_user`'s implied groups (closed by construction: a share user is not in `base.group_user`).
- No new stored field (D5). No new user-facing text containing the vendor's name.

## Safety rails
- Every sudo write in a `/my` route sits **after** the ownership guard and passes `employee_id` explicitly.
- The photo route and the payslip access override return 404 / redirect for anything not the person's own.
- `set_account_type` is manage-gated and refuses before it changes anything; one transaction; never touches
  passwords, `login`, `active`, `company_ids`.
- The clone is `p0clone` (port 8099, `--db-filter='^p0clone$'`); never run against `payobook`.

## Report back (write `docs/handovers/tiers/T2_REPORT.md`)
1. Files changed/added, one line each.
2. T2.1–T2.16 results with the clone log's summary lines; the T2.10 table; the T2.9 expected failure and the
   two-line pb_ess_workforce fix (T2b) spelled out as a diff.
3. "Left for T3": every avatar/download URL or page you found that still assumes an internal user.
4. Decisions the handover did not make; proposed ledger rows (gotcha + how to apply).
5. Self-review against Scope and Non-goals, one line each: "done" / "deviated: why".
