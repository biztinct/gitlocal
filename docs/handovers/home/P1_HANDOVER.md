# HOME P1 — server data for the new Home (handover for Opus)

Read first: `HOME_PROGRAM.md` (what Home becomes + verified plumbing with file:line), `HOME_LEDGER.md`
(H-R1…R8 + H1…H10), and open `docs/design/home-dashboard-prototype.html` in a browser once so every number you
compute has a place on the screen. CLAUDE.md rules apply (one addons dir; never "Odoo" in a user string).

## Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." For P1 that means: every figure the page
shows is exact, company-scoped, from the one pay band, and the whole payload is one fast call. Score the report
against it.

## Scope (P1)
One new RPC on the existing AbstractModel: `pb.dashboard.get_home_data()` (`@api.model`, no arguments; the browser
never sends a period — the chart carries all 12 months). Keep `get_dashboard_data` untouched (the old template
still calls it until P2 lands). Pure data, no sentences (H-R3). Every section wrapped in `safe()`; every foreign
model through `optional()` (H-R2); runs scoped through payslips (H-R4); never `hr_payslip_line` (H-R1).

### Payload contract (exact keys; `None` where a source is absent)
```
{
 'user': str, 'company': str, 'currency': {'symbol': str, 'position': 'before'|'after'},
 'today': 'YYYY-MM-DD',
 'period': {                       # the CURRENT calendar month (pb.pay.hub when installed; else first..last of today's month, stage None)
   'key': 'YYYY-MM', 'date_start': 'YYYY-MM-DD', 'date_end': 'YYYY-MM-DD',
   'stage': 1..5 | None, 'total': 5, 'run_count': int, 'delivered_count': int,
   'cutoff': 'YYYY-MM-DD' | None, 'payday': 'YYYY-MM-DD' | None,          # pb.payroll.calendar row for key + company (optional)
   'prepared': int,                # payslips (state != cancel) in the period's runs
   'expected': int,                # employees with an open contract (hr.contract state='open', distinct employee)
   'net_so_far': float | None,     # sum pb_total_net of the period's runs (H4)
   'awaiting_me': int,             # len(hr.payslip.run._pb_runs_awaiting(uid)) ∩ period runs, if the method exists
   'awaiting_run': {'id','name','division','people','net','submitted_by','initials'} | None,   # first awaiting run
   'now_run': {'id','name','division','done','total'} | None,              # draft run with the newest write_date and ≥1 slip
 },
 'needs_you': [ {'key': str, 'n': int} ],   # ONLY n > 0, in this order of keys:
   # runs_to_approve (awaiting_me) · leave_to_approve · other_to_approve · settlements_to_check · renewals_to_start · writeups_overdue
 'approvals_total': int | None,     # pb.approval.inbox counts.mine (optional)
 'months': [ 12 × {                 # calendar months ending at period.key, oldest first
   'key','year_mark': bool,         # year_mark True on the first entry and on every January (the axis prints the year there)
   'people': int, 'net','gross','ded','er','total','avg': float|None,     # sums of stored run totals; avg = net/people
   'runs': int, 'balance_ok': bool|None, 'done': bool,                    # done = every run in the month is state 'done'
   'latest': bool, 'inprogress': bool,                                    # latest = newest done month before the period; inprogress = key == period.key
   'approved': 'YYYY-MM-DD'|None, 'delivered': 'YYYY-MM-DD'|None,         # max biz.approval.request.closed_at for those runs (optional) / max done delivery batch date (optional)
   'note': 'tet' | None,                                                  # month that contains Tết (lunar new year) — read pb.holidays if it exposes it, else None (P2 shows nothing)
 } ],
 'runs': [ {                        # the period's runs, newest date_end first
   'id','name','division': str, 'initials': str (2–3 letters from the division or name),
   'state': 'draft'|'approval_pending'|'done'|'cancel', 'people': int, 'slips': int, 'done': int (slips in state done),
   'net': float|None, 'balance_ok': bool|None, 'unsourced': int|None, 'awaiting_me': bool, 'no_bank': int,
 } ],                               # no_bank = employees in the run's payslips with no bank account (hr.employee.bank_account_id False)
 'steps': [ 5 × {'key': 'setup'|'prepare'|'approve'|'pay'|'deliver', 'state': 'done'|'now'|'wait'|'todo',
            'when': 'YYYY-MM-DD'|None, 'n': int|None, 'who': {'name','initials'}|None, 'run': str|None} ],
 'upcoming': [ ≤6 × {'kind': 'cutoff'|'payday'|'contracts_end'|'holiday'|'interviews', 'date': 'YYYY-MM-DD',
               'n': int|None, 'extra': dict} ],   # today or later, ascending; extra = {'renewals': 3, 'renewed': 4} / {'name': 'New Year's Day'} / {'banks': 4}
 'people': {'headcount','active_contracts','no_contract','joined','joined_prev','leaving','settlements_to_check': int,
            'out_today': int|None, 'out_breakdown': [{'label','n'}] (≤3, by leave type), 'week': [7 × {'date','n','weekend': bool}] | None,
            'leave_pending': int|None},
 'hiring': None | {'open','candidates','interviews_week','writeups_overdue','over_budget','offers_waiting','referrals': int|None},
 'learn': None | {'key','title','minutes': int|None,'reason': str,'streak_days': int},
 'schemes': {'count','active','components','tests_total': int, 'tests_passed': int|None, 'last_run': 'YYYY-MM-DD HH:MM'|None, 'failing_configs': int},
 'activation': <exactly what get_dashboard_data returns today>,
 'timing_ms': {'period': int, 'needs_you': int, 'months': int, 'runs': int, 'people': int, 'hiring': int, 'learn': int, 'schemes': int, 'total': int},
}
```

