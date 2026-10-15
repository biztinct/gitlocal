# TIERS T1 — the fence — implementation report (Opus)

Handover: `T1_HANDOVER.md`. Ledger: `TIERS_LEDGER.md`. Not committed, not deployed.
Clone runs: `p0clone`, port 8099, staged from `/tmp/deployMH` (final run 2026-10-14 22:02 server time).

## 1. Files changed / added
| File | What |
|---|---|
| `pb_me_portal/models/ess_landing.py` | Module docstring "Three effects" → four (the fence, the T-R8 exclusions, fence-not-wall, fails open). New `res.users._pb_portal_only()` (whole body in try/except → warning + False) and the three probes `_pb_holds_role` (soft read of `pb.role.assignment`), `_pb_has_reports`, `_pb_has_open_seat` (all `search_count(..., limit=1)`, sudo). `session_info` also sets `pb_portal_only = True` inside the existing employee-only branch; `pb_employee_only` unchanged. |
| `pb_me_portal/controllers/ess_landing.py` | Module-level `_portal_only(uid)` (no uid / no `request.db` → False; try/except → warning + False). `EssLandingHome.web_client` and `.index` with bare `@http.route()` bounce a portal-only session to the literal `/my` (303), else `super()`. `_login_redirect` untouched. |
| `pb_me_portal/views/portal_templates.xml` | New `portal_user_dropdown_portal_only` (inherits `portal.user_dropdown`, attributes patch `t-if="not user_id._pb_portal_only()"` on `a#o_backend_user_dropdown_link`), with the comment the handover asked for. |
| `pb_me_portal/__manifest__.py` | Version `19.0.2.1.1` → `19.0.2.2.0`. |
| `pb_me_portal/tests/test_me_home_cards.py` | `test_06_font` pin → `19.0.2.2.0` (ledger T7). |
| `pb_me_portal/tests/test_portal_only.py` (new) | T1.1–T1.9 (rule, route, Apps link, arch). |
| `pb_me_portal/tests/__init__.py` | Imports `test_portal_only`. |
| `pb_me_portal_website/__init__.py` (new) | Licence line only. |
| `pb_me_portal_website/__manifest__.py` (new) | Name "Employee Self-Service Portal — website bridge", the exact summary, depends `['pb_me_portal', 'website']`, auto_install, Hidden/Tools, 19.0.1.0.0, LGPL-3, author Payobook. The engineering description covers why it is a bridge, what it hides, and that the route bounce is the real block. |
| `pb_me_portal_website/views/frontend_backend_nav.xml` (new) | `frontend_to_backend_nav_portal_only` (inherits `website.layout`, attributes patch `t-if="not user_id._pb_portal_only()"` on `div.o_frontend_to_backend_nav`). |
| `pb_me_portal_website/tests/__init__.py`, `tests/test_portal_only_nav.py` (new) | T1.8 corner half (HttpCase), T1.9 corner half (combined arch). |

No other module touched (T-R3). No new user-visible text; no "Odoo" in any new name, summary, description or template.

## 2. Test results (clone log)
```
odoo.tests.stats: pb_me_portal: 80 tests 18.71s 13266 queries
odoo.tests.stats: pb_me_portal_website: 6 tests 1.64s 820 queries
odoo.tests.result: 0 failed, 1 error(s) of 62 tests when loading database 'p0clone'
ERROR: TestPbMePortal.test_01_profile_change_flow_and_audit      <- pre-existing M19 (approval engine AccessError), not T1

odoo.tests.stats: biz_deroute_website: 9 tests 1.57s 487 queries
odoo.tests.result: 0 failed, 0 error(s) of 5 tests when loading database 'p0clone'
```
62 = the 47 existing pb_me_portal tests + 13 new in pb_me_portal + 2 in the glue module. No test was skipped (Odoo logs every skip as `skipped …`, and the log has none from these suites). The one error is M19 (`odoo.exceptions.AccessError: Uh-oh! Looks like you have stumbled upon some top-secret records.`).

