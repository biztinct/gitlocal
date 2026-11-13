# Workflow Studio — independent second opinion

**Date:** 10 November 2026 · **Reviewer:** separate session, read-only · **Baseline:** `f68945ecc` on `19.1`, `pb_lifecycle` 19.0.1.9.0.

Later commits `5c883d72c` and `c3f3993cd` add only the review pack (8 documentation files, no code). `pb_lifecycle` has no uncommitted changes. The documentation therefore describes current source.

**How this was produced.** Read in full: the review pack, `workflow_studio.py`, `workflow_models.py`, `workflow_definition.py`, `workflow_progress.py`, `workflow_configuration.py`, `workflow_record_context.py`, `app.js`, `graph.js`, `record-context.js`, the OWL wrapper, the POC README. Adjacent modules (approval engine, Matrix, inbox, filter kit, Lifecycle journeys, Hiring, Expense, leave, access) were surveyed by two read-only sub-agents with file:line citations; their findings are marked *(survey)*. Not done: no tests were run, the live application was not opened, the original POC was not exercised by hand, vendor documentation was not re-checked. Each finding says whether it is **Confirmed** (read in source), a **Risk** (inferred, needs a test) or **Missing evidence**.

A clickable prototype of the proposed interaction is in [second-opinion-poc.html](second-opinion-poc.html).

---

## 1. Recommendation

**Keep the direction. Do not add block types. Fix four structural problems before any wider rollout.** Confidence: high on the findings read in source, medium on the two that need a runtime test (F10, F15).

What is right and should stay: one definition behind every view; immutable published versions with pinned runs; publish separate from activate; approvals referenced, not rebuilt; `base_automation` used only to capture events; module actions limited to registered operations; the permission split between viewing, designing and publishing.

What blocks the stated goal ("one intuitive experience across all modules, no duplication"):

1. **Approval-capable records can barely be orchestrated.** Every workflow on Expense, Leave, Pay run or a Hiring offer must contain an approval step, and that step submits approval when it is reached. A simple "when a claim is paid, do X" cannot be built (F1).
2. **One automatic workflow per record type.** Activation refuses a second workflow with the same trigger kind regardless of its filters (F2). This contradicts the record-only design and rules out per-leave-type or per-department flows.
3. **Most of the workforce cannot take part.** Tasks and forms need an internal login; employees here are portal accounts and many managers have none (F3). The older journey runtime already solves this with token pages.
4. **The user still has to learn the software's concepts.** Stages versus Sections, four views, a third inbox, progress hidden in a menu on native forms that most screens do not use (F6, F7, F12).

The additional `pb.workflow.*` runtime is justified: `pb.journey.*` is a flat checklist with no branching, joins, versions or conditions *(survey: `journey_template.py:85-128`)*, and bending it into a graph engine would have been worse. The duplication is not in the runtime; it is in the surfaces around it (inbox, forms, conditions, reminders, participant pages), where Studio rebuilt things the product already has.

---

## 2. Findings

Severity: **A** blocks the product goal · **B** will hurt in real use · **C** polish or hygiene.

