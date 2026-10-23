# NAV P3c — Home: TEAM for people who manage others

Read first: `docs/handovers/NAV_LEDGER.md`; `docs/design/payobook-navigation-review-20261019.html` §12.4 Home row and §13 Home
"TEAM: Manager composition" (New, P3). Owner decisions 2026-10-21: in scope, after P3b. Rule from §12 F09: no Me / My team /
Administration switch; TEAM is one Home rail item, visible only to people with direct reports. Implementer: Opus.

## 1. Goal

A manager opens Home › TEAM and sees, in one screen and without clicking around: what is waiting on their decision, who on
their team is in, out or late today, which probation and review conversations are due, who is behind on required
learning, and the hiring requests they own. Every tile opens the existing screen already filtered. No salary, no growth
plans, no other manager's people.

## 2. Verified plumbing (do not re-derive)

| Fact | Where |
|---|---|
| "My team" has three meanings in the product: (A) direct reports `parent_id.user_id = me` (goals rules `pb_goals_rules_b2.xml:51,88,125,176`; probation rule `pb_probation_security.xml:75`; training `pb_my_training_due.py:195-202,221`; `res.users._pb_has_reports` `ess_landing.py:177-180`); (B) the whole branch `child_of` (inbox `_my_team_user_ids` `inbox_facade.py:103-117`); (C) a seat waiting on me (`_pb_has_open_seat` `ess_landing.py:182-186`). **TEAM uses (A)** for people, and (C) for decisions. | agent fact-find 2026-10-21 |
| No RPC-callable "has reports" probe exists; closest is `pb.my.training.i_manage_people()` (`pb_my_training_due.py:195-203`, (A), active, never raises) and `pb.hiring.can_open` as the probe pattern (`pb_hiring.py:86-91`, used `hiring_palette.js:82`). `resolveLensAccess` (`hub_gates.js:35-61`) calls `probe.method` with no args; falsy/error hides the lens. | |
| Inbox: `pb.approval.inbox.list_requests(tab='mine'|'all'|'returned'|'done', filters={area, process_key, due}, cursor, scope='me'|'team'|'org')` (`inbox_facade.py:178-230`); `counts.mine` = my open seat on the active step; cards have `area, icon, title, sub, amount, currency, due_at, late, mine, blocked, waiting_for` but no model/record; `money` per currency over `mine` cards. Areas `pay, money, data, people, time, setup, platform, other` (`process.py:6-15`). `team` scope reads as sudo and can include payroll amounts: **TEAM must call `tab='mine', scope='me'` and never show `amount`/`money`.** `PbInbox` accepts a `scope` prop; `pb_focus:"request:<id>"` targets one request; no arrival for `area`. Home door precedent `DOORS.approvals` (`pb_dashboard.js:133`). | |
| Today: `pb.today.get_today_data(department_id, day)` (`pb_today.py:129`) raises unless attendance officer/system; filters company + exact department; row `state on_shift|checked_out|on_leave|not_started`, `is_late`, `minutes_late` (`:327-348`). Leave: `pb.timeoff.get_board` is HR-only; "out today" domain `state='validate'`, `request_date_from<=today<=request_date_to` (`pb_timeoff.py:122-127`). **Neither can be filtered to reports; TEAM runs the same domains itself as sudo over the reports only.** | |
| Probation: `pb.probation.get_board()` is lifecycle-group gated (`pb_probation.py:55-58`); `pb.probation.review.manager_user_id` from `parent_id.user_id` (`probation_review.py:89,176-178`); review states `scheduled, nomination, feedback, consolidation, one_on_one, verdict, closed`; the manager's step = `consolidation|one_on_one|verdict` (`probation_board.js:236-254`); rows carry `red_flags`, `training_pending` (do not show). | |
| Goals: `pb.goals.get_year(cycle_id, tab, filters)` (`pb_goals_year.py:317`) reads as the caller; check-ins `state in (planned, missed)` with `overdue` (`:365-401`), reviews with `due, overdue` (`:403-431`); manager fields `manager_user_id`, `manager_employee_id` on checkin/review/set (`checkin.py:117-122`, `review.py:65`, `goal_set.py:84-87`). HR-group users get the whole company, so **TEAM filters `manager_user_id = uid` itself**. | |
| Training: `pb.my.training.team()` (`pb_my_training_due.py:206-245`) already returns the direct reports' assignments `{manages, name, rows, people, overdue, due, done}` as sudo; `team_overdue_count()` (`:247-249`). Portal page `/my/training/team` exists (`pb_training/controllers/portal.py:307-325`). | |
| Hiring: `pb.hiring.requisition` fields `requested_by_user_id`, `reporting_manager_id`, `asked_user_id`, `request_state` (`none, asked, writing, sent_in, hr_ok, agreed, not_approved`), `is_confidential`; rows carry `budget_cost`, `budget_over_by` (**do not show**). | `requisition.py:144-157`, `requests_p3.py:290-336` |
| Growth plans (`pb.pip.*`): gated to its own groups (`pb_pip.py:82-102`); **TEAM reads nothing from it.** | |
| Pulse precedent for composition: `pb.dashboard.get_home_data()` runs each section in a savepoint, AccessError → default (`home_data.py:124-218`), `optional(model, fn)` guard (`:96-118`); JS maps keys to words and doors (`pb_dashboard.js:132-238`), `door(xmlid,{lens,focus,back})` (`:1660-1688`). QuietGlance/QuietSteps are `t-call` templates (`pb_import_kit/static/src/xml/quiet_board.xml:26,38`; props documented there). Home lens contract `HOME_LENSES` (`home_hub.js:84-102`); registrations `askhr_lens.js:67-75` (seq 15), `rnr_palette.js:72-77` (wall 20), `comm_palette.js:90-100` (50). | |

