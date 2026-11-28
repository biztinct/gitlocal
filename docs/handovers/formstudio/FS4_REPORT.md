# FS-4 — Lists and columns (`pb_form_studio_lists` + the column model in `pb_filter_kit`) — report

Branch `fs-4` (from `origin/fs-1` @ 87ede1a76, then `origin/fs-1` @ d341ed396 merged in — the
R14 / pay-run-signal follow-up; the list helper is unchanged by it). New module
`pb_form_studio_lists` **19.0.1.0.0**; `pb_filter_kit` **19.0.1.4.0 → 19.0.1.5.0**. No other module
edited. Not deployed. Local databases `fs_4_base`, `fs_4_bl`, `fs_4_t`, `fs_4_rg` (dropped at the end).

## 1. Verified facts (file:line at this branch)

| # | Fact | Where |
|---|---|---|
| V1 | People list page = `pb.people.get_roster_page(filters, search, sort, offset, limit)` → rows from `_roster_row` (fixed dict); the card shows name, job · department, status badge, expiry chip (≤ 30 days), wage (`money(p.wage, p.currency)`, **unmasked**), ready icon, Contract button. | `pb_people/models/pb_people.py:408, 448`; `pb_people/static/src/xml/people.xml:62-86` |
| V2 | Contracts board page = `pb.contracts.get_contracts_page` → `_contract_row` + FILLIN answers; card shows person, reference · structure, start → end, status, expiry chip, FILLIN chip, wage (**unmasked**). No bulk tick on this board. | `pb_contracts/models/pb_contracts.py:370, 408`; `pb_contracts/static/src/xml/contracts.xml:50-108` |
| V3 | Both boards wrap their list in `<PbFilterLayout>`, whose `toolbar` slot neither fills — the clean place for Cards / Table / Columns / Excel. | `pb_filter_kit/static/src/xml/filter_kit.xml:31`; `people.xml:61`; `contracts.xml:43` |
| V4 | `PbPeople` / `PbContracts` are exported classes; their page calls go through `this.orm.call` in `loadPage`. | `pb_people/static/src/js/people.js:22, 134-156`; `pb_contracts/static/src/js/contracts.js:32, 113-140` |
| V5 | Records Desk keeps its pick in `localStorage` through four instance methods (`restorePicked`, `restoreOrder`, `rememberPicked`, called from `loadFields`) — patchable from outside. | `pb_records/static/src/js/records_desk.js:46-47, 212-270` |
| V6 | **The ORM never prefetches manual fields** ("prefetch only stored, column, non-manual fields"): each custom column read costs one query per page unless fetched together. | core `odoo/orm/fields.py:502-504` |
| V7 | `pb.filter.view` saved-view tabs are searched by the exact screen key; the Form builder's delete check reads `filters` and `search_text` only — a column set in `columns` never blocks a delete. | `pb_filter_kit/models/filter_mixin.py` `_pbf_views`; `pb_form_studio/models/form_studio.py` `_pbfs_refs_saved_views` |
| V8 | `fields_for(model, 'list')` answers only for models a host registered; FS-4 registers no host (hosts are FS-2 / FS-3). | `pb_form_studio/models/form_studio.py` `fields_for`, `_pbfs_host_models` |

## 2. What was built

**`pb_filter_kit` 1.5.0 — the column model (only builder to edit it)**
- `pb.filter.view.columns` (Json, new nullable column, `models/filter_view.py:74`). A person's own
  choice ("Just me") is ONE row per list filed under `<screen>::columns` (`COLUMNS_SUFFIX` :20), so it
  never shows as a view tab and the existing record rules keep it private. Holds `{cols: [{key, on}],
  mode: 'cards'|'table'}`.
- `pb.list.layout` (`:214`): screen, company, columns = the company default ("For everyone"); ACL
  read for everyone, write for `base.group_system` only; company rule.
