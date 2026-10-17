# TIDY Programme Ledger — find it, see it, clean it

Every TIDY phase handover references this file. Read it FULLY before coding. Append
(never rewrite history) when you hit a new gotcha — that is part of every phase deliverable.

Programme: the owner walked the finished GROUP programme (2026-09-08) and came back with
five things: two screens they could not find, a band picture whose dots eclipse each
other, a Budget lens that only reads by the year, and test data named "RIZE" that must
not be seen by a competitor in a demo. Owner chose the phased model (Fable designs, Opus
builds + tests + deploys, phases back to back; only destructive actions or a genuine
scope decision stop the run). The data deletion in P1 IS authorised by the owner in
writing ("you can actually delete them and also many users or employees if they have
Rize written on them") — it still gets a `pg_dump` first.

Phases: **P1 Find it & clean it** · **P2 The band picture** · **P3 Budget, month by month**.

Parent ledgers you must honour, in full: `docs/handovers/GROUP_LEDGER.md` (target,
credentials, binding rules 1–10, rulings, plumbing facts, gotchas GR1–GR60, deploy
ritual), `docs/handovers/WFPLAN_LEDGER.md` (WF1–WF29, deploy ritual, ports), and
`docs/handovers/RIZE_LEDGER.md` (platform contract, R-series). Everything there binds
here; this ledger only adds.

## Target & credentials
As GROUP ledger. GR24 stands: the admin password on file does not work; use a temporary
validator user, archive it at the end of the phase, and list it in the report. WF15
stands for abm. ssh alias `Payobook19v2`. DB order p9clone → payobook → abm →
payobook_template, `pg_dump` before each. Nothing in this programme touches abm data;
abm and payobook_template were checked on 2026-09-08 and hold NO RIZE-named rows.

## Binding rules (in addition to GROUP rules 1–10)
11. **Plain English on every door.** A screen is reachable from where a person would
    look for it, and the words on the menu are the words in the owner's summary. A
    ⌘K row alone is not a door (that is exactly how "Where people work" got lost).
12. **Every person is drawn.** No band picture may say "and N more not drawn". If the
    count is too large for marks, the picture changes shape; it never drops people.
13. **A month is a first-class scope on Budget**, equal to the year: every number,
    word, colour and export the year view has, the month view has too.
14. **Bulk data changes (rename or delete) are by the ORM, inside one transaction,
    after a `pg_dump`, with a before/after count table in the report.** Never raw
    `DELETE` on business tables except where the ledger names the table (fact rows).
15. **Test data is renamed, not deleted, when it carries demo-worthy content** (owner
    amendment 2026-09-08 on P1: the RIZE people hold growth plans, probation reviews
    and coaching notes that make good demos). Rename to realistic names in the style
    of the existing demo data; keep an old→new mapping in the phase log.

## Plumbing facts (verified 2026-09-08 — do not re-derive)

### The two lost doors
- "Who is paid by what" is the Mapping screen's scheme board, registered by
  `pb_scheme_map/static/src/js/scheme_map_board.js` into the soft registry
  `pb_mapping_boards` and mounted by `pb_formula_studio/static/src/js/mapping/
  mapping_studio.js:607-615`. **The tab is labelled "Scheme assignment"**
  (`mapping_studio.js:133`, `.po` msgid at `pb_formula_studio/i18n/vi_VN.po:7483`).
  ⌘K rows 3330/3340 (`scheme_map_palette.js`) already say "Who is paid by what".
- "Where people work" (`pb_workseg`) has NO menu/lens. Doors today: ⌘K rows 3380/3390
  (`workseg_palette.js`), the Employee 360 chip `where_they_work`
  (`workseg_chip.js:58`), and the client actions `pb_workseg.action_pb_assignments` /
  `action_pb_same_person` / `action_pb_cost_transfers` (`views/pb_workseg_action.xml`).
  The screen is `PbAssignmentsScreen` (`assignments.js`, `static props = ["*"]`,
  reads `props.action.context.pb_focus` — `"merge"` → Same person?, else the strip).
- People hub lenses: `registry.category("pb_people_hub_lens")` — the exact precedent
  is Pay: `pb_pay/static/src/js/pay_palette.js:46-52` (`key, icon, label, Component,
  groups`, sequence 45; Records is 40; Plan is last). Hub reads lenses ONCE in setup
  (`people_hub.js:120-128`); a lens that needs the arrival context declares
  `wantsArrival` (`pb_hub/static/src/js/hub_shell.js:315-335`). Lenses receive
  `{embedded, ...def.props}` — the component must tolerate no `action` prop.

### RIZE leftovers on `payobook` (counted 2026-09-08; none on abm/payobook_template)
| What | Count | Ids / notes |
|---|---|---|
| `hr_employee` named `RIZE …` | 27 | 17122–17148 |
| `hr_contract` on those employees | 13 | |
| `hr_payslip` on those employees | 0 | |
| `hr_payslip_run` named `RIZE …` | 3 | 1524 (3 slips), 1525 (1), 1526 (1) — 5 slips total, on non-RIZE employees |
| `hr_department` named `RIZE …` | 3 | 656 "RIZE P4 (test)", 657 "RIZE P9 Function (test)", 658 "RIZE P9 Team (test)" |
| `pb_budget_line` on those departments | 3 | this is the "RIZE P9 Function (test)" Budget card |
| `res_users` with `@example.com` logins | 15 | 14 named RIZE (2326–2342) + 2324 "Trần Minh Khôi" `rize.p3.joiner@example.com` |
| Other tables | unknown | P1 sweeps every table with a `name`/`display_name`/`login` column |

### Pay bands (P2)
- Server: `pb_pay/models/pb_pay_bands.py` — `MAX_DOTS = 400` (line 56), `_fill_band`
  (444–461) sorts people by wage, caps dots, sets `more`; `_band_labels` (463–481)
  builds `more_label` "and N more not drawn"; `_dot` (396–407) → `{id, name, job,
  wage, wage_label, pct, state}`; the proposal path (1140–1170) builds its own dots
  with the same cap. People rows come from `hr.contract` wages (line 291 fields).
- Client: `pb_pay/static/src/js/pay_hub.js` — `axisPct` (367), `live` (373), `dotStyle`
  / `dotClass` / `dotTitle` (396–411); `familyGroups` (fit per family, 320), `toggleDense`
  (356), drag at 418+ with a 160 ms settle then server preview. Template:
  `pb_pay/static/src/xml/pay.xml:239-270` (`.pay-track` holds `.pay-range`, `.pay-mid`,
  one `<button class="pay-dot">` per dot, two `.pay-grip`, two `.pay-edge-lab`).
  Styles: `pb_pay/static/src/scss/pay.scss` `.pay-track` (142), `.pay-dot` (156–171),
  dense track 24px (221), motion block (645).
- Lanes are per currency; a family may "fit" its own axis — every pixel is measured
  against the scope's `axis.max` through `axisPct`, so any new mark must be too.

### Budget (P3)
- Server `pb_budget/models/pb_budget.py`: `get_board(fy, budget_type, currency,
  row_cap)` (145–204) searches `pb.budget.line` for the FY months and hands
  `_matrix` (224–297) rows → functions → departments → months; per function
  `budget/spent/left/burn/pace/gap/tone/tone_label` and `months[{key,budget,spent}]`;
  `_kpis` (339), `_headline` (358), `_tone`/`_tone_label` (308/328), `_pace(fy)` (124)
  = share of the year gone. `get_function(function_id, fy, type, currency)` (391–415)
  re-calls `get_board` and adds `expenses` + `rows` (per line: month, department,
  budget, spent, left, source…). `budget_actuals.py` writes one `pb.budget.line`
  per (company, department, month, type) from `pb_fact_line` — actuals ARE monthly.
- Client `pb_budget/static/src/js/budget_board.js` (440 lines): state `view heat|table,
  fy, type, currency, open, drill`; `monthHeight` (173), `openFunction` (207).
  Template `pb_budget/static/src/xml/budget_board.xml` (588 lines): KPIs, tiles with
  `.bdg-spark` per month (227–233), the drill with `.bdg-months` bars (250–266),
  departments table, expenses table, table view with month expansion (340–380).
- Export `pb_budget/models/budget_export.py` `build(fy, budget_type, currency)` calls
  `get_board` — a month scope must be threaded through the same signature.
- Insights lens registration: `pb_budget/static/src/js/budget_palette.js:56-62`
  (`INSIGHTS_LENSES`, key `budget`, sequence 20); ⌘K rows 3000–3030.

## Deploy ritual
Exactly the GROUP/WFPLAN ritual (clean stage `/tmp/tidy_stage`, scoped per-module
`rsync --delete`, tests on p9clone `--http-port=8199 --gevent-port=8198` detached with
`--logfile` (GR57), `pg_dump` per DB, asset purge, manifest-vs-`latest_version` and
tree-hash verification, never `pkill -f odoo-bin`).

## Gotcha ledger (append below; T-numbers)

- T1 (P1): **`hubBack` takes the props and ONLY the props, and a second
  argument is not an error.** `pb_workseg` called `hubBack(this.env,
  this.props)`; the helper reads `props.action.context.pb_back`, the
  environment has no `action`, so it answered `null` on every road in and the
  back chip was absent on a screen whose action record carries a perfectly
  good `pb_back`. Nothing is logged, nothing throws, and the chip is DESIGNED
  to be absent when there is nowhere to go — so the bug is indistinguishable
  from the intended empty state. A helper whose whole job is to return `null`
  cheaply needs its call sites read, not its output trusted.
- T2 (P1): **a kit class and a module class on the same element must not
  share a name.** The new segmented control was written
  `class="pbim-segbtn wsg-seg on"`, and `.wsg-seg` has meant "a stretch of
  days" in `pb_workseg` since it was written. The module's own rule
  (`.pbim.pbim-page.wsg .wsg-seg`, four classes) beat the kit's
  (`.pbim .pbim-segbtn.on`, three), so the segment the reader was standing on
  rendered its background as the page's own grey and its text as white —
  white on white, with the class list looking exactly right in the inspector.
  Grep the module's SCSS for a class before borrowing the name; the kit's
  primitives are only safe next to a name nothing else owns
  (`.wsg-lenstab` now).
- T3 (P1): **`cursor.fetchall()` on an UPDATE raises, and inside a savepoint
  that exception silently rolls the UPDATE back.** One helper was doing both
  queries and statements; every raw write of the first pass was undone by the
  code written to protect it, and the only trace was one printed line per row
  in a log nobody was reading yet. A statement and a query do not share a
  helper: `q()` returns rows, `run()` returns whether it worked.
- T4 (P1): **a rename through the ORM is a CHANGE, and the platform writes
  changes down.** Renaming twenty-seven people put the OLD name back on the
  screen 197 times over — one `mail.tracking.value` per field with the old
  value in it, a notification message to carry each one, and eight
  `biz.audit.entry` rows. The word came off the label and reappeared in the
  chatter underneath it. Any bulk rename needs `tracking_disable=True` on the
  write AND a sweep of the tracking values, the notes they emptied and the
  audit rows, or the sweep that proves the work reports its own footprints.
- T5 (P1): **`rize` cannot be matched as a whole word, only as a word
  START.** A word-boundary rule on both sides (`[^a-z]rize[^a-z]`) leaves
  `authorize`, `categorized`, `prioritize` and `summarize` alone — and misses
  every identifier the connected system writes, because those are
  `RIZEP3T2002` with no separator at all. The rule that works is
  "not preceded by a letter": nothing in English begins with those four
  letters, so the leading half alone is both complete and safe.
- T6 (P1): **an `odoo-bin shell` script that never reaches `cr.commit()` can
  still have committed.** A long delete run was killed after its final sweep
  and before its commit, and the work was on disk anyway — something in the
  chain (`pb.budget.actuals.sync()` is the likeliest) had committed the
  cursor for its own reasons. A shell script is NOT a transaction you own
  from end to end; if the work must be reversible, take the `pg_dump` and
  plan to restore from it, because "I killed it before the commit" is not a
  rollback.
- T7 (P1): **a `pgrep`/`until` guard written on one line matches ITSELF.**
  `until ! pgrep -f "test-enable"; do sleep 10; done` never exits, because
  the shell running it has `test-enable` in its own command line. The same
  family as the ledger's standing "never `pkill -f odoo-bin`". Match on
  something only the target has (`odoo-bin.*test-enable`) or poll a file the
  target writes.
- T8 (P1): **adding a group to a user in one process does not reach the
  worker serving the browser.** The reader was granted the budget groups
  through the shell, logged out, logged back in, and was still refused — the
  ACL answer is `ormcache`d in the running worker and a commit from another
  process does not clear it. A service restart does. Same family as GR58.
- T9 (P1): **the People hub has EIGHT lenses, not the five the closeout
  named.** Records (40), Pay (45), Assets (50) and Praise (60) are all
  registered by other modules, so "after Pay, before Plan" is a range with
  three residents in it, and a new sequence has to be read off the registry
  rather than off the design note. `where` is 48.
- T10 (P1): **the manifest `description` of thirteen shipped modules opens
  with "RIZE phase Pn — …"**, and GR7 already ruled that a manifest
  description is a user-visible string (it is what the Apps list prints).
  The database copy cannot be fixed by hand: `ir_module_module.description`
  is rewritten from the manifest on the next upgrade. It is a one-line edit
  per module and belongs to a commit of its own; recorded here as an owner
  debt rather than done inside this phase's scope.

- T11 (P2): **purging `/web/assets/%` is NOT enough for a pure JavaScript
  change on this box, and a change to the manifest's asset LIST is invisible
  without a restart whatever you purge.** WFPLAN's WF18 says in brackets that
  deleting alone is enough for a `.js` change; it is not — a new file added to
  `web.assets_backend` never appeared in the bundle at all (the browser
  reported "modules needed by other modules but have not been defined" and the
  screen died on `Cannot find key "pb_pay" in the "actions" registry"), and two
  later JavaScript-only edits rebuilt the bundle under the SAME hash from the
  old contents. The running workers hold the manifest they were started with.
  `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` **and**
  `sudo service odoo-server restart`, every time, or half an hour goes on
  reading the right file on disk and the wrong one in the browser.
- T12 (P2): **an existing term that gains a JAVASCRIPT caller keeps printing in
  English until the `.pot` is exported again.** "%(count)s below" had lived in
  the catalogue since P6a with one occurrence — the Python facade. Moving the
  chip into the browser so it could answer during a drag left the msgid
  unchanged and the sentence untranslated: `_t()` in the browser reads
  `get_web_translations`, which only carries entries whose occurrences are
  marked `odoo-javascript`. The screen printed "57 below" beside a fully
  Vietnamese picture. GR58's trap, entered from the other side: moving a string
  between the server and the browser is a CATALOGUE change even when not one
  character of the string moves.
- T13 (P2): **`import … from "./thing.js"` under node reads a CommonJS module
  and finds no named exports.** A `.js` file with no `package.json` saying
  `"type": "module"` beside it is CommonJS to node, whatever `export function`
  is written inside it, and the error names the file rather than the reason.
  The repository's own precedent already had the answer — `tools/
  decision_engine_check.mjs` reads the source off disk and hands it to the
  runtime as a `data:text/javascript;base64,…` URL, which also guarantees the
  check runs against the file EXACTLY as it ships.
- T14 (P2): **a bin is eight pixels wide and a three-digit number is twenty.**
  Printing the count over every column ≥ 10 people produced a run of numbers
  printed on top of one another — "1 480" where the truth was "148" and "0" —
  and the first build of the picture shipped it. Counts are now laid out left
  to right and one is drawn only when it clears the last one by 30 px; every
  column still carries its exact figure on its own label and in the list it
  opens. Same family: the median's own writing, and the two figures at the ends
  of a band, are dropped when the band is drawn narrower than the words.
- T15 (P2): **a bottom sheet pinned to the viewport's left edge is painted over
  by the application's own icon rail.** `.pb-sidebar` is `position: absolute` at
  **z-index 25** and this module's ceiling is 20 (`pb_hub/tests/test_static.py`),
  so a full-bleed phone sheet lost its first sixty pixels — every name started
  mid-word and the screenshot was the only way to see it, because the DOM
  geometry was perfectly correct (`left: 0, width: 390`). Phone sheets start at
  `left: 60px`; never fight the rail with a z-index this module may not have.
- T16 (P2): **key a redrawn mark by WHERE it is, never by what colour it is.**
  The bins were keyed `band:bin:state`, so every recolour during a drag
  destroyed the element and built a new one — which replayed the fade-in, under
  the hand that was dragging. Keyed by position instead, the same element
  changes class and the only thing that moves is the colour, which is what the
  gesture is for.
- T17 (P2): **the chips came from the server and the marks recoloured in the
  browser, so one row carried two answers to the same question.** Mid-drag the
  picture showed 432 people below the edge and the chip beside it still read
  "57 below" — both correct about different moments, which on screen is simply
  wrong. Anything that answers WHILE a gesture is happening has to be computed
  from the same numbers the gesture is redrawing (here the complete `wages`
  list), not read from the payload that arrived before it started.
- T18 (P2): **there are TWELVE manifests that open "RIZE phase Pn", not
  thirteen** (T10 counted from a stale grep), and the search for them cannot be
  case-insensitive: `Categorized`, `authorized` and `Authorized` are the false
  positives T5 warned about, in manifest prose this time. While counting them,
  a wider sweep found **thirteen OTHER `pb_*` manifests whose `name`, `summary`
  or `description` still says "Odoo"** — `pb_explorer`, `pb_hub`, `pb_mission`,
  `pb_sidebar`, `pb_wf_kit`, `pb_login_language`, `pb_hr_payroll_demand` and six
  per-country payroll modules. GR7 makes every one of those a user-visible
  string in the Apps list. Recorded here as an owner debt, not fixed in P2.

## Phase log
- P3 — "Budget, month by month" — designed and BUILT 2026-09-08
  (`TIDY_P3_BUDGET_MONTH_BY_MONTH.md`). Status: **COMPLETE**.
  `pb_budget` 19.0.2.1.0 live on p9clone, payobook, abm and
  payobook_template, together with the seventeen manifests of deliverable 1e
  (`pb_explorer` 19.0.2.2.1, `pb_hub` 19.0.1.8.1, `pb_mission` 19.0.1.8.1,
  `pb_sidebar` 19.0.3.2.2, `pb_wf_kit` 19.0.1.5.2, `pb_login_language`
  19.0.1.0.1, `pb_hr_payroll_demand` 19.0.1.0.1, `biz_theme` 19.0.1.5.1, the
  six per-country payroll modules at 16.0.1.0.1, and — found while checking the
  work, T21 — `pb_zoho_sso` 19.0.1.0.1, `biz_debrand` 19.0.2.4.1 and
  `biz_mail_debrand` 19.0.1.0.1). All eighteen module trees verified
  byte-identical to the repository on the server, and every installed
  manifest version verified against `ir_module_module.latest_version` on all
  four databases.

  **A MONTH IS A SCOPE, EQUAL TO THE YEAR (rule 13).** Under the numbers sits
  a strip of thirteen chips — "Whole year" and the twelve months — and each
  month already answers, before anything is clicked, how far its spend fell
  either side of its budget: a two-tone micro bar (the track is the budget,
  the fill is what was spent, coloured by that month's own word) and a signed
  percentage. The month we are in is marked "now"; a month that has not
  started with nothing on it says "not yet"; a month with no budget says "no
  budget". Click one and the WHOLE board becomes that month — the KPIs and
  their captions, the headline, every tile's numbers, words and colours, the
  notch, the drill, the table and both exports — in one motion, because the
  functions are sorted by the YEAR's spend whatever the scope and keyed by
  their own id, so no tile moves and the bars travel to their new figures.
  ← and → walk the strip, Escape and the "Whole year" chip always come back,
  and `pb_focus: "month:2026-03"` (or `"month:current"`) opens the lens
  already scoped, through a new ⌘K row **"Budget this month"** at 3005.

  **The month has its own five words** — Over budget, Close to budget, Under
  budget, No budget set, Not yet — decided against the budget itself with a
  ±5% band rather than against a calendar there is none of inside a month, and
  **its own five sentences**: "March: 4 of 9 functions went over budget;
  Retail by the most (…)" / "March came in … under budget across 9 functions."
  / "March has no budget set; … was spent." / "September so far: 0% of the
  month's budget spent with 23% of the month gone." / "December has not
  started." Every one was produced live on real data during the walk.

  **The drill answers "compared with what".** `get_function(month=…)` adds a
  row of four small figures — this month, the month before, the same month a
  year ago and the monthly average — and the year-ago cell is BLANK with the
  words "no data" rather than a zero that would read as a collapse. The
  twelve-bar chart keeps the whole year with the chosen month lit; the
  departments, the expenses and the rows underneath are that month's, with
  Variance and Variance % columns toned by the same five tones.

  **The spreadsheet and the PDF are the month too.** `build(month=…)` names
  the sheet "Budget June 2026", drops the twenty-four month columns nobody
  opened a month's file to read, and answers with Variance and Variance %
  where the year's answers with Used and Year gone. Verified live on payobook:
  `Budget June 2026 People.xlsx` and `Budget June 2026 People.pdf`.

  **Vietnamese, from nothing.** `pb_budget` had NO catalogue at all before
  this phase. It now ships `i18n/pb_budget.pot` and `i18n/vi_VN.po` with
  **287 terms, 0 English survivors, 0 fuzzy entries, 0 lost placeholders, 0
  entries missing their `#. module:` comment (GR5) and the word "Odoo" in no
  translation** — and the month names come from babel in the reader's own
  language ("Thg 1" … "Thg 12", "Tháng 6 2026"), not from `strftime` in the
  server's locale.

  **Deliverable 1e.** No `pb_*` or `biz_*` manifest `name`, `summary` or
  `description` contains "Odoo" any more, proven by a repo-wide `ast` sweep —
  and, going one level deeper than the spec asked, **no `pb_*`/`biz_*` row of
  `ir_module_module` on any of the four databases** does either (T21: three
  modules had no description key at all and the platform was printing their
  README).

  **Tests.** 39 `pb_budget` test methods on p9clone (29 post-install),
  **0 failed and 0 errors**, including the eleven new ones covering T1–T6.
  The wider run over 228 tests (`pb_budget` 39, `pb_explorer` 55, `pb_hub` 34,
  `pb_insights_hub` 40, `pb_mission` 58, `pb_sidebar` 48) reports **3
  failures, all three in `pb_sidebar` and all three pre-existing** — the
  retired planning module's dead xmlids, recorded as T19 — and nothing else:
  zero regressions.

  **Browser.** B1–B9 walked on p9clone, payobook and abm at 1440 and 390, in
  English and Vietnamese, with no console errors. Screenshots:
  `docs/handovers/tidy_p3_shots/`.

  Owner debts: the payobook administrator password in the GROUP ledger is
  still wrong (GR24) and so is abm's (WF15) — P3 used one temporary
  `tidy.p3@payobook.com` on each of p9clone (4327), payobook (4426) and abm
  (261), all archived again at the end of the phase; the three `pb_sidebar`
  test failures (T19) are a `pb_hr_workforce_planning` retirement debt and
  belong to whoever finishes GR49's sweep; the six per-country payroll modules
  were patch-bumped for tidiness but are `uninstallable` on all four databases
  (16.0 manifests on a 19.0 server) and their summaries were never printed
  anywhere; the `pbim` kit still has no dark palette (GR38).

- P2 — "The band picture" — designed and BUILT 2026-09-08
  (`TIDY_P2_THE_BAND_PICTURE.md`). Status: **COMPLETE**.
  `pb_pay` 19.0.3.1.0 live on p9clone, payobook, abm and payobook_template,
  together with the twelve manifests of deliverable 1d (`pb_assets` 19.0.1.0.1,
  `pb_budget` 19.0.2.0.1, `pb_comp_ben` 19.0.1.0.1, `pb_contract_lifecycle`
  19.0.1.0.1, `pb_lifecycle` 19.0.1.3.1, `pb_offboarding` 19.0.1.0.1,
  `pb_onboarding` 19.0.1.0.1, `pb_pip` 19.0.1.1.1, `pb_probation` 19.0.1.1.1,
  `pb_rnr` 19.0.1.0.1, `pb_zoho_bridge` 19.0.1.0.1, `pb_vendor_access`
  19.0.1.7.1). All thirteen module trees verified byte-identical to the
  repository on the server and every manifest version verified against
  `ir_module_module.latest_version` on all four databases.

  **The picture changes shape rather than dropping anybody (rule 12).**
  The server sends `wages` — every person's pay, sorted, as whole units of the
  band's own currency — for every band, however many people are in it, and
  sends the named `dots` only while a band holds 24 people or fewer. `MAX_DOTS`,
  `more` and `more_label` are gone from the band payload and the words "not
  drawn" appear in no Python file, no template, no catalogue and nowhere on any
  screen. Up to 24 people the picture is a NAMED DOT each, dodged: sorted by
  pay, placed on the axis, and stepped onto one of five rows around the track's
  midline whenever a dot would land within 10 px of another on the same row —
  a beeswarm, so twenty-two people paid almost the same amount form a tidy
  block instead of a smear. Above 24 the track is cut into bins of 8 px (6 px in
  dense mode and on a phone) and each bin is drawn as PIPS — one 5 × 5 px square
  per person, up to six, so six people read as six — or as a COLUMN whose
  height is `24 px + 14 px × √((count − 6) / (busiest − 6))`, capped 4 px short
  of the track. A bin that straddles a band edge is split by wage into stacks
  side by side, so the colour boundary is exact to the person.

  **`pb_pay/static/src/js/band_picture.js`** is a pure module — no OWL, no
  `@web`, nothing but numbers in and objects out — holding `binPeople` and
  `dodgeDots`, and **`pb_pay/tools/band_picture_check.mjs`** runs 13 checks
  over it under node in under a second (T3a: over 400 random boards every
  person lands in exactly one bin; T3e: over 400 random boards no two dots on a
  row are ever closer than the gap, including boards where everybody is paid
  the same). The check is wired into the Python suite too, so it cannot rot.

  **A column can be asked WHO.** `pb.pay.bands.people_between(scope, low, high,
  limit=20)` is behind `READ_GROUPS` and scoped exactly as `get_board` is; every
  band carries a `people_scope` so a saved band is found by its id and a
  suggested one by its bucket and its proposed edges. Every mark is a button:
  hover or focus says "54 people · 8.6M ₫ to 8.9M ₫ · in the band", Enter or a
  click lists up to twenty of them by name, job, pay and standing with "and 34
  more.", a close button, a click on the veil and Escape (capture, WF4).

  **The whole row answers while the edge is moving.** The marks recolour from
  `live(band)` on every frame, and the chips are now computed in the browser
  from the same complete list of wages (T17), so mid-drag the picture, the chip
  and the server's own sentence agree: 432 rose marks, "432 below", "14B ₫ a
  year to bring 432 people back in". A thin tick marks the middle of what the
  band's people are actually PAID, written "median 8.5M ₫" above the track when
  the band is wide enough to hold the words.

  **Tests.** 111 `pb_pay` tests on p9clone, **0 failed and 0 errors**,
  including the three new ones (T1 every person in the payload and no band
  counting people it did not draw; T2 `people_between` names exactly the people
  in that slice, caps at twenty, tells the truth about the total, never crosses
  a company and refuses a reader with no role; T3 the node check). The wider
  run over 262 tests (`pb_pay` 111, `pb_group` 54, `pb_contracts` 48,
  `pb_hub` 34, `pb_people_hub` 33, `pb_budget` 26) reports the SAME 3 failures
  the ledger has recorded as p9clone data drift since GROUP P6a
  (`pb_contracts` ×2, `pb_group` `test_t9`) and nothing else: zero regressions.

  **Vietnamese** is complete: 770 exported terms, 0 English survivors, 0 lost
  placeholders, 0 fuzzy entries and the word "Odoo" in no translation — and the
  `.pot`'s own header no longer carries it either.

  **Browser.** B1–B8 walked on p9clone, payobook and abm at 1440 and 390, in
  English and Vietnamese. Screenshots: `docs/handovers/tidy_p2_shots/`.
  On the demo company (4,500 people over 21 suggested bands) **every band's
  drawn count equals its people count and no two marks' bounding boxes
  intersect anywhere on the screen** — measured in the browser, on p9clone,
  payobook and abm. On abm, 28 of 29 bands draw named dots and one draws
  columns; nothing overlaps there either.

  The p9clone rehearsal (21 accepted bands, 10 families, 30 job links, one
  dragged and undone edge) was DELETED afterwards and verified gone; payobook,
  abm and payobook_template carry **0 bands, 0 families and 0 job links** — the
  demo company still opens on the suggestion, so nothing was written to
  production beyond the module upgrades.

  Owner debts: the payobook administrator password in the GROUP ledger is still
  wrong (GR24) and so is abm's (WF15) — P2 used one temporary
  `tidy.p2@payobook.com` on each of p9clone (4312), payobook (4424) and abm
  (259), all archived again at the end of the phase; thirteen OTHER `pb_*`
  manifests still say "Odoo" in the Apps list (T18); the calibration scatter in
  Pay Review still caps at 900 dots and is the one picture in this module that
  can still drop a person (Phase 4 candidate); the `pbim` kit still has no dark
  palette (GR38).

- P1 — "Find it & clean it" — designed 2026-09-08, BUILT the same day
  (`TIDY_P1_FIND_IT_AND_CLEAN_IT.md`, amended mid-phase by the owner: the
  RIZE data is RENAMED, not deleted). Status: **COMPLETE**.
  `pb_formula_studio` 19.0.1.181.0 and `pb_workseg` 19.0.1.3.0 live on
  p9clone, payobook, abm and payobook_template; both trees verified
  byte-identical to the repository on the server and every manifest version
  verified against `ir_module_module.latest_version` on all four.

  **1a — the tab says what every other door says.** The Mapping screen's
  scheme tab read "Scheme assignment" while the ⌘K rows, the board itself and
  the owner's own summary all said "Who is paid by what". It now reads
  "Who is paid by what" (Vietnamese "Ai được trả lương theo phương án nào",
  taken from `pb_scheme_map`'s catalogue rather than invented a second time),
  and a repo-wide test asserts the old words survive in no `pb_*` module.

  **1b — "Where they work" is a lens on the People hub.** New
  `pb_workseg/static/src/js/workseg_lens.js` registers `where` at sequence 48
  behind `WORKSEG_GATE`, with `wantsArrival` so a deep link can be more
  specific than the lens. `PbAssignmentsScreen` reads its focus from
  `props.arrival.focus` first and its own action context second, hides its
  back chip when embedded, and names the breadcrumb only when it is a screen
  of its own. The three things a person may want are ONE segmented control:
  **"The month strip" · "Same person?" · "Charged between entities"**, the
  third opening the cost-transfer list in the breadcrumb with a `pb_back` to
  the People hub on the `where` lens. Both ⌘K rows (3380, 3390) now open the
  hub on that lens rather than the bare client action, so the two roads land
  in the same place with the same way out. The action, the module category,
  the privilege and the group are all renamed to "Where they work" too — one
  screen, one name. `pb_workseg` now depends on `pb_people_hub`; the hub
  reaches this module through nothing, so there is no cycle.
  The People hub now reads: **Employees · Contracts · Records · Pay · Where
  they work · Assets · Praise · Plan.**

  **1c — the RIZE test data is RENAMED (owner ruling, mid-phase).** The
  deletion was designed, rehearsed and — on `p9clone` only — committed,
  before the owner ruled that the growth plans, probation reviews, coaching
  notes and letters on those people are good demo content and only the
  programme's own vocabulary must go. **`payobook` was never deleted from.**
  `p9clone` was restored from
  `/odoo/backups/p9clone_before_tidy_p1_20260907_212559.dump` and verified
  identical to payobook (27 employees, 15 logins, 3 pay runs, 3 teams, 5
  payslips, 4,561 employees) before the rename ran.
  46 personas were given real Vietnamese names in the demo company's own
  style, checked for collisions against every employee and every contact on
  the database; every login and work address became
  `firstname.lastname@example.com`; teams 656/657/658 became **Facilities**,
  **Quality Assurance** and **Site Services**; runs 1524–1526 became
  **Retail top-up — Sep 2026**, **Awards run — Oct 2026** and **Retail bonus
  run — Nov 2026**; and every sentence anywhere in the database that named
  the old thing was rewritten to name the new one, so Growth Plans now reads
  "HR OWNER: Nhâm Đức Tài".
  **2,392 → 13 on payobook and 2,289 → 13 on p9clone**, across 87 columns of
  every text and jsonb column in the database. The 13 that remain are the
  same 13 on abm and payobook_template, which never held any test data at
  all: 11 `ir_model_data.name` xmlids shipped by `pb_onboarding` /
  `pb_offboarding` (technical identifiers, which the white-label rule
  explicitly does not touch — the templates they name read "New joiner — the
  full welcome"), 1 `ir_module_module.description` that comes from
  `pb_lifecycle`'s manifest (T10), and `res_country_state` "Rize", a real
  province of Türkiye that ships with the platform.
  Nothing was deleted from production. Everything is still there; it is
  simply called something a customer can read.

  **Tests.** 459 on p9clone (`pb_formula_studio` 411, `pb_workseg` 55,
  `pb_people_hub` 33, `pb_budget` 26 — counted per module, 459 distinct) with
  **2 failures, both the p9clone data drift the GROUP P7 entry recorded**
  (`test_07a2_the_board_opens_on_a_connector_that_HAS_rules`,
  `test_03j_the_run_lane_is_a_ghost_when_nothing_was_processed`) and 0
  errors. Zero regressions. `pb_workseg` gained 12 tests: T2 (the lens is on
  the hub at 48, one gate, an ordinary employee is not offered it, no
  dependency cycle) and T3 (both roads carry the same focus, the ⌘K rows land
  on the lens, no second back chip, the segments say what the owner says, the
  charged list carries a way back, one screen has one name).

  **Browser.** B1–B10 walked on payobook and p9clone at 1440 and 390, in
  English and Vietnamese. Screenshots: `docs/handovers/tidy_p1_shots/`.

  Owner debts: the payobook administrator password in the GROUP ledger is
  still wrong (GR24) — P1 used `tidy.p1@payobook.com` and
  `tidy.p1.vi@payobook.com`, archived at the end of the phase; the thirteen
  module manifests that open "RIZE phase Pn" (T10) are a commit of their own;
  the p9clone deletion rehearsal is recorded here as history and the dump it
  was restored from is kept.


### P1 name map (old → new)

| Old | New | Login / address |
|---|---|---|
| RIZE P4 Manager | Ngô Bảo Lâm | lam.ngo@example.com |
| RIZE P4 Leaver | Lâm Tuấn Kiệt | kiet.lam@example.com |
| RIZE P4 Zoho Leaver | Tạ Quỳnh Chi | chi.ta@example.com |
| RIZE P5 Passer | Chu Hải Đăng | dang.chu@example.com |
| RIZE P5 Extender | Đặng Thuý Vân | van.dang@example.com |
| RIZE P5 Leaver | Mai Quốc Hưng | hung.mai@example.com |
| RIZE P5 Backfill | Lương Nhật Minh | minh.luong@example.com |
| RIZE P5 Peer One | Tống Khánh Ly | ly.tong@example.com |
| RIZE P5 Peer Two | Hà Tuấn Phong | phong.ha@example.com |
| RIZE P5 Peer Three | Kiều Thanh Trúc | truc.kieu@example.com |
| RIZE P6 Alpha | Đinh Gia Huy | huy.dinh@example.com |
| RIZE P6 Bravo | Cao Bảo Ngọc | ngoc.cao@example.com |
| RIZE P6 Charlie | Tô Đức Thắng | thang.to@example.com |
| RIZE P6 Delta | Nghiêm Hải Yến | yen.nghiem@example.com |
| RIZE P7 Award Tester | Bạch Minh Quân | quan.bach@example.com |
| RIZE P8 Star | Ninh Thu Trang | trang.ninh@example.com |
| RIZE P8 Colleague | Quách Anh Tuấn | tuan.quach@example.com |
| RIZE P9 Function Head | Thái Ngọc Diệp | diep.thai@example.com |
| RIZE P10 Ends45 | Ưng Hoàng Long | long.ung@example.com |
| RIZE P10 Extend | Từ Mỹ Duyên | duyen.tu@example.com |
| RIZE P10 Window | Lại Đình Nam | nam.lai@example.com |
| RIZE P10 Convert | Sầm Kim Chi | chi.sam@example.com |
| RIZE P10 NoPass | Triệu Văn Lộc | loc.trieu@example.com |
| RIZE P10 Endit | Bành Thanh Hà | ha.banh@example.com |
| RIZE P10 Lapsed | Doãn Trọng Nghĩa | nghia.doan@example.com |
| RIZE P10 Intern | Giang Tuyết Nhung | nhung.giang@example.com |
| RIZE P10 Arriving Intern | Hồng Việt Anh | anh.hong@example.com |
| RIZE P3 Colleague A | Khổng Bích Ngọc | ngoc.khong@example.com |
| RIZE P3 Colleague B | Lư Trung Kiên | kien.lu@example.com |
| RIZE P3 Leaver Test | Mạc Hoài Thương | thuong.mac@example.com |
| RIZE P6 HR | Nhâm Đức Tài | tai.nham@example.com |
| RIZE P6 Plain | Ông Thảo Vy | vy.ong@example.com |
| RIZE P6 Lifecycle+PIP | Phùng Xuân Trường | truong.phung@example.com |
| RIZE P9 Finance | Quản Diệu Linh | linh.quan@example.com |
| RIZE P9 Plain | Sử Công Danh | danh.su@example.com |
| RIZE P9 Planning User | Tăng Hạnh Nguyên | nguyen.tang@example.com |
| RIZE P9 Planning + Budget | Uông Bá Lộc | loc.uong@example.com |
| Rize Tester One | Vi Thuỳ Dương | duong.vi@example.com |
| Rize Ambiguous Twin | Xa Hữu Phước | phuoc.xa@example.com |
| Rize File Leaver | Yên Ngọc Hân | han.yen@example.com |
| Rize File Newjoiner | Bế Quang Vinh | vinh.be@example.com |
| Rize Killswitch Test | Chử Lan Phương | phuong.chu@example.com |
| Rize Vietnam Joiner | Dư Thành Trung | trung.du@example.com |
| Rize Vietnam Reviewcase | Hoắc Minh Tú | tu.hoac@example.com |
| Rize Vietnam Joiner Two | Lãnh Bảo Trân | tran.lanh@example.com |
| Rize Backfill Leaver | Đoàn Hải Sơn | son.doan@example.com |
| (Trần Minh Khôi — name kept) | Trần Minh Khôi | khoi.tran@example.com |

Everything else the sweep found, renamed the same way and in the same
transaction: teams **RIZE P4 (test) → Facilities**, **RIZE P9 Function (test)
→ Quality Assurance**, **RIZE P9 Team (test) → Site Services**; pay runs
**RIZE P7 test run — Sep 2026 → Retail top-up — Sep 2026**, **RIZE P7 award
run — Oct 2026 → Awards run — Oct 2026**, **RIZE P7 neutral run — Nov 2026 →
Retail bonus run — Nov 2026**; vendors **RIZE P11 Talent Partners → Talent
Partners** and **RIZE P11 Cloudline Software → Cloudline Software**, its
agreement **RIZE P11 lapsed support contract → Lapsed support contract**;
budget notes **RIZE P9 currency test → Cross-currency check**, **RIZE P9
scoping test → Site Services budget**, **RIZE P9 test expense → Site Services
expense**; the asset **Test laptop (RIZE P4) → Spare laptop (Facilities)**
(serial `RIZE-P4-TEST-001 → LAP-2026-0091`); the job title **RIZE P10 test →
Fixed-term operative**; the headcount period **RIZE P10 contractor check →
Fixed-term contractor check**; contract names **"P10 fixed-term — X" →
"Fixed-term — X"**; the connected system's identifiers `RIZE… → ZH…`; and the
three alert addresses that belong to a mailbox rather than a person
(`hr.alerts@`, `digest.check@`, `finance.team@example.com`).

- T19 (P3): **three `pb_sidebar` tests have been failing since GROUP P6b
  retired the legacy planning module, and nobody had run them.** P3 bumped
  `pb_sidebar` for one line of manifest prose, which upgraded it on p9clone
  for the first time since the retirement — and `test_ia_c5` immediately
  reported seven RETIRED rail items pointing at
  `pb_hr_workforce_planning.action_wfp_*` xmlids that no longer resolve, plus
  two highlight-matrix rows naming `wfp_dashboard`. The failures are pure data
  drift (`git diff pb_sidebar` in this phase is four lines of a manifest) and
  they predate P3 — but they are the second half of GR49: uninstalling a module
  leaves everything that POINTS at it behind, and a retired-item row is exactly
  such a pointer. A retirement needs its sweep to include the rail's own
  retired list and the tests that pin it. Recorded as an owner debt, not fixed
  in this phase (the rail is an explicit non-goal here).
- T20 (P3): **an upgrade fails outright if one of the module's own crons is
  RUNNING.** `-u pb_budget` on p9clone died in `data/ir_cron.xml` with
  "This cron task is currently being executed and may not be modified" —
  Odoo 19's `ir.cron.write` refuses a row another worker holds, and the whole
  registry load rolls back with a `ParseError` naming the XML rather than the
  reason. On p9clone the live service stays up during a rehearsal (the ledger's
  own ritual), so the nightly budget job had just fired. Nothing was applied
  and a plain retry a minute later worked. Any module that ships an `ir.cron`
  can lose an upgrade to a coin toss: read the failure for the phrase
  "currently being executed" before believing the XML is broken.
- T21 (P3): **a module with no `description` key in its manifest has its
  README printed in the Apps list.** T18's sweep read the manifests and found
  thirteen; the DATABASE had sixteen, because `pb_zoho_sso`, `biz_debrand` and
  `biz_mail_debrand` declare no description at all and the platform falls back
  to `README.md` — engineering prose that names the vendor in almost every
  paragraph, and in two of the three the whole subject IS the vendor. A
  repo-wide grep of manifest strings cannot see this; the query that can is
  `SELECT … FROM ir_module_module WHERE description::text ILIKE '%odoo%'`,
  run per database. Fixed by giving each of the three an explicit plain-English
  `description` (which overrides the README for the Apps list and leaves the
  README on disk for engineers).
- T22 (P3): **`env.company` is not necessarily inside `env.companies`, and a
  fixture built in the first is invisible to a facade that reads the second.**
  On p9clone the superuser's `company_id` is 1 and its `company_ids` is `[5]`,
  so three budget rows created in "the current company" were not found by
  `get_board` — which scopes explicitly to `env.companies.ids` — and two brand
  new tests failed with an empty board and nothing in the log. A test fixture
  for any company-scoped facade builds in a company the FACADE can see
  (`self.env.companies`), never in `self.env.company`.
- T23 (P3): **setting `disabled` on the button the keyboard is standing on
  blurs it, and the next arrow press goes nowhere.** The month strip disabled
  every chip while the board re-scoped; after ← or → the focused chip was
  disabled mid-flight, lost focus, and the following press was read against a
  state that still said "the whole year", which sent it to January from
  anywhere. Two lessons in one: a busy guard belongs in the HANDLER, not on the
  control's `disabled` attribute; and where the keyboard is standing is the
  element that has FOCUS (`ev.target.closest('[data-month]')`), never the
  application state that a keypress is about to change.
- T24 (P3): **`_()` in a Python facade cannot translate a literal that lives
  in a list somewhere else.** `type_label` read its three words out of the
  `BUDGET_TYPES` tuples and passed them to `env._()`. The extractor never sees
  such a string as a Python term, so the catalogue carried it only as a
  `model:ir.model.fields.selection` entry — which is imported into the database
  column and is invisible to `code_translations`, the dictionary `_()` reads.
  The three chips at the top of the Budget board therefore printed "People /
  HR operations / Admin" on a screen where the headline, every tone word and
  every KPI caption were already Vietnamese. GR58 from the server side: the
  literal is written HERE, inside the `_()` call, in a dict keyed by the value
  (GR59), and the `.pot` then carries a `code:…py` occurrence for it.
