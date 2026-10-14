# Country tax tables and payroll workbook mapping

The August 2026 Indonesia client workbook stores BPJS and premium calculations
in supporting worksheets and copies most resulting amounts into the payroll
report. The new template computes them in one `Payroll` worksheet. `Tax Map`
contains metadata that connects each statutory number to a database field;
it is not an employee table and must not become a formula component.

## Workbook calculations

- TK wage floor: Rp1,000,000, with a zero-wage exception for JKM, JKK and JHT.
- JP wage floor: Rp1,000,000 and ceiling: Rp11,086,300.
- JKM employer 0.3%, JKK employer 0.24%, JHT employer 3.7%, JHT employee 2%,
  JP employer 2%, JP employee 1%.
- Health wage floor: Rp5,729,876 and ceiling: Rp12,000,000. Employer 4%,
  employee 1%. Coverage flags preserve the client treatment of leavers.
- Insurance premium: annual premium divided by 12, rounded to whole rupiah.
- Basic salary: contract salary × paid calendar days / period calendar days,
  rounded, plus a salary adjustment. Paid days come from payroll inputs;
  date strings are not treated as arithmetic operands by the application.
- Premium tax allowance: gross up the additional tax on the insurance premium
  using regular income, excluding bonus, THR and incentive. A separate mode
  supports monthly full-tax gross-up; BPJS reimbursement has its own flag.
- TER: select category A/B/C from the PTKP status and apply that category's
  rate to the entire monthly taxable gross, with inclusive upper bounds.
- Final period: annual gross less job expense, deductible JHT/JP and PTKP,
  rounded down to Rp1,000, taxed with annual marginal bands, less tax already
  withheld. Refunds stay negative. Annual full-net gross-up requires a separate
  review and is explicitly unavailable in this August template.
- Qualifying severance: cumulative first-two-year PP 68/2009 marginal bands
  less prior withholding. The client has no nonzero severance example, so this
  is statutory reference logic rather than a client reconciliation control.

The source calculations reconcile for all 122 employees. Take-home pay agrees
exactly for every employee. One copied allowance differs by Rp1 from the
formula; gross, tax and deductions for that employee also differ by Rp1, with
no net-pay difference. Bank transfers, fund requests, accounting, BCA reports,
the CTC analysis and unrelated historical named ranges are excluded. YTD is
used only to validate the final-period refund and define the required inputs.
Delivered examples are fictional. Client identifiers and salary controls are
temporary local analysis data and are never repository fixtures.

## Database contract

`hr.payroll.tax.table` is a company- and country-scoped edition. It has a stable
code, version, effective dates, basis and method. Supported methods are
progressive marginal bands, a whole-income selected rate (Indonesia TER), and
statutory parameters. `hr.payroll.tax.band` stores sequential inclusive upper
bounds and fractional rates; a final upper bound of zero means unlimited.
`income_from` is derived from the preceding upper bound. The displayed “Above”
boundary avoids a one-rupiah gap or double taxation at a progressive boundary.

`hr.formula.rule` stores the explicit edition, band/parameter, field, original
sheet and cell. Database rates and Excel rates both use fractions (0.05 = 5%).
The form displays percentage inputs with a factor of 100. No inferred name
match, approximate lookup, or generated component code is used for binding.

`Tax Map` has these exact headers:

| Column | Meaning |
| --- | --- |
| Table Code, Country, Version | Source edition identity within the company |
| Effective From, Effective To | ISO dates; end may be blank |
| Method | `progressive`, `whole_income`, or `parameters` |
| Basis | `monthly`, `annual`, or `daily` |
| Slot | Consecutive band number or stable parameter code |
| Field | `upper`, `rate`, or `parameter` |
| Payroll Sheet, Cell | Exact numeric constant above the employee header |
| Label | Readable payroll component label |

The importer validates metadata before proceeding, excludes it from worksheet
selection, retains the original constant cell identity, imports all selected
formulas normally, then binds the constants. It creates draft editions and
reuses an existing edition only when all values and metadata match. A changed
workbook cannot overwrite a database edition under the same version. Invalid
country, percentages, missing slots, duplicate cells or excluded constants
abort the transaction.

The generated workbook declares `PayrollHeader` as an Excel named range.
The importer uses that employee header instead of mistaking the TER table
headings above it for employee columns. Tax Map templates use explicit
header/cell metadata rather than colored-header heuristics; the configuration's
existing color-import preference is preserved for other workbooks.

## Changes to government rates

1. Duplicate the current source edition, give it a new version and effective
   date, and edit its bands or constants. Publish through statutory approval.
2. Copy or branch the active payroll configuration for the new period.
3. Open Statutory, choose its tax country, then **Refresh payroll constants**.
   Select the draft/testing configuration and the date the rules must cover.
4. Review the old/new values. Request the refresh through statutory approval.
   The proposal rechecks its source and target stamp before applying changes.
5. Test and activate the new configuration through the existing scheme process.

The refresh selects the most recent published edition covering the chosen date
for each table code, company, country, method and basis. It records outgoing
constant versions and a configuration milestone. It never writes active,
validated or archived configurations, recalculates prior payroll, or silently
follows a new edition at runtime. A change in band count requires a revised
template/formula review, not a partial value refresh. Edits to published
editions and their child rows are refused. The source date represents the
client August snapshot, not the original legislation commencement date.

Mapped table identities (country, company, code, method and basis) are locked
even while the edition is a draft. Activation checks the latest published
edition for the configuration's selected statutory date. Changes to the
calculation method or period basis require a formula review just like a
change in band count; they cannot be hidden by selecting an older edition.

The table form exposes mapped constants, current/source values and alignment.
**Export mapped constants** downloads a cell-addressed patch in the same map
format. Apply its numeric values to the indicated cells in the payroll
workbook; the patch itself is not a complete payroll schema. The source
workbook remains synchronized by explicit cell identity in either direction.

The Statutory cockpit has a tax-country selector. Indonesia never displays
Vietnam slabs or VND values. Existing Vietnam tables retain their legacy
detail screens; new linked templates use the country library. Insurance and
contribution totals retain their existing company scope.

## Sources for additional annual and severance logic

- Client workbook: `0826 Rize Farm Indonesia Payroll Report R1.xlsx`, August
  2026, specifically Payroll, Calculation, BPJS TK, BPJS Health, Premi
  Insurance, TER A B C and the final employee's YTD rows.
- [UU 7/2021, Article 17](https://www.pajak.go.id/id/peraturan/harmonisasi-peraturan-perpajakan)
- [PMK 168/2023](https://pajak.go.id/id/peraturan/petunjuk-pelaksanaan-pemotongan-pajak-atas-penghasilan-sehubungan-dengan-pekerjaan-jasa-1)
- [PP 68/2009](https://www.pajak.go.id/id/tarif-pajak-penghasilan-pasal-21-atas-penghasilan-berupa-uang-pesangon-uang-manfaat-pensiun)
