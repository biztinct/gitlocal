# -*- coding: utf-8 -*-
"""WDGAP Step 8 merge seams (S8-A × S8-B × S8-C), run on the merged tree with all
seven new modules installed. Each case skips when the module it crosses is absent.

M1 (seam b)  Change job with a pay change on a contract placed on an S8-A pay scale:
             afterwards the contract reads Drifted (placed, not pinned) or stays Pinned
             (pinned); the placement row itself is untouched; NO payslip or payslip
             line is written.
M2 (seam c)  Past-dated Change job → "Re-work those months" opens a DRAFT Past-month
             re-work for that person; worked out, the re-work sees the change; with the
             Step 5 merge in (back pay, W2-D2), sending it for payment still works
             (approved, back-pay entries only for that person; the paid payslips
             untouched).
M3 (seam d)  S8-B transfer to a team whose usual cost centre (S8-C) differs: the running
             contract keeps its cost centre (only NEW contracts take the team's), past
             payslip lines unchanged; then an S8-C move dated today: the finished
             payslip keeps the cost centre it was paid under, this month's draft follows
             (owner ruling CC1).
M4 (FACTS §9 table)  `_master_fields` keeps both phases' fields; `_build_new_contract`
             (S8-B override) carries the cost-centre text and S8-C links it; S8-A and
             S8-C `hr.contract` fields coexist; `pb.pay.apply.job_change_id` is S8-B's.
"""
import json
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch
import re

from odoo import fields
from odoo.sql_db import Cursor
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


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


