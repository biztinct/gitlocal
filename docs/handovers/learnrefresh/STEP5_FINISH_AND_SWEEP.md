# LEARN REFRESH — Step 5: finish every lesson, redo the paths, final sweep

Read first: `LEARN_REFRESH_LEDGER.md` (binding, incl. step 1–4 report sections).

## Scope

A. **Every outline-only lesson becomes full** (what/why/when/prereq/mistakes, 5–9
   steps, check question, glossary, `places`, duration, EN+VI), re-read from today's
   product — the step 2 report lists which remain; expected: insights (Insights ›
   Pulse), explorer, workforcean (Insights › Workforce), govreports (if step 4 did not
   deepen it), fullfinal (Pay Run › Settle), proration + retro (Pay Run › Adjust),
   employees (People › Employees incl. Contracts button + contract drawer Terms /
   Components / History), contracts (fold into employees if it now duplicates —
   keep the key, redirect), structures (Settings › Salary Structures — say plainly
   when a company needs it vs a pay scheme), statutory-adjacent outlines, integrations
   (Settings › Integrations: connections, sync schedule, Arrivals), plus any "short"
   stations from step 4 the report flags as thin. Add Pay Run › Results, Deliver,
   Calendar, Awards (one station "After the run: results, payments, calendar" unless
   the facts justify two) and Insights › Budget / Payroll Report if missing.
B. **Role paths + chapters redone** over the final station set.
   `pb_learn/models/learn_path.py` `ROLE_PATHS`, `ROLE_GUESS`, `MILESTONES` stations;
   Journey `CHAPTERS` in journey.js. Proposal (adjust with evidence):
   - officer: pulse, approvals, runpayroll, payruns, payslips, import, records,
     schemes, treatment, statutory, formula, blueprint, mapping, fullfinal, adjust.
   - approver: pulse, approvals, payruns, payslips, insights, payreview.
   - hr: pulse, employees, records, hiring, joiners, probation, exits, contractends,
     wftime, access (if HR admins hold it), paybands.
   - owner: pulse, approvals, insights, explorer, decisionroom, paybands, filings, matrix.
   - consider a 5th path "people manager" (wftoday, wftime, wfclose, hiring, probation,
     growth, approvals) — add only if the role guess can detect it from groups; say why.
   Chapters: Get around (pulse, approvals, helper) · Run pay · Set up pay · People
   and their journeys · Workforce · Understand and comply. Month-end card and Team
   readiness must work with the new keys; migrate existing progress rows for renamed
   keys (write a migration — risky tier, backups first).
C. **Final sweep (gates — all must be true, prove each):**
   1. Every station: `places` resolves on the live app for an admin; "Open" lands on
      hub › tab.
   2. Every anchor used by content exists in the product (registry test 01 green,
      0 retired anchors referenced).
   3. Every hub tab in the ledger product map has either a lesson or an orientation
      entry — list any tab without a lesson and why.
   4. Zero content strings mention a retired screen name (grep list: "Dashboard" as a
      screen, "Approvals" lanes, "Payroll Officer", "tier", "Setup section", "Overview
      section", "Statutory (Insurance & Tax)", "Import Data" menu, "left menu …
      Setup"). Words-on-screen check vs live labels for 30 random strings.
   5. VI parity: every EN string has VI; banned VI substrings clean.
   6. Ask Payobook: 20 questions across all areas, each answered with today's names and
      a working hand-off; suggested questions refreshed; lesson whitelist == station
      keys.
   7. ⌘K: every station and walkthrough findable.
   8. Glossary: no term defined with an old screen; every term used in lessons exists.
   9. Welcome tour ends on the helper button and touches only live anchors.
   10. pb_learn full suite on a throwaway clone: only the two known environment
       failures (test_learn_hub path artifact, template cron) may remain — or fix them.
D. **Owner-facing close-out**: write `docs/handovers/learnrefresh/LEARN_REFRESH_CLOSEOUT.md`
   (engineering record: what changed per step, commits, versions, open items).

## Non-goals
No product behaviour changes except the progress-key migration and anchors.

## Design
Bar (verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."**
Hero moment: **"Your path" on the Learn map redraws itself when a role is picked** — the
right chapters light, the rest step back, and the continue card names the one next
lesson with its minutes. Zero dead-ends, plain words, motion with purpose, phone width.

## Test cases
The ten gates in C, plus: role switch for each path on the map (EN + VI); Team lens with
two users on different paths; month-end card still renders (fake a calendar row on a
throwaway clone only); milestone baseline still silent; phone width; console clean.

## Deploy
pb_learn (+ any module touched). Tier: **risky** (progress-key migration) — backups of
all 4 DBs first to `/odoo/backups/learnrefresh/`. Restart after purge.

## Report back
As before, plus the gate table (C1–C10) with evidence per gate.
