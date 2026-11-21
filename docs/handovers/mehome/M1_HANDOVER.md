# MEHOME M1 — the page's bones: facts, tiles, hero, sections, Needs you, Me strip (handover for Opus)

Read first: `MEHOME_PROGRAM.md` (what the page becomes + every verified reference), `MEHOME_LEDGER.md` (rules
M-R1…R9, the tile table, rows M1–M11), the build target `docs/design/my-payobook-home-poc.html` → tab **Bento**
(open it in a browser; also press **Phone**), and the module you are extending: `pb_me_portal/views/
portal_templates.xml`, `controllers/portal.py`, `static/src/scss/me_portal.scss`, `__manifest__.py`. Repo
`CLAUDE.md` rules apply (one addons dir; never the vendor's name in a user-visible string). You do not deploy.

## Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." For M1 the page must already feel like
the mock-up with the three money/time cards missing: a personal greeting and one true sentence, a "Needs you"
card that names each thing and its door, the Me strip, and every tile below carrying a coloured Lucide badge in
a named section. Zero dead-ends: every empty state names what will appear. Score the report against this bar.

## Scope (M1)
1. **Facade** `pb_me_portal/models/pb_me_home.py`, AbstractModel `pb.me.home`, one entry point
   `get_home_data(emp)` → dict or `None` (no employee). One `optional(model_name, fn, *, fields=())` helper
   (M-R3): returns `None` when the model is absent, when a listed field is absent from `_fields`, on
   AccessError (debug log) or any other exception (warning + trace). Every section below is built through it and
   is `None` when its source is absent. Log `timing_ms` per section at debug. Payload keys (facts only, M-R5):
   - `person`: `{short_name, daypart, job, company, avatar_url, date}`. `short_name` = last word of the employee
     name when the user's lang is `vi_VN` or the employee's company country is VN, else the first word (one
     helper, tested). `daypart` ∈ `morning|afternoon|evening` from `now` in the user's tz (`user.tz` →
     company partner tz → UTC), cut-offs 12 and 18. `date` = today's date (template formats it).
   - `pay`: from own `hr.payslip` in state `done`, order `date_to desc`, limit 6 (never `cancel`):
     `{last: {period_date (date_to), net, currency_id, pdf_url, view_url, paid_on (date or None — only when
     'pb_paid_on' in Slip._fields)}, previous_net, trend: [{month_date, net}] oldest→newest (≤ 6, the last one
     is `last`), next_pay_date (date or None, M9: first `pb.payroll.calendar` row with state 'upcoming' and
     pay_date ≥ today for the employee's company, else a shared row with company_id empty, else None),
     explain_url ('/my/pay' when 'pb.pay.apply' in env else None), count}`; `{count: 0}` when no done slip.
     Net = `self._ess_net`-equivalent through `slip.line_ids.pb_net_line()` (one-pay-band rule; never a
     category sum). A slip whose net is None is skipped in `trend`.
   - `leave` (M3): through `pb.ess.workforce.get_my_leave()` (sudo, as its own route does): `{left, allocated,
     booked_pending (its `pending`), low (any row low), url: '/my/work/leave'}` summed over the returned rows;
     `{left: 0, allocated: 0, ...}` when the call returns no rows. `None` when the model is absent.
   - `week`: through `get_my_schedule(<this Monday>)` → the FIRST week only: `{days: [{date, is_today,
     label (its own day label), shift (its hours text or None), state ('acked'|'pending'|'off'|'leave')}×7],
     pending, hours_label, scheduled_h (parse from hours_label if numeric else None), url:
     '/my/work/schedule'}`. Read the real `days[]` shape before mapping (`ess_workforce.py:108-217`); keep what
     it gives, do not re-query `hr.shift.planning`. `None` when absent.
   - `needs_you`: ordered list (M-R6 order), each `{key, n, days?, url}`; items with `n == 0` are not emitted:
     `shifts_to_confirm` (`get_my_counters()['shift_pending']`, url `/my/work/schedule`), `doc_expired`
     (own `pb.employee.document`, active, `expiry_date < today`), `doc_expiring` (`today ≤ expiry_date ≤ today+90`,
     `days` = days to the soonest; M4), `timesheet_missing` (count of `missing` flags in `get_my_week(<this
     Monday>)['days']`, url `/my/work/timesheet`), `overtime_pending` (`get_my_counters()['overtime_pending']`),
     `training_overdue` / `training_due_soon` (`pb.my.training.home()` `overdue` / `due_soon`, url
     `/my/training`), `goals_to_set` (`pb.my.goals.home_count()`, url `/my/goals`), `profile_waiting` (own
     `pb.profile.change.request` in `hr_review`, url `/my/profile`), `profile_approved` (state `approved`,
     `write_date` within 7 days). Bound every search (`limit`/`search_count`).
   - `tiles`: the registry (item 2) as a list for tests.
