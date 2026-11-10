# WORKFLOW-2 · Phase 1 handover — backend unblock

Read first: `docs/handovers/workflow2/WF2_LEDGER.md` (rulings R1–R9, conventions, gotchas). Background: `docs/design/workflow-studio/review/SECOND_OPINION_REVIEW.md` findings F1, F2, F4, F5, F9, F11, F14 and the "Correction to the execution-identity ruling" block at the end.

## 1. Scope

Six changes in `pb_lifecycle`, mostly Python, two small workbench edits. No new screens, no new models, **no new or removed stored fields**.

1. **System-level execution** (R3, F9).
2. **Approval step no longer forced, and follows by default** (F1, R2).
3. **Several automatic workflows per record type** (F2).
4. **One timing rule for path decisions** (F11).
5. **Validation error codes** (F5, G2).
6. **Healthy branches keep moving when a sibling step failed** (F4, part) and **new-process approval must have a route before activation** (F14).

### Binding non-goals

- No stage layer, no module contract, no new step types, no By stage view (later phases).
- Do not touch `pb.journey.*`, `biz_approval_workflow`, `pb_approval_config`, `pb_hiring`, `pb_me_expense` or any other module. If a fix seems to need it, stop and report.
- Do not drop or rename the `execution_user_id` columns (stop using them; a later phase removes them).
- Do not translate strings in this phase.
- Do not change the workbench's look. R1: nothing shipped is removed.
- R7: no "Odoo"/"OdooBot" in any user-visible string. R8: plain English in every new message.

## 2. Verified plumbing (do not re-derive)

Paths are under `pb_lifecycle/`.

- Execution identity today: `models/workflow_models.py:264-269` `WorkflowRun._service()` returns the facade `with_user(self.execution_user_id)`; `:271-272` `_source()`; `:189-223` `WorkflowEvent._process()` builds the same thing from `self.execution_user_id` and raises when that user is inactive. `models/workflow_studio.py:191-194` sets `execution_user_id=self.env.uid` on create; `:340-347` lets a publisher change it; `:379-383` copies it to the version; `:475-479` to the event; `:202` returns it to the UI.
- Facade checks that rely on the caller's identity: `_staff` `:27-29`, `_source` `:59-68` (`check_access('read')`, company must equal `self.env.company`), `_source_fields` `:70-84` (`fields_get`, `has_access`), `_mail_template` `:521-530`, `_execute_action` `:532-546`.
- Step execution: `models/workflow_models.py:498-574` `WorkflowStep._execute`. Task owner read check at `:512-513` (`service.with_user(user)._source(...)`) — **keep**. Matrix branch `:541-562`: adopts `source.approval_request_id` when state in `pending/blocked/approved`, otherwise `engine.submit(...)`. Email `:563-571`. Action `:572-574`.
- Approval requirement: `models/workflow_studio.py:245-248` passes `approval=bool(native_processes and not after)`; `models/workflow_definition.py:416-417` raises "Use the existing Approval Matrix for this process."; `workflow_studio.py:254-255` requires `process_id` whenever the model has a connected process.
- Coexistence: `workflow_studio.py:401-412` in `activate`.
- Path timing: `workflow_models.py:347` — live values only if any path has grouped rules, else the start snapshot (`_values()` `:283-291` vs `_condition_values()` `:293-304`).
- Draft guard by text fragments: `workflow_studio.py:320-324`. Messages are produced by the inner `error(node, text)` at `workflow_definition.py:238-239` and by `form_errors` `:131-170`.
- Worker: `workflow_studio.py:724-779` `_cron_workflows`; run scan at `:740` takes only `running`/`waiting`. `_advance` (`workflow_models.py:306-395`) already tolerates a failed step and recomputes run state at `:392`.
- Polling of approval state for a waiting matrix step: `workflow_studio.py:762-774`.
- Engine API *(surveyed, confirm by reading)*: `biz_approval_workflow/models/engine.py:842` `submit(record, res_id=None, idempotency_key=None)` checks the caller's write access; `:57`/`:155` `_resolve_binding` / `resolve_binding(company_id, process_key, scope_keys=None, …)`; `:122-129` raises when nothing is bound. Request states: `draft, pending, approved, applied, returned, rejected, cancelled, blocked` (`request.py:14-21`).
- Workbench: settings dialog with the "Runs with this person's permissions" control at `static/workflow/actions.js:41-42`; matrix inspector at `static/workflow/app.js:31`; iframe cache key `static/src/js/workflow_studio.js:18` (`v: "record-stages-2"`).
- Tests: `tests/test_workflow_studio.py` (42 tests). Affected by this phase at least: `test_native_approval_cannot_be_omitted` (:226), `test_no_approval_route_reuses_native_fast_path` (:264), `test_new_conditions_read_live_old_branches_keep_snapshot` (:365), `test_start_requires_explicit_grant` (:182), anything asserting on execution user.

