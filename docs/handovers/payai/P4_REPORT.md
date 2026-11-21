# PAYAI P4 — report (Vietnamese + close-out)

Implemented by Opus, 2026-10-12/13, against `P4_HANDOVER.md`. Nothing deployed to any live database. All clone runs
staged from `git archive <commit>` (PA38/PA41) into `/tmp/payai_p4stage` on `Payobook19v2`, database `p0clone`,
port 8099, detached `systemd-run` units `p4-test-1…4` (harness `/tmp/p4_test.sh`, copy of P3's, PA50).

**Ship commit: `6327ca99b`** (versions moved only there, PA41). Commits of this phase (branch 19.1, not pushed):

| commit | what |
|---|---|
| `49afe270d` | fix: P4-W1 one Records door; P4-W2 plain wording (+ tests) |
| `a2a004cc5` | Vietnamese understanding: phrase table, months, amounts, dates, confirm words, number/date writing, approvals `pb_focus` on doors (labelled wip: catalogue + tests follow) |
| `a88c808af` | pb_approval_config `inbox.js`: opens on one request from `pb_focus request:<id>[:scope]` |
| `f1616bb5f` | vi_VN catalogues (pb_payai_actions new; pb_payrun_wizard, pb_audit, om_hr_payroll, pb_payroll_ai_insights) + PA11 unwrap + tests |
| `f663d00a3` | test-class fix (only inherited test methods switched off); scheme term aligned to "chương trình lương" |
| `a54ec45ac` | Learn: "Ask PayAI" step (Runs lesson) + typed-word tip (Approvals lesson), EN+VI; test 8 |
| `6327ca99b` | **ship**: 7 manifest bumps |
| (this) | docs: P4_REPORT.md, PAYAI_CLOSEOUT.md, ledger PA51–PA56 |

## P4-W1 / W2 (walk findings) — `49afe270d`
| # | Finding | Fix | Test |
|---|---|---|---|
| W1 | pay-value refusal drew "Open People › Records" twice | `runner._missing_card` skips the Action's door when the resolver already offers the same `door_id` | `TestPayaiP4Walk.test_w1_one_records_door_only` (exactly one door, no duplicate labels) |
| W2 | "This person's scheme has no pay value that can be changed here" | "Nothing on **<scheme>** can be changed from here yet: Records has no pay value on it that you may change. Open People › Records to see what you can change." (scheme read with the person's rights, PA31; neutral sentence otherwise); "What can you do?" chip kept | `test_w2_says_why_and_offers_what_can_you_do` |

## What was built
- **Vietnamese catalogue** — `pb_payai_actions/i18n/vi_VN.po` (new, 515 entries, single-line, every entry `#. module:`
  first, `#. odoo-python`/`#. odoo-javascript`, `#: code:addons/pb_payai_actions/…:0`; model terms for the settings
  view, fields, selections). Built from a template exported on the clone from the STAGED tree only (the live copy of
  the module would add its older strings — PA52). Vocabulary is the screens': đợt lương (pay run), kỳ lương (period),
  chương trình lương (scheme — the Run screen, Records and Learn say it; PA53), phiếu lương, duyệt / trả lại / từ chối,
  Nháp, Hồ sơ, Các đợt lương, mục Phê duyệt, Chi trả & gửi phiếu, Truy cập và ủy quyền. "PayAI" stays the brand.
- **Vietnamese understanding** (`payai/phrases_vi.py`, one row per Action; registry tries them after the English ones,
  on the marked text then with marks folded; slot texts are sliced from the original so names keep their marks):
  chạy/tính lương … cho …, gửi duyệt …, duyệt …, trả lại … vì …, từ chối … vì …, mở …, xem …, tải Excel …, gửi phiếu
  lương …, đổi <khoản> của <tên> thành <số> từ <tháng>, cho <tên> <khoản> <số>, lập tờ khai …, xoá … (→ never).
  Politeness cut (bạn giúp tôi … nhé / được không); how/why questions stay questions (làm sao, tại sao, … là gì).
- **Months/amounts/dates**: tháng 6, tháng sáu (June) vs tháng sau (next month — told apart on the marks), tháng 12 năm
  2031, tháng 6/2026, T6, tháng này/trước/tới; 500.000, 1.500.000,5, 5 triệu, 500 nghìn, 500.000đ; ngày 1 tháng 11,
  1/11/2026, hôm nay. Writing: `i18n.num/short_amount/month_label/stamp` (500.000 · ₫18,6 tỷ · tháng 12 năm 2031 ·
  13/10/2026 14:05) for a Vietnamese reader; English unchanged. Run NAMES stay English like the wizard's.
- **Confirm words**: DUYỆT / TRẢ LẠI / TỪ CHỐI beside APPROVE / SEND BACK / REJECT; either accepted from anybody;
  capitals, marks and inner spaces folded on the server (`runner.word_ok`) and the client (`normWord`/`wordMatches`);
  the card shows the word in the person's language (`typed.word`) and lists both (`typed.words`). Vietnamese spoken
  go-ahead words for Amber (tiến hành, làm đi, xác nhận…).
- **Tools schema stays English** whatever the reader's language (`i18n.EN`): the 13 Action summaries are model-only
  and are not in the catalogue.
- **Approvals deep link**: Red plan "Open my approvals instead", not-yours "Open my approvals", conflict and result
  cards carry `hub.focus` = `request:<id>[:me|team|org]` (+ `context.pb_focus`); `inbox.js` reads it from its own
  action or the hub action it is a lens of (`actionService.currentAction`), switches scope, opens the drawer once per
  arrival (on "All I can see" when not in My turn). pb_home_hub untouched.
- **Learn**: L2 (Runs) 10th step on `pk-card` — "Or ask PayAI, and read its plan first" (plan card → Do it →
  Withdraw for 10 minutes; tip: Run payroll the same, Undo deletes the draft); LA (Approvals) `ai-approve` tip — PayAI
  records it only when you type APPROVE / DUYỆT. EN+VI, generated with `gen_learn_data.py`; the generator's unrelated
  rewrites of `pb_learn/i18n/vi_VN.po` and `fixture.js` were discarded (PA54). `check_contract.py`: 73 checks passed.
- **Other modules' PayAI strings**: pb_payrun_wizard 14 (gate, period refusals, protected-payroll sentences, prefill
  note), pb_audit 2, om_hr_payroll 1 (email-all refusal), pb_payroll_ai_insights 1 (card field label).

## Tests (P4 handover 1–10) — `pb_payai_actions/tests/test_payai_p4.py` (14 methods, all ran, none skipped)
| # | Test(s) | Asserts | Result |
|---|---|---|---|
| 1 | `test_01_every_catalogue_parses_and_every_entry_reaches_a_screen`, `test_01b_every_shown_string_has_vietnamese` | PoFileReader over all 5 touched catalogues; every pb_payai_actions entry: module line first, marker, code/model occurrence; every `_lt`/`_` (summaries excepted) and JS `_t` literal re-derived from source has non-identical Vietnamese with the same placeholders; the other modules' PayAI strings translated | pass |
| 2 | `test_p4_02_vietnamese_plan_card` | vi_VN officer: "chạy lương tháng 12 năm 2031 cho Payai Retail End-Month" → plan "Chạy lương", subtitle "Chuẩn bị · tạo một đợt lương nháp…", Kỳ lương "1 đến 31 tháng 12 năm 2031", Chương trình lương, Nhân viên "Toàn bộ 3 người…", note "Chưa có đợt lương tháng 12 năm 2031 cho …", buttons Thực hiện / Mở trên màn hình thay vào đó / Hủy bỏ; no English words; run name stays "… · December 2031" | pass |
| 3 | `test_p4_03_vietnamese_confirm_words`, `test_p4_03b_send_back_in_vietnamese_with_the_english_word` | `word_ok` table (DUYỆT/duyet/Duyệt/APPROVE yes; "duyệt đi"/aprove/TRẢ LẠI no; TRẢ LẠI/tra lai/SEND BACK; TỪ CHỐI/tu choi/REJECT); Red plan in VI (word DUYỆT, words {APPROVE, DUYỆT}, hint "Gõ DUYỆT để xác nhận", step "…, bước 1 trên 2", figures "1 người · thực nhận …"); wrong word → inline VI hint naming DUYỆT; tap → "Việc này cần gõ để xác nhận"; "duyet" → decided once, VI outcome + audit line; VI send-back sentence with reason → plan word TRẢ LẠI, confirmed with "send back" → returned, run draft, VI outcome | pass |
| 4 | `test_04_every_vietnamese_phrasing_finds_its_action`, `test_04b_vietnamese_months` | 20-row VI table → action key + slot texts; 3 VI questions stay questions; **every "What can you do?" example, in Vietnamese, routes to its own Action** (21); tools schema English for a VI reader; month table incl. sáu/sau; writing helpers | pass |
| 5 | `test_05_vietnamese_numbers` | 500.000→500000, 1.500.000,5→1500000.5, 500,000→500000, 5 triệu, 500 nghìn, 500.000đ, 1,5 triệu; the VI pay-value sentence's value parses to 500000 | pass |
| 6 | `test_06_inbox_reads_the_focus_the_cards_send`, `test_p4_06_not_yours_card_opens_the_request` (+ test 3's door asserts) | `approvals_hub` writes `request:<id>[:scope]`; the regex lifted out of `inbox.js` accepts exactly that and rejects `queue`/`month:…`; consume-once + `currentAction` present; VI not-yours card ("Việc này không chờ bạn", chip "Nhắc Minh") door carries the request id; plan and done doors carry it. JS executed locally in node: `focusRequest` → `{id:42,scope:"me"}`, `{42,"org"}`, null for `queue`/`month:2026-06`/empty | pass |
| 7 | `TestPayaiP4Walk.test_w1…`, `test_w2…` | above | pass |
| 8 | `test_08_learn_teaches_asking_payai_in_both_languages` | the L2 "Ask PayAI" step (EN+VI words: plan card/Do it/Withdraw/10 minutes · thẻ kế hoạch/Thực hiện/Rút lại/10 phút), the LA tip (APPROVE / DUYỆT), screens match, anchors registered AND laid in their templates; the taught sentences route | pass |
| 9 | PA11 (`test_data_access.test_06`, `test_egress.test_04d/04e`) | green — see below | pass |
| 10 | `test_10_no_odoo_on_any_card` | no "odoo" in any msgid/msgstr, Python/JS literal, or visible XML text/attribute of pb_payai_actions | pass |

**PA11**: the three failures were not missing Vietnamese: the three entries existed but were wrapped over several
lines, and those tests read the catalogue with a single-line regex. Unwrapped (wording unchanged) → green. Deviation 1.

### Clone runs
| run | code | `-u` = `--test-tags` | result |
|---|---|---|---|
| p4-test-1 | `f1616bb5f` | payai_actions, payroll_ai_insights, payrun_wizard, audit | EXIT=255 — my test module set `test_tags` to None while switching off inherited tests (fixed `f663d00a3`) |
| p4-test-2 | `f663d00a3` | same 4 | `pb_audit: 12 tests` · `pb_payai_actions: 77 tests 23.82s` · `pb_payroll_ai_insights: 128 tests` · `pb_payrun_wizard: 71 tests` · `6 failed, 14 error(s) of 240 tests` = **all 20 PA40** |
| p4-test-3 | `a54ec45ac` | + pb_learn, pb_approval_config, om_hr_payroll | 623 tests; 20 PA40 + 5 environmental (below) |
| **p4-test-4** | **`6327ca99b` (ship)** | payai_actions, payroll_ai_insights, payrun_wizard, audit, learn, approval_config, om_hr_payroll | `pb_approval_config: 138 tests 35.97s` · `pb_audit: 12 tests 1.53s` · `pb_learn: 302 tests 47.96s` · `pb_payai_actions: 78 tests 24.92s 22701 queries` · `pb_payroll_ai_insights: 128 tests 2.26s` · `pb_payrun_wizard: 71 tests 10.65s` · **`8 failed, 17 error(s) of 623 tests`**; 14 `TestPayaiP4*` methods started. `latest_version` on p0clone after: pb_payai_actions 19.0.4.0.0, pb_approval_config 19.0.1.6.2, pb_learn 19.0.20.5.2, pb_payrun_wizard 19.0.1.32.1, pb_audit 19.0.1.4.1, om_hr_payroll 19.0.1.8.2, pb_payroll_ai_insights 19.0.3.12.1 |

Failures at the ship run, none caused by P4: **20 = PA40** (pb_payrun_wizard fixed-2026 tests; p0clone still holds the
**3** done "Walk Sales Jun/Jul/Aug" 2026 runs, counted by SQL after the run); **3** pb_approval_config
`test_static_contract` errors and **1** `test_vietnamese.test_z06c` failure read SIBLING modules from the test's own
directory — the stage holds only the 17 staged modules, so `pb_import_kit/…/import_tokens.scss` etc. are "missing"
(PA55: environmental, not code); **1** pb_learn `test_questions.test_07b` — the question-mining cron is inactive on
p0clone. pb_payai_actions, pb_payroll_ai_insights (PA11 included), pb_audit: 0 failures, 0 errors, 0 skipped.
The upgrade log shows each touched module loading its `vi_VN.po` (no error); on p0clone the settings field reads
"PayAI được quyết định (duyệt, trả lại, từ chối)" and the settings view carries a vi_VN arch.

### PO parse gate (PoFileReader, the server's own odoo, over the STAGED tree, as user odoo)
```
OK   pb_payai_actions/i18n/vi_VN.po rows=551 code=450 reach-screen=450 code-without-marker=0
OK   pb_payrun_wizard/i18n/vi_VN.po rows=107 code=103 reach-screen=103 code-without-marker=0
OK   pb_audit/i18n/vi_VN.po rows=94 code=80 reach-screen=80 code-without-marker=0
OK   om_hr_payroll/i18n/vi_VN.po rows=481 code=16 reach-screen=1 code-without-marker=15   (15 pre-existing)
OK   om_hr_payroll/i18n/vi.po rows=480 code=15 reach-screen=0 code-without-marker=13      (pre-existing, untouched)
OK   pb_payroll_ai_insights/i18n/vi_VN.po rows=360 code=115 reach-screen=115 code-without-marker=0
OK   pb_approval_config/i18n/vi_VN.po rows=710 code=604 reach-screen=604 code-without-marker=0
OK   pb_learn/i18n/vi_VN.po rows=238 code=76 reach-screen=76 code-without-marker=0
GATE PASSED   (and all 90 .po files of the 17 staged modules: GATE PASSED)
```
Same gate locally (`/Users/adity/odoo19/odoo`, venv polib): PASSED.

### Vietnamese coverage (strings translated / user-visible strings found)
| module | translated / found | note |
|---|---|---|
| pb_payai_actions | **515 / 515** | 528 in the exported template; 13 excluded on purpose (12 Action summaries = tools prompt, 1 debug-only field help) |
| pb_payrun_wizard | 14 / 14 PayAI strings | P0 gate/period/protected-payroll sentences, P2 prefill note |
| pb_audit | 2 / 2 | "Asked PayAI: …" row title, "PayAI" source label |
| om_hr_payroll | 1 / 1 | email-all refusal |
| pb_payroll_ai_insights | 1 / 1 shown (+3 PA11 unwrapped) | card field help is debug-only |
| pb_hub | 0 / 0 | the ⌘K "Ask PayAI to…" row lives in pb_payai_actions (`payai_palette.js`) — translated there |
| biz_approval_workflow | 0 / 0 | nothing user-visible |
| pb_learn | banner already VI (P2-F3) | + the new step and tip, EN+VI |

## Weak-test review
Each guard removed alone fails its test: the door dedupe (W1), the new sentence (W2), the marker/occurrence scan and
the coverage scan (1), the Vietnamese phrase rows and the example routing (4), `EN()` for the tools schema (4), the
marks/sau check (4b), `fold` in `word_ok` ("duyet") and the VI word list (DUYỆT shown) (3), `num`/`month_label` VI
branches (2, 4b), the focus format on either side (6), the Learn step/tip (8), "odoo" anywhere (10). The client half
(JS `normWord`/`wordMatches`, `focusRequest`) is not run by the server suite — checked in node locally (deviation 4).

## Design bar (verbatim: "Extreme WOW, intuitive, out-of-this-world experience, best in class.") — self-score, code only
- Written for a Vietnamese officer, not translated: **4** — screen vocabulary, short sentences, "tháng 12 năm 2031",
  "500.000", "₫18,6 tỷ", the word to type in their language; not yet read on screen by a native reader.
- Understands them: **4** — every Action has Vietnamese phrasings, unmarked typing works, every example on "What can
  you do?" is a sentence PayAI itself understands; scheme words are the scheme's own (a demo division's Vietnamese
  name is understood: "cho Bán lẻ").
- Zero dead-ends: **5** — W1/W2; approvals doors now open the request itself.
- No "Odoo": **5** (test 10).

## Deviations (with reasons)
1. **PA11 fixed by unwrapping, not adding**: the translations existed; only their line layout hid them from the tests'
   single-line reader. Wording unchanged.
2. **Learn content went into two existing lessons**, not a new lesson/station: the generator takes ONE lesson per
   station (`gen_learn_data.py:613`), and a new station ripples into role paths, the rail and milestone tests. L2 had a
   free step slot (9 → 10, the cap is 10); LA is at 10, so the typed word is a tip on its approve step.
3. **Scheme = "chương trình lương"**: the product uses two words (Run screen, Records, Learn: chương trình lương;
   scheme map, approvals: phương án lương). PayAI's cards follow the Run screen and Learn they sit next to (PA53).
4. **JS halves tested locally, not on the server** (no browser on the box): node runs of `normWord`/`wordMatches` and
   the real `focusRequest` lifted from `inbox.js`; the server test pins the shared format.
5. **"People" slot = "Nhân viên"** (who the run pays), not the hub name "Con người"; the hub name is used in "Mở Con
   người › Hồ sơ".
6. **Commit shape**: `a2a004cc5` is labelled wip (its catalogue/tests landed in the next commits); the deep-link door
   `hub.focus` server half rode in it because the hunks interleave with the typed-word hunks in `actions_red.py`.

## DEPLOY NOTES (Fable deploys — PA14 go-ahead; PA41 check `latest_version` before/after; stage from `git archive 6327ca99b`)
| module | version at ship `6327ca99b` | stored field? | installed on | upgrade |
|---|---|---|---|---|
| pb_payai_actions | 19.0.3.0.0 → **19.0.4.0.0** | no | **payobook only** | payobook |
| pb_approval_config | 19.0.1.6.1 → **19.0.1.6.2** | no (inbox.js) | every DB | payobook now; others when convenient (the doors that send `pb_focus` only exist on payobook) |
| pb_learn | 19.0.20.5.1 → **19.0.20.5.2** | no (content JSON) | every DB it is installed on (check `ir_module_module`) | payobook now; others batch |
| pb_payrun_wizard | 19.0.1.32.0 → **19.0.1.32.1** | no (vi_VN.po) | every DB | `-u` + PO gate on each DB it is installed on |
| pb_audit | 19.0.1.4.0 → **19.0.1.4.1** | no (vi_VN.po) | every DB | same |
| om_hr_payroll | 19.0.1.8.1 → **19.0.1.8.2** | no (vi_VN.po) | every DB (p0clone had 19.0.1.8.0 — check live before) | same |
| pb_payroll_ai_insights | 19.0.3.12.0 → **19.0.3.12.1** | no (vi_VN.po) | every DB | same |

Sequence on payobook: PO gate over the staged tree → `-u pb_payai_actions,pb_approval_config,pb_learn,pb_payrun_wizard,
pb_audit,om_hr_payroll,pb_payroll_ai_insights` → `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` →
restart. Other DBs: the five modules with new .po entries need `-u` + the gate wherever installed (Vietnamese is
installed there); PENDING.md rows are Fable's (this phase did not touch PENDING.md). No tier switch changes; tenants
stay off.

## WALK LIST for Fable on payobook.com, in Vietnamese (visible window, console open; PA24/PA42)
Before: switch the QA login's language to Tiếng Việt (Preferences); hard-reload. "PayAI may decide" on.
| # | Type (or do) | Expected |
|---|---|---|
| 1 | "Bạn làm được gì?" | card "Đây là những việc tôi làm được cho bạn"; examples in Vietnamese; tap "Chạy lương tháng 6 cho Bán lẻ" → it runs as a sentence |
| 2 | "chạy lương tháng 12 năm 2026 cho Retail End-Month" (or "… cho Bán lẻ") | plan "Chạy lương"; Kỳ lương "1 đến 31 tháng 12 năm 2026"; Chương trình lương; Nhân viên "Toàn bộ N người…"; buttons Thực hiện · Mở trên màn hình thay vào đó · Hủy bỏ; numbers with dots |
| 3 | Hủy bỏ | "Đã ghi lại: … đã hủy …" |
| 4 | "chạy lương tháng 12 cho Retail End-Month chỉ Vũ Khánh Chi" | Nhân viên "Vũ Khánh Chi (1 trên N)" |
| 5 | "xem bảng lương tháng 6" / "bảng lương tháng 6 đang ở đâu?" | run card, tiles "người", "thực nhận", "trạng thái"; money "₫…" with dots / "tỷ" |
| 6 | "tải Excel tháng 6" (an approved month) | "Đây là tệp Excel của …" |
| 7 | "Cho Linh phụ cấp 500.000 từ tháng 7" (a scheme with no Records values) | ONE "Mở Con người › Hồ sơ" door; "Hiện chưa đổi được gì của <scheme> từ đây…"; chip "Bạn làm được gì?" (W1/W2, also in English) |
| 8 | as an approver with a demo run waiting: "duyệt bảng lương tháng <m> <scheme words>" | rose card "Duyệt …"; hint "Gõ DUYỆT để xác nhận…"; type `duyet` → button lights; `duyệt đi` + Enter → red inline "Chưa đúng từ xác nhận. Hãy gõ DUYỆT."; `APPROVE` also lights |
| 9 | "Mở mục Phê duyệt của tôi thay vào đó" on that card | the Approvals inbox opens WITH that request's drawer open |
| 10 | as somebody not on the route: same sentence | "Việc này không chờ bạn", chip "Nhắc <tên>", "Mở mục Phê duyệt của tôi" opens the request (on "Tất cả tôi xem được") |
| 11 | "trả lại bảng lương tháng <m> vì thiếu tăng ca" (put a demo run back) | plan with Lý do "thiếu tăng ca", word TRẢ LẠI; after it "Đã trả về cho … Đợt lương trở lại dạng nháp." |
| 12 | Learn › Các đợt lương lesson, last step | "Hoặc nhờ PayAI, và đọc kế hoạch trước" on a run card; Phê duyệt lesson, approve step tip mentions DUYỆT |
| 13 | Settings › PayAI được làm | Vietnamese labels and help |
Any "Odoo" or English sentence on a card = fail (run names and scheme/step names are data and stay as typed).

## Open items (carried)
PA28, engine idempotency keys for Records / delivery / filing, PA32, PA40 fixtures, `team` scope for the not-yours
lookup, seat-holder live walk (typed word), settings card for payroll managers (P1 scope question), the two Vietnamese
words for "scheme" in the product (PA53), browser walk of the typed component and the deep link.