### How each section is built (sources are verified — program doc; do not search for alternatives)
- **period**: `optional('pb.pay.hub', lambda: env['pb.pay.hub'].get_period_state())` gives stage/run_count/
  delivered_count/date_start/date_end; without it, first..last of today. Calendar row: `optional('pb.payroll.calendar')`,
  domain `[('month','=',date_start), ('company_id','in',[company.id, False])]` → `cutoff_date`, `pay_date`.
  Period runs = `hr.payslip.run` overlapping the month, `state != 'cancel'`, scoped by payslips (H3). `prepared` =
  `hr.payslip` search_count on those runs. `expected` = `hr.contract` read_group distinct employee_id, state open,
  company in companies. `awaiting_me` via `hasattr(Run, '_pb_runs_awaiting')`. `submitted_by` = the pending
  `biz.approval.request` (res_model `hr.payslip.run`, res_id) `create_uid.name` through `optional('biz.approval.request')`,
  fallback `run.write_uid.name`. `now_run` = draft period run with ≥1 slip, newest `write_date`.
- **needs_you**: `runs_to_approve` = `period.awaiting_me`. With `optional('pb.approval.inbox')`: `counts = list_requests(tab='mine')`
  → `approvals_total = counts['counts']['mine']`; `leave_to_approve` = cards whose `area`/`process` is the leave one
  (read `cards[i]['area']` values on the clone and pick the leave key; say which in the report); `other_to_approve`
  = mine − runs − leave (≥0). Without the inbox: `leave_to_approve` = `hr.leave` state in (confirm, validate1) count
  via `optional('hr.leave')`. `settlements_to_check`: `optional('hr.full.final.settlement')` — look at its state
  selection on the clone; count the "to check / ready to check" state for the companies (one search_count); if no
  such state exists, 0. `renewals_to_start` = open contracts ending within 30 days whose employee has NO contract with
  `date_start > this.date_end` (one search + one read_group on hr.contract). `writeups_overdue` = `optional('pb.hiring.interview')`
  count with `feedback_late` True (if not stored: search the last 42 days, bounded 500, filter in Python).
