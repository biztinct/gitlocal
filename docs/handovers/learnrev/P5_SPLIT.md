# LEARNREV P5 — split between two builders (owner decision 2026-10-18)

The owner chose to split P5 (`P5_HANDOVER.md`) by the kind of work: structured, gate-checked work goes to Sonnet now;
writing quality (lessons, walkthroughs, natural Vietnamese) goes to Opus afterwards, on top of P5a.

## P5a — Sonnet (branch `learnrev-p5a` from 19.1)
- **S3** Manifests for the 8 screens (statutory, employees, import, matrix, records, payreview, govreports, wftime),
  truth gate, `used_by` from grep, right-now providers, VI gaps closed in the product .po files (plain, correct
  Vietnamese using the `pb_learn/i18n/vi_VN.po` terminology; Opus reviews them in P5b S5).
- **S4** Feedback loop: the "What people asked and rated" card in Learn › Settings, search-miss logging (hash +
  screen key unless the collect switch is on), CSV export, admins only.
- **S6, P2 + P3 items only**: Connections Storage / Use in payroll tabs with (i) and the Guide; an Approvals card with a
  request; chat ≥ 50 % of the panel while a conversation is live; `learn.path` optional `why` on the Continue card;
  ⌘K ranks the treatment "Pay role" row first.
- **S5 two small fixes only**: the English top-search placeholder "Search surfaces, actions…" reworded in plain screen
  words; the tick wording "Đã tính trong tổng khác" vs "…một tổng khác" made one wording everywhere.
- Tests: T2, T3 (all of `test_learnrev_p5.py` except lesson/scenario items), T4, full pb_learn suite on a clone.
  Browser: B3, B5, B6, B7, B8, plus the Guide on each of the 8 new manifest screens (four sections filled, (i) cards).
- Report: `P5A_REPORT.md`; LR rows after the last one in the ledger.

## P5b — Opus (after P5a is merged into 19.1)
- **S1** the 31 lessons, **S2** the 19 walkthroughs (+ `checks`), **S5** the full Vietnamese pass (including a review
  of P5a's new VI strings), **S6 P4 items** (replica fallback note in Vietnamese; `press` lines in the reader's
  language), **S7** `P5_REPLICA_NOTE.md`.
- Tests T1, T2 (anchors/replica gate), T4; Browser B1, B2, B4, B8.
- Report: `P5B_REPORT.md`.

Everything else in `P5_HANDOVER.md` (design bar, non-goals, plumbing, clone rules, commit rules) binds both builders.
