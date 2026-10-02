# LEARN REFRESH — Step 6: close the owner's open items

Owner instruction 2026-09-28: "Fix the items you mentioned for 'Still open, for you to
decide' and then commit." Read `LEARN_REFRESH_LEDGER.md` (binding rules, LR1–LR53) and
`LEARN_REFRESH_CLOSEOUT.md` first. Investigate each item in code before changing it;
if an item turns out different from the description, fix the real thing and say so.

## Items (do in this order; commit each when validated)

1. **Reject on the pay runs board asks for a reason.** `pb_payruns` in-card confirm
   ("Reject "X"? Every payslip in this batch is cancelled." → Keep it / Reject run):
   add a required "Why?" field; store it in `pb_reject_note` (same field the inbox
   turn-down uses); show it on the rejected card and run form. Unit test + update the
   Runs lesson/intents that say no reason is recorded.
2. **"Need review" flags a big pay change.** Today it counts only net ≤ 0, people it
   couldn't pay, people not in Payobook. Add: net pay differs by more than a threshold
   from the same employee's previous end-of-cycle payslip in the same scheme (skip when
   there is no previous payslip, i.e. joiners). Threshold = a Payroll defaults setting
   (config parameter), default 30%. Flag carries a plain reason ("Net pay up 42% on
   June"). Must show in Run's Review exceptions + pills, and Payslips' "Need review"
   chip/KPI (both counters must agree — one shared method). Compute cost: one query per
   run, not per slip. Unit tests (up, down, joiner, threshold setting). Update the Run +
   Payslips lessons, practice screens and intents that now say "a person has to spot
   it" (restore the flag teaching, with today's numbers from practice-data.js).
3. **Auto-created final settlements stuck at "Being prepared".** Find what creates them
   when a month's pay data finishes loading and why nothing moves them on. Do NOT
   auto-submit for approval (money must be looked at). Fix: once their figures are
   computed they reach the same state a hand-made settlement reaches when ready; Pay Run ›
   Settle and Lifecycle › Exits show them under a "ready to check" count with a Send for
   approval action; the payroll officer(s) get one notification per load naming how many
   are waiting. If a settlement can't be computed, it says why. Tests. Update the Exits /
   Settle lessons.
4. **Growth plans visible to administrators.** Lifecycle › Growth plans currently needs a
   growth-plan role with no admin fallback. Give system administrators the same read +
   act access as the PIP head (record rules + lens gate + probe + palette), consistent
   with the other Lifecycle tabs. Update the Access role catalogue if needed (tab-gate
   memory note: `pb_vendor_access/hooks.py` CATALOGUE). Tests.
5. **Untranslated screens → Vietnamese** (owning modules' vi_VN.po + stored values where
   applicable, LOOK L24; PO loading rules): Pay Run › Adjust and Settle numbers and
   labels, the contract drawer (Terms / Components / History), Insights › Payroll Report,
   Settings › Integrations connection screen, Pay Run › Calendar, Pay Run › Awards. Also
   the Access screen's role names/descriptions (stored records — translate the stored
   jsonb for vi_VN, and make new catalogue roles carry VI). Also repair the 59 broken
   entries in the two old payroll .po files (39 + 20) found in step 5. Then switch the
   affected lessons from "the screen shows the English label" wording to the VI labels.
   Parse-gate every .po. List before/after counts per module.
6. **Demo company pay runs go through approval.** On payobook (demo world) the pay-run
   route resolves to "no approval needed", so a submitted run finishes at once. Give the
   demo company the real three-step route (Payroll check → HR lead review → Finance
   approval) with seats filled by demo users so the demo login can walk a run through
   it (the demo login should hold at least the first seat; say who holds each).
   Make it part of the demo world's seed (pb_demo / pb_demo_seed, idempotent, survives
   regeneration), not a hand edit. payobook only — tenants keep their own matrices. Do
   not touch the April/May/June demo runs' states.
7. **Demo world gets leavers, a pay review and people on trial** so walkthroughs show a
   live example: a few employees in Exits (one at each step, one settlement), one open
   pay review with scored rows (budget meter mid-way, one row that stops approval), 3–4
   people on probation at different steps, one growth plan, one contract ending within 60
   days, one hiring role past step 2 if missing. Via the demo seed (DEMO naming rule —
   no "RIZE" in demo records, register with pb_demo_seed), idempotent, payobook only.
   Then re-point the walkthrough steps that were downgraded to "describe the screen" back
   to live anchors where the data now exists.
8. **QA login access.** On payobook only, give `qa.test@payobook.com` the groups that
   open Pay Run › Payslips, Settings › Formula Engine, Mapping and People › Records (read
   the gates; smallest groups that open them; via the Access screen's role catalogue if a
   role fits, else groups). Record what was granted in the report. Update the memory note
   `payobook-qa-login.md` (in /Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/memory/)
   with what the login can now open — never write its password anywhere else.
9. **Small things:** streak badge "1 days in a row" → proper singular/plural in EN and VI;
   the "Practice mode" card squeezes its text into a narrow column on phones — fix the
   layout at ≤ 600px.

## Rules
Everything in the ledger's standing rules (no "Odoo" on screen, plain words, EN+VI, no
credentials, explicit `git add`, commit message trailer
`Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`, never push).
Tier: **risky** (pay logic, security, demo data) — back up all 4 DBs to
`/odoo/backups/learnrefresh/step6/` first; rehearse on a throwaway clone; drop it after.
Wrap every remote command in `timeout`. Browser-validate each item on payobook.com
(Chrome MCP, standing approval). Design bar applies (verbatim): **"extreme WOW,
intuitive, out-of-this-world experience, best in class."**

## Report back
Per item: what the real cause was, what changed on screen, tests, commit hash. Versions
per DB. Anything you could not fix and why. Append gotchas to the ledger (LR54+) and add
a "Step 6" section to the closeout.
