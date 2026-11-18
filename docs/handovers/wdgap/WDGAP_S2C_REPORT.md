# WDGAP S2-C — report: bank payment files for any country

Branch `wdgap-s2c` from `origin/19.1` @ 116386329. Builder = implementer + tester +
self-reviewer. Nothing deployed; the live server not touched. Handover:
`WDGAP_S2_HANDOVER.md` §S2-C and `WDGAP_S2_FACTS.md` §C (main checkout, untracked — not
copied here; the S2-A builder carries them).

## 1. Verified facts added (file:line on this branch)

| # | Fact | Where |
|---|---|---|
| C1 | The XML loader skips EXISTING records of a `noupdate="1"` file on upgrade (marks the xmlid loaded, so nothing is deleted) — switching `bank_file_layouts.xml` to noupdate needs no data rewrite; the migration only flags `ir_model_data.noupdate` and fills the new country | `~/odoo19/odoo/odoo/tools/convert.py` `_tag_record`; `pb_pay_delivery/migrations/19.0.1.9.0/post-s2c_layouts_noupdate.py` |
| C2 | Every existing `pb.bank.registry.match()` caller (bank-document check ×2, VN bank file, Pay & deliver preview ×2, BG1 scripts) passes no country → still reads only the 40 Vietnamese rows | `pb_bank_ocr/models/pb_bank_change_request.py:383,444`; `pb_pay_delivery/models/bank_export_wizard.py:~275`; `pb_pay_delivery.py:67,175` |
| C3 | `res.partner.bank.clearing_number` (core) is the per-account code slot (an IFSC / SG branch code); `res.bank` has none — added `pb_clearing_code` | `~/odoo19/odoo/odoo/addons/base/models/res_bank.py:91`; `pb_pay_delivery/models/bank_identity.py` |
| C4 | None of the nine named banks publishes a complete upload specification on the open web (each hands its template to its own customers inside online banking) | §4 below |
| C5 | A `_()` inside a NESTED function has no `self`/`env` in its frame: it logs "no translation language detected" and never translates — use `self.env._()` | `pb_pay_delivery/models/payment_list_layout.py` `text_problems` |

## 2. What was built (only `pb_pay_delivery` + the `pb_bank_ocr` registry)

**pb_pay_delivery 19.0.1.8.1 → 19.0.1.9.0**

