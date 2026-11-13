# PRS P1 — the run screen's data (server only)

Read first: `docs/handovers/payrunscreen/PRS_LEDGER.md` (conventions C1–C12,
rulings R1–R3, gotchas). Visual spec: `docs/design/payrun-screen-prototype.html`
(open it in a browser; switch the six moments bottom-left).

## Goal

ONE read-only RPC that gives the new pay run screen everything it shows, in
one round trip, already in plain English: `pb.payruns.get_run_screen(run_id)`.
P2 builds the screen on it. P1 changes NOTHING a user can see.

## Scope

1. `pb.payruns.get_run_screen(run_id)` in `pb_payruns/models/pb_payruns.py`
   (new section after the board readers), returning the payload below.
2. Extract the per-payslip money from the run-totals SQL into one helper both
   readers use: `hr.payslip.run._pb_slip_totals(run_ids)` →
   `{slip_id: {'gross','deductions','net','employer_cost'}}`, and make
   `_compute_pb_totals` sum it (one source of truth, C3). The results of
   `_compute_pb_totals` must not change by a single đồng — prove it with the
   existing `test_run_totals.py` / `test_pay_bands.py` plus a new equality test.
3. Tests: `pb_payruns/tests/test_run_screen.py`.
4. vi_VN entries for every new server string (C9).

## Non-goals (binding)

- No view, JS, SCSS or template change. No deploy in P1 (P2 deploys both).
- No new stored field, no migration, no change to how pay is calculated,
  approved or paid.
- No new Excel exporter, no reminder mechanism, no new approval behaviour.
- Do not touch rize run 1591 or any rize record (R2).

## Verified plumbing — do not re-derive

- Board card builder: `pb.payruns._board_cards(runs, owner=None)` at
  `pb_payruns/models/pb_payruns.py:439`. Returns `{'batches': [card…],
  'stage_counts', 'may_write'}`. A card already carries: `id name state symbol
  period month_label employees net gross deductions employer_cost balance_ok
  balance_gap unsourced checks ready close_weeks credit_note next_action can_act
  can_reject awaiting_me approval{workflow,step,with,blocked,step_index,
  step_total,steps[{key,title,status,with,decided_by,decided_on}],submitted_on,
  closed_on,request_id} return_note return_by return_on reject_note reject_by
  prepared_by delivery history division_label currency currency_name may_write`.
  **Reuse it: `run_card = self._board_cards(run)['batches'][0]`** — never
  rebuild those facts.
- `next_action` (`pb_payruns.py:491-495`): `'submit'` (draft, may write),
  `'decide'` (pending, waiting on me), `''` otherwise. The board's client maps
  `submit → action_approval_submit`, `decide` → open the approval,
  `paydeliver → hr.payslip.run.action_pb_pay_deliver` (payruns.js:48, 583,
  1066). The screen's primary button must agree with the board for the same
  run — derive it from the card, then add the two cases the board does not
  need (no payslips → make; done and unpaid → pay & deliver).
- History sentences: `_history(run, approval, delivery)` (`pb_payruns.py:750`).
  Checks: `_run_checks(...)` (`pb_payruns.py:1102`). Helpers `_person`,
  `_short_name`, `_money_words(amount, symbol)`, `_fmt_date`, `_safe(fn,
  default=)` exist in the same file.
- Run totals SQL: `hr.payslip.run._compute_pb_totals`
  (`pb_payruns/models/hr_payslip_run.py:382`); it already groups by
  `(run, slip, bucket)` — the per-slip numbers are there, only summed away.
  Unsourced condition per slip is the SQL at lines ~424-436
  (`pb_sourced_inputs = 0 AND calculation_method = 'formula' AND
  formula_input_sources IS NOT NULL AND <> ''`).
- Currency: `run.pb_currency_id` (stored). Scheme: `run.pb_formula_config_id`
  (`hr.formula.config`, `name` is a plain char).
- Approval route for a DRAFT (who would sign it off): exactly what
  `biz.approval.engine.submit` does (`biz_approval_workflow/models/engine.py:842`)
  minus the writes: `ctx = run._approval_context()`;
  `process = run._approval_process()`;
  `binding, version, trace, error = engine._resolve_binding(company, process,
  ctx.get('scope_keys'), ctx.get('kind_key'))`; then
  `engine.preview(version, ctx)` (`engine.py:213`, read-only, returns
  `{'steps':[{key,title,kind,included,reason,people[…],issue,due_at}],
  'issues':[…]}`). `preview` calls `_require_config()` (approval-setup rights,
  `engine.py:44`) — call it on `engine.sudo()` AFTER `run.check_access('read')`;
  it writes nothing. For a PENDING run use the card's `approval.steps` (live
  seats), not the preview.
