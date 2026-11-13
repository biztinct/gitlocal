# FIX-1 "later" list — triage (GAPS pass, 2026-10-16)

Sources: `FIX1_LATER.json` (58 items: `from_fix1_converge` 43, `from_fix1_final` 7, `safety_later` 8),
the `later` lists of `FIX1_OPEN2.json` (73 rows; 41 repeat FIX1_LATER word for word and are not listed
twice — the 32 that are new are below), `FIX1_OPEN.json` (no `later` list; its six `note` rows are
listed at the end) and the open / later items of `docs/handovers/onechat/OC1–OC4_REPORT.md`.

Classes: **A** likely typed by real users and wrong in a way that matters → fixed; **B** rare, or
already safe (it asks, refuses, needs a tap / the typed word, or is a note with no behaviour);
**C** deliberate behaviour (pinned by a test or ruled on purpose).

Rules held (PA59): narrow fixes only, no new general mechanism; no question becomes a plan, no "how do
I" becomes an action, nothing reaches Settings › Access and delegations, Red / typed-word / voice rules
untouched. Every fix was checked HEAD-vs-tree over the FIX-1 stub corpora (b11 run-payroll corpus
32,504 sentences + slot dicts; vam rep; fr/amb cases + c2; fr/vi iq; z1 registry probe; registry
regress 34,241 sentences) — only the intended sentences moved — and the offline suites
(`test_onechat_oc1.py`, `test_onechat_oc3.py`, `test_gaps_doors.py`) and every node suite stayed green.

Counts: **A 4** (all fixed, by 2 narrow code changes) · **B 69** · **C 22** — 95 items.

