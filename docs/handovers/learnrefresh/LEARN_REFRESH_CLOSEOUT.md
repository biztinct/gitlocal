# LEARN REFRESH — close-out (2026-09-28)

Engineering record of the five-step program that brought Learn (lessons, walkthroughs,
practice company, helper, glossary, ⌘K, Ask Payobook) up to date with the product as it
stood on 2026-09-27. Rules and gotchas: `LEARN_REFRESH_LEDGER.md` (LR1–LR53).

## What changed, per step

| Step | What shipped | Main commits |
|---|---|---|
| 1 — the helper knows the tabs | Hubs publish where the reader is (`@pb_hub/js/hub_place`); every "Open" goes to hub › tab; hub orientation for the 9 hubs; Ask Payobook knows the hub/tab | 638003b6f, cd5f67f8b, 22bd88456, 4d011723d |
| 2 — payroll core | Practice company on the new rail + approval route; Pulse, Approvals inbox, Run (scheme first), Runs, Payslips, Import, Formula rewritten; intents/glossary/PayAI prompt | ee1ab56d8, 228098590, 5e0ad079e, 36a0ab129, a62c6e3e8, f068f0467 |
| 3 — payroll setup | Six new lessons (L7–L12): New configuration, Mapping, Component treatment, Approval Matrix, Records Desk, Schemes & currencies; anchors; VI for taught labels | 1e1cc757a, cea2a8ded, ea5f661e5, 4b36bf888, 063531054 |
| 4 — the wider app | L13–L28: People › Pay, Decision Room, Lifecycle, Workforce, Access, Filings (+4 short); tab gates askable without opening a hub; no-access ending; docked cards | d07b4dc8a, 0c4d5b169, 482453203, 80c52839e, 8a091392e, 8a441d048, 7e9c4ca2b, 2d43ffefc |
| 5 — finish and sweep | Every station a full lesson; role paths + six chapters; hero redraw; folded keys + migration; product Vietnamese; Ask Payobook hand-offs; final sweep | 217d1ad53 … 1040479f4 (16 commits, listed below) |

Step 5 commits: 217d1ad53 (Pay Run: Adjust, Settle, After the run), c819cec31 (Employees + contract
drawer), a708c9e3a (Structures, Integrations), e22cef28d (Insights ×3 + Payroll Report/Budget), 27aed77fb /
db0f9d146 (short lessons to 5 steps), 87f8a53e5 (paths, chapters, hero, aliases, migration, PayAI
whitelist), 3b2a856ac (Team label), 7c06da08b / 1e4db760e (product Vietnamese), f31e43be3 (retired-name
sweep), 0a420aa4a (version bumps), 2411e67b7 / 8e0e6c312 (fixes found on the clone and in the browser),
0a744d01d / 1040479f4 (Ask Payobook routing + lesson hand-off). Not pushed.

## Final shape

- 40 stations on 8 lines in 6 chapters; every station has a 5–9 step lesson with a check question, EN + VI.
- 24 live walkthroughs (sc_mapping retired), 5 role paths (officer 16, approver 7, HR 10, people manager 7,
  owner 10), Team readiness on those paths.
- Hero: picking "I am the …" lights the chapters on that path, quiets the rest, replays a short staggered rise
  once, and the Continue card names the next lesson with its minutes.
- Progress migration 19.0.19.0.0 (contracts → employees, proration/retro → adjust): rehearsed on a clone of
  `rize` with seeded rows (1 re-keyed, 2 merged, "done" → "in_progress"), then run on all four databases (no
  live rows carried retired keys; one event on payobook re-keyed). Clone dropped.

## Gates (step 5)

| Gate | Result | Evidence |
|---|---|---|
| C1 every station opens where it lives | Pass | Browser: 40/40 — 34 hub tabs answered "here"; 6 action screens opened their own screen. Payslips/Formula refused the QA login (no pay-run/formula access, LR18/LR30) and opened for the demo login; Filings needed its filing group (granted to QA for the check, removed after). |
| C2 anchors | Pass | anchor registry tests green on the clone; check_contract anchor-lint "all present"; every lesson step's anchor found on the replica in the browser (all 40 stations walked). |
| C3 every hub tab has a lesson or orientation | Pass | New stations cover Results, Deliver, Calendar, Awards, Adjust, Settle, Payroll Report, Budget. Tabs taught by orientation only: Home › Announce/Wall, People › Where they work/Assets/Praise/Goals/Announce (L28 covers them briefly), Lifecycle › Journeys, Workforce › Schedule/Trips/Approvals/Holidays/Field, Insights › Hiring/Training/Goals, Learn tabs — each has a hub orientation line. |
| C4 no retired screen names | Pass | Content grep: Dashboard, Approvals lanes, Payroll Officer, tier, Setup/Overview section, Statutory (Insurance & Tax), Import Data, Workforce Analytics, Government Reports, sidebar, Full & Final — 0 hits in lesson prose (one "left menu" is the Access screen's own label). |
| C5 VI parity | Pass | 0 missing VI; 0 "trình duyệt"; identical EN/VI only where the product itself is English (listed in test_bundle SAME_IN_BOTH). |
| C6 Ask Payobook | Pass (19/20 with a button) | Live AI, 20 questions across all areas: all answered with today's page › tab names; 19 offered a lesson/walkthrough ("where does this number come from" answered correctly without one; phrase added after). Whitelist == all 40 lesson keys (test_refresh_paths::test_05); starter questions refreshed. |
| C7 ⌘K | Pass | Browser: all 40 stations and 24 walkthroughs found by name, in EN and in VI; topic search ("back pay") finds its lesson. |
| C8 glossary | Pass | jargon lint clean; new terms payment release, pay calendar, award; proration/retro definitions rewritten to today's screens. |
| C9 welcome tour | Pass | sc_welcome: dash-hero → dash-kpis → pw-scheme → pk-kpis → ai-tabs → fs-config → fs-components → helper-orb; all registered and alive. |
| C10 pb_learn suite on a clone | Pass | 269 tests, 0 failed, 0 errors (the two known environment failures no longer fail). pb_payroll_ai_insights: only the known test_data_access_06 / test_egress 04d, 04e. The later Ask Payobook hand-off change (test_action_envelope::test_19) was checked against the content offline and live in the browser, not re-run on a clone. |

Other tests: role switch EN + VI (browser); Team lens with officer / manager / approver rows (browser);
month-end card data and milestone baseline silent (rolled-back shell on `rize`); phone width no horizontal
scroll; console clean.

## Open items for the owner

1. Several taught screens show English to Vietnamese users because the product never translates them: the
   Pay Run ledger numbers (Adjust/Settle), the contract drawer, Payroll Report, the connection screen, most of
   Calendar and Awards. Lessons name the English label and gloss it (LR44).
2. Access role names and descriptions are records written in English; the Access screen itself is Vietnamese now.
3. Pay Run and Settings do not say in advance which tabs a person may open, so Learn cannot warn "no access"
   on those lessons (Payslips, Formula refused the QA login only when opened).
4. Automatic final settlements (made when a month's pay data finishes loading) stay "Being prepared" — nobody
   submits them.
5. Back pay and part-month lines appear only when the pay scheme's Back-pay / Part-month switches are on.
6. Explorer-vs-Pulse answers from Ask Payobook are correct in names but generic in reasons.
7. The streak chip reads "1 days in a row".
8. pb_formula_studio (39) and pb_hr_payroll_formula (20) have older malformed .po entries.
