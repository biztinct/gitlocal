# FS-5 — Reach everywhere (`pb_form_studio_reach`) — report

Branch `fs-5` (from `origin/fs-1` @ 87ede1a76; `origin/fs-1` @ d341ed396 — the engine's R14
follow-up — merged in and everything re-tested against it). New module `pb_form_studio_reach` **19.0.1.0.0**;
one hook in `biz_access` (19.0.1.13.0 → **19.0.1.14.0**); lesson L42 in `pb_learn`
(19.0.20.8.8 → **19.0.20.8.9**). Not deployed. Local DB `fs_5_t` (copy of `upd_p6_t_tpl`
brought up to the branch), baseline copy `fs_5_b`; both dropped at the end.

Status: **done** — all eight items handled (item 5 Explorer deliberately not built, §5); 25 own
test methods pass against the real engine; touched suites identical to the baseline; browser walk
clean.

## 1. Verified facts (origin/fs-1; line numbers re-checked)

| # | Fact | Where |
|---|---|---|
| V1 | Payroll sources: catalogue + values are the typed-source seam; the base value path refuses `employee.`/`contract.` names outside its tuples → own prefix `custom.employee.<f>` / `custom.contract.<f>` | `pb_hr_payroll_formula/models/application_domain_sources.py:141-214, 216-283`; precedent `pb_me_tax/models/formula_sources.py:47-101` |
| V2 | Application inputs of a payslip come from `_application_employee_inputs`, which merges `_application_domain_values` (so a mapped source key reaches the payslip input row); a key nobody maps is never asked | `application_payroll_source.py:742-800, 1082-1101` |
| V3 | `pb_payroll_templates` calls `_application_record_context_values` directly (bypasses `_application_domain_values` overrides) — same for pb_me_tax / pb_time_pay sources; Form-builder keys are not answered there | `pb_payroll_templates/models/templates.py:544` |
| V4 | Records Desk reads every cell under sudo (`search_page` :783-808, `_read_cell` :971) and every write/whitelist goes through `_cards` (:280, `_whitelist` :1449) → dropping a card in `_cards` closes label, value, sheet and forged apply at once. A scheme mapping to ANY field makes a card regardless of field permission (no groups check outside Master mode) | `pb_records/models/pb_records_desk.py` |
| V5 | A cell marked `missing` means "no contract" to `_evaluate` (refusal text "has no contract") — a not-applicable cell must not use it | `pb_records_desk.py:1520-1526` |
| V6 | The Mapping board shows only CURATED destinations (`employee_mapping_data` keeps `f:` cards in `_ec_lane_index`); custom fields were reachable only by search. `_ec_is_mappable` is asked for the catalogue AND at wire creation | `pb_formula_studio/models/pb_formula_studio.py:11047-11054, 10554, 11363` |
| V7 | `biz_access` field rules: a field outside the static `RESOURCES` short-circuits the read check (`_has_field_access` :294) and the sudo attribute check (`_studio_attribute_check` :256); policy validation derives from `_studio_resources` (studio_service.py:206, 345) | `biz_access/models/studio_policy.py`, `studio_service.py` |
| V8 | Audit: watched fields are `biz.audit.rule._watched_fields` (ormcached, cleared by every registry setup, which field create/delete/permission change runs — core `registry.py:426-428`); a binary value would be logged as `str(bytes)` | `biz_audit_trail/models/biz_audit_rule.py:35`, `biz_audit_mixin.py:62-110` |
| V9 | Timeline readers: `pb.employee.timeline._audit_items` and `pb.contracts._cd_history_fields`; both run as the caller; precedent for hiding entries = context flag read by `biz.audit.entry._search` | `pb_employee_vault/models/employee_timeline.py:75`, `pb_contracts/models/pb_contract_360.py:1239`, `pb_job_change/models/job_change_inherits.py:44-75` |
| V10 | My details requests: one model, kinds extendable by `selection_add`; `pb_portal_create` refuses a second open request of the same kind; a draft request opens `_pbmd_render_form` by kind; `_DONE` limits the toast words | `pb_me_details/models/detail_request.py:230-302`, `controllers/portal.py:27, 279-294` |
| V11 | Explorer: `_DIMENSIONS` is a module constant read in 12 places (spec cleaner :448, `_dim_expr` :892, drill :2002, export :2281, PayAI spec parser :2912…); `pb_fact_line` has NO `employee_id` (`_T2_ONLY`, `_where` skips it on the line table) | `pb_explorer/models/pb_explorer.py`, `pb_fact.py:139-212` |
| V12 | Engine busy rail joins `pg_locks` to `pg_class` by oid without `l.database`: local databases copied from one template share table oids, so a payslip write in ANOTHER database can refuse field creation here — seen on the first suite run (engine tests 04/08/10/14/20/21 refused "pay run being worked out"); FIXED by the engine follow-up (FS1-8) | `pb_form_studio/models/form_studio.py` `_pbfs_busy` |

