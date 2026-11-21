# WDGAP S5-F — report (follow-ups to the Step 5 + back-pay go-live)

Builder (Opus), 2026-11-16/17. Branch `wdgap-s5f` from `origin/19.1` (merged again with
`origin/19.1` @ `c24630ccc` after the owner pause — documents only). Owner rulings LV1, LV2, TP3,
BP1, BP2 (`WDGAP_OWNER_RULINGS_2026-11-15.md`, "Rulings 2026-11-16") and the two leftovers of
`WDGAP_S5_DEPLOY_REPORT.md` §5. **Not merged, not deployed; no live server touched.**

## 1. What was built, per item

### Item 1 — LV1: Kinds of leave shows only the customer's countries (`pb_leave_setup`)
- **The customer's countries** (`pb.leave.setup._home_countries`): the country of every company in
  the database, **plus** the countries people are paid in (employee payroll country) and the
  countries of the leave policies (Rize) — see deviation D1. A kind is "home" when its country
  (policy country first, then the stock country — the same order the leave offer uses,
  `pb.timeoff._type_country`) is one of them, or when it is for every country.
- **List, steps, "of N", filter panel, glance and set-up check** count home kinds only
  (`_list_scope`, `_pbf_base_domain`, `get_board(other=False)`); **"Pay to decide"** (amber glance
  and the set-up check chips) leaves the hidden kinds out.
- **Quiet toggle** above the list: "Show kinds for other countries (N)" / "Hide kinds for other
  countries" (grey text button, Lucide globe). It flips `pbf_ctx.other` on the filter kit and
  reloads the panel and the numbers. A hidden kind still opens in the drawer. If every kind
  belongs to another country: "No kinds of leave for your countries yet" with the toggle and the
  ready-made button.
- **Ready-made dialog**: the customer's countries first; the rest behind an "Other countries"
  fold. The default country is the company's, else the first home country. Adding ready-made
  kinds, or saving a kind, for a country the list hides switches the toggle on, so the new kind
  is not lost from sight.
- **Hide only**: nothing is archived, deleted or written (test C5). If no company says where it
  is, nothing is hidden.
- Files: `pb_leave_setup/models/leave_setup.py` (gates section: `_home_countries`,
  `_home_domain`, `_list_scope`, `_is_home`, `_other_count`, `_show_other`; `_countries` adds
  `home`; `get_board(other)` adds `other`, `other_count`, `home_countries`; `_pbf_base_domain`),
  `static/src/js/leave_setup.js` (kit `ctx`, `kit.kw` on the page call, `setShowOther`,
  `starterHome` / `starterOthers`), `static/src/xml/leave_setup.xml` (toggle, empty state, dialog
  fold), `static/src/scss/leave_setup.scss` (`.pblk-others*`, amber banner).

### Item 2 — LV2: India warning (`pb_leave_setup`)
- Checked first: the sentence did not exist (India's sources only said "placeholder").
- Added "Figures differ by state — check yours before switching on" (en/vi/id) as an **amber
  banner on the India ready-made dialog** and in the **drawer of every ready-made India kind**
  (ready-made key `IN.*`). Other countries carry none. India kinds stay created switched off and
  waiting for review (as before). `leave_setup.py` `_starter_warning`, `get_kind['warning']`,
  `starter_list['warning']`; XML banners.

### Item 3 — TP3: employees see their own confirmed late minutes (`pb_time_pay`)
- New page **`/my/work/late`** ("Late and early minutes", My Work hero and nav, back link to My
  Overtime): one card per month (last 12 months, newest first), "N min counted" per month, rows
  date · Late arrival / Early leave · minutes · **Counted** / **Excused** (excused rows grey, never
  counted). Minutes nobody decided are never stored, so never shown; the manager's note is not
  shown. Empty state "No late or early minutes".
- **Door on My Overtime**: a quiet card "Late and early minutes · N minutes counted this month"
  shown **only to somebody who has decided minutes** — the page looks as before for everyone else.
- No `pb_me_portal` or `pb_ess_workforce` file edited: own controller
  (`pb_time_pay/controllers/portal.py`), facade method `pb.ess.workforce.get_my_late_minutes()`
  and a `late` key added to `get_my_overtime()` (C-4: every key kept) in
  `pb_time_pay/models/ess_workforce.py`, templates in `pb_time_pay/views/portal_templates.xml`
  (new `portal_my_work_late`; the door by xpath after `work_flash` in the existing inheriting
  template), frontend style `static/src/scss/time_pay_portal.scss` (prefix `pbmlm-`, checked free).
- Rights: the employee is resolved from the session (`_require_own_employee`), never from the
  request; the portal login still cannot read `pb.time.late` through the ORM.

### Item 4 — BP1: a leaver's back pay goes into their final payslip (`pb_retro`)
- `_pb_pay_check`: a person who has left (archived, or leaving date passed) is now **payable**
  (`why='final'`) when `_pb_final_payslip_to_come(emp)` holds, otherwise "not paid automatically /
  Has left" exactly as before. "Still to come" means either:
  a. an unfinished payslip of a REGULAR run of the same scheme and company, starting after the
     re-worked months, already exists; or
  b. the person record is still active, the leaving date is after the re-worked months, none of
     their own finished regular payslips of this scheme reaches the leaving date, and the
     scheme's regular payslip covering that date is not finished for anyone else (their final pay
     was not made somewhere else).
