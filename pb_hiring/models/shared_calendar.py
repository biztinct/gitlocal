"""Permission-preserving calendar projections. Never copy payroll to calendar.event.

The facade is internal-user only. All source searches retain the caller's ACLs,
record rules and selected companies. Only connector status (never tokens) uses
an existing provider API. A hidden source is absent from payloads, not CSS.
"""
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

PAYROLL_GROUPS = ('om_hr_payroll.group_hr_payroll_user',
                  'pb_hr_payroll_base.group_payroll_base_officer',
                  'pb_comp_ben.group_comp_user', 'pb_comp_ben.group_comp_head')


class PayrollCalendarDate(models.Model):
    _name = 'pb.payroll.calendar.date'
    _description = 'Payroll calendar deadline'
    _order = 'date, id'

    name = fields.Char(required=True)
    date = fields.Date(required=True, index=True)
    kind = fields.Selection([('cutoff', 'Input cut-off'), ('processing', 'Processing'),
        ('approval', 'Approval deadline'), ('payment', 'Payment date'),
        ('filing', 'Statutory filing'), ('other', 'Other')], required=True, default='processing')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    user_ids = fields.Many2many('res.users', string='Payroll team',
        default=lambda self: self.env.user, help='Only these payroll users see this deadline unless Company payroll team is selected.')
    company_wide = fields.Boolean(string='Company payroll team', default=False,
        help='Visible to payroll staff with access to this company. Never shared with other employees.')
    note = fields.Text()
    active = fields.Boolean(default=True)

    @api.constrains('company_wide', 'user_ids')
    def _check_audience(self):
        for rec in self:
            if not rec.company_wide and not rec.user_ids:
                raise ValidationError(_('Choose the payroll team who should see this deadline.'))


