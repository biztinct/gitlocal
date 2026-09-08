# LOOK Programme Ledger — see the whole picture, and choose the period

Every LOOK phase handover references this file. Read it FULLY before coding. Append
(never rewrite history) when you hit a new gotcha — that is part of every phase
deliverable.

## Where this programme came from

The TIDY programme closed on 2026-09-08 with four named candidates in its report. The
owner read them on 2026-09-09 and asked for all four, in one run, under the phased
model (Fable designs, Opus builds + tests + deploys + self-reviews; phases go back to
back; only a destructive action or a genuine scope decision stops the run).

The four, in the owner's own words:

> let a band open out to its own width on hover; a quarter or "March to June" range on
> the Budget strip; the same month strip on the Pulse and Explorer screens; and the Pay
> Review calibration chart, which is now the only picture in the product that can still
> drop people from view.

They split into two themes, and the phase order follows the themes rather than the
sentence, so that the two `pb_pay` picture phases sit next to each other and share one
piece of pure arithmetic:

| Phase | Name | Modules | Theme |
|---|---|---|---|
| **P1** | Open this band out | `pb_pay` | a picture you can read |
| **P2** | Everybody on the calibration picture | `pb_pay` | a picture you can read |
| **P3** | A stretch of months | `pb_budget` | the period is a scope |
| **P4** | The period on Pulse and Explorer | `pb_dashboard`, `pb_explorer` | the period is a scope |

## Parent ledgers — everything in them binds here

Read in full before P1:

- `docs/handovers/GROUP_LEDGER.md` — target, credentials, binding rules 1–10, rulings
  G1–G9, plumbing facts, gotchas **GR1–GR60**, the deploy ritual.
- `docs/handovers/TIDY_LEDGER.md` — binding rules **11–15**, gotchas **T1–T24**.
- `docs/handovers/WFPLAN_LEDGER.md` — WF1–WF29, ports.
- `docs/handovers/RIZE_LEDGER.md` — platform contract, R-series.

This ledger only ADDS. Where a rule below repeats a parent rule it is because that rule
is about to be tested by this programme's work.

## Target & credentials

As the GROUP ledger. ssh alias `Payobook19v2` (never a hardcoded IP). DB order for every
phase: **p9clone → payobook → abm → payobook_template**, `pg_dump` before each.

**GR24 stands**: the admin password on file for `payobook` does not work. Create a
temporary validator user, use it, archive it at the end of the phase, and name it in the
phase report. **WF15 stands** for `abm`.

## Binding rules (in addition to GROUP 1–10 and TIDY 11–15)

16. **A picture never drops a person, and never lies about scale.** TIDY rule 12 said
    "every person is drawn". LOOK widens it: a picture may not draw a person in a place
    that is wrong for the ruler underneath them, and it may not print a ruler a reader
    cannot tell apart from another one on the same screen. If a picture cannot honour
    both, it CHANGES SHAPE — it never caps, truncates, samples or says "and N more".
    The phrase "the first N people" may not appear in any picture's copy.

17. **A zoom is a way of LOOKING, never a way of EDITING.** Any per-band, per-family or
    per-period magnification is a reader's own convenience: it is remembered in that
    reader's browser and nowhere else, it changes no stored number, and while it is on
    the screen says out loud that this row's width no longer compares with its
    neighbours. Precedent: "Fit to this family" (`pay_hub.js` `toggleFit`, `FIT_KEY`).

18. **A period is a scope, not a filter** (TIDY rule 13, widened from Budget to every
    screen). When a screen accepts a period, EVERY number, word, colour, tone, drill and
    export on it becomes about that period. A period must resolve on the SERVER — the
    server decides what a bare `"current"` means and refuses a period it cannot answer —
    and the browser must adopt whatever the server answered rather than keeping what it
    asked for. Precedent: `pb_budget.get_board` + `_scope` + `_month_in_fy`.

19. **The period strip is a PATTERN, not a shared component.** Each screen's strip
    answers a different question in its chips (Budget: did this month run over? Pulse:
    was anybody paid, and how much? Explorer: how much data is there?). The shared
    things are the VISUAL LANGUAGE and the KEYBOARD CONTRACT below, not a class.
    Specifically: `pb_dashboard` MUST NOT gain a dependency on `pb_import_kit`,
    `pb_hub` or any cockpit — its manifest is `['web', 'om_hr_payroll',
    'pb_hr_payroll_base']` and staying lean is a documented property of that module
    (its own docstring, rule 2). It carries its own copy of the strip.

20. **The strip's keyboard contract, identical on every screen.**
    - `←` / `→` walk the chips; `Home` / `End` jump to the ends.
    - `Escape` clears the period back to the widest scope, after any dialog or drill.
    - The busy guard lives in the HANDLER, never on the chip's `disabled` attribute
      (**T23** — disabling the focused chip blurs it and the next arrow press is read
      against the wrong state).
    - "Where the keyboard is standing" is read from `ev.target.closest('[data-…]')`,
      never from application state a keypress is about to change (**T23**).

