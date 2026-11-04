# ORGCHART P4 — report

## PAUSED HERE (2026-11-05, owner asked to pause)

**Done**
* Code, committed and pushed on 19.1: `70ea4c559` (server: `export_rows`,
  `approvers_of`, `chain_of`; G29 fix — a Records viewer who is not an HR
  officer could not open the chart at all), `f0322d967` (client: Picture
  PNG + "Export this branch as a picture", PDF one page per team, full
  spreadsheet with note row, "Copy a link to this view", 4 ⌘K rows at
  2950–2980, move sheet names who keeps approving leave/expenses, Web
  Animation pan/zoom, virtual canvas above 150 cards, 43 Vietnamese entries,
  `data-coach` anchors), `028010e67` (Learn: lesson L41 "The org chart: find,
  move, plan", walkthrough `sc_orgchart`, practice copy, People tab lists,
  PayAI whitelists; pb_learn vi_VN.po unchanged).
* Unit tests on p0clone: **0 failed, 0 errors of 58** (6 new). Node test
  `pb_orgchart/tests/js/arrival.test.mjs`: 13/13. Learn guards: gen --check OK,
  check_contract 1 pre-existing failure (pe-filters), node suites green.
* **Deployed `full` to all four DBs** (run `/tmp/orgchart-p4-run-20261104204523`,
  20:45:36–20:50:08 UTC): EXIT=0 errors=0 ×4; pb_orgchart 19.0.1.3.0,
  pb_learn 19.0.20.8.7, pb_payroll_ai_insights files (19.0.3.12.4 unchanged);
  crons 32/29/75/43 unchanged; tree hashes OK; START/DONE in deploy notes.
  Gates: libsass OK, PO 610/241 rows none empty; live trees equalled the
  pre-P4 commit before the sync. `get_chart` build on payobook 465 ms (under
  500 ms, no fix needed).
* Browser (payobook.com, Mitchell Admin session already open): the chart loads
  on 19.0.1.3.0. Speed so far (657 cards):

  | | before (19.0.1.2.0) | after (19.0.1.3.0) |
  |---|---|---|
  | pan frame, median | 66 ms | **16.9 ms** |
  | transform write + style flush | 42 ms | 3–21 ms |
  | cards mounted | 657 | 119–189 |
  | tree mount → paint | 326–384 ms | 600–950 ms (see below) |
  | hover, two frames, median | 33–35 ms | 42–116 ms (see below) |
  | 1,501 cards: pan median / hover | 134 / 103 ms | not measured yet |

  **Open finding:** after the deploy the WHOLE page got slower — mounting all
  657 cards (virtual switched off on the instance) now takes 3.4–4.4 s in the
  same session where it took ~0.35 s before. Suspect: Learn's helper orb now
  runs a never-ending `lrn-breathe` CSS animation on the Org chart page (the new
  "First time on Org chart?" card), so every frame restyles a page with 646
  `:has()` rules. Not yet proven.

**Not done**
* Find and fix the slowdown above; then re-measure (657 and ~1,500 cards).
* Browser cases 3–12 (PNG files, PDF preview, spreadsheet 4,547 + note, copy
  link → new tab, ⌘K rows HR vs viewer, keyboard/minimap on the big world,
  lesson EN+VI, Vietnamese screenshots, no "Odoo") on payobook and rize;
  console read; `p4_shots/`.
* §1.9b Approve → live proof on payobook (nothing has been planned or sent).
* Vietnamese screenshots as qa.test (plan: sign in at www.payobook.com — the
  same payobook database with its own cookie, so Mitchell's session at
  payobook.com is untouched). **qa.test's language was NOT changed.**
* ORGCHART_CLOSEOUT.md, the rest of this report (§7 items), ledger G29–G33.

**Live data:** nothing changed on rize or payobook by P4 — no move, plan,
approval or language switch was made; browser experiments were client-only
(opened teams on screen, an instance getter patched and removed).

**Exact next step:** on payobook.com, Org chart, check whether the Learn orb's
`lrn-breathe` animation is running (`document.getAnimations()`), pause it in
the page and re-run the mount/hover probe (`oc_measure` method in this report's
numbers: List → Top-down, LoAF entries). If it is the cause, make the orb stop
breathing (pb_learn) or end the first-time nudge after one view; then re-measure
and continue with the browser cases.

Gotchas found so far (to append to the ledger): G29 Records viewer could not
open the chart (fixed); G30 www.payobook.com serves the payobook DB with its
own cookie (dbfilter `^%d$` drops `www`) — a second signed-in user without
signing anyone out; G31 the sign-in redirect keeps the query and drops the
hash (checked with curl), so the share link uses the query, read once at load;
G32 a wait loop `until ! pgrep -f "<pattern>"` matches its own command line and
never ends; G33 the chrome-devtools MCP browser was held by another session —
this phase used the Chrome extension.
