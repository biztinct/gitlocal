# -*- coding: utf-8 -*-
"""pb.clock.lens — the RPC facade behind the Time clocks lens (CLOCK ledger D8).

Officer-gated, company-scoped, every block built under `_safe` so one bad
record never blanks the lens (orgchart ledger rule 9). `get_lens` is a pure
READ (it never creates the upload device, never pairs). Every write RPC checks
its right on the server and answers {'error': 'plain sentence'} instead of
raising (`pb.people.bulk_apply` style).
"""

import logging
from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_OFFICER = 'hr_attendance.group_hr_attendance_officer'
_MANAGER = 'hr_attendance.group_hr_attendance_manager'
_RECENT_PAGE = 200
_QUIET_AFTER = timedelta(hours=2)

STATE_CHIP = {
    'new': ('waiting', 'slate'),
    'unmatched': ('unknown', 'amber'),
    'matched': ('waiting', 'slate'),
    'middle': ('break', 'slate'),
    'held': ('held', 'amber'),
    'ignored_duplicate_tap': ('double', 'slate'),
    'ignored_outlier': ('ignored', 'slate'),
    'ignored_before_start': ('before', 'slate'),
}


class PbClockLens(models.AbstractModel):
    _name = 'pb.clock.lens'
    _description = 'Time clocks lens'

    # ------------------------------------------------------------ access
    @api.model
    def _is_officer(self):
        u = self.env.user
        return self.env.su or u.has_group(_OFFICER) or u.has_group('base.group_system')

    @api.model
    def _is_manager(self):
        u = self.env.user
        return self.env.su or u.has_group(_MANAGER) or u.has_group('base.group_system')

    @api.model
    def _require_officer(self):
        if not self._is_officer():
            from odoo.exceptions import AccessError
            raise AccessError(_("Time clocks are for attendance officers."))

    @api.model
    def _company_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    @api.model
    def _tz(self):
        name = self.env.company.resource_calendar_id.tz or self.env.user.tz or 'UTC'
        try:
            return pytz.timezone(name)
        except Exception:  # noqa: BLE001
            return pytz.UTC

    @api.model
    def _week(self, week_start):
        df = self.env['hr.attendance.weekentry']._monday(week_start)
        return df, df + timedelta(days=6)

    @api.model
    def _local_window(self, d_from, d_to):
        """[lo, hi) naive UTC of local days d_from..d_to in the company zone."""
        tz = self._tz()
        lo = tz.localize(datetime.combine(d_from, datetime.min.time()))
        hi = tz.localize(datetime.combine(d_to + timedelta(days=1), datetime.min.time()))
        return (lo.astimezone(pytz.UTC).replace(tzinfo=None),
                hi.astimezone(pytz.UTC).replace(tzinfo=None))

    @api.model
    def _safe(self, fn, default):
        try:
            with self.env.cr.savepoint(flush=False):
                return fn()
        except Exception:  # noqa: BLE001 — one block never blanks the lens
            _logger.warning("Time clocks lens: a block failed", exc_info=True)
            return default

    @api.model
    def _dt(self, value):
        return fields.Datetime.to_string(value) if value else ''

    # ------------------------------------------------------------ badge
    @api.model
    def _unknown_count(self, week_start):
        """Unknown numbers with punches in the week — the lens badge (D8)."""
        df, dt = self._week(week_start)
        lo, hi = self._local_window(df, dt)
        rows = self.env['pb.clock.punch'].sudo()._read_group(
            [('company_id', 'in', self._company_ids()), ('state', '=', 'unmatched'),
             ('punch_utc', '>=', lo), ('punch_utc', '<', hi)],
            groupby=['user_code'], aggregates=['__count'])
        return len(rows)

    # ------------------------------------------------------------ read
    @api.model
    def get_lens(self, week_start=False, department_id=False, person_id=False,
                 codes=None, filters=None):
        """Everything the lens shows. A READ: it writes nothing."""
        self._require_officer()
        df, dt = self._week(week_start)
        filters = filters or {}
        now = fields.Datetime.now()
        devices = self._safe(lambda: self._devices(now), [])
        pending = self._safe(lambda: self._pending(), [])
        return {
            'week_start': df.isoformat(),
            'week_end': dt.isoformat(),
            'now': self._dt(now),
            'can_manage': self._is_manager(),
            'hero': self._safe(lambda: self._hero(now, devices), {'state': 'empty'}),
            'devices': devices,
            'unknown': self._safe(lambda: self._unknown(df, dt, codes or []),
                                  {'rows': [], 'total': 0, 'week': 0}),
            'held': self._safe(lambda: self._held(), {'rows': [], 'total': 0}),
            'recent': self._safe(
                lambda: self._recent(df, dt, department_id, person_id, filters),
                {'rows': [], 'total': 0}),
            'waiting': self._safe(lambda: self.env['pb.clock.punch'].sudo().search_count(
                [('company_id', 'in', self._company_ids()),
                 ('state', 'in', ('new', 'matched'))]), 0),
            'settings': self._safe(self._settings, {}),
            'focus_codes': [str(c) for c in (codes or [])][:50],
            'pending': pending,
            'zones': list(pytz.common_timezones) if pending else [],
            'blocked': self._safe(lambda: self._blocked(), []),
            'missing_checkout': self._safe(lambda: self._missing_checkout(),
                                           {'rows': [], 'total': 0}),
            'address': self._safe(self._address, {}),
        }

    @api.model
    def _settings(self):
        c = self.env.company
        return {'max_span_h': c.pb_clock_max_span_h,
                'double_tap_min': c.pb_clock_double_tap_min,
                'trust_direction': c.pb_clock_trust_direction,
                'allow_plain': c.pb_clock_allow_plain}

    @api.model
    def _address(self):
        """What HR types into the machine: this workspace's own address."""
        host = ''
        try:
            from odoo.http import request
            if request and request.httprequest:
                host = (request.httprequest.host or '').split(':')[0]
        except Exception:  # noqa: BLE001
            host = ''
        if not host:
            base = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
            host = base.split('://')[-1].split('/')[0].split(':')[0]
        return {'host': host, 'port': 443, 'plain_port': 80,
                'plain_on': bool(self.env.company.pb_clock_allow_plain)}

    @api.model
    def _pending(self):
        """Machines asking to connect — the whole database (a database is one
        tenant; the manager places the machine in a company on Allow)."""
        Device = self.env['pb.clock.device'].sudo().with_context(active_test=False)
        rows = Device.search([('state', '=', 'pending'), ('kind', '=', 'terminal')],
                             order='first_seen_at desc, id desc', limit=50)
        return [{
            'id': d.id, 'serial': d.serial or '', 'ip': d.ip or '',
            'firmware': d.firmware or (('push %s' % d.pushver) if d.pushver else ''),
            'first_seen_at': self._dt(d.first_seen_at or d.create_date),
            'last_seen_at': self._dt(d.last_seen_at),
            'name': d.name if d.name and d.name != d.serial else '',
            'location': d.location or '',
            'tz': d.tz or self.env.company.resource_calendar_id.tz or 'UTC',
            'history_from': fields.Date.to_string(d._default_history_from()),
            'known': bool(self.env['pb.clock.punch'].sudo().search_count(
                [('device_id', '=', d.id)], limit=1)),
        } for d in rows]

    @api.model
    def _blocked(self):
        Device = self.env['pb.clock.device'].sudo().with_context(active_test=False)
        rows = Device.search([('state', '=', 'blocked'), ('kind', '=', 'terminal'),
                              '|', ('company_id', 'in', self._company_ids()),
                              ('allowed_at', '=', False)],
                             order='last_seen_at desc, id desc', limit=50)
        return [{'id': d.id, 'serial': d.serial or '', 'name': d.name or '',
                 'last_seen_at': self._dt(d.last_seen_at)} for d in rows]

    @api.model
    def _missing_checkout(self):
        """D11: days the time clock closed at their own check-in."""
        Att = self.env['hr.attendance'].sudo()
        rows = Att.search([('pb_clock_auto_closed', '=', True),
                           ('employee_id.company_id', 'in', self._company_ids())],
                          order='check_in desc', limit=200)
        total = Att.search_count([('pb_clock_auto_closed', '=', True),
                                  ('employee_id.company_id', 'in', self._company_ids())])
        Corr = self.env['hr.attendance.correction'].sudo() \
            if 'hr.attendance.correction' in self.env else None
        out = []
        cache = {}
        for a in rows:
            try:
                day = a._pb_local_day(cache)
                emp = a.employee_id
                tz = pytz.timezone(emp._get_tz() or 'UTC')
                local_in = pytz.UTC.localize(a.check_in).astimezone(tz)
                filed = bool(Corr and Corr.search_count([
                    ('employee_id', '=', emp.id), ('date', '=', day),
                    ('state', '!=', 'refused')], limit=1))
                out.append({
                    'id': a.id, 'employee_id': emp.id, 'name': emp.name,
                    'day': fields.Date.to_string(day),
                    'day_label': day.strftime('%a %d %b'),
                    'check_in': local_in.strftime('%H:%M'),
                    'filed': filed,
                    'note': _("Check-out missing; closed so later days can be paired."),
                })
            except Exception as exc:  # noqa: BLE001
                _logger.debug("Time clocks lens: missing check-out %s: %s", a.id, exc)
        return {'rows': out, 'total': total}

    @api.model
    def _devices(self, now):
        Device = self.env['pb.clock.device'].sudo()
        devices = Device.search([('company_id', 'in', self._company_ids())])
        Punch = self.env['pb.clock.punch'].sudo()
        out = []
        for d in devices:
            lo, hi = d._local_today_bounds_utc(now)
            today = Punch.search_count([('device_id', '=', d.id),
                                        ('punch_utc', '>=', lo), ('punch_utc', '<', hi)])
            total = Punch.search_count([('device_id', '=', d.id)])
            if d.kind == 'upload' and not total:
                continue        # the pseudo device shows once it holds a punch
            if d.kind == 'terminal' and d.state in ('pending', 'blocked'):
                continue        # the strip / the ignored list show these
            row = {
                'id': d.id, 'name': d.name, 'location': d.location or '',
                'kind': d.kind, 'serial': d.serial or '', 'tz': d.tz or '',
                'allowed': d.allowed, 'last_punch_at': self._dt(d.last_punch_at),
                'punches_today': today, 'punches_total': total,
                'state': d.state, 'listening': d.kind == 'terminal' and d._listening(),
            }
            if row['listening']:
                last_cmd = self.env['pb.clock.command'].sudo().search(
                    [('device_id', '=', d.id), ('kind', '!=', 'set_time')],
                    order='id desc', limit=1)
                row.update({
                    'last_seen_at': self._dt(d.last_seen_at),
                    'ip': d.ip or '', 'lan_ip': d.lan_ip or '',
                    'firmware': d.firmware or '',
                    'plain': bool(d.plain_connection),
                    'skew_s': d.clock_skew_s or 0,
                    'skew_n': len(d._skew_list()),
                    'corrected_at': self._dt(d.clock_corrected_at),
                    'corrected_by_s': d.clock_corrected_by_s or 0,
                    'history_from': fields.Date.to_string(d.history_from) if d.history_from else '',
                    'before_start': Punch.search_count([
                        ('device_id', '=', d.id), ('state', '=', 'ignored_before_start')]),
                    'users_count': d.users_count or 0,
                    'attlog_count': d.attlog_count or 0,
                    'command': ({
                        'id': last_cmd.id, 'kind': last_cmd.kind, 'state': last_cmd.state,
                        'queued_at': self._dt(last_cmd.queued_at),
                        'done_at': self._dt(last_cmd.done_at),
                        'since': fields.Date.to_string(last_cmd.since) if last_cmd.since else '',
                        'note': last_cmd.note or '',
                    } if last_cmd else False),
                })
            out.append(row)
        out.sort(key=lambda r: (r['kind'] == 'upload', r['name'].lower()))
        return out

    @api.model
    def _working_today(self, local_today):
        cal = self.env.company.resource_calendar_id
        if not cal:
            return local_today.weekday() < 5
        days = {int(a.dayofweek) for a in cal.attendance_ids}
        return local_today.weekday() in days

    @api.model
    def _hero(self, now, devices):
        Punch = self.env['pb.clock.punch'].sudo()
        cids = self._company_ids()
        last = Punch.search([('company_id', 'in', cids)], order='punch_utc desc', limit=1)
        if not last:
            return {'state': 'empty'}
        tz = self._tz()
        local_today = pytz.UTC.localize(now).astimezone(tz).date()
        lo, hi = self._local_window(local_today, local_today)
        people = Punch._read_group(
            [('company_id', 'in', cids), ('punch_utc', '>=', lo), ('punch_utc', '<', hi),
             ('employee_id', '!=', False)],
            groupby=['employee_id'], aggregates=['__count'])
        quiet = (now - last.punch_utc > _QUIET_AFTER) and self._working_today(local_today)
        return {
            'state': 'quiet' if quiet else 'live',
            'last_punch_at': self._dt(last.punch_utc),
            'device': last.device_id.name or '',
            'people_today': len(people),
            'machines': len([d for d in devices if d['kind'] == 'terminal']),
        }

    @api.model
    def _suggest(self, company, codes):
        """{code: {id, name}} — a person whose number differs only by leading
        zeros, or whose badge / ID number now equals the code exactly."""
        variants = {}
        for c in codes:
            core = c.lstrip('0') or c
            for v in {c, core} | {('0' * k) + core for k in range(1, 5)}:
                variants.setdefault(v, set()).add(c)
        index = self.env['pb.clock.pairing']._code_index(company, list(variants))
        out = {}
        for v, emp in index.items():
            if not emp.active:
                continue
            for c in variants.get(v, ()):
                hit = out.get(c)
                if hit is None:
                    out[c] = {'id': emp.id, 'name': emp.name}
                elif hit['id'] != emp.id:
                    out[c] = False      # two candidates: no suggestion
        return {c: s for c, s in out.items() if s}

    @api.model
    def _unknown(self, df, dt, focus):
        Punch = self.env['pb.clock.punch'].sudo()
        lo, hi = self._local_window(df, dt)
        dom = [('company_id', 'in', self._company_ids()), ('state', '=', 'unmatched')]
        groups = Punch._read_group(dom, groupby=['user_code'],
                                   aggregates=['punch_utc:min', 'punch_utc:max', '__count'])
        week_codes = {g[0] for g in Punch._read_group(
            dom + [('punch_utc', '>=', lo), ('punch_utc', '<', hi)],
            groupby=['user_code'], aggregates=['__count'])}
        codes = [g[0] for g in groups]
        sugg = self._suggest(self.env.company, codes) if codes else {}
        focus = {str(c) for c in focus}
        rows = [{
            'code': code, 'first_seen': self._dt(first), 'last_seen': self._dt(last),
            'punches': n, 'this_week': code in week_codes,
            'focus': code in focus, 'suggestion': sugg.get(code) or False,
        } for code, first, last, n in groups]
        # newest first, then the numbers asked about and this week's on top
        rows.sort(key=lambda r: r['last_seen'], reverse=True)
        rows.sort(key=lambda r: (not r['focus'], not r['this_week']))
        return {'rows': rows[:300], 'total': len(rows), 'week': len(week_codes)}

    @api.model
    def _held(self):
        Punch = self.env['pb.clock.punch'].sudo()
        groups = Punch._read_group(
            [('company_id', 'in', self._company_ids()), ('state', '=', 'held')],
            groupby=['employee_id', 'work_day:day', 'note'], aggregates=['__count'],
            order='work_day:day desc', limit=200)
        rows = []
        for emp, day, note, n in groups:
            rows.append({
                'employee_id': emp.id if emp else False,
                'name': emp.name if emp else '',
                'day': fields.Date.to_string(day) if day else '',
                'day_label': day.strftime('%a %d %b') if day else '',
                'note': note or '', 'punches': n,
            })
        return {'rows': rows, 'total': len(rows)}

    @api.model
    def _recent(self, df, dt, department_id, person_id, filters):
        Punch = self.env['pb.clock.punch'].sudo()
        dom = [('company_id', 'in', self._company_ids())]
        period = filters.get('period') or 'week'
        if period == 'today':
            tz = self._tz()
            today = pytz.UTC.localize(fields.Datetime.now()).astimezone(tz).date()
            lo, hi = self._local_window(today, today)
        else:
            lo, hi = self._local_window(df, dt)
        dom += [('punch_utc', '>=', lo), ('punch_utc', '<', hi)]
        if filters.get('device_id'):
            dom.append(('device_id', '=', int(filters['device_id'])))
        if person_id:
            dom.append(('employee_id', '=', int(person_id)))
        elif department_id:
            dom.append(('employee_id.department_id', '=', int(department_id)))
        state = filters.get('state') or 'all'
        if state == 'unknown':
            dom.append(('state', '=', 'unmatched'))
        elif state == 'held':
            dom.append(('state', '=', 'held'))
        elif state == 'ignored':
            dom.append(('state', 'in', ('ignored_duplicate_tap', 'ignored_outlier',
                                        'ignored_before_start')))
        elif state == 'counted':
            dom.append(('state', 'in', ('paired', 'middle')))
        if filters.get('code'):
            dom.append(('user_code', '=', str(filters['code'])))
        offset = int(filters.get('offset') or 0)
        total = Punch.search_count(dom)
        recs = Punch.search(dom, order='punch_utc desc, id desc',
                            limit=_RECENT_PAGE, offset=offset)
        rows = []
        for p in recs:
            try:
                rows.append(self._punch_row(p))
            except Exception as exc:  # noqa: BLE001
                _logger.debug("Time clocks lens: punch row %s: %s", p.id, exc)
        return {'rows': rows, 'total': total, 'offset': offset,
                'more': offset + len(rows) < total}

    @api.model
    def _punch_row(self, p):
        if p.state == 'paired':
            att = p.attendance_id
            kind = 'out' if (att and att.check_out and p.punch_utc == att.check_out
                             and p.punch_utc != att.check_in) else 'in'
            tone = 'indigo'
        else:
            kind, tone = STATE_CHIP.get(p.state, ('waiting', 'slate'))
        return {
            'id': p.id,
            'time': p.punch_local.strftime('%H:%M') if p.punch_local else '',
            'seconds': p.punch_local.strftime(':%S') if p.punch_local else '',
            'day': p.punch_local.strftime('%a %d %b') if p.punch_local else '',
            'employee_id': p.employee_id.id or False,
            'name': p.employee_id.name or '',
            'code': p.user_code,
            'device': p.device_id.name or '',
            'device_id': p.device_id.id,
            'kind': kind, 'tone': tone,
            'state': p.state,
            'note': p.note or '',
            'work_day': fields.Date.to_string(p.work_day) if p.work_day else '',
        }

    @api.model
    def search_people(self, query, limit=8):
        """Typeahead for "Assign": active people first, then people who have
        left (a leaver's late punches still belong to them). A READ."""
        self._require_officer()
        q = str(query or '').strip()
        if not q:
            return []
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        dom = [('company_id', 'in', self._company_ids()), '|', '|', '|',
               ('name', 'ilike', q), ('barcode', '=ilike', q + '%'),
               ('pb_clock_code', '=ilike', q + '%'),
               ('identification_id', '=ilike', q + '%')]
        recs = Emp.search(dom, order='active desc, name', limit=int(limit or 8))
        return [{'id': e.id, 'name': e.name, 'active': e.active,
                 'badge': e.barcode or '', 'clock': e.pb_clock_code or '',
                 'dept': e.department_id.name or '',
                 'avatar': '/web/image/hr.employee/%s/avatar_128' % e.id}
                for e in recs]

    # ------------------------------------------------------------ writes
    @api.model
    def _employee_in_scope(self, employee_id):
        emp = self.env['hr.employee'].sudo().with_context(active_test=False).browse(
            int(employee_id or 0)).exists()
        if not emp or emp.company_id.id not in self._company_ids():
            return None
        return emp

    @api.model
    def _repair_code_backlog(self, company_ids, code, emp):
        """Give every unknown punch of `code` to `emp` and pair them."""
        Punch = self.env['pb.clock.punch'].sudo()
        backlog = Punch.search([('company_id', 'in', company_ids),
                                ('company_id', '=', emp.company_id.id),
                                ('user_code', '=', code), ('state', '=', 'unmatched')],
                               order='punch_utc, id')
        if not backlog:
            return 0
        backlog.write({'employee_id': emp.id, 'state': 'matched', 'note': False})
        summary = {'matched': 0, 'unmatched': 0, 'paired_days': 0, 'held': 0,
                   'ignored': 0, 'more': False}
        self.env['pb.clock.pairing'].sudo()._pair_employee(
            emp, backlog[0].punch_utc, summary)
        return len(backlog)

    @api.model
    def assign_code(self, code, employee_id):
        """Give `code` to a person and pair everything that number punched."""
        if not self._is_officer():
            return {'error': _("Only attendance officers can match numbers to people.")}
        code = str(code or '').strip()
        if not code:
            return {'error': _("Which number? None was given.")}
        emp = self._employee_in_scope(employee_id)
        if not emp:
            return {'error': _("That person is not in this company.")}
        current = (emp.pb_clock_code or '').strip()
        if current and current != code:
            return {'error': _(
                "%(name)s already has clock number %(code)s. Change it on their "
                "employee record first.", name=emp.name, code=current)}
        try:
            with self.env.cr.savepoint():
                if current != code:
                    emp.write({'pb_clock_code': code})
                n = self._repair_code_backlog(self._company_ids(), code, emp)
        except ValidationError as exc:
            return {'error': str(exc.args[0] if exc.args else exc)}
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Time clocks: assign failed", exc_info=True)
            return {'error': _("The number could not be assigned: %s") % exc}
        return {
            'ok': True, 'paired': n,
            'message': (_("Number %(code)s is now %(name)s · 1 punch paired",
                          code=code, name=emp.name) if n == 1 else
                        _("Number %(code)s is now %(name)s · %(n)s punches paired",
                          code=code, name=emp.name, n=n)),
        }

    @api.model
    def auto_match(self):
        """Unknown numbers that now equal exactly one person's clock number,
        badge ID or ID number → matched in bulk. Never guesses."""
        if not self._is_officer():
            return {'error': _("Only attendance officers can match numbers to people.")}
        Punch = self.env['pb.clock.punch'].sudo()
        cids = self._company_ids()
        codes = sorted({g[0] for g in Punch._read_group(
            [('company_id', 'in', cids), ('state', '=', 'unmatched')],
            groupby=['user_code'], aggregates=['__count'])})
        if not codes:
            return {'ok': True, 'assigned': 0, 'ambiguous': [],
                    'message': _("Every number matches a person.")}
        Emp = self.env['hr.employee'].sudo()
        company = self.env.company
        cands = Emp.search([('company_id', '=', company.id), '|', '|',
                            ('pb_clock_code', 'in', codes), ('barcode', 'in', codes),
                            ('identification_id', 'in', codes)])
        hits = {}
        for e in cands:
            for v in {(e.pb_clock_code or '').strip(), (e.barcode or '').strip(),
                      (e.identification_id or '').strip()}:
                if v in codes:
                    hits.setdefault(v, set()).add(e.id)
        assigned, ambiguous = 0, []
        for code in codes:
            ids = hits.get(code) or set()
            if len(ids) > 1:
                ambiguous.append(code)
                continue
            if len(ids) == 1:
                emp = Emp.browse(list(ids)[0])
                try:
                    with self.env.cr.savepoint():
                        self._repair_code_backlog(cids, code, emp)
                    assigned += 1
                except Exception:  # noqa: BLE001
                    _logger.warning("Time clocks: auto-match %s failed", code,
                                    exc_info=True)
        if assigned:
            msg = (_("1 number matched to a person") if assigned == 1
                   else _("%s numbers matched to people") % assigned)
        else:
            msg = _("No number equals a person's clock number, badge ID or ID "
                    "number yet. Assign them one by one.")
        if ambiguous:
            msg += ' · ' + (_("1 number fits more than one person")
                            if len(ambiguous) == 1 else
                            _("%s numbers fit more than one person") % len(ambiguous))
        return {'ok': True, 'assigned': assigned, 'ambiguous': ambiguous[:20],
                'message': msg}

    @api.model
    def repair_week(self, week_start, employee_ids=None):
        """Re-pair the week for these people (default: everyone who punched)."""
        if not self._is_officer():
            return {'error': _("Only attendance officers can re-pair punches.")}
        df, dt = self._week(week_start)
        lo, hi = self._local_window(df, dt)
        Punch = self.env['pb.clock.punch'].sudo()
        if employee_ids:
            ids = [int(e) for e in employee_ids]
        else:
            ids = [g[0].id for g in Punch._read_group(
                [('company_id', 'in', self._company_ids()), ('employee_id', '!=', False),
                 ('punch_utc', '>=', lo), ('punch_utc', '<', hi)],
                groupby=['employee_id'], aggregates=['__count'])]
        Pairing = self.env['pb.clock.pairing'].sudo()
        days = held = 0
        for eid in ids:
            if not self._employee_in_scope(eid):
                continue
            try:
                with self.env.cr.savepoint():
                    res = Pairing.repair_employee(eid, df, dt)
                days += res['paired_days']
                held += res['held']
            except Exception:  # noqa: BLE001
                _logger.warning("Time clocks: re-pair %s failed", eid, exc_info=True)
        if not days and not held:
            msg = _("Nothing changed — the week already matches its punches.")
        else:
            parts = [(_("1 day updated") if days == 1 else _("%s days updated") % days)]
            if held:
                parts.append(_("1 punch on hold") if held == 1
                             else _("%s punches on hold") % held)
            msg = ' · '.join(parts)
        return {'ok': True, 'paired_days': days, 'held': held, 'people': len(ids),
                'message': msg}

    @api.model
    def save_settings(self, max_span_h, double_tap_min, trust_direction,
                      allow_plain=None):
        if not self._is_manager():
            return {'error': _("Only attendance managers can change these settings.")}
        try:
            span = float(max_span_h)
            tap = int(double_tap_min)
        except (TypeError, ValueError):
            return {'error': _("Use numbers for the hours and the minutes.")}
        if not 8 <= span <= 36:
            return {'error': _("The longest work day must be between 8 and 36 hours.")}
        if not 0 <= tap <= 30:
            return {'error': _("The double-tap window must be between 0 and 30 minutes.")}
        vals = {'pb_clock_max_span_h': span, 'pb_clock_double_tap_min': tap,
                'pb_clock_trust_direction': bool(trust_direction)}
        if allow_plain is not None:
            vals['pb_clock_allow_plain'] = bool(allow_plain)
        self.env.company.sudo().write(vals)
        return {'ok': True, 'settings': self._settings(),
                'message': _("Saved. Re-pair this week to apply it to punches "
                             "already paired.")}

    @api.model
    def set_device(self, device_id, vals):
        if not self._is_manager():
            return {'error': _("Only attendance managers can change a machine.")}
        device = self.env['pb.clock.device'].sudo().browse(int(device_id or 0)).exists()
        if not device or device.company_id.id not in self._company_ids():
            return {'error': _("That machine is not in this company.")}
        vals = vals or {}
        clean = {}
        if 'name' in vals:
            name = str(vals['name'] or '').strip()
            if not name:
                return {'error': _("A machine needs a name.")}
            clean['name'] = name
        if 'location' in vals:
            clean['location'] = str(vals['location'] or '').strip() or False
        if 'tz' in vals:
            if vals['tz'] not in pytz.all_timezones_set:
                return {'error': _("That time zone is not known.")}
            clean['tz'] = vals['tz']
        if 'allowed' in vals:
            clean['allowed'] = bool(vals['allowed'])
        if clean:
            device.write(clean)
        return {'ok': True, 'message': _("Machine saved.")}

    # ------------------------------------------------------------ machines (CLOCK-2)
    @api.model
    def _manager_device(self, device_id, states=None):
        """(device, None) or (None, {'error'}) — manager gate + scope."""
        if not self._is_manager():
            return None, {'error': _("Only attendance managers can let a machine in "
                                     "or change one.")}
        device = self.env['pb.clock.device'].sudo().with_context(active_test=False) \
            .browse(int(device_id or 0)).exists()
        if not device or device.kind != 'terminal':
            return None, {'error': _("That machine is not known here.")}
        if device.allowed_at and device.state != 'pending' \
                and device.company_id.id not in self._company_ids():
            return None, {'error': _("That machine is not in this company.")}
        if states and device.state not in states:
            return None, {'error': _("That machine has changed in the meantime. "
                                     "Refresh and try again.")}
        return device, None

    @api.model
    def allow_device(self, device_id, vals):
        """Let a machine in (D10): name, location, time zone, pair-from day.
        It starts from punch stamp 0 — it then sends everything it holds, and
        what is older than the pair-from day is kept but never paired."""
        device, err = self._manager_device(device_id, states=('pending',))
        if err:
            return err
        vals = vals or {}
        name = str(vals.get('name') or '').strip()
        if not name:
            return {'error': _("Give the machine a name people will recognise, "
                               "like the place it hangs.")}
        tz = vals.get('tz') or device.tz or 'UTC'
        if tz not in pytz.all_timezones_set:
            return {'error': _("That time zone is not known.")}
        try:
            history_from = fields.Date.to_date(vals.get('history_from')) \
                or device._default_history_from()
        except Exception:  # noqa: BLE001
            return {'error': _("Use a date for the first day to pair.")}
        company = self.env.company
        now = fields.Datetime.now()
        target = device
        other = self.env['pb.clock.device'].sudo().with_context(active_test=False).search([
            ('company_id', '=', company.id), ('serial', '=', device.serial),
            ('kind', '=', 'terminal'), ('id', '!=', device.id)], limit=1)
        try:
            with self.env.cr.savepoint():
                if other:
                    # an upload already knew this serial: keep that machine (its
                    # punches stay on it) and drop the empty pending row
                    if not self.env['pb.clock.punch'].sudo().search_count(
                            [('device_id', '=', device.id)], limit=1):
                        info = {k: device[k] for k in ('ip', 'firmware', 'pushver',
                                                       'first_seen_at', 'last_seen_at',
                                                       'last_proto')}
                        device.unlink()
                        other.write(info)
                        target = other
                target.write({
                    'name': name,
                    'location': str(vals.get('location') or '').strip() or False,
                    'tz': tz, 'history_from': history_from,
                    'company_id': company.id, 'state': 'allowed',
                    'allowed_at': now, 'active': True,
                    'attlog_stamp': '0', 'operlog_stamp': '0',
                    'skew_samples': '[]', 'clock_skew_s': 0,
                })
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Time clocks: allow failed", exc_info=True)
            return {'error': _("The machine could not be let in: %s") % exc}
        return {'ok': True, 'device_id': target.id, 'message': _(
            "%(name)s is connected. Its punches from %(day)s on will arrive in "
            "the next minute or two.", name=name,
            day=history_from.strftime('%d %b %Y'))}

    @api.model
    def ignore_device(self, device_id):
        device, err = self._manager_device(device_id, states=('pending', 'allowed'))
        if err:
            return err
        device.write({'state': 'blocked'})
        return {'ok': True, 'message': _(
            "%s will be ignored. It can be let in again under Ignored machines.")
            % (device.serial or device.name)}

    @api.model
    def unblock_device(self, device_id):
        device, err = self._manager_device(device_id, states=('blocked',))
        if err:
            return err
        device.write({'state': 'pending', 'allowed_at': False})
        return {'ok': True, 'message': _(
            "%s is asking to connect again. Press Allow when you are ready.")
            % (device.serial or device.name)}

    @api.model
    def resend_since(self, device_id, since):
        """Queue "send me your punches since …" (CLOCK-2 §3.5)."""
        device, err = self._manager_device(device_id, states=('allowed',))
        if err:
            return err
        if not device._listening():
            return {'error': _("This machine has not connected yet.")}
        try:
            day = fields.Date.to_date(since)
        except Exception:  # noqa: BLE001
            day = None
        if not day:
            return {'error': _("Pick the first day to send again.")}
        today = device._local_now().date()
        if day > today:
            return {'error': _("Pick a day that has already happened.")}
        Command = self.env['pb.clock.command'].sudo()
        busy = Command.search_count([('device_id', '=', device.id),
                                     ('kind', '=', 'resend'),
                                     ('state', 'in', ('queued', 'sent'))], limit=1)
        if busy:
            return {'error': _("A resend is already on its way to this machine.")}
        Command._queue_resend(device, day)
        return {'ok': True, 'message': _(
            "Asked %(name)s to send its punches since %(day)s again. Punches "
            "already here are kept once.", name=device.name,
            day=day.strftime('%d %b %Y'))}
