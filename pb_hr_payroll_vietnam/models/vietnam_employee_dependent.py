# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class VietnamEmployeeDependent(models.Model):
    """
    Vietnam Employee Dependent
    Tracks dependents for tax allowance calculation.
    TAX03 - Quản lý người phụ thuộc
    """
    _name = 'vietnam.employee.dependent'
    _description = 'Vietnam Employee Dependent'
    _order = 'effective_from desc, name'

    # ==========================================
    # BASIC FIELDS
    # ==========================================
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(
        string='Dependent Name',
        required=True
    )
    relationship = fields.Selection([
        ('spouse', 'Spouse (Vợ/Chồng)'),
        ('child', 'Child (Con)'),
        ('parent', 'Parent (Bố/Mẹ)'),
        ('sibling', 'Sibling (Anh/Chị/Em)'),
        ('other', 'Other (Khác)'),
    ], string='Relationship', required=True)
    
    date_of_birth = fields.Date(string='Date of Birth')
    identification_number = fields.Char(
        string='ID/Birth Certificate Number',
        help="Citizen ID or Birth Certificate number"
    )
    tax_registration_number = fields.Char(
        string='Tax Registration Number',
        help="Dependent's personal tax code if available"
    )

    # ==========================================
    # ELIGIBILITY PERIOD
    # ==========================================
    effective_from = fields.Date(
        string='Effective From',
        required=True,
        default=fields.Date.today,
        help="Start date of tax deduction eligibility"
    )
    effective_to = fields.Date(
        string='Effective To',
        help="End date of eligibility (leave empty for ongoing)"
    )
    
    status = fields.Selection([
        ('eligible', 'Eligible (Đủ điều kiện)'),
        ('ineligible', 'Ineligible (Không đủ điều kiện)'),
        ('pending', 'Pending Verification (Chờ xác minh)'),
    ], string='Status', default='eligible', required=True)

    # ==========================================
    # TAX ALLOWANCE
    # ==========================================
    tax_allowance = fields.Float(
        string='Monthly Tax Allowance (VND)',
        default=4400000,
        help="Monthly deduction amount (4,400,000 VND standard)"
    )
    is_currently_eligible = fields.Boolean(
        string='Currently Eligible',
        compute='_compute_currently_eligible',
        store=True
    )

    # ==========================================
    # DOCUMENTS
    # ==========================================
    registration_date = fields.Date(
        string='Registration Date',
        help="Date registered with tax authority"
    )
    notes = fields.Text(string='Notes')

    # ==========================================
    # COMPUTED METHODS
    # ==========================================
    @api.depends('effective_from', 'effective_to', 'status')
    def _compute_currently_eligible(self):
        today = fields.Date.today()
        for dep in self:
            is_in_period = dep.effective_from <= today
            if dep.effective_to:
                is_in_period = is_in_period and today <= dep.effective_to
            dep.is_currently_eligible = is_in_period and dep.status == 'eligible'

    @api.constrains('effective_from', 'effective_to')
    def _check_dates(self):
        for dep in self:
            if dep.effective_to and dep.effective_from > dep.effective_to:
                raise ValidationError(_("Effective From must be before Effective To."))

    @api.constrains('date_of_birth')
    def _check_child_age(self):
        """Warn if child is over 18 (may need additional eligibility proof)"""
        for dep in self:
            if dep.relationship == 'child' and dep.date_of_birth:
                age = relativedelta(fields.Date.today(), dep.date_of_birth).years
                if age >= 18:
                    # Don't raise error, just set to pending if adult child
                    pass  # Could implement notification logic here

    def name_get(self):
        result = []
        for dep in self:
            relationship_label = dict(self._fields['relationship'].selection).get(dep.relationship, '')
            name = f"{dep.name} ({relationship_label})"
            result.append((dep.id, name))
        return result
