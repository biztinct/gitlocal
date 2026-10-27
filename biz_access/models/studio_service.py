import copy
from datetime import timedelta
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from .access_common import implied_closure, visible_people, forbidden_in_closure
from .studio_catalogue import WORKSPACES, RESOURCES, ACTIONS, SCOPES, workspace_of
from .studio_models import STUDIO
from .role_assignments import INTERNAL


class AccessStudio(models.AbstractModel):
    _inherit = 'pb.access'

    def _studio_store(self, model):
        return self.env[model].sudo().with_context(_pb_studio=STUDIO)

    def _studio_scope(self, workspace, manage=True):
        self._require()
        if workspace not in dict(WORKSPACES):
            raise UserError(_('Choose a module first.'))
        owners = self.env['pb.access.owner'].sudo().search([
            ('user_id', '=', self.env.uid), ('company_id', '=', self.env.company.id),
            ('workspace', '=', workspace), ('active', '=', True)])
        if manage and not self.can_manage() and not owners:
            raise AccessError(_('You are not an access owner for this module.'))
        return owners

    def _studio_roles(self, role_ids, workspace, definition=False):
        owners = self._studio_scope(workspace)
        ids = set(int(x) for x in role_ids)
        roles = self.env['pb.role.profile'].sudo().browse(sorted(ids)).exists()
        if set(roles.ids) != ids or any(not r.active or not r.group_ids for r in roles):
            raise UserError(_('Choose active roles with abilities.'))
        if forbidden_in_closure(roles.group_ids, self.env):
            raise AccessError(_('Administrator permissions cannot be assigned here.'))
        if not self.can_manage() and not ids <= set(owners.role_ids.ids):
            raise AccessError(_('These roles exceed your module grant ceiling.'))
        if definition and any(workspace_of(r) != workspace for r in roles):
            raise AccessError(_('A shared role must be edited in its owning module.'))
        if definition and not self.can_manage():
            users = self.env['pb.role.assignment'].sudo().search([('profile_id', 'in', roles.ids), ('active', '=', True)]).user_id
            shared = self.env['pb.access.profile'].sudo().search_count([('role_ids', 'in', roles.ids), ('company_id', '!=', self.env.company.id)])
            if shared or any(u.company_ids != self.env.company for u in users):
                raise AccessError(_('A central access owner must edit roles shared across companies.'))
        return roles

    def _studio_user(self, user_id, workspace):
        self._studio_scope(workspace)
        user = self._internal_user(user_id)
        if self.env.company not in user.sudo().company_ids:
            raise AccessError(_('This person does not belong to the selected company.'))
        if not self.can_manage() and user.sudo().company_ids != self.env.company:
            raise AccessError(_('A central access owner must review assignments for a person working across companies.'))
        return user

    def _studio_record(self, model, record_id, workspace):
        self._studio_scope(workspace)
        record = self._studio_store(model).with_context(active_test=False).browse(int(record_id)).exists()
        if not record or record.company_id != self.env.company or record.workspace != workspace:
            raise AccessError(_('This access record is outside the selected module or company.'))
        return record

    def _studio_reason(self, reason):
        reason = str(reason or '').strip()
        if not reason:
            raise UserError(_('Explain the reason for this change.'))
        return reason[:2000]

    def _studio_event(self, workspace, name, reason, details=None, user=None):
        return self._studio_store('pb.access.event').create({
            'workspace': workspace, 'company_id': self.env.company.id,
            'name': name, 'reason': reason, 'details': details or {},
            'actor_id': self.env.uid, 'user_id': user.id if user else False})

    def _studio_profile_json(self, record):
        return {'id': record.id, 'name': record.name, 'description': record.description or '',
                'workspace': record.workspace, 'role_ids': record.role_ids.ids,
                'roles': record.role_ids.mapped('name'), 'owner_id': record.owner_id.id,
                'owner': record.owner_id.name, 'review_date': str(record.review_date or ''),
                'revision': record.revision, 'active': record.active,
                'auto_department_id': record.auto_department_id.id or 0,
                'auto_department': record.auto_department_id.name or '',
                'members': self.env['pb.access.membership'].sudo().search_count([('profile_id', '=', record.id), ('active', '=', True)])}

    @api.model
    def studio_data(self, workspace='hiring', search=''):
        owners = self._studio_scope(workspace, manage=False)
        manage = bool(self.can_manage() or owners)
        domain = [('company_id', '=', self.env.company.id), ('workspace', '=', workspace)]
        roles = self.env['pb.role.profile'].search([])
        local_roles = roles.filtered(lambda r: workspace_of(r) == workspace)
        profiles = self.env['pb.access.profile'].sudo().with_context(active_test=False).search(domain)
        memberships = self.env['pb.access.membership'].sudo().search(domain)
        extra = self.env['pb.access.extra'].sudo().search(domain)
        if not manage:
            memberships = memberships.filtered(lambda a: a.user_id.id == self.env.uid)
            profiles = profiles.filtered(lambda p: p in memberships.profile_id)
            extra = extra.filtered(lambda a: a.user_id.id == self.env.uid)
        users = visible_people(self.env['res.users'].sudo().search([
            ('share', '=', False), ('company_ids', 'in', self.env.company.id),
            ('active', '=', True)] + ([] if manage else [('id', '=', self.env.uid)]) +
            ([('name', 'ilike', str(search)[:100])] if search else []), limit=201), self.env)
        if not manage:
            users = users.filtered(lambda u: u.id == self.env.uid)
        sources = self.env['pb.role.assignment'].sudo().search([('active', '=', True), ('profile_id', 'in', local_roles.ids)])
        involved = set(sources.user_id.ids) | set(memberships.user_id.ids) | set(extra.user_id.ids)
        people = []
        for user in users[:200]:
            rows = memberships.filtered(lambda m: m.user_id == user)
            grants = extra.filtered(lambda g: g.user_id == user)
            people.append({'id': user.id, 'name': user.name, 'login': user.login, 'in_module': user.id in involved,
                'assignments': [{'id': m.id, 'profile': m.profile_id.name, 'date_end': str(m.date_end or ''),
                    'review_date': str(m.review_date), 'due': m.review_date <= fields.Date.today(), 'origin': m.origin,
                    'revision': m.revision} for m in rows],
                'extras': [{'id': g.id, 'role': g.role_id.name, 'date_end': str(g.date_end)} for g in grants]})
        requests = self.env['pb.access.studio.request'].sudo().search(domain + ([] if manage else [('requested_by', '=', self.env.uid)]), limit=100)
        history = self.env['pb.access.event'].sudo().search(domain + ([] if manage else [('user_id', '=', self.env.uid)]), limit=100)
        return {'workspace': workspace, 'workspaces': [{'key': k, 'label': v} for k, v in WORKSPACES],
            'can_manage': manage, 'central_owner': self.can_manage(), 'company': self.env.company.name,
            'profiles': [self._studio_profile_json(p) for p in profiles], 'people': people, 'people_more': len(users) > 200,
            'role_ids': local_roles.ids, 'delegation_ids': self.env['pb.access.delegation'].search([('profile_ids', 'in', local_roles.ids)]).ids,
            'module_people_count': self.env['res.users'].sudo().search_count([('id', 'in', sorted(involved)), ('company_ids', 'in', self.env.company.id), ('active', '=', True)]),
            'roles': [{'id': r.id, 'name': r.name, 'workspace': workspace_of(r),
                'allowed': self.can_manage() or r in owners.role_ids, 'revision': r.studio_policy_revision} for r in roles],
            'requests': [{'id': r.id, 'name': r.name, 'kind': r.kind, 'state': r.state,
                'reason': r.reason, 'requester': r.requested_by.name, 'mine': r.requested_by.id == self.env.uid,
                'impact': r.impact, 'decision': r.decision_reason or '', 'decider': r.decided_by.name or ''} for r in requests],
            'history': [{'id': e.id, 'name': e.name, 'actor': e.actor_id.name, 'reason': e.reason,
                'date': fields.Datetime.to_string(e.create_date), 'details': e.details} for e in history],
            'departments': self.env['hr.department'].sudo().search_read([('company_id', '=', self.env.company.id)], ['name']) if manage else [],
            'owners': [{'id': o.id, 'user_id': o.user_id.id, 'name': o.user_id.name, 'role_ids': o.role_ids.ids} for o in self.env['pb.access.owner'].sudo().search(domain)] if self.can_manage() else [],
            'resources': self._studio_resources(workspace)}

    def _studio_resources(self, workspace):
        result = []
        for name, spec in RESOURCES.items():
            if spec['workspace'] != workspace or name not in self.env:
                continue
            Model = self.env[name]
            fields_out = []
            for key in spec['fields']:
                field = Model._fields.get(key)
                if field and field.store:
                    fields_out.append({'key': key, 'label': field.string, 'required': bool(field.required or key == Model._rec_name),
                        'readonly': bool(field.readonly), 'sensitive': key in spec.get('sensitive', [])})
            state = Model._fields.get(spec.get('state'))
            states = state._description_selection(self.env) if state and state.type == 'selection' else []
            result.append({'key': name, 'label': spec['label'], 'fields': fields_out,
                'department': bool(spec.get('department')), 'states': [{'key': k, 'label': v} for k, v in states],
                'owner_label': Model._fields[spec['owner'].split('.')[0]].string,
                'can_archive': 'active' in Model._fields, 'can_approve': bool(states),
                'team_label': _('People reporting to you, including yourself')})
        return result

    def _studio_expiry(self, value, required=False):
        date = fields.Date.to_date(value) if value else False
        if required and not date:
            raise UserError(_('Choose an expiry date.'))
        if date and not fields.Date.today() <= date <= fields.Date.today() + timedelta(days=366):
            raise UserError(_('Choose an expiry within the next year.'))
        return str(date) if date else False

    def _studio_conflicts(self, user, proposed_roles, remove_membership=None):
        sources = user.sudo()._pb_access_sources()
        if remove_membership:
            sources = sources.filtered(lambda s: s.source != 'package:%s' % remove_membership.id)
        roles = sources.filtered(lambda s: bool(s._groups())).profile_id | proposed_roles
        keys = set(roles.ability_ids.mapped('technical_key'))
        baseline = set(user.sudo().pb_access_baseline or user.sudo().group_ids.ids)
        for key, xmlid in [('payroll-officer', 'pb_hr_payroll_base.group_payroll_base_officer'),
                           ('payroll-manager', 'pb_hr_payroll_base.group_payroll_base_manager'),
                           ('payroll-final-approver', 'pb_hr_payroll_base.group_payroll_final_approver')]:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group and group.id in baseline:
                keys.add(key)
        # Business-defined incompatible capabilities, evaluated across sources.
        pairs = [('payroll-officer', 'payroll-final-approver'), ('payroll-manager', 'payroll-final-approver'), ('payroll-administrator', 'payroll-final-approver')]
        conflicts = []
        for left, right in pairs:
            if left in keys and right in keys:
                conflicts.append(_('Preparing and finally approving the same payroll must be separated.'))
        return conflicts

    def _studio_role_versions(self, roles):
        return {str(r.id): [r.revision, r.studio_policy_revision] for r in roles}

    def _studio_lock_role_versions(self, roles, expected):
        for role in roles.sorted('id'):
            self.env.cr.execute('SELECT id FROM pb_role_profile WHERE id=%s FOR UPDATE', [role.id])
        roles.invalidate_recordset()
        if self._studio_role_versions(roles) != expected:
            raise UserError(_('A referenced role changed after submission. Review and submit the latest version.'))

    def _studio_queue(self, workspace, kind, name, payload, impact, reason):
        request = self._studio_store('pb.access.studio.request').create({
            'workspace': workspace, 'company_id': self.env.company.id, 'kind': kind, 'name': name,
            'payload': payload, 'impact': impact, 'reason': reason, 'requested_by': self.env.uid})
        self._studio_event(workspace, _('Submitted: %s', name), reason, {'request_id': request.id, 'impact': impact})
        return {'id': request.id, 'message': _('Submitted for an independent access owner to review.')}

    @api.model
    def studio_submit_profile(self, workspace, values, reason):
        self._studio_scope(workspace)
        reason = self._studio_reason(reason)
        roles = self._studio_roles(values.get('role_ids', []), workspace)
        if not roles or not str(values.get('name', '')).strip():
            raise UserError(_('Give the profile a name and select at least one role.'))
        owner = self._studio_user(values.get('owner_id'), workspace)
        if not self.with_user(owner).can_manage() and not self.env['pb.access.owner'].sudo().search_count([
                ('user_id', '=', owner.id), ('workspace', '=', workspace), ('company_id', '=', self.env.company.id)]):
            raise UserError(_('The profile owner must be a central or module access owner.'))
        review_date = self._studio_expiry(values.get('review_date'), required=True)
        profile = self._studio_record('pb.access.profile', values['id'], workspace) if values.get('id') else None
        if profile and (not profile.active or profile.revision != int(values.get('revision', 0))):
            raise UserError(_('This profile changed or was retired. Reopen it.'))
        department = self.env['hr.department'].sudo().browse(int(values.get('auto_department_id') or 0)).exists()
        if department and department.company_id != self.env.company:
            raise UserError(_('Choose a department in the current company.'))
        vals = {'name': str(values['name']).strip()[:150], 'description': str(values.get('description') or '')[:2000],
                'role_ids': roles.ids, 'owner_id': owner.id, 'review_date': review_date,
                'auto_department_id': department.id or False}
        members = self.env['pb.access.membership'].sudo().search([('profile_id', '=', profile.id), ('active', '=', True)]) if profile else self.env['pb.access.membership']
        conflicts = [c for m in members for c in self._studio_conflicts(m.user_id, roles, m)]
        if conflicts:
            raise UserError('\n'.join(sorted(set(conflicts))))
        impact = {'before': self._studio_profile_json(profile) if profile else {}, 'after': dict(vals, roles=roles.mapped('name')),
                  'people': members.user_id.mapped('name'), 'count': len(members)}
        return self._studio_queue(workspace, 'profile', _('Profile: %s', vals['name']),
            {'id': profile.id if profile else 0, 'revision': profile.revision if profile else 0, 'values': vals, 'role_versions': self._studio_role_versions(roles)}, impact, reason)

    @api.model
    def studio_submit_assignment(self, workspace, profile_id, user_ids, date_end, reason):
        reason = self._studio_reason(reason)
        profile = self._studio_record('pb.access.profile', profile_id, workspace)
        if not profile.active:
            raise UserError(_('A retired profile cannot be assigned.'))
        self._studio_roles(profile.role_ids.ids, workspace)
        users = [self._studio_user(uid, workspace) for uid in sorted(set(user_ids))]
        if not users or len(users) > 100:
            raise UserError(_('Select between one and 100 people.'))
        for user in users:
            conflicts = self._studio_conflicts(user, profile.role_ids)
            if conflicts:
                raise UserError('%s: %s' % (user.name, '; '.join(conflicts)))
        payload = {'profile_id': profile.id, 'revision': profile.revision, 'users': [u.id for u in users],
                   'date_end': self._studio_expiry(date_end), 'memberships': {}, 'role_versions': self._studio_role_versions(profile.role_ids)}
        for user in users:
            row = self.env['pb.access.membership'].sudo().with_context(active_test=False).search([
                ('profile_id', '=', profile.id), ('user_id', '=', user.id)])
            payload['memberships'][str(user.id)] = row.revision if row else 0
        return self._studio_queue(workspace, 'assign', _('Assign %s', profile.name), payload,
            {'people': [u.name for u in users], 'roles': profile.role_ids.mapped('name'), 'count': len(users),
             'expires': payload['date_end'] or _('No expiry'), 'note': _('Independent roles and hand-overs remain in place.')}, reason)

    @api.model
    def studio_submit_extra(self, workspace, user_id, role_id, date_end, reason):
        reason = self._studio_reason(reason)
        self._studio_scope(workspace, manage=False)
        user = self._internal_user(user_id)
        if not (self.can_manage() or self.env['pb.access.owner'].sudo().search_count([
                ('user_id', '=', self.env.uid), ('workspace', '=', workspace), ('company_id', '=', self.env.company.id)])) and user.id != self.env.uid:
            raise AccessError(_('You can request temporary access for yourself.'))
        role = self.env['pb.role.profile'].browse(int(role_id)).exists()
        role.check_access('read')
        if not role or not role.active or workspace_of(role) != workspace:
            raise UserError(_('Choose an active role from this module.'))
        if self.env.company not in user.sudo().company_ids:
            raise AccessError(_('Choose a person in this company.'))
        return self._studio_queue(workspace, 'extra', _('Temporary %s', role.name),
            {'user_id': user.id, 'role_id': role.id, 'revision': role.revision, 'date_end': self._studio_expiry(date_end, True), 'role_versions': self._studio_role_versions(role)},
            {'people': [user.name], 'roles': [role.name], 'expires': date_end,
             'conflicts': self._studio_conflicts(user, role)}, reason)

    def _studio_validate_policy(self, workspace, policy):
        if not isinstance(policy, dict):
            raise UserError(_('Invalid policy.'))
        resources = {r['key']: r for r in self._studio_resources(workspace)}
        clean = {}
        for model, rule in policy.items():
            if model not in resources or not isinstance(rule, dict):
                raise UserError(_('That resource is not available in this module.'))
            spec = resources[model]
            item = {}
            for action in ACTIONS:
                scope = rule.get(action, 'none')
                if scope not in SCOPES:
                    raise UserError(_('Choose a valid record scope.'))
                item[action] = scope
            for action in ('export', 'archive', 'reassign', 'approve', 'reveal', 'download'):
                item[action] = bool(rule.get(action, False))
            item['fields'] = {}
            field_specs = {f['key']: f for f in spec['fields']}
            for name, value in (rule.get('fields') or {}).items():
                if name not in field_specs or value not in ('hidden', 'view', 'edit', 'masked'):
                    raise UserError(_('Choose a supported field and permission.'))
                f = field_specs[name]
                if f['required'] and value in ('hidden', 'masked'):
                    raise UserError(_('A required field cannot be hidden or masked.'))
                if value == 'masked' and not f['sensitive']:
                    raise UserError(_('Masking is available for the sensitive fields marked here.'))
                if value == 'edit' and f['readonly']:
                    raise UserError(_('A computed or read-only field cannot be made editable.'))
                item['fields'][name] = value
            item['create_fields'] = sorted(set(rule.get('create_fields') or []))
            if not set(item['create_fields']) <= set(field_specs):
                raise UserError(_('Choose supported creation fields.'))
            for f in field_specs.values():
                if f['required'] and not f['readonly'] and item['create'] != 'none' and f['key'] not in item['create_fields']:
                    raise UserError(_('Required fields must remain available when creating records.'))
            item['department_ids'] = sorted(set(int(x) for x in rule.get('department_ids', [])))
            departments = self.env['hr.department'].sudo().browse(item['department_ids']).exists()
            if set(departments.ids) != set(item['department_ids']) or any(d.company_id != self.env.company for d in departments):
                raise UserError(_('Choose departments from the current company.'))
            if item['department_ids'] and not spec['department']:
                raise UserError(_('This resource does not support a department rule.'))
            item['states'] = sorted(set(rule.get('states') or []))
            if not set(item['states']) <= {s['key'] for s in spec['states']}:
                raise UserError(_('Choose valid workflow stages.'))
            item['match'] = rule.get('match', 'all')
            if item['match'] not in ('all', 'any'):
                raise UserError(_('Choose whether all or any conditions must match.'))
            item['write_states'] = sorted(set(rule.get('write_states') or []))
            if not set(item['write_states']) <= {s['key'] for s in spec['states']}:
                raise UserError(_('Choose valid editable stages.'))
            clean[model] = item
        return clean

    @api.model
    def studio_role_policy(self, workspace, role_id):
        role = self._studio_roles([role_id], workspace, definition=True)
        users = self.env['pb.role.assignment'].sudo().search([('profile_id', '=', role.id), ('active', '=', True)]).user_id
        profiles = self.env['pb.access.profile'].sudo().search([('role_ids', 'in', role.id)])
        return {'id': role.id, 'name': role.name, 'revision': role.studio_policy_revision,
                'role_revision': role.revision, 'policy': copy.deepcopy(role.sudo().studio_policy or {}),
                'people': visible_people(users, self.env).mapped('name'), 'profiles': profiles.mapped('name'),
                'resources': self._studio_resources(workspace)}

    @api.model
    def studio_submit_policy(self, workspace, role_id, revision, policy, reason):
        reason = self._studio_reason(reason)
        role = self._studio_roles([role_id], workspace, definition=True)
        if role.studio_policy_revision != int(revision):
            raise UserError(_('The policy changed while you were editing. Reopen it.'))
        clean = self._studio_validate_policy(workspace, policy)
        users = self.env['pb.role.assignment'].sudo().search([('profile_id', '=', role.id), ('active', '=', True)]).user_id
        profiles = self.env['pb.access.profile'].sudo().search([('role_ids', 'in', role.id)])
        return self._studio_queue(workspace, 'policy', _('Policy: %s', role.name),
            {'role_id': role.id, 'revision': role.studio_policy_revision, 'role_revision': role.revision, 'policy': clean},
            {'before': role.sudo().studio_policy or {}, 'after': clean, 'count': len(users),
             'people': visible_people(users, self.env).mapped('name'), 'profiles': profiles.mapped('name'),
             'note': _('Existing application permissions and company rules remain the upper limit.')}, reason)

    @api.model
    def studio_decide(self, workspace, request_id, approve, reason):
        reason = self._studio_reason(reason)
        request = self._studio_record('pb.access.studio.request', request_id, workspace)
        self.env.cr.execute('SELECT id FROM pb_access_studio_request WHERE id=%s FOR UPDATE', [request.id])
        request.invalidate_recordset()
        if request.state != 'pending':
            raise UserError(_('This request has already been decided.'))
        if request.requested_by.id == self.env.uid:
            raise AccessError(_('A different access owner must decide your request.'))
        payload = request.payload
        if approve:
            # Both identities must still be authorized at the point of use.
            requester = self.with_user(request.requested_by).with_context(allowed_company_ids=[self.env.company.id])
            if request.kind != 'extra':
                requester._studio_scope(workspace)
            if request.kind == 'profile':
                vals = dict(payload['values'])
                roles = self._studio_roles(vals['role_ids'], workspace)
                requester._studio_roles(roles.ids, workspace)
                self._studio_lock_role_versions(roles, payload['role_versions'])
                record = self._studio_record('pb.access.profile', payload['id'], workspace) if payload['id'] else None
                if record:
                    self.env.cr.execute('SELECT id FROM pb_access_profile WHERE id=%s FOR UPDATE', [record.id])
                    record.invalidate_recordset()
                    if record.revision != payload['revision'] or not record.active:
                        raise UserError(_('The profile changed after submission. Submit a fresh review.'))
                    members = self.env['pb.access.membership'].sudo().search([('profile_id', '=', record.id), ('active', '=', True)])
                    for member in members:
                        self._studio_user(member.user_id.id, workspace)
                        conflicts = self._studio_conflicts(member.user_id, roles, member)
                        if conflicts:
                            raise UserError('; '.join(conflicts))
                vals['role_ids'] = [(6, 0, roles.ids)]
                if record:
                    record.write(dict(vals, revision=record.revision + 1))
                    members._sync_roles()
                else:
                    record = self._studio_store('pb.access.profile').create(dict(vals, workspace=workspace, company_id=self.env.company.id))
                self._studio_event(workspace, _('Profile published: %s', record.name), request.reason,
                    {'profile_id': record.id, 'snapshot': self._studio_profile_json(record), 'request_id': request.id})
            elif request.kind == 'assign':
                profile = self._studio_record('pb.access.profile', payload['profile_id'], workspace)
                self.env.cr.execute('SELECT id FROM pb_access_profile WHERE id=%s FOR UPDATE', [profile.id])
                profile.invalidate_recordset()
                if profile.revision != payload['revision'] or not profile.active:
                    raise UserError(_('The profile changed after submission. Submit a fresh review.'))
                self._studio_roles(profile.role_ids.ids, workspace)
                requester._studio_roles(profile.role_ids.ids, workspace)
                self._studio_lock_role_versions(profile.role_ids, payload['role_versions'])
                self._studio_expiry(payload['date_end'])
                for uid in sorted(payload['users']):
                    user = self._studio_user(uid, workspace)
                    requester._studio_user(uid, workspace)
                    self.env.cr.execute('SELECT id FROM res_users WHERE id=%s FOR UPDATE', [user.id])
                    member = self._studio_store('pb.access.membership').with_context(active_test=False).search([
                        ('user_id', '=', uid), ('profile_id', '=', profile.id)])
                    if (member.revision if member else 0) != payload['memberships'][str(uid)]:
                        raise UserError(_('An assignment changed after submission. Submit a fresh review.'))
                    conflicts = self._studio_conflicts(user, profile.role_ids, member)
                    if conflicts:
                        raise UserError('; '.join(conflicts))
                    vals = {'active': True, 'date_end': payload['date_end'], 'reason': request.reason,
                            'review_date': fields.Date.today() + timedelta(days=90), 'origin': 'manual'}
                    if member:
                        member.write(dict(vals, revision=member.revision + 1))
                    else:
                        member = self._studio_store('pb.access.membership').create(dict(vals, user_id=uid, profile_id=profile.id))
                    member._sync_roles()
                    self._studio_event(workspace, _('Assigned %s', profile.name), request.reason, {'membership_id': member.id}, user)
            elif request.kind == 'policy':
                role = self._studio_roles([payload['role_id']], workspace, definition=True)
                requester._studio_roles(role.ids, workspace, definition=True)
                self.env.cr.execute('SELECT id FROM pb_role_profile WHERE id=%s FOR UPDATE', [role.id])
                role.invalidate_recordset()
                if role.studio_policy_revision != payload['revision'] or role.revision != payload['role_revision']:
                    raise UserError(_('The role changed after submission. Submit a fresh review.'))
                policy = self._studio_validate_policy(workspace, payload['policy'])
                before = role.sudo().studio_policy or {}
                role.sudo().with_context(_pb_studio=STUDIO).write({'studio_policy': policy, 'studio_policy_revision': role.studio_policy_revision + 1})
                users = self.env['pb.role.assignment'].sudo().search([('profile_id', '=', role.id), ('active', '=', True)]).user_id
                for user in users:
                    conflicts = self._studio_conflicts(user, role)
                    if conflicts:
                        raise UserError('%s: %s' % (user.name, '; '.join(conflicts)))
                users._pb_reconcile_access()
                self.env.registry.clear_cache()
                self._studio_event(workspace, _('Policy published: %s', role.name), request.reason,
                    {'role_id': role.id, 'revision': role.studio_policy_revision, 'before': before, 'after': policy, 'request_id': request.id})
            elif request.kind == 'extra':
                role = self._studio_roles([payload['role_id']], workspace)
                user = self._studio_user(payload['user_id'], workspace)
                self._studio_lock_role_versions(role, payload['role_versions'])
                if role.revision != payload['revision']:
                    raise UserError(_('The role changed after submission. Request it again.'))
                conflicts = self._studio_conflicts(user, role)
                if conflicts:
                    raise UserError('; '.join(conflicts))
                grant = self._studio_store('pb.access.extra').create({
                    'user_id': user.id, 'role_id': role.id, 'date_end': self._studio_expiry(payload['date_end'], True),
                    'reason': request.reason, 'company_id': self.env.company.id, 'workspace': workspace})
                grant._sync_roles()
                self._studio_event(workspace, _('Temporary role: %s', role.name), request.reason, {'extra_id': grant.id}, user)
        request.write({'state': 'approved' if approve else 'rejected', 'decided_by': self.env.uid,
                       'decided_on': fields.Datetime.now(), 'decision_reason': reason})
        self._studio_event(workspace, _('Approved: %s', request.name) if approve else _('Rejected: %s', request.name), reason, {'request_id': request.id})
        return {'message': _('Change applied and recorded.') if approve else _('Request rejected and recorded.')}

    @api.model
    def studio_review_assignment(self, workspace, membership_id, revision, retain, reason):
        reason = self._studio_reason(reason)
        member = self._studio_record('pb.access.membership', membership_id, workspace)
        self._studio_user(member.user_id.id, workspace)
        self._studio_roles(member.profile_id.role_ids.ids, workspace)
        self.env.cr.execute('SELECT id FROM pb_access_membership WHERE id=%s FOR UPDATE', [member.id])
        member.invalidate_recordset()
        if member.revision != int(revision) or not member.active:
            raise UserError(_('This assignment changed. Refresh the review.'))
        member.write({'active': bool(retain), 'review_date': fields.Date.today() + timedelta(days=90),
                      'reason': reason, 'revision': member.revision + 1})
        member._sync_roles()
        self._studio_event(workspace, _('Access retained') if retain else _('Profile assignment revoked'), reason,
                           {'profile_id': member.profile_id.id, 'membership_id': member.id}, member.user_id)
        return {'message': _('Review recorded. Independent grants are preserved.')}

    @api.model
    def studio_revoke_extra(self, workspace, extra_id, reason):
        reason = self._studio_reason(reason)
        grant = self._studio_record('pb.access.extra', extra_id, workspace)
        self._studio_user(grant.user_id.id, workspace)
        self._studio_roles(grant.role_id.ids, workspace)
        grant.write({'active': False})
        grant._sync_roles()
        self._studio_event(workspace, _('Temporary role revoked'), reason, {'extra_id': grant.id}, grant.user_id)
        return {'message': _('Temporary grant revoked; other sources are retained.')}

    @api.model
    def studio_retire_profile(self, workspace, profile_id, revision, reason):
        reason = self._studio_reason(reason)
        profile = self._studio_record('pb.access.profile', profile_id, workspace)
        self._studio_roles(profile.role_ids.ids, workspace)
        self.env.cr.execute('SELECT id FROM pb_access_profile WHERE id=%s FOR UPDATE', [profile.id])
        profile.invalidate_recordset()
        if profile.revision != int(revision):
            raise UserError(_('The profile changed. Refresh it.'))
        if self.env['pb.access.membership'].sudo().search_count([('profile_id', '=', profile.id), ('active', '=', True)]):
            raise UserError(_('Remove active assignments before retiring this profile.'))
        profile.write({'active': False, 'auto_department_id': False, 'revision': profile.revision + 1})
        self._studio_event(workspace, _('Profile retired: %s', profile.name), reason, {'profile_id': profile.id})
        return {'message': _('Profile retired. Its history remains available.')}

    @api.model
    def studio_set_owner(self, workspace, user_id, role_ids, active, reason):
        self._require_manage()
        reason = self._studio_reason(reason)
        user = self._studio_user(user_id, workspace)
        roles = self._studio_roles(role_ids, workspace)
        Owner = self._studio_store('pb.access.owner')
        row = Owner.with_context(active_test=False).search([('workspace', '=', workspace), ('company_id', '=', self.env.company.id), ('user_id', '=', user.id)])
        vals = {'active': bool(active), 'role_ids': [(6, 0, roles.ids)]}
        if row:
            row.write(vals)
        else:
            Owner.create(dict(vals, workspace=workspace, company_id=self.env.company.id, user_id=user.id))
        self._studio_event(workspace, _('Module access ownership updated'), reason, {'role_ids': roles.ids, 'active': bool(active)}, user)
        return {'message': _('Module ownership and grant ceiling saved.')}

    @api.model
    def studio_restore_policy(self, workspace, event_id, reason):
        event = self._studio_record('pb.access.event', event_id, workspace)
        details = event.details or {}
        if not details.get('role_id') or 'after' not in details:
            raise UserError(_('This event is not a policy version.'))
        role = self._studio_roles([details['role_id']], workspace, definition=True)
        return self.studio_submit_policy(workspace, role.id, role.studio_policy_revision, details['after'], reason)

    def _studio_employee_changes(self, employees, previous):
        # Only published, independently approved department rules run here.
        # Moves remove automatic assignments; manual and extra grants survive.
        for employee in employees.sudo():
            user = employee.user_id
            if not user or user.share:
                continue
            Membership = self._studio_store('pb.access.membership')
            members = Membership.search([('user_id', '=', user.id), ('company_id', '=', employee.company_id.id)])
            for member in members:
                if not employee.active or (member.origin == 'automatic' and member.profile_id.auto_department_id != employee.department_id):
                    member.write({'active': False, 'reason': _('Employee left or moved out of the profile department'), 'revision': member.revision + 1})
                    member._sync_roles()
                    self.with_company(employee.company_id)._studio_event(member.workspace, _('Lifecycle profile assignment ended'), member.reason, {'membership_id': member.id}, user)
                elif previous.get(employee.id) and previous[employee.id] != employee.department_id.id:
                    member.write({'review_date': fields.Date.today(), 'revision': member.revision + 1})
            if not employee.active:
                # Only Studio-owned grants are revoked; the account owner still
                # controls deactivation and independent/native permissions.
                extras = self._studio_store('pb.access.extra').search([('user_id', '=', user.id), ('company_id', '=', employee.company_id.id)])
                extras.write({'active': False})
                extras._sync_roles()
                for extra in extras:
                    self.with_company(employee.company_id)._studio_event(extra.workspace, _('Leaver temporary grant revoked'), _('Employee archived'), {'extra_id': extra.id}, user)
                continue
            profiles = self.env['pb.access.profile'].sudo().search([('company_id', '=', employee.company_id.id), ('auto_department_id', '=', employee.department_id.id)]) if employee.department_id else self.env['pb.access.profile']
            for profile in profiles:
                owner_access = self.with_user(profile.owner_id).with_context(allowed_company_ids=[employee.company_id.id])
                try:
                    owner_access._studio_roles(profile.role_ids.ids, profile.workspace)
                    owner_access._studio_user(user.id, profile.workspace)
                except (AccessError, UserError) as error:
                    self.with_company(employee.company_id)._studio_event(profile.workspace, _('Automatic assignment needs owner review'), str(error), {'profile_id': profile.id}, user)
                    continue
                conflicts = self._studio_conflicts(user, profile.role_ids)
                if conflicts:
                    self.with_company(employee.company_id)._studio_event(profile.workspace, _('Automatic assignment blocked by conflict'), '; '.join(conflicts), {'profile_id': profile.id}, user)
                    continue
                member = Membership.with_context(active_test=False).search([('user_id', '=', user.id), ('profile_id', '=', profile.id)])
                if member:
                    # Never resurrect an explicit revocation on a routine edit.
                    continue
                member = Membership.create({'user_id': user.id, 'profile_id': profile.id, 'origin': 'automatic',
                    'reason': _('Approved department assignment rule'), 'review_date': fields.Date.today() + timedelta(days=90)})
                member._sync_roles()
                self.with_company(employee.company_id)._studio_event(profile.workspace, _('Department profile assigned'), member.reason, {'profile_id': profile.id}, user)

    @api.model
    def _studio_expire(self):
        for model in ('pb.access.membership', 'pb.access.extra'):
            records = self._studio_store(model).search([('active', '=', True), ('date_end', '<', fields.Date.today())])
            for record in records:
                record.write({'active': False})
                record._sync_roles()
                self.with_company(record.company_id)._studio_event(record.workspace, _('Time-limited access expired'), _('The approved end date passed.'), {'model': model, 'id': record.id}, record.user_id)
        return True

    @api.model
    def _studio_sync_navigation(self):
        """Idempotent module-local doors, all pointing at the same catalogue."""
        parents = {'hiring': ['pb_hiring.item_hiring'], 'people': ['pb_sidebar.item_employees'],
                   'payroll': ['pb_sidebar.item_run_payroll']}
        Data = self.env['ir.model.data'].sudo()
        for workspace, names in parents.items():
            parent = next((self.env.ref(n, raise_if_not_found=False) for n in names if self.env.ref(n, raise_if_not_found=False)), None)
            if not parent:
                continue
            action_key = 'action_studio_' + workspace
            action = self.env.ref('biz_access.' + action_key, raise_if_not_found=False)
            if not action:
                action = self.env['ir.actions.client'].sudo().create({'name': _('Access & delegation'), 'tag': 'pb_access_board',
                    'context': repr({'pb_access_workspace': workspace})})
                Data.create({'module': 'biz_access', 'name': action_key, 'model': action._name, 'res_id': action.id, 'noupdate': True})
            item_key = 'item_studio_' + workspace
            item = self.env.ref('biz_access.' + item_key, raise_if_not_found=False)
            if not item:
                item = self.env['pb.sidebar.item'].sudo().create({'name': _('%s access & delegation', dict(WORKSPACES)[workspace]), 'section_id': parent.section_id.id,
                    'parent_id': parent.id, 'sequence': 990, 'icon': 'shield', 'action_xmlid': 'biz_access.' + action_key,
                    'groups_id': [(6, 0, self.env.ref('base.group_user').ids)]})
                Data.create({'module': 'biz_access', 'name': item_key, 'model': item._name, 'res_id': item.id, 'noupdate': True})
            elif item.name == _('Access & delegation'):
                item.write({'name': _('%s access & delegation', dict(WORKSPACES)[workspace])})
        return True

    def _roles_of(self, user):
        rows = super()._roles_of(user)
        visible = self.env['pb.role.profile'].visible()
        for source in user.sudo()._pb_access_sources().filtered(lambda s: s.source.startswith(('package:', 'extra:')) and bool(s._groups())):
            role = source.profile_id
            if role not in visible or any(r['profile_id'] == role.id for r in rows):
                continue
            rows.append({'profile_id': role.id, 'name': role.name, 'description': role.description or '',
                'area': role.area, 'area_label': dict(WORKSPACES).get(workspace_of(role), role.area),
                'source': 'held', 'can_take_back': False, 'lent_by': '', 'lent_until': '', 'delegation_id': 0})
        return rows
