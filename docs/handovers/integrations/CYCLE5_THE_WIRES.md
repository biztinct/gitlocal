# Integrations Program — Cycle 5: the wires

> STATUS: FINAL. All plumbing facts below were verified by exploration on 2026-08-20 against the deployed code. **Do not re-derive them.**

The program shipped the Mapping Studio in Cycle 2 and filled it with real data in Cycles 3–4. On the owner's live abm screen — a **200-field** Zoho connector wired to the **40-column** "AB Mauri Payroll Vietnam" scheme — three things break down:

1. **Wires escape the screen.** Two amber dashed (suggested) wires run diagonally across the whole viewport, over the mode toolbar and out past the top and bottom edges.
2. **No way to follow a wire to its ends.** The owner asked for **a control on the wire that, on double-click, jumps to the source or the destination depending on which part you click**.
3. **The story-bar connector looks clunky**, and **neither column has any search** — with 200 source fields, finding one field means scrolling.

---

## The root cause — verified, and it is NOT (only) clipping

**`t-on-scroll` is bound to the wrong element, so wire geometry is never recomputed while you scroll.**

- The scroller is `.mc-col-body` (`pb_formula_studio/static/src/scss/mapping.scss:60`, `overflow-y:auto`).
- The handler sits on its PARENT `.mc-col` (`pb_formula_studio/static/src/xml/mapping_canvas.xml:17` and `:44`, `t-on-scroll="onColScroll"`).
- DOM `scroll` events **do not bubble**, and Owl attaches `t-on-scroll` as a plain non-delegated native listener on that exact element (`owl.js` `createEventHandler`/`createElementHandler`; synthetic delegation only with the `.synthetic` suffix).

So `onColScroll` (`mapping_canvas.js:67`) never fires. Wires stay pinned at their **pre-scroll** coordinates until some unrelated trigger (an OWL patch, a window resize) recomputes them. What the owner photographed is **stale geometry**: lines drawn to where cards used to be. Everything else compounds it:

- `.mc-wires` is `overflow: visible` (`mapping.scss:45`) and `.mapping-canvas` (`:44`) declares no `overflow` at all — the only clip in the studio host is the outer shell `.pbim.pbms { overflow:hidden }` (`mapping_studio.scss:14`), so a stray path paints freely over the story bar and the mode toolbar.
- There is **no clamping** of endpoints to the visible band and no off-screen indicator; the canvas's own comment admits the gap (`mapping_canvas.js:87-88`): *"clip badges/paths that fall outside the visible scroll band would need per-column clipping; columns are short here so full-board paint is fine."* Cycle 2 shipped that assumption; Cycles 3–4 invalidated it.

**Fix the listener first, then containment.** A fix that only clips would leave wires attached to the wrong cards — silently wrong, the bug class this codebase punishes hardest.

---

## Verified plumbing — `MappingCanvas` (the component to evolve)

`pb_formula_studio/static/src/js/mapping/mapping_canvas.js` (289 lines), template `xml/mapping_canvas.xml` (175), styles `scss/mapping.scss` (252). Host: `MappingStudio` (`js/mapping/mapping_studio.js`, 660 lines; template `xml/mapping_studio.xml`; action `pb_mapping_studio`). Second host: the legacy Formula-Studio overlay (`studio.xml:1867-1881`) — **both must keep working**.