| # | Sev | Kind | Area | Evidence | Impact | Proposed change | Verify |
|---|---|---|---|---|---|---|---|
| F1 | A | Confirmed | Approval coupling | `_validate` passes `approval=bool(native_processes and not after)` (`workflow_studio.py:246-248`); `_validate` errors "Use the existing Approval Matrix for this process" when no matrix node (`workflow_definition.py:416-417`). The matrix step adopts a request only in `pending/blocked/approved`, otherwise calls `engine.submit` (`workflow_models.py:541-557`). | On Expense: a "status changed to Paid" workflow must include an approval step that then tries to submit a paid claim. A "claim created" workflow submits the draft for approval on the employee's behalf. Same shape for Leave, Pay run, Hiring offer. Only `approval_applied` workflows are free of this, and that event fires at Approved, not Paid. | Drop "must contain approval". Replace with "must not bypass or duplicate approval": no approval step is required; when present it defaults to **follow the existing request** and may **submit** only where the module adapter declares a submit operation and the workflow starts before submission. | Expense and Leave cases T1–T4 in §7. |
| F2 | A | Confirmed | Coexistence | `activate` raises if any other enabled workflow on the same company + model has the same trigger kind (`workflow_studio.py:402-409`). Scope is not compared. | Module-wide and record-only automatic workflows cannot both be active. Two "field changed" flows watching different fields cannot both be active. DESIGN_REVIEW §6 says "multiple workflows can still match the same record"; true only for manual starts. | Conflict = same trigger **and** overlapping scope **and** overlapping effect. Otherwise allow, and list the co-running workflows on Review. | T5, T6. |
| F3 | A | Confirmed | Participation | `_staff()` requires `base.group_user` (`workflow_studio.py:27-29`); owners with `share=True` are rejected at validation (`:303`) and at run time (`workflow_models.py:510`). Employee logins are portal/share accounts (`pb_me_portal/models/ess_landing.py:12,38`). Manager owner needs `parent_id.user_id` (`workflow_progress.py:43-45`). | "Ask the employee for details" and "employee's manager does X" fail at run time for ordinary employees and for managers without a login. | Participant surface on the employee home for portal accounts, plus the existing token-link pattern from Lifecycle (`journey_task.py:80-96`, `token_pages.py:79-106`) for people with no login. | T7, T8. |
| F4 | A | Confirmed | Lateness and failure | Wait deadline → step `failed` (`workflow_studio.py:751-752`); `_advance` then sets the run `failed`; cron scans only `running/waiting` runs (`:740`); `run_action` needs Designer (`:680`). Tasks have a due date but no reminder, escalation or reassignment. `_resolve_owner` never calls `biz.approval.delegation.covering` *(survey)*. The engine already has reminder → escalation → reassign (`engine.py:1560-1688`) and Lifecycle has daily reminders (`lifecycle_reminders.py:50-190`). | A normal business event (nobody answered in time) becomes an error only a designer can clear. One failed step freezes time-based waits, mail checks and approval-following in sibling parallel paths. A person on leave blocks the process. | Make lateness an outcome on each task and wait: remind / pass to backup / carry on / take another path. Reuse the engine outbox and escalation job. Keep polling healthy branches of a run that has a failed step. | T9–T11. |
| F5 | A | Confirmed | Language | No translatable strings in `static/workflow/*.js` (0 uses of a translation helper); `pb_lifecycle/i18n/vi_VN.po` has 0 workflow entries; validation texts in `workflow_definition.py` are raw English. `save_draft` classifies errors by English fragments (`workflow_studio.py:322`); fragment `'stage order'` no longer matches the current text "Keep steps in their section order." (`workflow_definition.py:329`). | Vietnamese and Indonesian users get an English-only tool. The section-order guard on drafts is dead (publish still validates). | Structured error codes from `validate`; translatable UI (see F19). | T12. |
| F6 | B | Confirmed | Inboxes | Task = `mail.activity` on `pb.workflow.run`, note says "Open Workflow Studio → My tasks" (`workflow_models.py:526-532`); completing from the activity UI is blocked (`:607-616`). The approvals inbox is hard-wired to `biz.approval.request` (`inbox_facade.py:212-213`) *(survey)*. | Three places to look: Activities, Approvals, Studio "My tasks". The activity people see cannot be completed where they see it. | One "My work" list. Either a union facade over approval requests and workflow steps, or a new source on the existing inbox. Attach the activity to the business record with a deep link to the task. | T13. |
| F7 | B | Confirmed | Entry and progress | "View workflow" / "Set up workflow" exist only in the native form action menu (`workflow_studio.js:89-98`). The product's main screens are custom boards and side panels. Every native form load fires `record_runs` for every internal user (`:57-71`); for viewers it also parses the form view (`workflow_record_context.py:19`). | Progress is invisible on the screens people use. A background call on every form open across the app. | A small embeddable progress component that module screens place where their status already shows; load on demand. | T14. |
| F8 | B | Confirmed | Double-ups | Overlap list reads only `base.automation` (`workflow_studio.py:219-222`). Hiring rules live in `pb.hiring.automation.rule` (19 events, `automation_p8.py:53-108`) *(survey)*; approval messages come from the engine outbox (`engine.py:1031-1389`); Lifecycle reminders from its own job. Email duplicate check is by template id across the whole graph (`:296-298`). | The existing automations that matter are not shown. Same template on two mutually exclusive paths is refused; two different templates saying the same thing pass. | Each module declares what already happens per stage or event (see §3 contract). Show it in place in the builder. Duplicate check per path, per recipient, per event. | T15. |
| F9 | B | Confirmed | Execution identity | `execution_user_id` defaults to the creator (`workflow_studio.py:194`); events and runs fail when that user is inactive (`workflow_models.py:198-199, 265-266`). | When the designer leaves, every run of their workflows stops. | A per-company service identity, or a block in Access when deactivating a user who runs workflows. | T16. |
| F10 | B | Risk | Initiator | `_capture` records `self.env.uid` as initiator (`workflow_studio.py:519`). Date triggers run from the scheduler. | "Person who starts this", manager fallback and "started by · role" filters resolve against the system account. | Each model declares its subject person (employee, requester). Use that, not the trigger's uid. | T17. |
| F11 | B | Confirmed | Timing of rules | A branch reads live values if any path has grouped rules, otherwise the start snapshot (`workflow_models.py:347`). | Two rules that look alike behave differently. | One rule: values are read when the decision is reached. Mark legacy graphs with a version flag. | T18. |
| F12 | B | Confirmed | Stages vs Sections | Two toolbar buttons and a dialog whose body is mostly disclaimers (`app.js:23`, `record-context.js:10`). Section order is an enforced constraint (`workflow_definition.py:328`). Stage strip lists every selection value in declaration order; for Expense that puts Refused between Approved and Paid (`expense_claim.py:46-52`). | The concept the user found confusing is still there, now with an explanation attached. | §4. | Usability test U1. |
| F13 | B | Confirmed | Technical controls | Watched fields = native multi-select of every stored field (`app.js:27`); "who can start" = all security groups (`workflow_studio.py:233`); waits in hours only, no relative dates in filters; raw UTC timestamps (`app.js:77`); `<h3>` inside `<button>` (`graph.js:15`); HTML5 drag does not work on touch. | Reads as a technical tool. | Curated field lists per module; roles from Access profiles; "3 working days", "1 day before start date"; local times; pointer-based drag. | U2, T19. |
| F14 | B | Risk | New-process approval | Publishing creates a `biz.approval.process` (`workflow_studio.py:373-378`); activation does not check that a route is bound. Engine refuses submit without a binding (`engine.py:122-129`) *(survey)*. Facts limited to amount and urgent (`workflow_definition.py:166`). | First real run fails at the approval step. | Activation checks coverage through the Matrix facade; let form answers be declared as facts. | T20. |
| F15 | B | Risk | Submit path | Studio calls `engine.submit` directly; the Expense screen's own send does extra work first (`me_expense.py:371-390`) *(survey)*. | Claims submitted by a workflow may differ from claims submitted by a person. | Submit only through the module's declared operation (F1). | T2. |
| F16 | B | Confirmed | Module contract | Ownership is a hard-coded prefix table in Studio (`workflow_studio.py:119-150`); Hiring is special-cased in six places (`:115, :237-240, :305, :537-543`; `workflow_record_context.py:49, 55, 72`). No module implements `_workflow_capabilities` or `_workflow_execute` *(survey: none found)*. | "Use a module action" is empty for every record type except Hiring. Adding a module means editing Studio. | §3 contract. Move the Hiring cases behind it first. | T21. |
| F17 | C | Confirmed | Parallel schemas | Conditions: engine `{fact, op, value}` with 8 operators (`definition.py:36`), filter kit section state, Studio nested tree with 13 operators plus a separate domain compiler (`workflow_definition.py:14, 57-123`). Forms: Lifecycle JSON with 3 types, Hiring relational with 9 types and three languages, Studio JSON with 12 types and show-if. | Three things to maintain and to explain. | One condition leaf format shared with the engine (Studio adds nesting). One form field vocabulary; migrate Lifecycle questions to it first. | — |
| F18 | C | Risk | Scale | One job each minute advances up to 300 runs and re-reads source values (`workflow_studio.py:740-775`); approval-applied is found by polling the event log (`:727-737`); no retention for events or logs. | Latency grows with the number of waiting runs. | Wake a run when its task, approval or mail changes; index and prune; publish a workload target. | T22. |
| F19 | C | Risk | Front end | Iframe, string-built HTML, own CSS and icons. Brand colour differs from the product token. 34 of about 55 font-size rules are 14 px or below. | Outside the product's theme, translations, shortcuts and components. | Rebuild the builder as product components when doing §4; reuse filter-kit and form components. | — |
| F20 | C | Risk | Shared templates | Run versions are pinned; message templates are not. | A later edit changes what a running process sends. | Default to "copy for this workflow"; shared edit stays available with the warning. | — |
| F21 | C | Risk | Hygiene | Generated automation rules outlive an uninstall *(survey)*. Viewer rule shows every run; narrowed only by source access, so new-process runs are visible to all viewers (`workflow_security.xml:32`). | Minor. | Uninstall hook; scope viewer rule for runs with no source. | — |

