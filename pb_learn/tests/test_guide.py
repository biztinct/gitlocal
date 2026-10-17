# -*- coding: utf-8 -*-
"""LEARNREV P1 — the Guide, end to end (handover §6 T2, T3, T4, T6, T7).

One fixture scheme with four components, the smallest board that shows every
state the "Right now" list can name: a component nobody has answered yet, an
hours component wrongly set to add to net pay, and two that are fine.
Component codes are underscore-free and not substrings of one another (the
formula converter's contract).
"""
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .test_guide_truth import load_vi

OFFICER = 'pb_hr_payroll_base.group_payroll_base_officer'


@tagged('post_install', '-at_install', 'learnrev')
class TestGuide(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_formula = 'hr.formula.config' in cls.env
        if not cls.has_formula:
            return
        load_vi(cls.env, {'pb_hr_payroll_formula', 'pb_formula_studio', 'pb_learn'})
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Guide Scheme', 'code': 'GDSCHEME', 'country_code': 'VN'})

        def rule(code, name, letter, **kw):
            vals = {'config_id': cls.config.id, 'code': code, 'name': name,
                    'column_letter': letter, 'forced_column_letter': letter,
                    'column_type': 'input'}
            vals.update(kw)
            return cls.env['hr.formula.rule'].create(vals)

        cls.r_basic = rule('GDBASIC', 'Basic Salary', 'A', value_kind='money',
                           net_role='earning', net_role_confidence='certain')
        cls.r_loan = rule('GDLOAN', 'Loan Installment', 'B', value_kind='money')
        cls.r_hours = rule('GDOTHRS', 'Overtime Hours', 'C', value_kind='quantity',
                           net_role='earning', net_role_confidence='certain')
        cls.r_net = rule('GDTAKEHOME', 'Take Home', 'D', value_kind='money',
                         net_role='net', net_role_confidence='certain')
        cls.Guide = cls.env['learn.guide']

    def setUp(self):
        super().setUp()
        if not self.has_formula:
            self.skipTest('the formula engine is not installed here')

    def _guide(self, lang, key='treatment', **args):
        return self.Guide.with_context(lang=lang).guide(key, args or None)

    # ------------------------------------------------------------ T2
    def test_02_treatment_guide_in_english(self):
        out = self._guide('en_US', config_id=self.config.id)
        self.assertEqual(out['lang'], 'en_US')
        self.assertEqual(out['screen']['name'], 'Component treatment')
        self.assertEqual([p['label'] for p in out['screen']['path']],
                         ['Mapping', 'Component treatment'])
        self.assertEqual(out['screen']['path'][1]['open'],
                         {'xmlid': 'pb_formula_studio.action_pb_mapping_studio',
                          'lens': 'treatment', 'lens_key': 'pb_mode'})
        self.assertTrue(out['screen']['purpose'])
        self.assertEqual(len(out['fields']), 6)
        cards = {f['key']: f for f in out['fields']}
        self.assertEqual([f['column'] for f in out['fields']],
                         ['Comes from', 'Report group', 'Pay role',
                          'Included in another total', 'Run signal', 'Value type'])
        pay_role = cards['pay_role']
        self.assertEqual(len(pay_role['choices']), 6)
        self.assertEqual(pay_role['choices'][0],
                         {'value': 'earning', 'label': 'Added to net pay',
                          'when': pay_role['choices'][0]['when']})
        self.assertTrue(all(c['when'] for c in pay_role['choices']))
        self.assertTrue(pay_role['help'])
        self.assertGreaterEqual(len(pay_role['used_by']), 10)
        self.assertEqual({s['value'] for s in pay_role['source_values']},
                         {'auto', 'user'})
        self.assertEqual(len(cards['value_kind']['choices']), 9)
        self.assertEqual(cards['run_signal']['label'], 'Run signal')
        self.assertTrue(cards['lane']['derived'])
        self.assertIn('calculated', {v['value'] for v in cards['lane']['values']})
        self.assertEqual(out['doors']['station'], 'treatment')
        self.assertTrue(out['doors']['lesson'])
        self.assertEqual([t['key'] for t in out['doors']['tasks']], ['sc_treatment'])
        self.assertEqual(len(out['doors']['terms']), 4)
        self.assertEqual(len(out['actions']), 3)
        self.assertFalse(out['missing'], out['missing'])
        self.assertTrue(out['right_now']['ok'])

    def test_02b_treatment_guide_in_vietnamese(self):
        out = self._guide('vi_VN', config_id=self.config.id)
        self.assertEqual(out['lang'], 'vi_VN')
        self.assertEqual([p['label'] for p in out['screen']['path']],
                         ['Ánh xạ', 'Xử lý thành phần'])
        cards = {f['key']: f for f in out['fields']}
        self.assertEqual(len(out['fields']), 6)
        roles = {c['value']: c['label'] for c in cards['pay_role']['choices']}
        self.assertEqual(len(roles), 6)
        self.assertEqual(roles['earning'], 'Cộng vào thực nhận')
        kinds = {c['value']: c['label'] for c in cards['value_kind']['choices']}
        self.assertEqual(len(kinds), 9)
        self.assertEqual(kinds['money'], 'Số tiền (tiền tệ)')
        en = {c['value']: c['label'] for c in
              {f['key']: f for f in self._guide('en_US')['fields']}
              ['value_kind']['choices']}
        for value, label in kinds.items():
            self.assertNotEqual(label, en[value], 'value type %s is English' % value)
        self.assertEqual(cards['pay_role']['column'], 'Vai trò trong lương')
        self.assertEqual(cards['run_signal']['label'], 'Tín hiệu cho đợt lương')
        self.assertIn('lương', cards['pay_role']['filled_by'])
        self.assertEqual(out['doors']['station'], 'treatment')
        self.assertTrue(all(u['label'] for u in cards['pay_role']['used_by']))
        texts = [i['text'] for i in out['right_now']['items']]
        self.assertTrue(texts and all(texts))
        self.assertIn('dòng', texts[0])

    # ------------------------------------------------------------ T3
    def _items(self, lang='en_US'):
        return {i['key']: i for i in
                self._guide(lang, config_id=self.config.id)['right_now']['items']}

    def test_03_right_now_names_what_to_do(self):
        items = self._items()
        self.assertEqual(list(items)[:2], ['needs_answer', 'type_conflict'])
        self.assertEqual(items['needs_answer']['count'], 1)
        self.assertIn('Loan Installment', items['needs_answer']['text'])
        self.assertEqual(items['needs_answer']['action'],
                         {'kind': 'filter', 'value': 'review'})
        self.assertEqual(items['type_conflict']['count'], 1)
        self.assertIn('Overtime Hours', items['type_conflict']['text'])
        self.assertEqual(items['type_conflict']['action'],
                         {'kind': 'filter', 'value': 'conflict'})
        self.assertNotIn('ok', items)

        self.r_loan.write({'net_role': 'deduction', 'net_role_confidence': 'certain'})
        self.r_hours.write({'net_role': 'info'})
        items = self._items()
        self.assertEqual(list(items), ['ok'])
        self.assertEqual(items['ok']['severity'], 'ok')

    def test_03b_a_run_computed_before_the_change_is_named(self):
        company = self.env.company
        employee = self.env['hr.employee'].create({'name': 'Guide Person'})
        run = self.env['hr.payslip.run'].create({
            'name': 'Guide June Run', 'date_start': '2026-06-01',
            'date_end': '2026-06-30'})
        vals = {'name': 'Guide slip', 'employee_id': employee.id,
                'date_from': '2026-06-01', 'date_to': '2026-06-30',
                'payslip_run_id': run.id, 'company_id': company.id,
                'formula_config_id': self.config.id}
        slip = self.env['hr.payslip'].create(vals)
        # Every write in one test transaction shares one timestamp, so "before
        # the change" is made explicit: the payslip was written yesterday.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE hr_payslip SET write_date = now() - interval '1 day' "
            "WHERE id = %s", [slip.id])
        self.env.invalidate_all()
        items = self._items()
        self.assertIn('recompute', items)
        self.assertEqual(items['recompute']['count'], 1)
        self.assertIn('Guide June Run', items['recompute']['text'])
        self.assertTrue(items['recompute']['action']['kind'] in ('open', 'open_record'))
        vi = self._items('vi_VN')
        self.assertIn('Guide June Run', vi['recompute']['text'])
        self.assertIn('Đợt lương', vi['recompute']['text'])

    def test_03c_no_scheme_and_no_access_are_named_reasons(self):
        out = self._guide('en_US')
        self.assertIn('right_now: no scheme selected', out['missing'])
        self.assertEqual(len(out['fields']), 6)
        clerk = new_test_user(self.env, login='guide_clerk', groups='base.group_user')
        out = self.Guide.with_user(clerk).with_context(lang='en_US').guide(
            'treatment', {'config_id': self.config.id})
        self.assertIn('right_now: no access', out['missing'])
        self.assertEqual(out['right_now']['items'], [])
        self.assertEqual(len(out['fields']), 6)

    # ------------------------------------------------------------ T6
    def test_06_board_value_types_are_translated(self):
        board = self.config.with_context(lang='vi_VN').value_kind_board()
        options = {o['value']: o['label'] for o in board['options']}
        self.assertEqual(len(options), 9)
        self.assertEqual(options['money'], 'Số tiền (tiền tệ)')
        self.assertEqual(options['quantity'], 'Số lượng (giờ, ngày)')
        english = {o['value']: o['label'] for o in
                   self.config.with_context(lang='en_US').value_kind_board()['options']}
        self.assertEqual(english['money'], 'Amount (currency)')

    # ------------------------------------------------------------ T7
    def test_07_a_screen_without_a_manifest_still_answers(self):
        out = self._guide('en_US', key='hub_home')
        self.assertEqual(out['missing'], ['no manifest for this screen yet'])
        self.assertEqual(out['screen']['name'], 'Home')
        self.assertTrue(out['screen']['path'])
        self.assertEqual(out['fields'], [])
        self.assertIn('tasks', out['doors'])
        out = self._guide('vi_VN', key='no_such_screen')
        self.assertEqual(out['missing'], ['no manifest for this screen yet'])
        self.assertEqual(out['screen']['name'], 'no_such_screen')
