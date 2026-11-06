# LEARNREV P5 — every lesson in the new shape, the feedback loop, the Vietnamese pass (handover for Opus)

Program: `docs/handovers/learnrev/LEARNREV_PROGRAM.md` (standing rules verbatim there). Ledger: `LEARNREV_LEDGER.md`
(all rows LR-R1…R7, LR1–LR62; LR28 corrects the program doc: the generator merges vi_VN.po). Reports to read first:
`P4_REPORT.md` (the step shape, field steps, variants, checks, replica gate), `P3_REPORT.md`, `P2_REPORT.md`,
`P1_REPORT.md`. Design page: `docs/design/learn_revamp/LEARN_REVAMP_DESIGN.html` (gap table G1–G33; P5 closes G30
and the rest of G18/G22, and sweeps every "open item" the four reports left).

Work in the git worktree you are given (branch `learnrev-p5` from the 19.1 tip). No deploy in this phase (Fable
merges and deploys). Tests on a dump-based clone (AI off, LR17/LR26; server jobs via `systemd-run`, LR60; unique
file names, LR61; remote scripts in files, LR62).

## 0. Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." P5's hero moment is completeness: open ANY of
the 42 screens, press Understand, and every step reads Look at · It means · It affects · Press beside the real
control, in English or Vietnamese, with no sentence that names a label the screen does not show. Second hero: a
thumbs-down on any card or step reaches the authors as a topic count in Learn › Settings the same day. Zero dead
ends, plain screen words, never the word "Odoo", Lucide only, motion with purpose. Score every bullet 1–5.

## 1. Scope
- **S1 The other 31 lessons** (every lesson not rewritten in P4: all except L1, L2, L3, L5, L6, L8, L9, L31, L35, LA,
  LW) rewritten in the four-line shape, one idea a step, `field:` steps wherever a step is about a column of a
  manifest screen (P1 has manifests for 8 screens; for the 34 other screens write `look/means/affects` by hand from
  the screen's own template and `help=` texts, and cite the template line in a `source:` comment in data.js so the
  next manifest wave can replace them). Each lesson keeps its quiz; every rewritten step ≤ 28 English words a
  sentence; EN+VI; `press` only on product anchors; no retired labels (gate). Lessons whose screen cannot be reached
  by a normal reader (access-gated) keep their replica fallback.
- **S2 Walkthroughs**: the remaining 19 scenarios (all except the 6 P4 rewrote) in the four-line shape; `checks`
  declared for every scenario on a manifest screen where a real-state check is cheap and read-only (list them in the
  report); observe-only scenarios get a `press` only where the person really presses.
- **S3 Manifests for 8 more screens** (the next most-used, in this order): `approvals` detail drawer is covered; add
  `statutory`, `employees`, `import`, `matrix`, `records`, `payreview`, `govreports`, `wftime` — same schema as P1
  (§3 of `P1_HANDOVER.md`), truth gate, `used_by` from grep (never guessed), VI gaps closed in the product .po files,
  right-now providers where the screen already computes counts (statutory: no active policy / tax table; import:
  rows needing a match; matrix: routes needing people; records: pending applies).
- **S4 Feedback loop (G30).** The thumbs on field cards and lesson steps (P2 wired `rpc_feedback` to the event log
  with no free text) become a report: Learn › Settings gains a "What people asked and rated" card — per screen and
  per field/step: thumbs up/down counts (last 30 days), the helper's miss counts by screen (from `coach_miss`
  events, topics only), and the top 10 search phrases with no result (`library` search misses logged as a hashed
  phrase + the screen key, never the raw text unless the owner's collect-questions switch is on, per the existing
  consent rules in `learn_question.py`). Export as CSV from the card. Admins only (`base.group_system`), same as the
  other Learn settings.
- **S5 Vietnamese pass.** Every string P1–P4 added (chrome keys, manifests, variants, section titles, step lines,
  notes, Learn › Settings cards) reviewed for natural Vietnamese by one rule set: the terminology table in
  `pb_learn/i18n/vi_VN.po` and the glossary wins; no mixed-language sentence; diacritics correct; one translation
  per English string (the generator's duplicate-translation gate). Browser-check the Vietnamese Guide, Library,
  lesson and walkthrough on the clone. Also fix the pre-existing poor placeholder "Search surfaces, actions…" in the
  top search bar (P3_DEPLOY open item 3) and the tick wording mismatch "Đã tính trong tổng khác" vs "…một tổng khác"
  (P1_DEPLOY open item) — one wording everywhere.
- **S6 Open items sweep** (do each, or say why not in the report): P2 — Connections' Storage and Use in payroll tabs
  and an Approvals card with a request walked; the chat gets ≥ 50 % of the panel while a conversation is live (P4's
  fold handles the lesson case; verify the chat case). P3 — the Continue card's reason names the seat when the path
  rule carries one (add an optional `why` to `learn.path` rules; the role stays the fallback); ⌘K ranks the
  treatment "Pay role" row first (LR51: the screen whose own search words name the field wins, as the Library does).
  P4 — the replica fallback also announces itself in Vietnamese; `press` lines use the control's visible label in the
  reader's language.
- **S7 Replica generation — decision item, not build.** Write a one-page note `P5_REPLICA_NOTE.md`: what it would
  take to render the 8 manifest screens' practice copies from the Guide JSON + a fixture payload (reusing
  `ComponentTreatmentBoard readonly`, `JourneyBoard data`, `PayPreview`), the cost, and what the truth gate already
  guarantees without it. Fable takes it to the owner.

