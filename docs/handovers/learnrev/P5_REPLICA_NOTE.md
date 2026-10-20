# LEARNREV P5 S7 — generating the practice copies: what it would take (decision note)

For Fable, to take to the owner. A note, not a build (P5 non-goal: no new replicas).

## In plain words (for the owner)
The practice copy is a drawing of each screen that people can click around in without touching real records. Today
every drawing is made by hand. A check that already runs on every build makes sure the drawing uses the same column
names as the real screen, in English and Vietnamese, for the 16 screens that have a Guide. What it cannot promise is
that the drawing *looks* like the real screen after a redesign. Generating the drawings would fix that, at a cost of
roughly 7–10 working days for the first 8 screens. **Recommendation: not now.** Keep hand-drawn copies with the check;
generate only the two screens where it is nearly free (Mapping › Journey and the pay preview), when one of them is
next redesigned.

## What exists today (verified 2026-10-20)
- `pb_learn/static/src/engine/screens.js`: 55 hand-drawn screens, 3,334 lines, fed by the practice company in
  `docs/tutorial_poc/author/practice-data.js` (2,406 lines → generated `engine/fixture.js`).
- The 16 manifest screens' drawings are 40–121 lines each (treatment 43, mapping 48, runpayroll 121, payruns 110,
  payslips 57, approvals 96, dashboard 62, formula 107; statutory 106, employees 80, import 47, matrix 53, records 61,
  payreview 73, govreports 50, wftime 40) — about 1,150 lines in all.
- Practice copies are what tenants (and anyone who cannot open a screen) see in lessons: 48 `rep-*` lesson steps and
  the Try mode of every walkthrough without a server check.

## What the truth gate already guarantees without generation
`pb_learn/tests/guide_truth.py` (P1 + P4 `check_replica`, run offline and as `TestGuideTruth` on a clone):
1. every manifest column appears in that screen's drawing, and every table header the drawing shows is a manifest
   column or a string of the real template — in either language (P4 S5; it caught the treatment drawing's Group /
   Subtotal and, in P5a, Records' "Employee" and Import's "Status", LR66);
2. column words come from the template and its `.po` (LR30: one text node);
3. lesson text never names a retired label (P1 S7).
So the WORDS cannot drift on those 16 screens. Layout, order of columns, buttons that moved, and new sections can.
On the other 39 drawn screens nothing is gated yet (P5b writers found four drifts there: Today's "Checked out" VI,
Close's week heading, the Overtime "Near the limit" chip, the exits desk lights in Vietnamese).

## Three ways to go further
| | How | Cost (first 8 screens) | What it buys | Risk |
|---|---|---|---|---|
| A. Keep hand drawings + extend the gate | Add the 39 non-manifest screens to the gate as their manifests arrive (next manifest wave); add a "button labels" half to `check_replica` | ~0.5 day per wave | Words right everywhere; layout still hand-kept | Low |
| B. Generate the table part from the Guide JSON | A `replicaFromGuide(screen, guide, fixtureRows)` renderer: header row from `fields[].column`, choice chips from `choices`, cells from new fixture rows per screen; the hand-drawn hero/toolbar stays | 3–4 days: renderer + fixture rows for 8 screens (~25 rows each) + gate change + lesson anchors re-pointed | Columns, order and choice words always match | Medium: tables only; anchors in 40+ lesson steps must be re-laid |
| C. Mount the real components with fixture data | `JourneyBoard` takes `data` (pure — easy); `PayPreview` takes `preview` (pure — easy); `ComponentTreatmentBoard readonly` still calls `value_kind_board` / saves through `orm` (`component_treatment.js:104,244,271,297`), so it needs an `orm` stub that answers from the fixture; the other cockpits (runs board, run wizard, approvals, dashboard, formula studio) load their own data in `onWillStart` and would each need the same stub | 7–10 days for 8 screens (stub layer, fixture payloads in each server method's exact shape, assets loaded in the Learn bundle, gate rewritten to compare payload shapes) | The copy IS the screen: zero drift in layout and words | High: every screen refactor can break the fixture payload silently; heavier Learn bundle; practice copy can accidentally call a real method if the stub misses one |

## Recommendation
A now (cheap, already the program's direction: manifests for the next screens bring them under the gate). C only for
`JourneyBoard` and `PayPreview`, opportunistically, because they already take plain data. Revisit B/C if the owner's
priority becomes tenant onboarding through lessons, where practice copies carry more weight than on payobook (which
has the demo company and checked Try).

## Owner question (real-world form)
"When a screen is redesigned, should its practice copy update by itself (about two weeks of work now, and every
redesign must also update a sample data file), or is it enough that a build fails when the practice copy uses a
wrong column name (free, already in place)?"
