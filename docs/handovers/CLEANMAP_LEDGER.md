# CLEANMAP — conventions and gotcha ledger

Programme: **"the Mapping home shows only what is true for what you picked."**
Two phases, designed 2026-09-19 by Fable, to be built by Opus **later** — see
"DO NOT START" below.

| Phase | Handover | Size |
|---|---|---|
| P1 | `CLEANMAP_P1_LEFT_LIST_HANDOVER.md` — the Spreadsheet board's left list obeys FROM | small |
| P2 | `CLEANMAP_P2_JOURNEY_HANDOVER.md` — the Journey redesign (mapped-only, expandable cards, Payobook Source lane) | large |

## Go-ahead (owner, 2026-09-19, later the same day)

The hold is LIFTED. The other session (SCHEMECTX) finished at `b8509939d`.
Checked by Fable: it did not touch `models/pb_formula_studio.py`, any
`static/src/js/mapping/*`, `journey_board.xml` or `journey.scss`. It DID rewrite
`pb_formula_studio/i18n/vi_VN.po` heavily and moved the manifest to
`19.0.1.198.0` — so P1 ships as `19.0.1.199.0`, P2 as `19.0.1.200.0`, and new
VI strings are APPENDED to the current `.po`, never regenerated.

Anchors in the handovers are still by symbol name first, line number second —
re-verify before editing.

## Standing rules every phase inherits (state them in any sub-prompt)

* **White-label**: the word "Odoo" never appears in a user-visible string
  (labels, tooltips, empty states, errors, `.po` msgstr). Technical identifiers
  untouched.
* **Design bar, verbatim**: "extreme WOW, intuitive, out-of-this-world, best in
  class" — hero moment, zero dead-ends, plain language, purposeful motion, bulk
  ergonomics. Lucide icons via `ic()`, never emoji. Locked Payobook palette,
  white + rail, no gradients.
* **Browser validation is mandatory**: a phase is not done until it has been
  opened in Chrome MCP on `rize.payobook.com`, light and dark, and the console
  read. Chrome MCP has standing approval; restart the server if it is down.
* **Deploy contract**: ONE addons dir `/odoo/odoo-server/addons`; clean staging;
  per-module `rsync -a --delete`; upgrade EVERY database; purge
  `/web/assets/%` attachments after JS/SCSS; verify content hash + version per DB.
* **PO rules**: see memory `po-translation-loading-rules` — run the parse gate
  before deploy. A translation fix is two fixes (L24): the `.po` AND any value
  already stored per DB.
