# UPDATES — Phase 3b handover: new joiners from a sheet, drafts, "since the last pay run"

Read first: `UPDATES_LEDGER.md` (all of it), `UPDATES_P3A_REPORT.md` (§R14 is this phase's
research — do not re-derive, do re-grep line numbers; §R12 deviations describe how lanes
really work), `UPDATES_P2C_REPORT.md` and `UPDATES_P2D_REPORT.md` for methods. Visual
reference: `docs/design/updates-desk-prototype.html`.

**Design mandate (owner, verbatim): "extreme WOW, intuitive, out-of-this-world experience,
best in class".** Indigo design system (`#5A4BB0`), white cards, Lucide icons, never emoji.

**White-label rule:** the word "Odoo" never appears in any user-visible string. Technical
identifiers stay. **Plain words on screen** — "new employee", "pay scheme", "team", "pay
run"; never model names, state keys or codes in a sentence a user reads.

## 1. Scope

1. **New joiners**: rows of a "Lasting changes" file that match nobody can be added as new
   employees, with their first contract, through the EXISTING new-hire path and its approval.
2. **Drafts**: an unfinished Updates file survives closing the browser.
3. **"Since the last pay run"**: pay-run preparation shows which people in the run had
   changes since their last finished pay run.

Versions: `pb_updates` → `19.0.1.5.0` (or the next minor after what is live); bump any
other module you change.

## 2. Binding non-goals and safety rails

- **No new way to create an employee.** Every new person goes through
  `pb.people.onboard.wizard.create_employee` and therefore through the company's new-hire
  approval, exactly as "Add employee" does. Never set `pb_newhire_approved_write`
  yourself; never create `hr.employee` / contract rows directly.
- **Opt-in, never automatic.** A row that matches nobody stays "matches nobody" unless the
  person ticks the add-as-new choice for this file. Default OFF, every file.
- **Never a duplicate person.** §3.2's checks refuse; they never merge and never guess.
- **Never touch the scheme map.** A "Pay scheme" column is a CHECK against the team; no map
  row, work segment or rule is created or changed.
- **Cap**: at most 200 new employees per file; more is refused before review with a sentence.
- **Undo never deletes or archives a person.** The new-employee part of an update is not
  undoable; the screen says so before applying and in Past updates.
- **A draft is private** to the person who made it (per-user record rule), holds no values
  that bypass review — resuming ALWAYS re-reads the file against today's records — and is
  never visible in Past updates. No scheduled job deletes drafts.
- **The pay-run line is information only**: never a blocker, never changes a figure, and a
  run's preparation with nothing to show is byte-identical to before (test H14).
- Lanes (P3a), start dates (P2c), off-scheme and CLEAR (P2b), one-offs (P2d) keep behaving
  exactly as today for existing people (all existing suites green).
- No timesheets, leave balances or year-to-date sheets (P4). No change to the approval
  engine. No change to the onboarding wizard's own behaviour for its own screen.
- Never apply anything on `rize` or `sudima`; do not create users, roles or people there.
- Do not touch `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`,
  `docs/handovers/workflow2`. If the work truly needs a change there, report it instead.

## 3. Design — new joiners

### 3.1 What the file needs

