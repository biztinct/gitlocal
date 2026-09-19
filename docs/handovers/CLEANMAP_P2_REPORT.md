# CLEANMAP P2 — phase report

**Built 2026-09-19/20 by Opus, from `CLEANMAP_P2_JOURNEY_HANDOVER.md`.**
Shipped as `pb_formula_studio 19.0.1.200.0`. Live on `payobook`, `abm`,
`payobook_template`, `rize`, `rztest` (+ the `p9clone` test clone). Nothing
pushed.

## 1. What the Journey does now

The payload was inverted. v1 took a CENSUS of the database — every connector,
every feed of every connector, every sheet of the stored file, every
transformation rule anywhere — and then drew edges between whichever of those
happened to be wired. v2 builds the field-level LINKS first, from
`_declared_sources` and nothing else, and derives the cards from them. A
connector nothing on this scheme reads has no card; a feed no field of which
is linked has no card; a rule nothing consumes has no row.

`journey_data` returns `v: 2`, five lane keys (`systems, feeds, transforms,
scheme, source`), `links` between ROW ids, `contains` between card ids, and
`invite` for the zero state. An empty lane list means the lane is hidden and
takes no grid column.

## 2. Tests 1–31

### Python — `tests/test_cleanmap_journey.py` (new), run on `p9clone`

`odoo-bin -u pb_formula_studio --test-enable --test-tags /pb_formula_studio`,
final run **1 failed of 449** — and the one failure is pre-existing (§2.3).

| # | test | result |
|---|---|---|
| 1 | `v == 2`, lanes exactly systems/feeds/transforms/scheme/source, no `run` | PASS |
| 2 | a connector with zero wires draws NO system, feed or transformation card | PASS |
| 3 | one wire → one system card, exactly one feed card, one row, one `contains` | PASS |
| 4 | a consumed transformation: `t:` card, one row, `reads` links, and the feed rows those reads name | PASS |
| 5 | an unconsumed transformation rule is absent | PASS |
| 6 | file rows == the Spreadsheet board's accepted `c:` wires (same rule ids) | PASS |
| 7 | a letter alias lands on the heading's row; an absent key is `state: 'gone'` | PASS |
| 8 | `employee_field`/`contract_field` = `both`; `bank_account` = `fwd`; `contract_component` and `period` = `back` | PASS |
| 9 | scheme rows == inputs in sequence order; `folded.n` == calculated + constant; `fed + unfed == inputs` | PASS |
| 10 | two declared sources → two links, counted `fed` once | PASS |
| 11 | a non-primary wire is `dimmed`, does not feed, and its card carries the chip | PASS |
| 12 | every non-scheme card's rows sort by the scheme row they reach (file order deliberately reversed in the fixture) | PASS |
| 13 | zero state: scheme card alone + `invite` with three doors | PASS |
| 13b | a disabled lane takes its invitation door with it (SC-4) | PASS |
| 14 | every link end resolves to a row that exists; ids globally unique | PASS |
| 15 | MF37 row-count + id-sum diff across two `journey_data` calls = ∅ | PASS |
| 16 | `get_available_source_fields` is never called (patched, `assert_not_called`) | PASS |
| 17 | query budget: one read of a 12-input scheme with 6 wires stays ≤ 80 queries | PASS |

### Browser — Chrome MCP, `rize.payobook.com`, signed in as `ash@biztinct.com`

Console read on every step: **clean, no errors and no warnings**, before and
after the restart. Screenshots in `docs/handovers/cleanmap_p2_shots/`.

**There is no dark variant of this cockpit on this build**, as P1 recorded.
Re-checked this phase: setting `data-theme="dark"` leaves a card's background
at `rgb(255,255,255)`, and no rule in the served bundle matches both `.jny`
and a dark selector. Nothing was regressed; there is simply no dark surface
here to photograph.

