# Payobook Learn — In-App Tutorial Prototype

Three genuinely different concepts for replacing the current pb_coach tour list with a
bilingual (EN/VI), animated, self-sufficient learning system covering **Pay Run** and
**Setup**. Built as a zero-dependency HTML/CSS/JS prototype on a simulated Payobook shell.

## Run it

Open `index.html` in any modern browser. No server, no build step:

```bash
open docs/tutorial_poc/index.html      # macOS
```

Everything is local: state (language, role, lesson progress, mission completion,
confidence scores) persists in `localStorage` under the key `pbLearnPoc`.
**Reset progress** on the hub clears it.

## Navigating the prototype

The hub (`#/hub`) is the concept selector. Global controls appear on every screen:

| Control | What it does |
|---|---|
| `EN / VI` | Instantly switches the whole experience — UI, lessons, missions, AI answers, number formats (₫12,919,000 vs 12.919.000 ₫) |
| `OF / HR / GM / VW` | Role switcher (Payroll Officer, HR Manager, General Director, Viewer). Menus and AI answers adapt; Viewer gets refusal + safe alternatives on approval questions |
| Reduce motion | Manual reduced-motion toggle; `prefers-reduced-motion` is also honoured automatically |
| Reset progress | Wipes localStorage |

### Option 1 — Cinematic Guided Journey (`#/journey`)
- Two learning lines (Pay Run: 7 stations · Setup: 4 stations) with progress, required/optional
  badges, time estimates, dependencies, search and a resume state.
- Two **fully playable ★ lessons**:
  - **Run Payroll** (`#/journey/lesson/L1`) — 8 steps + quiz. Includes a consequence card
    on the Compute step and a simulated results state with an anomaly flag.
  - **Statutory** (`#/journey/lesson/L2`) — 7 steps + quiz. Includes the **Setup→Payslip
    trace animation** (step 5: an animated dot travels from the policy rates to the BHXH
    line on Mai's payslip) and the **before/after morph** (step 6: the payslip re-prices
    live when BHYT changes 1.5%→2%).
- Player controls: play/pause (autoplay with per-step timing), next/back, replay step,
  skip to quiz, save & exit (resumes at the same step). Keyboard: ← → Space Esc.
- Wrong quiz answers get a misconception explanation + "replay step" recovery;
  completion suggests the next station; finishing both ★ lessons awards the badge.
- Non-★ stations open a clearly-labelled **lesson outline** (what/why/when/prereq/mistakes)
  — placeholders for the production build, content already written bilingually.

### Option 2 — Safe Payroll Simulator (`#/sim`)
- Fictional practice company (Hoa Sen Retail Co., 48 employees, July 2026) with a
  permanent green "Practice environment — no real data" banner.
- **Mission 1 — Run the July pay run** (fully playable): open the wizard yourself →
  choose the right division (wrong choice gets a gentle correction) → **consequence
  preview** before Compute (affects / reversible / verify-first) → computing animation →
  **inspect the flagged OT spike** (expected-vs-actual comparison) → decide: flagging is
  right; accepting triggers a **misconception-recovery dialog** → submit → animated
  approval pipeline → **debrief** with what-you-did, pre-finalise checklist and a
  confidence gain (reduced if you needed the recovery).
- **Mission 2 — Apply a BHYT rate change** (fully playable): version the policy instead of
  editing live rates → set the rate (wrong values coached) → choose the effective date
  (choosing "immediately" while July is open triggers recovery) → before/after payslip
  impact preview with the PIT knock-on → commit or **undo**.
- Missions 3 & 4 (approvals walkthrough, formula-component add) shown as labelled outlines.
- Confidence panel scores four skills, earned by decisions — not by clicking Next.

### Option 3 — AI Learning Companion (`#/companion`)
- The full simulated app is freely navigable; the companion dock is grounded in the
  current screen: "You're on…" context card + per-screen suggested questions.
- Scripted Q&A engine (~10 intents, keyword-matched, bilingual) with **rich answer
  blocks**: paragraphs with glossary hover-terms (BHXH, BHYT…), numbered steps with
  point-at buttons that flash the real control, calculation breakdown tables
  (June→July decomposition of Mai's net), warnings, consequence notes,
  "Grounded in:" source lines, and a "Tell me more" progressive-disclosure expander.
- **Show me** replays the answer as a sequence of highlight rings on the live UI;
  **Explain more simply** re-answers in plain language; deep links hand off to the
  Journey lesson or a Simulator mission ("Let me practise safely").
- Permission-aware: the same question gets different answers per role; Viewer gets an
  honest "your role can't do this" + who can + how to request access.
- The guard banner is permanent: *"I guide — you act… I never perform payroll actions
  for you."* Prototype answers are canned; unknown questions get an honest fallback.
- Mobile: dock becomes a bottom sheet behind a floating action button.

## Files

```
index.html      Shell + inline Lucide SVG sprite (no CDN)
styles.css      Design system (mirrors pb_theme indigo #5A4BB0 tokens, Inter, 14px radius)
data.js         ALL content: i18n strings, menu inventory, lessons, missions, Q&A, glossary
app.js          Engine: router, simulated shell, spotlight/trace engine, 3 concept controllers
analysis.html   THE WRITTEN DELIVERABLE — coverage matrix, comparison, recommendation,
                roadmap, metrics, assumptions, integration checklist. Self-contained;
                open it directly or via "Read the analysis" on the prototype hub.
DESIGN_SPEC.md  PORTABLE BLUEPRINT — the strategy abstracted from Payobook so it can be
                applied to any application: binding rules vs adaptation checklist,
                content-spine schema, engine architecture, quality bar.
REUSE_PROMPT.md Ready-to-paste kickoff prompt for reusing this design in another
                application (copy this whole folder into the target repo first).
screenshots/    Captured states (hub, map, lessons, simulator, companion-VI, analysis)
```

## Ground truth used

- Menu inventory from `pb_sidebar/data/pb_sidebar_data.xml` (Pay Run + Setup sections,
  active items only).
- Approval pipeline from `pb_payruns/models/hr_payslip_run.py`
  (`draft → level0 Officer → level1 HR → level2 GM → done`, rejection with reason).
- Design tokens from `pb_theme/static/src/scss/primary_variables.scss`.
- Existing tour behaviour from `pb_coach` (service, overlay, hero_path/tour_payrun etc.).
- Payslip maths are internally consistent VN practice values (base 12,000,000 ₫ →
  BHXH 8% = 960,000; personal deduction 11m; PIT tier-1 5%); marked as practice data.
