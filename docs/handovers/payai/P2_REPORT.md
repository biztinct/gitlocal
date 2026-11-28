# PAYAI P2 — report (Amber tier)

Implemented by Opus, 2026-10-12, against `P2_HANDOVER.md`. Nothing deployed to any live database. Clone tests green
on `p0clone`: run 4 (build, `0d869baaa`), then the review round — 12 findings fixed (`e46f8ef01`, `c1603e53e`,
`7d7c3f6f3`, `460dd1b09`) and the 14 never-verified findings handled (`ea400fa22` design, `547b33134` tests), green
for pb_payai_actions in gap runs 1 and 3 (35 tests, 0 failed / 0 errors / 0 skipped); pb_payrun_wizard's 20
failures in gap 3 come from another session's walk data on the shared clone (PA40), not from code. Browser walk not done — Fable walks on payobook after deploy (WALK LIST below).

## Status at a glance
| Item | Status |
|---|---|
| P2-F1 "Open runs" ranks the Pay hub's Runs lens; near-ties ask | done, `test_00_f1_door_ranking` |
| P2-F2 Settings breadcrumb says "Settings" | done (`3aec1388d`), JS — walk it |
| P2-F3 helper banner no longer says PayAI never acts (EN + VI) | done (`bbcbcabf8`) — walk it |
| P2-F4 P1_REPORT walk section | done |
| Five Amber Actions | built, clone-tested, not yet seen in a browser |
| 32 review findings | 12 confirmed + fixed; 14 handled in the gap round (all real, all fixed); 6 refuted |

## Walk findings from P1 (fixed in P2's first commit)
| # | Finding | Fix | Where |
|---|---|---|---|
| P2-F1 | "Open runs" resolved to the Learn row "Lesson · 7 min · how to › Runs" instead of the Pay hub's Runs lens, and did not ask. | Door ranking: missions/surfaces/hub lenses above deep links above Learn rows; exact label on a lens wins; near-tie (≤ 0.1) between rows from DIFFERENT places → Clarify chips (≤ 6); same place → top row wins. Kind read from the client-sent `kind` (ranking only, PA19) with an id fallback (`learn.*`, `*hub_*`, `*hub`) — PA25. | `pb_payai_actions/payai/resolve.py`; test `test_00_f1_door_ranking` |
| P2-F2 | Settings form opened from the "PayAI can act" card showed "Unnamed" as its parent breadcrumb. | The settings hub names itself ("Settings") via `env.config.setDisplayName` when not embedded — the pb_hiring board's fix, copied. | `pb_settings/static/src/js/settings_hub.js` (1.9.1) |
| P2-F3 | Helper drawer banner still said "I explain — you act. I never … change a record for you." | EN replaced with "Ask me to do something and I show you the plan first. I only ever do what you could do yourself on the screen."; VI changed with it ("Bạn nhờ tôi làm một việc, tôi cho bạn xem kế hoạch trước. Tôi chỉ làm những gì bạn tự làm được trên màn hình."). The sentence lives in `learn_content.json`, not `coach.xml` as the handover said. Committed in `bbcbcabf8`. | `pb_learn/static/content/learn_content.json` (20.4.1) |
| P2-F4 | P1_REPORT's walk section said "not done". | "Walked by Fable on payobook 2026-10-12" appended. | `P1_REPORT.md` |

## Actions (all tier `prepare`, through the P1 registry / gate / card machinery — `payai/actions_amber.py`)
| Action | Plan (read-only preview) | Do it (as the person) | Undo (10 min) | Status |
|---|---|---|---|---|
| `run_payroll` | new `pb.payrun.wizard.plan_preview(vals)` (`@runner_only`; covered / not covered / total / existing / blockers, same helpers as `prepare_run`); slots period / scheme / people / pay data with origins said/chose/default; spreadsheet wanted → plan says so + "Open in the screen instead" | `rpc_confirm_task` re-validates and returns the server-built `vals`; the browser drives the shared run driver; `rpc_task_progress` bookkeeping; `rpc_task_result` accepts a run id only if it is one THIS task made (`_made_run`, PA-R3), stamps `pb_prepared_via='payai'`, tiles from `get_summary` (one pay-band rule) | `hr.payslip.run.unlink()` as the person; hidden for officers with "Ask a payroll manager to delete it, or leave it as a draft"; after 10 min → too-late card | built, untested in browser |
| `submit_run` | route + first approver from `biz.approval.engine.resolve_binding` / `preview`; the run's own `_approval_validate` refusal shown in its words | `biz.approval.engine.submit(run, idempotency_key='payai-task-<id>')` | withdraw through `pb.approval.inbox.cancel(request_id, …)` | built |
| `update_pay_data` | `pb.records.desk.preview_changes` | `apply_changes(…, source='desk', note="via PayAI")` (PA26); routed → "waiting for approval" | `undo_apply`; nothing restored + skipped → refusal with the Desk's own sentence (PA27); a routed, still-pending apply is withdrawn through the inbox | built |
| `send_payslips` | count from the run; done runs only; card says "cannot be undone" up front | `pb.pay.delivery.send_payslips(run_id, False)` (own `_require_access`, routed) | none (by design) | built |
| `filing_prepare` | `pb.filing.flow.start(country)` catalogue; "Nothing is sent to the authority" | `scope → generate` (proposal-routed); downloads (`/web/content/` only) + door Compliance › Filings | none | built |

