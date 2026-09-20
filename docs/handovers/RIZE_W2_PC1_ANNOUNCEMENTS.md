# RIZE Wave 2 — Phase C1: `pb_hr_comm` — HR announcements

New module: the communication calendar, scheduled posts (one-off and
recurring, per company/country, per audience), templates and posters, the
responsible person nudged two days before, the 2-day edit rule, an optional
sign-off route (off), the People-hub **Announcements** lens (seq 80), a Home
lens "Coming up", and birthdays joining the anniversary engine's card (which
already exists — D17: ships OFF).

Read first: `RIZE_LEDGER.md` (all), `RIZE_W2_HANDOVER.md` A/B/C3, D12 and
D17, the A1 handover §1.2 + `pb_hiring/models/requisition_approval.py`
(adapter canon with `_leg()`), then this file. Version `19.0.1.0.0`,
`post_init_hook` + migration for the route.

## 0. Scope and non-goals
**In scope:** `pb.hr.comm.post`, `pb.hr.comm.template`, audiences, the
scheduled sender (email; Slack OFF, D12 — the post carries a `channels`
field ready for it), recurrence, the T-2 nudge, the edit window, the
optional route, per-country responsibility, head-HR visibility, the
calendar lens, the Home lens, ⌘K 3700 block, birthday card check.
**Non-goals:** Slack/Teams, SMS, a new wall (the Recognition wall stays as
is), any change to `pb_rnr`'s seeded templates via `noupdate` dances —
inherit the QWeb views instead.

## 1. Verified facts
- **Celebration engine** (`pb_rnr/models/celebration.py`): ALREADY handles
  birthdays and anniversaries — `_candidates` reads `hr_employee.birthday`
  (:192-216, kind `birthday`), `run_celebrations_today` (:237, stamped per
  year in `pb.rnr.celebration.log` :65), `_send_celebration(emp, row, to)`
  (:290) renders `pb_rnr.mail_birthday` / `pb_rnr.mail_anniversary`
  (ir.qweb views) and queues one `mail.mail` with explicit `email_to`;
  switch `pb_rnr.anniv_mail` = **0** live (covers both kinds — verify by
  reading :237-260); manager Monday heads-up `run_manager_week` (:322),
  switch `pb_rnr.manager_mail` 0; `upcoming_celebrations(days, company_ids,
  offset, cap)` (:92) for screens. **So C1's birthday work is:** prove the
  birthday branch end to end with a fixture (birthday = server today), make
  the two cards a designed card (inherit the QWeb views from `pb_hr_comm`
  with the locked palette, no gradients, no emoji, literal colour
  fallbacks), show the week's birthdays + anniversaries on the calendar
  lens, and leave `anniv_mail` OFF (D17) with the single switch documented.
- **Bulk send precedent:** `pb_ess_workforce/models/publish_notify.py`
  (`_ess_mail_enabled` :61, burst cap :50, honest `capped` counts :102-148).
  Mail template seed `pb_pay_delivery/data/mail_template.xml:9-28`
  (explicit `email_to` at send, R6). `mail.mail` per recipient, `auto_delete`,
  cancel test rows (R37/R47), `@example.com` only — **audience expansion in
  a test must be capped to fixture people** (company 5 has 4,500 employees;
  never let a test mail them: use a fixture department and assert the
  capped count).
- **Responsibilities:** `biz.approval.responsibility.resolve(company, role,
  scope_keys, on_date)` (`responsibility.py:90`) → the `hr_lead` holder per
  company (backup, pool). The "HR responsible per country" = the company's
  `hr_lead` holder by default, overridable per post.
