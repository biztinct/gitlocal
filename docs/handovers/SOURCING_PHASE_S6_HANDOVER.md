# SOURCING — S6: one pill, an Excel source you can actually choose, and lineage where it belongs

**Follow-up phase. Three owner-reported defects against the live S1–S5 result.** Read
`SOURCING_CLOSEOUT.md` first; `SOURCING_LEDGER.md` (S1–S20) and `SOURCING_DESIGN.md` still bind, as do
`MAPFIX_LEDGER.md` (MF1–MF41) and `COLROLES_LEDGER.md` (CR1–CR33).

Versions at phase start: **pb_formula_studio 19.0.1.128.0 · pb_hr_payroll_formula 19.0.1.78.0 ·
pb_integrations 19.0.1.12.0**. Commits S1 `6724892c` · S2 `d074ce9f` · S3 `c960d022` · S4 `59835a8f` ·
S5 `3e273842`, none pushed.

---

## 0. The owner's report, and what was actually true

> *"Both in Mapping studio and mapping canvas … some of the calculated fields have two pills saying
> calculated. … I do not see any place where I can map fields with Excel as a source. And, also, where
> is the transformation indication for the fields?"*

He was on **abm**, config 14 **"AB Mauri Payroll"** (54 input · 36 formula · 9 constant = 99 rules),
connector **"Zoho People"**, 18 mapped.

### The board he was looking at, established from the database (do not re-derive)

```
abm  hr_integration_connector : 1 "Zoho People"        18 mappings, 18 wired, 0 transformation rules
                                3 "Zoho People (ABM)"  41 mappings, 15 wired, 8 transformation rules
     hr_formula_config        : 14 "AB Mauri Payroll", connector_id = NULL, draft
     hr_formula_rule          : 54 input / 36 formula / 9 constant, source_binding 0, data_source_field 0
     hr_payroll_import_batch  : 0
```

Three consequences, each of which is one of the three defects:

1. **45 cards are sealed** (36 formula + 9 constant) and every one of them renders **two pills**.
2. **The Import-columns board is `{'ok': False, 'reason': 'no_batch'}`** — abm has zero batches, so the
   only Excel surface in the product refuses to draw itself.
3. **The board landed on connector 1**, which has no transformation rules, so there is no "Derived
   here" lane and no lineage affordance to be seen — while **eight of config 14's own components are
   fed by rule outputs on connector 3** and say nothing about it.

---

## D1 — two pills saying "CALCULATED"

### Cause (ours, in one place)

`_mc_right_item` (`pb_formula_studio/models/pb_formula_studio.py:466-495`) puts **both** on the same
card for `column_type != 'input'`:

```python
'srcKind': declared['kind'],          # 'calculated'  -> srcChip label "Calculated"
...
'badge': _("Calculated"),             # 'calc' tone   -> badge  label "Calculated"
```

`.mc-src.s-calculated` is `#DDD6F2` and `.mc-badge.calc` is `#DDD6F2` — the indigo pair the owner
photographed.

### And the defect nobody reported, found by checking every other card kind

The `badge` is written under `if not wirable:`, which covers `formula` **and** `constant`. So abm's
**nine constant columns** carry `Fixed value` + `Calculated` — not a duplicate, a **contradiction**. A
fix that only de-duplicates would have left nine cards telling two different stories.

Full sweep of every card kind that can carry a source chip and a role/type chip:

| Card kind | Chips today | Verdict |
|---|---|---|
| `formula` (right col, both boards) | `Calculated` + `Calculated` | **duplicate** |
| `constant` (right col, both boards) | `Fixed value` + `Calculated` | **contradiction** |
| `contract_component` (right col) | `Contract component` | single, correct |
| `employee_field` (right col) | `Employee record` | single, correct |
| `none` (right col) | — (`srcChip` returns null for `none`) | correct |
| `excel`/`feed`/`rule` bound (right col) | one chip | correct |
| Employee-board LEFT card, contract component | `Contract component` badge only (`_mc_item` sets no `srcKind`) | single |
| Employee-board LEFT card, text component | `Text component` badge only | single |
| API-board LEFT card | one `provChip` (`expected`/`computed`/`not sent`/`Payobook field`/`mapped elsewhere`) | single |

