# LOOK P2 — Everybody on the calibration picture

**Read `docs/handovers/LOOK_LEDGER.md` in full first**, and the parent ledgers it names
(GROUP, TIDY, WFPLAN, RIZE), and **`docs/handovers/LOOK_P1_REPORT.md`** — P1 changed the
shared arithmetic this phase builds on, and its L-series gotchas bind you.

**Module touched: `pb_pay` only.** Server + browser. No schema change and no migration:
one abstract-model method changes shape and one new read-back method is added.

---

## 0. What you are building, in one paragraph

The calibration picture is the last place in this product that still drops people. The
server slices `review.line_ids[:900]` and the screen prints *"The picture draws the first
900 people."* — the exact sentence the LOOK ledger's rule 16 forbids, on the exact
screen where it matters most, because a calibration meeting is a meeting about the
people at the edges and the cap silently removes an arbitrary set of them. Even under
the cap the picture is not honest: nine hundred dots on four rating columns, nudged
sideways by a number derived from each row's own id, land on top of one another, so the
cloud a reader thinks they are reading is a few hundred dots with several hundred more
hidden underneath. **You are rebuilding it so that everybody is on it, always, at any
size** — the picture changes shape rather than capping, exactly as the band picture
does, and it gains the three things a calibration meeting actually asks for: the shape
of each score's spread, where the middle of each score sits, and where the limits are.

---

## 1. Rulings — decided, do not re-open

**R1. `MAX_DOTS` is deleted, not raised.** Along with the `capped` and `capped_note`
keys and the sentence they carry. A bigger cap is the same bug with a later onset. Grep
`pb_pay` afterwards and prove no cap survives.

**R2. The picture changes shape, the way the band picture does.** Along each rating
column the rise axis is cut into bins a few pixels tall. A bin holding a handful of
people draws each of them; a busier bin draws a bar whose length says how many, with its
exact count on its own label and in the list it opens. This turns each rating column
into a horizontal histogram of rises — which happens to be the picture a calibration
meeting wants anyway: *is this score's spread sane, and is it sensibly different from
the score below it?*

**R3. Not every dot needs to be draggable, and pretending otherwise is what caused the
cap.** Nobody drags four thousand five hundred dots in a meeting; they look at the shape
and pull on the exceptions. So:
- **Outliers are always drawn as individual, ringed, draggable dots on top of the
  shape** — they are what the meeting is about, and there are at most a few dozen.
- **A person drawn as their own mark in a thin bin is draggable**, exactly as today.
- **A busy bin is pressable**, and opens the named list of the people standing in it —
  the same gesture and the same kind of panel the band picture's columns already open —
  from which any one person can be adjusted.
The promise on the screen changes from *"Drag one and its row follows"* to a sentence
that is true at every size. Write it in plain English; do not leave the old one up.

**R4. Names are read back on demand, never sent for everybody.** Today every dot carries
`name`, `team`, `cost` and `position_pct`, which is both a payload and a permission
problem at scale. The compact set carries only what the picture needs to DRAW
(`line_id`, `rating`/`column`, `pct`, and the flags); names and details come from the
outlier list (already capped at 60, legitimately, because it is a LIST and not a
picture) and from a new read-back for one bin. Precedent to clone exactly:
`pb.pay.bands.people_between` + `pay_hub.js` `openPart` / `state.pop`.

**R5. Reading 4,500 lines may not go through record iteration.** The current code loops
`review.line_ids` and touches `line.employee_id.name` and
`line.department_id.display_name` on every one, which is the real reason somebody
reached for a cap. Use one `search_read` on `pb.pay.review.line` for the compact fields
only — `chips` is a stored `fields.Json` (`pb_pay_review.py:197`) so it costs nothing to
read, and `rating` and `proposal_pct` are plain stored columns. **Do not put
`employee_id` or `department_id` in that `search_read`**: the platform resolves a
many2one into `(id, display_name)` and that is a name lookup for every row.

**R6. The three states are `normal`, `outlier`, `blocked` — not below/inside/above.**
`blocked` is any line whose chips carry `blocks` (a limit says no). `outlier` is the
existing two-test rule, unchanged. Everything else is `normal`. Colour is never the
message: every mark's label and every list row says the word.

---

## 1b. What P1 already shipped, and the eight things it learned

**Verified in the tree, do not re-derive.** `pb_pay` is at **19.0.3.2.0** on all four
databases. `band_picture.js` now exports `axisSpan(axis)`,
`binPeople(wages, axis, trackPx, binPx, edges)`, `busiestBin(bins)`,
`dodgeDots(dots, axis, trackPx, minGapPx)` and `bandAxis(band, opts)`. The node check
runs **34** assertions (T3a–T3o) and must stay green untouched.