class SharedCalendar(models.AbstractModel):
    _name = 'pb.shared.calendar'
    _description = 'Payobook permission-aware calendar'

    def _require(self):
        if not self.env.user._is_internal():
            raise AccessError(_('Calendar is available to signed-in employees.'))

    def _payroll(self):
        # A Settings administrator is not automatically a payroll reader.
        return any(self.env.user.has_group(g) for g in PAYROLL_GROUPS)

    def _range(self, start, stop):
        try:
            first, last = fields.Datetime.to_datetime(start), fields.Datetime.to_datetime(stop)
        except (ValueError, TypeError):
            raise UserError(_('Choose valid calendar dates.'))
        if not first or not last or last <= first or last - first > timedelta(days=63):
            raise UserError(_('Choose a calendar range of up to 63 days.'))
        return first, last

    @api.model
    def can_payroll(self):
        self._require()
        return self._payroll()

    @api.model
    def capabilities(self):
        self._require()
        return {'payroll': self._payroll(), 'admin': self.env.user.has_group('base.group_system'),
                'timezone': self.env.user.tz or 'UTC',
                'payroll_planning': self.env.user.has_group('pb_comp_ben.group_comp_user'),
                'hiring': self.env['pb.hiring'].can_open(),
                'connections': self.env.user.check_synchronization_status(),
                'google_notifications': self.env['pb.calendar.google.channel']._own_status()}

    @api.model
    def events(self, start, stop, local_start=None, local_stop=None):
        self._require()
        first, last = self._range(start, stop)
        date_first = fields.Date.to_date(local_start) if local_start else first.date()
        date_last = fields.Date.to_date(local_stop) if local_stop else last.date()
        if abs((date_first - first.date()).days) > 1 or abs((date_last - last.date()).days) > 1:
            raise UserError(_('Calendar dates do not match the selected range.'))
        out = []
        Interview = self.env['pb.hiring.interview']
        interviews = Interview.search([('start', '<', last), ('stop', '>', first),
            ('state', 'in', ['scheduled', 'done', 'no_show'])], order='start,id', limit=1001)
        for rec in interviews[:1000]:
            out.append({'key': 'interview:%s' % rec.id, 'source': 'interviews',
                'title': _('Interview · %s', rec.candidate_name or _('Candidate')),
                'start': str(rec.start), 'stop': str(rec.stop), 'allday': False,
                'subtitle': rec.job_id.name or '', 'location': rec.location or '',
                'status': rec.state, 'editable': False,
                'detail': _('Manage scheduling and invitations in Hiring.')})
        # Exclude ALL Hiring event copies, even interviews not readable to this
        # user, without looking up their names or IDs with sudo.
        events = self.env['calendar.event'].search([
            ('applicant_id', '=', False),
            '|', ('user_id', '=', self.env.uid), ('partner_ids', 'in', self.env.user.partner_id.ids),
            '|', '&', '&', ('allday', '=', False), ('start', '<', last), ('stop', '>', first),
            '&', '&', ('allday', '=', True), ('start_date', '<', date_last), ('stop_date', '>=', date_first)],
            order='start,id', limit=1001)
        for rec in events[:1000]:
            own = rec.user_id == self.env.user
            source = 'google' if rec.google_id else 'microsoft' if rec.microsoft_id else 'meetings'
            out.append({'key': 'event:%s' % rec.id, 'source': source,
                'title': rec.name or _('Meeting'),
                'start': str(rec.start_date) if rec.allday else str(rec.start),
                'stop': str(rec.stop_date + timedelta(days=1)) if rec.allday else str(rec.stop),
                'allday': rec.allday, 'subtitle': rec.user_id.name or '',
                'location': rec.location or '', 'status': '',
                'editable': own and not rec.recurrency,
                'detail': _('Recurring series: manage this meeting in its calendar.') if rec.recurrency else
                          _('Only the organiser can edit this meeting.') if not own else ''})
        truncated = len(interviews) > 1000 or len(events) > 1000
        if 'hr.leave' in self.env and self.env['hr.leave'].has_access('read'):
            leave = self.env['hr.leave'].search([('state', '=', 'validate'),
                ('date_from', '<', last), ('date_to', '>', first)], limit=1001)
            truncated |= len(leave) > 1000
            for rec in leave[:1000]:
                out.append({'key': 'leave:%s' % rec.id, 'source': 'leave',
                    'title': _('Time off'), 'subtitle': rec.employee_id.name,
                    'start': str(rec.date_from), 'stop': str(rec.date_to),
                    'allday': False, 'location': '', 'status': '', 'editable': False,
                    'detail': _('Approved time off. Manage this request in Time off.')})
        if self._payroll():
            deadlines = self.env['pb.payroll.calendar.date'].search([
                ('date', '>=', date_first), ('date', '<', date_last)], limit=1001)
            truncated |= len(deadlines) > 1000
            for rec in deadlines[:1000]:
                out.append(self._date_row('deadline:%s' % rec.id, rec.name, rec.date,
                    rec.company_id.name, rec.note or '', True))
            months = self.env['pb.payroll.calendar'].search([
                '|', '&', ('cutoff_date', '>=', date_first), ('cutoff_date', '<', date_last),
                '&', ('pay_date', '>=', date_first), ('pay_date', '<', date_last)], limit=1001)
            truncated |= len(months) > 1000
            for rec in months[:1000]:
                for key, label, day in [('cutoff', _('Payroll input cut-off'), rec.cutoff_date),
                                        ('payday', _('Payday'), rec.pay_date)]:
                    if date_first <= day < date_last:
                        out.append(self._date_row('paymonth:%s:%s' % (rec.id, key), label, day,
                            '%s · %s' % (rec.company_id.name or _('All companies'), rec.name),
                            _('Saved in Payroll planning. Open the source to view this month.')))
            out.extend(self._payroll_rules(date_first, date_last))
        return {'events': out, 'truncated': truncated}

    def _date_row(self, key, name, day, subtitle, detail='', editable=False):
        return {'key': key, 'source': 'payroll', 'title': name, 'start': str(day),
                'stop': str(day + timedelta(days=1)), 'allday': True,
                'subtitle': subtitle, 'detail': detail, 'location': '',
                'status': '', 'editable': editable}

    def _payroll_rules(self, first, last):
        # Optional installed source. No guessed paydays from an unconfigured
        # default: only an explicitly saved, published monthly scheme is used.
        if 'pb.blueprint.studio' not in self.env:
            return []
        Config = self.env['hr.formula.config']
        Blueprint = self.env['pb.formula.blueprint']
        if not Config.has_access('read') or not Blueprint.has_access('read'):
            return []
        configs = Config.search([('company_id', 'in', self.env.companies.ids),
                                 ('state', '=', 'active')])
        studio = self.env['pb.blueprint.studio']
        rows = []
        for bp in Blueprint.search([('config_id', 'in', configs.ids)]):
            config = bp.config_id
            if config.cycle_type != 'regular' or not bp.calendar().get('calendar'):
                continue
            prefs, _payment = studio._calendar_prefs(bp)
            # Include next month: a cut-off relative to its payday can fall
            # inside the displayed previous month.
            month = first.replace(day=1)
            until = (last.replace(day=28) + timedelta(days=4)).replace(day=1)
            while month <= until:
                preview = studio._payday_preview(config, bp, prefs, month.strftime('%Y-%m'))
                if preview:
                    for key, label, value in [('payday', _('Payday'), preview['date']),
                        ('cutoff', _('Payroll input cut-off'), (preview.get('cutoff') or {}).get('date'))]:
                        day = fields.Date.to_date(value) if value else None
                        if day and first <= day < last and (not bp.effective_from or day >= bp.effective_from):
                            rows.append(self._date_row('scheme:%s:%s:%s' % (config.id, key, day),
                                label, day, config.name,
                                _('Calculated from the payroll scheme’s saved calendar rules. Change the rule in payroll setup.')))
                month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        return rows

    @api.model
    def open_record(self, key):
        self._require()
        try:
            kind, raw_id, *_suffix = str(key).split(':')
            record_id = int(raw_id)
        except (ValueError, TypeError):
            raise UserError(_('That calendar item is not valid.'))
        if kind == 'deadline':
            if not self._payroll():
                raise AccessError(_('Payroll dates are available to payroll staff only.'))
            rec = self.env['pb.payroll.calendar.date'].browse(record_id).exists()
        elif kind == 'interview':
            rec = self.env['pb.hiring.interview'].browse(record_id).exists()
        elif kind == 'event':
            rec = self.env['calendar.event'].browse(record_id).exists()
        elif kind == 'leave':
            rec = self.env['hr.leave'].browse(record_id).exists()
        elif kind == 'paymonth':
            if not self._payroll():
                raise AccessError(_('Payroll dates are available to payroll staff only.'))
            rec = self.env['pb.payroll.calendar'].browse(record_id).exists()
        elif kind == 'scheme':
            if not self._payroll():
                raise AccessError(_('Payroll dates are available to payroll staff only.'))
            rec = self.env['hr.formula.config'].browse(record_id).exists()
        else:
            raise UserError(_('That calendar item is not valid.'))
        rec.check_access('read')
        if not rec:
            raise UserError(_('This item is no longer available.'))
        if kind == 'interview':
            # The existing board owns reason capture, invitation review and
            # rescheduling. Never mutate an interview via the generic editor.
            return {'type': 'ir.actions.client', 'tag': 'pb_hiring_hub',
                    'context': {'pb_lens': 'overview', 'pb_role_id': rec.requisition_id.id}}
        return {'type': 'ir.actions.act_window', 'res_model': rec._name, 'res_id': rec.id,
                'views': [(False, 'form')], 'target': 'new',
                'context': {'form_view_initial_mode': 'edit' if kind == 'deadline' else 'view'}}

    @api.model
    def new_event(self):
        self._require()
        return {'type': 'ir.actions.act_window', 'res_model': 'calendar.event',
                'views': [(False, 'form')], 'target': 'new',
                'context': {'default_user_id': self.env.uid, 'default_privacy': 'private',
                            'default_partner_ids': [(6, 0, self.env.user.partner_id.ids)]}}

    @api.model
    def payroll_dates_action(self):
        self._require()
        if not self._payroll():
            raise AccessError(_('Payroll dates are available to payroll staff only.'))
        return self.env.ref('pb_hiring.action_payroll_calendar_dates').read()[0]

    @api.model
    def provider_action(self, provider, operation):
        self._require()
        if provider not in ('google', 'microsoft') or operation not in ('pause', 'resume'):
            raise UserError(_('Choose a supported calendar connection.'))
        # Pin to the session user: no caller-supplied user IDs or credentials.
        statuses = self.env.user.check_synchronization_status()
        other = 'microsoft' if provider == 'google' else 'google'
        if operation == 'resume' and statuses.get(other + '_calendar') == 'sync_active':
            raise UserError(_('Pause the other connection first. One active synchronisation avoids copying meetings between accounts.'))
        getattr(self.env.user, ('stop_' if operation == 'pause' else 'restart_') + provider + '_synchronization')()
        return self.capabilities()

    @api.model
    def settings_action(self):
        self._require()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only an administrator can configure calendar providers.'))
        action = self.env.ref('base_setup.action_general_configuration').read()[0]
        action['context'] = {'module': 'calendar'}
        return action
