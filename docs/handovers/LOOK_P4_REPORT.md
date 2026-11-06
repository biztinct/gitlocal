# LOOK P4 — "The period on Pulse and on Explorer" — phase report

**Status: COMPLETE.** `pb_dashboard` **19.0.1.2.0**, `pb_explorer` **19.0.2.3.0**,
`pb_home_hub` **19.0.1.1.0** and `pb_budget` **19.0.2.2.1** live on p9clone, payobook,
abm and payobook_template. All four module trees verified byte-identical to the
repository on the server, and every manifest version verified against
`ir_module_module.latest_version` on all four databases.

Scope kept: `pb_dashboard` and `pb_explorer`, plus the one-line `pb_budget` reduced-motion
fix the brief named and one word in `pb_home_hub` (the Pulse lens now says
`wantsArrival`, which is how the shell hands a lens the link it was opened with — §5
below). No schema change, no migration, no new model.

---

## 1. The hero moment

**Both of the two the brief offered, and the first one is the bigger.**

### The home page's headline figures name their month for the first time

On the master database this page reported **₫16.8M of monthly payroll under a headcount
of 4,533 people**, and never said that the ₫16.8M was a single November test payslip.
That is the one thing that makes a number uncheckable, and it is the first screen every
tenant sees.

| | before | after |
|---|---|---|
| What the page said | `Monthly payroll  16.8M ₫  ·  personnel cost` | **`Figures for November 2026 · the latest payroll month`** over `16.8M ₫ · personnel cost in November 2026` |
| Press "Jun 2026" | not possible | **`117.3B ₫`**, avg `30.5M ₫`, contributions `15.1B ₫` |
| Read back from SQL | — | `117,294,938,600` and `15,069,400,000` — **to the digit** |
| The shape of the year | invisible | Apr 4,402 · May 4,431 · Jun 3,852 · Jul 1,440 · Aug 902 · Sep 3 · Oct 1 · Nov 1 |

Screenshots: `look_p4_shots/01_p9clone_pulse_names_its_month.png`,
`02_p9clone_pulse_june_2026.png`, `11_payobook_pulse.png`, `12_payobook_pulse_june.png`.

### Explorer's sentence finally completes

*Show **Net pay** By **Division** Over **Month** **When June 2026** Where …* — the clause
that was never there, in its own chip group between "Over" and "Where", with a strip that
is **a live sparkline of the very question being asked**: change the measure and the bars
redraw. On the demo data, by net pay July is the tallest month (100%) and April 57.9%; by
people May is the tallest (100%) and July drops to 32.5%. Same eight months, two entirely
different shapes, one measure apart.

Screenshots: `05_p9clone_explorer_when_picker.png`,
`06_p9clone_explorer_strip_is_measure_aware.png`, `15_payobook_explorer_when.png`.

### And a third thing nobody asked for, which is arguably worth more than either

Measuring the strip found that **the home page's own KPI statement takes 12.5 seconds on
any real payroll month.** `hr_payslip_line` is 1.7 GB on the master database against
1.9 GB of memory on the box, so the planner's sequential scan of it can never be cached.
Today's page is fast only because the newest month on this data has one payslip in it; a
tenant whose newest month has four thousand would wait twelve seconds for their home
page, every time. Handed the month's payslip ids the planner uses the `slip_id` index
instead. Measured on payobook for June 2026, 3,852 end-of-month payslips:

| | before | after |
|---|---|---|
| June 2026 (3,852 payslips) | **12.5 s** | **2.1 s** |
| November 2026 (1 payslip) | 12.5 s in the general form, 103 ms in the shipped one | **16 ms** |
| Every figure | | **identical** |

## 2. Self-score against the design bar

> **extreme WOW, intuitive, out-of-this-world experience, best in class.**

**8.5 / 10.** What earns it:

- The Pulse fix is the rarest kind: it does not add a number, it makes an existing number
  **checkable**, and the first press of the strip shows a reader that the figure they
  have been looking at for months was a test payslip.
- Explorer's strip is not a date picker. It is a **shape of the answer** that redraws when
  the question changes, and pressing it is how you ask about a month.
- **Zero dead-ends, every state designed and proven live**: no payroll at all (the golden
  template), a month with payslips but no end-of-month run (AB Mauri), a month with one
  person in it, a period wholly before the facts, a period in the future, a link naming a
  month that does not exist, a malformed link, a fresh tenant with no facts to choose
  from, a phone, and a keyboard with no mouse.
