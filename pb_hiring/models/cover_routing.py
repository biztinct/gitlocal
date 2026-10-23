"""Explicit TA Lead routing and a dated HR fallback, scoped by country."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HiringCoverRule(models.Model):
    _inherit = 'pb.hiring.country.rule'
    ta_lead_id = fields.Many2one('res.users', string='TA Lead for cover approval')
    cover_hr_fallback_id = fields.Many2one('res.users', string='Head of HR fallback')
    ta_absent_from = fields.Date(string='TA Lead absent from')
    ta_absent_until = fields.Date(string='TA Lead absent until')

    @api.constrains('ta_lead_id','cover_hr_fallback_id','ta_absent_from','ta_absent_until','company_id')
    def _check_cover_approvers(self):
        for rule in self:
            for person in rule.ta_lead_id | rule.cover_hr_fallback_id:
                if person.share or rule.company_id not in person.company_ids:
                    raise ValidationError(_('Cover approvers must be internal users of this company.'))
            if bool(rule.ta_absent_from) != bool(rule.ta_absent_until) or (rule.ta_absent_from and rule.ta_absent_until < rule.ta_absent_from):
                raise ValidationError(_('Enter both absence dates in chronological order.'))


class CoverRouting(models.Model):
    _inherit = 'pb.hiring.cover'
    approver_source = fields.Selection(selection_add=[('ta_lead', 'Designated TA Lead'), ('hr_fallback', 'Designated Head of HR fallback')])

    def _resolve_approver(self):
        self.ensure_one()
        employee = self.env['hr.employee'].sudo().search([
            ('user_id', '=', self.recruiter_id.id), ('company_id', '=', self.company_id.id)], limit=1)
        rule = self.env['pb.hiring.country.rule'].sudo().rule_for(self.company_id,
            employee.country_id or self.company_id.country_id)
        today = fields.Date.today()
        lead = rule.ta_lead_id if rule else False
        absent = bool(rule and rule.ta_absent_from and rule.ta_absent_until and rule.ta_absent_from <= today <= rule.ta_absent_until)
        if lead and lead.active and lead.id != self.recruiter_id.id and not absent:
            return lead, 'ta_lead'
        fallback = rule.cover_hr_fallback_id if rule else False
        if fallback and fallback.active and fallback.id != self.recruiter_id.id:
            return fallback, 'hr_fallback'
        return self.env['res.users'].browse(), 'none'

    def action_submit(self):
        for rec in self:
            rec._compute_approver()
            if not rec.approver_user_id:
                raise UserError(_('Set the TA Lead and Head of HR fallback in Hiring rules before submitting cover.'))
        return super().action_submit()

    def _chain_title(self):
        self.ensure_one()
        return _('Cover: %(cover)s for %(recruiter)s — %(approver)s',
            cover=self.cover_user_id.name, recruiter=self.recruiter_id.name, approver=self.approver_user_id.name or _('Approver needed'))
