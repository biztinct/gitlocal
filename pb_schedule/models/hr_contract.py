# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``hr.contract._pb_hourly_rate()`` — the ONE display-math rate contract.

WHY THIS EXISTS
---------------
The Schedule cockpit has to answer "what does Tuesday cost?", and P1b's audit
found there was no hourly wage anywhere in the dependency chain to answer it
with: ``hr.employee.hourly_cost`` lives in ``hr_hourly_cost``, which is not
installed. The only existing derivation
(``pb_hr_workforce_planning/models/planning_scenario.py`` :644-655) is a COMPANY
AVERAGE with a hardcoded 176 h month and a hardcoded 1.5× overtime factor — a
number that is wrong per-person by construction, and reusing it would have made
the cost column a decoration.

THE CONTRACT (binding — P2 §3.3)
--------------------------------
``rate = wage / (working_days_per_month × working_hours_per_day)``

  * ``wage`` comes from ``_get_contract_wage()`` (``hr_contract/models/
    hr_contract.py`` :247), the documented override point — so a country module
    that pays on a different field (``pb_hr_payroll_*``) is respected for free
    instead of being bypassed by a raw ``contract.wage`` read;
  * the denominators come from the contract's salary structure
    (``hr.payroll.structure.working_hours_per_day`` 8.0 /
    ``working_days_per_month`` 22.0, contributed by ``pb_hr_payroll_base``).
    Both fields are PROBED, not assumed: ``pb_hr_payroll_base`` is not a
    dependency of this module's chain, and on a tenant without it the structure
    simply has no such fields;
  * fallback when the structure path yields nothing: the resource calendar's
    ``hours_per_week × 52 / 12`` as a monthly-hours figure;
  * **0.0, never an exception**, when the wage or both denominators are missing.
    A roster must render for an employee whose contract is half-filled in; the
    strip footnotes how many people had no rate rather than printing a
    confident, wrong total.

IT IS DISPLAY MATH (W12)
------------------------
Nothing here writes, nothing here feeds a payslip, and no salary rule may call
it. It is a READ helper whose only consumer is the Schedule cockpit's cost
strip, which publishes **aggregates only** — a day total and a week total — and
never a per-person rate. Payroll's own money path is untouched by P2.
"""

from odoo import models

# 52 weeks / 12 months — the calendar fallback's week→month conversion. Written
# as a constant so the fallback is auditable next to the primary path rather
# than being an unexplained 4.333 in the middle of a division.
_WEEKS_PER_MONTH = 52.0 / 12.0


class HrContract(models.Model):
    _inherit = 'hr.contract'

    def _pb_hourly_rate(self):
        """Monthly wage → an hourly rate, for DISPLAY only. Never raises.

        :return: float hourly rate in the contract's currency, or 0.0 when the
            wage or the denominators are unavailable.
        """
        self.ensure_one()
        try:
            wage = self._get_contract_wage() or 0.0
        except Exception:                                      # pragma: no cover
            # A country override that needs a context we do not have must not
            # be able to take the roster down with it.
            wage = self.wage or 0.0
        if not wage or wage <= 0:
            return 0.0

        monthly_hours = self._pb_monthly_hours()
        if not monthly_hours or monthly_hours <= 0:
            return 0.0
        return wage / monthly_hours

    def _pb_monthly_hours(self):
        """The denominator: contracted hours in a month. 0.0 when unknowable."""
        self.ensure_one()
        struct = self.struct_id if 'struct_id' in self._fields else False
        if struct:
            fields_ = struct._fields
            days = (struct.working_days_per_month
                    if 'working_days_per_month' in fields_ else 0.0) or 0.0
            hours = (struct.working_hours_per_day
                     if 'working_hours_per_day' in fields_ else 0.0) or 0.0
            if days > 0 and hours > 0:
                return days * hours

        cal = self.resource_calendar_id or self.employee_id.resource_calendar_id
        if cal:
            per_week = cal.hours_per_week or 0.0
            if per_week > 0:
                return per_week * _WEEKS_PER_MONTH
            # hours_per_day alone is not a month; only use it with a day count
            # we actually have, which is what hours_per_week already encodes.
        return 0.0
