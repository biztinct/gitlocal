# LEARNING L6 — Numbers and the Overview, finished

Programme: LEARNING. Design page `docs/design/rize-learning-blueprint.html` §5 "Overview",
"Numbers", §7 phase L6. Ledger binding. Predecessors L0–L5 reports: take every facade and
field name from them (hours L2, sessions L4, requests/feedback/follow-up/skills L5).

Report back to `docs/handovers/learning/L6_REPORT.md`.

## 1. Scope
1. **Numbers** gains: Hours (per person, department, course, kind; period), Cost (claims
   paid, approved outside requests, session costs; against the yearly allowances and the
   HR-operations budget line when `pb_budget` is installed), Compliance (required training
   in date by site, department, country, safety group — from the L2 matrix summary), Did it
   work? (course ratings, recommend %, manager follow-up effect), Country reports (the four
   L2 exports in one place), and a flat **Assignments** sheet for BI (one row per assignment
   with every dimension) (§3.1).
2. **Overview** finished: every tile live (compliance %, certificates, paths, sessions this
   week, requests waiting, follow-ups waiting), the headline composed from the blocks, the
   queue complete; a "calm" state when nothing waits (§3.2).
3. **Settings category "Learning"** (`pb_settings` registry): cards Report pack (on/off,
   weekly/monthly, recipients, "Send me a test"), Reminders (switch, escalation days,
   renewal window, enforcement cap), Feedback (feedback on/off, follow-up on/off and days),
   Country packs (L2 switches), Day one (L0 switch) — all parameters that today have no UI
   (§3.3).
4. **Report pack** body extended with hours, cost, compliance, effect; attachment = the full
   spreadsheet; recipients editable; preview modal (§3.4).
5. **Home › TEAM**: the Learning section shows three quiet chips — late courses (today),
   certificates expiring in 30 days, requests waiting on this manager (§3.5).
6. Learning record PDF (L1) gains hours and sessions. Tests, demo, deploy.

**Binding non-goals.** No new money door (awards lane only). No `pb_budget` edits: read the
budget line if present (`env.get`). No change to `pb_insights_hub` beyond the existing lens.
No BI connector; the flat sheet is the BI door.

## 2. Verified plumbing facts
| # | Fact | Where |
|---|---|---|
| F1 | `analytics.get_numbers()` payload keys `allowed, from, to, total, empty, headline, tiles, by_department, by_course, by_reason, by_certificate, cert_expiring, trend, claims, lists, reasons, core` (:129-185); `_core` :189-235; `_tiles` six + `_cert_tiles` four (:237-285); only duration source `channel.total_time` (hours float) via `training_common.minutes()`; assignments carry `company_id` only (site/country come from the employee at read time). `export_xlsx` sheets Summary, By department, By course, Why, Certificates, Week by week (:452-571), base64, no attachment. | `pb_training/models/analytics.py` |
| F2 | Pack: `_deliver` (:167-200, `MAIL_CAP 20`), `_body` renders QWeb `pb_training.mail_pack` (`data/mail_template_claims.xml:112-151`: label, headline, tiles table, claims count, expiring certificates, footer), `_sheet` :220-241; settings `report_pack` ('0'), `report_pack_period` ('monthly'; "week*" = weekly), `report_pack_email` (not in DEFAULTS), `report_pack_last`; cron daily `_cron_pack`; **no settings UI** — only the read-only `pbtn-packline` on the Claims tab (`training_board.xml:726-758`) and `send_pack()` → `run_now()` (managers). Emailed-report precedent with test address + preview modal: `pb_rnr/models/digest.py` (`send_digest` :237; settings `pb_rnr.digest_mail`, `digest_test_email`; modal `rnr_board.xml:435-447`). Toggle precedent `pb_comp_ben/models/pb_paycal.py:96, 174-185`. | |
| F3 | `training_numbers.xml` order: denied :34, header :44-60, range :66-83, filters :89-115, empty :121, headline :134, tiles :140-151, Week by week :158, three-split :190/:212/:235, Certificates :260, Claims :281. JS `get_numbers` :139, `export_xlsx` :218. Insights lens seq 40 (`training_palette.js:276-282`). | |
| F4 | Overview `pb_training_overview.py:36-84` keys `allowed, people, courses, headline, certificates, calm, queue[claims, requests, late, certs], month, departments`; XML hero :44, month :64, certificates :74, departments :98. | |
| F5 | TEAM: `pb_home_hub/models/team_facade.py` (`pb.home.team`), hard-coded sections tuple :200-206 (`decisions, probation, goals, training, hiring`), `_training()` :566-590 reads `pb.my.training.team()` and keeps overdue rows → `{overdue, overdue_people, due, done, people[], more}`; lens `team_lens.xml:167-185` draws `trainingWords` (`team_lens.js:195-201`) + "Open team training" → `/my/training/team`. Header forbids amounts/costs in the payload (`test_team_p3c`). Requests appear only in the `decisions` tiles via `pb.approval.inbox.list_requests` (:427-451); `_tile_of` :92-104 maps area → tile; the claim seed passes no `area` (lands on "other" — unverified). | |
| F6 | Budget: `BUDGET_TYPES` manpower/hr_ops/admin, no `training` (`pb_budget/models/budget_common.py:17-21`); help says training spend sits under `hr_ops` (`pb_budget_line.py:89-92`); `pb.budget.expense` fields (`budget_expense.py:34-76`). Awards: `pb.incentive` kind `training` + `claim_ids` (`pb_training/models/incentive_ext.py:33-39`); `claim._make_award()` idempotent (`claim.py:415-460`). | |
| F7 | Settings registry `SETTINGS_CATEGORIES` + `GROUP_OF_CATEGORY` (`pb_settings/static/src/js/settings_hub.js:256-309`, no learning entry); card precedents `pb_lifecycle/static/src/js/lifecycle_palette.js:57-71`, `pb_hiring/static/src/js/hiring_palette.js:114-139`; server gate `pb_settings/models/pb_settings.py:109`. L2 planned a "Required training" card — L6 folds it into one "Learning" category (if L2 shipped its card, move it). | |
| F8 | Learning record report (L1): `report/learning_record.xml`, `models/learning_record.py`. | |

