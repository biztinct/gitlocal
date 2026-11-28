# WORKFLOW-2 · Phase 4b handover — progress where people already are, and where time goes

Designer: Claude (Fable), 11 November 2026. Implementer: Opus agent, same session.
Read first: `WF2_LEDGER.md` (R1–R9, D1–D21, conventions §3, gotchas G1–G45 — binding), `WF2_P4A_REPORT.md` (§4 deploy, §7 deviations, §11 "What P4b needs to know"), then this file. Baseline: `pb_lifecycle` 19.0.1.14.0, 111 tests green, live ×5. Target **19.0.1.15.0**.

Design bar (owner, verbatim, binding): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** Lucide SVG icons, never emoji. Brand indigo `#5A4BB0`, one solid primary button per bar. Every state designed (empty, loading, error, partial, huge).

White-label (binding): "Odoo"/"OdooBot" never in anything a person can see or receive. Plain English (R8): no model or field names, no "state", "run", "node", "anchor", "gate", "SLA" on a screen.

## 1. Scope

1. **Progress on the record's own screen (staff).** Any record that has a workflow running, or sits in a user-made stage, shows a slim progress strip at the top of its own screen: the stage track, one sentence about who it is waiting for, and — for the right person — "Move to…" and "Do it now". Today people must open "View workflow" from the action menu (hidden entry point, review finding).
2. **Progress on the employee home.** The same strip (server-rendered) on an employee's own request pages and a one-line progress on "My requests" rows. "Move to…" there for the person a stage names.
3. **Status words compared (D12).** Produce the list of differences between each area's words in Studio and on the employee home. Change no shipped wording in this phase.
4. **Where time goes.** A panel in a workflow's Activity tab: time per stage and per step, how often late, where records are sitting now.
5. **"The candidate" as a participant (D18).**
6. **Late with no manager → a named role (D19).**
7. **Dock: one line with the task count (D20).**
8. **P4a polish:** the inbox task card reads heavy next to approval cards; the task drawer boots the workbench a second time.

### Binding non-goals

- No change to any area's own status bar, buttons, stage board or approval display. The strip is added above; nothing is moved, hidden or restyled (R1). Do not replace the "View workflow" / "Set up workflow" menu items.
- The strip never shows on records with nothing to show (no run, no user-made stage position). No empty frame, no layout shift on those records — this is every record on live today.
- Studio still never writes a module's status (R2c); "Move to…" moves only among user-made stages through the shipped `move_record_stage` rules.
- No rewording of employee-home status maps (owner decides after seeing the list).
- No new scheduled job; job counts 49/31/38/81/80; sudima's Studio job off.
- No version bump of `biz_approval_workflow`, `pb_approval_config`, `pb_me_portal`, `pb_me_team`, `pb_mission` unless proven necessary — stop and report first (G29). `pb_hiring` and `pb_me_expense` may be bumped if a view/asset of theirs must change; report reverse dependents first.
- No translations, schedule trigger, "Repeat for each line" (P5). No message clean-up (P2b).

## 2. Verified plumbing

