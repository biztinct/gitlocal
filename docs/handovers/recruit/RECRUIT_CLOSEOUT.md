# RECRUIT programme — close-out (2026-10-01)

Rize ATS requirements → Payobook Hiring rebuild. Eight phases, designed by Fable and built, tested,
deployed and browser-checked by Opus in one session (30 Sep – 1 Oct 2026). The gap register this closes is
`docs/design/rize-recruit-gap.html`; the owner page mirroring it with the "after" column is
`docs/design/rize-recruit-closeout.html`. Every ruling, gotcha (RC1–RC103) and phase log line is in
`RECRUIT_LEDGER.md` — read it first in any follow-up session.

## 1. What is live, per database

| Database | pb_hiring | pb_vendor_access | Notes |
|---|---|---|---|
| `payobook` (payobook.com, demo world) | 19.0.2.7.0 | 19.0.1.12.0 | All demo data registered with `pb.demo.seed` (labels "RECRUIT P1 …" to "RECRUIT P8 emails and automations") |
| `rize` (tenant, not in daily use) | 19.0.2.7.0 | 19.0.1.12.0 | No demo data; `google_calendar` installed, no Google client id |
| `payobook_template` (golden template) | 19.0.2.7.0 | 19.0.1.12.0 | Carries every feature for cloning |
| `abm` | 19.0.1.3.5 (untouched) | — | Retired; its two hiring crons (ids 67, 68) switched OFF (RC70) |

Also installed for the programme on the three DBs: `id_ID` language (P2), `hr_recruitment_skills` (P4),
`google_calendar` + `google_account` (P5). `pb_import_kit` gained icons (no version change). Code tree hashes
byte-identical repo ↔ server after the P8 deploy (`687d1e5c703ba777`).

Backups per phase: `/odoo/backups/2026-09-30-recruit-p1/`, `…-p2/`, `/odoo/backups/2026-10-01-recruit-p3/` …
`/odoo/backups/2026-10-01-recruit-p8/` (payobook, rize, payobook_template).

## 2. Owner items — every phase, one list

1. **Phase 1** — The Vietnamese names of the stages — have Rize's team read them and say if any word is wrong.
2. **Phase 1** — Line managers moving candidates on their own roles: the switch is OFF (only recruiters and the talent lead move people). Keep it off?
3. **Phase 1** — A door to Hiring in the left menu for the talent lead and line managers. Today they arrive by the search bar, the direct link or the email links.
4. **Phase 1** — An old coach tip on the hiring screen still describes the old board — refresh or remove it.
5. **Phase 2** — The consent sentence on the application form and the months it promises, per market.
6. **Phase 3** — Who is told when a request is over budget, per company (Rize names the CEO person).
7. **Phase 3** — The mailbox hiring emails come from — a real address on Rize's own domain.
8. **Phase 3** — Line managers: a full login, or the email pages only?
9. **Phase 3** — The wording of the small labels on each role card on the board.
10. **Phase 4** — How many months each market keeps a candidate, and whether people are asked for their consent again before that ends.
11. **Phase 4** — Who runs the clean-up (today the Head of hiring) and when the nightly clean-up is switched on. It is OFF.
12. **Phase 4** — Should scorecards be part of what a hiring manager sees by default when a candidate is shared?
13. **Phase 4** — Should the Head of hiring read every recruiter note (today: the author and the talent lead)?
14. **Phase 4** — Try "share back to the recruiter" once on Rize's own system.
15. **Phase 5** — Anita's real scorecards, to replace the five starting ones.
16. **Phase 5** — Google sign-in details from Rize's Google admin, so interviews go into Google Calendar with a Meet link.
17. **Phase 5** — Whether to pull interview transcripts in automatically later (today a person pastes the link).
18. **Phase 6** — Can the new joiner upload their own signed copy, or does the recruiter always do it?
19. **Phase 6** — The set of documents each country signs (Vietnam, India, Indonesia are filled in as a starting point).
20. **Phase 6** — "Stalled" means 14 days without a move. Right number?
21. **Phase 6** — Who the HR person is on the "a week before they join" email.
22. **Phase 7** — Job board subscriptions and access, so adverts can be posted directly instead of pasted.
23. **Phase 7** — The email contact at each job board, for "Send the advert".
24. **Phase 7** — Do agencies see the salary band of a role?
25. **Phase 7** — The agency rule is 6 months. Right length?
26. **Phase 7** — Can a confidential role be given to an agency?
27. **Phase 8** — The email to every colleague when a role opens to referrals is OFF. Switch it on for Rize?
28. **Phase 8** — Emails to colleagues are English only (the agreed rule). Does Rize want any of them in Vietnamese anyway?
29. **Phase 8** — Today only the system administrator edits the emails to colleagues. Should the Head of hiring edit them too?
30. **Phase 8** — The "Assignment" email rule is OFF because the email needs the tasks and a date that only a person can type. Switch it on once Rize writes its standard assignment into the email itself?
31. **Phase 8** — When a role is filled, the other finalists are closed and sent "Not this time" automatically. Keep that on?
32. **Phase 8** — The agency portal and its emails are English only. Do agencies need Vietnamese or Bahasa?
33. **Phase 8** — Have a native speaker read the Vietnamese and Bahasa Indonesia emails before Rize goes live.
34. **Phase 8** — "Let's chat" goes every time somebody enters Recruiter review, as it did before. Change it to once per person?
35. **Housekeeping** — The retired abm database still has Hiring installed with its reminders switched off. Remove Hiring there?
36. **Rize IT** — Add the email sending records for Rize's domain before go-live, so mail goes out as Rize.