## 2. What was built

`pb_form_studio_reach` (depends `pb_form_studio, pb_hr_payroll_formula, pb_formula_studio, pb_records,
pb_me_details, biz_access, pb_employee_vault, pb_contracts`). Every surface asks the ENGINE which
custom fields exist and who may see them (`fields_for`, `_pbfs_values_for`, `_pbfs_meta`,
`portal_*`); nothing reads a custom value with a plain read loop.

| Item | How (file) | Notes |
|---|---|---|
| 1 Pay formulas | `models/formula_sources.py` — catalogue = `fields_for(model,'formula')` (marked + caller may see), label "Company details: <label>"; values only for mapped keys, actor's own rights (`checked_read`/`readable_field`), Country of Work → empty value (`not_for_this_country_of_work`), choices answer their English label | `models/form_studio.py`: finder `_pbfr_refs_formulas` (delete blocker + Used by); `update_field` refuses switching "Use in pay formulas" off while a formula reads it. Import mappings / saved views / saved searches: the engine's own finders (proved with real rows) |
| 2 Records + Updates | `models/records.py` — `_master_fields` += custom fields the reader may see (files left out); `_cards` drops custom cards the reader may not see in EVERY mode (scheme mappings too); not-applicable cell blank; a change to it refused in words via `_coerce` | Updates sheets follow automatically (its catalogue is `get_fields(0)`) |
| 3 Mapping | `models/mapping.py` — lane "Company details" via `_ec_lane_index` + `_ec_lane_label` (between Bank and Other employee fields); `_ec_is_mappable` refuses a custom field the reader may not see (catalogue + wire creation) | lane list ormcached per user/lang |
| 4 My Payobook (R14) | `controllers/portal.py`, `models/portal_request.py`, `views/portal_templates.xml` — section(s) from `fields_for('hr.employee','portal',record)` + `portal_values`; "Change these details" → `/my/details/company`; POST → `portal_check` → instant part `portal_apply` at once, approve part → ONE request (new kind "Company details" of `pb.me.detail.request`), Approvals inbox rows label + now → proposed, My requests list; approval → `portal_apply`; refusal writes nothing; a new proposal takes over fields still waiting (old request withdrawn, hidden as replaced); switching "show"/"can change" off closes the field in open requests (plain note); open requests are a delete blocker | one request per SUBMISSION (all fields HR must approve), so "one open request per field" = a new submission takes over the waiting fields; link fields changeable only for country / department / job (owner question §9) |
| 5 Explorer | **not built** — see §5 | test 05 proves no custom field reaches its schema |
| 6 Access | `biz_access` hook `pb.access._studio_extra_fields(model)` (manual fields only; listing in `_studio_resources` for readers who may see the field; enforced in `_has_field_access` and the sudo attribute check); `models/access.py` answers it from the registry (ormcached) | unknown-field default unchanged |
| 7 Timeline | `models/audit.py` — custom fields of employee + contract added to the watched set; files logged as "File attached"/"File removed"; employee Timeline and contract History hide entries of fields the reader may not see | |
| 8 Learn | lesson **L42 "Add your own fields"** (station `formbuilder`, Setup line; 3 look steps on the Field library + quiz); anchors `fb-head/fb-kpis/fb-table` laid by `static/src/xml/learn_anchors.xml` (t-inherit; pb_form_studio untouched); SCREEN_CTX `formbuilder` | no existing lesson walks the employee side panel's tabs; L29's contract drawer tabs are unchanged (FS-3 adds a group inside Terms) → no lesson needed changing |

