# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta

from odoo import api, fields, models, _


class AttendanceTimecard(models.TransientModel):
    """Backend API for the Rippling-style Timecard visual timeline."""
    _name = 'hr.attendance.timecard'
    _description = 'Attendance Timecard API'

    @api.model
    def get_timecard_data(self, employee_id=False, week_start_str=False, department_id=False,
                          show_only_with_hours=False):
        """
        Return timecard data: daily attendance bars on an hour axis.
        Differentiates regular hours vs overtime and overtime type.
        """
        if week_start_str:
            week_start = fields.Date.from_string(week_start_str)
        else:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Build days
        days = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            days.append({
                'date': d.isoformat(),
                'label': d.strftime('%a'),
                'full_label': d.strftime('%a %b %d'),
                'day_name': d.strftime('%a'),
                'is_today': d == date.today(),
                'is_weekend': d.weekday() >= 5,
            })

        # Employee(s)
        if employee_id:
            employees = self.env['hr.employee'].browse(employee_id)
        else:
            domain = [('active', '=', True)]
            if department_id:
                domain.append(('department_id', '=', department_id))
            employees = self.env['hr.employee'].search(domain, order='name', limit=50)

        # Attendance records for the week
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        week_end_dt = datetime.combine(week_end, datetime.max.time())

        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', week_start_dt),
            ('check_in', '<=', week_end_dt),
        ])

        # Overtime rules
        ot_rules = self.env['hr.overtime.config'].search([('active', '=', True)])

        # Public holidays (if hr_holidays_public module provides them)
        holidays_dates = set()
        try:
            pub_holidays = self.env['hr.holidays.public.line'].search([
                ('date', '>=', week_start),
                ('date', '<=', week_end),
            ])
            holidays_dates = {h.date for h in pub_holidays}
        except Exception:
            pass  # Module may not be installed

        result = []
        for emp in employees:
            emp_att = attendances.filtered(lambda a: a.employee_id.id == emp.id)

            # Get daily standard hours from resource calendar
            standard_daily_hours = 8.0
            if emp.resource_calendar_id:
                cal = emp.resource_calendar_id
                standard_daily_hours = cal.hours_per_week / 5.0 if cal.hours_per_week else 8.0

            total_regular = 0
            total_ot = 0
            ot_breakdown = {}  # ot_type -> hours
            day_cards = {}

            for day_info in days:
                d = fields.Date.from_string(day_info['date'])
                day_start = datetime.combine(d, datetime.min.time())
                day_end = datetime.combine(d, datetime.max.time())

                day_atts = emp_att.filtered(
                    lambda a: a.check_in >= day_start and a.check_in <= day_end
                )

                # Total worked hours this day
                day_total = sum(a.worked_hours or 0 for a in day_atts)

                # Determine OT type for this day
                is_weekend = d.weekday() >= 5
                is_holiday = d in holidays_dates
                day_ot_type = False
                day_ot_rate = 1.0
                day_ot_label = ''

                if is_holiday:
                    rule = ot_rules.filtered(lambda r: r.overtime_type == 'holiday')
                    if rule:
                        day_ot_type = 'holiday'
                        day_ot_rate = rule[0].rate_multiplier
                        day_ot_label = f'Holiday OT ({rule[0].rate_display})'
                elif is_weekend:
                    rule = ot_rules.filtered(lambda r: r.overtime_type == 'weekend')
                    if rule:
                        day_ot_type = 'weekend'
                        day_ot_rate = rule[0].rate_multiplier
                        day_ot_label = f'Weekend OT ({rule[0].rate_display})'
                else:
                    rule = ot_rules.filtered(lambda r: r.overtime_type == 'weekday')
                    if rule:
                        day_ot_type = 'weekday'
                        day_ot_rate = rule[0].rate_multiplier
                        day_ot_label = f'Weekday OT ({rule[0].rate_display})'

                # Split regular vs overtime
                if is_weekend or is_holiday:
                    # All hours on weekend/holiday are OT
                    regular_hrs = 0
                    ot_hrs = day_total
                else:
                    regular_hrs = min(day_total, standard_daily_hours)
                    ot_hrs = max(0, day_total - standard_daily_hours)

                total_regular += regular_hrs
                total_ot += ot_hrs
                if day_ot_type and ot_hrs > 0:
                    ot_breakdown.setdefault(day_ot_type, {
                        'type': day_ot_type,
                        'label': day_ot_label,
                        'rate': day_ot_rate,
                        'hours': 0,
                    })
                    ot_breakdown[day_ot_type]['hours'] = round(
                        ot_breakdown[day_ot_type]['hours'] + ot_hrs, 1)

                # Check for night shift OT
                night_ot_hrs = 0
                night_rule = ot_rules.filtered(lambda r: r.overtime_type == 'night')
                if night_rule:
                    nr = night_rule[0]
                    for att in day_atts:
                        ci = att.check_in
                        co = att.check_out or datetime.now()
                        start_h = ci.hour + ci.minute / 60.0
                        end_h = co.hour + co.minute / 60.0
                        # Night typically 22:00 - 06:00
                        night_from = nr.time_from or 22.0
                        night_to = nr.time_to or 6.0
                        if start_h >= night_from or end_h <= night_to or start_h < night_to:
                            # Approximate night hours
                            if start_h >= night_from:
                                night_ot_hrs += min(end_h + 24 if end_h < start_h else end_h,
                                                    night_to + 24) - start_h
                            elif start_h < night_to:
                                night_ot_hrs += min(end_h, night_to) - start_h
                    if night_ot_hrs > 0:
                        night_ot_hrs = round(max(0, night_ot_hrs), 1)
                        ot_breakdown.setdefault('night', {
                            'type': 'night',
                            'label': f'Night OT ({night_rule[0].rate_display})',
                            'rate': night_rule[0].rate_multiplier,
                            'hours': 0,
                        })
                        ot_breakdown['night']['hours'] = round(
                            ot_breakdown['night']['hours'] + night_ot_hrs, 1)

                # Build bar entries
                entries = []
                for att in day_atts.sorted('check_in'):
                    ci = att.check_in
                    co = att.check_out
                    worked = att.worked_hours if att.worked_hours else 0

                    start_hour = ci.hour + ci.minute / 60.0
                    end_hour = (co.hour + co.minute / 60.0) if co else (
                        datetime.now().hour + datetime.now().minute / 60.0)

                    grid_start = 6
                    grid_end = 22
                    grid_span = grid_end - grid_start

                    bar_left = max(0, (start_hour - grid_start) / grid_span * 100)
                    bar_width = max(2, (end_hour - start_hour) / grid_span * 100)

                    # Determine bar type
                    bar_type = 'regular'
                    if is_holiday:
                        bar_type = 'holiday'
                    elif is_weekend:
                        bar_type = 'weekend'
                    elif worked > standard_daily_hours:
                        bar_type = 'overtime'

                    # Split bar into regular + OT if weekday with OT
                    bar_entries = []
                    if not is_weekend and not is_holiday and ot_hrs > 0 and len(day_atts) == 1:
                        # Regular portion
                        reg_width = (standard_daily_hours / grid_span * 100)
                        ot_left = bar_left + reg_width
                        ot_width = bar_width - reg_width

                        bar_entries.append({
                            'id': att.id,
                            'check_in': ci.strftime('%I:%M%p').lstrip('0').lower(),
                            'check_out': co.strftime('%I:%M%p').lstrip('0').lower() if co else 'Now',
                            'worked': round(regular_hrs, 1),
                            'bar_left': round(bar_left, 1),
                            'bar_width': round(max(2, reg_width), 1),
                            'bar_type': 'regular',
                            'is_active': not bool(co),
                            'label': f'{round(regular_hrs, 1)}h regular',
                        })
                        if ot_width > 0:
                            bar_entries.append({
                                'id': att.id * 1000,
                                'check_in': '',
                                'check_out': co.strftime('%I:%M%p').lstrip('0').lower() if co else 'Now',
                                'worked': round(ot_hrs, 1),
                                'bar_left': round(ot_left, 1),
                                'bar_width': round(max(2, ot_width), 1),
                                'bar_type': 'overtime',
                                'is_active': not bool(co),
                                'label': f'{round(ot_hrs, 1)}h OT',
                            })
                    else:
                        bar_entries.append({
                            'id': att.id,
                            'check_in': ci.strftime('%I:%M%p').lstrip('0').lower(),
                            'check_out': co.strftime('%I:%M%p').lstrip('0').lower() if co else 'Now',
                            'worked': round(worked, 1),
                            'bar_left': round(bar_left, 1),
                            'bar_width': round(min(bar_width, 100 - bar_left), 1),
                            'bar_type': bar_type,
                            'is_active': not bool(co),
                            'label': f'{round(worked, 1)}h',
                        })

                    entries.extend(bar_entries)

                day_cards[day_info['date']] = {
                    'entries': entries,
                    'regular': round(regular_hrs, 1),
                    'overtime': round(ot_hrs, 1),
                    'total': round(day_total, 1),
                    'ot_type': day_ot_type,
                    'ot_label': day_ot_label,
                }

            if show_only_with_hours and total_regular + total_ot == 0:
                continue

            result.append({
                'id': emp.id,
                'name': emp.name,
                'job_title': emp.job_title or '',
                'department': emp.department_id.name if emp.department_id else '',
                'avatar_url': f'/web/image/hr.employee/{emp.id}/avatar_128',
                'total_regular': round(total_regular, 1),
                'total_ot': round(total_ot, 1),
                'total_hours': round(total_regular + total_ot, 1),
                'standard_daily_hours': standard_daily_hours,
                'ot_breakdown': list(ot_breakdown.values()),
                'days': day_cards,
            })

        # Hour labels for the grid (6AM - 9PM)
        hour_labels = []
        for h in range(6, 22):
            ampm = 'AM' if h < 12 else 'PM'
            h12 = h if h <= 12 else h - 12
            if h == 0:
                h12 = 12
            hour_labels.append(f'{h12}{ampm}')

        # OT rules summary for legend
        ot_legend = []
        for rule in ot_rules:
            ot_legend.append({
                'type': rule.overtime_type,
                'name': rule.name,
                'rate': rule.rate_display,
                'color': {
                    'weekday': '#e74c3c',
                    'weekend': '#9b59b6',
                    'holiday': '#e67e22',
                    'night': '#2c3e50',
                    'extended': '#c0392b',
                }.get(rule.overtime_type, '#e74c3c'),
            })

        return {
            'days': days,
            'employees': result,
            'hour_labels': hour_labels,
            'ot_legend': ot_legend,
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
        }

    @api.model
    def get_departments(self):
        deps = self.env['hr.department'].search([], order='name')
        return [{'id': d.id, 'name': d.name} for d in deps]