## 3. Design

### 3.1 System-level execution

- Add one helper in `workflow_models.py`, e.g. `def system(env, company): return env(user=SUPERUSER_ID, su=True, context=dict(env.context, allowed_company_ids=[company.id], _pb_workflow_internal=INTERNAL))`. Use the **superuser environment**, not `sudo()` (ledger G1).
- `_service()` returns the facade on that environment with `_pb_workflow_origin=self.workflow_id.id`. `WorkflowEvent._process` uses the same helper; delete the "execution user no longer has access" checks.
- Stop reading `execution_user_id` everywhere. Keep writing a value on create (the fields are `required=True`): write the creating user as today, purely to satisfy the column. `save_draft` keeps accepting the `execution_user_id` argument but ignores it. `get_workflow` stops returning it.
- Workbench: remove the "Runs with this person's permissions" control from the settings dialog and its save path (`actions.js:41-42`). Keep name and "who can start".
- **Because record rules no longer apply inside the worker, every search made from the worker side must carry an explicit company term.** Audit `_cron_workflows`, `_enqueue`, `_capture`, `_process`, `_advance`, `_execute`, `_resolve_owner`, `_condition_values`, `_facts`. `_source` already compares `rec.company_id` to `self.env.company`; confirm `self.env.company` is the workflow's company under the helper.
- Participant- and designer-facing methods (`bootstrap`, `tasks`, `task_detail`, `answer`, `upload`, `progress`, `submission`, `record_runs`, `run_action`, every design method) keep running as the signed-in user. Do not move them to the system environment.
- Design-time protection stays as it is: `_models`, `_source_fields`, `_mail_template`, `metadata` run as the designer, so a designer still only picks what they can read. `_validate` at publish runs as the publisher. Add nothing here; add tests (T3).
- Keep `:512-513`: an assignee must be able to read the source record; assignment never grants access.
- `_execute_action` under the system environment: the `source.check_access('write')` line becomes a no-op; keep the `key in self._actions(...)` guard. Hiring's facade is then called as the system. Read `pb_hiring`'s `_act_journey_stage` guard path only far enough to confirm it does not refuse the system user; if it does, report rather than patch Hiring.
- History: `_log` uses `self.env.uid` (`:258-262`) — under the helper that is the system account. Where a human caused the step (an `answer`, a `run_action`), keep logging that human: those callers already log from their own environment. Check the system account's display name in the four databases is not a framework brand name; if it is, report it (do not rename it in this phase).

### 3.2 Approval step

