# pb_learn Phase D — Implementation Handover (Run D1 + Run D2)

**Read first:** `docs/handovers/PBLEARN_LEDGER.md` (ALL sections), design_v2.html §6-§7.
Phases A–C are merged. This is the final phase: intelligence — with the same honesty
rules that got us here. All content via `docs/tutorial_poc/author/` + generator.

## Binding non-goals

- The composer NEVER invents domain facts. Retrieval-first order is unchanged:
  curated intents → column glossary → (NEW, flag-gated) composer → honest miss.
- Nothing here weakens the Phase B live-surface guarantees (read-only, gated).
- No pb_coach changes (deploy-time retirement steps remain deploy-time).

---

# Run D1 — PayAI data-egress hardening (prerequisite, independent value)

The design_v2 §6 audit found: `payroll.data.query` runs `.sudo()` throughout, so PayAI
chat can leak data the asking user cannot read; `_query_individual_data`
(payroll_data_query.py:573-604) sends employee names + titles + salaries (limit 20)
to the external provider.

1. **Drop `.sudo()`** across `payroll.data.query` — answers respect the asker's
   access rights; catch AccessError → a friendly "your role can't see that data"
   response (bilingual, honest — reuse the refusal tone from pb_learn).
2. **Gate the individual path**: `_query_individual_data` requires
   `group_payroll_base_manager` or `group_payroll_final_approver`; below that, return
   the aggregate answer + the refusal note. (Do not pseudonymise in this phase —
   gate first, smallest correct change.)
3. Regression care: the demo world's PayAI must keep working for demo users (their
   record rules already grant broad read — verify against pb_demo/security/).
4. Tests: an officer-level ask on individual salaries gets the gated answer; a
   manager gets data; no `.sudo(` remains in payroll_data_query.py (source-scan test,
   contract-check style).

Commit: `fix(pb_payroll_ai_insights): data queries respect the asker's rights; gate individual salaries`.

# Run D2 — the composer seam + question mining

## D2-1 · Composer (port health_learn's, adapted; OFF by default)

- Port `_scrub / _corpus / _compose` from
  `/Users/adity/Documents/GitHub/health19/addons/health_learn/models/learn_intent.py`
  (l.410-520 region) into pb_learn's `learn_intent.py`, with:
  - **Provider seam**: `pb.payroll.ai.config.get_provider_instance()` — the same
    acquisition PayAI uses (payroll_ai_config.py:167 `get_provider`; instances via
    `get_provider_instance()` as seen at payroll_ai_conversation.py:212). Soft
    dependency: any exception → None → deterministic fallback. Do NOT import PayAI
    python modules at file top level — resolve via `self.env['pb.payroll.ai.config']`
    guarded by `'pb.payroll.ai.config' in self.env`.
  - **Flag**: `ir.config_parameter` `pb_learn.compose_enabled` (absent/false = off).
    `ask()` consults it AFTER column-glossary, BEFORE the honest miss.
  - **Scrub**: health_learn's regexes (email/phone/#ids/long numbers) PLUS
    VND-amount patterns (digit groups with . or , separators ≥ 5 digits) and the
    demo employee names present in the fixture (small static list) — payroll-grade.
    400-char cap unchanged.
  - **Corpus**: pb_learn's own content (stations/lessons/intents/columns/glossary,
    12k cap) — never database records. Prompt forbids inventing rates/amounts,
    requires literal NO_ANSWER; discard empty/NO_ANSWER/overlong (>1500 chars).
  - **Badge**: answers carry `source_kind: 'composed'`; coach.js renders the
    existing-style badge "Composed from the guide" / "Tổng hợp từ tài liệu hướng dẫn"
    (chrome string, generator-owned).
  - **The advice deny-list still runs FIRST** — a composed answer can never be
    reached by a question the deny-list catches.
- Contract checks: composer only reachable behind the flag (source check);
  scrub patterns present; corpus builder reads only learn.* models (no product
  model tokens in its source).
- Tests: flag off → miss path identical to Phase C; flag on + no provider → miss;
  NO_ANSWER → miss; scrub removes a salted sample of emails/amounts/names.

## D2-2 · Question mining (opt-in, deletable — the F7 completion)

- New model `learn.question`: `user_id, company_id, screen, question (Char 200),
  lang, occurred_at` — **ordinary model, deletable** (unlink allowed to the author
  group; users can delete their own). NOT `learn.event` (append-only stays clean).
- Opt-in: `ir.config_parameter` `pb_learn.collect_questions` (off by default) AND a
  per-user consent boolean surfaced in the Coach drawer the first time it would
  record ("Help improve the guide — store the questions I ask?" / bilingual;
  decline remembered). Both must be true before coach.js sends the question text;
  otherwise behaviour stays exactly as Phase B ruled (key-only).
- Author view: simple list grouped by screen with a "misses only" filter (join
  against coach_miss counts is unnecessary — record `matched` boolean on the row).
- Retention: `autovacuum`-style cron deleting rows older than 180 days.
- Tests: nothing recorded without both flags; user delete-own; author delete-any;
  the drawer consent renders once and is remembered.

Commit: `feat(pb_learn): Phase D2 — flag-gated composer + opt-in question mining`.

Report per established format after each run: done/how, the scrub pattern list, the
prompt text, verification outputs, no-regression, deviations, server-only, ledger,
commit hashes.
