# -*- coding: utf-8 -*-
"""UPDATES P3a (D1) — a pay data file is for its pay run only.

Owner decision D1: the pay run's pay data file is month-only; lasting changes
to employee, contract, bank and pay-item records come through People ›
Updates. Every door through which a PERSON uploads a pay data file is
therefore month-only, enforced here, on the server, whatever the screen sent:

  * the Import screen's "Load Pay Data" (the guided import,
    `pb_import_wizard.create_and_load`, which sets no flag and so got the
    model's defaults: lasting, creating unknown people);
  * the Run Payroll screen's file (`pb.payrun.wizard.attach_spreadsheet`;
    already one-time wherever `pb_payroll_templates` is installed — every
    live database — but its own default without that module is "update");
  * anything else that creates or edits a pay data file while serving a
    person's request (an RPC client included).

HOW. `hr.payroll.import.batch` is made "Use these values once", with both
"create missing employees / contracts" switches off, on create and on write,
whenever the call is made while serving a person's web request — unless it
comes from the CONNECTED-SYSTEM LANE, which is intentionally lasting (the
record refresh, `hr.integration.connector._rd54_writeback_from_store`, from
its schedule, its "Refresh records now" button and the Run Payroll screen's
"update records from the feed"). That lane is recognised by a context value
that is a module-level object IDENTITY (`LANE_TOKEN`), so a value arriving
over RPC can never equal it (the `payroll_import_approval` precedent).

What a month-only file does with a row for somebody who is not in the system
is the batch's own existing rule (`ONE_TIME_NO_EMPLOYEE`): the row is listed
as needing attention and is not paid — never a new employee.

Untouched on purpose: scheduled jobs and server scripts (no web request), the
batch model's lasting-write code (the connected-system lane uses it),
"Keep for future payrolls" (`pb_payroll_templates`, already routed through
the Records Desk) and every pay-run test suite (no web request in a
TransactionCase).
"""
import logging

from odoo import api, models
from odoo.http import request

_logger = logging.getLogger(__name__)

#: The context key the connected-system lane carries, and its unforgeable
#: value (an object identity — never equal to anything sent over JSON).
LANE_KEY = 'pb_updates_connected_lane'
LANE_TOKEN = object()

#: What month-only means on a pay data file.
MONTH_ONLY = {'one_time': True, 'auto_create_employees': False,
              'auto_create_contracts': False}


def lane_context(record):
    return record.with_context(**{LANE_KEY: LANE_TOKEN})


class HrPayrollImportBatchMonthOnly(models.Model):
    _inherit = 'hr.payroll.import.batch'

    @api.model
    def _pb_month_only_now(self):
        """True while serving a person's web request, outside the
        connected-system lane."""
        if self.env.context.get(LANE_KEY) is LANE_TOKEN:
            return False
        try:
            return bool(request)
        except RuntimeError:     # pragma: no cover — no request bound
            return False

    @api.model_create_multi
    def create(self, vals_list):
        if self._pb_month_only_now():
            for vals in vals_list:
                vals.update(MONTH_ONLY)
        return super().create(vals_list)

    def write(self, vals):
        if self._pb_month_only_now() and any(k in vals for k in MONTH_ONLY):
            vals = dict(vals, **MONTH_ONLY)
        return super().write(vals)

    def _pb_month_only_belt(self):
        """The belt: a pay data file a person processes is month-only even
        if it was made before this rule (a draft from last week). The
        connected system's own refreshes keep their lasting meaning."""
        if not self._pb_month_only_now():
            return self.browse()
        stale = self.filtered(
            lambda b: b.source_type != 'api_data_store' and (
                not b.one_time or b.auto_create_employees
                or b.auto_create_contracts))
        if stale:
            _logger.info('pb_updates: %s pay data file(s) made month-only '
                         'before processing: %s', len(stale), stale.ids)
            super(HrPayrollImportBatchMonthOnly, stale.sudo()).write(
                dict(MONTH_ONLY))
        return stale

    def action_process(self):
        self._pb_month_only_belt()
        return super().action_process()


class HrIntegrationConnectorLane(models.Model):
    """The connected-system lane: its record refresh stays lasting."""
    _inherit = 'hr.integration.connector'

    def _rd54_writeback_from_store(self, period_from, period_to):
        return super(HrIntegrationConnectorLane, lane_context(self)) \
            ._rd54_writeback_from_store(period_from, period_to)
