# UPDATES — Phase 4 handover: leave opening balances sheet, attendance tile

Start only after Phase 3c is live. Read first: `UPDATES_LEDGER.md` (all of it),
`UPDATES_P3B_REPORT.md` §R9 items 1–2 (this phase's research — do not re-derive, do re-grep
line numbers), `UPDATES_P2D_REPORT.md` (how a second kind of sheet was added — the pattern
to clone). Visual reference: `docs/design/updates-desk-prototype.html`.

**Design mandate (owner, verbatim): "extreme WOW, intuitive, out-of-this-world experience,
best in class".** Indigo design system (`#5A4BB0`), white cards, Lucide icons, never emoji.

**White-label rule:** the word "Odoo" never appears in any user-visible string. Technical
identifiers stay. **Plain words on screen**: "leave type", "days available", "start date
of the balances", "attendance".

First job: add to the ledger owner decisions D16–D19 (below) and the P4 row's real scope.

## 1. Owner decisions (2026-11-12) — do not re-ask

- **D16** rize keeps "no approval" for new employees, from a sheet or by hand. Do not
  change it and do not raise it again.
- **D17** Updates does NOT get its own timesheet/attendance sheet. It shows a tile that
  opens the existing attendance file screen. No fifth way of loading attendance.
- **D18** Updates gets a third kind of sheet: **Leave opening balances** for many people at
  once.
- **D19** Year-to-date pay figures: design first, owner decides later. **Not in this phase.**

## 2. Scope

1. A third kind of sheet in People › Updates: "Leave opening balances" — same four steps,
   same batch, drafts, history; approval and undo as designed below.
2. An "Attendance and timesheets" tile on the Updates Start screen that opens the existing
   attendance file screen.

Version: `pb_updates` → next minor.

## 3. Binding non-goals and safety rails

- **`pb_timeoff` is being edited by another session. Do NOT edit, stage or deploy any file
  in `pb_timeoff`.** Call its public methods only; if `pb_updates` must depend on it, use a
  soft check (`'pb.leave.policy.edition' in self.env`) or a manifest dependency only if
  `pb_timeoff` is installed on all five databases (check; report). If the work truly needs
  a change inside `pb_timeoff`, stop that part and report — do not make it.
- **One way to write a balance.** Where the company uses the leave policy layer, an
  opening balance is written ONLY through
  `post_opening_balance(employee, leave_type, cutover_date, available_days, carried_days,
  taken_year_to_date, review_reference)` (`pb_timeoff/models/rize_policy.py:367-394`), so
  its rails (refuses when allocations overlap the cutover; frozen postings; unique
  `posting_key`) stay in force. Where the company does not use the policy layer (no
  edition applies to the person — find how the Time Off screen decides), an opening
  balance is ONE validated `hr.leave.allocation` created the way the standard allocation
  flow does, marked so it can be recognised as an opening balance from Updates.
- **Never a second opening balance.** A person + leave type that already has an opening
  balance (policy posting of kind `opening`, or an allocation previously made by this
  sheet), or allocations overlapping the start date, is refused in a sentence — never
  added on top, never replaced silently. Replacing is: undo the earlier update, then send
  again.
- **Never touch leave already taken or requested**, accrual, carry-over or the January
  rollover. No leave requests are created or changed.
- **Undo** removes exactly what this update created and only if nothing has drawn on it:
  when leave has since been taken against that allocation such that the balance would go
  negative, undo of that row is refused in a sentence and the rest proceeds. If the policy
  layer's postings are frozen and offer no reversal method, undo for policy-layer rows is
  not offered — the screen says so BEFORE applying. Report which.
- Half-days and decimals: accept what the leave type's unit allows (days / half-days /
  hours — read it from the leave type); otherwise refuse. Negative numbers refused. Cap:
  365 days (or the hour equivalent) per cell, refused above.
- Approval: the batch goes through the approval engine on the same route as the pay lane
  (records route) — a leave balance is a liability, not a personal detail; it never applies
  "at once" unless that route is "No approval needed".
- No timesheet sheet, no attendance import of any kind in Updates (D17). No year-to-date
  figures (D19). No change to existing lanes, dates, one-offs, new joiners, drafts.
- Never apply anything on `rize` or `sudima`. Do not touch `pb_lifecycle`, `pb_hiring`,
  `pb_me_expense`, `pb_timeoff`, `docs/handovers/workflow2`.

## 4. Design

### 4.1 The sheet

Start: third choice "Leave opening balances" with a date field "Balances as at" (the
cutover date; default today; not in the future; not more than 366 days back) and the
usual people filter.

Download: one row per chosen person; identity columns as other sheets; then one column
group per leave type that tracks a balance and is offered in the person's company (the
leave types the Time Off screen shows with an allocation requirement): **"<Leave type> ·
days available"** always; and, only where the policy layer applies to at least one person
in the export, the two optional columns "· carried from last year" and "· already taken
this year" (they are record-only figures in `post_opening_balance`; say so on the "Read
me" sheet). Cells show the unit in the header ("days" / "hours"). A person who already
has an opening balance for a type gets that cell pre-filled and grey ("already set").
The "Read me" sheet explains the date, blank = leave alone, what the two optional
columns mean, and that a balance can only be set once per person and leave type.

