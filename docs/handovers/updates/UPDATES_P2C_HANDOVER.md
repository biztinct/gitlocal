# UPDATES — Phase 2c handover: start dates, scheduled changes, cancel, employee look-ups

Read first: `UPDATES_LEDGER.md` (rules, decisions D1–D10, facts U1–U18, gotchas G1–G24),
`UPDATES_P2A_REPORT.md` §R7 and `UPDATES_P2B_REPORT.md` §R7 (items 3 and 4 are this phase's
foundation). Visual reference: `docs/design/updates-desk-prototype.html`.

**Design mandate (owner, verbatim): "extreme WOW, intuitive, out-of-this-world experience,
best in class".** Indigo design system (`#5A4BB0`), white cards, Lucide icons (never emoji,
no gradients), one solid primary button per bar.

**White-label rule:** the word "Odoo" never appears in any user-visible string (labels,
tooltips, toasts, errors, `string=`, `help=`, selection labels, cron names a user can see,
exported sheet text, `.po` msgstr). Technical identifiers stay as they are. **Plain words on
screen** — "pay scheme", "pay item", "pay run", "starts on"; never a model name, a state key
or a rule code in a sentence a user reads.

This is the first phase that changes the Records Desk's WRITE side. Read §2 twice.

## 1. Scope

1. **A change can carry a start date** — today (default), a past date, or a future date.
2. **Future-dated changes are held** ("Scheduled") and written on the day by a scheduled job.
3. **A real cancel** for a change that has not been written yet (waiting for approval or
   scheduled) — and the fix for today's defect where "undo" on an unwritten change marks it
   undone but it is still written later (P2b report §R7.3).
4. **Pay run awareness**: a pay run's preparation mentions a scheduled change only when it
   starts inside that run's pay period.
5. **Employee look-ups** (owner decision D9): a manager / coach column accepts an employee
   code or a work email as well as a name; a name that matches nobody is refused, never
   created; namesakes stay refused (P2a) but the sentence now tells the person what to type.

One-off pay items for a named pay month are **NOT** in this phase (now P2d; research is
running separately).

Versions: `pb_records` `19.0.1.8.6` → `19.0.1.9.0`; `pb_updates` `19.0.1.1.0` → `19.0.1.2.0`;
`pb_hr_payroll_formula` patch bump only if item 4 changes a file there.

## 2. Binding non-goals and safety rails

- **No retro pay, no proration.** The pay run reads a pay item's CURRENT amount only (U14);
  proration and automatic back pay are off on every scheme (P2b §R7.4). A past start date
  is a RECORD of when the change started, nothing more — the screen says so. Do not switch
  on, call or extend proration/back pay.
- **No change to what "today" does.** A change with no date, or today's date, takes exactly
  the path it takes now: same evaluation, same approval route, same writes, same audit
  rows, same undo. P2a's golden comparison and every existing test stay green.
- **The Records screen** gains nothing visible except: (a) the cancel fix of item 3 where it
  already offers undo on an unwritten change, and (b) item 5's look-up rules. No date
  picker there in this phase.
- **All or none stays.** A scheduled change is written by the same `_write_plan`, after the
  same `_plan_moved_since` check, in one transaction. No partial writes, no second engine.
- **The scheduled job never guesses.** If anything moved since the proposal, nothing is
  written, the change is marked sent back with the existing sentence, and the requester is
  told (§4.4). It never retries silently and never writes a subset.
- **Never write early by itself.** Only a person pressing "Start now" writes before the date.
- No one-offs, no approval split, no new joiners, no drafts, no "Pay scheme" column.
- Do not touch sudima's two existing unwritten changes, or any stored row on `rize`/`sudima`.
- Do not touch `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`,
  `docs/handovers/workflow2`.

## 3. Verified plumbing facts (do not re-derive)

- `pb.records.apply` approval adapter: `pb_records/models/records_approval.py`. State
  selection `:59-65` (`draft`, `pending`, `applied`, `returned`, `rejected`); `applied`
  boolean `:51`; `_approval_apply` `:323` = moved-since check (`Desk._plan_moved_since`,
  `pb_records_desk.py` ~`:1771`) → `Desk._write_plan(self)` (~`:1797`) → marks applied
  `:343-347`. With "no approval needed" the same method runs inside `apply_changes` →
  `biz.approval.engine.submit` (`biz_approval_workflow/models/engine.py:842`; the engine
  calls `_approval_apply` at `:1117`).
