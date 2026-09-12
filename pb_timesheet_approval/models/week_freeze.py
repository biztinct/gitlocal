# -*- coding: utf-8 -*-
"""A week that is with somebody for approval does not move under them.

GUARDED AT THE ORM, not at the six screens that write hours. `hr.attendance`
already has five writers (the weekly grid, the import wizard, an approved
correction, the driver app's live punch and a plain officer edit) and
`hr.overtime.request` has its own; guarding each of them separately is six
places to forget. This is one.

WHAT THAW MEANS. `draft`, `returned` and "no packet at all" are editable.
`pending` and `approved` are not — and the message says whose desk the week is
on, because "refused" without a name is a dead end.

THE SENTINEL. Approving a week is itself what submits and approves that week's
overtime, so the packet's own apply path has to be able to write to rows inside
a frozen week. It carries a module-level `object()` identity, which a
client-supplied context value can never equal. `sudo()` deliberately does NOT
open this guard: the correction workflow's apply runs sudo'd, and it must still
be stopped by a week that has been signed off (the same posture `pb_close`
takes with a locked day).
"""

import logging
from datetime import timedelta

from odoo import _, api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_FROZEN_STATES = ('pending', 'approved')


class PbTimesheetFreeze(models.AbstractModel):
    """The one answer to "is this day frozen?", asked by both guards."""
    _name = 'pb.timesheet.freeze'
    _description = 'Weekly timesheet freeze guard'

    @api.model
    def frozen_map(self, pairs):
        """{(employee_id, date): packet} for every pair inside a frozen week.

        ONE query whatever the batch size: an import of ten thousand punches
        must not ask the packet table ten thousand times.
        """
        pairs = [(int(e), d) for (e, d) in (pairs or []) if e and d]
        if not pairs:
            return {}
        Packet = self.env['pb.timesheet.packet'].sudo()
        weeks = {d - timedelta(days=d.weekday()) for (_e, d) in pairs}
        employees = {e for (e, _d) in pairs}
        rows = Packet.search([
            ('employee_id', 'in', list(employees)),
            ('week_start', 'in', list(weeks)),
            ('state', 'in', list(_FROZEN_STATES)),
        ])
        by_key = {(row.employee_id.id, row.week_start): row for row in rows}
        out = {}
        for employee_id, day in pairs:
            packet = by_key.get((employee_id, day - timedelta(days=day.weekday())))
            if packet:
                out[(employee_id, day)] = packet
        return out

    @api.model
    def check_open(self, pairs, what):
        """Raise when any (employee, day) is inside a week under approval."""
        frozen = self.frozen_map(pairs)
        if not frozen:
            return True
        packet = list(frozen.values())[0]
        raise ValidationError(packet._frozen_message(what))


class PbTimesheetPacketMessage(models.Model):
    _inherit = 'pb.timesheet.packet'

    def _frozen_message(self, what):
        """Why this week cannot be touched, and what to do instead."""
        self.ensure_one()
        week = self.week_start.strftime('%d %b') if self.week_start else ''
        if self.state == 'approved':
            return _(
                "%(what)s is not possible: the week of %(week)s for %(who)s "
                "has been approved. Ask for it to be sent back if it has to "
                "change.", what=what, week=week, who=self.employee_id.name or '')
        with_whom = self._waiting_for() or _('the approver')
        return _(
            "%(what)s is not possible: the week of %(week)s for %(who)s is "
            "with %(whom)s for approval. Send it back to change it.",
            what=what, week=week, who=self.employee_id.name or '',
            whom=with_whom)

    def _waiting_for(self):
        """Whose desk this week is on right now, in names."""
        self.ensure_one()
        request = self.approval_request_id
        if not request:
            return ''
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)[:1]
        if not step:
            return ''
        names = sorted({seat.acting_user_id.name or ''
                        for seat in step.seat_ids
                        if seat.status == 'open'})
        return ', '.join(n for n in names if n)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    def _pb_week_pairs(self, extra_check_in=None):
        pairs = []
        for attendance in self:
            employee = attendance.employee_id
            if not employee:
                continue
            if attendance.check_in:
                pairs.append((employee.id, attendance.check_in.date()))
            if extra_check_in:
                pairs.append((employee.id, extra_check_in.date()))
        return pairs

    @api.model_create_multi
    def create(self, vals_list):
        if not self._pb_freeze_bypass():
            pairs = []
            for vals in vals_list:
                employee_id = vals.get('employee_id')
                check_in = self._pb_as_datetime(vals.get('check_in'))
                if employee_id and check_in:
                    pairs.append((int(employee_id), check_in.date()))
            self.env['pb.timesheet.freeze'].check_open(pairs, _("Adding a punch"))
        return super().create(vals_list)

    def write(self, vals):
        watched = {'check_in', 'check_out', 'employee_id'}
        if watched.intersection(vals or {}) and not self._pb_freeze_bypass():
            new_check_in = (self._pb_as_datetime(vals['check_in'])
                            if vals.get('check_in') else None)
            self.env['pb.timesheet.freeze'].check_open(
                self._pb_week_pairs(extra_check_in=new_check_in),
                _("Editing this punch"))
        return super().write(vals)

    def unlink(self):
        if not self._pb_freeze_bypass():
            self.env['pb.timesheet.freeze'].check_open(
                self._pb_week_pairs(), _("Deleting this punch"))
        return super().unlink()

    def _pb_freeze_bypass(self):
        from .timesheet_packet import _TS_CHAIN_KEY, _TS_CHAIN_TOKEN
        return self.env.context.get(_TS_CHAIN_KEY) is _TS_CHAIN_TOKEN


class HrOvertimeRequest(models.Model):
    _inherit = 'hr.overtime.request'

    def _pb_week_pairs(self, extra=None):
        pairs = [(r.employee_id.id, r.date) for r in self
                 if r.employee_id and r.date]
        if extra:
            pairs += extra
        return pairs

    @api.model_create_multi
    def create(self, vals_list):
        if not self._pb_freeze_bypass():
            from odoo import fields as _fields
            pairs = []
            for vals in vals_list:
                employee_id = vals.get('employee_id')
                day = _fields.Date.to_date(vals.get('date'))
                if employee_id and day:
                    pairs.append((int(employee_id), day))
            self.env['pb.timesheet.freeze'].check_open(
                pairs, _("Adding overtime"))
        return super().create(vals_list)

    def write(self, vals):
        if not self._pb_freeze_bypass():
            from odoo import fields as _fields
            extra = []
            if vals and vals.get('date'):
                day = _fields.Date.to_date(vals['date'])
                extra = [(r.employee_id.id, day) for r in self
                         if r.employee_id and day]
            self.env['pb.timesheet.freeze'].check_open(
                self._pb_week_pairs(extra), _("Changing overtime"))
        return super().write(vals)

    def unlink(self):
        if not self._pb_freeze_bypass():
            self.env['pb.timesheet.freeze'].check_open(
                self._pb_week_pairs(), _("Deleting overtime"))
        return super().unlink()

    def _pb_freeze_bypass(self):
        from .timesheet_packet import _TS_CHAIN_KEY, _TS_CHAIN_TOKEN
        return self.env.context.get(_TS_CHAIN_KEY) is _TS_CHAIN_TOKEN
