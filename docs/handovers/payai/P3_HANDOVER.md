# PAYAI P3 — Red tier + Learn tie-in (handover for Opus)

## P2 is LIVE on payobook (pb_payai_actions 19.0.2.1.0, 2026-10-12) — walk findings to fix FIRST (P3-W1…W6)
Fable walked P2 on payobook.com with the QA login through the chat's own RPCs (the DevTools browser was held by
another session): run_payroll clarify ("Which Retail scheme do you mean?") → plan card (Period said / Scheme chose /
Company default / People "All 902 covered" / Pay data default; notes; Do it · Open in the screen instead · Cancel;
"Nothing has been done yet. This plan is good for ten minutes.") → Cancel ✓; existing October run → blocked card ✓;
submit_run plan → voice confirm with the switch off refused ✓ → Do it (run 791 → approval_pending, "It is with Demo
User now", Withdraw 10 min) ✓ → Undo (draft again, "Withdrawn") ✓ → Undo twice idempotent ✓; audit rows redacted
("[person-1]", "[amount]") and plain in the Audit console ✓. Fix these in P3's first commit:
- **P3-W1 People slot not split.** "Run December 2026 payroll for Retail End-Month for Vũ Khánh Chi only" → the
  scheme slot swallowed "Retail End-Month for Vũ Khánh Chi only", the person was dropped, and the question read
  "Which Retail End-Month for Vũ Khánh Chi only scheme do you mean?". Teach the phrase table (and the tools prompt)
  to split "for <scheme> for/only <people>" / "for <people> only" into the scheme and people slots; resolve people
  via `eligible_preview` on the chosen scheme; the plan card's People row then reads "Vũ Khánh Chi (1 of 902)".
  Also cap the echoed word in the clarify question: echo `said` only when it is ≤ 3 words and contains no
  name-like token; else fall back to "Which scheme do you mean?". Tests: the sentence above → scheme Retail End-Month
  (assumed/said), people = 1 named person; a one-person run computes 1 payslip on the clone.
- **P3-W2 Grammar.** Blocked title "A October 2026 run … already exists" → use "An" before a vowel sound, or rephrase
  "There is already an October 2026 run for …". Sweep every card title built with "A %s" for the same.
- **P3-W3 Pay-value dead end.** "Give <person> a meal allowance of 500,000 …" where no "meal allowance" exists on the
  person's scheme → a refused card with only a door. Zero-dead-ends: offer the closest pay values on that scheme as
  clarify chips (difflib over the Desk cards' labels, ≤6, sublabel = current value) plus "Open People › Records".
- **P3-W4 Send payslips offers drafts.** The run chips for send_payslips listed a Draft run ("Corporate Office Jun
  2026 — Mid-Cycle Advance · Draft"). Filter candidates to done runs; if none, say "No approved run for <month>
  yet" with the Runs board door.
- **P3-W5 Cancel on a clarify card.** rpc_cancel_task on a task in state `clarify` left it `clarify` (task 15) —
  make cancel move clarify → cancelled with the same audit line as a plan cancel.
- **P3-W6 Audit row wording.** "Asked PayAI: Prepare a government filing — Waiting for a choice" is good; make sure
  `expired` reads "Not answered in time" rather than "Expired" in the console (plain English).

## Process rule learned on 2026-10-12 (ledger PA41) — binding for every phase
Another session's version-diff deploy (`-u` every module whose manifest moved) swept an UNREVIEWED P2 build
(0d869baaa) onto payobook from the shared working tree. Therefore: (1) bump a module's manifest version ONLY in the
commit that is ready to ship — while building, keep the version unchanged; (2) stage every clone run AND every deploy
from `git archive <commit>` (never the working tree, PA38); (3) Fable checks `ir_module_module.latest_version` on
payobook before and after each deploy and investigates any version it did not ship.


Read first: `PAYAI_PROGRAM.md`, `PAYAI_LEDGER.md` (all PA rows), `P1_HANDOVER/REPORT.md`, `P2_HANDOVER/REPORT.md`
(the plan card, confirm RPCs, run driver, undo rails you extend), and `docs/design/payai-does-it.html` — the
**"Approve the June Retail run"** scenario (View as: Approver) is this phase's hero: red plan card, the run's figures,
the step ("HR Manager check, 1 of 2 — Finance release comes after you"), an optional note, "Type APPROVE to confirm"
with the button disabled until the word matches, then the done note "Approved as HR Manager. The run moves to Finance.
Nobody has been paid yet." and the audit line "approved by <name> via PayAI, typed confirmation".

## Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment: the typed-word confirm — it must
feel deliberate, not bureaucratic (the input autofocuses, the word is shown in the hint, the button enables the
instant the word matches, Enter submits). Zero dead-ends: not the approver → who is, with "Remind them"; seat moved
since the plan → fresh card; wrong word → inline hint, never a toast; voice → "this one needs typing" note. Plain
language, never "Odoo". Lucide, locked palette (Red tier header uses `--pbim-rose-soft`), no gradients, no emoji.

## Scope (P3)
1. **Red Actions** (tier `decide`), all through the P1/P2 machinery:
   - `approve_item`, `send_back_item`, `reject_item` — slot `item` resolved against the person's OWN inbox
     (`pb.approval.inbox.list_requests(tab='mine', scope='me')`; program doc §Approval engine): by process label
     ("the June Retail run", "Linh's allowance", "the hiring request for a QA engineer") → request. Not in their
     inbox → refused card naming the current seat holder(s) (`get_request(request_id, scope='everyone')` when the
     user may see it) with a "Remind <name>" chip (sends the engine's existing reminder/outbox notification; if none
     exists, a mail.activity on the record — say which in the report) and the door to Home › Approvals.
   - Preview (red plan card): title + process, the record's headline figures (pay run: people / net via
     `pb_pay_totals`; records change: field old → new; hiring: role + budget), the step position ("step 1 of 2") and
     who comes next, warnings from `get_request().can_decide`/independence rule (preparer cannot approve → refused
     with the reason, never an exception grant through PayAI), a `reason` slot (required for send back / reject,
     optional note for approve).
   - Confirm: **typed word**, server-verified: `rpc_confirm_task(task_id, how='typed', word=...)` checks
     `word.strip().upper() == action.confirm_word` (APPROVE / SEND BACK / REJECT; VI words in P4), expiry, seat
     re-check (`can_decide` again), company `payai_tier_decide`; `how='voice'` or `'tap'` on a Red task → refused
     note "this one needs typing". Execute `pb.approval.inbox.decide(request_id, step_key, action, reason,
     expected_lock_revision, idempotency_key=task)` — lock revision from the preview; a changed revision → fresh card.
   - No undo (card says so up front); result card names the next step and the next approver; audit line
     "<action> by <name> via PayAI, typed confirmation, <time>"; `payai.task.confirm_kind='typed'`.
2. **"Learn to do this yourself"** on every done card of run_payroll / submit_run / approve_item:
   `learn.scenario.begin(key, 'watch')` with keys `payrun` (run + submit) and `matrix`/approval scenario for approve
   (check `pb_learn/static/content/learn_content.json` for the right key; report which).
3. **Audit console**: Red tasks show the typed-confirmation badge in the PayAI source rows.
4. **Coach copy** (P2-F3 done in EN): nothing new; VI in P4.
5. Tests + report as before.

## Binding non-goals
No exception grants, no reassign/move-it through PayAI (door to the inbox instead). No voice confirm for Red, ever.
No approving on behalf of someone else (delegation is the engine's; PayAI acts only for the signed-in user and only
when `can_decide` is true for THEM). No Vietnamese. No new Actions beyond the three.

## From P2_REPORT (answered)
- Reuse `_route_steps` (P2) for "who comes next" on the red card; reuse the plan-promise-matches-outcome test pattern
  of tests 07/07b.
- The typed-word field sits ABOVE the action buttons (the container query already makes buttons full-row in narrow
  drawers); autofocus, Enter submits, the button enables the instant the word matches (case-insensitive, trimmed).
- PA28 (pass `formula_config_id` to `compute_batch`), engine-side idempotency keys for Records/delivery/filing, and the
  Compliance screen failing for officers without Government Reports (PA32) are OUT of P3 scope — leave them in the
  report's open list.

## Numbered tests (P3)
1. "Approve the June Retail run" as the seat holder → red plan card with figures, step, next approver, reason slot.
2. Same sentence as a non-approver → refused card naming the seat holder + Remind chip + door; nothing decided.
3. Typed word mismatch ("aprove") → task stays planned, card hint; correct word → `decide` called once with the task
   id as idempotency key; a second confirm with the same word → "already done" card, no second decision.
4. `how='tap'` or `'voice'` on a Red task → refused note; `payai_tier_decide=False` on the company → refused.
5. Seat moved between plan and confirm (reassign via the facade) → fresh-card answer, nothing decided.
6. Independence rule: the run's preparer asks to approve → refused with the engine's own reason.
7. send_back without a reason → clarify for the reason; with reason → request returned, reason stored.
8. reject → cancelled with reason; result card names what happens to the run (back to draft / rejected).
9. Lock revision changed (a concurrent decision) → fresh card, no double decision.
10. Learn tie-in: the done card carries the scenario door with the right key for each Action.
11. Audit: `payai.task` row has confirm_kind='typed', the console row shows the badge; the approval event trail has
    the decision under the user's own name (never PayAI as a user).
12. Gate: Access-home locked "Approvals" screen → refused even for a seat holder (no back door).
13. P3-W1…W5 each have a test (W1 one-person run computes exactly 1 payslip; W4 no draft chip; W5 clarify cancel → cancelled).
