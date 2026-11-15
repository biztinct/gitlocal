# WDGAP S5-A — report: kinds of leave and how they are earned (`pb_leave_setup`)

Implemented, tested and self-reviewed by the Opus builder, 2026-11-15/16 (owner pause in
between). Branch `wdgap-s5a` from `origin/19.1` @ `abc2259b6`. **Not merged, not deployed.**

## 1. What was built

| Item | What HR / the employee gets | Where |
|---|---|---|
| 1 Set-up screen | **Kinds of leave** (client action `pb_leave_setup.action_pb_leave_kinds`, tag `pb_leave_kinds`), reached from **Settings › HR** (registry `pb_settings_category`, key `leave_kinds`, seq 42, one card so it opens directly) and **⌘K** (`wf_leave_kinds` 3830, `wf_leave_starters` 3840 opens the ready-made dialog). Filter-kit list (switched on/off, how earned, pay, country, company, counted, unit; views Every kind / Switched on / Waiting for review / Pay to decide), quiet glance + three steps (switched on · waiting for review · switched off), **set-up check** card (kinds switched on with no pay decision — click a chip to open it; people with no date of joining; ready-made kinds to review). **Guided drawer**, five numbered steps: 1 what it is (name in English/Vietnamese/Indonesian, company, "for people working in"); 2 how people take it (whole/half days/hours, who approves, **Only HR can enter this**, can be asked for after it happened + tell HR, a document is needed); 3 pay (paid/partly/unpaid/not decided, who pays, shares); 4 allowance (counted, how the days are given, days a year, waiting months, extra days for long service table, most a person can hold, days run out N months after the year, take days before they are earned, build-up starts from, carry warning); 5 **what it means and what people see** (rules in plain words, service table, the employee's tile and form option, live as values change). Source of every ready-made figure shown under the field it backs. "Days added recently" + "Add the finished months now". | `pb_leave_setup/models/leave_setup.py`, `static/src/{js,xml,scss}/leave_setup*` |
| 2 Build-up | Engine A (FACTS): `pb.leave.earning` = one audit row per person × kind × month (or year), unique `posting_key`, write/unlink refused, create only from the job; advisory lock `pb.leave.balance:<emp>:<kind>` (the Rize policy's own key); ONE allocation per person, kind and leave year (`hr.leave.allocation.pb_ls_year`, unique per person/kind/year), its days SET from the posted rows. A month is posted after it ends ("earned so far"); joiner/leaver share by days in the month; waiting period; service steps from the date of joining (highest step reached; counts from the month it is reached); most-you-can-hold cap (row flagged `capped`); days run out N months after the year (`date_to`). **L2**: per kind `pb_ls_take_ahead`, default OFF; ON puts the rest of the year in the allocation from 1 January and takes it back for a known leaver or when switched off. Daily job `cron_leave_earning` — quiet (no mail, no to-do, no chatter), catch-up bounded to 12 months and to "Build-up starts from", safe on an empty database. "All at once each year" posts the year's share on the first run of the year or the day the person becomes entitled. Never touches: kinds left at "Given by HR" (the default — existing kinds keep today's behaviour), hours kinds, kinds bound to a leave policy (Rize), opening-balance or HR allocations. | `pb_leave_setup/models/earning.py`, `leave_type.py`, `data/ir_cron.xml` |
| 3 Ready-made kinds (L1) | `pb_leave_setup/data/starters.json` (never `pb_pack_*`): **VN 8, ID 12, IN 5, SG 7, TH 5, KH 5, MY 6** kinds, names in en/vi/id, a source note on every figure (law + article; en always, vi for VN, id for ID), pay rule written explicitly (VN sick = 75 % from the insurance fund; maternity from the fund), steps (VN +1/5 y, SG +1/y to 14, MY 8/12/16, KH +1/3 y). Applied per company from "Ready-made kinds": review list (tick/untick, "Where the figures come from"), created **switched off and waiting for review**, names written as field translations, **never twice** (`pb_ls_starter_key` per company, archived included), never `pb_policy_code` / `pb_policy_category`. Kinds whose pay is genuinely split (TH maternity, KH sick) say "pay to decide" and **cannot be switched on until HR decides**. India figures are labelled placeholders (state law). Nothing is created or switched on by install. | `models/starters.py`, `data/starters.json` |
| Fix in lane | **Balances ignore days that ran out.** HR board `pb.timeoff._balances` and My Leave both use one rule (`pb.timeoff._pb_balance_numbers`): validated allocations − validated taken, less allocations whose `date_to` < today and the days core charged to them (`_get_consumed_leaves`). With nothing run out the numbers are the old ones and core is not called. Board kinds are now the companies' own + shared ones (it listed every company's). | `pb_timeoff/models/pb_timeoff.py` |
| My Leave | Override (no `pb_ess_workforce` edit): tiles use the rule above; a building-up kind shows "N days earned so far this year", "Next: 1.08 days on 1 Dec 2026" and, when taken ahead, "Includes N days not earned yet" (xpath on the tile's "used" line). `_my_appliable_types` drops "Only HR can enter this" kinds (page, preview and apply all ask it, so a crafted post is refused). | `models/ess_workforce.py`, `views/portal_templates.xml`, `static/src/scss/leave_setup_portal.scss` |

Rights: read = Time Off officer, HR manager, payroll manager, system; write = Time Off
administrator, **HR manager (tenant HR)**, system. Every method passes its own gate, then reads
and writes under sudo inside `env.companies`. The engine writes allocations as the system user
(see gotcha S5A-3).

**Versions:** `pb_leave_setup` **19.0.1.0.0** (new, install with `-i`); `pb_timeoff`
19.0.1.11.0 → **19.0.1.12.0**.

## 2. Files edited outside the new module

- `pb_timeoff/models/pb_timeoff.py` — `_balances` (expiry rule + company filter on kinds), new `_pb_expired_parts`, `_pb_balance_numbers`; `fields` import. `_apply_types` unchanged (nothing needed).
- `pb_timeoff/__manifest__.py` — version + comment.
- No `pb_timeoff/i18n` change: no new user-visible string in `pb_timeoff`.
- Not touched: `pb_ess_workforce`, `pb_me_portal`, `pb_pack_*`, `pb_hr_workforce`, `pb_mission`, `pb_schedule`, `pb_settings`, `pb_hub` (registries only).

## 3. Tests

Local only (`wdgap_s5a_t`, copy of `upd_p6_t_tpl`, vi + id installed; first `-u` of
pb_timeoff, pb_ess_workforce, pb_me_team, pb_updates, pb_clock, pb_settings, pb_hub,
pb_filter_kit, pb_me_portal to HEAD).

**New suite** `pb_leave_setup` (tag `wdgap_s5a`): **37 test methods, all pass** (final clean
run on a fresh copy — see §3b).

| # | Case | Test |
|---|---|---|
| E1 | Month maths: full month with step (13/12), joiner on 16 March (16/31), step reached in March (Feb old rate, Mar new), leaver 15 April (15/30, nothing in May), waiting 3 months (Jan joiner: nothing to March, 21/30 April), no start date (base share, no step; waiting kind → "no start") | `test_e1_month_maths` |
| E2 | Each finished month once; allocation = Σ rows; same-day re-run posts nothing; next month only April; one allocation per person/kind/year; current month not earned; "Build-up starts from" respected | `test_e2_*`, `test_e2b_*` |
| E3 | Most a person can hold: 1, 1, 0 (capped), 0 (capped) | `test_e3_*` |
| E4 | Take ahead: 2 earned + 10 to come = 12; leaver at end of June = 6; switched off → 2; on 2 January the whole year is there before any month ended | `test_e4_*`, `test_e4b_*` |
| E5 | 4 days asked with 3 earned → core refuses; take ahead on → accepted | `test_e5_*` |
| E6 | All at once: ID shape (12 days after 12 months; due 10 July, 175/365 share, once a year); MY shape 8 + steps → 16 at 6 years | `test_e6_*` |
| E7 | Quiet (no mail.mail, no mail.activity); "Given by HR" kind untouched; an HR/opening allocation untouched and not "this year's"; daily job on a database with nothing to build up → `{}` | `test_e7_*`, `test_e7b_*` |
| E8 | Policy-bound kind and hours kind never earn | `test_e8_*` |
| E9 | Audit rows: no change, no delete, no hand-made row | `test_e9_*` |
| B1 | HR board: allocation run out (5, 2 taken from it) + current 10 → 10 / 0 / 10 (was 15 / 2 / 13); nothing run out → exactly the old sums, core not asked | `test_b1_*` |
| B2 | One number: employee tile 10; employee preview left 10, after 9; manager "left after this" 9 | `test_b2_*` |
| B3 | QF3 over-balance refusal still right (14 days → over and blocked) | `test_b3_*` |
| B4 | Board lists only the companies' own and shared kinds | `test_b4_*` |
| B5 | Every day ran out, none taken since → the tile disappears | `test_b5_*` |
| S1 | Plain login refused everywhere; officer reads, cannot save or apply ready-made; tenant HR manager (no system rights) saves | `test_s1_*` |
| S2 | **Tenant staff reach**: Settings gate resolves True for a tenant HR manager (False for a plain login) with the palette file's own gate list; the client action has no groups; registry spellings match `pb_settings` source | `test_s2_*` |
| S3 | New kind starts off; switching on with no pay decision refused; with one → on; off again; partly paid from a fund kept; paid with nobody paying refused; "Every country" stays every country through re-saves (walk finding) | `test_s3_*` |
| S4 | Used kind: unit / counted refused, same values fine (core refuses even an unchanged `requires_allocation`); under a leave policy pay and earning refused, same pay fine | `test_s4_*` |
| S5 | Building up: refusals (not counted, hours, 0 days); start month = this month; steps saved; duplicate step years refused; start month normalised to the 1st | `test_s5_*` |
| S6 | vi/id names written into the field's translations | `test_s6_*` |
| S7 | Preview: rules, service table (12/1, 13/1.08), tile, document; Only-HR kind not offered | `test_s7_*` |
| S8 | List filters + step counts; "Add the finished months now" only for a building-up kind; by a tenant HR manager WITHOUT Time Off rights on a take-ahead kind → no failure, allocation grows (walk finding) | `test_s8_*`, `test_s8b_*` |
| S9 | Set-up check: count of kinds with pay to decide = list + "more", the filter finds it, deciding it lowers the count; people with no date of joining counted | `test_s9_*` |
| S10 | White-label: no vendor name in any screen file, `.po` msgstr or ready-made data (engineering comments excluded) | `test_s10_*` |
| R1 | Ready-made data: 7 countries, unique keys, unpaid kind each, 3 names, source per kind/days/steps, pay rule accepted by `_classification`, no policy code/category | `test_r1_*` |
| R2 | Nothing created or set to build up by install | `test_r2_*` |
| R3 | All 7 countries: created off + waiting for review, country, company, sources, vi/id names; again → 0 created, all skipped; review list shows "made"; VN annual monthly 12 + steps; VN sick partial 0.75 from the fund; drawer shows the source in the reader's language | `test_r3_*` |
| R4 | TH maternity cannot be switched on until pay decided; then on and no longer "waiting for review" | `test_r4_*` |
| R5 | Unknown country refused; empty tick list refused; review list states | `test_r5_*` |
| P1 | Real employee login (portal tier): Only-HR kind not offered; crafted apply refused; HR still enters it | `test_p1_*` |
| P2 | Earned-so-far and next-credit labels on the tile | `test_p2_*` |
| P3 | Own numbers only | `test_p3_*` |
| P4 | **HTTP** as a real portal login: `/my/work/leave` 200, the building-up kind and its earned line rendered, Only-HR kind absent | `TestPortalHttp.test_p4_the_page` |

**3a. Suites of every touched module vs the baseline** (same copy; baseline recorded BEFORE
any edit, unchanged tree):

| Run | Tests | Failures |
|---|---|---|
| Baseline (pb_timeoff 129, pb_ess_workforce 146, pb_me_team 22) | 297 | 1 failed + 8 errors: `TestLeaveRules` ×6 (lock fires in create on this template), `TestTimeoff` 03/05 ("account no longer in use"), `TestP8Adversarial.test_ack_week_only_touches_my_own_shifts` |
| With `pb_leave_setup` installed (+ its 36 methods at the time) | 345 counted | **the very same 9, test for test** (`diff base.fails full1.fails` empty) |

The combined run was made before the walk fixes; those changed only `pb_leave_setup` files
(engine writes as the system user, drawer save of country/company, labels, CSS prefix, the
"not earned yet" rounding) — no `pb_timeoff` change since, and the new suite was re-run in full
after them (§3b).

Note: `TestTimeoff.test_05_balance_math` already errors at baseline on this template before
it reaches a balance, so the board's balance change is proven by B1/B4 here, not by it.

**3b. Final run** after the walk fixes, on a fresh copy of the template: see the line below
(filled in when it ended).

Fresh copy of `upd_p6_t_tpl`, same first `-u` list, `-i pb_leave_setup --test-tags
/pb_leave_setup`: **37 / 37 pass, 0 failed, 0 errors** (the run before the last fix had one
failure, S3: on CREATE core recomputed the kind's country from the company even with
`country_id: False` in the same values — "Every country" is now written again on its own).

**3c. Browser walk** (Claude in Chrome, local copy, `s5a.localhost:8531` — its own cookie jar,
jobs off; DEMO people: `demo.s5a.hr` = HR manager, NOT system admin; `demo.s5a.emp` = employee login):
- Settings › **HR** shows "Kinds of leave"; Open → the screen. Set-up check, glance, steps,
  filter panel, list all render; "73 kinds that are switched on have no pay decision yet"
  (template's stock kinds), chips open the drawer.
- Drawer for VN Annual leave (ready-made): five steps, names in three languages, sources under
  pay / days / steps, service table to 30 years, tile + form mock, "Days added recently"
  (five months, "+1 for 7 years of service"). Ticked take-ahead → preview updated live; Save.
- Ready-made dialog: seven countries, Indonesia → 12 kinds with summaries and sources; "Add 12
  kinds, switched off" → list jumps to "Waiting for review" (15); ID Sick leave → banner "A
  starting point — please review…", Switch on → "Switched on. People can ask for it now."
- Employee `/my/work/leave`: tile "7.58 days left · 5.42 days earned so far this year · Next:
  1.08 days on 1 Dec 2026 · Includes 2.16 days not earned yet" (rounding fixed after the walk:
  2.17); fetched `/vi/my/work/leave`:
  "Nghỉ phép năm · Còn 7.58 ngày · Đã tích lũy 5.42 ngày trong năm nay · Tiếp theo: 1.08 ngày
  vào 1 thg 12 2026" (checked from the HTML, W2A-8).
- Console: no errors on the screen or the employee page.
- **Faults found in the walk and fixed** (each now has a test where testable): (1) the table's
  rows were flex boxes — `pb_training` owns the `pbls-` CSS prefix and its global `.pbls-row`
  hit this table → prefix renamed `pblk-`; (2) saving the drawer turned "Every country" into
  the company's country (core recomputes the kind's country on any company write) → company
  written only when changed, "Every country" clears both country fields (S3); (3) "Add the
  finished months now" by a tenant HR manager failed on a take-ahead kind
  (`hr_holidays_attendance` checks the USER's Time Off group even under sudo) → the engine
  writes allocations as the system user (S8b); (4) primary buttons were unstyled (the kit's
  primary is `pbim-btn primary`); (5) wording: "12 a year", "1 days are added", "1 people",
  "Next: 1 on …", "Includes 2.16" (rounding) → fixed.
- Phone width: the shared Chrome window could not be narrowed without disturbing other
  builders' tabs (other builders work in the same window); the `max-width: 720px` rules
  (drawer full width, one-column grids) are present in the served stylesheet. Not visually
  checked at phone width — see Left for later.

**3d. Static gates:** `pyflakes` clean (bar module `__init__` imports); `lxml` parse of every
XML; JSON parse of the ready-made data; PO parse gate (`PoFileReader`) on `vi_VN.po` /
`id_ID.po` — every entry carries `#. module`, `#. odoo-python|odoo-javascript` and a `code:`
occurrence (exported by `odoo-bin i18n export`, then translated); no msgstr names the vendor
(S10). 17 technical model terms (Created by, ID, Posting Key …) left untranslated on purpose.

## 4. Rails

| Rail | How it is met |
|---|---|
| White-label | No vendor name on any screen, msgstr or data (S10). The ID source note says "Payobook adds the days…" — product name, allowed. |
| Lane | New module + `pb_timeoff/models/pb_timeoff.py` + manifest only. `pb_ess_workforce` extended by override/xpath; `pb_settings` / `pb_hub` by registry. |
| No payslip change | Nothing in the pay engine changed. Building-up kinds create ordinary allocations; pay reads leave requests as before. Kinds' pay fields are only what HR sets (core "Is unpaid" is set for NEW kinds only — the drawer never flips it on an existing kind). |
| Silent install | No kind created, nothing switched on, no field changes behaviour by default (`pb_ls_earning='none'`); cron quiet and `{}` on an empty database (E7b); no email (E7). |
| Defaults, no required | Every new `hr.leave.type` field has a default, none required (S5-B creates kinds blind). |
| Rights | Read/write gates server-side (S1); portal employee only reaches own data through the facade (P1–P4); tenant HR reach proven (S2). |
| Idempotence | Unique key per person × kind × month; same lock as Rize; allocation set from rows, never added to (E2). |
| Rize | Policy-bound kinds never earn; their pay/earning locked in the drawer ("set by your leave policy"); `pb_policy_code`/`category` never written. |

## 5. Contracts other phases rely on

- New `hr.leave.type` fields (defaults, none required): `pb_ls_earning` ('none' | 'yearly' | 'monthly'), `pb_ls_days_per_year`, `pb_ls_waiting_months`, `pb_ls_max_balance`, `pb_ls_take_ahead` (False), `pb_ls_expire_months`, `pb_ls_earn_from`, `pb_ls_step_ids` (`pb.leave.service.step`: `after_years`, `extra_days`), `pb_ls_hr_only`, `pb_ls_starter_key`, `pb_ls_starter_version`, `pb_ls_review`, `pb_ls_sources` (Json). **S5-B's in-lieu kind** (hours, `requires_allocation=True`) is never touched by the engine (hours kinds never earn) and shows in the list as "Given by HR".
- `hr.leave.allocation.pb_ls_year` — set only by the engine.
- `pb.ess.workforce.get_my_leave` — every existing key kept; balance rows may add `pb_earned`, `pb_earned_label`, `pb_next_label`, `pb_ahead_label`. `_my_appliable_types` additionally drops `pb_ls_hr_only` kinds. (C-4 respected.)
- `pb.timeoff._pb_balance_numbers(emp_ids, type_ids, today=None)` → `{(emp_id, type_id): {'allocated','taken','balance'}}`; `pb.timeoff._pb_expired_parts(...)` → `{(emp_id, type_id): (days_ran_out, taken_from_them)}`. B's expiring time off (if any) shows correctly through these.
- `pb.leave.earning._run_kind(kind, today, employees=None)` / `_cron_post()`.

## 6. Deploy notes

- Merge order A → B → C (step handover). Install `pb_leave_setup` with **`-i`** on all five databases (payobook, payobook_template, p0clone, rize, sudima; never abm); `-u pb_timeoff` (expect the usual cascade to its dependents; cron snapshot before/after).
- **Tier: risky** (new module install + new table + a stored-data-free change to balance reading). No data migration. No payslip effect. No rehearsal recompute needed for this phase on its own (the step's rehearsal is for S5-B).
- Asset purge + `web.assets.version` bump: new backend and frontend assets.
- New cron `cron_leave_earning` (daily, first run 2026-11-16 18:30 UTC). On every database it does nothing until HR sets a kind to build up.
- What customers will see after go-live: Settings › HR › "Kinds of leave". The set-up check will show many kinds "with no pay decision" on databases whose kinds were never classified (true; it is the study's "set-up health check"). Rize: its policy-bound kinds show "Set by your leave policy".
- Seam test for the deploy agent: S5-B's in-lieu kind created on a database with `pb_leave_setup` → appears in the list as "Given by HR", engine skips it (hours kind).

## 7. Owner questions (plain words)

1. **The "pay not decided" warning will be amber on most databases at first.** Every kind of leave that nobody has said "paid / unpaid / who pays" for is listed. On our test copy that was 73 kinds (many came with the system for other countries). Do you want us to (a) leave it as is so HR sees the truth, (b) hide kinds for countries the company does not operate in, or (c) do a one-off clean-up on each customer before go-live?
2. **India's ready-made figures are placeholders** (each state sets its own: earned leave 15, casual 7, sick 7). Should India be offered now with that warning (as built), or hidden until someone checks the main states?
3. **Leave year = calendar year** (January–December) for leave that builds up. Do any customers need a different leave year (for example April–March in India)?
4. **Singapore sick leave**: the law gives 5, 8, 11 then 14 days in months 3–6; the ready-made kind gives 14 days after 6 months and says "add the earlier days by hand". Good enough for a starting point?

## 8. Left for later

- "Next step-up on …" line on the employee record (FACTS item 2) — the employee record belongs to another screen; not built. The drawer's service table and the "Days added recently" list show steps.
- Undo of one month's posting (the audit rows are permanent; a correction is an ordinary allocation by HR).
- Source notes in Vietnamese/Indonesian for the other five countries' kinds (they show in English; VN notes are in Vietnamese, ID notes in Indonesian).
- Phone-width visual check of the screen (rules exist; the shared browser window could not be narrowed safely).
- "You will have N days on <date>" in the refusal message itself (the tile shows "Next: …"; core's own refusal text is unchanged).
- A leave year other than the calendar year (owner question 3).

## 9. Gotchas → ledger rows

| # | Gotcha |
|---|---|
| S5A-1 | CSS prefix clash: `pb_training` (Learning settings) owns `pbls-` and ships a GLOBAL `.pbls-row { display: flex }`; a table row with that class became a flex box and its cells no longer lined up with the header. Grep the whole repo for a prefix before using it (`grep -rl "pbxx-" --include='*.scss'`). |
| S5A-2 | Writing `company_id` on `hr.leave.type` (even the same value) recomputes the stored `country_id` from the company — "Every country" silently became the company's country, and the kind stopped being offered to people working elsewhere. On CREATE a `country_id: False` in the same values does not stop it either. Write `company_id` only when it changes, and write `country_id = False` in a separate write. |
| S5A-3 | `hr_holidays_attendance` (auto-installed) refuses `number_of_days` on an approved allocation unless `env.user` is a Time Off officer — **sudo does not bypass it**. A tenant HR manager pressing a button hit it; tests as the superuser did not. Write as `with_user(SUPERUSER_ID).sudo()` (with `allowed_company_ids` set). |
| S5A-4 | Core refuses `requires_allocation` in a write once the kind has leaves, **even when the value is unchanged** (`check_allocation_requirement_edit_validity`). Send it only when it changes. |
| S5A-5 | Local walks: several builders share ONE Chrome window and `127.0.0.1` cookies (W2A-6) — a session on `127.0.0.1:<port>` was signed out by another builder. Use a hostname of your own (`s5a.localhost:<port>`); do not resize the shared window. |
| S5A-6 | The kit's primary button is `pbim-btn primary`; a bare `pbim-btn` renders as a grey browser button (pb_loans' board has the same bare class). |
| S5A-7 | Odoo 19 CLI: `--i18n-export` is gone; use `odoo-bin i18n export -c <conf> -d <db> -o <file.pot> <module>` — its output already carries the three markers a PO entry needs. |
