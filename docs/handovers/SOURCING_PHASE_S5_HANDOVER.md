# SOURCING Phase S5 — lineage in place, sealed components, the cockpit closes the loop

**The last phase.** Seven items, all from the approved brief, plus the owner's S15 ruling.

Design: `SOURCING_DESIGN.md` §8 (lineage), §9.5 (sealed, boards), §9.6 (cockpit, health).
Ledger: S1–S17 bind, plus CR1–CR33 and MF1–MF41. Vocabulary: S4's eight labels, **verbatim**.

## Owner ruling folded in (S15)

**Reserve header space; never truncate the code.** MAPFIX Phase A existed to make codes readable at
≤12 characters, and hiding them again in CSS would undo that programme. If the what-if button and the
code cannot both fit, **the button yields.** So: reserve right padding on `.g2-hrow th` for the button
and let the code use the full remaining width — no `max-width`, no ellipsis on `.g2-code`. Target:
the pre-existing 3 (1440) / 2 (1024) overlaps go to **0**.

## Verified plumbing — do not re-derive

| Fact | Evidence |
|---|---|
| The sync merge that loses computed provenance | `integration_field_mapping.py:590-597` (live layer forces `provenance='live'`), `:620-632` (`merged.update(live)` then return) |
| `expected_missing` set on catalogue rows | `:627-629` |
| ONE popover, `ui.menu.kind`, already carrying two payloads | `mapping_canvas.js:1129-1160`; template `mapping_canvas.xml:421-445` (`kind === 'values'` vs actions) |
| `itemMatches` searches `label`, `sublabel`, `sample`, `meta.col`, `group` — **not** tooltips | `mapping_geometry.js:139-149` |
| **`isWirable` already exists** (MAPFIX built it) and is honoured in `clickLeft` | `mapping_canvas.js:990-992`, `:1246-1256` |
| **…but NOT in `clickRight`** — the gap this phase must close | `:1258-1263` |
| Enter delegates to `clickLeft`/`clickRight` after resolving strictly | `:1511-1520` (MAPFIX D1) |
| `meta.badge` / `badgeTone` / `badgeHint` already render | `:986-989` |
| Sealed-card wording precedent | `pb_formula_studio.py:_ec_left_actions` — *"produced, not imported"* |
| Cockpit entry points | `pb_integrations.py:111` `get_board`, `:408` `_detail_mapping`, `:551` `_ledger_rule`, `:608` `_detail_rule` |
| `plain_summary` exists, stored | `api_transformation_rule.py:463-464` |
| `consumed_field_paths` uncapped + stored (S2) | `api_transformation_rule.py` |

**S11 is the live test case**: payobook has 14 transformation rules feeding **nothing**, 4 with
underscored keys (`NUM_TAX_DEPENDENTS`, `TOTAL_LEAVE_DAYS`, `TENURE_YEARS`, `NET_SALARY`) that
silently read 0. **If the "consumed by nobody" hint does not surface all 14, the hint is wrong.**

## Architecture

### 1. "Derived here" lane, and the end of a false amber chip

A **post-pass over `merged`**, after `merged.update(live)` — not a reordering of the layers. A
post-pass wins regardless of which layer produced the row, which is the property reordering would not
have, and it is what makes the chip survive a sync:

```python
computed_keys = {r.output_key for r in active rules on this connector if r.output_key}
for path, item in merged.items():
    if path in computed_keys:
        item['provenance'] = 'computed'
        item['group'] = 'Derived here'
        item['expected_missing'] = False    # a computed key is never "not sent"
```

`expected_missing=False` is the point: the amber *"not sent — this feed did not carry this field"* is
**a false statement about the owner's data** for a key the feed was never supposed to carry.

### 2. Lineage in place — a third `kind` on the shared popover

`kind: "lineage"` through the existing `_openMenu`. **Not a fourth popover** — MAPFIX E1 put the
second payload through this same state, scrim, anchoring and measure-then-place, and a second
implementation is a second set of placement bugs. MF27's double-`requestAnimationFrame` applies: the
lineage body is taller than an action list and cannot be placed from an estimate.

