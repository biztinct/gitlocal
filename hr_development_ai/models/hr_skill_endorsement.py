# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HRSkillEndorsement(models.Model):
    _name = 'hr.skill.endorsement'
    _description = 'Skill Endorsement'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    employee_skill_id = fields.Many2one(
        'hr.employee.skill',
        string='Employee Skill',
        required=True,
        ondelete='cascade',
        index=True
    )

    employee_id = fields.Many2one(
        related='employee_skill_id.employee_id',
        string='Employee',
        store=True,
        readonly=True
    )

    skill_id = fields.Many2one(
        related='employee_skill_id.skill_id',
        string='Skill',
        store=True,
        readonly=True
    )

    endorser_id = fields.Many2one(
        'hr.employee',
        string='Endorsed By',
        required=True,
        default=lambda self: self.env.user.employee_id,
        ondelete='cascade'
    )

    endorsement_type = fields.Selection([
        ('peer', 'Peer Endorsement'),
        ('manager', 'Manager Endorsement'),
        ('client', 'Client Endorsement'),
        ('mentor', 'Mentor Endorsement')
    ], string='Type', required=True, default='peer')

    proficiency_rating = fields.Selection([
        ('1', 'Beginner'),
        ('2', 'Intermediate'),
        ('3', 'Proficient'),
        ('4', 'Advanced'),
        ('5', 'Expert')
    ], string='Proficiency Rating', required=True)

    comment = fields.Text(string='Comment')

    is_verified = fields.Boolean(
        string='Verified',
        default=False,
        help='Manager has verified this endorsement'
    )

    verified_by_id = fields.Many2one(
        'hr.employee',
        string='Verified By',
        ondelete='set null'
    )

    verified_date = fields.Datetime(string='Verified Date')

    _sql_constraints = [
        ('endorser_employee_skill_uniq', 'unique(endorser_id, employee_skill_id)',
         'You can only endorse a skill once!')
    ]

    @api.constrains('endorser_id', 'employee_id')
    def _check_self_endorsement(self):
        """Prevent self-endorsement"""
        for record in self:
            if record.endorser_id == record.employee_id:
                raise ValidationError(_('You cannot endorse your own skills!'))

    @api.model_create_multi
    def create(self, vals_list):
        """Update employee skill proficiency when endorsement is created"""
        endorsements = super().create(vals_list)

        for endorsement in endorsements:
            # Update employee skill peer endorsement score
            employee_skill = endorsement.employee_skill_id

            # Calculate average from all peer endorsements
            all_endorsements = employee_skill.endorsement_ids.filtered(
                lambda e: e.endorsement_type == 'peer'
            )

            if all_endorsements:
                avg_rating = sum(int(e.proficiency_rating) for e in all_endorsements) / len(all_endorsements)
                employee_skill.peer_endorsement_score = (avg_rating / 5.0) * 100

            # Manager endorsements update manager score
            manager_endorsements = employee_skill.endorsement_ids.filtered(
                lambda e: e.endorsement_type == 'manager'
            )

            if manager_endorsements:
                avg_rating = sum(int(e.proficiency_rating) for e in manager_endorsements) / len(manager_endorsements)
                employee_skill.manager_assessment_score = (avg_rating / 5.0) * 100

            # Recalculate aggregate proficiency
            employee_skill.aggregate_proficiency_score()

        return endorsements

    def action_verify(self):
        """Verify endorsement (manager only)"""
        self.ensure_one()

        current_employee = self.env.user.employee_id
        if not current_employee:
            raise ValidationError(_('You must be an employee to verify endorsements'))

        self.write({
            'is_verified': True,
            'verified_by_id': current_employee.id,
            'verified_date': fields.Datetime.now()
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Endorsement Verified'),
                'message': _('The endorsement has been verified'),
                'type': 'success',
                'sticky': False,
            }
        }
