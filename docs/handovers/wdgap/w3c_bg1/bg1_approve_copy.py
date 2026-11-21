# WDGAP W3-C BG1 rehearsal — COPY ONLY. Approve the batch as one of the
# site's bank approvers (the "Approve all in this file" button's own call) and
# verify the result. Caller prepends APPROVER = <user id>.
import json
from collections import Counter

DB = env.cr.dbname  # noqa: F821
assert DB.startswith('bg1w3c_'), 'copies only: %s' % DB
KEY = 'bank-gap-copy,%s,2026-11-17' % DB
cr = env.cr  # noqa: F821
lists = json.load(open('/tmp/bg1w3c/%s-run-lists.json' % DB))
inc_ids = [r['employee_id'] for r in lists['included']]
exc_ids = [r['employee_id'] for r in lists['excluded']]
Emp = env['hr.employee'].sudo().with_context(active_test=False)  # noqa: F821
Req = env['pb.bank.change.request'].sudo()  # noqa: F821
user = env['res.users'].sudo().browse(APPROVER)  # noqa: F821


def digits(t):
    return ''.join(c for c in str(t or '') if c.isdigit())


def bank_file_view():
    """For every finished run touching an included person: who the bank file
    would leave out and why (the wizard's own row check), per run."""
    Wiz = env['vietnam.bank.export.wizard'].sudo()  # noqa: F821
    Reg = env['pb.bank.registry']  # noqa: F821
    slips = env['hr.payslip'].sudo().search([('state', '=', 'done'),  # noqa: F821
                                             ('employee_id', 'in', inc_ids)])
    runs = slips.mapped('payslip_run_id').sorted('id')[-3:]
    out = {}
    for run in runs:
        wiz = Wiz.create({'payslip_run_id': run.id})
        reasons = Counter()
        valid = 0
        inc_valid = 0
        inc_total = 0
        for idx, slip in enumerate(wiz._resolve_slips(), start=1):
            _src, why, _net = wiz._row_sources(slip, idx, Reg)
            is_inc = slip.employee_id.id in inc_ids
            inc_total += is_inc
            if why:
                for w in why:
                    reasons[w] += 1
            else:
                valid += 1
                inc_valid += is_inc
        out[run.name] = {'run_id': run.id, 'valid_rows': valid,
                         'left_out_reasons': dict(reasons),
                         'included_people_in_run': inc_total,
                         'included_people_paid_by_file': inc_valid}
    return out


before_file = bank_file_view()
pending = Req.search_count([('pb_import_key', '=', KEY), ('state', 'in', ('hr_review', 'finance_review'))])
groups = Req.with_user(user)._pb_import_groups()
res = env['pb.bank.ocr'].with_user(user).approve_import(KEY)  # noqa: F821
env.invalidate_all()  # noqa: F821
after_states = Counter(Req.search([('pb_import_key', '=', KEY)]).mapped('state'))

# (a) both stores agree for every included person
agree = disagree = 0
bad = []
for e in Emp.browse(inc_ids):
    a = e.bank_account_ids[:1]
    same = (digits(e.vietnam_bank_account_number) == digits(a.acc_number)
            and (e.vietnam_bank_name or '') == (a.bank_id.name or '')
            and (e.vietnam_bank_account_name or '') == (a.acc_holder_name or '')
            and len(e.bank_account_ids) == 1)
    if same:
        agree += 1
    else:
        disagree += 1
        bad.append(e.id)
# (b) the read-only check now lists only the excluded people
check = Emp.pb_bank_store_check()
left = {r['employee_id'] for r in check['rows']}
after_file = bank_file_view()
hist = env['pb.employee.bank.history'].sudo().search_count([  # noqa: F821
    ('employee_id', 'in', inc_ids)])
summary = {
    'db': DB, 'approver': user.login, 'groups_seen_by_approver': groups,
    'waiting_before': pending, 'approve_all_answer': res,
    'states_after': dict(after_states),
    'a_stores_agree': agree, 'a_disagree': disagree, 'a_bad_ids': bad[:20],
    'b_check_counts_after': check['counts'],
    'b_rows_left_equal_excluded': left == set(exc_ids),
    'b_rows_left': len(left), 'b_excluded': len(exc_ids),
    'b_extra_left': sorted(left - set(exc_ids))[:20],
    'history_rows_for_included': hist,
    'd_bank_file_before': before_file, 'd_bank_file_after': after_file,
}
print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
with open('/tmp/bg1w3c/%s-approve-summary.json' % DB, 'w') as fh:
    json.dump(summary, fh, indent=1, ensure_ascii=False, default=str)
cr.commit()
print('COMMITTED (copy)')
