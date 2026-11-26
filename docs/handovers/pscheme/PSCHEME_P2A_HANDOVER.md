# PSCHEME P2a — Mapping re-worded, "Set for everyone in this team", the one-time fill, Country of work prompt

Read first: `PSCHEME_LEDGER.md` (§0 rules, §1 rulings R1–R9, §2 decisions A1–A15, §4 gotchas PS1–PS9 — binding),
`PSCHEME_P1_REPORT.md` (§7 seams — **do not re-derive**), `PSCHEME_FACTS.md` (§5, §6, §9, §11, §12),
`docs/handovers/newhire/NEWHIRE_LEDGER.md` (local databases, walk method), NEWHIRE P8 report §1 B and §3 (the
"Suggest who pays each team" drawer — the look and the rails to clone).

Worktree `gitlocal-worktrees/pscheme-p2a`, branch `pscheme-p2a` (from `pscheme` HEAD). **Local only: no push, no
release, no live server or database.** A parallel stream (P2b: job change, Updates sheets, hiring offer, pay-data-file
joiners) is working in another worktree — stay out of `pb_job_change`, `pb_updates`, `pb_pay_package` and
`payroll_import_batch.py`.

Rails (ledger §0): design mandate verbatim **"extreme WOW, intuitive, out-of-this-world experience, best in class"**;
Lucide, no emoji; plain screen words (never rung / config / cycle); **never "Odoo" in a user-visible string**;
vi_VN + id_ID for every new string; public repo — no client names / data / credentials; backend needs a screen twin;
dependency rail; no effort on past pay runs; demo fixtures prefixed DEMO.

## Scope
### A. Mapping "Who is paid by what" says the truth
A.1 A team line reads as the team's USUAL pay scheme: row chip, attach dialog text
    (`pb_scheme_map/static/src/xml/scheme_map.xml:337-339`), "Everyone in this part of the business will be paid by
    the scheme you pick…" → "New people in <team> start on this pay scheme. People with a pay scheme of their own keep
    it." Board header gets one calm line: "Each person has their own pay scheme. A team's usual scheme is the starting
    point for new people and for anyone without one."
A.2 Each team row shows two small counts: "N on the usual scheme" and "M have their own" (M opens the names with
    their scheme and since-date). Coverage reason sentences (`pb_scheme_map.py` coverage, FACTS §8 row 1) gain "has
    their own pay scheme". "Nobody pays these people yet" (`scheme_map.xml:571-580`) offers both fixes: give them a
    pay scheme (opens the fill drawer filtered to them) or set their team's usual one.
A.3 "Waiting for approval" for many-person requests: extend `_person_waiting`
    (`pb_person_scheme_board.py:563`) so a person inside a waiting team / fill request shows it on their panel.

### B. "Set for everyone in this team…" (ledger R8)
B.1 Second action on a team row beside attach. Drawer: the pay scheme (default the team's usual; chooser of active
    schemes, the team's majority Country of work first), the mid-month advance switch (P1 D.4 suggestion; A13), then
    the people of this team and the teams below it that have no usual scheme of their own:
    - "Without a pay scheme (N)" — ticked, start = the first day of the current month;
    - "Already have their own (M)" — one unticked master tick "Also move these M people" with a From date (default
      the 1st of next month, R6 sentence under it), each row showing today's scheme → the new one;
    - people whose Country of work is not the scheme's country are shown unticked in both groups with the reason.
    Shift-range ticks, select all / none, a live sentence "12 people will be paid by <scheme>: 9 from 1 Nov 2026,
    3 from 1 Dec 2026." Button "Set for N people" / "Ask for this change" by lane.
B.2 Server: ONE many-person `person_set` proposal (source `team`) through P1's door (`person_set` `:271`,
    `_person_set_write` `:351`); two dates = two payload groups in one proposal; snapshot re-check per person with
    P1's plain sentence; never `accept_draft` (FACTS T13). Never writes or changes a team line.

