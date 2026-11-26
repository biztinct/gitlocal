# PSCHEME — ledger (standing rules, owner rulings, architect decisions, gotchas)

Programme: **the pay scheme belongs to the person.** Started 2026-11-26. Every handover of this programme references
this file. Builders append gotchas (PS1, PS2 …) in §4 the moment they are hit. Engineering document: real technical
names on purpose. No credentials, client names or client data.

Facts: `PSCHEME_FACTS.md` (study at `8eb27c95e`, every file:line is from that HEAD — **do not re-derive**; re-check a
line only if the code under it moved).

## 0. Standing rules (all phases)
1. Worktree `gitlocal-worktrees/pscheme`, branch `pscheme` from `origin/19.1`. Never the shared checkout. Feature-scoped
   commits; push only when a handover says so. Scan every commit for passwords. Public repo: no client names / data.
2. **White-label**: the word "Odoo" never appears in a user-visible string (labels, help, toasts, selection labels,
   reports, `.po` msgstr). Technical identifiers are left alone.
3. **Plain screen words** on every label, toast and sentence: "pay scheme", "pay run", "Country of work", "team",
   "mid-month advance". Never "rung", "config", "cycle type", "resolver" on screen.
4. **Design mandate (verbatim, binding): "extreme WOW, intuitive, out-of-this-world experience, best in class."**
   Every surface names a hero moment; zero dead-ends (empty, loading, error, partial, huge all designed; every failure
   names its reason and next step); motion with purpose; keyboard + bulk ergonomics where rows are involved; Lucide /
   SVG icons, never emoji; locked Payobook palette, no gradients; measured against the best SaaS tool in the category.
   The phase report scores itself against this bar.
5. Every new user-visible string ships in `vi_VN` and `id_ID` (PO loading rules: three things an entry needs; parse
   gate; a translation fix is two fixes — the .po AND the stored value).
6. Browser validation is mandatory (Chrome MCP, console read) before a screen is called done. Test boards inside their
   hub. Demo fixtures: reuse the persistent demo schemes; prefix DEMO; never "RIZE" in a demo record.
7. Lessons, tours and replicas follow screen changes (inventory in FACTS §10.2) — done in the phase that changes the
   screen or explicitly deferred to the named later phase.
8. Whatever is done from the backend must also be doable on screen.
9. Dependency rail: `pb_hr_payroll_formula` and `pb_payrun_wizard` never depend on `pb_scheme_map`
   (`test_t12_the_ladder_edit_is_guarded`); reach it through `'pb.scheme.map' in self.env` soft probes.
10. Release (only in the phase that says so): read `/opt/deploy-notes.md` first, START/DONE lines, risky tier ritual
    (this programme touches pay-run population), ONE addons directory, the four + sudima databases, never abm, clean
    staging, per-module scoped rsync, asset purge, hash + version verification. Tell the other sessions before a stop.
11. **No pay run or payslip is in production** (owner, 2026-11-26): do not spend effort keeping past runs / payslips
    unchanged or re-reading them. Build and test for pay runs created from now on. Backups before a release still apply.
12. Demo data on payobook is kept; seeds only add. `pb_demo` runs bypass the map (FACTS T9) — do not "fix" that.

## 1. Owner rulings (binding)
- R1. The pay scheme is stored on the PERSON with a start date. Pre-filled from **Country of work** (never the work
  site). HR may pick another scheme of that country. The pay run follows the person's own scheme.
- R2. Team lines on Mapping stay only as (a) a bulk shortcut and (b) the fallback for people with no scheme of their own.
- R3. Existing people are filled once: the scheme that pays them today, else from Country of work; review list; undo.
- R4. A Country of work change makes the screen ask to change the pay scheme from a date.
- R5. Split work: two sites in one country = one scheme (cost split only). Short trip = home scheme. Permanent move =
  dated change. Ongoing two-country split = LATER (second contract) — out of scope for this programme.
- R6. **Mid-month change: the old scheme pays that whole month; the new one starts with the next pay period. One
  payslip per person per period, always.** A new joiner's first scheme counts from their first month.
