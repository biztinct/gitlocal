# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BFSIKPITarget(models.Model):
    _name = 'bfsi.kpi.target'
    _description = 'BFSI KPI Target'
    _inherit = ['mail.thread']
    _order = 'valid_from desc'

    name = fields.Char(
        string='Target Name',
        compute='_compute_name',
        store=True
    )

    # Target scope - can be at employee, job, or branch level
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        ondelete='cascade',
        index=True,
        help='Specific employee (overrides job and branch targets)'
    )

    job_id = fields.Many2one(
        'hr.job',
        string='Job Position',
        ondelete='cascade',
        index=True,
        help='Role-based target (applies to all employees in this role)'
    )

    branch_id = fields.Many2one(
        'bfsi.branch',
        string='Branch',
        ondelete='cascade',
        index=True,
        help='Branch-level target (applies to all employees in branch)'
    )

    banker_type = fields.Selection([
        ('rm', 'Relationship Manager'),
        ('telesales', 'Telesales Agent'),
        ('field_sales', 'Field Sales Officer'),
        ('loan_officer', 'Loan Officer'),
        ('insurance_advisor', 'Insurance Advisor'),
        ('wealth_manager', 'Wealth Manager')
    ], string='Banker Type', help='Target for specific banker types')

    # Validity period
    valid_from = fields.Date(
        string='Valid From',
        required=True,
        default=fields.Date.today
    )

    valid_to = fields.Date(
        string='Valid To',
        help='Leave empty for no end date'
    )

    period_type = fields.Selection([
        ('daily', 'Daily Target'),
        ('weekly', 'Weekly Target'),
        ('monthly', 'Monthly Target')
    ], string='Period Type', default='daily', required=True)

    # ===================
    # INPUT KPI Targets
    # ===================
    target_dials_per_hour = fields.Float(
        string='Target Dials/Hour',
        digits=(5, 2)
    )

    target_total_dials = fields.Integer(
        string='Target Total Dials'
    )

    target_connects = fields.Integer(
        string='Target Connects'
    )

    target_meetings_scheduled = fields.Integer(
        string='Target Meetings Scheduled'
    )

    target_meetings_conducted = fields.Integer(
        string='Target Meetings Conducted'
    )

    target_calls_made = fields.Integer(
        string='Target Calls Made'
    )

    # ===================
    # BEHAVIOR KPI Targets
    # ===================
    target_script_adherence = fields.Float(
        string='Target Script Adherence %',
        digits=(5, 2),
        default=80.0
    )

    target_objection_handling = fields.Float(
        string='Target Objection Handling Score',
        digits=(5, 2),
        default=75.0
    )

    target_need_analysis = fields.Float(
        string='Target Need Analysis Quality',
        digits=(5, 2),
        default=75.0
    )

    target_product_knowledge = fields.Float(
        string='Target Product Knowledge',
        digits=(5, 2),
        default=80.0
    )

    target_compliance = fields.Float(
        string='Target Compliance Score',
        digits=(5, 2),
        default=95.0
    )

    target_customer_satisfaction = fields.Float(
        string='Target Customer Satisfaction',
        digits=(5, 2),
        default=85.0
    )

    # ===================
    # OUTPUT KPI Targets
    # ===================
    target_conversions = fields.Integer(
        string='Target Conversions'
    )

    target_products_sold = fields.Integer(
        string='Target Products Sold'
    )

    target_appointments_set = fields.Integer(
        string='Target Appointments Set'
    )

    target_leads_generated = fields.Integer(
        string='Target Leads Generated'
    )

    target_proposals_submitted = fields.Integer(
        string='Target Proposals Submitted'
    )

    target_connect_rate = fields.Float(
        string='Target Connect Rate %',
        digits=(5, 2)
    )

    target_conversion_rate = fields.Float(
        string='Target Conversion Rate %',
        digits=(5, 2)
    )

    # ===================
    # OUTCOME KPI Targets
    # ===================
    target_revenue = fields.Monetary(
        string='Target Revenue',
        currency_field='currency_id'
    )

    target_commission = fields.Monetary(
        string='Target Commission',
        currency_field='currency_id'
    )

    target_aum = fields.Monetary(
        string='Target AUM',
        currency_field='currency_id'
    )

    target_loan_amount = fields.Monetary(
        string='Target Loan Amount',
        currency_field='currency_id'
    )

    target_premium = fields.Monetary(
        string='Target Premium',
        currency_field='currency_id'
    )

    # Overall target
    target_overall_score = fields.Float(
        string='Target Overall Score',
        digits=(5, 2),
        default=75.0,
        help='Target overall performance score (0-100)'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    is_active = fields.Boolean(
        string='Is Active',
        compute='_compute_is_active',
        store=True
    )

    priority = fields.Integer(
        string='Priority',
        default=10,
        help='Higher priority targets override lower ones (Employee > Job > Branch > Type)'
    )

    notes = fields.Text(string='Notes')

    @api.depends('employee_id', 'job_id', 'branch_id', 'banker_type', 'period_type', 'valid_from')
    def _compute_name(self):
        for target in self:
            parts = []
            if target.employee_id:
                parts.append(target.employee_id.name)
            if target.job_id:
                parts.append(target.job_id.name)
            if target.branch_id:
                parts.append(target.branch_id.name)
            if target.banker_type:
                parts.append(dict(self._fields['banker_type'].selection).get(target.banker_type))

            period = dict(self._fields['period_type'].selection).get(target.period_type)
            parts.append(f"({period})")

            target.name = ' - '.join(filter(None, parts)) or 'New Target'

    @api.depends('valid_from', 'valid_to')
    def _compute_is_active(self):
        today = fields.Date.today()
        for target in self:
            valid_from_ok = target.valid_from <= today
            valid_to_ok = not target.valid_to or target.valid_to >= today
            target.is_active = valid_from_ok and valid_to_ok

    @api.constrains('employee_id', 'job_id', 'branch_id', 'banker_type')
    def _check_target_scope(self):
        for target in self:
            # At least one scope must be defined
            if not any([target.employee_id, target.job_id, target.branch_id, target.banker_type]):
                raise ValidationError(_(
                    'You must specify at least one target scope: Employee, Job Position, Branch, or Banker Type'
                ))

    @api.model
    def get_target_for_employee(self, employee_id, date=None):
        """Get the most specific applicable target for an employee

        Priority: Employee-specific > Job > Branch > Banker Type
        """
        if not date:
            date = fields.Date.today()

        employee = self.env['hr.employee'].browse(employee_id)

        # Search for targets in priority order
        domain_base = [
            ('valid_from', '<=', date),
            '|', ('valid_to', '=', False), ('valid_to', '>=', date)
        ]

        # 1. Employee-specific target (highest priority)
        target = self.search(
            domain_base + [('employee_id', '=', employee_id)],
            order='valid_from desc, priority desc',
            limit=1
        )
        if target:
            return target

        # 2. Job-based target
        if employee.job_id:
            target = self.search(
                domain_base + [('job_id', '=', employee.job_id.id), ('employee_id', '=', False)],
                order='valid_from desc, priority desc',
                limit=1
            )
            if target:
                return target

        # 3. Branch-based target
        if employee.branch_id:
            target = self.search(
                domain_base + [
                    ('branch_id', '=', employee.branch_id.id),
                    ('employee_id', '=', False),
                    ('job_id', '=', False)
                ],
                order='valid_from desc, priority desc',
                limit=1
            )
            if target:
                return target

        # 4. Banker type-based target
        if employee.banker_type:
            target = self.search(
                domain_base + [
                    ('banker_type', '=', employee.banker_type),
                    ('employee_id', '=', False),
                    ('job_id', '=', False),
                    ('branch_id', '=', False)
                ],
                order='valid_from desc, priority desc',
                limit=1
            )
            if target:
                return target

        return self.browse()  # Return empty recordset if no target found

    def get_target_summary_for_ai(self):
        """Generate a text summary of targets for AI context"""
        self.ensure_one()
        summary = f"""
Target: {self.name}
Period: {dict(self._fields['period_type'].selection).get(self.period_type)}
Valid: {self.valid_from} - {self.valid_to or 'Ongoing'}

INPUT TARGETS:
- Dials/Hour: {self.target_dials_per_hour or 'N/A'}
- Total Dials: {self.target_total_dials or 'N/A'}
- Connects: {self.target_connects or 'N/A'}
- Meetings: {self.target_meetings_conducted or 'N/A'}

BEHAVIOR TARGETS:
- Script Adherence: {self.target_script_adherence or 'N/A'}%
- Objection Handling: {self.target_objection_handling or 'N/A'}/100
- Need Analysis: {self.target_need_analysis or 'N/A'}/100

OUTPUT TARGETS:
- Conversions: {self.target_conversions or 'N/A'}
- Products Sold: {self.target_products_sold or 'N/A'}
- Connect Rate: {self.target_connect_rate or 'N/A'}%
- Conversion Rate: {self.target_conversion_rate or 'N/A'}%

OUTCOME TARGETS:
- Revenue: {self.currency_id.symbol}{self.target_revenue or 0:,.2f}
- Commission: {self.currency_id.symbol}{self.target_commission or 0:,.2f}

OVERALL TARGET SCORE: {self.target_overall_score}/100
"""
        return summary

    def action_duplicate_for_next_period(self):
        """Create a copy of this target for the next period"""
        self.ensure_one()
        new_target = self.copy()

        # Adjust dates based on period type
        from datetime import timedelta
        if self.period_type == 'daily':
            delta = timedelta(days=1)
        elif self.period_type == 'weekly':
            delta = timedelta(weeks=1)
        else:
            delta = timedelta(days=30)

        new_target.valid_from = self.valid_from + delta
        if self.valid_to:
            new_target.valid_to = self.valid_to + delta

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bfsi.kpi.target',
            'res_id': new_target.id,
            'view_mode': 'form',
        }
