# LOOK P1 — Open this band out

**Read `docs/handovers/LOOK_LEDGER.md` in full first**, and the parent ledgers it names
(GROUP, TIDY, WFPLAN, RIZE). Everything in them binds. This document adds only what is
specific to P1.

**Module touched: `pb_pay` only.** Browser only — no model change, no schema change, no
migration, no new server method. Every number this phase needs is already in the payload
`pb.pay.bands.get_board` hands over.

---

## 0. What you are building, in one paragraph

On the Pay bands screen a band is drawn as a range on a shared money axis, and that is
the point — a level 2 band and a level 8 band are meant to be comparable at a glance.
But on the owner's own screen "Construction · level 2 · Vietnam" runs 6.6M to 11M ₫ on
an axis that reaches 136M ₫, so 544 people, 57 of them below the band and 82 above it,
are drawn inside about forty pixels. The counts are right, the colours are right, and
nobody can read any of it. **You are making one band at a time unroll to its own money
scale** — the sliver stretches across the whole track, its people spread out into marks
you can actually see and press, a second ruler appears underneath saying what the new
width is worth, and a locator above shows where this zoom sits on the shared axis so the
reader never loses their bearings. It opens on hover, it pins on a press, it survives a
drag, and it changes nothing anybody is paid.

---

## 1. Rulings — decided, do not re-open

**R1. A zoom is a way of looking, never a way of editing** (ledger rule 17). No stored
number changes. The screen says out loud, while a band is open, that its width no longer
compares with its neighbours — in the same voice the family warning already uses.

**R2. Three ways in, one way out.**
- **Hover** the track opens the row after **180 ms**; leaving closes it after **140 ms**.
  The two delays are what stop the picture flickering as a reader sweeps down the list.
  Hover is gated behind `@media (hover: hover) and (pointer: fine)` — a touch screen
  gets no hover behaviour at all.
- **Pressing the "Open out" button** (or `Enter`/`Space` on it) **pins** the row: it
  stays open when the mouse leaves.
- **Starting a drag on a grip pins the row too**, and a drag started on a CLOSED row
  opens and pins it first. Dragging an edge inside a forty-pixel sliver is the exact
  thing this phase exists to stop.
- `Escape`, the button again, or opening a different band closes it. **One band is open
  at a time**, always.

**R3. The pin is NOT remembered between visits.** "Fit to this family" is a preference
("I always want to see this family on its own scale") and is remembered. A pinned band
is a moment ("I am working on this band right now"). Re-opening a band the reader has
long forgotten would be a surprise, not a convenience. No new localStorage key in this
phase.

**R4. The row grows downward, and one row at a time.** The open row gains a fixed
`padding-bottom` for the ruler, animated. Rows below it move down; the cursor is on the
track at the TOP of the growing row and never lands on anything that moves. Do not
overlay, do not float, do not open a panel — the whole idea is that the band itself
unrolls in place.

**R5. Zoom beats "Fit to this family", and closing returns to whatever the family was
set to.** The zoom is the third and narrowest ruler on this screen: lane axis → family
axis → this band's own. Closing a zoomed band must return it to the family axis if that
family is fitted, and to the lane axis otherwise.

**R6. A suggested band opens out too.** Reading is not editing. Suggested bands carry no
`id` and therefore no grips, so there is nothing to drag; the picture still unrolls.

---

## 2. Deliverables

### 2a. `band_picture.js` learns that an axis has two ends

The pure module (`pb_pay/static/src/js/band_picture.js`) currently takes `axisMax` and
assumes every axis starts at zero. Change it to take an **axis object `{ min, max }`**:

- `binPeople(wages, axis, trackPx, binPx, edges)`
- `dodgeDots(dots, axis, trackPx, minGapPx)`
- new export `axisSpan(axis)` — the guarded width of an axis, never zero, never
  negative; every other function uses it so they cannot disagree.
- new export **`bandAxis(band, opts)`** — the zoom axis for one band, computed from data
  the browser already holds. This is the heart of the phase and its rules are in §2b.

Change the parameter properly rather than accepting both shapes. There are exactly two
consumers — `pay_hub.js` and the node check — and an explicit break that the check
catches beats a clever signature that hides a missed call site. **Nothing in this file
may import from `@odoo/owl` or `@web/…`**; the node check loads it off disk as a `data:`
URL and any platform import stops the check running at all.