"Goes to" gains the destinations a new employee needs if not already offered: Name, Team
(department), Job title / job, Manager, Work email, Work phone, Country, Contract start
date, Contract end date, Wage, Working hours, Pay scheme (check only), Employee code.
Minimum for a row to be addable: **name + team (an existing one, by the P2a name ladder) +
contract start date**. Wage present → a contract is created with it; wage absent → the
person is created without a contract and the row says so ("No contract yet: no wage in the
file"). Teams, jobs and managers are never created from a new-joiner row: unknown → refused.

### 3.2 Checks (all refuse with a plain sentence, nothing is created)

- Same employee code, work email, or (name + team) as an existing employee — including
  archived ones — or as another new row in the same file → "looks like <existing name> who
  is already here" / "is in this file twice".
- A new-hire request already waiting for the same name + team (from this or another
  update) → "is already waiting for approval (<reference>)".
- Team not found / ambiguous (P2a sentences). Start date unreadable or more than 366 days
  away either side. Wage not a positive number.
- **Pay scheme column** (optional): the team's scheme, resolved the way a pay run resolves
  it (`pb.scheme.map` chain for that department — add a small read-only helper that
  resolves a DEPARTMENT without an employee; do not fake an employee), must equal the
  named scheme; else "<Team> is paid under <scheme>, not <named>. Change the team or the
  pay scheme column." A team no scheme covers → allowed with the amber note already used
  for people without a scheme.
- Contract overlap and other rails are whatever `create_employee` /
  `create_contract` return — surface their message on the row; errors are returned, not
  raised (P3a §R14.1), so check the answer.

### 3.3 What applying does

Per new row, as the proposer: call `create_employee(vals)` with `with_contract` when there
is a wage.
- **Created at once** ("No approval needed" route): set the employee code / clock code in a
  follow-up write if given (uniqueness refused → row note, person still created), then
  send the row's REMAINING cells (pay items, bank, other fields) through the normal lanes
  of the same batch — bank still needs its second person.
- **Pending**: keep the reference on a new per-row record
  (`pb.updates.joiner`: batch, row number, name, team, reference/proposal link, the row's
  remaining cells as JSON, state `waiting` / `created` / `turned_down` / `needs_attention`,
  `employee_id` once known). When the hire is approved and the person exists, the
  remaining cells are applied through the lanes as the original proposer. Find the hook
  where an approved new-hire proposal creates the employee (`newhire_approval.py`
  `:108-115` region) and continue from there with an override living in `pb_updates`; if
  no clean hook exists, do NOT patch the onboarding module's logic — instead show
  "Hired. N values from the sheet are still to apply" with an **Apply now** button on the
  batch (and on the Updates home), which re-reads the stored cells against today's record.
  Report which you built. Turned down → row `turned_down`, nothing else happens.
- One proposal per person (that is how the path works); the Apply step says how many
  hire requests will be sent and to whom.

### 3.4 Screens

- **Review**: the existing "matches nobody" section gains a clear choice card: "Add these
  N people as new employees" (toggle, default off) with what it means in one line. When
  on, those rows join the grid in a "New employees" group with a `user-plus` icon, their
  cells judged by §3.2 (refusals fixable on screen like any other cell), and rows that
  cannot be added stay under "matches nobody" with the reason.
- **Apply step**: a fourth card beside the lanes — "New employees · N · each goes to <who>
  as a new-hire request" or "· are added now" — and the not-undoable sentence.
- **Done / Past updates / home**: per-person state (waiting for approval <reference> /
  added / turned down / hired, values still to apply). A "New employees waiting" line on
  the home card that already lists waiting things.
- **Download sheet**: Start gains a third template under Lasting changes: "Blank sheet for
  new employees" — headings only (the §3.1 columns + the pay items of the chosen pay
  scheme's teams), with the "Read me" sheet explaining the minimum columns.

## 4. Design — drafts

On `pb.updates.batch`: stored `state` gains `draft` (do not break `_batch_state`, which
derives the rest from the applies — an apply-less NON-draft batch must read as today);
`draft_columns` (JSON: the column choice `_clean_columns` reads), `draft_choices` (JSON:
on-screen fixes, start date, hold scope, add-as-new toggle, kind, month, step reached),
`draft_saved_at`. Per-user rule `['|', ('state','!=','draft'), ('user_id','=',user.id)]`;
discard through a model method (owner or Records manager), not a general unlink right.

- Saved automatically when a file is read (after Match the first time) and on every step
  change and fix (debounced; one RPC `save_draft`), for both kinds of sheet. No draft
  before a file is chosen.
- Home: a "Continue where you left off" strip — file name, kind, step reached, "saved 2
  hours ago", **Continue** and **Discard** (confirm). At most the 5 newest; older ones
  under "More drafts".
- Continue: reopens at the step reached, re-running read/review against today's records;
  on-screen fixes are re-applied where the cell still exists; anything that no longer fits
  (a person since archived, a column no longer offered) is listed in one calm notice.
- Applying a draft turns the SAME batch into the real one (no second batch, the file
  attachment is kept once). `get_history` and every count skip drafts.
- A draft older than 30 days shows "saved N days ago" in amber; nothing is deleted
  automatically.

## 5. Design — "since the last pay run"

Extend the pay-run preparation workspace the way `pb_records/models/records_payrun.py`
adds `scheduled_changes` (same mechanism, living in `pb_updates`): for the people in the
run, since each person's last FINISHED payslip (`state='done'`, max `date_to`; a person
never paid → since their contract start):

| Source | Shown as |
|---|---|
| Written changes (`pb.records.change` on applied, not-undone applies; company through the apply) | "<Label>: <old> → <new>, <date>, by <who>" grouped pay / contract / bank / details (bank masked to the last 4 characters) |
| One-offs for this run's month (waiting for approval, approved, in this run) | "<Item> <amount> for <month> · <state>" |
| Scheduled changes starting on or before the period end | the P2c sentence |
| Pay-item history from OTHER sources than a Records/Updates write (de-duplicate against the first row by person, code and date) | "<Item>: <old> → <new>, <date> (changed on the contract)" |
| New employees added since the last finished run of this scheme | "New: <name>, starts <date>" |

