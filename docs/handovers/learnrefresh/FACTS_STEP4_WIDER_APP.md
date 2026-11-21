# Verified facts for Step 4 (read from code 2026-09-27; code wins if it moved)

NO `data-coach` anchors exist in: pb_pay, pb_decision_room, pb_lifecycle, pb_hiring,
pb_onboarding, pb_offboarding, pb_probation, pb_pip, pb_contract_lifecycle, pb_mission,
biz_access, pb_bank_ocr, pb_young_worker, pb_audit, pb_rnr, pb_hr_comm, pb_records,
pb_workseg, pb_assets, pb_goals. Only Filings has: gr-head, gr-countries, gr-grid,
gr-empty (pb_govt_reports/static/src/xml/govt_reports.xml:10,26,38,54).

## People › Pay (pb_pay) — tabs Bands / Fairness / Review / Changes (pay_hub.js:141-145)
Visible to pay viewer/manager, group admin, HR manager, system admin (pay_palette.js:38).
Only pay manager + group admin change bands.
- Bands: Work it out again, Export, Import, Place a new hire. No bands → "You have no pay
  bands yet — here is a set drawn from what you already pay" + Use these (nothing saved
  until pressed). Filters company/family/country. Band picture: every person placed
  (named dots / stacked marks) → "The people standing here". Dense rows. Fit to this
  family (own money scale warning). Per band "Open out" / "Back to the shared scale";
  "N below"/"N above". Drag a band edge → live cost, "Let go to save it…", "Band moved."
  + Undo. Jobs in no band card. "Worth knowing" 5 health cards (below band, above band,
  newer paid more, manager paid less, band width). "Nothing here changes anybody's pay."
- Fairness: computed on open, never stored; Print the statement; scope; "Show it all in
  the group's money"; Pay gap by gender, Across everybody; By level, By division, Same
  job different pay, Paid least for the same work (≥15% under middle). Names only for pay
  managers/group admins.
