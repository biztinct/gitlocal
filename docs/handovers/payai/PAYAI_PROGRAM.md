# PayAI "Do it for me" — command execution design

Status: DESIGN STAGE (2026-10-12). Exploration in progress; sections below are filled as facts land.

## Context
Today PayAI answers questions and can launch a guided tour. The owner wants PayAI to *carry out* the
things a user otherwise does by clicking through menus, buttons and wizards — e.g. "run June payroll for
Retail" — by typing or speaking, while (a) capturing the inputs the wizard would have asked for,
(b) respecting the person's access, and (c) making sure nothing risky runs by mistake.

## Verified plumbing (filled from exploration)

### PayAI today (`pb_payroll_ai_insights` 19.0.3.10.0)
- **Answers only.** No tool/function calling anywhere in custom modules. Intent classifier = LLM substring
  match (`payroll_ai_engine.py:500–535`): payroll_data / payroll_knowledge / onboarding / general.
- **Only action type today**: `open_lesson` / `open_walkthrough`, server-whitelisted by `_sanitize_action`
  (:803–846), rendered as a "Show me" button (`ai_insight_chat.js:270–294`). Legacy `start_tour` maps to a lesson.
  `pb_coach` is DELETED (commit 12283805b); replacement = `learn.scenario` service
  (`pb_learn/static/src/scenario/scenario_service.js:467`, modes watch/try/do; `sc_payrun` compute step is `guard:true`).
- **RPC**: `payroll.ai.conversation.rpc_send_message(message, session_id, screen)` :223; `rpc_transcribe_voice` :401
  (Whisper via MediaRecorder, 60 s cap, transcript goes into the box, NOT auto-sent :553). Screen context
  `_currentScreen()` :228–240 sends {tag, xml_id, model, name, hub, tab}.
- **Providers**: `ai_providers/openai_provider.py` (chat.completions, no tools), `anthropic_provider.py` (default
  claude-sonnet-5, drops temperature; BUG :79–82 overwrites system prompt with the screen note). `payroll.ai.config`
  fields: provider_type openai/anthropic/ollama/tesseract, purpose insights/doc_ocr, api_key, model_name, company_id.
  `get_active_config` :100 ignores `purpose`.
- **Who is a PayAI user**: `base.group_user` implies `group_payai_user` (`payroll_ai_security.xml:88–92`) → everyone.
  Manager rule :78 lets a PayAI manager read/clear/post into anyone's conversation via `session_id`.
- **Mounting**: floating pill (`main_components`), hides when pb_learn Coach drawer hosts it; embedded copy is the
  Coach's "ask" tab (`pb_helper_tabs` → `ask`). Coach Guide tab = deterministic `learn.intent.ask`; its composer
  prompt says "never claim to have performed an action" (`learn_intent.py:545–561`) and hard-codes "Payobook" :547.
- **Only human-confirm precedent for an LLM change**: Formula Studio "Edit with PayAI" proposal card Apply/Discard
  (`studio.xml:3727–3733` → `apply_ai_formula` :14491 → `save_formula` :2559, versioned for undo). Server guard = ACL only.
- **Pay run wizard Learn anchors** (`pb_payrun_wizard/static/src/xml/payrun_wizard.xml`): pw-rail, pw-scope, pw-scheme,
  pw-division, pw-summary, pw-paydata, pw-paymode, pw-coverage, pw-result, pw-pills, pw-missing, pw-exceptions,
  pw-compute, pw-skipsheet.
- **Pre-existing safety gaps worth fixing in the same stream**: pulse reads with sudo and returns to everyone
  (`payroll_ai_pulse.py:168–350, :454`); non-data paths send the raw message unredacted (:683, :902, :1011).

