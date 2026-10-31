# FILTER programme — closeout (2026-10-31)

One shared filter mechanism (`pb_filter_kit`, the "B+" design: left facet
panel with live counts, saved views as tabs, clickable chips, find-a-filter box,
pinned sections, drawer on narrow screens) rolled out to every list, board and
kanban in Payobook. Owner decisions, rulings R1–R8 and gotchas F1–F56 live in
`FILTER_LEDGER.md`; the per-screen inventory is `INVENTORY.md`; each wave has a
handover `FILTER_W<n>.md` and a builder report `FILTER_W<n>_REPORT.md`.

## 1. What shipped — 34 screens, all LIVE on payobook, payobook_template, rize, p0clone

| Wave | Screens | Modules (live version) | Report |
|---|---|---|---|
| Pilot | Employees | pb_people 1.3.0, **pb_filter_kit 1.2.0** | (direct build, 2026-10-30) |
| W2 | Contract renewals, Probation, Exits | pb_contract_lifecycle 1.3.0, pb_probation 1.5.0, pb_offboarding 1.4.0 | FILTER_W2_REPORT.md |
| W4 | Vendors, Praise, Assets, Ask HR, Approvals | pb_vendor_access 1.16.0, pb_rnr 1.4.0, pb_assets 1.2.0, pb_ask_hr 1.3.0, pb_approval_config 1.7.0 | FILTER_W4_REPORT.md |
| W1 | Contracts, Journeys, Awards, Growth plans, New joiners | pb_contracts 1.10.0, pb_lifecycle 1.6.0, pb_comp_ben 1.6.0, pb_pip 1.4.0, pb_onboarding 1.3.0 | FILTER_W1_REPORT.md |
| W6 | Import batches, Full & Final / Proration / Retro ledgers (own pages + Pay hub), Records Desk, Statutory › Data (4 tables), Integrations (connectors + Data) | pb_import 1.7.0, pb_payrun_ledgers 1.4.0, pb_records 1.8.0*, pb_statutory 1.5.0, pb_integrations 1.15.0 | FILTER_W6_REPORT.md |
| W5 | Salary Structures, Pay Run › Payslips, Pay Runs (own page + Payroll hub) | pb_structures 1.2.0, pb_payslip_review 1.4.0, pb_payruns 3.3.0 | FILTER_W5_REPORT.md |
| W7 | Business Trips (own + Expenses), Time Off approval queue, Attendance corrections (own + Time hub), Expense claims | pb_business_trip 1.3.0, pb_timeoff 1.8.0, pb_attendance_flow 1.2.0, pb_expenses_hub 1.2.0 | FILTER_W7_REPORT.md |
| W8 | Overtime approval queue, Payroll Report, Workforce-planning forecast table, Pay review worksheet | pb_hr_workforce 4.22.0, pb_pay 3.7.0, pb_hr_workforce_planning 8.2.0 (files synced; **module installed on none of the 4 DBs**) | FILTER_W8_REPORT.md |
| W3 | Hiring: Roles, Interviews, Applicants, Offers | pb_hiring 2.23.0 | FILTER_W3_REPORT.md |
| all | Learn anchors / replicas / lessons follow every screen | pb_learn 20.8.2 | — |

\* pb_records went 1.7.0 (W6) → 1.8.0 (white-label pass by gitlocal-65 the same evening); the filter work is in both.

Deliberately NOT converted (ledger R5/R8): Access › People (#34, access-studio
grid, owner to decide), and non-record rows (attendance exceptions, workbook
grid, statutory tax union).

Branch `19.1` at `63adc5bcc` (pushed). Every live deploy is logged START/DONE in
`/opt/deploy-notes.md` with evidence under `/tmp/pbf-b<n>-w<k>` on the server
(units pbf-b1-w2kit, pbf-b2-w4, pbf-b3-w1, pbf-b4-w6, pbf-b5-w5, pbf-b6-w7,
pbf-b7-w8, pbf-b8-w3). All passes: EXIT=0, 0 errors, cron states 31/28/74/42
unchanged, hashes + `latest_version` verified, sites 200, live smoke on
payobook.com with a clean console for every screen.

## 2. What users get (plain words, for the owner's summary)

- Every list counts **every** record server-side; the old "newest 300/400/600
  loaded" caps are gone (Hiring, Statutory dependents 3,851, Contracts 4,520,
  Records Desk 4,547, Payroll Report).
- Saved views: private, with a "Share with everyone" switch; built-in views per
  screen (e.g. Pay Runs "Approved, not paid", New joiners "Joining this week").
- Speed-ups found on the way: Pay Runs filter click 4.6 s → 0.3 s; Payroll
  Report 112 s → ~1.5 s per page of 60; Records Desk page ~1.2 s (faster than
  before); Payslips "Needs review" cached 2 min per worker.
- Vietnamese for every new string; search placeholders translated on all
  screens (several had English-only before).
- Learn: anchors kept or added on every screen; replicas draw the filter strip.

## 3. Kit gaps — consolidated backlog for `pb_filter_kit` (items 1–2 shipped as 1.3.0; the rest is the 1.4.0 backlog)

Priority order (count = how many waves asked for it).

