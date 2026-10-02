# In-App Learning System — Portable Design Specification

**Version 1.0 · Origin: Payobook Learn prototype (docs/tutorial_poc/)**

This document abstracts the Payobook tutorial redesign into a reusable blueprint, so the
same strategy can be applied to any business application with high-stakes workflows.
It defines what is **binding** (the parts that make the design work) and what is
**adaptable** (the parts you must re-derive from the target application).

Read alongside:
- `index.html` + `app.js` + `data.js` + `styles.css` — the working reference implementation
- `analysis.html` — the full comparison, decision table, recommendation and roadmap
- `README.md` — how to run and navigate the prototype

---

## 1. Vision statement

A user must be able to become competent and confident in the application **without a
classroom session, a tutor, a live demo, a manual, or a support ticket** for ordinary
workflow questions. The tutorial is not a feature tour; it is a **learning system** with
three cooperating surfaces:

| Surface | Teaches | Moment |
|---|---|---|
| **Guided Journey** (cinematic lessons on a station map) | the map — what exists, why, how it connects | first week |
| **Safe Simulator** (missions on practice data) | the hands — judgement, decisions, recovery | before first real high-stakes action |
| **AI Companion** (screen-grounded Q&A) | the moment — answers where the user stands | forever after |

**Binding recommendation:** build all three as a staged hybrid — Journey → Companion →
Simulator — on a **single shared content spine** (§4). No single surface removes the
trainer alone. Do not build three separate content systems.

---

## 2. The learning model (binding)

Every feature/menu-item in scope gets content structured as this 10-part model. This is
the atom of the whole system; all three surfaces consume it.

1. **What it is** — one plain sentence.
2. **Why it matters** — the consequence of it existing, not a feature list.
3. **When to use it** — trigger situations, and when *not* to use it.
4. **Prerequisites** — what must be true before starting.
5. **Guided demonstration** — the narrated walkthrough (lesson steps).
6. **Safe hands-on practice** — the mission or "try it" hook.
7. **Common mistakes + consequences** — the 2–3 real ways people get burned.
8. **Validation & recovery** — how to check your work, how to undo/fix.
9. **Knowledge/task check** — one scenario question (not recall trivia).
10. **Completion + next step** — progress credit and the suggested next station.

Rules:
- **Completion must reflect understanding**, not clicking Next: quizzes are scenario
  judgements with per-option explanations; missions score decisions.
- **Higher-risk actions get a consequence preview before the user proceeds**: what is
  affected (scope), whether it is reversible, and what to verify first. This card appears
  in lessons (informational) and in the simulator (as an interception before the action).
- **Wrong answers and wrong decisions get recovery, not rejection**: explain the
  misconception, show the real-world cost, offer the correct path. Tone: senior colleague
  saying "let's rethink that" — never scolding, never patronising.

---

## 3. The three surface patterns (binding structure, adaptable content)

### 3.1 Guided Journey
- **Map**: learning "lines" (one per major menu area) with **stations** = submenu items.
  Each station shows: icon, title, one-line desc, required/optional, time estimate,
  dependency ("After: X"), progress state (done / in-progress / suggested-next pulse).
  Provide overall + per-line progress, search, resume, and a completion badge for the
  flagship lessons.
- **Lesson player**: dim the real UI, spotlight the relevant control, show a narration
  card (kicker · title · body · optional consequence/tip), a step progress bar, and a
  floating control bar: exit(save) / back / play-pause(autoplay) / next / step-count /
  skip-to-quiz. Keyboard: ← → Space Esc. Autoplay duration derives from word count.
- **Signature animated moments** (these carry the teaching, keep them):
  - **Trace**: an animated dot travels from a *setup value* to the *output line it
    produces* (e.g. a rate → a payslip deduction). Teaches causality.
  - **Morph**: a before/after re-price of a real record when a setting changes, with a
    toggle to flip between states. Teaches consequence magnitude.
  - **Pipeline**: an animated stepper showing a record moving through its approval/state
    chain. Teaches process.
- **Non-flagship stations** may ship as **outline cards** (model parts 1–4 + 7) —
  clearly labelled as outlines — before their full lessons exist.

### 3.2 Safe Simulator
- A **fictional practice tenant** with realistic domain data, under a permanent,
  unmistakable banner ("Practice environment — no real data"). Never mix surfaces:
  practice state must be visually distinct and technically incapable of touching
  production.
- **Missions** are scripted state machines over the *real* UI (or a faithful shell):
  each step = instruction + glow-highlight on the expected control + validation of the
  user's actual action + a hint on demand. Wrong-but-plausible actions get coached
  corrections, not blocks.
- Every mission includes: one **consequence interception** before the risky action, one
  **seeded anomaly / judgement point** where the tempting choice is wrong (with a
  recovery dialog), an **undo** demonstration, and a **debrief** (what you did, the
  real-world pre-flight checklist, confidence gain).
