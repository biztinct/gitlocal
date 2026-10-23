# TIDY Phase 2 — "The band picture": every person drawn, nobody eclipsed

Read `docs/handovers/TIDY_LEDGER.md` FIRST and fully (rules 11–14, the Pay bands
plumbing facts, the P1 phase log and T-gotchas), then the GROUP ledger's rules,
gotchas and deploy ritual, then `docs/handovers/GROUP_P6A_PAY_BANDS_AND_FAIRNESS.md`
§Design so you know why the band picture is drawn the way it is. Do not re-derive the
plumbing facts.

## 0. What you are building, in one paragraph
The Pay Bands picture puts every person on the band as a 9 px dot. With 544 people
in "Construction · level 2" the dots pile into one smear, 144 of them are not drawn at
all, and the chips say so. The owner asked for "another way to depict people" that
looks better when they touch. Replace the dot cloud with a picture that **always draws
everyone** (rule 12), never overlaps, keeps the three colours (inside / below / above),
keeps the live answer while an edge is being dragged, keeps "Fit to this family" and
dense mode, and gives back the one thing dots had — a person's name — on hover and
click.

## 1. The picture (binding design)

### 1a. Two shapes, chosen by count
- **Up to 24 people in a band → named dots, dodged.** Sort by wage, place each on the
  axis; when a dot would land within 10 px of the previous one, step it to the next row
  (rows −2, −1, 0, +1, +2 around the track's midline, then wrap) so no two dots ever
  overlap. A dot is a `<button>` with the same title/aria-label as today; click opens a
  small popover (name · job · wage · "below the band"/"in the band"/"above the band").
- **More than 24 → people columns.** The track is cut into bins of **8 px** (6 px in
  dense mode) measured against the scope's axis (`axisPct` is the only ruler; a fitted
  family re-bins against its own axis). For each bin:
  - count ≤ 6: a stack of **pips**, one 5×5 px square per person (3×3 in dense), 1 px
    apart, bottom-aligned — six people read as six.
  - count > 6: a **solid column**, height = 24 px + 14 px × √((count − 6) / (busiest − 6)),
    capped 4 px short of the track, with the count printed above it in 9 px when the
    count ≥ 10 (never below it; never inside).
  - Each column is a `<button>`: hover/focus shows "12 people · 6.6M ₫ to 6.9M ₫ ·
    below the band"; Enter/click opens a popover that lists up to 20 of them (name · job
    · wage) with "and N more" and no dead-end — the popover has a close button and
    Escape (capture, WF4).
  - A bin that straddles a band edge is split by wage into two stacks side by side
    (below|inside or inside|above), so the colour boundary is always exact.
- **Colours**: inside = `--pbim-primary`; below = `--pbim-rose`; above = `--pbim-amber`
  (the same three the dots and the chips use; colour is never the only message — the
  tooltip carries the word). Suggested bands draw identically (rule from P6a: a
  proposal looks exactly like a saved band).
- **The drag** still answers live: classification is computed on the client against
  `live(band)` edges every render, so columns recolour while the mouse is down; the
  server preview sentence at 160 ms is unchanged.
- **Median mark**: a thin vertical tick at the band's median wage with the label
  "median 8.4M ₫" (server already sends `median_label`); it replaces the third chip.
- **Chips** under the band name: "57 below", "82 above" stay; **"and N more not drawn"
  is removed everywhere** (label builder, template, `.po`).
- **Dense mode**: track 24 px, pips 3×3, column cap 20 px, count labels off.
- Motion: pips/columns fade in on first paint only inside the existing
  `prefers-reduced-motion: no-preference` block; nothing animates during drag except
  colour.
- 390 px: same picture; bins 6 px; popover becomes a bottom sheet (kit precedent from
  the Decision Room phone sheet).

### 1b. Server
- `pb_pay/models/pb_pay_bands.py`: `_fill_band` and the proposal path return
  `wages` — every person's wage as a sorted list of **integers** (round; VND has no
  minor units; SGD ×100 is not needed — the picture is at 8 px resolution) — plus
  `dots` (named, full) **only when `people ≤ 24`**, else `dots: []`. Remove `MAX_DOTS`,
  `more`, `more_label`. Add `people_scope` to every band payload: `{band_id}` for saved
  bands, `{family, level, company_id, country}` for proposals — whatever lets the server
  find the same people again.
- New `@api.model people_between(scope, low, high, limit=20)` → `{total, rows:[{id,
  name, job, wage, wage_label, state}]}`, behind `READ_GROUPS`, company-scoped exactly as
  `get_board` is; `state` computed against the band's saved/proposed edges.
- Bump `pb_pay` to 19.0.3.1.0.

