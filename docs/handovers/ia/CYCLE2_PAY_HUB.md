# IA Redesign — Cycle 2: the Pay Run hub

Program: Option A "Six Missions" (mockup: `docs/PAYOBOOK_IA_REDESIGN_OPTIONS.html`, Option A demo → Pay Run hub).
Prior cycle: C1 shipped `pb_hub` (shell kit + global ⌘K) — commits 7eb2ccf2…345aa005; its report is summarized below. Conventions: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` is binding — it now runs to **W89** after the other session's Wave 2; re-read it fully, especially W68 (shared server), W73 (hotkey one-winner), W74 (adjacent-string bundle blanking), W75 (headless CDP validation).

## Task 0 — finish C1's deferred browser pass
One pass that server contention blocked last night: in the demo hub (`pb_hub.action_pb_hub_demo`), verify (a) the back chip renders when arriving with `pb_back` context via `openHub` and navigates back correctly; (b) a rapid double ⌘K press produces exactly one overlay (the `opening` race flag from commit ae28b584). Evidence, then move on.

## Scope
Build the **Pay Run hub** — one client action that absorbs the eight PAY RUN surfaces as lenses on the C1 `HubShell`, kills the ledger native-list escapes, and lights up the period tracker with real data. Reachable only via a ⌘K preview entry this cycle (rail cutover is C5; the old rail items keep working unchanged).

### Binding non-goals
- NO rail/sidebar data changes (C5). NO Integrations one-door work (C3) — the Import cockpit keeps its current tiles this cycle. NO Home hub, NO Payroll Report (C4). NO Planning changes. Do not refactor pb_mission. Do not modify the eight cockpits' standalone behavior — they must keep working exactly as today when opened from the current rail.

## C1 API you build on (verbatim — do not re-derive)
- `@pb_hub/js/hub_shell`: `HubShell` props `{config, action?, slots?}`; `config = {key, brand:{label,icon}, lenses:[{key,icon,label,groups?,Component?,props?,wantsArrival?}], dock?, tracker?:{label,stage,total,onClick?}, cog?, defaultLens?}`; lens components receive `{embedded:true, ...lens.props}` and `arrival:{lens,focus}` only if `wantsArrival`.
- `@pb_hub/js/hub_nav`: `openHub(actionService, {tag|xmlid, lens, lensKey="pb_lens", focus, back:{label,tag|xmlid,lens,lensKey}, context, clearBreadcrumbs})`; `HubBackChip`.
- `@pb_hub/js/hub_tracker`: `HubTracker {label, stage?, total?, onClick?}`.
- Palette registries: `pb_hub_palette` entries `{id,label,sublabel,icon,group:"Surfaces"|"Admin",action:{tag|xmlid,lens,lensKey},groups?,requires?}`; `pb_hub_palette_yield` (CSS root selectors that make the global palette yield).
- Gotcha inherited from C1: pb_mission reads `pb_shell_lens`, not `pb_lens` — for the NEW pay hub just use the default `pb_lens`.

## Verified plumbing facts (audit, re-verify line numbers only if an edit lands there)
The eight surfaces and their owners:
1. **Run** — `pb_payrun_wizard` client action tag `pb_payrun_wizard` (`views/pb_payrun_wizard_action.xml:3`, `static/src/js/payrun_wizard.js:184`): bespoke 3-step full-page wizard, chunked compute progress. Known warts: overwrite guard uses stock `ConfirmationDialog` (`payrun_wizard.js:135–164`); terminal CTA `openRun()` (`:173–180`) dumps into the native `hr.payslip.run` form.
2. **Runs** — rail currently points at `pb_payruns.action_pb_payruns_kanban` = native act_window on `hr.payslip.run` `kanban,list,form` (`views/hr_payslip_run_kanban.xml:90–96`, js_class `pb_payruns_kanban`, KPI band injected `static/src/js/payruns_kanban.js:190–193`). **An orphaned bespoke cockpit exists**: client action `action_pb_payruns` / `payruns.js:118` — nothing points at it. Revive it as the Runs lens (assess its state first; finish/polish as needed to at least match the kanban's information).
3. **Payslips** — `pb_payslip_review` tag `pb_payslip_review` (`payslip_review.js:73`): WOW, zero escapes.
4. **Results** — `pb_payrun_results` tag `pb_payrun_results` (`payrun_results.js:304`): WOW; XLSX export `:272–295`; row drill to native payslip form `:236–244` (keep — payslip form is VU-skinned).
5. **Import** — `pb_import` tag `pb_import` (`import.js:109`); launch tiles are server-driven xmlids (`pb_import/models/pb_import.py:24–35`) — unchanged this cycle.
6. **Deliver** — `pb_pay_delivery` tag `pb_pay_delivery` (`pb_pay_delivery.js:203`): WOW; one employee-form deep link `:187–198` (keep).
7+8. **Adjust & Settle** — `pb_payrun_ledgers` generic descriptor cockpit (`js/ledger.js:142–146` registers tags `pb_fullfinal`/`pb_proration`/`pb_retro`; descriptors `models/ledger_cockpits.py:113,171,231`). Escapes to kill IN THE LENS: row click → native forms (`ledger.js:120–126,137–139`); "Open full list →" → `pb_hr_fullandfinal.action_full_and_final_employees` (`full_and_final_views.xml:145–151`), `pb_hr_payroll_formula.action_payroll_proration_line` (`payroll_proration_views.xml:90–95`), `…action_payroll_retro_adjustment` (`payroll_retro_views.xml:79–84`).
- Drawer to clone for row detail: `pb_wf_kit` WfDrawer — `wf_kit.xml:87–106`, `wf_kit.scss:169–235` (320px slide-in, absolute scrim inside canvas, ESC closes).
- Embedded-cockpit precedent: `pb_today.xml:14` suppresses its own title when `props.embedded`; `pb_mission.xml:82–113` mounts with `embedded="true"`.

## Architecture
New module **`pb_payhub`** (depends `pb_hub`, `pb_payrun_wizard`, `pb_payruns`, `pb_payslip_review`, `pb_payrun_results`, `pb_import`, `pb_pay_delivery`, `pb_payrun_ledgers`):
1. Client action tag **`pb_pay_hub`** (xmlid `pb_payhub.action_pb_pay_hub`, no menu, no sidebar item) rendering `HubShell` with `key:"pay"`, brand `{label:"Pay Run", icon:"zap"}` and lenses in this exact order/naming (mockup spec): `run(zap) · runs(calendar) · payslips(receipt) · results(table) · import(download) · deliver(send) · adjust(percent) · settle(file)`.
2. **Embedded mode per cockpit**: add a `pb_today`-style `embedded` prop to each mounted cockpit — suppress only the redundant page-title/brand row, keep functional toolbars; padding tightens. Standalone rendering must remain pixel-identical (guard everything behind `props.embedded`; make `embedded` optional in each cockpit's props schema).
3. **Adjust lens** = the ledger component in a new in-lens mode: tabs **Retro | Proration** (two descriptors in one lens), grid in-cockpit, row click opens a WfDrawer-style 320px drawer with the line's full story (fields per descriptor) instead of navigating; "Open full list →" **not rendered** in hub mode. Standalone `pb_proration`/`pb_retro` actions keep today's behavior.
4. **Settle lens** = same in-lens ledger mode for full & final.
5. **Period tracker**: server model/method `pb.pay.hub` `get_period_state()` → `{label:"Aug 2026", stage:1..5, total:5}` for the current calendar month, heuristic mapped to REAL `hr.payslip.run`/payslip states — verify the actual state field values in `om_hr_payroll` (+ approval states used by `pb_approval`) and document the mapping in the module README + report. Suggested: 1 none yet · 2 draft/computing · 3 awaiting approval/exceptions · 4 approved, delivery pending · 5 delivered/closed. Wire into `config.tracker`; `onClick` switches to the stage-appropriate lens (2→run/runs, 3→payslips, 4→deliver, 5→runs).
6. **⌘K preview entry**: one `pb_hub_palette` entry "Pay Run Hub (preview)" (group "Surfaces", gated `om_hr_payroll.group_hr_payroll_user` or the closest real payroll-user group — verify what exists) opening tag `pb_pay_hub`. Plus per-lens sub-entries mirroring the Mission Control pattern (sublabel "Pay Run Hub").
7. Wizard terminal CTA: when embedded in the hub, `openRun()` should stay in-hub — switch to the **runs** lens focused on the new run (`arrival.focus = run id`, Runs lens honors `wantsArrival`). Standalone wizard behavior unchanged.

## Safety rails
- Demo data: REUSE the persistent demo payroll schemes/fixtures on the dev DB for any run you compute — never create/destroy throwaway ZZ records.
- W68 shared-server rule still binding: if the other session's server/tests are running, yield exactly as C1 did.
- One accent #5A4BB0, no gradients, `ic()` icons only, tabular-nums on numbers. No `window.confirm`. `.pbph-*` class prefix for new SCSS.
- Assets cache: bump/regenerate after JS changes (W74/W75 rituals for validation).
- All eight standalone actions must remain byte-for-byte functional — the hub is additive until C5.

## Tests (run all, paste evidence)
1. Task 0 evidence (back chip + double-⌘K).
2. `pb_payhub` installs; ⌘K → "Pay Run Hub (preview)" opens the hub; 8 lenses in spec order; lens choice persists (`pbhub.pay.lens.v1`).
3. Each lens mounts its cockpit with no duplicated title row and no console errors (screenshot or DOM assert per lens).
4. Run lens: complete a draft run on the demo scheme (period = current month) — progress UI works embedded; terminal CTA lands on the Runs lens with the new run focused, NOT the native form.
5. Runs lens (revived cockpit): shows the runs incl. the new draft with at least state + count + net info parity vs the kanban; opening a run from it still reaches the (VU-skinned) run form.
6. Adjust lens: Retro/Proration tabs render real demo rows; row click opens the drawer (no navigation); drawer ESC/X closes; "Open full list" absent in hub, still present standalone.
7. Settle lens: same assertions for full & final.
8. Tracker chip shows the computed stage for the current month and the mapping matches the documented heuristic (manufacture at least two different stages on the demo DB to prove it moves, using existing fixtures).
9. Standalone regression: old rail items Run Payroll / Pay Runs / Payslips / Results / Import / Pay & Deliver / Full & Final / Proration / Retro all open and behave exactly as before (smoke each).
10. Global ⌘K still yields correctly in Mission Control & Formula Studio; works inside the Pay hub (opens global palette — the pay hub declares no local palette).
11. Unit tests: keep C1's 30 green; add pb_payhub tests (period-state heuristic at minimum — pure-python cases for each stage) — all green in one run.
12. Server log clean after upgrades; no missing-asset 404s.

## Self-review (mandatory — you are the only reviewer)
Diff-read every file against this spec; verify no cockpit's standalone template changed rendering when `embedded` is falsy (git diff the templates and reason each hunk); check drawer z-index vs the hub shell's discipline (pb_mission.scss:12–16 precedent); confirm palette entry gating; re-run affected tests after fixes.

## Commits (per feature, explicit staging, do NOT push)
Suggested: (1) feat(pb_payhub): hub action + shell config + embedded modes; (2) feat(pb_payrun_ledgers): in-lens ledger mode + drawer; (3) feat(pb_payhub): period tracker + heuristic + tests; (4) feat(pb_payruns): revive cockpit as Runs lens; (5) docs: ledger additions. Adjust as reality dictates.

## Report back
- Lens-by-lens: what embedded mode changed per cockpit (file refs).
- The revived Runs cockpit: what state you found it in, what you added.
- Period-state mapping table (state values → stage) as implemented.
- Drawer field sets chosen for retro/proration/full-final rows.
- Test evidence 1–12, commit hashes, deviations + why, new W-ledger entries.