| # | Test(s) | Result |
|---|---|---|
| T1.1 | `TestPortalOnlyRule.test_t1_1_plain_employee_is_portal_only` | pass. plain is employee-only and portal-only. |
| T1.2 | `test_t1_2_team_lead_keeps_the_backend` (+ `test_t1_2b_staff_is_not_portal_only`) | pass. lead: employee-only True, has reports, portal-only False. staff: False. |
| T1.3 | `test_t1_3_open_seat_keeps_the_backend` (patched) | pass |
| T1.3b | `test_t1_3b_real_open_seat_keeps_the_backend` | pass, done for real: a `biz.approval.process` + request + step + seat (`acting_user_id=plain`, `status='open'`) → False. Moving the seat to a non-open status → True again. |
| T1.4 | `test_t1_4_role_holder_keeps_the_backend` | pass, real assignment, no patch. Direct sudo create with `_pb_access_internal=INTERNAL` on the first active profile with abilities whose closure has no forbidden group (68 active profiles on p0clone). `_pb_employee_only` stays True, `_pb_holds_role` is True, portal-only is False. Skips when biz_access is absent. |
| T1.5 | `test_t1_5_admin_share_and_public_are_not_portal_only` | pass (admin, a `base.group_portal` share user, the public user) |
| T1.6 | `test_t1_6_the_rule_fails_open` | pass. `_pb_has_reports` raises `RuntimeError` → False; exactly one WARNING on `odoo.addons.pb_me_portal`. |
| T1.6b (extra) | `TestPortalOnlyDoors.test_t1_6b_session_info_flag` | pass. `/web/session/get_session_info`: plain has `pb_employee_only` and `pb_portal_only`; lead has `pb_employee_only` only. |
| T1.7 | `test_t1_7_portal_only_person_is_bounced_to_my`, `test_t1_7b_staff_and_team_lead_open_the_backend` | pass. biz_deroute is installed, so the door is `/bizapp`. Werkzeug log: `GET /bizapp 303`, `GET /web 303`, `GET / 303`, each → `GET /my 200`. Staff and lead: `/bizapp` 200, final path `/bizapp`. |
| T1.8 | `test_t1_8_apps_link_only_for_staff` (pb_me_portal), `TestCornerShortcutPage.test_t1_8_corner_shortcut_only_for_staff` (glue) | pass. plain's `/my` has neither `o_backend_user_dropdown_link` nor `o_frontend_to_backend_nav`; staff's has both. |
| T1.9 | `test_t1_9_apps_link_inherit_reaches_the_combined_arch`, `TestCornerShortcutArch.test_t1_9_the_inherit_reaches_the_combined_arch` | pass. Both combined-arch nodes carry a `t-if` containing `_pb_portal_only`. |
| T1.10 | existing suites | pass, except the pre-existing M19 `TestPbMePortal.test_01`. biz_deroute_website: 5/5. |

Side effect on the clone only: `p0clone` now has `pb_me_portal` 19.0.2.2.0 and `pb_me_portal_website` installed, and `biz_deroute_website` was re-updated (same code as live). Live service, port 8069 and the `payobook` database were not touched.

