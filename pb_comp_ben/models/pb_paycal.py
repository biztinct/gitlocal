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
            'label': cal.name or '',
            'short': cal.month.strftime('%b') if cal.month else '',
            'month': cal.month and cal.month.isoformat() or '',
            'cutoff': cal.cutoff_date and cal.cutoff_date.isoformat() or '',
            'cutoff_label': _friendly(cal.cutoff_date),
            'pay': cal.pay_date and cal.pay_date.isoformat() or '',
            'pay_label': _friendly(cal.pay_date),
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
    def set_state(self, calendar_id, state):
        self._require_write()
        cal = self.env['pb.payroll.calendar'].browse(int(calendar_id)).exists()
        if not cal:
            return False
        return cal.action_close() if state == 'closed' else cal.action_reopen()

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


def _friendly(day):
    """"25 September" — the date on a page, not the one in the database."""
    if not day:
        return ''
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
              'August', 'September', 'October', 'November', 'December']
    same_year = day.year == date.today().year
    return '%s %s%s' % (day.day, months[day.month - 1],
                        '' if same_year else ' %s' % day.year)
