# WORKFORCE P3a — Mission Control, part 1: the workspace shell & lens router

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules through **W34**),
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (mockup B is THE visual target for the shell chrome: top
command bar, left icon rail with lens labels, full-bleed canvas. The right dock, person popover and
⌘K palette in that mockup are **P3b** — leave visual room for the dock, don't build it).
Prior phase: P2's P3-grounding facts are §2 below — verified, do not re-derive.

## §1 Scope

New module **`pb_mission`** — the single Workforce workspace: a top command bar with the synced
context, an icon rail of **7 lenses** (Today · Schedule · Time · Time Off · Overtime · Trips ·
Approvals) hosting the existing cockpits as embedded guests, and the sidebar flip: the WORKFORCE
section collapses to ONE rail item opening the shell. This phase delivers "stop navigating; stay in
the room" — the ambient layer (Needs-you dock, universal person surface, ⌘K) is P3b.

**Binding non-goals:**
- No dock, no person popover/hovercard, no ⌘K, no pb.team model changes — all P3b.
- No engine work (P4). No rebuild of any lens's internals — cockpits are embedded, not redesigned.
- No deletion of anything: the 7 hub actions stay registered and openable standalone (P1a
  precedent); retired sidebar items go to the 900-band (W18).
- Don't chase the pre-existing failing tests P2 catalogued (pb_timeoff test_05, pb_young_worker
  test_09, pb_learn, pb_payroll_ai_insights, pb_demo, pb_pay_delivery) — they are not yours.
- Deep wf_context adoption inside Time Off / Overtime / Trips / Approvals internals is NOT in
  scope (accepted gap, noted for later): embedding binds only what already exists.

## §2 Verified grounding (P2 report — do not re-derive)

- **Embeddability:** only `PbSchedule` has the W17 `embedded` prop today (`pb_schedule.js:57-64`,
  suppresses `.pbsc-head` at `pb_schedule.xml:11`). `PbTimeHub` is a host with the W26 arrival
  protocol (`props.action.context.pb_lens` / `pb_focus`) — reuse that protocol, don't invent
  another. The other five (`PbToday`, `PbTimeoff`, `PbOtDesk`, `PbTrips`, `PbTeamCockpit`) have
  unconditional heroes; all are exported and declare `"*": true` props, so adding `embedded` is
  additive.
- **Context adoption:** 3 of 7 consume `wf_context` (Today, Schedule, Time). Time Off has a
  private month nav; Overtime a private filter rail with NO department scope; Trips no scoping at
  all (`get_pipeline_data()` takes no args); Team a skip-level toggle only.
- **Scrolling (W20 hazards):** five cockpits are `height:100%` self-scrollers needing a definite
  host box. `PbTimeoff` / `PbOtDesk` / `PbTeamCockpit` make their ROOT the scroller with
  `position:sticky` chrome calibrated to it — under a shell they will mis-stick unless their
  scroller becomes an inner box in embedded mode. `PbTrips` is page-flow (`min-height:100%`).
  Three ship `position:fixed` modals at `z-index:1050` (fine: below overlay 1600).
- **Layout constraints:** `pb_sidebar` + `biz_theme` each xpath-replace `<ActionContainer/>`;
  core's `.o_action` height rules are GONE — height is re-supplied by `pb_sidebar.scss:13-24`
  (flex stretch, `overflow:auto` on `.o_action_manager`). **Below 1920px the biz rail is a 60px
  absolute hover-overlay** (`biz-rail-mode`, z-25, wrapper gains `padding-left:60px`) — the shell
  lives inside the action container so it inherits that inset; never place fixed-left chrome that
  assumes x=0. `.o-overlay-container` is z-1600. Sidebar active-item matching is strict
  `xml_id → tag → res_model` with last-writer-wins — with ONE Workforce item this is a non-issue.
  The sidebar icon set is a fixed 32-key inline list; unknown names silently render a circle.