- **Hubs:** People hub `PEOPLE_LENSES` (clone `pb_rnr/static/src/js/
  rnr_palette.js:52-69`; 70 = Goals in B1) — **Announcements = 80**, label
  "Announce" if "Announcements" overflows the 60px box (R63: measure; the
  longest word must fit). Home `HOME_LENSES` (`pb_home_hub/static/src/js/
  home_hub.js:101`; Wall 20; **Coming up = 30**; B2's Goals card takes 40).
  Settings `SETTINGS_CATEGORIES` (`settings_hub.js:277`, Vendors 20, Access
  30, Hiring 40 (A1)) — **Announcements = 50** with cards Templates and
  Responsibles. ⌘K block **3700**: `comm_calendar` 3700, `comm_new` 3710,
  `comm_templates` 3720, `comm_celebrations` 3730 ("Birthdays and
  anniversaries this week").
- **Adapter canon:** as A1; process key `hr_comm_post`, route =
  `role_step(_('HR lead'), 'hr_lead')`; when `pb_hr_comm.signoff` is 0 the
  facade schedules directly and the route is never entered (say so in the
  post's chatter: "Scheduled without sign-off — sign-off is switched off").
- **Employee reads** as the system (R56/R104); audience by department /
  company / country (company.country_id) / job / everyone; accents folded
  (R78); `hr.employee.work_email` for the address, skip people without one
  and count them honestly.
- **Actors:** validator (HR), lam.ngo (uid 2326) as a "responsible" who is
  not HR, fixture department 657 (Quality Assurance, 8 test people 17140-
  17147 + 17139) as the audience, `hr_lead` seat on company 5 borrowed and
  returned (R123).

## 2. Design
- **`pb.hr.comm.template`**: `name, subject, body_html, poster_attachment_id,
  company_id` (empty = every company), `active`. Seeded: none (empty
  state teaches).
- **`pb.hr.comm.post`** (`mail.thread`, `mail.activity.mixin`): `subject`,
  `body_html` (native editor), `poster_attachment_ids` (images/PDF), `template_id`,
  `company_id` (= the country), `audience_kind` (everyone / department /
  job / country-all-companies), `department_ids`, `job_ids`, `recipient_count`
  (computed on demand, cached at send), `send_at` (Datetime, company tz),
  `recurrence` (none / weekly / monthly / yearly), `recur_until`,
  `parent_id` (the occurrence chain), `responsible_user_id` (default: the
  company's `hr_lead` holder), `channels` (email only for now; `slack`
  present, disabled with the sentence "Not connected"), `state` draft →
  scheduled → sending → sent | cancelled (+ submitted/approved when the
  route is on), `sent_at, sent_count, skipped_count, nudge_sent_at`,
  `locked_from` (= `send_at` − `pb_hr_comm.edit_window_days` (2)).
  Rules: content fields (`subject, body_html, poster, audience, send_at`)
  may be changed by the responsible only while `now < locked_from`;
  inside the window only an HR lead (`group_hr_comm_manager` or the
  company's `hr_lead` holder) may, and the change is tracked (chatter);
  after `sent` nothing changes (a copy is offered). Company rule +
  visibility: country HR (`group_hr_comm_user`) sees own companies; head
  HR (`group_hr_comm_manager`) sees every company in the session; a
  responsible who holds no group sees and edits the posts they are
  responsible for (rule pair R60).
- **Sender** (`ir.cron` every 10 min, `pb_hr_comm.send_mail` **1**): posts
  `scheduled` with `send_at <= now` → `sending` → expand the audience →
  one `mail.mail` per work email (explicit `email_to`, poster attached),
  burst cap `pb_hr_comm.burst_cap` 500 per tick (the rest next tick,
  honest counts), → `sent` with counts; a recurring post clones its next
  occurrence (`send_at` + period, `parent_id`), stops at `recur_until`;
  each leg under a savepoint (R131); idempotent (a post is picked once by
  state). When the switch is 0: state moves to `sent` with `sent_count 0`
  and a chatter line "Emails are switched off — nothing was sent" (R54).
- **T-2 nudge** (daily 06:00): scheduled posts with `send_at` inside
  [now+2d, now+3d) and `nudge_sent_at` empty → mail + activity to the
  responsible ("goes out on <date>; you can still edit until <locked_from>"),
  stamp. Idempotent.
- **Route** (`pb_hr_comm.signoff` **0**): when on, "Schedule" submits the
  post; HR lead approves in the inbox → `scheduled`; return → `draft` with
  the note. Facts: company, audience size, send date; revision = subject +
  body hash + send_at.
- **Calendar lens** (People → Announcements, `pbim pbim-page pbcm`): month
  grid (Mon–Sun), one pill per post per day (company flag/short code,
  subject, state colour: scheduled / sent / draft / needs sign-off),
  country toggle chips (companies in session), "Coming up" side list (next
  14 days with responsible avatars and the T-2 state), birthdays and
  anniversaries of the week (from `upcoming_celebrations`, cap) as quiet
  rows, "New announcement" (native form, `views` R125), "Templates" door,
  facets: company, state, responsible. Hero: this month's sent / scheduled
  / drafts, and "next goes out in N hours". Empty month teaches.
- **Home lens "Coming up"** (seq 30): the next 7 days' announcements for
  the user's companies + this week's celebrations; gated to internal
  users; the employee-facing version is the email itself (no portal page
  in C1 — the sheet asks for none).
- **Cards**: inherit `pb_rnr.mail_birthday` / `mail_anniversary` QWeb
  views (`ir.ui.view` inherit, not a noupdate edit) into a designed card
  (name, years, a warm line, the company name, no images that need
  hosting). Switch stays `pb_rnr.anniv_mail` 0 (one switch for both,
  D17); the calendar lens says "Birthday and anniversary cards are
  switched off" with the switch name when 0.
- Settings → Announcements (seq 50): Templates card, Responsibles card
  (per company: the `hr_lead` holder shown read-only with "change in the
  Approval Matrix" + a per-company default responsible override
  `pb.hr.comm.default` (company, user)).
- Switches: `pb_hr_comm.send_mail` 1, `pb_hr_comm.signoff` 0,
  `pb_hr_comm.edit_window_days` 2, `pb_hr_comm.burst_cap` 500,
  `pb_hr_comm.nudge_days` 2.

## 3. Tests
T1  Install + gates; route laid; migration idempotent.
T2  Post "DEMO Town hall" (company 5, department 657, send in 3 days,
    responsible lam.ngo): `recipient_count` = people in 657 with a work
    email (assert vs psql); the T-2 nudge job → one mail + activity to
    lam.ngo once (run twice).
T3  Edit window: lam.ngo edits the subject before `locked_from` → ok;
    move `send_at` inside the window → lam.ngo refused with the sentence;
    the validator (HR lead) edits → ok and tracked.
T4  Sender: `send_at` in the past → one `mail.mail` per recipient (capped
    fixture, all `@example.com`), state `sent`, counts right, poster
    attached; run again → nothing; with `send_mail=0` → `sent` with 0 and
    the chatter line. Cancel the mails.
T5  Recurring monthly with `recur_until` +2 months → after send, one new
    occurrence with `parent_id`; the last occurrence makes none.
T6  Route on: `signoff=1`, Schedule → inbox of the HR lead with facts;
    approve → `scheduled`; return → `draft` with the note; `signoff=0` →
    Schedule goes straight to `scheduled` with the chatter line.
T7  Visibility: a company-6 HR user sees none of company 5's posts; head
    HR sees both; lam.ngo (no group) sees only the post they are
    responsible for.
T8  Birthdays: fixture employee with `birthday` = server today (month/day)
    and `anniv_mail=1` in the test DB → `run_celebrations_today` queues one
    birthday mail with the redesigned card (assert the body carries the
    name and the years, no "Odoo"); rerun → none; anniversary the same;
    on payobook the switch stays 0 (log-only proof).
T9  Lens light + dark (month grid, coming up, celebrations), Home "Coming
    up", Settings category; screenshots `RIZE/w2_c1_*.png`; no console
    errors; `unhandledrejection` listener.
T10 ⌘K 3700–3730; People lens `announcements` at 80 (label measured);
    Home lens at 30; Settings at 50; deploy `19.0.1.0.0`, crons active,
    log clean.
T11 Reverts (seat, groups, passwords), mails cancelled; posts stay named
    DEMO (ledger rule 9).

## 4. Report back
As A1, plus the sender's exact idempotency rule, the audience expansion
helper signature, the card views' xmlids, switches, new R-entries, ledger
row, owner items (turn the cards on, real responsibles, Slack later).

## Demo-data rule (owner, 2026-09-16 — D18, ledger binding rule 9)
Every demo record this phase creates on `payobook` is KEPT for future demos, so it
must NOT carry the customer name ("RIZE"/"Rize") anywhere a viewer can see — names,
subjects, notes, chatter, logins, emails, job/department titles, letter bodies. Name
them starting with **DEMO** ("DEMO Town hall"), logins `demo.<role>@example.com`.
Register every one at creation, in the fixture code:
`seed = self.env.get('pb.demo.seed'); if seed is not None: seed.register(records, label)`
(the guard keeps `pb_demo_seed` optional on tenants). The report carries a "Demo
records" table (model, ids, label) and the register count. Any "named RIZE W2" wording
left in this file is superseded by this section.
