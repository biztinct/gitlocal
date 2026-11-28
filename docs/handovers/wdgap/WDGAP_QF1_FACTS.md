# WDGAP QF1 — plumbing facts: approve selected in the inbox; PayAI's daily alerts on Home

Verified by a read-only code survey on 2026-11-14 (branch 19.1). Do not re-derive; spot-check a line before relying on it.

I've checked everything below against the code, with file:line references. Two findings change the plan:

1. **Feature A:** a server-side bulk decide already exists (`act`), but nothing in the UI calls it any more.
2. **Feature B:** PayAI's daily alerts have never had a screen people can reach. Only their PDF report section and a Pulse Alerts list that platform admins alone can open use them.

All paths are under `/Users/adity/Documents/GitHub/gitlocal/`.

---

# Feature A — "Approve selected" in the one Approvals inbox

**Manifest versions:** `pb_approval_config` 19.0.1.8.0 (`__manifest__.py:41`) · `biz_approval_workflow` 19.0.1.7.1 (`:41`) · `biz_approval_chain` 19.0.1.1.0 (`:24`) · `pb_filter_kit` 19.0.1.4.0.

**Client files**
- `pb_approval_config/static/src/js/inbox.js`: `PbInbox`, registered as the `pb_approval_inbox` action (`:502`). The filter panel is a hand-built `FilterKit` on model `pb.approval.inbox` (`:187-194`). The `scope` (me/team/org) is sent on every call as `context.pbf_ctx.scope`.
  - Loading: `load()` calls `get_inbox_head` (`:291-307`). `loadPage()` calls `get_inbox_page(filters, search, sort, offset, limit=60)` and ignores stale answers via `kit.isCurrent(q.seq)` (`:310-334`).
  - Refreshing: `refresh()` (`:437-439`) runs `load()` and `kit.refresh()`. `kit.refresh` recounts the view tabs (`views: true`) and re-runs `onChange` → `loadPage` (`filter_kit.js:364-415`).
- `static/src/js/request_drawer.js`: single decide is `decide(action, useException)` (`:205-230`).
- `static/src/xml/inbox.xml`: cards inside `<PbFilterLayout>` (`:95`).
  - The card loop is at `:120-181`. The whole card has `t-on-click="open(cd)"` (`:123`), so a checkbox needs to stop that click from also opening the drawer.
  - The footer reads "Showing N of total" (`:184-191`). The drawer is mounted with `onChanged="refresh()"` (`:197-204`). The drawer's decide buttons are at `:505-528`.
- `static/src/scss/inbox.scss`: `.pbam-req` `:86`, `&.is-mine` `:96`.

**Row payload: `_card()`** (`models/inbox_facade.py:536-610`)
- Keys: `id, process, process_key, area, icon, title, sub, amount, currency, count, kind` (adapter kind label), `workflow, submitted_by, submitted_at, due_at, late, state, state_label, mine, blocked, block_reason, return_note, waiting_for, badges, route[{title,status}]`.
- **Not on the card:** `step_key`, `lock_revision`, `conflict`, `can_decide`. Those come only from `get_request` (`:683-754`, steps `:1014-1044`, conflict `:1046-1086`).
- `get_inbox_page` returns `{cards, total, offset, money}` (`:371-396`). `inbox_extra.py:61-71` adds `tasks` on page 1, but inbox.js never reads it.

**Single decide**
- Facade: `decide(request_id, step_key, action, reason=None, expected_lock_revision=None, idempotency_key=None, use_exception=False)` (`inbox_facade.py:1197-1232`).
  - `action` must be one of `approve|return|reject`.
  - Return and reject need a reason of at least 6 characters (`MIN_REASON`, `:55`). Approve needs none.
  - Approving through an exception needs an arranged grant and a reason of at least 12 characters (`:1216-1227`).
  - It returns the **full `get_request` payload**, which is heavy to build per row.
