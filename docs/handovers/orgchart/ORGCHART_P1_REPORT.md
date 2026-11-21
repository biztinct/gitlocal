# ORGCHART P1 — report (the chart, read-only)

Implemented per `ORGCHART_P1.md` and `ORGCHART_LEDGER.md`. New module
`pb_orgchart` **installed and live on all four databases** (`payobook`,
`payobook_template`, `p0clone`, `rize`); `abm` not touched. Browser walk on
rize.payobook.com as the signed-in admin (Ash Sohani) and payobook.com as the
signed-in demo admin (Mitchell Admin) — sessions were already open, no login
was typed anywhere.

## 1. Files and commits

| Commit | What |
|---|---|
| `b2df028cf` | **Kit glyphs** (own commit): `network`, `listTree`, `rows2`, `crosshair`, `zoomIn`, `zoomOut`, `expand`, `shrink`, `keyboard`, `palette`, `image`, `ellipsis` added to `pb_import_kit/static/src/js/import_icons.js`. **Kit version NOT bumped** — deviation, see §6 / G5. |
| `ff11d2e6f` | `pb_orgchart` 19.0.1.0.0 — the module |
| `83c57dee3` | walk fixes 1 (looks): canvas fills the page, zoom label, row avatars, lane width/order |
| `195a07d59` | walk fixes 2 → 19.0.1.0.1: sideways layout, focus opens the lane, real photos only, 6× faster payload, fit on forests, list/side-panel "no manager" wording, local CSV date, test 14 |
| `d067f7d01` | perf: cards as components, hover painted without re-render, calm big draws |
| `3252b7485` | perf: card state in data attributes, `content-visibility` on card contents |
| `034579a8a` | a focus brings what it counts into view (lane order + fit to the lit cards) |
| `824a36c91` | pooled highlight lines; lane hint stays when nobody has a manager |
| (this commit) | this report, ledger G5–G13, `p1_shots/` |

Files (all new unless noted):

* `pb_orgchart/__manifest__.py` — depends `hr, mail, pb_import_kit, pb_hub, pb_people, pb_people_hub`; summary/description in plain English, no "Odoo".
* `pb_orgchart/models/pb_orgchart.py` — AbstractModel `pb.orgchart`: `get_chart()`, `get_branch(manager_id)`, helpers `_graph`, `_departments`, `_job_manager` (P2 adds `pb_manager_id` as its first branch), `_open_roles`, `_employee_data`, `_photo_ids`, `_rows`, `_team_count`, `_count_new`, `_may_write`, `_readable`.
* `pb_orgchart/static/src/js/orgchart_layout.js` — pure functions: `buildIndex`, `layout` (leaf stacks, forest, lane grid, sideways), `bounds`, `edges`/`edgePath`, `ancestors`, `descendants`, `directCount`, `totalCount`, `isUnloaded`, `colorOf`.
* `pb_orgchart/static/src/js/orgchart.js` — component `PbOrgChart`; also client action tag `pb_orgchart`.
* `pb_orgchart/static/src/js/orgchart_lens.js` — People lens `orgchart`, sequence 30, `EMPLOYEE_GATE` imported.
* `pb_orgchart/static/src/xml/orgchart.xml`, `static/src/scss/orgchart.scss`.
* `pb_orgchart/views/pb_orgchart_action.xml` — `pb_orgchart.action_pb_orgchart` ("Org chart", back door to People › Org chart). Not on the sidebar.
* `pb_orgchart/i18n/vi_VN.po` — 166 entries, every one with `#. module:`, its marker(s) and a `code:` occurrence (+ the action name as a `model:` occurrence). No `.pot` shipped.
* `pb_orgchart/security/README.md` — no models with records, no ACL.
* `pb_orgchart/tests/test_orgchart_p1.py` — 19 tests.

Rail icon: **`network`** (Lucide "network", a top-down org tree) instead of
`workflow`/`gitBranch`. Both of those read as process/version-control glyphs
on the rail; `network` is the shape of an org chart and matches the
Top-down view button. Screenshot: `p1_shots/T11_rize_standalone_first_draw.jpg`
(rail visible in the hub shots).

