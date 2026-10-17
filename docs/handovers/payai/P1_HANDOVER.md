# PAYAI P1 — Foundation + Green tier (handover for Opus)

Program: `PAYAI_PROGRAM.md` (read "Verified plumbing" + "Design" first). Ledger: `PAYAI_LEDGER.md` (PA-R1…R5 bind
this phase; add a PA row for every gotcha you hit). Design page: https://claude.ai/artifact/3t8BLmEm28WzzQehS5BsKa
(file `docs/design/payai-does-it.html` — open it in a browser; the "Open the Runs board" and the refusal cards are
this phase's hero; the plan card look is the target for P2). Owner decisions are final; do not re-ask them.

## Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment: the **plan card** — a stranger
reads it and knows exactly what will happen. Zero dead-ends: every state (no command matched, no right, expired,
provider down) names its reason and its next step. Plain language on every label (CLAUDE.md plain-English rule;
never the word "Odoo"). Motion with purpose (card enters, progress fills, undo counts down). Lucide icons, locked
indigo palette (`#5A4BB0`, soft `#EDEAF8`, semantic ok `#2E7D4F` / warn `#D97706` / bad `#DC2668`), no gradients,
no emoji. Measured against Linear/Notion AI, not against stock Odoo. Score the phase report against this bar.

## Scope (P1)
1. New module **`pb_payai_actions`** (19.0.1.0.0). Depends: `pb_payroll_ai_insights`, `pb_hub`, `pb_sidebar`,
   `biz_access`, `pb_payruns`, `pb_payrun_wizard`, `pb_audit`. (Later phases add pb_approval_config, pb_records,
   pb_pay_delivery, pb_govt_reports.) White-label rule applies to every string.
2. **Action catalogue** (`payai/actions.py`): Python registry with decorator `@payai_action(...)`; each Action
   declares `key, title, tier, summary, examples, slots, screen_key, gate, preview, execute, undo, open_in_screen`
   (see §Architecture). Emits (a) the LLM tools schema, (b) the deterministic fallback phrase table, (c) the "What
   can you do?" list.
3. **Slot resolvers** (`payai/resolve.py`): `period`, `scheme`, `division`, `run`, `door` (+ `person` stub for P2).
   Return `{status: resolved|ambiguous|missing, value, label, origin, candidates[]}`; never an id the user may not see.
4. **The gate** (`payai/gate.py`) — PA-R1: `allowed(user, action)` = Access-home visibility of the Action's
   `screen_key` **AND** the Action's own method-level check. Both. Refusal text in plain words with the door.
5. **`payai.task`** model (audit) + rows in the Audit console stream + "Prepared by PayAI" is NOT this phase (P2).
6. **Chat integration**: `rpc_send_message` → when the classifier says `command`, the engine calls the catalogue →
   response carries `card` JSON; the pill AND the Coach "ask" tab render **Plan card / Done card / Blocked card /
   Refused card / Clarify (chips)**. "Do it" for Green = immediate (no confirm) — Green cards show as a one-line
   "Opening Pay › Runs" done card, not a plan card.
7. **Green Actions**: `open_screen` (every ⌘K door), `run_status` (one run or "this month"), `download_run_excel`
   (done runs only — the native form's draft download is untouched), `what_can_you_do`.
8. **Company switches**: `res.company` fields `payai_tier_look`, `payai_tier_prepare`, `payai_tier_decide`,
   `payai_voice_go_ahead` (booleans; defaults look=True, prepare=True, decide=True on `payobook`; ALL False on every
   other database by a migration/`post_init` that checks the db name ≠ 'payobook' — tenants start off). Settings card
   "PayAI can act" in the Settings hub (precedent in §UI seams). Owner decision: tiers Green+Amber+Red on for payobook.
9. ⌘K row "Ask PayAI to…" (pb_hub palette entry, sequence 90) that opens the pill with the typed text.
10. Tests (numbered below), vi_VN.po NOT required this phase (P4), but every string goes through `_()`.

## Binding non-goals (P1)
- No Amber/Red execution: the catalogue may DECLARE `run_payroll` etc. as stubs with `tier` set, but `execute` raises
  `NotImplementedError` and the gate returns "coming soon" cards only in debug mode — in normal mode such a sentence
  gets the honest "I cannot do that yet; here is the screen" refusal with the door. No slot-filling conversation
  beyond one clarify turn for Green slots.
- No voice changes. No Vietnamese. No server-side long jobs. No changes to the approval engine.
- Do not touch `pb.payrun.wizard` methods (P0 just hardened them) except to READ via the public `get_defaults()`.
- Never sudo inside an Action (PA-R2). Never trust a model-produced id (PA-R3).

## Verified plumbing (do not re-derive; file:line in PAYAI_PROGRAM.md)
- Engine entry `payroll.ai.engine.process_message(message, conversation_history, context)`
  (`pb_payroll_ai_insights/models/payroll_ai_engine.py:349–416`); classifier `_classify_intent` :500–535 (LLM,
  substring match over `payroll_data|knowledge|onboard|general`); RPC `payroll.ai.conversation.rpc_send_message(
  message, session_id=None, screen=None)` :223 returns `{response, chart, insights, follow_up_questions, session_id,
  intent, drilldown_model, action}` :272–281. `screen` = `{tag, xml_id, model, name, hub, tab}` from the client's
  `_currentScreen()` (`ai_insight_chat.js:228–240`).
- Action whitelist precedent: `_sanitize_action` :803–846 → frontend `runAction` (`ai_insight_chat.js:270–294`) opens
  a hub via `openHub(actionService, {xmlid, lens, focus})`. **Extend this envelope**: add `card` beside `action`.
- Providers: `ai_providers/openai_provider.py:60–85` (`chat.completions.create`, no tools yet);
  `anthropic_provider.py:75–91`. Add a `generate_tools(messages, tools, …)` method to the base provider that returns
  `{tool_name, arguments}` or None — OpenAI `tools=[…], tool_choice="auto"`; Anthropic `tools=[…]` with
  `input_schema`. Fallback when the provider lacks it or is off: the deterministic phrase table.
- Redaction: `ai_redaction.redact_text(text, mapping)`, `restore_deep` — the command path must redact the message
  exactly like the other paths (PA9) and must never put a person's name into the tools call unredacted.
- Doors: the app-wide ⌘K registry `registry.category("pb_hub_palette")` rows `{id,label,sublabel,icon,group,
  action:{tag}|{xmlid},lens,lensKey,groups,requires}` (`pb_hub/static/src/js/hub_palette_entries.js:1–20`),
  filtered for the user by `hub_palette_service.js:137–160`, run by `run(id)` :183–216 → `openHub(...)`
  (`pb_hub/static/src/js/hub_nav.js:45–85`). Rows live in ~37 `*_palette.js` files; e.g. `payhub_runs` →
  `{tag:"pb_pay_hub", lens:"runs"}`. **Mechanism for P1**: the chat client sends the user's VISIBLE palette rows
  (`id, label, sublabel, group`) with `rpc_register_doors(session_id, rows)` when the pill mounts (and again when
  the palette registry changes); the server stores them on the conversation (`doors_json`) and resolves the `door`
  slot against them. The server returns `{card:{kind:'done', door_id}}`; the client runs the palette row by id
  (same code path as ⌘K). Server-side re-check: the door's `groups` are included in the rows; refuse when the user
  holds none of them (defence in depth — the client list is already filtered).
- Access home: `pb.sidebar.item.visibility_for(user)` (`pb_sidebar/models/pb_sidebar.py:121`) → `{items:{id:
  on|locked|hidden}, sections}` — Python-to-Python, takes a `res.users` recordset; `pb.access.surface_access(rows,
  user_id)` (`biz_access/models/pb_access_facade.py:1511`) → `{key:{allowed,parent}}`. Each Action's `screen_key`
  names a `pb.sidebar.item` xmlid (e.g. `pb_sidebar.item_run_payroll`, or the hub item for the Pay hub) — resolve
  via `self.env.ref(screen_key)` and read its state from `visibility_for(user)`; `locked` or `hidden` ⇒ refuse.
- Run facts: `pb.payruns.get_board_data()` (`pb_payruns/models/pb_payruns.py:42`, `@api.model`) per-run
  `can_act, can_reject, awaiting_me, approval, delivery, history`; run states `draft/approval_pending/done/cancel`;
  `hr.payslip.run.action_download_payslip_xlsx()` (`om_hr_payroll/models/hr_payslip.py:1261`, recordset, done-only
  on the board). `pb.payrun.wizard.get_defaults()` (`pb_payrun_wizard.py`) → `schemes[cards]`, `formula_config_id`,
  `date_start/date_end` (P0: now gated by `@runner_only` — call it only inside Actions whose gate already passed).
- Scope: divisions `pb.division` (`pb_group/models/pb_division.py:55`); period = `date_start/date_end`, no period
  model; "June 2026" ⇒ 2026-06-01..2026-06-30 (`calendar.monthrange`).
- Audit console: `pb.audit.console.get_stream` (`pb_audit/models/pb_audit_console.py:502`, manager gate :74),
  sources list :147–156 — add `payai.task` there.
- Company switch precedent: `res.company.pb_timesheet_block_run` (pb_timesheet_approval) — company fields, not
  config parameters. Settings hub lenses: `pb_settings_hub` (`company` lens). pb_learn "Companion settings" is a
  TransientModel settings screen (`pb_learn/models/learn_companion.py:56–115`) — DB-global; do NOT copy that shape
  for per-company switches.
- Test fixtures: `pb_payroll_ai_insights/tests/test_p0_gates.py` (users with/without payroll groups),
  `pb_payrun_wizard/tests/test_p0_runner_gate.py`. Tests run on the server clone (PA10) — never `--test-enable`
  on port 8069.

## Architecture
```
pb_payai_actions/
  __manifest__.py           depends above; assets: web.assets_backend (cards js/xml/scss)
  models/__init__.py
  models/payai_task.py      payai.task (audit)   — see schema
  models/res_company.py     the four switches + settings card RPC
  models/payai_conversation.py  inherit payroll.ai.conversation: doors_json, rpc_register_doors, rpc_confirm_task
  models/payai_engine.py    inherit payroll.ai.engine: command path hooked BEFORE _classify_intent
  payai/__init__.py
  payai/registry.py         @payai_action, ACTIONS dict, tools_schema(), phrases(), describe()
  payai/gate.py             allowed(env, user, action) → (ok, reason, door)
  payai/resolve.py          resolvers
  payai/actions_green.py    open_screen, run_status, download_run_excel, what_can_you_do
  payai/actions_stubs.py    run_payroll, submit_run, update_pay_data, send_payslips, filing_prepare,
                            approve_item, send_back, reject_item (tier set, execute = NotImplemented)
  security/ir.model.access.csv   payai.task: user rw own (rule), manager read all
  security/payai_security.xml    record rule "own tasks"; manager sees company tasks
  data/palette.xml? (no — palette rows are JS) static/src/js/payai_palette.js  "Ask PayAI to…" row
  static/src/js/cards/*.js + xml/cards.xml + scss/cards.scss   PlanCard, DoneCard, BlockedCard, ClarifyChips
  static/src/js/chat_patch.js    patch AiInsightChat (and the embedded variant): render `card`, send doors,
                                 confirm/undo RPCs, run door by id
  views/res_company_settings.xml  (or the hub lens card — follow the precedent found)
  tests/…
```
**Flow (Green):** message → `payai_engine.process_message` override: if `company.payai_tier_look` is off → super().
Else build tools schema from ACTIONS visible to this user (gate pre-filter, so the model is never offered a door the
user lacks) → `provider.generate_tools(redacted_messages, tools)`; if a tool call comes back → `registry.run(key,
arguments, user, screen, task)`: resolve slots → if any `ambiguous` → **Clarify card** (chips, ≤6, one question) →
else gate → preview → for Green: execute immediately, write `payai.task` (state done) → **Done card** (one line +
door button). No tool call → fall through to super() (today's behaviour) — the command path must never make a
question-answer worse. Provider unavailable → deterministic phrase table (regex over `examples`) → same path.

**Clarify round-trip:** chips post back `{"text": "<label>", "resolve": {"task_id": N, "slot": "door", "value":
"<candidate id>"}}` via `rpc_send_message(message, session_id, screen, resolve=...)` (new optional kwarg); the server
re-runs the pending task with that slot pinned (origin `chose`). A pending task expires after 10 minutes
(`expires_at`), after which the chips answer "That question has expired, ask me again".

**`payai.task` schema:** `user_id, company_id, session_id (conversation), utterance (redacted), action_key, tier,
params_json (resolved: value+label+origin per slot), plan_json (card as shown), state
(planned|clarify|confirmed|running|done|failed|refused|undone|expired), confirm_kind (none|tap|typed|voice),
confirmed_at, expires_at, result_json (ids + labels), undo_until, error (plain text), create_date`. `_description`
"PayAI request". Chatter not needed. Index on `(user_id, create_date)`.

**Card JSON contract** (server → client; keep it the ONLY thing the client interprets):
```
{kind: 'plan'|'done'|'blocked'|'refused'|'clarify',
 task_id, tier: 'look'|'prepare'|'decide'|'never', title, subtitle,
 slots: [{key, label, value_label, origin: 'said'|'chose'|'assumed'|'default', editable: bool}],
 notes: [{tone: 'ok'|'warn'|'bad'|'info', text}],
 actions: [{id: 'do'|'open'|'cancel'|'door'|'undo'|'learn', label, style: 'primary'|'outline'|'ghost',
            door_id?, hub?: {tag|xmlid, lens, focus}}],
 chips: [{label, sublabel, value}],            # clarify only
 progress: {done, total, label}?,              # P2
 result: [{value, label}],                     # done
 undo: {until_iso, label}?,                    # P2
 audit_line: "Recorded: …"}
```
The client never decides a tier or a right; it renders what it is given and calls back by `task_id`.

## Green Actions — exact behaviour
| key | screen_key / gate | slots | execute | card |
|---|---|---|---|---|
| `open_screen` | the door's own `groups` (from the registered row) | `door` (resolve against doors_json: label/sublabel/id fuzzy, difflib ≥0.6; ambiguous → chips) | none server-side; Done card with `actions:[{id:'door', door_id}]` the client runs | done: "Opening Pay › Runs." |
| `run_status` | `pb_sidebar.item_pay_runs` or the Pay hub item (whichever is active) AND `hr.payslip.run.has_access('read')` | `run` (period month + optional scheme name; "this month" default; resolve via `hr.payslip.run` search over date range as the user) | read `get_board_data()` rows for the run(s) | done: result tiles (people, net via `pb_pay_totals` — ONE PAY-BAND RULE memory, state, awaiting whom) + door to the run |
| `download_run_excel` | same as run_status AND run.state == 'done' | `run` | returns the report action from `action_download_payslip_xlsx()` as `actions:[{id:'door', report_action}]` | done: "Here is the Excel for Payroll June 2026." Draft run → refused card "available once approved" |
| `what_can_you_do` | none | — | `registry.describe(user)` (only Actions whose gate passes) | done: grouped list by colour |

## Refusals (every one is a card, never a toast)
- No right: "Running payroll is for payroll staff. Your sign-in does not have the Run payroll right; ask your
  administrator under Settings › Access and delegations." + door to Access home if the user can see it.
- Screen locked in Access (locked/hidden): "That screen is not switched on for you." + the same door.
- Tier switched off for the company: "PayAI can look, but is not allowed to do this here yet. An administrator can
  switch it on under Settings › PayAI can act."
- Not a command / nothing matched: fall through to the normal answer; append chips "What can you do?".
- Stubbed Amber/Red sentence: "I cannot run payroll for you yet — that arrives in the next release. Here is the
  screen, filled in as far as I can." (door only; no prefill in P1).

## Safety rails to implement now (they are cheap and P2 relies on them)
- One pending (clarify) task per user; starting a new one expires the old.
- `expires_at` = now + 10 min on every task; any callback on an expired task → "expired" card.
- Task is bound to `user_id` + `session_id`; a callback from another user → AccessError.
- Every refusal and every done writes a `payai.task` row (state refused/done) — the audit must show the asks that
  were refused too.
- Redact the utterance before storing (`redact_text` with the conversation mapping).

## UI seams (verified 2026-10-12; file:line)
**Chat client** `pb_payroll_ai_insights/static/src/components/ai_insight_chat/`
- `ai_insight_chat.js`: state :46–70 (`messages`, `isLoading`, `inputText`, `sessionId`, `showSuggestions`);
  `sendMessage` :159–220 — user push :169–175, RPC :182–187 (`{silent:true}`), assistant push :192–202 (`{role,
  content, chart, insights, followUpQuestions, drillDownModel, intent, action, timestamp}`) → **add `card:
  result.card || null` here** and in `_loadHistory` :668–686 (assigns `result.messages` straight — history must
  carry `card` too); `sendSuggestion(text)` :153–157 (chips); `runAction` :250–295 (only open_lesson /
  open_walkthrough; `openHub` import :13, `hubPlace` :12); `closePanel`.
- `AiInsightChatEmbedded extends AiInsightChat` :723–775 — own template, `embedded=true`, props `close?, handoff?`;
  registered `pb_helper_tabs` → `ask` :777–782 with `groups:["pb_payroll_ai_insights.group_payai_user"]`.
> ONECHAT update (2026-10-14): the helper drawer is now ONE chat called PayAI — no Guide me / Ask / Practice tabs and no "Your next step"; a router decides where each sentence goes (`docs/handovers/onechat/ONECHAT_HANDOVER.md`).
- `ai_insight_chat.xml`: the two variants do NOT share markup. Floating: messages loop :88 (`payai-message
  payai-msg-<role>`, text :109, chart :112–123, insights :126–138, "Show me" :144–149 `payai-coach-action`,
  follow-ups :152–161). Embedded: loop :323 (`payai-embed-msg me|ai`), action button :345–351 `payai-embed-action`.
  **Put the card in ONE sub-template** (`pb_payai_actions.Card`) and `t-call` it from both loops right after the
  text; a third variant `ai_insight_chat_full.js/.xml` (client action `payai_chat_full`) does not copy `action` —
  leave it (not in scope) but do not break it.
- SCSS `ai_insight_chat.scss`: floating styles use Sass vars (:7–22, `$primary-color #4F46E5` — legacy, do NOT
  reuse; the card uses the locked palette tokens); embedded :1015–1234 uses `--vuf-*` CSS vars (`--vuf-primary`,
  `--vuf-primary-soft`, `--vuf-line`, `--vuf-surface`, `--vuf-ink`, `--vuf-muted`). Card SCSS lives in the new
  module, scoped `.payai-card`, tokens from `--vuf-*` with the design-system fallbacks.
- Coach drawer: `pb_learn/static/src/coach/coach.xml:101–102` mounts the embedded chat; usable width ≈ 480−24 px
  (`coach.scss:582–585`), mobile ≤640 px full width (:378–385). Design the card for 300–456 px.

**Server**
- `payroll_ai_conversation.py`: `rpc_send_message` :222–281 (return keys :272–281); `add_message(role, content,
  chart_config=None, insights=None, intent=None)` :142–152; `get_history` :154–168 returns `{role, content, chart,
  insights, timestamp, intent}` — `action` is NOT persisted today. **Add** Text field `card` (JSON) on
  `payroll.ai.message` (:455–489), a `card=None` kwarg on `add_message`, `'card'` in `get_history` and in the
  `rpc_send_message` return. Never reuse `chart_config` (it feeds ChartRenderer and pin-to-dashboard).
- Engine `_sanitize_action` :806 whitelists action types — the card is a NEW key beside `action`, not a new type.

**Doors** — `pb_hub/static/src/js/hub_palette_service.js`: NO public listing API today; filtering is the private
`resolveEntries()` :225–260 (present → feature → `user.hasGroup` any-of → `{id,label,sublabel,icon,restricted,
group}`), `run(id)` :262–305 private; service returns `{open, close, isOpen}` :335. **Expose** `entries()` (=
resolveEntries) and `run(id)` on the service's return object (pb_hub bump) and use them from `chat_patch.js`.
`openHub` → `import { openHub } from "@pb_hub/js/hub_nav"` (`hub_nav.js:52`; opts `tag|xmlid, lens, lensKey,
focus, back, context`). ⌘K row: add to `pb_payai_actions/static/src/js/payai_palette.js` via
`registry.category("pb_hub_palette").add("payai_ask", {...}, {sequence: 90})` whose action opens the pill with the
query text (the pill is a `main_components` instance — expose `window.__payai_open(text)`-free: use a
`registry.category("pb_payai").add("open", fn)` hook the pill registers on mount).

**Company switches** — precedent `pb_timesheet_approval/models/res_company.py:19–42` (Booleans on `res.company`,
`related` on `res.config.settings` :36–42; view `views/res_config_settings_views.xml:18–22` `<setting id=…>`).
Settings hub cards only LINK (`pb_settings/static/src/js/settings_hub.js`, extension
`registry.category("pb_settings_category").add(key, {key, icon, label, blurb, groups, cards:[{id, tag|xmlid, icon,
label, sub}]}, {sequence})` :246–275). **Do:** `res.company` fields + `res.config.settings` related fields + a
"PayAI can act" `<setting>` block; plus a Settings-hub card under category `company` pointing at the settings
action. The toggles' plain labels: "PayAI may look (open screens, show figures)", "PayAI may prepare (draft runs,
send for approval, change values)", "PayAI may decide (approve, send back, reject)", "A spoken 'go ahead' counts
for Amber". Help text in plain words; never "Odoo".

**Undo banner / drawer precedents** — `pb_approval_config/static/src/xml/matrix_room.xml:168–179`
(`.pbam-attn.pbam-attn-green.pbam-bulkdone` + ghost Undo + `.pbam-x`), JS `matrix_room.js:459–480`; SCSS tokens
`--pbim-green(-soft)`, `--pbim-amber(-soft)`, `--pbim-rose(-soft)` (`approval_matrix.scss:96–109`, rise animation
:1140). Records Desk drawer markup `records_desk.xml:680–705` (`.rd-drawer` 466 px, `records_desk.scss:456–480`).
Clone the tone classes, not the components.

**Audit stream** — `pb_audit/models/pb_audit_console.py`: add `payai` to `_SOURCE_META` :55–63, `_SOURCE_ORDER`
:65–66, `_source_available` :147–156, a `_fetch_payai(filters, limit)` returning `self._row(...)` (pattern
`_fetch_delivery` :329–355; row shape :123–144), `_FETCHERS` :383–391, `_source_date_field` :701–710; frontend
chips `pb_audit/static/src/js/pb_audit.js:17–25`. Row title = "Asked PayAI: <action title> — <state>".

**Run history (P2, noted now)** — `pb_payruns/models/pb_payruns.py:335–385` `_history` builds `[[sentence,
date]]`; first line "Prepared by %s" :343–346 from `pb_prepared_uid` (P0 now writes it). P2 adds a marker
`pb_prepared_via = 'payai'` on `hr.payslip.run` and the sentence "Prepared by <name> through PayAI".

## Numbered test cases (Odoo tests, `pb_payai_actions/tests`)
1. Registry: every Action has key/tier/title/screen_key; tools schema is valid JSON schema; stubs are not offered
   to the model (`tools_schema(user)` excludes tier prepare/decide in P1).
2. Gate: officer passes `run_status`; plain internal user (no payroll group) is refused with the Access-home text;
   portal user refused; a user whose sidebar item is `locked` via Access (simulate by removing the group / using
   `visibility_for`) is refused even if the ACL would allow — the "no back door" test.
3. Company switch off (`payai_tier_look=False`) → command path skipped, super() answer returned.
4. `open_screen` resolves "runs board" → `payhub_runs` from registered doors; "runs" with two candidates → clarify
   card with ≤6 chips; chip callback with `resolve` pins the slot (origin `chose`) and returns a done card.
5. Doors a user does not hold (groups not held) are refused server-side even if sent by the client.
6. `run_status` for "June 2026": resolves the month, finds the run as the user, tiles contain count + net; a draft
   June run for a user without read on runs → refused card.
7. `download_run_excel` on a draft run → refused; on a done run → report action in the card.
8. Expiry: a clarify task older than 10 minutes answers "expired".
9. Audit: refused + done both create `payai.task` rows with the redacted utterance; a second user cannot read the
   first user's task (record rule); payroll manager can.
10. Provider off (`get_active_config()` empty): the phrase table still resolves "open the runs board".
11. Redaction: a sentence containing an employee name reaches `generate_tools` redacted (`[person-n]`).
12. Non-command message ("what is gross pay") → unchanged knowledge answer plus the "What can you do?" chip.

## Browser walk (Chrome MCP, payobook.com, QA login — mandatory, console clean)
Pill and Coach ask tab: "Open the Runs board" → done card → the board opens; "Open runs" → chips → pick → opens;
"What can you do?" → grouped list; "Show the June run" → tiles + door; "Run June payroll for Retail" → honest
stub refusal with the door; a sentence with no command → normal answer. Switch `payai_tier_look` off in the settings
card → the same sentence falls back to the plain answer. Phone width (400px) card layout.

## Deploy (normal tier, payobook only — PENDING.md row for the others)
New module install `-i pb_payai_actions` on payobook; `-u pb_payroll_ai_insights` if touched. Asset purge +
`web.assets.version` bump + `orm_signaling_assets` row. Verify versions + hashes. Tenants: NOT installed this phase
(owner: payobook first).

## Report back (P1_REPORT.md)
Tests 1–12 results (paste counts); browser walk record with screenshots list; the design-bar self-score (1–5 per
bullet with one sentence each); every PA ledger row added; deviations from this handover with reasons; open
questions for P2 (especially: shared `run_driver` extraction plan from `payrun_wizard.js`).

## How to run tests and rehearse (no local Odoo — the server is the test bench; PA10, PA14)
- ssh alias `Payobook19v2` (passwordless sudo). **Never** touch `/odoo/odoo-server/addons`, never stop or restart
  `odoo-server`, never use port 8069, never run anything against the live databases (`payobook`, `rize`,
  `payobook_template`, `abm`). Live deploys need the owner's go-ahead and are done by Fable.
- Stage: `ssh Payobook19v2 'sudo rm -rf /tmp/p1stage && mkdir -p /tmp/p1stage'` then
  `rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude=.DS_Store <every module you touched + pb_payrun_wizard
  pb_demo biz_approval_workflow pb_payroll_ai_insights om_hr_payroll (P0 code)> Payobook19v2:/tmp/p1stage/` and
  `sudo chown -R odoo:odoo /tmp/p1stage`. The FIRST addons-path entry wins, so staged copies shadow live ones.
- Clone DB `p0clone` exists (a copy of `payobook_template` with P0 applied; crons and mail servers disabled). Reuse
  it. If you need a fresh one: `pg_dump -Fc payobook_template` → `createdb -O odoo p1clone` → `pg_restore` →
  `update ir_cron set active=false; update ir_mail_server set active=false;` (clones get crons — never skip this).
- Run tests detached (SSH-timeout-proof): write `/tmp/p1_test.sh` with
  `sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d p0clone
  --addons-path=/tmp/p1stage,/odoo/odoo-server/addons --http-port=8099 -i pb_payai_actions -u <touched modules>
  --test-enable --test-tags /pb_payai_actions,/pb_payroll_ai_insights --stop-after-init --logfile=/tmp/p1test.log;
  echo EXIT=$? >> /tmp/p1test.log; touch /tmp/p1test.done`, launch with `sudo systemd-run --collect --unit=p1-test
  /bin/bash /tmp/p1_test.sh`, poll the sentinel, then grep `FAIL:|ERROR: Test|odoo.tests.stats|EXIT=`. Pre-existing
  failures to ignore are listed in ledger PA11.
- Browser walk: start a TEMPORARY server on the clone only for the walk —
  `sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d p0clone --addons-path=/tmp/p1stage,
  /odoo/odoo-server/addons --http-port=8099 --workers=0 --max-cron-threads=0 --logfile=/tmp/p1web.log` (detached
  unit `p1-web`), check `free -m` first (need ≥ 700 MB available; if not, skip the walk and SAY SO), tunnel from the
  Mac with `ssh -N -L 8099:127.0.0.1:8099 Payobook19v2` (background), browse `http://localhost:8099/web?db=p0clone`
  with Chrome MCP (admin login on the template clone: ask Fable if unknown — do not guess passwords; the QA login
  exists only on `payobook`). Stop the unit (`sudo systemctl stop p1-web`) when done. Assets: a clone served this
  way compiles bundles on first load; purge `ir_attachment` `/web/assets/%` on the clone after JS changes.