## 3. Design (R11 bar; plain words; Lucide; no "Odoo"; no money anywhere on this screen)

Lens: key `team`, icon `users`, label `_t("Team")` (VI "Đội của tôi"), title `_t("My team")`, sequence 12 (after Inbox, before Ask HR), no groups, probe `{model:"pb.home.team", method:"can_open"}` = has ≥1 active direct report (A). Lives in **`pb_home_hub`** (new `models/team_facade.py` model `pb.home.team`, new `static/src/js/team_lens.js` + xml + scss) and reads every other module through `self.env.get(...)` with the Pulse `optional()` pattern, so `pb_home_hub` gains **no** new dependencies.

Layout (top to bottom):
1. **Hero sentence** (the hero moment): "**Your team of 8** · 6 in today · 1 on leave · 1 not started yet · **3 things waiting on you**" with each number a door. Under it an avatar strip of the reports, each with a status dot (green in, grey not yet, amber late, blue on leave) and a tooltip "Linh · late 12 min". Clicking an avatar opens the employee drawer the People hub uses (`Employee360Drawer`, via `pb_employee_vault` if installed; else the employee form).
2. **Waiting on you** (QuietGlance tiles by area): Time off · Overtime · Expenses and trips · People · Other, counts from `list_requests(tab='mine', scope='me')` grouped by `area` (time → "Time off and overtime" split by `process_key` as Pulse does `home_data.py:689-720`). Tile door: Home › INBOX (`lens:"approvals"`) with the area pre-selected: add an optional `arrival.area` to `PbInbox` (`inbox.js` state `area`) read from `pb_focus:"area:<key>"` (extend the existing `pb_focus` parser at `inbox.js:47-55`, keep `request:<id>` working).
3. **Conversations due** (two QuietSteps strips side by side): **Probation** (reviews where `manager_user_id = uid` and state in consolidation / one_on_one / verdict: "Hoa · 1:1 due Thu", door → People › PROBATION focused on the review) and **Goals** (check-ins planned/missed and reviews due where `manager_user_id = uid`: "Nam · monthly conversation overdue 6 days", door → Talent › GOALS tab checkins/reviews with `pb_focus`). Max 5 rows each, then "+N more".
4. **Learning** (one line + tile): "2 people have required training past its date" from `pb.my.training.team()`; door → the portal page `/my/training/team` (it exists) opened in the same tab, or Talent › TRAINING filtered by the manager if the officer gate allows; prefer the portal page for a plain manager.
5. **Hiring requests I own** (compact rows): requisitions where `requested_by_user_id = uid` or `asked_user_id = uid` and `request_state` in asked / writing / sent_in / hr_ok, showing title, state word and "waiting on you" when `asked`/`writing`; door → Hiring › OVERVIEW with `pb_role_id`. No budget words.
6. **Empty states:** no reports → the lens is hidden (probe); reports but nothing due anywhere → one calm line "Nothing needs you today. 8 people, all accounted for." with the avatar strip still shown; a section whose module is not installed is absent, not zero.

Server `pb.home.team`:
- `can_open()`: `bool(hr.employee.search_count([('parent_id.user_id','=',uid),('active','=',True)]))` as sudo.
- `get_team()`: reports = active employees with `parent_id.user_id = uid` in `env.companies`; sections each in a savepoint with `optional()`: `today` (attendance punches today + validated leave today + shifts if `pb_schedule` present, computed over the report ids with the same state words as `pb.today`), `decisions` (inbox mine counts by area), `probation`, `goals`, `training` (`pb.my.training.team()`), `hiring`. Return only names, dates, counts, ids and door keys. **Never** include amounts, salary, `red_flags`, `training_pending` details, growth-plan anything, or people outside the reports.
- Everything reads as sudo but scoped by the report ids; raise nothing; log and skip a section on error.

## 4. Non-goals
No team scope (B); no department view; no new models; no approvals taken here (doors only); no portal changes except reusing `/my/training/team`; no changes to Pulse.

## 5. Tests
Python `pb_home_hub/tests/test_team_p3c.py`: `can_open` true/false by reports; a manager with 3 reports sees exactly those (a fourth employee under another manager never appears); today states; decisions counts equal `counts.mine` split by area; probation/goals rows only for `manager_user_id = uid` even when the user is in the HR goals group; training section equals `pb.my.training.team()`; hiring rows exclude confidential roles not theirs and carry no budget keys; a section's module absent → key absent; no `amount`/`salary`/`wage` key anywhere in the payload (assert recursively). Chrome: HR admin without reports → no TEAM item; a manager (use a demo manager with reports on the local DB) → hero numbers add up to the avatar strip; each tile door lands filtered (Inbox area chip pre-selected, Probation board focused, Goals tab, training page, Hiring role); keyboard reachable; console clean.

## 6. Deploy (after Fable's go) — NORMAL tier
`-u pb_home_hub,pb_approval_config,pb_learn` (+ any module whose palette/lesson changed); Learn: anchors `tm-hero`, `tm-waiting`, `tm-conversations`, `tm-learning`, `tm-hiring` reserved; hub_home tab `team` ("Team" / "Đội của tôi") added to `data.js` and practice MENU; station "home" outline sentence; regenerate; .po unchanged; bump pb_learn. Access: no sidebar change (lens-level); confirm Screens lens unchanged. Cron snapshot; bundle warm-up; push after.

## 7. Report
`docs/handovers/NAV_P3C_REPORT.md`; stop at the deploy gate first.
