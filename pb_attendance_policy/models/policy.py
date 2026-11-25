import json
from datetime import datetime, time, timedelta

import pytz
from markupsafe import Markup, escape
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.pb_attendance_flow.models.hr_attendance import PB_ATT_CORRECTION_CTX, _CORR_TOKEN
from odoo.addons.pb_clock.models import clock_code
from ..engine import calculate

_STATE_TOKEN = object()
_CALC_TOKEN = object()
_CALC_FIELDS = {'pb_calculation_json', 'pb_calculation_status', 'pb_normal_hours', 'pb_overtime_hours', 'pb_deduction_hours', 'pb_worked_hours'}


def manager(env):
    if not env.su and not env.user.has_group('hr_attendance.group_hr_attendance_manager'):
        raise AccessError(_('Attendance managers configure calculation policies.'))


class Policy(models.Model):
    _name = 'pb.attendance.policy'
    _description = 'Attendance calculation policy'
    _inherit = ['mail.thread']
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    tz = fields.Selection(_tz_get, required=True, default='UTC', tracking=True)
    state = fields.Selection([('draft', 'Draft / review'), ('active', 'Active'), ('retired', 'Retired')], default='draft', required=True, tracking=True)
    capture_before = fields.Float(default=2., required=True, string='Capture before shift (hours)')
    capture_after = fields.Float(default=2., required=True, string='Capture after shift (hours)')
    night_premium = fields.Boolean(string='Calculate overlapping night-premium hours', default=False)
    night_start = fields.Float(string='Night starts (local hour)', default=22.)
    night_end = fields.Float(string='Night ends (local hour)', default=6.)
    band_ids = fields.One2many('pb.attendance.policy.band', 'policy_id', string='Additional lateness deductions', copy=True)
    shift_ids = fields.One2many('pb.attendance.policy.shift', 'policy_id', string='Shift calculation rules', copy=True)
    note = fields.Text(string='Source and assumptions')
    # Exact first/last is explicit; no alternate modes are silently inferred.
    pairing = fields.Selection([('first_last', 'First check-in / last check-out within assigned shift')], default='first_last', required=True)
    deduction_basis = fields.Selection([('worked', 'Additional deduction from hours already worked')], default='worked', required=True)
    allocation = fields.Selection([('start', 'Allocate the whole shift to its start date')], default='start', required=True)

    @api.constrains('capture_before', 'capture_after', 'night_start', 'night_end')
    def _bounds(self):
        for r in self:
            if not (0 <= r.capture_before <= 6 and 0 <= r.capture_after <= 6):
                raise ValidationError(_('Capture windows must be between zero and six hours.'))
            if not (0 <= r.night_start < 24 and 0 <= r.night_end < 24) or r.night_start == r.night_end:
                raise ValidationError(_('Enter distinct night start/end hours between zero and 24.'))

    def write(self, vals):
        manager(self.env)
        if any(r.state != 'draft' for r in self) and set(vals) - {'state'}:
            raise UserError(_('Duplicate an active policy to change its rules. Existing calculations keep their original policy.'))
        if 'state' in vals and self.env.context.get('_policy_state_action') is not _STATE_TOKEN:
            raise UserError(_('Use the Activate or Retire button.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        manager(self.env)
        if any(v.get('state', 'draft') != 'draft' for v in vals_list):
            raise UserError(_('Create a draft policy first.'))
        return super().create(vals_list)

    def action_activate(self):
        manager(self.env)
        for p in self:
            if p.state != 'draft' or not p.shift_ids:
                raise UserError(_('A draft policy with shift rules is required.'))
            for category in ('worker', 'manager'):
                bands = p.band_ids.filtered(lambda b: b.category == category).sorted('minimum')
                cursor = 0.
                if not bands or any(not b.confirmed for b in bands):
                    raise UserError(_('Confirm every lateness band for both employee groups first.'))
                for b in bands:
                    if cursor is None or b.minimum != cursor:
                        raise UserError(_('Lateness bands must cover zero minutes upward without gaps or overlaps.'))
                    cursor = None if b.open_ended else b.maximum
                if cursor is not None:
                    raise UserError(_('The final lateness band must have no upper limit.'))
            p.with_context(_policy_state_action=_STATE_TOKEN).write({'state': 'active'})

    def action_retire(self):
        manager(self.env)
        self.with_context(_policy_state_action=_STATE_TOKEN).write({'state': 'retired'})

    def copy(self, default=None):
        return super().copy(dict(default or {}, state='draft', name=self.name + ' (revision)'))

    def unlink(self):
        if any(p.state != 'draft' for p in self):
            raise UserError(_('Retain active and retired policies for audit.'))
        return super().unlink()


class PolicyChild(models.AbstractModel):
    _name = 'pb.attendance.policy.child'
    _description = 'Editable draft policy rule'

    @api.model_create_multi
    def create(self, vals_list):
        manager(self.env)
        records = super().create(vals_list)
        records._editable()
        return records

    def _editable(self):
        manager(self.env)
        if any(r.policy_id.state != 'draft' for r in self):
            raise UserError(_('Rules of an active or retired policy cannot be changed. Duplicate the policy.'))

    def write(self, vals):
        self._editable()
        result = super().write(vals)
        self._editable()
        return result

    def unlink(self):
        self._editable()
        return super().unlink()


class Band(models.Model):
    _name = 'pb.attendance.policy.band'
    _inherit = 'pb.attendance.policy.child'
    _description = 'Lateness deduction band'
    _order = 'category, minimum'
    policy_id = fields.Many2one('pb.attendance.policy', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='policy_id.company_id', store=True)
    category = fields.Selection([('worker', 'Worker'), ('manager', 'Manager / supervisor')], required=True)
    minimum = fields.Float(string='From minutes (inclusive)', required=True)
    maximum = fields.Float(string='To minutes (exclusive)')
    open_ended = fields.Boolean(string='No upper limit')
    hours = fields.Float(string='Additional hours deducted')
    confirmed = fields.Boolean(string='Confirmed', default=False)
    note = fields.Char()

    @api.constrains('minimum', 'maximum', 'open_ended', 'hours')
    def _check_band(self):
        for b in self:
            if b.minimum < 0 or b.hours < 0 or b.hours > 24 or (not b.open_ended and b.maximum <= b.minimum):
                raise ValidationError(_('Enter a positive interval and a deduction between zero and 24 hours.'))


class ShiftRule(models.Model):
    _name = 'pb.attendance.policy.shift'
    _inherit = 'pb.attendance.policy.child'
    _description = 'Shift normal-hours and breaks'
    _check_company_auto = True
    policy_id = fields.Many2one('pb.attendance.policy', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='policy_id.company_id', store=True)
    template_id = fields.Many2one('hr.shift.template', required=True, check_company=True)
    normal_end_offset = fields.Float(string='Normal window ends after (elapsed hours)', required=True, default=9.)
    break_start_offset = fields.Float(string='Unpaid break starts after (elapsed hours)', required=True, default=4.)
    break_hours = fields.Float(string='Unpaid break hours', required=True, default=1.)
    normal_hours = fields.Float(string='Planned normal hours', compute='_normal')
    note = fields.Char(string='Source / inference')
    _unique = models.Constraint('UNIQUE(policy_id,template_id)', 'Each shift needs one calculation rule per policy.')

    @api.depends('normal_end_offset', 'break_start_offset', 'break_hours')
    def _normal(self):
        for r in self:
            r.normal_hours = r.normal_end_offset - max(0, min(r.break_hours, r.normal_end_offset-r.break_start_offset))

    @api.constrains('normal_end_offset', 'break_start_offset', 'break_hours', 'template_id')
    def _check_rule(self):
        for r in self:
            t = r.template_id
            span = (t.end_hour-t.start_hour) + (24 if t.is_overnight else 0)
            if not 0 < r.normal_end_offset <= span or r.break_start_offset < 0 or r.break_hours < 0 or r.break_start_offset+r.break_hours > span:
                raise ValidationError(_('Normal hours and the unpaid break must fit inside the shift.'))


class Employee(models.Model):
    _inherit = 'hr.employee'
    pb_attendance_category = fields.Selection([('worker', 'Worker'), ('manager', 'Manager / supervisor')], string='Attendance deduction group', groups='hr.group_hr_user')
    pb_attendance_policy_id = fields.Many2one('pb.attendance.policy', string='Attendance calculation policy', check_company=True, groups='hr.group_hr_user')



class Roster(models.Model):
    _inherit = 'hr.shift.planning'
    pb_policy_id = fields.Many2one('pb.attendance.policy', string='Calculation policy', check_company=True)
    pb_day_kind = fields.Selection([('weekday', 'Normal working day'), ('weekend', 'Rest-day overtime'), ('holiday', 'Public-holiday overtime')], default='weekday', required=True)
    pb_category = fields.Selection([('worker', 'Worker'), ('manager', 'Manager / supervisor')], string='Group for this shift', help='Blank uses the employee setting. Fixed when attendance is generated, preserving history when an employee changes role.')
    pb_inferred = fields.Boolean(string='Suggested from punch history')
    pb_evidence = fields.Text(string='Pattern evidence / assumptions')
    pb_calculation_json = fields.Text(readonly=True, copy=False)
    pb_calculation_status = fields.Char(readonly=True, copy=False)
    pb_calculation_summary = fields.Html(compute='_calculation_summary', string='Calculation detail')
    pb_normal_hours = fields.Float(string='Payable normal hours', readonly=True, copy=False)
    pb_overtime_hours = fields.Float(string='Payable overtime hours', readonly=True, copy=False)
    pb_deduction_hours = fields.Float(string='Additional deduction hours', readonly=True, copy=False)
    pb_worked_hours = fields.Float(string='Worked hours after break', readonly=True, copy=False)
    pb_attendance_id = fields.Many2one('hr.attendance', readonly=True, copy=False, ondelete='restrict')
    pb_corrected_in = fields.Datetime(readonly=True, copy=False)
    pb_corrected_out = fields.Datetime(readonly=True, copy=False)

    @api.depends('pb_calculation_json')
    def _calculation_summary(self):
        for r in self:
            data = json.loads(r.pb_calculation_json or '{}')
            if not data:
                r.pb_calculation_summary = '<p>Preview this shift to see the calculation.</p>'
                continue
            if data.get('error'):
                r.pb_calculation_summary = Markup('<p>%s</p>') % escape(data['error'])
                continue
            rows = [('First check-in', data.get('first', '')), ('Last check-out', data.get('last', '')),
                    ('Late by (minutes)', round(data.get('late_minutes', 0), 2)),
                    ('Unpaid break (hours)', round(data.get('break_hours', 0), 4)),
                    ('Worked after break (hours)', round(data.get('worked_hours', 0), 4)),
                    ('Additional deduction (hours)', round(data.get('penalty_hours', 0), 4)),
                    ('Payable normal (hours)', round(data.get('normal_hours', 0), 4)),
                    ('Payable overtime (hours)', round(data.get('overtime_hours', 0), 4)),
                    ('Night premium overlap (hours)', round(data.get('night_hours', 0), 4))]
            r.pb_calculation_summary = Markup('<table class="table table-sm">%s</table>') % Markup('').join(
                Markup('<tr><th>%s</th><td>%s</td></tr>') % (escape(k), escape(v)) for k, v in rows)

    @api.constrains('employee_id', 'company_id', 'pb_policy_id', 'shift_template_id', 'date', 'start_datetime', 'end_datetime')
    def _policy_scope(self):
        for r in self.filtered('pb_policy_id'):
            if r.company_id != r.employee_id.company_id or r.pb_policy_id.company_id != r.company_id or r.shift_template_id.company_id != r.company_id:
                raise ValidationError(_('Employee, shift and policy must belong to the same company.'))
            start = pytz.utc.localize(r.start_datetime).astimezone(pytz.timezone(r.pb_policy_id.tz))
            if start.date() != r.date or r.end_datetime <= r.start_datetime or r.end_datetime-r.start_datetime > timedelta(hours=24):
                raise ValidationError(_('Use the local shift start date and a positive shift duration of at most 24 hours.'))

    @api.onchange('employee_id')
    def _onchange_policy_employee(self):
        self.pb_policy_id = self.employee_id.pb_attendance_policy_id

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if set(v) & (_CALC_FIELDS | {'pb_attendance_id', 'pb_corrected_in', 'pb_corrected_out'}):
                raise AccessError(_('Calculated fields are filled by the calculation workflow.'))
            if 'pb_policy_id' not in v and v.get('employee_id'):
                p = self.env['hr.employee'].browse(v['employee_id']).pb_attendance_policy_id
                if p:
                    v['pb_policy_id'] = p.id
        return super().create(vals_list)

    def write(self, vals):
        if (set(vals) & (_CALC_FIELDS | {'pb_attendance_id', 'pb_corrected_in', 'pb_corrected_out'})) and self.env.context.get('_attendance_calc') is not _CALC_TOKEN:
            raise AccessError(_('Use Preview or Recalculate to update calculated hours.'))
        if set(vals) & {'employee_id', 'date', 'start_datetime', 'end_datetime', 'shift_template_id', 'pb_policy_id', 'pb_day_kind', 'pb_category', 'state'} and self.env.context.get('_attendance_calc') is not _CALC_TOKEN:
            for r in self.filtered('pb_attendance_id'):
                reason = self.env['pb.clock.pairing']._guards(r.employee_id, {r.date}).get(r.date)
                if reason:
                    raise UserError(reason)
                if set(vals) & {'employee_id', 'date', 'state'}:
                    raise UserError(_('This roster has generated attendance. Use an attendance correction; do not move its source shift.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered('pb_attendance_id'):
            raise UserError(_('A roster with generated attendance must be retained for audit.'))
        return super().unlink()

    def _pb_clock_codes(self, code):
        """The numbers a clock may have sent for this person, or None.

        WFSETUP P10b (owner ruling R8): the identity convention of the clock
        matcher itself (`pb.clock.pairing._code_index`) — exact number first,
        then leading zeros ignored when exactly one person holds that
        zero-free number. A number whose zero-free form two people share, or
        whose exact spelling is somebody else's, is ambiguous (None): the
        calculation refuses rather than take another person's punches. Every
        spelling that resolves to this person is searched, so a clock that
        drops zeros ("12" for badge "012") and one that adds them are both read.
        """
        if not code.isdigit():
            return {code}
        candidates = sorted(clock_code.variants(code))
        detail = {}
        index = self.env['pb.clock.pairing']._code_index(self.company_id, candidates, detail)
        if detail.get('shared') or index.get(code) != self.employee_id:
            return None
        return {v for v in candidates if index.get(v) == self.employee_id}

    def _policy_calculate(self):
        self.ensure_one()
        policy = self.pb_policy_id
        rule = policy.shift_ids.filtered(lambda r: r.template_id == self.shift_template_id)
        if not policy or len(rule) != 1:
            return {'error': 'Choose a policy containing this shift template.'}
        category = self.pb_category or self.employee_id.pb_attendance_category
        if not category:
            return {'error': 'Set the employee attendance deduction group.'}
        zone = pytz.timezone(policy.tz)
        start = pytz.utc.localize(self.start_datetime).astimezone(zone)
        end = pytz.utc.localize(self.end_datetime).astimezone(zone)
        low, high = start-timedelta(hours=policy.capture_before), end+timedelta(hours=policy.capture_after)
        # Reject overlapping capture windows: never assign one punch to two shifts.
        others = self.search([('employee_id', '=', self.employee_id.id), ('id', '!=', self.id),
            ('state', '!=', 'cancelled'), ('start_datetime', '<', (high+timedelta(hours=6)).astimezone(pytz.utc).replace(tzinfo=None)),
            ('end_datetime', '>', (low-timedelta(hours=6)).astimezone(pytz.utc).replace(tzinfo=None))])
        others = others.filtered(lambda o:
            pytz.utc.localize(o.start_datetime)-timedelta(hours=o.pb_policy_id.capture_before if o.pb_policy_id else 0) < high
            and pytz.utc.localize(o.end_datetime)+timedelta(hours=o.pb_policy_id.capture_after if o.pb_policy_id else 0) > low)
        if others:
            return {'error': 'Another shift overlaps this capture window. Review the roster or shorten capture windows.'}
        code = (self.employee_id.pb_clock_code or self.employee_id.barcode or '').strip()
        if not code:
            return {'error': 'Employee has no clock number or badge ID.'}
        codes = self._pb_clock_codes(code)
        if codes is None:
            return {'error': 'Clock number is ambiguous. Set a unique clock number.'}
        events = self.env['pb.clock.connector.event'].search([
            ('company_id', '=', self.company_id.id), ('user_code', 'in', list(codes)),
            ('state', 'in', ['ready', 'posted', 'duplicate']),
            ('punch_local', '>=', low.replace(tzinfo=None)), ('punch_local', '<=', high.replace(tzinfo=None)),
            ('connector_id.tz', '=', policy.tz)])
        points = []
        for e in events:
            try:
                points.append(zone.localize(e.punch_local, is_dst=None))
            except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
                return {'error': 'A punch falls in an ambiguous clock-change interval. Review its time zone.'}
        ledger = self.env['pb.clock.punch'].search([('employee_id', '=', self.employee_id.id),
            ('punch_utc', '>=', low.astimezone(pytz.utc).replace(tzinfo=None)),
            ('punch_utc', '<=', high.astimezone(pytz.utc).replace(tzinfo=None)),
            ('state', 'in', ['matched', 'paired', 'middle', 'held', 'ignored_duplicate_tap'])])
        points.extend(pytz.utc.localize(p.punch_utc).astimezone(zone) for p in ledger)
        if self.pb_corrected_in and self.pb_corrected_out:
            points = [pytz.utc.localize(dt).astimezone(zone) for dt in (self.pb_corrected_in, self.pb_corrected_out)]
            if points[0] < low or points[-1] > high:
                return {'error': 'Approved correction is outside this shift capture window. Review the roster.'}
        if high.astimezone(pytz.utc).replace(tzinfo=None) > fields.Datetime.now():
            return {'error': 'This shift capture window has not finished yet.'}
        breaks = [(start+timedelta(hours=rule.break_start_offset), start+timedelta(hours=rule.break_start_offset+rule.break_hours))]
        bands = [{'category': b.category, 'minimum': b.minimum,
                  'maximum': None if b.open_ended else b.maximum, 'hours': b.hours, 'confirmed': b.confirmed} for b in policy.band_ids]
        night_intervals = []
        if policy.night_premium:
            for offset in (-1, 0, 1, 2):
                midnight = datetime.combine(start.date()+timedelta(days=offset), time.min)
                a = midnight + timedelta(hours=policy.night_start)
                b = midnight + timedelta(hours=policy.night_end, days=1 if policy.night_end < policy.night_start else 0)
                night_intervals.append((zone.localize(a, is_dst=None), zone.localize(b, is_dst=None)))
        result = calculate(points, start, start+timedelta(hours=rule.normal_end_offset), end, breaks, bands, category, self.pb_day_kind, night_intervals)
        result.update(policy_id=policy.id, shift_rule_id=rule.id, roster_id=self.id, employee_id=self.employee_id.id,
                      work_date=str(self.date), source_event_ids=events.ids, pairing='first_last', category=category,
                      policy_state=policy.state, source_punch_ids=ledger.ids, corrected=bool(self.pb_corrected_in))
        return result

    def action_preview_calculation(self):
        manager(self.env)
        for r in self:
            result = r._policy_calculate()
            if r.pb_attendance_id:
                raise UserError(_('Use Recalculate for a shift already sent to timesheets.'))
            r.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_calculation_json': json.dumps(result, indent=2, ensure_ascii=False),
                     'pb_calculation_status': result.get('error') or 'Preview calculated; not yet sent to payroll',
                     'pb_normal_hours': result.get('normal_hours', 0.),
                     'pb_overtime_hours': result.get('overtime_hours', 0.),
                     'pb_deduction_hours': result.get('penalty_hours', 0.),
                     'pb_worked_hours': result.get('worked_hours', 0.)})
        return True

    def action_recalculate(self):
        manager(self.env)
        for r in self:
            r._process_calculation()
        return True

    def _process_calculation(self):
        self.ensure_one()
        if self.state != 'published' or self.pb_policy_id.state != 'active':
            raise UserError(_('Publish the roster and activate its confirmed policy before sending hours to timesheets.'))
        Pair = self.env['pb.clock.pairing']
        guard = Pair._guards(self.employee_id, {self.date}).get(self.date)
        sanctioned = self.env.context.get(PB_ATT_CORRECTION_CTX) is _CORR_TOKEN
        if sanctioned:
            self._assert_unfrozen()
        if guard and not sanctioned:
            return False
        result = self._policy_calculate()
        if result.get('error'):
            # Existing calculated hours must not survive a changed/erroring
            # source unnoticed: approval/payroll verifies the live proof too.
            self.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_calculation_status': result['error']})
            return False
        ci = datetime.fromisoformat(result['first']).astimezone(pytz.utc).replace(tzinfo=None)
        co = datetime.fromisoformat(result['last']).astimezone(pytz.utc).replace(tzinfo=None)
        Att = self.env['hr.attendance']
        overlap = Att.search([('employee_id', '=', self.employee_id.id), ('id', '!=', self.pb_attendance_id.id or 0),
            ('check_in', '<', co), '|', ('check_out', '=', False), ('check_out', '>', ci)], limit=1)
        if overlap:
            raise UserError(_('Existing attendance overlaps this shift. Review it before calculating.'))
        Req = self.env['hr.overtime.request']
        existing = Req.search([('employee_id', '=', self.employee_id.id), ('date', '=', self.date), ('state', '!=', 'refused')])
        if any(o.pb_policy_roster_id != self or o.state != 'draft' for o in existing):
            raise UserError(_('Overtime for this day has already been entered or submitted. Review it before recalculating.'))
        raw = json.dumps(result, sort_keys=True, ensure_ascii=False)
        values = {'check_in': ci, 'check_out': co, 'pb_policy_proof': raw}
        if self.pb_attendance_id:
            row = self.pb_attendance_id
            if any(row[k] != v for k, v in values.items()):
                row.with_context(_attendance_calc=_CALC_TOKEN).write(values)
        else:
            row = Att.with_context(_attendance_calc=_CALC_TOKEN).create(dict(values,
                employee_id=self.employee_id.id, pb_entry_source='device', pb_policy_roster_id=self.id))
        kind = 'weekday' if self.pb_day_kind == 'weekday' else self.pb_day_kind
        existing.filtered(lambda o: o.overtime_type not in (kind, 'night')).unlink()
        existing = existing.exists()
        hours = result['overtime_hours']
        own = existing.filtered(lambda r: r.overtime_type == kind)
        if len(own) > 1:
            raise UserError(_('Multiple generated overtime rows exist. Review this day.'))
        if hours:
            vals = {'planned_hours': hours, 'actual_hours': hours,
                    'reason': 'Calculated from assigned shift and retained first/last punches; approval required.'}
            if own:
                own.with_context(_attendance_calc=_CALC_TOKEN).write(vals)
            else:
                Req.with_context(_attendance_calc=_CALC_TOKEN).create(dict(vals, employee_id=self.employee_id.id,
                    company_id=self.company_id.id, date=self.date, overtime_type=kind, pb_policy_roster_id=self.id))
        elif own:
            own.unlink()
        night = existing.filtered(lambda r: r.overtime_type == 'night')
        night_hours = result['night_hours']
        if len(night) > 1:
            raise UserError(_('Multiple night premium entries exist. Review this day.'))
        if night_hours:
            nv = {'planned_hours': night_hours, 'actual_hours': night_hours,
                  'reason': 'Night premium overlapping calculated worked hours; approval required.'}
            if night:
                night.with_context(_attendance_calc=_CALC_TOKEN).write(nv)
            else:
                Req.with_context(_attendance_calc=_CALC_TOKEN).create(dict(nv, employee_id=self.employee_id.id,
                    company_id=self.company_id.id, date=self.date, overtime_type='night', pb_policy_roster_id=self.id))
        elif night:
            night.unlink()
        self.with_context(_attendance_calc=_CALC_TOKEN).write({
            'pb_category': result['category'],
            'pb_attendance_id': row.id, 'pb_calculation_json': raw,
            'pb_calculation_status': 'In timesheets; attendance and overtime approval required',
            'pb_normal_hours': result['normal_hours'], 'pb_overtime_hours': hours,
            'pb_deduction_hours': result['penalty_hours'], 'pb_worked_hours': result['worked_hours']})
        for p in self.env['pb.clock.punch'].browse(result['source_punch_ids']):
            Pair._apply(p, {'attendance_id': row.id, 'work_day': self.date,
                'state': 'paired' if p.punch_utc in (ci, co) else 'middle', 'note': False})
        return True

    def _assert_unfrozen(self):
        self.ensure_one()
        if 'pb.wf.lock' in self.env and self.env['pb.wf.lock'].sudo()._locked_dates(self.company_id, [self.date]):
            raise UserError(_('Reopen the closed day before applying this correction.'))
        if 'pb.timesheet.freeze' in self.env and self.env['pb.timesheet.freeze'].sudo().frozen_map([(self.employee_id.id, self.date)]):
            raise UserError(_('Return or reopen the weekly timesheet before applying this correction.'))

    @api.model
    def _cron_policy_calculate(self):
        # Only explicit active policies + published rosters opt into this job.
        rows = self.search([('state', '=', 'published'), ('pb_policy_id.state', '=', 'active'),
            ('end_datetime', '<', fields.Datetime.now()),
            ('date', '>=', fields.Date.today()-timedelta(days=35))], order='date,id')
        for row in rows:
            try:
                with self.env.cr.savepoint():
                    row._process_calculation()
            except Exception as exc:
                row.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_calculation_status': str(exc)[:500]})


class Attendance(models.Model):
    _inherit = 'hr.attendance'
    pb_policy_roster_id = fields.Many2one('hr.shift.planning', readonly=True, copy=False, index=True, ondelete='restrict')
    pb_policy_proof = fields.Text(readonly=True, copy=False)
    pb_policy_work_day = fields.Date(related='pb_policy_roster_id.date', store=True, index=True)

    @api.model
    def _pb_date_domain(self, low, high, first_day, last_day):
        return ['|', '&', ('pb_policy_roster_id', '=', False), '&', ('check_in', '>=', low), ('check_in', '<=', high),
                '&', ('pb_policy_work_day', '>=', first_day), ('pb_policy_work_day', '<=', last_day)]

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('pb_policy_roster_id') or v.get('pb_policy_proof') for v in vals_list) and self.env.context.get('_attendance_calc') is not _CALC_TOKEN:
            raise AccessError(_('Calculated attendance is created by the policy workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered('pb_policy_roster_id') and self.env.context.get(PB_ATT_CORRECTION_CTX) is _CORR_TOKEN and self.env.context.get('_attendance_calc') is not _CALC_TOKEN:
            for a in self:
                if not a.pb_policy_roster_id:
                    super(Attendance, a).write(vals)
                    continue
                r = a.pb_policy_roster_id
                r._assert_unfrozen()
                r.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_corrected_in': vals.get('check_in', a.check_in), 'pb_corrected_out': vals.get('check_out', a.check_out)})
                if not r._process_calculation():
                    raise UserError(r.pb_calculation_status or _('Review this shift calculation.'))
                super(Attendance, a).write({'pb_entry_source': 'correction'})
            return True
        if (self.filtered('pb_policy_roster_id') or set(vals) & {'pb_policy_roster_id', 'pb_policy_proof'}) and self.env.context.get('_attendance_calc') is not _CALC_TOKEN:
            if set(vals) & {'check_in', 'check_out', 'employee_id', 'pb_entry_source', 'pb_policy_roster_id', 'pb_policy_proof'}:
                raise UserError(_('Calculated attendance is protected. Review the source roster and recalculate before approval.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered('pb_policy_roster_id'):
            if self.env.context.get(PB_ATT_CORRECTION_CTX) is not _CORR_TOKEN:
                raise UserError(_('Use an approved attendance correction to remove calculated attendance.'))
            for a in self.filtered('pb_policy_roster_id'):
                r = a.pb_policy_roster_id
                r._assert_unfrozen()
                ots = self.env['hr.overtime.request'].search([('pb_policy_roster_id', '=', r.id)])
                if any(o.state not in ('draft', 'refused') for o in ots):
                    raise UserError(_('Return generated overtime to draft before removing this attendance.'))
                ots.unlink()
                r.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_attendance_id': False, 'state': 'cancelled',
                    'pb_calculation_status': 'Removed by approved attendance correction; retained source punches and calculation history.'})
        return super().unlink()

    def _pb_local_day(self, _cache=None):
        self.ensure_one()
        return self.pb_policy_roster_id.date if self.pb_policy_roster_id else super()._pb_local_day(_cache)

    def _pb_policy_values(self):
        self.ensure_one()
        return json.loads(self.pb_policy_proof or '{}') if self.pb_policy_roster_id else None

    def _pb_policy_valid(self, day=None):
        self.ensure_one()
        r = self.pb_policy_roster_id
        if not r:
            return False
        if day and day != r.date:
            return False
        if r.employee_id != self.employee_id or r.state != 'published' or r.pb_policy_id.state not in ('active', 'retired'):
            return False
        live = r._policy_calculate()
        saved = self._pb_policy_values()
        for d in (live, saved):
            d.pop('source_event_ids', None)
            d.pop('source_punch_ids', None)
            d.pop('policy_state', None)
        return not live.get('error') and live == saved


class Overtime(models.Model):
    _inherit = 'hr.overtime.request'
    pb_policy_roster_id = fields.Many2one('hr.shift.planning', readonly=True, copy=False, ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('pb_policy_roster_id') for v in vals_list) and self.env.context.get('_attendance_calc') is not _CALC_TOKEN:
            raise AccessError(_('Policy overtime is created by the calculation workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        if (self.filtered('pb_policy_roster_id') or 'pb_policy_roster_id' in vals) and self.env.context.get('_attendance_calc') is not _CALC_TOKEN:
            if set(vals) & {'employee_id', 'date', 'planned_hours', 'actual_hours', 'overtime_type', 'pb_policy_roster_id'}:
                raise UserError(_('Recalculate the source shift to change generated overtime hours.'))
        return super().write(vals)


class WeekEntry(models.TransientModel):
    _inherit = 'hr.attendance.weekentry'

    @api.model
    def _att_hours(self, a):
        values = a._pb_policy_values()
        return values['normal_hours'] if values else super()._att_hours(a)


class Packet(models.Model):
    _inherit = 'pb.timesheet.packet'

    def _scan_week(self):
        result = super()._scan_week()
        ids = [i for cell in result['days'] for i in cell.get('attendance_ids', [])]
        for att in self.env['hr.attendance'].browse(ids).filtered('pb_policy_roster_id'):
            result['stamp_rows'].append(['policy', att.id, att.pb_policy_proof, att._pb_policy_valid()])
        return result

    def _approval_validate(self):
        for packet in self:
            scan = packet._scan_week()
            ids = [i for cell in scan['days'] for i in cell.get('attendance_ids', [])]
            for att in self.env['hr.attendance'].browse(ids).filtered('pb_policy_roster_id'):
                if not att._pb_policy_valid():
                    raise UserError(_('A shift calculation changed or needs review. Recalculate it before approval.'))
        return super()._approval_validate()


class Pairing(models.AbstractModel):
    _inherit = 'pb.clock.pairing'

    @api.model
    def _pair_employee(self, emp, t_from, summary):
        if emp.pb_attendance_policy_id.state == 'active':
            # Policy calculations read retained source events and assigned
            # rosters. Legacy span pairing must not rewrite their attendance.
            return
        return super()._pair_employee(emp, t_from, summary)