### Navigation + palette (the "doors" catalogue already exists)
- **App-wide ⌘K is Payobook's own**: `pb_hub/static/src/js/hub_palette_service.js:251` (hotkey control+k), service
  `pb_hub_palette`; yields to Mission Control/Formula Studio via `pb_hub_palette_yield` (:60–63). `run(id)` :183–216
  → `openHub(actionService, {tag, xmlid, lens, lensKey})`. Rows filtered by `groups` any-of + feature + action present (:137–160).
- **Registry contract** `registry.category("pb_hub_palette").add(id, {id,label,sublabel,icon,group,action:{tag}|{xmlid},
  lens,lensKey,groups,requires},{sequence})` (`hub_palette_entries.js:1–20`); ~37 `*_palette.js` files across modules.
  e.g. `payhub_runs` → `{tag:"pb_pay_hub", lens:"runs"}` (`pb_payhub/static/src/js/pay_hub_palette.js`).
- **openHub protocol** `pb_hub/static/src/js/hub_nav.js:45–85`: ctx `pb_lens`, `pb_focus`, `pb_back`; pb_mission reads
  `pb_shell_lens`. Hub tags/lenses: pb_pay_hub (run, runs, payslips, results, import, deliver, adjust, settle),
  pb_home_hub (pulse, approvals), pb_insights_hub, pb_compliance_hub, pb_people_hub, pb_settings_hub, learn_hub,
  pb_lifecycle_hub, pb_workforce (today…close). "Where am I" store `hub_place.js:1–64`, `switchLens(key)` :140.
- Odoo core command palette is shadowed by the pb_hub binding; no module adds a `command_provider`.

### Preview → confirm → do → undo precedents (clone these)
- **Approval matrix bulk**: `matrix_facade.py:1091 bulk_no_approval_preview` → `:1124 set_no_approval_bulk(..., reason,
  confirmations)` returns `{done, skipped, undo}` snapshot → `:1207 undo_no_approval_bulk`. Review drawer
  `matrix_room.js:208–310`, undo banner `matrix_room.xml:169–174`.
- **Records Desk**: `pb_records_desk.py:1099 preview_changes` → `:1392 apply_changes` → `:1480 undo_apply`;
  `pb.records.change` stores before/after; undo refuses if value changed since.
- Confirms elsewhere use core `ConfirmationDialog`; no shared Payobook confirm component.

### LLM config
- `payroll.ai.config` per company; providers openai/anthropic/ollama/tesseract; `anthropic_provider.py` uses the SDK,
  no transcribe. Formula Studio + rule_assistant have their OWN OpenAI-compatible raw-requests stack
  (`pb_formula_studio.llm_*` config params). Coach `compose_enabled` is DB-global; its `_resolve_hook(question,
  screen_key, candidates)` (`learn_intent.py:749`) must return an intent KEY never text — same contract a command layer needs.
- Voice: MediaRecorder → `rpc_transcribe_voice` → Whisper (OpenAI only). No Web Speech API in the repo.

### Scope + period resolution
- Divisions `pb.division` (`pb_group/models/pb_division.py:55`); `_resolve_scope(kind, ref)` in
  `pb_pay/models/pb_pay_fairness.py:144` honours `_visible_divisions()`. Approval scope keys `scheme:X|division:Y`.
- Run wizard `vals` keys: name, date_start, date_end, formula_config_id, division, employee_ids, statuses, force_clean,
  search, spreadsheet_skipped. `get_defaults` `pb_payrun_wizard.py:404`; scheme cards :64; `_eligible_employees` :445
  (company-scoped); `_period_runs(ds, de, config)` :613 scheme-aware overlap guard; loose-slip adoption :655/:686.
- Demo schemes `DEMO_<DIV>_<END|MID>`, divisions retail/manufacturing/logistics/corporate/it/construction.
- **No pay-period model.** Period = date_start/date_end; "June 2026" → 1st..last day. Cut-off/payday rules live in
  `pb_blueprint/models/payday.py` (`cutoff_for` :117) + `blueprint_calendar.py:33–49`.
