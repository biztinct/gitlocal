# OC1 REPORT — the server router (ONECHAT)

Phase: OC1 (handover §4, §7 server half, §8 R8/R9, §11 OC1). Branch `onechat`, worktree
`gitlocal-onechat`. Implementer: Opus. Status: **done offline, server tests written and waiting for
the clone stage** (no odoo-bin on this machine — PA10). No manifest version was bumped; nothing was
deployed; no live database was touched.

## 1. What OC1 delivers, in one paragraph
One server method, `learn.helper.route(text, screen_key, lang, session_id)`, now decides where every
sentence of the one helper chat goes — PayAI's command path, PayAI's question path (with
`ask_only`), the guide, Explain this screen, a practice turn, a choice, or one short note — in the
order of handover §4.3, with no model call (only the flag-gated guide composer at step 16, and only
where PayAI cannot answer). The conversation side is ready for OC2: `rpc_note_turn` records every
non-PayAI turn as an authored marker, `rpc_helper_status` answers the drawer's mount call, the
model's history never carries a marker, Clear conversation stops waiting plans, the engine's
catch-all no longer shows exception text (R8), and the tools-call cache can no longer hand an old
person's name across a Clear (R9).

## 2. Files
| Module | File | What |
|---|---|---|
| pb_learn | `models/learn_helper.py` (new) | `learn.helper` AbstractModel: the order of checks, the pure shapes (Q, H proc/def, data signal, figure/name/time refs, whole-sentence words, small talk, explain, capability, practise/tour triggers, topic/stemming, order task), hooks for the PayAI layers, the capability card. |
| pb_learn | `models/learn_intent.py` | `_score_kind` / `_on_screen` / `_resolve_scored` (results unchanged; `_resolve_hook` keeps its contract), `probe(question, screen_key, exclude)`, `answer_for(key, screen_key, lang)`, `_miss_payload`, the Access boundary (`ACCESS_LEARN`, `ACCESS_INTENTS`, `ACCESS_SIDEBAR_KEY`, `_access_visible`, `_access_filter`, also applied to `_explain_floor`), `practice_probe`, `explain_scenario_offer` try rule. |
| pb_learn | `models/__init__.py`, `tests/__init__.py`, `tests/test_helper_route.py` (new), `tests/data/onechat_route_corpus.json` (new) | Registration; the B-column server test; the pinned corpus (137 rows). |
| pb_learn content | `docs/tutorial_poc/author/data.js`, `tools/gen_learn_data.py`, `static/content/learn_content.json` (regenerated) | Scenario `match` phrases (EN, VI with marks, VI without) on all 25 live scenarios; 24 router chrome keys EN+VI; generator emits scenario `phrases` and REFUSES a phrase on two scenarios. `vi_VN.po` / `fixture.js` unchanged after generating (PA54 checked). |
| docs | `docs/tutorial_poc/author/contract.json` | `learn_helper.py` added to `coach-answers-from-writing-only`. |
| pb_payroll_ai_insights | `models/learn_helper.py` (new) | `_payai_available()` (group + active config → provider → `is_available()`, wrapped), `_voice_offered()`. |
| pb_payroll_ai_insights | `models/payroll_ai_conversation.py` | `_own_session`, `_note_label`, `rpc_note_turn`, `rpc_helper_status`, `get_history(skip_intents=)`, LLM history without `helper_note`. |
| pb_payroll_ai_insights | `models/payroll_ai_engine.py`, `i18n/vi_VN.po`, `tests/test_onechat_conversation.py` (new) | R8 catch-all sentence (EN+VI); 3 new msgids; server tests 1.14/1.17/1.18. |
| pb_payai_actions | `models/learn_helper.py` (new) | `_can_act`, `_looks_like_question`, `_command_key`, `_go_ahead_words`, `_route_payai_state`, `_waiting_plan`, `_tap_note` (runner msgids), `_route_command` + `_explain_chip`, `_capability_route`; read-only `runner.Ctx`, own conversation only. |
| pb_payai_actions | `models/payai_conversation.py`, `models/payai_engine.py`, `payai/runner.py` | E2 `ask_only` kwarg → `payai_ask_only` → `_ask_only_skips`; `rpc_helper_status` adds `voice_go_ahead`; E3 `action_clear` expires planned/clarify tasks; E1/R9 cache key + placeholder values. |
| pb_payai_actions | `tests/test_onechat_router.py` (new), `tests/offline/` (new: `odoo_stub.py`, `router_env.py`, `test_onechat_oc1.py`) | P-column + state server tests; the offline harness. |
| docs | `docs/handovers/onechat/ONECHAT_LEDGER.md` (new), this report | Seeded §15 + OC17–OC29. |

