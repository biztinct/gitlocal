# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PbTripPolicy(models.Model):
    """Per-diem policy resolved by destination (country + optional city tier).

    ``per_diem_channel`` is the double-pay guard (safety rail 1): the per-diem is
    paid through payroll XOR expense, never both — exclusivity decided here and
    honoured by the two bridges.
    """
    _name = 'pb.trip.policy'
    _description = 'Business Trip Per-Diem Policy'
    _order = 'country_id, city_tier, sequence'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    country_id = fields.Many2one(
        'res.country', string='Country',
        help='Leave blank for a global fallback policy.')
    city_tier = fields.Selection([
        ('tier1', 'Tier 1 (major city)'),
        ('tier2', 'Tier 2 (other)'),
    ], string='City Tier')
    per_diem_rate = fields.Monetary(string='Per-Diem Rate / Day')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    per_diem_channel = fields.Selection([
        ('payroll', 'Payroll allowance'),
        ('expense', 'Expense claim'),
    ], string='Per-Diem Channel', default='payroll', required=True,
        help='Where the per-diem is paid. Exclusive — a trip never yields both '
             'a payroll allowance AND an expense claim for the same per-diem.')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)

    @api.model
    def _match(self, country, company, city_tier=False):
        """Best policy for a destination: most-specific first (country + tier),
        then country, then a global fallback. Company-scoped."""
        co_ids = [company.id, False] if company else [False]
        base = [('active', '=', True), ('company_id', 'in', co_ids)]
        candidates = [
            base + [('country_id', '=', country.id if country else False),
                    ('city_tier', '=', city_tier or False)],
            base + [('country_id', '=', country.id if country else False)],
            base + [('country_id', '=', False)],
        ]
        for dom in candidates:
            rec = self.search(dom, order='company_id desc, sequence', limit=1)
            if rec:
                return rec
        return self.browse()


class PbTripExpenseCategory(models.Model):
    """Expense-line category (Meals, Lodging, Transport…). The product mapping
    used to spawn draft ``hr.expense`` records is added by the expense bridge."""
    _name = 'pb.trip.expense.category'
    _description = 'Business Trip Expense Category'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