- No general fuzzy-name helper (difflib used ad hoc in Formula Studio :5783–5812).

### Reversibility today
- Undoable: approval bulk, Records Desk changes, mapping wire cut, formula save (versioned).
- **NOT undoable**: pay run delete (`hr_payslip_run.py:1265–1288`, blocks approval_pending/approved), delete draft slips
  :1290, discard empty run (`pb_payrun_wizard.py:1816`). State moves only via workflow (reject/send back/cancel/draft).
  → a command layer needs compensating actions (delete draft run, reject) not true undo.

### Run Payroll wizard + lifecycle (`pb_payrun_wizard`, `pb_payruns`)
- Wizard = AbstractModel `pb.payrun.wizard`, all `@api.model`. Steps period → [data] → compute → review.
  RPC chain the JS runs: `get_defaults()` :404 → `spreadsheet_gate(vals)` :1483 → `scheme_preview(vals)` :374 →
  `eligible_preview(vals)` :564 → `sync_plan/sync_step` :1195/:1217 → `prepare_run(vals)` :863 (may return
  `{needs_confirmation, kind:'exists'}`) → [`attach_spreadsheet` :1645] → `compute_batch(payload)` :945 in chunks of 40
  → `get_summary(run_id)` :1857. `submit_for_approval(run_id)` :1910 exists but UI uses the run's own
  `action_approval_submit()` (`hr_payslip_run.py:1048`). Legacy `create_and_compute` :747 ignores scheme/statuses.
- Inputs: name, date_start, date_end, formula_config_id, division (demo), statuses[], employee_ids[], file_b64/file_name,
  spreadsheet_skipped, force_clean. No cut-off / std days / pay date in the wizard.
- Guards: `_require_scheme` :330; scheme-aware duplicate `_period_runs` :613; loose-slip adoption :686; data-lane
  refusals :1230/:1306/:1693. Extensions: pb_demo (:188/:280/:367 division pin), pb_timesheet_approval (blocks only
  if company flag), pb_close + pb_young_worker add exception notes.
- Lifecycle: states draft → approval_pending → done (+cancel). **State seal** :546–569 (module-level `object()` token,
  unforgeable). `_compute_pb_perms` :498. Submit → `biz.approval.engine.submit` :842; decide via inbox facade
  `pb.approval.inbox.decide(request_id, step_key, action, reason, expected_lock_revision, idempotency_key)` :821 or
  `act(model, res_id, action, note)` :978; `get_request().can_decide` :439 = "may this user approve". Withdraw
  `_approval_withdraw` :1026. Reject `action_payslip_run_cancel()` :1146 (reason via ctx `pb_reject_note`).
  Delete `unlink()` :1265 refused if approval_pending or any slip not draft/cancelled. Pay & Deliver =
  `pb.pay.delivery` (`prepare_bank_file`/`download_bank_file`/`request_release`/`send_payslips`), gated by
  `_require_access` :32 (PAY_GROUPS) and routed through the engine.
- Other doors: Import `pb.import.wizard.create_and_load/do_validate/do_process`; Records Desk `preview_changes`
  → `apply_changes` (engine-routed) → `undo_apply`; contracts `save_contract_360` (engine-routed when money moves);
  new hire `pb.people.onboard.wizard`; filing `pb.filing.flow.start/scope/save_scope/generate`; pay bands/reviews.
- Audit: NO central who-did-what. Pieces: `biz.audit.entry` (field rules), `biz.approval.event`, `pb.records.change`,
  `pb.audit.console.get_stream` (`pb_audit/models/pb_audit_console.py:502`). hr.payslip.run is not a mail.thread;
  `pb_prepared_uid` is documented but never written.