Screen: one line on the preparation — "Since the last pay run: 14 people have changes
(9 pay, 3 bank, 2 new)" — opening a side panel: search, filter chips by kind, one
collapsible block per person, "Download as a sheet". Zero → the line is not shown at all.
Budget: ≤ 1.5 s added on a 4,575-person run (grouped queries only; no per-person search).
Covers every run mode's preparation surface that already shows the scheduled-changes
notice; where a mode has no such surface, report it rather than inventing one.

## 6. Tests (numbered)

| # | Case | Expect |
|---|---|---|
| H1 | Toggle off | rows that match nobody behave exactly as before this phase |
| H2 | Toggle on, no-approval route, row with wage + pay item + bank cells | person + contract created via the wizard; pay item through its lane; bank waits for a second person |
| H3 | Toggle on, new-hire approval route | nothing created; reference kept; on approval the person exists and the remaining cells follow (hook) or "Apply now" finishes them; turned down → nothing |
| H4 | Duplicates: existing code / email / name+team (active and archived), twice in file, already waiting | each refused with its sentence; nothing created |
| H5 | Unknown team, job, manager; bad date; bad wage | refused; no team/job/person created |
| H6 | Pay scheme column: matches the team's scheme / differs / team with no scheme | ok / refused with the sentence / ok with the note; scheme map untouched (row counts before = after) |
| H7 | No wage | person without contract, row says so |
| H8 | 201 new rows | refused before review |
| H9 | Undo on a batch with new employees | changes to existing people undone; new people stay; the sentence shown |
| H10 | Direct RPC trying to create a person without the wizard path or with the approved-write context key | impossible / refused |
| H11 | Draft: save, close, another user cannot see it, owner continues at the same step with fixes kept; a person archived meanwhile is listed in the notice | as stated |
| H12 | Draft applied → one batch, one attachment; discard removes it; Past updates and counts never show drafts; an apply-less non-draft batch reads as before | as stated |
| H13 | Since-last-run: each of the five sources, de-duplication, bank masking, undone change not shown, person never paid | as designed |
| H14 | Preparation with nothing to show; speed on a 4,575-person run | byte-identical payload to before; ≤ 1.5 s added |
| H15 | Lanes, dates, off-scheme, CLEAR, one-offs for existing people | all existing suites green; review 4,575 × 73 ≤ 25 s |
| H16 | `.po` parse gate; "Odoo" scan of new strings | clean |

Demo fixtures: reuse the persistent demo schemes; new test people are named "DEMO …"; no
"ZZ", no "RIZE".

## 7. Browser validation, deploy, report

- Browser (local copy, console read at every step, the people's company — G22): a file with
  existing people and three new ones through review, apply, approval as a second user, the
  per-person states; the blank new-employee sheet; a draft closed and continued; the
  since-last-run line and panel on a pay run. Screenshots to `outputs/updates-p3b/`.
- **Tier 3** on all five (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`;
  never `abm`, `pbf_preview`, `recruit_connect_20261023`): deploy-notes START/DONE + flock
  (wait if another session holds it); `pg_dump` of all five first; rollback note before
  deploying; scoped per-module rsync of only the modules you changed; cron snapshot with
  the id→active list (expect no new job); asset purge; **no tests in the stopped window**
  (G19); hashes and versions on all five; suites on live `p0clone` after start on free ports.
- Live check: adding a person cannot be undone and demo data is never deleted, so the
  new-joiner write is checked ONLY on a throwaway copy of `payobook` with scheduled jobs
  and mail servers switched off first (memory note `copy-db-runs-live-crons`), dropped
  afterwards. On live `payobook`, server-side as the QA user: a draft saved, continued and
  discarded; a file with one unknown row and the toggle OFF behaves as before; the
  since-last-run payload for an existing demo run is read (look only). Look-only in the
  browser on `payobook`. Never sign in to a live site with a password.
- Commit per feature with explicit paths, credential scan, push `origin 19.1`.
- Report `UPDATES_P3B_REPORT.md`: H1–H16 with output; hook or "Apply now" and why; deploy
  evidence ×5; deviations; new gotchas; ledger updated. For P4, from the code with
  file:line: (1) how attendance / timesheet rows are imported today (every screen and
  model, what `pb_clock` and the timesheet approval expect, what a pay run reads);
  (2) where leave balances are stored and how an opening balance is set today;
  (3) whether year-to-date pay figures can be loaded for a mid-year start, and what reads them.
