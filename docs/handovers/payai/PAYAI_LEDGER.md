# PAYAI DOES IT — conventions & gotcha ledger

Every handover in this program references this file. Add a row whenever a new gotcha is hit.
Program doc: `PAYAI_PROGRAM.md` (verified plumbing, design, owner decisions). Design page:
https://claude.ai/artifact/3t8BLmEm28WzzQehS5BsKa (file copy `docs/design/payai-does-it.html`).

## Standing rules (bind every phase)
- **PA-R1 No back door (owner, 2026-10-12).** An Action is refused whenever the matching screen is hidden or
  locked for the person under Settings › Access and delegations (biz_access), lent roles included. Gate =
  `pb.sidebar.item.visibility_for(user)` / `pb.access.surface_access()` on the Action's screen key **AND** the
  method-level gate (group / ACL / engine seat). Both must pass.
- **PA-R2 Never sudo in an Action.** Execute calls the same methods the screen calls, as the asking user.
- **PA-R3 The AI emits text, the server resolves ids.** Never trust a model-produced id; resolve names against the
  user's visible set only (schemes from `get_defaults().schemes`, divisions via `_visible_divisions()`).
- **PA-R4 Plain English on every card, toast and refusal.** No "Odoo", no code words (see CLAUDE.md rules).
- **PA-R5 Design bar verbatim** (design-mandate): extreme WOW, hero moment = the plan card, zero dead-ends,
  motion with purpose, Lucide icons, locked indigo palette.

## Ledger
| # | Date | Gotcha / fact | How to apply |
|---|---|---|---|
| PA1 | 2026-10-12 | `pb.payrun.wizard` is an AbstractModel → no ACL row ever applies; its public methods were callable by any authenticated session and ran sudo. | Every public method carries `@runner_only` (`_require_runner()`); any NEW wizard method must too. pb_demo's overrides that do not call `super()` call `_require_runner()` + `_check_period()` themselves. |
| PA2 | 2026-10-12 | Odoo's `_pre_dispatch(rule, args)` runs BEFORE `request.params` is set for JSON-RPC, and `get_json_data()` re-parses the body — mutating there is lost. | Scrub request parameters in `ir.http._dispatch(endpoint)` (biz_approval_workflow/models/ir_http.py): `request.params` is the very dict the endpoint receives. |
| PA3 | 2026-10-12 | Twelve `*_approved_write` context switches are plain strings read with `context.get(KEY)`; a client could send one. Pay runs / imports use `object()` tokens. | Closed at the door (PA2). **Debt:** convert each switch to an `object()` token like `_PB_CHAIN_TOKEN` (hr_payslip_run.py:59) — ~40 call sites across ~20 modules. |
| PA4 | 2026-10-12 | `hr.payslip.run` has no `company_id` on this build; `_period_runs` fell to an unscoped search, so another company's scheme-less month read as "already exists" (and was what Clean-and-Run would clear). | Scope by the slips' companies (`_period_runs`). Any duplicate check on runs must do the same. |
| PA5 | 2026-10-12 | Clean-and-Run cancelled done payslips, reset posted journals and deleted paid/pending runs, as sudo, unlogged. | `_clean_blockers(runs)` → `prepare_run` answers `{'blocked': True, 'kind': 'protected'}`; `_clean_period` re-asks and raises; the JS shows the message (no Clean button). Demo runs (`is_demo`) stay clearable. |
| PA6 | 2026-10-12 | `rpc_get_active_alerts` returned sudo-read payroll figures to every internal user (all are PayAI users). | Reader needs `hr.payslip.has_access('read')`. Any PayAI RPC that returns payroll facts must check the READER's rights, never the detector's. |
| PA7 | 2026-10-12 | Anthropic provider overwrote `system` on each system turn → screen note replaced the product prompt. | System turns are concatenated. Multi-system-message prompts are fine on both providers now. |
| PA8 | 2026-10-12 | `get_active_config` ignored `purpose`; an active Tesseract/OCR row could be handed to the chat. | Prefer `purpose='insights'`, never `tesseract`. |
| PA9 | 2026-10-12 | PayAI knowledge / onboarding / general paths sent the raw message unredacted; only the data path redacted. | All four paths redact the message with the conversation mapping and restore placeholders in the answer. |
| PA10 | 2026-10-12 | No local Odoo install — tests run on the server (`Payobook19v2`) against a clone DB. | Rehearse on a clone (`p9clone`-style) before real DBs; `--test-enable` always with `--http-port` ≠ 8069 (ledger F6). |
| PA11 | 2026-10-12 | On the `payobook_template` clone, 8 PRE-EXISTING test failures: `pb_payrun_wizard/tests/test_two_schemes_one_month.py` (6× `hr_formula_config.country_code` NOT NULL — the fixture predates the required country) and 3 vi_VN "copy ships in Vietnamese" tests in pb_payroll_ai_insights (`test_data_access.test_06`, `test_egress.test_04d/04e`). Not caused by P0. The two-schemes fixture was fixed in P0 (`country_code: 'VN'`); the 3 vi_VN tests remain. | Read the clone log with the 3 vi_VN failures filtered out; they are a translation-catalogue debt, not this program's. |
| PA12 | 2026-10-12 | Odoo test envs run as superuser (`env.su` True): a gate that short-circuits on `env.su` says yes to every explicit `user` you pass it. | Judge the explicit user on their own rights (`with_user(user)` drops su); keep the su short-circuit only in the no-argument `_require_runner()`. Same trap applies to every P1+ gate test — always call gates `with_user(...)`. |
| PA13 | 2026-10-12 | Only "Payroll Manager" holds `create` on `hr.payslip.run` by ACL; Payroll Officer has read+write only and creates runs through the wizard's sudo. | The wizard door = RUN_GROUPS **or** create right; an Access-home role that should run payroll must either imply an officer/manager group or grant create on runs. |
| PA14 | 2026-10-12 | The permission checker blocked writing/running a live-server deploy script until the owner said "go ahead" in the session; after that it went through. | Ask the owner for the go-ahead before each live deploy of this program; clone test runs and staging to `/tmp` are always allowed. Opus agents never deploy. |