### The ruling: one pill, and the pill says what the card *is*

For a produced column, *"it is calculated"* and *"it needs no source"* are one fact. The **badge**
keeps it, because the badge is the one that can carry the explanation (`badgeHint`) and the one the
sealed styling already keys off. The **source chip is dropped** for non-wirable cards — the server
stops sending `srcKind` for them — and the badge's label becomes that card's own vocabulary label
(`_SOURCE_LABELS[kind]`: **Calculated** for a formula, **Fixed value** for a constant), so the nine
constants stop being called something they are not.

### And a rail so it cannot come back

Server-side correctness is not enough — this is the third time a chip has gone wrong on these two
columns (S16, S18). Two structural changes:

- **`itemChips(it)` on the canvas** assembles `[provChip, srcChip, badge]` and **drops any chip whose
  label duplicates an earlier one** (trimmed, case-folded). One card, one pill per distinct fact, on
  every board, including boards not yet written.
- **A shared label sub-template** `pb_formula_studio.McItemLabel`, rendered by **both** columns.
  `mapping_canvas.xml` has had two item blocks (`:92` left, `:193` right) that do not share a label,
  which is S16 and S18 and, per the closeout's open item 5, was going to be a third. It now shares one.
  This is the durable fix and it is in scope precisely because D1 is that bug happening again.

---

## D2 — nowhere to map from Excel

### What is true today (verified; do not re-derive)

- `import_mapping_data` (`:5182`) returns **`{'ok': False, 'reason': 'no_batch'}`** whenever the
  database has no import batch. abm has none. The board is a dead end from the first click.
- Its left column is `_import_batch_columns(batch)` — *the keys of the first line of one batch*. "Keys
  of the last load", exactly as the design called it.
- `import_mapping_create` (`:5246`) writes **`rule.write({'data_source_field': col})`** and nothing
  else. **S12**: that Char is empty on every rule on all four databases. The tab has never written a
  value in its life.
- S3 built the real binding — `source_binding` + `source_binding_key` on `hr.formula.rule`
  (`pb_hr_payroll_formula/models/formula_rule.py:179-271`), written only through
  `set_source_binding(kind, key, origin)` so the stamp cannot be forgotten — and the resolver honours
  it with binding-wins / fallback+`fell_back` / `ignored`
  (`payroll_import_batch.py:3059-3160`). **Nothing in the UI writes one.** That is the entire gap.

### What S6 builds

**1. The Excel board draws itself with no batch.** `import_mapping_data` never returns `no_batch`
again. Its left column is the union of three honest sources, each in its own lane:

| Lane | Contents |
|---|---|
| *`<batch name>`* | the columns of the selected batch, or of this scheme's most recent batch when none was picked (today's behaviour, kept) |
| **Already used by this scheme** | every `source_binding_key` of this config's `excel`-bound components — so the wires you drew last month are visible on a database with no file loaded |
| **From this scheme's history** | non-empty legacy `data_source_field` values (empty everywhere today — S12 — and free to carry) |

**2. Bind by typing, when there is no file to point at.** The left search box doubles as the creator:
type a header or a column letter that matches nothing, and the column offers
**"Use “<what you typed>” as a spreadsheet column"**. It is a new optional canvas prop
(`onAddLeft`) rendered only for adapters that pass it, so every other board is unchanged, and there is
**no new chrome at rest** — the affordance appears at the moment it is the only useful thing on screen.
A board that stays empty until somebody happens to have loaded a file is why this was never used.

**3. Both create paths write a real binding.**

```python
# import_mapping_create  — the Excel side
rule.set_source_binding('excel', col, origin='board')

# api_mapping_create     — the feed side, which must be symmetric
kind = 'rule' if src in self.env['hr.integration.field.mapping']._computed_output_keys(conn) else 'feed'
rule.set_source_binding(kind, src, origin='board')
```

`import_mapping_create` **stops writing `data_source_field`.** Writing both would be two statements of
one fact that can drift apart, and the binding is the authoritative one (Step 1 runs in front of the
ladder `data_source_field` lives in). The Char is untouched where it already has a value; the delete
path clears whichever of the two produced the wire, so removing a wire removes the wire.

