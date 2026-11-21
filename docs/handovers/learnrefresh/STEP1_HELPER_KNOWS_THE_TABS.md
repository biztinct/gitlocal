# LEARN REFRESH — Step 1: the helper knows every tab

Read first: `docs/handovers/learnrefresh/LEARN_REFRESH_LEDGER.md` (binding rules, product
map, pipeline, deploy). Do not re-derive anything it states.

## Why

Since the 2026-08-19 rail cutover every screen lives as a TAB (lens) inside a hub. The
helper decides "which screen am I on" from the current action's tag / xml-id / model
(`pb_learn/static/src/coach/coach.js` `_resolveScreen` ~:311). Inside a hub the action
is the hub (`pb_pay_hub`, `pb_home_hub` …), so the helper finds nothing and says it
has no content on nearly every screen. Every "Show me" / walkthrough / practice-task
navigation also opens the OLD standalone cockpits by xml-id, outside the new rail.

## Scope

1. **A "where am I" signal from both shells.** Publish the active hub + lens from
   `pb_hub` HubShell and from `pb_mission`'s shell whenever the lens changes (arrival,
   restore, click, programmatic `setLens`) and when the hub unmounts (clear it). Pick
   the seam: a small exported reactive store in pb_hub (e.g. `hub_place.js`:
   `{tag, lens, hubKey}`) that pb_mission imports and pb_learn reads (check the manifest
   dependency graph: pb_learn's `learn_hub.js` already imports HubShell — confirm pb_hub
   is reachable in its depends; pb_mission must depend on pb_hub or use the same
   store through a module both can import). Also include sub-tabs where a lens has
   inner tabs the learner would see as different screens (Pay Run › Adjust › Retro vs
   Proration; Settle › Full & Final) if the lens exposes that cheaply — otherwise the
   lens level is enough; say which in the report.
2. **Coach resolution learns lenses.** Screens in content get an optional
   `places: ["<hub action tag>:<lens key>", …]` matcher (author field in data.js,
   carried through `gen_learn_data.py` and the server bundle). `_resolveScreen` gains
   a FIRST pass: when a hub place is published and the current action is that hub,
   match `places`. Keep the existing passes for standalone actions and native
   list/forms. Re-resolve when the place changes (not only on action change).
