# ORGCHART P4 — finish: exports, share, ⌘K, lessons, speed, closeout

Read `ORGCHART_LEDGER.md` (all of it, including every gotcha P1–P3 appended
and the owner rulings), then `ORGCHART_P3_REPORT.md` (what shipped, §8 open
items, the running list of owner questions). This phase closes the
programme: the remaining POC features, the speed work the big demo world
needs, the lesson, Vietnamese completeness, and the closeout document.

## 1. Scope

In `pb_orgchart` (bump to `19.0.1.3.0`), plus `pb_learn` content:

1. **Picture export (PNG)** — client-side, no new library: serialise the
   visible chart (cards + edges, current fold state, current colour-by) to
   an SVG string, draw it on a canvas at 2× and download
   `org-chart-<company>-<date>.png`. Photos are `/web/image` URLs on the same
   origin, so they draw cleanly; fall back to initials if an image fails to
   load within 2 s. The POC's export menu wording. Context-menu row "Export
   this branch as a picture" exports only that person's subtree.
2. **PDF** — "PDF · one page per team": open the print view with the POC
   print CSS and a page-break per top-level team (`break-after: page` on the
   team block in the List/Teams view), landscape A3, and call
   `window.print()`; the menu row says "opens your print dialog — choose
   Save as PDF". (A server-side PDF is a closeout candidate; say so in the
   menu's small text? No — keep the menu clean; put it in the closeout.)
3. **Spreadsheet on a cut chart** (P1 deviation 11): the export asks the
   server for the FULL list (`export_rows()` RPC: one `search_read` over
   everyone the user may read, same columns) rather than what is loaded;
   the file's last row is a note "Exported from Payobook on <date> ·
   <n> people". In plan mode it exports the projection (`plan_id`).
4. **Share** — "Copy a link to this view": a deep link to the hub lens with
   the current state in the URL hash (`lens=orgchart&focus=<emp>&view=
   tree&color=dept&as_of=…&plan=…`), read on arrival (the lens declares
   `wantsArrival`; see `pb_workseg` for the pattern). Login required (ledger
   D9). Copy to clipboard + toast "Link copied. Anyone in the company who can
   see the chart can open it."