- Record form hook: `pb_lifecycle/static/src/js/workflow_studio.js:53-98` — a `FormController` patch that calls `pb.workflow.studio.record_runs(model, id)` (`workflow_progress.py:106`, returns `runs`, `approvals`, `record_stages`, `can_design`) and adds two action-menu items; buttons template `static/src/xml/workflow_record.xml`. This runs on every backend form already, so the strip costs no extra request if `record_runs` is extended to carry the strip's data.
- Data for the strip: `record_stage(model, record_id)` `workflow_stage.py:650` (track states done/here/later/passed/stopped, waiting sentence, who may move); `move_record_stage(model, record_id, stage_id)` :613; `progress(run_id)` rows now carry `team`, `covering`, `link`, `done_by`, `due` (P4a §11). Iframe-only renderer today: `static/workflow/record-context.js` `stageTrail()` :3 — reuse its markup rules and class tokens, do not invent a second look.
- Where records are shown: expense claim = native form with statusbar `pb_me_expense/views/expense_claim_views.xml:40` (opened from `pb_expenses_hub/static/src/js/claims_lens.js:94`); leave = native `hr.leave` form (`pb_timeoff/static/src/js/pb_timeoff.js:239`); Other request and pay run = their own forms/cockpits (find and report); candidate = OWL drawer inside `PbHiringBoard` (`pb_hiring/static/src/js/hiring_board.js:155`, `openCand` :2048 → `pb.hiring.get_candidate`, template `hiring_board_p1.xml`), not a form — the FormController patch does not reach it.
- Employee home: `/my` expense claim page template `portal_expense_claim` `pb_me_expense/views/portal_templates.xml:378` ("With X (step)" :448 from `status()` `models/me_expense.py:466-494`); "My requests" sources `_my_requests_sources()` `pb_me_portal/models/pb_me_home.py:739`, rows `_my_requests_rows` :864, `get_my_requests` :897; P4a pages `/my/todo`, controller `pb_lifecycle/controllers/my_tasks.py` (ownership `_home_task(person, id)`), hooks `_wf_needs_rows(emp)`, `_wf_notice_card(emp)`.
- Status word sources: Studio = each contract's `stages[].name` (`pb_me_expense/models/workflow_contract.py:18-38`, `pb_timeoff/…:18-41`, `biz_approval_workflow/…:19-42`, `pb_payruns/…:22-37`, `pb_hiring/…:43`). Employee home = `pb_me_expense/models/me_expense.py:455` `_labels()`, `pb_me_expense/models/pb_me_home.py:56-62`, `pb_me_portal/models/pb_me_home.py:774-782` (leave), :787-797 (timesheet fix), `pb_timeoff/models/pb_timeoff.py:213`. Others: `CLAIM_STATES` `expense_claim.py:46`, `PB_STATES` `hr_payslip_run.py:51`, `generic_request.py:53`.
- Time data: step `started_at`, `done_at`, `due_at`, `reminded_at`, `passed_up_at`; run `create_date`, `ended_at`; record position row `entered_at`, `late_told_at` — **one row per record, overwritten on each move** (`workflow_stage.py:69`, :351-355); history only in `pb.workflow.log` ("Moved to" rows carry `stage_id` :734; "Left" rows do not :358-363; nothing logged when the record has no run). Stage target `target_hours` :41. Approval steps `activated_at`/`decided_at` (`biz_approval_workflow/models/request.py:146-147`). Activity tab today: `static/workflow/app.js:87` `activity()`, fed by `runs()` `workflow_studio.py:788`; no averages anywhere.
- Late seam: `biz.approval.engine._escalate_extra(now)`; pass-up target today = line manager → publisher of the run's version (P4a deviation 7). Roles: `biz.approval.responsibility.resolve(company, role, scope_keys, on_date=None)` `responsibility.py:90`.
- Inbox seam: `pb.approval.inbox._extra_items/_extra_counts`; dock reads `queues.tasks` on the server already (P4a deviation 2), screen `pb_mission/static/src/js/pb_dock.js:47`.
- Owner kinds: `workflow_definition.py:17` (+ `team` from P4a); subject resolution through the contract's `_workflow_subject`; Hiring's contract names the recruiter as the subject (P4a deviation 5). Link steps: P4a `access_token` path, `/workflow/t/<token>`.

## 3. Design

### 3.1 The strip on record screens (staff)

