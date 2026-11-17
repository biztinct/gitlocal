# WDGAP IDB1 — general bank payment list (any bank, any country)

Owner ruling IDB1 + follow-up (2026-11-18): Rize has 126 people paid into Indonesian
banks (BCA, Mandiri …). The bank payment file Payobook produces today knows Vietnamese
banks only (it reads the `vietnam_bank_*` fields), so those people cannot be paid by
file. The owner chose **"a general file for now"**: a plain Excel/CSV payment list
(name, bank, account number, amount) that a finance team can upload or retype into any
bank. A bank-specific Indonesian layout follows later, once the paying bank is known —
**do not invent a BCA/Mandiri layout now.**

Read first: `WDGAP_LEDGER.md`, `WDGAP_WAVE_RULES.md`, `WDGAP_OWNER_RULINGS_2026-11-15.md`
(E-rulings on bank, BK1, BK2, BG1–BG4, IDB1), `WDGAP_S6A_REPORT.md` (two bank stores,
approval path), `WDGAP_W3C_REPORT.md` (bank-gap findings, "bank not known to the bank
file"), all on `origin/19.1` / `origin/wdgap-w3c`. Plumbing is NOT pre-verified in this
handover (it would be longer than the diff): the owning code is `pb_pay_delivery` (bank
file from a pay run; "Pay & deliver"), `pb_bank_ocr/models/pb_bank_two_stores.py` (the
two stores: `res.partner.bank` and `vietnam_bank_*`), `pb_payruns`. Verify there and
record file:line facts in your report.

## Scope

1. On the pay run's Pay & deliver step, beside the existing bank file, a second
   download: **"Payment list (any bank)"** — `.xlsx` and `.csv`. One row per payslip in
   the run that is paid by bank transfer: employee number, employee name, account
   holder name, bank name, branch (if recorded), account number, amount (take-home,
   read from `pb_pay_totals` — the one-pay-band rule; never a rule category), currency,
   payment reference (run name + period), and a "Check" column in plain words when
   something is off (no account on record; account holder name differs from the
   employee; account shared with another person in this run; bank change waiting for
   approval; amount zero or negative).
2. Source of the account: the APPROVED account on record (`res.partner.bank` on the
   employee's own bank link), independent of the Vietnamese-only fields, so it works
   for Indonesia and every other country. A change still waiting for approval is NEVER
   used — the row uses the last approved account and says so in "Check".
3. Totals row per currency (never add two currencies together); count of rows; count
   of rows with a "Check" note. The existing Vietnamese bank file is unchanged, byte
   for byte (golden test). People the Vietnamese file leaves out for an unknown bank
   are no longer a dead end: its skipped-people message points to the payment list.
4. Screen: a quiet summary beside the button — "N people, total X IDR · M need a
   check" — and the download. Access: exactly who can download the existing bank file
   today; nobody else. Every download is logged the same way the existing file is (if
   it is logged; if not, add a chatter line on the run: who, when, row count — no
   account numbers in the log).
5. Excel safety: account numbers written as TEXT (leading zeros kept, no scientific
   notation); any cell starting with `=`, `+`, `-`, `@` in a text field is escaped.

## Non-goals (binding)

No bank-specific layout; no bank codes table; no change to how the two stores are
written or approved; no change to the Vietnamese file; no payment status tracking; no
edits to `pb_lifecycle/`, `pb_pack_*`, `pb_me_portal`, `pb_explorer`. No new module
unless the code genuinely cannot live in `pb_pay_delivery` (say why).

## Rules

White-label: the word "Odoo" must never appear in anything an end user can see (UI,
file contents, file names, sheet names). "Payobook" must not appear in generic `biz_*`
modules. vi/id PO entries for every new string (PO gate). Design mandate + quiet-board
pattern per the ledger; Lucide icons, no emoji. No credentials or test passwords in any
file, commit or message; never commit `outputs/`, `SUDIMA/`, `RIZE/`; explicit-path
staging; no `git stash`; no force-push. Build in your worktree on branch `wdgap-idb1`
from `origin/19.1`; own database `wdgap_idb1_t`, own port; drop it after. Long jobs:
ONE command with a bounded poll that checks the process is alive; never end a turn on
"waiting". Do NOT deploy and do NOT touch the live server. Commit trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Tests (numbered; all must pass, plus the touched modules' suites = baseline)

1. Run with VN + ID employees → list has every bank-paid payslip once; amounts equal
   each payslip's take-home; per-currency totals correct; two currencies never summed.
2. Indonesian employee with an approved account and empty `vietnam_bank_*` → present,
   no "Check".
3. No account → row present, account cells empty, "Check" says so.
4. Holder name ≠ employee name → "Check"; same account for two people → both flagged.
5. Bank change waiting → old approved account used + "Check"; after approval → new.
6. Leading-zero account survives xlsx and csv; formula-injection text escaped.
7. Vietnamese bank file for the same run byte-identical before/after (golden).
8. Access: a user without the existing bank-file right is refused (screen + direct
   URL); portal user refused.
9. Download logged without account numbers.
10. vi/id strings load; grep proves no "Odoo" in any user-visible string or file output.
11. Browser smoke on the local copy (desktop + phone width), console clean.

## Report — `docs/handovers/wdgap/WDGAP_IDB1_REPORT.md` on `wdgap-idb1` (commit + push)

Verified plumbing facts (file:line); what was built; test results vs baseline; version
raises; deploy notes (modules to `-u`; pay-reading → rize rehearsal old-vs-new; a
read-only count per live database of bank-paid people the Vietnamese file skips);
gotchas → ledger; owner questions as plain real-world questions. Final message under
200 words, plain English, screen words only.
