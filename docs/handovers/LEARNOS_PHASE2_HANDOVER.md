# LEARNOS Phase 2 — Novice language + glossary everywhere (DRAFT until 1b accepted)

Read both ledgers + the accepted 1a/1b reports first. Scope: docs/tutorial_poc/author/
(data.js, practice-data.js, tools) + the glossary-hovercard UI in pb_learn/static/src.
No engine changes beyond the hovercard renderer. No deploy, no commit.

## Why
The current copy is written for payroll-literate readers. The product promise is that a
complete beginner can learn payroll from the app alone. Every learner-facing sentence gets
rewritten to a "teaching a novice" register, in BOTH languages, and every unavoidable
technical term becomes a tap-to-understand glossary hovercard.

## The register (binding rules for every rewritten string)
1. Short sentences. One idea per sentence. Target ≤ 16 words average, hard-flag > 28 (EN).
2. Everyday words: "money taken out" before "deduction" — then NAME the term once, linked to
   glossary: the first occurrence of a technical term in a lesson/step teaches it inline
   ("BHXH — the social insurance everyone pays into"), later occurrences rely on the hovercard.
3. Active voice, second person: "You press Compute. Payobook calculates every payslip."
4. Never assume prior payroll knowledge; DO assume common sense. Explain WHY before HOW when
   the why is one sentence.
5. Numbers stay exact (contract checker still pins every product fact — the rewrite may not
   change any fact, code, key, anchor, or `{{token}}`).
6. Vietnamese is a PEER rewrite, not a translation: same rules applied natively (terminology
   per the existing VI conventions in data.js — e.g. "trình phê duyệt" rulings from the
   pb_learn VI audit). Both languages edited in the same author-source change.
7. Warm, never cute. No exclamation marks except celebration moments. No jokes in
   consequence/warning copy.

## Scope
1. **Rewrite** all learner-facing prose in `data.js`: I18N chrome, STATIONS (name/summary/
   outline), LESSONS (all step kicker/title/body/tip/consequence, quiz prompts/options/
   feedback), MISSIONS (+steps/options/notes/consequences/anomaly/did/check), SCENARIOS
   (from 1b), SCREEN_CTX (blurbs/next_step), QA intents (labels/simpler/blocks), COLUMNS,
   GLOSSARY (definitions become novice-first). `practice-data.js` label strings only where
   learner-facing (B() pairs); never values.
2. **Glossary expansion**: every technical term used anywhere in the content gets a glossary
   entry (target: complete coverage of the jargon-lint list). Definition format: one plain
   sentence + one "why you care" sentence, both languages.
3. **Hovercard UI** (pb_learn/static/src): a render-time pass that wraps known glossary terms
   in already-safe HTML bodies with `<span class="lrn-gloss" data-gloss="<key>">`; a single
   delegated hover/tap card (reuse the coach card visual language) showing term + definition +
   "More" linking into the glossary. Applies in: Journey lesson/mission bodies, Coach answers,
   scenario cards. MUST NOT wrap inside `<code>`, values, anchors, or attribute text; longest-
   match-first; each term at most once per rendered block; language-aware (match EN terms in
   EN render, VI in VI).
4. **Jargon lint** (generator): new author tool gate — a curated `JARGON` list in the author
   tools (seed it from the content itself: extract candidate terms) with three states:
   `glossary` (must exist in GLOSSARY — else fail), `banned` (fail if used at all — e.g.
   "remuneration", "utilize", "aforementioned"), `allow` (explicit exceptions, with reason).
   Plus the sentence-length flag (>28 words EN = fail, 17-28 = warning listed in output).
   Runs inside gen_learn_data.py; `--check` covers it.
5. **Readability report**: generator prints per-section avg sentence length EN so drift is
   visible in every future content commit.

## Non-goals (binding)
- No fact changes (contract checker must stay green with UNCHANGED fact assertions — if a
  rewrite breaks a `contains` check, the rewrite is wrong, not the check… unless the check
  pinned prose style rather than a fact; those may be updated with a per-check note).
- No schema/engine changes except the hovercard pass. No new RPCs. No pb_coach resurrection.
- Column letters, codes, keys, anchors, tokens, live fallback semantics untouched.

## Tests (numbered)
1. Generator + jargon lint + `--check` green; readability report captured in the phase report.
2. Contract checker green; list any prose-style checks updated (with before/after).
3. parity_check.py is NOT expected green vs 6add0cc2 (content changed by design) — instead
   run it with `--rev <1b-commit>` if only comparing structure, or skip with a note.
4. Resolver simulator green (phrases may be extended, never removed — misses must not grow;
   re-run the 6 miss probes + 11 advice probes).
5. Hovercard: node --check; a JSDOM-free unit test of the wrapper function (pure string in/out)
   covering: longest-match, once-per-block, no wrapping in code/anchor/attr, VI matching.
6. Spot diffs in the report: 10 before/after pairs (EN+VI) drawn from the worst old offenders,
   including at least one station outline, one lesson step body, one refusal, one quiz feedback.

## Review requirements (for the reviewer, binding)
- A dedicated VI audit pass: sample ≥40 rewritten VI strings across sections against the
  register rules + existing VI terminology rulings; hunt calques and machine-gloss syntax.
- A fact-drift pass: diff every numeric/code/term-of-art token between old and new content
  (script it); zero unexplained changes.

## Report back
Per-section rewrite coverage %, readability before/after numbers, jargon-lint list size and
states, the 10 spot diffs, VI terminology decisions, ledger candidates.

## Kickoff
"Implement docs/handovers/LEARNOS_PHASE2_HANDOVER.md exactly. Read it, both ledgers, and the
accepted 1a/1b reports first. Local-only; no deploy, no commit; leave the tree for review."
