# pb_learn Phase C — Implementation Handover (Run C1 + Run C2)

**Read first:** `docs/handovers/PBLEARN_LEDGER.md` (ALL sections), then design_v2.html §9-§10.
Phases A+B are merged and review-fixed; extend, never restructure. All content flows
through `docs/tutorial_poc/author/` + one generator run per commit.

**Mission:** (C1) extend coverage to the remaining core sections — Overview, People,
Insights, Compliance — and promote the Journey to its own top-level "Learn" sidebar
section; (C2) retire pb_coach: PayAI re-targets lessons, pb_coach's demo side-effects
move to their natural owners, the dependency is dropped.

## Binding non-goals

- Workforce and Planning sections are OUT (mixed plain-view surfaces; a later phase).
- No LLM; no live-mission additions; no new live-value keys.
- pb_coach FILES are not deleted and its module is not made uninstallable in code —
  retirement = nothing depends on it + its jobs have new owners + deploy notes describe
  the uninstall. The live demo must keep working through the transition.

---

# Run C1 — remaining sections + Learn section

## C1-1 · Verified plumbing (recon 2026-08-09; do not re-derive)

All 8 screens are OWL client actions:

| Screen key | Leaf (pb_sidebar_data.xml) | Tag | Template (regions with lines in recon report — use them) |
|---|---|---|---|
| dashboard | item_dashboard :37 | pb_dashboard | pb_dashboard/static/src/xml/pb_dashboard.xml — HAS 4 anchors: dash-hero :8, dash-runpayroll :18, dash-kpis :26, dash-formula :69 (currently `foreign` in the registry — PROMOTE to product, they become ours) |
| approvals | item_approvals :43 (officer/manager/final/admin groups) | pb_approval | pb_approval/static/src/xml/approval.xml — .pba-hero :15, .pba-kpis :33, .pba-lanes :64, .pba-recent :123, reject popover .pba-pop :143 |
| employees | item_employees :88 | pb_people | pb_people/static/src/xml/people.xml — head :11, bulkbar :23, kpis :36, filters :46, roster :82, foot :106 |
| contracts | item_contracts :97 | pb_contracts | pb_contracts/static/src/xml/contracts.xml — head :10, kpis :19, filters :29, roster :64, foot :88 |
| insights | item_analytics :108 | pb_insights | pb_insights/static/src/xml/insights.xml — hero :20, trend :84, duo :147, pulse :261, explore-link :405 |
| explorer | item_explorer :120 | pb_explorer_cockpit | pb_explorer/static/src/xml/explorer.xml — head :19, rail :141, filters :209, headline :260, table :367 |
| workforcean | item_workforce_insights :133 | pb_workforce_insights | workforce_insights.xml — head :17, filters :45, kpis :78, chart :119, duo :125/:198 |
| govreports | item_govt_reports :229 (NO groups) | pb_govt_reports | govt_reports.xml — head :10, countries :22, grid :34, empty :49 |

**Anchor naming warning (recon):** pb_people/pb_contracts/pb_govt_reports share the
`ppl-*` class vocabulary — anchor KEYS must be namespaced per screen: `pe-*`
(employees), `ct-*` (contracts), `pa-*` (approvals), `in-*` (insights), `ex-*`
(explorer), `wa-*` (workforcean), `gr-*` (govreports). Dashboard keeps its existing
`dash-*` names. ~5 anchors per screen, only regions content references.

## C1-2 · Content scope

- **New station lines** in the selection: `overview`, `people`, `insights`,
  `compliance`; section value stays `payroll`. 8 stations.
- **Two full lessons:**
  - **LW · "Welcome to your command centre"** (station dashboard, ★): the hero_path
    successor as a proper lesson — dashboard orientation → KPIs → formula-driven
    payroll → the monthly loop (pipeline moment) → where everything lives (the
    sidebar map) → how to get help (the Coach itself — meta-step pointing at the
    launcher) + quiz. Port the narrative voice of pb_coach's hero_path
    (static/src/js/tours/hero_path.js) but structured as the 10-part model demands.
    This lesson is the suggested first station for new users.
  - **LA · "Approve like it's your signature"** (station approvals, ★): the manager
    judgement lesson — what the lanes mean → sampling strategy vs reading everything →
    flags first → variance vs last month → reject-with-reason mechanics (testimony
    fields) → consequence card (approving moves real money one gate closer) + quiz
    (scenario: variance unexplained — approve/investigate/reject).
- **Outlines** for the other 6 (what/why/when/prereq/mistakes, bilingual).
- **Replicas:** approvals (lanes + KPI band — rich enough for LA), dashboard exists
  (rep-dash-*); the other 6 thin (KPI strip + table, ledger pattern). Reuse the
  fullfinal/ledger renderer parameterisation where possible.
