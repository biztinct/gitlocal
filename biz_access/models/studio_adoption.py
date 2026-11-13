"""Owner-authorized, explicit adoption of existing access into profiles.

This private maintenance API is not callable over RPC. It never grants a new
native permission, fabricates an independent approval, or runs on upgrade.
"""
from datetime import timedelta
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError
from .access_common import implied_closure, forbidden_in_closure
from .role_assignments import INTERNAL
from .studio_catalogue import workspace_of


class StudioAdoption(models.AbstractModel):
    _inherit = 'pb.access'

    def _studio_adopt_existing(self, key, name, workspace, roles, users, owner, reason):
        if self.env.uid != 1:
            raise AccessError(_('Existing-access adoption requires the maintenance account.'))
        reason = self._studio_reason(reason)
        if not roles or forbidden_in_closure(roles.group_ids, self.env):
            raise UserError(_('Choose safe existing roles.'))
        for role in roles.sorted('id'):
            self.env.cr.execute('SELECT id FROM pb_role_profile WHERE id=%s FOR UPDATE', [role.id])
        roles.invalidate_recordset()
        desired = set(implied_closure(roles.group_ids).ids)
        for user in users:
            if user.share or not user.active or self.env.company not in user.company_ids:
                raise UserError(_('Adoption requires an active internal person in this company.'))
            if not desired <= set(user.all_group_ids.ids):
                raise UserError(_('Adoption cannot grant new permissions to %s.', user.name))
        profile = self.env.ref('biz_access.' + key, raise_if_not_found=False)
        if profile:
            if profile.company_id != self.env.company or profile.workspace != workspace or set(profile.role_ids.ids) != set(roles.ids) or not profile.active:
                raise UserError(_('This profile has changed. Review it before adopting more assignments.'))
        else:
            profile = self._studio_store('pb.access.profile').create({
                'name': name, 'workspace': workspace, 'company_id': self.env.company.id,
                'description': _('Existing responsibilities, organised as a reusable profile. Native company, ownership and sharing rules still apply.'),
                'role_ids': [(6, 0, roles.ids)], 'owner_id': owner.id,
                'review_date': fields.Date.today() + timedelta(days=90)})
            self.env['ir.model.data'].create({'module': 'biz_access', 'name': key,
                'model': profile._name, 'res_id': profile.id, 'noupdate': True})
            self._studio_event(workspace, _('Profile set up from existing access'), reason,
                {'profile_id': profile.id, 'roles': roles.mapped('name'), 'authorization': 'Owner-authorized setup; no independent approval impersonated'})
        for user in users.sorted('id'):
            membership = self._studio_store('pb.access.membership').with_context(active_test=False).search([
                ('profile_id', '=', profile.id), ('user_id', '=', user.id)])
            # A later revocation must never be undone by running setup again.
            if membership:
                continue
            self.env.cr.execute('SELECT id FROM res_users WHERE id=%s FOR UPDATE', [user.id])
            user.invalidate_recordset()
            before = set(user.all_group_ids.ids)
            if not desired <= before:
                raise UserError(_('Existing permissions changed for %s. Review the setup again.', user.name))
            user._pb_initialize_access()
            old = user._pb_access_sources().filtered(lambda a: a.source == 'role' and
                workspace_of(a.profile_id) == workspace and
                set(implied_closure(a.profile_id.group_ids).ids) <= desired)
            transferred = set(user.pb_access_baseline or []) & set(roles.group_ids.ids)
            user.with_context(_pb_access_internal=INTERNAL).write({
                'pb_access_baseline': sorted(set(user.pb_access_baseline or []) - transferred),
                'pb_access_projected': sorted(set(user.pb_access_projected or []) | transferred)})
            membership = self._studio_store('pb.access.membership').create({
                'user_id': user.id, 'profile_id': profile.id, 'reason': reason,
                'review_date': fields.Date.today() + timedelta(days=90)})
            old.with_context(_pb_access_internal=INTERNAL).write({'active': False})
            membership._sync_roles()
            marker_ids = set(self.env['pb.role.profile'].sudo().search([]).membership_group_id.ids)
            if before - marker_ids != set(user.all_group_ids.ids) - marker_ids:
                raise UserError(_('Adoption changed native permissions for %s; transaction cancelled.', user.name))
            self._studio_event(workspace, _('Existing access assigned through profile'), reason,
                {'profile_id': profile.id, 'membership_id': membership.id,
                 'roles': roles.mapped('name'), 'replaced_direct_assignments': old.ids,
                 'native_permissions_unchanged': True}, user)
        return profile
