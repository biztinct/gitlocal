# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.pb_hr_payroll_formula.models import input_provenance

# OT input code → hr.overtime.request.overtime_type. Codes are underscore-free
# and pairwise non-substring (C5 / C18.2 registry). 'extended' is intentionally
# unmapped this phase — flag in report-back if any config needs it.
OT_INPUT_MAP = {
    'OTHRS150': 'weekday',
    'OTHRS200': 'weekend',
    'OTHRS300': 'holiday',
    'OTHRSNGT': 'night',
}

# Bonus Hours input (Phase K): Σ bonus_hours of APPROVED requests in the slip
# period — the OT overflow beyond the pb.ot.ceiling caps. Underscore-free and
# pairwise non-substring vs every registry code (OTHRS*, TRIPDAYS, PERDIEM) and
# vs demo input codes (BONPROD). Registry (C18.2/C18.55b): OTHRS150 OTHRS200
# OTHRS300 OTHRSNGT · TRIPDAYS PERDIEM · BONHRS. The client authors the bonus
# formula themselves; we only expose the stream.
BONUS_INPUT_CODE = 'BONHRS'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _pb_ot_bridge_feeds(self):
        """True when this payslip takes the month's approved overtime: one in
        a Regular run, or in no run at all — exactly the payslips that took it
        before WDGAP PR-D. A payslip in a Top-up or an Extra run does not
        (`pb_run_kind` comes from pb_payruns, which this module does not
        depend on; without it every run is regular)."""
        run = self.payslip_run_id
        kind = getattr(run, 'pb_run_kind', False) if run else False
        return (kind or 'regular') == 'regular'

    def _get_formula_input_values(self, config, provenance=None):
        """Inject approved overtime hours as formula inputs.

        The base worked-days branch strips only the WD_/HOURS_ prefixes
        (hr_payslip_formula.py:305-306), so our underscore-free OTHRS* codes
        never ride it — we override, call super(), and add ONLY the OT codes
        that this config actually declares as input rules (C18.2). OT hours come
        SOLELY from APPROVED requests (C18.3 — one OT source; never the Zoho path).

        SOURCING S1 — ``provenance`` is accepted and PROPAGATED. This override sits
        above the base producer in the MRO, so a signature that did not take the
        keyword would make the base one unreachable with it: every code this bridge
        adds would be a value with no recorded origin, and the caller would get a
        TypeError before it ever found out. Any future override of this method must
        take and forward the keyword for the same reason.
        """
        values = super()._get_formula_input_values(config, provenance=provenance)
        self.ensure_one()

        input_codes = {r.code for r in config.rule_ids if r.column_type == 'input'}
        wanted = input_codes & set(OT_INPUT_MAP)
        want_bonus = BONUS_INPUT_CODE in input_codes
        if not wanted and not want_bonus:
            return values
        # WDGAP PR-D — approved overtime is paid ONCE a month, in the month's
        # regular run. A Top-up or an Extra run for the same month used to be
        # fed it again (no double-pay guard); it now is not.
        if not self._pb_ot_bridge_feeds():
            return values

        # sudo: payslip access already gates the caller, and the officer
        # record rule on hr.overtime.request is own-records-only — without su
        # a non-manager payroll user would silently compute 0 OT hours for
        # every other employee (review F1, money path).
        Req = self.env['hr.overtime.request'].sudo()
        for code in wanted:
            recs = Req.search([
                ('employee_id', '=', self.employee_id.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('state', '=', 'approved'),
                ('overtime_type', '=', OT_INPUT_MAP[code]),
            ])
            values[code] = sum(r.approved_hours or 0.0 for r in recs)
            if provenance is not None:
                provenance[code] = input_provenance.entry(
                    'employee_field', key=OT_INPUT_MAP[code], via='overtime_request')

        # BONHRS — the Bonus-Hours overflow stream (all types), approved only.
        # Same sudo posture + period windowing as OTHRS* (rail 2: this is a
        # SEPARATE stream — OTHRS* still count only approved_hours within caps).
        if want_bonus:
            recs = Req.search([
                ('employee_id', '=', self.employee_id.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('state', '=', 'approved'),
            ])
            values[BONUS_INPUT_CODE] = sum(r.bonus_hours or 0.0 for r in recs)
            if provenance is not None:
                provenance[BONUS_INPUT_CODE] = input_provenance.entry(
                    'employee_field', key='bonus_hours', via='overtime_request')

        return values
