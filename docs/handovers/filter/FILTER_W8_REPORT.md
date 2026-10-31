# FILTER wave 8 — report (Overtime queue, Payroll Report, Forecast table, Pay review)

Branch `worktree-agent-aabf1aa616bfdd0ab`, rebased on `19.1` @ `15049168f`
(kit 1.2.0). Builder: Opus. Tested on the shared preview (`pbf_preview`, a
copy of payobook) while holding it as `w8` 07:50–08:10 UTC — nothing touched
the live addons, the live databases or `/opt/deploy-notes.md`.

**Summary: all four screens converted and passing T1–T22 (or n.a.) and
W8-T1…T4 on the preview. Console clean on every screen.**

| Screen | Module | Result |
|---|---|---|
| Overtime › Approval queue | `pb_hr_workforce` | PASS (W8-T1: select all + approve acted on the 1 card shown) |
| Insights › Payroll Report | `pb_hr_workforce` | PASS (W8-T2: Pay changed = old rows with events, 874 / 885) |
| Workforce planning › Employee forecast table | `pb_hr_workforce_planning` | PASS (W8-T3) — module is NOT installed on payobook; installed on the preview to test |
| Pay review › worksheet | `pb_pay` | PASS (W8-T4: Stops approval 1 = old chip count; Add 1% touched only that row) |

Modules for the live deploy (sync + `-u`; each gains a dependency on `pb_filter_kit`):

| Module | Manifest version | Installed on payobook? |
|---|---|---|
| pb_hr_workforce | 19.0.4.22.0 | yes |
| pb_pay | 19.0.3.7.0 | yes |
| pb_hr_workforce_planning | 19.0.8.2.0 | **no** (uninstalled on the payobook copy; `-u` only where installed) |
| pb_learn | 19.0.20.8.0 | yes (other waves also bump pb_learn and edit `screens.js` / `anchors.json` — expect a merge on those files) |

---

## 1. Per screen

### 1.1 Overtime desk › Approval queue — `pb.ot.desk` → `hr.overtime.request`, screen `otqueue`
- Base: every SENT request (submitted, approved, refused) of the reader's
  companies, read under the same sudo as `get_desk`, behind the attendance
  manager gate. `pbf_layout` refuses a reader the desk refuses (pure bonus
  viewer → "Not your queue" sentence, Bonus Hours door still there); counts
  answer nothing for them (base `id = 0`).
- Sections: **Department**, **Kind of overtime** (a choice with the cards'
  words, F27/F28), **Day worked** (today … last year + pick dates) pinned;
  Where it is (Waiting for a decision / Approved / Refused), Person, Manager,
  Hours asked for (number), Overtime rule, Company; payroll managers only:
  Beyond the ceiling (has bonus hours / within) and Bonus hours (number).
  Hidden on payobook (one value): Overtime rule, Company.
- Views: To approve (start) · Approved this month · With bonus hours (bonus
  viewers) · Weekend and holiday · This week.
- Sorts: Newest day first (default, the old order) · Oldest day first · Most hours first · Name, A to Z.
- Page 40 cards ("Show N more"). Decided cards show the stored split and an
  Approved / Refused chip, no tick, no buttons.
- Bulk (R6): "Select the N waiting here" = the waiting cards on the page;
  a filter change drops ticks that left the page.
- Numbers line: "pending approvals" = To approve; each "<kind> this month"
  figure = that kind, this month, waiting or approved. "Near or over the
  ceiling" stays a plain figure (a Python fact about people).
- Removed: the unbounded queue load (`get_desk(with_queue=False)`; the full
  queue stays for older callers, R4), the bare "Select all".
- Bonus Hours review untouched (its own server rail, R5-like).
- Learn: `coach="'wf-ot-filters'"`, declared (reserved); `wftime()` replica
  gains the filter strip inside `wf-ot-queue`. Lesson texts (`wf-ot-queue`
  ×4) still true.

### 1.2 Payroll Report — new facade `pb.payroll.report` → `hr.payslip`, screen `payreport`
- Base: the picked run's payslips, not cancelled (run = `pbf_ctx.run_id`;
  the panel is reconfigured on a run change and the reader's filters travel
  with them; saved views work on every run).
- Sections: **Department**, **Against the last run** (Pay changed / Same as
  last run / Nothing to compare with — `domain_method`), **Job position**
  pinned; Pay structure, Payslip status (Being prepared / Waiting for
  approval / Done), Manager, Company, Joined (in this run / before).
  On run 336: Pay structure, Payslip status, Company, Joined hide (one value).
