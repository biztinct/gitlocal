"""Role assignments are durable; groups remain the enforcement layer.

Private context tokens are process-local objects, never caller-controlled RPC
flags. A caller cannot turn a normal group write into an internal projection.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from .access_common import ROLE_MEMBERSHIP_XMLIDS, forbidden_in_closure, implied_closure, visible_people

INTERNAL = object()


class RoleAssignment(models.Model):
    _name = 'pb.role.assignment'
    _description = 'Role assignment'
    _order = 'id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    profile_id = fields.Many2one('pb.role.profile', required=True, ondelete='restrict', index=True)
    active = fields.Boolean(default=True, index=True)
    source = fields.Char(required=True, default='role', index=True)
    delegation_id = fields.Many2one('pb.access.delegation', ondelete='restrict')
    snapshot_ids = fields.Many2many('res.groups', 'pb_assignment_snapshot_rel',
                                   'assignment_id', 'group_id')
    origin = fields.Selection([('grant', 'Given on Access'), ('history', 'Existing grant'),
                               ('migration', 'Migrated membership'), ('loan', 'Hand-over')],
                              required=True, default='grant')
    reason = fields.Char()
    _one_source = models.Constraint('unique(user_id, profile_id, source)',
                                    'This source already records that role for this person.')

    def _check_manager(self):
        if not self.env.su and self.env.context.get('_pb_access_internal') is not INTERNAL:
            self.env['pb.access']._require_manage()

    @api.constrains('profile_id', 'snapshot_ids', 'user_id')
    def _check_safe(self):
        for rec in self:
            if rec.user_id.share:
                raise ValidationError(_('Roles require an internal login.'))
            if not rec.profile_id.group_ids or not rec.profile_id.active:
                raise ValidationError(_('Only an active role with abilities can be assigned.'))
            if forbidden_in_closure(rec.profile_id.group_ids | rec.snapshot_ids | rec.profile_id.sudo().membership_group_id, self.env):
                raise ValidationError(_('A role assignment cannot carry the system administrator permission.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        profiles = self.env['pb.role.profile'].browse([v['profile_id'] for v in vals_list]).sorted('id')
        for profile in profiles:
            self.env.cr.execute('SELECT id FROM pb_role_profile WHERE id=%s FOR UPDATE', [profile.id])
            profile.invalidate_recordset()
            profile._ensure_membership_group()
        users = self.env['res.users'].sudo().browse([v['user_id'] for v in vals_list])
        for user in users.sorted('id'):
            self.env.cr.execute('SELECT id FROM res_users WHERE id=%s FOR UPDATE', [user.id])
            user.invalidate_recordset()
        users._pb_initialize_access()
        records = super().create(vals_list)
        if self.env.context.get('_pb_access_internal') is not INTERNAL:
            users._pb_reconcile_access()
        return records

    def write(self, vals):
        self._check_manager()
        if {'user_id', 'profile_id', 'source', 'delegation_id', 'snapshot_ids'} & set(vals):
            if self.env.context.get('_pb_access_internal') is not INTERNAL:
                raise UserError(_('Assignment identity is fixed. Revoke it and give the new role instead.'))
        users = self.user_id
        result = super().write(vals)
        if self.env.context.get('_pb_access_internal') is not INTERNAL:
            users._pb_reconcile_access()
        return result

    def unlink(self):
        raise UserError(_('Assignments are part of the access history. Revoke them instead.'))

    def _groups(self):
        groups = self.env['res.groups'].browse()
        for rec in self.filtered('active'):
            if not rec.profile_id.active:
                continue
            if rec.source == 'role':
                groups |= rec.profile_id.group_ids
            elif rec.delegation_id.state == 'active':
                # Expansions never widen an existing loan; reductions apply now.
                approved = rec.snapshot_ids & implied_closure(rec.profile_id.group_ids)
                roots = approved.filtered(lambda group: not any(
                    group != other and group in other.all_implied_ids for other in approved))
                groups |= rec.profile_id.group_ids if rec.delegation_id.kind == 'permanent' else roots
            groups |= rec.profile_id.membership_group_id
        return groups


class AccessUser(models.Model):
    _inherit = 'res.users'

    pb_access_ready = fields.Boolean(groups='base.group_system', copy=False)
    pb_access_baseline = fields.Json(groups='base.group_system', copy=False)
    pb_access_projected = fields.Json(groups='base.group_system', copy=False)
    pb_access_revision = fields.Integer(default=0, copy=False)

    def _pb_adopt_registered_memberships(self, explicit_ids=None):
        # A signup that explicitly receives the historical Demo group must
        # follow the current role too. Unrelated writes to a borrower do not
        # convert their projected temporary permission into an assignment.
        access = self.env['pb.access'].sudo()
        for xmlid in ROLE_MEMBERSHIP_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group or (explicit_ids is not None and group.id not in explicit_ids):
                continue
            roles = self.env['pb.role.profile'].sudo().search([
                ('group_id', '=', group.id), ('active', '=', True)])
            for user in self.sudo().filtered(lambda u: not u.share and group in u.group_ids):
                for role in roles.filtered('group_ids'):
                    access._assign_role(role, user, _('Assigned from explicit role membership'),
                        origin='migration', adopt=True, adopt_groups=group)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if not self.env.context.get('install_mode') and self.env.context.get('_pb_access_internal') is not INTERNAL:
            users._pb_adopt_registered_memberships()
        return users

    def _pb_initialize_access(self):
        for user in self.sudo():
            if not user.pb_access_ready:
                user.with_context(_pb_access_internal=INTERNAL).write({
                    'pb_access_ready': True,
                    'pb_access_baseline': user.group_ids.ids,
                    'pb_access_projected': [],
                })

    def _pb_access_sources(self):
        self.ensure_one()
        return self.env['pb.role.assignment'].sudo().search([
            ('user_id', '=', self.id), ('active', '=', True)])

    def _pb_desired_groups(self, replace_profile=None, replace_groups=None):
        self.ensure_one()
        Group = self.env['res.groups'].sudo()
        baseline = Group.browse(self.pb_access_baseline or []).exists()
        groups = baseline
        for source in self._pb_access_sources():
            if replace_profile and source.profile_id == replace_profile:
                if source.source == 'role':
                    groups |= replace_groups
                elif source.delegation_id.state == 'active':
                    approved = source.snapshot_ids & implied_closure(replace_groups)
                    roots = approved.filtered(lambda group: not any(
                        group != other and group in other.all_implied_ids for other in approved))
                    groups |= replace_groups if source.delegation_id.kind == 'permanent' else roots
                groups |= source.profile_id.membership_group_id
            else:
                groups |= source._groups()
        return groups

    def _pb_reconcile_access(self):
        """Serialize each user; never remove another source's contribution."""
        for user in self.sudo().sorted('id'):
            self.env.cr.execute('SELECT id FROM res_users WHERE id=%s FOR UPDATE', [user.id])
            user.invalidate_recordset()
            user._pb_initialize_access()
            desired = user._pb_desired_groups()
            before = set(user.group_ids.ids)
            old_owned = set(user.pb_access_projected or [])
            remove = old_owned - set(desired.ids)
            add = set(desired.ids) - before
            vals = {'pb_access_projected': sorted(set(desired.ids) - set(user.pb_access_baseline or [])),
                    'pb_access_revision': user.pb_access_revision + 1}
            if add or remove:
                vals['group_ids'] = [(3, gid) for gid in sorted(remove)] + [(4, gid) for gid in sorted(add)]
            user.with_context(_pb_access_internal=INTERNAL).write(vals)
            if 'bus.bus' in self.env.registry:
                self.env['bus.bus']._sendone(user.partner_id, 'pb_access_changed',
                    {'revision': user.pb_access_revision})

    def write(self, vals):
        internal = self.env.context.get('_pb_access_internal') is INTERNAL
        if not internal and not self.env.su and any(k.startswith('pb_access_') for k in vals):
            raise AccessError(_('Access bookkeeping can only be updated by the role service.'))
        if 'group_ids' in vals and not internal:
            self.check_access('write')
            for user in self.sorted('id'):
                self.env.cr.execute('SELECT id FROM res_users WHERE id=%s FOR UPDATE', [user.id])
            self.invalidate_recordset()
        tracked = self.sudo().filtered('pb_access_ready') if 'group_ids' in vals and not internal else self.browse()
        before = {u.id: set(u.group_ids.ids) for u in tracked}
        result = super().write(vals)
        for user in tracked:
            now = set(user.group_ids.ids)
            added, removed = now - before[user.id], before[user.id] - now
            # Adding a permission already supplied by a loan is still a new,
            # independent direct grant even though membership did not change.
            explicit = set()
            for command in vals.get('group_ids', []):
                if command[0] == 4:
                    explicit.add(command[1])
                elif command[0] == 6:
                    explicit.update(command[2])
            added |= explicit & now
            baseline = (set(user.pb_access_baseline or []) | added) - removed
            # An explicit administrative removal must not be re-added by a role.
            sources = user._pb_access_sources().filtered(
                lambda s: bool(set(implied_closure(s._groups()).ids) & removed))
            sources.with_context(_pb_access_internal=INTERNAL).write({'active': False})
            user.with_context(_pb_access_internal=INTERNAL).write({'pb_access_baseline': sorted(baseline)})
            user._pb_reconcile_access()
        if 'active' in vals and vals['active'] and not internal:
            self.sudo().filtered('pb_access_ready')._pb_reconcile_access()
        if 'group_ids' in vals and not internal and not self.env.context.get('install_mode'):
            explicit_ids = set()
            for command in vals['group_ids']:
                if command[0] == 4: explicit_ids.add(command[1])
                elif command[0] == 6: explicit_ids.update(command[2])
            self._pb_adopt_registered_memberships(explicit_ids)
        return result


