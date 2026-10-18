# Rize Vietnam payroll master v3

The owner approved replacing the HC-derived calculation definition with a fresh
Vietnam configuration in **rize.payobook.com / rize**. The existing configuration
4639 has since been renamed `Rize Vietnam Payroll`, code `RIZE_VIETNAM_PAY`, and
activated. Its definition, source bindings and mappings are preserved. The new
configuration is **Rize Vietnam Payroll Master v3**, code
`RIZE_VIETNAM_MASTER_V3`, Draft. No payroll run, payslip or payroll assignment is
created by this installation.

## Authoritative sources

- `Rize_Vietnam_Payroll_Template_DATA_v3.xlsx` actually contains one Salary sheet
  and **no formulas**. The owner explicitly confirmed using
  `Rize_VN_Payroll_Report_Aug_2026_FINAL v3.xlsx` as the calculation master.
- August FINAL v3: Salary owns payroll logic; Data supplies approved adjustments,
  advisory payments, overtime and leave inputs; Union list supplies membership
  counts; SHUI independently reconciles insurance and employer contributions.
- `VN_HC_TemplateVietnam_updated_07Oct2026.xlsx` supplies the October roster and
  employee/contract values. Its salary overrides August where present. August
  supplies seven missing salaries and explicit recurring payroll settings.
- The DATA v3 file supplies the supplemental input headings. Its two identical
  Others headings are mapped by **physical columns S and AB**, with distinct
  non-taxable/taxable display labels. Flattened USD net-income/payment snapshots
  AJ and AO are excluded from the source-column catalogue; their authoritative
  formulas live in the calculation master.
- Sheet4 remains ignored. Exchange Rate is empty. Funding request is a downstream
  output. Premium-insurance and incident-support PIT comparisons remain visible
  information, as in the master; they do not silently change employee payment.

`tools/prepare_rize_vietnam_master.py` reads the originals without modifying them.
It writes a non-personal definition with source hashes and a separate private
payload containing the 70 August fixtures and 70 October roster records. Never
commit that private payload or the generated populated workbooks.

## Calculation and mapping decisions

The definition contains **185 components: 138 inputs, 42 formulas and five
constants**. It retains all 22 information-only HC Contract Text fields, all
11 recurring placeholders and the saved-dependent-count transformation.
Dependent/Children counts imported detail records; Registered tax dependents is
separate and is initialized from the payroll master's registered count, with an
October review note. No dependent detail or tax-eligibility record is altered.

| Master source | Application treatment |
| --- | --- |
| Salary Q | Gross salary / standard days × paid days, rounded to VND |
| Salary X–Y | Saved transport/phone entitlement, prorated by paid days; August job rules and individual exception initialize the entitlement |
| Salary V50 / Data resignation schedule | Explicit encashment days and salary divisor, not a monthly recurring payment |
| Salary AA / Data F, I, L, O | Sum four approved advisory payment buckets; outstanding amounts and payout percentages are not automatically paid |
| Salary AJ / Data E180:E194 | Weekend hours × salary / standard days / 8 × 200%, rounded |
| Salary AK | Approved holiday overtime amount; no unsupported holiday formula/rate invented |
| Salary M13 | Explicit insurance-basis setting for salary plus private-insurance allowance; other rows use contract salary or an explicit fixed base |
| Salary AN–AP, AS–AV | Employee/employer SI, HI and UI caps/rates; Expat excludes UI; explicit participation settings retained |
| Salary AQ / Union list | Member count × insurance base × 0.5%, capped at 10% of the 2,530,000 base salary, only with TU Joining x; fractional VND preserved |
| Salary AW–BA | Permanent personal deduction, separate registered-dependent deduction, five progressive bands; probation uses the workbook's 2,000,000 threshold and 10% withholding |
| Salary AL, AM, BB, BD | Noncash included in monthly/taxable income and employer cost, excluded from cash payment; tax-free allowance and overtime treatment preserved |
| Salary BI | Owner-approved correction: Net income − Advance − Deduction + Addition + PIT refund |
| Salary BN–BQ, BT–BW | Independent employer PIT comparison outputs; no automatic gross-up or additional employee withholding |

Before-tax Deduction Adjustment retains the source workbook's **signed negative**
input convention, because Salary AL sums the AH column. Advance and the later
Deduction fields are positive recoveries under the explicitly approved net
correction. USD conversion uses the master's 26,071 reference parameter rather
than the unrelated HC CTC exchange rate.

## Records and templates

The guarded installer refuses every database except `rize`, defaults to a full
rollback dry run, checks original source hashes, and refuses to overwrite a
previously installed/reviewed master configuration. Employee/contract changes go
through the application's **Records Desk approval engine**. Source placeholders
and nonnumeric values are skipped with review notes; blanks never erase saved
values. Existing employee name spellings/diacritics are preserved.

The approved October roster comprises 68 Active plus two Notice Period people.
Seven missing profiles and draft contracts are created from their HC identities;
the other 63 match stable country-based employee IDs. No payroll population is
assigned. Seven people still have no salary in either applicable source and
remain blocked by Payroll input validation until salary and payroll settings are
completed. August contract type, insurance/union settings and registered
dependents are baseline values requiring review for October changes.

The reusable monthly workbook has **five Time fields, 26 adjustment fields and
the protected Employee records sheet**. All monthly quantities/amounts start
blank. The optional annual-leave salary divisor is required by its formula only
when encashment days are positive. The third sheet and the separate Employee &
Contract workbook use the same 105 selected saved-record fields plus pinned
identities/name. Only the separate records import can propose master changes.

## Verification and deployment

Preparation passed all **70 August payroll rows / 2,205 cached Salary output controls and 560 SHUI controls**,
plus tax-band/probation boundaries, input guards and a nonzero net-adjustment
case: **96 stored scenarios, 2,800 control comparisons**. Real monthly resolution
also reads all 70 people from saved records: 63 Ready, seven Review salary.
August bonuses, overtime, advisory payments and attendance are not copied into
October monthly inputs. Both actual workbook generators and an unchanged
records round trip are checked. Definition errors are zero; informational output
visibility/unused-output warnings are reviewed separately.

Deployment and final Chrome verification receipts will be recorded here after
the Rize-only application and combined repository audit.
