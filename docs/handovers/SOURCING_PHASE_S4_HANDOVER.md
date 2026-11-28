# SOURCING Phase S4 — every screen says where a value comes from

**Scope:** render source on all five studio surfaces and both mapping boards, from one serializer and
one vocabulary. **Zero writes.** This phase shows what S1–S3 recorded; it does not decide anything.

Design: `SOURCING_DESIGN.md` §2 (vocabulary), §9 (surfaces). Ledger: S1–S13 bind, plus CR1–CR33 and
MF1–MF41.

**Raised stakes (S12):** `data_source_field` has never held a value on any live database, so for most
components these chips are the first time anyone will see where a value comes from. A wrong word here
is not a cosmetic bug — it is the first answer the product has ever given to the owner's question.

## Binding non-goals

- **No writes.** No binding is created, re-pointed or cleared. Proven by DB diff (MF37).
- **No lineage popover, no "Derived here" lane, no sealed-calculated cards, no cockpit** — S5.
- **`data_source` is never read.** It stays demoted; `declared` is derived from real bindings and
  from the component's own nature.

## The vocabulary — final, and identical everywhere

Eight kinds. The **token** crosses the RPC; the **label** is the only string a user sees. **The icon
is the primary differentiator and the colour is secondary**, so the chips are legible to a
colour-blind reader: grid, cloud, sigma, briefcase, person, equals, padlock and dashed-circle are
distinct in shape at 12px.

| token | label | icon (Lucide-style, inline SVG) | palette |
|---|---|---|---|
| `excel` | **Spreadsheet** | grid / sheet | `--green-soft` / `--green` |
| `feed` | **Connected system** | cloud | `--cyan-soft` / `--cyan` |
| `rule` | **Rule output** | sigma | `--i-soft` / `--i600` |
| `contract_component` | **Contract component** | briefcase | `--amber-soft` / `--amber` |
| `employee_field` | **Employee record** | person | `#E8EEF7` / `#3B5B8C` |
| `calculated` | **Calculated** | equals | `--i-soft2` / `--i-deep` |
| `constant` | **Fixed value** | padlock | `#EEF1F5` / `#64748B` |
| `none` | **No source** | dashed circle | `#F1F3F7` / `#94A3B8` |

Supporting strings, fixed here so no surface paraphrases them:

- Declared vs actual heading: **"Where this value comes from"**
- Declared row: **"Set to read"** · Actual row: **"Last run used"**
- Disagreement: **"Last run used a different source"**
- Fallback: **"Fell back to <label>"** — *"Nothing arrived under “<key>”, so this used <label> “<key>” instead."*
- Ignored: **"Also arrived from <label> — not used"**
- Unbound: **"No source chosen"** · Never run: **"This scheme has not been run yet"**
- Board chip on a component already fed: **"Already fed by <label>"**

**No "Odoo" anywhere.** No gradients. No emoji. Lucide/SVG icons only.

## Architecture

### 1. One serializer, one nested object

`get_studio_data`'s component serializer (`pb_formula_studio.py:298-335`) gains **one** key —
`source` — not five siblings, so every render site reads one path and an older client degrades to
"no source block" rather than half a truth (the `column_role` precedent at `:326-331`).

```jsonc
"source": {
  "declared": {"kind": "excel", "key": "Base Pay", "wirable": true},
  "actual":   {"kind": "excel", "key": "Base Pay", "via": "binding",
               "fell_back": false, "ignored": {...}, "run": "March 2026", "run_id": 12}
}
```

**`declared`** is derived in this order, and `data_source` is not consulted:
`column_type=='formula'` → `calculated` · `'constant'` → `constant` · `source_binding` set → that kind
and key · `is_contract_component` → `contract_component` · has an `hr.payslip.import.mapping`
destination → `employee_field` · else `none`.

