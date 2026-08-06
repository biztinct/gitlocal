# Payobook Learn — Analysis & Recommendation

Companion to the prototype in this folder. Covers: coverage matrix, per-concept analysis,
decision table, recommendation, roadmap, success metrics, assumptions, and what real
integration requires.

---

## 1. Coverage matrix — every Pay Run & Setup submenu

Inventory verified against `pb_sidebar/data/pb_sidebar_data.xml` (active items).
"Outline" = bilingual what/why/when/prereq/mistakes content written and shown in the
prototype; "★ Full" = fully playable in the prototype.

| Sidebar item (EN / VI) | Journey (Opt 1) | Simulator (Opt 2) | Companion (Opt 3) |
|---|---|---|---|
| **Pay Run · Chạy lương** | | | |
| Run Payroll · Chạy bảng lương | **★ Full lesson L1** (8 steps + quiz) | **★ Mission 1** (full) | Context card + 4 intents (what-next, affect-run, check-final, practice) |
| Pay Runs · Đợt tính lương | Outline station | Mission 1 submit leg + Mission 3 outline | Context card + approve/fix intents; pipeline explainer screen |
| Payslips · Phiếu lương | Outline station; L2 trace/morph steps land here | Mission 1 anomaly inspection | "Why is pay different" calc breakdown; BHXH glossary answer |
| Import Data · Nhập dữ liệu | Outline station | Referenced in M1 consequence ("verify import first") | Context card + intents; mock 4-step screen |
| Full & Final · Quyết toán thôi việc | Outline station | — (production phase) | Context card + intents; mock settlement screen |
| Proration Audit · Soát xét ngày công | Outline station | — (production phase) | Context card; mock audit screen (factor table) |
| Retro Adjustments · Điều chỉnh hồi tố | Outline station | Referenced in M1 quiz & fix-error answer | Context card; mock retro ledger |
| **Setup · Thiết lập** | | | |
| Formula Engine · Công thức lương | Outline station | Mission 4 outline | Context + why-setup intent; mock 3-pane studio |
| Salary Structures · Cấu trúc lương | Outline station (legacy framing) | — | Context card; mock legacy screen |
| Statutory · Bảo hiểm & Thuế | **★ Full lesson L2** (7 steps + quiz) | **★ Mission 2** (full) | "What happens if I change this rate" consequence answer |
| Integrations · Tích hợp | Outline station | — (production phase) | Context card; mock connector screen |

Overview items (Dashboard, Approvals) are present in the shell and used by lessons/answers
but are out of tutorial scope this phase, as instructed.

---

## 2. The three concepts

### Option 1 — Cinematic Guided Journey
**Central idea:** learning as a visible, story-shaped path. The map turns "a pile of menus"
into two lines with stations, dependencies and a destination; the player turns each screen
into a narrated scene where animation carries meaning (spotlight = "look here", trace-dot =
"this rate becomes this payslip line", morph = "this is what your change does").

- **Removes classroom coaching by:** replacing the trainer's projector walkthrough. The
  narration + camera movement + before/after does what a trainer's pointing and talking does,
  on demand, at the learner's pace, in their language.
- **Advantages:** best first impression ("wow"); best at teaching *causality* (Setup→Payrun
  tracing); lowest cognitive load; naturally linear so progress is meaningful; cheap to keep
  accurate (steps anchor to `data-coach` selectors that already exist for pb_coach).
- **Disadvantages / risks:** passive — watching ≠ doing; completion can be theatre if quizzes
  are shallow; long lessons compete with a payroll clerk's patience; anchors break silently
  when screens change (needs an anchor-lint CI).
- **Complexity:** Low-Medium. ~70% already exists in `pb_coach` (spotlight, tours, welcome,
  launcher). New: journey map surface, autoplay/narration player, trace/morph moments, quiz +
  progress persistence (`pb.coach.progress` model), i18n of tour content.