- **Full keyboard parity on both strips**, every contract proven with the browser's own
  key presses (L16): arrows walk, Home/End jump, Shift extends from the anchor, Escape is
  a ladder. `[disabled]` counted **0** on every chip at every moment (T23 does not come
  back).
- Plain language everywhere, Lucide only, Vietnamese complete on both screens, and **no
  console error on any of the four databases**.

What holds it back from 10:

- **Pulse's strip carries people, not money** — a deliberate deviation from §2b, measured
  and defended in §6. The money for the month on screen is the headline figure directly
  above the strip, so the question is answered; it is answered one glance higher up than
  the brief asked for.
- On a phone the strip is 230 px wide inside a 390 px screen, so about two and a half
  chips are visible at once. It scrolls, it keeps the chosen chip in view and it drops
  nothing — but a stretch of a year is a lot of scrolling on a phone.
- Explorer's period picker is a dropdown, so while the strip is open it covers the chart
  it is changing. Keeping it open is what makes shift-press and the arrows work at all
  (§5), and the chip's own label updates behind it, but the board is not visible under it.
- Thirteen lens names and their descriptions still print in English on a Vietnamese
  Explorer — the same trap this phase closed for the measures (§5), one registry further
  along. Recorded as **L22** rather than swept under a period picker's commit.
- The `pbim` kit still has no dark palette (GR38).

