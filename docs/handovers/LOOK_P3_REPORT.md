# LOOK P3 — "A stretch of months" — phase report

**Status: COMPLETE.** `pb_budget` **19.0.2.2.0** live on p9clone, payobook, abm and
payobook_template. Module tree verified byte-identical to the repository on the server
(`32199e6c666aaaa56d60444e32ea889f37496cdccc884beb9fe93369691d4dad` both sides) and
`ir_module_module.latest_version` reads `19.0.2.2.0` on all four databases.

Scope kept: **`pb_budget` only** — server and browser. No schema change, no migration, no
new model, no new field on a stored model. No other module touched.

---

## 1. The hero moment

**The reader sweeps four chips and the whole board — every number, every word, every
colour, the headline sentence, the drill, the table and both exports — becomes about
those four months under their hand, with the chips beneath the cursor fusing into one
band as they go.**

Measured on the demo company's own 2026 People budget, twelve functions:

| | whole year | March to June |
|---|---|---|
| Headline | 83% of the 2026 budget is spent and the year is 67% gone — spending is running ahead of the calendar. | March to June: 5 of 7 functions went over budget; Information Technology by the most (192.8bn VND, 122% over). |
| The five numbers | 2.0tn · 1.7tn · 348.5bn · 83% vs 67% · 4 warm-or-worse | 673.4bn · 1.5tn · −860.9bn · +128% · 5 over budget |
| Their captions | budget for the year / spent so far / left | budget for March to June / spent in March to June / left in March to June |
| Retail's word | Ahead of the year | Over budget |
| Retail's fill | 88% spent of the budget | 200% spent of the budget for these months |
| The chips | thirteen separate buttons | ONE band: `10px 0 0 10px` · `0` · `0` · `0 10px 10px 0` |
| The tiles | 7, in this order | the SAME 7, in the SAME order, numbers travelled |

The sweep costs **one** server read, not four: the chips under the hand are painted from
the strip itself and the board is re-read once, on release.

Screenshots: `look_p3_shots/13_p9clone_hero_sweep_under_hand.png` (mid-sweep),
`02_p9clone_march_to_june.png` (committed), `01_p9clone_year_with_brackets.png` (before).

## 2. Self-score against the design bar

> **extreme WOW, intuitive, out-of-this-world experience, best in class.**

**8.5 / 10.** What earns it:

- The strip stopped being thirteen buttons and became a **range control**, and it did it
  without giving up the one thing that made it good: every chip still answers, before
  anything is pressed, whether that month ran over its budget.
- The **quarter brackets land on the pixel** over their own three chips (measured:
  `300–575 · 575–850 · 850–1124 · 1124–1399` against month groups
  `300–575 · 574–850 · 849–1124 · 1123–1399`), and each one says which three months it
  means — because on a July financial year "Q1" is a guess otherwise.
- **Zero dead-ends, every state in §2d designed and proven live**: a stretch with no
  budget anywhere in it, one wholly in the future, one straddling today, one where a
  function spent nothing (it keeps its tile and its place), a shift-press with no anchor,
  a sweep that ends off the strip, a deep link half outside the year, one wholly outside,
  a malformed one, an empty database, a phone, and a keyboard with no mouse.
- **Full keyboard parity**: arrows walk, Home/End jump, Shift extends from the anchor,
  and Escape's ladder gained a rung for a gesture in flight — all proven with the
  browser's own key presses (L16).
- Plain language everywhere, Lucide only, Vietnamese complete, no console error anywhere
  on three databases.

What holds it back from 10:

- Below 1180 px the brackets can no longer sit over their own three chips (the strip
  wraps to rows of six, then of three) so they become four ordinary chips above it. They
  still work; they stop being brackets.
- On a phone a chosen stretch that wraps across rows reads as two bands, because a
  wrapped band is two shapes. Honest, but not beautiful.
- The `pbim` kit still has no dark palette (GR38), so "dark" remains the platform's
  chrome only.

