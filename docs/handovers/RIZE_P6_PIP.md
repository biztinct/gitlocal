# RIZE P6 — pb_pip: performance improvement, quietly

Read FIRST: `docs/handovers/RIZE_LEDGER.md` + phase-log P0–P5 (code wins). Design doc:
`docs/design/rize-hrms-blueprint.html` §07. Rulings D5 (employee sees own PIP,
switchable) and D8 (no Zoho push) bind this phase.

## Scope
ONE new module `pb_pip` (depends: pb_lifecycle, pb_probation for patterns, pb_offboarding
for the resignation hook):
1. `pb.pip.case` — request → coaching → active plan → check-ins → evaluation → outcome.
2. Coaching-plan stage (template-driven) BEFORE any formal PIP.
3. Objectives with success metrics; weekly/bi-weekly check-ins (P0 checkins).
4. Evaluation collection + pass/fail verdict; post-PIP restore; letters.
5. Auto-terminate on resignation (override P4's `_on_resignation_approved`).
6. Strict visibility: dedicated groups + country record rules + config switches.
7. **PIP lens** on the Lifecycle hub (invisible without the groups).
8. Portal `/my/growth`: own active plan + acknowledgement (D5).

### Binding NON-goals
- No probation changes. No auto-exit on fail (explicit HR button → P4 case, like P5).
- No Zoho outbound. No manager self-service beyond requesting + their own case view.

## Verified plumbing facts (do NOT re-derive)
- P0: `pb.employee.checkin` kind 'pip'; letter engine (seeded 'pip' letter type);
  reminder cron to inherit for check-in nudges; feedback requests kind 'pip' for the
  evaluation form.
- P4: `_on_resignation_approved` extension point (exact signature in the P4 report /
  code) — override: active PIP cases for that employee → state terminated + note + HR
  mail.
- P5: verdict-wizard interaction pattern + guided-dialog shapes to clone;
  `wfp_performance_rating` probe-write pattern (on PASS, write the agreed final rating).
- Record-rule + group canon: ledger platform contract; PIP needs COUNTRY-scoped rules —
  country via employee's company country or employee country: use
  `[('employee_id.company_id','in',company_ids)]` company rule PLUS group gating;
  "Head of HR by country" = `group_pip_user` members see cases in their allowed companies
  (multi-company allowed_company mechanism suffices — do NOT invent a country matrix;
  document this simplification in the report).
- Hub lens gating: `groups` on the lens entry (advisory) + facade `has_group` checks
  (enforcing). Palette 2600s.
- Portal canon: pb_me_portal; config params pattern.

## Architecture

### Models
**`pb.pip.template`** — name, default_weeks Integer default 6, checkin_freq Selection
weekly/biweekly, focus_line_ids (`pb.pip.template.line`: name, description, sequence),
coaching_body_html (starter coaching-plan text), active, company_id. Seed 2 templates
("Delivery quality — 6 weeks", "Collaboration — 4 weeks") with sensible plain-English
focus lines.

**`pb.pip.case`** — mail.thread. name computed ("<Employee> — improvement plan"),
employee_id required, requested_by_user_id (manager), hr_owner_user_id, template_id,
reason_text (manager's request), state Selection
`[('requested','Requested'),('coaching','Coaching'),('active','Plan running'),
('evaluation','Being evaluated'),('passed','Completed successfully'),
('failed','Not successful'),('terminated','Closed — left the company')]` tracked,
coaching_html, coaching_start/end Dates, start_date, end_date (start + weeks),
objective_ids, checkin_ids (P0 checkins linked by a `pip_case_id` field added via
_inherit inside this module), employee_ack Boolean + ack_at (portal), eval_request_id
(P0 feedback request, manager evaluation form), final_rating Integer 1–5,
outcome_note Text, company_id.
Flow: `action_take_up()` (HR accepts request → coaching; schedules the HR-manager call
as a checkin kind other), `action_start_plan()` (requires ≥1 objective + coaching done →
active; schedules ALL check-ins per freq through end_date; generates the PIP letter (P0)
and emails the employee IF employee-view is on, else letter only filed), employee ack via
portal, `action_evaluate()` (at end_date or manual → evaluation; creates the manager
evaluation feedback request with the objectives embedded as rating questions),
`action_verdict(pass|fail)` (guided dialog: per-objective met/not-met + final_rating +
note; PASS → passed + congratulation mail + wfp rating probe-write + restore note in
chatter; FAIL → failed + HR notification with explicit "Start exit" button → P4 case),
auto-terminate override per P4 hook.

**`pb.pip.objective`** — case_id, name, metric Char ("what good looks like"),
target Char, weight Integer default 1, status Selection
on_track/at_risk/met/not_met default on_track, notes, sequence.

### Check-in nudges
Inherit P0 reminder cron: today's PIP check-ins → owner mail; missed check-ins (>2 days)
→ HR owner alert; idempotent.

### Visibility (the heart of this phase — get it right)
- Groups: `group_pip_user` ("PIP — HR"), `group_pip_head` ("PIP — Head of HR", implied
  user), NO implication from lifecycle groups (deliberate: lifecycle admin ≠ PIP access;
  grant explicitly). Admin (base admin) implied via pip_head only.
- ACLs: pip models ONLY for these groups. Company ir.rule for both.
- Requesting manager: config `pb_pip.manager_sees_own` default '1' → a record rule
  granting the REQUESTER read on their own requested cases
  (`[('requested_by_user_id','=',user.id)]`) + the request entry point (below); write
  stays HR-only.
- Employee (D5): config `pb_pip.employee_view` default '1' → portal route only (no model
  ACL for portal; route-boundary sudo, session-scoped) — page hidden entirely when '0'.
- The hub lens: entry gated `groups: ['pb_pip.group_pip_user']`; every facade method
  re-checks `has_group` and returns a friendly refusal payload otherwise.
- Manager request entry: a small "Ask HR to start an improvement plan" action reachable
  from ⌘K (gated to ANY internal user managing people — filter: user's employee has
  child_ids) → creates a `requested` case visible to them per the rule; NO board access.
- Chatter/followers: do NOT auto-subscribe the manager to the full case; notifications
  to them only at explicit points (plan started if configured, verdict).

### PIP lens (Lifecycle hub, ⌘K 2600s — all gated)
Facade `pb.pip` get_board(): rows = open cases {employee (photo), state chip, weeks
in/left, objectives on-track/at-risk counts, checkin adherence % (done/scheduled-to-date),
ack ✓, HR owner}; kpis (open plans, awaiting coaching, evaluations due, at-risk);
facets (state, company, HR owner). Row → case drawer: objectives with status pills
(inline updatable), check-in timeline with notes, coaching panel, letters, action
buttons per state. Guided dialogs clone P5's verdict-wizard tone: every confirm states
in plain English what happens next.

### Portal `/my/growth`
If enabled and an active/evaluation case exists for the session employee: calm, supportive
page — the plan (objectives, what good looks like, dates), my check-in schedule, the
letter download, and the acknowledge button (one-time, stamps ack). NO board, NO history
of closed cases beyond the active one, no "PIP" scare-jargon: page title "My growth plan".
`/my` counter only while awaiting acknowledgement.

## Safety rails
- Triple-check the visibility matrix (T-cases below include negative tests) — a PIP leak
  is the worst failure mode of this phase.
- No mails to real staff (@example.com actors throughout); employee-facing mails only to
  test logins.
- Verdict FAIL never auto-opens exit.
- Deploy `-i pb_pip` only (inherits live inside pb_pip).

## Numbered test cases
T1. Deploy clean.
T2. As a manager-user (test): ⌘K request entry visible, creates a requested case with
    reason; the manager can read THEIR case, cannot see the board/lens, cannot see
    another case (direct URL/id probe → access error).
T3. As an internal user with NO pip groups: lens absent from the hub; facade RPC called
    directly → friendly refusal, no data, no traceback in log.
T4. As pip HR user: take up → coaching (HR-manager call checkin created); write coaching
    notes; start plan blocked until an objective exists (friendly error); add 2
    objectives → plan starts: check-ins scheduled per freq to end date; PIP letter
    generated + vault-filed; employee mail queued (employee_view '1').
T5. `/my/growth` as the employee: plan renders (supportive copy, screenshots light+dark);
    acknowledge → ack stamped, counter clears; with `pb_pip.employee_view`='0' the page
    404s/redirects politely and no employee mail is sent for a fresh case.
T6. Check-in nudges: today's checkin → owner mail once (idempotent); missed >2 days → HR
    alert once.
T7. Objective status inline updates (at_risk shows amber on board).
T8. Evaluation: reach end (or force) → evaluation state, manager evaluation form (token)
    with objectives as questions; submit it; verdict dialog shows the answers.
T9. Verdict PASS → passed; congrats mail; wfp rating written (or probe-skip logged);
    board archives it.
T10. Second case verdict FAIL → failed + HR notification with Start-exit button → P4
    offboarding case opens on click only.
T11. Third case: approve a resignation for that employee (P4 flow) → PIP auto-terminated
    with note; HR mail.
T12. `pb_pip.manager_sees_own`='0' → requester loses read (probe).
T13. White-label + no "PIP" on the EMPLOYEE page (title "My growth plan"); plain English;
    grep zero "Odoo".
T14. Regressions: P4 resignation without any PIP unaffected; P5 lens fine.
T15. Clean up; report param defaults left in place.

## Deliverables / report back
Commits, per-test results, deploy EXIT, deviations, gotchas appended, the pip_case_id
inherit shape on checkins, visibility matrix as-built (groups/rules/params), lens gating
approach confirmation, palette ids.