## 3. The numbered tests

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | **Pulse names its period** on first load, with no interaction | **PASS** | "Figures for November 2026 · the latest payroll month", above the numbers, on p9clone, payobook and abm; "No payroll has been run yet" on the golden template. `01_…`, `11_…`, `13_…`, `14_…`. |
| 2 | **Pulse's default is unchanged** to the digit | **PASS** | Baseline captured in psql BEFORE any code changed: `2026-11-01 \| 1 \| 16750000.00 \| 2867000.00` on p9clone and payobook, zeros on abm, nothing on the template. After: `16.8M ₫` / `2.9M ₫` on both, `0 ₫` on abm, `$0` on the template. Shipped as `test_p3_the_default_is_the_month_this_board_always_reported`, which re-derives the old statement independently and compares. |
| 3 | **The Mid/End guard holds (R3)** | **PASS** | `test_p4_the_mid_and_end_guard_holds_for_every_month` finds a month carrying BOTH kinds of run (June 2026: 4,393 mid-month, 3,852 end-of-month), asks the facade for it, and compares against two independent statements — the end-of-month one and the both-kinds one — asserting the payload equals the first and that the second is strictly larger, so the fixture cannot silently stop proving anything. Live: June reads **₫117.3B / 3,852 people**, not ₫230B / 8,245. |
| 4 | **Pulse with no payslips** | **PASS** | Walked on **payobook_template**, the one database in this state: no strip, honest zeros (`$0`, `0 active contracts`), "No payroll has been run yet", the sentence "No payroll months yet. Once a pay run is done, every month it covers appears here…", and the activation checklist untouched. `14_…`. `test_activation.py` is green including **`test_04`'s syntax-tree walk** — guarded models still exactly `{learn.progress, hr.payroll.import.batch}`, no leaks. |
| 5 | **Pulse's strip** | **PASS** | Every month against SQL (Apr 4,409 · May 4,431 · Jun 3,852 · Jul 1,440 · Aug 902 · Sep 3 · Oct 1 · Nov 1 for the company in scope, matching `test_p2` which re-reads the month list from the database). At 390 px the strip is 765 px wide in a 230 px port and the chosen chip is **scrolled fully into view** (`scrollLeft 535 of a maximum 535`, `chosenVisible true`, the page itself not scrolled sideways). Keyboard per rule 20, with real key presses: `→` May→June, `Home`→April, `End`→November, focus kept, `[disabled]` **0** throughout; `Escape` from August returned to November and the "Back to the latest month" button disappeared. Deep links `month:2026-06` → June, `month:current` → September (this month), `month:2026-04..2026-06` → June, `month:2029-01` / `month:rubbish` / `month:Q2` → November **with the sentence saying it fell back** — eight chips on every one. `03_…`, `04_…`. |
| 6 | **`pb_dashboard` gained no dependency** | **PASS** | `git diff` on the manifest is the version line and a comment. `depends` is still `['web', 'om_hr_payroll', 'pb_hr_payroll_base']`; the module imports nothing from another cockpit, keeps its own inline `ICONS` map (one Lucide path added: `calendar`), and `test_05_the_manifest_and_the_imports_name_neither_module` and `test_04`'s tree walk are both green. |
| 7 | **Explorer's When clause changes everything** | **PASS** | Everything → June 2026 on p9clone: total `116B ₫` → `21.3B ₫`, people `4,494` → `3,852`, the chart redrawn, and the coverage notice rewritten from "12 of 43 pay periods are still in progress" to "**9 of the 12 pay periods in June 2026** are still in progress". The link gained `"s":"2026-06-01","e":"2026-06-30"`. |
| 8 | **Each preset names the right dates**, on both fiscal years | **PASS** | Live on a January year: This month `September 2026` · Last month `August 2026` · This quarter `Jul to Sep 2026` · Last quarter `Apr to Jun 2026` · This year `Jan to Dec 2026` · Last year `Jan to Dec 2025` · Everything `every period on file`. `test_w2c` sets `pb_budget.fy_start_month = 7`, asserts the financial year moves to July and the quarter starts on a July-year boundary, then restores the parameter and deletes the row. `test_w2b` pins three months to a quarter and twelve to a year, and that the two quarters and the two years do not overlap. And the collapse rule works both ways: pressing "Last quarter" answers **"Q2 2026 · Apr to Jun 2026"**, because a stretch that IS a fiscal quarter is named as one. |
| 9 | **A stretch by shift-press and by drag** | **PASS** | Shift-press June→August: "Jun to Aug 2026", `74.9B ₫` (21.3 + 35.0 + 18.6), and the three chips fuse into ONE band — measured `is-first/is-last` flags `[true,false] [false,false] [false,true]`. A pointer sweep across the strip previews from the chips under the hand and reads the server **once**, on release. `08_…`. |
| 10 | **The strip is measure-aware** | **PASS** | Net pay: `Apr 57.9% · May 58.1% · Jun 61.1% · Jul 100% · Aug 53.3%`, heading "NET PAY BY MONTH". Switch the measure to People: `Apr 99.3% · May 100% · Jun 86.9% · Jul 32.5% · Aug 20.4%`, heading "PEOPLE BY MONTH". Same months, a different shape, one measure apart. `06_…`. |
| 11 | **R6 performance** | **PASS** | The strip's own grouped statement over the biggest fact table available (`pb_fact_line` on payobook, the derived table into which 719,487 payslip lines reduce): **131 ms**, and 497 ms over `pb_fact_emp`'s 197,834 rows. `get_schema` (which builds the presets and the month list) **772–899 ms** round trip. `query` round trip **959 ms** over everything and **841 ms** for one month — a period makes the board FASTER, because fewer runs are in scope. Pulse: **140–175 ms** for the default month and **2.6–2.9 s** for a month of 3,852 payslips (against 12.5 s before this phase). |
| 12 | **R7 round-trip** | **PASS** | A stretch set on one page, the URL copied, opened in a **fresh page** — "May to Jul 2026", `76.6B ₫`, "Net pay": identical. A malformed link (`"s":"2026-13-45","e":"rubbish"`) opens on "Everything" with no error and no blank board — **the case that raised a five-hundred error before this phase's first commit** (§5). |
| 13 | **Drill and export carry the period** | **PASS** | `drill(_all,_all)` over everything: **4,494** people; the same call with June's dates: **3,852**. `export_csv` for June writes, as its FIRST TWO ROWS, `Period,June 2026` and `From,2026-06-01,To,2026-06-30`, and names it `payobook_net_by_division_id_2026-06-01..2026-06-30.csv`. |
| 14 | **Every state in §3c** | **PASS** | No facts at all (the golden template — the When picker's own empty state, "No pay periods have been built yet…", with the presets still working). A period with no data: the empty state now points AT the control — "Nothing was paid in 1990 that matches. Widen the When clause above, drop a filter, or include mid-month advances." with a **"Look at every period"** button (`07_…`). A period wholly before the facts (1990, named as a year, `0 ₫`, strip intact). One in the future and one straddling the built/unbuilt boundary (covered by `test_w7` and by the coverage sentence rewriting itself). A shared link and a malformed one (test 12). A period plus a drill plus filters, breadcrumb intact (test 13, and the breadcrumb reads "Payobook Vietnam JSC › Division" throughout). |
| 15 | **Vietnamese on both screens** | **PASS** | Explorer: the chip rail reads **ĐO LƯỜNG · BỞI · KẾT THÚC · KHI NÀO · Ở ĐÂU**, the presets "Tháng này / Tháng 9 2026", "Quý trước / Thg 4 đến Thg 6 2026", the strip heading "LƯƠNG THỰC NHẬN THEO THÁNG", the coverage sentence "9 trong 12 kỳ lương của Tháng 6 2026 vẫn đang chạy…". Pulse: "Số liệu của Tháng 11 2026 · tháng lương gần nhất", chips "Thg 4 2026 · 4,402 người", tooltips "Tháng 6 2026 — 3,852 người đã được trả lương.", caption "chi phí nhân sự trong Tháng 11 2026". Month names from **babel**, not `strftime`. `09_…`, `10_…`. Catalogues: `pb_explorer` **274 terms**, `pb_dashboard` **88 terms**, both **0 untranslated, 0 fuzzy, 0 lost placeholders, 0 entries without their `#. module:` comment (GR5), the vendor's name in no translation and in no header (WF27)**. Both `.pot` templates are committed beside their catalogues. |
| 16 | **Reduced motion, and keyboard only** | **PASS** | Reduced motion proven the R85 way, against the **DEPLOYED** 5.9 MB stylesheet fetched from the running server: every declaration this phase touched — `.pbd-mchip`, `.pbd-mchip-fill`, `.pbd-period-back`, `.pbd-card`, `.pbex-mchip`, `.pbex-mchip-fill`, `.pbex-chip` and **`.bdg-chip`** — is inside `@media (prefers-reduced-motion: no-preference)` and **none of them declares a transition or an animation outside it**. Keyboard only: both strips walked end to end with the browser's own key presses (tests 5 and 9), and Explorer's Escape ladder proven in order — first press closed the picker and left the period alone, second press cleared the period and the total went back to `116B ₫`. |
| 17 | **Nothing regressed** | **PASS** | See §4. **398 tests on p9clone, 4 failed, 0 errors** — and a **control run with all four modules reverted to their pre-phase commit reproduces exactly the same four**. Zero regressions. |
| 18 | **No literal `%%`** | **PASS** | In the DOM: `document.body.innerText.includes('%%')` is **false** on both screens, in English and in Vietnamese. In the **deployed 11.3 MB bundle**: 15 occurrences, and every one of them is a POSITIONAL `_t("%s%% …", value)`, which is the form that correctly renders one sign (WF24). **Not one of them is in `pb_dashboard`, `pb_explorer` or `pb_budget`.** In the catalogues: `pb_dashboard` 0, `pb_explorer` 1 — a pre-existing Python `_()` string, where `%%` is required. |
| 19 | **Pulse's plurals, and `.bdg-chip`** | **PASS with a correction to the brief** | No bracketed plural exists anywhere in `pb_dashboard` — see §5: the "0 employee(s)" the brief attributes to this module is in **`pb_insights`**, not here. Every count Pulse prints branches on the singular in its own right ("1 person" / "%s people" / "nobody paid" / "no end-of-month run"), test-enforced. `.bdg-chip`'s transition is inside the reduced-motion guard and proven against the deployed bundle (test 16). |

## 4. Tests

**Per module on p9clone: `pb_explorer` 69, `pb_dashboard` + `pb_home_hub` + `pb_budget`
96 — 165 collected, 0 failed, 0 errors.** `pb_explorer` was 53 before this phase; the 16
new ones are in `tests/test_look_p4.py`. `pb_dashboard` gained 10 in a new
`TestPayrollMonth` class inside its existing test file.

| Method | What it pins |
|---|---|
| `pb_dashboard` `test_p1` … `test_p10` | the payload names its month; the strip is the database's own months; the default is what the board always reported; **R3's guard on a Mid+End month**; every shape of link lands somewhere real; `current` means now for ever; a stretch collapses and says which month; a fallback says so; the facade is a pure read; no bracketed plural and no stray per cent sign; and the two statements that must never scan the payslip lines |
| `pb_explorer` `test_w1`…`w1d` | the period resolves on the server; a whole month is a month; a part month still gets a sentence; one open end is a real answer |
| `test_w2`…`w2c` | seven presets, each naming its dates; three months to a quarter and twelve to a year; **a quarter is a quarter of the FISCAL year**, with the parameter restored |
| `test_w3`, `w3b` | a stretch of whole months is named as one, and dragged right to left is the same stretch |
| `test_w4`, `w5`, `w5b` | a period changes every number; the strip is NOT narrowed by what is already chosen; the months come from the facts, in order |
| `test_w6` | the drill and the export carry the period, and the CSV names it in its own content |
| `test_w7`, `w8a` | six malformed periods are never an error; six shapes that look like dates and are not are refused |
| `test_w8`…`w8e` | the link carries the period both ways; no bracketed plural, no stray per cent sign; the notices and the empty state branch on the period; the When clause sits between Over and Where; everything this phase moves is inside the reduced-motion guard |

**The wider run over 398 tests** (`pb_pay`, `pb_group`, `pb_budget`, `pb_contracts`,
`pb_hub`, `pb_explorer`, `pb_dashboard`, `pb_home_hub`) reports **4 failures and 0
errors**:

```
TestCd1Contract360.test_22_the_picker_is_whitelisted                 (pb_contracts)
TestCd3EditPaths.test_05_the_picker_is_whitelisted_and_answers       (pb_contracts)
TestPbGroup.test_t9_the_screen_counts_what_the_roster_counts…        (pb_group)
TestPayBands.test_tidy_t2_people_between_names_exactly_the_people…   (pb_pay)
```

The first three are the p9clone data drift this ledger has recorded since GROUP P6a. The
fourth is **new to the wide run and not new to the phase**, and it took two control runs
to be sure of that (recorded as **L23**):

- `pb_pay` on its own, with this phase's modules deployed: **117 tests, 0 failed, 0 errors.**
- `pb_pay` on its own, with all four modules reverted to `eae7c2ed`: **117 tests, 0 failed, 0 errors.**
- The **wide run with all four modules reverted**: **355 tests, and the SAME four failures.**

So it is an interaction inside an eight-module run, present before this phase and after
it, and invisible to the way every earlier LOOK phase measured `pb_pay`. P3's stated
baseline was 274 tests / 3 failures over a five-module set; this phase's set is eight
modules and 398 tests, so the honest comparison is the control run above rather than the
number.

## 5. What the handover got wrong about the code

Five things, all found by building against it.

1. **"Pulse prints 0 employee(s)" is not in `pb_dashboard`.** §1b's first named defect —
   `"%s employee(s) at 90%% of the %s monthly ceiling"` — lives in
   `pb_insights/static/src/js/insights.js:272`. P3 found it by grepping the deployed
   bundle for `%%` and attributed it to the nearest screen. `pb_dashboard` contains no
   bracketed plural at all, before or after this phase, which the sweep §1b asked for
   confirms and a shipped test now pins. **The real one is untouched**: fixing it means a
   fifth module in a phase whose scope discipline names three, so it is carried as an
   owner debt.
2. **§2a's `periods` cannot be "one grouped SQL query over `hr_payslip`" AND carry the
   month's payroll.** Payroll is in `hr_payslip_line`, which is 1.7 GB on the master
   database, and every statement that reads ten months of it costs **12.5 seconds** —
   measured four ways, warm and cold. §6 sets out what was built instead and why.
3. **`_as_date` accepted anything ten characters long**, so `2026-13-45` from a
   hand-edited link went into the run domain and the PLATFORM raised
   `ValueError: month must be in 1..12`. R7 asks for a malformed period that "must not
   error"; it did, on the code as it stood. Closed first and in its own commit.
4. **The whole Explorer vocabulary was English on a Vietnamese screen.** Every measure,
   dimension, grain and kind of run carried its label as a literal inside a module-level
   dict, and `_(entry['label'])` cannot translate one — the extractor never sees it as a
   term (T24 / GR58). The headline read "Net pay bởi Division". The strip's own heading
   names the measure it is a shape of, so this phase could not leave it. Twenty-one terms,
   fixed in GR59's shape. (`Division` was also translated "Phép chia", the arithmetic
   operation, where the rest of the product says "Khối"; six other modules still carry
   the wrong word.)
