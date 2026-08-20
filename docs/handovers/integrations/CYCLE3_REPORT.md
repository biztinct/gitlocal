# Integrations Cycle 3 — implementation report (the Zoho People catalog)

> Written incrementally during the cycle, committed at milestones. Read with
> `docs/handovers/integrations/CYCLE3_ZOHO_CATALOG.md` (the spec) open.

## Commits

| # | hash | what |
|---|---|---|
| 1 | `5479e66c` | feat(pb_hr_payroll_formula): the Zoho People feed catalog — the ABM inventory becomes data |
| 2 | `c9a5f773` | feat(pb_hr_payroll_formula): transformation-rule templates + instantiation |
| 3 | `b7436139` | feat(pb_hr_payroll_formula): the legacy field map joins the vendor templates |

Nothing pushed. `.claude/settings.json`, `thaco/` and `ABM/` never staged.
`pb_hr_payroll_formula` **19.0.1.50.0 → 19.0.1.51.0**.

## `_execute_for_records` — the namespace findings

The handover asked for this first, and it changed two of the eight shipped rows.

`hr.api.transformation.rule._execute_for_records` (`api_transformation_rule.py`,
now :210 after this cycle's constants block) groups store records by
`employee_external_id`, then loads that employee's OTHER data types with a
`search` restricted to `state in ('extracted','consumed')`, and calls
`_execute_single` per rule. `_execute_single` (:281) is where the vocabulary is
decided:

```python
match = safe_eval(self.filter_expression, {
    'rec': rec_data,          # the record's extracted_data dict
    'env': self.env,
    'datetime': datetime,
    'date': date,
})
```

Three consequences, all load-bearing:

1. **It is `rec`, not `record`.** The handover's inventory table wrote
   `record.get('OT_Type')`. Shipped as written, every row would raise
   `NameError`, and the very next line is `except Exception: pass` (:289) —
   so every record would be silently dropped from the filter and the whole feed
   would sum to **zero, with nothing in the log**. Every shipped expression uses
   `rec`, the data file's header says why, and `test_03b` asserts
   `'record.get(' not in filter_expression` for all six overtime rows.
2. **`source_records` are FLAT `extracted_data` dicts, one per store row.** So
   `rule_type=count` counts STORE ROWS. It cannot see inside a row.
3. **`_execute_python` gets `records`** — the already-filtered list of those
   dicts — plus `employee_data`, `all_records`, `period_start`/`period_end`,
   `env`, `employee`, and a pre-seeded `result`.

### How DEPCOUNT was expressed → `rule_type=python`

Consequence 2 decides it. Zoho does not return dependants as records; it returns
them as a **tabular section inside the employee's own record** —
`employee_data["tabularSections"]["Dependent and Dependent Health Insurance"]`
(legacy `hr_zoho_staging.py:367-373`). One store row holds the whole list, so a
`count` over employee records would answer **1 for an employee with four
dependants** and 0 for one with none: a wrong number that looks like a right
one. The handover anticipated this ("if impossible declaratively, ship as
rule_type=python with the code in the data file") and that is what shipped:

```python
deps = 0
for r in records:
    rows = (r.get('tabularSections') or {}).get('Dependent and Dependent Health Insurance') or []
    for d in rows:
        if d.get('Dependent_PIT_Number'):
            deps = deps + 1
result = deps
```

`test_06b` proves it against a three-dependant payload where one has no PIT
number, and asserts `len(emp) == 1` beside the answer `2` — which is the
assertion that justifies the python row rather than merely describing it.

### How WORKEDHRS was expressed → `rule_type=python`

The attendance summary returns the two halves of this number **in two different
units in one payload**: `totalWorkedHours` is an integer count of SECONDS
despite its name, and `paidLeaveHours` is an `"H:MM"` string. No
aggregate-plus-transform ladder can add those, because the ladder operates on
one already-numeric value. The shipped code reproduces the legacy arithmetic
`(paidLeaveSeconds + totalWorkedHours) / 3600` (`hr_zoho_staging.py:559-577`):

```python
total = 0.0
for r in records:
    worked = str(r.get('totalWorkedHours') or 0).strip()
    secs = float(worked) if worked.replace('.', '', 1).isdigit() else 0.0
    parts = str(r.get('paidLeaveHours') or '').split(':')
    if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
        secs = secs + int(parts[0].strip()) * 3600 + int(parts[1].strip()) * 60
    total = total + secs / 3600.0
result = total
```

Both parses are guarded by `isdigit` rather than by `try/except`. That is not
style: `safe_eval` runs this through a whitelisted-opcode check, and Python
3.11+ compiles exception handling to opcodes (`PUSH_EXC_INFO`, `CHECK_EXC_MATCH`,
`RERAISE`) that the whitelist was not written for. A guard that cannot raise
needs no handler. `test_06c` proves `28800s + '2:30' == 10.5`; `test_06d` feeds
it `'n/a'` and `'not-a-time'` and asserts `0.0` rather than a traceback.

### The dropped date filter

The legacy re-parsed each overtime record's `OT_Date` and re-checked it against
the same window it had just asked the API for (`:497-557`). Dropped, as the
handover directed, and the reasoning is now in the data file: the endpoint is
date-scoped by `fromDate`/`toDate`, so the second check could only ever remove
records Zoho had already excluded — while silently dropping any record whose
date string did not parse as `dd-MM-yyyy`. `test_03b` asserts `OT_Date` appears
in no shipped filter.

## The final target-code list (substring-audited)

33 codes, `test_05` auditing the shipped XML (not the table — a row that failed
to load must not be able to make the audit pass by being absent). **No code is a
substring of any other; all are UPPERCASE alphanumeric.**

| | codes |
|---|---|
| pre-existing (15) | `EMPID` `FULLNAME` `EMAIL` `DEPT` `JOBTITLE` `JOINDATE` `BASIC` `ALLOWFIX` `DEPS` `WDAYS` `OTHOURS` `LEAVEDAYS` `BANKACC` `TAXID` `BONUS` |
| new this cycle (18) | `SURNAME` `NAMEEN` `NAMEVN` `EMPSTATUS` `EMPKIND` `WORKSITE` `GENDERCODE` `BIRTHDATE` `MOBILENO` `PANCODE` `PITCODE` `UANCODE` `AADHAARNO` `BANKTITLE` `VNDACCOUNT` `INSBOOKNO` `ZOHOREF` + (`GIVENNAME` dropped — see deviations) |

**The handover's own two suggestions fail the law.** It warned that `FULLNAMEVN`
is illegal beside `FULLNAME` and offered `VNFULLNAME` as the fix — but
`VNFULLNAME` contains `FULLNAME` just as surely (`'FULLNAME' in 'VNFULLNAME'` is
`True`). The same applies to `ENFULLNAME`. Shipped as `NAMEEN` / `NAMEVN`, which
audit clean and read better in a formula.

`VNBANKACC` was already flagged by the handover; shipped as `VNDACCOUNT`.

## The `endpoint_code` decision table (the pre-existing rows)

Every stamp is evidence-backed; three rows are deliberately left blank.

| xml id | source_path | endpoint_code | why |
|---|---|---|---|
| `mt_zoho_empid` | `EmployeeID` | `zohoemployees` | read off the employee form, staging :379 |
| `mt_zoho_name` | `FirstName` | `zohoemployees` | staging :376 |
| `mt_zoho_email` | `EmailID` | `zohoemployees` | staging :378 |
| `mt_zoho_dept` | `Department` | `zohoemployees` | staging :380 |
| `mt_zoho_job` | `Designation` | `zohoemployees` | staging :383 |
| `mt_zoho_join` | `Dateofjoining` | `zohoemployees` | staging :388 |
| `mt_zoho_deps` | `No_of_Dependents` | `zohoemployees` | the legacy dependant count comes from THIS form's tabular section (:367-373) — same feed as DEPCOUNT |
| `mt_zoho_bank` | `Bank_Account_No` | `zohoemployees` | the real account (`Bank_Account_Number_VND`) is an employee-form field |
| `mt_zoho_tax` | `PAN_or_TaxID` | `zohoemployees` | `Pan_Number` / `PIT_Number` are employee-form fields |
| `mt_zoho_basic` | `Salary` | `zohosalary` | the row's own note says "payroll form"; P_Salary is that form (zoho_connector :411) |
| `mt_zoho_allow` | `Other_Allowance` | `zohosalary` | same form |
| `mt_zoho_wdays` | `Total_working_days` | `zohoattsummary` | working-day totals come from the summary report (`expectedWorkingHours`, staging :559) |
| `mt_zoho_ot` | `Overtime_hours` | `zohoovertime` | the row's note says "may come via the Attendance API — verify"; the legacy answer is the overtime_request form, which is the feed named |
| `mt_zoho_leave` | `LeaveTaken` | `zoholeave` | the leave tracker is the only feed that carries leave |
| `mt_dbx_*` (8 rows) | employee-directory fields | `darwinemployees` | `masterapi/employeedirectory` is documented as employee master data (darwin_connector :48) |
| `mt_dbx_basic`, `mt_dbx_allow` | `basic`, `special_allowance` | `darwincompensation` | darwin_connector :49 |
| `mt_dbx_ot` | `overtime_hours` | *(blank)* | neither documented Darwinbox path produces it |
| `mt_dbx_wdays` | `working_days` | *(blank)* | as above |
| `mt_dbx_deps` | `dependents_count` | *(blank)* | the row's note names a "dependents API" the connector does not have |

All 18 new Zoho rows carry `zohoemployees`: they are, by construction, the
employee-form fields.

## W13.1 — the frozen rows, and how they were unfrozen

`data/mapping_templates.xml` is `noupdate="1"`, so the 27 pre-existing vendor
rows are frozen in **every database that has already loaded them** — on this box
that is `payobook`, `acme`, `abm` and `payobook_template`. Adding
`<field name="endpoint_code">` to those records is correct for a fresh install
and a **complete no-op everywhere else**. Without a second path, a fresh install
would group the Zoho fields under "Employees" while every real database grouped
them under "Unassigned", and the difference would be invisible in the repo.

`migrations/19.0.1.51.0/post-stamp_endpoint_codes.py` closes it: stamps by XML
ID (so a cloned or foreign row is untouched), only where `endpoint_code` is
still empty (so a tenant that has already answered keeps their answer), and its
table is compared against the shipped XML by `test_08` rather than trusted.

*(deploy, test evidence and live validation appended below as each lands)*
