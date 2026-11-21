# WORKFLOW-2 · Phase 3b handover — more step types, richer step settings, candidate stages through Hiring

Read first, completely: `WF2_LEDGER.md` (R1–R9, R2a, D1–D13, conventions, gotchas G1–G27), `WF2_P3A_REPORT.md` (§5 deviations, §6 R1 audit, §9 "What P3b needs to know"), `WF2_P2_REPORT.md` §7 (contract and stage JSON), `EXISTING_BEHAVIOUR_INVENTORY.md` (Part 1.4 Hiring stages; Part 2 letters library, announcements, approval outbox notifications; the "Other request" and pay run rows). The prototype `docs/design/workflow-studio/review/second-opinion-poc.html` shows the step list group "New in this proposal" and the richer step settings; its wording is the reference.

Design bar (R9, verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** Every state designed, zero dead-ends, plain English, purposeful motion, keyboard reachable, Lucide-style SVG icons (never emoji or glyphs). R7: "Odoo"/"OdooBot" never in a user-visible string. R8: no model or field names and no internal words on screen. R1: everything shipped stays.

## 1. Scope

1. **Task buttons (outcomes)** — the base for "send back".
2. **Eight new step types**: Move to a stage · Send back for changes · Update the record · Create something · Tell someone in the app · Ask someone to confirm · Start another workflow · Stop here.
3. **Step settings**: "Manager's manager" owner; wait "when time runs out" choice; Duplicate step.
4. **Candidate stages added through Hiring** (D10).
5. **Contracts for two more record types**: "Other request" and Pay run (add-only), so their end statuses are exits and their existing behaviour shows.
6. Carry-overs from P3a: Review lists "already happens" once; the sentence never shows a half-written filter; tall "already happens" lists collapse.

### Binding non-goals

- **"Repeat for each line" is not built in this phase** (needs sub-runs; report what it would take). Team pools / "anyone can pick it up", reminders, backups, inbox merge and employee-home participation are P4 (D1, D2).
- No approval feature of any kind in Studio (R2d). No status writes (R2c): the only way a record's own status changes is a module-declared action.
- No free-form field writes, no code, no arbitrary method calls. Everything a step does is a registered, module-guarded operation.
- Area modules are add-only: `pb_hiring` (one facade verb + contract keys), `pb_me_expense`, `pb_timeoff`, `pb_payruns`, `biz_approval_workflow` generic request (contract methods only — if the generic request model cannot take an add-only contract file in a module you are allowed to touch, put its contract in `pb_approval_config` or report). Do not change existing behaviour anywhere.
- Do not drop `execution_user_id` (G7). No translations (P5).

## 2. Verified plumbing

- Where step types live (from the P3a report): `TYPES` and `summary()` in `static/workflow/app.js`; `makeNode()` in `actions.js`; step list in `palette()`; per-type inspector blocks in `inspector()` with the reusable `ownerControl(path, owner, label, noRecord)`; server validation in `models/workflow_definition.py` (`TYPES`, `_validate`, error codes, `STRUCTURAL`); facade validation in `workflow_studio.py::_validate` and `workflow_configuration.py::_validate`; execution in `workflow_models.py::WorkflowStep._execute`; worker polling in `workflow_studio.py::_cron_workflows`; module actions via contract `actions` + `_workflow_execute`; double-up checks in `workflow_contract.py::_repeat_warnings`; route preview in `workflow_definition.py::route_preview` (Try it out).
- A task/form step waits as `state='waiting'` with a `mail.activity` on the run (`workflow_step_id`); the participant completes it through `answer(task_id, values, complete)` → `_finish` → `run._advance()`. Answers of done steps are exposed to conditions as `step.<node id>.<field id>` (`WorkflowRun._values`).
- `_advance` walks `d['order']` with `sequence()`/`visit()`; steps are rows created once per run in `_initialize` (unique per run + key); states `pending, active, waiting, done, skipped, failed`; skipping uses the inner `skip()`; section gates from P2 are asked once (G16).
- Stage layer: `pb.workflow.stage`, `pb.workflow.record.stage`, the position helper and `move_record_stage` in the P2 stage file; invariant = position valid only while the record's status equals the stage's anchor.
- Starting a run: `_enqueue(w, source_id, initiator, key, initial, request_id)` + `event._process()`; one active run per workflow + record.
- Subject person: `_workflow_subject()` → `{employee, user, manager_user}`; owner kinds today: `initiator, user, role, manager, field, subject`.
- Hiring: stage rows `hr.recruitment.stage` with `pb_key` (17 fixed keys) and computed `pb_family` (`pb_hiring/models/journey.py`), facade `pb.hiring.act(verb, payload)` → `_act_<verb>` (`pb_hiring.py`), verbs `stage_rename`, `stage_meaning`, `stage_reorder` in `board_p1.py`; per-role visible stages `pb_visible_stage_ids` and presets `pb.hiring.stage.preset`; `_ensure_journey_stages()` seeds and retires stock rows. Studio's Stages sheet candidate branch: `ownRows()`, `stageForm`/`canRealAt`, `saveStageForm` in `static/workflow/stages.js`.
- Letters library `pb.letter.template` / `pb.hr.letter` (draft → generated → sent; sending has its own approval) in `pb_lifecycle/models/letter.py`, `letter_approval.py`. Announcements `pb.hr.comm.post` with templates `pb.hr.comm.template` (own approval, 10-minute sender) in `pb_hr_comm`. Approval outbox notifications: `biz_approval_workflow/models/outbox.py` (`message_post` as a note to the user's partner + optional to-do).

## 3. Design

### 3.1 Task buttons

- Node key `buttons` on `task` (and `confirm`): list of 1–4 `{key, label}`; default one button "Done". Presets in the inspector: Done · Done / Cannot do · Yes / No · custom labels. Keys are slugs, unique per step.
- `answer()` for a task takes the chosen `outcome`; stored in the step's answers as `outcome` (and the label as `outcome_label`); required when more than one button. The participant screen shows the buttons as the completion actions (primary = first).
- Conditions: `step.<id>.outcome` becomes an available value after that step, type choice with the step's own labels — shown in the filter editor as "⟨step title⟩ · answer". Works in paths, "only when" and waits. Progress view shows the chosen answer on the step.

### 3.2 New step types

Each: entry in the step list under **More possibilities** (existing collapsible group), an inspector block, `summary()` text, validation with codes, execution, Try-it-out wording, progress wording, and — where it produces an effect — a double-up check (R2). All automatic steps run in the system environment with explicit company terms (R3, G1).

| Type key | Step list name / hint | Behaviour |
|---|---|---|
| `stage_move` | **Move to a stage** · "Put the record in one of your stages" | Target = a your-stage of this record type (or of this new process). At run time: if the record's status equals the stage's anchor → write the position (same code path as `move_record_stage`, bypassing the person check, logged as "by the workflow"). If the status is earlier → wait ("Waiting for this to reach ⟨anchor name⟩"); if later → skip with reason. Area stages are **not** offered here; when the contract has a stage-moving action (Hiring) the inspector shows "To move between ⟨Area⟩'s own stages use: ⟨action label⟩" with a button that adds that module action step. Validation: target exists, belongs to the model/workflow. |
| `send_back` | **Send back for changes** · "Return to an earlier step" | Target = an earlier `task`/`input` step on the main path. When reached: the target and every main-path step after it up to this one are reset to not-started (their activities cancelled, answers kept as prefill for forms, previous outcome cleared), the run continues from the target, and the target's assignee sees the sender's note (take it from the most recent task answer's optional comment; add an optional `comment` to task answers). Guards: refused at validation if an approval step, a module action, `update`, `create` or `start` lies between target and this step ("Steps in between would run twice: ⟨names⟩"); emails in between are allowed but named in a warning; at most 3 send-backs of the same step per run, then the step needs attention with "This has gone back three times. Someone should look at it." Must sit inside a path or carry an "only when" (otherwise it would always loop) — validation error with the fix. |
| `update` | **Update the record** · "Set a value the area allows" | Contract key `safe_fields: [{key, label, type: text|choice|number|date|yesno|person, options?}]`. Inspector: pick a field, give a fixed value or an earlier answer of matching type. Execution: one `write` of that field only, through a new contract method `_workflow_update(key, value)` when the module declares it, else a plain write restricted to declared keys. The area's stage field and any key not declared are refused in validation and again at run time. When the record type declares no safe fields the step is listed but explains "⟨Area⟩ has not opened any values to workflows yet." Declare modestly: Expense claim → the note; Candidate → priority/appreciation if present; Leave and Pay run → none. |
| `create` | **Create something** · "A letter or an announcement, as a draft" | Registered creators only, each reusing the existing feature (D8): **A letter** — a draft letter for the person this is about from a chosen letters-library template (needs a subject employee; sending keeps its own approval, Studio never sends it); **An announcement** — a draft announcement from a chosen announcement template (it then follows its own sign-off). Implement as a small registry on the facade (`_creators()` → key, label, availability, template choices, `run(source, node)`), each available only when its module is installed. Result link stored on the step and shown in progress ("Draft letter created · Open"). Idempotent on retry (store the created record reference on the step; never create twice). |
| `notify` | **Tell someone in the app** · "A notice, not an email" | Recipient = same owner choices as a task. Text = a short message with the existing value picker. Delivered as an in-app notification the way the approval outbox does it (a note to the person's inbox on the record or run; no email, no to-do). Double-up: warn when an existing `message` effect targets the same audience at that stage. People with no login: step is skipped with reason "⟨name⟩ has no login to show this to." |
| `confirm` | **Ask someone to confirm** · "Read and agree, one tap" | A task variant: `text` to read (required), one button (default label "I confirm"), who and due as a task. Records who confirmed and when; shown in progress and in the run's history. |
| `start` | **Start another workflow** · "Hand over to another process" | Target = an active, person-started workflow of the same record type (or a new-process workflow). Execution: enqueue a start for the same record with this run's initiator; does not wait for it. Guards: target must still be active at run time (else needs attention with a plain sentence); a workflow cannot start itself; chains longer than 3 are refused at run time; one active run per workflow + record still applies (if one is already running, the step finishes with "⟨name⟩ is already running for this record."). |
| `end` | **Stop here** · "End the workflow early" | Marks every remaining step skipped ("Stopped by ⟨step title⟩"), closes the run as finished, optional reason shown in progress. Must sit inside a path or carry an "only when" (same validation as send back). |

Try it out (`route_preview`): each new type gets a plain line ("Would move this to Payment scheduled", "Would send it back to Receipt details", "Would stop here"); nothing is executed.

### 3.3 Step settings

- Owner kind `managers_manager` ("Their manager's manager"): the subject's manager's own manager with a login; plain failure sentence when there is none. Offered only where "Their manager" is.
- Wait step, when it waits for a rule: new select "If it never happens in time" → **Flag it for attention** (today) / **Carry on anyway** (`on_timeout: 'continue'`, step done with reason "Carried on after waiting ⟨n⟩.") Durations in the wait inspector become "⟨number⟩ hours / days / working days" with the value stored in hours as today (working days via the company calendar already used for task deadlines).
- **Duplicate** button beside Move/Remove on every step except Start and approval: copies the step (new id, " (copy)"), groups copy their children; one Undo.

### 3.4 Candidate stages through Hiring (D10)

- Investigate first, write down what you find in the report: how a stage row without one of the 17 fixed keys behaves on the Hiring board, presets, per-role visible stages, the stage log, reorder, and Studio's contract (P2 deviation 8 hid keyless rows). Design the smallest **add-only** way for Hiring to accept a company-made stage that behaves like an ordinary "open" stage (the family of the stage it follows), survives `_ensure_journey_stages()` and upgrades, appears on the board and in presets, and can be renamed/reordered with the existing verbs.
- Add facade verb `pb.hiring.act('stage_add', {'name', 'after_stage_id'})` with Hiring's own write-permission check, and expose it through the contract as `_workflow_add_stage(name, after_key_or_id)`; Studio's Stages sheet for candidates then offers "A real stage" again, calls it, refreshes the catalogue and binds the section. Removal of such a stage stays in Hiring set-up.
- If it cannot be done add-only without touching existing Hiring behaviour, **stop that item and report** the options; ship the rest.

### 3.5 Two more contracts

- **Other request** (`biz.approval.generic.request`): stages from its own status with end statuses flagged `exit`; `submits_itself` as appropriate; effects none of its own beyond the approval engine's.
- **Pay run** (`hr.payslip.run` in `pb_payruns`): Draft → Waiting for approval → Done, exit Rejected; `approval: True` on the waiting stage; no subject; effects: payslips are checked when it is sent, payslips are finished when it is approved (plain sentences, from inventory 1.3). No actions, no safe fields.

### 3.6 Carry-overs

- Review: remove the two older banners ("Existing automation to review", "Also active for these records") and show their content inside the one "Already happens for these records" group; the acknowledgement checkbox stays, once.
- Sentence: a filter rule with no value yet is left out of the sentence; with no complete rule it reads "for everyone".
- "Already happens" lists in Journey and By stage show three rows then "⟨n⟩ more" (expand in place), so a long approval route does not stretch the column.
- Server refusals in the Stages sheet appear next to the row they concern, not only as a toast.

## 4. Safety rails

- Risky tier if you add any stored field or model (backups of all five databases first); normal tier otherwise. Say which you chose and why.
- Never publish, activate or start a real workflow on a live database, never create a real stage, letter or announcement there, never move a real record's stage, never send mail. All of that is tested on the local database.
- Each new effect type ships with its double-up check and with a static test that it cannot write an area's status field.
- Overlaps you find go under "Overlaps found" (R2a).

## 5. Test cases

Backend (add to the suite; all 80 existing stay green):

- T1 Task with two buttons: outcome required, stored, usable in a path rule; single button needs none.
- T2 `stage_move`: writes position when status = anchor; waits when earlier; skips when later; never writes the status.
- T3 `send_back`: target and steps between reset, form answers kept as prefill, run continues; third send-back flags; validation refuses an approval step in between and a send back with no condition.
- T4 `update`: declared field written; undeclared field and the stage field refused at validation and at run time; no safe fields → clear validation message.
- T5 `create` letter: one draft per run even after retry; no subject employee → plain failure; letter is not sent. Announcement likewise (skip with a note if the module is not installed in the test database).
- T6 `notify`: in-app note to the resolved person, no email queued, no activity; no login → skipped with reason; repeat warning against an existing requester message.
- T7 `confirm`: only the assignee can confirm; who/when recorded.
- T8 `start`: target enqueued once; self-start and inactive target refused; already-running handled; chain limit.
- T9 `end`: remaining steps skipped, run finished with reason; unconditional `end` refused.
- T10 `managers_manager` owner resolves and fails plainly.
- T11 Wait with `on_timeout: 'continue'` carries on; default still flags.
- T12 Hiring `stage_add` (if shipped): row created with the right family, shows in the catalogue as a real Hiring stage, survives `_ensure_journey_stages()`, rename/reorder verbs work, permission enforced; Studio keeps refusing its own stage layer on candidates.
- T13 Contracts for Other request and Pay run load; exits flagged; banned-word test extended.
- T14 Company isolation for every new step type (second-company fixture).

Browser (local database, clean console, screenshots checked by eye):

- U1 Step list shows the eight new steps under More possibilities with icons and hints; each can be added by click, by "+" and by drag in Journey, By stage and the canvas.
- U2 Inspector for each new type: every control works, empty and error states read plainly, Review lists exactly the right issues.
- U3 Build "Paper receipt missing → send back to Receipt details" with task buttons; Try it out shows both routes.
- U4 Run it locally end to end as two people: send back, redo, carry on; progress shows the answers and the loop.
- U5 `stage_move` to a your-stage and the record page track updates.
- U6 Candidate workflow: add a real stage from the Stages sheet → appears in Hiring's board set-up (if shipped).
- U7 Duplicate, then Undo.
- U8 Review shows "already happens" once; sentence with a half-written filter reads "for everyone".
- U9 Phone width and keyboard-only pass over the new inspector blocks.
- U10 No emoji/glyph icons, no banned words on screen.

## 6. Deploy and verify

Versions: `pb_lifecycle` → `19.0.1.13.0`; patch bumps for each touched area module; bump both workbench cache keys. Commits with explicit paths (area contracts and Hiring verb · Studio backend · screens · docs). Do not push. Deploy per ledger §3 to `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima` (sudima's Studio job stays off, 80 active jobs); suite on `p0clone` with the service stopped; asset signal + purge; start; warm. Verify hashes, versions, job counts (49 / 31 / 38 / 81 / 80), logs, HTTP 200 with the new cache key.

## 7. Report back (`WF2_P3B_REPORT.md`)

Commits and versions; T1–T14 and suite count; U1–U10 with evidence; deploy evidence; what you found and decided for Hiring `stage_add`; what "Repeat for each line" would take; deviations; R1 audit; overlaps found; self-score against the design bar; new gotchas in the ledger; what P4 needs to know (task completion path, where assignment and activities are created, where a pool owner and reminders would hook in).