- Every place that switches on the state or on `applied` is listed in P2b report §R7.3
  (records_approval.py, records_learn.py, pb_records_desk.py apply answer / undo row /
  history, `pb_updates/models/updates_desk.py` `_batch_state` / `_batch_row` / `undo`,
  `pb_hr_payroll_formula/models/payroll_preparation.py:211-214` and `:551-553`, the Records
  History template and toast, the Updates Past-updates template and tone/icon maps,
  `pb_payrun_wizard/static/src/js/payroll_review.js:332-333`). Re-grep; line numbers moved.
- `undo_apply` (`pb_records_desk.py` ~`:1937`) never checks `applied`: on an unwritten
  change it makes an empty undo row, marks the source `undone`, returns ok — and
  `_approval_apply` ignores `undone`, so the change is still written on approval.
- `_component_log` stamps `effective_date = today` on `hr.contract.advantage.change`
  (`pb_records_desk.py` ~`:1701`). That date is read only by history screens and by
  proration / back pay (off everywhere) (U15).
- Updates reaches the desk through `pb.updates.desk._desk()` with the door context (U17);
  an apply linked to an Updates batch reopens the same context at approval and undo. The
  scheduled job and "Start now" must reopen it the same way.
- A typed many2one goes through `_m2o_ladder` (`pb_records_desk.py` ~`:1158-1215`): current
  value → scoped exact match → full path → one hit / namesakes refused → nothing:
  `m2o_creates_missing(comodel)` decides between refuse and `{'create': text}`; `hr.employee`
  creates today (G17).
- Row matching for the PERSON of a row already has a code → work email → name ladder
  (U5, `pb_records/models/pb_records_io.py:90,542-623`) — reuse its code fields
  (`barcode`, `employee_id`, `pb_source_ref`, `identification_id`) for item 5.

## 4. Design

### 4.1 Data (`pb_records`)

On `pb.records.apply`:
- `start_date` (Date, readonly, copy=False): empty = "today, as before".
- `hold_scope` (Selection `pay` / `all`, default `pay`): what waits for a future date.
- two new states: `scheduled` ("Scheduled") and `cancelled` ("Cancelled").
- `started_by_job` (Boolean, readonly) for the audit line "started automatically".

On the desk's audit row model (`pb.records.change`) and on the component history stamp:
- `effective_date` (Date). `_log` and `_component_log` use the apply's `start_date` when it
  is set, else today (unchanged behaviour). An undo stamps today.

`apply_changes` gains optional keywords `start_date=None`, `hold_scope='pay'`
(backward compatible; `source` rules unchanged). Bounds: not more than 366 days back or
ahead, else refused in a sentence.

### 4.2 The three cases

| Start date | What happens |
|---|---|
| empty / today | Exactly today's path. |
| past | Exactly today's path (written now, after approval if routed), history stamped with the past date. |
| future | Proposal and approval as today. At the moment `_approval_apply` would write: if `start_date` > today (the company's date, see §4.4) → set `state = 'scheduled'`, write nothing, return True. |

"Dated" columns are the `contract` and `component` groups. With `hold_scope='pay'`
(default) Updates sends the `employee`- and `bank`-group changes of a future-dated file as
a separate, undated apply in the same batch (written now, own approval route as today), and
the dated groups as the scheduled apply. With `hold_scope='all'` everything is in the
scheduled apply. For past dates there is no split (one apply, stamped).

Per-row dates: Updates groups the changes by their start date and makes one apply per
distinct FUTURE date; all today/past changes go in one apply per distinct past date plus
one undated. Cap: at most 6 distinct dates in one file — more is refused before review with
"This file has N different start dates. Split it into files of at most 6." (keeps approvals
readable).

### 4.3 Writing on the day, starting early, cancelling

- `PbRecordsApply._start_scheduled()` — shared by the job and by "Start now": reopen the
  door context when the apply belongs to an Updates batch; run as the proposer
  (`with_user(create_uid)`, falling back to the approver if that user is archived) so audit
  rows name a person, with `started_by_job` marking the automatic case; moved-since check;
  `_write_plan`; mark applied. On a moved-since conflict: state `returned`, `block_note` with
  the existing sentence, notify (below). Any other exception: roll back that apply only,
  keep it `scheduled`, log with traceback, write a `block_note` "Could not be started on
  <date>; it will be tried again", and continue with the next apply (one bad row never
  stops the rest). After 3 failed days → `returned` + notify.
