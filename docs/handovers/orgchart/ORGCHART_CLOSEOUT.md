# ORG CHART — closeout (programme complete, 2026-11-05)

The owner asked (2026-11-04) for a world-class organisation chart as a tab in
People. It shipped in four phases as one module, `pb_orgchart`, plus a Learn
lesson. Everything below is live on the four databases (`payobook`,
`payobook_template`, `p0clone`, `rize`); `abm` was never touched.

## 1. What shipped, phase by phase

| Phase | What it gave people | Version | Report |
|---|---|---|---|
| P1 | **The chart, read-only.** People › Org chart after Employees; top-down, sideways, Teams and List views; folds with +N; search and jump; Find me; six numbers that focus the chart; team / location / employment filters; colour by team, location, employment or time with us; pan, zoom, fit, minimap; side panel with the chain of managers, team and peers; keyboard; spreadsheet; print. Big companies load the top level first and open teams on demand. | 19.0.1.0.x | `ORGCHART_P1_REPORT.md` |
| P2 | **Changing it live.** Drag someone onto a new manager (whole team or only them); pick several and set one manager; dotted-line manager (new field "Also reports to"); add a team member (someone here, a new open role, a new starter form pre-filled); fill / move / close an open role; swap places; remove from a team; one-tap Undo; History tab on each person. A move changes the manager only — coach and leave / expense approvers keep their value. | 19.0.1.1.0 | `ORGCHART_P2_REPORT.md` |
| P3 | **Planning, time machine, suggest.** Plan changes on a copy of the chart (amber outlines, dashed "came from" lines, undo/redo), publish to the HR team through the approval engine, made live on the chosen day; time machine a year back and 90 days ahead; Suggest a chart from team records for a company with few managers set. | 19.0.1.2.0 | `ORGCHART_P3_REPORT.md` |
| P4 | **Finish.** Picture (PNG) of the chart or one branch; PDF print view with a page per larger team; spreadsheet of everyone (not only what is loaded); Copy a link to this view (opens the same view, person, day or plan after sign-in); four ⌘K rows; move sheet names who keeps approving leave and expenses; virtual canvas + smooth pan for the 4,500-person demo world; the Learn lesson in English and Vietnamese; two older bugs fixed (Records viewers could not open the chart; keyboard into a folded team). | **19.0.1.3.0** (+ pb_learn 19.0.20.8.7) | `ORGCHART_P4_REPORT.md` |

Ledger of rules and the 39 gotchas met on the way: `ORGCHART_LEDGER.md`.

## 2. Live where

| Database | pb_orgchart | pb_learn | Approval route for plans |
|---|---|---|---|
| payobook | 19.0.1.3.0 | 19.0.20.8.7 | 4 companies; **SG Company has none** (nobody holds the HR team seat) |
| payobook_template | 19.0.1.3.0 | 19.0.20.8.7 | My Company |
| p0clone | 19.0.1.3.0 | 19.0.20.8.7 | My Company |
| rize | 19.0.1.3.0 | 19.0.20.8.7 | Rize Farms (independence off, owner ruling 2026-09-18) |

The scheduled job "Org chart: make approved plans live" is on in all four.

## 3. Questions for the owner (the default is what the product does today)

1. **Pay on the chart.** Should managers see a pay band on people's cards?
   *Default: no pay anywhere on the chart.*
2. **A link that works without signing in.** Should "Copy a link" be able to
   make a read-only page anyone can open (for a board pack, say)? That needs a
   privacy decision. *Default: every link needs a Payobook sign-in.*
3. **Comparing two plans side by side.** Wanted? *Default: one plan at a time.*
4. **People who have left, in the past view.** When you rewind the chart,
   should people who have since left come back on it? *Default: they are not
   shown (the banner says so).*
5. **A PDF made by the server** instead of the print dialog's "Save as PDF"?
   *Default: the print dialog (one click more, no new server part).*
6. **The PDF of a very big company.** On payobook the screen first loads the
   top level only, and the PDF prints what is loaded (45 teams of the top
   level). Should the PDF print everyone, like the spreadsheet does?
   *Default: it prints what is on screen; open teams first for more.*
7. **The older built-in org chart** on the employee form (the stock widget):
   keep it or hide it now that People › Org chart exists? *Default: kept.*
8. **rize team managers.** Suggest a chart can place only 1 of 236 people on
   rize because its team records have no managers. Should rize fill in a
   manager on each team record (then Suggest does most of the work), or set
   managers by hand? *Default: nothing changed on rize.*
9. **SG Company on payobook** has nobody in the HR team seat, so no plan (and
   no contract extension) can be sent for approval there. Fill the seat, or
   leave the demo company as it is? *Default: left as it is.*
10. **Who approves plans.** Plans go to the HR lifecycle team (the people who
    approve contract extensions), because the approval setup has no separate
    "people team". Is that right? *Default: the HR lifecycle team.*
11. **When the person sending a plan holds that seat**, the request goes to the
    seat's backup (on payobook, Ông Thảo Vy) and the publish dialog now says so.
    Is that the behaviour you want? *Default: yes — it is the approval engine's
    independence rule.*
12. **Vietnamese screenshots.** You allowed them with the qa.test login on
    payobook. Signing that login in needs its password typed, which this
    assistant may not do on a live site. Would you sign qa.test in yourself
    (at www.payobook.com, which keeps your own session at payobook.com
    untouched), or accept the Vietnamese checks that were done instead (the
    lesson read in Vietnamese with Help's own language switch; 449 chart words
    served in Vietnamese)? *Default: the screenshots were not taken; nobody's
    language was changed.*
13. **For whoever looks after approvals:** a request withdrawn from the inbox
    left the record "waiting" for ever; fixed for org chart plans in P3, and
    other request types very likely have the same gap. *Default: fixed for
    plans only.*
14. **For whoever looks after the server:** the deploy script's lock is kept by
    the server it restarts, so the next deploy can wait 10 minutes (one-line
    fix in the script: start the server without the lock). *Default:
    unchanged; every deploy checks the lock first.*

Settled during the programme (not to be re-asked): the POC is the spec; a move
changes the manager only; Vietnamese screenshots only on payobook with
qa.test; the spreadsheet exports everyone (P4).

## 4. Known limits

* **The 4,547-person demo world (payobook)** is 657 small teams with nobody
  above them. The chart first loads the top level (657 people + open roles,
  payload built in ~0.47 s); each "+N" loads one team. Opening 78 teams one
  after another (to ~1,500 cards) took 15 s. With the virtual canvas only the
  ~120–190 cards near the screen are drawn: tree drawn in 0.13–0.19 s, pan at
  60 frames a second, hover 33 ms — also at 1,500 cards.
* **Spreadsheet** of all 4,547 people: about 3 s.
* **Picture** of the whole payobook chart is 4,268 × 16,000 px (the browser's
  limit), so it is drawn at 1.4× instead of 2×; a much wider chart would drop
  below print quality and the toast says to export one team instead. Photos
  are drawn when people have real photos (the demo worlds have none).
* **PDF** goes through the print dialog ("Save as PDF"); larger teams start a
  new page, small teams share pages (rize: 197 teams for 241 people).
* **Time machine** history starts when manager changes started being recorded
  (payobook: 31 Aug 2026).
* A shared link that names a plan the reader may not open shows today's chart
  with a short warning.
