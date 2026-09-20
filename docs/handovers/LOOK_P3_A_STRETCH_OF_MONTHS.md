# LOOK P3 — A stretch of months

**Read `docs/handovers/LOOK_LEDGER.md` in full first**, and the parent ledgers it names
(GROUP, TIDY, WFPLAN, RIZE), and the P1 and P2 reports for the L-series gotchas.

**Module touched: `pb_budget` only.** Server + browser. No schema change, no migration.

---

## 0. What you are building, in one paragraph

TIDY P3 made a month a first-class scope on the Budget board: thirteen chips under the
numbers — "Whole year" and the twelve months — and pressing one turns the whole board
into that month. The owner's next question was the obvious one: *a quarter, or "March to
June"*. Because a quarter is not a month and it is not a year, and neither is "the three
months since we changed the plan". **You are making the strip select a STRETCH of
months**: press one, shift-press another, or drag across them, and everything the board
can say — every total, word, colour, pace, tile, drill, table column and export —
becomes about those months together. Four quarter brackets sit above the strip for the
common case, and because the fiscal year does not have to start in January, a quarter
here is a quarter of the FISCAL year and says so.

---

## 1. Rulings — decided, do not re-open

**R1. One period vocabulary, three shapes.** The scope is a year, a month, or a range.
`_scope` gains `kind: 'range'` alongside `'year'` and `'month'`. **A range that covers
exactly one month collapses to `'month'`, and one that covers all twelve collapses to
`'year'`** — so nothing downstream ever has two ways to say the same thing, and a
reader who drags across the whole strip gets the year board they already know rather
than a second, subtly different one.

**R2. The single month key becomes an ordered LIST of month keys, and that is the
refactor.** Today `mkey` (one string, or `''` for the year) threads through `_matrix`,
`_kpis`, `_strip`, `_headline_month`, `_tone_month`, `_expenses` and `_rows`. Replace it
with `mkeys` — the ordered list of months the scope covers, which for the year is all
twelve. Then a month, a range and the year are ONE code path with a different list, and
ledger rule 18 stops being a promise and becomes a property of the code.

**R3. Prove you broke nothing, do not assert it.** This is the hot path of a screen that
shipped and was validated eight days ago. Before touching anything, capture
`get_board`'s payload for the year and for each of the twelve months on p9clone; after
the refactor, capture them again and prove them **identical**. Ship that as a test, not
as a paragraph in the report. Precedent: GROUP P1 proved the Budget screen
byte-identical after the `pb.budget.fx` shim.

**R4. The parameter is renamed, and every caller is swept.** `get_board(fy, budget_type,
currency, row_cap, month=None)` becomes `..., period=None`. It now accepts:
`''`/`None` (the year), `'YYYY-MM'`, `'current'`, `'YYYY-MM..YYYY-MM'` (a range) and
`'Q1'`…`'Q4'` (a quarter of the fiscal year). The browser calls it positionally so the
rename is free there; the Python callers are few and named in §2f — sweep all of them
including the tests.

**R5. A quarter is a quarter of the FISCAL year.** `_fy_start_month()` reads
`ir.config_parameter` `pb_budget.fy_start_month` (default 1) and `_fy_label` prints
`2026/27` when it is not January. Q1 is fiscal months 1–3, whatever the calendar says.
The chip says "Q1" and its label and tooltip name the actual months, so a reader on a
July year-start is never guessing.

**R6. Deep links keep working, and a bad one never lands on an empty board.** The
existing `pb_focus: "month:YYYY-MM"` and `"month:current"` must keep working exactly —
there is a ⌘K row ("Budget this month") pinned on `month:current`
(`budget_palette.js:84-94`) and saved links in the wild. Add `"month:YYYY-MM..YYYY-MM"`
and `"month:Q2"` in the same vocabulary rather than inventing a second prefix. A range
that hangs off the end of the fiscal year is **clamped to the year**, and only if
nothing at all remains does it fall back to the whole year (ledger rule 21). Never an
error, never a blank board.

**R7. The server resolves the period; the browser adopts the answer.** The browser sends
what the reader asked for and then takes `board.scope` as the truth about what it got —
which is already how `state.month` is set today (`budget_board.js:117-120`). Keep that
exactly.

---

## 1b. What P1 and P2 learned that lands on you

`pb_pay` is at **19.0.3.3.0** on all four databases; P2 passed 15/15 and removed the last
cap in the product. **Read L1–L16 in the ledger in full.** Six of them are traps this
phase will walk into unless you look:

- **L9 — a `_t()` handed a dictionary writes ONE per cent sign; two print literally.**
  Python's `_()` interpolates with `%` and needs `%%` to emit one sign; the browser's
  `_t()` with keyword arguments does not. This screen is *made of* percentages — every
  chip's variance, every tone word, the headline — and P2 shipped "0.00%% to 0.30%%" to a
  live screen with nothing warning it. The second half of the trap: the msgid then
  contains `%%`, so fixing it is a catalogue change as well as a code change.