- Access seams: `pb.access.passport(user_id)` :1480, `surface_access(rows, user_id)` :1511 (`biz_access/models/
  pb_access_facade.py`); `pb.sidebar.item.visibility_for(user)` :121. Groups officer/manager/super_admin/final_approver/
  integration (`pb_hr_payroll_base/security/payroll_base_security_enhanced.xml:77–176`). Run Payroll menu gated to
  officer/manager/super_admin (`pb_sidebar_data.xml:138–144`) — **UI only**.

### 🔴 Security holes found (must be closed in Phase 0, before any AI door)
1. `pb.payrun.wizard` has **no group/role check**; `prepare_run`/`compute_batch`/`attach_spreadsheet` run as **sudo**
   (:904, :961, :1700). Any authenticated session (incl. portal) can call them via `/web/dataset/call_kw`.
2. **Clean-and-Run** (`_clean_period` :717, called :902) deletes runs in ANY state as sudo — done, paid, approval_pending
   (forces draft, defeating the unlink guard; orphans the open approval request; resets+deletes posted journal entries).
3. Duplicate check not company-scoped (runs have no `company_id`; `_period_runs` :631 falls to an unscoped search).
4. No period validation (`date_start > date_end` accepted). 5. "historical/locked" branch dead (:763/:884).
6. ~19 "already approved" context switches are plain strings (`pb_contract_approved_write`, `pb_newhire_approved_write`,
   `pb_unlock_approved_write`, `pb_bands_approved_write`…) — forgeable from RPC; pay runs/imports use `object()` tokens.
7. No `ir.rule` on hr.payslip.run (every officer sees every company). 8. `action_send_email_all`, legacy bank export,
   `action_download_payslip_xlsx` skip routes / state checks. 9. PayAI pulse reads with sudo and shows everyone.

## Design — "PayAI does it" (working name; owner to name the feature)

### The one-sentence model
The AI never touches records. It chooses a **named Action from a server-owned catalogue**, fills the Action's **slots**,
the server **resolves and validates** every slot as the asking user, shows a **Plan card** (what will happen, with
counts from the same preview methods the screen uses), the person **confirms at the tier the Action requires**, the
server **executes the exact same methods the screen calls, as that user, never sudo**, writes a **task record** (audit),
and offers the Action's **compensating undo**.

### 1. Action catalogue (`payai.action` registry, Python)
One Python registry (decorator `@payai_action(key, tier, slots, …)` in a new module `pb_payai_actions`, depends on
pb_payroll_ai_insights + pb_payrun_wizard + pb_approval_config + pb_records + pb_hub). Each Action declares:
- `key`, `title`, plain-English `summary` template, `examples` (EN+VI phrasings — feed the LLM + "What can you do?")
- `tier`: `look` | `prepare` | `decide` | `money` | `never` (see §3)
- `slots`: typed, each with a server **resolver** (`period`, `scheme`, `division`, `employees`, `statuses`, `run`,
  `person`, `field`, `value`, `reason`, `file`) and `required`/`default_from`
- `gate(user)`: the SAME gate the screen uses (sidebar item key → `pb.sidebar.item.visibility_for`, plus method-level
  group/ACL; approvals use `pb.approval.inbox.get_request().can_decide`)
- `preview(params, user)` → facts for the Plan card (reuses `scheme_preview`, `eligible_preview`, `_period_runs`,
  `get_summary`, `bulk_no_approval_preview`-style counts)
- `execute(params, user, task)` → calls existing methods; long ones yield progress steps
- `undo(task)`: compensating action or `None` (card says "cannot be undone" up front)
- `open_in_screen(params)` → `openHub` target + prefill context (universal escape hatch)
Navigation Actions are **generated** from the existing `pb_hub_palette` registry (37 modules' doors) — the JS registry
is exported once to the server via a `/payai/doors` RPC at session start (or mirrored as Python data) so "open the
Runs board" costs nothing to add. The catalogue also emits the OpenAI/Anthropic **tools JSON schema** (replaces
the substring intent classifier for commands) and a **deterministic fallback** matcher (top phrasings) for when the
LLM is off or unavailable (same contract as `learn.intent._resolve_hook`: return a KEY, never text).

