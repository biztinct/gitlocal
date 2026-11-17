# WDGAP IDB1 — report: general bank payment list (any bank, any country)

Branch `wdgap-idb1` from `origin/19.1` @ 65fc59cd7. Builder = implementer + tester. Nothing
deployed, the live server not touched. Handover: `WDGAP_IDB1_HANDOVER.md` (copied beside this
report).

## 1. Verified plumbing facts (file:line on `origin/19.1` @ 65fc59cd7)

| # | Fact | Where |
|---|---|---|
| F1 | The Vietnamese bank file reads ONLY the four `vietnam_bank_*` fields and refuses a bank its registry does not know ("unknown bank") | `pb_pay_delivery/models/bank_export_wizard.py:106` `_row_sources`, reason at `:129` |
| F2 | The bank file's amount is the payslip's take-home LINE (`pb_net_line`), also used for the run's money split | `bank_export_wizard.py:74` `_slip_net`; `pay_hold.py:92` `_pb_net_amount` |
| F3 | The one pay-band reading: `hr.payslip.pb_pay_totals()` → `line_ids.pb_pay_totals()`; NET band = every line with pay role `net` (or category NET when unclassified); `pb_payruns` overrides it per payslip | `om_hr_payroll/models/pay_bands.py:91`, `:195`; `pb_payruns/models/payslip_money.py:21` |
| F4 | "The employee's account" everywhere = `hr.employee.bank_account_ids[:1]` (`res.partner.bank`), kept first by `put_first` | `pb_bank_ocr/models/pb_bank_two_stores.py:155-170` |
| F5 | `bank_account_ids` is an HR-only field in Odoo 19 core (`groups="hr.group_hr_user"`) | `~/odoo19/odoo/addons/hr/models/hr_employee.py:137` |
| F6 | Since S6-A/BK1/BK2 nothing is written to either bank store before a second person approves; a waiting change lives on `pb.bank.change.request` (`hr_review` / `finance_review`; import drafts "for HR to look at" = `draft` + `pb_origin='import'`) | `pb_bank_ocr/models/pb_bank_import_hold.py:44` (`OPEN_STATES`), `:97` |
| F7 | Updates sheet / Records bank changes wait as `pb.records.apply` (`state='pending'`, `touches_bank`, people in `plan_json` rows `emp_id`, bank cards `field_id` `b:*`) | `pb_records/models/records_approval.py:155-186`; `pb_records/models/pb_records_desk.py:1906` |
| F8 | Who may download the bank file: administrator, payroll manager or a finance role (`PAY_GROUPS`), checked by `_require_access` on every cockpit method | `pb_pay_delivery/models/approval_common.py:33`; `pb_pay_delivery/models/pb_pay_delivery.py:33`, `:507` |
| F9 | A bank-file download is logged as one platform trail line (`biz.audit.entry`) through `pb.money.approval.mixin.audit` | `pb_pay_delivery/models/bank_file.py:632`; `approval_common.py` `audit` |
| F10 | A bank-file copy batch (W3-C BG1) proposes the SAME account into the bank-file fields as a waiting `pb.bank.change.request` | `docs/handovers/wdgap/w3c_bg1/bg1_batch.py:184` |
| F11 | `pb_pay_delivery` had no controller and no `id_ID.po` | — |

## 2. What was built (all in `pb_pay_delivery`, 19.0.1.6.0 → 19.0.1.7.0; no new module)

1. **Payment list (any bank)** — new `pb_pay_delivery/models/payment_list.py`
   (`pb.payment.list`, abstract):
   - Rows: every finished payslip of the run that is still to be paid by bank transfer (not on
     hold, not paid another way, not already paid by a released bank file — the same people a
     new bank file would take). Columns: Employee number, Employee name, Account holder,
     Bank, Branch, Account number, Amount, Currency, Payment reference, **In the bank file**,
     Check.
   - Account = the approved account on record (`bank_account_ids[:1]`, F4), read under sudo
     after the door (F5). Branch only when the bank-file fields hold the same account.
   - Amount = `pb_pay_totals()['net']` (F3), rounded in the payslip's money.
   - Check (plain words, several joined with "; "): no bank account on record; no holder name;
     account in another person's name (name match under 60) or close-but-not-same (60–85, the
     bank-document check's bands); same account as another person in this list (both rows);
     a bank change waiting for approval (the row keeps the last approved account); take-home
     zero or below; **take-home shown two ways** (band reading ≠ take-home line, F2/F3).
   - A waiting change that proposes the very same account (the BG1 copy batches, F10) is not a
     change and gives no check. Updates/Records proposals (F7) always count as a change.
   - Footer: one total per currency (never two currencies added; a zero/negative take-home adds
     nothing), Rows, Rows with a check.
   - `.xlsx`: every text cell written as text (`num_format '@'`, `strings_to_numbers/formulas`
     off) — leading zeros and all 21 digits kept; amounts are numbers in the money's decimals.
     `.csv`: UTF-8 with byte-order mark, plain-digit amounts. Text starting with `= + - @`, tab
     or CR is prefixed with `'` in both files. Sheet "Payment list"; file name
     "Payment list - <run> - <end date>.xlsx|csv".
