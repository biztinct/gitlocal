# NEWHIRE P7 — Country of work first; bank fields follow the country

Owner request 2026-11-25 (late evening, after using the live screen on rize), verbatim intent:
1. Step 2: "move the field country of work to the very beginning, so that based on the value of that field the
   remaining fields get populated. For example country of work India → the teams should be only those belonging to
   India. Same with job. And below, in 'What this decides', the currency should change, etc."
2. Step 5 bank account: "depending on the country of work, also allow the user to fill in e.g. IFSC if it is India, or
   code if it is Singapore, etc. Whatever is the standard format of that country."

Read first: `NEWHIRE_LEDGER.md` (binding; D2 "the team decides the pay scheme, country is checked against it" is
AMENDED by this phase — see §1.4), P1 and P3a reports (step 2 and step 5 as built), `NEWHIRE_FACTS_CORE.md` (team →
scheme → country plumbing), `NEWHIRE_FACTS_ONBOARD.md` §D (bank: `pb.bank.change.request`, `_pb_hold_new_hire`,
`pb.bank.registry`, OCR) and §M, `NEWHIRE_P6_REPORT.md` (the release you repeat). Fresh worktree from `origin/19.1`.

Design mandate, verbatim: "extreme WOW, intuitive, out-of-this-world experience, best in class". Lucide icons, no
emoji. White-label: never "Odoo" in a user-visible string. Plain screen words. No client data/credentials in the repo.

## 1. Step 2 — country leads
1.1 Field order: **Country of work · Team · Job · Manager · Work site** (+ More). Intro line rewritten: pick the country
    first; teams, jobs, currency, trial period, letter and papers follow it. Step title/summary lines adjusted.
1.2 Default country: the company's country when the company works in one country; otherwise the country most of the
    company's active people work in; the user's last pick in this browser session wins over both. Country list: countries
    the company already has people, schemes or papers lists for come first ("Where you already have people"), then the
    rest, searchable.
1.3 **Which teams "belong" to a country** (establish from the code, state in the report; expected rule): a team belongs
    to country C when (a) the pay scheme that pays it (`resolve_for_team`) is for C, OR (b) at least one active person
    in the team has Country of work C, OR (c) the team carries an explicit country if such a field exists. The Team
    picker shows the teams of C first. Teams with NO signal at all (new/empty team, no scheme) must stay reachable —
    under a quiet divider "Other teams" — so nobody is ever stuck (rize today: 32 teams, none linked to a scheme; the
    people signal (b) must make its lists sensible). Teams that clearly belong to ANOTHER country are hidden behind
    "Show teams from other countries". Zero teams for C → calm empty state with that same link. One server call
    `pb.new.hire.places(country_id)` returns teams, jobs, managers, sites, and the "decides" block — no N+1; measure on
    a rize-sized copy (<300 ms).
