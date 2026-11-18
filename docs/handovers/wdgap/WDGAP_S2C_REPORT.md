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

- **Soft checks stay in the bank file** — except an account in another person's name, which
  ruling BL1 leaves OUT (see "Follow-up BL1"). A close-but-not-same holder name and two
  people on one account are IN the bank file and flagged in the list's Check column. Hard problems (no account, zero take-home, take-home two ways,
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
2. ~~Accounts in someone else's name in a bank's file~~ — ANSWERED by ruling BL1, see
   "Follow-up BL1" below. Still open: two people sharing one account stay in the file
   (flagged on the list) — should they be left out too?
3. Should the payment date on Pay & deliver default to today, or to the last day of the
   pay period?

## Follow-up BL1 (owner ruling 2026-11-18 ~15:25) — same branch

**BL1 — an account in someone else's name is LEFT OUT of a bank-specific file** (the
shipped ID/IN/SG layouts and any copy of them), with the reason "Account is in another
name" on Pay & deliver and in the general payment list's Check column; finance pays that
person by hand. The general payment list still lists everyone (IDB3), byte for byte; the
Vietnamese bank file is untouched.

What changed (`pb_pay_delivery` only, still 19.0.1.9.0 — never released):
- **One name test.** The general list's own check is now a method,
  `pb.payment.list._pb_name_band(holder, employee_name)` → `'other'` (under 60, "The
  account is in another person's name"), `'close'` (60 to under 85), `''` — the same
  `name_similarity` and the same two bands as before, so the list's bytes are unchanged
  (golden). Each list row carries its `name_band`; the layout renderer leaves out a row
  whose band is `'other'` with "Account is in another name". No new matching logic.
- **Close names stay in.** A holder name close to, but not the same as, the employee's
  (band `'close'`, e.g. a shortened name) is not "another name": it stays in the bank file
  and stays flagged on the list, as before. (Owner question below.)
- **Counted apart, never silently.** The Pay & deliver preview now says, under "N people are
  left out of this bank file", what they are owed per money: "4 people · 5,800,000.00 IDR to
  pay another way" (never two moneys added); the approver's detail gets a chip per money
  "Left out of the bank file: N people · total". In the people-left-out list each person keeps
  their reasons.

**"Not confirmed by the bank — check with your bank before the first upload" cannot be
removed** — this did NOT fully hold before (a manager could edit a shipped layout's note
through the data, and a copy's note freely); now enforced:
- the three shipped general layouts: the note must keep the sentence, `inferred` cannot be
  switched off and they can never be marked confirmed (constraint
  `_check_not_confirmed_note`, any write path);
- a company's copy keeps the sentence until somebody ticks **"Confirmed with our bank"**
  (Settings › Bank layouts, on the copy) — `bank_confirmed`, `bank_confirmed_by`,
  `bank_confirmed_on` kept; ticking turns the copy's "Not confirmed" marks off; unticking puts
  the sentence back and clears who/when. The tick is on the platform trail (migration
  19.0.1.9.0 adds `inferred`, `bank_confirmed`, `note` to the layout-change rule).
- Test: `test_s2c_bl2_not_confirmed_note_stays`.

Tests added: `test_s2c_bl1_account_in_another_name_left_out` (Dewi — account in "Joko
Widodo"'s name — left out with exactly that reason; Fitri — close name — in; for every person
of the run "another person's name" on the list ⇔ left out of the file; a copy behaves the
same; the general list still shows her account and both sentences in Check; preview counts
4 IDR people left out with IDR 5,800,000 and everybody is either in the file or counted
out; no account number in the preview), `test_s2c_bl1_general_list_unchanged` (CSV and
Excel golden), `test_s2c_bl2_not_confirmed_note_stays`. Earlier expectations updated for
Dewi now being left out (Indonesian file: 5 people, IDR 14,900,000).

Results (fresh `wdgap_s2c_t` from the template, behind modules + this branch upgraded):

| Run | Tests | Failed | Errors |
|---|---|---|---|
| `-u pb_bank_ocr,pb_pay_delivery,pb_approval_config`, tags `/pb_pay_delivery,/pb_bank_ocr,/pb_approval_config` | 307 | 4 | 7 — the 9 recorded baselines + 2 new tests hitting one ordering slip in the screen's detail (`can_confirm` read before `editable`), fixed |
| after the fix, tags `wdgap_s2c,wdgap_idb1` (every S2-C and IDB1 test, incl. both goldens) | 52 | 0 | 0 |

Touched suites therefore = baseline (the 9 recorded failures, nothing else).

Browser (local `s2cb.localhost:8763`, DEMO run, own login, no approval needed on the copy):
Pay & deliver › Indonesia layout → "4 people in the … file • total 14,000,000.00 IDR",
"4 people are left out of this bank file", "2 people · 5,000,000.00 IDR to pay another way •
2 people · 27,500,000.00 USD to pay another way", "DEMO Dewi Lestari — Account is in another
name"; Settings › Bank layouts: a shipped layout shows no tick; its copy shows "Confirmed
with our bank", ticking it reads "Confirmed with our bank by DEMO Walk Manager on
2026-11-18" and the "Not confirmed" banner and chip go; console clean.

New strings: 12 vi + 12 id entries (text-level), "Left out of the bank file" given its code
occurrence.

Owner question (plain words): a bank account whose holder name is CLOSE to the person's
(for example a shortened name, "Fitri Handaya" for "Fitri Handayani") is still put in the
bank's file and flagged on the list. Should those be left out too, like accounts in another
person's name?

## Follow-up BL4 (owner ruling 2026-11-18 ~18:30) — same branch

**1. Company setting — Settings › Payroll › Bank layouts › "Accounts in another person's
name":** "Leave out of the bank file" (default = BL1) or "Pay by file".
- `res.company.pb_other_name_policy` (selection, default `leave_out`); changed only through
  `pb.bank.layout.studio.set_other_name_policy` (payroll manager or administrator — the
  screen's own gate), for the company the person is working in; each change writes ONE trail
  line on the company (`biz.audit.entry`, field `pb_other_name_policy`, old → new label, who,
  when); the same value again writes nothing.
- Read when a file is PREPARED, per payslip's company (`_pb_layout_rows` →
  `other_name_policy`): "Pay by file" puts the person in the bank-layout file; the payment
  list still says "The account is in another person's name"; Pay & deliver shows "1 person
  paid into another person's account · 2,000,000.00 IDR" per money (never added across
  moneys); the approver's detail gets a chip "Paid into another person's account" per money
  (stored with the file, `layout_other_name_json`, names and amounts only). A file already
  prepared or approved keeps its bytes — flipping the setting changes the NEXT prepare only.
- Only the payment-list layouts read it. The Vietnamese bank file and the general payment
  list are byte-identical under both settings (test 3). Close names unchanged (BL3: in,
  flagged).

**2. Flag on the employee** (`models/other_name.py`, `hr.employee`):
- Non-stored `pb_other_name_show` / `pb_other_name_holder` computed when read; the test is
  the payment list's own (`pb.payment.list._pb_name_band` → `'other'`) on the APPROVED
  account (`bank_account_ids[:1]`) — a change waiting for approval is not judged.
- "Mark as seen" (`action_pb_other_name_seen`, RPC `pb_other_name_mark_seen`) keeps
  `pb_other_name_seen_by` / `_on` and a stamp `pb_other_name_seen_key` = sha256 of (account
  id, account number, holder name) — never the number itself — plus one trail line "Marked as
  seen by …. Payment is not changed by this." The notice returns when the account number,
  the holder name or the approved account changes (the stamp no longer matches).
- Who: HR and the payroll team (`hr.group_hr_user`, `om_hr_payroll.group_hr_payroll_user`,
  administrators): every field carries those groups and both methods refuse anybody else
  (employee, line manager, portal) — screen and RPC.
- Where: the employee FORM, under the bank details (view inheritance after pb_bank_ocr's
  "To change where this person is paid…" note): "This bank account is in another person's
  name: <holder>", a "Mark as seen" button, and the help line "Marking it as seen only hides
  this notice. Whether this person is paid by bank file is decided by the company setting on
  Settings › Payroll › Bank layouts." The form button is a native button (text only — the
  native form has no Lucide icon slot).
