# MEHOME M1 — report (Opus build, 2026-10-14)

Handover: `M1_HANDOVER.md`. Ledger rows added: M12–M19. Nothing deployed, nothing pushed. Bench: `p0clone`
only (fresh stage `/tmp/m1stage`, `-u pb_import_kit,pb_me_portal --test-tags /pb_me_portal`).

## What shipped

| File | What |
|---|---|
| `pb_me_portal/models/pb_me_home.py` (new) | AbstractModel `pb.me.home`: `get_home_data(emp, now=None)`, `optional(model_name, fn, *, fields=())`, `tile_meta(url)`, `TILES` registry (+ `_TILE_WORDS` lazy words), `NEEDS_ORDER`. |
| `pb_me_portal/controllers/portal.py` | `_prepare_portal_layout_values` sets `pbme_home` on `/my` and `/my/home` only; never raises. |
| `pb_me_portal/views/portal_templates.xml` | `portal_my_home_ess` rewritten (my_details / no_breadcrumbs / classes / top / bento); new `portal_docs_entry_pbme`, `pbme_top`, `pbme_need_sentence`, `pbme_bento`, `pbme_need_row`; `ess_icon` + 23 Lucide branches. |
| `pb_me_portal/static/src/interactions/me_home.js` (new) | `public.interactions` `pb_me_portal.me_home`, selector `.pbme-home`: moves (never copies) each tile into its section in registry order, marks empty sections, adds `pbme-ready`; `destroy()` puts tiles back. |
| `pb_me_portal/static/src/scss/me_portal.scss` | MEHOME block scoped `.pbme-home` (tinted canvas, hero, badges, bento, Needs you, Me strip, sections, 900/700 px container + media twins, reduced motion); finance-tile rule now `.pbme-home.pbme-employee`. |
| `pb_import_kit/static/src/scss/import_tokens.scss` | `$pbim-teal(-soft)`, `$pbim-pink(-soft)` + the four `--pbim-*` vars in `pbim-root-vars`. |
| `pb_me_portal/i18n/vi_VN.po` | 95 new entries (template terms + `#. odoo-python`/`#: code:` lines for the lazy words), appended — no existing entry touched. |
| tests | `test_me_home.py`, `test_me_home_source.py` (new); `test_portal_icons.py` allows the one registry-driven icon call site. |
| manifests | `pb_me_portal` **19.0.2.0.0** (+ the Interaction in `web.assets_frontend`); `pb_import_kit` **19.0.1.22.0**. No new dependency. |

### Payload as built (facts only)
```
person    {name, short_name, daypart, job, company, avatar_url (hr.employee.public avatar_128), date}
pay       {count, next_pay_date, next_pay_days, explain_url, list_url,
           last {id, period_date, net, currency_id, currency, pdf_url, view_url, paid_on},
           previous_net, trend [{month_date, net}] oldest→newest}      (count 0 → only the first five keys)
leave     {left, allocated, booked_pending, low, types, url}
week      {days [{date, is_today, label, day_num, shift, shifts, state}]×7, pending, hours_label, scheduled_h, url}
needs_you [{key, n, url, days?}] in M-R6 order, zeros dropped
docs      {expired, expiring, soonest_days}   (feeds the Documents tile line "1 expiring soon")
tiles     [registry rows + url]
```
Every section goes through `optional()` (savepoint per call; AccessError → debug, anything else → warning).
`get_home_data` refuses an employee that is not the caller's own.

