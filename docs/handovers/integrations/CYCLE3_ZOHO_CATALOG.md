# Integrations Program — Cycle 3: the Zoho People catalog + legacy-ABM prepopulation (data XMLs)

> STATUS: FINAL — reconciled against Cycle 1 AND Cycle 2 (both shipped, deployed, live-verified). Cycle 1 facts are CONFIRMED SHIPPED (commits 745d736d..5e9bbb5a, deployed, live-verified): `hr.integration.endpoint` + `hr.integration.endpoint.template` live in `pb_hr_payroll_formula/models/integration_endpoint.py` (read it for exact field names — the data-type vocabulary is the shared `api_data_store.DATA_TYPES` list); `action_sync_endpoint_catalog()` is CREATE-ONLY matching on `code` with `active_test=False`; `action_apply_mapping_template` already resolves `mapping.template.endpoint_code` against the connector's endpoints (unresolvable → unstamped, never invented); `_stamp_endpoint` covers all five pull branches. The degrade rail (commit cf2d197a): server-side reads must not abort on databases lacking the feeds table — follow that guard pattern for anything you add. Cycle 2 is also CONFIRMED SHIPPED (read `CYCLE2_REPORT.md` for full detail): the **Mapping Studio** is live — client action tag `pb_mapping_studio`, arrival context keys `pb_connector`/`pb_endpoint`/`pb_config`/`pb_mode`/`pb_back`, FROM picker lists connectors with feeds, feed-scoped left column with per-feed group headers, samples on every left card, transform popover (8 ops, python absent), suggest/accept-all, template apply with the `{applied, skipped_existing, …}` shape, "Map fields" per feed in the connector cockpit, board mapping-counts are doors resolving to the most-mapped config. `api_mapping_create` now stamps `source_sample_value`/`source_data_type` (fix 3ba96e59). Settings → Integrations is a TWO-card section page (Integrations + Mapping Studio). The live backend prefix is **/bizapp** (`/odoo` 301s). Conventions binding through **W136** (C2 added W131–W136 — read them): note especially W127 (JS gate form is `node --input-type=module --check < file`), W129 (stale admin credential — temp single-company validation user via shell, removed same session), W130 (own Chrome over CDP with `--remote-allow-origins`), W131 (a `--test-tags` run's process can keep serving 8069 — end it by PID).

Purpose: everything the legacy ABM application pulled from Zoho People — its API endpoints AND its transformations — becomes **declarative, shipped, prepopulated data**: endpoint-catalog rows, vendor mapping-template rows, and transformation-rule templates. After this cycle, creating a Zoho People connector anywhere instantly shows the full feed catalog with the ABM-era feeds flagged, and "Apply vendor template" reproduces the legacy field map. Cycle 4 then binds it to the abm tenant's real config.

Conventions + environment: same as `docs/handovers/integrations/CYCLE1_ENDPOINTS_AND_NAV.md` §Environment (deploy ritual, logins, commit rules, W-rules through W119+C1/C2 additions, C18.x).

## The legacy inventory (verified from code 2026-08-20 — cite these, do not re-derive)

Source of truth: `om_hr_payroll/models/hr_zoho_staging.py` (live legacy client), `om_hr_payroll/models/hr_zoho.py:177-282` (dormant endpoints), `om_hr_payroll/models/hr_payslip.py:333-389` (rule-code map), modern client `pb_hr_payroll_formula/integrations/zoho_connector.py`. **READ-ONLY this cycle — you never edit om_hr_payroll.**

### Endpoints to catalog (`hr.integration.endpoint.template` rows ⟲C1, connector_type `zoho`)
| code | name | data_type | path | params_note | is_legacy_abm | evidence |
|---|---|---|---|---|---|---|
| `zohoemployees` | Employees | employee | `forms/P_Employee/records` | sIndex/limit=200, paginated; legacy ABM variant: `forms/employee/getRecords` (dateFormat yyyy-MM-dd, no pagination) | **True** | staging :309; modern :284 |
| `zohoattsummary` | Attendance summary | attendance | `attendance/getSummaryReport` | startDate/endDate dd-MM-yyyy; seconds + H:MM payloads; join key emailId | **True** | staging :456 |
| `zohoovertime` | Overtime requests | custom | `forms/overtime_request/getRecords` | searchColumn=EMPLOYEEMAILALIAS, fromDate/toDate dd-MM-yyyy; legacy called it per-employee (N+1 — do not reproduce) | **True** | staging :472-485 |
| `zohosalary` | Salary form | salary | `forms/P_Salary/records` | searchField=Employee_ID.Zoho_ID | False | zoho_connector :411 |
| `zoholeave` | Leave records | leave | `api/v2/leavetracker/leaves/records` | from/to dd/MM/yyyy; modern alt: `leave/getLeaveDetails` (empId-scoped) | False | hr_zoho :218; zoho_connector :495 |
| `zohoattdaily` | Attendance by date | attendance | `attendance/getAttendanceByDate` | empId, sdate, edate | False | zoho_connector :454 |
| `zohotimesheet` | Timesheets | custom | `timetracker/gettimesheet` | dormant in legacy code | False | hr_zoho :182 |

