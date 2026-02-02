# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VietnamTaxTable(models.Model):
    """
    Vietnam Tax Table Configuration
    Defines progressive income tax slabs at company level.
    TAX01 - Quản lý danh mục thuế
    """
    _name = 'vietnam.tax.table'
    _description = 'Vietnam Tax Table'
    
    _order = 'tax_year desc, name'

    # ==========================================
    # BASIC FIELDS
    # ==========================================
    name = fields.Char(
        string='Tax Table Name',
        required=True,
        help="E.g., 'Vietnam Income Tax 2024'"
    )
    code = fields.Char(
        string='Code',
        required=True,
        
    )
    tax_year = fields.Integer(
        string='Tax Year',
        required=True,
        default=lambda self: fields.Date.today().year,
        
    )
    country_code = fields.Char(
        string='Country Code',
        default='VN',
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Html(string='Notes')

    # ==========================================
    # TAX SLABS
    # ==========================================
    slab_ids = fields.One2many(
        'vietnam.tax.slab',
        'table_id',
        string='Tax Slabs',
        copy=True
    )
    slab_count = fields.Integer(
        string='Number of Slabs',
        compute='_compute_slab_count'
    )

    # ==========================================
    # EXEMPTIONS & DEDUCTIONS
    # ==========================================
    personal_deduction = fields.Float(
        string='Personal Deduction (VND/month)',
        default=11000000,
        help="Monthly personal deduction (11,000,000 VND standard)"
    )
    dependent_deduction = fields.Float(
        string='Dependent Deduction (VND/person/month)',
        default=4400000,
        help="Monthly deduction per dependent (4,400,000 VND standard)"
    )
    insurance_exemption = fields.Boolean(
        string='Insurance Contributions Tax Exempt',
        default=True,
        help="SI/HI/UI contributions are exempt from taxable income"
    )

    # ==========================================
    # TAX COMPONENTS
    # ==========================================
    include_basic_income_tax = fields.Boolean(
        string='Basic Income Tax',
        default=True
    )
    include_defense_fund = fields.Boolean(
        string='Defense Fund Contribution',
        default=True,
        help="Include mandatory defense fund contribution"
    )

    # ==========================================
    # SQL CONSTRAINTS
    # ==========================================
    _sql_constraints = [
        ('code_company_year_uniq', 'unique(code, company_id, tax_year)',
         'Tax table code must be unique per company and year!'),
    ]

    # ==========================================
    # COMPUTED METHODS
    # ==========================================
    @api.depends('slab_ids')
    def _compute_slab_count(self):
        for table in self:
            table.slab_count = len(table.slab_ids)

    def name_get(self):
        result = []
        for table in self:
            name = f"{table.name} ({table.tax_year})"
            result.append((table.id, name))
        return result

    def action_create_default_slabs(self):
        """Create default Vietnam 2024 tax slabs"""
        self.ensure_one()
        self.slab_ids.unlink()
        
        # Vietnam 2024 progressive tax brackets
        slabs = [
            (0, 5000000, 5, 0),
            (5000001, 10000000, 10, 250000),
            (10000001, 18000000, 15, 750000),
            (18000001, 32000000, 20, 1650000),
            (32000001, 52000000, 25, 3250000),
            (52000001, 80000000, 30, 5850000),
            (80000001, 0, 35, 9850000),  # 0 = unlimited
        ]
        
        for seq, (from_amt, to_amt, rate, fixed) in enumerate(slabs, 1):
            self.env['vietnam.tax.slab'].create({
                'table_id': self.id,
                'sequence': seq,
                'income_from': from_amt,
                'income_to': to_amt,
                'tax_rate': rate,
                'fixed_amount': fixed,
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Created %d default tax slabs for Vietnam 2024.') % len(slabs),
                'type': 'success',
            }
        }


class VietnamTaxSlab(models.Model):
    """
    Vietnam Tax Slab - Individual tax bracket
    """
    _name = 'vietnam.tax.slab'
    _description = 'Vietnam Tax Slab'
    _order = 'sequence, income_from'

    table_id = fields.Many2one(
        'vietnam.tax.table',
        string='Tax Table',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    
    income_from = fields.Float(
        string='Income From (VND)',
        required=True,
        help="Taxable income bracket start"
    )
    income_to = fields.Float(
        string='Income To (VND)',
        help="Taxable income bracket end (0 or empty = unlimited)"
    )
    tax_rate = fields.Float(
        string='Tax Rate (%)',
        required=True,
        help="Tax percentage for this bracket"
    )
    fixed_amount = fields.Float(
        string='Fixed Amount (VND)',
        help="Fixed tax amount for income up to previous bracket"
    )
    formula_description = fields.Char(
        string='Formula',
        compute='_compute_formula_description'
    )

    @api.depends('income_from', 'income_to', 'tax_rate', 'fixed_amount')
    def _compute_formula_description(self):
        for slab in self:
            if slab.fixed_amount:
                slab.formula_description = f"{slab.fixed_amount:,.0f} + {slab.tax_rate}% above {slab.income_from:,.0f}"
            else:
                slab.formula_description = f"{slab.tax_rate}%"

    @api.constrains('income_from', 'income_to')
    def _check_income_range(self):
        for slab in self:
            if slab.income_to and slab.income_from > slab.income_to:
                raise ValidationError(_("Income From must be less than Income To."))