2. **Download** — new `pb_pay_delivery/controllers/payment_list.py`,
   `/pb_pay_delivery/payment_list` (auth user, GET/POST). Streamed, never stored (no attachment
   with account numbers left behind). Door = `_require_access` (F8) + record rules on the run +
   run approved; refusal → 403 / 404, never the file. The screen first asks
   `pb.pay.delivery.payment_list_check` so a refusal is a sentence, then downloads.
3. **Log** — each download writes one trail line on the pay run, like the bank file (F9):
   "Payment list (any bank) downloaded · <who> · XLSX · N rows · M need a check". No account
   number.
4. **Screen** (Pay & deliver › Money out): a quiet card under the bank file — "8 people •
   total 27,500,000 USD • total 19,000,000 IDR • 5 need a check" (grey; amber only when a
   check is needed), Excel / CSV buttons (disabled until the run is approved), "Not in the
   list: N on hold, …" when anybody is left out.
5. **The bank file's left-out list is not a dead end**: the drawer says "5 people left out have
   an approved bank account and can be paid from the payment list (any bank) below" (also in
   the "No payable rows" state); the approver's detail and the "No valid rows to export" error
   gain one sentence pointing to the payment list (old sentences and msgids untouched).
6. Translations: 47 entries appended to `vi_VN.po` (text-level, rest byte-identical), new
   `id_ID.po` (header "Payobook 19.0", 52 entries: the new strings + 5 reused ones).

Files edited outside new files: `pb_pay_delivery/__init__.py`, `__manifest__.py`,
`models/__init__.py`, `models/bank_file.py` (one sentence), `models/bank_export_wizard.py` (one
sentence in the "no valid rows" error), `static/src/{js,xml,scss}`, `i18n/vi_VN.po`,
`tests/__init__.py`. Nothing outside `pb_pay_delivery`. Not touched: `pb_lifecycle`,
`pb_pack_*`, `pb_me_portal`, `pb_explorer`, the two bank stores, any approval route.

## 3. Tests

Local copy `wdgap_idb1_t` (from `upd_p6_t_tpl`, 44 behind modules `-u`), port 8631.

| Run | Tree | Tests | Failed | Errors |
|---|---|---|---|---|
| Baseline `/pb_pay_delivery` | pristine `git archive origin/19.1` | 50 | 0 | 0 |
| Golden stamps recorded (test 7 file on the OLD code) | pristine | 1 | 0 | 0 |
| After `/pb_pay_delivery` (final code) | worktree | 68 | 0 | 0 |

New tests (`tests/test_wdgap_idb1_payment_list.py`, `tests/test_wdgap_idb1_vn_golden.py`, tag
`wdgap_idb1`):

| # | Handover test | Result |
|---|---|---|
| 1 | VN + ID run: every bank-paid payslip once, held person absent, amount = band take-home = take-home line, totals per currency (home money + IDR), two totals rows in the file, Rows / Rows with a check | PASS |
| 2 | Indonesian person, approved BCA account, empty Vietnamese fields → present, no check (a waiting copy of the same account is not a change); left out of the Vietnamese file | PASS |
| 3 | No account → row present, account cells empty, "No bank account on record" | PASS |
| 4 | Other person's name; close name; same account (formatted differently) → both flagged | PASS |
| 5 | Waiting change → old approved account + check; after approval (`_apply_to_master` + approved) → new account, no check; 5b waiting Updates/Records bank proposal → check; 5c take-home zero, and take-home shown two ways | PASS |
| 6 | Leading-zero and 21-digit accounts are TEXT in xlsx (read back with openpyxl) and exact in csv; `= + - @` escaped; no formula cell anywhere | PASS |
| 7 | Vietnamese file byte-identical: sha256 of Vietcombank / Generic CSV / VietinBank (txt) / MB Bank (xlsx sheet + strings) recorded on the pre-IDB1 code = the same on IDB1 code; and unchanged after building both payment lists | PASS |
| 8 | Payroll officer and portal user refused: download, check, screen data (AccessError) and the direct address (HTTP 403, no account number, no vendor name); pay manager gets 200 + file; unapproved run and unknown format refused | PASS |
| 9 | One trail line per download, by the downloader, with "10 rows"; no account number (no run of 6+ digits) | PASS |
| 10 | vi + id entries load through `PoFileReader` with the code markers for every new string; no "odoo" in any msgstr, file name, csv bytes, any member of the xlsx, or the new card's text | PASS |
| — | Screen payload: summary carries no account number; "can be paid from the payment list" count | PASS |
| 11 | Browser walk, local copy (`idb1.localhost:8631`, DEMO run, 8 people VN + ID, walk login archived after): card reads "8 people • total 27,500,000 USD • total 19,000,000 IDR • 5 need a check"; left-out drawer hint "5 people left out have an approved bank account…"; download address answers 200 for xlsx (6,687 bytes) and csv (1,441 bytes); both buttons call the check then the download (download stubbed — no file saved); phone 390 px (device emulation): card wraps, no sideways scroll; console clean on both | PASS |

