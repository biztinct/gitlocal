# DOCSTUDIO phase R — Report builder: build your own report from any data (study line 900)

Branch `docstudio-r` (cut from `origin/19.1` @ 4eaee9db3). New module **`pb_report_builder` 19.0.1.0.0**.
No file outside `pb_report_builder/` was touched (plus this report). Not merged, not deployed.

## 1. What was built, per item

| Item | Built |
|---|---|
| R1 Home tab | "Build a report" tab in the Insights hub through `registry.category("pb_insights_hub_lens")` (sequence 30; `pb_insights_hub` untouched, still Python-free) + a ⌘K row (`pb_hub_palette`, "Build a report", sublabel Insights, `probe` = `pb.report.builder.can_open`). Start view: hero line, **My reports** (mine first, then shared with me: subject chip, columns count, Grouped chip, Shared / Shared by <name>, Last opened), **Start from an example** (10 recipes). Quiet empty state ("No saved reports yet. Start from an example below, or press New report."). |
| R2 Subjects | Server registry `pb.report.builder._pbrb_subjects()` (`models/subjects.py`): 10 subjects, each listed only when its model exists; each opens only when `has_access('read')` is true for the reader, otherwise the tile is locked with the reason ("You cannot see Applicants. Ask your administrator for Hiring access."). Labels built inside the method with `self.env._`. Extend by overriding `_pbrb_subjects` / `_pbrb_counts`. Table in §2. |
| R3 Fields from anywhere | Every subject with an employee link gets an **About the person** section (19 People fields through the link, plus the customer's own employee fields). People gets **Counts from other areas**: time off days taken, days attended, assets held now, training finished, expense claims still open, goals set — one `_read_group` on the other model per count, as the reader, for the chosen period. Own fields (Form builder, "Show in lists", read as the reader through `pb.form.studio.fields_for(model,'list')`) appear as **Your own fields**; standard-field renames from `_pbfs_std_rules` are used as labels. |
| R4 Build by clicking (hero) | Left: "Each row is" switch, field search (`/`), grouped field list with type icons, a "Pay" badge on the pay field, tick when on. Centre: the column header appears the moment a field is clicked, its cells shimmer, then the real values slide in (first 50 rows), row count above ("548 rows"). Column menu: sort (words follow the type: A to Z / Oldest first / Smallest first), Filter by this, Total (Sum / Average / Count / No total), Group by this, Hide; drag a header to reorder (no new read: the cell map follows). Filter bar: chips written as sentences by the server ("Country of Work is one of Vietnam"), editor with is / is not / contains / is one of / is empty / is not empty / between, per type (searchable pick-list for linked fields, chips for choices, Yes/No, number and date ranges). Period picker: Any time, This month, Last month, This quarter, This year, Last 12 months, Next 30/60/90 days, Pick dates; "by" which date when the subject has several (People: "Counts only", Start date, Leaving date). |
| R5 Group and total | Group by up to two fields (chips + "Group by…" + column menu); collapsible groups with counts and subtotals, child groups, rows loaded per group (50, "Load more in this group"); grand total row; "Summary only" switch. Groups sorted by name (dates by date, "Not set" last). Money is totalled per currency (grouped by the currency too): "$4,500.00 · ₫75,000,000", never one sum. |
| R6 Save, share, Excel | `pb.report.definition` (cloned from `pb.explorer.view` + its rules): name (80), owner, shared, subject, spec, sequence, last opened; 50 per owner said plainly. Save (⌘S) / rename / Share toggle / Make a copy / Delete (inline confirm) / Excel (whole result, cap 10,000 rows, note in the file and on screen when hit; grouped files lead with the group fields and carry subtotal rows; Summary-only files carry one row per group). Read-only view of somebody else's shared report (Make a copy to change it). ⌘Z undoes the last layout change (30 steps). |
| R7 Examples | 10 recipes built from code on demand (nothing stored): time off + attendance + assets per person; time off by department this year; people by country and contract type; joiners this quarter; leavers this year; contracts ending in the next 60 days; assets held by person; applicants by open role and stage; training still to finish; expense claims waiting for approval. Hidden when the reader cannot open the subject or keeps fewer than two of its columns. |
| R8 C1/C2 | `pb.report.definition._pbxl_table()` returns exactly the ledger C1 shape, read as the calling user (see §5). The toolbar renders `registry.category("pb_excel_layout").get("button", null)` with `{sourceModel: "pb.report.definition", sourceId, disabledReason?}` ("Save the report first." / "Save your changes first."); nothing when absent; no dependency either way. |

## 2. The registry — what each report can contain

"About the person" (every subject except Open roles and Applicants): Department, Job position, Job title,
Manager, Company, Country of Work, Location, Employee type, Contract type, Start date, Leaving date,
Why they left, Still working here, Work email, Work mobile, Gender, Date of birth, Nationality, ID number,
plus the customer's own employee fields marked "Show in lists". Each field is offered only when the
reader may read it (field groups, Access Studio).

| Each row is | Model | Fields of its own | Period by | Scoped by |
|---|---|---|---|---|
| People | `hr.employee` | Name + the 19 person fields; Counts from other areas (6); own fields | Counts only / Start date / Leaving date | company, department |
| Contracts | `hr.contract` | Contract, Employee, Department, Job position, Company, Contract type, Status, Start date, End date, End of trial, Working hours, **Contract pay** (pay groups only); own contract fields | Start date / End date / End of trial | company, person's department |
| Time off requests | `hr.leave` | Employee, Kind of leave, First day, Last day, Days, Status, Reason given | First day / Last day | person's company, person's department |
| Attendance | `hr.attendance` | Employee, Check in, Check out, Hours worked, Extra hours | Check in | person's company, person's department |
| Open roles | `pb.hiring.requisition` | Reference, Role, Department, Company, Country, How many people, Status, Wanted by, Opened on, Closed on, Recruiter, Days open, Applicants | Opened on / Wanted by / Closed on | company, department |
| Applicants | `hr.applicant` | Name, Job position, Open role, Stage, Status, Department, Company, Applied on, Hire date, Source, Recruiter | Applied on / Hire date | company, department |
| Assets | `pb.asset` | Asset code, What it is, Category, Kind, Status, Held by, Company, Country, Serial number, Bought on, Warranty ends, Cost | Bought on / Warranty ends | company, holder's department |
| Training | `pb.training.assignment` | Employee, Course, How far it has got, Why, Put on it, To be finished by, Finished on, Test score | Put on it / To be finished by / Finished on | company, person's department |
| Expense claims | `pb.expense.claim` | Reference, Employee, Status, Total (per currency), Receipts, Sent on, Decided on, Paid on, Company | Sent on / Decided on / Paid on | company, person's department |
| Goals | `pb.goal.set` | Goal sheet, Employee, Goal year, Department, Manager, Status, Goals, How far along, Deadline | Deadline / Created on | company, person's department |

Counts from other areas (People only): Time off days taken (approved, first day in the period), Days
attended (distinct check-in days in the period), Assets held now, Training finished (finished in the
period), Expense claims still open (sent or approved, not paid), Goals set (goal sheets created in the
period). A count column is offered only when the reader may read that model.

## 3. Tests

Local database `docstudio_r_base` = copy of `wf2p6c_uitpl` upgraded to this tree (13 behind modules `-u`)
+ Form builder ×5 + People reports installed, then `pb_report_builder -i`. Dropped at the end.

Final run on a fresh copy (`pb_report_builder,pb_insights_hub,pb_insights,pb_people_reports`, 108 tests):
**pb_report_builder 24/24 pass; 3 failures elsewhere = the baseline exactly** (recorded on the same copy
before the module existed: `test_82_tiles_reconcile_with_the_records`, `test_the_lens_order_matches_the_mockup`,
`test_the_feature_set_is_intact`).

| # | Case | Result |
|---|---|---|
| 1 | Install on the live module set, nothing created | PASS — `-i` clean (no ERROR); module data = 2 models, 15 fields, 1 access line, 3 rules, 1 inherit; 0 saved reports, 0 jobs (`test_01` too) |
| 2 | Subjects only when model exists and readable | PASS (`test_02`: absent model never listed or run; HR user without Hiring sees Applicants locked with the reason and is refused; outside the gate = sentence, not screen) |
| 3 | People + 6 fields + own field = direct ORM read | PASS (`test_03`, own field made with the Form builder) |
| 4 | Time off + person's department + this year + grouped total = independent `_read_group` | PASS (`test_04`; opening a group returns exactly its rows) |
| 5 | Counts (time off days, days attended, assets held) = independent counts for 5 people | PASS (`test_05`) |
| 6 | Filters, each operator × type | PASS (`test_06`: text, link, choice, bool, number, date, datetime; wrong-typed values refused) |
| 7 | R1 grep gate; fuzz | PASS (`test_static.test_07`; `test_07`: 14 hostile specs refused on screen and Excel, bad group key, choices on a non-link field) |
| 8 | Shared report, three readers, Excel = screen | PASS (`test_08`) + browser (HR user sees "1 column is hidden…", no money anywhere on the page) |
| 9 | Access Studio masks ID number | PASS (`test_09`: gone from the list, from the shared report with a note, from Excel and from "About the person" of other subjects; no traceback) |
| 10 | Two currencies in one column | PASS (`test_10`) + walk file: grand total "1,181,500.00 USD · 1,000,068,000.00 VND" |
| 11 | Save, reopen, duplicate, share, delete, caps | PASS (`test_11`) + browser (⌘S save, Share toggle) |
| 12 | Excel cap + formula text | PASS (`test_12`) + walk database: 12,000 attendance rows → file of 10,000 rows + the note line; `=HYPERLINK(...)` written as text |
| 13 | C1 shape | PASS (`test_13`) |
| 14 | C2 button | PASS (`test_static.test_14`) + browser: fake component registered → "Fill my Excel layout pb.report.definition#168" in the toolbar; not registered → nothing |
| 15 | 2,000 people × 12 columns < 1.5 s | PASS — 2,008 people, 12 columns (9 fields + 3 counts, this year, 2 totals): first page **0.66 s**, grouped by department **0.47 s** (best of 3, machine shared with other builders). Full Excel of the same: 10.8 s; 12,000-row attendance Excel: 16.6 s |
| 16 | Existing suites = baseline | PASS (see above) |
| 17 | Browser walk inside the hub | PASS — administrator at 1440 and 1280: home → example → subject switch → click 6 fields (shimmer then values) → group by from the column menu → Sum total → open a group → filter "Country of Work is one of Vietnam" → name + ⌘S → Share → Excel (file 10.7 kB, "Payobook Vietnam people with counts 2026-11-22.xlsx") → ⌘Z → `/` → drag a header; HR user (only the "Build a report" tab, shared pay report read-only with the note, no Applicants example); Vietnamese user (tab "Tạo báo cáo", whole screen translated). Console clean on every page |
| 18 | PO parse gate; static gates | PASS (`test_18a` white-label in templates/strings/msgstr, `test_18b` no emoji + no "--" in XML comments, `test_18c` both .po parse with babel, cover all 314 .pot terms, keep every placeholder) |
| 20, 21 | Examples follow the reader; sort one link away pages exactly | PASS |

## 4. Safety rails — evidence

| Rail | Evidence |
|---|---|
| R1 no superuser switch, no raw SQL | `test_static.test_07_r1_…` greps every .py/.js/.xml of the module (tests included, nothing allowed). Rows via `search`/`read`/`_read_group` as the reader; counts via `_read_group` on the other model as the reader. |
| R2 pay | "Contract pay" carries `pay: True`; offered only when `pb.contracts._cd_unmask_wage()` is true (payroll manager or admin). For anyone else the column, its filter, its sort and its total are dropped with a note (case 8) — the filter is dropped, so nothing is ordered or narrowed by pay. |
| R3 shared reports never widen | Case 8: administrator / HR user without pay / division-scoped manager open the same shared report: all rows + pay; pay dropped + 2 notes; only their department. Excel equals the screen for each. |
| R4 spec validation | `_clean_spec` on every call: unknown top-level keys, subject, column, operator, total or period refused; filter values type-checked (ids must be ints, choices strings, dates ISO, numbers numbers); group keys type-checked; no domain or field name from the client reaches the ORM (case 7, 14 hostile specs on `run` and `export_xlsx`). |
| R5 Excel | Text written with the formula-safe writer (`_set_text`, quote prefix); case 12 (`=HYPERLINK(...)` is text). Built from the same cleaned spec as the screen, so it holds only what the reader may see (cases 8, 9). |
| R6 silent install | Case 1: the module's data is models, fields, access lines and three record rules; no cron, no mail, no records. |
| R7 never two currencies | Case 10 (screen total "a · b", grouped by company one currency each, Excel grand total never 6,000, exporters get a currency column beside every money column). |
| R8 white-label, plain words, vi + id | Case 18 (no brand word in templates, `_()`/`_t()` strings or msgstr); 314 terms translated to vi_VN and id_ID; browser walk in Vietnamese. |

## 5. Contracts other phases rely on

* **C1** `pb.report.definition._pbxl_table()` → `{'title': str, 'columns': [{'key','label','type'}], 'rows': [[python values]], 'truncated': bool, 'note': str}`. Types: text / number / money / date / datetime / bool. A money column is followed by `<key>__currency` (type text, label "<field> currency"). Datetimes are naive, in the reader's time zone. A Summary-only report answers one row per group (group labels, "Rows", then the totals). Read as the calling user: another reader gets their own table (case 13: the HR user gets no pay column and a note).
* **C2** consumed as specified (case 14 static + browser walk with a fake registered component: shown with `pb.report.definition#<id>`, absent otherwise).
* Extension points: override `_pbrb_subjects` / `_pbrb_counts` / `_pbrb_examples` (call `super()`); field tuples are `(key, path, label, dict(pay=…, currency=…))`, dates `(key, path, label, None)`.
* RPC names on `pb.report.builder`: `schema`, `can_open`, `run(spec, offset, limit, group=None)`, `values_for(subject, key, search)`, `export_xlsx(spec, name)`, `my_reports`, `save_report(name, spec, shared)`, `update_report(id, vals)`, `remove_report(id)`, `duplicate_report(id)`, `open_report(id)`, `examples`.

## 6. Deviations from the handover

* RPC names `save_report / update_report / remove_report / duplicate_report / open_report` instead of `save / update / remove / duplicate / open`: `update` is a method every model already has (record.update), overriding it would break the ORM.
* The "Joiners and leavers this quarter" recipe is two recipes ("Joiners this quarter", "Leavers this year"): one report has one period date. Added "Time off, attendance and assets per person" (the mix that shows what the builder is for) and "Expense claims waiting for approval" — 10 in all.
* Periods "Next 30 / 60 / 90 days" added (needed by "Contracts ending in 60 days").
* Test 9 marks the ID number as masked by patching Access Studio's decision point (`pb.access._studio_field_allowed`) for the HR user, not by publishing a full role package (that needs an owner + reviewer + profile workflow). The path exercised (`_has_field_access` → Access Studio) is the one a real package uses.
* Test 12's 12,000-row file was produced on the walk database (12,000 attendance rows: file has 10,000 rows + the note "This report has 12,000 rows; the first 10,000 are included."); the unit test proves the cap logic with the cap patched to 3 (a 12,000-row fixture takes ~30 minutes to create on this machine).
* `test_the_lens_order_matches_the_mockup` **fails at baseline** on `origin/19.1` (the hub file has a third lens, `reports`, the test expects two). Unchanged by this phase (it reads only `insights_hub.js`).

## 7. Deploy notes

* New module, install with `-i pb_report_builder` on all five databases (tenant module-sync rule). Depends on `base, web, hr, pb_hub, pb_insights_hub, pb_group, pb_import_kit, pb_filter_kit` — all already installed everywhere. No data migration, no job, no mail, nothing touches pay. Tier: normal (new module, read-only screen, new table `pb_report_definition`).
* Asset purge + `web.assets.version` bump (new JS/SCSS/XML).
* Lessons: no existing screen was changed, so no `pb_learn` anchor or lesson text is affected. A lesson for the new tab is left for later.

## 8. Design self-score (mandate: "extreme WOW, intuitive, out-of-this-world experience, best in class")

Benchmark: Airtable / Notion table building. Self-score **8 / 10**.

* Hero (R4) works as specified: click a field, the header appears at once, its cells shimmer and the
  values slide in with a soft indigo flash; row count updates; ⌘Z takes the click back.
* Zero dead ends: locked subjects say why and whom to ask; hidden columns and dropped filters say so in
  an amber line; errors show the reason with "Try again"; empty table teaches in one line with
  quick-add chips; "No rows match. Try a wider period or fewer filters."; shared reports open read-only
  with "Make a copy".
* Keyboard: `/`, Enter, ⌘S, ⌘Z, Escape. Lucide icons, no emoji, no gradients, locked indigo palette,
  zero counts grey (quiet board), reduced-motion respected.
* Walked inside the Insights hub at 1440 and 1280, as administrator, HR user and in Vietnamese; console
  clean throughout.
* Short of 10: no column resize, no inline cell click-through to the record, filters on counts not
  possible, and the ⌘K-only door for HR officers (owner question 1).

## 9. Owner questions (plain)

1. **Who should see "Build a report" in the side menu?** Today the Insights button in the side menu is only for people with the payroll analytics right. HR officers can open the report builder (it is built for them) but only through the search box (⌘K) or a link. Should HR officers also get the Insights button? Cost: a small change to the side menu; they would see only the tabs they are allowed (just "Build a report" for most HR officers).
2. **Contract pay in a report shows the company's money.** A person paid by a scheme in another money (for example an Indian scheme inside a Vietnamese company) shows their contract pay in the company's money, as the contract list does. Should the report use the scheme's money instead? Cost: slower reports with many people (one look-up per person).
3. **Two "Department" columns.** On contracts, time off and goals, "Department" (stored on the record) and "About the person › Department" (where the person is now) can differ for people who moved. Both are offered and both read "Department" in the table header. Should the person's one read "Department now"?

## 10. Left for later

* Charts, scheduled email, PDF output, Excel layouts (phases B / X / wave 2, binding non-goals).
* A `pb_learn` lesson and anchors for the new tab.
* Resizable column widths and a saved column width per report.
* Filters on "Counts from other areas" columns (e.g. "people with more than 5 days off") — counts are worked out per page, so a filter would need a different read.
* Scheme money for contract pay (owner question 2).

## 11. Gotchas → ledger rows

* DS-R1 | Odoo 19's term extractor (`odoo/tools/babel/python_extractor.py`) mis-reads tuples after `_("…")` when they contain `{}` or are three-long: `('job', 'job_id', _("Job"), {})` put the keys `job`, `department`… into the .pot as terms | use `dict()` (or `None`) in such tuples; check the .pot for lowercase keys.
* DS-R2 | `_read_group` ordering on a dotted many2one (`employee_id.department_id desc`) orders by the linked record's **id**, not its name; grouping by `id` returns records | order by `employee_id.department_id.name`; a one-row-per-record `_read_group(domain, [<path>, 'id'], order=…, offset, limit)` gives exact paging on a field one link away.
* DS-R3 | `hr.employee.version_id` is not stored, but inherited fields (`department_id`, `sex`…) are still sortable/groupable through it | ask the field: `field._description_sortable(env)` / `_description_groupable(env)` / `_description_searchable`, never `field.store`.
* DS-R4 | `hr.contract.department_id` (a stored compute) can be empty on contracts made by code, and `hr.contract.currency_id` is not stored | scope contracts by `employee_id.department_id`; total money by `company_id.currency_id`.
* DS-R5 | Attendance and assets have record rules: an HR officer without the attendance manager / asset rights sees only their own team's (or no) rows — a report built "as the reader" is correctly smaller for them | tests give the reader the real rights; never compare against a superuser count.
* DS-R6 | TransactionCase `assertRaises((A, B))` fails with "issubclass() arg 1 must be a class" (Odoo wraps assertRaises) | assert a common base (`UserError`).
* DS-R7 | Creating employees on the local template takes ~1.2 s each (hooks of many modules): a 2,000-person seed took ~45 minutes | seed small, or seed once and keep the copy for the walk only.
