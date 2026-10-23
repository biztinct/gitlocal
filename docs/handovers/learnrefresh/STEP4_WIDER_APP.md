# LEARN REFRESH — Step 4: lessons for the rest of the app

Read first: `LEARN_REFRESH_LEDGER.md` (binding, incl. step 1–3 report sections) and
`FACTS_STEP4_WIDER_APP.md` (verified labels/flows). Do not re-derive.

## Scope — new stations and lines

New map lines (add to `line_order` and to the Journey `CHAPTERS` grouping in
`pb_learn/static/src/journey/journey.js` so they show; step 5 finalises chapters):
`lifecycle`, `workforce`. Existing lines get new stations.

| Key | Name | Line | Where | Depth |
|---|---|---|---|---|
| paybands | Pay bands and fairness | people | People › Pay (Bands, Fairness) | full |
| payreview | Pay review and pay changes | people | People › Pay (Review, Changes) | full |
| decisionroom | Decision Room | people | People › Plan | full |
| hiring | Hiring | lifecycle | Lifecycle › Hiring | full |
| joiners | New joiners | lifecycle | Lifecycle › New joiners | full |
| exits | Exits and final settlement | lifecycle | Lifecycle › Exits (+ Pay Run › Settle) | full |
| probation | Probation | lifecycle | Lifecycle › Probation | full |
| growth | Growth plans | lifecycle | Lifecycle › Growth plans | short |
| contractends | Contracts ending | lifecycle | Lifecycle › Contracts | short |
| wftoday | A day in Workforce | workforce | Workforce › Today + Needs you panel | full |
| wftime | Time, time off and overtime | workforce | Workforce › Time, Time Off, Overtime | full |
| wfclose | Close the week | workforce | Workforce › Close | full |
| access | Access and delegation | setup | Settings › Access & delegation | full |
| filings | Government filings | compliance | Compliance › Filings (+ Generate a filing) | full (replaces/extends govreports — keep the govreports key, rename + deepen it rather than duplicate) |
| compliancemore | Bank checks, young workers, audit | compliance | Compliance › Bank, Young workers, Audit | short |
| peoplemore | The rest of People and Home | people | Home › Wall, Announce; People › Where they work, Assets, Praise, Goals | short |

"full" = what/why/when/prereq/mistakes, 5–9 steps, check question, glossary, role tags,
`places`, duration. "short" = the outline set + 3 steps. EN + VI.

**Visibility honesty.** Many of these tabs are gated (groups or `probe`). A lesson for
a screen the learner can't open must say so plainly on the map card ("You don't have
access to this in your company — you can still read the lesson") and its "Open the real
screen"/Watch must not dead-end (step 1 built the no-access ending — reuse it). Reuse
the same gates the hubs use; never copy group lists into content.

**Practice company.** Replica screens only for: Hiring board (step strip + Next box +
request wizard), Pay review worksheet (budget meter + calibration marks), Exits board
(four desks → settlement), Close the week (flags → Lock week & send to payroll). Others
teach on the real app. Keep replica screens compact, fixture-driven.

**Real-app walkthroughs + anchors.** None of these modules has anchors (only Filings).
Add `data-coach` anchors for every full station's hero flow in the product templates
(prefixes: `pp-` pay, `dr-` decision room, `hi-` hiring, `nj-` joiners, `ex2-` exits,
`pr-` probation, `wf-` workforce, `ac-` access, `cp-` compliance), rendering in hub
mode, registered in anchors.json. One Watch walkthrough per full station. Walkthroughs
never save anything.

**Helper, ⌘K, Ask Payobook, glossary.** `places` for every station; ⌘K rows appear;
intents for the top question of each area (e.g. "how do I raise a hiring request",
"who has to sign a pay review", "how do I lock the week", "give someone access while I'm
away", "file the monthly insurance report"); Ask Payobook prompt paragraph per area +
whitelist; glossary terms (Pay band, Compa position / "in the band", Calibration, Pay
review, Decision Room, Exact cost, Hiring request, Candidate stage, Buddy, Clearance,
Final settlement, Probation, Growth plan, Needs you, Lock the week, Role, Hand-over,
See it as, Filing).

**Added after the step 3 report (do these first — they matter more in step 4, where
most screens are gated):**
- A Watch walkthrough over a screen the learner is refused (navigation succeeds but
  the screen/lens refuses or hides its content) currently plays as centred cards. It
  must detect the refusal (hub place says lens not allowed, lens hidden, or the first
  anchor never appears + an access-error signal) and show the step-1 no-access ending
  FIRST ("You don't have access to <hub › tab> — try it in the practice company"),
  across all existing walkthroughs, not only new ones.
- Narrow screens: the lesson card covers part of the replica board (seen on the
  Mapping Journey). Make the card dock/collapse so the anchored element stays visible
  at ≤ 900px width.

## Non-goals
No product changes beyond anchors. No redesign of any board. No role-path redo (step 5
— but tag each station with roles). Do not touch Training (it is its own Learn lens).

## Design
Bar (verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."**
Hero moment: **one person's journey across the app** — the map shows a new Lifecycle
line where a single person (the Hoa Sen practice hire) moves from Hiring → New joiners →
Probation → (years later) Exits, each station lighting as it is learned; the Pay review
lesson animates the budget meter filling as rises are added. Zero dead-ends (esp.
no-access), plain words, motion with purpose, phone width, Lucide only.

## Test cases
1. Map shows the new lines and stations in VI and EN; progress counters right.
2. Each station plays; replica anchors resolve for the four replica-backed ones.
3. Watch walkthrough per full station on payobook.com with the demo/admin login — every
   step anchored, nothing saved. Try mode for the four replica ones.
4. As the QA login (limited access): gated stations show the no-access sentence, no
   dead-ends.
5. Helper Guide me on each real screen → the right lesson.
6. ⌘K + Ask Payobook for each area's top question.
7. Contract checker 0; anchor tests; tools green; module suites on a throwaway clone.
8. Phone width; console clean.

## Deploy
pb_learn + every module given anchors + pb_payroll_ai_insights. Tier: normal. All 4
DBs; restart after purge. Remember tenants lack some modules (goals/training/
announcements on some DBs): content must degrade (station hidden or no-access), never
error.

## Report back
As step 3.
