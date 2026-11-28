# WORKFLOW-2 · Phase 5c report — repeat for each line, and three small decisions

Builder: Claude (Opus implementation agent), 12 November 2026. Handover: `WF2_P5C_HANDOVER.md` (design: `WF2_P5A_HANDOVER.md` §3.3–3.4). Ledger: `WF2_LEDGER.md` (gotchas G72–G79 added, P5c row marked).

## 0. In plain words (for the owner)

- **Repeat for each line is built and live on all five sites (payobook, payobook_template, p0clone, rize, sudima).** A workflow can now do the same steps once for every receipt on an expense claim, every answer to a list question, or every person on an Approvals team. Each line is its own little run: "Check receipt · Taxi to airport · 9 Nov · receipt 1 of 3". The lines can run together or one by one, and the workflow carries on when every line is done (or the first one, if you choose). A line that gets stuck shows "1 of 3 lines needs attention" with a Retry for that line only.
- **People see the line everywhere they work**: the Approvals inbox (with one heading per repeat and a "Do all in turn" button that opens the next one by itself), the task page, the employee home, the record's strip ("1 of 3 receipts done"), the progress page (one row per line) and Activity ("Show lines").
- **Building it**: "Repeat for each…" is under More possibilities. It draws as a dashed frame with a "For each receipt" chip on Journey, By stage, Across and the Flowchart canvas; steps go in with the "+" inside the frame or by dragging; the side panel shows a live example ("EXP/2026/0701 has 2 receipts: Small · 10 Nov, Big · 11 Nov").
- **A workflow without a repeat looks and works exactly as before** — proven pixel for pixel on the Flowchart canvas and byte for byte on the server's checks and Try it out.
- **"Around a date"** is now a choice in the schedule picker. It switches the workflow to the existing "At a record date" start and shows its settings right there; picking Every day / week / … switches back. Nothing is built twice.
- **Contracts, trial periods and employee documents now tell Studio about their own reminders** (read from their real settings). Studio lists them under "Already happens" and warns before a date-based workflow reminds the same kind of person a second time.
- **New right "See everyone's approvals"** (read only) exists on every site and is **given to nobody**. It lets a person open Approvals › Everyone and read any request in their company — nothing else. The main loop can now give it to Debalina on rize from Access (D32).
- **P2b's three browser checks** were finally looked at: the joining checklist says "Chosen in Hiring by …", the employee claim page shows the strip only when a workflow is involved, and the dock says "No approvals are waiting on you." under the task line. One real problem found and fixed on the way: a repeat on a claim did not show its strip on the employee claim page.

## 1. Commits, versions

| Commit | What |
|---|---|
| `771b5b78a` | D30 "Around a date" in the schedule picker; D31 timetables declared by contracts (`pb_contract_lifecycle`), trial periods (`pb_probation`) and employee documents (`pb_employee_vault`), Studio's window warning; tests s1, s2 |
| `63690618a` | D32 "See everyone's approvals": group, read-only rule, Access ability (`pb_lifecycle/security/approvals_see_everyone.xml`), Everyone gate by inheritance; tests s3, s4; `pb_lifecycle` 19.0.1.18.0 |
| `6afc5a89a` | Repeat for each line: engine, expense receipts door (`pb_me_expense/models/workflow_lines.py`), people surfaces, workbench, inbox; in-app notice fix (G72); tests t1–t12; browser scripts; cache keys `wf2-p5c` |
| `b4942f2fb` | "Around a date" starts three days before the date (was: on it) |
| (docs commit) | This report and the ledger |

Not pushed. Versions: **`pb_lifecycle` 19.0.1.18.0** (data: one group, one rule, one ability; new columns on `pb_workflow_run`). **Not bumped** (method-only files, restart-loaded, ledger G29): `pb_me_expense` 19.0.1.2.0, `pb_contract_lifecycle` 19.0.1.3.2, `pb_probation` 19.0.1.5.0, `pb_employee_vault` 19.0.1.5.0. **`biz_approval_workflow` and `pb_approval_config` not touched at all** (see deviation 1).

## 2. Tests