Five of P1's gotchas (**L1–L8** in the ledger — read them all) land directly on this
phase's work:

- **L1 — a boolean ARIA attribute must be written `cond ? 'true' : 'false'`.** OWL drops
  an attribute whose value is boolean `false`, so a closed disclosure carries no
  `aria-expanded` at all. Every ARIA boolean you add here follows the ternary form.
- **L2 — anything whose height depends on a translated sentence goes in NORMAL FLOW.**
  A fixed pixel growth is right in English at 1440 px and prints over the next element
  at 390 px. If a panel or a note has to animate in, animate the CONTENT arriving
  (opacity + a few pixels of travel), never a container height nobody can predict.
- **L4 — a picture that stops its ruler lying has to stop its MARKS lying too.** P1's
  ruler picks its decimals from the span; its bin labels did not, and read
  "12 people · 9.0M ₫ to 9.0M ₫" for a bin fifty thousand dong wide. **This applies
  directly to you**: your bins are a few pixels of a percentage axis, so a bin from
  7.02% to 7.14% must not print "7% to 7%". Both ends of any range printed on this
  picture take their figures from THAT range's own width.
- **L5 — a capture-phase Escape handler outranks every element's own.** The cockpit
  registers `keydown` on `window` with `{ capture: true }` (WF4). **A gesture in flight
  must be the FIRST rung of the ladder**, whatever the visual nesting says — so a drag
  in progress cancels before the bin panel closes, and the bin panel before the view
  leaves calibration.
- **L6 — `var(--pbim-pill)` is not defined anywhere** and neither is `--pbim-canvas`;
  an undefined custom property invalidates the whole declaration, so those radii resolve
  to 0 product-wide. Read `pb_import_kit/static/src/scss/import_tokens.scss` before
  borrowing a token name from a neighbouring rule.

Two of P1's findings are **owner debts on the server side of this very file's
neighbourhood**, and you may fix them in this phase because you are already in the
server: **L7** — `_lane_axis` in `pb_pay/models/pb_pay_bands.py` builds one sentence for
every count and says "1 people" (GR42's trap in the one place GR42 did not sweep);
**L8** — `endDrag` in `pay_hub.js` writes `state.undo` from whatever `move_edge`
answered, including a refusal, so the foot bar reads "Band moved." above a sentence
saying it was not. Both are small, both are in `pb_pay`, and both are exactly the kind
of thing this programme exists to stop. Fix them, in their own commits, and say so.

## 2. Deliverables

### 2a. The shared arithmetic learns a second use (`band_picture.js`)

P1 made `binPeople(wages, axis, trackPx, binPx, edges)` take an axis object. This phase
needs the same binning along a DIFFERENT axis (a rise in percent, not money) with a
DIFFERENT three-way split (R6). Do not fork it and do not bend the edge semantics:

- Add **`binValues(values, axis, trackPx, binPx, classify)`** — the general form.
  `values` is `[{ value, ...anything }]`; `classify(item)` returns a state string; the
  result is one entry per non-empty bin carrying `x0`, `x1`, `low`, `high`, a count per
  state, and `count`. Ordering, the clamp-onto-the-edge rule and the "counts always add
  back up to `values.length`" promise are exactly as `binPeople` already guarantees.
- Re-express **`binPeople` as a thin wrapper** over `binValues` with the
  below/inside/above classifier, so the band picture cannot drift away from the
  calibration picture. Its exported signature and behaviour must not change — the P1
  node cases must still pass untouched.
- The file's standing rule holds: **no import from `@odoo/owl` or `@web/…`**, ever.
- Extend `pb_pay/tools/band_picture_check.mjs` with numbered cases for `binValues`.

### 2b. The server (`pb_pay/models/pb_pay_reviews.py`, `calibration`)

Rewrite `calibration(review_id)` to return, for a review of any size:

- `people` — the compact set, EVERY line, no slice: `line_id`, `column` (1…levels,
  clamped, with an unscored person still placed in the middle column as today), `pct`,
  and `state` (`normal` | `outlier` | `blocked`).
- `columns` — one entry per rating on the scale, carrying the rating's word (from
  `scale_words`), how many people scored it, and **the median rise of that score**. The
  median is the single most useful number on this screen and it is not there today.
  Reuse `pb.pay.bands._median` as the existing code already does.
