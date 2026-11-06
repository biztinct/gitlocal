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

Implementation commit `adc566feb` was applied to Rize as configuration **4760**.
The approved Records Desk route applied **3,317 values across 70 people** under
**RD00141**, with no refused changes. Seven profiles and seven draft contracts
were created; employee data was not copied to another database. The original
configuration, all dependent rows and the zero payroll-run/payslip baseline are
preserved. The deployed 74 template/dependent-count regressions pass.

Chrome then identified that positional Others bindings displayed only S and AB.
A small shared Formula Studio fix honors explicit source display labels and
physical Excel positions without changing stored keys. Its regression covers
two identical headings, their different labels/positions and unchanged wires.
Curated metadata on configuration 4760 supplies those labels; generic imports
retain their existing behavior. `VN_MASTER_VERIFY=1 VN_MASTER_LABELS_APPLY=1`
performs this Rize-only metadata update after the shared code deployment and
rechecks the calculation/record invariants. Other databases receive shared code
only. Final combined deployment and Chrome receipts follow below.


## Final deployment and checks

The latest combined application tree at **ff795602a** was synchronized to
Payobook19v2: **149 modules / 4,901 files**, verified byte-for-byte. Formula
Studio **19.0.1.202.3** was upgraded on **rize, payobook, payobook_template, abm
and p0clone**; the service is active and every installed custom-module version
matches the repository. The shared rollout preserved each database's business
counts, aggregate wages and active cron IDs. Its protected backup is
`/odoo/backups/vn-master-code-20261018-191226/`.

The Vietnam installation and display-metadata update were applied **only to
rize**. A full-row hash audit of Employee, Contract, contract advantage,
configuration, component and dependent tables proves the other four databases
are unchanged; the new master code occurs in none of them. The original Rize
pre-import dump and evidence are protected at
`/odoo/backups/vn-master-20261018-190232/`. Rize now has **119 employees and
109 contracts**; seven new contracts are Draft. Its zero payslip/run baseline is
unchanged. Configuration 4760 remains Draft and payroll assignments are unchanged.

Final post-install regression results: **89 tests on each of five databases,
445 total, zero failures/errors**. These include source-column rendering and
wire preservation, template/records import safety and the native dependent
count. The post-deployment Rize verification again passes **96 scenarios /
2,800 Salary and SHUI controls**, resolves all 70 saved records and creates no
additional people or contracts. An actual DATA-file parser check also proves
non-taxable S=12,345 and taxable AB=67,890 resolve separately without committing
any business change.

Chrome confirms the new Master v3 selector, **70/70 review roster**, 31 editable
monthly inputs, 106 records fields including the pinned name, protected-record
placement, Blood Type as Contract Text / Information only, the distinct Others
labels and wires, collapsed five constants, and absence of formula targets.
Both actual Chrome workbook downloads were inspected for all 70 rows, 22 retained
HR headings, blank monthly inputs and fully locked master cells. Uploading the
unchanged records download returns **0 changes, 3,801 blanks ignored,
3,619 unchanged values and 0 issues**; the review was cancelled. Browser warning
and error logs are empty after the final checks.

Private deliverables are in `outputs/rize-vn-master-v3-20261018/`: the monthly
workbook, separate records workbook and review HTML. The review identifies seven
missing salaries/settings, nine August probation classifications, **three** HC
salary differences (including the expatriate's 26,065 versus 26,071 exchange-rate
baseline), separate registered/detail dependent counts, and 22 skipped source
placeholder/nonnumeric cells. HC VND salary wins where supplied; no tax type or
missing salary is invented. Nine configuration warnings concern intentionally
terminal information outputs or totals hidden from payslips; there are zero
calculation errors.

No test PNG files were generated on disk. Test/deployment staging is removed
after protected receipts are retained. Unrelated and concurrent workspace files
are preserved. The final documentation-only commit is copied to the protected
deployment evidence; application hashes remain unchanged.
