# WORKFLOW-2 · Phase 3b report — more step types, richer step settings, candidate stages through Hiring

Builder: Claude (Opus implementation agent), 11 November 2026. Handover: `WF2_P3B_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (gotchas G28–G35 added, P3b row closed).

## 1. Commits and versions

| Commit | What |
|---|---|
| `d33483854` | Let Other requests and pay runs describe themselves, open safe values, add candidate stages in Hiring (area modules, add-only) |
| `1bc343cc7` | Add eight step types, task buttons and richer waits to Workflow Studio's engine (`pb_lifecycle` backend + tests T1–T14) |
| `54ad2fbe4` | Show the new steps, task buttons and step settings on the workbench (screens + `tools/workflow_studio/chrome_test_p3b.cjs`) |
| (docs commit) | This report and the ledger |

Not pushed. Versions: `pb_lifecycle` **19.0.1.13.0**, `pb_hiring` **19.0.2.23.5**. `biz_approval_workflow` (19.0.1.7.1), `pb_payruns` (19.0.3.5.0) and `pb_me_expense` (19.0.1.0.3) are **not bumped** on purpose (deviation 2): their new files add methods only, a restart loads them, and a bump would force an upgrade of every module that depends on them (38 / 8 / 1 direct dependents, ledger G29). Workbench cache keys: **`wf2-p3b`** on the iframe `v=` (`static/src/js/workflow_studio.js:18`) and on all 12 tags of `static/workflow/index.html` (G11; `steps.js` is new).

Files:

- Area modules: `biz_approval_workflow/models/workflow_contract.py` (new: Other request contract + subject), `pb_payruns/models/workflow_contract.py` (new: pay run contract), `pb_me_expense/models/workflow_contract.py` (`safe_fields` = note, `_workflow_update`), `pb_hiring/models/stage_add.py` (new: key pool + `stage_add` verb), `pb_hiring/models/workflow_contract.py` (`adds_stages`, `safe_fields` = evaluation, `_workflow_update`, `_workflow_add_stage`), the three `models/__init__.py`, `pb_hiring/__manifest__.py`.
- Studio backend: new `pb_lifecycle/models/workflow_steps.py` (execution of the new types, creators registry, safe values, notice words, Try-it-out words, `metadata` additions, `stage_add_area`); `workflow_definition.py` (types, buttons, shape helpers `parents/ancestors/between/reset_range/conditional`, validation by code, preview stops at a send back / stop); `workflow_models.py` (dispatch, send-back restart, stop, skipped leaf continues, wait wake by unit, `_values` hides `_` keys); `workflow_studio.py` (DB-level checks `_new_step_issues`, task outcome + note in `answer`, `task_detail` buttons/text/sent-back note, confirm in "My tasks", wait "carry on", stage-move recheck, capped send back retry, half-written filters left out of `_rule_words`); `workflow_progress.py` (manager's manager, answers/notes/links/loops/history on progress); `workflow_contract.py` (contract keys `safe_fields`/`adds_stages`, other workflows' new steps in "already happens", double-up checks, same-path drafts, send-back warnings); `workflow_stage.py` (owner kind, "by the workflow" wording); tests T1–T14.
- Workbench: new `static/workflow/steps.js`; edits to `app.js`, `actions.js`, `forms.js`, `conditions.js`, `graph.js`, `stages.js`, `icons.js` (11 icons), `style.css` (one appended block), `index.html`, `static/src/js/workflow_studio.js`.
- Tools: `tools/workflow_studio/chrome_test_p3b.cjs` (real mouse, local databases only, credentials from the environment).

## 2. Tests

### Backend

Local `am_wf2p3b` (clone of `am_wf2p3`, `-u pb_lifecycle,pb_hiring`, later `-i pb_hr_comm` so the announcement branch runs): **94 tests, OK** (80 + 14), 0 skips. Server, `p0clone`, service stopped: see §4.

| # | Test | Result |
|---|---|---|
| T1 | `test_wf2p3b_t1_task_buttons_choose_the_path` — two buttons: no choice → "Choose one of the buttons."; answer stored as `outcome`/`outcome_label`/`comment`; a path rule on "Check receipt · answer" picks the path; the other answer takes Otherwise; progress row shows the answer; one button needs no choice (`done`); duplicate keys → `bad_buttons` | pass |
| T2 | `test_wf2p3b_t2_move_to_a_stage_follows_the_record` — at Approved: position written ("Moved to … by the workflow."), status unchanged; at Draft: waits "Waiting for this to reach Approved.", moved by the worker once the claim gets there; at Paid: skipped "This is already past Approved, so it was not moved to …", next step runs; unknown stage → `stage_move_target` | pass |
| T3 | `test_wf2p3b_t3_send_back_redoes_the_work_and_stops_after_three` — reviewer answers "Paper receipt missing" with a note: form back to waiting with its answers as prefill, `sent_back` = reviewer + note, review step reset and its answer cleared, progress reason "Sent back by …: …"; redo + "Looks fine" carries on; three send-backs then the fourth fails "This has gone back three times. Someone should look at it."; Retry carries on; approval step in between → `send_back_effects`; unconditional → `needs_condition`; unknown target → `send_back_target` | pass |
| T4 | `test_wf2p3b_t4_update_sets_only_a_value_the_area_opened` — note written, status unchanged, history "Set Note to …"; `refusal_reason`, `state`, `total` refused (`update_field`) and refused again at run time; a number reads as text; an earlier form answer fills the note (after keeping the double-up with the first workflow); Time off: "Time off has not opened any values to workflows yet." | pass |
| T5 | `test_wf2p3b_t5_create_makes_one_draft_and_never_sends_it` — one draft letter, retry makes none more, step points at it, progress link, letter stays Draft; Other request without an employee → "This is not about an employee, so there is nobody to write a letter for."; partner → `create_needs_subject`; announcement draft from a template (runs where announcements are installed: locally after `-i pb_hr_comm`, and on p0clone) | pass |
| T6 | `test_wf2p3b_t6_notify_tells_the_person_in_the_app_only` — inbox notification to the claimant with the claim reference filled in; no `mail.mail`, no activity; no login → skipped "… has no login to show this to."; on Time off "Approved" → `repeats_existing` "Time off already does this here …" | pass |
| T7 | `test_wf2p3b_t7_only_the_assignee_confirms_and_it_is_recorded` — empty text refused; listed in the assignee's tasks; another person → AccessError; detail shows text + "I confirm"; done with who/when and history "… confirmed: “I confirm”." | pass |
| T8 | `test_wf2p3b_t8_start_hands_over_once_within_limits` — target run started once with the same initiator, step links to it; self → `start_self`; paused target → step "… is not switched on …"; already running for the record → done with "… is already running for this record." and still one run; chain of five: the fourth hand-over fails "… three times at most." | pass |
| T9 | `test_wf2p3b_t9_stop_here_ends_the_run_with_its_reason` — later step skipped "Stopped by “Stop”.", run finished, history "Stopped here: Stop. Nothing to pay"; unconditional → `needs_condition`; Try it out ends at the stop | pass |
| T10 | `test_wf2p3b_t10_managers_manager_resolves_and_fails_plainly` — resolves one level above the area's manager; no such person → "… has no manager with a staff login, so this cannot go to their manager’s manager."; on a new process → `owner_needs_record` | pass |
| T11 | `test_wf2p3b_t11_wait_can_carry_on_when_time_runs_out` — "Carry on anyway" → done "Carried on after waiting 1 hour.", next step waiting; default still fails; bad choice → `bad_wait`; working days planned on the company calendar | pass |
| T12 | `test_wf2p3b_t12_candidate_stage_added_through_hiring` — `stage_add_area` makes a Hiring row with an `own_*` key, family open, not always on, straight after Shortlist in the catalogue (kind core, not an exit), in every preset that holds Shortlist; survives `_ensure_journey_stages()`; renamed and reordered by Hiring's verbs; a designer without Hiring's set-up right → AccessError; Studio's own stage layer still refused; after Joined refused; reachable by "Move to a Hiring stage" | pass |
| T13 | `test_wf2p3b_t13_other_request_and_pay_run_contracts` — both declared, exits {Turned down, Withdrawn} / {Rejected} last, approval stage flagged, banned-word check over labels, stages, "enters", area effects, creator texts; pay run: no subject, no safe values, 3 area rows; static guard over `workflow_steps.py` and the four area contract files (no status write) | pass |
| T14 | `test_wf2p3b_t14_new_steps_stay_inside_their_company` — another company's stage (`stage_move_target`), workflow (`start_target`), letter template (`create_template`), person for a notice or a confirmation (`inactive_owner`); at run time a stage moved to another company fails the step | pass |

Existing test changed: `test_wf2p2_t2_record_type_without_contract_is_discovered` now picks a record type that still has no contract (letters), because this phase gives "Other request" a declared contract (its premise changed, as the handover asked).

### Browser (local server on `am_wf2p3b`, Chrome; screenshots looked at; console clean of workbench errors — the only 500 was the cloned database's website favicon)

| # | Result | Evidence |
|---|---|---|
| U1 | pass | Step list shows the eight under "More possibilities" → "Change, tell and hand over", each with its icon and hint; the "+" picker lists all 18. `chrome_test_p3b.cjs` (real mouse): Journey drag 8/8, By stage drag 2/2, canvas drag 2/2, click and "+" add, "More possibilities" stays open after each add, no page errors. |
| U2 | pass | Every inspector opens (8/8) with designed empty states ("You have no stages of your own for these records yet." + "Add one in Stages"; "No other workflow for these records is started by a person yet …"; "An announcement · This app is not switched on here." where it is not installed). Review on a fresh step-per-type draft lists exactly: send back no condition / no target, confirm no text, start no workflow, notice no text, stop no condition, move no stage, create no template — each in plain words. |
| U3 | pass | Built "P3b receipts check": form "Receipt details" → task "Check receipt" with own buttons "Looks fine" / "Paper receipt missing" (live button preview) → "Add a path for each answer" → "Send back for changes" in "Paper receipt missing" (shows "Runs again after the changes: Receipt details, Check receipt") → notice. Try it out: "Paper receipt missing" → "Would send it back to Receipt details. The steps from there run again." and stops; "Looks fine" → "Would tell the person who started the workflow in the app". |
| U4 | pass | Published + activated locally; Administrator filled the form; Pat Viewer (second login) chose "Paper receipt missing" with a note; Administrator's task reopened with the card "Sent back by Pat Viewer for changes · “Please attach the paper receipt from the taxi.”" and the answer kept; redo; Pat chose "Looks fine"; run Completed. Progress: "Answer: Looks fine", "What happened" (chose “Paper receipt missing” … chose “Looks fine”), send-back card "Sent back once". The notice reached Administrator's inbox with the receipt text filled in; 0 emails. |
| U5 | pass | Expense workflow "P3b pay booking": stage "Booked for payment" (after Approved) added in the Stages sheet; "Move to a stage" chose it ("If the record is not at Approved yet, this waits …"); started on an approved claim: record track "Booked for payment · counts as Approved · Here now", "Waiting for Administrator: Pay it.", "moved by the workflow" (after the fix in deviation 10). |
| U6 | pass | Candidate workflow → Stages → "Add a stage here" after Shortlist → "A real Hiring stage" (text: "It is added to Hiring, so it shows on the Hiring board and in Hiring set-up, after Shortlist …") → "“Culture chat” is added to Hiring. It shows on the Hiring board too." Hiring set-up › Stages lists "Culture chat · Working column" right after Shortlist. |
| U7 | pass | Duplicate on a path group → "(copy)" with its inner step, one Undo restores `[order, nodes]` exactly (also in the Playwright run on a single step). |
| U8 | pass | Review: no older banners; one "Already happens for these records" group now ends with "Other workflows that start for these records" (name, start, filters, Open) and one box "I checked these; this workflow adds different work." Sentence with a filter field chosen but no value: "… , for everyone"; with a value: "for records where Reference is EXP/2026/0090". |
| U9 | pass | 390 px: drawer with the new blocks, no sideways overflow (`scrollWidth` 390), buttons editor and preview fit, action row wraps. Keyboard (Playwright): Tab from the step name reaches the notice text, typing + Tab saves it. |
| U10 | pass | Byte scan of new screen code: no emoji or glyph icons (the only non-text glyph is "→" inside a Python docstring). Text, aria-labels, titles and placeholders of 49 screens (5 views × the P3b workflows, every step's inspector, Review) scanned for Odoo/OdooBot, model/field names, "state", "anchor", "gate", "outcome", raw `{{step.` keys: 0 hits. |

## 3. Pre-deploy live numbers (read-only, 11 Nov 02:39 UTC)

| DB | enabled workflows | live runs | user-made stages | active jobs | announcements |
|---|---|---|---|---|---|
| payobook | 0 | 0 | 0 | 49 | installed |
| payobook_template | 0 | 0 | 0 | 31 | installed |
| p0clone | 0 | 0 | 0 | 38 | installed |
| rize | 0 | 0 | 0 | 81 | installed |
| sudima | 0 | 0 | 0 | 80 | installed |

Server trees of all five touched modules hashed identical to the repo before this phase (`8b9c62782`): pb_lifecycle 7c8ed691…, pb_hiring b42fc586…, pb_payruns 8e3430c7…, biz_approval_workflow 699c2ed0…, pb_me_expense 236a01a5… — nobody else's work overwritten. Notes file: every START had its DONE (latest UPDATES P1 follow-up, DONE 02:27).

## 4. Deploy evidence

One deploy, normal tier (no new stored field or model; the Hiring key pool is a selection addition, data only), through the notes file and `flock /tmp/payobook-studio-deploy.lock` (read-only open, G9), no other START open in the last 12 hours. START `2026-11-11 02:41 UTC`, DONE `02:47 UTC` (330 s, 322 s down). Script: P3a's, extended to five module trees (`wf2p3b_deploy.sh` in the evidence folder).

- Clean staging from `git archive` of `54ad2fbe4` → service stopped (no `odoo-bin` left) → scoped `rsync -a --delete` of `pb_lifecycle`, `pb_hiring`, `pb_payruns`, `biz_approval_workflow`, `pb_me_expense` (trees before kept as `/odoo/backups/wf2-p3b-20261111T024143Z/*-before.tgz`) → `-u pb_lifecycle,pb_hiring --no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize (all exit 0, 0 ERROR/CRITICAL lines) → suite on p0clone **94/94** (`WORKFLOW_TEST_RESULT={"tests": 94, "successful": true, "failures": 0, "errors": 0}`, announcements installed there, so T5's announcement branch ran) → sudima last (exit 0) → no job newly switched on anywhere → probe on all five → `orm_signaling_assets` + asset purge on all five → service started.
- Tree hashes (skip `__pycache__`, `*.pyc`, `.DS_Store`; `LC_ALL=C` sort), server = repo at `54ad2fbe4`: pb_lifecycle 5d1a2111…36858, pb_hiring 56866bd9…fe8a, pb_payruns 74dc61b1…7327, biz_approval_workflow 2dca54f5…13c6, pb_me_expense a73237d6…453a.
- `latest_version` in all five: pb_lifecycle **19.0.1.13.0**, pb_hiring **19.0.2.23.5**, pb_payruns 19.0.3.5.0, biz_approval_workflow 19.0.1.7.1, pb_me_expense 19.0.1.0.3 (each equal to its manifest).
- Active job id lists before → after byte-identical: payobook 49, payobook_template 31, p0clone 38, rize 81, sudima 80. Sudima's "Workflow Studio: progress active runs" (id 89) still **off** (D11).
- Probe (system environment, rolled back), all five: Expense claim / Time off / Candidate / Other request / Pay run contracts all `declared` (5 / 5 / 17 / 6 / 4 stages); exits as expected (Other request: Turned down, Withdrawn; Pay run: Rejected); safe values Expense note, Candidate evaluation, none elsewhere; `adds_stages` only on candidates; letters and announcements creators available; 12 spare Hiring keys offered, 0 company stage rows; 0 "already happens" rows with the framework's brand name; a half-written filter reads "Every record"; backend bundle builds. System account "Payobook" (payobook, payobook_template, p0clone, sudima), "Rize" (rize).
- Logs: 0 ERROR/CRITICAL in the five upgrade logs; 0 in the service log since the restart (602 lines).
- Warm: payobook.com, p0clone, rize, sudima login pages 200; workbench `index.html?v=wf2-p3b` 200, it references `steps.js?v=wf2-p3b`, which is served (200) and contains the new inspector code.
- Evidence: `/tmp/wf2-p3b-20261111T024143Z/` (steps, upgrade logs, suite output, probe, job lists, hashes, versions, warm).

**Live check on payobook.com (the signed-in browser session P3a used, read only):** the workbench loads with `v=wf2-p3b`; workflow "Test Expense" shows the eight new steps under "More possibilities", the "+" picker lists all 18 kinds, the sentence reads "When an expense is started by a person, for everyone", Review shows no older banners; the "Create something" choices say plainly why letters are not offered for this record type. Nothing saved (draft not dirty, no Undo history), browser console empty. No workflow published, activated or started; no stage, letter or announcement created; nothing moved; no mail.

## 5. Hiring `stage_add` — what I found and decided

Found (read in `journey.py`, `board_p1.py`, `registers_p9.py`, `filters_w3.py`, `automation_p8.py`, the contract):

- A stage row **without** one of the 17 keys is invisible everywhere: the board (`_pb_board_stages`), set-up (`get_setup`), presets (`_standard_stages` and `preset_save` keep `pb_family == 'open'`), rules, the filter panel, the stage log readers and Studio's contract all search `pb_key != False`. `pb_family` is computed from the key, so a keyless row has no family. P2 deviation 8 already hid keyless rows from Studio. So "a stage without a key" cannot be the add-only answer.
- Nothing indexes a dictionary by an unknown key at run time (only seeding and a migration index `MEANINGS[...]`, both over the 17 product keys); the Hiring JavaScript has no per-key lookups. `_act_journey_stage` accepts any keyed row (only Joined is refused). Rename (`stage_rename`) and reorder (`stage_reorder`, families kept in bands) accept any keyed row. `_ensure_journey_stages()` walks the 17 product rows only; `_retire_stock_stages()` walks stock xmlids only.
- Presets and a role's own columns are many2many lists of rows; a new row is on no board until it is put into them.

Decided (the smallest add-only way, shipped): a **pool of 12 spare keys** (`own_1` … `own_12`) added to the key list (`selection_add`), and a compute override that gives them the family "open" (never "always on"). `pb.hiring.act('stage_add', {name, after_stage_id})` checks Hiring's own set-up permission (`_require_write`), refuses a duplicate name and a position after a non-working stage (Joined, the closed ones), takes the next free key, places the row straight after the chosen stage **through the existing reorder verb**, and adds it to every preset that holds that stage and every role whose board shows it. Studio calls it through the contract (`_workflow_add_stage`) and `stage_add_area`; the sheet offers "A real Hiring stage" again and binds the new section to it. Studio still refuses a stage layer of its own on candidates.

Limits (for the owner): Hiring set-up has no "remove a stage" (it hides columns per role and per preset, as for any stage), so a company stage can be renamed or hidden but not deleted; at most 12; Hiring stages are shared by all companies in one database (as the 17 are).

## 6. What "Repeat for each line" would take

- A line source in the contract (`lines: [{key, label, fields}]`, e.g. receipts on a claim, days of leave), read through the area like `safe_fields`.
- Per-line step instances: today a step is one row per run and key (`unique(run_id, key)`); either a line index on steps (stored field + constraint change, risky tier) or a sub-run per line (a child `pb.workflow.run` with `parent_id`/`line_key`, the cleaner option, and what the handover calls sub-runs).
- Join semantics like a parallel group ("when every line is done" / "when any"), plus validation: no approval, send back or stop inside a repeat; a cap on lines.
- Values: `line.<field>` for conditions and notices inside the repeat; outcomes per line.
- Progress and the person's screen: one card per line, counts ("3 of 5 lines checked"), and the inbox (P4) listing line tasks sensibly.
- Roughly a phase on its own (backend + screens + tests), best after P4's single "My work" list.

## 7. Deviations from the handover

1. **Update the record writes only through the area's `_workflow_update`** (no "plain write restricted to declared keys" fallback). Studio's static guard forbids any record write in Studio files; each area that declares safe values also declares the door (Expenses: note; Hiring: evaluation). A record type that declares values without the door is refused ("… has not opened this value to workflows.").
2. **No version bump for `biz_approval_workflow`, `pb_payruns`, `pb_me_expense`** (method-only files; G29). Their trees are synced and loaded by the restart; their `latest_version` stays equal to their manifests.
3. **Other request contract**: "Sent back" is an **optional stage before "Waiting for approval"**, not an exit (it can be changed and sent again); exits are Turned down and Withdrawn. It also declares a subject (who asked, and their manager when they are an employee) so letters, notices and "The person this is about" work there.
4. **Pay run effects** in plain sentences: payslips held while it waits, finished when approved, cancelled when turned down (the module sends no message of its own).
5. **Tell someone in the app** creates the note itself (`mail.message`) and puts it in the person's inbox (`_notify_thread_by_inbox`) instead of `message_post`, because `message_post` emails people whose preference is "by email" (G31). Author: the company. It sits on the record when the person can read it, else on the run. People with a portal login are skipped like people with none (portal users have no in-app inbox; P4 brings the employee home).
6. **Send back** may target a task, a form or a confirmation; once-only steps in between are refused at design time and again at run time; messages or notices in between are a warning kept on purpose on Review. Retry on a step that has gone back three times carries on without a fourth send back (zero dead-ends).
7. **Start another workflow**: chain depth is read from the start keys (`chain:<run>:<step>`), no new field; "already running" and "its filters do not match" finish the step with a note instead of failing it.
8. **Wait durations** keep `hours` as the stored value and add `unit`/`amount` (working days planned on the company calendar at run time).
9. **Progress gained more than asked**: a per-step "What happened" list (the run's own history), the send-back count, links to what was made or started.
10. **Record track wording**: a stage entered by the system now says "moved by the workflow" (P3a showed the system account's name, e.g. "BizApp" locally) — R7.
11. **Helpers added for the design bar**: "Add a path for each answer" (makes the paths from a task's buttons), an optional note on every task (the send back carries it), notices show details in words (`{{Receipt details · Receipt}}`) while the key is saved, "More possibilities" stays open once opened.
12. **"Their manager’s manager"** also appears in the Stages sheet's "Who may move it" on record workflows (the control is shared); validated there too.
13. **Already happens**: three rows then "n more" in Journey (was all) and By stage (was two).
14. **Half-written filters** are also left out of the server's filter words (Review's other-workflow summaries), not only of the sentence.
15. A step that decides it does not apply (`skipped`) lets the walk continue; before, only `done` did (existing kinds never skip themselves, so no change for them).

## 8. R1 audit — everything shipped that changed, however small

- Step list: "More possibilities" holds eight more steps under a small heading and stays open once opened (was re-collapsed on every redraw).
- Inspector: tasks gain "Buttons the person sees"; the owner list gains "Their manager’s manager"; the wait step's "Wait for (hours)" became a number + hours/days/working days, its rule hint names the chosen time-out behaviour, and "If it never happens in time" appears when it waits for a rule; "Duplicate" sits between "Move step" and "Remove" (not on Start or an approval step); the bottom row wraps on a narrow drawer.
- The person's task screen: an optional note box under the instructions on tasks; custom buttons replace "Mark done" only when a task has its own buttons (the default single "Done" task keeps "Mark done"); a confirmation shows its text and one button; a sent-back task shows the note card.
- Review: the two banners "Existing automation to review" and "Also active for these records" are gone; their content is the last part of "Already happens for these records", with the one confirmation box (same `#ack-automation`, same activation check).
- Progress: drawer shows Answer, a note, an Open link, "What happened"; cards show an answer chip and "Sent back once/n times". Record track: "moved by the workflow".
- Journey: "already happens" capped at three rows + "n more" (expand in place); By stage from two to three.
- Sentence: rules without a value are ignored ("for everyone").
- Stages sheet: candidates offer "A real Hiring stage" again; refusals of moves, deletes and shared renames also appear beside the row (the toast stays).

## 9. Overlaps found (R2a) — for the owner

1. **Candidate "Evaluation" stars** are the only value I could declare safe on candidates, but Hiring's own screens do not show them (Hiring uses scorecards and tags; its automations already "add a tag"). Options: (a) keep Evaluation (now); (b) declare nothing for candidates until Hiring shows a value; (c) let workflows add a Hiring tag through Hiring's own tag door (reuses the automation action). Recommend (c) later, (b) now if Evaluation would confuse recruiters.
2. **"Tell someone in the app" vs D8 "notice step → announcement"**. Built as the handover says: a one-person inbox notice the approval outbox's way; company-wide notices go through "Create something → An announcement" (a draft that follows its own sign-off). Options: (a) keep both (now); (b) drop the one-person notice and send everything as announcements. Recommend (a): different audiences.
3. **"Ask someone to confirm" vs the joining/leaving checklist "Confirmation" step** (which also has a token link for people with no login). Same job; R6 says checklists move into Studio later. Options: (a) Studio's confirmation becomes the general one (like D4 for forms) and gains token links in P4; (b) keep both. Recommend (a).
4. **Hiring has no "add a stage" button in its own set-up**; Studio now reaches Hiring's new door. Options: (a) add the same "Add a stage" to Hiring set-up (one door, two screens); (b) Studio only. Recommend (a), a small Hiring screen change (not done: outside this phase's add-only Hiring scope).
5. **Durations in working days** reuse the company calendar task deadlines use; no new calendar. No decision needed.
6. No overlap with Approval Matrix: no step decides, routes or reminds; a send back cannot jump over an approval; "Stop here" is refused inside parallel work so it never abandons an open approval.

## 10. Self-score against the design bar

| Bar | Score | What is still weak |
|---|---|---|
| Hero moment (build "receipt missing → send back" in under a minute, see it run as two people) | strong | The buttons → "Add a path for each answer" → drop a send back flow is fast, but a new task still opens with the shipped single "Done"; the path helper names the last path after the last button (it is the Otherwise path). |
| Zero dead-ends | good | Every empty state has a next step; a capped send back can be retried to carry on. A Hiring stage cannot be deleted anywhere (Hiring has no door). A notice to someone without a login is skipped quietly (said in progress, not to the designer up front). |
| Plain language | good | Notices show details in words, but a detail whose label changes later stays as typed. The Try it out sample select resets to "Choose…" after showing a path (shipped). "Workflow section" still names sections for steps inside paths ("follows its group", shipped). |
| Motion / look | good | New blocks reuse the shipped cards, chips and choice cards; no new motion beyond hover. Inspector card summaries refresh on the next redraw after typing a title (shipped behaviour). |
| Keyboard | good | Every new control is a native input/select/button and reachable by Tab; the inspector still has no Escape-to-close (shipped). |

Also weak: the announcement path was exercised by the backend suite and the probe, not by a browser run (local announcements were installed late); no real touchscreen.

## 11. What P4 needs to know

- **Task completion path**: `pb.workflow.studio.answer(task_id, values, complete)` (`workflow_studio.py`) → `D.validate_answers` (forms) or `D.validate_outcome` (task/confirm buttons + note) → `WorkflowStep._finish(cleaned)` → `run._advance()`. `task_detail` returns `buttons`, `text` (confirm), `sent_back`. Bookkeeping keys in answers start with `_` and never become values (`_values`).
- **Assignment and activities**: `WorkflowStep._execute`, branch `self.kind in D.PEOPLE` (`workflow_models.py`) → `service._resolve_owner(run, owner)` (`workflow_progress.py`, kinds incl. `managers_manager`) → one `mail.activity` on the run with `workflow_step_id`. "My tasks" = `tasks()` (kinds `D.PEOPLE`).
- **Where a pool owner would hook**: `_resolve_owner_on` returns one uid today; a pool would return several and `_execute` would create one claimable activity (or one per member) and `answer`/`_task` would accept any member until claimed.
- **Where reminders would hook**: `_check_waiting_step` (`workflow_studio.py`) does nothing for waiting person steps today; D2 says feed them into the approval engine's late handling instead of adding a chaser here.
- **Notices** go through `_notify_step` (`workflow_steps.py`): inbox only, staff logins only; the employee home (portal) needs its own surface.
- **Send back** resets with `D.reset_range` and restarts the walk in `_advance` (`signals['restart']`); a P4 inbox must show the `_sent_back` note on the task.

## 12. Needs an owner decision / follow-ups

- §9 overlaps 1–4.
- Whether Hiring set-up should gain its own "Add a stage" and "Remove a stage" (company stages cannot be deleted today).
- Local database `am_wf2p3b` is left in place (clone of `am_wf2p3` + announcements installed + this phase's test workflows, the Hiring stage "Culture chat", the stage "Booked for payment", and a local-only password on the local viewer login `p3a.viewer`); the local server was stopped.
