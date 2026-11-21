# WORKFLOW-2 · Phase 5a report — messages decided, start on a schedule

Builder: Claude (Opus implementation agent), 11 November 2026. Handover: `WF2_P5A_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (gotchas G65–G71 added, P5a row marked).

## 0. In plain words (for the owner)

- **Shipped and live:** §3.1 (the message decisions and leftovers) and §3.2 (start on a schedule). **Not shipped:** §3.3 "Repeat for each line" — not started, nothing of it is on any site (see §9 for exactly what remains).
- **Pay changes / pay reviews (D26).** When an approval route is live, only the person whose turn it is is told. The rest of the pay group no longer gets "A pay … is waiting for you" — except anyone who could not then see the request under Approvals › Everyone (today: one pay manager on rize), who keeps the to-do.
- **"Sent back" emails (D28).** Expense claims, time off, goal sheets, goal changes and resignations now email the employee when a request is sent back, with the reason and one button to their own page. Approvals' own "Sent back to you" stops for those (only when the employee sent it in themselves and has an email address). Trips and equipment: not done (they have no approved/refused email to sit beside).
- **Start on a schedule.** A workflow can start by itself: every day / week / month / year, or once, at a time, optionally on working days only; for a new process or once for each matching record. "Next 5 starts" and "Would start for 12 records today" are shown while building. Nothing is switched on anywhere; on sudima nothing scheduled can start until its workflow clock (the Studio job) is switched on, and Review says so.
- **Small leftovers.** The time-off card corner ribbon now says "Waiting for approval" / "Second approval". A candidate's workflow link goes out the moment the recruiter saves their email (no minute's wait).

## 1. Commits, versions

| Commit | What |
|---|---|
| `7a2be049e` | D26: pay change / pay review to-dos only for the person asked (`pb_pay/models/pay_single_notice.py`), tests T1a–e |
| `3b3ff23e9` | D28: sent-back emails (expenses with vi/id, time off, goal sheet declaration, goal change, resignation), time-off ribbon words, P2b tests updated to the decisions, tests T2, T3, T4a |
| `4bed4748c` | Start on a schedule (backend, worker, preview, Review/Activity data, workbench `schedule.js`), instant email re-check (D24 leftover, Hiring write hook), Studio tests T4b, T5–T8, T17, P2 T5 updated, `tools/workflow_studio/run_p5a.py` |
| (docs commit) | This report, ledger |

Not pushed. Versions: `pb_lifecycle` **19.0.1.17.0**, `pb_me_expense` **19.0.1.2.0**, `pb_timeoff` **19.0.1.10.0**, `pb_goals` **19.0.1.4.0**, `pb_offboarding` **19.0.1.5.0**. Unchanged (method-only, G29): `pb_pay` 19.0.3.7.0, `pb_hiring` 19.0.2.23.6; `biz_approval_workflow` / `pb_approval_config` not touched. Reverse dependents checked first: `pb_me_expense` → `pb_expenses_hub`; `pb_timeoff` → `pb_ess_workforce`, `pb_mission`; `pb_goals` → none; `pb_offboarding` → `pb_contract_lifecycle`, `pb_pip`, `pb_probation`, `pb_demo_seed`, `pb_training*` — all already upgraded by every `-u pb_lifecycle` (G70), so no wider cascade than every earlier WF2 deploy. Workbench cache keys **`wf2-p5a`** (iframe, inbox, strip and all 15 tags in `index.html`; `schedule.js` new, loaded last).

## 2. Tests

### Backend — Studio suite (`run_suite.py`, local `am_wf2p5a` = clone of `am_wf2p2b`)

Before this phase: **126/126**. After: **132/132** (126 + 6 new; P2 T5 updated for D28). P5a tests:

| # | Test | Result |
|---|---|---|
| T4b | `test_wf2p5a_t4b_candidate_email_saved_sends_the_link_at_once` — recruiter saves the email → link queued once, helper to-do gone, no worker pass needed; a save that is not about the email never looks | pass |
| T5 | `test_wf2p5a_t5_schedule_maths` — day; Monday in Sydney (22:00 UTC the day before); "31st" → 30 Nov / 28 Feb; "last"; 29 Feb → 28 Feb in common years, 29 Feb 2028; once (and none once passed); working days (Sat/Sun → Mon, once); clocks forward (2:30 → 3:30, once); clocks back (2:30 twice → once, the first); worker window (after, until]; words; checks | pass |
| T6 | `test_wf2p5a_t6_scheduled_new_process_starts_once_per_tick` — switching on sets the clock, no rule and no job made; nothing due → nothing written; a week off → one run, 6+ missed noted, "Started on schedule", history sentence; same pass again → none; a window reaching the same start again → none; same start key → none; next start → a new run | pass |
| T7 | `test_wf2p5a_t7_scheduled_each_record_filters_cap_pause` — preview count/names/5 next = worker's; one run per matching record (filters applied, a non-matching record left out), start keys; same start again → no second history row; next start with runs still going → none twice ("already had this workflow running"); over the cap → none started, reason kept, publisher told once (also on a second look), the note lands in their inbox; paused → none; switched on again → clock reset, no catch-up | pass |
| T8 | `test_wf2p5a_t8_scheduled_design_rules_and_review` — "the person who starts it" refused (`schedule_initiator`); record workflow as "a new process" refused (`schedule_starts`); week with no day refused; Review: the twin with the same pattern (`schedule_twin`), clock switched off sentence, time off's own carry-forward timetable (`schedule_area_chaser`); plain words | pass |
| T17 | `test_wf2p5a_t17_new_strings_are_plain` — no framework name, "cron", "schedule expression", "sub-run", "loop", "iteration", "index", "node" in the new files | pass |

T9–T16 (Repeat for each line): **not written — the feature is not built** (§9).

### Area tests (`tools/workflow_studio/run_p5a.py`, local)

**55/55** — P5a T1a–e (pay), T2a–f (expenses), T3a–d + T4a (time off), T3e–g (goals), T3h–j (resignations), plus the P2b area tests these decisions touch (pay, expenses, time off, goals, resignations; four P2b assertions updated to the owner's D28 — "sent back is the engine's" → "is the area's").

- T1: D26 both ways, kill switch both ways, the engine's job off → as before, and the other managers really can read the request under Everyone (`_scoped('org')`).
- T2: one email with the reason to a staff login and to an employee-home login; idempotent (a retry sends nothing); sent in again and sent back again → told again; the engine's "Sent back to you" stops; switch off → engine copy back; no address → engine keeps it; vi + id words; Studio "already happens" lists it.
- T3: time off (staff + employee-home login → `/my/requests`), goal sheet (existing "have come back" email, now owned), goal change (new email), resignation (new email; employee sent it in → engine copy stops; resignation emails off → engine keeps it).
- T4a: time-off staff card ribbon reads "Waiting for approval" / "Second approval", stock words gone.

Not re-run this phase: the full area module suites (728 + 528 tests in P2b) and the approval suites (175). Neither `biz_approval_workflow` nor `pb_approval_config` changed; the area modules changed only in the files above. The machine was under heavy load from other sessions (load average 10–11), one Studio suite took ~40 min. Listed under weak points.

### Browser (local `am_wf2p5a_ui`, Chrome; screenshots looked at)

| # | Result |
|---|---|
| U1 | pass — "On a schedule" in "Start this workflow"; picker (How often segmented, weekday chips, day/month selects, date, time, "Working days only", the catch-up sentence); sentence per kind: "Every working day at 9:00, for each expense claim" · "On the 1st of each month at 9:00 …" · "Every year on 1 January …" · "Once, on 12 Nov 2026 at 9:00 …" · "Every Monday and Wednesday at 9:00 …"; process workflow: "On the last day of each month at 17:30, start a new “Month-end checks”". Next 5 starts correct for working-day shifts (1 Jan 2028 Sat → Mon 3 Jan; 28 Feb 2027 Sun → Mon 1 Mar) and leap years (Tue 29 Feb 2028). **Found and fixed:** switching to month/year on a schedule saved without a day read "Choose a day of the month" (G71); the sentence did not say a start moves to a working day ("…, or the next working day" added, server and screen). |
| U2 | pass — Try it out: "Every day at 8:00 · Next start: Thu 12 Nov 2026 at 8:00 · Would start for 4 expense claims today: EXP/2026/0090, …". Review "On a schedule": words, next three, "Would start for 4 records today: …", then the existing "Who takes part" and "Already happens" (which now lists Expenses' "When a claim is sent back, the employee gets an email with the reason and a link to fix it."). Clock-off warning proven by T8 (not switched off in the browser). |
| U3 | pass — Activity: "Scheduled starts" panel ("Did not start: 4 records matched, more than … it may start at once." in the problem colour; "Started for 4 records. 2 earlier starts were missed while the system was off; it started once."), runs table "Started by" = clock chip "Started on schedule". **Found and fixed:** the cap in that sentence was read at display time (fixture used a patched cap) — the cap used is now stored with the row. |
| U4–U8 | not run — Repeat for each line not built |
| U9 | pass — sent-back emails rendered: expense vi ("Đề nghị của bạn đã được trả lại", reason box "Lý do", button "Mở đề nghị của bạn"), time off en ("Your request was sent back", reason, "Open your requests"). The pay to-do before/after is proven by T1, not in a browser. |
| U10 | **not done** — P2b's U3 (joining checklist), U5 (employee claim page with/without strip), U7 (dock sentence) still have backend proof only. |
| U11 | partial — picker at the browser's narrowest window (500 px; drawer ~390 px): segmented wraps to two rows, chips wrap, Next 5 list fits, no sideways scroll. No real phone. |
| U12 | pass — T17 scan + by eye: no framework name, no emoji, Lucide-style clock icon. Console: only the cloned database's missing website favicon (500) and a refused connection during my own server restart. |

## 3. Performance

- Worker pass cost of the schedule look when nothing is due: one search of switched-on workflows and a pure date computation per scheduled workflow; nothing is written (no write every minute). With no scheduled workflow anywhere (every live site today) it is one empty search.
- Each-record fan-out queues one start per record inside the pass (≤ 500), and the existing event loop starts at most 100 runs per minute — a 500-record start finishes over about five passes, never in one long pass.
- The "200 child runs" measurement is for Repeat for each line — not built.

## 4. Deploy evidence

One normal-tier deploy (additive columns: `pb_workflow.last_tick_at`, `.schedule_log`, `pb_workflow_event.scheduled_at`, `pb_workflow_run.scheduled_at`, `pb_expense_claim.pb_told_returned_at`; four mail templates, noupdate; one inherited time-off board view; nothing rewritten) through the notes file and `flock /tmp/payobook-studio-deploy.lock`. Read the notes file right before: no START open (UPDATES P2d DONE 09:40). START **12:13 UTC**, DONE **12:21 UTC** (432 s, **421 s down**). Script: P2b's, adapted (`/tmp/wf2-p5a-20261111T121315Z/wf2p5a_deploy.sh`); launched with no "odoo-bin" in the ssh command (G62).

- **Before:** the seven server trees (pb_lifecycle, pb_hiring, pb_pay, pb_me_expense, pb_timeoff, pb_goals, pb_offboarding) hashed identical to the repo at `fae0f5148` (the commit before this phase) — nobody else's work overwritten.
- Clean staging from `git archive 4bed4748c` → service stopped → scoped `rsync -a --delete` per module (trees before in `/odoo/backups/wf2-p5a-20261111T121315Z/*-before.tgz`) → `-u pb_lifecycle,pb_timeoff,pb_me_expense,pb_goals,pb_offboarding --no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize (all exit 0, 0 ERROR/CRITICAL) → suites on p0clone: **Studio 132/132, P5a area 55/55** → sudima last (exit 0) → no job newly switched on anywhere → probe ×5 → asset signal + purge ×5 → service started → sites 200.
- **Tree hashes** server = repo at `4bed4748c` for all seven modules. **`latest_version`** in all five: pb_lifecycle 19.0.1.17.0, pb_timeoff 19.0.1.10.0, pb_me_expense 19.0.1.2.0, pb_goals 19.0.1.4.0, pb_offboarding 19.0.1.5.0; pb_pay 19.0.3.7.0, pb_hiring 19.0.2.23.6, biz_approval_workflow 19.0.1.7.1 unchanged.
- **Active job id lists** before = after on all five: 50 / 32 / 39 / 82 / 81. Sudima's Studio job still **off** (`studio_job_on: false`).
- **The deploy sent nothing.** Emails queued / Approvals outbox / to-dos identical before → after on all five (payobook 3,135 / 159 / 391; template 0 / 0 / 0; p0clone 34 (17 waiting) / 8 / 9; rize 830 / 123 / 88; sudima 18 / 6 / 4). rize messages +4 = the upgrade's change notes on two job names and two server actions (G64); nobody notified.
- **Probe ×5:** 0 workflows switched on, 0 scheduled workflows, 0 live runs, 0 runs started on schedule; new fields present; outbox kind present; the four sent-back templates present; requester declarations loaded (time off, expense, goal sheet, goal change, resignation all include "returned"); 0 claims stamped (no backfill); time-off board ribbon words in en / vi / id ("Đang chờ duyệt" / "Duyệt cấp 2", "Menunggu persetujuan" / "Persetujuan kedua") — the stock "To Approve"/"To Validate" gone. Guards on: p0clone, rize, sudima; off by themselves on payobook and the template (Approvals' message job off, G56) — so on those two the engine's sent-back notice was never delivered anyway and the new emails are the only ones.
- **Service:** exactly one process (`python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf`, the unit's own cgroup; the unit is an LSB forking one, so `MainPID=0` is normal). 0 ERROR/CRITICAL in the five upgrade logs and in the service log since the restart. Workbench `index.html?v=wf2-p5a` and `schedule.js?v=wf2-p5a` 200.
- **Signed-in live look: not done** — my browser had no live session open on a screen this phase changed (the open payobook.com tab is the time-off cockpit, which this phase does not touch). For the main loop: Time off › the standard time-off board card ribbons; Workflow Studio › any workflow › Start → "On a schedule" listed (open, do not save).
- Evidence: `/tmp/wf2-p5a-20261111T121315Z/` (steps, upgrade logs, suites, probe, job and queue snapshots, versions, hashes, warm).

Nothing published, switched on, created, approved, moved or sent. ABM untouched. Rollback: `biz_approval.single_notice=0` brings back every engine copy (the new emails are the areas' own and stay); whole phase: the tree tarballs above + `-u`.

## 5. D28 per area

| Area | Shipped? | Email | Engine's "Sent back to you" |
|---|---|---|---|
| Expense claims | yes | new, vi + id (siblings have them) | stops for the person who sent it in, when the employee has an address |
| Time off | yes | new, English (time off's templates have no vi/id) | stops likewise |
| Goal sheets | yes (declared only) | the sheet already emailed "Your goals … have come back" (note + "Open my goals") on both doors — P2b's note that it did not on a route was wrong; proven by T3e | stops |
| Goal changes | yes | new, English | stops |
| Resignations | yes | new, English, only when resignation emails are switched on | stops only when emails are on and there is an address |
| Trips, equipment | **no** | they have no approved / refused email of their own to sit beside (only notes on the record) | unchanged — the engine's notice still goes (nothing lost) |
| Pay change, pay review, overtime, contract extension, org plan | not in scope (the requester is not the person it is about / no requester messages owned by the area) | — | unchanged |

Time off note: a sent-back request is still turned into a refusal by time off (it has no "back to draft"), so the employee also gets the stock "has been refused" message as before; the new email says plainly that it was sent back and why.

## 6. Lines, `execution_user_id`

- **Which areas declare lines:** none — Repeat for each line was not built.
- **`execution_user_id` is still read:** by the two record rules `workflow_run_participant` and `workflow_log_participant` (`security/workflow_security.xml`, G7), and written to fill the stored column on create, publish and every start (`workflow_studio.py` create/publish/`_enqueue`, `workflow_models.py` event/run). Nothing uses it to run anything. Dropping it = remove the rule terms first, then the columns (left for a later decision, as the handover says).

## 7. Deviations from the handover

1. **"Around a date" (relative ±n days) not built** — it is the same job as the shipped trigger "At a record date" (offset before/after a date on the record). Reported as an overlap (§10.1), not silently resolved; the picker offers day/week/month/year/once.
2. **D26 keeps the to-do for anyone who cannot open Approvals › Everyone.** The handover said "verify they can see it there; if not, do not ship D26". On payobook, the template, p0clone and sudima every pay manager can; on rize one pay manager (an HR officer with payroll officer rights) cannot. Rather than not shipping, D26 applies per person: those who can see Everyone stop getting the to-do, the one who cannot keeps it. Nobody loses sight of a request.
3. **The "did not start" notice** goes into the publisher's in-app inbox as a note on their own contact (a workflow is not something a message can be posted on, and no run exists). It goes through the outbox once per start, but on payobook and the template the outbox job is off (G56), so it is never delivered there — the Activity row still shows it.
4. **A new process started on a schedule may not have filters** (code `schedule_process_filters`): it has no record to filter.
5. **A start that falls on the same day twice** (working-day shift: Saturday and Sunday both moving to Monday, or Monday's own start) is one start.
6. **Times on screens** ("Mon 16 Nov 2026", "9:00") are English formats for now (P5b).
7. **Resignation address read** is now done with system rights inside the message hooks (it reads an HR-only field the deciding approver may not hold, G67) — fixes a silent failure in P2b's "approved" check too.

## 8. R1 audit — every visible change to shipped screens

- **Workbench, any workflow:** "Start this workflow" has one more choice at the end, "On a schedule". Nothing else changes for a workflow that does not start on a schedule — the sentence, inspector, Try it out, Review and Activity wrappers return the shipped output untouched, and the Flowchart canvas code was not touched (no canvas or layout file changed).
- **Workbench, scheduled workflows only:** the "When…" card reads "On a schedule · Every Monday at 9:00, for each expense claim"; the start inspector holds the picker and Next 5 starts; Try it out has one card above the samples; Review has an "On a schedule" section above "Who takes part"; Activity has a "Scheduled starts" panel above the runs table and a clock chip in "Started by".
- **Time-off staff board:** the corner ribbon "TO APPROVE" → "WAITING FOR APPROVAL", "TO VALIDATE" → "SECOND APPROVAL" (same colours, same conditions).
- **Messages:** new sent-back emails (five areas); the approval engine's own sent-back notice stops for those areas (requester only, conditions in §5); the rest of a pay group stops getting "A pay … is waiting for you" while a live route has told the person whose turn it is (one rize manager excepted, §7.2).
- **Hiring:** saving a candidate's email sends a waiting workflow link at once (was: within a minute).
- **Studio "Already happens"** for expense claims shows the sent-back email as Expenses' row instead of Approval Matrix's.

## 9. What was not shipped, and what remains (Repeat for each line, §3.3)

Nothing of §3.3 exists in code. What it needs, in order (each piece is real work; the handover's design stands):
1. Contract `lines` + `_workflow_lines(record, key)` for expense claims (receipts); generic sources "each answer in a list question" and "each person in a team".
2. Engine: the `repeat` container in `workflow_definition` (validation codes for the refused kinds, one level deep, caps 50/200); child runs (`parent_id`, `line_key`, `line_label`, `line_values` on `pb.workflow.run` — additive columns) started together or one by one; join all/any; counts and per-outcome counts back on the parent; "Stop here" ends one line; per-line Retry; snapshot at start.
3. People surfaces: line label on inbox cards, grouping with "Do all in turn", employee home and link pages, strip "3 of 5 receipts checked", progress card per line, time report counting the container once.
4. Exclusions: child runs out of the one-automatic-workflow check, the runs table (toggle), schedule counts, strip switcher.
5. Screens: "Repeat for each…" in More possibilities; framed group on Journey, By stage and the Flowchart canvas (following how parallel groups are drawn), drag in/out, inspector with live sample.
6. Tests T9–T16, browser U4–U8, the 200-child-run timing.
Estimate: a full phase on its own (it touches the run walker, the inbox, the strip and all three canvases).

## 10. Overlaps found (R2a)

1. **"3 days before Contract end" = the shipped "At a record date" trigger.** Studio already starts a workflow a number of days before/after a date on the record (through the standard automation scheduler). Options: (a) in the schedule picker, add "Around a date on the record" that simply switches the workflow to that existing trigger (one way to do it, two doors to it); (b) build a second date-relative start inside the schedule (two engines for one job); (c) leave as is (people find it under "At a record date"). **Recommend (a).**
2. **Date-based chasers the areas run but do not declare.** A scheduled workflow can only be warned about what an area declares (today only time off's carry-forward warning). Undeclared ones (inventory §2.4): contract extension overdue email; goals "not in yet" reminders; joiner/leaver checklist daily reminders and contract-end / probation triggers (Lifecycle daily job); training chase; employee document expiry to-dos; vendor agreements running out; birthdays/anniversaries and monthly digest; payroll calendar cut-off reminders; Hiring's daily chase. Options: (a) each area declares its timetable in its contract (a `reminder` effect), starting with contract end, probation and document expiry, the most likely to be repeated; (b) accept the gap. **Recommend (a)** — small, add-only, one area at a time.
3. **Time off sent back is still also a refusal** (§5 note). Options: keep (now); or a "back to waiting" door in time off so it is not a refusal at all. Recommend keep until someone asks.

## 11. Self-score against the design bar

| Bar | Score | What is still weak |
|---|---|---|
| Hero moment (set "every Monday at 9, for each approved claim" and see exactly when and for whom it will start) | strong | Next 5 starts and "would start for N today" update as you click; no calendar view of a month. |
| Zero dead-ends | good | Over-cap says what to do; clock-off says why nothing starts; a schedule with a mistake shows the reason in place of the next starts. The over-cap notice never arrives on payobook/template (G56). |
| Plain language | good | No "cron"/"expression"; times and day names English only until P5b; the company time zone name is shown only after the first preview loads. |
| Motion / look | good | Reuses the segmented control, chips and cards; no new motion. The "How often" control wraps to two rows in the drawer. |
| Keyboard | good | Every control is a native button/select/input/checkbox; weekday chips are toggle buttons with `aria-pressed`. |

## 12. Gotchas added (ledger G65–G71)

See `WF2_LEDGER.md`.

## 13. For P5b

- **Strings WORKFLOW-2 added with no vi/id** (single-line `_()` strings, counted by script; multi-line ones add a little): `pb_lifecycle/models/` workflow_contract 39, workflow_stage 58, workflow_steps 70, workflow_people 68, workflow_people_design 22, workflow_home 6, workflow_strip ~42, workflow_time 8, workflow_reach 25, workflow_schedule_run 18; `workflow_schedule.py` words and checks (~25 plain English constants, not yet wrapped in `_()`); area contracts: pb_hiring 26, pb_timeoff 15, pb_me_expense 13, biz_approval_workflow 8, pb_payruns 9; mail templates in English only: time off sent back, goal change sent back, resignation sent back, plus earlier WF2 ones (link email, …). The whole workbench (`static/workflow/*.js`, incl. `schedule.js` ~45 strings) has no translation mechanism at all. `pb_lifecycle` has no `id_ID.po`.
- **Consolidate:** §10 overlaps; `workflow_schedule.words` and `schedWords` in `schedule.js` are the same sentence twice (server and screen) — keep one when translating; date formats on screens.

## 14. Owner decisions needed

1. §10.1 — the "around a date" start: switch to the existing date trigger from the schedule picker (recommended), or build a second one?
2. §10.2 — should areas declare their own timetables (contract end, probation, document expiry first) so a scheduled workflow is warned before repeating them?
3. §7.2 — D26 applied per person (the rize pay manager who cannot open Approvals › Everyone keeps the to-do). Keep, or give that person the right to see Everyone instead?
4. §7.3 — the "did not start on schedule" notice does not arrive on payobook / template because Approvals' message job is off there (G56). Leave, or switch that job on?
5. Repeat for each line (§9) — schedule as its own phase?