* **Commit per feature**, explicit file staging, never `git add -A` (another
  session's files are in the tree). Do not push.
* **Demo data**: no "RIZE" in demo records on payobook.com; reuse persistent
  demo fixtures, no ZZ throwaways.
* **Read-only boards stay read-only**: the Journey writes nothing (MF37 diff
  proof). P2 must keep that — expanding a card is client state, never a write.

## Ledgers this programme stands on (read, do not re-derive)

* `JOURNEY_LEDGER.md` (MJ1–MJ29) — esp. MJ10 (nodes are buttons), MJ16
  (`env.get` is None-or-model; empty recordset is falsy), MJ19 (two-line JS
  string with no `+` blanks the whole backend), MJ22 (primary connector =
  `config.connector_id`, nothing else).
* `RUNSRC_LEDGER.md` (RS1–RS27) — esp. RS8 (no lane of zeroes), RS13 (the
  source vocabulary lives in FOUR places), the dual-key storage being
  load-bearing.
* W146 — DOM `dataset.id` is always a string; mint string ids.
* MAPFIX-D / F1 — a wire whose `leftId` has no card crashes the canvas; a
  suppressed wire is never drawn to a column edge pretending to be real.

## CLEANMAP gotchas (append as they are hit)

* **CM1** — A loaded pay run stores each column under a different number of
  names depending on how the file was read. Single-sheet list rows: TWO
  (`heading`, `A`), interleaved per column
  (`payroll_import_batch._raw_data_from_row`). Multi-sheet dict rows: **FOUR**
  (`heading`, `Sheet|heading` for every column FIRST, then `Sheet|A`, `A` per
  column — `_load_multisheet_data`, the `base_row[...]` block). RUNSRC A1's
  `_column_alias_fold` walks positionally and only understands the first shape;
  `test_runsrc_left_columns.test_05_multisheet_dict_rows_are_untouched` PINS the
  gap on purpose. Rize's workbook is multi-sheet: 43 columns × 4 = 172 cards.
* **CM2** — The left list of the Spreadsheet board is an UNION of four lanes
  regardless of what FROM says (`_import_left_columns`). FROM only ever chose
  which batch fills lane 2. That union is why a 43-column file reads "180
  fields".
* **CM3** — Every accepted wire MUST have a left card (MAPFIX-D). Any rule that
  removes cards must either re-point the wire at the surviving card of the same
  real column, or keep a card for it. Never drop the card and keep the wire.
* **CM4** — The Journey's `journey_data` iterates `Conn.search([])` — every
  connector on the database — not the connectors that feed this scheme. That is
  why an unused "Zoho People — inbound" and seven never-synced feeds are drawn.
  The Spreadsheet board's FROM list has the same shape: `contexts` is every
  batch on the database, not this scheme's. **Consequence for tests**: a test
  that calls `import_mapping_data(cfg, False)` on a real database does NOT get
  the empty-board path — the RD60 ladder happily lands on somebody else's
  batch. To exercise `source='none'`, create a batch with no import lines and
  pass its id.
* **CM5** — **CM1 is confirmed, with one correction.** Read off rize batch 1128
  (`Rize Vietnam Payroll · August 2026 — pay data`, first line, 2026-09-19):
  **174 keys**, in three blocks, not interleaved — 43 bare headings (1–43),
  then 43 `Salary|heading` (44–86), then 44 `Salary|<letter>` + `<letter>`
  PAIRS (87–174). The handover said "every `heading` + `Sheet|heading` first";
  it is in fact *all* headings, *then* all `Sheet|heading`. 43 unique headings
  but 44 letters: the workbook has two columns with the same heading text, and
  `base_row = row.copy()` collapses them.
* **CM6** — So the fold cannot use "heading count" to decide whether a
  letter-shaped key is an alias. It uses the **unbroken A, B, C… run of letters
  written for that sheet**, which is the sheet's real column count
  (`headers_meta`). On rize that is 44, so `Salary|AR` (index 43) is an alias;
  on a 10-column sheet a column genuinely headed `AR` keeps its card. The two
  storage shapes are told apart by WHERE the first letter-shaped key sits:
  position 1 on the interleaved `_raw_data_from_row` shape, position ≥2 on the
  merge shape.
* **CM7** — A duplicated heading costs the last column its alias map entry:
  `Salary|AR` and `AR` fold away (they are aliases) but have no canonical card
  to point at, because the heading list is one short. Nothing on rize binds
  them. Failure mode is a Lane C card, never a crash.
* **CM8** — `test_runsrc_left_columns` **test_05 and test_06 were already RED**
  before this phase (baseline run on `p9clone`, 2 failed / 12). RUNSRC A1b
  started stripping `Sheet|` off a card's LABEL and neither assertion was
  updated. P1 rewrote 05 (as the handover directs) and corrected 06 to assert
  the card's `id` *and* its label. Lesson: "the suite is green" was never
  checked on this file — run the baseline before claiming a regression.
* **CM9** — Re-pointing a wire through the alias map is done for the **merge
  shape and the template file only**. On the interleaved shape a component
  bound to a bare column letter keeps a card of its own in the file lane
  (restored from the stored keys) — that is RUNSRC A test_02/test_12's pinned
  behaviour, and it is truthful: the file really does have a column `B`.
  Re-pointing there would have broken two green tests to say the same thing.
* **CM10** — `_column_alias_fold` must keep working for callers that pass a
  plain list; the alias map is a SIBLING (`_column_alias_map`), not a change to
  the fold's return type. Both share `_multisheet_fold` / `_flat_fold`.
* **CM11** — **RD60's default ladder used to leave the scheme.** Its last three
  rungs (`pay_data.filtered(has lines)`, `batches.filtered(has lines)`,
  `batches[:1]`) accepted ANY load on the database, so a scheme whose only file
  had been dropped on the board opened on another scheme's pay run. Harmless
  while the left list was a union; fatal once it obeys FROM. Every load on
  every live database carries a `formula_config_id` (checked 2026-09-19), so
  those rungs only ever mis-fired. New order: this scheme's pay-data load →
  this scheme's any load → this scheme's template file → the no-file state.
  Caught by `test_excel_onramp` 03/04/04b, not by anything in the handover.
* **CM12** — **The board keeps FROM while you change TO.** Switching the scheme
  from Rize India to Rize Vietnam left FROM reading "Rize India Payroll ·
  August 2026 — pay data · 75 fields" with the India columns under it — W76.3's
  bug class, on the board this phase exists to fix. Two guards, both needed: the
  client clears `state.batchId` when the scheme changes, and the server ignores
  a `batch_id` whose `formula_config_id` is not the scheme being read. Found in
  Chrome, never by a test.
* **CM13** — **The Journey's "source no longer exists" chip must not be asked
  of `hr.formula.rule.binding_dangling`.** That field's per-source compute
  calls `get_available_source_fields` — the catalogue discovery P2's payload
  had just finished promising it never runs — and it is charged once per
  connector, every read. Measured on abm before the fix: `journey_data` cost
  **492 queries and 470 of them were that one compute**. P2 derives the same
  fact from the links it already has (an `excel` key the stored file does not
  contain; a `rule` key with no transformation rule left on that connection; a
  system key with no connection to draw it from), and abm's read fell to **28
  queries**. Consequence to know: a feed key the catalogue would call missing
  but a live wire still carries is no longer counted as dangling — abm's
  "needs attention" went 2 → 1. The Journey's claim is now "nothing on this
  board can draw it", which is the claim the picture can actually defend.
* **CM14** — **`counts['wired']` and `header['fed']` are different questions
  and are SUPPOSED to differ.** `_journey_scheme_lane`'s `wired` asks "is the
  top-ranked declared kind excel/feed/rule"; `fed` asks "does at least one
  link exist that a run would read". On rize they are 41 and 42: the component
  that takes its value from the pay run is fed and was never wired. Both stay
  in the payload; never average them, and never assert one against the other.
* **CM15** — **A card whose header is a `<button>` cannot carry a chip that is
  also a button.** The v1 board's own comment said this about `actions[]` and
  P2 hit it again with the scheme card's warning chips: nested buttons are
  invalid markup and the inner one stops being reachable. Chips moved to a
  sibling row inside `.jny-card`, which also reads better — the warning sits
  under the sentence it is about.
* **CM16** — **`align-items: start` on a lane grid takes the sticky lane
  headers down with the shortest lane.** Scrolling a long Scheme card left the
  Payobook Source column with no heading and its dashed divider stopping in
  mid-air. Lanes stretch to the tallest; the headers then all stay put.
* **CM17** — **The wire gutter has a hard floor, and it is arithmetic, not
  taste.** An arrowhead is `HEAD = 11px`, so a two-way link needs two of them
  plus air: at `--jny-gut: 14` (28px between cards) the heads of an open
  Scheme ↔ Payobook Source pair collide, and forty lines gathering onto one
  closed card read as a single vertical stripe. 24 (48px of run) draws both
  heads and turns the gathering into a fan.
* **CM18** — **`_consumed_field_names()` reads `value_steps`,
  `filter_conditions` and `excel_formula` — NEVER `aggregate_field`.** A
  transformation-rule fixture built as `rule_type='sum'` with only an
  `aggregate_field` reads nothing at all, which is a valid rule and a useless
  fixture: two P2 tests about what a rule reads failed against correct code
  until the fixture grew a DERIVE step.
* **CM19** — **The stored sample's `letter` is the workbook's real column
  letter, not a position.** rize's 174 stored spellings carry 43 with
  `preferred: true` (the `Sheet|heading` cards) whose letters are AP, AD, FG,
  V… — the columns as the workbook lays them out. That is what the Journey's
  row gutter shows, and it is why the file card can be sorted by the SCHEME's
  order without losing the file's own.
* **CM20** — **MJ13, third time: `resize_page` reported success and left
  `innerWidth` at 500 when 390 was asked for.** `emulate` with a viewport
  string (`390x844x2,mobile,touch`) got it. Always assert the width you asked
  for before believing a responsive check.
* **CM21** — **On a tenant, the "Payobook Source" lane renders as "Rize
  Source" / "Nguồn Rize".** That is `biz_debrand` doing its job on a
  user-visible string, not a translation gap. A literal-string test must
  therefore assert the SOURCE strings, never what a tenant's screen shows.