(Auth — `accounts.zoho.com/oauth/v2/token` refresh grant — is connector-level, NOT an endpoint row. Scope note for description fields: `ZOHOPEOPLE.forms.READ,attendance.READ,leave.READ`, callback `/zoho/callback` — zoho_connector :530-533.)

Darwin (parity, connector_type `darwin`): `darwinemployees` / Employee directory / employee / `masterapi/employeedirectory` (POST, page/page_size=200); `darwincompensation` / Compensation / salary / `masterapi/compensation` (POST, employee_ids+date range) — darwin_connector.py :48-49. Plus a description note that an inbound webhook exists at `/api/darwin/webhook`.

### Employee field map (legacy renames → vendor mapping-template rows)
Legacy write sites: staging create :376-402, bypass :406. Existing vendor rows (14) live in `pb_hr_payroll_formula/data/mapping_templates.xml:9-73` with generic target codes: `EMPID, FULLNAME, EMAIL, DEPT, JOBTITLE, JOINDATE, BASIC, ALLOWFIX, DEPS, WDAYS, OTHOURS, LEAVEDAYS, BANKACC, TAXID`. **Code law (formula-converter contract): target codes are UPPERCASE, underscore-free, and NO code may be a substring of another** — check every new code against the union of existing codes in that file before choosing it (e.g. `FULLNAMEVN` is illegal beside `FULLNAME`; pick `VNFULLNAME`).

New/updated rows (source_path → suggested target_code; adjust codes to obey the law, keep labels human):
| Zoho key | target (suggest) | transformation |
|---|---|---|
| `FirstName` | GIVENNAME | direct |
| `LastName` | SURNAME | direct |
| `Nick_Name` | ENFULLNAME | direct (legacy semantic: English full name) |
| `Full_Name_Vietnamese` | VNFULLNAME | direct |
| `EmployeeID` | EMPID (exists) | keep |
| `EmailID` | EMAIL (exists) | keep |
| `Department` | DEPT (exists) | keep |
| `Designation` | JOBTITLE (exists) | keep |
| `Employeestatus` | EMPSTATUS | direct |
| `Employee_type` | EMPKIND | direct |
| `LocationName` | WORKSITE | direct |
| `Gender` | GENDERCODE | python `value.lower() if value else ''` (legacy :395) — **seed with `verify` flag per the file's convention; python rows are data-shipped, never UI-edited** |
| `Date_of_birth` | BIRTHDATE | note: yyyy-MM-dd parse, silent-False on bad value (legacy :354-363) |
| `Dateofjoining` | JOINDATE (exists) | same date note |
| `Mobile` | MOBILENO | direct |
| `Pan_Number` | PANCODE | direct |
| `PIT_Number` | PITCODE | direct |
| `UAN_Number` | UANCODE | direct |
| `Aadhaar_Number` | AADHAARNO | direct |
| `Bank_Name` | BANKTITLE | direct |
| `Bank_Account_Number_VND` | VNBANKACC | direct (distinct from generic BANKACC — check substring law: BANKACC vs VNBANKACC violates it → rename one, e.g. keep `BANKACC` and use `VNDACCOUNT`) |
| `Insurance_Book_Number` | INSBOOKNO | direct |
| `Zoho_ID` | ZOHOREF | direct |
Stamp `endpoint_code='zohoemployees'` (⟲C1 field) on ALL zoho employee-form rows including the existing 14 where they're employee-form fields (Salary/OT/leave-ish existing rows get their right endpoint_code or stay blank — judge per row, report the table).

### Transformation-rule templates (the legacy aggregations)
Engine: `hr.api.transformation.rule` (`pb_hr_payroll_formula/models/api_transformation_rule.py:24`) — rule_type count/sum/…, `filter_expression` (python), `aggregate_field`, `output_key`, `source_data_type`. There is NO vendor-template model for it yet — **WP-2 adds one** (`hr.api.transformation.rule.template`, clone the C1 endpoint.template pattern).