- The **taking side is unchanged**: the final payslip takes the entries with the same
  reservation, paid-once rule, whole months and never-below-zero (BP2). Extra / top-up runs never
  take them; nothing is written to past payslips or the formula engine; payslips with no entries
  go through untouched code (golden F08 + the existing B01).
- Approval re-checks: entries are made at approval from a fresh `_pb_pay_check` (unchanged
  code), so a final payslip finished in between turns the person back to "Has left" (F05).
- Words: approval detail cell "Final payslip"; payment strip "Will be paid in their final
  payslip"; when the final payslip does not take everything (a month that would push take-home
  below zero, or finished without it) "The final payslip does not take all of it — cancel the rest
  here and settle it by hand" (amber; the existing per-person cancel with a reason works); the pay
  run review note on a final payslip says the month "does not fit in this final payslip … settle
  it by hand" instead of "waits for the next pay run".
- Files: `pb_retro/models/retro_backpay.py` (`PERSON_WHY` + `final`; `_pb_pay_check`;
  `_pb_has_left`, `_pb_final_payslip_to_come`; `_pb_why_text`; `_approval_detail`;
  `hr.payslip._pb_backpay_regular`, `_pb_backpay_final`; `_pb_backpay_notes`),
  `pb_retro/models/retro_board.py` (`_where_words`).

