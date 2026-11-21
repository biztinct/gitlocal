# Approval Matrix · Phase 1 — Engine foundation + audit source

**Handover from Fable (design) to Opus (build) · 12 Sep 2026 · read `APPROVAL_MATRIX_LEDGER.md` first and append to it.**

Design context (read once, do not re-derive): `docs/handovers/APPROVAL_MATRIX_DESIGN.md` (product decision), `docs/handovers/APPROVAL_WORKFLOWS_DESIGN_HANDOVER.md` §6–§10 and §13 (behaviour contract + acceptance IDs A01–A41), the POC at `docs/design/approval-matrix-poc/builder.js` (`P.evalRoute`, `P.runCoverage`, `P.sentence` — the route logic this engine must reproduce server-side).

## 1. Scope

Build the new module **`biz_approval_workflow`**: the one versioned, configurable approval engine every Payobook feature will use. Deliver it with a generic business object, full model-level tests, and the audit console reading its events. Deploy and install on every database.

**Binding non-goals for this phase** (later phases own them; do not start them):
- No OWL screens, no builder, no inbox (P2).
- No changes to `hr.payslip.run`, `pb_payruns`, `pb_approval`, `pb_team`, `pb_blueprint`, formula modules (P3/P4).
- No shim into `biz.approval.chain.mixin` consumers (P5). Do not edit `biz_approval_chain` except as noted in §5.7.
- No Payobook role catalogue seeding (HR lead, Finance approver…) — P2 seeds those in `pb_approval_config`. P1 seeds only the `generic` process and two generic roles (`reviewer`, `approver`).

## 2. Verified plumbing (do not re-derive)

| Fact | Where |
|---|---|
| Existing chain module: deps `base, web, mail`, version `19.0.1.0.3`, models `biz.approval.chain.mixin` (AbstractModel) + `biz.approval.step.log` (append-only; `create()` forces `user_id`/`stamp`) | `biz_approval_chain/__manifest__.py`, `models/biz_approval_mixin.py:15-175`, `models/biz_approval_log.py:1-60` |
| Mixin seams the P5 shim will use (leave them untouched now): `_approval_can` :42, `_advance_state` :65 (class-dict check at :69), `write` guard :118, `get_approval_trail` :147 | `biz_approval_chain/models/biz_approval_mixin.py` |
| Log ACL: `base.group_user` read+create, `base.group_system` full; company record rule | `biz_approval_chain/security/ir.model.access.csv`, `security/biz_approval_security.xml:6` |
| Audit console: `_SOURCE_META` :54, `_SOURCE_ORDER` :63, `_source_available` :145 (model-presence check), `_fetch_approval` :204 (pattern to copy), `_row(...)` normaliser, manager gate `_require_manager` :72 | `pb_audit/models/pb_audit_console.py` |
| Test style in this repo | `biz_approval_chain/tests/test_log_authenticity.py` |
| Constraint syntax (Odoo 19) | `_x_uniq = models.Constraint('unique(a,b)', 'msg')` — see ledger |
| Delegation of *access roles* already exists (`pb.access.delegation`, `biz_access/models/pb_access_delegation.py`); it is NOT approval delegation. Do not touch; P5 bridges | — |
| Working calendar = standard `resource.calendar` (company `resource_calendar_id`); `hr` gives `hr.employee.parent_id` (manager) | standard |

## 3. Architecture

### 3.1 Module layout

```
biz_approval_workflow/
  __manifest__.py           depends: biz_approval_chain, hr, mail  (NOTHING else)
  models/
    process.py              biz.approval.process        (catalogue row per business object)
    role.py                 biz.approval.role           (responsibility catalogue)
    responsibility.py       biz.approval.responsibility (who fills a role, where, when)
    delegation.py           biz.approval.delegation     (approval hand-over)
    exception_grant.py      biz.approval.exception.grant
    workflow.py             biz.approval.workflow + biz.approval.workflow.version
    binding.py              biz.approval.binding
    request.py              biz.approval.request / .request.step / .request.seat
    decision.py             biz.approval.decision       (immutable)
    event.py                biz.approval.event          (append-only)
    outbox.py               biz.approval.outbox         (+ cron delivery)
    engine.py               biz.approval.engine         (AbstractModel: resolve / preview / validate / submit / decide / reassign / cancel / escalate)
    definition.py           pure-python serializer + validator for the definition JSON (SCHEMA_VERSION = 1)
    adapter.py              biz.approval.adapter.mixin  (AbstractModel the business models inherit)
    generic_request.py      biz.approval.generic.request (real object + reference adapter)
  security/ (groups, ACL csv, record rules)
  data/ (roles, generic process, cron)
  tests/ (T01…T34 below)
```