- **Sidebar state (post-P2):** WORKFORCE rail = 7 active items (Today 10 … Team Approvals 70),
  all their data files noupdate 0 (W13/W27 history). Retired band at 900 already holds 8 items.

## §3 Design decisions (binding)

1. **Module `pb_mission`** (deps: `pb_wf_kit`, `pb_import_kit`, `pb_today`, `pb_schedule`,
   `pb_time_hub`, `pb_timeoff`, `pb_hr_workforce`, `pb_business_trip`, `pb_team`). One client
   action, tag **`pb_workforce`**, its own xmlid. No new backend models — the shell is chrome;
   any RPC it needs already exists.
2. **Shell anatomy (mockup B):** top command bar (brand "Workforce", a search input that is a
   PLACEHOLDER for P3b's ⌘K — renders, focuses, and filters nothing yet beyond triggering the
   person typeahead already in `WfContextBar`; simplest: mount the context bar's segments in the
   command bar), context chips (dept + day/week per-lens), user avatar (session user, no menu).
   Left icon rail: 76px, icon + small uppercase label per lens, active = soft-indigo per mockup B;
   bottom slot "Rules" linking nothing yet (disabled ghost, P4 territory) — or omit it. Canvas:
   the embedded lens in a **definite-height flex box** (W20). Right edge: reserve nothing visible
   (the dock arrives in P3b; no empty gutter).
3. **Lens map:** `today→PbToday` (context features dept/day/search), `schedule→PbSchedule`
   (dept/week/search), `time→PbTimeHub` (dept/week/search), `timeoff→PbTimeoff` (search only),
   `overtime→PbOtDesk` (search only), `trips→PbTrips` (search only), `approvals→PbTeamCockpit`
   (search only). The shell owns ONE `WfContextBar` instance in the command bar; a per-lens
   feature map shows/hides segments. Lens switch preserves context (that's the whole point);
   remount lenses on switch (simple `t-key` remount is fine — no state-cache ambitions in P3a).
4. **Embeddability sweep (the five):** add the W17 `embedded` prop — suppresses the hero/private
   context chrome, turns the ROOT-scroller cockpits into inner-box scrollers in embedded mode so
   their sticky chrome sticks correctly (P2's warning), accepts the host's height box. Standalone
   rendering must stay byte-identical (default `embedded:false`; prove it like P1a's T9).
   `PbTimeoff`'s private month nav STAYS (it's its own dimension); `PbOtDesk`/`PbTrips` filters
   stay. Team cockpit's hero collapses to its queue + roster (its "MY TEAM" hero text is already
   renamed "Team Approvals" from P2).
5. **Arrival routing (W26):** the shell action reads `context.pb_shell_lens` (default `today`)
   and forwards `pb_lens`/`pb_focus` to the Time hub exactly as `PbTimeHub` already understands;
   Today's File-correction deep-link must now land INSIDE the shell (Today is embedded → its
   navigation to the Time hub becomes a lens switch + forwarded context, not a doAction to a
   separate action — do this via a host-provided callback prop, W17-style, with the standalone
   fallback keeping the old doAction path).
6. **Sidebar flip:** retire the 7 hub items to the 900-band (`active=False`, W18; all files
   unfrozen). New single item **"Workforce"** (icon `compass` — already in the fixed set), seq 10,
   in `pb_mission`'s own data file (noupdate 0), pointing at the shell's action xmlid. W28 check
   against all rail labels. DB-assert everything (W13.1).
7. **Z/height discipline:** shell chrome z ≤ 20 (under the 60px biz rail overlay at z-25); lens
   modals at 1050 keep working; nothing fixed to viewport-left. Shell root fills the action
   container per §2's height chain; every lens box is definite-height (W20).
8. **The 6 retired standalone actions + Time hub remain registered** — smoke-test one of them
   standalone after the flip.

## §4 Work packages (one commit each)

- **WP-1** Embeddability sweep: `embedded` prop on the five cockpits (+ static gate test: all 7
  lens components accept `embedded`; standalone default unchanged).