## 3. The numbered tests

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | **The parity proof (R3)** | **PASS** | See §4. 117 live payloads before and after: **0 values changed, 0 keys missing**. Shipped as `test_t1_the_refactor_moved_nothing`. |
| 2 | A quarter is three months and its totals equal those three read one at a time | **PASS** | `test_t2_…`: Q1's budget and spend equal the sum of January, February and March read separately; the four quarters together are exactly the twelve months and do not overlap; `get_board('Q1')` is byte-identical to `get_board('2032-01..2032-03')`. Live on p9clone: Q2 = Apr+May+Jun, `scope.quarter = 'Q2'`. |
| 3 | Shift-press in each direction; a drag; a drag that leaves the strip | **PASS** | Shift-press March→June and June→March both give the same four months. A genuine pointer drag Feb→May committed February to May. A sweep July→October released **on the window, off the strip**, committed July to October. |
| 4 | **The collapse rules (R1)** | **PASS** | `test_t4_…` plus live: `Shift+End` from January extended across all twelve and the board came back as **the whole year** — the strip cleared, the "Whole year" chip took `aria-pressed="true"`, the headline became the year's. A stretch of one reports `kind: 'month'`; both payloads are byte-identical to the scope read directly. |
| 5 | **Fiscal-year quarters (R5)** | **PASS** | `pb_budget.fy_start_month = 7` on p9clone: the strip reads **Jul Aug Sep Oct Nov Dec Jan Feb Mar Apr May Jun**, the year chip reads **2026/27**, Q1 is **July to September**, Q3 is **January to March** (2027), and the scope line reads "Every figure on this board is **Q1 2026/27 · July to September**." `10_p9clone_july_fiscal_year_q1.png`. Parameter reverted and the row removed. |
| 6 | **Pace** | **PASS** | `test_t6_…`: over each of the twelve months `_period_pace` equals `_month_pace` **to the decimal**; a stretch wholly past = 100.0, wholly future = 0.0, and April–September on 11 June = the elapsed share of its 183 days. Live: "July to October so far: 20% of the budget for those months spent, with **57%** of them gone." |
| 7 | **Deep links (R6)** | **PASS** | Live, through the real action service: `month:2026-03` → March · `month:current` → September · `month:2026-03..2026-06` → four months · `month:Q2` → Apr–Jun · `month:2025-11..2026-03` (half outside) → **clamped** to Jan–Mar · `month:2029-01..2029-06` (wholly outside) → the whole year · `month:rubbish` → the whole year. **Seven tiles on every one of them, no error, no blank board.** And the ⌘K row **"Budget this month"** still works: typed into the palette, Enter, and the board opened on September 2026 with its original sentence unchanged. |
| 8 | **Exports** | **PASS** | Live on p9clone: `Budget March to June 2026 People.xlsx` (64 ms) and `.pdf` (1.3 s), both downloaded from the buttons with their toasts. Server-side, four scopes checked: the sheet's total equals the screen's to the digit every time (`1,534,454,819,545` for Mar–Jun and for Q2 — March spent nothing, so they are genuinely equal; `525,699,056,538` for June; `1,666,439,945,499` for the year). A period's sheet carries **7** columns and the year's **32**. Tabs: `Budget March to June 2026`, `Budget Q2 2026 · April to June`, `Budget June 2026`, `Budget 2026`. The printed page names the stretch and draws all twelve months with those in bold. |
| 9 | **Keyboard only** | **PASS** | Every key a real browser press. `→` April → May; `Shift+→` ×2 → May to July; `Shift+←` → May to June; `Home` → January; `Shift+End` → the whole year (collapsed). Escape's ladder proven in order: a **gesture in flight** first (the preview vanished and the release afterwards did nothing), then the drill, then the period. |
| 10 | **T23 does not come back** | **PASS** | Scope on **December**, keyboard standing on **April**, `→` went to **May** — not to January and not to anything derived from the scope. The chip kept focus (`document.activeElement` still the strip), and `.bdg-mchip[disabled]` counted **0** at every moment. |
| 11 | **Every state in §2d** | **PASS** | No budget anywhere in the stretch: "February to May has no budget set; 0 VND was spent." (abm, `09_…`). Wholly future and empty: "January to June has not started." Straddling today: "August to October so far: 9% of the budget for those months spent, with 42% of them gone." A function that spent nothing keeps its tile and its place (`test_t11b_…` asserts the id ORDER is identical to the year's). Shift-press with no anchor = a plain press. A sweep ending off the strip commits. Truncation still flags under a range (`truncated: 1`). An empty database answers every shape with a sentence, never a blank. |
| 12 | **Vietnamese** | **PASS** | 299 terms, **0 untranslated, 0 fuzzy, 0 lost placeholders, 0 entries without their `#. module:` comment, the vendor's name in no translation and no `.pot` header**. Walked live: "Tháng 3 đến Tháng 6: 5 trên 7 bộ phận vượt ngân sách…", brackets "Q1 · Tháng 1 đến Tháng 3", the hint "Bấm một tháng, giữ Shift và bấm tháng khác, hoặc kéo qua nhiều tháng.", "Q3 2026 đến nay: đã chi 26% ngân sách của những tháng đó, khi 76% thời gian đã trôi qua." Month names from babel. `07_…`. |
| 13 | **Reduced motion** | **PASS (by the R85 proof)** | `prefers-reduced-motion` cannot be emulated through Chrome MCP, so the deployed bundle was fetched and read back. **14 declarations in this module move; 12 are inside `@media (prefers-reduced-motion: no-preference)` and both of the two this phase added are among them** (`.bdg-mchip { transition: … border-radius .18s … }` and `.bdg-qbr { transition: … }`). The two unguarded ones are the same rule twice — `.bdg-chip { transition: .14s }` on the budget-TYPE chips, present at line 163 of the file this phase inherited and untouched by it (L18). |
| 14 | **Nothing regressed** | **PASS** | **274 tests on p9clone, 3 failed, 0 errors.** The three are exactly the p9clone data drift this ledger has recorded since GROUP P6a: `pb_contracts::test_22_the_picker_is_whitelisted`, `pb_contracts::test_05_the_picker_is_whitelisted_and_answers`, `pb_group::test_t9_the_screen_counts_what_the_roster_counts_and_is_quick`. P2's baseline was 262 tests / 3 failures; this phase adds 12 (`pb_budget` 41 → 53 collected). **Zero regressions.** Per module: `pb_pay` 125, `pb_group` 54, `pb_budget` 53, `pb_contracts` 48, `pb_hub` 34. |
| 15 | **No literal per cent sign reaches a screen (L9)** | **PASS** | The rendered DOM: `document.body.innerText.includes('%%')` is **false** in English and in Vietnamese. The deployed 11.4 MB JavaScript bundle holds 15 `%%` in total and **not one of them is in `pb_budget`** (the only one anywhere near this subject is `pb_dashboard`'s `"%s employee(s) at 90%% of the %s monthly ceiling"`, which is POSITIONAL and therefore correct — WF24). The browser's translation payload holds **0**. Server side, `test_t12_…` asserts no `%%` in any headline, scope label, scope name, quarter name, quarter title or tone word across five period shapes. |

## 4. The parity proof (R3)

**Before touching a line**, `get_board` was captured on p9clone for **3 fiscal years ×
3 budget types × 13 scopes = 117 payloads** (the year and each of the twelve months),
canonicalised to sorted JSON. After the refactor, the same capture was taken from the
same running database.

```
payloads compared : 117
values CHANGED    : 0
keys MISSING      : 0
keys ADDED        : scope.keys, scope.quarter, quarters
```

39 of the 117 carry real functions, so this is not a comparison of empty payloads. Every
figure, every word, every tone, every strip cell, every month array and every currency
block came back identical, byte for byte, from a code path that no longer has a single
month key in it anywhere.

**Where I bent R3, and why.** R3 asks for the payloads to be proven "identical". They are
not, and cannot be: this phase's whole purpose is to add a stretch, and a stretch needs
`scope.keys` (which months), `scope.quarter` (whether it is one) and `quarters` (the four
brackets). So the assertion actually made is the strongest one available and, I think,
the one R3 means: **every key the old payload had is present with the identical value,
and the only differences are three additive keys.** Nothing was removed, nothing was
renamed inside the payload, and nothing changed value. The three additions are named
above rather than buried.

**And it is shipped as a test, not as this paragraph.**
`pb_budget/tests/test_budget_period.py::test_t1_the_refactor_moved_nothing` builds a
deterministic twelve-month fixture, reads `pb.budget.line` back independently, and
asserts the year board and each of the twelve month boards against that reading; then
asserts that a stretch of one month is **byte-identical** to that month asked for
directly, that a stretch of twelve is **byte-identical** to the year, and that a stretch
dragged right to left is byte-identical to the same stretch dragged left to right.

## 5. What the handover got wrong about the code

Three things, all found by building against it:

1. **`_compare`'s "this" cell was already the scope's own words, so widening it was
   free — but `_compare_cell` was not.** §2b says the drill's comparison row becomes
   scope-aware. The handover did not say that `_compare_cell` searches
   `('period_month', '=', first)` — one date — so a stretch needed it to take a LIST.
   It now does (`'in', firsts`), and it labels itself "August 2026 to September 2026"
   when the two ends differ and keeps the single-month label when they do not, which is
   what makes the single-month payload byte-identical.
2. **The printed page's new sentence became TWO msgids, and only a fresh export shows
   it.** §2c warns that a sentence must be built with a `_()` format string. It does not
   say that a sentence written in a QWeb REPORT template either side of a `<t t-esc/>` is
   split by the extractor into "The whole year, with" and "in bold — this page is about
   those months." — two half-sentences no translator can reorder. Found only because the
   `.pot` was rebuilt and diffed; moved into `pb.budget.export.period_page_line()`.
   Recorded as **L17**.
3. **§2f's caller list is complete but the sweep is smaller than it looks.** Every one of
   the eight callers passes the period POSITIONALLY, including both tests and the
   browser, so the `month=` → `period=` rename touched exactly two keyword call sites
   (`budget_export.build`'s own signature and its `pb.budget.get_board` call). Worth
   saying because a reader of §2f would budget for eight edits.

Two smaller notes, neither a fault in the handover:

- **`pb_dashboard` prints "0 employee(s)"** in the Pulse lens ("%s employee(s) at 90%% of
  the %s monthly ceiling"). It is GR42/R46's trap, it is on the screen **P4 is about**,
  and it is one line. Flagged for P4 rather than fixed here (scope discipline).
- **`.bdg-chip`'s `transition: .14s` is outside the reduced-motion guard** and has been
  since TIDY P3 shipped it. One line, not this phase's, recorded as **L18**.

## 6. Rulings I bent

**R3 only, and only in the sense set out in §4** — the payload gains three additive keys
because the feature requires them, so "identical" is proven as "every pre-existing key
identical, three named additions".

R1, R2, R4, R5, R6 and R7 are as written and each is proven above. In particular R2 is
proven by its consequence: `_matrix` now has ONE membership test and no month/year
branch at all, and the year board is simply the case where the list holds twelve.

## 7. Tests

**`pb_budget` on p9clone: 53 collected, 41 post-install, 0 failed, 0 errors.** TIDY P3's
baseline was 39 collected / 29 post-install; this phase adds twelve methods, all in the
new `tests/test_budget_period.py`:

| Method | What it pins |
|---|---|
| `test_t1_the_refactor_moved_nothing` | R3, as described in §4 |
| `test_t2_a_quarter_is_three_months_and_adds_up_to_them` | a quarter equals its three months, and the four are the year |
| `test_t4_the_collapse_rules` | one → month, twelve → year, four → range, and no false quarter |
| `test_t5_a_quarter_is_a_quarter_of_the_fiscal_year` | R5 on a July year-start, and the parameter restored |
| `test_t6_the_pace_of_a_stretch` | `_period_pace` == `_month_pace` over one month; past/future/straddling |
| `test_t7_a_deep_link_never_lands_on_an_empty_board` | every accepted form, both clamps, and nine shapes of rubbish |
| `test_t8_the_exports_name_the_stretch_they_are_about` | the file name, the sheet title, the total to the digit, the bars in scope, the narrative |
| `test_t11_every_shape_of_stretch_has_words_for_itself` | the three naming rules, and nothing blank in any shape |
| `test_t11b_a_stretch_with_nothing_in_it_still_answers` | the tiles do not rearrange when a period is empty |
| `test_t12_the_new_words_are_this_product_and_carry_no_stray_signs` | white-label + L9 over five period shapes |
| `test_t12b_a_running_stretch_gets_its_own_sentence` | the one sentence a month could not share |
| `test_t14_the_drill_of_a_stretch_adds_up_and_compares_like_for_like` | the drill sums, and compares a stretch with a stretch |

**The wider run over 274 tests** (`pb_pay` 125, `pb_group` 54, `pb_budget` 53,
`pb_contracts` 48, `pb_hub` 34) reports **3 failures and 0 errors**, all three the
recorded p9clone data drift. Zero regressions.

## 8. The four databases

| Database | `pb_budget` | budget rows | expense rows | tree hash |
|---|---|---|---|---|
| p9clone | 19.0.2.2.0 | 332 | 2 | `32199e6c…4dad` |
| payobook | 19.0.2.2.0 | 332 | 2 | `32199e6c…4dad` |
| abm | 19.0.2.2.0 | 10 | 0 | `32199e6c…4dad` |
| payobook_template | 19.0.2.2.0 | 0 | 0 | `32199e6c…4dad` |

One tree, one hash, verified against the repository over every file except
`__pycache__`, `*.pyc` and `.DS_Store`.

`pg_dump` before every database:
`/odoo/backups/p9clone_before_look_p3_20260909_000155.dump`,
`payobook_before_look_p3_20260909_003216.dump`,
`abm_before_look_p3_20260909_003248.dump`,
`payobook_template_before_look_p3_20260909_003253.dump`.

Asset ritual on all four: `/web/assets/%` attachments purged **and** the
`web.assets.version` `ir.config_parameter` bumped, then a service restart.

### What was created to test with, and the proof it is gone

Nothing was written to any budget on any database. The **row counts above are exactly
what they were before this phase started** (332 / 332 / 10 / 0 budget rows, 2 / 2 / 0 / 0
expenses), measured before the walk and again after it.

What was created and undone:

- **One temporary validator**, `look.p3@payobook.com`, on p9clone (**4420**), payobook
  (**4429**) and abm (**264**) — GR24 and WF15 both still stand. **All three archived
  again at the end of the phase**, and every earlier LOOK validator is still archived
  too: `SELECT count(*) … WHERE login LIKE 'look.p%' AND active` returns **0** on all
  three.
- **One config parameter on p9clone**, `pb_budget.fy_start_month = 7`, for the fiscal-year
  quarter test. Set back to 1 and then the ROW DELETED, because payobook, abm and
  payobook_template have no such row and the module's own default is 1 — so p9clone now
  matches them exactly (`FY_PARAM_ROWS 0` on all four).
- The validator's language was flipped to Vietnamese for the Vietnamese walk and back to
  English afterwards.
- `payobook_template` was never written to at all beyond the module upgrade.

## 9. Commits (NOT pushed)

| Commit | What | Files |
|---|---|---|
| `5a6daebc` | `feat(pb_budget): a period is an ordered list of months, not one key` | `models/pb_budget.py`, `models/budget_export.py`, `report/budget_report.xml`, `tests/test_budget_period.py`, `tests/__init__.py` |
| `4f0453e5` | `feat(pb_budget): the month strip becomes a range control` | `static/src/js/budget_board.js`, `static/src/xml/budget_board.xml`, `static/src/scss/budget.scss`, `__manifest__.py`, `i18n/pb_budget.pot`, `i18n/vi_VN.po` |
| (this report) | `docs(look): the P3 phase log, two new gotchas and the browser evidence` | `LOOK_P3_REPORT.md`, `LOOK_LEDGER.md`, `look_p3_shots/` |

Explicit `git add` of named files every time. **Not pushed** — with this report's commit
the phase made **three**, and **127** now wait on `19.1`.

## 10. What the owner has to decide

1. **Push, or keep holding.** **127** commits sit unpushed on `19.1`, three of them this
   phase's.
2. **The `payobook` administrator password in the ledger is still wrong (GR24), and so is
   `abm`'s (WF15).** This phase used one temporary `look.p3@payobook.com` on p9clone
   (4420), payobook (4429) and abm (264), **all three archived again**. Resetting the
   owner's own password is an owner decision and was not done.
3. **A future period that has already been spent on says "came in … under budget".**
   Q4 2026 has ₫75m of spend against a budget nobody has met, so the board judges it
   like any finished period rather than saying "not yet". That is exactly the rule TIDY
   P3 shipped for a month and its own test pins ("a future month that HAS been spent on
   is judged like any other"), so it was left alone. If it should read differently for a
   stretch, that is a one-line ruling.
4. **`pb_dashboard` prints "0 employee(s)"** on the Pulse lens — GR42's missing-plural
   trap, on the screen P4 is about. One line, and it belongs to P4.
5. **The `pbim` kit still has no dark palette (GR38)**, so "dark" remains the platform's
   chrome only.
