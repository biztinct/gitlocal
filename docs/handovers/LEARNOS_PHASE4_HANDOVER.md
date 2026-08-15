# LEARNOS Phase 4 — Ask-anything companion + explain-this-screen + egress hardening (DRAFT until Phase 2/3 merge)

Read both ledgers + accepted 1a/1b/2/3 reports. Scope: pb_learn (coach surfaces + one new
endpoint), pb_payroll_ai_insights (the two unscrubbed egress paths + the dead provider call
they share). No deploy, no commit.

## Why
The Coach already answers from curated content with an honest miss. This phase makes it feel
like a companion: every answer offers "Watch" / "Try" when a scenario covers the ground, any
screen can explain itself in plain words, and the two known holes where PayAI sends real
names to the LLM are closed. Privacy rails are copy-paste from pb_learn (ledger rule 3).

## Verified seam facts (re-verify only if the 2/3 merges touched them)
- ask() ladder + composer: pb_learn/models/learn_intent.py (file-backed since 1a; flag
  `pb_learn.compose_enabled` off by default; `_scrub`; advice deny-list; source badging).
- Scenario show_me targets (`scenario:<key>#<step>`) + coach "Show me how": 1b report.
- Content plane accessors: learn.content (screens/columns/chrome/glossary/scenarios).
- PayAI egress holes: `payroll_ai_engine.py` `_process_data_query` sends
  `json.dumps(payroll_data)` verbatim (names included) into the prompt (~:243 pre-2 line
  numbers); `payroll_ai_pulse.py` `_generate_ai_summaries` (~:328) sends alert payloads
  carrying employee names (~:196,211). NOTE: pulse + voice call `get_provider_instance()`
  which DOES NOT EXIST on payroll.ai.config (only `get_provider()`) — the pulse path is
  currently dead code that would crash if reached. Data queries run as the asking user with
  refusal short-circuits BEFORE the provider (`payroll_ai_engine.py:227` area) — do not
  disturb that ordering.

## Scope

