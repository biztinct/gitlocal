# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""S5-B T11–T14: late and early minutes from real punches, confirmed first
in the weekly Close (owner ruling L5)."""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TimePayCase


@tagged('post_install', '-at_install', 'wdgap_s5b')
class TestLateMinutes(TimePayCase):

    def _late(self, emp):
        _rows, late = self._week()
        return {(r['date'], r['kind']): r for r in late
                if r['employee_id'] == emp.id}

    def _row(self, payload, emp, kind='late'):
        return [r for r in payload['late']
                if r['employee_id'] == emp.id and r['kind'] == kind][0]

    # ------------------------------------------------------------ the maths
    def test_t11_grace_minutes_late_and_early(self):
        """15 minutes' grace each way: 14 late is on time, 16 late is 16
        minutes late; out at 15:44 is 16 minutes early, at 15:46 it is not."""
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8 + 14 / 60.0, 16)
        self._shift(self.shifty, self.tue)
        self._punch(self.shifty, self.tue, 8 + 16 / 60.0, 15 + 44 / 60.0)
        self._shift(self.shifty, self.wed)
        self._punch(self.shifty, self.wed, 8, 15 + 46 / 60.0)
        got = self._late(self.shifty)
        self.assertNotIn((self.mon.isoformat(), 'late'), got)
        self.assertEqual(got[(self.tue.isoformat(), 'late')]['minutes'], 16)
        self.assertEqual(got[(self.tue.isoformat(), 'early')]['minutes'], 16)
        self.assertNotIn((self.wed.isoformat(), 'early'), got)

    def test_t12_no_shift_compares_with_working_hours(self):
        self._punch(self.office, self.mon, 8.5, 17)
        row = self._late(self.office)[(self.mon.isoformat(), 'late')]
        self.assertEqual(row['minutes'], 30)
        self.assertEqual(row['basis'], 'hours')

    def test_t12b_an_open_punch_has_no_early_leave_yet(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8.5, None)
        got = self._late(self.shifty)
        self.assertEqual(got[(self.mon.isoformat(), 'late')]['minutes'], 30)
        self.assertNotIn((self.mon.isoformat(), 'early'), got)

    # ------------------------------------------------------ the decisions
    def test_t13_confirm_and_excuse(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8.5, 15.5)
        payload = self._payload(self.manager_user)
        late = self._row(payload, self.shifty, 'late')
        early = self._row(payload, self.shifty, 'early')
        self.assertEqual(late['state'], 'open')
        self.assertEqual(payload['late_stats']['open'], 2)
        TP = self.TP.with_user(self.manager_user)
        ctx = (self.dept.id, self.week_start.isoformat(), '')
        res = TP.decide_late([late['key']], 'confirmed', False, *ctx)
        self.assertEqual(res['decided'], 1, res)
        res = TP.decide_late([early['key']], 'excused', 'bus strike', *ctx)
        self.assertEqual(res['decided'], 1, res)
        rows = self.Late.sudo().search([('employee_id', '=', self.shifty.id)])
        self.assertEqual(sorted(rows.mapped('state')), ['confirmed', 'excused'])
        self.assertEqual(rows.filtered(lambda r: r.kind == 'late').minutes, 30)
        self.assertEqual(rows.filtered(lambda r: r.kind == 'early').note,
                         'bus strike')
        payload = self._payload(self.manager_user)
        self.assertEqual(payload['late_stats']['open'], 0)
        self.assertEqual(payload['late_stats']['minutes_confirmed'], 30)

    def test_t13b_changed_punches_ask_again(self):
        self._shift(self.shifty, self.mon)
        att = self._punch(self.shifty, self.mon, 8.5, 16)
        payload = self._payload(self.manager_user)
        key = self._row(payload, self.shifty)['key']
        self.TP.with_user(self.manager_user).decide_late(
            [key], 'confirmed', False, self.dept.id,
            self.week_start.isoformat(), '')
        att.sudo().write({'check_in': att.check_in.replace(minute=50)})
        row = self._row(self._payload(self.manager_user), self.shifty)
        self.assertTrue(row['changed'])
        self.assertEqual((row['minutes'], row['decided_minutes']), (50, 30))
        self.assertEqual(self._payload(self.manager_user)['late_stats']['open'], 1)

    def test_t13c_own_and_locked_are_refused(self):
        self._shift(self.boss, self.mon)
        self._punch(self.boss, self.mon, 8.5, 16)
        self._shift(self.shifty, self.tue)
        self._punch(self.shifty, self.tue, 8.5, 16)
        self.env['pb.wf.lock'].sudo().lock_day(self.company.id, self.tue,
                                               'closing')
        payload = self._payload(self.manager_user)
        own = self._row(payload, self.boss)
        locked = self._row(payload, self.shifty)
        res = self.TP.with_user(self.manager_user).decide_late(
            [own['key'], locked['key']], 'excused', False, self.dept.id,
            self.week_start.isoformat(), '')
        self.assertEqual(res['decided'], 0)
        self.assertEqual(len(res['skipped']), 2, res)
        self.assertFalse(self.Late.sudo().search(
            [('employee_id', 'in', (self.boss | self.shifty).ids)]))

    def test_t13d_a_paid_decision_stays(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8.5, 16)
        row = self.Late.sudo().create({
            'employee_id': self.shifty.id, 'company_id': self.company.id,
            'date': self.mon, 'kind': 'late', 'minutes': 30,
            'state': 'confirmed'})
        slip = self.env['hr.payslip'].sudo().create({
            'employee_id': self.shifty.id, 'date_from': self.mon,
            'date_to': self.mon})
        row.write({'payslip_id': slip.id})
        slip.sudo().write({'state': 'done'})
        row.invalidate_recordset()
        self.assertEqual(row.pay_state, 'paid')
        with self.assertRaises(UserError):
            row.write({'state': 'excused'})
        with self.assertRaises(UserError):
            row.unlink()

    # --------------------------------------------------------- the lock gate
    def test_t14_minutes_hold_the_week_only_once_mapped_into_pay(self):
        self._shift(self.shifty, self.mon)
        self._shift(self.shifty, self.tue)
        self._punch(self.shifty, self.mon, 8, 16)
        self._punch(self.shifty, self.tue, 8, 16)
        self._shift(self.office, self.mon)
        self._punch(self.office, self.mon, 8.5, 16)
        data = self.Close.with_user(self.manager_user).get_close_data(
            department_id=self.dept.id, week_start=self.week_start.isoformat())
        self.assertIn('time_pay', data)
        self.assertFalse(data['time_pay']['late_in_pay'])
        self.assertNotIn('late_minutes', [c['key'] for c in data['checklist']])

        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'S5B late scheme', 'code': 'S5BLATE', 'country_code': 'VN',
            'company_id': self.company.id})
        self.env['hr.formula.rule'].sudo().create({
            'config_id': cfg.id, 'name': 'Late minutes', 'code': 'LATEMIN',
            'column_type': 'input'})
        data = self.Close.with_user(self.manager_user).get_close_data(
            department_id=self.dept.id, week_start=self.week_start.isoformat())
        self.assertTrue(data['time_pay']['late_in_pay'])
        self.assertFalse(data['can_lock'])
        chk = [c for c in data['checklist'] if c['key'] == 'late_minutes'][0]
        self.assertFalse(chk['done'])

        self.assertEqual(data['time_pay']['late_stats']['open'], 1)
        key = self._row(data['time_pay'], self.office)['key']
        self.TP.with_user(self.manager_user).decide_late(
            [key], 'confirmed', False, self.dept.id,
            self.week_start.isoformat(), '')
        data = self.Close.with_user(self.manager_user).get_close_data(
            department_id=self.dept.id, week_start=self.week_start.isoformat())
        chk = [c for c in data['checklist'] if c['key'] == 'late_minutes'][0]
        self.assertTrue(chk['done'])

    def test_t14b_open_minutes_disable_the_lock_on_a_clean_board(self):
        """On a board that is otherwise clean, open minutes (once mapped)
        are the one thing between the manager and the lock."""
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 16)
        Close = self.Close.with_user(self.manager_user)
        data = Close.get_close_data(department_id=self.dept.id,
                                    week_start=self.week_start.isoformat())
        self.assertTrue(data['can_lock'], data['checklist'])
        fake = dict(data['time_pay'], late_in_pay=True,
                    late_stats=dict(data['time_pay']['late_stats'], open=2))
        with patch.object(type(self.TP), '_close_payload',
                          lambda *a, **k: fake):
            data = Close.get_close_data(department_id=self.dept.id,
                                        week_start=self.week_start.isoformat())
        self.assertFalse(data['can_lock'])
        self.assertIn('2 late or early minute row(s)',
                      [c for c in data['checklist']
                       if c['key'] == 'late_minutes'][0]['label'])
