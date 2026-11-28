# FS-8 facts pass — reports split and filtered by the customer's own fields

Read at `origin/19.1` = `df98e07cd` (fetched 2026-11-20). All `file:line` are at that commit.
During the build `origin/19.1` moved to `e69bebcc4` (FS-7 merged and live); the branch was
rebased onto it. Nothing in `pb_explorer` changed between the two; the `pb_form_studio` line
numbers in §4/§6 moved (FS-7 added ~80 lines to `form_studio.py`) but no method used here changed.
Engineering readers only. Written BEFORE any code (handover FS-8 "Facts pass first").

## 1. How the Explorer's fact tables are built — stored rows, rebuilt from payslips

| Fact | Where |
|---|---|
| Three STORED tables, rebuilt from payslip truth (not SQL views, not on-the-fly): `pb.fact.run` (header), `pb.fact.line` (T1: run × division × department × category_type × component), `pb.fact.emp` (T2: run × employee × category_type) | `pb_explorer/models/pb_fact.py:49, 138, 187` |
| `pb_fact_line` has NO employee column; `pb_fact_emp` has `employee_id` (:203), `run_id` (:194), `month` / `quarter` / `year`, as-of `department_id` / `job_id`, `amount` | `pb_fact.py:139-184, 192-245` |
| The one aggregate behind both tables; the emp grain sums `pl.total FILTER (WHERE NOT roll-up)`, so money on T2 equals money on T1 (roll-ups skipped on both) | `pb_explorer/models/pb_fact_builder.py:222-289` (emp :271-288) |
| Facts are freshened per query (`ensure_fresh`, token per run); only `pb.fact.builder` writes | `pb_fact_builder.py:322`; facade `pb_explorer.py:595-628` |
| The facade is READ-ONLY (asserted by `test_08`); writes live in `pb_explorer_view.py` | `pb_explorer.py:10-13` |

**Consequence for FS-8:** an own field is NOT in any fact table and must not be (no schema change
per query, no rebuild). The value is joined at read time from the live record: the employee's
current value through `pb_fact_emp.employee_id`, the contract's through the payslip of that run
(`hr_payslip.contract_id`, `om_hr_payroll/models/hr_payslip.py:78`). Every own-field split or
filter therefore runs on the employee grain (T2), exactly like the built-in "Job position"
split (`_T2_ONLY`, `pb_explorer.py:118`). `hr_payslip` is indexed on `payslip_run_id` only (no
`employee_id` index, checked on the demo copy) → resolve "the contract of each payslip" as ONE
`DISTINCT ON (run, employee)` sub-select restricted to the runs in scope, hash-joined — never a
per-row lateral lookup.

## 2. Where dimensions and filters are declared — module constants, read in many places

| Item | Where | Trap for a run-time dimension |
|---|---|---|
| `_DIMENSIONS` (registry) | `pb_explorer.py:119-151` | module constant: unknown key → default `department_id` in `_clean_spec` :448 |
| `_FILTERS` (key → column, type) | `:171-192` | `_where` does `_FILTERS[key]` (:817) → KeyError for a new key; `_clean_spec` drops unknown keys (:455) |
| `_resolve_table` (line vs emp) | `:551-592` | new keys must force `emp` |
| `_dim_expr` | `:880-893` | `_DIMENSIONS[d]` |
| `_raw` FROM `pb_fact_{tbl}` (three statements) | `:899-961` (:926, :944, :954) | needs a FROM seam to carry the joined value |
| `_heads` FROM `pb_fact_emp` | `:663-682` | own-field FILTERS must apply to the people count too |
| `_dim_remap` | `:971` | `_DIMENSIONS[spec['dimension']]` → KeyError |
| `_query_derived` numerator hard-coded to `'line'` | `:1266` | with an own field the numerator must read `emp` |
| `_period_weights` table from the measure only | `:1666` | with an own-field filter it must read `emp` |
| `_dim_labels` | `:1707-1733` | `_DIMENSIONS[dimension]` |
| `get_schema` dimensions + filter options | `:1737-1908` | lists only the registries |
| `drill` cell + filters, `JOIN pb_fact_emp fe` | `:1950-2116` (cell :1972-2006, join :2072) | needs the same FROM seam |
| narrative `_emp_map` (waterfall) | `:2478-2494` | filters by a fixed key list |
| `_anomalies` | `:2593-2678` | reads T1 only and ignores filters today — out of scope, stated as a limit |
| `_ask_keywords` / `_ask_llm` | `:2716, :2890` | list the registries |
| Labels in the reader's language: `_dimension_words()` etc. | `:243-277` | fallback prints the raw KEY |
| Browser: `FILTER_META` hard-coded filter list | `pb_explorer/static/src/js/explorer.js:32-47`; `filterFields` :1301, `activeFilters` :1283 | an own-field filter would show its raw key |
| "By" picker / "Add filter" picker | `pb_explorer/static/src/xml/explorer.xml:308-326, 466-495` | one flat list, no help line |
| The browser never adopts the server's cleaned dimension (only the period) | `explorer.js:279-303` | a dropped split would leave the chip showing a raw key |

