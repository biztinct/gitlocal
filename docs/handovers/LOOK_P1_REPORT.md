# LOOK P1 — "Open this band out" — phase report

**Status: COMPLETE.** `pb_pay` **19.0.3.2.0** live on p9clone, payobook, abm and
payobook_template. Module tree verified byte-identical to the repository on the server
(`b5fab614e7833b8613991ab18f2302e84b953103e2e2444f8951adc653e1c7ab` both sides), and
`ir_module_module.latest_version` reads `19.0.3.2.0` on all four databases.

Scope kept: **`pb_pay` only, browser only.** No model change, no schema change, no
migration, no new server method. Every number the phase needs was already in the payload
`pb.pay.bands.get_board` hands over.

---

## 1. The hero moment

**A band that was an unreadable smear unrolls under the cursor into a picture with real
people in it, and a hairline above it shows exactly which slice of the company's pay you
are now looking at — no dialog, no new screen, no click required to see it.**

Measured on the owner's own band, "Construction · level 2 · Vietnam", 544 people:

| | closed | opened |
|---|---|---|
| Width of the band on the track | **37 px of 1,053 — 3.49%** | **746 px — 70.83%** |
| Marks drawn | 9 | **67** |
| People drawn | 544 | 544 |
| Marks whose boxes intersect | 0 | 0 |
| Ruler under the track | — | 5.9M · 7.6M · 9.3M · 11.0M · 12.7M ₫ |
| Locator on the shared axis | — | 4.36% → 9.28% of a 136M ₫ ruler |

Screenshot: `look_p1_shots/08_p9clone_hero_opened.png` (and `01_…` / `02_…` for the
before-and-after pair).

## 2. Self-score against the design bar

> **extreme WOW, intuitive, out-of-this-world experience, best in class.**

**8.5 / 10.** What earns it:

- The hero is genuinely a "stop and look" moment: three columns become sixty-seven
  people, in place, on hover, with no click.