- Views: Everyone in this run · Pay changed · New joiners this run.
- Sorts: Name, A to Z (default, the old order) · Name, Z to A · Payslip number.
- Page 60 rows, "Show N more"; the three tabs render the page. The KPIs and
  the Dept Summary are computed on the server over EVERY matching payslip
  (one grouped query + the request's facts) and say "Totals for the N
  payslips the filters show" when filtered. Pressing **Changes** = the Pay
  changed view.
- "Pay changed" = the rows' own rule (gross or basic moved against the same
  person's payslip in the previous run, to the cent), computed once per
  request for the whole run with one SQL pass that mirrors the pay run's
  `_compute_pb_totals` bands (ORM fallback without pb_payruns). SQL vs ORM
  figures identical on 30 sampled payslips; summary and department table
  identical to the old `get_batch_report` on runs 336 and 339.
- Gross / net / deductions are not stored (R2): no number sections (debt).
- Removed: the whole-run load (old: 112 s for 900 slips), the name-only
  browser search.
- Learn: `coach="'rp-filters'"`, declared (reserved); `reports()` replica
  gains the filter strip. `rp-pick` / `rp-kpis` / `rp-tabs` unchanged and
  their lesson texts still true.

### 1.3 Workforce planning › Employee forecast table — new facade `pb.wfp.forecasts` → `wfp.employee.forecast`, screen `wfpforecast`
- Base: the selected scenario's forecast rows, excluded people included.
- Sections: **Department**, **Increase rule** (none = "No rule applied"),
  **Increase %** (number) pinned; Size of the increase (the row colour
  bands: over 10% / over 5% up to 10% / up to 5% / none / a decrease), In
  the forecast (counted / excluded), Job position, Manager, Increase amount
  (money), Country, Location or cost centre, Months of service.
  On the test scenario Country hides (all VN).
- Views: Everyone in the forecast (= counted only, the old table) ·
  Increases over 10% · No rule applied · Excluded people. ("Everyone in the
  scenario" was renamed: that view leaves the excluded out.)
- Sorts = the table's columns (13), default Biggest increase first. A column
  header press picks its sort (second press: the other direction where
  there is one); the sorted header is tinted.
- Page 60 rows, "Show N more"; excluded rows carry an "Excluded" tag and the
  reason as a tooltip.
- The department and employer-cost charts keep reading the whole scenario
  from `get_dashboard_data` (said in the template). Only the table block
  changed; Chart.js, fa icons and the other tabs untouched.
- Learn: nothing in Learn describes this screen
  (`grep -c "wfp\|Forecast Detail\|workforce_planning"` on anchors.json,
  screens.js, learn_content.json → 0, 0, 0); no coach anchor added.

### 1.4 Pay review › worksheet — new facade `pb.pay.review.sheet` → `pb.pay.review.line`, screen `payreview`
- Base: the open review's rows (`pbf_ctx.review_id`), read with the review's
  widened company context (GR27); refusal for readers without a pay role.
- Sections: **Team**, **Score** (Not scored / Scored), **In the band**
  (below / inside / above / no band yet) pinned; Stops approval
  (`domain_method` over the chips JSON, one query: 30 ms), Whose team (My
  team / Other teams), Rise or not (No rise / A rise / Less pay), Manager,
  Job position, Division, Pay band, Proposed rise (%), Where the row is.
  Hidden on payobook's 902-row review: In the band (nobody has a band),
  Whose team (admin manages nobody), Division, Pay band, Where the row is.
- Views = the six old filters, same words and order: Everybody · My team ·
  Not scored · Stops approval · Paid below the band · No rise (old vs new
  counts equal: 2 / 0 / 901 / 1).
- Sorts: Team, then name (default — the old window order, identical first
  120 rows) · Name, A to Z (only for readers who may see names) · Biggest /
  smallest rise · Highest score · Lowest in the band · Paid most.
- Page 120 rows (the old window), "Show 120 more".
- Privacy: rows still say "Person N" without `can_names`; such a reader also
  cannot search or sort by name; no section lists the people.
- Bulk (R6): no selection = the rows shown; "Select everything matching (N)"
  after the page is picked = one server call (cap 5,000, says so). After a
  write the rows are patched in place and the counts recount.
- Header "N people have not been scored" reads the panel's Score count
  (always counted), so it follows the other filters (R1).
- Fix found on the way (pre-existing): the worksheet's capture-phase keys
  took "-", "+" and Enter typed in ANY box as Take off 1% / Add 1% / edit
  row; typing in a field is now ignored (F31).
- Removed: the six filter buttons, the change-only search box, the
  Back/More pager.
- Learn: `coach="'pp-filters'"`, declared (reserved); `payreview()` replica's
  filter strip carries it plus Filters and the search. Lessons name the same
  six words and stay true.

## 2. Test matrix (preview, Chrome DevTools MCP 1440×900; T21 at 420×860)

| Test | OT queue | Payroll Report | Forecast | Pay review |
|---|---|---|---|---|
| T1 open, counts, first tab, list | pass | pass | pass | pass |
| T2 tick → chip, own counts stay, others recount | pass | pass | pass | pass |
| T3 OR within section | pass | pass | pass | pass |
| T4 AND across | pass | pass | pass | pass |
| T5 Only | pass | kit ¹ | kit ¹ | kit ¹ |
| T6 find + Enter + Escape | pass | pass | kit ¹ | kit ¹ |
| T7 nothing matches | pass | kit ¹ | kit ¹ | kit ¹ |
| T8 date preset + range | pass | n.a. (no date section) | n.a. | n.a. |
| T9 number | pass ("4 or more") | n.a. (R2) | pass ("10 or more") | kit ¹ |
| T10 chip × / clear all | pass | pass | pass | pass |
| T11 search + Escape | pass | pass | pass | pass (and the "-" guard) |
| T12 sorts | pass | pass | pass (menu + headers) | pass |
| T13 Show N more | n.a. (19 sent requests < 40) | pass (60→120) | pass (60→73) | pass (120→240) |
| T14 save / rename / share / delete | pass | kit ¹ | kit ¹ | kit ¹ |
| T15 built-in views | pass | pass | pass | pass |
| T16 numbers line | pass (pending, lit) | pass (Changes, lit/unlit) | n.a. | n.a. |
| T17 hide + reload | pass | kit ¹ | kit ¹ | kit ¹ |
| T18 link | pass (`?pbf=` reopened the same filters) | kit ¹ | kit ¹ | kit ¹ |
| T19 bulk on the filtered set | pass (W8-T1) | n.a. | n.a. | pass (W8-T4, everything matching 901) |
| T20 empty + start again | pass | pass | pass | pass |
| T21 phone drawer | pass | pass | kit ¹ | kit ¹ |
| T22 Vietnamese (`pbf_layout`, lang vi_VN) | pass | pass | pass | pass |
| Console (errors/warnings) | clean | clean | clean | clean |

¹ Same kit code path, exercised in full on the OT queue in this wave (and on Vendors / Approvals in wave 4).

Wave tests:
- **W8-T1** OT: Department = Civil Works + To approve → 1 waiting card →
  "Select the 1 waiting here" → Approve: submitted 5→4, approved 13→14 (only
  that request). PASS.
- **W8-T2** Payroll Report: Pay changed view = old rows with events — run 336
  (900 slips) 874 = 874, run 339 (902) 885 = 885; summary and department
  table identical. Facts timed (below). PASS.
- **W8-T3** Forecast: default "Biggest increase first" = the old default
  order (same 73 people, identical increase sequence; ties of equal amounts
  may swap). PASS.
- **W8-T4** Pay review: Stops approval 1 = old chip count 1; Add 1% on that
  view changed exactly line 1805 (22% → 23%, every other line unchanged),
  then Take off 1% put it back. PASS.

### Timing (payobook copy; server time per call)

| Call | OT queue | Payroll Report (run 336, 900 slips) | Forecast (80 rows) | Pay review (902 rows) |
|---|---|---|---|---|
| pbf_layout | 101 ms | 348 ms warm · 7.7 s first after restart | 22 ms | 113 ms |
| pbf_counts | 90 ms | 415 ms | 120 ms | 311 ms |
| page | 92 ms | 1.5–1.7 s (60 rows, two payslips' lines each) | 105 ms | 370 ms |
| Python fact | — | "Pay changed" whole run: 0.4 s warm, ~8 s cold (one SQL pass 130 ms) | — | Stops approval: 30 ms |
| Old screen | — | `get_batch_report` 112 s (run 336), 103 s (run 339) | — | — |

## 3. Deploy evidence (preview rehearsal only — the live deploy is the coordinator's)
- `pbf_preview.sh upgrade pb_filter_kit,pb_hr_workforce,pb_pay,pb_learn,+pb_hr_workforce_planning`:
  **EXIT=0**, no ERROR lines in this run (the script's "errors=11" counts an
  earlier day's lines in the appended log — F33).
- Versions on the preview after it: pb_filter_kit 19.0.1.2.0,
  pb_hr_workforce 19.0.4.22.0, pb_pay 19.0.3.7.0, pb_learn 19.0.20.8.0,
  pb_hr_workforce_planning 19.0.8.2.0 (installed).
- PO gate (server `PoFileReader`) passed: pb_hr_workforce vi_VN.po,
  pb_hr_workforce_planning vi_VN.po, pb_pay vi_VN.po and pb_pay.pot.
- Server log while held: only the platform's `mail_presence` serialisation
  noise; no `Filter section … hidden` / `Filter counts … failed`.
- Live: not touched. Cron counts / hashes / per-DB versions: n.a. for builders.
- **Changes left on the preview copy:** pb_hr_workforce_planning installed;
  one scenario "DEMO W8 forecast test" with 80 forecast rows and two DEMO
  rules; one overtime request approved (W8-T1); pay review line 1805 back to
  22%. No saved views left; `pbf:*` storage cleared; tab closed.

## 4. Kit gaps and design debts

Kit gaps (pb_filter_kit unchanged):
1. **Clear all keeps the current view lit with a dirty dot** even when the
   view's own filter was cleared (OT "To approve •" after Clear all). Seen in
   W2/W4 too.
2. **Number range hint has no unit** ("In this list now: 2 to 8." for hours;
   the forecast's percent the same). A `unit: 'hours' | 'pct'` would read
   better.
3. **View counts are not refreshed after a write** (OT: "To approve 5" after
   approving one; the list and figure said 4). A `kit.reloadViews()` would fix it.
4. **Each kit call is its own request**, so per-request Python facts are
   computed three times on a cold start (F34). A request-spanning cache
   would need a kit hook.

Design debts:
- Payroll Report: gross / net / deductions cannot be filtered (not stored, R2).
- Payroll Report: the previous run is still "the latest run that ended before
  this one started", whatever its scheme (pre-existing) — e.g. run 1553's
  comparison run shares no employee with it, so all 1,000 are "Nothing to
  compare with".
- Payroll Report: 60 rows take ~1.5 s (two payslips' lines per row through
  the ORM, same per-row cost as before).
- OT queue: "near or over the ceiling" is not a filter (Python fact).
- Forecast: the legacy table (10 columns, fa icons) wraps tightly with the
  panel open; "Hide filters" gives it the width back. The dashboard is a
  candidate for its own redesign.
- Pay review: a 9-column worksheet beside the panel scrolls sideways under
  ~1,500 px; "Hide filters" restores the full width (remembered).

## 5. Self-score (design bar)

| Screen | Hero moment | Zero dead-ends | Plain language | Motion | Keyboard / bulk |
|---|---|---|---|---|---|
| OT queue | figures = views; decided cards readable in place | skeleton, queue clear, search/filter empty with "Show what is waiting", refusal sentence | yes | kit + pulse skeleton (reduced-motion safe) | `/`, kit keys; select the waiting on the page |
| Payroll Report | totals and department summary follow the filters; Changes is a button | no run, no payslips, filter/search empty, load failure toast | yes | kit + pulse skeleton | `/`, kit keys |
| Forecast | the colour bands are a filter; headers sort through the panel | no rows, filter/search empty, load failure toast | yes | kit + pulse skeleton | `/`, header clicks |
| Pay review | six familiar views + "everything matching" for the worksheet tools | review empty, filter/search empty, refusal | yes | kit + pulse skeleton | arrows/shift/Enter/± kept, now safe while typing |

## 6. Commits (branch `worktree-agent-aabf1aa616bfdd0ab`)
- `c7918215e` feat(filter): Overtime desk queue on the shared filter panel (+ pb_learn 19.0.20.8.0)
- `2ee5f7238` feat(filter): Payroll Report on the shared filter panel
- `d9f8bca65` feat(filter): Workforce planning forecast table on the shared filter panel
- `b598abeb7` feat(filter): Pay review worksheet on the shared filter panel
- `b2ba04f3a` perf(filter): Payroll Report summary in one grouped query
- `0f9dd5118` fix(filter): w8 panels follow ledger F27-F29
- `dc2edd53b` i18n(filter): Vietnamese for the wave 8 panels; refresh pb_pay.pot
- this report + ledger F31–F34 (docs commit)

Not committed: nothing of the product. Not pushed, not merged.

## 7. New gotchas
Appended to `FILTER_LEDGER.md` §4 as **F31–F34** (screen key handlers eat
typing in the kit's boxes; timing staged code in a shell without the lock;
the preview dying after an upgrade + the appended error count; cold
per-request facts).

Also seen (already F26, fixed in 19.1 since): at 02:48 UTC the old `hold`
told w6 and w8 "HELD" together and two upgrades collided; w8 backed off,
re-queued with the fixed script and was granted at 07:50.