Phase-1 Action list (proposal):
| key | tier | wraps |
|---|---|---|
| open_screen | look | palette row → openHub |
| run_status / run_summary | look | `get_board_data`, `get_summary` |
| run_payroll | prepare | `get_defaults`→`scheme_preview`→`eligible_preview`→`prepare_run`→`compute_batch`(chunks)→`get_summary`; creates a **draft** run |
| submit_run | prepare | `action_approval_submit()` (withdraw = undo) |
| update_pay_data | prepare | Records Desk `preview_changes`→`apply_changes` (engine-routed; `undo_apply`) |
| download_run_excel | look | `action_download_payslip_xlsx` (+ add state check) |
| approve_item / send_back / reject_item | decide | `pb.approval.inbox.decide` with reason; typed confirm |
| send_payslips | prepare | `pb.pay.delivery.send_payslips` (engine-routed) |
| prefill_wizard ("fill this in for me") | look | opens Run Payroll with slots pre-filled; human presses Compute |
| clean_and_run, delete_run, delete_draft_slips, release_payment, bank file | **never** in v1 | — |

### 2. Slot filling = the wizard, collapsed into a conversation
- The LLM extracts slot **text** ("June", "Retail", "everyone except leavers"); the server **resolves** text → ids
  against the user's visible set only (schemes from `get_defaults().schemes`, divisions via `_visible_divisions()`,
  employees via `_eligible_employees`, periods via month/year parsing EN+VI → 1st..last day; cut-off/payday from
  `pb_blueprint` when present). A shared `payai.resolve` helper uses difflib + code/name/alias match, returns
  `{value, confidence, candidates[]}`.
- Rules: confidence ≥ 0.9 and unique → **assumed** (shown on the card as "assumed: Retail End-Month ✎");
  2–6 candidates → **ask with chips** (cards, never free text when the set is finite); 0 → say what exists.
  One question per turn. Defaults come from `get_defaults()` so AI and screen never disagree.
- The Plan card lists every slot with its origin (you said / assumed / default) — a wrong guess is visible before Do it.
- Everything the person types/says is **redacted** with the existing `ai_redaction` before it leaves the server
  (also fixes the current unredacted non-data paths).

### 3. Risk tiers (the "traffic light"), enforced server-side per Action
| tier | examples | confirm | undo |
|---|---|---|---|
| look | open, show, count, download | none | n/a |
| prepare | run payroll (draft), submit, update a value (routed), send payslips (routed) | Plan card + **one tap "Do it"** (voice "go ahead" allowed if the setting is on) | compensating: delete draft run (`unlink` guard holds), withdraw, `undo_apply`; offered on the card for 10 min |
| decide | approve / send back / reject as the seat holder | Plan card + **typed word** ("APPROVE") or re-auth; never by voice; reason captured | workflow only (send back) |
| money | bank file, release payment | **not available through PayAI** in v1 | — |
| never | clean-and-run, delete runs/slips, change access, settings | refused with "do this on the screen" + the door | — |
Extra rails: a plan is bound to user+session, expires after 10 min, is **re-validated at execution** (state may have
changed: "a June Retail run appeared since you asked"); one in-flight task per user; engine `idempotency_key` =
task id; a company-level **kill switch per tier** in Companion settings (default: look+prepare on, decide off,
tenants fully off until turned on, like `compose_enabled`).

### 4. Access = exactly the screen's rights, never more
- Every Action's `gate` runs as the user; execution never uses sudo. Pre-req **Phase 0** adds the missing server
  gates so the screen and the AI share them: `pb.payrun.wizard._require_runner()` (officer/manager/super_admin +
  create right on hr.payslip.run, or the demo group) on every public method; Clean-and-Run refused unless the run is
  draft with no approval request, and never on paid/done; company-scoped `_period_runs`; period sanity; state
  check on Download Excel; convert the string "approved_write" context switches to `object()` tokens.
