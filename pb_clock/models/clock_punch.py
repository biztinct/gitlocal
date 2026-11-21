# -*- coding: utf-8 -*-
"""pb.clock.punch — the punch ledger (CLOCK ledger rules 7, 8, 12; D7).

APPEND-ONLY. Rows are created by the intake paths (the upload today, the
machine receiver in CLOCK-2) and afterwards only their matching / pairing
fields are written. Nobody edits a punch: a wrong day is fixed through an
attendance correction, which is a human decision with an approval.

SAME PUNCH TWICE = ONE ROW. `dedup_key` is sha1(company | device serial or
'upload' | user code | local time to the second) under a UNIQUE constraint.
`create()` drops a key that already exists (or repeats inside the batch) and
returns the existing row in its place, so every intake path can simply send
what it has — a backfill overlapping a live push is harmless.

NEVER BIOMETRICS. The ledger holds a number, a time, a machine and how the
person was recognised (`verify_mode`, e.g. "1" fingerprint). Nothing else.

NEVER PAIRS INLINE (rule 12). Creating rows does not make attendance; the
pairing cron does, triggered right after an intake.
"""

import hashlib
import logging

import pytz
from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

SOURCES = [
    ('upload', 'Punch file'),
    ('mitaco_export', 'Attendance program daily sheet'),
    ('adms', 'Machine push'),
    ('bridge', 'Office PC connector'),
]

STATES = [
    ('new', 'Waiting'),
    ('unmatched', 'Unknown number'),
    ('matched', 'Matched'),
    ('paired', 'In / Out'),
    ('middle', 'Break tap'),
    ('held', 'On hold'),
    ('ignored_duplicate_tap', 'Double tap'),
    ('ignored_outlier', 'Ignored'),
    ('ignored_before_start', 'Before the start date'),
]

# the only fields anyone may write after create (ledger rule 7)
PAIRING_FIELDS = frozenset({'employee_id', 'state', 'attendance_id', 'note',
                            'work_day'})


def dedup_key(company_id, serial, user_code, punch_local):
    stamp = fields.Datetime.to_string(punch_local)[:19] if punch_local else ''
    raw = '%s|%s|%s|%s' % (company_id or 0, (serial or 'upload'),
                           (user_code or '').strip(), stamp)
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


