# RIZE P1 — pb_zoho_bridge: the Zoho receiving door

Read FIRST: `docs/handovers/RIZE_LEDGER.md` (conventions, deploy ritual, gotchas, rulings —
especially D6 and D8). Design doc: `docs/design/rize-hrms-blueprint.html` §14.
Depends on P0 (`pb_lifecycle`) being installed — check the P0 section at the bottom of the
ledger's phase log for any model-name deviations before coding.

## Scope

ONE new module `pb_zoho_bridge`, ready-to-connect (live Zoho hookup happens later; the
door + rules + fallback must be fully testable with sample payloads today):

1. **Inbound webhook** `POST /api/zoho/webhook` — clone of the Darwin webhook.
2. **`ZohoConnector.ingest_records`** so the generic `webhook_ingest` hook accepts Zoho pushes.
3. **Event rules** (data-driven): employment-status values → open onboarding/offboarding
   journey, update-only, ignore, or log-conflict.
4. **Core-field writes** for arriving employees (create/update) through a strict whitelist.
5. **File-upload fallback** wizard: a Zoho employee export (CSV/XLSX) runs through the SAME
   pipeline as the webhook.
6. **Auto login creation** (ruling D6): portal user created on employee arrival; a
   `send_credentials()` method that P3's journey step will call on joining day.

### Binding NON-goals
- NO Payobook→Zoho outbound (ruling D8 — on hold; do not stub controllers for it).
- NO changes to the existing Zoho pull/OAuth/sync-schedule machinery.
- NO new cockpit/lens — admin config is native views + ⌘K deep link.
- NO probation/asset/buddy logic (later phases hook in via the extension points below).

## Verified plumbing facts (do NOT re-derive)

- Webhook canon: `pb_hr_payroll_formula/controllers/darwin_webhook.py:38` —
  `POST /api/darwin/webhook`, `type='json'`, `auth='public'`, `csrf=False`, body
  `{connector_id, token, data_type, records}`, auth via
  `hmac.compare_digest(token, connector.api_key)`, UNIFORM "unauthorized" reply for
  unknown/wrong-type/inactive connector. Clone this file's shape exactly for
  `/api/zoho/webhook`.
- Server hook: `hr.integration.connector.webhook_ingest()` at
  `pb_hr_payroll_formula/models/integration_connector.py:2077` — requires the connector
  class to implement `ingest_records`; enforces `MAX_WEBHOOK_RECORDS`; stamps connector +
  endpoint. Read it before writing `ingest_records`.
- Connector classes live in `pb_hr_payroll_formula/integrations/`;
  `zoho_connector.py:30` `ZohoConnector` (BASE_URL people.zoho.com). Add `ingest_records`
  THERE (this is the one edit to an existing module; keep it additive).
  Factory: `integration_connector.py:1896` `_get_connector_instance()`.
- Raw store: `hr.api.data.store` (`pb_hr_payroll_formula/models/api_data_store.py:32`,
  DATA_TYPES include 'employee','custom') — land raw payloads there like the Darwin path.
- Existing Zoho staging (LEGACY — do not extend, but reuse its knowledge):
  `om_hr_payroll/models/hr_zoho.py` maps Zoho employees; check whether `hr.employee`
  already carries a Zoho id field there (e.g. an employee-number/zoho id column) — REUSE it
  for matching if present; otherwise add `pb_zoho_id` Char (indexed) on hr.employee inside
  pb_zoho_bridge. Also match by work_email as fallback, then by name last (log ambiguity,
  never guess between 2 candidates — mark the row for review instead).
- Journey engine (P0): open a case via `env['pb.journey.case'].create(...)` +
  `action_open()`; case fields: employee_id, case_type ('onboarding'/'offboarding'),
  template_id (auto-pick: active template matching case_type + employee country, else the
  countryless one), anchor_date, source='zoho'. Skip creation if an ACTIVE case of the same
  type exists for the employee (idempotency). Confirm exact API in
  `pb_lifecycle/models/` before use.
- `hr.employee` Odoo-19 facts: `sex` not gender; departure fields exist
  (`departure_date`, `departure_reason_id`); manager = `parent_id`; joining date derives
  from first contract (`pb_people/models/pb_people.py:22-30` `_join_date`) — the bridge
  stores DOJ on the case anchor_date and (if no contract exists) leaves contract creation
  ALONE (P10/HR does contracts; do not auto-create contracts).
