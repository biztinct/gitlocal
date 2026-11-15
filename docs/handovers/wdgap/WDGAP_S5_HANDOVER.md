# WDGAP Step 5 — Leave and time rules (three builders side by side: S5-A, S5-B, S5-C)

Read first: `WDGAP_WAVE_RULES.md`, `WDGAP_OWNER_RULINGS_2026-11-15.md` (L1–L6, C-3, C-4),
`WDGAP_LEDGER.md`, then `WDGAP_S5_FACTS.md` IN FULL — it is the verified plumbing for
every item (path:line), the precedents to clone, the exact lane table ("Proposed split:
three builders at the same time") and the collision list. Your lane = your phase's row
in that table ("Owns (may edit)" / "Must not edit"), narrowed by anything below. Also
`WDGAP_QF3_REPORT.md` (leave quick fixes already live).

Branches `wdgap-s5a` / `wdgap-s5b` / `wdgap-s5c`; db prefixes `wdgap_s5a_` etc.

## S5-A — Kinds of leave and how they are earned (new module `pb_leave_setup`)

Build items 1–3 as the FACTS document specifies, with the owner's rulings:
- Set-up screen "Kinds of leave" reachable by TENANT staff (FACTS: today they cannot
  reach it) from Settings › HR and ⌘K, with a guided drawer and an employee preview.
- Monthly build-up + extra days for long service. L2: a per-kind setting "People can
  take days before they are earned" — default OFF ("only what is earned so far").
  Posting is audited, idempotent per person × kind × month, and the job is quiet and
  safe on an empty database. Existing kinds keep today's behaviour until HR changes them.
- L1: ready-made kinds for VN, ID, IN, SG, TH, KH, MY as reviewed data INSIDE
  `pb_leave_setup` (never `pb_pack_*`), offered on demand as "A starting point — please
  review each kind before switching it on"; every figure carries its source note in the
  drawer; nothing is created or switched on by install; applying twice never duplicates.
- Fix inside your lane (FACTS findings): leave balances must ignore EXPIRED days.
- All new fields on leave kinds have defaults and no required constraints (S5-B creates
  a kind without knowing yours).
- Tests: build-up maths incl. joiner mid-month, service steps, cap, leaver; taking ahead
  on/off; expiry in balances (employee page, manager "balance after", QF3 over-balance
  refusal still right); starter set apply/re-apply per country; tenant-staff reach;
  portal employee sees only kinds they may apply for; existing `pb_timeoff` suite =
  baseline.

## S5-B — Time into pay (new module `pb_time_pay`) — RISKY: touches what reaches a payslip

Build items 4–5 as the FACTS document specifies, with the owner's rulings:
- L6: overtime suggested from clock punches; where no shift was published compare with
  the person's NORMAL WORKING HOURS (working schedule). Suggestions are only
  suggestions: a manager accepts them (bulk) into ordinary overtime requests.
- L5: late (and early-leave) minutes derived from REAL punches (FACTS: today only demo
  data produces "late" rows), shown in the weekly Close with Confirm and Excuse; ONLY
  confirmed minutes become a pay input. Off until the company maps that input in a
  scheme; a scheme without the mapping is byte-identical.
- L3: on approving overtime the manager picks "Pay it" or "Give time off" — hour for
  hour into a "Time off in lieu" kind; hours given as time off are NOT also paid
  (subtract above the bridge as FACTS describes). L4: these hours NEVER run out — no
  expiry, no payout (ignore the expiry/payout parts of the FACTS proposal).
- Fix inside your lane (FACTS findings): holiday-overtime detection reads a list that
  does not exist on this version → make it read the real public-holiday source.
- KNOWN GAP to handle honestly: approved overtime never reaches payslips made from a pay
  data file (rize: 15 such schemes). Do NOT change the file path. Your new inputs must
  state on screen, for such schemes, "This scheme is paid from a pay data file —
  confirmed minutes/overtime are shown for you to include in the file" (plain words),
  and the report must spell out what a real fix would need (owner question).
- The ONE shared-file edits allowed: one line each in
  `pb_hr_payroll_formula/models/input_provenance.py` and
  `pb_source_atlas/models/pb_source_atlas.py`, plus the `pb_close`/Close-lens files in
  your row. Nothing else in the formula engine.
- Tests: suggestion maths (shift vs working hours, night/holiday), accept → request;
  late minutes from punches incl. grace minutes, Excuse, confirmed-only; in-lieu split
  (paid vs time off, hour for hour, no double pay); payslip golden with no new data;
  file-scheme message; reservation/idempotence on recompute; suites of every edited
  module = baseline.

## S5-C — Rotating shift patterns (new module `pb_shift_patterns`)

Build item 6 as the FACTS document specifies: pattern, slots, members; "Generate N weeks
as drafts" with the existing copy-week checks and a skip report; a "from pattern" mark;
a "Patterns" lens in Mission Control via the registry and ⌘K rows. Nothing is published
automatically — drafts only. Optional toolbar button in `pb_schedule` only as your row
allows. Tests: 2-crew and 4-crew rotations across a month boundary, leave/holiday
clashes skipped and reported, re-generate does not duplicate, rights, empty install.

## Step go-live note (for the deploy agent, later)

One go-live for the whole step: merge A, then B, then C; seam tests from the FACTS
"Shared files inside S5" list; `pb_time_pay` touches pay → short rize rehearsal.