- **Confidence score** per skill area, earned by decisions; reduce the gain when the
  learner needed the recovery dialog. 5–8 canonical missions total — not one per menu.

### 3.3 AI Companion
- A **dock** on every in-scope screen: context card ("You're on: X" + one-line purpose),
  3–4 suggested questions for *this* screen, free-text input.
- **Rich answers, not chat walls** — compose from typed blocks:
  `paragraph` (with glossary hover-terms) · `steps` (numbered, each with a point-at
  button that flashes the real control) · `calc` (breakdown table for "why is this
  number X") · `warn` / `ok` callouts · `links` (deep links to lessons/missions) ·
  `source` ("Grounded in: …" + why-am-I-seeing-this) · `more` (progressive disclosure).
- **Modes**: Show me (replay answer as highlight sequence) · Explain more simply ·
  Let me practise safely (hand-off to a mission) · Open the lesson.
- **Permission-aware**: the same question answers differently per role; a role that
  cannot perform the action gets an honest refusal + who can + how to request access.
- **Honesty rules (binding)**: the companion never claims to have performed an action;
  it never invents domain facts (rates, rules) — grounded corpus or admit ignorance;
  the fallback answer says what it *can* answer.

---

## 4. The content spine (binding architecture)

One content model feeds all three surfaces. Do not duplicate content per surface.

```
Station {
  id, line, icon, title*, desc*, required, minutes, after (dependency),
  outline* { what, why, when, prereq, mistakes },      // model parts 1–4, 7
  lesson?  { steps[], quiz }                            // flagship stations
}
LessonStep { screen, anchor, kicker*, title*, body*, consequence?*, tip?*,
             moment? (trace|morph|pipeline|simulate) }
Quiz { question*, options[ { text*, correct, explanation* } ] }
Mission { id, group, minutes, confidence {skill, gain},
          steps[ { id, instruction*, detail*, hint*, nav?, validate } ],
          consequence, anomaly, debrief { did[], checklist[] } }
QAIntent { id, matchKeywords[], label*, blocks[] | roleVariants{ role → blocks[] },
           simplerVariant?*, showMe? }
Glossary { term*, definition* }
```
`*` = translatable (every language ships the full value, no partial fallbacks mid-lesson).

In production this is a translatable data model (e.g. `*.learn.content` records) exported
to the frontend as JSON; the Companion's retrieval grounds on the same records; mission
copy comes from the same place. **The prototype's `data.js` is the working example of
this schema — port its shape, replace its content.**

**Anchor registry (binding):** every UI element referenced by content carries a stable
`data-*` anchor attribute. A CI lint compares anchors named in content against anchors
present in templates, so screen changes break tutorials *loudly* at build time, never
silently at runtime.

---

## 5. Personalisation model

- **Starting modes** (ask once, changeable): full guided journey · only-my-role ·
  today's task · explore independently · test what I know.
- **Role switcher-aware everywhere**: menus filter, lessons show what the role can see
  (lessons/missions may show the full menu — a guided context justifies it), companion
  answers adapt, refusals are honest.
- **Returning users**: resume card (last surface + position); lessons save their step on
  exit; struggled-twice → offer the simpler explanation + a practice hand-off.
- **Language**: a visible switcher on every screen; switching re-renders *everything*
  immediately — UI chrome, content, numbers/currency formats, AI answers. Second-language
  copy must be written for the domain user, not machine-literal.

---

## 6. Visual & interaction language (adaptable tokens, binding rules)

Map these **roles** to the target app's design system — never carry Payobook's palette
into another brand:

| Role | Payobook value (example) | Rule |
|---|---|---|
| Primary / brand | indigo `#5A4BB0` | solid fills only, one primary button per bar |
| Primary-soft | `#EDEAF8` | chips, soft cards, hover states |
| Positive / money | emerald `#0F8A63` | success, practice-safe banner, money values |
| Warning | amber `#B7791F` | consequence cards, flags, outline labels |
| Danger | red `#C0332A` | deductions, rejections, danger-ghost buttons |
| Accent | cyan `#0891B2` | highlight rings, traces, info callouts |
| Canvas / card / border / ink | `#F4F5FB` / `#fff` / `#E2E8F0` / `#212121` | white cards on tinted canvas |

Binding rules regardless of brand:
- **No gradients. No emoji — SVG icon set only** (inline sprite, no CDN).
- Motion is **purposeful** (spotlight/trace/morph/pipeline) and **interruptible**;
  everything honours `prefers-reduced-motion` *and* a manual reduce-motion toggle
  (both collapse animation to instant states, not broken states).
- Keyboard reachable: lesson player, quizzes, dock input; visible focus rings;
  narration in `aria-live` regions; dialogs take focus, Esc closes.
- Never cover the UI being explained — spotlight dims *around* it.
- Avoid: modal chains, text walls, tooltip-only tours, gamification beyond the
  confidence score + one badge, unclear practice-vs-production states.

---

## 7. Engine architecture (from the reference implementation)

The prototype is deliberately dependency-free so it ports anywhere; production embeds
these same pieces in the host framework:

- **Simulated/real shell**: sidebar + topbar + screen renderer; screens carry anchors.
- **Spotlight engine** (`Spot` in `app.js`): a box-shadow "hole" element + positioned
  narration card + animated pointer; smooth-moves between targets; placement algorithm
  prefers right → left → below → above with viewport clamping.
- **Trace engine**: SVG cubic path between two anchors + dot advanced along
  `getPointAtLength` (skipped under reduced motion).
- **Highlight ring** (`flashRing`): scroll-into-view + temporary ring, used by
  companion point-at and Show-me sequences.
- **Router + state**: hash routes per surface; one persisted state object
  (language, role, motion, mode, per-station progress, mission completion, confidence,
  last position) — localStorage in the prototype, per-user records in production.
- **i18n**: every string is `{lang: value}`; one `tx()` accessor; number/currency
  formatting per locale.
- **Delegated events**: `data-act` / `data-nav` attributes + one document-level
  listener routed to the active surface controller. Missions are step machines whose
  steps validate real user actions; **each distinct user decision = one step**
  (lesson learned: two decisions sharing one modal caused off-by-one bugs twice).

---

## 8. What to re-derive for a new application (adaptation checklist)

Do **not** copy these from Payobook — inspect the target app and rebuild:

1. **Menu inventory** — from the app's real navigation source (its sidebar/menu data,
   not screenshots). List every in-scope item with exact labels in all shipped languages.
