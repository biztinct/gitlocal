# -*- coding: utf-8 -*-
"""The Vietnam payroll facts that belong to the CONTRACT.

Two of them are not typed at all. "Months on this contract" and "Days of service
this year" are arithmetic on dates the contract already holds, and a number a
person re-derives by hand every month is a number that will eventually be a
month out. They are computed, they are not stored, and nothing writes to them:
`_mapped_record_value` reads a mapped field with `getattr`, so a computed field
answers the payroll exactly as a stored one does.

WHY NOT STORED. A stored compute would need recomputing on every 1 January for
every contract in the database, for a value only the pay run reads. The pay run
reads at most a few thousand contracts and reads each one once.

NOTHING HERE RAISES. These run inside a payroll computation; a contract with no
start date must produce a harmless zero, not an error that stops a pay run.
"""

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from .vn_profile import CONTRACT_FIELDS


_HELP = {name: help_text for name, _t, _l, help_text in CONTRACT_FIELDS}


class HrContract(models.Model):
    _inherit = 'hr.contract'

    # ---- typed -------------------------------------------------------
    pb_vn_hours_per_day = fields.Float(
        string='Hours in a working day', default=8.0, tracking=True,
        help=_HELP['pb_vn_hours_per_day'])
    pb_vn_pay_grade = fields.Integer(
        string='Pay grade', default=1, tracking=True,
        help=_HELP['pb_vn_pay_grade'])
    pb_vn_annual_days = fields.Integer(
        string='Working days in a full year', default=260, tracking=True,
        help=_HELP['pb_vn_annual_days'])

    pb_vn_qual_other_exempt = fields.Boolean(
        string='Other exempt reimbursement — evidence held',
        help=_HELP['pb_vn_qual_other_exempt'])
    pb_vn_qual_leave_encash = fields.Boolean(
        string='Leave encashment — evidence held',
        help=_HELP['pb_vn_qual_leave_encash'])
    pb_vn_qual_transport = fields.Boolean(
        string='Additional transportation — evidence held',
        help=_HELP['pb_vn_qual_transport'])
    pb_vn_qual_ot_weekday = fields.Boolean(
        string='Weekday overtime — exemption evidence held',
        help=_HELP['pb_vn_qual_ot_weekday'])
    pb_vn_qual_ot_weekend = fields.Boolean(
        string='Weekend overtime — exemption evidence held',
        help=_HELP['pb_vn_qual_ot_weekend'])
    pb_vn_qual_ot_holiday = fields.Boolean(
        string='Public-holiday overtime — exemption evidence held',
        help=_HELP['pb_vn_qual_ot_holiday'])
    pb_vn_qual_night = fields.Boolean(
        string='Night work — exemption evidence held',
        help=_HELP['pb_vn_qual_night'])
    pb_vn_variable_bonus = fields.Boolean(
        string='Variable bonus approved', tracking=True,
        help=_HELP['pb_vn_variable_bonus'])

    # ---- derived -----------------------------------------------------
    pb_vn_contract_months = fields.Integer(
        string='Months on this contract', compute='_compute_pb_vn_derived',
        help="Whole months between the contract start and today. Worked out "
             "from the contract, never typed.")
    pb_vn_service_days = fields.Integer(
        string='Days of service this year', compute='_compute_pb_vn_derived',
        help="Working days served since 1 January, capped at a full year. "
             "Worked out from the contract, never typed.")

    @api.depends('date_start', 'date_end', 'pb_vn_annual_days')
    def _compute_pb_vn_derived(self):
        """Both derived values, from the same two dates, in one pass.

        THE REFERENCE DAY IS TODAY, not the pay period. A contract is a fact
        about the world rather than about a run, and the components that read
        these (`CONTRACTMTH` decides whether the short-contract withholding rule
        applies; `SERVDAYS` spreads annual entitlements) ask how long somebody
        has been employed, not how long they had been employed in March.
        """
        today = fields.Date.context_today(self)
        jan = date(today.year, 1, 1)
        year_days = (date(today.year, 12, 31) - jan).days + 1
        for contract in self:
            start = contract.date_start
            end = contract.date_end
            months, served = 0, 0
            if start:
                last = min(end, today) if end else today
                if last >= start:
                    delta = relativedelta(last, start)
                    months = delta.years * 12 + delta.months
                    # Calendar days inside THIS year, scaled onto the working
                    # year the contract declares. Working out the real working
                    # days would mean walking a calendar per contract per run,
                    # for a figure that only ever spreads an annual amount.
                    window_start = max(start, jan)
                    window_end = last
                    if window_end >= window_start:
                        elapsed = (window_end - window_start).days + 1
                        annual = contract.pb_vn_annual_days or 260
                        served = int(round(elapsed * annual / year_days))
            contract.pb_vn_contract_months = months
            contract.pb_vn_service_days = served
