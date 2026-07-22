# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for the Weekly Entry grid API (``hr.attendance.weekentry``).

Covers Phase-B handover §6 cases 1–6, 9 and the post-implementation review
fixes committed in 60398d54:
  * F2  — reads and writes live in ONE permission world (sudo both sides), so a
          plain officer sees every employee's cells/ceilings, not just their own.
  * F5  — the stale-token check is unconditional: an empty/omitted token no
          longer bypasses it.
  * F6  — a REFUSED OT request renders locked and refuses a grid edit.
  * F7  — ``_save_ot`` re-validates config applicability server-side (weekend OT
          on a Tuesday is rejected even from a crafted RPC).
  * F8  — OT ceilings resolve caps PER EMPLOYEE COMPANY, not the first row's.
"""

from datetime import date, datetime, time, timedelta

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWeekEntry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WE = cls.env['hr.attendance.weekentry']
        cls.company = cls.env.company

        # a fixed, weekday-anchored test week (offsets are computed from the
        # Monday so the assertions never depend on what day 2026-07-20 is)
        anchor = date(2026, 7, 20)
        cls.monday = anchor - timedelta(days=anchor.weekday())
        cls.tue = cls.monday + timedelta(days=1)
        cls.sat = cls.monday + timedelta(days=5)

        cls.cal = cls.env['resource.calendar'].create({
            'name': 'VN Test Calendar',
            'tz': 'Asia/Ho_Chi_Minh',
        })

        # OT configs: day-flags unset → natural-default applicability
        # (weekday = Mon–Fri, weekend = Sat/Sun, night = any day).
        Cfg = cls.env['hr.overtime.config']
        cls.cfg_weekday = Cfg.create({
            'name': 'WD OT', 'overtime_type': 'weekday',
            'rate_multiplier': 1.5, 'sequence': 1, 'country_id': False,
        })
        cls.cfg_weekend = Cfg.create({
            'name': 'WE OT', 'overtime_type': 'weekend',
            'rate_multiplier': 2.0, 'sequence': 1, 'country_id': False,
        })
        cls.cfg_night = Cfg.create({
            'name': 'NIGHT OT', 'overtime_type': 'night',
            'rate_multiplier': 1.3, 'sequence': 1, 'country_id': False,
        })

        # company ceiling (company-specific wins over any seed global row)
        cls.env['pb.ot.ceiling'].create({
            'name': 'Main Ceilings', 'company_id': cls.company.id,
            'monthly_cap': 40.0, 'annual_cap': 200.0, 'annual_cap_special': 300.0,
        })

        # data employees — NOT linked to the officer user (proves the sudo reads)
        Emp = cls.env['hr.employee']
        cls.emp1 = Emp.create({
            'name': 'Trang Nguyen', 'company_id': cls.company.id,
            'resource_calendar_id': cls.cal.id,
        })
        cls.emp2 = Emp.create({
            'name': 'Binh Le', 'company_id': cls.company.id,
            'resource_calendar_id': cls.cal.id,
        })

        # users: officer (own-only OT rule), manager (all-OT rule), plain
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_officer = cls.env.ref('hr_attendance.group_hr_attendance_officer')
        g_manager = cls.env.ref('hr_attendance.group_hr_attendance_manager')
        g_hr_user = cls.env.ref('hr.group_hr_user')
        g_pay_user = cls.env.ref('om_hr_payroll.group_hr_payroll_user')
        cls.officer = Users.create({
            'name': 'Officer', 'login': 'we_officer',
            'group_ids': [(6, 0, [g_officer.id, g_hr_user.id])],
        })
        cls.manager = Users.create({
            'name': 'Manager', 'login': 'we_manager',
            'group_ids': [(6, 0, [g_manager.id, g_hr_user.id])],
        })
        cls.plain = Users.create({
            'name': 'Plain', 'login': 'we_plain',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        # payroll user that is an attendance OFFICER (own-only OT) but can read
        # payslips — for the bridge-parallel F1 assertion here on the OT rule.
        cls.pay_officer = Users.create({
            'name': 'Pay Officer', 'login': 'we_pay_officer',
            'group_ids': [(6, 0, [g_officer.id, g_hr_user.id, g_pay_user.id])],
        })

    # ------------------------------------------------------------ helpers
    def _cell(self, emp, d, measure, value, token=None):
        c = {'rowId': emp.id, 'dayISO': d.isoformat(), 'measure': measure,
             'value': value}
        if token is not None:
            c['token'] = token
        return c

    def _save(self, cells, user=None):
        we = self.WE.with_user(user) if user else self.WE
        return we.save_week_entries({'cells': cells})['results']

    def _att(self, emp, d):
        return self.env['hr.attendance'].search([
            ('employee_id', '=', emp.id),
            ('check_in', '>=', datetime.combine(d, time.min)),
            ('check_in', '<=', datetime.combine(d, time.max)),
        ])

    def _ot(self, emp, d, ot_type):
        return self.env['hr.overtime.request'].search([
            ('employee_id', '=', emp.id), ('date', '=', d),
            ('overtime_type', '=', ot_type)], limit=1)

    # --------------------------------------------------------- §6.1 REG create
    def test_01_reg_create_no_shift_local_0800(self):
        """No attendance, no shift → 08:00 employee-local (01:00 UTC for ICT)."""
        res = self._save([self._cell(self.emp1, self.tue, 'reg', 8, token='')])
        self.assertTrue(res[0]['ok'], res)
        att = self._att(self.emp1, self.tue)
        self.assertEqual(len(att), 1)
        self.assertEqual(att.check_in.hour, 1)  # 08:00 Asia/Ho_Chi_Minh = 01:00 UTC
        span = (att.check_out - att.check_in).total_seconds() / 3600.0
        self.assertAlmostEqual(span, 8.0, places=5)
        self.assertEqual(att.pb_entry_source, 'grid')

    def test_02_reg_create_uses_published_shift_start(self):
        """A published shift anchors check-in at the shift start_datetime."""
        tmpl = self.env['hr.shift.template'].create({
            'name': 'Day', 'code': 'DAY', 'start_hour': 7.67, 'end_hour': 16.0,
            'shift_type': 'morning',
        })
        start = datetime.combine(self.tue, time(7, 40))
        self.env['hr.shift.planning'].create({
            'employee_id': self.emp2.id, 'shift_template_id': tmpl.id,
            'date': self.tue, 'start_datetime': start,
            'end_datetime': start + timedelta(hours=8), 'state': 'published',
        })
        res = self._save([self._cell(self.emp2, self.tue, 'reg', 8, token='')])
        self.assertTrue(res[0]['ok'], res)
        att = self._att(self.emp2, self.tue)
        self.assertEqual(att.check_in, start)
        self.assertEqual(att.check_out, start + timedelta(hours=8))

    # --------------------------------------------------------- §6.2 REG adjust
    def test_03_reg_adjust_and_multi(self):
        ci = datetime.combine(self.tue, time(1, 0))  # 08:00 ICT
        att = self.env['hr.attendance'].create({
            'employee_id': self.emp1.id, 'check_in': ci,
            'check_out': ci + timedelta(hours=4), 'pb_entry_source': 'grid',
        })
        token = self.WE._att_token(att)
        res = self._save([self._cell(self.emp1, self.tue, 'reg', 9, token=token)])
        self.assertTrue(res[0]['ok'], res)
        self.assertEqual(att.check_out, ci + timedelta(hours=9))

        # a second record on the same day makes the cell un-editable (multi)
        self.env['hr.attendance'].create({
            'employee_id': self.emp1.id, 'check_in': ci + timedelta(hours=10),
            'check_out': ci + timedelta(hours=12), 'pb_entry_source': 'grid',
        })
        both = self._att(self.emp1, self.tue)
        res = self._save([self._cell(self.emp1, self.tue, 'reg', 5,
                                     token=self.WE._att_token(both))])
        self.assertFalse(res[0]['ok'])
        self.assertEqual(res[0]['error'], 'multi')

    # ---------------------------------------------------------- §6.3 zero-hours
    def test_04_zero_hours_grid_unlink_kiosk_refused(self):
        ci = datetime.combine(self.tue, time(1, 0))
        grid_att = self.env['hr.attendance'].create({
            'employee_id': self.emp1.id, 'check_in': ci,
            'check_out': ci + timedelta(hours=8), 'pb_entry_source': 'grid',
        })
        res = self._save([self._cell(self.emp1, self.tue, 'reg', 0,
                                     token=self.WE._att_token(grid_att))])
        self.assertTrue(res[0]['ok'], res)
        self.assertFalse(grid_att.exists())

        # a kiosk/device punch (blank source) is never destroyed by the grid
        kiosk = self.env['hr.attendance'].create({
            'employee_id': self.emp2.id, 'check_in': ci,
            'check_out': ci + timedelta(hours=8),
        })
        res = self._save([self._cell(self.emp2, self.tue, 'reg', 0,
                                     token=self.WE._att_token(kiosk))])
        self.assertFalse(res[0]['ok'])
        self.assertEqual(res[0]['error'], 'notgrid')
        self.assertTrue(kiosk.exists())

    # ------------------------------------------------------------- §6.4 OT upsert
    def test_05_ot_upsert_then_locked(self):
        res = self._save([self._cell(self.emp1, self.tue, 'weekday', 3)])
        self.assertTrue(res[0]['ok'], res)
        req = self._ot(self.emp1, self.tue, 'weekday')
        self.assertEqual(req.state, 'draft')
        self.assertAlmostEqual(req.actual_hours, 3.0)

        # editing the draft updates it in place — no duplicate request
        res = self._save([self._cell(self.emp1, self.tue, 'weekday', 5)])
        self.assertTrue(res[0]['ok'], res)
        self.assertEqual(len(self.env['hr.overtime.request'].search([
            ('employee_id', '=', self.emp1.id), ('date', '=', self.tue),
            ('overtime_type', '=', 'weekday')])), 1)
        self.assertAlmostEqual(req.actual_hours, 5.0)

        # once submitted the cell is locked server-side
        req.action_submit()
        res = self._save([self._cell(self.emp1, self.tue, 'weekday', 6)])
        self.assertFalse(res[0]['ok'])
        self.assertEqual(res[0]['error'], 'locked')

    # ------------------------------------------------ §6.5 submit / approve flow
    def test_06_submit_week_and_approve(self):
        self._save([self._cell(self.emp1, self.tue, 'weekday', 4)])
        req = self._ot(self.emp1, self.tue, 'weekday')
        self.assertEqual(req.state, 'draft')

        out = self.WE.with_user(self.officer).submit_week(self.monday.isoformat())
        self.assertEqual(out['submitted'], 1)
        self.assertEqual(req.state, 'submitted')

        out = self.WE.with_user(self.manager).approve_requests([req.id])
        self.assertEqual(out['approved'], 1)
        self.assertEqual(req.state, 'approved')
        self.assertAlmostEqual(req.approved_hours, 4.0)

    # ------------------------------------------------------------- §6.6 ceilings
    def test_07_ceilings_mtd_and_special_sector(self):
        ref = date(self.monday.year, self.monday.month, 15)
        # 38 h approved weekday OT within the reference month
        for i, hrs in enumerate((20.0, 18.0)):
            self.env['hr.overtime.request'].create({
                'employee_id': self.emp1.id,
                'date': date(ref.year, ref.month, 3 + i),
                'overtime_type': 'weekday', 'planned_hours': hrs,
                'approved_hours': hrs, 'reason': 'x', 'state': 'approved',
            })
        out = self.WE.get_ot_ceilings([self.emp1.id], ref.isoformat())
        self.assertAlmostEqual(out[self.emp1.id]['mtd'], 38.0)
        self.assertEqual(out[self.emp1.id]['cap_month'], 40.0)

        # special-sector employee → higher annual cap
        self.emp2.pb_ot_special_sector = True
        out = self.WE.get_ot_ceilings([self.emp2.id], ref.isoformat())
        self.assertEqual(out[self.emp2.id]['cap_year'], 300.0)

    # ---------------------------------------------------------- §6.9 / F5 stale
    def test_08_stale_isolates_one_cell(self):
        ci = datetime.combine(self.tue, time(1, 0))
        att = self.env['hr.attendance'].create({
            'employee_id': self.emp1.id, 'check_in': ci,
            'check_out': ci + timedelta(hours=8), 'pb_entry_source': 'grid',
        })
        stale_cell = self._cell(self.emp1, self.tue, 'reg', 6,
                                token=self.WE._att_token(att) + 'STALE')
        good_cell = self._cell(self.emp2, self.tue, 'reg', 7, token='')
        res = self._save([stale_cell, good_cell])
        by_row = {r['rowId']: r for r in res}
        self.assertEqual(by_row[self.emp1.id]['error'], 'stale')
        self.assertTrue(by_row[self.emp2.id]['ok'])
        self.assertEqual(len(self._att(self.emp2, self.tue)), 1)

    def test_09_empty_token_no_longer_bypasses(self):
        """F5: a record exists now but the cell sends no token → still stale."""
        ci = datetime.combine(self.tue, time(1, 0))
        self.env['hr.attendance'].create({
            'employee_id': self.emp1.id, 'check_in': ci,
            'check_out': ci + timedelta(hours=8), 'pb_entry_source': 'grid',
        })
        # omit the token entirely (cell had no record at fetch time)
        res = self._save([self._cell(self.emp1, self.tue, 'reg', 6)])
        self.assertFalse(res[0]['ok'])
        self.assertEqual(res[0]['error'], 'stale')

    # ------------------------------------------------------ F7 OT applicability
    def test_10_weekend_ot_on_weekday_rejected(self):
        res = self._save([self._cell(self.emp1, self.tue, 'weekend', 4)])
        self.assertFalse(res[0]['ok'])
        self.assertEqual(res[0]['error'], 'notapplicable')
        # …and it IS accepted on an actual Saturday
        res = self._save([self._cell(self.emp1, self.sat, 'weekend', 4)])
        self.assertTrue(res[0]['ok'], res)

    # ------------------------------------------------------------- F6 refused
    def test_11_refused_request_locked_read_and_write(self):
        req = self.env['hr.overtime.request'].create({
            'employee_id': self.emp1.id, 'date': self.tue,
            'overtime_type': 'weekday', 'planned_hours': 3.0,
            'reason': 'x', 'state': 'submitted',
        })
        req.action_refuse()
        self.assertEqual(req.state, 'refused')

        # read side: the cell is locked (not editable) with state refused
        data = self.WE.with_user(self.officer).get_week_entries(
            self.monday.isoformat())
        row = next(r for r in data['rows'] if r['id'] == self.emp1.id)
        meas = row['cells'][self.tue.isoformat()]['measures']['weekday']
        self.assertEqual(meas['state'], 'refused')
        self.assertFalse(meas['editable'])

        # write side: a crafted edit on the refused cell is refused
        res = self._save([self._cell(self.emp1, self.tue, 'weekday', 7)])
        self.assertFalse(res[0]['ok'])
        self.assertEqual(res[0]['error'], 'locked')

    # ------------------------------------------------- F8 per-company ceilings
    def test_12_ceilings_resolved_per_employee_company(self):
        company_b = self.env['res.company'].create({'name': 'VN Branch B'})
        self.env['pb.ot.ceiling'].create({
            'name': 'B Ceilings', 'company_id': company_b.id,
            'monthly_cap': 20.0, 'annual_cap': 120.0, 'annual_cap_special': 180.0,
        })
        emp_b = self.env['hr.employee'].create({
            'name': 'Branch B Worker', 'company_id': company_b.id,
        })
        out = self.WE.get_ot_ceilings([self.emp1.id, emp_b.id])
        self.assertEqual(out[self.emp1.id]['cap_month'], 40.0)
        self.assertEqual(out[emp_b.id]['cap_month'], 20.0)

    # ---------------------------------------- F2 one permission world (reads)
    def test_13_officer_sees_other_employees_data(self):
        """The officer owns no OT here; sudo reads must still surface it."""
        self.env['hr.overtime.request'].create({
            'employee_id': self.emp1.id, 'date': self.tue,
            'overtime_type': 'weekday', 'planned_hours': 5.0,
            'approved_hours': 5.0, 'reason': 'x', 'state': 'approved',
        })
        # a plain non-sudo read as the officer sees nothing (own-only rule)…
        seen = self.env['hr.overtime.request'].with_user(self.officer).search([
            ('employee_id', '=', self.emp1.id)])
        self.assertFalse(seen)
        # …but the cockpit payload (sudo reads) surfaces the value + lock
        data = self.WE.with_user(self.officer).get_week_entries(
            self.monday.isoformat())
        row = next(r for r in data['rows'] if r['id'] == self.emp1.id)
        meas = row['cells'][self.tue.isoformat()]['measures']['weekday']
        self.assertAlmostEqual(meas['value'], 5.0)
        self.assertFalse(meas['editable'])
        self.assertGreater(data['ceilings'][self.emp1.id]['ytd'], 0.0)

    # -------------------------------------------------------- access gating
    def test_14_plain_user_denied(self):
        with self.assertRaises(AccessError):
            self.WE.with_user(self.plain).get_week_entries(self.monday.isoformat())
        with self.assertRaises(AccessError):
            self.WE.with_user(self.plain).get_ot_ceilings([self.emp1.id])
