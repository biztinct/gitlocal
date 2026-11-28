"""Run in an Odoo maintenance shell after backup; dry-run unless explicitly enabled.

Owner-authorized setup for the existing traceability-matrix accounts. No new
logins/passwords, no demo replication to production, no forged second approver.
This is intentionally not an automatic module-upgrade hook.
"""
import json
import os
from collections import defaultdict
from odoo import fields
from odoo.addons.biz_access.models.studio_catalogue import workspace_of
from odoo.addons.biz_access.models.studio_models import STUDIO

assert env.uid == 1
assert env.cr.dbname in ('payobook', 'payobook_template', 'p0clone', 'rize', 'codex_studio_followup_20261028')
APPLY = os.environ.get('APPLY_TRACEABILITY_ACCESS') == 'owner-authorized-20261028'
REASON = 'Owner requested complete profile, role and policy setup for the traceability matrix accounts, 28 October 2026.'
MATRIX = {
    'demo.recruiter@example.com': ('hiring', 'Recruiting team', ['hiring-recruiter']),
    'demo.talentlead@example.com': ('hiring', 'Hiring leadership', ['hiring-head']),
    'demo.hiringmanager@example.com': ('hiring', 'Hiring managers', ['hiring-requester']),
    'ess1.demo@payobook.com': ('people', 'Employee self service', ['studio-employee-self']),
    'lam.ngo@example.com': ('people', 'Team managers', ['studio-team-manager']),
    'diep.thai@example.com': ('money', 'Function budget owners', ['budget-holder']),
    'linh.quan@example.com': ('money', 'Finance budget reviewers', ['budget-finance']),
    'tuan.quach@example.com': ('people', 'Employee self service', ['studio-employee-self']),
    'demo.field@example.com': ('people', 'Field team', ['field-staff']),
    'komal@rize.farm': ('people', 'Learning administration', ['training-head']),
}
PORTALS = ['demo.learner@example.com', 'demo.agency@example.com', 'khoi.tran@example.com', 'huy.dinh@example.com']
Users = env['res.users'].with_context(active_test=False)
if env.cr.dbname in ('rize', 'p0clone', 'payobook_template'):
    # Production gets only the documented, already-existing training account.
    MATRIX = {k:v for k,v in MATRIX.items() if k == 'komal@rize.farm'}
    PORTALS = []
users = Users.search([('login', 'in', list(MATRIX) + PORTALS + ([] if env.cr.dbname == 'rize' else ['demo.hr@example.com']))])
assert all(u.active for u in users), 'Do not reactivate a retired matrix account'
report = {'database': env.cr.dbname, 'applied': APPLY, 'profiles': [], 'accounts': [], 'policies': []}


def native_role(key, name, workspace, xmlids):
    """Name a native capability only where a persona already holds it."""
    ability = env['pb.role.ability'].search([('technical_key', '=', key)])
    groups = env['res.groups'].browse([env.ref(x).id for x in xmlids])
    if not ability:
        ability = env['pb.role.ability'].create({'technical_key': key, 'name': name,
            'description': 'Existing application permissions; company, personal and sharing rules apply.',
            'area': 'lifecycle' if workspace == 'hiring' else workspace, 'group_ids': [(6, 0, groups.ids)]})
    assert set(ability.group_ids.ids) == set(groups.ids)
    role = env['pb.role.profile'].search([('ability_ids', 'in', ability.id)]).filtered(lambda r: r.ability_ids == ability)
    if not role:
        role = env['pb.role.profile'].create({'name': name, 'area': ability.area,
            'description': ability.description, 'ability_ids': [(6, 0, ability.ids)]})
    assert len(role) == 1
    return role


native_role('hiring-requester', 'Hiring requestor', 'hiring', ['base.group_user'])
native_role('studio-employee-self', 'Employee self service', 'people', ['base.group_user'])
native_role('studio-team-manager', 'Team management', 'people', ['base.group_user', 'hr_holidays.group_hr_holidays_responsible'])
native_role('studio-hr-records', 'HR records administration', 'people', ['hr.group_hr_manager'])
native_role('studio-payroll-operations', 'Payroll operations', 'payroll', ['om_hr_payroll.group_hr_payroll_manager'])
roles = env['pb.role.profile'].search([])


def by_keys(keys):
    found = env['pb.role.profile']
    for key in keys:
        matches = roles.filtered(lambda r: r.ability_ids.mapped('technical_key') == [key])
        assert len(matches) == 1, (key, matches.ids)
        found |= matches
    return found


# Publish only previously-unconfigured policies, reflecting existing native
# capabilities, never guessed narrower ownership or hidden fields. Record rules
# and native field groups remain authoritative. Existing owner edits are kept.
policy_keys = {'hiring-recruiter', 'hiring-manager', 'hiring-head', 'hiring-requester',
    'studio-hr-records', 'studio-payroll-operations', 'payroll-read', 'payroll-officer',
    'payroll-manager', 'payroll-administrator', 'payroll-final-approver', 'pay-reporting-read'}