## 3. Test results
Offline (this machine):
```
python3 pb_payai_actions/tests/offline/test_onechat_oc1.py      Ran 26 tests … OK
  (corpus P + B, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 1.12, 1.13, 1.19, 1.20,
   1.21 offline half, 1.22, 1.23, 1.14 offline half, R9/3.9, shapes, practice_probe,
   white-label, and a REPLAY of pb_learn/tests/test_helper_route.py — its 13 methods, all green)
  negative control: one corpus expectation corrupted → test_1_1_P FAILED as it should.
check_contract.py --quiet          ✓ 73 checks passed
simulate_resolver.py               ✓ every property holds (scorer refactor mirrored)
gen_learn_data.py --check          ✓ generated data is up to date (6 files)   [was STALE at HEAD, OC22]
replay_tests.py                    TOTAL: 215 pass, 16 skip, 2 fail   — identical to HEAD (the 2 are
                                   the pre-existing "bridge suite did not run" node-resolve failures)
test_scenario_rules.py             ✓ 20 refusals and 1 acceptance
node pb_payai_actions/tests/js/client_fix.test.mjs   82 passed, 0 failed
pyflakes on every changed/new .py  clean
```
Server (clone stage, NOT run here — PA10/PA50): `pb_learn/tests/test_helper_route.py` (13 tests),
`pb_payroll_ai_insights/tests/test_onechat_conversation.py` (6), `pb_payai_actions/tests/
test_onechat_router.py` (9 + 4 Red; P3 Red tests blanked per PA56). All tagged `onechat`. Run with
`-u pb_learn,pb_payroll_ai_insights,pb_payai_actions --test-tags /pb_learn,/pb_payroll_ai_insights,/pb_payai_actions`
(PA35) and read PA11/PA40/PA55 environmental failures out. The pb_learn file was replayed offline;
the other two need records and are unexecuted — treat their first clone run as the real review.

Handover cases → where they are tested:
| Case | Offline | Server |
|---|---|---|
| 1.1 corpus | P + B, all rows incl. state rows | B: test_helper_route; P stateless: test_onechat_router; state: TestOneChatRouter(Red) |
| 1.2 no writes | n/a (no tables) | test_1_2 (B), test_1_1 asserts no task/message (P) |
| 1.3 no model call | provider raises on every corpus row | test_1_3, P column |
| 1.4 composer only at 16 | yes | test_1_4 |
| 1.5 / 1.6 / 1.7 / 1.8 | yes | yes |
| 1.9 / 1.10 / 1.11 / 1.12 / 1.13 | yes | yes |
| 1.14 markers | validation + labels + VI | real rows, owner refusal (manager read-all), history, LLM-history exclusion |
| 1.15 / 1.16 | — (needs runner + rows) | yes |
| 1.17 | — | yes (can_answer ×3, can_act on/off, voice_go_ahead) |
| 1.18 R8 | — | yes |
| 1.19 / 1.20 | yes | 1.20 yes |
| 1.21 ask_only | engine switch, all five branches | real send: no tools call / no task; go-ahead + reason still reach PayAI |
| 1.22 Access | yes (B + P, explain floor, practice) | yes |
| 1.23 small talk | yes | yes |
| 3.9 R9 (fixed here) | yes | — (offline covers it fully: pure function over patched seams) |

