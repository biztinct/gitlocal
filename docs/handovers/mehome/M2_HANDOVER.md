# MEHOME M2 — the hero moment: Pay, Leave and This week cards, motion, font, polish (handover for Opus)

Read first: `MEHOME_PROGRAM.md`, `MEHOME_LEDGER.md` (rules M-R1…R9, rows M1–M19 — M12–M19 are M1's own
gotchas, read them all), `M1_HANDOVER.md` + `M1_REPORT.md` (what exists: payload keys, template ids, class
names, the words table, the bench recipe incl. `--db-filter`, M14), and the build target
`docs/design/my-payobook-home-poc.html` → tab **Bento** (desktop AND Phone). The code you extend:
`pb_me_portal/models/pb_me_home.py` (`get_home_data`, `_pbme_pay`, `_pbme_leave`, `_pbme_week`),
`views/portal_templates.xml` (`pbme_bento`, the `data-pbme-slot` comment), `static/src/scss/me_portal.scss`
(`.pbme-bento`, `.pbme-b*`, the `pbme-ready` rules), `static/src/interactions/me_home.js`. CLAUDE.md applies.
You do not deploy.

## Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." M2 IS the hero moment: a person opens
`/my` and sees their own last pay, their leave left and their week before any click, the cards settle in with
one quiet motion, and every empty state names what will appear. Measure against the best consumer pay app, not
against stock portal pages. Score the report against this bar, card by card.

## Scope (M2)
1. **Pay card** (`data-pbme-slot="pay"`, template `pbme_card_pay`), light-tint (`--pbim-soft` bg,
   `--pbim-primary-light` border) exactly as the mock-up: label `banknote` icon + "Last pay · %(month)s"
   (`last.period_date` as `MMMM`); the net figure large (40 px, `--pbim-primary-dark`, monetary widget with
   `last.currency`, tabular-nums); a **neutral** delta line when `previous_net` is not None: "%(amount)s more
   than %(prev month)s" / "%(amount)s less than …" / "Same as %(prev month)s" (amount = monetary of the absolute
   difference; prev month = `trend[-2].month_date` as `MMMM`; grey, no arrow colour); **six bars** from `trend`
   (height = net / max net × 100 %, inline `style="--pbme-h: 76%"` set server-side; the last bar `is-cur` solid
   indigo, others white with indigo border; `MMM` labels under; one bar still draws when `trend` has one
   entry); footer: "Next pay" + `<b>` weekday-date (`EEEE d MMMM`) when `next_pay_date`, else "Paid on
   %(date)s" when `last.paid_on`, else nothing; buttons right: "Explain my pay" (outline, only when
   `explain_url`) and "Payslip PDF" (solid, `download` icon, `last.pdf_url`); the label row's right end holds a
   quiet "All payslips" link (`list_url`). **Empty state** (`count == 0`): `file-text` badge, "No payslips yet",
   "Your first payslip appears here once payroll runs", the next-pay line when known, and the quiet "All
   payslips" link. The card ALWAYS renders (pay is never `None` on this build; guard anyway).
2. **Leave card** (`slot="leave"`, `pbme_card_leave`; not drawn when `leave` is `None`): label `umbrella` icon
   + "Leave"; a 96 px ring = `conic-gradient(var(--c) 0 var(--pbme-pct), var(--c-soft) var(--pbme-pct) 360deg)`
   with `--pbme-pct` set inline from `left / allocated` (clamped 0–100 %, 0 when allocated is 0) — the ONE
   allowed two-tone (M-R1); inside: `left` (one decimal only when not whole, e.g. "9.5", "12") + "days left";
   caption "of %(allocated)s allocated" + " · %(n)s request(s) waiting" when `booked_pending`; ring colour green,
   **amber when `low`** (never rose, never a ring at 100 % — when `left == allocated` draw the ring at 100 %
   soft colour only, i.e. `--pbme-pct: 0`, and the caption "None taken yet"); outline button "Request time off"
   → `url`. **Empty state** (`allocated == 0`): `umbrella` badge grey, "No leave allocated yet", "Your balance
   appears here once HR allocates your days", quiet link "Open My Leave". Add `worked_h` nowhere here.