1. **Layouts for any bank** (`models/bank_file_layout.py`). `pb.bank.file.layout` gains:
   `target` (`bank_file` = the Vietnamese bank file, default for every existing row;
   `payment_list` = made from the payment list's rows), `country_id`, `currency_id`
   ("Pays in"), `company_id` (a company's own copy), `copied_from_id`, header and trailer
   line templates with the words `{count} {total} {date} {company_account} {reference}
   {currency}` (unknown words refused on save), `amount_format` (whole / 2 decimals /
   2 decimals without the point), `date_format`, `line_ending`, `ascii_only` ("Plain
   letters only"), `code_label`, `code_pattern`, `account_pattern`, `inferred` ("Not
   confirmed by the bank"). Columns gain the sources payment date, currency, bank
   SWIFT/BIC, bank code, employee email, payment reference, number of payments, total of
   the file; number formats `dec2` / `implied2`; `max_length` and `required`.
   `pb_copy_for_company()` makes a company copy with its own key `<key>_c<company>_<n>`.
2. **The renderer** (`models/payment_list_layout.py`): payment-list rows
   (`_pb_build_rows`, unchanged) → layout → CSV / fixed-width text / Excel. Account =
   the approved account on record; a waiting bank change is never used (IDB1 rule kept).
   Bank code = account's own `clearing_number` → the bank's `pb_clearing_code` → the bank
   directory by name + the layout's country. One money per file (layout's, else its
   country's, else the run's); people paid in another money are left out with the reason.
   **Left out, never cut or changed**, each with a plain reason: no bank account; no holder
   name; take-home zero or below; take-home shown two ways; another money; a required
   column empty ("Bank code is missing", "IFSC is missing"); a code or account number not in
   the bank's form; a value longer than the bank takes (fixed width or "longest"); letters
   the bank refuses (plain-letters layouts) or the encoding cannot hold; a text cell that
   starts with a formula sign; an amount with cents in a whole-number column. A whole-file
   figure that does not fit (count/total) refuses the file instead of cutting it.
3. **Stored and approved with the list** (`models/payment_list.py`):
   `pb.payment.list.file.prepare(run, layout=None, payment_date=None, company_account=None)`.
   With a layout: a THIRD stored file (own sha256 `layout_hash`; the record's stamp then
   covers all three files), row count, total, money, left-out list (JSON), payment date and
   company account; the general list's Check column says "Not in the <layout> file:
   <reasons>" for each person left out. Without a layout everything is byte-identical to
   before (golden). Same `bankfile` approval, same approved-bytes-only download
   (`fmt='bank'` on the existing address `/pb_pay_delivery/payment_list`), one trail line
   "Bank file (any bank) downloaded · who · layout · N rows · M left out" (no account
   number). The approver's detail shows the layout, the count and total in the bank file,
   and every person left out with the reasons.
4. **Pay & deliver** (payment list card): "Bank layout" chips — "General list only" (default)
   or any payment-list layout this company may use; payment date (defaults to today) and an
   optional company debit account; a live preview "6 people in the <layout> file • total …"
   plus who is left out and why (first 12, "and N more"); a "not confirmed by the bank —
   check with your bank before the first upload" line; after approval a third download
   button "<layout> file". The Vietnamese bank file's chips now list only
   `target = bank_file` layouts (the seven Vietnamese ones as before, plus the company's
   own copies of them).
5. **S2F-1 fixed** (`models/bank_export_wizard.py`, `models/bank_file.py`): the wizard keeps
   its `bank_format` selection; a layout key the selection does not know rides on the new
   `pb_layout_key` (`_pb_wizard_values`). Known keys are passed exactly as before (same
   bytes, same file name — golden). A payment-list layout is refused by the Vietnamese file
   in plain words. A bank file made with a company copy is named after the copy.
6. **S2F-2 fixed**: `data/bank_file_layouts.xml` is `noupdate="1"`; migration 19.0.1.9.0
   flags the module's layout/column xmlids `noupdate`, sets Vietnam on the seven shipped
   layouts, and adds the new fields to the two layout-change trail rules (noupdate,
   IDB1F-1). It changes no layout or column. New shipped layouts:
   `data/bank_layouts_world.xml` (noupdate) — see §4.
7. **Settings › Payroll › Bank layouts** (`models/bank_layout_studio.py`,
   `static/src/{js,xml,scss}/bank_layouts*`, `views/bank_layout_views.xml`): every layout
   grouped by country (shipped + this company's copies), "Make our own copy", an editor
   for copies only (the file, lines before/after, columns with move/remove/add), "Stop
   offering it" / "Offer it again", and for payment-list layouts a preview with three
   made-up DEMO people rendered by the real renderer. Payroll manager (or administrator)
   only — refused on the server for anybody else. Settings card (soft registry, group
   Payroll, seq 33) + one ⌘K row ("Bank layouts", seq 2190).
8. **Security**: global record rules — a copy belongs to its company; shipped layouts are
   everybody's (`security/bank_layout_rules.xml`).
9. `res.bank.pb_clearing_code` ("Bank code") on the bank form beside SWIFT/BIC.
10. Translations: 159 entries appended text-level to `vi_VN.po` and `id_ID.po` (rest of the
    files byte-identical); PO parse gate passes.

**pb_bank_ocr 19.0.1.5.0 → 19.0.1.6.0** (registry only): `pb.bank.registry` gains
`country_id` and `clearing_code` ("Bank code"); `match(raw, country=None)` — no country =
the Vietnamese rows only (unchanged behaviour); new `data/bank_directory_data.xml`
(noupdate): 9 Indonesian, 6 Singaporean, 12 Indian banks with aliases and codes. 5 PO
entries ×2.

Not touched: `pb_lifecycle`, `pb_pack_*`, `pb_me_portal`, `pb_explorer`, `pb_govt_reports`,
`pb_form_lines`, `pb_me_details`, any approval route, either bank store, which account
is paid.

## 3. Tests

Local copy `wdgap_s2c_t` (from `upd_p6_t_tpl`, 44 behind modules `-u` + `pb_retro`),
port 8763.

| Run | Tree | Tests | Failed | Errors |
|---|---|---|---|---|
| Baseline `-u pb_pay_delivery,pb_bank_ocr,pb_approval_config`, tags `/pb_pay_delivery,/pb_bank_ocr,/pb_approval_config` | pristine `git archive origin/19.1` | 284 | 4 | 5 |
| General-list golden stamps recorded (test 2, `S2C_PRINT_GOLDEN=1`) | pristine | 1 | 0 | 0 |
| Final, same tags, on a fresh restore of the upgraded base (so the 19.0.1.9.0 migration ran as a real upgrade: "50 layout/column records kept … 7 shipped layouts given their country") | `wdgap-s2c` | 304 | 4 | 5 |

Failure set final = baseline, exactly (pb_approval_config u10, the look, u13, z06d, z06e;
pb_bank_ocr 07, 07b, 09, 15 — the IDB1-F recorded baselines). 20 new tests, all pass.

| # | Handover test | Where | Result |
|---|---|---|---|
| 1 | Vietnamese bank file byte-identical | `test_wdgap_idb1_vn_golden` (unchanged golden) + 6 below | PASS |
| 2 | General payment list byte-identical (CSV sha256, Excel by parts — IDB1M-3), also after a bank-layout file was made | `test_wdgap_s2c_golden`, `test_s2c_golden_general_list_with_layout_file_made` | PASS |
| 3 | Shipped layouts render: Indonesia on the seeded run (6 in, IDR 16,900,000, codes 014/008 from the directory, leading zeros, approved account only); header/trailer with count/total/date/company account/money; amounts whole / 2 decimals / implied / grouped; count and total columns; fixed width (never cut); India (IFSC form) and Singapore (4/7-digit code); Excel keeps text as text | `test_s2c_3a..3e` | PASS |
| 4 | Left out with reasons (no account, zero, missing code, another money, cents in a whole-number column, accents in a plain-letters layout, account form) and named in the general list's Check column | `test_s2c_4` | PASS |
| 5 | Approval + hash + download + trail for the bank file; refused while waiting and after its bytes changed; approver detail without account numbers; "no approval needed" route; no layout = nothing changes | `test_s2c_5`, `5b`, `5c`, `TestS2cUrl` | PASS |
| 6 | New layout key end to end: a company copy of Vietcombank listed, prepared, same bytes; a payment-list layout refused by the Vietnamese file; a copy of the Indonesian layout prepared with the list | `test_s2c_6` | PASS |
| 7 | Upgrade keeps an edited shipped layout, an edited copy and every row; migration flags noupdate, sets Vietnam, extends trail rules; second run changes nothing | `test_s2c_7` | PASS |
| 8 | Bank by alias per country; Vietnamese match unchanged (BCA unknown, Vietcombank same record); code order account → bank → directory | `test_s2c_8` | PASS |
| 9 | Access: payroll officer / portal refused on the screen, preview and prepare; shipped layout not editable; another company cannot see or use a copy; preview shows only DEMO people | `test_s2c_9`, `TestS2cUrl` | PASS |
| 10 | Formula signs left out (bank name, holder), the run name never starts a formula in the reference, leading zeros and 21-digit accounts exact | `test_s2c_10` | PASS |
| 11 | vi/id entries load for every new string; no vendor word in strings, files, file names or shipped notes | `TestS2cTranslations`, `test_s2c_11` | PASS |
| 12 | Browser walk (local, `s2c.localhost:8763`, DEMO run of 8 people VN + ID, a pay manager walk login, "no approval needed" route on the copy): Pay & deliver still lists the 7 Vietnamese layouts; the payment list card offers General / India / Indonesia / Singapore; Indonesia → "5 people in the … file • total 16,000,000.00 IDR", 3 left out with reasons ("Paid in USD …", "Bank code is missing", "No bank account on record"), the not-confirmed line; prepared → approved → third button downloads 200, file name and header right, amounts 2-decimal, the waiting bank change not used; Settings › Bank layouts: list by country, read-only shipped layout with its source note, preview (3 DEMO people, INR), Make our own copy → edit (trailer line, remove a column) → Save → preview shows the trailer `T,3,13170.50`; phone 390 px (device emulation): no sideways scroll on both screens; console: no errors or warnings | manual | PASS |

Also run: `-u pb_hub,pb_settings` tags `/pb_hub,/pb_settings` (the palette and Settings
registries that the new doors join) — 105 tests, 2 failed, neither about this phase:
`test_every_tab_has_a_row_or_says_why_not` lists four tabs of OTHER modules with no ⌘K row
(hiring staff_moves, home policies, people family / privacy — Step 6 tabs), and
`test_the_kit_stacks_nothing_above_twenty` reads only `pb_hub`'s own files (a z-index 30).
The tests that check the new rows (`test_rows_onto_a_settings_card_carry_its_gate`,
`test_every_tab_row_carries_its_tabs_gate`, the resolver) pass. Not baselined on the
pristine tree (time); flagged for the deployer as pre-existing on `19.1`.

Static gates: `py_compile` of every changed Python file; every changed XML parses; PO
files parse (polib) and were merged text-level (only insertions in the diff); `git diff`
scanned for passwords (none; test logins get a random one-off password at run time).

## 4. Bank layouts — sources, and what was not shipped

Searched 2026-11-18 (WebSearch/WebFetch, public pages only; no customer, employee,
company or owner detail sent anywhere).

| Bank / format | Published specification found? | Shipped |
|---|---|---|
| BCA KlikBCA Bisnis payroll / multi-transfer | No. BCA hands a converter tool + checksum app inside KlikBCA Bisnis; the public guideline URL is gone (404); vendor guides only | No |
| Mandiri MCM / Kopra bulk | No. Kopra pages say "Download Template" inside the portal; format customisable per client | No |
| BNI Direct | No public layout found | No |
| BRI CMS | No. Template inside CMS (Fund Transfer menu) | No |
| HDFC bulk salary (ENet) | No | No |
| ICICI bulk (CIB) | **Partly**: ICICI "File Format for Bulk upload in CIB" v3.3 (https://www.icici.bank.in/content/dam/icicibank/missing-assets/File_Format_Bulk_%20Transfers_3.3.pdf) lists field names and lengths but not the file type, the separator, nor (for the salary-to-other-banks file) the amount field | No (would need invented fields). Its IFSC rule (11 characters, 5th = 0) is used by the India layout |
| DBS IDEAL (UFF) | No. The UFF specification is in the IDEAL Resource Center (customers only) | No |
| OCBC Velocity GIRO | No (vendor guides name the "GIROFASTWITHINV" format only). OCBC's public "ACH Bank and Branch Code Guide" (as at 09 Dec 2011, https://www.ocbc.com/assets/pdf/ach-bank-and-branch-code-guide.pdf) gives the Singapore bank codes used in the directory | No |
| UOB BIBPlus / Infinity | No (UFF / fixed-length files described, layout not published) | No |

Shipped instead (all **INFERRED**, `inferred = True`, note ends "Check with your bank
before the first upload", meant to be COPIED and shaped to the paying bank's template):

| Layout | Columns | Bank code rule |
|---|---|---|
| Indonesia — bank transfer list (general) `id_general` | No, Bank code, Bank, Account number, Account holder, Amount (2 decimals), Currency, Reference | 3 digits (`^[0-9]{3}$`) |
| India — NEFT / RTGS bulk transfer (general) `in_neft_general` | Beneficiary name, Beneficiary account number, IFSC, Amount, Payment date (dd/mm/yyyy), Remarks | IFSC `^[A-Z]{4}0[A-Z0-9]{6}$` (ICICI v3.3) |
| Singapore — GIRO / FAST bulk transfer (general) `sg_giro_general` | Beneficiary name, Bank / branch code, Account number, Amount, Value date (yyyymmdd), Reference | 4 or 7 digits |

Bank directory sources (also in `pb_bank_ocr/data/bank_directory_data.xml`):
Singapore codes from OCBC's 2011 guide (DBS/POSB 7171, OCBC 7339, UOB 7375, HSBC 7232,
Standard Chartered 7144 — a 2011 bank document; one blog gives SCB 7214: check);
Indonesian codes INFERRED from press lists (Bisnis.com 2022, CNN Indonesia 2021, Kompas TV:
BCA 014, Mandiri 008, BNI 009, BRI 002, BTN 200, CIMB Niaga 022, Permata 013, Danamon 011,
BSI 451 — the press also gives 427/422 for BSI's merged banks); Indian rows INFERRED (IFSC
four-letter prefixes; a full IFSC must be on each account).

## 5. INFERRED list

All three shipped payment-list layouts; the 9 Indonesian and 12 Indian directory codes;
the Singapore codes are from a bank's own 2011 document (treat as "check"). The seven
Vietnamese layouts were already INFERRED (Phase F) and are unchanged.

## 6. Decisions the owner may want to change

- **Soft checks stay in the bank file.** A holder name that does not match the employee, two
  people on one account: they are IN the bank file (as in the general list) and flagged in
  the list's Check column. Hard problems (no account, zero take-home, take-home two ways,
  another money, missing/invalid bank code, too long, refused letters) leave the person OUT.
- **One money per file.** A file pays in the layout's money (else its country's); people
  paid in another money are left out with the reason.
- **Payment date defaults to today** on Pay & deliver.
- **Shipped layouts cannot be edited on the screen** — only copies (the data stays
  editable by an administrator, and an upgrade no longer overwrites it).

## 7. Merge-time tasks (out of lane — not done)

- Updates / import: an "IFSC" / "Bank code" column of a pay data file is still classified
  into the SWIFT/BIC lane (`pb_formula_studio/models/pb_formula_studio.py:11828-11829`,
  `pb_hr_payroll_formula/models/column_role_classifier.py:177-182`). To let imports fill the
  new codes, those headers should map to `res.partner.bank.clearing_number` (per account)
  — a `pb_formula_studio` / `pb_hr_payroll_formula` change.
- The bank-document check (`pb_bank_ocr` change requests) still resolves banks against the
  Vietnamese directory only (`match()` without a country): an Indonesian bank document still
  reads "Bank not recognised". Passing the employee's country there is a one-line change in
  `pb_bank_change_request.py:383,444` — deliberately not made (registry-only lane, and it
  changes what the bank check says).

## 8. Deploy notes

- Upgrade order: `-u pb_bank_ocr,pb_pay_delivery` on payobook, payobook_template, p0clone,
  rize, sudima (never abm). Tier: **normal-plus** (new columns/table fields, new record rules,
  a migration that only flags `noupdate` + fills a country + extends two trail rules; no
  payslip, bank store or route touched). Asset purge + restart (JS/SCSS/XML).
- **Silent-install proof** per database after the upgrade (read-only):
  `SELECT count(*) FROM pb_payment_list_file WHERE layout_id IS NOT NULL` = 0;
  `SELECT count(*) FROM pb_bank_file_layout WHERE company_id IS NOT NULL` = 0;
  `SELECT bank_format, target FROM pb_bank_file_layout ORDER BY id` = 7 × bank_file + 3 ×
  payment_list; `SELECT count(*) FROM ir_model_data WHERE module='pb_pay_delivery' AND
  model IN ('pb.bank.file.layout','pb.bank.file.column') AND noupdate IS NOT TRUE` = 0;
  `pb_bank_registry` = 40 (or the database's own count) + 27; nothing in the Approvals inbox;
  no job.
- **rize rehearsal**: Vietnamese bank file bytes before/after for one finished run (all 7
  layouts — MB Bank by parts, IDB1M-3); general payment list CSV before/after for run 2111
  (expect identical); then build the Indonesian general layout once on the copy and read
  the left-out reasons (expect people with no code where the account's bank name is not in
  the directory).
- A database where someone EDITED a shipped Vietnamese layout before this upgrade: the
  edit is kept (no longer rewritten). Before S2-C every upgrade reset it.

## 9. New ledger gotchas (for S2-A to add)

| # | Gotcha |
|---|---|
| S2C-1 | Switching a data file from `noupdate="0"` to `noupdate="1"`: on upgrade the loader SKIPS every record that already exists (it only marks the xmlid loaded), so a NEW field written in that XML (here `country_id`) never reaches an upgraded database — fill it in a post-migration, and flag `ir_model_data.noupdate` there too. |
| S2C-2 | `_()` inside a nested function (a closure in a model method) finds no `self`/`env` in its own frame: it logs "no translation language detected" once per call and returns English. Use `self.env._(...)` there (the exporter still sees it). |
| S2C-3 | A test that pulls `_("…")` out of source with a regex reads only the FIRST piece of an implicit string concatenation (`_("a " "b")`) and reports a missing translation that is really there. Keep every msgid on one line (also PRD-3). |
| S2C-4 | `pb.bank.registry.match()` now reads ONE country: no country = the Vietnamese rows only (the old behaviour). A new caller for another country must pass `country=` or it matches nothing. |
| S2C-5 | The chrome-devtools `evaluate_script(sourcePath=…)` reads files only inside the workspace (the worktree), not the scratchpad. A one-off sign-in script with a walk password had to sit in the worktree for one call (untracked, deleted at once) — never stage it. |
| S2C-6 | A local walk server started with `nohup … -c <conf>` is NOT found by `pkill -f logs/serve.log` (the log path is inside the conf, not on the command line): the next test run died at start with "Address already in use" (S8B-7). Stop it by port (`lsof -iTCP:<port> -sTCP:LISTEN -t`). |
| S2C-7 | `assertRaises((AccessError, UserError))` fails with "issubclass() arg 1 must be a class" in Odoo 19 tests (W2M-2 again): try/except inside a savepoint. |

## 10. Owner questions (plain words)

1. Which bank will Rize pay its Indonesian staff from (BCA, Mandiri, BNI, BRI…)? None of
   these banks publishes its upload file on the internet. If finance downloads the bank's
   own upload template (or sample file) from its online banking and sends it to us, we turn
   the "Indonesia — general" layout into that bank's exact file. Same for India and
   Singapore.
2. When a person's account is in someone else's name, or two people share one account,
   should they be left OUT of a bank's file (today: they stay in, and the payment list
   flags them)?
3. Should the payment date on Pay & deliver default to today, or to the last day of the
   pay period?