### Item 5a — the ⌘K / search test the shift-pattern entry trips (`pb_hub` test only)
- `pb_hub/tests/test_palette_lens_gates.py` `_NARROWER` (lines 47–60): added `wf_patterns_make`
  with its reason (making draft shifts is the attendance MANAGER's; the Patterns tab is the
  officers'). That is the test's own reviewed list for "deliberately narrower" rows (ledger S8M-5).
  No behaviour changes. `pb_hub`'s version is NOT raised (deviation D3).

### Item 5b — "Odoo Report" browser-tab title (`biz_debrand`)
- Source: the platform's `web/views/report_templates.xml` lines 16 and 50 —
  `<title t-esc="title or 'Odoo Report'"/>` in `web.report_layout` and `web.report_preview_layout`.
  Every report preview (and the PDF made from the same page) gets it unless the report sets
  `title`.
- Fix by inheritance in `biz_debrand` (no vendored file edited, no product name):
  `views/report_title.xml` replaces both titles with `title or biz_report_title or
  _biz_default_title()`; `models/ir_actions_report.py` hands `biz_report_title` into every
  report's rendering values = the printed name of the one document when the report says how to
  name it (`print_report_name`, as the download's file name: "Payslip - Bùi Hữu Khang"), else the
  report's own name; never stops a print. Neutral fallback "Report" (vi "Báo cáo", id "Laporan").
  New `biz_debrand/i18n/` (one entry).

### Commits (branch `wdgap-s5f`)
| Commit | Item |
|---|---|
| `99848cceb` | 1 + 2 — Kinds of leave: customer's countries; India warning |
| `aff8fe0b3` | 3 — late and early minutes on My Payobook |
| `68c8f6ea9` | 3 — walk fix (month tables line up) |
| `5f102638e` | 4 — a leaver's back pay in the final payslip |
| `93ad7e5d4` | 5a — the ⌘K shortcut-list test |
| `16b3e3079` | 5b — report preview / PDF title |

## 2. Versions raised

| Module | Before | After |
|---|---|---|
| pb_leave_setup | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_time_pay | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_retro | 19.0.1.1.0 | 19.0.1.2.0 |
| biz_debrand | 19.0.2.10.0 | 19.0.2.11.0 |
| pb_hub | 19.0.1.13.2 | unchanged (test file only — D3) |

## 3. Tests

Local copy `wdgap_s5f_t` (= `upd_p6_t_tpl` + `-u all` + `-i` the Step 5 and back-pay modules),
own port 8841, jobs off.

### 3.1 New tests (all pass)

| # | Case | File |
|---|---|---|
| C1 | every company's country is a home country | `pb_leave_setup/tests/test_wdgap_s5f_countries.py` |
| C2 | list / "of N" / panel total hold home + every-country kinds; toggle count = the rest | 〃 |
| C3 | "Pay to decide" glance and chips leave out exactly the hidden kinds | 〃 |
| C4 | toggle shows all; a hidden kind opens in the drawer (`home` false) | 〃 |
| C5 | hide only: active, countries, write dates and count unchanged after every read | 〃 |
| C6 | policy country wins over the stock country | 〃 |
| C7 | no country anywhere → nothing hidden | 〃 |
| C8 | ready-made countries flagged home; default = a home country | 〃 |
| W1 | India dialog + every ready-made India kind carry the warning; made switched off, waiting for review; other countries and hand-made kinds carry none | 〃 |
| L1 | own decided rows only, by month, newest first; excused shown "Excused", never counted; another person's and >12 months never listed | `pb_time_pay/tests/test_wdgap_s5f_late_page.py` |
| L2 | My Overtime summary (count, this month's counted minutes); every old key kept; zero for a person with nothing decided | 〃 |
| L3 | **HTTP as real portal logins**: own page shows 23 min counted + Excused, not the other person's 88; the door on My Overtime; the other person sees only their 88; a login with no employee gets the plain page | 〃 |
| L4 | read-only (no write); the portal login still cannot read the decisions through the ORM | 〃 |
| L5 | no vendor name in the two templates | 〃 |
| F01 | leaver with a final payslip: payable "final", "Final payslip", "Will be paid in their final payslip"; lines and take-home as anyone's; paid; re-work closes | `pb_retro/tests/test_wdgap_s5f_leaver_backpay.py` |
| F02 | negative difference that fits | 〃 |
| F03 | negative difference that does not fit: Aug+Sep taken, Oct waits; review note and strip say settle by hand; cancel the rest with a reason → paid | 〃 |
| F04 | none to come → "Has left": left inside the months, own final finished, archived with nothing made, scheme's run of the last month finished without them; archived WITH an unfinished regular payslip → final | 〃 |
| F05 | the check is live (finished final payslip → "Has left") | 〃 |
| F06 | matrix for the leaver: compute, recompute identical, second payslip nothing, done → paid, back → held, recompute, cancel → open (still to come), taken again, delete → open, run delete → open | 〃 |
| F07 | Extra and top-up never take it | 〃 |
| F08 | golden: leaver without back pay byte-identical with the seam off; nothing written | 〃 |
| F09 | people who have not left untouched; a leaving date still ahead is not "has left" | 〃 |
| T1 | report preview over HTTP: page title = the report's name, no vendor name | `biz_debrand/tests/test_report_title.py` |
| T2 | rendered page (the PDF source) has the same title | 〃 |
| T3 | one document → printed name; several → report name; an unworkable name never stops a print | 〃 |
| T4 | nothing to name it → "Report" (vi/id translated); a report's own `title` kept; both layouts | 〃 |
| 5a | `pb_hub` `TestPaletteRowsFollowTheirTabs.test_every_tab_row_carries_its_tabs_gate` passes | existing |

### 3.2 Suites of every touched module vs the baseline

Baseline recorded BEFORE any edit: `pb_leave_setup`, `pb_time_pay`, `pb_retro` on pristine copies
(run `base1`); `pb_hub` and `biz_debrand` on a full pristine `origin/19.1` tree (run `base2` — their
tests read neighbouring module folders, so copies outside the repo give false failures; ledger
S5F-1).

| Run | Test methods (per module) | Failed / errors |
|---|---|---|
| Baseline `base1` (pristine pb_leave_setup, pb_time_pay, pb_retro) | 37 / 51 / 52 | **0** |
| Baseline `base2` (full pristine tree; pb_hub, biz_debrand) | 38 / 64 | **5**: pb_hub `TestPaletteRowsFollowTheirTabs.test_every_tab_row_carries_its_tabs_gate` (item 5a, S8M-5), pb_hub `TestHubKitStaticGates.test_the_kit_stacks_nothing_above_twenty` (S8 deploy: pre-existing), biz_debrand `TestFieldTermSeam.test_05_a_bot_shaped_field_label_is_rebranded`, `TestNoUnreachableProductName.test_01_no_product_name_where_no_seam_can_reach_it`, `TestProductRuleIsOptIn.test_09_the_scrub_never_asks_for_the_product_rule` (pre-existing, unchanged code) |
| After (`after2`, branch, `-u` all five, `--test-tags` all five) | pb_leave_setup 46 (+9), pb_time_pay 56 (+5), pb_retro 61 (+9), pb_hub 38, biz_debrand 68 (+4) = **269** | **4** = the baseline set minus the palette test this phase fixes. Every new test passes. |

(`after1` had one more error, my own T1 signing in as `admin`, which is archived on this template;
the test now makes its own login — ledger S5F-4.)

### 3.3 Static gates
`py_compile` on every changed Python file, `lxml` parse of every changed XML, `node --check` on the
changed JS: clean. PO gate (`PoFileReader`) on the 8 changed/new `.po`: all parse; every new entry
was taken from `odoo-bin i18n export` (module, `odoo-python`/`odoo-javascript`, occurrence) and
appended or merged TEXT-LEVEL (old entries byte-identical; "Excused", "Late arrival", "Early leave",
"Minutes" got their new code occurrence added). Vendor word in added user-visible lines / msgstr:
none (only an engineering XML comment).

### 3.4 Browser walk
Claude in Chrome, my own tab on `s5f.localhost:8841` (own cookie jar), jobs off; the copy's company
set to Vietnam; local logins only (admin re-activated on the copy, `demo.s5f.emp` = a portal
employee "DEMO S5F Walker" with decided minutes; "DEMO S5F Somebody else" has 77 minutes).
1. **Kinds of leave** (admin): 6 kinds listed (every-country kinds; the template has no Vietnamese
   kind), set-up check "6 kinds … no pay decision", glance "6 with pay to decide", quiet link
   "Show kinds for other countries (67)". Pressed: everything moves together to 73 (list "73 of 73",
   tabs, steps, amber 73, chips of other countries); "Hide kinds for other countries" → back to 6.
2. **Ready-made kinds**: country row shows Vietnam only; "Other countries" fold opens Indonesia,
   India, Singapore, Thailand, Cambodia, Malaysia. India → amber banner "Figures differ by state —
   check yours before switching on". "Add 5 kinds, switched off" → toast, the toggle switched on by
   itself, list on "Waiting for review" with the five IN kinds. Earned leave drawer: the same amber
   banner at the top, above "A starting point — please review…".
3. **My Overtime** (portal employee): door card "Late and early minutes · 43 minutes counted this
   month" (25 + 18; the excused 12 not counted). **/my/work/late**: "November 2026 · 43 min counted"
   (Sun 8 Nov late 18 Counted, Wed 4 Nov early 12 Excused in grey, Tue 3 Nov late 25 Counted),
   "October 2026 · 40 min counted"; the other person's 77 not on the page. `/vi/` and `/id/` pages
   translated ("43 phút được tính", "43 menit dihitung"). Walk fix: the two month tables did not
   line up → fixed widths (commit `68c8f6ea9`).
4. **Report previews** (admin): browser tab "Payslip - DEMO S5F Walker" (payslip),
   "Payslip Details - DEMO S5F Walker", the themed payslip "In phiếu lương (theo chủ đề)" (its
   report name, in the reader's language), "Model Overview" → no vendor name anywhere.
5. Console: no errors on the Kinds of leave screen, My Overtime or the late-minutes page.
Not checked: a real phone width (the shared Chrome window is not resized; the page's tables sit
in the existing scrolling wrapper and the door card is one flexible row).

## 4. Rails

| Rail | How it is met |
|---|---|
| White-label | No vendor name in any new string, msgstr or template (S10 / T32 / L5 / static gate); item 5b removes the last one from report previews and PDF titles. No product name in `biz_debrand`. |
| Lane | Edited only `pb_leave_setup`, `pb_time_pay`, `pb_retro`, `biz_debrand` and one test file of `pb_hub`. `pb_me_portal`, `pb_ess_workforce`, `pb_lifecycle`, `pb_explorer`, `pb_pack_*`, the formula engine and vendored standard addons untouched. |
| Golden | Payslips with no back pay: untouched code (F08, B01). Nothing in the formula engine. |
| Silent on upgrade | Kinds of leave: fewer kinds listed (the ruling). My Overtime: the door shows only to people with decided minutes. Back pay: no data changes (0 entries live). Report previews: the tab says the report's name. Nothing sent, no job, no data migration. |
| Portal | own-employee facade + HTTP tests with real portal logins (L3) |

## 5. Deviations

- **D1 (LV1)** — "the customer's countries" also include the countries people are paid in and
  leave-policy countries, not only company countries, so a kind somebody actually works under is
  never hidden (e.g. a company paying people in a second country).
- **D2** — items 1 and 2 are one commit (both in `pb_leave_setup`, same files).
- **D3 (5a)** — `pb_hub`'s version is not raised: only a test file changed; no `-u pb_hub` is
  needed (and `-u pb_hub` would cascade through every hub). The deploy copies the file with the
  tree; the hash check still covers it.
- **D4 (5b)** — the fix also changes the PDF's document title (same page): the report's name
  instead of the platform's. Payslip figures and layout unchanged.
- **D5 (BP1)** — "a payslip still to come" is decided as in §1 item 4 (rules a/b); an archived
  person counts only when an unfinished regular payslip already exists.

## 6. Deploy notes

- Modules: `-u pb_leave_setup,pb_time_pay,pb_retro,biz_debrand` on all five (payobook,
  payobook_template, p0clone, rize, sudima; never abm). `pb_hub`: copy the tree only (test file).
- **Tier: risky** (pay: who gets back pay in a payslip; `biz_debrand` is a base module with many
  dependents — cron snapshot before/after). Rehearsal: recompute a real regular run old vs new = 0
  differences (no back-pay entries exist live); `-u biz_debrand` cascade timing.
- Assets: backend (Kinds of leave) and frontend (late-minutes page) changed → purge
  `/web/assets/%`, bump `web.assets.version`, restart.
- No data migration. New selection value `final` on `pb.retro.person.why`. New route
  `/my/work/late`.
- What customers see: Kinds of leave lists fewer kinds (only their countries) with the quiet
  toggle and a lower amber count; employees with confirmed minutes see the door on My Overtime;
  report previews' browser tab shows the report's name.

## 7. Questions for the owner (plain words)

1. **Late minutes page**: employees see each confirmed late arrival or early leave with its date
   and minutes, and excused ones marked "Excused". The manager's note on an excuse is NOT shown.
   Should employees see that note too?
2. **Leavers' back pay that does not fit**: if a leaver owes money and their final payslip cannot
   take a whole month without going below zero, that month is not taken; the screen says to cancel
   it and settle it by hand. Is that right, or should the final payslip take part of the month?

## 8. Left for later
- Phone-width check of the new page beyond the walk above.
- The themed payslip print has no "printed name" set, so its preview tab reads "Print Payslip
  (Themed)" (its report name) rather than "Payslip - <person>". One field on that report action
  (`pb_hr_payroll_formula`, out of lane) would make it match the other payslip prints.
- A run-level count "Includes back pay for N leavers" on the pay run screens (out of lane, as in
  W2-D2 §8).

## 9. Gotchas → ledger rows
| # | Gotcha |
|---|---|
| S5F-1 | A baseline made from module copies OUTSIDE the repo (`git archive … <modules>` first on the addons path) gives false failures for `pb_hub` and `biz_debrand`: their tests read neighbouring module folders through their own path. Baseline those two on a full `git archive origin/19.1` tree. |
| S5F-2 | A text node inside `<head><title>` of an inherited report layout is NOT exported as a translatable term; a translated fallback has to come from Python (`_()`) and be called from the template. |
| S5F-3 | `polib` save rewraps every entry of a `.po`; merge new entries text-level so the rest of the file stays byte-identical. |
| S5F-4 | The local template `upd_p6_t_tpl` has company 1 in the United States and `admin` archived: country-dependent screens need the company country set on the walk copy, and HTTP tests must make their own login. A plain (non-dev) local server does not rebuild assets after an SCSS edit: purge `/web/assets/%` and restart. |