class RoleChange(models.Model):
    _name = 'pb.role.change'
    _description = 'Role change history'
    _order = 'id desc'
    profile_id = fields.Many2one('pb.role.profile', required=True, ondelete='restrict')
    revision = fields.Integer(required=True)
    actor_id = fields.Many2one('res.users', required=True)
    reason = fields.Char(required=True)
    before = fields.Json()
    after = fields.Json()
    user_ids = fields.Many2many('res.users', 'pb_role_change_user_rel', 'change_id', 'user_id')

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('_pb_access_internal') is not INTERNAL:
            raise AccessError(_('Role history is written by the role service.'))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_('Role history cannot be changed. Publish a new version instead.'))

    def unlink(self):
        raise UserError(_('Role history cannot be deleted.'))


class ManagedRole(models.Model):
    _inherit = 'pb.role.profile'
    revision = fields.Integer(default=1, readonly=True, copy=False)
    membership_group_id = fields.Many2one('res.groups', readonly=True, copy=False,
                                        ondelete='restrict', groups='base.group_system')
    equivalent_count = fields.Integer(compute='_compute_equivalent_count')
    can_edit_access = fields.Boolean(compute='_compute_can_edit_access')

    def _compute_can_edit_access(self):
        for role in self:
            role.can_edit_access = self.env['pb.access'].can_manage()

    def _ensure_membership_group(self):
        self.ensure_one()
        if not self.sudo().membership_group_id:
            marker = self.env['res.groups'].sudo().create({'name': _('Role assignment — %s', self.id)})
            self.sudo().write({'membership_group_id': marker.id})

    def action_edit_access(self):
        self.ensure_one()
        self.env['pb.access']._require_manage()
        self.check_access('read')
        action = self.env['ir.actions.actions']._for_xml_id('biz_access.action_pb_access_board')
        action['context'] = dict(self.env.context, pb_edit_role=self.id)
        return action

    def _permission_users(self):
        return super()._holder_users()

    def _holder_users(self):
        self.ensure_one()
        sources = self.env['pb.role.assignment'].sudo().with_context(active_test=False).search([
            ('profile_id', '=', self.id), ('active', '=', True)])
        users = sources.filtered(lambda s: s.active and (s.source == 'role' or s.delegation_id.state == 'active')).user_id
        return visible_people(users.filtered('active'), self.env)

    def _compute_equivalent_count(self):
        for role in self:
            role.equivalent_count = len(role._permission_users() - role._holder_users())

    def _access_snapshot(self):
        self.ensure_one()
        return {'name': self.name, 'description': self.description,
                'area': self.area, 'ability_ids': self.ability_ids.ids,
                'abilities': self.ability_ids.mapped('name'), 'group_ids': self.group_ids.ids}

    def write(self, vals):
        if {'revision', 'membership_group_id'} & set(vals) and not self.env.su:
            raise AccessError(_('The role revision is controlled by the role service.'))
        tracked = bool({'ability_ids', 'name', 'description', 'area', 'active', 'group_id'} & set(vals))
        if not tracked:
            return super().write(vals)
        if not self.env.su:
            self.env['pb.access']._require_manage()
        reason = (self.env.context.get('pb_access_reason') or '').strip()
        if 'ability_ids' in vals and not reason and not self.env.su:
            raise UserError(_('Say why this role is changing before saving it.'))
        reason = reason or _('Role updated by administration')
        before = {r.id: r._access_snapshot() for r in self}
        for role in self.sorted('id'):
            self.env.cr.execute('SELECT id FROM pb_role_profile WHERE id=%s FOR UPDATE', [role.id])
            if vals.get('active') is False:
                running = self.env['pb.role.assignment'].sudo().search_count([
                    ('profile_id', '=', role.id), ('active', '=', True)])
                if running:
                    raise UserError(_('Revoke the active assignments and hand-overs before archiving this role.'))
        result = super().write(vals)
        self.flush_recordset(['group_ids'])
        for role in self:
            if not role.group_ids and self.env['pb.role.assignment'].sudo().search_count([
                    ('profile_id', '=', role.id), ('active', '=', True)]):
                raise UserError(_('An assigned role must retain at least one ability.'))
            super(ManagedRole, role).write({'revision': role.revision + 1})
            users = self.env['pb.role.assignment'].sudo().search([
                ('profile_id', '=', role.id), ('active', '=', True)]).user_id
            users._pb_reconcile_access()
            History = self.env['pb.role.change'].sudo().with_context(_pb_access_internal=INTERNAL)
            if not History.search_count([('profile_id', '=', role.id)]):
                History.create({
                    'profile_id': role.id, 'revision': role.revision - 1,
                    'actor_id': role.create_uid.id or self.env.uid,
                    'reason': _('Configuration before the first recorded change'),
                    'before': before[role.id], 'after': before[role.id],
                    'user_ids': [(6, 0, users.ids)],
                })
            History.create({
                'profile_id': role.id, 'revision': role.revision, 'actor_id': self.env.uid,
                'reason': reason, 'before': before[role.id], 'after': role._access_snapshot(),
                'user_ids': [(6, 0, users.ids)],
            })
        return result

    def unlink(self):
        if self.env['pb.role.assignment'].sudo().with_context(active_test=False).search_count([
                ('profile_id', 'in', self.ids)]):
            raise UserError(_('This role has assignment history. Archive it instead.'))
        return super().unlink()


