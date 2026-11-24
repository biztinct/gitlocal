"""Cancel only the exact pending duplicate of an already-applied bank import.

Uses the normal Records Desk cancellation as Ash, retaining both proposals and
the approval audit. Default rolls back. No bank, salary or employee writes.
"""
import json
import os
from pathlib import Path

assert env.cr.dbname == 'sudima'
e = env(user=2500, context=dict(env.context, allowed_company_ids=[1], lang='en_US',
                              mail_notify_force_send=False))
assert e.user.login == 'ash@biztinct.com'
old = e['pb.records.apply'].sudo().browse(185)
done = e['pb.records.apply'].sudo().browse(189)
assert old.name == 'RD00185' and done.name == 'RD00189'
assert old.company_id == done.company_id == e.company
assert old.touches_bank and done.applied and done.state == 'applied'
for field in ('plan_json', 'changes_json', 'config_id', 'source', 'lane'):
    assert old[field] == done[field], ('Not an exact duplicate', field)


def digest(table):
    e.cr.execute('SELECT md5(coalesce(string_agg(md5(to_jsonb(t)::text),chr(10) ORDER BY id),\'\')) FROM ' + table + ' t')
    return e.cr.fetchone()[0]


tables = ['hr_employee', 'hr_contract', 'hr_payslip', 'hr_payslip_line', 'res_partner_bank',
          'hr_formula_config', 'hr_formula_rule', 'res_users', 'pb_bank_change_request']
before = {t: digest(t) for t in tables}
e.cr.execute("SELECT pg_advisory_xact_lock(hashtext('sudima-checked-banks-20261124'))")
if old.state == 'cancelled':
    result = {'already_cancelled': True}
else:
    assert old.state == 'pending' and not old.applied and old.with_env(e)._may_cancel()
    result = e['pb.records.desk'].cancel_apply(old.id)
    assert result.get('ok') and result.get('cancelled'), result
e.flush_all()
assert old.state == 'cancelled' and not old.applied
assert {t: digest(t) for t in tables} == before
waiting = e['pb.payment.list']._pb_waiting_changes(e['hr.employee'].sudo().browse(6065))
assert not waiting.get(6065)
commit = os.getenv('SUDIMA_BANK_APPLY') == '1'
if commit:
    e.cr.commit()
else:
    e.cr.rollback()
receipt = {'committed': commit, 'cancelled': 'RD00185', 'already_applied_copy': 'RD00189',
           'actor': e.user.login, 'result': result, 'protected': before, 'waiting_bank_warning_cleared': True}
path = Path('/odoo/archives/sudima-bank-check-20261124') / ('cancel-applied.json' if commit else 'cancel-rehearsal.json')
path.write_text(json.dumps(receipt, indent=2)); path.chmod(0o600)
print('OBSOLETE_PROPOSAL_RESULT', json.dumps({k: v for k, v in receipt.items() if k != 'protected'}))
