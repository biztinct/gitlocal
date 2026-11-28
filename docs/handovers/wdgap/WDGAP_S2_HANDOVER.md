# WDGAP Step 2 — Government paperwork and bank files (design + phase handovers)

Owner started Step 2 on 2026-11-18. Binding rulings (in
`/Users/adity/Documents/GitHub/gitlocal/docs/handovers/wdgap/WDGAP_OWNER_RULINGS_2026-11-15.md`,
main checkout, untracked — read by absolute path): **G1** countries first = Indonesia,
Vietnam, India, Singapore (Malaysia later); **G2** every file reads the CUSTOMER'S OWN
pay figures (what their pay runs worked out) — never the ready-made packs; Step 1 stays
postponed; never edit `pb_pack_*`; **G3** build from published official layouts; every
output is marked "Check with your adviser before first filing" until the customer's HR
marks that form "Accepted by the authority" (per company, per form; who + when kept);
**G4** employees propose tax details on My Payobook; nothing changes until HR approves;
proof attachment. Also IDB1a/IDB2/IDB3 (payment list) and BK1/BK2.

**Verified plumbing — do not re-derive:**
`/Users/adity/Documents/GitHub/gitlocal/docs/handovers/wdgap/WDGAP_S2_FACTS.md`
(main checkout, untracked; `origin/19.1` @ 6843fa946; file:line for everything). Its
sections are referenced below as FACTS §x. Also read on `origin/19.1`:
`docs/handovers/wdgap/WDGAP_LEDGER.md` (conventions + every gotcha row FACTS §G.1
lists), `WDGAP_WAVE_RULES.md`, `WDGAP_IDB1_REPORT.md`, `WDGAP_S6A_REPORT.md`.

## Shape of the step

| Phase | Wave | Lane (only this phase edits these) | New module |
|---|---|---|---|
| S2-A Form lines + filing engine + ID/VN monthly tax returns | 1 | `pb_govt_reports`, `pb_compliance_hub` (Filings lens only), legacy false-claim wizards (retire) | `pb_form_lines` |
| S2-C Bank layouts for any country | 1 | `pb_pay_delivery`, `pb_bank_ocr` (registry only) | — |
| S2-D Tax details on My Payobook | 1 | `pb_me_details` (hooks/extension points only), `pb_employee_vault` (Full details groups only) | `pb_me_tax` |
| S2-B Year-end certificates, IN + SG forms, fund files outside VN | 2 (after S2-A merges) | `pb_form_lines` | — |

Wave 1 runs side by side; ONE go-live for the step after wave 2. Nobody edits
`pb_lifecycle/`, `pb_pack_*`, `pb_me_portal` (hooks only, FACTS §D.4), `pb_explorer`,
`pb_hr_payroll_formula` engine code (a plain new field or registered source is allowed
only where a phase says so), or another phase's lane. A needed change in another lane →
write it in your report as a merge-time task, do not make it.

## Rules for every phase

- White-label: the word "Odoo" must never appear in anything an end user can see (UI,
  file contents, file/sheet names, PDF titles — ledger S5M-5: set the report title
  yourself). "Payobook" must not appear in generic `biz_*` modules.
- Plain screen words; design mandate + quiet-board pattern per ledger; Lucide icons, no
  emoji; phone width works. vi/id PO for every new string (PO gate precedent FACTS §F
  iv; ledger PO rows).
- Official layouts: use the authority's/bank's PUBLISHED specification. You may use
  WebSearch/WebFetch for public specs only; never send any customer, employee, company
  or owner detail to an outside service. Record each source (name, URL, version/date)
  in the form/layout's note and in your report; anything you could not confirm from a
  published source is marked INFERRED on the record and in the report. Never invent a
  field silently.
- No credentials or test passwords in any file, commit or message; never commit
  `outputs/`, `SUDIMA/`, `RIZE/`; explicit-path staging; no `git stash`; no force-push.
  Demo/test names: no "RIZE"; prefix DEMO.
- Worktree branch from `origin/19.1`: `wdgap-s2a` / `wdgap-s2c` / `wdgap-s2d` /
  `wdgap-s2b`. Own database `wdgap_<phase>_t`, own port; drop it after; other builders
  share this Mac. Long jobs in ONE command with a bounded poll that checks the process
  is alive — never end a turn on "waiting". Do NOT deploy; do NOT touch the live
  server. Existing outputs stay byte-identical unless the phase says otherwise (golden
  tests: VN bank file, payment list, payslip PDFs, VN social-insurance reports).
- Tests: your numbered cases + full suites of every touched module; failure set =
  recorded baseline on `origin/19.1` (run the baseline first). Browser smoke on the
  local copy, desktop + phone, console clean.
