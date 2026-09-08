# LOOK P4 — The period on Pulse and on Explorer

**Read `docs/handovers/LOOK_LEDGER.md` in full first**, and the parent ledgers it names
(GROUP, TIDY, WFPLAN, RIZE), and the P1, P2 and P3 reports for the whole L-series.

**Modules touched: `pb_dashboard` and `pb_explorer`.** Two screens, two different
questions, one visual language and one keyboard contract. This is the last phase of the
programme; it also writes the closeout.

---

## 0. What you are building, in one paragraph

Two screens still cannot answer "what about March to June". **Pulse** — the first screen
every tenant sees — silently reports the most recent payroll month and **never names
it**: the headline figures on the home page have no period on them at all, which is the
one thing that makes a number uncheckable. **Explorer** reads as a sentence — *Show
total cost By department Over month Where …* — and is missing a clause: it has
`date_from` and `date_to` in its spec, the server honours them, and **there is no
control anywhere on the screen that sets either one.** They arrive only through a saved
link. You are giving Pulse a period it names and a strip to change it, and giving
Explorer the **When** it never got.

---

## 1. Rulings — decided, do not re-open

**R1. `pb_dashboard` gains no new dependency** (ledger rule 19). Its manifest stays
`['web', 'om_hr_payroll', 'pb_hr_payroll_base']`. It keeps its own inline `ICONS` map
and its own SCSS. Do not import `@pb_import_kit/js/import_icons`, do not import
`pb_hub`, do not "just share" P3's strip. The two strips look like siblings because you
build them to the same visual language, not because they share a class.

**R2. `pb_dashboard`'s two documented rules are not negotiable.**
- **No fabricated number, ever.** A database with no payslips reports zeros and an empty
  state. It has already reached a real customer's screen once with a hard-coded sample
  dict; there is a test that greps for the legacy model.
- **Every read of another module's model goes through `optional()`.**
  `pb_dashboard/tests/test_activation.py::test_04` **walks this file's syntax tree** and
  fails if one does not. `hr.payslip` is fine — `om_hr_payroll` is a declared
  dependency — but if you reach for anything else, it goes through `optional()`.

**R3. The Mid/End double-count guard survives verbatim.** The KPI aggregate is
restricted to end-cycle configs (`fc.cycle_type = 'end_cycle' OR fc.id IS NULL`) because
with a Mid+End cycle **both slips carry the full GROSS**, so counting both doubles the
payroll AND the headcount. Whatever you do to the period, that clause stays and you
prove it still holds for a month that has both kinds of run.

**R4. Naming the period is the fix; the strip is the upgrade.** Even a reader who never
touches the strip must now see which month the home page's figures are about. If you
build only one thing in Pulse, build that.

**R5. Explorer's period is a clause in its sentence, not a filter in its "Where".**
It goes in its own chip group labelled **When**, between "Over" and "Where", in the same
picker idiom as Show / By / Over. Putting a period among the filters would bury the one
thing every number on the screen depends on.

**R6. Explorer's period costs one `read_group`, not a scan.** `pb.fact.month` is an
indexed `fields.Date` (`pb_explorer/models/pb_fact.py:63`) over a derived fact table
(711k payslip lines reduce to a few thousand fact rows). The strip's per-month weight is
a `read_group` on that column. Never iterate facts in Python to build it.

**R7. A shared Explorer link must carry its period.** The URL compaction
(`explorer.js:269-292`) packs the spec into the keys `m d g c f p a u` — **`date_from`
and `date_to` are not among them**, so today a period set in one browser is lost the
moment the link is shared. Add them, in the same short-key style, and prove a
round-trip.

**R8. Reuse P3's period vocabulary, do not invent a second one.** Presets, the
`'YYYY-MM..YYYY-MM'` and `'QN'` forms, the collapse rules, the plain-English naming
("March to June 2026", "Q2 2026 · April to June") and the keyboard contract all come
from P3. Read what P3 actually shipped before designing anything here; if P3's helpers
are reusable from `pb_budget`, **do not import them** — `pb_explorer` must not depend on
`pb_budget` (it is the other way round today: `pb_budget` depends on `pb_explorer`).
Match the vocabulary, not the code.

---

## 2. Deliverables — Pulse (`pb_dashboard`)

### 2a. Server

