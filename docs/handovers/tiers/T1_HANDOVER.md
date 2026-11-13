# TIERS T1 — the fence: portal-only people cannot reach the backend (handover for Opus)

Read first: `TIERS_PROGRAM.md` (the finding, the strategy, every verified reference), `TIERS_LEDGER.md` (rules
T-R1…R9, rows T1–T8), then the files you extend: `pb_me_portal/models/ess_landing.py`,
`pb_me_portal/controllers/ess_landing.py`, `pb_me_portal/views/portal_templates.xml`, `pb_me_portal/__manifest__.py`,
`pb_me_portal/tests/`, and the module you clone: `biz_deroute_website/` (manifest, view, tests). Repo `CLAUDE.md`
rules apply (one addons dir; never "Odoo" in a user-visible string). You do not deploy; Fable does.

## What T1 is, in the owner's words
"A general employee should not have access to backend functionality." After T1, a person whose only work is
their own (no payroll, no hiring, no roles, no reports, nothing waiting for their decision) can no longer open
the backend: the address bounces them to My Payobook, and the two links that led there (the purple corner with
the nine dots on every portal page, and "Apps" in the account menu) are not drawn for them. Everyone else sees
exactly what they see today. This is a fence (ledger T8); T2 builds the wall.

## Scope (binding)
1. **The rule.** In `pb_me_portal/models/ess_landing.py`, on `res.users`:
   - `_pb_portal_only(self)` → bool. `ensure_one()`. Returns **True** iff `_pb_employee_only()` is True AND
     `_pb_holds_role()` is False AND `_pb_has_reports()` is False AND `_pb_has_open_seat()` is False. The whole
     body is inside `try/except Exception` → `_logger.warning(..., exc_info=True)` and **False** (T-R2).
   - `_pb_holds_role(self)`: `'pb.role.assignment' in self.env` and
     `self.env['pb.role.assignment'].sudo().search_count([('user_id','=',self.id),('active','=',True)], limit=1)`.
     False when the model is absent.
   - `_pb_has_reports(self)`: `self.env['hr.employee'].sudo().search_count([('parent_id.user_id','=',self.id)],
     limit=1)` (active employees only — the default domain already does that).
   - `_pb_has_open_seat(self)`: `self.env['biz.approval.request.seat'].sudo().search_count(['|',
     ('acting_user_id','=',self.id), ('user_id','=',self.id), ('status','=','open')], limit=1)`.
   - Three small helpers on purpose: tests patch one at a time. Docstring: who is excluded and why (T-R8).
   - `session_info`: also set `info['pb_portal_only'] = True` when the person is portal-only (harmless now;
     T2/T3 read it). Keep `pb_employee_only` exactly as is.
2. **The route.** In `pb_me_portal/controllers/ess_landing.py` (`EssLandingHome(Home)`):
   - module-level `_portal_only(uid)` → `request.env['res.users'].sudo().browse(uid)`; `user.exists() and
     user._pb_portal_only()`; inside `try/except` → False with a warning (T-R2).
   - `@http.route()` `def web_client(self, s_action=None, **kw)`: if `request.session.uid` and
     `_portal_only(request.session.uid)` → `return request.redirect('/my', 303)`; else `super()`.
     Bare decorator, no paths (ledger T2). Docstring says why (ancestors-first merge).
   - `@http.route()` `def index(self, s_action=None, db=None, **kw)`: same bounce, then `super()`.
   - `_login_redirect` unchanged.
3. **The Apps link.** In `pb_me_portal/views/portal_templates.xml`: template `portal_user_dropdown_portal_only`,
   `inherit_id="portal.user_dropdown"`, xpath `//a[@id='o_backend_user_dropdown_link']` position `attributes`:
   `<attribute name="t-if">not user_id._pb_portal_only()</attribute>`. Comment above it: what it hides, for whom,
   that biz_deroute_website patches the same anchor's href and both apply.