- Commit per feature, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  push your branch. Usage-limit error: commit WIP (explicit paths), PAUSED at the top
  of the report, stop.
- Report `docs/handovers/wdgap/WDGAP_<PHASE>_REPORT.md` on your branch: verified facts
  added (file:line), what was built, sources of each layout, INFERRED list, tests vs
  baseline, version raises, merge-time tasks, deploy notes (modules to `-i`/`-u`;
  silent-install proof to check; rize rehearsal needs), new ledger gotchas, owner
  questions as plain real-world questions. Final message under 250 words, plain simple
  English, screen words only.

---

## S2-A — Form lines, the filing engine, Indonesia + Vietnam monthly tax returns

**Goal.** HR says once which line of each government form every pay item goes to;
Payobook then fills the form for a period from finished payslips, behind an approval,
with a logged download. Wave 2 adds more forms as DATA + small renderers on this engine,
so the contract below is binding.

**New module `pb_form_lines`** (depends: `pb_hr_payroll_formula`, `om_hr_payroll`,
`biz_approval_workflow`, `pb_approval_config`, `pb_hub`, `pb_import_kit`,
`pb_filter_kit`, `mail`; NOT `pb_hr_govt`, NOT any `pb_hr_payroll_<country>` — FACTS
S2F-7).

1. **Catalogue (data, `noupdate="1"`):** `pb.gov.form` (country, code, name, authority,
   period kind month/quarter/tax_year, output kinds, source note, `inferred` flag) and
   `pb.gov.form.line` (form, code, label, kind: money / count / text / computed-from-
   other-lines, per-employee vs total, sign rule). Ship: **ID** monthly income-tax
   return for employees (PPh 21/26 — the current e-Bupot 21/26 monthly import layout)
   and **VN** monthly/quarterly PIT declaration 05/KK-TNCN.
2. **Mapping (company + scheme scoped):** `pb.gov.form.map(form_line, rule_id
   (hr.formula.rule), share/sign, source: payslip line | computed value)` — clone of
   `pb.fund.payee.item` (FACTS §B option 1, §F ii) but one pay item MAY feed several
   lines/forms; a line may take several items. "Suggest" pass from pay roles + name
   stems (never auto-saved; HR confirms). Screen: Compliance › Filings → "Form lines"
   (board in the fund-payees style: per form, each line with its items, unmapped-items
   tray, warnings: item not on payslips → offered as "computed value" source, FACTS
   S2F-6).
3. **Reader (the contract wave 2 relies on):**
   `env['pb.gov.form.reader'].read(form, company, period_start, period_end,
   scheme_ids=None) -> {'lines': {line_code: amount}, 'employees': [{employee_id,
   'lines': {...}, 'identity': {...}}], 'payslip_ids': [...], 'warnings': [...]}`.
   Done payslips only (never draft/verify — FACTS S2F-3); pay month by the payslip
   period; tax year from the scheme (`tax_year_start_month`, ledger W2A-4); deduction
   sign rule = the one-pay-band rule (`abs()`, back-pay band helper — ledger W2D2-2);
   lines by `(formula_config_id, code)` SQL as fund payments does
   (`pb_fund_payments/models/fund_payment.py:262-310`); "computed value" source reads
   `hr.payslip.formula_computed_values`; never adds two currencies; multi-company safe
   (`hr.payslip.run` has no company — ledger IDB1-1).
4. **Filing output record** `pb.gov.filing` — clone of `pb.payment.list.file`
   (FACTS §F i): form, company, period, stored files (+sha256), control totals, row
   count, warnings JSON, payslip ids, states draft/pending/approved/returned/rejected/
   superseded; process key `filing` (existing route, FACTS §A.3 — do not create a
   second key; rize route behaviour follows whatever `filing` is set to there);
   approved-bytes-only download + trail line (no tax numbers in the log); prepare
   supersedes the previous try; the G3 mark is printed on the cover sheet/first row
   comment and shown on screen until "Accepted by the authority" is ticked (manager
   only; who/when kept; un-tick allowed).
5. **Renderers** registered per form code (`_pb_render_<code>(filing, data) ->
   [(filename, bytes, mimetype)]`): ID → the XLSX/CSV the tax office's bulk import
   expects + a human-readable XLSX summary; VN → XLSX in the 05/KK-TNCN line order
   (+ the official XML only if you can confirm the published schema; else INFERRED and
   left out). Identity columns come from the employee record (ID `pb_npwp_number` /
   NIK; VN `vietnam_tax_code`) — missing identity = warning row, never a crash.