- Drawer call: `[requestId, step.key, action, reason, lock_revision, false, useException]` (`request_drawer.js:210-213`).
- **There is no typed confirmation in the inbox.** Typed words exist only in PayAI's decide actions: `pb_payai_actions/payai/actions_red.py` `ApproveItem` `:908-919` (`APPROVE`/`DUYỆT`), `SendBackItem` `:1020-1031`, `RejectItem` `:1064-1095`. PayAI never uses an exception (`:564-570`).

**Server guards** (`biz_approval_workflow/models/engine.py` `decide` `:1182-1308`)
- `_lock` takes `FOR UPDATE NOWAIT` on the request. If another person holds it: "Someone else is deciding this right now" (`:1169-1180`).
- Idempotency key short-circuit (`:1190-1194`). Lock-revision mismatch: "changed while you were looking" (`:1195-1199`).
- Only an open seat whose `acting_user_id` is the current user may decide; otherwise AccessError (`:1211-1222`). The user must be active, and `record.check_access('read')` runs on the business record (`:1223-1226`).
- A delegation that has lapsed is refused (`:1227-1234`).
- **Independence rule:** when the route's safeguard `independent` is on and the decider is the submitter, a maker or the subject, approval needs a grant and a reason (`:1236-1260`). `_conflict_kind` is at `:445-452`.
- Apply runs in a savepoint. A failure leaves the request `approved` with `block_reason` (`:1104-1131`). `act()` treats that as `ok: False` (`inbox_facade.py:1379-1387`).
- **Money:** `process.money` (`process.py:35`) only triggers a publish-time warning (`engine.py:642`). Nothing at decide time checks it.
  - The second-person rule for bank details lives in the adapters (`pb_records/models/records_approval.py:236-362`). The inbox only explains it afterwards (`_second_person_fix`, `inbox_facade.py:757-835`).
- **Visibility:** record rule `rule_request_own` (submitter / maker / seat holder) for `group_approval_user`. `rule_request_config` lets config users see everything (`biz_approval_workflow_rules.xml:108-119`). The company rule is at `:56-61`.

**Counts and badges**
- No bus and no service. Tab counts come from filter-kit `pbf_counts`, and "My turn" from `_my_turn_ids` (`:243-256`).
  - **Gotcha:** `_my_turn_ids` caches its answer in `env.cr.cache` under `('pb_approval_inbox.my_turn', uid)` for the whole request. A bulk RPC that recounts after deciding will read stale ids.
- Home's "Needs you" chips and Team tiles call `list_requests(tab='mine')` at load (`pb_dashboard/models/home_data.py:698-711`, `pb_home_hub/models/team_facade.py:432`). That path caps at 120 cards (`MAX_CARDS`). The hub shell has no lens badges.

**Precedents to clone**
1. **Existing server bulk verb:** `pb.approval.inbox.act(model, res_id, action, note)` (`inbox_facade.py:1354-1387`). Its sibling `get_team_data` returns `is_clean` via the adapter hook `_approval_batch_safe` (`:1314-1352`).
   - The hook is implemented only on overtime (`pb_hr_workforce/models/overtime_request_approval.py:194`). It fails closed.
   - The dock that called `act` has been retired: no JS in the tree calls `act` or `get_team_data`. Tests: `pb_close/tests/test_clean_batch.py`, `test_inbox_scopes.py:115-140`.