2. **Tile registry** in the same model: `TILES = {url: {group, icon, tone, title?, text?, hidden?}}` for every
   URL in the ledger tile table + the stock ones. Groups and order: `me` (Profile, Documents, Tax Sheet, My
   Things, My Pay Package) → `time` (My Schedule, My Timesheet, My Overtime, Public holidays) → `growth` (My
   goals, My Growth Plan, My training, My training allowance, Recognition) → `people` (Who's Who, My Buddy, My
   Journey, Refer someone, My hiring, My team's training) → `more` (Sign-in & security = title override of
   "Connection & Security", Addresses, My Resignation, and every unknown URL incl. stock finance tiles).
   `hidden`: `/my/payslips` (M6), `/my/pay`, `/my/work/leave` (their doors are the cards; the Leave card ships
   in M2 but the tile is hidden from M1 — say so in the report). Icons/tones exactly as the mock-up's Bento tab
   (Profile user/indigo, Documents file/amber, Tax Sheet calculator/slate, My Things laptop/blue, My Pay Package
   gift/pink, My Schedule calendar/indigo, My Timesheet clock/blue, My Overtime timer/amber, Public holidays
   sun/teal, My goals target/indigo, My Growth Plan trending-up/green, My training graduation-cap/blue, My
   training allowance wallet/teal, Recognition award/pink, Who's Who users/indigo, My Buddy user-check/green, My
   Journey route/blue, Refer someone user-plus/teal, My hiring briefcase/amber, My team's training
   graduation-cap/pink, Sign-in & security shield/slate, Addresses map-pin/slate, My Resignation log-out/slate,
   unknown file/slate). `tile_meta(url)` returns the entry or the `more` default (match on the path before `?`).
3. **Tile override**: inherit `portal.portal_docs_entry` (priority 20). Before the outer div: `t-set pbme_tile`
   = `tile_meta(url)`; `title`/`text` replaced when the registry overrides them; `config_card` forced true when
   the registry says `always` (none yet). On the outer `div.o_portal_index_card`: `t-att-data-pbme-group`,
   `t-att-data-pbme-hidden`. Replace `div.o_portal_icon` with `<div class="pbme-badge pbme-badge--{tone}">`
   holding `ess_icon` (M-R8; extend `ess_icon` with every Lucide name above — paths from the mock-up's sprite —
   keeping W23). Hidden tiles get `pbme-hidden` (CSS `display:none`) — never removed, the counters script still
   finds them.
4. **Page**: inherit `portal.portal_my_home`: `t-set my_details` → `not pbme_home` (M10); replace the current
   hero block with the new top line (eyebrow with the brand read as `ess_hero` does + the date; h1 greeting;
   the sentence; the who pill) — only when `pbme_home`, else nothing of ours renders and the stock page is
   untouched (test 10). After `.o_portal_docs` (position `after`): the bento shell `div.pbme-bento` with, in
   M1, the **Needs you** card (`data-pbme-slot="needs"`) and the **Me strip** (`data-pbme-section="me"`,
   empty container the Interaction fills) and reserved empty slots `data-pbme-slot="pay|leave|week"` (M2 fills
   them; in M1 they do not render — no empty boxes). Then the sections `time`, `growth`, `people`, `more`: each
   `section.pbme-sec` with an `h3` and an empty `div.pbme-sec-body[data-pbme-section]`. Class `pbme-home` on
   `.o_portal_my_home` (keep `pbme-employee` as today). Breadcrumb bar and "My account" h3 are not shown for an
   employee (preferred: the `my_details` override + `t-if` on the breadcrumb `ol` in our existing
   `portal_my_home_menu_ess` inherit; if the layout still shows a bar, hide it by CSS scoped to the page and say
   so).
   **The sentence** (M-R5, words in QWeb): pieces joined with " · "-free prose: pay piece "Your next pay lands
   in %(n)s days" (n ≥ 2) / "tomorrow" / "today" when `next_pay_date`; needs piece: 1 item → its own sentence
   ("%(n)s shifts are waiting for your OK", "Your work permit… " NO — documents are unnamed: "A document needs
   renewing", "%(n)s documents need renewing", "%(n)s days are missing on your timesheet", …), ≥ 2 items →
   "%(n)s things need you"; nothing → "Nothing needs you right now." With neither pay date nor items: "Your
   payslips, time off and documents, all in one place." Screen-reader: a visually hidden " · " between pieces.
5. **Needs you card**: rows in M-R6 order, each `badge(icon, tone)` · `b` what · grey detail · chevron, the whole
   row a link to `url`. Words table in the template: shifts "Confirm %(n)s shifts" / "for this week and next";
   doc_expired "%(n)s document(s) expired" / "Upload the renewal for HR"; doc_expiring "A document expires in
   %(d)s days" / "Upload the renewal so HR can verify it"; timesheet "%(n)s day(s) missing on your timesheet" /
   "Fill in the hours"; overtime "%(n)s overtime request(s) waiting" / "With your manager"; training_overdue
   "%(n)s course(s) past their date" / "Finish them to stay compliant"; training_due_soon "%(n)s course(s) due
   within a week"; goals_to_set "Your goals are waiting to be set" / "Agree them with your manager";
   profile_waiting "Profile change with HR" / "They will confirm it shortly"; profile_approved "Profile change
   approved" / "HR updated your details". Tones per M-R6 (amber waiting, rose expired/late, green approved,
   indigo/blue otherwise). Empty: the grey line "Nothing needs you right now" inside the card, no rows.
