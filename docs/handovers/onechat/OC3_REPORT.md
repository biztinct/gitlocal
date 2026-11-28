# OC3 REPORT — voice in the one chat (ONECHAT)

Phase: OC3 (handover §6, §11 OC3, §16 Q1/Q2/Q5/Q6). Branch `onechat`, worktree `gitlocal-onechat`.
Implementer: Opus. Status: **done offline; the server tests and the browser walk (W14, W15, W16)
wait for the clone stage** (no odoo-bin and no browser on this machine — PA10). No manifest
version was bumped; nothing was deployed; no live database was touched; no switch default was
changed (Q4: "Talk to PayAI" and "a spoken go ahead counts" stay as they are in data files).

§16 owner decisions applied: **Q1** the words wait for a tap on Send (no auto-send anywhere; the
transcriber still cannot send); **Q2** figures are not read aloud — a pay-data answer says only
"the figures are on screen", and every other spoken string has its amounts replaced by "an amount
shown on screen"; **Q5** no re-ask (no `copy_version` field; a past yes stays a yes); **Q6** a
spoken plan naming a person or an amount always needs a tap — enforced on the server in the
confirm path, EN + VI; **Q3** "PayAI" in every new string; **Q7** untouched.

## 1. What OC3 delivers, in one paragraph
One microphone in the composer. Tap it and it says "Starting…" until the recorder really runs,
then "Listening" with a red dot, five live level bars and a "0:07 / 1:00" clock; the same button
is now a solid Stop, and Cancel sits in the bar (Cancel sends nothing). A press held longer than
400 ms stops on release; Space or Enter on the focused microphone toggles it; Escape cancels and
leaves the drawer open. After Stop the bar says "Turning your words into text…"; the words land in
the box (soft wash), focus stays in the box with the cursor at the end, Send pulses once, and the
hint says "This is what I heard. Edit it, then press send." with a "Hear it as Tiếng Việt / English"
link that re-sends the same recording in the other language. A recording under 0.7 s, a silent
one, and the service's filler ("Thank you for watching", its own hint echoed back) never reach the
box. Recognition auto-detects English or Vietnamese. A spoken turn is always read back (a typed one
only with "Read answers aloud" on), in a voice that matches the text's language, with a Stop on
the turn being read; amounts and the vendor's name are never spoken. On the server, a plan that
came from a spoken sentence and names a person or an amount refuses a spoken go-ahead with "Tap Do
it — I heard a name or an amount, so I need your tap."