## 4. Routing corpus — observed (pinned in `pb_learn/tests/data/onechat_route_corpus.json`)
Screen `payruns` unless stated. "P" = payobook shape (PayAI can act, assistant set up); "B" = base.
| Sentence | Screen | State | P (payobook) | B (base) |
|---|---|---|---|---|
| how do I approve a request | payruns |  | guide / guide_strong (approve) | guide / guide_strong (approve) |
| How do I approve a request? | payruns |  | guide / guide_strong (approve) | guide / guide_strong (approve) |
| approve the request waiting for me | payruns |  | payai / command (chip: Explain how (approve)) | guide / guide_imperative (approve) |
| approve this run | payruns |  | payai / command (chip: Explain how (approve)) | guide / guide_imperative (approve) |
| approve | payruns |  | payai / command_ai (fallback=approve) | guide / guide_imperative (approve) |
| Run payroll? | payruns |  | choose / order_question (doOrHow; choices: payai/guide) | guide / guide (howrun) |
| Run payroll | payruns |  | payai / command (chip: Explain how (howrun)) | guide / guide_imperative (howrun) |
| Approve? | payruns |  | guide / guide (approve) | guide / guide (approve) |
| lock the week | payruns |  | guide / guide_offer (lockweek; chip: Do it for me) | guide / guide_imperative (lockweek) |
| run June payroll for Retail | payruns |  | payai / command (chip: Explain how (howrun)) | guide / guide_imperative (howrun) |
| help me run payroll | payruns |  | payai / command_ai | guide / guide_imperative (howrun) |
| please process June salaries | payruns |  | payai / command_ai | miss / guide |
| I'd like to run June payroll | payruns |  | payai / command_ai | guide / guide_imperative (howrun) |
| chạy lương tháng 6 cho Retail | payruns |  | payai / command (chip: Explain how (howrun)) | guide / guide_imperative (howrun) |
| show me how to run payroll | payruns |  | guide / guide_strong (howrun) | guide / guide_strong (howrun) |
| show me how to approve the June run | payruns |  | guide / guide_strong (approve) | guide / guide_strong (approve) |
| show me how payroll works | payruns |  | payai / question (ask_only=True) | miss / guide |
| show me the steps to run payroll | payruns |  | guide / guide_strong (howrun) | guide / guide_strong (howrun) |
| cho tôi xem cách chạy lương | payruns |  | guide / guide_strong (howrun) | guide / guide_strong (howrun) |
| can I approve the June run? | payruns |  | payai / data (ask_only=True; fallback=approve) | guide / guide_strong (approve) |
| where do I approve requests? | payruns |  | guide / guide_strong (approve) | guide / guide_strong (approve) |
| where can I approve | payruns |  | guide / guide_strong (approve) | guide / guide_strong (approve) |
| could I run payroll now? | payruns |  | payai / question (ask_only=True) | miss / guide |
| which button approves the run? | payruns |  | payai / question (ask_only=True) | miss / guide |
| hướng dẫn tôi chạy lương | payruns |  | guide / guide_strong (howrun) | guide / guide_strong (howrun) |
| chỉ tôi cách duyệt | payruns |  | payai / question (ask_only=True) | miss / guide |
| cách chạy lương tháng 6 | payruns |  | guide / guide_strong (howrun) | guide / guide_strong (howrun) |
| tôi có thể duyệt đợt lương tháng 6 không | payruns |  | payai / data (ask_only=True) | guide / weak (column:pay_runs) |
| let me practise running payroll | payruns |  | practice / practise (sc_payrun:try) | practice / practise (sc_payrun:try) |
| cho tôi thực hành chạy lương | payruns |  | practice / practise (sc_payrun:try) | practice / practise (sc_payrun:try) |
| let me practise approving overtime | payruns |  | practice / practise (sc_wftime:watch; watchOnlyNote) | practice / practise (sc_wftime:watch; watchOnlyNote) |
| practice | payruns |  | practice / practise (sc_payslips:try) | practice / practise (sc_payslips:try) |
| show me around Payobook | payruns |  | practice / practise (sc_welcome:watch) | practice / practise (sc_welcome:watch) |
| show me the tour | payruns |  | practice / practise (sc_welcome:watch) | practice / practise (sc_welcome:watch) |
| start the tour | payruns |  | practice / practise (sc_welcome:watch) | practice / practise (sc_welcome:watch) |
| open the practice company | payruns |  | practice / practise (chips:sc_payslips:sandbox_first) | practice / practise (chips:sc_payslips:sandbox_first) |
| how do I get off the practice company? | payruns |  | practice / weak (practice; chips:sc_payslips) | practice / weak (practice; chips:sc_payslips) |
| Is Lan on the practice company? | payruns |  | payai / data (ask_only=True) | practice / weak (practice; chips:sc_payslips) |
| Practice of paying overtime twice must stop | payruns |  | payai / command_ai | miss / guide |
| nhân viên mới đang tập làm quen | payruns |  | payai / command_ai | miss / guide |
| Làm thủ tục nghỉ việc cho Lan | payruns |  | payai / command_ai | miss / guide |
| làm thủ công | payruns |  | payai / command_ai | miss / guide |
| explain this screen | payruns |  | explain / explain | explain / explain |
| explain this screen is wrong | payruns |  | payai / question (ask_only=True) | miss / guide |
| what can you do | payruns |  | payai / command | guide / capability (capability) |
| what can I ask | payruns |  | guide / capability (capability) | guide / capability (capability) |
| giúp tôi | payruns |  | guide / capability (capability) | guide / capability (capability) |
| bạn làm được gì | payruns |  | payai / command | guide / capability (capability) |
| trợ giúp | payruns |  | payai / command | guide / capability (capability) |
| giúp tôi chạy lương | payruns |  | payai / command (chip: Explain how (howrun)) | guide / guide_imperative (howrun) |
| go ahead | payruns |  | note / nothing_waiting (nothingWaiting) | note / nothing_waiting (cannotActHere) |
| yes | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| thanks | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| hi | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| ok | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| uh | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| what is BHXH | payruns |  | guide / guide_strong (bhxh) | guide / guide_strong (bhxh) |
| how many payslips should there be | payruns |  | payai / question (ask_only=True) | miss / guide |
| how many payslips are in the June run | payruns |  | payai / data (ask_only=True) | miss / no_payai (noPayai) |
| how much back pay is owed to Lan | payruns |  | payai / data (ask_only=True; fallback=retroq) | guide / guide_strong (retroq) |
| what was Lan's last day | payruns |  | payai / data (ask_only=True; fallback=leaver) | guide / guide_strong (leaver) |
| how many people have their first day this month | payruns |  | payai / data (ask_only=True; fallback=firstday) | guide / guide_strong (firstday) |
| how many employees do we have | payruns |  | payai / data (ask_only=True) | miss / no_payai (noPayai) |
| how much does BHXH cost the company | payruns |  | payai / data (ask_only=True) | miss / no_payai (noPayai) |
| how do I compare two pay runs | payruns |  | payai / question (ask_only=True) | miss / guide |
| what is the most common reason a payslip changes | payruns |  | payai / data (ask_only=True) | guide / weak (rejectright) |
| show me headcount by department | payruns |  | payai / data (ask_only=False) | miss / no_payai (noPayai) |
| show me net pay for June | payruns |  | payai / data (ask_only=False) | miss / no_payai (noPayai) |
| open the runs board | payruns |  | payai / command | miss / guide |
| open the pay runs board | payruns |  | payai / command | miss / guide |
| where is the bank file | payruns |  | payai / question (ask_only=True) | miss / guide |
| bhxh là gì | payruns |  | payai / question (ask_only=True) | miss / guide |
| send it back | payruns |  | payai / command | guide / guide (rejectright) |
| Approve the overtime first | payruns |  | payai / command (chip: Explain how (approve)) | guide / guide_imperative (approve) |
| delegate my access | payruns |  | payai / command (chip: Explain how (delegate)) | guide / guide_imperative (delegate) |
| How do I approve a request? | approvals |  | guide / guide_strong (approve) | guide / guide_strong (approve) |
| practice | approvals |  | practice / practise (chips:sc_payrun,sc_payslips,sc_import,sc_people) | practice / practise (chips:sc_payrun,sc_payslips,sc_import,sc_people) |
| practice | dashboard |  | practice / practise (chips:sc_payrun,sc_payslips,sc_import,sc_people) | practice / practise (chips:sc_payrun,sc_payslips,sc_import,sc_people) |
| open the practice company | dashboard |  | practice / practise (chips:sc_payrun,sc_payslips,sc_import,sc_people:sandbox_first) | practice / practise (chips:sc_payrun,sc_payslips,sc_import,sc_people:sandbox_first) |
| what is BHXH | none |  | guide / guide_strong (bhxh) | guide / guide_strong (bhxh) |
| what is BHXH | dashboard |  | guide / guide_strong (bhxh) | guide / guide_strong (bhxh) |
| let me practise running payroll | none |  | practice / practise (sc_payrun:try) | practice / practise (sc_payrun:try) |
| how do I approve a request | none |  | guide / guide_strong (approve) | guide / guide_strong (approve) |
| practice | none |  | practice / practise (chips:sc_payrun,sc_payslips,sc_import,sc_people) | practice / practise (chips:sc_payrun,sc_payslips,sc_import,sc_people) |
| explain this screen | dashboard |  | explain / explain | explain / explain |
| lock the week | approvals |  | guide / guide_offer (lockweek; chip: Do it for me) | guide / guide_imperative (lockweek) |
| how many employees do we have | dashboard |  | payai / data (ask_only=True) | miss / no_payai (noPayai) |
| Tôi chạy bảng lương thế nào? | payruns |  | guide / guide_strong (howrun) | guide / guide_strong (howrun) |
| lam sao chay luong | payruns |  | guide / guide_strong (howrun) | guide / guide_strong (howrun) |
| cho toi thuc hanh chay luong | payruns |  | practice / practise (sc_payrun:try) | practice / practise (sc_payrun:try) |
| lam thu cong | payruns |  | payai / command_ai | miss / guide |
| tap lam quen | payruns |  | payai / command_ai | miss / guide |
| try again | payruns |  | payai / command_ai | miss / guide |
| thực hành | runpayroll |  | practice / practise (chips:sc_payrun,sc_schemes) | practice / practise (chips:sc_payrun,sc_schemes) |
| làm thử chạy lương | payruns |  | practice / practise (sc_payrun:try) | practice / practise (sc_payrun:try) |
| cảm ơn | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| xin chào | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| ờ | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| hmm | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| dạ | payruns |  | note / smalltalk (smalltalk) | note / smalltalk (smalltalk) |
| giải thích màn hình này | payruns |  | explain / explain | explain / explain |
| màn hình này là gì | payruns |  | explain / explain | explain / explain |
| what am I looking at | payruns |  | explain / explain | explain / explain |
| help | payruns |  | payai / command | guide / capability (capability) |
| tôi có thể hỏi gì | payruns |  | guide / capability (capability) | guide / capability (capability) |
| show me around | payruns |  | practice / practise (sc_welcome:watch) | practice / practise (sc_welcome:watch) |
| take the tour | payruns |  | practice / practise (sc_welcome:watch) | practice / practise (sc_welcome:watch) |
| give me a tour | payruns |  | practice / practise (sc_welcome:watch) | practice / practise (sc_welcome:watch) |
| đi một vòng payobook | payruns |  | practice / practise (sc_welcome:watch) | practice / practise (sc_welcome:watch) |
| cho tôi xem một vòng | payruns |  | practice / practise (sc_welcome:watch) | practice / practise (sc_welcome:watch) |
| thử trên công ty thực hành | payruns |  | practice / practise (chips:sc_payslips:sandbox_first) | practice / practise (chips:sc_payslips:sandbox_first) |
| take me to the practice company | payruns |  | practice / practise (chips:sc_payslips:sandbox_first) | practice / practise (chips:sc_payslips:sandbox_first) |
| i want to practise importing the month | payruns |  | practice / practise (sc_import:try) | practice / practise (sc_import:try) |
| practise how to close the week | payruns |  | practice / practise (sc_wfclose:try) | practice / practise (sc_wfclose:try) |
| let me practise adding an employee | payruns |  | practice / practise (sc_people:try) | practice / practise (sc_people:try) |
| let me practise something random entirely | payruns |  | practice / practise (chips:sc_payslips) | practice / practise (chips:sc_payslips) |
| rehearse | runpayroll |  | practice / practise (chips:sc_payrun,sc_schemes) | practice / practise (chips:sc_payrun,sc_schemes) |
| try it safely | formula |  | practice / practise (sc_formula:try) | practice / practise (sc_formula:try) |
| cancel | payruns |  | note / nothing_waiting (nothingToCancel) | note / nothing_waiting (nothingToCancel) |
| làm đi | payruns |  | note / nothing_waiting (nothingWaiting) | note / nothing_waiting (cannotActHere) |
| how do I pay less BHXH | payruns |  | guide / guide_strong (compliance) | guide / guide_strong (compliance) |
| pay less tax on salaries | payruns |  | guide / guide_strong (compliance) | guide / guide_strong (compliance) |
| go ahead | payruns | plan_amber | payai / goahead | note / nothing_waiting (cannotActHere) |
| làm đi | payruns | plan_amber | payai / goahead | note / nothing_waiting (cannotActHere) |
| yes | payruns | plan_amber | note / tap_card (tapDoIt) | note / smalltalk (smalltalk) |
| yes | payruns | plan_amber_voice | note / tap_card (tapDoItOrSay) | note / smalltalk (smalltalk) |
| ok | payruns | plan_red | note / tap_card (typeWordOnCard) | note / smalltalk (smalltalk) |
| cancel | payruns | plan_amber | note / tap_card (tapCancel) | note / nothing_waiting (nothingToCancel) |
| Practice of paying overtime twice must stop | payruns | reason_open | payai / open_question | — |
| explain this screen is wrong | payruns | reason_open | payai / open_question | — |
| thanks | payruns | reason_open | payai / open_question | — |
| yes | payruns | reason_open | payai / open_question | — |
| send it back | payruns | reason_open | payai / open_question | — |
| Approve the overtime first | payruns | reason_open | payai / open_question | — |
| how do I approve a request | payruns | reason_open | payai / open_question | — |
| let me practise running payroll | payruns | reason_open | payai / open_question | — |
| what can you do | payruns | reason_open | payai / open_question | — |


