# PAYAI P2 — Amber tier (handover for Opus)

## P1 is LIVE on payobook (2026-10-12) — walk findings to fix FIRST, in P2's first commit
Fable walked P1 on payobook.com with the QA login (Chrome, visible window, console clean). Works: "Open the Runs
board" → done card + the board opens; "Run June payroll for Retail" → honest stub refusal with the door; "Delete the
May run" → blocked card (lock note, door, audit line); "Show the June run" → tiles 12 runs / 8,879 people / ₫113.3 bn
+ run chips; "What can you do?" → grouped list; "PayAI can act" settings card under Settings with the four switches.
Fix these (each is small; number them P2-F1…F4 in the report):
- **P2-F1 Door ranking.** "Open runs" resolved to the Learn row "Lesson · 7 min · how to › Runs" instead of the Pay
  hub's Runs lens, and did not ask. Rule: rank hub lenses and mission rows (palette `group` surfaces/missions) above
  deep links and above Learn rows; an exact label match on a lens wins outright; when the top two scores are within
  0.1 of each other AND belong to different groups → Clarify chips (≤6). Add tests: "open runs" → Runs lens; "open the
  runs lesson" → Learn row; "open approvals" (Home lens vs Workforce lens) → chips.
- **P2-F2 Breadcrumb "Unnamed".** The settings action opened from the "PayAI can act" card shows the parent
  breadcrumb as "Unnamed" (`/bizapp/pb_settings_hub/action-1573`). Give the hub breadcrumb its name ("Settings") —
  check how other settings-hub cards that open a form avoid it, and copy that.
- **P2-F3 Coach banner copy.** The helper drawer still says "I explain — you act. I never compute a pay run, approve
  a payslip or change a record for you." (pb_learn coach.xml). From P2 that sentence is false. Replace with: "Ask me
  to do something and I show you the plan first. I only ever do what you could do yourself on the screen." (EN now,
  VI in P4) — pb_learn bump.
- **P2-F4 Report hygiene.** P1_REPORT's walk section said "not done"; append the walk record above to it under
  "Walked by Fable on payobook 2026-10-12" so the record is complete.


Read first: `PAYAI_PROGRAM.md`, `PAYAI_LEDGER.md` (PA-R1…R5 + every PA row), `P1_HANDOVER.md` + `P1_REPORT.md`
(the card contract, the registry, the gate, the resolvers and the chat patch you are extending), and the design
page `docs/design/payai-does-it.html` — the **"Run June payroll for Retail"** scenario is this phase's hero: clarify
chips → plan card with slot origins → Do it → progress bar → result tiles → undo countdown → audit line. Build to it.

## Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment: the plan card turning into a live
progress card and then a result — one card, three states, no page change. Zero dead-ends: expired plan, stale state,
provider down, run refused by the wizard, undo too late — each names its reason and its next step. Plain language,
never "Odoo". Motion with purpose (progress fill, undo countdown, card state change). Lucide, locked palette, no
gradients, no emoji. Score the report against this bar.

