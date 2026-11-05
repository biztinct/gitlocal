# PDR P1 — fast worksheet, honest red cells, final-tax-month reminder

Read `PDR_LEDGER.md` first. Its §0 rules and §1 plumbing are binding and are
**not** repeated here; do not re-derive them.

## 1. Goal (plain words)

On rize, opening Indonesia "Review pay data" for 113 people takes 49 s and
shows 1,240 red "Needs a value" cells, almost all false. After P1:

* the worksheet opens in **≤ 10 s** (stretch 6 s) and the calculation-preview
  columns fill in behind it;
* blank cells in the 11 columns of ruling R1 are quiet (blank = 0 / No), and
  the one real red cell (BPJS TK covered missing for one person) stays red;
* in a person's final tax month the "Final tax period" cell carries a
  non-blocking reminder.

## 2. Scope / binding non-goals

In scope: §4 S1–S3 (+ S4 only on its trigger), B1–B2, R1-reminder, tests,
deploy to all four DBs, rize data step.

**Non-goals (binding):**
* No Y / N display work — that is P2. Keep showing numbers.
* No formula text changes, no `value_kind` changes, no change to what is
  stored on contracts, no new contract lines.
* No change to the non-application (legacy spreadsheet) resolver.
* No change to what `evaluate()` (the non-readonly path) writes. You may make
  it faster only through the same conversion memo, with identical writes.
* No change to approval / certification semantics: `review()` still needs the
  checklist + note; sealed runs still re-validate.
* No Formula Studio UI for the new rule flag (data only in P1).
* Do not touch BPJS TK covered / BPJS health covered requiredness.
* No Pay run "Compute" redesign. Measure it (report item), don't redesign it.

## 3. Design decisions (binding)

**D1 — blank = 0 for the 10 period columns is a scheme setting, not code.**
These are `period.input.<CODE>` rules; the existing `_optional()` already makes
them optional once `application_zero_allowed = True` — exactly how Bonus / THR
already behave. Do it as data on rize (§5).

**D2 — "No line = No" for zero-default flags is code, narrowly.** In
`_application_employee_inputs`, non-key branch (`application_payroll_source.py`
≈ :595-600): when the legacy resolver did not source the value AND
`rule.is_contract_component` AND `rule.value_kind` is numeric AND
`not (rule.default_value or 0)` AND the rule's parsed `value_labels` contain a
label for 0 (use `parse_value_labels` from `contract_fill_in.py:58` / the
rule helper at :102) → the fact is
`_fact(0, 'resolved', '', sources=[['usual_answer', rule.id]], usual_answer=True)`
with a cell reason the UI can show: **"No line on the contract, so this is No
(the usual answer)."** Set `values[code] = 0` and a provenance entry
`{'src': 'contract_component', 'via': 'usual_answer', 'status': 'resolved'}`.
This is FILLIN D2 made visible to the worksheet; it never creates a line.
A flag whose usual answer is non-zero (TK, Health, Tax mode = 1) is
**unchanged**: a missing line stays red.