Rows to ship (connector_type `zoho`):
| output_key | rule_type | source_data_type | aggregate_field | filter_expression | legacy evidence |
|---|---|---|---|---|---|
| `OTHRS150` | sum | custom | `Actual_Pay_Hour` | `record.get('OT_Type')=='150%' and record.get('ApprovalStatus')=='Approved'` | staging :497-511 |
| `OTHRS200` | sum | custom | same | OT_Type=='200%' … | :513 |
| `OTHRS300` | sum | custom | same | OT_Type=='300%' … | :522 |
| `OTHRS210` | sum | custom | same | OT_Type=='210%' … | :531 |
| `OTHRS270` | sum | custom | same | OT_Type=='270%' … | :540 |
| `OTHRS390` | sum | custom | same | OT_Type=='390%' … | :550 |
| `DEPCOUNT` | count | employee | — | `bool(record.get('Dependent_PIT_Number'))` over tabular section `Dependent and Dependent Health Insurance` | :367-373 — **verify the engine's record shape supports tabular sections; if `_execute_for_records` (:176) walks flat records only, note it and express the filter against the flattened dot-path instead; if impossible declaratively, ship as rule_type=python with the code in the data file** |
| `WORKEDHRS` | python (or sum+transform) | attendance | — | seconds→hours `/3600` + paidLeaveHours `'H:MM'` parse (legacy :559-577) — express as a python rule template with the exact legacy arithmetic |
(Exact filter_expression syntax: read `_execute_for_records` :176 to confirm the eval namespace — `record` vs bare keys — before writing the rows; the legacy date-window re-filter (:497-557) is redundant because the endpoint is already date-scoped — drop it, note the drop.)

Instantiation: `action_apply_template` on the onboarding wizard (`integration_mapping_template.py:159`) and connector `action_apply_mapping_template` (`integration_connector.py:283`) grow a sibling step instantiating rule templates (create-only by `(connector_id, output_key)`, never overwrite). ⟲C1: if C1's catalog-sync grew a different natural hook, use it consistently.

## Work packages
- **WP-1** `data/integration_endpoints.xml` (noupdate="1"): the endpoint-template rows above. Remember W13.1: noupdate rows are frozen per-DATABASE on first load — get them right the first time; corrections on live need the force-write path, so proof-read paths/codes before deploy.
- **WP-2** `hr.api.transformation.rule.template` model + ACLs (user=read/admin=CRUD) + `data/transformation_rule_templates.xml` rows + instantiation hooks (create-only).
- **WP-3** mapping_templates.xml: new rows + endpoint_code stamps per the table; the substring-law audit across ALL target codes in the file (report the final code list).
- **WP-4** Wire-through check: on a fresh zoho connector (test), catalog sync (⟲C1) + apply-template yields endpoints + endpoint-stamped mappings + rules; Mapping Studio (⟲C2) shows them grouped per endpoint with transform pills.
- **WP-5** Live demo touch: after deploy, run catalog sync + template apply on the live demo "Zoho People" connector (`pb_demo` seeds it — demo_integrations.py:26-28) via JSON-RPC so the owner SEES the prepopulated catalog on payobook.com. is_demo hygiene per C1's pattern.

### Binding non-goals
No om_hr_payroll edits. No live Zoho HTTP calls (no credentials exist on payobook; everything is catalog/data). No abm/tenant work (C4). No UI redesign beyond what C2 shipped. No python-transform UI editing. Codes obey the converter contract.

## Numbered tests
1. Fresh zoho connector → catalog sync creates exactly the 7 endpoint rows, legacy-ABM flags right; idempotent re-run creates 0.
2. Apply vendor template → employee mappings created with `endpoint_id` = the employees endpoint; existing-wire never overwritten (pre-create one, assert skipped).
3. Rule templates instantiate create-only by output_key; re-apply = 0 new.
4. **Coverage battery**: every row of the legacy rename table above exists as a template row (assert source_path set equality in a test, so future edits can't silently drop one).
5. Substring-law audit test over all target codes in mapping_templates.xml (fails if any code is a substring of another).
6. `filter_expression` rows actually execute: feed `_execute_for_records` synthetic OT records (150%/Approved, 150%/Pending, 200%/Approved) → OTHRS150 sums only the first; DEPCOUNT counts only rows with a PIT number; WORKEDHRS converts 28800s + '2:30' correctly (10.5h total shape per legacy math).
7. Darwin parity rows instantiate.
8. Suites green (scoped run; the 2 known failures only).
9. Chrome-MCP on live: demo Zoho People connector shows the 7-feed catalog (legacy-ABM badge visible ⟲C1 UI); Mapping Studio FROM picker lists the feeds; applied template wires visible with pills; screenshots.

## Deploy + verify
Standard ritual. Data files load via `-i`-less `-u pb_hr_payroll_formula` (noupdate rows load once — verify they landed by count query, W13.1). WP-5 via JSON-RPC. Chrome-MCP per test 9.

## Self-review
Proof-read every endpoint path against the evidence column (a wrong path shipped noupdate is a frozen wrong path); re-check the code-substring audit; confirm no rule template can throw on empty payloads (default_value semantics).

## Commits
(1) feat(pb_hr_payroll_formula): the Zoho People feed catalog — the ABM inventory becomes data; (2) feat(pb_hr_payroll_formula): transformation-rule templates + instantiation; (3) feat(pb_hr_payroll_formula): the legacy field map joins the vendor templates; (4) docs/ledger. Tests with features.

## Report back
Final code list (substring-audited), the endpoint_code decision table for the existing 14 rows, `_execute_for_records` namespace findings + how DEPCOUNT/WORKEDHRS were expressed, per-test evidence, live screenshots, hashes, EXIT codes, deviations, new W-rules.