**`actual`** comes from **one** payslip per call — the most recent `calculation_method='formula'`
payslip of this config carrying a `formula_input_sources` blob — parsed once and indexed by code. One
extra read, not one per component. Absent blob → `actual` omitted and the UI says *"This scheme has
not been run yet"*, which is a different statement from "no source" and must not be collapsed into it.

### 2. Surfaces, each cloning its precedent

| Surface | Precedent | Change |
|---|---|---|
| Components rail | role chip `studio.xml:972-974`, `.ol-role` `studio.scss:141-147` | `ol-src s-{kind}` sibling, same 18×18 / 12px geometry |
| Card hero subtitle | `studio.xml:1038` | append `· from <label> “<key>”` |
| Cell Editor | advanced block `studio.xml:1354-1372` | **new section above Advanced**, open by default; the old Data-source block stays inside Advanced relabelled *"Manual classification (does not affect import)"* |
| Grid header | `grid_studio.xml:58-77` | `g2-src s-{kind}` glyph after `g2-code`, tooltip carries the sentence |
| Both boards' right column | `:4399-4401` api, `:4897-4898` import | add `prov` / `provKind` / `note`, the **same keys the API board's left column already uses**, so the canvas renders chips with almost no client change |

A `SrcIco` template + `SOURCES` const + `srcIcon`/`srcLabel`/`srcOf` helpers, cloning `RoleIco` /
`ROLES` / `roleIcon` exactly (`studio.xml:4358-4365`, `formula_studio.js:58-65`). Labels resolve per
render via `_t()`, never at module scope — the existing comment at `formula_studio.js:55-57` says why.

### 3. Width — measured, not eyeballed

MF13 / CR22 / MF26: an affordance that reserves width wrecks these cards, and only a screenshot or a
bounding-box measurement can see it. **0 overlaps across every card at 1440 and 1024**, measured with
`getBoundingClientRect` over the rail rows, the grid header cells and both boards' right columns.
The rail chip is icon-only (no text) precisely so it costs 18px and not a word.

### 4. Payload

The rail carries hundreds of rows. Measure `get_studio_data` payload size and wall time before and
after; Phase E's baseline was 132 ms / 69 KB. Report the delta. `actual` is a single indexed dict, so
the added cost is one small object per component, not a query per component.

## Numbered test cases

1. Serializer emits `source.declared` for every component; `kind` always one of the eight.
2. `declared` never consults `data_source` — a rule with `data_source='integration'` and no binding
   still reports its derived kind.
3. `actual` present when the config has a run, omitted when it has none.
4. Declared/actual disagreement is reported, not smoothed.
5. Rail chip renders for every row; icon differs per kind.
6. Card subtitle names the source and the key.
7. Cell Editor shows both rows; the old block is relabelled inside Advanced.
8. Grid header glyph present with tooltip.
9. Both boards' right column carries a chip.
10. **0 bounding-box overlaps at 1440 and 1024.**
11. Payload delta measured and reported.
12. **Zero writes** — full DB checksum before/after a Chrome MCP session.
13. No "Odoo" in any rendered string.
14. Three batteries green; JS/XML/SCSS parse.

## Deploy + validation

**MF12 matters again** — this is the first phase in four with JS/XML/SCSS, so the asset bundle
rebuilds on the module UPGRADE, not on file mtime. Bump `pb_formula_studio` and `-u` it; a late asset
edit after the `-u` serves a stale bundle indefinitely.

Ritual: rsync → `chmod -R a+rX` (CR6) → park tabs on `about:blank` (CR20) → stop → zero pids by PID →
`sudo -u odoo` (MF35) over all four → log not sentinel (MF9) → start → psql `latest_version` ×4
(MF17). Chrome MCP validation on **payobook** (S7 — abm has no payroll data). CR33: drive the browser
session, not RPC credentials.

## Report back

Final vocabulary; per-surface screenshots; overlap measurement at both widths; payload delta;
before/after DB diff proving zero writes; tests 1–14; manifest versions; commit hash; deviations;
new S-gotchas.