class ManagedAbility(models.Model):
    _inherit = 'pb.role.ability'

    def write(self, vals):
        roles = self.profile_ids if 'group_ids' in vals else self.env['pb.role.profile'].browse()
        # Updating the catalogue cannot silently widen assigned roles.
        if roles and self.env['pb.role.assignment'].sudo().search_count([
                ('profile_id', 'in', roles.ids), ('active', '=', True)]):
            raise UserError(_('This ability is used by assigned roles. Create a new ability and review each role change instead.'))
        return super().write(vals)


class ManagedGroup(models.Model):
    _inherit = 'res.groups'

    def write(self, vals):
        if (self.env.context.get('_pb_access_internal') is INTERNAL
                or self.env.context.get('install_mode')
                or not {'user_ids', 'implied_ids', 'implied_by_ids'} & set(vals)):
            return super().write(vals)
        users = self.all_user_ids.sudo().filtered('pb_access_ready')
        self.check_access('write')
        candidates = set(users.ids)
        for command in vals.get('user_ids', []):
            if command[0] == 4: candidates.add(command[1])
            elif command[0] == 6: candidates.update(command[2])
        for uid in sorted(candidates):
            self.env.cr.execute('SELECT id FROM res_users WHERE id=%s FOR UPDATE', [uid])
        users.invalidate_recordset()
        before = {u.id: set(u.group_ids.ids) for u in users}
        result = super().write(vals)
        if {'implied_ids', 'implied_by_ids'} & set(vals):
            abilities = self.env['pb.role.ability'].sudo().search([])
            if any(forbidden_in_closure(a.group_ids, self.env) for a in abilities):
                raise ValidationError(_('This permission change would give a role system administrator access.'))
            markers = self.env['pb.role.profile'].sudo().search([]).membership_group_id
            if forbidden_in_closure(markers, self.env):
                raise ValidationError(_('Role membership markers cannot carry administrator permissions.'))
            loans = self.env['pb.role.assignment'].sudo().search([
                ('active', '=', True), ('source', '!=', 'role'), ('delegation_id.state', '=', 'active'),
                ('delegation_id.kind', '=', 'temporary')])
            for loan in loans:
                if not set(implied_closure(loan.snapshot_ids).ids) <= set(loan.snapshot_ids.ids):
                    raise UserError(_('An active hand-over uses this permission definition. End or reapprove that hand-over before expanding its implied permissions.'))
            (users | self.all_user_ids.sudo().filtered('pb_access_ready'))._pb_reconcile_access()
        if 'user_ids' in vals:
            users |= self.user_ids.sudo().filtered('pb_access_ready')
            explicitly_added = set()
            for command in vals['user_ids']:
                if command[0] == 4: explicitly_added.add(command[1])
                elif command[0] == 6: explicitly_added.update(command[2])
            for user in users:
                now = set(user.group_ids.ids)
                old = before.get(user.id, now - set(self.ids))
                added, removed = now - old, old - now
                if user.id in explicitly_added: added |= set(self.ids) & now
                base = (set(user.pb_access_baseline or []) | added) - removed
                sources = user._pb_access_sources().filtered(
                    lambda source: bool(set(implied_closure(source._groups()).ids) & removed))
                sources.with_context(_pb_access_internal=INTERNAL).write({'active': False})
                user.with_context(_pb_access_internal=INTERNAL).write({'pb_access_baseline': sorted(base)})
                user._pb_reconcile_access()
        return result