### 2b. `bandAxis` — the rules of a band's own scale

Given a band's `min`, `max` and its complete `wages[]`, return `{ min, max, below,
above }` where `below` / `above` are how many people are clamped onto each end.

1. **It must contain the band.** The band's own `min` and `max` are always inside.
2. **It must not be flattened by one outlier.** Mirror the lane axis's tail rule at band
   scale: take the 5th and 95th percentile of the band's own wages, and widen to the
   band's edges. Formally: `lo = min(band.min, p05)`, `hi = max(band.max, p95)`.
3. **Pad** by 6% of the span at each end, then clamp `lo` at 0 — money does not go
   negative, and a picture whose left edge is below zero is a lie about the ruler.
4. **Guard the degenerate span.** A band where `min === max` and every person is on the
   same wage has a span of zero. Widen to ±10% of the value, or to `0 … 1` when the
   value itself is zero. Never divide by zero, never return `max <= min`.
5. **Count both tails.** People below `lo` and above `hi` are clamped ONTO the edge (the
   existing `binPeople` clamp already does this) and counted. Unlike the lane axis, a
   zoom has a LEFT tail as well as a right one, and both must be reported.
6. **Deterministic**: same input, same axis, every time. `bandAxis` is checked under
   node, so it may not read the clock, the window or the DOM.

### 2c. The picture, drawn on the open band

In `pay_hub.js`:

- **`axisPct(scope, value)` must honour `scope.axis.min`.** Today it divides by `max`
  alone. Make it `(value - lo) / (hi - lo) * 100` with `lo` read defensively
  (`Number(scope?.axis?.min) || 0`), because the lane axis already ships `min: 0.0` and
  the family axes come from the same builder. Every position on a band row goes through
  this one function — `rangeStyle`, `midStyle`, `gripStyle`, `medianStyle`, `_bandPx` —
  so getting it right here is most of the work.
- **`picture(scope, band)`** passes the axis object straight through to `binPeople` /
  `dodgeDots`. The ≤24-people named-dot shape and the binned-column shape are unchanged;
  what changes is that on a zoomed band far more of them clear the minimum gap, so a
  band that drew as three columns closed will draw as a readable spread open. That is
  the point. **The counts must still add up to `wages.length` in both states** — that is
  test 3.
- **The scope handed to a row** becomes: the band's own zoom axis when it is open,
  otherwise the family axis when that family is fitted, otherwise the lane axis (R5).
  Put this in one getter/helper so no drawing function has to work it out again.

### 2d. The ruler, the locator and the sentence

While a band is open the row carries three new things and nothing else:

1. **A ruler under the track** — 5 ticks in normal mode, 3 in dense, each labelled in
   the band's own currency. **They must not print the same label twice.** `shortMoney`
   rounds to one decimal at M/B scale, so a zoom spanning 6.6M–11M would print "7.0M,
   8.0M, 9.0M, 10.0M, 11.0M" fine, but a zoom spanning 6.60M–6.68M would print "6.6M"
   five times. Give the ruler enough significant figures for its own span (pick the
   decimals from the span, not from the magnitude) and, if two ticks would still read
   the same, drop to fewer ticks rather than print a lie.
2. **A locator above the track** — a hairline the width of the whole track with a filled
   segment showing where this zoom sits on the SHARED lane axis. This is what stops a
   reader losing their sense of scale, and it is the single cheapest thing on the screen
   that makes the zoom feel honest. When the zoomed span is under about 1.5% of the
   shared axis, draw the segment at a 2px minimum width so it never vanishes.
3. **One sentence**, in the voice of the existing family warning: *"This band is drawn
   on its own money scale, so its width no longer compares with the others."* Plus, when
   either tail is non-empty, the tail sentence in the voice of the existing axis note —
   e.g. *"3 people are paid less than 5.9M ₫ and sit on the left-hand edge. Their own
   pay is on their label."*

Empty and thin states, all of which must be designed:
- **Nobody on the band**: it still opens, the range is drawn on its own scale, and the
  sentence says *"Nobody is on this band yet."*
- **One person**: one dot, the ruler still reads sensibly.
- **Everybody on the same wage**: rule 2b.4's guarded span; the dodge spreads them into
  a block; nobody is hidden.
- **One huge outlier**: the zoom does not flatten (2b.2); the outlier sits on the right
  edge and the tail sentence counts them.

### 2e. The drag, under zoom

- `startDrag` currently stores `laneMax` only. It must store **both ends** of the axis
  the row is actually drawn on, and `onDrag` must map
  `value = lo + ratio * (hi - lo)`.
- `onGripKey` steps by **1% of the drawn span** (5% with Shift) — under zoom that is a
  much finer nudge, which is exactly what a reader who has zoomed in wants.
- **The drag axis is computed once at drag start, with 30% headroom on each end, and
  then frozen for the duration of the gesture.** Two reasons, both learned the hard way
  in this kind of control: recomputing the axis under the moving hand makes the grip run
  away from the cursor, and freezing without headroom means an edge dragged to the end
  of the zoom hits an invisible wall — a dead end, which the design bar forbids. With
  headroom the reader can always drag further than the picture currently shows, and the
  axis recomputes on release.
- Everything else about the drag is unchanged: the marks recolour under the hand from
  data already loaded, the exact money still comes from the server's `move_edge` preview
  after `DRAG_SETTLE`, and the undo still restores the three numbers the server handed
  over before it wrote anything.

### 2f. Motion

- The range bar, the mid mark, the grips, the median tick and the marks transition their
  `left` / `width` over ~260 ms on `cubic-bezier(.2, .8, .2, 1)` — one unroll, not a
  jump.
- The row's `padding-bottom` growth uses the same curve and duration.
- **All of it lives inside `@media (prefers-reduced-motion: no-preference)`.** A reader
  who has asked their machine for less movement gets the opened row on the first frame,
  finished, with nothing to recover from.
- A zoom changes the bin boundaries, so the marks' `t-key`s change and OWL remounts
  them, which would replay their fade-in as a shimmer under the unroll. Put `.is-zooming`
  on the track for the duration of the transition and disable the mark entry animation
  under it, so the whole thing reads as one motion.

### 2g. Accessibility and keyboard

- "Open out" is a real `<button>` carrying `aria-expanded`, and its label changes to
  "Back to the shared scale" when open (**one whole sentence per state, never glued from
  template nodes** — ledger GR22).
- The row's sentence gets an id and the track gets `aria-describedby` pointing at it, so
  a screen reader is told the ruler changed.
- Ruler ticks are `aria-hidden`; their numbers are already on every mark's label.
- Escape closes the open band. It must sit in the EXISTING ladder in `onKey`, and the
  band is the OUTERMOST of the things that ladder closes: popover first, then drawers,
  then the undo bar, then the open band. Register stays `{ capture: true }` — the
  platform's own hotkey service claims Escape on `window` (WFPLAN WF4).

### 2h. Words

Every new string goes through `_t()`, is one whole expression (JavaScript has no
implicit string concatenation, and a Python habit there kills the entire asset bundle),
and is added to `pb_pay/i18n/pb_pay.pot` **and translated in `pb_pay/i18n/vi_VN.po`**. A
`.po` entry without its `#. module:` comment kills the install (GR5). Plain English, the
words on the screen and not the words in the code. No "Odoo" anywhere a reader can see.