- **L13 / T24 — a user-visible literal that lives in a module-level list or tuple is
  invisible to the extractor.** T24 already caught `BUDGET_TYPES` on this very screen.
  Your quarter labels, preset names and range words are exactly the same shape of thing:
  write them **inside** the `_()` call, in a dict keyed by value, with the ordering in a
  separate ladder (GR59). If you add a module-level list of words in this phase, you have
  reintroduced T24.
- **L15 — never edit a msgid in place.** A substring replacement across a `.po` misses
  any msgid the exporter wrapped across lines: the short ones change, the wrapped one
  does not, and a grep looks correct while the screen still prints English. Rebuild the
  catalogue from a fresh `odoo-bin i18n export` and carry translations across by msgid.
  You are renaming period sentences, so this WILL bite.
- **L16 — prove a keyboard contract with the browser's own key press.** A synthetic
  `KeyboardEvent` dispatched on `window` does not reach a capture-phase
  `useExternalListener` the way a real press does; P2 chased a "broken" Escape that was
  perfect under `press_key`. Your Shift-extend and Escape tests must use real presses.
- **L2 — nothing sized by a translated sentence gets a fixed pixel height.** Your range
  headline and the quarter brackets both hold translated text.
- **L12 — `overflow: hidden` on a strip will clip whatever sits in its margin.** The
  quarter brackets sit above the chips; if you clip the strip to scroll it, they go.

## 2. Deliverables

### 2a. The strip becomes a range selector

The strip is `budget_board.xml:182-206`: a "Whole year" chip and twelve month chips,
each carrying a label, a two-tone micro bar and either "not yet", "no budget" or a
signed variance percentage, with a "now" marker on the current month. **Keep every one
of those chips and everything each one already says** — the whole point of the strip is
that it answers before anybody clicks. Add:

- **Press** a month → that month (today's behaviour, unchanged).
- **Shift-press** a second month → the stretch from the first to it, in either
  direction.
- **Drag** across the chips → the same stretch, previewed live under the hand and
  committed on release.
- **Press the selected month again** → back to the whole year.
- **Four quarter brackets above the strip**, each spanning its three chips. Pressing one
  selects those three months; pressing the selected one clears.
- **The selected chips read as one continuous band** — rounded only at the two ends,
  square where they meet. That is the detail that makes the strip feel like a range
  control rather than thirteen buttons, and it costs one CSS rule.

Keyboard (ledger rule 20, extended):
- `←` / `→` walk the chips, `Home` / `End` jump to the ends.
- `Shift` + `←` / `→` **extend** the selection from the anchor.
- `Escape` clears back to the whole year, after any dialog and after the drill.
- The busy guard is in the HANDLER, never on a chip's `disabled` attribute, and "where
  the keyboard is standing" is read from `ev.target.closest("[data-month]")` — **T23**,
  which this screen has already been bitten by once.

### 2b. What a range changes on the server

Everything (ledger rule 18):

- **Totals and KPIs** — summed across the months in the range.
- **Pace** — how far the calendar is through the RANGE. A range wholly in the past is
  100, wholly in the future is 0, and one we are inside is the elapsed share. Extend
  `_month_pace`'s idea rather than inventing a second one; a range of one month must
  give exactly what `_month_pace` gives today.
- **Tone words and colours** — `_tone_month` / `_tone_label_month` take the scope.
- **The headline sentence** — `_headline_month` becomes the scope's headline. Write the
  range's sentence in the same voice: it names the stretch in plain English.
- **The tiles' sparks** — the twelve months are still sent whatever the scope, and the
  chosen ones are ALL lit (`isLit` today matches one key; it becomes membership).
- **The drill**, the table's month columns, and the expanded rows.
- **The exports** — `budget_export.py`: `month_bars(board)` and `_narrative_month(board)`
  both become scope-aware, and the spreadsheet and PDF say which stretch they are about
  in their own title. An export that does not name its period is a document that will be
  read next year and believed.

### 2c. Naming a stretch in plain English

`scope.label` and `scope.name` must read like something a person would say:

- One month: "March 2026" (unchanged).
- A quarter: "Q2 2026 · April to June" — and "Q1 2026/27" when the fiscal year is not
  the calendar year.
- Any other stretch: "March to June 2026", and "December 2026 to February 2027" when it
  crosses the turn of the calendar year.
- The whole year: unchanged.

Month names come from **babel** via the existing `_month_words` / `_month_title` —
`strftime` answers in the server's C locale and would print "Mar" on an otherwise
Vietnamese screen. Any new sentence assembled from those words must be built with a
`_()` format string, never glued from fragments, or it cannot be translated.

### 2d. States that must be designed

- A range with **no budget** in any of its months.
- A range **wholly in the future** ("not yet"), and one that **straddles today**.
- A range where **one function spent nothing** — it keeps its tile, because a board
  whose tiles rearrange on every press is a board nobody can learn (the existing
  `_matrix` docstring says this; honour it).
- A **shift-press with no anchor** (the reader shift-presses first) — treat it as a
  plain press, do not do nothing.
- A **drag that starts on a chip and ends off the strip**.
- A **deep link** naming a range half outside the fiscal year (clamped), wholly outside
  (falls back to the year), or malformed.
- The **currency-forcing note** and the **truncation** flag still behave under a range.

### 2e. Motion

The board already re-scopes visibly rather than blinking: tiles keep their places, keyed
by function id, and the fills transition their width. Keep that, and give the strip's
selection band the same treatment. All of it inside
`@media (prefers-reduced-motion: no-preference)`.

### 2f. Callers to sweep

`get_board` is called from: `pb_budget/models/pb_budget.py:719` (itself),
`pb_budget/models/budget_export.py:46` and `:64`,
`pb_budget/tests/test_budget.py:261` and `:276`,
`pb_budget/tests/test_budget_month.py:63` and `:318`, and
`pb_budget/static/src/js/budget_board.js:108` (positional). Sweep every one.

---

## 3. Design — the bar

> **extreme WOW, intuitive, out-of-this-world experience, best in class.**

**Name the hero moment in your report.** The intended one: the reader drags across four
chips and the whole board — every number, every word, every colour, the headline
sentence — becomes about those four months under their hand, with the chips beneath the
cursor fusing into one band as they go.

Benchmark against the date-range control in a modern analytics tool, not against a stock
date filter. Zero dead-ends: every state in §2d designed, every failure naming its
reason and its next step. Plain language everywhere. Full keyboard parity. Lucide via
`ic()`, no emoji.

---

## 4. Tests (numbered — run on p9clone, report each one)

1. **The parity proof (R3).** `get_board` for the year and for each of the twelve months
   is byte-identical before and after the refactor. Shipped as a test.
2. A quarter selects exactly three months and its totals equal the sum of those three
   months read one at a time.
3. A shift-press range in each direction; a drag range; a drag that leaves the strip.
4. **The collapse rules (R1)**: a range of one reports `kind: 'month'`; a range of twelve
   reports `kind: 'year'`; the payloads match those scopes read directly.
5. **Fiscal-year quarters (R5).** Set `pb_budget.fy_start_month` to 7 and prove Q1 is
   July–September, the label says so, and `_fy_label` still prints `2026/27`.
6. **Pace.** A range wholly past = 100, wholly future = 0, straddling today = the
   elapsed share; a range of one month equals today's `_month_pace` exactly.
7. **Deep links (R6).** `month:2026-03`, `month:current`, `month:2026-03..2026-06`,
   `month:Q2`, a range half outside the year, one wholly outside, and a malformed one —
   none errors, none lands on an empty board, and the ⌘K "Budget this month" row still
   works.
8. **Exports.** Spreadsheet and PDF for a range: the figures match the screen to the
   digit, and both name the stretch.
9. **Keyboard only**, including `Shift`+arrows extending from the anchor, `Home`/`End`,
   and Escape's ladder (dialogs → drill → period).
10. **T23 does not come back**: hold the keyboard on a chip, re-scope, and prove the next
    arrow press goes where it should.
11. Every state in §2d, screenshotted.
12. **Vietnamese**: the range names, the headline sentence, the quarter labels and the
    export titles.
13. **Reduced motion.**
14. **Nothing regressed**: the full `pb_budget` suite green (including
    `test_budget_month.py`), neighbours at the same pre-existing baseline. **The
    baseline as of P2: a wide run of 262 tests with 3 failures, all the recorded
    p9clone drift (`pb_contracts` ×2, `pb_group` `test_t9`).** Report against that
    number rather than claiming zero.
15. **No literal per cent sign reaches a screen** (L9): grep the deployed bundle and the
    rendered DOM for `%%`, on both the English and the Vietnamese walk.

---

## 5. Deploy

`pb_budget` only. Bump the manifest to **19.0.2.2.0**. Ledger deploy ritual exactly, all
four databases in order p9clone → payobook → abm → payobook_template, `pg_dump` first.

**T20 applies to this module specifically**: `pb_budget` ships an `ir.cron`
(`data/ir_cron.xml`), and an upgrade fails outright with a `ParseError` naming that XML
if the cron happens to be RUNNING. Read the failure for the phrase "currently being
executed" before believing the XML is broken, and retry a minute later.

Python and assets both changed, so a real `-u`, then purge `/web/assets/%` **and** bump
`web.assets.version` per database, then Chrome-MCP load the board.

---

## 6. Report back

Write `docs/handovers/LOOK_P3_REPORT.md`, append gotchas to `LOOK_LEDGER.md` (continuing
the L-series) plus one phase-log line, and return a summary covering: each numbered test
with its result and evidence (screenshots in `docs/handovers/look_p3_shots/`); the hero
moment named; the self-score against the design bar; the parity proof; any ruling you
bent and why; anything this handover got wrong about the code; the four databases'
versions and tree hashes; the commits (feature-scoped, explicit `git add`, **not
pushed**); and anything the owner has to decide.

Do not start P4. Report and stop.
