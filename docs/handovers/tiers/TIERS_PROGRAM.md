# TIERS — Employee (portal only) vs Staff (full account) — program doc

Owner brief (2026-10-15): "Explore if there is a role which only allows general employees to use the Employee
Self Service portal and no access to backend via the nine dots on top left corner. Ideally a general employee
should not have access to backend functionality rather features should be provided in portal itself eg entering
timesheet etc. … what is the strategy for staff and general employees. By general employees I mean just viewing
payslip, raising tickets, applying leaves and other activities like that."

Findings + proposal page: https://claude.ai/artifact/3epyMvtEBfm9VBLua1zepV — file copy
`docs/design/employee-access-strategy.html` (sections 1–7 + an engineers' appendix with file:line facts).

Owner decisions (2026-10-15, AskUserQuestion): **Two tiers, fence first**; **"Ask HR" tickets in scope for
Phase 3**; **phased workflow** (Fable designs, Opus builds in-session, Fable deploys payobook-first and walks).
Do not re-ask any of the three for this stream.

## The finding in one paragraph
There is no "portal only" role today. Every real employee login is a full (internal) account. The "nine dots on
the top left corner" the owner means is the website's fixed backend shortcut on every portal page
(`website.layout` → `o_frontend_to_backend_nav`, a `fa-th` icon, rendered for every `base.group_user`); the
"Apps" entry in the account dropdown (`portal.user_dropdown`) is the second door; typing `/bizapp` is the third.
`_pb_employee_only()` (pb_me_portal) only *lands* such a person on `/my`, prunes the backend app switcher to one
app and hides Home's Pulse tab — a courtesy, not a boundary. Joiners hired through Hiring / the connected HR
system already get a *portal* account automatically, but it is stored on `hr.employee.pb_portal_user_id`, never
`user_id`, so every `/my` page finds no employee for them.

## The strategy (what the product becomes)
| Tier | Account type | Lands on | Sees | How they get it |
|---|---|---|---|---|
| **Employee** (default for everyone paid) | **Portal** (`base.group_portal`, share user) | `/my` | My Payobook only. Cannot load `/bizapp` at all (stock: share users are bounced by `portal`'s `web_client`). | Default on hire; the Access screen's People lens switch "Employee (portal only)". |
| **Team lead** | Full, roles: approvals / lifecycle-team only | `/my` | My Payobook + backend Home (Approvals, Wall, Announce). | Promoted on the Access screen. Later (optional): a "My team" portal page lets most of them be Employees too. |
| **Staff** (HR, payroll, finance, recruiters, admins) | Full, role bundles | Payroll dashboard / Home as today | Everything their roles allow; also their own `/my`. Switch via the corner shortcut (Gusto pattern). | As today. |

## Phases
| Phase | Agent | Scope (binding non-goals in the handover) | Size |
|---|---|---|---|
| **T1 Fence** | Opus | One server rule `_pb_portal_only()`; `/bizapp` `/web` `/` bounce to `/my` for those people; the corner shortcut and the Apps link not rendered for them; HttpCase proof; version bump. **pb_me_portal + a new auto-install glue module `pb_me_portal_website` only.** | days |
| **T2 Portal accounts** | Opus | Make every `/my` page work for a share user (5 write seams: profile change request, document upload + attachment, payslip list, timesheet fix, leave apply; the home's employee look; employee lookup falling back to `pb_portal_user_id` or copying it into `user_id`); "Employee / Staff" switch on the Access screen with promote/demote (roles stripped on demote); new hires default to Employee; demo employee logins become portal accounts. The two auto-rights (`group_approval_user`, `group_payai_user`, implied by `base.group_user`) stop reaching employees **by construction** — nothing in other modules is edited. | ~1 week |
| **T3 Employee features** | Opus | "Ask HR" tickets (new model, portal form, HR queue, portal thread, states New / With HR / Answered / Closed, approvals engine for sign-offs); "My requests" (one list across leave, fixes, profile changes, tickets, assets, resignation); clock in/out on the portal for every Employee (today `/driver` needs a full account); Announcements on the portal home. | 1–2 weeks |
| **T4 Switch-over** | Fable | Convert existing employee-only full accounts to portal accounts per tenant with a rollback list; deploy batch. Expenses / business trips / timesheet entry follow as small phases on demand. | days |

## Status
- **T1 LIVE on payobook 2026-10-15** (pb_me_portal 19.0.2.2.0, pb_me_portal_website 19.0.1.0.0; report
  `T1_REPORT.md`; live walk: ess2.demo bounced + links gone; ess1/ess5 are team leads in the demo data, ledger T13).
- **T2 built 2026-10-15** (`T2_HANDOVER.md`, `T2_REPORT.md`): decisions D1–D6; pb_me_portal 19.0.3.1.0,
  biz_access 19.0.1.6.0, pb_zoho_bridge 19.0.1.2.0, pb_demo 19.0.1.13.0, pb_ess_workforce 19.0.1.1.0 (T2b by Fable:
  the two workforce writes under sudo + the hand-given-permission exclusion, ledger T22). Deployed payobook-first
  2026-10-15; live walk = flip ess2.demo to Employee through the new switch.
- **T3 next**: Ask HR, My requests, clock in/out on the portal, announcements; plus the "Left for T3" list in
  `T2_REPORT.md` §3 (colleague photos, tokenless downloads, write buttons of the neighbour pages).

## Verified plumbing (do not re-derive; line numbers checked 2026-10-15)
- Rule: `pb_me_portal/models/ess_landing.py:36-57` `_pb_employee_only()` (internal, not admin/system, an
  `hr.employee` with `user_id` = user, Pay Run sidebar item not visible, `pb.hiring.can_open()` false).
  `session_info` override `:63-77` sets `home_action_id` + `pb_employee_only`.
- Landing: `pb_me_portal/controllers/ess_landing.py:17-31` `_login_redirect` → `/my` when the destination is one
  of `'', '/', '/odoo', '/bizapp', '/web'`.
- Web client routes: stock `web/controllers/home.py:46-83` (`/web`, `/odoo`, `/odoo/<path>`, `/scoped_app/<path>`;
  `auth='none'`; bounces non-internal to `/web/login_successful`, which `portal/controllers/web.py:23-27`
  turns into `/my`). biz_deroute re-declares the paths as `/web`, `/bizapp`, `/bizapp/<path>`, `/scoped_app/<path>`
  (`biz_deroute/controllers/home.py:35-40`) and 301s `/odoo[/…]` → `/bizapp` (`:42-51`).
- Route merging: `odoo/http.py:915-933` — ancestors first, `merged_routing.update(submethod.original_routing)`;
  a bare `@http.route()` override keeps whatever paths the explicit declarations set, in any module order.
- Corner shortcut: `website/views/website_templates.xml:289-305` (inside `website.layout`, which inherits
  `portal.frontend_layout`); shown by `website/static/src/js/content/redirect.js:9-19` unless
  `session.is_website_user`. `user_id` (a `res.users` record) is in that template's scope (`:339` uses it).
- Apps link: `portal/views/portal_templates.xml:113` `a#o_backend_user_dropdown_link` `groups="base.group_user"`;
  `biz_deroute_website/views/frontend_backend_nav.xml:34-41` already patches its `href` (attributes position —
  a second attributes patch on the same node is fine).
- QWeb may call underscore methods on records: stock `portal.user_dropdown:100` calls `user_id._is_public()`.
- Roles: `biz_access/models/role_assignments.py:13-29` `pb.role.assignment` (`user_id`, `profile_id`,
  `active`); `:39-40` a share user can never hold one. pb_me_portal does NOT depend on biz_access → soft read.
- Direct reports: `hr.employee.parent_id` / `child_ids` (`hr/models/hr_employee.py:195-197`).
- Approval seats: `biz_approval_workflow/models/request.py:158-176` `biz.approval.request.seat`
  (`user_id` "Whose seat", `acting_user_id` "Decides it", `status` with `'open'` = waiting). pb_me_portal
  depends on biz_approval_workflow (hard read OK).
- Glue-module precedent: `biz_deroute_website` (`__manifest__.py`: depends `[biz_deroute, website]`,
  `auto_install: True`, one view, tests `tests/test_frontend_nav.py` with the combined-arch check and the
  HttpCase `dbfilter` pin at `:66-74`).
- SSO: `pb_zoho_sso/controllers/main.py:299-301` skips `_login_redirect` and lands on `/bizapp` — closed by
  construction once `/bizapp` itself bounces (no change to pb_zoho_sso).
- Version pin: `pb_me_portal/tests/test_me_home_cards.py` `test_06_font` asserts the manifest version
  (`'19.0.2.1.1'` today) — bump both together.
- Tests on the clone (ledger M31): `--addons-path=/tmp/deployMH,/odoo/odoo-server/addons --http-port=8099
  --db-filter='^p0clone$' --workers=0 --max-cron-threads=0 -u <modules> --test-enable --test-tags
  /<module> --stop-after-init --logfile=…`. Known pre-existing error `TestPbMePortal.test_01` (M19).
