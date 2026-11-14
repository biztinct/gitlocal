# WDGAP QF3 — report: leave on My Payobook (half days, withdraw, certificate, balance after)

Implemented, tested and self-reviewed by the Opus implementation agent on 2026-11-14, branch
`wdgap-qf3` (from `origin/19.1` at `1065e98bf`). **Not deployed, not merged.**

## 1. What was built

| Scope item | What the employee / approver gets | Where |
|---|---|---|
| 1 Half days and hours | Kind counted in half days: "The day: Full day / Morning / Afternoon" (one day); "First day: Full day / Afternoon" + "Last day: Full day / Morning only" (several days). Kind counted in hours: From / To times, one day. Whole-day kinds: the form as before. The unit is the kind's (`request_unit`), never a per-request choice; no kind's unit was changed. | `pb_ess_workforce/models/ess_workforce.py` `_leave_vals`, template `portal_my_work_leave`, `static/src/interactions/leave_form.js` |
| 2 Withdraw | "Withdraw" on own rows waiting for approval (`confirm`/`validate1`) that have not started. The open approval is withdrawn through the engine (`biz.approval.engine.sudo().cancel` in a savepoint, cloned from expenses); the leave ends `cancel` (kept, not deleted). No leave route → the leave is cancelled directly. | `withdraw_leave`; `pb_timeoff/models/hr_leave_approval.py` `_approval_withdraw`, `_pb_cancel_pending` |
| 3 Cancel an approved leave | "Cancel" (a fold-out with a required reason) on own approved rows whose first day is after today. hr_holidays' own `_action_user_cancel(reason)`: the manager is told by the leave's normal message. Any open request is withdrawn first. Helper text: "To change a request, withdraw or cancel it and ask again." | `cancel_leave` |
| 4 Documents | Two inputs on the form (Choose a file / Take a photo, `capture="environment"`), and "Add a document" on own rows that are waiting or approved. Bound to the leave (`res_model='hr.leave'`), so the Leave Command Center's papers show them. A kind with "Supporting document" makes the block prominent with "A document is needed for this kind of leave"; otherwise "Add a document (optional)". Sending is never blocked. Files open from tokened links. | `_check_leave_files`, `_attach_leave_files`, `add_leave_document`, template `leave_doc_inputs` |
| 5 "After this request" | Live line under the form: "This request: Half a day / 3 hours / 2 days" and "After this request: 9.5 days left" (`virtual_remaining_leaves` − this request, read-only `new()` record, `POST /my/work/leave/preview`). Below zero: a calm amber line (see deviation D1). Balance tiles gain a quiet "N days waiting for approval". | `preview_leave`, `get_my_leave` |
| 6 Approver sees it | Manager area on /my (one approval): "Half day, afternoon" / hours next to the dates, "Half a day" / "N hours" as the length, the files as tokened links. Approvals inbox: the leave adapter's drawer chips "Part of the day: Half day, morning" and "Documents: 1 document attached"; the card count says "Half a day" / "1.5 hours". | `pb_me_team/models/pb_me_team.py` `_leave_context`, template; `pb_timeoff` `_approval_detail`, `_approval_card_count` |

Also: R5 readers — the attendance exceptions no longer hide a missing punch behind a half day or
a few hours (lateness / early leave the part-day leave explains is not raised); the Today board
says "Annual leave · half day, morning" and the schedule grid "… · half day". R7 Boolean fix.

**Version bumps:** `pb_ess_workforce` 19.0.1.3.2 → **19.0.1.4.0**; `pb_timeoff` 19.0.1.10.0 →
**19.0.1.11.0**; `pb_me_team` 19.0.1.1.0 → **19.0.1.2.0**; `pb_attendance_flow` 19.0.1.3.0 →
**19.0.1.4.0**; `pb_today` 19.0.1.5.2 → **19.0.1.6.0**; `pb_schedule` 19.0.1.9.1 → **19.0.1.10.0**.

