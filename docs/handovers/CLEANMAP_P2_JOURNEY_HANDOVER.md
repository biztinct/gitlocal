# CLEANMAP P2 — the Journey, redesigned: only what is mapped, cards that open

**Status: DESIGNED, NOT STARTED.** Read `CLEANMAP_LEDGER.md` first — including
"DO NOT START". Depends on P1 (uses its `_column_alias_map`). Anchors were true
at `cdefe5439`, `pb_formula_studio 19.0.1.196.0`; re-verify by symbol name.

## 1. The owner's brief (2026-09-19, their words condensed; rulings are final)

1. The **Journey pill goes to the very end** of the pill row.
2. The Journey shows **only the systems, feeds and files that actually go into
   this scheme**, plus any transformation in between. Zoho People is drawn today
   although nothing uses it — that must go. This holds collapsed AND expanded.
3. **No Pay Run column** at the end.
4. A new **rightmost column, "Payobook Source"**: values that come from the
   app's own records (employee, contract…), joined to the scheme with
   **two-way arrows**. The records card that sits bottom-left today goes away —
   it has moved here.
5. **No "Details" button** (the owner withdrew it). Instead **clicking a card
   opens it** into its mapped fields; clicking again closes it. Any mix of open
   and closed cards. This REPLACES today's click-navigates-away behaviour.
6. Getting to the editing tab is a **small "open" icon on the card's corner**.
7. Open **Scheme** card: the fields that need a source (mapped ones linked,
   unmapped ones clearly marked) + ONE folded line for calculated/fixed ones.
8. Lines: **thin and pale; hovering a field lights its whole path and fades the
   rest**. Open card ↔ closed card: **lines gather into the closed card**. Both
   closed: one line with a count.
9. A column with nothing mapped is **hidden entirely**.
10. **Small fonts** so an open board does not look messy.
11. Warning chips (fed twice, source gone…) stay, on the scheme card.

Design bar, verbatim and binding: "extreme WOW, intuitive, out-of-this-world,
best in class". No "Odoo" in any user-visible string.

## 2. What exists (verified — do not re-derive)

* Server: `pb.formula.studio.journey_data(config_id)`
  (`models/pb_formula_studio.py` ~7431). Builds lanes `systems, feeds,
  transforms, scheme, run` + `edges`. **It iterates `Conn.search([])`** — every
  connector on the database (CM4) — then every endpoint of those
  (`_api_endpoints`), every sheet of the stored file as a separate `s:` node,
  the file as a `file` node, a `records` node in the systems lane, every
  transformation rule of every connector, ghosts for every empty lane, health
  nodes as separate cards in the scheme lane, and `_journey_run_lane`.
* Per-component truth already exists and MUST be the only source of field-level
  links: `_declared_sources(rule, record_dests, wire_dests)` (~683) returns the
  ranked list `[{'kind','key','wirable'[, 'label']}]` with kinds `excel`,
  `feed`, `rule`, `employee_field`, `contract_field`, `bank_account`,
  `contract_component`, `period` (RUNSRC C1), `calculated`, `constant`, and the
  "nothing" description. Helpers computed once per config:
  `_source_record_dests` → `{rule_id: {kind,key,label}}`,
  `_source_wire_dests` → `{rule_id: {kind:'rule'|'feed', key, connector}}`,
  `_source_conflicts`.
* Wire census already in `journey_data`: `wires_by_conn`, `wires_by_ep` from
  `hr.integration.field.mapping` on `target_rule_id in input_ids`.
* Rule consumers: `_tf_consumers(rule)`; a rule's inputs:
  `rule._consumed_field_names()`.
* Primary-connector honesty (MJ22, S20): `primary = config.connector_id`;
  wires on a connection the scheme is not set to are NOT read on a system run.
  Keep that statement — as a chip, see 4.6.
* Client: `static/src/js/mapping/journey_board.js` (587 lines),
  `static/src/xml/journey_board.xml` (174), `static/src/scss/journey.scss`.
  Every node is ONE `<button>` whose click is `openDoor` → `props.onOpenDoor`.
  `_measure` walks `body.children` by `data-id` (direct children only).
  Geometry = `mapping_geometry.js` `wireGeometry(ax,ay,bx,by,bidi)` + `clampY`.
  Lane bodies scroll individually (`onLaneScroll`).
