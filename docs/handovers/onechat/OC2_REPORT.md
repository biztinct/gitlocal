# OC2 REPORT — the one chat UI (ONECHAT)

Phase: OC2 (handover §5, §7 client half, §11 OC2). Branch `onechat`, worktree `gitlocal-onechat`.
Implementer: Opus. Status: **done offline; server tests and the browser walk wait for the clone
stage** (no odoo-bin and no browser stage on this machine — PA10). No manifest version was bumped;
nothing was deployed; no live database was touched. §16 owner decisions applied: the chat is named
**PayAI** (Q3); spoken words wait for Send (Q1, unchanged — no auto-send anywhere); pay figures are
not read aloud (Q2, the read-aloud path now says "the figures are on screen"); Explain keeps its own
next-step part (Q7); voice switch defaults untouched (Q4).

## 1. What OC2 delivers, in one paragraph
The helper drawer is now ONE chat called PayAI: no tab strip, no "Your next step", no separate guide
box. One stream of turns and one composer. Every sentence typed (or spoken, then sent) goes to the
OC1 router first; the chat draws whatever comes back — a PayAI answer or plan card, a guide answer, an
Explain-this-screen answer, a practice turn, a "Which did you mean?" choice, or a short note — in one
card frame. Every non-PayAI turn writes one content-free marker into the person's conversation, so the
thread survives a reload and a later spoken "go ahead" knows the plan is no longer the last thing
shown. Answers that teach a task carry one **Practise this** chip. Card chips (Change Period, a name,
Cancel) never touch the router. The header has Explain this screen, the language pill, a **More** menu
(Read answers aloud · Clear conversation · Open practice mode · Use my voice) and Close. People without
the PayAI chat get the same router, guide-only, in a stream the drawer draws itself.