- One OWL component `WorkflowStrip` in `pb_lifecycle/static/src/js/` (new file + xml + scss), mounted by the existing FormController patch **above the form sheet** only when `record_runs` says there is something to show (reserve no space otherwise; decide before first paint from the same call so nothing jumps — if the answer arrives after paint, slide in with the shipped 160 ms ease, never a jolt).
- Content, left to right: workflow name chip → the stage track (same states and tokens as `stageTrail()`; user-made stages and the module's own, current one "Here now", long tracks collapse the middle to "+3" with a popover) → one sentence ("Waiting for Lan Tran: Check receipt · due Friday" / "Waiting for Payroll team — nobody has taken it" / "Late by 2 days" in the shipped late colour / "Done on 4 Nov") → on the right one primary at most: "Do it now" (opens the P4a task drawer in place) when the viewer is the person it waits for, else "Move to…" (menu of allowed stages, shipped rules and refusals shown inline) when the viewer may move it, else a quiet "View workflow" link (the existing action). More than one workflow on the record: a small switcher "2 workflows".
- `record_runs` gains a `strip` key built server-side in plain words (one call, no N+1; cap the work; a failure returns no strip and logs — a Studio fault must never break another module's form). Access: only what the viewer could already see through "View workflow" (same check).
- Not a form (OWL cockpits): export the component and a helper `loadWorkflowStrip(orm, model, id)`; register the component in a registry category `pb_record_strips` so a cockpit can render it **if present** without importing pb_lifecycle (soft link). Use it in the Hiring candidate drawer (small add-only slot at the top of the drawer body) and in any of pay run / Other request that turns out not to be a native form. If the claims lens or leave queue show a drawer before the form, add the slot there too only if it is a two-line change; otherwise report.
- States to design and screenshot: nothing (absent), one stage of many, last stage, stopped, late, waiting for a team, waiting by link ("Waiting for m***@… by email link · Send again" for people with progress rights), two workflows, 390 px (track becomes "Stage 2 of 5 · Approved" with a tap-to-expand), dark-on-light contrast AA.

### 3.2 The employee home

- Server-rendered twin (QWeb template `pb_lifecycle.workflow_strip_page`) with the same data and look, used:
  - on the employee's own expense claim page (inherit `portal_expense_claim` from pb_lifecycle — if pb_lifecycle does not depend on pb_me_expense, put a `t-call` slot in pb_me_expense that renders only when the template exists, or report the cleanest option) and on the leave / Other request detail pages the employee home has (find them; list which pages got it and which have no page);
  - on `/my/todo/<id>` above the task (where am I in the whole thing).
- "My requests" rows: when a request has a workflow or user-made stage position, add one quiet line under the existing status ("Step 2 of 4 · with Finance") — the existing status word stays exactly as is.
- "Move to…" on those pages for the employee the current stage names as the person who may move it: `POST /my/todo/move` (csrf on; session login → employee → the same `move_record_stage` rule check with the user passed explicitly → sudo; never ids trusted from the form beyond record + stage, both re-checked).
- An employee sees only: stage names, the waiting sentence with first names/roles as the shipped employee pages already show them, and dates. No amounts, notes or other people's answers.

### 3.3 Status words (D12)

- Build `tools/workflow_studio/status_words.py` (run locally) that prints, per area, value → word in Studio (contract) vs word(s) on the employee home vs word on the area's own screen. Put the table in the report with a recommended single word per value. **Change nothing.** The strip uses the contract words on staff screens and, on employee pages, the word that page already uses for the area's own statuses (so one page never shows two words for one thing — test this).

### 3.4 Where time goes

- New model `pb.workflow.stage.visit` (record model+id, stage or area status value, workflow, company, `entered_at`, `left_at`, `entered_by`), written in `_set_position` (close the open visit, open the next) and when a contract status change is observed by the engine; kept even when the record has no run. No backfill invention: backfill only what `pb.workflow.log` "Moved to" rows prove, and say on the panel "Counting since 11 Nov 2026" when history is short. (New model: normal tier; ACL = progress viewers read, nobody writes by hand.)
- Facade `time_report(workflow_id, period)` → per stage: records that passed, median and typical-longest (90th) time, share past target, sitting now; per step: median waiting time for people steps split "waiting for the person" (`started_at`→`done_at`), late count, sent-back count, reminders and pass-ups; approval steps read `activated_at`/`decided_at` (read-only) and are labelled "Approval (managed in Approvals)". Medians in working hours/days in words ("1 day 3 h"); fewer than 5 records → "Not enough yet" instead of a number.
- Screen: a "Where time goes" panel at the top of a workflow's Activity tab (the runs table stays below, untouched): period switch (30 days / 90 days / all), a horizontal stage bar where width = share of total time, a ranked "Slowest steps" list (top 5, each row: step, who usually has it, typical time, late share, a quiet "Open step" that jumps to it in Build), and "Sitting now" (count per stage, click = the runs table filtered). Empty state: an illustration-free, friendly line "Nothing has run yet. Publish and start this workflow to see where time goes." Follow the house dataviz rules: one hue (brand indigo tints) + the shipped late colour only for late; labels on the bars, no legend to decode, numbers right-aligned; keyboard reachable; no chart library — plain DOM/SVG as the workbench does.

### 3.5 "The candidate" (D18)

- Hiring contract (`pb_hiring/models/workflow_contract.py`) declares extra participants: `participants: [{key:'candidate', label:'The candidate', login:false}]` with `_workflow_participant(key)` returning name + email of the candidate (never a user). Studio: generic support for contract participants as an owner kind (`participant`), shown in "Who does this?" under the record's own people; always reached by link (P4a path); Review says so. Refuse it on `task` steps that need a file/record field (P4a limit) with the plain reason. Double-up check: where Hiring already emails the candidate at that stage (contract effects), Review warns `repeats_existing`.
- Privacy: the link page for a candidate shows only the step's text and fields — no recruiter notes, no stage names other than the step title.

### 3.6 Late with no manager (D19)

- Workflow Settings gains one control: "If a task is late and there is no manager, tell…" → a role from Approvals › Who approves (single-person roles and teams), stored in the definition's settings (versioned with it). Pass-up order: line manager → this role (resolved in the run's company via `responsibility.resolve`) → the publisher. Words on the task/progress: "Their manager was told on …" / "HR lead was told on …". Empty role at publish → no error (falls back), a quiet hint.

### 3.7 Dock (D20) and polish

- `pb_dock.js`: one line "3 tasks for you" (singular/plural, hidden at zero) that opens the Approvals inbox on the Tasks group. If this needs a `pb_mission` upgrade, check dependents (G29) and report before doing it; a restart-loaded asset edit with an asset purge is enough for JS/XML.
- Inbox task card: drop the double emphasis (keep the "your turn" ring OR the left accent, matching approval cards' weight); before/after screenshot next to an approval card.
- Task drawer: do not boot the whole workbench twice — give the embed a light entry (only the files the task page needs) or keep one hidden frame warm; measure and report open time before/after.

## 4. Safety rails

1. The strip must never break or slow another module's screen: one RPC (the existing one), server work capped, all failures swallowed to "no strip" + a log line. Measure `record_runs` time on p0clone for a record with and without a run; report (target: no measurable change for records with nothing to show).
2. Employee pages: session login → ownership → sudo; csrf on; no ACL widening; only the fields listed in §3.2.
3. Candidate link pages expose nothing but the step (§3.5).
4. No status writes (static guard covers the new files). No approval decisions.
5. Company isolation on visits, time report, role resolution, participants.
6. Live: never publish/activate/start a workflow, never create or move anything, never send mail; `enabled workflows = 0, live runs = 0` before and after; never `abm`. (`pbf_preview` and `recruit_connect_20261023` no longer exist — the owner had them deleted on 11 Nov.)
7. Approval suites (`biz_approval_workflow`, `pb_approval_config`) identical before/after (175 tests, the same 4 known failures).

## 5. Test cases (`test_wf2p4b_tN_…`)

Backend
- T1 `record_runs` strip: absent for a record with nothing; for a running record gives track, sentence, the right single action per viewer (assignee → do it; mover → move; other → view); two workflows → both.
- T2 strip sentences: team untaken, covered, by link (masked email), late, stopped, done — each in plain words, no banned words.
- T3 strip fault isolation: an injected error inside the strip builder returns runs without a strip and does not raise.
- T4 employee page data: owner sees their own request's strip; another employee → not found; fields limited to the allowed set; one word per status on the page.
- T5 employee move: allowed for the named person; refused for others; refused to a stage the rules forbid; module status untouched.
- T6 visits: moving through stages writes closed/open visits; no run → still recorded; company kept; backfill creates only what the log proves.
- T7 `time_report`: medians and shares correct on a built fixture (hand-computed); under 5 records → "not enough"; other company's data excluded; approval step times read-only.
- T8 participant: Hiring declares "The candidate"; a confirm step to the candidate mints a link to the candidate's email; no email → design-time message; file-field form refused; `repeats_existing` where Hiring already emails at that stage.
- T9 late order: manager; no manager + role → role holder; no role → publisher; never the person themselves or the system account; other company's role holder never used.
- T10 dock/inbox counts unchanged for approvals; task count line data.
- T11 static guards (no status write; controllers check before sudo).

Browser (local; screenshots looked at; console clean)
- U1 expense claim form with a running workflow: strip present, nothing else moved (before/after overlay); a claim with nothing: pixel-identical to before.
- U2 "Do it now" opens the task drawer in place; done → strip updates without reload.
- U3 "Move to…" from the strip incl. an inline refusal.
- U4 leave form and one cockpit (candidate drawer) show the strip.
- U5 every strip state in §3.1 incl. 390 px.
- U6 employee home: My requests line, request page strip, `/my/todo/<id>` strip, employee "Move to…".
- U7 Activity › Where time goes: filled, short-history, empty; period switch; "Open step"; keyboard.
- U8 "The candidate" in the picker; link page as the candidate in a logged-out window.
- U9 Settings control for D19; dock line; task card before/after.
- U10 banned-word and brand scan over every new/changed screen and page.

## 6. Deploy and verify

As P4a (`WF2_P4A_REPORT.md` §4): notes file START/DONE "Claude WORKFLOW-2", flock, clean staging from `git archive`, service stopped, scoped per-module rsync with before-tarballs, `-u` only what is needed (`pb_lifecycle`, plus `pb_hiring`/`pb_me_expense` if changed) on payobook, payobook_template, p0clone, rize, suite on p0clone, sudima last; job id lists identical; asset purge ×5; restart; warm; hashes + `latest_version` ×5; 0 ERROR lines. Cache keys `wf2-p4b`. Live look on payobook.com, read-only, signed in with the QA login (ask nothing of the owner: the main loop holds it; if your browser session is signed out, do the unsigned checks, say so, and the main loop will do the signed-in look): an expense claim form opens with no strip and no console error; Approvals unchanged; Studio › a workflow › Activity shows the empty "Where time goes".

Commit per feature with explicit paths. Do not push.

## 7. Report back (`WF2_P4B_REPORT.md`)

Commits, versions; T1–T11, U1–U10; approval suites before/after; `record_runs` timing; drawer open time before/after; which screens and employee pages got the strip and which could not (why); the **status words table** with a recommendation per value; deploy evidence; deviations; R1 audit; Overlaps found (R2a); self-score vs the design bar; gotchas G46+ into the ledger; "What P2b and P5 need to know" (every place a message is sent to approvers/requesters that you passed while working; strings count for translation; where a schedule trigger would hook); owner decisions needed.