Match columns: "Goes to" offers leave types (grouped: days available / carried / taken),
the columns that find the person, and nothing else. Remembered layouts are kept
separately for this kind.

Review: the standard grid. Cell states: new balance · same (equals the existing opening
balance) · already set (differs from an existing opening balance → refused with "… already
has an opening balance of N days for <type>. Undo that update first.") · overlaps
("… already has <type> days from <date>; an opening balance cannot be added on top.") ·
not a number / negative / too large / unit not allowed · leave type not offered in the
person's company. Column totals per leave type and a grand total of days; a summary strip
"N people · M balances · X days in total".

Apply: one card — "Leave opening balances as at <date> · M balances for N people · go to
<who> for approval" (or "are set now"), plus the undo sentence that applies. Done / Past
updates / home: its own icon (`calendar-range` or similar Lucide), states as other kinds.

### 4.2 Storage of what was written

`pb.updates.leave.line` (in `pb_updates`): batch, employee, leave type, cutover date,
available / carried / taken, state (`waiting` / `set` / `refused` / `undone`), the created
`allocation_id` and/or policy `posting` reference, refusal reason. The batch is what is
approved (clone the P2d adapter approach). All rows of an update are written in one
transaction on approval; a row whose rails refuse at write time (something changed since
review) is recorded `refused` with the reason and the others still go through — report
this choice in the Done screen ("3 could not be set: …"); never silently dropped.

### 4.3 Attendance tile (D17)

On Start, below the three kinds, a quiet secondary tile "Attendance and timesheets —
loaded on the Attendance screen" with a `clock` icon and an arrow; it opens the existing
attendance file screen (`pb_attendance_flow` cockpit action; the import wizard is
`pb.attendance.import.wizard`, `pb_attendance_flow/views/attendance_flow_action.xml:3`).
Shown only when that module is installed and the user may open that screen (ask the
action/menu's own groups; no new right). No other change.

## 5. Tests (numbered)

| # | Case | Expect |
|---|---|---|
| L1 | Company on the policy layer: balances for 3 people × 2 leave types, approved | written through `post_opening_balance`; the Time Off screen shows the days |
| L2 | Company without the policy layer | one validated allocation per cell, recognisable as an opening balance |
| L3 | Second opening balance for the same person + type; overlapping allocation | refused with the two sentences; nothing added |
| L4 | Same value as the existing opening balance | `same`, not sent |
| L5 | Units: half-day where allowed / not allowed; hours type; negative; 366 days | accepted / refused with sentences |
| L6 | Leave type not offered in the person's company | refused |
| L7 | Approval route: approve / send back / turn down / cancel; "No approval needed" | rows follow the batch; nothing written before approval |
| L8 | Something changes between review and approval for one row | that row `refused` with reason, others written, Done screen lists it |
| L9 | Undo: untouched balance; balance already drawn on; policy-layer row | removed / that row refused, rest proceeds / as designed and stated on screen |
| L10 | Leave taken, leave requests, accrual, carry-over rows | untouched (counts before = after) |
| L11 | Draft of a leave sheet; history; "Read me"; remembered layout separate | as other kinds |
| L12 | Attendance tile: module present + right / absent / no right | shown and opens the screen / hidden / hidden |
| L13 | Existing kinds (lasting changes, one-offs, new joiners) | all suites green; review 4,575 × 73 ≤ 25 s |
| L14 | `.po` parse gate; "Odoo" scan of new strings | clean |

Fixtures: demo people named "DEMO …"; no "ZZ", no "RIZE".

## 6. Browser validation, deploy, report

- Browser (local copy, console read at every step, the people's company): the leave sheet
  end to end with approval by a second user, the refusals, undo, the Time Off screen
  showing the result, the attendance tile. Screenshots to `outputs/updates-p4/`.
- **Tier 3** on all five (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`;
  never `abm`, `pbf_preview`, `recruit_connect_20261023`): deploy-notes START/DONE + flock
  (wait if held); `pg_dump` ×5 first; rollback note before deploying; scoped rsync of only
  the modules you changed (never `pb_timeoff`); cron snapshot with the id→active list;
  asset purge; **no tests in the stopped window** (G19); hashes and versions ×5; suites on
  live `p0clone` after start on free ports.
- Live check: on a throwaway copy of `payobook` (jobs and mail servers off first, dropped
  afterwards): set, see on Time Off, undo. On live `payobook`, server-side as the QA user:
  download the sheet, review an unchanged sheet (0 to set), save and discard a draft —
  nothing written. Look-only in the browser. Never sign in to a live site with a password.
- Commit per feature with explicit paths, credential scan, push `origin 19.1`.
- Report `UPDATES_P4_REPORT.md`: L1–L14 with output; which databases/companies use the
  policy layer; what undo can and cannot do; deploy evidence ×5; deviations; new gotchas;
  ledger updated (phase map: P4 done; year-to-date listed as "design only, owner to decide").
