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

## Deploy

| window | unit | EXIT | notes |
|---|---|---|---|
| main upgrade | `i3up` | **0** | 209 modules, registry loaded 45.9s, zero ERROR/CRITICAL; service restarted by the unit |
| scoped tests (1st) | `i3test` | **1** | 4 failed, 3 errors — two real bugs, below |
| fix redeploy + tests (2nd) | `i3test2` | **0** | **0 failed, 0 error(s) of 109 tests** |

Both test windows ran with the **real service UP** and their own `--http-port`
(8273) and their own `--logfile` — W131 and W132 applied from the start rather
than after the incident. Checked afterwards: `ss -lntp` shows 8069 owned by the
service pid alone, and no `odoo-bin` besides it.

The upgrade window was a single W136 script: stop → poll for zero `odoo-bin`
(clear after 2 polls) → `-u pb_hr_payroll_formula,pb_integrations
--stop-after-init --http-port=8272 --logfile=/tmp/i3up.log` → `echo EXIT=$?` →
`service odoo-server start`, launched with `systemd-run --no-block` (W133) and
polled from outside.

W118 version-diff over the **reverse-dependency closure** of the two changed
modules (56 modules, 54 installed): the only drift was the two this cycle
touched. No `pb_import_kit`-shaped straggler this time.

Live versions now equal to the repo: `pb_hr_payroll_formula` **19.0.1.51.0**,
`pb_integrations` **19.0.1.5.0**. Health after the window: `payobook/web/login`
**200**, `acme.payobook.com/web/login` **200**, `payobook.com/` **200**.

### The migration ran

```
INFO payobook odoo.upgrade.pb_hr_payroll_formula.19.0.1.51.0.post-stamp_endpoint_codes:
IG-C3: stamped endpoint_code on 24 of 24 vendor mapping template row(s)
```

### The catalogue landed (asserted against the DATABASE, W13.1)

```
 endpoint_tmpl    | zoho               |     7
 endpoint_tmpl    | darwin             |     2
 rule_tmpl        | zoho               |     8
 map_tmpl_stamped | zohoemployees      |    26     (9 pre-existing + 17 new)
 map_tmpl_stamped | zohosalary         |     2
 map_tmpl_stamped | zohoattsummary     |     1
 map_tmpl_stamped | zohoovertime       |     1
 map_tmpl_stamped | zoholeave          |     1
 map_tmpl_stamped | darwinemployees    |     8
 map_tmpl_stamped | darwincompensation |     2
 map_tmpl_stamped | (blank)            |    41     (workday 13, sap 13, oracle 12, darwin 3)
```

## Two bugs the first test run found

### 1. Every python transformation rule has been returning its default (`efbb64b5`)