- **Props** (`:12-28`): `leftItems`, `rightItems`, `wires`, `leftTitle`, `rightTitle`, `canEdit`, `busy`, `onAccept/onReject/onDelete`, `onDraw`, `onSuggest`, `onTransformPreview`, `onTransformSave`, `onRemoveRight`. Dead today: `busy` never read; `onSuggest` never called from the canvas; `ui.armedRight` never set (right-side arming is dead); `get svgSize()` (`:91-94`) referenced nowhere.
- **Geometry** `_recompute()` (`:68-90`): origin = `rootRef.el` rect; per wire, two `root.querySelector('.mc-item[data-side=…][data-id="${id}"]')` lookups (**O(2×wires) selector queries per frame**, and the interpolation is unescaped — an id containing `"` throws); `x1 = lr.right - rb.left`, `y1` = left card centre; `x2 = rr.left - rb.left`, `y2` = right card centre; `dx = Math.max(48, |x2-x1| * 0.42)`; path `M x1,y1 C x1+dx,y1 x2-dx,y2 x2,y2`; badge anchor = chord midpoint `mx,my`. Wires whose endpoint card is absent from the DOM are **silently dropped** (`:76`).
- **Recompute triggers**: `onMounted` (`:51-55`, plus a `ResizeObserver` on the root **only** — not the columns), `onPatched` (`:57`), `window resize` (`:59`), and the broken `t-on-scroll`. `_schedule()` (`:63-66`) coalesces via one rAF with a `this._raf` guard — **keep this**; teardown in `onWillUnmount` (`:56`).
- **SVG**: no `viewBox`, no width/height attrs (`mapping_canvas.xml:8`); sized by CSS; coordinates are raw CSS px, 1:1 with the root. `pointer-events:none` on the layer (`mapping.scss:45`), **no handlers on `<path>`** — hover (`ui.hoverWire` → `.mc-wire.hot`, `mapping.scss:50`) is driven only from the badge divs (`xml:74,83,94`). There is **no wire-selection concept** in state.
- **Strokes** (`mapping.scss:46-50`): base `stroke-width:2`, `.accepted` `var(--i,#5A4BB0)` 2.4, `.suggested` `#D97706` dashed `6 5` opacity .85, `.error` `#DC2626` (never emitted by any adapter), `.hot` 3.4. **No arrowheads at all** — no `marker`, no polygon.
- **Badges**: HTML divs in `.mc-badges` (`xml:70`, z-index 3), positioned `left/top` px at the chord midpoint with `translate(-50%,-50%)` (`mapping.scss:91-92`); three mutually-exclusive variants (`sug` / `tf` / `acc`) sharing one anchor, **no collision avoidance between nearby wires**. Transform glyphs `× ÷ + − ≈ |x| ? ƒ` from `transformGlyph()` (`:154-167`).
- **Transform popover**: `openTransform` (`:196-213`), debounced preview 260ms + supersede token (`:220-240`), `saveTransform` (`:244-261`) manager+non-python gated. Anchored absolutely inside the canvas via `tfAnchor` (`:180-183`) → **clipped by ancestor overflow and never repositions to stay in view** (relevant once you add clipping — see WP-1.5).
- **Draw interaction**: `clickLeft` (`:125-130`, toggles arm), `clickRight` (`:131-137`, fires `onDraw`); keyboard at `:264-288` (Arrow/Enter/Escape). No drag, no rubber-band preview.
- **Layout**: `.mc-col` fixed **340px** (`mapping.scss:53`), left `margin-right:auto` / right `margin-left:auto` (`:54-55`) — the gutter is whatever remains, and that width drives `dx`. Column headers are OUTSIDE the scroller (`xml:18-21`, `:45-48`) — **that is where search belongs**. Z-stack: wires 1 → columns 2 → badges 3 → drawhint 4 → tf scrim 40 → popover 41.
- **Capacity**: **no virtualization, no cap** — `t-foreach` renders every item (`xml:23`, `:50`). Left items for `api` come from `get_available_source_fields()` (`pb_hr_payroll_formula/models/integration_field_mapping.py:445-489`, flattens ≤20 recent payloads, depth ≤6) — 100-300+ entries is normal, hence the owner's 200.
- **Story bar** (`mapping_studio.xml:24-84`): FROM picker `:28-43`, feed chip `:47-52` (api mode only), **the centre connector `:56-63`** — a separate decorative `<svg viewBox="0 0 240 24">` with `path d="M2 12 H 210"` + a chevron `d="M206 6 L 218 12 L 206 18"`, styled `mapping_studio.scss:92-110` (fixed 240px, `stroke-dasharray: 9 7`, `@keyframes pbms-flow` 1.1s linear infinite, already disabled under `prefers-reduced-motion` at `:105-107`) — and the counts `mappedCount`/`suggestedCount` (`mapping_studio.js:283-284`). TO picker `:65-83`. Modes `MODES` (`js:54-65`) → pills `xml:114-121`; `setMode` nulls `state.data` and reloads (`js:349-355`).
- **Search today**: exists ONLY inside the picker dropdown (`mapping_studio.xml:92-96`, `state.pquery`, `pickerOptions` `js:366-411`). **Nothing filters `leftItems`/`rightItems`.**
- **Token debt to respect (W1)**: `mapping.scss` hardcodes `#D97706 #DC2626 #FCD34D #B45309 #F1F5F9 #FEE2E2 #B91C1C #CBD5E1 #94A3B8 #64748B #EEF1F5 #FAFAFE`; `--i-deep` is used (`:110`) but never bound (`mapping_studio.scss:16-24` binds the rest from `--pbim-*`). Bind or replace what you touch; do not add new hexes.

---

## The quality bar already exists in this repo — copy it, don't invent it

