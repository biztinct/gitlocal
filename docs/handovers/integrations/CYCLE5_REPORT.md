# Integrations Cycle 5 — report: the wires

> Implementation report for `CYCLE5_THE_WIRES.md`. Every claim below is backed
> by an artefact in this file: a measured number, a log line, or a live browser
> observation on `abm.payobook.com` / `payobook.com`.

## The owner's four sentences, and what each became

| The owner's words | What shipped |
|---|---|
| the dashed arrows "go out of the screen — they should be something like what you have done in Formula engine" | The root cause was a scroll listener on the wrong element (WP-1.1). The board now clips, every endpoint is clamped into its column's band, and the curve is the Formula Engine's own arrow geometry — control points riding their endpoint's Y, an unrotated triangular head landing exactly on the tip |
| "need a mechanism/icon on the arrow on double clicking on which takes to source or destination component depending where you click on that mechanism/icon" | The three-zone wire hub `◀ │ ÷3600 │ ▶`. Either arrow scrolls that column to the card and flashes it; double-clicking the wire itself goes to whichever end you clicked nearer |
| "the blue arrow at top … is looking very clunky. think deep and implement an out of the world WOW arrow experience" | The story-bar rail rebuilt in the wires' own vocabulary — one solid stroke, the same filled triangle, still at rest, dash-flow only while the board is working. The counts became controls |
| "provide maybe a search on left column/source and also right column/destination so that user can search for a field as there could be 100s of fields" | A search box and All · Mapped · Unmapped · Suggested chips in both column headers; matches label, code, path **and sample value**; `M of N`; Esc clears; `/` focuses the hovered column |

---

## The root cause — confirmed, and reproduced

`t-on-scroll` sat on `.mc-col`. The scroller is its child `.mc-col-body`. DOM
`scroll` does not bubble and OWL binds `t-on-scroll` as a plain, non-delegated
native listener on that exact element — so `onColScroll` had **never run in
production**. The wires in the owner's screenshots are drawn to where the cards
*used to be*. Fixing only the clipping would have left every wire attached to
the wrong card: silently wrong, which is worse than visibly broken.

**Reproduced live, on the owner's exact board.** The Cycle-2 algorithm was
replayed verbatim against `abm` (Zoho People (ABM) 200 fields → AB Mauri Payroll
Vietnam) — two `querySelector`s per wire, no clamping, chord midpoint, geometry
computed once — the columns were then scrolled, and the result is the owner's
photograph: two amber dashed lines crossing the whole viewport, out past the top
edge over the mode strip and the story bar, out past the bottom, attached to
nothing. The same reconstruction reported `silentlyDropped: 15` — the fifteen
accepted wires the old `continue` threw away without a word (see *Findings*).

---

## Test results

### JS unit suite — 14/14 green (`/web/tests?filter=pb_formula_studio`)

New bundle `web.assets_unit_tests` on `pb_formula_studio`; file
`static/tests/mapping_canvas.test.js`.

| # | Test | Covers |
|---|---|---|
| 1 | scroll does not bubble — which is why the old binding could never fire | T1 (the mechanism) |
| 2 | a scroll on `.mc-col-body` triggers exactly one coalesced recompute | T1 |
| 3 | the right column's scroller is bound too | T1 |
| 4 | a numeric item id is not a different id from its data-id string | live defect, W147 |
| 5 | control points share the endpoint Y, so a wire leaves and arrives flat | T5 |
| 6 | the arrowhead apex is exactly the wire tip | T5 |
| 7 | a right-to-left wire reserves its head on the other side | T5 |
| 8 | the hub sits ON the curve at t=0.5 | WP-2 |
| 9 | `clampY` parks an out-of-band endpoint on the band edge and says so | T2 |
| 10 | docks aggregate per column edge, never one chip per wire | T3 |
| 11 | a dock chip never names a kind the pile is not entirely made of | live defect, W149 |
| 12 | a wire with both ends in view produces no chip at all | T3 |
| 13 | search matches label, code and sample — not just the label | T7 |
| 14 | search tolerates items with no sublabel, sample or meta | T7 |

**T1 was proven to fail on the pre-fix arrangement** two ways: test 1 asserts the
DOM semantics directly (a `scroll` dispatched on a child is seen by the child,
never by the parent — `onParent` is 0), and the live reconstruction above shows
the consequence on the real board.

### Python suites — T12: **0 failed, 0 error(s) of 109 tests**