- `limits` — the review's limits that can be drawn as a line across the picture:
  today that is `max_raise_pct`. Each with its value, its `sentence()` and whether it
  blocks or warns. `pb.pay.review.limit.summary()` already returns exactly this shape.
- `outliers` — unchanged in spirit: full, named rows, still `[:60]`, still with `why`.
  This is a list, not a picture; a list may legitimately show the top few, and it must
  say so in its own words when it does.
- `flat` / `flat_note` — keep. Everybody still on the guidance is TRUE and looks broken,
  so the screen must go on saying which it is. Re-check the test still holds when the
  shape is bins rather than dots.
- `levels`, `words`, `max_pct`, `card` — keep.
- **Gone**: `MAX_DOTS`, `dots`, `capped`, `capped_note`, and the `jitter` field (the
  shape no longer needs a fake spread — the bins are the spread).

Add **`calibration_people(review_id, rating, low, high)`** — the named people standing
in one bin of one rating column. Model it on `pb.pay.bands.people_between`: the same
`_require_read()`, the same name gating (`can_names`), the same `{rows, total, more,
more_label}` answer shape so the browser panel is the one that already exists.

`max_pct` must account for the limit lines too: a review whose highest proposal is 8%
but whose limit is 15% should draw the limit inside the picture, not off the top.

### 2c. The picture (`pay_review.js`, `pay_review.xml`, `pay.scss`)

The plot is `.pay-scatter`, 380px tall with a left axis of percentage ticks
(`pay.scss:650`). Keep that frame. Inside it, per rating column:

1. **The shape** — bins along the rise axis (a few pixels tall; pick the number the way
   `SHAPE.normal` / `SHAPE.dense` in `pay_hub.js` picks the band picture's, and measure
   the plot rather than assuming its height). A bin with few people draws one mark each;
   a busier bin draws a bar out from the column's centre line whose length says how
   many. Bars are keyed by WHERE they are, never by what colour they are — a key that
   carries the state makes every recolour a remount and the picture flickers under the
   hand (the band picture learned this; `pay_hub.js:551`).
2. **The median tick** — a short horizontal mark across the column at that score's
   median rise, labelled when there is room, in the voice the band picture's median
   label already uses.
3. **The limit line** — a dashed line across the WHOLE plot at each drawable limit, with
   its sentence beside it. Anything above a blocking limit is already `blocked` and
   already coloured; the line explains why.
4. **The outliers on top** — individually drawn, ringed, draggable, each with its name
   on its label.
5. **The count under each column**, beside the score's word.

Every state must be designed and screenshotted:
- **Nobody in the review** — an empty state that says so and offers the next step.
- **One person.** **One rating used by everybody.**
- **Everybody on the guidance** (the `flat` case) — one bar per column, the note.
- **A review of 4,500** — the point of the phase.
- **A rating on the scale that nobody scored** — an empty column that is still drawn and
  still labelled, never a missing column.
