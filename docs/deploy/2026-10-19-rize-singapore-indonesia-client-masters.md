Rize Singapore and Indonesia client payroll masters, 19 October 2026
==================================================================

The owner requested consolidated employee/payroll sources, maintainable payroll
definitions, recurring monthly templates and August payroll reconciliation for
Singapore and Indonesia, following the India/Vietnam workflow. Client records
and configurations belong only to database `rize`, company Rize Farms. Shared
application includes corrections for saved numeric zero in monthly review,
cents on large payslip amounts, and genuine deduction refunds in summaries;
their rollout covers all five databases. Employee
data, source workbooks, calculation fixtures and produced XLSX files are
private artifacts outside this commit.

Sources
-------

* Singapore: `India Employee Details -rize.farm.xlsx`, Singapore worksheet,
  and `SGP PayrollInput.xlsx`, Payroll Input - August26. The other payroll tabs
  contain stale periods and some formula errors; they are reports, not inputs.
* Indonesia: `HC - Indonesia.xlsx`, ID worksheet, and
  `0826 Rize Farm Indonesia Payroll Report R1.xlsx`, 0826 Payroll Report, with
  Calculation, Premi Insurance, BPJS and TER schedules supplying calculation
  drivers and independent controls. Financial amounts in bank and accounting
  reports are outputs. Matched Bank Transfer beneficiary fields supply missing
  employee banking records; domestic routing codes remain separate from BIC.

`prepare_rize_sg_id_master.py` builds metadata-only definitions and private
record plans. The reusable Artifact Tool builder creates the consolidated
workbooks, with source inputs, calculations, statutory assumptions, August
comparisons and a field guide. `install_rize_sg_id_master.py` defaults to
rollback, asserts the Rize scope and uses normal mapping, Records Desk,
statutory publication, activation and roster APIs. It preserves all pre-existing
employee/contract/bank rows and all payroll transactions during configuration.

Design and source decisions
---------------------------

Singapore has two August payroll employees and four master profiles. Inactive
profiles remain archived with Draft contracts. The master supplies employee
IDs, names and joining dates; source payroll names/dates remain audit fields.
One conflicting join date does not change August pay. Salary is saved on the
contract; three Time fields and six monthly adjustments remain period-specific.
CPF, self-help and employer CPF are explicit reviewed monthly inputs rather
than inferred from nationality/name. The supplied net-before-proration method
is retained. SDL calculates on actual cash wages with its published rate, floor
and cap. Sum employee SDL before rounding the employer remittance down.

Indonesia retains all 292 bindings to the existing six published statutory
editions. New editions and effective-date refresh preserve historical rates.
The master repeats 11 IDs and collides with two existing foreign-country IDs;
unique `ID<local payroll number>` codes are canonical, satisfying Odoo's native
alphanumeric badge rule. Original HR IDs remain
reference fields. Of 122 payroll employees, 111 match by normalized name and
seven by unique national ID; four are payroll-only. Four master-only profiles
remain Draft for payroll pending review. Actual source contract ends and the
payroll leaver date are retained; later payroll requires a real renewal.
The HC banking columns are empty, so the August Bank Transfer worksheet
supplies all 122 bank names, accounts and holders. Its net-pay controls match
the payroll report exactly. Missing registration references can come from the
matched payroll NIK and August BPJS TK schedule. Ten HC/payroll national-ID
disagreements retain both values, with HC authoritative and a visible review
flag before statutory filing; national IDs are never payroll-matching aliases.

Indonesia has three Time fields and 23 monthly adjustments. Salary, annual
insurance premium, PTKP, coverage and tax mode are saved settings. A visible
signed regular-tax-allowance correction of -1 IDR reproduces the one August
rounding exception; future periods do not inherit it. Final-period tax uses
annual reconciliation with reviewed YTD inputs. For an allowance/net contract,
the final annual allowance is an explicit reviewed input instead of the old
unsupported-text result or a monthly approximation. Qualifying severance has
an explicit eligibility flag. Validation formulas expose days, PTKP, coverage,
annual review and severance issues for the payroll reviewer.

Validation before installation
------------------------------

The old Singapore definition matched both supplied August rows. The old
Indonesia definition matched 121 of 122 rows; the remaining row had a 1 IDR
allowance/gross/tax difference and unchanged net. With the visible source
rounding correction, the new calculation reproduces every source control.

Odoo rollback tests passed two Singapore scenarios and 122 Indonesia scenarios,
with 24 and 4,026 exact value comparisons respectively. The Artifact Tool
workbooks independently reproduced the same 4,050 comparisons and recalculated
net pay after a salary mutation; each mutation was restored. Formula error
scans were empty. All worksheets are rendered and visually reviewed. Native
monthly exports retain their issued receipts and read-only protection.