### Rows where the observation differs from the handover's expectation (reviewer: please judge)
| Row | Handover said | Observed | Why |
|---|---|---|---|
| delegate my access (P) | guide miss, no Watch/lesson/Show me | payai command (+ "Explain how instead" chip only when Access is visible) | PayAI's phrase table names `never_access` (its refusal card); step 11 sends phrase-table commands to PayAI. B is the guide miss when Access is hidden (OC20). |
| how many payslips should there be | guide guide_strong (howmanyslips) | P payai question / B miss | No `howmanyslips` phrase matches; "payslips"/"many" are ambiguous words. Content gap → OC4 (OC26). |
| how many payslips are in the June run (B) | guide (howmanyslips) | miss no_payai | Same gap. |
| how do I compare two pay runs | guide (H) | P payai question / B miss | No intent phrase; the only hit was the "Pay runs" COLUMN, which never answers a request for steps (router rule). OC4. |
| Run payroll? (B) | guide (Q, howrun) | guide guide (howrun) ✓ | — |
| approve (P) | command or command_ai | command_ai (fallback approve) ✓ | phrase table has no bare "approve". |
| could I run payroll now? | guide / payai question | P payai question / B miss | no guide hit (record). |
| Is Lan on the practice company? (B) | guide / miss, never a practice start | practice/weak with the guide's practice answer + chips | Not a start (no key); the guide's practice intent is drawn as chips (§4.5 last bullet). |
| what is the most common reason a payslip changes (B) | guide (whydiff) | guide weak (rejectright) | one long word; a weak answer is today's acceptance on a database without PayAI. |
| tôi có thể duyệt đợt lương tháng 6 không (B) | guide / miss | guide weak (the "Pay runs" column) | the column label "đợt lương" is in the question. |

