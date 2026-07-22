# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class PbOtCeiling(models.Model):
    """Company-scoped overtime ceiling caps (labour-law budget).

    The Weekly Entry cockpit reads these as CONFIG — no OT-cap constants live in
    code (C18: engine reads config records). VN defaults ship in data:
    40 h/month, 200 h/year, 300 h/year for special-sector employees.
    """
    _name = 'pb.ot.ceiling'
    _description = 'Overtime Ceiling Configuration'
    _order = 'company_id'

    name = fields.Char(string='Name', default='Overtime Ceilings')
    company_id = fields.Many2one(
        'res.company', string='Company',
        help='Leave blank for a global fallback cap set.')
    monthly_cap = fields.Float(string='Monthly OT Cap (h)', default=40.0)
    annual_cap = fields.Float(string='Annual OT Cap (h)', default=200.0)
    annual_cap_special = fields.Float(
        string='Annual OT Cap — Special Sector (h)', default=300.0,
        help='Annual cap applied to employees flagged as special-sector '
             '(higher statutory ceiling).')
    active = fields.Boolean(default=True)

    @api.model
    def _for_company(self, company):
        """Resolve the ceiling config for a company (company-specific first,
        then a global fallback, then a transient default record)."""
        rec = self.search([
            ('active', '=', True),
            '|', ('company_id', '=', company.id), ('company_id', '=', False),
        ], order='company_id desc', limit=1)
        if rec:
            return rec
        # never None: hand back a NewId with the field defaults
        return self.new({})


class HrEmployeeOtSector(models.Model):
    _inherit = 'hr.employee'

    pb_ot_special_sector = fields.Boolean(
        string='Special-Sector OT Ceiling',
        groups='hr.group_hr_user',
        help='When set, this employee is subject to the higher special-sector '
             'annual overtime cap instead of the standard annual cap.')
