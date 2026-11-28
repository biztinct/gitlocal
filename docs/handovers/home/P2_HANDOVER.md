# HOME P2 — the new Home front end (handover for Opus)

Read first: `HOME_PROGRAM.md`, `HOME_LEDGER.md` (H-R1…R8 + every H row), `P1_HANDOVER.md` + `P1_REPORT.md` (the
payload you render — keys, `None` rules, what the clone returned), and the build target
`docs/design/home-dashboard-prototype.html` (open it in a browser; read its CSS tokens, its SVG helpers and its JS
`applyMonth`/`drawChart` — you are porting them to OWL, not redesigning). CLAUDE.md rules apply.

## Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment: the one sentence that says
where the month stands, and the 12-month chart that is also the month picker (click / ← → / Esc) with the figures
and the stacked cost bar re-reading under it. Zero dead-ends: every chip, step, run row and figure opens the screen
it talks about; every empty state says what will appear. Motion with purpose only (hero rise, column grow,
count-up, the one pulse on the "now" node), all off under `prefers-reduced-motion`. Lucide, locked indigo
`#5A4BB0`, no gradients, no emoji, one solid primary per button bar. Score the report against this bar.

## Scope (P2) — sections 1–5 of the program doc's "What Home becomes"
Rewrite `PbDashboard` (template, JS, SCSS) on top of `get_home_data()`:
1. **Top line**: greeting (client clock, as today) + date + company; "Updated hh:mm"; NO ask pill (the hub's ⌘K
   already exists). When embedded in the hub, the top line is hidden (the shell carries the brand) — keep the
   existing `embedded` prop behaviour (`pbd-root--embedded`).
2. **Hero** (light-tint card): eyebrow "<Month> <year> payroll"; **h1 = state words** built from the payload (table
   below); the sentence with inline links (buttons styled as the prototype's `.link`); the 5-node journey (tones
   from `steps[].state`); buttons: ONE solid primary that names the act (table below) + "Open pay runs" (outline) +
   "Insights" (ghost, existing `openInsights`). Right card "<Month> so far": `period.prepared` of `period.expected`
   (big figure + progress bar), `net_so_far`, `run_count`, cut-off date, 12-month net sparkline (months[].net,
   in-progress month excluded, latest highlighted).
3. **Needs you** line: one chip per `needs_you` item (amber; `writeups_overdue` rose), tail link
   "All N approvals" when `approvals_total` is not None (→ Home hub `approvals` lens). When `needs_you` is empty
   the line reads one grey sentence: "Nothing needs you right now" + "next: payday <date>" when known.
4. **Payroll, month by month** card: segmented control (Net pay / Gross pay / Deductions / Employer cost / People),
   the column chart (geometry computed in JS, drawn by the template — see "Chart contract"), tooltip, keyboard,
   the hint line (visible on card hover / chart focus), then the **month panel**: title + pill (Latest completed /
   Completed / In progress), facts line (runs, approved, delivered, "All runs balance" green / "Figures grow as
   payslips are prepared" amber), the four figures (People paid, Net pay, Average net per person, Total cost to the
   company) each with a 12-point sparkline and a neutral delta, and the stacked bar Net | Deductions | Employer
   cost with the Gross bracket + legend. `pb_focus: 'month:YYYY-MM'` (arrival or action context) selects that month
   on mount; `month:current` selects the in-progress one.
5. **Right column**: "<Month>, step by step" (5 rows from `steps`, who/when, amber "waiting on you") and
   "Coming up" (rows from `upcoming`, date tile, amber "in N days" when ≤ 3 days). Every row is a button/link.
6. **Activation checklist**: keep the existing markup, JS table and behaviour byte-for-byte (tests pin it); when
   `activation.show` it replaces sections 2–5 (today it sits between hero and KPIs — now it sits alone under the
   top line with the hero reduced to the greeting line).
7. **Learn anchors** (H9): `data-coach="dash-hero"` on the hero, `dash-runpayroll` on the primary button,
   `dash-period` on the chart card, `dash-kpis` on the four-figure grid, `dash-formula` on the right column's steps
   card for now (P3 moves it to the Pay schemes card and updates the lesson).

Sections 6–7 (the card rows) are P3. Leave a `<!-- P3: cards -->` placeholder div.

