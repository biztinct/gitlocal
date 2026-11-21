"""Owner-approved, Sudima-only Records route; existing UI services only.

Run in the Sudima Odoo shell with SUDIMA_REVIEW_DIR. Default rehearses and
rolls back. SUDIMA_RECORDS_APPLY=1 publishes and re-proposes the two imports.
Approval of the replacement proposals is left to the HR Approval Inbox UI.
"""
import copy
import hashlib
import json
import os
from pathlib import Path

assert env.cr.dbname == 'sudima'
root = Path(os.environ['SUDIMA_REVIEW_DIR'])
apply = os.getenv('SUDIMA_RECORDS_APPLY') == '1'
admin = env['res.users'].search([('login', '=', 'ash@biztinct.com')])
hr = env['res.users'].search([('login', '=', 'hr@sudima.local')])
assert len(admin) == len(hr) == 1 and admin.active and hr.active
context = dict(env.context, allowed_company_ids=[1], lang='en_US')
a, h = env(user=admin.id, context=context), env(user=hr.id, context=context)
assert a.company.name == h.company.name == 'Sudima Panels Vietnam'
matrix = a['pb.approval.matrix']
inbox = h['pb.approval.inbox']
workflow = a['biz.approval.workflow'].search([
    ('company_id', '=', 1), ('process_id.key', '=', 'records')])
assert len(workflow) == 1 and workflow.id == 22
assert workflow.published_version_id.revision == 1, 'Review subsequent owner edits before running again.'

def fingerprint(records, fields):
    return hashlib.sha256(json.dumps(records.read(fields), sort_keys=True,
                                    default=str).encode()).hexdigest()

others = a['biz.approval.workflow.version'].search([('workflow_id', '!=', workflow.id)])
other_before = fingerprint(others, ['definition', 'status', 'write_date'])
responsibilities = a['biz.approval.responsibility'].search([])
roles_before = fingerprint(responsibilities, ['user_id', 'backup_user_id', 'write_date'])
protected_models = ('hr.payslip', 'hr.payslip.run', 'hr.attendance', 'hr.formula.scheme.assignment')
protected = {m: fingerprint(a[m].search([]), ['write_date']) for m in protected_models}
before_receipt = (root/'applied.json').read_text()
receipt = json.loads(before_receipt)
old = h['pb.records.apply'].browse([185, 186])
assert old.mapped('name') == ['RD00185', 'RD00186']
assert all(p.state == 'pending' and not p.applied and p.company_id.id == 1
           and p.approval_request_id.state == 'pending' for p in old)

data = matrix.get_workflow(workflow.id)
definition = copy.deepcopy(data['draft']['definition'])
definition['steps'] = [{
    'key': 's1', 'kind': 'approve', 'title': 'Sudima HR approval',
    'who': {'mode': 'people', 'user_ids': [hr.id]},
    'min_amount': 0, 'condition': None,
}]
definition['safeguards']['independent'] = False
definition['safeguards']['self_exception'] = {'enabled': False}
saved = matrix.save_draft(data['draft']['version_id'],
                          data['draft']['draft_revision'], definition)
assert not saved['errors'], saved['errors']
preview = matrix.publication_preview(data['draft']['version_id'])
assert not preview['errors'], preview['errors']
warnings = {w['code'] for w in preview['warnings']}
assert warnings <= {'single_person', 'independence_off'}, preview['warnings']
reason = ('Owner explicitly authorized Sudima HR to submit and approve alone, '
          'including bank changes, for Sudima Records only on 7 November 2026. '
          'Remove the separate Finance step and permit self-approval; retain an '
          'explicit approval action and its audit trail.')
published = matrix.publish(data['draft']['version_id'], saved['draft_revision'],
                           reason=reason, confirmations=sorted(warnings))
result = {'applied': apply, 'database': 'sudima', 'workflow': workflow.id,
          'version': published['revision'], 'approver': hr.login,
          'self_approval': True, 'separate_finance': False,
          'confirmed_warnings': sorted(warnings), 'replacements': []}
for proposal in old:
    previous_request = proposal.approval_request_id.id
    inbox.cancel(previous_request,
                 'Superseded by the identical import under the owner-approved Sudima HR Records route.')
    assert proposal.approval_request_id.state == 'cancelled'
    replacement = h['pb.records.desk'].apply_changes(
        proposal.config_id.id or 0, proposal.requested(),
        note=(proposal.note or '') + ' Replaces %s after the owner-approved Records route change.' % proposal.name,
        source='import')
    assert replacement['ok'] and replacement['pending'] and not replacement['refused']
    new = h['pb.records.apply'].browse(replacement['apply_id'])
    assert new.values_count == proposal.values_count and new.people_count == proposal.people_count
    request = new.approval_request_id
    assert request.version_id.id == published['version_id'] and request.state == 'pending'
    seats = request.seat_ids.filtered(lambda s: s.status == 'open')
    assert seats.mapped('acting_user_id').ids == [hr.id]
    assert inbox.get_request(request.id)['can_decide']
    entry = {'old_reference': proposal.name, 'old_request': previous_request,
             'reference': new.name, 'request': request.id,
             'values': new.values_count, 'people': new.people_count}
    result['replacements'].append(entry)
    target = receipt['master_import'] if not proposal.config_id else next(
        c['records'] for c in receipt['configuration'] if c['id'] == proposal.config_id.id)
    target.update(reference=new.name, pending=True, with_whom=hr.name,
                  supersedes=proposal.name)

assert fingerprint(others, ['definition', 'status', 'write_date']) == other_before
assert fingerprint(responsibilities, ['user_id', 'backup_user_id', 'write_date']) == roles_before
assert {m: fingerprint(a[m].search([]), ['write_date']) for m in protected_models} == protected
cfg = h['hr.formula.config'].browse(7844)
assert cfg.state == 'draft' and not cfg.application_data_enabled
if apply:
    assert not (root/'applied-before-records-route.json').exists()
    (root/'applied-before-records-route.json').write_text(before_receipt)
    a.cr.commit()
    (root/'applied.json').write_text(json.dumps(receipt, indent=2))
    (root/'records-route-applied.json').write_text(json.dumps(result, indent=2))
else:
    a.cr.rollback()
print('SUDIMA_RECORDS_ROUTE', json.dumps(result))
