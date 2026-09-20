# -*- coding: utf-8 -*-
"""The weekly grid learns to send a week in.

`submit_week` used to mean one thing — bulk-submit the week's draft overtime.
It still does that, and now it also builds and submits the WEEK, which is the
thing somebody is actually being asked to sign off. The overtime submission is
kept rather than replaced: an entry that never reaches a packet (a person whose
week has no punches at all) must still be able to travel its own road.

Every method here gates itself with the grid's own `_require_officer`, and then
does the work through the packet model, which re-checks everything again. The
packet reads and writes under `sudo()` for the same reason the grid already
does: the officer record rules on attendance and overtime are own-records-only,
and a grid that showed blank cells for everybody else would be a grid nobody
could use.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Never build more than this many packets in one press. The grid itself caps
#: at 200 employees; this is the same promise stated where the writes happen.
_MAX_PACKETS = 200


class AttendanceWeekEntry(models.TransientModel):
    _inherit = 'hr.attendance.weekentry'

    # ------------------------------------------------------------- read side
    @api.model
    def week_packets(self, week_start_str=False, department_id=False,
                     search=False):
        """One status row per employee on screen, for the week on screen."""
        self._require_officer()
        Packet = self.env['pb.timesheet.packet']
        week_start = Packet._monday(week_start_str)
        employees = self._employees(department_id, search)[:_MAX_PACKETS]
        rows = Packet.sudo().search([
            ('employee_id', 'in', employees.ids),
            ('week_start', '=', week_start)])
        by_employee = {row.employee_id.id: row for row in rows}
        out = []
        for employee in employees:
            packet = by_employee.get(employee.id)
            out.append(self._packet_row(employee, packet))
        return {
            'week_start': week_start.isoformat(),
            'rows': out,
            'can_submit': True,
            'summary': {
                'draft': len([r for r in out if r['state'] in ('draft',
                                                               'returned')]),
                'pending': len([r for r in out if r['state'] == 'pending']),
                'approved': len([r for r in out if r['state'] == 'approved']),
            },
        }

    def _packet_row(self, employee, packet):
        """One line of the approval tray, in the words the tray prints."""
        if not packet:
            return {
                'employee_id': employee.id, 'name': employee.name or '',
                'packet_id': 0, 'state': 'draft',
                'state_label': _('Not sent in'), 'tone': 'draft',
                'hours': 0.0, 'ot_hours': 0.0, 'note': '',
                'request_id': 0, 'waiting_for': '',
            }
        tone = {'draft': 'draft', 'returned': 'bad', 'pending': 'wait',
                'approved': 'ok', 'rejected': 'bad'}.get(packet.state, 'draft')
        label = {
            'draft': _('Not sent in'),
            'pending': (_('Waiting for %s', packet._waiting_for())
                        if packet._waiting_for() else _('Waiting for approval')),
            'approved': _('Approved'),
            'returned': _('Sent back'),
            'rejected': _('Turned down'),
        }.get(packet.state, packet.state)
        return {
            'employee_id': employee.id,
            'name': employee.name or '',
            'packet_id': packet.id,
            'state': packet.state,
            'state_label': label,
            'tone': tone,
            'hours': round(packet.total_hours or 0.0, 1),
            'ot_hours': round(packet.ot_hours or 0.0, 1),
            'note': packet.packet_note or '',
            'request_id': packet.approval_request_id.id,
            'waiting_for': packet._waiting_for(),
        }

    # ------------------------------------------------------------ write side
    @api.model
    def submit_week(self, week_start_str=False, department_id=False,
                    search=False):
        """Send the visible week in — every person on screen who has hours.

        The overtime half is exactly what it was, because an overtime entry
        that belongs to no packet must still be able to be sent in on its own —
        EXCEPT for a week that is already frozen. The base method submits every
        draft in the visible week in one write, and a week under approval
        refuses that write, which would take the whole press down with it. So
        the frozen people are taken out first and the rest go through the base
        method untouched.
        """
        frozen = self._frozen_employee_ids(week_start_str, department_id,
                                           search)
        if frozen:
            result = self._submit_overtime_except(week_start_str,
                                                  department_id, search, frozen)
        else:
            result = super().submit_week(week_start_str, department_id, search)
        packets = self.submit_week_packets(week_start_str, department_id,
                                           search)
        if isinstance(result, dict):
            result.update(packets)
        return result

    @api.model
    def _frozen_employee_ids(self, week_start_str, department_id, search):
        """Whose week on this screen is already with somebody for approval."""
        Packet = self.env['pb.timesheet.packet']
        week_start = Packet._monday(week_start_str)
        employees = self._employees(department_id, search)[:_MAX_PACKETS]
        rows = Packet.sudo().search([
            ('employee_id', 'in', employees.ids),
            ('week_start', '=', week_start),
            ('state', 'in', ('pending', 'approved'))])
        return set(rows.mapped('employee_id').ids)

    @api.model
    def _submit_overtime_except(self, week_start_str, department_id, search,
                                frozen):
        """The base method's own body, minus the people whose week is frozen."""
        from datetime import timedelta
        self._require_officer()
        Packet = self.env['pb.timesheet.packet']
        week_start = Packet._monday(week_start_str)
        week_end = week_start + timedelta(days=6)
        employees = self._employees(department_id, search)[:_MAX_PACKETS]
        wanted = [e for e in employees.ids if e not in frozen]
        drafts = self.env['hr.overtime.request'].sudo().search([
            ('employee_id', 'in', wanted),
            ('date', '>=', week_start), ('date', '<=', week_end),
            ('state', '=', 'draft'),
        ])
        drafts.action_submit()
        return {'submitted': len(drafts)}

    @api.model
    def submit_week_packets(self, week_start_str=False, department_id=False,
                            search=False):
        """Build and send in this week for everybody on screen who has hours."""
        self._require_officer()
        Packet = self.env['pb.timesheet.packet']
        week_start = Packet._monday(week_start_str)
        employees = self._employees(department_id, search)[:_MAX_PACKETS]
        sent, skipped, problems = 0, 0, []
        for employee in employees:
            packet = Packet.packet_for(employee, week_start)
            if packet.state in ('pending', 'approved'):
                skipped += 1
                continue
            if not (packet.reg_hours or packet.ot_hours):
                skipped += 1
                continue
            try:
                # Each week in its own savepoint: one person with no manager
                # must not stop the other forty-nine going in.
                with self.env.cr.savepoint():
                    packet.action_submit_week()
                sent += 1
            except Exception as exc:    # noqa: BLE001
                problems.append({
                    'employee': employee.name or '',
                    'why': (exc.args[0] if getattr(exc, 'args', None)
                            else _('It could not be sent in.')),
                })
                _logger.info('pb_timesheet_approval: %s could not send in the '
                             'week of %s: %s', employee.name, week_start, exc)
        return {'weeks_submitted': sent, 'weeks_skipped': skipped,
                'weeks_problems': problems}

    @api.model
    def submit_week_for(self, employee_id, week_start_str=False):
        """Send ONE person's week in, from their own row on the grid."""
        self._require_officer()
        Packet = self.env['pb.timesheet.packet']
        employee = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not employee:
            raise UserError(_("That employee no longer exists."))
        packet = Packet.packet_for(employee, week_start_str)
        packet.action_submit_week()
        return self._packet_row(employee, packet)