```
odoo.tests.stats: pb_formula_studio:     16 tests 1.30s   988 queries
odoo.tests.stats: pb_hr_payroll_formula: 42 tests 3.65s  1598 queries
odoo.tests.stats: pb_import_advanced:    13 tests 1.36s  1045 queries
odoo.tests.stats: pb_integrations:       41 tests 0.51s   281 queries
odoo.tests.stats: pb_settings:           25 tests 0.10s   153 queries
odoo.tests.result: 0 failed, 0 error(s) of 109 tests when loading database 'payobook'
```

Scoped run (`-u` on the same five modules, W9/C18.40), inside a W136 stall-proof
unit. The two known pre-existing failures are in `pb_timeoff` / `pb_today`,
outside this scope, and were not touched.

### T10 — performance, measured

Owner's board, **200 left × 40 right**, real 17 wires:

| | |
|---|---|
| recompute cost | min 0.60 ms · **median 0.70 ms** · max 1.30 ms |
| 8 scroll events in one frame | **0** synchronous recomputes, **exactly 1** after one frame |
| 60-frame momentum scroll | 58 recomputes / 60 frames, avg 16.29 ms/frame (≈61 fps) |

Synthetic stress, same 200 × 40 columns, **82 drawn wires** (≥50 as required):

| | |
|---|---|
| recompute cost | min 1.30 ms · **median 1.70 ms** · p95 2.40 ms · max 2.60 ms |
| 10 scroll events in one frame | **0** synchronous, **exactly 1** after one frame |
| 90-frame momentum scroll | 88 recomputes / 90 frames · median frame 22.9 ms · p95 25.3 ms · **0 frames over 32 ms** |

No virtualization was needed and none was smuggled in. The per-frame figure
includes the CDP-driven scroll loop; the recompute itself is 1.7 ms of it.

The profiling also found the loop described in **W148**: `ui.geom` was
reassigned unconditionally on every recompute while `onPatched` scheduled the
next one — a permanent rAF loop present since Cycle 2, invisible at six wires.
A geometry signature now gates the write.

---

## Live validation (Chrome MCP, W129 temp users, both databases)