## 2. Files
| Module | File | What |
|---|---|---|
| pb_payroll_ai_insights | `static/src/components/ai_insight_chat/ai_insight_chat.js` | Tap to talk (pointer, hold > 400 ms, Space/Enter, repeat guard); `micStarting` → `isRecording` only on `onstart`; `_stopWanted`; stream released on any failure; format fallback `pickRecordingType` (WebM/Opus → WebM → MP4 → none = no microphone + "This browser cannot record here."); `NotAllowedError` vs other errors; level meter (AnalyserNode, peak RMS) closed inside `_releaseMicrophone` after the tracks; short/silent gate; `isPhantomTranscript`; kept audio + `hearAs`; `lang`/`mime` sent; iOS speech prime; `speak(text, turnId)` through `speechText` (markup, brand, amounts, 600 chars), voice from the text, `voiceschanged` wait, no-Vietnamese-voice notice once, `speakingId` + Stop; spoken turns always read; helper turns read (`_readHelper`); `isRecording` api counts "Starting…"; recorder `onerror`. |
| pb_payroll_ai_insights | `…/ai_insight_chat.xml`, `…/ai_insight_chat.scss` | Recording bar (dot, meter, clock, Cancel), the mic-turned-Stop, "Turning your words into text…", heard wash, Send pulse, "Hear it as" link, Stop reading; pill wording "Tap to speak". Reduced motion honoured. |
| pb_payroll_ai_insights | `models/payroll_ai_conversation.py` | `rpc_transcribe_voice(audio_base64, lang=None, mime=None)`: `lang` ∈ {en, vi} else None (then NO language argument); `VOICE_FILES` whitelist → file name; nouns-only `VOICE_VOCAB` hint in the asked/reader's language; order of the gates unchanged. `rpc_voice_status` + `switch_on`, `provider_ready`, `vocab`; tap-to-talk consent copy; `tap_hint` replaces `hold_hint`. |
| pb_payroll_ai_insights | `ai_providers/openai_provider.py` | `transcribe_audio(audio_bytes, language=None, filename=…, prompt=None)`: language and prompt only when set; log line is byte count + character count only. |
| pb_payroll_ai_insights | `i18n/vi_VN.po` | New consent body (old entry replaced), "Tap to speak", the format refusal. |
| pb_payroll_ai_insights | `tests/test_egress.py` (`test_04e` updated), `tests/test_onechat_voice.py` (new), `tests/__init__.py` | 3.1–3.3 on a real database. |
| pb_payai_actions | `payai/runner.py` | **Q6** (the §16 exception to "runner not changed"): `run()` marks a spoken request (`data['spoken']`), `spoken_needs_tap(action, data)`, the refusal card in `confirm(how='voice')`, and the read-back tail never says "or say go ahead" for such a plan. |
| pb_payai_actions | `models/learn_helper.py` | The router's "yes" note follows Q6 (no "or say go ahead" over such a plan). |
| pb_payai_actions | `static/src/js/chat_patch.js` | The plan's read-back goes through the chat's one `speak` (same filter, Stop on its card). |
| pb_payai_actions | `i18n/vi_VN.po` | The Q6 sentence in Vietnamese. |
| pb_payai_actions | `tests/js/onechat_oc3.test.mjs` (new), `tests/offline/test_onechat_oc3.py` (new), `tests/test_onechat_voice.py` (new), `tests/test_onechat_client.py` (+ `test_02`), `tests/offline/test_onechat_oc1.py` (fake task gets `params_json`), `tests/__init__.py` | |
| pb_learn | `static/src/coach/coach.js` | `helper.answerSpeech(answer, lang)` / `_answerSpeech` — an answer as plain words (no source line, no worked figures). |
| pb_learn | `static/src/journey/icons.xml` | + `languages` (Lucide). |
| pb_learn | `tests/test_onechat_ui.py` | `test_10` white-label scan covers the 14 new chrome keys. |
| pb_learn content | `docs/tutorial_poc/author/data.js` → `static/content/learn_content.json` | 14 chrome keys EN + VI; `swVoiceBody` gains "Recordings go to the speech service only to be turned into text." `vi_VN.po` / `fixture.js` unchanged after generating (PA54 checked). |
| docs | `ONECHAT_LEDGER.md` (OC46–OC55), this report | |

## 3. Test results
Offline (this machine):
```
node pb_payai_actions/tests/js/onechat_oc3.test.mjs        84 passed, 0 failed   (×10 in a row, ×6 in parallel)
   negative control (Listening before onstart, no amount filter, stop-before-start not applied):
                                                           71 passed, 13 failed  ← as it should
node pb_payai_actions/tests/js/onechat_oc2.test.mjs        126 passed, 0 failed (unchanged)
node pb_payai_actions/tests/js/client_fix.test.mjs         82 passed, 0 failed (unchanged)
python3 pb_payai_actions/tests/offline/test_onechat_oc3.py Ran 13 tests … OK
   negative control (Q6 check and read-back tail removed from runner.py): FAILED (failures=2)
python3 pb_payai_actions/tests/offline/test_onechat_oc1.py Ran 34 tests … OK (unchanged)
replay_tests.py                                            TOTAL: 229 pass, 16 skip, 2 fail
   (same as OC2; the 2 are the pre-existing "bridge suite did not run";
    test_egress 28/28 incl. the updated test_04e, 04, 04b, 04b2, 04d, 04f)
check_contract.py --quiet                                  ✓ 73 checks passed
simulate_resolver.py                                       ✓ every property holds
gen_learn_data.py --check                                  ✓ generated data is up to date (6 files)
test_scenario_rules.py                                     ✓ 20 refusals and 1 acceptance
dart-sass (scratchpad) on ai_insight_chat.scss             compiles
```
Server (clone stage, NOT run here): `pb_payroll_ai_insights/tests/test_onechat_voice.py` (6),
`pb_payai_actions/tests/test_onechat_voice.py` (Amber 6 + Red 1), `test_onechat_client.test_02`
(runs the OC3 node suite where node ≥ 18 is on the server). Run with
`-u pb_learn,pb_payroll_ai_insights,pb_payai_actions --test-tags /pb_learn,/pb_payroll_ai_insights,/pb_payai_actions`
(PA35). Existing tests that read the changed files — test_egress 04*, test_payai_p2 `test_10`
(a spoken plan naming nobody still reads "or say go ahead"), test_payai_p3 `test_04`, fix_runner
`ux3`, test_onechat_router 1.7/1.15, test_assets, test_coach, test_onechat_ui — were checked
against the new source and the replayable ones replayed: all hold.

