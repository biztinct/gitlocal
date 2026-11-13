# UPDATES — Phase 5b report (two owner follow-ups to P5: the "confident zero", demo taxable pay)

Implemented, tested, deployed and checked on 2026-11-13 by the Opus implementation agent, against
the owner's prompt of 2026-11-13 (this phase had no separate handover: the prompt was the spec) and
`UPDATES_LEDGER.md`. Decisions recorded as **D27** (item A) and **D28** (item B). Facts **U47–U48**,
gotchas **G84–G88** (G80–G83 are WORKFLOW-2 numbers quoted in the shared deploy notes; skipped
here to avoid two meanings).

R0 below was written BEFORE the deploy.

## R0. Rollback note (written before deploying)

- **What the deploy changes.** Files only, on the one addons directory (so all five databases at
  once): `pb_hr_payroll_formula` (three Python files, one appended `vi_VN.po` entry, one new test
  file) and `pb_demo` (two Python files). **No `-u`, versions unchanged** (`pb_hr_payroll_formula`
  19.0.1.165.0, `pb_demo` 19.0.1.14.1 — `latest_version` keeps matching the manifests), one service
  restart. No schema, view, data, job or mail change. `pb_demo` is installed on `payobook` only.
- **Files:** the previous trees (= repo `7192505e3`, hashes `91c5e875ea31d67a` / `6df18c98d50a850d`)
  are kept as `/odoo/backups/updates-p5b-<TS>/{pb_hr_payroll_formula,pb_demo}.prev`. Restore = scoped
  `rsync -a --delete <m>.prev/ /odoo/odoo-server/addons/<m>/` for each, then
  `sudo service odoo-server restart`. Nothing else: no upgrade was run, so none is needed back.
- **Data:** five dumps `/odoo/backups/updates-p5b-<TS>/<db>.pre-updates-p5b.dump`, taken before the
  files change. The code writes nothing on deploy; a restore of data should never be needed.
- **What a rollback leaves behind:** demo pay runs generated on payobook after the deploy keep their
  stored calculation results (`formula_computed_values`); the old code ignores them and reports read
  them exactly as they read any engine-computed payslip. Nothing else.
- Nothing is applied, backfilled or changed on `rize` or `sudima`; no joining date is filled in
  anywhere.

---

## R1. What shipped

| Module | Version | Where | What |
|---|---|---|---|
| `pb_hr_payroll_formula` | 19.0.1.165.0 (unchanged, files only) | all five | D27: `_application_history_value` answers "not known" with a sentence instead of `0.0 zero_confirmed` when the joining date is blank and the contract start drove the lower bound; the sentence in the reader's language on the worksheet cell and in the payslip stop; one `vi_VN.po` entry (append only); 8 tests |
| `pb_demo` | 19.0.1.14.1 (unchanged, files only) | payobook (the only database it is installed on) | D28: new demo payslips keep their calculation results (`formula_computed_values`), as every engine-computed payslip does |

Commits: `64629c4b9` (engine, D27) · `471da8baf` (demo, D28) · the docs commit carrying this report
and the ledger. No file in `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff` or
`docs/handovers/workflow2` was touched; nothing under `outputs/` committed.

## R2. Item A — the "confident zero" (D27)

**Before.** The engine's own year-to-date source (`history.ytd.<CODE>`, application-data runs only)
took the person's start as `date_of_joining or contract.date_start`. A blank joining date with a
contract made at go-live (the shape of every client that moved to Payobook mid-year) gave
`0.0 zero_confirmed`, "no prior service days this year" — a confident zero for everything paid
before Payobook.

**After** (`application_domain_sources.py`, `_application_history_value`):

```python
start_known = bool(employee.date_of_joining)
joined = employee.date_of_joining or (contract.date_start if contract else False)
...
lower = max(year_start, joined)
if lower >= start:
    if not start_known and joined > year_start:
        return source_result(reason=HISTORY_START_UNCONFIRMED_REASON,
                             why='employment_start_unconfirmed_for_history')
    return source_result(0.0, 'zero_confirmed', reason='no_prior_service_days_this_year')
```

