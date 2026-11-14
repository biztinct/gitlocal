# WDGAP PR-C — Hold one person's pay (and pay them later)

Read first: `WDGAP_LEDGER.md`, then `WDGAP_PR1_FACTS.md` §3 "Hold one person's pay"
(verified plumbing, file:line — do not re-derive), then the PAY RUN SCREEN closeout docs
and memory `payrun-screen-program.md`, `multi-scheme-currency-gaps.md`.

You are the implementer AND tester/self-reviewer. You do NOT deploy. This phase sits on
the money-out path (bank file, payment release, payslip delivery): a held person must
never be paid by accident, and a not-held person must never be left out by accident.

## 1. Scope (module `pb_pay_delivery`, plus the review screen in `pb_payslip_review`)

1. **Hold** a payslip: `hr.payslip` gains `pb_pay_hold` (Bool, indexed), `pb_hold_reason`
   (required, min 6 characters), `pb_hold_by`, `pb_hold_on`, `pb_hold_released_by`,
   `pb_hold_released_on`. Actions `action_pb_hold(reason)` / `action_pb_release_hold()`.
   Allowed for the pay team (same groups that may prepare the bank file) on a payslip
   that is computed or finished, as long as it has NOT been paid (`pb_paid_on` empty) and
   is not already in a bank file that has been released.
2. **Where**: a "Hold pay" / "Release hold" action in the payslip review screen
   (`pb_payslip_review/static/src/xml/payslip_review.xml:146`, server
   `pb_payslip_review.py:428-446`) with an in-page reason box; and on Pay & deliver
   (`pb_pay_delivery/static/src/xml/pb_pay_delivery.xml:88-145`) a clear "On hold" group
   in the left-out list: who, why, by whom, amount — with "Release hold".
   A quiet "On hold" chip on the person's row wherever that run's payslips are listed in
   those two screens. The payslip itself is still calculated and approved with the run —
   holding stops the MONEY and the payslip delivery, not the calculation.
3. **Bank file leaves them out**: `_row_sources` (`bank_export_wizard.py:95-131`) excludes
   held slips with the reason "On hold" (shown with the other exclusion reasons;
   `excluded_json`/`excluded_count`, `bank_file.py:85`).
   `_control_total_matches_run` (`bank_file.py:233-241`) compares the file to the run's
   total **minus held slips** — and the screen says so: "Bank file 412,000,000 = run
   418,500,000 − 6,500,000 on hold (2 people)".
4. **Payment release marks only the people in the file as paid**: `_approval_apply`
   (`payment_release.py:289-292`) today stamps `pb_paid_on` on EVERY done slip in the run
   — change it to stamp only the slips that are in the released file. (This is also more
   correct for people excluded for other reasons, e.g. no bank details: check what the
   current behaviour means for them and keep their behaviour unless it is plainly a bug —
   if you change it, say so prominently in the report.)
5. **Payslip delivery skips them**: `_do_send` (`payslip_delivery.py:187-258`) does not
   send a held payslip; the delivery summary counts them ("2 not sent: pay on hold").
   The employee does not see a held payslip on My Payobook until the hold is released
   (`pb_me_portal/controllers/portal.py:500` reads done payslips — filter held ones;
   keep `pb_me_portal` edits minimal, or expose a small hook in `pb_pay_delivery` if
   `pb_pay_delivery` is not a dependency of the portal: check and choose the smaller change).
6. **Paying them later**: after a hold is released, Pay & deliver offers "Prepare a
   payment file for the 2 people released from hold" — a follow-up bank file for the same
   run containing only finished, not-yet-paid, not-held slips, with its own approval and
   its own release (which stamps only those slips). The first file and its release stay
   as they are: today a new file supersedes earlier ones (`bank_file.py:181`) and there
   is one release per file (`payment_release.py:113-118`) — a follow-up file must NOT
   supersede a file that has been released; it supersedes only unreleased ones. Payslip
   delivery then sends the released people's payslips ("Send the 2 that were held").
7. **Totals stay honest** on Pay & deliver (`pb_pay_delivery.py:224-257`): total
   take-home, of which on hold, of which paid, of which still to pay — per currency,
   never added across currencies.