Temp validators created through `odoo-bin shell`, single-company, `company_ids`
and `company_id` in the same write (W129):
`ig-c5-validator@abm.local` (abm, uid 9, company 1 "AB Mauri") and
`ig-c5-validator@payobook.local` (payobook, uid 2096, company 5 "Payobook
Vietnam JSC"). Both removed at the end of the session — see *Teardown*.

| # | What | Where | Result |
|---|---|---|---|
| T2 | Containment — the owner's exact scene | abm | ✅ No path or badge outside the board at any scroll position, including with 82 wires |
| T3 | Dock chips | abm | ✅ `2 suggested below` on each column; click scrolled to `ID / id` and flashed it; the count fell to `1 suggested below`; the right chip flipped to `↑ 1 suggested above` after the target jump |
| T4 | Hub navigation | abm + payobook | ✅ `◀` and `▶` both jump and flash; the centre zone opened the transform popover with live preview and manager gating intact |
| T5 | Geometry | both | ✅ Arrowheads land exactly on the target card's edge; wires leave and arrive horizontally |
| T6 | Hover coupling | payobook | ✅ Hovering `bank_account` lit it **and** `Basic Salary`, thickened their wire, dimmed 28 other cards and the other wire |
| T7 | Search | abm | ✅ `bank` → `4 of 200`; `allowance` → `6 of 40`; the honesty banners read `2 wires hidden by this filter · clear` and `1 wire hidden by this filter · clear`, with matching dashed "hidden by filter" dock chips |
| T8 | Filters | abm | ✅ Chips are dynamic — *Suggested* appears only where suggestions exist (absent on the payobook ADP board, present on abm) |
| T9 | Reduced motion | both | ✅ All five rules present inside `@media (prefers-reduced-motion: reduce)`, verified through the CSSOM of the shipped bundle: `.mc-flow{display:none}`, transitions off, `.mc-item.flash` off, `.is-pulse` off, the rail's dash-flow off. Highlight colours are **outside** the block, so they survive |
| T10 | Performance | abm | ✅ table above |
| T11 | Cycle-2 regressions | payobook | ✅ Draw (two wires created), transform preview + debounce, delete (both removed), all five modes, both pickers, `Accept all ≥90%`, `Apply template…`, arrival contexts. **The legacy Formula-Studio overlay host renders correctly**: 5 tabs, `Search 56 fields…` / `Search 53 columns…`, chips, and the single cycle wire correctly docked as `1 mapped below` with a delete-only hub (no transform affordance — D-I1 preserved) |
| T13 | Console + network | abm | ✅ **0 console errors**, 1 pre-existing `biz_debrand` manifest-icon warning; **0 non-200 responses** across 27 requests |

**WP-5 controls, verified:** `15 mapped` sets `cmd.token` 0 → 1 and `ui.pulse`
true, the board takes `.is-pulse` for ~1 s, and a second click goes to token 2
and pulses again — the token is what makes a repeat repeat. `2 suggested`
filtered both columns to `2 of 200` and `2 of 40` with the amber chips on.

---

## Findings for the owner (not bugs in this cycle's code)

1. **abm: all 15 accepted mappings point at source fields the connector does not
   deliver.** `f:DEPCOUNT`, `f:Dateofjoining`, `f:EmployeeID`, … — Cycle 4 seeded
   them from the legacy vendor template's field codes, while
   `get_available_source_fields()` returns what the connector's stored payloads
   actually contain (`f:account_number`, `f:date_of_joining`, …). The previous
   canvas dropped these fifteen wires with a bare `continue` and said nothing;
   the board now reads **"15 mappings point at a field this source no longer
   delivers."** The story bar still says *15 mapped* because the records exist —
   that pair of statements is the honest description of the data. This is an
   abm data debt, and it is the reason the owner's screenshot showed only two
   wires on a board that claimed fifteen.
2. **`pb_formula_studio` never declared `pb_import_kit`** despite importing its
   icon registry since Cycle 2. Declared this cycle.
3. **Version drift unrelated to this cycle** (W118 audit, both databases):
   `biz_theme` 19.0.1.2.0 → 19.0.1.2.1, `biz_deroute` 19.0.1.1.0 → 19.0.1.1.1,
   and on payobook `biz_debrand` 19.0.2.1.0 → 19.0.2.3.0. Left alone — out of
   scope, and W143 says a restart that publishes someone else's fix belongs in a
   report, not in a side effect.

---

## Deploy

Two windows, both W136 stall-proof units (the unit stops, upgrades and starts
the service itself), plus four asset-only redeploys with no window at all.

| Step | Result |
|---|---|
| rsync → fresh staging `/tmp/i5stage.884723971` (verified empty first) | ok |
| `sudo rsync --chown=odoo:odoo` → `/odoo/odoo-server/addons` | ok |
| unit `i5deploy`: stop · poll `PROCS_LEFT=0` · `-u pb_formula_studio,pb_import_kit` on **payobook** and **abm** · start | `EXIT_PAYOBOOK=0` `EXIT_ABM=0` `ACTIVE=active` |
| ERROR/CRITICAL in either upgrade log | **0** and **0** |
| unit `i5tests`: stop · scoped `-u` + `--test-enable` · start | `EXIT=0` `ACTIVE=active` |
| versions after | `pb_formula_studio 19.0.1.71.0`, `pb_import_kit 19.0.1.6.0` — identical on both databases |
| post-deploy page load (mandatory after SCSS) | ✅ both hosts render, no Sass runtime failure |

Asset discipline: `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` on
both databases after each SCSS/JS redeploy, plus a cache-ignoring reload — a
plain reload serves the stale bundle (W150.2).

---

## Commits

| # | Hash | Subject |
|---|---|---|
| 1 | `53ea332a` | fix(pb_formula_studio): the wires follow the scroll, and never leave the board |
| 2 | `e75b58d7` | feat(pb_formula_studio): the story bar's rail, and counts that do something |
| 3 | `7bf9cb70` | test(pb_formula_studio): the twelfth test is why the bug was invisible |
| 4 | `37cd62e1` | fix(pb_formula_studio): three defects the owner's own board found |
| 5 | *(this file)* | docs(integrations): Cycle 5's ledger — W146-W150 — and the report |

Explicit staging throughout. Nothing pushed. `.claude/settings.json`, `thaco/`
and `ABM/` never staged.

---

## Deviations from the handover, and why

1. **Commits are 4, not 8.** The handover's eight were one coherent rewrite of a
   289-line component; splitting them by file would have produced intermediate
   commits where a host passed a prop the canvas no longer declared. Each commit
   here is self-consistent and its message enumerates the work packages it
   carries. Nothing was accumulated: the first two landed before the first
   deploy, per this program's incident history.
2. **The *Suggested* filter chip renders on both columns**, not only the left.
   The story bar's `2 suggested` control filters both columns, and a chip that
   showed the resulting state on one side only would have made that control look
   broken.
3. **Suggested wires keep their hub permanently**; only accepted wires hide
   theirs until hover or selection. A suggestion is the board's call to action
   and it already behaved this way in Cycle 2; hiding it would have removed
   Accept/Reject from sight.
4. **The travelling dot is a CSS `pathLength="100"` dash, not SMIL** — the
   handover left this call to the implementer. SMIL `animateMotion` restarts on
   every OWL re-render, which on a scrolling board is every frame. The dash is
   normalised, so a short wire and a long one carry the same-looking bead, and
   durations are desynchronised (`7.5 + (i % 9) * 0.7`) exactly as the reference
   does. It is capped at 60 wires and paused while `busy`.
5. **Keyboard reach for hubs is `w` / `Shift+w`**, not Tab. Hidden hubs are
   `t-if`-ed out of the DOM, so Tab cannot reach them and making them
   permanently focusable would have put 50 invisible buttons in the tab order.
   `w` cycles the selection, `←`/`→` jump to the two ends, `Enter` opens the
   transform, `Escape` deselects, `/` focuses the hovered column's search.
6. **`busy` was wired up rather than deleted.** Both hosts pass it, so removing
   it meant touching both; it now pauses the beads and disables hubs and dock
   chips, which stops a click acting on geometry that is about to be replaced.
7. **`.error` is emitted rather than deleted** — by wires whose transform is
   failing, which is a real state the board had no way to show.

## New rules — W146 … W150

Appended to `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` in the same commit as this
report.

- **W146** `scroll` does not bubble, and OWL's `t-on-scroll` is a plain listener
  on that exact element — a handler one level above the scroller never runs, and
  the failure mode is *stale output*, not *no output*.
- **W147** `dataset.id` is always a string; replacing an attribute-selector
  lookup with a `Map` silently loses every id that is not one.
- **W148** Writing a fresh array into reactive state on every recompute while
  `onPatched` schedules the next one is a permanent rAF loop that looks like an
  idle screen.
- **W149** An aggregate badge may name a kind only when the whole pile is that
  kind — `any` is the wrong quantifier, and it tells the lie next to an honest
  number.
- **W150** `mountWithCleanup` starts the real service stack, so on a database
  with `mail` a component test needs `defineMailModels()`; and a new
  `assets_unit_tests` bundle needs an attachment purge plus a cache-ignoring
  reload before `/web/tests` will list it at all.

## Teardown

Both temp validators and their residue removed in the same session. The residue
was cleared **before** the `unlink`, and the fallback branch begins with a
`rollback()` — W144, whose lesson this cycle promptly re-earned: the browser
pass again left a `payroll.ai.conversation` behind on abm, exactly the row that
blocked Cycle 4's teardown.

```
===== payobook =====            ===== abm =====
IGC5-TARGET payobook [2096]     IGC5-TARGET abm [9]
IGC5-RESIDUE mail.presence 1    IGC5-RESIDUE payroll.ai.conversation 1
IGC5-RESIDUE res.device.log 1   IGC5-RESIDUE mail.presence 1
IGC5-RESIDUE res.users.log 2    IGC5-RESIDUE res.device.log 1
IGC5-UNLINKED ok                IGC5-RESIDUE res.users.log 2
IGC5-PARTNER-UNLINKED ok        IGC5-UNLINKED ok
                                IGC5-PARTNER-UNLINKED ok
```

Absence read back from the database afterwards, not from the script's own
output (W144.3):

```sql
-- payobook                              -- abm
SELECT count(*) FROM res_users            SELECT count(*) FROM res_users
  WHERE login LIKE 'ig-c5%';   -->  0       WHERE login LIKE 'ig-c5%';   -->  0
SELECT count(*) FROM res_partner          SELECT count(*) FROM res_partner
  WHERE name ILIKE '%IG-C5%';  -->  0       WHERE name ILIKE '%IG-C5%';  -->  0
```

Service after teardown: `active`; `payobook=200`, `abm=200`. The session-unique
staging directory `/tmp/i5stage.884723971` was deleted (W118/W119).

## Nothing was left for the owner to decide mid-cycle

No destructive or irreversible action was required. The two mappings drawn on
the payobook demo world during T11 were deleted in the same pass (board back to
`0 mapped`); no abm record was created, modified or deleted.