## 3. biz_access hook (merge risk — the only edit outside the bridge)
`biz_access/models/studio_policy.py:25-45` (`_studio_extra_fields`, `_studio_is_extra_field`),
`:256-266` (`_studio_attribute_check`), `:294-296` (`_has_field_access`);
`studio_service.py:217-227` (`_studio_resources`). Generic, no product word, manual fields only.

## 4. Tests
Module suite `/pb_form_studio_reach` on `fs_5_t` after merging the engine follow-up:
**25 test methods (31 incl. class set-up), 0 failed, 0 errors.** Hosts for the employee and the
contract are registered in TEST CODE only (`tests/common.py`, patch of `_pbfs_hosts`).

| # | Case | Result |
|---|---|---|
| 1a | formula catalogue: only fields marked "Use in pay formulas", only those the reader may see (HR never gets an administrator-only field's key or label); unmarked / file / text not offered; contract fields under `custom.contract.` | PASS |
| 1b | values: number, choice (English label), yes/no, date, contract field; India-only field empty for a Vietnam person and filled for an India person; unmarked never answered; administrator-only field → "not accessible" for HR, value for the administrator | PASS |
| 1c | payslip byte-identical with and without the bridge (plain scheme); application inputs identical when no component uses a custom field; a component mapped to one reads 42 | PASS |
| 1d | delete blockers: pay formula (named), pay-data import mapping (real row), saved view (real row); "Use in pay formulas" cannot be switched off while used; an unused field has no blocker | PASS |
| 2a | Records Master: custom fields listed + editable for HR; administrator-only and file fields absent; a pay scheme mapping an administrator-only field still gives HR no card (the administrator gets it) | PASS |
| 2b | values on the grid; India-only cell blank for Vietnam, change refused in plain words; forged apply of an administrator-only field refused before any write; a normal change goes through the desk's own path (approval route respected) | PASS |
| 2c | Updates sheet catalogue: field in, administrator-only field and its label out | PASS |
| 3 | Mapping: "Company details" lane between Bank and Other employee fields; files never; administrator-only field neither offered to HR nor wireable | PASS |
| 4 (P1–P8) | My details over HTTP as a portal login: shown-only vs changeable; saved at once vs after HR approves (approve writes, refuse writes nothing, reason on the page); forged locked / hidden / standard / unknown names refused, nothing written; only the session's own record; Country of Work; untick "can change" closes the open request with a note; one open request per field; open request blocks delete | PASS |
| 5 | Explorer schema carries no custom field (nothing built — §5) | PASS |
| 6a | Access catalogue lists custom fields under Employees / Contracts, labels in the reader's language, only to readers who may see them; static catalogue unchanged; a standard field can never be pulled in by the hook | PASS |
| 6b | a field rule "hidden" on a custom field (real role, profile, policy, approval) → read and write refused, engine `fields_for` drops it; an un-ruled field keeps today's default | PASS |
| 7 | timeline: change logged old → new; file logged "File attached" (never content); HR's employee Timeline and contract History hide administrator-only fields (label and values); the administrator sees them | PASS |
| 9 | with no host / no field every surface answers as before | PASS |
| 10 | silent install (no job, mail, action, rule, layout, field settings in module data) | PASS |
| 11a-c | PO gate vi + id (45 entries each, three markers, no empty msgstr, no vendor word); no vendor word in views / manifest / `_()` literals; Vietnamese words load | PASS |

**Touched suites vs baseline** (same database copy; baseline = bridge uninstalled + `biz_access`
at origin/fs-1): `/biz_access, /pb_records, /pb_updates, /pb_me_details, /pb_employee_vault,
/pb_contracts, /pb_form_studio, /biz_audit_trail, /pb_job_change` + the Mapping classes of
`pb_formula_studio` (9) + the payroll-source classes of `pb_hr_payroll_formula` (4):
**1,012 tests, 4 failed + 1 error on BOTH sides — identical set**, none in a file this phase
touched: `pb_contracts` test_cd1 test_01 (components key set) and four static-source checks in
`pb_formula_studio/tests/test_one_mapping_home.py` (JS source wording).

**Learn**: `gen_learn_data.py` writes clean, `--check` clean, `test_step_shape.py` 0 failed;
`check_contract.py` 2 failures, both pre-existing and unrelated (`c1-cockpit-anchors` missing
`pe-filters` in pb_people; `govt-reports-coming-soon-is-an-install`).

**Browser walk** (local `fs_5_t`, walk-only hosts module kept in the scratchpad, never committed):
portal login → My details shows a "Company details" card (shown-only Shoe size, changeable Shift
and Safety course), the administrator-only field absent; Change these details → form; Shift
changed (waits for HR, "change waiting for HR" on the page, "Your changes" lists "Company details:
DEMO Shift") and the date changed (saved at once); page and form at 390 px: no sideways scroll
(scrollWidth 390, card 360); no vendor word; console clean. Administrator → Settings › Form
builder: Field library with the engine's "My Payobook" column, Used by = 1 on the field with an
open request; Learn anchors `fb-head`, `fb-kpis`, `fb-table` present; Records Master lists the
custom fields (editable); Mapping lists them under "Company details"; console clean.

## 5. Explorer — not forced (item 5)
A custom-field dimension cannot be added safely from outside today: `_DIMENSIONS` is a module
constant shared by every database on the server and read in 12 places (spec cleaner, SQL
expression, drill, export, PayAI spec parser); money measures live on `pb_fact_line`, which has no
employee column, so "Net pay by <custom field>" needs a fact-table column + rebuild. Only the
people-count measures could be split. Recommended later phase: an `employee_id` on line facts
(rebuild) and a `_dimensions()` method replacing the constant in `pb_explorer`.

## 6. Merge-time tasks / checks
1. **Engine portal methods (R14)**: landed on origin/fs-1 (d341ed396), merged into fs-5, tested
   for real (P1–P8). The engine's deprecated `'everyone'` purpose is no longer called by this
   module — the engine builder may delete the alias.
2. **Real hosts**: with FS-2 (`hr.employee`, `portal: True`) and FS-3 (`hr.contract`) merged,
   nothing here changes; the tests register test-only hosts by patching `_pbfs_hosts` (the patch
   replaces the merged hosts during the test run — keep it). Check after merge: Records Master
   lists a real custom field; Mapping lane shows it; L42 anchors render on the Field library.
3. FS-2 must not add its own My details section — My Payobook belongs to this module (R14 block).
4. Engine busy rail across databases: already fixed on fs-1 (FS1-8) — nothing to do.
5. `pb_learn` vi_VN.po was restored after the generator (memory trap); `--check` clean.

## 7. Deploy notes (not done here)
Install `pb_form_studio_reach` everywhere `pb_form_studio` is; `-u biz_access,pb_learn`;
asset purge (one backend xml). Silent: no field, layout, job, mail, route or rule row is created
(the "Company details" request kind uses the existing My details route).

## 8. New gotchas (ledger rows)
- FS5-1 (same finding as FS1-8, now fixed in the engine) Local databases copied from one template
  share table oids; `pg_locks` checks must filter `l.database`.
- FS5-2 A Records Desk cell with `missing: True` reads "has no contract" in the review — use a blank
  cell (`v: None, label: ''`) for "not for this person".
- FS5-3 Payroll officers' group implies HR user on this build: a "pay team without HR" test user
  still sees HR-only fields; test hiding with an administrator-only field.

## 9. Owner questions (plain)
- A link field (for example "Department") can be changed on My Payobook only when it points to a
  country, a department or a job — a list of people's names is never shown to an employee. Is that
  right, or should employee and contact links be changeable too?
- People search, Mapping and pay runs still read a value that was filled before somebody limited the
  field to some countries. Should limiting a field to a country also clear the values of people in
  other countries?