| # | check | result |
|---|---|---|
| 18 | Journey pill is LAST of eight; a cold start (no `pb_mode`) still lands on it | PASS |
| 19 | collapsed: three lanes (Files & systems, Scheme, Payobook Source). No Zoho, no feeds, no Transformations, no Pay run, no bottom-left records card | PASS |
| 20 | click the file card → 41 rows, lines fan from the rows INTO the closed scheme card; click again → one line badged `41` | PASS |
| 21 | all three open → row-to-row lines; 50 wires = 41 `excel` (one head), 7 `record` (two heads), 1 `component`, 1 `period` (one head each) | PASS |
| 22 | hover a file row → exactly 3 rows lit across three lanes and 2 wires; 95 rows and 48 wires fade. Click pins, Esc unpins | PASS |
| 23 | scheme card open: 6 unfed rows amber with "not fed"; "32 calculated or fixed" opens and closes on its own | PASS |
| 24 | corner icon lands on the Spreadsheet tab with the "← Journey" chip, which returns; the card body toggles and never navigates | PASS |
| 25 | reload → the same cards are open (per scheme, `localStorage`, every read/write in try/catch) | PASS |
| 26 | filter "Vị trí" → 3 matching/linked rows in temporarily-opened cards; clearing restores the previous open set exactly | PASS |
| 27 | keyboard: both card actions are `BUTTON` with a visible focus ring, Enter toggles, rows are `tabindex=0` and trace on focus, Escape clears | PASS |
| 28 | 390 px: lanes stack, wires hidden, each row names its partner as an inline tag, zero horizontal scroll | PASS |
| 29 | five lanes appear by themselves on a scheme with a system + transformations | PASS **by payload, not in a browser** — §7 |
| 30 | Vietnamese: every new string translated, no "Odoo" in the rendered DOM | PASS |
| 31 | 20 open/close cycles with all cards open: 0 new ResizeObservers, 0 of 50 wires detached from their row/card anchors | PASS |

### 2.3 The one failure, and what became of the two known reds

* **`TestJourneyTransformations.test_07a2_the_board_opens_on_a_connector_that_HAS_rules`
  — STILL RED, and still not this phase's.**
  `AssertionError: 2 != 3639 : a rule-less connector is not this board's default`.
  It exercises `_tf_active_connector` on the Transformations board, which P2
  does not touch, and it fails because `p9clone` (a clone of `payobook`) has
  six real transformation rules on connector 2, so the heuristic prefers that
  over the fixture's connector. P1 recorded it red on the baseline commit.
* **`TestJourneyView.test_03j_the_run_lane_is_a_ghost_when_nothing_was_processed`
  — GONE, replaced, and the replacement PASSES.** It asserted that
  `lanes['run']` held a ghost; the owner removed the pay-run column, so the
  subject no longer exists. It is now
  `test_03j_the_run_lane_is_gone_from_the_payload_and_still_works`, which pins
  both halves: the payload has no `run` lane, and `_journey_run_lane` (a
  binding non-goal — not deleted) still answers.

## 3. Every pinned assertion that was reversed

| file:line | was | is |
|---|---|---|
| `tests/test_journey_view.py:223` `test_03a` | lanes `systems, feeds, transforms, scheme, run`; "the run lane always has at least a ghost"; header keys `components, wired, fallback, attention` | lanes `systems…source`, `run` asserted ABSENT, `v == 2`, header keys `inputs, fed, unfed, attention` |
| `:244` `test_03b` | every NODE has id/kind/lane/label, ids unique | every CARD has those + `rows`; every ROW has id/card/label/tag/state; ids unique across cards AND rows |
| `:269` `test_03c` | `edges` between nodes, `from`/`to` | `links` between ROWS, `a`/`b`, `kind` in the seven, `dir` in fwd/both/back; `contains` between cards |
| `:292` `test_03d` | "exactly one connection is primary" | "at most one" — a connection is on the board only if something reads through it |
| `:312` `test_03d2` | health NODE `h:noprimary` in the scheme lane, labelled with a wire count | CHIP `noprimary` on the scheme CARD (ruling 11), plus: every system link is `dimmed` when no connection is chosen |
| `:360` `test_03f` | `counts['unread']` == every transformation rule on the DATABASE with an unread output | every transformation ROW drawn is a rule this scheme consumes (the census is the thing ruling 2 removed) |
| `:385` `test_03g` | the partition read off `lanes['scheme'][0]['counts']`; `header['wired'] == counts['wired']` | the partition read off the payload's `counts`; the scheme CARD carries a two-part `bar` that sums to `header['inputs']` |
| `:407` `test_03h` | `header['wired']` == components whose top declared kind is excel/feed/rule | `header['fed']` == components with at least one live LINK; `fed + unfed == inputs`; `wired` kept equal for one release |
| `:453` `test_03j` | `lanes['run'][0]` is a ghost when nothing was processed | no `run` lane in the payload; `_journey_run_lane` still answers |
| `:481` `test_03k` (absorbed `test_03k2`) | every lane ghosts on an empty scheme and every ghost has a door | every lane but the scheme is EMPTY on an empty scheme, and `invite` carries the doors |
| `:508` `test_03l` | every node door names a real mode | every card door, chip door and invite door names a real mode |
| `:536` `test_04a` | MODES ids `['journey', 'api', … 'treatment']` | `['api', … 'treatment', 'journey']` + the SC-4 fallback must name `"journey"` rather than take `modes[0]` |
| `tests/test_one_mapping_home.py:176` | same ids, journey first | journey LAST; the cold-start default is asserted unchanged |

