# -*- coding: utf-8 -*-
"""The week, as one thing that can be signed off.

WHY A DURABLE RECORD AND NOT A FACADE. The catalogue row for "Weekly timesheet"
used to name ``hr.attendance.weekentry``, which is a TransientModel with no
stored fields — a screen's API, not a record. An approval has to be ABOUT
something that still exists next month: the request carries `res_model` /
`res_id` and re-reads the record at apply time, and a vacuumed transient row is
a request pointing at nothing. So this module ships `pb.timesheet.packet`, one
row per person per week, and repoints the catalogue at it.

WHAT THE PACKET IS. A snapshot of seven days of punches and overtime, plus the
totals they add up to, plus a stamp (`source_hash`) of the hours it was built
from. Nothing here decides anything about overtime: ceilings, the bonus-hours
split and the young-worker rules already decided, and the packet records what
they decided so ONE sign-off can cover the week instead of one per entry.

THE STAMP DELIBERATELY LEAVES OUT STATE (ledger AM32's rule, applied here).
`source_hash` covers which punches, when they start and end, and how many hours
of overtime were entered. It does NOT cover the overtime workflow state or the
approved/bonus split — because approving the packet is itself what submits and
approves that overtime, and a stamp that included the state would differ from
itself in the middle of its own apply.
"""

import hashlib
import json
import logging
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.pb_hr_workforce.models.attendance_weekentry import OT_TYPES

_logger = logging.getLogger(__name__)