1.4 Jobs: jobs tied to the chosen team first (job's own team), then jobs already held by people working in C, then
    "Other jobs". Same never-stuck rule. Manager and Work site suggestions follow team and country as today.
1.5 Changing the country AFTER a team/job is chosen: if the team still belongs → keep; otherwise clear team (and job
    if it no longer fits), with a one-line inline notice "Team cleared — <team> has no one in <country>" and an Undo
    link (restores both). Never silently keep a mismatching pair. The old "country differs from the team's pay scheme"
    warning + one-click fix remains for the cases that can still arise (team picked from "other countries").
1.6 "What this decides" updates the instant the country changes (currency, trial period, contract letter, papers
    needed) even before a team is chosen; the Pay scheme tile reads "Pick a team" until then (not the amber warning).
    Right panel follows. Sequence-guard replies; no flicker.
1.7 Entry points that prefill a team (org chart "add a person here", From Hiring, Hiring's "Confirm they joined")
    derive the country from that team by the same rule (scheme country → majority of the team's people → default) and
    keep both.
1.8 Server validation unchanged in substance: any team/country pair remains ACCEPTED by the create path (filtering is
    guidance on screen, not a new refusal) — prove with a test that older drafts and payloads still apply.

## 2. Step 5 — bank details in the country's own format
2.1 First establish what exists (FACTS §D; `pb_bank_ocr`, `pb_employee_bank_panel`, `/my` bank form, country payroll
    modules' bank-file exporters): which fields the bank change request and the bank account record already carry
    (bank, branch, bank code / BIC, IFSC-like fields, holder name) and what each country's bank file actually reads.
    **The format table must be ONE shared definition** used by the studio, by the employee's own bank form on My
    Payobook (welcome link), and by the side panel's bank form — the owner's standing rule: what HR can type, the
    employee must be able to type too. Put it where the bank request model lives (extending `pb_bank_ocr` is allowed —
    version bump, upgrade ×5); only add stored fields that are genuinely missing, on the request AND carried to the
    bank account on approval.
2.2 Formats (verify each against the country module's exporter and public standard; correct me in the report):
    | Country | Fields beyond bank + account number + name | Checks |
    |---|---|---|
    | India | IFSC code (required) | `^[A-Z]{4}0[A-Z0-9]{6}$`; account 9–18 digits; bank auto-suggested from IFSC's first 4 letters when the registry knows it |
    | Singapore | Bank code (4 digits) + Branch code (3 digits) | account 7–14 digits; bank code filled from the chosen bank when known |
    | Malaysia | none required; SWIFT/BIC optional | account 7–17 digits |
    | Indonesia | Branch (optional), bank code (3 digits, from bank when known) | account 8–16 digits |
    | Vietnam | Branch (optional) — keep today's bank dictionary | account 6–19 digits (today's) |
    | Thailand | Branch code (optional, 4 digits) | account 10–12 digits |
    | Cambodia | none; SWIFT optional | account 6–16 |
    | Australia | BSB (6 digits, shown NNN-NNN) | account 6–10 digits |
    | anything else | SWIFT/BIC (optional) and IBAN accepted in the account box | generic 5–34 |
    Labels in the country's own words ("IFSC code", "BSB", "Bank code", "Branch code"), a one-line hint under each
    ("11 characters, on the cheque book or bank app"), format-as-you-type (uppercase IFSC, BSB dash), inline plain
    errors, never a blocking modal. Bank picker lists that country's banks first where the registry has them.
2.3 The second-person approval card and the Bank requests list show the new fields; the payroll-ready check treats a
    country's REQUIRED code as part of "bank on record" only for NEW requests (never turn existing complete people red:
    prove on a copy that payroll-ready counts are unchanged ×5).
2.4 OCR / From Hiring bank paper: map a read IFSC/BSB/bank code into the new fields when the reader returns one;
    otherwise unchanged.
2.5 Bank file exporters: where an exporter already reads a code from somewhere else (e.g. `res.bank` BIC), keep ONE
    source of truth — write through to it, do not create a parallel field. Report per country.

## 3. Also
- vi_VN / id_ID for every new string (PO rules, LOOK rule); Learn: the `sc_people` lesson + replica + anchors follow the
  new field order (lessons follow screen changes; mind the vi_VN.po wipe trap).
- Tests: C1 places() rule a/b/c + other-teams + never-stuck (company with zero links); C2 country change clears/undo;
  C3 default country; C4 prefill entry points; C5 old payload still applies; C6 performance; B1 each country's
  validators (good/bad samples); B2 fields carried request → account on approval; B3 same definition serves studio,
  /my form and side panel; B4 payroll-ready counts unchanged for existing people; B5 exporter reads the new value
  (India at least); B6 hiring/OCR mapping; static no-"Odoo" test still green. Full `pb_new_hire`, `pb_bank_ocr`,
  `pb_me_*`, `pb_learn` suites before/after.
- Walks (Claude-in-Chrome, local): W1 pick India → only India's teams/jobs, tiles in INR; switch to Singapore → team
  cleared + Undo; W2 company with no links (rize-shaped) is usable; W3 bank in India (IFSC), Singapore, Australia,
  Malaysia, Vietnam — good and bad input; W4 approve → bank account carries the code; W5 employee's own welcome-link
  bank form shows the same fields at phone width; W6 org chart prefill; W7 340 px; W8 vi + id; W9 console clean.

## 4. Release (same window, risky-tier ritual exactly as P6)
Merge to 19.1, push; `-u` `pb_new_hire` + every other touched module on ALL FIVE (payobook_template → p0clone →
sudima → rize → payobook). Deploy notes (the DOCSTUDIO session is shipping a contract-letter fix tonight — wait on
any open START/HOLD), flock, quiet check, job counts, backups ×5 twice, rehearsals on hidden copies of rize AND
payobook (jobs + mail off at once; dropdb --force after), rollback plan before the stop. Never `abm`, never
`_test_sudima_policy_20261119`. Create nothing on client sites. Verify as P6 + on the hidden rize copy: Malaysia →
team list is sensible, bank form shows Malaysia's fields; India → IFSC.

## Report back — `NEWHIRE_P7_REPORT.md` (+ ledger: amend D2, new gotchas; closeout §1), committed + pushed on 19.1
Final message: short plain summary — what changed on screen, tests/walks, live or not per site, downtime, the team
rule as built, the bank format table as built (and where it differs from §2.2), open questions.