## FIX1_LATER.json — from_fix1_converge
| # | Item | Class | What was done / why | Test |
|---|---|---|---|---|
| 1 | amber#0 "Run mid-month payroll for Retail for May" — May dropped, plan showed this month | A | Fixed: a period of only filler / month-phrase words ("mid-month", "monthly", "current", "kỳ này") gives way to the month said in the "for …" part; the scheme question still asks Retail mid / end | test_payai_fix_amber `test_gaps_a_month_after_a_word_that_names_none` |
| 2 | amber#1 "May month", "13th month", "this pay period", "2031", "May of this year", "May 1 to May 31", "the May period" not read | B | Rare phrasings; the card marks the month "default" or the scheme is refused and asked again; nothing runs without a tap | — |
| 3 | amber#2 "Send everyone back from leave their June payslips" goes to the model | C | Pinned on purpose (`test_crit3_a_send_back_with_any_reason_or_none_is_never_a_payslip_send`): an unsure "back" never takes the email shortcut | — |
| 4 | amber#3 "Run Warehouse payroll for end of May": scheme now "missing" not "ambiguous" | B | Better than HEAD; says the scheme was not found and lists them | — |
| 5 | amber#4 pencil edit of Period keeps "May" in the stored scheme words | B | Rare (phrase path + pencil); fails at HEAD too; the card shows every slot before Do it | — |
| 6 | amber#5 past-tense "… who called back" sends go to the model | B | Safe fallback; nothing is sent without the plan card | — |
| 7 | amber#6 two different months in one sentence → first one | B | Contradictory sentence; card shows the month as said | — |
| 8 | amber#7 contradictory corpus sentences still refuse (two schemes, two names) | B | Refusal is the right answer to a contradiction | — |
| 9 | amber#8 Warehouse rule: words before "payroll" move to the scheme | C | Deliberate since the ninth pass (`test_wf4_only_a_scheme_or_a_name_leaves_the_period`); unchanged by this pass | — |
| 10 | amber#9 "Chạy lương cho toàn bộ nhân viên / cho tất cả / nhân viên thử việc" → scheme refused | A | Fixed: a single "for / cho …" part that means nobody left out ("everyone", "all employees / all staff", "the whole team", "toàn bộ nhân viên", "tất cả (nhân viên)", "mọi người", "cả công ty") is no scheme — the scheme question is asked, as for "Run June payroll". Only after no scheme matched those words. "… cho nhân viên thử việc" (a status, not everyone) still lands in the scheme slot and is refused — left as a refusal | test_payai_fix_amber `test_gaps_everyone_is_no_scheme` |
| 11 | amber#10 "tháng 13 cho Bán lẻ" ready at HEAD, refused now | C | Period reading asks for the month rather than guess (cluster D design; see OPEN2 amber#22) | — |
| 12 | amber#11 slot case with two schemes said → refused | B | Same as HEAD; contradictory | — |
| 13 | amber#12 "Run Mai payroll for 2031" keeps the words where said | B | Not a regression vs HEAD; asks for the scheme | — |
| 14 | red-runner#0 pb_audit console labels from the raw English selection | C | Left on purpose until pb_audit is next touched (outside PayAI; one-line `_description_selection` fix noted) | — |
| 15 | red-runner#1 "cancel" typed after a pencil question goes to the lookup | B | Says it could not read it; nothing happens; the card's Cancel works | — |
| 16 | vietnamese#0 "duyệt yêu cầu của Lan à" now a question | C | Deliberate (vi-1 third pass); can only lose a plan card, never start a decision | — |
| 17 | vietnamese#1 "15 tháng sau" read as 15 months ahead | B | Rare and ambiguous; card shows the date | — |
| 18 | vietnamese#2 a past June date with no year is asked | C | P4 crit-3 design: a past date with no year is asked | — |
| 19 | vietnamese#3 lower-case "bạn / thôi / luôn" after "của" dropped from the Approvals search | B | Rare; the search asks when nothing matches | — |
| 20 | vietnamese#4 harness note (scratchpad/d4) | B | Note, no behaviour | — |
| 21 | vietnamese#5 unmarked question ending on "ha" after a whose-word read as an order | B | Rare (no marks + particle); a Red plan needs the typed word | — |
| 22 | vietnamese#6 "Chạy lương cho tháng 5" puts tháng 5 in the scheme slot | B | Checked on the stub: normalise moves it back — May 2026 "you said", scheme asked | — |
| 23 | vietnamese#7 corpus-diff noise from another agent | B | Note | — |
| 24 | vietnamese#8 test_vi4c needs the database | B | Note; runs in the clone stage (run 31) | — |
| 25 | vietnamese#9 verification note | B | Note | — |
| 26 | vietnamese#10 "duyệt bảng lương tháng 6: là gì" → approve_item, reason "là gì" | B | Rare; Red needs the typed word, the reason shows on the card | — |
| 27 | vietnamese#11 "duyệt đi chứ" searches Approvals with "di", "chu" | B | Rare tone; the search finds nothing and asks; same at HEAD | — |
| 28 | vietnamese#12 unmarked "sau / ba thang truoc" read as counts | B | Cannot be told apart without marks | — |
| 29 | vietnamese#13 verification note | B | Note | — |
| 30 | access#0 "show Lan's passport" gets no never card | C | Deliberate (fb20): the employee record has a passport field | — |
| 31 | access#1 bare "thêm Lan vào nhóm" → None | C | Deliberate: "nhóm" alone is as likely a team | — |
| 32 | access#2 "xem bảng lương như Lan" → run status | B | A look as the asker, with the asker's own rights; nothing changes | — |
| 33 | access#3 "chọn Lan làm người duyệt bảng lương tháng 6" → never card | C | Appointing an approver is an access order; refusal kept | — |
| 34 | access#4 database parts of fb19/fb20, fs01–04 | B | Note; clone stage | — |
| 35 | access#5 lower-case names ("see it as lan") get no never card | B | No action writes access; the model cannot either | — |
| 36 | access#6 never_access groups carry extra slot keys | B | Refusal cards ignore slots | — |
| 37 | access#7 "thêm khoản thưởng vào nhóm quản lý lương" → never card | B | A refusal on a rare sentence | — |
| 38 | access#8 test_vi4c database-only | B | Note; clone stage | — |
| 39 | access#9 "view as Acme" → never card | B | Rare; a refusal | — |
| 40 | access#10 "next week Lan will approve for me" not refused | B | News, not an order; nothing can change access | — |
| 41 | access#11 Title Case "View As Lan" not read as a name | C | By design (`_name_like` ignores Title Case) | — |
| 42 | access#12 dotless-i "từ chốı" → None | B | Rare keyboard; nothing happens | — |
| 43 | access#13 tests/__init__ did not import test_payai_fix_access | B | Already fixed (imported, checked) | — |