### Words (template, all in vi_VN.po)
Greeting "Morning, / Afternoon, / Evening, <name>." · sentence: "Your next pay lands in N days." / "…tomorrow." /
"…today." + one needs sentence ("1 shift is waiting for your OK.", "N shifts are waiting…", "A document has
expired.", "A document needs renewing.", "N days are missing on your timesheet.", "Your overtime request is
waiting with your manager.", "A course is past its date.", "A course is due within a week.", "Your goals are
waiting to be set.", "Your profile change is with HR.", "HR approved your profile change.") or "N things need
you." / "Nothing needs you right now." / "Your payslips, time off and documents, all in one place."
Needs rows: the handover's table, with real singular/plural branches instead of "(s)", and "A document expires
today / tomorrow / in N days". Empty card: "Nothing needs you right now" with a quiet tick.
The Leave tile is hidden from M1 on (its door becomes the Leave card in M2), as are Payslips and "Your pay,
explained" (their door is the Pay card).

## Tests (p0clone, final run)

| # | Test | Result |
|---|---|---|
| 1 | registry covers every tile URL found under every addons path (`*/views/*portal*.xml`, pb_/om_/biz_) + 6 stock URLs | pass |
| 2 | `tile_meta('/my/unknown?x=1')` → more/file/slate; payslips, pay, leave hidden; Me order | pass |
| 3 | rendered tile: one `svg.pbme-ic` in `.pbme-badge--amber`, `data-pbme-group="me"`, no `<img>`; "Sign-in & security"; stock render untouched off the home | pass |
| 4 | no employee → `None` (also: someone else's employee → `None`); HTTP `/my` for such a user: no `pbme-home`, has `o_portal_my_home`, contact column, "My account" | pass |
| 5 | `optional()`: absent model / absent field → None; AccessError → None + 1 debug; other → None + 1 warning; failed SQL does not poison the transaction | pass |
| 6 | pay: 2 done + 1 cancelled → last = newest, previous = older, trend 2 oldest→newest, cancelled out, PDF url | pass |
| 7 | next pay: closed only → None; shared row when no company row; company row beats an earlier shared row (own company, so clone rows cannot answer) | pass |
| 8 | needs: expired + 10-day + hr_review → `doc_expired, doc_expiring(days=10), profile_waiting`; 120 days not listed; order is M-R6 | pass |
| 9 | short name (vi → "An", en → "Mitchell"); daypart 11:59 / 12:00 / 18:00 on a frozen clock; tz fallback user → company → UTC | pass |
| 10 | employee HTTP `/my`: `pbme-home`, greeting, Needs card, 5 section containers, no "My account", no contact column, every tile badged; SCSS finance rule kept | pass |
| 11 | sources: no vendor name / emoji / Font Awesome / `#4F46E5` / gradient; every icon name drawn; JS has no `cloneNode`, never writes counters; no new dependency | pass |
| 12 | vi_VN.po parses (polib), no empty msgstr, code entries carry `odoo-python`, every new term present (checked against the fresh `.pot` export AND in-test term extraction) | pass |
| 13 | browser walk | pass — see below |
| — | existing pb_me_portal tests | all pass except `TestPbMePortal.test_01_profile_change_flow_and_audit`, which errors identically with the LIVE (unmodified) module code on the clone — approval engine AccessError, pre-existing (M19) |

Final log line: see "Final run" at the end of this file.

## Walk (test 13) — p0clone, temporary server on 8099 (memory-capped, ssh tunnel)
Seeded "Linh Tran" (internal user, employee, Operations Lead): 2 done payslips, 1 work permit expiring in 24
days, 1 profile change in HR review. Shots in `m1_shots/`.
- **Desktop 1440** (`m1_desktop_1440_top.jpg`, `m1_desktop_1440_sections.jpg`): eyebrow "MY PAYOBOOK ·
  WEDNESDAY 14 OCTOBER", "Evening, Linh.", "Your next pay lands in 17 days. 2 things need you." (the clone's pay
  calendar has an upcoming row), who pill with avatar. Needs you: "A document expires in 24 days" → opened
  `/my/documents` (clicked), "Profile change with HR" → `/my/profile`. Me strip: Profile, Documents ("1 expiring
  soon"), Tax Sheet, My Things (My Pay Package is not drawn by its own module for this person — no package).
  Time / Growth / People / More sections with coloured badges; Payslips, pay explainer and Leave tiles present
  in the DOM but `display:none`; invoice tiles hidden (`pbme-employee`); no breadcrumb bar, no "My account", no
  contact column; no horizontal scroll.
- **412 px** (`m1_phone_412_top.jpg`, `m1_phone_412_sections.jpg`, rendered in a 412 px same-origin frame,
  M18): one column, 30 px greeting, who pill under it, Needs card then Me strip (two per row), sections one per
  row; page width = viewport (no sideways scroll).
- **Vietnamese** (`m1_desktop_1440_vi.jpg`): every MEHOME word translated ("Chào buổi tối, Linh.", "Kỳ lương tới
  sẽ về sau 17 ngày. 2 việc đang chờ bạn.", "ĐANG CHỜ BẠN", section names, tile lines). Some tile TITLES from
  other modules (My Things, My goals, Public holidays…) stay English on the clone — their own modules'
  translations, not touched (M-R2).
- **Console**: no errors, no warnings, on every load (English, Vietnamese, phone frame, documents page).
- Afterwards: the walk login switched OFF (`active = false`; `admin` was already off), walk server stopped,
  tunnel closed.

## Font answer
The portal renders in **Inter**, but only because the website theme loads it from Google Fonts at weights
**400 and 700** (plus Inter Tight 700). The page's 800-weight greeting and labels are synthetic bold from 700.
Cost of doing it properly in M2: ship `pb_import_kit/static/fonts/InterVariable.woff2` (352 KB, one file, all
weights, already in the repo with its licence) into `web.assets_frontend` with one `@font-face`; it is cached
after the first visit. Alternative at zero cost: change the 800s to 700.

## Deviations (code over handover)
1. **`/my/home` also gets the page** — the stock `home()` serves both routes; only `/my` would have left
   `/my/home` as a bare stock page for employees.
2. **Hidden marker is `data-pbme-hidden="1"`, not a class** — the card's class is a stock expression
   (`t-att-class`); rewriting it would copy stock logic. CSS hides `[data-pbme-hidden]`. Same effect.
3. **Card xpath** uses `contains(@t-att-class, 'o_portal_index_card')` (M12).
4. **Breadcrumb bar** is removed with `no_breadcrumbs` (set beside `my_details`), not a `t-if` on the `ol` —
   the `ol` lives inside a container div that would still draw an empty bar.
5. **Facades called as the session user, not sudo** — that is what their own routes do (M15).
6. **`scheduled_h`** is summed from the week's own shift hours (the same sum the facade rounds into its label)
   instead of parsing the translated label.
7. **`pay` with no slips** still carries `next_pay_date`/`next_pay_days`/`explain_url` (a new starter still gets
   "Your next pay lands in N days"); `paid_on` is the Datetime stamp's date (M16); `trend`/`previous_net` keep
   only slips in the last slip's currency (no two currencies on one card).
8. **Test 6 PDF check**: the URL ends with `&download=true`; the test asserts `report_type=pdf` is in it (M16).
9. **Section headings are `h2`** (page `h1` is the greeting), not `h3` — correct outline for screen readers.
10. **Registry title/text overrides** carry the mock-up's short lines for most tiles (so a row reads in one
    line); they are lazy-translated Python words with VI lines.
11. **Documents tile line** ("1 expiring soon" / "N expired, upload the renewals") is filled from the payload
    in M1 (program doc lists it for the Me strip).
12. **Needs-row tones**: overtime and profile-with-HR indigo (waiting on someone else), goals amber (waiting on
    you), timesheet blue (mock-up).

## Against the design bar
Strong: personal greeting + one true sentence; Needs you names each thing and opens its door; every tile has a
coloured line icon in a named section; nothing empty is ever drawn; Vietnamese complete; clean console; phone
layout tidy. Not yet "extreme WOW" — that needs M2's money/time cards (the hero moment) and:
- **Load shift**: while the scripts load, the tiles show in the stock grid (sorted, badged) and then jump into
  their sections. Invisible on a warm cache in the walk; on a cold first visit it is visible for a moment. M2
  could hide `.o_portal_docs` behind a `<noscript>`-safe class set by an inline script, or render the sections
  server-side.
- 800-weight font (above).

## Learn
Nothing in Learn points at `/my`: grep of `pb_learn` and `docs/tutorial_poc` finds no route, anchor, tour or
replica for it — only one sentence in a Home tip and in `first_login.js` saying employees "start on My
Payobook". No lesson change needed.

## Open questions / left for Fable
- Font: ship the kit's Inter (352 KB) to the frontend, or drop to 700? (M17)
- The stock site header on the clone shows a broken logo image — clone website data, not this work.
- `TestPbMePortal.test_01` pre-existing error (M19) belongs to the approval-engine owner.
- The vault's teal (`pb_employee_vault` uses `var(--pbim-teal, #0E7C86)`) will now resolve to the kit's
  `#0F766E` wherever the kit vars are in scope — a one-shade change, worth a glance at deploy.
- Other modules' tile titles untranslated on the clone (Vietnamese) — check on payobook after deploy.

## Final run
`odoo.tests.result: 0 failed, 1 error(s) of 36 tests when loading database 'p0clone'` (2026-10-14 11:31 UTC) —
the one error is the pre-existing `TestPbMePortal.test_01` (M19). The log line
`ERROR: relation "no_such_table_pbme" does not exist` is test 5 proving a failed statement is contained.