- Multi-company: current company only; naming another company → "switch company first" with the door.
- Who may use it: same people who can do it on screen (recommended) — see owner question.

### 5. Execution + progress
- Chat client orchestrates `run_payroll` chunks exactly like the wizard (extract the wizard's compute loop into a shared
  JS helper `@pb_payrun_wizard/js/run_driver`), posting progress into the task record; the card shows "Computing
  160 / 412…", and a Learn-style "Open the run" door at the end. Browser must stay open (same as today's wizard).
- Server-side long jobs (cron) deferred to v2.

### 6. Audit: `payai.task`
Fields: user, company, utterance (redacted), action_key, params (resolved ids + labels), plan shown (json), tier,
confirm_kind (tap/typed/voice), confirmed_at, state (planned/confirmed/running/done/failed/undone/expired), result
refs (run_id…), undo_until, error. Written to `biz.audit.entry` summary + surfaced in `pb.audit.console.get_stream`
and on the Pay Run's history ("Prepared by PayAI for <user>"; also start writing `pb_prepared_uid`).

### 7. Voice
Keep: hold-to-talk → Whisper → transcript lands in the box (never auto-sent). Add: TTS read-back of the Plan card
when voice was used ("I'll run June payroll for Retail End-Month, 412 people. Tap Do it or say go ahead.");
spoken confirmation only for `prepare` tier and only if the company setting allows; `decide` always typed/tapped.

### 8. Surfaces
- The existing PayAI pill / Coach "ask" tab gains the Plan card, progress card, undo banner (clone matrix_room undo
  banner + Records Desk preview drawer styles; Lucide; locked palette; no gradients).
- ⌘K gets a "Ask PayAI to…" row that forwards the typed sentence.
- Every Plan card has "Open in the screen instead" (openHub + prefill) — and after a successful AI run, "Learn to do
  this yourself" → `learn.scenario.begin('payrun','watch')`.

## Owner decisions — 2026-10-12 (do not re-ask)
Design page shown: https://claude.ai/artifact/3t8BLmEm28WzzQehS5BsKa (file: scratchpad/payai-does-it.html → copy to
`docs/design/payai-does-it.html` + spec `docs/design/PAYAI_DOES_IT.md` in P0).
1. **Phased** Fable↔Opus workflow (Fable codes the P0 security kernel itself).
2. **Green + Amber + Red** allowed at launch (approve / send back / reject with typed word).
3. **Same rights as the screen.** Owner's explicit rail: *no back door* — a command must be refused whenever the
   corresponding screen is hidden or locked for that person under **Settings → Access and delegations** (biz_access),
   including lent/delegated roles. Gate = `pb.access.surface_access()` / `pb.sidebar.item.visibility_for(user)` on the
   Action's screen key **AND** the method-level group/ACL/engine-seat check. Both must pass; neither alone.
4. **In the chat with an escape hatch**: progress in chat + "Open in the screen instead" (pre-filled) on every card.
5. **English first; Vietnamese in the last phase.**
6. **Amber confirm = one tap; spoken "go ahead" allowed when the company switch is on.** Red = typed word, never voice.
7. **First release commands**: core six (run payroll, send for approval, open any screen, run status, download Excel,
   change a pay value) **+ approve/send back/reject + send payslips + government filing.**
8. **Security fix first, on ALL databases** (payobook, rize, payobook_template, abm), clone-rehearsed.
Pre-decided (owner did not object): keep OpenAI key (Anthropic provider exists for later); lives in the existing PayAI
pill + Coach "ask" tab; payobook.com first, tenants' tier switches off until asked; no "Odoo" in any string.

