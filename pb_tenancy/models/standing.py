# -*- coding: utf-8 -*-
"""FLEET P5 — what this database has been told about its own standing.

THE SEVEN SETTINGS, AND THEY ARE READ HERE AND WRITTEN NOWHERE.

    pb_tenancy.access          "open" or "suspended"
    pb_tenancy.access_text     the sentence shown on the paused page
    pb_tenancy.trial_ends      the last day of the trial, or empty
    pb_tenancy.plan_name       what the company pays for, in words
    pb_tenancy.seat_limit      how many employees the plan allows, 0 = no limit
    pb_tenancy.invoices        the invoice list, as JSON, newest first
    pb_tenancy.recovery_login  the one account that still gets in when paused

WHY THE RULES ARE COPIED RATHER THAN IMPORTED. `pb_tenants` is the platform's
own cockpit and is never installed here — the never-list is the whole point of
it. So the two small judgements this database has to make for itself (is the
trial ending, is the company at its employee limit) are written out again, in
the same words, the way `read_features` already repeats the platform's feature
modes. Twelve lines of arithmetic duplicated is a better trade than a customer's
payroll database depending on the platform's billing code.

AND IT FAILS OPEN, EVERY TIME. A database that has never been told anything
reads "no answer" as: access is open, there is no trial, there is no employee
limit. That is the only safe direction. The alternative is a payroll office
locked out of its own data because a settings row was empty.
"""
import json
import logging
import time

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

P_ACCESS = 'pb_tenancy.access'
P_ACCESS_TEXT = 'pb_tenancy.access_text'
P_TRIAL_ENDS = 'pb_tenancy.trial_ends'
P_PLAN_NAME = 'pb_tenancy.plan_name'
P_SEAT_LIMIT = 'pb_tenancy.seat_limit'
P_INVOICES = 'pb_tenancy.invoices'
P_RECOVERY = 'pb_tenancy.recovery_login'

#: The line shown on the paused page when the platform sent no words of its own.
DEFAULT_PAUSED_TEXT = ("Your Payobook access is paused. Please contact your "
                       "administrator.")

#: A trial is announced for this many days at the end of it.
TRIAL_WARN_DAYS = 7
#: The share of the employee limit at which the company is warned.
SEAT_NEAR_PCT = 0.9

#: How long the employee count is remembered before it is counted again.
#: `state()` runs on EVERY page load of EVERY user, and a count over a table
#: with five thousand rows on every one of those is a cost nobody agreed to.
#: Five minutes is far shorter than the time it takes anybody to hire enough
#: people to cross a limit.
SEAT_CACHE_SECONDS = 300

#: `{dbname: (taken_at, count)}`. Per process, thrown away on restart, and a
#: wrong answer costs one banner shown five minutes late.
_SEAT_CACHE = {}


def trial_phase(trial_ends, today, warn_days=TRIAL_WARN_DAYS):
    """`none` / `ok` / `ending` / `ended`, and how many days are left."""
    if not trial_ends or not today:
        return {'phase': 'none', 'days_left': 0}
    days = (trial_ends - today).days
    if days < 0:
        return {'phase': 'ended', 'days_left': days}
    if days <= warn_days:
        return {'phase': 'ending', 'days_left': days}
    return {'phase': 'ok', 'days_left': days}


def trial_sentence(days_left):
    if days_left is None:
        return ''
    if days_left < 0:
        return "Your Payobook trial has ended."
    if days_left == 0:
        return "Your Payobook trial ends today."
    if days_left == 1:
        return "Your Payobook trial ends tomorrow."
    return "Your Payobook trial ends in %d days." % int(days_left)


def seat_verdict(limit, count, near_pct=SEAT_NEAR_PCT):
    """`ok`, `near` or `full`. A limit of nought means no limit at all."""
    try:
        limit = int(limit or 0)
    except (TypeError, ValueError):
        limit = 0
    try:
        count = int(count or 0)
    except (TypeError, ValueError):
        count = 0
    if limit <= 0:
        return {'verdict': 'ok', 'limit': 0, 'count': count, 'left': -1, 'pct': 0}
    pct = int(round(min(count, limit) * 100.0 / limit))
    if count >= limit:
        return {'verdict': 'full', 'limit': limit, 'count': count, 'left': 0,
                'pct': 100}
    if count >= limit * near_pct:
        return {'verdict': 'near', 'limit': limit, 'count': count,
                'left': limit - count, 'pct': pct}
    return {'verdict': 'ok', 'limit': limit, 'count': count,
            'left': limit - count, 'pct': pct}


def seat_refusal(limit, count):
    """Why an employee was not added, and what to do about it."""
    return ("Your plan allows {:,} employees and you already have {:,}. "
            "Ask your Payobook administrator to move you to a larger plan, "
            "or archive an employee who has left."
            .format(int(limit or 0), int(count or 0)))