## 4. The `data_source_field` question (handover §4.3)

**`hr.formula.rule.declared_sources()` does NOT include `data_source_field`,
and the Spreadsheet board still draws a wire for it.** The legacy column is
not a `source_ids` row and never was (`formula_rule.py:343` builds the list
from `source_ids` + the contract component + the pay-run key); the Spreadsheet
board's wire key is
`((source_binding_key) if source_binding == 'excel' else '') or data_source_field`
(`pb_formula_studio.py`, `import_mapping_data`).

So P2 applies the same fallback in `journey_data`: a component that declares
no `excel` source and carries a `data_source_field` gets an `excel` link on
that key. Without it a pre-binding scheme would read "unfed" on the Journey
and "mapped" on the Spreadsheet board — one scheme described two ways.
**Test 6 compares the two sets of component ids and passes.** No live database
has a component that relies on it (rize: 0 `data_source_field` on 48 inputs),
so nothing on screen changed; the fixture is what proves it.

## 5. Query counts — before (v1, 19.0.1.199.0) and after

Measured on the box, registry loaded from disk, caches invalidated between the
warm-up and the measured call (`cr.sql_log_count`).

| database | scheme | before | after |
|---|---|---|---|
| rize | Rize Vietnam Payroll (3938) | **45** | **17** |
| payobook | Viet Retail (18) | **718** | **21** |
| abm | AB Mauri Payroll (14) | **1 001** | **28** |

Two things paid for it: the feed/rule census and its per-connector
`get_available_source_fields` are gone, and the "source no longer exists" chip
stopped asking `binding_dangling` — on abm that single compute was **470 of
the 492** queries the first v2 cut still charged (ledger **CM13**).

Card counts fell with them. payobook's Viet Retail drew **33 system cards and
67 feed cards** for a scheme with eight wires; it now draws one system card
with eight rows.

## 6. What the rize Journey shows, in plain words

Opening Mapping on **Rize Vietnam Payroll** shows **three columns**, not five:

* **Files & systems** — one card, the workbook `Rize_Vietnam_Payroll_Templatev2
  DATA.xlsx`, "41 columns used". Open it and 41 rows appear, each with its
  spreadsheet column letter in a small grey gutter, in the order the scheme
  reads them rather than the order the file stores them.
* **Scheme** — "Rize Vietnam Payroll · 48 need a source", a green bar reading
  **42 fed** and **6 not fed yet**, and 48 rows. The six with nothing behind
  them wear an amber dot and the words "not fed": *Phụ cấp khác (Others)*,
  *KPCD 0.5%*, *Bảo hiểm cao cấp cho người phụ thuộc*, *Lương cơ sở*, *Cap
  lương đóng BHXH*, *Cap lương đóng BHTN*. One folded line at the bottom says
  "32 calculated or fixed" and opens on its own.
* **Payobook Source** — "9 fields · 4 kinds", in four labelled groups:
  Employee (4), Contract (3), Contract pay components (1), Pay run (1), with
  the "Open Records Desk" button under it.

Closed, the three cards are joined by three counted lines: **41**, **7** and
**2**. Nothing is `gone`, nothing is `dimmed`, and there are no warning chips.

The word "Payobook" is brand-substituted per tenant, so on rize that column
reads **"Rize Source"** in English and **"Nguồn Rize"** in Vietnamese
(ledger **CM21** — that is `biz_debrand` working, not a translation gap).

### Every scheme on every database, swept

No `gone` row and no `dimmed` link **anywhere** — on any scheme, on any
database. One `twice`: abm's *ID Card Number* is fed by two sources and the
scheme card says "1 fed twice".

