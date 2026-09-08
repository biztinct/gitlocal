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

_Nothing yet — P1 is the first phase._

## Phase log

_Appended by each phase report._
