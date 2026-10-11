# Pay Run board redesign — design spec (2026-10-11)

Status: **DESIGN, awaiting owner approval.** Nothing implemented. Prototype the
owner reviews: see the Artifact link in memory `payrun-board-redesign.md`.
Source of the prototype: `docs/design/payrun-board-prototype.html` (single
file, no build; open in a browser).

Owner's brief: "This kanban screen is going to be used a lot. Design it to be
visually attractive, intuitive, premium, WOW." Coaching/Learn screens follow
later and must stay in sync (anchors below).

## 1. What is wrong with the live board (pb_payruns 19.0.2.10.0)

Observed on payobook.com (screenshot 2026-10-11):

1. **The same three numbers appear three times** — the quiet numbers line
   (16 in pipeline / 0 awaiting / 33 completed), the numbered step strip
   (16 / 0 / 33) and the column headers (16 / 0 / 33) directly beneath. The
   "Showing all 49 pay runs · press a step or a number" line is a fourth row
   of chrome before the first card.
2. **Columns are unequal** when one is empty: Draft wide, "Waiting for
   approval" a sliver, Done wide. An empty column looks broken rather than
   calm.
3. **Cards carry three identical grey tiles** (Employees / Gross / Net) so
   the figure that matters (net) has no hierarchy; the period line repeats
   the month already in the run's name.
4. **Done cards are button soup**: five buttons (Pay & Deliver, Report,
   Excel, Journals, Payments) × 33 cards, and "Pay & Deliver" is the solid
   primary on runs paid months ago. The board cannot tell an approved-unpaid
   run from a paid-and-delivered one, although the data exists
   (`hr.payslip.run.pb_paid / pb_paid_on`, delivery batch state, journal
   state in `pb_pay_delivery`).
5. **No sense of time.** The Done column is a 33-card wall; the hub chip
   says "OCT 2026 · STAGE 2/5" but nothing on the board explains the month.
6. Division chip label bug: `pb_division_label` title-cases the key, so
   `it` → "It" (should read "IT"). Tag it from the config's name instead.
7. No bulk actions, no keyboard, no quick look — every click leaves the board
   for the native form.

## 2. The design (what the prototype shows)

Keeps the owner-approved model: three steps (Draft → Waiting for approval →
Done), rejected runs as an outcome in a drawer, the "Run payroll" door, the
in-card Reject with a required reason, scheme-currency figures.

### Hero: "This month"
Light-tint card (design-system hero treatment). Three parts:
- **Month + journey**: "October 2026 · 1–31 Oct", a 5-node journey
  (Not started · Drafting · In approval · Approved · Delivered) lit from the
  hub's own tracker (`pb.pay.hub.get_period_state` — same stage number as the
  header chip, so they never disagree), "Stage 2 of 5 · Drafting".
- **The sentence** (the hero moment): "7 pay runs this month across 6
  divisions. 3 are still drafts, 2 are waiting for a sign-off, 1 is approved
  and ready to pay and 1 is paid and delivered." Each phrase is a filter
  (press "3 are still drafts" → board narrows to October drafts; press again
  clears). Second line in amber only when a person must act: "1 pay run is
  waiting on you." / "1 was sent back to be fixed." Otherwise grey "Nothing
  is waiting on you."
- **Net pay this month** (big) + people + runs, and **the one next-step
  button**, chosen in this order: waiting on me → "Open the approval";
  sent back → "See what to fix"; drafts → "Submit N drafts for approval"
  (opens a confirm sheet listing them); approved unpaid → "Pay & Deliver X";
  all done → "Run payroll for November"; no runs → "Run payroll for October".
  This is the ONLY solid button on the page; "Run payroll" top-right becomes
  outline. (Coaching anchor `pk-run` stays on it.)
- Replaces the quiet numbers line entirely (anchor `pk-kpis` moves to the
  hero). The all-time "₫273B net paid" figure is dropped from this screen —
  it is an Insights number.

