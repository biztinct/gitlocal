# -*- coding: utf-8 -*-
"""RD49 — pull last month's data on a schedule, so payroll never waits for it.

WHY THIS EXISTS. The Zoho pull asks about ONE EMPLOYEE AT A TIME and makes up to
three requests for each (salary, attendance, leave). On the reference tenant
that is 456 sequential HTTP round trips and several minutes of somebody sitting
in front of the Run Payroll wizard watching a spinner — at exactly the moment
they least want to wait.

The owner's call, and the right one: fetch the previous month early, on a
schedule, so the run reads data that is already there. Making the pull itself
faster (asking Zoho for everyone at once instead of person by person) is a
separate, larger change against a live API; this removes the wait either way.

WHAT IT WILL NOT DO:

* **It never computes payroll.** It pulls data into the store and stops. Nobody
  should find a pay run they did not start.
* **It never fails silently.** A connector that errors is logged AND left with
  its own error state; the job continues to the next connector rather than
  taking the whole schedule down with it. A sync that did no work must not look
  like one that did — the standing rule from the ABM session.
* **It skips a connector that is inactive or has no active wires**, because
  pulling data nothing reads is what this change is removing, not adding.
"""
import calendar
import logging
from datetime import date

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HrIntegrationConnector(models.Model):
    _inherit = 'hr.integration.connector'

    #: Opt-in per connector. Off by default: a scheduled job that reaches out to
    #: somebody's HR system is not something to switch on for them.
    cron_pull_enabled = fields.Boolean(
        string="Fetch last month automatically",
        default=False,
        help="Pull the previous month's data early each month, so a pay run "
             "does not have to wait for it.")

    cron_pull_last_run = fields.Datetime(
        string="Last automatic fetch", readonly=True, copy=False)
    cron_pull_last_result = fields.Char(
        string="Last automatic fetch result", readonly=True, copy=False,
        help="What the last scheduled fetch did, or why it could not.")

    @api.model
    def _rd49_previous_month(self, today=None):
        """First and last day of the month before `today`.

        Split out and taking `today` so the boundary cases (January, and a run
        on the 1st) are testable without waiting a year for one.
        """
        today = today or fields.Date.context_today(self)
        year, month = today.year, today.month - 1
        if month == 0:
            year, month = year - 1, 12
        return (date(year, month, 1),
                date(year, month, calendar.monthrange(year, month)[1]))

    @api.model
    def _rd49_next_fifth(self, now=None):
        """The next 5th of a month at 02:00, in UTC.

        ODOO 19 — this is set here rather than in the cron's XML because
        `nextcall` is required and the data file cannot compute a date without
        an eval expression, and an expression there fails the ENTIRE module
        load if anything about it is wrong (the `numbercall` lesson: one bad
        field took every co-upgraded module down). A method can be tested.

        02:00 because the fetch is minutes of sequential HTTP and nobody should
        meet it during the working day.
        """
        now = now or fields.Datetime.now()
        target = now.replace(day=5, hour=2, minute=0, second=0, microsecond=0)
        if target <= now:
            year, month = now.year, now.month + 1
            if month == 13:
                year, month = year + 1, 1
            target = target.replace(year=year, month=month)
        return target

    @api.model
    def _rd49_schedule_first_run(self):
        """Point the schedule at the next 5th, without disturbing a set one.

        Called from the module's post-install hook. It only moves a `nextcall`
        that is still the install-time default, so an owner who has since
        chosen their own time keeps it across every later upgrade.
        """
        cron = self.env.ref(
            'pb_hr_payroll_formula.ir_cron_pull_previous_month',
            raise_if_not_found=False)
        if not cron:
            return False
        target = self._rd49_next_fifth()
        # A `nextcall` in the past (or within the hour) is the default the
        # record was created with; anything else is somebody's decision.
        if not cron.nextcall or cron.nextcall <= fields.Datetime.now():
            cron.sudo().nextcall = target
            _logger.info("RD49: first automatic fetch scheduled for %s", target)
        return True

    @api.model
    def cron_pull_previous_month(self):
        """Fetch the previous month for every connector that opted in."""
        period_from, period_to = self._rd49_previous_month()
        connectors = self.search([('cron_pull_enabled', '=', True),
                                  ('active', '=', True)])
        if not connectors:
            _logger.info("RD49: no connector is set to fetch automatically.")
            return True

        for connector in connectors:
            stamp = {'cron_pull_last_run': fields.Datetime.now()}
            try:
                kinds = connector._mapped_feed_kinds()
                if not kinds:
                    stamp['cron_pull_last_result'] = _(
                        "Skipped — no active field mappings, so there is "
                        "nothing to fetch for.")
                    connector.write(stamp)
                    _logger.warning(
                        "RD49: %s has no active mappings; skipped.",
                        connector.display_name)
                    continue
                # The employee feed is the roster every other feed joins to, so
                # it is always pulled even when no component maps a field from
                # it — without it the rest attaches to nobody.
                data_types = sorted(set(kinds) | {'employee'})
                connector.action_pull_data(
                    data_types=data_types,
                    period_from=period_from,
                    period_to=period_to,
                    triggered_by='cron',
                )
                stamp['cron_pull_last_result'] = _(
                    "Fetched %(kinds)s for %(from)s to %(to)s.",
                    kinds=', '.join(data_types),
                    **{'from': fields.Date.to_string(period_from),
                       'to': fields.Date.to_string(period_to)})
                _logger.info("RD49: %s fetched %s for %s..%s",
                             connector.display_name, data_types,
                             period_from, period_to)
            except Exception as exc:        # noqa: BLE001
                # One connector's outage must not stop the others, and it must
                # not disappear either.
                stamp['cron_pull_last_result'] = _(
                    "Could not fetch: %s") % exc
                _logger.exception(
                    "RD49: automatic fetch failed for %s", connector.display_name)
            connector.write(stamp)
        return True
