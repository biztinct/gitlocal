# PSCHEME P2b — job change, upload sheets, hiring offer and pay-data-file joiners follow the person's pay scheme

Read first: `PSCHEME_LEDGER.md` (§0 rules, §1 rulings R1–R9, §2 decisions A1–A15, §4 gotchas — binding),
`PSCHEME_P1_REPORT.md` (§7 seams — **do not re-derive**), `PSCHEME_FACTS.md` (§6.1 rows "Updates sheets", "Job
change / transfer", "Pay data file import", "Hiring offer"; §6.2; §8; §10.1), `docs/handovers/newhire/NEWHIRE_LEDGER.md`
(local databases, walk method), `docs/handovers/updates/` ledger for the sheet conventions.

Worktree `gitlocal-worktrees/pscheme-p2b`, branch `pscheme-p2b` (from `pscheme` HEAD). **Local only: no push, no
release, no live server or database.** A parallel stream (P2a) is changing `pb_scheme_map` (board, fill, team
drawer), `pb_employee_vault`, `pb_contracts`, `pb_employee_form_tidy`, `pb_form_studio_people` and
`contract_fill_in.py`. **Ledger A15: in `pb_scheme_map` you may only ADD new files / methods (plus `__init__`, the
manifest, i18n); never edit a line P1 wrote there. Stay out of the other P2a modules.** Write every person row through
P1's one writer `_person_set_write` (`pb_scheme_map/models/pb_person_scheme_board.py:351`) or its approval door
`person_set` (`:271`).

Rails (ledger §0): design mandate verbatim **"extreme WOW, intuitive, out-of-this-world experience, best in class"**;
Lucide, no emoji; plain screen words (never rung / config / cycle); **never "Odoo" in a user-visible string**;
vi_VN + id_ID for every new string; public repo — no client names / data / credentials; backend needs a screen twin;
dependency rail (modules that do not depend on `pb_scheme_map` reach it by soft probe); no effort on past pay runs.

## Scope
### A. Job change (`pb_job_change`) — a permanent move changes the pay scheme from a date (ledger R5, R6, A9)
A.1 `pb.job.change` (`job_change.py:129-227`) gains "New Country of work" and "New pay scheme" (+ the advance switch,
    P1 D.4 suggestion, A13). The form asks for them only when they matter: picking a new Country of work pre-fills the
    new pay scheme (the country's only / usual scheme; chooser when several); a new company REQUIRES a pay scheme of
    that company (A9). The what-if ("Paid by now → after", `_scheme_now_and_after` `:411-440`) reads person rows
    first and shows the R6 sentence when the effective date is not a 1st: "<Old scheme> still pays <month>. <New
    scheme> starts with the next pay run."
A.2 Apply (`_write_change` `:1035-1160`, scheduled `_start_scheduled` `:1327`, cron `:1360`): writes Country of work
    (it is in no `EMPLOYEE_MAP` today) and the person row(s) with `source='job_change'`, `date_from` =
    `effective_date`; a company move ends the old company's rows the day before FIRST (add a small helper in a NEW
    file in `pb_scheme_map` if the one writer cannot express it — report). The job change's own approval is the
    approval; no second proposal. Undo (`action_undo` `:1432`) restores Country of work and the rows exactly (rows it
    created removed, rows it ended re-opened), refusing with a plain sentence if someone changed them since.
A.3 A team-only change (no country, no scheme asked) never touches person rows — and the form says, once, "Their pay
    scheme stays <scheme>. Change it here if this move changes who pays them."

### B. Upload sheets (`pb_updates`)
B.1 Joiner sheet: "Pay scheme" becomes a VALUE (FACTS §6.1): empty → the Country of work default (only / usual
    scheme; several without a usual → the row asks, with the list in the cell's dropdown); filled → must be an active
    scheme of the row's Country of work (else a red cell with the reason and the allowed names). On apply the joiner
    gets the person row from their first day (`source='import'`), advance per A13 / R7 (a "Mid-month advance" column
    only where the company has advance schemes). `_department_schemes` (`updates_joiners.py:219-268`) no longer
    decides the scheme of anyone; it may only supply the "usual" default.
B.2 Lasting sheet (details / pay): a "Pay scheme" column with the row's start date (`WHEN_TARGET`, `updates_desk.py:65`)
    → `person_set` through the sheet's own approval path; unchanged cell = no change; R6 sentence in the review step
    when the date is not a 1st; a Country of work change in the same row pre-suggests the scheme in review (never
    applied silently, A7).
B.3 Every sheet reader of "which scheme pays these people" stays on `resolve_many` (already per person) — verify
    `_people_schemes` and the year-to-date sheets with two people of one team on different schemes.

### C. Hiring offer (`pb_pay_package/models/offer_total.py:165-176`)
Default scheme = the offer's / requisition's Country of work (only / usual scheme), the team's usual scheme only as
the tie-break — the same answer Add employee gives (`pb_new_hire/models/studio.py:487` `_scheme_for`; share, do not
copy, if the dependency direction allows; else mirror and test equality).

### D. Pay data file creating a person (`payroll_import_batch.py:1739,1815`)
When a pay data file creates an employee, also write the person row for the batch's scheme (`source='import'`, from
the first day of the batch's period) through a soft probe (the formula module never depends on `pb_scheme_map`).
An existing person paid by a file whose scheme differs from their own row is NOT changed — the batch review says
"N people in this file have another pay scheme of their own" with the names (soft probe; quiet at zero).

## Binding non-goals
Mapping board, fill tool, team drawer, Country of work prompt on forms, contract currency (P2a). `pb_learn`, release
(P3). Dating Country of work. Two-country split. `pb_demo`.

## Numbered tests (coverage binding, names free)
- T1 job change with new country + scheme, effective today: Country of work written, old row ended the day before,
  new row from the date; pay-run population for next month = the new scheme only.
- T2 effective the 15th: that month's run still has the person under the old scheme, next month's under the new (R6).
- T3 scheduled (future) change: nothing until the cron day; then as T1.
- T4 company move: old company's rows ended first; a scheme of the old company refused with its sentence; new row OK.
- T5 undo: exact restore; refused with a plain sentence after a later hand change.
- T6 team-only change: no row touched; `test_jc12_paid_by_what_if_is_read_only` updated deliberately (list it).
- T7 what-if reads person rows first (person with own scheme moving team: "stays <scheme>").
- T8 joiner sheet: empty cell default (one scheme) · several with usual · several without usual asks · wrong-country
  scheme red with reason · apply writes the row from the first day · advance column on / off · the joiner lands in
  that scheme's run population.
- T9 `test_H6_pay_scheme_column` and the `test_updates_p2b` fixtures updated deliberately (list each assertion).
- T10 lasting sheet: scheme cell changed + date → proposal → rows; unchanged → nothing; country change pre-suggests.
- T11 readers: two people of one team on different schemes → each sheet reader names the right scheme.
- T12 offer default follows Country of work; equals Add employee's answer in every branch.
- T13 pay-data-file joiner gets the row; existing person with another own scheme untouched and listed.
- T14 rights: each path refuses a portal user; no new direct write access on `pb.person.scheme`.
- T15 static: no "Odoo" / rung / config / cycle in new strings; vi_VN + id_ID complete (parse gate; `pb_contracts`
  has no id file — not yours).
- T16 dependency rail test and P1's 63 tests still pass.
Suites before / after as P1, plus `/pb_pay_package`; every difference explained.

## Browser walks (local, Claude-in-Chrome, console read; en + vi)
- W1 Job change: pick a new Country of work → scheme pre-fills → what-if with the R6 sentence → approve → the
  person's Pay scheme block shows "Changes to <scheme> on <date>" / the new scheme; Undo → back.
- W2 Company move requires the scheme; refusal sentences.
- W3 Joiner sheet: default, a red wrong-country cell, the dropdown, apply → the new person's panel.
- W4 Lasting sheet: change a pay scheme with a date → review sentence → apply (and the second-approver lane).
- W5 Hiring offer for another country than the team's usual → the offer total uses that country's scheme.
- W6 Pay data file with one new person and one person who has another own scheme → the review line.
- Console clean on every walk.

## Report back — `PSCHEME_P2B_REPORT.md`, committed on `pscheme-p2b` (not pushed)
Result (GO / NO-GO for P3) + commits · what changed on screen per section · deviations with reasons (ledger §2
breaches are STOP-and-report) · T and W tables · suites before / after · design bar self-score · every file you
touched in `pb_scheme_map` (for the merge) · lesson / help sentences now untrue · versions, msgid counts · gotchas
appended to the ledger (prefix your entries "PS-b") · owner questions in plain non-technical words.
Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. On a usage limit: commit WIP + PAUSED.