5. **⌘K rows** in `registry.category("pb_hub_palette")` (next free 2xxx block
   ≥ 2600 after grepping every `*_palette.js`): "Org chart" (People),
   "Who reports to <me>?" (opens focused on the user's employee), "Plan org
   chart changes" (opens in plan mode; HR users only), "Suggest a chart".
   Gate = `EMPLOYEE_GATE`; `requires: "pb_orgchart"`.
6. **Speed on the big demo world** (G12, G15; P1/P2 open items):
   * Pan/zoom move the world by a paused Web Animation whose keyframes are
     rewritten (P2's ghost trick), not an inline transform.
   * **Virtualise the canvas**: only cards whose box intersects the viewport
     (plus a 400 px margin) are mounted; others are a lightweight placeholder
     (no children) so edges and the minimap still know their position.
     Re-evaluate on pan/zoom end (not per frame). Target on payobook (667
     cards, all teams opened to ~1,500): first draw under 1 s after payload,
     pan frames ≤ 16 ms, hover ≤ 40 ms. Report before/after numbers.
   * `get_chart` on payobook: report build time; if over 500 ms, profile and
     fix the top item only.
7. **Lesson + tours** (ledger §0.10; P1 report §8 lists every Learn file
   that names People tabs): add a "People › Org chart" lesson to
   `pb_learn/static/content/learn_content.json` (clone the shape of the
   Employees lesson; steps: find someone, read the chain, fold and open
   teams, pick several people and set a manager, undo, plan changes and
   send them, rewind the time machine), the practice replica in
   `pb_learn/static/src/engine/screens.js` if the other People tabs have
   one (clone Employees'), the anchors file if used, and update any lesson
   that lists the People tabs so the list now includes Org chart. Keep the
   `vi_VN.po` of `pb_learn` in step (ledger §0.8; memory "LEARN v3": the
   generator wipes `pb_learn` `vi_VN.po` — restore it if that happens).
8. **Vietnamese completeness**: diff every `_t()`/`_()` string in
   `pb_orgchart` against `vi_VN.po`; add what is missing; run the PO gate.
   Take the Vietnamese screenshots the owner allowed — **the owner answered
   Fable's question card directly on 2026-11-05: "Yes, on payobook demo
   only", recorded in the ledger's owner rulings; this is first-hand, not
   relayed** — switch `qa.test@payobook.com` on payobook.com to Vietnamese,
   photograph the chart, a move sheet, the draft bar, the publish dialog and
   the time machine, switch it back (say so).
9. **Approvals ruling** (owner, 2026-11-05): a move changes the manager
   only; leave and expense approvals stay. Make sure the move sheet's "What
   changes" text says "Leave and expense approvals stay with <current
   approver> — change them on the employee record if they should move"
   (one sentence), in both languages. Remove any text that still promises
   approvals move.
9b. **Prove Approve → live, in the browser, on payobook only** (P3 could
    not click Approve: the browser tool refused the click). On payobook.com,
    in a demo company that HAS the `orgplan` route (P3 report names which),
    make a two-change plan on demo people, publish it, then approve it as a
    user who holds the HR lifecycle seat (the signed-in admin session if
    there is one). If the browser tool refuses the Approve click again, do
    NOT work around the refusal in the browser: run the engine's own approve
    method from an `odoo-bin shell` as that approver user, then show in the
    browser that the chart changed and the plan reads "Applied". Afterwards
    put the two demo people back (a reversing plan approved the same way, or
    P2's undo), and say so. Never on rize.
9c. **Picture / PDF of a plan**: the exports in §1.1–1.2 work in plan mode
    on the projection (amber outlines and ghost lines included in the PNG;
    the file name carries the plan name).
10. **Closeout document** `ORGCHART_CLOSEOUT.md`: what shipped per phase with
    module versions, what is live where, every owner question collected
    across P1–P4 as plain questions with the default taken (pay on the
    chart; public share link; scenario compare; archived people in the past
    view; server-side PDF; hr_org_chart stock widget — keep or hide; the
    deploy-script lock fix for the ops owner; from P3: should rize fill in
    team managers on its team records so Suggest can place more than 1 of
    236 people; "SG Company" on payobook has nobody in the HR lifecycle seat
    so no plan — or contract extension — can be sent there; the
    withdrawn-request bug P3 fixed for plans probably affects other approval
    types — for whoever owns approvals; the approvers of a plan are the HR
    lifecycle team because the engine has no separate people team), and the
    known limits (the 4,500-person demo numbers).
11. **Tests** (§5) and the **report** (§7).

### Non-goals (binding)
* No public (no-login) share page. No server-side PDF. No scenario
  comparison. No change to the approval engine. No new fields.

## 2. Plumbing — verified, do not re-derive
* Ledger §1 "The People hub and its lenses" (deep links, palette rows,
  `wantsArrival`), `pb_workseg/static/src/js/workseg_lens.js:41-45` and its
  component for reading `props.arrival`.
* P1 report §8 — the Learn files; `pb_learn/static/content/learn_content.json`
  is the lesson store.
* G12/G15 — the measurement method (`data-render-ms`,
  `data-drag-worst-ms`, `odoo.__WOWL_DEBUG__` walk) and the Web Animation
  trick.
* P1's CSV export code (client-side) — reuse the column list for
  `export_rows()`.

## 3. Design to build
Hero moment: **the 4,500-person chart feels like the 60-person one** —
instant pan, instant hover — and one tap puts a crisp picture of any team
in a slide deck.

## 4. Safety rails
* Export reads only what the user may read (`export_rows()` runs the same
  `search` the chart does; no `sudo()` for employees).
* The share link carries ids, never names; an id the viewer may not see
  simply does not focus.
* Virtualisation must not change layout, selection, keyboard travel or the
  minimap; the test cases below re-run P1's keyboard case on the big world.
* Lesson content must match the live screen's words (lessons-follow-screen
  rule).

## 5. Test cases
Unit: 1. `export_rows()` returns every readable person with the columns, in
plan mode the projection; a plain user gets the same list as the chart shows
them. 2. Arrival payload parsing (focus/view/color/as_of/plan) — pure
function test in JS if the project has a JS test runner (grep `tests/` in
`pb_hub`); else a documented manual check.
Browser (payobook + rize; console clean; `p4_shots/`): 3. PNG export of the
whole chart and of one branch — open the files, they look like the screen
(photos included). 4. PDF print preview shows one team per page, landscape.
5. Spreadsheet on payobook has all 4,547 people and the note row. 6. Copy
link → open in a new tab → same view, same focus; a link with `as_of` and
with `plan` resume those modes. 7. ⌘K: the four rows appear for an HR user;
"Plan org chart changes" is absent for a viewer. 8. Speed on payobook: the
numbers in §1.6 (before/after), hover, pan, keyboard travel across a folded
team, minimap click. 9. Lesson: open Learn, run the Org chart lesson end to
end on the practice replica (or the live screen if that is how People
lessons run), in English and Vietnamese. 10. Vietnamese screenshots of the
four screens in §1.8, then the login switched back. 11. Every People lesson
that lists tabs now lists Org chart. 12. No "Odoo" on screen, in exports,
or in the lesson.

## 6. Deploy / verify
Ledger §0.4 (+ §0.11 SCSS gate, §0.13 lock). `full` for pb_orgchart and
pb_learn; PO gate on both; browser cases.

## 7. Report back — `ORGCHART_P4_REPORT.md`
Files/commits; each test with evidence; speed before/after table; the
closeout document path; design-bar self-score for the whole programme;
gotchas appended; anything left open, stated plainly.
