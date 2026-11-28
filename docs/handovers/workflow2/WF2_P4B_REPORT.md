# WORKFLOW-2 · Phase 4b report — progress where people already are, and where time goes

Builder: Claude (Opus implementation agent), 11 November 2026. Handover: `WF2_P4B_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (gotchas G46–G54 added, P4b row closed).

## 1. Commits and versions

| Commit | What |
|---|---|
| `d360a4cfa` | Hiring: the candidate as a workflow participant (D18) — `participants` in the contract, `_workflow_participant('candidate')` → name + email, never a user |
| `1ba4171bc` | Studio engine: strip data (`record_runs.strip`, `record_strip`, `strip_move`), employee-home strip + `/my/todo/move`, My requests line, `pb.workflow.stage.visit` + `time_report`, participant owner kind, D19 `late_tell` role, migration 1.15.0, tests T1–T11, `tools/workflow_studio/status_words.py` |
| `5a22b1c11` | Screens: `WorkflowStrip` on forms and in the Hiring candidate drawer, workbench `insights.js` (Where time goes, The candidate, late-task role, who was told), lighter task embed, inbox card emphasis, dock task line |
| `8e691a858` | Fixes from the browser run (drawer portalled to body, alignment, z-order, Sass, open stays, plain error, lower-case owner words, dock wording) |
| (docs commit) | This report and the ledger |

Not pushed. Versions: `pb_lifecycle` **19.0.1.15.0**. `pb_hiring` stays **19.0.2.23.6** (Python method + static only; it is upgraded anyway as a dependent of `pb_lifecycle`). `pb_mission` stays as it was (static only, restart + asset purge, G29). `biz_approval_workflow`, `pb_approval_config`, `pb_me_portal`, `pb_me_team`, `pb_me_expense` untouched. Workbench cache keys **`wf2-p4b`** on the iframe, the inbox task URL, the strip's task URL and all 14 tags in `index.html` (`insights.js` is new, loaded last).

Reverse dependents checked before touching: `pb_hiring` → `rize_website` (only); `pb_mission` → none in the deploy set needed an upgrade (no version change).

## 2. Tests

### Backend — Studio suite

Local `am_wf2p4b` (clone of `am_wf2p4a`, `-u pb_lifecycle`): **122 tests, OK** (111 + 11). Server, `p0clone`: see §4.

| # | Test | Result |
|---|---|---|
| T1 | `test_wf2p4b_t1_the_strip_shows_only_when_there_is_something` — none on a claim with nothing; assignee → "Waiting for you: Check receipt" + **do**; progress viewer → named sentence + **view**; outsider with no rights → none; person a company stage names (no rights) → strip with track, no workflow detail, **move**; designer → move; refusal reason in words; two workflows → two rows; position only → "In … since …" | pass |
| T2 | `test_wf2p4b_t2_every_sentence_is_plain` — team untaken, late ("Late by N days", late tone), covered, by link (masked, Send again for viewers, full address nowhere), stopped, done; no banned word, no "run" | pass |
| T3 | `test_wf2p4b_t3_a_fault_in_the_strip_never_breaks_the_form` — injected error → `strip` None, rest of `record_runs` intact, one log line; same for `record_strip` | pass |
| T4 | `test_wf2p4b_t4_the_employee_page_shows_only_their_own_and_its_own_words` — owner sees it, another employee gets nothing; keys limited to stage track / sentence / dates / own task link; "here" uses the page's own word ("Approved — being paid"), rendered page never shows the contract word for that status nor the workflow name; My requests line "Stage n of m · with …", status word unchanged | pass |
| T5 | `test_wf2p4b_t5_the_employee_moves_it_only_when_the_stage_names_them` — other employee `who`; stage the rules forbid `gone`; automatic stage `auto`; model without a contract `gone`; named person ok, position written as them, claim status untouched | pass |
| T6 | `test_wf2p4b_t6_stays_are_counted_with_or_without_a_workflow` — two moves → one closed, one open stay, company kept, no hand-made rows; status change closes the stay; backfill rebuilds only what the history proves, never a stage never entered, runs once | pass |
| T7 | `test_wf2p4b_t7_where_time_goes_is_counted_right` — hand-computed: step median "3 h" over 5, stage median "3 h", slow ones "3 h", 60 % past a 2 h target, other company's 60 h stay excluded, shares sum to 100; 1 record → "Not enough yet"; never started → empty; approval step labelled and its request untouched; no progress right → refused | pass |
| T8 | `test_wf2p4b_t8_the_candidate_takes_part_by_link` — participant offered; Review note; link minted to the candidate's email, no user; link page shows no record or workflow name; no email → step stops "… has no email address on the record, so this cannot reach them."; file form `participant_cannot`; notice `participant_notice`; unknown key `bad_participant`; Hiring already emails the candidate at that stage → `repeats_existing` warning; stage mover refuses a participant | pass |
| T9 | `test_wf2p4b_t9_late_with_no_manager_tells_the_named_role` — manager first ("Their manager was told on …"); no manager → role holder ("WF2 P4b HR lead was told on …" in progress); no role → publisher; never the person themselves; other company's holder never used; bad role `late_tell`; `late_fallback` hint | pass |
| T10 | `test_wf2p4b_t10_the_dock_line_counts_tasks_and_leaves_approvals_alone` — `queues.tasks` +1, every other queue key identical, inbox counts identical | pass |
| T11 | `test_wf2p4b_t11_new_doors_check_first_and_never_write_status` — `/my/todo/move` checks the login before any system read and calls `_home_move(person, …)`; `_home_move` checks contract, company and the named person before `_set_position`; no status write or `_chain_engine_write` in the three new files; no `t-raw`; no `csrf=False`; unknown page → no strip; public user → no strip | pass |

### Approval suites (rail 7)

`-u biz_approval_workflow,pb_approval_config --test-tags /biz_approval_workflow,/pb_approval_config` on a fresh clone with this phase's code: **77 + 138 = 175, the same 4 known failures as P4a's before/after** (`test_static_contract…no_colour…gradient`, `test_u13_the_catalogue_covers…`, `test_z06d…`, `test_z06e…`), all in `pb_approval_config` translations/look, unrelated. Neither module's files changed in this phase.

### Browser (local server on `am_wf2p4b_ui`, Chrome; screenshots looked at)

| # | Result | Evidence |
|---|---|---|
| U1 | pass | Claim with a workflow: strip above the sheet, its edges lined up with the sheet's cards (112–1356 px = the status bar card); nothing else moved. Claim with nothing: no element added at all (no host, renderer starts at the content top) — DOM identical to before. |
| U2 | pass | Assignee (no progress rights) on the claim: "Waiting for you: Check receipt · due Monday" + **Do it now** → the task page in a drawer over the page (167 ms to the task); **Mark done** → drawer closes, toast "Done. It has moved on to the next step.", strip re-read without reload (it disappears for this person: nothing of theirs left). |
| U3 | pass | Designer: **Move to…** lists the four company stages → "Payment booked" → track moves to it at once. A person with one stage of their own: locked rows say "Only the person this is about can move this to …" / "Only Lan Tran can …"; pressing one shows the refusal inline, in red, under the sentence. |
| U4 | pass | Time-off form: "Leave handover · Waiting for you: Plan the handover · Do it now". Hiring candidate drawer (through the registry slot): "Candidate details · Waiting for Tuan Dang by email link (t***@example.com) · Send again · View workflow", compact track in the narrow drawer. |
| U5 | pass | Late (red dot, "Late by 3 days" in the late colour), team ("Waiting for Finance team — nobody has taken it yet"), by link (masked), two workflows ("2 workflows ›" switcher), stopped ("Stopped on 11 Nov"), stage only ("In Payment booked since 11 Nov · moved by Lan Tran"), long track ("+3" with a popover of names). Narrow (Chrome's minimum window, 500 px; the strip itself ~380 px): "Stage 3 of 8 · Approved" that opens to the full vertical track; button full width. |
| U6 | pass | Employee home (portal login): claim page strip with the page's own words ("Approved — being paid", same as the page's pill) and **Do it now** to `/my/todo/…`; `/my/todo/<id>` strip above the task, **Move to… → Receipts handed in** → "Moved. Everyone sees the new stage now." and the track shows it; My requests row: "Stage 5 of 8 · waiting for you" under the title, pill unchanged. |
| U7 | pass | Activity › Where time goes: bar (labels on the bar, one hue), stage table (Usually / Slow ones / Went through / Sitting now, "Not enough yet", "50 % past its 24 h target" in the late colour), "Counting since 1 Nov 2026.", Slowest steps with "Open step" → Build with the step selected; 30/90/All switch; "Sitting now 2" filters the runs table ("Showing the 2 sitting in Approved · Show all"); every control a real button (keyboard). Empty state proved by T7; error state shows a plain sentence. |
| U8 | pass | "The candidate (by email link)" in Who does this?, with its hint; card "The candidate · “I confirm”"; logged-out link page shows only the company and "Confirm your details". |
| U9 | pass | Settings: "If a task is late and there is no manager, tell…" (roles and "(a team)"), saved into the draft (`late_tell`). Dock: "2 workflow tasks for you" → opens Approvals on the Tasks group. Inbox task cards: the left accent is gone; the inbox's own ring is the one emphasis (no approval card in the fixture to stand beside it). |
| U10 | pass | Scan of every new `_()` string (69), template and workbench text: no framework name, no "state/model/_id/run/node/gate/anchor/SLA". The only "odoo" hits are technical (`<odoo>`, `@odoo-module`, `@odoo/owl`). No emoji. |

Console: clean on the backend pages and the workbench; the employee pages log the cloned database's missing website logo/favicon (500), as in P3b/P4a.

## 3. Timings

- **Task drawer open** (click → task page drawn), median of 6, designer login, local: **before 329 ms** (full workbench start-up) → **after 186 ms** (embed=1&task= skips the start-up call; `lightBoot` in `actions.js`). The inbox drawer gets the same gain (same URL). No hidden warm frame was added.
- **`record_runs` on p0clone** (records with nothing to show, administrator): claim 121 → 120 ms, time off 80 → 77 ms, employee 72 → 73 ms median — no measurable change. With a workflow running (local, fixture claim) the strip adds one sentence per workflow and the stage track to the same answer; no extra request from the form.

## 4. Deploy evidence

One deploy, normal tier (one new model, one additive column; no data rewritten), through the notes file and `flock /tmp/payobook-studio-deploy.lock` (read-only open, G9). No other START was open (UPDATES P2c had written DONE at 07:27). START `2026-11-11 07:50 UTC`, DONE `07:57 UTC` (384 s, 376 s down). Script: P4a's, adapted (`/tmp/wf2-p4b-20261111T075046Z/wf2p4b_deploy.sh`).

- Before: server trees of `pb_lifecycle`, `pb_hiring`, `pb_mission` hashed identical to the repo before this phase (be9824f9…, 44822ab7…, 5c9b93b0…) — nobody else's work overwritten.
- Clean staging from `git archive` of `8e691a858` → service stopped (no `odoo-bin` left) → `record_runs` timing on p0clone with the OLD code → scoped `rsync -a --delete` of the three modules (trees before kept in `/odoo/backups/wf2-p4b-20261111T075046Z/*-before.tgz`) → `-u pb_lifecycle --no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize (all exit 0, 0 ERROR/CRITICAL) → timing with the NEW code → suite on p0clone **122/122** (`WORKFLOW_TEST_RESULT={"tests": 122, "successful": true, "failures": 0, "errors": 0}`) → sudima last (exit 0) → no job newly switched on anywhere → probe on all five → asset signal + purge on all five → service started.
- Tree hashes, server = repo at `8e691a858`: pb_lifecycle d039d786…c5e9, pb_hiring 8e568c05…fcc7, pb_mission be627e60…2689.
- `latest_version` in all five: pb_lifecycle **19.0.1.15.0**, pb_hiring 19.0.2.23.6, pb_mission 19.0.1.13.1 (unchanged).
- Active job id lists before → after byte-identical: payobook **50**, payobook_template **32**, p0clone **39**, rize **82**, sudima **81** (the handover's 49/31/38/81/80 predates UPDATES P2c's new job, G53). Sudima's Studio worker job still **off**.
- Probe (system environment, rolled back), all five: 0 enabled workflows, 0 runs of any kind, 0 company-stage positions, 0 stays (the 1.15.0 backfill made nothing), visit model and `passed_up_to` present, Hiring declares "The candidate", strip template and layout hook loaded, sample expense claim strip = none. So **no record on any live site shows a strip**.
- `record_runs` timing on p0clone (administrator, records with nothing to show, median): expense claim 121 → 120 ms, time off 80 → 77 ms, employee 72 → 73 ms — no measurable change (rail 1). (Only 2 claims and 2 leaves exist on p0clone; employees n = 12.)
- Logs: 0 ERROR/CRITICAL in the five upgrade logs and in the service log since the restart.
- Warm: payobook.com, p0clone, rize, sudima login pages 200; workbench `index.html?v=wf2-p4b` 200, `insights.js?v=wf2-p4b` 200; the link page still shows "This link has run out." for an unknown link.
- **Signed-in live look on payobook.com** (read-only, the browser's existing session): expense claim EXP/2026/0001 opens, no strip, no added element, no console error (one old icon-size warning from the brand manifest); Workflow Studio › "Test Expense" › Activity shows the empty "Nothing has run yet. Publish and start this workflow to see where time goes." with nothing saved (draft not dirty); Approvals opens with its tabs and counts (My turn 0, All I can see 8, Sent back 2, Finished 73, Late 7), no Tasks group, console clean.
- Evidence: `/tmp/wf2-p4b-20261111T075046Z/` (steps, upgrade logs, suite output, timing before/after, probe, job lists, hashes, versions, warm).

Nothing published, activated or started; nothing created or moved; no mail sent. ABM untouched.

## 5. Where the strip shows, and where it could not

| Screen | Strip? | Why |
|---|---|---|
| Every native backend form (expense claim, time off, Other request, pay run form, employee, …) | yes | One `FormController` hook (the existing `record_runs` answer); not in dialogs |
| Hiring candidate drawer (OWL cockpit) | yes | `pb_record_strips` registry slot, two lines in `pb_hiring` |
| Expenses claims lens / time-off board drawers | no | They open the native form; no separate drawer worth a slot |
| Pay run cockpit | no (form yes) | The pay run screen is its own cockpit with its own status track; a slot there is more than a two-line change — report only |
| Employee home: expense claim page `/my/expenses/<id>` | yes | Portal layout hook keyed on the page name (`HOME_PAGES`), no dependency on Expenses |
| Employee home: `/my/todo/<id>` | yes | Above the task, for the record the task belongs to |
| Employee home: My requests | one line | Under the title, status pill unchanged |
| Employee home: time off, Other request, equipment, resignation, overtime | no | These have no detail page (lists only); the My requests line covers them |

## 6. Status words compared (D12) — nothing changed

`tools/workflow_studio/status_words.py` (local `am_wf2p4b`). Only the rows that differ:

| Area | Value | Studio (contract) | Employee home: My requests | Employee home: request page | Area's own screen | Recommended single word |
|---|---|---|---|---|---|---|
| Expense claim | approved | Approved | Approved — being paid | Approved — being paid | Approved | **Approved — being paid** on employee pages, **Approved** on staff screens (it says what happens next to the person who is owed) |
| Expense claim | refused | Refused | Refused — your turn | Refused — see why | Refused | **Refused — your turn** on both employee pages (one word for the two employee pages); Refused for staff |
| Time off | confirm | To Approve | Waiting approval | — | form "To Approve", board "To approve" | **Waiting for approval** everywhere (plain, and the word Other request and pay runs already use) |
| Time off | validate1 | Second Approval | Waiting approval | — | form "Second Approval", board "2nd approval" | **Second approval** for staff; employee home keeps **Waiting for approval** (the employee does not need to know which round) |

Same everywhere (no action): Expense draft / waiting approval / paid; Time off approved / refused / cancelled; Other request, pay runs and candidates are not on the employee home (their words are the area's own). Other employee-home words that are not Studio areas yet (timesheet fix "With your manager", equipment "Waiting for the manager", resignation "With the manager") use three different phrasings for the same idea — a candidate for the same clean-up.

How the strip follows this today: staff screens use the contract word; employee pages replace the area's statuses with that page's own word (claim page: `_labels()`; My requests and `/my/todo`: the My requests word). Side effect worth knowing: on an employee page a leave shows "Waiting approval" twice in the track (to approve and second approval both read so).

## 7. Deviations from the handover

1. **Area-status times come from the area's own change history, not from a new write hook.** `pb.workflow.stage.visit` holds stays in company stages (written by the position row itself on create / stage change / removal, with or without a run). For the area's own statuses the report reads the tracked history (`mail.tracking.value`) at report time: exact times, history from day one, and no new write in any area's status change (safety rail 1). Pay runs' status is not tracked, so a pay run shows company-stage times only (G50).
2. **A person without "view progress" still gets a strip when it holds something of theirs** (their own waiting task, or a company stage they are named to move it into) — otherwise "Do it now" would almost never show (most task owners do not have that right). They see the stage track and their own sentence only, never other workflows' detail. The handover said "same check as View workflow".
3. **"Move to…" offers every company stage a person moves records into at the current status** (the shipped `move_record_stage` rules), not only the next one; locked rows show who may.
4. **My requests line says "Stage 5 of 8 · with Lan Tran"** ("Stage", not "Step": the track is the record's stages; steps are inside a workflow).
5. **No warm hidden frame**: the light start (skipping the start-up call) halves open time; a warm frame would hold a second workbench in memory on every inbox and form.
6. **Dock line reads "n workflow tasks for you"** (not "tasks"): the dock's own empty state right under it says "Nothing is waiting on you right now" (approvals); "workflow" keeps the two from contradicting each other.
7. **Expense claim page strip sits above the page header** (portal layout hook) rather than inside the claim body, because Studio does not depend on Expenses (no template inheritance across a missing dependency).
8. **Time report "who usually has it"** for teams shows the team name; link steps show "Someone by email link".

## 8. R1 audit — every visible change to shipped screens

- **Every backend form**: a strip above the sheet, only on records with a workflow or a company-stage position (none on live today). Header buttons, status bar, action menu items "View workflow" / "Set up workflow" unchanged.
- **Hiring candidate drawer**: the same strip between the drawer's navigation line and the details, only when there is something to show.
- **Employee home**: strip on the expense claim page and above `/my/todo/<id>`; one line under a My requests row; nothing on any other page.
- **Workbench**: Activity tab gains "Where time goes" above the unchanged runs table; Settings dialog gains one control; Who does this? gains "The candidate (by email link)" on candidate workflows; Review gains two "Who takes part" notes (candidate by link, late fallback); progress drawer gains "… was told on …".
- **Approvals inbox**: task cards lose the left colour accent (the ring stays); the task drawer opens faster. Nothing else.
- **Dock**: one line under the header when there are workflow tasks.

## 9. Overlaps found (R2a)

1. **Two "where is my request" displays on the expense claim page.** The claim page already shows "With X (approval step)" for the approval part and its own status pill; the strip adds the whole track and workflow sentence above. They agree (same words), but say part of the same thing twice while a claim is waiting for approval. Options: (a) keep both (now); (b) hide the claim page's "With X" panel when a strip is shown (an Expenses change); (c) show the strip only when a company stage or a workflow step (not just the approval) is involved. Recommend (c) at P5 consolidation.
2. **Dock empty state vs task line.** "All clear · Nothing is waiting on you right now" shows under "2 workflow tasks for you". Options: (a) keep with the clarified wording (now); (b) let the dock's empty state know about tasks (a pb_mission wording change). Recommend (b) — small, owner wording call.

## 10. Self-score against the design bar

| Bar | Score | What is still weak |
|---|---|---|
| Hero moment (open a record, see where it is and who has it, do it in place) | strong | The strip arrives just after the form (slides in, 160 ms); it is not decided before first paint because that would delay every form by one call. |
| Zero dead-ends | good | A person with a task but no "Move to" right sees no Move; an employee only sees "Move to…" on a request that already has a workflow or stage (by rule). |
| Plain language | good | Dates follow the reader's language but employee pages still print "Needed by 11/16/2026" (P4a page). "Due Monday" style words are English until P5. |
| Motion / look | good | Strip, menu, drawer, track and narrow view designed; screenshots at 1400 and 500 px. No real phone. |
| Data viz | good | One hue + late colour, labels on bars; very small shares carry no label (tooltip only). |
| Keyboard | good | Every control a button / summary; Escape closes the drawer and menu. |

Also weak: core-status times depend on the area tracking its status (pay runs do not); "sitting now" for area statuses counts only records with a live run of this workflow; the time report caps at 500 runs / 1,000 records per call.

## 11. What P2b and P5 need to know

- **Messages passed while working** (for P2b): the link email (`mail_template_workflow_link`, now also to candidates); approval-engine outbox kinds `task_reminder`, `task_passed_up` (now also to a named role, D19), `stage_late`; Hiring's own candidate emails (automation `send_email` to candidate, built-ins "received", "invite", "offer", "not this time"); the expense claim page's "Sent to X" toast; the team "New for your team" note. None changed in this phase.
- **Strings for translation (P5)**: about 69 new `_()` strings in `workflow_strip.py`, `workflow_time.py`, `workflow_reach.py`; 2 QWeb templates (`workflow_strip_page.xml`); the OWL strip template; ~45 workbench strings in `insights.js`; the dock line. The day words ("today", "Friday") come from the reader's language via `format_date`. Employee-home strip runs in the reader's language (`lang` from the login).
- **Schedule trigger (P5)**: a date-based start would hook beside `_cron_workflows`; "Where time goes" already reads `pb.workflow.run.create_date` per workflow, so scheduled starts show up there with no change.
- **Consolidation (P5)**: §6 status words; §9 overlaps; `HOME_PAGES` in `workflow_strip.py` is the one list of employee pages with a strip (add a page = one row).

## 12. Needs an owner decision

- §6 — the recommended single word per status (four rows).
- §9 items 1 and 2.
- Deviation 2 — a task owner without "view progress" sees the stage track of that record (recommended: keep).
- Whether a candidate who has no email address should be skipped (step marked "not needed") instead of stopping the workflow for a person to look at (now: it stops, plainly worded).
- Local databases left: `am_wf2p4b` (suite), `am_wf2p4b_ui` (browser fixtures, local-only passwords), `am_wf2p4b_appr` (approval suites). Local server stopped.
