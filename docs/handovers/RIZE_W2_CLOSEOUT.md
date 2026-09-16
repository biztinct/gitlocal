# RIZE Programme — Wave 2 Closeout (2026-09-16)

The Wave 2 blueprint (`docs/design/rize-w2-blueprint.html`, approved 2026-09-15) is
implemented end to end on the live `payobook` database (https://payobook.com): the five
tabs of `RIZE/HRMS Proposal - Must Have.xlsx` that wave 1 left uncoloured — Hiring &
Recruitment, Goal Setting, HR Comm, Leave & Attendance, LnD — plus the DEMO sweep the owner
ruled mid-wave (D18). Eleven Opus implementation cycles in one session (A1 A2 A3 · X1 · E1
E2 E3 · B1 B2 · D1 · C1), each deployed, browser-validated and committed; rulings D10–D19
and gotchas R131 onwards in `docs/handovers/RIZE_LEDGER.md`. One owner checkpoint (the
training learner flow, after E1) — approved.

Wave 1 closeout: `RIZE_CLOSEOUT.md` (P0–P11, R1–R130). This file covers only what Wave 2
added or changed.

## What is live (module → where you see it)

| Phase | Module (version) | What it does | Where |
|---|---|---|---|
| A1 | pb_hiring 19.0.1.0.0 | Hiring request with the budget check and the Matrix route (`hiring_request`), the advert versioned and agreed (`hiring_jd`), referrals, the posting pack, screening, per-country hiring rules | **Lifecycle → Hiring**; `/my/refer`; Settings → Hiring |
| A2 | pb_hiring 19.0.1.1.0 | Interviews with calendar invites (ICS, the engine's own mails silenced), 24 h / 30 min reminders every 10 min, reschedule and no-show with reasons, the panel's private opinion page due in 24 working hours and chased once, next-round / not-this-time mails, the debrief that picks the candidate | Hiring → Interviews tab; `/hiring/f/<token>`; `/my/hiring` |
| A3 | pb_hiring 19.0.1.2.0 | Background check with an HR-lead override, the document request page with a 2-working-day deadline, the offer (lines, letter, manager → HR lead route `hiring_offer`, candidate page, signed copy), closure into employee + contract + draft pay package + joining checklist + login, recruiter cover (`hiring_cover`), the agency link, the Hiring numbers | Hiring → the path strip and offer panel; `/hiring/d|o/<token>`; **Insights → Hiring** (+ XLSX) |
| X1 | pb_demo_seed 19.0.1.2.0 (**installed**) | The Demo data panel on payobook, a public register API, logins archived not deleted on Remove, the whole programme's demo data renamed DEMO and on one register | **Settings → Demo data** |
| E1 | pb_training 19.0.1.0.2, pb_learn 19.0.13.3.0 | The learner flow on our own pages (lessons, quick questions, the test via the Surveys engine, the certificate), the stock course site gated to staff, the Learn mission turned into a hub with a soft lens registry, the Training board | **Learn → Training**; `/my/training` |
| E2 | pb_training 19.0.1.1.0 | Assignments (day-one / trial period / compliance / one-off / leadership) with due dates, reminders −3/−1/0 then every 3 days, manager at +2, HR lead at +5, "ask for more time" through the Matrix (`training_delay`), the probation gate, compliance schedules, the day-one checklist step, a team page | Training → Assignments, Schedules, Rules; `/my/training/team` |
| E3 | pb_training 19.0.1.2.0 | Training allowance per company/year (personal override), cost claims with receipt + certificate through the Matrix (`training_claim`) → an award on the one money door, certificates filed in the vault, the Training numbers, the weekly/monthly pack (off) | Training → Claims; `/my/training/claims`; **Insights → Training** (+ XLSX) |
| B1 | pb_goals 19.0.1.0.0 | Goal years, the goal sheet (weighted goals + key results, weights must total 100), manager → HR-lead route (`goal_set`), templates, the joining-checklist kick-off, the Goals lens | **People → Goals**; `/my/goals` |
| B2 | pb_goals 19.0.1.1.0 | Monthly check-ins, mid-year / year-end applicability and pro-rating, change requests after lock (`goal_change`) with audit, KR scoring and bands, cycle close and archive, the Goals numbers, "Goals waiting on you" | Goals → Check-ins, Changes; **Insights → Goals**; **Home → Goals** |
| D1 | pb_timeoff 19.0.1.4.1, pb_driver_checkin 19.0.1.5.0, pb_today 19.0.1.5.0, pb_mission 19.0.1.10.0 (+ biz_approval_workflow, Python only) | Public holidays for everybody, late leave requests escalated to the HR lead (they used to go to the owner), back-dated sick leave with the HR alert, the past-leave lock, the carry-forward watch, the Field staff group (drivers + agronomists), the field check-in chip on Today, Mission Control's soft lens registry | **Workforce → Holidays, Field**; `/my/holidays`; `/field` |
| C1 | pb_hr_comm 19.0.1.0.0 | Announcements calendar: one-off and recurring posts per company and audience (everyone / department / job / country), templates and posters, the responsible person nudged 2 days before, the 2-day edit window (HR lead may edit inside it, tracked), the sender every 10 min with a burst cap and one delivery row per person, an optional HR-lead sign-off (`hr_comm_post`, off), the birthday/anniversary cards redesigned (D17: off) | **People → Announce**; **Home → Coming up**; Settings → Announcements; ⌘K "My announcements" for a responsible without the group |

Platform seams added on the way (all soft registries, test-enforced): `pb_learn_lens`
(Learn hub), `pb_mission_lens` (Mission Control), the `pb.demo.seed.register()` API, and a
generic `late.to_role` escalation target in the approval engine (owner as fallback).
⌘K blocks 3500–3970 used; next free **4000**. Lens sequences taken: Lifecycle Hiring 10;
People Goals 70, Announcements 80; Home Goals 40, Coming up 50; Insights Hiring
30, Training 40, Goals 50; Settings Hiring 40, Announcements 50; Learn Training 20;
Mission holidays 20, field 30.

## Logins

- **Owner**: `ash@biztinct.com` — never used by the wave; the password is the owner's own.
- **Validator** `igc1.validator` (uid 2065) — **archived as the last step of this closeout**.
- **Demo logins (all `@example.com` or `@payobook.com`, none can receive real email):**

| Login | Password | Who it is |
|---|---|---|
| `demo.recruiter@example.com` (uid 4446) | `RizeW2!2026` | the recruiter A1–A3 ran as; holds the Hiring user group |
| `demo.a3.an@` / `demo.a3.binh@example.com` | portal, no password | the two joiners closed from offers |
| `demo.learner@example.com` (uid 5344) | `RizeP7!2026` | the portal learner (E1) |
| `demo.joiner@` / `demo.joiner2@example.com` | no password | E2's day-one joiners |
| `demo.field@example.com` (uid 6533) | `RizeD1!2026` | the agronomist with Field staff (D16) |
| `lam.ngo@example.com` (uid 2326) | `RizeP4!2026` | manager of the test cast |
| `diep.thai@example.com` (uid 2336) | `RizeP9!2026` | manages department 657 "Quality Assurance" |
| `tuan.quach@` (2333) / `linh.quan@example.com` (2337) | `RizeP8!2026` / `RizeP9!2026` | wave-1 cast |
| `ess1.demo@payobook.com` (uid 1984) | `RizeP7!2026` | INTERNAL user (not portal — R177) |

All demo logins are on the Demo data register; "Remove demo data" switches them off rather
than deleting them.

## Switches worth knowing (config parameters, live values)

| Area | Live | What it means |
|---|---|---|
| Hiring | `pb_hiring.reminders` 1, `candidate_mail` 1, `feedback_hours` 24, `offer_mail` 1, `closure_mail` 1, **`create_contract` 1**, `doc_deadline_days` 2, `platform_mail` **0** | Interview and candidate mails go; closing an offer writes the contract (gives the joiner a start date); job-board mail is off (D12) |
| Training | `stock_pages_internal_only` 1, `completion_mail` **0**, `unenrol_on_failed_test` **0**, `reminders` 1, `day1_auto` **0**, `manager_escalate_days` 2, `hr_escalate_days` 5, `default_due_days` 14, pack **off** (test address) | The stock course site is staff-only; finishing a course mails nobody; failing the last go does not un-enrol; day-one courses wait for the owner to pick the induction course |
| Goals | `kickoff_auto` 1, `reminders` 1, `checkins` 1, `checkin_day` 25, `mid_year_min_months` 3, `year_end_min_months` 3, `yearend_mail` 1, `review_lead_days` 30, `hr_sender` (default = platform address) | Check-ins on the 25th; joiners under 3 months skip the mid-year review; under 3 months left carries to next year |
| Leave | `escalate_days` 2, `lock_past` 1, `carry_watch` 1, `carry_cutoff` 12-31, `carry_warn_months` 6, carry caps **0** (= not watched) | Two working days for the manager, chase the day after, HR lead the day after that; nothing is watched until a cap is set per leave type |
| Announcements | `pb_hr_comm.send_mail` 1, `signoff` **0**, `edit_window_days` 2, `burst_cap` 500, `nudge_days` 2, `row_limit` 400 | Announcements go out at the time picked, without a sign-off; the HR-lead route is laid and one switch turns it on | |
| Celebrations | `pb_rnr.anniv_mail` **0** (D17) | Birthday and anniversary cards designed and proven, switched off |
| Demo data | panel installed; Load/Remove go through the demo-data approval on payobook | Nobody pressed Load or Remove |

## Money path facts (unchanged rule, one new door)

- A training claim never writes a payslip. Agreeing it raises a `pb.incentive` of kind
  `training`, already approved, in the month it was agreed; the pay team queues it from the
  Awards lens like any bonus (needs `INCENTV` on the run's scheme — wave-1 rule).
- **One real pay run was touched to prove it**: award 51 (1,200,000 ₫, Hồ Thị Trâm) was
  queued into draft run 339 "Demo Payroll June 2026 — Retail" → `INCENTV` on payslip 140174.
  Not confirmed, not paid. Award 50 (2,500,000 ₫) is agreed and waiting for a run.
- "Remove demo data" would take the two claims and their awards, but NOT the payslip line
  already on run 339 — take it off the run first.

## Demo data (D9 + D18)

Everything a phase created stays, named **DEMO …**, and sits on one register: **Settings →
Demo data → "DEMO HR programme data"** (1,251 records). "What would be removed"
is read-only and truthful; "Remove demo data" deletes the records, switches the demo logins
off, and goes through the demo-data approval first. The customer name survives only on the
`pb_tenant` row "Rize Farms", its backups and the fleet alerts about it (a REAL tenancy) and
on the Turkish province — never on demo data. Every old value of the rename is in
`/root/x1_demo_rename_backup_20260916.tsv` on the server. The plain "Demo data" row is empty;
its Load button would build the five-people world in Payobook Vietnam JSC and is untested
there. The content engine's seven stock sample courses are gone (D19); survey 6 "MyCompany
Vendor Certification" remains (owner item); a future `-u website_slides` re-seeds the courses.

Worked examples on the demo: 10 hiring requests (one filled by two closed offers, one
offer waiting on a manager), 3 interview rounds with opinions, a cover, the course "DEMO
Agronomist basics" with a passed test and certificate, assignments in every state incl. a
missed one and two delay requests, two claims (one queued to a run), three goal years with
16 sheets (one locked, one waiting, one finished at 4.2 Strong on a closed year), check-ins,
a change request agreed and one refused, 12 Vietnamese public holidays, an agronomist with a
selfie check-in, eight DEMO announcements (posts 97–104) with their delivery rows and a poster.

## Owner decisions still open

Programme-wide
1. **Push**: 1,616+ commits sit unpushed on branch `19.1` (this wave, wave 1 and every
   earlier stream).
2. **The R131 sweep**: every wave-1 hook/cron leg can lose the record's own status write
   after a database error in a later leg (no savepoint). Wave 2 modules are built without
   the hole; fixing the 12 wave-1 modules the same way is a separate job.
3. **Dark mode**: the shared cockpit kit has no dark palette — every cockpit renders light
   in dark mode (every colour resolves; nothing unreadable). Product-wide theme job.
4. **Ten internal to-do notifications failed with "no sender address"** across phases
   (payslip runs, letters, checklists, hiring). Candidate/employee mails are unaffected.
5. **Two auto-installed modules** came with the Surveys install: `hr_skills_survey`
   and `survey_crm`. Harmless, white-labelled, not on the approved list (R173).
6. **The HR-lead seat on Payobook Vietnam JSC is still the owner's account** (uid 2,
   backup uid 7): late-leave escalations, late-course warnings, claim approvals and goal
   locks all land there until real HR people are named in the Approval Matrix.

Hiring
7. Replace the placeholder Vietnam hiring rule; decide whether `platform_mail` (job-board
   posting by email) goes on.
8. Reword the two offer letters (general, Vietnam) if wanted — same list as the probation
   and experience letters.
9. Is "Talent Partners" the agency name to show on screen?
10. `create_contract` stays on? (Off = joiners have no start date until typed.)

Training
11. The real training allowance (5,000,000 ₫ is a demo figure); allow claims above it?
12. Where the weekly/monthly training pack goes (off, test address); the payslip wording
    "Training reimbursement".
13. Pay or remove award 51 (1,200,000 ₫) from run 339.
14. Which course(s) are day-one for joiners (`day1_auto` then on); which come round yearly.
15. Delete survey 6 "MyCompany Vendor Certification"?

Goals
16. The real goal-year dates (demo: April–March, two weeks to write); the reminder sender
    address; who holds the Goals groups (only the built-in admin today).
17. Band words and cut-offs (Outstanding ≥ 4.5, Strong ≥ 3.5, Solid ≥ 2.5); check-in day
    (25); the minimum-months rules (3/3 — carrying a November joiner needs year-end 6).

Leave & field
18. Who is Field staff (one agronomist today; drivers imply it); carry-forward caps per
    leave type (all 0 = off); check the 2026/2027 Vietnamese holiday dates; set working
    hours on Payobook Singapore so it can hold a holiday calendar.

Announcements
19. Turn the birthday/anniversary cards on when ready (`pb_rnr.anniv_mail` — about 32 people a day on this database); name a responsible per company under Settings → Announcements (today: the HR-lead seat holder); decide whether announcements need the HR-lead sign-off (`signoff`); Slack/Teams later (D12).

## Commits

A1 17260086a 84d78f392 6be6969d1 a3e51eeb0 1aa53f38b f2b1f21e9 95ae021f1 · A2 a59db7ce3
3085d13b5 4eaef57d5 5afbb7f0d 832e3a430 8f3fee7a5 · A3 0dc3a1854 7e5f1eb85 de6257760
0f06f916a 009de15cb edf16bb00 6ca125a68 d4acf990a · X1 4759f327e ec990a7b1 f9c39e804
ea2bde1ea 18ba5cb44 · E1 ca2cd89f1 7ae1b9632 e12ac3604 edf3a5f11 · E2 11a459917 4625f4c45
b2d8c1d42 15d7a794f 799768c87 3c65ff75f d5f96f8b3 dcaa3a259 dc7681c20 1672a8ffa · E3
dbd4c156e 108fe6833 cc16e092d 3ec7889f6 b54e460bf 36b88efde df703e09f d35c72c43 46b48ea7c
f47962826 · B1 07ee83c2c 3ab7c5e67 d2d4c48da 93732cb15 c44ec5985 48cdc255e d65ba150b
b4435e6bd 2d492e25e · B2 (8 commits, see the ledger row) · D1 7cbae0e9f a2121989f e1617a0f1
abdeb840b bb4dfb9b5 d35c72c43 c8dec222b f622babb2 19420f5ee 0164ac2af 18cd7caa8 · C1
47fc57e56 e73b0cba8 cb4575fcc. Blueprint + rulings 713e6b9c9; handovers a4ca81913 2e8042be5 e2ce213e6
80148dac4 f87fa9d80 b8a52e33c e40d04aef af665ed25 9729ba3c1 4199c2125.