### Backend — Studio suite (local `am_wf2p5c`, clone of `am_wf2p5a`)

Before: **132/132**. After: ****149/149**** (132 + 17). The run on the clean commit used a separate worktree so that another session's uncommitted files were not loaded.

| # | Test | Result |
|---|---|---|
| s1 | `test_wf2p5c_s1_around_a_date_switches_both_ways` — schedule → "Around a date" (date start, 3 days before) → valid, filters unchanged, schedule kept to go back → "Every week" → valid | pass |
| s2 | `test_wf2p5c_s2_area_timetables_declared_and_warned` — each of the three declared from its own setting (changed in the test, the words follow), listed in "Already happens"; a date start 5 days before with a named person's task → `repeats_existing`; another date → none; kept on purpose → acknowledged; 300 days before → none; active job ids identical | pass |
| s3 | `test_wf2p5c_s3_see_everyones_approvals_reads_and_nothing_more` — without the right: no Everyone, request not found; with it: Everyone on, request read in both scopes; decide (engine and inbox), cancel, repair, write, creating a route → all refused, request still pending; no set-up / HR manager right; another company's request hidden; D26's `pay_group_rest` treats the holder as "can see Everyone" (no to-do) | pass |
| s4 | `test_wf2p5c_s4_nobody_has_the_new_right` | pass |
| t1 | repeat basics — 4 answers together → 4 lines, parent waits, steps live on lines only; answers → counts `count 4, done 4, check__fine 3, check__missing 1`; "any" → first done carries on, the others stopped with no to-do left; one by one → in order | pass |
| t1b | receipts snapshotted — a fifth receipt added after the start is not picked up | pass |
| t2 | limits and refusals — 3 lines over a cap of 2 → step stops "There are 3 answers, more than the 2 …", nothing started; refused by code: `repeat_matrix`, `repeat_stage_move`, `repeat_start`, `repeat_update`, `repeat_nested`, `repeat_parallel`, `repeat_cap`, `repeat_source`, `empty_repeat`, `repeat_send_back_outside`, `line_owner` | pass |
| t3 | people — "the person on the line" from a team source; inbox card "Check in · <name>", "person 1 of 2", group key; another person cannot see or answer it; task detail and link/home page carry the line; a team inside a repeat still works; six line tasks → one card "Check it · 6 to do"; counts still count each task | pass |
| t4 | failure — one line fails (its person switched off) → repeat "1 of 3 lines needs attention", run needs attention, progress lists each line; healthy lines carry on; Retry that line → back to waiting, the others untouched; Retry on the repeat retries every failed line; "Stop here" inside ends that line only | pass |
| t5 | values — a path on `line.value`, a notice "Please look at {{line.value}} ({{line.number}})" filled, a path after the repeat on `step.rep.check__missing ≥ 1`; Try it out walks one sample line and says "…and the same for …" | pass |
| t6 | generic sources — line items ("Hotel", "Bus") with `line.amount > 50` steering each line; no answers → nothing to repeat, carries on | pass |
| t7 | exclusions — runs table without lines by default, with lines on request; record progress, strip (one row, "0 of 3 receipts done", "next for you: …"), no start event for a line, "where time goes" counts one run and does not rank line steps | pass |
| t8 | isolation and guards — lines share the parent's company/version/starter; another company's person sees no line task; no status write or record write in the new files; banned words in new strings | pass |
| t9 | scheduled workflow with a repeat — preview counts 2 records (never lines); two worker passes → 2 parents, 6 lines, 6 distinct start keys, one history row | pass |
| t10 | send back inside a line — line A goes back to its own form with the note, line B untouched, then both finish and the run is done | pass |
| t11 | no repeat byte-identical — three definitions (receipts check with send back and notice; parallel + saved group + stop; a scheduled one with errors): `validate` and Try it out output equal to a golden file written by the pre-phase code | pass |
| t12 | performance — 200 receipts (numbers in §3) | pass |