- **A person nobody scored** — still in the middle column, still visible, with the chip
  on their row saying so (this is today's behaviour and it must survive).

### 2d. The drag, and the bin panel

- Dragging an outlier or a lone mark works as today: `set_proposals`, then re-read.
  Keep the foot bar (`.pay-dragbar`) showing who and what percentage while the hand is
  down.
- **The re-read after a drag is currently a full `calibration()` call.** At 4,500 people
  that is now a bigger call than it was; measure it, and if it is slow, merge the one
  changed line into the loaded payload the way `_merge` already does for the worksheet
  and only re-bin that one column. Report the timing either way.
- Pressing a bar opens the named list for that bin (`calibration_people`), with a
  loading state, a failure state that names its reason and its next step, and Escape to
  close. Escape's ladder: the bin panel is innermost — it closes before the drawers and
  before leaving calibration.
- The refusal ladder on every RPC is `error.data.message` → `error.message.data.message`
  → your own sentence. `error.message` is never a rung: on this platform it holds the
  other product's name (GR17).

### 2e. Words

Every new and changed string through `_t()`, one whole expression each, into
`pb_pay/i18n/pb_pay.pot` and translated in `pb_pay/i18n/vi_VN.po` (GR5: a `.po` entry
without its `#. module:` comment kills the install). The removed cap sentence must be
gone from both catalogues. Plain English; no "Odoo" anywhere a reader can see.

---

## 3. Design — the bar

> **extreme WOW, intuitive, out-of-this-world experience, best in class.**

**Name the hero moment in your report.** The intended one: a review of four and a half
thousand people opens as four honest distributions — you can see at a glance that the
top score's spread overlaps the one below it, where each score's middle sits, and where
the limit cuts across — and the handful of people worth arguing about are already ringed
and already draggable, with nothing hidden behind anything else.

Benchmark this against a modern calibration tool (Lattice, Pave), not against a stock
chart widget. Zero dead-ends. Motion with purpose only, inside
`@media (prefers-reduced-motion: no-preference)`. Full keyboard parity: the columns and
the outliers are reachable and adjustable by keyboard. Lucide via `ic()`, no emoji.

---

## 4. Tests (numbered — run on p9clone, report each one)

1. `node pb_pay/tools/band_picture_check.mjs` passes: every P1 case untouched and green,
   plus new `binValues` cases — counts always add back up to the input length; bins are
   ordered, non-overlapping and inside the track; a value beyond the axis is clamped on
   and still counted; an empty input answers with no bins; a classifier returning an
   unexpected state does not lose the person.
2. **Nobody is dropped.** On a review of 4,500 on p9clone, the sum of every mark's count
   plus every individually drawn dot equals the number of lines in the review, proven by
   a DOM count against a SQL count. Repeat at 902 and at 12.
3. **The cap is gone.** `grep -rn "MAX_DOTS\|capped\|first %(count)s people" pb_pay/`
   returns nothing, and neither catalogue still carries the sentence.
4. **The medians are right.** Each column's median matches a SQL median of that rating's
   `proposal_pct`.
5. **The limit line is right.** Set a `max_raise_pct` limit, reopen: the line sits at the
   right height, everybody above it reads `blocked`, and the sentence beside it is the
   limit's own.
6. **`max_pct` covers the limit**: a review whose highest proposal is well under the
   limit still draws the limit inside the plot.
7. **Drag still works** on an outlier and on a lone mark: the row follows, the number
   saves, the picture re-reads, and the foot bar agrees with what was saved. Report the
   timing of the re-read at 4,500.
8. **The bin panel**: press a busy bar, get the right people, the right count, a working
   loading state, a failure state that names its reason, and Escape closes it first.
9. **Permissions.** As a user WITHOUT the name-reading groups, no name reaches the
   browser — check the network payload, not the screen — and the picture still draws.
10. **Every state in §2c**, each screenshotted.
11. **Speed.** Time `calibration()` at 12, 902 and 4,500 lines. The P6b baseline was
    162 ms for 902. Report all three; a regression at 902 is a failure.
12. **Nothing regressed.** The full `pb_pay` suite green — **P1's baseline was 111 tests,
    0 failed, 0 errors** — and P1's 34 node assertions untouched and green.
    Neighbouring suites at the same pre-existing baseline: **P1 measured 248 tests with
    3 failures, all p9clone drift (`pb_contracts` ×2, `pb_group` `test_t9`)**. Report
    against those two numbers rather than claiming zero.
15. **L7 and L8 fixed**, each proven: a band holding a single outlier says "1 person" in
    English, and a refused band move no longer raises an undo bar saying "Band moved."
13. **Vietnamese.** Walk the picture in VI: the new sentences, the column words, the
    limit sentence, the bin panel and the empty states are all translated.
14. **Reduced motion**, and **keyboard only** end to end.

---

## 5. Deploy

`pb_pay` only. Bump the manifest one minor from whatever P1 shipped (P1 was to ship
`19.0.3.2.0`, so **`19.0.3.3.0`** unless P1 says otherwise). Ledger deploy ritual
exactly: clean staging, per-module scoped `rsync --delete`, detached systemd unit with
`--logfile` and a sentinel, all four databases in order p9clone → payobook → abm →
payobook_template with a `pg_dump` before each.

Python changed this time as well as assets, so the module needs a real `-u`. The asset
ritual still applies: purge `/web/assets/%` **and** bump `web.assets.version` per
database, then Chrome-MCP load the screen — SCSS errors only appear at page load.

Verify tree hashes both sides and `ir_module_module.latest_version` in all four
databases.

---

## 6. Report back

Write `docs/handovers/LOOK_P2_REPORT.md`, append your gotchas to `LOOK_LEDGER.md`
(continuing the L-series) plus one phase-log line, and return a summary covering: each
numbered test with its result and evidence (screenshots in
`docs/handovers/look_p2_shots/`); the hero moment named; your self-score against the
design bar; the three timings; any ruling in §1 you had to bend and why; anything this
handover got wrong about the code — say so plainly, it was written from a read of the
files before P1 landed and it can be wrong; the four databases' versions and tree
hashes; the commits (feature-scoped, explicit `git add`, **not pushed**); and anything
the owner has to decide.

Do not start P3. Report and stop.
