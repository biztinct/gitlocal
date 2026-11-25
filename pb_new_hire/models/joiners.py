# -*- coding: utf-8 -*-
"""NEWHIRE P3b — the New joiners board shows what each new person was asked
(handover §2.6), patched from here: `pb_onboarding`'s files are not edited.

Each row (and the open joiner's drawer) gains `asked`: `{total, done,
waiting, open, items, can_send, can_copy, has_login, act, chip, first}`, or
False when the person was asked nothing. ONE batched read for the whole
page (`pb.new.hire.invite._board`), never one per row. The buttons are the
invite facade's own (`send_again`, `copy_link`), gated there.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PbOnboardingNewHire(models.AbstractModel):
    _inherit = 'pb.onboarding'

    @api.model
    def _nh_asked(self, employee_ids):
        """One card's worth of trouble never blanks the board (its own
        savepoint: the read may write the asks' refreshed state)."""
        try:
            with self.env.cr.savepoint():
                return self.env['pb.new.hire.invite']._board(employee_ids) or {}
        except Exception:                       # noqa: BLE001 — a chip, never the board
            _logger.warning('new hire: the asked chips could not be read', exc_info=True)
            return {}

    @api.model
    def get_joiners_page(self, *args, **kwargs):
        out = super().get_joiners_page(*args, **kwargs)
        rows = out.get('rows') or []
        asked = self._nh_asked([r.get('employee_id') for r in rows if r.get('employee_id')])
        for row in rows:
            row['asked'] = asked.get(row.get('employee_id')) or False
        return out

    @api.model
    def get_joiner(self, case_id):
        detail = super().get_joiner(case_id)
        joiner = detail.get('joiner') or {}
        if joiner.get('employee_id'):
            joiner['asked'] = self._nh_asked([joiner['employee_id']]).get(joiner['employee_id']) or False
        return detail
