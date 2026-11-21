# WORKFLOW-2 · Phase 4a handover — one place for work, reminders reused, everyone can take part

Designer: Claude (Fable), 11 November 2026. Implementer: Opus agent, same session.
Read first, in this order: `WF2_LEDGER.md` (rulings R1–R9, decisions D1–D17, conventions §3, gotchas G1–G35 — all binding), `WF2_P3B_REPORT.md` §11 ("What P4 needs to know"), then this file. Baseline: `749e7cc2e` on `19.1`, `pb_lifecycle` 19.0.1.13.0, 94 tests green. Target: `pb_lifecycle` **19.0.1.14.0**.

Design bar (owner, verbatim, binding on every screen you touch): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** Lucide SVG icons, never emoji. Brand indigo `#5A4BB0`, one solid primary button per bar. Every state designed (empty, loading, error, partial, huge).

White-label (binding): the words "Odoo" and "OdooBot" never appear in anything a person can see or receive — labels, toasts, errors, emails, public pages, `.po`. Technical identifiers are untouched. Plain English everywhere (R8): no model names, field names, "state", "token", "pool", "escalate" on a screen. Say "team", "pass up", "link".

## 1. Scope

1. **Workflow tasks appear in the Approvals inbox (D1).** A person's waiting workflow tasks, forms and confirmations show in the one inbox next to approvals, on Home and wherever the inbox is read. Studio's own "My tasks" stays (R1) and shows the same items.
2. **Reminders, pass-up and cover reused (D2, D13).** A late waiting task is reminded and passed up by the approval engine's existing hourly job and outbox — no new job, no second chaser. "I'm away" cover applies when a task is assigned. A stage that has run past its target time uses the same path.
3. **Teams.** A step can be given to a team (an approval role that is a team); anyone on the team can take it.
4. **Employees with an employee-home login take part (R5).** Their tasks show on the employee home and are done there.
5. **People with no login take part by link (R5, D16).** Form, task and confirmation steps can go to a person who has an email but no login; they act on a public page.
6. **Candidate tag instead of stars (D14).**
7. **Hiring set-up gets "Add a stage" and "Remove" for company-added stages (D17).**

### Binding non-goals

- No progress widget on record screens, no "Move to…" on the employee home, no shared status word list, no "where time goes" — that is P4b.
- No new scheduled job. No change to any existing job's cadence or active flag. Job counts stay 49/31/38/81/80; sudima's Studio job stays off (D11).
- No new approval feature. Studio never decides, routes, or defines who approves (R2d). Tasks in the inbox are not approvals: no approve/refuse wording on them.
- No change to how approval cards look, sort, filter or count for approvals. Adding task items must not move, rename or recount anything approvals already show (R1). Audit and list every visible change under "R1 audit".
- No ACL widening for employee-home logins. They reach workflow data only through controllers that check ownership first (§4).
- No migration of running joining/leaving checklists (R6). Their own confirmation links are untouched.
- No "Repeat for each line", no translations, no schedule trigger (P5).
- Do not bump the manifest version of `biz_approval_workflow`, `pb_approval_config`, `pb_me_portal`, `pb_me_team` (G29: 38+ dependents). Extend them from `pb_lifecycle` by `_inherit`, or with add-only method/asset files a restart loads. If a change there truly needs an upgrade, stop and report before doing it.

## 2. Verified plumbing (do not re-derive; re-open only the lines you edit)