- Side panel: registered into the panel's existing chip seam `pb_employee_360_chips` (BY
  NAME — no dependency, no edit of `pb_employee_vault` or `pb_people`): an amber chip with
  Lucide `user-x`, the same sentence, and a "Mark as seen" button with Lucide `eye`; shown
  only when the server says so (HR/payroll), nothing rendered otherwise. It sits in the
  panel's HEADER chip row (the seam that exists); the panel has no hook inside its bank
  section — merge-time note if the bank section should carry it instead.
- Install is silent: three nullable columns on `hr_employee` (no default, nothing written),
  one column with default `leave_out` on `res_company`; nobody marked; no trail line.

Not touched: `pb_people`, `pb_employee_vault`, `pb_me_portal`, `pb_me_tax`, `pb_lifecycle/`.

Tests (class `TestS2cBl4OtherName`, tag `wdgap_s2c`):

| # | Test | Result |
|---|---|---|
| 1 | `test_bl4_1_default_leaves_out` — default "Leave out": Dewi out with "Account is in another name", nobody counted as paid into another account | PASS |
| 2 | `test_bl4_2_pay_by_file` — "Pay by file": Dewi IN the file (6 people), close name Fitri still in (BL3), still flagged on the payment list, preview and approver count "1 · IDR 2,000,000" apart, no account number in either | PASS |
| 3 | `test_bl4_3_goldens_under_both_settings` — general list CSV + Excel = golden and Vietnamese bank file bytes (3 layouts) unchanged under leave out → pay → leave out, both companies | PASS |
| 4 | `test_bl4_4_manager_only_logged_and_files_kept` — payroll officer / portal refused; one trail line old → new by the manager (none for the same value); an approved file downloads the same bytes after the flip; the next prepare follows the new setting | PASS |
| 5 | `test_bl4_5_employee_notice` — shown for Dewi (holder "Joko Widodo"), not for own / close names / no account; equals the list's own test for every person; Mark as seen hides it, keeps who/when, one trail line with no number, stamp is not the number; payment unchanged; returns on holder change, number change and a new approved account | PASS |
| 5b | `test_bl4_5b_not_for_anybody_else` — plain internal user (line manager) and portal: state / mark seen / reading the fields refused; the employee form shows the notice to HR/payroll | PASS |
| 6 | `test_bl4_6_silent_install` — no employee row marked, every company on "Leave out", no trail line, the flag not stored | PASS |
| 11 | `test_s2c_11_vi_and_id_entries_load` / `…_no_vendor_name…` — 19 new vi + 19 id entries (incl. the form's `<span>` text) | PASS |

| Run | Tests | Failed | Errors |
|---|---|---|---|
| fresh `wdgap_s2c_t`, `-u pb_bank_ocr,pb_pay_delivery,pb_approval_config`, their three suites | 314 | 5 | 5 — the 9 recorded baselines + the translation test missing the form's `<span>` text (fixed) |
| after the fix, tags `wdgap_s2c,wdgap_idb1` (all S2-C + IDB1 incl. both goldens) | 59 | 0 | 0 |
| after moving the form notice under the bank row (view only), same tags, on a CLEAN rebuilt copy | 59 | 0 | 0 |

(A first rerun on the walk copy failed 11 tests: the walk seed had COMMITTED a "no approval
needed" route, a policy flip and a "seen" mark into that copy — ledger S8D-6 again; the clean
copy is the result that counts. New gotcha S2C-8: never run suites on a copy a browser walk
seeded; rebuild or restore first.)

Browser (local, DEMO run, walk login given the payroll-base + HR officer groups on the copy):
Settings › Bank layouts shows "Accounts in another person's name" with "Leave out of the bank
file" / "Pay by file"; pressing "Pay by file" saved and wrote the trail line; Pay & deliver ›
Indonesia: "5 people in the … file • total 16,000,000.00 IDR" + "1 person paid into another
person's account · 2,000,000.00 IDR" and 3 left out with reasons; the employee form (Personal
tab, under the bank accounts) shows "This bank account is in another person's name: Joko
Widodo", "Mark as seen" and the help line; pressing it hid the notice and kept who/when + the
trail line; phone 390 px: no sideways scroll; console clean. The side panel chip could not be
walked here (the local copy opens the native form, not the side panel) — covered by the RPC
tests; worth one look on the go-live walk.
