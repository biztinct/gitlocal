# WORKFORCE P5 — The Week Grid, redesigned: cells show outcomes, not inputs

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules through W54 + P6's additions).
Visual target: **mockup A's grid** in `docs/WORKFORCE_REDESIGN_OPTIONS.html` — plain bold hour
numbers in cells, OT as compact chips, one focused editing state — plus the owner's direct
feedback on the current live grid (screenshot reviewed 2026-08-18): *"the % pills are very
confusing."* Field-note grammar: Deputy's consolidated timesheet row + tolerance chrome; Zoho's
tabular day entry; When-I-Work's keyboard ergonomics gap as the anti-pattern to avoid.

## §1 The diagnosis (owner-confirmed)

Today every cell renders a pill per APPLICABLE OT rate (`150%` `130%`, Saturday `200%`) whether or
not any hours exist — inputs masquerading as data. An empty week reads as a wall of red pills; the
one real entry ("6 · 150% 3 DRAFT") drowns. The Save button floats disabled top-right under a
tooltip. Rates are configuration — they belong in a legend, once.

## §2 Scope

Redesign the **generic `biz_week_grid` component** (both hosts get it automatically: the Time-hub
Week-Grid lens and the standalone Weekly Entry action) around one principle: **cells show
outcomes; entry lives in a focused editor.**

