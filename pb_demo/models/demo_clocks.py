# -*- coding: utf-8 -*-
"""Time clocks demo (CLOCK-3 §8) — extends pb.demo.generator.

The Time clocks lens is the sales screen for attendance machines, and on a
demo world it opened on "No machine connected". This seeder gives it a life:

  * one terminal, "DEMO Factory gate" (serial DEMO-0001, Asia/Ho_Chi_Minh),
    pairing from the Monday a week before this one;
  * two weeks of punches for a cohort of 24 demo people — the 57th to the 80th
    adult in name order, so they are NOT the 40 the attendance seeder gives a
    grid week to (`demo_workforce._COHORT`) and no punch ever lands on a day a
    person already has hours (those would wait "on hold") — every person-day
    that already has an attendance row is skipped anyway;
  * the shapes the machine story needs: morning and afternoon shifts with a
    lunch tap or two (shown, not paid), one night shift that crosses midnight,
    one double tap, one forgotten check-out (a day closed at its check-in and
    listed under "Days missing a check-out"), and an unknown number DEMO-999
    with a handful of punches;
  * today's morning punches up to the moment the seed runs, so the live
    sentence reads "Last punch 3 min ago, DEMO Factory gate · 21 people
    punched today".

ADDITIVE ONLY (memory `keep-demo-data-payobook`): nothing existing is changed
or removed. The one write to an existing record is the EMPTY clock number of
the 24 cohort people (`pb_clock_code`, never overwritten when set) — a machine
number is how a punch finds its person. Idempotent: the ledger keeps a punch
once (dedup key), the machine and the codes are found again, so a second run
adds nothing. The machine is a "punches by file" terminal (no live connection:
`allowed_at` empty), so it never reads as a silent machine on the demo world,
and the demo company's time-clock emails are switched off (prospects log in
to this database).

Pairing is NOT done here (CLOCK ledger rule 12): the seed adds ledger rows and
triggers the pairing job, like every other intake.
"""

import hashlib
import logging
from datetime import datetime, time, timedelta

from pytz import timezone, utc

from odoo import fields, models

_logger = logging.getLogger(__name__)

_FROM, _TO = 56, 80          # adults[56:80] in name order: 24 people
_SERIAL = 'DEMO-0001'
_UNKNOWN = 'DEMO-999'
_CODE_BASE = 1001


def _h(*parts):
    """A stable small number from the parts (no RNG: a re-run is the same world)."""
    raw = '|'.join(str(p) for p in parts).encode('utf-8')
    return int(hashlib.sha1(raw).hexdigest()[:8], 16)


