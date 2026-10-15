# TIERS — conventions & gotcha ledger

Every handover in this program references this file. Add a row whenever a new gotcha is hit.
Program doc: `TIERS_PROGRAM.md`. Findings page: https://claude.ai/artifact/3epyMvtEBfm9VBLua1zepV
(file copy `docs/design/employee-access-strategy.html`).

## Standing rules (bind every phase)
- **T-R1 One rule, every door asks it.** Who is "portal only" is decided by ONE server method on `res.users`
  (`_pb_portal_only()`, pb_me_portal). The web-client route, the `/` route, the corner shortcut, the Apps link,
  the sign-in landing and (later) the Access screen all call it. No door re-derives the rule in its own words.
- **T-R2 The fence fails open.** A rule error must never lock a person out of their work: `_pb_portal_only()`
  catches everything, logs a warning with the trace, and returns False. T2's portal accounts are the real wall.
- **T-R3 Other modules stay untouched in T1.** Only `pb_me_portal` and the new glue module `pb_me_portal_website`
  change. Never edit biz_deroute, biz_deroute_website, website, portal, pb_zoho_sso, biz_approval_workflow,
  biz_access, pb_dashboard, pb_home_hub, pb_learn for this phase. (T2 may touch biz_access's People lens and the
  five `/my` write seams; the handover names each file.)
- **T-R4 Never the vendor's name in a user-visible string** (module `name`/`summary` show in the Apps list;
  QWeb text; error text; `.po` msgstr). Technical identifiers, comments, docs keep it.
- **T-R5 Plain English to the owner; engineering words in docs, commits and comments only.**
- **T-R6 Proof is HTTP + browser.** Every door has an HttpCase that signs in as a portal-only employee and as a
  member of staff and asserts the response (final URL, presence/absence of the markup). Fable walks payobook.com
  after deploy in the owner's session. A phase never reports a door as closed without the HttpCase.
- **T-R7 A door closes by construction before it closes by code.** Prefer "a share user cannot load the web
  client" (stock) over a new check; prefer "the route bounces, so the SSO landing bounces" over editing the SSO.
- **T-R8 Team leads keep the backend in T1.** A person with an active role assignment, a direct report, or an
  open approval seat is never portal-only, whatever else is true. Approvals live on the backend Home until T3.
- **T-R9 Every test runs on the clone with the M31 command** (`TIERS_PROGRAM.md`, last bullet). A version bump
  updates `test_06_font`'s pin in the same commit.
- **T-R10 One link: `hr.employee.user_id` is the employee's login, internal or portal.** No `/my` page, helper or
  record rule reads `pb_portal_user_id`; the joiner pipeline sets `user_id` too. (T2 D1.)
- **T-R11 A portal seam is `sudo()` after an explicit ownership guard**, never a new `base.group_portal` ACL or
  rule. The guard is "the record's employee is `_ess_employee()`". `sudo()` keeps `env.user`, so the submitter
  stays the employee. (T2 D2.)
- **T-R12 Demotion to Employee is refused, never forced**, while the person has a direct report, an open approval
  seat, admin rights, or active roles under a live roles-approval route. Roles end through the board's own removal
  path with audit rows. (T2 D4.)

