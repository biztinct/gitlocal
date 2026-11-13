# TIDY Phase 3 — "Budget, month by month": a month is a scope, not a bar

Read `docs/handovers/TIDY_LEDGER.md` FIRST and fully (rules 11–14, the Budget plumbing
facts, the P1/P2 phase logs and T-gotchas), then the GROUP ledger's rules, gotchas and
deploy ritual. Do not re-derive the plumbing facts.

## 0. What you are building, in one paragraph
The Budget lens on Insights reads by the year: KPIs, the heat tiles ("88% spent of the
budget", "Ahead of the year"), and a per-function drill with twelve bars. The owner
wants to **drill into a month** and see budget vs actual for that month across the
same things the year view shows — functions, departments, spent/budget/left, the
words — and how the month varies. Make a month a first-class scope (rule 13): pick a
month and the whole board, drill, table and spreadsheet are that month's.

## 1. Deliverables

### 1a. The month strip (the new hero)
Under the KPIs, above the tiles: a strip of thirteen chips — **"Whole year"** then the
twelve months. Each month chip carries a two-tone micro bar (budget grey, spent
coloured by that month's tone) and a small variance figure ("−4%" / "+12%"); the
current month is marked "now"; future months are quiet ("not yet"). Click a month and
the board re-scopes; click "Whole year" (or Escape) to return. ←/→ move between
months while the strip has focus. The chosen month is a deep link: `pb_focus:
"month:2026-03"` on the Insights hub arrival opens the lens on that month (register
`wantsArrival` as the People-hub lenses do; the Insights hub is the same `HubShell`).

### 1b. What a month scope changes
- **KPIs** become: "budget for March", "spent in March", "left in March", "vs budget"
  (variance %, signed), "functions over budget in March".
- **Headline sentence** (server, one expression each): "March: 4 of 9 functions went
  over budget; Retail by the most (₫12.4bn, 18% over)." / "March came in ₫8.1bn under
  budget across 9 functions." / "March has no budget set; ₫… was spent." / for the
  current month: "March so far: 62% of the month's budget spent with 71% of the month
  gone." / future: "April has not started."
- **Tiles**: the same tiles, that month's `spent/budget/left`; the bar is the share of
  the month's budget spent; the notch is **days of the month gone** for the current
  month, at 100% for a finished month, absent for a future month. **Month words**
  (server `_tone_month`): "Over budget" (spent > budget × 1.05), "Close to budget"
  (within ±5%), "Under budget", "No budget set", "Not yet" (future, nothing spent).
  The spark on each tile keeps all twelve months and highlights the chosen one.
- **The drill** (`get_function` with `month`): the twelve-bar chart stays with the
  chosen month highlighted; the departments table shows that month; add a **"How March
  compares"** row of four small figures: this month, last month, the same month last
  year (blank + "no data" when absent), and the year's monthly average — each with
  spent vs budget. Expenses list filtered to the month.
- **Table view**: in month scope the columns are Department · Budget · Spent ·
  Variance (money) · Variance (%) with the variance cells toned; in year scope, add the
  same two variance columns to the existing expanded month rows.
- **Spreadsheet** (`budget_export.build`) takes `month` and produces that month's sheet
  titled "Budget March 2026"; the PDF summary likewise if it shares `build`, else say
  so in the report.
- Everything else — type switch, currency switch, upload, add an expense, refresh —
  keeps working inside a month scope (upload and expense are not month-scoped; they stay
  as they are).

### 1c. Server
- `get_board(fy, budget_type, currency, row_cap, month=None)`: `month` is `'YYYY-MM'`
  within the FY or `None`. When set, `_matrix` totals only that month's rows (keep the
  per-function `months[]` for the spark), `pace` becomes the month pace (days gone),
  `_tone` uses the month rule, `_kpis`/`_headline` the month forms; payload carries
  `scope: {kind: 'month'|'year', key, label, state: 'past'|'current'|'future'}` and a
  `strip: [{key, label, budget, spent, variance_pct, tone, state}]` (always, for the
  chips). `get_function(..., month=None)` adds `compare: {this, last, last_year, average}`.
- `budget_export.build(..., month=None)`.
- Bump `pb_budget` to 19.0.2.1.0. Vietnamese for every new string.

### 1d. Client
- `budget_board.js`: state `month: ""`, `stripFocus`; `setMonth(key)`, `clearMonth()`,
  key handling (←/→/Escape with capture, WF4); `load()` and `openFunction()` pass
  `month`; the arrival focus parsed once in setup. Template: the strip, month-aware KPI
  captions, tile notch rule, drill compare row, table variance columns.
- SCSS: `.bdg-strip`, `.bdg-mchip` (+ `is-now`, `is-future`, `is-on`), micro bars,
  variance tone classes reusing the tile tone tokens.

### 1e. Carried over from P2 (gotcha T18): no "Odoo" in the Apps list
Thirteen `pb_*` manifests still say "Odoo" in their `summary`/`description` (T18 lists
them: `pb_explorer`, `pb_hub`, `pb_mission`, `pb_sidebar`, `pb_wf_kit`,
`pb_login_language`, `pb_hr_payroll_demand` and six per-country payroll modules).
The Apps list is user-visible — GROUP rule 1 applies. Rewrite in plain words ("this
system", "Payobook"); code comments and technical ids stay. Patch-bump each, upgrade on
all four DBs, one commit for the set. Confirm with a repo-wide grep that no
`__manifest__.py` `summary`/`description` string contains "Odoo" (case-insensitive)
in any `pb_*`/`biz_*` module.

Non-goals: no new lens, no rail item, no change to how actuals are read, no change to
uploads or expenses, no quarter scope (note it as a candidate).

## 2. Design (the bar)
**"extreme WOW, intuitive, out-of-this-world experience, best in class."** Hero: the
month strip — thirteen chips that already show, before any click, which months ran
hot; click March and the whole board becomes March in one motion (tiles keep their
places; numbers and words change; the spark's March bar lights). Plain words
("Over budget", "Close to budget", "Under budget", "not yet", "now"). Zero dead-ends:
Escape and "Whole year" always return; a month with no budget says so on every tile;
a future month says "has not started". Keyboard on the strip. Lucide via `ic()`; no
emoji; no "Odoo".

## 3. Tests (p9clone; numbered)
- T1 `get_board(month=…)`: function `spent/budget` equal the sum of that month's lines;
  `strip` has 12 entries whose `spent` sum to the year's `spent`; `scope.state` correct
  for past/current/future against a frozen `context_today`.
- T2 month tone rule boundaries (±5%); "Not yet" only for future with nothing spent.
- T3 headline forms (over / under / none / current / future) each produced once.
- T4 `get_function(month=…)`: departments sum to the function's month figure; `compare`
  has `last_year` blank when there is no prior FY data.
- T5 `build(month=…)` sheet title and totals match the board for that month.
- T6 Existing `pb_budget` tests green (18 today) + Vietnamese completeness.
Browser (p9clone + payobook; validator; 1440 + 390; EN + VI; `docs/handovers/
tidy_p3_shots/`): B1 the strip at rest; B2 click March → board re-scoped; B3 drill
with the compare row; B4 table view variance columns; B5 ←/→/Escape; B6 deep link
`month:2026-03` from ⌘K/URL; B7 spreadsheet for the month; B8 phone; B9 Vietnamese.

## 4. Deploy
Ritual as the ledger: p9clone → payobook → abm → payobook_template, `pg_dump` each,
`-u pb_budget`, asset purge, version + hash verification.

## 5. Report back
1. Three sentences: what a person sees when they click a month, what the words are,
   what the spreadsheet gives them.
2. T1–T6 / B1–B9 table; deploy evidence per DB; commits; T-gotchas appended; self-score;
   candidates (quarter scope, month scope on the Pulse lens…).
