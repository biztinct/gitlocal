"""Stage policies for scoped manager/panel readers; never grant global access."""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from .privacy_p4 import PART_KEYS, _is_hiring_user


class StageVisibility(models.Model):
    _name = 'pb.hiring.visibility.policy'
    _description = 'Candidate stage visibility'
    _order = 'company_id, stage_id, audience'

    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    stage_id = fields.Many2one('hr.recruitment.stage', required=True, ondelete='cascade')
    audience = fields.Selection([('manager', 'Hiring manager'), ('panel', 'Interview panel'), ('group', 'Named internal group')], required=True)
    group_id = fields.Many2one('res.groups', string='Internal group')
    profile = fields.Boolean(string='Profile')
    cv = fields.Boolean(string='CV')
    portfolio = fields.Boolean(string='Portfolio')
    assignment = fields.Boolean(string='Assignment')
    attachments = fields.Boolean(string='Other attachments')
    answers = fields.Boolean(string='Application answers')
    scorecards = fields.Boolean(string='Completed scorecards')
    expected_pay = fields.Boolean(string='Expected pay')
    active = fields.Boolean(default=True)

    @api.constrains('audience', 'group_id', 'company_id', 'stage_id', 'active')
    def _check_policy(self):
        for rec in self:
            if rec.audience == 'group' and not rec.group_id:
                raise ValidationError(_('Choose an internal group. This policy does not grant access to unrelated candidates.'))
            if rec.group_id and rec.group_id.id in [self.env.ref(x).id for x in ('base.group_public','base.group_portal')]:
                raise ValidationError(_('Public and portal groups cannot receive internal candidate permissions. Agencies keep their restricted portal.'))
            if self.sudo().search_count([('id', '!=', rec.id), ('company_id', '=', rec.company_id.id),
                ('stage_id', '=', rec.stage_id.id), ('audience', '=', rec.audience), ('group_id', '=', rec.group_id.id), ('active', '=', True)]) and rec.active:
                raise ValidationError(_('There is already a policy for that stage and audience.'))

    def _expire_links(self):
        apps = self.env['hr.applicant'].sudo().search([('company_id', 'in', self.company_id.ids)])
        self.env['ir.attachment'].sudo().search([('res_model', '=', 'hr.applicant'), ('res_id', 'in', apps.ids),
            ('access_token', '!=', False)]).write({'access_token': False})

    @api.model_create_multi
    def create(self, values):
        result = super().create(values)
        result._expire_links()
        return result

    def write(self, vals):
        self._expire_links()
        result = super().write(vals)
        self._expire_links()
        return result

    def unlink(self):
        self._expire_links()
        return super().unlink()

    @api.model
    def _parts_for(self, app, user):
        if _is_hiring_user(user) or user.share or app.company_id not in user.company_ids:
            return None
        req = app.pb_requisition_id
        manager_ids = [u.id for u,e,l in req._pb_manager_targets()] if req else []
        panel_ids = self.env['pb.hiring.interview'].sudo().search([
            ('applicant_id', '=', app.id), ('state', 'not in', ('cancelled','rescheduled'))]).panel_employee_ids.user_id.ids
        try:
            req.with_user(user).check_access('read')
            scoped = bool(req)
        except AccessError:
            scoped = False
        policies = self.sudo().search([('company_id', '=', app.company_id.id), ('stage_id', '=', app.stage_id.id)])
        matched = policies.filtered(lambda p:
            (p.audience == 'manager' and user.id in manager_ids) or
            (p.audience == 'panel' and user.id in panel_ids) or
            (p.audience == 'group' and scoped and p.group_id in user.group_ids))
        if not matched:
            return None
        # An explicit policy replaces individual shares at this stage.
        return {key for key in PART_KEYS if any(p[key] for p in matched)} | {'card'}


class PolicyShare(models.Model):
    _inherit = 'pb.hiring.share'

    @api.model
    def parts_for(self, applicant, user=None):
        user = user or self.env.user
        app = self.env['hr.applicant'].sudo().browse(applicant.id if hasattr(applicant, 'id') else int(applicant)).exists()
        if app:
            policy = self.env['pb.hiring.visibility.policy']._parts_for(app, user)
            if policy is not None:
                return policy
        return super().parts_for(applicant, user)


class VisibilityFacade(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _doc_rows(self, app, parts=None, tokenised=False):
        rows = super()._doc_rows(app, parts, tokenised=False)
        if tokenised:
            for row in rows:
                row['url'] = '/hiring/candidate-file/%s' % row['id']
        return rows

    @api.model
    def _applicant(self, applicant_id, for_move=False):
        try:
            return super()._applicant(applicant_id, for_move=for_move)
        except AccessError:
            if for_move:
                raise
            app = self.env['hr.applicant'].sudo().browse(int(applicant_id)).exists()
            if app and self.env['pb.hiring.visibility.policy']._parts_for(app, self.env.user) is not None:
                return app
            raise


class PolicyApplicant(models.Model):
    _inherit = 'hr.applicant'

    def write(self, vals):
        result = super().write(vals)
        if 'stage_id' in vals:
            self.env['ir.attachment'].sudo().search([('res_model', '=', 'hr.applicant'),
                ('res_id', 'in', self.ids), ('access_token', '!=', False)]).write({'access_token': False})
        return result