2. **Bulk per-row results:** `pb.ot.desk.act(request_ids, action, note)` runs each row in its own savepoint and returns `{results:[{id, ok, name, error}]}` (`pb_hr_workforce/models/ot_desk.py:422-448`). The client side is `pb_ot_desk.js:253-300` (`bulkApprove`, then `load()` and `kit.refresh()`), with the tray at `pb_ot_desk.xml:310-312`.
3. **Selection on the same filter kit:** `pb_ask_hr/static/src/js/askhr_lens.js`. `sel` map, `toggleAll` over loaded cards only, and dropping selections the new filters hide (rule R6) are at `:128-134` and `:329-357`. The server `act(verb, {ids})` returns `{done, skipped, message}` (`pb_ask_hr/models/askhr_board.py:591-630`).
4. **Bulk with a money confirmation and a reason, in this module:** `set_no_approval_bulk(..., reason, confirmations)` requires `'money_fast'` when money processes are included (`matrix_facade.py:1212-1236`). UI: `matrix_room.xml:421-449`.
5. There is no "approve all" in `pb_payslip_review`: payslips are approved as a run (`pb_payslip_review.py:456`). The `pb_lifecycle` "Repeat for each…" (`models/workflow_repeat.py`) is a workflow step, not a selection pattern. The filter kit's "%(n)s of %(total)s" text is at `filter_components.js:344`.

**Process kinds** (`biz.approval.process`; areas at `process.py:6-15`; ★ = `money=True`)
- **Pay:** payrun Pay run, reopen, retro, fnf, month.
- **Money out:** bankfile★, release★, journal★, payslips, filing (`pb_approval_config/data/processes.xml:20-98`); expense★ Expense claims (`pb_me_expense/data/approval_process.xml:14`).
- **Pay data:** records, runonly, loads, arrivals; records_bank★ (`pb_records/data/records_bank_process.xml:14`).
- **People:** paychange, contract, master, trip, assets, awards★, resign, verdict, newhire; payreview★ Pay review, bankchange Bank account change (**not** money), recognition, extension (`processes_p6.xml:18-46`); letters (`processes_p7.xml:14`); hiring_request★, hiring_jd, hiring_offer★, hiring_cover (`pb_hiring/data/approval_process.xml`); training_delay/claim/request; orgplan; goal_set, goal_change; hr_comm_post.
- **Time:** timesheet, overtime, leave, correction, unlock.
- **Setup:** scheme, statutory, bands, fx, schememap, mappings.
- **Platform:** roles, support, tenant, demo.
- **Other:** generic (`biz_approval_workflow/data/biz_approval_process_data.xml:8`); `workflow_studio` is created in Python (`pb_lifecycle/models/workflow_models.py:249`).

**Tests and i18n**
- Tests: `pb_approval_config/tests/test_inbox_facade.py` (decide pattern `:82-118`, fixtures `MatrixCase` in `common.py:15-103`), `test_inbox_scopes.py`, `test_static_contract.py`.
  - Every markup class must start `pbam-`/`pbim-` or be on an allow-list; `is-sel` is not on it (`:349-366`). No `self.env.company` in `inbox_facade.py` (`:422`). Kit colour tokens only (`:368`). Escape is handled in the capture phase (`:402`).
- i18n: `pb_approval_config/i18n/vi_VN.po` and `.pot` only, **no id**. `test_vietnamese.py:29-65` requires full coverage. `biz_approval_workflow` has `vi_VN.po` and `id_ID.po`; `biz_approval_chain` has `vi.po`.

---

# Feature B — PayAI's daily alerts on Home

**Manifest versions:** `pb_payroll_ai_insights` 19.0.3.12.4 (`:19`) · `pb_payai_actions` 19.0.4.2.2 · `pb_home_hub` 19.0.1.4.1 (`:45`) · `pb_dashboard` 19.0.2.2.8 (`:35`) · `pb_me_portal` 19.0.3.5.3.

