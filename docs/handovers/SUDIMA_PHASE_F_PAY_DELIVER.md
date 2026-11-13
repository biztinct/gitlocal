# SUDIMA Phase F — Pay & Deliver (Real Bank Files + Payslip Distribution)

**Scope items:** #15 Bank Payment Processing (*Partial* — wizard exists, file generation is a stub, VietinBank & ACB missing) + #16 Payslip Distribution (*Partial* — themed PDF + portal exist; auto-email and password-PDF missing). One phase: "the run is approved → the money files and the payslips go out."
**Module:** NEW `pb_pay_delivery` (+ inherit of the existing VN export wizard). Config-driven: bank layouts are DATA records, password patterns are config.
**Ledger:** `docs/FORMULA_ENGINE_CONVENTIONS.md` — **C1, C2, C18 binding** (esp. C18.14 no credentials in data, C18.24/31 sentinel rails, C18.40 `-u`-scoped test runs).
**Prerequisites:** none of F–J; Phase D shipped (bank registry + bank-change approval exist).

---

## 1. Scope

1. **Real per-bank file generation** for the existing wizard's formats (Vietcombank, BIDV, Techcombank, MB, generic CSV) **plus VietinBank and ACB** — layouts as data records, not code.
2. **Batch payslip email** from a payslip run: themed PDF attached, **password-protected**, per-slip delivery log, resend of failures.
3. Close the Phase-D honesty debt: extend `pb_bank_ocr` test_09 to assert the NEW approved account appears **in the generated file content**.