## 2. Binding non-goals
No change to PayAI tiers/gates/router beyond the search-miss logging seam; no lesson player or Guide layout changes
beyond S6; no stored content (the feedback report reads the existing event log — if the log lacks a field the report
needs, add it to the EVENT, not a new table); no sudo; no deploy; no new replicas (S7 is a note).

## 3. Verified plumbing (do not re-derive)
- Everything in `P4_HANDOVER.md §3` (lesson render, generator gates, scenario engine, live checks, country, progress,
  replay) and `P4_REPORT.md`. Step shape and field steps: `gen_learn_data.py` (P4 commit `92363dc48`), exporter
  `docs/tutorial_poc/author/tools/export_manifests.py`. Panel player: `pb_learn/static/src/coach/` (P4 `6aebe6295`,
  `2ac0a9bd7`). Checks seam `learn.scenario.check` (P4 `c8c1c2e9e`). Replica gate in `pb_learn/tests/guide_truth.py`.
- Feedback events: P2 `rpc_feedback` → the drawer's `_log` seam (`learn.event.log`); consent rules
  `pb_learn/models/learn_question.py` (collect switch `pb_learn.collect_questions`, `_flag_on`); Learn › Settings lens
  `pb_learn/static/src/hub/learn_settings.js` + `models/learn_settings.py` (`base.group_system` gate, `get_switches`).
- Manifest schema + gate: `P1_HANDOVER.md §3`, `pb_learn/models/learn_guide.py`, `pb_learn/tests/guide_truth.py`;
  readers grep strategy in `P1_HANDOVER.md §7`.
- Lesson inventory: 42 lessons / 296 steps; P4 rewrote 84 steps in 11 lessons; the 48 practice-only (`rep-*`) steps
  are listed in the P4 facts (keep their replica fallback). Scenario inventory (26) in the P4 facts.
- Search misses: Library search `pb_learn/static/src/journey/library.js` (P3); ⌘K rows `learn_palette.js`.

## 4. Tests
- **T1** generator gates green for all 42 lessons and 25 live scenarios; `--check` up to date; no sentence > 28
  words; every step has `look/means/affects` (legacy `body` now only on the 48 replica-only steps — list them).
- **T2** truth gate 0 errors across 16 manifests; replica gate 0; anchors registry green.
- **T3 Python** `test_learnrev_p5.py`: feedback report shape (counts per screen/field, no free text unless the
  collect switch is on; admin-only); search-miss logging stores a hash + screen key; `learn.path` `why` surfaces in
  bootstrap; ⌘K ranking rule; providers for the 8 new manifests return the §1 S3 items on fixtures.
- **T4** node suites (guide_panel, lesson_panel, library) + PayAI suites green; `replay_tests.py` ≥ baseline;
  `check_contract.py` only `grid-hint` (or fix that anchor if cheap — it is a Studio template anchor P2 may have
  retired; if the retired-list covers it, drop it from the contract instead).
- Full pb_learn suite on the clone; baselines test_07b, TestCoach.test_11 with AI on, pb_hub palette with a partial
  stage.

## 5. Browser checks (clone, Guide ON; headless Chrome on a fresh port; sign in via fetch)
B1 three lessons from three different areas (People, Workforce, Compliance) play in the Guide with the four lines
beside the real control; B2 a lesson on an access-gated screen falls back to the replica with the note (EN and VI);
B3 Learn › Settings shows the feedback card with counts after two thumbs and one failed search on the clone, CSV
downloads; B4 Vietnamese: Guide, Library, one lesson, one walkthrough, the top search placeholder; B5 Continue card
reason names the seat for a seat-based path; B6 ⌘K "pay role" ranks Component treatment first; B7 Connections
Storage / Use in payroll tabs with (i) and the Guide; an Approvals card with a request; B8 console clean. Screenshots
`p5_b*.png`.

## 6. Commits, report
Worktree branch `learnrev-p5`. Commits by scope item (S1 may be several, by product area). Explicit paths;
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; no version bumps; no push. `P5_REPORT.md` as the earlier
reports (+ the lesson/scenario inventory table showing every lesson now in the new shape, the 16 manifests, the
feedback card, the VI changes count), `P5_REPLICA_NOTE.md`, LR rows after LR62, open items. Report files are
written as `.md`; if refused, `.txt` and say so.
