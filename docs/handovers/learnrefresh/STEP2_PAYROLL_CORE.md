# LEARN REFRESH — Step 2: the payroll core, rewritten to today's product

Read first: `LEARN_REFRESH_LEDGER.md` (binding) and the Step 1 report section appended
to it (the place signal, `places`, the station→place helper, retired anchors). Do not
re-derive what they state.

## Scope

A. **Practice company (replica) gets today's shell.** `pb_learn/static/src/engine/fixture.js`
   `MENU` (~:976) + `shellHTML` in `engine/screens.js` (~:1284). Replace the old
   6-section purple nav with today's rail (Home, Pay Run, People, Lifecycle, Workforce,
   Insights, Compliance, Learn, Settings) and, per hub, a lens strip matching the real
   hub's tab labels and order (ledger product map). Only lenses the replica actually has
   screens for are clickable; the others render as present-but-quiet ("Not in the
   practice company" tooltip) — never a dead click. Kill the duplicated practice banner
   (the owner's screenshot shows two stacked banners: keep ONE). Replica footer/brand as
   today. `STATUS_LABELS` / `CHAINS` in fixture.js: states become Draft · Waiting for
   approval · Done (+ Rejected, + Sent back note). Replica screen ids stay stable where
   possible so progress rows survive; where a screen is renamed, keep the key.
   Settings in the replica = a category page (Formula Engine, Salary Structures,
   Statutory, Integrations, Guided setup …) opening the existing formula/statutory/
   structures/integrations replica screens.

B. **Rewrite these 7 full lessons, their replica screens and their anchors** to the
   verified facts in "Verified facts" below — every label, tab, column, number caption:
   - dashboard → **Home › Pulse** (name on the map: "Pulse"): hero line, "Figures for
     {month}" line + month strip, 4 KPIs with their real captions (and what each
     counts), Latest pay run / Company overview / Formula engine cards, first-payroll
     checklist (only when no runs). Keep the "What makes this product different"
     moment but reword: rulebook = the pay scheme (formula configuration), one per
     scheme, not "one per division".
   - approvals → **Home › Approvals, the one inbox**: header, Mine/My team/Everyone,
     tabs My turn · All I can see · Sent back · Finished, request card anatomy (route
     dots, "Waiting for {name}", amount in its own currency, due), the drawer's
     decisions (Approve, Send it back, Turn it down, Move it to somebody else,
     Withdraw), what each does to a PAY RUN (after the product fix in D). The
     old "sign like it's your signature" judgement advice (flags first, sample, explain
     variance) is still good — keep it, re-anchored. Pay-run facts frozen on the request
     (net, gross, payslips, people, variance %, overtime included).
     The inbox has NO `data-coach` anchors: add them in `pb_approval_config`
     (`inbox.xml`: header, scope switch, tabs, a request card, route dots, drawer
     decision buttons) and register them. Name prefix `ai-` (approvals inbox).
   - runpayroll → **Pay Run › Run**: rail Select period → [Pay data] → Compute →
     Review exceptions; "Pay run for" scheme cards first (grouped End of month /
     Regular / Mid-month advance / Final settlement); Pay data step only when the scheme
     reads a spreadsheet, with **Update Payobook** vs **This run only**; feed sync before
     compute; pills Payslips · Computed · Need review; Review (people not in Payobook yet
     → Add these people / Copy names); Open Payroll lands on Runs. Standard working
     days on the run.
   - payruns → **Pay Run › Runs**: columns Draft · Waiting for approval · Done, collapsed
     "Rejected pay runs"; card actions Submit for approval / Open the approval / Reject
     (in-card confirm); route sentence on the run; "These figures do not add up" banner
     (what it means, where to go: Component treatment — one sentence, step 3 teaches it);
     currency note; done-run actions.
   - payslips → **Pay Run › Payslips**: run selector, KPIs (Need review = net ≤ 0 — say
     it plainly), stepper Draft / Waiting for approval / Done, "approved together, as a
     pay run". Keep Mai's gross-to-net worked example (derived via practice-data.js,
     never hand-typed) — re-verify the numbers still derive.
   - import → **Pay Run › Import**: hero "Load this period's pay data", tiles, pipeline,
     guided flow Source & file · Review & match · Validate · Commit, "Commit import" vs
     "Send for approval", Match… / Retry / Skip, "This run only — no records were
     updated". Teach the two answers to "what should these values do?" (the same
     choice appears in Run's Pay data step — link the two).
   - formula → **Settings › Formula Engine**: views Cards · Grid · Test · Compare · Health
     · Settings; lifecycle Start testing → Validate → Activate, Put it back to draft /
     Retire (or Propose retiring when a route exists); Simulate lives in Tools (⌘K) →
     Analyze; Settings opens the guided setup in edit mode. Remove `fs-simulate` and any
     Settings-panel teaching.
