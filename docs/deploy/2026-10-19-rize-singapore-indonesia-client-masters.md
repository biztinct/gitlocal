Rize Singapore and Indonesia client payroll masters, 19 October 2026
==================================================================

The owner requested consolidated employee/payroll sources, maintainable payroll
definitions, recurring monthly templates and August payroll reconciliation for
Singapore and Indonesia, following the India/Vietnam workflow. Client records
and configurations belong only to database `rize`, company Rize Farms. Shared
application code is unchanged. Employee data, source workbooks, calculation
fixtures and produced XLSX files are private artifacts outside this commit.

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

Installation, deployed checks, Chrome payroll runs and artifact cleanup are
recorded below after completion.