3. **This week card** (`slot="week"`, `pbme_card_week`; not drawn when `week` is `None`): label `calendar` icon
   + "This week" + a right-aligned amber pill "%(n)s to confirm" when `pending`; seven cells from `days`
   (`label` as given, `day_num`, then the shift text or a word): `state` → class and tone: `acked` indigo-soft
   with the hours text, `pending` amber-soft with the hours text, `leave` green-soft "Leave", `off` grey "off";
   `is_today` outlines the cell indigo; two or more shifts in a day → the first's hours + "+1"; footer line
   "%(h)s h scheduled" + " · %(w)s h worked so far" when the server gives `worked_h` (ADD IT: in `_pbme_week`,
   read `Ess.get_my_week(monday.isoformat())` once and take `totals.actual` (the week's `{sched, actual,
   entered, delta}`, `pb_time_hub/models/time_hub.py:368-373` — read the real key names first) → `worked_h`
   rounded to one decimal, `None` when the call gives nothing); button: solid "Confirm shifts" → `url` when
   `pending`, else outline "Open schedule". **Empty week** (every day `off`): cells still draw, footer reads
   "No shifts scheduled this week", button outline "Open schedule".
4. **Grid** (desktop ≥ 1000 px, 12 columns, `grid-auto-rows: minmax(84px, auto)`, 14 px gap): Pay cols 1–5
   rows 1–3; Leave cols 6–8 rows 1–2; This week cols 9–12 rows 1–2; **Needs you cols 6–12 row 3**; the **Me
   strip becomes a full-width row under the bento** (cols 1–12, five tiles across, two rows of tiles when
   more). Place with explicit `grid-column`/`grid-row` so auto-placement cannot leave holes; when Leave AND
   This week are absent: Pay cols 1–5, Needs cols 6–12 row 1 (the mock-up's row heights do not apply);
   when only one of them is absent the other takes cols 6–12 rows 1–2. 700–1000 px: Pay cols 1–6, Leave 7–12,
   Week 1–6, Needs 7–12, Me full. ≤ 700 px (container AND media twin, as M1): one column in the order Pay →
   Needs you → This week → Leave → Me. Day cells shrink (min-width 0, 9–10 px shift text, ellipsis).
5. **Motion with purpose** (CSS only, all disabled under `prefers-reduced-motion`): the bento cards enter once
   with a 320 ms fade + 8 px rise, staggered 60 ms per card (`animation-delay` by nth-child); the six bars grow
   from 0 to `--pbme-h` over 480 ms after the card lands; the ring fills from 0 to `--pbme-pct` over 600 ms
   (`@property --pbme-pct { syntax: '<percentage>'; inherits: false; initial-value: 0% }` + a transition on
   `.pbme-ready` — browsers without `@property` simply show the final ring); tiles keep their hover lift. No
   count-up on money (locale formatting stays on the server).
6. **Tile load shift** (M1 report): `.pbme-home:not(.pbme-ready) .o_portal_docs { visibility: hidden; animation:
   pbme-reveal 0s 2s forwards }` with `@keyframes pbme-reveal { to { visibility: visible } }` — the stock grid
   never flashes on a normal load, and a page whose scripts fail still shows its tiles after two seconds. Keep
   the hero and the Needs card visible from the first paint (they are server-rendered, no class gate).
7. **Font** (M17, decision: ship it): add the kit's `fonts.scss` (the `@font-face` for
   `pb_import_kit/static/fonts/InterVariable.woff2`, weights 100–900, `font-display: swap`) to
   `pb_me_portal`'s `web.assets_frontend` BEFORE `import_tokens.scss`. Prove in the walk that the greeting's
   computed weight 800 is served by the variable face (`document.fonts.check('800 20px Inter')` true and no
   synthetic bold — compare a screenshot crop of "Evening, Linh." before/after if in doubt). If the website
   theme's Google-hosted Inter 400/700 and the local face fight, the local one must win for 800 (say what you
   saw).
8. **Words**: every new sentence in the templates with a VI line in `i18n/vi_VN.po` (same export recipe as M1,
   H37, M13; `polib` gate). Plural forms as M1's rows (`n == 1` branch + the other).
9. **Learn**: nothing points at `/my` (M1 confirmed) — re-state in the report.

## Binding non-goals
No change to any other module except the kit (M-R2). No new dependency (M-R3); no new model reads beyond
`get_my_week` totals (item 3). No OWL, no Chart.js, no CDN. No deploy. No vendor name. No change to M1's
registry, Needs you rows or sections except the grid placement in item 4.

## Numbered tests (`tests/test_me_home_cards.py` + additions to `test_me_home_source.py`; M1's 13 and the module's older tests stay as M1 left them — M19 remains the one pre-existing error)
1. Pay card HTML (render `pbme_card_pay` with a built payload): the net figure through the monetary widget
   (currency symbol present), the delta line reads "more than" / "less than" / "Same as" for the three cases and
   is absent when `previous_net` is None, six `.pbme-bar` with `--pbme-h` proportional to the max (max = 100 %)
   and the last one `is-cur`, "Explain my pay" only when `explain_url`, "Payslip PDF" href = `pdf_url`.
2. Pay empty state (`count == 0`): "No payslips yet", no bars, next-pay line present when `next_pay_date`.
3. Leave: `--pbme-pct` = 47.5 % for 9.5/20; 0 % and "None taken yet" when left == allocated; amber class when
   `low`; empty state when allocated == 0; `leave is None` → no `pbme-b-leave` in the page and Needs you takes
   cols 6–12 row 1 (source test on the SCSS rule + an HTML test with the slot absent).
4. Week: seven cells, class per state (`is-acked/is-pending/is-leave/is-off`), `is-today` once, "+1" when a day
   has two shifts, pill "3 to confirm" and solid "Confirm shifts" when `pending == 3`, outline "Open schedule"
   when 0, footer "38 h scheduled · 16 h worked so far" when `worked_h` = 16.0, "No shifts scheduled this week"
   when all off. Server: `_pbme_week` returns `worked_h` from `get_my_week` totals (seed an attendance if the
   clone's facade needs one; otherwise assert the key is present and `None`).
5. Grid source test: the template places the five slots in the order pay, leave, week, needs, me; the SCSS has
   explicit `grid-column`/`grid-row` for each at ≥ 1000 px, the three fallbacks (both absent / one absent) and
   the ≤ 700 px order.
6. Font: the manifest lists the kit `fonts.scss` in `web.assets_frontend` before the tokens; the WOFF2 and its
   licence file exist.
7. Source: the only `gradient` in the module's SCSS is `conic-gradient` inside the `.pbme-ring` rule; the
   reduced-motion block names the enter, bar and ring animations; `pbme-reveal` keyframes exist with a 2 s delay;
   no vendor name, no emoji, no Font Awesome, no `#4F46E5`; the JS still never clones.
8. `vi_VN.po`: parses, no empty `msgstr`, every new term present (fresh `.pot`).
9. Browser walk on the clone (seed for "Linh Tran": a validated allocation of 20 days + 2 validated days taken,
   three published shifts this week with confirmation pending (one on today), one approved leave day this week,
   an attendance of 8 h on Monday, 3 done slips with nets 27.25 M / 28.45 M / 26.1 M đ in that date order, and
   M1's document + profile request; if `pb_ess_workforce` is not installed on the clone, install it on the clone
   only and say so): desktop 1440 — all three cards with real figures, delta line, bars, ring at 90 %, pill "3 to
   confirm", footer hours, Needs you at cols 6–12, Me strip full width; the enter motion visible once (record a
   short GIF with the Chrome tool if it works, else say so); 412 px (iframe, M18) — single column in the stated
   order, no sideways scroll; VI switch — the three cards fully translated; console clean on every load; the
   font check from item 7. Shots in `docs/handovers/mehome/m2_shots/`. Login OFF after (H44).

## Deliverables / report
`docs/handovers/mehome/M2_REPORT.md` as M1's (what shipped, test table, walk with shots, deviations, score
against the bar per card, ledger rows M20…, open questions). Version `pb_me_portal 19.0.2.1.0`; kit bump only
if touched. Commits on `19.1`, feature-scoped, explicit paths, `feat(mehome): M2 …`, Co-Authored-By line from the
session reminder. Do not push, do not deploy.

## How to run
As M1 (`M1_REPORT.md` "How to run" + M14's `--db-filter=^p0clone$`): fresh stage dir, `pb_me_portal
pb_import_kit` staged, detached `-u pb_import_kit,pb_me_portal --test-tags /pb_me_portal` on `p0clone`, read
the `odoo.tests.result` line; walk server on 8099 through the tunnel; live databases never touched.
