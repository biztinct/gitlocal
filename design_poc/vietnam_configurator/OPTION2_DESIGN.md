# Option 2 — Payroll Blueprint

> Latest revision: see `IMPLEMENTATION_HANDOFF.md` for the approved six-step journey, optional Mapping/Approval/Payslip setup and the implementation plan. The earlier journey below records the original design rationale.

This is a separate, interactive design proposal at `/option2` and a standalone HTML artifact at `public/option2.html`. Option 1 remains unchanged. It is a local browser prototype, not an Odoo deployment or a certified Vietnam legislative pack.

## Design recommendation

Use six intent-based steps: Your blueprint → Pay components → Tax & protection → Pay & deliver → Prove it works → Review & create. A persistent employee story shows the effect of each calculation decision. Keep advanced tax, insurance and payout controls behind disclosure, while the first view asks a plain-language question. Match Payobook’s deep-purple navigation, violet actions, light panels and rounded geometry.

Use **Excel as the rule source of truth**. Guided settings generate Excel formulas; manual edits take precedence, retain their generated counterpart and are not silently overwritten or reverse-engineered into misleading controls. Validate syntax, references and dependency cycles, then evaluate the same Excel formula in the sample preview. The export uses `excel_formula`, readable component-code references and typed inputs. Standard Excel workbook use requires corresponding defined names or a cell-reference translation. `BRACKET` is an existing Formula Studio convenience, not a standard Excel function; this proposal emits SUM/MIN/MAX marginal-band formulas instead.

The local parser supports arithmetic, comparisons, IF, AND, OR, NOT, SUM, MIN, MAX, ROUND, FLOOR and ABS. It deliberately does not claim to implement all Excel syntax. It never uses JavaScript eval. Company-paid incremental benefit PIT is expressed using 32 non-circular Excel helper columns plus a residual check. If convergence is worse than 1 VND, calculation fails. Full guaranteed-net contracts are a separate integration recipe.

## Workbook coverage and decisions

All 24 earnings, 8 deductions and 6 benefits from the three source tabs are included initially. Components can be removed/restored and custom ones added. The rule editor covers approved inputs, fixed amounts, contractual salary, salary percentages, role amounts, overtime hours/rates, annual service ratios and linked premiums. Tax treatment, exemption evidence, annual limits, entitlement, proration, payout month, employer-paid PIT, insurance basis, contribution rates and benefit cost sharing are editable where applicable.

The other nine tabs inform the broader design:

- Company Setup and Payroll Calendar: currency, effective date, cutoff, second-last working-day payday, late-input routing, holiday-calendar dependency, separate joiner/final-pay rules.
- Statutory Config and PIT Brackets: editable bands and relief, residency/contract routes, insurance caps and policy conflict visibility.
- Bank Accounts and Bank File Spec: synthetic account text, leading zeros, bank identifier types, currency/FX, payment reconciliation, explicit transmission-vs-validation mapping.
- Payslip Mapping: bilingual labels, zero suppression, cash/non-cash distinction and release timing.
- Approval Matrix: distinct input, payroll, bank-maker/checker, signatory and reopen responsibilities. Role names replace personal names.
- Dashboard: readiness is computed from actual unresolved decisions and tests. Its green statuses are not imported as evidence.

Workbook status flags, personal names, individual account details, source-action prose and spreadsheet validation helper columns are not payroll arithmetic parameters. Source sheet/cell provenance is retained. Bank helper columns are not blindly emitted as payment fields. The source workbook is not modified.

Unresolved evidence remains visible: union dues 0.5% vs 1%; incomplete benefit eligibility/costs; foreign cash allowance insurance treatment; inconsistent migration/YTD notes; absent Employee Master, Compensation, GL Mapping, UAT, Open Items and Source Index tabs referenced by the dashboard; unconfirmed bank-format/date fields. Rates shown are workbook assumptions, not newly certified legal advice.

## Existing models and integration plan

Repository inspection established these actual connections:

| Existing surface | Current model / field | Proposed enhancement |
| --- | --- | --- |
| Vietnam configuration | `hr.formula.config.vn_tax_table_id`, `vn_insurance_policy_id`, company-default switches | Preserve the existing links; pin approved effective-date snapshots and display drift |
| Statutory tax tables | `vietnam.tax.table` | Select an approved company record; existing source defaults still create 2024 bands and old relief values |
| Formula Studio rate tables | `hr.formula.rate.table`, `hr.formula.rate.bracket`, `BRACKET` | Bind master provenance to a config snapshot, validate unique ascending thresholds and source version |
| Insurance policies | `vietnam.insurance.policy` | Resolve applicable policy and eligibility, separate employee deductions from employer cost |
| Formula engine | `hr.formula.config`, `hr.formula.rule.excel_formula` | Add a validated create-from-blueprint adapter; current `create_config` seeds templates and does not accept this custom blueprint |
| Data mapping | employee/contract inputs and `res.partner.bank` bank lanes | Enforce typed required inputs, account text integrity and date-specific provenance |
| Pay & Deliver | `pb.bank.file.layout`, `pb.bank.file.column` | Extend the source vocabulary for bank code, payment date, currency, email and FX, then validate against a bank-approved file |
| Payslip configuration | `hr.payslip.config` | Map output codes to the selected salary structure, sections and bilingual layout |
| Payroll lifecycle | existing scenario/test/review/release and retro/proration/carryover modules | Reuse approval evidence, historical periods, segmentation and paired-cycle recovery rather than inventing a parallel lifecycle |

Bank layouts currently expose a limited source enum, so the workbook's full bank specification cannot be represented without an extension. Config tax links already exist; the missing part is not a brand-new relationship but versioned resolution and synchronization to Formula Studio's separate rate tables.

## Complex scenarios: explicit scope

Working calculations: monthly cash/non-cash components; working/calendar-day proration; local/foreign insurance eligibility; resident progressive, non-resident flat and short-contract withholding; annual uniform exemption balance; qualifying exemption; approved severance entitlement; annual payout; role allowances; employer-paid incremental benefit PIT; benefits linked once; manual Excel overrides; currency conversion of payment output only.

Integration recipes represented in the design: multiple salary segments in one month; true historical tax/cap/YTD recomputation; net contracts; tax equalisation/shadow payroll; mid-cycle/end-cycle recovery; loan schedules; negative-net recovery/carry-forward; holiday calendars; GL mappings; maker/checker/signatory assignment and bank acceptance. Selecting these does not pretend that a single-period calculator implements them.

Prototype review items may remain open when creating a local schema, but formula errors and failed checks block creation. Production activation must also require confirmed source policies, required mappings and approved test evidence. Exports explicitly set `productionCompatible: false` and `activationAllowed: false`.

## Validation

Run `npm test` for the original 15 engine tests plus 16 Option 2 tests. The latter cover independent golden values, tax boundaries, proration, foreign UI exclusion, gross-up and no double-counting, threshold/commitment, exemptions, manual override preservation, missing/circular references, removed benefit links, custom salary percentage, editable tax bands, invalid input guards, account text/FX and parser safety.

Chrome interaction coverage includes guided navigation, manual Excel validation, invalid tax band rejection, bank validation, scenario checks and schema creation. Screenshots are emitted in memory; no test PNGs are saved. `public/og.png` is an existing product social-preview asset and is retained.
