# WDGAP Step 6 — More for employees to do themselves (S6-A, S6-B, S6-C side by side)

Read first: `WDGAP_WAVE_RULES.md`, `WDGAP_OWNER_RULINGS_2026-11-15.md` (E1–E6, C-1..C-4),
`WDGAP_LEDGER.md`, then `WDGAP_S6_FACTS.md` IN FULL — verified plumbing per item
(path:line), the portal-user access facts (§1: employee logins are mostly PORTAL users
and almost every grant today is for internal users only — every employee-facing read
and write must go through your own controller/model method with explicit checks, tested
as a real portal user), the lane table (§8) and the collision list (§9). Your lane =
your phase's row in §8, narrowed by anything below. The "design defaults applied without
asking" at the end of §10 are binding.

Branches `wdgap-s6a` / `wdgap-s6b` / `wdgap-s6c`; db prefixes `wdgap_s6a_` etc.

## S6-A — My details, papers and consent (new `pb_me_details`, `pb_me_letters`,
## `pb_me_privacy`; may edit `pb_bank_ocr`, and `pb_records` ONLY for the bank fix) — RISKY

- Employee proposes changes to their own family members, ID papers, photo and bank
  details on My Payobook; nothing changes on the record until approved; the employee
  sees "waiting / approved / sent back (with reason)". Approvals through the one inbox.
- E1: an approved family change never reaches pay by itself. For Vietnam it shows on the
  HR side as "waiting for HR to confirm for tax" with one tick; only the tick updates
  what pay reads. (`pb_hr_payroll_vietnam` may be read; edit it only if there is no
  other way to hold the tick — report file/lines.)
- Bank details: through the bank-document check, second person approves, never the
  proposer (existing bank approver rules; rize's named approvers).
  **BANK STORE FINDING (FACTS §0.1) — fix it here:** the pay bank file reads one store,
  the Updates/Records bank lane writes another, nothing copies across. Required end
  state: an approved bank change from ANY path (My Payobook, bank-document check,
  Updates sheet) lands in the store the bank file reads, and both stores agree. Make the
  smallest correct change (in `pb_bank_ocr` and the one bank-lane method in
  `pb_records`), with tests for each path. Do NOT bulk-rewrite existing data: ship a
  READ-ONLY check (a method the deploy agent can run per database) that lists employees
  whose two stores disagree, so the owner can decide. Also repair the unreachable code
  after `return` in `pb_bank_ocr` (FACTS §0.3).
- E2: certificates from My Payobook — employment certificate (no pay figures) at once as
  a PDF; salary certificate waits for one HR click, then the employee is told and
  downloads it. Letter engine by inheritance only (`pb_lifecycle` is off-limits; the
  signatures you rely on are listed in FACTS §9 — list them again in your report).
  Every certificate is numbered, filed on the employee's documents and logged.
- E3: consent — on first sign-in to My Payobook after the company has published a
  notice, the employee reads it and presses "I have read and agree"; asked again only
  when the company publishes a new version; HR board shows agreed / not yet / paper
  consent recorded by HR (with who and when). No company notice published → nobody is
  asked (silent install). The screen must be answered to continue; it offers "I have
  read and agree" and "I do not agree" (both recorded; HR sees it; the employee
  continues to My Payobook either way — nobody is locked out of their payslip).

## S6-B — Apply and ask (new `pb_hiring_internal`, new `pb_me_payai`) — RISKY (AI, access)

- Internal roles on My Payobook: open roles the employee may see, apply with their
  existing record (no re-typing), track status. E4: the current manager is told only
  when an offer is near (the stage FACTS names); until then only that role's hiring team
  sees the application — test that the manager's views, team pages and inbox show
  nothing. C-2: hide paused roles (probe). C-1: hiring an internal candidate opens the
  Change job flow (probe `pb.job.change`), never a second employee record; without it,
  a calm "job change to do" note for HR.
- E5: PayAI on My Payobook answers ONLY from the company's policy files HR uploads —
  NO personal figures (no leave balance, no payslip), no general knowledge. Always shows
  which policy it used; when it cannot answer from the files it says so and offers "Ask
  HR" with the question filled in. Off by default; switched on per customer on the
  existing AI settings, with a daily limit per person and per company and a use count HR
  can see. Uses the database's existing AI account configuration (never a key in code or
  in the repo; a database without one shows HR "not set up yet", employees see nothing).
  Privacy: only the question and policy excerpts leave the system — never employee
  identity or records; test that.

## S6-C — Claims paid in pay (new `pb_expense_payroll`, `pb_trip_advance`,
## `pb_expense_allowance`; small edits in `pb_me_expense`, `pb_expenses_hub`,
## `pb_business_trip` as §8 allows) — RISKY: pay calculation

- E6: a company setting "Approved claims are paid: in the next pay run / by finance"
  (default: by finance = today's behaviour, byte-identical). In the pay run a claim is
  a separate UNTAXED line on the next REGULAR run's payslip, paid once (reservation
  pattern of loans/one-offs; Extra/top-up runs never take it), and the claim shows
  "Paid in <run>".
- Trip advances tracked per trip: given, claimed against, settled. When a trip's claims
  are settled, unspent advance is taken back from the next regular pay as a deduction —
  the employee sees the figure first on My Payobook; take-home never below zero (take
  what fits, carry the rest; clone the PR-E loan pass).
- Yearly claim allowances per category: company figure, per-person figure wins, refusal
  shows "limit, used, left" unless the company allows going over with approval (FACTS
  §10 defaults).
- Schemes paid from a pay data file: do not change the file path; follow the ledger
  rule and S5-B's wording — say plainly on screen that the amounts are shown for the
  pay team to include in the file — and report what a real fix needs.
- Golden: every payslip with no claim/advance byte-identical.

## Step go-live note (for the deploy agent, later)

One go-live for the step; merge A, B, C; seam tests from FACTS §8 "unavoidable shared
surfaces"; run S6-A's bank-store check read-only on all five databases BEFORE go-live
and report the numbers; S6-C touches pay → short rize rehearsal; seam test with S5-B
if Step 5 is already live (a payslip carrying a claim and time inputs).