- **months**: build the 12 keys in Python; search `hr.payslip.run` with `date_end` in [first key's 1st, period.date_end],
  `state != 'cancel'`, scope by payslips (one SQL), group in Python by `date_end` month. Money only when
  `'pb_total_net' in Run._fields` (H4): net/gross/ded/er = sums of `pb_total_net/_gross/_deductions/_employer_cost`,
  total = gross + er, people = sum `pb_employee_count` (fallback: slips count), avg = net/people. `balance_ok` =
  all `pb_balance_ok`. `approved` / `delivered` as in the contract (both optional). `note`: leave `None` unless
  `pb.holidays` exposes the Tết dates cheaply (check `_column`'s source; do not build a lunar calendar).
- **runs**: the period runs with the stored fields; `initials` = first letters of the division label words (max 3)
  or of the run name; `no_bank` = one search_count on `hr.employee` with `bank_account_id = False` and id in the
  run's payslip employee ids (one `read_group` over `hr.payslip` for employee ids per run, ≤ 6 runs).
- **steps**: derived — `setup` done when stage ≥ 2 or any period run exists (`when` = date_start, `n` = joined);
  `prepare` now when stage == 2 (`run` = now_run name, `n` = prepared); `approve` wait when awaiting_me > 0 (`who`
  = submitted_by, `run` = awaiting_run name), now when stage == 3, done when stage ≥ 4; `pay` done when stage ≥ 4
  (`when` = payday, `n` = total no_bank); `deliver` done when delivered_count == run_count > 0 (`when` = payday + 2 days).
- **upcoming**: cutoff (if ≥ today), payday (extra banks = distinct `bank_account_id.bank_id` over expected
  employees — one read_group; drop if > 1 query), contracts_end (date = the earliest `date_end` in the next 30 days;
  `n` = count; extra renewals/renewed from the renewals computation), holiday (`optional('pb.holidays')`
  `next_one()` → its date + name), interviews (`optional('pb.hiring.interview')` next 7 days count; date = first).
  Sort by date, cap 6.
- **people**: headcount = active `hr.employee` in companies; active_contracts = open contracts; no_contract =
  headcount − distinct employees with an open contract; joined = `first_contract_date` in the period month,
  joined_prev = previous month; leaving = open/close contracts with `date_end` in the period month;
  settlements_to_check as above; leave via `optional('hr.leave')`: out_today = validated leaves covering today
  (count + breakdown by `holiday_status_id.name`, top 3), week = 7 counts from ONE search over [today, today+6]
  (the pb_timeoff `_kpis` shape), leave_pending as above. Employees scoped by company.
- **hiring**: `optional('pb.hiring')` and `_can_read()` else `None`; counts from `pb.hiring.requisition` (state
  open), `hr.applicant` on those requisitions (one read_group), interviews next 7 days, writeups_overdue, over_budget
  (a requisition field — check; `None` if there is none), offers_waiting / referrals only if each is ONE query
  (otherwise `None`).
- **learn**: `optional('learn.runtime')`: `next_best()` → key/title/minutes/reason (reason in the user's language),
  `streak()['days']`. `None` when the module is absent or next_best returns `{}`.
- **schemes**: as today's `formula` block (inside `safe()`), company-scoped (`company_id in companies + False`),
  plus `tests_passed` (look at the test-result model's fields on the clone for a pass flag; `None` if none),
  `last_run` = max create_date of test results, `failing_configs` = `validation_status == 'failed'` count.
- **timing_ms**: `time.perf_counter()` around each section; `total` for the whole call. Also `_logger.info`
  one line `home_data %d ms` so Fable can read payobook timings from the server log.

## Binding non-goals
No template/JS changes (P2). No change to `get_dashboard_data`, `_payroll_months`, `_period_kpis`, the activation
checklist or its tests except H5 (test_05 exact-name fix) and the new OPTIONAL_MODELS entries. No new stored fields.
No sudo beyond what a source facade does itself. No sentences in the payload (H-R3). No deploy (Fable deploys).

## Safety rails
- `safe(fn, default)` around every section so one broken source never blanks Home (`pb_dashboard.py:221-226`);
  `sql_safe` (savepoint) around every raw SQL.
- All new SQL is parameterised; run ids go through `tuple(ids)` guards (empty → skip the query).
- Nothing in this RPC may take longer than the sum of its parts on the clone; log and assert (test 11).

## Numbered tests (add `tests/test_home_data.py`; keep `test_activation.py` green)
1. Shape: every top-level key of the contract is present; `months` has 12 entries, oldest first, last key ==
   `period.key`; `year_mark` True on index 0 and every January.
2. Money from the one pay band: seed two runs in last month (payslips + lines through the demo scheme fixtures —
   reuse persistent demo fixtures, memory `demo-payroll-test-fixtures`; else build with the pb_payruns test helpers)
   and assert `months[-2].net == sum(run.pb_total_net)`, same for gross/ded/er, `people == sum(pb_employee_count)`,
   `balance_ok` matches. Skip with a reason if `pb_payruns` is not installed on the clone.
3. Company scope: a run whose payslips belong to another company is absent from `months`, `runs`, `prepared`.
4. Period: `period.stage` equals `pb.pay.hub.get_period_state()['stage']`; a seeded `pb.payroll.calendar` row sets
   `cutoff`/`payday`; `expected` equals the distinct open-contract employees of the companies.
5. In-progress month: `months[-1].inprogress` True, `latest` True only on the newest done month before it, `done`
   True only when every run is done.
6. Needs you: nothing waiting → `[]`; a run submitted on a route where the test user holds the seat (clone a
   pb_payruns approval test fixture; if none is cheap, skip with a reason) → `[{'key':'runs_to_approve','n':1}]`
   first and `period.awaiting_run.id` is that run; a leave in state confirm → `leave_to_approve` appears when
   `hr.leave` is installed.
7. People: seeded joiner this month / leaver this month / employee without a contract → joined, leaving,
   no_contract correct; a validated leave covering today → `out_today == 1` and `week[0].n == 1` (skip if hr.leave absent).
8. Upcoming: ascending dates, none before today, ≤ 6, `cutoff` present when the calendar row's cut-off is ahead.
9. Source rail (AST, extend test_04): every `env['<model>']` read in `get_home_data` and its helpers for a model
   outside the depends sits inside `optional()`; `OPTIONAL_MODELS` extended with every model named above; the new
   code contains no `hr_payslip_line` / `hr.payslip.line` token (absence test, spelled by concatenation like test_06).
10. test_05 narrowed (H5): depends/imports may not contain the exact module names `pb_learn` / `pb_import`
    (word boundary), proven by a negative check that `pb_import_kit` would pass.
11. Timing: on the clone `timing_ms.total < 1500` and every section < 600; the info log line is emitted.
12. Activation: `get_home_data()['activation'] == get_dashboard_data()['activation']`.

## Deliverables
- `pb_dashboard/models/pb_dashboard.py` (+ a new `models/home_data.py` if the file would pass ~900 lines; keep one
  AbstractModel `pb.dashboard` either way), `tests/test_home_data.py`, `tests/test_activation.py` (H5 + models list),
  `__manifest__.py` version `19.0.2.0.0` with a comment line in the existing style.
- Commit per feature (memory `commit-per-feature`), explicit staging, message prefixed `feat(home): P1 …`. Do not push.
- Ledger rows for every gotcha hit (H11+), in `HOME_LEDGER.md`.

## Report back (`P1_REPORT.md`)
Tests 1–12 results with counts; the clone timing table; the leave `area` key you found; which optional sections
returned `None` on the clone and why; every H row added; deviations with reasons; open questions for P2 (payload
fields you would add or drop after building it).

## How to run tests (no local Odoo — the server is the test bench)
- ssh alias `Payobook19v2` (passwordless sudo). **Never** touch `/odoo/odoo-server/addons`, never stop/restart
  `odoo-server`, never use port 8069, never run anything against `payobook`, `rize`, `payobook_template`, `abm`.
- Stage: `ssh Payobook19v2 'sudo rm -rf /tmp/h1stage && mkdir -p /tmp/h1stage'`, then
  `rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude=.DS_Store pb_dashboard Payobook19v2:/tmp/h1stage/`
  and `sudo chown -R odoo:odoo /tmp/h1stage`. The FIRST addons-path entry wins, so the staged copy shadows live.
- Clone DB: reuse `p0clone` (a copy of `payobook_template`, crons + mail servers off). If missing: `pg_dump -Fc
  payobook_template | pg_restore -d h1clone` after `createdb -O odoo h1clone`, then
  `update ir_cron set active=false; update ir_mail_server set active=false;`.
- Run detached: `/tmp/h1_test.sh` = `sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d p0clone
  --addons-path=/tmp/h1stage,/odoo/odoo-server/addons --http-port=8099 -u pb_dashboard --test-enable
  --test-tags /pb_dashboard --stop-after-init --logfile=/tmp/h1test.log; echo EXIT=$? >> /tmp/h1test.log; touch /tmp/h1test.done`,
  launched with `sudo systemd-run --collect --unit=h1-test /bin/bash /tmp/h1_test.sh`; check `free -m` first
  (≥ 600 MB available, poll until it is); poll the sentinel; grep `FAIL:|ERROR: Test|odoo.tests.stats|EXIT=`.
  Pre-existing failures to ignore: the three vi_VN tests in pb_payroll_ai_insights (PA11) — not in `/pb_dashboard`.
- Shell reads for discovery (field names, selection values): `odoo-bin shell -d p0clone --addons-path=…` with
  `--http-port=8099`, never against a live DB.