## 2. Files
| Module | File | What |
|---|---|---|
| pb_learn | `static/src/coach/coach.js` | Tabs, next step, Ask-tab hand-off, practice tab, tour card and practice-mode card removed. New: `pb_helper_chat` seam (+ one-release `pb_helper_tabs/ask` shim), `chat`/`chatAllowed`, the `helper` object (built once), `openHelper` + queue + `_attach`/`_detach`/`_flush`, one turn renderer `_turnHTML` for both streams (guide, note, practice, choose, consent, context/divider, marker), context card `_contextHTML` + `_notSureHTML` chips, More menu `menuHTML` + keyboard nav, Escape ladder rungs, guide-only stream (`ask()` now routes), Practise this, `explainScreen()` returns the answer, `user.lang` language. |
| pb_learn | `static/src/coach/coach.xml`, `coach.scss` | One header (Explain `scan-text`, pill, More `ellipsis`, Close with chrome aria); chat mount with `helper`, `lang`, `screen`, `place`, `close`; guide-only stream + textarea composer; drawer 480 px `.lrn-has-chat`; phone bottom sheet off `visualViewport`; the one-chat styles. |
| pb_learn | `static/src/journey/icons.xml` | + `mic square volume-2 volume-x ellipsis trash-2 scan-text arrow-down` (Lucide). |
| pb_learn | `static/src/journey/journey.js`, `static/src/hub/learn_palette.js` | Language read from `user.lang` (was the page's session info, absent on this version). |
| pb_learn | `static/src/anchors.json` | + `helper-composer`, `helper-mic` (reserved); `helper-orb` description. |
| pb_learn content | `docs/tutorial_poc/author/data.js` → `static/content/learn_content.json` | 35 new chrome keys EN+VI (§8); Q3 renames; three sentences that named the Ask tab reworded. `vi_VN.po` / `fixture.js` unchanged after generating (PA54 checked). |
| pb_learn tests | `tests/test_onechat_ui.py` (new), `tests/__init__.py`, `tests/test_bundle.py` ("PayAI" same in both languages) | 2.1 / 2.2 / 2.9 / 2.10 source pins; added to `replay_tests.py`. |
| pb_payroll_ai_insights | `static/src/components/ai_insight_chat/ai_insight_chat.js|xml|scss` | `sendMessage(opts)`; `submitComposer` (the only `_takeSpoken` caller); spoken provenance (`_heard`, `_boxBeforeRecording`); `cancelRecording`; `_rpcContext` (pill language to the server); markers from history (`markerOf`); the embedded one chat: router dispatch table, markers, practice beat, fallback-key answer, api for the drawer, page-life turn store, Jump to latest, auto-growing box, Lucide only. |
| pb_payroll_ai_insights | `models/payroll_ai_engine.py`, `i18n/vi_VN.po`, `tests/test_onechat_prompt.py` (new), `tests/__init__.py` | §5.5: "Answer in Vietnamese" line when `env.lang` is Vietnamese; 2 new JS msgids. |
| pb_payai_actions | `static/src/js/chat_patch.js` | `_extraSendKwargs(opts)` ({resolve} alone / `voice` iff spoken / `ask_only`); `_bypassRouter()`; `_payaiVoice` and the `_transcribe` patch deleted (OC7); doors registered once per page + conversation. |
| pb_payai_actions | `static/src/js/coach_patch.js` | ⌘K hook → `openHelper({text, send:true})`; no tab. |
| pb_payai_actions | `tests/js/harness.mjs`, `tests/js/onechat_oc2.test.mjs` (new), `tests/test_onechat_client.py` (new), `tests/__init__.py` | Relative imports resolvable; the node suite; its server-side runner. |
| docs | `docs/tutorial_poc/author/tools/replay_tests.py`, `ONECHAT_LEDGER.md` (OC36–OC45), this report | |

`cards.xml` is untouched — both anchors it extends are kept exactly (OC36).

## 3. Test results
Offline (this machine):
```
node pb_payai_actions/tests/js/onechat_oc2.test.mjs        126 passed, 0 failed
   negative control (copy with voice always sent + a marker on tap_card notes):
                                                           118 passed, 8 failed  ← as it should
node pb_payai_actions/tests/js/client_fix.test.mjs         82 passed, 0 failed (unchanged)
python3 pb_payai_actions/tests/offline/test_onechat_oc1.py Ran 34 tests … OK (OC1, unchanged)
replay_tests.py                                            TOTAL: 229 pass, 16 skip, 2 fail
   (was 215/16/2; +14 = test_onechat_ui; the 2 are the pre-existing "bridge suite did not run")
check_contract.py --quiet                                  ✓ 73 checks passed
simulate_resolver.py                                       ✓ every property holds
gen_learn_data.py --check                                  ✓ generated data is up to date (6 files)
test_scenario_rules.py                                     ✓ 20 refusals and 1 acceptance
dart-sass (scratchpad npm) on coach.scss, ai_insight_chat.scss   both compile (OC44)
```
Server (clone stage, NOT run here): `pb_learn/tests/test_onechat_ui.py` (14, source-only — already
replayed), `pb_payai_actions/tests/test_onechat_client.py` (runs the node suite where node ≥ 18 is on
the server, skips with a sentence otherwise), `pb_payroll_ai_insights/tests/test_onechat_prompt.py`
(3; skips the Vietnamese case where vi_VN is off — OC38). Run with
`-u pb_learn,pb_payroll_ai_insights,pb_payai_actions --test-tags /pb_learn,/pb_payroll_ai_insights,/pb_payai_actions`
(PA35). Existing pins that read the changed files — test_coach 08/20b, test_explain 06/06b,
test_practice 08, test_assets 01/01b/01c/02/03/05/06, test_questions 04f/04d, test_progress_security
06, test_welcome, test_retirement, test_egress 04b2, biz_debrand starters, test_connector_cockpit 41
— were each checked by hand against the new source (and the replayable ones replayed): all hold.

Handover cases → where tested:
| Case | Where |
|---|---|
| 2.1 old pins | test_onechat_ui `test_01*` (mirror) + the original tests on the clone |
| 2.2 removals, openSuggested, no FA, icons, no session_info, no bar-chart-3 | test_onechat_ui `test_02*` |
| 2.3 spoken provenance + kwargs | node `spokenSuite` (12 checks) |
| 2.4 dispatch table | node `dispatchSuite` (7 routes × 6 checks; payai one person turn; error → fallback guide answer; choice / Do it for me / Explain how instead without a second route) |
| 2.5 chip bypass | node `bypassSuite` (resolve via sendText and composer, payaiPick, payaiEdit, chip.ask, follow-up with resolve — never routed; plain follow-up and context suggestion — routed) |
| 2.6 language | node `langSuite` (past guide turn, source label, note, placeholder, server lang) |
| 2.7 close / reopen / reload | node `storeSuite` (no history call on re-open, full answer kept; fresh load → marker + Show again) |
| 2.8 queue | node `queueSuite` (moment Explain + ⌘K before attach → once each after) |
| 2.9 anchors | test_onechat_ui `test_09` + test_anchor_registry (replayed) |
| 2.10 white-label | test_onechat_ui `test_10*` (every new chrome key EN+VI, every string literal in the one chat's code and templates) |

## 4. Browser walk
**Not run** — no Odoo on this machine and the phase brief forbids the live server. W1–W13, W16, W17
are for the clone stage (W14/W15 are OC3). What to look at first: the header row at 390 px (five
controls), the phone sheet with the keyboard open (`--lrn-vvh` / `--lrn-kb`), the More menu's focus
order, the 160 ms fade, and that a plan card has no outer frame around its own.

## 5. Deviations from the handover (each with the reason)
1. **The chat takes two more props, `screen` and `place`.** `helper` never changes identity and
   `lang` only changes on a flip, so without them the context card would not redraw when the person
   moves screen or hub tab with the drawer open, and the "new screen" card could not be pushed.
2. **Helper turns are drawn by the drawer (`helper.turnHTML`) for both streams**, not re-implemented
   in the chat. One renderer = one visual language and one `data-act` whitelist (test_coach 08); the
   chips inside those turns go through CoachHost's `onClick`, which calls the chat's api. The api
   therefore has a few more members than §5.1 lists: `findTurn`, `sendDirect`, `practise`,
   `dropTurns`, `isEmpty`, `ttsSupported`, `voiceDeclined`.
3. **⌘K row label kept "Ask PayAI to…"** — §16 Q3 wins over §5.4's "Ask the helper…".
4. **Content pulled forward from OC4** because OC2 made it false or Q3 named it: `coachName` "PayAI",
   `orbLabel` "Ask PayAI" / "Hỏi PayAI", `orbHint`, `helperFailed` (+ the `LOAD_FAILED` copy),
   `swVoiceTitle` "Talk to PayAI", `swVoiceBody` (all three named the Ask tab). OC4 still retires the
   old keys (`tabGuide/tabAsk/tabPractice`, `nextStep`, `askDataInstead`, `askDataLead`, `honest`) —
   no code reads any of them now.
5. **Only Try draws a practice turn and the 600 ms beat.** Watch and Do it live start at once, as
   before; a watch-only hit ("let me practise approving overtime") shows its note and a Watch button
   rather than starting by itself; the tour ("show me the tour") starts after the beat.
6. **"Use my voice" waits for OC3**: it needs `voice.switch_on` and `voice.provider_ready`, which OC3
   adds to `rpc_voice_status`; until then the item never shows.
7. **The embedded chat's own footer (Read aloud / Clear chat), per-message replay link and welcome
   block are gone** — read-aloud and Clear live in More; the banner + context card replace the welcome.
8. **The figures rule (Q2) is in the read-aloud path already** (`_readable`): a `payroll_data` / chart
   answer reads only "Here are the figures you asked for — they are on screen." OC3 owns the rest of
   read-back.
9. **Language reads fixed in journey.js and learn_palette.js too** (2.2 asks for no `session_info`
   read). `live_state.js` reads it for database/user, not language — left, OC43.
10. `c-ask` and `c-back` dropped from `COACH_ACTIONS` (never emitted).
11. Show me how rows say **Practise** (`scPractise`), not "Try" — one word for one promise (OC42).

## 6. What changes what is stored or sent outside
* **Stored**: from now on, one assistant `payroll.ai.message` per non-PayAI turn (OC1's
  `rpc_note_turn`, now called by the client): kind + key only, never text from the browser. Not for
  "Tap Do it…" notes about a plan card.
* **Sent to the server**: the pill's language as `context.lang` on send, status, voice status, notes
  and transcription; `ask_only` for question-shaped sentences (OC1 server side); `voice: true` only for
  a send that is exactly what was heard into an empty box.
* **Sent to the AI service**: one more line in the system prompt for Vietnamese readers ("Answer in
  Vietnamese…"). Nothing else; markers never reach the model (OC1).
* **Browser memory**: the conversation's turns for the page's life (closing the drawer keeps them).

## 7. Findings the handover asked for
* **Vietnamese answer language (§5.5)**: none of the four system prompts said which language to answer
  in, and the chat never told the server the pill's language. Both fixed (context.lang + the one-line
  prompt rule). **Not verified against a live model** — needs the clone with an active AI service
  (W10).
* **`card.speak` month / name (test 3.8)**: OC3.

## 8. Chrome keys
Added (EN + VI): `honestAct`, `honestAsk`, `honestGuide`, `askAny`, `askAnyNoAct`, `send`, `close`,
`more`, `readAloud`, `clearConv`, `clearConvConfirm`, `clearConvYes`, `clearConvNo`, `useVoice`,
`micStart`, `recording`, `answering`, `fromGuide`, `fromPayData`, `aboutScreen`, `aboutColumn`,
`practiseThis`, `scPractise`, `letMePractise`, `openingPractice`, `openingWatch`, `practiceChipsLead`,
`whatCanYouDo`, `showAgain`, `composedAgain`, `jumpLatest`, `spoken`, `routeFailed`, `pinDashboard`,
`figuresOnScreen`. Changed: `coachName`, `orbLabel`, `orbHint`, `helperFailed`, `swVoiceTitle`,
`swVoiceBody`. Reused: `composedAnswer` (for "Composed from the guide"), `notSure`, `explainScreen`,
`explainHint`, `onScreen`, `practiceOpen`, `coachNoScreen`, `pointNotHere`, the OC1 router keys.
Retired: none (OC4). Not added yet (OC3): `micStop`, `micCancel`, `micStarting`, `transcribing`,
`heardNothing`, `hearAsVi`, `hearAsEn`, `micDenied`, `micCannot`, `noViVoice`. pb_payroll_ai_insights
.po: 2 new JS msgids ("From your pay data", the figures sentence).

## 9. Design-bar self-score
| Bullet | Score | Why |
|---|---|---|
| The right thing back with no tab to pick | 5 | One box; the router decides; card chips answer their card; "Which did you mean?" when it genuinely cannot tell. |
| Speaking instant and safe | 3 | Spoken = exactly what was heard into an empty box (OC7 closed); Escape cancels a recording without closing; the recorder's look and feel is OC3. |
| Zero dead-ends | 4 | Every turn ends in chips or a next step; misses carry "What I can answer here"; practice chips always offer Open practice mode; a PayAI error with a known guide answer shows that answer. |
| Plain screen words, never "Odoo" | 5 | 35 keys EN+VI authored, scanned in a test; PayAI by name everywhere (Q3). |
| Locked palette, Lucide, no gradients, motion with purpose | 4 | Only the five locked colours and their tints, sprite icons only, 160 ms fade-up honouring Reduce motion; not yet seen in a browser. |

## 10. Open items
* **Clone stage**: the three server files; then the browser walk W1–W13, W16, W17 (W17 on a
  `payobook_template`-like clone: guide-only stream, no mic, "how many employees" → the no-assistant
  note).
* **OC3**: the recorder (tap to talk, Starting…/Listening only after `onstart`, level meter, Stop /
  Cancel, short/silent gate, hallucination filter, mime fallback, consent re-wording + test_04e),
  read-back of spoken guide answers, `switch_on` / `provider_ready` for "Use my voice", Q6 server
  enforcement, 3.8.
* **OC4**: retire the old chrome keys listed in §8; lessons/tour wording (LW, P4 steps, tour last
  step); consider removing `reserved` from `helper-composer` once LW anchors to it.
* **Later**: OC43 (`live_state.js` resume key); drop the `pb_helper_tabs/ask` shim next release.
