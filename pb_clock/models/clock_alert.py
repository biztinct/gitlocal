# -*- coding: utf-8 -*-
"""pb.clock.alert — what a time clock needs a person for (CLOCK-3 §3).

ONE CONDITION = ONE ROW. Every alert carries a `key`
(`kind|device|employee|day`, unique per company). The watcher computes the set
of conditions that are true right now and reconciles it with the rows: a row
whose condition still holds is refreshed, a row whose condition is gone is
resolved, and a condition that comes back re-opens its own row. Running the
watcher twice changes nothing but `last_seen_at`.

WORDS ARE COMPUTED WHEN READ. `detail` keeps the English sentence of the moment
the alert was raised (the record, the log); every screen and email builds its
sentence again from the kind and the stored facts (`ref_at`, `ref_value`, the
machine, the person, the day) in the reader's language — a Vietnamese manager
never reads an English sentence a 03:00 job happened to write.

MUTE. "Mute for a week" sets `muted` and `muted_until`; a muted alert is not
shown, not counted and not mailed until `muted_until`, then it opens again if
its condition still holds. A condition that clears resolves a muted row too.

The watcher runs every 15 minutes, one company at a time, each in its own
savepoint: one company's error never blocks another's alerts. It also sends
the two emails (§4.5): the 08:00 summary and the immediate "a machine stopped"
note — see `_mail_company`.
"""

import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

KINDS = [
    ('silent', 'Machine not calling in'),
    ('no_punches', 'No punches on a working day'),
    ('clock', 'Machine clock is off'),
    ('pending', 'Machine asking to connect'),
    ('auto_closed', 'Day missing a check-out'),
    ('command_failed', 'Requests to a machine failed'),
    ('plain', 'Plain connection in use'),
    ('held', 'Punches on hold'),
    ('backlog', 'Punches waiting to be paired'),
    ('recheck_changed', 'Nightly re-check changed days'),
]
STATES = [('open', 'Needs attention'), ('resolved', 'Resolved'), ('muted', 'Muted')]

SILENT_AFTER = timedelta(minutes=15)
QUIET_HOURS = timedelta(hours=6)
DAY_FROM = time(6, 0)
DAY_TO = time(22, 0)
SKEW_LIMIT_S = 60
SKEW_MIN_SAMPLES = 3
SET_TIME_GRACE = timedelta(hours=6)
FUTURE_IGNORED_MIN = 3
PENDING_AFTER = timedelta(hours=24)
AUTO_CLOSED_AFTER = timedelta(days=2)
HELD_AFTER = timedelta(hours=24)
BACKLOG_HIGH = 20000
BACKLOG_LOW = 1000
BACKLOG_FOR = timedelta(minutes=30)
MUTE_FOR = timedelta(days=7)
IMMEDIATE_EVERY = timedelta(hours=6)
DIGEST_HOURS = (8, 12)          # local [08:00, 12:00): a missed 08:00 run still sends

#: kinds that belong to one machine (one strip row each)
DEVICE_KINDS = ('silent', 'no_punches', 'clock', 'command_failed', 'pending', 'plain')
#: kinds that belong to a person's day (one strip row per kind)
PERSON_KINDS = ('auto_closed', 'held')
#: the order the strip, the digest and the Home sentence read in
ORDER = ('silent', 'no_punches', 'clock', 'command_failed', 'pending',
         'auto_closed', 'held', 'recheck_changed', 'backlog', 'plain')
#: the machine kinds that colour the Integrations row "error"
ERROR_KINDS = ('silent', 'clock', 'command_failed')
#: the kinds an immediate email is sent for (on a working day only)
IMMEDIATE_KINDS = ('silent', 'no_punches')

ICON = {
    'silent': 'powerOff', 'no_punches': 'hourglass', 'clock': 'clock',
    'command_failed': 'xCircle', 'pending': 'plug', 'auto_closed': 'logOut',
    'held': 'pause', 'recheck_changed': 'history', 'backlog': 'loader',
    'plain': 'unlink',
}
#: grey kinds: worth knowing, nothing broken
QUIET_KINDS = ('plain', 'backlog')

_OFFICER = 'hr_attendance.group_hr_attendance_officer'
_MANAGER = 'hr_attendance.group_hr_attendance_manager'


