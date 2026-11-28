# WORKFLOW-2 · Phase 4a report — one place for work, reminders reused, everyone can take part

Builder: Claude (Opus implementation agent), 11 November 2026. Handover: `WF2_P4A_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (gotchas G36–G45 added, P4a row closed).

## 1. Commits and versions

| Commit | What |
|---|---|
| `59c3bd19c` | Approvals seams, add-only method files: `biz_approval_workflow/models/late_extra.py` (`_escalate_extra`, request-less outbox delivery), `pb_approval_config/models/inbox_extra.py` (`_extra_items` / `_extra_counts`) |
| `6bb76c4bd` | Hiring: tag through Hiring's one tag door (D14), `stage_remove` + set-up "Add a stage" / "Remove" / counter (D17) |
| `d562e513e` | Studio engine, link and employee-home pages, tests T1–T15 (+T7b, T9b) |
| `65fb08b48` | Screens: inbox Tasks group + task drawer, workbench (teams, cover, links, Review, progress, Stages sheet) |
| (docs commit) | This report and the ledger |

Not pushed. Versions: `pb_lifecycle` **19.0.1.14.0**, `pb_hiring` **19.0.2.23.6**. `biz_approval_workflow` (19.0.1.7.1) and `pb_approval_config` (19.0.1.7.0) **not bumped** (method-only files, G29); `pb_me_portal`, `pb_me_team` untouched. Workbench cache keys **`wf2-p4a`** on the iframe and all 13 tags in `index.html` (G11; `people.js` is new).

### Dependency answer (handover §2)

`pb_lifecycle` did **not** depend on `pb_approval_config` or `pb_me_portal`, and neither depends back on it (checked the full dependency closure of both, of `pb_me_team` and `pb_home_hub`). Both are installed on all five live databases. So the bridging code lives in `pb_lifecycle` with two new `depends` entries (`pb_approval_config`, `pb_me_portal`); no new module. `pb_hiring` has one reverse dependent (`rize_website`).

## 2. Tests

### Backend — Studio suite

Local `am_wf2p4a` (fresh clone of `am_wf2p3b`, expense company stage archived per G32, `-u pb_lifecycle,pb_hiring`): **111 tests, OK** (94 + 17). Server, `p0clone`: see §4.

| # | Test | Result |
|---|---|---|
| T1 | `test_wf2p4a_t1_tasks_join_the_inbox_without_touching_approvals` — task card for the assignee only, plain labels (no banned words), `open` = task; approval page cards/total/money and `mine/all/returned/done` counts identical with the task present; `tasks` on page 1 only; head `task_counts`; done → gone | pass |
| T2 | `test_wf2p4a_t2_team_and_company_views_follow_progress_rights` — a manager with progress rights sees a report's task under "team" as a read (opens progress); a login without progress rights gets nothing under team or org | pass |
| T3 | `test_wf2p4a_t3_late_tasks_are_reminded_then_passed_up_once` — one `task_reminder` a day after due, not repeated; one `task_passed_up` to the line manager two days after, task not moved; delivered as a note on the run to that person; no manager → the publisher, never the person it waits for; no deadline → nothing; a raising late handler does not stop `escalate_cron` | pass |
| T4 | `test_wf2p4a_t4_a_stage_past_its_target_tells_once_per_entry` — not before the target; one `stage_late` to the person it waits for; entering again arms it again | pass |
| T5 | `test_wf2p4a_t5_cover_while_away_goes_to_the_person_covering` — delegate assigned, history "Waiting for X, covering for Y while they are away.", inbox card and progress say so, the away person cannot answer, the delegate can | pass |
| T6 | `test_wf2p4a_t6_a_team_task_is_taken_by_the_first` — `team_empty`, `bad_team`, `team_notice` codes; waiting with no assignee and no to-do; each member told once; both see it (My tasks, inbox); first take wins, second gets "Administrator has just taken this." style message; release; non-member refused; answering takes it | pass |
| T7 | `test_wf2p4a_t7_an_employee_home_login_does_their_task_at_home` — assigned to the employee-home login (no to-do), listed by the home hook with `/my/todo/<id>`, another person's lookup returns nothing, staff RPCs refuse the login, done through the helper with history | pass |
| T7b | `test_wf2p4a_t7b_an_employee_home_login_attaches_a_file` — upload only as that person, kept on the step, accepted by the answer check | pass |
| T8 | `test_wf2p4a_t8_a_notice_reaches_the_employee_home` — one notice row, body filled, no email, "For you" card, read clears it, the login cannot search notices directly | pass |
| T9 | `test_wf2p4a_t9_someone_without_a_login_answers_by_link` — 43-char key, expiry ≥ due + 13 days, one email (subject, link, address, no framework name), key never in progress data; ok / missing (unknown, short) / done after use / second POST refused / expired; resend voids the old key; a bad number refused | pass |
| T9b | `test_wf2p4a_t9b_send_back_sends_a_new_link` — a send back to a link step mints a new key, the old one is dead | pass |
| T10 | `test_wf2p4a_t10_done_by_link_never_names_the_public_visitor` — "Done by the link sent to m***@example.com", history "Confirmed by link sent to m***@example.com: “I confirm”.", no public-user name, full address nowhere | pass |
| T11 | `test_wf2p4a_t11_every_form_field_type_renders_and_round_trips` — walks all 12 `FORM_TYPES`, both pages; typed text never becomes markup | pass |
| T12 | `test_wf2p4a_t12_a_workflow_adds_a_hiring_tag_through_hiring` — "Add a tag" choice of Hiring's tags, tag added, history "Added the tag “…”.", stars refused "Hiring no longer offers this value. Choose another.", a Hiring automation adding the same tag → `repeats_existing` | pass |
| T13 | `test_wf2p4a_t13_hiring_removes_a_company_stage_only` — built-in refused, "1 candidate is in this stage. Move them first.", no set-up right → refused, removed through Studio's door, off presets, section → `bind_removed`, key stays retired | pass |
| T14 | `test_wf2p4a_t14_people_from_another_company_are_never_used` — team member, delegate, manager and link employee from another company never used | pass |
| T15 | `test_wf2p4a_t15_outside_routes_check_first_and_never_write_status` — source order: ownership / key check before any other read in all four routes; no `csrf=False` on the link routes; no `t-raw`; status-write guard over the new files | pass |

The existing 94 tests stayed green without changes.

### Approval suites before / after (handover rail 6)

Run locally with `-u biz_approval_workflow,pb_approval_config --test-tags /biz_approval_workflow,/pb_approval_config` on two fresh clones of `am_wf2p3b`: **before** (snapshot of `d25bf7c3d`) and **after** (this phase).

| | biz_approval_workflow | pb_approval_config | failed |
|---|---|---|---|
| before | 77 | 138 | 4 of 175 |
| after | 77 | 138 | 4 of 175 |

The same four failures before and after, all in `pb_approval_config` and unrelated to this phase: `test_static_contract.test_the_look_invents_no_colour_and_carries_no_gradient`, `test_vietnamese.test_u13_the_catalogue_covers_the_whole_exported_template`, `TestP7Vietnamese.test_z06d_every_p7_block_is_filled_in`, `TestP7Vietnamese.test_z06e_no_p7_translation_loses_a_placeholder`.

### Browser (local server on `am_wf2p4a`, Chrome; screenshots looked at; console clean except the cloned database's missing website favicon, as in P3b)

| # | Result | Evidence |
|---|---|---|
| U1 | pass | Approvals › My turn: "Tasks 4" group above the approval list ("Work a workflow has asked of you. Approvals are below."), team card with "Team: Payroll team · nobody has taken it" and a primary "Take it", due shown as a day; approvals list and tab numbers unchanged (0 here; equality of cards/totals/counts proven by T1). |
| U2 | pass | "Check the travel booking" opened in the slide-over: Studio's own task page (instructions, note box, "Looks fine" / "Needs a fix"); "Looks fine" → drawer closed, card left, count 4 → 3, toast "Done. It has moved on to the next step." |
| U3 | pass | Admin "Take it" → "Team: Payroll team · Administrator has it"; the other member's take over HTTP → "Administrator has just taken this." and the card left their list; "Put it back" in the drawer → "nobody has taken it", Take it back. |
| U4 | pass | Studio › My tasks lists the same three items, the team one with "Take it" / "Look first". |
| U5 | pass | Employee-home login at 390 px: home "Needs you" shows "Fill in: Tell us about the trip · Due 11/13/2026" and "Read and confirm: Read the expense policy"; `/my/todo/<id>` → "I confirm" → "Thanks — sent."; `/my/todo` lists the remaining task and the workflow's notice ("For you", Mark as read); the form with a file posted over HTTP as that login → done; another person's id → 404; POST without the form key → 400. No sideways scroll (scrollWidth 390). |
| U6 | pass | Logged-out window, 390 px: link page with company name, every field type (file and record choice say plainly how instead), "Send my answers" → "Thanks — sent."; same link again → "Thanks, this is already done."; unknown link → "This link has run out. Ask whoever sent it to you for a new one." with no company shown. No brand of the framework in the visible text (page source only has the platform's own script identifiers every public page carries). |
| U7 | pass | Inspector: owner picker "A team (anyone on it can take it)" with "Payroll team · 2 people" / "Bank signatory · nobody on it yet" and the team hint; reminder line "Reminded a day after it is due, then their manager is told a day later — the same way approvals work."; cover and link hints. Review "Who takes part": link line and the warning that "Tickets", "Partner" cannot be sent by link. Progress drawer: "Link sent to t***@example.com · works until …" + "Send the link again" → "A new link was sent to t***@example.com. The old one no longer works." |
| U8 | pass | Hiring set-up › Stages: "1 of 12 company stages used", "Add a stage" after Shortlist → "“Values chat” added after Shortlist.", 2 of 12; Remove → confirm "Remove “Values chat”? It comes off every board and preset. Candidates' history keeps it." → removed, "11 of 12 company stages are free."; Culture chat with a candidate → "1 candidate is in this stage. Move them first." A built-in name ("Reference check") refused as a duplicate. |
| U9 | pass | Update the record on a candidate: "Value to set: Add a tag", fixed value is a list of Hiring's tags; Try it out "Would add the tag “IT”"; card "Adds the tag “IT”". |
| U10 | pass | Scan of every new `_()` string, template text, workbench string and the email for the framework's name, "token", "pool", "escalate", "state", model and field names: 0 hits. No emoji or glyph icons in new files. |

## 3. Pre-deploy live numbers (read-only)

Read just before the deploy (11 Nov 03:58 UTC, after the UPDATES P2a deploy wrote its DONE; it had started at 03:43 and I waited for it).

| DB | enabled workflows | live runs | active jobs | modules needed by this phase |
|---|---|---|---|---|
| payobook | 0 | 0 | 49 | all installed |
| payobook_template | 0 | 0 | 31 | all installed |
| p0clone | 0 | 0 | 38 | all installed |
| rize | 0 | 0 | 81 | all installed |
| sudima | 0 | 0 | 80 | all installed |

"All installed" = `pb_approval_config`, `pb_me_portal`, `pb_me_team`, `pb_hiring`, `pb_hr_comm`, `biz_mail_debrand`, and `project` (whose portal owns `/my/tasks`). Server trees of the four touched modules hashed identical to the repo baseline `d25bf7c3d` (pb_lifecycle 5d1a2111…, pb_hiring 56866bd9…, biz_approval_workflow 2dca54f5…, pb_approval_config 5391fd1e…) — nobody else's work overwritten.

## 4. Deploy evidence

One deploy, normal tier (additive columns and one new model; no data rewritten), through the notes file and `flock /tmp/payobook-studio-deploy.lock` (read-only open, G9). START `2026-11-11 03:59 UTC`, DONE `04:08 UTC` (404 s, 381 s down). Script: P3b's, adapted (`/tmp/wf2-p4a-20261111T035917Z/wf2p4a_deploy.sh`).

- Clean staging from `git archive` of `65fb08b48` → service stopped (no `odoo-bin` left) → scoped `rsync -a --delete` of `pb_lifecycle`, `pb_hiring`, `biz_approval_workflow`, `pb_approval_config` (trees before kept as `/odoo/backups/wf2-p4a-20261111T035917Z/*-before.tgz`) → `-u pb_lifecycle,pb_hiring --no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize (all exit 0, 0 ERROR/CRITICAL) → suite on p0clone **111/111** (`WORKFLOW_TEST_RESULT={"tests": 111, "successful": true, "failures": 0, "errors": 0}`) → sudima last (exit 0) → no job newly switched on anywhere → probe on all five → asset signal + purge on all five → service started.
- Tree hashes (skip `__pycache__`, `*.pyc`, `.DS_Store`; `LC_ALL=C` sort), server = repo at `65fb08b48`: pb_lifecycle be9824f9…0073, pb_hiring 44822ab7…1a13, biz_approval_workflow 3e5b5fb0…da16, pb_approval_config 0e282447…1c72.
- `latest_version` in all five: pb_lifecycle **19.0.1.14.0**, pb_hiring **19.0.2.23.6**, biz_approval_workflow 19.0.1.7.1, pb_approval_config 19.0.1.7.0 (each equal to its manifest).
- Active job id lists before → after byte-identical: payobook 49, payobook_template 31, p0clone 38, rize 81, sudima 80. Sudima's Studio worker job still **off** (D11).
- Probe (system environment, rolled back), all five: 0 enabled workflows, 0 live runs, 0 link steps (so no link email can go out), 0 drafts using the evaluation stars; notice model, step fields, three outbox kinds and the inbox seam present; link email template has no framework name; candidate values = [tag]; company Hiring stages 0 of 12; the late job's new part ran and queued nothing; admin's inbox tasks 0.
- Logs: 0 ERROR/CRITICAL in the five upgrade logs and in the service log since the restart.
- Warm: payobook.com, p0clone, rize, sudima login pages 200; workbench `index.html?v=wf2-p4a` 200 and `people.js?v=wf2-p4a` 200; `https://payobook.com/workflow/t/not-a-real-link` shows the designed "This link has run out." page (browser: tab "Your task | Payobook", no company shown, no framework name, console clean). Backend bundle built on request (`/web/assets/994906c/web.assets_backend.min.js`, 15.0 MB): contains the inbox Tasks group template and its styles; still 0 errors.
- **Not done live:** the signed-in check of Home › Approvals and Studio on payobook.com. The browser's payobook.com session had expired, and the QA login's password was reset by the UPDATES session earlier today; its credentials are only with the main loop. What that check would show is covered read-only above (bundle builds; admin has 0 tasks so no Tasks group is drawn; approval data paths unchanged by T1 and the approval suites). The main loop should do the 2-minute signed-in look.
- Evidence: `/tmp/wf2-p4a-20261111T035917Z/` (steps, upgrade logs, suite output, probe, job lists, hashes, versions, warm).

Nothing published, activated or started; no stage, tag, letter or announcement created; no mail sent. ABM untouched.

## 5. Reminders: what approvals do today, what tasks do

- **Approval reminders** (`biz.approval.outbox._deliver`): a note posted on the request with the person as a recipient (`message_post`, subtype note, `partner_ids`), **plus a to-do**. A note with recipients reaches each person by **their own setting**: in-app for people set to "in the app", **email for people set to "by email"** (G31).
- **Task reminders and pass-ups** do exactly that, minus the to-do (the task already has one): a note posted on the workflow run to that one person, through the same outbox and the same hourly job. So people who chose email for notifications get these by email, as they do for approvals; nobody else does. Team "new for your team" notes go the same way, once per member.
- Numbers come from the approval engine's own defaults (`remind_days` 1, `escalate_days` 2), read at run time. A task becomes late the morning after its due day; reminder a day later; manager told a day after that. Employee-home logins are never sent reminders (the outbox refuses them, unchanged); their "Needs you" row turns red "Late — it was due …", and their manager is still told.

## 6. Field types (QWeb parity, T11)

Studio offers 12: text, long answer, number, date, email, dropdown, multiple choices, yes/no, file, line items, record choice, heading. On the **employee home** 11 work (file upload included); on the **link page** 10 work. **Record choice** is never offered outside the app (it would show a stranger a list of records) and **file** is not offered by link: the page says "This one is chosen inside the app. Ask {company} to fill it in for you." / "Files cannot be sent from this page. Ask {company} how to send it.", and Review warns the designer. A required file or record choice on a step that goes by link therefore cannot be finished by the person — see §9.

## 7. Deviations from the handover

1. **Paths `/my/todo…` instead of `/my/tasks…`**: `/my/tasks` and `/my/tasks/<id>` belong to the Projects portal, installed on all five databases (G36).
2. **Inbox counts**: tasks are counted in **separate keys** (`tasks`, `tasks_late`, `task_counts`), not added into the approval `mine` count, so every number approvals show stays exactly as it was (R1). The dock gets `queues.tasks` (server only; its screen is unchanged). Home › Team's "Waiting on you" tiles read approvals only, unchanged.
3. **A team is its own owner kind** (`team`, id = an Approvals "group of people" responsibility) rather than a pooled `role`; `role` still means one person. An empty team is a design-time **error** (`team_empty`), not a warning: a warning blocks publishing anyway until acknowledged, and a task for nobody can never run.
4. **Hiring "Remove" cannot archive** (stages have no archive flag): it takes the stage off every board and preset and clears its key, which makes it invisible everywhere; the key stays retired when anything named it (history, a workflow section). Removal is also refused while one of Hiring's automations uses the stage (not in the handover; it would leave a rule pointing at nothing).
5. **Candidates are not reached by link**: Hiring's contract says the person a candidate is "about" is their recruiter (P2), so "The person this is about" on candidates is a staff person. Links work for employees with no login (subject or line manager) on every other record type. See §9.
6. **Link expiry** = max(due date + 14 days, today + 14 days); 30 days when there is no due date. Every person step has a due date (default 2), so "No due time, so nobody is reminded" never shows.
7. **Pass-up when nobody manages them** goes to the person who **published the version the run follows** (there is no workflow owner field); never to the person the task waits for, never the system account.
8. Plain-words extras: an area may word its safe value ("Added the tag “IT”.", "Would add the tag …", card "Adds the tag …"); dates on the pages and inbox are days, not times (G44).
9. The link and home pages share one QWeb body; a page guard from another module blocks an empty required answer in the browser before the server check (G41) — the server check is proven by tests.
10. Rate guard for bad links: in-memory, per worker process, 10 misses per address per 10 minutes → the "run out" page without a lookup.

## 8. R1 audit — every visible change to shipped screens

- **Approvals inbox (and Home › Approvals, which is the same component)**: a "Tasks" group above the approval cards on "My turn" and "All I can see" only when there are tasks; when there are tasks but no approvals, the big "Nothing is waiting for you" empty state is replaced by one quiet line "No approvals are waiting for you right now."; a task slide-over (same drawer shell) with an embedded task page. Approval cards, tabs, numbers, filters, sort, drawer: unchanged.
- **Workflow Studio**: My tasks cards gained chips (due, late, sent back, team, cover) and "Take it" / "Look first" / "Put it back"; the page subtitle now says tasks are in Approvals too. Task page: team / cover banners and a due line; inside the inbox there is no top bar or "My tasks" back button. Inspector (task/form/confirm): owner list gains "A team (anyone on it can take it)" + team picker; three hint lines under "Due in". Review gains "Who takes part". Progress drawer: team, cover, "Done by the link…", link box with "Send the link again". Stages sheet: "Remove from Hiring" on company-added candidate stages. Step cards: "Team: …"; candidate tag step "Adds the tag …".
- **Employee home**: a "Needs you" row per waiting task; a "For you" card when a workflow sent an unread notice; new pages `/my/todo`, `/my/todo/<id>`.
- **Hiring set-up › Stages**: "Add a stage" button and inline form, "n of 12 company stages used" pill, "added by your company · Remove" on company rows with an inline confirm.
- **Hiring automations**: "tag the candidate" now goes through the shared door; behaviour identical.
- **History wording**: "Waiting for X, covering for Y while they are away.", "X took this for the team.", "Told X on their employee home.", "Waiting for X: a link was sent to m***@….", "Confirmed by link sent to …", "A reminder went out for …", "… is late; X was told."

## 9. Overlaps found (R2a) — for the owner

1. **The link email has no existing counterpart** (the approvals outbox cannot reach people without a login). It is the one email this phase adds; the joining/leaving checklists keep their own confirmation links (R6). Options: (a) keep (now); (b) also move the checklists' links onto this page when checklists move into Studio. Recommend (b) later, with R6.
2. **Team "new for your team" note vs the approval engine's "It is your turn"**: same channel, different wording; no double: approvals never send for workflow tasks. No decision needed.
3. **Workflow notices for employee-home logins vs Announcements on the employee home** (D15 kept both for staff). A one-person workflow notice now shows in a small "For you" card; company notices stay in the feed. Options: (a) keep; (b) show workflow notices inside the feed. Recommend (a).
4. **Candidate by link** (deviation 5): to let a candidate confirm their details by link, Hiring would need to name the candidate as a contact (a second "who" on its contract, e.g. "The candidate"). Options: (a) add "The candidate" as an owner on candidates (small Hiring contract addition, next phase); (b) leave candidates to Hiring's own candidate emails and forms. Recommend (a) — it is what D16 imagined.
5. **Dock** gets the task count on the server but shows nothing yet (the handover asked for count only, no new card types). Options: show a small "n tasks" line in the dock, or leave it. Recommend a one-line count in P4b.

## 10. Self-score against the design bar

| Bar | Score | What is still weak |
|---|---|---|
| Hero moment (a task appears in Approvals, open it in place, done, it leaves) | strong | The drawer's embedded page loads a second time when it opens (workbench boot); about half a second locally. |
| Zero dead-ends | good | A required file or record choice on a link step cannot be finished by the person (Review warns; the page says what to do). A link step for someone whose work email is wrong just waits — "Send the link again" sends to the same address; fixing the address is in People. |
| Plain language | good | Dates on the employee home follow the browser/company locale (11/13/2026 on an en_US database). The history keeps the starter's name on system lines (shipped behaviour). |
| Motion / look | good | Card leave animation, success pop on the pages, reduced-motion respected. The task card keeps the inbox's "your turn" ring plus a left accent, which reads heavy next to approval cards. |
| Keyboard | good | Task cards focusable with Enter/Space; Escape closes the task drawer; page forms are native controls. |

Also weak: the team race was proven sequentially (row lock + "first wins" check) and over HTTP with two logins, not with two truly simultaneous requests; no real phone, only 390 px emulation.

## 11. What P4b needs to know

- **Record-screen progress component** reads `pb.workflow.studio.progress(run_id)` (rows now carry `team`, `covering`, `link`, `done_by`, `due` as a date) and `record_runs(model, id)`; the stage track from `record_stage` / `_record_stage_safe`.
- **Employee home hooks used**: `pb.me.home._pbme_needs_extra` (rows via `_wf_needs_rows(emp)`), `_pbme_extra_cards` (card via `_wf_notice_card(emp)`, template `pb_lifecycle.pbme_card_workflow_notices`); pages `/my/todo`, `/my/todo/<id>` (controller `pb_lifecycle/controllers/my_tasks.py`, ownership by `_home_task(person, id)`). "Move to…" on the home should follow the same pattern: session login → explicit ownership → sudo.
- **Label sources** for one shared status word list (D12): each area's contract `stages[].name` (`_contract(model)`), user-made stage names (`pb.workflow.stage`), and the inbox card `state_label` words ("To do", "Sent back to you", "Late").
- **Inbox seam**: `pb.approval.inbox._extra_items(scope, search)` / `_extra_counts(scope)`; any other area can add cards the same way.
- **Late seam**: `biz.approval.engine._escalate_extra(now)`; "where time goes" can read `pb.workflow.step.started_at / done_at / due_at / reminded_at / passed_up_at` and `pb.workflow.record.stage.entered_at / late_told_at`.

## 12. Needs an owner decision / follow-ups

- §9 items 1, 3, 4, 5.
- Whether pass-up with no line manager should go to the workflow's publisher (now) or to a named Approvals responsibility (e.g. HR lead), as approvals can.
- Local databases left: `am_wf2p4a` (this phase's fixtures, local-only passwords), `am_wf2p4a_before`, `am_wf2p4a_after` (approval suite runs). Local server stopped.