8. **Audit**: hold and release each write a chatter line on the payslip and, if
   `biz_audit_trail` has a one-call entry point, an audit entry (else chatter only).
9. A run flag (clone `review_flags.py:49`): "2 people's pay is on hold" so the approver
   of the run / bank file sees it; the bank-file approval detail lists the held people.

## 2. Binding non-goals

- No partial hold (hold part of the net), no automatic holds (missing documents, exit
  clearance — the offboarding gate already exists), no change to full & final, no hold on
  draft runs' calculation, no new approval process for the hold itself (reason + audit;
  report whether you recommend a second person), no change to bank file layouts.
- Do not edit `pb_payruns`, `pb_payrun_wizard`, `pb_hr_payroll_formula`, `pb_updates`,
  `pb_approval_config` code, `pb_pack_*`.

## 3. Safety rails

R1. A held slip can never get `pb_paid_on`, appear in a prepared file, or be delivered —
    assert each with a test, including the race "hold placed after the file was prepared
    but before it was released": preparing a release re-checks, and a file containing a
    now-held slip is refused with a plain sentence telling the user to prepare the file
    again.
R2. A slip already paid, or in a released file, cannot be held (plain refusal).
R3. Nobody not held is dropped: with zero holds every output (file rows, control total,
    delivery list, paid stamps for people in the file) is identical to today — golden
    test against the unchanged code on the same fixture.
R4. Follow-up file: never includes anyone already paid; never supersedes a released
    file; the sum of all released files for a run + still-held + other-excluded = run total
    (test the identity).
R5. Rights: only the pay team; an employee cannot see or lift their own hold. Multi-company.
R6. Demo world (`pb_demo` overrides, `payment` demo bank details): the demo Pay & deliver
    walk still works unchanged with no holds.
R7. White-label, plain words, quiet chips, Lucide icons; `vi_VN.po` for
    `pb_pay_delivery` and `pb_payslip_review`; PO gate; version bumps.

## 4. Numbered test cases (T = Odoo test; write and run)

`pb_pay_delivery/tests/test_wdgap_prc_hold.py`.
1. T Hold needs a reason; sets by/on; release sets released by/on; chatter lines.
2. T Held slip excluded from the file with reason "On hold"; control total matches
   run − held; without holds identical to golden (R3).
3. T Release stamps `pb_paid_on` only on slips in the file; held stay unpaid.
4. T Delivery skips held; counts reported; portal list hides held payslip, shows it after
   release.
5. T Race (R1): hold after prepare → release refused; re-prepare works.
6. T Cannot hold a paid slip or one in a released file (R2).
7. T Follow-up file: only released-from-hold, unpaid slips; own approval/release; first
   released file untouched; identity of sums (R4).
8. T Two currencies in one run: totals per currency.
9. T Rights and company rules (R5).
10. T Existing suites `pb_pay_delivery` (`test_pay_delivery`, `test_money_out`),
    `pb_payslip_review`, `pb_me_portal` payslip tests — failure set equals baseline.
11. Browser, local copy: hold one DEMO person from review, see the chip and the Pay &
    deliver group, prepare the file (person absent, totals sentence right), release
    payment, deliver payslips, release the hold, prepare the follow-up file, send the
    held payslip; console clean.
12. Static gates.

## 5. Working rules

- NEW git worktree from `origin/19.1` (after the QF merge is pushed), branch `wdgap-prc`.
- Feature-scoped commits, explicit paths; push. Do NOT merge. Do NOT deploy.
- Commit messages end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- Usage-limit error → WIP commit, "Where I stopped", PAUSED. Drop test databases.

## 6. Report back — `docs/handovers/wdgap/WDGAP_PR_C_REPORT.md` (commit it)

What was built; test table + suites vs baseline; self-review R1–R7; exactly what changed
in who gets marked "paid" on release (scope item 4) and what it means for people excluded
for other reasons; follow-ups; owner questions in plain words (e.g. "Should lifting a
hold need a second person?"); deploy notes (RISKY: money-out path; new stored fields);
new gotchas → ledger.

Final message: under 250 words.
