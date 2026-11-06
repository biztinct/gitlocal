# PDR P1 — report (fast worksheet, honest red cells, final-tax-month reminder)

Spec: `PDR_P1.md`; rules and gotchas: `PDR_LEDGER.md` (G7–G13 added by this phase).
Implementer: Opus, 2026-11-05.

## 0. In plain words

* "Review pay data" for Rize Indonesia (113 people) opened in **48.7 s**; it now
  opens in ****about 10 s on the server and 12 s until the grid is on screen**** on the live server. The calculation-preview columns
  fill in behind it, 20 people at a time, with "Working out previews · 40 of 113"
  next to "Saved on server".
* Red "Needs a value" cells: **1,240 → 1**. The one left is real
  (BPJS TK covered missing for one person).
* "Employer reimburses employee BPJS" reads **0** with the note "No line on the
  contract, so this is No (the usual answer)." The 10 period columns are quiet
  blanks that count as 0 / No.
* People in their final tax month (December, or the month they leave) get a calm
  blue reminder on Final tax period — never a block. On the live October run
  that is already **7 people** (their contracts end in October).

## 1. Before / after

Live "before" lines are from `/var/log/odoo/odoo-server.log` (2026-11-05 01:38 /
01:42, owner's session). "Copy" = a throwaway copy of rize with the new code,
served by its own `odoo-bin` on port 8195 (shared, busy 2-core box — G9).

| What | Before (live) | After (copy, served) | After (live) |
|---|---|---|---|
| Open "Review pay data" | 48.7 s, 15,519 queries (4.9 s SQL + 43.8 s other) | 11.7–13.1 s, 2,436–2,523 queries (22.3 s once during another deploy) | 08:13 (first after restart): 9.9 s, 2,494 queries (1.10 s SQL + 8.85 s); 08:18 warm: 10.4 s, 2,428 queries (1.15 + 9.24). Browser, grid on screen: 11.9 s / 12.4 s |
| One cell save | 52.3 s, 15,640 queries | 11.5–12.3 s, 2,646–2,653 queries | not measured live (a save on #19 is forbidden); copy: 11.5–12.3 s |
| Calculation previews, all 113 | never ran (every row had an issue — G5); estimate ≈ 16 min at 8.77 s/person | 23–27 s in 6 calls of 20 (2.9–5.6 s each), after the grid is on screen | 6 calls, 2.5–3.7 s each; all previews on screen 19–21 s after the grid |
| Evaluator per person (scheme 7121, 409 rules) | 8.77 s served (ledger); 4.76 s in a shell | 0.031 s with the call's memo; 0.91 s without (first person of a call builds the program) | — |

Shell breakdown of resolving the 113 people, old → new (wrappers, not served):

| Part | Old | New |
|---|---|---|
| dependency walk (226 calls) | 59.4 s | 1.3 s (10 distinct walks) |
| calendar hours (7,006 calls) | 50.1 s | 0.18 s (62 calls) |
| period-input lookups (domain values) | 29.3 s (with record reads) | one search per call |
| settings stamp (113) | 10.7 s | 0.1 s (1) |
| catalogue (113) | 6.7 s | 0.04 s (1) |
| legacy record resolver (unchanged, non-goal) | 19.7 s | ~same; now the largest remaining cost |

Fresh profile of the open (copy, cProfile, inflates ~4.7×) — top items after
S1–S3, before S4: `biz_access … __getattribute__` 40.8 s self time of 112 s
(36 %), `fields.__get__`, the legacy resolver chain
(`pb_timesheet_approval` → `pb_trip_payroll_bridge` →
`pb_workforce_payroll_bridge` → `hr_payslip_formula._get_formula_input_values`,
40 s cumulative), `_application_record_context_values` (29 s cumulative,
`check_access` 16 s, `fields_get` per key), `_has_field_access` (970 k calls,
19.7 s), period-input `search` (fixed), `_mark_cells` 8.3 s, refresh 8.0 s,
time values 7.2 s, `deepcopy` 5.1 s (now marshal).

## 2. S4 (biz_access)

**Ran.** Trigger met: the attribute hook was 36 % of the profiled open (> 15 %).
`RESOURCES` is a module-level dict built at import and never mutated
(`studio_catalogue.py:37`; every other use reads it). Change: a module-level
`frozenset` of every catalogue field name; any other attribute name returns
`super().__getattribute__(name)` at once. Identical behaviour; new test
`biz_access/tests/test_pdr_attribute_hook.py` proves every catalogue field
still reaches `_studio_attribute_check`. biz_access 19.0.1.10.4.

## 3. Exactness and tests

* **E1** — all 113 people of prep #19, blank → 0 as the worksheet does, old
  readonly loop (copied verbatim into the script, calling `_run_formula`) vs
  new: **113 / 113 identical** (keys, order, values, types, `errors`).
* **E2** — old code's `workspace()` (before the data step) vs new code's (after
  it) on the copy: **0 unexpected differences**. Differences found, all
  allowed: IDERREIMBUBPJS 109 cells (issue/reason/status/tone/usual_answer/value),
  the 10 period columns 113 cells each (issue/optional/tone; +reason/remind on
  7 IDFINALTAXPERI cells), 10 column `optional` flags, 2,599 result cells
  `preview` added (value still None), top-level issues/affected/optional/
  reminders. Issues 1,240 → 1.
* **E3** — payslip twin (application mode), old loop vs new, 10 people:
  **10 / 10 identical** (results and log lines).
* E1–E3 ran before the last two speed commits (`checked_read` memo, marshal
  copy, S4). None of those touch the evaluator; the suites below cover them.

Unit tests (new, in `pb_hr_payroll_formula/tests/test_payroll_preparation.py`):
T1–T11 all pass (`TestPayrollPreparation`, 39 tests incl. inherited, 0 failed,
on the rize copy). Four existing assertions that read preview values out of
`workspace()` now read them from `preview_rows` (G7).

Full suites on a throwaway copy of p0clone (scratch addons, new code), then every
failure re-run on the OLD live code on the same copy:

| Suite | Tests | Fail / error (new code) | Same on old code? |
|---|---|---|---|
| pb_hr_payroll_formula | 678 | 6 (TestImportApproval m08b; TestRd49SyncCost 02ab, 02i; TestRecordsR1OneTime 05, 07, 07b) | yes, all 6 — **pre-existing** (copy has jobs off; brand reads "Rize"; approval settings) |
| pb_payrun_wizard | 84 | 0 | — |
| pb_formula_studio | 516 | 7 (TestOneMappingHome ×4, TestJourneyView 04a, TestNetPayCandidates 01, TestRunsrcPcBoardLane 14) | yes, all 7 — **pre-existing** |
| biz_access | 218 (incl. the new S4 test, which passes) | 6 (TestAccessRequest q09a/b/c/e/g, TestThePeopleList platform recovery) | yes, all 6 — **pre-existing** (copy has logins off) |

**No new failures.** (The first full run was killed at 07:51 by another
session's deploy; the remaining suites were re-run afterwards.)

## 4. Red cells on prep #19 after deploy, by column

Read-only shell on rize after the data step (rolled back), and the live screen:

| Column | Before | After |
|---|---|---|
| BPJS TK covered (IDBPJSTKCOVERE) | 1 | **1** (real: one person has no line) |
| Employer reimburses employee BPJS (IDERREIMBUBPJS) | 109 | 0 (reads 0, "usual answer") |
| Final tax period, Prior YTD taxable gross, Prior YTD deductible JHT and JP, Job expense eligible months, Prior YTD PPh21 withheld, Prior qualifying severance paid, Prior severance tax withheld, Approved final-period tax allowance, Final-period YTD reviewed, Severance eligibility confirmed | 113 each (1,130) | 0 (quiet "Optional · left blank") |
| **Total** | **1,240** | **1** |

Header: "1 cells need attention · 1 employees affected · 2979 blank cells".
Reminders: 7 people (Aradea Putra Suriya, Ayul Nasrullah, Didik Imam
Kholistiawan, Isna Arfiani Rosyida, Muchamad Salman Firdaus, Oky Tio
Wijanarko, Wulan Aryanti) — all "last month of work" in October.

## 5. Indonesia Compute time (measured only)

Measured only, on a throwaway copy of rize (rolled back, then dropped). The
October Indonesia run has not been created yet, so the August application-mode
test run **2114** was used. Only **3 of its 122 payslips compute** today; the
other 119 are refused by their own data checks ("Application payroll needs
attention") in both old and new code — so "20 people" could not be timed.

| Code | Per computed payslip | Batch of the same 3 |
|---|---|---|
| Old (live tree before P1) | 5.45 / 5.32 / 5.38 s (avg 5.38) | 12.8 s |
| New (P1) | 3.25 / 2.57 / 2.57 s (avg 2.80) | 5.5 s |

## 6. What generated the rize rules

* `tools/migrate_rize_application_sources.py` + `tools/data/rize_application_source_plan.json`
  wrote the period sources on the Indonesia master scheme
  (`RIZE_INDONESIA_CLIENT_MASTER_2026`, 7096) with `zero_allowed: false`;
  `tools/replace_rize_payroll_schemes.py` (plan `rize_focused_payroll_plan.json`)
  copied the rules into the focused schemes (7116 draft, 7121 active), so the
  flags travel with `rule.copy`.
* Changed: the plan now has `zero_allowed: true` for the 10 R1 codes and
  `final_period_flag: true` on IDFINALTAXPERI; the migrate script writes
  `application_final_period_flag` from it (guarded on the field existing).
  Commit `b593cdac8`.

## 7. IMPORT-GENDER (§6)

Not shipped by PDR. Its own session deployed it 07:31–07:38 UTC from
`git archive 503279518` only (live `pb_hr_payroll_formula` 19.0.1.163.2), per the
coordinator's arrangement. PDR's 19.0.1.164.0 goes on top; the live-vs-stage tree
diff before the deploy is in §10.

## 8. Deviations

1. **Open time** — target ≤ 10 s (stretch 6 s) is met on the server (9.9–10.4 s)
   but not in the browser (11.9–12.4 s until the grid shows; the rest is the
   4.6 MB worksheet payload and drawing ~11,000 cells). The largest remaining
   server cost is the legacy record resolver (`_get_formula_input_values`
   chain, ~35 % of the open), which P1 was told not to change. Options for a
   follow-up, smallest first: trim the per-cell payload (reason/source text
   only on demand); memoise the scheme-level parts of the legacy resolver
   inside the same request memo (needs an owner/Fable call because it is the
   legacy resolver); render rows lazily in the grid.
2. **Reminder text** says "Set Final tax period to Yes (1)" — the "(1)" tells a P1
   user what to type in a number cell; P2 (Y / N) should drop it.
3. **Extra speed work beyond S1's list**, all inside the same request memo:
   one period-input search per call instead of one per component per person;
   source-record permission answers remembered per call (granted checks only);
   the worksheet's own source rows reused within one call (a save no longer
   resolves 113 people twice), copied with `marshal`.
4. Wrapped two more batch entries in the memo besides the listed ones:
   `hr.payslip._application_assert_current` (approval re-checks) and
   `compute_sheet_with_formulas` (the batch compute entry, as asked).
   `submit_record_changes` is deliberately NOT wrapped (it may change records
   between its reads).
5. `formula_program.py` is a new pure-function module (no model) holding the
   compiled evaluator, shared by both evaluators. Conversion/compile failures
   now log once per program build instead of once per evaluation.
6. Server-side words added in P1 are English only (no vi_VN entries yet).

### Self-review against the non-goals and decisions

| Non-goal / decision | Held? |
|---|---|
| No Y / N display | Yes — cells still show numbers (0 / 1). |
| No formula text, `value_kind` or contract storage change; no new contract lines | Yes — D2 only reads "no line"; T2 asserts the line count is unchanged. |
| No change to the legacy (spreadsheet) resolver | Yes — `_get_formula_input_values` and the import-batch resolver are not in the diff. |
| `evaluate()` (non-readonly) writes unchanged | Yes — only the readonly paths use `formula_program`; `_run_formula` got DEBUG guards only. |
| Approval / certification semantics | Yes — `review()` still needs the checklist + note; T5 reviews with reminders showing; sealed runs re-validate as before. |
| No Formula Studio UI for the flag | Yes — data only (field + generator). |
| BPJS TK / health requiredness untouched | Yes — still red when missing (T3; 1 live). |
| No Compute redesign | Yes — only the request memo around the batch (measured in §5). |
| D4: memo never outlives a call; no module/ormcache caches | Yes — T6; the only module-level object is S4's static frozenset, which the handover asked for. |
| "Odoo" never on screen | Yes — no new user string contains it. |

## 9. Screenshots

`docs/handovers/paydatareview/p1_shots/` — `B1_B2_B4_open_streaming.jpg` (grid open, "1 cells need attention", reminder line,
"Working out previews · 20 of 112"), `B2_next_issue_bpjs_tk.jpg`,
`B3_reimburses_usual_answer.jpg`, `B5_final_tax_month_reminder.jpg`,
`B6_vietnam_unchanged.jpg`.

| Check | Result |
|---|---|
| B1 open ≤ 10 s | **Partly.** Server 9.9 s / 10.4 s; grid on screen 11.9 s / 12.4 s (was 49 s). |
| B2 header ≈ 1 cell; Next issue lands on it | **Pass** — 1 cell, lands on BPJS TK covered (Arief Andani Hidayat). |
| B3 Employer reimburses reads 0 with the note; period columns quiet | **Pass** |
| B4 previews fill progressively; text disappears; console clean | **Pass** — "Working out previews · N of 112", gone at the end, 0 console errors. |
| B5 reminder line, filter option, calm tone | **Pass on live October data** (7 real people), no December copy needed. |
| B6 Vietnam 7118 looks the same apart from speed | **Pass** — 9 cells / 3 people, no reminder line, grid 5.1 s, previews done 9.6 s; no Vietnam rule meets the D2 or D3 condition, so its cells cannot change. |

How the worksheet was opened: the step-1 screen unticks this month's 7
leavers by default (106 people), and opening a different scope creates a new,
undeletable preparation. So B1–B6 opened the real `PayrollReviewDialog` from
the browser console with the exact scope of prep #19 (113) and Vietnam prep #1
(50) — the same RPC the screen makes. Both preps were checked afterwards:
still revision 1, unchanged write dates, no new preparation.

## 10. Commits, versions, deploy, undo

Commits on `19.1` (pushed):

| Commit | What |
|---|---|
| `f253c2942` | WIP (committed on the coordinator's ask after the usage-limit pause): memo, S1, S2 `formula_program.py`, S3 `preview_rows` + streaming JS, D2, D3 field + reminder + UI, tests T1–T11 |
| `c111a1227` | S4 — biz_access attribute hook fast exit + test |
| `ad8bb4d16` | S1 — permission answers once per call; marshal copy |
| `b593cdac8` | rize generator plan + migrate script (R1/D3) |
| `44926bd92` | versions + ledger G7–G13 |
| (this commit) | report + 5 screenshots |

Versions live ×4 (payobook, payobook_template, p0clone, rize):
`pb_hr_payroll_formula` 19.0.1.164.0, `pb_payrun_wizard` 19.0.1.42.0,
`biz_access` 19.0.1.10.4. Deployed 08:03:51–08:10:09 UTC from `git archive
b8a40f474`, `filter_deploy.sh full`: EXIT=0 errors=0 ×4, crons 33/29/76/44
unchanged, tree hash = stage ×3, latest_version ×4, assets purged +
`web.assets.version` bumped ×4, sites 200. Backups
`/odoo/backups/pdr-p1-run-20261105080351`.

Proof the deploy diff was exactly P1: `diff -rq` live vs stage listed the same
18 files as the PDR commits touch (2 new), and each of the 16 changed live
files was byte-identical to its version at `ef6536b89` (the commit before the
WIP) — so nothing of anyone else's rode along. Live before = 163.2 (IMPORT-GENDER,
deployed by its own session from `503279518` at 07:31–07:38).

Deploy-notes lines (all 2026-11-05 UTC): 04:48 proof copy DATA → 07:31 DATA
DONE; 05:10 tests TEST → 07:31 TEST DONE; 07:29 NOTE to IMPORT-GENDER; 07:42
compute timing DATA; 07:4x tests TEST / 07:53 NOTE (run killed) / 08:03 TEST
DONE; 08:03 PDR P1 START → 08:10 DONE; 08:10 rize data START → DONE.

**rize data step (undo):** backup table `rize.pb_bak_pdr_zero_20261105`
(30 rows). To undo:

```sql
UPDATE hr_formula_rule r
   SET application_zero_allowed = b.application_zero_allowed,
       application_final_period_flag = b.application_final_period_flag,
       write_date = now() at time zone 'utc'
  FROM pb_bak_pdr_zero_20261105 b
 WHERE r.id = b.id;
```

Run as `sudo -u postgres psql -d rize`. It puts back `false` on all 30 rules
and moves `write_date` so the settings stamp changes again.
