# PRS P1 — report (the run screen's data, server only)

Phase: P1 of the PAY RUN SCREEN programme. Brief: `PRS_P1_HANDOVER.md`.
Built 2026-11-04 by an Opus implementation agent. Server only; nothing a
user can see changed; nothing deployed; no live record written.

## 1. Payload as built

`pb.payruns.get_run_screen(run_id)` (`pb_payruns/models/pb_payruns.py`, new
"run screen" section after `_board_cards`) returns every key the handover
lists, with these additions and decisions:

| Where | Change | Why |
|---|---|---|
| `primary.context` | NEW key (always present; `None` except `make`) | The make door is a wizard that needs `active_model/active_id/active_ids` of the run; P2 can pass it straight to `doAction`. |
| `primary.confirm.danger`, `actions[*].confirm.danger` | NEW key | So P2 knows the OK button is rose ("Send anyway", "Delete payslips", "Reject", "Set back to draft") without re-deriving it. |
| `primary.kind = 'decide'/'approvals'` | `action` is the inbox xmlid when `pb_approval_config` is installed, else `None` | Same door the board's `openApprovals()` uses. |
| `route.fast` | NEW bool | A route that is a fast lane (nobody signs) has no seats; the screen must say so, not show an empty chain. |
| `route.prepared_by` | NEW `{name, initials, me}` | The mock-up's first seat ("Prepared it · you"). |
| `route.seats[*].issue` | NEW (preview: the engine's per-step issue text, e.g. "Nobody holds …"; live: `''`) | Lets P2 mark the one seat that is broken. |
| `delivery.left` | NEW int | The mock-up's "Step 1 of 4 left". Step states are `done/now/later` (same words as the journey). |
| `checks` on a run with no payslips | `verdict 'wait'`, `items []` | The mock-up's empty moment draws no checks card at all. |
| `checks` on a rejected run | `verdict 'bad'`, title "This pay run was rejected", `sub` = the reason | — |
| route row title | "Approval route is set" / "No sign-off is needed" (fast lane) / "No sign-off was needed" (approved with no request) | Rize 1591 is a fast lane — "route is set" would hide that. |
| `money.sentence` | 4 whole-sentence variants (1 person / N people × with / without company contributions) + empty + rejected | "With the company's own contributions" is false when there are none. |
| `date_mismatch.text` | Draft: "…Check the dates before sending it."; any other state: the first sentence only | A done run cannot be "sent". |
| `compare` | `sentence` = two whole sentences ("2.4% more take-home than August 2026. 61 people were paid then.") | Whole msgids; no "1 people". The previous run must ALSO have payslips (an empty earlier draft is not "last month"). |
| Person flags | Order: cancelled · no data · not calculated · new · ±10% · fine | A cancelled payslip is never judged "not calculated". `amber` is in the vocabulary but nothing in P1 produces it. |
| `actions` keys | downloads: `xlsx`, `report`, `pdf`; more: `atlas`, `changes`, `recalc`, `split`, `cleardraft`, `reject`, `redraft`, `email` | Mock-up DLG / XML confirm texts reused. |
| `split` | Offered only when the payslips really fall in 2+ review groups | Offering it on one group is a dead end ("nothing to split") — C6. |
| `redraft` | Offered only on a done run with no bank file, no payment and no payslips sent, and only to someone who may edit | "Only if allowed": setting a paid run back to draft is the dangerous case. |
| `email` | Done runs, payslips present, reader may edit | Sending mail is an action, not a read. |
| `bulk` + `hr.payslip.run.action_pb_slips(verb, slip_ids)` | ADDED. Verbs `recalc` (the run's own `_adopt_scheme_when_structureless` + `action_recompute_formula_lines`, on the selection), `pdf` (the run's own review report, on the selection — `action_pb_print_payslips` now delegates to a shared `_pb_print_slips`), `delete` (draft/cancelled payslips only, run kept) | Every verb is an existing per-payslip method. Refuses any slip not on this run, any non-draft delete, and any change to a non-draft run. |

`_pb_slip_totals(run_ids)` (`hr_payslip_run.py`) returns
`{slip_id: {run_id, gross, deductions, net, employer_cost, bands}}`;
`_compute_pb_totals` now sums its `bands` in the helper's own row order — the
same float additions in the same order as before.

Two performance changes outside the screen code, both behaviour-neutral (see §6):

* `_pb_review_groups` honours a per-call cache passed in the context, but ONLY
  as an instance of the private class `ReviewGroupsMemo` — a client (plain
  JSON) can never forge it (test `test_the_groups_cache_cannot_be_forged_from_a_client`).
* `_pb_overtime_included` reads the DISTINCT line codes in one `_read_group`
  (same reader, same record rules, same per-code rule) instead of loading every
  line as a record. This also makes Submit itself faster.

## 2. Test results

New file `pb_payruns/tests/test_run_screen.py`: **25 tests, all pass, none
skipped** — T1–T13 plus T3b (no lines), T7b (another scheme is not last month),
T8b (Vietnamese names, spanning periods), T9b (short money), T11b (missing run),
T12b (split offered only with 2 groups; route row explains), T12c (rejected
run), the forged-cache guard, overtime parity, and three bulk-bar guards
(foreign slip refused, picked drafts deleted with the run kept, approved slip
never deleted).

Whole `pb_payruns` suite on a fresh local DB with pb_approval_config,
pb_pay_delivery, pb_source_atlas, pb_payroll_templates and pb_payslip
installed:

| | test methods | failed | errors | skipped |
|---|---|---|---|---|
| Before (repo HEAD) | 121 | 0 | 0 | 12 |
| After (P1) | 146 | 0 | 0 | 11 (all pre-existing: wkhtmltopdf, pb_comp_ben/pb_close absent, no OTH category, pb_me_portal absent) |

`test_run_totals.py` (27) and `test_pay_bands.py` (16) green on both, plus
T10's own run-by-run equality over five line shapes — the run totals did not
move. No failure text to quote. Note PRS-G11: without pb_approval_config the
whole approval suite skips silently; the first P1 run hit exactly that.

## 3. Measured time — rize run 1591 (read-only)

Not deployed, so it could not be called over JSON-RPC. Measured with
`odoo-bin shell` as the odoo user, loading the P1 copy of pb_payruns from a
scratch folder ahead of the live addons (PRS-G16), as user 2, three calls,
then rolled back. The running server was never touched (same PID, 18 h up);
run 1591's `write_date` is still 2026-10-19 02:16; the scratch folder is
deleted.

| Run | Payslips | 1st call | warm calls |
|---|---|---|---|
| rize 1591 | 63 | 365 ms | **198–199 ms** |
| payobook 2419 | 520 | 778 ms | 627–634 ms |
| payobook 1526 (done) | 1 | 52 ms | 50 ms |

First version measured 434 ms warm on 1591; the four changes above brought it
to 198 ms. Estimated ~280 ms for 200 payslips. What is left at 520 payslips is
mostly the approval engine's own route working-out (`_pb_review_groups`'
division look-up ~230 ms, the rest of `_approval_context`) — the same work
Submit does.

