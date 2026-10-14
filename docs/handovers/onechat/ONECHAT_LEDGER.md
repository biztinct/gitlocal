# ONECHAT — conventions & gotcha ledger

Every ONECHAT handover and phase agent references this file. Add a row whenever a new gotcha is hit.
Program doc: `ONECHAT_HANDOVER.md` (§16 owner decisions win over any other text). The PayAI ledger
(`docs/handovers/payai/PAYAI_LEDGER.md`) binds this program too — PA-R1…R5 and every PA row.

## Standing rules (seeded from handover §15)
| # | Fact | Apply |
|---|---|---|
| OC-R1 | Routing never calls a model and never sees the voice flag. | Keep `route()` pure + signature test. |
| OC-R2 | Guide questions are never stored; markers carry authored labels only. | `rpc_note_turn` has no text arg, checks owner + key. |
| OC-R3 | Markers are what keeps `_is_latest` honest across non-PayAI turns. | Every non-PayAI turn except `tap_card` writes one. |
| OC-R4 | Card chips answer a card; a router would turn "Cancel" into a guide miss. | Any send with `_payaiResolve` / card chip bypasses the router. |

## Ledger
| # | Date | Gotcha / fact | How to apply |
|---|---|---|---|
| OC1 | 2026-10-14 | The guide scores imperatives at 100 — a high guide score is not "not a command". | Command check before guide; on a can-act DB an imperative goes to PayAI unless the guide match is exact. |
| OC2 | 2026-10-14 | Guide candidates are screen-filtered; "what is BHXH" misses on Pay Runs. | `probe` runs a screenless pass at floor 55 — and the Access filter applies to it. |
| OC3 | 2026-10-14 | `test_composer test_02b` pins the miss payload keys. | Scores only via `probe`, never on `ask()` misses. |
| OC4 | 2026-10-14 | `explainScreen` used to draw nothing on the Ask/Practice tab. | It pushes into the stream now (queued until attach); walk W9. |
| OC5 | 2026-10-14 | Read-aloud language read `window.odoo.session_info` (absent in Odoo 17+) → always en-US. | Pick the voice from the reply text. |
| OC6 | 2026-10-14 | Transcripts were logged at INFO by the OpenAI provider. | Log counts only. |
| OC7 | 2026-10-14 | `_payaiVoice` leaked onto chips and hand-offs. | Spoken = sent text equals what was heard into an empty box. |
| OC8 | 2026-10-14 | "Talk to the helper" (DB-wide) and spoken go-ahead (per company) are separate switches, both off live. | Demos need both; never switch on during deploy. |
| OC9 | 2026-10-14 | Scores carry a +25 screen bonus; "80" can be a two-word overlap. | Threshold on `kind`, never on the score. |
| OC10 | 2026-10-14 | `ask_model` makes a plan from ANY non-question the phrase table misses, and `looks_like_question` misses many questions. | Router sends question-shaped sentences with `ask_only`. |
| OC11 | 2026-10-14 | `_onKey` is document-capture: it runs before any element handler in the drawer. | New Escape rungs (menu, recording) live inside `_onKey`, each with a `close(` call (test_06). |
| OC12 | 2026-10-14 | Device keyboard dictation into the Red card's word box counts as typed. | Known gap; not detected; the word box is still a deliberate act. |
| OC13 | 2026-10-14 | "send it" / "run it" are go-ahead words; a clipped "send it back" can confirm an Amber send. | Read-back + onstart cue; W14 checks. |
| OC14 | 2026-10-14 | The transcription service echoes its prompt and invents filler on silence. | Short/silent gate, filler filter, nouns-only prompt. |
| OC15 | 2026-10-14 | Provider forced `language='en'`; Vietnamese speech came back garbled. | Auto-detect; omit the argument; "Hear it as …" re-transcribe. |
| OC16 | 2026-10-14 | `RT.lang` is not reactive and `helper` never changes identity. | Pass `lang` as a prop; turns store payloads, render at draw time. |
| OC17 | 2026-10-14 | OC1: the guide's `practice` intent carries the unaccented phrase "lam thu" — it is CONTAINED in "làm thủ tục nghỉ việc" (leaver paperwork) and "làm thủ công" (by hand), so the guide answered "let me practise" to both. `ask()` still does (pre-existing). | The router drops the `practice` intent unless `mentions_practice(text)` (marks-aware: marked text → "thực hành / làm thử / tập làm(not quen)"; folded only when the sentence has no marks) and re-probes with `exclude=('practice',)`. |
| OC18 | 2026-10-14 | OC1: `test_composer::test_03b` slices `ask()`'s body up to the next `\n    @api.model` and needs the literal `'matched': False` after `self._compose(` — moving the miss dict into a helper breaks it. | Keep the miss dict INLINE in `ask()`; `learn.intent._miss_payload` is its twin for the router (same three keys). |
| OC19 | 2026-10-14 | OC1: there is NO left-menu entry for Settings › Access and delegations — the Access home is a tab of the Settings cog, and the Learn station `access` has `sidebar_key: ''` (`_station_reach('')` says "visible"). | "Can see Access" = `_station_reach('pb_settings.item_settings')` (`learn_intent.ACCESS_SIDEBAR_KEY`), behind `learn.intent._access_visible()` — one place to retarget if the owner wants a stricter test (e.g. `biz_access.group_access_manager`). |
| OC20 | 2026-10-14 | OC1: on payobook "delegate my access" hits PayAI's phrase table (`never_access`, the refusal card) — so the P route is `payai command`, not the corpus' expected guide miss. The "Explain how instead" chip is offered only when the guide answer survives the Access filter. | Pinned as observed (`payai command`); B is the guide miss when Access is not visible. |
| OC21 | 2026-10-14 | OC1: how-to requests and orders rarely match the guide's phrases as typed — "show me how to run payroll" shares only ambiguous words with `howrun`; "run June payroll for Retail" has a month and a name in the middle. | The router also probes the TOPIC in the guide's own phrase shape: `howto_canonical` ("how do i <topic>" / "lam sao <topic>") for how-to requests, `order_task` + `command_canonical` (lead, month, number, name, "for X"/"cho X" removed) for orders. Stronger kind wins. |
| OC22 | 2026-10-14 | OC1: `gen_learn_data.py --check` was already STALE at HEAD 0910b7149 (only `learn_content.json` `version` hash differed). Regenerating after the OC1 content left `pb_learn/i18n/vi_VN.po` and `static/src/engine/fixture.js` UNCHANGED ("5 unchanged") — PA54 did not strike this time, but check `git status` after every regenerate. | Commit `data.js` + `learn_content.json` only; run `--check` after. |
| OC23 | 2026-10-14 | OC1: scenario NAMES are phrases too, and they share common words ("month" is in "Load a month's pay data" and "File the month's government reports") — the ambiguous-word filter then drops it, so "let me practise importing the month" scored only one long word. | `practice_probe` accepts a single overlap1 hit when NO other scenario has any hit (a tie is still chips). |
| OC24 | 2026-10-14 | OC1: `docs/tutorial_poc/author/tools/simulate_resolver.py` EXECUTES learn_intent.py's module source between `_STOP = {` and `class LearnIntent`, and pins marker lines (`best = max(best, 100)`, the tie-at-floor line, `best += _ON_SCREEN_BONUS`, `s[0] >= floor` …). | Module-level code there must be pure (only `re` / `unicodedata`); keep the marker lines verbatim when refactoring the scorer (`_score_kind` / `_resolve_scored` kept them). |
| OC25 | 2026-10-14 | OC1: no odoo-bin locally (PA10). `pb_payai_actions/tests/offline/` stubs Odoo, loads the REAL source files and composes `_inherit` layers in load order; it replays the corpus, the router rules, `ask_only`, the R9 cache, the marker door, and `pb_learn/tests/test_helper_route.py` itself. | Run `python3 pb_payai_actions/tests/offline/test_onechat_oc1.py` before every commit touching the router; any NEW table read inside a router hook must be its own patchable method (`_payai_ctx`, `_planned_task`). |
| OC26 | 2026-10-14 | OC1: guide content gaps the router exposes (no intent phrase matches): "how many payslips should there be", "how many payslips are in the June run" (B), "how do I compare two pay runs", "show me how payroll works", "where is the bank file", "bhxh là gì", "chỉ tôi cách duyệt", "could I run payroll now?". On payobook they go to PayAI's question path (`ask_only`); on a base DB they are honest misses. | OC4 content: add the phrases (data.js `match`), then re-pin the corpus rows. |
| OC27 | 2026-10-14 | OC1: `learn.helper._payai_available()` calls `provider.is_available()` on every routed sentence. OpenAI/Anthropic answer from the key (free); Ollama's does a network GET with a 3-second timeout. | Fine on today's providers; cache per request if an Ollama row is ever the active chat config. |
| OC28 | 2026-10-14 | OC1: `rpc_note_turn` writes the marker label in `env.lang` (the request's context language). | OC2: send `context: {lang}` from the language pill on `rpc_note_turn` (handover §5.5). |
| OC29 | 2026-10-14 | OC1: before OC2 ships, the old chat would draw a `helper_note` history row as a plain assistant message whose `card` is the marker dict (kind guide/practice/…). Nothing writes markers until OC2's client calls `rpc_note_turn`. | Ship OC1 and OC2 together (§13 deploy is after OC4 anyway); OC2's `_loadHistory` maps `intent == 'helper_note'` to a marker and sets `card=null`. |