## Words (the browser owns them — H-R3; use these exact EN strings through `_t`, VI comes in P3)
| Payload | Sentence |
|---|---|
| h1, payday known + awaiting_me ≥ 1 | "%(days)s days to payday · %(n)s pay run needs your approval" (plural: "pay runs need your approval"); payday today: "Payday is today · …" |
| h1, payday known, nothing waiting | "%(days)s days to payday · nothing is waiting on you" |
| h1, no payday known | "%(month)s payroll is at step %(stage)s of 5" |
| sentence | "%(month)s is at [step N of 5]. " + (awaiting: "%(who)s has submitted the **%(run)s** run (%(people)s people, %(net)s) for your approval") + (now_run: ", and the **%(run)s** run is being prepared") + (period.stage==1: "No pay run has started yet.") |
| journey labels | Set up · Prepare · Approve · Pay · Deliver payslips; subs: "Done %(date)s" / "Under way" / "Waiting on you" / "Waiting on %(who)s" / payday date / "Email, EN + VI" |
| primary button | awaiting: "Review %(run)s"; else now_run: "Continue preparing %(run)s"; else stage ≤ 1: "Start %(month)s payroll"; else "Open pay runs" |
| hero right card | eyebrow "%(month)s so far"; pill "In progress"; big "%(prepared)s" + "of %(expected)s payslips prepared"; row "%(net)s net pay so far · %(n)s pay runs · cut-off %(date)s"; foot "Net pay, last 12 months" |
| needs_you keys | runs_to_approve: "pay run to approve / pay runs to approve"; leave_to_approve: "leave request(s) to approve"; other_to_approve: "other approval(s)"; settlements_to_check: "final settlement(s) to check"; renewals_to_start: "contract renewal(s) to start"; writeups_overdue: "interview write-up(s) overdue" |
| chart card | title "Payroll, month by month"; sub "Click a month to read its figures below. The last 12 months of completed pay runs."; segments as listed; hint "← → walk the months · Esc back to the latest · Hover a column for the full figures"; column labels "Latest", "In progress" |
| tooltip rows | Net pay · Gross pay · Deductions · Employer cost · People paid (+ " of N so far" when in progress) · "No pay run" when runs == 0 |
| month panel | pills "Latest completed" / "Completed" / "In progress"; facts "%(n)s pay runs", "approved %(date)s", "delivered %(date)s", "All runs balance", "Figures grow as payslips are prepared"; figure labels "People paid", "Net pay", "Average net per person", "Total cost to the company"; deltas "+11 vs Aug" / "about the same as Aug" (|Δ| < 0.5 %) / "so far · no comparison yet" / "no earlier month"; bar title "Where the money goes"; bracket "Gross pay"; segments "Net", amounts; legend "Net pay to people", "Deductions (tax, insurance)", "Employer cost (insurance, union)" |
| steps card | title "%(month)s, step by step"; sub "Cut-off %(date)s · payday %(date)s"; rows: "Set up the month" ("%(n)s joiners and leavers added" → keep simple: "%(n)s people added"), "Prepare payslips" ("%(run)s run in progress"), "Approve" ("%(who)s submitted the %(run)s run"), "Pay" ("Bank file" + rose "%(n)s people have no bank account" when n > 0), "Deliver payslips" ("Email in English and Vietnamese"); when: "today" / short date / amber "waiting on you" |
| coming up | title "Coming up"; kinds: cutoff "Last day for %(month)s changes" / "New joiners, salary changes, overtime"; payday "Payday" / "%(n)s banks"; contracts_end "%(n)s contracts end" / amber "%(r)s renewals to start" + " · %(k)s already renewed"; holiday "Next public holiday" / name; interviews "%(n)s interviews" / "this week"; right column "today" / "tomorrow" / "in %(n)s days" (amber when ≤ 3) / weekday name when within 7 days |
| empty | no runs in 12 months: chart shows 12 zero columns and the panel says "No pay run yet. Figures appear after your first pay run."; period.stage None: hero shows the month and "Pay runs are not tracked on this database" |

