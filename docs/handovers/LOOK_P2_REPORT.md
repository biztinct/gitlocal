# LOOK P2 — "Everybody on the calibration picture" — phase report

**Status: COMPLETE.** `pb_pay` **19.0.3.3.0** live on p9clone, payobook, abm and
payobook_template.

Scope kept: **`pb_pay` only** — server and browser, no schema change, no migration, no
new model. One abstract-model method changed shape (`pb.pay.reviews.calibration`), one
was added (`calibration_people`), the shared picture arithmetic gained a general form,
and the two pre-existing defects the phase was given (L7, L8) are closed.

---

## 1. The hero moment

**Four and a half thousand people open as five honest distributions, and nobody is
hidden behind anybody.**

The calibration picture used to slice `review.line_ids[:900]` and print *"The picture
draws the first 900 people."* — on the one screen where the people at the edges are the
entire point of the meeting. It now changes SHAPE instead. On the rehearsal review of
**4,510 people** the picture draws **117 bars and 102 individual marks**, and the sum of
what every drawn element accounts for is **4,510 exactly**, measured in the browser
against the row count in the database.

What a reader sees in one glance, which the old picture could not show at all:

| | |
|---|---|
| The spread of each score | five ridges, each the shape of that score's own rises |
| Where each score's middle sits | 0.12% · 2.99% · 4.46% · 5.92% · 7.94% |
| Whether one score overlaps the one below | yes — visibly, "Doing well" and "Very strong" share most of their range |
| Where the limit cuts across | a dashed line at 12% over the whole picture |
| Who is worth arguing about | 123 marks ringed on top, each one draggable |
| Who is standing anywhere | press a bar: 148 names, with their rises editable in place |

Screenshot: `look_p2_shots/01_p9clone_hero_4510.png`.

## 2. Self-score against the design bar

> **extreme WOW, intuitive, out-of-this-world experience, best in class.**

**8.5 / 10.** What earns it:

- The picture is the one a calibration meeting actually wants — a violin per score with
  the middle marked and the limit drawn across it — rather than a cloud of dots that was
  never readable at any size.
- **Zero dead-ends, every state designed and screenshotted**: nobody in the review, one
  person, twelve people, everybody on the guidance, one score used by everybody, a score
  nobody used, ten people nobody scored, 902, 4,510, a bin nobody is standing in, a
  read-back that fails, a reader who may see no names, a phone, and a keyboard with no
  mouse.
- **The picture proves its own honesty**: every drawn element carries how many people it
  accounts for, the sentence under it says "All 4,510 people in this review are on the
  picture", and both are checkable from the DOM.
- **A gesture that answers**: the mark under the hand moves 29/59/89/119 px for a hand
  that moved 30/60/90/120, names the person while it is held, and the whole picture —
  medians, limits and what counts as standing out — is read again in **87 ms**.
- Full keyboard parity at the same resolution as the mouse, Lucide icons only, plain
  language, Vietnamese complete.

What holds it back from 10:

- A phone gets a 192 px-wide plot for five columns. It is honest and it draws everybody,
  but a calibration meeting is a desktop act and the phone is a reading surface.
- The reason on a blocked row is a STORED chip, so it is written in the language of
  whoever last recomputed the review (L14) — pre-existing, and now more visible.
- The `pbim` kit still has no dark palette (GR38).