6. **Filings board integration (`pb_govt_reports`):** new forms appear as tiles for
   the company's countries beside the VN social-insurance tiles; the stepped flow for
   them is: period → check (totals, warnings, unmapped items) → send for approval →
   download. Fix the gate mismatch (FACTS S2F-8): seeing the lens and generating use
   the same right (payroll officer/manager); VN social-insurance tiles keep working.
7. **Retire the false-claim doors (FACTS §A.2, S2F-4):** SG CPF, TH SSF, KH NSSF, MY
   EPF wizards, VN tax report wizard, the dangling VN social-insurance button, MY/KH
   import wizards → each button either removed from every menu/dashboard/board or
   replaced by an honest "Not available yet" message that makes no claim; no data
   migration; list each door and what you did. Do not delete models that have stored
   rows.
8. **Vietnam social-insurance reports (`pb_hr_govt`) — minimal honesty fixes only:**
   done payslips only; insurance-book column from `vietnam_social_insurance_number`
   (fall back to empty, never the national ID); remove placeholder serial/account
   literals (leave empty). Their code→item reading stays as is in this phase (say so
   in the report as a wave-2 candidate). Golden: with no draft slips and the field
   filled, output otherwise unchanged.

**Non-goals.** No year-end certificates, no IN/SG forms, no fund files outside VN (wave
2); no e-filing submission; no change to how pay is computed; no pack edits.

**Tests (numbered).** 1 mapping CRUD + one item on two lines + company isolation.
2 suggest proposes, saves nothing. 3 reader: done-only; two schemes; computed-value
source; deduction sign; back-pay line; tax-year boundary for an April scheme; two
currencies refused/split. 4 ID return: totals = sum of mapped payslip figures for a
seeded run; identity warnings. 5 VN return likewise. 6 filing approval: prepare →
pending → approve → download; hash mismatch refused; requester/decider per route;
decider with no payroll group (ledger W2B-2). 7 supersede. 8 G3 mark present until
accepted, absent after. 9 access: officer/manager yes; HR without payroll, portal no
(screen + URL + RPC). 10 retired doors make no claim. 11 VN social-insurance golden +
the three honesty fixes. 12 install is silent (no mapping, no filing, nothing in the
Approvals inbox, no job that sends). 13 PO gate; no "Odoo" in strings or outputs.
14 browser walk desktop + phone.

---

## S2-C — Bank payment files for any country

**Goal.** A bank-specific payment file for non-Vietnamese banks, rendered from the
payment-list rows (approved account, take-home from `pb_pay_totals`) through a layout,
behind the existing bank-file approval. Seam = FACTS §C.4.

1. Extend `pb.bank.file.layout`: `country_id`, optional `currency_id`, header and
   trailer record templates (with count / total / date / company account / reference
   tokens), amount format (integer, 2-decimals, implied decimals — ledger IDB1-3), new
   column sources: payment date, currency, bank BIC, bank clearing code, beneficiary
   email (empty default), reference, row count, control total, literal. Layout chosen
   on Pay & deliver: "Payment list (any bank)" card gains "Bank layout" (default: the
   general list, unchanged bytes — golden).
2. Rendering: `pb.payment.list` rows → layout → stored on `pb.payment.list.file` as a
   third stored format beside xlsx/csv (own sha256; approved-bytes-only download;
   same trail). Rows the layout cannot express (missing clearing code, account too
   long, non-ASCII holder name where the bank forbids) → excluded WITH a plain reason
   and listed on screen and in the general list's "Check" column; never silently
   truncated.
3. Fix FACTS S2F-1 (the `bank_format` Selection refuses new layout keys) WITHOUT
   changing the Vietnamese path's bytes; fix S2F-2: shipped layouts become
   `noupdate="1"` with a migration that preserves existing rows; a company can copy a
   shipped layout and edit the copy (Settings screen: Pay › Bank layouts — list, copy,
   edit columns, preview with 3 sample rows; payroll manager only).
