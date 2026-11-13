# -*- coding: utf-8 -*-
"""pb.clock.adms — the ZK PUSH / ADMS ("iclock") protocol (CLOCK-2 §3).

The controller (`controllers/iclock.py`) is a thin door: it reads the request,
calls `handle(route, method, params, body, meta)` here, and turns the
`(status, body)` answer into a plain-text response. Everything that decides
anything lives here so it is unit-testable without HTTP.

RULES (ledger D10–D13, rules 8 and 12)

  * The tenancy door first: a paused tenant answers 403 `paused` on every route
    and nothing is written.
  * The serial decides everything. Unknown serial → ONE `pending` machine row
    (50 per database at most) and 403 `pending`. Pending / blocked → 403 and
    nothing written (a pending row's last-heard time is refreshed at most once
    a minute; that is the only write a non-allowed serial ever causes).
  * Plain connection (D12): `X-Forwarded-Proto: http` with the company's
    switch off → 403 `https required`.
  * ATTLOG lines go into the CLOCK-1 ledger with `source='adms'`; nothing pairs
    inline — the pairing job is triggered. `OK: n` only after the rows are in.
  * Every other table (OPERLOG, USERINFO, BIODATA, FP, FACE, USERPIC,
    ATTPHOTO, …) is counted and dropped unread. No biometric is ever stored.
  * Unknown `/iclock/*` paths answer 200 `OK` — a 404 makes some firmware
    re-register in a loop.
"""

import logging
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from urllib.parse import parse_qsl

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

SERIAL_RE = re.compile(r'^[A-Za-z0-9_-]{6,32}$')
MAX_BODY = 2 * 1024 * 1024
MAX_LINES = 5000
MAX_PENDING = 50
RATE_WARN_PER_MIN = 240
SEEN_EVERY = timedelta(seconds=60)
SKEW_WINDOW = timedelta(minutes=15)
LIVE_SKEW_MAX = timedelta(hours=24)
LIVE_MAX_LINES = 2

ATTLOG_TABLES = ('ATTLOG', 'TRANSACTION')
VERIFY = {'1': 'fingerprint', '4': 'card', '15': 'face', '0': 'password'}
STATUS_VALUES = {'0', '1', '2', '3', '4', '5', '255'}

# in-process bookkeeping (the box runs one threaded server process)
_LOCK = threading.Lock()
_RATE = defaultdict(deque)          # (db, serial) -> request times
_TABLE_LOGGED = {}                  # (db, serial, table) -> date logged


def _clean_serial(value):
    sn = (value or '').strip()
    return sn if SERIAL_RE.match(sn) else ''


def _parse_time(text):
    text = (text or '').strip().replace('T', ' ').replace('/', '-')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(text[:19] if fmt.endswith('%S') else text[:16], fmt)
        except ValueError:
            continue
    return None


def parse_attlog_line(line):
    """One ATTLOG line → dict, or None when it does not parse.

    `PIN \\t YYYY-MM-DD HH:MM:SS \\t status \\t verify [\\t workcode …]`, 2–8+
    columns. Some firmware puts a machine number third: recognised when
    column 3 is an integer that CANNOT be a status (not 0–5 / 255) and column 4
    looks like one; the extra column is skipped. Status and verify are kept as
    the strings the machine sent."""
    cols = [c.strip() for c in line.rstrip('\r\n').split('\t')]
    if len(cols) < 2:
        return None
    pin = cols[0]
    when = _parse_time(cols[1])
    if not pin or not when or len(pin) > 64:
        return None
    rest = cols[2:]
    if (len(rest) >= 2 and rest[0].isdigit() and rest[0] not in STATUS_VALUES
            and rest[1] in STATUS_VALUES):
        rest = rest[1:]          # machine-number column
    status = rest[0] if len(rest) > 0 else ''
    verify = rest[1] if len(rest) > 1 else ''
    workcode = rest[2] if len(rest) > 2 else ''
    return {'pin': pin, 'local': when.replace(microsecond=0), 'status': status,
            'verify': verify, 'workcode': workcode if workcode not in ('', '0') else ''}


def body_lines(body):
    return [ln for ln in (body or '').replace('\r\n', '\n').split('\n') if ln.strip()]