5. **§2b's deep link cannot reach Pulse without one word in `pb_home_hub`.** The Pulse
   lens is one of the two the Home hub HARD-CODES; it is not in the soft registry, so it
   has no `propsFromContext`. The shell hands a lens the arrival payload only if the lens
   declares `wantsArrival`, and that is a one-word change in `home_hub.js`. Both of that
   module's tests that read the pulse declaration still pass unchanged.

Two smaller notes: `.pbex-chip`'s `transition: all .16s` and `.pbd-card`'s hover lift were
both outside the reduced-motion guard and are now inside it; and this phase hit WF13
(a grep defeated by its own comment) **twice**, in a test's docstring and in a source
comment, which is now written down as part of L23.

## 6. The ruling I bent, and why

**§2b, the one thing: Pulse's chips carry HOW MANY PEOPLE were paid, not how much.**

The brief asks for "a micro bar of that month's payroll against the busiest month". That
bar cannot be built at a price this screen may pay. Measured on payobook, 2026-09-09,
four ways:

| Statement | Time |
|---|---|
| Ten months of payroll, joined through `hr_payslip_line` | **12.5 s** (warm: 12.7 s) |
| The same, filtered to GROSS lines only | **12.5 s** |
| The same, handed every end-of-month payslip id | **10.4 s** |
| Ten months of PEOPLE, over `hr_payslip` alone | **32 ms** |

