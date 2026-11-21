# OC4 REPORT — content: lessons, practise phrases, Vietnamese (ONECHAT)

Phase: OC4 (handover §10, §11 OC4, §16). Branch `onechat`, worktree `gitlocal-onechat`.
Implementer: Opus. Status: **done offline; PO gate PASSED on Payobook19v2; the server suites and
the browser walk wait for the clone stage** (PA10). No manifest version was bumped; nothing was
deployed; no live database or live addons directory was touched. The parallel OC2/OC3 fix agent's
files (coach.js, ai_insight_chat*.js/xml/scss, the node suites) were not edited; its commit
512335ba2 was re-scanned (no new user-visible strings).

§16 owner decisions applied: **Q3** the chat is "PayAI" in every lesson, tour and settings string
touched (lessons keep "… to PayAI" / "Nhờ PayAI"; ⌘K row untouched; voice switch label stays
"Talk to PayAI"); **Q1/Q2** content says "type, or speak" — never that words send themselves, and
no content reads figures aloud; **Q5** consent copy untouched beyond OC3; **Q7** Explain keeps its
next-step part (`explainHint` unchanged); **Q4** no switch default touched.

## 1. What OC4 delivers, in one paragraph
The Learn content now describes the screen people actually have: one PayAI chat, no tabs, no
"Your next step". The welcome lesson's help step is true on every database ("PayAI is on every
screen … Type, or speak if your company has turned voice on") and a second step, shown only where
PayAI may prepare work, teaches "read the plan first, nothing changes until you tap Do it". The
tour's last stop names PayAI, typing and speaking; the Vietnamese tour name is one name
("Đi một vòng Payobook") wherever it appears. Settings and consent copy no longer talk about "the
helper" or "the Coach". The guide now answers questions it used to miss ("bhxh là gì",
"bhyt là gì", "lương thực nhận là gì", "chạy lương thế nào", "where is the bank file", "how do I
compare two pay runs", "show me how payroll works", "chỉ tôi cách duyệt"), "How do I add a new
employee?" carries a Practise this chip, and every practice walkthrough on the handover's list
answers to at least six phrasings in English, Vietnamese and Vietnamese typed without marks.

## 2. Files
| File | What |
|---|---|
| `docs/tutorial_poc/author/data.js` | All content edits (§4). |
| `pb_learn/static/content/learn_content.json` | Generated from data.js on a scratch mirror and copied back (ledger OC59). `--check` clean. |
| `pb_learn/i18n/vi_VN.po` | Obsolete "Close" (old drawer header) removed. |
| `pb_payroll_ai_insights/i18n/vi_VN.po` | Four obsolete chat strings removed (§5). |
| `pb_learn/tests/test_onechat_content.py` (new), `pb_learn/tests/__init__.py`, `docs/tutorial_poc/author/tools/replay_tests.py` | 4.3 + content pins (§3). |
| `pb_learn/tests/test_feature_gate.py` | 4.2: one allow-listed ungated PayAI step; `test_02b` (LW split), `test_02c` (tour step). |
| `pb_learn/tests/data/onechat_route_corpus.json` | 20 rows re-pinned, 17 rows added (§6). |
| `pb_payai_actions/tests/offline/test_onechat_oc1.py` | One assertion follows the new guide answer (§6). |
| Docs (text only) | `PAYAI_PROGRAM.md`, `PAYAI_CLOSEOUT.md` (×2), `payai/P1_HANDOVER.md`, `LEARN_REFRESH_LEDGER.md`, `STEP2_PAYROLL_CORE.md`: a one-line ONECHAT note; `docs/design/payai-does-it.html:423` reworded. |
| `ONECHAT_LEDGER.md` (OC59–OC66), this report | |