class PbClockPunch(models.Model):
    _name = 'pb.clock.punch'
    _description = 'Time clock punch'
    _order = 'punch_utc desc, id desc'
    _rec_name = 'user_code'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 readonly=True)
    device_id = fields.Many2one('pb.clock.device', string='Machine',
                                required=True, index=True, readonly=True,
                                ondelete='restrict')
    source = fields.Selection(SOURCES, required=True, default='upload',
                              readonly=True)
    user_code = fields.Char(string='Number on the machine', required=True,
                            index=True, readonly=True)
    punch_local = fields.Datetime(string='Time on the machine', required=True,
                                  readonly=True,
                                  help='As the machine read it, in its own time zone.')
    punch_utc = fields.Datetime(string='Time', required=True, index=True,
                                readonly=True)
    direction_raw = fields.Char(readonly=True)
    direction = fields.Selection(
        [('in', 'In'), ('out', 'Out'), ('unknown', 'Not pressed')],
        default='unknown', readonly=True)
    verify_mode = fields.Char(readonly=True)
    work_code = fields.Char(readonly=True)
    received_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    dedup_key = fields.Char(required=True, readonly=True, copy=False)

    employee_id = fields.Many2one('hr.employee', string='Person', index=True)
    state = fields.Selection(STATES, default='new', required=True, index=True)
    attendance_id = fields.Many2one('hr.attendance', ondelete='set null',
                                    index=True)
    note = fields.Char()
    work_day = fields.Date(string='Work day', index=True)

    _dedup_key_uniq = models.Constraint(
        'UNIQUE(dedup_key)', 'This punch is already on record.')
    _emp_time_idx = models.Index('(employee_id, punch_utc)')

    # ------------------------------------------------------------ helpers
    @api.model
    def _to_utc(self, device, punch_local):
        tzinfo = device._tzinfo() if device else pytz.UTC
        try:
            aware = tzinfo.localize(punch_local, is_dst=None)
        except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
            aware = tzinfo.localize(punch_local, is_dst=False)
        return aware.astimezone(pytz.UTC).replace(tzinfo=None)

    @api.model
    def _prepare_vals(self, vals, device_cache):
        vals = dict(vals)
        device_id = vals.get('device_id')
        device = device_cache.get(device_id)
        if device is None:
            device = self.env['pb.clock.device'].sudo().browse(device_id).exists()
            device_cache[device_id] = device
        if not device:
            raise UserError(_("A punch needs a machine."))
        vals['company_id'] = vals.get('company_id') or device.company_id.id
        vals['user_code'] = (vals.get('user_code') or '').strip()
        local = fields.Datetime.to_datetime(vals.get('punch_local'))
        if not local or not vals['user_code']:
            raise UserError(_("A punch needs a number and a time."))
        local = local.replace(microsecond=0)
        vals['punch_local'] = local
        if not vals.get('punch_utc'):
            vals['punch_utc'] = self._to_utc(device, local)
        vals['dedup_key'] = dedup_key(vals['company_id'], device.serial,
                                      vals['user_code'], local)
        return vals

    # ------------------------------------------------------------ CRUD
    @api.model_create_multi
    def create(self, vals_list):
        """Create the punches that are new; a repeat returns the existing row.

        The returned recordset has one row per input row, in input order
        (a repeated punch appears as its existing row)."""
        return self._create_counted(vals_list)[0]

    def _create_counted(self, vals_list):
        device_cache = {}
        prepared = [self._prepare_vals(v, device_cache) for v in vals_list]
        keys = list({v['dedup_key'] for v in prepared})
        existing = {}
        if keys:
            for row in self.sudo().search_read([('dedup_key', 'in', keys)],
                                               ['dedup_key']):
                existing[row['dedup_key']] = row['id']
        fresh, fresh_keys = [], set()
        for v in prepared:
            k = v['dedup_key']
            if k in existing or k in fresh_keys:
                continue
            fresh_keys.add(k)
            fresh.append(v)
        created = 0
        if fresh:
            try:
                with self.env.cr.savepoint():
                    made = super().create(fresh)
                for rec, v in zip(made, fresh):
                    existing[v['dedup_key']] = rec.id
                created = len(made)
            except IntegrityError:
                # a concurrent intake landed the same punch between our read
                # and our insert: fall back to one savepoint per row
                for v in fresh:
                    try:
                        with self.env.cr.savepoint():
                            rec = super().create([v])
                        existing[v['dedup_key']] = rec.id
                        created += 1
                    except IntegrityError:
                        other = self.sudo().search(
                            [('dedup_key', '=', v['dedup_key'])], limit=1)
                        if other:
                            existing[v['dedup_key']] = other.id
        ids = [existing[v['dedup_key']] for v in prepared
               if v['dedup_key'] in existing]
        return self.browse(ids), created

    @api.model
    def _ingest(self, vals_list):
        """Intake door for every path: {'created': n, 'duplicates': n,
        'records': recordset}. sudo — the caller has already checked its own
        right (officer for an upload, a known serial for a machine)."""
        if not vals_list:
            return {'created': 0, 'duplicates': 0, 'records': self.browse()}
        records, created = self.sudo()._create_counted(vals_list)
        # machines heard from: last punch / last seen
        now = fields.Datetime.now()
        by_device = {}
        for rec in records:
            cur = by_device.get(rec.device_id.id)
            if not cur or rec.punch_utc > cur:
                by_device[rec.device_id.id] = rec.punch_utc
        Device = self.env['pb.clock.device'].sudo()
        for device_id, last in by_device.items():
            device = Device.browse(device_id)
            vals = {'last_seen_at': now}
            if not device.last_punch_at or last > device.last_punch_at:
                vals['last_punch_at'] = last
            device.write(vals)
        return {'created': created,
                'duplicates': max(len(vals_list) - created, 0),
                'records': records}

    def write(self, vals):
        if not self.env.su:
            # the access right first: an officer (read-only) is told that,
            # not the ledger rule below
            self.check_access('write')
        locked = set(vals or {}) - PAIRING_FIELDS
        if locked and not (self.env.su or self.env.user.has_group('base.group_system')):
            raise UserError(_(
                "A punch is never edited — it is what the machine reported. To "
                "change a day, file an attendance correction."))
        return super().write(vals)

    def unlink(self):
        if not (self.env.su or self.env.user.has_group('base.group_system')):
            raise AccessError(_(
                "Punches cannot be deleted. Only a system administrator may "
                "remove them, for a data-protection request."))
        return super().unlink()