- R7. **No advance from the team**: a person with their own pay scheme gets a mid-month advance only if they were
  given one themselves.
- R8. "Set this pay scheme for everyone in this team" fills only people without a scheme of their own; moving people
  who already have one is a separate, unticked-by-default tick with a start date.
- R9. Who changes it: HR asks, a payroll manager approves — the same route as Mapping changes today
  (`pb.schememap.proposal`, process `schememap`); saved at once where no second approver is set up (fast lane).
- R10 (owner, 2026-11-26 evening). **No lesson updates in this programme.** `pb_learn` lessons, tours and replicas are
  NOT updated in P3 (this overrides ledger §0.7 and A10 for this programme only). The untrue lesson sentences listed
  in the phase reports go into the closeout as a known open item.

## 2. Architect decisions (made — do not reopen without a report)
- A1. **Storage**: new model `pb.person.scheme` in `pb_scheme_map`, cloned from `pb.division.link` (FACTS §4 option a).
  One row per scheme the person is on; the kind of run is DERIVED (`cycle_type` related to `config_id.cycle_type`,
  stored). An advance person has two rows. No `full_final` rows.
- A2. **Rung**: key `'person'`, between `'segment'` and `'department'`:
  `RUNGS = ('segment', 'person', 'department', 'division', 'rule', 'only', 'none')`.
- A3. **The person rung is authoritative once a person has any active row** (any kind, any date): for an asked kind it
  answers its row or `none` — it never falls through to team / division / rule / only. The single exception is
  `full_final`, which always falls through to the rest of the ladder. A person with NO active row at all falls through
  exactly as today (so a database with no rows behaves byte-for-byte as before).
- A4. **Which row counts on date D** (implements R6 without storing false dates): per kind, the row in force on D
  (`date_from <= D` and (`date_to` empty or `>= D`)); if none is in force AND the person has no earlier row of that
  kind (nothing with `date_from < D`), the EARLIEST row of that kind (their first-ever scheme counts backwards, so a
  joiner hired on the 15th is found by a run judged on the 1st); otherwise no row of that kind. The pay run keeps
  judging on the period's first day (`on_date=date_start`), so a change dated mid-period leaves the old scheme paying
  that period.
- A5. `'any'` asked: `_pick` order over the person's counting rows (`end_cycle`, `regular`, `full_final`, `mid_cycle`).
- A6. One constant for the advance allow-list in `pb_scheme_map` (`ADVANCE_RUNGS`, includes `'person'`); the copy in
  `pb_hr_payroll_formula/models/scheme_component_scope.py` stays a literal (dependency rail) and a test asserts it
  equals the constant.
- A7. The server never changes a scheme because a country changed; screens ask first (R4). A `payroll_country` write
  only marks "Paid by" to be worked out again.
- A8. Country of work stays undated (FACTS D5). Demo people are filled like everyone else (D6).
- A9. A scheme on a person row must belong to the person's company or be shared; a job change to another company ends
  the old row the day before and starts a row for the new company's scheme (D8, built in the phase that touches
  `pb_job_change`).
- A10. Phases: **P1** engine + Add employee + the person's "Pay scheme" panel and change dialog (local, no release) ·
  **P2** Mapping re-wording and "Set for everyone in this team", the one-time fill tool, Country of work prompt, job
  change, Updates sheets, hiring-offer default, pay-data-file joiners, contract currency / usual answers on a scheme
  change (local) · **P3** lessons, vi/id completion, release ×5, the fill on each database, closeout.
- A11 (after P1, confirms PS4). **A4 tightened**: only the person's FIRST-EVER pay scheme (no earlier row of ANY main
  kind) counts backwards. A later row of a new kind never does, so a mid-month move between a regular and an
  end-of-month scheme leaves the old scheme paying that month (R6: never two runs in one month).
- A12 (after P1, confirms PS5). The "main question" flag (`MAIN_QUESTION`) is accepted: "who pays this person" screens
  accept either main kind; pay runs never use it.
