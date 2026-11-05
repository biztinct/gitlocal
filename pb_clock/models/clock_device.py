# -*- coding: utf-8 -*-
"""pb.clock.device — one attendance machine, or the company's upload pseudo
device ("Files you upload").

CLOCK-2 uses `serial` + `allowed` as the allow-list for machines that push to
Payobook; CLOCK-1 only needs a device per ledger row so the dedup key and the
local time zone of a punch are defined.
"""

from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.addons.base.models.res_partner import _tz_get


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
    allowed = fields.Boolean(string='Allowed', default=True)
    tz = fields.Selection(
        _tz_get, string='Time zone',
        default=lambda self: self._default_tz())
    last_punch_at = fields.Datetime(string='Last punch', readonly=True)
    last_seen_at = fields.Datetime(string='Last heard from', readonly=True)
    punches_today = fields.Integer(
        string='Punches today', compute='_compute_punches_today')
    active = fields.Boolean(default=True)

    _serial_company_uniq = models.Constraint(
        'UNIQUE(company_id, serial)',
        'This serial number is already registered for this company.')

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

    def _local_today_bounds_utc(self, now=None):
        """[start, end) of TODAY in this device's zone, as naive UTC."""
        self.ensure_one()
        tzinfo = self._tzinfo()
        now = now or fields.Datetime.now()
        local_now = pytz.UTC.localize(now).astimezone(tzinfo)
        start = tzinfo.localize(datetime.combine(local_now.date(), datetime.min.time()))
        start_utc = start.astimezone(pytz.UTC).replace(tzinfo=None)
        return start_utc, start_utc + timedelta(days=1)

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