C. **Walkthroughs, practice tasks, tour, questions, words** that ride on those lessons:
   - scenarios sc_welcome, sc_payrun, sc_payslips, sc_formula, sc_import, sc_people,
     sc_mapping → re-anchored to live anchors via hub places (step 1 helper). sc_welcome:
     Home › Pulse → Pay Run › Run (scheme card) → Pay Run › Runs → Home › Approvals →
     Settings › Formula Engine → helper button. sc_mapping currently rides the OLD
     mid/end-cycle mapping wizard: retire it from the map (step 3 writes the Mapping
     walkthrough) — hide, don't delete progress rows.
   - missions: m1 (compute + overtime flag + **Submit for approval**), m2 (rewrite: the run
     comes back "Sent back" with a note → fix → resubmit; and a separate beat where you
     Reject a run and see "Rejected pay runs"), m4 statutory (check still true), mL1 live
     (steps: compute June → submit for approval → it is with the first person on the
     route → done; drop "Payroll Officer gate"; predicates in learn_live already use the
     new states — confirm).
   - intents (41): rewrite every stale one (approve, reject, rejectright, whichlane,
     checkfinal, howmanyslips, howrun, wherelives, firstday, whatpage, whichconfig …) to
     the new rail + inbox + scheme-first run. Add: "who approves this run?" (read the
     route), "why is my run stuck waiting?" (whose desk, Move it to somebody else),
     "sent back vs turned down".
   - glossary: retire Approval gate, Tier, Approval chain, Payroll Officer; add Approval
     route, Step, Inbox, Sent back, Turned down, Pay scheme, Pay data, This run only,
     Hub, Tab; fix Rejection. Update every definition that names an old screen.
   - global_suggest: re-check the 6.
D. **Product fix (small, in scope because a lesson must not teach a lie):** a pay run
   turned down in the inbox stays "Waiting for approval" — `hr.payslip.run` has no
   `_approval_reject` (engine calls it: `biz_approval_workflow/models/engine.py:1379`;
   default no-op `adapter.py:163`). Implement `_approval_reject` on the run to do what
   the board's Reject does (`pb_payruns/models/hr_payslip_run.py` ~:1091-1125: cancel
   slips, state `cancel`, store the reason in `pb_reject_note`) WITHOUT withdrawing the
   request again (it's already rejected) and carrying the state-write sentinel. Test it
   (unit test in pb_payruns) + live on a demo run you create for the test and delete
   afterwards (never touch "Demo Payroll June 2026" or April/May runs). Tier: risky →
   backups of all 4 DBs first (`/odoo/backups/learnrefresh/`).
E. **Ask Payobook's product knowledge** (`pb_payroll_ai_insights/models/payroll_ai_engine.py`
   `ONBOARDING_SYSTEM_PROMPT` ~:154-190, `_KNOWN_LESSONS` ~:616, `_TOUR_TO_LESSON` ~:660):
   rewrite the navigation (8 hubs + tabs + Settings), the run flow (scheme first, pay
   data, compute, submit for approval, route from the Approval Matrix, inbox on Home),
   and the lesson list to the station keys that exist after this step. Hand-off: add
   the ability to hand off to a walkthrough (scenario) as well as a lesson, through the
   existing action-whitelist envelope (keep its hardening). Suggested questions in
   `ai_insight_chat.js` (~:86-93): refresh to questions this step can answer well.
   Must never say "Odoo". VI .po entries for any new visible strings.

F. **Added after the step 1 report:**
   - Vietnamese hub tab labels are wrong in the product (LR11): Run and Runs both
     "Chạy", Deliver "Giao hàng", Statutory "Biên chế". Fix every hub lens label's VI
     in each owning module's i18n/vi_VN.po (+ the stored value if the label is stored —
     LOOK L24: a translation fix can be TWO fixes). Audit all 9 hubs' tab labels in VI
     and list before/after in the report. Helper orientation must use the same words.
   - Clear all 13 retired-anchor uses (the checker warning must reach 0).
   - sc_payrun: `pw-division` is gone for scheme-based companies (use `pw-scheme`);
     `pw-pills` / `pw-result` exist only after Compute — Watch must not point at them
     before Compute (explain the result with a centred card that says so, or reorder).
   - QA login now has pay-run access (LR15) — for the no-access check use a probe user
     you create and archive afterwards, or simulate as step 1 did.

## Non-goals

No new stations beyond renames (step 3/4). No role-path/chapter changes (step 5).
No redesign of the inbox or any product screen beyond adding anchors and fix D.
Do not rewrite outline-only lessons (step 5) — but fix any stale menu/approval
sentence in them (they must not lie either).

## Verified facts (from code, 2026-09-27 — use these, re-check only if the code moved)