- A13. The fill and every later writer copy a mid-month advance ONLY when the scheme is really of kind `mid_cycle`
  (PS6). A team line "for any kind of run" never becomes someone's advance. No owner question: it was a display
  artefact, nobody was ever paid an advance by it.
- A14. A person whose pay scheme's country differs from their Country of work is never changed silently: every screen
  that shows the pay scheme says so in one amber line with "Change pay scheme" (the universal net behind R4, covering
  imports and sheets that write Country of work without a screen prompt).
- A15. P2 is built as two parallel streams from `pscheme` HEAD: **P2a** (branch `pscheme-p2a`: Mapping, team button,
  fill tool, Country of work prompt, contract follows the scheme) and **P2b** (branch `pscheme-p2b`: job change,
  Updates sheets, hiring-offer default, pay-data-file joiners). P2b may ADD files / methods to `pb_scheme_map` but
  never edits a line P1 wrote there except `__init__`, the manifest and i18n; P3 merges both.

## 3. Open (owner)
- none

## 4. Gotchas (append as hit)
- PS0. Inherited: FACTS §12.1 T1–T13 are live traps for every phase — read them before coding.
- PS1. The proposal mixin's generic `_proposal_moved` prints snapshot KEYS to the user ("12 (was [...], now [...])").
  A `person_set` snapshot keyed by employee id gets its own `_proposal_moved` naming the person in plain words
  (board `_person_moved_words`) — never a raw id on screen (coordinator ruling).
- PS2. Fast lane + a proposer without the carry-out group: the engine catches the gate error, the request becomes
  "approved" with `block_reason`, and `answer_message()` says "Sent for approval." — false. `person_set` refuses up
  front with a plain sentence (`_person_blocked`), and the screen hides the button with that reason.
- PS3. `hr.formula.config.cycle_type` selection labels are "Mid-Cycle" / "End-Cycle" ("cycle" on screen). Screens use
  `pb.scheme.map.cycle_words` ("mid-month advance", "end-of-month", "regular payroll").
- PS4. Ledger A4 read per kind of run double-counts: a later row of a NEW kind (regular -> end of month on the 15th,
  or an advance added later) "counted backwards" too, so the person sat in two runs of one month (R6 broken). Built:
  only the FIRST-EVER scheme counts backwards — while nothing of the person's has started on or before the day, and
  only for rows starting on their first-ever start date (`_person_rows_for`, test T16b). Joiners still land (T3).
- PS5. "Paid by" asks the company's main kind (`_pb_main_cycle`: end of month where one exists). A person whose own
  scheme is a REGULAR one then read "no pay scheme". `MAIN_QUESTION` context (`pb_scheme_main_question`) lets the
  "who pays this person" readers (recompute, chip, panel, pay items, old hire payloads) accept the other main kind;
  pay runs never set it (T5b). The pay run's preview uses it too, so such people show as "paid elsewhere", never as
  "not covered".
- PS6. A team line "for any kind of run" answers the ADVANCE question with the main scheme (pre-existing: the stored
  `pb_paid_by_advance_id` holds a regular scheme for many people; the chip showed "Advance: <main scheme>"). P1 hides
  it on screen (chip, panel) and never writes it as an advance row (hire, `cycle_type == 'mid_cycle'` guard). The
  stored column is unchanged — P2's fill must copy an advance only when it IS a mid-month scheme.
- PS7. `CYCLE_WORDS` is a plain dict: `_(CYCLE_WORDS[...])` was never extracted, so "end-of-month" / "mid-month
  advance" stayed English in vi/id. `cycle_words` now holds one `_()` literal per word.
- PS8. `pkill -f "<pattern>"` from a shell whose own command line contains the pattern kills that shell (exit 144).
  Restart walk servers from a script file (`serve.sh`), never inline.
- PS9. The first page load after an upgrade + asset purge can take 45 s+ (the renderer looks frozen to the browser
  tool; a navigate during server start shows an error page). Wait for "HTTP service running", then navigate again.