**4. Switching sides is one act, and it says what it replaced.** `set_source_binding` overwrites, so
drawing on the Excel board a component that was bound to a feed simply re-binds it. Both create RPCs
return `replaced: {kind, key}` when they displaced a different binding, and the host raises a
notification — *"BASESALARY now reads Spreadsheet “Basic Salary” instead of Connected system
“Salary”."* One click, one sentence, no re-import.

**5. Precedence is S3's, unchanged.** Nothing in this phase touches
`payroll_import_batch.py`. Binding wins; the other side is a marked `fell_back`; the displaced value is
recorded as `ignored`. The UI does not tell a second story.

### Write safety

The only writes S6 adds are `set_source_binding` calls on an explicit create/delete gesture. Proven by
a before/after `hr_formula_rule` binding checksum on all four databases (MF37 — the database is the
oracle; a `fetch` hook is blind).

---

## D3 — the transformation indication

### Diagnosis, stated explicitly because it decides the fix

**It is not conditional on synced data.** `_catalog_source_fields`
(`pb_hr_payroll_formula/models/integration_field_mapping.py:739-762`) has contributed every
transformation rule's `output_key` to the catalogue layer since Integrations Cycle 4, *before any
sync*, and S5's post-pass (`:667-672`) re-stamps them `provenance='computed'` + `group="Derived here"`
after `merged.update(live)`. Both paths are correct and both are live.

**It is S20 again.** Config 14 has `connector_id = NULL` — no config on any of the four databases has
one. `_api_active_connector` (`pb_formula_studio.py:4574-4593`) therefore tie-breaks on *"the connector
with the most mappings already targeting this config's inputs"*: connector 1 has **18**, connector 3
has **15**. The board lands on connector **1 "Zoho People"**, which owns **zero** transformation rules.
There is correctly nothing to derive on that board — and nothing on it said so. S5 validated lineage by
naming connector 3 in the test, exactly as S20 says to.

**And the gap that made it invisible anyway.** Eight of config 14's components are fed by rule outputs
through connector 3:

```
OTHRS150 → OT15HOURS    OTHRS270 → OTNIGHTSHIFA    DEPCOUNT  → NOOFDEPENDEN
OTHRS200 → OT2HOURS     OTHRS300 → OT3HOURS        WORKEDHRS → ACTUWORKHOUR
OTHRS210 → OTNIGHTSHIFT OTHRS390 → OTNGIHTSHIFT
```

