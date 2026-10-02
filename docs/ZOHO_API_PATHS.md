# Zoho People — the paths, verified

Every path and parameter here was executed against a live Zoho People tenant
(ABM, `https://people.zoho.com/people/api`) on **2026-08-26**, with the ABM
connector's own OAuth token. This file exists because four of the seven seeded
paths had never been called: they were plausible, they were catalogued with
confident descriptions, and Zoho does not serve any of them.

## Why this needed writing down

Zoho People does **not** use HTTP status to report failure. Three of the four
refusals below arrive with `200 OK`. Anything that branches on
`response.status_code` reads them as success, and anything that then does
`payload.get('response', {})` on the list-shaped ones raises `AttributeError`.

The incident: a user pressed **Sync** on the Employees feed and got no error and
no data. The feed card read `Synced <1h ago · 0 staged · 0 pulled`, the header
read `Connected`. Every one of those statements was produced by a failure — and
because six of the seven feeds are per-employee lookups driven by the stored
employee list, an empty employee store made *all* the feeds read empty.

## The feeds

| Feed code | Path | Notes |
|---|---|---|
| `zohoemployees` | `forms/employee/getRecords` | `sIndex`/`limit=200`, `dateFormat=yyyy-MM-dd` |
| `zohoattsummary` | `attendance/getSummaryReport` | `startDate`/`endDate` (dd-MM-yyyy), `dateFormat` |
| `zohoovertime` | `forms/overtime_request/getRecords` | per employee, `searchColumn=EMPLOYEEMAILALIAS` |
| `zohosalary` | `forms/salary_details/getRecords` | per employee, `searchField=Employee_ID.Zoho_ID` |
| `zoholeave` | `forms/leave/getRecords` | whole form; the window is applied by Payobook |
| `zohoattdaily` | `attendance/getUserReport` | per employee, `empId` = employee NUMBER |
| `zohotimesheet` | `timetracker/gettimesheet` | `user` = email, required; catalogue-only by default |

### What each replaced, and why

| Feed | Shipped as | Zoho's answer |
|---|---|---|
| `zohoemployees` | `forms/P_Employee/records` | **200** `[{"message":"Invalid View Name","errorcode":7012,"Response status":2}]` |
| `zohosalary` | `forms/P_Salary/records` | same; and `P_Salary` is not a form on this tenant at all |
| `zoholeave` | `leave/getLeaveDetails` | **404** `{"errors":{"code":7201,"message":"Incorrect URL…"}}` |
| `zohoattdaily` | `attendance/getAttendanceByDate` | **404**, same shape |

`zohoattsummary` and `zohoovertime` were already correct.

Installed databases are repaired by migration `19.0.1.84.0`, which rewrites a
row only where it still holds the exact broken seeded value — an operator's own
path is never overwritten.

## Response shapes

**Form feeds nest one level deeper than they look.** `result` is a list of
single-key objects whose key is the record id and whose value is a list:

```json
{"response": {"result": [{"811648000007178001": [{"EmployeeID": "11708", …}]}],
              "status": 0}}
```

Reading the outer object gives one blank record per page. `_result_rows`
unwraps it.

**`attendance/getSummaryReport`** answers `{"summaryReport": [ … ]}` — no
`response` envelope.

**`attendance/getUserReport`** answers an object keyed by date, not a list;
`_result_rows` carries the key through as `_result_key`.

## Identifiers — three of them, and they are not interchangeable

| What | Where | Example |
|---|---|---|
| record id | `Zoho_ID`, and the form envelope's key | `811648000007178001` |
| employee number | `EmployeeID` on the employee form | `11708` |
| email | `EmailID` | `thuy.bui@abmauri.vn` |

- `attendance/getUserReport` takes the **number** in `empId`, or the email in
  `emailId`. Given the record id it answers **200** `{"error":"Invalid User."}`.
- `forms/salary_details/getRecords` takes the **record id**, via
  `searchField=Employee_ID.Zoho_ID`.
- `forms/overtime_request/getRecords` takes the **email**, via
  `searchColumn=EMPLOYEEMAILALIAS`.
- The leave form carries `Employee_ID.ID` (the record id) as its join key; its
  plain `Employee_ID` is a display string like `"Tuan Tran 11672"`.

## Two traps

**Emptiness is reported as an error.** Code **7024**, `"No records found"`,
`status: 1`, HTTP 200 — returned by an employee with no overtime this month, by
an empty form, and by the page *after* the last page of any paginated feed.
Treating it as a refusal breaks both quiet months and pagination. See
`ZohoConnector.EMPTY_ERROR_CODES`.

**Form search accepts a date filter and ignores it.**
`searchField=From&searchOperator=Between&searchText=01-01-2020,31-01-2020` on
the leave form returns exactly the same first page as no filter at all. Any
windowing on a form feed has to be done here, after the read — a server-side
filter would be a filter that silently does nothing.

## Field discovery

`GET forms/<linkName>/components` returns component keys in **all lowercase**:
`labelname` (the API field name), `displayname` (the human label), `comptype`,
`ismandatory`. The camelCase spellings (`compLinkName`, `labelName`, `compType`,
`isMandatory`) match nothing, so every discovered field came back nameless and
was dropped — "Fetch fields" reported that the vendor had returned none, of the
sixty it had just described.

`GET forms` lists the tenant's own form link names. On ABM:
`employee`, `salary_details`, `leave`, `overtime_request`, `employee_contracts`,
`department`, `designation`, `exitinterview`, `job_change1`, `manage_probation`,
`AddressProof`, `ExperienceLetter`, `P_Task`. Note that the `P_`-prefixed
internal names are mostly *not* valid: `P_Employee` happens to resolve to
`employee`, but `P_Salary` and `P_Attendance` are both rejected with
"Form name is invalid".
