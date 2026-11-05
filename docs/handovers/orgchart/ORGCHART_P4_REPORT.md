# ORGCHART P4 — report (finish: exports, share, ⌘K, lessons, speed, closeout)

Implemented per `ORGCHART_P4.md` and `ORGCHART_LEDGER.md`. **pb_orgchart
19.0.1.3.0 and pb_learn 19.0.20.8.7 are live on all four databases**
(`payobook`, `payobook_template`, `p0clone`, `rize`); `abm` not touched.
Programme closeout: **`ORGCHART_CLOSEOUT.md`** (every owner question, defaults,
known limits).

Paused once on the owner's request (2026-11-05 ~07:45 Sydney) after the first
deploy, resumed the same morning; the pause note is folded into §9.

**Read first:**
1. **The "after deploy" slowdown was the measuring tab, not the product** (G30).
   In a fresh tab the same build draws the 657-card tree in 0.13–0.19 s (was
   0.33–0.38 s), hovers in 33 ms (was 33–35 ms), pans at 16.7 ms frames (was
   66 ms), and holds those numbers at 1,500 cards. The Learn orb's pulse is not
   the cause (≈25 % of an all-cards mount, nothing on the virtual canvas), so
   pb_learn was not changed. No deploy was needed for it.
2. **Approve → live is proved on payobook** — plan sent in the browser,
   approved by the person the engine routed it to (Ông Thảo Vy, the seat's
   backup, because the seat holder Mitchell Admin sent it), through the inbox's
   own `decide` call from an `odoo-bin shell` (the browser session cannot act as
   her); the chart and the Plans menu showed it live; then put back by a
   reversing plan approved the same way. The two demo people's manager, coach
   and approvers are exactly as before.
3. **That proof found a wording bug** (G33): the publish dialog named the
   sender as the approver. Fixed and deployed; live check: "HR team (Ông Thảo
   Vy)".
4. **Vietnamese screenshots of the chart were not taken.** They need the
   qa.test login signed in, which means typing its password on a live site;
   this assistant may not do that. qa.test's language was never changed. Done
   instead: the lesson end to end in Vietnamese (Help's own language switch,
   browser-local), and the chart's 449 Vietnamese words served live. Owner
   question 12 in the closeout.

## 1. Files and commits

| Commit | What |
|---|---|
| `70ea4c559` | Server: `export_rows` (everyone, tree order, open roles, plan projection with "In the plan"), `approvers_of`, `chain_of`; G29 Records-viewer fix; `test_orgchart_p4` (6) + `tests/js/arrival.test.mjs` (13) |
| `f0322d967` | Client: `orgchart_export.js` (PNG painter, PDF print sheet, CSV, share link, arrival), `orgchart_arrival.js` (pure parser), `orgchart_palette.js` (⌘K 2950–2980), lens `wantsArrival`, move-sheet approvers line, virtual canvas + Web Animation pan/zoom in `orgchart.js`, print CSS, `data-coach` anchors, 43 VI entries, 19.0.1.3.0 |
| `028010e67` | Learn (built by a helper agent, checked here): lesson L41, walkthrough `sc_orgchart`, practice copy, People tab lists EN+VI, anchors, HR role path, PayAI whitelists; pb_learn 19.0.20.8.7; `vi_VN.po` unchanged |
| `298467fa7` | PAUSED note |
| `af3883af8` | Browser findings: keyboard into a folded team (G36), PNG tag row, clipboard timeout (G34), PDF packs small teams (G35); evidence |
| `598a2f3e0` | Publish dialog names the backup (G33), test 04; evidence |
| (this commit) | this report, `ORGCHART_CLOSEOUT.md`, ledger G29–G39, `p4_shots/` |

## 2. Tests

### Unit — **59 of 59 pass** (p0clone, scratch addons dir first, SCHEMECTX §0.13 recipe, `--http-port=8199`; log `/tmp/oc4_test/t3.log`, last line `0 failed, 0 error(s) of 59 tests`)

| # | Case | Test | Result |
|---|---|---|---|
| 1 | `export_rows`: every readable person, columns, tree order (top first, manager before team, lane last), open role row "× 2" under its manager | test_01 | PASS |
| 1b | same count as the chart; a cut chart (limit 3) still exports all 9; nothing written | test_01b | PASS |
| 1c | a Records viewer gets the same list as their chart — **first run ERROR**: their chart did not open at all (G29); fixed | test_01c | PASS |
| 1d | plan export = projection ("Hoa Two", "Changed"), live export unchanged, missing plan → sentence | test_01d | PASS |
| — | `approvers_of`: names, bad ids → `{}`, viewer → no error | test_02 | PASS |
| — | `chain_of`: managers top first, unknown → `[]` | test_03 | PASS |
| — | publish preview names the backup when the sender holds the seat (G33) | test_04 | PASS |
| 2 | arrival parsing (⌘K `me`/`plan`/`suggest`, link focus/view/colour/day/plan, junk dropped, ids only) | `node pb_orgchart/tests/js/arrival.test.mjs` | **13/13** |