## 3. Architecture
### 3.1 Numbers
- `get_numbers` payload += `hours: {total, by_person:[{employee, department, hours, courses, sessions}], by_department, by_course, by_kind:{online, session, toolbox, signoff}}`, `cost: {claims_paid, claims_agreed, requests_approved, sessions, total, allowance_total, allowance_used_pct, budget:{line, spent, left}|null}` (money as words + raw with currency; one currency per company — never add two currencies), `compliance: {percent, by_site, by_department, by_country, by_group, missing, expiring}` (from `pb.training.requirement.matrix` summary, L2; `null` when L2 absent), `effect: {ratings_avg, ratings_count, recommend_pct, followup_effect_avg, followup_used_pct, by_course_top}`, `countries: [{key, label, on}]` for the report buttons. Each block through `_safe` with a default; each has an "empty" sentence.
- Sections added to the numbers page in this order after "Why they were set": Hours · Cost · Required training · Did it work? · Country reports (buttons) · then Certificates, Claims. Tiles strip gains `hours_total`, `cost_total`, `required_pct`, `ratings_avg` (quiet; grey at zero).
- Spreadsheet sheets += Hours (by person), Cost, Compliance, Effect, **Assignments** (flat: employee, department, job, site, country, safety group, course, kind, reason, path, requirement, assigned on, due, completed on, state, score, hours, certificate valid until, version).
- Filters += site (`work_location_id`), country, kind.

### 3.2 Overview
- Blocks: `compliance` (L2 summary), `paths` (L3), `sessions` (L4: this week count, seats free, sign-offs waiting), `requests` (L5 waiting on HR), `followups` (waiting on managers), existing `certificates`, `month`, `departments`. Headline composer: one sentence per non-zero concern, max three, in a fixed priority (late → missing required → expiring → sign-offs → requests); zero concerns → calm hero "All clear. 214 people are in date." Queue rows for every block with a count > 0, each opening its lens/tab/filter.
- Phone: hero + queue first; departments collapse.

### 3.3 Settings category "Learning"
- `registry.category(SETTINGS_CATEGORIES).add("learning", { key:"learning", group:"hr", icon:"graduationCap", label:_t("Learning"), blurb, groups: TRAINING_GATE (manager/head), cards:[report_pack, reminders, feedback, country_packs, day_one] }, { sequence: 48 })`; `GROUP_OF_CATEGORY.learning = "hr"`; server gate row.
- Each card opens a small OWL settings panel (client action `pb_training_settings`, tabs = cards) that reads/writes the `ir.config_parameter` keys through one facade `pb.training.settings_get()/settings_set(values)` (head of training only), with plain labels and the effect sentence under each switch ("Reminders go to the person 3, 1 and 0 days before the date, then every 3 days; the manager after 2 days late; the HR lead after 5."). Recipients field validates emails.

### 3.4 Report pack
- Body (`mail_pack` QWeb) += hours total and top 5 people, cost line vs allowance, compliance % and missing count, ratings line, expiring certificates (exists), links to Numbers. Attachment = the full spreadsheet (all sheets). "Send me a test" sends to the current user only. Preview modal clones `rnr_board.xml:435-447`.

### 3.5 Home › TEAM
- `pb.my.training.team()` payload += `expiring_certs` (count + names, 30 days), `waiting_on_me` (course requests + more-time requests where this user is the next approver, count). `team_facade._training` passes them through (no amounts); `team_lens.xml` Learning section draws two more quiet chips. Edit `pb_home_hub` minimally (NAV module — note the touch in the report and keep its tests green).

## 4. Safety rails
Ledger L1–L8; one currency per total (never add two); nothing writes money; settings
writable by head of training only; every new block has an empty sentence; pack never sends
to more than `MAIL_CAP`.
Commits: (a) numbers blocks + sheets + filters; (b) Overview; (c) settings category +
panel; (d) pack + TEAM chips + record PDF; (e) demo + docs.

## 5. Tests
- **T1** hours block adds up (person = Σ courses + sessions); by kind; period filter.
- **T2** cost block: claims paid/agreed, approved requests, session costs; allowance used %; budget line read only when `pb_budget` present; single currency guard raises otherwise.
- **T3** compliance block equals the L2 matrix summary for the same filters; `null` without L2.
- **T4** effect block equals independent recomputation from feedback answers.
- **T5** Assignments sheet: one row per assignment, columns in order, dimensions resolved.
- **T6** Overview headline priority and calm state; queue rows only when > 0.
- **T7** settings facade: head only; email validation; switches round-trip; the daily job honours changed values.
- **T8** pack body contains the new lines; test send goes to the user only; cap.
- **T9** TEAM payload has no amounts (existing `test_team_p3c` stays green); chips counts.
- **T10** no "Odoo", no emoji; VI.
- **T11** Chrome walk: Numbers sections + downloads; Overview with concerns and calm; Settings › Learning cards and a switch change reflected; pack test send; TEAM chips; console clean.

## 6. Deploy
Normal tier (`pb_training`, `pb_settings` registry file, `pb_home_hub` minimal) unless a
migration is needed; usual ritual; stop at the deploy gate.