**D3 — final-tax-month reminder is a rule flag + a worksheet tone.**
New field `hr.formula.rule.application_final_period_flag` (Boolean, default
False, string "Final tax month reminder", help in plain words). In
`workspace()`, for each row and each cell whose rule has the flag, when the
person is in their final tax month AND the cell value is blank / 0, set
`remind=True`, `tone='remind'`, and reason:
"Final tax month for this person (December / last month of work). Set Final
tax period to Yes and fill in the year-to-date figures." (Use the rule's own
name, not a hard-coded "Final tax period"; pick "December" or "last month of
work" by which test fired.)
Final tax month = `date_to.month == 12` OR the effective contract's `date_end`
falls inside the period OR the person's approved last working day (the
`exit.approved_lwd` fact if the domain sources supply it; else
`hr.employee.departure_date` if the field exists) falls inside the period.
Workspace payload adds `reminders` (cell count) and each person
`reminders` (codes). **Never a blocker, never an issue**, never counted in
"cells need attention". UI (pb_payrun_wizard): a quiet line in the summary band
("2 people are in their final tax month — check Final tax period and the
year-to-date figures." + a "Show them" link), a "Final tax month" option in
"Show employees", and a distinct calm tone on the cell (info tint from the
locked palette, Lucide `calendar-clock` icon, not red, not the amber used for
"Source needs review"). Grey / absent when the count is 0.

**D4 — request memo, one public call long.** Add on `hr.formula.config` a
context-manager helper `_application_memo()` that installs a dict at
`self.env.cr.cache[('pb_hr_payroll_formula.app_memo', self.id)]` if absent and
**removes it on exit only if it installed it** (so nested calls share it).
Wrap these entry points: `PayrollPreparation.workspace`, `save_cells`,
`review`, `_assert_scope`, `preview_rows` (new), `application_preflight`, and
the payslip batch compute entry that calls `_application_employee_inputs` for
many people (find it; wrap at the batch level, not per slip). No module-level
or ormcache caches. The memo must never outlive one public call (tests run
many calls on one cursor — a stale memo is a correctness bug, see T6).

## 4. Speed work

Measure before/after with the werkzeug log line on live (ledger G2), and with a
non-profiled shell / throwaway copy for internals.

**S1 — hoist scheme-level work out of the per-person loop** (all via the D4
memo):
* `_application_settings_stamp()` — once per memo.
* input-rule list, formula-rule list, `by_reference`, the
  `application.mode`-only dependency usage (`:563`), `paid_source_keys`,
  `_application_source_catalogue()` — once per memo.
* `_application_dependency_usage(cells)` — memoise on an exact key: the subset
  of `known` whose refs appear as the left side of an `IF(ref = literal …)` /
  `IF(ref <> literal …)` predicate anywhere in the pay formulas (precompute
  that ref set once). Everything else in `known` cannot change the result.
  Also memoise the `probe.formula_dependencies` lookups by branch text.
* `_application_time_values` — memoise `get_work_hours_count(low, high,
  compute_leaves=…)` per `(calendar.id, tz, low, high, compute_leaves)` for
  the per-day calls (:232-233). The per-leave call (:279) may use the same
  memo. Confirm in code that a call without a resource only depends on the
  calendar (company-wide leaves), else key by resource too.
* `workspace()` `ready`: reuse the `_resolved(True)` result when it was
  already computed in this call.

**S2 — fast, exact formula evaluation.** In both
`formula_sample_data._evaluate_rules_with_dependencies` and the
`hr_payslip_formula` twin (readonly path):
* build `column_map` and the topological order once per call (and once per
  memo across rows);
* convert Excel → Python, run `assert_safe_expression`, and `compile()` once
  per `(excel_formula, column_map)`; evaluate the code object;
* keep the coerced `values` dict up to date incrementally instead of
  re-coercing every value for every formula;
* in `_run_formula`, guard the debug-only loops (:2389-2412) with
  `_logger.isEnabledFor(logging.DEBUG)`.
Add a private fast path (e.g. `_run_compiled`) used by the two evaluators;
`_run_formula`'s public behaviour and signature stay. **Results must be
identical** — same keys, values, types, error dict, pass count (E1).
Target ≤ 0.15 s per person for scheme 7121 (today 8.77 s).

**S3 — previews off the critical path.** `workspace()` no longer evaluates
previews. Result cells come back with `value: None, preview: 'pending'` for
rows without issues (rows with issues: `preview: 'blocked'`, as today's
blank). New RPC `hr.payroll.preparation.preview_rows(revision, employee_ids)`:
`_access()`; ids must belong to the preparation; ≤ 25 ids; stale revision →
`UserError` the JS swallows; returns `{employee_id: {'values': {code: value},
'error': bool}}` computed exactly as today's block (:272-285, optional cells
as 0 / ''). JS: after the grid renders, request previews in batches of 20 one
after another; show a quiet "Working out previews · 40 of 113" next to "Saved
on server" until done; result cells show a soft placeholder until filled;
after a save, re-request only the employees whose cells changed; drop any
response for an older revision. `save_cells` / `review` keep returning
`workspace()` (now cheap).

