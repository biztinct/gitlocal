# PSCHEME P1 — the person's own pay scheme: engine, Add employee, the person's panel

Read first, in this order: `PSCHEME_LEDGER.md` (rules §0, owner rulings §1, architect decisions §2 — binding),
`PSCHEME_FACTS.md` (every seam with file:line — **do not re-derive**), `docs/handovers/newhire/NEWHIRE_LEDGER.md`
(local database conventions, walk method, gotchas NH…), `docs/handovers/newhire/NEWHIRE_P8_REPORT.md` §2.

Worktree `gitlocal-worktrees/pscheme`, branch `pscheme` (already holds the facts doc, the ledger and this file).
**Local only: no release, no push, no live server, no live database in this phase.**

Rails (ledger §0, restated because they bind every line you write): design mandate verbatim **"extreme WOW,
intuitive, out-of-this-world experience, best in class"**; Lucide, no emoji; plain screen words; **never "Odoo" in a
user-visible string**; vi_VN + id_ID for every new string; public repo — no client names / data / credentials;
backend needs a screen twin; dependency rail (ledger §0.9); no effort on past pay runs (ledger §0.11).

## Scope
A. Model `pb.person.scheme` + the `'person'` rung in the one resolver (real person and draft).
B. Cache, stale marks, the daily boundary job, the advance allow-list.
C. Pay run: judged on the period's first day through the new rung; a "has their own pay scheme elsewhere" list.
D. Changing a person's scheme through the existing approval route (new proposal kind).
E. Add employee stores the chosen scheme on the person; the "pay run follows the team" sentences go.
F. The person's "Pay scheme" panel + "Change pay scheme" dialog (employee side panel; contract drawer strip).

## Binding non-goals (P2 / P3 — do not start them)
- Mapping board re-wording, "Set for everyone in this team", "Suggest who pays each team" changes.
- The one-time fill of existing people (tool or script). P1 ships with ZERO rows on every existing person.
- The Country of work change prompt; `pb_job_change`; Updates sheets / joiner sheet; hiring-offer default;
  pay-data-file joiners; contract currency or usual answers following a scheme change (FACTS T6, T7).
- `pb_learn` lessons / replicas (P3) — but list in the report every lesson sentence P1 made untrue.
- `pb_demo` runs (FACTS T9). Work segments (rung 1) stay exactly as they are, above the new rung.
- Any second contract / two-country split (ledger R5).

## A. Model and rung
A.1 `pb.person.scheme` in `pb_scheme_map/models/pb_person_scheme.py`, cloned from `pb.division.link`
    (`pb_group/models/pb_division.py:269-325`). Fields exactly as FACTS §4 "Fields" (employee_id required / index /
    cascade; company_id related stored; config_id required restrict; cycle_type related stored index; date_from
    required; date_to; source selection `fill / hire / hand / team / import / job_change`; note; active; contract_id
    optional, unused). Constraints: no overlap per (employee, cycle_type) with a plain named sentence; scheme's company
    = the person's or shared; no `full_final`; `date_to >= date_from`. Access: read for the groups that read map lines;
    write only through the board under `SCHEMEMAP_WRITE` (clone how map lines are guarded) — nobody writes it from a
    native form. `_description` and field strings in screen words ("Pay scheme of a person").
