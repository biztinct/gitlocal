# -*- coding: utf-8 -*-
"""One extra fact per card on the Payroll configurations screen.

A configuration whose guided setup was never finished is not the same thing as
a configuration somebody built and left alone, and the card has to say so — or
the half-finished draft looks like a broken configuration and somebody deletes
it. The card gains `blueprint`, and the screen turns that into a setup ring and
a "Resume setup" button.

`pb.formula.studio` itself is never edited (13.5k lines, several programmes in
flight): this extends it by inheritance.
"""
import logging

from odoo import api, models

from .blueprint import STEPS

_logger = logging.getLogger(__name__)


class PbFormulaStudioBlueprint(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    @api.model
    def bureau_board(self):
        board = super().bureau_board()
        cards = board.get('cards') or []
        if not cards:
            return board
        ids = [c['id'] for c in cards]
        rows = self.env['pb.formula.blueprint'].search_read(
            [('config_id', 'in', ids), ('state', '=', 'draft')],
            ['config_id', 'step'])
        by_config = {}
        for row in rows:
            step = row.get('step') or 'start'
            try:
                step_no = STEPS.index(step) + 1
            except ValueError:
                step_no = 1
            by_config[row['config_id'][0]] = {
                'id': row['id'],
                'step': step,
                'step_no': step_no,
                'total': len(STEPS),
            }
        for card in cards:
            card['blueprint'] = by_config.get(card['id'], False)
        return board

    # ==================================================================
    # SCHEMECTX P1 — a new configuration starts in the company's country
    # ==================================================================
    @api.model
    def create_config(self, vals):
        """Vietnam stops being the answer for everybody.

        The studio's older create path defaulted `country_code` to 'VN' when
        the caller did not say. On a Singapore or Indian company that is the
        wrong country, and because the country decides the money, it was also
        the wrong currency — the whole of the defect this phase closes.

        The company's own country wins when it is one of the countries this
        product runs payroll for. Anything else, and Vietnam stays the default
        exactly as before: a country the engine has no rules for would be a
        worse answer than a country it has.
        """
        vals = dict(vals or {})
        if not vals.get('country_code'):
            guess = self._pb_default_country_code()
            if guess:
                vals['country_code'] = guess
        return super().create_config(vals)

    @api.model
    def _pb_default_country_code(self):
        """The company's country, if this product pays payroll there."""
        try:
            code = (self.env.company.country_id.code or '').upper()
        except Exception:               # noqa: BLE001 — never block a create
            _logger.warning("Guided setup: could not read the company country")
            return ''
        if not code:
            return ''
        allowed = dict(
            self.env['hr.formula.config']._fields['country_code'].selection)
        return code if code in allowed else ''
