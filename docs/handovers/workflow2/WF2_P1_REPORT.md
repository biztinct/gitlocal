# WORKFLOW-2 · Phase 1 report — backend unblock

Builder: Claude (Opus implementation agent), 11 November 2026. Handover: `WF2_P1_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (gotchas G4–G10 added).

## 1. Commits, files, version

| Commit | What |
|---|---|
| `fb02541cb` | Run workflows at system level and let approval steps follow the record (code + tests) |
| (docs commit) | This report, the ledger update, the handover |

`pb_lifecycle/__manifest__.py` → **19.0.1.10.0**. Workbench cache key `static/src/js/workflow_studio.js:18` → `v: "wf2-p1"`.

Files changed (all in `pb_lifecycle`, no other module touched, no stored field added/removed/renamed):

- `models/workflow_models.py` — `system(env, company)` helper (superuser env pinned to one company, `_pb_workflow_internal`); `_service()` and `WorkflowEvent._process` use it; execution-user checks deleted; `_advance` path timing; matrix `mode` (`follow` / `submit`); new `WorkflowStep._follow`.
- `models/workflow_studio.py` — `_validate` (no forced approval step, codes, `follow_needs_record`), `save_draft` (blocks by code, sets `timing: 'live'`, ignores `execution_user_id`), `get_workflow` (no `execution_user_id`), `review` (other workflows carry `trigger_label` + `scope_summary`), `activate` (exact-duplicate refusal, acknowledgement for same-kind peers, new-process route check through `biz.approval.engine.resolve_binding`), `_enqueue` (explicit company term), `_cron_workflows` (failed runs with waiting steps, per-step savepoint, follow handling, one log per run error) + `_check_waiting_step`.
- `models/workflow_definition.py` — `timing` in `fresh`, every issue has a `code`, `form_errors` returns `(code, text)`, `approval=` argument removed, `mode` and `timing` validated, `STRUCTURAL` code set.
- `models/workflow_configuration.py` — code `bad_comparison`.
- `models/workflow_progress.py` — reason "Waiting for this record to be sent for approval." for a following approval step with no request yet.
- `static/workflow/actions.js` — "Runs with this person's permissions" control and its save path removed; new approval steps on a record workflow get `mode: 'follow'`.
- `static/workflow/app.js` — approval-step select "What should this step do?" (record workflows only); Review "Also active for these records" lists each workflow's start event and filters in words and carries the confirmation box "I checked these; this workflow adds different work."
- `static/src/js/workflow_studio.js` — iframe `v=` bump.
- `tests/test_workflow_studio.py` — T1–T15, helpers, three tests re-ordered, one replaced.

## 2. Tests

Local (am_wf2, cloned from am_tpl and brought to HEAD with `-u all` + recruitment/Hiring) and server (`p0clone`, service stopped, `odoo-bin shell < tools/workflow_studio/run_suite.py`, rolled back):

```
Ran 56 tests … OK
WORKFLOW_TEST_RESULT={"tests": 56, "successful": true, "failures": 0, "errors": 0}
```
(locally 1 skip: `test_record_stages_reuse_native_statusbar…`, Expenses not installed; on p0clone 0 skips.)

| # | Test | Result |
|---|---|---|
| T1 | `test_t1_run_keeps_advancing_after_creator_and_publisher_leave` | pass |
| T2 | `test_t2_system_execution_stays_inside_the_runs_company` (env pinned to company A; B record refused; record moved to B → step fails, no task; A trigger ignores B record; follow ignores B's request) | pass |
| T3 | `test_t3_design_time_access_stays_with_the_designer` (unreadable record type refused; group-hidden field not offered and rejected with `bad_filter`) | pass (found a hidden field on both DBs, no skip) |
| T4 | `test_t4_assignee_who_cannot_read_the_record_is_not_assigned` | pass |
| T5 | `test_t5_approval_capable_model_runs_without_approval_step` (Other request, connected process, no approval step: validates, publishes, activates, runs) | pass |
| T6 | `test_t6_studio_never_writes_a_records_status` (scans `models/workflow_*.py` outside `_execute_action`) | pass |
| T7 | `test_t7_follow_waits_adopts_and_finishes_without_submitting` | pass |
| T8 | `test_t8_follow_finishes_when_the_record_is_already_approved` | pass |
| T9 | `test_t9_submit_is_sent_by_the_person_who_started` (valid starter = submitter; deactivated starter and system starter → plain message) | pass |
| T10 | `test_t10_version_without_mode_still_submits` | pass |
| T11 | `test_t11_several_automatic_workflows_share_a_record_type` | pass |
| T12 | `test_t12_one_timing_rule_for_path_decisions` (flat + grouped → same path on live record; version without key keeps snapshot) | pass |
| T13 | `test_t13_drafts_are_refused_by_code_not_wording` | pass |
| T14 | `test_t14_healthy_path_keeps_moving_beside_a_failed_one` | pass |
| T15 | `test_t15_new_process_approval_needs_a_route_before_activation` | pass |
| — | the 41 remaining existing tests | pass |

Existing tests deliberately changed:
- `test_native_approval_cannot_be_omitted` → replaced by T5 (the behaviour it asserted is what F1 removes).
- `test_custom_process_uses_native_matrix_and_frozen_answers`, `test_no_approval_route_reuses_native_fast_path`, `test_returned_approval_reopens_information_without_repeating_steps` → now publish, set the route, then activate (`publish_with_route`), because F14 refuses activation without a route. Assertions unchanged.
- `approval_route()` helper takes a `process` and switches off the company's other bindings for that process inside the test transaction (a tenant's own route would make the test route ambiguous).
- `setUpClass` also holds existing `failed` runs (the worker now resumes failed runs that have a waiting step).
- `test_new_conditions_read_live_old_branches_keep_snapshot` and `test_start_requires_explicit_grant` needed no change.

Browser check (local server on am_wf2, Chrome): settings dialog no longer has the permissions control and "Save settings" works; a new approval step on an "Other request" workflow defaults to "Wait for the approval this record already goes through", switching to "Send it for approval…" autosaves; Review shows "Also active for these records: WF2 other active (When a record is created · Records where Urgent is Yes)" with the confirmation box; no console errors. **Not done on payobook.com** — the QA login is held by the main loop; that check is still owed (ledger §3).

## 3. Pre-deploy live numbers (read-only, 10 Nov 22:3x UTC = 11 Nov Sydney)

| DB | enabled workflows | workflows | runs running/waiting | runs failed | live runs with approval step on a record | failed runs with waiting step | pending events |
|---|---|---|---|---|---|---|---|
| payobook | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| payobook_template | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| p0clone | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| rize | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

No live run could change behaviour, so the rail did not stop the deploy.

## 4. Deploy evidence

- Notes file: START `2026-11-10 22:38 UTC | WORKFLOW-2 P1 (Claude WORKFLOW-2) | START …` and DONE `2026-11-10 22:45 UTC | … | DONE | … 294 seconds (235 s down) …`. No other session had an open START.
- Lock: `flock` on `/tmp/payobook-studio-deploy.lock` (read-only open, see G9).
- Backups (risky tier): `/odoo/backups/wf2-p1-20261110T223829Z/` — `payobook.dump` 70 MB, `rize.dump` 31 MB, `p0clone.dump` 19 MB, `payobook_template.dump` 17 MB (`pg_dump -Fc`), `pb_lifecycle-before.tgz` (server tree before deploy; it hashed identical to `f68945ecc`).
- Steps: clean staging `/tmp/deployWF2` from `git archive HEAD pb_lifecycle` → service stopped (no `odoo-bin` left) → scoped `rsync -a --delete` into `/odoo/odoo-server/addons/pb_lifecycle/` → `-u pb_lifecycle --no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize (all exit 0, no ERROR/CRITICAL) → suite on p0clone 56/56 → probe → `orm_signaling_assets` + asset purge on all four → service started.
- Tree hash (skip `__pycache__`, `*.pyc`, `.DS_Store`): server `5882893eec71…ec908` = repo HEAD `5882893eec71…ec908`.
- `latest_version` = 19.0.1.10.0 in payobook, payobook_template, p0clone, rize.
- Active cron ids before → after: payobook 49 → 49, payobook_template 31 → 31, p0clone 38 → 38, rize 81 → 81; id lists byte-identical.
- Downtime 235 s; whole run 294 s.
- Warm: payobook.com 200, p0clone.payobook.com 200, rize.payobook.com 200, `/pb_lifecycle/static/workflow/index.html` on payobook.com 200. (`payobook-template.payobook.com` 404 — that is not the template's hostname; nothing to fix.)
- Log after restart: no ERROR in the four databases. Errors seen are `sudima` cron jobs (Hiring adverts, Calendar), already failing since at least 10 Nov 00:06, unrelated.
- Evidence folder on the server: `/tmp/wf2-p1-20261110T223829Z/` (steps, upgrade logs, test output, probe, cron lists, hash).

## 5. Deviations from the handover

1. **Approval step on a new process cannot be `follow`** (`follow_needs_record`): a new process has no record whose module would send it in, so a following step would wait forever. Added as a validation error; the workbench only offers the choice on record workflows anyway.
2. **Submit-mode message for a new process** drops the last sentence ("Send it from the record instead.") because there is no record; record workflows get the handover text exactly.
3. **Activation route check** blocks on `no_route` and `no_version` with the handover message, and on `ambiguous_route` with the approval engine's own message; it does **not** block a `paused` route (a pause is a temporary decision made in Approval Matrix; submission reports it at the time).
4. **`_follow` looks requests up with explicit company and process terms** instead of `source.approval_request_id` (G5).
5. **Worker hardening beyond the spec** (needed because failed runs are now re-scanned, G6): each waiting step is checked in its own savepoint and a problem fails that step only (logged once as "Needs attention: …"); a run-level worker error is written to history only the first time.
6. **Run scan stays all-companies** (no company term in the run search itself). Each run is worked in its own company's system environment; every lookup made from the worker carries a company term (`_enqueue`, `_follow`, `_resolve_owner`, approval events) or is checked against `env.company` (`_source`, `_mail_template`). Documented in code.
7. **Upgrade command**: ran `odoo-bin -u … --no-http --max-cron-threads=0` directly (as `tools/workflow_studio/deploy_release.py` does) instead of `~/pb_upgrade.sh`, which upgrades with HTTP and cron threads on (G9).
8. **Text tweak**: Hiring stage validation now ends "Joined stays with its own action." (was "native action", jargon under R8). No other existing wording changed.
9. `save_draft`'s error now lists only the blocking issues, not every issue.
10. `execution_user_id` is still written on create/publish/event/run (required columns) and still referenced by two record rules (`workflow_run_participant`, `workflow_log_participant`). Behaviour no longer depends on it; the rules were left alone because changing them changes who can see runs (G7, for the column-removal phase).

## 6. Hiring facade as the system, system account names

- Probe in all four databases, as the system environment: `pb.hiring._can_recruit()` = True, `_can_move(no role)` = True. The "Move to a Hiring stage" action is therefore accepted when called as the system; no Hiring change needed. (`_act_journey_stage` also refuses "joined" itself, unchanged.)
- System account (id 1, the worker job's user, shown as the actor of worker-written history): **payobook "Payobook", payobook_template "Payobook", p0clone "Payobook", rize "Rize"**. No framework brand name. Locally the template DB shows "BizApp".

## 7. Self-review

- **R1 (add, never replace):** only the "Runs with this person's permissions" control was removed (named in the handover). Journey/Across/Flowchart/People, Build/Try it out/Review/Activity, step list, saved groups, module actions, reference steps and the canvas are untouched. Published versions behave as before: no `mode` → submit; no `timing` → old path rule.
- **R2 (no double-ups):** "follow" never calls the engine's submit (T7/T8 count requests). No Studio code writes a record's `state`/`stage_id` (T6). No approval route is defined in Studio; route existence is read through the engine's public resolver. Effects are not added in this phase, so no new double-up check was due.
- **R3 (system level):** worker-side work runs as the system account pinned to the run's company; no per-workflow execution user, no new service user. Participant- and designer-facing methods still run as the signed-in person; design-time checks unchanged (T3); assignees still need read access (T4).
- **R7 (white-label):** every new user-visible string checked; none contains "Odoo"/"OdooBot". System account names verified above.
- **R8 (plain English):** new messages: "Waiting for this record to be sent for approval.", "Nobody is recorded as having started this, so there is no one to send it for approval. Send it from the record instead.", "Another active workflow starts on exactly the same records and event. Change the filters or pause the other one.", "Other workflows also start for these records. Review them and confirm this one does different work.", "Set up who approves this in Approval Matrix before turning it on.", "A new process has no record of its own to follow. Choose “Send it for approval”.", "This workflow timing setting is not supported.", "Choose what this approval step should do.", select labels, Review summaries ("When a record is created · Records where Urgent is Yes"). Known gap kept (G10): the framework's own access message names the technical model when an assignee cannot read a record.
- Security note for the reviewer: email steps now render their template as the system account (as native automated actions do); a designer still only picks templates they can read, and template-editing rights are unchanged.

## 8. Overlaps found (R2a)

1. **Review lists another Studio workflow twice** — once under "Existing automation to review" (its generated rule "Workflow Studio · …") and once under "Also active for these records" (G8). Options: (a) leave both; (b) hide Studio-generated rules from the automation list because the workflow list already covers them; (c) merge both into one "Already happens for these records" list in P3. Recommend (b) now or (c) in P3 — owner choice.
2. **Plain-language filter summary.** P1 added a small server-side sentence builder for Review ("Records where Urgent is Yes"). The workbench filter editor and `pb_filter_kit` show filters as editable chips but I found no existing sentence describer to reuse. If the owner knows of one (e.g. in Access or Filter kit), P3 should switch to it.
3. No overlap with Approval Matrix: following and submitting both go through the existing engine; Studio defines no route, no approver, no reminder.

## 9. Needs an owner decision / follow-ups

- Overlap 1 above (Review double listing).
- `sudima` and `pbf_preview` databases have Lifecycle installed at **19.0.1.6.0** (already behind before this phase; outside the four-database deploy set). The shared code on disk is now 19.0.1.10.0 for them too. Should they be upgraded, or is this expected?
- Browser check on payobook.com with the QA login is still owed (main loop).
- Whether a **paused** approval route should block turning on a new process (currently it does not; deviation 3).
