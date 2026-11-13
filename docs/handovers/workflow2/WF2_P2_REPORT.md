# WORKFLOW-2 · Phase 2 report — module contract, "already happens", user-made stages

Builder: Claude (Opus implementation agent), 11 November 2026. Handover: `WF2_P2_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (gotchas G11–G16 added, P2 row closed).

## 1. Commits and versions

| Commit | What |
|---|---|
| `a5422594d` | Let Expenses, Time off and Hiring describe their records to Workflow Studio (the three area modules, add-only) |
| `f24786073` | Show what already happens, warn before a repeat, and let users add their own stages (`pb_lifecycle`, code + tests + workbench) |
| (docs commit) | This report and the ledger |

Not pushed. Versions: `pb_lifecycle` **19.0.1.11.0**, `pb_me_expense` **19.0.1.0.3**, `pb_timeoff` **19.0.1.8.2**, `pb_hiring` **19.0.2.23.3**. Workbench cache keys: iframe `v=wf2-p2` (`static/src/js/workflow_studio.js:18`) **and** every script/style tag in `static/workflow/index.html` (`?v=wf2-p2`; P1 had left these on `record-stages-2`, ledger G11).

Files:

- Area modules (new file each + `models/__init__.py` import + manifest bump; nothing existing changed): `pb_me_expense/models/workflow_contract.py`, `pb_timeoff/models/workflow_contract.py`, `pb_hiring/models/workflow_contract.py`.
- `pb_lifecycle/models/workflow_contract.py` (new): `_contract`, `existing_behaviour`, `_existing`, approval effects from the engine, binding validation, per-path template rule, `repeats_existing` warnings, `metadata` gains `contract` + `stage_catalogue`.
- `pb_lifecycle/models/workflow_stage.py` (new): models `pb.workflow.stage`, `pb.workflow.record.stage`; facade `stage_catalogue`, `stage_create`, `stage_update`, `stage_reorder`, `stage_delete`, `stage_rename_shared`, `move_record_stage`, `record_stage`; `_record_position`, `_set_position`, `_occupants`, run gate `_gate`.
- `workflow_models.py`: run field `gate` (Json), history field `stage_id`, section gates in `_advance`.
- `workflow_studio.py`: `_declared`; `_actions` / `_ownership` / `_execute_action` read the contract (Hiring special cases removed); generic action-parameter validation; `_studio_rules` (G8); `_blocking`; paused route blocks activation; `_capture_initiator`; `_rule_words` split out of `_scope_summary`; `review` returns `blocking`; owner kind `subject` validated.
- `workflow_progress.py`: `_resolve_owner_on` (owner rules without a run), `subject`, area manager rule; `record_runs` and `progress` gain `record_stage` (and `progress` a `gate` reason).
- `workflow_record_context.py`: Hiring branch of `_record_stages` replaced by the module's `_workflow_stage_options`; `rename_record_stage` is now an alias of `stage_rename_shared`.
- `workflow_definition.py`: owner kind `subject` accepted.
- Security: read-only ACL for `base.group_user` on both new models; company rules on both; position reads also need read access to the record (`_check_access`).
- Workbench: `app.js` (module-action parameters from the contract, "The person this is about", Review warnings with "Keep it, it is different" / "Undo", publish enabled by `blocking`), `actions.js` (`ack-repeat`), `index.html`, `static/src/js/workflow_studio.js`.
- Tests: `tests/test_workflow_studio.py` T1–T20.

## 2. Tests

Local database `am_wf2p2` (clone of P1's `am_wf2`, plus `pb_me_expense` installed, then `-u` of the four modules) and on the server on `p0clone` with the service stopped (`odoo-bin shell < tools/workflow_studio/run_suite.py`, rolled back):

```
Ran 76 tests … OK
WORKFLOW_TEST_RESULT={"tests": 76, "successful": true, "failures": 0, "errors": 0}
```

Locally 0 skips (Expenses, Time off and Hiring are all installed). Server, `p0clone`, service stopped: **76/76**, 0 failures, 0 errors (§4).

| # | Test | Result |
|---|---|---|
| T1 | `test_wf2p2_t1_contracts_load_in_plain_words` — three contracts load as `declared`; every stage has a name and an "enters" sentence; exits flagged and last; banned-word check (`odoo`, `hr.`, `pb.`, `res.`, `*_id`, `state`, `model`) over labels, stages, area/approval effects, action labels and errors | pass |
| T2 | `test_wf2p2_t2_record_type_without_contract_is_discovered` — "Other request" discovered from its form; partner discovered with no stages; catalogue all locked core; plus all 56 existing tests | pass |
| T3 | `test_wf2p2_t3_hiring_move_through_the_contract` — run as the system moves the candidate to Shortlist through `journey_stage`; Hiring's rule dispatcher fires "enters a stage" exactly once; Joined refused by validation (`bad_hiring_stage`) and by `_workflow_execute`; choices come from the contract | pass |
| T4 | `test_wf2p2_t4_shared_stage_rename_keeps_lock_revision_and_permission` — ported; Hiring write permission, stale copy refused, Studio permission, a module without rename refused | pass |
| T5 | `test_wf2p2_t5_existing_behaviour_for_leave_and_expense` — Leave: to-do at To Approve, employee messages at Approved / Refused, balance change at Approved; Expense with a bound route: route sentence (route name + approver), engine messages to approver and requester at the right stages; no route: "No approval route is set up for this yet." | pass |
| T6 | `test_wf2p2_t6_hiring_rules_are_listed_while_switched_on` | pass |
| T7 | `test_wf2p2_t7_studio_rules_are_not_existing_automation` (G8: review, metadata and existing_behaviour) | pass |
| T8 | `test_wf2p2_t8_repeat_warning_and_same_path_templates` — email in a section bound to Leave "Approved" → `repeats_existing` warning naming Time off; `blocking` 1; publish refused; with `ack_repeat` it publishes; same template on exclusive branches accepted, twice on one path or on two parallel paths → `duplicate_email` | pass |
| T9 | `test_wf2p2_t9_user_made_stages_lifecycle_permission_and_company` — create/update/reorder (anchor moves while empty)/delete; exit anchor and duplicate name refused; non-designer refused; direct write refused; delete refused while a record is in it and while an enabled workflow waits on it; second company cannot update, list or read it | pass |
| T10 | `test_wf2p2_t10_section_bindings_are_checked_by_code` — `bind_unknown`, `bind_exit`, `bind_order`, `bind_duplicate`; headings anywhere fine; core binding on a new process refused | pass |
| T11 | `test_wf2p2_t11_core_gate_waits_proceeds_and_stops` — waits at Draft (reason logged once over three passes), proceeds at Waiting approval, proceeds at once when already Approved, closed with "Stopped: the record is now Refused." | pass |
| T12 | `test_wf2p2_t12_auto_stage_writes_only_its_own_position` + P1's static guard extended to the new Studio files and the three area contract files (status writes, `.write(` on a record, `_chain_*_write`, `_advance_state(`, `action_approve(`, `action_refuse(`) | pass |
| T13 | `test_wf2p2_t13_person_stage_right_person_designer_and_status` | pass |
| T14 | `test_wf2p2_t14_rule_stage_waits_until_the_rule_is_true` (and a rule with an unknown field is refused by the shared validator) | pass |
| T15 | `test_wf2p2_t15_position_is_dropped_when_the_status_moves_on` | pass |
| T16 | `test_wf2p2_t16_record_stage_track_never_invents_history` — entered stage `done`, never-entered stage `passed`, exits separate, refused claim → all `stopped` | pass |
| T17 | `test_wf2p2_t17_subject_owner_and_the_areas_own_manager` — expense approver first, line manager otherwise; subject without login fails with "WF2 T17 no login has no staff login yet, so this task cannot be given to them."; subject on a record type without a subject refused | pass |
| T18 | `test_wf2p2_t18_date_start_is_recorded_as_the_person_it_is_about` — system start → the employee's login; no login → stays the system; a person's own change → that person | pass |
| T19 | `test_wf2p2_t19_new_process_stages_live_on_the_run` | pass |
| T20 | `test_wf2p2_t20_paused_route_blocks_activation_of_a_new_process` | pass |

Local browser pass (local server on `am_wf2p2`, Chrome): Review on a Leave workflow shows the warning sentence, "Publish version" disabled; "Keep it, it is different" → "Kept on purpose" + "Undo", heading "The workflow is ready to publish", publish enabled. Hiring "Use a module action" inspector shows "Existing stage" from the contract (Joined absent, saved value kept). "Who does this?" lists "The person this is about" on Expense; the step card reads "The person this is about". The shipped Stages dialog still renames a Hiring stage (through the alias) and back. Console: no workbench errors (the only 500s were the local login page's logo and asset files on a cloned database without its file store). **Not done on payobook.com** — the QA login is held by the main loop (still owed, as in P1).

## 3. Pre-deploy live numbers (read-only, 10 Nov 23:4x UTC)

| DB | enabled workflows | workflows | runs running/waiting | runs failed | pending events | active jobs | versions before |
|---|---|---|---|---|---|---|---|
| payobook | 0 | 2 | 0 | 0 | 0 | 49 | lifecycle 1.10.0, expense 1.0.2, timeoff 1.8.1, hiring 2.23.2 |
| payobook_template | 0 | 0 | 0 | 0 | 0 | 31 | same |
| p0clone | 0 | 0 | 0 | 0 | 0 | 38 | same |
| rize | 0 | 0 | 0 | 0 | 0 | 81 | same |
| sudima | — (no Studio tables) | — | — | — | — | 80 | **lifecycle 1.6.0**, expense 1.0.2, timeoff 1.8.1, hiring 2.23.2 |

No live run anywhere, so the rail did not stop the deploy. Server trees of the four modules were byte-identical to the repo before these commits (nobody else's work overwritten). `sudima` custom-module scan (143 installed custom modules, manifest on disk vs `latest_version`): only `pb_lifecycle` was behind. Its mail servers: 0 active.

## 4. Deploy evidence

- Notes file: START `2026-11-10 23:44 UTC | WORKFLOW-2 P2 (Claude WORKFLOW-2) | START | …` and DONE `2026-11-10 23:51 UTC | … | DONE | … 394 seconds (329 s down) …`. No other session had a START in the last 12 hours (older unmatched STARTs are naming mismatches, ledger G14).
- Lock: `flock` on `/tmp/payobook-studio-deploy.lock` (read-only open, G9). Script: P1's, extended to four modules and five databases (copy in the evidence folder as `wf2p2_deploy.sh`).
- Backups (risky tier): `/odoo/backups/wf2-p2-20261110T234436Z/` — `payobook.dump` 69 MB, `rize.dump` 31 MB, `sudima.dump` 19 MB, `p0clone.dump` 18 MB, `payobook_template.dump` 17 MB (`pg_dump -Fc`), and the four module trees before deploy (`pb_lifecycle-before.tgz`, `pb_me_expense-before.tgz`, `pb_timeoff-before.tgz`, `pb_hiring-before.tgz`). Before deploy those four server trees hashed identical to the repo at `77dc0c4f4`.
- Steps: clean staging `/tmp/deployWF2P2` from `git archive HEAD` → service stopped (no `odoo-bin` left) → scoped `rsync -a --delete` per module → `-u pb_lifecycle,pb_me_expense,pb_timeoff,pb_hiring --no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize (all exit 0, no ERROR/CRITICAL in any upgrade log) → suite on p0clone **76/76** → `sudima` last (exit 0, no ERROR) → newly-active jobs switched off before start → probe on all five → `orm_signaling_assets` + asset purge on all five → service started.
- **sudima**: modules upgraded `pb_lifecycle` 19.0.1.6.0 → 19.0.1.11.0 (the only custom module behind; this created every Workflow Studio table there for the first time), plus `pb_me_expense` 1.0.2 → 1.0.3, `pb_timeoff` 1.8.1 → 1.8.2, `pb_hiring` 2.23.2 → 2.23.3 like the others. The upgrade created job 89 "Workflow Studio: progress active runs" switched on; it was **switched off** before the service started (D9). Mail servers untouched (0 active).
- Tree hashes (skip `__pycache__`, `*.pyc`, `.DS_Store`), server = repo HEAD: `pb_lifecycle` 4493d01c…2ee783, `pb_me_expense` 236a01a5…b9c158ae, `pb_timeoff` 6ef4fea4…1c21c6a, `pb_hiring` 1c20f062…3966209.
- `latest_version` in all five databases: pb_lifecycle 19.0.1.11.0, pb_me_expense 19.0.1.0.3, pb_timeoff 19.0.1.8.2, pb_hiring 19.0.2.23.3.
- Active job ids before → after (id lists byte-identical): payobook 49 → 49, payobook_template 31 → 31, p0clone 38 → 38, rize 81 → 81, sudima 80 → 80.
- Probe (system environment, rolled back) on all five: the three contracts load as `declared` (Expense 5 stages, Leave 5, Hiring 17); "already happens" rows Expense area 4 + approvals 6, Leave area 8 + approvals 6, Hiring area 19 (payobook 7: some Hiring built-ins are switched off there); 0 rows containing the framework's brand name; the Hiring, Time off, Expenses and Workflow Studio screens exist; the backend asset bundle builds. System account: "Payobook" (payobook, payobook_template, p0clone, sudima), "Rize" (rize).
- Warm after start: payobook.com 200, p0clone.payobook.com 200, rize.payobook.com 200, sudima.payobook.com 200, workbench `index.html?v=wf2-p2` 200. Signed-in checks of the hubs need the QA login (main loop).
- Service log: no ERROR or CRITICAL line since the restart (23:50 UTC).
- Downtime 329 s; whole run 394 s. Evidence: `/tmp/wf2-p2-20261110T234436Z/` (steps, upgrade logs, test output, probe, job lists, hashes, versions).
- Script slip (no effect): the line meant to record the switched-off job's name used the wrong column type and wrote nothing; the job (id 89, "Workflow Studio: progress active runs", now inactive) was read back by hand.

## 5. Deviations from the handover

1. **`stage_catalogue` returns an object** `{model, workflow_id, source, label, area, stages: [...]}`; the merged list is `stages` (exits last, flagged). Room for P3 without a second call.
2. **`record_stage` states**: besides `done | here | later`, `passed` (the record is beyond this stage but nothing shows it entered it: a user-made stage with no history row, or a core stage the area marks `optional`, e.g. Time off "Second Approval") and `stopped` (every track stage when the record sits in an exit). This is how "never mark a skipped stage done" is kept.
3. **Two new stored fields beyond the two models**: `pb.workflow.run.gate` (Json, allowed by §3.4) and `pb.workflow.log.stage_id` (Many2one, set on "Moved to …" rows) — the evidence `record_stage` uses for `done`.
4. **A gate is asked once.** A section, once entered (`gate.passed`), is not re-checked, so a record moving on mid-section never strands its work, and a person-stage cannot deadlock when the status moves past its anchor. Consequence: a record reaching an exit mid-section does not close the run (a later gate or a following approval step does) — ledger G16.
5. **A user-made stage the record has already gone past** (status later than the anchor): the gate passes without writing a position (writing one would break the invariant). Logged nowhere; `record_stage` then shows the stage as `passed`.
6. **Moves without a run** are allowed (designer, or the named owner resolvable from the record), but history rows need a run, so a move on a record with no run leaves no history row.
7. **Unique stage name** is enforced in Python among active stages (a database constraint cannot cover the empty workflow column). Positions are unique per (company, record type, record).
8. **Hiring stage list** in the shipped Stages dialog now shows Hiring's own stage rows only (those with a key); a stock recruitment stage row without a key is no longer listed there.
9. **Module action choices are compared as text** (`str`), because a screen sends them so. Contract authors: choice keys should be strings.
10. **Warnings are computed only for a structurally sound draft**, and repeat warnings only when the section bindings are valid (a broken binding is fixed first).
11. **Settings links in "already happens"** are dropped (`null`) when the target screen is not installed (seen locally for Expenses; present on the servers).
12. **Hiring "person this is about"** = the role's recruiter, else the candidate's recruiter (Hiring's own rule for "the recruiter"); manager = the role's hiring manager (`_pb_manager_targets`). No employee.
13. **`metadata.stages`** (the old Hiring stage list) is kept, now filled from the contract's action choices, for screens cached before this phase.
14. Gate and history sentences written by the worker are in English (the system environment has no language), as P1's were.

## 6. Overlaps found (R2a) — for the owner

1. **Two wordings for the same statuses.** Studio's stage names are each area's own status labels (what the back-office screens show: Time off "To Approve", "Second Approval"). The employee home's "My requests" list already has friendlier words per request type ("Waiting approval" for both, "Refused — your turn" for expenses). Options: (a) keep the back-office words in Studio (now); (b) use the employee-home words; (c) move both onto one shared label list per area. Recommend (a) now, (c) when the employee home shows workflow progress (P4).
2. **User-made stages on Hiring candidates.** Hiring already owns its stages (17 fixed keys, renames, per-role presets, "waited in a stage" rules). A company could now also add its own stage after a Hiring stage in Studio. Options: (a) allow it (now); (b) refuse user-made stages on candidates and send people to Hiring set-up; (c) allow only "heading" sections there. Recommend (b) or (c): Hiring is the owner (D3).
3. **Stage targets (`target_hours`).** Stored, not acted on in P2. Hiring's "has waited N days in a stage" rule and the approval engine's late reminders already chase lateness (D2). Options: (a) P3/P4 feed the target into the approval engine's reminder → pass-up (D2); (b) use it only for "where time goes" reporting; (c) drop it. Recommend (a)+(b).
4. **Plain-language rule sentences** (carried from P1 overlap 2): user-made rule stages describe their rule with Studio's own sentence builder; still no shared one found in the filter kit.
5. No overlap with Approval Matrix: the route sentence is the engine's own (`route_labels` / `summary`), Studio defines no route and sends nothing.

## 7. JSON shapes (real Expense example, local test database, rolled back)

Set-up for the example: company stages "Payment scheduled" (after Approved, moved by the HR lead responsibility, target 48 h) and "Receipts filed" (after Paid, by itself); a claim at Approved, moved into "Payment scheduled".

### 7.1 `metadata(...)['contract']`

```json
{"source": "declared", "label": "Expense claim", "area": "Expenses", "stage_field": "state",
 "has_subject": true, "submits_itself": false, "screen": "pb_expenses_hub",
 "stages": [
  {"key": "draft", "name": "Draft", "enters": "The employee starts a claim, or it comes back to them", "exit": false, "optional": false, "approval": false, "renamable": false, "kind": "core", "locked": true},
  {"key": "submitted", "name": "Waiting approval", "enters": "The employee sends the claim", "exit": false, "optional": false, "approval": true, "renamable": false, "kind": "core", "locked": true},
  {"key": "approved", "name": "Approved", "enters": "The last approver says yes", "exit": false, "optional": false, "approval": false, "renamable": false, "kind": "core", "locked": true},
  {"key": "paid", "name": "Paid", "enters": "Every receipt on the claim has been paid", "exit": false, "optional": false, "approval": false, "renamable": false, "kind": "core", "locked": true},
  {"key": "refused", "name": "Refused", "enters": "An approver says no", "exit": true, "optional": false, "approval": false, "renamable": false, "kind": "core", "locked": true}]}
```

Hiring stages also carry `id` (row), `family`, `revision` (when renamable), `meaning`. Discovered contracts (`source: "discovered"`) have empty `enters` and no exits.

### 7.2 `stage_catalogue('pb.expense.claim')`

```json
{"model": "pb.expense.claim", "workflow_id": null, "source": "declared", "label": "Expense claim", "area": "Expenses",
 "stages": [
  {"id": "core:draft", "kind": "core", "key": "draft", "name": "Draft", "locked": true, "area": "Expenses", "enters": "The employee starts a claim, or it comes back to them", "exit": false, "approval": false, "renamable": false, "revision": null, "stage_id": null},
  {"id": "core:submitted", "kind": "core", "key": "submitted", "name": "Waiting approval", "locked": true, "area": "Expenses", "enters": "The employee sends the claim", "exit": false, "approval": true, "renamable": false, "revision": null, "stage_id": null},
  {"id": "core:approved", "kind": "core", "key": "approved", "name": "Approved", "locked": true, "area": "Expenses", "enters": "The last approver says yes", "exit": false, "approval": false, "renamable": false, "revision": null, "stage_id": null},
  {"id": "yours:37", "kind": "yours", "key": 37, "name": "Payment scheduled", "locked": false, "counts_as": "Approved", "anchor": "approved", "enter": "person", "enter_owner": {"kind": "role", "id": 3}, "enter_rule": {}, "enters": "HR lead presses Move to Payment scheduled", "target_hours": 48, "exit": false, "count": 1},
  {"id": "core:paid", "kind": "core", "key": "paid", "name": "Paid", "locked": true, "area": "Expenses", "enters": "Every receipt on the claim has been paid", "exit": false, "approval": false, "renamable": false, "revision": null, "stage_id": null},
  {"id": "yours:38", "kind": "yours", "key": 38, "name": "Receipts filed", "locked": false, "counts_as": "Paid", "anchor": "paid", "enter": "auto", "enter_owner": {}, "enter_rule": {}, "enters": "By itself, when the steps before are finished", "target_hours": 0, "exit": false, "count": 0},
  {"id": "core:refused", "kind": "core", "key": "refused", "name": "Refused", "locked": true, "area": "Expenses", "enters": "An approver says no", "exit": true, "approval": false, "renamable": false, "revision": null, "stage_id": null}]}
```

Section bindings in a definition: `{"kind": "core", "value": "approved"}` or `{"kind": "yours", "id": 37}`. `stage_reorder(model, workflow_id, ordered)` takes the whole list in new order: module stages by key (strings, in their own order), user-made stages by id (numbers); each user-made stage then follows the nearest module stage before it. For a new-process workflow pass `model=''` and the workflow id; there are no core stages.

### 7.3 `existing_behaviour('pb.expense.claim', workflow_id)`

Each row: `stage` (contract key, `"yours:<id>"` for another workflow's user-made section, or `null` = not tied to a stage), `kind` (`message | todo | record | reminder | change`), `audience` (`approver | requester | manager | team | candidate | other`), `text`, `owner`, `settings` (`{action, lens?}` or `{workflow_id}` or `null`), `source` (`area | approvals | rules | workflow`), optional `detail`, optional `ref` (`hiring_rule:<id>`, `hiring_builtin:<key>`, `rule:<id>`).

```json
[
 {"stage": "approved", "kind": "change", "audience": "other", "text": "Every receipt on the claim is marked approved.", "owner": "Expenses", "settings": null, "source": "area"},
 {"stage": "refused", "kind": "change", "audience": "requester", "text": "Every receipt is marked refused with the approver’s reason, which the employee sees on their claim.", "owner": "Expenses", "settings": null, "source": "area"},
 {"stage": "refused", "kind": "message", "audience": "requester", "text": "The employee home shows the employee a “fix and resend” reminder.", "owner": "Expenses", "settings": null, "source": "area"},
 {"stage": "draft", "kind": "change", "audience": "requester", "text": "When a claim is sent back or taken back, its receipts can be changed and sent again.", "owner": "Expenses", "settings": null, "source": "area"},
 {"stage": "submitted", "kind": "change", "audience": "approver", "text": "Approval route “Expense claims”: Their manager, then Finance approver · whole company.", "owner": "Approval Matrix", "settings": {"action": "pb_approval_config.action_pb_approval_matrix"}, "source": "approvals", "detail": "After it is sent in, Their manager approves. Then Finance approver · whole company gives final approval."},
 {"stage": "submitted", "kind": "message", "audience": "approver", "text": "Each approver is told when it is their turn and gets a to-do.", "owner": "Approval Matrix", "settings": {"action": "pb_approval_config.action_pb_approval_matrix"}, "source": "approvals"},
 {"stage": "submitted", "kind": "reminder", "audience": "approver", "text": "A late approver is reminded, and then it is passed up.", "owner": "Approval Matrix", "settings": {"action": "pb_approval_config.action_pb_approval_matrix"}, "source": "approvals"},
 {"stage": "approved", "kind": "message", "audience": "requester", "text": "The person who sent it in is told it is approved.", "owner": "Approval Matrix", "settings": {"action": "pb_approval_config.action_pb_approval_matrix"}, "source": "approvals", "detail": "People who only use the employee home are not told this way."},
 {"stage": "draft", "kind": "message", "audience": "requester", "text": "The person who sent it in is told it was sent back.", "owner": "Approval Matrix", "settings": {"action": "pb_approval_config.action_pb_approval_matrix"}, "source": "approvals", "detail": "People who only use the employee home are not told this way."},
 {"stage": "refused", "kind": "message", "audience": "requester", "text": "The person who sent it in is told it was turned down.", "owner": "Approval Matrix", "settings": {"action": "pb_approval_config.action_pb_approval_matrix"}, "source": "approvals", "detail": "People who only use the employee home are not told this way."}
]
```

(Expenses' own `settings` is `null` here only because the Expenses hub is not installed on the local test database.) Another enabled workflow on the same record type adds rows like `{"stage": "approved", "kind": "todo", "audience": "manager", "text": "“Expense follow-up” gives their manager a task: “Book the payment”.", "owner": "Expense follow-up", "settings": {"workflow_id": 12}, "source": "workflow"}`.

Validation issue shape for a repeat (Review / `save_draft` / `_validate`):

```json
{"id": "tell", "code": "repeats_existing", "severity": "warning", "acknowledged": false,
 "text": "Time off already does this here: the employee is told their time off is approved. This step would send a second message.",
 "existing": "The employee is told their time off is approved.", "existing_source": "area"}
```

`review()` also returns `blocking` (errors + unacknowledged warnings). Binding errors carry `"id": "sections", "section": <index>`.

### 7.4 `record_stage('pb.expense.claim', id)`

```json
{"model": "pb.expense.claim", "record_id": 64, "source": "declared", "area": "Expenses",
 "track": [
  {"kind": "core", "state": "done", "key": "draft", "name": "Draft", "approval": false},
  {"kind": "core", "state": "done", "key": "submitted", "name": "Waiting approval", "approval": true},
  {"kind": "core", "state": "done", "key": "approved", "name": "Approved", "approval": false},
  {"kind": "yours", "state": "here", "key": 37, "name": "Payment scheduled", "counts_as": "Approved"},
  {"kind": "core", "state": "later", "key": "paid", "name": "Paid", "approval": false},
  {"kind": "yours", "state": "later", "key": 38, "name": "Receipts filed", "counts_as": "Paid"}],
 "exits": [{"key": "refused", "name": "Refused", "here": false}],
 "current": {"kind": "yours", "key": 37, "name": "Payment scheduled", "since": "2026-11-10 23:41:12", "by": "Example designer"},
 "approval_at": "submitted"}
```

`current` for a module status: `{"kind": "core", "key": "paid", "name": "Paid", "exit": false}`. For a new-process run call `record_stage('pb.workflow.run', run_id)`; the track holds that workflow's own stages only. `progress()` and `record_runs()` carry this object as `record_stage` (beside the unchanged `record_stages`); `progress()` also carries `gate: {section, reason}` while a run waits at a stage.

## 8. Self-review

- **R1 (add, never replace):** nothing shipped removed. Journey / Across / Flowchart / People, Build / Try / Review / Activity, step list, saved groups, module actions, reference steps, canvas untouched. "Heading only" sections behave exactly as before (no `bind` = no gate); published versions without bindings run identically (gates are skipped when no section is bound). `rename_record_stage` kept as an alias; `metadata.record_stages` and `metadata.stages` kept.
- **R2 (no double-ups):** Studio's only new effect is writing its own stage position, beside the record; no module status is written (T6 + T12 static guards, T12/T11 assert the status unchanged). The Hiring move goes through Hiring's own door and its rules fire once (T3). No approval route defined (the route sentence is read from the engine). The double-up check ships in the same phase: email / task / self-submitting approval steps warn against area, approval-engine, rule and other-workflow effects.
- **R2a (reuse first):** reused the engine's route words, the shared condition validator (for rule stages), the existing owner resolver, the areas' own manager rules and status labels, Hiring's `journey_stage` / `stage_rename` and its rule sentences. Four overlaps reported in §6 instead of chosen silently.
- **R3 (system level):** gates, positions and stale-row clean-up run in the system environment pinned to the run's company; facades run as the signed-in person with design / record-read checks; a date-triggered start is recorded as the person the record is about, with no new service user.
- **R4 (users add stages without programming):** company stages after any module status (or on a new process), entered by itself, by a named person, or when a rule matches; the record's own status is never touched.
- **R7 (white-label):** every new user-visible string checked (T1 banned-word test incl. "odoo"); the server probe counts branded "already happens" rows (§4). No technical identifier renamed.
- **R8 (plain English):** every new message is a sentence a process owner would say ("Waiting for this to reach Waiting approval.", "Stopped: the record is now Refused.", "Only Mai Tran can move this to Ready to pay.", "Records are in “Payment scheduled” now. Move them on before removing it."). Known gap kept (G10): the framework's own access message still names the technical record type when a person cannot read a record.

## 9. Needs an owner decision / follow-ups

- §6 overlaps 1–3.
- `sudima`: the Workflow Studio worker job now exists there and is **switched off** (D9 rule). If Sudima is to use workflows, it needs switching on.
- Browser check on payobook.com with the QA login (main loop), for the three workbench touches.
- P3 builds the Stages screen, "Gets here when…" lines and "already happens" rows on these shapes.