Every one of them renders **"No source chosen"**, on every surface, because `_declared_source`
(`:339-359`) consults the S3 binding and the component's nature and **nothing else** — a live field
mapping, which is the most explicit statement of source these databases actually contain, is not read.
And the lineage affordance exists only in the canvas's **left** item block, so a component could not
carry one even if it had lineage (S18's shape, for the third time).

### The rule S6 implements

> A rule output is identifiable as a rule output wherever it can appear, including on a not-yet-synced
> board and on a board pointed at a different connector. If a rule produces a key, that fact does not
> depend on the vendor having been called.

**Fix A — a live mapping is a declared source.** `_declared_source` gains one tier, between the binding
and the component's nature:

```
binding                                   (explicit, S3)          -> excel | feed | rule
live hr.integration.field.mapping         (explicit, pre-S3)      -> rule  when source_field is an
                                                                     output_key of that mapping's
                                                                     connector's rules, else feed
is_contract_component / employee dest / … (the component's nature) -> unchanged
```

Computed **once per config in one search** (`_source_mapping_dests(config)` → `{rule_id: {...}}`),
never per component — the S4 precedent (one payslip read, not one per component). Where a component is
wired on two connectors (seven of abm's are), **a `rule` mapping beats a `feed` mapping** and ties break
on the lowest mapping id, so the answer is deterministic and the more specific fact wins.

This is **display only**. It changes no resolution, writes nothing, and is honest: `declared` has always
meant *"what configuration says"*, and `actual` (S4) still reports what the last run did — including
"This scheme has not been run yet".

**Fix B — lineage on the component, not only on the vendor field.** `_lineage_for_config` unions the
lineage of every connector that matters to this config (the board's connector ∪ the connectors of the
mappings that target its components ∪ the connector named by a `('rule', key)` binding), and every
right-column card whose declared kind is `rule` carries it. The lineage button moves into the shared
`McItemLabel` sub-template, so it renders in **both** columns — which is what D1's structural fix buys.

**Fix C — `onLineage` is actually passed.** Neither host passes it
(`studio.xml:2162-2178`, `mapping_studio.xml:208-220`), so the popover's **"Open rule"** button has
never rendered. Both hosts now pass it, and both now pass `onRightBlocked` so a sealed card refuses out
loud on the boards as well as on the server.

### Not in scope, reported instead

`_mc_right_item` writes `meta.createRule` (`:477-484`) — S5's "Create a rule for this" — and **nothing
in any template or component reads it.** The right column has no action menu at all. It is dead payload,
not a regression, and giving the right column a menu is a bigger change than this phase should carry.
Recorded as an owner item.

---

## The hand-holding — `docs/handovers/SOURCING_WALKTHROUGH.md`

Written for the owner, on **abm**, with real data and a screenshot at every step. No model names, no
file paths, no "Odoo". Contents: the click path from home to a transformation's lineage; what Reads /
If nothing matches / Feeds / Open rule each mean; mapping a component from a feed; mapping one from a
spreadsheet; switching it; and all eight source chips in plain words.

---

## Test cases

1. **T1** — every one of abm's 45 sealed cards renders exactly **one** pill; the 36 formula cards say
   *Calculated*, the 9 constant cards say *Fixed value*. Counted in the live DOM, both boards.
2. **T2** — no card anywhere on either board renders two pills with the same text. Asserted over every
   card of all five adapters.
3. **T3** — bounding-box overlaps from our own glyphs: **0** at 1440 and **0** at 1024, both boards.
4. **T4** — the Import-columns board renders on abm (0 batches) with a left column and a usable empty
   state, instead of *"No file has been uploaded yet."*
5. **T5** — typing a header that matches nothing offers *Use “…” as a spreadsheet column*; the card
   appears; a wire can be drawn to a component.
6. **T6** — that wire writes `source_binding='excel'` + `source_binding_key` + `origin='board'` and
   **does not** write `data_source_field`. Verified in psql.
7. **T7** — the component's card, rail chip and Cell Editor then all say **Spreadsheet “…”**.
8. **T8** — re-binding the same component on the API board flips it to `feed`/`rule`, returns
   `replaced`, and the notification names both sides. Removing the wire clears the binding.
9. **T9** — on the owner's own board (config 14, connector 1) the eight rule-fed components carry a
   **Rule output** chip naming the output key, and a lineage button.
10. **T10** — that lineage popover shows summary / Reads / If nothing matches / Feeds / **Open rule**.
11. **T11** — the seven components wired on both connectors resolve deterministically to the `rule`
    mapping.
12. **T12** — a sealed card refuses a wire on the board (notification) and on the server (RPC), mouse
    and Enter (MF33).
13. **T13** — DB before/after: `hr_formula_rule` binding checksum unchanged on all four databases apart
    from the bindings deliberately created and then removed by T6/T8.
14. **T14** — neutrality: payobook `input_values` md5 still `b1dcd785739e1c0f49d304ee5428229a`.
15. **T15** — three batteries green (provenance, `excel_semantics_battery`, `import_resolution_battery`).

## Standing rails

JS `.mjs` + `node --check`, XML parse, `npx sass`, `py_compile` before deploy. Deploy per the ledger
ritual to **abm acme payobook payobook_template**, `sudo -u odoo` (MF35), `chmod -R a+rX` (CR6), psql
`latest_version` on all four (MF17), **and `service odoo-server restart` (S17)**. Chrome MCP on abm
(CR13), other tabs parked on `about:blank` (CR20). Locked palette, no gradients, no emoji, Lucide/SVG
only. S4's vocabulary verbatim; no surface paraphrases it. **No user-visible string contains "Odoo".**
One commit, explicit staging, no push.
