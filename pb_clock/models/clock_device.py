# -*- coding: utf-8 -*-
"""pb.clock.device — one attendance machine, or the company's upload pseudo
device ("Files you upload").

CLOCK-1 needed a device per ledger row so the dedup key and the local time
zone of a punch are defined. CLOCK-2 makes it the allow-list for machines that
push to Payobook (ADMS / iclock, ledger D10):

  * `state` — `pending` (it called in, nobody let it in yet), `allowed`,
    `blocked`. `allowed` (the CLOCK-1 Boolean) is now a stored mirror of
    `state == 'allowed'` with an inverse, so CLOCK-1 code and tests still read
    and write it.
  * A machine is LISTENED TO only when `state == 'allowed'` AND `allowed_at`
    is set — i.e. a manager pressed Allow (or allowed it from the machine
    card). A terminal an upload created (CLOCK-1, `<serial>_attlog.dat`) has no
    `allowed_at`: the first time it calls in over the network it turns
    `pending` and waits for Allow like any stranger, so a machine that holds
    100 000 old punches never pairs months of history nobody asked for.
  * `history_from` — punches before it are kept as `ignored_before_start`.
  * The receiver's bookkeeping: stamps, last protocol, firmware, the INFO
    counters, the measured clock skew.
"""

import json
import statistics
from datetime import date, datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.addons.base.models.res_partner import _tz_get

DEVICE_STATES = [
    ('pending', 'Asking to connect'),
    ('allowed', 'Allowed'),
    ('blocked', 'Ignored'),
]

SKEW_SAMPLES = 7          # D13: median of the last 7 realtime pushes
SKEW_MIN_SAMPLES = 3      # never act on one or two
SKEW_LIMIT_S = 60         # over a minute off → correct it
SET_TIME_EVERY = timedelta(hours=6)


