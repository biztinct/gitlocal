# -*- coding: utf-8 -*-
"""LEARNREV P0 T6 (G33, ledger LR3) — a Pay role reason says "net pay".

`net_role_reason` used to embed the NET component's own name, so on a
Vietnamese scheme the English sentence read "Never reaches Số tiền thực nhận
…". The classifier now says "net pay" (translated); the Component treatment
board says it too for reasons stored before the fix, without re-classifying.
"""
from odoo.tests import TransactionCase, tagged

NET_NAME = 'Số tiền thực nhận'


@tagged('post_install', '-at_install')
class TestLearnrevNetWords(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config = self.env['hr.formula.config'].create({
            'name': 'Learnrev net words', 'code': 'LRNETWORDS', 'country_code': 'VN',
        })
        Category = self.env['hr.salary.rule.category']
        for code in ('BASIC', 'ALW', 'GROSS', 'DED', 'NET', 'COMP', 'OTH'):
            if not Category.search([('code', '=', code)], limit=1):
                Category.create({'name': code.title(), 'code': code})
        other = Category.search([('code', '=', 'OTH')], limit=1)
        spec = [
            ('A', 'BASE', 'Lương cơ bản', 'input', ''),
            ('B', 'ALWONE', 'Phụ cấp', 'input', ''),
            ('C', 'GROSSAGG', 'Tổng thu nhập', 'formula', '=A5+B5'),
            ('D', 'PITAMT', 'Thuế TNCN', 'input', ''),
            ('E', 'NETPAY', NET_NAME, 'formula', '=C5-D5'),
            ('F', 'ERSI', 'Bảo hiểm công ty đóng', 'formula', '=ROUND(A5*0.175,0)'),
            ('G', 'ERCOST', 'Tổng chi phí công ty', 'formula', '=E5+F5'),
            ('H', 'INFOFIELD', 'Ghi chú', 'input', ''),
        ]
        self.rules = {}
        sequence = 10
        for letter, code, name, ctype, formula in spec:
            vals = {
                'config_id': self.config.id, 'name': name, 'code': code,
                'column_type': ctype, 'sequence': sequence, 'column_letter': letter,
                'appears_on_payslip': True, 'category_id': other.id,
            }
            if formula:
                vals['excel_formula'] = formula
            rule = self.env['hr.formula.rule'].create(vals)
            rule.salary_rule_id = self.env['hr.salary.rule'].create({
                'name': name, 'code': code, 'sequence': sequence,
                'category_id': other.id, 'condition_select': 'none',
                'amount_select': 'fix',
            }).id
            self.rules[code] = rule
            sequence += 10
        self.config.invalidate_recordset()

    def _classify(self):
        summary = self.config.with_context(lang='en_US').classify_net_roles()[self.config.id]
        self.assertIsNone(summary['error'], summary.get('error'))
        self.assertEqual(self.rules['NETPAY'].net_role, 'net')

    def test_01_reasons_say_net_pay_not_the_component_name(self):
        self._classify()
        reasons = {code: r.net_role_reason or '' for code, r in self.rules.items()
                   if code != 'NETPAY'}
        for code, reason in reasons.items():
            self.assertNotIn(NET_NAME, reason, code)
        for code in ('GROSSAGG', 'PITAMT', 'INFOFIELD'):
            self.assertIn('net pay', reasons[code], code)

    def test_02_the_board_reads_stored_reasons_right(self):
        """A reason written by the old classifier (NET's name inside) reads
        "net pay" on the board; the stored value is left as it was."""
        self._classify()
        old = 'Never reaches %s, so it is information rather than pay.' % NET_NAME
        self.rules['INFOFIELD'].net_role_reason = old
        # `via` names a real component on purpose — never rewritten.
        via = 'Added into %s through Tổng thu nhập.' % NET_NAME
        self.rules['ALWONE'].net_role_reason = via
        board = self.config.with_context(lang='en_US').value_kind_board()
        rows = {r['code']: r for r in board['rows']}
        for code, row in rows.items():
            if code == 'NETPAY':
                continue
            self.assertNotIn(NET_NAME, row['pay_role_reason'], code)
        self.assertEqual(rows['INFOFIELD']['pay_role_reason'],
                         'Never reaches net pay, so it is information rather than pay.')
        self.assertEqual(rows['ALWONE']['pay_role_reason'],
                         'Added into net pay through Tổng thu nhập.')
        self.assertEqual(self.rules['INFOFIELD'].net_role_reason, old)

    def test_03_a_component_named_after_net_keeps_its_name(self):
        reader = self.config._net_role_reason_read
        self.rules['NETPAY'].net_role = 'net'
        self.rules['BASE'].name = '%s trước thuế' % NET_NAME
        words = self.config._net_role_reason_net_words()
        self.assertEqual(
            reader('Added into %s through %s trước thuế.' % (NET_NAME, NET_NAME), words),
            'Added into net pay through %s trước thuế.' % NET_NAME)