* Host: `mapping_studio.js` — `MODES` (~101) has `journey` FIRST; cold start is
  `mode: askedMode || "journey"` (~200); the SC-4 fallback is
  `(this.modes[0] || {}).id || "journey"` (~328) — **moving the pill changes
  what `modes[0]` is**; `openDoor(door)` (~894); `journeyWired` (~655) reads
  `header.wired`.
* Tests that pin today's shape: `tests/test_journey_view.py` (lines ~228, 231,
  397, 451 assert the five lanes incl. `run` and its ghost),
  `test_journey_guardrails.py`, `test_one_mapping_home.py` (may pin MODES order).

## 3. Scope and binding non-goals

In scope: `journey_data` payload v2, `journey_board.{js,xml}`, `journey.scss`,
the MODES order + two fallbacks in `mapping_studio.js`, tests, EN/VI strings.

Non-goals (binding):

* **Read-only stays read-only.** Opening a card is client state. `journey_data`
  and everything it calls write nothing; MF37 diff across the whole validation
  session must be empty.
* No change to the resolver, to `_declared_sources` ORDER or return shape, to
  any other tab, to `openDoor(door)` semantics in the host.
* Do not delete `_journey_aggregate` / `_journey_run_lane` /
  `_JOURNEY_VIA_BUCKETS` — fixture tests cover them and the owner may want the
  run summary elsewhere. Only stop CALLING the run lane from `journey_data`.
* No analytics, no percentages, no invented health score (J5 scope 5 stands).
* No Expand-all / Details button. The owner withdrew it.

## 4. Design

### 4.1 The picture

Collapsed, Rize today (Feeds and Transformations hidden because empty):

```
 FILES & SYSTEMS            SCHEME                         PAYOBOOK SOURCE
 ┌───────────────────┐ 41  ┌──────────────────────────┐ 7 ┌────────────────────┐
 │▸ Rize_…DATA.xlsx ↗│────▶│▸ Rize Vietnam Payroll   ↗│◀─▶│▸ Payobook Source  ↗│
 │  41 columns used  │     │  48 need a source        │   │  7 fields · 2 kinds│
 └───────────────────┘     │  ▓▓▓▓▓▓▓▓▓▓▓░  41 fed    │   └────────────────────┘
                           │  7 not fed yet           │     [Open Records Desk]
                           │  ⚠ 2 fed twice           │
                           └──────────────────────────┘
```

All three open:

```
 ┌▾ Rize_…DATA.xlsx ───↗┐   ┌▾ Rize Vietnam Payroll ─↗┐   ┌▾ Payobook Source ──↗┐
 │ A  Mã nhân viên      ○───▶○ Mã nhân viên (Code)   ○◀─▶○ EMPLOYEE             │
 │ B  Họ và tên         ○───▶○ Họ và tên             ○◀─▶○  Employee code       │
 │ F  Vị trí            ○───▶○ Vị trí (Position)     ○◀─▶○  Name                │
 │ …                    │   │ ● Phụ cấp xăng  not fed │   │ CONTRACT             │
 │                      │   │ …                       │◀─▶○  Job position        │
 │                      │   │ ▸ 32 calculated or fixed│   │ PAY RUN              │
 └──────────────────────┘   └─────────────────────────┘◀──○  Standard work days  │
                                                          └──────────────────────┘
```

Lanes, left to right — the ORDER IS THE STORY and is fixed:

| id | Header | Icon | Shown when |
|---|---|---|---|
| `systems` | Files & systems | `server` | ≥1 card |
| `feeds` | Feeds | `database` | ≥1 card |
| `transforms` | Transformations | `sigma` | ≥1 card |
| `scheme` | Scheme | `calculator` | always |
| `source` | Payobook Source | `users` | ≥1 row |

A hidden lane takes NO grid column (CSS grid built from the visible lanes), so
the board re-balances instead of leaving a hole.

### 4.2 What earns a card ("mapped-only", ruling 2)

Build the field-level LINKS first (4.3); cards are derived from links, never
from a census of what exists. That single inversion is the whole fix for CM4.