## 2. Tests

### Unit (cases 1–10 + extras)

Run on `p0clone` from a scratch addons dir listed first
(`--addons-path=/tmp/oc_test2/addons,/odoo/odoo-server/addons -u pb_orgchart
--test-enable --test-tags /pb_orgchart --stop-after-init --max-cron-threads=0
--http-port=8199 --gevent-port=8198`), log `/tmp/oc_test2/t2.log` on the box.
Result line: **`0 failed, 0 error(s) of 19 tests`**. (First run before the
first deploy, `-i`, 18 tests: `/tmp/oc_test/t1.log`, also 0/0.) Active
scheduled jobs on p0clone after the runs: 31 (unchanged).

| # | Case | Result |
|---|---|---|
| 1 | everyone active once, `manager_id` right, archived absent, `n_reports`/`n_total`, title/team/location fallback, initials | PASS |
| 2 | no manager → `manager_id False`, `counts.no_manager == 1` (the tree's top is not counted) | PASS |
| 3 | open job → `open_roles`, `manager_id` = department manager, `count == 2`; 3b a job whose department has no manager has `manager_id False` (the lane) | PASS |
| 4 | department colours stable across two calls, first ten distinct, payload colours = facade colours | PASS |
| 5 | `pb_orgchart_limit=3` → `truncated`, rows ≤ 3, all depth ≤ 2, counts over everyone, `get_branch(head)` = the head's staff + their open role; 5b limit 9 keeps exactly three levels; 5c `get_branch(0/'x')` empty | PASS |
| 6 | manager archived → root; 6b manager in another company (SQL) → root | PASS |
| 7 | first contract 10 days ago → `status 'new'`, `joined` ISO, 400 days ago → `''` | PASS |
| 8 | `is_absent` → `status 'leave'` + note. hr_holidays IS installed; the case patches `_search_absent_employee` (a validated leave needs type + allocation + calendar) — what it pins is how the chart reads `is_absent` | PASS |
| 9 | `me` = the user's employee; `False` for a user with none; 9b a cut chart keeps my chain | PASS |
| 10 | `may_write` true for an HR officer, false for a plain user | PASS |
| 11 | read RPCs post no message | PASS |
| 12 | one person raising inside the row builder → that person dropped, 8 drawn | PASS |
| 13 | a one-person company has no "no manager yet" lane | PASS |
| 14 | only a raster image counts as a photo; the generated SVG letter avatar does not | PASS |

### Browser (cases 11–25)

Signed-in sessions: rize as Ash Sohani (admin), payobook as Mitchell Admin
(demo admin, company Payobook Vietnam JSC). Evidence: `p1_shots/` and the
in-page measurements quoted (taken with page scripts in Chrome; nothing written).

| # | Case | Result | Evidence |
|---|---|---|---|
| 11 | Tab after Employees; draws < 2 s; subline = counts | **PASS rize** — rail EMPLOYEES · **ORG CHART** · CONTRACTS · RECORDS…; payload 0.48–0.71 s + render 65–128 ms; subline "241 people across 197 teams · 2 levels deep · 67 open roles · …", numbers 2.5 / 67 / 234 / 0 / 0 / 2 = server counts. **PARTIAL payobook** — counts match (4,547 · 35 teams · 3 levels · banner "Showing the top level of 4,547 people — open a team to load it"), but click → cards on screen is **2.2–2.9 s** (payload 0.5–1.2 s over the network for 657 people, then the browser mounting 667 cards; see §6) | `T11_rize_standalone_first_draw.jpg`, `T11_payobook_truncated_top_left_fit.jpg`, `T11_payobook_truncated_BEFORE_fit_fix.jpg` |
| 12 | Hover lights the chain; click opens the panel; chain button selects + centres | PASS — hover on Demo Tran Van Hung marks him + Demo Vo Thanh Son, 1 highlighted line; panel chain "Demo Vo Thanh Son › Demo Tran Van Hung"; the chain button selects Vo Thanh Son, panel switches, Team (4) lists 4 | `T12_rize_chain_highlight_side_panel.jpg` |
| 13 | +N opens a branch with motion; chevron folds | PASS — rize: chevron folds Vo Thanh Son's 4 (23 → 19 cards, toggle "+4"), +4 reopens; payobook (cut chart): "+15" on Đỗ Diễm Phương loads the team from the server (`get_branch`, 96 ms server) → 657 → 672 cards, toggle turns to a chevron. Motion: cards glide/settle on charts ≤ 150 cards; above that the chart appears without motion (deviation, §6) | measurements in this session |
| 14 | Each number focuses; hint clears | PASS — open roles lights 67 (lane opens), new this month lights 2 and the view fits to them, no manager yet lights 234; each "Show everyone" folds back to 23 cards. Zero numbers (wide teams 0, dotted lines 0) are inert (grey at zero). payobook: wide teams lights 56 | `T14_rize_new_this_month_focus_fits.jpg` (before the fix: `T14_rize_new_this_month_BEFORE_fit_fix.jpg`) |
| 15 | Search → suggestions; Enter jumps + panel | PASS — rize "agronom" → 8 suggestions, ↓↓ Enter → Demo Nguyen Thi Mai selected, centred, panel open; payobook "store manager" → 8, ↓ Enter → Đào Văn Nam | measurements |
| 16 | Team / Location / Employment filter, Colour by location, Levels 2, Clear (×) | PASS — Team "Product & Technology · 18" dims 21 of 23 cards, × clears (0 dimmed); Location and Employment filter and clear; Colour: location recolours avatars, legend "Bangalore, Rize Farms, Open role"; Colour: time with us recolours; Levels 2 sets the chip "2 levels" — **no visible change on rize/payobook because their trees are only 2 levels deep** (logic covered by layout code; noted) | measurements |
| 17 | Sideways, Teams, List, Compact; List fold toggles | PASS after fix — Sideways first overlapped (POC flaw, `T17_rize_sideways_BEFORE_fix_overlap.jpg`), fixed in 195a07d59: 0 overlapping cards (`T17_rize_sideways_fixed.jpg`); Teams 198 groups on rize / 45 on payobook, leads marked; List 308 rows, fold 308 → 304 → 308; Compact shrinks cards to 180 px | `T17_rize_teams.jpg`, `T17_rize_list_folds.jpg` |
| 18 | Zoom −/+, fit, wheel-pan, ⌘-wheel zoom, minimap click | PASS — 45 % → + 54 % → −− 38 % → fit 45 %; wheel pans; ⌘-wheel 45 → 50 %; minimap click moves the view; drag-pan moves | measurements |
| 19 | Keyboard | PASS — ↓ from Vo Thanh Son → Le Thi Hoa, → Pham Minh Quan, ← back, ↑ manager; Enter opens the panel; Space folds/unfolds (23 ↔ 19); + 108 %, − 90 %, F fits; / focuses search; Esc closes | measurements |
| 20 | Find me | PASS — rize: centres on Ash Sohani (lane) with the "You" ribbon, panel open; payobook: hidden (Mitchell Admin has no employee in the company) | `T20_rize_find_me_you_ribbon.jpg` |
| 21 | Open employee record: drawer; fallback | PASS — drawer (`employee_360`) opens on rize; with the registry entry removed **in the console of that tab** the fallback opens the `pb_employee_detail` page; entry restored | `T21_rize_open_record_drawer.jpg`, `T21_rize_open_record_fallback_action.jpg` |
| 22 | Spreadsheet; Print | PASS — `org-chart-2026-11-04.csv` (now named by the local date), 309 lines = header + 241 people + 67 open roles, columns Name, Title, Team, Reports to, Location, Employment, Joined, UTF-8 with BOM; Picture / PDF / Share rows present, disabled, "Coming soon". Print calls the print dialog and the print rules are loaded (2 `@media print` rules hide everything but the canvas); the print preview itself cannot be captured from here | measurements |
| 23 | Narrow window (1,150 px) | PASS (simulated) — the browser window cannot be resized from this session and the app refuses to be framed, so the chart page was narrowed to 1,030 px with the narrow-screen rules applied: side panel overlays the canvas (`position:absolute`), numbers fold to 3 columns, toolbar wraps over 2 rows with 0 overlaps, no sideways scroll | `T23_rize_narrow_simulated_1150.jpg` |
| 24 | Nobody managed → lane + empty-state copy | PASS — unit test 13 (one-person company) + a rehearsal in the browser: the loaded chart's managers were cleared **in memory only** (nothing saved) → "Nobody has a manager set yet" card over the lane, "Set managers on the employee records" + "Show the lane"; on real rize data the hint "234 people have no manager yet · Set managers on the employee records" opens People › Employees | `T24_rize_nobody_managed_rehearsal.jpg` |
| 25 | Console clean; no "Odoo" | PASS — no console errors on rize or payobook across the walk; "Odoo" scan over all chart text + tooltips + placeholders (incl. every menu, the panel, Teams and List): 0 hits in 86,690 + 40,574 characters | measurements |


## 3. Facts per database (2026-11-04, after fix 2)

Server build time measured in an `odoo-bin shell` as the admin (rolled back);
render time read from the page (`data-render-ms`: layout start → painted).

| | rize | payobook | p0clone | payobook_template |
|---|---|---|---|---|
| active employees (allowed companies) | 241 | 4,547 in the signed-in company (4,575 across all four) | 12 | 1 |
| with a manager | 5 | 3,918 (all four companies) | 1 | 0 |
| tops with a team / lone ("no manager yet") | 2 / 234 | 639 / 18 | 1 / 10 | — (one-person company: no lane) |
| open jobs (`no_of_recruitment > 0`) | 67 (65 in the lane: their teams have no manager) | 71 | 0 | 0 |
| depth | 2 levels | 5 levels across all companies, 3 in Payobook Vietnam JSC | 2 | 1 |
| payload sent | 241 people + 67 roles, 115 KB | **cut**: top level, 657 people + 61 roles, 286 KB | 12 | 1 |
| payload build (server) | 164 ms (was 256 ms) | 478 ms (was 3,029 ms) | 23 ms | 13 ms |
| `get_branch` | 30 ms | 96 ms (was 1,725 ms) | 13 ms | — |
| first draw (cards / script render) | 23 cards / 65 ms; lane opened 308 cards / 130 ms, on screen 0.5 s | 667 cards / 152 ms script; click → cards 2.2–2.9 s incl. network | — | — |
| hover (two frames) | 35–89 ms at 308 cards | 40–230 ms at 667 cards (was ~600 ms) | — | — |

## 4. `hr_org_chart` per database (informational)

Installed on all four (`payobook`, `payobook_template`, `p0clone`, `rize`).
`pb_orgchart` does not depend on it or read it.

## 5. Deploys

All with `/odoo/ops/filter_deploy.sh`, staged from committed HEAD (`git archive`),
staging dir cleaned first, START/DONE in `/opt/deploy-notes.md`. Before the
first deploy the live `pb_import_kit` tree hash equalled the previous commit
(`127a57ba6176`), so no foreign work was overwritten. `ListAgents` is not
available in this session; coordination was through the deploy notes (no open
START without a DONE) and the script's lock.

| Deploy | Commit | Modules → version | Window (UTC) | p0clone / template / rize / payobook | Jobs before/after | Evidence |
|---|---|---|---|---|---|---|
| A full | `b2df028cf` + `ff11d2e6f` | **pb_orgchart 19.0.1.0.0 installed** (`-i`); pb_import_kit files only (19.0.1.22.1 unchanged) | 12:49:05–12:51:11 | EXIT=0 errors=0 ×4 | 31/28/74/42 unchanged | `/tmp/orgchart-p1-run-20261104124904` |
| B looks | `83c57dee3` | pb_orgchart JS/SCSS/XML | 13:24 | OK, assets purged ×4 | — | `/tmp/orgchart-p1b-run-20261104132400` |
| C full | `195a07d59` | pb_orgchart 19.0.1.0.1 (`-u`) | 14:04:59–14:07:19 | EXIT=0 errors=0 ×4 | 31/28/74/42 unchanged | `/tmp/orgchart-p1c-run-20261104140457` |
| D looks | `d067f7d01` | pb_orgchart JS/SCSS/XML | 14:11 | OK ×4 | — | `/tmp/orgchart-p1d-run-20261104141125` |
| E looks | `3252b7485` | pb_orgchart JS/SCSS/XML | 14:44 | OK ×4 | — | `/tmp/orgchart-p1e-run-20261104144451` |
| F looks | `034579a8a` | pb_orgchart JS | 15:23 | OK ×4 | — | `/tmp/orgchart-p1f-run-20261104152323` |
| G looks | `824a36c91` | pb_orgchart JS | 15:26 | OK ×4 | — | `/tmp/orgchart-p1g-run-20261104152626` |

Script result `OK` every time (its stage-vs-server tree hash check included);
sites warm 200; `ir_module_module`: pb_orgchart **installed 19.0.1.0.1** on
all four, pb_import_kit 19.0.1.22.1 unchanged. Backups of the full runs in
`/odoo/backups/orgchart-p1-run-20261104124904` and `…p1c-run-20261104140457`.
p0clone got pb_orgchart one deploy early, from the first unit-test run (`-i`
from the scratch dir, same code); every deploy then used `+pb_orgchart` /
`pb_orgchart` so each database was installed or upgraded.

PO gate (`PoFileReader` on the staged `vi_VN.po`): 167 rows, 166 reaching a
screen, no error. The live web client serves 163 of them for `pb_orgchart`
in Vietnamese (`/web/webclient/translations?lang=vi_VN`); the other 3 are
server strings ("On leave today", "Last day …", "Open · N to fill"),
translated in the payload.

## 6. Self-score against the design bar, and deviations

Hero moment (cards settle in, the chain lights up, the numbers become
filters): delivered on readable charts; on a 650-card chart the settle is
switched off to stay responsive.

* **Name the hero moment** — the chain to the top lights on hover and the six numbers turn into filters that bring what they count into view; it works on both tenants.
* **Every state designed** — loading, error + Retry, empty roster, nobody managed, cut chart banner, huge (folds first), wide lane (+N more / Show fewer) are all drawn; the "huge" state is honest but not yet fast on payobook (2–3 s to first cards).
* **Plain language** — every label is a sentence a manager understands, in English and Vietnamese (166 strings), no "Odoo" anywhere on screen.
* **Motion with purpose** — glide and settle on charts up to 150 cards, edges fade in after the cards; bigger charts appear without motion because motion there cost two seconds of jank.
* **Keyboard + bulk ergonomics** — arrows, Enter, Space, /, F, E, C, +, −, Esc all work; there is nothing to bulk-edit in a read-only phase.
* **Best SaaS in the category** — on rize it matches the POC and the tools it was studied against (forest, lane, focus, minimap, four views); against the best on a 4,500-person flat demo world it is still slower than ChartHop-class tools, which virtualise.

Deviations from the handover / POC, and why:

1. **Kit version not bumped** (ledger said "kit version bump"): `-u pb_import_kit` cascades to every dependent module (G5). Files synced only, like 47fc57e56.
2. **Truncation rule**: "top three levels" does not bound a flat company (G7); the payload keeps three levels or fewer, plus the viewer's chain.
3. **Forest and lane** (G6): every root with a team is drawn as its own tree, trees wrap into rows; the lane is a grid that folds behind "+N more". The POC drew one tree and one lane row.
4. **"Leaving" reads `departure_date` only** — the contract end-date fallback would mark every fixed-term renewal as leaving (G9).
5. **Photos**: only real photos replace initials (G13); the generated letter avatars are ignored.
6. **"No manager yet" number counts people only**; open roles without a manager also sit in the lane but are counted under open roles.
7. **Big charts** (> 150 cards) appear without the entrance motion; cards are separate components; card state is a data attribute (G12).
8. **Rail icon** is `network` instead of `workflow`/`gitBranch` (§1).
9. **Zero numbers are inert** (the POC let you press a 0 and see nothing lit).
10. **Sideways** lays out with the card's footprint rotated; the POC overlapped cards.
11. **Spreadsheet** exports what is loaded: on a cut chart (payobook) that is the top level plus opened teams, not all 4,547 — the file says nothing about this yet (P4 item).
12. **Narrow-window and nobody-managed browser cases were simulated** (window not resizable here; no data changed), see §2.

## 7. Gotchas (appended to the ledger §3 as G5–G13)

G5 kit `-u` cascade · G6 real data is not one tree · G7 three levels do not bound a
flat company · G8 HR-only fields refuse the whole read · G9 contract end ≠ leaving ·
G10 CSS `content:` text cannot be translated · G11 `search_read` names every
many2one (450 ms on 4,500 parents) and version-held fields cost ~1.5 ms a person
through the employee · G12 on this app a class change re-checks the whole page's
styles (646 `:has()` rules): ~130–230 ms with a big chart, a data-attribute
change ~0.1 ms, a DOM insertion as bad as a class · G13 every employee has a
generated SVG avatar, so "has an image" is not "has a photo". Full text in
`ORGCHART_LEDGER.md` §3. Also seen (not ours): `pb_formula_studio` styles a bare
global `.pct` class (renamed ours `pboc-pct`).

## 8. Learn lessons / tours that mention People tabs (for P4)

* `pb_learn/static/content/learn_content.json` — "People › Employees" (7),
  "People › Contracts" (2), "People › Records" (4), "People › Pay" (9),
  "People › Plan" (5), "People › Joiners" (5), "People › Exits" (4),
  "People › Probation" (3).
* `pb_learn/static/src/engine/screens.js` (People › Employees / Pay / Records /
  Plan) and `pb_learn/static/src/engine/fixture.js` (People › Pay / Exits) —
  the practice replicas.
* `pb_learn/static/src/anchors.json` (People › Pay), `pb_learn/static/src/coach/coach.js`,
  `pb_learn/static/src/journey/library.js`, `pb_learn/models/learn_guide.py`
  reference `pb_people_hub`.
* The hub's lesson gate mirror (`people_hub.js:211-216`) spreads the lens
  registry, so the new tab needs nothing there.

## 9. Prepared for P2

* **No drag code was ported**: the POC's pointer-drag block is not trivially
  switch-off-able in OWL; P2 ports it (G2: pointer events + ghost card). The
  card component (`PbOcCard`) is the place for `pointerdown`; drop targets can
  use `data-id` (already on every card) and a `data-over` attribute (not a
  class — G12).
* **Hover quick actions**: the pill on each card holds one button (Open side
  panel); P2 adds Add team member / Change manager / More next to it.
* **Primary button slot** in the head is empty (comment marks it) for "Plan changes".
* **Server seams**: `_job_manager()` has the department-manager fallback only —
  P2 adds `hr.job.pb_manager_id` as its first branch; `dotted_id` is in every
  row (False) and the client already draws dotted edges, the dotted number and
  the "Also reports to" fact from it; `may_write` is in the payload
  (`_may_write()`: HR officer or system) for P2 to gate buttons and for every
  write RPC to re-check.
* **Side panel**: History tab not drawn; facts list is `sideFacts` (add rows there).
* **Refresh after a write**: `load()` rebuilds everything; for one change P2 can
  patch `this.nodes`, then `buildIndex` + `relayout()` (cards keep identity by
  signature, so only the moved cards re-render).
* **Known open items for later phases**: payobook-scale first draw (2–3 s; a
  virtualised canvas that renders only the cards in view would fix it — P4
  candidate); the CSV on a cut chart; Levels has no visible effect on the two
  live tenants (both 2 levels deep).