`get_dashboard_data(self)` becomes `get_dashboard_data(self, period=None)`, accepting the
P3 vocabulary. Callers to sweep: `pb_dashboard/static/src/js/pb_dashboard.js:122`
(positional, so free) and `pb_dashboard/tests/test_activation.py:292`, `:340`, `:359`.

Add to the payload:

- **`period`** — what this board IS about, resolved on the server (rule 18): its key,
  its plain-English label ("March 2026"), and its state (past / current / future).
- **`periods`** — the payroll months that actually exist, company-scoped, oldest to
  newest, each with its key, its label, its total payroll and its headcount. This is one
  grouped SQL query over `hr_payslip` with the same end-cycle restriction as R3 — not
  one query per month.
- The **KPI block** becomes about the resolved period rather than about
  `max(date_from)`. The default period is still the latest month that has data, so a
  reader who does nothing sees exactly what they see today.

A database with no payslips: `periods` is empty, `period` is null, the KPIs are honest
zeros, and the screen says so in its own words. That is R2, and it is a test.

### 2b. Browser

- **The KPI card names its period** (R4), plainly: "For March 2026", not a bare date.
- **The strip** sits under the KPI row: one chip per payroll month, chronological, the
  chosen one lit, the latest one marked as the latest. Each chip carries the month and a
  micro bar of that month's payroll against the busiest month, so the shape of the year
  is readable before anything is pressed — that is this strip's own question (rule 19).
- Many months: the strip scrolls horizontally and **scrolls the chosen chip into view**;
  it does not shrink chips until they are unreadable and it does not drop months.
- Keyboard: the ledger's rule 20 contract, identical to Budget's.
- Deep link: the Home hub hands arrival context to its lenses
  (`home_hub.js` `propsFromContext`). Accept `pb_focus: "month:YYYY-MM"` and
  `"month:current"` in the same vocabulary Budget uses, with rule 21's fallback.
- Motion, and its absence, per the design bar. **L2**: nothing sized by a translated
  sentence gets a fixed pixel height.

---

## 3. Deliverables — Explorer (`pb_explorer`)

### 3a. The **When** clause

A new chip group between "Over" and "Where", built in the existing picker idiom
(`explorer.xml:210-248` is the pattern to clone — chip, `togglePicker`, menu, `active`
class, a check on the chosen row). The chip's label is the period in plain English, and
"Everything" when there is none.

The picker holds, in this order:

1. **Presets** — This month, Last month, This quarter, Last quarter, This year, Last
   year, Everything. Each names the actual dates it means, so nobody has to guess what
   "this quarter" is on a July fiscal year.
2. **The month strip** — one chip per month that has facts, each carrying its weight for
   the CURRENT measure, so the strip is a sparkline of the question being asked and it
   redraws when the measure changes. Press one for a month; shift-press or drag for a
   stretch, exactly as P3 shipped it.

Setting a period sets `spec.date_from` / `spec.date_to`, which the server already
honours (`pb_explorer.py:493-496`). The browser then adopts what the server answered,
never what it asked for (rule 18).

### 3b. Server

- `schema` gains the presets and the available months with their weights — the
  `read_group` of R6, scoped and measure-aware.
- The payload echoes the resolved period so the browser can adopt it.
- **The coverage and pending notes become period-aware.** "3 pay periods are still being
  built" is a different message when none of the three is inside the period on screen;
  today it is stated flatly (`explorer.xml:94-105`). Say what is true for the period the
  reader is looking at.
- `drill(spec, …)` and `export_csv(spec)` already take the spec and therefore inherit the
  period for free — **prove it rather than assuming it**, and make sure the CSV names its
  period in its own content, not only in its filename.

### 3c. States that must be designed

- **No facts at all** (a fresh tenant) — the When chip says "Everything", the picker
  explains there is nothing to choose yet, and it is not a dead end.
- **A period with no data** — the empty state already says "Try widening the filters or
  picking another period" (`explorer.xml:473-476`); now that there IS a period control,
  that sentence must point at it.
- **A period that predates the facts**, one entirely in the future, and one that
  straddles the built/unbuilt boundary.
- **A shared link** carrying a period (R7), and one carrying a malformed period.
- A period **plus** a drill **plus** filters, all at once, and the breadcrumb still
  making sense.

---

## 4. Design — the bar

> **extreme WOW, intuitive, out-of-this-world experience, best in class.**