* **File card** (`file`): iff ≥1 link of kind `excel`. ONE card per stored file
  — the separate `s:<sheet>` nodes and the file→sheet `contain` edges are gone.
  Multi-sheet: rows grouped under small sheet sub-heads, only when >1 sheet has
  a mapped column.
* **System card** (`c:<id>`): iff that connector carries ≥1 `feed` or `rule`
  link into this scheme.
* **Feed card** (`e:<id>`): iff ≥1 of its fields is linked to the scheme, or is
  read by a transformation that is.
* **Transformations card** (`t:<connector_id>`): ONE card per system, iff ≥1 of
  its rules has a consumer on this scheme. (A card per rule would be twelve
  cards on abm; the rules are the ROWS.)
* **Scheme card**: always.
* **Payobook Source card** (`source`): iff ≥1 row. ONE card, as the owner named
  it, with sub-heads inside.

Nothing else is drawn: no unused connector, no `0 fields · never synced` feed,
no "No transformation rules yet" ghost, no pay-run lane, no records card in
lane 1.

**The zero state** (a scheme with no links at all): lanes collapse to the
Scheme card alone plus a designed invitation beside it — headline "Nothing
feeds this scheme yet", three doors as buttons: "Map a spreadsheet"
(`{mode:'import'}`), "Connect a system" (`{mode:'api'}`), "Use Payobook
records" (`{mode:'employee'}`). Doors filtered by the host's visible `modes`
(SC-4). This replaces five ghosts; zero dead-ends is part of the bar.

### 4.3 Payload v2 (`journey_data`)

Keep: `ok, can_edit, config, primary_id, primary_name, counts`. Add `'v': 2`.
Replace `lanes`/`edges`:

```python
'lanes': {'systems': [card…], 'feeds': [card…], 'transforms': [card…],
          'scheme': [card], 'source': [card]},      # empty list = hidden lane
'links': [{'id': 'k12', 'a': '<row id>', 'b': '<row id>',
           'kind': 'excel'|'feed'|'rule'|'reads'|'record'|'component'|'period',
           'dir': 'fwd'|'both'|'back', 'dimmed': bool}],
'contains': [{'from': 'c:3', 'to': 'e:11'}, {'from': 'c:3', 'to': 't:3'}],
```

Card: `{id, kind, lane, label, sub, tone, chip, chips[], door, actions[],
rows[], groups[], folded}`. Row: `{id, card, label, tag, sub, state, group}`.

* Row ids are strings and globally unique (W146): `f:<canonical key>`,
  `e:<ep id>:<source_field>`, `r:<rule rec id>`, `s:<formula rule id>`,
  `p:emp:<field>`, `p:con:<field>`, `p:bank:<role>`, `p:comp:<rule id>`,
  `p:run:<PERIODCODE>`.
* `tag` is the tiny left gutter text: the column letter for a file row, the
  output key for a transformation row, empty otherwise.
* `state`: `fed` | `unfed` | `gone` (source no longer exists / not in the file)
  | `twice` (in `_source_conflicts`) | `plain`.

**Building links — one pass over `config.rule_ids` inputs, asking
`_declared_sources` and NOTHING else** (so the Journey can never disagree with
the chips on the other boards):