## 5. Deviations from the handover (each with the reason)
1. **Content authored in OC1 that §10 assigns to OC4**: scenario `match` phrases for all 25 live
   scenarios (≥3 EN, ≥3 VI marked, ≥3 VI unmarked; `sc_wftime` has "approve overtime" / "duyệt tăng
   ca") and the router's 24 chrome keys. The router's practise step, test 1.12 and every note need
   them; without them OC1 could not be tested. OC4 extends (≥6 for the seven named scenarios is
   met for sc_payrun, sc_payslips, sc_import, sc_people, sc_wfclose, sc_hiring, sc_welcome in EN).
2. **"Can see Access" = `_station_reach('pb_settings.item_settings')`** — there is no Access
   left-menu entry (OC19). One constant + one method to retarget.
3. **Router rules added beyond §4.3's text** (each closes a corpus row the plain rules got wrong;
   PA59 kept in mind — each is narrow and has a test):
   * how-to requests are ALSO probed as "how do i <topic>" / "lam sao <topic>" (OC21);
   * orders are probed as "how do i <task>" with the lead and particulars removed, for "Explain how
     instead", and for "Here is how you do it." on a database that cannot act (OC21);
   * H is split into PROCEDURE (never a data question; column hits ignored) and DEFINITION/PLACE;
   * a quantity word next to "should / nên" and no figure is policy, not data;
   * the `practice` intent counts only when the sentence mentions practice, marks-aware (OC17);
   * `practice_probe` accepts a unique single-word hit (OC23);
   * the advice guard (compliance) is answered by the guide before steps 10/11 — a refusal never
     becomes a command, a data question or "Do it for me";
   * step 15 (weak) is for questions only, and step 18 answers a non-question only with kind
     overlap2 or better ("Practice of paying overtime twice must stop" → miss, not a practice card).