A pre-install Rize dump is stored on SSH `Payobook19v2` at
`/odoo/backups/rize-sg-id-client-master-20261019/rize-before.dump`.
The combined repository/application status was checked before installation:
all installed custom modules match the repository on payobook,
payobook_template, abm, p0clone and rize. The client configuration deployment
is Rize only; no other tenant receives client employee or payroll data.

Installed configurations and maintenance
----------------------------------------

Configuration 7095, `RIZE_SINGAPORE_CLIENT_MASTER_2026`, is active with 118
components: 101 inputs, 14 formulas and three SDL-linked parameters. Its old
configuration 3948 is archived. Records Desk RD00273 created the reviewed
values; RD00278 supplied four missing bank fields from the matched payroll.
The country/date assignment selects two employees in August and October.

Configuration 7096, `RIZE_INDONESIA_CLIENT_MASTER_2026`, is active with 459
components: 130 inputs, 37 formulas and 292 statutory-linked parameters.
Its old configuration 3943 is archived. Records Desk RD00276 applied 5,852
values. The August roster has 122 employees, September 120 and October 113;
four additional master profiles have Draft payroll contracts pending review.
This is a dated roster, so renewals require actual approved contract dates.

Users maintain identity, banking, recurring salary, coverage and tax mode in
Records Desk. Monthly Time and adjustments stay separate. Each new pay month
should start with a fresh download after selecting its scheme and period;
this includes current new hires, departures and record changes. October
deliverables have blank monthly amounts and no August correction carried over.
The consolidated workbooks document source fields, saved-record destinations,
monthly drivers, editable statutory assumptions and independent August checks.

New statutory editions must be published with their actual effective date and
reviewed through the refresh wizard before use. The source's 2026 wage caps,
floor and risk classification are preserved as parameters. Future statutory
changes are maintained as editions rather than edits to historical payroll.
Singapore CPF and self-help amounts remain reviewed monthly inputs. Indonesia
final-period annual gross-up needs an approved allowance and reviewed YTD;
the configuration refuses unsupported automatic annual assumptions.