Money: compact with the unit after and a space — `53.1 bn đ`, `11.8 M đ`, `850 K đ` (thresholds 1e9 / 1e6 / 1e3;
the symbol and position from `currency`; when position is `before` print `$1.2 M`). Full values in tooltips with
thousands separators in the user's locale (`luxon`/`Intl`). Dates: short "Tue 20 Oct" for this year, "20 Oct 2025"
otherwise (Intl with the user's language). Numbers tabular only in columns (the figure grid uses proportional).

## Chart contract (port the prototype's `drawChart`/`sparkline`, but geometry in JS, drawing in the template)
- `get chart()` returns `{W, H, ticks:[{y,label}], cols:[{key, x, y, w, h, fill, sel, ghost:{y,h}|null, label, labelX, topLabel, hitX, hitW}]}`
  from `state.width` (ResizeObserver on the host → `state.width`), `state.measure`, `state.sel`. Column width
  `min(24, slot*.55)`, 4 px rounded top (path from the prototype's `roundedTop`), square base; hairline solid
  gridlines at `niceStep(max/4)`; axis max = 1.08 × the max over DONE months; the in-progress month = a hollow
  column (surface fill, indigo stroke, 2 px when selected) at the LATEST month's height with the prepared share
  filled inside; unselected columns `--p-soft2`, selected `--p`. Hit targets = the full slot (tooltip on hover,
  click selects). Keyboard on the focusable chart root: ArrowLeft/Right move, Escape → latest, Home/End first/last.
- Sparkline: `sparkPath(values, W, H)` → `{line, area, dot:{x,y}}`; 2 px line, 10 % area, 5 px surface ring + 3.5 px
  dot on the highlighted point (selected month, or latest when in progress is selected).
- Stacked bar: three `<i>` segments with widths in % of total; amounts inside when the segment is ≥ 90 px (measure
  with the rendered width — never clip a label; otherwise drop the inline amount and let the legend + tooltip carry
  it); the Gross bracket width = gross/total.
- Count-up on figure change (520 ms, cubic ease-out) unless reduced motion; never animate on first paint if the
  payload is still loading (show the kit skeleton, `biz-skeleton--card`).

## Plumbing (verified)
- Mount contract: standalone action `pb_dashboard` + hub lens `pulse` with `embedded: true`, `wantsArrival: true`
  (`pb_home_hub/static/src/js/home_hub.js:128-135`); arrival focus arrives as `props.arrival.focus`
  (`pb_dashboard.js:147-152`). Keep props `['*']`.
- Doors: `import { openHub } from "@pb_hub/js/hub_nav"` (`pb_hub/static/src/js/hub_nav.js:52-80`): `openHub(action,
  {xmlid, lens, focus, back})`. Pay Run hub = `pb_payhub.action_pb_pay_hub`, lenses `run / runs / payslips / deliver`
  (`pb_payhub/static/src/js/pay_hub.js:97-125`); the Runs board reads `arrival.focus` as a run id
  (`pb_payruns/static/src/js/payruns.js:170-174`) — so "Review <run>" = `openHub(this.action, {xmlid:
  'pb_payhub.action_pb_pay_hub', lens:'runs', focus: String(run.id), back:{label:_t('Home'), xmlid:
  'pb_home_hub.action_pb_home_hub'}})`. Journey nodes use `STAGE_LENS` (`home_hub.js:166-176`: 1 run, 2 runs,
  3 payslips, 4 deliver, 5 runs). Approvals = Home hub lens `approvals` (`openHub` with xmlid
  `pb_home_hub.action_pb_home_hub`, lens `approvals`). Settlements / renewals / write-ups: find the action xmlid in
  `pb_sidebar/data/pb_sidebar_data.xml` or the module's `views/*_action.xml` (Exits board, Contracts, Hiring) and open
  by xmlid with the Home back chip; never a bare tag (W98 "Unnamed" breadcrumb).
- Icons: `import { ic } from "@pb_import_kit/js/import_icons"` — add `pb_import_kit` to `depends` (H5 fixed in P1).
  Names that EXIST in the kit: sparkles, check, trendingUp, trendingDown, bell, arrowRight, barChart, listChecks,
  calendar, users, layers, loader, clock, briefcase, graduationCap, play, calculator, checkCircle, activity, zap,
  wallet, landmark, userPlus, search, minus. **Missing — add them to the kit's IC map with real Lucide 24×24 paths
  (one registry, rule W2):** `fileCheck`, `layoutGrid`, `moveRight`, `chartColumn`, `triangleAlert`, `flame`.
  Bump `pb_import_kit` version + comment. Source test (H7): every `ic('…')` name in the Home template exists in IC.
- Tokens: root `<div class="pbim pbd">` (kit vars) and alias `--pbd-*` from `--pbim-*` exactly as the Pay Runs
  board does (`pb_payruns/static/src/scss/payruns.scss:5-22`); the semantic set is the Pay Runs one (amber
  `#B45309/#FEF3C7`, green `#0F7B4F/#D9F2E4`, rose `#DC2655/#FFE4E8`, slate `#64748B/#EDF0F4`, teal `#0F766E/#D6F1EC`);
  wash `#F3F0FB`, soft2 `#DDD6F2`, deep `#241F52`. Copy the prototype's CSS class by class into `pbd-*` names;
  dark-mode blocks are NOT needed (the product is light-only; drop them).
- Font (H6): self-host Inter — download `Inter` variable WOFF2 (OFL) into `pb_import_kit/static/fonts/` and add
  `pb_import_kit/static/src/scss/fonts.scss` (`@font-face` weight 100–900, `font-display: swap`) FIRST in the kit's
  `web.assets_backend` list. This makes every screen that already names Inter render in it — say so in the report.
- Loading: `onWillStart` → `orm.call('pb.dashboard','get_home_data',[])`; one call. Errors → the kit's empty block
  with "Home could not load. Try again." + a Retry button (never a blank page).
- Old code: remove the KPI strip, month chips, three cards and `ring()` from the template and JS; `get_dashboard_data`
  stays on the server until P3. Keep `greeting()`, `money()` (updated to the spaced unit), `open()`, `openInsights()`,
  the ACTIVATION table and `runStep()`.

## From P1_REPORT (Opus's open questions, answered — binding)
- **Hero pair**: use `period.prepared` of `period.expected` only. The run-level "done of slips" belongs to each run
  row (P3). The hero sentence names `now_run` without numbers.
- **Two currencies (H21)**: P2 shows the company-currency figures as they come; when `months[i].runs` counts more
  runs than were summed (P1 exposes this — if it does not, add a `foreign_runs` int per month in a tiny P2 server
  touch), the month facts line adds "%(n)s runs in another currency are not added". Nothing else.
- **People `None` (H14)**: P2 does not render People (P3 card); the hero still shows `prepared` of `expected`
  because `expected` lives under `period`. If `expected` is `None` too, the big figure is `prepared` alone with the
  sub "payslips prepared".
- **Cut-off passed**: when `upcoming` carries no `cutoff`, the hero right card drops the cut-off fact; P3 will add
  next month's cut-off server-side.
- Payload facts you must honour: `learn` may be `None` (H15), bank accounts are a many-to-many (H11, server side
  only), the stage is computed over the reader's company runs (deviation 1), the activation block is shared
  `_activation()` (H19). Read `models/` for the exact key names before writing the template.

## Binding non-goals
No server changes except adding `pb_import_kit` to depends and the kit icon/font additions. No cards row (P3). No
Vietnamese (P3). No dark mode. No Chart.js. No deploy (Fable deploys after P2 — tell Fable in the report which
modules to upgrade: `pb_import_kit` (if icons/fonts changed), `pb_dashboard`).

## Numbered tests (source tests in `tests/test_home_front.py`; keep every existing test green, adapting test_06
to the new template: it now pins "no `ring(` call anywhere" and ZERO `pbd-ring-none`)
1. The template carries the five `data-coach` anchors exactly once each.
2. Every `ic('name'…)` in the template and JS names a key in `pb_import_kit/static/src/js/import_icons.js`.
3. Every `needs_you` key the server can emit (`runs_to_approve, leave_to_approve, other_to_approve,
   settlements_to_check, renewals_to_start, writeups_overdue`) has an entry in the JS words table, and vice versa;
   same for `steps` keys and `upcoming` kinds.
4. No literal "Odoo", no emoji code points, no `#4F46E5` / gradient in template, JS or SCSS.
5. The JS never calls `get_dashboard_data` (only `get_home_data`); the activation markup block is unchanged
   (compare the `pbd-act` block against the pre-P2 template, stored as a fixture string in the test).
6. `money()` unit tests via a tiny pure-JS harness are not possible on the server — instead pin the formatter's
   rules in a Python twin test that reads the JS and asserts the three thresholds and the space before the unit
   appear in the source (string checks), and that `toLocaleString` is used for full values.
7. Manifest: `pb_import_kit` present in depends, version bumped; kit bundle lists `fonts.scss` first and
   `static/fonts/` holds the WOFF2.
8. Browser walk on the clone (only if `free -m` shows ≥ 700 MB; otherwise say so): start the temporary clone server
   (P1 recipe), purge `/web/assets/%` attachments on the clone, open Home standalone and inside the hub, take
   screenshots at 1440 and 1100 px wide, read the console (must be clean), press ← → Esc on the chart, hover a
   column, click the primary button and come back with the back chip. The template clone has little data, so the
   empty states are what you will see — check they match the "empty" row of the words table.

## Deliverables
- `pb_dashboard/static/src/{xml,js,scss}/pb_dashboard.*` rewritten; `pb_dashboard/__manifest__.py` (depends +
  version `19.0.2.1.0` + comment); `pb_dashboard/tests/test_home_front.py`; `test_activation.py` test_06 adapted;
  `pb_import_kit` icons + fonts + version bump.
- Commits per feature (`feat(home): P2 …`, Co-Authored-By line), explicit staging, no push. Ledger rows H-next.

## Report back (`P2_REPORT.md`)
Tests 1–8 with results; screenshots list; the design-bar self-score (1–5 per bullet, one sentence each); modules to
upgrade on deploy; every H row added; deviations with reasons; open questions for P3 (cards row, VI, Learn words).

## How to run tests and walk — exactly as `P1_HANDOVER.md` "How to run tests" (stage `pb_dashboard` AND
`pb_import_kit` into `/tmp/h2stage`; `-u pb_import_kit,pb_dashboard --test-tags /pb_dashboard`).