### Inbox
- Server facade `pb.approval.inbox` (AbstractModel, `pb.filter.mixin`): `pb_approval_config/models/inbox_facade.py:74-83`. One source only, `biz.approval.request` (`_pbf_model` :212, `_scoped(scope)` :149-193, scopes me/team/org :44).
- List: `get_inbox_head()` :355, `get_inbox_page(filters, search, sort, offset, limit)` :371; older `list_requests(tab, filters, cursor, scope)` :400 still used by `pb_me_team`. Card dict `_card(request)` :536-610 (keys id, process, process_key, area, icon, title, sub, amount, currency, count, kind, workflow, submitted_by, submitted_at, due_at, late, state, state_label, mine, blocked, block_reason, return_note, waiting_for, badges, route).
- Counts `_counts(scope)` :461; "my turn" `_is_mine` :526, `_my_turn_ids` :244; four tabs `_pbf_builtin_views` :331-352.
- **No extension seam exists**; nothing `_inherit`s the facade. `DOCK_SOURCES` :1171 is only a colour map.
- Actions: `decide(...)` :1094 → engine :1125; dock `act(model, res_id, action, note)` :1251.
- JS: `PbInbox` `pb_approval_config/static/src/js/inbox.js:120` (client action `pb_approval_inbox` :502); `RequestDrawer` `request_drawer.js:37`; templates `static/src/xml/inbox.xml:17` (cards :120, route :161, drawer :269). One card type, no per-type branch.
- Hosts: Home's Approvals lens `pb_home_hub/static/src/js/home_hub.js:51`; `pb_mission/static/src/js/pb_dock.js:47`; `pb_goals/static/src/js/goals_home.js`. Action `pb_approval_config/views/actions.xml:30`.
- Employee home: `/my/team/approvals…` `pb_me_team/controllers/portal.py:122,134,156` → `pb_me_team/models/pb_me_team.py:135,168,192`; `_inbox()` returns None for logins that cannot read approval requests (:78-87) — i.e. every employee-home login.

### Reminders, pass-up, cover
- Outbox `biz.approval.outbox` `biz_approval_workflow/models/outbox.py:46`; kinds :18-28; `_queue(self, kind, user, request=None, payload=None, dedupe=None)` :68 (refuses share/inactive users :70); `_deliver()` does nothing without a request :108-109, else posts + schedules an activity :111-122.
- Jobs `biz_approval_workflow/data/ir_cron.xml`: `cron_outbox` every 5 min → `_cron_deliver` (:17-24); `cron_escalate` hourly → `escalate_cron` (:27-34).
- Late rule: per request step `due_at`, `activated_at`, `decided_at`, `reminded_at`, `escalated_at` (`request.py:145-150`); due from route `safeguards.due` (`definition.py:43,53`), computed by `_due_for(self, company, safeguards, index, base=None)` `engine.py:590`; defaults `late = {remind_days:1, escalate_days:2, reassign:False}` `definition.py:54`.
- `escalate_cron(self)` `engine.py:1560`: reminds at `due_at + remind_days` (:1578-1591), passes up at `+ escalate_days` to `_escalate_to(request, late)` :1608 (:1630-1651), optional `_late_reassign` :1653. It searches request steps only (:1564). **No generic entry point exists.**
- Cover: `biz.approval.delegation` `delegation.py:14`, `covering(self, user, company, role_key=None, on_date=None)` :108, applied in `_activate_next` `engine.py:1039` (:1062-1075). Standing backups `biz.approval.responsibility.backup_user_id` `responsibility.py:33`; `resolve(self, company, role, scope_keys, on_date=None)` :90. Teams: `biz.approval.role.is_pool` `role.py:25`, `responsibility.pool_user_ids` `responsibility.py:34`.

### Studio
- `workflow_studio.py`: `_staff()` :27 (refuses non-internal logins), `tasks(run_id=None)` :813, `_task` :825, `task_detail` :845, `answer(task_id, values=None, complete=True)` :864, `_cron_workflows` :971, `_check_waiting_step(run, step)` :1016 (no branch for people steps).
- `workflow_progress.py`: `_resolve_owner(run, owner)` :28, `_resolve_owner_on(source, company, owner, initiator=None)` :42; subject refuses share logins :64; team roles refused :94.
- `workflow_models.py`: `_execute` :614, people branch :623-650 (refuses share/other-company users :626; one `mail.activity` on the run with `workflow_step_id` :642-648; deadline from `due`/`due_kind` :632-641); `_finish` :584; activity guard `WorkflowActivity` :740-769. Step times: `started_at` :577, `done_at` :576, `wake_at` :571.
- `workflow_definition.py`: `PEOPLE = ('task','input','confirm')` :15; `OWNER_KINDS` :17.
- Notices `_notify_step` (`workflow_steps.py`): inbox only, staff logins only; employee-home logins are skipped today (P3b deviation 5).
- Workbench: "My tasks" `static/workflow/app.js:86` (nav :20); task page `taskPage()`/`openTask()` `forms.js:15-16`; actions `actions.js:16,67`.
- Stage target `pb.workflow.stage.target_hours` `workflow_stage.py:41`; record position row `entered_at`/`entered_by` :66-67.