### 3.2 Definition JSON (the contract with P2's builder; mirror the POC)

```json
{
  "schema_version": 1,
  "steps": [
    {"key": "s1", "kind": "review", "title": "HR lead review",
     "who": {"mode": "role", "role": "hr_lead", "scope": "division"},
     "min_amount": 0, "condition": null},
    {"key": "s2", "kind": "approve", "title": "Finance approval",
     "who": {"mode": "role", "role": "finance", "scope": "company"},
     "min_amount": 300000000, "condition": null},
    {"key": "s3", "kind": "joint", "title": "Joint sign-off",
     "who": {"mode": "people", "user_ids": [7, 9], "all": true}, "min_amount": 0,
     "condition": {"fact": "overtime_included", "op": "eq", "value": true}},
    {"key": "n1", "kind": "notify", "title": "Tell the preparer", "who": {"mode": "preparer"}}
  ],
  "tiers": {"enabled": true, "fact": "net_total"},
  "safeguards": {
    "independent": true,
    "self_exception": {"enabled": false},
    "repeated": "different",
    "evidence": [{"key": "control_report", "name": "Payroll control report", "when": "before_final"}],
    "due": {"kind": "working_days", "days": 1, "calendar_id": null},
    "late": {"remind_days": 1, "escalate_days": 2, "reassign": false}
  }
}
```

Rules enforced by `definition.py` (`validate(definition, capabilities) -> {errors:[], warnings:[]}`):
- `kind ∈ review|approve|joint|any|notify|fast`. A `fast` step must be the only decision step. `notify` steps are never counted.
- `who.mode ∈ role|manager|skip|people|team|preparer(notify only)`. `role` requires a known `biz.approval.role.key`; `people` requires ≥1 active user; `joint` requires `people` with ≥2 and `all=true` or a `role` with `pool=true`; `any` requires `team` or a pool role.
- `condition` facts/ops must be in the adapter's `capabilities().facts` (typed: bool/decimal/int/percent/selection) — unknown fact = error. `min_amount` needs `tiers.fact` to be a decimal fact with a currency.
- Errors block; warnings get codes per ledger AM4. Empty decision route → warning `fast_lane` (treated as fast).

### 3.3 Models (fields that matter; add `company_id` + `active` + chatter where noted)