**Files:** `pb_ess_workforce/{__manifest__.py, controllers/portal.py, models/ess_workforce.py,
views/portal_templates.xml, static/src/scss/ess_workforce.scss, static/src/interactions/leave_form.js
(new), i18n/vi_VN.po, tests/__init__.py, tests/test_wdgap_qf3.py (new), tests/test_wdgap_qf3_http.py
(new)}`; `pb_timeoff/{__manifest__.py, models/hr_leave_approval.py, models/leave_rules.py,
i18n/vi_VN.po, i18n/id_ID.po, tests/__init__.py, tests/test_wdgap_qf3_withdraw.py (new)}`;
`pb_me_team/{__manifest__.py, models/pb_me_team.py, views/portal_templates.xml,
static/src/scss/my_team.scss, i18n/vi_VN.po, i18n/id_ID.po, tests/__init__.py,
tests/test_wdgap_qf3_team.py (new)}`; `pb_attendance_flow/{__manifest__.py,
models/attendance_exception.py, tests/__init__.py, tests/test_wdgap_qf3_half_day.py (new)}`;
`pb_today/{__manifest__.py, models/pb_today.py, i18n/vi_VN.po}`; `pb_schedule/{__manifest__.py,
models/schedule_grid.py, i18n/vi_VN.po}`.

Routes added (all `auth='user'`, POST): `/my/work/leave/preview` (jsonrpc, read-only),
`/my/work/leave/<id>/withdraw`, `/my/work/leave/<id>/cancel`, `/my/work/leave/<id>/document`;
`/my/work/leave/apply` now also reads `period_from`, `period_to`, `hour_from`, `hour_to`, `doc`,
`doc_cam`. New flash keys `leave_withdrawn`, `leave_cancelled`, `doc_added`.

## 2. Tests

Local runs only (no server touched). Tree: this worktree. Templates: `upd_p5e_y9` (first
runs) then, after the local disk filled up (ledger QF3-2), the small `upd_p6_t_tpl` (vi + id
installed) for both the baseline and the final run. Commands are the repo recipe:
`odoo-bin -c <wt conf> -d <copy> -u pb_ess_workforce,pb_timeoff,pb_me_team,pb_attendance_flow,pb_today,pb_schedule,pb_me_portal,pb_clock --test-enable --test-tags <tags> --stop-after-init --http-port/--gevent-port <free>` (G12/G19/G35/G97).

**The 24 QF3 tests** (`--test-tags wdgap_qf3`): **24 / 24 pass** (last full run, and alone).

| # | Case | Test(s) | Result |
|---|---|---|---|
| 1 | Whole-day apply, old call signature; existing suites green | `test_01_whole_day_apply_keeps_the_old_signature`; `test_p8_portal`, `test_p8_adversarial`, `pb_me_portal` `test_portal_accounts` (T2.9 portal apply), `pb_timeoff` `test_leave_rules` | PASS (the `test_leave_rules` errors are the same 6 as on unchanged HEAD — see below) |
| 2 | Half day morning → 0.5, `am`; afternoon; several days pm→am = 2; full | `test_02_half_day_morning` (internal + employee login) | PASS |
| 3 | Part-day values on a whole-day kind refused plainly; "Full day"/empty times accepted; nothing created | `test_03_…` | PASS |
| 4 | Hours: 2 h; from ≥ to refused; several days refused; missing times refused | `test_04_hours` | PASS |
| 5 | Preview = created amount; `after == virtual_remaining − amount`; writes nothing (leave and attachment counts); hours; over-balance both forms | `test_05_…` | PASS |
| 6 | Past date refused with `lock_past` on (both logins), sick-leave kind allowed + flagged, allowed with the switch off | `test_06_…` | PASS |
| 7 | Withdraw (engine company): leave `cancel`, request `cancelled`, no open seat, no to-do; company with no route | `test_07_…`, `test_07b_…` | PASS |
| 8 | Withdraw someone else's / garbage id / started / approved ("use Cancel") refused | `test_08_withdraw_refusals` | PASS |
| 9 | Cancel approved future leave with reason (both logins): `cancel`, no open request, reason on the leave's message, balance back 9 → 10; no reason / waiting / started / someone else's refused | `test_09_cancel_an_approved_leave` | PASS |
| 10 | Approvals-screen withdraw cancels the leave (engine as submitter; `pb.approval.inbox.cancel`); an approved leave is untouched by the hook | `test_10_…`, `pb_timeoff` `test_10a/b/c` | PASS |
| 11 | PDF + JPEG accepted (paths stripped), `.exe` renamed `.pdf` refused, 11 MB refused, 6th refused, bound to the leave (Command Center papers = 2), another person's leave refused, refused file on apply creates nothing, cancelled leave takes no papers | `test_11_documents`, `test_11b_…`, `pb_timeoff` `test_facts_…` | PASS |
| 12 | Manager context: files with tokens, "Half day, afternoon"; `_balance_after` skips an uncounted kind (allocation read patched to fail) and still answers 4 for a counted one | `pb_me_team` `test_12a`, `test_12b` | PASS |
| 13 | Whole-day leave hides the missing punch (as before); half day and hours do not; lateness after a morning off not raised | `pb_attendance_flow` `test_13a/b/c` | PASS |
| 14 | Browser walk (below) | Claude in Chrome, local copy | PASS |
| 15 | Static gates | `py_compile` on every changed `.py`; `lxml` parse of both changed templates; PO parse gate (`PoFileReader`) on all 11 `.po` files of the six modules: 0 failures, 0 msgstr naming the vendor; diff scan for the vendor name in added lines: none outside imports | PASS |

