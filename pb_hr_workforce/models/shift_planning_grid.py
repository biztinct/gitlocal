# Part of Payobook. See LICENSE file for full copyright and licensing details.

import json
from datetime import date, datetime, timedelta

from odoo import api, fields, models, _


class ShiftPlanningGrid(models.TransientModel):
    """Backend API for the Deputy-style shift planning grid."""
    _name = 'hr.shift.planning.grid'
    _description = 'Shift Planning Grid API'

    @api.model
    def get_grid_data(self, week_start_str, department_id=False):
        """
        Return grid data: employees (rows) × days (columns) × shifts (cells).
        week_start_str: ISO date string for Monday of the target week.
        """
        week_start = fields.Date.from_string(week_start_str)
        week_end = week_start + timedelta(days=6)
        days = []
        for i in range(7):
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
        employees_raw = self.env['hr.employee'].search(emp_domain, order='name')

        # Shifts for this week
        shifts = self.env['hr.shift.planning'].search([
            ('date', '>=', week_start),
            ('date', '<=', week_end),
            ('state', '!=', 'cancelled'),
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

            # Group shifts by date
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

            employees.append({
                'id': emp.id,
                'name': emp.name,
                'job_title': emp.job_title or '',
                'department': emp.department_id.name if emp.department_id else '',
                'avatar_url': f'/web/image/hr.employee/{emp.id}/avatar_128',
                'total_hours': round(total_planned, 1),
                'shifts': shifts_by_date,
            })

        # Summary stats
        all_shifts = shifts
        published = len(all_shifts.filtered(lambda s: s.state == 'published'))
        draft = len(all_shifts.filtered(lambda s: s.state == 'draft'))
        completed = len(all_shifts.filtered(lambda s: s.state == 'completed'))
        total_hours = round(sum(s.planned_hours for s in all_shifts), 1)

        return {
            'days': days,
            'employees': employees,
            'templates': list(template_map.values()),
            'summary': {
                'total_shifts': len(all_shifts),
                'published': published,
                'draft': draft,
                'completed': completed,
                'total_hours': total_hours,
            },
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
        }

    @api.model
    def quick_create_shift(self, employee_id, date_str, template_id):
        """Quick-create a shift from the grid."""
        template = self.env['hr.shift.template'].browse(template_id)
        shift_date = fields.Date.from_string(date_str)

        # Calculate datetimes from template hours
        start_h = int(template.start_hour)
        start_m = int((template.start_hour % 1) * 60)
        end_h = int(template.end_hour)
        end_m = int((template.end_hour % 1) * 60)

        start_dt = datetime.combine(shift_date, datetime.min.time().replace(
            hour=start_h, minute=start_m))
        if template.is_overnight:
            end_dt = datetime.combine(shift_date + timedelta(days=1),
                                       datetime.min.time().replace(
                                           hour=end_h, minute=end_m))
        else:
            end_dt = datetime.combine(shift_date, datetime.min.time().replace(
                hour=end_h, minute=end_m))

        shift = self.env['hr.shift.planning'].create({
            'employee_id': employee_id,
            'shift_template_id': template_id,
            'date': shift_date,
            'start_datetime': start_dt,
            'end_datetime': end_dt,
            'state': 'draft',
        })
        return shift.id

    @api.model
    def delete_shift(self, shift_id):
        """Delete a draft shift from the grid."""
        shift = self.env['hr.shift.planning'].browse(shift_id)
        if shift.state == 'draft':
            shift.unlink()
            return True
        return False

    @api.model
    def publish_shifts(self, week_start_str, department_id=False):
        """Publish all draft shifts for the week."""
        week_start = fields.Date.from_string(week_start_str)
        week_end = week_start + timedelta(days=6)
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
    def get_departments(self):
        """Return departments for the filter dropdown."""
        deps = self.env['hr.department'].search([], order='name')
        return [{'id': d.id, 'name': d.name} for d in deps]