The SDL method was cross-checked against the
[CPF calculation guidance](https://ask.gov.sg/cpf/questions/cmr2qsrwi00gl4a01ukqzp2z8).
Indonesia's regular TER and final-period annual distinction agrees with
[PMK 168/2023](https://jdih.kemenkeu.go.id/download/e60a82e0-b218-40f5-9d18-b924aa1e11ce/2023pmkeuangan168.pdf).
The contribution splits agree with the
[BPJS participant guidance](https://www.bpjsketenagakerjaan.go.id/penerima-upah.html);
its generic page still displays an older pension cap, so the August workbook's
2026 cap is retained in the dated edition rather than replacing it with that
undated web value.

Shared application correction and deployment
-------------------------------------------

Chrome review initially exposed 121 missing numeric inputs: zero-valued saved
contract components were exported as visually blank record cells. Payroll now
reads their numeric zero directly from the Records Desk reader, while a person
without a contract still has a missing value. This preserves required zero
coverage/reimbursement/tax-mode settings. Records Desk's presentation and all
business records are unchanged. Regression coverage exercises the native
workbook, required-input review, positive values and a missing contract.

Commit `25091ea23` deployed the latest combined application snapshot, comprising
149 custom modules and 4,907 files, to `/odoo/odoo-server/addons` on
`Payobook19v2`. All installed custom-module versions were checked and
`pb_payroll_templates` upgraded to `19.0.1.2.17` on `payobook`,
`payobook_template`, `abm`, `p0clone` and `rize`. Fresh full database dumps and
the previous addon snapshot are in
`/odoo/backups/rize-sg-id-code-20261019-224428`. Employee, contract, component,
bank, dependent, configuration and mapping hashes were preserved across the
upgrade; existing payroll counts and totals were unchanged. The service was
restarted and verified active. Client configurations and data remain Rize only.

The final counted-line audit found an older amount-size heuristic in
`om_hr_payroll`: line amounts of at least 1,000 were rounded to integers.
Singapore's source computation retained cents, while its stored employer-cost
lines lost S$0.25 each. Commit `afed3770d` removes that heuristic and retains
the fields' declared two-decimal precision for both amounts and totals.
Whole-unit rounding remains in the applicable payroll formulas/currency
calculation. Negative refunds, threshold amounts, large integer amounts and
subsequent total recomputation have regression coverage. The Singapore test
Draft is recomputed after deployment; existing payroll history is preserved.

During the long test, the normal presence scheduler refreshed employee
timestamps and one user's transient presence flag. Field-by-field comparisons
of the original and pre-upgrade dumps show no other employee-field changes.
The original Chrome baseline is retained. The independent audit compares all
employee columns with the pre-upgrade dump, permits only the three transient
presence/audit columns, and records the exact resulting snapshot hash. The
reconciliation still compares all contract, contract-component, bank and
dependent rows with the original baseline. Separately, generated native salary-rule links and evaluation cache
fields are audited only on the two new configurations. Formula expressions,
roles, source bindings and statutory parameters are not exempted from checks.

The next reconciliation caught a run/report aggregation issue: individual
Indonesia payslips matched, but a magnitude-only deduction summary turned
negative annual-tax refunds into charges. Commit `db04ba525` preserves the
existing mixed-sign legacy convention, and chooses signed deductions only
where all deduction lines are explicitly classified and their signed total
reconciles that payslip's gross to net exactly. The decision is per payslip,
so refunds and legacy insurance/advance conventions can share one run. The SQL
run totals and ORM report totals use the same rule. Existing regression cases
remain, with new refund and mixed-convention cases added. Only the two new
Draft runs have their stored aggregate figures refreshed.

Final deployed verification and handoff
--------------------------------------

The final combined snapshot (`db04ba525`) contains 149 custom modules and
4,909 files. Every file hash and installed custom-module version matches on
`payobook`, `payobook_template`, `abm`, `p0clone` and `rize`; `odoo-server` is
active. Runtime versions are `pb_payroll_templates` 19.0.1.2.17,
`om_hr_payroll` 19.0.1.8.4 and `pb_payruns` 19.0.3.0.7. The final pre-rollout
database/addon backups and deployment receipt are in
`/odoo/backups/rize-sg-id-code-20261019-231946`. The later verification-script
and documentation commit has identical application content.

The deployed monthly-template suite passed 87 tests per database (435 total).
The final precision, run-total and pay-band suites passed 36 tests per database
(180 total), retaining the legacy mixed-sign tests and adding refund coverage.
Seven Singapore and 15 Indonesia future scenarios passed in the live formula
engine. All 124 stored August scenarios pass, with 4,050 exact expected-value
comparisons. The produced workbooks independently reproduce those controls.

Chrome downloaded each country's native template, uploaded the filled August
file, reviewed 18 Singapore and 3,100 Indonesia monthly inputs with zero
unresolved inputs, and computed the actual Drafts. Singapore was recomputed
in Chrome after the cents fix. Final full-run views confirm all four financial
totals below. Both one-time import batches have zero errors and created no
employees, contracts or bank records. Report totals and counted payslip lines
also match for every employee, including Indonesia's negative tax refunds.

| August 2026 | Singapore (SGD) | Indonesia (IDR) |
|---|---:|---:|
| Configuration | 7095 | 7096 |
| Draft run | 2019 | 2040 |
| Import batch | 2261 | 2283 |
| Employees | 2 | 122 |
| Gross | 46,252.00 | 1,544,551,404 |
| Deductions | 30.00 | 342,457,378 |
| Net | 46,222.00 | 1,202,094,026 |
| Income tax | 0.00 | 157,550,783 |
| Employer cost | 46,274.50 | 1,605,974,382 |

Runs are clearly named `Rize <country> · August 2026 TEST · Client comparison`
and remain Draft. Approval, posting, payment and payslip delivery were not
performed. Chrome's exception review showed workforce-close notes (six
unclosed weeks with zero open flags), repeated across Indonesia divisions;
these are informational and do not block calculation. No formula errors remain.
The 63 pre-existing payslips and pre-existing run rows are unchanged.

The original four source workbooks retain their original SHA-256 hashes.
Native monthly receipts, comments, styles, protection and read-only employee
records are preserved byte-for-byte; only reviewed Time/adjustment cells were
authored in the August files. October contains no saved or carried monthly
inputs. Six private XLSX deliverables are in
`outputs/rize-sg-id-payroll-20261019`: one consolidated configuration/master,
one blank October template and one filled August TEST template per country.

All 24 PNG previews generated by this task and both duplicate browser
downloads were removed. No screenshots are retained. Pre-existing product
images, downloads and concurrent-session artifacts are preserved. Private
calculation evidence remains outside Git. Before future payroll/filing, review
the ten flagged national-ID disagreements, the four held master-only profiles,
and real contract renewals. Reissue the monthly template after record updates.