**Model: `payroll.ai.pulse`** (`models/payroll_ai_pulse.py:70-117`)
- Fields: `name`, `severity` (info/warning/critical), `category` (cost/headcount/overtime/attendance/leave/other), `summary`, `details` (JSON text), `metric_value`, `baseline_value`, `deviation_pct`, `department_id`, `state` (new/acknowledged/resolved), `chart_config`, `user_id` (defaults to the cron's user). `_order='create_date desc'`.
- **No `company_id`, and no de-duplication.** Each daily run creates fresh rows whenever a condition still holds.

**Cron:** `ir_cron_payai_pulse_detection` runs `model.run_anomaly_detection()` daily and is active (`data/payroll_ai_pulse_cron.xml`). Its four detectors run under `sudo` across all companies (`:129-164`):

| Detector | Lines | Rule |
|---|---|---|
| Pay cost | `:166-227` | change over 10% vs the 3-month average; over 25% is critical |
| Headcount | `:229-276` | 3+ new this week = info; 2+ archived = warning; puts names in `details` |
| Overtime | `:278-343` | per department, +30%, salary rule code contains "OT" |
| Leave | `:345-385` | 5+ approved leaves in 7 days; 10+ = warning |

- Nothing produces `attendance`.
- AI summaries are written with names redacted (`:397-447`).
- **The cron checks no switch at all.**

**Reading alerts:** `rpc_get_active_alerts(limit=10)` (`:453-479`).
- It returns `[]` unless the reader can read `hr.payslip`.
- Each row: `{id, name, severity, category, summary, metric_value, baseline_value, deviation_pct, department, state, created, chart_config}`.
- `rpc_acknowledge_alert` / `rpc_resolve_alert` are at `:481-495`.

**Access**
- `security/ir.model.access.csv:12-13`: pulse users read/write, managers have full rights. There is **no record rule** on pulse.
- `payroll_ai_security.xml:91-95` makes `base.group_user` imply PayAI User on a fresh install. On payobook.com PayAI is a role instead (owner ruling 2026-10-20, `tests/common.py:1-34`).
- Groups: `group_payai_user` / `_manager` / `_admin` (`:21-42`).

**How alerts were shown before**
- An act_window `action_payroll_ai_pulse` with list and form views (`views/payroll_ai_pulse_views.xml:7-75`). Its context names `search_default_filter_active`, but no search view defines it.
- Menu PayAI › Pulse Alerts (`payroll_ai_menus.xml:31-35`). That root is not under payroll, so `pb_dashboard/models/menu_rails.py:58-103` prunes it for everyone except platform admins. **In practice it can't be reached.**
- Also used in the PDF report's "Anomaly Alerts" section (`payroll_ai_report.py:422-440`). Its `order='severity desc'` sorts the selection as text, so critical is not first.
- No JS has ever called `rpc_get_active_alerts` (checked with `git log -S`).

**Is there a PayAI on/off switch?**
- **No database-wide `ir.config_parameter` turns PayAI off.**
- What exists is per-company Boolean fields on `res.company`: `payai_tier_look`, `payai_tier_prepare`, `payai_tier_decide`, `payai_voice_go_ahead` (`pb_payai_actions/models/res_company.py:22-42`). They default to on only when the database name is `payobook`; the `post_init_hook` writes the same rule (`pb_payai_actions/__init__.py:6-21`).
- Gate helpers: `tier_on` / `tier_on_somewhere` (`payai/gate.py:427-460`), mapping in `payai/registry.py:50-54`.
- The one config parameter is `payai.voice_enabled`, for voice only (`payroll_ai_consent.py:29-34`).
- An active provider is found by `payroll.ai.config.get_active_config()` (`:100-115`).

**Home structure**
- `pb_home_hub/static/src/js/home_hub.js`: a HubShell with lenses `pulse` (the `PbDashboard` component) and `approvals` (`PbInbox`), both `wantsArrival` (`:127-149`). Other modules add lenses through registry `HOME_LENSES` (`:102`, e.g. `team_lens.js:293`).
- Feed: `pb.dashboard.get_home_data()` (`pb_dashboard/models/home_data.py:126-220`).
  - Each section runs in a savepoint via `section()`; AccessError gives the empty default (`:136-152`).
  - Foreign models are read only through `optional('<model>', lambda: env['<model>'])` (`:99-119`).
  - "Needs you" is `_home_needs` (`:691-732`). The closest precedent for a cross-module alert feed is `pb.clock.alert._home_need()` → `{n, text}` (`home_data.py:721-723`, `pb_clock/models/clock_alert.py:664-670`).
- Front end: `pb_dashboard/static/src/js/pb_dashboard.js`.
  - `load()` makes one call in `onWillStart` and is not awaited (`:541`, `:559-578`).
  - Word tables: `NEEDS` `:152-190`. Doors: `DOORS` `:132-144`, `door(xmlid, {lens, focus, back})` → `doAction(xmlid, {additionalContext, clearBreadcrumbs:true}).catch(notify)` (`:1681-1698`).
  - `needs` getter `:988-1009`.
- Template: `pb_dashboard/static/src/xml/pb_dashboard.xml`. Needs-you strip `:111-118`; the main layout row `pbd-split` follows at `:120`; then the `pbd-row3` row of cards at `:244` and the `pbd-row2` closing row at `:335`.
  - Cards follow `<section t-if="pc" class="pbd-card">`; a `None` section hides its card (test `test_home_cards.py:74`).
  - Icons come from `ic()`, which returns a new `markup()` on every call (`pb_import_kit/static/src/js/import_icons.js:382`).

**Who sees what on Home**
- The `item_home` rail entry is ungated (`pb_home_hub/data/pb_sidebar.xml`). The `pulse` lens is ungated; `APPROVAL_GATE=[]` (`home_hub.js:71`).
- Employee-only users (`res.users._pb_employee_only()`, `pb_me_portal/models/ess_landing.py:66-91`) land on `/my`. For them Home drops Pulse and opens on Approvals (`pb_me_portal/static/src/js/ess_home.js:15-20`). The same happens for `session.pb_hiring_not_payroll` (`pb_hiring/static/src/js/home_no_pulse.js:22-24`).
- Non-admins get `home_action_id` set to `pb_dashboard` (`menu_rails.py:106-118`).
- Demo users: `pb_demo.group_payobook_demo` (`pb_demo/security/pb_demo_security.xml:8`).

**Dependencies**
- `pb_home_hub` depends on `pb_hub, pb_settings, pb_payhub, pb_dashboard, pb_approval_config` (`__manifest__.py:50-57`), **not** on PayAI. `pb_dashboard` depends on `web, om_hr_payroll, pb_hr_payroll_base, pb_import_kit`.
- PayAI depends on `pb_learn` (`pb_payroll_ai_insights/__manifest__.py:55-82`), and `pb_dashboard` must never depend on `pb_learn` (`tests/test_activation.py:75`, `:244-256`). So a hard dependency from `pb_dashboard` on PayAI is effectively ruled out.
- Optional-read patterns: `optional()` in `home_data.py`, and `self.env.get(name)` in `pb_home_hub/models/team_facade.py:127-129`.

**Gotchas from the tests**
- `test_home_data.py:517-535`: every foreign model must be inside `optional()` and listed in `HOME_MODELS` (`test_activation.py:50-60`). No payslip-line token may appear in `home_data.py` (the pulse detector reads lines; reading pulse rows is fine).
- `TOP_KEYS` pins the payload keys (`test_home_data.py:29-31`). The `timing` keys are set at `home_data.py:133`.
- `test_home_front.py:116-129` checks that the JS word tables and the server keys match both ways.
- `test_home_cards.py:200-262` requires the `.pot` to be fresh and every `_t()` to have a non-empty Vietnamese translation. `pb_dashboard` has `vi_VN.po` and `.pot`; `pb_home_hub` and `pb_payroll_ai_insights` have `vi_VN.po` only, **no id**.
- Pulse rows have no company, so any reader with payslip-read sees every company's alerts.
- The detectors use `fields.Date.today()` (UTC).
- Existing PayAI tests: `tests/test_p0_gates.py:54-71` (pulse access follows payslip-read), `test_egress.py`, `test_redaction.py`.