### C. The one-time fill — "Give everyone their pay scheme" (ledger R3)
Hero moment (name it in the report): **one drawer turns "313 people, nobody has their own pay scheme" into
"All 313 people have a pay scheme" — every person listed with who pays them today, grouped so that the safe ones are
one press and only the real questions need a choice; and "Undo this fill" is still there the next day.**
C.1 Entry: a banner on the Mapping board while anyone active has no row ("N people still follow their team. Give
    everyone their own pay scheme"), and a quiet menu entry afterwards. Drawer cloned from P8's suggest drawer.
C.2 Plan (server `pb.scheme.board.fill_plan(company)`; paged / grouped — must stay fast at 5,000 people, one
    `resolve_many` per kind with `SKIP_PERSON` + `MAIN_QUESTION`, no per-person query):
    | Group | Who | Default |
    |---|---|---|
    | Ready | today's answer is a scheme of the person's Country of work | ticked → that scheme (+ advance only per A13) |
    | From Country of work | nobody pays them today; their country has exactly ONE active scheme | ticked → that scheme |
    | Check these | today's scheme is of ANOTHER country than their Country of work | unticked; both options shown, pick per person or for the whole group |
    | Needs your choice | nobody pays them and the country has several schemes / none; or no Country of work | no default; several → pick (bulk pick per country); none / no country → the reason + its fix (link to Mapping / to "Fill empty Country of Work", which must be run FIRST — FACTS T10) |
    | Already have their own | has any row | never touched; count only |
    Grouped by country then team with counts; rows virtualised or paged; search by name; summary line live.
C.3 Start date of every filled row = the first day of the current month. `source='fill'`.
C.4 Apply: ONE proposal (kind `person_set`, source `fill`, or a sibling kind if cleaner — report) through the same
    route; fast lane writes at once. A fill log (`pb.person.scheme.fill`: who, when, company, counts, the row ids
    created) cloned from `pb.cow.fill.log`. Re-running is safe: people who got a row are "Already have their own".
C.5 **Undo on screen**: "Undo this fill" on the latest fill of a company removes exactly the rows that fill created
    and nobody changed since (changed ones are kept and named); through the same approval route; logged.
C.6 A callable for P3's release script with the same semantics: `fill_plan` + `fill_apply(tick=group names)` so the
    live fill runs the product's own path (dry mode = build the plan, write nothing).

### D. Country of work prompt (ledger R4, A7, A14)
D.1 The universal net: `person_scheme` (P1 read API `:429`) returns `country_mismatch` when the person's counting
    main scheme is of another country than their Country of work (and no later row or waiting change fixes it). The
    Pay scheme block (side panel, contract strip) and the "Paid by" chip show ONE amber line: "<Name> works in
    Singapore but is paid by Vietnam Monthly. Change pay scheme" → P1's dialog preselected to the country's usual /
    only scheme, From = the 1st of next month. Mapping board: "N people are paid by a scheme of another country than
    their Country of work" → the list, each with the same action (and a bulk "Change these N" when one target fits).
D.2 The prompt on save: on the native Full details form and the employee workspace Pay tab (FACTS §6.1 rows 2–3),
    when a save changed Country of work and D.1's mismatch is now true, open the dialog straight away with the
    sentence "Country of work is now Singapore. Change the pay scheme too?" — "Not now" keeps the amber line. One
    shared hook (`openChangePayScheme`, `person_scheme.js:330`); with `pb_scheme_map` absent nothing happens.
    Records Desk / sheets / imports are covered by D.1 only (report them as such).

### E. The contract follows the scheme (FACTS T6, T7)
E.1 When a person row of a MAIN kind takes effect (written with `date_from <= today`, or reached by the daily
    boundary job) and its scheme's country differs from the open contract's `payroll_country`: set the contract's
    `payroll_country` to the scheme's country (currency follows by the existing compute) and fill the new scheme's
    usual answers through the FILLIN path (`contract_fill_in.py`, the "newly known" hook `hr_employee.py:177-187` —
    extend "newly known" to "scheme changed"). Soft probes; idempotent; never deletes old component lines (report what
    stays). Never rewrites wage amounts: the panel then says "Their contract is now in SGD. Check their pay amounts."
    with a link to the contract (shown until the wage is edited or the note dismissed — cheapest honest form; report).
E.2 The dialog says so before saving when the picked scheme is in another currency: "This also changes their
    contract's currency to SGD from <date>."

## Binding non-goals
`pb_job_change`, `pb_updates`, `pb_pay_package`, pay-data-file import (P2b). `pb_learn` lessons, release, the live
fill (P3). Two-country split. `pb_demo` runs. Rewording or changing the rules of "Suggest who pays each team" beyond
its title sentence saying it sets teams' USUAL schemes.

## Numbered tests (`pb_scheme_map/tests/test_p2a_*.py`; coverage binding, names free)
- T1 board payload: usual / own counts per team; own list; coverage reasons.
- T2 team drawer plan: three groups, country-mismatch rows unticked, sub-teams with their own usual scheme excluded.
- T3 team apply fast lane: only ticked people; fills from the 1st of this month, moves from the given date (old row
  ended the day before); advance per A13 / R7; no team line created or changed; idempotent.
- T4 team apply with a second approver: nothing until approved; one moved person in between → that person refused
  by name, the rest applied (or the whole request refused — state which and why); waiting shows on each person's panel.
- T5 fill plan groups: Ready / From Country of work / Check these / Needs your choice (several, none, no country) /
  Already have their own — one fixture person each, plus the A13 case (team line "any kind" → no advance row).
- T6 fill apply: rows = plan; `source='fill'`, date = first of month; second run writes nothing; after it, every
  filled person's answer WITH the person rung equals their answer before (Ready group) for main and advance.
- T7 fill at size: 5,000 fixture people plan in bounded queries (assert a query-count ceiling) and under a stated time.
- T8 undo: removes exactly the fill's untouched rows; a row changed since is kept and named; log written; answers
  return to the team ladder.
- T9 `fill_plan` / `fill_apply` dry mode writes nothing.
- T10 mismatch: true / false / fixed by a later row / fixed by a waiting change; the board list and count.
- T11 contract follows: row effective today → contract country + currency + usual answers of the new scheme; future
  row → nothing until the boundary job day, then the same; same-country change → contract untouched; idempotent.
- T12 rights: HR officer can propose B and C, cannot carry out; portal user refused everywhere; payroll manager both.
- T13 static: no "Odoo" / rung / config / cycle in new strings; vi_VN + id_ID complete (parse gate).
- T14 dependency rail test and P1's 63 tests still pass.
Suites before / after as P1 (same list), every difference explained.

## Browser walks (local, Claude-in-Chrome, console read; en + vi; drawers at 340 px)
- W1 Mapping board: usual wording, counts, own list.
- W2 Team drawer: tick ranges, the master tick + date + R6 sentence, apply (fast lane), counts move.
- W3 Fill on a company with ≥ 200 people: groups, bulk pick in "Needs your choice", search, apply → "All N people
  have a pay scheme"; banner gone; a person's panel reads "Their own pay scheme since 1 <month>".
- W4 Undo this fill → banner back, panel back to "From <team>'s usual pay scheme".
- W5 Second-approver database: fill → "Sent for approval" → approve → done.
- W6 Change Country of work on Full details → the prompt → change → no amber; "Not now" → amber line on panel, strip
  and chip; Mapping's mismatch list → bulk change.
- W7 Scheme of another currency: dialog warns; after save the contract shows the new currency and the "check their
  pay amounts" note.
- W8 Dead-ends: empty team, country with no scheme, nobody to fill, an HR officer without the carry-out right.
- Run payroll after the fill for two schemes of one team: each person in exactly one run.

## Report back — `PSCHEME_P2A_REPORT.md`, committed on `pscheme-p2a` (not pushed)
Result (GO / NO-GO for P3) + commits · what changed on screen per section · deviations with reasons (ledger §2
breaches are STOP-and-report) · T and W tables · suites before / after · design bar self-score · the exact call P3's
release script must make for the dry and real fill, and the counts it prints · lesson / help sentences now untrue ·
versions, xml ids, msgid counts · gotchas appended to the ledger (continue the PS numbering from the ledger's last,
prefix your entries "PS-a") · owner questions in plain non-technical words.
Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. On a usage limit: commit WIP + PAUSED.
