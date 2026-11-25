# WFSETUP P10b — clock hours into Sudima's pay from 1 Dec 2026 (build, rehearse, go live)

## Binding design
`WFSETUP_P10A_PROPOSAL.md` is the design. Build it as written (architecture §3, keys §4.1, mapping §4.2, lateness §5,
pre-run check §6, extra hours §7, leading zeros §8, tests §9, gotchas §11 → add to the ledger), **with these owner
rulings overriding the proposal** (`WFSETUP_OWNER_RULINGS.md` R8–R16):
- **R13 (Q1 = option B):** no `VNLEAVEDAYS` column and no formula change. `clock.worked_days` (rename the key to
  `clock.paid_days` if clearer) = worked-day equivalents + approved PAID leave days (Payobook time off, paid leave
  types only, approved, in the period) + public holiday days from the company holiday calendar (only on days the
  person had no worked shift — a worked holiday is holiday overtime). Reuse the leave/holiday day logic of
  `application_payroll_source.py:444-492` (proposal §4.3). Show the three parts separately as info inputs
  ("Days worked", "Paid leave days", "Public holiday days") so HR can see how paid days were made.
  Unpaid leave counts 0. A leave day that also has punches → blocker on the readiness list.
- **R14 (Q2 = pay only up to the limit):** `clock.ot_hours` and `clock.ot_premium_hours` use `approved_hours` ONLY;
  `bonus_hours` goes to the info input "Overtime above the legal limit" (`VNOVERLIMIT`). Verify Sudima's overtime
  ceilings exist and match the law used in the proposal (4 h/day, 40 h/month, yearly); if Sudima has none, report —
  do NOT invent limits; the ceilings are configuration the owner/Sudima owns (list it as a pre-run blocker).
  The excess-pay design is backlog B1: do not build anything for it.
- **R15:** pre-run check requires every overtime entry decided; no weekly timesheet sign-off.
- **R16:** no cap; 27/26 stays.
- **R12:** the on-screen way to stop built-in extra hours = an on/off in Workforce setup (step 4 foot, managers) that
  empties/restores the Default overtime rule set's rules exactly as proposal §7 proves; turn it OFF on sudima only
  (owner instruction). Record what it removed so "on" restores it.
- **R8:** leading-zero matching in the one place + the two copies (proposal §8); exact match first; ambiguity →
  no auto-pick. All sites.

## Live data changes on sudima (owner-instructed; each through the same method the screen uses)
1. Load Vietnam's public holidays for Dec 2026 and all of 2027 via Workforce setup step 5's "add holidays" method
   (R13: "we load Vietnam's public holidays"). Show the list in the report.
2. Proposal §4.3 says Sudima's people are on a Mon–Fri calendar while they work 6 days, which breaks holiday/leave day
   counting. Study first: what calendar the leave/holiday logic needs, whether the rules' published roster is the
   better source of "working day" for Sudima. Prefer a design that does NOT require re-assigning 678 calendars. If a
   calendar change is unavoidable, STOP and report the exact change before making it on live.
3. Extra hours OFF (R12) through the new on/off.
4. Map Sudima's scheme 7844 inputs per §4.2 + R13/R14 (clock date 2026-12-01) through the scheme editor's new
   "From the clocks" source (on-screen twin required). The scheme stays draft — switching scheme/contracts on is
   Sudima's decision (pre-run blocker, listed).
Do NOT: confirm rules, publish a roster, switch clock-ins on, approve overtime, run a pay run, or activate the
scheme/contracts on any live database.

## Rehearsal (mandatory, hidden sudima copy; jobs + mail off the instant it exists; dropped after)
On the copy, do the whole December story end-to-end with a FAKE December: confirm rules, publish a roster for a past
4-week window (re-date as the proposal §9 tests do, or use Nov 1–23 with the clock date moved to 2026-11-01 ON THE
COPY ONLY), switch clock-ins on for connectors 4–8 (never 1), let them drain, approve/refuse overtime, enter 3 paid
leaves and 1 unpaid leave for test people, activate scheme/contracts on the copy, build a pay run with a pay data file
(Sep columns), and show: readiness refusal list before approvals; after approvals the payslips compute; for 5
anonymised people the clock cells, info cells and pay vs a hand calculation; zero double lateness; over-limit hours not
paid and shown; Sunday column guard; stamp refusal after a change; Sep–Nov style run (before the clock date)
byte-identical to today's behaviour. Numbers in the report.

## Rules (binding)
Clone deploy scripts from `p9/`/`p6/`. Deploy contract (repo CLAUDE.md): `/opt/deploy-notes.md` START/DONE, lock,
quiet check, backups ×5, scoped rsync, all modules that changed upgraded on every database where installed, asset
purge, hashes, versions, crons, HTTP 200 ×5. Never abm. White-label: the word "Odoo" never in a user-visible string
(labels, readiness messages, msgstr). Design bar verbatim: "extreme WOW, intuitive, out-of-this-world experience, best
in class"; Lucide via `ic()`; vi_VN + id_ID for every new sentence (WS40 import spelling, parse gate). Lessons follow
screen changes (check pb_learn for scheme-editor / pay-data-review lessons). No names/employee numbers in committed
files. Commit messages end `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Usage limit: server consistent,
"Where I stopped", PAUSED. Any rehearsal failure → stop and report, do not improvise.

## Report `WFSETUP_P10B_REPORT.md` (committed + pushed)
What was built; tests; rehearsal numbers; live changes made (holidays list, extra hours off, scheme mapping) with undo
notes; versions ×5; and the **Sudima go-live checklist for December** in plain English, in order, each line a button
or a decision with who does it (scheme + contracts on, ceilings, rules confirmed, December roster published, clock-ins
on for the five PCs, leave entered, overtime decided, pay data file without Sunday hours, run).