4. **The corner shortcut** — new module `pb_me_portal_website/` (clone `biz_deroute_website`'s shape):
   - `__manifest__.py`: name "Employee Self-Service Portal — website bridge", summary "Hides the backend shortcut
     on portal pages for portal-only employees", `depends: ['pb_me_portal', 'website']`, `auto_install: True`,
     `category: 'Hidden/Tools'`, `version: '19.0.1.0.0'`, `license: 'LGPL-3'`, `author: 'Payobook'`, data =
     `views/frontend_backend_nav.xml`. Description (engineering text): why a bridge (pb_me_portal must install
     without website; `website.layout` owns the shortcut), what it hides, that the route bounce is the real block.
   - `views/frontend_backend_nav.xml`: template `frontend_to_backend_nav_portal_only`, `inherit_id="website.layout"`,
     xpath `//div[hasclass('o_frontend_to_backend_nav')]` position `attributes`:
     `<attribute name="t-if">not user_id._pb_portal_only()</attribute>`.
   - `__init__.py` (empty besides the licence line), `tests/__init__.py`, `tests/test_portal_only_nav.py` (item 7).
5. **Version**: `pb_me_portal` → `19.0.2.2.0`; `test_06_font` pin → `19.0.2.2.0` (ledger T7).
6. **Docs in code**: update the module docstring at the top of `models/ess_landing.py` ("Three effects" → add the
   fourth: the fence, and name T-R8's exclusions). Keep every string an engineer reads technical; every string a
   person could see plain (there are none new — no new UI text in T1).
7. **Tests** (numbered; `pb_me_portal/tests/test_portal_only.py`, add to `tests/__init__.py`; and
   `pb_me_portal_website/tests/test_portal_only_nav.py`). Fixtures: `plain` = internal user + `hr.employee`
   (`user_id`), no other groups (clone `test_pb_me_portal.py:26-36`); `lead` = same + a second employee whose
   `parent_id` is plain's employee; `staff` = internal + `hr.group_hr_user` (+ payroll user group if present).
   - **T1.1** `plain._pb_portal_only()` is True and `plain._pb_employee_only()` is True.
   - **T1.2** `lead._pb_portal_only()` is False while `lead._pb_employee_only()` is True (landing unchanged).
   - **T1.3** with `_pb_has_open_seat` patched to return True, `plain._pb_portal_only()` is False. If creating a
     real `biz.approval.request` + step + seat with only required fields is straightforward, add T1.3b doing it
     for real (`status='open'`, `acting_user_id=plain`); otherwise say so in the report.
   - **T1.4** if `'pb.role.assignment' in env`: assign any active profile with abilities to `plain` through
     `env['pb.access']._assign_role(...)` or a direct sudo create with `_pb_access_internal` context — read
     `biz_access/models/role_assignments.py:46-62` and `:103-117` first; if neither is practical in a test,
     patch `_pb_holds_role` → True and say so. Expect False. Skip (with `skipTest`) when the model is absent.
   - **T1.5** admin (`base.user_admin`), a share user (`base.group_portal` only), and the public user: all False.
   - **T1.6** with `_pb_has_reports` patched to raise `RuntimeError`, `plain._pb_portal_only()` is False and
     `assertLogs('odoo.addons.pb_me_portal', level='WARNING')` catches one record (T-R2).
   - **T1.7** HttpCase (pin `dbfilter` as `biz_deroute_website/tests/test_frontend_nav.py:66-74`): give `plain`
     and `staff` passwords in `setUpClass`; `self.authenticate(login, pw)`; `self.url_open('/bizapp')` for plain
     → the final response URL path is `/my` (`allow_redirects` default); same for `/web` and `/`; for staff
     `url_open('/bizapp')` ends on `/bizapp` with status 200. If biz_deroute is not installed on the test DB,
     use `/odoo` in place of `/bizapp` (read `'biz_deroute' in env['ir.module.module']._installed()`).
   - **T1.8** HttpCase: plain `url_open('/my')` body contains neither `o_frontend_to_backend_nav` nor
     `o_backend_user_dropdown_link`; staff's body contains both. (Corner assertion lives in the glue module's
     test; the Apps-link assertion in pb_me_portal's. Skip the corner assertion in pb_me_portal if website is
     absent.)
   - **T1.9** arch: `env.ref('portal.user_dropdown').get_combined_arch()` → the anchor's `t-if` contains
     `_pb_portal_only`; glue module: `env.ref('website.layout').get_combined_arch()` → the nav div's `t-if`
     contains `_pb_portal_only` (clone `test_frontend_nav.py:40-58`).
   - **T1.10** the existing pb_me_portal suite (47 tests) and `biz_deroute_website`'s suite still pass; the
     pre-existing `TestPbMePortal.test_01` error (M19, approval engine) is not yours — name it in the report.
8. **Run everything on the clone** (ledger T-R9; `TIERS_PROGRAM.md` last bullet). Stage both modules into
   `/tmp/deployMH` on the server (`rsync -az --exclude=__pycache__ --exclude='*.pyc' pb_me_portal
   pb_me_portal_website ubuntu@payobook.com:/tmp/deployMH/` — the server alias and key are the ones the repo's
   deploy scripts use; see `docs/deploy/PENDING.md` and memory `payobook-deploy`), then run with `-u pb_me_portal
   -i pb_me_portal_website --test-tags /pb_me_portal,/pb_me_portal_website`. The log is the proof: paste the
   test summary lines into the report.

## Non-goals (do not do)
- No change to who lands where after sign-in (`_login_redirect`), to Home's tabs, to the app switcher, to
  pb_learn, to pb_zoho_sso (closed by construction, T-R7), to biz_deroute / biz_deroute_website (T-R3).
- No removal of `base.group_user`'s implied groups (approvals user, PayAI user) — T2 closes that by construction.
- No portal-account support yet (a share user is still "not an employee" to `_pb_employee_only`). That is T2.
- No new user-facing text. No deploy.

## Safety rails
- T-R2: the fence fails open; never raise out of `_pb_portal_only()` or `_portal_only()`.
- The bounce target is always the literal `/my` (never a user-supplied redirect).
- `search_count(..., limit=1)` on every probe; no recordset loads.
- The glue module must install on a database that already has pb_me_portal and website, and must not break
  `-u pb_me_portal` on a database without website (it simply is not installed there).

## Report back (write `docs/handovers/tiers/T1_REPORT.md`)
1. Files changed/added with one line each.
2. The numbered test results T1.1–T1.10 with the clone log's summary lines (module, tests run, failures,
   errors), and the M19 error named as pre-existing.
3. Anything you had to decide that the handover did not say, and any ledger row you propose (gotcha + how to
   apply) — Fable adds it to `TIERS_LEDGER.md`.
4. A self-review against the Scope and Non-goals: one line per item, "done" / "deviated: why".