| database | scheme | inputs | fed | not fed | lanes drawn |
|---|---|---|---|---|---|
| rize | Rize Vietnam Payroll | 48 | 42 | 6 | files, scheme, source |
| rize | Rize India Payroll | 28 | 28 | 0 | files, scheme, source |
| rztest | Rize Vietnam | 57 | 53 | 4 | files, scheme, source |
| abm | AB Mauri Payroll | 54 | 52 | 2 | **all five** |
| payobook | VPTQ End Cycle | 50 | 30 | 20 | scheme, source |
| payobook | VPTQ Mid Cycle | 49 | 29 | 20 | scheme, source |
| payobook | Viet Retail | 98 | 8 | 90 | systems, scheme |
| payobook | Payobook Construction — End-Month | 8 | 2 | 6 | systems, scheme |
| payobook | 17 other schemes | — | 0 | all | scheme only, with the invitation |
| payobook_template | *(no schemes at all)* | — | — | — | — |

Seventeen of payobook's twenty-four schemes have nothing mapped and now show
the designed invitation — "Nothing feeds this scheme yet" with three doors —
where v1 showed five lanes of ghosts over two connectors and fourteen feeds.

**Owner debts surfaced (plain words):**

1. **Viet Retail on payobook reads only 8 of its 98 columns.** The other 90
   have no source at all. It was impossible to see before, because the board
   drew a hundred cards over it.
2. **abm's "ID Card Number" is fed twice.** A pay run reads one of the two and
   ignores the other. The scheme card says so; which one wins is the feed.
3. **rize's six unfed components** (list above) include two that P1 already
   raised: the duplicate *Phụ cấp khác (Others)* that nothing feeds.

## 7. Deviations from the spec, and why

1. **The "source no longer exists" chip is derived from the links, not from
   `binding_dangling`** (ledger **CM13**). The handover says "no
   `get_available_source_fields` call at all"; `binding_dangling` reaches it
   through its per-source compute, so asking that field would have broken the
   promise and cost 470 queries on abm. The Journey's claim is now "nothing on
   this board can draw it", which the picture can defend. Consequence: abm's
   "needs attention" went 2 → 1.
2. **`canon()` is `_sample_alias_map`, not `_column_alias_map`.** The handover
   names P1's `_column_alias_map`; that one folds the RAW STORED KEYS of a
   loaded pay run. The Journey's file card is the STORED FILE, whose columns
   already carry `preferred`/`header`/`letter`, and `_sample_alias_map` is the
   helper built for exactly that shape (it is what `import_mapping_data` uses
   for `source == 'sample'`). `_journey_file_index` wraps it and adds the two
   spellings a person types by hand — a bare heading and a bare column letter
   — which is what test 7 exercises.
3. **The scheme card carries `bar` (fed / unfed / total) rather than the v1
   six-segment `counts` bar.** Ruling 10 asks for a calm board; six segments
   and six keys under a card that is now also a 48-row list is not calm. The
   partition is still in the payload's `counts` and is still asserted.
4. **The invitation's doors are filtered SERVER-side** by the scheme's lane
   flags, not client-side by the host's visible `modes`. Same result, one
   definition; a second copy of the rule in the client is how two surfaces
   come to disagree.
5. **Row order inside the Payobook Source card is group-first.** The handover
   fixes the group order (Employee · Contract · Bank · Contract pay components
   · Pay run) AND says rows follow the scheme; the two can disagree, and the
   groups win. The lines cross a little inside that one card as a result, and
   that is the right trade: a reader looks for "the contract fields", not for
   the straightest line.
6. **The gutter is 24px a side, not the v1 14** (ledger **CM17**) and lanes
   stretch to equal height (**CM16**) — both found by looking at screenshots,
   neither in the spec.

## 8. Deploy / verify

`pb_formula_studio` only, `19.0.1.199.0` → **`19.0.1.200.0`**. Clean staging
dir `/tmp/deployCM2`, per-module `rsync -a --delete` into
`/odoo/odoo-server/addons/pb_formula_studio/`, every database upgraded,
`/web/assets/%` attachments purged and `web.assets.version` bumped per
database, service restarted.

**PO parse gate** (run on the box, over all 20 k `.po` files in the addons
tree): **0 failures**. `pb_formula_studio/i18n/vi_VN.po` now reads **2 338
rows, 2 299 of which reach a screen** (was 2 304 / 2 265 at P1) — the 34
appended entries all carry `#. module:`, `#. odoo-python` or
`#. odoo-javascript`, and a valid `#: code:addons/…:0` occurrence. The file
was APPENDED to, never regenerated.