The Formula Engine's dependency arrows (`formula_studio.js:2740-2854`, layer `studio.xml:918`, CSS `studio.scss:590`) are exactly what the owner pointed at. VERIFIED mechanics to port:

- **`_arrow(layer, sx, sy, tipx, ty, color, onClick, dur, clampPt)` (`formula_studio.js:2768-2791`) is genuinely generic** — pure numbers + colour + callback. Lift the geometry:
  ```js
  const rtl = tipx < sx;
  const basex = tipx + (rtl ? 14 : -14);          // reserve 14px for the head
  const dx = basex - sx, c1 = sx + dx * 0.45, c2 = sx + dx * 0.55;
  const d = `M ${sx} ${sy} C ${c1} ${sy} ${c2} ${ty} ${basex} ${ty}`;
  ```
  Both control points share the endpoint Y → the curve **leaves and arrives horizontally**; that plus the tight 0.45/0.55 arms is the difference between "a connection" and "a diagonal scratch". (MappingCanvas's outward-offset `0.42/max(48)` form is softer and longer-shouldered — adopt the reference form.)
- **Arrowheads are hand-placed polygons, not `<marker>`s** (`:2785-2787`): `points="tipx,ty basex,ty-7 basex,ty+7"`, solid fill, no rotation — exact landing, no marker/stroke-scaling pitfalls. This works *because* arrival is guaranteed horizontal.
- **Containment is four rules; there is no `<clipPath>` anywhere in that module**: per-pane Y **clamping into an inset band** (`:2819`, `:2827-2829`, `:2848-2850`); a **clamp indicator** — a 4px dot at the parked endpoint (`:2790`); an **anchorability guard** skipping `display:none`/off-canvas panes whose rects would sweep a line across the screen (`:2806-2814`); and CSS `.pbfs-work { overflow-x: clip }` (`studio.scss:112`) with the layer `pointer-events:none` and paths re-enabling `pointer-events:stroke` individually (`:2777`).
- **Coordinate space**: screen px, no viewBox, SVG sized to the container rect (`:2800-2802`), rects converted by `x - wr.left` / `y - wr.top`.
- **Click-to-navigate already works there**: path AND head are hit-testable; handler `scrollToCol` (`:2761-2767`) does `scrollIntoView({behavior:"smooth", block:"center"})` then adds `.pulse` for 950ms (`@keyframes pbfs-pulse`, `studio.scss:586`). **Clone this flash-on-arrival.**
- **The traveling dot** (`:2780-2783`): `<circle r="3.6">` + `<animateMotion>` along the same path, durations **deliberately desynchronised** (`7.5 + i*0.7`) so N dots never march in lockstep — a large part of why it feels alive. (SMIL restarts on every redraw; with our declarative OWL paths prefer a CSS `offset-path`/dash-offset equivalent if SMIL fights the re-render — your call, report it.)

Two defects there NOT to copy: no rAF coalescing (every scroll schedules a full `innerHTML=""` rebuild) and `addEventListener` with no teardown (`:2742-2751`). **Keep MappingCanvas's lifecycle; swap its geometry; add containment.**

---

## The design (binding)

### WP-1 — Containment: a wire may never leave the board, and never lie
1. **Fix the scroll binding** — move `t-on-scroll` to `.mc-col-body` (or listen with `capture:true`), and observe both column bodies with the existing `ResizeObserver`. Add a regression test that asserts a scroll event on the body triggers exactly one coalesced recompute. *This is the primary bug.*
2. **Clip the layer**: give the canvas root/board `overflow: clip` (follow `.pbfs-work`'s proven shape) so nothing paints over the story bar, the mode strip or the column headers.
3. **Clamp per column into an inset band** (±8px, as the reference). An endpoint whose card is scrolled out of its column parks on that column's edge instead of flying off.
4. **Dock chips** — the upgrade over the reference's bare dot, because our columns are long: parked endpoints on the same edge of the same column **aggregate into one chip** — `▲ 3 mapped above` / `▼ 5 below`, amber variant when the docked wires are suggestions. Clicking scrolls that column to the nearest docked endpoint; repeat clicks cycle. Never a line to nowhere; never a silently-dropped connection (today `:76` drops them silently — a docked/"unavailable" state must replace that where the card exists but is out of band, and the genuinely-absent case must be counted and surfaced, not swallowed).
5. **Anchorability guard**: skip wires whose column/card rects are unmeasurable (hidden host, mid-transition) rather than drawing from garbage. Also: with clipping added, re-check the transform popover (`tfAnchor`, `:180-183`) — it is absolutely positioned inside the canvas and will now be clipped; reposition it (flip/shift to stay in view) or portal it above the clip.

### WP-2 — The wire hub (the owner's explicit ask)
At each wire's midpoint, a **three-zone hub pill**:

```
   ◀ │ ÷3600 │ ▶      ◀ = jump to SOURCE   centre = the transform   ▶ = jump to TARGET
```

- **Double-click** on `◀`/`▶` jumps to that end — the gesture the owner named — and **single click does the same** (double-click alone is undiscoverable). Wire-selection moves to the path, so the two never conflict.
- **Double-clicking the path itself** jumps to whichever end is nearer the click point, so "depending where you click" also holds on the wire.
- Jumping = the reference behaviour: smooth `scrollIntoView({block:"center"})` on the owning column **plus a flash ring** on arrival (clone `.pulse`/`pbfs-pulse`), with the hub staying highlighted so you can bounce to the other end.
- The **centre zone is the existing transform glyph** and keeps its current behaviour (popover, debounced live preview, manager+non-python gating). One object per wire — fold today's three overlapping badge variants into it rather than adding a fourth.
- Hubs show on hover/selection for unselected wires (50 pills at once is clutter); the selected wire's hub is always visible. Give nearby hubs **collision avoidance** (today they stack at identical coordinates with none). Keyboard reachable (extend the existing `onKeydown` model: Tab to wire, Enter opens, ←/→ jump).
- Add real hit-testing on paths (`pointer-events:stroke` + a wider transparent hit path underneath), since the layer is `pointer-events:none` today.

### WP-3 — Hover coupling (the "what maps to what" payoff)
- Hover a **wire** → both endpoint cards highlight, wire thickens (`.hot` exists), everything else dims.
- Hover a **card** → its wires thicken, counterpart cards highlight, unrelated wires dim to ~20%.
- Selection persists until dismissed. `prefers-reduced-motion` disables travelling dots and dim transitions, never the highlight itself.

### WP-4 — Search + filters on both columns
- A **search field in each column header** (headers are already outside the scroller): "Search 200 fields…" / "Search 40 columns…", matching label, code/path (`meta.col`, sublabel) and sample; debounced ~120ms; shows `12 of 200`; `Esc` clears; `/` focuses the hovered column's search.
- **Filter chips per column: All · Mapped · Unmapped** (+ **Suggested** on the left when suggestions exist). With 200 fields, *Unmapped* is the workhorse.
- **Filtering must never lie about wires.** A wire whose endpoint is filtered out does not vanish: it docks (WP-1.4) with distinct "hidden by filter" styling, and the column header shows `3 wires hidden by this filter · clear`.
- State is per-mode and resets on connector/feed/scheme/mode change (`setMode` already nulls `state.data`).

### WP-5 — The story-bar connector, redesigned
Rework `mapping_studio.xml:56-63` + `mapping_studio.scss:92-110` into one coherent object:
- a thin rail using the **same arrowhead polygon language** as the wires (today's chevron is a different vocabulary);
- the dash-flow animation runs **only while loading/suggesting** — static at rest, so the screen is calm (keep the existing `prefers-reduced-motion` guard);
- counts become **controls**: `15 mapped` → flash all wires (one-second board pulse); `2 suggested` → filter both columns to the suggested set (amber, matching the dashed wires);
- no gradients (W3), no new hexes (W1), Lucide via the IC registry (W2).

### WP-6 — Performance discipline (200×40 is the new baseline)
- Replace the per-wire `querySelector` pair with **one cached offset map per column** (single pass over `.mc-item` children → `{id: {top, height}}`), invalidated on scroll/resize/filter/data change; recompute becomes O(wires) arithmetic. Escape or avoid interpolated attribute selectors entirely (today an id containing `"` throws).
- Keep the rAF coalescing guard; passive scroll listeners; `useExternalListener` teardown.
- Target: no dropped frames scrolling either column with ≥50 wires. **Report the measured recompute cost.** If profiling says virtualization is required, say so and defer it — do not smuggle it in.

### Hygiene (only what you touch)
Remove or wire up the dead code you encounter in these files: `busy`, `onSuggest` (canvas), `armedRight`, `svgSize`, the unreachable `.mc-wire.accepted.hot + .mc-badge.acc` selector and the duplicated `.mc-badge.acc { opacity }` rule (`mapping.scss:101-108`), and either emit or delete the `.error` wire state. Bind `--i-deep` or drop it. Each with a one-line reason in the commit message.

### Binding non-goals
- No changes to mapping persistence, RPC contracts, or the transform whitelist (python stays server-refused, W12). No schema changes. No new models.
- **Do not refactor the Formula Engine's own arrow renderer.** Lift the geometry into the mapping layer; a shared util is acceptable only if `formula_studio.js` behaviour stays byte-identical and its tests prove it.
- No virtualization unless WP-6 profiling demands it. Don't touch the ⌘K fold question (separate owner decision). Don't fix the two known pre-existing failures.
- **The legacy Formula-Studio overlay host (`studio.xml:1867-1881`) must keep working** — same component, short columns, no dock chips expected there.

---

## Numbered test cases
1. **Scroll binding**: a `scroll` event on `.mc-col-body` triggers exactly one coalesced recompute (and the pre-fix code fails this test — prove it fails first).
2. **Containment**: with both endpoints scrolled out of view, no path or badge paints outside the board; parked coordinates lie inside the clamp band. Reproduce the owner's exact scene (abm, 200-field Zoho connector, AB Mauri config, 15 mapped + 2 suggested) before and after.
3. **Dock chips**: N wires parked on one edge yield ONE chip with the correct count; click scrolls to the nearest docked endpoint; repeat clicks cycle; the chip disappears when its wires re-enter view.
4. **Hub navigation**: double-click `◀` scrolls the left column to the source and flashes it; `▶` likewise; double-click on the path jumps to the nearer end; the centre zone still opens the transform popover with live preview and manager gating intact.
5. **Geometry**: arrowhead apex equals the wire tip coordinate; control points share endpoint Y (horizontal leave/arrive).
6. **Hover coupling**: hovering a card highlights exactly its wires and counterparts; unrelated wires dim; leaving restores.
7. **Search**: filters by label and by code/path; count reads `M of N`; `Esc` clears; no wire silently lost — the "hidden by filter" affordance shows the right number.
8. **Filters**: *Unmapped* on the 200-field connector lists exactly the fields with no wire (assert against the wire set); *Suggested* shows only suggestion endpoints.
9. **Reduced motion**: with `prefers-reduced-motion: reduce`, no travelling dots and no dash animation; highlights still work.
10. **Performance**: scroll both columns with ≥50 wires; prove the rAF guard coalesces (≤1 recompute per frame) and report measured cost per recompute at 200×40.
11. **Regression**: Cycle 2's flows unchanged — draw, transform preview/save, delete, suggest, accept-all ≥90%, template apply, all five modes, arrival contexts from the connector cockpit and the board count; **and the legacy overlay host renders correctly**.
12. **Suites**: pb_formula_studio + pb_hr_payroll_formula + pb_integrations + pb_settings + pb_import_advanced in one scoped run, exit 0 modulo the two known pre-existing failures.
13. **Live validation** (Chrome MCP, W129 temp user, W130 own Chrome): on **abm** (the owner's exact screen) and on payobook's demo world — before/after screenshots of both owner screenshots' scenes, plus dock chips, hub hover, hub jump + flash, search filtering, suggested filter, reduced-motion; zero console errors, zero non-warmup ≥400s.

## Deploy + verify
Standard ritual with the **W136 stall-proof unit** (the unit restarts the service itself). `pb_formula_studio` is asset-heavy: version-diff the reverse-dep closure (W118), expect a bundle rebuild, and Chrome-load a page after the SCSS deploy (compile errors surface only at runtime; watch the Sass mixed-unit `min()/max()` trap). JS gate is `node --input-type=module --check < file` (W127).

## Self-review (mandatory)
Re-read the diff against this handover. Check twice: (1) no wire paints outside the board at ANY scroll position, including mid-momentum; (2) no search/filter/clamp path can hide a connection without saying so; (3) the legacy overlay host is unbroken; (4) hub hit-zones are trackpad-sized and don't swallow wire-select or the transform popover.

## Commits
Per feature, explicit staging, never push: (1) fix(pb_formula_studio): the wires follow the scroll — the listener was on the wrong element; (2) fix: a wire never leaves the board — clipping, clamping, dock chips; (3) feat: the wire hub — both ends, one click away; (4) feat: hover tells you what maps to what; (5) feat: search and filter both columns; (6) feat: the story bar's rail, and counts that do something; (7) perf: one offset map per column, not two selectors per wire; (8) docs: ledger + report. Tests ship with their feature (W9). Write `CYCLE5_REPORT.md` incrementally, committing at milestones.

## Report back
Per-test evidence, before/after screenshots of the owner's two exact scenes, measured frame cost, commit hashes, deploy EXIT codes, deviations with reasoning, new W-rules (W146+), and anything too risky to decide alone.
