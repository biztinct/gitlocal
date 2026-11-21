# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Shared fixtures for the S5-B suites.

Everything is made inside the test transaction and rolled back with it. The
week is a settled PAST week (nothing "today"), every person is on UTC so a
local day is the UTC day, and the company gets its own overtime rules for the
four kinds so the kind of day a suggestion carries does not depend on what a
database happens to have seeded.
"""

from datetime import date, datetime, time, timedelta

from odoo.tests import TransactionCase


class TimePayCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.TP = cls.env['pb.time.pay']
        cls.Close = cls.env['pb.close']
        cls.Late = cls.env['pb.time.late']
        cls.Att = cls.env['hr.attendance']
        cls.OT = cls.env['hr.overtime.request']
        cls.Rule = cls.env['pb.attendance.rule'].sudo()
        for process in ('unlock',):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
                    cls.company, process, reason='S5-B suite')
            except Exception:       # noqa: BLE001 — a fixture must not die
                pass

        today = date.today()
        cls.week_start = today - timedelta(days=today.weekday() + 14)
        cls.mon = cls.week_start
        cls.tue = cls.mon + timedelta(days=1)
        cls.wed = cls.mon + timedelta(days=2)
        cls.sat = cls.mon + timedelta(days=5)

        cls.Rule.search([]).write({'active': False})
        cls.rule = cls.Rule.create({
            'name': 'S5B global', 'company_id': False,
            'grace_in_minutes': 15, 'grace_out_minutes': 15,
            'open_checkout_hours': 16,
            'variance_minutes': 10, 'variance_hours_week': 0.5})

        Config = cls.env['hr.overtime.config'].sudo()
        Config.search([('company_id', '=', cls.company.id)]).write(
            {'active': False})
        for kind, rate in (('weekday', 1.5), ('weekend', 2.0),
                           ('holiday', 3.0)):
            Config.create({'name': 'S5B %s' % kind, 'overtime_type': kind,
                           'rate_multiplier': rate,
                           'company_id': cls.company.id})
        cls.night_cfg = Config.create({
            'name': 'S5B night', 'overtime_type': 'night',
            'rate_multiplier': 2.1, 'time_from': 22.0, 'time_to': 6.0,
            'company_id': cls.company.id})

        # A 08:00-16:00 schedule with no lunch for the SHIFT people (their day
        # is the shift, and no calendar lunch is taken off their punches) and a
        # 08:00–17:00 one with a 12:00–13:00 lunch for the HOURS people.
        Cal = cls.env['resource.calendar'].sudo()
        cls.cal_flex = Cal.create({
            'name': 'S5B shift people', 'tz': 'UTC',
            'company_id': cls.company.id,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'name': 'Day', 'dayofweek': dow, 'hour_from': 8,
                        'hour_to': 16, 'day_period': 'full_day'})
                for dow in '01234']})
        att = []
        for dow in '01234':
            att += [
                (0, 0, {'name': 'AM', 'dayofweek': dow, 'hour_from': 8,
                        'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Lunch', 'dayofweek': dow, 'hour_from': 12,
                        'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'PM', 'dayofweek': dow, 'hour_from': 13,
                        'hour_to': 17, 'day_period': 'afternoon'}),
            ]
        cls.cal_office = Cal.create({
            'name': 'S5B office', 'tz': 'UTC', 'company_id': cls.company.id,
            'attendance_ids': [(5, 0, 0)] + att})

        cls.manager_user = cls._mk_user('s5b_manager', [
            'hr.group_hr_user',
            'hr_attendance.group_hr_attendance_officer',
            'hr_attendance.group_hr_attendance_manager'])
        cls.officer_user = cls._mk_user('s5b_officer', [
            'hr.group_hr_user',
            'hr_attendance.group_hr_attendance_officer'])
        Emp = cls.env['hr.employee'].sudo()
        cls.dept = cls.env['hr.department'].sudo().create(
            {'name': 'S5B Floor', 'company_id': cls.company.id})
        cls.boss = Emp.create({
            'name': 'S5B Boss', 'company_id': cls.company.id, 'tz': 'UTC',
            'user_id': cls.manager_user.id, 'department_id': cls.dept.id,
            'resource_calendar_id': cls.cal_flex.id})
        cls.shifty = Emp.create({
            'name': 'S5B Shifty', 'company_id': cls.company.id, 'tz': 'UTC',
            'parent_id': cls.boss.id, 'department_id': cls.dept.id,
            'resource_calendar_id': cls.cal_flex.id})
        cls.office = Emp.create({
            'name': 'S5B Office', 'company_id': cls.company.id, 'tz': 'UTC',
            'parent_id': cls.boss.id, 'department_id': cls.dept.id,
            'resource_calendar_id': cls.cal_office.id})
        cls.tmpl = cls.env['hr.shift.template'].sudo().create({
            'name': 'S5B Day', 'code': 'S5BDAY', 'start_hour': 8.0,
            'end_hour': 16.0, 'break_duration': 0.0, 'is_overnight': False,
            'shift_type': 'morning', 'company_id': cls.company.id})

    # ------------------------------------------------------------- helpers
    @classmethod
    def _mk_user(cls, login, group_xmlids):
        groups = [cls.env.ref('base.group_user').id]
        for xmlid in group_xmlids:
            groups.append(cls.env.ref(xmlid).id)
        return cls.env['res.users'].sudo().with_context(
            no_reset_password=True).create({
                'name': login, 'login': login,
                'email': '%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, groups)]})

    def _shift(self, emp, day, start_h=8, end_h=16, state='published'):
        return self.env['hr.shift.planning'].sudo().create({
            'employee_id': emp.id, 'shift_template_id': self.tmpl.id,
            'date': day,
            'start_datetime': datetime.combine(day, time(0)) + timedelta(hours=start_h),
            'end_datetime': datetime.combine(day, time(0)) + timedelta(hours=end_h),
            'state': state})

    def _punch(self, emp, day, start, end, source='device'):
        """`start` / `end` are hours (floats) from midnight of `day`."""
        base = datetime.combine(day, time(0))
        vals = {'employee_id': emp.id,
                'check_in': base + timedelta(hours=start),
                'pb_entry_source': source}
        if end is not None:
            vals['check_out'] = base + timedelta(hours=end)
        return self.Att.sudo().create(vals)

    def _closure(self, day, name='S5B Holiday'):
        return self.env['resource.calendar.leaves'].sudo().create({
            'name': name, 'company_id': self.company.id,
            'calendar_id': self.company.resource_calendar_id.id or False,
            'date_from': datetime.combine(day, time(0, 0)),
            'date_to': datetime.combine(day, time(23, 59)),
            'time_type': 'leave'})

    def _week(self, emps=None, start=None):
        emps = emps or (self.shifty | self.office)
        start = start or self.week_start
        return self.TP._week(emps, start, start + timedelta(days=6))

    def _payload(self, user=None):
        tp = self.TP.with_user(user) if user else self.TP
        return tp._close_payload(self.dept.id, self.week_start.isoformat(), '')

    def _approved(self, emp, day, hours, kind='weekday', bonus=0.0,
                  choice=False):
        """An approved request made the way the bridge suites make one."""
        vals = {'employee_id': emp.id, 'date': day, 'overtime_type': kind,
                'planned_hours': hours + bonus, 'actual_hours': hours + bonus,
                'approved_hours': hours, 'bonus_hours': bonus,
                'reason': 'S5B', 'state': 'approved',
                'company_id': self.company.id}
        if choice:
            vals['pb_comp_choice'] = choice
        return self.OT.sudo().create(vals)