---

## 3. Ownership and reuse map

| Concern | Owner today | What Studio does | Verdict |
|---|---|---|---|
| Approval route, people, backups, amount limits, apply | `biz.approval.engine` + Matrix | References it; submits or adopts | **Keep.** Change "must include and submits" to "follows, submits only via module" (F1). |
| Approval reminders, escalation, reassign | Engine outbox and hourly job | Nothing for tasks | **Reuse** for workflow tasks (F4). |
| Inbox | `pb.approval.inbox` ("mine / all / returned / done") | Separate "My tasks" | **Consolidate** into one list (F6). |
| Conditions | Engine facts; filter kit | Third format | **Share** the leaf format (F17). |
| Forms for people without a login | Lifecycle token pages; Hiring public pages | Internal only | **Reuse** token pages (F3). |
| Form builder | Hiring (relational, three languages); Lifecycle (3 types) | Third builder | **Keep Studio's as the general one**, retire Lifecycle's simple schema onto it; leave Hiring application forms alone. |
| Checklists for joiners and leavers | `pb.journey.*` | Separate runtime | **Keep both for now.** Freeze journeys; later express a journey template as a Studio workflow. Do not migrate running cases. |
| Stage values and transitions | Each module | Reads the status bar; Hiring rename | **Module contract** below (F12, F16). |
| What already happens (messages, to-dos, balance changes) | Module code, Hiring rules, engine outbox, Lifecycle reminders | Reads `base.automation` only | **Module contract** (F8). |
| Access | `biz_access` | Three groups, re-checks | **Keep.** Use Access profiles in pickers, not raw groups (F13). |
| Message templates | `mail.template`; Hiring's own | Shared editor | **Keep**, default to a copy (F20). |