**S4 — only if, after S1–S3, a fresh profile of the open still shows
`biz_access … __getattribute__` above 15 % of wall time.** Then, and only
then: in `studio_policy.py:247` add a first test against a module-level
`frozenset` of every field name in `RESOURCES` and return
`super().__getattribute__(name)` immediately on a miss. Verify `RESOURCES` is
static (never mutated at runtime); if it is not, skip S4 and report. Behaviour
must be identical; add a test that every `RESOURCES` field still triggers
`_studio_attribute_check`. biz_access 19.0.1.10.4 and its 15 tests must pass.

## 5. rize data step (after the code is live)

SQL on **rize only**, inside one transaction, with backup tables:
1. `CREATE TABLE pb_bak_pdr_zero_20261105 AS SELECT id, config_id, code,
   application_zero_allowed, application_final_period_flag, write_date FROM
   hr_formula_rule WHERE config_id IN (7121, 7116, 7096) AND code IN (<10
   codes from ledger R1 + 'IDFINALTAXPERI'>);`
2. `application_zero_allowed = true, write_date = now() at time zone 'utc'`
   for the 10 period codes in 7121, 7116, 7096.
3. `application_final_period_flag = true, write_date = …` for
   `IDFINALTAXPERI` in the same three schemes.
4. Print before / after counts. Write the exact undo statement into the
   report and `/opt/deploy-notes.md`.
`write_date` must move so `_application_settings_stamp` changes.
Also find what generated these rules (`git log -S IDFINALTAXPERI`,
`tools/build_indonesia_*`, any rize seed script) and set the same two settings
there so a rebuild keeps them; report what you found.

## 6. Paused WIP in HEAD (ledger G1)

Before deploying `pb_hr_payroll_formula`, read
`docs/handovers/orgchart/IMPORT_GENDER_FIX_REPORT.md` and the latest
`IMPORT-GENDER` lines in `/opt/deploy-notes.md`.
* If that work has since been deployed or abandoned by its session, follow
  what is there.