## 4. Rize 1591 payload (no salaries)

* Header: "Rize Vietnam Payroll · October 2026", work dates "1 – 30 Sep 2026",
  scheme "Rize Vietnam Payroll — archived master-data scheme", 63 people, VND
  ₫, 0 decimals, status Draft.
* **date_mismatch**: "The name says October 2026, but the dates are 1 – 30 Sep
  2026. Check the dates before sending it." (R2 satisfied.)
* Journey: Prepare done "63 payslips made" · Check done "All 4 checks pass" ·
  Approve **now** "Not sent yet" · Pay later · Send payslips later.
* Primary: `submit`, "Send for approval", warn 0, confirm "Send for approval?".
* Checks: verdict **ok** "Everything checks out"; data ✓, balance ✓, all 63
  calculated ✓, route ✓ ("No sign-off is needed").
* **Route: preview, FAST LANE, zero seats** — "Nobody checks this pay run
  before it is approved: it is approved the moment it is sent, and that is
  recorded." Binding 3, scope `scheme:4760`, kind `regular`. See §8.
* Compare: none — "This is the first run on this scheme, so there is nothing
  to compare with yet." (R3.)
* Teams (count): Agronomists (Jr+SA) 31, Operations 15, Finance, Strategy &
  Partnership 7, Carbon & Innovation 4, HR 2, OpsX 2, Legal 1, Product &
  Technology 1. Flags: all 63 "Calculated"; flagged 0, changed 0.