- Review: list "Pay reviews" (Set up guidance, New review); meters Budget, Fairness,
  Scores. Stepper Being written → With HR → With finance → With the CEO → Approved →
  Applied. Buttons Send for approval, Approve for HR/finance, Approve it, Apply ("What
  Apply would change"), Take it back (24 h), Send back, Close, Drop it. "What stops
  approval"; 5 limit types. Worksheet filters Everybody/My team/Not scored/Stops
  approval/Paid below the band/No rise; bulk Use the guidance, Add 1%, Take off 1%, Share
  out what is left; Paste scores, Read scores in, Guidance, Calibration; columns Person,
  Team, Score, In the band, Paid now, Guidance, Rise, New pay, A year. Calibration marks
  in line / stands out / breaks a limit + "Worth a second look".
- Changes: New pay change; reasons Promotion / Putting a mistake right / Keeping up with
  the market / Something else; same approval ladder + Undo.

## People › Plan = Decision Room (pb_decision_room)
"DECISION ROOM — See the year before you commit to it." Undo, Reset, Save plan. Goals
("Six goals. The room keeps score."). "What if we…" presets Grow thoughtfully / Invest in
people / Ease overtime; levers (revenue, more work by December, team/roles, add/remove
people + start month, overtime per person, salary increase + start month, productive
time, unavailable paid time, bonus, leavers, replace leavers, contributions). "Explore
freely. Nothing here changes payroll." Results tabs Work & shifts / Why profit changed /
People & pay / Room to hire. Compare table. Propose → Approve / Send back → Keep editing
a copy. Exact cost (runs the real payroll scheme; "Exact cost X · the estimate was Y
(±Z%)"). Export the decision brief.

## Lifecycle (default lens Journeys). Every board: quiet numbers row, step strip, Next box.
- Hiring: Raise a hiring request; Hiring tools (Company story, Email templates, Run
  today's chasing, Hiring rules, Cover for me, Covers). Quiet numbers Open, Awaiting
  sign-off, Waiting on you, Candidates, Over budget, Interviews this week, Opinions late,
  Offers out, Referrals this month, Joined this month. Steps 1 Request & approve · 2
  Prepare & publish · 3 Meet your candidates · 4 Welcome aboard. Tabs Roles / Interviews.
  Row "Step X of 4" + Next box. Request wizard "Let's shape your next hire." The role /
  Responsibilities / Interview plan / Budget & review. Approval manager → HR lead →
  Finance only if over budget. 15 candidate stages (Screening, Panel Review, Recruiter
  Phone Call, Assignment, Discussion 1–3, Reference Check, Offer Stage, Joined + CV
  Reject, Interview Reject, Drop Out, On Hold, Offer Drop out) via Move stage. Gate:
  probe `pb.hiring.can_open`.
- New joiners: Run today's steps; numbers Joining this week, Already started, Still
  without a buddy, Steps overdue, Said they are struggling; steps Getting ready →
  Settling in → Checklist done; drawer Still to do / Done / Conversations, buddy.
- Exits: numbers Leaving this month, Last day has passed, Settlements held up, Clearances
  still open, Items not back yet; steps Working their notice → Signing off → Ready to
  settle → Settled; clearance from IT, HR, Finance, Admin ("The final settlement waits
  for all four"); Close settlement / Open the settlement; handover, farewell note.
- Probation: numbers In a trial period, Reviews running, Waiting on a decision, Answers
  overdue, Ending within a week; steps Choose peers → Gather perspectives → Manager
  conversation → HR & leadership review → Share the outcome; 6 peer questions (4 ratings,
  2 free text); verdicts Confirm them / Extend the trial / Do not confirm; gate Manager
  evaluation → HR lead → CEO.
- Growth plans (PIP user/head only): numbers Open, Still a conversation, Plans running,
  Waiting on a decision, Drifting or at risk; steps Asked → Coaching → Plan running →
  Decision; objectives On track / At risk / Met / Not met; manager form "Ask HR about
  someone in your team".
- Contracts: All decisions, Extensions, Run today's steps; numbers Ending within 60 days,
  Nobody has decided, Waiting to be agreed, Being evaluated, Made permanent this year;
  steps Running → Decision needed → Being agreed → Decided; Raise the decision; Let it
  end / Extend it / Make it permanent.

## Workforce (pb_mission) lenses Today, Schedule, Time, Time Off, Overtime, Trips, Close,
Approvals (+ Holidays, Field). Visibility per lens (pb_mission.js:142-196). Needs you
panel (My team / Organisation): "N clean overtime … " + Approve all N clean (it is in the
panel, NOT the Overtime screen). Close: flags Fix / Approve as-is / Review all N;
Payroll handoff Regular hours / Overtime / Bonus hours / Est. gross; Lock week & send to
payroll (manager; all flags cleared); "Week locked" + Reopen… (reason). Headings: Today
(Open map), Schedule (Copy week, Set budget, Open shifts, People needed), Time, "Leave
Command Center" (File leave, Apply on behalf, Out today), Overtime (Approval queue,
Bonus Hours review, rules & ceilings), "Business Trips" (New trip), Public holidays
(IMPORT → REVIEW → PUBLISH), Field map.

## Settings › Access & delegation (biz_access)
Everyone can open; grant/see-as/new-role only for access managers/admins. Buttons See it
as ▾, Who holds what, History, Take back what has ended, Edit the list of roles, Hand my
access over, New role. See-as banner "Looking at this as X… You still have exactly your
own access" + Back to your own view. Tabs Roles / People / Screens / Hand-overs. Role
card "Opens on the left menu", "Lets them", "Held by…". Builder What it is called →
Where it belongs → Worked out for you. Give a role / Take this role away. Add a person
(login + invite email). Hand-over dialog: who, what, how long → Hand it over; taken back
automatically the morning after the end date.

## Compliance: Filings (govt-filing users) · Bank (all) · Young workers (payroll user /
attendance officer) · Audit (payroll manager / admin)
- Filings: "Government Reports", country picker, tile Generate; "coming soon" empty;
  "Generate a filing" flow Choose the filing → Scope → Generate (⌘K entry).
- Bank "Bank Verification": Draft → HR Review → Finance Review → Approved; New
  bank-change request, Submit, Approve as HR/Finance, Refuse; duplicate-account warning.
- Young workers "Young Worker Guard": Protected, Compliant this week, Violations 30 days,
  Missing birthdays.
- Audit "Audit & Compliance": Stream / Salary lens / Login lens; filters Today, This
  week, By me, Salary only, Logins.

## Home › Wall ("What people said about each other", Say thank you, value chips) ·
Home › Announce (everyone) · People › Announce (comms team: monthly calendar) · Records
(HR user/payroll officer/admin) · Where they work ("A month is thirty days…") · Assets ·
Praise (recognition users) · Goals (probe `pb.goals.can_open`).
