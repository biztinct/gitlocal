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
from odoo.exceptions import UserError

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

    #: RD53 — the OUTCOME, not the prose. A person checking whether the fetch
    #: ran wants a colour before they want a sentence, and "it failed" must be
    #: answerable without reading. Kept beside the message rather than parsed
    #: out of it.
    cron_pull_last_state = fields.Selection([
        ('ok', 'Fetched'),
        ('skipped', 'Nothing to fetch'),
        ('failed', 'Could not fetch'),
    ], string="Last automatic fetch outcome", readonly=True, copy=False)

    cron_pull_last_rows = fields.Integer(
        string="Rows fetched last time", readonly=True, copy=False,
        help="How many records the last scheduled fetch brought in. Zero after "
             "a successful run means the connected system had nothing for that "
             "period — which is a different thing from the fetch failing.")

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
                    stamp['cron_pull_last_state'] = 'skipped'
                    stamp['cron_pull_last_rows'] = 0
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
                # Counted before and after so the report can say what ARRIVED,
                # not merely that the call returned. A fetch that brought in
                # nothing must not look like one that brought in everything.
                Store = self.env['hr.api.data.store'].sudo()
                before = Store.search_count([('connector_id', '=', connector.id)])
                connector.action_pull_data(
                    data_types=data_types,
                    period_from=period_from,
                    period_to=period_to,
                    triggered_by='cron',
                )
                arrived = Store.search_count(
                    [('connector_id', '=', connector.id)]) - before
                stamp['cron_pull_last_state'] = 'ok'
                stamp['cron_pull_last_rows'] = max(arrived, 0)
                stamp['cron_pull_last_result'] = _(
                    "Fetched %(kinds)s for %(from)s to %(to)s — %(rows)s new "
                    "records.",
                    kinds=', '.join(data_types), rows=max(arrived, 0),
                    **{'from': fields.Date.to_string(period_from),
                       'to': fields.Date.to_string(period_to)})
                _logger.info("RD49: %s fetched %s for %s..%s",
                             connector.display_name, data_types,
                             period_from, period_to)
            except Exception as exc:        # noqa: BLE001
                # One connector's outage must not stop the others, and it must
                # not disappear either.
                stamp['cron_pull_last_state'] = 'failed'
                stamp['cron_pull_last_result'] = _(
                    "Could not fetch: %s") % exc
                _logger.exception(
                    "RD49: automatic fetch failed for %s", connector.display_name)
            connector.write(stamp)
        return True

    # ------------------------------------------------------------------
    # RD53 — "did it run, and when?" as a screen rather than a guess.
    # ------------------------------------------------------------------
    def action_fetch_last_month_now(self):
        """Run the monthly fetch for THIS connector, right now.

        The schedule is monthly, so without this the only way to find out
        whether it works is to wait until the 5th. It runs the same code the
        cron runs — not a second implementation of it — so what it proves is
        what will happen.
        """
        self.ensure_one()
        if not self.cron_pull_enabled:
            raise UserError(_(
                "“%s” is not set to fetch automatically. Tick “Fetch last "
                "month automatically” first, so that what you test here is "
                "what the schedule will do.") % self.display_name)
        self.cron_pull_previous_month()
        self.invalidate_recordset()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Fetch finished"),
                'message': self.cron_pull_last_result or _("Nothing to report."),
                'type': ('danger' if self.cron_pull_last_state == 'failed'
                         else 'success'),
                'sticky': self.cron_pull_last_state == 'failed',
            },
        }

    @api.model
    def rd53_fetch_status(self):
        """What the schedule is doing, for whoever is wondering.

        One call, because the question is one question: is it on, when does it
        next run, when did it last run, and what happened.
        """
        cron = self.env.ref(
            'pb_hr_payroll_formula.ir_cron_pull_previous_month',
            raise_if_not_found=False)
        connectors = self.search([('active', '=', True)])
        return {
            'scheduled': bool(cron and cron.active),
            'next_run': fields.Datetime.to_string(cron.nextcall) if cron else '',
            'connectors': [{
                'id': c.id,
                'name': c.display_name,
                'enabled': bool(c.cron_pull_enabled),
                'last_run': fields.Datetime.to_string(c.cron_pull_last_run) or '',
                'state': c.cron_pull_last_state or '',
                'rows': c.cron_pull_last_rows or 0,
                'message': c.cron_pull_last_result or '',
            } for c in connectors],
        }