class PbClockAdms(models.AbstractModel):
    _name = 'pb.clock.adms'
    _description = 'Attendance machine receiver'

    # ------------------------------------------------------------ helpers
    @api.model
    def _answer(self, status, body):
        return status, body

    @api.model
    def _paused(self):
        if 'pb.tenancy' not in self.env:
            return False
        try:
            state = self.env['pb.tenancy'].sudo().access_state()
        except Exception:  # noqa: BLE001 — a broken check must not open the door
            _logger.warning("pb_clock: tenancy check failed", exc_info=True)
            return False
        return (state or {}).get('access') == 'suspended'

    @api.model
    def _rate(self, serial):
        key = (self.env.cr.dbname, serial)
        now = time.monotonic()
        with _LOCK:
            q = _RATE[key]
            q.append(now)
            while q and now - q[0] > 60:
                q.popleft()
            n = len(q)
        if n == RATE_WARN_PER_MIN:
            _logger.warning("pb_clock: machine %s made %s requests in a minute",
                            serial, n)

    @api.model
    def _log_table_once(self, serial, table, n):
        key = (self.env.cr.dbname, serial, table)
        today = fields.Date.today()
        with _LOCK:
            if _TABLE_LOGGED.get(key) == today:
                return False
            _TABLE_LOGGED[key] = today
        _logger.info("pb_clock: machine %s sent %s %s line(s); dropped unread",
                     serial, n, table)
        return True

    @api.model
    def _main_company(self):
        company = self.env.ref('base.main_company', raise_if_not_found=False)
        return company or self.env['res.company'].sudo().search([], order='id', limit=1)

    @api.model
    def _register_pending(self, serial, meta, params):
        """First contact of an unknown serial: one pending row (cap 50)."""
        Device = self.env['pb.clock.device'].sudo().with_context(active_test=False)
        n = Device.search_count([('state', '=', 'pending')])
        if n >= MAX_PENDING:
            _logger.warning("pb_clock: %s pending machines already; ignoring "
                            "serial %s from %s", n, serial, meta.get('ip'))
            return Device.browse()
        company = self._main_company()
        now = fields.Datetime.now()
        firmware = (params.get('pushver') and 'push %s' % params.get('pushver')) or ''
        vals = {
            'name': serial, 'serial': serial, 'kind': 'terminal',
            'state': 'pending', 'company_id': company.id,
            'tz': company.resource_calendar_id.tz or 'UTC',
            'ip': meta.get('ip') or False, 'first_seen_at': now, 'last_seen_at': now,
            'pushver': (params.get('pushver') or '')[:32] or False,
            'firmware': firmware[:120] or False,
            'last_proto': meta.get('proto') or 'https',
        }
        try:
            with self.env.cr.savepoint():
                return Device.create(vals)
        except Exception:  # noqa: BLE001 — a concurrent first contact made it
            return self.env['pb.clock.device']._by_serial(serial)

    @api.model
    def _touch(self, device, meta, now, force=False):
        vals = {}
        if force or not device.last_seen_at or now - device.last_seen_at >= SEEN_EVERY:
            vals['last_seen_at'] = now
        ip = meta.get('ip')
        if ip and ip != device.ip:
            vals['ip'] = ip
        proto = meta.get('proto') or 'https'
        if proto != device.last_proto:
            vals['last_proto'] = proto
        plain = proto == 'http'
        if plain and not device.plain_connection:
            vals['plain_connection'] = True
        elif not plain and device.plain_connection and proto == 'https':
            vals['plain_connection'] = False
        if vals:
            device.sudo().write(vals)

    # ------------------------------------------------------------ the door
    @api.model
    def handle(self, route, method, params, body, meta):
        """→ (http_status, text body). `route` is the path after /iclock/."""
        self = self.sudo()
        params = {k: (v if isinstance(v, str) else str(v)) for k, v in (params or {}).items()}
        meta = meta or {}
        if self._paused():
            return 403, 'paused'
        route = (route or '').strip('/').lower()
        if route.endswith('.aspx'):
            route = route[:-5]
        raw_sn = params.get('SN') or params.get('sn') or ''
        if route == 'ping' and not raw_sn:
            return 200, 'OK'
        known_routes = ('cdata', 'getrequest', 'devicecmd', 'push', 'registry',
                        'ping', 'querydata', 'rtdata')
        if route not in known_routes and not raw_sn:
            return 200, 'OK'
        serial = _clean_serial(raw_sn)
        if not serial:
            return 400, 'bad serial'
        if meta.get('too_big') or len(body or '') > MAX_BODY:
            return 413, 'too large'
        self._rate(serial)

        now = fields.Datetime.now()
        device = self.env['pb.clock.device']._by_serial(serial)
        if not device:
            device = self._register_pending(serial, meta, params)
            return 403, 'pending'
        if device.state == 'blocked':
            return 403, 'pending'
        if device.state == 'allowed' and not device._listening():
            # a terminal an upload created, calling in for the first time:
            # it waits for Allow like any new machine (D10)
            device.write({'state': 'pending', 'first_seen_at': device.first_seen_at or now,
                          'last_seen_at': now, 'ip': meta.get('ip') or device.ip,
                          'pushver': (params.get('pushver') or '')[:32] or device.pushver})
            return 403, 'pending'
        if device.state == 'pending':
            if not device.last_seen_at or now - device.last_seen_at >= SEEN_EVERY:
                vals = {'last_seen_at': now}
                if meta.get('ip'):
                    vals['ip'] = meta['ip']
                if params.get('pushver'):
                    vals['pushver'] = params['pushver'][:32]
                device.write(vals)
            return 403, 'pending'

        # ---- allowed from here on
        proto = meta.get('proto') or 'https'
        if proto == 'http' and not device.company_id.pb_clock_allow_plain:
            return 403, 'https required'
        self._touch(device, meta, now)

        if route == 'cdata':
            if method == 'GET':
                return 200, self._options(device, params)
            return self._cdata_post(device, params, body, now)
        if route == 'getrequest':
            return 200, self._getrequest(device, params, now)
        if route == 'devicecmd':
            return 200, self._devicecmd(device, body, now)
        if route == 'registry':
            return 200, self._registry(device, params)
        if route == 'push':
            return 200, self._options(device, params, v3=True)
        return 200, 'OK'

    # ------------------------------------------------------------ handshake
    @api.model
    def _options(self, device, params, v3=False):
        if params.get('pushver') and params['pushver'][:32] != (device.pushver or ''):
            device.write({'pushver': params['pushver'][:32]})
        lines = [
            'GET OPTION FROM: %s' % device.serial,
            'ATTLOGStamp=%s' % (device.attlog_stamp or 0),
            'OPERLOGStamp=%s' % (device.operlog_stamp or 0),
            'ATTPHOTOStamp=0',
            'ErrorDelay=30',
            'Delay=10',
            'TransTimes=00:00;12:00',
            'TransInterval=1',
            'TransFlag=TransData AttLog\tOpLog',
            'TimeZone=%s' % device._utc_offset_hours(),
            'Realtime=1',
            'Encrypt=0',
            'ServerVer=2.4.1',
        ]
        if v3:
            lines += [
                'ServerVersion=3.0.1',
                'PushProtVer=3.0.1',
                'RequestDelay=10',
                'TransTables=Transaction',
                'SessionID=%s' % secrets.token_hex(8),
                'TimeoutSec=10',
            ]
        return '\r\n'.join(lines) + '\r\n'

    @api.model
    def _registry(self, device, params):
        code = device.registry_code
        if not code:
            code = secrets.token_hex(8)
            device.write({'registry_code': code})
        if params.get('pushver') or params.get('DeviceType'):
            _logger.info("pb_clock: machine %s registered (push 3.x, %s)",
                         device.serial, params.get('pushver') or params.get('DeviceType'))
        return 'RegistryCode=%s' % code

    # ------------------------------------------------------------ uploads
    @api.model
    def _cdata_post(self, device, params, body, now):
        table = (params.get('table') or '').strip().upper()
        lines = body_lines(body)
        if len(lines) > MAX_LINES:
            return 413, 'too many lines'
        n = len(lines)
        if table in ATTLOG_TABLES:
            self._ingest_attlog(device, lines, now)
            if params.get('Stamp'):
                device.write({'attlog_stamp': params['Stamp'][:32]})
            return 200, 'OK: %s' % n
        if table == 'OPERLOG':
            if params.get('Stamp'):
                device.write({'operlog_stamp': params['Stamp'][:32]})
            self._log_table_once(device.serial, table, n)
            return 200, 'OK: %s' % n
        # USERINFO, BIODATA, FP, FACE, USERPIC, ATTPHOTO, … — never stored
        self._log_table_once(device.serial, table or '?', n)
        return 200, 'OK: %s' % n

    @api.model
    def _ingest_attlog(self, device, lines, now):
        company = device.company_id
        trust = bool(company.pb_clock_trust_direction)
        Punch = self.env['pb.clock.punch'].sudo()
        vals_list, bad = [], 0
        for line in lines:
            row = parse_attlog_line(line)
            if not row:
                bad += 1
                _logger.warning("pb_clock: machine %s sent a line that does not "
                                "parse: %r", device.serial, line[:80])
                continue
            direction = 'unknown'
            if trust and row['status'] in ('0', '1'):
                direction = 'in' if row['status'] == '0' else 'out'
            vals = {
                'device_id': device.id, 'company_id': company.id,
                'source': 'adms', 'user_code': row['pin'],
                'punch_local': row['local'],
                'direction_raw': row['status'] or False,
                'direction': direction,
                'verify_mode': row['verify'] or False,
                'work_code': row['workcode'] or False,
                'received_at': now,
            }
            if device.history_from and row['local'].date() < device.history_from:
                vals['state'] = 'ignored_before_start'
                vals['note'] = _("From before this machine's start date: kept, "
                                 "not paired.")
            vals_list.append(vals)
        if not vals_list:
            return {'created': 0, 'bad': bad}
        before_last = device.last_punch_at
        res = Punch._ingest(vals_list)
        self._measure_skew(device, res['records'], len(lines), before_last, now)
        if res['created']:
            self.env['pb.clock.pairing']._trigger_soon()
        return {'created': res['created'], 'bad': bad}

    @api.model
    def _measure_skew(self, device, records, n_lines, before_last, now):
        """D13: a sample from a REALTIME push only — the newest line is within
        15 minutes of now, or the post is a small live one (≤ 2 lines, newer
        than anything this machine sent before, within a day). Skew = machine
        time − server time (positive = the machine is fast)."""
        if not records:
            return None
        newest = max(records.mapped('punch_utc'))
        delta = newest - now
        live = abs(delta) < SKEW_WINDOW
        if not live and n_lines <= LIVE_MAX_LINES and abs(delta) < LIVE_SKEW_MAX \
                and (not before_last or newest > before_last):
            live = True
        if not live:
            return None
        device._add_skew_sample(int(delta.total_seconds()))
        return device._maybe_queue_set_time(now)

    # ------------------------------------------------------------ commands
    @api.model
    def _getrequest(self, device, params, now):
        info = params.get('INFO') or params.get('info')
        if info:
            self._store_info(device, info)
        body = self.env['pb.clock.command']._hand_out(device, now)
        return body or 'OK'

    @api.model
    def _store_info(self, device, info):
        """INFO=firmware,users,fingerprints,punches,ip,… — counts only."""
        parts = [p.strip() for p in str(info).split(',')]

        def as_int(i):
            try:
                return int(parts[i])
            except (IndexError, ValueError):
                return None
        vals = {}
        if parts and parts[0]:
            vals['firmware'] = parts[0][:120]
        for i, field in ((1, 'users_count'), (2, 'fp_count'), (3, 'attlog_count')):
            v = as_int(i)
            if v is not None:
                vals[field] = v
        if len(parts) > 4 and re.match(r'^[0-9a-fA-F:.]{3,45}$', parts[4] or ''):
            vals['lan_ip'] = parts[4]
        vals = {k: v for k, v in vals.items() if device[k] != v}
        if vals:
            device.write(vals)

    @api.model
    def _devicecmd(self, device, body, now):
        Command = self.env['pb.clock.command']
        for line in body_lines(body):
            kv = dict(parse_qsl(line.strip(), keep_blank_values=True))
            if 'ID' in kv:
                Command._close(device, kv.get('ID'), kv.get('Return'), now)
        return 'OK'
