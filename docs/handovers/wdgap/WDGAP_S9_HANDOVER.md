# WDGAP Step 9 — Performance and listening (S9-A, S9-B, S9-C side by side)

Read first: `WDGAP_WAVE_RULES.md`, `WDGAP_OWNER_RULINGS_2026-11-15.md` (P1–P6, C-3, C-5),
`WDGAP_LEDGER.md`, then `WDGAP_S9_FACTS.md` IN FULL — verified plumbing per item
(path:line), precedents, the lane table (§5), the collision list (§6, binding — above
all: NEVER edit any file under `pb_lifecycle/`) and the "defaults taken without asking"
at the end of §7 (binding). Your lane = your phase's row in §5, narrowed by anything
below. `WDGAP_QF4_REPORT.md` (goals → pay review, already live). The e-learning player
and on-the-job sign-off are DEFERRED — not in this step.

Branches `wdgap-s9a` / `wdgap-s9b` / `wdgap-s9c`; db prefixes `wdgap_s9a_` etc.

## S9-A — Review forms (new `pb_review_forms`; `pb_goals` manifest only)

- P1: ONE company review form per goal year — the goals score, a few skills or company
  values rated on a five-point scale ("Well below" … "Well above"), and up to about
  eight questions HR writes. Flow: the employee gives their own view on My Payobook
  first, then the manager in the Goals drawer, then an overall comment; hide-until and
  acknowledgement as FACTS describes; a PDF of the finished review filed on the
  employee's documents.
- P2: once a goal year has a published form, the pay review starts from the OVERALL
  review result — shares set by HR on the form (e.g. 70% goals, 30% skills) — delivered
  ONLY by changing what the existing goals score hook returns (FACTS: `_pay_score`); no
  `pb_pay` edit. A goal year WITHOUT a form behaves exactly as today (golden test on the
  pay-review reading).
- A year's form is locked once the first review is submitted (new version = next year);
  HR can preview as an employee.

## S9-B — Conduct cases + People reports (new `pb_conduct`, new `pb_people_reports`)

- Disciplinary cases: concern → hearing → decision → letter, generic steps with country
  notes HR can edit (legal wording per country is an owner item — say so on screen as
  "review with your adviser", plain words). P3: visible ONLY to people HR names on the
  Access screen (clone the growth-plans naming pattern); the employee sees only their
  own FINISHED letters on My Payobook and can reply; the line manager sees nothing
  unless named; payroll officers and general HR users see nothing.
  **Privacy leaks found by FACTS (letters readable by every lifecycle user; every
  document readable by every payroll officer): your module must add its own blocking
  rules so conduct letters, notes and files are closed to everyone not named — prove it
  with tests as each of those roles.** Do not edit `pb_lifecycle`; if a leak cannot be
  closed from your module, STOP that item and report.
- People reports as their own tab under People › Insights: turnover, joiners against
  leavers, age bands, gender, length of service, by company/department/period. P6: HR
  only, for the companies they can already see; ANY group under 5 people shows as
  hidden (also in exports and totals — no figure may be recoverable by subtraction;
  test that). No `pb_explorer` edits. Never adds across currencies (no money here).

## S9-C — Employee voice (new `pb_voice`)

- Survey rounds with a small question library in en/vi/id, answered on My Payobook,
  results by group, a manager card on the team page (xpath from your module), simple
  action plans (own list, not workflow tasks). Own small model — NOT the standard
  survey tool.
- P4: FULLY ANONYMOUS by construction — the answer rows carry NO link to the person or
  login, no timestamps finer than the day, no IP; "who has answered" is kept separately
  only as a yes/no per person so reminders work, and cannot be joined to answers (test:
  with full database access as HR there is no path from an answer to a person). Results
  AND written comments only for groups of 5 or more; comments to HR only; no
  subtraction leak between a group and its parent (suppress the complementary group).
- P5: only on My Payobook; people without email use bulk logins with printed slips
  (existing Access feature — link to it from the round's "who can answer" panel). No
  tablet or paper path.
- Reminders respect the tenant email rule: on a database with no outgoing mail nothing
  is queued; the in-app "Needs you" row is the reminder.

## Step go-live note (for the deploy agent, later)

One go-live for the step; three or four new modules with `-i` ×5; risky tier because
of the new security rules; seam test: all three plus the Step 6 modules on the employee
home (hooks stack, each calls `super()`).
