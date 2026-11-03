# FILLIN — closeout (2026-11-04)

Both phases are live on `payobook`, `payobook_template`, `p0clone`, `rize`.

| Phase | Commits | Modules (versions) | Report |
|---|---|---|---|
| P1 server | code inside `ef836533e` (FI11), report `ec4d01b9e` | pb_hr_payroll_formula, pb_scheme_map | `FILLIN_P1_REPORT.md` |
| P2 screens | `e1bce1180`, `1207a1456`, `12e57634d`, `671bf55d5`, `9807cd1aa`, report `d4eb7e057` | pb_contracts, pb_learn, pb_employee_vault, pb_payruns 19.0.3.3.1, pb_payrun_wizard, pb_formula_studio | `FILLIN_P2_REPORT.md` (23 shots in `p2_shots/`) |
| Side stream CONTRACTLIFE SCOPE | `edf9154a9`, `eb94d25a9`, `ef01df40a` (lesson) | pb_contract_lifecycle 1.3.2, pb_learn 19.0.20.8.4 | `../CONTRACTLIFE_SCOPE_REPORT.md` |

## What a reader sees now
* A new contract for a person paid by a scheme starts with that scheme's
  usual answers (rize Indonesia: BPJS TK Yes, BPJS health Yes, Tax allowance
  "Insurance-premium tax only"; Pays back BPJS stays No).
* Contract panel › Components: words and Yes/No switches instead of "Rp1";
  amber "Filled in · not checked" tags; **All correct**; History sentences.
* Contracts list › **To check** tab; answers as chips on the card; **Looks
  right** / **Change**; **All N look right** with a confirm naming people.
* Employee panel chip "N answers to check" → opens the contract.
* Pay run card: amber advisory (does not block); Run Payroll window: count
  of people with unchecked answers.
* Setup (studio) component editor: **Usual answer for a new contract** and
  **Words for each value**.

## Open items
1. **Test contract 3650 (Aradea Putra Suriya, draft, rize)** — created for
   T3 with BPJS TK and Tax allowance changed during testing. Owner decides:
   delete, or keep and reset TK=Yes / Tax mode=Insurance-premium tax only.
2. **Pay run card advisory has no door yet** (kept out of the run screen
   while the PAY RUN SCREEN session owns it). Add `next` → Contracts › To
   check once that session has shipped.
3. **New contract dialog** says "No contract exists yet" after creating one
   at once; the Contracts list's own **New contract** button opens the
   dialog with no person field (FI14, `pb_people_advanced` wizard). Not a
   FILLIN bug; worth a small fix.
4. **Pay data file column note** — add "1 = Yes, 0 = No" / the words to the
   note of a rule with labels (P2 C4, skipped: no single small seam found).
5. **Contract category** on rize: all 210 contracts read "Vietnam Permanent
   Monthly"; fix by scheme country once the client confirms (workbook tab 3).
6. Learning: a lesson replica of the contract panel was updated (A5); the
   To check tab and the chip have no lesson yet.