def read_invoices(raw):
    """The invoice list from the setting. Damage reads as "none". PURE."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        _logger.warning("pb_tenancy: the invoice list is not readable.")
        return []
    if not isinstance(data, list):
        return []
    out = []
    for row in data:
        if not isinstance(row, dict) or not row.get('number'):
            continue
        out.append({
            'number': str(row.get('number') or ''),
            'period': str(row.get('period') or ''),
            'period_label': str(row.get('period_label') or ''),
            'total': str(row.get('total') or ''),
            'state': str(row.get('state') or ''),
            'due_date': str(row.get('due_date') or ''),
            'issued_at': str(row.get('issued_at') or ''),
            'attachment_id': int(row.get('attachment_id') or 0),
        })
    return out


class PbTenancyStanding(models.AbstractModel):
    """Added to the same model the release and the notices already live on."""
    _inherit = 'pb.tenancy'

    # ------------------------------------------------------------------ reads
    @api.model
    def _icp(self):
        return self.env['ir.config_parameter'].sudo()

    @api.model
    def access_state(self):
        """`open` or `suspended`, plus the sentence to show. Never raises."""
        icp = self._icp()
        access = (icp.get_param(P_ACCESS, '') or 'open').strip().lower()
        if access != 'suspended':
            access = 'open'
        text = (icp.get_param(P_ACCESS_TEXT, '') or '').strip()
        return {'access': access,
                'access_text': text or DEFAULT_PAUSED_TEXT}

    @api.model
    def recovery_login(self):
        return (self._icp().get_param(P_RECOVERY, '') or '').strip().lower()

    @api.model
    def seat_count(self, fresh=False):
        """How many people are on Payobook here, counted at most every 5 min.

        Straight SQL rather than `search_count`: this runs on every page load
        and must cost one index-free count on a small table, not a record set.
        """
        dbname = self.env.cr.dbname
        now = time.time()
        cached = _SEAT_CACHE.get(dbname)
        if not fresh and cached and now - cached[0] < SEAT_CACHE_SECONDS:
            return cached[1]
        count = 0
        try:
            self.env.cr.execute(
                "SELECT count(*) FROM hr_employee WHERE active")
            count = int((self.env.cr.fetchone() or [0])[0] or 0)
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenancy: could not count the employees",
                            exc_info=True)
            return cached[1] if cached else 0
        _SEAT_CACHE[dbname] = (now, count)
        return count

    @api.model
    def seat_state(self, fresh=False):
        """Where this company stands against its plan's employee limit."""
        try:
            limit = int(self._icp().get_param(P_SEAT_LIMIT, '0') or 0)
        except (TypeError, ValueError):
            limit = 0
        if limit <= 0:
            # No limit means nothing to count, and nothing to count means the
            # cheapest possible answer on every page load.
            return seat_verdict(0, 0)
        return seat_verdict(limit, self.seat_count(fresh=fresh))

    @api.model
    def trial_state(self):
        raw = (self._icp().get_param(P_TRIAL_ENDS, '') or '').strip()
        if not raw:
            return {'phase': 'none', 'days_left': 0, 'ends': '', 'text': ''}
        try:
            ends = fields.Date.to_date(raw)
        except (ValueError, TypeError):
            return {'phase': 'none', 'days_left': 0, 'ends': '', 'text': ''}
        if not ends:
            return {'phase': 'none', 'days_left': 0, 'ends': '', 'text': ''}
        phase = trial_phase(ends, fields.Date.context_today(self))
        return dict(phase, ends=ends.isoformat(),
                    text=trial_sentence(phase['days_left'])
                    if phase['phase'] in ('ending', 'ended') else '')

    @api.model
    def invoices(self):
        return read_invoices(self._icp().get_param(P_INVOICES, ''))

    @api.model
    def plan_name(self):
        return (self._icp().get_param(P_PLAN_NAME, '') or '').strip()

    # ------------------------------------------------- the one chrome answer
    @api.model
    def state(self):
        """The release, the notices, the switches — and now the standing.

        Still one dict read in one go on every page load. The two additions
        that could cost anything are guarded: the employee count is only taken
        when the plan actually has a limit, and it is remembered for five
        minutes when it is.
        """
        data = super().state()
        access = self.access_state()
        seat = self.seat_state()
        trial = self.trial_state()
        data.update({
            'access': access['access'],
            'access_text': access['access_text'],
            'plan_name': self.plan_name(),
            'trial': trial,
            'trial_ends': trial['ends'],
            'seat': seat,
            'seat_limit': seat['limit'],
            'seat_count': seat['count'],
            # ONE STRING THAT CHANGES ONLY WHEN THE ANSWER CHANGES — the same
            # trick `features_sig` plays (ledger F47). Every screen that has to
            # repaint when the standing moves watches this rather than the
            # objects above, which are rebuilt on every read.
            'standing_sig': '%s|%s|%s|%s' % (
                access['access'], trial['phase'], seat['verdict'],
                seat['count']),
        })
        return data

    # -------------------------------------------------------- the plan page
    @api.model
    def plan_usage(self):
        """Everything the customer's own "Plan & usage" page draws.

        A SEPARATE CALL FROM `state()` on purpose: this one counts the payslips
        produced this month, which is a real query, and it must not be run on
        every page load of every user for a page almost nobody opens.
        """
        today = fields.Date.context_today(self)
        first = today.replace(day=1)
        payslips = 0
        try:
            self.env.cr.execute(
                "SELECT count(*) FROM hr_payslip "
                "WHERE date_from >= %s AND date_from <= %s "
                "AND state NOT IN ('draft', 'cancel')", (first, today))
            payslips = int((self.env.cr.fetchone() or [0])[0] or 0)
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenancy: could not count this month's "
                            "payslips", exc_info=True)
        # THE COUNT IS TAKEN HERE, NOT READ OFF `seat_state`. That one skips
        # counting altogether when the plan has no limit — which is right for
        # a banner nobody will ever see, and wrong for THIS page, where the
        # ring showed "0 employees" above a tile that said 153.
        employees = self.seat_count(fresh=True)
        try:
            limit = int(self._icp().get_param(P_SEAT_LIMIT, '0') or 0)
        except (TypeError, ValueError):
            limit = 0
        seat = seat_verdict(limit, employees)
        return {
            'plan_name': self.plan_name(),
            'seat': seat,
            'employees': employees,
            'payslips': payslips,
            'month': first.strftime('%B %Y'),
            'trial': self.trial_state(),
            'access': self.access_state(),
            'invoices': self.invoices(),
            'pushed_at': (self._icp().get_param('pb_tenancy.pushed_at', '')
                          or ''),
        }
