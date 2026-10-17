# LEARNREV — Learn / help revamp program (Option C: help on the screen)

Status: STARTED 2026-10-17. Design page (owner-approved): `docs/design/learn_revamp/LEARN_REVAMP_DESIGN.html`
(33 gaps G1–G33, best-in-class study, the content engine, three options, build plan). Owner decisions 2026-10-17
(binding, do not re-ask): **Option C**; **phased** Fable-designs / Opus-builds-reviews-tests workflow; **drop badges,
streaks and the overall ring**; practice world = **demo company on payobook, generated replicas on tenants**.

Ledger: `docs/handovers/learnrev/LEARNREV_LEDGER.md` binds every phase (inherits PBLEARN, LEARNOS, ONECHAT and PAYAI
ledgers — read their standing rules before touching pb_learn / PayAI). Each phase: `P<n>_HANDOVER.md` → one Opus
agent implements, self-reviews against the handover, runs the numbered tests, deploys, browser-walks, commits, writes
`P<n>_REPORT.md`. Fable reads the report only; intervenes on failures or spec deviations.

## Standing rules (verbatim in every handover)
- **Design bar:** "Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment named per
  phase; zero dead ends (every state and failure names its reason and next step); plain screen words on every
  label, toast and summary; motion with purpose; keyboard + bulk ergonomics where rows are involved; measured against
  the best SaaS help (Stripe, Xero, Gusto, Notion, Linear), never stock back-office. Payobook design system: indigo
  `#5A4BB0` (soft `#EDEAF8`), ok `#2E7D4F`, warn `#D97706`, bad `#DC2668`, white cards, **Lucide icons only, no
  emoji, no gradients**. Every phase report scores itself against this bar (1–5 per bullet).
- **White-label:** the word "Odoo" never appears in anything a user can see or receive (labels, tooltips, help,
  errors, toasts, .po msgstr). Technical identifiers, imports, xml ids, logs, comments and these docs keep it.
- **Plain English in product copy:** screen words only ("pay run", "pay scheme", "the connected system"), never code
  vocabulary (`net_role`, `value_kind`, "rung", "provenance").
- **Lessons follow screen changes** (owner 2026-10-12): any screen change updates the lessons, tours, anchors and
  replicas that describe it in the same phase.
- **Truth gate (this program):** nothing may name a field, a choice or a consequence unless it comes from the
  generated layer (P1 onwards). A build fails when authored text names a label that is not on the screen.
- **Commits:** feature-scoped, explicit paths (`git add <files>`), never `-A`; message = problem → fix → decisions;
  end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Fable pushes 19.1 after reading the report.
- **Deploy:** pick the tier (looks-only / normal / risky) and say which; stage ONLY the changed modules from
  `git archive HEAD` (never the working tree, never untracked dirs); before any stop / `-u` / restart, `ListAgents` →
  `SendMessage` the other live sessions and check the server for a running `odoo-bin --stop-after-init`; payobook
  first, then the other DBs (owner standing OK 2026-10-16); abm's scheduled jobs back OFF after an abm upgrade;
  asset purge + `web.assets.version` bump + `INSERT INTO orm_signaling_assets DEFAULT VALUES` per DB after JS/SCSS;
  one browser walk on payobook.com with the QA login; `docs/deploy/PENDING.md` row if any DB is skipped.

## Phases
| Phase | Scope | Status |
|---|---|---|
| **P0 Quick fixes** | Six live-product fixes with evidence: chat scroll on open (G4), lesson door target (G2), ⌘K rows after translations (G16), "calculated" lane label (G21), PayAI door dead end (G24), "Never reaches <component>" wording (G33). | handover written 2026-10-17 |
| **P1 Content engine** | Generator that reads field label/help/choices, "set by" markers, readers ("Used by"), buttons → methods, hub › tab path, for the first 8 screens; Guide schema; truth gate; EN+VI. | design next |
| **P2 Guide panel + field cards** | (i) on every label; six-section Guide panel (This screen / Right now / Fields / Tasks / Understand / Ask); "Right now" from screen state; PayAI answers from and cites the cards. 8 screens. | |
| **P3 Library** | New Learning page: Continue, path strip, screens listed like the sidebar, one search over everything; badges/streaks/ring removed; old page retired. | |
| **P4 Lessons + walkthroughs** | Steps in the Look at · It means · It affects · Press shape, one field a step, played in the panel beside the real screen; checked Try; guarded Do; replicas generated from screen definitions; country-aware statutory content. | |
| **P5 Everything else** | Remaining 56 screens; thumbs on every card/step; misses → Learn › Settings; full Vietnamese pass. | |

## Where things are (verified 2026-10-17, do not re-derive)
- Authoring: `docs/tutorial_poc/author/data.js` (screens `SCREEN_CTX`, stations, lessons, scenarios, glossary,
  columns, intents); generator `docs/tutorial_poc/author/tools/gen_learn_data.py` → `pb_learn/static/content/
  learn_content.json` (+ `learn_tenant_slots.xml`, `fixture.js`, `anchors.json` practice block, `i18n/vi_VN.po` —
  **the generator can WIPE vi_VN.po: `git checkout pb_learn/i18n/vi_VN.po` after a run, then re-add hand entries**).
- Client: `pb_learn/static/src/coach/` (drawer + screen resolution), `journey/` (Learning page), `scenario/`
  (Watch/Do overlay + service), `engine/` (places, screens replicas, fixture), `hub/` (Learn hub lenses, ⌘K rows).
- Server: `pb_learn/models/learn_intent.py` (probe / answer / explain), `learn_helper.py` (router), `learn_runtime.py`
  (bootstrap, `next_step_live`), `learn_content.py`.
- Chat: `pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.js` (+ `chat_patch.js` in
  pb_payai_actions); PayAI doors `pb_payai_actions/payai/resolve.py`.
- Component treatment: `pb_formula_studio/static/src/js/component_treatment.js` + `xml/component_treatment.xml`;
  data `hr.formula.config.value_kind_board` (`pb_hr_payroll_formula/models/formula_config.py:2383-2476`); fields on
  `hr.formula.rule` (`net_role`, `net_role_detail`, `component_type`, `payroll_signal`, `value_kind`, `*_source`).