- **Job**: `ir.cron`, hourly, `noupdate`, name "Records: start scheduled changes". Each run
  takes applies with `state='scheduled'` and `start_date <= today in the apply's company
  time zone` (company partner tz → the proposer's tz → UTC), oldest first, commits per
  apply. Idempotent: `applied` is checked under `FOR UPDATE SKIP LOCKED` (or equivalent
  row lock) so "Start now" and the job can never both write.
- **Start now** (`start_now(apply_id)`): same gate as applying; needs the same write rights;
  stamps `effective_date = today` (it really started today) and keeps `start_date` for the
  record.
- **Cancel** (`cancel_apply(apply_id)`): allowed while not `applied` and state in
  `pending` / `scheduled` / `returned`; allowed for the proposer, an approver on the route,
  or a Records manager. Sets `cancelled`, and withdraws the open approval request through
  the approval engine's own public method (find it in `biz_approval_workflow/models/engine.py`;
  if none exists, add the smallest adapter hook and report it). `_approval_apply` and
  `_start_scheduled` refuse a `cancelled` or `undone` apply — this is the defect fix.
  `undo_apply` on an unwritten apply now routes to `cancel_apply` and answers honestly
  ("Cancelled before anything was changed"), never an empty undo.
- **Notify**: an activity on the apply for the proposer (no email; the apex database's
  outgoing mail must not be relied on — memory note `payobook-demo-mail-spam`), plus the
  state visible on the Updates home (below).

### 4.4 Pay run awareness (`pb_hr_payroll_formula/models/payroll_preparation.py`)

Today `:211-214` and `:551-553` treat unwritten applies as "waiting". Rule for `scheduled`:
- `start_date` <= the run's period end and the apply touches somebody in the run → listed,
  with its own sentence: "N scheduled change(s) start on <date>, inside this pay period.
  They are not in this pay run unless you start them now." Never a blocker.
- `start_date` after the period end → not mentioned at all.
- `cancelled` → never mentioned.
Read both sites first and report what each does today before changing them; keep the change
minimal, and keep `pending` behaviour identical.

### 4.5 Employee look-ups (decision D9; `pb_records`, both doors)

In `_m2o_ladder`, when the comodel is `hr.employee`:
1. current value (unchanged);
2. **code**: exact, case-insensitive match across the same code fields the row matcher
   uses → one hit wins; two hits → refused;
3. **work email**: exact, case-insensitive → one hit wins;
4. name (unchanged scoped exact match); namesakes refused with a new sentence:
   "N people are called '<name>'. Type the employee code or work email of the right one
   instead." (the Records-screen sentence keeps its "Pick the right one…" ending when the
   call did not come from a file — pass the distinction, do not guess);
5. nothing → refused: "Nobody is called '<value>'. Check the spelling, or use their
   employee code or work email." **Never `{'create': …}` for `hr.employee`.**
Company scope as P2a. Memo per `_evaluate` as P2a. The download sheet's "Read me" sheet
gains one line saying a manager can be given by name, employee code or work email.

### 4.6 Screens (`pb_updates`)

- **Match columns**: a new destination, first in the "Goes to" list under its own group
  "When it starts": "Start date for this row". At most one column. Values: real spreadsheet
  dates, ISO `2026-12-01`, and day-first / month-first text according to the user's
  language date format; an unreadable date refuses that row's dated cells with
  "'<value>' is not a date. Use a date like 1 Dec 2026." A blank cell = the file's default.
