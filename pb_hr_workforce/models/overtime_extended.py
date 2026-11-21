from datetime import date

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ExplicitExtendedOvertime(models.Model):
    _inherit = 'hr.overtime.request'

    overtime_type = fields.Selection(selection_add=[('extended', 'Extended overtime')],
                                     ondelete={'extended': 'set default'})
    policy_approval_reference = fields.Char(string='Employee / manager approval evidence', tracking=True)
    policy_employee_agreed_on = fields.Date(string='Employee agreed on', tracking=True)
    policy_manager_approved_on = fields.Date(string='Manager approved on', tracking=True)
    policy_timesheet_reference = fields.Char(string='Monthly timesheet evidence', tracking=True)

    def _application_policy_errors(self, approving=False):
        self.ensure_one()
        employee = self.employee_id
        policy = employee._pb_policy_for_date(self.date) if hasattr(employee, '_pb_policy_for_date') else False
        if not policy or not policy.overtime_policy_enabled:
            return []
        errors = []
        if (not self.policy_approval_reference or not self.policy_employee_agreed_on
                or not self.policy_manager_approved_on
                or self.policy_employee_agreed_on > self.date or self.policy_manager_approved_on > self.date):
            errors.append('Overtime %s needs prior employee consent and manager approval evidence.' % self.id)
        if not self.policy_timesheet_reference:
            errors.append('Overtime %s needs its monthly timesheet evidence.' % self.id)
        expected = {'weekday': 1.5, 'weekend': 2., 'holiday': 3.}.get(self.overtime_type)
        if expected is None or abs(self.rate_multiplier - expected) > .00001:
            errors.append('Overtime %s needs an explicit policy-compatible payment rate (weekday 150%%, rest day 200%%, holiday 300%%); other categories require policy review.' % self.id)
        # Night premiums can overlap ordinary OT and are not counted twice.
        # Bonus overflow is actual work and must never bypass the policy cap.
        history = self.sudo().search([('employee_id', '=', employee.id),
            ('date', '>=', date(self.date.year, 1, 1)), ('date', '<=', date(self.date.year, 12, 31)),
            ('state', '=', 'approved'), ('id', '!=', self.id), ('overtime_type', '!=', 'night')])
        hours = ((self.actual_hours or self.planned_hours) if approving
                 else self.approved_hours + self.bonus_hours) if self.overtime_type != 'night' else 0.
        annual = hours + sum(history.mapped('total_hours'))
        monthly = hours + sum(history.filtered(lambda r: r.date.month == self.date.month).mapped('total_hours'))
        if monthly > policy.overtime_monthly_limit + .00001:
            errors.append('Overtime exceeds the policy monthly limit of %g hours.' % policy.overtime_monthly_limit)
        if annual > policy.overtime_annual_limit + .00001:
            errors.append('Overtime exceeds the policy annual limit of %g hours.' % policy.overtime_annual_limit)
        return errors

    def _check_extended_configuration(self):
        for request in self.filtered(lambda r: r.overtime_type == 'extended'):
            if not request.overtime_config_id or request.rate_multiplier <= 0:
                raise ValidationError(_('Configure an extended overtime rule and rate for this company before submitting these hours.'))

    def action_submit(self):
        self._check_extended_configuration()
        return super().action_submit()

    def action_approve(self):
        self._check_extended_configuration()
        for request in self.filtered(lambda r: r.state == 'submitted'):
            # Serialize decisions for an employee so simultaneous approvals
            # cannot both observe the same unused annual/monthly allowance.
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                                ['pb.policy.overtime:%s' % request.employee_id.id])
            errors = request._application_policy_errors(approving=True)
            if errors:
                raise ValidationError('\n'.join(errors))
        return super().action_approve()