class PbClockDevice(models.Model):
    _name = 'pb.clock.device'
    _description = 'Attendance machine'
    _order = 'kind desc, name, id'

    name = fields.Char(string='Name', required=True)
    serial = fields.Char(string='Serial number', index=True, copy=False)
    location = fields.Char(string='Location')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    kind = fields.Selection(
        [('upload', 'Files you upload'), ('terminal', 'Machine')],
        string='Kind', required=True, default='terminal')
    state = fields.Selection(
        DEVICE_STATES, string='Status', required=True, default='allowed',
        index=True)
    allowed = fields.Boolean(
        string='Allowed', compute='_compute_allowed', inverse='_inverse_allowed',
        store=True, readonly=False)
    allowed_at = fields.Datetime(string='Allowed on', readonly=True, copy=False)
    tz = fields.Selection(
        _tz_get, string='Time zone',
        default=lambda self: self._default_tz())
    history_from = fields.Date(
        string='Pair punches from',
        help='Punches the machine holds from before this day are kept on '
             'record but never become work days.')
    last_punch_at = fields.Datetime(string='Last punch', readonly=True)
    last_seen_at = fields.Datetime(string='Last heard from', readonly=True)
    first_seen_at = fields.Datetime(string='First heard from', readonly=True)
    punches_today = fields.Integer(
        string='Punches today', compute='_compute_punches_today')
    active = fields.Boolean(default=True)

    # ---- what the receiver learns from the machine (never biometrics)
    ip = fields.Char(string='Calls from', readonly=True,
                     help='The internet address the machine calls from.')
    lan_ip = fields.Char(string='Address on the local network', readonly=True)
    firmware = fields.Char(string='Firmware', readonly=True)
    pushver = fields.Char(string='Push version', readonly=True)
    last_proto = fields.Selection(
        [('https', 'Secure'), ('http', 'Plain')], string='Connection',
        readonly=True)
    plain_connection = fields.Boolean(string='Plain connection', readonly=True)
    users_count = fields.Integer(string='People on the machine', readonly=True)
    fp_count = fields.Integer(string='Fingerprints on the machine', readonly=True,
                              help='A count the machine reports. No fingerprint '
                                   'ever leaves the machine.')
    attlog_count = fields.Integer(string='Punches held by the machine', readonly=True)
    attlog_stamp = fields.Char(string='Punch stamp', readonly=True, copy=False)
    operlog_stamp = fields.Char(string='Operation stamp', readonly=True, copy=False)
    registry_code = fields.Char(string='Registration code', readonly=True, copy=False)

    # ---- measured clock (D13)
    clock_skew_s = fields.Integer(
        string='Clock difference (seconds)', readonly=True,
        help='How far the machine clock is ahead (+) or behind (-), measured '
             'from its live punches.')
    skew_samples = fields.Char(string='Clock samples', readonly=True, copy=False)
    clock_corrected_at = fields.Datetime(string='Clock corrected', readonly=True)
    clock_corrected_by_s = fields.Integer(string='Corrected by (seconds)', readonly=True)

    command_ids = fields.One2many('pb.clock.command', 'device_id', string='Commands')

    _serial_company_uniq = models.Constraint(
        'UNIQUE(company_id, serial)',
        'This serial number is already registered for this company.')

    # ------------------------------------------------------------ state
    @api.depends('state')
    def _compute_allowed(self):
        for device in self:
            device.allowed = device.state == 'allowed'

    def _inverse_allowed(self):
        for device in self:
            want = 'allowed' if device.allowed else 'blocked'
            if device.state != want:
                device.state = want
            if want == 'allowed' and not device.allowed_at and device.kind == 'terminal' \
                    and device.first_seen_at:
                # allowed from the machine card after it called in
                device.allowed_at = fields.Datetime.now()

    def _listening(self):
        """Is this machine let in? (state allowed AND a person allowed it)."""
        self.ensure_one()
        return self.state == 'allowed' and bool(self.allowed_at) \
            and self.kind == 'terminal'

    # ------------------------------------------------------------ zone
    @api.model
    def _default_tz(self):
        company = self.env.company
        return (company.resource_calendar_id.tz or self.env.user.tz or 'UTC')

    def _tzinfo(self):
        self.ensure_one()
        try:
            return pytz.timezone(self.tz or self.company_id.resource_calendar_id.tz
                                 or 'UTC')
        except Exception:  # noqa: BLE001
            return pytz.UTC

    def _utc_offset_hours(self, now=None):
        """The zone offset as the handshake's TimeZone: whole hours (7), or
        minutes for a half-hour zone (330) — what ZK firmware reads."""
        self.ensure_one()
        now = now or fields.Datetime.now()
        off = self._tzinfo().utcoffset(now) or timedelta(0)
        minutes = int(off.total_seconds() // 60)
        if minutes % 60 == 0:
            return minutes // 60
        return minutes

    def _local_now(self, now=None):
        self.ensure_one()
        now = now or fields.Datetime.now()
        return pytz.UTC.localize(now).astimezone(self._tzinfo()).replace(tzinfo=None)

    def _local_today_bounds_utc(self, now=None):
        """[start, end) of TODAY in this device's zone, as naive UTC."""
        self.ensure_one()
        tzinfo = self._tzinfo()
        now = now or fields.Datetime.now()
        local_now = pytz.UTC.localize(now).astimezone(tzinfo)
        start = tzinfo.localize(datetime.combine(local_now.date(), datetime.min.time()))
        start_utc = start.astimezone(pytz.UTC).replace(tzinfo=None)
        return start_utc, start_utc + timedelta(days=1)

    def _default_history_from(self, now=None):
        """First day of the current month in the machine's zone (D10)."""
        self.ensure_one()
        return self._local_now(now).date().replace(day=1)

    def _compute_punches_today(self):
        Punch = self.env['pb.clock.punch'].sudo()
        for device in self:
            if not device.id:
                device.punches_today = 0
                continue
            lo, hi = device._local_today_bounds_utc()
            device.punches_today = Punch.search_count([
                ('device_id', '=', device.id),
                ('punch_utc', '>=', lo), ('punch_utc', '<', hi)])

    # ------------------------------------------------------------ clock (D13)
    def _skew_list(self):
        self.ensure_one()
        try:
            data = json.loads(self.skew_samples or '[]')
            return [int(x) for x in data][-SKEW_SAMPLES:]
        except Exception:  # noqa: BLE001
            return []

    def _add_skew_sample(self, skew_s):
        """One measured sample → rolling median. Returns the new median."""
        self.ensure_one()
        samples = (self._skew_list() + [int(skew_s)])[-SKEW_SAMPLES:]
        median = int(round(statistics.median(samples)))
        self.sudo().write({'skew_samples': json.dumps(samples),
                           'clock_skew_s': median})
        return median, len(samples)

    @staticmethod
    def zk_encode(local_dt):
        """ZK firmware's packed time: ((Y-2000)*12*31 + (M-1)*31 + (D-1))
        *86400 + h*3600 + m*60 + s, of the machine's LOCAL time."""
        return ((((local_dt.year - 2000) * 12 * 31) + ((local_dt.month - 1) * 31)
                 + (local_dt.day - 1)) * 86400
                + local_dt.hour * 3600 + local_dt.minute * 60 + local_dt.second)

    @staticmethod
    def zk_decode(value):
        value = int(value)
        s = value % 60
        value //= 60
        m = value % 60
        value //= 60
        h = value % 24
        value //= 24
        d = value % 31 + 1
        value //= 31
        mo = value % 12 + 1
        value //= 12
        y = value + 2000
        return datetime(y, mo, d, h, m, s)

    def _maybe_queue_set_time(self, now=None):
        """|median skew| > 60 s, at least 3 samples, and no set_time in the
        last 6 h → queue `SET OPTIONS DateTime=`. Returns the command or None."""
        self.ensure_one()
        now = now or fields.Datetime.now()
        samples = self._skew_list()
        if len(samples) < SKEW_MIN_SAMPLES or abs(self.clock_skew_s or 0) <= SKEW_LIMIT_S:
            return None
        Command = self.env['pb.clock.command'].sudo()
        recent = Command.search_count([
            ('device_id', '=', self.id), ('kind', '=', 'set_time'),
            ('queued_at', '>=', now - SET_TIME_EVERY)], limit=1)
        if recent:
            return None
        return Command._queue_set_time(self, now=now)

    # ------------------------------------------------------------ lookups
    @api.model
    def _get_upload_device(self, company):
        """The company's one `upload` pseudo device, created on first use."""
        company = company or self.env.company
        Device = self.sudo().with_context(active_test=False)
        device = Device.search([('company_id', '=', company.id),
                                ('kind', '=', 'upload')], limit=1)
        if not device:
            device = Device.create({
                'name': _('Files you upload'),
                'kind': 'upload',
                'company_id': company.id,
                'tz': company.resource_calendar_id.tz or 'UTC',
            })
        elif not device.active:
            device.active = True
        return device

    @api.model
    def _find_terminal(self, company, token):
        """A terminal of `company` named by `token` (serial first, then name),
        or an empty recordset."""
        token = (token or '').strip()
        if not token:
            return self.browse()
        Device = self.sudo().with_context(active_test=False)
        dom = [('company_id', '=', company.id), ('kind', '=', 'terminal')]
        device = Device.search(dom + [('serial', '=', token)], limit=1)
        if not device:
            device = Device.search(dom + [('name', '=ilike', token)], limit=1)
        return device

    @api.model
    def _by_serial(self, serial):
        """The machine with this serial anywhere in the database (a database
        is one tenant; the serial decides the company). Allowed first, then
        pending, then blocked; the oldest row wins a tie."""
        Device = self.sudo().with_context(active_test=False)
        rows = Device.search([('serial', '=', serial), ('kind', '=', 'terminal')],
                             order='id')
        if not rows:
            return Device.browse()
        rank = {'allowed': 0, 'pending': 1, 'blocked': 2}
        return rows.sorted(lambda d: (rank.get(d.state, 3),
                                      0 if d.allowed_at else 1, d.id))[:1]