Nothing outside `pb_explorer` reads these internals (grep: only `pb_insights/models/module_insights.py:189`
calls `_require`). `pb_form_studio_reach/tests/test_reach.py:262-272` (FS-5 test 05) asserts that NO
custom field reaches the Explorer schema — it must change with FS-8 (it is in an allowed module;
FS-7 does not touch that file).

## 3. How the Excel export names columns — the "department_id" leftover

| Item | Where |
|---|---|
| Column heads already use labels (`dimension_label`, period labels, "Total") | `_export_rows` `pb_explorer.py:2120-2168` (:2148) |
| **The FILE NAME uses the code keys**: `'%s_%s_by_%s_%s'` with `spec['measure']`, `spec['dimension']` → `payobook_net_by_department_id_….xlsx` (the WDGAP_DEFERRED leftover, main checkout `docs/handovers/wdgap/WDGAP_DEFERRED.md:20-21`) | `_export_name` `:2170-2177` (CSV and Excel) |
| The "Filters" line of the workbook prints the raw key for any filter not in `_DIMENSIONS` (`basis`, `split`, `employee_id`, `cycle`…) | `_xlsx_filter_words` `:2276-2292` (`name = key` :2290) |
| Regular email attachment is named from the VIEW name (already words) | `pb_explorer_schedule.py:439-443` |
| Tests that read the name: must end `.xlsx`, carry the month key, no vendor word | `tests/test_wdgap_qf2.py:317-318`, `tests/test_look_p4.py:229` |

## 4. How access is applied

- Gate: `_require` — administrator, payroll base manager, analytics user, super admin
  (`pb_explorer.py:46-50, 374-385`); then reads are `sudo` / raw SQL.
- Company scope survives sudo: every statement carries `company_id IN _co_ids()` (`:387-399`);
  division heads narrowed by `_visible_divisions()` (`:791`, GROUP P7).
- Saved views: record rules own-or-shared to read, own to change, settings admins anything
  (`security/pb_explorer_rules.xml`); `open_view` re-cleans the stored spec and sets a plain
  "part of this view no longer exists" note when `_pbx_drift` sees a dropped piece
  (`pb_explorer_view.py:97-109, 215-243`). Regular sends rebuild AS THE RECIPIENT
  (`pb_explorer_schedule.py:380-403`) — so any server-side check keyed on the caller also
  protects the emailed workbook.