4. Bank identity: `res.bank` gets a clearing/national code field used by layouts
   (label per country: Indonesia "Bank code", India "IFSC", Singapore "Bank / branch
   code"); the Updates/import bank-code header stops being forced into the BIC lane
   ONLY if you can do it inside your lane — otherwise merge-time task. A small bank
   directory (data, `noupdate="1"`): main Indonesian, Indian and Singaporean banks with
   their public codes, used to resolve a recorded bank name (aliases) — extend
   `pb.bank.registry` with `country_id` (VN rows keep working, VN matching unchanged).
5. Ship layouts (each with its published source or INFERRED): **Indonesia** BCA
   (KlikBCA Bisnis payroll/multi-transfer upload), Mandiri (MCM bulk/payroll), BNI
   Direct, BRI CMS; **India** a generic NEFT/RTGS bulk upload (IFSC, account, name,
   amount) + HDFC and ICICI bulk salary formats; **Singapore** DBS IDEAL bulk
   GIRO/FAST, OCBC Velocity GIRO, UOB BIBPlus bulk — do the ones you can source; list
   the rest as INFERRED or not shipped. Every shipped layout note says "Check with
   your bank before the first upload".

**Non-goals.** No change to which account is paid or to approvals; no bank API; no
Vietnamese layout changes; no edits outside `pb_pay_delivery` + `pb_bank_ocr` registry.

**Tests.** 1 VN bank file golden. 2 general list golden. 3 each shipped layout renders
a seeded run: header/trailer totals and counts right; amounts per format. 4 exclusions
with reasons. 5 approval + hash + download + trail for the layout file; rize-style "no
approval needed" route. 6 new layout key accepted end to end (S2F-1). 7 upgrade keeps
an edited copy and existing rows (S2F-2 migration test). 8 bank resolve by alias per
country; VN unchanged. 9 access (bank-file door only). 10 formula-injection and
leading zeros. 11 PO gate / no "Odoo". 12 browser walk.

---

## S2-D — Tax details on My Payobook

**Goal (G4).** Employee sees their tax details and proposes changes with proof; HR
approves; only then the employee record changes. Reuse `pb.me.detail.request` and its
approval chain (FACTS §D.3) — new kinds, not a new request model, unless impossible
(say why).

1. New module `pb_me_tax` (depends `pb_me_details`, `pb_employee_vault`,
   `pb_hr_payroll_formula`). Page `/my/tax` + tile under "Me" via `TILES.setdefault`
   (seq after existing rows — ledger S6M-4; the pinned `pb_me_portal` tile test is a
   merge-time task for the deployer: write the exact change). "Needs you" and "My
   requests" through the hooks.
2. Fields by the employee's scheme country (store on `hr.employee`; reuse existing
   fields first — FACTS §D.1; add only what is missing): **VN** tax code, dependants
   (links to the existing family flow — do not duplicate it; show registered tax
   dependants and their state); **ID** NPWP/NIK-as-NPWP, PTKP status (new selection
   TK/0…K/3, K/I/…), BPJS numbers (view only); **IN** PAN, tax regime old/new (new),
   UAN (view only); **SG** NRIC/FIN (view, masked), tax residency (view), self-help
   fund choice (new). Sensitive numbers masked on screen to the last 4 except while
   editing own.
3. Each change = a request with optional/required proof (required for tax number and
   PTKP/regime change), HR review, apply writes exactly what was proposed; before/
   after rows in the Approvals inbox; one open request per kind.
4. **What it does NOT do, stated on screen for HR:** a customer's pay rules read their
   own inputs (FACTS §D.2). Expose each approved field as a registered application
   source a scheme CAN read (precedent `application_source_key`), but wire nothing into
   any existing scheme. For VN dependants show HR a read-only "does not match" note
   when the approved dependant count differs from the contract's registered-dependants
   component (FACTS S2F-5) — never change the contract component.
5. HR "Full details": add IN and SG tax groups (FACTS §D.1 last row) in
   `pb_employee_vault` (groups only).

**Non-goals.** No payslip or scheme change; no change to the family flow's rules; no
`pb_me_portal` edits.

**Tests.** 1 own employee only (no route takes an id). 2 each kind: propose → nothing
changes → approve → written; refuse → nothing. 3 proof required where stated; file
stored once, one savepoint. 4 masking. 5 country shown follows the scheme country; an
employee with no scheme sees a plain message. 6 approver without payroll group. 7 the
VN mismatch note. 8 application sources registered and unused by default (a seeded
payslip byte-identical before/after install). 9 silent install. 10 privacy: other
employees, line managers, payroll without HR cannot read requests/proofs. 11 PO gate /
no "Odoo". 12 portal browser walk on phone width (ledger PRB-W5).

---

## S2-B — wave 2 (designed after S2-A reports; outline only)

Year-end: ID 1721-A1 employee certificate (PDF) + annual figures; VN annual
finalisation 05/QTT-TNCN + employee tax-withheld certificate; IN Form 16 Part B figures
(PDF) + quarterly 24Q figures; SG IR8A (AIS file + PDF). Fund files: ID BPJS
Ketenagakerjaan (SIPP) + BPJS Kesehatan (e-Dabu) upload sheets; IN EPF ECR text file +
ESI sheet; SG CPF EZPay file + SDL. My Payobook: employee downloads own year-end
certificate once HR releases it. Rewire the VN social-insurance reports onto form-line
mapping. All on the S2-A reader/filing contract.
