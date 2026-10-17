# Vietnam HC payroll review configuration

Created **Rize Vietnam Payroll HC Oct 2026**, configuration **4639**, code
`RIZE_VIETNAM_HC_202610`, in **rize / Rize Farms** on 17 October 2026.
The configuration remains Draft with no population assigned. The existing
Vietnam configuration and employee, contract and payroll values were preserved.

The supplied `VN_HC_TemplateVietnam_updated_07Oct2026.xlsx` is a headcount and
compensation master, not a monthly payroll calculation file. Its VN sheet has
127 people (68 Active, 2 Notice Period, 57 Inactive). All 104 employee columns
have an explicit disposition: 64 mapped, with derived/reference and unrelated
HR fields documented separately. DA2 is an FX reference, not an employee column.
The headerless Sheet4 and name-only Dependent sheet are not treated as payroll
inputs. Country employee ID (E) is the proposed unique match key.

## Installed configuration

- 116 typed components: 93 inputs, 20 formulas and three 2026 parameters.
- 26 native employee/contract/bank mappings, 38 contract-text components and
  12 contract-amount components. The latter are declarations on the scheme;
  no actual employee contract advantage values were created or overwritten.
- Recurring salary maps to native contract wage. Tax mode, registered tax
  dependents, insurance participation/base/UI region cap and fixed allowances
  have distinct recurring settings. HC children counts do not establish tax
  eligibility. No nationality, job-title or source-status field silently
  determines tax residency, participation, allowances or payroll population.
- Resident gross-VND payroll uses the 2026 five-band PIT schedule. Nonresident,
  short-term, net-to-gross and special cases require reviewed Manual PIT.
  Insurance uses a reviewed base, separate participation flags, explicit UI
  region cap and the standard employer rates shown in the definition. Exceptions
  and payroll-month applicability remain business review items.
- Fixed salary/allowances are prorated by approved paid days over standard days.
  Actual overtime pay and approved exemptions are explicit monthly amounts.
  Unpaid days/weekend hours are labelled reference fields, not an additional
  deduction or automatic overtime calculation.
- Actual bonuses, 13th-month payments, advances, deductions and refunds are
  monthly inputs. Annual targets, estimates, CTC and leave balances do not
  become monthly pay. Typed groups and subtotal/detail treatment avoid counting
  both components and their totals in net pay.
- Records have source priority over spreadsheets. The saved monthly layout
  has four Time fields and 13 Monthly adjustments fields.

## Review and delivery

Of the 70 Active/Notice source IDs, 63 match existing employees and seven do not.
Fourteen lack source salary details. Three supplied salaries differ from current
open-contract wages. The review workbook contains 131 exception observations,
including these ten current-record comparisons, indexed by source row and ID.
Some observations concern the same person or missing prerequisite.

Delivered and attached to configuration 4639:

- `Vietnam_Configuration_Review.xlsx` (attachment 30900): review decisions,
  complete source dispositions, rule treatment, contract components, source
  exceptions, roster review and sources.
- `Vietnam_Monthly_Input_Template.xlsx` (attachment 30901): blank Time and
  Monthly adjustments schema plus instructions. It contains no sample payroll
  data. A populated server download follows approved records and population.

Before cutover, approve source identity/salary/date exceptions, reconcile seven
unmatched people, confirm the pay month and population, review recurring settings
and tax/exemption/bonus policies, then apply approved record changes through
Records Desk. Assign the new scheme and compare a parallel draft before activation.
No live payroll cutover or employee-data import was performed in this task.

## Deployment and validation

Functional commits: `2f113b452`, `02344611b`, `721296e2d`. Deployment scope was
configuration data in **rize only**, using the currently deployed ORM/Studio and
template APIs. No shared application-addon files, module upgrades or service
restart were required. Latest branch state was rechecked before installation
and artifact attachment; concurrent Library deployment work and unrelated local
file deletions were preserved. No tenant-specific configuration was copied into
another database.

- Dry run, atomic installation and deployed verification passed 30 stored
  scenarios, with 516 independent assertions. Coverage includes resident tax
  boundaries, caps, proration, bonuses, cash/noncash distinctions, reimbursements,
  advances, manual PIT and missing-input guards. Net and employer rollups reconcile.
- Zero formula-health errors and no value-kind/pay-role conflicts. One known
  warning is the terminal employer payroll-cost output not being used downstream
  or printed on a payslip. The 68 hints concern optional/unpopulated HR/reference
  input context in the fictional scenarios; they are not statutory approval.
- The generated monthly workbook parsed and transformed a fictional joined row
  with the configured identifiers and monthly amounts. Pay Run preflight
  recognized the employee ID column. No employee or payslip was imported.
- Chrome: opened the new Draft card, inspected typed components and sources,
  ran all 30 scenarios successfully (zero untested formulas), and verified the
  17-column template workspace and disabled pay-run guard. Its download produced
  the correct current-configuration workbook with exact headers and zero roster
  rows. The automation download event timed out, but the actual downloaded file
  was located, independently opened and verified, then removed. Browser error
  and warning logs were empty.
- Artifact Tool recalculation and visual review covered all ten delivered tabs.
  Review status updates from 11 to 10 pending when one decision is approved and
  returns to 11 when restored. Exported workbooks contain no unexpected errors.
  Excel desktop was not used. Monthly inputs have nonnegative numeric validation,
  frozen identities/headers and blank editable cells.
- Employee/contract/payslip/run/advantage counts were unchanged during installation
  and verification: **107 / 102 / 183 / 4 / 4234**.
- Test-generated PNGs/screenshots and temporary browser downloads were removed.
  Pre-existing product images and downloads were preserved.

Protected server evidence and pre-install Rize dump:
`Payobook19v2:/odoo/backups/rize-vn-hc-20261017/`.