## 3. Demo logins (payobook.com, company 5 "Payobook Vietnam JSC")

| Who | Login | Password |
|---|---|---|
| Recruiter | `demo.recruiter@example.com` | `RizeW2!2026` |
| Talent lead | `demo.talentlead@example.com` | `RizeR1!2026` |
| Line manager (no hiring group) | `demo.hiringmanager@example.com` | `RizeR1!2026` |
| Agency portal (DEMO Talent Bridge) | `demo.agency@example.com` | `RizeR7!2026` |
| Post-deploy QA | `qa.test@payobook.com` | see memory `payobook-qa-login` (not in the repo) |

Demo roles: DEMO Territory Manager (req 936, the walk role), DEMO Field Agronomist, DEMO Regional Sales Lead,
DEMO Plant Manager (confidential), DEMO Junior Agronomist (943, Indonesia). Candidates carry ordinary
Vietnamese / Indonesian names and `demo.cand.*@example.com` addresses (RC-D7).

## 4. Switches and parameters (same on all three DBs unless noted)

Only `doc_deadline_days 2`, `doc_reminder_days 1`, `feedback_hours 24`, `interview_duration 45`,
`jd_reminder_days 3`, `recruiter_nudge_days 3`, `referral_announce 0`, `reminder_cap 400`,
`retention_enabled 0`, `stage_set_version 2`, `urgent_after_hours 0` are stored rows (payobook also stores
`platform_mail 0`, `reminders 1`). Everything else defaults in code (`hiring_common.DEFAULTS` and the P8
built-in defaults):