---

## 3. Design — the bar

> **extreme WOW, intuitive, out-of-this-world experience, best in class.**

**Name the hero moment in your report.** The intended one: a band that was an
unreadable smear unrolls under the cursor into a picture with real people in it, and a
hairline above it shows you exactly which slice of the company's pay you are now looking
at — no dialog, no new screen, no click required to see it.

Zero dead-ends: every state listed in §2d is designed. Plain language on every label and
sentence. Motion with purpose, and none at all for a reader who asked for none. Keyboard
parity with the mouse throughout. Lucide icons via the shared `ic()` set — no emoji.
Measured against the best chart interaction in a modern SaaS tool, not against a stock
platform widget.

---

## 4. Tests (numbered — run them on p9clone, report each one)

1. `node pb_pay/tools/band_picture_check.mjs` passes, with the existing T3a–T3g cases
   migrated to the axis-object signature **and new cases added**: an axis whose `min` is
   not zero places a mark correctly; `bandAxis` always contains the band's own edges;
   `bandAxis` is not flattened by a single 10× outlier; `bandAxis` never returns
   `max <= min` for an all-identical band, a single-person band, an empty band or a band
   whose wages are all zero; both tails are counted; the same input gives the same axis
   twice.
3. **Counts are conserved.** On "Construction · level 2 · Vietnam" (payobook, 544
   people), the sum of every mark's count is 544 closed AND 544 open, and the "57 below"
   / "82 above" chips read the same in both states.