- **biz.approval.process**: `key` (unique), `name`, `area` (selection: pay, money, data, people, time, setup, platform, other), `model_name`, `description`, `allow_fast` (default True — informational only now), `money` (bool: triggers `money_single_person` warning), `connected` (computed: an adapter model is registered for `model_name`), `sequence`. Adapters create their row in data XML.
- **biz.approval.role**: `key` (unique), `name`, `description`, `fallback_to_company` (bool), `pool` (bool), `sequence`, `active`.
- **biz.approval.responsibility**: `company_id` (req), `role_id`, `scope_key` (Char, '' = company), `scope_label`, `user_id`, `backup_user_id`, `pool_user_ids` (M2M, used when role.pool), `date_from`, `date_to`, `active`, `note`. Constraint: no two active single-holder rows for the same (company, role, scope) with overlapping dates (Python constraint). `resolve(company, role_key, scope_keys_in_order, on_date)` → the most specific row; if none and `role.fallback_to_company` → the company row; else None. Returns `(row, via_label)`.
- **biz.approval.delegation**: `company_id`, `principal_user_id`, `delegate_user_id`, `role_ids` (empty = all seats), `date_from`, `date_to`, `reason` (req), `state` draft/active/ended/revoked, `set_by_uid`. Constraints: principal ≠ delegate; delegate must not itself be a principal of an active delegation overlapping (no chains). `covering(user, company, role_key, on_date) -> delegate or None`. `unlink` refused (history), revoke instead.
- **biz.approval.exception.grant**: `company_id`, `process_id`, `workflow_id` (optional), `step_keys` (Json list), `scope_key` ('' = any), `user_ids`, `role_ids`, `conflicts` (Json list of maker|submitter|subject), `date_to`, `reason` (req), `state` active/revoked, `set_by_uid`. `permits(request, step, user, conflict_kind)`.
- **biz.approval.workflow**: `company_id`, `name`, `process_id`, `owner_user_id`, `active`, `parent_workflow_id` (custom variants), `published_version_id` (computed), `draft_version_id` (computed), `state` (computed: draft/published/archived). `action_new_draft()` copies the published definition into a new draft revision.
- **biz.approval.workflow.version**: `workflow_id`, `revision` (int), `status` draft/published/superseded/archived, `definition` (Json), `schema_version`, `summary` (computed sentence — port `P.sentence`), `route_labels` (computed Json list — port `P.routeLabels`), `published_by_uid`, `published_at`, `effective_from`, `publish_reason`, `confirmations` (Json), `fingerprint` (sha256 of canonical definition), `draft_revision` (int, incremented on every draft write for optimistic locking). Unique `(workflow_id, revision)`. `write` on a published version raises unless only `status` (supersede/archive) changes.
- **biz.approval.binding**: `company_id`, `process_id`, `scope_key` (''=company default), `scope_label`, `kind_key` ('any' default), `workflow_id`, `mode` follow/pin/paused, `pinned_version_id`, `date_from`, `date_to`, `revision`, `note`. Constraint at create/write: no other effective binding with same (company, process, scope_key, kind_key) — raise `ValidationError` naming the clash (that is the "tie refused at publish").
- **biz.approval.request**: `process_id`, `company_id`, `res_model`, `res_id`, `title`, `attempt` (int), `source_revision` (Char hash), `scope_keys` (Json), `kind_key`, `facts` (Json), `amount`, `currency_id`, `maker_uids` (Json), `submitter_uid`, `subject_uids` (Json), `binding_id`, `version_id`, `state` (pending/approved/applied/returned/rejected/cancelled/blocked), `current_step_key`, `due_at`, `lock_revision` (int), `submitted_at`, `closed_at`, `return_note`, `confirmations` (Json copied from version). Chatter (`mail.thread`). `_read_group`/search must be company-scoped by record rule; visibility rule: submitter, maker, any seat holder or delegate, or `group_approval_config` members of the company.
- **biz.approval.request.step**: `request_id`, `key`, `sequence`, `title`, `kind`, `included` (bool), `include_reason`, `status` pending/active/done/skipped/returned/blocked, `due_at`, `activated_at`, `decided_at`, `block_reason`.
- **biz.approval.request.seat**: `step_id`, `request_id` (related stored), `key`, `user_id` (principal), `acting_user_id` (delegate at activation, else = user), `resolved_via` (Char), `backup_user_id`, `status` open/approved/returned/rejected/reassigned. Unique `(step_id, key)`.
- **biz.approval.decision**: `request_id`, `step_id`, `seat_id`, `user_id` (actual, forced = env.uid in create), `acting_for_uid`, `action` approve/return/reject/reassign/cancel/apply, `reason`, `stamp` (forced), `source_revision`, `idempotency_key` (unique), `exception_grant_id`, `conflict_kind`. `write`/`unlink` always raise.
- **biz.approval.event**: `company_id`, `kind` (selection: submitted, step_activated, decided, returned, rejected, cancelled, applied, blocked, reassigned, escalated, reminded, published, binding_changed, responsibility_changed, delegation_changed, grant_changed, exception_used), `summary` (plain words, e.g. "Nithya approved HR lead review on Pay run · September 2026"), `payload` (Json), `user_id` (forced), `stamp` (forced), `request_id`, `workflow_id`, `res_model`, `res_id`. Append-only (`write`/`unlink` raise except for system in tests).
- **biz.approval.outbox**: `kind` (your_turn, reminder, escalation, returned, approved, rejected, exception_used, covering), `user_id`, `request_id`, `payload`, `dedupe_key` (unique), `state` queued/sent/failed, `attempts`, `last_error`. Cron `biz_approval_workflow.cron_outbox` (every 5 min): delivers as a `mail.activity` on the request (type `mail.mail_activity_data_todo`) + a `message_post` with `partner_ids`; never puts amounts or bank details in the subject. Idempotent by `dedupe_key`.

### 3.4 Adapter contract (`biz.approval.adapter.mixin`, AbstractModel)

Business models inherit it and set `_approval_process_key`. Methods (defaults raise `NotImplementedError` where marked):