| Case | Before | After |
|---|---|---|
| No joining date, contract starts on / inside the period (after 1 January) | 0 (confident) | **not known**, with the sentence |
| Real joining date this year, no earlier pay | 0 | 0 (unchanged) |
| Joining date last year, no payslips | not known (`posted_history_or_opening_balances_missing`) | unchanged |
| No joining date, contract earlier this year, no payslips | not known | unchanged |
| January period (the year starts with it), joining date or not | 0 | 0 (unchanged — calendar-year rule) |

The sentence (stored in English, like the P2 "usual answer" sentence, because it enters the
worksheet facts and fingerprints; shown in the reader's language by `shown_reason` on the worksheet
cell and in the payslip stop "Application payroll needs attention: …"):

- EN: "The employee record has no Date of Joining, so what was paid earlier this year is not known.
  Add the Date of Joining to the employee record."
- VI: "Hồ sơ nhân viên chưa có ngày vào làm, nên chưa biết đã trả bao nhiêu trước đó trong năm nay.
  Hãy thêm ngày vào làm vào hồ sơ nhân viên."

No "Odoo"; the field is named by its screen label (Date of Joining). No joining date was filled in
on any database.

## R3. Item B — demo taxable pay (D28)

**What the view reads.** "Taxable pay · paid in Payobook" for the demo company adds up the code
`TXBASE` (the P5 default: the first of `TXBASE/TAXABLE/TAXABLEINCOME/PITBASE` the company's schemes
have). `TXBASE` is a helper the demo schemes compute but do not print, so it has no payslip line;
the view then reads it from the payslip's stored calculation results (`formula_computed_values`).
The demo shortcut (Run Payroll for a division, and the history generator) built the lines from the
engine's results but never stored the results — every other engine path does
(`hr_payslip_formula.py:214, 1207`, `payroll_import_batch.py:3961`). Now it does
(`demo_payrun.py` both run paths, `demo_history.py` mid and end).

**Existing demo payslips were NOT given the figure (the owner's last fallback: new runs only).** The
two ways an existing payslip could carry it are both visible to a report:

1. **Only `TXBASE` in the stored results** — the Pay run results screen (`pb_payrun_results`) and
   several other readers switch from payslip lines to the stored results the moment a payslip has
   any (`use_fcv = bool(slips[0].formula_computed_values)`; `_slip_values` prefers it). A one-value
   store would blank every column of every demo run on that screen.
2. **The full re-derived results** — the numbers for printed items would match the lines, but the
   Vietnam payslip report (`hr_payslip_vietnam.py:206-219`, its `computed` lookups), the period
   comparison, the scheme simulator's baseline, the shadow run, the Source Atlas and the demo
   walkthroughs' stand-in all start reading values they did not see before (e.g. a taxable income
   where the print showed nothing). A report could notice.
3. A new `TXBASE` payslip **line** would enter every line-reading report (statutory tax-category
   sums, explorer facts, Pay run results totals).

So the 34,322 existing payobook payslips, their lines and every run total are untouched (proof R5),
and only demo pay runs generated from now on carry taxable pay. Owner decision R9.1.

**What the demo view now shows.** On live payobook nothing visible changes until a new demo pay run
is finished. Proved on live inside a rolled-back transaction (R6.3): a new Corporate run for December
2026 (500 people) → the view's Taxable pay "paid in Payobook" went from **3 numbers / 497 dashes to
500 numbers / 0 dashes** (e.g. Trần Bích Vy 8,128,000 ₫). Caveats in R8 (G85–G87): that number is
December's only (the April–July payslips still carry no taxable pay), it counts a negative taxable
base as positive, and a mid-month advance's payslips double gross pay in that view.

## R4. Tests

