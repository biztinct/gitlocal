# Bilingual component labels from an Excel workbook — the "Two languages in one heading" step

> **STATUS: NOT APPROVED — DECLINED BY THE OWNER, 2026-09-17. DO NOT IMPLEMENT.**
>
> The owner reviewed this design and decided against it: the risk of changing existing,
> working import behaviour outweighs the benefit. **The component name stays exactly as the
> Excel heading provides it.** No code was written and nothing in the product was changed.
>
> This document is kept only for the research in it — the measured shape of the Rize Vietnam
> workbook, the verified plumbing chain, and the regression risks. Do not restart this work
> without the owner asking for it by name.

Source workbook: `RIZE/VIETNAM/Rize_Vietnam_Payroll_Templatev2.xlsx`.
Everything below was verified against the code and the file on 2026-09-17.

---

## Context

The proposal was to import the Rize Vietnam workbook through the **New configuration**
journey, via the "Import Excel workbook" starter on step 1.

Every heading in that workbook carries **two languages in one cell**:

> `Ngày ký hợp đồng (Date contract)` — Vietnamese outside the brackets, English inside.

Today the import takes the whole heading as one flat string and stores it as the component's
only label. The result is a component literally called `Ngày ký hợp đồng (Date contract)` on
every payslip, report and analytics column, for every user, in every language.

The proposal was: the wizard **asks which language is outside the brackets and which is
inside**, splits all 73 headings accordingly, and stores the two halves as real Odoo field
translations — so a Vietnamese user sees `Ngày ký hợp đồng` and an English user sees
`Date contract`, from the same record.

**Owner decisions taken while designing (2026-09-17), before the design was declined:**
1. A proper new screen inside the journey, styled like the rest — not a page in the old grey pop-up.
2. **New imports only.** Existing pay setups keep the single name they have. No back-fill tool.
3. Component **codes built from the English half** (`DATECONTRCT`, not `NGYKHPNG`).
4. Built directly — no phased handover documents.

**Final owner decision: do none of it.** See the status banner above.

---

## What the workbook actually contains (measured — still true, reusable)

`Salary` sheet, header row **6**, 73 headings, columns A–BU. 34 formula columns, 39 input
columns.

| Shape | Count | Example |
|---|---|---|
| `Vietnamese (English)` — bracket at the very end | **71** | `Lương hợp đồng (Gross contract salary VND)` |
| Brackets in the MIDDLE — not a translation | **2** | see below |
| No brackets at all | 0 | — |
| Two bracket groups | 0 | — |

The two exceptions are why this could never have been a silent automatic rule:

- **AA** `New product launching (RP-Lem Lep Hat) incentive` — the brackets are part of an
  **English-only** product name. A naive split yields Vietnamese = "New product launching",
  English = "RP-Lem Lep Hat". Both wrong.
- **AG** `Phúc lợi (không trả bằng tiền) Non-cash benefit` — the brackets belong to the
  **Vietnamese** half and the English half trails with no brackets. The reverse shape.

Three more traps in the same sheet:

1. **Eight headings carry no Vietnamese diacritics** — `STT (No.)`, `Tham gia BHXH (SHUI Joining)`,
   `BHXH 8% (BHXH SI 8%)`, `KPCD 0.5% (KPCD TU 0.5%)`, `BHYT 3% (BHYT HI 3%)` … They *are*
   Vietnamese, as abbreviations. So accent detection can only move a **sheet-wide** score;
   it can never decide a single row.
2. **Duplicate halves.** `Phụ cấp khác (Others)` appears twice (S and AD) — identical on both
   sides. `Lương hợp đồng` appears twice (J, K), told apart only by the English half (USD vs
   VND). `BHTN 1%` appears twice (AN employee share, AS employer share).
3. **Dirty whitespace** — `STT\n(No.)` (newline), `BHTN 1%(BHTN UI 1%)` (no space before the
   bracket), `' Phụ cấp khác (Others) '` (padded both ends), `BHYT  HI 1.5%` (double space).