6. **Interaction** `pb_me_portal/static/src/interactions/me_home.js` (Odoo 19 `Interaction`, registry
   `public.interactions`, selector `.pbme-home`; clone the shape of
   `portal/static/src/interactions/portal_home_counters.js`): on start, for every `.o_portal_index_card` in
   `.o_portal_docs`, read `data-pbme-group` and append the node to `[data-pbme-section=<group>]` (unknown →
   `more`); then add `is-empty` to every `.pbme-sec` whose body has no child and to the Me strip when empty;
   finally add `pbme-ready` to the page. Never touch `data-placeholder_count`, never clone nodes (the counters
   script holds references). CSS: tiles carry `order` by group so the no-JS fallback is sorted; sections with
   `is-empty` and the spinner are `display:none`; `.pbme-sec` is hidden until `pbme-ready` (the tiles are visible
   in `.o_portal_docs` meanwhile, so no blank page if JS fails).
7. **Look** (`me_portal.scss`, scoped `.pbme-home`): tokens from `--pbim-*`; hero per the mock-up (38 px h1,
   indigo `em` on the name, 15 px sentence, who pill); Needs you card; Me strip rows; section rows
   (`auto-fill minmax(230px,1fr)`, 34 px badges, hover = white + shadow); tile badge tones indigo/green/blue/
   amber/rose/teal/pink/slate from the kit tokens (add `--pbim-teal(-soft)`/`--pbim-pink(-soft)` to
   `pb_import_kit/static/src/scss/import_tokens.scss` + the `pbim-root-vars` mixin if missing; bump the kit).
   Container queries are fine (`.pbme-home { container-type: inline-size }`) with a `@media (max-width: 700px)`
   twin for the page. `prefers-reduced-motion` kills transitions. No Sass `min()/max()` with mixed units.
8. **Controller**: `_prepare_portal_layout_values` sets `pbme_home` = `get_home_data(emp)` only when
   `request.httprequest.path == '/my'` (M1), else `None`; never raises (log + `None` → stock page). Keep
   `pbme_employee_only` and the existing finance-tile CSS rule (now `.pbme-home.pbme-employee`).
9. **Vietnamese**: every new template string in `pb_me_portal/i18n/vi_VN.po` (export the `.pot` on the clone:
   `odoo-bin --addons-path=<stage>,… i18n export -c <conf> -d p0clone -l pot -o <file> pb_me_portal`, header
   "Payobook"; H37); every entry with the three markers (memory rule); `polib` parse gate.
10. **Learn**: nothing points at `/my` (program doc) — confirm by grep and say so in the report.

## Binding non-goals
No edit to any other module except the kit tokens (M-R2). No new dependency (M-R3). No Pay / Leave / This week
cards (M2). No OWL, no Chart.js, no CDN, no fonts beyond what the frontend bundle already loads (say in the report
which font the portal actually renders in — Inter is referenced by `.pbme`; if it is not loaded on the portal,
list the cost of shipping the kit's WOFF2 to `web.assets_frontend` for M2's decision). No deploy (Fable). No
"Odoo" anywhere user-visible. No change to the non-employee page.