* No string in the payload contains "Odoo".

## 5. `actions` keys, rize vs payobook

Both databases have the same optional modules, so the keys are the same for
the same state:

| Run | downloads | more |
|---|---|---|
| rize 1591 (draft) | xlsx, report, pdf | atlas, changes, recalc, cleardraft, reject |
| payobook 2419 (draft) | xlsx, report, pdf | atlas, changes, recalc, cleardraft, reject |
| payobook 1526 (done, unpaid) | xlsx, report, pdf | atlas, changes, redraft, email |

`split` appears only for a draft whose payslips span 2+ review groups (none
on either database today). On the local test DB without the optional
modules, `report`/`atlas`/`changes`/paydeliver are simply absent (T12).

## 6. Self-review against the handover

* No view, JS, SCSS or template change — ✓. No deploy — ✓ (manifest version
  left at 19.0.3.3.0; **P2 must bump it** so the deploy gate sees the change).
* No stored field, no migration — ✓. No change to how pay is calculated,
  approved or paid — ✓ for results. Two approval-path functions were made
  faster without changing their answers (`_pb_review_groups` cache,
  `_pb_overtime_included` grouped read); both tested. Flagging them because
  they are on the Submit path.
* No new Excel exporter, reminder or approval behaviour — ✓. `action_pb_slips`
  only wraps existing per-payslip methods, as the handover allowed.
* Rize: read only, through a rolled-back shell; nothing written — ✓.
* C1: payload walked for "Odoo" (T13, and on rize/payobook live data) — none.
  New .po msgstr contain none.
* C2: every sentence is a whole msgid built server-side. C3: one per-payslip
  money source; run = its sum. C4: decimals from the currency; short money
  trims zeros ("₫2 billion", never "₫2.00 billion").
* C9: 193 new vi_VN entries (`#. module`, `#. odoo-python`, `#: code:…:0`),
  plus the python marker/occurrence added to 8 entries that were JS-only and
  are now said by Python too. Read back with Odoo's `PoFileReader` locally
  (686 rows, all 213 screen strings present). No `.pot` exists for pb_payruns.
  The on-box gate still needs running before P2's deploy.
* C8: no screen changed, so no Learn lesson, tour or replica is affected.
* Deviations: listed in §1 (added keys, split/redraft/email gating, flag order,
  previous run must have payslips, empty-run checks).
* C6 self-score (server side only): every state the mock-up draws has words,
  including empty, rejected, fast lane, broken route, two groups; nothing
  offered that would only refuse. The bar is P2's to meet on screen.

## 7. New ledger rows

PRS-G10 (run gross vs payslip gross on mixed runs), PRS-G11 (approval
catalogue comes from pb_approval_config; tests skip silently without it),
PRS-G12 (stale `am_tpl`; how to build a working test DB), PRS-G13 (Odoo 19
job/team via version, `load=None`), PRS-G14 (biz_access attribute cost —
read rows, not records), PRS-G15 ("OdooBot" in data on non-debranded DBs),
PRS-G16 (measuring unreleased code on live via a rolled-back shell), PRS-G17
(overtime "OT" substring quirk, kept), PRS-G18 (rize 1591 is a fast lane).

## 8. Commit, and what Fable must decide

Commit: see the hash in the agent's summary (one commit on 19.1, explicit
paths, not pushed).

For Fable / the owner:

1. **Rize 1591 has no sign-off.** Its scheme's route is "No approval needed".
   Pressing Send for approval approves it instantly. Combined with the wrong
   month in its name, the owner may want Rize told before anyone presses it.
   (The screen now says it plainly; nothing was changed.)
2. **Should a fast lane count as a check that passes?** P1 shows it as a
   green row ("No sign-off is needed"). An amber row would be one line to
   change.
3. **"Compared with" on payobook 2419 picks June** (the latest earlier run on
   that scheme), and 507 of 520 people get "+250 % vs June" flags. The rule is
   the handover's; it may want the same KIND of run (end-of-month vs
   mid-month) or "only the month just before". Demo data makes it loud.
4. **Mixed gross shapes (PRS-G10).** Kept as is; changing the run rule would
   move stored totals.
5. Performance at 500+ payslips (~630 ms) is the approval engine's own
   route working-out; a lazy route preview in P2 is the lever if needed.
