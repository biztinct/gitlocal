# FILTER wave 3 — report (Hiring: Roles, Interviews, Applicants, Offers)

Branch `worktree-agent-a4a00437ba90ee2d8`, rebased on `19.1` @ `15049168f`
(kit 1.2.0, W1 + W4 merged). Builder: Opus. Tested on the shared preview
(`pbf_preview`, a copy of payobook). Nothing touched the live addons, the live
databases or `/opt/deploy-notes.md`.

**Summary: all four Hiring lists are on the shared filter panel and pass
T1–T22 and W3-T1…T4 on the preview.** Testing found one real defect (a press
during a list switch landed on the wrong list) — fixed and retested.

| Screen | Result |
|---|---|
| Hiring › Roles | PASS |
| Hiring › Interviews | PASS (calendar view still switches) |
| Hiring › Applicants register | PASS (bulk move on shown cards, W3-T2) |
| Hiring › Offers register | PASS (Overview figures = view counts, W3-T3) |

Modules for the live deploy (sync + `-u` on all four DBs: pb_hiring gains a
dependency on `pb_filter_kit` and new option translations that only an
upgrade loads):

| Module | Manifest version | Note |
|---|---|---|
| pb_hiring | 19.0.2.22.0 | new `models/filters_w3.py`, `depends += pb_filter_kit` |
| pb_learn | 19.0.20.7.1 | after W1/W4's 20.7.0; anchors.json + screens.js merged cleanly on the rebase |

## 1. Per screen

One facade (`pb.hiring` gets `pb.filter.mixin`); the kit sends
`context.pbf_ctx.kind` and every hook switches on it. Saved views are filed
under `hiring:roles|interviews|applicants|offers`. One kit in the board,
re-pointed per tab (`_switchKit`, queued); each list keeps its own filters.
The kit's calls refuse exactly whom the board refuses (`_can_read`).
"Hidden on payobook" = sections the kit hides on the preview copy because the
data has fewer than two values.

### Roles (`pb.hiring.requisition`)
- Sections (14): **Where it is** (the four steps as domains), **Role status**,
  **Department** (pinned); Needs attention (Waiting on you · Waiting for a
  sign-off · Nobody recruiting it · Over budget*), Hiring request, Budget*,
  Recruiter, Who they would report to (only for readers who may read
  employees), Country, Why it is needed, Candidates, People to find (number),
  Wanted by (future dates), Opened on (past dates). *hiring team only.
  Hidden on payobook: none.
- Views: All roles · Open roles · Over budget* · Nobody asked yet · Filled ·
  Opened this quarter.
- Sorts: What needs you first (default — the board's order of work: waiting
  on you, over budget, nobody recruiting, open, being set up, the rest; walked
  as disjoint tiers so it pages) · Newest first · Open the longest · Wanted
  soonest · Role, A to Z. Page 60.
- "Waiting on you": one seat query + the engine's own `_chain_my_seat` on the
  few records found — ~5 ms on the copy, so it is a filter, not just a figure.
- Steps strip counts follow the filters (R1); press = only that step, press
  again = step off. The "Showing … · Show all" line stays (lesson wording).
- Figures: Open roles / Requests to agree / No agreed request / Waiting on
  you / Over budget tick their filters (Over budget only when non-zero);
  Interviews this week / Opinions late open Interviews with that view;
  offer figures open Offers with that view.
- Removed: the search + four selects + Clear row, the 300-row window and its
  "Showing the newest …" line.

### Interviews (`pb.hiring.interview`)
- Base: the board's window (company, last 42 days or opinions still pending);
  a stand-in reads as the system limited to the covered recruiters' roles.
- Sections (10): **When it is** (today / next 7 days / later / already
  happened), **How it went**, **Role** (pinned); Opinions (late / still
  coming in / all in), Kind of step, How it happens, Recruiter, Job, Round
  (number), Date (kit 1.2.0 explicit presets: today, this week, next 7/30
  days, already passed, last 90 days). Hidden on payobook: When it is (every
  interview on the copy is in the past).
- Views: All interviews · Today · This week · Opinions late · Called off
  recently. Sorts: Earliest first · Latest first · Candidate, A to Z. Page 60.
- "Send the reminders due now" in the toolbar. The List/Calendar switch now
  wraps the whole list (shared_calendar.xml xpaths re-pointed).
- Removed: the search + Today/This week/Waiting/Late chips + Clear.