- **Accessibility:** good — narration is text (aria-live), player is keyboardable, reduced
  motion swaps animation for instant states. Spotlight must keep 4.5:1 text contrast on the
  dimmed layer.
- **Localisation:** tour content moves from JS literals into translatable records
  (`_description` + `ir.translation` or JSON per lang) — a day of plumbing, then VI is a
  content task.
- **Maintenance:** per-screen change → update 1–3 steps. The outline data model (what/why/
  when/prereq/mistakes) doubles as documentation.
- **Best for:** first-week users; the guided trial / demo world (existing hero_path users);
  anyone who answers "give me the complete journey".

### Option 2 — Safe Payroll Simulator
**Central idea:** payroll competence is judgement, not navigation. The simulator makes the
*decisions* the curriculum: consequence previews before risky actions, seeded anomalies,
misconception-recovery when the learner takes the tempting-but-wrong path, and a confidence
score earned by choices.

- **Removes classroom coaching by:** replacing the supervised "first payroll with a senior
  watching over your shoulder". The recovery dialogs are the senior colleague saying "let's
  rethink that" — available forever, without embarrassment.
- **Advantages:** deepest learning (doing + failing safely); directly reduces real errors
  (the missions rehearse the exact top-3 mistakes: blind compute, blind accept, live-rate
  edit); confidence score is a real readiness signal managers can trust; VN-realistic data
  makes it feel like work, not a game.
- **Disadvantages / risks:** most expensive to build honestly (a mission is a scripted state
  machine per workflow); risk of divergence from the real screens if built as replicas;
  seeded scenarios go stale unless generated; a badly-tuned recovery dialog can feel
  patronising.
- **Complexity:** Medium-High as a separate surface — **but Payobook has an unfair
  advantage:** `pb_demo` already provides a regenerable practice world with real screens,
  partial read-only security, and a live June run. Missions can run on the *real* UI against
  demo data, which kills the replica-divergence risk. The new work is the mission engine
  (steps, validation, consequence interception, debrief) + seeded anomalies in the demo
  generator.
- **Accessibility:** same as the host app; consequence/recovery dialogs are standard modals;
  timers avoided by design.
- **Localisation:** mission copy is structured strings; the practice data itself is already
  bilingual in pb_demo.
- **Maintenance:** highest per-workflow cost; keep missions few and canonical (5–8 total),
  not exhaustive.
- **Best for:** users about to run their first real payroll; managers certifying readiness;
  experienced payroll people new to Payobook who want to "try, not read".

### Option 3 — Contextual AI Learning Companion
**Central idea:** the tutor is ambient. Instead of "go learn", the user asks from where they
stand, and the answer arrives grounded in the current screen, their role and the current
data — as guidance with pointing, steps, calculations and warnings, never as an action
performed on their behalf.