Supporting pieces: shared run driver `pb_payrun_wizard/static/src/js/run_driver.js` (`runPayroll`, `CHUNK = 40`,
`stashPrefill` / `takePrefill`), the wizard's `_compute` now a thin caller; `pb.payruns._history` override in
`pb_payai_actions/models/hr_payslip_run.py` ("Prepared by <name> through PayAI"); new runner RPCs
`rpc_confirm_task` / `rpc_task_progress` / `rpc_task_result` / `rpc_task_undo` / `rpc_cancel_task`; new
`payai.task` state `cancelled`; per-user LRU (256) of routed sentences; voice read-back + server-side go-ahead
phrase table (`runner.GO_AHEAD`).

## Rails (checked in code by the assess stage)
- **PA-R1** every Amber Action has `method_gate` (group / ACL / engine seat) on top of the P1 screen gate; test 12.
- **PA-R2** no `sudo()` anywhere in `actions_amber.py`; `payai.task` writes in the runner are bookkeeping (PA18).
- **PA-R3** `vals` built server-side and handed out by `rpc_confirm_task`; the wizard's `_applyPrefill` only fills the
  form (the person still presses every button); run ids from the browser accepted only via `_made_run`.
- **force_clean** never appears in `pb_payai_actions` except test assertions (test 2 greps the driver call site and
  the chat patch).