* If still paused: run `tests/test_import_gender_marital.py` together with
  your own tests on the throwaway DB. **Green** → ship it with P1 and write one
  line in deploy notes and your report ("503279518 IMPORT-GENDER shipped with
  PDR P1, its tests green"). **Red** → do not deploy `pb_hr_payroll_formula`;
  stop and report.
Bump `pb_hr_payroll_formula` to **19.0.1.164.0** and `pb_payrun_wizard` to
**19.0.1.42.0** (and biz_access 19.0.1.10.4 only if S4 shipped).

## 7. Tests

Unit (in `pb_hr_payroll_formula/tests/test_payroll_preparation.py` /
`test_application_payroll_source.py`, `pb_payrun_wizard/tests` where it fits),
run on a throwaway copy DB (pg_dump of p0clone, jobs and logins off, scratch
addons dir, ports 8193/8192 — as the other sessions' deploy-note lines do):

* **T1** `period.input` rule with `application_zero_allowed` and blank → not an
  issue, `optional`, counted in `optional`, value 0 in preview values.
* **T2** contract flag, default 0, labels `0=No;1=Yes`, no line → resolved 0,
  `usual_answer` evidence, the reason text above, not an issue.
* **T3** same with default 1 → still missing and an issue.
* **T4** default 0 but no value labels → unchanged (still missing / issue).
* **T5** reminder: December period → `remind` on a flagged blank cell; flagged
  cell = 1 → no reminder; October with contract `date_end` inside → reminder
  ("last month of work"); plain October → none; `review()` succeeds with
  reminders present; `issues` count excludes them.
* **T6** memo freshness: on one cursor, `workspace()`, then change a rule's
  `is_required` / a contract line, then `workspace()` again → sees the change.
* **T7** evaluator equivalence on a synthetic scheme with nested IF, IFERROR,
  quoted text with commas, forward references, a division by zero and a text
  input: old per-rule `_run_formula` loop vs fast path → identical results and
  identical `errors`.
* **T8** `preview_rows`: other user → AccessError; id outside the prep →
  refused; 26 ids → refused; stale revision → UserError; values equal the old
  in-workspace preview for the same row.
* **T9** `save_cells` returns a workspace without computing previews (assert
  the evaluator is not called).
* **T10** two people on one calendar → per-day `get_work_hours_count` called
  once per day per `compute_leaves` value.
* **T11** after `review()`, the 10 optional period cells are `zero_confirmed`
  in the signed preview (like Bonus), and `_assert_scope` passes.
* Full existing suites of `pb_hr_payroll_formula`, `pb_payrun_wizard`,
  `pb_formula_studio` (it calls the evaluator in 6 places) green — list any
  failure that also fails on HEAD^ as pre-existing.

Exactness on real data (rolled-back shell or the throwaway rize copy — never a
write on rize):
* **E1** for all 113 people of prep #19 (blank → 0 as the worksheet does): old
  evaluator (copy the old function into the script) vs new → identical dicts.
* **E2** old vs new `workspace()` JSON for prep #19: identical except the 11
  columns' `issue/optional/tone/reason`, reminder fields, and preview values
  now pending. Print the diff summary.
* **E3** the `hr_payslip_formula` twin: old vs new for 10 people → identical.

Browser (Chrome MCP, after deploy, as the owner's session on
`rize.payobook.com` — read-only, ledger G4):
* **B1** Open Indonesia "Review pay data" for Oct 2026: time it; grid ≤ 10 s.
* **B2** Header shows about 1 cell needing attention (BPJS TK covered), not
  1,240; "Next issue" lands on it.
* **B3** Employer reimburses cells read 0 with the "No line on the contract…"
  reason in the side panel; Final tax period etc. are quiet blanks.
* **B4** Preview columns fill in progressively; the progress text disappears
  at the end; console clean.
* **B5** On a December period of a throwaway copy (or by pointing the shell at
  a person whose contract ends in October), the reminder line, the filter
  option and the calm cell tone render; screenshot.
* **B6** Vietnam 7118 worksheet still opens and looks the same apart from
  speed (no regressions for the scheme that has no flags).

## 8. Deploy and verify

Tiered deploy rule: this is **risky** (engine + schema) → full ritual.
1. Commit per feature (S-work, B-rules, reminder, JS), explicit staging, push
   `19.1`.
2. `/opt/deploy-notes.md` START line; announce in it that the payroll engine
   restarts on all four DBs.
3. Stage from `git archive HEAD`, `tools/filter_deploy.sh`, `-u
   pb_hr_payroll_formula,pb_payrun_wizard` (+ biz_access if S4) on
   `payobook, payobook_template, p0clone, rize`; EXIT=0 ×4; asset purge +
   `web.assets.version` bump; restart; registry loaded; sites 200.
4. Verify hash (live tree == staged tree) and `latest_version` ×4.
5. §5 data step on rize. DONE line in deploy notes with undo pointers.
6. B1–B6.

## 9. Report back (`PDR_P1_REPORT.md`, same folder)

1. Before / after: open time (werkzeug line), query count, preview total time,
   one cell save time, evaluator s/person; fresh profile top 15 of the open.
2. Whether S4 ran and why.
3. E1–E3 results; T1–T11 + suite results with counts; pre-existing failures.
4. Red-cell count on prep #19 after deploy, by column.
5. Indonesia Compute time for the October test run (or 20 people on the copy)
   before / after — measured only.
6. What generated the rize rules and what you changed there.
7. IMPORT-GENDER decision taken (§6).
8. Deviations from this handover, with reasons; new gotchas (also append them
   to `PDR_LEDGER.md` §2).
9. Screenshots (B1–B6) saved under `docs/handovers/paydatareview/p1_shots/`.
10. Commits, versions, deploy-notes lines, undo statements.
