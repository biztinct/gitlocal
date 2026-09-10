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
from odoo import api, models

from .blueprint import STEPS


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