### 9. Phasing (locked)
Program docs: `docs/handovers/payai/PAYAI_PROGRAM.md` (verified facts above, verbatim design bar), handovers
`P1_…P4_HANDOVER.md`, shared ledger `PAYAI_LEDGER.md` (PA1…), reports `P*_REPORT.md`. Memory file `payai-does-it-program.md`.
- **P0 Hardening — Fable codes it (security):** `pb.payrun.wizard._require_runner()` on every public method (officer/
  manager/super_admin + hr.payslip.run create right, or demo group; portal refused); Clean-and-Run only when every
  existing run is draft with no open approval request, never done/paid, audited; company-scoped `_period_runs`;
  period sanity (start ≤ end, ≤ 1 year); `action_download_payslip_xlsx` state check; `action_send_email_all` routed or
  gated; convert the ~19 string "approved_write" context switches to module-level `object()` tokens; pulse reads
  without sudo (or filtered by the asker's access); redact the message on knowledge/onboarding/general paths; fix
  Anthropic system-prompt overwrite; `get_active_config` honours purpose. Tests per fix. Clone rehearsal → all DBs.
- **P1 Foundation + Green (Opus):** new module `pb_payai_actions` (depends pb_payroll_ai_insights, pb_hub, pb_sidebar,
  biz_access, pb_payruns, pb_payrun_wizard, pb_approval_config, pb_records, pb_pay_delivery, pb_govt_reports);
  `@payai_action` registry + tools-schema emitter + deterministic fallback matcher; slot resolvers (period, scheme,
  division, person, run, field/value, reason, country/filing); **gate = Access-home visibility + method gate**;
  `payai.task` model + audit-console stream row + run history line; Plan card / progress / undo / blocked card
  components in the pill AND the Coach ask tab (clone matrix_room undo banner + Records Desk preview drawer);
  "What can you do?"; Actions: open_screen (generated from `pb_hub_palette` rows), run_status, download_run_excel;
  company tier switches (Green/Amber/Red/voice-go-ahead) on a "PayAI actions" settings card; ⌘K "Ask PayAI to…" row.
- **P2 Amber (Opus):** run_payroll (shared `run_driver` extracted from the wizard JS; chunked compute with progress;
  needs_confirmation → blocked branch; re-validate at Do it; 10-min expiry; undo = delete draft run), prefill_wizard
  escape hatch (wizard `prefill(vals)` seam), submit_run (undo = withdraw), update_pay_data (Records Desk preview →
  apply; undo_apply), send_payslips, filing_prepare (`pb.filing.flow` start→scope→generate); TTS read-back when voice
  was used; spoken "go ahead" behind the company switch.
- **P3 Red (Opus):** approve / send_back / reject via `pb.approval.inbox.get_request().can_decide` + `decide(...)`
  with typed word (server verifies the word + idempotency key), reason capture, seat re-check at confirm; never voice;
  audit; "Learn to do this yourself" → `learn.scenario.begin(key,'watch')`.
- **P4 Vietnamese + closeout (Opus):** VI phrasings/resolver aliases (month names, scheme names), vi_VN.po for every
  new string (PO parse gate), Learn lesson "Ask PayAI to do it", tenant switch docs, CLOSEOUT.md.
- Later (not in this program): chained requests, server-side long jobs, new hire / contract change Actions.

## Verification (every phase)
- Numbered test cases in each handover; Odoo unit tests per Action (gate refused for employee/portal; wrong-company
  scheme refused; expired plan refused; re-validation stops on a newly created run; typed word mismatch refused; voice
  cannot confirm Red; every task leaves a `payai.task` row).
- Browser walk with the QA login on payobook.com (Chrome MCP, console clean): each example sentence from the design
  page, each persona (officer / approver / employee), Undo, "Open in the screen instead", blocked card.
- Deploy: tiered rule; P0 = risky (backups, clone rehearsal, all DBs); P1–P4 payobook first, PENDING.md for others.
- Report-back per phase scores itself against the design bar (hero moment = the plan card; zero dead-ends).