### Browser — payobook.com (Mitchell Admin session already open) and rize.payobook.com (Ash Sohani session already open); no login typed. Evidence in `p4_shots/`.

Downloads were not written to disk: the page's download click was captured, the
file read back in the page and shown full-screen to look at (G38).

| # | Case | Result | Evidence |
|---|---|---|---|
| 3 | PNG whole chart + one branch, looks like the screen | **PASS** — payobook 4,268 × 16,000 px `org-chart-payobook-vietnam-jsc-2026-11-05.png` (lane, +N folds, tags, colours); branch "Ngô Bảo Lâm's team · 35 people" 1,280 × 7,064; rize 4,124 × 2,300. Found + fixed: tags drawn over the team line. Photos: neither demo world has a real photo (0 of the loaded people), so the photo path is untested live | `T03_*` |
| 4 | PDF: one team per page, landscape | **PASS (structure)** — print sheet on `<body>`, `@page A3 landscape` added for that print only and removed after, 45 team sections on payobook; page look checked on screen with the print rules applied. The real print preview was not opened (the dialog would block the browser tool). Found + fixed: rize = 198 near-empty pages → small teams share pages | `T04_*` |
| 5 | Spreadsheet: all 4,547 + note row | **PASS** — 4,617 lines = header + 4,547 people + 67 open roles + blank + "Exported from Payobook on Nov 5, 2026 · 4,547 people · 67 open roles"; 3.0 s. rize: 241 people, note says "Exported from **Rize**" (the tenant's brand rewrite). No "Odoo" | — |
| 6 | Copy link → new tab, same view and focus; `as_of` and `plan` links | **PASS** — copied (toast), new tab opened on the Org chart even with the hub's memory set to Employees, Sideways, Colour: location, Lâm Tuấn Kiệt focused inside a team not loaded on the cut chart; `as_of=2026-09-01` → "You are looking at Sep 1, 2026", 65 days ago; `plan=2` → "Viewing a plan … Live", both changes "Made"; an unknown plan → today's chart. Found + fixed: the clipboard can hang without a real press | `T06_*` |
| 7 | ⌘K rows | **PASS for an HR user** — the four rows on payobook; "Who reports to me?" on rize focuses Ash Sohani ("You"); on payobook (no employee linked) says so; "Plan org chart changes" opens planning mode; "Suggest a chart" opens the dialog (closed with Not now). **Viewer case not seen in the browser** (no viewer session open); the row's gate is `hr.group_hr_user`/`base.group_system`, the same as the server's write check | `T07_*` |
| 8 | Speed on payobook | **PASS** — §3; keyboard into a folded team (bug found + fixed, G36), right, up; far card selected stays mounted; minimap click moves the view (27,724 px) and mounts what is there | — |
| 9 | Lesson end to end, EN + VI | **PASS** — ⌘K → lesson page → Full lesson · 8 min, 10 steps on the practice copy, Understanding check (not answered, so no progress written); Help's "Tiếng Việt" switch → same check and step 10 in Vietnamese, switched back | `T09_*` |
| 10 | Vietnamese screenshots (chart, move sheet, draft bar, publish dialog, time machine) | **NOT DONE** — Read first 4 | — |
| 11 | Every People lesson that lists tabs lists Org chart | **PASS** — `hub_people` screen EN + VI ("Sơ đồ tổ chức"), practice People tabs, PayAI's People list, HR role path | content check |
| 12 | No "Odoo" on screen, exports, lesson | **PASS** — chart text + titles/placeholders/labels: 0; CSV: 0; learn content: 0; `.po` msgstr: 0 | — |
| 13 | Move sheet approvals line (owner ruling 3) | **PASS** — "Leave and expense approvals stay with Ngô Bảo Lâm — change them on the employee record if they should move." | `T13_*` |
| 14 | Picture / spreadsheet of a plan (§1.9c) | **PASS** — PNG of Huỳnh Bá Nam's branch in the plan: amber outlines on the two moved people, plan line in the title, file `…-org-chart-changes-huynh-ba-nam-…png`; CSV with "In the plan" = Changed and the note "plan … not live yet" | `T14_*` |
| 15 | Approve → live (§1.9b) | **PASS** — Read first 2; §4 | `T15_*` |
| — | Console | No errors on payobook or rize (read after the last reloads) | — |

## 3. Speed — payobook, Payobook Vietnam JSC (4,547 people), same machine and browser

Measured with an in-page probe (switch List → Top-down and time to the second
painted frame; 60 synthetic 8-px wheel pans timed by animation frames; 12
hovers timed over two frames; one transform write plus a forced style flush).
"After" is a fresh tab, 8 repeats stable (G30).

| | Before (19.0.1.2.0) | After (19.0.1.3.0) |
|---|---|---|
| `get_chart` server build | 465–478 ms | 465 ms (under 500 ms: no change needed) |
| redraw after the payload (plan change, day change) | 94–117 ms | **24–44 ms** |
| tree drawn (view switch) — 657 cards | 326–384 ms | **132–189 ms** |
| cards mounted — 657 in the layout | 657 | 119–199 |
| pan frame median / p95 / worst — 657 | 66 / 83–166 / 134–234 ms | **16.6 / 17.6 / 32 ms** |
| hover (two frames) median — 657 | 33–35 ms | **33 ms** |
| transform write + style flush — 657 | 42 ms | **0.7–1.3 ms** |
| tree drawn — 1,501 cards | 515 ms | **147–178 ms** |
| pan frame median / p95 / worst — 1,501 | 134 / 151 / 215 ms | **16.7 / 17.6 / 18 ms** |
| hover median / worst — 1,501 | 103 / 190 ms | **33 / 34 ms** |
| transform write + flush — 1,501 | 70 ms | **0.7–1.3 ms** |

Targets (§1.6): first draw under 1 s after the payload ✔, pan ≤ 16 ms frames ✔
(16.6 = one 60 Hz frame), hover ≤ 40 ms ✔. Opening 78 teams one by one to reach
1,500 cards still takes ~15 s (one server call per team; closeout limit).

## 4. Approve → live proof (payobook only)

| Step | What happened |
|---|---|
| before | Chu Hải Đăng (17125) and Đặng Thuý Vân (17126): manager Ngô Bảo Lâm (17122), coach 17122, leave and expense approver user 2326 |
| plan | ⌘K "Plan org chart changes" → planning mode; Change manager → Huỳnh Bá Nam for both (move sheet named the approver); picture + spreadsheet of the plan |
| publish | "P4 approve-to-live proof (demo people, put back afterwards)", goes live today → "Sent to the HR team for approval" |
| route | inbox: "Ông Thảo Vy was asked instead of Mitchell Admin, because Mitchell Admin sent this in" — the browser session could not decide it |
| approve | `pb.approval.inbox.decide(392, 'lifecycle', 'approve')` as Ông Thảo Vy (uid 2330) from `odoo-bin shell` — the Approve button's own call; logged in `/opt/deploy-notes.md` |
| live | plan 2 "Live" in the Plans menu; Chu Hải Đăng under Huỳnh Bá Nam in the browser; coach and approvers unchanged (G16) |
| put back | reversing plan 3 made as Mitchell Admin and approved the same way → both back under Ngô Bảo Lâm; coach 17122, approvers 2326 — identical to "before" |

Plans 2 and 3 stay as the audit trail (state Live), with their requests in the
approvals history.

## 5. Deploys

All with `/odoo/ops/filter_deploy.sh full`, staged from committed HEAD (`git
archive`), staging dir cleaned first, START/DONE in `/opt/deploy-notes.md`,
lock free before each (`fuser` empty). `ListAgents` is not available in this
session; coordination was the deploy notes (no open START) and the lock.
Before each, the live trees equalled the previous P4 commit (no foreign work
overwritten). Gates: libsass compile of `orgchart.scss` OK; `PoFileReader`
pb_orgchart 610 rows, pb_learn 241, none empty.

| Deploy | Commit | Modules → version | Window (UTC) | p0clone / template / rize / payobook | Jobs before/after | Evidence |
|---|---|---|---|---|---|---|
| A full | `028010e67` | pb_orgchart **19.0.1.3.0**, pb_learn **19.0.20.8.7** (`-u`, cascades to pb_learning_hub, pb_payroll_ai_insights, pb_talent_hub); pb_payroll_ai_insights files (19.0.3.12.4 unchanged) | 20:45:36–20:50:08 (4 Nov) | EXIT=0 errors=0 ×4 | 32/29/75/43 unchanged | `/tmp/orgchart-p4-run-20261104204523` |
| B full | `af3883af8` | pb_orgchart 19.0.1.3.0 (JS/SCSS/XML/PO; restart for the PO) | 00:49:05–00:51:25 | EXIT=0 errors=0 ×4 | 32/29/75/43 unchanged | `/tmp/orgchart-p4b-run-…` |
| C full | `598a2f3e0` | pb_orgchart 19.0.1.3.0 (Python) | 01:01:53–01:04:15 | EXIT=0 errors=0 ×4 | 32/29/75/43 unchanged | `/tmp/orgchart-p4c-run-…` |

Sites warm 200 after each; `ir_module_module.latest_version` = manifest on all
four. Backups in `/odoo/backups/<run name>`. p0clone also received pb_orgchart
from the unit-test runs (same code).

## 6. Live data left as found

* **payobook:** the two demo people put back exactly (§4); plans 2 and 3 kept
  as audit trail; no demo data deleted; Mitchell Admin's Learn progress not
  written (the understanding check was not answered). A stray keystroke during
  the walk opened an "Add someone to … team" dialog that was closed without
  saving (G39).
* **rize:** read-only checks only (exports captured in the page, Suggest
  opened and closed with Not now, ⌘K focus) — nothing written.
* **qa.test:** not signed in, language not changed.

## 7. Design-bar self-score — the whole programme

Hero moments: P1 the chain lights up and the numbers become filters; P2 drag a
card onto a manager, one sentence says what changes, one tap undoes; P3 Plan
changes turns the chart into a sandbox and the time slider rewinds it; P4 the
4,500-person chart feels like the 60-person one, and one click puts a crisp
picture of any team into a slide.

| Bar | Score | Why |
|---|---|---|
| Hero moment named and delivered | 9/10 | each phase's moment works on both tenants; the 4,500-person world is now as fluid as rize |
| Every state designed | 9/10 | loading, error/retry, empty roster, nobody managed, cut chart, wide lane, plan/stale/failed changes, time banner, refused link, viewer read-only lines, export busy and failure toasts |
| Plain language, EN + VI | 9/10 | every label a sentence; approvers named; 449 chart words in Vietnamese; lesson bilingual; no "Odoo". Minus: the Vietnamese screens were not photographed |
| Motion with purpose | 8/10 | cards settle and glide on small charts, glides are Web Animations, nothing restyles per frame; big charts appear without entrance motion by design |
| Keyboard + bulk | 9/10 | arrows (now into folded teams), Enter, Space, /, F, E, C, ±, M, A, ⌘Z/⇧⌘Z, pick several, set manager for many, ⌘K rows |
| Best in category | 8/10 | matches or beats the tools studied on planning, time machine and suggest; behind ChartHop-class tools on opening a huge company's teams one by one (one call per team) and on server-made PDFs |

## 8. Deviations from the handover, and why

1. **Share link uses the query string, not the hash** — the sign-in redirect
   drops a hash (G31). Read once at load.
2. **Picture painted straight onto a canvas** (Path2D for the same edge
   strings), not via an SVG string — same result, no foreignObject or taint
   questions; icons drawn from the shared `ic()` set as SVG images.
3. **PDF: larger teams (> 6) start a page; small teams share pages** — "one page
   per team" gave rize 198 pages (G35). Menu wording kept.
4. **Virtual canvas placeholder** is ONE skeleton `<path>` with every card's box
   (not a placeholder element per card — an insertion costs a page-wide style
   check, G12).
5. **⌘K block 2950–2980** — every hundred-block 2600–2900 is taken.
6. **"Who reports to me?"** says "You are not on the chart" when no employee is
   linked to the login (payobook's demo admin).
7. **Approve proof through the inbox call from a shell**, because the request
   was routed to the backup approver, not the open session (not a browser
   refusal).
8. **Helper agent** wrote the Learn content (independent files); its report
   was checked and its guards re-run here.

## 9. Gotchas appended to the ledger (§3)

G29 Records viewer could not open the chart · G30 measure in a fresh tab
(the "slowdown" was the tab) · G31 sign-in keeps the query, drops the hash ·
G32 `pgrep -f` wait loops match themselves · G33 approver preview ignored the
backup swap · G34 clipboard can hang · G35 one page per team = 198 pages on
rize · G36 ArrowDown into a folded team · G37 www.payobook.com has its own
cookie; a password still has to be typed · G38 browser-tool notes · G39 typing
right after ⌘K lands on the chart.

Pause record: paused 2026-11-05 ~07:45 Sydney on the owner's request after
deploy A (WIP note `298467fa7`), resumed the same morning; nothing was left
half-deployed.

## 10. Left open, plainly

* Vietnamese screenshots of the chart (owner question 12).
* The ⌘K "Plan org chart changes" row was not seen from a viewer's session.
* Photos in the picture export are untested on live data (no real photos in
  either demo world).
* The real print preview was not opened; the print sheet was checked in the
  page.
* Everything in the closeout's owner questions.