### Toolbar
`All months | October only` segment · division chips with the division
monogram · search "Find a pay run" (`/`) · Board | List toggle · keyboard
help. Showing line stays but only when narrowed ("Showing 3 of 33 pay runs
at Draft · in Retail · Show all").

### Lanes (the step strip and the column header are ONE thing)
Three equal lanes on a soft lane background; the lane header is the numbered
step card: `01` badge (slate / amber / green), title, count pill naming its
unit ("4 pay runs"), a flag line in place of a second strip:
- Draft: "1 sent back to be fixed" (amber) or "1 run has payslips with no
  data" (rose), else a one-line hint.
- Waiting: "1 is waiting on you" (amber, soft glow) beats "2 waiting for a
  sign-off".
- Done: "1 approved, not paid yet" (indigo).
Arrow badge in the gutter as today. Pressing a header = **focus mode**: the
other two lanes collapse to 64px rails (number, vertical title, count, first
four monograms) and the focused lane spreads into a card grid. Press again or
Esc to restore. Animated grid-template-columns.
Inside a lane, runs are grouped by month when more than one month is present;
in Done each month is a collapsible row ("September 2026 · 7 runs · ₫96.8B",
collapsed rows show the division monograms) with only the latest month open.
Anchors: `pk-steps` → lane headers, `pk-tabs` → the board.

### Card
- Division monogram tile (two letters, muted categorical tint per division;
  neutral "PR" when the tenant has no divisions) + name (2-line clamp) +
  period + kind chip (Bonus / Top-up / Awards / refund).
- **One figure**: "NET PAY ₫14.51B" large; "400 people · gross ₫17.79B"
  quiet below. (Owner rule: a figure the reader came to read may stay big.)
- Notes, each naming the problem AND the next step: amber "Sent back by Lan
  Nguyen: …"; rose "12 payslips have no source data … Check the import before
  you submit →" (`pb_unsourced_count`); rose "Figures don't add up … Open
  the run to see which component →" (`pb_balance_ok` / `pb_balance_gap`).
- Waiting: route block "Sign-off 2 of 3 · Finance sign-off", 3 segments,
  avatars, "With Minh Tran" / amber "Waiting on you" (card gets an amber
  left stripe). Anchor `pk-route`.
- Done: a 5-segment **delivery rail** Approved · Bank file · Paid ·
  Payslips · Journals (green done, indigo next) with a status line
  ("Paid 30 Sep · 902 payslips sent · journals posted" / "Approved 10 Oct ·
  not paid yet").
- Footer (anchor `pk-card-actions`): Draft → solid "Submit for approval" +
  text "Reject" + ⋯; Waiting → "Open the approval" if mine, else "Waiting for
  Minh Tran" + ⋯; Done unpaid → solid "Pay & Deliver" + ⋯; Done paid →
  outline Report, Excel + ⋯. The ⋯ menu holds Payroll report, Download
  Excel, Journals, Payments, Quick look, Open the full run, Reject.
- Hover: lift + a checkbox appears (top-right) for multi-select; shift-click
  selects a range within a lane.
- In-card Reject confirm unchanged in behaviour (reason required, Esc / ⌘↵).
  Anchor `pk-reject-why`.

### Quick look (peek panel)
Clicking a card body opens a 480px right panel instead of leaving the board:
Where it is (3 step tiles + the sign-off route timeline, or the delivery
timeline), The money (net with the full figure, gross, deductions, employer
cost, net per person, "Gross − deductions = net. The figures add up." or the
rose gap), What happened (prepared / submitted / signed off / sent back /
paid / delivered, with dates), footer with the same primary action and "Open
the full run ↗". Esc closes.

### Bulk bar
Appears when ≥1 card is selected: "3 pay runs selected · ₫52.0B net ·
Submit for approval (only when all are drafts) · Download Excel · Clear".
Bulk submit goes through the same confirm sheet as the hero button.

### Keyboard
↑↓ move within a lane, ←→ across lanes, Enter quick look, Space select,
S submit a draft, / find, Esc close/clear, ? help sheet.

### Motion with purpose
Hero rises in once; the current journey node pulses; a submitted card FLIPs
from Draft to Waiting and both count pills bump; lane focus animates the
grid; peek slides in; busy card shimmers; skeleton while loading. All off
under prefers-reduced-motion.

### Zero dead-ends (states designed)
Empty Draft ("No drafts. Press Run payroll…" + button), empty Waiting
("Nothing is waiting. A run you submit sits here until everyone on its route
has signed it off."), empty Done, narrowed-empty variants, new tenant (hero
says "No pay run covers October yet"), small tenant without divisions (no
chips, neutral monogram, "Monthly payroll · October 2026"), loading skeleton,
multi-currency note kept from today (not drawn in the prototype).

### List view
Same filters; table Pay run · Period · Where it is (status pill incl. "With
Minh Tran", "Approved · to pay", "Paid 30 Sep") · People · Gross · Net ·
action; sortable headers; row click = quick look.

## 3. Data the board needs that it does not load today
All additive to `pb.payruns.get_board_data` (no model changes):
- per run: `paid` (`pb_paid`), `paid_on`, `bank_file_done`, `payslips_sent`
  (delivery batch `sent_count` / state), `journals_posted`
  (`pb.payroll.journal` state), `balance_ok`, `balance_gap`, `unsourced_count`,
  `approved_on`, `prepared_by` (`pb_prepared_uid`), route `step_index` /
  `step_total` / per-step status (`approval_request_id.step_ids`), history
  events (mail.tracking or the request's step log).
- period block: reuse `pb.pay.hub.get_period_state()` (stage, label, counts)
  rather than recompute.
- division label from the formula config's name (fixes "It").
- **Pay day**: no field exists. The prototype prints "pay day 31 Oct" as a
  proposal; either add a pay-day setting on the scheme or drop the words.

## 4. Coaching / Learn anchors (keep names, move targets)
`pk-run` (Run payroll button) · `pk-kpis` (hero) · `pk-divchips` (chips) ·
`pk-steps` (lane headers) · `pk-tabs` (board) · `pk-card` · `pk-card-actions`
· `pk-route` · `pk-reject-why` · `pk-rejected`. New anchors to add for Learn:
`pk-hero-next` (the next-step button), `pk-peek` (quick look), `pk-bulk`.
Lessons that describe "the numbers line + the step strip" need re-recording.

## 5. Owner decisions (settled 2026-10-11 — binding)
1. Default period: **All months** (Done grouped by month, latest open).
2. "Pay day" words: **dropped**. No pay-day setting. Hero shows month + dates.
3. Division monograms: **soft categorical colour per division** (stable per key).
4. Reject: **stays visible on the card** as the quiet red text button.
5. Card click: **quick-look panel**; "Open the full run" inside it.

Build mode: **Fable builds directly** (owner's choice), then the Learn /
coaching catch-up.
