# Part of Payobook. See LICENSE file for full copyright and licensing details.

import json
from datetime import date, datetime, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ShiftPlanningGrid(models.TransientModel):
    """Backend API for the Deputy-style shift planning grid."""
    _name = 'hr.shift.planning.grid'
    _description = 'Shift Planning Grid API'

    # ------------------------------------------------- shift wall clock (P5)
    @api.model
    def _pb_shift_tzname(self, employee=None):
        """The timezone a shift template's hours are expressed IN.

        Employee first — a shift describes that person's morning — then the
        calendar they work to, then the requesting user, then UTC. Same ladder
        as `hr.attendance.weekentry._emp_tz`. A junk name degrades to UTC
        instead of exploding a roster load.

        Lives on the BASE facade on purpose: `pb_schedule._pb_shift_window`
        exists to predict byte-for-byte what `quick_create_shift` writes, and
        two copies of this ladder would be two things to drift (W53).
        """
        company = (employee.company_id if employee else False) or self.env.company
        cal = ((employee.resource_calendar_id if employee else False)
               or company.resource_calendar_id)
        name = ((employee.tz if employee else False)
                or (cal.tz if cal else False)
                or self.env.user.tz or 'UTC')
        try:
            pytz.timezone(name)
        except Exception:
            name = 'UTC'
        return name

    @api.model
    def _pb_shift_utc(self, start_dt, end_dt, employee=None, tzname=False):
        """Wall-clock (start, end) → the naive UTC pair Odoo actually stores."""
        tz = pytz.timezone(tzname or self._pb_shift_tzname(employee))

        def conv(dt):
            if not dt:
                return dt
            return tz.localize(dt).astimezone(pytz.UTC).replace(tzinfo=None)

        return conv(start_dt), conv(end_dt)

    @api.model
    def _require_officer(self):
        # C18.73: the sudo reads below live BEHIND an explicit gate, never
        # behind the accident of a missing ACL (review K-F6)
        u = self.env.user
        if not (u.has_group('hr_attendance.group_hr_attendance_officer')
                or u.has_group('base.group_system')):
            raise AccessError(_(
                "Shift planning is restricted to attendance officers."))

    @api.model
    def get_grid_data(self, week_start_str, department_id=False, job_id=False, num_days=7):
        """
        Return grid data: employees × days × shifts + leave overlay.
        """
        self._require_officer()
        week_start = fields.Date.from_string(week_start_str)
        week_end = week_start + timedelta(days=num_days - 1)
        days = []
        for i in range(num_days):
            d = week_start + timedelta(days=i)
            days.append({
                'date': d.isoformat(),
                'label': d.strftime('%a'),
                'full_label': d.strftime('%a %d %b'),
                'is_today': d == date.today(),
                'is_weekend': d.weekday() >= 5,
            })

        # Employees
        emp_domain = [('active', '=', True)]
        if department_id:
            emp_domain.append(('department_id', '=', department_id))
        if job_id:
            emp_domain.append(('job_id', '=', job_id))
        employees_raw = self.env['hr.employee'].search(emp_domain, order='name')

        # Shifts for this period
        shifts = self.env['hr.shift.planning'].search([
            ('date', '>=', week_start),
            ('date', '<=', week_end),
            ('state', '!=', 'cancelled'),
        ])

        # Leaves for this period. sudo: the leave/leave-type presence overlay is
        # system-derived roster context (same one-permission-world rail as the
        # Weekly Entry grid, which also sudo-reads leaves) — without it a planner
        # who lacks hr.leave.type read crashes the whole roster on the
        # holiday_status_id dereference below.
        all_leaves = self.env['hr.leave'].sudo().search([
            ('state', 'in', ('confirm', 'validate', 'validate1')),
            ('date_from', '<=', datetime.combine(week_end, datetime.max.time())),
            ('date_to', '>=', datetime.combine(week_start, datetime.min.time())),
        ])

        # Shift templates for color/name mapping
        templates = self.env['hr.shift.template'].search([])
        template_map = {t.id: {
            'id': t.id,
            'name': t.name,
            'code': t.code,
            'color': t.color,
            'shift_type': t.shift_type,
            'start_hour': t.start_hour,
            'end_hour': t.end_hour,
            'duration': t.duration,
        } for t in templates}

        # Build employee rows
        employees = []
        for emp in employees_raw:
            emp_shifts = shifts.filtered(lambda s: s.employee_id.id == emp.id)
            total_planned = sum(s.planned_hours for s in emp_shifts)

            # Shifts by date
            shifts_by_date = {}
            for s in emp_shifts:
                d = s.date.isoformat()
                shifts_by_date.setdefault(d, [])
                tmpl = template_map.get(s.shift_template_id.id, {})
                shifts_by_date[d].append({
                    'id': s.id,
                    'template_id': s.shift_template_id.id,
                    'template_name': tmpl.get('name', ''),
                    'template_code': tmpl.get('code', ''),
                    'color': tmpl.get('color', 0),
                    'shift_type': tmpl.get('shift_type', ''),
                    'start': s.start_datetime.strftime('%I:%M%p').lstrip('0').lower() if s.start_datetime else '',
                    'end': s.end_datetime.strftime('%I:%M%p').lstrip('0').lower() if s.end_datetime else '',
                    'state': s.state,
                    'compliance': s.compliance_status,
                    'planned_hours': s.planned_hours,
                })

            # Leaves by date
            emp_leaves = all_leaves.filtered(lambda l: l.employee_id.id == emp.id)
            leaves_by_date = {}
            for lv in emp_leaves:
                lv_start = lv.date_from.date() if isinstance(lv.date_from, datetime) else lv.date_from
                lv_end = lv.date_to.date() if isinstance(lv.date_to, datetime) else lv.date_to
                cur = max(lv_start, week_start)
                end_d = min(lv_end, week_end)
                while cur <= end_d:
                    d_str = cur.isoformat()
                    leaves_by_date[d_str] = {
                        'type': lv.holiday_status_id.name or 'Leave',
                        'state': lv.state,
                        'is_approved': lv.state in ('validate', 'validate1'),
                    }
                    cur += timedelta(days=1)

            # Contracted hours (from resource calendar)
            contracted = 0
            if emp.resource_calendar_id:
                contracted = emp.resource_calendar_id.hours_per_week or 40
            else:
                contracted = 40

            employees.append({
                'id': emp.id,
                'name': emp.name,
                'job_title': emp.job_title or '',
                'job_id': emp.job_id.id if emp.job_id else False,
                'department': emp.department_id.name if emp.department_id else '',
                'avatar_url': f'/web/image/hr.employee/{emp.id}/avatar_128',
                'total_hours': round(total_planned, 1),
                'contracted_hours': round(contracted, 1),
                'shifts': shifts_by_date,
                'leaves': leaves_by_date,
            })

        # Open/unassigned shifts
        open_shifts = shifts.filtered(lambda s: not s.employee_id)
        open_by_date = {}
        for s in open_shifts:
            d = s.date.isoformat()
            open_by_date.setdefault(d, [])
            tmpl = template_map.get(s.shift_template_id.id, {})
            open_by_date[d].append({
                'id': s.id,
                'template_name': tmpl.get('name', ''),
                'color': tmpl.get('color', 0),
                'start': s.start_datetime.strftime('%I:%M%p').lstrip('0').lower() if s.start_datetime else '',
                'end': s.end_datetime.strftime('%I:%M%p').lstrip('0').lower() if s.end_datetime else '',
                'state': s.state,
            })

        # Warnings / conflict detection
        warnings = self._detect_conflicts(shifts)

        # Summary stats
        assigned = shifts.filtered(lambda s: s.employee_id)
        published = len(assigned.filtered(lambda s: s.state == 'published'))
        draft = len(assigned.filtered(lambda s: s.state == 'draft'))
        completed = len(assigned.filtered(lambda s: s.state == 'completed'))
        total_hours = round(sum(s.planned_hours for s in assigned), 1)

        return {
            'days': days,
            'employees': employees,
            'templates': list(template_map.values()),
            'open_shifts': open_by_date,
            'warnings': warnings,
            'summary': {
                'total_shifts': len(assigned),
                'published': published,
                'draft': draft,
                'completed': completed,
                'total_hours': total_hours,
                'open_shifts': len(open_shifts),
                'warnings': len(warnings),
                'leave_approved': sum(1 for e in employees for d in e.get('leaves', {}).values() if d.get('is_approved')),
                'leave_pending': sum(1 for e in employees for d in e.get('leaves', {}).values() if not d.get('is_approved')),
            },
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
        }

    def _detect_conflicts(self, shifts):
        """Find overlapping shifts for the same employee."""
        warnings = []
        assigned = shifts.filtered(lambda s: s.employee_id and s.start_datetime and s.end_datetime)
        emp_shifts = {}
        for s in assigned:
            emp_shifts.setdefault(s.employee_id.id, []).append(s)

        for emp_id, emp_s in emp_shifts.items():
            sorted_s = sorted(emp_s, key=lambda x: x.start_datetime)
            for i in range(len(sorted_s) - 1):
                a = sorted_s[i]
                b = sorted_s[i + 1]
                if a.end_datetime > b.start_datetime:
                    warnings.append({
                        'type': 'overlap',
                        'employee_id': emp_id,
                        'employee_name': a.employee_id.name,
                        'shift_a_id': a.id,
                        'shift_b_id': b.id,
                        'message': f'Overlapping shifts on {a.date}',
                    })
        return warnings

    @api.model
    def quick_create_shift(self, employee_id, date_str, template_id):
        """Quick-create a shift from the grid."""
        self._require_officer()
        template = self.env['hr.shift.template'].browse(template_id)
        shift_date = fields.Date.from_string(date_str)

        start_h = int(template.start_hour)
        start_m = int((template.start_hour % 1) * 60)
        end_h = int(template.end_hour)
        end_m = int((template.end_hour % 1) * 60)

        start_dt = datetime.combine(shift_date, datetime.min.time().replace(
            hour=start_h, minute=start_m))
        if template.is_overnight:
            end_dt = datetime.combine(shift_date + timedelta(days=1),
                                       datetime.min.time().replace(hour=end_h, minute=end_m))
        else:
            end_dt = datetime.combine(shift_date, datetime.min.time().replace(
                hour=end_h, minute=end_m))

        # P5 WP-0b: a template hour is a WALL CLOCK ("08:00" means 8 in the
        # morning where the person works) and `start_datetime` is a
        # fields.Datetime, i.e. UTC. Storing the wall clock verbatim made an
        # 08:00 VN shift sit at 15:00 local, which every consumer that DOES
        # localize then reported wrongly — the roster's own printed times, the
        # lateness compute, and `_save_reg`'s derived check-in. Converted here,
        # and byte-identically in `pb.schedule`'s `_pb_shift_window`, which is
        # the warning engine's prediction of exactly this create.
        emp = self.env['hr.employee'].browse(employee_id) if employee_id else None
        start_dt, end_dt = self._pb_shift_utc(start_dt, end_dt, emp)

        vals = {
            'shift_template_id': template_id,
            'date': shift_date,
            'start_datetime': start_dt,
            'end_datetime': end_dt,
            'state': 'draft',
        }
        if employee_id:
            vals['employee_id'] = employee_id
        shift = self.env['hr.shift.planning'].create(vals)
        return shift.id

    @api.model
    def delete_shift(self, shift_id):
        """Delete a draft shift."""
        self._require_officer()
        shift = self.env['hr.shift.planning'].browse(shift_id)
        if shift.state == 'draft':
            shift.unlink()
            return True
        return False

    @api.model
    def publish_shifts(self, week_start_str, department_id=False, num_days=7):
        """Publish all draft shifts for the period."""
        self._require_officer()
        week_start = fields.Date.from_string(week_start_str)
        week_end = week_start + timedelta(days=num_days - 1)
        domain = [
            ('date', '>=', week_start),
            ('date', '<=', week_end),
            ('state', '=', 'draft'),
        ]
        if department_id:
            domain.append(('department_id', '=', department_id))
        shifts = self.env['hr.shift.planning'].search(domain)
        shifts.action_publish()
        return len(shifts)

    @api.model
    def copy_week(self, source_week_str, target_week_str, department_id=False):
        """Copy all shifts from source week to target week."""
        self._require_officer()
        source_start = fields.Date.from_string(source_week_str)
        source_end = source_start + timedelta(days=6)
        delta = fields.Date.from_string(target_week_str) - source_start

        domain = [
            ('date', '>=', source_start),
            ('date', '<=', source_end),
            ('state', '!=', 'cancelled'),
        ]
        if department_id:
            domain.append(('department_id', '=', department_id))

        source_shifts = self.env['hr.shift.planning'].search(domain)
        count = 0
        for shift in source_shifts:
            new_date = shift.date + delta
            new_start = shift.start_datetime + delta if shift.start_datetime else False
            new_end = shift.end_datetime + delta if shift.end_datetime else False
            self.env['hr.shift.planning'].create({
                'employee_id': shift.employee_id.id,
                'shift_template_id': shift.shift_template_id.id,
                'date': new_date,
                'start_datetime': new_start,
                'end_datetime': new_end,
                'state': 'draft',
            })
            count += 1
        return count

    @api.model
    def get_departments(self):
        """Return departments for the filter dropdown."""
        self._require_officer()
        deps = self.env['hr.department'].search([], order='name')
        return [{'id': d.id, 'name': d.name} for d in deps]

    @api.model
    def get_job_positions(self):
        """Return job positions for the filter dropdown."""
        self._require_officer()
        jobs = self.env['hr.job'].search([], order='name')
        return [{'id': j.id, 'name': j.name} for j in jobs]
