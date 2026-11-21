# Singapore client configuration and monthly inputs

Installed on **payobook.com**, database **payobook**, configuration **613**,
`RIZE_SINGAPORE_AUGUST_2026_I`, **Rize Singapore · August 2026 (import review)**.
The review company is Payobook Vietnam JSC, matching the earlier Indonesia
demo review. The configuration is Singapore, currency SGD, effective 1 August
2026, and remains **draft**. Guided setup is finished. The RIZESGSDL statutory
edition remains draft and its three parameter bindings align.

The user explicitly requested payobook testing first and approval before
deployment to **rize, payobook_template, abm and p0clone**. Those four databases
have not received this configuration. No shared application module was changed
or upgraded for this task. Existing concurrent mail, portal and import styling
work was preserved and excluded from these commits.

## Workbooks

- `outputs/sg-payroll-20261014/Rize_Singapore_Payroll_Configuration_Aug2026.xlsx`
  imports Payroll at header row 12, data from row 13, with Employee ID as the
  primary key. Tax Map supplies statutory metadata and must not be selected as
  an employee sheet. There are 38 employee columns: 25 inputs and 13 formulas,
  plus three mapped SDL constants, for 41 components. Eight fictional examples
  replace client identities and salaries after numerical reconciliation.
- `outputs/sg-payroll-20261014/Rize_Singapore_Monthly_Inputs.xlsx` has Payroll
  header row 1, 25 input columns, 300 blank prepared rows and 11 validation
  rules. Instructions define all fields and the monthly workflow. It has no
  formulas, statutory tables, example employees or calculated output columns.

SHA-256:

```
configuration 94ce15333aff042cb26417ac49c2ae240bcfc45ac2eb35ad84be49156e4c9240
monthly       45d35b020dab37a73e1d7d79892a9777f6d6a050ae6dc68bd7e042aa90419a66
```

Both are attached to configuration 613, attachment IDs **219189** and
**219190**, with contents verified byte for byte against the final files.

## Calculation and treatment

The main `Payroll Input - August26` sheet in `SGP PayrollInput.xlsx` is the
numerical baseline. The setup pack's compensation, earning/deduction codes,
statutory definitions and payslip mapping informed classification. Historical
tabs were inventoried only; one contains 13 broken references and another
carries stale period labels. No approval matrix was imported.

The user confirmed both decisions during this session:

- CPF and self-help contributions remain reviewed monthly inputs.
- Preserve the client's net-before-proration calculation:
  `ROUND((basic - employee CPF - self-help) / standard days * active days, 0)`.
  Medical allowance and other income are added afterwards.

The misleading USD source heading was replaced with Monthly basic salary SGD;
the setup pack confirms the actual amounts are SGD and no FX conversion applies.
Standard working days are entered for each month, rather than carrying August's
20 days into future months.

SDL follows the CPF Board's published 0.25% rate, S$2 minimum and S$11.25 maximum
per employee. Individual cost retains the exact calculation. The employer
remittance is the sum of employee SDL rounded down to whole dollars, documented
in the instructions. The source reference is retained in a native note at C4.
https://www.cpf.gov.sg/employer/employer-obligations/skills-development-levy

All 41 treatments are explicit and protected from automatic reclassification:

- Cash earnings (`GROSS`, AJ) counts once. Prorated gross salary, medical
  allowance and other income are earnings detail with Subtotal selected.
- Deductions applied to pay (`EEDED`, AI) counts once and preserves the client's
  proration and whole-dollar rounding. The full-month CPF/SHG inputs are
  information, so they cannot be deducted twice.
- Net take-home pay (`NET`, AA) is the net-pay component.
- Employer cost (`ERCOST`, AK) counts once. Employer CPF and SDL are detail.
- Annual/full-month references, salary/day drivers, bank data and SDL parameters
  are information. `PIT`, AL, explicitly holds zero for this ordinary monthly
  template; this does not implement IR21 tax-clearance withholding.
- IDs, bank accounts and SWIFT codes are reference codes; names/status/fund
  labels are text; dates are dates; days are quantities; SDL rate is a percentage.

Every input binds by `Payroll|<heading>`, so the compact monthly file maps
correctly despite different column letters. Native mappings were added for
employee ID, name, job title, birthday and contract start date, plus all four
bank-account slots. No employee, contract, bank account or payslip was created
or updated during testing. Samples contain fictional data only.

The monthly instructions recommend **This run only** for period values and
**Update Payobook** for approved record changes. Employees must already exist
and match the registered Employee IDs. Publication/activation and population
assignment precede live monthly use. Bonus/AW CPF, automated citizen/PR rates,
FnF/leave policy, IR21, filing, benefits and bank exports need separate setup.

## Verification

- The application workbook import was completed through Chrome: upload,
  worksheet/column selection, resolution, execution and category review.
  Payroll header row 12 and the leading-zero source values were detected.
- The initial import accepted `ISNUMBER`, but the deployed engine does not
  evaluate it. The final files use supported `IF(standard days > 0, …)` guards;
  the imported formulas were updated through `save_formula` and verified.
- Eight stored scenarios pass, with zero failures or pending checks. Chrome
  reran the checks and showed all eight passing and 13 of 13 calculations covered.
- The deployed monthly parser read eight fictional rows. All **104 calculated
  values** match the exported workbook to 0.0000001 SGD. The two anonymous
  client controls add **16 exact numerical comparisons**.
- Changed salary recalculates net pay and SDL. A zero working-day denominator
  exposes `Working days required` in net, earnings and cost instead of a numeric
  zero. Employee ID `000001` and bank account `0000123456` remain literal in
  parsed input and evaluated values.
- Pay Run's preflight connects all **25 of 25** inputs, with no missing
  components and employee identity found. Its headline reads 30 columns because
  it also counts the five headings on Instructions. Only Payroll supplies the
  eight employee rows. No live pay run was created; the scheme remains draft.
- Chrome inspected the installed component treatment, including the reviewed
  roles, subtotal flags and reference-code/rate types. Treatment has **zero
  unresolved decisions and zero type conflicts**. All three SDL bindings align.
- Health: **0 errors, 6 warnings, 17 hints**. Warnings are the hidden full-month
  net salary and annual CTC references, unused annual CTC references, and the
  zero PIT reporting line. The installation checker refuses other warnings.
- The final files were rendered and visually checked. Saved-file checks confirm
  blank monthly data, validation rules, native source note, literal identifiers
  and supported formulas. The current compact Studio preview still applies its
  older numeric display formatting to identifiers and rounds currency on cards;
  parsed/evaluated data and component treatment preserve the declared values.

Backup: `/odoo/backups/singapore-payroll-20261014/payobook-before-import.dump`
on SSH **Payobook19v2**. The service remained active. Final deployment evidence
and workbook copies are retained beside the backup; private numerical controls
and other transient setup files were removed. All test PNGs were removed from
the task output directory. Pre-existing assets and client files were untouched.