### 1c. Client
- `pb_pay/static/src/js/band_picture.js` (new): a pure, exported
  `binPeople(wages, axisMax, trackPx, binPx, edges)` → `[{x0, x1, low, high, below,
  inside, above, count}]` and `dodgeDots(dots, axisMax, trackPx, minGapPx)` → row per
  dot; no OWL inside, so `pb_pay/tools/band_picture_check.mjs` can run them under node
  (precedent `pb_decision_room/tools/decision_engine_check.mjs`).
- `pay_hub.js`: measure each track with a `ResizeObserver` (precedent: the scheme
  board measures on paint/resize), keep widths in `useState` (GR26), compute bins in a
  getter that reads `live(band)`; popover state `{bandKey, bin, rows, total, busy}`.
- `pay.xml` 239–270: replace the dot loop with the two shapes; `pay.scss`: `.pay-pip`,
  `.pay-col`, `.pay-col-n`, `.pay-median`, `.pay-pop`, dense variants.
- Vietnamese for every new string in `pb_pay/i18n/vi_VN.po` (GR5 comment form).

### 1d. Carried over from P1 (gotcha T10): no "RIZE" in the Apps list
Thirteen module manifests open their `description`/`summary` with "RIZE phase Pn — …"
(pb_lifecycle, pb_onboarding, pb_pip, pb_budget and nine others — `grep -l "RIZE
phase" pb_*/__manifest__.py`). A user sees these in the Apps list. Rewrite each
opening line to say what the module does in plain words, no programme codes; keep
the engineering history in the manifest's code comment if you want it. Bump each
version (patch), upgrade on all four DBs. One commit for all thirteen.

Non-goals: the calibration scatter in Pay Review (a Phase 4 candidate — say so in the
report); no change to bands' numbers, drag maths, apply/undo, health cards or Fairness;
no employee form navigation from the popover unless a deep link into the People hub
already exists (check `pb_people`; if it does, add "Open" — if not, leave it out and
say so).

## 2. Design (the bar)
**"extreme WOW, intuitive, out-of-this-world experience, best in class."** Hero: the
Construction level 2 band — 544 people — reads as a skyline: a rose foothill below the
edge, a violet ridge inside, an amber tail above, with the median tick, and a drag of
the edge sweeps the colours across it in real time. Second: click a column and the
people in it are simply listed. Plain words on every tooltip and popover ("12 people
between 6.6M ₫ and 6.9M ₫, below the band"). Zero dead-ends (popover close/Escape;
no "not drawn"). Keyboard: Tab across columns, Enter opens, Escape closes. No emoji,
Lucide via `ic()`, no "Odoo".

## 3. Tests (p9clone; numbered)
- T1 `get_board`: for every band `len(wages) == people`, `wages` sorted ints, no `more`
  key, no "not drawn" string anywhere in the payload; `dots` non-empty iff `people ≤ 24`.
- T2 `people_between`: gate enforced; `total` equals the count of that band's people in
  `[low, high]`; `rows ≤ limit`; other companies' people never appear.
- T3 node check: `binPeople` with a straddling edge splits counts exactly; sum of bin
  counts == len(wages) for random inputs; `dodgeDots` never returns two dots within
  `minGapPx` on the same row.
- T4 DOM (Chrome MCP on p9clone): in the 544-person band no two marks' bounding boxes
  intersect; in a ≤ 24 band the same; count labels only on columns ≥ 10.
- T5 drag: hold an edge across a column — the below/above chips and the coloured counts
  agree with the server's preview sentence at rest.
- T6 dense mode + fit-to-family re-bin (bin count changes with the axis).
- T7 Vietnamese: 0 English survivors in `pb_pay` (existing `test_p7_vietnamese.py`).
- T8 `pb_pay` suites green (same drift set as before).
Browser (p9clone + payobook; validator; 1440 + 390; EN + VI; `docs/handovers/
tidy_p2_shots/`): B1 Construction level 2 before/after; B2 Engineering level 6 (33
people → columns) and a ≤ 24 band (dodged dots); B3 drag recolour mid-drag; B4 column
popover with names; B5 dense; B6 fit to family; B7 phone; B8 Vietnamese.

## 4. Deploy
Ritual as the ledger: p9clone → payobook → abm → payobook_template, `pg_dump` each,
`-u pb_pay`, asset purge, version + hash verification.

## 5. Report back
1. Three sentences: what the 544-person band looks like now, what a small band looks
   like, what a person can do that they could not before.
2. T1–T8 / B1–B8 table with the before/after screenshots named.
3. Deploy evidence per DB; commits; T-gotchas appended; self-score against the bar;
   the Phase 4 candidates you noticed.