- **Review**: when any row has a date, or a default date is chosen (below), a slim pinned
  "Starts" column after the person: "Today" (muted), a past date with a Lucide `history`
  icon (amber, tooltip: "Recorded as starting on <date>. Pay runs already finished are not
  recalculated."), a future date with `calendar-clock` (indigo). Filter chips "Starts
  later · N" and "Dated in the past · N" next to the existing ones.
- **Apply step**: a card "When do these changes start?" — segmented control: **Today**
  (default) / **Pick a date** (date field, bounds from §4.1); it is the default for rows
  without their own date. When a future date is in play, a two-option choice:
  "Pay and contract changes wait; personal details change today" (default) /
  "Everything waits until that date". Under it a live plain summary, e.g. "38 values
  change today · 12 are scheduled for 1 Dec 2026 · 4 are recorded as starting 1 Oct 2026".
  When a past date is in play and any of those people has a finished payslip ending on or
  after it: an amber note "N of these people have already been paid for a period after
  this date. Finished pay runs are not recalculated, and back pay is not added
  automatically." (one grouped query on finished payslips). The primary button reads
  "Apply" / "Schedule" / "Apply and schedule" to match.
- **Done**: says what was written now and what is scheduled, with the dates.
- **Home**: a "Coming up" card listing scheduled updates (name, date, people, values) with
  **Start now** and **Cancel** (both confirm in a small dialog that says exactly what will
  happen); empty state hidden. "Past updates" rows gain the states "Scheduled for <date>",
  "Cancelled", "Sent back: <reason>", and mixed batches read "Part applied, part scheduled
  for <date>". Undo on a batch with a scheduled part offers "Cancel the scheduled part" and
  "Undo what was applied" as separate actions.
- Records screen history: the two new states render with sensible tone/icon and "Cancel"
  where "Undo" would have hit the defect.
- Vietnamese translations for every new string (parse gate G2, extractor rule G6).

## 5. Tests (numbered)

| # | Case | Expect |
|---|---|---|
| C1 | Apply with no date, and with today's date | byte-identical writes/audit to before this phase (P2a golden + existing suites green) |
| C2 | Past date, pay item + wage | written now; component history and audit rows carry the past date; undo restores, stamped today |
| C3 | Future date, no approval route | state `scheduled`, nothing written, `applied` false |
| C4 | Future date with an approval route | pending → approve → `scheduled`, nothing written |
| C5 | Job on the day (freeze the date) | written, `applied`, `started_by_job`, audit names the proposer, effective date = start date |
| C6 | Job before the day; job in a company whose time zone is ahead of / behind UTC around midnight | not written before the company's date; written once it is |
| C7 | Value changed by somebody else between scheduling and the day | nothing written; `returned` with the sentence; activity for the proposer |
| C8 | Job hits an exception on one apply of two | the other is written; the failed one stays scheduled with a note; third failed day → `returned` |
| C9 | Start now | written today, effective date today, job later does nothing |
| C10 | Start now and the job at the same moment (two cursors) | exactly one write |
| C11 | Cancel a scheduled apply; cancel a pending one | `cancelled`; approval request withdrawn; a later approve / job writes nothing |
| C12 | `undo_apply` on an unwritten apply (the defect) | routed to cancel; never written afterwards |
| C13 | `hold_scope='pay'` with employee + contract + pay-item columns, future date | employee values written now in their own apply; the rest scheduled; `all` → everything scheduled |
| C14 | Per-row dates: 3 distinct dates → 3 applies in one batch; 7 distinct dates → refused sentence | as stated |
| C15 | Unreadable date in the start-date column; date beyond 366 days | row's dated cells refused / apply refused, with the sentences |
| C16 | Pay run preparation: scheduled inside the period, after the period, cancelled; pending unchanged | listed with the sentence / not mentioned / not mentioned / identical to before |
| C17 | Manager by code, by work email, by unique name; namesakes; nobody; `hr.employee` never created | per §4.5 |
| C18 | Records screen: `get_fields`, grid apply, its own import | unchanged except §4.5 and the cancel fix (capture before, compare after) |
| C19 | Off-scheme and CLEAR (P2b) on a scheduled apply, checked again on the day | dropped / applied exactly as when proposed; door context reopened |
| C20 | Full suites + speed | `pb_records` and `pb_updates` all green; review on 4,575 × 73 still ≤ 25 s |
| C21 | `.po` parse gate; scan new user-visible strings for "Odoo" | clean |

## 6. Browser validation (mandatory)

Local copy, Chrome tools with the console read at every step (G20: do not kill another
session's browser): match with a start-date column; review with the Starts column and
chips; the apply card in all three states with the live summary and the amber note;
schedule; home "Coming up"; Start now; Cancel; Past updates states; mixed batch undo
choices; Records screen history showing a scheduled and a cancelled change. Work in the
company the people belong to (G22). Screenshots to `outputs/updates-p2c/` (never committed).

## 7. Deploy and live check

**Tier 3** (new stored fields, new states, a new scheduled job) on all five: `payobook`,
`payobook_template`, `p0clone`, `rize`, `sudima`. Never `abm`, `pbf_preview`,
`recruit_connect_20261023`.

1. `/opt/deploy-notes.md`: read, wait on anyone's open START, append START, take the flock
   `/tmp/payobook-studio-deploy.lock`.
2. Back up all five databases first (`pg_dump -Fc` to the server's backup area, names with
   `pre-updates-p2c`; confirm sizes; keep the nightly ones untouched).
3. Clean staging; dry-run rsync of the changed modules — only this phase's differences may
   show; per-module scoped `rsync -a --delete`; never `--delete` into the addons root.
4. Cron snapshot before (counts and the id→active list, memory note
   `cron-snapshot-boolean-trap`). Stop; upgrade on all five; **expected cron change: +1 per
   database (the new job), and nothing else newly active** — switch off anything else that
   re-activated. Leave the new job active on all five (it does nothing while no change is
   scheduled). Asset purge per database; start. **No tests inside the stopped window** (G19).
5. Warm each site; grep the log; byte-identical hashes; manifest version ==
   `latest_version` on all five; confirm the job exists once per database and its next run.
6. Live check on `payobook`, server-side as the QA user (never sign in to a live site with a
   password), DEMO people in Payobook Vietnam JSC: (a) past-dated pay item change → applied,
   history shows the date → undo → proven restored; (b) future-dated change → scheduled →
   run the job method by hand: nothing written → **Cancel** → run it again: nothing written;
   (c) a second future-dated change → **Start now** → written → undo → proven restored.
   Leave nothing scheduled and nothing changed. Then look-only in the browser through the
   existing session on `payobook` and `sudima`: Updates opens, Past updates shows the check,
   console clean. Never apply or schedule anything on `rize` or `sudima`.
7. Run the suites on live `p0clone` after start, on free ports.
8. Append DONE/FAILED to the deploy notes with the downtime. Commit per feature with
   explicit paths (handover, ledger, report included), credential scan, push `origin 19.1`.
   The QA password appears nowhere in the repo, the report, a commit message or the notes.

Rollback (write it in the report before deploying): module files from git at the previous
commit + the five dumps; the new columns are additive, so files-only rollback is safe as
long as no apply is in `scheduled`/`cancelled` state.

Usage-limit rule: on a 429 or at 97 %, commit work in progress with a `PAUSED` section in
the report and stop cleanly.

## 8. Report back — `UPDATES_P2C_REPORT.md`

- C1–C21 with output; timings; screenshot list.
- What the two pay-run preparation sites did before and do now.
- Which engine method withdraws a request (or the hook you added).
- Deploy evidence ×5, cron lists, backups, downtime, rollback note; the live check with
  proof of restoration.
- Deviations and why; new gotchas into the ledger; the P2c row in the phase map updated.
- For Phase 3 (from the code, file:line): (1) how the approval engine could route ONE
  proposal's bank changes to a second person while its pay changes follow the pay route —
  does `pb.records.apply` already split by `touches_bank` / `touches_salary`, and where are
  routes chosen; (2) what creating an employee + first contract from a row needs at minimum
  (required fields per company, what `pb_people` / the old employee import do today, and
  which screen the old import lives on); (3) where the pay run's pay data file writes
  lasting values today (every write to employee / contract / pay-item lines from the
  pay-file path), so D1 "month-only" can be enforced.