- **Removes classroom coaching by:** replacing the post-training support channel ("quick
  question…"). It's the only concept that helps at the *moment of need*, forever, including
  long after onboarding.
- **Advantages:** zero-navigation help; personalises for free (screen + role + state are the
  context); the "why is this number X" calc-explainer is a genuine support-ticket killer;
  gracefully bridges to the other two concepts ("Show me" = micro-journey, "Let me practise"
  = simulator hand-off); Payobook already has the substrate (`pb_payroll_ai_insights` with
  screen-context, intent classifier, action buttons, and `pb_coach` launching).
- **Disadvantages / risks:** an LLM answering payroll/legal questions must be
  guard-railed (grounding corpus, refusal styles, no invented rates); discoverability — a
  dock can be ignored; costs per query; a bad answer damages trust faster than no answer;
  bilingual quality needs review, not just translation.
- **Complexity:** Medium. Frontend dock + rich-answer blocks + highlight engine are
  prototype-proven here; backend = extend the existing PayAI engine with a learning-content
  retrieval layer (the Journey's outline/lesson corpus becomes the grounding source) +
  permission-aware answer filters.
- **Accessibility:** chat + blocks are screen-reader-friendly; point-at highlights need a
  text fallback ("in the sidebar, under Setup"); language switch must also switch TTS/voice
  if voice is kept.
- **Localisation:** answers generated in the user's language, but the *grounding corpus*
  must exist in VI (same content as Option 1's lessons — shared asset).
- **Maintenance:** lowest per-screen cost once grounded: content lives in one corpus; new
  screens need a context blurb + suggested questions.
- **Best for:** everyone after week one; experienced users with one-off questions; returning
  users; Viewer-type roles needing explanations rather than training.

---

## 3. Decision table

| Criterion | 1 · Journey | 2 · Simulator | 3 · Companion |
|---|---|---|---|
| First-run onboarding power | **Excellent** | Good | Fair |
| Depth of learning (retention) | Good | **Excellent** | Good |
| Moment-of-need help | Poor | Poor | **Excellent** |
| Error prevention (real runs) | Good | **Excellent** | Good |
| Build cost on current codebase | **Low-Med** (pb_coach exists) | Med (pb_demo exists) | Med (PayAI exists) |
| Ongoing content maintenance | Medium | High | **Low** (shared corpus) |
| Accuracy risk as app evolves | Anchor drift | Scenario drift | Grounding drift (worst if unmanaged) |
| Localisation effort | Content-only | Content-only | Corpus + generation QA |
| Wow factor for demos/sales | **High** | High | Medium-High |
| Measurable mastery signal | Quiz scores | **Confidence by decisions** | Question-resolution rate |

---

## 4. Recommendation — a staged hybrid on one content spine

**Recommendation: build the hybrid, staged Journey → Companion → Simulator, on a single
shared content model.** No single option removes the trainer alone: the Journey teaches the
map, the Simulator builds the hands, the Companion answers the moment. The prototype
deliberately demonstrates the seams: companion answers link to lessons and missions; lesson
outlines feed companion answers; missions debrief into checklists the companion also serves.

Why this order:

1. **Journey first** because it is the cheapest leap from what exists (pb_coach already
   ships spotlight tours + launcher + AI "Show me"), and it *creates the content spine* —
   the per-station what/why/when/prereq/mistakes + lesson steps — that both other options
   consume. Nothing built here is throwaway.
2. **Companion second** because PayAI already has screen-context and tour-launching; adding
   the learning corpus + rich-answer blocks (steps with point-at, calc tables, consequence
   warnings, role-aware refusals) converts existing plumbing into the support-ticket killer.
3. **Simulator last** because it is the most expensive and most valuable *after* users know
   the map — and because running missions on the real UI over `pb_demo` data (not replicas)
   needs the mission-engine investment to be done carefully once.

**First release (Phase 1) must include:** journey map for Pay Run + Setup; 4 full lessons
(Run Payroll, Pay Runs & approvals, Statutory, Formula Engine); outlines for the rest;
quizzes + progress persistence; EN/VI; reduced-motion; resume. **Can follow later:**
autoplay narration voice, confidence scoring, celebration polish, remaining lessons.

**Technical foundations required:** (a) a `pb.learn.content` model — stations, lessons,
steps, outlines, quizzes — translatable, exported to the frontend as JSON (single source for
Journey, Companion grounding, and mission copy); (b) an **anchor registry**: every
`data-coach` selector named in content is checked by a CI script against the rendered
templates so screen changes fail loudly, not silently; (c) progress persistence per user
(`pb.learn.progress`); (d) the PayAI grounding retrieval over (a); (e) mission engine as an
OWL service intercepting real actions in the demo company.

**Keeping it accurate as the app changes:** content lives beside code (module data files),
anchor-lint in CI, a "content owner" review step in PRs that touch Pay Run/Setup screens,
and the Companion's fallback answer explicitly admits when it doesn't know rather than
guessing.

---

## 5. Phased roadmap

- **Phase 1 — Pay Run & Setup proof of value (3–4 weeks):** content model + anchor lint;
  journey map + 4 full lessons + outlines; quizzes, progress, EN/VI; ship to the demo world
  first (guided-trial users are the safest beta cohort).
- **Phase 2 — Remaining menus + Companion (3–4 weeks):** People/Insights/Workforce
  stations; PayAI learning intents grounded in the content model; rich-answer blocks +
  point-at highlights + role-aware refusals; "Show me / Open lesson" bridges.
- **Phase 3 — Personalisation & Simulator (4–6 weeks):** starting modes; role-filtered
  paths; resume & re-teach ("struggled twice → offer simpler explanation + mission");
  mission engine on pb_demo with 5 canonical missions; confidence scoring; manager view.
- **Phase 4 — Optimisation with behavioural data (ongoing):** lesson abandonment funnels,
  question clustering → new content, EN-vs-VI comprehension gaps, quiz-item analysis,
  support-ticket deflection tracking; prune what nobody uses.

---

## 6. Success metrics

Primary: **time to first successful (approved) pay run**; **setup errors per new company**
(statutory misconfigurations caught in review); **pay-run corrections** (retro adjustments
attributable to operator error); **support requests per active user** (target: ↓40% for
question-type tickets); **self-service resolution rate** (companion answer not followed by
a ticket within 24h).

Secondary: lesson completion & abandonment point; quiz first-try correctness;
mission completion + recovery-dialog frequency (a *healthy* recovery rate proves the
simulator is teaching, not just confirming); confidence-score distribution vs manager
sign-off; repeat visits to help content (should fall per-user over time); EN vs VI
completion/comprehension deltas (flags translation quality issues).

---

## 7. Assumptions & unresolved questions

1. **Menu scope**: took the *active* pb_sidebar items; inactive children (Insurance
   Policies, Tax Tables under Statutory) treated as part of the Statutory lesson. Confirm.
2. **"Setup" position**: sidebar data places Setup between Pay Run and People (sequence 25)
   — the prototype mirrors that.
3. Statutory rates/deduction values (8/17.5, 1.5/3, 1/1, ₫11m/₫4.4m, 5% first band) are
   **practice values** for the fictional company; production content must read the live
   policy records, never hardcode.
4. Assumed the tutorial ships inside the existing web client (OWL), not as a separate site;
   the prototype's shell is a stand-in only.
5. Open: should mission progress/confidence be visible to managers (HR analytics), or
   private to the learner? Affects Phase 3 data model.
6. Open: voice narration (PayAI already has voice) — worth it for VN factory-floor users on
   mobile? Deferred to Phase 3.
7. Open: does the guided-trial demo world adopt Phase 1 immediately (recommended — safest
   audience, highest sales value)?

## 8. Integrating into the real app — concrete checklist

1. New module `pb_learn` (models: content, progress; assets: map surface, lesson player —
   the player is an evolution of `pb_coach`'s overlay, keep one engine).
2. Port prototype content (`data.js`) into `pb_learn/data/*.xml` translatable records; VI
   review by a native payroll speaker.
3. Extend `pb_coach` overlay: autoplay bar, consequence/tip cards, trace + morph moments,
   quiz modal, progress wiring. Add missing `data-coach` anchors (statutory + payslip lines).
4. Extend `pb_payroll_ai_insights`: `learning` intent; retrieval over pb_learn content;
   rich-answer block renderer in `ai_insight_chat.js` (steps/calc/warn blocks as OWL
   components); role-aware answer filter from `res.groups`.
5. Mission engine (Phase 3): OWL service on the demo company; intercepts
   `pw-compute`/approve/policy-write actions to inject consequence previews and validate
   steps; seeded anomalies added to the `pb_demo` generator.
6. CI: anchor-lint script (grep content anchors vs template `data-coach` attributes).
