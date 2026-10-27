"""Durable Access Studio governance. All mutations go through the facade.

Process-local tokens cannot be supplied through JSON/RPC. Audit events and
submitted snapshots are immutable. A profile is deliberately a new model;
`pb.role.profile` continues to mean an existing role.
"""
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from .role_assignments import INTERNAL
from .studio_catalogue import WORKSPACES

STUDIO = object()


class StudioProtected(models.AbstractModel):
    _name = 'pb.access.studio.protected'
    _description = 'Access Studio protected service storage'

    def _studio_write_allowed(self):
        if self.env.context.get('_pb_studio') is not STUDIO:
            raise AccessError(_('Use Access Studio to review and save this change.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._studio_write_allowed()
        return super().create(vals_list)

    def write(self, vals):
        self._studio_write_allowed()
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Access records are retained. Retire or revoke them instead.'))


class StudioProfile(models.Model):
    _name = 'pb.access.profile'
    _inherit = 'pb.access.studio.protected'
    _description = 'Access profile (bundle of roles)'
    _order = 'workspace, name, id'
    name = fields.Char(required=True)
    description = fields.Text()
    workspace = fields.Selection(WORKSPACES, required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    role_ids = fields.Many2many('pb.role.profile', string='Roles')
    owner_id = fields.Many2one('res.users', required=True)
    review_date = fields.Date(required=True)
    active = fields.Boolean(default=True)
    revision = fields.Integer(default=1)
    auto_department_id = fields.Many2one('hr.department')


class StudioScope(models.Model):
    _name = 'pb.access.owner'
    _inherit = 'pb.access.studio.protected'
    _description = 'Module access owner and grant ceiling'
    user_id = fields.Many2one('res.users', required=True)
    company_id = fields.Many2one('res.company', required=True)
    workspace = fields.Selection(WORKSPACES, required=True)
    role_ids = fields.Many2many('pb.role.profile', string='May assign these roles')
    active = fields.Boolean(default=True)
    _one_owner = models.Constraint('unique(user_id, company_id, workspace)', 'This module owner is already recorded.')


class StudioMembership(models.Model):
    _name = 'pb.access.membership'
    _inherit = 'pb.access.studio.protected'
    _description = 'Profile assignment'
    user_id = fields.Many2one('res.users', required=True, index=True)
    profile_id = fields.Many2one('pb.access.profile', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='profile_id.company_id', store=True, index=True)
    workspace = fields.Selection(related='profile_id.workspace', store=True, index=True)
    active = fields.Boolean(default=True, index=True)
    date_end = fields.Date()
    review_date = fields.Date(required=True)
    origin = fields.Selection([('manual', 'Assigned by owner'), ('automatic', 'Department rule')], default='manual', required=True)
    reason = fields.Text(required=True)
    revision = fields.Integer(default=1)
    _one_profile = models.Constraint('unique(user_id, profile_id)', 'This profile assignment already exists.')

    def _sync_roles(self):
        Assignment = self.env['pb.role.assignment'].sudo().with_context(_pb_access_internal=INTERNAL)
        today = fields.Date.today()
        for membership in self:
            source = 'package:%s' % membership.id
            desired = membership.profile_id.role_ids if membership.active and membership.profile_id.active and (not membership.date_end or membership.date_end >= today) and membership.user_id.active else self.env['pb.role.profile']
            existing = Assignment.with_context(active_test=False).search([('user_id', '=', membership.user_id.id), ('source', '=', source)])
            existing.filtered(lambda a: a.profile_id not in desired).write({'active': False})
            for role in desired:
                row = existing.filtered(lambda a: a.profile_id == role)
                vals = {'active': True, 'reason': membership.reason}
                if row:
                    row.write(vals)
                else:
                    Assignment.create(dict(vals, user_id=membership.user_id.id, profile_id=role.id, source=source))
            membership.user_id.sudo()._pb_reconcile_access()


class StudioRequest(models.Model):
    _name = 'pb.access.studio.request'
    _inherit = 'pb.access.studio.protected'
    _description = 'Reviewed access change'
    _order = 'id desc'
    name = fields.Char(required=True)
    workspace = fields.Selection(WORKSPACES, required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    requested_by = fields.Many2one('res.users', required=True)
    kind = fields.Selection([('profile', 'Profile definition'), ('assign', 'Profile assignment'), ('policy', 'Role policy'), ('extra', 'Temporary role')], required=True)
    payload = fields.Json(required=True)
    impact = fields.Json(required=True)
    reason = fields.Text(required=True)
    state = fields.Selection([('pending', 'Awaiting review'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', required=True)
    decided_by = fields.Many2one('res.users')
    decided_on = fields.Datetime()
    decision_reason = fields.Text()

    def write(self, vals):
        if set(vals) - {'state', 'decided_by', 'decided_on', 'decision_reason'}:
            raise AccessError(_('A submitted change is fixed. Submit a new request instead.'))
        if any(r.state != 'pending' for r in self):
            raise UserError(_('This change has already been decided.'))
        return super().write(vals)


class StudioEvent(models.Model):
    _name = 'pb.access.event'
    _inherit = 'pb.access.studio.protected'
    _description = 'Immutable access event'
    _order = 'id desc'
    name = fields.Char(required=True)
    workspace = fields.Selection(WORKSPACES, required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    actor_id = fields.Many2one('res.users', required=True)
    user_id = fields.Many2one('res.users')
    reason = fields.Text(required=True)
    details = fields.Json()

    def write(self, vals):
        raise UserError(_('Access history cannot be changed.'))


class StudioPolicyRole(models.Model):
    _inherit = 'pb.role.profile'
    studio_policy = fields.Json(copy=False, groups='biz_access.group_access_manager,base.group_system')
    studio_policy_revision = fields.Integer(default=1, copy=False)

    def write(self, vals):
        if {'studio_policy', 'studio_policy_revision'} & set(vals) and self.env.context.get('_pb_studio') is not STUDIO:
            raise AccessError(_('Review policy changes in Access Studio.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any({'studio_policy', 'studio_policy_revision'} & set(v) for v in vals_list) and self.env.context.get('_pb_studio') is not STUDIO:
            raise AccessError(_('Review policy changes in Access Studio.'))
        return super().create(vals_list)


class StudioSource(models.Model):
    _inherit = 'pb.role.assignment'
    def _groups(self):
        packages = self.filtered(lambda a: a.source.startswith('package:'))
        result = super(StudioSource, self - packages)._groups()
        for row in packages.filtered('active'):
            membership = self.env['pb.access.membership'].sudo().browse(int(row.source.split(':')[1])).exists()
            if membership and membership.active and membership.profile_id.active and (not membership.date_end or membership.date_end >= fields.Date.today()) and row.profile_id.active:
                result |= row.profile_id.group_ids | row.profile_id.membership_group_id
        return result


class StudioLifecycle(models.Model):
    _inherit = 'hr.employee'
    def write(self, vals):
        previous = {r.id: r.department_id.id for r in self} if 'department_id' in vals else {}
        result = super().write(vals)
        if not self.env.context.get('install_mode') and {'active', 'department_id', 'user_id'} & set(vals):
            self.env['pb.access']._studio_employee_changes(self, previous)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('install_mode'):
            self.env['pb.access']._studio_employee_changes(records, {})
        return records


class StudioExtra(models.Model):
    _name = 'pb.access.extra'
    _inherit = 'pb.access.studio.protected'
    _description = 'Independent temporary role grant'
    user_id = fields.Many2one('res.users', required=True, index=True)
    role_id = fields.Many2one('pb.role.profile', required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True)
    workspace = fields.Selection(WORKSPACES, required=True, index=True)
    date_end = fields.Date(required=True)
    reason = fields.Text(required=True)
    active = fields.Boolean(default=True)

    def _sync_roles(self):
        Assignment = self.env['pb.role.assignment'].sudo().with_context(_pb_access_internal=INTERNAL)
        for grant in self:
            source = 'extra:%s' % grant.id
            row = Assignment.with_context(active_test=False).search([('user_id', '=', grant.user_id.id), ('source', '=', source)])
            vals = {'active': grant.active and grant.date_end >= fields.Date.today(), 'reason': grant.reason}
            if row:
                row.write(vals)
            else:
                Assignment.create(dict(vals, user_id=grant.user_id.id, profile_id=grant.role_id.id, source=source))
            grant.user_id.sudo()._pb_reconcile_access()


class StudioExtraSource(models.Model):
    _inherit = 'pb.role.assignment'
    def _groups(self):
        extras = self.filtered(lambda a: a.source.startswith('extra:'))
        groups = super(StudioExtraSource, self - extras)._groups()
        for row in extras.filtered('active'):
            grant = self.env['pb.access.extra'].sudo().browse(int(row.source.split(':')[1])).exists()
            if grant and grant.active and grant.date_end >= fields.Date.today() and row.profile_id.active:
                groups |= row.profile_id.group_ids | row.profile_id.membership_group_id
        return groups


class StudioRoleHolders(models.Model):
    _inherit = 'pb.role.profile'
    def _holder_users(self):
        self.ensure_one()
        from .access_common import visible_people
        sources = self.env['pb.role.assignment'].sudo().search([('profile_id', '=', self.id), ('active', '=', True)])
        return visible_people(sources.filtered(lambda s: bool(s._groups())).user_id.filtered('active'), self.env)


class StudioMenuDoor(models.Model):
    _inherit = 'pb.sidebar.item'
    def _state_for(self, item, is_admin, user_groups):
        visible, locked = super()._state_for(item, is_admin, user_groups)
        if (item.action_xmlid or '').startswith('biz_access.action_studio_') and item.parent_id:
            if not item.parent_id.active:
                return False, False
            parent_visible, parent_locked = self._state_for(item.parent_id, is_admin, user_groups)
            return visible and parent_visible, locked or parent_locked
        return visible, locked