## 3. Test results (offline, this machine)
```
python3 pb_payai_actions/tests/offline/test_onechat_oc1.py   Ran 34 tests … OK   (corpus 186 → 203 rows)
python3 pb_payai_actions/tests/offline/test_onechat_oc3.py   Ran 13 tests … OK
node pb_payai_actions/tests/js/onechat_oc2.test.mjs          146 passed, 0 failed
node pb_payai_actions/tests/js/onechat_oc3.test.mjs          143 passed, 0 failed
node pb_payai_actions/tests/js/client_fix.test.mjs           82 passed, 0 failed
replay_tests.py                                              TOTAL: 239 pass, 16 skip, 2 fail
   (2 = the pre-existing "bridge suite did not run" / engine JS @web/core import, same as HEAD;
    +8 test_onechat_content, +2 test_feature_gate; test_feature_gate 11 pass 3 skip)
check_contract.py --quiet                                    ✓ 73 checks passed
simulate_resolver.py                                         ✓ every property holds
test_scenario_rules.py                                       ✓ 20 refusals and 1 acceptance
gen_learn_data.py --check                                    ✓ generated data is up to date (6 files)
   vi_VN.po and fixture.js unchanged by the generator (mirror run; PA54 never struck)
```
Server (clone stage, not run here): `-u pb_learn,pb_payroll_ai_insights,pb_payai_actions
--test-tags /pb_learn,/pb_payroll_ai_insights,/pb_payai_actions` (PA35) — new
`test_onechat_content` (8, source-only, already replayed), `test_feature_gate` 02b/02c, and the
server corpus replays (`test_helper_route`, `test_onechat_router`) against the re-pinned corpus.

Handover cases: **4.1** `--check` clean, vi_VN.po / fixture.js unchanged after generating (mirror).
**4.2** `test_feature_gate::test_02b` (LW split: ungated help step has no acting words; the
`payai_prepare` step follows it and is the only one dropped when off) and `test_02c` (tour step
names PayAI, no prepare clause, VI name). **4.3** `test_onechat_content::test_01` (255 chrome keys
the code reads, all present EN + VI) and `test_02` (11 retired keys gone and unread). **4.4** server.

