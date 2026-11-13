"""Read-only desktop collectors. Durable intake precedes data interpretation.

No source data error prevents acknowledgement or subsequent batches. HTTP/auth/
DB failures are retried by the collector. Secrets are hashed and company scope is
chosen by pairing, never by an uploaded company or database identifier.
"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.base.models.res_partner import _tz_get

COLUMNS = ('UserFullCode', 'UserEnrollNumber', 'TimeDate', 'TimeStr',
           'TimeType', 'TimeSource', 'MachineNo', 'CardNo')


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def canonical(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class ClockConnector(models.Model):
    _name = 'pb.clock.connector'
    _description = 'Attendance data connector'
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, tracking=True)
    source_type = fields.Selection([('mitaco_mdb', 'Mitaco · local Access database')], required=True, default='mitaco_mdb', tracking=True)
    source_group = fields.Char(required=True, tracking=True, help='A stable name for databases covering the same terminals. Use the same group for overlapping PC copies. This is not a terminal serial number.')
    tz = fields.Selection(_tz_get, required=True, default='UTC', tracking=True)
    history_from = fields.Date(required=True, default=lambda self: fields.Date.today().replace(day=1), tracking=True)
    interval_minutes = fields.Integer(default=15, required=True, tracking=True)
    code_field = fields.Selection([('UserEnrollNumber', 'Enrollment number'), ('UserFullCode', 'Full code (keep leading zeros)')], default='UserEnrollNumber', required=True, tracking=True)
    publish_punches = fields.Boolean(string='Send accepted records to attendance', default=False, tracking=True,
        help='Collection always continues. Enable after checking the source group, time zone and employee numbers. Closed attendance remains protected.')
    state = fields.Selection([('new', 'Awaiting setup'), ('connected', 'Connected'), ('revoked', 'Access revoked')], default='new', readonly=True, tracking=True)
    last_contact = fields.Datetime(readonly=True)
    last_read = fields.Datetime(readonly=True, string='Last successful database read')
    latest_source_punch = fields.Char(readonly=True)
    source_rows = fields.Integer(readonly=True)
    pending_rows = fields.Integer(readonly=True)
    client_version = fields.Char(readonly=True)
    last_error = fields.Text(readonly=True)
    token_hash = fields.Char(groups='base.group_no_one', copy=False)
    pairing_hash = fields.Char(groups='base.group_no_one', copy=False)
    pairing_until = fields.Datetime(groups='base.group_no_one', copy=False)
    installation_id = fields.Char(readonly=True, copy=False)
    event_ids = fields.One2many('pb.clock.connector.event', 'connector_id', readonly=True)
    device_id = fields.Many2one('pb.clock.device', readonly=True, copy=False)

    @api.constrains('interval_minutes', 'source_group', 'company_id', 'tz', 'code_field')
    def _check_settings(self):
        for rec in self:
            if not 5 <= rec.interval_minutes <= 1440:
                raise ValidationError(_('Choose a sync interval from 5 to 1440 minutes.'))
            if not (rec.source_group or '').strip():
                raise ValidationError(_('A source group is required.'))
            others = self.sudo().search([('company_id', '=', rec.company_id.id), ('source_group', '=', rec.source_group), ('id', '!=', rec.id)])
            if any(o.tz != rec.tz or o.code_field != rec.code_field for o in others):
                raise ValidationError(_('Connectors in the same source group must use the same time zone and employee-code format.'))

    def _manager(self):
        if not self.env.su and not self.env.user.has_group('hr_attendance.group_hr_attendance_manager'):
            raise AccessError(_('Attendance managers manage connectors.'))
        self.check_access('write')

    def write(self, vals):
        if not self.env.su:
            self._manager()
            if set(vals) & {'token_hash', 'pairing_hash', 'pairing_until', 'state', 'installation_id', 'device_id', 'last_contact', 'last_read', 'last_error', 'latest_source_punch', 'source_rows', 'pending_rows', 'client_version'}:
                raise AccessError(_('Connection status is maintained by the connector.'))
        # Changing interpretation of already published data must not silently rewrite it.
        for rec in self:
            if any(k in vals and vals[k] != rec[k] for k in ('company_id', 'source_group', 'tz', 'code_field')) and rec.event_ids:
                raise UserError(_('This source already has records. Create a new connector for a different source group, company, time zone or code format. Existing records remain available for review.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                if set(vals) - {'name', 'company_id', 'source_type', 'source_group', 'tz', 'history_from', 'interval_minutes', 'code_field', 'publish_punches'}:
                    raise AccessError(_('Use the setup fields to create a connector.'))
        return super().create(vals_list)

    def action_pair(self):
        self.ensure_one()
        self._manager()
        code = secrets.token_urlsafe(24)
        # Re-pairing revokes the former installation immediately.
        self.sudo().write({'pairing_hash': digest(code), 'pairing_until': fields.Datetime.now() + timedelta(minutes=30),
                           'token_hash': False, 'installation_id': False, 'state': 'new'})
        wizard = self.env['pb.clock.connector.pair'].create({'connector_id': self.id, 'code': code})
        self.message_post(body=_('New 30-minute pairing code issued. Previous installation access revoked.'))
        return {'type': 'ir.actions.act_window', 'name': _('Set up on a Windows PC'), 'res_model': wizard._name,
                'res_id': wizard.id, 'view_mode': 'form', 'target': 'new'}

    def action_revoke(self):
        self._manager()
        self.sudo().write({'state': 'revoked', 'token_hash': False, 'pairing_hash': False, 'pairing_until': False})
        for rec in self:
            rec.message_post(body=_('Installation access revoked. Stored records remain available.'))

    def action_records(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Received records'), 'res_model': 'pb.clock.connector.event',
                'view_mode': 'list,form', 'domain': [('connector_id', '=', self.id)], 'context': {'create': False}}

    def action_download(self):
        return {'type': 'ir.actions.act_url', 'url': '/clock-bridge/download', 'target': 'download'}

    def _config(self):
        self.ensure_one()
        return {'connector_id': self.id, 'history_from': str(self.history_from), 'interval_minutes': self.interval_minutes,
                'source_type': self.source_type, 'name': self.name, 'timezone': self.tz}

    @api.model
    def _pair(self, code, installation):
        rec = self.sudo().search([('pairing_hash', '=', digest(code)), ('pairing_until', '>', fields.Datetime.now())], limit=1)
        if not rec:
            return None
        self.env.cr.execute('SELECT id FROM pb_clock_connector WHERE id=%s FOR UPDATE', [rec.id])
        rec.invalidate_recordset()
        if rec.pairing_hash != digest(code) or not rec.pairing_until or rec.pairing_until <= fields.Datetime.now():
            return None
        token = secrets.token_urlsafe(48)
        rec.write({'token_hash': digest(token), 'pairing_hash': False, 'pairing_until': False,
                   'installation_id': installation, 'state': 'connected', 'last_contact': fields.Datetime.now()})
        return {'token': token, 'config': rec._config()}

    @api.model
    def _authenticate(self, token):
        return self.sudo().search([('token_hash', '=', digest(token)), ('state', '=', 'connected')], limit=1) if token else self.browse()

    def _receive(self, payload):
        self.ensure_one()
        # Serialize intake per installation; retries are safe at row level.
        self.env.cr.execute('SELECT id FROM pb_clock_connector WHERE id=%s FOR UPDATE', [self.id])
        rows = payload['rows']
        Event = self.env['pb.clock.connector.event'].sudo().with_context(tracking_disable=True, mail_create_nolog=True, mail_create_nosubscribe=True)
        prepared = []
        for row in rows:
            row = {k: row[k] for k in COLUMNS if k in row} if isinstance(row, dict) else {}
            raw = canonical(row)
            prepared.append((digest(raw), raw))
        seen = set(Event.search([('connector_id', '=', self.id), ('row_hash', 'in', [x[0] for x in prepared])]).mapped('row_hash'))
        vals = []
        for key, raw in prepared:
            if key not in seen:
                vals.append({'connector_id': self.id, 'row_hash': key, 'raw_json': raw})
                seen.add(key)
        if vals:
            Event.create(vals)
            self.env.ref('pb_clock.cron_process_connector')._trigger()
        status = payload.get('status', {})
        updates = {'last_contact': fields.Datetime.now(), 'client_version': str(status.get('version', ''))[:40],
                   'last_error': str(status.get('error', ''))[:2000]}
        if status.get('read_ok'):
            updates.update(last_read=fields.Datetime.now(), source_rows=max(0, min(int(status.get('source_rows', 0)), 2147483647)),
                           latest_source_punch=str(status.get('latest_punch', ''))[:40])
        updates['pending_rows'] = max(0, min(int(status.get('pending', 0)), 2147483647))
        self.write(updates)
        return {'acknowledged': len(rows), 'stored': len(vals), 'duplicates': len(rows) - len(vals), 'config': self._config()}

    def _collection_device(self):
        self.ensure_one()
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s)', [int(digest('%s|%s' % (self.company_id.id, self.source_group.strip()))[:15], 16)])
        serial = 'COLLECTION-' + digest('%s|%s' % (self.company_id.id, self.source_group.strip()))[:32]
        device = self.env['pb.clock.device'].sudo().search([('company_id', '=', self.company_id.id), ('serial', '=', serial)], limit=1)
        if not device:
            device = self.env['pb.clock.device'].sudo().create({'name': self.source_group + ' (collection group)',
                'serial': serial, 'company_id': self.company_id.id, 'kind': 'collection', 'tz': self.tz})
        elif device.tz != self.tz:
            raise UserError(_('This source group already uses a different time zone. Review its configuration.'))
        self.device_id = device
        return device


class ConnectorPair(models.TransientModel):
    _name = 'pb.clock.connector.pair'
    _description = 'Pair a desktop connector'
    connector_id = fields.Many2one('pb.clock.connector', required=True, readonly=True)
    code = fields.Char(readonly=True)


class ConnectorEvent(models.Model):
    _name = 'pb.clock.connector.event'
    _description = 'Received attendance source record'
    _inherit = ['mail.thread']
    _order = 'id desc'
    _rec_name = 'user_code'

    connector_id = fields.Many2one('pb.clock.connector', required=True, ondelete='restrict', index=True, readonly=True)
    company_id = fields.Many2one(related='connector_id.company_id', store=True, index=True)
    row_hash = fields.Char(required=True, readonly=True)
    raw_json = fields.Text(required=True, readonly=True)
    received_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    state = fields.Selection([('pending', 'Received'), ('ready', 'Ready'), ('posted', 'In attendance'),
        ('duplicate', 'Already received'), ('review', 'Review'), ('historical', 'Historical / ignored')], default='pending', required=True, index=True, readonly=True)
    user_code = fields.Char(readonly=True)
    punch_local = fields.Datetime(readonly=True)
    punch_local_display = fields.Char(string='Punch time (source local)', compute='_compute_local_display')
    source_timezone = fields.Selection(related='connector_id.tz', string='Source time zone', readonly=True)
    machine_code = fields.Char(readonly=True, string='Source machine code (not verified terminal)')
    note = fields.Text(readonly=True)
    punch_id = fields.Many2one('pb.clock.punch', readonly=True)
    resolution_note = fields.Text(tracking=True)
    _row_uniq = models.Constraint('UNIQUE(connector_id, row_hash)', 'This source record is already received.')

    @api.depends('punch_local')
    def _compute_local_display(self):
        # This is a wall-clock value, not UTC. A normal datetime widget would
        # incorrectly add the viewer's timezone offset a second time.
        for record in self:
            record.punch_local_display = fields.Datetime.to_string(record.punch_local) if record.punch_local else False

    def write(self, vals):
        if not self.env.su and set(vals) - {'resolution_note'}:
            raise AccessError(_('Source records are immutable. Use review actions or an attendance correction.'))
        return super().write(vals)

    def action_ignore(self):
        self.check_access('write')
        if any(not r.resolution_note for r in self):
            raise UserError(_('Enter a review note before ignoring records.'))
        for rec in self:
            if rec.state in ('posted', 'duplicate'):
                raise UserError(_('This record is already in the punch ledger. Use an attendance correction.'))
            rec.sudo().write({'state': 'historical', 'note': rec.resolution_note})
            rec.message_post(body=_('Reviewed and ignored; collection continues.'))

    def action_retry(self):
        self.check_access('write')
        self.filtered(lambda r: r.state not in ('posted', 'duplicate')).sudo().write({'state': 'pending', 'note': False})

    def _interpret(self):
        self.ensure_one()
        connector = self.connector_id
        row = json.loads(self.raw_json)
        if not isinstance(row, dict) or any(k not in row for k in COLUMNS):
            raise ValueError('The source row does not have the expected Mitaco columns.')
        code = str(row.get(connector.code_field) or '').strip()
        if not code or len(code) > 100:
            raise ValueError('Missing or invalid employee number.')
        local = datetime.strptime(str(row.get('TimeStr', '')), '%Y-%m-%d %H:%M:%S')
        if str(row.get('TimeDate', ''))[:10] != local.strftime('%Y-%m-%d'):
            raise ValueError('Source date and punch timestamp disagree.')
        vals = {'user_code': code, 'punch_local': local, 'machine_code': str(row.get('MachineNo', ''))[:100]}
        if local.date() < connector.history_from:
            self.write(dict(vals, state='historical', note='Before the configured history date.'))
            return
        if local.year < 2015 or local > datetime.utcnow() + timedelta(days=2):
            raise ValueError('The source timestamp needs review.')
        if not connector.publish_punches:
            self.write(dict(vals, state='ready', note='Received. Attendance processing is not enabled for this source.'))
            return
        device = connector._collection_device()
        # Keep source attributes and possible conflicts visible before the ledger's
        # employee/time deduplication collapses a tap.
        existing = self.env['pb.clock.punch'].search([('device_id', '=', device.id), ('user_code', '=', code), ('punch_local', '=', local)], limit=1)
        raw_type = str(row.get('TimeType') or '')
        mode = str(row.get('TimeSource') or '')
        if existing and (existing.direction_raw != (raw_type or False) or existing.verify_mode != (mode or False)):
            self.write(dict(vals, state='review', note='Same employee and time with different source attributes. Existing punch kept; this version is preserved for review.'))
            return
        result = self.env['pb.clock.punch']._ingest([{'device_id': device.id, 'source': 'bridge', 'user_code': code,
            'punch_local': local, 'direction_raw': raw_type, 'direction': 'unknown', 'verify_mode': mode}])
        self.write(dict(vals, state='posted' if result['created'] else 'duplicate', punch_id=result['records'][:1].id,
            note='Collection group attribution; physical terminal not inferred from MachineNo.'))

    @api.model
    def _cron_process(self):
        self.env.cr.execute('''SELECT e.id FROM pb_clock_connector_event e JOIN pb_clock_connector c ON c.id=e.connector_id
            WHERE e.state='pending' OR (e.state='ready' AND c.publish_punches)
            ORDER BY e.id LIMIT 500 FOR UPDATE OF e SKIP LOCKED''')
        rows = self.sudo().browse([r[0] for r in self.env.cr.fetchall()])
        for row in rows:
            try:
                with self.env.cr.savepoint():
                    row._interpret()
            except (ValueError, TypeError, UserError) as exc:
                row.write({'state': 'review', 'note': str(exc)[:2000]})
        if rows:
            self.env.ref('pb_clock.cron_pair_punches')._trigger()
        if len(rows) == 500:
            self.env.ref('pb_clock.cron_process_connector')._trigger()