### Link pages (precedent to clone)
- `pb.journey.task.portal_token` `journey_task.py:61`, minted `secrets.token_urlsafe(24)` :79-87, `_token_url()` :90, `_task_for_token(token)` → invalid/closed/used/ok :99-114. Routes GET `/journey/t/<token>`, POST `…/submit` `pb_lifecycle/controllers/token_pages.py:79,88` (csrf off, sudo). Template `journey_task_page` `views/token_templates.xml:32`. No expiry; `done_by` is the public user. Expiry precedent: `pb_hiring/models/booking.py:44` (7-day `expires_at`); feedback window `feedback.py:49,105`.

### Employee home
- Hooks on `pb.me.home` `pb_me_portal/models/pb_me_home.py:213`: cards `_pbme_extra_cards(emp)` :328, "Needs you" rows `_pbme_needs_extra(emp, put)` :720, "My requests" sources `_my_requests_sources()` :739. Precedents: `pb_me_team/models/pb_me_home.py:14,25`; `pb_me_expense/models/pb_me_home.py:17,48`.
- Route pattern `pb_me_portal/controllers/portal.py:1-21`: `auth='user'`, employee re-resolved from the session by `_ess_employee()` :55, ownership check, then `sudo()`; never an employee id from the URL.
- Nothing in `pb_me_*` references `pb.workflow`; workflow ACLs are internal-users only (`security/workflow/ir.model.access.csv:6`).

### Hiring
- `stage_add` verb and key pool `pb_hiring/models/stage_add.py`; contract `pb_hiring/models/workflow_contract.py` (`safe_fields` = evaluation, `_workflow_update`, `_workflow_add_stage`); Hiring's automations already "add a tag" (`pb_hiring/models/automation_p8.py` — find the action and reuse its door); set-up screen data `get_setup`; rename/reorder verbs `stage_rename`, `stage_reorder`.

Check before coding and report: whether `pb_lifecycle` already depends (directly or through its chain) on `pb_approval_config` and `pb_me_portal`. If not, put the bridging code in the lightest correct place (a new glue file inside the module that already depends on both, or a new dependency on `pb_lifecycle` — a manifest `depends` change needs `-u pb_lifecycle` only, which we do anyway). Do not create a new module without reporting why.

## 3. Design

### 3.1 One seam in the inbox, used by Studio (D1)

Add-only seam on `pb.approval.inbox` (in `pb_approval_config`, method file, no version bump):

- `_extra_items(scope, search=None)` → list of card dicts, default `[]`. Card = the existing card keys plus `source` (`'workflow'`), `kind: 'task'`, `open: {type:'workflow_task', id}`; `route` empty; `state_label` in plain words ("To do", "Sent back to you", "Late").
- `_extra_counts(scope)` → `{mine: n, late: n}` default zeros, added into `_counts` so the badge on Home and the dock include tasks.
- `get_inbox_head`/`get_inbox_page`: extra items are returned in their own key (`tasks`) on the first page, not interleaved into the SQL-paged approvals, so approval paging, filters and sort are byte-for-byte unchanged. `list_requests` (pb_me_team) is untouched.
- Studio (`pb_lifecycle`, new file `models/workflow_inbox.py`, `_inherit = 'pb.approval.inbox'`) fills both: scope `me` = steps waiting for me (assignee, or a team I am on and nobody has taken); `team`/`org` = waiting steps of people who report to me / everyone, only for logins that may already view workflow progress.