Home has lenses Pulse, Approvals (+ Wall, Announce). Pulse anchors: dash-hero,
dash-runpayroll, dash-period, dash-kpis, dash-formula. KPIs: Headcount ("N active
contracts"; counts active employees, not month-scoped), Monthly payroll ("personnel
cost in {month}"; gross on end-of-cycle payslips for the month), Pending approval
("awaiting sign-off"), Active configs ("N rules"). Checklist "Get your first payroll
out" only while no runs.

Inbox (`pb_approval_config/static/src/xml/inbox.xml`, `js/inbox.js`): eyebrow
"Approvals", heading "Waiting for a decision", buttons Ask for a sign-off / Workflows /
Refresh; scope Mine / My team / Everyone (only when >1 option; "Watching, not deciding
…"); tabs My turn · All I can see · Sent back · Finished; money line "Amounts are never
added across currencies." Drawer (`request_drawer.js` ~:118-150): Turn it down ("Why?
(required)"), Send it back ("What should change?"), Approve, Move it to somebody else
("Who should decide it instead?" + reason → Move it), Withdraw it. Send back → run
Draft, slips back to draft, note stored. Approve at last step → run Done. Seeded route
per company: "Pay run approval": Payroll check → HR lead review (per division) →
Finance approval.

Run wizard anchors: pw-rail, pw-scheme, pw-scope, pw-division, pw-summary, pw-paydata,
pw-paymode, pw-coverage, pw-result, pw-pills, pw-missing, pw-exceptions, pw-compute,
pw-skipsheet. Runs anchors: pk-kpis, pk-run, pk-tabs, pk-datechips, pk-divchips,
pk-card, pk-card-actions (some on the kanban fallback only — verify which render in
the hub lens). Runs KPIs: Pay runs / In pipeline / Awaiting your approval / Completed /
"Net paid (done), in {CUR}". Payslips anchors: ps-runsel, ps-kpis, ps-chips, ps-list,
ps-detail, ps-status, ps-breakdown. Payslips has NO drawer / Download Excel (those live
elsewhere — don't teach them here). Import wizard steps Source & file · Review & match ·
Validate · Commit. Formula Studio views Cards · Grid · Test · Compare · Health ·
Settings (`studio.xml` ~:83-101); Simulate = Tools → Analyze.

Demo world: "Payobook Vietnam JSC", 6 divisions (Retail, Manufacturing, Logistics,
Corporate Office, Information Technology, Construction), 12 schemes "Payobook
{Division} — End-Month Payroll" / "— Mid-Month Advance", months April/May done, June
open (Draft), "Demo Payroll June 2026" locked. The practice company (Hoa Sen Retail Co.)
is fictional and separate — keep it, but its screens must look like today's app.

## Design

Bar (verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."**
Hero moment: **the practice company is indistinguishable from the real app's shape** —
same rail, same tabs, same words — and the Approvals lesson plays a request card
travelling along its route dots (Payroll check → HR lead review → Finance approval) as
each step is taught. Zero dead-ends in the replica (every visible control either works
or says why not). Plain words. Motion with purpose (route dot advance, card moving
columns Draft → Waiting → Done). Phone width. Lucide only.

## Test cases

1. Replica: rail + lens strip match the live app labels/order for Home and Pay Run
   (side-by-side screenshots); one practice banner; every rail item clickable or
   explains itself.
2. Each of the 7 lessons: open from the map, play every step, anchors resolve in the
   replica; texts match live labels (spot-check 5 per lesson against the live app).
3. Walkthroughs Watch on the real app (demo login): sc_welcome, sc_payrun, sc_payslips,
   sc_import, sc_formula — every step anchored (report any centred-card fallbacks).
4. Try mode for the same five in the practice company.
5. m1, m2 complete end-to-end in the practice company; mL1 steps show correct text
   (don't complete it on the live demo run).
6. Product fix D: unit test green; live: create a small test run on payobook demo,
   submit, turn it down in the inbox → run shows Rejected with the reason; delete it.
7. Helper Guide me on Home › Approvals and Pay Run › Runs → the new lessons, not the
   orientation fallback.
8. Ask Payobook: "how do I run payroll?", "who approves my pay run?", "where is the
   formula engine?", "show me around" → answers match the new rail/flow; a hand-off
   opens the right lesson or walkthrough; no "Odoo".
9. check_contract.py: 0 failures (the 6 pre-existing approval ones must now pass);
   retired-anchor warnings from step 1: 0 remaining for these 7 lessons.
10. jargon, replay, simulate_resolver, scenario rules tools green; resolver simulation
    for the new intents routes correctly (add cases).
11. pb_learn + pb_payruns + pb_approval_config + pb_payroll_ai_insights test suites on a
    throwaway clone; report counts.
12. VI: every lesson/intent/glossary item has VI; walk Approvals + Run lessons in VI.
13. Phone width replica + helper.
14. Console clean.

## Deploy

pb_learn, pb_payruns (fix D), pb_approval_config (anchors), pb_payroll_ai_insights.
Tier: **risky** because of fix D (backups first). All 4 DBs. Restart after purge.

## Report back

As step 1: per scope item; tests 1–14; anchors added/retired; self-score vs the bar;
new ledger items LR*; commits; versions per DB. Also: a list of any product behaviour
you found that contradicts what a lesson should teach (don't fix beyond D — list it).
