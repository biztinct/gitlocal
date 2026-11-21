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

THE MID-MONTH ADVANCE (WDGAP W2-F, F-1 — owner ruling 2026-11-15: "An Extra
run ignores the advance from the file when the month's regular run already
took it, and says so on screen"). The pay data file path adds the month's
mid-month advance to every payslip it makes. For an Extra run the engine now
asks first (`pb_hr_payroll_formula/models/advance_once.py`): when another
payslip of the month already carries it, the Extra run feeds 0 and the
payslip records where it was taken (`pb_advance_taken_in_id`). The review
then carries a NOTE, not a flag: "Advance not taken again (already in …)".
Where the Extra run still takes it, it stays flagged: saying why when the
rule could not tell (the month's regular payslip is not worked out yet) or
when a payslip worked out later took it too; with PR-E's words, unchanged,
when nothing else has taken it (the Extra run may be the one to take it).
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
        """What an Extra run's payslip did with the mid-month advance.

        * kept out (another payslip of the month had taken it) — a NOTE, never
          a flag: "Advance not taken again (already in <run>)";
        * taken, and the rule could not tell (the regular payslip of the month
          is not worked out yet) — FLAGGED, saying why;
        * taken, and a payslip of the month worked out AFTER it took it too —
          FLAGGED: it is taken twice;
        * taken, nothing else has (the Extra run may be the one that takes
          it), or a scheme the rule cannot read — the PR-E flag, unchanged
          (handover: "behaviour is unchanged").

        A flag appends to a reason already there (" · "), the way every other
        module adds to the one shared answer (ledger PRM-1); a note appends to
        a note the same way."""
        if not out or 'pb_run_kind' not in self._fields \
                or (self.pb_run_kind or 'regular') != 'extra':
            return out
        slips = self.env['hr.payslip'].sudo().browse(list(out)).exists()
        if 'formula_input_sources' not in slips._fields:
            return out
        kept_field = 'pb_advance_taken_in_id' in slips._fields
        taking = slips.filtered(lambda s: s.state != 'cancel' and not (
            kept_field and s.pb_advance_taken_in_id) and self._pb_took_advance(s))
        verdicts = self._pb_advance_verdicts_of(taking)
        for slip in slips:
            row = out.get(slip.id)
            if row is None or slip.state == 'cancel':
                continue
            if kept_field and slip.pb_advance_taken_in_id:
                where = self._pb_advance_where(slip.pb_advance_taken_in_id)
                row['advance_kept_out'] = True
                self._pb_add_note(row, _("Advance not taken again (already in %s)", where))
                continue
            if slip not in taking:
                continue
            row['advance'] = True
            verdict = verdicts.get(slip.employee_id.id) or {}
            if verdict.get('verdict') == 'undecided':
                words = _(
                    "Takes the mid-month advance: %s is not worked out yet, so "
                    "it could not be told whether it takes it too",
                    verdict.get('where') or _("the regular payslip"))
            elif verdict.get('verdict') == 'taken':
                # the month's regular payslip was worked out after this one
                # and took it as well
                words = _("Takes the mid-month advance, and %s took it too — it "
                          "is taken twice", verdict.get('where') or '')
            else:
                words = _("This file also takes the mid-month advance; check it has "
                          "not been taken already")
            if row.get('flag'):
                row['reason'] = ' · '.join(
                    r for r in [row.get('reason') or '', words] if r)
            else:
                row.update(flag=True, kind=ADVANCE_FLAG, reason=words)
        return out

    @staticmethod
    def _pb_add_note(row, words):
        row['note'] = ' · '.join(r for r in [row.get('note') or '', words] if r)

    @staticmethod
    def _pb_advance_where(slip):
        """The pay run (else the payslip) that took the advance, by name."""
        slip = slip.sudo()
        return slip.payslip_run_id.name or slip.name or ''

    def _pb_advance_verdicts_of(self, slips):
        """The engine's verdicts for these payslips' people ({} without the
        engine's rule — the old flag then stands)."""
        if not slips or 'formula_config_id' not in slips._fields:
            return {}
        out = {}
        for config in slips.mapped('formula_config_id'):
            if not hasattr(config, '_pb_advance_verdicts'):
                continue
            mine = slips.filtered(lambda s, c=config: s.formula_config_id == c)
            try:
                out.update(config._pb_advance_verdicts(
                    mine.mapped('employee_id'), self.date_start, self.date_end,
                    exclude_run=self))
            except Exception:   # noqa: BLE001 — a review line never breaks a screen
                _logger.exception('pb_payrun_wizard: advance verdict failed on run %s',
                                  self.id)
        return out

    @staticmethod
    def _pb_took_advance(slip):
        """Did the pay data file's carry-over change any of this payslip's
        values? Read from the payslip's own sources (the file path names the
        adjustment that touched a value: ``adj: ['carryover']``). A payslip
        the advance was kept out of (W2-F) did not take it."""
        if 'pb_advance_taken_in_id' in slip._fields and slip.pb_advance_taken_in_id:
            return False
        try:
            sources = json.loads(slip.formula_input_sources or '{}')
        except (TypeError, ValueError):
            return False
        if not isinstance(sources, dict):
            return False
        return any(isinstance(e, dict) and CARRYOVER_ADJ in (e.get('adj') or [])
                   for e in sources.values())