| Parameter | Default | Meaning |
|---|---|---|
| `pb_hiring.candidate_mail` | 1 | Master switch for every candidate email |
| `pb_hiring.line_managers_move` | 0 | Line managers may move candidates on their roles (RC-D1) |
| `pb_hiring.phone_auto_mail` | 1 | Master switch over the seeded "Let's chat" automation row |
| `pb_hiring.phone_minutes` | 30 | Minutes in the Let's chat email |
| `pb_hiring.auto_received` | 1 | "Application received" (P8 built-in) |
| `pb_hiring.reminders` | 1 | Interview day-before / half-hour reminders |
| `pb_hiring.auto_chase` | 1 | Opinion asks, daily chase, talent lead told (P8 built-in) |
| `pb_hiring.lead_late_days` / `chase_every_hours` / `chase_stop_days` | 2 / 24 / 14 | The opinion chase |
| `pb_hiring.auto_doc_remind` | 1 | Papers daily reminder (P8 built-in) |
| `pb_hiring.docreq_trigger` | on_check_clear | When papers are asked for |
| `pb_hiring.auto_check_todo` | 1 | Recruiter to-do when a background check starts (P8) |
| `pb_hiring.offer_mail` | 1 | Offer emailed to the candidate |
| `pb_hiring.auto_close_finalists` | 1 | G-44: other finalists closed when the role is filled (P8) |
| `pb_hiring.auto_week_before` | 1 | Week-before-joining email (P8 built-in) |
| `pb_hiring.week_before_days` / `stalled_days` | 7 / 14 | P6 |
| `pb_hiring.closure_mail` / `notify_mail` / `referral_mail` | 1 / 1 / 1 | Joining, recruiter-assigned and referral emails |
| `pb_hiring.auto_share_mail` | 1 | "You were given access to …" (P8) |
| `pb_hiring.referral_announce` | 0 | Email every colleague when a role opens to referrals (owner item) |
| `pb_hiring.platform_mail` | 0 | Email adverts to a board's contact |
| `pb_hiring.retention_enabled` | 0 | Nightly anonymise (Run now works regardless) |
| `pb_hiring.ask_escalate_days` | 3 | Working days before an unwritten request goes to the talent lead |
| `pb_hiring.agency_cooling_months` | 6 | The agency rule |
| `pb_hiring.sender` | (empty) | Typed hiring sender; else the company's email |
| `website.auto_redirect_lang` | off on all three | Careers page browser-language redirect (P3) |

Automations seeded per company (P8): Calendly ON, Assignment brief OFF, first-look nudge (7 days in
Applications received) OFF, buddy to-do on offer accepted OFF. payobook company 5 also has the two DEMO rules
and the walk's "waited 3 days in Shortlist" rule.

## 5. Register lines G-01 … G-58 — final status