`_execute_python` called `safe_eval(..., mode='exec', nocopy=True)`. **Odoo 19
removed `nocopy`** — the signature is now
`safe_eval(expr, /, context=None, *, mode="eval", filename=None)`, and its
docstring makes the old opt-in the only behaviour ("This dict will be mutated
with any variables created during evaluation"). The call therefore raised
`TypeError` before the expression ran, on every `rule_type='python'` rule, since
the port.

Nothing surfaced it because `_execute_for_records` wraps each rule in
`except Exception` and writes `default_value` instead: a python rule did not
fail loudly, it quietly returned 0, the payroll used the 0, and the only trace
was one WARNING per employee per rule in a log nobody reads during a pull.

It was found because this cycle ships the first python rules the codebase has
had, and the first ones anybody asserted an ANSWER for — DEPCOUNT returned 0.0
where the answer is 2, WORKEDHRS returned 0.0 where the answer is 10.5. Fixed
by deleting the argument; four tests now stand on it.

### 2. Cycle 1's three catalogue tests assumed an empty catalogue (same commit)

`test_01`, `test_01b` and `test_05b` were written when
`hr.integration.endpoint.template` had no rows, so they could say "one template
in, one feed out" and count the whole `endpoint_ids` o2m. With seven shipped
Zoho feeds that count is 8 — and the failure was the tests measuring the DATA
rather than the mechanism. Each now names the row it created.

`test_01b` was **strengthened, not loosened**: it deactivates the whole
catalogue rather than one row, because proving a deactivated code is still taken
for eight rows beats proving it for one. `test_05b`'s fix matters most —
`assertEqual(mapping.endpoint_id, conn.endpoint_ids)` against an eight-record
set would have passed for any of the eight.

## Test suites (handover test 8)

One scoped run, service up, `-u pb_hr_payroll_formula,pb_integrations,
pb_formula_studio,pb_settings,pb_import_advanced` with the matching
`--test-tags`:

```
pb_formula_studio:      16 tests  1.56s   988 queries
pb_hr_payroll_formula:  42 tests  3.67s  1598 queries
pb_import_advanced:     13 tests  1.51s  1045 queries
pb_integrations:        41 tests  0.33s   276 queries
pb_settings:            25 tests  0.09s   153 queries
0 failed, 0 error(s) of 109 tests when loading database 'payobook'
```

Cycle 2's baseline on the same scoping was 85 tests; this cycle adds 24
(`test_zoho_catalog.py` 14, `test_transform_preview.py` 4, and the rest from the
studio/endpoint suites). The two known pre-existing failures (`pb_timeoff`
test_05, `pb_today` hex) are outside this scoping and did not run — not fixed,
per the non-goal.

### Numbered tests 1–7 — where each is gated

| # | what | gate | evidence |
|---|---|---|---|
| 1 | 7 endpoints, right ABM flags, idempotent re-run | `test_01`, `test_01b` | code/data_type/path/flag asserted per feed; re-sync `{created: 0, skipped: 7}`, a renamed feed keeps its name |
| 2 | template apply stamps `endpoint_id`; existing wire never overwritten | `test_02`, `test_02b` | all 23 legacy paths land on `zohoemployees`; a pre-drawn `EmployeeID` wire keeps its feed, label and transform, and no duplicate appears |
| 3 | rules create-only by `output_key` | `test_03`, `test_03b` | 8 created, re-apply `{rules_created: 0, rules_skipped: 8}`; a retuned + deactivated rule survives |
| 4 | coverage battery | `test_04`, `test_04b` | 23 legacy source_paths present as a set; the 8 non-legacy rows pinned too, so drift in either direction fails |
| 5 | substring-law audit | `test_05` | 32 unique codes read from the shipped XML, 0 violations, all UPPERCASE alnum |
| 6 | expressions execute | `test_06`, `06b`, `06c`, `06d`, `06e` | OTHRS150 = 4.0 (approved 150% only), OTHRS200 = 3.0, OTHRS300 = 0.0; DEPCOUNT = 2 of 3 dependants; WORKEDHRS 28800s + '2:30' = **10.5**; empty and malformed payloads = 0.0, not a traceback; `_execute_for_records` writes the keys to `computed_data` |
| 7 | Darwin parity | `test_07` | 2 feeds, POST, right data types; `employee_no`→`darwinemployees`, `basic`→`darwincompensation`; the 3 unevidenced rows assert **no** feed |
| — | migration ↔ XML agreement | `test_08`, `test_08b` | the two lists of the same fact compared, and the live rows re-read |
| — | count honesty | `test_07` (C1 file) | `feeds_known` asserted false in the degraded state and true outside it |
| — | preview hygiene | `test_transform_preview.py` | 4 cases incl. the handler-order regression |

## WP-5 — the live demo touch (JSON-RPC, `payobook`)

Ran as the temporary validator (uid 2095) against the demo **"Zoho People"**
connector, id **161**:

```
BEFORE  endpoints=3 mappings=8 rules=0
catalog sync   -> {'created': 7, 'skipped': 3}
template apply -> {'applied': 0, 'suggested': 31, 'total': 31,
                   'rules_created': 8, 'rules_skipped': 0}
AFTER   endpoints=10 mappings=39 rules=8

  FEED zohoemployees    Employees              employee   legacy=True   maps=26  forms/P_Employee/records
  FEED zohoattsummary   Attendance summary     attendance legacy=True   maps=1   attendance/getSummaryReport
  FEED zohoovertime     Overtime requests      custom     legacy=True   maps=1   forms/overtime_request/getRecords
  FEED zohosalary       Salary form            salary     legacy=False  maps=2   forms/P_Salary/records
  FEED zoholeave        Leave records          leave      legacy=False  maps=1   api/v2/leavetracker/leaves/records
  FEED zohoattdaily     Attendance by date     attendance legacy=False  maps=0   attendance/getAttendanceByDate
  FEED zohotimesheet    Timesheets             custom     legacy=False  maps=0   timetracker/gettimesheet
  FEED employee/dependent/leave  (the three the demo had DERIVED from its store rows)
  RULES: DEPCOUNT(python) OTHRS150/200/210/270/300/390(sum) WORKEDHRS(python)
  mappings with NO feed: 8
```

Three things worth reading twice:

* **the catalogue sync skipped 3 and created 7.** The three skips are the
  generic feeds pb_demo derived from the connector's own store rows in Cycle 1
  (`employee`, `dependent`, `leave`); they keep their codes and their rows,
  exactly as create-only promises. The demo world's history is not overwritten
  by the vendor's catalogue arriving after it;
* **`applied: 0, suggested: 31`.** Every wire is `suggested`, because the
  config linked to this connector has no input codes matching the Zoho target
  codes. That is D114.2 working: a template guess is never load-bearing until
  the batch test confirms it against a real payload;
* **8 mappings with no feed** are the demo's own pre-existing rows
  (`bank_account`, `department`…), which no Zoho feed produces. They render
  under "Unassigned", which is the honest answer, and they prove the stamping
  did not reach for rows it had no evidence about.

`is_demo` stamped on all 10 endpoints and all 39 mappings (C1's hygiene
pattern). The 8 transformation rules have no `is_demo` field — `pb_demo` never
added one to `hr.api.transformation.rule` — but they carry
`ondelete='cascade'` on `connector_id`, so the demo clean path removes them with
their connector. Noted rather than fixed: adding a field to another module's
model is outside this cycle's scope, and the cascade already makes the clean
correct.

*(live browser validation appended below)*