Handover cases → where tested:
| Case | Where |
|---|---|
| 3.1 test_egress 04/04b/04b2 with the new kwargs; 04e on the tap-to-talk copy; 04f | replay (28/28); offline `test_3_1…`; server `test_3_1_gates_unchanged` |
| 3.2 `lang='vi'` → language + VI hint; None → NO language kwarg; bad mime refused; no decision verb | offline `TestTranscribe` (4); server `test_3_2_*` (3) |
| 3.3 provider log has no transcript | offline `TestProviderLog`; server `test_3_3…` |
| 3.4 recorder rules | node `recorderSuite` (52 checks) |
| 3.5 read-back rules | node `readBackSuite` (26 checks) |
| 3.6 Red by voice | server `TestOneChatVoiceRed.test_3_6…` |
| 3.7 Amber by voice, switch off / on | server `test_3_7_amber_by_voice`; offline `TestConfirmByVoice` (switch-off branch) |
| 3.8 read-back only when spoken; month / names recorded | server `test_3_8…`; finding in §7 |
| 3.9 (R9 cache) | done in OC1 (`TestModelCache`), unchanged |
| Q6 EN + VI, person and amount, typed plan unaffected, read-back tail, router note | offline `TestSpokenNeedsTap`, `TestConfirmByVoice`, `TestReadBackTail`, `TestRouterTapNote`; server `test_q6_*` (4) |

## 4. Browser walk
**Not run** — no Odoo on this machine and the phase brief forbids the live server. W14 (voice, on
the CLONE with "Talk to PayAI" on), W15 (Vietnamese voice + Hear it as English) and W16 (390 px,
tap to talk with the keyboard up) are for the clone stage. Look first at: the mic-turned-Stop at
44 px on a phone; "Starting…" on the first permission prompt; the level bars on a real microphone;
Safari/iOS recording MP4 end to end (`mime=audio/mp4` → `voice.mp4`); the iOS read-back after the
prime; a device with no Vietnamese voice; and W14's "send it back" over an Amber "send payslips"
plan (OC13 — the read-back names the run).

## 5. Deviations from the handover (each with the reason)
1. **Stop is the microphone button itself**, not a second Stop inside the recording bar (§6.2
   lists both). Removing the microphone while it records loses the `pointerup` of a held press, so
   press-and-hold could never stop (OC46). The bar keeps the dot, meter, clock and Cancel.
2. **Amounts are filtered out of EVERY spoken string**, not only pay-data answers (Q2 says
   "amounts are not spoken"): PayAI's own plan read-back says "…to 500,000" for Change a pay value
   (OC53). The runner's text is unchanged; the filter is in the chat (`speechText`).
3. **The runner was changed for Q6** — §2 says it must not be, §16 Q6 says "server-enforced in the
   confirm path" and §16 wins. The change is narrow: a flag in the task's params, one pure rule,
   one refusal before the latest-plan check, and the read-back tail. Red is untouched.
4. **"Hear it as …" disappears on the first edit** of the box, and the kept recording is dropped
   then (§6.6 keeps it until Send/Cancel/close): once the words are edited they are no longer what
   was heard, and holding the audio longer than needed is the worse privacy default.