| Line | Rize wanted | Final status | Phase |
|---|---|---|---|
| G-01 | Application form editable per role: add, remove, reorder, rename fields, own questions | Built | P2 |
| G-02 | Application form in Vietnamese and Bahasa Indonesia, chosen by market | Built | P2 |
| G-03 | A drag-and-drop board per role: columns are stages, cards are people, move several at once | Built | P1 |
| G-04 | Rize's own stage names, with columns shown or hidden per role; department + country pre-fills | Built | P1 |
| G-05 | Nothing waits on a sign-off; recruiters move anyone anywhere; one hard rule only | Built | P1 |
| G-06 | Who may move a candidate: recruiters and the TA Lead only | Built | P1 |
| G-07 | Role names and what each role sees (Recruiter, TA Lead, Head of HR, Hiring Manager, Finance, Interviewer, Agency, Candidate) | Built | P1 |
| G-08 | Recruiter-owned privacy: comp, opinions and the resume bank visible only where the recruiter shares them | Built | P4 |
| G-09 | Delegate a recruiter's roles to a backup for a date range, approved, logged, auto-reverted | Have | P1 |
| G-10 | TA Lead self-serves stages, forms, templates and automations without a ticket | Built | P1 |
| G-11 | A simpler screen with fewer filters | Built | P1 |
| G-12 | Hiring manager raises the request on a standard form; all mandatory fields; a Confidential toggle | Built | P3 |
| G-13 | Recruiter asks a hiring manager to complete a request; reminders until done; escalation | Built | P3 |
| G-14 | A role can exist before, or without, a hiring request | Built | P3 |
| G-15 | Budget entered by the hiring manager; over-budget flags CEO, Head of HR and Finance by email; nothing blocked | Built | P3 |
| G-16 | Recruiter auto-assigned by the role's country; recruiter and TA Lead told | Have | P3 |
| G-17 | Job description from a role-family template, shared with the hiring manager for input, versioned, no sign-off gate | Built | P3 |
| G-18 | Interview rounds and the panel named on the request | Built | P5 |
| G-19 | Referral opens automatically when the role goes live, unless Confidential | Built | P3 |
| G-20 | Post to website, LinkedIn, employee portal and regional boards from one place, each source-tagged | Built | P7 |
| G-21 | Agency portal: see assigned open roles, submit only, no internal data; 6-month cooling; performance tracked | Built | P7 |
| G-22 | Expected salary asked on the application form | Built | P2 |
| G-23 | Portfolio required where the role needs it, and impossible to skip | Built | P2 |
| G-24 | Who screens first and how: recruiter for most roles, hiring manager first for senior or new roles | Have | P1 |
| G-25 | Applied date and one full timeline on the candidate | Built | P1 |
| G-26 | Tagging on the board; a searchable Resume bank hidden from hiring managers | Built | P4 |
| G-27 | The application form field list (11 fields) | Built | P2 |
| G-28 | Screening assessments (five types) and automatic filtering of high volumes | Deferred | — |
| G-29 | Duplicate application flagged; merge or link | Built | P2 |
| G-30 | Scheduling with calendar holds, an automatic video link, transcript attached, time zones handled | Built | P5 |
| G-31 | Reminders 24 hours and 30 minutes before, to everyone | Have | — |
| G-32 | Scorecards per role and per discussion round; recruiter may enter on a panellist's behalf; reminders; hidden between panellists | Built | P5 |
| G-33 | Reschedule needs 30 minutes' notice, a reason, an Internal / External tag; old and new times kept | Have | — |
| G-34 | Every interview closed with an outcome: attended, candidate no-show, interviewer no-show | Built | P1 |
| G-35 | Advance, or send a templated rejection editable by HR | Built | P8 |
| G-36 | Private recruiter notes: author and TA Lead only; shareable with a named hiring manager | Built | P4 |
| G-37 | Moving to the Recruiter review stage sends the recruiter's Calendly link automatically | Built | P5 |
| G-38 | Panel debrief with scores side by side; decision Selected / Not selected / Hold; others flagged | Built | P5 |
| G-39 | Background check by calls against a template, documents attached, runs alongside and never blocks | Built | P3 |
| G-40 | Secure upload link for documents, 2-day deadline, reminders, live checklist | Have | P3 |
| G-41 | Offer built from a country salary file; hiring manager + HR sign-off recorded and notified, not blocking; money masked | Built | P4 |
| G-42 | Offer letter generated in the system and e-signed (DocuSign); signed copy auto-filed | Built, part later | P6 |
| G-43 | No offer without an agreed hiring request (the one hard rule) | Built | P3 |
| G-44 | On a signed offer: notify hiring manager + TA Lead, archive the other finalists, trigger pre-onboarding | Built | P6 |
| G-45 | Explicit consent at application; retention period and deletion rules per market | Built | P4 |
| G-46 | Withdrawal, offer declined and adverse-check handling | Have | — |
| G-47 | Every automated email editable by HR, with language versions for ID / VN / IN / SG | Built | P8 |
| G-48 | The notification matrix: 23 triggers, who, channel, timing, escalation | Built | P8 |
| G-49 | Only Rize's own confirmation email goes out when someone applies; no stock "thank you" | Have | P1 |
| G-50 | Email automations the TA Lead can set up herself | Built | P8 |
| G-51 | Email domain authentication so mail goes out as @rize.farm | Rize-side | — |
| G-52 | Time to fill, time to offer, time in stage, offer acceptance, source effectiveness, internal / external delay split; filterable, exportable | Built | P6 |
| G-53 | Four dashboards: Recruiter Workbench, TA Lead Overview, Hiring Manager View, Leadership Pipeline | Built | P6 |
| G-54 | Eight reports with Excel / CSV export | Built | P6 |
| G-55 | The person stays a candidate, with the recruiter, until the date of joining is verified | Built | P6 |
| G-56 | Pre-onboarding run by the recruiter: buddy nomination, laptop preferences, meet-the-team chats | Built | P6 |
| G-57 | Reminder one week before the expected joining date to recruiter, hiring manager and HR | Built | P6 |
| G-58 | Offer-drop measurement: offered → accepted → joined | Built | P6 |

