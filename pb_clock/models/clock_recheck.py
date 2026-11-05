# -*- coding: utf-8 -*-
"""pb.clock.recheck — the nightly full re-check (CLOCK-3 §5).

Every night at 02:30 company time, for every person who punched in the last 35
days, the pairing engine rebuilds their days from the ledger. The engine's own
guards (D4) leave every day a person decided about exactly as it is — closed,
inside a week under approval or approved, corrected, or overlapping a row a
person typed — so the re-check can only ever put a time-clock day back to what
its punches say. Then it counts the days that changed: a time-clock day edited
by hand, a day whose punches are gone, a day the live pairing got wrong.

Stored on the company (`pb_clock_last_recheck_at`, `_fixed`); the lens
settings card reads "Last full re-check: today 02:31 · 0 days changed". When a
night changes something, the watcher raises `recheck_changed` with the count;
the next clean night resolves it.

ONE job for every company: it runs every 15 minutes and does the work for a
company only inside that company's night window (02:30–06:00 local) and once a
day — the same "check the hour in each zone" pattern the 08:00 summary uses.
Idempotent: a second run the same night changes nothing (rule 10).
"""

import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

RECHECK_DAYS = 35
NIGHT_FROM = time(2, 30)
NIGHT_TO = time(6, 0)
_ACTIVE = ('matched', 'paired', 'middle', 'held', 'ignored_duplicate_tap')


class PbClockRecheck(models.AbstractModel):
    _name = 'pb.clock.recheck'
    _description = 'Time clock nightly re-check'

    @api.model
    def _cron_recheck(self):
        return self.sudo()._run_due()

    @api.model
    def _local_now(self, company, now):
        try:
            tz = pytz.timezone(company.resource_calendar_id.tz or 'UTC')
        except Exception:  # noqa: BLE001
            tz = pytz.UTC
        return pytz.UTC.localize(now).astimezone(tz).replace(tzinfo=None)

    @api.model
    def _run_due(self, now=None):
        """Re-check every company whose night it is and that was not checked
        tonight. {company_id: days changed}."""
        self = self.sudo()
        now = fields.Datetime.to_datetime(now) or fields.Datetime.now()
        out = {}
        companies = self.env['pb.clock.device'].with_context(active_test=False).search(
            []).mapped('company_id')
        for company in companies:
            local = self._local_now(company, now)
            if not (NIGHT_FROM <= local.time() < NIGHT_TO):
                continue
            if company.pb_clock_recheck_on == local.date():
                continue
            try:
                with self.env.cr.savepoint():
                    out[company.id] = self.run_company(company, now)
            except Exception:  # noqa: BLE001 — one company never blocks another
                _logger.exception("pb_clock: nightly re-check failed for company %s",
                                  company.id)
        return out

    @api.model
    def run_company(self, company, now=None):
        """Rebuild the last 35 days of every person of `company` who punched,
        count the days that changed, store it, and let the watcher look."""
        self = self.sudo()
        now = fields.Datetime.to_datetime(now) or fields.Datetime.now()
        since = now - timedelta(days=RECHECK_DAYS)
        Punch = self.env['pb.clock.punch']
        groups = Punch._read_group(
            [('company_id', '=', company.id), ('employee_id', '!=', False),
             ('state', 'in', _ACTIVE), ('punch_utc', '>=', since)],
            groupby=['employee_id'], aggregates=['punch_utc:min'])
        fixed = 0
        for emp, first in groups:
            if not emp or not first:
                continue
            try:
                with self.env.cr.savepoint():
                    fixed += self._recheck_employee(emp, first)
            except Exception:  # noqa: BLE001 — one person never stops the night
                _logger.warning("pb_clock: re-check failed for employee %s", emp.id,
                                exc_info=True)
        local = self._local_now(company, now)
        company.write({'pb_clock_last_recheck_at': now,
                       'pb_clock_last_recheck_fixed': fixed,
                       'pb_clock_recheck_on': local.date()})
        if 'pb.clock.alert' in self.env:
            self.env['pb.clock.alert']._watch(now=now, company_ids=[company.id], mail=False)
        if fixed:
            _logger.info("pb_clock: nightly re-check of company %s changed %s days",
                         company.id, fixed)
        return fixed

    @api.model
    def _snapshot(self, emp, lo):
        Att = self.env['hr.attendance'].sudo()
        rows = Att.search([('employee_id', '=', emp.id), ('pb_entry_source', '=', 'device'),
                           ('check_in', '>=', lo)])
        cache = {}
        return {r.id: (r.check_in, r.check_out, bool(r.pb_clock_auto_closed),
                       r._pb_local_day(cache)) for r in rows}

    @api.model
    def _recheck_employee(self, emp, first_utc):
        """Re-pair one person from their first punch in the window. Returns
        the number of local days whose time-clock row changed."""
        span = timedelta(hours=emp.company_id.pb_clock_max_span_h or 21.0)
        lo = first_utc - span
        before = self._snapshot(emp, lo)
        summary = {'matched': 0, 'unmatched': 0, 'paired_days': 0, 'held': 0,
                   'ignored': 0, 'more': False}
        self.env['pb.clock.pairing']._pair_employee(emp, first_utc, summary)
        self.env.flush_all()
        after = self._snapshot(emp, lo)
        days = set()
        for rid, vals in before.items():
            now_vals = after.get(rid)
            if now_vals is None or now_vals[:3] != vals[:3]:
                days.add(vals[3])
        for rid, vals in after.items():
            if rid not in before:
                days.add(vals[3])
        return len({d for d in days if d})