Also run: the area reminder suites (contract extension, employee vault, probation verdict and review-journey tests): **26/26 before and 26/26 after**; the approval suites (`biz_approval_workflow` + `pb_approval_config`, all test modules, read in a shell that rolls back): **198 run, the same 4 failures before and after** (`test_the_look_invents_no_colour_and_carries_no_gradient`, `test_u13_the_catalogue_covers_the_whole_exported_template`, `test_z06d_every_p7_block_is_filled_in`, `test_z06e_no_p7_translation_loses_a_placeholder`). The count is now 198 (was 175) because UPDATES P6 added tests today.

### Browser (local `am_wf2p5c_ui`, Playwright with real mouse, Chrome headless; screenshots looked at)

Scripts: `tools/workflow_studio/chrome_test_p5c.cjs` (fixture `ui_fixture_p5c.py`, local logins with random passwords kept outside the repo) and `tools/workflow_studio/chrome_test_p2b_u357.cjs`.

| # | Result |
|---|---|
| Canvas pixel diff | pass — two shipped drafts without a repeat (ids 1166 and 672), Flowchart surface screenshotted with this phase's file blocked and loaded (the test proves which page ran which code): **PNG bytes identical and HTML identical** for both |
| U4 | pass — "Repeat for each…" by click (title "For each receipt" from the claim's receipts); "+" inside the frame offers only what may run per line (no approval, stage move, hand-over or repeat); a task dragged into the frame on Journey (real mouse); frame on By stage, Across and Flowchart (chip "For each receipt", join "Every one done"); dragged back out on the canvas |
| U5 | pass — live sample "EXP/2026/0701 has 2 receipts: Small · 10 Nov, Big · 11 Nov."; together / one by one, carry on, at most N; refused types never offered |
| U6 | pass — checker's inbox: heading "Check receipt · EXP/… · 3 to do, one for each line · Do all in turn", cards "Check receipt · Taxi to airport · 9 Nov" with "receipt 1 of 3"; six on one claim → one card "Check receipt · 6 to do" with "Do all in turn"; drawer shows "Doing all in turn · 3 left"; task page shows the line chip; after "Looks fine" the next line opened by itself ("Hotel Hanoi · 10 Nov"); progress page lists each line (state, who); record strip "0 of 3 receipts done" |
| U7 | pass — employee home list "Read and confirm: Confirm this receipt is yours · Parking · 10 Nov"; task page "… · receipt 1 of 2" and its strip "0 of 2 receipts done · next for you: …" |
| U8 | pass — a line that needs attention shows on the progress page with Retry; Retry → that line waiting again, the run back to waiting |
| U11 | pass — 390 px: repeat inspector and the inbox, no sideways scroll (`scrollWidth` 390) |
| D30 | pass — "Around a date" switches to "At a record date" (date "Sent on", before) with How often shown above; "Every week" switches back |
| P2b U3 | pass — Hiring joiner (P2b T13 replayed into the local database): Journeys › the case › Finished › "Choose their buddy · Chosen in Hiring by DEMO P2b Boss on 12 Nov 2026." (not on the case form's step list — G79) |
| P2b U5 | pass after a fix — employee claim page with a workflow: strip "0 of 2 receipts done · next for you … · Do it now"; plain claim: no strip. **Found and fixed:** with a repeat the strip was missing (D23 asks "does it add something?" by who the run waits for; the repeat row said nobody) |
| P2b U7 | pass — dock for a manager with workflow tasks and no approvals: "52 workflow tasks for you" / "No approvals are waiting on you." |
| Console | clean of workbench and inbox errors; one environment error on the claim form after a local restart (`web_tour.interactive` lazy bundle failed to load once) |

## 3. Performance (local laptop, load average 6–7 from other sessions)

| What | Time |
|---|---|
| Starting 200 lines in one go (worker or a test) | 22–28 s (all lines, tasks and to-dos made) |
| A worker pass with 200 lines waiting | 6.5–8 s (inside the job's minute) |
| Inbox read of 200 line tasks for one person | 0.8–0.9 s, **1 card** |
| A person's own click that reaches a repeat | starts at most 25 lines (about 3 s); the worker starts the rest on its next pass (G78) |

## 4. Deploy evidence

One normal-tier deploy (additive columns on `pb_workflow_run`; one group, one read-only rule, one Access ability; nothing rewritten) through the notes file and `flock /tmp/payobook-studio-deploy.lock`. Another session (UPDATES P6) was deploying `pb_approval_config` at the same time: I waited for its DONE (11:13 UTC) and checked that only the one service process was running. START **11:13 UTC**, DONE **11:21 UTC** (432 s, **417 s down**). Script: P5a's, adapted (`/tmp/wf2-p5c-20261112T111357Z/wf2p5c_deploy.sh`); launched with no "odoo-bin" in the ssh command (G62).

- **Before:** the five server trees (pb_lifecycle, pb_me_expense, pb_contract_lifecycle, pb_probation, pb_employee_vault) hashed identical to the repo at `f030318ce` (the commit before this phase) — the script stops if not; nobody else's work overwritten. `pb_approval_config` not touched.
- Clean staging from `git archive b4942f2fb` → service stopped → scoped `rsync -a --delete` per module (trees before in `/odoo/backups/wf2-p5c-20261112T111357Z/*-before.tgz`) → `-u pb_lifecycle --no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize (all exit 0, 0 ERROR/CRITICAL) → Studio suite on p0clone **149/149** → sudima last (exit 0) → no job newly switched on anywhere → probe ×5 → asset signal + purge ×5 → service started → sites 200.
- **Tree hashes** server = repo at `b4942f2fb` for all five modules. **`latest_version`** in all five: pb_lifecycle **19.0.1.18.0**; pb_me_expense 19.0.1.2.0, pb_contract_lifecycle 19.0.1.3.2, pb_probation 19.0.1.5.0, pb_employee_vault 19.0.1.5.0 unchanged; pb_approval_config 19.0.1.8.0 (UPDATES P6's), biz_approval_workflow 19.0.1.7.1 untouched.
- **Active job id lists** before = after on all five: 50 / 32 / 39 / 82 / 81. Sudima's Studio job still **off**.
- **The deploy sent nothing.** Emails / outgoing / Approvals outbox / to-dos identical before → after on all five (payobook 3,135 / 0 / 161 / 391; template 0 / 0 / 0 / 0; p0clone 34 / 17 / 8 / 9; rize 845 / 0 / 123 / 89; sudima 18 / 0 / 6 / 4). rize messages +4 = the upgrade's job-name change notes (G64); nobody notified.
- **Probe ×5:** 0 workflows switched on, 0 live runs, 0 line runs; the nine new run columns present; repeat step type present; **"See everyone's approvals" exists with 0 users** (direct and implied) and its ability is in no role; expense claims declare "receipts"; the three timetables declared (contract decision raised by itself: on for payobook, off elsewhere; trial review opened by itself: on for payobook, off elsewhere; the HR reminders on everywhere); the inbox additions are in the backend bundle.
- **Service:** exactly one process (`python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf`). 0 ERROR/CRITICAL in the five upgrade logs and in the service log since the restart. `index.html?v=wf2-p5c` references `repeat.js?v=wf2-p5c`, which is served (200).
- **Signed-in live look: not done** (no live session in this run). For the main loop, read only: Workflow Studio › any workflow › More possibilities lists "Repeat for each…" (do not save); Start → On a schedule → "Around a date" shows (do not save); Access › abilities lists "See everyone's approvals" (do not grant — the main loop grants it to Debalina on rize, D32).
- Evidence: `/tmp/wf2-p5c-20261112T111357Z/` (steps, upgrade logs, suite, probe, job and queue snapshots, versions, hashes, warm, processes).

Nothing published, switched on, created, approved, granted, moved or sent. ABM untouched. Rollback: the tree tarballs above + `-u pb_lifecycle` (the new columns and group then stay, unused).

## 5. Where the new right lives, and what it can read

- **Group** `pb_lifecycle.group_approvals_see_everyone` "See everyone's approvals", defined in `pb_lifecycle/security/approvals_see_everyone.xml` (pb_lifecycle already depends on `pb_approval_config` and is upgraded in this deploy; the Approvals modules are not bumped).
- **Reads:** every approval request of the companies the person works in (record rule `[(1,'=',1)]`, read only; the global company rule still applies, so other companies stay hidden). Steps, seats and decisions already had company-only rules.
- **Opens:** Approvals › Everyone (`_can_org` extended by inheritance in `pb_lifecycle/models/workflow_inbox.py`). D26's pay to-do check asks the same method, so a pay manager holding it no longer gets the per-step to-do.
- **Cannot:** decide, move, repair, cancel, write, or open set-up — the engine checks seats and the set-up/admin groups, which this group does not imply (test s3).
- **Side effect to know:** like the set-up right, it also widens "All I can see" in the inbox to the company's requests (the inbox's own tab reads what the record rules allow).
- **Granted from:** Access, ability "See everyone's approvals" (area System), with the usual audit row. **Granted to nobody by the deploy** (users 0 on all five sites, §4).

## 6. The three reminder timetables, as declared (plain words)

| Area | Record | What it says in "Already happens" | Read from |
|---|---|---|---|
| Contracts | contract, end date | "60 days before a contract ends, its manager can be asked to decide what happens next (raising these by itself is switched off here)." — or "… is asked …" where it is on. "While a contract decision is still open, HR is told halfway to the end date, and every day in the last 7 days." | `pb_contract_lifecycle.lead_days`, `.auto_trigger`, `.nag_days` |
| Trial periods | employee, trial end date | "21 days before a trial period ends, a review can open for the manager (opening these by itself is switched off here)." (or "… a review opens …"). "While a trial-period review is open, HR (or else the manager) gets a to-do 15 days and again 5 days before the trial period ends." | `pb_probation.evaluation_lead_days`, `.auto_trigger`, `.remind_days_far`, `.remind_days_near` |
| Employee documents | employee document, expiry date | "30 days before a document expires, HR gets a to-do on the employee to renew it." (minimal read-only contract added for documents: no stages, nothing a workflow may set) | `pb_employee_vault.expiry_warn_days` |

The warning: a workflow on those records that starts "At a record date" on the same date, no earlier than the reminder (or on a schedule for each record), and that tells or gives a task to the same kind of person (manager; HR = a named person, responsibility or team; an email to anyone) gets "Contracts already reminds people on its own timetable: … This step would remind them a second time." with "Keep it, it is different". A reminder switched off on the site does not warn.

## 7. Deviations from the handover

1. **The Everyone gate was not added to `ORG_GROUPS` in `pb_approval_config`.** Another session (UPDATES P6) had uncommitted edits in that very file and was deploying `pb_approval_config` today. Editing and shipping it would have mixed our work or overwritten theirs. The same effect comes from `pb_lifecycle` by inheritance (`_can_org`), and D26's check uses that method. `pb_approval_config` is untouched by this phase.
2. **"3 of 5 receipts checked" reads "3 of 5 receipts done"** — the verb is not known for every source; "done" is always true.
3. **Lines start 25 at a time inside a person's click**, the rest by the worker on its next pass (§3, G78). In the worker all 200 start in one pass.
4. **Send back over a repeat** (from a later step to one before it) is allowed: the repeat starts a fresh round and the open lines of the old round are stopped. Steps inside the repeat that make things (drafts) block such a send back, as any once-only step does.
5. **"Update the record", module actions, saved groups and "existing work" are refused inside a repeat** in addition to the handover's list (no area declares line-safe values yet; a module action or a saved group could hide an approval).
6. **Across** (not named in the handover) also draws the repeat as a labelled lane.
7. **In-app notice fix (G72)**: the person is now named on the step before the notice is sent. Without it a notice from a line (or from a new process to someone who did not start it) failed. Behaviour for every shipped case is the same.
8. **"Around a date" starts three days before** the chosen date by default (the shipped "At a record date" default is 0 days after).

## 8. R1 audit — every visible change to shipped screens

- **A workflow with no repeat: nothing changes** — canvas pixel-identical (§2), server checks and Try it out byte-identical (t11). Every workbench wrapper hands the shipped function its arguments and returns its output untouched unless a repeat is present.
- **Step list:** one more item, "Repeat for each…", in More possibilities (before "Change, tell and hand over").
- **"+" picker inside a path or group:** "Repeat for each…" is not offered there (it belongs on the main path); inside a repeat, only per-line steps are offered.
- **Schedule picker:** one more choice, "Around a date"; with "At a record date" the How often row shows above the date settings (record workflows only).
- **Inspector of a step inside a repeat:** a line "Runs for each receipt. Line details can be used in its rules and words."; "Who does this?" gains "The person on the line" when the line names a person; rules and notices offer "This receipt · Amount" etc.; steps after a repeat can use its counts.
- **Approvals inbox (Tasks group):** line tasks show their line ("receipt 2 of 3"), a heading with "Do all in turn" above a repeat's tasks, one card beyond five; the Tasks count counts each task. Nothing else in the inbox changed.
- **Task page / employee home / link page:** a line chip or the line in the title, only for line tasks. Employee-home task list shows the line in the name.
- **Record strip, employee claim page:** a run with a repeat says "1 of 3 receipts done" (and "next for you: …").
- **Progress page:** the repeat's panel lists each line with Retry; the steps inside show where the lines are. **Activity:** "Show lines" next to Refresh on workflows that have a repeat. **Where time goes:** a repeat row with "Each receipt usually …".
- **In-app notices:** unchanged for people; internally the step names the person first (deviation 7).
- **Already happens / Review:** contracts, employees and documents show their reminder rows; date-based workflows on them may get the new warning.
- **Approvals:** "Everyone" for holders of the new right (nobody yet).

## 9. Overlaps found (R2a)

1. **"Each person in a team" vs Approvals team tasks.** A repeat over a team gives each member their own task; a team step ("anyone on it can take it") gives one shared task. Different jobs, both reuse the same Approvals teams. Options: (a) keep both (recommended); (b) offer only one. No new feature added.
2. **"Do all in turn" vs the inbox's own order.** It only opens the next of the same repeat; it does not reorder or batch-approve anything. No overlap with Approvals' decisions. No decision needed.
3. **Line candidates for other areas (not built, per the handover):** pay run → payslips (safe and capped, the most useful next one), time off → days of a long leave, business trips → legs/expenses, assets → items on a handover, joiner checklist → equipment lines. Options: add them area by area through each area's own door when asked.

## 10. What is still weak

- Starting many lines is slow (22–28 s for 200 on the laptop); a person's click starts 25 and the worker the rest, so a big claim fills in over a minute.
- The progress canvas shows the steps inside a repeat once, with "x of y" words; the per-line detail is in the side panel only.
- Line details are read once at the start; a receipt edited afterwards keeps its old amount on the line.
- "Do all in turn" lives in the inbox only; the Studio "My tasks" page shows the line in the name but has no turn mode.
- The new words are English only (P5b).
- Area reminder suites and the approval suites: see §2 for what was run.

## 11. Self-score against the design bar

| Bar | Score | What is still weak |
|---|---|---|
| Hero moment (build "check every receipt", see each one land in the right inbox and work through them in turn) | strong | Live sample and "Do all in turn" make it feel immediate; a 200-line start takes a minute to fill in. |
| Zero dead-ends | good | Over the cap says the count and what to do; refused steps are never offered inside; a failed line has its own Retry. |
| Plain language | good | "For each receipt", "receipt 2 of 3", "1 of 3 lines needs attention"; no "loop", "iteration" or "index" anywhere (t8). |
| Motion / look | good | Dashed frame with a brand chip, same card grammar; no new motion. |
| Keyboard | good | Every new control is a native button/select/input; segmented buttons carry `aria-pressed`. |

## 12. Gotchas added (ledger G72–G79)

See `WF2_LEDGER.md`.

## 13. For P5b

**WORKFLOW-2 strings without Vietnamese / Indonesian (cumulative, all phases; counted by script on `_()` / `env._()` strings):**

| File | strings | no vi | no id |
|---|---|---|---|
| `pb_lifecycle/models/workflow_contract.py` | 39 | 39 | 39 |
| `pb_lifecycle/models/workflow_stage.py` | 58 | 57 | 58 |
| `pb_lifecycle/models/workflow_steps.py` | 70 | 69 | 70 |
| `pb_lifecycle/models/workflow_people.py` | 68 | 68 | 68 |
| `pb_lifecycle/models/workflow_people_design.py` | 22 | 22 | 22 |
| `pb_lifecycle/models/workflow_home.py` | 6 | 6 | 6 |
| `pb_lifecycle/models/workflow_strip.py` | 42 | 41 | 42 |
| `pb_lifecycle/models/workflow_time.py` | 8 | 8 | 8 |
| `pb_lifecycle/models/workflow_reach.py` | 25 | 25 | 25 |
| `pb_lifecycle/models/workflow_schedule_run.py` | 18 | 18 | 18 |
| `pb_lifecycle/models/workflow_schedule.py` | ~25 plain constants, not yet wrapped in `_()` | all | all |
| `pb_lifecycle/models/workflow_timetable.py` (P5c) | 2 | 2 | 2 |
| `pb_lifecycle/models/workflow_repeat.py` (P5c) | 64 | 63 | 64 |
| `pb_hiring/models/workflow_contract.py` | 26 | 22 | 26 |
| `pb_timeoff/models/workflow_contract.py` | 15 | 13 | 13 |
| `pb_me_expense/models/workflow_contract.py` | 13 | 10 | 13 |
| `pb_me_expense/models/workflow_lines.py` (P5c) | 6 | 4 | 6 |
| `biz_approval_workflow/models/workflow_contract.py` | 8 | 7 | 8 |
| `pb_payruns/models/workflow_contract.py` | 9 | 7 | 9 |
| `pb_contract_lifecycle/models/workflow_timetable.py` (P5c) | 4 | 3 | 4 |
| `pb_probation/models/workflow_timetable.py` (P5c) | 4 | 4 | 4 |
| `pb_employee_vault/models/workflow_timetable.py` (P5c) | 3 | 3 | 3 |
| **Total** | **510** | **491** | **508** |

Plus: the security/data words of P5c (group, rule, ability name and description); the inbox additions `pb_lifecycle/static/src/xml/workflow_inbox_lines.xml` (~6) and `workflow_inbox_lines.js` (1); English-only mail templates from earlier phases (link email; time off / goal change / resignation sent back). **The whole workbench has no translation mechanism** (`static/workflow/*.js`, roughly 466 distinct English phrases by a rough count, of which `repeat.js` ~29 and `schedule.js` ~22). `pb_lifecycle` has no `id_ID.po`.

**Consolidation candidates:** `workflow_schedule.words` and `schedWords` in `schedule.js` (same sentence twice); `_repeat_words` (server) and `repWords` (screen) — same idea twice; the inbox card and the Studio "My tasks" row both build the line words; date formats on screens.

**Known-failing baseline tests per module** (unchanged by this phase; ledger G60): `pb_me_portal` 8 (`TestMeHomeCards`, `TestMeHomeSource`, `TestPbMePortal`, `TestPortalOnlyDoors`); `pb_pay` 2 (`test_t4c` vi catalogue, `test_t11` pot name); `pb_timeoff` `TestLeaveRules` 6 (field access on `pb_policy_exception_by`); `pb_hiring` 14 (list in the P2b run logs); approvals 4 (`pb_approval_config` look / translation tests). This phase: Studio 149/149, area reminder suites 26/26, approval suites unchanged (§2).

## 14. Owner decisions needed

1. **Give "See everyone's approvals" to Debalina on rize** (D32) — the right is live and given to nobody; the main loop grants it from Access.
2. **Where repeat should reach next** (§9.3): pay run payslips first? Each area is added through its own door.
3. **Should a person's click start every line at once** (slower page for big claims) **or 25 now and the rest within a minute** (as built)?
4. **Should "See everyone's approvals" also widen "All I can see"** (as the set-up right does today, §5) — or should it open only the Everyone tab? Keeping it as built is the simplest and matches the handover's "readable company-wide".
