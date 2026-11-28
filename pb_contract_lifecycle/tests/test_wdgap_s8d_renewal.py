# -*- coding: utf-8 -*-
"""WDGAP S8-D (owner ruling EX1) — a renewal carries the old contract's pay
lines. Numbered as in the S8-D report (§3, EX1 rows):

X1  contract decisions board: an approved extension builds the new (draft)
    contract with the SAME pay lines and amounts as the old one; each line is
    logged in the pay-line trail dated the new start ("Carried from …"); the
    old contract's lines are not touched.
X2  Contracts "Renew" form: the form opens with the pay lines carried over;
    HR changes one amount and takes one line off before saving — the new
    contract has exactly that.
X3  HR can still change them before the contract runs: the board's new
    contract is a draft and its lines can be edited.
X4  "Make it permanent" builds the new contract the same way (lines carried).
X5  the READ-ONLY check (`tools/renewal_lost_pay_lines.sql`) lists a renewal
    made before this change that lost a line (linked, and by dates), and not
    one that carried its lines; it writes nothing.
X6  golden: a renewal writes no payslip and no payslip line, and leaves every
    other contract's pay lines exactly as they were.
"""
import os
import re
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch

from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_people_advanced.models.newhire_approval import (
    NEWHIRE_PROCESS_KEY, NEWHIRE_WRITE,
)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextmanager
def spy_writes(tables):
    seen = []
    real = Cursor.execute

    def execute(self, query, params=None, log_exceptions=True):
        text = str(query.code if hasattr(query, 'code') else query).lower()
        if text.lstrip()[:7].startswith(('insert', 'update', 'delete')):
            for table in tables:
                if re.search(r'\b%s\b' % re.escape(table), text):
                    seen.append(text[:120])
        return real(self, query, params, log_exceptions)

    with patch.object(Cursor, 'execute', execute):
        yield seen