5. **The vocabulary hint reaches the browser** through `rpc_voice_status.vocab`, so the "echoed
   hint" filter uses the server's exact words instead of a second copy.
6. **"This browser cannot record here." is said once per page**, in the hint line, when voice is on
   for the person but the browser has no recording format — not on every open.
7. **The format refusal** ("This kind of recording cannot be used here. Please try typing.") is a
   new server sentence (EN + VI); a missing `mime` still means WebM (an old tab keeps working).

## 6. What changes what is stored or sent outside
* **Sent to the speech service**: the same recording as before, now with a file name that matches
  its real format, a short product-noun hint (never a name, never a decision word), and — only when
  the person taps "Hear it as …" — a language; by default NO language (auto-detect). "Hear it as …"
  sends the same recording a second time (about US$0.006 a minute).
* **Not sent**: recordings under 0.7 s, silent ones, cancelled ones, and any started while the
  drawer was closing.
* **Stored**: `spoken: true` inside the PayAI task's existing `params_json` when a request (or an
  answer to its question) was spoken. No new field, no new table.
* **Logged**: the transcription log line is now "N bytes into M characters" — no words (OC6).
* **Browser memory**: the last recording, until Send, Cancel, an edit, a new recording, close or
  unmount.

## 7. Findings the handover asked for
* **`card.speak` month / names (3.8)** — recorded, not changed (PayAI program): `run_payroll` says
  "I will run June 2031 payroll for Retail, 3 people." — the month by NAME only in English and by
  NUMBER only in Vietnamese ("tháng 6 năm 2031"), never both; named people are COUNTED, never named.
  `send_payslips` says "I will email N payslips for <run name>." (the run's own name). `approve_item`
  (Red) says only that the word must be typed. `update_pay_data` names the person in full and the
  amount (the amount is now filtered on the device, Q2). With Q6 a misheard NAME can no longer be
  confirmed by voice; a misheard MONTH still can where the company switch is on — recommend the
  PayAI program adds "month 6" to the read-back (ledger OC54).
* **Vietnamese answer language (§5.5)**: done in OC2, unchanged here.

## 8. Chrome keys
Added (EN + VI): `micStarting`, `listening`, `micStop`, `micCancel`, `transcribing`, `heardNothing`,
`hearAsVi`, `hearAsEn`, `micDenied`, `micCannot`, `micUnsupported`, `noViVoice`, `amountOnScreen`,
`stopReading`. Changed: `swVoiceBody`. Retired: none (OC4 retires the OC2 list). Server copy:
`tap_hint` replaces `hold_hint`; the consent body is reworded (test_04e).

## 9. Design-bar self-score
| Bullet | Score | Why |
|---|---|---|
| The right thing back with no tab to pick | 5 | Spoken words go through the same router as typed ones, after the same Send. |
| Speaking instant and safe | 4 | Starting…/Listening honest to the recorder, live meter, words in the box with one pulse on Send, nothing sent by itself, names/amounts need a tap; not yet felt on a real phone. |
| Zero dead-ends | 4 | Every failure says what to do (blocked microphone, no format, heard nothing, no Vietnamese voice); "Hear it as …" fixes the wrong language in one tap. |
| Plain screen words, never "Odoo" | 5 | 14 keys EN + VI in the white-label scan; spoken text passes the brand filter; no amounts spoken. |
| Locked palette, Lucide, no gradients, motion with purpose | 4 | Indigo / bad and their tints, sprite icons only (+ `languages`), one 1.04 pulse, blink and opacity pulse off under Reduce motion; unseen in a browser. |

## 10. Open items
* **Clone stage**: the two new server files + `test_onechat_client.test_02`; then W14, W15, W16
  (and the OC2 walk W1–W13, W17).
* **PayAI program**: say the month as "June, month 6" in plan read-backs (OC54); consider naming
  the people in `run_payroll`'s read-back now that Q6 makes it safe.
* **OC4**: lessons/tour wording that mentions speaking ("Type, or speak if your company has turned
  voice on"), the old chrome keys' retirement.
* **Q4 (main loop, after the walk)**: switch "Talk to PayAI" on for payobook only.