for role in roles.filtered(lambda r: bool(set(r.ability_ids.mapped('technical_key')) & policy_keys) and workspace_of(r) in ('hiring', 'people', 'payroll')):
    workspace = workspace_of(role)
    access = env['pb.access']
    if role.studio_policy:
        continue
    policy = {k:v for k,v in access._studio_policy_defaults(role, workspace).items() if v['read'] != 'none'}
    if not policy:
        continue
    clean = access._studio_validate_policy(workspace, policy)
    role.with_context(_pb_studio=STUDIO).write({'studio_policy': clean, 'studio_policy_revision': role.studio_policy_revision + 1})
    holders = env['pb.role.assignment'].search([('profile_id', '=', role.id)]).user_id
    holders._pb_reconcile_access()
    access._studio_event(workspace, 'Existing role policy made explicit', REASON,
        {'role_id': role.id, 'after': clean, 'native_permissions_unchanged': True,
         'note': 'Native ACL starting limits; existing company, sharing, workflow and field-group restrictions retained.'})
    report['policies'].append({'role': role.name, 'resources': list(clean)})

companies = users.company_id or env.company
for company in companies:
    access = env['pb.access'].with_company(company)
    owner = env.ref('base.user_admin')
    if company not in owner.company_ids or not owner.active:
        owner = env['res.users'].search([('active','=',True),('share','=',False),('company_ids','in',company.id)]).filtered(
            lambda u: access.with_user(u).can_manage())[:1]
    assert owner, 'A real current access owner is required for '+company.name
    grouped = defaultdict(lambda: env['res.users'])
    for user in users.filtered(lambda u: u.company_id == company and u.login in MATRIX):
        grouped[MATRIX[user.login][0:2] + (tuple(MATRIX[user.login][2]),)] |= user
    # HR lead spans five workspaces; include maximal existing business roles,
    # keeping original stock permissions that are outside this catalogue.
    hr = users.filtered(lambda u: u.company_id == company and u.login == 'demo.hr@example.com')
    if hr:
        for workspace, name, keys in [
            ('people', 'HR service team', ['studio-hr-records','equipment-team','packages-and-awards-head','recognition-lead','goals-hr-lead','training-manager','growth-plans-head','announcements-head']),
            ('lifecycle', 'HR lifecycle team', ['lifecycle-team']),
            ('money', 'HR budget administration', ['budget-team']),
            ('payroll', 'HR payroll operations', ['studio-payroll-operations','pay-reporting-read','formula-view']),
            ('system', 'HR access and vendor administration', ['access-team','vendor-team'])]:
            grouped[(workspace,name,tuple(keys))] |= hr
    # The detailed Leave/Attendance tests also use this login as HR, although
    # the cover lists only its resignation scenario. Preserve both use cases.
    workforce_hr = users.filtered(lambda u: u.company_id == company and u.login == 'tuan.quach@example.com')
    if workforce_hr:
        grouped[('people', 'Workforce HR reviewer', ('studio-hr-records',))] |= workforce_hr
    # Useful unassigned packages exist even on clean template/clone environments.
    for workspace,name,keys in [('hiring','Recruiting team',('hiring-recruiter',)),
            ('hiring','Hiring leadership',('hiring-head',)), ('hiring','Hiring managers',('hiring-requester',)),
            ('people','People records team',('records-edit',)),
            ('payroll','Payroll preparation',('payroll-officer',)),
            ('payroll','Payroll reporting',('payroll-read','pay-reporting-read'))]:
        grouped[(workspace,name,keys)]
    for (workspace,name,keys),people in grouped.items():
        selected = by_keys(keys)
        key = 'matrix_profile_%s_%s' % (company.id, '_'.join(keys).replace('-', '_'))
        profile = access._studio_adopt_existing(key,name,workspace,selected,people,owner,REASON)
        report['profiles'].append({'id':profile.id,'name':profile.name,'workspace':workspace,'company':company.name,'roles':selected.mapped('name'),'logins':people.mapped('login')})
    for user in users.filtered(lambda u: u.company_id == company):
        memberships = env['pb.access.membership'].search([('user_id','=',user.id)])
        report['accounts'].append({'login':user.login,'portal':user.share,'profiles':memberships.profile_id.mapped('name'),
            'native_groups_retained':True,'scope':'Existing portal controller and employee/agency ownership rules' if user.share else 'Profiles plus remaining independent application permissions'})

env.flush_all()
if APPLY:
    env.cr.commit()
else:
    env.cr.rollback()
print('TRACEABILITY_SETUP='+json.dumps(report))