- API beside `pbf_save` / `pbf_update`: `pbf_columns_read` :145, `pbf_columns_save` :159 (`scope='me'`
  anyone, `'company'` administrator only — plain refusal otherwise), `pbf_columns_reset` :196. Junk
  entries are dropped, never refused.
- Mixin (`models/filter_mixin.py`): hook `_pbf_columns()` :94 (a board's columns; empty = no table,
  every other board unchanged), `_pbf_table_rows`, `_pbf_export_name`; RPC `pbf_columns` :672 and
  `pbf_export_table` :683 (the visible columns in order, every matching row, 10,000 cap said out
  loud; keys the board does not offer THIS person are ignored; every text cell written as text with
  the spreadsheet's text prefix when it starts with = + - @ — `_set_text` :799).
- Browser (`static/src/js/list_table.js`, `xml/list_table.xml`, `scss/list_table.scss`):
  `ListColumns` + `useListColumns` (layers: board standard → company → mine; a deleted key is
  skipped, a new column joins next to its neighbour), `PbTableTools` (Cards | Table, Columns, Excel),
  `PbColumnsButton` (switches, drag to reorder, up/down arrows for keyboard and touch, Reset, "Just
  me" / "For everyone" for the administrator, a phone bottom sheet), `PbListTable` (sticky first
  column, sideways scroll inside its own box, heading = the board's own sort, tick column in select
  mode, a slot for row actions, the column that just arrived glows once).
- vi_VN entries appended (existing lines untouched), `id_ID.po` new; header de-branded.

**`pb_form_studio_lists` 1.0.0 (depends `pb_form_studio`, `pb_filter_kit`, `pb_people`,
`pb_contracts`, `pb_records`)**
- People list (`models/people_lists.py`, `static/src/js/people_table.js`, `xml/people_table.xml`):
  standard columns = what the card shows (Name+job, Department, Contract, Contract ends + "12 days"
  chip, Monthly wage, Payroll-ready) + Job, Manager, Work email, Joined, Contract start (off) + every
  custom field marked "Show in lists" the reader may see (on, after the standard ones).
  `get_roster_page` `_inherit` (:49) adds `pbfs` cells ONLY when the browser asks for the table
  (`context.pbfl_table`, set by a thin wrapper around the board's `orm` for that one method —
  `table_flag.js`), so the cards get exactly what they got before.
- Contracts board (`contract_lists.py`, `contracts_table.js`, `contracts_table.xml`): Person+reference,
  Pay structure, Starts, Ends + chip, Status, Monthly wage, Answers to check (where FILLIN exists),
  Contract reference (off) + custom contract fields. The "To check" bar and each row's Change / Looks
  right stay in the table.
- Values only through the engine: `fields_for(model, 'list')` + `_pbfs_values_for` (visibility and
  Country of Work); the page's custom columns are fetched in ONE query first (`_pbfl_prefetch`,
  `list_columns.py:45`, because of V6). Money exactly as the cards (same row values, unmasked as the
  cards are).
- Records Desk (`records_columns.js`): picked fields + order kept in the store under
  `records.<scheme>`; the first open with nothing stored reads the old browser keys once and stores
  them; the browser copy is still written as a fallback.
- Learn: the table carries the roster anchors `pe-roster` / `ct-roster`, so a step pointing at "the
  list" finds either view; cards stay the default, so no lesson or tour step changes.

## 3. Tests (numbered) vs baseline

Module suite `/pb_form_studio_lists` (`tests/test_lists.py`, 11 methods). The suite lends the engine
two minimal hosts for `hr.employee` / `hr.contract` only when FS-2 / FS-3 are not installed.