## 3. Decisions the handover did not make
1. **`/` on a website database.** Website's `index` serves the homepage and never calls `super()`. The bounce still runs because of how controllers are combined (`odoo/http.py:862-901`): leaf classes are collected depth-first over `web.Home.__subclasses__()`, and the tuple is reversed, so a later leaf is earlier in the MRO. `EssLandingHome` is a direct subclass of `web.Home` created after `portal.Home`, so it always lands after website's subtree (which hangs under `portal.Home`). Its `index` therefore runs before `Website.index`, whatever order pb_me_portal and website load in. T1.7's `GET / 303 → /my` proves it. The bare decorator keeps website's `auth='public', website=True` routing.
2. **`_portal_only` checks `request.db` first**, so a database-less request (the db selector) returns False quietly instead of logging a warning on every hit.
3. **`ensure_one()` sits inside the try**, so even a multi-record call fails open (T-R2 wording: "never raise").
4. **The session_info check is an HttpCase** (`/web/session/get_session_info`). My first version called `ir.http.session_info()` from a TransactionCase and errored, because session_info needs a live request (other modules' overrides read `request`).
5. **A real seat for T1.3b** needs only `biz.approval.process(key, name)`, a request (title, process, company, res_model, res_id), a step (request, key) and a seat (step, key, acting_user_id). Tracking is disabled in the test context.
6. **Bounce is checked before the stock session-token check** in `web_client`. A stale session then lands on `/my` (`auth='user'`), which sends the person to sign-in anyway. The target is always the literal `/my`; `?redirect=` is ignored for these people.

## 4. Proposed ledger rows
| # | Gotcha / fact | How to apply |
|---|---|---|
| T9 | `ir.http.session_info()` cannot be called from a TransactionCase on this platform: several overrides (biz_theme, pb_tenancy, biz_deroute's session guard…) read `request`. | Assert session_info keys in an HttpCase via `self.make_jsonrpc_request('/web/session/get_session_info')` after `authenticate`. |
| T10 | Overriding `index` in a `web.Home` subclass that does not depend on website still runs before `website.Website.index`. The combined controller orders leaves depth-first, and website's subtree hangs under `portal.Home`, which is created first. | A bare `@http.route()` `index` override in pb_me_portal is enough to bounce `/` even on website databases. Do not add a website dependency for it. |
| T11 | Post-install tests of a module run only when that module is in the `-u`/`-i` set. `--test-tags /biz_deroute_website` with only `-u pb_me_portal` ran 0 tests. | To re-run a neighbour's suite on the clone, add it to `-u` (e.g. `-u pb_me_portal,biz_deroute_website`). |
| T12 | The fence is evaluated up to 3× per frontend page for signed-in internal users (Apps link desktop + mobile, corner shortcut). Each call short-circuits at `_pb_employee_only`, which costs a few queries (sidebar Pay Run rule). | Fine for T1. If T2/T3 add more doors on hot pages, memoise per request rather than re-deriving (T-R1 still: one method). |

## 5. Self-review against the spec
**Scope**
1. The rule (`_pb_portal_only` + three helpers, fail-open, docstring, `session_info` flag): done.
2. The route (`_portal_only`, bare-route `web_client` and `index` bounce to `/my`, `_login_redirect` unchanged): done.
3. The Apps link (`portal_user_dropdown_portal_only` with comment): done.
4. The corner shortcut (new `pb_me_portal_website`: manifest, view, `__init__`, tests): done.
5. Version `19.0.2.2.0` + `test_06_font` pin: done.
6. Docs in code (module docstring: fourth effect + T-R8 exclusions; no new UI text): done.
7. Tests T1.1–T1.10 (T1.3b and T1.4 for real; T1.6b added): done.
8. Run on the clone with the M31 command: done (log lines above). Staged via the `Payobook19v2` alias as instructed.

**Non-goals**
- No change to `_login_redirect`, Home's tabs, the app switcher, pb_learn, pb_zoho_sso, biz_deroute or biz_deroute_website: done (untouched).
- No removal of `base.group_user`'s implied groups: done (untouched).
- No portal-account (share user) support: done (a share user is still not employee-only, so not portal-only; T1.5).
- No new user-facing text, no deploy: done.

**Safety rails**: fails open in both the rule and the route helper (T1.6); bounce target is the literal `/my`; every probe is a `search_count(..., limit=1)`. The glue module installed cleanly on p0clone (`-i`). On a database without website it is simply not auto-installed, and pb_me_portal has no website reference.

**Honest framing (ledger T8)**: this is a fence. A portal-only person still holds every `base.group_user` ACL and can call the JSON-RPC endpoints; only the web client, `/` and the two links are closed. T2 removes the group.
