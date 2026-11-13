# LEARNOS Phase 6 — Companion senses: voice, egress closure, personalization, skill tree (DRAFT until Phase 5 merges)

Read both ledgers + accepted reports 4/5. Scope: pb_learn + pb_payroll_ai_insights + author
sources. No deploy, no commit. All features OFF by default per tenant.

## Why
The companion gets senses and memory — voice in/out, honest "what should I learn next", and
a Journey that celebrates progress — while the LAST known egress gaps close: the dead
provider calls in voice + PDF-report paths get fixed WITH redaction (the Phase-4 ruling:
"the fix and the redaction are one change or neither"), and conversation history gets the
per-conversation persistent mapping that fully closes the Phase-4 named residual.

## Verified facts (from Phase 4 review; re-verify against the merged tree)
- `get_provider_instance()` does not exist; surviving dead call sites pinned by
  `test_egress::test_02b` exact-count: `payroll_ai_conversation.py: 1` (voice),
  `payroll_ai_report.py: 2` (section narratives + exec summary). Fixing the lookup without
  redaction OPENS unredacted egress — `_generate_section_narratives` puts
  `json.dumps(section['data'])[:2000]` in a prompt.
- `ai_redaction.py`: collect/redact/restore + generic_scrub (Phase-4 fix round); named
  residuals: history prior-turn names, dict keys, mixed-diacritic partials.
- Whisper/TTS plumbing: openai provider `transcribe_audio` + `text_to_speech`;
  `rpc_send_voice_message` sends base64 audio out (raw voice egress — must be
  consent-gated and documented).
- Progress/confidence: learn.progress key-namespaced rows, learn.confidence awards.
  learn.event kinds whitelist. Journey map: LINE_ORDER, stations, doneCount, badgeEarned.

## Scope

### 6.1 Egress closure (privacy first, the rest rides on it)
- **Per-conversation redaction memory**: persist the placeholder↔name mapping per
  payroll.ai.conversation (new model field or aux table, GC'd with the conversation);
  every turn REUSES + extends it; history redaction on ALL paths uses the accumulated
  mapping (closes the Phase-4 named residual). Placeholders stay stable across turns so
  the model's own references stay coherent.
- **Report narratives**: `get_provider_instance` → `get_provider` in payroll_ai_report.py
  AND redact `section['data']` through the same redactor before any prompt; restore in the
  rendered narrative. Update test_egress::test_02b's exact-count pin (voice-only remains).
- **Voice**: fix the conversation.py voice call site the same way; the transcribed TEXT
  enters the normal engine path (already redacted); the AUDIO egress itself is gated behind
  a new per-user consent (reuse learn.consent pattern — server-side, double-gated with a
  tenant flag `payai.voice_enabled`, off by default) and the privacy note names it.
  TTS output of a reply containing restored names is user-facing (inside trust boundary) —
  fine; document.
- Dict-key redaction guard: `redact_names` gains key handling for mapping-shaped payloads
  (walk keys too when the dict is data, with the PERSON-key heuristic documented) — or the
  pulse `by_type` site gets a structural test forbidding person-keyed maps. Pick one,
  justify.

### 6.2 Voice UX (pb_learn/PayAI drawer)
- Mic button on PayAI pill + coach drawer (flag-gated, consent-gated): hold-to-talk →
  Whisper → the text lands in the ask bar for CONFIRMATION (never auto-submits — the
  learner sees what was heard before it goes anywhere); reply optionally spoken via TTS
  (per-user toggle, remembers preference). Register-simple copy EN+VI via author source.
- Degrades: no provider/flag/consent → button absent (never disabled-with-tooltip).

### 6.3 "What should I learn next?" (pure local heuristics — NO egress)
- `learn.runtime.next_best()` server-side over own-rows progress/confidence/events:
  in-progress station first; then the station whose line has highest completion (finish
  the line); then the next unstarted required station in LINE_ORDER; live capstone offered
  only when gate_open. Returns {key, kind, reason:P} with an authored reason sentence per
  rule (chrome keys, both languages).
- Surfaced: Journey map hero strip ("Continue: …") + Coach drawer "not sure" state +
  activation checklist's meet/practice rows when partially done. Structural test: next_best
  reads ONLY learn.* models (model-scope check).

### 6.4 Skill tree + streaks (Journey map)
- Per-line progress rings on the map headers (done/total per line, CSS rings — reuse
  pb_dashboard ring idiom, design-system colors, no gradients/emoji); station cards gain
  subtle done-tier styling (bronze/silver/gold = first-try-correct ratio from existing
  progress fields — derived, never stored).
- Streak = consecutive DAYS with ≥1 learn.event (computed server-side from own events,
  capped display "7+"); shown in Journey header with an honest tooltip; NO notifications,
  NO shame states (a broken streak just resets quietly).
- All copy register-gated EN+VI; celebration = the existing check-draw idiom, once.

## Non-goals (binding)
- No push/email notifications. No gamification currency/leaderboards (privacy: no
  cross-user comparison anywhere). No new provider stacks. No auto-submitted voice. No
  personalization data leaving the server (next_best is a server computation over own
  rows; nothing goes to any LLM). No cron additions except conversation-mapping GC if
  needed (noupdate, documented).

## Tests (numbered)
1. All gates green; contract gains: voice-is-consent-gated, next-best-reads-learn-only,
   report-prompt-is-redacted (structural), updated egress exact-count pin.
2. Redaction round-trip tests for report + voice paths; per-conversation mapping
   stability across 3 simulated turns (offline harness); negative controls: bypass the
   report redaction → test fails; auto-submit the transcription → test fails.
3. next_best decision table unit tests (each rule + tie behaviour + empty-progress case).
4. Streak computation tests (timezone edges: compute in user tz, document).
5. Register/jargon gates on all new copy.

## Report back
Per-file summary; the redacted report-prompt template verbatim; next_best decision table;
consent/flag matrix (who sees the mic when); deviations; ledger candidates; deploy-time
Chrome script (voice consent flow, next-best strip, rings/streak, report narrative).

## Kickoff
"Implement docs/handovers/LEARNOS_PHASE6_HANDOVER.md exactly. Read it and both ledgers
first. Worktree only; no deploy, no commit; leave the tree for review."
