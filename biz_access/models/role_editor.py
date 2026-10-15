from odoo import _, api, fields, models
from odoo.exceptions import UserError
from .access_common import ACCESS_SURFACES, ROLE_MEMBERSHIP_XMLIDS, area_label, forbidden_in_closure, implied_closure
from .role_assignments import INTERNAL


class RoleEditor(models.AbstractModel):
    _inherit = 'pb.access'

    def _safe_profile(self, profile_id):
        role = super()._safe_profile(profile_id)
        if not role.active:
            raise UserError(_('This role has been archived. Restore it before assigning or editing it.'))
        return role

    def _assignments(self, role, user=None):
        domain = [('profile_id', '=', role.id), ('source', '=', 'role'), ('active', '=', True)]
        if user:
            domain.append(('user_id', '=', user.id))
        return self.env['pb.role.assignment'].sudo().search(domain)

    def _assign_role(self, role, user, reason='', origin='grant', adopt=False, adopt_groups=None):
        self.env.cr.execute('SELECT id FROM pb_role_profile WHERE id=%s FOR UPDATE', [role.id])
        role.invalidate_recordset()
        role._ensure_membership_group()
        user = user.sudo()
        self.env.cr.execute('SELECT id FROM res_users WHERE id=%s FOR UPDATE', [user.id])
        user._pb_initialize_access()
        Assignment = self.env['pb.role.assignment'].sudo().with_context(_pb_access_internal=INTERNAL)
        row = Assignment.with_context(active_test=False).search([
            ('profile_id', '=', role.id), ('user_id', '=', user.id), ('source', '=', 'role')], limit=1)
        if row and row.active:
            return False
        if adopt:
            # Migration transfers a documented permission source to its role.
            keep = {self.env.ref('base.group_user').id}
            adopted = role.group_ids | (adopt_groups or self.env['res.groups'].browse())
            transferred = set(user.pb_access_baseline or []) & (set(adopted.ids) - keep)
            base = set(user.pb_access_baseline or []) - transferred
            user.with_context(_pb_access_internal=INTERNAL).write({
                'pb_access_baseline': sorted(base),
                'pb_access_projected': sorted(set(user.pb_access_projected or []) | transferred),
            })
        vals = {'active': True, 'reason': reason, 'origin': origin}
        if row:
            row.write(vals)
        else:
            Assignment.create(dict(vals, user_id=user.id, profile_id=role.id, source='role'))
        user._pb_reconcile_access()
        return True

    @api.model
    def grant(self, profile_id, user_id, reason=None):
        self._require_manage()
        role, user = self._safe_profile(profile_id), self._internal_user(user_id)
        before = set(user.sudo().group_ids.ids)
        if not self._assign_role(role, user, reason or _('Given on the roles board')):
            raise UserError(_('%s is already assigned this role.', user.name))
        self.env['pb.access.delegation'].sudo().create({
            'delegator_user_id': self.env.uid, 'delegate_user_id': user.id,
            'profile_ids': [(6, 0, role.ids)], 'kind': 'permanent', 'state': 'active',
            'origin': 'board', 'reason': reason or _('Given on the roles board'),
            'date_start': fields.Date.context_today(self), 'applied_on': fields.Datetime.now(),
            'applied_group_ids': [(6, 0, sorted(set(user.sudo().group_ids.ids) - before - set(role.sudo().membership_group_id.ids)))],
        })
        return {'ok': True, 'message': _('%(who)s is assigned "%(role)s". Future role changes update their access automatically.',
                who=user.name, role=role.name)}

    @api.model
    def grant_many(self, profile_ids, user_id, reason=None):
        self._require_manage()
        user = self._internal_user(user_id)
        roles = [self._safe_profile(pid) for pid in dict.fromkeys(profile_ids or [])]
        changed = [role for role in roles if not self._assignments(role, user)]
        if not changed:
            raise UserError(_('All selected roles are already assigned.'))
        for role in changed:
            self.grant(role.id, user.id, reason)
        return {'ok': True, 'message': _('%s roles assigned. Future edits update this person automatically.', len(changed))}

    @api.model
    def remove(self, profile_id, user_id, reason=None):
        self._require_manage()
        role, user = self._safe_profile(profile_id), self._internal_user(user_id)
        sources = self._assignments(role, user)
        if not sources:
            visible = self.env['pb.role.profile'].visible()
            providers = user.sudo()._pb_access_sources().filtered(lambda source:
                source.source == 'role' and set(role.group_ids.ids) <= set(implied_closure(source._groups()).ids)).profile_id & visible
            raise UserError(_('This person is not assigned "%(role)s". Their equivalent permissions come from %(source)s; review that source instead.',
                role=role.name, source=', '.join(providers.mapped('name')) or _('direct permissions or a hand-over')))
        sources.with_context(_pb_access_internal=INTERNAL).write({'active': False, 'reason': reason or _('Taken away on Access')})
        user.sudo()._pb_reconcile_access()
        kept = set(role.group_ids.ids) <= set(user.sudo().all_group_ids.ids)
        self.env['pb.access.delegation'].sudo().create({
            'delegator_user_id': self.env.uid, 'delegate_user_id': user.id,
            'profile_ids': [(6, 0, role.ids)], 'kind': 'permanent', 'state': 'revoked',
            'origin': 'board_removal', 'reason': reason or _('Taken away on Access'),
            'date_start': fields.Date.context_today(self), 'ended_on': fields.Datetime.now(),
        })
        return {'ok': True, 'message': (_('Role assignment removed. Access they have from another source stays in place.')
                                      if kept else _('Role assignment and its access removed.'))}

    @api.model
    def composer_options(self):
        result = super().composer_options()
        result['surfaces'] = self._surface_rows(self.env['res.groups'].browse())
        return result

    def _surface_rows(self, groups, profile=None):
        held = set(implied_closure(groups).ids)
        rows = []
        Ability = self.env['pb.role.ability'].sudo()
        for definition in ACCESS_SURFACES.values():
            needs = [self.env.ref(xmlid, raise_if_not_found=False) for xmlid in definition.get('groups', [])]
            model = definition.get('model')
            available = bool(needs) and any(needs) and (not model or model in self.env.registry)
            feature = definition.get('feature')
            enabled, reason = True, ''
            if feature and 'pb.tenancy' in self.env.registry:
                enabled, mode, reason = self.env['pb.tenancy'].sudo().feature_state(feature)
            abilities = Ability.search([('technical_key', 'in', definition.get('abilities', [])), ('active', '=', True)])
            exclusive = abilities.filtered(lambda a: a.technical_key in definition.get('exclusive', []))
            allowed = available and bool(held & {g.id for g in needs if g})
            status = 'unavailable' if not available else ('feature_off' if not enabled else ('allowed' if allowed else 'denied'))
            rows.append({'key': definition['key'], 'label': _(definition['label']),
                         'parent': _(definition.get('parent', '')), 'icon': definition.get('icon', 'layers'),
                         'status': status, 'available': available, 'feature_enabled': enabled,
                         'exclusive_ids': exclusive.ids,
                         'reason': reason or (_('Not installed here') if not available else
                             (_('Company feature is switched off') if not enabled else _('Company and record rules still apply'))),
                         'abilities': [{'id': a.id, 'name': a.name, 'description': a.description or ''} for a in abilities]})
        # Installed menu entries and real sidebar children remain the menu's
        # own data. Registered surfaces add the tabs inside those entries.
        catalog = Ability.search([('active', '=', True)])
        for item in self.env['pb.sidebar.item'].sudo().search([('active', '=', True)], order='section_id, sequence, id'):
            roots = set(item.groups_id.ids)
            # One ability can satisfy a one-ability role gate. A capability
            # inside an administrator bundle does not, by itself, open every
            # menu that bundle opens.
            candidate_ids = set(item.role_ids.filtered(lambda r: len(r.ability_ids) == 1).ability_ids.ids)
            for ability in catalog:
                if roots & set(implied_closure(ability.group_ids).ids):
                    candidate_ids.add(ability.id)
            candidates = catalog.filtered(lambda a: a.id in candidate_ids)
            on, locked = item._state_for(item, False, self.env['res.groups'].browse(sorted(held)))
            enabled, reason = True, _('Menu entry; the screens inside also require their own abilities')
            feature = item.feature_key if 'feature_key' in item._fields else ''
            if feature and 'pb.tenancy' in self.env.registry:
                enabled, mode, text = self.env['pb.tenancy'].sudo().feature_state(feature)
                if not enabled: reason = text or _('Company feature is switched off')
            if profile and profile in item.role_ids and groups:
                on, locked = True, False
            if item.section_id.restricted:
                on, locked = False, True
                reason = _('This menu section is restricted by company configuration')
            rows.append({'key': 'sidebar.%s' % item.id, 'label': item.name,
                'parent': item.parent_id.name or item.section_id.name, 'icon': item.icon,
                'status': 'feature_off' if not enabled else ('allowed' if on and not locked else 'denied'),
                'available': True, 'feature_enabled': enabled, 'reason': reason, 'exclusive_ids': [],
                'always_open': not item.groups_id and not item.role_ids,
                'abilities': [{'id': a.id, 'name': a.name, 'description': a.description or ''} for a in candidates]})
        return rows

    @api.model
    def role_editor(self, profile_id):
        self._require_manage()
        role = self._safe_profile(profile_id)
        return dict(role._access_snapshot(), id=role.id, revision=role.revision,
                    assigned=len(self._assignments(role)), equivalent=role.equivalent_count,
                    options=self.composer_options())

    @api.model
    def screen_detail(self, item_id, user_id=None):
        result = super().screen_detail(item_id, user_id)
        item = self._screen(item_id)
        result.update(parent_id=item.parent_id.id, parent_label=item.parent_id.name or '',
                      customized=item.access_customized)
        return result

    @api.model
    def preview_role_change(self, profile_id, ability_ids):
        self._require_manage()
        role = self._safe_profile(profile_id)
        abilities = self._validated_abilities(ability_ids)
        users = self._assignments(role).user_id
        rows = []
        for user in users.sorted('id')[:100]:
            before = set(user.sudo().all_group_ids.ids)
            after = set(implied_closure(user.sudo()._pb_desired_groups(role, abilities.group_ids)).ids)
            removed = set(implied_closure(role.group_ids).ids) - set(implied_closure(abilities.group_ids).ids)
            rows.append({'id': user.id, 'name': user.name, 'active': user.active,
                         'added': len(after - before), 'removed': len(before - after),
                         'retained': len(removed & after)})
        return {'revision': role.revision, 'assigned': len(users), 'rows': rows,
                'more': max(0, len(users) - len(rows)),
                'adds': (abilities - role.ability_ids).mapped('name'),
                'drops': (role.ability_ids - abilities).mapped('name'),
                'surfaces': self._surface_rows(abilities.group_ids, role),
                'temporary': self.env['pb.role.assignment'].sudo().search_count([
                    ('profile_id', '=', role.id), ('source', '!=', 'role'), ('active', '=', True)])}

    def _validated_abilities(self, ids):
        abilities = self._abilities(ids)
        if set(abilities.ids) != {int(i) for i in ids or []} or not abilities or not all(abilities.mapped('active')):
            raise UserError(_('Choose at least one available ability. An unavailable ability cannot be saved.'))
        if forbidden_in_closure(abilities.group_ids, self.env):
            raise UserError(_('The system administrator permission cannot be carried by a role.'))
        return abilities

    @api.model
    def update_role(self, profile_id, expected_revision, name, description, area, ability_ids, reason):
        self._require_manage()
        role = self._safe_profile(profile_id)
        self.env.cr.execute('SELECT id FROM pb_role_profile WHERE id=%s FOR UPDATE', [role.id])
        role.invalidate_recordset()
        if role.revision != int(expected_revision):
            raise UserError(_('Someone changed this role while you were editing. Reopen it and review the latest version.'))
        if not (name or '').strip() or not (reason or '').strip():
            raise UserError(_('Give the role a name and explain why it is changing.'))
        abilities = self._validated_abilities(ability_ids)
        impact = self.preview_role_change(role.id, ability_ids)
        role.sudo().with_context(pb_access_reason=reason.strip()).write({
            'name': name.strip(), 'description': (description or '').strip(),
            'area': area or self._dominant_area(abilities), 'ability_ids': [(6, 0, abilities.ids)]})
        return {'ok': True, 'id': role.id, 'revision': role.revision,
                'message': _('Role saved. %s assigned users now follow the updated role; access from other sources is retained.', len(self._assignments(role)))}

    @api.model
    def role_change_history(self, profile_id):
        self._require_manage()
        role = self._safe_profile(profile_id)
        changes = self.env['pb.role.change'].sudo().search([('profile_id', '=', role.id)], limit=30)
        return [{'id': r.id, 'revision': r.revision, 'reason': r.reason,
                 'actor': r.actor_id.name, 'date': fields.Datetime.to_string(r.create_date),
                 'users': len(r.user_ids), 'abilities': (r.after or {}).get('abilities', [])} for r in changes]

    @api.model
    def role_version_draft(self, change_id):
        self._require_manage()
        change = self.env['pb.role.change'].sudo().browse(int(change_id)).exists()
        if not change:
            raise UserError(_('That role version is no longer available.'))
        self._safe_profile(change.profile_id.id)
        return change.after or {}

    @api.model
    def restore_role_version(self, change_id, expected_revision, reason):
        self._require_manage()
        change = self.env['pb.role.change'].sudo().browse(int(change_id)).exists()
        if not change:
            raise UserError(_('That role version is no longer available.'))
        snapshot = change.after or {}
        return self.update_role(change.profile_id.id, expected_revision,
            snapshot.get('name'), snapshot.get('description'), snapshot.get('area'), snapshot.get('ability_ids'), reason)

    def _profiles(self, area=None, search=None):
        result = super()._profiles(area, search)
        by_id = {r.id: r for r in self.env['pb.role.profile'].browse([r['id'] for r in result])}
        assigned = set(self.env.user.sudo()._pb_access_sources().profile_id.ids)
        for row in result:
            role = by_id.get(row['id'])
            if role:
                row['equivalent_count'] = role.equivalent_count
                row['i_hold'] = role.id in assigned
        return result

    def _kpis(self, profiles):
        result = super()._kpis(profiles)
        people = set()
        for role in self.env['pb.role.profile'].browse([p['id'] for p in profiles]):
            people.update(role._holder_users().ids)
        result['people'] = len(people)
        return result

    @api.model
    def role_detail(self, profile_id):
        result = super().role_detail(profile_id)
        role = self.env['pb.role.profile'].browse(int(profile_id))
        result['revision'] = role.revision
        result['equivalent_count'] = role.equivalent_count
        result['surfaces'] = self._surface_rows(role.group_ids, role)
        permanent = set(self._assignments(role).user_id.ids)
        for row in result['holders']:
            if row['id'] in permanent:
                row.update(source='held', until='', by='', delegation_id=0)
        return result

    def _roles_of(self, user):
        rows = super()._roles_of(user)
        sources = user.sudo()._pb_access_sources()
        permanent = set(sources.filtered(lambda r: r.source == 'role').profile_id.ids)
        loans = sources.filtered(lambda r: r.source != 'role' and r.delegation_id.state == 'active')
        assigned = permanent | set(loans.profile_id.ids)
        rows = [row for row in rows if row['profile_id'] in assigned]
        present = {row['profile_id'] for row in rows}
        visible = self.env['pb.role.profile'].visible()
        for source in loans:
            role = source.profile_id
            if role.id not in present and role in visible:
                rows.append({'profile_id': role.id, 'name': role.name, 'description': role.description,
                    'area': role.area, 'area_label': area_label(role.area, self.env), 'source': 'lent',
                    'lent_by': source.delegation_id.delegator_user_id.name,
                    'lent_until': fields.Date.to_string(source.delegation_id.date_end) or '',
                    'delegation_id': source.delegation_id.id, 'can_take_back': False})
                present.add(role.id)
        for row in rows:
            if row['profile_id'] in permanent:
                row.update(source='held', can_take_back=self.can_manage())
        return rows

    @api.model
    def passport(self, user_id=None):
        result = super().passport(user_id)
        if result['header'].get('kind') == 'employee':
            # an employee login (TIERS T2) holds nothing to compare
            result['equivalent_roles'] = []
            return result
        user = self._person(user_id)
        assigned = {row['profile_id'] for row in result['roles']}
        matches = super()._roles_of(user)
        result['equivalent_roles'] = [dict(row, source='equivalent', can_take_back=False)
            for row in matches if row['profile_id'] not in assigned]
        return result

    @api.model
    def access_revision(self):
        self._require()
        return self.env.user.sudo().pb_access_revision

    def _migrate_assignments(self, include_memberships=False):
        """Private, idempotent, grants no new permission during migration."""
        history = self.env['pb.access.delegation'].sudo().search([
            ('origin', '=', 'board'), ('state', '=', 'active')])
        for grant in history:
            for role in grant.profile_ids:
                if not role.active:
                    continue
                later_removal = self.env['pb.access.delegation'].sudo().search_count([
                    ('origin', '=', 'board_removal'), ('delegate_user_id', '=', grant.delegate_user_id.id),
                    ('profile_ids', 'in', role.id), ('id', '>', grant.id)])
                if later_removal:
                    continue
                if role.group_ids and set(role.group_ids.ids) <= set(grant.delegate_user_id.all_group_ids.ids):
                    self._assign_role(role, grant.delegate_user_id, _('Migrated existing role grant'), 'history', adopt=True)
        if include_memberships:
            # Only historically explicit memberships approved by the application,
            # never a computed intersection of a bundle's permission groups.
            for xmlid in ROLE_MEMBERSHIP_XMLIDS:
                group = self.env.ref(xmlid, raise_if_not_found=False)
                if not group:
                    continue
                roles = self.env['pb.role.profile'].sudo().search([('group_id', '=', group.id)])
                for role in roles:
                    for user in group.with_context(active_test=False).user_ids.filtered(lambda u: not u.share):
                        self._assign_role(role, user, _('Migrated existing role membership'), 'migration', adopt=True, adopt_groups=group)
        loans = self.env['pb.access.delegation'].sudo().search([
            ('origin', '=', 'delegation'), ('state', '=', 'active')])
        for loan in loans:
            user = loan.delegate_user_id.sudo()
            user._pb_initialize_access()
            Assignment = self.env['pb.role.assignment'].sudo().with_context(_pb_access_internal=INTERNAL)
            if not Assignment.with_context(active_test=False).search_count([('delegation_id', '=', loan.id)]):
                baseline = set(user.pb_access_baseline or []) - set(loan.applied_group_ids.ids)
                user.with_context(_pb_access_internal=INTERNAL).write({'pb_access_baseline': sorted(baseline)})
            for role in loan.profile_ids:
                if not Assignment.with_context(active_test=False).search_count([
                    ('user_id', '=', user.id), ('profile_id', '=', role.id), ('source', '=', 'loan:%s' % loan.id)]):
                    Assignment.create({'user_id': user.id, 'profile_id': role.id, 'delegation_id': loan.id,
                        'source': 'loan:%s' % loan.id, 'snapshot_ids': [(6, 0, implied_closure(role.group_ids).ids)],
                        'origin': 'loan', 'reason': _('Migrated running hand-over')})
            user._pb_reconcile_access()
