# RIZE Wave 2 — Phase X1: the DEMO sweep — no customer name in demo data, and every demo record on the register

Owner ruling D18 (2026-09-16): the demo data built on `payobook` is KEPT for future
demos, but the owner may show `payobook.com` to RIZE's competitors. So nothing a
viewer can see may carry the customer's name — record names, subjects, notes, chatter,
logins, emails, job titles, department names, letter bodies. Demo records start with
**DEMO** instead, and every one of them is on the register of the existing
"Demo data" panel (`pb_demo_seed`) so "Remove demo data" can take them out in one go.

This phase runs AFTER A3 has reported (A3 uses the `rize.w2.recruiter` login until
then) and BEFORE E1. Nothing else may write to `payobook` while it runs.

Read first: `RIZE_LEDGER.md` (all — binding rule 9, D18, the Wave 2 table rows for
A1/A2/A3 and their "demo records" lists), `RIZE_CLOSEOUT.md` (the wave-1 demo data /
test logins section), `pb_demo_seed/models/demo_seed.py` (all of it — the register's
one idea), `pb_demo_seed/seeds/__init__.py`, and this file.

## 0. Scope and non-goals
**In scope:** (1) `pb_demo_seed` grows a public register API any module can call, an
"adopted" profile, a users-are-archived-not-deleted removal branch, and loses its
customer-named label and one dead dependency; (2) `pb_demo_seed` is INSTALLED on
`payobook` (owner-authorised, D18); (3) a one-off sweep script renames every
customer-named demo row and registers every RIZE-programme demo record (waves 1 and 2)
on one seed row named **"DEMO HR programme data"**; (4) proof by whole-word scan;
(5) the rule written into the ledger and the later handovers already carry it.
**Non-goals:** touching the `pb_demo` 4,500-employee VN world, the older
`*.demo@payobook.com` logins (manager/employee/minor/driver1-2/ess1-10 — other
programmes own them), the `pb_tenant` row "Rize Farms" (a REAL tenant record, not
demo data), the province `res.country.state` "Rize" (a real Turkish province), the
`rize` tenant database (D11), pressing **Load** or **Remove** on `payobook` (the data
must stay — the removal path is proven by unit tests only), any change to module
names / xmlids / docs / commit history (engineering-facing, "rize" stays).

## 1. Verified facts (2026-09-16, `payobook`)
- `pb_demo_seed` is `uninstalled` on `payobook` (it was built for the `rize` tenant).
  Every dependency is installed there EXCEPT `pb_payroll_mapping_vn` — and no file in
  `pb_demo_seed/seeds/` or `models/` references it (grep proves it: the only hit is the
  manifest). Drop it from `depends`. The `rize` DB has it installed on its own.
- The user-visible profile label is `'Rize Vietnam — five people, five stories'`
  (`seeds/__init__.py:15`). The profile KEY `rize_vn` is stored in a `noupdate` row on
  the `rize` DB — keep the key, rename the label to `'DEMO Vietnam — five people,
  five stories'`. The manifest description says "`rize_vn` is the one that ships" —
  fine (engineering text), but re-read the whole description for anything a
  Settings viewer sees (the `summary` is shown in Apps).
- Register model `pb.demo.record` (`seed_id, sequence, model_name, res_id, label`);
  removal walks `sequence desc` and unlinks under a savepoint each (`remove_demo`
  :248); `PROTECTED_MODELS` (:41) refuses `res.users` and `res.company`; the seed
  row is per company and "one loaded world per company" is enforced (:198-207);
  `SeedContext.track` (:516) is the only writer and dedups per (model, id); `last=True`
  puts a row below zero so it is removed last (private contacts).