- Validation: stop requiring a matrix node. Remove the `approval=` requirement path (`workflow_definition.py:416-417` and its argument) and the unconditional process requirement at `workflow_studio.py:254-255` → require `process_id` only when the definition contains a matrix node or the trigger is `approval_applied`. Keep: at most one matrix node, on the main path, forms before it, no `when` on it, not allowed together with `approval_applied`.
- New node key on matrix nodes: `mode` ∈ `follow` | `submit`.
  - `follow`: never calls `engine.submit`. If the record has a request in `pending/blocked/approved` → adopt it and wait (as today). If its most recent request is `applied` → finish. Otherwise set the step `waiting` with no `approval_id`; the worker re-checks each pass and adopts a request when one appears. Progress reason: "Waiting for this record to be sent for approval."
  - `submit`: today's behaviour, but submit **as the run's initiator**, not as the system: `engine.with_user(run.initiator_id)` plus the internal context. If the initiator is not an active internal user of the company, fail the step with "Nobody is recorded as having started this, so there is no one to send it for approval. Send it from the record instead."
  - Missing `mode`: for a new-process run (`not run.source_model`) → `submit` (unchanged behaviour, submitter is already forced to the initiator by `_approval_context`). For a source-model run → `submit`, so already-published versions behave as before.
  - `D.validate`: `mode`, when present, must be one of the two values.