1. ~~**View tab counts do not refresh after an action**~~ (W7, W8) — **DONE in
   kit 1.3.0 (2026-11-01)**: `pbf_counts(views=True)` recounts every tab on the
   kit's full `refresh()`, so a screen's existing `await this.kit.refresh()`
   after an approval updates the tabs at once (ledger §3a-ter).
2. ~~**"Clear all" leaves the previous tab lit with a dirty dot**~~ (W1, W2 K1,
   W4 #6, W8 #1) — **DONE in kit 1.3.0**: `clearAll()` sets `viewKey = ""`
   before `_changed()`. Residual: a *figure* that matches no view still keeps the
   previous tab lit with a dot — that is the Save/Reset design, not a bug.
3. **`ctx` only rides the kit's own calls** — screens must forward
   `context: {pbf_ctx}` on their page/select-all/export calls (W6 F31; export
   `kit.kw()`).
4. **Labels of ticked values read as the reader** even on sudo screens (W4 #3,
   W7 F42; `_pbf_label_values` should use `_pbf_records().env`).
5. **`reconfigure` race**: `screen` keeps the old key until the new layout
   loads; `load()` has no sequence guard (W3 K-W3-1).
6. **Filters arriving by `?pbf=` link are not written to tab memory** until a
   change (W3 F54).
7. **Date presets**: "none" always offered (blank radio without `none_label`,
   W5 F40); missing "this quarter / next 60 / today / overdue" (W4 #4, partly
   answered by 1.2.0 `presets` list).
8. **Number sections**: no `unit` in the range hint (W8 #2); mixed currencies
   across companies (W4 Assets, W7 Trips) — a per-currency number filter.
9. **`initial` cannot mean "on top of the first view"** (W7 #3).
10. **Kanban lane paging** is re-written per board (W5 #2).
11. **`hidden: True` sections** shown only while on (W6 #3, Records
    "Hand-picked"); **per-value `domain_method` args** (W6 #2).
12. **Per-request fact cache** across the three kit calls on a cold start
    (W8 #4, F50; W4 #8 strip counts).
13. Small: `pickFirstFound` skips a section whose NAME matches (W4 #7); a
    ticked zero-match value is appended out of order (W4 #5); phone scrim only
    from the kit's own `matchMedia` (W2 K2); a `choice` needs ≥ 2 options so a
    single yes/no fact cannot stand alone (W3 K-W3-3).

## 4. Design debts per screen (owner-visible, not blocking)

- **Figures vs lists**: Journeys/New joiners "Steps overdue" counts steps, the
  list shows journeys (W1); Integrations numbers line counts in-use connectors
  while the panel also lists archived (W6).
- **Payroll Report** still compares with the latest earlier run of ANY scheme —
  can be a run with nobody in common (W8, pre-existing). Gross/net/deductions
  cannot be filtered (not stored, R2) — same for Payslips net pay (W5).
- **Layouts**: Leave queue and Attendance corrections now stack their side
  panel under the list (W7); forecast table and pay-review worksheet are
  cramped with the panel open — "Hide filters" is remembered (W8).
- **Probation** "Needs somebody" has no filter equivalent (W2). **Trips**
  approve could not be exercised on the payobook copy (no approval route,
  W7 F46). **Records Desk** "Employment status" unverified on a tenant whose
  feed reports statuses (rize) (W6).
- **Old untranslated strings** in pb_probation/pb_offboarding/pb_contract_lifecycle
  (~390/560/520), pb_records, pb_statutory, pb_integrations, pb_timeoff,
  pb_attendance_flow, pb_payruns (49) — pre-existing, not part of this programme.
- Pre-existing test mismatches: `pb_payhub/tests/test_payhub.py` (3 vs 2
  `!props.embedded`), a Hiring menu-order test, `pe-filters` anchor test (F17).

## 5. Not exercised on the preview (copy too small or no fixture)

T13 paging in the UI on W2 screens; "Show N more" on Hiring; OT queue paging
(19 requests); Payslips T8/T10/T14/T17/T18/T21 (kit-shared, run in full on
Structures); phone layout of Records Desk (styles only); "not your queue"
sentence for a payroll manager without attendance rights; Payroll Report on a
900-slip run live (checked on the preview: 874/885 counts equal the old screen).

## 6. Preview-copy residue (pbf_preview on the server)

One settlement sent for approval (W6), one demo leave request approved (W7), one
overtime request approved (W8), Workforce planning installed with scenario
"DEMO W8 forecast test" (80 rows). No saved views or stored prefs left. The copy
is throwaway: `pbf_preview.sh reset` rebuilds it from payobook.

## 7. Process notes worth keeping

- One shared preview (3 GB server) + `flock` hold loop worked, but the
  queue is not FIFO and a long wave starves the others (W7 waited ~4.5 h behind
  W6). Next time: two previews, or cap a hold at 45 min.
- Builders in worktrees + Fable merging per wave: every wave collided on
  `pb_learn/__manifest__.py` and the ledger's F-numbers. Rule for next time:
  each wave gets a reserved F-range in its handover, and pb_learn's version is
  bumped only by the coordinator at merge.
- Stage every live deploy from `git archive HEAD`, never the working tree —
  a parallel session (white-label) was editing the same checkout this evening.
- Usage limit hit twice (07:20 and 14:10 AEDT); subagents resumed cleanly by
  SendMessage with "Where I stopped" notes in their branches.
