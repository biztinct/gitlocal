# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class AttendanceLive(models.TransientModel):
    """Backend API for the Deputy-style Live Attendance Feed."""
    _name = 'hr.attendance.live'
    _description = 'Live Attendance Feed API'

    @api.model
    def _require_officer(self):
        # C18.73: the sudo leave read below lives BEHIND an explicit gate,
        # never behind the accident of a missing ACL (review K-F6)
        u = self.env.user
        if not (u.has_group('hr_attendance.group_hr_attendance_officer')
                or u.has_group('base.group_system')):
            raise AccessError(_(
                "The live attendance board is restricted to attendance officers."))

    @api.model
    def get_live_data(self, department_id=False):
        """
        Return live attendance data: employees grouped into status columns.
        Statuses: on_shift, on_break, not_started, checked_out
        """
        self._require_officer()
        today = date.today()
        now = datetime.now()
        today_start = datetime.combine(today, datetime.min.time())

        emp_domain = [('active', '=', True)]
        if department_id:
            emp_domain.append(('department_id', '=', department_id))
        employees = self.env['hr.employee'].search(emp_domain, order='name')

        # Today's attendance records
        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', today_start),
        ])

        # Today's scheduled shifts
        shifts = self.env['hr.shift.planning'].search([
            ('employee_id', 'in', employees.ids),
            ('date', '=', today),
            ('state', 'in', ('published', 'completed')),
        ])

        # Build status cards
        on_shift = []
        checked_out = []
        not_started = []

        for emp in employees:
            emp_att = attendances.filtered(lambda a: a.employee_id.id == emp.id)
            emp_shift = shifts.filtered(lambda s: s.employee_id.id == emp.id)

            # Get the latest attendance record
            latest = False
            if emp_att:
                latest = emp_att.sorted('check_in', reverse=True)[0]

            # Get the scheduled shift info
            shift_info = {}
            is_late = False
            if emp_shift:
                s = emp_shift[0]
                shift_info = {
                    'template': s.shift_template_id.name if s.shift_template_id else '',
                    'start': s.start_datetime.strftime('%I:%M%p').lstrip('0').lower() if s.start_datetime else '',
                    'end': s.end_datetime.strftime('%I:%M%p').lstrip('0').lower() if s.end_datetime else '',
                    'planned_hours': s.planned_hours,
                }
                # Late check
                if latest and s.start_datetime:
                    if latest.check_in > s.start_datetime + timedelta(minutes=10):
                        is_late = True
                elif not latest and s.start_datetime:
                    if now > s.start_datetime + timedelta(minutes=10):
                        is_late = True

            card = {
                'id': emp.id,
                'name': emp.name,
                'job_title': emp.job_title or '',
                'department': emp.department_id.name if emp.department_id else '',
                'avatar_url': f'/web/image/hr.employee/{emp.id}/avatar_128',
                'shift': shift_info,
                'is_late': is_late,
            }

            if latest and not latest.check_out:
                # Currently checked in
                duration = (now - latest.check_in).total_seconds() / 3600
                card['check_in'] = latest.check_in.strftime('%I:%M%p').lstrip('0').lower()
                card['duration'] = round(duration, 1)
                card['status'] = 'on_shift'
                on_shift.append(card)
            elif latest and latest.check_out:
                # Checked out already
                duration = latest.worked_hours
                card['check_in'] = latest.check_in.strftime('%I:%M%p').lstrip('0').lower()
                card['check_out'] = latest.check_out.strftime('%I:%M%p').lstrip('0').lower()
                card['duration'] = round(duration, 1)
                card['status'] = 'checked_out'
                checked_out.append(card)
            else:
                # No attendance record today
                card['status'] = 'not_started'
                not_started.append(card)

        # Today's leaves. sudo: the on-leave strip is system-derived presence
        # context (same one-permission-world rail as the Weekly Entry grid) —
        # without it a viewer lacking hr.leave.type read crashes the whole board
        # on the holiday_status_id.name dereference below.
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', employees.ids),
            ('state', 'in', ('validate', 'validate1')),
            ('date_from', '<=', datetime.combine(today, datetime.max.time())),
            ('date_to', '>=', today_start),
        ])
        on_leave = []
        for lv in leaves:
            emp = lv.employee_id
            on_leave.append({
                'id': emp.id,
                'name': emp.name,
                'job_title': emp.job_title or '',
                'department': emp.department_id.name if emp.department_id else '',
                'avatar_url': f'/web/image/hr.employee/{emp.id}/avatar_128',
                'leave_type': lv.holiday_status_id.name or 'Leave',
                'status': 'on_leave',
            })
        # Remove on-leave employees from not_started
        leave_ids = {lv['id'] for lv in on_leave}
        not_started = [c for c in not_started if c['id'] not in leave_ids]

        summary = {
            'total': len(employees),
            'on_shift': len(on_shift),
            'checked_out': len(checked_out),
            'not_started': len(not_started),
            'on_leave': len(on_leave),
            'late': sum(1 for c in on_shift if c.get('is_late')) + sum(1 for c in not_started if c.get('is_late')),
        }

        return {
            'on_shift': on_shift,
            'checked_out': checked_out,
            'not_started': not_started,
            'on_leave': on_leave,
            'summary': summary,
            'timestamp': now.strftime('%I:%M:%S %p'),
        }

    @api.model
    def get_departments(self):
        """Return departments list."""
        self._require_officer()
        deps = self.env['hr.department'].search([], order='name')
        return [{'id': d.id, 'name': d.name} for d in deps]
