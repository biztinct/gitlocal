# Rize Indonesia installation and monthly input workbook

Rize Farms, database `rize`, configuration **3943**,
`RIZE_INDONESIA_AUGUST_2026`, **Rize Indonesia · August 2026**. Country
Indonesia, currency IDR, first period 1 August 2026. The setup is finished;
the configuration remains draft, and its six statutory source editions remain
draft pending the normal publication and payroll activation approvals.

## Installed configuration

The formula workbook was imported through Chrome's standard workbook wizard:
Payroll, header row 29, Employee ID as primary key. Tax Map was consumed as
metadata. There are 367 components: 39 inputs, 36 formulas and 292 mapped
constants. The six August 2026 editions are IDPARAMS, IDTERA, IDTERB, IDTERC,
IDANNUAL and IDSEVERANCE; all mapped values align.

`tools/configure_rize_indonesia_inputs.py` records the treatment setup using
the normal application methods. All 367 treatments have explicit roles, groups
and value kinds, with no unresolved treatment decisions or type conflicts.
The setup also specifies payslip visibility and number formats.

- Total income and qualifying severance count as earnings. Earnings detail
  lines already contained in total income carry the Subtotal flag.
- Total deduction counts once; its individual deduction lines carry Subtotal.
- Take home pay is the net-pay component.
- Employer cost is the employer total. The JHT and JP company contributions
  are detail within that total.
- Salary drivers, controls, prior YTD amounts, tax bases, calculation helpers
  and statutory values are information only. In particular, prior PPh21 and
  severance tax withheld are not counted as current earnings.
- Names are text, employee/cost-centre codes retain their literal identity,
  join/leaving dates are dates, days are quantities, controls are integers and
  tax/contribution rates are percentages.

The payable-tax component retains column AN and its displayed name, with code
`PIT` assigned through the standard rename API. This connects the application's
income-tax headline and test-coverage check. The source-mapping task is marked
configured through its coverage-checked API (39 of 39 inputs connected).

The six fictional workbook cases are installed as Template example 1–6.
The guided setup's generic BASIC/STDDAYS placeholder is retained archived.
No employees or payslips were created by installation or testing.

## Client workbook

`outputs/rize-monthly-20261014/Rize_Indonesia_Monthly_Inputs.xlsx` contains:

- Payroll: the 39 non-formula employee input columns, header row 1, with 300
  empty prepared rows, frozen headings/identity columns and input validation.
- Instructions: monthly use and definitions for all 39 fields.

It contains no formulas, statutory tables, example employees or Tax Map.
The workbook is also attached to configuration 3943 as attachment 27194.
Each input has an explicit `Payroll|<heading>` spreadsheet source binding.
The compact input file therefore maps by heading even though its column
letters differ from the calculation workbook.

The client fills a copy each month and returns it to the payroll operator.
The operator selects the pay period and the Indonesia configuration in Pay
Run, loads the input file, checks employee matches and calculations, and follows
the payroll approval workflow. Employee IDs must match the registered employees.
Production activation and employee onboarding follow the normal workflow.
The guided calendar still carries the application's opening defaults: inputs
close on day 20 and payday is the last working day. Confirm these with the
client before live use. The workbook's paid-day denominator is supplied per row
and is not inferred from that cutoff.

The original August limitation remains: final tax period = 1 with full monthly
net-to-gross mode = 2 requires an annual gross-up review. The template exposes
that case explicitly. Qualifying severance also needs eligibility confirmation
before a first real payment; the client August source had no nonzero control.

## Fixed side-panel controls

`pb_formula_studio` 19.0.1.201.12 keeps these controls together in sticky
containers within the existing panel scrollers:

- Components title/actions, Payroll/Everything lens and All/Related filter.
- Live preview title, sample selector, real-person selector and pin button.

The existing scrolling containers and arrow listeners are preserved. The
headers also work in the grid's slide-in drawers and the panels can still
collapse/expand.

## Deployment and verification

Main implementation commit `d75055c48`; installation refinements through
`08cd694b5`. Upgraded pb_formula_studio on **payobook, rize,
payobook_template, abm and p0clone** using the shared addons on SSH
`Payobook19v2`. Backups of all five databases and cron states are at
`/odoo/backups/rize-inputs-20261014`. The original cron states were restored and
the service is active. Concurrent biz_mail_debrand work was preserved and
excluded from these commits. The combined working tree's 4,279 custom files
match the shared server; `tools/deploy_status.py` reports nothing pending.

- XML and script syntax checks passed; the deployed assets compiled.
- Chrome completed the workbook import into Rize and verified the installed
  schema, component treatment, sample results and completed setup.
- Chrome scrolled Components by 1,868 px and Live preview by 2,802 px. Both
  header tops remained at 160.5 px. The sample selector changed to example 2
  while preview values remained scrolled; its take-home pay is Rp90,000,000.
- Both grid drawers retained their headers at the same position with the
  scroll offsets preserved.
- The deployed monthly parser read all six fictional rows from a disposable
  copy of the compact input workbook. All 216 calculated outputs match the
  formula workbook's cached controls to 0.000001 IDR. Employee ID `000001`
  remains literal. Earnings less deductions equals net pay exactly once, and
  employer cost equals its selected total, in every case.
- Six stored sample checks pass, with no failures or pending checks. The
  normal guided check and finish methods were used, preserving their gates.
- All 292 statutory bindings align. Component treatment has zero unresolved
  decisions and zero type conflicts.
- Health has **0 errors, 10 warnings and 18 hints**. The warnings are the
  current health screen's name-based hidden-total notices for four gross-up
  helpers, the unused residual helper and five final unlimited-band upper
  sentinels. These helpers are deliberately information only and hidden from
  payslips; the sentinel values remain explicitly mapped for edition refresh.
  The installation checker refuses any other warning. Hints cover optional
  profile fields and shared formula patterns. These advisories do not alter
  the numeric results or represent unsettled component treatment.

The workbook was visually checked and its saved file verified: 39 headings,
blank data rows, no formulas, nine validation rules and PayrollHeader at
`Payroll!A1:AM1`. Test PNGs and transient filled input workbooks were removed;
the only delivered artifact is the blank monthly workbook.
