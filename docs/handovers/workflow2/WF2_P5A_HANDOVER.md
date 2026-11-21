# WORKFLOW-2 · Phase 5a handover — start on a schedule, repeat for each line, last message decisions

Designer: Claude (Fable), 11 November 2026. Implementer: Opus agent, same session.
Read first: `WF2_LEDGER.md` (R1–R9, D1–D29, conventions §3, gotchas G1–G64 — binding), `WF2_P3B_REPORT.md` §6 ("What Repeat for each line would take"), `WF2_P4B_REPORT.md` §11, `WF2_P2B_REPORT.md` (§4 deploy as last done, §9, §11, §11b), then this file. Baseline: `pb_lifecycle` 19.0.1.16.0, 126 Studio tests, live ×5. Target **19.0.1.17.0**.

Design bar (owner, verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** Lucide SVG icons, never emoji. Brand indigo `#5A4BB0`, one solid primary button per bar. Every state designed.
White-label (binding): "Odoo"/"OdooBot" never in anything a person can see or receive. Plain English (R8): never "cron", "schedule expression", "sub-run", "loop", "iteration", "index" on a screen — say "every Monday at 9:00", "for each receipt", "line 2 of 5".

Order of work (ship what is complete and proven if the phase cannot be finished safely in one go, in this order): §3.1 → §3.2 → §3.3 → §3.4.

## 1. Scope

1. **Message decisions:** D26 (pay managers), D28 (sent-back emails, each area), and the small leftovers from P2b.
2. **Start on a schedule.** A workflow can start by itself on a date pattern ("every Monday 9:00", "on the 25th", "3 days before a contract ends"), for a new process or for each matching record.
3. **Repeat for each line.** A group of steps runs once per line of the record (each receipt on a claim, each day or each person in a list).
4. Every new string in English only this phase, written translation-ready (P5b translates).

### Binding non-goals

- **No new scheduled job.** Scheduled starts are evaluated inside the existing Studio worker job (`_cron_workflows`). Job id lists identical before/after on every database; sudima's Studio job stays off (D11) — which means scheduled workflows do not start on sudima until the owner turns that job on; say so in the Review of a scheduled workflow there ("This site's workflow clock is switched off.").
- Never write a module's status; never define or decide an approval (R2). An Approval Matrix step **inside** a repeat is refused at design time (one record, one approval).
- No change to shipped screens beyond the additions listed (R1 audit required).
- Do not drop `execution_user_id` (G7) — left for a later decision; report whether anything still reads it.
- No translations (P5b). No mail server on rize/sudima/p0clone (D29) — never raise it.
- Do not bump `biz_approval_workflow` / `pb_approval_config` (G29). For other area modules list reverse dependents first.

## 2. Verified plumbing

- Worker: `pb.workflow.studio._cron_workflows` `workflow_studio.py:971` (line may have moved; it is the one Studio job per database, id 89 on sudima and off there), `_check_waiting_step` near :1016. Triggers today: definition `trigger` (`manual` / record event) + `scope` filters + `timing:'live'`; start keys guard double starts (P3b used `chain:<run>:<step>` keys for "start another workflow" — the same uniqueness mechanism is the idempotency tool for scheduled starts).
- "Where time goes" reads `pb.workflow.run.create_date`; scheduled starts need no change there.
- Steps: one row per run and key, `unique(run_id, key)` (`workflow_models.py`); parallel groups have join semantics ("when everyone finishes") — reuse for the repeat's join. Shape helpers `parents/ancestors/between/reset_range/conditional` in `workflow_definition.py` (G28: `parents` is shadowed inside `_validate`). Validation is by code (`_new_step_issues`); preview "Try it out" words in `workflow_steps.py`.
- Contracts: duck-typed `_workflow_capabilities()` per area (`pb_me_expense`, `pb_timeoff`, `pb_hiring`, `biz_approval_workflow` generic request, `pb_payruns`); keys so far: stages, effects, subject, `safe_fields`, `adds_stages`, `participants`, `own_stage_rows`, `submits_itself`.
- People steps, inbox, teams, cover, links, employee home: P4a (`workflow_inbox.py`, `my_tasks.py`, `/workflow/t/<token>`), strip P4b (`workflow_strip.py`), time report `workflow_time.py`.
- Messages (P2b): engine helper `tells_approver(record, user)` and kill switch `biz_approval.single_notice`; requester ownership declared per model as a set of results (`_approval_requester_notice`); expense messages `pb_me_expense/models/expense_messages.py` (idempotent, three templates, vi + id shipped) — the pattern to clone for D28. Pay change / pay review group to-dos and their guard: `WF2_P2B_REPORT.md` per-area table and §9 item 3.
- Time-off card ribbon "TO APPROVE": stock kanban layout word, fix = small view change in `pb_timeoff` (`WF2_P2B_REPORT.md` §11b).

## 3. Design

### 3.1 Message decisions and leftovers

- **D26**: with a live route (same `tells_approver` guard and kill switch), the pay change / pay review per-step to-do goes to **nobody the engine did not ask**; without a route, unchanged. The other pay managers keep read access through Approvals › Everyone — verify they can see such a request there and report if not (then do not ship D26; report).
- **D28**: "sent back" email owned by the area, clone of the expense trio: expenses first (template + idempotency + reason + "Open your claim" button), then time off, then every other area whose requester messages the area owns per P2b (goals, goal changes, resignations) and the employee-home request kinds the P2b census listed (trips, equipment) **only if** that area already has an approved/refused message pattern to sit beside; else list it as not done with the reason. Each area then adds `'returned'` (or the engine's real key) to its `_approval_requester_notice` set so the engine's copy stops for it. vi + id for these new templates may ship now if the area's siblings already have them (keep one template family consistent).
- Leftovers: time-off card ribbon wording (D22); D24 instant re-check when a candidate's email is saved (hook the candidate write through Hiring's own door or a light `write` override in the Hiring contract file — not a new job); browser proof for P2b's U3, U5, U7 (were backend-only).

### 3.2 Start on a schedule

Definition: `trigger: 'schedule'` with
```
schedule: { every: 'day'|'week'|'month'|'year'|'once'|'relative',
            at: 'HH:MM', weekdays: [..], day: 1..31|'last', month: 1..12, date: 'YYYY-MM-DD',
            relative: { field: <date detail of the record type>, offset_days: ±n },
            starts: 'process' | 'each_record' }
```
- `process`: one run with no record at each tick (a new process: "Month-end checks"). `each_record`: one run per record matching the workflow's existing filters at the tick; `relative` is always each-record ("3 days before {Contract end}" — date details come from the same catalogue the condition builder offers; only date/datetime details).
- Company timezone and company working calendar ("working days only" toggle: a tick on a non-working day moves to the next working day).
- Evaluation in the worker: for each active scheduled workflow compute due ticks since `last_tick_at` (new stored field on the workflow), **cap catch-up to the latest tick only** (a server that was down for a week starts once, not seven times; say so in the inspector: "If the system was off at that time, it starts once when it is back."), start runs with a start key `schedule:<workflow>:<tick ISO>[:<record>]` so a retried job never double-starts, and cap each-record fan-out (default 500 per tick; over the cap → start none, mark the workflow "needs attention" with the count and tell the publisher through the outbox once — never half a batch silently).
- Who "started" it: the system, shown as "Started on schedule" (never the system account's name, R7). Steps addressed to "the person who started it" are refused at design time for scheduled workflows with the fix offered.
- Screens: the "When…" sentence gains the third trigger choice ("on a schedule") with a friendly picker (segmented Every day / week / month / year / once / around a date; time; weekday chips; "working days only"); the sentence reads "Every Monday at 9:00, for each expense claim where Status is Approved" / "3 days before Contract end, for each contract". A "Next 5 starts" preview list (computed by the server with the same function the worker uses — one implementation), and in Try it out "Would start for 12 records today" with the first five named. Review: fan-out estimate, the sudima-style "clock is off" notice, double-up check (R2): warn when an area effect or another workflow already runs on the same pattern for the same records (e.g. contract-end reminders — inventory §2.4 lists the existing chasers; read them through contracts' effects where declared, and report any undeclared chaser you find as an overlap rather than guessing).
- Activity: runs started on schedule carry a small clock chip; a missed/over-cap tick shows as a row with the reason.
- Pausing a scheduled workflow stops ticks; resuming does not catch up.

### 3.3 Repeat for each line

Contract (areas, add-only): `lines: [{key, label, singular, fields:[{key,label,type}], }]` + `_workflow_lines(record, key)` → list of `{id, name, values}` read through the area (never a raw field walk from Studio). Ship for: expense claim → receipts/lines; time off → none unless a natural line exists (do not invent one); Other request → none; pay run → payslips **only if** safe and small (cap applies) else none; candidate → none. Plus one generic source for new processes and any record: **"each answer in a list question"** (a Studio form's multi-choice/list answer) and **"each person in a team"** (an Approvals team) — so the feature is useful without area support.

Engine: a container node `repeat` {source, mode: 'together'|'one_by_one', join: 'all'|'any', max_lines (default 50, hard 200)} holding steps. Execution = **one child run per line** (`parent_id`, `line_key`, `line_label`, `line_values` on `pb.workflow.run`; additive columns), started when the container starts (all at once, or the next when the previous ends); the container step is done when the join rule is met; a "Stop here" inside ends that line only; a failed line shows on the parent as "1 of 5 lines needs attention" with Retry per line. Lines are **snapshotted at start** (a line added later is not picked up; say so in the inspector). Over `max_lines` → the step stops with the plain reason and count, nothing started.
- Allowed inside: task, form, confirm, notify, email, wait, path, update (line-safe values only if the area declares them — none this phase), create. Refused inside (design time, plain reason each): Approval Matrix, move to a stage, send back to outside the repeat, start another workflow, another repeat, parallel group (keep the first version one level deep).
- Values: `line.<field>` available to conditions, owners ("the person on the line" when a line field is a person), notices and task text inside the repeat (shown in words, G34); after the repeat, the parent gets `count`, `done`, and per-outcome counts ("3 Looks fine, 2 Missing") for path rules.
- People surfaces (must not regress P4a/P4b): inbox task cards show the line ("Check receipt · Taxi 12 Nov · line 2 of 5"); a person with several line tasks sees them grouped under one header with "Do all in turn" (opens the next when one is done); employee home and link pages show the line label; the strip sentence says "3 of 5 receipts checked"; progress page shows the container as one card with a per-line list (state, who, answer) and expands; "Where time goes" counts the container once plus a per-line median.
- Child runs are excluded from: "one automatic workflow per record" checks, the runs table by default (toggle "show lines"), scheduled fan-out counts, record strip switcher.
- Screens: the step list gains "Repeat for each…" under "More possibilities"; on Journey and By stage it renders as a framed group with a header chip "For each receipt" and a "+" inside; on the Flowchart canvas as a rounded frame using the same visual grammar as the shipped parallel group (do not move existing layout code paths; follow how parallel is drawn); drag steps in/out with the shipped drag; inspector: source picker with a live sample ("This claim has 4 receipts: Taxi…, Hotel…"), together / one by one, "carry on when all / any are done", the cap. Try it out walks one sample line and says "…and the same for 3 more".

### 3.4 Performance and limits

- Worker pass with 200 child runs must stay inside the job's existing time budget; measure on p0clone-sized data locally (report numbers). Inbox `_extra_items` with 200 line tasks for one user: grouped server-side, one card per group beyond 5.

## 4. Safety rails

1. Scheduled starts are idempotent (start key), capped, catch-up limited, company-timezone correct across DST and month-ends ("31st" in a 30-day month = last day; test).
2. Nothing scheduled may start on live as a result of the deploy: no workflow is enabled anywhere (`enabled = 0, live runs = 0` before/after). Do not create or enable any scheduled workflow on live.
3. Lines are read only through the area's door; company isolation; child runs inherit the parent's company and system execution (G1: superuser env, not `sudo()`); a person only ever sees their own line tasks.
4. Messages (D26/D28): P2b's rails apply — guard not delete, kill switch both ways, when in doubt send, deploy sends nothing, mail queue counts identical before/after.
5. Static guards extended to new files (no status write; controllers check before sudo). Approval suites identical before/after (175, same 4 known failures). Area suites: same failures as baseline, none new (P2b's baseline numbers are in its report).
6. Deploy set payobook, payobook_template, p0clone, rize, sudima; never `abm`.

## 5. Test cases (`test_wf2p5a_tN_…`; area tests in the areas)

- T1 D26: live route → only the asked approver is told; no route → all as before; kill switch restores; the other managers can read the request in the inbox "Everyone" scope.
- T2 D28 expenses: one sent-back email with the reason to staff and employee-home logins, idempotent, engine copy stopped, re-sent-back after a resubmit sends again; T3 same per other area shipped; areas not shipped still get the engine's notice (nothing lost).
- T4 leftovers: ribbon word; candidate email saved → link sent at once and the helper task closes.
- T5 schedule maths: next-ticks for every `every` kind incl. last day, leap day, DST change in the company timezone, working-days shift, `once`, relative ±n with a date and a datetime detail.
- T6 scheduled start `process`: one run per tick; second worker pass same tick → none; a week missed → one.
- T7 scheduled start `each_record`: filters applied, one per record, start keys, cap exceeded → none started + attention + one notice to the publisher; paused → none; resume → no catch-up.
- T8 scheduled design rules: "person who started it" refused; double-up warning with a declared area chaser; the clock-off notice when the job is inactive.
- T9 repeat basics: 4 lines together → 4 child runs, parent waits, all done → continues with counts; `any`; one by one order; snapshot (a 5th line added later ignored).
- T10 repeat limits and refusals: over cap stops with the count; each refused step kind gives its code; nested repeat refused.
- T11 repeat people: line owner from a line field; tasks in the inbox carry the line label, grouped; another person cannot see or answer; team and cover still work inside; link page shows the line.
- T12 repeat failure: one line fails → parent "needs attention", Retry that line only; "Stop here" inside ends only that line.
- T13 repeat values: `line.<field>` in a path rule, a notice text and a task title; parent outcome counts drive a path after the repeat.
- T14 generic sources: each answer of a list question; each person in a team (one task each).
- T15 exclusions: child runs absent from the runs table default, the one-automatic-workflow check, strip switcher, schedule counts; time report counts container once + per-line median.
- T16 isolation and guards; T17 banned words over every new string.
- Existing Studio suite green (126 + new).

Browser (local; screenshots looked at; console clean): U1 schedule picker and sentence for each kind, "Next 5 starts"; U2 Try it out + Review for a scheduled each-record workflow; U3 Activity clock chip and an over-cap row; U4 add "Repeat for each…" by click and by drag on Journey, By stage, Flowchart (frame drawn, nothing else moved — before/after of a workflow without a repeat must be pixel-identical on the canvas); U5 inspector with the live sample; U6 run a claim with 3 receipts as two people: grouped inbox tasks, "Do all in turn", strip "2 of 3 receipts checked", progress per-line list; U7 employee home + link page inside a repeat; U8 a failed line and Retry; U9 the sent-back email (en, vi) and the pay to-do before/after; U10 P2b's U3/U5/U7 proofs; U11 390 px for picker, repeat inspector, grouped tasks; U12 banned-word and brand scan.

## 6. Deploy and verify

As P2b's final successful attempt (`WF2_P2B_REPORT.md` §4 — read its account of the two aborted tries and the self-rollback, and its gotchas G55–G64, before scripting): notes file START/DONE "Claude WORKFLOW-2", flock, clean staging, service stopped (confirm exactly one service process after start — P2b left a duplicate once), scoped per-module rsync with before-tarballs, `-u` only modules with data/field changes (pb_lifecycle; area modules whose templates/views changed — list reverse dependents first), payobook, payobook_template, p0clone, rize, suites on p0clone, sudima last; job id lists identical; mail queue counts identical; asset purge ×5; restart; warm; hashes + `latest_version` ×5; 0 ERROR lines. Cache keys `wf2-p5a`. Another session (UPDATES) is deploying today — re-read the notes file immediately before START. Live look read-only (the main loop does the signed-in look if your session is signed out).

Commit per feature, explicit paths. Do not push.

## 7. Report back (`WF2_P5A_REPORT.md`)

Commits, versions; tests T1–T17, U1–U12; suites before/after; performance numbers; deploy evidence; D28 per-area table (shipped / not shipped and why); which areas declare lines; whether `execution_user_id` is still read anywhere; deviations; R1 audit; Overlaps found (R2a) — especially existing date-based chasers that a scheduled workflow could repeat; self-score vs the design bar; gotchas G65+; **for P5b: the full list of files/strings WORKFLOW-2 added that lack vi/id** (count per file) and anything worth consolidating; owner decisions needed.
