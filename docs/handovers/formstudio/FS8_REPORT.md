# FS-8 — Reports split and filtered by the customer's own fields — report

**Status: BUILT, NOT LIVE.** Branch `fs-8` (rebased on `origin/19.1` = `e69bebcc4`, FS-7 live).
No server was touched. Facts pass: `FS8_FACTS.md` (same folder, written before the code).

## 1. What was built

| Piece | Where | What |
|---|---|---|
| Generic seams in the reports module | `pb_explorer` **19.0.2.7.0 → 19.0.2.8.0**: `models/pb_explorer.py`, `models/pb_explorer_view.py`, `static/src/{js,xml,scss}`, `i18n` | Hooks `_pbx_extra_dims / _pbx_extra_source / _pbx_extra_labels / _pbx_extra_options / _pbx_extra_group / _pbx_extra_gone` (all answer nothing by default). Every registry read goes through `_pbx_dim_meta` / `_pbx_dim_word`; the three aggregate statements, the people count, the drill, the movement story and the month strip read FROM `_pbx_from(...)` (the fact table, or a one-statement stand-in carrying the extra columns). Run-time keys contain `:` and are only kept by `_clean_spec` when offered to THIS reader now; a dropped split falls back to no split ("Total"), never to a different one. No word of the Form builder in this module. |
| Download names + filter line | same | File names use screen words (`payobook_net_pay_by_department_….xlsx`, was `…_net_by_department_id_…`); the workbook's "Filters" line names Basis / Where they work / Employee / Kind of run in words with value labels (it printed `basis: approved`). |
| Pickers | same (JS/XML/SCSS) | "By" and "Add filter" show a "Your own fields" group (two-line rows: field, then "Employee · as it is today" / "Contract · as on each payslip") and ONE sticky help line. Filter names come from the server (`filterLabel`), never a raw key. The board adopts the server's cleaned split and drops filters the server dropped. Menus near the right edge on a phone are moved back on screen (pre-existing clipping, made worse by the wider menu). |
| Saved views | `pb_explorer_view.py` | A view whose split/filter is no longer offered opens without it with one sentence ("…a field that is not available to you any more, so it opened without it."). If the field is DELETED, the owner's view stops carrying it on that first open → the note appears once. A shared view opened by someone else is never changed. |
| New bridge | **`pb_form_studio_explorer` 19.0.1.0.0** (depends `pb_form_studio`, `pb_explorer`) | Answers the hooks from the engine: `fields_for(model, 'list')` as the real reader (custom fields marked "Show in lists" that this person may see) on employee and contract; kinds choice / yes-no / short text / link / date (three splits: by month, quarter, year). Employee value = today's; contract value = the contract of each payslip of the run (`hr_payslip.contract_id`, newest if two). Country of Work (R10) → "—"; no country recorded → "—" for a limited field (same rule as `_pbfs_applies`). Saved reports that use a field are shown as "In reports" / a count chip in the Field library and WARN in both delete confirmations (shared and own reports named, other people's private reports only counted) — they never block the delete (follow-on, §10). On delete the field is taken off every affected saved report and its name is left in `_lost`, so the report opens without it and says so once. "Show in lists" help now reads "Lists and reports: …" (template extension, no engine file touched). vi + id. |

Not touched: `pb_form_studio` engine files, any forbidden module, any standard addon. `pb_form_studio_reach`
test 05 (no custom field in the Explorer schema) still passes unchanged: its fields are not marked
"Show in lists".

## 2. Verified facts that drove the design (details and file:line in FS8_FACTS.md)
- Explorer = stored, rebuilt fact tables; only the per-person table has the employee → own fields
  live there (like "Job position"); nothing stored, no rebuild, no column per query.
- Explorer reads with elevated rights → visibility must be checked in the query path:
  `_clean_spec` asks `fields_for` as the reader for EVERY call (screen, link, saved view, regular
  email — which runs as the recipient).
- New fields: the engine signals a registry reload; nothing in FS-8 is cached beyond one request
  (the per-request memory is keyed on user, groups, language, companies and a fingerprint of the
  field settings rows) → a field made on one worker is offered by every worker on the next request.