### Applicants register (`hr.applicant`, read as the system as before)
- Base: the jobs of the roles the reader may see (`_p9_roles`, newest role per job).
- Sections (11): **Where they are** (In play · Offer · Joined · Closed),
  **Role**, **Recruiter** (pinned); Needs attention (Waiting on you* ·
  Opinions late* · Interview this week · An interview arranged · Possibly the
  same person*), Stage, Moved to this stage; hiring team only: First look,
  Where they came from, Allowed to work, Applied, Look at them again.
  Email is searched for the hiring team only (it is masked on everybody
  else's cards). Hidden on payobook: none.
- The card flags became domains and match the old card-built counts exactly
  on the copy (waiting 14, opinions late 6, duplicates 2).
- Views: Everyone · In play · Waiting on you* · Opinions late* · Interview
  this week · Possible duplicates*. Sorts: Moved most recently (default) ·
  Longest in their stage · Applied most/longest ago · Name A–Z / Z–A. Page 120.
- Board: one column per stage, counts over the whole filtered list; a column
  with people beyond the pages read says "N more further down the list"
  (press = next page). List view: Name, Days in stage and Applied headings
  sort through the kit; the others no longer sort (a page sorted in the
  browser would be a stale array, R6).
- Hero line: figures counted over everybody (not the filters) with the same
  domains as the views. "People in play" now reads 15 where it used to read
  18: the old figure also counted people at the offer stages while the filter
  it opened excluded them; figure and filter now agree.
- Bulk move: acts on ticked shown cards; a person the new filters no longer
  list is unticked (R6). The register has no drag (it never had).
- Removed: search + role/recruiter/stage selects + flag chips + Clear,
  localStorage filter memory (`pbhr.applicants.v1`, `pbhr.offers.v1` are
  deleted on load; only Board/List is remembered, key `pbhr.applicants.v2`).

### Offers register (`pb.hiring.offer`, as the reader)
- Sections (13): **Where it is** (5 steps), **Offer status**, **Role**
  (pinned); Needs attention (Waiting on you · Joining in 30 days · Joining date
  passed), Recruiter, Who they will report to, Their answer, Starts on, Sent
  on, Joined on; hiring team only: Documents (past the date / still coming
  in / all in / not asked), Background check, A month (money). Hidden on
  payobook: Needs attention, Recruiter.
- Views: All offers · With the candidate · Joining in 30 days · Documents
  overdue* · Joined this month · Turned down. Sorts: Newest first · Joining
  soonest · Candidate, A to Z. Page 60.
- Step strip counts follow the filters; its two flags ("N waiting on you",
  "N joining in 30 days") are counted over the filtered list.
- Overview figures (offers waiting on you, joining soon, joined this month)
  now count through these views' own domains over every offer (no 200-row
  window); `get_board` is otherwise unchanged (R4).
- Removed: search + role/recruiter selects + five flag chips + Clear.

### Learn
- New anchor `hi-filters` (registered in anchors.json, `reserved`, file
  hiring_board.xml + also hiring_p9.xml; literal kept in an XML comment, F22).
- Practice replica `hiring` draws the filter strip (All roles · Open roles ·
  Nobody asked yet · Filters · search) under the tabs.
- Every existing `hi-*` anchor stays where it was (`hi-numbers`, `hi-steps`,
  `hi-tabs`, `hi-row`, `hi-card`, `hi-next`, `hi-reqchip`, `hi-applicants`,
  `hi-applicants-board`, `hi-offers`, `hi-offers-steps`, `hi-offer-row` …).
