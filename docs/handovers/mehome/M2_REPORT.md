# MEHOME M2 — report (Opus build, 2026-10-14)

Handover: `M2_HANDOVER.md`. Ledger rows added: M20–M28. Nothing deployed, nothing pushed. Bench: `p0clone`
only (fresh stage `/tmp/m2stage`, `-u pb_import_kit,pb_me_portal --test-tags /pb_me_portal`,
`--db-filter=^p0clone$`). `pb_ess_workforce` was already installed on the clone — nothing installed.

## What shipped

| File | What |
|---|---|
| `pb_me_portal/models/pb_me_home.py` | `_pbme_week` adds `worked_h` (from `get_my_week()['totals']['actual']`, one decimal, `None` when the facade gives nothing; read through its own `optional()` so a failure only loses the number) and `shift_short` per day ("9–17", "9:30–18"); new `_pbme_hm_short`, `_pbme_worked_h`, public `fmt_num(value)` (days/hours in the reader's language: "12", "9.5", "9,5" in Vietnamese). |
| `pb_me_portal/views/portal_templates.xml` | `pbme_bento` now draws, in order, `pbme_card_pay` → `pbme_card_leave` → `pbme_card_week` → Needs you → Me strip, with `pbme-bento--no-leave` / `--no-week` classes for the grid fallbacks. Three new templates `pbme_card_pay`, `pbme_card_leave`, `pbme_card_week`. |
| `pb_me_portal/static/src/scss/me_portal.scss` | Card styles (pay light-tint, bars, ring, day cells, card buttons, empty cards), the 12-column grid with explicit placement at ≥ 1000 px + the three fallbacks, the 700–1000 px two-column layout, the ≤ 700 px one-column order (container query + media twin), the motion (`pbme-enter`, `pbme-bar-grow`, `pbme-ring-fill` + `@property --pbme-pct`), the tile load-shift fix (`pbme-reveal`), reduced-motion block. |
| `pb_me_portal/__manifest__.py` | **19.0.2.1.0**; `pb_import_kit/static/src/scss/fonts.scss` first in `web.assets_frontend` (before the tokens). No new dependency. |
| `pb_me_portal/i18n/vi_VN.po` | 32 new entries + one new occurrence ("No payslips yet" for the Pay card). No existing entry changed. |
| `pb_me_portal/tests/test_me_home_cards.py` (new), `test_me_home_source.py` | M2 tests 1–8 (below); the M1 source gates (vendor name, emoji, Font Awesome, icons, Vietnamese coverage) now also cover the three card templates. |
| `pb_import_kit` | **not touched** — `fonts.scss`, the WOFF2 and its licence already existed (HOME P2). No kit bump. |

### Words (all in the template, all with a Vietnamese line)
Pay: "Last pay · September" / "Pay" (no slip yet), "All payslips", "₫2,350,000 less than August" / "… more than …" /
"Same as August", "Next pay **Saturday 31 October**" / "Paid on **…**", "Explain my pay", "Payslip PDF";
empty: "No payslips yet · Your first payslip appears here once payroll runs".
Leave: "Leave", "18 days left" / "1 day left", "of 20 allocated" / "None taken yet", "· 1 request waiting" /
"· N requests waiting", "Request time off"; empty: "No leave allocated yet · Your balance appears here once HR
allocates your days · Open My Leave".
This week: "This week", "3 to confirm", cells "9–17" / "On leave" / "off", "39.5 h scheduled · 7 h worked so far" /
"No shifts scheduled this week", "Confirm shifts" / "Open schedule".
Every " · " is drawn by CSS and said to screen readers by a visually hidden twin (no lone "·" term).

## Tests (p0clone, final run)

| # | Test | Result |
|---|---|---|
| 1 | Pay card: figure through the monetary widget (₫ + `oe_currency_value`), "less than May" / "more than" / "Same as", no delta with one slip, six bars with `--pbme-h` = net / max × 100 (max = 100 %), last `is-cur`, one bar with one month, "Explain my pay" only with `explain_url`, PDF href = `pdf_url`, "All payslips" → `/my/payslips`, footer Next pay / Paid on / nothing, label "Last pay · June" | pass |
| 2 | Pay empty: "No payslips yet" + sentence, no bars, no PDF, next-pay line only when known, `pay = None` still draws the empty card | pass |
| 3 | Leave: `--pbme-pct: 47.5%` for 9.5/20, caption "of 20 allocated · 1 request waiting"; 20/20 → `0%` + "None taken yet"; `is-low` amber; empty state; `leave = None` → no card; bento with leave and week `None` → both modifier classes + SCSS puts Needs you at `6 / 13`, row `1 / 2`; only leave absent → This week `6 / 13`, rows `1 / 3` | pass |
| 4 | Week: 7 cells, `is-acked/pending/leave/off` per day, `is-today` once, "13–21 +1", pill "3 to confirm", solid "Confirm shifts"; pending 0 → outline "Open schedule", no pill; footer "38 h scheduled · 16 h worked so far"; all off → 7 off cells + "No shifts scheduled this week". Server: seeded attendance → `worked_h` = the facade's `totals.actual` (> 0); facade gives `{}` → `None` and the card still has 7 days; `fmt_num` 9.5 / 12 / 38 / None | pass |
| 5 | Grid: template order pay, leave, week, needs, me (source and rendered `data-pbme-slot`); SCSS explicit `grid-column`/`grid-row` for all five at ≥ 1000 px, the both-absent and one-absent fallbacks, `grid-auto-rows: minmax(84px, auto)`; ≤ 700 px one column ordered Pay → Needs → Week → Leave → Me in the container query AND the media twin | pass |
| 6 | Font: `fonts.scss` before `import_tokens.scss` in `web.assets_frontend`; WOFF2 + `Inter-OFL.txt` exist; face is `100 900`, `swap`; version 19.0.2.1.0 | pass |
| 7 | Sources: the only gradient (comments stripped) is `conic-gradient`, inside `.pbme-ring`; reduced-motion block stops the enter, bar and ring animations and NOT `pbme-reveal`; the four keyframes; `pbme-reveal 0s 2s forwards`; `@property` shape; stagger 60/120/180/240 ms. Plus M1 test 11 over the new templates: no vendor name / emoji / Font Awesome / `#4F46E5`, every icon drawn, JS never clones | pass |
| 8 | `vi_VN.po` parses (polib), no empty msgstr, every term of the three new templates present (M1 test 12, now covering them; checked against the fresh `.pot`) | pass |
| — | page over HTTP for a new employee: Pay card first ("No payslips yet"), Leave and This week empty states, Needs you + Me last | pass |
| 9 | Browser walk | pass — below |
| — | everything older | all pass except `TestPbMePortal.test_01_profile_change_flow_and_audit` (M19, pre-existing) |

Final line: `odoo.tests.result: 0 failed, 1 error(s) of 47 tests when loading database 'p0clone'` (2026-10-14
12:03 UTC) — the one error is M19. (`ERROR: relation "no_such_table_pbme"` in the log is M1 test 5 by design.)

## Walk (test 9) — p0clone, temporary server on 8099 (memory-capped unit, ssh tunnel)
Seed for "Linh Tran" (`docs/handovers/mehome/m2_walk_seed.py`): Paid Time Off allocation 20 days validated + 2 days
taken in September (validated); one approved Unpaid day on Friday 16; shifts Mon/Tue confirmed 9–17, Wed (today)
22:00–23:30, Thu 9–17, Sat 9–13 waiting; attendance Mon 09:00–17:00; three done slips July 27,250,000 / August
28,450,000 / September 26,100,000 in đ (a July slip added, the two M1 slips re-valued, one đ pay run per month — the
clone company is in USD, M26); her timezone set to Ho Chi Minh (user and employee, M22). M1's document and profile
request were already there.

- **Desktop 1440** (`m2_shots/m2_desktop_1440_top.jpg`, `m2_desktop_1440_sections.jpg`): Pay card "LAST PAY ·
  SEPTEMBER", **26,100,000 ₫** (symbol small, figure 40 px deep indigo), "2,350,000 ₫ less than August" in grey, three
  bars Jul/Aug/Sep (Sep solid), "Next pay Saturday 31 October", "Explain my pay" + "Payslip PDF". Leave ring at
  **90 %** (computed `--pbme-pct: 90%`, green), "18 days left", "of 20 allocated", "Request time off". This week:
  pill "3 to confirm", Mon/Tue indigo 9–17, Wed outlined with amber "22–23:…" (full time in the tooltip), Thu amber,
  Fri green "On leave", Sat amber 9–13, Sun grey off; "39.5 h scheduled · 7 h worked so far" (the 8 h attendance
  counts 7 h after lunch, M24), solid "Confirm shifts". Placement read from the browser: Pay `1/6 × 1/4`, Leave
  `6/9 × 1/3`, Week `9/13 × 1/3`, Needs you `6/13 × 3/4`, Me strip `1/13 × 4/5` (full width; four tiles across —
  My Pay Package is not drawn by its module for this person). No sideways scroll (scrollWidth = 1440).
- **Motion**: the GIF tool could not catch it — the first frame lands after the 1 s entrance has finished (M25).
  Proved instead by re-inserting the bento and reading the browser's own animation list: `pbme-enter` on pay/leave/
  week/needs/me at 0/60/120/180/240 ms (320 ms each), `pbme-bar-grow` ×3 (480 ms, +340 ms), `pbme-ring-fill`
  (600 ms, +400 ms); at t = 0 pay opacity 0, ring 0 %, bars scaleY 0; afterwards opacity 1, ring 90 %, bars full,
  nothing running.
- **Tile load shift**: with `pbme-ready` removed, `.o_portal_docs` is `visibility: hidden`, `animation: pbme-reveal`
  with a 2 s delay, `order: 1` (it sits below the bento, so nothing jumps); the Needs card stays drawn.
- **412 px** (`m2_phone_412_top.png`, `m2_phone_412_middle.png`, same-origin 412 px frame, M18): one column in the
  order Pay → Needs you → This week → Leave → Me (read from the frame's layout), full-width buttons (Request time off
  340 px), cells fit except today's "22–23:30" (ellipsis + tooltip), frame scrollWidth = 412.
- **Vietnamese** (`m2_desktop_1440_vi.jpg`): "KỲ LƯƠNG GẦN NHẤT · THÁNG 9", "26.100.000 ₫", "2.350.000 ₫ ít hơn tháng 8",
  bars "Thg 7/8/9", "Kỳ lương tới Thứ Bảy 31 Tháng 10", "Giải thích lương của tôi", "Phiếu lương PDF"; "NGHỈ PHÉP",
  "18 ngày còn lại", "trên tổng 20 ngày được cấp", "Xin nghỉ phép"; "TUẦN NÀY", "3 cần xác nhận", day names
  "TH 2 … CN", "Phép", "nghỉ", "39,5 giờ theo lịch · 7 giờ đã làm", "Xác nhận ca làm". All three cards fully
  translated (first pass showed "Nghỉ p…" in Friday's cell; fixed with its own word, M27).
- **Console**: no messages on any load (English, Vietnamese, phone frame).
- **Font check** (item 7): `document.fonts.check('800 20px Inter')` = true; the greeting's computed weight 800;
  loaded Inter faces = Google's 400 and 700 (from the website theme) **and** ours `100 900` from
  `/pb_import_kit/static/fonts/InterVariable.woff2`. The only face that covers 800 is ours, so the browser uses it
  for every 800 (no synthetic bold); the two sources do not fight for 800. They overlap at 400/700, where either is
  the same Inter.
- Afterwards: Linh's login switched OFF (`active = false`; `admin` still off), walk server stopped, tunnel closed,
  browser tab closed.

## Deviations (code over handover)
1. **Ring fill is a keyframe animation from 0 %**, not a transition armed by `.pbme-ready` — it does not depend on the
   scripts running (a transition would leave the ring empty if they failed). Same `@property`, same 600 ms.
2. **Bars grow with `transform: scaleY`** (smooth on the compositor) rather than animating `height`; the final height
   is still the server's `--pbme-h`.
3. **Day names come from the date** (`EEE` through the date widget), not the facade's `label`, which is English in
   every language (M22). The facade label is the fallback when a day has no date.
4. **`shift_short` added** ("9–17") because "09:00–18:00" is cut to "09:0…" in a 45 px cell; the full text is the
   cell's tooltip.
5. **The leave cell says "On leave"**, not "Leave" — one msgid has one translation, and "Nghỉ phép" did not fit (M27).
6. **Separators** are CSS + a visually hidden " · " (M1's approach), so the HTML text reads "38 h scheduled · 16 h
   worked so far" without a "·" translation term.
7. **Load shift**: besides the hidden-then-revealed grid, `.pbme-home` is a flex column and `.o_portal_docs` has
   `order: 1`, so the invisible stock grid sits at the end while scripts load — otherwise it would hold space ABOVE the
   bento and the cards would jump up when the tiles move.
8. **700–1000 px** uses even `span 6` auto-placement (pay, leave / week, needs / me) — the stated layout — and, when
   only one of Leave / This week is absent, Needs you takes the full row so no hole is left.
9. **No slip yet → label "Pay"** (the handover only names "Last pay · month").
10. **Bars take the card's spare height** (72–200 px) — the 3-row Pay card next to a long Needs list otherwise had a
    large blank middle.
11. **"None taken yet" replaces "of N allocated"** (the number is already inside the ring).
12. **`worked_h` shows whenever it is not `None`**, including 0 h, as the handover words it.
13. **`%%` in templates** is written as `'…%g' % v + '%'` (M20).
14. Walk seed differs where the clone needed it: 7 h worked (M24), two confirmed days added for a fuller week, today's
    shift in the evening so it is still confirmable, đ pay runs (M26).

## Against the design bar (card by card)
- **Pay — 9/10.** The person's own last pay is the biggest thing on the page, with the month, a calm grey difference
  against the month before, a real six-month chart and the next pay day; both doors are one click. The figure is
  server-formatted, so Vietnamese reads "26.100.000 ₫". Short of 10: with three months the chart is three wide bars
  on the left (true to the data, but a little sparse), and when the nets are close the bars look alike.
- **Leave — 9/10.** One glance answers "how much is left": a 96 px two-tone ring that fills on arrival, the number
  inside, plain caption, one outline button. Empty and "nothing taken" states say what they mean. It is a quiet card
  next to Pay — by design.
- **This week — 8.5/10.** Seven cells read like a calendar strip: confirmed indigo, waiting amber, leave green, off
  grey, today outlined, a count pill and the one solid button when something waits; hours scheduled against worked
  below. Short of more: a late or long shift ("22–23:30") is cut in a desktop cell (tooltip only), and the card has
  some empty height under the cells when Needs you is long.
- **Page as a whole**: the three cards + Needs you + Me strip fill the first screen at 1440 with real figures, settle
  in once with a 60 ms stagger, nothing flashes while scripts load, the phone order puts money and "needs you" first,
  and the 800-weight type is now the real Inter. Clean console.

## Learn
Nothing in Learn points at `/my` (grep of `pb_learn` and `docs/tutorial_poc`: no route, anchor, tour or replica);
no lesson change needed.

## Open questions / left for Fable
- Deploy needs the usual frontend asset purge (JS/SCSS changed) and an upgrade of `pb_me_portal` on every database.
- Today's or long shifts cut in a desktop day cell ("22–23:…"): accept the tooltip, or let the cell text wrap to two
  lines?
- Tile titles from other modules (My Things …) are still English in Vietnamese on the clone (M1 open point).
- The clone's website logo image is broken (missing file) — clone data, not this work.
- M19 (`TestPbMePortal.test_01`) is still the approval-engine owner's.