## 3. Tests (numbered as the handover)

Baseline on the same template copy at `origin/19.1` `e69bebcc4` (pb_explorer at 19.0.2.7.0, no bridge):
`/pb_explorer, /pb_form_studio_reach, /pb_form_studio` — **163 tests, 0 failed**.
Branch (`-u pb_explorer -i pb_form_studio_explorer`): explorer 101 + reach 51 + bridge 13 →
**141 tests, 0 failed**; engine 41 + bridge 13 (separate run, bridge installed) → **48, 0 failed**;
final re-run after the last change: see §3a.

| # | Case | Result |
|---|---|---|
| 1 | Headcount split by a choice field ("Medium 2, Large 1"); money split adds up to the unsplit total to the cent; cost per person; yes/no, short text, link split with screen words; component measure refused in words | PASS (test_01) |
| 1b | Unmarked, whole-number and long-text fields never offered; contract field and three date splits offered | PASS (test_01b) |
| 2 | Filter by a choice field: options in screen words + "Not filled in"; people count, money, drill (whole and one cell) and the movement story all honour it | PASS (test_02) |
| 3 | Date field by quarter ("Q1 2026", "Q2 2026", "Not filled in", calendar order), by month, by year; filter by a quarter | PASS (test_03) |
| 4 | Contract field on a payslip report: April money under the OLD contract's value, May under the NEW one; empty contract → "Not filled in" | PASS (test_04) |
| 5 | Visibility: payroll manager without HR sees neither the HR-only nor the admin-only field — picker, filter list, schema text — and a direct call with either (split, filter, drill, Excel, link) gets no split, no filter, no label, no value; HR+payroll sees the HR one only; administrator sees both | PASS (test_05); also on screen (walk) |
| 6 | Field limited to Vietnam: India person "—", Vietnam people their value, no Country of Work "—"; the India value is kept | PASS (test_06) |
| 7 | (follow-on rule) Saved reports never block: library + Studio carry `report_uses` (3 = own + shared named, "Private reports of other people: 1" — that report's name and owner appear nowhere in the payload); delete goes through; every affected report's stored question loses the field; each owner's next open: no split / no filter, note naming the field; second open: no note; the board answers | PASS (test_07); on screen: warning sheet with Delete enabled, deleted, saved view opened with the note, then without |
| 7c | Field removed another way (straight from the field list): view opens without it, note once | PASS (test_07c) |
| 7b | "Show in lists" switched off → a shared view opens without the split, note shown, owner's stored question kept | PASS (test_07b) |
| 8 | Excel/CSV names in screen words (`…_net_pay_by_department_…`, `…_people_by_job_position_…`, `…_by_demo_shirt_size_…`), no `department_id`, no field code, no colon, no vendor word; workbook "Split by" and "Filters" in words (`DEMO Shirt size: Medium, Large`, `Basis: Approved`), no raw key/choice code | PASS (test_08); walk download name `payobook_people_by_demo_shirt_size_2026-11-20.xlsx` |
| 9 | New field usable without restart: same process (test_09) AND **two workers** (`--workers 2`, demo copy): before 0/6 fresh connections, after creating the field through one request **12/12** fresh connections offered it, answered by both worker processes; after delete 0/6 | PASS |
| 10 | Silent install on the demo-size copy (4,575 people, 53 runs, 137,204 per-person rows): counts of jobs, mails, x_ fields, field settings, screen designs, saved views, settings, server actions, employees, payslips and a checksum of the per-person report rows **identical before/after** `-u pb_explorer -i pb_form_studio_explorer`; five shipped reports (Cost Explorer, Workforce Movement, Cost per Head, Tax & Deductions, Statutory Ledger) — totals, every row, people counts — **byte-identical** before/after; schema unchanged until a field is marked; in-suite: three reports identical with the hooks switched off | PASS (test_10 + scratch-copy snapshots) |
| 11 | PO gate: bridge vi/id 16/16 screen rows each, markers + occurrences, read by the platform's reader; pb_explorer vi 342 rows incl. 4 new + 3 words now marked for Python; new pb_explorer `id_ID.po` with the 4 new strings; no vendor word in any msgstr, header or user string; console clean (desktop + phone); 390 px: page never scrolls sideways (scrollWidth 390), menus kept on screen | PASS (test_11 + walk) |

### 3a. Final run
See the line appended at the end of this report (§9).

### 3b. Performance (demo-size scratch copy, machine shared with two other builders — load ≈ 10–13)
Median of 7, whole question (chart + people count + month strip), all four companies:

| Question | Built-in by department | Built-in by job position (same per-person table) | Own field (employee) | Own date by quarter | Own field (contract) | Own-field filter |
|---|---|---|---|---|---|---|
| People | 1,039 ms | 1,070 ms | 1,219 ms (1.17×) | 1,228 ms (1.18×) | 1,098 ms (1.06×) | 454 ms |
| Net pay | 254 ms | 350 ms | 393 ms (1.55× / 1.12× vs job) | 446 ms (1.76× / 1.27×) | 473 ms (1.86× / 1.35×) | 460 ms |

Small company (21 people, the largest near Rize's 230 on this copy): every own-field question
0.99–1.27× the built-in one (50–68 ms). **Limit:** a MONEY figure split by an own field at
demo size is 1.55–1.86× the department split, because department money reads the small
per-component table while any per-person split (own field or the built-in job position) must
read the per-person table; against the built-in job position it is 1.12–1.35×. The contract
lookup was made a hash-grouped read (was a sort, a third slower). No schema change per query.
Making the field: 0.4–0.8 s each on the demo copy.

## 4. Limits, in plain words
- Numbers and money fields cannot be used to split or filter yet (range filters are a later phase).
- Employee fields use each person's value **today**, not the value they had in the month of the
  payslip. Contract fields use the contract each payslip was made with. Said in the picker.
- A field limited to some countries shows "—" for people elsewhere and for people with no
  Country of Work.
- The "what changed" list next to the movement story (new / stopped components, departments
  against the trend) does not follow any filter today — own-field filters included. The movement
  waterfall itself does.
- A text field with many different answers shows the 24 largest, the rest counted as "more" (as
  every split does); a filter offers up to 200 values.
- A shared saved report opened by someone other than its owner shows the "field was removed"
  note until the owner has opened it once (the note is cleared by the owner's first look).
- The Indonesian screen of the reports is still mostly English (pre-existing: the module had no
  Indonesian file; only the 4 new sentences are translated).

## 5. Gotchas (rows for FORMSTUDIO_LEDGER.md)
- FS8-1 Explorer reads with SQL: any own-field value written earlier in the same transaction must
  be flushed first (`flush_model`) or the split shows the old value (found by test 6).
- FS8-2 A stand-in FROM text placed in statements run WITH parameters must have `%` doubled.
- FS8-3 Local asset bundles are not rebuilt when only a JS file changes (no version bump): purge
  `/web/assets/%` attachments to see a JS change in a local walk.
- FS8-4 `origin/19.1` moved under the branch (FS-7 merged and went live mid-build): rebase and
  re-run the baseline on the new base before comparing.
- FS8-5 Pre-existing, not fixed (out of scope): "Cost per person" split by Job position runs its
  money half on the per-component table, which has no job column.

## 6. Go-live (when the owner says so)
- `-u pb_explorer` (19.0.2.8.0) and `-i pb_form_studio_explorer` (19.0.1.0.0) on payobook,
  payobook_template, p0clone, rize, sudima. Order: pb_explorer first (the bridge needs its hooks).
- Risk tier: normal (no new table or column, no data written by install; proven silent on the
  demo-size copy). Asset purge + `web.assets.version` bump (JS/SCSS/XML changed).
- No merge-time task. No engine file changed. Nothing created on any customer database.

## 7. Owner questions
All three earlier questions were answered by the architect's defaults under the owner's standing
approval (§10): saved reports warn but never block a delete; "value as it is today" stays; one
switch ("Show in lists", help text now "lists and reports"). No open question.

## 8. Files
`pb_explorer/__manifest__.py`, `pb_explorer/models/pb_explorer.py`, `pb_explorer/models/pb_explorer_view.py`,
`pb_explorer/static/src/js/explorer.js`, `pb_explorer/static/src/xml/explorer.xml`,
`pb_explorer/static/src/scss/explorer.scss`, `pb_explorer/i18n/{pb_explorer.pot,vi_VN.po,id_ID.po}`,
`pb_form_studio_explorer/**` (incl. `static/src/scss/form_builder_reports.scss`), `docs/handovers/formstudio/FS8_FACTS.md`, this report.

## 9. Final run
After the last code change (contract lookup, phone menus): `/pb_explorer, /pb_form_studio_explorer` on a fresh copy with the bridge — **0 failed, 0 errors** (explorer 101 + bridge 13 test methods). Local databases `fs_8_*` dropped at the end.

## 10. Follow-on (2026-11-20, architect defaults under the owner's standing approval)
Branch already on current `origin/19.1` (`e69bebcc4`, FS-7 live) — nothing to rebase.

1. **Delete rule changed — a saved report never blocks a delete.** The report use is no longer an
   engine reference finder (a finder blocks). The bridge adds `report_uses` to each own field in
   the Studio and Field library payloads (`get_studio` / `library` overrides): shared reports and
   the administrator's own are named, other people's private reports only counted ("Private
   reports of other people: N" — never their names or owners). Shown as a count chip in the Field
   library's "Used by" column, an "In reports" block in the properties panel, and a warning in both
   delete confirmations ("Saved reports that use this field: N. Deleting it takes it off them: they
   open without this split or filter and say so once."). `delete_field` override: the engine's own
   delete first (its checks and real blockers unchanged), then every affected saved report's stored
   question loses the field (split → none, filter removed) and keeps the field's name under
   `_lost`; `pb.explorer.open_view` says "This view was split or filtered by “X”, which was
   removed, so it opened without it." and clears the mark at the owner's first open. Proactive
   clean-up also means a later field that happens to get the same code can never be picked up by
   an old report.
2. **One switch.** "Show in lists" stays the only switch; its help now reads "Lists and reports: a
   column on the lists of these records, and a split and a filter in reports." (Field library:
   "Lists and reports."). vi + id. "Value as it is today" unchanged.
3. **Speed.** Re-measured (machine load ≈ 8–10; median of 7; whole question):

   | Net pay split | ms | vs department | vs job position (same per-person table) |
   |---|---|---|---|
   | department (built-in) | 252 | 1.00× | — |
   | job position (built-in) | 293 | 1.16× | 1.00× |
   | own employee choice | 306 | **1.21×** | 1.04× |
   | own employee date by quarter | 349 | **1.39×** | 1.19× |
   | own contract choice | 454 | **1.80×** | 1.55× |
   | own-field filter (split by department) | 335 | 1.33× | 1.14× |

   People-count splits: 1.19–1.35× department. 21-person company: 1.00–1.02× everywhere.
   Employee fields are under the 1.5× target; a **contract** field on money is not (1.80×): the
   extra cost is finding the contract each payslip used across all 34,322 payslips of the 53 runs
   in scope (already a hash-grouped read). Further speed would need a stored "contract per payslip
   per run" in the report tables (a fact-table change + rebuild) — not attempted (not short or
   safe). Results unchanged by any of this.

Re-run after the follow-on:
- Test 7 (new rule) + 7c, all bridge tests: `/pb_explorer, /pb_form_studio_reach,
  /pb_form_studio_explorer` on a fresh template copy — **142 tests, 0 failed** (explorer 101,
  reach 51, bridge 14 methods).
- Test 10 + totals at demo size, on a NEW copy: silent-install counts and the per-person report
  checksum identical before/after; five shipped reports byte-identical before/after (and identical
  to the first run's snapshot).
- Screen (administrator, demo copy): Field library chip "2", delete sheet shows the warning with
  "DEMO People by shirt size, Private reports of other people: 1" and an enabled Delete; delete
  done; the saved report opened with the note, the second time without it.
- Engine suite with the bridge installed: `/pb_form_studio, /pb_form_studio_explorer` — **0 failed** (engine 41 = baseline). Local databases `fs_8_*` dropped.