**Name the hero moment in your report.** Two candidates, and you may claim both:
Explorer's sentence finally completing — *Show total cost By department Over month
**When March to June 2026*** — with a strip that is a live sparkline of the very
question being asked; and the home page's headline figures naming their month for the
first time, with the shape of the whole year readable underneath them.

Zero dead-ends: every state in §2a and §3c designed. Plain language everywhere. Motion
with purpose only, inside `@media (prefers-reduced-motion: no-preference)`. Full
keyboard parity. Lucide via `ic()` in Explorer; Pulse's own inline `ICONS` map (R1) —
add to it rather than importing one. No emoji anywhere.

---

## 5. Tests (numbered — run on p9clone, report each one)

1. **Pulse names its period** on first load, with no interaction.
2. **Pulse's default is unchanged**: the KPIs on first load equal today's KPIs to the
   digit, on a database with data. Capture before you start.
3. **The Mid/End guard holds (R3)** for a month carrying both an advance run and an end
   run: the payroll and the headcount are not doubled. Compare against SQL.
4. **Pulse with no payslips**: no strip, honest zeros, an empty state that says so, and
   `test_activation.py` still green — **including `test_04`'s syntax-tree walk**.
5. **Pulse's strip**: pick each month, compare each against SQL; many months scroll and
   the chosen chip is scrolled into view; keyboard contract per rule 20; deep links
   `month:YYYY-MM`, `month:current`, and one outside the data.
6. **`pb_dashboard` gained no dependency** — diff the manifest and prove it.
7. **Explorer's When clause** sets the period; every number, the chart, the coverage
   note and the breadcrumb change with it.
8. **Each preset** names the right dates, on a January fiscal year AND on a July one.
9. **A stretch** by shift-press and by drag, matching P3's behaviour and vocabulary.
10. **The strip is measure-aware**: change the measure, the strip's weights redraw.
11. **R6 performance**: time the strip's `read_group` on the biggest fact table
    available and report the number. Report Explorer's overall load time with and
    without a period.
12. **R7 round-trip**: set a period, copy the link, open it in a clean session, get the
    same period. Then a malformed one, which must not error.
13. **Drill and export carry the period** (§3b), and the CSV names it in its content.
14. Every state in §3c, screenshotted.
15. **Vietnamese** on both screens: the period names, the presets, the empty states, the
    coverage sentences.
16. **Reduced motion**, and **keyboard only** end to end on both screens.
17. **Nothing regressed**: `pb_dashboard`, `pb_home_hub` and `pb_explorer` suites green
    (P1 measured `pb_explorer` at 46 tests at GROUP P3; re-measure and report), and the
    wider run at the same pre-existing baseline — **248 tests with 3 known p9clone drift
    failures (`pb_contracts` ×2, `pb_group` `test_t9`)** as of P1. Name what you measure.

---

## 6. Deploy

`pb_dashboard` and `pb_explorer`. Bump both manifests (`pb_dashboard` → **19.0.1.2.0**;
`pb_explorer` one minor from whatever it is when you start — it was 19.0.2.2.1). Ledger
deploy ritual exactly, all four databases in order p9clone → payobook → abm →
payobook_template, `pg_dump` before each.

Python and assets both change: a real `-u` for both modules, then purge `/web/assets/%`
**and** bump `web.assets.version` per database, then Chrome-MCP load both screens.
Remember Pulse is the FIRST screen of every tenant — if you break it, every tenant sees
it, so walk it on all four databases and not only on p9clone.

---

## 7. Report back, and close the programme

Write `docs/handovers/LOOK_P4_REPORT.md` and, because this is the last phase, also
**`docs/handovers/LOOK_CLOSEOUT.md`**: what the four phases delivered in plain English,
every module and version, the full L-series, the numbers that prove each phase's claim,
and — most importantly — **the complete list of open owner decisions and debts** carried
from this programme and inherited from GROUP/TIDY, in one place, written for somebody
who does not read code.

Append your gotchas to `LOOK_LEDGER.md` (continuing the L-series) and the final
phase-log line. Return a summary covering: each numbered test with its result and
evidence (screenshots in `docs/handovers/look_p4_shots/`); the hero moment named; the
self-score against the design bar; any ruling you bent and why; anything this handover
got wrong about the code; the four databases' versions and tree hashes; the commits
(feature-scoped, explicit `git add`, **not pushed**); and the owner-decision list.