- `_approval_context(self)` **(impl)** → dict: `company_id, title, scope_keys (list, most specific first, last = ''), kind_key, facts {key: {"value":…, "unit": "VND"|"h"|"%"|"count"|"bool"|…}}, amount, currency_id, maker_uids, submitter_uid, subject_uids, source_revision, evidence [{key,name,ok,note}]`.
- `_approval_capabilities(self)` **(impl, @api.model)** → `{facts: {key: {type, label, unit}}, kinds: [{key,label}], evidence: [{key,label}], scope_levels: [labels], manager_mode: bool}`.
- `_approval_coverage_scopes(self, company)` **(impl, @api.model)** → `[{scope_key, label, kind_key, headcount}]` for the coverage scan.
- `_approval_validate(self)` (default ok) → raise `UserError` for domain reasons (mixed scope etc.).
- `_approval_freeze(self, request)` (default no-op) → lock decision-relevant fields.
- `_approval_apply(self, request)` **(impl)** → the domain transition after final approval; must be idempotent and re-verify `request.source_revision == current`.
- `_approval_return(self, request, reason)` (default no-op) → make the record editable again.
- `_approval_manager_uids(self)` (default: `hr.employee` of `subject_uids` → `parent_id.user_id`) for `who.mode = manager`/`skip`.
- Convenience: `action_approval_submit()` → `engine.submit(self)`; `approval_request_id` (computed latest open request); `approval_state` (related).

### 3.5 Engine (`biz.approval.engine`, AbstractModel — all public methods re-check access)

- `resolve_binding(company, process, scope_keys, kind_key, at)` → `(binding, version, trace[])`: walk `scope_keys` in order; at each rank prefer exact `kind_key`, then `any`; first effective binding wins; `paused` = stop with error; tie (two effective at same rank+kind) = error `ambiguous_route`; none = error `no_route`. `trace` is the "Why this route?" list.
- `preview(version_or_definition, example_ctx)` → the POC `evalRoute` port: per step `{key,title,kind,included,reason,people:[{user_id,name,via,cover_user_id,backup_user_id}],issue:{level,code,msg,fixes[]},due_at}` + `issues[]` + `level` (ready/warn/block) + `via` trace. Pure function of inputs; no writes; no notifications.
- `validate_for_publish(version)` → `{errors, warnings}` = definition validation + binding overlap check + coverage scan over `_approval_coverage_scopes` (missing person per scope → `coverage_gap:<scope>` warning) + independence feasibility + single-person/money checks + notify-only route.
- `publish(version, expected_draft_revision, effective_from, reason, confirmations)` → refuses if `errors`, refuses if any warning code not in `confirmations` (message lists the missing ones), refuses if `draft_revision` moved (concurrent edit). Supersedes the previous published version, writes `published_*`, `fingerprint`, event `published`.
- `submit(record, idempotency_key)` → `_approval_validate`, context, resolve, build request (freeze facts, copy `confirmations`), evaluate step inclusion, resolve people for every included step now (frozen principals) — a missing person = request `blocked` with `block_reason` (not refused: the request exists and is repairable), fast lane → `state=applied` + `_approval_apply` immediately + event `applied`; else activate step 1 (seats open; delegation resolved into `acting_user_id`; outbox `your_turn`), event `submitted`. Idempotent on `idempotency_key` (return the existing request).
- `decide(request, step_key, action, reason, expected_lock_revision, idempotency_key, exception_grant=None)`:
  1. `SELECT … FOR UPDATE NOWAIT` on the request row (`self.env.cr.execute`), re-read; `expected_lock_revision` mismatch → `UserError` "This request changed. Reload." Existing decision with the same `idempotency_key` → return it (no double count).
  2. Eligibility: user is `acting_user_id` of an open seat on the active step; user active; delegation still valid (recheck `covering`); record access via `record.check_access('read')`.
  3. Independence: if `safeguards.independent` and user ∈ maker/submitter (or subject) → require `exception_grant` that `permits(...)` and non-empty `reason`; record `conflict_kind`, `exception_grant_id`; event `exception_used`; outbox to workflow owner.
  4. Joint: one seat per person; the step completes when every required seat is approved. `any`: first approval closes all seats. Repeated-person rule (`repeated = different`): at activation, if the resolved principal already decided an earlier step, use `backup_user_id`; if none, seat opens with `resolved_via = 'repeated person, no backup'` and `preview` warns.
  5. `return` → step + request `returned`, open seats `returned`, `_approval_return`, outbox to submitter. `reject` → `rejected`, `_approval_return` not called (record stays as submitted; adapter decides), outbox. `approve` completing the last step → `state=approved`, then `_approval_apply(request)` under the same lock; success → `applied`; failure → stays `approved` with `block_reason` (retriable via `retry_apply`), never half-applied.
  6. `lock_revision += 1`; decision row; event; outbox after commit (`self.env.cr.postcommit.add` for the delivery kick — the rows are written in-transaction).