- Whole-word scan of every text/jsonb column (`~* '\mrize\M'`, `ir_*` excluded) on
  `payobook` today — the demo rows to rename:
  `hr_job.name` 6 (ids 147–151, 153 "RIZE W2 …"), `pb_hiring_requisition.title` 9
  (55–63), `pb_hiring_jd.title` 5, `pb_hiring_posting.subject/body_html` 3,
  `pb_hiring_referral.candidate_name/email` 1, `hr_applicant.partner_name/email_from/
  email_normalized` 4, `pb_hiring_interview.candidate_name/email/location` 6/6/5,
  `pb_hiring_feedback.notes` 6, `pb_hiring_country_rule.note` 1, `calendar_event.name/
  description/location` 6/6/5, `calendar_attendee.common_name` 6, `res_partner.name/
  complete_name/email/email_normalized` 5 (21912 recruiter, 21913 referred candidate,
  22960–22962 candidates), `hr_employee.name/legal_name/work_email` 1 (17338 "RIZE W2
  Recruiter") + `hr_employee_public` (a view — follows), `resource_resource.name` 1,
  `res_users.login/signature` 1 (uid 4446 `rize.w2.recruiter@example.com`),
  `discuss_channel.name` 1 (106, a chat name computed from the partner),
  `biz_approval_request.title` 13, `biz_approval_event.summary` 68,
  `biz_approval_process.description` 2 (READ these two first — if they are the
  seeded process descriptions written by A1's `register_chain`, the fix is in
  `pb_hiring`'s code/data AND the row), `pb_alert.key/title/text` 13,
  `mail_activity.summary/note/res_name` 38/29/39, `mail_message.subject/body/
  email_from/reply_to` 149/125/98/62, `mail_tracking_value.new/old_value_char` 19/2,
  `mail_mail.body_html/email_to` 423/26 (the leftover test mails — check `state`; the
  cancelled ones (R37/R47) are deleted, not rewritten), `mail_compose_message.*` 1
  (a transient wizard row — vacuum, do not edit), `bus_bus.message` 7 (transient,
  expires — leave), `project_task.name/description` 1/1 (READ it — decide real vs
  demo and say which), `pb_tenant.*` and `pb_tenant_backup.path` (LEAVE — real
  tenant), `res_country_state.name` 1 (LEAVE — real province).
  The earlier substring scan also hit `payment_provider.auth_msg` 23 and
  `project_task.description` 102 — those are the word "authorized"; the whole-word
  regex is the one that counts. Re-run the scan after A3 reports: A3 was told to
  name its records DEMO, but verify.
- Wave-1 test actors already carry neutral names and `@example.com` logins (TIDY
  rule 15): employees 17122 Ngô Bảo Lâm (uid 2326), 17138 Quách Anh Tuấn (2333),
  17139 Thái Ngọc Diệp (2336, manages dept 657 "Quality Assurance"), 17140–17147
  (the eight QA test people), 2337 linh.quan. Nothing to rename there; everything to
  REGISTER (see §2.3). Passwords stay as they are.
- The demo-database gate: `is_demo_db()` (`pb_hr_payroll_formula/models/
  demo_approval.py:44`) is true when any module is flagged demo or the DB name
  carries a marker; on `payobook` Load/Remove otherwise go through the
  `pb.demo.proposal` approval — that is correct and stays.

## 2. Design

### 2.1 `pb_demo_seed` → `19.0.1.2.0`
- **Public register API** on `pb.demo.seed` (both `@api.model`):
  - `programme_seed()` → the seed row named **"DEMO HR programme data"**, profile
    `adopted`, `state='loaded'` (stamped `loaded_on/loaded_by` at first creation),
    `company_id` = company 5; find-or-create, `sudo()`.
  - `register(records, label=None, last=False)` → appends `pb.demo.record` rows to
    the programme seed for every record in `records` (any model, mixed recordsets
    allowed one model per call), `sequence` = current max + 1 per row (or below the
    current min when `last`), dedup per (model, id), refuses `PROTECTED_MODELS`
    except `res.users` (allowed — see removal), returns the count added. Callers in
    OTHER modules guard with `seed = self.env.get('pb.demo.seed'); if seed is not
    None: seed.register(...)` — no manifest dependency on `pb_demo_seed` is added
    anywhere (it is optional on tenants). Log one info line per call.
  - Refactor `SeedContext.track` to call one shared private writer so the two paths
    cannot drift.
- **Profile `adopted`**: label `'Records adopted from the product'`, `builders: []`.
  `load_demo` on it is a no-op that marks loaded; the "one loaded world per company"
  check IGNORES profile `adopted` in both directions (an adopted register beside a
  built world is the normal case). The Settings panel hides **Load** for it and shows
  the record count + **Remove demo data** + "What it made".
- **Removal of users**: in `remove_demo`, a registered `res.users` row is
  `write({'active': False})` under its savepoint instead of unlinked (audit trails
  point at users); counted separately and the notification says "N logins were
  switched off rather than deleted". `res.company` and the rest of the protected
  set stay refused.
- **`preview_remove()`** (button "What would be removed"): counts per model of live
  registered rows, plus the list of registered users that would be switched off —
  read-only, so it is safe on `payobook` and gives the owner a truthful number.
- Label rename (§1), manifest `depends` minus `pb_payroll_mapping_vn`, manifest
  summary/description checked for anything user-facing with the customer name.
  White-label sweep of every string in the module while there.

### 2.2 The sweep script — `tools/demo_sweep_payobook.py`
Run through the server's shell against `payobook` only (ledger deploy ritual for
shell runs; commit the script — it is the audit trail). Idempotent: a second run
changes nothing and says so. Three parts, each under a savepoint, with counts printed:
1. **Rename.** Whole-word replacements, case-preserving: `RIZE W2 ` → `DEMO `,
   `RIZE` → `DEMO`, `Rize` → `Demo`; addresses `rize.w2.<x>@example.com` →
   `demo.<x>@example.com` (login, partner email, employee work_email, applicant
   email_from + normalized, interview/referral candidate_email, attendee email,
   `mail_mail.email_to`, message `email_from/reply_to`). Go through the ORM for
   translated (`jsonb`) and computed-store fields (`hr.job.name`, partner
   `complete_name`, `hr.employee` → `resource.resource`, the chat channel name —
   recompute rather than hand-write); plain SQL `regexp_replace` is fine for
   chatter bodies, activities, tracking values, approval events, alerts. Cancelled
   `mail.mail` rows: delete. Transient rows: vacuum. Print the before/after count per
   column. The recruiter login becomes `demo.recruiter@example.com` (same password
   `RizeW2!2026` — a password is not visible; leave it), employee 17338 "DEMO
   Recruiter", partners "DEMO Mai Phuong Thao" etc., jobs "DEMO Site Agronomist" …
2. **Register.** Collect every RIZE-programme demo record into one list, sort by
   `(create_date, id)` (creation order is dependency order — the module's own
   principle), and `register()` them in that order; employees' private partners
   `last=True`. What counts as a programme record:
   - Wave 2: the hr.job rows above, requisitions 55–63 and every row that points at
     them (jd + versions, postings, referrals, steps, budget lines the module made,
     interviews 77–83, feedback, reschedules, stage logs, applicants incl. 175–177,
     calendar events + attendees, approval requests/tasks/events for those records
     via `res_model/res_id`), partners 21912/21913/22960–22962, employee 17338 +
     user 4446, A3's "Demo records" table from its report (offers, BGV, docreqs,
     covers, the closed hire's employee/contract/pay package/onboarding case/login,
     the agency vendor "DEMO Talent Partners" if A3 created it).
   - Wave 1: the test actors (employees 17122, 17138–17147; users 2326, 2333, 2336,
     2337 + their partners), department 657 if its `create_date` falls inside the
     wave-1 window (2026-08-31 … 09-02) and `create_uid` is a programme login — say
     which; and every row in the wave-1 modules that points at those employees:
     enumerate models in `pb_lifecycle, pb_assets, pb_onboarding, pb_offboarding,
     pb_probation, pb_pip, pb_comp_ben, pb_rnr, pb_budget, pb_contract_lifecycle,
     pb_vendor_access, pb_zoho_bridge` with an `employee_id` (or `applicant_id`,
     `case_id`, `nominee_id` … read each model), plus `hr.contract`, letters
     (`pb.hr.letter`), journeys/cases, feedback requests, and the named wave-1
     fixtures listed in `RIZE_CLOSEOUT.md` (vendors, agreements, budgets,
     nominations, benefit plans, assets) — match by the closeout's names, NEVER by
     the word "demo" alone (the module's own warning: spelling is not origin).
   - NOT: anything in §0 non-goals; `igc1.validator` (uid 2065, archived at
     closeout by hand); payslips/pay runs of real-looking people.
   Print counts per model and the grand total; the seed's `summary` gets the same.
3. **Prove.** Re-run the whole-word scan (the SQL generator is in this file's
   history: every text/jsonb column, `~* '\mrize\M'`, `ir_*` excluded) — the only
   survivors allowed are `pb_tenant.*`, `pb_tenant_backup.path`,
   `res_country_state.name`, `bus_bus.message` (until it expires) and whatever
   `project_task` row you ruled real. List them in the report with the reason.

### 2.3 Rule for every later phase (already written into E1–C1 and the ledger)
Every demo record a phase's tests or fixtures create on `payobook` is (a) named
starting with **DEMO** (logins `demo.<role>@example.com`), never with the customer
name, and (b) registered at creation through `env['pb.demo.seed'].register(recs,
label)` behind the `env.get` guard — in the fixture code, not as an afterthought;
the phase report carries a "Demo records" table (model, ids, label) and the
register count.

## 3. Tests
T1  `pb_demo_seed` unit tests: existing suite green; `register()` dedups, numbers
    after the current max, `last=True` goes below the min, refuses `res.company`,
    accepts `res.users`; a caller without the module (`env.get` returns None) is a
    no-op pattern (test the guard in a tiny fixture).
T2  `remove_demo` on a register holding a user + records: records gone, the user
    archived not deleted, counts and the sentence right; blocked rows still named.
T3  Profile `adopted`: `programme_seed()` idempotent; it does not block loading
    `rize_vn` in the same company, nor the reverse; Settings panel hides Load and
    shows the count; `preview_remove()` numbers equal a hand count.
T4  Label reads "DEMO Vietnam — five people, five stories"; grep the module for the
    customer name in user-visible strings → none; for "Odoo" → none.
T5  Install on `payobook` via the detached ritual (`-i pb_demo_seed`): state
    `installed`, `19.0.1.2.0`, the noupdate "Demo data" row present and `empty`,
    log clean, no other module changed state (compare `ir_module_module` before and
    after — `pb_payroll_mapping_vn` MUST still be `uninstalled`).
T6  Sweep part 1 on `payobook`: per-column before/after counts; login
    `demo.recruiter@example.com` signs in with the unchanged password; the Hiring
    lens, a requisition, an interview, a candidate page and the chat show DEMO names
    (Chrome, light + dark, screenshots `RIZE/w2_x1_*.png`); no console errors.
T7  Sweep part 2: counts per model; every wave-2 row from §2.2 present on the
    register; a random 20 wave-1 rows spot-checked against the closeout's list;
    `preview_remove()` on `payobook` returns the same totals (read-only — do NOT
    press Remove).
T8  Sweep part 3: the whole-word scan is clean but for the allowed survivors; run
    the sweep a second time → "nothing to do" and identical counts.
T9  Settings → Demo data panel on `payobook` light + dark: two rows ("Demo data",
    empty; "DEMO HR programme data", N records), plain English, Lucide, no dead
    ends; screenshot.
T10 Deploy verified (files byte-identical, version, log), commits per feature
    (module change / script / docs), nothing pushed.
T11 Reverts: none needed (no grants, no password changes); `payobook` data stays.

## 4. Report back
As A2, plus: the per-column rename counts, the register total per model, the
survivors list with reasons, the exact `register()` signature and the guard
snippet for the ledger, the new login table (old → new), `preview_remove()` totals,
new R-entries (continue after A3's last), the ledger row for X1, and owner items in
plain English (what "Remove demo data" would now take out, that Load on `payobook`
would build the five-people world in company 5 and is untested there, the
`project_task` ruling).