- **Zero dead-ends, all designed and all proven live**: nobody on the band ("Nobody is on
  this band yet."), one person, everybody on very nearly the same wage, one ten-times
  outlier, a span too narrow for rounded money, a band with no grips, a touch screen with
  no hover, a reader who asked for no motion, and a keyboard with no mouse.
- **No wall anywhere.** A drag can always travel past the end of the picture, and the
  ruler recomputes on release.
- **Honesty rails**: the ruler refuses to print the same label twice; the picture never
  drops a person (544 both states); both tails are counted; the row says out loud that
  its width no longer compares with its neighbours.
- Full keyboard parity, Lucide icons only, plain language throughout, Vietnamese
  complete.

What holds it back from 10:

- The row's re-scale at the moment a drag starts is still a visible change to everything
  except the grip under the hand. It is anchored so nothing moves under the cursor and no
  stored number changes, but a reader will see the other grip and the marks shift.
- On a 390 px screen the median label and the two edge figures still print over the marks
  — pre-existing at that width, and not widened by this phase.
- The `pbim` kit still has no dark palette (GR38), so "dark" remains the platform's
  chrome only.

## 3. The numbered tests

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | `node band_picture_check.mjs` passes, old cases migrated, new cases added | **PASS** | 13 checks → **34 checks passed**, exit 0. New: T3h a mark on an axis that starts above zero (bin `496–504 px`, dot at exactly 50%, bin money reads back), the same person drawn at 56 px on the lane and 496 px on the band's own; T3i the guarded span (5, and 1 for zero/negative/missing/nonsense); T3j 400 random bands, the band's own edges always inside its own axis; T3k a 10× outlier moves the axis by < 1 ₫ and is counted (`above: 1`); T3l both tails counted (2 below, 3 above) with all 105 people still binned; T3m all-identical / one person / nobody / all-zero / no arguments / rubbish, `max > min` and `min ≥ 0` in every case; T3n the same band twice in either order; T3o the drag's headroom widens both ends and still contains the band. Also run inside the Python suite (`test_tidy_t3…`). |
| 2 | The band actually opens | **PASS** | 3.49% → **70.83%** of the track. `01_p9clone_bands.png` (closed), `08_p9clone_hero_opened.png` (open). |
| 3 | Counts are conserved | **PASS** | "Construction · level 2 · Vietnam": **544 drawn closed and 544 drawn open**, summed from every mark's own label; the chips read **"57 below" / "82 above" in both states**. Same figures on p9clone and on payobook. |
| 4 | The drag is 1:1 under zoom | **PASS** | Hand moved +40/+80/+120/+150 px; grip moved +41/+81/+121/+151 px. Chip and foot bar agreed while the mouse was down ("221 below" · "2.6B ₫ a year to bring 221 people back in"). Saved 6.6M → **8.0M ₫**; **Undo restored 6.6M–11M and 57/82 exactly**. `05_p9clone_drag_under_zoom.png`. |
| 5 | No invisible wall | **PASS** | The highest edge was dragged to the far right and past it: 11M → **13.4M ₫**, beyond the 12.7M end the picture showed before the press. On release the ruler recomputed to 5.9M–13.8M and the right-hand tail sentence disappeared because nobody was outside any more. Undone afterwards. |
| 6 | Keyboard only | **PASS** | Focus "Open out" → `aria-expanded="false"`; Enter opens (`"true"`, ruler appears); Tab to a grip; `→` moves the grip **10 px = 1% of the drawn span** (1% of the shared axis would have been 13× coarser); `Shift+→` moves it **53 px = 5%**; Enter saved 11M → 12M ₫; Undo restored it; Escape closed the band. |
| 7 | Fit-to-family interaction | **PASS** | Lane 3.49% → fitted **11.75%** → opened **70.83%** → closed back to **11.75%**, the FAMILY axis (R5). The two sentences do not both claim to be the reason: the family says "…so its widths no longer compare with the other **families**", and a band opened inside a fitted family says "…**narrower than this family's**, so its width no longer compares with the other **bands**." |
| 8 | Dense rows | **PASS** | 3 ticks not 5 (5.9M · 9.3M · 12.7M ₫), **0 overlapping ticks**, 544 still drawn over 67 marks, **0 intersecting marks**. `04_p9clone_dense_opened.png`. |
| 9 | A suggested band | **PASS** | On a scope with no saved bands (payobook, and p9clone before the rehearsal) the band unrolls, carries **0 grips**, and pressing a mark still opens the people popover with real names. `03_p9clone_suggested_popover.png`, `13_payobook_opened.png`. |
| 10 | Thin data | **PASS** | **Nobody**: a constructed empty band opens, draws its range on its own scale (19.4M–30.6M ₫) and says "Nobody is on this band yet." (`09_…`). **One person**: abm "Data & Analysis · level 5", 0.94% closed → **89.29%** open, one dot, ruler 22.0M–27.5M. **Everybody on the same wage**: abm "Logistics · level 2", 14 people, **0.48% closed** → 89.29% open, 14 named dots, none overlapping (`14_abm_named_dots_opened.png`); the exactly-zero-span case is proven under node (T3m). **One huge outlier**: a contract raised to ₫700M inside a 42-person band — the axis stayed at 45.0M–75.6M and the sentence read "**1 person** is paid more than 75.6M ₫ and sits on the right-hand edge" (`11_…`). All fixtures reverted. |
| 11 | Ruler honesty | **PASS** | A constructed band 6.60M–6.68M ₫, whose own header prints "6.6M ₫ to 6.7M ₫", draws a ruler of **five distinct labels: 6.595M · 6.618M · 6.640M · 6.662M · 6.685M ₫** where one-decimal formatting would have printed "6.6M" five times. `10_p9clone_narrow_span_ruler.png`. It also fires on real production data: abm's 14-person Logistics band prints two decimals (11.10M … 13.90M ₫). |
| 12 | Reduced motion | **PASS (by the R85 proof)** | `prefers-reduced-motion` cannot be emulated through Chrome MCP, so the stronger proof was used: the deployed bundle was fetched and read back. **Every moving declaration this phase added — the 260 ms travel on `.pay-track.is-zooming`, the row's padding transition, the locator's travel and the tray's entry — sits inside `@media (prefers-reduced-motion: no-preference)`**, so under a reduced-motion preference none of them is applied at all and the opened row arrives finished on the first frame with nothing to recover from. |
| 13 | Coarse pointer | **PASS** | With `390x844x3,mobile,touch` emulated, `(hover: hover) and (pointer: fine)` reports **false**, a `mouseenter` held for 600 ms opens nothing, and the button is the only door. `06_…`, `07_p9clone_phone_opened_fixed.png`. |
| 14 | Nothing regressed | **PASS** | **`pb_pay`: 111 tests, 0 failed, 0 errors** on p9clone (the same 111 the TIDY P2 entry recorded). The wider run over **248 tests** (`pb_pay` 111, `pb_group` 54, `pb_contracts` 48, `pb_hub` 34, `pb_budget` 39) reports **3 failures and 0 errors**, and all three are the p9clone data drift this ledger has recorded since GROUP P6a: `pb_contracts::test_22_the_picker_is_whitelisted`, `pb_contracts::test_05_the_picker_is_whitelisted_and_answers`, `pb_group::test_t9_the_screen_counts_what_the_roster_counts_and_is_quick`. **That is the baseline. Zero regressions.** |
| 15 | Vietnamese | **PASS** | Every new string translated and walked live: **"Mở rộng ra" / "Trở lại thang đo chung"**, the hint, the warning sentence, both tail sentences, the locator tooltip and the mark labels ("12 người · từ 8.952triệu ₫ đến 9.003triệu ₫ · trong khoảng lương"). `15_p9clone_vietnamese_opened.png`. Catalogue: **780 of 780 terms**, 0 English survivors, 0 fuzzy entries, 0 lost placeholders, 0 entries missing their `#. module:` comment, the word "Odoo" in no translation, and the freshly exported `.pot` header rewritten to `Payobook 19.0` (WF27). |

## 4. Rulings I had to bend, and why

**R2 — hover, with one refinement.** The spec says hover opens a row. It does, after
180 ms, closing 140 ms after leaving, behind `(hover: hover) and (pointer: fine)` — all
verified live. The refinement: **hover does not steal a band somebody has PINNED.** A
pinned row means "I am working on this one", and letting a cursor crossing another row
take it away would be a worse screen than the one the ruling describes. "One band is open
at a time" is unchanged.

**R4 — the row grows downward, but the growth is not a `padding-bottom` transition.**
The spec says the open row gains a fixed animated `padding-bottom` for the ruler. The
first build did exactly that, and the phone walk showed it printing the tail sentence
over the next band's name at 390 px — a fixed height cannot hold a sentence whose length
depends on the reader's language and screen. The ruler and the sentence now sit **below
the track in normal flow**, so the row grows by exactly what it has to say on any screen,
and they **ease in on the same 260 ms curve as the unroll** (`pay-tray-in`, inside the
reduced-motion guard) so it still reads as one motion. Everything else about R4 holds:
the row grows downward, one at a time, nothing floats, nothing overlays, no panel opens,
and the cursor stays on the track at the top of what grows. Screenshot pair
`06_…` (the fault) and `07_…` (the fix).

**§2e — the drag's frozen axis is ANCHORED, which the spec did not ask for.** The spec
says the drag axis is computed at drag start with 30% headroom and frozen. Built exactly
that way, the first live drag showed the fault the spec itself warns about: the grip
jumped from x=422 to x=571 at the moment of the press while the cursor stayed at 422 —
the grip running away from the hand. The drag axis now takes its 30% headroom and is then
POSITIONED so the grabbed edge keeps the fraction of the track it already had, and the
gesture moves the edge by how far the hand moves rather than to wherever the cursor sits.
Measured after the change: **the grip stays at 422 under a cursor at 422**, and moving
the hand 150 px moves it 151 px. Both of the spec's stated reasons are honoured and the
side effect it warned about is gone.

Nothing else was bent. R1, R3, R5 and R6 are as written and are each proven above.

## 5. Where the handover was wrong about the code

Three things, all small and all found by building against them:

1. **`t-att-aria-expanded="isOpen(band)"` renders nothing when the value is `false`.**
   §2g asks for a real `<button>` carrying `aria-expanded`; OWL omits an attribute whose
   value is boolean `false`, so a closed disclosure had no `aria-expanded` at all. It is
   written `isOpen(band) ? 'true' : 'false'`.
2. **`_lane_axis`'s "%(count)s people are paid more than…" sentence already existed in
   the catalogue**, so only ten of the eleven new strings were new terms — the right-hand
   plural tail is shared with the server's own lane note. (And the left-hand plural, the
   two singulars and the rest are new.)
