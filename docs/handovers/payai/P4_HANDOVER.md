# PAYAI P4 — Vietnamese + close-out (handover for Opus)

Read first: `PAYAI_PROGRAM.md`, `PAYAI_LEDGER.md` (PA1–PA50, binding rules PA-R1…R5, PA41 version rule, PA38 stage from
`git archive`), `P3_REPORT.md` (open items), `P1/P2/P3_HANDOVER.md` for the code you translate. Owner decision 5:
English first, **Vietnamese in the last phase** — this is it. Payobook's demo world and real tenants are Vietnamese.

## Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." In Vietnamese too: a Vietnamese payroll
officer should feel the cards were written for them, not translated. Plain words, the screen's own Vietnamese
vocabulary (read pb_payruns / pb_approval_config / pb_records vi_VN.po for the established terms — "kỳ lương",
"bảng lương", "phê duyệt", "trả lại", "từ chối", etc.; reuse, never invent a second term). Never "Odoo".

## P3 live walk (Fable, payobook, 2026-10-12) — fix first (P4-W1, W2)
Live: pb_payai_actions 19.0.3.0.0. Walked via the chat RPCs with the QA login: not-yours approve/reject → "This is not
waiting for you", names the seat holder + step, "Remind <first name>" chip ✓; "Approve it" with nothing waiting ✓;
W1 one-person run plan "Vũ Khánh Chi (1 of 902)" ✓ + cancel ✓; W2 "…already has a run for October 2026" ✓; W4 no
December run ✓. NOT walked live: the seat-holder typed-word path (the QA login holds no seat; the demo routes seat the
shared Demo User — Fable does not sign in as it). Covered by P3 tests 1/3/5/9 on the clone.
- **P4-W1** Duplicate door: the pay-value refusal ("This person's scheme has no pay value that can be changed here")
  renders "Open People › Records" TWICE (W3's door + the missing-card door). One door only; test it.
- **P4-W2** That refusal is right on the data (Retail End-Month has no Records Desk groups for the QA login) — but say
  why in plain words: "Nothing on <scheme> can be changed from here yet." and offer "What can you do?".

## Scope (P4)
1. **Vietnamese for every user-visible string** added by PAYAI P0–P3: pb_payai_actions (cards, notes, titles,
   settings card + field strings/help, tools prompt is NOT user-visible — leave English), pb_payrun_wizard P0/P2
   strings (protected-payroll message, period refusals, plan_preview notes, prefill), biz_approval_workflow (none
   user-visible), pb_payroll_ai_insights P0/P1 strings, pb_hub "Ask PayAI to…", pb_audit PayAI source label + chips,
   pb_learn banner (already VI — check), om_hr_payroll email-all refusal. Follow `po-translation-loading-rules`
   EXACTLY (memory): every entry `#. module:` first, then `#. odoo-python`/`#. odoo-javascript`, then
   `#: code:addons/<module>/<path>:0`; check the `.pot` too. Run the PO parse gate (PoFileReader over every touched
   .po and .pot) locally AND on the clone before finishing. Also make PA11's three failing tests green IF the fix is
   adding the missing vi_VN entries those tests ask for (check what they assert; fix only by adding translations).
2. **Vietnamese phrasings + confirm words**: the phrase table and resolvers understand VI sentences for every
   Action ("chạy lương tháng 6 cho Bán lẻ", "gửi duyệt bảng lương tháng 8", "duyệt bảng lương tháng 6 Bán lẻ",
   "trả lại … vì …", "từ chối … vì …", "mở bảng lương", "tải Excel tháng 6", "gửi phiếu lương tháng 6", "đổi phụ cấp
   ăn trưa của <tên> thành 500.000 từ tháng 11"); VI month names and number formats (500.000 = five hundred
   thousand); confirm words accept EN and VI: APPROVE/DUYỆT, SEND BACK/TRẢ LẠI, REJECT/TỪ CHỐI (fold diacritics
   and case — "duyet" counts); the hint shows the word in the person's language. Cards render in the user's lang
   (the runner already sets lang — verify with a vi_VN user in tests).
3. **Approvals deep link**: `pb_focus` support in the inbox (`pb_approval_config/static/src/js/inbox.js`) so "Open my
   approvals instead" / "Open it" open the one request; the Red/not-yours cards pass the request id. Bump
   pb_approval_config in the ship commit only.
4. **Learn**: a short lesson or scenario "Ask PayAI to do it" (EN+VI) in pb_learn's content (docs/tutorial_poc/author/
   data.js is the SOURCE, pb_learn/static/content/learn_content.json is GENERATED — edit both, memory
   run-screen-scheme-field), covering plan card → Do it → undo, and the typed word for approvers; the "Learn to do
   this yourself" button on Red pay-run cards may keep `sc_payslips`. ⚠ Another session edits pb_learn in this tree:
   commit ONLY your hunks (git add -p is not available non-interactively — use a patch file and `git apply --cached`).
5. **Close-out**: `docs/handovers/payai/PAYAI_CLOSEOUT.md` — what PayAI can do now (by tier, plain English), every
   owner decision, what is live where (payobook only for pb_payai_actions; the tier switches; tenants off), the
   carried debts (PA28, engine idempotency keys, PA32, PA40, team scope, seat-holder live walk), the ledger summary,
   and a one-page "how to add a new Action" for future engineers (registry, gate, resolvers, cards, tests).
6. Tests + clone run + report (`P4_REPORT.md`) as before, with a VI test user (lang vi_VN installed on the clone?
   check `res.lang`; activate it in the test if missing).

## Binding non-goals
No new Actions. No changes to tiers, gates or the approval engine. No tenant installs. Deploys are Fable's.

## Rules (repeat)
PA41: bump versions ONLY in the ship commit. PA38: stage the clone from `git archive HEAD`, never the working tree.
PA37: check the clone/port is free with `pgrep -af odoo-bin | grep -v pgrep | grep p0clone` and `ss -ltn | grep 8099`.
PA35: every module whose tests you need goes in BOTH `-u` and `--test-tags`. Ignore PA40 (20 pb_payrun_wizard
fixed-2026 tests) while the "Walk Sales" runs sit on p0clone — say the count. Never touch pb_dashboard, pb_home_hub,
docs/deploy/PENDING.md, or another session's pb_learn hunks.

## Numbered tests (P4)
1. Every new/changed vi_VN.po and .pot parses with PoFileReader (gate) and every entry has module + odoo-python/
   javascript + code occurrence (scan).
2. A vi_VN user: "chạy lương tháng 12 năm 2031 cho <test scheme>" → plan card in Vietnamese (title, slot labels,
   notes, buttons) with Period "1 đến 31 tháng 12 năm 2031" (or the established VI date phrasing).
3. VI confirm words: DUYỆT, "duyet", "Duyệt" all accepted for approve; "TRẢ LẠI" for send back; EN words still
   accepted for a VI user; a wrong word gives the VI inline hint.
4. VI phrasings for every Action resolve to the right action key (table-driven test).
5. 500.000 parses as 500000 in a VI sentence; "1.500.000,5" → 1500000.5; EN "500,000" still 500000.
6. Deep link: the not-yours card's door carries the request id; the inbox opens that request (JS: assert the action
   context; Python: the card's hub action has `pb_focus`).
7. P4-W1 single door; P4-W2 wording.
8. The Learn lesson exists in both languages and its anchors exist on the screens it points at.
9. PA11's three tests green if their failure is missing vi_VN entries (else say why not).
10. No user-visible string anywhere in pb_payai_actions contains "Odoo" (scan py/xml/js/po).
