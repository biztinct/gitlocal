# PAYBUILDER — design of record

**Status:** approved by the owner 2026-11-28 (clickable design + answers below).
**Clickable design:** `docs/design/pay-builder-poc.html` · published https://claude.ai/artifact/CRAxKSWmfKUyvTUg5fgqNY
**Companions:** `PAYBUILDER_FACTS.md` (verified plumbing, file:line) · `PAYBUILDER_BUILD_HANDOVER.md` (what to build, phases, tests) · `PAYBUILDER_LEDGER.md` (rules + gotchas) · `PAYBUILDER_CODEX_PROMPT.md` (paste-in prompt).

This document says **what the person sees**: screens, words, states, motion, styling. The handover says how to build it.
Where this document and the clickable design disagree, **this document wins**; where both are silent, copy the clickable
design pixel for pixel.

---

## 1. The idea in one paragraph

Today step 3 of Add employee asks for one number ("Monthly wage") and shows "The scheme's usual answers". HR cannot see
what that number becomes, and on schemes that do not start from a monthly wage (live example: Rize India starts from a
yearly package) the number HR types pays nothing: the example payslip reads Gross 0, Take-home 0. The **Pay Builder**
replaces both cards with one block: HR types what was agreed, and the person's pay scheme works out the whole month in
front of them — earnings, deductions, what the company pays on top, take-home. Lines HR may set are inputs. Lines the
scheme works out are locked, and each opens to show its sum in plain words with this person's numbers. The same block is
then used wherever pay is agreed or changed: the Hiring offer, the contract panel ("Change pay"), and read-only on the
new person's joining page.

**Hero moment (design mandate):** type the big number and watch every line, the split bar and the take-home figure move
together; point at a worked-out line and the lines it uses light up; open it and read the sum with real numbers.

**The bar, verbatim from the owner (binding):** "extreme WOW, intuitive, out-of-this-world experience, best in class."
A hero moment; zero dead-ends (every state designed, every failure names its reason and next step); plain language over
code vocabulary on every label; motion with purpose; keyboard ergonomics; measured against the best tool in the
category. Lucide SVG icons only, never emoji. No gradients. The phase report scores itself against this paragraph.

## 2. Owner decisions (do not re-ask)

| # | Decision | Date |
|---|---|---|
| D1 | The Pay Builder replaces the "Monthly wage" card and "The scheme's usual answers" card in step 3. | 2026-11-28 |
| D2 | Formula lines are read-only everywhere; HR can read how each is worked out, never edit it here. | 2026-11-28 |
| D3 | Lines with no formula that the scheme marks as per-person are editable by HR and are saved on the person's contract (same path as today's usual answers; after approval where a route exists). | 2026-11-28 |
| D4 | "Let HR choose per allowance": the per-person / each-month choice is the scheme's existing tick box on each component, given a plainer name (§9). Nothing changes on any tenant until someone flips one. | 2026-11-28 |
| D5 | "Work back from take-home" is built now. | 2026-11-28 |
| D6 | **The right column ("The record so far") keeps today's layout, colours and cards exactly** — avatar ring, key facts, Payroll-ready, Who does what, Paid by, the dark "A month's payslip · example" card. Only its numbers must agree with the Pay Builder. Do not restyle it. (The clickable design simplified that column; ignore that part of it.) | 2026-11-28 |
| D7 | Same block in four homes: Add employee step 3, Hiring offer, contract panel "Change pay", new person's joining page (read-only). | 2026-11-28 |
| D8 | Built and released by a Codex session (as JOINING was). | 2026-11-28 |
| D9 | A later raise of an allowance is done from the contract panel's "Change pay", with a start date and before/after, through today's approval route. | 2026-11-28 |

## 3. Words (screen vocabulary — use exactly)