3. **The bin labels needed the same honesty rule as the ruler, which §2d did not ask
   for.** Under zoom a bin is about fifty thousand dong wide, and `shortMoney`'s one
   decimal at millions printed "12 people · 9.0M ₫ to 9.0M ₫". A picture built to stop a
   ruler lying cannot leave its own marks lying, so a mark takes its figures from the
   bin's own width and now reads "8.952M ₫ to 9.003M ₫".

Two pre-existing faults were seen while walking and deliberately NOT fixed (they are
server-side and outside this phase's scope — recorded as owner debts in §8):

- the lane axis's own note prints **"1 people are paid more than 136M ₫"** — GR42's
  missing-plural trap, in `pb_pay_bands.py::_lane_axis`. This phase's own tail sentences
  branch correctly and say "1 person".
- releasing a drag that the server REFUSES still shows the undo bar reading "Band moved."
  above the refusal sentence. `move_edge` is untouched by this phase.

## 6. The four databases

| Database | `pb_pay` version | Bands | Families | Job links | Tree hash |
|---|---|---|---|---|---|
| p9clone | 19.0.3.2.0 | 0 | 0 | 0 | `b5fab614…c7ab` |
| payobook | 19.0.3.2.0 | 0 | 0 | 0 | `b5fab614…c7ab` |
| abm | 19.0.3.2.0 | 0 | 0 | 0 | `b5fab614…c7ab` |
| payobook_template | 19.0.3.2.0 | 0 | 0 | 0 | `b5fab614…c7ab` |

One tree, one hash, verified against the repository over every file except
`__pycache__`, `*.pyc` and `.DS_Store`.

`pg_dump` before every database: `/odoo/backups/p9clone_before_look_p1_20260908_213246.dump`,
`payobook_before_look_p1_20260908_213455.dump`, `abm_before_look_p1_20260908_213455.dump`,
`payobook_template_before_look_p1_20260908_213455.dump`.

**Nothing was written to production.** The p9clone rehearsal — 21 accepted bands, 11
families, 30 job links, two constructed thin-data bands and one contract temporarily
raised to ₫700M — was undone and deleted afterwards and verified gone (the contract is
back at ₫74,800,000; 0 bands, 0 families, 0 job links on all four databases). payobook
and abm still open on the suggestion, exactly as they did before this phase.

Asset ritual, run on every database: `/web/assets/%` attachments purged **and** the
`web.assets.version` `ir.config_parameter` bumped, then a service restart — four times
over the phase, once per deploy.

## 7. Commits (NOT pushed)

| Commit | What |
|---|---|
| `2be2f3e2` | `feat(pb_pay): an axis has two ends, and a band can be given its own` — `static/src/js/band_picture.js`, `tools/band_picture_check.mjs` |
| `10746b8f` | `feat(pb_pay): open a band out onto its own money scale` — `static/src/js/pay_hub.js`, `static/src/xml/pay.xml`, `static/src/scss/pay.scss`, `__manifest__.py`, `i18n/pb_pay.pot`, `i18n/vi_VN.po` |

Explicit `git add` of named files both times. **Not pushed** — there are now ~106
unpushed commits on `19.1` and pushing is the owner's decision.

## 8. What the owner has to decide

1. **Push, or keep holding.** ~106 commits sit unpushed on `19.1`.
2. **The `payobook` administrator password in the ledger is still wrong (GR24), and so is
   `abm`'s (WF15).** This phase used one temporary `look.p1@payobook.com` on p9clone
   (id 4338), payobook (id 4427) and abm (id 262), **all three archived again at the end
   of the phase**. Resetting the owner's own password is an owner decision and was not
   done.
3. **"1 people are paid more than 136M ₫"** on the shared axis note is a one-line
   server-side fix in `pb_pay_bands.py::_lane_axis` (GR42's shape). It is outside this
   phase's browser-only scope; say the word and it goes in the next one.
4. **A refused band move still says "Band moved."** above the refusal. Also server-side
   and pre-existing.
5. **The `pbim` kit has no dark palette (GR38)**, so nothing in this product genuinely
   re-tints for a dark reader. Still a `pb_import_kit` release of its own.