#: The states a packet may be in, and the words for them. ONE map, read by the
#: grid chip, the list view and the adapter, so no screen can name a stage the
#: model does not have.
PACKET_STATES = [
    ('draft', 'Not sent in'),
    ('pending', 'Waiting for approval'),
    ('approved', 'Approved'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
]
PACKET_STATE_NAME = dict(PACKET_STATES)

#: The seal. Same shape and same reason as the pay run's: a state machine that
#: `write()` does not enforce is decoration, and a raw `call_kw` write to
#: `approved` would put unapproved hours into payroll.
_TS_CHAIN_KEY = 'pb_timesheet_chain_write'
_TS_CHAIN_TOKEN = object()
_TS_SEALED = {'state', 'approved_hash', 'attempt'}

#: When nothing on this database says otherwise, inputs close on the 15th.
DEFAULT_CUTOFF_DAY = 15


class PbTimesheetPacket(models.Model):
    _name = 'pb.timesheet.packet'
    _inherit = ['biz.approval.adapter.mixin']
    _description = 'Weekly Timesheet Packet'
    _order = 'week_start desc, id desc'
    _rec_name = 'name'

    #: The row in the approval catalogue this model is approved under.
    _approval_process_key = 'timesheet'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade')
    department_id = fields.Many2one(
        'hr.department', related='employee_id.department_id', store=True,
        readonly=True)
    week_start = fields.Date(string='Week beginning', required=True, index=True)
    week_end = fields.Date(string='Week ending', compute='_compute_week_end',
                           store=True)
    #: How many times this week has been sent in. A packet is durable — sending
    #: it back and sending it in again is the SAME week, not a second one.
    attempt = fields.Integer(default=0, readonly=True, copy=False)

    # ------------------------------------------------------------ the snapshot
    days_json = fields.Text(
        string='Day by day (JSON)', readonly=True, copy=False,
        help="Seven days: the hours worked, where each punch came from, and "
             "the overtime recorded on that day.")
    reg_hours = fields.Float(string='Worked hours', readonly=True)
    ot_hours = fields.Float(string='Overtime hours', readonly=True)
    ot_weekday_hours = fields.Float(string='Weekday overtime', readonly=True)
    ot_weekend_hours = fields.Float(string='Weekend overtime', readonly=True)
    ot_holiday_hours = fields.Float(string='Public-holiday overtime',
                                    readonly=True)
    ot_night_hours = fields.Float(string='Night overtime', readonly=True)
    bonus_hours = fields.Float(string='Bonus hours', readonly=True)
    total_hours = fields.Float(string='Total hours', readonly=True)
    days_with_hours = fields.Integer(string='Days worked', readonly=True)
    scheduled_hours = fields.Float(string='Hours on the schedule', readonly=True)
    variance_pct = fields.Float(string='Against the schedule (%)', readonly=True)

    source_hash = fields.Char(string='Hours stamp', readonly=True, copy=False)
    approved_hash = fields.Char(string='Approved stamp', readonly=True,
                                copy=False)
    state = fields.Selection(PACKET_STATES, default='draft', required=True,
                             index=True, readonly=True, copy=False)
    packet_note = fields.Char(string='Note', readonly=True, copy=False)
    submitted_uid = fields.Many2one('res.users', string='Sent in by',
                                    readonly=True, copy=False)
    submitted_at = fields.Datetime(string='Sent in on', readonly=True,
                                   copy=False)
    late_submission = fields.Boolean(string='Sent in after the cut-off',
                                     readonly=True, copy=False)
    ot_apply_note = fields.Char(string='Overtime carried out', readonly=True,
                                copy=False)

    _week_uniq = models.Constraint(
        'unique(employee_id, week_start)',
        'This person already has a timesheet for that week.')

    # ==================================================================
    # words
    # ==================================================================
    @api.depends('employee_id', 'week_start')
    def _compute_name(self):
        for packet in self:
            week = packet.week_start
            packet.name = _(
                "%(who)s · week of %(when)s",
                who=packet.employee_id.name or '',
                when=week.strftime('%d %b %Y') if week else '')

    @api.depends('week_start')
    def _compute_week_end(self):
        for packet in self:
            packet.week_end = (packet.week_start + timedelta(days=6)
                               if packet.week_start else False)

    # ==================================================================
    # the seal
    # ==================================================================
    def _ts_chain(self):
        return self.with_context(**{_TS_CHAIN_KEY: _TS_CHAIN_TOKEN})

    def _ts_seal_ok(self):
        return (self.env.context.get(_TS_CHAIN_KEY) is _TS_CHAIN_TOKEN
                or self.env.su or self.env.user._is_admin())

    @api.model_create_multi
    def create(self, vals_list):
        if not self._ts_seal_ok():
            for vals in vals_list:
                for key in _TS_SEALED.intersection(vals):
                    vals.pop(key)
        return super().create(vals_list)

    def write(self, vals):
        forged = _TS_SEALED.intersection(vals or {})
        if forged and not self._ts_seal_ok():
            raise AccessError(_(
                "A week's approval status can only change by sending it in, or "
                "by a decision on it: %s.", ', '.join(sorted(forged))))
        return super().write(vals)

    # ==================================================================
    # building the packet
    # ==================================================================
    @api.model
    def _monday(self, day):
        day = fields.Date.to_date(day) or fields.Date.context_today(self)
        return day - timedelta(days=day.weekday())

    @api.model
    def packet_for(self, employee, week_start, create=True):
        """The packet for one person and one week, refreshed from the source.

        Never two: a week that was sent back and sent in again is the same
        week. `attempt` counts the submissions.
        """
        employee = employee if isinstance(employee, models.BaseModel) \
            else self.env['hr.employee'].browse(int(employee))
        week_start = self._monday(week_start)
        packet = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('week_start', '=', week_start)], limit=1)
        if not packet:
            if not create:
                return self.browse()
            packet = self.sudo().create({
                'employee_id': employee.id,
                'week_start': week_start,
                'company_id': (employee.company_id or self.env.company).id,
            })
        packet._refresh_snapshot()
        return packet

    def _week_bounds(self):
        """[start, end] as datetimes, in the grid's own convention.

        The weekly grid keys a punch by `check_in.date()` — the stored (UTC)
        day — and the packet has to agree with the grid cell for cell, or a
        person would be asked to approve a week that does not look like the one
        they are reading. `pb.wf.lock` keys by the employee-LOCAL day instead;
        the two answers differ only for punches within the timezone offset of
        midnight, and the lock keeps its own convention because a closed day is
        a statement about the factory's calendar rather than about this grid.
        """
        self.ensure_one()
        start = self.week_start
        end = start + timedelta(days=6)
        return (datetime.combine(start, time.min),
                datetime.combine(end, time.max))

    def _refresh_snapshot(self):
        """Re-read the seven days. Refused once the week is frozen."""
        for packet in self:
            if packet.state in ('pending', 'approved'):
                continue
            packet._write_snapshot()
        return True

    def _scan_week(self):
        """Read the seven days. A pure read: it writes nothing.

        Separate from `_write_snapshot` because the STAMP has to be taken from
        the source every time it is asked for. The engine re-reads
        `_approval_context()` at apply time and compares its `source_revision`
        with the one frozen at submission; if the stamp were read back off the
        stored snapshot it would always equal itself, and the whole "this
        changed after it was sent in" rail would be decoration.
        """
        self.ensure_one()
        employee = self.employee_id
        start, end = self._week_bounds()
        Att = self.env['hr.attendance'].sudo()
        Req = self.env['hr.overtime.request'].sudo()
        attendances = Att.search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start), ('check_in', '<=', end),
        ], order='check_in')
        requests = Req.search([
            ('employee_id', '=', employee.id),
            ('date', '>=', self.week_start), ('date', '<=', self.week_end
                                              or self.week_start),
        ])
        Grid = self.env['hr.attendance.weekentry']

        by_day = {}
        for att in attendances:
            by_day.setdefault(att.check_in.date(), Att.browse())
            by_day[att.check_in.date()] |= att
        req_by_day = {}
        for req in requests:
            req_by_day.setdefault(req.date, {})[req.overtime_type] = req

        days, stamp_rows = [], []
        totals = {t: 0.0 for t in OT_TYPES}
        reg_total = bonus_total = 0.0
        worked_days = 0
        for index in range(7):
            day = self.week_start + timedelta(days=index)
            cell_atts = by_day.get(day, Att.browse())
            reg = round(sum(Grid._att_hours(a) for a in cell_atts), 2)
            reg_total += reg
            if reg:
                worked_days += 1
            overtime = {}
            for ot_type, req in (req_by_day.get(day) or {}).items():
                if req.state == 'refused':
                    continue
                entered = round(req.actual_hours or req.planned_hours or 0.0, 2)
                overtime[ot_type] = {
                    'id': req.id,
                    'hours': entered,
                    'approved': round(req.approved_hours or 0.0, 2),
                    'bonus': round(req.bonus_hours or 0.0, 2),
                    'state': req.state,
                }
                if ot_type in totals:
                    totals[ot_type] += entered
                bonus_total += round(req.bonus_hours or 0.0, 2)
                stamp_rows.append(['ot', req.id, ot_type, entered])
            days.append({
                'date': day.isoformat(),
                'reg': reg,
                'attendance_ids': cell_atts.ids,
                'sources': sorted({a.pb_entry_source or 'device'
                                   for a in cell_atts}),
                'ot': overtime,
            })
            for att in cell_atts:
                stamp_rows.append([
                    'att', att.id,
                    fields.Datetime.to_string(att.check_in) or '',
                    fields.Datetime.to_string(att.check_out) or ''])

        return {
            'days': days,
            'stamp_rows': stamp_rows,
            'totals': totals,
            'reg_hours': round(reg_total, 2),
            'bonus_hours': round(bonus_total, 2),
            'days_with_hours': worked_days,
        }

    def _live_stamp(self):
        """The stamp of the hours as they are RIGHT NOW."""
        self.ensure_one()
        return self._stamp_of(self._scan_week()['stamp_rows'])

    def _write_snapshot(self):
        self.ensure_one()
        scan = self._scan_week()
        days = scan['days']
        totals = scan['totals']
        reg_total = scan['reg_hours']
        bonus_total = scan['bonus_hours']
        worked_days = scan['days_with_hours']
        ot_total = round(sum(totals.values()), 2)
        scheduled = self._scheduled_hours()
        variance = 0.0
        if scheduled:
            variance = round(
                (reg_total - scheduled) / scheduled * 100.0, 2)
        self.sudo().with_context(**{_TS_CHAIN_KEY: _TS_CHAIN_TOKEN}).write({
            'days_json': json.dumps(days),
            'reg_hours': round(reg_total, 2),
            'ot_weekday_hours': round(totals.get('weekday', 0.0), 2),
            'ot_weekend_hours': round(totals.get('weekend', 0.0), 2),
            'ot_holiday_hours': round(totals.get('holiday', 0.0), 2),
            'ot_night_hours': round(totals.get('night', 0.0), 2),
            'ot_hours': ot_total,
            'bonus_hours': round(bonus_total, 2),
            'total_hours': round(reg_total + ot_total, 2),
            'days_with_hours': worked_days,
            'scheduled_hours': scheduled,
            'variance_pct': variance,
            'source_hash': self._stamp_of(scan['stamp_rows']),
        })
        return True

    @api.model
    def _stamp_of(self, rows):
        raw = json.dumps(sorted(rows, key=lambda r: (str(r[0]), str(r[1]))),
                         sort_keys=True, default=str)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]

    def _scheduled_hours(self):
        """What this person's working schedule says the week should hold."""
        self.ensure_one()
        calendar = self.employee_id.sudo().resource_calendar_id \
            or self.company_id.resource_calendar_id
        if not calendar:
            return 0.0
        start, end = self._week_bounds()
        try:
            import pytz
            data = calendar.get_work_duration_data(
                pytz.utc.localize(start), pytz.utc.localize(end),
                compute_leaves=False)
            return round(float(data.get('hours') or 0.0), 2)
        except Exception:       # noqa: BLE001 — a schedule must never stop this
            return round(float(getattr(calendar, 'hours_per_week', 0.0) or 0.0),
                         2)

    def days(self):
        """The snapshot, as a list. Empty rather than an exception if unbuilt."""
        self.ensure_one()
        try:
            rows = json.loads(self.days_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []

    # ==================================================================
    # where this week sits in the business
    # ==================================================================
    def _division(self):
        self.ensure_one()
        Division = self.env.get('pb.division')
        department = self.employee_id.sudo().department_id
        if Division is None or not department:
            return self.env['pb.division'] if 'pb.division' in self.env \
                else self.env['res.company'].browse()
        try:
            return Division.sudo().division_for(department, self.week_start)
        except Exception:       # noqa: BLE001 — never stop a submission
            _logger.warning('pb_timesheet_approval: division lookup failed '
                            'on packet %s', self.id)
            return Division.browse()

    def _scope_keys(self, division):
        keys = []
        if division:
            keys.append('division:%s' % division.id)
        keys.append('')
        return keys

    @api.model
    def _cutoff_day(self, company):
        """The day of the month inputs close on.

        Read off a finished setup for this company when there is one, because
        that is where the business wrote it down; day 15 otherwise.
        """
        Blueprint = self.env.get('pb.blueprint')
        if Blueprint is not None:
            try:
                rows = Blueprint.sudo().search(
                    [('company_id', '=', company.id)], order='id desc',
                    limit=20)
                for row in rows:
                    day = (row.calendar() or {}).get('cutoff_day')
                    if day:
                        return max(min(int(day), 28), 1)
            except Exception:   # noqa: BLE001 — a preference must never raise
                _logger.debug('pb_timesheet_approval: no setup calendar')
        return DEFAULT_CUTOFF_DAY

    def _is_late(self, on_date=None):
        """Was this week sent in after the month's cut-off?"""
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        cutoff = self._cutoff_day(self.company_id or self.env.company)
        end = self.week_end or self.week_start
        if not end:
            return False
        # The cut-off that matters is the one for the month the week ENDS in.
        # A week sent in during its own month is never late; a week sent in
        # later is late once that month's cut-off has passed.
        if on_date.year == end.year and on_date.month == end.month:
            return on_date.day > cutoff
        return (on_date.year, on_date.month) > (end.year, end.month)

    # ==================================================================
    # Adapter — what an approval of a week is about
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.state in ('pending', 'approved'):
            raise UserError(_(
                "“%(name)s” has already been sent in (status: %(state)s).",
                name=self.name or '',
                state=_(PACKET_STATE_NAME.get(self.state, self.state))))
        if not self.employee_id.active:
            raise UserError(_(
                "%s is no longer an employee, so this week cannot be sent in.",
                self.employee_id.name or ''))
        self._refresh_snapshot()
        if not (self.reg_hours or self.ot_hours):
            raise UserError(_(
                "There are no hours recorded for %(who)s in the week of "
                "%(when)s, so there is nothing to approve.",
                who=self.employee_id.name or '',
                when=self.week_start.strftime('%d %b')))
        locked = self._locked_days()
        if locked:
            raise UserError(_(
                "This week has day(s) that are already closed and locked, so "
                "it cannot be sent in: %s.",
                ', '.join(d.strftime('%d %b') for d in sorted(locked))))
        return True

    def _locked_days(self):
        """The days of this week the workforce close has already locked."""
        self.ensure_one()
        Lock = self.env.get('pb.wf.lock')
        if Lock is None:
            return set()
        days = [self.week_start + timedelta(days=i) for i in range(7)]
        try:
            return Lock.sudo()._locked_dates(self.company_id, days)
        except Exception:       # noqa: BLE001
            return set()

    def _approval_context(self):
        """The frozen truth about this week at the moment it is sent in."""
        self.ensure_one()
        company = self.company_id or self.env.company
        division = self._division()
        # WHERE THIS WEEK BELONGS IS NOT A PERMISSION QUESTION (ledger AM40).
        # Working out which route applies means reading the employee's
        # department and the division it sits in; an attendance officer who may
        # send a week in has no reason to be allowed to read the group
        # structure. Nothing is granted: every seat and every decision still
        # runs as the real person.
        this = self.sudo()
        hours_unit = _('h')
        facts = {
            'total_hours': {'value': this.total_hours, 'unit': hours_unit},
            'reg_hours': {'value': this.reg_hours, 'unit': hours_unit},
            'ot_hours': {'value': this.ot_hours, 'unit': hours_unit},
            'days_with_hours': {'value': this.days_with_hours, 'unit': ''},
            'has_overtime': {'value': bool(this.ot_hours), 'unit': ''},
            'variance_vs_schedule_pct': {'value': this.variance_pct,
                                         'unit': ''},
            'late_submission': {'value': self._is_late(), 'unit': ''},
        }
        makers = set()
        for day in this.days():
            attendances = self.env['hr.attendance'].sudo().browse(
                day.get('attendance_ids') or []).exists()
            makers |= set(attendances.mapped('create_uid').ids)
            for row in (day.get('ot') or {}).values():
                request = self.env['hr.overtime.request'].sudo().browse(
                    row.get('id') or 0).exists()
                makers |= set(request.mapped('create_uid').ids)
        makers.add(self.env.uid)
        subject = this.employee_id.user_id
        return {
            'company_id': company.id,
            'title': self.name or _('Weekly timesheet'),
            'scope_keys': self._scope_keys(division),
            'scope_label': (division.name if division
                            else (this.department_id.name or company.name)),
            'kind_key': 'week',
            'facts': facts,
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            'maker_uids': sorted(u for u in makers if u),
            'submitter_uid': self.env.uid,
            'subject_uids': subject.ids,
            # Taken from the SOURCE every time, never read back off the stored
            # snapshot — see `_scan_week`.
            'source_revision': this._live_stamp(),
            'evidence': [],
        }

    def _approval_manager_uids(self):
        """Their manager — read off the employee, not off the subject's account.

        The mixin's default answer walks `subject_uids`, and most people who
        clock in have no login at all; on this model that would have made
        "their manager" resolve to nobody for exactly the workforce this is
        built for.
        """
        self.ensure_one()
        manager = self.sudo().employee_id.parent_id.user_id
        return manager.ids

    def _approval_skip_manager_uids(self):
        self.ensure_one()
        return self.sudo().employee_id.parent_id.parent_id.user_id.ids

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'total_hours': {'type': 'decimal', 'label': _('Total hours'),
                                'unit': 'h'},
                'reg_hours': {'type': 'decimal', 'label': _('Worked hours'),
                              'unit': 'h'},
                'ot_hours': {'type': 'decimal', 'label': _('Overtime hours'),
                             'unit': 'h'},
                'days_with_hours': {'type': 'int', 'label': _('Days worked')},
                'has_overtime': {'type': 'bool',
                                 'label': _('Contains overtime')},
                'variance_vs_schedule_pct': {
                    'type': 'percent',
                    'label': _('Difference from the working schedule')},
                'late_submission': {'type': 'bool',
                                    'label': _('Sent in after the cut-off')},
            },
            'kinds': [{'key': 'week', 'label': _('A week of hours')}],
            'evidence': [
                {'key': 'timesheet_signed', 'label': _('Signed timesheet')},
                {'key': 'overtime_note', 'label': _('Note on the overtime')},
            ],
            'scope_levels': [_('Part of the business')],
            # A week is about ONE person, so "their manager" has an answer.
            'manager_mode': True,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        """Every part of the business hours are recorded in."""
        rows = []
        Division = self.env.get('pb.division')
        if Division is not None:
            divisions = Division.sudo().search(
                [('company_id', '=', company.id)], limit=200, order='name') \
                if 'company_id' in Division._fields \
                else Division.sudo().search([], limit=200, order='name')
            for division in divisions:
                rows.append({
                    'scope_key': 'division:%s' % division.id,
                    'scope_keys': ['division:%s' % division.id, ''],
                    'label': division.name or '',
                    'headcount': 0,
                    'kind_key': 'week',
                    'facts': {},
                })
        rows.append({'scope_key': '', 'scope_keys': [''],
                     'label': company.name, 'headcount': 0,
                     'kind_key': 'week', 'facts': {}})
        return rows

    # --------------------------------------------------------- the transitions
    def _approval_freeze(self, request):
        """Nobody edits this week while somebody is deciding about it."""
        self.ensure_one()
        self._ts_chain().sudo().write({
            'state': 'pending',
            'attempt': (self.attempt or 0) + 1,
            'submitted_uid': self.env.uid,
            'submitted_at': fields.Datetime.now(),
            'late_submission': self._is_late(),
            'packet_note': False,
        })
        return True

    def _approval_apply(self, request):
        """Carry out what the approval authorised.

        Two things: the week is marked approved with the stamp it was approved
        AT, and the overtime inside it is brought into line with that decision.
        Idempotent — an already approved packet is left alone.
        """
        self.ensure_one()
        if self.state == 'approved':
            return True
        note = self._apply_overtime()
        self._ts_chain().sudo().write({
            'state': 'approved',
            'approved_hash': self.source_hash or '',
            'ot_apply_note': note or False,
        })
        return True

    def _apply_overtime(self):
        """Send in and approve the week's own overtime, once the week is signed.

        WHY THIS IS NOT ONE CALL. `hr.overtime.request.action_approve` asks
        whether the acting user is an attendance decider or the person's line
        manager — a true question for somebody pressing Approve on an overtime
        form, and the wrong one here: the decision has already been taken, by
        whoever the published route named, and that may be an HR lead who is
        neither. The approval is therefore carried out for the engine
        (`sudo()`), and each request is approved inside its OWN savepoint so a
        refusal that is a RULE — a young worker's illegal overtime, a ceiling
        constraint — stops that entry and not the whole week.
        """
        self.ensure_one()
        # The sentinel rides along: this week is frozen by this module's own
        # guard, and the guard must not stop the very apply that is unfreezing
        # it (`week_freeze`).
        Req = self.env['hr.overtime.request'].sudo().with_context(
            **{_TS_CHAIN_KEY: _TS_CHAIN_TOKEN})
        ids = []
        for day in self.days():
            for row in (day.get('ot') or {}).values():
                if row.get('id'):
                    ids.append(row['id'])
        requests = Req.browse(sorted(set(ids))).exists()
        drafts = requests.filtered(lambda r: r.state == 'draft')
        if drafts:
            try:
                with self.env.cr.savepoint():
                    drafts.action_submit()
            except Exception as exc:    # noqa: BLE001
                _logger.warning('pb_timesheet_approval: overtime could not be '
                                'sent in for packet %s: %s', self.id, exc)
        todo = requests.filtered(lambda r: r.state == 'submitted')
        done, failed = 0, 0
        for request in todo:
            try:
                with self.env.cr.savepoint():
                    request.action_approve()
                done += 1
            except Exception as exc:    # noqa: BLE001 — one entry, not the week
                failed += 1
                _logger.info('pb_timesheet_approval: overtime %s on packet %s '
                             'was not approved: %s', request.id, self.id, exc)
        if failed:
            return _("%(ok)s overtime entr(ies) approved with the week; "
                     "%(bad)s could not be and still need a decision of their "
                     "own.", ok=done, bad=failed)
        if done:
            return _("%s overtime entr(ies) approved with the week.", done)
        return ''

    def _approval_return(self, request, reason):
        """Sent back: the week thaws, with the reason on it."""
        self.ensure_one()
        self._ts_chain().sudo().write({
            'state': 'returned',
            'packet_note': (reason or '')[:512] or False,
        })
        return True

    # ==================================================================
    # doors
    # ==================================================================
    def action_submit_week(self):
        """Send this week in for approval."""
        self.ensure_one()
        return self.env['biz.approval.engine'].submit(self)

    def action_open_request(self):
        """Open this week's request in the one inbox."""
        self.ensure_one()
        request = self.approval_request_id
        if not request:
            raise UserError(_("This week has not been sent in yet."))
        return {
            'type': 'ir.actions.client',
            'tag': 'pb_approval_inbox',
            'name': _('Approvals'),
            'params': {'request_id': request.id},
        }

    # ==================================================================
    # what the inbox shows
    # ==================================================================
    def _approval_card_count(self, request):
        """The one number that says how big this request is."""
        self.ensure_one()
        facts = request.facts or {}

        def _hours(key):
            raw = facts.get(key)
            value = raw.get('value') if isinstance(raw, dict) else raw
            try:
                return round(float(value or 0.0), 1)
            except (TypeError, ValueError):
                return 0.0

        total, overtime = _hours('total_hours'), _hours('ot_hours')
        if overtime:
            return _("%(total)s h incl. %(ot)s h overtime",
                     total=total, ot=overtime)
        return _("%s h", total)

    def _approval_detail(self, request):
        """The seven days, as a small table the drawer can draw for any process.

        A generic table rather than a timesheet-shaped payload: the drawer
        knows how to draw columns and rows, and learns nothing about weeks.
        """
        self.ensure_one()
        rows = []
        for day in self.days():
            date = fields.Date.to_date(day.get('date'))
            overtime = day.get('ot') or {}
            ot_hours = sum(float(row.get('hours') or 0.0)
                           for row in overtime.values())
            rows.append({
                'head': date.strftime('%a') if date else '',
                'sub': date.strftime('%d %b') if date else '',
                'cells': [
                    '%s' % round(float(day.get('reg') or 0.0), 1),
                    ('%s' % round(ot_hours, 1)) if ot_hours else '',
                ],
                'tone': 'on' if (day.get('reg') or ot_hours) else 'off',
            })
        chips = []
        for key, label in (('ot_weekday_hours', _('Weekday overtime')),
                           ('ot_weekend_hours', _('Weekend overtime')),
                           ('ot_holiday_hours', _('Public-holiday overtime')),
                           ('ot_night_hours', _('Night overtime')),
                           ('bonus_hours', _('Bonus hours'))):
            value = round(float(self[key] or 0.0), 1)
            if value:
                chips.append({'label': label, 'value': _("%s h", value)})
        return {
            'title': _('Day by day'),
            'columns': [_('Worked'), _('Overtime')],
            'rows': rows,
            'chips': chips,
            'note': (self.ot_apply_note or ''),
        }

    # ==================================================================
    # the payroll side
    # ==================================================================
    @api.model
    def approved_in_period(self, employee_id, date_from, date_to):
        """Every APPROVED packet whose week starts inside the pay period.

        A week is the unit. One that straddles the end of the period belongs to
        the period its Monday is in, which is the same rule the weekly grid and
        the close board already use — and the only rule under which every hour
        is counted exactly once across two consecutive runs.
        """
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        if not (employee_id and date_from and date_to):
            return self.browse()
        return self.sudo().search([
            ('employee_id', '=', int(employee_id)),
            ('state', '=', 'approved'),
            ('week_start', '>=', date_from),
            ('week_start', '<=', date_to),
        ], order='week_start')

    @api.model
    def weeks_missing_approval(self, employee_ids, date_from, date_to,
                               limit=40):
        """People with a week in this period that nobody has approved.

        Only weeks that HAVE hours count: a person who did not work a week is
        not a problem to report, and a payroll advisory that lists everybody
        every month is an advisory people stop reading.
        """
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        employee_ids = [int(e) for e in (employee_ids or []) if e]
        if not (employee_ids and date_from and date_to):
            return []
        weeks = []
        cursor = self._monday(date_from)
        if cursor < date_from:
            cursor += timedelta(days=7)
        while cursor <= date_to:
            weeks.append(cursor)
            cursor += timedelta(days=7)
        if not weeks:
            return []
        rows = self.sudo().search([
            ('employee_id', 'in', employee_ids),
            ('week_start', 'in', weeks),
        ])
        approved = {(p.employee_id.id, p.week_start) for p in rows
                    if p.state == 'approved'}
        state_of = {(p.employee_id.id, p.week_start): p.state for p in rows}
        # Which (person, week) actually has hours — one query over the punches
        # rather than a packet per person per week that nobody ever built.
        self.env.cr.execute("""
            SELECT employee_id, MIN(check_in)::date, COUNT(*)
            FROM hr_attendance
            WHERE employee_id IN %s AND check_in >= %s AND check_in <= %s
            GROUP BY employee_id, check_in::date
        """, (tuple(employee_ids),
              datetime.combine(weeks[0], time.min),
              datetime.combine(weeks[-1] + timedelta(days=6), time.max)))
        worked = set()
        for employee_id, day, _count in self.env.cr.fetchall():
            worked.add((employee_id, self._monday(day)))
        out = []
        for key in sorted(worked):
            if key in approved:
                continue
            employee = self.env['hr.employee'].sudo().browse(key[0])
            out.append({
                'employee_id': key[0],
                'employee': employee.name or '',
                'week_start': key[1].isoformat(),
                'week_label': key[1].strftime('%d %b'),
                'state': state_of.get(key, 'none'),
            })
            if len(out) >= limit:
                break
        return out