- Portal user creation: create `res.users` with `share=True` semantics via the portal
  group — look at how Odoo 19 core does portal invites (`base`/`portal` addon,
  `portal.wizard` pattern) and create the user with `login = work_email`,
  `groups_id`→portal group ONLY, `active=True`, NO password, no invitation mail at create
  time (suppress with context `no_reset_password=True` — verify the exact context key in
  core code). `send_credentials(employee)`: trigger the standard password-reset/invite
  email (white-label is automatic via biz_mail_debrand). Config param
  `pb_zoho_bridge.auto_create_logins` default '1'. Guard: never touch EXISTING users;
  skip employees without work_email (count + report).
- Config params: `ir.config_parameter` pattern used everywhere
  (e.g. `pb_ess_workforce.publish_mail`).

## Architecture

### Models (pb_zoho_bridge/models/)

**`pb.zoho.event.rule`** — sequence, trigger Selection
`[('created','Employee created'),('status','Employment status changed'),
('updated','Employee updated')]`, match_value Char (for 'status': the Zoho status text,
case-insensitive trim match; empty = any), action Selection
`[('onboard','Open onboarding journey'),('offboard','Open exit journey'),
('update','Update the record only'),('ignore','Ignore'),('review','Log for review')]`,
active, company_id optional, note.
Seed data (noupdate="0" so we can evolve): created→onboard; status "resigned"→offboard;
status "notice"→offboard; status "terminated"→review; status "confirmed"→update;
updated→update.

**`pb.zoho.inbox`** — the audit/idempotency log. One row per received record:
external_event_id Char (indexed), zoho_record_id Char, payload_json Text, received_at,
source Selection `[('webhook','Live push'),('file','File upload'),('manual','Manual')]`,
state Selection `[('applied','Applied'),('skipped','Skipped (duplicate)'),
('review','Needs review'),('error','Error')]`, employee_id m2o (set when matched),
action_taken Char, error_note. Unique constraint (models.Constraint) on
(external_event_id) where provided; when Zoho gives no event id, derive one as a hash of
(zoho_record_id, modified-time/payload). Duplicate → state='skipped', no side effects.
List view for HR review (gated integration/lifecycle managers), filters by state.

**Pipeline service** (`models/zoho_pipeline.py`, AbstractModel `pb.zoho.pipeline`):
`process_records(records, source)` — for each record (own savepoint + own try/except):
1. normalise the Zoho employee dict (helper `_normalise(rec)` mapping Zoho People keys —
   EmployeeID, FirstName/LastName, EmailID, Department, Designation, Date_of_joining,
   Employeestatus, Reporting_To... — study `om_hr_payroll/models/hr_zoho.py` +
   `zoho_connector.py fetch_employees` for the real key spellings and reuse their
   normalisation if importable);
2. dedupe via pb.zoho.inbox;
3. match employee (zoho id → email → single-name-match; ambiguous → review);
4. determine trigger (created if no match and rule says so; status if status changed vs
   stored; else updated);
