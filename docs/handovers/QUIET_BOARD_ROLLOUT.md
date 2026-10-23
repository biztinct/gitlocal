# QUIET BOARD rollout — every screen gets the Hiring look (2026-09-23)

Owner approved the Hiring board and asked for the same look on every other
screen: "finish off in other screens as well what you did to Hiring board (new
look related to tiles, workflow look etc)".

Scope of THIS rollout (owner's earlier ruling: "looks + the step strip across
all screens first, then the Next boxes screen by screen"):

1. **Quiet numbers** — replace every row of big statistic tiles with ONE slim
   clickable line.
2. **Numbered step strip** — on every screen whose records move through a
   workflow (states / stages), a strip of numbered step cards 01..N with the
   round arrow badge, a count pill that names its unit, and an amber flag
   under a step when something there is waiting on a person.
3. **"Step N of M · <step>"** line on each record card where the screen has
   cards and a step strip (optional per screen; skip if the screen is a table).

**Binding non-goals**
- NO "Next" boxes (the sentence + one button) — those come later, screen by
  screen, after the owner sees this.
- NO change to data, models, server methods' behaviour, security, menus.
  Adding a field to an existing JSON payload a board already loads is fine
  (e.g. a per-state count); new server methods only if unavoidable.
- Analytics screens KEEP their big tiles (numbers are the point there):
  `pb_insights`, `pb_explorer`, `pb_workforce_insights`, `pb_decision_room`,
  `pb_demo` (demo_analytics), `pb_dashboard`, `pb_today` (Home pulse),
  `pb_goals/goals_numbers.xml`, `pb_hiring/hiring_numbers.xml`,
  `pb_training/training_numbers.xml`. Do not touch them.
- Hiring (`pb_hiring/hiring_board.xml`) is already done. Do not touch it.
- Do not touch `pb_import_kit` (the shared pieces are already written — below).
- A figure the person came to the page to READ (a pay run's gross/net totals,
  a report's headline money figure) may stay prominent. Counts of things that
  exist to navigate/filter go quiet. When unsure: quiet.

## The reference — verified, do not re-derive

- Hiring board is the reference: `pb_hiring/static/src/xml/hiring_board.xml`
  lines 81–118 (glance line, steps, showing line) and
  `pb_hiring/static/src/js/hiring_board.js` getters `stages` (l.337),
  `stageMeta`, `showingLine` (l.363), `showAll`, `glance` (l.383),
  `pressGlance`, `chooseJourney` (l.573), `stageOf`.
- Live prototype the owner iterated on:
  https://claude.ai/artifact/DGTZJXpgFdnTaJNua9ti1M
- **Shared pieces now in the kit (use them, don't copy CSS):**
  - Styles `pb_import_kit/static/src/scss/quiet_board.scss` — top-level
    classes with token fallbacks, so they work on non-`.pbim` screens too:
    `.pbim-glance/.pbim-gl(-n,-l,-dot)` (`.zero .is-amber .is-rose .is-green
    .on .flat`), `.pbim-steps/.pbim-st(-top,-n,-t,-c,-s,-flag,-heat,-arrow)`
    (`.on .has .wait`, `.is-many` auto for >4 steps), `.pbim-showing`,
    `.pbim-showall`, `.pbim-where(-marks)`, `.pbim-next` (not used yet).
  - Templates `pb_import_kit/static/src/xml/quiet_board.xml`:
    ```xml
    <t t-call="pb_import_kit.QuietGlance">
      <t t-set="qGlance" t-value="glance"/>          <!-- [{key,n,label,tone,run}] -->
      <t t-set="qGlanceOn" t-value="state.focus"/>    <!-- key now filtering, or '' -->
    </t>
    <t t-call="pb_import_kit.QuietSteps">
      <t t-set="qSteps" t-value="steps"/>             <!-- [{key,n:'01',title,countLabel,count,sub,flag,flagTone,on}] -->
      <t t-set="qStepsLabel" t-value="'Where every contract is'"/>
      <t t-set="qStepPick" t-value="(k) => this.pickStep(k)"/>
    </t>
    ```
    Parameter names carry a `q` prefix (verifier fix 2026-09-23): a plain
    `t-set="glance"` crashes the screen when the component has a `glance` getter.
    `run` is a function (or null → the figure is plain text). `flag` is a whole
    translated sentence ("2 waiting for a sign-off", "1 waiting on you") or ''.
  - The screen's module must depend (directly or transitively) on
    `pb_import_kit` — nearly all pb_* boards already do. If a module does
    not, add it to `depends` ONLY if it is a pb_* module that already loads
    the kit's classes; otherwise copy the markup with the same class names
    (the CSS is global) and say so in your report.

## The rules the owner set (from the prototype rounds)

1. Numbers line: grey at zero; a colour ONLY when a person must act (amber =
   waiting on someone, rose = a problem/late/over, green = a good outcome
   like "joined this month"). Everything else neutral. Every figure that
   used to filter when pressed still filters (`run`); pressing the lit one
   again clears it.
2. Steps: numbered `01`, `02`… The count is a SEPARATE pill that names its
   unit ("3 contracts", "1 contract") — a bare number reads like a step
   number (owner complaint). An item is at EXACTLY ONE step so the counts add
   up to the total (the Hiring bug the owner found: the same card under two
   steps). No fake "Overview/All" step — pressing a lit step again, or "Show
   all" in the showing line, clears the filter.
3. Under a step: an amber flag "N waiting for a sign-off" (or "N waiting on
   you", which beats it) when the screen knows about approvals; skip if it
   doesn't.
4. A showing line under the steps: "Showing all 12 contracts · press a step
   or a number to narrow it" / "Showing 3 of 12 contracts at Signed · Show
   all" / "no contracts yet" when empty.
5. Only draw a step strip if the screen's records really move through ordered
   states. A screen that is a list of settings, a calendar, or a report gets
   the quiet numbers only. If the screen ALREADY has a stage/flow strip
   (e.g. Probation's "How a review runs" `.prb-flow`, lifecycle stage
   chips), REPLACE it with the numbered steps rather than adding a second.
6. Keep the page's own colour identity (each lens has its tint via
   `--pbim-*` tokens) — the kit classes read those tokens.

## Standing rules (bind every change)

- **White label:** the word "Odoo" must never appear in any user-visible
  string (labels, tooltips, aria-labels, empty states, translations).
  Technical identifiers are untouched.
- **Translations:** every NEW user-visible string: in JS use `_t("…")` with
  `%s` placeholders, whole sentences (never glue fragments in XML); in XML
  plain text is extracted automatically. Add a Vietnamese entry to the
  module's `i18n/vi_VN.po` for each new string, and each entry MUST carry
  all three comment lines or the upgrade crashes / stays English:
  ```
  #. module: <module>
  #. odoo-javascript
  #: code:addons/<module>/static/src/<path>:0
  msgid "…"
  msgstr "…"
  ```
  Don't duplicate an msgid already in the file. `python3 -c "import polib"`
  is not available — check by eye; the verifier parses them.
- OWL gotchas: no computed object keys in `t-att-class`; use string
  concatenation. `t-esc` for text. Keep `t-key` on every `t-foreach`.
- Lucide icons only, no emoji. No gradients.
- Bump each touched module's manifest patch version (e.g. 19.0.1.4.2 →
  19.0.1.4.3).
- Remove CSS that your change leaves dead (old tile/flow rules for that
  screen), but don't refactor beyond the screen.
- Do NOT start, stop or upgrade any Odoo server, and do NOT use the browser —
  several agents are editing in parallel; a single verifier runs everything
  afterwards. Do NOT commit. Do NOT touch files outside your module list.
- Static checks you must run on every file you touched:
  `python3 -c "import xml.dom.minidom,sys; xml.dom.minidom.parse(sys.argv[1])" <file.xml>`
  and for JS `node --check` is not enough for ES modules — use
  `node --input-type=module -e "$(sed 's/^import .*//' <file.js>)" 2>&1 | grep SyntaxError`
  or equivalent to catch syntax errors.

## Report back (keep it short)

Per screen: what the numbers line shows (list of figures + tones), the steps
(titles, which states map to each — proving one item = one step), anything
kept big and why, dead CSS removed, versions bumped, strings added to
vi_VN.po, anything you skipped or were unsure about.