- **Intents (~10):** approvals-focused (howmanyslips sampling, variance, rejectright),
  whopays/whosees (people/contracts capability answers incl. no_access refusals),
  explorer-vs-insights ("which tool answers which question"), govreports country logic
  (tiles scope by the active company's country), plus whatpage/whatnext dynamic
  coverage via the new screen records. Columns for every KPI band (~25).
- **Journey promotion:** new `pb.sidebar.section` "Learn" — `technical_key: learn`,
  `sequence: 50`, `show_label: True` — emitted by the GENERATOR alongside the leaf
  (extend `SIDEBAR_LEAF` → `SIDEBAR` declaration with section + leaf; leaf moves from
  `sec_payrun` to the new section, sequence 10). Bilingual section name ("Learn" /
  "Học tập" — consistent with the chrome key ruling from A2).
- Contract checks (~6): the 8 leaf/tag pairs, dash-* anchors literal in
  pb_dashboard.xml, approvals testimony fields (already pinned — extend taughtIn),
  govt reports country-scoping method exists (`pb.govt.reports.get_govt_reports_data`).

## C1-3 · Verify + commit

Full suite; no-regression analysis on A+B content; commit
`feat(pb_learn): Phase C1 — Overview/People/Insights/Compliance + Learn section`.
(+ separate commit for the 7 templates' anchors, additive only.)

---

# Run C2 — pb_coach retirement

## C2-1 · Verified seams (recon; do not re-derive)

- **Only dependent:** `pb_payroll_ai_insights/__manifest__.py:48`.
- **Service use:** ai_insight_chat.js:20 `useService("pb_coach")` (HARD — throws if
  absent) and :153-157 `runAction` → `coach.start(action.tour)`.
- **Whitelist:** payroll_ai_engine.py:301-302 `_KNOWN_TOURS = ('hero_path',
  'tour_payrun', 'tour_formula', 'tour_payslips')`; `_sanitize_action` :304-316;
  system prompt lists the same 4 at :105-118.
- **Side effects pb_coach owns today:** `body.pb-demo-user` (hides apps menu +
  Discuss systray; coach_overlay.js:61, coach.scss:9-11); demo disclaimer chip
  (coach_overlay.xml:126-136, scss:269-287); demo first-login auto-start of
  hero_path (coach_overlay.js:74-83); `demo_missing_record.js` FetchRecordError
  guard (demo hardening, unrelated to tours). Welcome modal is dead code (no callers).
- pb_learn's `.lrn-fab` sits at bottom 160px because pb_coach's FAB holds 92px.

## C2-2 · The work

1. **PayAI re-target (pb_payroll_ai_insights — sanctioned this run):**
   - `useService("pb_coach")` → optional lookup (try/catch or `env.services["pb_coach"]
     || null`) so the module survives pb_coach's absence.
   - Envelope: `_KNOWN_TOURS` → `_KNOWN_LESSONS = ('LW', 'L1', 'L5', 'L3')` mapping
     the four old tours to their lesson successors (hero_path→LW, tour_payrun→L1,
     tour_formula→L5, tour_payslips→L3); `_sanitize_action` emits
     `{'type': 'open_lesson', 'lesson': key, 'label': …}` and STILL accepts+converts
     `start_tour` with an old tour id (the LLM prompt may lag) — map old→new. Update
     the system prompt lesson list. `runAction` handles `open_lesson` via
     `doAction('pb_learn.action_learn_journey', {additionalContext:{lesson: key}})`
     and falls back to legacy coach.start only when the coach service exists.
   - pb_learn: `learn_journey` action reads `context.lesson` and auto-opens that
     lesson (station resolve → startLesson) — small journey.js addition.
   - Contract check updated: `payai-known-tours` → pins `_KNOWN_LESSONS` AND that
     each key is a real `learn.lesson` key.
   - **Do NOT remove the pb_coach dep from the PayAI manifest yet** — that happens at
     deploy time with the uninstall; instead add the dep note + deploy step.
2. **Side-effect migration:**
   - `pb_demo` gains a tiny asset `demo_chrome.js/scss`: sets `body.pb-demo-user`
     for demo-group users (same class name — CSS contract preserved), renders the
     ephemeral-demo disclaimer chip (port template + scss; same copy), and carries
     `demo_missing_record.js` (moved verbatim). pb_demo owns its own hardening now.
   - `pb_learn`: demo first-login behaviour — for demo-group users, once per login
     (same login_date mechanism, localStorage-flagged), open the Journey with LW
     suggested (do NOT auto-start a spotlight; opening the map with a "Start here"
     pulse on LW is the calmer successor). Ledger the divergence.
3. **Launcher restack:** with pb_coach retired the stack is two controls — move
   `.lrn-fab` to bottom 92px via a body-class toggle (`pb-coach-present` detection:
   if the pb_coach service exists keep 160px, else 92px) so BOTH deploy states render
   correctly during the transition.
4. **Deploy notes (ledger):** order — `-u pb_payroll_ai_insights -u pb_demo -u
   pb_learn` first (all coach-independent), verify, then uninstall pb_coach + remove
   the manifest dep in a follow-up commit at deploy time; vi_VN caveat still applies.
5. Tests: PayAI sanitize accepts old+new envelope forms; journey deep-link opens the
   lesson; pb_demo chrome renders for demo group only; anchors dash-* now product-
   owned (registry tests updated).

## C2-3 · Verify + commit

Full suite + grep-proof PayAI works with and without the coach service; commit
`feat(pb_learn,pb_payroll_ai_insights,pb_demo): Phase C2 — pb_coach retirement seams`.

Report per established format after each run.