2. **The band actually opens.** Closed, that band occupies under 5% of the track;
   opened, it fills it. Screenshot both.
4. **The drag is 1:1 under zoom.** Open the band, drag the lower grip, and the grip
   tracks the cursor in zoomed money; the foot bar's sentence and the saved figures agree
   with each other; Undo restores all three numbers exactly.
5. **No invisible wall.** Drag an edge to and past the zoom's visible end — the headroom
   lets it keep going, and the axis recomputes on release.
6. **Keyboard only.** Tab to "Open out", Enter opens, Tab to a grip, `←`/`→` step by 1%
   of the zoomed span (Shift = 5%), Enter saves, Escape closes the band.
7. **Fit-to-family interaction.** With a family fitted, open a band in it and close it
   again: it returns to the FAMILY axis, not the lane axis (R5), and the two warning
   sentences do not both claim to be the reason.
8. **Dense rows.** Toggle Dense and open a band: fewer ticks, nothing overlapping,
   nothing dropped.
9. **A suggested band.** On a scope with no saved bands, open one out: it unrolls, has
   no grips, and pressing a mark still opens the people popover.
10. **Thin data.** A band with nobody; one with one person; one where everyone is on the
    same wage; one with a single very large outlier. Screenshot each.
11. **Ruler honesty.** Find (or construct on p9clone) a band whose span is small enough
    that one-decimal M formatting would repeat, and prove the ruler prints distinct
    labels or drops to fewer ticks.
12. **Reduced motion.** With `prefers-reduced-motion: reduce` emulated, the open state
    arrives on the first frame.
13. **Coarse pointer.** With touch emulated, hover does nothing and the button is the
    only door.
14. **Nothing regressed.** The full `pb_pay` server test suite is green (it was 56 + the
    review tests at GROUP P6b), and neighbouring suites sit at the same pre-existing
    baseline — name the baseline in the report rather than claiming zero.
15. **Vietnamese.** Switch to VI and walk the opened band: every new string is
    translated, including the two tail sentences and the button's two states.

---

## 5. Deploy

`pb_pay` only. Bump the manifest to **19.0.3.2.0**. Follow the ledger's deploy ritual
exactly: clean staging directory, per-module scoped `rsync --delete`, detached systemd
unit with `--logfile` and a sentinel, then **every database in order p9clone → payobook
→ abm → payobook_template**, `pg_dump` before each.

This phase is JS + SCSS + XML, so the asset ritual is mandatory and is not optional
folklore: `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` **and** bump the
`web.assets.version` `ir.config_parameter`, per database. Then Chrome-MCP load the
screen — `odoo-bin -u … --stop-after-init` does not surface SCSS compile errors, and a
broken bundle only appears at page load.

Verify: tree hashes match both sides for `pb_pay`, and `ir_module_module.latest_version`
reads `19.0.3.2.0` in all four databases.

---

## 6. Report back

Write `docs/handovers/LOOK_P1_REPORT.md` and append to `LOOK_LEDGER.md` (the gotcha
series **L1, L2, …** and one phase-log line). In the report:

- The numbered tests, each with its result and the evidence — screenshots in
  `docs/handovers/look_p1_shots/`.
- **The hero moment, named**, and a self-score against the design bar in §3.
- Every ruling in §1 you had to bend, and why.
- Anything you found that this handover got wrong about the code. Say so plainly; the
  handover was written from a read of the files and it can be wrong.
- The four databases' versions and tree hashes.
- The commit(s) — feature-scoped, explicit `git add` of named files, **not pushed**.
- Anything the owner has to decide.

Do not start P2. Report and stop; the next phase is designed from what you report.
