# TIERS T2 — portal accounts: the Employee tier becomes real — implementation report (Opus)

Handover: `T2_HANDOVER.md`. Ledger: `TIERS_LEDGER.md`. Not committed, not deployed.
Clone runs: `p0clone`, port 8099, staged from `/tmp/deployMH` (final run 2026-10-15 02:08–02:12 server time).
pb_demo is not installed on `p0clone`, so its suite ran on a throwaway database (`t2demo`), which was dropped
straight after the run, filestore included.

## 1. Files changed / added
| File | What |
|---|---|
| `pb_me_portal/models/ess_landing.py` | `_pb_employee_only()`: refuses public/admin/system first, then the employee search, then **`if user.share: return True`**, then the internal checks (Pay Run, Hiring) as before. `_pb_portal_only()`: `share` → True right after `_pb_employee_only()`, before the three internal-only exclusions. Docstrings and module docstring updated: who is an employee now, fence (internal) vs wall (employee login). |
| `pb_me_portal/controllers/portal.py` | Module docstring: the T-R11 rule. New `_ess_own_employees()` (every employee record of the session user, sudo; empty for public). **Profile**: create under sudo with `employee_id` passed explicitly; `_own_request` returns a sudo record guarded by `req.employee_id == _ess_employee()`; submit runs on it. **Documents**: attachment and document creates under sudo after the existing guards (own employee, `ess_uploadable` category, size, type); `_doc_download_url()` adds `&access_token=` (from `generate_access_token()`) for every user. **Payslips**: overrides `_get_payslips_domain` (own employee, om_hr_payroll's `('done','cancel')` filter), `_prepare_my_payslips_values` (same keys, sudo search + count) and `_document_check_access` (own slip → sudo record, else `super()`); the home counter `payslip_count` counts under sudo. **Photo**: new route `/my/photo/<int:employee_id>/<string:size>` (auth user, GET, `avatar_128`/`avatar_256` only, own employee only, else 404). `_profile_card` uses the photo route. |
| `pb_me_portal/models/pb_me_home.py` | New `pb.me.home._photo_url(employee, size)` → `/my/photo/<id>/<size>`; the home's person card uses it. |
| `pb_me_portal/__manifest__.py` | `19.0.2.2.0` → `19.0.3.0.0`. |
| `pb_me_portal/tests/test_me_home_cards.py` | `test_06_font` pin → `19.0.3.0.0` (ledger T7). |
| `pb_me_portal/tests/test_portal_only.py` | T1.5 comment: a share user WITHOUT an employee is still not portal-only (assertion unchanged, still true). |
| `pb_me_portal/tests/test_portal_accounts.py` (new) | T2.1–T2.7, T2.9, T2.9b (goals), T2.10. |
| `pb_me_portal/tests/__init__.py` | Imports the new file. |
| `biz_access/models/pb_access_facade.py` | `_internal_user` now delegates to new `_login_user(user_id, allow_share)`; `_person(user_id, allow_share=False)`; new `_employee_user_ids(users)` (searched on `hr.employee`). `people()`: internal logins plus share logins that belong to an employee record. `_person_row` adds `kind` and `has_employee`. `passport()`: opens an employee login (`allow_share=True`) and returns header + switch, empty rail/roles; every header gains `kind`, `has_employee`, `switch`. `surface_access()` admits an employee login (pure read; it opens nothing). |
| `biz_access/models/account_type.py` (new) | `_switch_counts`, `_switch_sources`, `_switch_refusal` (the one list of refusals), `_account_switch_preview`, `set_account_type(user_id, kind, reason=None)`, `_end_roles_for_switch`. |
| `biz_access/models/role_editor.py` | `passport` override returns early for an employee login (`equivalent_roles = []`) instead of calling `_person` without `allow_share`. |
| `biz_access/models/pb_access_delegation.py` | `origin` selection gains `('account_switch', 'Account type changed')` (a value, not a column — D5 holds). |
| `biz_access/models/__init__.py` | Imports `account_type`. |
| `biz_access/static/src/js/access_board.js` | State `switching`/`switchingBusy`; `kindOptions`, `openSwitch`, `closeSwitch`, `onSwitchReason`, `switchTitle`, `switchRolesLine`, `confirmSwitch` (calls `set_account_type`, toast, `reload()`); Escape closes the modal; `seesLine` and `personNote` know an employee login. |
| `biz_access/static/src/xml/access_board.xml` | People row: quiet "Employee" chip. Passport: "Give a role" hidden for an employee login; an `Employee | Staff` segmented control (the lens bar's own `pbva-tabs`/`pbva-tab`) with the reason line under it; employee wording in the menu column and the roles column; confirm modal cloned from "Add a person". |
| `biz_access/static/src/scss/access.scss` | One small block: the switch row and the disabled state. No new colour. |
| `biz_access/__manifest__.py` | `19.0.1.5.3` → `19.0.1.6.0`. |
| `biz_access/tests/test_account_type.py` (new) | T2.11–T2.13 (+ 12b, 12c, 13b, 13c). |
| `biz_access/tests/test_access_generic.py` | The copy audit also scans `account_type.py` for product names. |
| `biz_access/tests/__init__.py` | Imports the new file. |
| `pb_zoho_bridge/models/zoho_pipeline.py` | `_auto_create_login` calls new `_link_employee_login(employee, user)` after creating or finding the account: sets `user_id` only for a share account, only when the employee has no login, and only when that account is not already another employee's in the same company. `pb_portal_user_id` untouched. |
| `pb_zoho_bridge/models/hr_employee.py` | Module docstring: the "It is NOT `user_id`" sentence rewritten (D1). |
| `pb_zoho_bridge/__manifest__.py` | `19.0.1.1.0` → `19.0.1.2.0`. |
| `pb_zoho_bridge/tests/test_joiner_login.py` (new), `tests/__init__.py` | T2.14 (a–d). |
| `pb_demo/models/demo_ess.py` | `_ensure_demo_login(..., manager=False, internal=None)`: a NEW login is portal (`base.group_portal` only) unless `manager` or `internal=True`; an EXISTING login keeps its kind (internal ones get their internal groups re-asserted as before, share ones are left alone). Docstring says the live logins are switched on the Access screen, not by regen. "Only the manager keeps the demo visitor group" untouched. |
| `pb_demo/models/demo_workforce_current.py` | The two field-check-in drivers pass `internal=True` (`/driver` needs a full account until T3). |
| `pb_demo/__manifest__.py` | `19.0.1.12.3` → `19.0.1.13.0`. |
| `pb_demo/tests/test_demo_logins.py` (new), `tests/__init__.py` | T2.15 (a–d). |

Not touched: `pb_me_portal_website` (staged and tested only), pb_ess_workforce and every other module (D6).
No stored field added (D5). No `base.group_portal` ACL or record-rule row added (D2).

## 2. Test results (clone log)
```
p0clone   (-u pb_me_portal,biz_access,pb_zoho_bridge,pb_demo --test-tags /pb_me_portal,/pb_me_portal_website,/biz_access,/pb_zoho_bridge,/pb_demo)
odoo.tests.stats: biz_access: 212 tests 92.72s 69034 queries
odoo.tests.stats: pb_me_portal: 101 tests 41.54s 19806 queries
odoo.tests.stats: pb_me_portal_website: 6 tests 3.03s 820 queries
odoo.tests.stats: pb_zoho_bridge: 14 tests 2.28s 1708 queries
odoo.tests.result: 0 failed, 1 error(s) of 253 tests when loading database 'p0clone'
ERROR: TestPbMePortal.test_01_profile_change_flow_and_audit   <- pre-existing M19 (AccessError "Uh-oh! Looks like you have stumbled upon some top-secret records."), not T2

t2demo    (throwaway database, -i pb_demo --test-tags /pb_demo, dropped afterwards)
odoo.tests.stats: pb_demo: 42 tests 0.87s 760 queries
odoo.tests.result: 0 failed, 0 error(s) of 36 tests when loading database 't2demo'
```
pb_demo note: on the final run `createdb -T p0clone` was refused (the live server's job runner was connected to
`p0clone` for a moment), so Odoo created `t2demo` as a fresh database and installed pb_demo with its 114 modules
into it. The 23 `TestWorkforceCurrent` cases skip themselves ("no demo company on this database"), as they did on
the earlier run against a copy of p0clone, which was also green (36/36). The four T2.15 cases ran. `t2demo` and its
filestore are gone (`pg_database` and the filestore listing checked).

| # | Test(s) | Result |
|---|---|---|
| T2.1 | `TestEmployeeLoginRule.test_t2_1_*`, `_1b_*`, `_1c_*` | pass. Employee login: `_pb_employee_only` and `_pb_portal_only` True. Share user without employee: both False. plain / lead / staff / admin / public unchanged from T1. T1.1–T1.6 still pass. |
| T2.2 | `test_t2_2_home_and_doors`, `test_t2_2b_sign_in_lands_on_my` | pass. `/my` 200 with `pbme-home`, `pbme-employee`, the greeting and the short name, own photo through `/my/photo`, neither backend link. `/bizapp`, `/web`, `/` all end on `/my`. **Deviation**: a bare `GET /web/login` while signed in renders the sign-in page (stock `web_login` only redirects when `?redirect=` is given), so the test checks `GET /web/login?redirect=/bizapp` → `/my`, plus a real form sign-in (csrf token, password) → `/my`. |
| T2.3 | `test_t2_3_profile_change_request`, `test_t2_3b_*` | pass. Request created for their own employee, `create_uid` = the employee login, value stored, page 200, submit moves it out of draft. Someone else's request: GET and submit both land on `/my/profile`, nothing shown, nothing changed. |
| T2.4 | `test_t2_4_document_upload_and_download`, `test_t2_4b_*` | pass. Upload into `cat_other` → document for their employee, `create_uid` the employee login, attachment bound, not verified; `/my/documents` lists it; the link carries `access_token` and returns the exact bytes (200). A category with `ess_uploadable` off → `?error=category`, no record. |
| T2.5 | `test_t2_5_payslips_for_an_employee_login`, `test_t2_5b_payslips_for_an_internal_employee` | pass. Share user: list shows exactly their two slips; detail 200; `?report_type=pdf` 200 `application/pdf`; somebody else's slip → `/my`. Same four for the internal `plain`. |
| T2.6 | `test_t2_6_tax_sheet_and_photo`, `test_t2_6b_*` | pass. `/my/taxsheet` 200; own photo 200 `image/*`; another person's photo 404; an unknown size 404; `/my/profile` draws the photo route. |
| T2.7 | `test_t2_7_home_facts_for_an_employee_login` | pass. `get_home_data` returns `person`, `pay`, `leave`; the avatar is `/my/photo/<id>/avatar_128`; another person's employee → None. |
| T2.8 | existing suites | pass, except pre-existing M19 above. Odoo's stats line for pb_me_portal went from 80 (T1) to 101; pb_me_portal_website 6 as in T1; biz_access's own suite green (212). |
| T2.9 | `test_t2_9_leave_apply_fails_until_t2b` | **the expected failure, pinned** (see below). The route shows its error page (200), no leave is created. Message logged on the clone: *"You are not allowed to access 'Time Off Type' (hr.leave.type) records. … Time Off/Administrator, Time Off/Officer …"*. |
| T2.9b (extra) | `test_t2_9b_goals_progress_for_an_employee_login` | pass. pb_goals' own portal rows work: an employee login moves its own key result to 40 % (`POST /my/goals/kr/<id>/move` 303 → `/my/goals?ok=moved`). |
| T2.10 | `test_t2_10_neighbour_pages_smoke` | pass (no 500). Table below. |
| T2.11 | `TestAccountType.test_t2_11_*` | pass. `people()` has the employee login (`kind='employee'`, `has_employee`), not the vendor-style share login; passport: kind employee, empty rail and roles, `switch.to='staff'`, allowed. `surface_access` opens nothing; `grant` to an employee login is still refused. |
| T2.12 | `test_t2_12_both_ways`, `_12b_roles_end_through_the_board`, `_12c_refused_while_role_changes_need_approval` | pass. plain → employee: share, `group_ids == {portal}`, `_pb_portal_only()` True, one `account_switch` audit row (state "Taken back", reason, who); → staff: `group_ids == {group_user}`, second audit row. With a role and the route not live: the assignment goes inactive, a `board_removal` row is written, the group is gone, "1 role ended". With the route live: refused "Remove their roles first.", nothing changed, no audit row. |
| T2.13 | `test_t2_13_refusals`, `_13b_an_open_decision_keeps_the_full_login`, `_13c_promoting_needs_nothing_more` | pass. Yourself; admin; lead ("1 person reports to …"); public user; share login without employee; a non-manager caller (AccessError); an unknown kind. A real open approval seat → "1 decision is waiting with …". Promotion works, second press says "already has a full login" and writes nothing. |
| T2.14 | `TestJoinerLogin.test_t2_14*` (a–d) | pass. New account is share, `user_id` and `pb_portal_user_id` both set, name and work email unchanged. Existing internal account → `pb_portal_user_id` only. Existing share account → both. Setting off → nothing created. |
| T2.15 | `TestDemoLogins.test_t2_15*` (a–d) | pass. New demo login → `{portal}` only; second call leaves its groups alone; manager → internal; an existing full login stays full; a driver (`internal=True`) is full. |
| T2.16 | the runs above | done. |

### T2.10 — the neighbours' pages as an employee login (smoke)
| Path | Status | Body |
|---|---|---|
| /my/holidays | 200 | ok |
| /my/pay | 200 | ok |
| /my/assets | 200 | ok |
| /my/journey | 200 | ok |
| /my/buddy | 200 | ok |
| /my/orgchart | 200 | ok |
| /my/training | 200 | ok |
| /my/hiring | 200 | ok |
| /my/refer | 200 | ok |
| /my/resignation | 200 | ok |
| /my/growth | 200 | ok |
| /my/recognition | 200 | ok |
| /my/compensation | 200 | ok |
| /my/goals | 200 | ok |
| /my/work/schedule | 200 | ok |
| /my/work/timesheet | 200 | ok |
| /my/work/leave | 200 | ok |
| /my/work/overtime | 200 | ok |
All 18 modules are installed on p0clone; none skipped. "ok" = no `o_error_detail` / "Access Error" / "AccessError"
in the body, final URL = the path asked for. This is a smoke check on a fresh person with no data: the pages render;
it does not prove every button on them (the leave and timesheet-fix writes below do fail).

### T2.9 — the expected failure, and why it is not `@unittest.expectedFailure`
This platform's test runner (`odoo/tests/case.py` `_Outcome`) does not honour `@unittest.expectedFailure`: the
first run reported the decorated test as a plain `FAIL` (counted in "3 failed"). So T2.9 is written as a **passing
check of today's failure**: status 200, the error page ("We couldn't do that"), zero leaves. Its docstring says to
flip it when T2b lands; it will go red the day the fix arrives, on purpose.

### T2b: pb_ess_workforce (the 20-minute follow-up)
Both writes already sit after `_require_own_employee()`, which forces the employee from the session (D1 finds the
share user's employee). The fix is `.sudo()` on the two creates; `sudo()` keeps `env.uid`, so `create_uid` stays the
employee and the self-approval guard (C18.27) still sees the truthful filer.
```diff
--- a/pb_ess_workforce/models/ess_workforce.py
+++ b/pb_ess_workforce/models/ess_workforce.py
@@ def request_fix(self, day, reason, check_in=False, check_out=False):
         if not ci:
-            corr = self.env['hr.attendance.correction'].create(vals)
+            corr = self.env['hr.attendance.correction'].sudo().create(vals)
             return {'ok': True, 'id': corr.id, 'state': corr.state}
-        corr = self.env['hr.attendance.correction'].create(vals)
-        corr.action_submit()     # as the real user — the chain's own gate
+        # TIERS T-R11: sudo after `_require_own_employee` (an employee login
+        # has no ACL here); env.uid is still the employee, so create_uid and
+        # the self-approval guard stay truthful
+        corr = self.env['hr.attendance.correction'].sudo().create(vals)
+        corr.action_submit()
         return {'ok': True, 'id': corr.id, 'state': corr.state}
@@ def apply_leave(self, type_id, date_from, date_to, note=False):
-        leave = self.env['hr.leave'].create({
+        leave = self.env['hr.leave'].sudo().create({
             'employee_id': emp.id,           # FORCED (I-H3)
```
Three things T2b must also do (they are why it is more than two keystrokes):
1. Under sudo, `hr.leave.type`'s company rule no longer filters `type_id`: check `int(type_id)` is one of the types
   `get_my_leave()` offers the person before the create, or a crafted id could book a type they are not offered.
2. Update the two docstrings ("created AS THE REAL USER", "No sudo anywhere in this method").
3. Flip `pb_me_portal`'s `test_t2_9_leave_apply_fails_until_t2b` to assert the leave exists, and add the same
   check for `/my/work/timesheet/fix`.

## 3. Left for T3 — pages and links that still assume a full account
- **Avatars** an employee login cannot load (placeholder instead of the face): pb_onboarding
  (`models/hr_employee.py:199`, `buddy_nomination.py:195`, `journey_ext.py:351`, `pb_onboarding.py:148`,
  `controllers/portal.py:455` res.users), pb_rnr (`pb_rnr_wall.py:88,126`, `celebration.py:130`,
  `digest.py:122,168,205`, `cycle.py:103`, `pb_rnr.py:176,349`, `controllers/portal.py:228`), pb_timeoff
  (`pb_timeoff.py:92`), pb_hiring (`pb_hiring.py:282` res.users). The pattern to clone: `pb.me.home._photo_url`
  only serves the person's OWN photo; colleague photos (org chart, buddy, wall) need a separate decision (which
  colleague photos may an employee login see) — a `hr.employee.public`-style rule or a tokened URL.
- **Downloads without a token** (403 for an employee login): pb_timeoff `pb_timeoff.py:203`, pb_pay
  `controllers/portal.py:102` (pay letter), pb_training `claim.py:561,668,671`, pb_hiring `facade_p6.py:153`,
  `offer.py:822`, `board_p1.py:743,795`, `forms_p2.py:1343` (pb_hiring `facade_p4.py:152-155` already adds a token
  — the precedent).
- **Writes**: pb_ess_workforce leave apply and timesheet fix (T2b above). Not smoke-tested here: the write buttons
  of pb_timeoff, pb_assets, pb_training claims, pb_offboarding resignation, pb_rnr nominations, pb_comp_ben,
  pb_probation — each should get one POST test as an employee login.
- **`/driver`** (field check-in) needs a full account; the demo drivers stay full logins (`internal=True`).
- **Approvals**: an employee login cannot hold an approval seat it can act on; the switch refuses demotion while a
  seat is open, but nothing stops a published route from naming an employee login as a future decider (a
  responsibility/role holder). T3's portal approvals, or a guard in the route builder, closes that.

## 4. Decisions the handover did not make
1. **`people()` searches `hr.employee`, not `res.users.employee_ids`.** `employee_ids` carries a company domain
   (`hr/models/res_users.py:57-60`) that follows the manager's current companies, so a multi-company group would
   hide employees of other companies. Same result on a single company; the same reason pb_me_portal searches.
   `has_employee` uses the same search.
2. **`surface_access()` admits an employee login.** `loadPassport` calls it beside `passport` in one
   `Promise.all`; refusing it would have failed the whole passport. It is a read and answers "opens nothing".
3. **Two extra refusals in the one refusal list**: making somebody an employee login when they have no employee
   record ("an employee login would show them nothing"), and promoting a share login that has no employee record
   (vendor/agency contacts are not this screen's business). Both in `_switch_refusal`, shown under the switch.
4. **Audit rows.** Each ended role gets the exact `board_removal` row `remove()` writes (so the migration's
   "later removal" check keeps working), and every switch writes one `account_switch` row: to Employee →
   state "Taken back" with `ended_on`; to Staff → state "Active", `applied_on`, `applied_group_ids = {group_user}`.
   No job or list filters on those rows (`run_auto_revert` needs `kind='temporary'`; the hand-over lists filter
   `origin='delegation'`).
5. **Loans to the person are ended through `revoke()`** (the hand-over's own end + both mails), then any source
   still marked active is closed under the sentinel, so an employee login never keeps an active assignment.
   "Active roles" for the live-route refusal counts own roles and loans alike (as T1's `_pb_holds_role` does).
6. **The same kind twice** returns `ok` with "already has …" and writes nothing (idempotent press).
7. **Payslip state filter** is om_hr_payroll's original `('done','cancel')` (the handover's example said
   `('done','paid')`; there is no `paid` state on this build — "keep the same state filter" won).
8. **Ownership by id across companies**: the payslip page and the photo accept any of the session user's own
   employee records (`_ess_own_employees`), not only the current company's — a person employed by two companies
   owns both records' slips. The list keeps `_ess_employee()` (current company first), as before.
9. **The switch sits on its own row directly under the passport header**, not inside `pbva-pass-actions`: the
   reason line ("3 people report to Khang. Move them to another manager first.") needs the width.
10. **biz_access is product-agnostic** (its copy audit failed my first run on "My Payobook"). Its strings say
    "self-service pages" instead; pb_me_portal (the product) keeps "My Payobook".
11. **pb_demo drivers stay full logins** (`internal=True`): `/driver` needs one (T3 non-goal).
12. **The upload's document create runs in a savepoint**, so a refused create can always clean up its attachment.
13. **The people-row note is blank for an employee login**: the "Employee" chip says it, and a second word
    squeezed the chip (seen in the browser check).

**Browser check (not a deploy).** I ran the staged code on the clone (local-only, port 8099, tunnelled) with three
temporary logins and drove the Access screen in a headless Chrome: Employee chip on the list; employee passport
(switch, reason line, menu and roles wording, no "Give a role"); staff passport; the confirm modal; Make employee →
toast "… now has an employee login …" and the switch flips; Make staff → back; my own passport → Employee disabled
with "You cannot change your own account." Console: no errors from this screen (one pre-existing pb_learn warning).
The temporary logins are archived with scrambled passwords; the server is stopped.

### Finding about T1 (no change made)
An access manager who holds the access-team permission **as a direct group** (no role assignment), has an employee
record and no Pay Run on the menu is "portal only" under T1's rule and is bounced from the backend — my first
temporary manager login was. `_pb_holds_role` only sees role *assignments*. On live, access managers get the group
through roles, so this probably never bites; if it does, the fix is one more probe in the T1 rule (any group from
`MANAGE_GROUPS`, soft read), not a change here.

### Proposed ledger rows
| # | Gotcha / fact | How to apply |
|---|---|---|
| T16 | This platform's test runner (`odoo/tests/case.py` `_Outcome`) ignores `@unittest.expectedFailure`: the test is reported as a plain FAIL. | Pin a known failure as a PASSING check of today's behaviour, with a docstring saying when to flip it. |
| T17 | The odoo user cannot traverse `/home/ubuntu` on Payobook19v2, (`drwxr-x---`, odoo is not in the ubuntu group), so it cannot open `--logfile=/home/ubuntu/x.log`. | In the detached script, pass `--logfile=` (empty) and redirect stdout/stderr from the root shell into the `/home/ubuntu` log. |
| T18 | The live server's job runner connects to every database on the box, including a fresh throwaway copy: `dropdb t2demo` failed "being accessed by other users", and `createdb -T p0clone` can fail for the same reason. | Use `dropdb --force` for a throwaway; expect `createdb -T` to fail sometimes (Odoo then creates the database fresh — fine for a module's own suite). |
| T19 | biz_access is the product-agnostic layer: its copy audit (`test_access_generic` `TestNoProductNameInTheGenericLayer`) fails on "Payobook" (and "Odoo") in any JS/XML string or model message. | On the Access screen say "self-service pages", never the product name. |
| T20 | An employee login reaches `/web/content/ir.attachment/<id>` only with the attachment's `access_token` (`ir.attachment._can_return_content`), and om_hr_payroll's payslip URLs already carry the payslip's token (`get_portal_url`). | Tokened links for every user (one code path); the payslip page's own check is `_document_check_access`. |
| T21 | Stock `GET /web/login` while signed in, without `?redirect=`, renders the sign-in page; it does not send you anywhere. | Test the landing with a real form sign-in, or with `?redirect=`. |
| T22 | `_pb_holds_role` sees role assignments, not directly held groups: a direct-group access manager with an employee record is fenced by T1. | If it matters on a tenant, add a `MANAGE_GROUPS` probe to the rule (T1 file, one method). |

## 5. Self-review against the spec
**Scope**
1. The rule (`_pb_employee_only` share branch, `_pb_portal_only` share short-circuit, docstrings; `session_info` and `_login_redirect` unchanged): done.
2. pb_me_portal seams — profile (sudo create with explicit employee, sudo `_own_request`, comment replaced), documents (sudo creates after the guards, category check kept and tested, tokened downloads for everyone), payslips (`_get_payslips_domain`, sudo values, `_document_check_access`), tax sheet (test only), photos (route + `_photo_url` used in both places), home (test): done.
3. Workforce seams: done as specified — not fixed, proven (T2.9) and the T2b fix written out. pb_goals tested and passes. Neighbour pages smoke-tested (T2.10).
4. Access screen — `people()`, `_person_row`, `passport()` with `allow_share`, `_account_switch_preview`, `set_account_type` (manage gate, refusals, roles ended through the board's path or refused under a live route, loans revoked, portal/user group set, reconcile, audit, log line), UI chip / switch / reason / modal / employee wording / toast + reload: done. Deviated: the switch sits on its own row under the header (decision 9); two extra refusals (decision 3).
5. Joiners (`user_id` for a share account, `pb_portal_user_id` kept, docstring, no backfill): done.
6. Demo generator (new logins portal except the manager; existing logins keep their kind, with the comment; demo visitor group rule kept): done. Deviated: drivers stay full (decision 11).
7. Versions (`pb_me_portal` 19.0.3.0.0 + pin; biz_access, pb_zoho_bridge, pb_demo minor bumps; pb_me_portal_website unchanged): done.
8. Tests T2.1–T2.16: done. Deviated: T2.2's bare `/web/login` (ledger T21) and T2.9's decorator (ledger T16).

**Non-goals**
- No backfill of `user_id`; no flipping of live demo logins: done (untouched).
- No change to pb_ess_workforce, pb_goals, pb_timeoff, pb_pay, pb_onboarding, pb_training, pb_hiring, pb_offboarding, pb_pip, pb_rnr, pb_comp_ben, pb_probation, pb_driver_checkin, om_hr_payroll, pb_hr_payroll_base, hr, portal, website: done.
- No `/driver`, "Ask HR", "My requests", announcements: done.
- No new `base.group_portal` ACL or record rule: done — none was needed.
- No removal of `base.group_user`'s implied groups: done.
- No new stored field; no user-facing text with the vendor's name: done (one selection value added; copy audit green).

**Safety rails**: every sudo write in a `/my` route sits after the ownership guard and passes `employee_id`
explicitly; the photo route and the payslip override answer 404 / redirect for anything not the person's own (T2.5,
T2.6); `set_account_type` is manage-gated, decides every refusal before writing, runs in one transaction, never
touches password, login, active or companies; every run was on `p0clone` or a throwaway (`t2demo`, dropped).

**Side effects on the clone only**: `p0clone` now has pb_me_portal 19.0.3.0.0, biz_access 19.0.1.6.0 and
pb_zoho_bridge 19.0.1.2.0 installed; three archived temporary logins (`t2.ui.*@example.com`) and their audit rows
remain. Live service, port 8069 and the `payobook` database were not touched.

---

## T2b (Fable, 2026-10-15) — the follow-up, done in the same session
- `pb_ess_workforce/models/ess_workforce.py`: `request_fix` and `apply_leave` create under `sudo()` after
  `_require_own_employee` (T-R11); `apply_leave` checks the type against the company-scoped set `get_my_leave`
  offers before creating; both docstrings updated. `pb_ess_workforce` 19.0.1.0.1 → 19.0.1.1.0.
- `pb_me_portal/models/ess_landing.py`: fourth exclusion `_pb_holds_backend_group()` (ledger T22): any direct group
  outside `base.group_user`'s implied closure, minus `HARMLESS_GROUPS` (`base.group_multi_company`, the two
  pb_driver_checkin groups), keeps the backend. On payobook that un-fences tuan.quach (HR manager, no payroll) and
  diep.thai (budget viewer); ess2–10, employee.demo, minor.demo stay fenced. `pb_me_portal` 19.0.3.0.0 → 19.0.3.1.0
  (+ `test_06_font` pin).
- Tests: `test_t2_9_leave_apply_works_for_an_employee_login` (flipped: leave exists, `create_uid` = employee, not
  draft; a foreign-company type is refused), `test_t2_9c_timesheet_fix_works_for_an_employee_login` (draft
  correction, `create_uid` = employee), `test_t2b_a_permission_given_by_hand_keeps_the_backend`.
- Clone run (p0clone, `-u pb_me_portal,biz_access,pb_zoho_bridge,pb_demo,pb_ess_workforce`):
  ```
  biz_access: 212 tests · pb_ess_workforce: 105 tests · pb_me_portal: 103 tests · pb_me_portal_website: 6 tests · pb_zoho_bridge: 14 tests
  0 failed, 2 error(s) of 348 tests
  ```
  Errors: `TestPbMePortal.test_01` (M19, pre-existing) and `TestP8Badges.test_the_cockpit_renders_the_badge_behind_a_presence_guard`
  (reads `pb_schedule/static/src/xml/pb_schedule.xml` relative to the module's own path; pb_schedule is not in the
  `/tmp/deployMH` staging dir — a staging artefact, not a code failure). pb_demo is not installed on p0clone; its
  suite ran green on Opus's throwaway database.