Totals: 47 built, 1 built with a later part (G-42, e-signature waits for Rize's templates), 8 already there and
kept or refined, 1 deferred by Rize (G-28), 1 Rize-side (G-51).

## 6. Rulings

Gap-register rulings (all applied):

- **R1** Call. One hard rule at the offer; all other sign-offs record and notify. (G-05, G-43)
- **R2** Call. Manager-entered budget, non-blocking flag to CEO / Head of HR / Finance, tracking tag. (G-15)
- **R3** Call. Offers offline for now; upload of several signed documents per country now; generated letters + DocuSign later. (G-42)
- **R4** Call, keeping the workbook's 1–5 lines as an optional part of a template. (G-32)
- **R5** Call. Deferred; questions live in the form. (G-28, G-01)
- **R6** Call, pending Rize's confirmation: Recruiter + TA Lead move; hiring managers view and comment. (G-06)
- **R7** Prompt for the outcome, never block. (G-34)
- **R8** Call. "Offer signed" and "Joined" are two separate moments. (G-44, G-55)
- **R9** Call. Roles and requests are separate; the request is only needed for the offer. (G-14)
- **R10** Call. Recipients = CEO, Head of HR, Finance; Rize names the CEO recipient. (G-15, G-48)
- **R11** Both. Candidate-facing text in three languages; internal screens and emails English. (G-02, G-47)
- **R12** Both. Rounds and panel on the role; the MR pre-fills them when it exists. (G-18, G-08)

Owner rulings (`RECRUIT_LEDGER.md`): **RC-D1** only recruiters + the talent lead move candidates (switch off);
**RC-D2** Rize's words are the product default, tier "Talent lead"; **RC-D3** Google Calendar + Meet built in P5,
Rize authorises later; **RC-D4** deploy payobook + rize + payobook_template, never abm; **RC-D5** one hard gate —
no offer without an agreed request; **RC-D6** the role is the requisition record with a request facet;
**RC-D7** demo candidates with ordinary names, registered per phase; **RC-D8** "Recruiter review", never
"phone screen".

## 7. Unpushed commits

Branch `19.1`, upstream `origin/19.1`: **51 commits ahead** after the P8 docs commit (`git log origin/19.1..HEAD
--oneline | wc -l`). Nothing was pushed (standing rule: push only when the owner asks).

## 8. What the next session must know

- Read `RECRUIT_LEDGER.md` fully; RC47 explains the three payobook-only test failures (also failing on old code);
  run the suite on a rize clone for a clean baseline. P8 rehearsal: 357/360 on a payobook clone.
- Deploy ritual that worked every phase: backups → payobook clone rehearsal with
  `--addons-path=/tmp/pN_addons,/odoo/odoo-server/addons` (RC22, RC90 needs `pb_import_kit` beside it) → clean
  `/tmp/rize_stage` → per-module `rsync --delete` → stop server, `-u` per DB in a detached systemd unit → asset
  purge + `web.assets.version` + `orm_signaling_assets` per DB → hash + `latest_version` check. Python-only fixes
  after that: the "hot" script (rsync, purge, restart). Scripts live in the session scratchpad (`p8_*.sh`).
- Candidate emails are `pb.hiring.message.template` rows per company, NOT `mail.template` (RC92). Add a new
  candidate email = new key + seed text in `comms_i18n_p8.py` + a sender calling `pb.hiring._mail_candidate`.
- Automations: add an event = one entry in `automation_p8.EVENTS`/`EVENT_CLAUSE` + a one-line `_fire` hook in
  `hooks_p8.py` (a `leg` after super) + the JS `CLAUSE` table in `hiring_p8.js`.
- Chrome MCP's profile has been locked by a parallel session in every phase; the headless puppeteer harness
  (`drive.js`, `owlcheck.js`) in the scratchpad is the fallback and compiles every OWL template before a deploy.
- Agency pages and mails, internal emails and recruiter screens are English (R11). Candidate-facing words exist
  in en/vi/id; a native-speaker read is an owner item.
- Google Calendar is built and mocked in tests; it has never run against a real Google account (no OAuth client).