- **Own-field visibility is the engine's** (FS-1 V1/§2): `pb.form.studio.fields_for(model,
  'list')` returns custom fields marked "Show in lists" that the CALLER may read
  (`_has_field_access`, `pb_form_studio/models/form_studio.py:1597-1643`, check at :1627;
  FS-5's field rules hook the same method). Because the Explorer reads with sudo/SQL, the
  visibility check must be made in the query path (spec cleaning), from `fields_for` as the
  real user — never from the picker only.
- Country of Work (R10): `_pbfs_applies` (`form_studio.py:510-516`) — a limited field applies only
  where the record's country is in the list; no country recorded → only all-country fields.
  Employee host country = `pbfs_country_of_work_id`, computed from the stored
  `hr_employee.payroll_country` (ISO code) (`pb_form_studio_people/models/hr_employee.py:20-35`);
  contract host = the same person's country through the contract's employee
  (`pb_form_studio_contracts/models/hr_contract.py:1-14`, host :55). In SQL:
  `UPPER(hr_employee.payroll_country) IN (<codes of the field's countries>)`.

## 5. Adding a dimension at run time, with no upgrade and no restart

- A field is created by `ir.model.fields.create` → `_setup_models__` → `registry_invalidated`,
  signalled after commit; every other worker reloads on its next request (FS1 V4, test 11 there).
  `fields_for` reads `pb.form.field.meta` on every call (no cache).
- So: the Explorer must NOT keep own fields in a module constant or an `ormcache`. Build the list
  of own-field splits per call from `fields_for` (as the reader), and the SQL per query from
  `Model._fields` (column present only once the registry knows the field). No column, view or
  index is added by FS-8; nothing to rebuild.
- Seam choice: `pb_explorer` gets small GENERIC hooks (no product or Form-builder word in it):
  `_pbx_extra_dims()`, `_pbx_extra_source(keys, run_ids, alias)`, `_pbx_extra_labels(key, values)`,
  `_pbx_extra_options(key)`, `_pbx_extra_group()`; every registry read above goes through a
  `_pbx_dim_meta(key)` helper. A NEW bridge module `pb_form_studio_explorer` (depends
  `pb_form_studio`, `pb_explorer`) answers them from the engine. Without the bridge (or with no
  marked field) every hook answers nothing → the Explorer is byte-for-byte today's.

## 6. Delete and saved views

- `_pbfs_reference_finders` (`form_studio.py:195-201`) — a non-empty answer BLOCKS a delete and
  shows as "Used by" (`delete_field` :1267-1270; overlay "Cannot delete" `studio_overlay.xml:250`;
  Field library sheet `field_library.xml:144-146`). Precedent: People/Contracts saved views
  already block (`_pbfs_refs_saved_views` :1201-1211). → the bridge adds
  `_pbfx_refs_report_views` (saved Explorer views whose stored question splits or filters by the
  field; names = view names).
- Other ways a split disappears from a saved view without a delete: "Show in lists" switched
  off, "Who can see it" narrowed, a reader without the right opens a SHARED view. `_clean_spec`
  must drop the key (fall back to no split, "Total") and `open_view` must say so in one plain note.

## 7. Wording on screen today

- The engine switch is "Show in lists — Offered as a column on the lists of these records."
  (`pb_form_studio/static/src/xml/studio_overlay.xml:193`; FS-7 rewrites this file, the line is
  :252 on `origin/fs-7`). FS-8 reuses `list_ok` (no new flag) and changes the sentence from the
  bridge by a template extension (no engine file touched): "…and as a split and a filter in
  reports." Field library row `field_library.xml:111` keeps its title.

## 8. Eligible kinds (handover constraint 1) mapped to field types

| Form builder kind | ttype | Split key value |
|---|---|---|
| Choice list | selection | the choice key; label = the choice's label in the reader's language |
| Yes / No | boolean | `true` / `false` (empty = No, as the screens show it) |
| Text (short) | char | the text (top 24 by size, the rest counted as "more", like every split) |
| Date | date | `YYYY-MM` / `YYYY-Qn` (calendar quarter) / `YYYY` — three splits per date field |
| Link to a record | many2one | the record id; label = its name |
| Long text, File, Whole number, Decimal, Money | text, binary, integer, float, monetary | NOT offered (non-goal; numbers/money: range filters later) |

Two extra buckets: "Not filled in" (`__none__`) and "—" for people in a country the field is not
used in (`__na__`, R10).
