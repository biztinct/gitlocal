# -*- coding: utf-8 -*-
"""`pb.paycal` — the Payroll calendar lens's only server surface.

The cockpit shape this product keeps: an `AbstractModel` facade, `@api.model`
reads, every independent probe in its own `_safe()` so one failing number
answers zero instead of taking the screen down, `env.companies` scoping, a row
cap, and no sudo in a read.

THE QUESTION THIS LENS ANSWERS: how long have I got. Everything else on the
screen is context for the countdown at the top of it.
"""

import logging
from datetime import date

from odoo import _, api, models

from .month_approval import propose_reopen
from odoo.exceptions import AccessError

from .comp_common import (
    GROUP_HEAD, GROUP_USER, P_REMINDERS, flag,
)

_logger = logging.getLogger(__name__)

BOARD_LIMIT = 60


def _refusal():
    return {
        'allowed': False, 'can_write': False,
        'months': [], 'next': None, 'kpis': {}, 'reminders_on': False,
        'why': _("The payroll calendar is looked after by the pay team. Ask "
                 "your payroll lead to add you to it."),
    }


class PbPaycal(models.AbstractModel):
    _name = 'pb.paycal'
    _description = 'Payobook payroll calendar cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:              # noqa: BLE001
            _logger.debug('paycal metric failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return bool(self.env.su or user._is_admin()
                    or user.has_group(GROUP_USER)
                    or user.has_group(GROUP_HEAD))

    @api.model
    def _can_write(self):
        return bool(self.env.su or self.env.user._is_admin()
                    or self.env.user.has_group(GROUP_HEAD))

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "Building the payroll calendar is for the head of the pay "
                "team."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self, year=None):
        if not self._can_read():
            return _refusal()
        Cal = self.env['pb.payroll.calendar']
        today = date.today()
        year = int(year or today.year)
        rows = Cal.search([
            ('month', '>=', date(year, 1, 1)),
            ('month', '<=', date(year, 12, 31)),
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='month', limit=BOARD_LIMIT)
        months = [self._month_row(cal, today) for cal in rows]
        upcoming = [m for m in months if m['days_left'] is not None
                    and m['days_left'] >= 0 and m['state'] == 'upcoming']
        nxt = upcoming[0] if upcoming else None
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'year': year,
            'years': self._years(),
            'months': months,
            'next': nxt,
            'reminders_on': flag(self.env, P_REMINDERS),
            'kpis': {
                'planned': len(months),
                'closed': len([m for m in months if m['state'] == 'closed']),
                'ahead': len(upcoming),
                'reminders': sum(m['reminders'] for m in months),
            },
            'why': '',
        }

    @api.model
    def _years(self):
        today = date.today()
        return [today.year - 1, today.year, today.year + 1]

    @api.model
    def _month_row(self, cal, today):
        left = (cal.cutoff_date - today).days if cal.cutoff_date else None
        return {
            'id': cal.id,
            'label': _month_label(self.env, cal.month) or cal.name or '',
            'short': _month_short(self.env, cal.month.month) if cal.month else '',
            'month': cal.month and cal.month.isoformat() or '',
            'cutoff': cal.cutoff_date and cal.cutoff_date.isoformat() or '',
            'cutoff_label': _friendly(self.env, cal.cutoff_date),
            'pay': cal.pay_date and cal.pay_date.isoformat() or '',
            'pay_label': _friendly(self.env, cal.pay_date),
            'state': cal.state or 'upcoming',
            'days_left': left,
            'is_past': bool(left is not None and left < 0),
            'offsets': cal._offsets(),
            'reminders': len([1 for line in (cal.reminder_log or '').splitlines()
                              if line.strip()]),
            'log': [line for line in (cal.reminder_log or '').splitlines()
                    if line.strip()],
            'notes': cal.notes or '',
            'company': cal.company_id.name or '',
        }

    # ------------------------------------------------------------ the writes
    @api.model
    def build_year(self, cutoff_day, pay_day, start_month=False, months=12,
                   offsets='5,2,0'):
        self._require_write()
        # R43 — everything below arrives from the browser as a string.
        return self.env['pb.payroll.calendar'].build_year(
            cutoff_day, pay_day, start_month=start_month or False,
            company_id=self.env.company.id, months=months, offsets=offsets)

    @api.model
    def set_state(self, calendar_id, state, reason=''):
        """Close or reopen. Only one of the two is a decision (P7)."""
        self._require_write()
        cal = self.env['pb.payroll.calendar'].browse(int(calendar_id)).exists()
        if not cal:
            return False
        if state == 'closed':
            return cal.action_close()
        held = propose_reopen(cal, reason)
        if held is not None:
            if not held.get('applied'):
                return dict(held, pending=True)
            return dict(held.get('result') or {},
                        reference=held.get('reference'))
        return cal.action_reopen(reason)

    @api.model
    def save_month(self, calendar_id, vals):
        self._require_write()
        cal = self.env['pb.payroll.calendar'].browse(int(calendar_id)).exists()
        if not cal:
            return False
        clean = {k: v for k, v in (vals or {}).items()
                 if k in ('cutoff_date', 'pay_date', 'reminder_offset_days',
                          'notes')}
        cal.write(clean)
        return True

    @api.model
    def run_reminders_now(self):
        """"Run it now" does EXACTLY what the night does (R53) — same method."""
        self._require_write()
        return self.env['pb.payroll.calendar']._cron_payroll_calendar_reminders()

    @api.model
    def set_reminders(self, enabled):
        self._require_write()
        self.env['ir.config_parameter'].sudo().set_param(
            P_REMINDERS, '1' if enabled else '0')
        return bool(enabled)


def _friendly(env, day):
    """"25 September" — the date on a page, not the one in the database.

    Called from the board's model methods, so `env._()` reads the caller's
    language (LEARN REFRESH step 6). Every placeholder is offered to every
    sentence, so a translation may write the month as a name or a number."""
    if not day:
        return ''
    args = {'day': day.day, 'month': _month_name(env, day.month),
            'num': day.month, 'year': day.year}
    if day.year == date.today().year:
        return env._("%(day)s %(month)s", **args)
    return env._("%(day)s %(month)s %(year)s", **args)


def _month_name(env, month):
    return [env._("January"), env._("February"), env._("March"), env._("April"), env._("May"),
            env._("June"), env._("July"), env._("August"), env._("September"), env._("October"),
            env._("November"), env._("December")][month - 1]


def _month_short(env, month):
    return [env._("Jan"), env._("Feb"), env._("Mar"), env._("Apr"), env._("May"), env._("Jun"),
            env._("Jul"), env._("Aug"), env._("Sep"), env._("Oct"), env._("Nov"),
            env._("Dec")][month - 1]


def _month_label(env, month):
    """"September 2026" — the stored `name` is English for ever (it is
    computed once, in whatever language the write ran in)."""
    if not month:
        return ''
    return env._("%(month)s %(year)s", month=_month_name(env, month.month),
             num=month.month, year=month.year)