### Binding non-goals
- **NO mobile app** (gap analysis calls it a separate decision) — the portal stays the ESS surface.
- **NO GL/cost-centre journal exports** (that's #17 territory, out of scope).
- **NO redesign of the themed payslip report** — reuse `action_report_payslip_themed` as-is.
- **NO writes to the employee master** — file generation READS `vietnam_bank_*`; the only master-write path remains `pb.bank.change.request._apply_to_master`.
- **NO real SMTP sends from tests** — tests assert on `mail.mail` queue rows; live demo sending is a controlled report-back item (§7).

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **The wizard is a stub**: `vietnam.bank.export.wizard` (`pb_hr_payroll_vietnam/wizards/vietnam_bank_export_wizard.py:6`), fields `payslip_ids` M2M, `bank_format` selection `vietcombank|bidv|techcombank|mb_bank|generic` (:11-17), `action_export_file()` returns a display_notification only (:21-30).
- ✓ **Employee bank master**: four Chars on `hr.employee` — `vietnam_bank_name/branch/account_number/account_name` (`pb_hr_payroll_vietnam/models/hr_employee_vietnam.py:47-50`).
- ✓ **NET amount (formula path)**: `slip.line_ids.filtered(lambda l: (l.code or '').upper() == 'NET')` (`pb_payrun_wizard/models/pb_payrun_wizard.py:267`); category fallback `category_id.code == 'NET'` (`pb_hr_payroll_formula/models/hr_payslip_formula.py:677`).
- ✓ **Run linkage**: `hr.payslip.payslip_run_id` (`om_hr_payroll/models/hr_payslip.py:85`), `hr.payslip.run.slip_ids` (:967).
- ✓ **Download pattern to clone**: `pb_hr_workforce_planning/wizards/export_wizard.py:32-84` — xlsxwriter in-memory → `base64` → Binary field → re-open wizard form (:72-84).
- ✓ **Bank normalization**: `pb.bank.registry` with `match(raw_name)` token-subset lookup + `account_ok` 6–19-digit validator (`pb_bank_ocr/models/vn_bank_dictionary.py:68,93-113`); ~40 banks seeded (`pb_bank_ocr/data/vn_bank_registry_data.xml`).
- ✓ **Export logging precedent**: `bank.export.log` (`payroll_analytics_approval/models/bank_export_log.py:6-36`) — period, totals, format, binary, creator. `payroll_analytics_approval` is OPTIONAL → soft-reference only (`if 'bank.export.log' in self.env`).
- ✓ **Themed payslip PDF**: report action `pb_hr_payroll_formula.action_report_payslip_themed`, model hr.payslip, qweb-pdf (`pb_hr_payroll_formula/report/payslip_themed.xml:7-11`), rendered via `o._themed_payslip_render()` (`hr_payslip_formula.py:565-666`).
- ✓ **Existing mail template**: `om_hr_payroll/data/mail_template.xml:5-28` (`mail_template_payslip`, to `object.employee_id.work_email`), sent by `action_send_email_backend` (`om_hr_payroll/models/hr_payslip.py:272-277`); multi-send `action_send_email_tree` filters state='done' (:280-283).
- ✓ **Debrand is automatic**: `biz_mail_debrand` hooks `mail.mail._prepare_outgoing_body/_prepare_outgoing_list` at SEND time (`biz_mail_debrand/models/mail_mail.py:8-35`) — nothing to do here.
- ✓ **PDF encryption**: live venv has **PyPDF2 2.12.1 with `PdfWriter.encrypt`** (verified on Payobook19v2); pikepdf NOT installed — use `PdfWriter.encrypt(user_password, use_128bit=True)`. Do NOT pip-install anything new.
- ✓ Cockpit/sidebar/theming per Phase A §2; versions: pb_hr_payroll_vietnam 19.0.1.0.0, om_hr_payroll 19.0.1.0.0.

---

## 3. Architecture

### `pb_pay_delivery` (depends: `om_hr_payroll`, `pb_hr_payroll_vietnam`, `pb_hr_payroll_formula`, `pb_bank_ocr`, `pb_import_kit`; NO dependency on `payroll_analytics_approval`)

```
pb_pay_delivery/
├── models/
│   ├── bank_file_layout.py   pb.bank.file.layout + pb.bank.file.column (DATA-driven)
│   ├── bank_export_wizard.py inherit vietnam.bank.export.wizard → real generation
│   ├── payslip_delivery.py   pb.payslip.delivery.batch + pb.payslip.delivery (per-slip log)
│   └── hr_payslip_run.py     "Send Payslips" action + delivery smart-button
├── data/bank_file_layouts.xml   7 layouts (VCB, BIDV, TCB, MB, VietinBank, ACB, generic) noupdate="0"
├── data/mail_template.xml       themed-payslip template (clones om's, attaches encrypted PDF)
├── security/                    ACLs: layouts payroll-manager write; delivery HR read
└── wizards/ + views             pbim-styled wizard + delivery list views
```

**Layouts as data — `pb.bank.file.layout`**: `bank_format` (extends the wizard selection key), `name`, `file_type` (`csv|txt|xlsx`), `delimiter`, `encoding` (default `utf-8`, VN banks often need `utf-8-sig` — per-layout), `with_header` Bool, `column_ids` One2many. **Column**: `sequence`, `header`, `source` selection (`account_number|account_name|bank_name|bank_branch|employee_code|employee_name|net_amount|period|company_account|literal`), `literal_value`, `width` + `pad` (fixed-width txt), `number_format`. The layouts for VietinBank/ACB use the same column vocabulary — adding a bank later is a data file, zero code.

**Wizard inherit** (`vietnam.bank.export.wizard`): `selection_add` `vietinbank`, `acb`; new `payslip_run_id` M2O convenience (fills `payslip_ids` from `slip_ids` filtered `state='done'`); `company_account_number` Char (debit account, from `res.company` field or wizard input). `action_export_file()`:
1. Resolve layout by `bank_format` (error if no layout record).
2. Per slip: employee master `vietnam_bank_*` + NET via the :267 pattern. **Validation pass first**: `account_ok` on every account, non-empty holder, `pb.bank.registry.match` on the bank name — rows that fail go to an `excluded_ids` list with reasons; generation proceeds only over valid rows and the wizard SHOWS the exclusions (never silently drops — no-silent-caps rule).
3. Build csv/txt/xlsx per layout (xlsxwriter pattern :32-84), base64 → Binary field → re-open wizard (download).
4. Soft-log to `bank.export.log` when the model exists.

**Delivery — `pb.payslip.delivery.batch`**: `run_id`, `state` (`draft|sending|done`), `sent/failed/skipped` counters; `pb.payslip.delivery` lines: `slip_id`, `email`, `state` (`sent|failed|skipped_no_email`), `error`, `mail_id`. `action_send()` iterates done-state slips: render themed PDF via the report action → encrypt with PyPDF2 (password = pattern from `ir.config_parameter` `pb_pay_delivery.pdf_password_pattern`, default `{account_last4}{birth_year}`; supported placeholders `{account_last4}`, `{birth_year}`, `{employee_code}`; resolved per employee, **never logged, never stored**) → attach to the mail template → `send_mail(force_send=False)` (queued; the mail queue cron sends). **Per-slip savepoint** — one bad slip never kills the batch. Resend = only `failed` lines unless `force_all`. Slips with no `work_email` → `skipped_no_email` (surfaced, not silent).

**UI — WOW mandate (binding, all F–J phases)**: every surface this phase touches must be WOW-grade per the Payobook design system, and **any legacy screen the phase builds on gets redesigned into the system as part of the phase** — never left stock. Concretely here: the existing `vietnam.bank.export.wizard` native form IS legacy — it is replaced by a bespoke full-screen OWL experience (`pb_pay_delivery` action tag, pbim shell like the Import wizards); the wizard model stays as the backend, its native form view is removed from menus. Export and Delivery both launch from the **Pay Runs cockpit** (a "Pay & Deliver" panel on the run card — the same surface that carries Pay Salary, memory `payobook-ia-surfacing`), not from the legacy `hr.payslip.run` form.

---

## 4. WOW-UX specification (exceptional, out-of-world — consistent with the WOW screens already shipped)

1. **"Pay & Deliver" flow, launched from the Pay Runs cockpit**: a full-screen two-lane experience — left lane "Money out" (bank file), right lane "Payslips out" (delivery) — with a cinematic header showing the run (period, headcount, total NET counting up on load).
2. **Bank export lane**: bank selector as large logo-chip tiles (registry short names), live counters ("38 payslips · 2 excluded"), exclusion drawer (rose rows, reason chips "invalid account"/"unknown bank" with a deep-link to the employee's bank record), generate → animated build progress → a satisfying download tile (file icon, size, row count) with a subtle success sweep. Re-generate is idempotent and obvious.
3. **Delivery lane**: recipient preview (avatars stack + count), skipped list (amber, with why), password-pattern explainer card; send → per-line status pills streaming in (green sent / rose failed / amber skipped), one-click "Resend failures", and a final summary card worth screenshotting in a client demo.
4. **Legacy replacement**: the old native wizard form and any stock list views for delivery logs are NOT shown to users — bespoke OWL everywhere; native views exist only as admin fallbacks off-menu.
5. Design-system discipline: pbim tokens, white+rail hero, no gradients/emoji, Lucide only (`download`, `mail`, `lock`, `landmark`), button hierarchy per the locked palette. Chrome-MCP validate edge cases (0 valid rows, all-skipped delivery) — empty states must be designed, not blank.

---

## 5. Safety rails

1. **Read-only over master** — generation and mailing never write any `vietnam_bank_*` or employee field.
2. **Validation before generation** — a file can never contain a row failing `account_ok`; exclusions are always visible in the wizard result.
3. **Access**: wizard + delivery gated `om_hr_payroll.group_hr_payroll_manager` OR the finance groups (clone the `_FINANCE_GROUPS` pattern in `pb_bank_ocr/models/pb_bank_ocr_cockpit.py:16-17`); an employee-level user calling the RPC gets AccessError (test it).
4. **Password hygiene**: pattern resolved in memory per employee; never in logs, never in `pb.payslip.delivery` rows, never returned by RPC. C18.14 applies — no secrets in data XML.
5. **Email only `state='done'` slips**; drafts refuse with a friendly error.
6. **Idempotent delivery** — re-running a batch never double-sends `sent` lines.
7. Debrand rides automatically (send-time hook) — do not re-implement.

---

## 6. Test cases

**Server (in `pb_pay_delivery/tests/`, plus one edit in `pb_bank_ocr`):**
1. Layout resolution: each of the 7 `bank_format` keys resolves to a layout; a missing layout raises a friendly UserError.
2. CSV content: generated Vietcombank file contains employee account, holder (diacritics intact under the layout's encoding) and NET amount matching the :267 extraction, one row per done slip.
3. Fixed-width TXT (pick BIDV or VietinBank per the real spec you encode): column offsets and padding exact; XLSX opens and cell types are numeric for amounts.
4. VietinBank + ACB layouts exist as data and produce non-empty files (they were the missing scope banks).
5. Validation: a slip whose employee has account `123` (fails `account_ok`) is EXCLUDED with a reason and the file still generates for the rest; zero valid rows → UserError, no file.
6. **test_09 extension in `pb_bank_ocr/tests/test_bank_ocr.py`**: after the approval chain writes the new account, generate a file for that employee's slip → assert `123456789012` appears in the decoded file content (this closes the Phase-D honest-scope note in the test docstring).
7. Delivery: batch over a 3-slip run (one employee without work_email) → 2 `mail.mail` rows created + 1 `skipped_no_email`; re-run → no new mail rows; force_all → resends.
8. Encryption: the attached PDF opens with the pattern password and refuses without it (PyPDF2 `PdfReader.decrypt` round-trip in the test).
9. Access: a plain employee user calling `action_export_file` / `action_send` raises AccessError.
10. Draft slips refused for delivery; done-only filter proven.

**Chrome MCP:**
11. Export wizard from a demo run: exclusion table renders, file downloads (screenshot).
12. Send Payslips: status pills + resend button (screenshot). Do NOT actually deliver externally — check the queued `mail.mail` rows in Settings > Technical instead, and leave them unsent (delete the queued rows after the screenshot; demo-pristine rule).

---

## 7. Deploy & verify

Memory `payobook-deploy` ritual, `--uid=odoo`, kill stale by PID. `-i pb_pay_delivery -u pb_hr_payroll_vietnam,pb_bank_ocr --test-tags /pb_pay_delivery,/pb_bank_ocr` (NEVER a bare `--test-tags` — C18.40). Bump versions (C2). Live: run §6.11-12 on the existing June Retail demo run; confirm the demo outgoing-mail queue is left EMPTY afterwards. Report the SMTP posture you find on live (is a real SMTP server configured? if yes, flag it — we must not accidentally email demo addresses).

---

## 8. Report back

1. Tests 1–12 results + the two screenshots.
2. The exact per-bank column specs you encoded (VCB/BIDV/TCB/MB/VietinBank/ACB) with your source for each layout (bank template doc or best-effort inference — flag inferred ones for client confirmation).
3. Live SMTP posture + proof the demo mail queue is clean.
4. Deviations, file list, manifest versions.
5. New gotchas → proposed C18 addendum wording.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_F_PAY_DELIVER.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding — esp. C18.14/24/31/40), then implement Phase F exactly as specified: new `pb_pay_delivery` with data-driven bank-file layouts (7 banks incl. VietinBank + ACB), validated file generation on the existing VN wizard, and password-PDF batch payslip delivery with a per-slip log. Tests §6 including the pb_bank_ocr test_09 file-content extension, deploy §7. Report back with the five §8 items. Files read the employee master — nothing in this phase may ever write it.
