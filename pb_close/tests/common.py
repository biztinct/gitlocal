# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Shared fixtures for the P4 suites.

Everything here is created inside the test transaction and rolled back with it —
no suite in this module touches a pre-existing lock, correction, OT request or
punch on the live demo database (T16).
"""

from datetime import date, datetime, time, timedelta

from odoo.tests import TransactionCase


class CloseCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Att = cls.env['hr.attendance']
        cls.Lock = cls.env['pb.wf.lock']
        cls.Corr = cls.env['hr.attendance.correction']
        cls.OT = cls.env['hr.overtime.request']
        cls.Grid = cls.env['hr.attendance.weekentry']
        cls.Rule = cls.env['pb.attendance.rule'].sudo()

        # A settled PAST week so nothing here collides with "today" logic and
        # nothing is scheduled in the future (shift seeding refuses that).
        today = date.today()
        cls.week_start = today - timedelta(days=today.weekday() + 14)
        cls.day = cls.week_start                       # the Monday
        cls.day2 = cls.week_start + timedelta(days=1)  # the Tuesday

        # A deterministic tolerance for the whole suite, and UTC employees so
        # local day == UTC day and every assertion is about the LOCK, not about
        # a timezone.
        cls.Rule.search([]).write({'active': False})
        cls.rule = cls.Rule.create({
            'name': 'P4 test global', 'company_id': False,
            'grace_in_minutes': 15, 'grace_out_minutes': 15,
            'open_checkout_hours': 16,
            'variance_minutes': 10, 'variance_hours_week': 0.5})

        Emp = cls.env['hr.employee']
        cls.emp = Emp.create({'name': 'P4 Punchy', 'company_id': cls.company.id,
                              'tz': 'UTC', 'barcode': 'P4C001'})
        cls.emp2 = Emp.create({'name': 'P4 Steady', 'company_id': cls.company.id,
                               'tz': 'UTC', 'barcode': 'P4C002'})

        cls.tmpl = cls.env['hr.shift.template'].create({
            'name': 'P4 Day', 'code': 'P4DAY', 'start_hour': 8.0,
            'end_hour': 16.0, 'is_overnight': False, 'shift_type': 'morning',
            'company_id': cls.company.id})

    # ------------------------------------------------------------- helpers
    @classmethod
    def _mk_user(cls, login, group_xmlids):
        groups = [cls.env.ref('base.group_user').id]
        for x in group_xmlids:
            groups.append(cls.env.ref(x).id)
        return cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': login, 'login': login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, groups)]})

    def _officer(self, login='p4_officer'):
        return self._mk_user(login, [
            'hr.group_hr_user',
            'hr_attendance.group_hr_attendance_officer'])

    def _manager(self, login='p4_manager'):
        return self._mk_user(login, [
            'hr.group_hr_user',
            'hr_attendance.group_hr_attendance_officer',
            'hr_attendance.group_hr_attendance_manager'])

    def _punch(self, emp=None, day=None, start_h=8, hours=8.0, source='grid'):
        emp = emp or self.emp
        day = day or self.day
        ci = datetime.combine(day, time(start_h, 0))
        return self.Att.create({
            'employee_id': emp.id, 'check_in': ci,
            'check_out': ci + timedelta(hours=hours),
            'pb_entry_source': source or False})

    def _shift(self, emp=None, day=None, start_h=8, end_h=16,
               state='published'):
        emp = emp or self.emp
        day = day or self.day
        return self.env['hr.shift.planning'].create({
            'employee_id': emp.id,
            'shift_template_id': self.tmpl.id,
            'date': day,
            'start_datetime': datetime.combine(day, time(start_h, 0)),
            'end_datetime': datetime.combine(day, time(end_h, 0)),
            'state': state})

    def _lock(self, day=None, company=None, reason='closing the week'):
        """Lock a day AS SUPERUSER — the gate itself is tested separately."""
        day = day or self.day
        cid = (company or self.company).id
        return self.Lock.sudo().lock_day(cid, day, reason)

    def _unlock(self, day=None, company=None, reason='payroll correction'):
        day = day or self.day
        cid = (company or self.company).id
        return self.Lock.sudo().unlock_day(cid, day, reason)