| On screen | Never say |
|---|---|
| pay scheme | config, structure, formula config |
| line (of the month's pay) | rule, component code, column |
| You set | input, contract component, advantage |
| Worked out | formula, computed, calculated field |
| Each month | variable input, feed, import column |
| Set by the pay scheme (a fixed rate or ceiling) | constant |
| usual amount / Back to usual | default value |
| Take-home | net, NET PAY (unless that is the line's own name) |
| Gross pay · Deductions · Cost to the company | band, role, employer_cost |
| the pay data file · the connected system · the timesheet | feed, integration, provenance |
| Formula Studio | (keep — it is the screen's name) |

**White-label rule (binding):** the word "Odoo" never appears in any string a user can see or receive — labels, help,
toasts, errors, emails, `.po` msgstr. Use "Payobook" (white-label swaps it per tenant) or a neutral word. Technical
identifiers are untouched.

Money: the contract's currency symbol and the user's number format, tabular figures, no decimals when the currency has
none; never add two currencies.

## 4. Anatomy of the block

```
┌ CARD A — "What you agree" ───────────────────────────────────────────────┐
│ <HEADLINE LABEL> *                      ALSO ASKED BY THIS PAY SCHEME      │
│ [ ₹  1,200,000            INR a year ]  Variable pay for the year  [₹ 0]  │
│ That is ₹100,000 a month before deductions.  Work back from take-home     │
│ (pay band / pay scale line, as today)   Pays social insurance      (●)    │
└───────────────────────────────────────────────────────────────────────────┘
┌ CARD B — "A month's pay, worked out" ────────────────────────────────────┐
│ By <scheme>, for a full <Month YYYY>.        ✎ You set  ▦ Worked out  ▣ Each month │
│ EARNINGS                                                                   │
│  ▦ Basic                 Worked out                         ₹50,000   ⌄   │
│  ✎ Medical reimbursement You set · ✦ Usual amount        [₹   1,250]      │
│  ▣ Approved arrears      Each month, from the pay data file · Try an amount   ₹0 │
│  Also in this scheme:  (+ Telephone and internet) (+ Car maintenance …)   │
│  Gross pay                                                  ₹98,250       │
│ DEDUCTIONS …                              Total deductions   ₹3,200       │
│ PAID BY THE COMPANY ON TOP …              On top of gross pay ₹3,000      │
│ ───────────────────────────────────────────────────────────────────────── │
│ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ (split bar)        │
│ ● Take-home     Gross pay     ● Deductions    ● Cost to the company       │
│ ₹95,050         ₹98,250       ₹3,200          ₹101,250                    │
│ ₹1,140,600 a year …                                                       │
│ ⓘ A full month, with each-month lines at their usual amount. …            │
└───────────────────────────────────────────────────────────────────────────┘
```

The "Contract / Starts / Contract category / Trial period" card stays exactly as today, **below** the Pay Builder.
The "Paid by" card stays exactly as today, above it.

### 4.1 Card A — What you agree

- **Headline input** (required). Label = the name of the scheme's *main pay* line (handover §"Main pay"): "Monthly wage"
  for a scheme that starts from the contract wage; the component's own name (e.g. "Annual fixed pay") otherwise. Suffix
  `<CUR> a month` / `<CUR> a year` from the component's period. Same big input as today (`.pbnh-wage`).
- **Helper line** under it: `That is <amount> a year.` (monthly headline) / `That is <amount> a month before deductions.`
  (yearly headline) / empty state: `Needed before this person can be paid.`
- **Pay band chip and pay-scale line**: unchanged from today, shown under the helper line, when the headline is the
  contract wage. Hidden (not faked) when the headline is another component.
- **Work back from take-home** (link, right of the helper line) → §7.
- **Also asked by this pay scheme** (right half): every other per-person line that is not a monthly earning or
  deduction — yearly amounts, counts, yes/no and choices (today's "usual answers" live here and in Card B, never in a
  separate card). Controls by kind: money → small money input; count/quantity/rate → small number input; yes/no →
  toggle; choice → select. Each row: name, one grey hint line (`Usual answer: Yes` / the component's help text), control.
  If the scheme asks nothing else, the right half is not rendered and the headline takes the full width.
- Step is complete when the headline is > 0 **and** the server could work the month out (or refused for a reason that
  does not block — §6).

### 4.2 Card B — A month's pay, worked out

Header: title `A month's pay, worked out`; sub `By <scheme name>, for a full <Month YYYY>.`; legend of the three kinds
(right, wraps under on narrow widths).

Three sections in this order, each with a small uppercase label and a bold total row:

| Section | Lines | Total row |
|---|---|---|
| `Earnings` | lines counted as earnings | `Gross pay` |
| `Deductions` | lines taken off the person's pay | `Total deductions` |
| `Paid by the company on top` | company contributions | `On top of gross pay` |

A section with no lines is not rendered. Lines keep the scheme's own order. Lines that are "already inside another
total" (detail lines) are shown indented one step under the line they belong to, in muted ink, and never counted twice.

#### The three kinds of line

| Kind | Icon (Lucide) · tile colour | Sub-label | Amount cell | Behaviour |
|---|---|---|---|---|
| **You set** | `pencil` · soft indigo | `You set` + chip | money input | Editable. Saved on the contract. |
| **Worked out** | `calculator` · soft teal | `Worked out` | plain amount + chevron | Whole row is a button; opens the explainer (§5). Never editable. |
| **Each month** | `calendar` · soft amber | `Each month, from <source>` + `Try an amount` | muted amount, dotted underline | Shown at its usual amount. `Try an amount` swaps in an input; chip `Example only, not saved`; link `Remove`. Never saved. |

`<source>` is one of: `the pay data file`, `the connected system`, `the timesheet`, `the leave record` — whatever the
scheme declares; if nothing is declared: `Each month`.

Chips on a **You set** line:
- untouched and usual amount > 0 → teal chip `✦ Usual amount`
- changed → amber chip `Changed` + link `Back to usual <amount>`
- untouched and usual amount 0 → no chip.

**"Also in this scheme" bar** (end of a section): You-set lines whose usual amount is 0 and that HR has not touched are
*not* rows; they are dashed chips `+ <name>`. Clicking one turns it into a row with the input focused and selected.
Setting it back to 0 with `Back to usual` returns it to the bar. This keeps a 14-allowance scheme readable.
Zero **Each month** lines stay visible (they explain why tax is 0 in the example). Zero **Worked out** lines are hidden
behind one quiet link at the end of the section: `Show <n> lines at zero` / `Hide lines at zero`.

#### The foot (take-home bar)

- Split bar, 10 px, three flat segments: take-home (green `--pbnh-ok`), deductions (rose `#E08AA8`), company on top
  (`--pbnh-p-light`). Widths animate.
- Four figures: **Take-home** (largest, green), Gross pay, Deductions, Cost to the company. Under each: `<amount> a year`.
- If the scheme has no take-home line: the Take-home tile reads `—` with the sub `This pay scheme has no take-home line.`
- Note line (info icon): `A full month, with each-month lines at their usual amount. <First name> starts on <d Month>, so the first pay may be less.`
  (second sentence only when the first day is not the 1st). Every note today's payslip example returns is shown here too.

## 5. "How this is worked out" — the explainer

Opens inline under a Worked-out row (row gets a soft background and a 1 px inset border; chevron rotates). Several can
be open at once. Enter/Space toggles; Escape closes the focused one. Contents, top to bottom:

1. **One sentence in plain words.** e.g. `Half of the annual fixed pay, spread over 12 months.` Built on the server from
   the formula (handover §"Explain"), never the raw formula text.
2. **The sum with this person's numbers**, as chips:
   - a line it uses → white chip button `<name> <amount>`; click scrolls to and flashes that row (focuses its input if it
     is a You-set line);
   - a fixed rate or ceiling → grey chip with a lock icon `<name> <value>`, tooltip `Set by the pay scheme`;
   - operators as glyphs `× ÷ + −`, words for functions: `the smaller of … and …`, `the larger of … and …`,
     `rounded`, `if … then … otherwise …`, `the total of <first> to <last>` (a range shows its count: `the total of 14 lines`
     with the lines listed as chips when ≤ 8, otherwise `Show the 14 lines`).
3. **Result:** `= <amount> a month` in teal display type.
4. **Stepped sums** (a formula that is a ladder of bands, e.g. income tax): a small table, one row per step
   `<from> to <to> at <rate>% | <part taxed> | <tax>`; steps that apply are tinted teal, steps above are muted.
   Only when the server recognises a ladder; otherwise the generic chips are shown.
5. **Lock line:** lock icon + `This sum belongs to <scheme name>, so it cannot be changed for one person.` +, only for
   people who may edit pay schemes, link `See it in Formula Studio` (opens the scheme at that component).
6. If the formula is too long to read as chips (more than 14 chips): sentence + `It uses: <chips of the lines>` + the
   result. Never a wall of symbols.
7. If the formula failed: amber row, sub-label `Could not be worked out`, explainer says the reason in words
   (`The formula for <name> divides by zero.`) and `Tell the person who looks after the pay scheme.` Totals that depend
   on it show `—`; the step is not blocked (the wage is still valid), but the step rail reads `Pay typed · check the scheme`.

**Pointing (desktop):** hovering or focusing a Worked-out row tints every row it uses (soft indigo fill + 3 px indigo
inset on the left). Leaves on mouse-out/blur.

## 6. States — every one is designed

| State | What shows |
|---|---|
| **No team / no country yet** | Today's "They decide the pay scheme…" card, unchanged. No builder. |
| **No pay scheme found** | Today's amber fix card, unchanged. Headline input still shown (wage can be typed); Card B: `No pay scheme pays this person yet, so the month cannot be worked out. <fix sentence from today's card>`. |
| **Waiting for the number** | Card A as normal. Card B body: centred `Type the <headline name> to see the month work out` / `Basic, allowances, deductions and take-home appear here the moment there is a number.` Foot figures `—`, bar empty. |
| **Working** (first answer) | Card B body: 5 skeleton rows (shimmer off under reduced motion). |
| **Refreshing** (typing) | Rows stay; amounts dim to 55 % until the answer lands, then tween. A 2 px indigo progress hairline under the card header if the answer takes > 400 ms. Never a spinner over the block. Inputs are never disabled or re-rendered while typing. |
| **Worked out** | §4. |
| **A line failed** | §5.7. |
| **The whole month failed** | Card B body: amber card with the server's reason sentence and `Try again`. Headline keeps its value. |
| **Scheme with nothing but a wage** | Card B shows the wage line(s) and take-home; no "Also asked" column; no "Also in this scheme" bar. |
| **Huge scheme** (> 40 visible lines) | Sections stay; each section shows its first 12 lines then `Show all <n> lines`. |
| **At the plan's employee limit** | Whatever today's example refuses with, said once in Card B's body, with today's fix sentence. |
| **Read-only viewer** (may not write contracts) | Inputs render as plain amounts; chips and links that change things are not rendered. |
| **Came from a Hiring offer** | Card A sub-line: teal chip `✦ From the signed offer` on every value that travelled; `Back to usual` still works. |

Nothing ever says "error" alone, shows a code, or leaves a blank card.

## 7. Work back from take-home

- Link `Work back from take-home` under the headline. Opens an indigo-soft strip inside Card A:
  target icon · `Take-home wanted each month` · small money input · solid small button `Find the pay`.
- On success: the headline is filled, every line animates, and the strip says
  `<headline amount> a year|a month gives a take-home of <net> a month. It is in the box above; change it if you like.`
- The answer is the **smallest headline, rounded up to the currency's sensible step, whose take-home is at least the
  target** (so the person is never short). Other You-set lines and what-if amounts are kept as typed.
- Refusals in words: `Type the take-home you want first.` · `This pay scheme has no take-home line, so it cannot be worked
  back.` · `No pay gives that take-home on this scheme. The closest is <amount>.` · `Working back took too long. Type the
  pay and adjust it instead.`
- Link text becomes `Close` while open. Not shown in read-only homes or when the scheme has no take-home line.

## 8. The four homes

| Home | Variant | Differences |
|---|---|---|
| **Add employee · step 3** | full | As §4–§7. Replaces two cards. Right column untouched (D6); its payslip example must show the same gross, deductions and take-home as the foot. Step rail sub-line: `Take-home <amount> a month` when worked out, `Pay needed` when empty (today's `Wage needed` wording may stay if the lessons quote it — see handover). |
| **Hiring · offer** | slim (foot 2×2) | Same block in the offer panel where the offer's pay is typed. Below it: toggle `Show the pay table in the offer letter` (on by default) and a live letter preview: earnings lines > 0, bold `Gross pay`, and `Take-home after the usual deductions is about <amount> a month.` When the candidate accepts, every typed value arrives in step 3 with the `From the signed offer` chip. |
| **Contract panel · Change pay** | compare (slim) | Opened by a `Change pay` button in the contract slide-over's pay section. Fields above the block: `New pay starts from` (date) and `Reason` (Yearly review / Promotion / Correction / Other). Each row gains a struck-through "was" amount when it changes; foot tiles show `+<amount> a month` chips (green when the person gains, rose when they lose; for Deductions and Cost to the company the colours flip). Note: `A full month before and after. The month the change starts may mix both.` Primary button `Send for approval` (or `Save` where no route exists). |
| **Joining page (new person, phone)** | read | Card `Your pay`, sub `A full month, as agreed. Tap a line to see how it is worked out.` No Card A, no inputs, no "Paid by the company" section, no Cost tile, no Formula Studio link. Sub-labels: `As agreed` / `Tap to see how` / `Changes each month`. Shown only when HR's hire is approved and the tenant allows the person to see pay before day one (handover decides the switch; default on). |

## 9. Formula Studio — the plainer switch (D4)

In the component editor, the tick box labelled "Contract Component" becomes a two-way choice shown only for lines with
no formula:

> **Where does this amount come from?**
> ( ) **The same for this person every month** — HR types it when hiring or changing pay. Kept on the person's contract.
> ( ) **It changes each month** — it arrives with the pay data file, the connected system or the timesheet.

Under the first choice the existing field `Usual answer for a new contract` keeps its place and its help text. Lines with
a formula show neither; they show a grey line `Worked out by its formula — nobody types it.` The stored value is the
same field as before; no data moves. The same wording is used wherever else that tick box is shown to a user.

## 10. Motion

| What | How |
|---|---|
| A number changes | Tween 320 ms ease-out-cubic from old to new; the row flashes soft green fading over 1 s. |
| Split bar | Segment widths transition 450 ms. |
| Explainer opens | Rise 4 px + fade, 200 ms; chevron rotates 180°. |
| Chip → row ("Also in this scheme") | Row rises in, input focused and selected. |
| Jump from a chip in a sum | Smooth scroll to nearest, target row flashes. |
| `prefers-reduced-motion` | No tweens, no flashes, no smooth scroll: values switch at once. |

No decorative motion anywhere.

## 11. Keyboard and access

- Tab order: headline → Work back → "Also asked" controls → each row top to bottom (inputs and worked-out row buttons)
  → "Also in this scheme" chips → next section. Ctrl+Enter still goes to the next step.
- Every input has a label (`aria-label` = the line's name); worked-out rows are `<button aria-expanded>`; toggles carry
  `aria-pressed`; the foot is a `role="status"` live region that announces `Take-home <amount> a month` once per settled
  answer (not on every tween frame).
- Money inputs: digits only, grouped as typed, caret kept at the end; pasting `1,200,000` or `12 00 000` works; Arrow
  Up/Down nudges by the currency step, Shift for ×10.
- Focus ring: 2 px `--pbnh-p`, offset 2 px (as the rest of the studio).

## 12. Styling — tokens and measures

Reuse the studio's tokens (`.pbim.pbnh` in `pb_new_hire/static/src/scss/new_hire_studio.scss`); add **no new colours**
except the rose split segment. New classes are prefixed `pbpb-` (the block is shared by four homes, so it must not
depend on a `.pbnh` ancestor: it declares the same token names itself with the same fallbacks).

| Token | Value | Use |
|---|---|---|
| `--pbnh-p` / `-p-h` / `-p-soft` / `-p-light` / `-p-dark` | `#5A4BB0` / `#4A3D96` / `#EDEAF8` / `#CBC2EE` / `#241F52` | primary, You-set tile, source highlight, work-back strip |
| `--pbnh-teal` / `-teal-soft` | `#0F8B8D` / `#E0F2F2` | Worked-out tile, result figure, usual chip |
| `--pbnh-warn` / `-warn-soft` | `#B45309` / `#FDF1DD` | Each-month tile, Changed chip, failed line |
| `--pbnh-ok` / `-ok-soft` | `#2E7D4F` / `#E4F3EA` | take-home, flash, gain chip |
| `--pbnh-err` / `-err-soft` | `#DC2668` / `#FCE7EF` | loss chip, required star |
| `--pbnh-line` / `-line2` / `-soft` / `-faint` / `-muted` | `#E2E8F0` / `#EEF0F6` / `#FAFAFD` / `#94A0B4` / `#64748B` | borders, tracks, open row, labels |
| split "deductions" | `#E08AA8` | split bar + its dot only |

| Element | Measure |
|---|---|
| Cards | radius 14 px, 1 px `--pbnh-line`, white; padding 16 × 18 |
| Card A grid | `minmax(0,1.1fr) minmax(0,1fr)`, gap 18 × 26; one column under 620 px |
| Headline input | as today's `.pbnh-wage`: 1.5 px border, radius 12, Manrope 800 26 px, symbol Manrope 700 18 px |
| Small money input | radius 9, padding 5 × 9, 104 px field (52 px for counts), right-aligned, 14 px/600, tabular |
| Row | grid `26px minmax(0,1fr) auto 18px`, gap 10, padding 7 × 10, radius 10, 8 px side margin inside the card; compare variant adds a 96 px "was" column |
| Kind tile | 26 × 26, radius 8, 14 px icon |
| Name / sub-label | 13.5 px/600 · 12 px muted |
| Amount | 14 px/600 tabular, min-width 104 px (84 px under 620 px) |
| Section label | 11 px/600 uppercase, letter-spacing .08em, `--pbnh-faint` |
| Total row | 13 px/700, padding 8 × 18 × 10 |
| Explainer | padding 2 × 14 × 14 × 46 (14 left under 620 px); sentence 13.5 px, max 64ch; chips radius 9, padding 4 × 9, 12.5 px; result Manrope 800 15 px teal |
| Foot | top border, `--pbnh-soft`, padding 14 × 18; figures Manrope 800 18 px (take-home 24 px green); `a year` line 12 px faint; 4 columns → 2 under 620 px and in slim/read variants |
| Chips | radius 99, padding 2 × 9, 11.5 px/600 |

Typography: Manrope (display) and Inter (body), as the studio. Icons: Lucide through the studio's icon helper; add any
missing glyph (`calculator`, `target`, `lock`) to that helper — never an emoji or an image.

## 13. What is deliberately NOT in this build

- Editing a formula, a rate or a ceiling from the Pay Builder (Formula Studio only).
- Saving a what-if amount for an Each-month line.
- Part-month (pro-rata) examples: always a full month, with the honest note.
- Working back from cost-to-company or from gross (take-home only).
- Two pay schemes at once for one person (mid-month advance): the builder shows the main scheme.
- Restyling the right column of Add employee (D6) or any other part of steps 1, 2, 4–7.
- Back-filling existing contracts when a line is switched to "the same every month" (nothing changes until HR types).
- 7/30/60/90-day check-ins, pay-scale editing, pay-band editing.