## 4. Content items changed
**Chrome retired** (EN + VI; no code reads them since OC2): `tabGuide`, `tabAsk`, `tabPractice`,
`nextStep`, `thisScreen`, `askDataInstead`, `askDataLead`, `practiceTry`, `practiceTour`,
`practiceTourLead`, `honest`; the stale "three tabs" comment rewritten.
**Chrome reworded**: `coachNoScreen` ("…ask me about it, or ask me how to do something, in the box
below"), `swNextBody` ("The lesson map shows one next lesson…" — the drawer no longer does),
`swCollectBody` ("agrees in PayAI"), `consentBody` ("PayAI works exactly the same either way";
test_questions 04c/04d promises intact), `welcomeGo` VI → "Đi một vòng Payobook".
**Chrome added**: none needed — every key §10 lists was added by OC1–OC3 except `readAloudOn/Off`
and `nowOn`, which no code reads (the More menu uses `readAloud`, the divider `onScreen`).
**Lesson LW** (welcome): the help step → "PayAI is on every screen" (ungated: asking, practice
copy, type or speak; "what to do next" and "It explains — you act" dropped) + a new
`requires: payai_prepare` step "Ask PayAI to do something, and read the plan first" (Do it /
Thực hiện). LW goes 8 → 9 steps where PayAI may prepare, stays 8 elsewhere.
**PayAI P4 lesson steps**: unchanged ("Type … to PayAI" stays, Q3; Red tip stays).
**Tour `sc_welcome`**: tagline "…and PayAI"; last step "And PayAI is always one press away" — type
or speak when voice is on, answers, practice copy; no "prepares" clause (scenario steps cannot be
gated — OC62). Formula Studio walkthrough step "The copilot knows this configuration" → "PayAI
knows this configuration".
**Intents**: `addperson` `try: sc_people` (Practise this). No intent is about the formula engine
as a task — `editlive`/`whichconfig`/`configvsstructure` teach judgement, not the sc_formula walk —
so **no formula try was added** (handover: "else report"). New phrases: `bhxh` (bhxh là gì / la gi,
bảo hiểm xã hội là gì), `howrun` (chạy lương thế nào / chay luong the nao, cách chạy lương /
cach chay luong, how does payroll work, how payroll works), `approve` (chỉ tôi cách duyệt, cách
duyệt đợt lương / cach duyet dot luong), `getpaid` (where is / find the bank file, tệp ngân hàng ở
đâu / tep ngan hang o dau), `variance` (compare two pay runs, compare this run with last month,
so sánh hai đợt lương / so sanh hai dot luong), `howmanyslips` (should I check, nên đọc bao nhiêu
phiếu lương, có phải đọc hết không). **New intents** `bhyt` ("What is BHYT?") and `netpay` ("What
is net pay?"), screen-scoped, glossary facts + source (OC60). `firstday` VI names the tour by its
name; its source and `whichpolicy`'s fallback say "PayAI", not "this helper" / "the Coach".
**Scenario phrases**: sc_welcome +7, sc_payrun +4, sc_payslips +4, sc_import +4, sc_people +4,
sc_wfclose +6, sc_hiring +4 — each of the seven now ≥6 EN, ≥6 VI with marks, ≥6 VI without marks
(pinned, `test_06`); every other live scenario ≥3 each (OC1); sc_wftime keeps "approve overtime" /
"duyệt tăng ca". The generator's duplicate-phrase refusal stayed quiet.

## 5. Vietnamese .po (every new or changed string across OC1–OC3)
Method: Odoo's own extractors run on the server over `git archive 0910b7149` vs the current tree
(after 512335ba2) of the three modules (ledger OC65). Result:
* **New msgids (9)** — all already had one-line VI entries with `#. module:` / `#. odoo-python|
  odoo-javascript` / `#: code:addons/…:0`, identical (no) placeholders: pb_payroll_ai_insights ×8
  ("From your pay data", the figures sentence, the R8 error sentence, the tap-to-talk consent body,
  "Tap to speak", "That conversation belongs to somebody else.", "That note cannot be recorded.",
  "This kind of recording cannot be used here. Please try typing."), pb_payai_actions ×1 (the Q6
  tap sentence). pb_learn: none (its new copy is Learn chrome, EN + VI in data.js).
* **Gone msgids → VI entries deleted (5)**: pb_learn "Close"; pb_payroll_ai_insights "Ask about
  your pay data", "Numbers, people, trends, or how to do something. Charts appear right here.",
  "Read aloud: on", "Read aloud: off". ("Hold the microphone…" / "Hold to speak" were already
  replaced in OC3.)
* No module ships a `.pot`, so PA58 does not apply. The router's "Tap Do it…" notes reuse the
  runner's msgids (`_lt(variable)` in pb_payai_actions — same module catalogue).
* **PO gate** (`/tmp/p4_po_gate.py` on Payobook19v2, files in `/tmp/onechat_po/<module>/i18n/`):
```
OK   /tmp/onechat_po/pb_learn/i18n/vi_VN.po rows=238 code=75 reach-screen=75 code-without-marker=0
OK   /tmp/onechat_po/pb_payroll_ai_insights/i18n/vi_VN.po rows=362 code=117 reach-screen=117 code-without-marker=0
OK   /tmp/onechat_po/pb_payai_actions/i18n/vi_VN.po rows=602 code=499 reach-screen=499 code-without-marker=0
GATE PASSED
```

## 6. Routing corpus — rows that changed (reviewer: please judge)
All 20 moved rows went from PayAI's question path (`ask_only`) or the honest miss to a written
guide answer; **none became a command, none became a plan, no safety row was loosened**.
| Sentence (payruns) | Was P / B | Now P and B |
|---|---|---|
| show me how payroll works | payai question / miss | guide guide_strong howrun |
| chỉ tôi cách duyệt | payai question / miss | guide guide_strong approve |
| how do I compare two pay runs | payai question / miss | guide guide_strong variance |
| where is the bank file · Where is the Bank File? | payai question / miss | guide guide_strong getpaid |
| bhxh là gì | payai question / miss | guide guide_strong bhxh |
| tôi muốn biết cách chạy lương | payai question / miss | guide guide_strong howrun |
| What is Net Pay? · ok what is net pay · Ok, what is Net Pay? | payai question / miss | guide guide_strong netpay |
Unchanged on purpose: "What is Lan's net pay?", "what is the net pay of Lan", "show me net pay
for June" stay PayAI data; "how many payslips should there be" / "… are in the June run" stay as
OC1 observed (OC64). `test_howto_in_mid_sentence_is_never_a_command` now expects the guide's
howrun answer for "tôi muốn biết cách chạy lương" and still asserts it is never a command.
17 rows added (observed): bhyt là gì / la gi, what is BHYT (payslips), lương thực nhận là gì /
luong thuc nhan la gi, what is net pay, What is Lan's take-home pay? (stays PayAI data), bhxh la gi,
chạy lương thế nào / chay luong the nao, cách chạy lương, chỉ tôi cách duyệt tăng ca (wftime →
approveot), and six practise starts in Vietnamese / English on employees, wfclose, hiring,
payslips (sc_people, sc_wfclose, sc_hiring, sc_payslips Try).

## 7. Deviations (each with the reason)
1. **Two new intents** (`bhyt`, `netpay`) instead of phrases "on the existing intents": none
   existed (OC60).
2. **"how many payslips should there be" not mapped to `howmanyslips`**: different question (OC64).
3. **Ungated LW step says "PayAI"**, allow-listed in test_feature_gate: Q3 names the chat PayAI
   everywhere (OC61).
4. **Tour step without the "prepares" clause**: scenario steps cannot be gated (OC62).
5. **Generator run on a scratch mirror**, never in the worktree; only `learn_content.json` copied
   back (OC59) — the result is byte-identical to a hand edit plus the right version hash.
6. Retired four more unread Practice-tab keys than §10 lists (`thisScreen`, `practiceTry`,
   `practiceTour`, `practiceTourLead`) — the tab is gone and nothing reads them; the tour-name
   mismatch lived in `practiceTour`'s Vietnamese.

## 8. What changes what is stored or sent outside
Nothing new is stored or sent. The guide (no model call) now answers ~10 sentence shapes that used
to go to PayAI's question path — fewer AI calls on payobook, fewer honest misses elsewhere.
`learn_content.json` changes reach every database at the next restart (one file, no upgrade);
the .po deletions need `-u` to drop the stale rows from the database (harmless if left).

## 9. Design-bar self-score
| Bullet | Score | Why |
|---|---|---|
| The right thing back with no tab to pick | 5 | Ten more everyday questions get a written answer in both languages; practise phrases cover how people actually say it, with or without marks. |
| Speaking instant and safe | 4 | Lessons and the tour say "type, or speak" and never promise a spoken go-ahead; nothing claims auto-send. |
| Zero dead-ends | 5 | No content points at a tab, a "next step" card or an Ask-tab hand-off that no longer exists; add-a-person now ends in Practise this. |
| Plain screen words, never "Odoo" | 5 | PayAI by name; one Vietnamese tour name; white-label and stale-word scans pinned (`test_onechat_content` 03/04). |
| Locked palette, Lucide, no gradients, motion | n/a | Content phase — no UI drawn. |

## 10. Open items
* Clone stage: the three modules' server suites (incl. the re-pinned corpus on real records), then
  the OC2/OC3 walk W1–W17; look at LW on a payobook-like clone (9 steps) and a base clone (8).
* `pb_website` landing mock still says "or hold to speak" (OC66) — website pass.
* `helper-composer` anchor stays `reserved`: LW plays on the practice replica, which has no drawer.
* PayAI program (unchanged from OC3): month as "June, month 6" in plan read-backs (OC54).