## Numbered tests (`pb_me_portal/tests/test_me_home.py` + `test_me_home_source.py`; everything existing stays green)
1. Registry covers every URL the repo's tiles declare: a source test walks `*/views/*portal*.xml` under the repo
   root for `t-set="url" t-value="'/my/…'"` and asserts each path is a `TILES` key (list the stock three too).
2. `tile_meta('/my/unknown?x=1')` → group `more`, icon `file`, tone `slate`; `tile_meta('/my/payslips')` hidden.
3. Rendering `portal.portal_docs_entry` for `/my/documents` yields one `svg.pbme-ic` inside `.pbme-badge--amber`,
   `data-pbme-group="me"`, no `<img>`; for `/my/security` the title reads "Sign-in & security".
4. `get_home_data` with no linked employee → `None`; `/my` for such a user (HttpCase `url_open`) has no
   `pbme-home` class and still has `o_portal_my_home` and the side column.
5. `optional()`: absent model → `None`; a callback raising AccessError → `None` + one debug log (patch the
   module logger with `wraps=`, H17); other exception → `None` + warning.
6. Pay: two done slips + one cancelled (seed NET lines so `pb_net_line()` answers — reuse the fixture shape of
   `pb_me_portal/tests/test_pb_me_portal.py`) → `last.net` = newest done, `previous_net` = the older, `trend`
   has 2 entries oldest→newest, cancelled excluded, `pdf_url` ends with `report_type=pdf`.
7. Next pay: when `'pb.payroll.calendar' in env` (skip otherwise, say so): an upcoming row for the company dated
   tomorrow → `next_pay_date` = tomorrow; a closed row only → `None`; company row beats the shared row.
8. Needs you: an expired document + one expiring in 10 days + a `hr_review` profile request → keys in M-R6 order
   `doc_expired, doc_expiring(days=10), profile_waiting`; a document expiring in 120 days is not listed.
9. `short_name`: "Nguyễn Văn An" under `vi_VN` → "An"; "Mitchell Admin" under `en_US` → "Mitchell".
   `daypart` at 11:59 / 12:00 / 18:00 in the user's tz (freeze `now`).
10. Employee user: `/my` contains `pbme-home`, the greeting, the Needs you card, `data-pbme-section` containers
    for me/time/growth/people/more, no "My account" h3, no `col-lg-4` side column; `pbme-employee` still hides
    `/my/invoices` tiles by the existing CSS rule (source test on the SCSS).
11. Source: no vendor name, no emoji, no Font Awesome class, no `#4F46E5`, no `linear-gradient` in the new
    template/SCSS/JS; every icon name used in templates exists as an `ess_icon` branch; the JS never calls
    `cloneNode` and never writes `placeholder_count`.
12. `vi_VN.po` parses with `polib`, no empty `msgstr`, every new `msgid` present in the fresh `.pot`.
13. Browser walk on the clone (seed one internal user + employee with 2 done slips, 1 expiring document, 1
    profile request in `hr_review`; switch the login on for the walk and OFF after, H44): desktop 1440 and 412 px
    — greeting, sentence, Needs you rows link to their doors, Me strip holds the five tiles, sections are
    grouped with badges, Payslips tile absent, console clean (`list_console_messages` errors). Screenshots in
    `docs/handovers/mehome/m1_shots/`.

## Deliverables / report
`docs/handovers/mehome/M1_REPORT.md`: what shipped (files, payload shape as built, the words table), the test
table (number → result), the walk (what you saw, with the shots), the font answer, ledger rows M12… for every
gotcha, open questions. Versions: `pb_me_portal 19.0.2.0.0`, kit bump if touched. Commits on branch `19.1`
(feature-scoped, explicit paths, no `git add .`, message problem → fix → decisions, Co-Authored-By line from the
session reminder): `feat(mehome): M1 …`. Do not push, do not deploy.

## How to run (bench = server clone, no local Odoo)
ssh alias `Payobook19v2`. Fresh stage every run (H35): `ssh Payobook19v2 'sudo rm -rf /tmp/m1stage && mkdir -p
/tmp/m1stage'`, `rsync -az --exclude=__pycache__ --exclude='*.pyc' pb_me_portal pb_import_kit
Payobook19v2:/tmp/m1stage/`. Detached test run on `p0clone` with the stage path FIRST in `--addons-path`
(`/tmp/m1stage,/odoo/odoo-server/addons`), `-u pb_import_kit,pb_me_portal --test-tags /pb_me_portal
--stop-after-init`, sentinel file, read the `odoo.tests.result: … 0 failed, 0 error(s)` line (H30). For the walk,
a memory-capped unit on port 8099 + ssh tunnel (H42 recipe). The live databases are never touched.