- Lessons: unchanged. The one lesson about the filter area ("press a step,
  then Show all") is still true — the "Show all" line was kept for it.
- `pb_learn` TestAnchorRegistry passes on the preview.

## 2. Test matrix (preview, Chrome DevTools MCP at 1440×900)

| Test | Roles | Interviews | Applicants | Offers |
|---|---|---|---|---|
| T1 open: panel, counts, first view lit, list | pass | pass | pass | pass |
| T2 tick → chip, N of total, others recount | pass | pass | pass | pass |
| T3 OR within a section | pass | — | — | — |
| T4 AND across sections | pass | — | — | — |
| T5 Only | pass | — | — | — |
| T6 find box, Enter, Escape | pass | — | — | — |
| T7 find nonsense → "Nothing matches" | pass | — | — | — |
| T8 date preset + range | pass | presets checked | — | — |
| T9 number "2 or more", grouped hints | pass | — | — | — |
| T10 chip jump (page still), ×, clear all | pass | — | — | — |
| T11 search + Escape | pass | — | — | — |
| T12 every sort changes the order | pass | — | pass (list headings) | — |
| T13 paging | pass (server pages, offset 0/5 vs full order) | pass (same) | pass (same) | pass (same) |
| T14 save / rename / share / delete view | pass | — | — | — |
| T15 every built-in view | pass | pass | pass | pass |
| T16 figures + steps, press again = everyone | pass | pass | pass | pass (steps) |
| T17 hide + reload memory | pass | — | — | — |
| T18 copied link reopens the same filters | pass | — | — | — |
| T19 bulk acts on the shown set | n.a. | n.a. | pass (W3-T2) | n.a. |
| T20 empty state + "Show all …" | pass | pass | — | pass |
| T21 phone 420 px: drawer + scrim, no sideways scroll | pass | — | — | — |
| T22 Vietnamese layout, values, views, sorts | pass | pass | pass | pass |

"—" = the same kit path already exercised on Roles in the same build; not
repeated per list. UI "Show N more" button not reachable on the copy (every
list is under one page); the server paging behind it is checked (T13).

Wave tests:
- **W3-T1** PASS — a stand-in covering one recruiter (created on the copy,
  archived after): list 2 roles = counts 2 = truth 2; every section counted
  only those roles.
- **W3-T2** PASS — after filtering In play, a ticked card was moved to
  Shortlist from the selection bar; columns 3→2 / 4→5, panel counts updated.
- **W3-T3** PASS — Overview "Joined this month 2" = view 2, "Joining soon 0"
  = view 0, "Offers waiting on you 0" = view 0. (There is no "Documents
  overdue" figure on the Overview; that view shows 1.)
- **W3-T4** PASS — each list keeps its own filters across tab switches;
  rapid tab hopping ends on the right list; no console errors.

Console: no errors after the fix (the only errors seen were
`ConnectionLost` while another wave restarted the preview).
Unit tests on the copy: `TestFiltersW3` 6/6, `TestAnchorRegistry` pass,
`TestRegistersP9` 7/8 — the failing one (`test_08`) checks the order of the
Hiring rail in `hiring_hub.js`, a file this wave does not touch (the rail
lists Interviews before Offers today): existing failure, not caused here.

Timings on the copy (admin, ms): roles layout 52 / counts 87 / page 357;
interviews 80 / 59 / 105; applicants 113 / 99 / 340; offers 71 / 45 / 77;
"waiting on you" 4–5.

Screenshots (local, not committed):
`docs/handovers/filter/w3_shots/roles_t1.png`, `roles_t21_phone.png`,
`applicants.png`, `offers.png`, `interviews.png`.

## 3. Deploy evidence (preview only — builders do not deploy)
- `pbf_preview.sh upgrade pb_hiring,pb_learn`: EXIT=0, no new ERROR lines
  (the 11 counted are the 02:49 collision below); `latest_version`
  pb_hiring 19.0.2.22.0, pb_learn 19.0.20.7.1.
- First attempt at 02:48 UTC collided with another wave's upgrade (the old
  double-grant race): all aborted with "could not serialize access", rolled
  back, rerun alone → EXIT=0 (F52).
- PO gate (ledger §5) on the box: 3,387 entries read.
- Preview held 08:10–08:27 UTC, released.

## 4. Kit gaps and debts
- **Kit gap K-W3-1:** `reconfigure` keeps the old `screen` until the new
  layout loads, so `_changed` during the switch writes to the old list's tab
  memory, and `load()` has no sequence guard (overlapping reconfigures apply
  an older layout last). Worked around here (queued switches, presses while
  `!kit.loaded` go through the queue). Suggest: clear `screen` and ignore
  `_changed` while `!loaded`, and drop a `load()` whose call was superseded.
- **Kit gap K-W3-2:** filters that came from a `?pbf=` link are not written to
  the tab memory until something changes (F54).
- **Kit gap K-W3-3 (small):** a `choice` section needs ≥ 2 options, so a
  single "waiting on you" fact cannot be a section on its own (grouped into
  "Needs attention" here).
- Debt: "Waiting on you" counts the reader's open seat on the first ACTIVE
  step only (as the board does); a route with two steps active at once is
  counted on the earlier one.
- Debt: the Applicants role section filters by `pb_requisition_id`; the card
  names the newest role on the job. They differ only when an applicant points
  at an older role on the same job.
- Debt: Interviews search no longer looks in panel names (`panel_employee_ids`
  is many2many; not a kit path).
- Debt: the background check section reads `offer.bgv_id` only; the row
  falls back to the role's check for the candidate when that is empty.
- Debt: Roles still read `get_board` (300 newest) for the figures and the
  step strip's "waiting" flags (R4); the step counts themselves are exact.

## 5. Self-score (design bar)
- Hero moment: steps strip and figures now drive the same panel the views
  do, and every count is over every record — 4/5.
- Zero dead-ends: designed loading skeletons, base-empty and filter-empty
  states with "Show all …", failure toasts naming what to press — 4/5.
- Plain language: every new label is a screen word, Vietnamese complete
  (option labels included) — 5/5.
- Motion with purpose: kit motion only; nothing new — 3/5.
- Keyboard / bulk: kit keyboard (/, Escape, arrows, Enter in find); bulk
  move kept on the shown cards — 4/5.

## 6. Commits (branch `worktree-agent-a4a00437ba90ee2d8`)
- `7fc67032e` feat(filter-w3): Hiring Roles and Interviews on the shared filter panel
- `1a0d70824` feat(filter-w3): Hiring Applicants and Offers registers on the filter panel
- `364bfadf5` feat(filter-w3): Learn knows Hiring's filter panel
- `180cdb0a2` fix(filter-w3): one list switch at a time on the Hiring board
- `bfc7dddf7` i18n(filter-w3): Vietnamese for the four Hiring lists' filter panels
- (this report + ledger F51–F56 (renumbered at merge) in the last commit)

Roles and Interviews share one component and Applicants and Offers one
patch file, so they are committed in pairs rather than one commit per screen.
Not committed: the screenshots under `docs/handovers/filter/w3_shots/`.

## 7. New gotchas
F51–F56 (renumbered at merge from F31–F36) appended to FILTER_LEDGER.md §4 (non-FIFO hold, concurrent upgrades
on the preview, the reconfigure race, link filters not remembered, DevTools
path roots, tests beside the preview need their own ports). Other waves may
append their own F31+ — renumber on merge.