`hr_payslip_line` is 1.7 GB — 719,487 rows over 210,264 blocks — against 1.9 GB of memory
on the box, so it can never be cached and a sequential scan of it costs twelve seconds
whatever the state of the cache. This is the first screen of every tenant.

What was built instead answers this strip's own question under ledger rule 19 — *was
anybody paid, and how many* — in 32 ms, on `hr_payslip` alone, with the same end-of-month
restriction as the KPI so the two can never disagree. **The money is not lost: it is the
headline figure directly above the strip**, read once, for the month the strip names.

Two things make the deviation smaller than it reads. The bar is a RELATIVE shape and
people track payroll closely, so the picture of the year is very nearly the one the brief
asked for. And the measurement that forced it also made the KPI itself six times faster,
which is worth more to a reader than the bar would have been.

Every other ruling is as written. **R1** is proven by the manifest diff and by test 6;
**R2** by the golden-template walk and by `test_04`'s tree walk; **R3** by
`test_p4`, which picks the month that actually double-counts and proves the payload
refuses to; **R4** is the first thing on the screen; **R5** by test W8d, which pins the
When clause between Over and Where; **R6** by the 131 ms measurement; **R7** by the
round-trip in a fresh page; **R8** by matching P3's vocabulary and importing none of it —
`pb_explorer` still depends on `pb_group` and not on `pb_budget`, and `pb_dashboard`
depends on neither.