Screen (`inbox.js` / `inbox.xml`, add-only): a "Tasks" group above the approval cards on the "my turn" view, using the same card component and tokens (title = step name, sub = workflow · record name, who asked, due/late chip, "Sent back" chip, team chip "Team: Payroll · nobody has taken it"). Empty = the group is not drawn at all. Clicking opens a **task drawer** in the same slide-over shell as `RequestDrawer`, whose body is the Studio task page embedded (`index.html?task=<id>&embed=1`: no Studio chrome, same form renderer, same buttons, same note box, same sent-back card — one renderer, never a second OWL form). On done, the drawer closes, the card leaves with the shipped leave animation and counts refresh. A team task shows one primary "Take it" first. The dock (`pb_dock.js`) only gets the count; no new dock card types.

Studio "My tasks" (`app.js:86`) lists the same items from the same server method and gains the team rows and "Take it". Nothing else on it changes.

The `mail.activity` created today stays (people rely on the clock icon); it is closed by the same completion path. No second activity for team tasks until someone takes one.

### 3.2 Reminders and pass-up through the approval engine (D2, D13)

Add-only seam in `biz_approval_workflow` (method file, no bump):

- `biz.approval.engine._escalate_extra(now)` called at the end of `escalate_cron` inside a savepoint with its own try/except + logged error (a Studio fault must never stop approval reminders). Default no-op.
- `biz.approval.outbox._deliver` : when there is no request and `payload` has `res_model`, `res_id`, `summary`, `body`, deliver on that record (in-app note to the user by inbox, the G31 way — never an email unless that kind already emails for approvals; match what approval reminders do today and report which it is). New kinds added by `selection_add` from `pb_lifecycle`: `task_reminder`, `task_passed_up`, `stage_late`.

Studio (`pb_lifecycle`):
- New stored fields on `pb.workflow.step`: `due_at` (the deadline already computed for the activity, now also stored), `reminded_at`, `passed_up_at`; on `pb.workflow.record.stage`: `late_told_at`. (Normal tier: additive columns.)
- `_escalate_extra` override: for waiting people steps with `due_at`: at `due_at + 1 day` queue `task_reminder` to the assignee (or every member of an untaken team task), once; at `due_at + 2 days` queue `task_passed_up` to the assignee's manager (employee manager with a staff login) → else the workflow's owner, once. Use the engine's own default numbers (`definition.py:54`) by reading them, not copying them. Passing up **tells**; it never reassigns (reassigning is an approval-route feature; do not grow one here).
- Stage target (D13): a record whose position row is older than its stage's `target_hours` → `stage_late` once per entry, to whoever the record is waiting for (the waiting step's assignee if any, else the stage's "who may move it" person, else the workflow owner).
- Cover: in the people branch of `_execute`, after resolving the person, ask `biz.approval.delegation.covering(user, company)`; if someone covers, assign the delegate and say so on the step ("Covering for Lan while she is away") — shown on the task card, progress and history.
- Double-up check (R2): a step with no `due` gets no reminders (say so in the inspector: "No due time, so nobody is reminded."). The inspector's due block gains one line of words: "Reminded a day after it is due, then their manager is told a day later — the same way approvals work." No new settings.

### 3.3 Teams

- `OWNER_KINDS` role branch: stop refusing `is_pool` roles (`workflow_progress.py:94`). Resolve to the role's team members for the record's company/scope via `biz.approval.responsibility` (`pool_user_ids`).
- New field on step: `team_user_ids` (m2m to users), `assignee` empty until taken. `take(task_id)` RPC: member-only, first wins (lock the row `FOR UPDATE NOWAIT` or equivalent compare-and-set; the loser gets "Minh has just taken this."). `release(task_id)` by the taker puts it back. `answer` by a member auto-takes.
- Inspector owner picker lists team roles under "A team" with member count; empty team → design-time warning with the fix ("Add people to this team in Approvals › Who approves").
- Tell each member once through the outbox (kind reuse: `task_reminder` wording "New for your team").