## FIX1_LATER.json — from_fix1_final
| # | Item | Class | What was done / why | Test |
|---|---|---|---|---|
| 44 | amber#0 corpus note: changes all on the later list | B | Note | — |
| 45 | amber#1 test_wf6 / wf11 need Odoo | B | Note; clone stage | — |
| 46 | vietnamese#0 fixes already in the tree; new test | B | Note | — |
| 47 | vietnamese#1 verification note | B | Note | — |
| 48 | vietnamese#2 "gửi phiếu lương tháng 6 đi chứ" leaves "chu" as a run word | B | Rare tone; no run matches and it says so; nothing is sent | — |
| 49 | access#0 OPEN2 items already fixed by the seventh pass | B | Note (OPEN2 access#14–16 verified them) | — |
| 50 | access#1 database-only access tests | B | Note; clone stage | — |

## FIX1_LATER.json — safety_later
| # | Item | Class | What was done / why | Test |
|---|---|---|---|---|
| 51 | #0 "chạy lương khối 2 tháng trước" | B | Already fixed in that round (`test_final_safety_a_label_with_its_number_stays_in_the_period`) | — |
| 52 | #1 unmarked label in a marked message | B | Already fixed in that round (`test_final_safety_a_label_typed_without_marks_is_still_a_label`) | — |
| 53 | #2 safety check: no other wrong picks | B | Note | — |
| 54 | #3 "send back the June run for approval" → send_back_item | C | Judgement pinned by `test_crit3_a_send_back_mentioning_payslips_is_a_send_back`; needs the typed word | — |
| 55 | #4 "duyệt bảng lương tháng 6: là gì" | B | As #26 | — |
| 56 | #5 Title Case "Giúp" narrows the Approvals search | B | Rare (Title Case Vietnamese); nothing found → asks | — |
| 57 | #6 "Run December payroll" → December 2025; "June '31"; "June and July" | B | Card shows "December 2025 · you said"; an existing run is refused; the others are rare | — |
| 58 | #7 unmarked "lan" before a number read as a count | C | On purpose (Lan is a common name) | — |

