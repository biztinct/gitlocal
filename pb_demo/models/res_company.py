# -*- coding: utf-8 -*-
"""Group presentation currency + FX-aware consolidation helper.

The architecture review concluded currency must be a property of the legal entity
(company.currency_id, the *functional* currency) while group-level analytics roll
up into a single *presentation* currency. This adds that presentation currency and
a conversion helper that every consolidated dashboard can reuse, so cross-entity
totals (e.g. VND + SGD) are never silently summed in mixed units.
"""
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    presentation_currency_id = fields.Many2one(
        'res.currency', string='Group Presentation Currency',
        help="Currency cross-entity payroll analytics are consolidated into. "
             "Defaults to the parent company's functional currency.")

    @api.model
    def _payroll_presentation_currency(self):
        """Resolve the presentation currency for the active company set."""
        company = self.env.company
        root = company
        while root.parent_id:
            root = root.parent_id
        return root.presentation_currency_id or root.currency_id or company.currency_id

    @api.model
    def convert_to_presentation(self, amount, from_currency, date=None):
        """Convert ``amount`` from ``from_currency`` into the group presentation
        currency using native res.currency rates at ``date`` (period date).
        Returns the amount unchanged when currencies already match."""
        presentation = self._payroll_presentation_currency()
        if not from_currency or not presentation or from_currency == presentation:
            return amount
        date = date or fields.Date.context_today(self)
        return from_currency._convert(
            amount, presentation, self.env.company, date, round=True)