## Ledger
| # | Date | Gotcha / fact | How to apply |
|---|---|---|---|
| T1 | 2026-10-15 | The owner's "nine dots on the top left corner" is the website's fixed backend shortcut on portal pages (`o_frontend_to_backend_nav`, `fa-th`), rendered for every `base.group_user` — a plain employee sees it. The backend's own app switcher is already hidden for them (one app). | T1 stops rendering that div (and the Apps link) for portal-only people server-side; JS-only hiding is not enough (the stock `redirect.js` re-shows it). |
| T2 | 2026-10-15 | Route overrides merge ancestors-first with `dict.update`; a bare `@http.route()` keeps biz_deroute's `/bizapp` paths whatever the module order (`odoo/http.py:915-933`). pb_me_portal does not depend on biz_deroute and must not. | Override `web_client` and `index` in `EssLandingHome` with bare `@http.route()`; never restate paths. |
| T3 | 2026-10-15 | `web_client` is `auth='none'`: `request.env.user` is not the session user there. | Read the person as `request.env['res.users'].sudo().browse(request.session.uid)` (+ `.exists()`), as `_login_redirect` already does. |
| T4 | 2026-10-15 | `website.layout` cannot be inherited from pb_me_portal (no `website` dependency, and pb_me_portal must stay installable without it). | The corner-shortcut inherit lives in the auto-install glue module `pb_me_portal_website` (clone of `biz_deroute_website`). The Apps-link inherit (`portal.user_dropdown`) lives in pb_me_portal (depends on portal). |
| T5 | 2026-10-15 | QWeb lets a template call an underscore method on a record (`user_id._is_public()` in stock portal). | `t-if="not user_id._pb_portal_only()"` is legal; the method is exception-safe (T-R2) so a template can never 500 on it. |
| T6 | 2026-10-15 | HttpCase on this platform: `dbfilter = %h` routes by host, so localhost matches no DB. | Pin `config['dbfilter']` to the test DB in `setUpClass` exactly as `biz_deroute_website/tests/test_frontend_nav.py:66-74` does. |
| T7 | 2026-10-15 | `test_06_font` pins the manifest version string. | Bump to `19.0.2.2.0` in both places. |
| T8 | 2026-10-15 | Hidden menus hide buttons, not data: a full account keeps every `base.group_user` ACL and the JSON-RPC endpoints. | T1 is a fence (documented as such in the findings page); do not claim otherwise in the report. T2 removes the group. |
| T9 | 2026-10-15 | `ir.http.session_info()` cannot be called from a TransactionCase on this platform: several overrides (biz_theme, pb_tenancy, biz_deroute's session guard…) read `request`. | Assert session_info keys in an HttpCase via `self.make_jsonrpc_request('/web/session/get_session_info')` after `authenticate`. |
| T10 | 2026-10-15 | An `index` override in a `web.Home` subclass that does not depend on website still runs before `website.Website.index`: the combined controller orders leaves depth-first (`odoo/http.py:862-901`) and website's subtree hangs under `portal.Home`, created first. | A bare `@http.route()` `index` override in pb_me_portal is enough to bounce `/` on website databases too. Do not add a website dependency for it. |
| T11 | 2026-10-15 | Post-install tests of a module run only when that module is in the `-u`/`-i` set. `--test-tags /biz_deroute_website` with only `-u pb_me_portal` ran 0 tests. | To re-run a neighbour's suite on the clone, add it to `-u` (e.g. `-u pb_me_portal,biz_deroute_website`). |
| T12 | 2026-10-15 | The fence is evaluated up to 3× per frontend page for signed-in internal users (Apps link desktop + mobile, corner shortcut); each call short-circuits at `_pb_employee_only` (a few queries). | Fine for T1. If T2/T3 add more doors on hot pages, memoise per request rather than re-deriving (T-R1 still: one method). |
| T13 | 2026-10-15 | On payobook the demo logins ess1.demo and ess5.demo have direct reports (1 and 5) in the demo data, so the fence rightly keeps their backend; ess2–4, 6–10, employee.demo, minor.demo are plain. | Demo the fence (and T2's Employee tier) with ess2.demo; ess1/ess5 show the team-lead tier. Do not re-parent demo data to "fix" this. |
| T14 | 2026-10-15 | Share users get no `/web/image/hr.employee*` and no `/web/content/ir.attachment` (no ACL): images fall back to the placeholder, downloads 403. | T2: one sudo photo route (`/my/photo/<id>/<size>`, own employee only) and tokened attachment URLs (`generate_access_token`), used for every user — one code path. |
| T15 | 2026-10-15 | om_hr_payroll's portal controller searches `hr.employee` as the request user (`om_hr_payroll/controllers/portal.py:30`) and payslips behind `check_access_rights`: a share user gets an AccessError / an empty list. | pb_me_portal's own `/my/payslips` route searches under sudo from `_ess_employee()`; `_document_check_access` override returns the sudo payslip when it is the person's own. |
| T16 | 2026-10-15 | This platform's test runner (`odoo/tests/case.py` `_Outcome`) ignores `@unittest.expectedFailure`: the test is reported as a plain FAIL. | Pin a known failure as a PASSING check of today's behaviour, with a docstring saying when to flip it. |
| T17 | 2026-10-15 | The odoo user cannot traverse `/home/ubuntu` on Payobook19v2 (`drwxr-x---`), so it cannot open `--logfile=/home/ubuntu/x.log`. | In the detached script pass `--logfile=` (empty) and redirect stdout/stderr from the root shell into the `/home/ubuntu` log. |
| T18 | 2026-10-15 | The live job runner connects to every database on the box, including a fresh throwaway copy: `dropdb` fails "being accessed by other users", `createdb -T p0clone` can fail the same way. | `dropdb --force` for a throwaway; expect `createdb -T` to fail sometimes. |
| T19 | 2026-10-15 | biz_access is the product-agnostic layer: its copy audit (`test_access_generic`) fails on "Payobook" (and "Odoo") in any JS/XML string or model message. | On the Access screen say "self-service pages", never the product name. |
| T20 | 2026-10-15 | An employee login reaches `/web/content/ir.attachment/<id>` only with the attachment's `access_token`; om_hr_payroll's payslip URLs already carry the payslip's token (`get_portal_url`). | Tokened links for every user (one code path); the payslip page's own check is `_document_check_access`. |
| T21 | 2026-10-15 | Stock `GET /web/login` while signed in, without `?redirect=`, renders the sign-in page. | Test the landing with a real form sign-in, or with `?redirect=`. |
| T22 | 2026-10-15 | `_pb_holds_role` sees role assignments, not directly held groups: on payobook an HR manager without payroll (tuan.quach, 11 direct groups), a budget viewer (diep.thai) and a direct-group access manager with an employee record were fenced by T1. | T2b adds the fourth exclusion `_pb_holds_backend_group()`: any direct group outside `base.group_user`'s implied closure, minus a harmless allowlist (`base.group_multi_company`, the two pb_driver_checkin groups). The landing rule `_pb_employee_only` is unchanged. |
| T23 | 2026-10-15 | A live upgrade launched 4 s after `service odoo-server stop` died with `LockNotAvailable: canceling statement due to lock timeout` (pb_demo init, `CREATE INDEX` on `hr_salary_rule`): the stopping server still held the table. `EXIT=255` with an empty stdout log — the cause is only in `/var/log/odoo/odoo-server.log`. | After `stop`, wait until `ps -eo cmd \| grep '[o]doo-bin'` is empty and `pg_stat_activity` has no session on the database, then launch. On a lock timeout, check both and simply re-run. |
| T24 | 2026-10-15 | libsass evaluates a bare CSS `min()`/`max()` with mixed units (`min(78%, 620px)`) and fails: the WHOLE `web.assets_frontend` bundle falls back to "A css error occurred" while tests stay green. | Write `unquote("min(78%, 620px)")`. After any SCSS change load one page and check the bundle has no `css_error_message`. |
| T25 | 2026-10-15 | QWeb drops an element whose `t-out` value is empty: `<textarea t-out="text"/>` with `text=None` renders nothing. | Put the value in a body: `<textarea …><t t-out="text or ''"/></textarea>`; assert form fields exist in the HttpCase. |
| T26 | 2026-10-15 | With two browser contexts in one headless Chrome the background one never renders the backend (OWL waits on animation frames), even after `Page.bringToFront`. | Drive the backend walk in its own browser instance. |
| T27 | 2026-10-15 | The left rail is a closed spec: a new `pb.sidebar.item` must also be added to `TARGET_RAIL` and the match tables in `pb_sidebar/tests/test_ia_c5.py`, with an icon from the closed set in `pb_sidebar.js`. The People section is retired (an item there never shows). | One data record plus three table lines; never a new icon name without editing `pb_sidebar.js`. Adding a rail item is an IA decision for the owner (rail 38→8 ruling). |
| T28 | 2026-10-15 | `formatted_read_group` honours `group_expand` only with the context key `read_group_expand=True`. | Set it when a test asserts kanban columns. |
| T29 | 2026-10-15 | A QWeb attribute expression `'--x: %g%%' % v` 500s the page with `ValueError: incomplete format`. | Write `'--x: %g' % v + '%'` (the MEHOME bars already do). |
| T30 | 2026-10-15 | Every website page carries the language switcher, which links to the CURRENT URL: "page X has no link to X" is always false. | Assert on the component's own markup (`<span>Clock</span>`, a class), never on a bare `href`. |
| T31 | 2026-10-15 | p0clone's `base.user_admin` is archived: pb_timeoff `TestTimeoff.test_03/test_05` error "Your account is no longer in use" there. | Known clone-data errors; do not chase them in a phase run. |
| T32 | 2026-10-15 | Suites that read a neighbour's files by path (pb_pay static contract → pb_import_kit, TestP8Badges → pb_schedule) fail when the neighbour is not staged. | Stage `pb_import_kit` and `pb_schedule` (unedited, hash-checked) in `/tmp/deployMH`. |
| T33 | 2026-10-15 | Signing in from a headless browser sets the user's timezone to the browser's (the walk login became Australia/Sydney). | Read times in a walk in the browser's zone, or set the tz after the first sign-in. |
| T34 | 2026-10-15 | Stock keeps punch location / IP / browser only when the company's "Device & Location Tracking" is on (default off). | The portal clock follows the same switch; tests turn it on to see coordinates. |