5. apply action per first matching active rule (sequence order):
   - create/update through the WHITELIST ONLY: name, work_email, work_phone, job_title,
     department_id (match by name, create if missing), parent_id (match manager by zoho
     id/email), sex, country via company — NEVER wage/bank/contract fields (ruling D8:
     Zoho owns employee core only);
   - onboard/offboard → open journey case (idempotent) with anchor_date = DOJ / last
     working day from payload (fallback today);
   - offboard also writes `departure_date` ONLY if empty (never overwrite HR's value);
   - review → inbox row state='review', no writes;
6. auto login creation (D6) after a create, if enabled;
7. stamp inbox row applied/error with action_taken.
Extension point for later phases: after-hooks
`_after_onboard(case, rec)` / `_after_offboard(case, rec)` — empty methods later modules
override (P2 asset deactivation, P3 buddy/HRBP kick-off).

### Connector + controller

- `controllers/zoho_webhook.py`: `/api/zoho/webhook` — exact Darwin clone; find the
  connector by id, require `connector_type == 'zoho'`; hand to `webhook_ingest`.
- `ZohoConnector.ingest_records(data_type, records, endpoint)` (in
  pb_hr_payroll_formula/integrations/zoho_connector.py, ADDITIVE): store raw rows in
  `hr.api.data.store` (mirroring Darwin's approach) AND call
  `env['pb.zoho.pipeline'].process_records(records, 'webhook')` when data_type is
  'employee' (guard with a registry check so pb_hr_payroll_formula still loads when
  pb_zoho_bridge is not installed: `if 'pb.zoho.pipeline' in self.env: ...`).
- Setup data: create (data XML, noupdate="1") one `hr.integration.connector` record
  "Zoho People — RIZE inbound", connector_type 'zoho', active, with a generated api_key
  IF the model has such a field & default — otherwise document the manual step and set the
  key via the deploy script. Confirm field names in `integration_connector.py`.

### Fallback wizard (`wizard/zoho_upload_wizard.py` + native wizard view)

TransientModel `pb.zoho.upload.wizard`: file Binary + filename, parse CSV or XLSX
(openpyxl available), header-map the same normalised keys (accept both Zoho export
headers and our own re-import), preview_json + counts on a second step (created/updated/
journeys to open/review), `action_apply()` → `process_records(rows, 'file')`, then result
summary. Gated `group_lifecycle_manager` OR the integration group — pick the existing
integration group from `pb_hr_payroll_base` security (`group_payroll_integration_user`).
⌘K deep link "Upload joiner file" (sequence 2150 range) + an act_window for the inbox
"Arrivals from the connected system" (⌘K 2151).

### Security
- ACLs: rules/inbox/wizard for integration users (read) + lifecycle managers (write rules);
  pipeline AbstractModel needs no ACL. Company ir.rule on inbox + rules.
- The webhook route is public-token-gated (Darwin pattern) — no session.

## Safety rails
- NEVER auto-create contracts, wage data, or bank data from Zoho payloads.
- Never overwrite a non-empty departure_date, and never rename an employee whose name
  differs only by case/whitespace (skip cosmetic renames).
- The pipeline must be idempotent: replaying the same payload twice = zero new side effects
  (second pass all 'skipped').
- Do not send ANY email to real addresses during testing: use test employees with
  @example.com mails; `auto_create_logins` respects that portal users are created but no
  invite is sent until `send_credentials`.
- One additive edit to pb_hr_payroll_formula (zoho_connector.py + nothing else). Deploy
  `-i pb_zoho_bridge -u pb_hr_payroll_formula` per ledger ritual (the engine takes -u fine).

## Numbered test cases
T1. Deploy clean (EXIT=0, no tracebacks); registry loads.
T2. Webhook auth: curl from the server to 127.0.0.1:8069 `/api/zoho/webhook` with a WRONG
    token → uniform unauthorized; nothing created.
T3. Webhook with valid token + one NEW employee record (fake Zoho payload, @example.com)
    → employee created with whitelist fields, inbox row 'applied', onboarding case opened
    (visible in Journeys cockpit), portal user created (no email sent).
T4. Replay the exact same payload → inbox 'skipped', no duplicate employee/case/user.
T5. Status-change payload for that employee with "Resigned" → offboarding case opened,
    departure_date set; replay → skipped.
T6. Unknown status value → 'review' row, zero writes.
T7. Ambiguous match (two employees sharing a name, payload without id/email) → 'review'.
T8. Upload wizard: XLSX with 3 rows (1 new, 1 update, 1 resigned) → preview counts right,
    apply → same outcomes as webhook path; inbox rows source 'file'.
T9. `send_credentials()` on the test employee → exactly one invite/reset mail queued
    (inspect mail.mail), white-labelled (no "Odoo" in subject/body).
T10. Kill-switch: `auto_create_logins`='0' → new arrival creates NO user.
T11. pb_hr_payroll_formula still healthy: open the Integrations cockpit + run one existing
    screen; no regression, and the module loads fine on a DB WITHOUT pb_zoho_bridge
    (code-level guard verified by reading, since only payobook gets the install).
T12. White-label grep zero; inbox/rules views read in plain English; dark+light screenshots
    of the inbox list and wizard.
T13. Delete the test employees/cases/users you created (or deactivate) — leave the DB tidy;
    document what remains (inbox audit rows may stay).

## Deliverables / report back
- Commits per ledger (module + the one connector edit staged explicitly).
- Per-test results, deploy EXIT line, deviations, new gotchas appended to ledger.
- The exact whitelist of fields written, the seeded rule set, and the after-hook method
  names (P2/P3 will override them).
- Confirm where the Zoho api_key lives + the exact curl needed to configure the real
  webhook later (goes in the final owner report).
