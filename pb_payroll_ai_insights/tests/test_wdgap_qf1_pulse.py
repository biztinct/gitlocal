# -*- coding: utf-8 -*-
"""WDGAP QF1 — PayAI's daily alerts belong to a company, there is one open
alert per thing, and Home reads them through `home_alerts` (cases 11-13).

The cost detector is driven with real payslips (lines and all) in two fresh
companies, so what is proved is the detector's own company filter, not a
stub of it.
"""
import json

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import payai_group_ids


@tagged('post_install', '-at_install', 'wdgap_qf1')
class TestWdgapQf1Pulse(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Pulse = cls.env['payroll.ai.pulse']
        cls.co_a = cls.env['res.company'].create({'name': 'QF1 Alpha'})
        cls.co_b = cls.env['res.company'].create({'name': 'QF1 Beta'})
        cls.env.user.write({'company_ids': [(4, cls.co_a.id), (4, cls.co_b.id)]})
        cls.rule = cls.env['hr.salary.rule'].search([], limit=1)
        cls.category = cls.env['hr.salary.rule.category'].search([], limit=1)
        cls.month_start = fields.Date.today().replace(day=1)
        groups = [cls.env.ref('base.group_user').id,
                  cls.env.ref('om_hr_payroll.group_hr_payroll_manager').id] \
            + payai_group_ids(cls.env)
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.reader_a = Users.create({
            'name': 'QF1 reader A', 'login': 'qf1.reader.a@test.invalid',
            'company_id': cls.co_a.id, 'company_ids': [(6, 0, [cls.co_a.id])],
            'group_ids': [(6, 0, groups)]})
        cls.reader_b = Users.create({
            'name': 'QF1 reader B', 'login': 'qf1.reader.b@test.invalid',
            'company_id': cls.co_b.id, 'company_ids': [(6, 0, [cls.co_b.id])],
            'group_ids': [(6, 0, groups)]})
        cls.plain_a = Users.create({
            'name': 'QF1 plain A', 'login': 'qf1.plain.a@test.invalid',
            'company_id': cls.co_a.id, 'company_ids': [(6, 0, [cls.co_a.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id]
                          + payai_group_ids(cls.env))]})

    # ------------------------------------------------------------ fixtures
    def _person(self, company, name):
        emp = self.env['hr.employee'].create(
            {'name': name, 'company_id': company.id})
        contract = self.env['hr.contract'].create({
            'name': '%s contract' % name, 'employee_id': emp.id,
            'wage': 1000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': company.id})
        return emp, contract

    def _slip(self, company, emp, contract, month_first, amount):
        if not (self.rule and self.category):
            self.skipTest('no salary rule on this database to hang lines off')
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': 'QF1 slip %s' % emp.name,
            'contract_id': contract.id, 'company_id': company.id,
            'date_from': month_first,
            'date_to': month_first + relativedelta(months=1, days=-1)})
        self.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'name': 'Basic', 'code': 'QF1BASIC',
            'amount': amount, 'quantity': 1.0, 'rate': 100.0,
            'employee_id': emp.id, 'contract_id': contract.id,
            'category_id': self.category.id, 'salary_rule_id': self.rule.id})
        self.env.flush_all()
        self.env.cr.execute("UPDATE hr_payslip SET state = 'done' WHERE id = %s",
                            (slip.id,))
        self.env.invalidate_all()
        return slip

    def _amount(self, slip, value):
        self.env['hr.payslip.line'].sudo().search(
            [('slip_id', '=', slip.id)]).write({'amount': value})
        self.env.flush_all()

    def _history(self, company, current):
        """Three months at 1,000 each, then this month at `current`."""
        emp, contract = self._person(company, 'QF1 %s worker' % company.name)
        for back in (1, 2, 3):
            self._slip(company, emp, contract,
                       self.month_start - relativedelta(months=back), 1000.0)
        slip = self._slip(company, emp, contract, self.month_start, current)
        return emp, contract, slip

    def _open(self, company, category='cost'):
        return self.Pulse.sudo().search([
            ('company_id', '=', company.id), ('category', '=', category),
            ('state', 'in', ('new', 'acknowledged'))])

    # ------------------------------------------------------------ case 11
    def test_11_an_alert_belongs_to_the_company_it_is_about(self):
        self._history(self.co_a, 1500.0)     # +50 %: critical
        self._history(self.co_b, 1000.0)     # flat: nothing
        self.Pulse.sudo().run_anomaly_detection()
        mine = self._open(self.co_a)
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine.severity, 'critical')
        self.assertEqual(mine.direction, 'up')
        self.assertAlmostEqual(mine.deviation_pct, 50.0)
        self.assertEqual(mine.dedupe_key, '%s:cost:none' % self.co_a.id)
        self.assertFalse(self._open(self.co_b))

        # Beta's reader sees none of it — not on Home, not by searching
        got_b = self.Pulse.with_user(self.reader_b).with_context(
            allowed_company_ids=[self.co_b.id]).home_alerts()
        self.assertFalse([a for a in got_b if a['id'] == mine.id])
        self.assertFalse(self.Pulse.with_user(self.reader_b).with_context(
            allowed_company_ids=[self.co_b.id]).search([('id', '=', mine.id)]))
        got_a = self.Pulse.with_user(self.reader_a).with_context(
            allowed_company_ids=[self.co_a.id]).home_alerts()
        self.assertEqual([a['id'] for a in got_a], [mine.id])
        # whoever may not open a payslip gets nothing
        if not self.env['hr.payslip'].with_user(self.plain_a).has_access('read'):
            self.assertEqual(self.Pulse.with_user(self.plain_a).with_context(
                allowed_company_ids=[self.co_a.id]).home_alerts(), [])

    # ------------------------------------------------------------ case 12
    def test_12_one_open_alert_per_thing(self):
        emp, contract, slip = self._history(self.co_a, 1200.0)  # +20 %
        Pulse = self.Pulse.sudo()
        Pulse.run_anomaly_detection()
        first = self._open(self.co_a)
        self.assertEqual(len(first), 1)
        self.assertEqual(first.severity, 'warning')
        Pulse.run_anomaly_detection()
        self.assertEqual(self._open(self.co_a), first, 'a second alert was made')

        # the figures move: the same alert is updated
        self._amount(slip, 1220.0)
        Pulse.run_anomaly_detection()
        again = self._open(self.co_a)
        self.assertEqual(again, first)
        self.assertAlmostEqual(again.deviation_pct, 22.0)

        # "Got it": hidden from Home while it stays the same
        reader = self.Pulse.with_user(self.reader_a).with_context(
            allowed_company_ids=[self.co_a.id])
        self.assertTrue(reader.rpc_acknowledge_alert(first.id))
        first.invalidate_recordset()
        self.assertEqual(first.state, 'acknowledged')
        self.assertAlmostEqual(first.ack_level, 22.0)
        self.assertFalse(reader.home_alerts())
        # 3 points worse: still hidden
        self._amount(slip, 1250.0)
        Pulse.run_anomaly_detection()
        self.assertEqual(self._open(self.co_a).state, 'acknowledged')
        self.assertFalse(reader.home_alerts())
        # 5 points worse than when it was put away: back on Home
        self._amount(slip, 1270.0)
        Pulse.run_anomaly_detection()
        back = self._open(self.co_a)
        self.assertEqual(back, first)
        self.assertEqual(back.state, 'new')
        self.assertEqual([a['id'] for a in reader.home_alerts()], [first.id])

        # severity rising brings it back even under 5 points: put away at
        # 24 % (a warning), then 26 % (critical) — 2 points, one level up
        back.write({'deviation_pct': 24.0, 'severity': 'warning'})
        back.action_acknowledge()
        self.assertEqual(back.ack_severity, 'warning')
        seen = set()
        Pulse._raise_alert(self.co_a, {
            'name': 'x', 'category': 'cost', 'severity': 'warning',
            'direction': 'up', 'deviation_pct': 25.0, 'metric_value': 1.0,
            'baseline_value': 1.0}, seen)
        back.invalidate_recordset()
        self.assertEqual(back.state, 'acknowledged')
        Pulse._raise_alert(self.co_a, {
            'name': 'x', 'category': 'cost', 'severity': 'critical',
            'direction': 'up', 'deviation_pct': 26.0, 'metric_value': 1.0,
            'baseline_value': 1.0}, seen)
        back.invalidate_recordset()
        self.assertEqual(back.state, 'new')

        # the condition goes away: resolved on the next run
        self._amount(slip, 1000.0)
        Pulse.run_anomaly_detection()
        back.invalidate_recordset()
        self.assertEqual(back.state, 'resolved')
        self.assertFalse(self._open(self.co_a))

    def test_12b_old_rows_are_left_alone(self):
        old = self.Pulse.sudo().create({
            'name': 'Old row', 'category': 'cost', 'severity': 'critical',
            'state': 'new'})
        self.Pulse.sudo().run_anomaly_detection()
        old.invalidate_recordset()
        self.assertEqual(old.state, 'new')
        self.assertFalse(old.company_id)

    # ------------------------------------------------------------ case 13
    def test_13_home_reads_the_worst_first_and_no_names(self):
        Pulse = self.Pulse.sudo()
        make = lambda sev, cat, key, **kw: Pulse.create(dict({  # noqa: E731
            'name': 'Ana Nguyen and Binh Tran joined', 'severity': sev,
            'category': cat, 'state': 'new', 'company_id': self.co_a.id,
            'dedupe_key': '%s:%s' % (self.co_a.id, key),
            'details': json.dumps({'new_employees': [{'name': 'Ana Nguyen'}]}),
            'summary': 'Ana Nguyen joined', 'metric_value': 4.0}, **kw))
        info = make('info', 'headcount', 'headcount.joined:none',
                    direction='joined')
        warn = make('warning', 'leave', 'leave:none', direction='approved')
        crit = make('critical', 'cost', 'cost:none', direction='up',
                    deviation_pct=31.0)
        crit2 = make('critical', 'overtime', 'overtime:none', direction='up',
                     deviation_pct=40.0)
        Pulse.create({'name': 'Old', 'severity': 'critical', 'category': 'cost',
                      'state': 'new'})
        make('critical', 'cost', 'x:done', state='resolved')
        make('critical', 'cost', 'x:ack', state='acknowledged')
        got = self.Pulse.with_user(self.reader_a).with_context(
            allowed_company_ids=[self.co_a.id]).home_alerts()
        self.assertEqual(len(got), 3)
        self.assertEqual([a['severity'] for a in got],
                         ['critical', 'critical', 'warning'])
        self.assertEqual({a['id'] for a in got[:2]}, {crit.id, crit2.id})
        self.assertEqual(got[2]['id'], warn.id)
        self.assertNotIn(info.id, [a['id'] for a in got])
        for row in got:
            self.assertEqual(set(row), {'id', 'category', 'severity', 'direction',
                                        'pct', 'value', 'baseline',
                                        'department', 'since'})
            self.assertNotIn('Ana', json.dumps(row))
        self.assertEqual(
            len(self.Pulse.with_user(self.reader_a).with_context(
                allowed_company_ids=[self.co_a.id]).home_alerts(10)), 4)