### 3.4 Employee-home logins (R5)

- Allow a share user **who is linked to an active employee in the run's company** as the assignee of `task`/`input`/`confirm` for owner kinds subject, initiator, field, manager (lift the refusals at `workflow_progress.py:64`, `workflow_models.py:626` only for that case). A specific named user who is a share user is still refused in the picker.
- No activity for them (employee-home logins have no activity surface). Instead:
  - `pb.me.home` extensions (clone `pb_me_expense/models/pb_me_home.py:17`): a "Needs you" row per waiting task ("Read and confirm: Code of conduct", due chip) linking to `/my/tasks/<id>`; a small "For you" list for in-app notices sent to them by `_notify_step` (store as rows of a new light model `pb.workflow.notice` {user, run, body, read_at}; lift the skip for employee-home logins; staff behaviour unchanged).
  - Routes (new `pb_lifecycle/controllers/my_tasks.py`, pattern `pb_me_portal/controllers/portal.py`): `GET /my/tasks`, `GET /my/tasks/<int:step_id>`, `POST /my/tasks/<int:step_id>/done` (csrf on). Ownership check = `step.assignee == request.env.user` and step waiting, else the shipped not-found page; then `sudo()`. Team tasks are staff-only this phase (say so in the inspector if a team has such members: they are simply not counted).
  - Page: one QWeb task page (`views/workflow_task_page.xml`) in the employee-home shell and look (clone the layout of `pb_me_expense/views/portal_templates.xml:378`): instructions, form fields, own buttons, note box, confirmation text + "I confirm", sent-back card with the note and kept answers, done state ("Thanks — sent."), already-done state, mobile first (390 px). It must render **every field type Studio forms offer today**; list the types in the report and prove parity with a test that walks the type list.
- Reminders for them: the outbox refuses share users (`outbox.py:70`) — do not change that. The "Needs you" row shows "Late" instead; pass-up still tells their manager.
- `_staff()` stays on every existing RPC; the routes call new internal helpers that take the user explicitly.

### 3.5 People with no login (R5, D16)

- When the resolved person (subject, field, manager) has **no login** but the system knows an email (employee work email; a candidate's or partner's email for the subject of those record types), the step waits "by link": fields `access_token` (`secrets.token_urlsafe(32)`, unique index, never logged, never in progress JSON), `link_expires_at` (due date + 14 days, at least 14 days from sending; default 30 days when no due), `link_email`, `link_opened_at`, `link_done_ip` (for the record).
- Sending: one new mail template in `pb_lifecycle` data ("You have something to do: {step}" — company name as sender, one button, no brand of the framework anywhere; `biz_mail_debrand` covers the frame, verify the rendered HTML has no "Odoo"). Sent once when the step starts; "Send the link again" for a designer/progress viewer on the progress drawer mints a **new** token and voids the old one. This is the only email this phase adds; it has no existing counterpart (the outbox cannot reach non-users), state that under "Overlaps found" anyway.
- Routes in `pb_lifecycle/controllers/token_pages.py` (clone the journey ones, same file): `GET /workflow/t/<token>`, `POST /workflow/t/<token>/done`, `auth='public'`, **csrf on** (the page carries the token), `sudo()` only after the token resolves. States, each a designed page: ok, already done ("Thanks, this is already done."), expired ("This link has run out. Ask {company} to send a new one."), not found (same text as expired — never reveal which). Same QWeb body as §3.4 in a bare public shell with the company logo and name only.
- Recorded as: done by link sent to `m***@example.com`, with time — on progress and history (R8 words: "Confirmed by link sent to …"). `done_by` stays empty rather than the public user's name; never show "Public user".
- Not offered: uploading files by link (if Studio forms have a file field, the link page shows "Ask {company} how to send this file" for it and the designer gets a Review warning), teams, "send back" targets are fine (a new link is sent on send back).
- Designer sees before publishing: Review lists who will get a link ("Candidates have no login, so “Confirm your details” goes to them by email link."). Inspector hint on the owner picker.
- Studio's confirm step is now the general one (D16): nothing to remove from checklists.