**Content check** — SHA-256 over every file of the module tree (skipping
`__pycache__`, `*.pyc`, `.DS_Store`), repo vs server:

```
repo   9cc7ce7142cb83ab6858b60b150af71425e11a3947eab8a1dbd53a07d03ff0d3
server 9cc7ce7142cb83ab6858b60b150af71425e11a3947eab8a1dbd53a07d03ff0d3
```

**Version check** — `ir_module_module.latest_version` per database:

| database | pb_formula_studio | upgrade exit |
|---|---|---|
| payobook | 19.0.1.200.0 / installed | 0 |
| abm | 19.0.1.200.0 / installed | 0 |
| payobook_template | 19.0.1.200.0 / installed | 0 |
| rize | 19.0.1.200.0 / installed | 0 |
| rztest | 19.0.1.200.0 / installed | 0 |
| p9clone *(test clone)* | 19.0.1.200.0 / installed | 0 |

`addons_path` is still the single entry `/odoo/odoo-server/addons`. Service
`active` after the restart; the rize board re-rendered from the regenerated
bundles with a clean console.

## 9. Ledger

New entries **CM13–CM21** in `CLEANMAP_LEDGER.md`.

## 10. What I could not do

* **Test 29 was proved by payload, not in a browser.** It needs a scheme fed
  by a connected system WITH transformations, and the only one on the cluster
  is `abm`'s AB Mauri Payroll — a database there are no credentials for (a
  standing owner debt; `abm.payobook.com` was also retired by the owner on
  2026-09-15). The payload read straight off `abm` shows the five lanes
  appearing by themselves, with the card-by-card shape the handover describes:

  ```
  systems    file   ABM Data.xlsx           26 columns used     rows=26
  systems    c:3    Zoho People (ABM)       1 field read here   rows=1  [Primary]
  feeds      e:1    Employees               16 fields used      rows=16
  feeds      e:2    Attendance summary       3 fields used      rows=3
  feeds      e:3    Overtime requests        3 fields used      rows=3
  feeds      e:4    Salary form              1 field used       rows=1
  transforms t:3    Transformations          7 rules            rows=7
  scheme     scheme AB Mauri Payroll        54 need a source    rows=54 [1 fed twice]
  source     source Payobook Source         42 fields · 4 kinds rows=42
  links  excel 26 · feed 20 · rule 7 · reads 20 · record 18 both + 3 fwd · component 21 back
  ```

  The three bank rows are `fwd` and never `both`, live — J3 S1's exception,
  which no other database could show.
* **The Settings-card door was proved from source plus cold starts**, not by
  clicking through Settings: `test_04c` pins that the Settings hub still
  carries no `pb_mode`, and every one of the six page loads in this session
  landed on the Journey with the pill last.
* **No live example of a `gone` row or a `dimmed` link exists on any database**
  (swept, §6), so both are proved by tests 7 and 11 and by the styling rather
  than by a screenshot.

---

# CLEANMAP P2 — follow-up, `19.0.1.201.0`

Two defects found by the coordinator in `03_all_open.png`. Both were real,
both are fixed, and both had the same underlying character: a number that was
never checked against the thing it describes.

## A. The tag gutter was showing the wrong column letters

**What it was.** `Mã nhân viên (Code)` — the first column of rize's Salary
sheet — showed **AP**. `Họ và tên` showed **AD**, `Vị trí` **FG**, `Loại`
**AK**. The true letters are A, B, C, D.

**Where it came from.** `peek_source_columns`
(`payroll_import_batch.py:577`) stores a `letter` beside every column and
computes it as `index_to_letter(headers.index(header))`. On a MERGED
multi-sheet workbook `headers` is the merged key list — 174 entries on rize,
in the loader's own order — so the index it finds is the heading's position in
that merged list, not the column's position in its own sheet. The Journey read
that stored value straight off.

It had gone unseen because the only screen that showed it was the Spreadsheet
board's **template-file** FROM. Its **pay-run** FROM letters positionally
(`_multisheet_fold`: `_index_to_letter(pos)`), so the two FROM choices of one
board had been describing one workbook two ways, and P2 inherited the wrong
half.

**The fix.** A new `_sample_column_letters(config)` gives each stored-file
column its position among the cards of ITS OWN SHEET — the pay-run lane's rule
exactly. The Journey's row tag and the Spreadsheet board's template-file lane
both read it, so the two boards and the two FROMs now agree. The loader and
the stored JSON are untouched: this is a display derivation, so no database
has to be re-read.