**HTTP test** (`test_wdgap_qf3_http`, employee login over real HTTP): page renders the new
controls with no inline `style=`; preview answers JSON and writes nothing; the form posted as a
browser with scripts off sends it (every control at its default + a PDF) → half day created with
the file; the tokened link opens (200) for the employee login; add a document and withdraw
from the row; another person's leave → error page, nothing moved. PASS.

**Full suites of every touched module** (final run, this branch, `upd_p6_t_tpl`): **509 tests,
6 failed, 13 errors** — pb_ess_workforce 146, pb_timeoff 129, pb_me_portal 125, pb_schedule 113,
pb_today 48, pb_attendance_flow 44, pb_me_team 22. **Unchanged HEAD on the same template (the `origin/19.1` tree exported to a scratch folder):
485 tests, the very same 6 failed + 13 errors, test for test** (19 identical ids:
`TestAttendanceFlow` 04/05/07/13, `TestLeaveRules` x6 (the lock fires inside create on that
template), `TestTimeoff` 03/05 ("Your account is no longer in use" from `pb_records`' engine
check on that template's seat holder), `TestMeHomeCards` 05/06, `TestMeHomeSource` 12,
`TestP1bSidebar`, `TestP2Sidebar`, `TestPbMePortal` 01, `TestPortalOnlyDoors` t1_7). So:
**+24 tests, 0 new failures**. (On the big `upd_p5e_y9` template the unchanged HEAD gave 485
tests, 8 failed, 12 errors: the same family plus three template-only ones; the phase was not
re-run there because the disk filled.)

**Browser walk (14)** — local copy `qf3_walk` (from `upd_p5_t_full2`, jobs and mail off),
`127.0.0.1:8879`, Claude in Chrome, signed in by `fetch` to `/web/session/authenticate` (G99),
DEMO people only (an employee login and a manager), tab closed after:
- Employee: chose a half-day kind → only "The day: Full day / Morning / Afternoon" appeared and
  the document block turned prominent ("A document is needed for this kind of leave"); chose
  Morning → "This request: Half a day / After this request: 10.5 days left" appeared live;
  took a photo (camera input) → file named under the buttons; sent → "Leave request sent for
  approval", row "Half a day · Half day, morning" with the photo chip, tile "0.5 days waiting
  for approval".
- Hours kind: only From/To showed; 09:00–11:30 → "This request: 2.5 hours"; 11:30→08:00 → "The
  end time must be after the start time." Over the balance → "After this request: 3.5 days more
  than you have" + "This is more than you have left, so it cannot be sent. Ask HR about your
  balance."
- Manager (`/my/team/approvals/<id>`): "Tue 15 Dec · Half day, morning", length "Half a day",
  Documents: the photo (link answers 200, image/png), "Left after this 10.5 days"; drawer chips
  "Part of the day: Half day, morning", "Documents: 1 document attached"; list card "Half a day".
- Employee: Withdraw → "Request withdrawn…", row Cancelled; Cancel on the approved one with a
  reason → "Leave cancelled. Your manager has been told.", tile back to 12.0; Add a document on
  a waiting row → "Document added…".
- Scripts off: the form as the server drew it (parsed, no script run), every control at its
  default, posted → `done=leave_sent`, "Half day, afternoon" created.
- Phone width: the page in a 390 px frame: no sideways scroll, an open fold-out stays inside
  the row; the browser window itself would not go below 614 px (also checked).
- Console: no errors on My Leave or the manager page. Two layout faults found and fixed in the
  walk (commit `4c227e44d`): an open fold-out squeezed the request text into a narrow column;
  at phone width the request column reserved 240 px of empty height. Status badges also got
  their colours.

## 3. Self-review against the non-goals and the rails

**Non-goals (§2):** `pb_approval_config`, `biz_approval_workflow` and every `pb_pack_*` untouched
(`git diff origin/19.1 --stat` lists none of them). No set-up screen, accrual, comp-off, new
process key, "ask to change" flow or leave letter. The Rize medical-reference rule is untouched
(an upload does not satisfy it; nothing seeded). No portal ACL added for `hr.leave` or
`ir.attachment`: every portal write is `sudo()` after the ownership guard.

| Rail | How it is met | Proof |
|---|---|---|
| R1 ownership | Every new method starts with `_require_own_employee()`; `_own_leave` looks the id up and refuses any leave whose `employee_id` is not that employee before anything else (and a garbage id the same way). | T8, T9, T11, HTTP test (another person's leave → "We could not find that request", nothing moved) |
| R2 rules sudo skips | ONE helper, `_leave_refusal(action, …)`, behind apply / withdraw / cancel / document and behind the page's `can_*` flags. Apply asks `pb_timeoff`'s past-date rule (now `hr.leave._pb_backdate_verdict(vals, as_officer=False)`, the same method `create` uses) and honours `pb_timeoff.lock_past`. Withdraw: `confirm`/`validate1`, first day today or later. Cancel: `validate`, first day after today, `can_cancel` evaluated `with_user(person)` for an internal login, restated for an employee login (approved, starts in the future). Document: own, `confirm`/`validate1`/`validate`. `request_date_to_period` added to `SUBSTANCE_FIELDS`. | T6 (hole closed: refused with the switch on, allowed with it off), T8, T9 |
| R3 withdraw retracts | `hr.leave._approval_withdraw` cancels a waiting leave through `_force_cancel` (in its own savepoint, because the engine swallows a failure there); the employee path calls the engine's cancel in a savepoint when a request is open, else cancels directly. Cancel of an approved leave withdraws any open request first and asserts none is left. | T7 (engine company + no-route company), T9 (no open request after cancel), T10 (engine cancel as the submitter, and `pb.approval.inbox.cancel`) |
| R4 uploads | Cloned from expenses: first-bytes sniff (jpeg/png/webp/pdf), bound read of 10 MB + 1 byte in the controller, 10 MB refusal in the facade, at most 5 per leave, attachment created `sudo()` bound to the leave, filename path stripped and control characters removed, declared type ignored; links carry `access_token`. | T11, HTTP test (tokened link opens for the employee login) |
| R5 half-day readers | Attendance exceptions: whole-day leaves exactly as before; a part-day leave no longer hides the missing punch; lateness at a covered start / early leave at a covered end is not raised. Today board and schedule grid labels. Payroll readers untouched. | T13 a/b/c |
| R6 portal CSP | No inline `style=` (classes in `ess_workforce.scss`, `my_team.scss`, both in `web.assets_frontend`); the preview is a frontend interaction cloned from the expense form calling the new JSON route; with scripts off every control shows and the server re-checks everything. | HTTP test (no ` style="` in the form; scripts-off post with every control at its default + a file), browser walk |
| R7 Boolean bug | `if not lt.requires_allocation: return None` before any allocation read. | T12b (allocation read patched to fail: not called; a counted kind still answers 4) |
| R8 words | No "Odoo" in any new user-visible string or msgstr (diff scan + PO gate). Every new sentence in `vi_VN.po`; `id_ID.po` where the module ships one (`pb_timeoff`, `pb_me_team`). `pb_ess_workforce`, `pb_today`, `pb_schedule` ship no Indonesian file — none created (as the handover says); their new sentences show in English to an Indonesian reader, as the rest of those pages already do. | PO gate |

**Deviations from the handover (written plainly):**

- **D1 — "You can still send it" is only true for some kinds.** hr_holidays itself refuses a
  request that goes over the balance of a kind that does not allow going below zero (its
  `_check_validity`). Saying "You can still send it" there would be untrue. So the warning has
  two forms: for a kind that allows going below zero (and within its limit): "This is more than
  you have left. You can still send it; your approver will see that."; otherwise: "This is more
  than you have left, so it cannot be sent. Ask HR about your balance." Nothing about the core
  rule was changed.
- **D2 — the past-date switch now governs the employee pages only.** As the handover asks,
  `pb_timeoff.lock_past` off lets an employee-page request start in the past. The rule inside
  `create` (internal users in the back office) still does not read that switch — unchanged
  behaviour.
- **D3 — internal logins without HR rights.** Core's `can_cancel` cannot be computed as a plain
  internal login: it reads the employee's leave manager, a private employee field such a login
  may not read (AccessError). For that case the same rule is restated (approved, starts in the
  future), exactly as for an employee login.
- **D4 — the inbox facts are drawer chips, not frozen facts.** The documents are attached after
  the request is sent in (the route starts inside `create`), so a frozen "documents" fact would
  always say none. Both lines are live chips from the leave adapter instead; no new condition
  appears in the route editor.

## 4. Will customers see half days without a set-up change?

The option appears only for kinds whose own setting is "half day" or "hours". From the data:

- Stock data files (`hr_holidays/data/hr_leave_type_data.xml`, noupdate): Paid Time Off and Sick
  Time Off are whole days; **Unpaid is hours**; **Extra Time Off is half days**; the Belgian
  kinds are half days.
- On the local copy of payobook (taken 2026-11-13): 50 kinds in whole days, **27 in half days**
  (among them ID Annual Leaves, ID Sick Leaves, ID Unpaid Leaves, HK Annual / Sick, Extra Time
  Off), **3 in hours** (Unpaid, Extra Hours, Unemployment). The Vietnamese demo kinds (Demo
  Annual Leave, Demo Unpaid Leave) are whole days.
- Rize: its kinds are seeded by `tools/seed_rize_absence_policy.py` with `request_unit: 'day'`
  — **Rize will not see half days** until HR changes a kind's "Duration type".

So Indonesian employees on payobook see half days at once; Vietnamese and Rize employees see
the page as before until a kind is set to half days.

## 5. Left unchanged, follow-ups and owner questions

**Whole-day readers left unchanged (R5):** `pb_hr_workforce/models/shift_planning_grid.py:104`
(the shift grid's leave marker), `pb_driver_checkin/models/pb_driver_map.py:95`, the Leave
Command Center heat map and KPIs (`pb_timeoff.py:155-200, 255-296`), `pb_schedule`'s
`_leave_presence` warning map (it marks the day "on leave" for a roster warning — still right
for a half day as a caution), `rize_policy.py:1023` (calendar-day counting: a half day counts as
1 for "calendar days" rules) and `_pb_policy_payroll_metrics` (errors on hour kinds). Payroll
readers are hour-based and untouched.

**Follow-ups (engineering):**
- Clickable files inside the Approvals inbox drawer (needs `pb_approval_config`, QF1's area).
- `get_my_leave` uses the deprecated `read_group` (as before this phase); a later tidy.
- The rest of `pb_timeoff`'s vi/id files are thin (hundreds of older strings have no entry):
  pre-existing, not this phase.

**Owner questions:**
1. Rize's kinds of leave are all "whole days". Should HR switch some (for example annual leave)
   to half days so Rize staff can ask for a morning or an afternoon off? It changes nothing else.
2. When someone asks for more days than they have, the system refuses unless that kind of leave
   is set to "allow going below zero". Do you want annual leave to allow a small negative
   balance (for example up to 2 days) so the request can be sent and the approver decides?
3. Should a missing certificate on a kind that needs one ever stop the request from being sent?
   Today it never does (the page says it is needed, the approver sees whether one came).

## 6. Deploy notes

- **Modules to `-u`** (all five databases: payobook, payobook_template, p0clone, rize, sudima;
  never abm): `pb_ess_workforce, pb_timeoff, pb_me_team, pb_attendance_flow, pb_today,
  pb_schedule`. Expect the usual cascade to dependents (`pb_timeoff` and `pb_attendance_flow`
  are depended on widely — ledger G39 of UPDATES); take the per-database active-job lists
  before/after (cron snapshot rule).
- **Tier: normal** (stop → `-u` each database → purge/bump → start). No stored-data rewrite,
  no new model, no new field, no new table, no access rule; the only new persistent thing is an
  `ir.attachment` when a person uploads.
- **Asset purge: yes** — new frontend script `pb_ess_workforce/static/src/interactions/leave_form.js`
  and SCSS changes in `pb_ess_workforce` and `pb_me_team` (`web.assets_frontend`). Bump
  `web.assets.version` and add the `orm_signaling_assets` row as usual.
- **Data step: none.** No kind of leave is switched to half days by this phase (owner question 1).
- **Translations:** `vi_VN.po` for all six modules' new sentences (+ `id_ID.po` in `pb_timeoff`,
  `pb_me_team`); PO parse gate passed locally on all 11 files of the six modules.
- **After deploy, check on payobook with the QA login:** `/my/work/leave` renders; an Indonesian
  half-day kind shows Morning / Afternoon; the preview line appears; console clean.

## 7. New gotchas (also in `WDGAP_LEDGER.md`)

QF3-1 … QF3-7 in `WDGAP_LEDGER.md`: shared scratchpad between phase agents; local disk nearly full (use the small templates); sudo skipped the past-date rule and the HR alert; `can_cancel` as a plain internal login raises AccessError; core refuses over-balance unless the kind allows going below zero; the engine calls `_approval_withdraw` without a savepoint; a running server keeps old CSS until restarted.