class PbDemoGenerator(models.TransientModel):
    _inherit = 'pb.demo.generator'

    # ------------------------------------------------------------------ entry
    def ensure_time_clocks(self, now=None):
        """The demo machine and its two weeks. Returns the counts."""
        if 'pb.clock.punch' not in self.env:
            return {}
        self = self.with_context(**self._GEN_CTX)
        company = self.get_group_company()
        if not company:
            _logger.warning('pb_demo: no demo company; skipping time clocks')
            return {}
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        adults = Employee.search([
            ('is_demo', '=', True), ('company_id', '=', company.id),
            ('active', '=', True),
        ], order='name').filtered(lambda e: 'Minor' not in (e.name or ''))
        cohort = adults[_FROM:_TO]
        if len(cohort) < 6:
            _logger.warning('pb_demo: not enough demo people for time clocks')
            return {}
        cal = self.get_calendar(company)
        tz = timezone((cal and cal.tz) or 'Asia/Ho_Chi_Minh')
        now = fields.Datetime.to_datetime(now) or fields.Datetime.now()
        today = utc.localize(now).astimezone(tz).date()
        monday = today - timedelta(days=today.weekday())
        res = self._seed_time_clocks(cohort, company, tz, today, monday, now=now)
        _logger.info('pb_demo: time clocks ready %s', res)
        return res

    # ----------------------------------------------------------------- helpers
    def _clock_device(self, company, monday, now):
        Device = self.env['pb.clock.device'].sudo().with_context(active_test=False)
        device = Device.search([('company_id', '=', company.id), ('serial', '=', _SERIAL)],
                               limit=1)
        if device:
            return device, False
        device = Device.create({
            'name': 'DEMO Factory gate', 'serial': _SERIAL, 'kind': 'terminal',
            'location': 'Main entrance', 'company_id': company.id,
            'tz': 'Asia/Ho_Chi_Minh', 'state': 'allowed',
            'history_from': monday - timedelta(days=7),
            'firmware': 'Ver 8.0.4.2', 'pushver': '2.4.1',
            'first_seen_at': now - timedelta(days=15),
            'users_count': _TO - _FROM + 1, 'fp_count': 2 * (_TO - _FROM),
        })
        return device, True

    def _clock_codes(self, cohort):
        """{employee: code}; fills an EMPTY clock number only."""
        out = {}
        Emp = self.env['hr.employee'].sudo()
        taken = set(Emp.with_context(active_test=False).search(
            [('pb_clock_code', '!=', False), ('company_id', '=', cohort[:1].company_id.id)]
        ).mapped('pb_clock_code'))
        filled = 0
        for i, emp in enumerate(cohort):
            code = (emp.pb_clock_code or '').strip()
            if not code:
                want = str(_CODE_BASE + i)
                if want in taken:
                    continue
                emp.pb_clock_code = want
                taken.add(want)
                filled += 1
                code = want
            out[emp] = code
        return out, filled

    def _busy_days(self, cohort, tz, first, last):
        """{(employee id, local day)} that already carry an attendance row."""
        Att = self.env['hr.attendance'].sudo()
        lo = tz.localize(datetime.combine(first, time.min)).astimezone(utc).replace(tzinfo=None)
        hi = tz.localize(datetime.combine(last + timedelta(days=1), time.min)).astimezone(
            utc).replace(tzinfo=None)
        busy = set()
        for a in Att.search([('employee_id', 'in', cohort.ids),
                             ('check_in', '>=', lo - timedelta(hours=14)),
                             ('check_in', '<', hi)]):
            for dt in (a.check_in, a.check_out):
                if dt:
                    busy.add((a.employee_id.id, utc.localize(dt).astimezone(tz).date()))
        return busy

    # -------------------------------------------------------------- the seed
    def _seed_time_clocks(self, cohort, company, tz, today, monday, now=None):
        now = fields.Datetime.to_datetime(now) or fields.Datetime.now()
        local_now = utc.localize(now).astimezone(tz).replace(tzinfo=None)
        device, made = self._clock_device(company, monday, now)
        codes, filled = self._clock_codes(cohort)
        if 'pb_clock_alert_mail' in company._fields and company.pb_clock_alert_mail:
            company.sudo().pb_clock_alert_mail = False
        first = monday - timedelta(days=7)
        busy = self._busy_days(cohort, tz, first - timedelta(days=1), today)
        people = list(codes.items())
        night_emp = people[0][0] if people else None
        double_emp = people[1][0] if len(people) > 1 else None
        forgot_emp = people[2][0] if len(people) > 2 else None
        # the forgotten check-out: a weekday at least three days back
        forgot_day = None
        for back in range(3, 9):
            d = today - timedelta(days=back)
            if d >= first and d.weekday() < 5:
                forgot_day = d
                break

        vals = []

        def add(code, local_dt):
            if local_dt > local_now:
                return
            vals.append({'device_id': device.id, 'company_id': company.id,
                         'source': 'adms', 'user_code': code,
                         'punch_local': fields.Datetime.to_string(local_dt),
                         'verify_mode': '1' if _h(code, local_dt) % 5 else '15'})

        d = first
        while d <= today:
            weekday = d.weekday()
            for idx, (emp, code) in enumerate(people):
                if (emp.id, d) in busy:
                    continue
                k = _h(emp.id, d)
                if emp == night_emp:
                    # nights Mon–Fri: 19:1x → 07:3x next morning (one day)
                    if weekday < 5 and (emp.id, d + timedelta(days=1)) not in busy:
                        add(code, datetime.combine(d, time(19, 10 + k % 9)))
                        add(code, datetime.combine(d + timedelta(days=1),
                                                   time(7, 28 + k % 7)))
                    continue
                if weekday == 6 or (weekday == 5 and idx % 3):
                    continue          # Sundays off; a third of the floor on Saturdays
                if k % 23 == 0 and d != today and emp not in (double_emp, forgot_emp):
                    continue          # the odd day off (never on the story's people)
                afternoon = idx % 4 == 3
                start = time(13, 40 + k % 15) if afternoon else time(7, 20 + k % 32)
                end_h, end_m = (21, 30 + k % 25) if afternoon else (16, 30 + k % 50)
                if end_m >= 60:
                    end_h, end_m = end_h + 1, end_m - 60
                if weekday == 5:
                    end_h, end_m = (17, 5) if afternoon else (11, 30 + k % 20)
                t_in = datetime.combine(d, start)
                add(code, t_in)
                if emp == double_emp and d == today - timedelta(days=1):
                    add(code, t_in + timedelta(seconds=40))      # the double tap
                if emp == forgot_emp and d == forgot_day:
                    continue                                     # no check-out that day
                if not afternoon and weekday < 5 and k % 3 == 0:
                    # a lunch tap pair: kept and shown, never paid
                    add(code, datetime.combine(d, time(11, 58 + k % 2)))
                    add(code, datetime.combine(d, time(12, 41 + k % 9)))
                add(code, datetime.combine(d, time(end_h, end_m)))
            if weekday < 5 and d >= today - timedelta(days=5):
                add(_UNKNOWN, datetime.combine(d, time(7, 44 + _h(_UNKNOWN, d) % 9)))
            d += timedelta(days=1)

        Punch = self.env['pb.clock.punch'].sudo()
        res = Punch._ingest(vals) if vals else {'created': 0, 'duplicates': 0}
        if res['created']:
            self.env['pb.clock.pairing']._trigger_soon()
        return {'device_created': made, 'codes_filled': filled,
                'punches_offered': len(vals), 'punches_added': res['created'],
                'people': len(people), 'busy_person_days': len(busy)}
