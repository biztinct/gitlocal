"""Panel availability and expiring candidate booking links."""
import json
import os
import subprocess
import sys
from pathlib import Path
import secrets
from datetime import datetime, timedelta, timezone

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class HiringBooking(models.Model):
    _name = 'pb.hiring.booking'
    _description = 'Interview booking invitation'
    _rec_name = 'applicant_id'

    applicant_id = fields.Many2one('hr.applicant', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='applicant_id.company_id', store=True)
    organiser_id = fields.Many2one('res.users', required=True, default=lambda s: s.env.user)
    panel_ids = fields.Many2many('hr.employee', string='Interview panel', required=True)
    provider = fields.Selection([('google', 'Google Calendar'), ('microsoft', 'Microsoft Outlook')], required=True, default='google')
    date_from = fields.Date(required=True, default=lambda s: fields.Date.today() + timedelta(days=1))
    date_to = fields.Date(required=True, default=lambda s: fields.Date.today() + timedelta(days=7))
    duration = fields.Integer(string='Minutes', default=45, required=True)
    tz = fields.Selection(selection=lambda s: [(x,x) for x in pytz.all_timezones], string='Working-hours timezone', default=lambda s: s.env.user.tz or 'UTC', required=True)
    hour_from = fields.Integer(string='Start of working day', default=9)
    hour_to = fields.Integer(string='End of working day', default=17)
    location = fields.Char(string='Location or video link')
    mode = fields.Selection([('in_person', 'In person'), ('video', 'Video'), ('phone', 'Phone')], default='video', required=True)
    state = fields.Selection([('draft', 'Choose panel'), ('ready', 'Ready to share'), ('booked', 'Booked'), ('cancelled', 'Cancelled')], default='draft', readonly=True)
    token = fields.Char(default=lambda s: secrets.token_urlsafe(32), copy=False, groups='base.group_system')
    expires_at = fields.Datetime(default=lambda s: fields.Datetime.now() + timedelta(days=7), required=True)
    slot_ids = fields.One2many('pb.hiring.booking.slot', 'booking_id', readonly=True)
    interview_id = fields.Many2one('pb.hiring.interview', readonly=True, copy=False)
    booking_url = fields.Char(compute='_compute_url')

    def _compute_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        for rec in self:
            rec.booking_url = base + '/hiring/book/' + rec.sudo().token if rec.state == 'ready' else ''

    def _gate(self):
        self.ensure_one()
        self.check_access('write')
        self.env['pb.hiring']._require_recruit(self.applicant_id.pb_requisition_id)
        if self.organiser_id != self.env.user and not self.env.su:
            raise UserError(_('Create the booking as the organiser whose calendar is connected.'))

    @api.constrains('date_from', 'date_to', 'duration', 'hour_from', 'hour_to')
    def _check_window(self):
        for rec in self:
            if rec.date_to < rec.date_from or (rec.date_to - rec.date_from).days > 14:
                raise ValidationError(_('Choose a window of at most fourteen days.'))
            if not 15 <= rec.duration <= 180 or not 0 <= rec.hour_from < rec.hour_to <= 24:
                raise ValidationError(_('Choose a duration of 15–180 minutes and valid working hours.'))

    def write(self, vals):
        if set(vals) & {'applicant_id','organiser_id','panel_ids','provider','date_from','date_to','duration','tz','hour_from','hour_to','location','mode'}:
            if any(r.state == 'booked' for r in self):
                raise UserError(_('Reschedule the interview from the interview record.'))
            vals = dict(vals, state='draft', token=secrets.token_urlsafe(32))
            self.slot_ids.sudo().unlink()
        return super().write(vals)

    @api.model
    def _provider_busy(self, provider, user, emails, start, stop):
        if not emails or any(not e for e in emails):
            raise UserError(_('Every panellist needs a work email address.'))
        if provider not in ('google', 'microsoft'):
            raise UserError(_('Choose Google or Microsoft.'))
        getter = '_get_google_calendar_token' if provider == 'google' else '_get_microsoft_calendar_token'
        token = getattr(user.sudo(), getter)()
        if not token:
            raise UserError(_('Connect your calendar before checking availability.'))
        payload = dict(provider=provider,token=token,emails=emails,start=start.isoformat(),stop=stop.isoformat())
        runner = Path(__file__).resolve().parent.parent / 'services' / 'calendar_sdk.py'
        try:
            result = subprocess.run([sys.executable, '-I', str(runner)], input=json.dumps(payload),
                text=True, capture_output=True, timeout=35, check=False)
            data = json.loads(result.stdout)
            if result.returncode or 'busy' not in data:
                raise ValueError()
            return [(utc(a),utc(b)) for a,b in data['busy']]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise UserError(_('Calendar availability could not be read. Check organiser consent, panel sharing and SDK installation.')) from None

    def _busy(self, start, stop):
        self.ensure_one()
        conn = self.env['pb.hiring.connection']._for_company(self.provider, self.company_id)
        if not conn:
            raise UserError(_('Enable this calendar in Hiring connections first.'))
        conn._ready()
        emails = list(set(self.panel_ids.mapped('work_email') + [self.organiser_id.email]))
        if len(self.panel_ids.filtered(lambda p: not p.work_email)):
            raise UserError(_('Add a work email address for every panellist.'))
        busy = self._provider_busy(self.provider, self.organiser_id, emails, start, stop)
        people = self.panel_ids.user_id | self.organiser_id
        interviews = self.env['pb.hiring.interview'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'scheduled'),
            ('start', '<', stop), ('stop', '>', start), '|', '|',
            ('panel_employee_ids', 'in', self.panel_ids.ids),
            ('panel_employee_ids.user_id', 'in', people.ids), ('recruiter_id', 'in', people.ids)])
        return busy + [(i.start, i.stop) for i in interviews]

    def action_find_slots(self):
        self._gate()
        if not self.panel_ids or self.panel_ids.filtered(lambda p: p.company_id != self.company_id):
            raise UserError(_('Choose a panel from this company.'))
        if self.state == 'booked':
            raise UserError(_('This invitation has already been booked.'))
        zone = pytz.timezone(self.tz)
        start = utc(zone.localize(datetime.combine(self.date_from, datetime.min.time())))
        stop = utc(zone.localize(datetime.combine(self.date_to + timedelta(days=1), datetime.min.time())))
        busy = self._busy(start, stop)
        slots = []
        day = self.date_from
        while day <= self.date_to:
            if day.weekday() < 5:
                for minute in range(self.hour_from * 60, self.hour_to * 60 - self.duration + 1, 30):
                    point = utc(zone.localize(datetime.combine(day, datetime.min.time()) + timedelta(minutes=minute)))
                    end = point + timedelta(minutes=self.duration)
                    if point > fields.Datetime.now() + timedelta(minutes=30) and not any(a < end and b > point for a,b in busy):
                        slots.append((0,0,{'start': point, 'stop': end}))
            day += timedelta(days=1)
        self.sudo().slot_ids.unlink()
        self.sudo().write({'slot_ids': slots[:120], 'state': 'ready' if slots else 'draft'})
        if not slots:
            raise UserError(_('No shared slots were found. Change the date range or panel.'))
        return True

    def action_cancel(self):
        self._gate()
        if self.state == 'booked':
            raise UserError(_('Cancel the interview from its record.'))
        self.sudo().write({'state': 'cancelled', 'token': secrets.token_urlsafe(32)})
        return True

    def _book(self, slot_id):
        """Called only after the controller validates the bearer link."""
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM pb_hiring_booking WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.state != 'ready' or self.expires_at <= fields.Datetime.now():
            raise UserError(_('This booking link has expired or has already been used.'))
        slot = self.slot_ids.filtered(lambda s: s.id == slot_id)
        if not slot or slot.start <= fields.Datetime.now() + timedelta(minutes=30):
            raise UserError(_('Choose an available future slot.'))
        # Serialise overlapping panel bookings made by this application.
        for person in self.panel_ids.sorted('id'):
            self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', [19023, person.id])
        for user in (self.panel_ids.user_id | self.organiser_id).sorted('id'):
            self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', [19024, user.id])
        if any(a < slot.stop and b > slot.start for a,b in self._busy(slot.start, slot.stop)):
            raise UserError(_('That time has just become busy. Please choose another slot.'))
        interview = self.env['pb.hiring.interview'].sudo().schedule({
            'applicant_id': self.applicant_id.id, 'requisition_id': self.applicant_id.pb_requisition_id.id,
            'recruiter_id': self.organiser_id.id, 'panel_employee_ids': self.panel_ids.ids,
            'start': fields.Datetime.to_string(slot.start), 'duration_minutes': self.duration,
            'mode': self.mode, 'location': self.location or ''})
        self.write({'interview_id': interview.id, 'state': 'booked'})
        return interview


class BookingSlot(models.Model):
    _name = 'pb.hiring.booking.slot'
    _description = 'Available interview slot'
    _order = 'start'
    booking_id = fields.Many2one('pb.hiring.booking', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='booking_id.company_id', store=True)
    start = fields.Datetime(required=True)
    stop = fields.Datetime(required=True)


class ApplicantBooking(models.Model):
    _inherit = 'hr.applicant'

    def action_booking_invitation(self):
        self.ensure_one()
        self.check_access('read')
        self.env['pb.hiring']._require_recruit(self.pb_requisition_id)
        return {'type': 'ir.actions.act_window', 'name': _('Find a panel interview time'),
                'res_model': 'pb.hiring.booking', 'views': [(False, 'form')], 'target': 'current',
                'context': {'default_applicant_id': self.id}}