**Module contract (proposed, one method per module, read-only declarations plus guarded operations):**

- stages: ordered real values, which are exits (Refused, Cancelled), which are held by approval;
- transitions: who or what moves the record into each stage, in words, and whether Studio may trigger it;
- effects: what already happens on entering each stage or on each event (message, to-do, balance change), with owner;
- subject person and manager resolver for the record;
- operations Studio may call, each guarded by the module;
- where the progress component goes on the module's own screen.

Expense, Leave and Hiring first. Hiring's six special cases in Studio move behind it.

---

## 4. Stages, sections and progress — proposed interaction

**One concept on screen: stages.** For a record that belongs to an app area, the stages are the area's real statuses, shown locked. For a brand-new process, the stages are the designer's own and can be renamed and added. "Sections" disappears as a word and as a button.

```
 When [an expense claim] [is created], [for everyone]

 1 Draft            2 Waiting approval        3 Approved             4 Paid
 🔒 Expenses        🔒 Expenses               🔒 Expenses            🔒 Expenses
 gets here when:    gets here when:           gets here when:        gets here when:
 employee starts    employee sends it         last approver says yes Finance marks paid
 ────────────────   ───────────────────────   ────────────────────   ─────────────────
                    ALREADY HAPPENS HERE      ALREADY HAPPENS HERE
                    · Manager, then Finance   · Message to employee:
                      over 5m  (Matrix) Open    approved
                    · Message to approver
 YOUR STEPS         YOUR STEPS                YOUR STEPS             YOUR STEPS
 [Receipt details]  [No decision in 3 days →  [Schedule payment]     [Tell employee
                     remind, then Finance]    [Paper receipt? …]      it is paid]
 + Add a step       + Add a step              + Add a step           + Add a step

 ⊘ If an approver says no → Refused; later steps are skipped.
```

Rules:

- **Viewing.** The same picture appears on the record, with the record's position marked and one sentence above it: "Waiting for Hoa Pham: finance check." A stage is ticked only when the record really left it. Exits (Refused, Cancelled) are shown as a note, not as a column in the line.
- **Adding work.** A step is added under the stage in which it should happen. Placing it there *is* its trigger and its wait: there is no separate "wait for this stage" block for the common case.
- **Editing stages.** Locked stages show who owns them and offer "Open in Expenses". Where the module allows a rename (Hiring), the pencil appears with the shared-impact warning. On a new process, stages are freely editable.
- **Moving a record.** The line under each stage name says what moves a record into it. Studio adds a move only where the module declares an operation; then it appears as a step "Move to Phone screen" in the stage it leaves.
- **Approval.** Shown inside the stage that holds it, as one grey row with its route and an Open link to the Matrix that returns to this step. On a new process it is a placeable step.
- **Order and dragging.** Order is stage, then position in the stage. Dragging a card to another stage changes when it runs. A step that uses earlier answers cannot be dragged before the form that collects them; the message says why. Undo on every move. Keyboard: Alt + arrows.
- **Views.** Two, not four: "By stage" and "Compact" (the wrapping left-to-right, right-to-left row). People becomes a "Show who" switch. A full flowchart stays available for unusual processes but is not a top-level choice.

Leave works the same way (To send → Waiting approval → Approved, exit Refused), with "leave balance is reduced" shown as something that already happens. Both are in the prototype, with a new-process example.

---

## 5. Implemented, prototype-only, proposed

| Capability | Shipped at baseline | Original POC only | Proposed here |
|---|---|---|---|
| One definition, several views | Yes (4 views) | 3 views | 2 views + "Show who" |
| Drag to reorder, validation, undo | Yes (mouse; Move dialog for touch) | Yes | Pointer drag incl. touch; keyboard |
| Multi-field forms, save and resume | Yes, internal users only | Yes (files simulated) | Employees and no-login people |
| Conditions on steps, paths, waits | Yes | Decision tables | Sentence wording; relative dates |
| Approval | Must include; submits or adopts | Sample routes | Follows by default (F1) |
| Record stages | Read-only strip; Hiring rename | Hiring sample editing | Stage-led builder and record view |
| Workflow from a record | Yes; record-only by id filter | — | "Try on one record first" on the normal workflow |
| Several automatic workflows per record type | No (F2) | — | Yes, with listed coexistence |
| Lateness handling | Deadline → needs attention | Simulated timers | Remind / backup / carry on / other path |
| Module actions | Hiring stage move only | — | Via module contract |
| Existing-behaviour display | `base.automation` list on Review | Sample catalogue | In place, per stage, from modules |
| One inbox | No (separate My tasks) | — | Yes |
| Translation | No | Sample three-language templates | Yes |
| Rehearsal with people and timers, version compare, AI drafting, external apps | No | Yes / proposal | Not prioritised |

Exclusions behind "all modules": only models with a company field that the user can read; no technical models; custom screens are not wired for entry; module actions exist for Hiring only. Behind "new process": no new record type or fields; approval facts limited to amount and urgent.

---

## 6. Sequence

| Step | Scope | Trade-off | Done when |
|---|---|---|---|
| 1. Unblock | F1, F2, F11, F14, F5 error codes. Backend only, small. | Loosens a guard; needs the bypass tests first. | An Expense "when paid" workflow and a Leave "sick leave only" workflow publish, activate together with another automatic workflow, and run without touching approval. No workflow can move a record past approval. |
| 2. Module contract | F16, F8, F10, F15 for Expense, Leave, Hiring. | Each module gains a small declaration to maintain. | Studio contains no model names. Builder lists stages, transitions and existing effects for the three modules from their declarations. |
| 3. Stage-led builder and record view | F12, F13, F7, F19. Built as product components. | Largest piece; replaces the iframe builder. Published definitions keep working: sections map to stages or stay as a hidden grouping. | Five process owners build "claim paid → tell employee" unaided in under 5 minutes and can say what moves a claim to Approved (U1). |
| 4. One list of work, everyone can take part, lateness | F6, F3, F4, F9. | Touches the inbox and employee home. | A portal employee completes a form from their home; a late task reminds and passes to the backup with no designer involved. |
| 5. Consolidate | F17, F20, F18, F21. | Unseen by users; reduces upkeep. | One condition leaf format; journey questions use Studio fields; run wake-ups; retention set. |

Compatibility: schema stays `payobook.workflow/1` through step 2. Step 3 adds an optional stage binding per node; existing versions render through a fallback. No running run is migrated.

---

## 7. Test plan for the remaining gaps

Backend, each on Expense and Leave unless noted:

- T1 Workflow with no approval step on an approval-capable model publishes and runs.
- T2 A workflow never changes the approval state of a claim other than through the module's own send; compare a claim sent by a person and one sent by a workflow, field by field.
- T3 "Changed to Paid" workflow runs once per claim, never calls the engine.
- T4 Approval step on an already-applied record completes without a new request.
- T5 Two automatic workflows, disjoint filters, same trigger: both active, each fires only for its records.
- T6 Record-only pilot beside a module-wide workflow: listed as overlapping, effects not doubled.
- T7 Task assigned to a portal employee: delivered, completed, answers validated.
- T8 Manager with no login: token link issued, single use, same page for unknown and used links.
- T9 Wait deadline with "carry on" and with "other path"; no designer action.
- T10 Task overdue: reminder, then backup from People & backups, cover honoured.
- T11 Parallel paths, one step failed: sibling timed wait still completes.
- T12 Validation returns codes; Vietnamese user sees translated text; out-of-order draft refused.
- T13 Approval and workflow task appear in one list; completing from the record works.
- T14 No workflow call on form open for a user with no workflow permission.
- T15 Adding a message where the module already sends one produces a warning naming it (Expense approved; Hiring stage entered).
- T16 Deactivating the designer does not stop runs.
- T17 Date-triggered start: initiator is the record's subject person.
- T18 Same rule written flat and grouped takes the same path after the record changes mid-run.
- T19 Filter "start date within 3 days" evaluates the same in preview, native domain and at run time, across a timezone boundary.
- T20 New process with approval cannot be activated without a route.
- T21 Hiring stage move through the contract keeps Joined protected and fires each Hiring rule once.
- T22 5,000 waiting runs: time from task completion to next step under a stated target.
- Multi-company: every case above repeated with a second company's user expecting refusal.

Browser: drag by mouse, touch and keyboard with undo; 200% zoom; reduced motion; screen-reader pass over builder and task form; phone-width task completion.

Usability: U1 five process owners who have not seen the tool, Expense and Leave tasks, think-aloud; U2 the same on the current build for comparison.

---

## 8. Questions that only the owner can answer

1. Should ordinary employees (portal logins) and people with no login take part in workflow tasks? The findings assume yes.
2. Is a per-company service identity acceptable for running workflows, in place of the designer's own account?
3. Should joiner and leaver checklists eventually be built in Studio, or stay a separate product area for good?

---

## 9. Addendum, 11 November 2026 — owner feedback and revised proposal

Owner rulings: (1) employees and people without a login **do** take part in workflow tasks; (3) joiner and leaver checklists **are** to be built in Studio eventually; question 2 (service identity) is still open. The owner also ruled that the proposal must **add to** the shipped design, not replace it. Sections 4 and 5 above are superseded where they say "two views, not four" and "Sections disappears":

- **All shipped views and tabs stay**: Journey, Across, Flowchart, People; Build, Try it out, Review, Activity; the left step list; saved groups, module actions and reference steps. **By stage** is a fifth view over the same definition. The prototype renders Journey, By stage and Flowchart from one stage renderer with three layouts, so drag, keyboard move and Undo behave identically in each.
- **Sections stay** as "Just a heading" stages (grouping only, no record effect). No migration: existing `stages[]` entries become heading-kind stages.

### User-made stages (the owner's main concern)

Goal: a designer adds a real stage from the Stages screen, with no code and no change to the owning module.

Design: a **workflow stage layer** beside the module's own status field.

- New model, e.g. `pb.workflow.stage`: company, source model, name, sequence, `kind` (`yours` | `heading`), `anchor_value` (the module status it sits after and "counts as"), `enter` (`auto` | `person` | `rule`), `enter_who` (owner spec, same shape as a task owner), `enter_rule` (condition tree), `must_finish` (bool), `target_hours`.
- Record position: `pb.workflow.record.stage` keyed by (model, res_id) → current workflow stage, entered_at, entered_by. Written only by the Studio facade. The module's own status field is never written by this layer.
- Invariant: a record may be in a user-made stage only while its module status equals that stage's `anchor_value`. When the module status changes, the position is cleared (or advanced to the first user-made stage anchored on the new status). This is what keeps module reports, approval and accounting correct.
- Entering: `auto` when the previous stage's steps are done; `person` exposes a guarded "Move to …" operation (owner check + `must_finish` check + source write access); `rule` evaluated with the same interpreter as waits.
- Display: the module contract (§3) gives the built-in stages; Studio merges user-made stages into that sequence for the strip, lists and filters. A stored computed "display stage" is available to list views and filters.
- Hiring is the exception: its stages are already rows. A user-made Hiring stage should be a real `hr.recruitment.stage` created through a new `pb.hiring.act('stage_add')` that requires a family and inherits the guards of that family; Studio calls it rather than using the layer.
- New process: all stages are user-made; `anchor_value` is empty.