- Re-validation at Do it (`plan_preview` again + fingerprint; changed → "Things changed since I showed you this
  plan" + fresh card); 10-min expiry; one in-flight task per user (stale after 3 min, PA29); other users' Do it →
  refused.
- White-label / plain English: no "Odoo" in any changed user-visible string.
- All changed .py/.js compile (`py_compile` / `node --check`); `learn_content.json` parses.

## Tests (`pb_payai_actions/tests/test_payai_p2.py`, clone `p0clone`, staged `/tmp/p2stage`)
**Results: green on run 4 (final code, `0d869baaa`).** Clone runs on `Payobook19v2` (odoo-bin, `--http-port=8099`, staged modules first on the addons
path, log `/tmp/p2test.odoo.log`, run summary `/tmp/p2test.log`):

| Run | When (UTC) | Code | Outcome |
|---|---|---|---|
| 1 | 2026-10-11 23:38 | P2 as built | `test_06_submit_run` and `test_08_send_payslips` ERROR — AccessError reading the run's scheme (`hr.formula.config`) as a payroll manager without a Formula Engine role, raised out of `resolve._run_words` → fixed (PA31, `resolve._scheme_of`) |
| 2 | 2026-10-11 23:41 | + PA31 fix | `pb_payai_actions: 32 tests` (P1 + P2 together) — 0 failed, 0 errors, 1 skipped (test 9); `pb_payrun_wizard: 71 tests` — pass (1 pre-existing self-skip, `test_the_compute_that_follows_pays_nobody_twice`: "the file produced no payslip in this database"); `pb_payroll_ai_insights: 128 tests` — only the 3 vi_VN copy FAILs (ignored, PA11) |
| 3 | 2026-10-12 02:03 | + test 9 VN fall-back + People-slot / label edits (clone-run fixes 2, 4, 5) | `pb_payai_actions: 32`, `pb_payrun_wizard: 71`, `pb_payroll_ai_insights: 128`; 3 failed = the PA11 vi_VN trio only. Test 9 skipped with "No filing route here: You are not allowed to create '… Report Wizard' (pb.govt.report.wizard) records" — the VN fall-back worked, then Do it failed: the filer lacks the Government Reports permission, and the card showed the framework's raw text (model name) → fixes 7 and 8 |
| 4 | 2026-10-12 02:07 | + fixes 7, 8 (filing permission at plan time, plain access-error text, govt-group filer in the fixture) | `pb_payai_actions: 32 tests` (13 P1 + 15 P2 methods) — 0 failed, 0 errors, **0 skipped**; `pb_payrun_wizard: 71` — pass (same pre-existing self-skip); `pb_payroll_ai_insights: 128` — only the 3 vi_VN FAILs (PA11). `3 failed, 0 error(s) of 195 tests`. No OOM (start at 611 MB available; the dmesg OOM lines are ~20 days old) |

P1's 15 tests (`test_payai_p1.py`, the stats line in P1_REPORT) all still pass alongside — no P1 test appears in any
FAIL/ERROR line. The 3 vi_VN failures (`test_data_access.test_06`, `test_egress.test_04d` / `test_04e`) are the
known translation-catalogue debt (PA11), not this phase.

| # | Test | What it asserts | Skips itself when (skipTest) | Result |
|---|---|---|---|---|
| F1 | `test_00_f1_door_ranking` | "open runs" → `payhub_runs`; "open the runs lesson" → Learn row; "open approvals" → chips | — | pass |
| — | `test_00b_scheme_resolver` | "Retail" (two) → ambiguous; "Retail End-Month" → unique; "Marketing" → none | — | pass |
| 1 | `test_01_run_payroll_plan` | two Retail schemes → chips; plan card origins said/chose/default; counts = `scheme_preview` | — | pass (run 4, People slot reads `covered`) |
| 2 | `test_02_existing_run_blocked_and_never_force_clean` | existing draft → blocked card + door; no `force_clean` in card / params / confirm payload / driver + chat source | — | pass |
| 3 | `test_03_do_it_drives_and_closes` | confirm → running; driver as the person (prepare_run + compute_batch by 40); task done with run_id; tiles = `get_summary` | — | pass |
| 4 | `test_04_undo` | manager undo deletes the draft; officer: no button + sentence; > 10 min → too late | — | pass |
| 5 | `test_05_revalidated_at_do_it` | run created between plan and Do it → fresh card, nothing created; expired plan refused; other user's Do it refused | — | pass |
| 6 | `test_06_submit_run` | two-scheme run → blocked "different groups"; request created with `idempotency_key='payai-task-<id>'`; undo withdraws | **no pay run approval route** on the DB (card comes back blocked) — did not fire | fail-fixed (run 1 AccessError → PA31), pass in run 2 |
| 7 | `test_07_update_pay_data` | two Linhs → chips; preview = Desk preview; undo reverts; moved value → Desk's sentence | **Records Desk not installed** — did not fire | pass |
| 7b | `test_07b_update_pay_data_routed` | routed apply → "approval" on the card; undo cancels the request | Records Desk not installed; **no `hr_lead` approval role**; **records route needs no approval** — none fired | pass |
| 8 | `test_08_send_payslips` | draft → refused ("approved"); done → plan "cannot be undone" → routed request, no undo | **Pay & Deliver not installed**; **no send-out route** (state failed) — none fired | fail-fixed (run 1 AccessError → PA31), pass in run 2 |
| 9 | `test_09_filing_prepare` | plan "Nothing is sent to the authority"; proposal created; door `cmphub_filings` | **Government filings not installed**; **no covered filing country**; **no filing route** (state failed) | run 2 skip "No covered filing country here." (US clone) → VN fall-back; run 3 skip "No filing route here" (filer had no Government Reports permission) → fixes 7–8; **pass in run 4**, including the new no-permission refusal at plan time |
| 10 | `test_10_voice_go_ahead` | switch off → note only; typed never counts; switch on + Amber → the Do-it tap; read-back when spoken; Red → ignored | — | pass (`payai_voice` context survives into the engine env) |
| 11 | `test_11_history_and_audit` | history "Prepared by … through PayAI"; audit console row | — | pass |
| 12 | `test_12_no_back_door` | Access-home locked Run payroll screen → refused even for an officer | — | pass |

Every test also skips when the DB has no `hr.formula.config` model (`setUp`, "This database has no payroll
schemes.") — not expected on `p0clone`. Fixtures patch `_eligible_employees`, `_scheme_population` and
`get_active_config` (provider off: the phrase table must carry every test sentence).

## Deviations from the handover (with reasons)
1. **`submit_run` calls `biz.approval.engine.submit(run, idempotency_key=…)`**, not `run.action_approval_submit()`:
   the button method takes no key and is only `engine.submit(self)` (`biz_approval_workflow/models/adapter.py:206`)
   plus a toast (`pb_payruns/models/hr_payslip_run.py:1048`). Same engine path, same gates; the run's
   `_approval_validate` refusal is also surfaced at plan time.
2. **`filing_prepare` runs `scope → generate`, without `save_scope`**: the period is passed straight into
   `generate(wizard_id, country, filing_key, write)`, which writes it itself; no proposal is lost.
3. **Idempotency key only on `engine.submit`.** The handover asked for "task id on every engine call"; the other
   engines (Records Desk apply, delivery send-out, filing generate) accept no key. Double-press is instead stopped
   by the task state machine (a task not in `planned` refuses a second confirm; one in-flight per user).
4. **VI helper banner changed too** (P2-F3): the handover left VI for P4, but `bbcbcabf8` changed EN and VI together
   so the Vietnamese drawer no longer says PayAI never acts. Every OTHER new P2 string is still EN-only (P4).
5. **PA28 — `formula_config_id` not passed to `compute_batch`**: the shared run driver keeps the wizard's payload
   byte-for-byte (P2 non-goal to change screen behaviour). Payslips made by PayAI are therefore stamped like the
   screen's (run carries the scheme; slips not at creation). Fable/owner decision.
6. **`update_pay_data` applies with `source='desk'`** (not `'payai'`) because `source` is the Matrix's kind key
   (PA26); PayAI provenance is the `note` + the `payai.task` row.
7. **`pb.payruns._history` override lives in `pb_payai_actions`**, not `pb_payruns` (the handover cited the
   pb_payruns line): keeps pb_payruns free of a PayAI field; pb_payai_actions already depends on it.
8. **Prefill goes through two paths** (PA30): `run_driver.stashPrefill()` for the Pay hub lens, plus the
   `pb_payai_prefill` action context for the standalone action.
9. **`go_ahead()` runs on every message before the phrase table**; it only fires when a planned task exists in the
   same conversation, so ordinary messages are unaffected.

## Clone-run fixes
1. **PA31 — scheme read as a payroll manager.** Run 1: `test_06` / `test_08` errored with AccessError — a payroll
   manager without a Formula Engine role may read runs but not `hr.formula.config`, and `resolve._run_words` read
   `run.pb_formula_config_id.display_name`. New `resolve._scheme_of(run)` checks read access and returns nothing on
   AccessError, so run words skip the scheme (name + division still match) instead of failing the whole message.
   Also feeds `run_scheme_label`. `pb_payai_actions/payai/resolve.py` (`_scheme_of`, `from odoo.exceptions import
   AccessError`).
2. **Test 9 on a non-VN clone.** `p0clone`'s company is in the US, so `pb.filing.flow.start()` reported no covered
   country and the test skipped. The test now asks for VN explicitly when VN is in `covered` before giving up; the
   skip guard stays for databases with no covered country at all. `pb_payai_actions/tests/test_payai_p2.py`.
4. **People slot shows the scheme card's count** (local check, after run 2): the run_payroll plan's People slot now
   reads `pv.get('covered', pv['total'])` — the number the wizard's scheme card shows and what test 1 compares;
   `can_do`, the spoken summary and `extra.total` still use `pv['total']` (the list the run computes). Differs from
   `total` only when `_segment_hosts` adds host employments. `pb_payai_actions/payai/actions_amber.py`. Untested on
   the clone (run 3).
5. **Settings label**: "A spoken 'go ahead' counts for Amber" → "A spoken 'go ahead' counts for prepare requests"
   in `pb_payai_actions/views/res_config_settings_views.xml` and the field `string=` in
   `pb_payai_actions/models/res_company.py:41` (both done).
6. Staging note: `/tmp/p2stage` must be wiped (`sudo rm -rf`) before each rsync — an rsync into the odoo-owned
   staging dir fails part-way (`Permission denied`) and a half-updated stage would test old files.
7. **PA32 — filing permission at plan time.** `filing_prepare.plan` now checks create access on the country's
   filing form (`pb.filing.flow._adapter(cc)['model']`, e.g. the VN report wizard, which needs Government Reports
   User). Without it the card is "Not allowed yet — Preparing this filing needs the Government Reports permission.
   Ask your administrator to give it to you." instead of a plan whose Do it fails. Test 9 asserts it (user
   `P2 Filer Two`, no model name on the card); the fixture's `P2 Filer` gets `pb_hr_govt.group_pb_hr_govt_user`.
8. **PA33 — plain text for framework access errors.** `runner._exc_text(exc)`: an AccessError whose message carries
   a technical model name in brackets (`(a.b.c)`, any language) shows "You do not have the permission this needs.
   Ask your administrator." on every Look/Amber failure card; business messages (UserError, custom AccessError
   sentences such as the filing flow's own) are kept as written.

## Gap round — final clone runs (`p0clone`, staged `/tmp/p2stage`, port 8099)
Stage built from `git archive HEAD` for every module except `pb_payai_actions` (working tree, = `547b33134`), so the
other sessions' uncommitted edits (pb_learn, pb_dashboard) never reached the clone.

| Run | Unit | Command | Outcome |
|---|---|---|---|
| gap 1 | `p2-gap-1` | `-u pb_payai_actions --test-tags /pb_payai_actions,/pb_payrun_wizard` | `odoo.tests.stats: pb_payai_actions: 35 tests 10.45s 9290 queries`; `odoo.tests.result: 0 failed, 0 error(s) of 31 tests`; **0 skipped** (no `skipped` line); EXIT=0. pb_payrun_wizard's tests are at-install, so they only run when that module is upgraded too → gap 2 |
| gap 2 | `p2-gap-2` | same + `-u pb_payrun_wizard` | never ran: launched while another session's walk server held `p0clone` on port 8099; died at once (`EXIT=1`, nothing loaded). Launch rule broken by a self-matching `pgrep` (PA37) — no harm done |
| gap 3 | `p2-gap-3` | `-u pb_payai_actions,pb_payrun_wizard --test-tags /pb_payai_actions,/pb_payrun_wizard` | `pb_payai_actions: 35 tests 9.41s 9311 queries` — **0 failures, 0 errors, 0 skipped**; `pb_payrun_wizard: 71 tests 10.39s 9244 queries`; `odoo.tests.result: 6 failed, 14 error(s) of 86 tests`; EXIT=1. **All 20 are pb_payrun_wizard tests with fixed 2026 dates** (`test_run_adopts_the_period` ×7 `KeyError: 'adopted'`, `test_spreadsheet_step` ×8, `test_two_schemes_one_month` ×5 `2 != 1`): p0clone now holds three DONE runs "Walk Sales Jun/Jul/Aug" 2026 (ids 1173–1175, created today by the Home P3 walk session), so `prepare_run` answers "exists / needs confirmation" and the duplicate counts see 2. pb_payrun_wizard code is unchanged since `c5b77d6be` (71 green in build run 4, same tests); not touched — the walk data is another session's (PA40) |

(The stats line counts 4 more than the methods — 13 P1 + 18 P2 = 31 — in every run, the build runs included; the
result line is the method count.) The six "Could not read the scheme currency" ERROR tracebacks in test_07/07b are
pre-existing (same six in build run 4): `_scheme_currency` logs and falls back when the asker cannot read
`hr.formula.config` (PA31 family) — not a failure.

### Tests 1–12 → final state
| # | Test(s) | Final |
|---|---|---|
| F1 | `test_00_f1_door_ranking`, `test_00b_scheme_resolver` | pass |
| 1 | `test_01_run_payroll_plan` — chips, origins, covered count, **covered 1 / not covered 1** note, "Which Retail scheme do you mean?" | pass |
| 2 | `test_02_…never_force_clean` — blocked card + door; `force_clean` absent from card, params, confirm payload, `drive.vals` keys, and the whole `payai/`, `models/`, `static/src/js` tree | pass |
| 3 | `test_03_do_it_drives_and_closes` (tiles **exactly** `get_summary`: count, `money(total_net)`, flagged + exceptions) + `test_03b_one_driver_for_screen_and_card` (run_driver.js `CHUNK = 40`, RPC order sync_plan → sync_step → prepare_run → attach_spreadsheet → discard_empty_run → compute_batch → get_summary; payrun_wizard.js imports `runPayroll` and names no `compute_batch`/`prepare_run` itself) | pass |
| 4 | `test_04_undo` | pass |
| 5 | `test_05_revalidated_at_do_it`, `test_05b_progress_and_result_need_your_own_go_ahead`, `test_05c_result_takes_only_the_run_this_task_made` | pass |
| 6 | `test_06_submit_run` — explicit auto-approve branch (no Undo, skip with reason); on p0clone the route is pending, so Withdraw ran | pass (not skipped) |
| 7 | `test_07_update_pay_data` (+ refused undo leaves 777,000, task `done`, `undo_until` kept; plan promise = outcome), `test_07b_update_pay_data_routed` | pass (not skipped) |
| 8 | `test_08_send_payslips` | pass |
| 9 | `test_09_filing_prepare` — exactly one `_press` for the plan's country + filing when not pending; none when pending | pass |
| 10 | `test_10_voice_go_ahead` | pass |
| 11 | `test_11_history_and_audit` — audit row `payai-<task id>` for this task's run, actor = asker; a hand-made run has no "through PayAI" line | pass |
| 12 | `test_12_no_back_door` — screen half AND method half (base user, screen patched 'on', run_payroll + submit_run refused `no_right`, no plan) | pass |

## Review findings (32)
Source: workflow journal `wf_dda17ba9-ed4` (3 verifiers per finding, majority decides) + this gap round.

**Confirmed and fixed in the review round (12)**
| Finding | Fix | Commit |
|---|---|---|
| design-1 slot pencils missing | editable slots + pencil re-asks one slot | `e46f8ef01` |
| design-2 result card drops the plan slots | `cards.plan_slots(task)` on result cards | `e46f8ef01` |
| design-3 undo strip in warning colour | brand tint | `e46f8ef01` |
| design-4 off-palette hex | `--pc-*-ink` tokens | `e46f8ef01` |
| design-5 countdown hits 0:00 but Undo stays | `onExpire` → card flips to the too-late state | `e46f8ef01` |
| design-7 default chip cannot say why | `origin_label` ("current company") | `e46f8ef01` |
| design-9 audit line "(tap)" code word | two whole sentences (tap / voice) | `e46f8ef01` |
| design-10 reduced-motion misses transitions | block extended | `e46f8ef01` |
| security-2 bare "yes" confirms a stale plan by voice | stricter go-ahead table + latest-plan only | `e46f8ef01` |
| correctness-1 late progress reopens a finished task | row lock + state re-check under it | `c1603e53e` |
| correctness-3 submit plan promises a withdraw window it cannot see | `known` flag; conditional sentence when unread | `7d7c3f6f3` |
| correctness-2 Withdraw reverts an approved change | routed change only ever withdraws; decided → "It has moved on" | `460dd1b09` |

**Never verified before — handled now (14; all real, all fixed)**
| Finding | Real? | What was done | Commit |
|---|---|---|---|
| tests-1 PA-R1 method half untested | real | test_12 base-user case, run_payroll + submit_run; removing `method_ok` makes it fail (the plan would be built or fail at `plan_preview`, never a `refused`/`no_right` card) | `547b33134` |
| tests-2 progress/result on an unconfirmed / other's task | real (code was right, untested) | test_05b | `547b33134` |
| tests-3 `_made_run` guard untested | real (code was right) | test_05c: other user's run, own run backdated before `confirmed_at` (SQL; in a test every `create_date` is the transaction clock) | `547b33134` |
| tests-4 test 7 refusal proves nothing | real | value still 777,000 (Desk preview `same`), task `done`, `undo_until` set | `547b33134` |
| tests-5 test 6 silent skip | real | explicit else-branch: no Undo, no `undo_until`, skip with reason | `547b33134` |
| tests-6 one tile compared, chunking never run | real | exact tiles; chunking pinned by a static guard on the driver (40-person fixtures would be slow and test the same code path) | `547b33134` |
| tests-7 force_clean scan too narrow | real | whole-tree scan + `drive.vals` keys | `547b33134` |
| tests-8 filing `_press` never asserted | real | one press with the plan's country/filing; none when pending | `547b33134` |
| tests-9 not-covered unchecked | real | covered 1 / not covered 1 case (also fixed "1 people" → "1 person … is not covered") | `ea400fa22` + `547b33134` |
| tests-10 audit not tied to the task | real | row `payai-<task id>`, ref run id, hand-made run has no PayAI line | `547b33134` |
| design-8 narrow rule keyed to the window | real in principle, minor in practice — one verifier "refuted" it because the Ask-tab drawer is 480 px (card ≈ 454 px), but the rule still answered the wrong question (window, not card) and the pill / small windows do go narrow | `.payai-card` is a size container; `@container payai-card (max-width: 340px)`: tiles 2-up, plan buttons full rows; old `@media` kept under `@supports not (container-type…)`; pill bubble holding a card takes the full row (a size container no longer sizes its parent). **libsass 0.22 on the server compiles it** and passes `@container` through unchanged (checked with `sass.compile` before deploy, mapping-compact recipe). No `min()`/`max()` | `ea400fa22` |
| design-11 progress bar a11y | real — the bar had no accessible name (a progressbar is not named by its content); the bogus max (100) only in the adopt-only edge (total 0), which one verifier rightly called rare | `aria-label` = progress label (falls back to card title); total 0 → no `aria-valuemax`/`aria-valuenow` (Owl drops an attribute whose value is `false`); progress words `aria-live="polite"` | `ea400fa22` |
| design-12 scheme question drops the person's word | real | "Which Retail scheme do you mean?" (word capped at 40 chars, a trailing "scheme" dropped, empty → old question). "your division" sublabel: **already there** — `resolve_scheme` / `reask_slot` read the scheme card's `mine` flag, which pb_demo's `get_defaults` sets from `res.users.pb_demo_division`; no generic "my division" exists outside the demo, so nothing more is cheaply knowable | `ea400fa22` |
| design-13 pay-value plan vague about approval | real | `UpdatePayData._records_route`: evaluates the change with the Desk's own `_evaluate`/`_plan_rows`/`_plan_touches`, builds the `pb.records.apply` IN MEMORY (`new`, same values `apply_changes` writes, `user_id` = asker), reads its own `_approval_context()`, `resolve_binding(company, 'records', scope, 'desk')`, then the shared `_route_steps` (engine preview → names; else the version's steps → needs/not, no names). Card says "need no approval: saved as soon as you press Do it" / "needs approval. It goes to X first" / "needs approval … the approver set up for pay changes"; anything unreadable keeps the old conditional sentence. Fingerprint unchanged (the result card already reports what really happened). Tests 07/07b assert the promise matches the outcome | `ea400fa22` |

