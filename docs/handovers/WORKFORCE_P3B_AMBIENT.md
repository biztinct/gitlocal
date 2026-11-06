# WORKFORCE P3b — Mission Control, part 2: the ambient layer (dock · person surface · ⌘K)

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules through **W40**),
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (mockup B's right dock, person popover and ⌘K are the
visual targets — the popover is realized as the shared drawer + a small dock hovercard, see §3.4).
Prior phase: P3a's grounding (§2) is measured fact — do not re-derive.

## §1 Scope

Three ambient capabilities inside the P3a shell: the persistent **Needs-you dock** (the five-inbox
problem dissolves), the **shell-wide person surface** (any personId from any lens/palette/dock gets
a drawer, everywhere), and the **⌘K palette** (lenses · people · actions). Plus two small closures:
`pb.team` payload gaps and the redundant rail label.

**Binding non-goals:**
- No engine work: no tolerances, no locks, no "clean batch" auto-approval — the dock's "N clean,
  approve all" moment is P4, when tolerance data exists. The dock ships without it.
- No approval-LOGIC changes: the dock calls `pb.team.act` which acts AS THE REAL USER through each
  model's own gated action (C18.63 heritage). Never sudo a mutation (W12).
- No redesign of lens internals beyond the lens-capability flag (§3.4) and trivial pb_cmd handlers
  (§3.5). No mobile work. Don't chase the six pre-existing failing tests.

## §2 Verified grounding (P3a report — measured live)

- **Dock mount:** third flex child of `.pbms-low` (`display:flex; flex:1 1 auto; min-height:0`),
  `flex: 0 0 268px`, **no z-index** (W37); measured with a 268px probe: zero horizontal overflow in
  all 7 lenses at 1920 and 1440. If it must float on narrow screens: `position:absolute` inside
  `.pbms-low`, z ≤ 20.
- **Command-bar search today:** the `WfContextBar` `person` segment — ≥2 chars, 220ms debounce,
  `hr.employee.name_search(name, domain:[], operator:"ilike", limit:8)`, menu at z-40 inside the
  z-2 `.pbms-top` stacking context. Picking calls `wf_context.set({personId})`. It does NOT search
  lenses/actions. The palette REPLACES this segment (keep `set({personId})` as the jump outcome).
- **Two live search facts:** (a) the DB has **no `unaccent`** — "Bui Anh" matches nothing,
  "Bùi Anh" matches; (b) picking a person `pb.time.hub.get_person_week` can't resolve makes Today
  clear the pin with a warning toast — on-pick graceful failure is the pattern (don't pre-filter
  expensively).
- **`pb.team.get_team_data`** returns dock-ready `queues.items[]` (10 uniform keys incl. `model`,
  `res_id`, `source` ∈ ot/trip/correction/leave, `employee{...}`, `can_approve/can_refuse`) +
  `queues.counts`; `pb.team.act(model, res_id, action, note)` is the mutation door (whitelisted,
  real-user, refusals → caught → toast). **Four gaps:** `total` missing when `has_team` is false;
  `when` is display-only (no ISO); the four searches are UNCAPPED; scope is manager-only
  (`parent_id = me`) so an HR user with no reports sees an empty queue.
- **Person-drawer inventory:** Time, Today and Schedule lenses own a `WfPersonWeek` drawer already;
  Time Off, Overtime, Trips, Approvals have none.
- **Refuse-with-note precedent:** the Team cockpit's queue refuse opens a note box (required note);
  reuse those semantics in the dock.
- **Rail redundancy:** sidebar reads "WORKFORCE › Workforce" (one item). Formula Studio owns the
  name "Command Center" (its ⌘K); don't reuse that label.

## §3 Design decisions (binding)

1. **`pb.team` additive fixes (no shape breaks):** always return `total` (0 with `has_team:false`);
   add `when_iso` (ISO 8601) beside the display `when`; cap each source search at 20 with TRUE
   totals in `queues.counts` + `has_more` per source; add `scope='team'|'org'` — `org` gated
   server-side to HR manager | payroll manager (`_require_org_approver`), reads sudo under that
   gate (C18.65 one-permission-world precedent), mutations still real-user via `act`. Dock offers
   the Team/Org toggle only when the server says the user qualifies (payload flag `can_org`).
