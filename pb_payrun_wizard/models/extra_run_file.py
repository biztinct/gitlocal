# -*- coding: utf-8 -*-
"""WDGAP PR-E (E1) — an Extra run that loads a pay data file keeps only the
people picked.

Owner ruling (2026-11-15): "The file can still be loaded, but the Extra run
keeps only the rows of the people you picked."

WHERE THE PICKS LIVE. `prepare_run` / `create_and_compute` write the picks
they have already checked (`_extra_run_people`) onto the run itself
(`pb_extra_employee_ids`), so the server — not the browser — decides which of
the file's rows the run keeps when `attach_spreadsheet` loads it. A stale tab
or a script cannot widen an Extra run by sending other people.

WHAT HAPPENS TO THE OTHER ROWS. They are taken out of the batch after the
rows are matched to people and BEFORE anything is validated or processed, so
nobody else gets a payslip, no record of anybody else is updated from the
file, and nobody is created from it.

A PICKED PERSON WHO IS NOT IN THE FILE is computed the way a regular run
computes anybody the file leaves out: by the wizard's own compute, from their
contract and records, without the file. They are named before the run is
computed (the pay-data step's check) and again in the run's summary.

THE MID-MONTH ADVANCE. On an end-of-month scheme the pay data file path adds
the month's mid-month advance (`_apply_mid_cycle_carryover`) to every
payslip it makes, whatever the kind of run — so a picked person's extra
payslip takes it off again. Carry-over is not redesigned here (handover); the
payslip is flagged on the run's review instead, with kind ``advance``.
"""
import json
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

#: The review flag's kind for "this extra payslip also took the advance".
ADVANCE_FLAG = 'advance'
#: The name the file path's adjustment gives the advance in a payslip's sources.
CARRYOVER_ADJ = 'carryover'


class HrPayslipRunExtraPicks(models.Model):
    _inherit = 'hr.payslip.run'

    pb_extra_employee_ids = fields.Many2many(
        'hr.employee', 'pb_payslip_run_extra_employee_rel', 'run_id',
        'employee_id', string='People picked for this extra run',
        readonly=True, copy=False,
        help="The people this extra run is for. A pay data file loaded into "
             "the run keeps only their rows.")

    # ------------------------------------------------------------ review
    def pb_review_flags(self, slip_ids=None):
        out = super().pb_review_flags(slip_ids=slip_ids)
        try:
            self._pb_extra_advance_flags(out)
        except Exception:       # noqa: BLE001 — a flag never breaks a screen
            _logger.exception('pb_payrun_wizard: extra-run advance flag failed '
                              'on run %s', self.id)
        return out

    def _pb_extra_advance_flags(self, out):
        """Flag an Extra run's payslip that the pay data file also took the
        mid-month advance off. Appends to a reason already there (" · "), the
        way every other module adds to the one shared answer (ledger PRM-1)."""
        if not out or 'pb_run_kind' not in self._fields \
                or (self.pb_run_kind or 'regular') != 'extra':
            return out
        slips = self.env['hr.payslip'].sudo().browse(list(out)).exists()
        if 'formula_input_sources' not in slips._fields:
            return out
        words = _("This file also takes the mid-month advance; check it has "
                  "not been taken already")
        for slip in slips:
            row = out.get(slip.id)
            if row is None or slip.state == 'cancel' \
                    or not self._pb_took_advance(slip):
                continue
            row['advance'] = True
            if row.get('flag'):
                row['reason'] = ' · '.join(
                    r for r in [row.get('reason') or '', words] if r)
            else:
                row.update(flag=True, kind=ADVANCE_FLAG, reason=words)
        return out

    @staticmethod
    def _pb_took_advance(slip):
        """Did the pay data file's carry-over change any of this payslip's
        values? Read from the payslip's own sources (the file path names the
        adjustment that touched a value: ``adj: ['carryover']``)."""
        try:
            sources = json.loads(slip.formula_input_sources or '{}')
        except (TypeError, ValueError):
            return False
        if not isinstance(sources, dict):
            return False
        return any(isinstance(e, dict) and CARRYOVER_ADJ in (e.get('adj') or [])
                   for e in sources.values())