@tagged('post_install', '-at_install', 'wdgap_s8d')
class TestS8dRenewalCarriesPayLines(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
            cls.company, NEWHIRE_PROCESS_KEY)
        Template = cls.env['hr.contract.advantage.template']
        cls.meal = Template.search([('code', '=', 'SDMEAL')], limit=1) or Template.create(
            {'name': 'S8D Meal allowance', 'code': 'SDMEAL'})
        cls.phone = Template.search([('code', '=', 'SDPHONE')], limit=1) or Template.create(
            {'name': 'S8D Phone allowance', 'code': 'SDPHONE'})
        cls.house = Template.search([('code', '=', 'SDHOUSE')], limit=1) or Template.create(
            {'name': 'S8D Housing', 'code': 'SDHOUSE'})
        cls._n = 0

    def _person(self, lines=None, end_in=40):
        type(self)._n += 1
        emp = self.env['hr.employee'].create({
            'name': 'S8D Renewal %s' % self._n, 'company_id': self.company.id})
        contract = self.env['hr.contract'].create({
            'name': 'S8D fixed term %s' % self._n, 'employee_id': emp.id,
            'company_id': self.company.id, 'state': 'open', 'wage': 9_000_000.0,
            'date_start': date.today() - timedelta(days=300),
            'date_end': date.today() + timedelta(days=end_in)})
        for template, amount in (lines if lines is not None else
                                 ((self.meal, 730_000.0), (self.phone, 200_000.0))):
            self.env['hr.contract.advantage'].create({
                'contract_id': contract.id, 'advantage_template_id': template.id,
                'amount': amount})
        return emp, contract

    def _lines(self, contract):
        return sorted((l.advantage_template_id.code, l.amount)
                      for l in self.env['hr.contract.advantage'].sudo().search(
                          [('contract_id', '=', contract.id)]))

    def _review(self, contract):
        return self.env['pb.contract.review'].create({
            'contract_id': contract.id, 'company_id': self.company.id})

    # ================================================================ X1
    def test_x1_board_extension_carries_the_lines(self):
        _emp, old = self._person()
        before = [(l.id, l.amount, l.write_date) for l in old.sudo().advantage_ids] \
            if 'advantage_ids' in old._fields else self._lines(old)
        start = old.date_end + timedelta(days=1)
        new = self._review(old)._build_new_contract(start, start + timedelta(days=365))
        self.assertTrue(new, "the new contract is made")
        self.assertEqual(new.state, 'draft')
        self.assertEqual(self._lines(new), [('SDMEAL', 730_000.0), ('SDPHONE', 200_000.0)])
        rows = self.env['hr.contract.advantage.change'].sudo().search(
            [('contract_id', '=', new.id)])
        self.assertEqual(sorted(rows.mapped('advantage_template_code')), ['SDMEAL', 'SDPHONE'])
        self.assertEqual(set(rows.mapped('effective_date')), {start})
        self.assertTrue(all('Carried from' in (r.notes or '') for r in rows))
        old.invalidate_recordset()
        after = [(l.id, l.amount, l.write_date) for l in old.sudo().advantage_ids] \
            if 'advantage_ids' in old._fields else self._lines(old)
        self.assertEqual(before, after, "the old contract's lines are untouched")

    # ================================================================ X2
    def test_x2_renew_form_carries_and_hr_changes_them(self):
        emp, old = self._person(lines=((self.meal, 730_000.0), (self.phone, 200_000.0),
                                       (self.house, 1_500_000.0)))
        Wizard = self.env['pb.people.contract.wizard'].with_context(**{NEWHIRE_WRITE: True})
        d = Wizard.get_defaults(emp.id, old.id)
        lines = d['prefill']['lines']
        self.assertEqual(sorted((l['code'], l['amount']) for l in lines),
                         [('SDHOUSE', 1_500_000.0), ('SDMEAL', 730_000.0),
                          ('SDPHONE', 200_000.0)])
        for line in lines:
            if line['code'] == 'SDMEAL':
                line['amount'] = 800_000.0
            if line['code'] == 'SDPHONE':
                line['drop'] = True
        res = Wizard.create_contract({
            'employee_id': emp.id, 'wage': 9_500_000.0,
            'date_start': str(old.date_end + timedelta(days=1)),
            'struct_id': d['prefill'].get('struct_id') or d.get('default_struct'),
            'renew_from': old.id, 'lines': lines})
        self.assertFalse(res.get('error'), res)
        new = self.env['hr.contract'].browse(res['contract_id'])
        self.assertEqual(self._lines(new), [('SDHOUSE', 1_500_000.0), ('SDMEAL', 800_000.0)])
        # a contract for somebody else never takes another person's lines
        other, _c = self._person(lines=())
        res = Wizard.create_contract({
            'employee_id': other.id, 'wage': 1.0, 'date_start': str(date.today()),
            'struct_id': d.get('default_struct'), 'renew_from': old.id})
        self.assertEqual(self._lines(self.env['hr.contract'].browse(res['contract_id'])), [])
        # a new contract that is not a renewal is exactly as before
        res = Wizard.create_contract({
            'employee_id': emp.id, 'wage': 1.0, 'date_start': str(date.today()),
            'struct_id': d.get('default_struct')})
        self.assertEqual(self._lines(self.env['hr.contract'].browse(res['contract_id'])), [])

    # ================================================================ X3
    def test_x3_hr_changes_the_draft_before_it_runs(self):
        _emp, old = self._person()
        start = old.date_end + timedelta(days=1)
        new = self._review(old)._build_new_contract(start, start + timedelta(days=180))
        self.assertEqual(new.state, 'draft')
        line = self.env['hr.contract.advantage'].sudo().search(
            [('contract_id', '=', new.id), ('advantage_template_id', '=', self.phone.id)])
        line.amount = 250_000.0
        self.assertIn(('SDPHONE', 250_000.0), self._lines(new))
        self.assertIn(('SDPHONE', 200_000.0), self._lines(old))

    # ================================================================ X4
    def test_x4_make_it_permanent_carries_the_lines(self):
        _emp, old = self._person()
        review = self._review(old)
        start = old.date_end + timedelta(days=1)
        new = review._build_new_contract(start, False,
                                         contract_type=review._permanent_contract_type())
        self.assertTrue(new)
        self.assertFalse(new.date_end)
        self.assertEqual(self._lines(new), [('SDMEAL', 730_000.0), ('SDPHONE', 200_000.0)])

    # ================================================================ X5
    def _check_sql(self):
        path = os.path.join(HERE, 'tools', 'renewal_lost_pay_lines.sql')
        with open(path) as handle:
            text = handle.read()
        # The file wraps itself in a read-only transaction; inside a test the
        # SELECT is run on its own (a BEGIN / ROLLBACK here would end the test's).
        body = '\n'.join(l for l in text.splitlines()
                         if not l.strip().upper().startswith(('BEGIN', 'ROLLBACK', '--')))
        self.assertIn('BEGIN TRANSACTION READ ONLY', text)
        self.env.flush_all()
        with spy_writes(('hr_contract', 'hr_contract_advantage', 'hr_payslip')) as seen:
            with self.env.cr.savepoint():
                self.env.cr.execute(body)
                rows = self.env.cr.dictfetchall()
        self.assertFalse(seen)
        return rows

    def test_x5_read_only_check_lists_the_lost_lines(self):
        # a renewal made BEFORE S8-D: linked by the board, no lines carried
        emp1, old1 = self._person()
        new1 = self.env['hr.contract'].create({
            'name': 'S8D old renewal', 'employee_id': emp1.id, 'company_id': self.company.id,
            'wage': 9_000_000.0, 'date_start': old1.date_end + timedelta(days=1),
            'state': 'draft', 'pb_renewed_from_id': old1.id})
        old1.write({'state': 'close'})
        new1.write({'state': 'open'})
        # one by dates only (the Renew button wrote no link), the meal line kept
        emp2, old2 = self._person(end_in=-10)
        new2 = self.env['hr.contract'].create({
            'name': 'S8D dated renewal', 'employee_id': emp2.id, 'company_id': self.company.id,
            'wage': 9_000_000.0, 'date_start': old2.date_end + timedelta(days=1),
            'state': 'draft'})
        self.env['hr.contract.advantage'].create({
            'contract_id': new2.id, 'advantage_template_id': self.meal.id, 'amount': 730_000.0})
        old2.write({'state': 'close'})
        new2.write({'state': 'open'})
        # one made WITH S8-D: nothing lost
        emp3, old3 = self._person()
        start = old3.date_end + timedelta(days=1)
        new3 = self._review(old3)._build_new_contract(start, start + timedelta(days=365))
        old3.write({'state': 'close'})
        new3.write({'state': 'open'})
        rows = {r['current_contract']: r for r in self._check_sql()}
        self.assertIn(new1.id, rows)
        self.assertEqual(rows[new1.id]['lines_lost'], 2)
        self.assertEqual(rows[new1.id]['how_linked'], 'board')
        self.assertEqual(rows[new1.id]['earlier_contract'], old1.id)
        self.assertIn(new2.id, rows)
        self.assertEqual(rows[new2.id]['lines_lost'], 1)
        self.assertIn('SDPHONE', rows[new2.id]['lines'])
        self.assertEqual(rows[new2.id]['how_linked'], 'by dates')
        self.assertNotIn(new3.id, rows, "a renewal that carried its lines lost nothing")

    # ================================================================ X6
    def test_x6_golden_nothing_else_moves(self):
        _bystander, other = self._person(lines=((self.meal, 500_000.0),))
        snap = [(l.id, l.amount, l.write_date) for l in self.env['hr.contract.advantage']
                .sudo().search([('contract_id', '=', other.id)])]
        _emp, old = self._person()
        start = old.date_end + timedelta(days=1)
        self.env.flush_all()
        with spy_writes(('hr_payslip', 'hr_payslip_line')) as seen:
            self._review(old)._build_new_contract(start, start + timedelta(days=365))
            self.env.flush_all()
        self.assertFalse(seen, "a renewal writes no payslip")
        self.env.invalidate_all()
        self.assertEqual(snap, [(l.id, l.amount, l.write_date) for l in
                                self.env['hr.contract.advantage'].sudo().search(
                                    [('contract_id', '=', other.id)])])