A.2 `RUNGS` per ledger A2. New `_person_schemes(employee_ids, on_date)` beside `_segment_schemes`
    (`pb_scheme_map.py:294-336`), read with the ORM (FACTS T4), ONE search for the whole roster, returning per person
    `{'has_rows': bool, 'rows': {cycle_type: row}}` chosen by ledger A4. Called once in `resolve_many` (`:378`) and
    answered between rung 1 and rung 2 by ledger A3 + A5 (reuse `_pick` unchanged). Answer `rung='person'`,
    `via` = "their own pay scheme, from %(date)s" (date formatted in the user's language).
    A context key `pb_scheme_skip_person` makes `resolve_many` skip the rung (needed by C.2 and by P2's fill) — it is
    read nowhere else.
A.3 `resolve_for_draft` (`:537-567`): when `values` carries `scheme_id` (and optionally `advance_scheme_id`), the
    person rung answers first from those, by the same A3 / A5 rules (main kind = the chosen scheme's own kind). Without
    `scheme_id` it behaves exactly as today. `resolve_for_team(s)` unchanged.
A.4 The payslip's rung 3 (`pb_hr_payroll_formula/models/hr_payslip_formula.py:461-475`) passes
    `on_date=self.date_from` (soft probe kept; never raises).

## B. Cache, stale marks, boundary job
B.1 `ADVANCE_RUNGS` constant (ledger A6) used at `hr_employee.py:155-158` and `pb_scheme_board.py:690-692`; add
    `'person'` to the literal in `scheme_component_scope.py:114-115`; a test asserts the three agree.
B.2 Stale marks (`_pb_mark_paid_by_stale`, GR13 order): on `pb.person.scheme` create / write / unlink (the people
    touched); on `hr.employee.write` with `payroll_country` in vals (fixes today's gap, FACTS fact 5; marks only —
    ledger A7).
B.3 Daily job in `pb_scheme_map/data/ir_cron.xml`: marks stale every person with a row whose `date_from` is today or
    whose `date_to` was yesterday; the existing nightly recompute settles them. `noupdate`, off-by-default is NOT
    wanted — it runs. (Cron snapshot trap on release is P3's concern; note the new job's xml id in the report.)
B.4 "Paid by" (`_pb_recompute_paid_by`) keeps writing the same four columns; with a person row the via sentence is
    A.2's. Add a stored `pb_paid_by_own` boolean (rung is `person`) so screens can tell "their own" from "from the
    team" without parsing the sentence (FACTS T11).

## C. Pay run
C.1 No change to `_scheme_population`'s call (`on_date=date_start`); ledger A4 does the work. Prove with tests C-T.
C.2 `scheme_preview` (`pb_payrun_wizard.py:544-574`) gains a third list beside covered / not covered: people whose
    answer is ANOTHER scheme because of their own row, while the ladder without the person rung
    (`pb_scheme_skip_person`) would have put them in THIS run. Screen (run step where "not covered" shows): a quiet
    grey line "N people of these teams have their own pay scheme and are paid elsewhere" that opens the names with
    "paid by <scheme>, from <date>". Grey at zero = hidden (quiet board pattern). Through the soft probe; a database
    without `pb_scheme_map` is unchanged.
C.3 The pay-run help sentence `pb_payrun_wizard/static/src/xml/payrun_wizard.xml:93-96` ("Attaching their team to a
    scheme fixes everybody in it at once.") becomes two honest options: give the person a pay scheme, or set the team's
    usual one.

## D. Changing a person's scheme (server)
D.1 New kind `person_set` on `pb.schememap.proposal` (`pb_hr_payroll_formula/models/schememap_approval.py:40-157`),
    FACTS §5 "cheapest correct route": payload `{employee_ids, config_id, advance_config_id | False | 'keep',
    date_from, company_id, source}`; snapshot = each person's counting rows on `date_from`; fact `employees_moved`;
    `_apply_person_set` → `pb.scheme.board.person_set(...)` under `SCHEMEMAP_WRITE`. Kind label through `_()` (the
    existing labels are plain literals — make the new one translatable and, since you are in the file, the old ones
    too if that is a one-line change; otherwise report).
D.2 `pb.scheme.board.person_set` semantics (one transaction, idempotent, `flush_all` before any resolve):
    - for the main kind: the row in force on `date_from` (if any, and a different scheme) gets `date_to = date_from - 1`
      (a row that started on or after `date_from` is unlinked — it never took effect); a new row starts on `date_from`;
      same scheme already in force → nothing written.
    - the advance: `advance_config_id` a scheme → same treatment for kind `mid_cycle`; `False` → the advance row in
      force is ended the day before (ledger R7: no advance unless given); `'keep'` → untouched.
    - a change of the main scheme to another kind (`regular` ↔ `end_cycle`) ends the row of the OLD kind too — a
      person never keeps two main schemes.
    - refusals in plain words: scheme not active; scheme of another company; `full_final`; advance scheme that is not a
      mid-month advance; person archived.
D.3 Rights (ledger R9): who may PROPOSE = HR officers / HR managers and payroll roles (check what `propose` needs
    today and open it for HR without widening any write access rule on map models); who CARRIES OUT = today's gate
    (`_proposal_gate_groups`), unchanged. Fast lane when no second approver → applied at once and the dialog says
    "Saved". Otherwise "Sent for approval" and the panel shows the waiting change (F.3). Test both lanes.
D.4 Read API for the screens: `pb.scheme.board.person_scheme(employee_id)` → current main + advance (scheme name,
    currency, kind in words, since-date, own / from where in words), the next dated change if any, a waiting proposal
    if any, history rows (newest first), the chooser list (active schemes of the person's Country of work via
    `_country_schemes`, then "other countries" on request), the suggested advance (the ONE mid-month advance paired
    to a scheme through `hr.payroll.cycle.component.mapping`, else none), `can_propose`, and the default start date =
    the 1st of next month.

## E. Add employee (`pb_new_hire`)
E.1 `_scheme_for` (`studio.py:456-520`): the chosen (or defaulted) country scheme is now HONOURED — pass
    `scheme_id` / `advance_scheme_id` into `resolve_for_draft` so every reader (tile, step 3, record panel, Check,
    payslip example, usual answers, approver card) sees one answer. Default order when a country has several stays
    P8's (team's usual → most of the team → most of the country); the "Usual" tag and "This differs from the team's
    usual scheme, X. Use the usual one" stay — as information, no longer a warning.
E.2 Retire the amber family (FACTS §11 `pb_new_hire` list): "…and the pay run follows the team.", "To pay them by
    %(scheme)s, pick one of its teams…", "The pay run will pay them by %(run)s, not %(scheme)s.", "Set who pays
    %(team)s in Mapping…" (all three variants), "You can still add the person. Set who pays this team in Mapping
    before the first pay run." Replace with ONE calm confirming line where a line is useful: "<Person> will be paid
    by <scheme> from <first day>." Keep "No pay scheme for <country> yet" + its Mapping link (the only remaining
    dead-end, and it names its fix). Intro texts `new_hire_studio.xml:275,395` say the pay scheme follows the Country
    of work and can be changed here. Remove the dead msgids from the .pot / vi / id.
E.3 Mid-month advance: when the chosen scheme has exactly one paired advance (D.4), the tile shows a ticked
    "Mid-month advance: <name>" switch (keyboard reachable); none paired → no switch; several → a small chooser,
    default none. The pick travels as `advance_scheme_id`.
E.4 On apply (`create_ext.py` hire apply, FACTS §5 "The hire path"): write the person row(s) through
    `person_set` semantics with `source='hire'`, `date_from` = the first day (contract start), inside the hire's own
    approval (no second proposal). Old payloads without a scheme key: resolve as today and write the row for what the
    resolver answered when it is a scheme of the Country of work; write nothing when the answer is none.
E.5 Vietnamese joiner case (P8 §6.4 last row): a new person in a country with one scheme and no team line now lands in
    that scheme's pay run — test E-T3.

## F. The person's panel
Hero moment (name it in the report): **open a person, see in one line who pays them and since when; press Change,
pick a card, and the line rewrites itself with the date — "Paid by Indonesia Monthly from 1 Dec 2026" — before you
close the dialog.**
F.1 Employee side panel: replace the read-only "Paid by" / "Advance paid by" rows
    (`pb_employee_vault/models/employee_details.py:119-125`, FACTS §6.1 row 1) with a "Pay scheme" block, built as a
    custom kind the way `pb_employee_bank_panel` does it (`bank_panel.py:60-102`, `bank_panel.xml:11-20`) from a
    module that may depend on both (`pb_scheme_map` owns it if the dependency direction allows, else a thin bridge —
    report which). Content: scheme name + currency chip; "Their own pay scheme since <date>" or, without a row, "From
    <team>'s usual pay scheme" / "From a rule on the map" / "No pay scheme yet" (amber only for the last);
    "Mid-month advance: <name>" or nothing; "Changes to <scheme> on <date>" when a later row exists; "Waiting for
    approval: <scheme> from <date>" when a proposal is open; a "History" disclosure. Also fix the label "Payroll
    country" → "Country of work" on that panel (FACTS §6.1).
F.2 "Change pay scheme" dialog (one OWL component, reused by F.4): radio cards like Add employee's chooser (name,
    currency · kind of run in words · "pays N people"), the person's Country of work schemes first, "Show pay schemes
    of other countries" disclosure with a plain note that tax and insurance boxes follow the Country of work; advance
    switch (D.4 suggestion); "From" date, default the 1st of next month, with the R6 sentence live under it: "A change
    during a month starts with the next pay run. <Old scheme> still pays <month>." when the date is not a 1st, and
    "First pay run: <month>" otherwise; primary button "Change pay scheme" / "Ask for this change" (per lane). States:
    loading skeleton, no scheme for the country (link to Mapping), same scheme picked (button disabled with the
    reason), refusal sentences from D.2, sent-for-approval confirmation. Enter / arrows / Esc; focus returns to the
    button; 340 px wide works.
F.3 After a change the panel re-reads `person_scheme` (no full reload) and the line animates in once (no jitter on
    later redraws — OWL markup flicker memory: never `t-out` a new `markup()` per redraw).
F.4 Contract drawer strip (`pb_contracts/static/src/xml/contract_360.xml:355-372,400-407`): the strip names the
    person's scheme + since-date; "Choose who is paid by what" becomes "Change pay scheme" and opens the same dialog.
    `pb_contracts` must not gain a dependency on `pb_scheme_map` — use a registry / soft bridge; with the map module
    absent the strip is as today.
F.5 Not shown to people who cannot see pay today (keep whatever gates the "Paid by" rows now). Employees (portal)
    never see the dialog.

## Numbered tests (all must pass; names may differ, coverage may not)
Resolver — `pb_scheme_map/tests/test_person_scheme.py`:
- T1 no rows anywhere → every existing answer identical (run the whole existing `TestSchemeMap` unchanged, plus an
  explicit "same answers with and without the new code path" case for none / only / rule / division / team).
- T2 a person row beats their team line, their division and a rule; segment (rung 1) still beats the person row.
- T3 ledger A4: row from the 15th, run judged on the 1st of that month, no earlier row → answered (joiner case);
  with an earlier row of the same kind → the earlier row answers that month and the new one the next month.
- T4 ledger A3: own `regular` row, team has a `mid_cycle` line → asking `mid_cycle` answers none (R7); a person with
  no rows in the same team still gets the team's advance.
- T5 own main + own advance rows → the end / regular run finds main, the advance run finds the advance; `'any'`
  never answers the advance.
- T6 `full_final` falls through to the ladder for a person with rows.
- T7 ended row with no successor → none (listed as not covered), not the team's scheme.
- T8 constraints: overlap per kind, other company's scheme, `full_final`, date order — each with its sentence.
- T9 `pb_scheme_skip_person` restores the old answer.
- T10 `resolve_for_draft` with `scheme_id` (and advance) equals `resolve` for a real person given the same rows, in
  every branch (extend P8's A9); without `scheme_id` unchanged.
Cache — same file or `test_scheme_map.py`:
- T11 create / write / unlink of a row marks only those people stale; recompute writes own scheme, advance,
  `pb_paid_by_own`; `payroll_country` write marks stale.
- T12 the boundary job marks a person whose row starts today and one whose row ended yesterday, nobody else.
- T13 the three advance allow-lists agree; a person advance row shows in `schemes_for_employee`.
- T14 `test_t12_the_ladder_edit_is_guarded` still passes (dependency rail).
Pay run — `pb_payrun_wizard` tests (soft-probe pattern) or `pb_scheme_map`:
- T15 two people in ONE team with different own schemes each land in their own scheme's run population and in no
  other; the "paid elsewhere by their own pay scheme" list names the right one in the team's usual run.
- T16 R6: a change dated the 15th → the run for that month has them under the old scheme, the next month's under
  the new one; never in both, never in neither.
- T17 payslip rung 3 passes its own `date_from` (a payslip without a stamped scheme, row changing next month).
Change route — `pb_scheme_map` tests:
- T18 `person_set` fast lane: rows written as D.2 (end the day before, unlink never-effective, same scheme no-op,
  advance set / removed / kept, main kind switch ends the old kind); idempotent on a second call.
- T19 second-approver route: nothing written until approved; snapshot re-check refuses when the person's rows moved
  in between, with a plain sentence; an audit line is written on apply.
- T20 rights: HR officer can propose and cannot write rows directly; the carry-out gate is unchanged; an employee
  (portal) is refused by `person_scheme` and `person_set`.
- T21 every refusal of D.2 returns its sentence.
Add employee — `pb_new_hire/tests/test_pscheme.py` (+ deliberate updates of `test_p8.py` a4 / a5 / a7 / a9 / a10,
`test_new_hire.py` t04 — list each changed assertion in the report):
- T22 (E-T1) hire with a hand-picked scheme that differs from the team's line → person row written from the first
  day, the person is in THAT scheme's run population and not in the team's.
- T23 (E-T2) advance switch on / off → advance row written / not written; the advance run population follows.
- T24 (E-T3) the Vietnamese-joiner shape: country with one scheme, no team line, a rule that does not match → row
  written, lands in the run; no amber line anywhere in `decides`.
- T25 old payload without a scheme key → row for the resolver's answer when of the Country of work; none → no row,
  hire still succeeds.
- T26 none of the retired sentences is produced by any branch of `decides`; .pot has no dead msgid of that family.
- T27 the hire approval route (second approver) writes the row on approval, not on send.
Screens — static / tour-less checks + browser walks:
- T28 source-level: no user-visible string in the changed files contains "Odoo", "rung", "config", "cycle".
- T29 vi_VN and id_ID carry every new msgid (parse gate passes).
Suites before / after (same-before/after rule, as P8 §4.2): `/pb_scheme_map,/pb_new_hire,/pb_payrun_wizard,
/pb_hr_payroll_formula,/pb_employee_vault,/pb_contracts,/pb_updates,/pb_job_change,/pb_loans,/pb_retro,
/pb_expense_payroll,/pb_pay,/pb_me_tax,/pb_decision_room`. Every "only after" failure is fixed or explained.

## Browser walks (local walk database, Claude-in-Chrome, console read, en + vi, 340 px for the dialog)
- W1 Employee side panel: person without a row ("From <team>'s usual pay scheme") → Change → pick another card →
  date not a 1st shows the R6 sentence → Save (fast lane) → line rewrites; History shows both; reopen: persisted.
- W2 Same on a database / company with a second approver: "Ask for this change" → "Waiting for approval…" on the
  panel → approve as the payroll manager → the panel shows the new scheme.
- W3 Advance: switch on, save, "Mid-month advance" appears; switch off, it goes.
- W4 Contract drawer: strip shows the scheme + date, "Change pay scheme" opens the same dialog.
- W5 Add employee: country with several schemes → pick the non-usual card → no amber anywhere on steps 2 / 3 / Check
  → add → the new person's panel reads "Their own pay scheme since <first day>".
- W6 Run payroll for the team's usual scheme: the W5 person is not in it and is named in "have their own pay scheme
  and are paid elsewhere"; run for the picked scheme: they are in it.
- W7 Dead-ends: country with no scheme (dialog + Add employee), same scheme picked, an HR officer without the
  carry-out right, a narrow screen.
- Console: errors only, every walk — clean.

## Report back — `docs/handovers/pscheme/PSCHEME_P1_REPORT.md`, committed on `pscheme` (not pushed)
1. Result line (GO / NO-GO for P2) and the commit list.
2. What changed on screen, per section A–F, in screen words.
3. Deviations from this handover or the ledger, each with the reason (anything in ledger §2 you could not honour is
   a STOP-and-report, not a silent change).
4. Test table (T1–T29 → test name → pass/fail), suites before / after with every difference explained.
5. Walk table W1–W7 with what you saw; console state.
6. Design bar self-score (hero moment, zero dead-ends, plain language, motion, keyboard) out of 10 each.
7. Seams P2 will need (where "Set for everyone in this team", the fill tool, the Country of work prompt and
   `pb_job_change` plug into what you built) with file:line.
8. Lesson / help sentences that are now untrue (file:line) for P3.
9. New module versions, new xml ids (the cron), new groups / access rules, new msgid counts per language.
10. Gotchas appended to the ledger (PS1 …) and open questions — owner questions in plain non-technical words.

Usage-limit rule: on a 429 or near the limit, commit WIP with a `PAUSED` note in the report and stop.
