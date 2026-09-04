# Reusing this design in another application

## How to transfer

1. Copy the **entire `tutorial_poc/` folder** into the target application's repo
   (e.g. `docs/learning_system_reference/`). It is fully self-contained — the prototype,
   the spec, the analysis and the screenshots travel together with relative links intact.
2. Open a Claude session in the target repo and paste the prompt below, filling the
   three `<<placeholders>>`.

The prompt is written so the agent treats the reference as a **blueprint to adapt**, not
a template to reskin: it must re-derive the target app's menus, roles, maths and brand,
while keeping the parts of the design that are binding.

---

## The prompt (copy everything inside the fence)

```text
You are a world-class SaaS product designer, learning-experience designer, interaction
designer, and senior frontend engineer.

TASK
Design and prototype a bilingual, animated, self-sufficient in-app learning system for
<<APPLICATION NAME — one line on what it does and who uses it>>, covering these areas of
the application: <<IN-SCOPE MENUS/MODULES, e.g. "Orders and Configuration">>.
Languages: <<LANGUAGE 1 and LANGUAGE 2>>.

REFERENCE MATERIAL — read in this order BEFORE designing
A proven reference implementation of this exact strategy (built for a payroll product)
is in this repo at docs/learning_system_reference/ (copied from another project):

1. DESIGN_SPEC.md   — THE BLUEPRINT. Portable specification: the 10-part learning model,
                      the three surfaces (Guided Journey / Safe Simulator / AI Companion),
                      the staged-hybrid strategy, the shared content-spine schema, the
                      binding rules vs the parts you must re-derive (§8 adaptation
                      checklist), roadmap, metrics, and the acceptance checklist (§11).
2. index.html       — Run this in a browser (no build step) to EXPERIENCE the reference:
                      concept hub → journey map → lesson player (spotlight, trace, morph,
                      quiz with recovery) → simulator missions (consequence previews,
                      seeded anomaly, recovery, debrief) → AI companion (screen-grounded
                      rich answers, role-aware refusals, language switching).
3. app.js / data.js / styles.css — the engine and the content-schema example. Reuse the
                      engine patterns (spotlight/trace/flash-ring, step machines, i18n,
                      delegated events, localStorage state) freely.
4. analysis.html    — why the staged hybrid won: comparison, decision table, roadmap.

BINDING (do NOT change these — they are what makes the design work)
- The three cooperating surfaces and the staged hybrid on ONE shared content spine.
- The 10-part learning model for every covered menu item; completion = demonstrated
  understanding (scenario quizzes / scored decisions), never just clicking Next.
- Consequence previews before risky actions (scope / reversibility / verify-first).
- Mistake RECOVERY, not rejection — "let's rethink that" tone, never patronising.
- Practice surfaces unmistakably labelled; the companion never claims to have performed
  an action and never invents domain facts (grounded or honestly ignorant).
- Both languages complete and natural everywhere, switchable live, locale-correct
  number formats.
- Accessibility: prefers-reduced-motion + manual toggle, keyboard paths, aria-live
  narration, focus management. No gradients, no emoji (SVG icons only), no tooltip-chain
  tours, no modal chains, never cover the UI being explained.
- One user decision per mission step (see DESIGN_SPEC §7 — this prevented real bugs).

RE-DERIVE FROM THIS APPLICATION (do NOT copy from the reference — DESIGN_SPEC §8)
- The real menu inventory from the app's actual navigation source (code, not screenshots)
  with exact labels in both languages. If the structure cannot be discovered, show
  clearly-labelled placeholders and ask me.
- One internally consistent worked example from THIS domain (every number reconciles;
  reuse it across lessons, missions and calculation answers).
- The 3–5 genuinely risky actions → they become the consequence previews and missions.
- One realistic seeded judgement anomaly per flagship mission.
- Real roles/permissions for the role switcher and honest refusals.
- The record-state pipeline for the pipeline animation.
- This app's terminology + bilingual glossary.
- This app's design tokens mapped to the roles in DESIGN_SPEC §6 (do NOT reuse the
  reference's indigo palette).
- Flagship picks: 2 full lessons (most-used workflow + most consequential setup screen)
  and 2 full missions; everything else as labelled outlines with content written.

DELIVERABLES (match the reference's quality bar — DESIGN_SPEC §11)
1. A runnable no-build HTML prototype: concept hub + all three surfaces, both languages,
   progress in localStorage, reduced-motion, desktop + mobile states.
2. README.md — how to run and navigate.
3. analysis.html — coverage matrix (every in-scope submenu × surface), the decision
   table re-scored for THIS application, recommendation, phased roadmap, success
   metrics, assumptions and open questions, integration checklist into the real app.
4. Screenshots of the main states if tooling permits.

WORKING APPROACH
Inspect this application's codebase first and build the real inventory; run the
reference prototype to internalise the interaction quality; then design and build.
Validate the prototype in a real browser (desktop, one mobile width, reduced motion,
both languages) before declaring it done. Ask only questions the codebase cannot
answer; do not let non-critical uncertainties block the first prototype.
```

---

## Notes for you (not part of the prompt)

- If the target session runs in the same machine/repo layout, you can skip the copy and
  point the prompt at the absolute path
  `/Users/adity/Documents/GitHub/gitlocal/docs/tutorial_poc/` instead of
  `docs/learning_system_reference/` — but copying keeps the target repo self-sufficient.
- If the target app's languages differ (e.g. EN/TH), the reference's Vietnamese content
  still serves as the *quality bar* for what "natural, domain-correct second language"
  means.
- If you want the phased Fable-designs / Opus-implements workflow for the target app,
  paste the prompt into a Fable session and add: "Produce the per-phase handover
  documents for Opus rather than implementing directly."