| # | Case | Result |
|---|---|---|
| 1 | table shows the same people / contracts, totals, steps and rows as the cards under 6 People filters × 2 sorts and 4 Contracts filters; cards get nothing new | PASS |
| 2 | choose / reorder / junk dropped / mode kept; per person; company default administrator only (method + table ACL); reset me → company; reset company; the person's row is never a tab | PASS |
| 3 | custom column appears when "Show in lists" is on, goes when off; a saved set naming it is NOT a delete blocker; after delete the list, the stored sets and the Excel all still work | PASS |
| 4 | admin-only field: not in the HR reader's columns, page or file (forged key ignored); India-only field blank on a Vietnam record (table + Excel); numbers as numbers; wage = the card's wage with its money sign | PASS |
| 4b | Excel: a name starting with "=" stays text (type s + text prefix); file "Employees YYYY-MM-DD.xlsx", sheet "Employees"; Contracts file complete | PASS |
| 5 | paging (offset/limit) and every sort identical cards vs table; every heading sort is a real board sort; bulk "Move to department" untouched | PASS |
| 6 | Records Desk choice per person per scheme in the store; JS reads the old browser keys once | PASS (+ browser walk) |
| 7 | 500 people × 10 custom columns, page of 60 | PASS — see §3.1 |
| 8 | every other board on the kit has no table (`_pbf_columns` empty); panel payload same shape; boards' suites = baseline (§3.2) | PASS |
| 9 | silent install: no column layout, no person row, no job / mail / view / menu, no custom field | PASS |
| 10 | PO: vi + id entries for every new string (needles), PO parse gate (Odoo `PoFileReader`) on all 5 files, no "Odoo" in any msgid/msgstr, template, `_t()` or `_()` | PASS |
| 11 | browser walk desktop + phone, console clean | PASS — §4 |

### 3.1 Performance (test 7, best of 3, local Mac)
Page of 60 out of 500 people, 10 custom columns: **cards 8 queries, table 14 (+6), 0.15 s → 0.23 s**.
The +6 = **1 query that loads every custom column of the page** (any number of columns, any number
of rows) + 5 fixed queries the engine spends reading its field settings (`fields_for` twice and
`_pbfs_meta`). Before the one-query fetch it was +15 (one per column). Excel, 500 rows × 11
columns: 1.3 s.

### 3.2 Touched suites vs baseline
Same suites, same template copy (`fs_4_base` = `upd_p6_t_tpl` + FS1-4 fix + engine), run once on a
clean `git archive origin/fs-1` tree (baseline) and once on this branch after the merge of the latest
`fs-1` (`-i pb_form_studio_lists -u …`):
`/pb_contracts, /pb_records, /pb_people_hub, /pb_hiring, /pb_timeoff, /pb_lifecycle, /pb_expenses_hub,
/pb_learn, /pb_hub, /pb_settings, /biz_debrand, /pb_form_studio` (+ `/pb_form_studio_lists` after).

| Run | Tests | Failed | Errors |
|---|---|---|---|
| baseline (origin/fs-1 87ede1a76) | 1,612 | 19 | 11 |
| fs-4 (merged with fs-1 d341ed396) | 1,652 | 19 | 11 |

**Identical failure set** (30 names, `comm` of the two lists: nothing new, nothing gone), none in a
screen FS-4 touches: Learn guide/anchor truth tests, Hiring privacy/joining/stages, time-off leave
rules, hub static gates, `TestCd1Contract360.test_01` (contract panel payload keys), biz_debrand
product-name scans, People hub static order. The extra 40 tests are the engine's new R14 tests (all
pass) and this module's 11 (all pass). The filter kit has no suite of its own; its ~30 boards are
covered by the suites above and by case 8.

## 4. Browser walk (local, Chrome; desktop 1512 × 900, phone 390 × 844 emulated)
- People (administrator): cards unchanged, Cards | Table in the filter bar; Table → 13 columns incl.
  7 custom ones; Name column sticky; table scrolls sideways inside its box (page width = window).
  Reload → still Table (remembered). Columns: switch Manager on (column glows in), arrows move a
  column, drag DEMO Bike parking above Department (drop marker shown; the pinned Name cannot be
  dragged) — "Saved for you", stored on the server. "For everyone": Save disabled until a change,
  click outside does not lose an unsaved company set, "Saved for everyone…" message. Reset → "you now
  see the company's columns".