## 3. The numbered tests

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | `node band_picture_check.mjs` — P1's cases untouched, new `binValues` cases | **PASS** | 34 → **44 checks passed**, exit 0. New: T3p counts add back up over 400 random boards of up to 4,500 values with values beyond BOTH ends (count, per-state and item totals all equal); T3q ordered, non-overlapping, inside the track; T3r a value past either end clamped ON and still counted; T3s empty and missing input; T3t a classifier answering `undefined`, a number, an empty string or an unexpected word loses nobody (filed under `other`, count unchanged) and no classifier at all still bins five people; T3u a bin keeps its items in arrival order; T3v the wrapper's bins ARE the general form's bins and still carry `below`/`inside`/`above`. |
| 2 | **Nobody is dropped** | **PASS** | Sum of `data-people` over every drawn element, in the browser, against a SQL row count: **4,510 = 4,510** (117 bars + 102 marks), **902 = 902** (5 bars), **12 = 12** (1 bar + 6 marks). Re-measured after a drag: still 4,510. |
| 3 | **The cap is gone** | **PASS** | `MAX_DOTS` appears in no file in `pb_pay`; `the first %(count)s people` and `not drawn` appear in no shipped string, template, stylesheet or catalogue (they survive only in two engineering comments, which R118 explicitly allows). Both catalogue entries deleted. Test-enforced by `test_no_picture_in_this_module_draws_only_the_first_n_people`. |
| 4 | **The medians are right** | **PASS** | Server payload against the guidance the rows were built from: 0.12 / 2.99 / 4.46 / 5.92 / 7.94 for the five scores, and the unit test `test_t05_each_column_carries_the_middle_of_its_own_score` pins a constructed median of 6.0 over rises of 2/6/10. The column also carries `scored` and `drawn` separately, because they differ by exactly the ten people nobody scored. |
| 5 | **The limit line is right** | **PASS** | A blocking `max_raise_pct` of 12% draws at the right height across the whole plot, its own sentence is in the legend under it ("Nobody rises by more than 12%."), **23 people above it read `blocked`** and are ringed rose, and the list under the picture gives each of them the row's own sentence: "14.74% is above the 12% this review allows." |
| 6 | **`max_pct` covers the limit** | **PASS** | The 902-person review's highest proposal is 8% and its warning limit is 15%: the axis runs to **16.2%** and the limit is drawn inside the picture with room for its own line. `look_p2_shots/04_p9clone_flat_902.png`. |
| 7 | **The drag still works** | **PASS** | On an outlier: hand +30/+60/+90/+120 px → mark +29/+59/+89/+119 px, the foot bar reading "Huỳnh Văn Tuấn · 10.73% / 9.47% / 8.2% / 6.94%" while the mouse was down. Saved **6.94%** and **8.75%**, both read back from `pb.pay.review.line` to the digit. **The re-read after a drag at 4,510 people took 87–124 ms**, so the full `calibration()` re-read was kept rather than a partial merge — the medians, the limits and what counts as standing out all move when one rise does. |
| 8 | **The bin panel** | **PASS** | Pressing the busiest bar opens "148 people scored Doing well, rising 3.84% to 4.13%" with 40 named rows, each rise editable in place, and "and 108 more standing here." A loading line ("Reading the names…"), a failure line that names its reason and its next step, an empty line, and **Escape closes the panel first and the picture second** (proven in that order). |
| 9 | **Permissions** | **PASS** | The payload that DRAWS the picture carries four keys per person and no name at all — `line_id`, `column`, `pct`, `state` — test-enforced. A `group_pay_viewer` who manages a team reads their own team's rows, `can_names` is false, and no real name appears in the outlier list or in the bin panel. |
| 10 | **Every state in §2c** | **PASS** | Nobody (`06_…`), twelve people with individual marks (`05_…`), one score used by everybody with four empty-but-labelled columns (`07_…`), everybody on the guidance with the note (`04_…`), 4,510 (`01_…`), ten people nobody scored drawn in the middle column and counted separately ("2068 people, 10 not scored"), a phone at 390 (`08_…`), Vietnamese (`09_…`). |
| 11 | **Speed** | **PASS** | `calibration()` on p9clone, warm: **12 people 3–4 ms · 902 people 20–34 ms · 4,510 people 85–119 ms** (one 248 ms reading under load). The P6b baseline was 162 ms for 902, so 902 is **five times faster** and 4,510 — five times the people — costs less than the old 902 did. |
| 12 | **Nothing regressed** | **PASS** | See §6. |
| 13 | **Vietnamese** | **PASS** | 812 terms, 0 empty, 0 fuzzy, 0 lost placeholders, 0 entries without their `#. module:` comment, the word "Odoo" in no translation, and the `.pot` header rewritten to Payobook (WF27). Walked live. |
| 14 | **Reduced motion, and keyboard only** | **PASS** | See §4. |
| 15 | **L7 and L8 fixed** | **PASS** | See §5. |