One reading worth stating out loud, because it is a judgement rather than a proof.
**Pulse's period is always exactly one month.** Rule 20 says Escape "clears the period
back to the widest scope"; this board has no honest widest scope, because its figures are
a MONTH's ("Monthly payroll", "Avg salary") and four months summed under that label would
be a lie no chip could repair. Escape therefore returns to the latest payroll month, which
is where the board opens and what it reported before this phase. A link naming a stretch
resolves to the newest month inside it that has payroll, and P3's `Q1` — which needs a
fiscal year this board has no notion of — falls back like anything else it cannot read.

## 7. The four databases

| Database | `pb_dashboard` | `pb_explorer` | `pb_home_hub` | `pb_budget` | payroll months | payslips |
|---|---|---|---|---|---|---|
| p9clone | 19.0.1.2.0 | 19.0.2.3.0 | 19.0.1.1.0 | 19.0.2.2.1 | 8 (10 across every company) | 28,286 |
| payobook | 19.0.1.2.0 | 19.0.2.3.0 | 19.0.1.1.0 | 19.0.2.2.1 | 8 | 28,286 |
| abm | 19.0.1.2.0 | 19.0.2.3.0 | 19.0.1.1.0 | 19.0.2.2.1 | 1, with no end-of-month run | 36 |
| payobook_template | 19.0.1.2.0 | 19.0.2.3.0 | 19.0.1.1.0 | 19.0.2.2.1 | 0 | 0 |