**Binding non-goals:** the adapter contract (`adapter/params/onData/onDirty/onFocus/onSaved`), the
`flags`/`day_badges` seam (trips' violet BT badge, young-worker `week_cap` — Phase C/E consumers),
the save concurrency token, `WF_ROW_CAP`, the `--bwg-*`→pbim token mapping, the Ceilings rail, and
the submit/approve tray SEMANTICS are all preserved. No backend model changes; if the editor needs
per-day applicable-type metadata, it is already in the payload the pills render from today — reuse
it. No autosave. Don't touch Timeline/Exceptions/Import lenses.

## §3 Design decisions (binding)

1. **Cell anatomy v2.** A cell renders, at most: the day's regular **hours as a bold tabular
   number**; **OT chips ONLY where hours were entered** — `+3 OT` tinted by type (colors from the
   W1 categorical order, assigned per `hr.overtime.config` type in the legend's fixed order);
   a **status micro-dot** for OT state (hollow amber = draft, solid amber = submitted, green
   check = approved); existing flag badges (BT, week_cap) as micro-icons. Empty cell = blank;
   a subtle `+` appears on hover/focus only. **Zero rate-% text in cells** (T-gated).
2. **Cell editor.** Click or Enter opens a popover editor anchored to the cell (overlay service,
   W43): Regular-hours input (auto-focused), one stepper row per applicable OT type for THAT day
   labelled with name + rate ("Overtime · 150%"), a live ceiling mini-bar (reuse the payload the
   rail already loads — no new RPC), inline warnings incl. the over-cap → bonus-split preview
   (Phase-K `_split` semantics, advisory copy, never blocking), Save/Cancel; Enter saves, Esc
   cancels; the save path is the EXISTING dirty-cell mechanism (the editor stages, the tray
   commits — W21: staging from handlers only).
3. **Keyboard-first.** Arrow keys move cell focus; typing digits on a focused cell edits regular
   hours inline (fast path, no popover); Enter opens the editor for OT detail; Tab advances;
   Ctrl/Cmd+D fills down from the cell above; a small `?` chip shows the shortcut map. (This is
   the anti-Connecteam move — dense grids need shortcuts.)
4. **Legend, once.** One compact row above the grid: swatch + name + rate per OT type, plus the
   status-dot key. Rates appear here and in the editor — nowhere else.
5. **Summaries.** Sticky day-column footer: Σ regular + Σ OT per day. Row-total column stays;
   weekend shading and today-column tint stay.
6. **Chrome.** The floating top-right Save dies; the sticky bottom tray becomes the single
   commit point: "N cells edited · M h OT drafted — Save · Discard · Submit all" (existing
   submit/approve actions unchanged). Add an "only rows with entries" filter chip beside the
   row-filter box.
7. **Both hosts verified** (Time-hub lens + standalone action), embedded and not (W17 discipline
   already in place).

## §3.5 P6 grounding (measured live — calibrate against it)

- `get_week_entries` timings on the seeded cohort: unfiltered current week ~1.4s / 200 rows;
  dept-filtered ~500ms / 169 rows; settled week 2026-08-10 unfiltered 746ms with **267 filled REG
  cells** vs the current week's ~49. **Judge the redesign on BOTH**: the settled week (density) and
  the current week (sparseness is data-honest — elapsed days only, and today's open punches
  contribute 0.0).
- OT chip density is deliberately low (2–5 chips/week). Your live edit round-trip creates its own
  chips; no wider seeding needed.
- The unfiltered grid is alphabetical over 4,505 employees — the department filter is the honest
  demo view; use "Stores - North" (169 rows) for screenshots.

## §4 Work packages (one commit each)

- **WP-0 Two P6-exposed defects (surgical, first, own tests):**
  (a) `pb.close._classify` flags every currently-open punch as `missing_checkout` with NO
  threshold — on a live day ~50 of 66 flags are just people at work. Reuse the exception engine's
  own open-hours threshold semantics (read how `pb.attendance.exception.engine` gates
  `missing_checkout` via open-hours before flagging) so the Close board and the engine agree; a
  punch open less than the threshold on the CURRENT day is not a flag. Tests: open-punch today →
  not flagged; open past threshold → flagged; settled missing checkout → still flagged.
  (b) `pb_schedule` renders shift times in UTC — `schedule_grid._pb_hhmm` is a bare
  `strftime('%H:%M')`. Localize to the employee's tz (fallback company tz), matching what
  pb_today/pb_time_hub render (W55/W51 family). Tests: an 08:00 Asia/Ho_Chi_Minh shift renders
  08:00, not 01:00, and the day-column cost strip keys the same local day.
- **WP-1** Cell anatomy v2 + legend + summaries (+ hoot tests: render-state matrix, the
  no-%-in-cells gate, flags/badges still render).
- **WP-2** Cell editor popover + inline warnings + ceiling bar (+ hoot tests: open/edit/stage/
  cancel against a mocked adapter; overlay-service mounting gate).
- **WP-3** Keyboard nav + fill-down + fast-path typing (+ tests), tray consolidation + filter
  chip, Save relocation.
- **WP-4** Live validation on the P6-seeded cohort + screenshots + regression + fixes.

## §5 Tests (with features, W9)

- **T1** Hoot: cell render matrix (empty / hours-only / hours+OT draft / submitted / approved /
  flagged / trip badge), legend from config order, footer sums.
- **T2** Hoot: editor — open on click and Enter, stage regular + OT, Esc discards, Enter stages,
  ceiling bar reflects payload, over-cap shows split preview and never blocks.
- **T3** Hoot: keyboard — arrows, digit fast-path, Tab, Ctrl+D; focus visible (a11y outline).
- **T4** Static gates: no `%` rendering inside cell templates (grep the cell template region);
  W16/W1/W2/W3; popover only via overlay service; W21 on staging/commit paths; adapter contract
  untouched (existing host tests still pass unmodified).
- **T5** Regression: pb_time_hub, pb_hr_workforce suites green (their grid tests may need honest
  updates for the new DOM — update assertions, not behavior); no NEW failures elsewhere.
- **T6–T13 Chrome-MCP live:** before screenshot of the old grid is already on record — capture
  after (`p5_grid.png`, `p5_editor.png`, `p5_legend.png`); on a P6 demo employee: open editor,
  set 8.0 regular + 2.0 OT → tray shows the stage → Save → DB-assert the attendance/OT rows →
  then REVERT via the same editor → DB back to before (residue zero, pasted counts); digit
  fast-path + fill-down live; "only rows with entries" filters; both hosts (lens + standalone)
  render the new grid; Ceilings rail + Submit-all tray intact; trip badge visible on the seeded
  trip days; console clean; a 1440×900 pass (no horizontal surprises beyond the grid's own
  scroller, W39 lesson).
- **T14** Perf sanity: render + first-interaction timing on the seeded cohort vs the P6 baseline
  numbers — no regression beyond noise; paste the numbers.

## §6 Deploy & verify

Ritual per W10 (ssh alias Payobook19v2, apex DB `payobook`, detached systemd-run,
`-u biz_week_grid,pb_hr_workforce,pb_time_hub` + anything touched; version bumps; asset purge
fallback — this is a pure asset phase, expect to need it; W33 tell). Chrome-MCP on
https://payobook.com (/bizapp).

## §7 Report back

Commit hashes per WP; T1–T14 evidence; before/after visual notes; self-review (W0.1); W-rules
appended; deviations + reasons; and anything the P7 design (housekeeping bundle) should know.
