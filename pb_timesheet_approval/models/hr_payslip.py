# -*- coding: utf-8 -*-
"""Payroll reads the week that was signed off, not the week as it is today.

THE RUNG, AND WHY IT IS HERE AND NOT IN THE BRIDGE. `_get_formula_input_values`
is a chain: the base producer fills what the scheme itself knows, and
`pb_workforce_payroll_bridge` adds the overtime codes from live approved
overtime requests. To ANSWER for those codes instead, this rung has to sit
ABOVE the bridge in the method resolution order — and the only thing that puts
it there is depending on the bridge, which a module inside the bridge cannot do
to itself. So the rung lives in this module. (Handover §A.5 asked for it in the
bridge module; this is the same rung, one module further out, for a reason the
MRO leaves no choice about.)

WHAT IT FILLS

  REGHRS    the worked hours of every approved week in the period
  TOTHRS    those plus the week's overtime
  WORKDAYS  the days with hours in them
  OTHRS150 / OTHRS200 / OTHRS300 / OTHRSNGT  the approved overtime of those
            weeks, by kind, INSTEAD of the live overtime records
  BONHRS    the bonus hours of those weeks

Only the codes the scheme actually declares as inputs are touched (the same
rule the bridge follows), and only when the company has said payroll reads
approved timesheets. With no approved week the code is left exactly as the rung
below it left it — unresolved, with the existing provenance chain saying why —
because inventing a zero would be a payslip that looks computed and is not.
"""

import logging

from odoo import models

from odoo.addons.pb_hr_payroll_formula.models import input_provenance
from odoo.addons.pb_workforce_payroll_bridge.models.hr_payslip import (
    BONUS_INPUT_CODE, OT_INPUT_MAP)

_logger = logging.getLogger(__name__)

#: Input code -> the packet field that answers it. Underscore-free and pairwise
#: non-substring, like every other code in the registry (C18.2): REGHRS TOTHRS
#: WORKDAYS beside OTHRS150 OTHRS200 OTHRS300 OTHRSNGT BONHRS.
HOUR_INPUT_MAP = {
    'REGHRS': 'reg_hours',
    'TOTHRS': 'total_hours',
    'WORKDAYS': 'days_with_hours',
}

#: Which overtime kind each code means, mirrored from the bridge so the two can
#: never drift: this rung REPLACES those values and must agree about what they
#: are.
OT_TYPE_FIELD = {
    'weekday': 'ot_weekday_hours',
    'weekend': 'ot_weekend_hours',
    'holiday': 'ot_holiday_hours',
    'night': 'ot_night_hours',
}

#: How a value that came from an approved week says so. `src` stays
#: `employee_field` — these are the employee's own records rather than anything
#: imported — and `via` is what names WHICH record, exactly as the overtime and
#: business-trip streams already do.
TIMESHEET_VIA = 'timesheet_packet'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_formula_input_values(self, config, provenance=None):
        values = super()._get_formula_input_values(config,
                                                   provenance=provenance)
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.pb_timesheet_payroll:
            return values

        input_codes = {rule.code for rule in config.rule_ids
                       if rule.column_type == 'input'}
        wanted_hours = input_codes & set(HOUR_INPUT_MAP)
        wanted_ot = input_codes & set(OT_INPUT_MAP)
        wants_bonus = BONUS_INPUT_CODE in input_codes
        if not (wanted_hours or wanted_ot or wants_bonus):
            return values

        packets = self.env['pb.timesheet.packet'].approved_in_period(
            self.employee_id.id, self.date_from, self.date_to)
        if not packets:
            # Nothing was approved for this person in this period. Whatever the
            # rung below resolved stays exactly as it is, including its own
            # account of why it is unresolved.
            return values

        key = self._pb_timesheet_key(packets)
        for code in wanted_hours:
            field = HOUR_INPUT_MAP[code]
            values[code] = round(sum(float(p[field] or 0.0)
                                     for p in packets), 2)
            if provenance is not None:
                provenance[code] = input_provenance.entry(
                    'employee_field', key=key, via=TIMESHEET_VIA)
        for code in wanted_ot:
            field = OT_TYPE_FIELD[OT_INPUT_MAP[code]]
            values[code] = round(sum(float(p[field] or 0.0)
                                     for p in packets), 2)
            if provenance is not None:
                provenance[code] = input_provenance.entry(
                    'employee_field', key=key, via=TIMESHEET_VIA)
        if wants_bonus:
            values[BONUS_INPUT_CODE] = round(
                sum(float(p.bonus_hours or 0.0) for p in packets), 2)
            if provenance is not None:
                provenance[BONUS_INPUT_CODE] = input_provenance.entry(
                    'employee_field', key=key, via=TIMESHEET_VIA)
        return values

    def _pb_timesheet_key(self, packets):
        """Which weeks answered, in the words a person reading a chip wants."""
        weeks = sorted(p.week_start for p in packets if p.week_start)
        if not weeks:
            return 'approved timesheet'
        if len(weeks) == 1:
            return 'week of %s' % weeks[0].strftime('%d %b %Y')
        return '%s weeks from %s' % (len(weeks),
                                     weeks[0].strftime('%d %b %Y'))
