# -*- coding: utf-8 -*-
"""WDGAP wave 3 merge seams (W3-A, W3-B, W3-C on ONE tree). Deploy handover §1.

M1 (a) the yearly Pay Review (W3-B PRV1) and "Raise the scale" (S8-D) share the
   quiet hourly job that writes dated rises: a scale rise and a pay review due
   on the same day are both written on their day, once each; a second run
   writes nothing; a person in BOTH (the scale rise writes first) is left out
   of the review and listed with the reason (owner ruling PRV2), never
   overwritten.
M2 (c) one renewal carries everything at once: the Vietnam contract kind
   (RN1), the payroll treatment Permanent (RN3), the old pay lines (S8-D EX1)
   and the link to the old contract (RN2) — on the Contracts "Renew" path and
   on the decision board's extension; "Make it permanent" still builds an
   open-ended contract with the lines carried and no treatment copied.

Skipped where a module of the seam is not installed (probe pattern).
"""
import re
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged


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


PAY_TABLES = ('hr_contract', 'hr_contract_advantage', 'hr_contract_advantage_change',
              'hr_payslip', 'hr_payslip_line')


@tagged('post_install', '-at_install', 'wdgap_w3m')
class TestW3MergeSharedJob(TransactionCase):
    """M1 — seam (a)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.company = cls.env['res.company'].create({
            'name': 'W3M Job Co', 'currency_id': cls.vnd.id,
            'country_id': cls.env.ref('base.vn').id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id],
            tracking_disable=True, mail_notrack=True))
        cls.Scales = cls.env['pb.pay.scales']
        cls.Raise = cls.env['pb.pay.scale.raise']
        cls.Reviews = cls.env['pb.pay.reviews']
        cls.Change = cls.env['hr.contract.advantage.change']
        Rule = cls.env['hr.formula.rule']
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'W3M scheme', 'code': 'WTHREEM', 'country_code': 'VN',
            'state': 'active', 'company_id': cls.company.id, 'currency_id': cls.vnd.id})
        basic = Rule.create({'config_id': cls.cfg.id, 'code': 'BASIC', 'name': 'Basic',
                             'column_type': 'input', 'sequence': 10, 'net_role': 'earning'})
        Rule.create({'config_id': cls.cfg.id, 'code': 'NETPAY', 'name': 'Take-home',
                     'column_type': 'formula', 'sequence': 30, 'net_role': 'net',
                     'excel_formula': '=%s' % basic.column_letter})
        cls.scale = cls.env['pb.pay.scale'].create({
            'name': 'W3M scale', 'country_code': 'VN', 'currency_id': cls.vnd.id,
            'step_count': 2, 'company_ids': [(6, 0, [cls.company.id])]})
        cls.grade = cls.env['pb.pay.scale.grade'].create(
            {'scale_id': cls.scale.id, 'name': 'W3M grade', 'sequence': 10})
        version = cls.env['pb.pay.scale.version'].create(
            {'scale_id': cls.scale.id, 'date_from': '2025-01-01'})
        for step, amount in enumerate((5_500_000, 5_800_000), start=1):
            cls.env['pb.pay.scale.cell'].create({
                'version_id': version.id, 'grade_id': cls.grade.id,
                'step_no': step, 'amount': amount})
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, 'scaleraise')
        cls._n = 0

    def _person(self, wage, on_scale):
        type(self)._n += 1
        emp = self.env['hr.employee'].create({
            'name': 'W3M Person %s' % self._n, 'company_id': self.company.id})
        contract = self.env['hr.contract'].create({
            'name': 'W3M contract %s' % self._n, 'employee_id': emp.id,
            'wage': wage, 'state': 'open', 'date_start': '2025-01-01',
            'company_id': self.company.id})
        emp.sudo().write({'pb_paid_by_id': self.cfg.id})
        if 'pb_paid_by_stale' in emp._fields:
            emp.sudo().write({'pb_paid_by_stale': False})
        if on_scale:
            self.env['pb.pay.scale.placement'].create({
                'contract_id': contract.id, 'grade_id': self.grade.id, 'step_no': 1,
                'source': 'hand'})
        return emp, contract

    def test_m1_scale_rise_and_pay_review_share_the_job(self):
        today = self.Raise._today_for(self.company)
        start = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        emp_a, con_a = self._person(5_500_000.0, on_scale=True)     # scale only
        emp_b, con_b = self._person(10_000_000.0, on_scale=False)   # review only
        emp_c, con_c = self._person(5_500_000.0, on_scale=True)     # both
        # the scale rise: +5 %, approved for the first of next month
        read = self.Scales.raise_save(self.scale.id, {
            'effective_date': fields.Date.to_string(start), 'method': 'percent',
            'pct': 5, 'reason': 'W3M yearly rise'}, 0)
        self.Scales.raise_act(read['id'], 'send')
        rise = self.Raise.browse(read['id'])
        self.assertEqual(rise.state, 'scheduled')
        # the pay review: B and C, same start date
        review = self.env['pb.pay.review'].create({
            'name': 'W3M review', 'scope_kind': 'company', 'scope_ref': self.company.id,
            'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)],
            'currency_id': self.vnd.id, 'year': start.year, 'effective_date': start})
        for emp, con, new in ((emp_b, con_b, 10_500_000.0), (emp_c, con_c, 6_000_000.0)):
            self.env['pb.pay.review.line'].create({
                'review_id': review.id, 'employee_id': emp.id, 'contract_id': con.id,
                'company_id': self.company.id, 'currency_id': self.vnd.id,
                'current_wage': con.wage, 'new_wage': new,
                'proposal_amount': new - con.wage})
        review.sudo()._chain_state_write('approved')
        Model = type(self.Raise)
        with patch.object(Model, '_today_for', lambda s, company=None: today):
            answer = self.Reviews.apply(review.id)
            self.assertTrue(answer['scheduled'], "a future review waits for its day")
            self.env.flush_all()
            with spy_writes(PAY_TABLES) as seen:
                tally = self.Raise._cron_apply_due()
                self.env.flush_all()
            self.assertFalse(tally.get('started'))
            self.assertFalse(tally.get('review_started'))
            self.assertEqual(seen, [], "nothing before the day")
        with patch.object(Model, '_today_for', lambda s, company=None: start):
            tally = self.Raise._cron_apply_due()
            self.assertGreaterEqual(tally.get('started', 0), 1, "the scale rise started")
            self.assertEqual(tally.get('review_started'), 1, "the review started")
            self.env.invalidate_all()
            self.assertEqual(con_a.wage, 5_775_000.0, "scale rise written")
            self.assertEqual(con_b.wage, 10_500_000.0, "review written")
            self.assertEqual(con_c.wage, 5_775_000.0,
                             "the scale rise came first; the review never overwrote it")
            row_c = review.apply_ids.filtered(lambda r: r.employee_id == emp_c)
            self.assertEqual(row_c.state, 'skipped')
            self.assertIn('changed since', row_c.note)
            self.assertEqual(self.Reviews._card(review)['pbs_skipped']['count'], 1,
                             "the left-out person is listed on the review")
            row_b = review.apply_ids.filtered(lambda r: r.employee_id == emp_b)
            self.assertEqual(row_b.state, 'applied')
            changes = self.Change.sudo().search(
                [('contract_id', 'in', (con_a | con_b | con_c).ids)])
            self.assertEqual(len(changes), 3, "one dated record per written rise")
            self.assertEqual(set(changes.mapped('effective_date')), {start})
            by = {c.contract_id.id: c.change_source for c in changes}
            self.assertEqual(by[con_b.id], 'pay_review')
            self.assertNotEqual(by[con_a.id], 'pay_review')
            self.assertNotEqual(by[con_c.id], 'pay_review', "C was written by the scale rise")
            # the job again: nothing more
            self.env.flush_all()
            with spy_writes(PAY_TABLES + ('pb_pay_apply',)) as seen:
                again = self.Raise._cron_apply_due()
                self.env.flush_all()
            self.assertEqual(seen, [], "twice is once")
            self.assertFalse(again.get('started'))
            self.assertFalse(again.get('review_started'))


@tagged('post_install', '-at_install', 'wdgap_w3m')
class TestW3MergeRenewalCarriesAll(TransactionCase):
    """M2 — seam (c)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'W3M Renewals VN', 'country_id': cls.env.ref('base.vn').id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id],
            tracking_disable=True, mail_notrack=True))
        cls.ready = ('pb.contract.review' in cls.env and 'pb.contract.rule' in cls.env)
        if not cls.ready:
            return
        from odoo.addons.pb_people_advanced.models.newhire_approval import (
            NEWHIRE_PROCESS_KEY, NEWHIRE_WRITE)
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
            cls.company, NEWHIRE_PROCESS_KEY)
        cls.Wizard = cls.env['pb.people.contract.wizard'].with_context(
            **{NEWHIRE_WRITE: True})
        Template = cls.env['hr.contract.advantage.template']
        cls.meal = Template.search([('code', '=', 'WTMMEAL')], limit=1) or Template.create(
            {'name': 'W3M Meal allowance', 'code': 'WTMMEAL'})
        cls.phone = Template.search([('code', '=', 'WTMPHONE')], limit=1) or Template.create(
            {'name': 'W3M Phone allowance', 'code': 'WTMPHONE'})
        cls._n = 0

    def setUp(self):
        super().setUp()
        fields_ = self.env['hr.contract']._fields
        if not self.ready or 'vietnam_contract_type' not in fields_ \
                or 'pb_payroll_contract_type' not in fields_:
            self.skipTest('a module of the renewal seam is not installed here')

    def _old(self):
        type(self)._n += 1
        emp = self.env['hr.employee'].create({
            'name': 'W3M Renewal %s' % self._n, 'company_id': self.company.id,
            'address_id': self.company.partner_id.id})
        old = self.env['hr.contract'].create({
            'name': 'W3M fixed term %s' % self._n, 'employee_id': emp.id,
            'company_id': self.company.id, 'state': 'open', 'wage': 9_000_000.0,
            'date_start': date(2025, 1, 1), 'date_end': date(2025, 12, 31),
            'vietnam_contract_type': 'definite', 'pb_payroll_contract_type': 'permanent'})
        for template, amount in ((self.meal, 730_000.0), (self.phone, 200_000.0)):
            self.env['hr.contract.advantage'].create({
                'contract_id': old.id, 'advantage_template_id': template.id,
                'amount': amount})
        return old

    def _lines(self, contract):
        return sorted((l.advantage_template_id.code, l.amount)
                      for l in self.env['hr.contract.advantage'].sudo().search(
                          [('contract_id', '=', contract.id)]))

    def test_m2_one_renewal_carries_kind_treatment_lines_and_link(self):
        want = [('WTMMEAL', 730_000.0), ('WTMPHONE', 200_000.0)]
        # Contracts > Renew
        old = self._old()
        d = self.Wizard.get_defaults(old.employee_id.id, old.id)
        self.assertEqual(d['prefill']['vn_kind'], 'definite')
        self.assertEqual(d['prefill']['pay_treatment'], 'permanent')
        self.assertEqual(sorted((l['code'], l['amount']) for l in d['prefill']['lines']), want)
        res = self.Wizard.create_contract({
            'employee_id': old.employee_id.id, 'wage': old.wage, 'date_start': '2026-01-01',
            'date_end': '2026-12-31',
            'struct_id': d['prefill'].get('struct_id') or d.get('default_struct'),
            'renew_from': old.id, 'lines': d['prefill']['lines']})
        self.assertFalse(res.get('error'), res)
        new = self.env['hr.contract'].browse(res['contract_id'])
        self.assertEqual(new.vietnam_contract_type, 'definite')
        self.assertEqual(new.pb_payroll_contract_type, 'permanent')
        self.assertEqual(self._lines(new), want, "pay lines still carried")
        self.assertEqual(new.pb_renewed_from_id, old)
        self.assertEqual(self._lines(old), want, "the old contract is untouched")
        # the decision board's extension
        old2 = self._old()
        review = self.env['pb.contract.review'].create(
            {'contract_id': old2.id, 'company_id': self.company.id})
        ext = review._build_new_contract(date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(ext.state, 'draft')
        self.assertEqual(ext.vietnam_contract_type, 'definite')
        self.assertEqual(ext.pb_payroll_contract_type, 'permanent')
        self.assertEqual(self._lines(ext), want)
        self.assertEqual(ext.pb_renewed_from_id, old2)
        # Make it permanent: open-ended, lines carried, no treatment copied (as before)
        old3 = self._old()
        review3 = self.env['pb.contract.review'].create(
            {'contract_id': old3.id, 'company_id': self.company.id})
        perm = review3._build_new_contract(date(2026, 1, 1), False)
        self.assertTrue(perm, "Make it permanent still works")
        self.assertFalse(perm.date_end)
        self.assertEqual(perm.vietnam_contract_type, 'indefinite')
        self.assertFalse(perm.pb_payroll_contract_type)
        self.assertEqual(self._lines(perm), want)
        self.assertEqual(perm.pb_renewed_from_id, old3)
