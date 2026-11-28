"""Approve the owner-requested Rize bank-file setup batch via its normal route.

Run in Odoo shell. RIZE_BANK_SETUP_DIR contains private live.json and a full
backup. Default rolls back; RIZE_BANK_SETUP_APPLY=1 commits. No approvals are
impersonated: Ash Sohani's existing account must hold a valid, independent seat.
Only the already-reviewed blank-to-existing-account batch is eligible.
"""
import json
import os
from pathlib import Path

assert env.cr.dbname == 'rize'
root = Path(os.environ['RIZE_BANK_SETUP_DIR'])
apply = os.getenv('RIZE_BANK_SETUP_APPLY') == '1'
e = env(user=2, context=dict(env.context, allowed_company_ids=[1]))
assert e.user.name == 'Ash Sohani' and not e.su
key = 'bank-gap-copy,rize,2026-11-17'
expected = json.loads((root / 'live.json').read_text())
expected = {r['id']: r for r in expected['rows']}
requests = e['pb.bank.change.request'].search([('pb_import_key', '=', key)])
assert set(requests.ids) == set(expected) and requests
assert not (root / 'applied.json').exists(), 'Already applied; inspect the receipt.'
if apply:
    assert (root / 'rize-before.dump').stat().st_size > 1000000


def digest(table, where='TRUE', omit=()):
    expression = 'to_jsonb(t)'
    for name in omit:
        expression += " - '%s'" % name
    e.cr.execute("SELECT md5(coalesce(string_agg(md5((" + expression +
                 ")::text),chr(10) ORDER BY id),'')) FROM " + table +
                 ' t WHERE ' + where)
    return e.cr.fetchone()[0]


fields = ['vietnam_bank_name', 'vietnam_bank_branch',
          'vietnam_bank_account_name', 'vietnam_bank_account_number']
employees = requests.mapped('employee_id')
employee_ids = ','.join(map(str, employees.ids))
request_ids = ','.join(map(str, requests.ids))
approval_ids = []
for request in requests:
    saved = expected[request.id]
    person = request.employee_id
    account = person.bank_account_ids.with_context(active_test=False)
    proposal = [request.x_bank_name, request.x_bank_branch,
                request.x_account_name, request.x_account_number]
    assert proposal == saved['proposed'], (request.id, 'Proposal changed')
    assert request.state in ('hr_review', 'finance_review')
    assert person.active and person.company_id.id == 1
    assert not any(person[f] for f in fields), (request.id, 'No longer blank')
    assert not any([request.cur_bank_name, request.cur_bank_branch,
                    request.cur_account_name, request.cur_account_number])
    assert len(account) == 1 and account.active and account.partner_id == person.work_contact_id
    assert account.acc_number == request.x_account_number
    assert account.acc_holder_name == request.x_account_name
    assert account.bank_id.name == request.x_bank_name
    assert not request.x_bank_branch
    bank = e['pb.bank.registry'].match(request.x_bank_name)
    assert bank and request.v_format_ok and request.name_match_band == 'green'
    assert not request.duplicate_ids and not request._find_duplicates(bank)
    assert e.user not in request._pb_never_decide()
    approval = request._chain_open_request()
    assert approval.id == saved['approval_id'] and approval.lock_revision == saved['revision']
    assert approval.state == 'pending' and approval.submitter_uid != e.user
    step = approval.step_ids.filtered(lambda s: s.status == 'active')
    assert step.seat_ids.filtered(lambda s: s.status == 'open' and s.acting_user_id == e.user)
    approval_ids.append(approval.id)

protected = ['hr_contract', 'hr_payslip', 'hr_payslip_line', 'hr_payslip_run',
             'hr_formula_config', 'hr_formula_rule', 'pb_payroll_month_inputs',
             'res_partner_bank', 'res_bank']
before = {t: digest(t) for t in protected}
other_employees = digest('hr_employee', 'id NOT IN (' + employee_ids + ')')
other_requests = digest('pb_bank_change_request', 'id NOT IN (' + request_ids + ')')
nonbank_employee_values = digest('hr_employee', 'TRUE', fields + ['write_uid', 'write_date'])
history_before = e['pb.employee.bank.history'].sudo().search_count([('request_id', 'in', requests.ids)])

# This is the same action as Compliance > Bank > Approve all in this file.
# The engine still checks the approver, independence, request facts and locks.
result = e['pb.bank.ocr'].approve_import(key)
assert result['approved'] == len(requests) and not any(result[k] for k in ('yours', 'others', 'failed')), result
e.flush_all()
requests.invalidate_recordset()
employees.invalidate_recordset()
for request in requests:
    assert request.state == 'approved', request.id
    proposal = expected[request.id]['proposed']
    assert [(request.employee_id[f] or '') for f in fields] == [(x or '') for x in proposal]
    approval = e['biz.approval.request'].browse(expected[request.id]['approval_id'])
    decisions = approval.decision_ids.filtered(lambda d: d.action == 'approve' and d.user_id == e.user)
    assert len(decisions) == 1 and approval.state in ('approved', 'applied')
assert e['pb.employee.bank.history'].sudo().search_count([('request_id', 'in', requests.ids)]) == history_before + len(requests)
assert {t: digest(t) for t in protected} == before, 'Protected records changed'
assert digest('hr_employee', 'id NOT IN (' + employee_ids + ')') == other_employees
assert digest('pb_bank_change_request', 'id NOT IN (' + request_ids + ')') == other_requests
assert digest('hr_employee', 'TRUE', fields + ['write_uid', 'write_date']) == nonbank_employee_values
receipt = {'database': 'rize', 'committed': apply, 'batch': key, 'count': len(requests),
           'approver_id': e.uid, 'approver': e.user.name, 'result': result,
           'bank_request_ids': requests.ids, 'approval_ids': approval_ids,
           'employee_ids': employees.ids, 'protected_tables': before,
           'existing_accounts_unchanged': True, 'nonbank_values_unchanged': True,
           'other_requests_unchanged': True}
if apply:
    e.cr.commit()
else:
    e.cr.rollback()
dest = root / ('applied.json' if apply else 'rehearsal.json')
dest.write_text(json.dumps(receipt, indent=2)); dest.chmod(0o600)
print('BANK_SETUP_RESULT', json.dumps({k:v for k,v in receipt.items() if k not in (
    'bank_request_ids', 'approval_ids', 'employee_ids', 'protected_tables')}))
