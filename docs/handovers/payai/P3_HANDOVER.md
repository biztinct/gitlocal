# PAYAI P3 — Red tier + Learn tie-in (handover for Opus) — DRAFT, finalise after P2_REPORT.md

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