**Verified on rize** (config 3938, all 41 mapped columns):

```
journey rows 41 · template-file lane 43 · pay-run lane 43
journey vs template-file lane mismatches: 0
journey vs pay-run lane mismatches:       0
tags in row order: A B C D E F G H I J M N O P Q R S T U V W X Y Z
                   AA AB AC AD AE AF AG AH AI AJ AK AL AM AN AO AP AQ
```

They run in order, with **one gap: K and L are missing**. That is correct and
worth reading — the workbook has 43 headings, the scheme maps 41 of them, and
the two it does not map are the sheet's 11th and 12th columns. The Journey
draws only what is mapped (ruling 2), so the gutter shows the gap rather than
renumbering around it.

Two new tests pin it: `test_12b` builds a merged fixture whose STORED letters
are all deliberately `ZZ` — so it fails against the stored value and passes
only against the walk — and then asserts the Journey and the Spreadsheet board
give each column the same letter; `test_12c` pins that a second sheet starts
its own letters again at A.

## B. The lines were nearly invisible with cards open

**What it was.** 45px between two cards. `wireGeometry` puts its control
points at 45% and 55% of the run and reserves 11px at the tip for the
arrowhead, so a row-to-row line had ~34px to be a curve in: what reached the
screen was an arrowhead with a smudge behind it. The resting stroke — 1px at
35% of the line token — then finished the job.

**The fix**, three parts, all measured rather than nudged:

| | before | after |
|---|---|---|
| gap between two cards (3 lanes, 1512px) | **45px** | **81px** (`--jny-gut` 24 → 40 a side) |
| resting stroke | 1px @ 35% | **1.25px @ 45%** |
| trace stroke | 2px @ 100% | **2.25px @ 100%** |
| containment (dotted) | 1px @ 50% | 1.25px @ 55% |
| not-read (dimmed) | @ 22% | @ 30% |

The run comes out of the lane's own padding, so no label lost width. Four and
five lanes step down (`--jny-gut` 32 / 26 via an `n4`/`n5` class on the lane
grid) because a card narrower than ~200px is a worse trade than a shorter
curve, and the narrow ladder is 30/24/18 below 1400px and a flat 16 below
1180px.

**One thing the stylesheet could not fix on its own.** The count-thickness
rule writes `stroke-width` as an INLINE style, and inline wins: with its base
at `1`, every single-link line silently went back to a hairline the moment the
sheet said 1.25. The base is now the resting width (`1.25 + min(3, log2(n))`),
and the trace's `!important` still beats both.

**Count badges re-checked in the collapsed state**: the three badges (41, 7,
2) sit at x = 479, 963 and 974 against lines whose midpoints are 479, 968 and
968 — on the line, with `spreadHubs` separating the two that share a pair by
22px vertically.

## Tests, deploy and verification

* **1 failed of 451** on `p9clone` (449 + the two new letter tests). The one
  failure is the same pre-existing
  `TestJourneyTransformations.test_07a2`; every other test, including all 19
  in `test_cleanmap_journey.py`, passes.
* `node --check` clean on `journey_board.js` and `mapping_studio.js`; the XML
  parses; the SCSS bundle rebuilt and was read back off the live page.
* `19.0.1.200.0` → **`19.0.1.201.0`**, upgraded on **payobook, abm,
  payobook_template, rize, rztest, p9clone** (all `EXIT=0`), `/web/assets/%`
  purged and `web.assets.version` bumped per database, service restarted and
  `active`.
* Content hash repo vs server:
  `0f8744f130c76a0dc2f8996ef6033bbc6f80e220867b899193bb79e008df6932` on both.
  `latest_version` `19.0.1.201.0 / installed` on all six.
  `addons_path` still the single entry.
* **Console on rize: one message, and it is not ours** — a PWA manifest
  icon-size warning from `biz_debrand`
  (`brand_icon.png`, "Resource size is not correct"), present before this
  phase.
* Screenshots re-taken into `docs/handovers/cleanmap_p2_shots/`: **02, 03, 04,
  07** as asked, plus **01, 05, 06, 08, 09**, because every one of them showed
  either the wrong letters or the old 45px gutter and leaving them would have
  documented a board that no longer exists.

## Ledger

New entries **CM22–CM24** in `CLEANMAP_LEDGER.md`.