Other sheets prove the pattern is per-import, never global:
- `Sheet1` heading `OT Adjustment (hour)` — the brackets are a **unit**, not a translation.
- `Premium insurance` heading `DANH SÁCH NGƯỜI ĐƯỢC BẢO HIỂM/LIST OF INSURED` — the separator
  is a **slash**; and `Họ tên NĐBH` beside it has no second language at all.

---

## How the import works today (verified plumbing — reusable reference)

**The import chain**
1. `pb_blueprint/static/src/js/blueprint.js:541-543` — starter `excel` → `openExcel()`.
2. `blueprint.js:783-805` — `doAction` on `hr.formula.multisheet.import.wizard`,
   `target:"new"`, context `{default_config_id, pb_blueprint_return: true}`.
3. `pb_hr_payroll_formula/wizards/multisheet_import_wizard.py:45-52` — 7 states
   `upload → select_sheets → select_columns → configure_order → review_components → map_missing → confirm`.
4. `multisheet_import_wizard.py:797` — each heading stored verbatim as
   `hr.formula.multisheet.column.selection.original_header` (field at `:3791`).
5. `multisheet_import_wizard.py:1238` + `:1253` — `code = _generate_code(original_header, …)`
   and **`'generated_name': col_sel.original_header`** on `hr.formula.multisheet.component.preview`.
6. `multisheet_import_wizard.py:2976-2978` — `hr.formula.rule.create({'name': comp.generated_name, 'code': comp.generated_code, …})`.
7. `pb_blueprint/models/formula_config_ext.py:24-44` — with `pb_blueprint_return` in context,
   sets `blueprint.step='rules'` and returns the `pb_blueprint` client action.

**Where the label is stored and read**
- `pb_hr_payroll_formula/models/formula_rule.py:93-97` — `name = fields.Char(string='Label/Name', required=True)`.
  **Not `translate=True`.** Plain `varchar`.
- `pb_blueprint/models/blueprint_components.py:97` — step 2 renders `rule.name`.
- `pb_hr_payroll_formula/models/hr_payslip_formula.py:915` — `'name': rule.name` snapshotted onto the payslip line.
- `hr_payslip_formula.py:1332-1337` (`_line_name`) — payslip document renders
  `salary_rule_id.name or r.name or r.code`.
- `pb_payrun_results/models/payrun_results.py:75`, `pb_payslip_review/models/pb_payslip_review.py:148`,
  `pb_formula_studio/models/pb_formula_studio.py:1244,3447,5538,10673` — the same fallback chain.
- `pb_hr_payroll_analytics/models/hr_formula_config_analytics.py:348,427` — bare `rule.name`.

**Three facts worth keeping**
- `hr.payslip.line` is `_inherit = ['hr.salary.rule']` (`om_hr_payroll/models/hr_payslip.py:884-885`),
  and `hr.salary.rule.name` is `translate=True` (`om_hr_payroll/models/hr_salary_rule.py:91`).
  So **`hr_payslip_line.name` is ALREADY a jsonb translated column** — confirmed live in the
  comment at `pb_explorer/models/pb_fact_builder.py:70-74`.
- **`code` is already a user-editable field** — `pb_formula_studio/models/pb_formula_studio.py:2466-2474`
  `_EDIT_FIELDS` includes `'code'`; the only constraint is shape
  (`formula_rule.py:1911-1930`, uppercase/digits/no underscore, explicitly **not** non-substring).
- Generated formulas reference **column letters, not codes** (ledger rule BP-R4;
  `_resolve_cross_sheet_formula:1376`, `_resolve_same_sheet_formula:1500`), so renaming a code
  cannot break a formula.

**What exists for translations today**: nothing in the payroll stack. Zero `translate=True` in
`pb_hr_payroll_formula` / `pb_formula_studio` / `pb_blueprint`; zero `update_field_translations`
anywhere in `pb_*`. The only dual-language write in the product is
`pb_demo/models/demo_generator.py:105-108` (`_tr`) with `_ensure_languages()` at `:88-96`.
The only per-record bilingual label is the parallel-column `hr.payslip.config.label_vi`
(`pb_hr_payroll_formula/models/payslip_config.py:32-35`).