@tagged('post_install', '-at_install', 'wdgap_s8m')
class TestWdgapS8MergeSeams(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.company = cls.env['res.company'].create(
            {'name': 'S8M Co', 'currency_id': cls.vnd.id,
             'country_id': cls.env.ref('base.vn').id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id],
            tracking_disable=True, mail_notrack=True))
        cls.JC = cls.env['pb.job.change']
        cls.Board = cls.env['pb.job.change.board']
        cls.calendar = cls.company.resource_calendar_id or \
            cls.env['resource.calendar'].create(
                {'name': 'S8M Hours', 'company_id': cls.company.id})
        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'S8M Shop', 'company_id': cls.company.id})
        cls.dept_b = Dept.create({'name': 'S8M Warehouse', 'company_id': cls.company.id})
        Job = cls.env['hr.job']
        cls.job_a = Job.create({'name': 'S8M Associate', 'company_id': cls.company.id})
        cls.job_b = Job.create({'name': 'S8M Senior associate',
                                'company_id': cls.company.id})
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, 'jobchange')
        cls._seq = 0

    # ------------------------------------------------------------ fixtures
    def _person(self, wage=5_500_000.0, costcenter=None):
        type(self)._seq += 1
        emp = self.env['hr.employee'].create({
            'name': 'S8M Person %s' % self._seq, 'company_id': self.company.id,
            'department_id': self.dept_a.id, 'job_id': self.job_a.id,
            'resource_calendar_id': self.calendar.id})
        vals = {'name': 'S8M contract %s' % self._seq, 'employee_id': emp.id,
                'wage': wage, 'state': 'open', 'date_start': '2026-01-01',
                'company_id': self.company.id,
                'resource_calendar_id': self.calendar.id,
                'department_id': self.dept_a.id, 'job_id': self.job_a.id}
        if costcenter:
            vals['costcenter'] = costcenter
        return emp, self.env['hr.contract'].create(vals)

    def _today(self):
        return self.JC._today_for(self.company)

    def _send(self, emp, **kw):
        vals = {'employee_id': emp.id, 'reason_kind': 'pay', 'reason': 'S8M merge seam',
                'effective_date': fields.Date.to_string(self._today())}
        vals.update(kw)
        return self.JC.browse(self.Board.send(vals)['id'])

    def _scale(self):
        if 'pb.pay.scale' not in self.env:
            self.skipTest('pay scales not installed')
        scale = self.env['pb.pay.scale'].create({
            'name': 'S8M scale', 'country_code': 'VN', 'currency_id': self.vnd.id,
            'step_count': 3})
        grade = self.env['pb.pay.scale.grade'].create(
            {'scale_id': scale.id, 'name': 'S8M grade', 'sequence': 10})
        version = self.env['pb.pay.scale.version'].create(
            {'scale_id': scale.id, 'date_from': '2020-01-01'})
        for step, amount in enumerate((5_500_000, 5_800_000, 6_100_000), start=1):
            self.env['pb.pay.scale.cell'].create({
                'version_id': version.id, 'grade_id': grade.id, 'step_no': step,
                'amount': amount})
        return scale, grade

    # ================================================================ M1
    def test_m1_change_job_pay_on_a_scale_contract(self):
        _scale, grade = self._scale()
        Place = self.env['pb.pay.scale.placement']
        emp, contract = self._person(wage=5_500_000.0)
        emp2, contract2 = self._person(wage=5_650_000.0)
        on = Place.create({'contract_id': contract.id, 'grade_id': grade.id, 'step_no': 1,
                           'source': 'hand'})
        pin = Place.create({'contract_id': contract2.id, 'grade_id': grade.id, 'step_no': 1,
                            'pinned': True, 'pin_reason': 'retention'})
        self.assertEqual(contract.pb_scale_state, 'on')
        self.assertEqual(contract2.pb_scale_state, 'pinned')
        snap = [(p.id, p.grade_id.id, p.step_no, p.pinned, p.pin_reason) for p in on | pin]
        tables = ('hr_payslip', 'hr_payslip_line', 'pb_pay_scale_placement')
        self.env.flush_all()   # the fixture's own pending writes are not the change's
        with spy_writes(tables) as seen:
            rec = self._send(emp, change_pay=True, new_wage=5_800_000.0)   # = step 2
            rec2 = self._send(emp2, change_pay=True, new_wage=6_000_000.0)
        self.assertEqual(rec.state, 'applied')
        self.assertEqual(rec2.state, 'applied')
        self.assertEqual(seen, [], "no payslip, line or placement write")
        self.env.invalidate_all()
        self.assertEqual(contract.wage, 5_800_000.0)
        self.assertEqual(contract.pb_scale_state, 'drifted',
                         "placed on step 1, now paid step 2's figure: Drifted until "
                         "somebody keeps or re-places it")
        self.assertIn('step 1', contract.pb_scale_label)
        self.assertEqual(contract2.pb_scale_state, 'pinned', "a pinned person stays Pinned")
        self.assertEqual(
            [(p.id, p.grade_id.id, p.step_no, p.pinned, p.pin_reason) for p in on | pin],
            snap, "Change job never moves a placement")
        chip = self.env['pb.pay.scales'].contract_chip(contract.id) \
            if hasattr(self.env['pb.pay.scales'], 'contract_chip') else None
        if chip:
            self.assertIn('Drifted', json.dumps(chip, default=str))

    # ================================================================ M2
    def _retro_fixture(self):
        if 'pb.retro.review' not in self.env:
            self.skipTest('Past-month re-work not installed')
        from odoo.addons.pb_retro.tests import test_retro as base
        B = base.TestW2d1Retro
        holder = type('H', (), {'_seq': 100})()
        holder.env = self.env
        holder.company = self.company
        holder.calendar = self.calendar
        holder.cat = {
            'earning': self.env.ref('om_hr_payroll.BASIC'),
            'deduction': self.env.ref('om_hr_payroll.DED'),
            'net': self.env.ref('om_hr_payroll.NET'),
            'employer_cost': self.env.ref('om_hr_payroll.COMP'),
        }
        for name in ('_scheme', '_rule', '_progressive', '_run', '_slip'):
            setattr(holder, name, getattr(B, name).__get__(holder))
        return base, holder

    def test_m2_past_dated_change_opens_a_rework_and_back_pay_still_sends(self):
        base, h = self._retro_fixture()
        cfg = h._progressive()
        emp, contract = self._person(wage=44_000_000.0)
        slips = [h._slip(cfg, emp, contract, p, {'BASICPAY': 44_000_000, 'LOANINST': 0.0})
                 for p in (base.SEP, base.OCT)]
        stored = {s.id: sorted((l.code, l.total) for l in s.line_ids) for s in slips}
        start = base.SEP[0]
        with patch.object(type(self.JC), '_wage_code', lambda s, c: 'BASICPAY'):
            rec = self._send(emp, change_pay=True, new_wage=50_000_000.0,
                             effective_date=fields.Date.to_string(start))
        self.assertEqual(rec.state, 'applied')
        self.assertEqual(len(rec.paid_months()), 2, rec.paid_months())
        # the dated wage row must read as "entered after the payslips" (W2D1-3)
        self.env['hr.contract.advantage.change'].sudo().search(
            [('contract_id', '=', contract.id)]).write(
            {'changed_at': fields.Datetime.now() + timedelta(days=1)})
        answer = self.Board.act(rec.id, 'rework')
        review = self.env['pb.retro.review'].browse(answer['review_id'])
        self.assertEqual(review.state, 'draft')
        self.assertEqual(review.employee_ids, emp)
        self.assertEqual(review.config_id, cfg)
        self.assertEqual((review.month_from, review.month_to), (base.SEP[0], base.OCT[0]))
        review.action_work_out()
        diffs = {}
        for row in review.slip_ids:
            for line in row.line_ids:
                diffs.setdefault(line.code, 0.0)
                diffs[line.code] += line.diff
        self.assertAlmostEqual(diffs.get('BASICPAY', 0.0), 12_000_000.0, delta=1.0,
                               msg="Sep + Oct at +6,000,000 each: %s" % diffs)
        if not hasattr(review, 'action_send_for_payment'):
            return   # before the Step 5 / back-pay merge
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'backpay')
        review.action_send_for_payment()
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'approved', review.person_ids.mapped('why'))
        entries = self.env['pb.retro.backpay'].sudo().search([('review_id', '=', review.id)])
        self.assertTrue(entries)
        self.assertEqual(entries.mapped('employee_id'), emp)
        for s in slips:
            s.invalidate_recordset()
            self.assertEqual(s.state, 'done')
            self.assertEqual(sorted((l.code, l.total) for l in s.line_ids), stored[s.id],
                             "paid payslips untouched")

    # ================================================================ M3
    def test_m3_transfer_and_cost_centre_history(self):
        if 'pb.cost.centre' not in self.env:
            self.skipTest('organisation module not installed')
        CC = self.env['pb.cost.centre']
        old = CC.create({'code': 'S8M-SHOP', 'name': 'S8M Shop costs',
                         'company_id': self.company.id})
        new = CC.create({'code': 'S8M-WH', 'name': 'S8M Warehouse costs',
                         'company_id': self.company.id})
        self.dept_b.pb_cost_centre_id = new.id
        emp, contract = self._person(costcenter='S8M-SHOP')
        today = self._today()
        last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        this_month = today.replace(day=1)
        rule = self.env['hr.salary.rule'].search([], limit=1)

        def slip(first, state):
            nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
            s = self.env['hr.payslip'].create({
                'name': 'S8M slip %s' % first, 'employee_id': emp.id,
                'contract_id': contract.id, 'date_from': first,
                'date_to': nxt - timedelta(days=1), 'company_id': self.company.id})
            self.env['hr.payslip.line'].create({
                'slip_id': s.id, 'name': 'Basic', 'code': 'BASIC', 'amount': 1.0,
                'quantity': 1.0, 'rate': 100.0, 'salary_rule_id': rule.id,
                'category_id': rule.category_id.id, 'contract_id': contract.id,
                'employee_id': emp.id})
            if state != 'draft':
                s.write({'state': state})
            return s
        done = slip(last_month, 'done')
        draft = slip(this_month, 'draft')
        self.env.flush_all()
        self.assertEqual(done.line_ids.costcenter, 'S8M-SHOP')
        rec = self._send(emp, reason_kind='transfer', new_department_id=self.dept_b.id)
        self.assertEqual(rec.state, 'applied')
        self.env.invalidate_all()
        self.assertEqual(contract.department_id, self.dept_b)
        self.assertEqual(contract.costcenter, 'S8M-SHOP',
                         "a transfer keeps the cost centre: only NEW contracts take the "
                         "team's usual one; moving people is dated, on the Jobs tab")
        self.assertEqual(contract.pb_cost_centre_id, old)
        self.assertEqual(done.line_ids.costcenter, 'S8M-SHOP')
        self.assertEqual(draft.line_ids.costcenter, 'S8M-SHOP')
        # the dated move (S8-C) after the transfer
        contract.with_context(pb_cost_centre_change_date=today).write(
            {'costcenter': new.code})
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(contract.pb_cost_centre_id, new)
        self.assertEqual(done.line_ids.costcenter, 'S8M-SHOP',
                         "CC1: a finished payslip keeps the cost centre it was paid under")
        self.assertEqual(draft.line_ids.costcenter, 'S8M-WH', "this month's draft follows")

    # ================================================================ M4
    def test_m4_shared_seams_table(self):
        desk = self.env['pb.records.desk']._master_fields()
        if 'pb.contract.rule' in self.env:
            self.assertIn('pb_fixed_term_before', desk['hr.employee'])
            self.assertIn('pb_fixed_term_months_before', desk['hr.employee'])
        flat = json.dumps(desk, default=str)
        self.assertIn('costcenter', flat, "the existing cost-centre box is still offered")
        C = self.env['hr.contract']
        if 'pb.pay.scale' in self.env:
            self.assertIn('pb_scale_state', C._fields)
            self.assertFalse(C._fields['pb_scale_state'].store)
        if 'pb.cost.centre' in self.env:
            self.assertTrue(C._fields['pb_cost_centre_id'].store)
        self.assertIn('job_change_id', self.env['pb.pay.apply']._fields)
        # _build_new_contract: only S8-B (pb_contract_rules) overrides it; S8-C must
        # not — the cost-centre text is already carried (CARRIED_FIELDS) and S8-C's
        # stored link follows the text on the new contract.
        if 'pb.contract.review' in self.env:
            from odoo.addons.pb_contract_lifecycle.models import contract_review
            self.assertIn('costcenter', contract_review.CARRIED_FIELDS)
            owners = sorted({cls.__module__.split('.')[2]
                             for cls in type(self.env['pb.contract.review']).__mro__
                             if '_build_new_contract' in vars(cls)
                             and cls.__module__.startswith('odoo.addons.')})
            self.assertEqual(owners, ['pb_contract_lifecycle', 'pb_contract_rules'], owners)
        if 'pb.cost.centre' in self.env:
            cc = self.env['pb.cost.centre'].create(
                {'code': 'S8M-REN', 'name': 'S8M renewals',
                 'company_id': self.company.id})
            _emp, fresh = self._person(costcenter='s8m-ren ')
            self.assertEqual(fresh.pb_cost_centre_id, cc,
                             "a contract carrying the text links to the list entry")
            if 'pb.pay.scale.placement' in self.env:
                self.assertFalse(self.env['pb.pay.scale.placement'].search(
                    [('contract_id', '=', fresh.id)]),
                    "a contract made with a wage is not placed on a scale by itself")
