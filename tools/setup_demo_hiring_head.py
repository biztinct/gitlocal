"""Run in an Odoo shell; apply only with APPLY_DEMO_HIRING_HEAD=20261029.

Owner-requested setup for the existing payobook Demo Talent Lead. Other active
databases are verified without provisioning demo users. No module-upgrade hook.
"""
import json
import os

from odoo.exceptions import AccessError
from odoo.addons.biz_access.models.studio_catalogue import workspace_of

assert env.uid == 1
assert env.cr.dbname in ('payobook', 'payobook_template', 'p0clone', 'rize')
apply = os.environ.get('APPLY_DEMO_HIRING_HEAD') == '20261029'
reason = ('Owner requested all Hiring access for DEMO Talent Lead as head of '
          'Hiring, 29 October 2026. Hiring workspace ownership only; existing '
          'review and approval requirements remain in force.')
report = {'database': env.cr.dbname, 'applied': apply, 'changed': False}
user = env['res.users'].with_context(active_test=False).search([
    ('login', '=', 'demo.talentlead@example.com')])

if env.cr.dbname != 'payobook':
    assert not user, 'Unexpected demo account outside payobook: review explicitly'
    report['result'] = 'No demo account; no configuration change'
else:
    assert len(user) == 1 and user.active and not user.share
    assert len(user.company_ids) == 1
    access = env['pb.access'].with_company(user.company_id)
    roles = env['pb.role.profile'].search([('active', '=', True)]).filtered(
        lambda role: workspace_of(role) == 'hiring')
    head = roles.filtered(lambda role: role.ability_ids.mapped('technical_key') == ['hiring-head'])
    assert len(head) == 1
    membership = env['pb.access.membership'].search([
        ('user_id', '=', user.id), ('workspace', '=', 'hiring'), ('active', '=', True)])
    assert len(membership) == 1 and membership.profile_id.role_ids == head
    assert not membership.date_end and membership.profile_id.active
    assert user.has_group('pb_hiring.group_hiring_admin')
    before = set(user.all_group_ids.ids)
    restriction = env.ref('pb_hiring.group_hiring_only')
    home = env.ref('pb_hiring.action_pb_hiring_hub')
    changes = {}
    if restriction in user.group_ids:
        # Normal res.users.write also removes this direct baseline restriction,
        # so the next access reconciliation cannot silently restore it.
        changes['group_ids'] = [(3, restriction.id)]
    if user.action_id != home:
        changes['action_id'] = home.id
    if changes:
        user.write(changes)
        report['changed'] = True

    owners = access._studio_store('pb.access.owner')
    owner = owners.with_context(active_test=False).search([
        ('user_id', '=', user.id), ('company_id', '=', user.company_id.id),
        ('workspace', '=', 'hiring')])
    desired = {'active': True, 'role_ids': [(6, 0, roles.ids)]}
    if not owner:
        owner = owners.create(dict(desired, user_id=user.id,
            company_id=user.company_id.id, workspace='hiring'))
        report['changed'] = True
    elif not owner.active or set(owner.role_ids.ids) != set(roles.ids):
        owner.write(desired)
        report['changed'] = True

    user._pb_reconcile_access()
    assert set(user.all_group_ids.ids) == before - {restriction.id}
    assert not user.has_group('base.group_system')
    as_user = access.with_user(user)
    assert not as_user.can_manage(), 'Do not grant global access administration'
    studio = as_user.studio_data('hiring')
    assert studio['can_manage'] and not studio['central_owner']
    assert set(owner.role_ids.ids) == set(roles.ids)
    for workspace in ('people', 'payroll', 'lifecycle', 'money', 'system'):
        try:
            as_user._studio_scope(workspace)
        except AccessError:
            pass
        else:
            raise AssertionError('Unexpected access ownership: ' + workspace)

    hiring = env['pb.hiring'].with_user(user).with_company(user.company_id)
    assert all(getattr(hiring, name)() for name in (
        'can_open', '_can_recruit', '_can_write', '_can_admin', 'can_open_job_boards'))
    checks = []
    for method in ('get_board', 'get_setup', 'get_forms', 'get_emails',
                   'get_automations', 'get_retention_preview', 'get_applicants',
                   'get_offers', 'job_board_home', 'job_board_catalogue',
                   'connection_overview'):
        result = getattr(hiring, method)()
        assert result.get('allowed', True), method
        checks.append(method)
    analytics = env['pb.hiring.analytics'].with_user(user).with_company(user.company_id)
    for method in ('get_board', 'get_funnel', 'get_ageing', 'get_leadership'):
        result = getattr(analytics, method)()
        assert result.get('allowed', True), method
        checks.append('analytics.' + method)
    sidebar = env['pb.sidebar.item'].with_user(user).get_sidebar_data()
    assert any(item['action_xmlid'] == 'pb_hiring.action_pb_hiring_hub'
               and not item['restricted'] for section in sidebar for item in section['items'])
    report.update(user_id=user.id, profile=membership.profile_id.name,
        role=head.name, expiry=False, home_action=home.id,
        hiring_access_owner=True, grant_ceiling=roles.mapped('name'),
        feature_checks=checks, global_access_admin=False,
        other_workspace_ownership=False)
    if report['changed']:
        access._studio_event('hiring', 'Demo head of Hiring access configured',
            reason, report, user)

env.flush_all()
if apply:
    env.cr.commit()
    env.registry.signal_changes()
else:
    env.cr.rollback()
print('DEMO_HIRING_HEAD=' + json.dumps(report))