- People (HR user, second session): starts on cards (their own choice), Table shows the company's
  columns, no "For everyone" switch, the administrator-only field absent, India-only field filled for
  India staff and "—" for Vietnam staff. Excel → "Employees 2026-11-19.xlsx", 25 rows.
- Heading click sorts (Name Z → A, the sort menu follows), Select mode: tick column, row click ticks,
  header tick = all 25 / none, the bulk bar counts follow; Done → row click opens the side panel.
- Contracts board: starts on cards (own memory per board); Table: 8 columns incl. the custom one;
  search "Sharma" 8 rows = 8 cards; the "Ending soon" step → 10 of 24 with "12 days" / "25 days"
  chips; heading arrow follows "Newest start first".
- Phone: no sideways page scroll (390 = 390), table scrolls in its box, Columns opens as a bottom
  sheet with Reset always in view.
- Records Desk: old browser pick (Badge ID, Birthday, Blood type) moved to the store on first open;
  browser memory wiped + reload → the three columns are still there ("3 of 79 picked"); removing one
  updates the store.
- Console: clean after the fixes below (one pre-existing handled warning in the server log from
  `pb_me_portal`).
Fixed during the walk: the Excel save called a helper the browser layer does not have; the person
column was squeezed to one letter; the chooser ran off the bottom of a short screen.

## 5. Self-review against the spec — deviations (stated, not silent)
- "Toggle remembered per user": kept in this browser (instant) AND on the server with the person's
  column row; a choice made on another device wins after the first load. Card users therefore make
  one small background call (`pbf_columns`) after the page shows.
- The person's own columns live in a `pb.filter.view` row under `<screen>::columns` rather than on a
  saved view: saved views do not carry columns on screen (R13 — no backend-only switch was added).
- "Money masking as the cards do": the cards do not mask the wage (V1, V2); the table shows exactly
  the card's value. Custom money fields follow the engine's "who can see it".
- The Contracts board has no bulk tick today, so its table has none.
- FS-4 registers no host (V8): custom columns appear once FS-2 / FS-3 are merged; until then the
  tables show the standard columns (proved with a local host only).

## 6. Merge-time tasks
- None for the engine (the cross-database pay-run check I hit is FS1-8, already fixed on `fs-1`).
- `pb_filter_kit` is shared: FS-2 / FS-3 add filter sections through `_pbf_spec`; FS-4 adds
  `_pbf_columns` — different hooks, no overlap.
- When FS-2 / FS-3 land, re-run `/pb_form_studio_lists` (the suite then uses their hosts).

## 7. Deploy notes (not done here)
- `-u pb_filter_kit` (new table `pb_list_layout`, new nullable column `pb_filter_view.columns`) and
  `-i pb_form_studio_lists` on every database; normal tier; asset purge after (JS/SCSS).
- Silent: nothing is created at install. New vi/id terms load with the `-u`.

## 8. New gotchas (rows for the ledger)
- FS4-1 Manual (custom) fields are never prefetched by the ORM: a list that reads N custom columns
  costs N queries per page unless it calls `records.fetch(names)` first (core `fields.py:502`).
- FS4-2 `browser.atob` does not exist on the web client's `browser` object — use `window.atob`.
- FS4-3 This Mac's Chrome window cannot be resized past ~614 px: use the DevTools browser with
  viewport emulation for desktop screenshots.

## 9. Owner questions (plain)
- Should the People and Contracts lists open as a table for everyone by default, or stay on cards
  until each person switches (today: cards, and each person's choice is remembered)?
- When an administrator saves "For everyone", people who already chose their own columns keep
  theirs. Should "For everyone" also replace their choice (they could still change it again)?