4. **Bare words**: "cancel" with nothing waiting → `note nothing_waiting` with a new key
   `nothingToCancel`; "yes"/"ok"/"dạ" with nothing waiting → small talk.
5. **Contract extras the client may read**: `choices[].ask_only`, `practice.sandbox_first` (the
   practice-company trigger), `note.key` `tapDoIt` / `tapDoItOrSay` (runner msgids, not chrome).
6. `ask()` keeps its miss dict inline (OC18); `_miss_payload` is its twin.
7. R9 (§3.3 says "Fixed in OC1") implemented here; its test 3.9 runs offline now.
8. `rpc_note_turn` also accepts `practice` with no key (a chips turn → "Practice mode") and `explain`
   keys as `screen:<k>`; refusals raise `UserError` (bad argument) / `AccessError` (not the owner);
   it returns `{session_id, message_id}`.
9. `get_history(limit, skip_intents=())` — new optional kwarg, used by `rpc_send_message` so a marker
   never takes the place of a real turn among the last ten.
10. The Explain floor is Access-filtered too (`_explain_floor` → `_access_filter`).

## 6. What changes what is stored or sent outside
* **Stored**: one assistant `payroll.ai.message` per non-PayAI turn (`intent='helper_note'`,
  `content` = an authored label from the content plane, `card` = `{kind, key, source_kind,
  screen_key}`, never a `task_id`, never client text). Only once OC2's client calls `rpc_note_turn`.
