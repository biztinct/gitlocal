# -*- coding: utf-8 -*-
"""FLEET P5 — what a customer pays for, and what that buys them.

ONE RECORD, THREE WAYS OF CHARGING. The owner's ruling is that a plan must be
able to charge per active employee, per payslip produced, or one flat monthly
price by company size — selectable per plan, not per platform. So `pricing` is
the switch and `price` / `tier_ids` are the two shapes the number can take.

A PLAN IS ALSO A DOOR LIST. `feature_ids` are the parts of the product the plan
includes, and putting a customer on a plan writes those as `pb.tenant.feature`
rows with source `plan` (P4 reserved that word for exactly this). A row somebody
set by hand keeps `manual` and wins: a plan is what a customer bought, a manual
row is somebody deciding, and deciding beats buying.

PRICES ARE DATA, NOT CODE. The three seeded plans carry the owner's placeholder
numbers and are editable on the Plans tab. Nothing here has an opinion about
what Payobook should cost.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .billing_rules import (
    DEFAULT_TRIAL_DAYS, PRICING, PRICING_LABEL, money, qty_text,
)


class PbPlan(models.Model):
    _name = 'pb.plan'
    _description = 'Payobook plan'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True,
                       help="What this plan is called on the screen and on the "
                            "invoice.")
    code = fields.Char(required=True, index=True,
                       help="Short name, never shown to a customer. Used to "
                            "find the plan from a script.")
    blurb = fields.Char(translate=True,
                        help="One plain sentence: who this plan is for.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    pricing = fields.Selection([(p, PRICING_LABEL[p]) for p in PRICING],
                               default='per_employee', required=True,
                               help="How this plan works out what to charge.")
    price = fields.Float(
        digits=(16, 2),
        help="The price of ONE employee, or of ONE payslip, each month. Not "
             "used by a plan priced by company size.")
    tier_ids = fields.One2many('pb.plan.tier', 'plan_id',
                               help="Only for a plan priced by company size.")
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id,
        help="Every invoice raised from this plan is in this currency.")
    employee_limit = fields.Integer(
        default=0,
        help="How many employees this plan allows. Nought means no limit.")
    vat_pct = fields.Float(
        digits=(16, 2), default=0.0,
        help="Tax added to the invoice, as a percentage. Nought adds nothing "
             "and prints no tax line.")
    trial_days = fields.Integer(
        default=DEFAULT_TRIAL_DAYS,
        help="How long a trial on this plan lasts.")
    feature_ids = fields.Many2many(
        'pb.feature', 'pb_plan_feature_rel', 'plan_id', 'feature_id',
        help="The parts of the product this plan includes. Leave empty and "
             "the customer gets whatever the catalogue's defaults are.")
    tenant_ids = fields.One2many('pb.tenant', 'plan_id')
    tenant_count = fields.Integer(compute='_compute_tenant_count')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'That plan code is already in use.'),
    ]

    @api.depends('tenant_ids.state')
    def _compute_tenant_count(self):
        for plan in self:
            plan.tenant_count = len(plan.tenant_ids.filtered(
                lambda t: t.state != 'decommissioned'))

    @api.constrains('pricing', 'tier_ids')
    def _check_tiers(self):
        for plan in self:
            if plan.pricing == 'flat_tier' and not plan.tier_ids:
                raise ValidationError(_(
                    "The %s plan charges one price by company size, so it "
                    "needs at least one size band.") % plan.name)

    # ------------------------------------------------------------------ rules
    def as_dict(self):
        """One plan as the pure rules read it (rail R6)."""
        self.ensure_one()
        cur = self.currency_id
        return {
            'id': self.id,
            'name': self.name or '',
            'code': self.code or '',
            'blurb': self.blurb or '',
            'pricing': self.pricing,
            'pricing_label': PRICING_LABEL.get(self.pricing, ''),
            'price': self.price or 0.0,
            'tiers': [{'id': t.id, 'up_to': t.up_to, 'price': t.price}
                      for t in self.tier_ids.sorted(lambda t: t.up_to)],
            'currency_id': cur.id,
            'currency': cur.name or '',
            'symbol': cur.symbol or '',
            'position': cur.position or 'after',
            'rounding': cur.rounding or 0.01,
            'employee_limit': self.employee_limit or 0,
            'vat_pct': self.vat_pct or 0.0,
            'trial_days': self.trial_days or DEFAULT_TRIAL_DAYS,
            'features': [{'id': f.id, 'key': f.key, 'name': f.name}
                         for f in self.feature_ids],
            'feature_keys': [f.key for f in self.feature_ids],
            'active': self.active,
            'sequence': self.sequence,
            'tenants': self.tenant_count,
            'headline': self.headline(),
            'limit_text': self.limit_text(),
        }

    def headline(self):
        """"200,000 ₫ per employee, each month" — the price in one line."""
        self.ensure_one()
        cur = self.currency_id
        fmt = lambda v: money(v, cur.symbol or '', cur.rounding or 0.01,   # noqa: E731
                              cur.position or 'after')
        if self.pricing == 'per_employee':
            return _("%s per employee, each month") % fmt(self.price)
        if self.pricing == 'per_payslip':
            return _("%s per payslip produced") % fmt(self.price)
        tiers = self.tier_ids.sorted(lambda t: t.up_to)
        if not tiers:
            return _("No size bands yet")
        return _("From %(low)s a month, by company size",
                 low=fmt(min(tiers.mapped('price') or [0.0])))

    def limit_text(self):
        self.ensure_one()
        if not self.employee_limit:
            return _("No employee limit")
        return _("Up to %s employees") % qty_text(self.employee_limit)

    @api.model
    def catalogue(self):
        """Every plan, newest rules first. Read-only."""
        return [p.as_dict() for p in self.sudo().search([])]


class PbPlanTier(models.Model):
    _name = 'pb.plan.tier'
    _description = 'Payobook plan size band'
    _order = 'up_to, id'

    plan_id = fields.Many2one('pb.plan', required=True, ondelete='cascade',
                              index=True)
    up_to = fields.Integer(
        required=True,
        help="The largest company this band covers, in employees. The band "
             "with the highest number also covers anything bigger.")
    price = fields.Float(digits=(16, 2), required=True,
                         help="What a company in this band pays each month.")