2. **Domain maths** — build one internally consistent worked example (Payobook's
   equivalent: one employee's payslip whose every number reconciles). All lessons,
   missions and calc-answers reuse the same example so numbers always agree.
3. **The risky actions** — identify the 3–5 actions with real-world blast radius; they
   get consequence previews and become the simulator missions.
4. **The seeded anomaly** — one realistic judgement case per flagship mission (the
   Payobook equivalent: a 282% overtime spike that *might* be genuine).
5. **Roles & permissions** — from the app's real groups; wire the role switcher and
   refusal answers to them.
6. **State pipeline** — the app's real record lifecycle for the pipeline animation.
7. **Terminology & glossary** — the app's own vocabulary, defined in both languages.
8. **Brand tokens** — map §6 roles to the app's design system.
9. **Flagship picks** — 2 lessons (one per major menu area: the most-used workflow +
   the most consequential setup screen) and 2 missions, fully built; the rest as
   outlines with content written.

---

## 9. Delivery roadmap template

- **Phase 1 — proof of value**: content model + anchor lint; journey map for the two
  in-scope menu areas; 2–4 full lessons + outlines for everything else; quizzes,
  progress, both languages, reduced motion, resume. Ship to the safest cohort first
  (demo/trial users if they exist).
- **Phase 2 — coverage + Companion**: remaining menu areas; companion grounded on the
  content spine; rich-answer blocks, point-at, role-aware refusals; lesson/mission
  bridges.
- **Phase 3 — personalisation + Simulator**: starting modes; re-teach on struggle;
  mission engine on the practice tenant; canonical missions; confidence scoring.
- **Phase 4 — optimisation**: abandonment funnels, question clustering → new content,
  per-language comprehension gaps, quiz-item analysis, ticket-deflection tracking.

## 10. Success metrics template

Primary: time to first successful <core workflow completion>; setup errors per new
tenant; corrections attributable to operator error; support requests per active user
(target −40% on question-type tickets); self-service resolution rate (answer not
followed by a ticket in 24h).

Secondary: lesson completion + abandonment point; quiz first-try correctness per item;
mission completion + recovery-dialog frequency (healthy > zero — zero means it isn't
teaching); confidence distribution vs supervisor sign-off; repeat help visits per user
(should fall); language-A vs language-B completion/comprehension deltas.

---

## 11. Quality bar (acceptance for any port)

- [ ] Every in-scope menu item covered (full lesson or labelled outline) — coverage matrix produced
- [ ] Both languages complete and natural; switcher live everywhere; locale number formats
- [ ] 2 flagship lessons with trace/morph/pipeline moments + scenario quizzes with recovery
- [ ] 2 flagship missions with consequence interception, seeded anomaly, recovery, undo, debrief
- [ ] Companion: per-screen context, ≥8 intents, calc-breakdown answer, role-aware refusal, honest fallback
- [ ] Progress + language survive refresh; resume works
- [ ] Reduced-motion (media query + manual toggle) and keyboard paths verified
- [ ] Desktop + one mobile state verified in a real browser
- [ ] Practice surfaces unmistakably labelled; companion never claims to act
- [ ] Analysis document delivered: comparison, decision table, recommendation, roadmap, assumptions