* **Audit**: Clear conversation now marks this person's planned/clarify PayAI tasks in that
  conversation `expired`.
* **Sent outside**: less, never more. `ask_only` removes the tools call for question-shaped
  sentences; small talk, bare words and practise/explain triggers reach no model; markers are
  filtered out of the model's history. The engine's catch-all no longer returns exception text.
* **Process memory**: the tools-call cache holds placeholders, not names, keyed per database,
  person and conversation.

## 7. Findings the handover asked for
* Vietnamese answer language (§5.5): OC2 item — not exercised by a server-only phase.
* `card.speak` month/name (test 3.8): OC3 item.
* **Owner decision Q6** (spoken plans naming a person or an amount always need a tap, enforced in
  the confirm path): not in OC1's scope as given; it touches `runner.confirm` — OC3 must carry it
  (with EN + VI tests).

## 8. Chrome keys
Added (EN + VI): `nothingWaiting`, `nothingToCancel`, `cannotActHere`, `typeWordOnCard`, `tapCancel`,
`smalltalk`, `noPayai`, `hereIsHow`, `hereIsHowOrPrepare`, `doItForMe`, `askPayData`,
`explainHowInstead`, `doItNow`, `howItWorks`, `whichMeant`, `doOrHow`, `watchOnlyNote`, `capTitle`,
`capExplain`, `capAnswer`, `capData`, `capAct`, `capPractise`, `capVoice`. Reused: `composedAnswer`,
`explainScreen`, `practiceMode`. Retired: none (OC2/OC4). No "Odoo" in any of them (tested).

## 9. Design-bar self-score (server phase — scored on what the router makes possible)
| Bullet | Score | Why |
|---|---|---|
| Right thing back with no tab to pick | 4 | 137-row corpus routes sensibly in both languages; a few content gaps fall to PayAI's question path (OC26). |
| Speaking instant and safe | 4 | `route()` cannot see voice; markers keep `_is_latest` honest; spoken UI is OC3. |
| Zero dead-ends | 4 | every miss carries suggestions; no_payai names the next step; practice falls back to chips + practice mode. |
| Plain screen words / no "Odoo" | 5 | all copy authored EN+VI in data.js; white-label test. |
| Locked palette / Lucide / motion | n/a | no UI in OC1. |

## 10. Open items for OC2 (and later)
* OC2 client: call `learn.helper.route` from the composer path only (test_practice tripwire);
  render `extra_chips` (primary "Do it for me"), `choices` (with `ask_only`), `practice.sandbox_first`,
  `note.key`; send `context: {lang}` on `rpc_note_turn` (OC28); call `rpc_helper_status` once on
  mount; map `intent == 'helper_note'` history rows to markers and set `card=null` (OC29); never write
  a marker for `tap_card` notes.
* OC3: Q6 server enforcement; 3.8 recording.
* OC4: content gaps (OC26), ≥6 phrases for the seven named scenarios in VI too, VI guide phrases
  (§10), then re-pin the affected corpus rows (run the offline suite; it prints every mismatch).
* Clone stage: run the three server files first; the P-column and state tests are the ones never
  executed.