Tree hashes, verified over every file except `__pycache__`, `*.pyc` and `.DS_Store`, and
**identical between the repository and the server**:

```
pb_dashboard  3ce7951a1304ac4df07925bee77078020749defe0cb1066aab72d4453115b290
pb_explorer   3aac4094471d295d6215d7551d67fb41c32e79c7baf12b775ccedfc0f6f5b5c4
pb_home_hub   e21de977501b402cac57b73261d5dc1016713fe98699fead9b4ab546c2ada983
pb_budget     04f7eff64fb673408dfebf6b0075d7848fdd9ad71e34e6c24e2a48ef7469638b
```

`pg_dump` before every database:
`/odoo/backups/p9clone_before_look_p4_20260909_005655.dump`,
`payobook_before_look_p4_20260909_021038.dump`,
`abm_before_look_p4_20260909_021059.dump`,
`payobook_template_before_look_p4_20260909_021106.dump`.

Asset ritual on all four: `/web/assets/%` attachments purged **and** the
`web.assets.version` `ir.config_parameter` bumped, then a service restart.

### What was created to test with, and the proof it is gone

**Nothing was written to any business record on any database.** The row counts after the
phase are exactly what they were before it:

| | p9clone | payobook | abm | payobook_template |
|---|---|---|---|---|
| payslips | 28,286 | 28,286 | 36 | 0 |
| pay runs | 45 | 45 | 1 | 0 |
| budget rows | 332 | 332 | 10 | 0 |
| fact rows | 6,158 | 6,158 | 760 | 0 |
| `pb_budget.fy_start_month` rows | 0 | 0 | 0 | 0 |
| active `look.p*` users | 0 | 0 | 0 | 0 |

- **One temporary validator**, `look.p4@payobook.com`, on p9clone (**4451**), payobook
  (**4430**), abm (**265**) and payobook_template (**647**) — GR24 and WF15 both still
  stand. **All four archived at the end of the phase**, and every earlier LOOK validator
  is still archived too.
- **One config parameter**, `pb_budget.fy_start_month`, set to 7 by the fiscal-quarter
  test and restored by the test itself; the row does not exist on any of the four.
- The p9clone validator's language was flipped to Vietnamese for the Vietnamese walk and
  back to English afterwards.

## 8. Commits (NOT pushed)

| Commit | What | Files |
|---|---|---|
| `da7005e7` | `fix(pb_budget): the last moving rule a calm reader was still given` (L18) | `static/src/scss/budget.scss`, `__manifest__.py` |
| `37d1908b` | `fix(pb_explorer): a date that is ten characters long is not a date` | `models/pb_explorer.py` |
| `bcd25ce5` | `fix(pb_explorer): the words this board prints are words, in the reader's language` | `models/pb_explorer.py`, both catalogues |
| `aba2bea3` | `feat(pb_explorer): the sentence finally has a When` | the server, the browser, the stylesheet, the template, the tests, both catalogues, the manifest |
| `7070d8d1` | `feat(pb_dashboard): the home page names the month its figures are about` | `pb_dashboard` server/browser/stylesheet/template/tests/manifest/catalogues, `pb_home_hub` |
| `5616ac00` | `fix(pb_dashboard): the empty strip's two sentences keep the space between them` | `static/src/xml/pb_dashboard.xml`, `static/src/scss/pb_dashboard.scss` |
| (this report) | `docs(look): the P4 phase log, the closeout and the browser evidence` | `LOOK_P4_REPORT.md`, `LOOK_CLOSEOUT.md`, `LOOK_LEDGER.md`, `look_p4_shots/` |

Explicit `git add` of named files every time. **Not pushed** — with this report's commit
the phase made **seven**, and **135** now wait on `19.1`.

## 9. What the owner has to decide

See `LOOK_CLOSEOUT.md` §5 for the complete list across all four phases. This phase's own
additions:

1. **`pb_insights` prints "0 employee(s)"** — the real home of the plural P3 attributed
   to the home page. One line, in a module this phase did not open.
2. **Thirteen Explorer starting-point names print in English** on a Vietnamese screen
   (L22), the same trap this phase closed one registry along.
3. **Six other modules translate "Division" as "Phép chia"**, the arithmetic operation,
   where the rest of the product says "Khối".