- `reassign(request, seat_key, new_user, reason)` → allowed for workflow owner / `group_approval_admin`; logs decision `reassign` + event; never erases a completed decision.
- `cancel(request, reason)` → submitter or admin; only while pending/blocked.
- `repair(request)` → re-resolve people for blocked steps (after a manager/responsibility fix); if all resolve → `pending`, event.
- `escalate_cron()` (hourly): active steps past `due_at + remind_days` → outbox `reminder` once; past `+ escalate_days` → outbox `escalation` to `workflow.owner_user_id` once; if `late.reassign` and backup exists → `reassign` logged as system with reason "Late: reassigned to backup as configured". Never approves.
- Due dates: `due.kind ∈ none|working_days|calendar_day|per_request`; `working_days` uses the company `resource_calendar_id` (`plan_days`); `calendar_day` = next occurrence of day N at 17:00 company tz; store `due_at` UTC.

### 3.6 Security

Groups (data XML, `name` + `implied_ids` only): `group_approval_user` (implied by `base.group_user`: may submit, decide own seats, read own requests), `group_approval_config` (edit drafts, responsibilities, bindings in own companies), `group_approval_publish` (implies config; publish), `group_approval_admin` (implies publish; grants, others' delegations, reassign, cancel any), `group_approval_audit` (read all events). ACL csv accordingly; record rules by `company_id in company_ids` on every company-bearing model; request visibility rule as in §3.3. Decisions/events: create allowed to `group_approval_user`, no write/unlink for anyone (model-level raise; ACL grants none). Do not grant `base.group_system` write on decisions/events either.

### 3.7 `biz_approval_chain` (minimal, additive only)

Bump version to `19.0.1.1.0` and add nothing else. (P5 will add the engine seam.) If you find you need a change here, stop and record why in the ledger instead.

### 3.8 Audit console source (in `pb_audit`)

Add `depends: biz_approval_workflow` to `pb_audit/__manifest__.py`; add source key `workflow` to `_SOURCE_META` (`label: 'Approval workflow', icon: 'workflow', color: 'violet'`), `_SOURCE_ORDER` after `approval`, `_source_available` (`biz.approval.event`), and `_fetch_workflow(filters, limit)` copying `_fetch_approval`'s domain handling (`stamp`, `user_id`, `res_model`), title = `event.summary`, old/new = kind label / request state. Keep the existing `approval` source untouched. Bump `pb_audit` version.

## 4. Safety rails

1. No `sudo()` in engine writes. Reads for resolution may use `sudo()` on responsibility/delegation/grant only after the caller's access to the request was checked.
2. Never fall back to "everyone in group X". Unresolved = blocked with a named fix.
3. Immutable: published versions, decisions, events. Model-level guards, not just ACL.
4. Every message a user can see: plain words, no "Odoo", no model names, no state keys. Example: "This request changed while you were looking at it. Reload to see the latest." Not "lock_revision mismatch".
5. The engine imports nothing from `pb_*`.
6. Keep methods callable over RPC without an underscore prefix only where the UI needs them (`submit`, `decide`, `preview`, `validate_for_publish`, `publish`, `reassign`, `cancel`, `repair`, `list_requests`, `get_request`); everything else `_`-prefixed.

## 5. Tests (`biz_approval_workflow/tests/`, all `@tagged('post_install','-at_install')`, using `biz.approval.generic.request` and freshly created users/companies)

| ID | Scenario | Expected |
|---|---|---|
| T01 | Definition validation: unknown role / unknown fact / joint with one person / fast + other steps | errors with codes; valid definition returns no errors |
| T02 | Warnings: fast lane; single person; independence off; money process single person; notify-only | warning codes per AM4 |
| T03 | Publish refuses when a warning is unconfirmed; succeeds with all confirmations stored | `confirmations` on version |
| T04 | Publish with stale `expected_draft_revision` | UserError, nothing published |
| T05 | Binding precedence A01: company default vs scope rank 2 vs rank 1 | most specific wins; trace lists candidates |
| T06 | Exact `kind_key` beats `any` within a rank (A04) | correct binding |
| T07 | Two effective bindings same rank+kind (A02) | second create raises ValidationError; runtime `resolve_binding` on a forced tie → `ambiguous_route` |
| T08 | Cross-company: binding in company B never matches company A record (A03) | `no_route` |
| T09 | Paused winning binding (A05) | submit refused with pause message, no fallback |
| T10 | No binding (A06) | submit refused; no request row |
| T11 | Responsibility resolution: division exact → company fallback only when `fallback_to_company`; division-required role missing → blocked request with fix | as designed |
| T12 | Overlapping single-holder responsibility rows | ValidationError |
| T13 | Submit builds steps/seats; tiers skip steps under `min_amount`; condition skips; frozen facts | correct `included`/`include_reason` |
| T14 | Fast lane: submit → `applied` immediately, `_approval_apply` called once, event `applied` | as designed |
| T15 | Independence: submitter is the resolved approver, no grant (A10) | decide raises; message names the conflict |
| T16 | Independence with a valid scoped grant + reason (A37) | decision recorded with `exception_grant_id`, event `exception_used`, outbox to owner |
| T17 | Grant expired / wrong scope / wrong step / empty reason (A38) | refused |
| T18 | Joint step: two distinct users must approve (A11); duplicate click by the same user with a new idempotency key | second click refused ("already approved this step"); step not complete until both |
| T19 | Same idempotency key twice (A14/A20) | one decision row; second call returns it |
| T20 | Stale `expected_lock_revision` | UserError |
| T21 | `any` mode: first approval closes the step | seats closed |
| T22 | Delegation: active hand-over → `acting_user_id` = delegate; delegate decides; decision records both; expired hand-over → principal only (A12/A13) | as designed |
| T23 | Delegation chain / self-delegation | ValidationError |
| T24 | Repeated-person rule: same principal on consecutive steps → backup seat; no backup → seat opens with note and preview warns (A40) | as designed |
| T25 | Return → request `returned`, `_approval_return` called, resubmit creates attempt 2 keeping history (A17) | as designed |
| T26 | Reject → `rejected`, history kept | as designed |
| T27 | Reassign by admin with reason; earlier completed decision untouched | as designed |
| T28 | `_approval_apply` raises → request stays `approved` with `block_reason`; `retry_apply` completes; no double apply (A34) | as designed |
| T29 | Source revision changed after submission → final approval refuses to apply; return required (A16) | as designed |
| T30 | Published version immutable; new draft copies it; old requests keep `version_id` after a new publish (A07/A08) | as designed |
| T31 | Escalation cron: overdue → one reminder, then one escalation; `reassign=true` with backup → logged reassignment; never approves (A19 partial) | as designed |
| T32 | Access: a plain user cannot read another company's request, cannot write a decision/event/published version, cannot call `decide` on a seat that is not theirs (A15/A31) | AccessError / refused |
| T33 | Coverage scan: one scope lacks a person → warning `coverage_gap:<scope>` while the example passes (A33) | as designed |
| T34 | Audit console: `_fetch_workflow` returns event rows; gate still enforced | rows present |

## 6. Deploy & verify

1. Commit locally per feature (engine models; engine services; tests; audit source), messages per ledger.
2. Deploy `biz_approval_workflow`, `biz_approval_chain`, `pb_audit` per the ledger deploy contract.
3. Run the test suite on the server against a scratch DB created from `payobook_template` (ledger §8). All T-cases must pass; paste the summary line.
4. Install `biz_approval_workflow` and upgrade `biz_approval_chain, pb_audit` on **every** DB (`psql -l` on the box; expected at least `payobook, payobook_template, abm, acme, rize`). Take a `pg_dump -Fc` of each tenant first.
5. Verify per DB: `ir_module_module.state/latest_version` for the three modules; a `biz.approval.generic.request` created via RPC as a test user goes pending → approved → applied through the engine; the Audit console page loads (Chrome MCP) and shows the workflow source; remove screenshots afterwards.
6. Version parity: repo manifest vs DB for the three modules on every DB.

## 7. Report back (in your final message)

- Files created/changed (paths), model list with field counts, RPC surface list.
- Test results: exact pass/fail counts, the log summary line, any skipped case with reason.
- Deploy: per-DB install/upgrade result, `EXIT=` lines, registry load time, any traceback.
- Deviations from this handover with reasons; open questions for P2.
- Ledger entries you appended (AM numbers).
- Commit hashes.
