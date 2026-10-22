# LEARNING L4 — Sessions, attendance and toolbox talks — report

Implementer: Opus, 2026-10-22. Spec: `L4_SESSIONS_SIGNOFF.md` minus the LD5 cuts (no practical sign-off). Ledger: `LEARNING_LEDGER.md`.
Status: **BUILDING** (see "Where I stopped").

## Where I stopped

- WIP commits `029e4c178` and the one after it (pb_training 19.0.1.8.0): models, facade, screens, portal pages, mails,
  reports, LD11, tests, Vietnamese (288 new entries, PO gate 1,456 rows / 0 empty), demo seed `l4_demo_seed.py`.
- Full suites on a fresh copy (`-u pb_training`, `/pb_training,/pb_training_growth,/pb_learning_hub`): 369 tests,
  3 failed — the 2 known `TestTheAssignmentsTab` and the L0 rail test that pinned Courses to one tab (fixed since).
- Local walk (am_l4_walk, port 8072) got as far as: Overview Sessions block + chip, Sessions tab week strip, day filter,
  cards, session page, remove-a-booking promotes the next person waiting, Start the session → attendance screen.
- **Found in the walk:** the QR picture is broken. The stock `/report/barcode` route answers 500 locally AND on the
  live box (reportlab has no `rlPyCairo` backend) — handover fact F3 is wrong. Next: draw the QR ourselves with the
  `qrcode` library (present locally and live, 10.2.0) as an inline SVG data URI, for the screen and the PDF sheet.
- Then: finish the walk (manual ticks, live count, close, toolbox drawer, Book people drawer, New session drawer,
  My learning "My sessions", portal block, scan page, Vietnamese), the report, the deploy plan.