Tests: record never shows a user-made stage whose anchor differs from its status; "person" move refused for the wrong person and while required steps are open; deleting a stage with records in it is refused or moves them explicitly; time-in-stage totals equal elapsed time.

### Step types added in the prototype

Move to a stage; Send back for changes (bounded: to an earlier human step, re-runs the steps between); Update the record (fields the module marks as safe only; never status or money); Create something (registered creators: task, letter from `pb.letter.template`, asset request); In-app notice; Ask to confirm; Repeat for each line; Start another workflow; Stop here. Owner options added: a team where anyone can pick up, manager's manager. Each human step gains: due, what happens when late, outcome buttons, "must finish before leaving the stage", guidance.

The "What is covered" page in the prototype lists 40 capabilities against the shipped build and this proposal.

### Owner rulings, 11 November 2026 (second round)

- **Question 2 is decided: workflows run at system level, not as the person who built them.** Replace the per-workflow `execution_user_id` default (creator) with one dedicated, non-login "Workflow" service user per company. It must not be the superuser: give it a fixed, reviewed permission set (read source records, create activities, queue mail, call registered module operations) so a designer cannot use a workflow to reach data the service identity is not meant to touch. Keep recording the human who started or triggered a run as the initiator for history. Drop the "choose another execution account" control from the editor.
- **Who may build stays a matter of groups**, as shipped: `group_workflow_viewer`, `group_workflow_designer`, `group_workflow_publisher`, assigned through Access. Workflows are company-level objects; there is no personal workflow.
- **The shipped Flowchart canvas stays as it is** (dotted canvas, curved connectors, "+" insert points, side-by-side paths, zoom and fit). The prototype's Flowchart is a simplified drawing of it, not a replacement. User-made stages, the new step types and the stage headers are to be added to the existing canvas. Only change to the canvas itself: make dragging work with touch as well as a mouse (F13).

### Correction to the execution-identity ruling, 11 November 2026 (third round)

The owner asked for this to follow the framework's own practice. Checked against the local Odoo 19.0 source (`/Users/adity/odoo19/odoo`):

- `base.automation` runs its server actions with system rights while keeping the triggering user's uid: `for action in self.sudo().action_server_ids` (`addons/base_automation/models/base_automation.py:824`), rule lookup and domain filtering also under `sudo()` (`:707, :747-769`).
- Scheduled jobs run as the job's own `user_id` (`odoo/addons/base/models/ir_cron.py:110, :426, :482`); jobs installed from module data run as the system account.
- The framework's safeguard is who may create a rule (administrators), not a restricted run-time identity.

**Revised ruling — supersedes the "dedicated Workflow service user per company" bullet above:**

- **No new user.** Workflows run the native way: with system rights in the background, in the workflow's company, keeping the triggering person as the recorded initiator. Remove `execution_user_id` from `pb.workflow`, `pb.workflow.version`, `pb.workflow.event` and `pb.workflow.run` (or stop reading it), and remove the "execution account" control. `_service()` becomes `sudo().with_company(...)` with the internal context flags, not `with_user(...)`.
- **The safeguards move to build time and to the step catalogue**, which is already tighter than native automation (no free code):
  1. only Designer builds, only Publisher publishes and activates (groups as shipped, assigned through Access);
  2. at design time the designer may only pick record types, fields, templates and stages they can read themselves (already the case in `_models`, `_source_fields`, `_mail_template`);
  3. steps stay limited to registered, module-guarded operations; "Update the record" only offers fields the module marks as safe;
  4. approval is never applied by the workflow; it still goes through the approval engine with the real approvers;
  5. assigning a task still never grants the assignee access to the record; keep the per-assignee read check in `_execute`;
  6. company isolation stays explicit on every query, since record rules no longer apply under system rights.
- **Keep the participant-side checks as they are**: `tasks`, `task_detail`, `answer`, `progress`, `submission` run as the signed-in person.
- Scheduled starts have no human trigger; record the initiator as the record's subject person from the module contract (F10), and show "System" in history. Check that the system account's display name is the product name, never the framework's bot name (white-label rule).
- F9 is closed by this change. Add test: deactivating the designer or publisher of a workflow does not stop its runs; a designer cannot select a field they cannot read; two companies never see each other's runs under system rights.