21. **Deep links keep working and never land on an empty screen.** A saved link naming
    a period the screen cannot answer falls back to the widest scope silently — never
    an error, never a blank board (`_month_in_fy`'s contract). `"current"` is always
    accepted so a bookmark or a ⌘K row means "now" for ever.

## The design bar — verbatim in every phase, and every phase report scores itself

> **extreme WOW, intuitive, out-of-this-world experience, best in class.**

Concretely, every phase must state and satisfy:

- a **hero moment** — name it in the phase report;
- **zero dead-ends**: every state (empty, loading, error, partial, huge, one person,
  nobody) is designed, and every failure names its reason and its next step;
- **plain-language over code vocabulary** on every label, toast, tooltip and summary;
- **motion with purpose** (enter/exit, progress, state change), never decorative jitter,
  and always inside `@media (prefers-reduced-motion: no-preference)`;
- **keyboard + bulk ergonomics** wherever rows or chips are involved;
- measured against the best consumer/SaaS tool in the category, not against the stock
  platform.

Icons come from the shared `ic()` set (`@pb_import_kit/js/import_icons`) — Lucide, never
emoji. `pb_dashboard` uses its own inline `ICONS` map for the same reason it has no kit
dependency; add to that map rather than importing one.

## The white-label rule (standing, binds every phase)

The word "Odoo" may never appear in anything a user can see: labels, chips, tooltips,
help text, placeholders, empty states, toasts, menu/action names, `string=`/`help=`,
selection labels, reports, exports, emails, `.po` msgstr, or a manifest `summary` /
`description` (**T18**, **T21** — a module with no `description` key has its README
printed in the Apps list instead). Technical identifiers, imports, model/XML ids, log
lines, code comments, docs and handovers keep the real name.

## Plumbing facts — verified 2026-09-09, do NOT re-derive

### The band picture (`pb_pay`, P1 + P2)

- Pure arithmetic, no OWL, no `@web`: `pb_pay/static/src/js/band_picture.js`
  (153 lines) exports `binPeople(wages, axisMax, trackPx, binPx, edges)`,
  `busiestBin(bins)`, `dodgeDots(dots, axisMax, trackPx, minGapPx)`.
  **Nothing in this file may import from `@odoo/owl` or `@web/…`** — the node check
  loads it off disk as a `data:` URL and any platform import breaks that.
- Its check: `node pb_pay/tools/band_picture_check.mjs` — numbered assertions T3a–T3g,
  one line each, non-zero exit on any failure. Extending a function means extending
  this file in the same phase.
- The cockpit: `pb_pay/static/src/js/pay_hub.js` (1170 lines), class `PbPayScreen`,
  registered as action `pb_pay`. Template `pb_pay/static/src/xml/pay.xml`
  (`pb_pay.PbPayScreen`), band rows at lines **224–312**. Styles
  `pb_pay/static/src/scss/pay.scss`, band block at **135–245**, dense overrides at
  **273–283**.
- **`axisPct(scope, value)` (`pay_hub.js:419`) assumes the axis starts at ZERO** —
  it divides by `scope.axis.max` only. The server's `_lane_axis`
  (`pb_pay/models/pb_pay_bands.py:320-359`) already returns `{'min': 0.0, 'max': high,
  'ticks': [...], 'beyond': n, 'note': str}`, so the `min` key exists and is ignored.
  Every position on the band row is measured through `axisPct`: `rangeStyle`,
  `midStyle`, `gripStyle`, `medianStyle`, `_bandPx`.
- `picture(scope, band)` (`pay_hub.js:521`) picks the shape: ≤24 named dots →
  `dodgeDots`; otherwise `binPeople` columns. `SHAPE.normal` / `SHAPE.dense`
  (`pay_hub.js:60-65`) hold every pixel size.
- The drag: `startDrag` stores `laneMax` from `scope.axis.max`; `onDrag`
  (`pay_hub.js:803`) maps `clientX` → `ratio` → `ratio * drag.laneMax`; `onGripKey`
  (`pay_hub.js:895`) steps by `top * 0.01` (`0.05` with Shift). All three read the axis
  as `0 … max`.
- Per-reader conveniences are namespaced localStorage keys, every read and write wrapped
  in try/catch: `FIT_KEY = "pbpay.bands.fit.v1"`, `DENSE_KEY = "pbpay.bands.dense.v1"`
  (`pay_hub.js:90-111`).
- Every band payload already carries the complete `wages[]` (sorted, whole currency
  units) plus `min`/`mid`/`max`, `median`, `symbol`, `symbol_before`, `min_short`,
  `max_short`, `people_scope` — so a per-band re-scale needs NO server call.
- `people_between(people_scope, low, high)` is the popover's read-back
  (`pay_hub.js:752`).

### The calibration picture (`pb_pay`, P2)

- Server: `pb_pay/models/pb_pay_reviews.py`, `calibration(review_id)` at **618–716**.
  `MAX_DOTS = 900` at **line 34** with the comment "How many dots the calibration
  picture draws"; the slice is `review.line_ids[:MAX_DOTS]` at **line 643**; the
  `capped` / `capped_note` keys are built at **713–716** and the note reads "The picture
  draws the first %(count)s people." — **that sentence is what rule 16 forbids.**
- Each dot carries `line_id`, `name`, `rating`, `column` (1…levels, clamped; an unscored
  person is placed in the middle column), `jitter` (`((line.id * 37) % 100) / 100`),
  `pct`, `position_pct`, `cost`, `team`, `outlier`.
- Outliers: two tests OR'd — more than 2 standard deviations above the mean rise of the
  same rating, or more than twice that rating's median and at least 2 points above it —
  plus any line whose chips block. `outliers[:60]` is a LIST cap, not a picture cap.
- `flat` / `flat_note`: when everybody is still on the guidance every dot sits on one
  line per rating. That is TRUE and it looks broken, so the screen says which it is.
- Browser: `pb_pay/static/src/js/pay_review.js` (956 lines), `openCalibration`
  **504**, `dotStyle` **532** (`left` = `6 + column*band + jitter*band*0.86` %,
  `bottom` = `(pct / max_pct) * 92` %), `scatterTicks` **545**, drag **560–590**
  (`document.querySelector(".pay-scatter")`, `set_proposals`, then a full re-read of
  `calibration`). Template `pb_pay/static/src/xml/pay_review.xml` **332–384**. Styles
  `pay.scss` **650–660**.
- `PAGE = 120` (`pb_pay_reviews.py:31`) is the WORKSHEET's page size — a different
  thing, and legitimate: the worksheet is a list you page through, not a picture.

### The Budget month strip (`pb_budget`, P3)

- Model `pb.budget`, `pb_budget/models/pb_budget.py`. The month helpers are a labelled
  block at **148–283**: `_month_keys(fy)`, `_month_date(key)`, `_month_bounds(key)`,
  `_month_in_fy(month, fy)` (accepts `'current'`, refuses anything outside the twelve),
  `_month_state(key)` → `past|current|future`, `_month_pace(key)`, `_month_words(day,
  full)` and `_month_title(day)` (both via **babel**, because `strftime` answers in the
  server's C locale and would print "Mar" on a Vietnamese screen), `_short(value)`.
- `_scope(fy, month)` at **261** returns `{'kind': 'year'|'month', 'key', 'label',
  'name', 'short', 'state'}` — this is what the whole board is ABOUT.
- `get_board(fy, budget_type, currency, row_cap, month)` at **~285**. Every function
  keeps its twelve `months[]` whatever the scope, so the spark on each tile still draws
  the whole year with the chosen month lit.
- Other scope-aware pieces: `_matrix` **384**, `_tone_month` **525**,
  `_tone_label_month` **545**, `_headline_month` **660**, `_expenses(function_id,
  months, btype, month)` **808**, `_rows(…, month)` **831**; exports
  `pb_budget/models/budget_export.py` `month_bars(board)` **210**, `_narrative_month`
  **275**.
- Browser: `pb_budget/static/src/js/budget_board.js` (722 lines) — `state.month`
  (`""` = whole year), `state.scoping`, `state.stripFocus`, deep link `pb_focus:
  "month:YYYY-MM"` read once at **86–95**, `setMonth` **~283**, `clearMonth` **~300**,
  `onStripKey` **~319** (reads the focused chip via `ev.target.closest("[data-month]")`),
  `focusChip` **~339**, `onKey` **~345** (Escape ladder: dialogs → drill → month),
  `isLit` **~425**, `monthHeight` **429**, drill bars **~444**.
  Template `pb_budget/static/src/xml/budget_board.xml` **182–206** is the whole strip:
  a `bdg-mchip--all` chip plus twelve `bdg-mchip` chips, each with a label, a two-tone
  micro bar (`bdg-mchip-fill`), and either "not yet" / "no budget" / a signed variance
  percentage, plus a `bdg-mchip-now` marker on the current month.
- FY is not always the calendar year: `_fy_start_month()` reads
  `ir.config_parameter` `pb_budget.fy_start_month` (default 1), and `_fy_label`
  prints `2026/27` when it is not January. **Any quarter must be a quarter of the
  FISCAL year, not Jan–Mar.**
- `pb_budget` ships an `ir.cron` (`data/ir_cron.xml`) — see **T20**: an upgrade fails
  outright with a `ParseError` naming that XML if the cron is RUNNING. Read the failure
  for "currently being executed" before believing the XML is broken; retry a minute
  later.

### Pulse and Explorer (P4)

- **Pulse** is the default lens of the Home hub: `pb_home_hub/static/src/js/home_hub.js`
  **113**, `{ key: "pulse", icon: "activity", label: _t("Pulse"), Component:
  PbDashboard }`. The component is `pb_dashboard/static/src/js/pb_dashboard.js` (320
  lines); its one data call is `pb.dashboard.get_dashboard_data()`,
  `pb_dashboard/models/pb_dashboard.py` (218 lines).
- That model has TWO documented rules in its own docstring, and both bind:
  **(1) no fabricated number, ever** — a database with no payslips reports zeros and an
  empty state, never a sample; **(2) no hard dependency on another cockpit** — the
  manifest is `['web', 'om_hr_payroll', 'pb_hr_payroll_base']`, everything it reads from
  another module goes through `optional()`, and
  `pb_dashboard/tests/test_activation.py::test_04` **walks this file's syntax tree and
  fails if a single such read sits outside an `optional()` call.**
- The KPI block is raw SQL at **106–127**: `SELECT max(date_from) FROM hr_payslip WHERE
  company_id IN %s` picks the reference month, then one aggregate over
  `hr_payslip` × `hr_payslip_line` × `hr_salary_rule_category` restricted to
  `p.date_from = ref` and to END-cycle configs (`fc.cycle_type = 'end_cycle' OR fc.id IS
  NULL`) — **because with a Mid+End cycle both slips carry the full GROSS and counting
  both double-counts the payroll and the headcount.** The screen never names the month
  it is showing.
- `hr.payslip.run` carries **no `company_id` field** in this codebase (om_hr_payroll
  does not declare one and none of the eight country modules adds one) — a `company_id`
  domain on it raises, which `safe()` would swallow into a silent zero
  (`pb_dashboard.py:68-75`).
- **Explorer** is `pb_explorer/static/src/js/explorer.js` (1158 lines) +
  `pb_explorer/models/pb_explorer.py` (2145 lines). The spec already carries
  `date_from` / `date_to` (`explorer.js:105-109`, applied server-side at
  `pb_explorer.py:493-496` as `date_end >= date_from` / `date_start <= date_to`), and
  the grain list already includes `month` and `quarter`
  (`_period_end` handles both, **873–904**) — **but there is no control anywhere in
  `explorer.xml` that sets either date.** They are only ever carried through the URL
  compaction (`explorer.js:269-292`, keys `m d g c f p a u`) and through "a starting
  point keeps the period" (**1047–1057**). That is the whole of the gap.
- Explorer's period vocabulary: `_clabel` **1150–1161** prints a month as
  `"%s %s" % (_MONTHS[d.month-1], d.year)` and answers `_('All periods')` when there is
  no grain. Coverage/pending periods are surfaced in the payload
  (`explorer.xml:94-105`, `663`).

## Deploy ritual (per phase — the repo `CLAUDE.md` contract is the authority)

1. Clean staging: `sudo rm -rf /tmp/deployX && mkdir -p /tmp/deployX`.
2. `rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude=.git <modules>
   Payobook19v2:/tmp/deployX/`.
3. Per module: `sudo rsync -a --delete /tmp/deployX/<m>/ /odoo/odoo-server/addons/<m>/`.
   **NEVER `--delete` with `/odoo/odoo-server/addons/` itself as the destination.**
4. Never deploy this repo's vendored copies of standard addons.
5. Stop the service, run the upgrade in a DETACHED systemd unit writing a sentinel
   (`--logfile`, **GR57**), poll with the Monitor tool, grep for `EXIT=` and for
   `traceback|critical|ERROR`, then start the service.
6. **Upgrade every database**: p9clone → payobook → abm → payobook_template.
7. After JS/SCSS: `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` per DB
   **and bump the `web.assets.version` ir.config_parameter per DB** — the immutable
   `/web/assets/<unique>/…` URL gets reused after regeneration on this box, so the purge
   alone leaves browsers on old bundles.
8. Verify: hash each module tree both sides (skipping `__pycache__`, `*.pyc`,
   `.DS_Store`); compare each manifest version to `ir_module_module.latest_version` in
   EVERY database (normalise the `19.0.` series prefix first).
9. **Bump the manifest version on every module you touch** — a code change with no
   version bump is invisible to the version-diff gate.

`odoo-bin -u … --stop-after-init` does NOT surface SCSS compile errors; assets compile
lazily at page load and a broken bundle shows up as a "Style error" toast with the real
message in `/var/log/odoo/odoo-server.log`. **Always Chrome-MCP load a page after an
SCSS deploy.** Sass evaluates its own `min()`/`max()` and dies on mixed units — write
`width: 76%; max-width: 420px`, never `min(420px, 76%)`.

## Validation contract (every phase)

Chrome MCP, on the live server, before reporting done. Standing owner approval covers
running and restarting it — never skip it, never pause to ask. Click every new control,
walk every new flow, and prove the states that break pictures: nobody, one person,
everybody on the same number, one huge outlier, a period with no data, a deep link to a
period that does not exist, keyboard-only, and `prefers-reduced-motion`.

Screenshots go in `docs/handovers/look_p<N>_shots/`.

## Commit contract

One feature-scoped commit per verified feature (explicit `git add` of named files, never
`git add .` — a parallel session may be running). Reviewer-focused message. **Do not
push** unless the owner asks; there are already ~104 unpushed commits on `19.1`.

Commit messages end with:

```
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

## Gotchas (append here, numbered L1, L2, …)

- L1 (P1): **`t-att-aria-expanded="isOpen(band)"` renders NOTHING when the value
  is `false`.** OWL drops an attribute whose value is boolean `false`, so a
  disclosure button that is closed carries no `aria-expanded` at all — the one
  state in which a screen reader most needs it, and the one state a walk is
  least likely to inspect. The DOM looks correct when the row is open, which is
  how it survived the first build. Any boolean ARIA attribute is written
  `cond ? 'true' : 'false'`, never handed the boolean.
- L2 (P1): **a fixed `padding-bottom` cannot hold a sentence.** The opened band
  grew by a fixed 84 px for its ruler and its two sentences, which is right at
  1440 px in English and prints the tail sentence over the NEXT band's name at
  390 px — where the same words wrap to six lines. Nothing errors and the
  desktop screenshot is perfect. Anything whose height depends on a translated
  sentence goes in NORMAL FLOW and the row grows by what it needs; if the growth
  has to be animated, animate the CONTENT arriving (opacity + a few pixels of
  travel) rather than a container height nobody can predict.
- L3 (P1): **re-scaling a row at `mousedown` moves the grip out from under the
  hand.** The drag axis is deliberately frozen with headroom at the press
  (§2e) — and freezing a WIDER axis than the one the row was drawn on moved the
  grabbed grip 149 px away from a cursor that had not moved, at 1440 px on a
  1,053 px track. The value was safe (the gesture already carried a grab
  offset), but the picture read as the grip running away. The fix is to ANCHOR
  the new axis: keep the held edge at the fraction of the track it already had
  (`lo = held − share × span`, floored at zero) and let the headroom fall either
  side of it. Any control that changes its own scale during a gesture needs the
  thing under the cursor pinned first and the scale chosen around it.
- L4 (P1): **a picture that stops its RULER lying has to stop its MARKS lying
  too.** The ruler picks its decimals from the span, so a zoom over 6.60M–6.68M
  prints five distinct labels. The bin labels went on using `shortMoney`'s one
  decimal at millions, and on the same zoomed band every mark read
  "12 people · 9.0M ₫ to 9.0M ₫" — a bin fifty thousand dong wide described as
  having the same two ends. Both ends of any money range printed on a zoomable
  picture take their figures from THAT range's own width, not from the size of
  the number.
- L5 (P1): **a capture-phase Escape handler outranks every element's own.** The
  cockpit registers `keydown` on `window` with `{ capture: true }` (WF4), so
  adding "the open band" to that ladder meant Escape reached the ladder BEFORE
  the focused grip's own handler and a keyboard drag could never be cancelled
  once a band was open underneath it. A gesture in flight has to be the FIRST
  rung of a capture-phase ladder, whatever the visual nesting says.
- L6 (P1): **`--pbim-canvas` and `--pbim-pill` are not tokens.**
  `pb_import_kit/static/src/scss/import_tokens.scss` defines `--pbim-bg` (the
  page canvas) and no `--pbim-pill` at all — yet `var(--pbim-pill)` is used for
  a border radius in the kit's own `.pbim-chip`, `.pbim-badge` and `.pbim-fchip`
  and in this module's `.pay-fitbtn`. An undefined custom property makes the
  whole declaration invalid, so those radii silently resolve to 0 across the
  product. Pre-existing and product-wide; recorded here so the next phase reads
  the token file before borrowing a name from a neighbouring rule.
- L7 (P1): **the shared axis's own note says "1 people".** `_lane_axis`
  (`pb_pay/models/pb_pay_bands.py`) builds one sentence for every count, which
  is GR42's trap in the one place GR42 did not sweep, and it is visible on
  p9clone the moment a band holds a single outlier. Vietnamese hides it (there
  is no plural), so an English-only walk is the only thing that finds it. The
  browser-side tail sentences added by this phase branch on `count === 1` and
  say "1 person". Server-side, so out of scope for a browser-only phase, and
  carried as an owner debt.
- L8 (P1): **a refused `move_edge` still raises the undo bar.** `endDrag` writes
  `state.undo` from whatever the server answered, and a refusal ("The lowest
  amount has to stay under the highest one.") is an answer — so the foot bar
  reads "Band moved." above a sentence saying it was not. Pre-existing, seen
  live while proving the drag, untouched by this phase.

- L9 (P2): **a `_t()` handed a DICTIONARY writes ONE per cent sign; two of
  them print literally.** WF24 is already in the ledger and this phase got it
  wrong anyway, because the SAME sentence exists on both sides of this
  feature: Python's `_()` interpolates with `%` and needs `%%` to emit one
  sign, and the browser's `_t()` with keyword arguments does not. The bar
  labels rendered "0.00%% to 0.30%%" on a live screen and nothing warned. The
  trap has a second half: the msgid then CONTAINS `%%`, so fixing the sentence
  is a catalogue change as well as a code change.
- L10 (P2): **the mark under the hand is exempt from every drawing cap.** A
  bin seven pixels tall can only hold a few rings before they draw over each
  other, so a busy bin rings the first few of its standouts — and dragging a
  ringed mark INTO such a bin took the mark off the picture in the middle of
  the gesture. The hand was still moving something and there was nothing on
  screen to see. Any picture that thins itself out has to make an exception
  for whatever is currently being held.
- L11 (P2): **a mark drawn at the middle of its own BIN cannot follow a
  hand.** The bins are the shape and a gesture is not: drawn at its bin's
  centre, the dragged mark answered a 120 px hand in seven-pixel steps. The
  held mark is drawn at the exact figure the hand is holding and everything
  else at its bin's centre — measured afterwards, 29/59/89/119 px for
  30/60/90/120.
- L12 (P2): **`overflow: hidden` on a plot deletes the numbers up its own
  side.** The tick labels are positioned OUTSIDE the plot box (`left: -46px`,
  in the margin the plot leaves for them), so the one property that stops a
  mark escaping the picture also clips the ruler that gives the picture its
  meaning — and the DOM still reports five tick elements, so only a screenshot
  finds it.
- L13 (P2): **the five words a rating is CALLED were module-level literals**
  (`SCALE_WORDS` in `pb_pay_guidance.py`), which is T24's trap: the extractor
  never sees such a string as a Python term, so "Needs support / Doing well /
  Very strong / Outstanding" printed in English under every column of a fully
  Vietnamese picture. They are now written inside `_()` in a dict keyed by
  value, with the order in a separate ladder (GR59). Fixed in this phase.
- L14 (P2): **a stored chip is frozen in the language of whoever last
  recomputed it.** `recompute_chips` writes the sentence for each row into
  `pb.pay.review.line.chips`, so a review recomputed by an English reader
  shows an English reason to a Vietnamese one — on the worksheet, in "what
  stops approval", and now in the calibration list. Pre-existing since P6b and
  surfaced by this phase; the fix is to store the ingredients and build the
  sentence at read time, which is a change to every chip. Owner debt.
- L15 (P2): **a substring replacement across a `.po` misses any msgid the
  exporter WRAPPED across lines.** Renaming a long term looked like it worked —
  the short ones changed, the wrapped one did not, and the screen went on
  printing English with the catalogue looking correct in a grep. Rebuild a
  catalogue from a fresh `odoo-bin i18n export` and carry the translations
  across by msgid; never edit msgids in place.
- L16 (P2): **a synthetic `KeyboardEvent` dispatched on `window` from the
  automation does not reach a capture-phase `useExternalListener` the way a
  real key press does.** Escape looked broken during a scripted walk and was
  perfect under `press_key`. Prove a keyboard contract with the browser's own
  key press; a dispatched event is only good enough for handlers bound to the
  element itself.


## Phase log

- P2 — "Everybody on the calibration picture" — designed and BUILT 2026-09-09
  (`LOOK_P2_EVERYBODY_ON_THE_PICTURE.md`). Status: **COMPLETE**.
  `pb_pay` 19.0.3.3.0 live on p9clone, payobook, abm and payobook_template;
  the module tree verified byte-identical to the repository on the server
  (`fc1ec439…079a` both sides) and every manifest version verified against
  `ir_module_module.latest_version` on all four. No other module touched.

  **THE HERO: four and a half thousand people open as five honest
  distributions, and nobody is hidden behind anybody.** The picture used to
  slice `review.line_ids[:900]` and say "The picture draws the first 900
  people." — the sentence rule 16 forbids, on the screen where it matters
  most. It now changes SHAPE: along each score's column the rise axis is cut
  into bins a few pixels tall by the same `binValues` the band picture uses;
  a bin with a handful of people draws each of them, a busier one draws a bar
  whose length says how many and which opens the named list of who is
  standing there. On the rehearsal review of **4,510 people the picture draws
  117 bars and 102 marks, and the sum of what every drawn element accounts
  for is 4,510 exactly**, measured in the browser against a SQL count.
  Proven again at **902** and at **12**.

  **And it gained the three things a calibration meeting asks for**: the
  shape of each score's spread; a tick at the MIDDLE of each score's rises
  (0.12 · 2.99 · 4.46 · 5.92 · 7.94% on the rehearsal, and it was not there
  at all before); and every drawable limit as a dashed line across the whole
  picture with its own sentence in a legend underneath. A column carries how
  many people HOLD that score and how many are DRAWN in it separately,
  because they differ by exactly the people nobody has scored — ten of them
  on the rehearsal, 152 of 152 on AB Mauri.

  **`calibration()` is now one `search_read` of four columns and carries no
  names at all** (R4/R5): 12 people **3–4 ms**, 902 people **20–34 ms**,
  4,510 people **85–119 ms** — five times the people for less than the
  162 ms the old 902 cost. The re-read after a drag is 87–124 ms, so no
  partial merge was needed. `calibration_people(review_id, rating, low, high)`
  is the new read-back, modelled on `people_between`, with a half-open bin so
  nobody is listed under two bars and the two ends of the axis closed so
  nobody clamped onto an end is lost.

  **The gesture.** The mark under the hand is drawn at the exact figure the
  hand is holding and is exempt from every thinning rule (L10, L11): measured,
  29/59/89/119 px of mark for 30/60/90/120 px of hand, the person's name on
  the foot bar, 6.94% and 8.75% read back from the database to the digit.
  Arrows move a rise by a tenth of a point and Shift by half a point;
  3.0 → 3.1 → 3.3 → 3.8 → 3.7, Enter, and the row reads back 3.7. Escape
  cancels the gesture first, then the panel, then the drawers, then leaves
  calibration.

  **L7 and L8 are closed**, each in its own commit and each proven: the
  shared money scale now reads "**1 person** is paid more than 136M ₫ and
  sits on the right-hand edge" on the owner's own lane (constructed live on
  p9clone and reverted), and a band move the server REFUSES shows the
  server's own sentence and raises no undo bar.

  **Tests.** 117 `pb_pay` tests on p9clone, **0 failed and 0 errors** (P1's
  baseline was 111; this phase added six and rewrote five). The wider run
  over **262 tests** (`pb_pay`, `pb_group` 54, `pb_contracts` 48, `pb_budget`
  39, `pb_hub` 34) reports **3 failures and 0 errors**, all three the
  p9clone data drift recorded since GROUP P6a: zero regressions.
  `band_picture_check.mjs` went from **34 checks to 44**.

  **Vietnamese** is complete: 812 terms, 0 empty, 0 fuzzy, 0 lost
  placeholders, 0 entries missing their `#. module:` comment, the word
  "Odoo" in no translation, and the `.pot` header rewritten off the
  platform's own name. The five words a score is CALLED were module-level
  literals and printed English under every column of an otherwise Vietnamese
  picture (L13) — fixed in `scale_words`.

  **Browser.** Walked on p9clone, payobook and abm at 1440 and 390, in
  English and Vietnamese, over all fifteen numbered tests, with no console
  errors. Screenshots: `docs/handovers/look_p2_shots/`. Report:
  `docs/handovers/LOOK_P2_REPORT.md`.

  Everything created to test with was undone and the removal verified: four
  p9clone reviews (4,510 · 902 · 12 · 0), 18,000 copied scores, one guidance
  grid, a spread written over 4,510 rows and one contract temporarily raised
  to ₫900M are all gone and the contract is back at ₫129,800,000; the
  eleven-minute 902-person review on payobook and the 152-person one on abm
  are gone; payobook_template was never written to. All four databases carry
  **0 reviews, 0 worksheet rows, 0 guidance grids and 0 bands**, and
  payobook keeps only the two performance scores GROUP P6b kept.

  Owner debts: the payobook administrator password in the GROUP ledger is
  still wrong (GR24) and so is abm's (WF15) — P2 used one temporary
  `look.p2@payobook.com` on p9clone (4388), payobook (4428) and abm (263),
  all archived again at the end of the phase; a reason written on a review
  row is frozen in the language it was written in (L14); nobody has scored
  anybody on AB Mauri; the `pbim` kit still has no dark palette (GR38);
  6 commits made and NOT pushed (120 now waiting on `19.1`).

- P1 — "Open this band out" — designed and BUILT 2026-09-09
  (`LOOK_P1_OPEN_THIS_BAND_OUT.md`). Status: **COMPLETE**.
  `pb_pay` 19.0.3.2.0 live on p9clone, payobook, abm and payobook_template; the
  module tree verified byte-identical to the repository on the server
  (`b5fab614…c7ab` both sides) and every manifest version verified against
  `ir_module_module.latest_version` on all four. No other module touched: this
  phase is browser-only inside `pb_pay`, with no model, schema, migration or
  server method added.

  **THE HERO: a band that was a smear unrolls under the cursor.** On the
  owner's own "Construction · level 2 · Vietnam" — 544 people, 6.6M to 11M ₫ on
  an axis reaching 136M ₫ — the band occupied **37 px of a 1,053 px track
  (3.49%)** and drew its people as nine marks. Opened out it fills **70.83%**
  of the track in **67** marks, with a ruler under it in its own money, a
  hairline above it showing which 4.9% of the shared scale this is, and one
  sentence saying out loud that its width no longer compares with its
  neighbours. **544 people are drawn in both states and the chips read
  "57 below" / "82 above" in both.**

  Three ways in and one way out, all proven live: hover opens after 180 ms and
  leaving closes after 140 ms (nothing at 120 ms, open by 320 ms, still open
  80 ms after leaving, closed by 280 ms), all of it behind
  `(hover: hover) and (pointer: fine)` so a touch screen gets the button and
  nothing else; the button pins; a drag opens and pins. Escape closes it, as
  the outermost rung of the existing ladder. **The pin is not remembered
  between visits and no new localStorage key was added.**

  `band_picture.js` learned that an axis has two ends: `binPeople` and
  `dodgeDots` take the axis OBJECT, `axisSpan` is the one guarded definition of
  its width, and the new `bandAxis` works out a band's own scale from the wages
  the browser already holds — containing the band, not flattened by one
  outlier, padded and floored at zero, never degenerate, both tails counted,
  and deterministic. `band_picture_check.mjs` went from **13 checks to 34**.

  The drag freezes its ruler at the press with 30% headroom AND anchors it so
  the grabbed grip does not move (L3): measured, the grip stays under a
  stationary cursor and travels 151 px for a 150 px hand. An edge dragged past
  the end of the picture reached **13.4M ₫** where the picture ended at 12.7M,
  and the axis recomputed on release. Arrows step by 1% of the DRAWN span
  (10 px) and Shift by 5% (53 px) — thirteen times finer under zoom than on the
  shared axis. Undo restored all three numbers exactly, twice.

  The ruler may not print the same label twice: it takes its figures from the
  span, drops to fewer ticks rather than repeat itself, and stops rounding
  altogether if two ends still cannot be told apart. Proven on a constructed
  6.60M–6.68M band (**6.595M · 6.618M · 6.640M · 6.662M · 6.685M ₫** where one
  decimal would print "6.6M" five times) and on real abm data (a 14-person band
  at 11.10M–13.90M ₫). The same rule now governs the mark labels (L4).

  **Tests.** 111 `pb_pay` tests on p9clone, **0 failed and 0 errors**. The
  wider run over **248 tests** (`pb_pay` 111, `pb_group` 54, `pb_contracts` 48,
  `pb_budget` 39, `pb_hub` 34) reports **3 failures and 0 errors**, and all
  three are the p9clone data drift the GROUP ledger has recorded since P6a
  (`pb_contracts` ×2, `pb_group` `test_t9`): zero regressions.

  **Vietnamese** is complete: 780 of 780 exported terms, 0 English survivors, 0
  fuzzy entries, 0 lost placeholders, 0 entries missing their `#. module:`
  comment (GR5), the word "Odoo" in no translation, and the freshly exported
  `.pot` header rewritten off the platform's own name (WF27).

  **Browser.** Walked on p9clone, payobook and abm at 1440 and 390, in English
  and Vietnamese, over all fifteen numbered tests. Screenshots:
  `docs/handovers/look_p1_shots/`. Report: `docs/handovers/LOOK_P1_REPORT.md`.

  The p9clone rehearsal — 21 accepted bands, 11 families, 30 job links, two
  constructed thin-data bands and one contract temporarily raised to ₫700M —
  was undone and DELETED afterwards and verified gone; payobook, abm and
  payobook_template carry **0 bands, 0 families and 0 job links** and still
  open on the suggestion. Nothing was written to production beyond the module
  upgrade.

  Owner debts: the payobook administrator password in the GROUP ledger is still
  wrong (GR24) and so is abm's (WF15) — P1 used one temporary
  `look.p1@payobook.com` on p9clone (4338), payobook (4427) and abm (262), all
  archived again at the end of the phase; the shared axis's own note still says
  "1 people" (L7); a refused band move still raises an undo bar reading "Band
  moved." (L8); the `pbim` kit still has no dark palette (GR38); 3 commits made
  and NOT pushed (111 now waiting on `19.1`).