- Payslip quick look data already exists: `hr.payslip.pb_statement_json`
  (`pb_payslip/models/hr_payslip.py:31`, built by `_pb_build_statement()`).
  pb_payruns does NOT depend on pb_payslip — P2 reads it softly; P1 only returns
  a flag `statement_available` = `'pb_statement_json' in env['hr.payslip']._fields`.
- Employee team / job: `hr.employee.department_id` and `job_title`/`job_id`
  are related fields on Odoo 19 (they live on `hr_version`; raw SQL on
  `hr_employee.department_id` FAILS) — read them through the ORM.
- Make payslips door: `om_hr_payroll.action_hr_payslip_by_employees`
  (`om_hr_payroll/wizard/hr_payroll_payslips_by_employees_views.xml:30`);
  check `pb_payruns/tests/test_generate_payslips_dialog.py` for how pb_payruns
  wraps it and return that door.

## Payload (exact keys; every sentence already translated)

```
{
  'run':        <run_card from _board_cards>,
  'header': {
     'title': run.name,
     'work_dates': "1 – 30 Sep 2026",        # one month: "1 – 30 Sep 2026";
                                              # spanning: "16 Sep – 15 Oct 2026"
     'scheme': scheme name or '',
     'people': int,                           # non-cancelled payslips
     'currency_name': 'VND', 'symbol': '₫', 'decimals': 0,
     'status': {'key': draft|sent_back|pending|done|rejected, 'label': …},
  },
  'date_mismatch': None | {'text': "The name says October 2026, but the dates
                    are 1 – 30 Sep 2026. Check the dates before sending it."},
                   # only when run.name contains an English month name + year
                   # (also match Vietnamese "Tháng 10/2026" / "tháng 10 năm 2026")
                   # that differs from the month holding most of the date range
  'journey': [ {'key': 'prepare'|'check'|'approve'|'pay'|'deliver',
                'state': 'done'|'now'|'warn'|'later',
                'label': …, 'sub': …} ×5 ],   # mock-up journey() is the spec
  'primary': {'kind': 'make'|'submit'|'resubmit'|'decide'|'approvals'|
                      'paydeliver'|'none',
              'label': …, 'method': str|None, 'action': xmlid|None,
              'warn': int,                     # open rose checks (badge)
              'confirm': {'title','body','ok','cancel'} | None},
  'money': {'net','gross','deductions','employer_cost','total_cost',
            'sentence': "63 people take home ₫1.62 billion. With the
             company's own contributions, this run costs ₫2.16 billion in all."},
  'compare': None | {'run_id','label': "August 2026",'net','people',
             'change_pct', 'sentence': "2.4% more take-home than August 2026
             (61 people then)"},
             # previous = latest non-cancelled run, same pb_formula_config_id,
             # same pb_division, date_end < this date_start; same currency only
  'compare_none': "This is the first run on this scheme, so there is nothing to
                   compare with yet." | None,
  'checks': {'verdict': 'ok'|'bad'|'wait'|'done', 'title','sub',
             'items': [{'key': 'data'|'balance'|'calculated'|'route',
                        'ok': bool, 'title','detail',
                        'door': None|{'kind': 'flagged'|'atlas'|'approvals_setup'|
                                      'make','label'}}]},
             # the four rows of the mock-up, in that order; rose rows reuse
             # _run_checks' wording where it exists
  'route': {'mode': 'preview'|'live'|'none',
            'seats': [{'name','initials','title','status':
                       'done'|'now'|'later','when'}],
            'note': …, 'error': … | None},
  'delivery': run_card['delivery'] plus 'steps': [{'key','state','label','sub'}]
              # approved → bank file → paid → payslips sent → journals
  'people': {'rows': [{'slip_id','employee_id','name','initials','job','team',
                       'gross','deductions','net','employer_cost',
                       'flag': {'kind': 'rose'|'amber'|'p'|'ok'|'muted',
                                'text'}}],
             'teams': [{'name','count','net'}],          # sorted by count desc
             'counts': {'all','flagged','changed'},
             'changed_available': bool,
             'capped': bool, 'total': int},              # cap rows at 2000
  'settings_editable': bool,                             # draft + may write
  'actions': {'downloads': [ … ], 'more': [ … ]},
             # each {'key','label','hint','method'|'action','danger':bool,
             #       'confirm': {'title','body','ok','cancel'}|None}
             # ONLY what applies to this state and this user may do; map from
             # the existing header buttons (ledger table): Excel
             # (action_download_payslip_xlsx), Payroll report
             # (action_open_payroll_report, only if method exists), Payslips PDF
             # (action_pb_print_payslips), Where the numbers come from
             # (action_open_source_atlas, only if method exists + slips),
             # What changed (action_input_changes, only if exists),
             # Recalculate everyone (action_recompute_formula_lines_batch,
             # draft), Split into review groups (action_split_review_groups,
             # draft + slips), Delete draft payslips
             # (action_pb_delete_draft_payslips, draft + slips, danger),
             # Reject (action_pb_ask_reject, draft|pending + can_reject, danger),
             # Set back to draft (draft_payslip_run, done, only if allowed),
             # Email payslips (action_send_email_all, done).
             # Confirm texts = the mock-up DLG texts / the existing XML confirm=.
  'bulk': {'recalc': bool, 'pdf': bool, 'delete': bool},  # what a selection
             # of payslips can do; P1 adds `hr.payslip.run.action_pb_slips(
             # verb, slip_ids)` ONLY IF an existing per-slip method already does
             # the work (compute_sheet / the print report / unlink of drafts);
             # it must refuse slips not on this run and non-draft deletes.
  'statement_available': bool,
}
```

Flags per person (first match wins): no data this period (rose) · not
calculated yet — no lines (rose) · cancelled (muted) · new since <prev month>
(p) · take-home up/down ≥ 10% vs <prev month> (p, "+12% vs August") ·
otherwise ok ("Calculated" / "Approved" when done). `flagged` counts rose +
amber; `changed` counts the two p kinds.

Access: `run.check_access('read')`; every money and name read is what this user
may already read on the board. A run the user cannot read → AccessError, never
an empty payload. Everything optional (atlas, input changes, statement,
approval preview) sits inside `_safe` so one failure never blanks the screen.

Performance: one SQL pass for per-slip money (the helper), one ORM read for the
employees, no per-row queries. Target < 300 ms for a 200-payslip run on the
live box; report the measured time for rize run 1591 (read-only call).

## Numbered test cases (`test_run_screen.py`)

T1  draft with payslips, all good → primary submit, journey [done,done,now,
    later,later], checks verdict ok with 4 ok items.
T2  draft with no payslips → primary make (door = the generate action),
    journey[0] now, people rows empty, money all 0, no compare.
T3  draft with one unsourced slip and an unbalanced line → verdict bad,
    primary warn = 2 and a confirm, that person's flag rose, flagged = 1.
T4  sent back (pb_return_note set) → status sent_back, primary resubmit,
    journey check = warn.
T5  pending → route mode live, seats from the card's approval steps;
    primary decide for the approver, approvals (view only) for the preparer.
T6  done and unpaid → primary paydeliver, delivery steps first = done.
T7  previous run on same scheme exists → compare present and per-person
    changed flags; none exists → compare None and compare_none sentence.
T8  name "Payroll · October 2026" with dates 1–30 Sep → date_mismatch text;
    "September 2026" with the same dates → None; a name with no month → None.
T9  VND run: decimals 0 and no ".00" in any sentence; a USD run: decimals 2.
T10 `_pb_slip_totals` sums equal the stored run totals exactly on every run
    the existing fixtures make (C3).
T11 user without read access → AccessError.
T12 actions: a done run offers no Delete/Split/Recalculate; a draft offers no
    Email payslips; missing optional modules' methods are simply absent.
T13 no user-visible string in the payload contains "Odoo" (walk the dict).

Run the full pb_payruns suite (existing tests must stay green) — report counts.
Locally: `/Users/adity/odoo19/runtests.sh pb_payruns` (drops/creates its own
scratch DB; a full install can take up to an hour — run ONE at a time). For a
re-run after a code change, reuse the DB it left behind:
`odoo-bin -c odoo-local.conf -d <that db> -u pb_payruns --test-enable
--test-tags /pb_payruns --stop-after-init` (~2 min). A bare `--test-tags`
without a scoping `-u` crashes DB init. Never run tests against the four live
databases.

## Report back (`docs/handovers/payrunscreen/PRS_P1_REPORT.md`)

1. Payload as built (any key renamed or added, and why).
2. Test results: new + whole pb_payruns suite, counts, any failure verbatim.
3. Measured time of `get_run_screen(1591)` on rize (read-only; run it through
   a JSON-RPC or `odoo-bin shell` read with the server untouched — prefer
   JSON-RPC; if you must use shell, see memory payobook-deploy pitfalls).
4. The real payload for rize 1591 summarised (journey, primary, checks
   verdict, route seats, date_mismatch text, team counts) — no salaries.
5. Which `actions` keys exist on rize vs payobook (module presence differs).
6. Self-review against this handover: every non-goal respected? any deviation?
7. New ledger rows added (PRS-Gn).
8. Commit hash (one commit, explicit paths, C10). Do NOT push.