- **WP-2** `pb_mission` shell: command bar + icon rail + lens router + context feature map +
  definite-height canvas + W26 arrival routing + the Today→Time in-shell hand-off callback.
- **WP-3** Sidebar flip: one "Workforce" item, 7 retired, DB-asserts, W28 label gate.
- **WP-4** Chrome validation choreography + screenshots + regression sweep + any fixes it forces.

## §5 Tests (with features, W9; scoped `-u` always)

- **T1** Static: every lens component accepts `embedded`; W16 grep; no invented hex/gradient/FA/
  emoji in `pb_mission`; shell z-values ≤ 20 (grep the scss).
- **T2** Sidebar DB-asserts after `-u`: WORKFORCE section = exactly 1 active item ("Workforce",
  seq 10, shell xmlid), the 7 at 900-band inactive, retired total = 15, label unique DB-wide.
- **T3** Regression suites all green: pb_schedule 112 · pb_today 44 · pb_time_hub 30 ·
  pb_hr_workforce 36 · pb_attendance_flow 29 · pb_team 10 · pb_wf_kit 5 (+ pb_timeoff's suite
  minus its pre-existing failure — assert no NEW failures, W-note it).
- **T4–T14 Chrome-MCP live (https://payobook.com, /bizapp/action-pb_workforce):**
  - Shell renders with the Today lens; screenshot `p3a_shell_today.png`.
  - All 7 lenses switch; console clean on every switch (×2 cycles); screenshots per lens
    (`p3a_lens_<name>.png`).
  - Context persistence: set dept + week in Schedule lens → switch to Time lens → same dept/week;
    switch to Today → same dept, day intact; SQL-free assertion via the visible chips.
  - Today→Time hand-off: a late row's File-correction lands on the Time lens INSIDE the shell,
    Exceptions view, person chip set (P1b's T8 semantics, now shell-internal).
  - Sticky-chrome check on the three former root-scrollers embedded (scroll the Time Off lens —
    its sticky header sticks at the lens box top, not mid-air).
  - Resize to 1440×900 (biz rail overlay mode): shell not clobbered by the 60px rail; hover the
    rail → overlay paints OVER the shell (z-25 vs ≤20); screenshot `p3a_1440_rail_overlay.png`.
  - A lens modal (Schedule quick-create) opens above shell chrome; cancel, no write.
  - Standalone proofs: `/bizapp/action-pb_schedule` AND `/bizapp/action-pb_today` still render
    un-embedded with their own heroes (P1a T9 pattern).
  - New sidebar: one Workforce item, correct icon, opens the shell; retired items absent;
    screenshot `p3a_rail.png`.
- **T15** Residue zero (no test writes should exist at all in this phase — assert the usual tables
  unchanged).

## §6 Deploy & verify

Ritual per W10 (ssh alias Payobook19v2, apex DB `payobook`, detached systemd-run,
`-i pb_mission -u pb_wf_kit,pb_today,pb_schedule,pb_time_hub,pb_timeoff,pb_hr_workforce,pb_business_trip,pb_team,pb_sidebar`,
asset purge fallback, no bare pkill, no daemon-reload). Version bumps everywhere touched.
Chrome-MCP on https://payobook.com.

## §7 Report back

Commit hashes per WP; T1–T15 evidence; self-review notes (W0.1); W-rules appended; deviations +
reasons; and open questions for the **P3b design (the ambient layer: Needs-you dock fed by
`pb.team.get_team_data` + `act` with the four catalogued gaps to close [total when has_team=false,
ISO `when`, uncapped searches, manager-only scope], the universal person surface [drawer-first,
RPC-free hovercard], and the ⌘K palette [lenses · people · actions])** — in particular report:
where in the shell the dock should mount (your real DOM), any lens whose embedded mode fights a
right-side panel, and what the command-bar search currently does so P3b can take it over cleanly.