## FIX1_OPEN2.json — `later` rows not already above
| # | Item | Class | What was done / why | Test |
|---|---|---|---|---|
| 59 | amber#13 crit-3 repro fixed | B | Note (fixed) | — |
| 60 | amber#14 items 2–4 repros fixed | B | Note (fixed) | — |
| 61 | amber#15 two "back" sends go to the model | C | Accepted trade-off, pinned | — |
| 62 | amber#16 "Gửi phiếu lương tháng 6, lương trả về tài khoản" goes to the model | B | Rare; safe fallback | — |
| 63 | amber#17 unknown scheme word before "payroll" now refuses | C | Matches the Warehouse pin | — |
| 64 | amber#18 contradictory two-scheme VI sentences | B | Refused; contradictory | — |
| 65 | amber#19 "Chạy lương tháng 5 luôn cho Vũ Khánh Chi" silently ready on a scheme | B | Checked on the stub: now people = Vũ Khánh Chi, scheme asked; nothing silent | — |
| 66 | amber#20 "Run monthly payroll for next month" runs this month | A | Fixed (same narrow rule as #1): November 2026 "you said" | test_payai_fix_amber `test_gaps_a_month_after_a_word_that_names_none` |
| 67 | amber#21 "toàn bộ nhân viên", "tất cả", "mọi người", "cả công ty", "the whole team" not read as everyone | A | Fixed for the common shape (the only "for / cho …" part, #10). With a scheme also named ("cho Bán lẻ cho tất cả") the people slot still says it could not find them — a refusal; English "everyone" there keeps its existing reading (every employment status, shown on the card) | test_payai_fix_amber `test_gaps_everyone_is_no_scheme` |
| 68 | amber#22 "lương tháng 13" asks for the month | C | Asks rather than run October (cluster D) | — |
| 69 | amber#23 scratch note (v14) | B | Note | — |
| 70 | red-runner#2 Vietnamese for two task states | B | Already done (`pb_payai_actions/i18n/vi_VN.po`; stored selection needs the module upgrade it already had) | — |
| 71 | red-runner#3 msgid "the word" | B | Already done ("từ xác nhận") | — |
| 72 | red-runner#4 pb_audit labels | C | As #14 | — |
| 73 | red-runner#5 unmarked "Huy di", "Vang a" collisions | B | Very rare; an unmarked message is taken as meant | — |
| 74 | red-runner#6 a reason ending "?" goes to the answers | C | crit-4 design: a question exits the reason flow | — |
| 75 | vietnamese#14 own repros checked | B | Note | — |
| 76 | vietnamese#15 "tháng 10 vừa rồi" in October | B | Ambiguous; card shows the month | — |
| 77 | vietnamese#16 "cho tôi coi bảng lương tháng 6" → None | B | Goes to PayAI's own AI planning call (look tier), which picks the status look; nothing changes | — |
| 78 | vietnamese#17 "cho Minh xem bảng lương tháng 6" → show me the June run | B | A look as the asker; nothing shared with Minh | — |
| 79 | vietnamese#18 "duyệt yêu cầu đang chờ tôi" search words [] | B | No change in effect | — |
| 80 | vietnamese#19 "từ" in ITEM_STOP | B | Half-broken at HEAD; search asks | — |
| 81 | vietnamese#20 "chạy lương cho tháng 6" month into the scheme slot | B | As #22: moved back, June "you said" | — |
| 82 | access#14 tests/__init__ imports | B | Verified fixed | — |
| 83 | access#15 FIX-1b:3 repro | B | Verified fixed | — |
| 84 | access#16 access tables 343 rows | B | Note | — |
| 85 | access#17 "show Lan's passport" | C | As #30 | — |
| 86 | access#18 small new refusals ("remove the backup") | B | Rare; refusals only | — |
| 87 | access#19 unmarked "nhom quyen" | B | Inherent without marks; marked text is right | — |
| 88 | access#20 "xem với tư cách Quản Lý" vs "Kế Toán" | B | Rare; refusal or nothing | — |
| 89 | (OPEN2 amber#0–#12, red-runner#0–#1, vietnamese#0–#13, access#0–#13) | — | Same text as #1–#43; triaged there | — |

## ONECHAT reports — open / later items
| # | Item | Class | What was done / why | Test |
|---|---|---|---|---|
| 90 | OC1 §10 OC2/OC3/OC4 to-dos | B | Done by OC2–OC4 (reports) | — |
| 91 | OC2 later: OC43 `live_state.js` resume key reads `session_info` | B | A lost practice resume only; client fix noted in the ledger for a later phase | — |
| 92 | OC2 later: drop the `pb_helper_tabs/ask` shim next release | C | Scheduled on purpose for the next release | — |
| 93 | OC3/OC4: say the month as "June, month 6" in plan read-backs (OC54) | C | PayAI-program wording item; Q6 already makes named people / amounts need a tap | — |
| 94 | OC4: `pb_website` "hold to speak" mock-up (OC66) | B | Already resolved (OC72) | — |
| 95 | OC4: `helper-composer` anchor stays reserved | C | Deliberate (LW plays on the replica) | — |
| 96 | OC26 / OC64 guide content gaps ("how many payslips should there be") | C | Deliberate: a wrong guide answer is worse than PayAI's question path | — |

## FIX1_OPEN.json — notes (no `later` list; listed for completeness, not counted)
- pb_approval_config `.pot` block — done (the three msgids are in the `.pot`).
- Learn Vietnamese "Thu hồi" alignment — done (learn_content.json says "Thu hồi").
- "Pay Runs" → "Các đợt lương" stored action names — GAPS 4a: the `.po` is right; the four databases
  still store "kỳ lương" (see the GAPS report for the deploy step).
- runner "the word" fallback — done (#71).
- pb_payruns `.po`: 8 entries with no `#:` line never load (submit / split / delete refusals stay
  English) — pre-existing, outside this pass.