### 3.6 Hiring items

- **D14**: in `pb_hiring/models/workflow_contract.py` replace the `evaluation` safe value with `tag` ("Add a tag"), type `choice` with options = Hiring's tags, executed through the same code path Hiring's automation "add a tag" uses. "Update the record" inspector renders a choice list for a `choice` value (generic: any area may declare one). Existing drafts that chose Evaluation: Review says "Hiring no longer offers this value. Choose another." (no crash; none exist on live — verify with a count and report). Double-up check: a Hiring automation that already adds the same tag at the same stage → `repeats_existing` warning.
- **D17**: new verb `pb.hiring.act('stage_remove', {stage_id})`: only `own_*` stages; refused with the reason when any candidate (open or closed) sits in it ("3 candidates are in this stage. Move them first."); otherwise removed from every preset and role board, archived (history rows keep pointing at it), its key freed for reuse only if nothing references the row — else keep the key taken and say how many of the 12 are left. Hiring set-up › Stages gains "Add a stage" (same `stage_add`, placed after the selected row, working stages only) and a "Remove" on company-added rows with a confirm that names the stage; counter "2 of 12 company stages used". Studio: a section bound to a removed stage falls back to a heading and Review says so; Stages sheet shows the same Remove for candidate stages through the contract (`_workflow_remove_stage`), never its own delete.
- pb_hiring gets a version bump (screen assets + verb): check its reverse dependents first (G29) and report the number; it was upgraded in P3b without trouble.

## 4. Safety rails

