# -*- coding: utf-8 -*-
"""`pb.pay.settings` — the few decisions a company makes once about pay.

Which guidance a new review opens with, whether people can see their own pay
explained in the portal, above what size a one-off pay change has to go past
finance, and the limits every new review starts with. Four answers, one row per
company, created on first read so nothing in this module ever has to cope with
"there is no settings row yet".
"""

from odoo import _, api, fields, models


class PbPaySettings(models.Model):
    _name = 'pb.pay.settings'
    _description = 'Pay settings'
    _rec_name = 'company_id'
    _order = 'company_id'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        ondelete='cascade', default=lambda self: self.env.company)
    guidance_id = fields.Many2one(
        'pb.pay.guidance', string='Guidance a review opens with',
        ondelete='set null')
    portal_enabled = fields.Boolean(
        string='People can see their own pay explained', default=True,
        help='When this is on, everybody can open "Your pay, explained" and '
             'read what they are paid, where it sits and what last changed. '
             'Never anybody else\'s.')
    change_finance_pct = fields.Float(
        string='A one-off rise this big goes past finance', default=10.0,
        digits=(16, 2))
    limit_ids = fields.One2many(
        'pb.pay.review.limit', 'settings_id',
        string='Limits every review starts with')

    _company_uniq = models.Constraint(
        'unique(company_id)',
        'That company already has its pay settings.')

    @api.model
    def for_company(self, company=None):
        """The row, made if it is not there yet."""
        company = company or self.env.company
        found = self.sudo().search(
            [('company_id', '=', company.id)], limit=1)
        if found:
            return found
        return self.sudo().create({'company_id': company.id})

    def default_limits(self):
        """The limit templates a new review is born with, as write values."""
        self.ensure_one()
        return [(0, 0, {
            'kind': limit.kind, 'value': limit.value,
            'enforcement': limit.enforcement,
            'division_id': limit.division_id.id or False,
        }) for limit in self.limit_ids]

    def summary(self):
        self.ensure_one()
        return {
            'id': self.id,
            'company_id': self.company_id.id,
            'company': self.company_id.display_name,
            'guidance_id': self.guidance_id.id or 0,
            'guidance': self.guidance_id.name or '',
            'portal_enabled': bool(self.portal_enabled),
            'change_finance_pct': float(self.change_finance_pct or 0.0),
            'limits': [limit.summary() for limit in self.limit_ids],
            'portal_note': _('Everybody can open “Your pay, explained”.')
            if self.portal_enabled
            else _('“Your pay, explained” is switched off for this company.'),
        }