## Scope (P2)
1. **Amber Actions** (tier `prepare`), all through the P1 registry/gate/card machinery:
   - `run_payroll` — slots `period` (month/year → 1st..last; "this month" default from `get_defaults()`), `scheme`
     (resolve against `get_defaults().schemes`; exactly one → default origin, several → clarify chips, "Retail" →
     fuzzy over scheme names/division labels), `people` (default "everyone this scheme covers"; optional statuses /
     named people resolved via `eligible_preview`), `pay_data` (default: whatever the scheme's lanes say —
     `spreadsheet_gate(vals)`; if a file is WANTED, the plan card says so and offers "Open in the screen instead"
     because files are not uploaded through chat in P2).
     Preview = `scheme_preview(vals)` (covered / not covered), `eligible_preview` (count), `_period_runs` via a
     dry call of `prepare_run` is NOT allowed (it creates) — add a read-only `pb.payrun.wizard.plan_preview(vals)`
     that returns `{covered, not_covered, total, existing:[{name,state}], blockers:[…]}` using the same helpers
     (`_require_scheme`, `_period_runs`, `_clean_blockers`) — gated by `@runner_only` like the rest.
     Execute = the wizard's own chain, driven from the CLIENT exactly like the wizard: extract the compute loop from
     `pb_payrun_wizard/static/src/js/payrun_wizard.js` (`_compute`, chunking of `compute_batch` by 40, `sync_plan`/
     `sync_step`, `get_summary`) into a shared ES module `@pb_payrun_wizard/js/run_driver` with a progress callback;
     the wizard and the PayAI card both call it (P1_REPORT's open question answers the exact seam). `force_clean`
     is NEVER sent by PayAI: an existing run → blocked card ("A June run for Retail End-Month already exists — open
     it" + door). `needs_confirmation`/`blocked` answers from `prepare_run` → blocked card.
     Result tiles: payslips, net (ONE PAY-BAND RULE: `pb_pay_totals`, via `get_summary().total_net`), need-a-look
     count. Buttons: Open the run (door to the Runs board focused on the run), Send for approval (chains
     `submit_run`), Learn to do this yourself (`learn.scenario.begin('payrun','watch')`).
     Undo (10 min): delete the draft run through `hr.payslip.run.unlink()` AS THE USER (officers lack unlink →
     the undo button is hidden for them with the sentence "Ask a payroll manager to delete it, or leave it as a
     draft" — never sudo). Mark the run: new field `hr.payslip.run.pb_prepared_via = 'payai'` + history sentence
     "Prepared by <name> through PayAI" in `pb.payruns._history` (`pb_payruns/models/pb_payruns.py:343–346`).
   - `submit_run` — slot `run` (resolve: period + scheme → draft runs the user can read). Preview: route name +
     first approver seat from `biz.approval.engine.resolve_binding`/`preview` (program doc §Approval engine), the
     `_approval_validate` refusals shown as notes. Execute `run.action_approval_submit()`. Undo = withdraw
     (`_approval_withdraw` path through the inbox facade `cancel(request_id, reason)` as the submitter), 10 min.
   - `update_pay_data` — slots `person` (employee search as the user; ≥2 → chips with department sub-labels),
     `field` (resolve against the Records Desk column catalogue for the person's scheme — `pb.records.desk` config
     columns), `value` (number/text parsed server-side; money in the scheme currency), `from` (date; default
     today). Preview = `pb.records.desk.preview_changes(config_id, changes)`; execute = `apply_changes(config_id,
     changes, note="via PayAI", source='payai')` (engine-routed when the Matrix says so → note "needs <approver>");
     undo = `undo_apply(apply_id)` (already refuses if the value moved since).
   - `send_payslips` — slot `run` (done runs only). Execute `pb.pay.delivery.send_payslips(run_id, force_all=False)`
     (gated by its own `_require_access`; routed). No undo (card says so up front). Count preview from the run.
   - `filing_prepare` — slots `country`, `filing` (from `pb.filing.flow.start(country)` catalogue), `period`.
     Execute `scope → save_scope → generate` (proposal-routed). Card ends with the door to Compliance › Filings.
2. **Rails**: re-validate at Do it (`plan_preview` again; any change → "Things changed since I showed you this
   plan" + a fresh card); expiry 10 min; one in-flight task per user; idempotency key = task id on every engine call;
   `payai.task` states running/done/failed/undone with `result_json` (run_id, apply_id, request_id).
3. **Voice**: TTS read-back of the plan card when the message came from voice (the client knows: `voice=true` on
   the send); spoken "go ahead" / "yes, do it" accepted as the Do-it tap ONLY when `company.payai_voice_go_ahead`
   AND the task is Amber — the server checks both; the phrase list lives server-side.
4. **Prefill escape hatch**: "Open in the screen instead" opens the Run Payroll wizard with `vals` pre-filled —
   add `prefill` support to the wizard action context (`pb_payai_prefill: {...}`) read in `payrun_wizard.js` setup.
5. Tests + browser walk + report, as in P1.

## Binding non-goals
No Red (approve/reject). No clean-and-run through PayAI, ever. No file upload through chat. No sudo. No Vietnamese.
No server-side long jobs: the browser stays open during a run, exactly like the wizard today.

## Verified plumbing — see PAYAI_PROGRAM.md "Run Payroll wizard + lifecycle" (file:line) and P1_REPORT.md.
Key P0 facts: every wizard method is `@runner_only`; `prepare_run` may answer `{blocked, kind:'protected'}` or
`{needs_confirmation}`; `_check_period` refuses bad dates; `pb_prepared_uid` is written.

## From P1_REPORT (Opus's open questions, answered)
- **run_driver extraction**: lift `_compute` (`payrun_wizard.js:897–1066`) into `@pb_payrun_wizard/js/run_driver`
  exporting `runPayroll(orm, vals, {onProgress, onStep})` that returns `{run_id, summary, exceptions, sync, batch,
  prep}`; the wizard keeps its own state handling around the call (`gotoKey`, `busyMsg`, dialogs) and the PayAI card
  passes `onProgress({done,total,label})`. The driver never decides on `needs_confirmation`/`blocked`: it returns
  `prep` and the CALLER decides (the wizard shows its dialog; PayAI shows the blocked card). Keep the chunk size 40
  and the `already` guard behaviour unchanged. Wizard tests must still pass.
- **Server-validated confirm/progress**: the client calls `rpc_confirm_task(task_id, how)` (how = tap|voice) which
  re-runs gate + `plan_preview`, checks expiry and the company tier switch, moves the task to `confirmed` and returns
  the exact `vals` to drive (the client never composes `vals` itself); `rpc_task_progress(task_id, done, total)` is
  bookkeeping only; `rpc_task_result(task_id, run_id)` closes it after the driver's `get_summary`. A task not in
  `confirmed` state refuses progress/result writes.
- **Latency of the extra tools call**: keep the phrase table first (P1 deviation) and add a per-user LRU of the last
  resolved sentences; show the typing dots immediately. No other work in P2.
- **Resolvers untested (scheme/division)**: P2 tests 1 and 12 cover them; add unit tests for `resolve.scheme` with
  "Retail" (two Retail schemes → ambiguous), "Retail End-Month" (unique), "Marketing" (none).
- **Who may change the switches**: admin only stays (owner can revisit); do not widen.

## Numbered tests (P2)
1. run_payroll plan: "Run June payroll for Retail" → chips when two Retail schemes; one → plan card with origins
   said/chose/default and the covered/not-covered counts equal to `scheme_preview`.
2. Existing draft June run → blocked card with the door; `force_clean` never present in any RPC payload (assert).
3. Do it → prepare_run + compute_batch chunks → payai.task done with run_id; result tiles equal `get_summary`.
4. Undo within 10 min as a manager deletes the draft run; as an officer the undo button is absent and the sentence
   shown; after 10 min → "too late" card.
5. Re-validation: a run created between plan and Do it → the fresh-card answer, nothing created.
6. submit_run → request created, undo withdraws it; a run with two schemes → `_approval_validate` text on the card.
7. update_pay_data → preview equals Records Desk preview; apply routed when the Matrix requires it; undo_apply
   reverts; a value moved meanwhile → undo refused with the Desk's own sentence.
8. send_payslips on a draft run → refused; on a done run → routed request.
9. filing_prepare → proposal created, door returned.
10. Voice go-ahead accepted only with the company switch on and only for Amber (Red/never → ignored with a note).
11. History line "Prepared by … through PayAI" on the run; audit console row.
12. Gate: Access-home locked Run payroll screen → refused even for an officer (no back door).
