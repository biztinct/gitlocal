# WORKFLOW-2 · Phase 2 handover — module contract, "already happens", and user-made stages (backend)

Read first, completely: `docs/handovers/workflow2/WF2_LEDGER.md` (rulings R1–R9 and R2a, reuse decisions D1–D9, conventions, gotchas G1–G10), `WF2_P1_REPORT.md`, and `EXISTING_BEHAVIOUR_INVENTORY.md` Part 1 blocks 1.1 (Expense), 1.2 (Leave), 1.4 (Hiring) and Part 2 for the approval engine and Hiring automations. Design background: `docs/design/workflow-studio/review/SECOND_OPINION_REVIEW.md` §3, §4 and §9. The clickable prototype `docs/design/workflow-studio/review/second-opinion-poc.html` shows what the data must be able to drive in P3 (Stages screen, "Already happens here" rows, "Gets here when…" lines).

Design bar for anything user-visible (R9, verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** White-label (R7): the words "Odoo"/"OdooBot" never appear in a user-visible string. Plain English (R8) in every label and message.

## 1. Scope

Backend and data only. P3 builds the screens on top of this.

1. **Module contract**: each business area declares its record's stages, what moves a record into each, what already happens, who the record is about, and the operations Studio may call. Implemented for Expense claim, Leave and Hiring candidate. Studio reads it; a fallback keeps every other model working as today.
2. **"Already happens" data and the double-up check** (R2, D3, D8): one facade call returns, per stage, everything that already happens (module effects, approval-engine effects, Hiring automation rules, other Studio workflows). Validation warns before a step repeats one.
3. **Workflow stage layer** (R4, the owner's main concern): users create their own stages without programming. Sections become stages that are either a heading (today's behaviour), bound to one of the module's own statuses, or bound to a user-made stage.
4. **Stage gates at run time**: a section bound to a real stage waits for the record to be there.
5. **Subject person** (F10): the person a record is about, used for system-triggered starts and as a new task owner choice.
6. Small carry-overs from P1: G8 (Review double listing), a paused approval route also blocks activation of a new process.
7. **Bring `sudima` up to date** (D9).

### Binding non-goals

- No workbench UI work beyond what is listed in §3.7 (keep the shipped screens working; nothing shipped is removed — R1).
- No new step types (P3). No inbox merge, no reminders reuse, no portal participation (P4). No message clean-up in other modules (D5–D7 are a later phase).
- In `pb_me_expense`, `pb_timeoff`, `pb_hiring` you may **only add** the contract methods (and bump the manifest version). Do not change any existing behaviour, state machine, message or automation there.
- Do not touch `biz_approval_workflow` or `pb_approval_config`. Read them; call their public methods.
- Studio never writes a module's status field (R2c). The stage layer stores its own position beside it.
- Do not drop `execution_user_id` (G7).
- Never touch `pbf_preview` or `recruit_connect_20261023` (D9). Never `abm`.

## 2. Verified plumbing (do not re-derive; line numbers predate P1, locate by name)

- Studio already duck-types a module hook: `_actions()` and `_ownership()` in `pb_lifecycle/models/workflow_studio.py` call `self.env[model]._workflow_capabilities()` when it exists and read `actions` and `owners`; `_execute_action()` calls `source._workflow_execute(key, params)`. **No module implements either yet.** Because it is duck-typed, the three modules need no dependency on `pb_lifecycle`.
- Hiring special cases to move behind the contract: `_actions` (`hiring.stage`), `metadata` (`result['stages']`, excludes `joined`, `offer_accepted`, `offer_rejected`), `_validate` (`stage_key` check), `_execute_action` (calls `pb.hiring.act('journey_stage', {'applicant_ids', 'key'})`), `_ownership` (Hiring row); `workflow_record_context.py` `_record_stages` (job-scoped stage choices, rename flag) and `rename_record_stage` (`pb.hiring.act('stage_rename')`). P1 confirmed the Hiring facade accepts the system user.
- Stage discovery today: `workflow_record_context.py::_record_stages(model, record)` reads statusbar fields from the form view, falls back to `stage_id`/`state`; returns `{field, label, type, options[{key,name,…}], visible, current, approval_value, fixed}`. Used by `metadata`, `record_runs`, `record_setup`, `progress`, `approval_progress`.
- Definition schema (`workflow_definition.py`): top-level `stages: [{'name': …}]` (1–40) are today's Sections; every node has integer `stage` (index); main-path nodes must be in non-decreasing section order (`section_order` code after P1); grouped nodes share their group's section. Context fields `workflow.stage`, `workflow.completed_stages` refer to section indexes.
- Run loop: `WorkflowRun._advance()` in `workflow_models.py`, inner `sequence(ids)` / `visit(key)`; main path is `d['order']`. Worker `_cron_workflows` re-advances `running`/`waiting` runs and failed runs with a waiting step (G6: per-step savepoint, log once).
- System environment helper from P1 (`system(env, company)` or as named in the P1 report) — use it for all worker-side reads; add explicit company terms (R3, P1 T2).
- Approval engine, read-only use: process per model `biz.approval.process` (`model_name`, `connected`, `key`); `engine.resolve_binding(company_id, process_key, scope_keys=None, …)`; `engine.get_request(id)`; outbox message kinds queued by the engine: `your_turn`, `covering`, `notified`, `approved`, `returned`, `rejected`, `reminder`, `escalation` (`biz_approval_workflow/models/engine.py`, `outbox.py`). Outbox does not deliver to portal logins (inventory fact 4).
- Expense claim (`pb_me_expense/models/expense_claim.py`): `CLAIM_STATES` draft → submitted (label "Waiting approval") → approved → paid, exit refused; shim `submit_state='submitted'`, `driven=('approved',)`; subject `employee_id`; manager = `employee.expense_manager_id` else `parent_id.user_id`; paid is set by `_sync_paid`, nobody presses it; the module sends no message of its own.
- Leave (`pb_timeoff/models/hr_leave_approval.py` on stock `hr.leave`): `confirm` → `validate1` → `validate`, exits `refuse`, `cancel`; create auto-submits when a route is bound; stock to-do to the leave manager on create; stock messages to the employee on approve/refuse; balance consumed on approve; backdated alert; subject `employee_id`, manager `leave_manager_id` else `parent_id.user_id`.
- Hiring candidate (`hr.applicant`, `pb_hiring`): `stage_id` → `hr.recruitment.stage` rows with `pb_key` (17 keys) and `pb_family` open/done/closed (`models/journey.py`); move through `pb.hiring.act('journey_stage', …)`; Joined cannot be set by hand; automation rules `pb.hiring.automation.rule` (`event`, `action` send_email/todo/move_stage/tag, `recipient`, scope by department/country, `active`, company) and `BUILTINS` in `models/automation_p8.py`; rule screen: Hiring set-up → Automations.
- The employee home already keeps friendly status labels per request type (`pb_me_portal/models/pb_me_home.py` registry, extended per module). Reuse those label sources where the module has them rather than writing new wording (R2a).
- Tests: `pb_lifecycle/tests/test_workflow_studio.py` (56 after P1), runner `tools/workflow_studio/run_suite.py`. P1 found a usable local test database — see `WF2_P1_REPORT.md` for how it was run.

## 3. Design

### 3.1 The contract

Extend the existing duck-typed hook. `Model._workflow_capabilities()` (an `@api.model` method) returns a dict; every key optional:

```python
{
  'label': _('Expense claim'),            # singular, as users say it
  'area': _('Expenses'),                  # owner name shown on locked stages
  'stage_field': 'state',
  'stages': [                             # in real order; exits last
      {'key': 'draft', 'name': _('Draft'), 'enters': _('The employee starts a claim')},
      {'key': 'submitted', 'name': _('Waiting approval'), 'enters': _('The employee sends the claim'), 'approval': True},
      {'key': 'approved', 'name': _('Approved'), 'enters': _('The last approver says yes')},
      {'key': 'paid', 'name': _('Paid'), 'enters': _('Every line of the claim has been paid')},
      {'key': 'refused', 'name': _('Refused'), 'exit': True, 'enters': _('An approver says no')},
  ],
  'effects': [                            # what the AREA itself already does
      # {'stage': key or None, 'kind': 'message'|'todo'|'record'|'reminder'|'change',
      #  'audience': 'approver'|'requester'|'manager'|'team'|'candidate'|'other',
      #  'text': _('…plain sentence…'), 'owner': _('Time off'),
      #  'settings': {'action': '<xmlid>', 'lens': ''}  # optional, where it is configured}
  ],
  'actions': {key: {'label': …, 'owner': …, 'params': [{'key','label','type':'choice','options':[…]}]}},
  'owners': [...],                        # as today
  'screen': 'pb_expenses_hub',            # client action tag; used in P4
}
```

Companion instance methods, also optional:

- `_workflow_subject()` → `{'employee': hr.employee recordset or empty, 'user': res.users or empty, 'manager_user': res.users or empty}` using the module's **own** manager rule (Expense: expense manager first; Leave: leave manager first).
- `_workflow_stage_options(record=None)` for models whose stages are rows (Hiring): returns the `stages` list computed for that record/company (job-scoped, with `family`, `renamable`, `revision`), replacing the Hiring branch in `_record_stages`.
- `_workflow_effects(company)` for effects that depend on configuration (Hiring: active automation rules and switched-on built-ins, each as an effect with `stage` = the stage key for `stage_entered` rules or `None` with the event named in `text`).
- `_workflow_execute(key, params)` as today.

Implement in the three modules, **add-only**:

- `pb.expense.claim`: stages as above; effects: none of its own except "Lines are marked approved" (kind `change`, stage approved) and "Lines go back to the employee" on refuse/return; no actions; subject.
- `hr.leave` (in `pb_timeoff`): stages To approve / Second approval / Approved, exits Refused, Cancelled (use the labels the product shows); effects from inventory 1.2: to-do to the leave manager on create (`todo`, approver), message to the employee on approve and on refuse (`message`, requester), balance reduced on approve (`change`), backdated alert to HR lead (`message`, other; only when the type has it on — say so in the text), carry-forward warnings (`reminder`); subject.
- `hr.applicant` (in `pb_hiring`): `stage_field` `stage_id`, `_workflow_stage_options`, `_workflow_effects` from rules and built-ins, action `hiring.stage` (params: stage choice excluding the keys Studio excludes today) executed through `pb.hiring.act('journey_stage', …)`, rename exposed as `_workflow_rename_stage(stage_id, name, revision)` wrapping `pb.hiring.act('stage_rename')` with the same lock/revision check now in `rename_record_stage`; subject = recruiter as `user`, hiring manager as `manager_user`, no employee.

Studio side (`pb_lifecycle`): new file `models/workflow_contract.py` extending `pb.workflow.studio`:

- `_contract(model, record=None)` → normalised dict: module contract when present, else a fallback built from `_record_stages` (all values `kind` normal, no `enters`, `area` = model description). Always includes `source: 'declared' | 'discovered'`.
- Remove the Hiring special cases listed in §2 from Studio and route them through the contract. Keep the generic `_ownership` prefix table as fallback for models with no `owners` in a contract.
- `_resolve_owner` kind `manager` uses `_workflow_subject()['manager_user']` when the model declares it, else today's logic. New owner kind `subject` ("The person this is about") → `_workflow_subject()['user']`; validation: only offered when the model declares a subject. If the subject has no internal login the step fails with "… has no staff login yet, so this task cannot be given to them." (P4 lifts this.)
- `_capture` (system-triggered starts): when the triggering uid is the system account, set the event's initiator to the subject's user if the model declares one and it resolves; otherwise keep today's behaviour.

### 3.2 "Already happens" and double-ups

`existing_behaviour(model, workflow_id=None)` (designer permission) returns a list of effects, each with `stage` (contract key or `None` = not tied to a stage), `kind`, `audience`, `text`, `owner`, `settings`, `source` ∈ `area` | `approvals` | `rules` | `workflow`:

- **area**: contract `effects` + `_workflow_effects(company)`.
- **approvals** (generic, for any model with a connected approval process): one effect at the stage flagged `approval: True` (or the shim's submit state from `_chain_spec()` as `_record_stages` already derives) describing the live route in words when `resolve_binding` finds one ("Manager checks, then Finance" — build the sentence from the route's steps; keep it short), `settings` → the Approval Matrix action; plus the engine's messages as effects: next approver is told (`message`, approver), requester told when approved / sent back / refused (`message`, requester), late reminder and escalation (`reminder`, approver). When no route is bound, return one effect "No approval route is set up for this yet" with the same settings link — do not describe the legacy ladder.
- **rules**: active `base.automation` on the model **excluding rules generated by Studio** (fixes G8).
- **workflow**: other enabled Studio workflows on the same model: for each, its email/notify-type and task steps as effects, `stage` from that step's section binding (§3.3) when it has one.

Double-up check in `_validate` (publish and review), as **warnings**, not errors — new issue field `severity: 'warning'`, code `repeats_existing`, with `id` = the node and text naming the existing effect in plain words ("Time off already tells the employee when leave is approved. This step would tell them again."):

- an `email` step in a section bound to stage S when an existing effect has `kind` message at S (compare audience when the step's recipient can be classified; otherwise any message at S);
- a `task` step at S when an existing `todo` effect at S targets the same audience (approver/manager);
- a `matrix` step in `submit` mode on a model whose area already submits on its own (Leave auto-submits; declare with contract key `'submits_itself': True`).

A warning does not block publishing if the node carries `ack_repeat: true` (the designer's deliberate "keep it"); without it, publishing is refused with the warning text. The existing `purpose` requirement on email steps stays. Replace the whole-graph "this template is already sent by another step" error with: same template twice **on the same path** is an error; on mutually exclusive branches it is allowed.

### 3.3 Stage layer

New models (in `workflow_models.py` or a new `workflow_stage.py`), both inheriting `pb.workflow.protected` (writes only through the facade):

`pb.workflow.stage`
- `company_id` (required), `source_model` (Char, the business model; empty for a new-process workflow), `workflow_id` (Many2one, set only for new-process stages, cascade), `name` (required, ≤ 40), `sequence`, `anchor_value` (Char: the module stage key this stage sits after and counts as; empty for new-process), `enter` (`auto` | `person` | `rule`), `enter_owner` (Json, same shape as a task owner), `enter_rule` (Json condition tree, validated with the existing condition validator), `target_hours` (Integer, 0 = none), `active`.
- Unique name per (company, source_model, workflow_id).

`pb.workflow.record.stage` (current position, one row per record)
- `company_id`, `res_model`, `res_id` (unique together), `stage_id` (→ `pb.workflow.stage`, restrict), `entered_at`, `entered_by` (res.users), `run_id`.
- History: append a `pb.workflow.log` row on every enter/leave ("Moved to Payment scheduled by …").

Invariant: a position row is valid only while the record's module status equals the stage's `anchor_value`. Enforce lazily in one helper `_record_position(model, res_id)` that deletes a stale row (system env, logged) and returns the valid stage or nothing; call it wherever position is read and once per worker pass for runs waiting at a gate.

Security: ACL read for `base.group_user` on both (needed to show a record's stage), no direct write/create/unlink for anyone but system; company record rules on both; `record.stage` read additionally guarded by source-record access the same way runs are (`_check_access` in the protected mixin).

Facade (designer permission unless stated; all company-scoped; plain-English errors):

- `stage_catalogue(model, workflow_id=None, record_id=None)` → merged ordered list for the Stages screen: contract stages (`kind: 'core'`, `locked: True`, `area`, `enters`, `exit`, `renamable`) with each user-made stage inserted after its anchor in `sequence` order (`kind: 'yours'`, `counts_as` = anchor name, `enters` sentence built from `enter`: "By itself, when the steps before are finished" / "<owner> presses Move to <name>" / the rule in words), plus counts of records currently in each user-made stage.
- `stage_create(model, workflow_id, values)`, `stage_update(stage_id, values)`, `stage_reorder(model, workflow_id, ordered_ids)` (a stage may move to another anchor only while no record is in it), `stage_delete(stage_id)` → archive; refused with a clear sentence while records are in it or an enabled workflow's published version binds a section to it.
- `stage_rename_shared(model, stage_key, name, revision)` → the module's `_workflow_rename_stage` when declared (replaces `rename_record_stage`; keep the old method name as a thin alias so the shipped UI keeps working).
- `move_record_stage(model, record_id, stage_id)` (any internal user): allowed when the stage's `enter` is `person`, the caller resolves as its `enter_owner` (reuse `_resolve_owner`) **or** is a Designer, the caller can read the record, and the record's module status equals the anchor. Writes the position, logs, and advances any run waiting at that gate.
- `record_stage(model, record_id)` → `{track: [...merged stages with state done|here|later…], current: {...}, approval_at: key}` for display. "done" only for stages before the current one in the merged order and never for exits; exits are returned separately as `exits`. No invented history.

Definition schema (still `payobook.workflow/1`): each `stages[i]` may carry `bind`:

- absent → heading only (today's Section; unchanged behaviour);
- `{'kind': 'core', 'value': '<module stage key>'}`;
- `{'kind': 'yours', 'id': <pb.workflow.stage id>}`.

Validation: bound values must exist in the catalogue for the workflow's model; bound sections must appear in catalogue order (a heading may sit anywhere); an exit stage cannot be bound; at most one section per bound stage. `D.fresh` unchanged (three headings).

### 3.4 Gates at run time

In `_advance`, before visiting the first not-yet-done main-path node of a section whose `bind` is set, evaluate that section's gate (source-model runs only; system env; explicit company):

- `core`: satisfied when the record's status is that value **or a later non-exit stage** in contract order. If the record is in an exit stage → close the run: cancel open activities, run state `cancelled`, log "Stopped: the record is now <exit name>." Otherwise the run waits; progress reason "Waiting for this to reach <stage name>."
- `yours`: first the anchor must be satisfied exactly as a `core` gate. Then by `enter`: `auto` → write the position now; `rule` → wait until the rule matches (same interpreter and live values as waits), then write the position; `person` → wait until `move_record_stage` is called. Progress reason names who can move it.
- Leaving a user-made stage needs nothing special: the next bound section's gate, or the module status moving on (which invalidates the row), handles it.
- New-process runs: `core` does not exist; `yours` stages apply to the run itself (`res_model='pb.workflow.run'`), anchor checks skipped.
- Store nothing new on the step table for gates; compute each pass. Keep one `gate` Json on the run (`{'section': i, 'reason': …}`) only if you need it for `progress()`; if you add a stored field say so in the report (it is allowed in this phase).
- G6 applies: a gate that raises must not log every minute.

`progress()` and `record_runs()` gain `record_stage` (from §3.3) alongside the existing `record_stages` key, which stays for the shipped UI.

### 3.5 Carry-overs

- G8 as in §3.2.
- Activation of a new process: a route that exists but is paused also blocks, with "The approval route for this is paused. Switch it back on in Approval Matrix first."

### 3.6 Sudima (D9)

`sudima` is a live client database with `pb_lifecycle` at 19.0.1.6.0. In this phase's deploy: back it up, compare every installed custom module's `latest_version` with its manifest, and upgrade the ones that are behind (list them in the report). Snapshot its active job ids before and after (expected 80) and disable any that the upgrade newly switches on. Its mail servers are off; leave them off. If any upgrade fails, restore nothing blindly: stop, keep the backup, report.

### 3.7 Workbench (minimum to stay correct)

- `metadata` keeps returning `record_stages`; add `contract` (stages, area, label, has_subject) and `stage_catalogue`.
- Module-action inspector: render `params` from the contract instead of the hard-coded Hiring stage select; "Who does this?" gains "The person this is about" when the model declares a subject.
- Review page: show `severity: 'warning'` issues with a "Keep it, it is different" control that sets `ack_repeat` on that node; errors unchanged.
- Nothing else. Bump the iframe `v=` value.

## 4. Safety rails

- New tables and access rules → **risky tier**: `pg_dump -Fc` of all five databases first; keep tars of the four module trees; upgrade all five in one window (a new stored model must reach every database that loads the code). Order of `-u`: the three area modules and `pb_lifecycle` together per database.
- Pre-deploy read-only numbers per database: enabled workflows, running/waiting runs. If any run is live, stop and report.
- Never publish, activate, start or cancel a real workflow; never move a real record's stage; never send mail. Tests roll back.
- If you find another existing feature that already does something this handover asks you to build, do not build it: record it under "Overlaps found" (R2a).

## 5. Test cases

- T1 Expense, Leave and Hiring contracts load; each stage has a name and an `enters` sentence; exits flagged; no user-visible string contains a model or field name (assert on a small banned-word list incl. "Odoo").
- T2 A model with no contract still returns a discovered contract and all 56 existing tests pass.
- T3 Hiring stage move through the contract action works as the system, refuses Joined, and fires Hiring's own stage-entered dispatch exactly once.
- T4 Shared Hiring stage rename through `stage_rename_shared` keeps the lock, revision and permission checks (port the existing test).
- T5 `existing_behaviour` for Leave lists the stock to-do, the two employee messages and the balance change at the right stages; for Expense with a bound route lists the route sentence and the engine messages; with no route says none is set up.
- T6 `existing_behaviour` for Hiring lists an active stage-entered rule at its stage and stops listing it when the rule is switched off.
- T7 Studio-generated automation rules no longer appear as "existing automation" (G8).
- T8 Email step in a section bound to Leave "Approved" → `repeats_existing` warning; publish refused; with `ack_repeat` it publishes. Same template on two exclusive branches is accepted; twice on one path is an error.
- T9 Stage create / update / reorder / delete; delete refused while a record is in it and while an enabled workflow binds it; Designer-only; company-isolated (second company cannot read or use it).
- T10 Binding validation: unknown stage, exit stage, out-of-order bindings, duplicate binding are refused by code; headings anywhere are fine.
- T11 Core gate: run waits while the claim is Draft, proceeds when it becomes Waiting approval, proceeds immediately if the claim is already Approved, and is closed with the plain reason if the claim becomes Refused.
- T12 User-made stage, `auto`: position written when reached and the claim's status equals the anchor; the claim's own status field is never written by any workflow code (extend P1's static guard to the new files).
- T13 User-made stage, `person`: wrong person refused, right person moves it, run continues; a Designer may also move it; nobody can move it while the status differs from the anchor.
- T14 User-made stage, `rule`: waits until the rule is true.
- T15 Invariant: when the claim's status moves on, the position row is removed and `record_stage` shows the module status.
- T16 `record_stage` track: done/here/later correct, exits separate, never marks a skipped stage done.
- T17 Owner kind `subject` and contract manager: Expense uses the expense manager first; subject without a staff login fails with the plain sentence.
- T18 Date-triggered start records the subject's user as initiator when available.
- T19 New-process workflow with two user-made stages (`auto`, then `person`) runs through with positions on the run.
- T20 Activation blocked by a paused route.

## 6. Deploy and verify

1. Local suite first (see P1 report for the local database).
2. Versions: `pb_lifecycle` → `19.0.1.11.0`; bump `pb_me_expense`, `pb_timeoff`, `pb_hiring` patch versions. Bump iframe `v=`.
3. Commits with explicit paths: one for the contract in the three area modules, one for Studio, one for docs. Do not push.
4. Deploy per ledger §3 (G9: flock read-only; run `-u` with `--no-http --max-cron-threads=0`), databases `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`. Run the suite on `p0clone` with the service stopped. Asset signal + purge, start, warm each site with one curl.
5. Verify: tree hashes of the four modules identical both sides; `latest_version` in all five; active job counts unchanged per database (P1: 49 / 31 / 38 / 81; sudima 80); logs clean; workbench and the Hiring, Time off and Expenses hubs return 200.
6. Local browser pass on the three workbench touches in §3.7, console clean.

## 7. Report back (`docs/handovers/workflow2/WF2_P2_REPORT.md`)

Commits and versions; T1–T20 results and the full-suite count; pre-deploy live numbers; deploy evidence per database including the sudima module list; deviations with reasons; **Overlaps found**; the exact JSON shape returned by `metadata.contract`, `stage_catalogue`, `existing_behaviour` and `record_stage` (P3 builds on them — include one real example each for Expense); self-review against R1, R2, R2a, R3, R4, R7, R8; new gotchas added to the ledger.
