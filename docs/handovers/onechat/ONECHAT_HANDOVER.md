# ONECHAT — one helper chat, no tabs, with voice (handover for Opus)

Status: DESIGN rev 3, 2026-10-14 (rev 1 + the adversarial review; dispositions in Appendix A; **owner decisions Q1–Q7 in §16 are binding and win over any other text — notably the chat is named "PayAI", and spoken plans naming a person or an amount always need a tap**). Owner rulings
2026-10-14 (final, do not re-ask):
1. The Payobook helper drawer becomes **ONE chat with no tabs**. The helper decides what to do from what was
   typed: a command goes to PayAI's action path, a how-to or screen question goes to the guide, a pay-data question
   goes to PayAI's data answer, and "let me practise …" goes to practice.
2. **"Your next step" is removed** from the helper.
3. Practice is asked for in the chat, and a small **"Practise this"** suggestion appears under answers that teach a task.
4. **People can SPEAK** instructions and questions. Spoken words are routed exactly like typed text.
Locked earlier (PayAI program — unchanged here): an Amber plan may be confirmed by a spoken "go ahead" only when the
company's switch is on; a **Red decision (approve / send back / turn down) is never confirmed by voice**, only by the
typed word; PayAI reads plans back aloud when voice was used; English first, Vietnamese too.

Ledger: `docs/handovers/payai/PAYAI_LEDGER.md` binds this program (PA-R1…R5 and every PA row, especially PA10, PA14,
PA23, PA38, PA41, PA49, PA54, PA57, PA59, PA60). The first implementer creates `docs/handovers/onechat/ONECHAT_LEDGER.md`
seeded with §15 below and adds an OC row for every new gotcha. Phases run as **OC1 → OC2 → OC3 → OC4**, one Opus agent
each (or one agent doing them in order with a report per phase). Never start a phase before the previous one's tests
are green.

**White-label rule (binding, every phase):** the word "Odoo" (any case) never appears in anything a user can see, hear
or receive — labels, tooltips, placeholders, aria, errors, toasts, spoken read-back, .po msgstr. Technical identifiers
(`from odoo import`, module/model ids, log lines, comments, this doc) keep the real name.

## 0. Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." Measured against Linear / Notion AI / ChatGPT
voice — not stock back-office chat. Hero moments: (a) the person types or says anything and the RIGHT thing comes back
with no tab to pick; (b) speaking feels instant and safe — a live level meter, the words appear in the box, one tap
sends. Zero dead-ends: every reply names its next step. Plain screen words on every label (CLAUDE.md plain-English
rule). **Never the word "Odoo"** in anything a user can see or hear. Payobook design system: locked indigo palette
(`#5A4BB0`, soft `#EDEAF8`, ok `#2E7D4F`, warn `#D97706`, bad `#DC2668`), **Lucide icons only** (no Font Awesome in
anything this program draws), **no gradients, no emoji**, motion with purpose (160 ms fade-up on a new turn, respect
`prefers-reduced-motion`). Score every phase report against this bar (1–5 per bullet, one sentence each).

## 1. Scope (whole program)
- **S1 Router.** One server method decides where each sentence goes, with no AI call (§4).
- **S2 One chat UI.** Tab strip, the Guide input and the Practice tab disappear. One stream of turns, one composer,
  one header. Guide answers, PayAI answers, plan cards, practice turns and the question-collection consent card render
  in that one stream (§5).
- **S3 Voice in the one chat.** One microphone in the composer (tap to talk); the transcript lands in the box; one tap
  sends; the router runs on the sent text exactly as for typing; spoken go-ahead and read-back follow the locked rules;
  English and Vietnamese recognition (auto-detect); the consent copy is reworded for tap-to-talk (whether people are
  asked again is owner question Q5); the known recorder bugs fixed (§6).
- **S4 One conversation.** Every non-PayAI turn is recorded in the person's PayAI conversation as a content-free marker
  (no question text), so the thread survives a reload and the spoken go-ahead's "last thing I showed you" rule stays
  true (§7).
- **S5 Learn content follows the screen** (lessons, tour, settings wording, anchors, icons, tests) (§10).
- **S6 Remove "Your next step"** from the helper only (the Journey map keeps `next_best`).