| Suite | Old code (HEAD `7192505e3`) | New code |
|---|---|---|
| `pb_hr_payroll_formula`, local isolated tree (G13: `git archive HEAD` + the two modules), copy of the template shape `upd_p3c_t_tpl`, `-u pb_hr_payroll_formula` | 691 tests, 4 failed | **699 tests, the same 4 failed** (identical list) |
| of which `test_application_payroll_source` | 34, 0 failed | **34, 0 failed** |
| new `test_application_history_ytd` | — | **8, 0 failed** |
| live p0clone after start (ports 8471/8472, no upgrade: post-install tests of the loaded module) | — | **42 (34 + 8), 0 failed, 0 ERROR** |

The 4 failures are pre-existing on that template copy and fail identically on HEAD:
`TestRd49SyncCost.test_02ab` (the sync job is inactive on the copy), `.test_02i`,
`TestRecordsR1OneTime.test_07b`, `TestSchemeCtxCurrency.test_04` ("fixture is degenerate — pick
another currency").

New cases (`pb_hr_payroll_formula/tests/test_application_history_ytd.py`):

| # | Case | Result |
|---|---|---|
| H1 | blank joining date + contract at go-live (and a contract starting mid-period) → missing, the sentence, `why = employment_start_unconfirmed_for_history` | PASS |
| H2 | real joining date this year (1st and mid-period), no earlier pay → `0.0 zero_confirmed`, as today | PASS |
| H3 | joining date last year, no payslips → `posted_history_or_opening_balances_missing`, as today | PASS |
| H4 | blank joining date, contract earlier this year, no payslips → missing as today | PASS |
| H5 | January period, blank joining date (contract last year / on 1 January) → 0, calendar-year rule | PASS |
| H6 | a code not in the scheme → unchanged reason | PASS |
| H7 | a required pay item reading `history.ytd.*`: the person's row is blocked with the sentence and no value; with a real joining date this year the same item is 0 and not blocked | PASS |
| H8 | sentence: no "Odoo", no code words; English unchanged; Vietnamese loaded when the language is active | PASS |

`.po`: append only (the old file is a byte prefix of the new one); `PoFileReader` 3,982 rows; the
entry carries `#. module:`, `#. odoo-python`, `#: code:` (G2); 0 "Odoo" in any msgstr. Python code
translations are read from the `.po` on disk at run time (`CodeTranslations`), so a restart loads
it — checked on a local copy and on live rize (R6.2).

Demo (item B) has no unit test: the generator needs the demo world. It was proved on a fresh copy of
live payobook and on live payobook inside a rolled-back transaction (R5, R6.3).

## R5. Before/after proofs

**A — inertness.** Read-only census on all five databases (live, before the deploy and again after):
**0 scheme items with an `application_source_key` starting `history.ytd.`** (0 even counting any
key containing "history"). Then a fresh read-only dump of live **rize** restored locally
(`upd_p5b_rize`, scheduled jobs and mail servers switched off), captured with the old code and the
new code (`a_capture.py`, rolled back):

| What | Size | Old vs new |
|---|---|---|
| all 10 application-data preparations (`_resolved`: every person's inputs, values, sources, blockers) + their fingerprints | 676 person rows | **identical** |
| the same 10 worksheets (`_workspace`, what the screen gets) | 10 | **identical** |
| `_application_employee_inputs` for every person the scheme map sends to each of the 8 application-data schemes, November and December 2026, full coverage | 225 people × 2 months (126 Indonesia) | **identical** (16 hashes) |
| the changed function itself, asked directly for Indonesia person 5228 (no joining date, contract 11 Feb 2026) at the contract start | | `0.0 zero_confirmed` → **missing + the sentence** |
| same person, December | | missing (`posted_history_or_opening_balances_missing`) both |

So the change is live in the function and reaches nothing any scheme reads today.

**B — demo totals.** All 51 pay runs of the demo company on payobook (the memory note's "47" was
the count of 2026-09-22; four more exist now), per run: stored gross / deductions / net / employer
cost, payslip count, line count, line sum, a hash of every line (id, payslip, code, amount, pay
role) and a hash of every payslip (state, stored inputs, stored results):

| Where | Before vs after |
|---|---|
| fresh local copy, after both experiment runs (rolled back) | **identical** (51 rows) |
| live payobook, before the deploy vs after the deploy | **identical** (51 rows) |
| live payobook, after the rolled-back live check | **identical** |

A NEW demo run, old code vs new code, on the copy (Corporate, December 2026, 500 people): lines
(13,000, hashed by person/code/amount/pay role) **identical**; run totals **identical** (gross
18,720,648,315 / deductions 3,151,310,744 / net 15,569,337,571 / employer 2,666,589,000); stored
results 0 → 500; every stored `TXBASE` equals the payslip's own figures (GROSS + SIEMP + HIEMP + UIEMP
− DEDUCTSELF − DEDUCTDEP × DEPS): **500 of 500**, and every printed item in the stored results
equals its line (0 mismatches). 29 of the 500 have a negative taxable base (reliefs larger than pay).

## R6. Deploy evidence (five databases)

Unit `updates-p5b-20261112T215452Z` under `flock /tmp/payobook-studio-deploy.lock` (free; the last
entry before it was the UPDATES P4b DONE at 21:07). START 21:54 / DONE 21:58 UTC lines in
`/opt/deploy-notes.md`. Evidence `/tmp/updates-p5b-20261112T215452Z/` on the server. Tier 3.

- Before: server trees = repo `7192505e3` (`pb_hr_payroll_formula` 91c5e875ea31d67a, `pb_demo`
  6df18c98d50a850d). Staged = commit `471da8baf` (c261708a58c1fa9f / f1b68a10427ae9c2). Clean staging
  folder; scoped rsync of the two modules only; no standard addon.
- **Backups before anything changed**: `/odoo/backups/updates-p5b-20261112T215452Z/` — payobook
  79,273,016 B, payobook_template 28,035,363, p0clone 28,377,788, rize 41,712,692, sudima 27,946,979
  (`*.pre-updates-p5b.dump`), plus both previous trees.
- **Files only, no `-u`** (Python + one code translation, nothing that needs loading into a
  database). Versions unchanged, as P3a/P3c did for files-only modules: `latest_version` still
  equals the manifests on all five (bumping the manifest without an upgrade would break that check).
  `pb_hr_payroll_formula` is the base of ~150 modules; not upgrading it is also what kept every
  scheduled job untouched.
- **Downtime ≈ 32 s**: shutdown 21:56:47, listening 21:56:53, first registry loaded 21:57:19.
  **No test in the stopped window** (G19).
- Active scheduled jobs: identical id lists before/after — **50 / 32 / 39 / 82 / 81**.
- Users, payslips (count + state / inputs / results hash), payslip lines (count + sum), pay runs,
  employees (and how many have a joining date: payobook 4,502/4,575, rize 117/258, template 0/3,
  p0clone 0/14, sudima 650/653), year-to-date rules (0), preparations (rize 10, hash), mail queue:
  **identical before/after on all five**.
- After: server tree hashes = repo; sites payobook.com, rize, p0clone, sudima 200; one service
  process; server log since the restart: 0 ERROR.

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_hr_payroll_formula` latest_version | 19.0.1.165.0 | 19.0.1.165.0 | 19.0.1.165.0 | 19.0.1.165.0 | 19.0.1.165.0 |
| `pb_demo` | 19.0.1.14.1 | not installed | not installed | not installed | not installed |
| `history.ytd.*` items | 0 | 0 | 0 | 0 | 0 |
| active jobs before → after | 50 → 50 | 32 → 32 | 39 → 39 | 82 → 82 | 81 → 81 |

**Live checks after start** (server-side; logs in the evidence folder, 0 ERROR in each):

1. p0clone tests (R4): 42, 0 failed.
2. **rize, read only, rolled back**: person 5228 at the contract start → missing + the sentence;
   December → missing as before; the Vietnamese sentence loads; 0 `history.ytd.*` items.
3. **payobook, everything rolled back** (as the admin, company Payobook Vietnam JSC): a new Corporate
   demo run for December 2026 computed (500 payslips, all with stored results and `TXBASE`) and
   finished inside the transaction; the view for those 500 people: Taxable pay "paid in Payobook"
   **3 numbers / 497 dashes before → 500 numbers / 0 dashes after**; rolled back — pay runs 53 → 53
   (highest id 2419 both), mail 3,135 → 3,135, the 51 demo runs' totals identical.

Browser: not walked. Nothing on any screen changed on live (no backfill, no new run kept); the view
was checked server-side with the screen's own method (`_ytd_rows`). No sign-in with a password.

## R7. Deviations, and why

1. **The fix is narrower than P5's sketch.** P5 proposed "missing whenever the joining date is
   blank". That would also turn the January zero (the year starts with the period, so nothing can
   be earlier this year) into "not known". The rule asked for: missing ONLY where the fallback date
   produced the zero, i.e. blank joining date AND the contract start after 1 January.
2. **New demo runs only** for item B (R3): both ways to give existing payslips the figure are seen
   by reports. Owner decision R9.1.
3. **Stored results on every newly computed demo payslip** (mid-month advances too, in the history
   generator), because that is what the engine stores for every payslip it computes. The view's
   doubling of mid + end (G87) is the view's, not this change's.
4. **Files-only, versions unchanged** (not bumped): the precedent for files-only modules, and a bump
   without `-u` would leave `latest_version` behind the manifest on every database.

## R8. New facts and gotchas (ledger U47–U48, G84–G88)

- U47: who reads `hr.payslip.formula_computed_values`, and that most prefer it over lines once set.
- U48: Python `_()` translations come from the module's `.po` on disk at run time; a restart is
  enough, no upgrade.
- G84: a one-key `formula_computed_values` blanks the Pay run results screen.
- G85: the year-to-date view counts "paid in Payobook" as known when ANY of the person's finished
  payslips this year carries the pay item — payslips with and without it give an understated number
  with no dash.
- G86: the view sums `ABS()` of computed values — a negative taxable base (reliefs larger than pay;
  29 of 500 in December's Corporate run) counts as positive taxable pay.
- G87: the view adds a mid-month advance's payslips to the month's end payslips — the demo's April
  and May gross pay is counted twice (the mid and end payslips both carry GROSS).
- G88: `odoo-bin shell` with `_()` and no language in the context logs a stack-trace warning per
  call ("no translation language detected") — noise, not an error.

## R9. Needs an owner decision

1. **Give the existing demo payslips taxable pay?** Today only demo pay runs made from now on carry
   it, so on payobook.com the Updates year-to-date screen still shows a dash for taxable pay for
   almost everyone, and once a new demo run is finished it shows that month's taxable pay only. To
   fill the whole year, the 21,465 finished demo payslips of 2026 would need their stored
   calculation results filled in from their own figures. Cost: the Pay run results screen and the
   Vietnam payslip print would then read those stored results instead of the payslip lines (same
   amounts for every printed item; the print could start showing a taxable income where it shows
   nothing today). Say yes and it is a separate, checked change; say no and nothing more is needed.
2. **Year-to-date view, three counting faults found on the way (G85–G87)** — in the Updates screen
   (P5), not in this phase's scope: a partly known taxable pay shown as a full number; a negative
   taxable base counted as positive; mid-month advance payslips doubling gross pay. None changes a
   payslip or a tax figure (nothing is mapped into a pay run anywhere), but the screen can show a
   wrong total. Recommend a small fix in Updates; your call.
3. **Rize joining dates** (P5 R12.2) — unchanged advice: 141 of rize's 258 employee records have no
   joining date. With this phase the engine says "not known" instead of 0 for them, so a scheme that
   ever reads the engine's own year-to-date figure will stop and ask for the date.
