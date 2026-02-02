# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class VietnamInsuranceAdjustment(models.Model):
    """
    Vietnam Insurance Adjustment / Arrears
    Manual adjustments for backdated insurance corrections.
    INS04 - Điều chỉnh bảo hiểm
    """
    _name = 'vietnam.insurance.adjustment'
    _description = 'Vietnam Insurance Adjustment'
    
    _order = 'adjustment_date desc, id desc'

    # ==========================================
    # BASIC FIELDS
    # ==========================================
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='employee_id.company_id',
        store=True
    )
    adjustment_date = fields.Date(
        string='Adjustment Date',
        required=True,
        default=fields.Date.today,
        
    )
    period_from = fields.Date(
        string='Period From',
        required=True,
        help="Start of backdated period"
    )
    period_to = fields.Date(
        string='Period To',
        required=True,
        help="End of backdated period"
    )

    # ==========================================
    # ADJUSTMENT TYPE
    # ==========================================
    adjustment_type = fields.Selection([
        ('backdated', 'Backdated Collections (Đóng bổ sung)'),
        ('refund', 'Refund (Hoàn trả)'),
        ('correction', 'Rate Correction (Điều chỉnh mức đóng)'),
        ('late_enrollment', 'Late Enrollment (Đăng ký muộn)'),
    ], string='Adjustment Type', required=True, default='backdated')

    insurance_type = fields.Selection([
        ('si', 'Social Insurance (BHXH)'),
        ('hi', 'Health Insurance (BHYT)'),
        ('ui', 'Unemployment Insurance (BHTN)'),
        ('all', 'All Insurance Types'),
    ], string='Insurance Type', required=True, default='all')

    # ==========================================
    # AMOUNTS
    # ==========================================
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    old_contribution = fields.Monetary(
        string='Previous Contribution',
        currency_field='currency_id',
        help="Original contribution amount"
    )
    new_contribution = fields.Monetary(
        string='Correct Contribution',
        currency_field='currency_id',
        help="Corrected contribution amount"
    )
    difference = fields.Monetary(
        string='Difference',
        currency_field='currency_id',
        compute='_compute_difference',
        store=True
    )
    employer_amount = fields.Monetary(
        string='Employer Adjustment',
        currency_field='currency_id',
        help="Employer portion of adjustment"
    )
    employee_amount = fields.Monetary(
        string='Employee Adjustment',
        currency_field='currency_id',
        help="Employee portion of adjustment"
    )

    # ==========================================
    # REASON & NOTES
    # ==========================================
    reason = fields.Selection([
        ('rate_change', 'Rate Change'),
        ('salary_correction', 'Salary Base Correction'),
        ('late_enrollment', 'Late Enrollment'),
        ('retroactive', 'Retroactive Adjustment'),
        ('system_error', 'System Error Correction'),
        ('other', 'Other'),
    ], string='Reason', required=True)
    notes = fields.Text(string='Notes')

    # ==========================================
    # STATE
    # ==========================================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('applied', 'Applied to Payroll'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True)

    applied_payslip_id = fields.Many2one(
        'hr.payslip',
        string='Applied in Payslip',
        readonly=True
    )

    # ==========================================
    # COMPUTED METHODS
    # ==========================================
    @api.depends('old_contribution', 'new_contribution')
    def _compute_difference(self):
        for adj in self:
            adj.difference = adj.new_contribution - adj.old_contribution

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('vietnam.insurance.adjustment') or _('New')
        return super().create(vals_list)

    # ==========================================
    # STATE ACTIONS
    # ==========================================
    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_apply(self):
        """Mark as applied - manual application to payroll"""
        self.write({'state': 'applied'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