Static gates: `py_compile` of every changed Python file; the XML parses; `git diff` holds no
password, no customer data; test logins get a random one-off password at run time.

## 4. Decisions the owner may want to change (also the questions in §7)

- **No second sign-off on the payment list.** As the handover says, whoever may download the
  bank file may download the list at once; the Vietnamese bank file itself needs a second
  person before download. Every download is logged. (Question 1.)
- **People already in the Vietnamese bank file are listed too** (handover: every bank-paid
  payslip), with "In the bank file: Yes" so nobody is paid twice by mistake.
- People on hold, paid another way, or already paid by a released bank file are NOT in the list
  (same rule as a new bank file); the card says how many.
- A zero or negative take-home stays in the list with a check but adds nothing to the total.
- CSV amounts carry the money's own decimals (IDR has 2 here: "7500000.00").

## 5. Contracts others may rely on

- `env['pb.payment.list'].pb_build(run, 'xlsx'|'csv')` → `(filename, mimetype, bytes, data)`
  (no door, no log); `pb_download(run_id, fmt)` → `(filename, mimetype, bytes)` with door + log;
  `pb_summary(run)` → screen dict; `_pb_build_rows(run)` → `{'rows', 'totals', 'count',
  'check_count', 'left_out'}`.
- `pb.pay.delivery.get_delivery_data` now carries `payment_list` and
  `validation.payment_list_can_pay`; `pb.pay.delivery.payment_list_check(run_id, fmt)`.
- Route `/pb_pay_delivery/payment_list?run_id=&fmt=`.

## 6. Deploy notes

- Tier: **normal** (new screen + download; reads pay, writes nothing but a trail line; no stored
  data rewritten, no payslip figure changes). Upgrade `-u pb_pay_delivery` on payobook,
  payobook_template, p0clone, rize, sudima. Asset purge + restart (JS/SCSS/XML changed).
- Pay-reading rehearsal (rize copy, old vs new): payslips and run totals must be identical
  (nothing here writes them); on one finished-or-approved rize run compare the Vietnamese bank
  file bytes before/after the upgrade (expect identical) and build the payment list once.
- **Read-only count per live database** (owner wants to know who the Vietnamese file skips):
  `odoo-bin shell -c /etc/odoo-server.conf -d <db> --no-http < docs/handovers/wdgap/idb1/count_skipped.py`
  — prints, per company, how many active people the Vietnamese file leaves out for bank details,
  how many of them have an approved account (payable from the list), and by which bank; no names
  or numbers; rolls back. Expected on rize from W3-C: ~126 at Indonesian banks.
- The PO parse gate (memory `po-translation-loading-rules`) covers the two `.po` files.

## 7. Owner questions (plain words)

1. Today the Vietnamese bank file needs a second person to approve it before anyone can
   download it. The new payment list can be downloaded straight away by the same pay team
   members, and each download is recorded. Do you want the payment list to need the same second
   sign-off before it can be downloaded? (Safer; one more step for finance each month.)
2. People who are already in the Vietnamese bank file also appear in the payment list, marked
   "In the bank file: Yes". Would you rather the payment list showed only the people the bank
   file leaves out? (Shorter list; but it would no longer be the whole run.)

## 8. Left for later

- A bank-specific Indonesian layout (BCA/Mandiri…), once the paying bank is known (handover
  non-goal).
- Pre-existing, seen on the walk: Pay & deliver says "Couldn't open this run" when a run holds
  payslips of two companies and only one company is selected in the company switcher
  (`pb_pay_delivery.py` `_validation_preview` reads employee names as the user). Not changed.

## 9. Gotchas → ledger

Rows IDB1-1 … IDB1-5 added to `WDGAP_LEDGER.md`.
