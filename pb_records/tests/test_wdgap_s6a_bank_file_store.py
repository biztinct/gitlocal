# -*- coding: utf-8 -*-
"""WDGAP S6-A — an approved bank change on the Updates / Records bank lane
reaches the four fields the pay bank file reads (FACTS §0.1).

Before: `_write_bank` wrote the employee's bank ACCOUNT only, so the bank
file kept paying the old number. Now the account it wrote is read first and
the four `vietnam_bank_*` fields say the same; an undo puts both back.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_records.tests.bank_second import (
    approve_bank, ensure_second_person)


@tagged('post_install', '-at_install')
class TestS6aBankFileStore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Desk = cls.env['pb.records.desk']
        Emp = cls.env['hr.employee']
        if 'vietnam_bank_account_number' not in Emp._fields:
            cls.skip_all = True
            return
        cls.skip_all = False
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
            cls.env.company, 'records')
        ensure_second_person(cls.env, cls.env.company)
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'S6A Scheme', 'code': 'S6ASCHEME', 'country_code': 'VN',
            'state': 'active', 'company_id': cls.env.company.id})
        Rule = cls.env['hr.formula.rule']
        Mapping = cls.env['hr.payslip.import.mapping']
        for code, role in (('SSAACCNO', 'acc_number'), ('SSABANK', 'bank_name'),
                           ('SSAHOLDER', 'acc_holder_name')):
            rule = Rule.create({'config_id': cls.cfg.id, 'name': code,
                                'code': code, 'column_type': 'input',
                                'sequence': 1, 'default_value': 0.0})
            Mapping.create({'salary_structure_id': cls.cfg.id,
                            'component_id': rule.id,
                            'destination_type': 'bank_account',
                            'bank_role': role})
        cls.emp = Emp.create({'name': 'S6A Bank Person',
                              'company_id': cls.env.company.id,
                              'vietnam_bank_name': 'Old Bank',
                              'vietnam_bank_branch': 'Old Branch',
                              'vietnam_bank_account_number': '999000111',
                              'vietnam_bank_account_name': 'S6A BANK PERSON'})
        cls.env['hr.contract'].create({
            'name': 'S6A contract', 'employee_id': cls.emp.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2026-01-01'})

    def setUp(self):
        super().setUp()
        if self.skip_all:
            self.skipTest('the bank file fields are not installed here')

    def _change(self, number, bank='S6A New Bank', holder=None):
        rows = [{'emp_id': self.emp.id, 'field_id': 'b:acc_number', 'value': number},
                {'emp_id': self.emp.id, 'field_id': 'b:bank_name', 'value': bank}]
        if holder:
            rows.append({'emp_id': self.emp.id, 'field_id': 'b:acc_holder_name',
                         'value': holder})
        res = self.Desk.apply_changes(self.cfg.id, rows)
        self.assertEqual(approve_bank(self.env, res), 1)
        part = [p for p in res['lanes'] if p.get('lane') == 'bank'][0]
        self.env.invalidate_all()
        return part['apply_id']

    # R1 — the approved account reaches the bank file's four fields
    def test_r1_approved_change_reaches_the_bank_file_fields(self):
        self._change('1234 5678 90', holder='S6A Holder')
        emp = self.emp
        self.assertEqual(emp.vietnam_bank_account_number, '1234567890')
        self.assertEqual(emp.vietnam_bank_name, 'S6A New Bank')
        self.assertEqual(emp.vietnam_bank_account_name, 'S6A Holder')
        # the bank changed, so the old bank's branch is cleared
        self.assertFalse(emp.vietnam_bank_branch)
        self.assertEqual(emp.bank_account_ids[:1].acc_number, '1234567890')
        if 'pb.employee.bank.history' in self.env:
            row = self.env['pb.employee.bank.history'].search(
                [('employee_id', '=', emp.id)], limit=1)
            self.assertEqual(row.change_source, 'updates')
            self.assertEqual(row.old_account_number, '999000111')
            self.assertEqual(row.new_account_number, '1234567890')

    # R2 — a second change adds an account and the NEW one is read first
    def test_r2_second_change_is_the_one_read_first(self):
        self._change('111000222')
        self._change('333000444')
        emp = self.emp
        self.assertEqual(len(emp.bank_account_ids), 2)
        self.assertEqual(emp.bank_account_ids[:1].acc_number, '333000444')
        self.assertEqual(emp.vietnam_bank_account_number, '333000444')
        # the bank file reads the new number
        if 'vietnam.bank.export.wizard' in self.env \
                and 'pb.bank.registry' in self.env:
            wizard = self.env['vietnam.bank.export.wizard'].new({})
            if hasattr(wizard, '_row_sources'):
                slip = self.env['hr.payslip'].new({'employee_id': emp.id})
                sources = wizard._row_sources(
                    slip, 1, self.env['pb.bank.registry'])[0]
                self.assertEqual(sources['account_number'], '333000444')

    # R3 — the same holder and bank again writes nothing more
    def test_r3_same_values_do_not_rewrite(self):
        self._change('555000666')
        before = self.emp.write_date
        History = self.env['pb.employee.bank.history'] \
            if 'pb.employee.bank.history' in self.env else None
        n = History.search_count([('employee_id', '=', self.emp.id)]) if History is not None else 0
        res = self.Desk.preview_changes(self.cfg.id, [
            {'emp_id': self.emp.id, 'field_id': 'b:acc_number', 'value': '555000666'}])
        self.assertTrue(all(i['status'] == 'same' for i in res['items']))
        if History is not None:
            self.assertEqual(History.search_count([('employee_id', '=', self.emp.id)]), n)
        self.assertEqual(self.emp.write_date, before)

    # R4 — undo puts both places back
    def test_r4_undo_puts_both_back(self):
        self._change('777000888')
        apply_id = self._change('121000343')
        self.assertEqual(self.emp.vietnam_bank_account_number, '121000343')
        undone = self.Desk.undo_apply(apply_id)
        self.assertTrue(undone.get('ok'), undone)
        self.env.invalidate_all()
        self.assertEqual(self.emp.vietnam_bank_account_number, '777000888')
        self.assertEqual(self.emp.bank_account_ids[:1].acc_number, '777000888')