| declared kind | link | dir |
|---|---|---|
| `excel` | `f:<canon(key)>` → `s:<rule>` | fwd |
| `feed` | `e:<ep>:<key>` → `s:<rule>` (endpoint from the field mapping's `endpoint_id`; no endpoint → a row on the system card itself, `c:<id>:<key>`) | fwd |
| `rule` | `r:<tf rule>` → `s:<rule>`, plus for each name in `_consumed_field_names()`: `e:<ep>:<name>` → `r:<tf rule>` kind `reads` | fwd |
| `employee_field` / `contract_field` | `s:<rule>` ↔ `p:emp|con:<key>` | **both** |
| `bank_account` | `s:<rule>` → `p:bank:<key>` | **fwd only** — J3 S1: bank rows are the import half, never read back. A two-way arrow here would be a lie. |
| `contract_component` | `p:comp:<rule>` → `s:<rule>` | back |
| `period` | `p:run:<CODE>` → `s:<rule>` | back |

`canon()` = P1's `_column_alias_map` over the stored sample's columns, so a
binding spelled `A` or `Mã nhân viên` lands on the ONE row for that column,
labelled with its heading. A key the sample does not contain → its own row,
`state: 'gone'`, label = the key as stored.

A component with several sources (J9) gets several links. `dimmed` = the link's
connector is not the scheme's primary (or there is no primary) — today's rule,
carried per link.

Verify while building: does `rule.declared_sources()` include the legacy
`data_source_field`? The Spreadsheet board draws a wire for it
(`import_mapping_data` ~8690). If `_declared_sources` does not, add the legacy
key as an `excel` link HERE with the same fallback expression, and ledger it.
Test 6 exists to catch either answer.

**Scheme card rows** = input rules in `sequence` order; `state` from the links
(`fed` if ≥1 non-dimmed link, else `unfed`). `folded`:
`{'n': calculated+constant, 'label': _("%s calculated or fixed")}` with its own
rows (label only, no links) — opened by its own small toggle inside the card.

**Row order everywhere except the scheme follows the scheme** (the WOW detail
that keeps 40 lines parallel instead of a web): sort each card's rows by the
lowest `sequence` of the scheme row they link to; ties by label. File column
letter stays visible in the `tag` gutter so the file's own order is not lost.

**Payobook Source groups**, fixed order, each only when non-empty:
Employee · Contract · Bank · Contract pay components · Pay run.

**Header** (replaces `header`): `{'inputs', 'fed', 'unfed', 'attention'}`.
Keep `header.wired` = `fed` for one release so `journeyWired` does not break;
then the host reads `fed`.

**Chips on the scheme card** (`chips[]`, replacing the separate health nodes;
same four conditions, same wording, same doors): no primary connection /
fed twice / source no longer exists / severed.

Performance: one `_declared_sources` pass (already done today for the counts),
one field-mapping search (already done), one rule search restricted to
connectors that HAVE links (cheaper than today's all-connectors loop), and
**no `get_available_source_fields` call at all** — the catalogue discovery that
today runs once per connector on the landing tab is deleted with the unused
feeds it counted.

### 4.4 The card component (client)

A card can no longer be one `<button>` (it now contains two actions and a
list). Markup:

```xml
<div class="jny-card" t-att-data-card="c.id" …>
  <div class="jny-card__h">
    <button class="jny-card__t" t-att-data-id="c.id" t-att-aria-expanded="isOpen(c)"
            t-on-click="() => this.toggle(c)">  chevron · icon · label · sub · bars · chips </button>
    <button class="jny-card__go" t-if="c.door" title="Open …" t-on-click="… openDoor(c)">
      ic('external', 13)</button>
  </div>
  <ul class="jny-rows" t-if="isOpen(c)"> <li class="jny-row" t-att-data-id="r.id" …/> </ul>
</div>
```

* MJ10 still honoured: both actions are real buttons; Enter/Space free.
* `toggle` flips membership of `ui.open` (a Set of card ids, kept as an object
  for OWL reactivity). Persist per scheme with `browser.localStorage` under
  `pb.journey.open.<configId>`, every read/write in try/catch; the board must
  render correctly with storage unavailable.
* Rows are `<li tabindex="0">`: hover/focus = trace (4.5); click = pin the
  trace; click again or Escape = unpin. Escape ladder: search → pin → focus.
* The `jny-card__go` tooltip reuses `doorHint` ("Opens the Spreadsheet tab,
  already on this."). "Open Records Desk" stays as today's `actions[]` button
  under the Payobook Source card (registry-probed).
* Motion: rows reveal with a 140 ms height+opacity ease, staggered 8 ms per
  row capped at 120 ms total; wires re-measure on `transitionend` AND every
  rAF during the transition so lines travel with the rows rather than snapping.
  `prefers-reduced-motion` → no transition.

### 4.5 Lines

Client derives drawn edges from `links` + `ui.open`:

```
end(row) = row.id  if its card is open and the row is rendered (not filtered)
         = row.card otherwise
group links by (end(a), end(b), dir, dimmed) → one drawn edge, count = n
```

* count > 1 → stroke width `1 + min(3, log2(n))`, and a count badge at the
  midpoint ONLY when both ends are cards (both closed).
* Open↔closed: each row's line converges on the closed card's edge midpoint —
  "lines gather". No badge (the rows are the count).
* `contains` edges (system→feed, system→transformations) drawn as today's
  quiet dotted connector, only between visible cards.
* `_measure` must change from `body.children` to
  `body.querySelectorAll('[data-id]')`, anchoring a card on its `__t` header
  and a row on itself. Left/right edges come from the CARD rect, so every row
  line leaves from the card's border, not from the row's text.
* Arrowheads: `dir='both'` → `wireGeometry(..., true)`; `dir='back'` → swap the
  ends so the head points INTO the scheme. Spanning a hidden lane is not a
  span: compute `span` over VISIBLE lane indexes.
* Default look: 1px, 35% opacity, palette line colour. **Trace**: hovering or
  focusing a row (or card) computes the connected set by walking `links` both
  ways transitively (file column → component → employee field is one path);
  those lines go 2px/100%, their rows get the `on` tint, everything else drops
  to 12%. One Set, recomputed on hover change only — no geometry recompute.
* Scrolling: lane bodies STOP scrolling individually. The board grows and the
  page scrolls; lane headers are `position: sticky`. This removes wire docking
  (`clampY`) from the common path and keeps a row and its partner on screen
  together. Keep `clampY` as the guard it is.

### 4.6 Type and density (ruling 10)

| Element | Size |
|---|---|
| Lane header | 10.5px caps, tracking .06em (as today) |
| Card title | 12.5px / 600 |
| Card sub, chips | 11px |
| Row label | 11.5px, single line, ellipsis, full text in `title` |
| Row tag gutter | 10px mono-ish, muted, fixed 22px wide |
| Row height | 22px; sub-head 18px caps 9.5px |

Unfed scheme rows: amber dot + "not fed" right-aligned in 10px — state is never
colour alone. `gone` rows: strike-through tag + amber. Dark mode through the
existing tokens only; no new colours, no gradients.

### 4.7 Header bar

`Rize Vietnam Payroll — 48 need a source · 41 fed · 7 not fed yet` (+ "· 2 need
attention" when >0). One msgid per shape, never assembled from fragments. The
word "fallback" and "wired" leave the Journey; "components" → "fields" is NOT
changed elsewhere (non-goal).

Search stays ("Filter the journey…"). It now matches rows too: a query
TEMPORARILY opens any card holding a match and shows only matching rows +
their linked partners (J4's match-through-neighbours rule, carried to rows).
Clearing restores the owner's own open set untouched.

### 4.8 Host changes (`mapping_studio.js`)

* Move the `journey` entry of `MODES` to the END (after Component treatment).
  Update its hint: "The whole picture: every file, system and record that
  feeds this scheme, and what each one changes on the way."
* Cold start stays the Journey (`askedMode || "journey"`) — moving the pill
  must NOT change where Settings/⌘K land.
* SC-4 fallback (~328): prefer `"journey"` when it is in `this.modes`, else
  `modes[0]`. Without this, a hidden-tab deep link now lands on System fields.
* FROM box on the Journey ("Every source · Systems, files and records") and
  the "41 wired" middle count: reword count to "41 fed" from `header.fed`.

### 4.9 Copy (EN → VI) — all new strings

Files & systems → Tệp & hệ thống · Payobook Source → Nguồn Payobook ·
"%s columns used" → "%s cột đang dùng" · "%s need a source" → "%s cần nguồn" ·
"%s fed" → "%s đã có nguồn" · "%s not fed yet" → "%s chưa có nguồn" ·
"not fed" → "chưa có nguồn" · "%s calculated or fixed" → "%s tính sẵn hoặc cố
định" · Employee/Contract/Bank/Contract pay components/Pay run → Nhân viên/Hợp
đồng/Ngân hàng/Khoản lương theo hợp đồng/Kỳ lương · "Nothing feeds this scheme
yet" → "Chưa có gì cấp dữ liệu cho bảng lương này" · "Map a spreadsheet" /
"Connect a system" / "Use Payobook records" · "this file has no such column".
PO rules per the ledger; run the parse gate.

## 5. Numbered test cases

Python (`tests/test_cleanmap_journey.py`; REWRITE the pinned assertions in
`test_journey_view.py` rather than deleting the file — list each reversal in
the report):

1. Payload has `v == 2`, lanes exactly `systems, feeds, transforms, scheme,
   source`; no `run` key.
2. A connector with zero wires into the scheme produces NO card, NO feed cards,
   NO transformation card (the Zoho case).
3. A connector with one wire produces its system card, exactly the one feed
   card, and one row on it.
4. A transformation consumed by the scheme: `t:` card with one row; `reads`
   links from the feed rows it consumes; those feed rows exist even though no
   component reads them directly.
5. An unconsumed transformation rule: absent.
6. File rows == the Spreadsheet board's accepted `c:` wires for the same scheme
   (same set of rule ids). Catches the `data_source_field` question either way.
7. Binding spelled as a letter alias lands on the heading's row (P1 map); a
   binding absent from the file → `state 'gone'`.
8. `employee_field`/`contract_field` links are `dir 'both'`; `bank_account` is
   `fwd`; `contract_component` and `period` are `back`.
9. Scheme rows == input rules, sequence order; `folded.n` == calculated +
   constant; `fed + unfed == inputs`.
10. A component with two declared sources has two links and is `fed` once.
11. Wires on a non-primary connector: links `dimmed`, component NOT counted
    `fed` by them, chip present on the system card.
12. Row order: every non-scheme card's rows are sorted by partner sequence.
13. Zero state: a scheme with no links → only the scheme card + `invite` block
    with doors filtered by lane config.
14. Every link's `a` and `b` resolve to a row that exists (no orphan ends).
15. Read-only: MF37-style row-count + checksum diff across `journey_data` = ∅.
16. `get_available_source_fields` is not called (patch + assert_not_called).
17. Query count of `journey_data` on the VN demo scheme ≤ the pre-phase count.

Browser (Chrome MCP, rize.payobook.com, light + dark, console read each time):

18. Pill row: Journey is last; opening Mapping from Settings still lands on it.
19. Collapsed: three lanes (Files & systems, Scheme, Payobook Source). No Zoho,
    no feeds, no Transformations, no Pay run, no bottom-left records card.
20. Click the file card → rows appear, lines fan from rows INTO the closed
    scheme card; click again → one counted line.
21. Open all three → row-to-row lines, near-parallel; two-way heads only on
    Employee/Contract rows.
22. Hover a file row → its path lights through the scheme row to the Payobook
    row (where one exists); everything else fades. Click pins; Esc unpins.
23. Scheme card open: unfed rows amber with "not fed"; "32 calculated or fixed"
    opens and closes on its own.
24. Corner icon on each card lands on the right tab, pre-scoped, with the
    "← Journey" chip; card body click never navigates.
25. Reload: the same cards are open. Private window: board still renders.
26. Filter "Vị trí": matching rows shown in temporarily-opened cards; clearing
    restores the previous open set.
27. Keyboard only: Tab to a card, Enter toggles, Tab to the corner icon, Enter
    navigates; rows focusable and trace on focus.
28. Phone width (390px): lanes stack; lines hidden; each row shows its partner
    as an inline tag instead (no horizontal scroll).
29. abm-style scheme with a system + transformations (use the VN demo scheme on
    `payobook`): five lanes appear by themselves.
30. VI language: every new string translated; no "Odoo" anywhere (grep the
    rendered DOM).
31. Open/close 20 times with all cards open: no leaked ResizeObserver, wires
    never detach from rows (screenshot mid-transition).

## 6. Deploy / verify

`pb_formula_studio` only; next free `19.0.1.x.0` after P1. Ledger deploy
contract verbatim: clean staging → per-module rsync → upgrade ALL databases →
purge `/web/assets/%` per DB → restart → content hash + version per DB.

## 7. Report back

* Tests 1–31 PASS/FAIL, with output for failures and screenshots for 19–23
  (light + dark).
* Each pinned old assertion that was reversed, with file:line.
* The answer to the `data_source_field` question (4.3).
* Query count before/after for `journey_data` on rize and on the VN demo.
* Any scheme on any database whose Journey shows `gone` or `dimmed` — those are
  owner debts, listed in plain words.
* New ledger entries CM5+.