Body: `plain_summary` · **Reads** (`consumed_field_paths`, uncapped per S2) · **If nothing matches**
(the rule's default) · **Feeds** (consuming components — S2 gave every abm rule output exactly one) ·
*Open rule*.

**The rule name goes in `label`/`sublabel`.** `itemMatches` searches those; a board with 236 cards is
navigated by search, and tooltip-only text is unsearchable.

### 3. Calculated components shown but sealed

Both boards stop filtering to `column_type == 'input'` and include `formula`/`constant` with
`meta.wirable: false`, `meta.badge: "Calculated"`, `badgeHint: "Calculated — needs no source."` and
the S4 `srcKind` so the chip agrees with the badge.

**Three enforcement points, because refusing to offer is not a gate:**
1. `clickRight` gains the `isWirable` check `clickLeft` already has — **this is the actual gap**; a
   non-wirable RIGHT card currently accepts a wire.
2. The Enter path is covered by (1) because Enter delegates to `clickRight` (`:1511-1520`).
3. **The server re-checks on create** (MAPFIX F3's precedent): the mapping-create RPCs refuse a target
   whose `column_type != 'input'`. A client that has been tampered with, or an older bundle, must not
   be able to write a wire the board would not draw.

### 4. Inline rule creation

An unbound input's card menu offers **"Create a rule for this"**, launching the composer with
`output_key` pre-filled from the component's code. It must respect the S2 `output_key` constraint
(underscore-free, `^[A-Z][A-Z0-9]*$`) — so the pre-fill is sanitised through the same rule rather than
handing the composer a key its own constraint will reject.

### 5. Cockpit reverse links

`_detail_rule` → **"Feeds these components"**; `_detail_mapping` → **"Produced by"** when its
`source_field` is a rule `output_key`, plus the severed row and repair affordance; `_ledger_rule` →
a consumers count column, so a rule feeding nothing is visible in the list without opening it.

### 6. Health hints

Four, on `get_board` as a new `hints` key (the cockpit has no health surface today):
rule output consumed by nobody · severed mapping · input with no source at all · bound source that
produced nothing last run (`actual.via ∈ {fallback, binding_empty}`).

### 7. S15 — the grid header

`.g2-hrow th { padding-right: <button + gap>; }` and **no width cap on `.g2-code`**. Per the ruling:
the button yields, the code never truncates.

## Numbered test cases

1. Computed keys carry `provenance='computed'`, `group='Derived here'` **after** a simulated sync.
2. `expected_missing` is never True on a computed key.
3. Lineage popover renders Reads / If nothing matches / Feeds / Open rule for `OTHRS150` on abm.
4. Rule name is searchable via `itemMatches` (in `label`/`sublabel`, not a tooltip).
5. Calculated components appear on both boards with the badge.
6. `clickRight` refuses a non-wirable card; **Enter refuses it too**; the server refuses a
   non-input target even when called directly.
7. "Create a rule for this" pre-fills a converter-legal key.
8. Cockpit: rule detail lists consumers; mapping detail names its producer; ledger shows the count.
9. **Health hint surfaces all 14 payobook orphan rules** (S11).
10. Grid header: **0 overlaps at 1440 and 1024**, and no code is truncated.
11. New chips/lane/badges add **0 overlaps** at both widths.
12. Zero unintended writes (DB checksum before/after).
13. Three batteries green; JS/XML/SCSS parse.

## Deploy + validation

Ritual as always — **plus the S17 reload check**: this phase touches models AND JS, so after `-u`
across all four, `sudo service odoo-server restart`, and if a shell and the browser disagree about a
method, that is the signature. MF12's companion when assets look stale:
`delete from ir_attachment where url like '/web/assets/%'` then restart. Chrome MCP on **abm**
(CR13/S7). The database is the oracle (MF37).

## Closing act

After S5 lands, write `docs/handovers/SOURCING_CLOSEOUT.md`: what shipped S1–S5, the gate each passed,
**live vs latent**, the full S-gotcha list, open owner decisions, and what becomes visible on the
first real feed-backed run. That is what the owner reads instead of five phase reports.