3. **Map the 19 existing screens to their places** (ledger "Old name → where it lives
   now"). Contracts now lives inside People › Employees (drawer) — map by model too so
   the drawer/contract form still grounds.
4. **Hub-level orientation for all 9 hubs + every uncovered lens.** When on a hub tab
   that has no lesson screen yet, the helper must still say something true and useful
   — never "no content". Author, in data.js, one short orientation screen per hub
   (Home, Pay Run, People, Lifecycle, Workforce, Insights, Compliance, Learn, Settings):
   what this page is for (1–2 sentences), its tabs in order with one plain line each,
   and the 1–3 things people most often do here, each with a "Take me there" that
   switches tab. These are orientation, not lessons — steps 2–4 write the lessons.
   EN + VI. Every tab name and line must be read from the current lens definitions
   (labels, groups, probes). A tab the user cannot see must not be listed for them —
   the helper filters by the same visibility the shell uses (reuse, don't copy).
5. **Navigation goes through hubs.** Every learner-facing "open the real screen":
   station "Open" on the Learn map, helper "Show me"/"Take me there", scenario
   `entry.nav` and per-step navigation (`pb_learn/static/src/scenario/scenario_service.js`
   `navigate` ~:163), live mission navigation (`pb_learn/static/src/live/live_mission.js`
   ~:242-252), ⌘K lesson rows' "open the screen", and PayAI's "Show me" hand-off —
   opens hub › lens via `openHub` (pb_mission lenses with `lensKey: "pb_shell_lens"`).
   One helper function in pb_learn owns the station → place map (read from content, not
   hard-coded twice). Anchors must still resolve after navigation: verify each anchor
   the existing scenarios use is rendered inside the embedded lens (cockpits guard some
   chrome with `t-if="!props.embedded"`); where an anchor is lost only because of the
   embedded guard, move the `data-coach` to an element that renders in both modes. List
   every anchor you could not keep in the report (step 2 rewrites approvals/formula
   content anyway).
   **Fix the known stall** while here: a Watch walkthrough that cannot open its screen
   (no access) currently freezes on step 1 with the overlay stuck "navigating". It must
   end with a plain sentence ("You don't have access to <tab>. Ask your administrator,
   or try this lesson in the practice company.") and a Try-in-practice button.
6. **Ask Payobook knows where you are.** `pb_payroll_ai_insights/models/payroll_ai_engine.py`
   `_SCREEN_NAMES` (~:705-725) only knows 5 old tags. Make the screen name come from
   hub + lens (the client already sends context — find how; add the lens). Plain names
   ("the Payslips tab in Pay Run"). Do NOT rewrite its product-knowledge prompt (~:158-181)
   — that is step 2 — but add nothing that contradicts the new rail.
7. **Anchor registry catches up** (`pb_learn/static/src/anchors.json`,
   `pb_learn/tests/test_anchor_registry.py` tests 01 + 05): register the undeclared
   live anchors (`pw-scheme`, `dash-period`, `ex-trail`, `ex-when`, and any others test 05
   lists after your changes). For anchors that no longer exist in the product
   (`pa-hero`, `pa-kpis`, `pa-lanes`, `pa-reject`, `pa-recent`, `fs-simulate`): content
   still points at them until step 2. Mark them `retired: true` in the registry (or the
   equivalent the test understands) so test 01 passes and the contract checker flags
   content that still uses a retired anchor as a WARNING that step 2 must clear — do
   not delete the content in step 1.

## Non-goals (binding)

- No lesson rewrites (steps 2–5). No practice-company (replica) changes. No new
  stations. No role-path changes. Do not touch Ask Payobook's product prompt text.
- Do not change hub behaviour visible to users other than publishing the place signal.
- Do not re-point `sidebar_key` (the retired rail items stay the reach index, see
  `learn_runtime.py` ~:244 comment) unless you find it blocks the work — then explain.

## Design

Bar (owner's words, verbatim): **"extreme WOW, intuitive, out-of-this-world experience,
best in class."** Hero moment for this step: **open the helper on any tab in the app and
it already knows where you are** — header reads "On: Pay Run › Payslips", with a
one-line plain description and the next useful thing. Tab switch while the drawer is
open → header and content cross-fade to the new tab (≤200 ms, respects Reduce motion).
Orientation card lists the hub's tabs as a compact vertical list with the current tab
highlighted; "Take me there" switches tab without closing the helper. Zero dead-ends:
no-access, loading, content-failed and "tab with no lesson yet" states each have a
designed sentence and next step. Lucide icons only. Phone width works.

## Test cases (run all, report each)

1. Home › Pulse, Home › Approvals, Pay Run › Run / Runs / Payslips / Import / Adjust /
   Settle, People › Employees (+ open a contract drawer), Settings (category page),
   Insights › Explorer, Compliance › Filings, Workforce › Today, Lifecycle › Hiring,
   Learn › Lessons: open the helper → header names hub › tab; content is the right
   lesson screen or the hub orientation. No "no content" anywhere on a hub.
2. Switch tabs with the drawer open → helper follows within one frame of the lens change.
3. Reload on a hub (lens restored from storage) → helper correct without clicking.
4. Workforce (pb_mission) lens switch → helper follows (proves the second shell publishes).
5. Learn map → station "Open" for payslips → lands on Pay Run › Payslips (hub rail
   visible), not the standalone cockpit.
6. Walkthrough Watch for sc_payslips and sc_payrun as the demo login → navigates into
   the hub tab; every step's anchor highlights (list any that fall back to a centred card).
7. Same walkthrough as the QA login (no pay-run access) → ends with the plain no-access
   sentence + Try-in-practice; overlay not stuck.
8. Practice task mL1 "open" step → lands on Pay Run › Run.
9. Ask Payobook tab on Pay Run › Payslips: ask "what is this page?" → answer names the
   Payslips tab in Pay Run.
10. A hub tab hidden for the user (e.g. Hiring for a user without the role) is not
    listed in that hub's orientation card.
11. Vietnamese: repeat 1 for three hubs in VI; no English leaks in new strings.
12. Phone width (390px): helper drawer + orientation card usable.
13. `tools/check_contract.py`, anchor registry tests, full pb_learn test suite on a
    throwaway clone (ports per ledger): report counts; only the pre-existing
    test_learn_hub path artifact and template cron failures may remain.
14. Console clean on every page visited.

## Deploy

Modules likely: pb_hub, pb_mission, pb_learn, pb_payroll_ai_insights. Tier: normal
(JS + content + Python, no stored-data change) unless you add a field/migration → risky.
All four DBs. Restart after purge (LR3). One browser walk on payobook.com.

## Report back (keep it short; the report is read by the designer, not the owner)

- What you built, per scope item; the seam you chose for the place signal and why.
- Test results 1–14 with pass/fail and screenshots referenced by name.
- Anchors lost / moved / retired; content still pointing at retired anchors (count).
- Self-score against the design bar (each of the 6 bar items, one line each).
- New gotchas → append to the ledger as LR6+.
- Commits (hashes), modules + versions deployed per DB.