- Worker (`:762-774`): handle a waiting matrix step with no `approval_id` in `follow` mode (look up the record's current request, company-scoped, adopt or finish as above). Rejected/cancelled/returned handling unchanged.
- Workbench: new matrix nodes on a source-model workflow get `mode: 'follow'`. In the matrix inspector (`app.js:31`), when `S.w.source_model`, add one select "What should this step do?" → "Wait for the approval this record already goes through" (`follow`) / "Send it for approval for the person who started this" (`submit`). No other UI change.
- R2 guard, as a test not a feature: nothing in `pb_lifecycle/models/workflow_*.py` writes a source record's status field (T6).

### 3.3 Coexistence

Replace the peer rule in `activate`:

- Refuse only an **exact duplicate**: another enabled workflow on the same company + model whose published `trigger` and `scope` are equal (compare canonical JSON). Message: "Another active workflow starts on exactly the same records and event. Change the filters or pause the other one."
- Any other enabled workflow with the same trigger kind on the model is allowed but needs `acknowledge_existing=True`, same as the existing automation acknowledgement. Without it raise: "Other workflows also start for these records. Review them and confirm this one does different work."
- `review()` already returns `other_workflows`; add each one's trigger kind and a short plain scope summary so the Review page can show them (the Review page renders `r.other_workflows` names today; extend the text only).
- The workbench Review checkbox `#ack-automation` is shown only when `r.automations.length`; show it also when `r.other_workflows.length`, with the label "I checked these; this workflow adds different work."

### 3.4 Path timing

- New top-level definition key `timing: 'live'`. `D.fresh` sets it; `save_draft` sets it on every save; `D.validate` accepts absent or `'live'`.
- `_advance` path choice: live values when `d.get('timing') == 'live'` **or** any path has grouped rules (today's test); otherwise the snapshot. Published versions without the key keep their behaviour.

### 3.5 Error codes

- Every issue from `D.validate` and from the facade `_validate` gains a stable `code` (snake_case, e.g. `section_order`, `step_missing_reference`, `one_path_only`, `self_nesting`, `bad_schema`, `too_large`). Text stays.
- `save_draft` blocks on a set of **codes** covering every structural error (everything the old fragment list intended, plus `section_order`, `bad_path_group`, `shared_identifier`, `group_section_mismatch`, `bad_saved_group`). Unfinished-but-valid drafts must still save.
- The workbench reads `i.text` and `i.id` only; do not change that.

### 3.6 Worker

- Run scan: also take runs in `failed` that still have a step in `waiting` (company term explicit). Order and limit unchanged.
- Activation of a workflow with `source_model == ''` and a matrix node: resolve the binding for its process through the engine's own resolver; if nothing is bound raise "Set up who approves this in Approval Matrix before turning it on." Read `engine.py:57-160` and use the public resolver; do not reimplement resolution.

## 4. Safety rails

- No stored-field change, so a plain `-u pb_lifecycle` is enough; but this phase changes execution rights, so treat the deploy as **risky tier**: `pg_dump -Fc` of all four databases to `/odoo/backups/` first, and keep a tar of the server's current `pb_lifecycle` tree for rollback.
- Before deploying, read-only check on each database: how many workflows are `enabled`, how many runs are `running/waiting`, how many of those have a matrix step on a source model. Report the numbers. If any live run would change behaviour, stop and report.
- Never activate, publish, start or cancel a real workflow. Never send mail. Tests roll back.

## 5. Test cases (add to `tests/test_workflow_studio.py`; update the existing tests this phase deliberately changes and say which)

- T1 A run keeps advancing after its creator and publisher are deactivated.
- T2 Under system execution, a run of company A never reads or advances a record, run, event or approval request of company B (two-company fixture).
- T3 A designer without read access to a model cannot create a workflow on it; a field hidden from the designer by groups is not offered and is rejected in a rule.
- T4 Task assignment to a person who cannot read the source record fails the step with the existing message (unchanged).
- T5 Workflow on an approval-capable model with **no** matrix node validates, publishes, activates and runs.
- T6 Static guard: grep-style test that no `workflow_*.py` writes `state`/`stage_id` on a source record outside `_execute_action` → registered module operation.
- T7 `follow`: no request yet → step waits, `engine.submit` not called; request appears → adopted; request applied → step done.
- T8 `follow` on a record whose latest request is already applied → step done immediately, no new request.
- T9 `submit` with an inactive or system initiator → step fails with the plain message; with a valid initiator → request's submitter is the initiator.
- T10 Version published before this phase (no `mode`) on a source model still submits.
- T11 Two automatic workflows, same trigger kind, different scope: both activate with acknowledgement, each fires only for its records; exact duplicate refused.
- T12 `timing: 'live'`: a flat rule and the same rule grouped take the same path after the record changes mid-run; a version without the key keeps the snapshot.
- T13 Out-of-section-order draft is refused by code; an unfinished draft (form with no fields, email with no template) still saves.
- T14 Parallel paths: one step failed, a sibling timed wait still completes on the next worker pass.
- T15 New process with a matrix node and no bound route cannot be activated; with a route it can.
- All 42 existing tests pass, apart from those intentionally rewritten.

## 6. Deploy and verify

1. Local first: check whether a local test database with these modules exists (`/Users/adity/odoo19/odoo`, `psql -l`); spend at most five minutes. If yes, run the suite there before touching the server.
2. Bump `pb_lifecycle/__manifest__.py` to `19.0.1.10.0`; bump the iframe `v=` value.
3. Commit (explicit paths), then deploy per ledger §3 and the repo `CLAUDE.md`: clean staging dir, `git archive HEAD pb_lifecycle`, per-module scoped rsync, stop, backups, `-u pb_lifecycle` on `payobook`, `payobook_template`, `p0clone`, `rize` one at a time (stop at first failure), then with the service still stopped run the suite on `p0clone` through `odoo-bin shell < tools/workflow_studio/run_suite.py`, then asset signal + purge, start, warm.
4. If the suite fails on the server: restore the saved module tree, `-u` again on all four, start, report. Do not leave the server on failing code.
5. Verify: module tree hash identical on both sides (skip `__pycache__`, `*.pyc`, `.DS_Store`); `latest_version` `19.0.1.10.0` in all four databases; active cron counts unchanged per database; log clean of new tracebacks; the workbench opens on payobook.com (HTTP 200 for `/pb_lifecycle/static/workflow/index.html`).

## 7. Report back (`docs/handovers/workflow2/WF2_P1_REPORT.md`)

- Commits, files changed, manifest version.
- Test output: counts, and each of T1–T15 with pass/fail. Which existing tests were rewritten and why.
- The pre-deploy live numbers from §4.
- Deploy evidence: notes-file lines, hashes, versions per database, cron counts before/after, downtime.
- Deviations from this handover with the reason.
- What the Hiring facade does when called as the system (§3.1), and the system account's display name per database.
- Self-review against R1, R2, R3, R7, R8.
- New gotchas (also add them to the ledger §4).