### 0. Coverage + honesty fixes found by the Phase-1 live validation (binding)
- **Author the missing obvious intents**, starting with "How do I run payroll" (the live
  validation found the product's most obvious question has NO corpus entry) — sweep the
  suggest chips + real pb_learn coach_miss patterns for other gaps; add ≥6 new intents with
  phrases in both languages.
- **Fix the screenless weak-match**: with screen context the resolver honestly refuses, but
  on the screenless Journey the same question keyword-matches a wrong-topic intent and shows
  it with a "Grounded in" badge — a badged wrong answer is worse than a miss. Raise the
  screenless match threshold (or require ≥2 strong token hits when screen_key is null) and
  add both cases to simulate_resolver's probes.

### 1. Answers that teach (pb_learn)
- Author-side: each intent MAY declare `watch`/`try` scenario targets (extend the QA schema +
  emitter; validate keys like show_me). Coach `_answerHTML` renders [Watch] [Try] buttons when
  present (reuse the existing c-scenario action; Try only when the scenario has try mode).
- A "Not sure what to ask?" state: when the drawer opens with no question, show the current
  screen's suggest chips + its scenarios + "Explain this screen" (below).

### 2. Explain-this-screen (pb_learn)
- New button in the Coach drawer header (Lucide info icon) + chrome strings (register rules).
- Server: `learn.intent.explain_screen(screen_key, lang)`:
  1. DETERMINISTIC FLOOR (always works, offline): compose from the content plane — screen
     blurb + next_step (live-rendered via learn.runtime) + the screen's top columns (≤4) +
     matching scenarios, as blocks in the existing answer-block shape so the drawer renders
     it with zero new UI. Badge `source_kind: 'screen'`.
  2. If composer flag enabled AND provider configured: optionally rewrite the floor text
     with the composer under the EXACT existing gates (corpus-only prompt, scrub, caps,
     NO_ANSWER refusal → fall back to the floor, badge 'composed'). The prompt carries the
     screen key and content-plane text ONLY — never records, never user data.
- Contract checks: `explain-screen-reads-content-only` (model-scope on the new method —
  learn.* namespace only), `explain-screen-has-deterministic-floor` (structural: the
  provider branch is behind the flag read + the floor return exists without it).

### 3. PayAI egress hardening (pb_payroll_ai_insights)
- New shared module `models/ai_redaction.py`: `redact_names(payload) -> (redacted, mapping)`
  and `restore_names(text, mapping)`. Names → stable placeholders (`[person-1]`…); reuse
  pb_learn's `_ascii` tone-fold matching idea so accented/unaccented forms both catch; also
  scrub emails/phones with the existing pb_learn regex family (copy, don't import across
  modules — document the duplication with a pointer comment both ways).
- `_process_data_query`: redact BEFORE building the prompt; restore placeholders in the
  reply before returning to the user. The asking user was entitled to the names (access
  gate already passed) — the LLM was not.
- `payroll_ai_pulse.py`: fix `get_provider_instance()` → `get_provider()` (ticket 4, pulse
  half only — voice stays for Phase 6), then redact alert payloads the same way. If pulse
  output is user-visible text containing names, restore after; if it is stored, store the
  restored text (DB is inside the trust boundary; the wire to the provider is not).
- Tests (offline, no provider): unit tests that a payload with VN names (accented + folded),
  emails, phones yields a prompt string containing NONE of them (assert on the exact prompt
  the engine would send — factor prompt-building so it is testable without network); the
  restore round-trip; pulse path no longer references get_provider_instance (grep test).
- NEGATIVE CONTROL (mandatory, like 1b): temporarily bypass redaction → the no-names test
  fails; restore → green. Report both runs.

### 4. Enablement UX (small)
- Training menu (author group): a one-page "Companion settings" form-less view or wizard
  showing composer flag state + provider-configured state per company, with an enable/disable
  action gated on group_learn_author + base.group_system. Flag stays OFF by default
  everywhere; enabling is per-DB (tenant) and logged in the chatter/log.

## Non-goals (binding)
- No voice, no personalization, no skill tree (Phase 6). No new provider stacks — everything
  through payroll.ai.config. No change to ask()'s public contract shapes beyond ADDING
  optional watch/try keys. No relaxation of any existing gate (refusal-before-provider,
  advice deny-list, consent, caps). Real record data NEVER enters any prompt — the redaction
  is for the two legacy paths, not a license for new data egress.

## Tests (numbered)
1. Generator/--check/contract (with the two new checks)/resolver sim/replay green; node/py
   compile clean.
2. The redaction suite + negative control (above) with real output.
3. Offline replay: explain_screen floor for 3 screens × both languages (assert block shapes,
   live-token fallback, no provider touched when flag off).
4. Grep-proofs: no `get_provider_instance` anywhere in pb_payroll_ai_insights except the
   voice path (list what remains for Phase 6); `json.dumps(payroll_data)` no longer feeds a
   prompt unredacted (structural: the prompt builder takes only the redacted variable).
5. Register conformance for all new chrome strings (jargon lint green).

## Review requirements (binding — Opus reviewer, adversarial egress pass)
- Read EVERY line of ai_redaction.py, the changed prompt builders, and explain_screen.
  Hunt: any variable reaching a prompt string that transits record data; placeholder
  collisions; restore() applied to stored-but-unrestored text; the flag-off path touching
  the provider; prompt-injection via content (the corpus is trusted, but tenant fact slots
  are tenant-authored — verify tokens are NOT interpolated into any LLM prompt, or are
  scrubbed if they are).
- Execute the negative control independently.

## Report back
Per-file summary; the exact prompt template(s) after hardening (verbatim); redaction unit
outputs; the enablement UX screenshots-script; deviations; ledger candidates.

## Kickoff
"Implement docs/handovers/LEARNOS_PHASE4_HANDOVER.md exactly. Read it and both ledgers first.
Local-only; no deploy, no commit; leave the tree for review."
