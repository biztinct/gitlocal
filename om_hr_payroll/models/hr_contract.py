# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class HrContractAdvantage(models.Model):
    _name = "hr.contract.advantage"
    _description = "Employee's Advantages on Contract"

    contract_id = fields.Many2one("hr.contract")
    advantage_template_id = fields.Many2one(
        "hr.contract.advantage.template", string="Advantage Template"
    )
    advantage_template_code = fields.Char(
        string="Code", related="advantage_template_id.code", readonly=True
    )
    advantage_lower_bound = fields.Float(
        string="Lower Bound", related="advantage_template_id.lower_bound", readonly=True
    )
    advantage_upper_bound = fields.Float(
        string="Upper Bound", related="advantage_template_id.upper_bound", readonly=True
    )
    amount = fields.Float(string="Amount")

    @api.onchange("advantage_template_id")
    def _onchange_advantage_template_id(self):
        for record in self:
            record.amount = record.advantage_template_id.default_value

    @api.constrains("amount")
    def _check_bound_limits(self):
        for record in self:
            #if record.amount and record.amount != 0.00:
            if record.amount and record.amount != 0.00 and not ( record.advantage_upper_bound ==0 and  record.advantage_lower_bound == 0):
                if record.amount > record.advantage_upper_bound:
                    raise ValidationError(
                        _("Component amount can't be greater than upper bound limit for " + record.advantage_template_id.name)
                    )
                elif record.amount < record.advantage_lower_bound:
                    raise ValidationError(
                        _("Component amount can't be less than lower bound limit for " + record.advantage_template_id.name )
                    )

class HrContract(models.Model):
    """
    Employee contract based on the visa, work permits
    allows to configure different Salary structure
    """
    _inherit = ['hr.contract']
    _description = 'Employee Contract'

    struct_id = fields.Many2one('hr.payroll.structure', string='Salary Structure')
    schedule_pay = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi-annually', 'Semi-annually'),
        ('annually', 'Annually'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-weekly'),
        ('bi-monthly', 'Bi-monthly'),
    ], string='Scheduled Pay', index=True, default='monthly',
    help="Defines the frequency of the wage payment.")
    resource_calendar_id = fields.Many2one(required=True, help="Employee's working schedule.")
    dependents = fields.Integer(string= "No of dependents")
    hra = fields.Monetary(string='HRA', help="House rent allowance.")
    travel_allowance = fields.Monetary(string="Travel Allowance", help="Travel allowance")
    da = fields.Monetary(string="DA", help="Dearness allowance")
    meal_allowance = fields.Monetary(string="Meal Allowance", help="Meal allowance")
    medical_allowance = fields.Monetary(string="Medical Allowance", help="Medical allowance")
    other_allowance = fields.Monetary(string="Other Allowance", help="Other allowances")
    type_id = fields.Many2one('hr.contract.type', string="Employee Category",
                              required=True, help="Employee category",
                              default=lambda self: self.env['hr.contract.type'].search([], limit=1))
    advantages_ids = fields.One2many(
        "hr.contract.advantage", "contract_id", string="Contract Components"
    )
    location = fields.Char(string='Location',  help="Location of the employee.")
    tupart = fields.Selection([('YES', 'YES'), ('NO', 'NO')], string='TU Participation',  help="TU Participation.", default='YES')
    shuipart = fields.Selection([('YES', 'YES'), ('NO', 'NO')], string='SHUI Participation',  help="SHUI Participation.", default='YES')
    hirestatus = fields.Selection([('long leave', 'Long Leave'), ('resignee', 'Resignee'), ('new hire', 'New Hire')], string='Hire status',  help="Hire status")
    costcenter = fields.Char(string='Cost center',  help="Cost center of employee.")
    def get_all_structures(self):
        """
        @return: the structures linked to the given contracts, ordered by hierachy (parent=False first,
                 then first level children and so on) and without duplicata
        """
        structures = self.mapped('struct_id')
        if not structures:
            return []
        # YTI TODO return browse records
        return list(set(structures._get_parent_structure().ids))

    def get_attribute(self, code, attribute):
        return self.env['hr.contract.advantage.template'].search([('code', '=', code)], limit=1)[attribute]

    def set_attribute_value(self, code, active):
        for contract in self:
            if active:
                value = self.env['hr.contract.advantage.template'].search([('code', '=', code)], limit=1).default_value
                contract[code] = value
            else:
                contract[code] = 0.0

    #Biztinct
    @api.model
    def create(self, vals):
        #set_trace()
        record = super(HrContract, self).create(vals)
        lines = self.env['hr.contract.advantage.template'].search([])
        for line in lines :
            self.env['hr.contract.advantage'].create({'contract_id': record[0].id, 'advantage_template_id': line.id})
        return record


class HrContractAdvantageTemplate(models.Model):
    _name = 'hr.contract.advantage.template'
    _description = "Employee's Advantage on Contract"

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    lower_bound = fields.Float('Lower Bound', help="Lower bound authorized by the employer for this advantage")
    upper_bound = fields.Float('Upper Bound', help="Upper bound authorized by the employer for this advantage")
    default_value = fields.Float('Default value for this advantage')
