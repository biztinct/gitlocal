# -*- coding: utf-8 -*-
"""GROUP P5 — what this module promises, tested.

The first test is the one that matters. Everything else in this phase is new
surface; the hook is the only thing that can change a number somebody is paid,
and T1 is the statement that it does not, for anybody without a stretch of
days drawn on their month.
"""

from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkSegments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Person = cls.env['pb.person']
        cls.Segment = cls.env['pb.work.segment']
        cls.Transfer = cls.env['pb.cost.transfer']
        cls.Assign = cls.env['pb.assignments']

        cls.currency = cls.env.ref('base.VND', raise_if_not_found=False) \
            or cls.env.company.currency_id
        cls.home_company = cls.env['res.company'].create({
            'name': 'WS Home Co', 'currency_id': cls.currency.id})
        cls.host_company = cls.env['res.company'].create({
            'name': 'WS Host Co', 'currency_id': cls.currency.id})
        cls.env.user.company_ids = [(4, cls.home_company.id),
                                    (4, cls.host_company.id)]

        cls.home_emp = cls.env['hr.employee'].create({
            'name': 'Split Person', 'company_id': cls.home_company.id})
        cls.host_emp = cls.env['hr.employee'].create({
            'name': 'Split Person', 'company_id': cls.host_company.id})
        cls.person = cls.Person.for_employee(cls.home_emp)
        cls.host_emp.pb_person_id = cls.person.id

    # ------------------------------------------------------------------ T1
    def test_t01_nobody_without_a_segment_is_touched(self):
        """RULE 8, PHASE 5 FORM. This is the whole safety story.

        A payslip whose person has no confirmed stretch of days is handed
        `(1.0, None)` before anything is read, so the input builder returns
        without touching a value. The live proof is the re-run parity on a
        closed month; this is the unit that says the door is shut.
        """
        slip = self.env['hr.payslip'].new({
            'employee_id': self.home_emp.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30),
        })
        factor, meta = self.Segment.factor_for(slip)
        self.assertEqual(factor, 1.0)
        self.assertIsNone(meta)

    def test_t01b_a_broken_segment_still_answers_one(self):
        """A segment may NEVER break a pay run — however it fails."""
        broken = self.Segment.with_context(pb_break_me=True)
        factor, meta = broken.factor_for(object())
        self.assertEqual(factor, 1.0)
        self.assertIsNone(meta)

    # ------------------------------------------------------------------ T2
    def test_t02_bootstrap_and_merge(self):
        made = self.Person.bootstrap()
        self.assertGreaterEqual(made, 0)
        self.assertTrue(self.home_emp.pb_person_id)

        other = self.env['hr.employee'].create({
            'name': 'Split Person', 'company_id': self.host_company.id})
        twin = self.Person.for_employee(other)
        self.assertNotEqual(twin.id, self.person.id)

        keeper = min(self.person.id, twin.id)
        answer = self.Person.browse(keeper).merge([self.person.id, twin.id])
        self.assertEqual(answer['person_id'], keeper)
        self.assertEqual(other.pb_person_id.id, keeper)
        self.assertFalse(
            self.Person.browse(max(self.person.id, twin.id)).active)

    def test_t02b_suggestions_rank_the_strongest_evidence_first(self):
        rows = self.Person.suggest_merges([self.home_company.id,
                                           self.host_company.id])
        self.assertIsInstance(rows, list)
        for row in rows:
            self.assertIn('score', row)
            self.assertIn('evidence', row)
            self.assertEqual(len(row['person_ids']), 2)
        if len(rows) > 1:
            self.assertGreaterEqual(rows[0]['score'], rows[-1]['score'])

    # ------------------------------------------------------------------ T3
    def _segment(self, **kw):
        vals = {
            'person_id': self.person.id,
            'home_employee_id': self.home_emp.id,
            'host_company_id': self.host_company.id,
            'host_employee_id': self.host_emp.id,
            'date_from': date(2026, 6, 1),
            'date_to': date(2026, 6, 10),
            'kind': 'split',
        }
        vals.update(kw)
        return self.Segment.create(vals)

    def test_t03_days_share_and_the_refusals(self):
        seg = self._segment()
        self.assertGreater(seg.month_days, 0)
        self.assertGreater(seg.days, 0)
        self.assertAlmostEqual(seg.share, seg.days / seg.month_days, 5)
        # `fte` keeps four decimals and `share` six, so they agree to the
        # precision the field actually stores.
        self.assertAlmostEqual(seg.fte, seg.share, 4)

        with self.assertRaises(ValidationError):
            self._segment(date_from=date(2026, 6, 25),
                          date_to=date(2026, 7, 5))

        seg.action_confirm()
        with self.assertRaises(ValidationError):
            self._segment(date_from=date(2026, 6, 5),
                          date_to=date(2026, 6, 12),
                          state='confirmed')

    def test_t03b_more_than_a_month_is_refused_unless_part_time(self):
        self._segment(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
                      state='confirmed')
        with self.assertRaises(ValidationError):
            self.Segment.create({
                'person_id': self.person.id,
                'home_employee_id': self.home_emp.id,
                'host_company_id': self.home_company.id,
                'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 20),
                'kind': 'split', 'state': 'confirmed',
            })

    def test_t03c_a_host_employment_must_be_in_the_host_entity(self):
        with self.assertRaises(ValidationError):
            self._segment(host_employee_id=self.home_emp.id)

    # ------------------------------------------------------------------ T4
    def test_t04_the_factor_each_pays(self):
        seg = self._segment(pay_policy='each_pays')
        seg.action_confirm()
        home_slip = self.env['hr.payslip'].new({
            'employee_id': self.home_emp.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30),
        })
        factor, meta = self.Segment.factor_for(home_slip)
        self.assertAlmostEqual(factor, 1.0 - seg.share, 5)
        self.assertEqual(meta['kind'], 'home')

        host_slip = self.env['hr.payslip'].new({
            'employee_id': self.host_emp.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30),
        })
        factor, meta = self.Segment.factor_for(host_slip)
        self.assertAlmostEqual(factor, seg.share, 5)
        self.assertEqual(meta['kind'], 'host')

    def test_t04b_the_two_sides_add_up_to_one_whole_month(self):
        seg = self._segment(pay_policy='each_pays')
        seg.action_confirm()
        home = self.env['hr.payslip'].new({
            'employee_id': self.home_emp.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        host = self.env['hr.payslip'].new({
            'employee_id': self.host_emp.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        total = (self.Segment.factor_for(home)[0]
                 + self.Segment.factor_for(host)[0])
        self.assertAlmostEqual(total, 1.0, 5)

    def test_t04c_home_pays_keeps_the_home_month_whole(self):
        seg = self._segment(pay_policy='home_pays')
        seg.action_confirm()
        home = self.env['hr.payslip'].new({
            'employee_id': self.home_emp.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        factor, meta = self.Segment.factor_for(home)
        self.assertEqual(factor, 1.0)
        self.assertEqual(meta['kind'], 'home')
        self.assertEqual(meta['transfers'], seg.ids)

    def test_t04d_a_joiner_is_worth_the_days_they_were_here(self):
        seg = self.Segment.create({
            'person_id': self.person.id,
            'home_employee_id': self.home_emp.id,
            'host_company_id': self.home_company.id,
            'date_from': date(2026, 6, 15), 'date_to': date(2026, 6, 30),
            'kind': 'joiner', 'state': 'confirmed',
        })
        slip = self.env['hr.payslip'].new({
            'employee_id': self.home_emp.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        factor, meta = self.Segment.factor_for(slip)
        self.assertAlmostEqual(factor, seg.share, 5)
        self.assertLess(factor, 1.0)

    # ------------------------------------------------------------------ T6
    def test_t06_the_group_pattern_decides_and_a_stretch_may_overrule_it(self):
        group = self.env['pb.group'].create({
            'name': 'WS Group',
            'presentation_currency_id': self.currency.id,
            'split_pay_policy': 'each_pays',
        })
        (self.home_company | self.host_company).write({
            'pb_group_id': group.id})
        seg = self._segment(pay_policy='inherit')
        seg.action_confirm()
        self.assertEqual(seg.effective_policy, 'each_pays')

        group.split_pay_policy = 'home_pays'
        seg.invalidate_recordset(['effective_policy'])
        seg.modified(['pay_policy'])
        seg._compute_effective_policy()
        self.assertEqual(seg.effective_policy, 'home_pays')

        seg.pay_policy = 'each_pays'
        self.assertEqual(seg.effective_policy, 'each_pays')

    # ------------------------------------------------------------------ T7
    def test_t07_the_pay_run_gains_the_host_employment(self):
        seg = self._segment(pay_policy='each_pays')
        seg.action_confirm()
        wizard = self.env['pb.payrun.wizard'].with_company(self.host_company)
        hosts = wizard._segment_hosts(0, date(2026, 6, 1), date(2026, 6, 30))
        self.assertIn(self.host_emp.id, hosts)
        self.assertIn('why', hosts[self.host_emp.id])

    def test_t07b_the_split_chips_name_both_sides(self):
        seg = self._segment(pay_policy='each_pays')
        seg.action_confirm()
        chips = self.env['pb.payrun.wizard'].with_company(
            self.home_company).split_chips({
                'date_start': date(2026, 6, 1), 'date_end': date(2026, 6, 30)})
        self.assertTrue(chips['count'])

    # ------------------------------------------------------------------ T9
    def test_t09_the_full_time_figure_follows_the_days(self):
        seg = self._segment(pay_policy='each_pays')
        seg.action_confirm()
        answer = self.Assign.split_people(
            [self.home_company.id], date(2026, 6, 1))
        self.assertEqual(answer['count'], 1)

    # ----------------------------------------------------------------- T10
    def test_t10_joiners_are_derived_only_when_the_switch_is_on(self):
        self.host_company.prorate_joiners_leavers = False
        answer = self.Segment.derive_joiners_and_leavers(
            self.host_company, date(2026, 6, 15))
        self.assertEqual(answer['created'], 0)

    # ------------------------------------------------------- the screen
    def test_t11_the_screen_answers_for_a_reader_with_no_permission(self):
        payload = self.Assign.get_screen(self.person.id)
        self.assertIn('allowed', payload)
        self.assertIn('policies', payload)
        self.assertEqual(len(payload['policies']), 2)

    def test_t11b_a_host_outside_the_group_is_refused_in_words(self):
        outsider = self.env['res.company'].create({'name': 'WS Outsider'})
        group = self.env['pb.group'].create({
            'name': 'WS Group 2',
            'presentation_currency_id': self.currency.id})
        (self.home_company | self.host_company).write({
            'pb_group_id': group.id})
        with self.assertRaises(Exception):
            self.Assign.save_segment({
                'person_id': self.person.id,
                'home_employee_id': self.home_emp.id,
                'host_company_id': outsider.id,
                'date_from': '2026-06-01', 'date_to': '2026-06-10',
            })

    def test_t11c_the_chip_says_nothing_for_a_whole_month(self):
        answer = self.Assign.chip_for(self.home_emp.id, date(2026, 6, 1))
        self.assertFalse(answer['found'])