## 2. Binding non-goals
- **PayAI's tiers, gates, runner, registry phrase table and confirm rules are NOT changed** (`pb_payai_actions/payai/
  runner.py`, `registry.py`, `gate.py`, `actions_*.py`). The ONLY exceptions, each narrow and tested:
  (E1) the `_LRU` cache fix (§8 R9); (E2) the `payai_ask_only` context flag read in
  `pb_payai_actions/models/payai_engine.py` `process_message` and set by an `ask_only` kwarg on the pb_payai_actions
  `rpc_send_message` override (§4.9) — it can only SKIP the command path, never add one; (E3) the `action_clear`
  override (§7); (E4) new READ-ONLY helpers that wrap existing predicates. A routed command reaches PayAI through the
  **same client `sendMessage()` → `payroll.ai.conversation.rpc_send_message(...)` path as today** (signature change in
  §5.4 is client-side only), with the same kwargs (`resolve`, `voice`) plus `ask_only`. Do not call `runner.handle`
  from anywhere else.
- **No auto-send of a transcript.** `rpc_transcribe_voice` keeps returning text only (test_egress `test_04b`). No
  hands-free loop, no wake word, no always-listening mode, no end-of-speech auto-send (owner question Q1).
- No browser speech recognition (Web Speech API) and no new speech provider. Voice needs the existing OpenAI speech
  service; where it is absent the microphone is absent.
- No change to the full-page chat (`payai_chat_full`, `ai_insight_chat_full.js`) beyond not breaking it; no change to
  the floating pill path except what `hosted` already does.
- No practice-mission deep links (`m1…m5` keep opening only from the Learn map). No new scenarios. "Do it live" is never
  offered under the word "practise".
- Do not touch the moment card (`momentHTML`, `c-m*`, `_momentAct`) — it keeps calling `openSuggested`
  (coach.js:557) and `c-fvexplain` (565-569), so **`openSuggested` stays**; only `c-fvexplain`'s
  `explainScreen()` call is routed through the queued `openHelper` (§5.4) so it lands in the new stream. Also untouched:
  the welcome card, the glossary card, the Journey, the scenario overlay, the hub "All tabs in <hub>" feature (that is
  the PAGE's tabs — name collision, keep it).
- Do not remove `learn.runtime.next_best`, `pb_learn.next_best_enabled`, or the intent `whatnext` (the screen's own
  next step — test_coach.py:263-276 relies on it). The Explain answer's own next-step block (`explain_blocks`,
  learn_intent.py:572) stays unless the owner says otherwise (Q7).
- Never reach Settings › Access and delegations: no router route, chip, door, lesson, Watch, Show-me or walkthrough
  offer that opens it for a person PayAI would refuse (owner ruling 2026-10-13; `gate.door_denied`, `ACCESS_LEARN`
  gate.py:92). This now includes answers found by the new SCREENLESS pass (§4.4).
- Opus implementers **never bump manifest versions and never deploy** (PA41, PA57). Fable bumps in the ship commit.

## 3. Verified plumbing (do not re-derive)
### 3.1 The drawer shell — `pb_learn` `CoachHost`
- Mounted once on the WebClient: `pb_learn/static/src/coach/coach_patch.js:17-27`, xpath `coach_patch.xml:11-16`.
  Template `pb_learn.CoachHost` = `coach.xml:14-120`; class `CoachHost` = `coach.js:177`.
- Root `div.lrn-coachhost t-on-click="onClick"` (`coach.xml:18`) — **every** `data-act` click inside the drawer, including
  HTML inside a child component, bubbles to `onClick` (`coach.js:1474-1520`), whitelisted by `COACH_ACTIONS`
  (`coach.js:73-119`).
- Drawer `<aside class="lrn-drawer" t-if="state.open">` (`coach.xml:44`) — it is not in the DOM while closed.
- Header `.lrn-dhead` `coach.xml:47-78`: title `coachName` + `<small>` "On: <screenLabel>" (getters `screenLabel`
  `coach.js:616-637`, `onScreenText` 639-642); Explain `data-act="c-explain"` (68-71, `t-if="covered"`); language
  `c-lang` (72-74, `langLabel` 1570-1576); Close `c-close` (75-77, aria-label hard-coded "Close").
- Banner `p.lrn-dhonest` 81-84 = `T("honest")`, unconditional. Tab strip `nav.lrn-dtabs` 88-97. Ask host
  `div.lrn-dask-tab` 101-103: `<t t-component="askTab.Component" close="closeHelper" handoff="state.handoff"/>` while
  `state.tab==='ask'`. Body `div.lrn-dbody t-out="bodyHTML" t-key="bodyKey"` 108. Guide form `form.lrn-dask` 110-117
  (single-line `<input t-ref="input">`, `onSubmit` → `ask()`), only on the guide tab.
- Registries `coach.js:121-140`: `HELPER_TABS="pb_helper_tabs"` (138), `HELPER_HOST="pb_helper_host"` (139) with `orb`
  added at 140. `TAB_ORDER` 144. `askAllowed` from the registered `groups` via `user.hasGroup` in `onWillStart`
  (232-241). Getters `askTab` 576-579, `tabs` 583-590; `setTab` 592-601 (logs `coach_tab` at 597); `askData` 604-611.
- `bodyHTML` 954-1022: practice branch 972-977 (`_practiceHTML` 1173-1180, `_practiceTryHTML` 1117-1138, `_tourHTML`
  1141-1151); `_groundedHTML()` call 978, method **1209**; answer at 983 (`this._answerHTML(this.state.answer)`);
  hub-without-lesson branch 984-993 (`_oftenHTML` 1297-1318, `_tabsHTML(true)`, `_nextStepHTML` call 991,
  `_notSureHTML`, `_suggestHTML`); default 994-1014 (`_nextStepHTML` call 997, `_notSureHTML` 1003, `_scenarioHTML`
  1008 / 1236-1259, `_suggestHTML` 1009 / 1320-1334, `_tabsHTML(false)` 1013 / 1264-1293). **Consent card**: drawn at
  1018-1019 when `state.askConsent` (`_consentHTML` method **1027**; set at 795, cleared 712/805) — it has no home once
  `bodyHTML` goes; it becomes a stream turn kind (§5.3). **"Your next step"** = `_nextStepHTML` **1097** +
  `_continueHTML` 1071-1090 + the `c-continue` branch (~1509, which calls `openSuggested`). `openSuggested(key)` 1156 is
  ALSO used by the moment card (`_momentAct` 544, call 557) → keep it. CSS `.lrn-cnext*` `coach.scss:661-691`.
- `ask()` 729-802: `orm.call('learn.intent','ask',[q, state.screen, RT.lang])` → ONE `state.answer` (not a transcript);
  `state.history` (195, pushed 741) is never drawn; logs `coach_hit`/`coach_miss` via `this._log(answer.matched…)`;
  `_maybeStore` (consent-gated question mining, `pb_learn.collect_questions`; sets `askConsent`). `askIntent(key)`
  846-852. `explainScreen` 827-844 → `orm "learn.intent","explain_screen",[screen, RT.lang]`, sets `state.answer`,
  never `_maybeStore`. **Bug:** it does not switch tab, so on Ask/Practice the button seems dead. The moment card's
  `c-fvexplain` (565-569) sets `state.open=true` and calls `explainScreen()` at once — in the one chat that is BEFORE
  the chat child has mounted and attached (§5.4 queues it).
- `_answerHTML(a)` **1336** already takes the answer as its argument. Miss → `noAnswer` + `askDataLead` + `c-askdata`
  (1341-1345) + "What I can answer here" chips (`_suggestions` 1361). Hit → badge (column / composed / screen), label
  h4, blocks via `_blockHTML` 1424 (p, steps, warn, ok, refusal, who, how, source, calc, calc_kpi), tools 1358-1374 via
  `_offers` 1199-1205: Show me, Watch, Try (**1369: literally `this._offers(a["try"], "try")` — pinned by test_explain.py:434**),
  Say it more simply, Open the lesson (`openLesson` 892 opens the GENERIC map — leave as is).
- `startScenario(key, mode, stepKey)` 906-929 closes the drawer, then `sc.load()`, `sc.begin()`. `openPractice` 1185-1188
  = `openLearn(this.action, "practice")` + close.
- Language: `toggleLang` 1542-1557 flips `state.lang`, `RT.lang`, `sc.state.lang`, saves localStorage `pbLearnPrefs.lang`;
  `_restoreLang` 1559-1568 falls back to the session language (and reads `session_info` the same broken way as PayAI —
  see 3.6). **`RT.lang` is not reactive**: only `this.state.lang` re-renders anything. Every getter rendered outside
  `bodyHTML` must read `this.state.lang` (test_coach.py ~556-580); test_coach.py:587 pins that `get bodyHTML() {`
  (sliced up to the next `\n    /**`) reads `state.lang` — move that pin if `bodyHTML` shrinks or moves.
- Keys: `_onKey` 410-429, document CAPTURE phase (bound 321, removed 340) → it runs BEFORE any handler on an element
  inside the drawer. `?` opens only (not in INPUT/TEXTAREA/contentEditable). Escape ladder today: `glossaryOpen()` →
  `return` (stand down, no stopPropagation); else `stopPropagation()` + `close()`. test_assets.py:286-313 `test_06`
  slices `_onKey(ev)` up to the first `\n    }` and requires: `glossaryOpen()` present, `stopPropagation` present, and
  EVERY `stopPropagation` followed within 220 characters by one of `Exit(`, `exitLesson(`, `onLeave(`, `close(` (note:
  `closeMenu(` does NOT contain `close(`; `this.menu.close()` does).
- `toggle()` 431-438 focuses the guide input after 60 ms. `close()` 700-718 resets `tab='guide'`, clears handoff,
  answer, question, `askConsent`. On mount adds `body.lrn-one-helper` (325/341). Drawer widens 420→480 px only
  `:has(.lrn-dask-tab)` (`coach.scss:582-585`).
- Chrome strings come from `pb_learn/static/content/learn_content.json` `"chrome"` — **generated** from
  `docs/tutorial_poc/author/data.js` by `docs/tutorial_poc/author/tools/gen_learn_data.py`. Never hand-edit the JSON.
  PA54: the generator rewrites `pb_learn/i18n/vi_VN.po` and `static/src/engine/fixture.js` — `git checkout` both after
  generating. `LOAD_FAILED` (`coach.js:63-66`) duplicates `helperFailed` and names "the Ask tab".
- Icon sprite `pb_learn/static/src/journey/icons.xml` has (relevant): `x send compass info flask rotate-ccw bar-chart
  sparkles help-circle bot`. **Missing** (add): `mic square volume-2 volume-x ellipsis trash-2 scan-text`. There is no
  `bar-chart-3` — use `bar-chart`.

### 3.2 The PayAI chat — `pb_payroll_ai_insights` `AiInsightChat` / `AiInsightChatEmbedded`
- `ai_insight_chat.js`: floating `AiInsightChat` (27); `this.hosted = !embedded && registry("pb_helper_host")
  .contains("orb")` (39-40) → draws and fetches nothing when the helper exists. `AiInsightChatEmbedded extends
  AiInsightChat` (727-792), props `close?`, `handoff?` (737); registered `registry.category("pb_helper_tabs").add("ask",
  {Component: AiInsightChatEmbedded, groups:["pb_payroll_ai_insights.group_payai_user"]})` (788-793).
  `base.group_user` implies `group_payai_user` (security xml:92) → every internal user has it.
- Template `pb_payroll_ai_insights.AiInsightChatEmbedded` = `ai_insight_chat.xml:301-451` (root `div.payai-embed`):
  message loop over `state.messages`, text div `payai-embed-text`, textarea `t-ref="chatInput"` (404-408; Enter sends,
  Shift+Enter newline, `onInputKeydown` js:142-147), mic (410-423, FA icon, only if `voiceOffered` js:373-375), send
  (424-429), recording line (397-402), voice consent card (381-394), hint/error (431-436), footer "Read aloud" + "Clear
  chat" (437-449), per-message replay (362-368). Hard-coded English: "Pin to Dashboard" (334), "Recording" (400), "Clear
  chat" (447), aria "Send" (427), fallbacks 'Show me' / 'Hold to speak' / 'Read answers aloud', notification
  "Microphone access denied…" (js:504-507). Welcome getters js:767-785.
- **Send today (exact):** `sendMessage()` js:159 takes **no arguments**: `text = state.inputText.trim()`; returns early
  `if (!text || this.state.isLoading)` (160-161); pushes the person's turn itself; clears `inputText` (176); sets
  `isLoading` (178) … clears it (223). Calls `rpc_send_message(text, sessionId, _currentScreen())` + `_extraSendKwargs()`
  (default `{}`); reply `{session_id, response, chart, insights, follow_up_questions, intent, drilldown_model, action,
  card}`. `sendSuggestion(text)` 153-157 sets `inputText` then awaits `sendMessage()`. `_takeHandoff` 750-762 (waits
  `_historyReady`, sends once per id). `runAction` 254 (`open_lesson`/`open_walkthrough` → Learn hub, closes the drawer).
  History `_loadHistory` 679 → `rpc_get_history` on EVERY mount — reload loses follow-up chips and "Show me" buttons.
- Transcript lands by APPENDING (563-564): `inputText = existing ? existing + " " + heard : heard`.
- Mount effects each time: `rpc_get_history`, `rpc_get_ai_icon_url`, `rpc_voice_status`, and (pb_payai_actions)
  `rpc_register_doors` (`chat_patch.js:314-343`). `onWillUnmount`: `_discarded = true`, `_audioChunks = []`, then
  `_releaseMicrophone()` (js:113-123, method 522) — **pinned by test_egress `test_04b2`**.
- Server `payroll_ai_conversation.py` (521 lines): `add_message(role, content, chart_config, insights, intent, card)`
  142-159 (`intent` is a **Char**, `card` a **Text** JSON column — both already on every DB; no new stored field is
  needed); `get_history(limit)` 161-176 (includes `card` via `_card_dict`); `action_clear` 178; `rpc_send_message(
  message, session_id, screen, resolve)` 231-296 → `self.browse(session_id).exists()` (**no owner check of its own** —
  relies on record rules) → `add_message('user', …)` → `get_history(limit=10)` → `payroll.ai.engine.process_message(
  message, history[:-1], context={user_id, screen, conversation_id, payai_resolve})`; `rpc_get_history` 298-311 (limit
  50; `get_or_create_session` when id is null); `rpc_clear_history` 314; `rpc_voice_status` 340-386; `rpc_set_voice_consent`
  388; `_speech_provider` 393-412; `rpc_transcribe_voice(audio_base64)` 415-466 (order: flag `payai.voice_enabled` →
  consent → provider → `MAX_AUDIO_B64` 8 MB → decode → `provider.transcribe_audio(bytes)`).
- **Voice consent copy is press-and-hold today** (`rpc_voice_status` copy 361-383): `consent_body` "Hold the microphone
  and speak. When you let go, the recording goes to an outside company's speech service, which turns it into text. The
  recording is audio: unlike text, we cannot take names out of it first. The text then waits in the box — nothing is
  asked or answered until you read it and press send. Say no and the microphone stays off. Everything else works the
  same."; `hold_hint` 'Hold to speak'; `check_hint`; `listen_label`; `failed`. **test_egress.py:583 `test_04e`** finds
  the body by the substring 'Hold the microphone and speak' and asserts EN 'When you let go, the recording goes',
  "outside company's speech service", 'cannot take names out of it', 'The text then waits in the box', NOT 'Nothing is
  sent until'; VI (lower-cased) 'khi bạn thả tay, bản ghi âm sẽ được gửi', 'công ty bên ngoài', 'không thể bỏ tên
  riêng', 'nằm chờ trong ô nhập'. `test_04f` gates register (≤28 words/sentence, jargon list).
  `payroll.ai.consent` (`payroll_ai_consent.py`) stores `user_id`, `voice`, `decided_at` — **no copy version**, so
  "ask everyone again" needs a new mechanism (Q5).
- `payroll.ai.message.card` / `_card_dict` **513-521** (end of file). pb_payai_actions overrides `_card_dict`
  (`pb_payai_actions/models/payai_conversation.py:175-200`): non-plan cards pass through `gate.scrub_card` unchanged.
- Engine `payroll_ai_engine.py`: `process_message` 349 (classifier `_classify_intent` 500, one LLM call; routes data
  537 / knowledge 665 / onboarding 893 / general 1000, one more call). Catch-all at ~412 returns `'I apologize, but I
  encountered an error: {str(e)}'` — raw exception text on screen (fix in OC1, §8 R8). `_content_handoff` 925-946 already
  calls `learn.intent.resolve(message[:400])` screenless.
- Provider `ai_providers/openai_provider.py:155` `transcribe_audio(audio_bytes, language='en')` — **always forces
  English** today (Vietnamese speech comes back garbled), file name always `voice_recording.webm`, **logs the first 80
  characters of the transcript at INFO (179-181)** — privacy fix in OC3. Only OpenAI has `transcribe_audio`. Live:
  payobook has an active OpenAI row; on rize and payobook_template the only row is INACTIVE (every PayAI question fails
  there today).

### 3.3 PayAI actions — `pb_payai_actions` (installed on **payobook only**)
- `PayrollAIEngine.process_message` override `models/payai_engine.py:44-73`: tier `look` off → question path; else
  `runner.handle` (exceptions other than AccessError → logged, question path); `None` → question path + "What can you
  do?" chip.
- `runner.handle` (`runner.py:1769-1806`) order: `payai_resolve` → `go_ahead` → `typed_answer(only_kinds=('reason',))`
  → question/thanks while a reason is open (return None) → `registry.match` → `typed_answer` → **`ask_model`** (LLM
  tools call). **`ask_model` (409-456) runs for EVERY non-question the phrase table misses** and refuses only when
  `registry.looks_like_question(message)` (411) is true. So today "help me run payroll", "please process June
  salaries", "I'd like to run June payroll" become plans through the AI (observed by the reviewer). And many questions
  are NOT `looks_like_question` (observed `q=False`): "can I approve the June run?", "where do I approve requests?",
  "where can I approve", "could I run payroll now?", "which button approves the run?", "where is the bank file",
  "hướng dẫn tôi chạy lương", "chỉ tôi cách duyệt", "cách chạy lương tháng 6", "tôi có thể duyệt đợt lương tháng 6
  không" — the AI may turn any of them into an `approve_item` (Red) or `run_payroll` (Amber) plan.
- `_provider(env)` (396-406): active config → `get_provider()` → `is_available()` and has `generate_tools`.
- Pure, no DB, no LLM (0.04-1.3 ms measured live): `registry.match(message)` (`registry.py:626`) → `(key, {slot:text})`
  or None (None for how/why questions); `registry.looks_like_question(message)` (552 = `_asks_how_or_why or
  asks_by_its_end`); `registry._FOLD_TWINS` (574: marked words that fold onto an order word but are another word);
  `runner.go_ahead_words(text)` (79; `GO_AHEAD` 61-64 is anchored whole-sentence and **includes "send it" and "run
  it"**; a bare "yes" never counts). DB reads, no LLM: `runner._open_question(ctx)` (984; typed clarify or reason
  question still latest), `runner.reason_question_open(ctx)` (1011), planned-task lookup inside `go_ahead`.
  `runner.Ctx(engine, context)` (302) builds `conversation` from `engine._conversation(context)`; `voice` =
  `env.context.get('payai_voice')` (326) — i.e. flags reach the runner through `with_context`, not the dict.
- Reason path observed in the review: sentences such as "Practice of paying overtime twice must stop" or "explain this
  screen is wrong" are valid typed REASONS while a reason question is open — the router must not grab them first.
- `_is_latest(ctx, task, past_answers)` (1707-1735): a spoken go-ahead counts only if the task is the newest task in the
  session AND the newest assistant `payroll.ai.message` carries that task's card; with `past_answers` the search is
  `card != False` and rows whose card has no `task_id` are skipped.
- Read-back tail already exists (1379-1387): Red → `out['speak']` (says the word must be typed); Amber → + 'Tap Do it or
  say go ahead.' when `company.payai_voice_go_ahead` else 'Tap Do it to go ahead.' — **reuse those two msgids** for the
  router notes (§4.3 step 4).
- Voice client: `chat_patch.js:375-382` patches `_transcribe` → `this._payaiVoice = true`; `_extraSendKwargs` (364-372)
  sends `voice:true` with whatever is sent next (edited text, chip, hand-off) and clears it; `resolve` wins when set.
  Server `payai_conversation.py:120-128` → `with_context(payai_voice=…)`. `_plan` sets `card.speak` only when
  `ctx.voice`; client `sendMessage` patch (345-362, forwards `...arguments` at 352) speaks it via `_payaiSpeak`.
  Red: `go_ahead` → `_needs_typing` ("A spoken go-ahead never counts", 1449-1462); `confirm` (1498) refuses Red unless
  `how=='typed'` and `word_ok`; voice needs `company.payai_voice_go_ahead` (`res_company.py:40-44`, default False,
  forced False by `__init__.py:20` post_init) and `_is_latest`.
- **Card chips send with a resolve:** `payaiPick` (chat_patch.js:525-528 sets `_payaiResolve` then
  `sendSuggestion(act.label)`), `payaiEdit` (730-731), follow-up chips with resolve (756-763); a chip with `chip.ask`
  calls `payaiAsk(chip.ask)` (736-737); hand-off `sendSuggestion(q)` (793). Their LABELS ("Cancel", "Change Period", a
  person's name) mean nothing to a router.
- `coach_patch.js:13-37` patches `CoachHost.setup`: `_payaiOpenHook` sets `state.open`, `state.handoff`, `state.tab="ask"`;
  registered in `registry.category("pb_payai").add("open", …)`; the ⌘K "Ask PayAI to…" row (`payai_palette.js:10-24`)
  calls it. `cards.xml:211-220` xpaths into `AiInsightChatEmbedded` on `//div[hasclass('payai-embed-text')]` and
  `//t[@t-foreach='state.messages']/div` — **keep both anchors**.
- `_LRU` (`runner.py:297-298`, used 420-456) is a **per-process** OrderedDict keyed `(ctx.user.id, ' '.join(safe.lower()
  .split()))` where `safe` is the redacted text; it stores slot texts AFTER `restore_names(…, mapping)` (452). After
  Clear chat the placeholder numbering restarts, so the same `safe` text maps to OLD names. Fixed in OC1 (§8 R9).
- Name resolver: fuzzy name match `resolve.tok_match` (`difflib` ratio ≥ 0.85, resolve.py:134-140); "tháng sáu" (June)
  vs "tháng sau" (next month) decided by marks (`sau_after_thang`, resolve.py:~365-380). A misheard word can pick a real
  but different employee or month — the read-back is the safeguard (§6.5).
- Company switches live on payobook: look / prepare / decide ON on all five companies; `payai_voice_go_ahead` OFF.

### 3.4 Guide path — `pb_learn/models/learn_intent.py` (`learn.intent`, AbstractModel)
- `ask(question, screen_key, lang)` 943-1003: `resolve` (793; advice guard `_is_advice` 139 first → `compliance`;
  candidates filtered to the screen) → `_match_column` (1312, only with a screen) → `_compose` (1098, flag
  `pb_learn.compose_enabled` = `COMPOSE_FLAG` :207, one `generate_text` per miss, ≤44 000-char corpus) → honest miss.
  `_answer(intent_key, screen_key)` 914 builds a hit payload (incl. `watch`, `try`, `practice_key`).
  `explain_screen(screen_key, lang)` 1290 (deterministic floor `_explain_floor` 1190, built by `explain_blocks` 572,
  which includes a next-step block); `explain_scenario_offer` 608-624 takes the FIRST scenario listed for the screen.
- Scoring `_score` 694-751 — **five match kinds**: exact 100, contained (phrase inside the question) 80, reverse
  (question inside a phrase, ≥6 chars) 60, two strong (non-ambiguous) shared words 55, one strong word of ≥6 letters
  40; then `+_ON_SCREEN_BONUS=25` (149) when the intent lists this screen and is not `*`. So 80 can be a two-word
  overlap on a screen-specific intent (55+25), one long word reaches 65, and "approve" on payruns is 60+25=85.
  `_resolve_hook` 753-789 ("THE SEAM": returns a key only). Floors `_SCORE_FLOOR=20` (148) with a screen,
  `_SCREENLESS_FLOOR=55` (182); a tie AT the floor is a miss. `_norm` 185 folds case, marks, đ→d, punctuation. No score
  leaves the server today; **test_composer.py:133-141 `test_02b` pins the MISS payload keys to exactly
  `{'matched','capability','suggest'}`** — never add a key to a miss.
- The guide claims many IMPERATIVES at 100 ("approve this run", "reject the run", "lock the week", "add a new employee",
  "start hiring", "email the payslips", "make the payment"…). A high guide score does NOT mean "not a command".
- Short intent phrases match INSIDE pay-figure questions (observed): "how much back pay is owed to Lan" → `retroq`
  ("back pay"); "what was Lan's last day" → `leaver`; "how many payslips are in the June run" on payruns →
  `howmanyslips` (55+25); "how many people have their first day this month" → `firstday`.
- `practice_key` is sent (939) but never read by the client. "let me practise …" resolves to intent `practice` (80) →
  text only, no practice starts. 16 intents carry `try` (list in §5.6).
- Contract `docs/tutorial_poc/author/contract.json:266` `coach-answers-from-writing-only` forbids provider-registry
  tokens, `cr.execute`, `json.load`, `file_open(` in `learn_intent.py`, `learn_runtime.py`, `learn_question.py`.
- `learn.runtime._station_reach(sidebar_key, visible_ids=None, index=None)` (learn_runtime.py:391) takes a **sidebar
  key** (menu xml id), returns `(visible, missing, reach)`. Today guide candidates are screen-filtered, so "delegate my
  access" (intent `delegate`, watch `sc_access`) only resolves on `access` / `hub_settings`; the new screenless pass
  would find it anywhere.

### 3.5 Practice — `learn.scenario` service (`pb_learn/static/src/scenario/scenario_service.js`)
- `begin(key, mode)` (307) → false for an unknown key; mode `try` → `openLearn(action, 'scenario:<key>:try')` (leaves the
  screen for the Learn hub); `forScreen(screenKey)`. 26 scenarios (1 retired); 16 have `try`; only `sc_payrun` and
  `sc_payslips` have `do` (real data). Scenario records have no phrases field (keys: entry, icon, key, line, modes, name,
  retired, screens, steps, tagline). Generator emits them at `gen_learn_data.py` `content_scenarios` (:1259); intents'
  `match` → `phrases` via `_intent_phrases` (:859).
- Scenarios per screen (computed from `learn_content.json`, non-retired, order as listed): payruns `sc_welcome`(watch),
  `sc_payslips`(try); runpayroll `sc_welcome`, `sc_payrun`(try), `sc_schemes`(try); formula `sc_welcome`,
  `sc_formula`(try); approvals `sc_welcome` only; dashboard `sc_welcome` only; access `sc_access`(watch). `sc_payrun.
  screens == ['runpayroll']`. `sc_wftime` and `sc_wftoday` are watch-only; `sc_wfclose` has try.

### 3.6 Voice switches
- Microphone switch for the whole DATABASE: `ir.config_parameter` `payai.voice_enabled` (`VOICE_FLAG`,
  `payroll_ai_consent.py:29`; Learning settings card "Talk to the helper", `pb_learn/models/learn_settings.py:48-56`,
  `learn_settings.js:28-29`). **Absent (= off) on every database today → no microphone anywhere.**
- Per-person consent `payroll.ai.consent` (`voice` unset/granted/declined, own-row rule). A "no" is permanent with no
  way back today.
- Spoken go-ahead switch per COMPANY: `res.company.payai_voice_go_ahead` ("PayAI can act" settings,
  `pb_payai_actions/views/res_config_settings_views.xml:29-32, 61`).
- Read-aloud = browser `speechSynthesis` (js:600-651); `utterance.lang` from `window.odoo?.session_info?.user_context
  ?.lang` (635) — that object does not exist in Odoo 17+ (`odoo.__session_info__` is deleted on load,
  `web/static/src/session.js:1-2`), so it is always en-US. localStorage `payaiReadAloud`.

## 4. The router (OC1) — one decision per sentence, never an AI call
### 4.1 Where it lives (layered by `_inherit`, no cross-imports)
- **New** `pb_learn/models/learn_helper.py`: AbstractModel **`learn.helper`**, method
  `route(self, text, screen_key=None, lang='en', session_id=None)` → dict (contract below). Pure Python over
  `learn.content` + `learn.intent`; NO provider code. Add `pb_learn/models/learn_helper.py` to the `files` list of
  contract `coach-answers-from-writing-only` (contract.json:269-273) so the same tokens are banned there.
- **New** `pb_payroll_ai_insights/models/learn_helper.py`: `_inherit = 'learn.helper'`; overrides
  `_payai_available()` = user holds `group_payai_user` AND the same test as `runner._provider` minus the tools clause:
  `get_active_config()` → `get_provider()` → `provider.is_available()` (wrapped in try → False). Adds conversation-side
  hooks (markers, §7).
- **New** `pb_payai_actions/models/learn_helper.py`: `_inherit = 'learn.helper'`; overrides `_route_payai_state(...)`,
  `_route_command(...)`, `_can_act()`, `_looks_like_question(...)`, `_capability_route(...)` using the EXISTING pure
  predicates (§3.3). Builds a `runner.Ctx` with `self.env['payroll.ai.engine']` and `{'conversation_id': session_id}` —
  read-only, no task rows written, no savepoint. A `session_id` whose conversation's `user_id != env.user` is treated
  as None (never read another person's tasks).
- **`route()` takes NO voice argument.** That is the structural guarantee that spoken text is routed exactly like typed
  text. Test 1.20 asserts the signature.
- `route()` stores nothing and logs no question text (guide privacy rule; same as `_log(answer.matched…)`).

### 4.2 Return contract (the ONLY thing the client interprets)
```
{route: 'payai'|'guide'|'explain'|'practice'|'choose'|'note'|'miss',
 why: '<stable code for tests: goahead|open_question|command|command_ai|data|question|practise|explain|capability|
       guide_strong|guide|guide_imperative|guide_offer|weak|composed|no_payai|empty|nothing_waiting|tap_card|
       smalltalk|howto|order_question>',
 ask_only?: bool,                                                     # payai: send with ask_only=True (§4.9)
 fallback_key?: '<intent key>',                                       # payai: show answer_for(key) if PayAI errors
 answer?: <learn.intent hit payload, exactly as ask() returns>,      # guide
 lead?: {en, vi},                                                     # guide_imperative / guide_offer
 practice?: {key, mode:'try'|'watch', name:{en,vi}} | {chips:[{key, mode, name}], sandbox: true},
 choices?: [{label:{en,vi}, route:'guide'|'payai'|'practice', key?, text?, mode?}],   # ≤ 3
 extra_chips?: [{label:{en,vi}, route, key?, text?, primary?: bool}],  # "Explain how instead", "Do it for me"
 note?: {en, vi, key},                                                # route 'note' / 'miss' (key = chrome key)
 suggest?: [...]}                                                     # miss / smalltalk: "What I can answer here"
```
A miss built by `learn.intent.ask` keeps its own exact keys inside `answer`; `route()` wraps, never edits it (test_02b).

### 4.3 Order of checks (first match wins). D = deterministic; DB = reads only; no step calls an AI model.
Shapes used below (all pure, §4.6): `Q` = information question; `H` = how-to request (⊂ Q); `whole(...)` = the
trigger is the whole sentence (after trimming punctuation/filler); `start(...)` = the trigger opens the sentence.
| # | Check | Kind | Route |
|---|---|---|---|
| 1 | Empty / whitespace | D | `miss` `empty` (client never sends it) |
| 2 | `_route_payai_state`: `go_ahead_words(text)` AND a `planned` task in this session | DB (pb_payai_actions) | `payai` `goahead` |
| 3 | `_route_payai_state`: `runner._open_question(ctx)` is not None (typed clarify OR reason question open and latest) → **everything else goes to PayAI**, including sentences that look like practise / explain / bare words. PayAI's own `handle()` decides reason-vs-question (FIX-1 crit-4, PA49). Do NOT re-implement that split (PA59). | DB | `payai` `open_question` |
| 4 | Whole-sentence bare words. With a planned task: yes / ok / có / dạ / ừ / được → note `tap_card`, wording by tier: Red "Type <WORD> in the box on the card." (the card's own word, from the task's action); Amber with `company.payai_voice_go_ahead` on AND voice offered to this person → "Tap Do it or say go ahead." (runner msgid); otherwise "Tap Do it to go ahead." (runner msgid); cancel / không / thôi → "To stop, tap Cancel on the plan card." With NO planned task: go-ahead words → note `nothing_waiting` "Nothing is waiting for your go-ahead." when `_can_act()`, else "I can't do things for you here — ask me how instead." | D/DB | `note` `tap_card` / `nothing_waiting` |
| 5 | Small talk, whole sentence: greetings (hi, hello, hey, xin chào, chào), thanks (thanks, thank you, cảm ơn, cám ơn), acknowledgements (ok, okay, got it, được rồi, ừ) with nothing waiting, and junk (< 3 letters, or only punctuation/filler such as "uh", "hmm", "ờ"). Reply: short authored note ("Happy to help. Ask me how to do something, or about this screen.") + the screen's suggestion chips. | D | `note` `smalltalk` |
| 6 | Practise / tour trigger (§4.5), anchored, and NOT `Q`. A `Q` sentence that mentions practice ("how do I get off the practice company?", "Is Lan on the practice company?") skips this step and is answered by the guide (step 12/14; a hit on intent `practice` is drawn as a practice route with chips, see 4.5). | D | `practice` `practise` |
| 7 | Explain trigger, `whole(...)`: EN "explain this (screen\|page)", "what is this (screen\|page)", "what am I looking at"; VI "giải thích (màn hình\|trang) này", "(màn hình\|trang) này là gì" (folded). "explain this screen is wrong" does NOT match. | D | `explain` |
| 8 | Capability, `whole(...)`: "what can you do", "help", "what can I ask", "what can I ask you", "bạn làm được gì", "giúp tôi", "trợ giúp", "tôi có thể hỏi gì". `_capability_route` (pb_payai_actions): if `registry.match(text)` returns `what_can_you_do` → `payai` `command` (PayAI's own card); else the helper capability card (lists what THIS helper can do here: explain, answer, pay data if `_payai_available`, act if `_can_act`, practise, voice if offered). "giúp tôi chạy lương" is NOT whole-sentence → not this step. | D | `payai` `command` / `guide` `capability` |
| 9 | How-to request `H` (§4.6). Marks the sentence `Q`+`H`; **steps 10 and 11 are skipped** (a how-to request is never a command). Continue at 12. | D | — |
| 10 | Order + "?": the sentence is ≤ 4 words, ends with "?", and `registry.match(text without "?")` hits (e.g. "Run payroll?", "Approve?") → `choose` with "Do it now" (route payai, text = the sentence without "?") and "How it works" (route guide, key = the probe's best intent; omitted when none). | D | `choose` `order_question` |
| 11 | `_route_command`: tier `look` on for the company AND the sentence is NOT `Q` by the router's own lead words (polite requests "can you / could you / would you / please …" are NOT `Q`) AND `registry.match(text)` hit → `payai` `command`. Add `extra_chips` "Explain how instead" (route guide, key) when the probe (4.4) has an intent hit of kind exact or contained. | D | `payai` `command` |
| 12 | Guide strong: `Q` AND probe kind **exact**; OR `Q` AND kind **contained** unless (`_payai_available()` AND the data signal (4.7) fires AND the sentence has a figure, time or name reference) — then fall to 13. | D | `guide` `guide_strong` |
| 13 | Data signal (4.7) AND `_payai_available()` → PayAI, `ask_only = Q`. `fallback_key` = probe key when kind ≥ overlap2. When PayAI is NOT available, remember `data_seen=True` and **continue** (never end here). | D | `payai` `data` |
| 14 | Guide normal. (a) `Q` AND kind ∈ {contained, reverse, overlap2} → `guide` `guide`. (b) NOT `Q`: if `_can_act()`: kind exact → `guide` `guide_offer` with lead "Here is how. Or I can prepare it for you." + primary chip "Do it for me" (route payai, text = the sentence); any other kind or no hit → `payai` `command_ai` (PayAI's own tools call, exactly as the Ask tab does today; `fallback_key` when kind ≥ overlap2). If NOT `_can_act()`: kind ∈ {exact, contained} → `guide` `guide_imperative` with lead "Here is how you do it." (c) A hit on intent `practice` → `practice` with this screen's chips. | D | `guide` / `payai` / `practice` |
| 15 | Weak: kind overlap1, or a COLUMN hit on a `Q` sentence → if `_payai_available()` `choose` with two chips: the guide intent's label (route guide, key) and "Ask about your pay data" (route payai, text, ask_only); else `guide` with that answer (today's acceptance). Column hits on a NON-`Q` sentence are ignored (stops "open the pay runs board" becoming a column definition). | D | `choose` / `guide` |
| 16 | Composer: NOT `_payai_available()` AND `Q` AND `COMPOSE_FLAG` on → `learn.intent.ask(text, screen_key, lang)` (re-runs intent/column, then composes); a hit → `guide` `composed`; NO_ANSWER → continue to 18. Never runs when PayAI is available (PayAI's knowledge path answers instead — one path, not a chain). | 1 AI call, only here | `guide` `composed` |
| 17 | `_payai_available()` → PayAI question path, `ask_only = Q` (always true for sentences reaching here as `Q`; non-`Q` sentences on a database that cannot act also get `ask_only=True`, since there is no command path to protect them from). `fallback_key` when kind ≥ overlap2. | — | `payai` `question` |
| 18 | Else `learn.intent.ask(...)` full → hit `guide`; miss → `miss` (with `suggest`); when `data_seen`, the miss is `no_payai` with note "Questions about pay figures need the assistant service, which is not set up here. Ask your administrator to set it up, or ask me how something works." + suggestions. | — | `guide` / `miss` |
Routing itself never calls a model. The only model calls are inside destinations: step 16 (guide composer, flag-gated,
only where PayAI is unavailable) and PayAI's own path after steps 2/3/8/10-chip/11/13/14/17 (tools call and/or
classifier + answer, as today). With `ask_only` the tools call is skipped, so a question costs at most classifier +
answer (2 calls), the same as one Ask-tab question today.

### 4.4 Guide probe — new, deterministic, no composer
- Refactor `_score` into `_score_kind(question, intent, ambiguous)` → `(kind, base)` with kind ∈
  `exact|contained|reverse|overlap2|overlap1|None` and base 100/80/60/55/40/0, plus `_on_screen(intent, screen_key)`;
  `_score` = base + 25 if on-screen (UNCHANGED results — test 1.9 runs the whole existing suite).
- `learn.intent._resolve_scored(question, screen_key, candidates)` → `[(score, kind, on_screen, key)]` sorted, floors
  and the tie-at-floor rule applied exactly as `_resolve_hook` does; refactor `_resolve_hook` to call it and return the
  first key (contract unchanged).
- New `@api.model probe(question, screen_key=None)` → `{key, score, kind, on_screen, scope:'screen'|'any',
  source:'intent'|'column'|'advice'}` or `None`: advice guard first (→ `compliance`, kind exact, source advice); then
  the screen pass; if no hit of kind ≥ overlap2, a SCREENLESS pass over all intents (floor 55) — fixes "what is BHXH"
  asked on Pay Runs; then `_match_column` (source column, kind overlap1). **The router thresholds on `kind`, never on
  the score.** `ask()`'s miss payload is untouched (test_02b).
- **Access filter on every guide payload the router returns** (screenless hits included): if the payload's intent,
  `watch`, `try`, lesson or Show-me target is in `ACCESS_LEARN` terms (`access`, `sc_access`, the Access lesson) and
  `learn.runtime._station_reach(<the Access sidebar key>)` says not visible, drop those offers (and for intent
  `delegate` itself, answer the honest miss). Mirror `gate.ACCESS_LEARN` in pb_learn as a constant; do not import gate.
- New `@api.model answer_for(key, screen_key=None, lang=None)` → the same hit payload `ask()` returns for that intent
  (for chips, "Show again", PayAI-error fallback and the router), with the same Access filter. Unknown key → the honest
  miss payload.

### 4.5 Practise trigger and scenario matching
- Triggers checked at step 6, never for a `Q` sentence. **Anchored**: each EN trigger must open the sentence
  (`start`), except the tour/practice-company phrases which must be the whole sentence (`whole`).
  EN start: `let me practi[sc]e`, `i want to practi[sc]e`, `i'd like to practi[sc]e`, `practi[sc]e (running|how|
  approving|adding|…)` (practise + a verb-ing or "how", never "Practice of …"), `rehearse`, `try it safely`.
  EN whole: `practice`, `practise`, `practice mode`, `open the practice company`, `take me to the practice company`,
  tour `show me around( payobook)?`, `take the tour`, `give me a tour`, `show me the tour`, `start the tour`.
- **Vietnamese triggers are matched on the MARKED text** (NFC, lower-case): start `cho tôi thực hành`, `tôi muốn thực
  hành`, `thực hành`, `cho tôi làm thử`, `làm thử`, `tập làm` — each as whole words and NOT followed by `quen|tục|công`
  (so "Làm thủ tục nghỉ việc cho Lan", "làm thủ công", "tập làm quen" never trigger); whole `thử trên công ty thực
  hành`, tour `cho tôi xem một vòng`, `đi một vòng( payobook)?`. Folded matching is used ONLY when the whole sentence
  has no Vietnamese marks at all (PayAI's `_FOLD_TWINS` approach): then `cho toi thuc hanh`, `^thuc hanh`, `lam thu`
  (not followed by `tuc|cong`), `tap lam` (not followed by `quen`).
- **Never bare "try"** ("try again").
- Strip trigger + filler (`me, to, how, the, a, an, cách, việc`), tiny EN stem (`running→run, importing→import,
  approving→approve, adding→add, closing→close, paying→pay`).
- Score the remainder against a NEW authored `phrases` list per scenario (EN + VI + unaccented), added in `data.js` as
  `match:[…]` on each scenario and emitted by `content_scenarios` like `_intent_phrases`; same kinds (exact / contained /
  reverse / overlap2) and ambiguous-word filter; the generator REFUSES a phrase that appears on two scenarios.
  Candidates: non-retired scenarios.
- Outcome: best hit with `try` → `practice {key, mode:'try'}`; a watch-only hit → `practice {key, mode:'watch'}` + note
  `watchOnlyNote` "This one can be watched, not practised." (pinned: "let me practise approving overtime" →
  `sc_wftime` watch + note, provided its authored phrases include "approve overtime" — OC4 authors them); a tie or
  below floor → `practice {chips: this screen's try scenarios (≤4), sandbox: true}`; trigger with no topic → this
  screen's single try scenario if exactly one, else the same chips (a screen with none, e.g. approvals/dashboard →
  chips of the 4 most-used try scenarios + "Open practice mode"); tour trigger → `sc_welcome` watch; "open the practice
  company" → `{chips, sandbox:true}` with "Open practice mode" first. Secondary signal when scenario phrases miss:
  `probe()` restricted to intents with a `try` key → that scenario. `sc_access` is never offered by the router to a
  person who cannot see Access (`_station_reach` for the Access sidebar key).
- A guide hit on intent `practice` (a question ABOUT practice) is returned as `practice {chips…}` with the guide answer
  drawn above the chips (route `practice`, `answer` set) — not text only.

### 4.6 Question and how-to shape (pure, in `learn.helper`)
- `Q` (information question): EN lead `how|what|where|why|when|which|who|whose|can i|could i|may i|do i|does|did|is|
  are|am i|should|will|would i|tell me (how|what|why|where)`; OR ends with `?`/`？` AND does not open with a polite
  request lead (`can you|could you|would you|will you|please`); OR VI (folded) contains `lam sao|the nao|nhu the nao|
  o dau|la gi|tai sao|vi sao|khi nao|bao gio|co the … khong$|co … khong$|duoc khong$|chua$`; OR `H`. When
  pb_payai_actions is present, also OR `registry.looks_like_question(text)` (override hook `_looks_like_question`).
- `H` (how-to request, ⊂ Q): EN `show me how|teach me|walk me through|guide me|steps to|what are the steps|explain how|
  how (do|can|should|would) i|how to|where (is|are|do|can)|what (is|are|does .* mean)`; VI marked-or-folded
  `chỉ (tôi|mình|em )?cách|hướng dẫn|cách (để )?|các bước|làm sao|làm thế nào|ở đâu|là gì|nghĩa là`.
  Observed today (`registry.match`): "show me how to run payroll", "show me how to approve the June run", "show me how
  payroll works", "show me the steps to run payroll" and "cho tôi xem cách chạy lương" all return `run_status` — the
  `H` check at step 9 is what keeps them out of step 11.

### 4.7 Data signal (pure)
- A quantity word anywhere: EN `how many|how much|total|sum|average|avg|highest|lowest|top \d*|most|least|compare|trend|
  breakdown|by (department|division|team|month)|headcount|payroll cost|cost of|spend|ranking`; VI (folded)
  `bao nhieu|tong|trung binh|cao nhat|thap nhat|so sanh|xu huong|theo phong ban|so nguoi|chi phi`.
- OR a time/figure reference (`\d`, month names EN/VI incl. `thang \d+`, `this|last|next (month|year|quarter)`, `ytd`,
  `thang nay|thang truoc|nam nay`) AND (`Q` OR starts with `show|list|give|tell|xem|cho toi xem|liet ke`).
- `figure_ref` (used at step 12): a digit, a month/period word, or a capitalised word that is not the first word and
  not a product word (a likely person name, e.g. "Lan"). VI: same, plus a word after "của"/"cho".
- Bare terms ("net pay", "gross") are NOT a data signal ("what is net pay" is a definition → guide / PayAI knowledge).
- A data signal does not end the conversation on a database without the assistant (step 13 continues): "how much does
  BHXH cost the company", "how do I compare two pay runs", "what is the most common reason a payslip changes" still get
  a guide answer there when one exists.

### 4.8 Routing corpus (server test 1.1 — run on screen `payruns` unless stated; P = payobook with pb_payai_actions,
B = base only / rize-like. "record" = the implementer fills in the observed value and the test pins it; a reviewer
checks it is sensible. Every row asserts `route` AND `why`.)
| Sentence | P route / why | B route / why |
|---|---|---|
| how do I approve a request | guide guide_strong (approve) | same |
| How do I approve a request? (screen approvals) | guide guide_strong | same |
| approve the request waiting for me | payai command (Red plan) + chip Explain how instead | guide guide_imperative |
| approve this run | payai command | guide guide_imperative (approve) |
| approve (single word, payruns: kind reverse/overlap, 60+25) | record: payai command if `registry.match` hits, else payai command_ai | record (guide guide_imperative or weak) |
| Run payroll? | choose order_question ("Do it now" / "How it works") | guide (Q, howrun) |
| lock the week | record: payai command if phrase-table hit; else guide guide_offer (exact) + "Do it for me" | guide guide_imperative (lockweek) |
| run June payroll for Retail | payai command | guide guide_imperative (howrun) |
| help me run payroll | payai command_ai (or command if the phrase table hits — record) | guide guide_imperative |
| please process June salaries | payai command_ai / command — record | guide / miss — record |
| I'd like to run June payroll | payai command_ai / command — record | guide / miss — record |
| chạy lương tháng 6 cho Retail | payai command | guide / miss (record actual; VI gap) |
| show me how to run payroll | guide (H, howrun) — never payai command | same |
| show me how to approve the June run | guide (H) | same |
| show me how payroll works | guide (H) or payai question ask_only — record | guide / composed / miss — record |
| show me the steps to run payroll | guide (H, howrun) | same |
| cho tôi xem cách chạy lương | guide (H, howrun if VI phrase exists, else payai question ask_only) — record; never command | guide / miss |
| can I approve the June run? | guide or payai question with ask_only=True — never command | guide / miss |
| where do I approve requests? | guide guide_strong/guide (approve) | same |
| where can I approve | guide (Q) | same |
| could I run payroll now? | guide / payai question ask_only — record; never command | guide |
| which button approves the run? | guide / payai question ask_only — record | guide / miss |
| hướng dẫn tôi chạy lương | guide (H) or payai question ask_only — never command | guide / miss |
| chỉ tôi cách duyệt | guide (H) or payai question ask_only | guide / miss |
| cách chạy lương tháng 6 | guide (H) or payai question ask_only | guide / miss |
| tôi có thể duyệt đợt lương tháng 6 không | payai question ask_only (or guide) — never command | guide / miss |
| let me practise running payroll | practice sc_payrun try | same |
| cho tôi thực hành chạy lương | practice sc_payrun try | same |
| let me practise approving overtime | practice sc_wftime watch + watchOnlyNote | same |
| practice | practice: payruns has one try (sc_payslips) → sc_payslips try | same |
| practice (screen approvals) | practice chips (no try on approvals) | same |
| show me around Payobook | practice sc_welcome watch | same |
| show me the tour / start the tour | practice sc_welcome watch | same |
| open the practice company | practice chips, sandbox, "Open practice mode" first | same |
| how do I get off the practice company? | guide (intent practice → practice chips + answer) — not a practice start | same |
| Is Lan on the practice company? | guide / payai question — record; never a practice start | guide / miss |
| Practice of paying overtime twice must stop (reason question open) | payai open_question | — |
| Practice of paying overtime twice must stop (nothing open) | not practise; record (guide / payai) | record |
| nhân viên mới đang tập làm quen | not practise; record | record |
| Làm thủ tục nghỉ việc cho Lan | not practise; record (payai command / command_ai) | record |
| làm thủ công | not practise; record | record |
| explain this screen | explain | explain |
| explain this screen is wrong (reason question open) | payai open_question | — |
| explain this screen is wrong (nothing open) | not explain; record | record |
| what can you do | payai command (what_can_you_do) | guide capability |
| what can I ask | guide capability (registry.match None) | guide capability |
| giúp tôi | guide capability | guide capability |
| bạn làm được gì / trợ giúp | payai command (what_can_you_do) | guide capability |
| giúp tôi chạy lương | not capability; payai command / command_ai — record | guide / miss — record |
| go ahead (plan waiting, typed or spoken) | payai goahead | note nothing_waiting ("I can't do things for you here…") |
| go ahead (nothing waiting) | note nothing_waiting ("Nothing is waiting for your go-ahead.") | note nothing_waiting ("I can't do things…") |
| yes (Amber plan waiting, voice switch off) | note tap_card "Tap Do it to go ahead." | — |
| yes (Amber plan waiting, switch on, voice offered) | note tap_card "Tap Do it or say go ahead." | — |
| yes (Red plan waiting) | note tap_card "Type APPROVE in the box on the card." (the card's word) | — |
| thanks / hi / ok (nothing waiting) / "uh" | note smalltalk + suggestions — no AI call | same |
| thanks (reason question open) | payai open_question (FIX-1 thanks path) | — |
| what is BHXH | guide guide_strong (screenless pass) | same |
| how many payslips should there be | guide guide_strong (howmanyslips) | same |
| how many payslips are in the June run | payai data (contained + figure ref → data wins) | guide (howmanyslips) |
| how much back pay is owed to Lan | payai data | guide (retroq) |
| what was Lan's last day | payai data / question — record; not leaver unless exact | guide (leaver) |
| how many people have their first day this month | payai data | guide (firstday) |
| how many employees do we have | payai data | miss no_payai |
| how much does BHXH cost the company | payai data | guide if a hit, else miss no_payai — record |
| how do I compare two pay runs | guide (H) | guide (H) |
| what is the most common reason a payslip changes | guide or payai data — record | guide (whydiff) — record |
| show me headcount by department | payai data | miss no_payai |
| show me net pay for June | payai command (run_status) or data — record which | miss no_payai |
| open the runs board | payai command (open_screen) | not a column answer: guide / miss — record |
| where is the bank file | guide (H) or payai question ask_only — record | guide / miss |
| bhxh là gì | guide (VI phrase added in OC4) or payai question ask_only — record | guide / miss |
| send it back (Red plan waiting, reason question open) | payai open_question | — |
| a typed reason "Approve the overtime first" (reason open) | payai open_question (PayAI keeps it as the reason, PA49) | — |
| delegate my access (screen payruns, person cannot see Access) | guide miss / no Watch, no lesson, no Show me | same |

### 4.9 `ask_only` (exception E2 — the only server change on PayAI's question path)
- `pb_payai_actions/models/payai_conversation.py` `rpc_send_message(..., voice=False, ask_only=False)` →
  `with_context(payai_voice=bool(voice), payai_ask_only=bool(ask_only))`.
- `pb_payai_actions/models/payai_engine.py` `process_message`: when `self.env.context.get('payai_ask_only')` and
  `context.get('payai_resolve')` is empty: run `runner.handle` ONLY if `runner.go_ahead_words(message)` is true or
  `runner._open_question(runner.Ctx(self, context))` is not None (both cheap; state can change between route and send);
  otherwise skip `runner.handle` and go straight to the question path (+ the existing "What can you do?" chip). It can
  only remove the command path, never add one; a client that omits it gets today's behaviour.
- The base module's `rpc_send_message` does NOT accept `ask_only`; the client sends it only through the pb_payai_actions
  `_extraSendKwargs` patch (same pattern as `voice`), so base databases never see an unknown kwarg.

## 5. The one chat UI (OC2)
### 5.1 Ownership (decision)
**The stream, composer and voice live in PayAI's embedded component; the shell, header, guide brain and practice
doors stay in CoachHost.** Reasons: voice, read-aloud, history, plan cards, `cards.xml` xpaths and the `test_04b2`
discard pins are all already in `AiInsightChat`; PayAI depends on pb_learn (manifest :81), so PayAI JS may import from
`@pb_learn/...`; pb_learn still never imports PayAI (registry seam). The guide brain (`_answerHTML`, `_offers`,
`explainScreen`, `_log`, `_maybeStore`, `startScenario`, `openPractice`, `openSuggested`) stays in `coach.js`, keeping
every source-pinned test where it is.
- Registry: rename the seam to **`pb_helper_chat`**, key `main`: `{Component: AiInsightChatEmbedded, groups:[…
  group_payai_user]}`. CoachHost reads `pb_helper_chat/main`, falling back to `pb_helper_tabs/ask` (3-line shim, remove
  next release). Rename `askAllowed`/`askTab` → `chatAllowed`/`chat`.
- CoachHost passes the chat these props: `helper` (a plain object built once in `setup`; functions read reactive state
  at call time), **`lang` (a plain string prop = `state.lang`)** and `close`. Because `helper` never changes identity,
  OWL would never re-render the child on a language flip; the `lang` prop is what does. `helper` =
  `{T(key, lang), screen(), covered(), canExplain, answerHTML(answer, lang) → markup, contextHTML(lang) → markup,
  consentHTML(lang) → markup, practiseChip(answer) → {key,name}|null, onGuideAnswer(question, answer), explain() →
  Promise<answer>, answerFor(key) → Promise<answer>, startPractice(key, mode), openPracticeMode(), attach(api),
  detach()}`. `_answerHTML(a)` already takes its argument (1336) — keep the name and body shape (test_coach pins no
  `doAction`). `answerHTML` returns `markup(...)` (OWL escapes plain strings).
- The chat calls `helper.attach(api)` in setup and `detach()` on unmount, where
  `api = {pushGuide(answer, opts), pushNote(note), pushTurn(turn), sendText(text, opts), focus(), setDraft(text),
  clear(), toggleReadAloud(), readAloudOn(), reopenVoiceConsent(), cancelRecording(), isRecording()}`.
- CoachHost keeps a queue: any `helper` push requested while no api is attached (moment card `c-fvexplain`, ⌘K, header
  Explain clicked during mount) is queued and flushed on `attach`, the same mechanism as `openHelper` (§5.4).
- Mount: `<t t-if="chat" t-component="chat.Component" helper="helper" lang="state.lang" close="closeHelper"/>` inside
  the open drawer — mounted while the drawer is open, unmounted on close (keeps the `_discarded` guarantee).
- **In-memory turns survive close/reopen**: the chat's turns live in a module-level store keyed by session id (or a
  `{turns}` object owned by CoachHost and passed in `helper`), for the page's life. On re-mount, if the store has turns
  for this session, use them and skip the history reload's marker collapse; `rpc_get_history` is used only when the
  store is empty (first open after a page load) — that is the only time guide answers appear as markers.
  Cache per page load (module variables) the icon url and the doors registration hash, so a re-open costs one
  `rpc_helper_status` call and no history call.
- **Turns store payloads, not markup.** A guide turn stores the answer payload (both languages are in it — `gtx`
  picks) and is rendered at draw time via `helper.answerHTML(answer, lang)`, so the language pill re-renders every past
  guide turn. Notes store `{en, vi}`.
- **Fallback (no chat registered, or the person lacks the group):** CoachHost draws its own minimal stream
  (`state.turns`, in memory for the page's life) with the same `_answerHTML`, the context card and a textarea composer
  (no mic), and calls `learn.helper.route` itself (base layer only: guide / explain / practice / capability / note /
  miss). Keep `ask()` as the guide call for that path. The practice tripwire (test_practice) must still see only
  `learn.progress`/`learn.event` calls in practice-reachable methods — `route` is called from the composer path only.

### 5.2 Drawer layout (top → bottom)
1. **Header** (keep): mark + "Payobook helper" + "On: <screen>"; right cluster: **Explain this screen** (icon
   `scan-text`, label in tooltip and aria), **language pill** ("Tiếng Việt" / "English"), **More** (`ellipsis`) menu,
   **Close** (`x`, aria from chrome `close`, not hard-coded).
   More menu: **built as an HTML string in coach.js** (so test_practice test_08's `data-act="c-practice"` pin in
   coach.js stays true), rendered by CoachHost, items: "Read answers aloud" (switch, `volume-2`/`volume-x`; calls
   `api.toggleReadAloud()`, state from `api.readAloudOn()`), "Clear conversation" (`trash-2`, inline confirm; calls
   `api.clear()`), "Open practice mode" (`flask`, `data-act="c-practice"`), "Use my voice" (`mic`, only when the person
   once said no and voice is otherwise available — calls `api.reopenVoiceConsent()`). Keyboard-navigable (arrows move,
   Enter picks). **Escape**: `_onKey` (document capture) gets two new rungs, in this order, each with
   `ev.stopPropagation()` followed within 220 chars by a `close(`-containing call (test_06):
   (i) glossary open → stand down (unchanged); (ii) `this.menu.open` → `ev.stopPropagation(); this.menu.close();`;
   (iii) `this._api?.isRecording()` → `ev.stopPropagation(); this._api.cancelRecording(); this.menu.close();` (the
   `menu.close()` call is harmless when the menu is shut and satisfies test_06's `close(` rule — test_06 must pass
   unmodified); (iv) else close the drawer (unchanged). Where the More menu's state lives: `this.menu = useState({open:
   false, close(){…}})` in CoachHost.
2. **Banner** `lrn-dhonest` — shown only while the stream is empty, then gone. Three variants from chrome:
   `honestAct` (when `can_act`): "Ask me anything, or ask me to do something. I always show you the plan first, and
   nothing changes until you say so." · `honestAsk` (PayAI available, cannot act): "Ask me about this screen, how to do
   something, or your pay figures." · `honestGuide` (fallback): "Ask me how anything on this screen works."
3. **Stream** (scrolls; sticks to the bottom; "Jump to latest" pill when scrolled up). Turn kinds in §5.3.
4. **Context card** — not stored, built by `helper.contextHTML(lang)`; shown (a) when the stream is empty, (b) as the
   newest item when the drawer opens on a screen other than the last turn's screen; it collapses to a one-line divider
   "On Pay Run › Runs" as soon as the person sends something. Content, in order: grounded line (`_groundedHTML`, one
   line); **"Not sure what to ask?"** (chrome `notSure`, kept — test_explain 07b) with ≤4 chips = the screen's `suggest`
   (or `_oftenHTML` items on a hub tab with no lesson), plus "What can you do?" when `can_act`, plus "Let me practise this"
   when the screen has a try scenario; **Explain this screen** (secondary button); **"Show me how"** rows
   (`_scenarioHTML`: Watch / Practise / Do it live — "Do it live" keeps its own label and only appears here); **"All tabs
   in <hub>"** folded (`_tabsHTML(false)`, unchanged). **No "Your next step". No "Practice mode" card. No "Take the tour"
   card** (the tour is a "Show me how" row on Home and a router trigger). Access-filtered like §4.4.
5. **Composer** (sticky bottom; `padding-bottom: env(safe-area-inset-bottom)`): one auto-growing textarea (1→5 lines,
   `data-coach="helper-composer"`), placeholder chrome `askAny` ("Ask a question, or tell me what to do…" when `can_act`;
   `askAnyNoAct` "Ask about this screen or your pay figures…"; fallback `askPlaceholder`), microphone (§6), Send
   (`send`, aria chrome `send`). Enter sends, Shift+Enter new line. Under it, one hint/error line (voice hints, errors).
6. The drawer is 480 px wide whenever the chat is mounted (replace `coach.scss:582-585` `:has(.lrn-dask-tab)` with
   `.lrn-drawer.lrn-has-chat`). Phone keeps the bottom sheet (`coach.scss:377-392`) at full width; its height is
   `min(88dvh, var(--lrn-vvh, 88vh))` where `--lrn-vvh` is set from `window.visualViewport.height` on its `resize`
   (iOS keyboard) — never a plain `vh`; the composer stays above the keyboard.

### 5.3 Turn kinds in the one stream (one visual language)
- **Person** (right, soft `#EDEAF8` bubble). A spoken turn shows a small `mic` glyph and aria "spoken".
- **Guide answer** (left, white card, 1 px `#E4E1F2` border, no shadow stack): a source label row ("From the guide" with
  `compass`; "Composed from the guide"; "About this screen"; "About this column"), then exactly what `_answerHTML` draws
  today for a hit (h4, blocks, tools). Tools row: Show me · Watch · **Practise this** (§5.6) · Say it more simply ·
  Open the lesson. An optional `lead` line above the h4 (guide_imperative / guide_offer) and `extra_chips` row below
  (a `primary` chip — "Do it for me" — is a solid button). A guide MISS appears only from step 18.
- **PayAI answer** (left): source label "From your pay data" (`bar-chart`) for intent `payroll_data`, else none; text,
  chart, insights, follow-up chips, "Show me" — unchanged rendering, restyled to the same card frame. Under a PayAI
  answer whose `action` is `open_walkthrough` for a scenario with `try`, add "Practise this". If the reply's intent is
  `error` and the route carried `fallback_key`, replace the error with `helper.answerFor(fallback_key)` drawn as a guide
  answer (no error shown).
- **Plan / done / blocked / refused / clarify cards** — `cards.xml` renders them exactly as today (anchors kept). Router
  `extra_chips` ("Explain how instead") render as a ghost chip row under the card.
- **Practice turn** (left, compact): `flask` + "Opening practice: Run a pay run — on the practice company, nothing real
  changes." Then `helper.startPractice(key, mode)` after a 600 ms beat (the drawer closes, as today). Practice chips
  turn: same frame, ≤4 chips + "Open practice mode".
- **Choice turn**: lead "Which did you mean?" (or, for `order_question`, "Do you want me to do it, or see how it
  works?") + ≤3 chips. Clicking a chip resolves WITHOUT re-routing: guide → `helper.answerFor(key)`; payai →
  `sendMessage({text, spoken:false, askOnly})`; practice → start.
- **Note turn** (left, info tone, one line): router notes, `no_payai`, nothing waiting, small talk (+ suggestion chips).
- **Consent turn** — the question-collection consent card (`askConsent`, `_consentHTML` 1027) is pushed into the
  stream as a turn (`helper.consentHTML(lang)`), with its existing `data-act` buttons handled by CoachHost's `onClick`.
  The voice consent card stays the chat's own (§6.7).
- **History marker** (only after a page reload, §5.1): compact line "From the guide: <label>" + "Show again"
  (`rotate-ccw`) which calls `answerFor(key)` and expands in place. Composed markers: "Composed from the guide — ask
  again to see it" (the answer is not stored; §7). Practice / choose / miss / note markers: one quiet line.
- Typing indicator: three dots in `#5A4BB0` at 40 % opacity, pulse (no shimmer gradient). New turns fade up 160 ms.

### 5.4 Sending (the one entry point)
- **New `sendMessage(opts = {})` signature** in the base chat: `opts = {text?, spoken?, askOnly?, fallbackKey?,
  pushPerson? = true}`. When `opts.text` is given it is used instead of `state.inputText` (the box is not read or
  cleared); when `pushPerson === false` no person turn is pushed (the composer already pushed it). The early return on
  `isLoading` stays ONLY for the no-`opts` legacy call; `submitComposer` manages `isLoading` itself and calls
  `sendMessage({..., _fromComposer:true})`, which skips that early return. `sendSuggestion(label)` keeps its legacy
  behaviour (sets `inputText`, calls `sendMessage()`), so every pb_payai_actions card path keeps working unchanged.
  The pb_payai_actions `sendMessage` patch already forwards `...arguments` (chat_patch.js:352); its `_extraSendKwargs
  (opts)` returns `{resolve}` when `_payaiResolve` is set, else `{voice:true}` iff `opts.spoken`, plus `{ask_only:true}`
  iff `opts.askOnly`.
- `submitComposer()`: `text = state.inputText.trim()`; `spoken = this._takeSpoken(text)` (§6.3); clear the box; push
  the person turn; `isLoading = true`; `r = await orm.call('learn.helper','route',[text],{screen_key, lang,
  session_id})`; dispatch: `payai` → `sendMessage({text, spoken, askOnly:r.ask_only, fallbackKey:r.fallback_key,
  pushPerson:false, _fromComposer:true})`; `guide` → push guide turn, `helper.onGuideAnswer(text, r.answer)` (CoachHost
  logs `coach_hit/miss` and runs `_maybeStore` exactly as `ask()` does — which may push the consent turn),
  `rpc_note_turn` (§7); `explain` → `await helper.explain()` then push + marker; `practice` / `choose` / `note` / `miss`
  → push the turn + marker (except `tap_card` notes). `isLoading` covers route + destination + marker; finally false.
- **What goes through the router, and what never does:**
  - Router: the composer; welcome suggestions; context-card "Not sure what to ask?" chips; PayAI `follow_up_questions`
    chips that carry no resolve; ⌘K hand-off text. These call `api.sendText(text, {origin})` → same as
    `submitComposer` with `spoken:false`.
  - **Never the router (straight to `sendMessage` / `sendSuggestion` as today):** any send while `_payaiResolve` is
    set; every chip that comes from a PayAI card (`payaiPick`, `payaiEdit`, chips with `chip.ask` → `payaiAsk`, follow-up
    chips with a resolve); `_takeHandoff`. Rule in code: `sendText` checks `this._payaiResolve` (via an overridable
    `_bypassRouter()` hook that pb_payai_actions implements) and, when true, calls `sendMessage()` directly.
- Header Explain and the moment card's `c-fvexplain` call `this.openHelper({explain:true})`: opens the drawer, queues
  until `attach`, then `api.pushGuide(await explain())`. With no chat attached (fallback) it pushes into the fallback
  stream. The moment card code itself is not edited beyond replacing its `this.explainScreen()` call with that.
- ⌘K: rewrite `pb_payai_actions/static/src/js/coach_patch.js` so `_payaiOpenHook(text)` calls the new public
  `CoachHost.openHelper({text, send:true})` (opens the drawer, waits for `attach`, then `api.sendText(text,
  {origin:'palette'})`). No `state.tab` anywhere. Rename the palette row to **"Ask the helper…"** (Q3 default; EN + VI
  in pb_payai_actions .po); it routes like the composer. The pill-side twin (`chat_patch.js:290-305`) stays for the
  hosted-off case.
- `askData` / `c-askdata` / `askDataLead` / `askDataInstead` are removed (routing is automatic).

### 5.5 Language — one source of truth
The header language pill decides everything: guide text (`RT.lang` AND the `lang` prop), every chat chrome string
(move the embedded chat's visible strings to Learn chrome and read them through `helper.T(key, lang)` — placeholder,
Send, Recording, Transcribing, Read aloud, Clear conversation, Pin to dashboard, welcome copy, mic labels, errors),
PayAI replies (send `context: {lang: 'vi_VN'|'en_US'}` on `rpc_send_message`, `rpc_helper_status`, `rpc_voice_status`,
`rpc_note_turn`, `rpc_transcribe_voice` — `set_lang(self.env.lang …)` in pb_payai_actions already follows `env.lang`).
Read-aloud picks its voice from the reply text, not the pill (§6.5). Fix `_restoreLang` and read-aloud to use
`user.lang` from `@web/core/user` (or `session.user_context.lang` from `@web/session`), never
`window.odoo.session_info`. Verify in OC2 whether the PayAI answer prompts produce Vietnamese when `lang=vi_VN`; if not,
add one line to each system prompt "Answer in Vietnamese" when `env.lang` starts with `vi` (report it).

### 5.6 "Practise this" rule
Show **one** "Practise this" chip (`flask`) under an answer when ALL hold: the answer carries a scenario key in `try`
(guide) or an `open_walkthrough` scenario (PayAI); that scenario is non-retired and `_offers(key, "try")` is true; it is
not `sc_access` for a person who cannot see Access. It replaces today's "Try" button (one label, not two) — **keep the
literal `this._offers(a["try"], "try")` in `_answerHTML`** (test_explain.py:434); only the label text and icon change.
Click → practice turn + `startPractice(key, 'try')`. Intents with try today: howrun→sc_payrun, whydiff→sc_payslips,
confidence→sc_import, newscheme→sc_blueprint, wherefrom→sc_mapjourney, notaddup→sc_treatment, changeroute→sc_matrix,
bulkupdate→sc_records, currency→sc_schemes, whosignsreview→sc_payreview, raisehire→sc_hiring,
confirmjoined/movecandidate/sharecandidate→sc_hiringrole, leaver→sc_exits, lockweek→sc_wfclose. OC4 adds
`try:"sc_people"` to `addperson`, and a try on the formula intent if one exists (else report). `explain_scenario_offer`
(learn_intent.py:608-624): keep `watch` from the first listed scenario, but take `try` from the first listed scenario
that HAS try. Resulting Explain offers (from §3.5): payruns → `sc_payslips`; runpayroll → `sc_payrun`; formula →
`sc_formula`; approvals → **none**; dashboard → none. Watch-only teaching answers show Watch only. `practice_key`
(missions) stays unused (non-goal).

### 5.7 Removals (OC2)
`nav.lrn-dtabs`, `TAB_ORDER`, `tabs`, `setTab`, `state.tab`, `bodyKey`'s tab part, `c-tab`, `c-askdata`, `c-continue`,
`_nextStepHTML`, `_continueHTML`, the practice branch of `bodyHTML`, `_practiceTryHTML` (its rows live in the context
card's "Show me how" and in practice chips), `_tourHTML`, `.lrn-dtabs/.lrn-dtab/.lrn-dask-tab/.lrn-cnext*` CSS, the
guide `<input>` form (fallback gets a textarea composer). **Keep `openSuggested`** (moment card). Stop emitting
`coach_tab`; KEEP the selection value `('coach_tab', …)` in `learn_progress.py:211` for old rows. Remove entries from
`COACH_ACTIONS` that are no longer emitted; declare every new `data-act` (test_coach test_08). If `bodyHTML` survives
only for the fallback stream, keep it reading `this.state.lang` (test_coach.py:587) or move that pin with it in the same
change. The embedded chat's FA icons → Lucide `<svg class="lrn-ic"><use href="#lrn-i-…"/></svg>` (the sprite
`pb_learn.IconSprite` is in the DOM via coach.xml).

## 6. Voice in the one chat (OC3)
### 6.1 Recommendation: the words wait in the box, one tap sends (keep)
Spoken text lands in the composer, highlighted, with the hint "This is what I heard. Edit it, then press Send." The
person taps Send (or presses Enter). Then the router runs exactly as for typing. **Why this, and not "show for a moment
then send":**
1. The consent every person already gave says "the text then waits in the box — nothing is asked or answered until you
   read it and press send" (`rpc_voice_status` copy; test_04e). Auto-send breaks that promise.
2. A misheard name or amount would reach the AI model, and a pay-figure answer could be READ ALOUD about the wrong
   person, before anyone saw the words.
3. Self-confirmation: with auto-send, a second voice in the room or the speaker itself could confirm an Amber plan with
   nobody touching anything. With a tap, the spoken go-ahead stays a deliberate act — and the locked rule ("Amber by
   voice only when the switch is on; Red never") is untouched.
4. The transcription service invents words on silence/noise; auto-send turns that into junk turns and wasted AI calls.
5. `rpc_transcribe_voice` stays unable to send (test_04b) without any test change.
The WOW comes from speed and feel, not from skipping the tap: tap-to-talk, a live level meter, the words appearing in
~1 s, the Send button turning solid `#5A4BB0` with one 1.04-scale pulse. **Focus stays in the textarea with the cursor
at the end** (never moved to Send — a keyboard user who starts/stops the mic with Space/Enter would otherwise send a
half-sentence with the next key press); Enter in the textarea sends. Owner question Q1 offers a later opt-in auto-send.

### 6.2 The microphone (one, in the composer)
- Shown when `voice.available || voice.ask` (as today); absent otherwise (no greyed button). `data-coach="helper-mic"`,
  Lucide `mic`, 40 px (44 px on phone), aria chrome `micStart` "Speak instead of typing".
- **Tap to start, tap to stop** (primary; works on phones). Press-and-hold still works: a press held > 400 ms stops on
  release. Space/Enter on the focused mic toggles. No new global shortcut. Escape while recording cancels the
  recording (its own rung in `_onKey`, §5.2) and does NOT close the drawer.
- "Listening" (the red dot, level meter and an optional soft start tone) appears **only after `MediaRecorder.onstart`
  fires** — before that the mic shows "Starting…", so nobody speaks into a recorder that is not yet running (a clipped
  first word turns "Don't go ahead" into "go ahead"). Pairs with the `_stopWanted` fix below.
- Recording bar replaces the textarea: red dot (`#DC2668`), live level meter (Web Audio `AnalyserNode`, 5 bars in
  `#5A4BB0`), timer "0:07 / 1:00", **Stop** (`square`, primary) and **Cancel** (`x`, discards — nothing is sent for
  transcription). Then "Turning your words into text…" (opacity pulse).
- **Short / silent gate (client):** a recording shorter than ~700 ms, or whose meter never passed a minimum level
  (track the peak RMS), is NOT uploaded; hint "I didn't hear anything. Tap the microphone and try again."
- Opening the mic first cancels any read-aloud (`speechSynthesis.cancel()`); read-aloud never starts while recording.
- 60 s ceiling (`MAX_RECORDING_SECONDS`) and server 8 MB cap unchanged.
- Bugs fixed (OC3): (a) permission race — a stop requested before recording actually started is remembered
  (`_stopWanted`) and applied the moment `MediaRecorder` starts, so no silent 60 s recording is ever sent; (b) any failure
  after `getUserMedia` releases the stream in the `catch`; (c) mime: `audio/webm;codecs=opus` → `audio/webm` →
  `audio/mp4` (Safari/iOS) → none = mic hidden with "This browser cannot record here."; the blob type and a server-side
  whitelisted file name follow the chosen type; (d) "Microphone access denied" only on `NotAllowedError`, translated via
  chrome; other errors say "This browser could not start the microphone."; (e) `touch-action:none; user-select:none;
  -webkit-touch-callout:none` on the mic; (f) iOS: prime `speechSynthesis` with an empty utterance inside the first mic
  tap so later read-back is allowed; (g) the level meter's `AudioContext` is closed inside `_releaseMicrophone`, AFTER
  the existing stop-tracks step (test_04b2's `_discarded` → chunks → `_releaseMicrophone()` order unchanged).
- The discard rule stays: closing the drawer, Escape, Cancel, or unmount sets `_discarded`, empties chunks, releases the
  mic, in that order (test_04b2 strings stay in `ai_insight_chat.js`). The kept audio for "Hear it as …" (§6.6) is
  dropped by the same steps and on Send.

### 6.3 The spoken flag (exact — provenance, not a sticky flag)
- Base chat keeps `this._heard = null` and `this._boxBeforeRecording = ''`. On mic start: `_boxBeforeRecording =
  state.inputText`. On a transcript: if `_boxBeforeRecording.trim()` is empty, the box becomes the transcript and
  `_heard = transcript`; else the transcript is appended (as today) and `_heard = null` (mixed typed + spoken = typed).
- `_takeSpoken(text)`: returns `_heard !== null && text.trim() === _heard.trim()`, then clears `_heard`. Any edit of the
  words (select-all and type "go ahead", type "go" then speak "ahead", fix a name) makes the send TYPED. ONLY
  `submitComposer()` calls it. Chips, suggestions, ⌘K hand-offs, choice chips: always `spoken:false` (today's
  `_payaiVoice` leaks onto any next send — fixed).
- pb_payai_actions: delete the `_transcribe` patch and `_payaiVoice` (`chat_patch.js:375-382`, 283); `_extraSendKwargs
  (opts)` returns `{voice: true}` iff `opts.spoken`. Server path unchanged (`payai_conversation.py:120-128` → `ctx.voice`).
- The router never sees the flag (§4.1). Spoken guide/practice turns use it only for read-aloud.
- **Hallucination filter (client, before the text reaches the box):** drop a transcript that, folded, equals or is
  only made of known filler outputs — EN "thank you for watching", "thanks for watching", "subtitles by …",
  "please subscribe"; VI "hãy subscribe cho kênh …", "cảm ơn các bạn đã xem" — or that equals/contains a run of ≥4 words
  from the vocabulary prompt (§6.6) (the service echoes its prompt on silence). Show the "I didn't hear anything" hint.

### 6.4 Go-ahead and decisions by voice (no rule changes — verify)
- Spoken "go ahead" / "làm đi" with an Amber plan waiting → router step 2 → PayAI with `voice:true` → `confirm(…,'voice')`
  only if `company.payai_voice_go_ahead` and `_is_latest`; else the runner's existing sentences.
- Red: router step 2 → PayAI → `_needs_typing`. The card's own word box is the only way to decide; our transcription
  fills only the composer, never the card's word box (keep `chatInput` the only transcription target). A spoken
  "APPROVE" sent from the composer with a Red plan open must decide nothing (test 3.6).
- **Known gap (ledger OC12):** the phone's or computer's OWN keyboard dictation can type into the card's word box, and
  the server sees typed text. Browsers do not reliably report dictated input, so we do not try to detect it (a false
  refusal would block a real typed decision). The typed word is still a deliberate act on the card itself.
- **"send it" is a go-ahead word** (`GO_AHEAD`). A truncated "send it back" heard as "send it" over an Amber "send
  payslips" plan confirms it when the company switch is on and the plan is latest. The read-back (which names the plan)
  and the onstart cue are the safeguards; walk W14 checks it; ledger OC13.
- Any non-PayAI turn between a plan and a spoken go-ahead → the marker (§7) makes the plan "not the last thing I
  showed you" → nothing happens (test 1.15).

### 6.5 Reading back
- Spoken turn: always read the reply — plan `card.speak` (as today); guide answers as plain text (render, then strip
  tags, `{{slots}}` already resolved by `gtx`, cap 600 chars, skip "Grounded in" source lines); PayAI text with markdown
  symbols stripped. **Pay figures are NOT read aloud by default (Q2 default changed):** a PayAI answer with intent
  `payroll_data` (or with a chart/insights) reads only "Here are the figures you asked for — they are on screen." A
  visible Stop control sits on any turn being read.
- Typed turn: read only when "Read answers aloud" is on (localStorage `payaiReadAloud`, unchanged), same figure rule.
- Check that every Amber/Red `card.speak` names the resolved MONTH as both name and number ("June, month 6") and each
  person's FULL name (resolver risks §3.3). The speak text is built in `runner.py`, which this program must not edit
  (§2): if it omits either, report it as a PayAI-program item and pin today's text (test 3.8).
- **Voice language from the text**: `utterance.lang = 'vi-VN'` when the text to read contains Vietnamese marks
  (`/[ăâđêôơưàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ]/i`), else `'en-US'`; pick a matching voice from `getVoices()` (wait for
  `voiceschanged`); no Vietnamese voice on the device → read nothing and show once "This device has no Vietnamese
  voice, so answers are shown, not read." Any new typing, mic tap or close cancels speech.
- **Branding filter on spoken text**: run the same debrand replacement used for displayed text (R7) over the string
  handed to `speechSynthesis` — never speak "Odoo".

### 6.6 Recognition language
`rpc_transcribe_voice(audio_base64, lang=None, mime=None)` (keyword args only; order of checks unchanged for test_04):
`lang` ∈ {'en','vi'} else None. **Default: auto-detect** — the client sends `lang=None` and the provider receives NO
`language` argument (omit it, never send null), with the prompt in the helper language as a hint. After a transcript
lands, the hint line offers **"Hear it as Tiếng Việt"** / **"Hear it as English"** (the other language): it re-sends the
SAME kept audio with that `lang` (about US$0.006; the audio stays in browser memory only until Send, Cancel, close or
unmount). `mime` whitelisted → file name `voice.webm|voice.mp4|voice.ogg`. Provider `transcribe_audio(audio_bytes,
language=None, filename='voice_recording.webm', prompt=None)`: pass `language` only when set; `prompt` = a fixed
product vocabulary per language, **nouns only, no decision verbs** (EN "Payobook, pay run, payslip, pay scheme,
overtime, BHXH, BHYT, BHTN"; VI "Payobook, đợt lương, phiếu lương, chương trình lương, tăng ca, BHXH, BHYT, BHTN") —
never employee names, never approve / send back / turn down / duyệt / gửi lại / từ chối. Log line becomes byte count +
character count only (no text). Cost stays ≈ US$0.006 per minute.

### 6.7 Consent, switches, errors, fallbacks
- **Consent copy is reworded for tap-to-talk** (substance of what leaves, who gets it, and when is unchanged; the
  gesture changes). New `consent_body` (EN): "Tap the microphone and speak. When you tap Stop, the recording goes to an
  outside company's speech service, which turns it into text. Tap Cancel and nothing is sent. The recording is audio:
  unlike text, we cannot take names out of it first. The text then waits in the box — nothing is asked or answered
  until you read it and press send. Say no and the microphone stays off. Everything else works the same." VI in
  pb_payroll_ai_insights `vi_VN.po`, keeping 'công ty bên ngoài', 'không thể bỏ tên riêng', 'nằm chờ trong ô nhập' and
  replacing 'khi bạn thả tay, bản ghi âm sẽ được gửi' with 'khi bạn bấm Dừng, bản ghi âm sẽ được gửi'. `hold_hint` →
  `tap_hint` 'Tap to speak' / 'Bấm để nói'. **Update test_04e in the same change**: find the body by 'Tap the microphone
  and speak'; EN claims 'When you tap Stop, the recording goes', "outside company's speech service", 'cannot take names
  out of it', 'The text then waits in the box', 'Tap Cancel and nothing is sent'; VI 'khi bạn bấm dừng, bản ghi âm sẽ
  được gửi' (lower-cased), 'công ty bên ngoài', 'không thể bỏ tên riêng', 'nằm chờ trong ô nhập'; keep the NOT
  'Nothing is sent until' assertion and test_04f's register gate. Whether this counts as new substance that needs
  people who said yes to be asked again is **owner question Q5** (default: no re-ask; the change makes the recording
  leave LATER and adds a way to send nothing). If the owner says re-ask, add `payroll.ai.consent.copy_version` (Integer)
  and treat `granted` with an older version as `unset`.
- "Use my voice" in the More menu re-opens the consent card after a past "no".
- `rpc_voice_status` gains `switch_on` and `provider_ready` (booleans) so the menu knows when "Use my voice" makes sense.
- Errors keep the server's plain sentences; client-side ones move to chrome (EN+VI).
- No speech service / switch off / declined → no microphone; the composer still works. Fallback (guide-only) stream →
  no microphone (voice needs the assistant's speech service) — say nothing about voice there.
- Learning settings "Talk to the helper" body (`swVoiceBody`): "Adds a microphone to the helper chat. People speak, check
  the words, then press Send. Recordings go to the speech service only to be turned into text."

## 7. One conversation (OC1 server, OC2 client)
- The person's single `payroll.ai.conversation` (`get_or_create_session`) is the thread for the drawer on every screen.
- New `payroll.ai.conversation.rpc_note_turn(session_id, kind, key=None, source_kind=None, screen_key=None)` in
  pb_payroll_ai_insights:
  - **Ownership**: `session = self.browse(int(session_id)).exists()`; refuse (`AccessError`, plain sentence) unless
    `session.user_id == self.env.user` — the managers' read-all rule must never let one person write markers into
    another's thread (that would change their `_is_latest`). `session_id` null → `get_or_create_session()`.
  - **Inputs**: `kind` ∈ {'guide','composed','explain','practice','choose','miss','capability','note','smalltalk'}
    else refuse. `key` must exist in `learn.content` for that kind (intent key / column key for guide; screen key for
    explain; scenario key for practice; chrome key for note/smalltalk/miss/choose; capability → none) else refuse.
    `source_kind`, `screen_key`: each ≤ 64 chars, `[a-z0-9_]` only, screen key must exist. **`task_id` is never written
    from any argument** (the signature has none and the card is built server-side), so a marker can never make an old
    plan "latest".
  - Writes ONE assistant `payroll.ai.message` with `intent='helper_note'`, `content` = an AUTHORED label looked up
    server-side from `learn.content` by key in `env.lang` (intent label; column label; "Explain this screen: <screen
    label>"; scenario name; composed → "Composed from the guide"; note → the chrome sentence), `card` =
    `{kind, key, source_kind, screen_key}` (no `task_id`). **It never accepts or stores client text** → guide question
    privacy holds; the person's own guide question is not stored either (no user message row for non-PayAI turns).
- **Markers for every non-PayAI turn the chat shows** — guide, composed, explain, practice, choose, miss, capability,
  small talk and notes — EXCEPT `tap_card` notes (those are about the plan itself and must not make it "not latest").
  A `choose`, `miss` or capability turn after a plan therefore stops a later spoken go-ahead from confirming it.
- Base `_loadHistory` maps a history row with `intent == 'helper_note'` (or `card.kind` in the list above) to a marker
  turn and sets `card=null` so `cards.xml` never sees it. `rpc_send_message` builds the LLM history WITHOUT rows whose
  intent is `helper_note` (no change to what reaches the model).
- Why markers: `_is_latest` (non-reason) reads the newest assistant message → a marker after a plan cancels a spoken
  go-ahead ("That plan is not the last thing I showed you…"); with a reason question open, `past_answers` searches
  `card != False` and skips cards without `task_id` → the reason question stays open across a guide answer. Both are the
  runner's existing semantics.
- `rpc_helper_status(session_id=None)` (new, one call on mount): `{session_id, voice:<rpc_voice_status>, can_answer:
  learn.helper._payai_available(), can_act: learn.helper._can_act(), voice_go_ahead: company.payai_voice_go_ahead
  (pb_payai_actions), icon_url}`. pb_payai_actions supplies `can_act` (tier `look` on for the company).
- **Clear conversation**: confirm inline "Clear this conversation? Plans waiting for you stop working." → existing
  `rpc_clear_history`; additionally (pb_payai_actions override of `action_clear`) mark this person's `planned`/`clarify`
  tasks in that session `expired` (they are already harmless via `_is_latest`; this makes the audit say so). The
  `_LRU` fix (§8 R9) makes old names unreachable. The client also empties the in-memory turn store for that session.
  With `sessionId` null, nothing to clear — draw the empty state.
- Fallback stream (no chat): in memory for the page's life; kept across close and screen changes (a context divider marks
  each new screen). Today's "wipe on close" comment (`coach.js:142-144, 714-716`) is replaced by this rule.

## 8. Safety rails (bind every phase)
- **R1** A routed command goes through the unchanged server `rpc_send_message` path; PayAI tiers, gates, Access-home
  check (PA-R1), sudo ban (PA-R2), id rule (PA-R3) untouched.
- **R2** `route()` has no voice parameter, stores nothing, calls no model; only step 16 (flag-gated composer, only where
  PayAI is unavailable) and PayAI destinations call models.
- **R3** Practise trigger before commands, anchored, never for a question; "Do it live" never offered under "practise";
  `sc_access`, Access doors and Access lesson/Watch/Show-me never offered to a person PayAI would refuse
  (`gate.door_denied`, `ACCESS_LEARN`; in pb_learn `_station_reach` for the Access sidebar key) — including
  screenless-pass answers.
- **R4** Transcript never auto-sent; `rpc_transcribe_voice` never sends (test_04b); discard on close (test_04b2).
- **R5** Spoken = the sent text equals exactly what was heard into an empty box (§6.3); chips never spoken; Red never
  by voice (server, unchanged); Amber by voice only with the company switch and the latest plan (server, unchanged).
- **R6** Guide question text is never stored or logged; markers carry authored labels only; mining stays consent-gated;
  `rpc_note_turn` checks ownership and validates every argument.
- **R7** No "Odoo" in any user-visible string or spoken text; plain screen words; Lucide only; locked palette.
- **R8** `process_message` catch-all (`payroll_ai_engine.py:~412`) must not show exception text: log it, answer
  "Something went wrong on my side. Please try again, or ask your administrator to check the assistant settings."
  (EN+VI, `_()`), intent `error` — and the client shows the guide `fallback_key` answer instead when it has one.
- **R9** `_LRU` (exception E1): key = `(env.cr.dbname, user.id, conversation.id or 0, redacted text)`, and the stored
  value is the AI's slot texts **with placeholders still in them** (`[person-n]` etc., i.e. before `restore_names`); on
  a hit (and on a miss, after the call) restore with the CURRENT mapping: `restore_names(val, mapping)`. Because the
  stored value never holds a real name, a Clear (numbering restarts) or another worker process can never surface an
  old name. Test 3.9.
- **R10** One addons directory: pb_learn and pb_payroll_ai_insights JS reaches rize, payobook_template and abm at the
  next restart. The one chat must work there with no pb_payai_actions (no cards, no ⌘K hook, no spoken go-ahead, no
  `ask_only` kwarg sent) and with an inactive AI service (guide + practice fully work; data questions get a guide answer
  when one exists, else the `no_payai` note with a next step — `_payai_available()` is False when the provider is
  missing, inactive or not available).
- **R11** `ask_only` (exception E2) can only remove PayAI's command path for a question-shaped send; it never adds one.
- **R12** Card chips and any send with `_payaiResolve` set bypass the router (§5.4).
- **R13** Cost: no turn chains the guide composer into PayAI; small talk, empty/junk audio and bare words never reach a
  model; a question costs at most PayAI's classifier + answer.

## 9. Files you will touch (expected)
pb_learn: `models/learn_helper.py` (new), `models/__init__.py`, `models/learn_intent.py` (`_score_kind`,
`_resolve_scored`, `probe`, `answer_for`, Access filter, `explain_scenario_offer` try rule, scenario `practice_probe`),
`static/src/coach/coach.js|xml|scss`, `static/src/journey/icons.xml` (add mic, square, volume-2, volume-x, ellipsis,
trash-2, scan-text), `static/src/anchors.json` (helper-composer, helper-mic; helper-orb desc "Opens the Payobook
helper chat"), tests. Content: `docs/tutorial_poc/author/data.js` (+ regenerate `learn_content.json`; PA54),
`gen_learn_data.py` (scenario `match`→`phrases`, duplicate refusal), `contract.json` (learn_helper.py in the files list).
pb_payroll_ai_insights: `models/learn_helper.py` (new), `models/payroll_ai_conversation.py` (`rpc_note_turn`,
`rpc_helper_status`, `rpc_transcribe_voice` kwargs, consent copy, LLM-history filter), `models/payroll_ai_engine.py`
(R8), `ai_providers/openai_provider.py`, `static/src/components/ai_insight_chat/ai_insight_chat.js|xml|scss`,
`i18n/vi_VN.po` (+ `.pot` if the module ships one — PA58), `tests/test_egress.py` (test_04e), tests.
pb_payai_actions: `models/learn_helper.py` (new), `models/payai_conversation.py` (`rpc_send_message` `ask_only`,
`action_clear`), `models/payai_engine.py` (`payai_ask_only`), `payai/runner.py` (R9 only),
`static/src/js/chat_patch.js`, `static/src/js/coach_patch.js`, `static/src/js/payai_palette.js` (row label),
`static/src/xml/cards.xml` (only if anchors move — they should not), `i18n/vi_VN.po`, tests incl. `tests/js/`.

## 10. Learn content, lessons, tour, settings (OC4 — "lessons follow screen changes")
Edit `data.js`, regenerate with `gen_learn_data.py`, then `git checkout pb_learn/i18n/vi_VN.po
pb_learn/static/src/engine/fixture.js` (PA54); commit only `data.js` + `learn_content.json` (+ generated anchors/xml if
they changed legitimately).
- Retire: `tabGuide/tabAsk/tabPractice` (en 368-370 / vi 722-724), `nextStep` (371/725), `askDataInstead`,
  `askDataLead` (373-374/727-728); stale comment data.js:359-364.
- Reword (EN + VI): `helperFailed` (130/550) and `LOAD_FAILED` (coach.js:63-66) — no "Ask tab"; `coachNoScreen` (333);
  `honest` → `honestAct/honestAsk/honestGuide`; `swVoiceBody` (467/814, §6.7); `swNextBody` (460/807) → "The lesson map
  shows one next lesson." Keep `notSure`, `explainScreen`, `explainHint`, `screenAnswer` (test_explain 07b).
- New chrome keys (EN + VI): `askAny`, `askAnyNoAct`, `send`, `close`, `more`, `readAloud`, `readAloudOn/Off`,
  `clearConv`, `clearConvConfirm`, `useVoice`, `micStart`, `micStop`, `micCancel`, `micStarting`, `recording`,
  `transcribing`, `heardNothing`, `hearAsVi`, `hearAsEn`, `micDenied`, `micCannot`, `noViVoice`, `figuresOnScreen`,
  `fromGuide`, `fromPayData`, `composedFromGuide`, `aboutScreen`, `aboutColumn`, `whichMeant`, `doOrHow`, `doItNow`,
  `howItWorks`, `practiseThis`, `openingPractice`, `watchOnlyNote`, `nothingWaiting`, `cannotActHere`, `typeWordOnCard`,
  `tapCancel`, `smalltalk`, `noPayai`, `hereIsHow`, `hereIsHowOrPrepare`, `doItForMe`, `askPayData`,
  `explainHowInstead`, `showAgain`, `jumpLatest`, `nowOn`, capability card blocks. Vietnamese: "chương trình lương" for
  scheme (PA53); natural, short; no "Odoo". (`tapDoIt` copy reuses the runner's msgids, §4.3 step 4.)
- Scenario `match` phrases for every non-retired scenario (EN, VI with marks, VI without marks), ≥3 each; ≥6 for
  sc_payrun, sc_payslips, sc_import, sc_people, sc_wfclose, sc_hiring, sc_welcome; `sc_wftime` includes "approve
  overtime" / "duyệt tăng ca".
- `addperson` intent: `try: "sc_people"`. VI phrases for the guide's top gaps: "bhxh là gì", "bhyt là gì", "lương thực
  nhận là gì", "chạy lương thế nào", "cách chạy lương" (and unaccented) on the existing intents.
- Lesson LW (data.js:3562; step ~3626-3630): body says "It explains — you act. It never…" (false on payobook) and
  promises "what to do next" (gone with "Your next step"). Split with `requires`: base step "The helper on every screen
  answers questions and opens a safe practice copy. Type, or speak if your company has turned voice on."; a
  `requires:"payai_prepare"` step "Ask it to do something and it shows you the plan first; nothing changes until you
  tap Do it." Drop "what to do next" (the Explain answer still ends with a next step — Q7). Optionally anchor to
  `helper-composer`.
- PayAI P4 steps (data.js:3096-3109, 3740-3745): "Type … to PayAI" → "Type … into the helper" (Q3 default). The Red tip
  ("A tap or a spoken yes never counts") stays.
- Tour `sc_welcome` last step `copilot` (data.js:10196-10202): "Ask the helper anything — type it, or speak it when voice
  is on. It answers, opens a safe practice copy, and when your company allows it, prepares the work and shows you the plan
  first." Split the "prepares" clause behind `requires:"payai_prepare"` if the tour supports `requires`; else keep it
  without that clause.
- Tour VI name mismatch: use "Đi một vòng Payobook" for both the scenario and any label that named it.
- PayAI .po: the consent copy and `tap_hint` (§6.7); palette row "Ask the helper…" / VI.
- Docs that describe the tabs (update text only): PAYAI_PROGRAM.md:30, PAYAI_CLOSEOUT.md:8/46, P1_HANDOVER.md:193,
  `docs/design/payai-does-it.html:345, 423`, LEARN_REFRESH_LEDGER.md:5, STEP2_PAYROLL_CORE.md:192.

## 11. Tests (numbered; server tests run on the clone per PA10/PA50; keep every existing test green or update it in the
same change and say why)
### OC1 — server
1.1 Routing corpus §4.8, both columns (B = `patch.object` `_route_command`/`_route_payai_state`/`_capability_route` to
the base behaviour and `_payai_available` to False), EN + VI, on `payruns`, `approvals`, `dashboard`, and screenless.
Asserts `route`, `why`, and `ask_only` where the row says so.
1.2 `route` never writes: row counts of `payroll.ai.message`, `payai.task`, `learn.question`, `learn.event` unchanged.
1.3 `route` makes no model call: patch the provider's `generate_text/generate_chat/generate_tools` to raise; every corpus
row except composed rows still routes.
1.4 Composer only on step 16: with `COMPOSE_FLAG` on and `_payai_available` True, NO sentence calls `generate_text`;
with it False, a command / data / practise sentence never calls it.
1.5 Practise before commands: "let me practise running payroll" on payobook with tiers on → `practice`, no task row.
1.6 Open question first: create a clarify task with a typed reason question (reuse FIX-1 fixtures) → "Approve the
overtime first", "Practice of paying overtime twice must stop", "explain this screen is wrong", "yes", "thanks" → all
`payai open_question`; a how-to question → still `payai open_question` (PayAI decides).
1.7 Go-ahead and bare words: planned Amber task → "go ahead" → `payai goahead`; no task → `note nothing_waiting` with
the can-act wording on P and the "I can't do things for you here" wording on B; "yes" with an Amber task → `tap_card`
"Tap Do it to go ahead." (switch off) / "Tap Do it or say go ahead." (switch on + voice offered); with a Red task →
"Type <WORD> in the box on the card."; "cancel" → "To stop, tap Cancel…".
1.8 Look tier off (company switch) → "approve the request waiting for me" → not `payai command`.
1.9 `probe`: kinds reported separately from the on-screen bonus; screen pass + screenless pass ("what is BHXH" on
payruns → key, scope any); tie at floor → None; advice guard → compliance. `_score` and `_resolve_hook` results
unchanged on the whole existing test suite.
1.10 `ask()` miss payload keys still exactly `{'matched','capability','suggest'}` (test_02b green).
1.11 `answer_for(key)` == `ask(label)` hit payload for 10 intents; unknown key → miss payload.
1.12 Scenario phrases: generator refuses a duplicate; every non-retired scenario has ≥3 phrases in each language;
`practice_probe` maps the sample sentences correctly; "try again", "Làm thủ tục nghỉ việc cho Lan", "làm thủ công",
"nhân viên mới đang tập làm quen", "Practice of paying overtime twice must stop" are NOT triggers; "show me the tour",
"start the tour", "open the practice company" ARE; "how do I get off the practice company?" is not a practice start.
1.13 `explain_scenario_offer` try: payruns → `sc_payslips`, runpayroll → `sc_payrun`, formula → `sc_formula`,
approvals → none, dashboard → none; watch unchanged on all five.
1.14 `rpc_note_turn`: writes one assistant row with authored content in the requested language, `intent='helper_note'`,
card without task_id; it has no text parameter (signature check); `get_history` returns it; LLM history in
`rpc_send_message` excludes it (patch `process_message` and inspect `conversation_history`). **Refusals**: another
user's `session_id` (as a payroll manager with read-all) → AccessError, no row; unknown `kind`, unknown `key`,
over-long or non-`[a-z0-9_]` `source_kind`/`screen_key` → refused, no row.
1.15 Spoken go-ahead after a marker: planned Amber task (company voice switch ON) → `rpc_note_turn` of each kind
guide / choose / miss / capability → `rpc_send_message("go ahead", voice=True)` → nothing confirmed, "not the last
thing I showed you" card; without the marker → confirmed `confirm_kind='voice'`.
1.16 Reason question open → guide marker → typed reason still accepted (past_answers path).
1.17 `rpc_helper_status`: `can_act` true on a payobook-like company with look on, false with look off and on base;
`can_answer` false with an inactive config AND false with an active config whose provider `is_available()` is False.
1.18 R8: force an exception inside a route → the answer has no exception text and no model name; intent `error`.
1.19 Contract check passes with `learn_helper.py` added (`check_contract.py`).
1.20 `inspect.signature(learn.helper.route)` has no voice-like parameter.
1.21 `ask_only`: `rpc_send_message("can I approve the June run?", ask_only=True)` with the provider's `generate_tools`
patched to raise → no tools call, no task row, question-path answer; `ask_only=True` + "go ahead" with a planned task →
still confirms (tap rules); `ask_only=True` + an open reason question → still taken as the reason; `ask_only=False`
→ today's behaviour (tools call reached). Base module `rpc_send_message` signature unchanged.
1.22 Access filter: "delegate my access" on payruns as a person without Access → no Watch / lesson / Show me offer and
no `sc_access` anywhere in the payload; as an Access admin → offered.
1.23 Small talk: "thanks", "hi", "ok", "uh", "ờ" → `note smalltalk`, no model call (patch to raise).
### OC2 — client (node tests where a precedent exists: `pb_payai_actions/tests/js/client_fix.test.mjs`; source-pin
tests in Python like test_coach)
2.1 Source pins stay green: COACH_ACTIONS literal + every emitted `data-act` declared; `_answerHTML(` without doAction;
`this._offers(a["try"], "try")` (test_explain test_06, :434); `"learn.intent", "explain_screen"`; explainScreen without
`_maybeStore`; `this._log(answer.matched`; `data-act="c-practice"` in coach.js + `openLearn(this.action, "practice")`
(test_practice test_08, :321-328); `get bodyHTML()` reads `state.lang` (test_coach :587) or the pin moved with it;
`maybeWelcome` order; `markLauncherStack`; IconSprite call; every `#lrn-i-…` and `ic("…")` exists in icons.xml;
test_assets test_06 (Escape ladder) green with the new menu and recording rungs.
2.2 New pins: no `lrn-dtabs`, `c-tab`, `c-askdata`, `c-continue`, `_nextStepHTML`, `state.tab` in pb_learn and
pb_payai_actions JS/XML; `openSuggested` still present and called by `_momentAct`; no `fa-` class in
`AiInsightChatEmbedded`; every `#lrn-i-` used in ai_insight_chat.xml exists in icons.xml; no `session_info` read
anywhere in these modules; no `bar-chart-3`.
2.3 Node — spoken provenance: speak into an empty box + Send → spoken; speak, then select-all and type "go ahead" →
typed; type "go", speak "ahead" → typed; speak, fix one word → typed; speak, Send, then a chip → chip not spoken; empty
box resets; `_extraSendKwargs({spoken:true})` → `{voice:true}`, `{askOnly:true}` → `{ask_only:true}`, `{}` otherwise;
`_payaiResolve` set → `{resolve}` only.
2.4 Node: route dispatch table — each route value draws the right turn kind; `choose` chips resolve without a second
`route` call; `payai` route calls `sendMessage` with `pushPerson:false` and exactly ONE person turn exists; a PayAI
`error` reply with `fallback_key` draws the guide answer.
2.5 Node — chip bypass: with `_payaiResolve` set, `sendText` / `sendSuggestion` never call `learn.helper.route`;
`payaiPick` / `payaiEdit` / a `chip.ask` chip / follow-up chips with resolve reach `rpc_send_message` with their
resolve; a plain follow-up chip and a welcome suggestion DO call `route`.
2.6 Node — language: flipping `lang` re-renders past guide turns in the other language; notes too.
2.7 Node — close/reopen keeps full guide answers (no markers); a fresh page load shows markers.
2.8 Node — queue: `c-fvexplain` before attach → the Explain answer appears once after attach; ⌘K text before attach →
routed once.
2.9 Anchors: `helper-composer`, `helper-mic` present in anchors.json and referenced or `reserved` (test_anchor_registry).
2.10 White-label scan: no "Odoo" (any case) in new/changed chrome strings, .po msgstr, templates, JS string literals
and the spoken-text path of the three modules.
### OC3 — voice
3.1 test_egress 04/04b/04b2 green with the new kwargs (order unchanged; no send in the transcriber); **test_04e updated
to the tap-to-talk copy** (§6.7) and green; test_04f green on the new copy.
3.2 `rpc_transcribe_voice(lang='vi')` passes `language='vi'` and the VI prompt; `lang=None` passes NO `language`
argument at all (assert the kwarg is absent); bad `mime` → refused with a plain sentence; the prompt contains no
decision verb in either language.
3.3 Provider log line contains no transcript text (capture the logger).
3.4 Node: stop-before-start → recorder stops as soon as it starts; "Listening" shows only after `onstart`; a
`MediaRecorder` constructor failure releases the stream; mime fallback order; `AudioContext.close` called inside
`_releaseMicrophone`; a 400 ms recording and a silent recording are not uploaded; a transcript equal to "Thank you
for watching" / the vocabulary prompt is dropped; Escape while recording cancels the recording and leaves the drawer
open.
3.5 Node: mic tap cancels `speechSynthesis`; read-aloud voice lang follows the reply text (Vietnamese marks → vi-VN);
spoken text passes the debrand filter; a `payroll_data` answer reads only the "figures are on screen" line.
3.6 Red by voice: Red plan waiting; composer send "APPROVE" with spoken=true → no decision, task still planned;
"go ahead" spoken → `_needs_typing` card.
3.7 Amber by voice with the company switch OFF → refused sentence; ON and latest → confirmed `voice`.
3.8 Read-back: spoken Amber plan returns `card.speak`; typed does not. Record whether `card.speak` names month name +
number and full person names for `run_payroll`, `send_payslips`, `approve_item` (report; do not change the runner).
3.9 R9: a hit after Clear (numbering restarted, same redacted text) restores the CURRENT person's name; two
conversations and two DB names never share an entry; the stored value contains no real name.
### OC4 — content
4.1 `gen_learn_data.py --check` clean; vi_VN.po and fixture.js unchanged in git after generating (PA54 restore done).
4.2 test_feature_gate cases for the split LW step and the tour step.
4.3 Every new chrome key exists in en and vi; no retired key referenced by any JS.
4.4 pb_learn, pb_payroll_ai_insights, pb_payai_actions full suites; PA11/PA40/PA55 environmental failures read out, no
new failures vs HEAD.

### Browser walk (Chrome MCP; mandatory; console clean; PA24/PA42 apply) — on the clone first, then payobook.com with
the QA login after Fable's deploy
W1 Open with `?`: one chat, no tabs, banner variant correct, context card with "Not sure what to ask?" chips, no "Your
next step". W2 "how do I approve a request" → guide card "From the guide", tools row, Practise this only where a try
exists. W3 "approve the request waiting for me" → Red plan card + "Explain how instead"; tap the chip → guide answer.
W4 "run June payroll for Retail" → Amber plan card; Do it untouched (cancel it); pick a card chip ("Change Period") →
the card answers (not routed). W5 "how many employees do we have" → "From your pay data" answer. W6 "let me practise
running payroll" → practice turn → Learn hub opens on the sc_payrun try. W7 "lock the week" on the clone without act →
"Here is how you do it." W8 Weak sentence → "Which did you mean?" two chips; "Run payroll?" → "Do it now / How it
works". W9 Explain this screen from the header after a PayAI answer → appears in the stream; moment card "Explain" from
a closed drawer → appears once. W10 Tiếng Việt → past guide turns, chat chrome, PayAI reply, placeholder all
Vietnamese; back to English. W11 Close + reopen → full guide answers kept; reload → PayAI turns and guide markers
("From the guide: …" + Show again) come back. W12 Clear conversation → confirm → empty state. W13 ⌘K "Ask the helper…
open the runs board" → drawer opens, sentence routed, board opens. W14 Voice (switch "Talk to the helper" ON on the
CLONE only): consent card (tap-to-talk copy) → tap mic → "Starting…" then "Listening" → speak "how do I run payroll" →
words in the box, focus in the box → Enter → guide answer read aloud; speak "go ahead" after an Amber plan with the
company switch OFF → refused sentence; ON → done card; speak then edit one word → sent as typed (no voice go-ahead);
Red plan + spoken go ahead → "type the word"; speak "send it back" over an Amber "send payslips" plan and confirm the
read-back names the plan (note the "send it" risk in the report); tap mic and stay silent → "I didn't hear anything",
nothing uploaded (network panel); Escape while recording → recording cancelled, drawer open; close mid-recording →
nothing sent. W15 Vietnamese voice: "chạy lương thế nào" → recognised in Vietnamese with auto-detect; "Hear it as
English" re-transcribes. W16 Phone width 390 px (emulate): bottom sheet, tap-to-talk, composer above the keyboard
(visualViewport), no horizontal scroll. W17 rize-like clone without pb_payai_actions and with an inactive AI service:
guide, explain, practice work; "how many employees" → `no_payai` note with a next step; "how do I compare two pay runs"
→ guide answer; "go ahead" → "I can't do things for you here…"; no mic; no console errors.

## 12. How to run tests and rehearse (unchanged from PayAI; PA10, PA14, PA37, PA38, PA50)
ssh `Payobook19v2`. Never touch `/odoo/odoo-server/addons`, never restart `odoo-server`, never use port 8069, never run
against `payobook`, `rize`, `payobook_template`, `abm`. Stage from `git archive HEAD <modules>` + overlay this phase's
modules from the working tree (PA38; other sessions' uncommitted pb_learn/pb_dashboard work must not ride along). Clone
`p0clone` (shared — check PA37 before launching); detached `systemd-run` test units, poll sentinel, grep
`FAIL:|ERROR: Test|odoo.tests.stats|EXIT=`; put every module whose tests you want in `-u` (PA35). Walk server on 8099
only, ≥ 600 MB free (PA21), stop it after. For the B-column walk (W17) make a second clone from `payobook_template`
(pb_payai_actions uninstalled there) with crons and mail servers off; drop it after. Clone DBs are internet-reachable —
never leave a clone login active (memory clone-db-internet-reachable).

## 13. Deploy (Fable only; risky tier — full ritual; payobook-first)
- Modules: `pb_learn` (new model + content + JS), `pb_payroll_ai_insights` (new RPCs + JS + .po + consent copy),
  `pb_payai_actions` (JS + new model + engine flag + .po). No new stored fields (markers use the existing `intent` Char
  and `card` Text columns) — unless Q5 says re-ask, which adds `payroll.ai.consent.copy_version`.
- Because files are shared (one addons dir) the new pb_learn / pb_payroll_ai_insights JS and Python reach EVERY database
  at restart. New Python methods on already-installed modules work after restart; translations need `-u`. Plan:
  `-u pb_learn,pb_payroll_ai_insights,pb_payai_actions` on **payobook** first; then `-u pb_learn,pb_payroll_ai_insights`
  on **rize, payobook_template, abm** in the same sitting (their bundles will already run the new JS — stale
  translations and the old voice status shape would otherwise show; abm: re-disable crons after its upgrade, memory
  abm-tenant-retired). Record in `docs/deploy/PENDING.md` if the owner holds any DB back.
- Before: PA60 dry-run `rsync -rcn --delete` staged commit → live per module; `latest_version` on all DBs (PA41/PA57);
  backup dump of payobook. After: `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` per DB, bump
  `web.assets.version`, restart once; hash every module tree both sides; manifest vs `latest_version` per DB.
- Do NOT switch on "Talk to the helper" or the spoken go-ahead switch during deploy (Q4).
- Commit per feature (OC1…OC4), push 19.1, scan for passwords first.

## 14. Report back (one `OCn_REPORT.md` per phase in this folder)
Test results with counts (paste stats lines); routing corpus table with observed values for "record" rows; browser
walk record with screenshot list; design-bar self-score; every OC ledger row added; deviations with reasons; anything
that changes what is stored or sent outside; the Vietnamese answer-language finding (§5.5); the `card.speak` month /
name finding (3.8); list of chrome keys added and retired; open items for the next phase.

## 15. Ledger seed (copy into ONECHAT_LEDGER.md)
| # | Fact | Apply |
|---|---|---|
| OC-R1 | Routing never calls a model and never sees the voice flag. | Keep `route()` pure + signature test. |
| OC-R2 | Guide questions are never stored; markers carry authored labels only. | `rpc_note_turn` has no text arg, checks owner + key. |
| OC-R3 | Markers are what keeps `_is_latest` honest across non-PayAI turns. | Every non-PayAI turn except `tap_card` writes one. |
| OC-R4 | Card chips answer a card; a router would turn "Cancel" into a guide miss. | Any send with `_payaiResolve` / card chip bypasses the router. |
| OC1 | The guide scores imperatives at 100 — a high guide score is not "not a command". | Command check before guide; on a can-act DB an imperative goes to PayAI unless the guide match is exact. |
| OC2 | Guide candidates are screen-filtered; "what is BHXH" misses on Pay Runs. | `probe` runs a screenless pass at floor 55 — and the Access filter applies to it. |
| OC3 | `test_composer test_02b` pins the miss payload keys. | Scores only via `probe`, never on `ask()` misses. |
| OC4 | `explainScreen` used to draw nothing on the Ask/Practice tab. | It pushes into the stream now (queued until attach); walk W9. |
| OC5 | Read-aloud language read `window.odoo.session_info` (absent in Odoo 17+) → always en-US. | Pick the voice from the reply text. |
| OC6 | Transcripts were logged at INFO by the OpenAI provider. | Log counts only. |
| OC7 | `_payaiVoice` leaked onto chips and hand-offs. | Spoken = sent text equals what was heard into an empty box. |
| OC8 | "Talk to the helper" (DB-wide) and spoken go-ahead (per company) are separate switches, both off live. | Demos need both; never switch on during deploy. |
| OC9 | Scores carry a +25 screen bonus; "80" can be a two-word overlap. | Threshold on `kind`, never on the score. |
| OC10 | `ask_model` makes a plan from ANY non-question the phrase table misses, and `looks_like_question` misses many questions. | Router sends question-shaped sentences with `ask_only`. |
| OC11 | `_onKey` is document-capture: it runs before any element handler in the drawer. | New Escape rungs (menu, recording) live inside `_onKey`, each with a `close(` call (test_06). |
| OC12 | Device keyboard dictation into the Red card's word box counts as typed. | Known gap; not detected; the word box is still a deliberate act. |
| OC13 | "send it" / "run it" are go-ahead words; a clipped "send it back" can confirm an Amber send. | Read-back + onstart cue; W14 checks. |
| OC14 | The transcription service echoes its prompt and invents filler on silence. | Short/silent gate, filler filter, nouns-only prompt. |
| OC15 | Provider forced `language='en'`; Vietnamese speech came back garbled. | Auto-detect; omit the argument; "Hear it as …" re-transcribe. |
| OC16 | `RT.lang` is not reactive and `helper` never changes identity. | Pass `lang` as a prop; turns store payloads, render at draw time. |

## 16. OWNER DECISIONS 2026-10-14 (binding — this section WINS over any other text in this handover)
- **Q1 Voice sending → WAIT FOR A TAP.** Spoken words land in the box; nothing is sent until the person presses Send.
  No countdown, no auto-send (as §6.1).
- **Q2 Pay figures read aloud → NO.** Plans and how-to answers are read; amounts are not spoken — the helper says
  "the figures are on screen" (as the §6.5 default).
- **Q3 Name → "PayAI" everywhere in the chat** (owner chose this over "Payobook helper"). The drawer title is "PayAI"
  (the "On: <screen>" line stays), the launcher's accessible label / tooltip says PayAI, the ⌘K row stays
  "Ask PayAI to…", lessons keep "… to PayAI" / "Hỏi PayAI", and the voice switch label is "Talk to PayAI". Replace
  every "Payobook helper" / "the helper" user-visible string this program adds or touches (EN + VI) accordingly; code
  identifiers (CoachHost, learn.helper, pb_helper_*) stay. Never "Odoo".
- **Q4 Voice ON for payobook.com after release.** The main loop switches on the microphone switch ("Talk to PayAI")
  for payobook ONLY, after the browser walk passes. The company "a spoken go ahead counts" switch stays OFF (not part
  of this decision). Other DBs stay off. Implementers: do not change switch defaults in data files.
- **Q5 Consent → NO re-ask.** People who already said yes keep it; new wording for new consents only. No
  `copy_version` field.
- **Q6 Spoken plans naming a person or an amount → ALWAYS NEED A TAP**, even where the spoken go-ahead switch is on.
  Server-enforced in the confirm path (a task whose plan came from a spoken sentence AND has a resolved person/people
  slot or a money/value slot refuses `how='voice'` with a plain message: "Tap Do it — I heard a name or an amount, so
  I need your tap."), with tests EN + VI. Red stays typed-word only.
- **Q7 Explain's own next step → KEEP.**

## Appendix A — dispositions of the adversarial review (rev 2)
Accepted and applied (section): 1 (§2, §5.7), 2 (§3.5, §5.6, test 1.13), 3 (§3.1, §5.2, test 2.1), 4 (§3.2, §6.7,
Q5, test 3.1), 5 (§3.2, §5.4, test 2.4), 6 (§3.3, §4.3 step 14), 7 (§3.3, R9, test 3.9), 8 (§3.4, §4.4, ledger OC9),
9 (§3.1/3.2/3.4 line refs; sprite), 10 (§4.3 step 9, §4.6, corpus), 11 (§4.9, §4.3 steps 13/17, R11, test 1.21),
12 (§4.3 step 3 moved up; §4.5 anchoring), 13 (§4.3 step 14b), 14 (§4.5 VI marked matching), 15 (§4.5, step 6,
corpus), 16 (§4.3 step 12, §4.7 `figure_ref`, corpus), 17 (step 8 whole-sentence + `_capability_route`), 18 (pinned
watch + note), 19 (step 10 `order_question`), 20 (§5.4, R12, test 2.5), 21 (§6.3, test 2.3), 22 (step 4 wording,
reusing runner msgids), 23 (§7, test 1.14), 24 (§7 markers for every non-PayAI turn), 25 (§4.4 Access filter, test
1.22), 26 (step 13 continues, step 18 note), 27 (`_payai_available` mirrors the provider; `fallback_key`), 28 (step 4
copy), 29 (§5.6, §5.2, §5.7, test 2.1), 30 (§6.7, test 3.1), 31 (corpus + tests 1.6/1.7/1.12/1.14/1.21-1.23,
2.3-2.8), 32 (§10 LW, Q7), 33 (§5.1 `lang` prop + payload turns, test 2.6), 34 (§5.1 in-memory store, test 2.7),
35 (§5.3 consent turn), 36 (§5.1 api), 37 (§5.1 queue, §5.4, test 2.8), 38 (§5.4 rename, Q3), 39 (§5.2 dvh /
visualViewport), 40 (step 16 composer only without PayAI; `ask_only`; R13), 41 (step 5 small talk), 42 (§6.1 focus),
43 (§6.2 gate, §6.3 filter, §6.6 nouns-only prompt), 44 (§6.2 onstart cue), 45 (§6.6 auto-detect + re-transcribe),
46 (§6.5 check + Q6), 47 (§6.4, OC13, W14), 49 (§6.5 language from text, debrand filter, Q2 default changed),
50 (§6.2 AudioContext + Escape rung).
Partly accepted:
- 13 — "Do it for me" chip is offered only where the database CAN act (exact guide match, §4.3 14b); on a database that
  cannot act the lead is "Here is how you do it." (a "Do it for me" chip there would be a dead end).
- 46 — the month-number / full-name check of `card.speak` is recorded (test 3.8) but not changed here: the speak text is
  built in `runner.py`, which this program must not edit (§2); any change goes to the PayAI program.
Rejected:
- 48 (refuse dictated input in the Red word box) — browsers do not reliably report keyboard dictation, and a false
  refusal would block a legitimate typed decision; recorded as known gap OC12 instead.