class PbClockAlert(models.Model):
    _name = 'pb.clock.alert'
    _description = 'Time clock alert'
    _order = 'first_seen_at desc, id desc'
    _rec_name = 'detail'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 readonly=True)
    kind = fields.Selection(KINDS, required=True, readonly=True, index=True)
    device_id = fields.Many2one('pb.clock.device', string='Machine', index=True,
                                ondelete='cascade', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Person', index=True,
                                  ondelete='cascade', readonly=True)
    day = fields.Date(string='Day', readonly=True)
    state = fields.Selection(STATES, required=True, default='open', index=True)
    first_seen_at = fields.Datetime(string='First seen', readonly=True)
    last_seen_at = fields.Datetime(string='Last checked', readonly=True)
    resolved_at = fields.Datetime(string='Resolved', readonly=True)
    muted_until = fields.Datetime(string='Muted until', readonly=True)
    detail = fields.Char(string='What happened', readonly=True)
    key = fields.Char(required=True, readonly=True, copy=False)
    ref_at = fields.Datetime(string='Since', readonly=True,
                             help='The moment the sentence refers to, e.g. the '
                                  'last time the machine called in.')
    ref_value = fields.Integer(string='How many', readonly=True,
                               help='The number in the sentence: punches, days, '
                                    'seconds of clock difference.')
    facet = fields.Char(string='Which case', readonly=True,
                        help='Which sentence fits: e.g. a clock that is off by '
                             'a measured amount, or punches dated ahead.')
    last_mailed_at = fields.Datetime(string='Last emailed', readonly=True)

    _company_key_uniq = models.Constraint(
        'UNIQUE(company_id, key)', 'This alert already exists.')

    # ================================================================ watcher
    @api.model
    def _cron_watch(self):
        """The 15-minute job body."""
        return self.sudo()._watch()

    @api.model
    def _watch(self, now=None, company_ids=None, mail=True):
        """Raise / refresh / resolve every company's alerts, then send the
        emails that are due. {company_id: {'open': n}}."""
        self = self.sudo()
        now = fields.Datetime.to_datetime(now) or fields.Datetime.now()
        out = {}
        for company in self._watch_companies(company_ids):
            try:
                with self.env.cr.savepoint():
                    out[company.id] = self._watch_company(company, now)
            except Exception:  # noqa: BLE001 — one company never blocks another
                _logger.exception("pb_clock: watching company %s failed", company.id)
                continue
            if not mail:
                continue
            try:
                with self.env.cr.savepoint():
                    self._mail_company(company, now)
            except Exception:  # noqa: BLE001
                _logger.exception("pb_clock: alert emails for company %s failed",
                                  company.id)
        return out

    @api.model
    def _watch_companies(self, company_ids=None):
        Company = self.env['res.company'].sudo()
        if company_ids:
            return Company.browse([int(c) for c in company_ids]).exists()
        ids = set(self.env['pb.clock.device'].sudo().with_context(
            active_test=False).search([]).mapped('company_id').ids)
        ids |= set(self.search([('state', 'in', ('open', 'muted'))]).mapped(
            'company_id').ids)
        return Company.browse(sorted(ids))

    @api.model
    def _watch_company(self, company, now):
        conditions = {}
        unknown = set()      # kinds whose check failed: their rows stay as they are
        for builder, kinds in (
                (self._cond_devices, ('silent', 'no_punches', 'clock', 'command_failed',
                                      'plain')),
                (self._cond_pending, ('pending',)),
                (self._cond_auto_closed, ('auto_closed',)),
                (self._cond_held, ('held',)),
                (self._cond_backlog, ('backlog',)),
                (self._cond_recheck, ('recheck_changed',))):
            try:
                with self.env.cr.savepoint():
                    for cond in builder(company, now) or ():
                        conditions[self._key(cond)] = cond
            except Exception:  # noqa: BLE001 — one check never hides the others
                unknown.update(kinds)
                _logger.warning("pb_clock: alert check %s failed for company %s",
                                builder.__name__, company.id, exc_info=True)
        return self._sync(company, conditions, now, unknown)

    @staticmethod
    def _key(cond):
        return '%s|%s|%s|%s' % (cond['kind'], cond.get('device_id') or '',
                                cond.get('employee_id') or '',
                                fields.Date.to_string(cond.get('day')) if cond.get('day') else '')

    @api.model
    def _sync(self, company, conditions, now, unknown=()):
        """Reconcile the true conditions with the company's rows. A kind in
        `unknown` (its check failed) is neither raised nor resolved."""
        rows = self.with_context(active_test=False).search([('company_id', '=', company.id)])
        by_key = {r.key: r for r in rows}
        opened = 0
        for key, cond in conditions.items():
            vals = {
                'ref_at': cond.get('ref_at') or False,
                'ref_value': int(cond.get('ref_value') or 0),
                'facet': cond.get('facet') or False,
                'last_seen_at': now,
            }
            row = by_key.get(key)
            if not row:
                vals.update({
                    'company_id': company.id, 'key': key, 'kind': cond['kind'],
                    'device_id': cond.get('device_id') or False,
                    'employee_id': cond.get('employee_id') or False,
                    'day': cond.get('day') or False,
                    'state': 'open', 'first_seen_at': now,
                })
                row = self.create(vals)
                row.detail = row._sentence()[:250]
                opened += 1
                continue
            if row.state == 'resolved':
                vals.update({'state': 'open', 'first_seen_at': now,
                             'resolved_at': False, 'muted_until': False,
                             'last_mailed_at': False})
            elif row.state == 'muted' and (not row.muted_until or row.muted_until <= now):
                vals.update({'state': 'open', 'muted_until': False})
            changed = {k: v for k, v in vals.items() if k == 'last_seen_at' or row[k] != v}
            row.write(changed)
            if {'ref_at', 'ref_value', 'facet', 'state'} & set(changed):
                row.detail = row._sentence()[:250]
            if row.state == 'open':
                opened += 1
        gone = rows.filtered(lambda r: r.key not in conditions and r.state != 'resolved'
                             and r.kind not in unknown)
        if gone:
            gone.write({'state': 'resolved', 'resolved_at': now, 'muted_until': False})
        return {'open': opened, 'resolved': len(gone)}

    # ============================================================ conditions
    @api.model
    def _terminals(self, company):
        return self.env['pb.clock.device'].sudo().search([
            ('company_id', '=', company.id), ('kind', '=', 'terminal'),
            ('state', '=', 'allowed'), ('allowed_at', '!=', False)])

    @api.model
    def _is_working_day(self, company, day):
        """The company's working week (its calendar), minus company-wide days
        off. No calendar → Monday to Friday."""
        cal = company.resource_calendar_id
        if not cal:
            return day.weekday() < 5
        if day.weekday() not in {int(a.dayofweek) for a in cal.attendance_ids}:
            return False
        if 'resource.calendar.leaves' in self.env:
            start = datetime.combine(day, time.min)
            off = self.env['resource.calendar.leaves'].sudo().search_count([
                ('calendar_id', 'in', (cal.id, False)), ('resource_id', '=', False),
                ('company_id', 'in', (company.id, False)),
                ('date_from', '<', start + timedelta(days=1)),
                ('date_to', '>', start + timedelta(hours=12))], limit=1)
            if off:
                return False
        return True

    @api.model
    def _cond_devices(self, company, now):
        """silent · no_punches · clock · command_failed · plain."""
        out = []
        Punch = self.env['pb.clock.punch'].sudo()
        Command = self.env['pb.clock.command'].sudo()
        for d in self._terminals(company):
            seen = d.last_seen_at or d.allowed_at
            silent = bool(seen and now - seen > SILENT_AFTER)
            if silent:
                out.append({'kind': 'silent', 'device_id': d.id, 'ref_at': seen})
            # -- no punches for 6 h inside 06:00–22:00 of a working day -------
            tzinfo = d._tzinfo()
            local_now = pytz.UTC.localize(now).astimezone(tzinfo).replace(tzinfo=None)
            today = local_now.date()
            if not silent and self._is_working_day(company, today):
                day_from = datetime.combine(today, DAY_FROM)
                day_to = datetime.combine(today, DAY_TO)
                last_local = None
                if d.last_punch_at:
                    last_local = pytz.UTC.localize(d.last_punch_at).astimezone(
                        tzinfo).replace(tzinfo=None)
                allowed_local = pytz.UTC.localize(d.allowed_at).astimezone(
                    tzinfo).replace(tzinfo=None)
                start = max(x for x in (day_from, last_local, allowed_local) if x)
                end = min(local_now, day_to)
                if end - start >= QUIET_HOURS:
                    punched_today = bool(last_local and last_local >= day_from)
                    out.append({
                        'kind': 'no_punches', 'device_id': d.id, 'day': today,
                        'facet': 'since' if punched_today else 'today',
                        'ref_at': d.last_punch_at if punched_today else False})
            # -- the machine's clock ------------------------------------------
            samples = d._skew_list()
            fixed = Command.search_count([
                ('device_id', '=', d.id), ('kind', '=', 'set_time'),
                '|', ('state', 'in', ('queued', 'sent')),
                '&', ('state', '=', 'done'), ('done_at', '>=', now - SET_TIME_GRACE)],
                limit=1)
            skewed = (len(samples) >= SKEW_MIN_SAMPLES
                      and abs(d.clock_skew_s or 0) > SKEW_LIMIT_S and not fixed)
            lo, hi = d._local_today_bounds_utc(now)
            future = Punch.search_count([
                ('device_id', '=', d.id), ('state', '=', 'ignored_outlier'),
                ('received_at', '>=', lo), ('received_at', '<', hi),
                ('punch_utc', '>', now)])
            if skewed:
                out.append({'kind': 'clock', 'device_id': d.id, 'facet': 'skew',
                            'ref_value': int(d.clock_skew_s or 0)})
            elif future >= FUTURE_IGNORED_MIN:
                # a fast clock nobody could correct: punches dated ahead
                out.append({'kind': 'clock', 'device_id': d.id, 'facet': 'future',
                            'ref_value': future})
            # -- two requests in a row did not work -----------------------------
            last_two = Command.search([('device_id', '=', d.id),
                                       ('state', 'in', ('done', 'failed'))],
                                      order='id desc', limit=2)
            if len(last_two) == 2 and all(c.state == 'failed' for c in last_two):
                out.append({'kind': 'command_failed', 'device_id': d.id,
                            'ref_at': last_two[0].done_at})
            # -- a plain connection in use --------------------------------------
            if d.plain_connection:
                out.append({'kind': 'plain', 'device_id': d.id})
        return out

    @api.model
    def _cond_pending(self, company, now):
        Device = self.env['pb.clock.device'].sudo().with_context(active_test=False)
        rows = Device.search([('company_id', '=', company.id), ('kind', '=', 'terminal'),
                              ('state', '=', 'pending')])
        return [{'kind': 'pending', 'device_id': d.id,
                 'ref_at': d.first_seen_at or d.create_date}
                for d in rows
                if (d.first_seen_at or d.create_date) and
                now - (d.first_seen_at or d.create_date) > PENDING_AFTER]

    @api.model
    def _decided_days(self, emp, days):
        """{day} a person already decided about: closed, approved, or with a
        correction that was not refused."""
        Pairing = self.env['pb.clock.pairing']
        return set(Pairing._guards(emp, set(days)).keys())

    @api.model
    def _cond_auto_closed(self, company, now):
        Att = self.env['hr.attendance'].sudo()
        rows = Att.search([('pb_clock_auto_closed', '=', True),
                           ('employee_id.company_id', '=', company.id),
                           ('check_in', '<', now - AUTO_CLOSED_AFTER)],
                          order='check_in desc', limit=500)
        by_emp = {}
        cache = {}
        for a in rows:
            day = a._pb_local_day(cache)
            if day:
                by_emp.setdefault(a.employee_id, {})[day] = a
        out = []
        for emp, days in by_emp.items():
            decided = self._decided_days(emp, days.keys())
            frozen = self._approved_days(emp, days.keys())
            for day, a in days.items():
                if day in decided or day in frozen:
                    continue
                out.append({'kind': 'auto_closed', 'employee_id': emp.id, 'day': day,
                            'ref_at': a.check_in})
        return out

    @api.model
    def _approved_days(self, emp, days):
        """The days whose week was approved (the pay run reads them as they
        are, so there is nothing left to fix here)."""
        if 'pb.timesheet.freeze' not in self.env:
            return set()
        frozen = self.env['pb.timesheet.freeze'].sudo().frozen_map(
            [(emp.id, d) for d in days])
        return {day for (_e, day), packet in frozen.items()}

    @api.model
    def _cond_held(self, company, now):
        Punch = self.env['pb.clock.punch'].sudo()
        groups = Punch._read_group(
            [('company_id', '=', company.id), ('state', '=', 'held'),
             ('employee_id', '!=', False), ('work_day', '!=', False),
             ('write_date', '<', now - HELD_AFTER)],
            groupby=['employee_id', 'work_day:day'],
            aggregates=['__count', 'write_date:min'], limit=500)
        return [{'kind': 'held', 'employee_id': emp.id, 'day': day, 'ref_value': n,
                 'ref_at': first}
                for emp, day, n, first in groups if emp and day]

    @api.model
    def _cond_backlog(self, company, now):
        Punch = self.env['pb.clock.punch'].sudo()
        waiting = Punch.search_count([('company_id', '=', company.id),
                                      ('state', 'in', ('new', 'matched'))])
        since = company.pb_clock_backlog_since
        if waiting > BACKLOG_HIGH and not since:
            company.sudo().pb_clock_backlog_since = now
            since = now
        elif waiting < BACKLOG_LOW and since:
            company.sudo().pb_clock_backlog_since = False
            since = False
        if not since:
            return []
        key = {'kind': 'backlog'}
        already = self.search_count([('company_id', '=', company.id),
                                     ('key', '=', self._key(key)),
                                     ('state', 'in', ('open', 'muted'))], limit=1)
        if already or now - since >= BACKLOG_FOR:
            return [{'kind': 'backlog', 'ref_value': waiting, 'ref_at': since}]
        return []

    @api.model
    def _cond_recheck(self, company, now):
        if 'pb_clock_last_recheck_fixed' not in company._fields:
            return []
        n = company.pb_clock_last_recheck_fixed or 0
        if n > 0:
            return [{'kind': 'recheck_changed', 'ref_value': n,
                     'ref_at': company.pb_clock_last_recheck_at}]
        return []

    # ============================================================== the words
    def _tz(self):
        name = (self.device_id.tz if self.device_id else False) \
            or self.company_id.resource_calendar_id.tz or 'UTC'
        try:
            return pytz.timezone(name)
        except Exception:  # noqa: BLE001
            return pytz.UTC

    def _when(self, dt, now=None):
        """'14:02' today, 'yesterday 14:02', 'Tue 14:02' this week, '05 Nov'
        before — in the machine's zone, which is named when it is not the
        company's ('14:02 Sydney time')."""
        self.ensure_one()
        if not dt:
            return ''
        now = now or fields.Datetime.now()
        tz = self._tz()
        local = pytz.UTC.localize(dt).astimezone(tz)
        today = pytz.UTC.localize(now).astimezone(tz).date()
        if local.date() == today:
            text = local.strftime('%H:%M')
        elif local.date() == today - timedelta(days=1):
            text = _("yesterday %s") % local.strftime('%H:%M')
        elif (today - local.date()).days < 7:
            text = local.strftime('%a %H:%M')
        else:
            text = local.strftime('%d %b')
        company_tz = self.company_id.resource_calendar_id.tz or 'UTC'
        if self.device_id and self.device_id.tz and self.device_id.tz != company_tz:
            city = self.device_id.tz.split('/')[-1].replace('_', ' ')
            text = _("%(time)s %(city)s time", time=text, city=city)
        return text

    def _machine(self):
        d = self.device_id
        return (d.name if d.name and d.name != d.serial else '') or d.serial or _("A machine")

    def _sentence(self, now=None):
        """One plain sentence, in the reader's language (env.lang)."""
        self.ensure_one()
        k = self.kind
        n = self.ref_value or 0
        if k == 'silent':
            return _("%(machine)s has not called in since %(time)s.",
                     machine=self._machine(), time=self._when(self.ref_at, now))
        if k == 'no_punches':
            if self.facet == 'since' and self.ref_at:
                return _("No punch on %(machine)s since %(time)s, on a working day.",
                         machine=self._machine(), time=self._when(self.ref_at, now))
            return _("No punch on %(machine)s yet today, a working day.",
                     machine=self._machine())
        if k == 'clock':
            if self.facet == 'future':
                return _("%(machine)s sent %(n)s punches dated in the future today: "
                         "its clock looks wrong.", machine=self._machine(), n=n)
            mins = max(1, round(abs(n) / 60.0))
            if n > 0:
                return _("%(machine)s's clock is %(n)s min fast and could not be set.",
                         machine=self._machine(), n=mins)
            return _("%(machine)s's clock is %(n)s min slow and could not be set.",
                     machine=self._machine(), n=mins)
        if k == 'command_failed':
            return _("%(machine)s did not carry out the last two requests sent to it.",
                     machine=self._machine())
        if k == 'pending':
            return _("Machine %(serial)s has been asking to connect since %(day)s.",
                     serial=self.device_id.serial or self._machine(),
                     day=self._when(self.ref_at, now))
        if k == 'plain':
            return _("%(machine)s sends over a plain connection. Ask the supplier "
                     "for a firmware update that can connect securely.",
                     machine=self._machine())
        if k == 'auto_closed':
            return _("%(name)s has no check-out on %(day)s.",
                     name=self.employee_id.name or '', day=self._day_label())
        if k == 'held':
            return (_("1 punch of %(name)s on %(day)s has been on hold for more "
                      "than a day.", name=self.employee_id.name or '',
                      day=self._day_label()) if n == 1 else
                    _("%(n)s punches of %(name)s on %(day)s have been on hold for "
                      "more than a day.", n=n, name=self.employee_id.name or '',
                      day=self._day_label()))
        if k == 'backlog':
            return _("%s punches are waiting to be paired.") % '{:,}'.format(n)
        if k == 'recheck_changed':
            return (_("Last night's re-check changed 1 day to match its punches.")
                    if n == 1 else
                    _("Last night's re-check changed %s days to match their punches.") % n)
        return dict(KINDS).get(k, k)

    def _day_label(self):
        return self.day.strftime('%a %d %b') if self.day else ''

    # ================================================================ readers
    @api.model
    def _open(self, company_ids):
        return self.sudo().search([('company_id', 'in', list(company_ids)),
                                   ('state', '=', 'open')])

    @api.model
    def _items(self, company_ids, now=None):
        """The open alerts as the strip reads them: one row per machine alert,
        one row per kind for the people's days. Sorted by `ORDER`. Words in
        the caller's language. A READ."""
        now = now or fields.Datetime.now()
        alerts = self._open(company_ids)
        if not alerts:
            return []
        # words in the caller's language, not the superuser's
        alerts = alerts.with_context(lang=self.env.lang)
        items = []
        for kind in ORDER:
            rows = alerts.filtered(lambda a, k=kind: a.kind == k)
            if not rows:
                continue
            if kind in PERSON_KINDS and len(rows) > 1:
                items.append(self._group_item(kind, rows))
                continue
            for a in rows.sorted('first_seen_at'):
                items.append({
                    'key': a.key, 'kind': kind, 'ids': [a.id],
                    'text': a._sentence(now),
                    'since': fields.Datetime.to_string(a.first_seen_at) if a.first_seen_at else '',
                    'icon': ICON.get(kind, 'alert'),
                    'tone': 'slate' if kind in QUIET_KINDS else 'amber',
                    'door': self._door(a),
                    'device_id': a.device_id.id or False,
                    'employee_id': a.employee_id.id or False,
                    'day': fields.Date.to_string(a.day) if a.day else '',
                })
        return items

    @api.model
    def _group_item(self, kind, rows):
        n = len(rows)
        if kind == 'auto_closed':
            text = _("%s days are missing a check-out for more than two days.") % n
        else:
            punches = sum(rows.mapped('ref_value')) or n
            text = _("%(n)s punches on %(days)s days have been on hold for more "
                     "than a day.", n=punches, days=n)
        first = min(rows.mapped('first_seen_at'))
        return {
            'key': kind, 'kind': kind, 'ids': rows.ids, 'text': text,
            'since': fields.Datetime.to_string(first) if first else '',
            'icon': ICON.get(kind, 'alert'), 'tone': 'amber',
            'door': {'block': 'missing' if kind == 'auto_closed' else 'held'},
            'device_id': False, 'employee_id': False, 'day': '',
        }

    @api.model
    def _door(self, a):
        if a.kind == 'pending':
            return {'block': 'pending'}
        if a.kind == 'auto_closed':
            return {'block': 'missing'}
        if a.kind == 'held':
            return {'block': 'held'}
        if a.kind == 'recheck_changed':
            return {'block': 'settings'}
        if a.kind == 'backlog':
            return {'block': 'machines'}
        return {'block': 'machine', 'device_id': a.device_id.id}

    @api.model
    def _count(self, company_ids):
        """How many things need attention (the strip's rows)."""
        return len(self._items(company_ids))

    # ===================================================== other surfaces
    @api.model
    def _may_read(self):
        u = self.env.user
        return self.env.su or u.has_group(_OFFICER) or u.has_group('base.group_system')

    @api.model
    def _integrations_card(self):
        """The "Time clocks" row on the Integrations board (§4.3): connected
        when every machine is fine, error when one is silent / its clock is
        off / its requests fail, disconnected when no machine is let in yet.
        None for a reader who is not an attendance officer. A READ."""
        if not self._may_read():
            return None
        cids = self.env.companies.ids or [self.env.company.id]
        Device = self.env['pb.clock.device'].sudo()
        # every machine let in: one that pushes, or one whose punches come by file
        terminals = Device.search([('company_id', 'in', cids), ('kind', '=', 'terminal'),
                                   ('state', '=', 'allowed')])
        pending = Device.with_context(active_test=False).search_count(
            [('kind', '=', 'terminal'), ('state', '=', 'pending')])
        uploads = Device.search([('company_id', 'in', cids), ('kind', '=', 'upload')])
        alerts = self._open(cids)
        items = self._items(cids)
        if not terminals:
            status = 'disconnected'
        elif any(a.kind in ERROR_KINDS for a in alerts):
            status = 'error'
        else:
            status = 'connected'
        label = {'connected': _("Connected"), 'error': _("Needs attention"),
                 'disconnected': _("No machine yet")}[status]
        devices = len({a.device_id.id for a in alerts
                       if a.kind in DEVICE_KINDS and a.device_id})
        missing = len(alerts.filtered(lambda a: a.kind == 'auto_closed'))
        held = len(alerts.filtered(lambda a: a.kind == 'held'))
        hints = []
        if devices:
            hints.append({'kind': 'machines', 'count': devices, 'block': 'machines',
                          'label': (_("1 machine needs attention") if devices == 1
                                    else _("%s machines need attention") % devices)})
        if missing:
            hints.append({'kind': 'missing', 'count': missing, 'block': 'missing',
                          'label': (_("1 day missing a check-out") if missing == 1
                                    else _("%s days missing a check-out") % missing)})
        if held:
            hints.append({'kind': 'held', 'count': held, 'block': 'held',
                          'label': (_("1 day with punches on hold") if held == 1
                                    else _("%s days with punches on hold") % held)})
        last = max([d.last_punch_at for d in (terminals | uploads) if d.last_punch_at]
                   or [False])
        return {
            'name': _("Time clocks"),
            'status': status, 'status_label': label,
            'status_cls': {'connected': 'ok', 'error': 'err'}.get(status, 'muted'),
            'machines': len(terminals), 'pending': pending,
            'last_punch_at': fields.Datetime.to_string(last) if last else '',
            'attention': len(items),
            'top': items[0]['text'] if items else '',
            'hints': hints,
        }

    @api.model
    def _home_need(self):
        """{n, text} for the Home "needs you" chips (§4.4); n = 0 hides it.
        Officers only. A READ."""
        if not self._may_read():
            return {'n': 0, 'text': ''}
        items = self._items(self.env.companies.ids or [self.env.company.id])
        return {'n': len(items), 'text': items[0]['text'] if items else ''}

    # ================================================================== mute
    def _mute(self, now=None):
        now = now or fields.Datetime.now()
        rows = self.sudo().filtered(lambda a: a.state == 'open')
        rows.write({'state': 'muted', 'muted_until': now + MUTE_FOR})
        return rows

    def _unmute(self):
        rows = self.sudo().filtered(lambda a: a.state == 'muted')
        rows.write({'state': 'open', 'muted_until': False})
        return rows

    # ================================================================ emails
    @api.model
    def _managers(self, company):
        """Attendance managers of the company with an email — internal users
        only, never an employee's portal login (§4.5)."""
        group = self.env.ref(_MANAGER, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        users = group.sudo().all_user_ids.filtered(
            lambda u: u.active and not u.share and u.email
            and company in u.company_ids)
        return users

    @api.model
    def _lens_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        return '%s/odoo/action-pb_clock.action_pb_clock_lens' % base.rstrip('/')

    @api.model
    def _mail_company(self, company, now):
        """The 08:00 summary (once a day) and the immediate 'a machine stopped'
        note (once per machine per 6 hours, working days only)."""
        sent = 0
        if not company.pb_clock_alert_mail:
            return 0
        managers = self._managers(company)
        if not managers:
            return 0
        sent += self._send_immediate(company, managers, now)
        sent += self._send_digest(company, managers, now)
        return sent

    @api.model
    def _company_local_now(self, company, now):
        try:
            tz = pytz.timezone(company.resource_calendar_id.tz or 'UTC')
        except Exception:  # noqa: BLE001
            tz = pytz.UTC
        return pytz.UTC.localize(now).astimezone(tz).replace(tzinfo=None)

    @api.model
    def _by_lang(self, users):
        out = {}
        for u in users:
            out.setdefault(u.lang or 'en_US', []).append(u)
        return out

    @api.model
    def _send_digest(self, company, managers, now):
        local = self._company_local_now(company, now)
        if not (DIGEST_HOURS[0] <= local.hour < DIGEST_HOURS[1]):
            return 0
        if company.pb_clock_digest_sent_on == local.date():
            return 0
        if not self._open([company.id]):
            return 0
        sent = 0
        for lang, users in self._by_lang(managers).items():
            Alert = self.with_context(lang=lang)
            items = Alert._items([company.id], now)
            if not items:
                continue
            n = len(items)
            subject = (Alert._t_one_thing() if n == 1 else Alert._t_n_things(n))
            sent += Alert._send(company, users, subject, Alert._t_digest_intro(),
                                [i['text'] for i in items])
        if sent:
            company.sudo().pb_clock_digest_sent_on = local.date()
        return sent

    @api.model
    def _send_immediate(self, company, managers, now):
        due = self.search([('company_id', '=', company.id), ('state', '=', 'open'),
                           ('kind', 'in', IMMEDIATE_KINDS), ('last_mailed_at', '=', False)])
        sent = 0
        for a in due:
            d = a.device_id
            if not d:
                continue
            local_day = pytz.UTC.localize(now).astimezone(d._tzinfo()).date()
            if not self._is_working_day(company, local_day):
                continue
            recent = self.search_count([
                ('device_id', '=', d.id), ('kind', 'in', IMMEDIATE_KINDS),
                ('last_mailed_at', '>=', now - IMMEDIATE_EVERY)], limit=1)
            if recent:
                continue
            for lang, users in self._by_lang(managers).items():
                A = a.with_context(lang=lang)
                subject = A._t_machine_subject(A._machine()) if a.kind == 'silent' \
                    else A._t_no_punch_subject(A._machine())
                sent += A._send(company, users, subject, A._sentence(now),
                                [A._t_what_to_check()])
            a.write({'last_mailed_at': now})
        return sent

    @api.model
    def _send(self, company, users, subject, intro, lines):
        template = self.env.ref('pb_clock.mail_template_clock_alerts',
                                raise_if_not_found=False)
        if not template:
            _logger.warning("pb_clock: the time-clock alert email is missing")
            return 0
        to = ','.join(u.email_formatted or u.email for u in users)
        ctx = {
            'pb_subject': subject, 'pb_intro': intro, 'pb_lines': lines,
            'pb_url': self._lens_url(), 'pb_button': self._t_open_button(),
            'pb_footer': self._t_footer(), 'pb_hello': self._t_hello(),
        }
        template.sudo().with_context(**ctx).send_mail(
            company.id, force_send=False,
            email_values={'email_to': to, 'recipient_ids': [(6, 0, [])]})
        return 1

    # the words of the emails, in the language the recordset carries
    def _t_one_thing(self):
        return _("Time clocks: 1 thing needs attention")

    def _t_n_things(self, n):
        return _("Time clocks: %s things need attention") % n

    def _t_digest_intro(self):
        return _("This is this morning's summary of the time clocks. Each line "
                 "is something a person needs to look at:")

    def _t_machine_subject(self, machine):
        return _("Time clocks: %s has stopped calling in") % machine

    def _t_no_punch_subject(self, machine):
        return _("Time clocks: no punches on %s") % machine

    def _t_what_to_check(self):
        return _("Check that the machine has power and its network cable or "
                 "Wi-Fi, then restart it. Its punches are kept on the machine and "
                 "arrive as soon as it calls in again.")

    def _t_open_button(self):
        return _("Open Time clocks")

    def _t_hello(self):
        return _("Hello,")

    def _t_footer(self):
        return _("You receive this because you manage attendance for this company.")