> **Ledger correction, and it stands whatever happens to this design:**
> `BLUEPRINT_LEDGER.md` rule **BP-R9** says bilingual labels are `salary_rule_id.name`. That is
> wrong in practice — `salary_rule_id` is optional and is only populated at payslip time
> (`payroll_import_batch.py:3864-3915`). The label the journey, the studio and analytics
> actually read is `hr.formula.rule.name`.

---

## The design that was declined

Recorded briefly, for the record only.

**A. Make the label translatable.** `translate=True` on `formula_rule.py:93` (Odoo converts the
column `varchar → jsonb` on upgrade), plus one shared helper
`pb_hr_payroll_formula/models/translated_label.py::write_label(record, field, by_lang)` using
`res.lang._activate_lang` and `update_field_translations`.

**B. A detection engine**, `pb_blueprint/models/label_split.py`, pure and unit-testable.
Sheet-wide first, row-wise second — because eight Vietnamese headings have no accents, a
per-row guess gets them wrong. Separator scored across all headings
(`brackets` / `slash` / `dash` / `newline` / `none`; brackets wins 71/73 here); language guessed
per **pool** of halves, not per row; then a per-row verdict of `clean` or a flag
(`separator_mid`, `no_second_language`, `same_language_both_sides`, `duplicate_label`,
`empty_half`). Codes from the English half via the existing
`pb_hr_payroll_formula/models/component_code.py::build_component_code`.

**C. A seventh journey step**, `labels`, shown only on the Excel path and only when a second
language was found. Hero specimen of one real heading with the two halves tinted differently, a
language picker under each half, a swap button, a separator segmented control, a confidence
strip ("73 headings · 71 read cleanly · 2 need you"), and a table of Column · Vietnamese ·
English · Code with flagged rows floated to the top and editable inline. Four RPCs on
`pb.blueprint.studio` (`bp_labels_load` / `_detect` / `_apply` / `_skip`), server re-deriving
everything on apply.

**D. Carrying both languages onward** — rule creation at `multisheet_import_wizard.py:2976`,
payslip line snapshot at `hr_payslip_formula.py:915`, `hr.salary.rule` copy at
`payroll_import_batch.py:3864`, and the journey's sentence editor at
`blueprint_components.py:894-897` writing only the current language rather than clobbering the other.

---

## Why it was declined — the regression risks

These are the reasons the owner judged the change not worth it. They are real and they would
apply again to any future attempt:

1. **Re-uploading the same workbook would stop matching.**
   `pb_formula_studio/models/pb_formula_studio.py:10501` matches a re-uploaded file's headers
   against `rule.name`. Once the name is split, matching must try the English half, the
   Vietnamese half **and** the rejoined original — otherwise re-import silently stops
   recognising columns, with nothing in any log. This was the single biggest risk.
2. **Analytics would not follow the reader.** `pb_explorer/models/pb_fact_builder.py:76`
   hardcodes `pl.name->>'en_US'`, and `pb_explorer/models/pb_explorer.py:1584-1586` falls back
   to a title-cased raw code for the `code` dimension. Both would need changing.
3. **A `.po` entry must carry both extractor comments** or half the product stays English with
   nothing in any log (BP54); entries over ~1,500 characters must be dropped, not left with an
   empty msgstr (BP49).
4. **No module-level label dicts** — a `{'separator_mid': "…"}` map at module scope can never
   be translated at all (BP54 corollary, `blueprint_studio.py:24-30`).
5. **A schema change on four live databases** — `hr_formula_rule.name` `varchar → jsonb` on
   `p9clone`, `payobook`, `abm` and `payobook_template`.

---

## Current behaviour, which is what ships

The workbook imports through the existing "Import Excel workbook" path unchanged. The full
bilingual heading — `Ngày ký hợp đồng (Date contract)` — becomes the component name, in one
piece, for every user in every language. That is deliberate.