2. **Dock (`pb_mission`):** 268px column per §2; header "Needs you · N" (true total); source-tinted
   cards (P0's semantic map: ot amber, trip indigo, correction blue, leave green) with employee,
   subtitle, age; inline ✓ approve and ✗ refuse-with-required-note; every write ONLY from click
   handlers (W21), refresh after each act; 60s read-only poll; collapsible to a 44px badge strip
   (state in localStorage `pbwf.dock.v1`; starts collapsed below 1280px); card employee click →
   person surface; per-source "+N more" and footer "Open full queue →" → Approvals lens; empty
   states: all-clear (green check moment) and no-team (explain + Org toggle if `can_org`).
3. **Shell person surface:** the shell renders ONE `WfPersonWeek` drawer overlaying the canvas
   when `personId` is set AND the active lens does not own a drawer. Lens map gains
   `ownsPersonDrawer: true` for time/today/schedule (those keep their behavior; no double drawers).
   Drawer close clears `personId`. Unresolvable person → toast + clear (the §2 pattern).
4. **Dock hovercard (RPC-free):** hovering a dock card shows a small card from data already in the
   payload (name, job, source, when) with "Open person" — no RPC, no new endpoint. This is the
   whole "popover" for P3b; anything richer belongs to later polish.
5. **⌘K palette (`WfCommandPalette` in `pb_wf_kit`, W6):** opened by ⌘K/Ctrl-K (hotkey scoped to
   the shell) and by clicking the command-bar search (which this replaces; the `person` feature of
   `WfContextBar` stays for standalone cockpits). Render through the Odoo overlay service (lives in
   `.o-overlay-container` z-1600 — no shell z games, W37 untouched). Three groups: **Lenses** (7,
   icons, instant), **People** (the same debounced name_search; empty-state hint mentions
   diacritics per §2a; on-pick `set({personId})` → person surface), **Actions** (static registry:
   New shift → schedule + `pb_cmd:'quick_create'`; Copy week → schedule + `pb_cmd:'copy_week'`;
   Set budget → schedule + `pb_cmd:'set_budget'`; Import punches → time + `pb_lens:'import'`;
   File correction → time + `pb_lens:'exceptions'`; Open map → today + `pb_cmd:'map'`; Apply time
   off on behalf → timeoff + `pb_cmd:'apply'`; Bonus review → overtime + `pb_cmd:'bonus'`).
   Keyboard: arrows/enter/esc; last-5 recents in localStorage `pbwf.palette.v1`.
6. **`pb_cmd` protocol (W26 extension):** the shell forwards `pb_cmd` to the lens as a prop, ONCE
   (consumed on mount/update, cleared after). Implement handlers ONLY where the target affordance
   already exists (schedule quick-create/copy-week/budget dialogs; time initial views via pb_lens;
   today map view; timeoff apply button; overtime bonus view). A lens ignoring an unknown pb_cmd
   is correct behavior. Document the registry in the conventions ledger (append to W26).
7. **Rail label:** rename the single item "Workforce" → **"Mission Control"** (data-only; W28
   check DB-wide). The section header stays WORKFORCE — "WORKFORCE › Mission Control" reads as
   intended, not redundant.

## §4 Work packages (one commit each)

- **WP-1** `pb.team` additive payload fixes + org scope (+ server tests).
- **WP-2** Dock in `pb_mission` (+ hovercard) wired to WP-1; collapse/poll/empty states.
- **WP-3** Shell person surface (lens capability map + shared drawer + toast-and-clear).
- **WP-4** `WfCommandPalette` in kit + shell wiring + `pb_cmd` protocol + the trivial lens
  handlers + command-bar takeover (standalone cockpits keep the old person segment).
- **WP-5** Rail rename + full validation choreography + screenshots + regression.

## §5 Tests (with features, W9; scoped `-u` always)

- **T1** `pb.team` tests: total always present; `when_iso` parses ISO; caps honored with true
  counts + `has_more`; `scope='org'` refused for a plain manager, allowed for HR/payroll manager;
  org reads return other managers' teams' items; `act` still refuses what the real user can't do.
- **T2** Static gates: W16/W2/W3 on all touched modules; palette + dock z discipline (dock has NO
  z-index; palette only via overlay service); W21 gate — no ORM writes reachable from dock/palette
  lifecycle hooks (extend the P1a grep).
- **T3** Regression: all suites green, no NEW failures vs the catalogued six (pb_mission 30+,
  pb_team, pb_wf_kit, pb_schedule 111, pb_today 41, pb_time_hub 31, pb_hr_workforce 36,
  pb_attendance_flow 29).
- **T4–T15 Chrome-MCP live:** dock renders with real pending counts (SQL cross-check the total);
  seed ONE OT request via the weekentry seam (P1a T8 precedent) → appears in dock → inline approve
  → state `approved` in DB → then delete request + its attendance rows, prove residue zero; second
  seeded item → refuse requires a note → refusal recorded → clean up; Org toggle visible as admin,
  switches counts (SQL cross-check); collapse persists across reload; card employee → person
  surface; hovercard renders without any network call (assert via the network log); on the Trips
  lens set a person from ⌘K → the SHELL drawer opens (screenshot `p3b_shell_drawer_trips.png`);
  on the Time lens the lens's OWN drawer still opens (no double drawer); ⌘K: opens by hotkey and
  by clicking the bar; lens jump; person jump; action "New shift" lands on Schedule with the
  quick-create open (cancel, no write); action "Import punches" lands on Time·Import; recents
  populate; esc closes; unresolvable person → toast + pin cleared; rail shows "Mission Control"
  (`p3b_rail.png`); dock screenshots expanded/collapsed/all-clear (`p3b_dock_*.png`); console
  clean throughout.
- **T16** Residue zero across `hr_overtime_request`, `hr_attendance`, `hr_attendance_correction`,
  `pb_business_trip`, `hr_leave`, mail queue (before/after counts pasted).

## §6 Deploy & verify

Ritual per W10 (ssh alias Payobook19v2, apex DB `payobook`, detached systemd-run,
`-u pb_wf_kit,pb_mission,pb_team,pb_time_hub,pb_today,pb_schedule,pb_timeoff,pb_hr_workforce,pb_sidebar`
— add anything else you touch; no `-i`), version bumps everywhere touched, asset purge fallback,
W33 tell (missing "Starting post tests" = partial commit), Chrome-MCP on https://payobook.com
(backend prefix /bizapp).

## §7 Report back

Commit hashes per WP; T1–T16 evidence; self-review notes (W0.1); W-rules appended; deviations +
reasons; and open questions for the **P4 design (the engine: tolerance-based auto-approval feeding
the dock's clean batch; day/week locks + the Close-the-week ritual handing a clean week to the pay
run; employee shift acknowledgment; shift-end pulse)**. For P4 grounding, report: where payroll
runs read attendance today (the pb_workforce_payroll_bridge seams and `_get_formula_input_values`
override chain), what `hr.attendance` correction/exception state machines allow post-hoc edits,
the `compliance_status` staleness question from P1b (recompute trigger vs live derivation — P4
must decide), and any existing acknowledgment/notification plumbing (bus, mail templates, the
driver PWA's service worker) a shift-ack flow could ride on.