**Refuted (6)**
- correctness-4 (finish drops the wizard's reason on blocked/confirm) — unreachable: prepare_run blocks only when `_period_runs` finds runs, and `finish` re-runs `plan_preview` on the same vals, so the named `_exists_card` is always shown.
- design-6 ("left" untranslatable) — Owl runs template text through `_t`, and the PO extractor collects `static/src/xml` text; P4 translates it like any other string.
- security-1 (callbacks not bound to the task's company) — 2 of 3: PayAI RPCs use the bare `rpc()` with no context, so the env company is the session's, not the switcher's; plan and Do it cannot diverge.
- security-3 (`pb_prepared_via` forgeable, `how` client-claimed) — 2 of 3: a display flag with the same trust as `pb_prepared_uid`; the audit of record is `payai.task` (PA18), which nobody can write.
- security-4 (browser run id can stamp a wizard-made run) — 3 of 3: `_made_run` only accepts the asker's own run for that month/scheme made after Do it; now also pinned by test_05c.
- security-5 (records proposals labelled 'desk') — 3 of 3: deliberate (PA26) — `source` is the Matrix kind key; 'payai' would skip the route the business published.

## Design-bar self-score (1–5, code-level only — not seen in a browser)
- Extreme WOW / best in class: **3** — one card, three states (plan → progress → result), pencils, countdown; unseen on screen.
- Hero moment = plan card: **4** — slots with origin pills that say why, exact counts (covered / not covered), the route
  stated up front on the pay-value plan, Do it / Open in the screen instead / Cancel.
- Zero dead-ends: **4** — expired, things changed, existing run, stopped when the page closed (PA29), undo too late
  (also when the countdown runs out on screen), officer cannot delete, route missing, moved on — each names its reason
  and next step.
- Plain language: **4** — screen words, the person's own word in the question, no model names (PA33), "Odoo" absent; VI not yet (P4).
- Motion with purpose: **3** — progress fill, countdown, head tint change; reduced-motion covers all transitions now.
- Fit: **4** — the card now answers to its own width in the drawer and the pill.
- Accessibility: **4** — named progress bar, polite live progress words, labelled pencils.
- Lucide / locked palette / no gradients / no emoji: **5**.

## DEPLOY NOTES (Fable deploys; builders do not — PA14 go-ahead first)
Modules changed since `9db1eed96` **by this program**:
| module | version | stored field? | installed where | upgrade |
|---|---|---|---|---|
| pb_payai_actions | 19.0.1.0.0 → **19.0.2.1.0** | yes: `hr.payslip.run.pb_prepared_via` (added BY this module); `payai.task` state `cancelled` (selection) | **payobook only** (owner decision) | payobook |
| pb_payrun_wizard | 19.0.1.31.0 → 19.0.1.32.0 | no (abstract wizard; `plan_preview` + JS driver) | every DB | payobook now with pb_payai_actions; tenants can wait (JS + Python only) |
| pb_settings | 19.0.1.9.0 → 19.0.1.9.1 | no (JS) | every DB | payobook now; tenants can wait |
| pb_learn | 19.0.20.3.0 → 19.0.20.4.1 (P2-F3) — **HEAD is now 19.0.20.5.0** from the Home P3 stream (`a6811b862`), and the tree holds another session's uncommitted pb_learn edits | no (JSON/JS) | every DB | deploy whatever pb_learn the Home stream ships; do not rsync the working tree while it is dirty |

PA23 check: the only new stored field (`pb_prepared_via`) lands through `pb_payai_actions`, which is installed on
payobook alone, so no other DB needs an upgrade for it. No module installed everywhere gained a stored field in P2.
Other modules changed since `9db1eed96` (biz_access, pb_dashboard, pb_demo, pb_demo_portal, pb_home_hub, pb_hub,
pb_import_kit, pb_people_hub, pb_records, pb_tenants, pb_vendor_access, biztinct_website) belong to the Home / Access
/ website streams — their own PENDING.md rows decide them.

Sequence (payobook only): `-u pb_payai_actions,pb_payrun_wizard,pb_settings[,pb_learn]` in one upgrade →
`DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` → restart. SCSS changed: compile `cards.scss` with the
server's libsass first (done for `ea400fa22`, compiles; a Sass error would blank the whole backend bundle and
`--stop-after-init` does not show it). Verify `ir_module_module.latest_version` = 19.0.2.1.0 on payobook and the
module tree hash. `docs/deploy/PENDING.md` row "pb_payai_actions → 2.0.0" should read 2.1.0 when Fable updates it
(not touched here — another session owns that file today).

## WALK LIST for Fable on payobook.com (visible DevTools window, PA24; console open)
Switch on first: Settings › PayAI can act → "PayAI may prepare" on (and "may look"); voice go-ahead OFF.
| # | Type (or do) | The card should show |
|---|---|---|
| 1 | "Open runs" | opens Pay Run › Runs straight away (not a lesson) |
| 2 | "Open approvals" | a question with two or more chips (Home / Mission Control) |
| 3 | Settings from the PayAI card | breadcrumb reads "Settings", not "Unnamed" |
| 4 | Helper drawer | banner: "Ask me to do something and I show you the plan first…" |
| 5 | "Run June payroll for Retail" (demo) | "Which Retail scheme do you mean?" with the scheme chips, your own division's chip sub-labelled "your division" |
| 6 | pick a scheme | plan card: Period / Scheme / Company ("current company") / People ("All N covered by this scheme") / Pay data, each with a pill, pencils on the editable ones; note "No June run exists for … yet"; buttons Do it · Open in the screen instead · Cancel; footer "Nothing has been done yet…" |
| 7 | tap a pencil (Scheme) | the scheme chips again; picking one redraws the same plan card |
| 8 | Do it | same card turns "running": named progress bar fills "Computing payslips… n / N"; then "Run prepared: …" with tiles (payslips in draft · net to pay · need a look), the plan slots kept, Open the run · Send for approval · Learn to do this yourself, an indigo undo strip with a live countdown, and "Recorded: run … prepared by PayAI for <you>…" |
| 9 | Pay Run › Runs board | the new draft's history says "Prepared by <you> through PayAI" |
| 10 | Undo (within 10 min) | "Undone — the draft run and its N payslips were deleted"; "Prepare it again" chip |
| 11 | let the countdown reach 0 on another run | strip changes to too-late; no live Undo button |
| 12 | "Run June payroll for <scheme>" again → **Open in the screen instead** | Run Payroll opens with period + scheme filled in; nothing ran |
| 13 | ask again for a month that already has a run | blocked card "A June run for … already exists" + Open it; no Clean button anywhere |
| 14 | "Send the June <scheme> run for approval" | plan with Run / Figures / Route; "It goes to <name> first" (or the conditional sentence for non-config users); Do it → "Sent for approval", Withdraw strip |
| 15 | "Give <person> a <allowance> of 500,000" | plan says up front either "Pay changes here need no approval…" or "This change needs approval. It goes to …"; Do it matches what it said; Undo/Withdraw |
| 16 | say "go ahead" by voice with the switch OFF | note "A spoken go-ahead is switched off here, so I did nothing"; typed "go ahead" → "Typing it does not count" |
| 17 | "Prepare the June tax filing" | "Nothing is sent to the authority" plan, or a plain "needs the Government Reports permission" card |
| 18 | narrow the drawer / a phone width | tiles two across, plan buttons one per row; no horizontal scroll |
| 19 | Run Payroll screen itself (no PayAI) | runs exactly as before (shared driver regression) |
| 20 | Learn `sc_payrun` replica | unchanged |
Any "Odoo" on a card, toast or refusal = fail.

## Open questions / items for P3 (`P3_HANDOVER.md` draft)
- P3 Red cards should reuse `_route_steps` for "who comes next" (it reads the route as the person, with the same
  preview-or-steps fallback), and the plan-promise-matches-outcome test pattern from 07/07b.
- The typed-word confirm (P3) needs its own visible input on the plan card; the container query already gives the
  card full-row buttons in narrow drawers — put the word field above them.
- PA28 decision still open (pass `formula_config_id` to `compute_batch` — screen and PayAI alike).
- Idempotency keys on the Records / delivery / filing engines (deviation 3) — engine-side.
- The Compliance screen itself fails for an officer without Government Reports (PA32) — screen work outside PayAI.
- VI for every P2 string (P4); "your division" stays demo-only until a real "my division" exists.
- Browser walk (list above) before P3 starts building on the card.

## Modules touched (manifest versions)
| module | version | why | state |
|---|---|---|---|
| pb_payai_actions | 19.0.1.0.0 → 19.0.2.1.0 | Amber Actions, runner RPCs, `hr.payslip.run.pb_prepared_via` (stored), `payai.task` state `cancelled`, card states; review fixes; gap-round design fixes | committed `0d869baaa` … `ea400fa22`, tests `547b33134` |
| pb_payrun_wizard | 19.0.1.31.0 → 19.0.1.32.0 | `plan_preview` (`@runner_only`), shared `run_driver.js`, prefill — no stored field | committed `c5b77d6be` |
| pb_settings | 19.0.1.9.0 → 19.0.1.9.1 | P2-F2 breadcrumb name (JS) | committed `3aec1388d` |
| pb_learn | 19.0.20.3.0 → 19.0.20.4.1 | P2-F3 helper banner, EN + VI (now superseded by Home's 20.5.0 at HEAD) | committed `bbcbcabf8` |