## 4. Reduced motion and the keyboard

**Reduced motion (R85's proof, because Chrome MCP cannot emulate the media feature).**
The deployed bundle was fetched and read back. All four moving declarations this phase
added sit INSIDE `@media (prefers-reduced-motion: no-preference)`, each appears exactly
once in the whole bundle, and `@keyframes pay-cbar-in` is at the top level of the
stylesheet where a browser will play it:

```
.pay-cbar   {transition: left/width/background-color; animation: pay-cbar-in}   guarded
.pay-cdot   {transition: background-color, box-shadow}                          guarded
.pay-cmed, .pay-cmed-l {transition: bottom}                                     guarded
.pay-climit {transition: bottom}                                                guarded
```

Under a reduced-motion preference none of them is applied at all, so the picture paints
finished on the first frame with nothing to recover from.

**Keyboard only, end to end.** A mark takes focus; `↑` moves the rise by a tenth of a
point and `Shift+↑` by half a point; `Enter` saves; `Escape` puts it back. Measured:
3.0 → 3.1 → 3.3 → 3.8 → 3.7, `Enter`, and `pb.pay.review.line` reads back **3.7**.
Escape during a keyboard gesture cancelled it and left the value at 3.7 while keeping
the picture open — the gesture is the FIRST rung of the capture-phase ladder (L5), the
bin panel the second, the drawers the third and leaving calibration the last.
`aria-pressed` reads `"true"` while a mark is held and `"false"` when it is not — the
ternary form L1 requires.

## 5. The two debts this phase was given

**L7 — the shared money scale said "1 people".** `_lane_axis` built one sentence for
every count. The WHOLE sentence now branches on the count, verb included (R117), and the
singular wording is the one P1's browser-side tails already use, so it is the same term
in the catalogue rather than a second one. `_family_axes` computes a family's own scale
through `_lane_axis`, so it is fixed too. Test: one person beyond the edge reads
"1 person is paid more", three read "3 people are paid more", nobody reads nothing.

**L8 — a refused band move raised an undo bar saying "Band moved."** `move_edge` answers
a refusal rather than raising it and writes nothing; `endDrag` wrote `state.undo` from
whatever came back. It now reads `answer.ok` first, shows the server's own sentence as a
warning, reads the board again so the picture returns to what is actually saved, and
raises no undo bar. Two tests, one each side.

## 6. Tests

**`pb_pay` on p9clone: 117 tests, 0 failed, 0 errors** (P1's baseline was 111; this
phase added six and rewrote five). The suite covers, new this phase: the payload holds
everybody and carries no cap and no names; the three states; a rise that breaks a limit;
each column's own median; a score nobody used; a person nobody scored; the axis reaching
past its limit; the bin read-back; a half-open bin so nobody is listed twice; a reader
with no name role; two ends of a narrow range told apart; "1 person" on the shared axis;
a refused move that answers as a refusal; and the static gate that no picture in this
module draws only the first N people.

**The wider run over 262 tests** (`pb_pay` 125 collected / 117 post-install,
`pb_group` 54, `pb_contracts` 48, `pb_budget` 39, `pb_hub` 34) reports **3 failures and
0 errors**, and all three are the p9clone data drift this ledger has recorded since
GROUP P6a: `pb_contracts::test_22_the_picker_is_whitelisted`,
`pb_contracts::test_05_the_picker_is_whitelisted_and_answers` and
`pb_group::test_t9_the_screen_counts_what_the_roster_counts_and_is_quick`.
**That is the baseline. Zero regressions.**

`node pb_pay/tools/band_picture_check.mjs` — **44 checks passed**, exit 0, P1's 34
untouched.

## 7. Where the handover was wrong about the code

Four things, all found by building against it:

1. **`scale_words` is not translatable, and the picture made that impossible to ignore.**
   §2b says the columns carry "the rating's word (from `scale_words`)". Those five words
   were module-level literals in a dict, which the string extractor never sees as a
   Python term (T24), so they printed "Needs support / Doing well / Very strong /
   Outstanding" in English under every column of a fully Vietnamese picture. Fixed in
   `pb_pay_guidance.py`: the words are written inside `_()` calls in a dict keyed by
   value, and the order comes from a separate ladder (GR59).
2. **A `_t()` handed a DICTIONARY writes ONE per cent sign, not two.** WF24 is in the
   ledger and the first build got it wrong anyway: the bar labels rendered "0.00%% to
   0.30%%" live. Python's `_()` needs `%%` and the browser's `_t()` with keyword
   arguments does not, and the same sentence exists on both sides of this feature.
3. **The `MAX_DOTS`/`capped` grep in test 3 is broader than the ruling it enforces.**
   The word "capped" legitimately described the two LIST caps the spec itself endorses
   (`people_between`'s twenty, the outlier list's sixty) and a column-height cap in the
   band picture. Those three were reworded so the grep is literally clean, and the
   shipped test strips comments first (R118).
4. **`§2d`'s worry about the re-read was unfounded, in the good direction.** The full
   `calibration()` re-read after a drag costs 87–124 ms at 4,510 people because the
   payload is now one `search_read` of four columns rather than record iteration. No
   partial merge was needed; the changed figure is put into the loaded payload
   immediately so the mark does not jump back, and the whole picture is then re-read.

## 8. Rulings I had to bend, and why

**R3 — "a busy bin is pressable" needed one addition: the mark under the hand is exempt
from every cap.** A bin seven pixels tall can only hold a few rings before they draw over
each other, so a busy bin rings the first few of its standouts. Dragging a ringed mark
INTO such a bin therefore took the mark off the picture in the middle of the gesture —
the hand was still moving something and there was nothing on screen to see. The one under
the hand is now always drawn, wherever the gesture has taken it (L10).

**R2 — a mark is drawn at the middle of its own bin, EXCEPT the one being dragged.** Bins
are the shape; a gesture is not. Drawn at its bin's centre the dragged mark answered a
150 px hand in seven-pixel steps. The held mark is drawn at the exact figure the hand is
holding, which is what makes the gesture 1:1 (measured: 29/59/89/119 px for
30/60/90/120).

**§2b's `outliers` — the list says how many it did not name.** The spec keeps the
sixty-row cap and says a list "must say so in its own words when it does". With 123
standouts on the rehearsal review the sentence reads "63 more rises stand out. Every one
of them is on the picture; the biggest 60 are named here." — the cap is stated as a fact
about the LIST, and the picture's own promise is repeated in the same breath.

Nothing else was bent. R1, R4, R5 and R6 are as written and each is proven above.

## 9. The four databases

| Database | `pb_pay` | reviews | worksheet rows | guidance grids | scores | applied rows | bands |
|---|---|---|---|---|---|---|---|
| p9clone | 19.0.3.3.0 | 0 | 0 | 0 | 0 | 0 | 0 |
| payobook | 19.0.3.3.0 | 0 | 0 | 0 | 2 | 0 | 0 |
| abm | 19.0.3.3.0 | 0 | 0 | 0 | 0 | 0 | 0 |
| payobook_template | 19.0.3.3.0 | 0 | 0 | 0 | 0 | 0 | 0 |

One tree, one hash, verified against the repository over every file except
`__pycache__`, `*.pyc` and `.DS_Store`:
`fc1ec439c006d271e226a8c46aade2de2ebdb01df2304c4e2245eb427607079a` **both sides**.

The two `pb.pay.rating` rows on payobook are the two performance scores GROUP P6b kept;
they were there before this phase and are there after it.

`pg_dump` before every database:
`/odoo/backups/p9clone_before_look_p2_20260908_225636.dump`,
`payobook_before_look_p2_20260908_233118.dump`,
`abm_before_look_p2_20260908_233140.dump`,
`payobook_template_before_look_p2_20260908_233145.dump`.

Asset ritual per database: `/web/assets/%` attachments purged **and** the
`web.assets.version` `ir.config_parameter` bumped, then a service restart — on all four.
The translation cache is per worker and per bundle version, so a `.po` change needs both
(the Vietnamese picture printed English until the bump and the restart).

### What was created to test with, and the proof it is gone

**p9clone** carried four rehearsal reviews (4,510 · 902 · 12 · 0 people), one guidance
grid, 18,000 scores copied into them, three limits, a spread written over 4,510 rows,
one contract temporarily raised to ₫900,000,000 to make exactly one person sit beyond
the lane axis, and one validator. Every one of them is gone: **0 reviews, 0 worksheet
rows, 0 guidance grids, 0 scores**, the contract is back at **₫129,800,000** and the
lane note is empty again (`beyond 0`).

**payobook** carried one review of exactly 902 people (the Retail End-Month scheme,
narrowed by GROUP P2's own map), one guidance grid, 902 scores and one limit, for
eleven minutes. All gone; the two pre-existing scores are untouched.

**abm** carried one review of 152 people, one grid and one limit. All gone.

**payobook_template** was never written to at all beyond the module upgrade.

Every validator is archived again: `look.p2@payobook.com` on p9clone (id **4388**),
payobook (id **4428**) and abm (id **263**).

## 10. Commits (NOT pushed)

| Commit | What | Files |
|---|---|---|
| `ecc8c92d` | `feat(pb_pay): one binner, two pictures` | `static/src/js/band_picture.js`, `tools/band_picture_check.mjs` |
| `ba0f8d77` | `fix(pb_pay): the shared money scale says "1 person"` (L7) | `models/pb_pay_bands.py`, `tests/test_pay.py` |
| `dc7b4dff` | `fix(pb_pay): a band move that was refused no longer says "Band moved."` (L8) | `static/src/js/pay_hub.js`, `tests/test_static_contract.py` |
| `9121c7c3` | `fix(pb_pay): a score's word is a word, and a reader gets it in their language` | `models/pb_pay_guidance.py` |
| `7f5611b3` | `feat(pb_pay): everybody on the calibration picture` | the server, the browser, the stylesheet, the template, the tests, both catalogues, the manifest |

Explicit `git add` of named files every time. **Not pushed** — there are now **116**
commits waiting on `19.1` and pushing is the owner's decision.

## 11. What the owner has to decide

1. **Push, or keep holding.** **116** commits sit unpushed on `19.1`.
2. **The `payobook` administrator password in the ledger is still wrong (GR24), and so
   is `abm`'s (WF15).** This phase used one temporary `look.p2@payobook.com` on p9clone
   (4388), payobook (4428) and abm (263), **all three archived again at the end**.
   Resetting the owner's own password is an owner decision and was not done.
3. **A reason written on a row is frozen in the language it was written in** (L14). The
   sentence that says why a rise breaks a limit is STORED on the row when the review is
   recomputed, so a review last recomputed by an English reader shows an English reason
   to a Vietnamese one — on the worksheet, in "what stops approval", and in the
   calibration list. Pre-existing since the review shipped; the fix is to store the
   ingredients and build the sentence at read time, which touches every chip and is a
   phase of its own.
4. **Nobody has scored anybody on AB Mauri.** A review there draws all 152 people in the
   middle column and says "152 people, 152 not scored" — which is exactly right and is
   also a company that cannot calibrate anything until somebody records a score.
5. **The `pbim` kit still has no dark palette (GR38)**, so "dark" remains the platform's
   chrome only. Still a `pb_import_kit` release of its own.