1. **Public and employee-home routes are the risk in this phase.** Token compared by indexed equality on a 32-byte random value; no enumeration signal (same page for unknown and expired); `POST` single-use (state check inside the transaction, row locked); answers validated by the same `D.validate_answers`/`D.validate_outcome` as staff; values never rendered unescaped (`t-esc`, never `t-raw`/`t-out` of user text, G: owl markup); no record data on the page beyond the step's own instructions, the fields the designer put on the form, and the record's display name. No `sudo()` before the ownership/token check. Rate: after 10 bad tokens from one address in 10 minutes return the not-found page without a lookup if a cheap in-memory guard is practical; otherwise report that it is not there.
2. Never widen `ir.model.access` or record rules for share users. New model `pb.workflow.notice`: internal read own; share users through the controller only.
3. Never write a module's status (static guard test stays green and covers the new files). Never define or decide an approval.
4. Company isolation on every new path (team members, cover, manager, link email all resolved inside the run's company).
5. Live databases: never publish, activate or start a workflow; never create stages, tags, letters; **never send the link email** (no live step will reach it because nothing is enabled — verify `enabled workflows = 0, live runs = 0` before and after and report); never touch `abm`, `pbf_preview`, `recruit_connect_20261023`.
6. The approval engine's reminder job must behave identically for approvals: prove with the existing approval test suites of `biz_approval_workflow` and `pb_approval_config` (run them locally before and after; report counts).
7. No credentials in the repo; local test logins get local-only passwords from the environment.

## 5. Test cases (add to the Studio suite; names `test_wf2p4a_tN_…`)

Backend
- T1 inbox items: a waiting task appears in `_extra_items('me')` for the assignee only, with plain labels; counts include it; done → gone; approvals list/paging/counts identical with and without tasks (snapshot compare).
- T2 inbox scopes: manager sees a report's task under team; a login without progress rights gets none under org.
- T3 reminder: step due yesterday+ → one `task_reminder`, not repeated next hour; two days → one `task_passed_up` to the manager; no manager → workflow owner; step without due → nothing; a raising override does not stop approval reminders (inject a fault).
- T4 stage target: record past `target_hours` → one `stage_late` to the right person; re-entering the stage arms it again.
- T5 cover: assignee away with a delegate → delegate assigned, words on the step, original person cannot answer, delegate can.
- T6 team: all members see it; first `take` wins, second gets the plain message; `release`; `answer` by a member auto-takes; non-member AccessError; empty team → design-time warning code.
- T7 employee-home login as subject: assigned (no activity), listed by the home hook, answered through the helper as that user; another employee's step → not found; staff RPCs still refuse the share user.
- T8 notice to an employee-home login → one `pb.workflow.notice`, listed, marked read; staff path unchanged, 0 emails.
- T9 link: subject without login + email → token minted, one mail queued (template rendered, no "Odoo" in subject/body), progress JSON has no token; GET ok; POST done once; second POST → already done; expired → expired page; unknown → same page; resend voids the old token; answers validated (bad value refused); send back issues a new link.
- T10 link identity: done row shows masked email + time, no public user name anywhere in progress, history or track.
- T11 QWeb field parity: every Studio form field type renders and round-trips on the page (walk the type list).
- T12 Hiring tag: update step adds the tag through Hiring's door; evaluation refused; double-up warning with an automation adding the same tag.
- T13 Hiring `stage_remove`: refused with candidates; removed from presets/roles; built-in stage refused; without set-up right AccessError; Studio section falls back to heading with a Review line.
- T14 isolation: other company's team, delegate, manager, link email never used.
- T15 static guards: no status write; no `sudo()` before check in the two controllers (assert by reading source order or by behaviour tests on each route with a wrong user/token).

Browser (local, Chrome, screenshots looked at, console clean)
- U1 Home › Approvals shows the Tasks group above approvals; approvals below unchanged (before/after screenshot).
- U2 open a task in the drawer, fill, done → card leaves, count drops; sent-back task shows the note.
- U3 team task: two logins, "Take it" race, loser message; release.
- U4 Studio "My tasks" shows the same items.
- U5 employee home (employee-only login): "Needs you" row → `/my/tasks/<id>` → done; 390 px.
- U6 link page in a logged-out window: ok, done, already done, expired; 390 px; no brand of the framework in page source.
- U7 inspector: team picker, due-block words, link hint; Review lists who gets a link.
- U8 Hiring set-up: Add a stage, Remove with confirm, refusal with candidates, counter.
- U9 Update the record on a candidate: tag choice list.
- U10 scan of every new/changed screen and the email for banned words (as P3b U10).

## 6. Deploy and verify

As P3b (`WF2_P3B_REPORT.md` §4; its script is in the server evidence folder `/tmp/wf2-p3b-20261111T024143Z/`): read `/opt/deploy-notes.md`, START/DONE as "Claude WORKFLOW-2", flock (read-only open, G9), clean staging from `git archive`, service stopped, per-module scoped rsync with before-tarballs, `-u pb_lifecycle,pb_hiring` (plus only what you proved is needed) `--no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize, suite on p0clone, then sudima; job id lists identical before/after (49/31/38/81/80; sudima's Studio job off); asset purge on all five; restart; warm; tree hashes and `latest_version` equal on all five for every touched module; 0 ERROR lines. Bump workbench cache keys to `wf2-p4a` (G11). Live check on payobook.com is read-only: Home › Approvals loads with no Tasks group (there are none) and approvals unchanged; Studio opens; `/workflow/t/not-a-real-link` shows the designed page; console clean.

Commit per feature with explicit paths (areas seam / Studio engine + tests / screens / Hiring / docs). Do not push.

## 7. Report back (`WF2_P4A_REPORT.md`)

Commits and versions; test table T1–T15, U1–U10; approval suites before/after; deploy evidence; the dependency answer from §2; which delivery (in-app or email) approval reminders use and what task reminders do; field-type parity list; deviations; **R1 audit** (every visible change to shipped screens, including the inbox); **Overlaps found** (R2a) with options and a recommendation; self-score against the design bar with what is still weak; new gotchas into the ledger (G36+); "What P4b needs to know" (where a record-screen progress component would read from; the employee-home hooks used; label sources); anything that needs an owner decision.
