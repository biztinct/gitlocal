# -*- coding: utf-8 -*-
"""WDGAP W3-B (owner ruling PRV1) — the yearly Pay Review waits for its start
date. Numbered as in the W3-B report (§3, PRV1 rows):

V1  future start date: Apply writes NOTHING on any contract, pay line, dated
    change or payslip; the review reads "Applies on <date>" with "Take it
    back"; the hourly job does nothing before the day and on the day writes
    every wage + ONE dated amount-change record each ("From the pay review",
    dated the start date); a second run writes nothing.
V2  today / past date: GOLDEN — the final wages are exactly what the old
    Apply writes (worked out by the old code on the same review, rolled
    back); plus one dated record each, dated the review's own start date;
    the 24-hour take-back stays and writes the way back as a dated record.
V3  take it back before the day: nothing had moved, the review is approved
    again and can be applied again; after the day it is refused in words.
V4  idempotent: Apply twice changes nothing (refused, zero writes); the job
    twice writes once; a person whose pay moved since Apply is skipped with
    the reason, never overwritten; Close waits for the day.
V5  a start date in a month already paid: "This change starts in a month
    already paid"; the button opens a NEW draft Past-month re-work for those
    people and months that finds the difference; C-6: no back-pay input is
    written, the paid payslips are byte-identical; a second press opens the
    same re-work; without the re-work module a calm note.
V6  a review with NO start date behaves exactly as before (golden), no dated
    record, no waiting rows.
V7  a group review over two companies in two currencies: each person's row
    keeps their own money, each contract gets its own figure on the day,
    nothing on the screen adds the two.
V8  a review applied by the old code is untouched: the job ignores it, its
    take-back writes no dated record.
"""
import re
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_pay.models.pb_pay_apply import PbPayApply as OldApply


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


class _Rollback(Exception):
    pass


@tagged('post_install', '-at_install', 'wdgap_w3b')
class TestW3bReviewWaits(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.company = cls.env['res.company'].create({
            'name': 'W3B Review Co', 'currency_id': cls.vnd.id,
            'country_id': cls.env.ref('base.vn').id})
        cls.company2 = cls.env['res.company'].create({
            'name': 'W3B Review Co USD', 'currency_id': cls.usd.id,
            'country_id': cls.env.ref('base.sg').id})
        cls.env.user.company_ids = [(4, cls.company.id), (4, cls.company2.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id, cls.company2.id],
            tracking_disable=True, mail_notrack=True))
        cls.Review = cls.env['pb.pay.review']
        cls.Apply = cls.env['pb.pay.apply']
        cls.Reviews = cls.env['pb.pay.reviews']
        cls.Raise = cls.env['pb.pay.scale.raise']
        cls.Change = cls.env['hr.contract.advantage.change']
        cls.today = cls.Raise._today_for(cls.company)
        cls._n = 0

    # ------------------------------------------------------------ fixtures
    def _person(self, wage, company=None):
        type(self)._n += 1
        company = company or self.company
        emp = self.env['hr.employee'].create({
            'name': 'W3B Person %s' % self._n, 'company_id': company.id})
        contract = self.env['hr.contract'].create({
            'name': 'W3B contract %s' % self._n, 'employee_id': emp.id,
            'wage': wage, 'state': 'open', 'date_start': '2025-01-01',
            'company_id': company.id})
        return emp, contract

    def _review(self, start, people, companies=None):
        """An APPROVED review with one row per (employee, contract, new wage)."""
        companies = companies or self.company
        review = self.Review.create({
            'name': 'W3B review %s' % self._n, 'scope_kind': 'company',
            'scope_ref': companies[:1].id, 'company_id': companies[:1].id,
            'company_ids': [(6, 0, companies.ids)],
            'currency_id': companies[:1].currency_id.id,
            'year': start.year, 'effective_date': start})
        for emp, contract, new in people:
            self.env['pb.pay.review.line'].create({
                'review_id': review.id, 'employee_id': emp.id,
                'contract_id': contract.id, 'company_id': contract.company_id.id,
                'currency_id': contract.company_id.currency_id.id,
                'current_wage': contract.wage, 'new_wage': new,
                'proposal_amount': new - contract.wage})
        review.sudo()._chain_state_write('approved')
        return review

    def _crowd(self):
        a = self._person(10_000_000.0)
        b = self._person(20_000_000.0)
        return [(a[0], a[1], 10_500_000.0), (b[0], b[1], 21_000_000.0)]

    @contextmanager
    def _on(self, day, code='BASIC'):
        Model = type(self.Raise)
        with patch.object(Model, '_today_for', lambda s, company=None: day), \
                patch.object(Model, '_wage_code', lambda s, e: code):
            yield

    def _changes(self, contracts):
        return self.Change.sudo().search([('contract_id', 'in', contracts.ids)])

    def _old_answer(self, review):
        """What the OLD Apply writes on this review, rolled back."""
        contracts = review.line_ids.mapped('contract_id')
        try:
            with self.env.cr.savepoint():
                OldApply.apply_review(self.Apply, review.id)
                self.env.flush_all()
                golden = {c.id: c.wage for c in contracts}
                raise _Rollback()
        except _Rollback:
            pass
        self.env.invalidate_all()
        return golden

    # ================================================================ V1
    def test_v1_future_date_waits_and_applies_on_the_day(self):
        crowd = self._crowd()
        contracts = self.env['hr.contract'].browse([c.id for _e, c, _w in crowd])
        start = self.today + timedelta(days=10)
        review = self._review(start, crowd)
        self.env.flush_all()
        with self._on(self.today):
            preview = self.Apply.preview_review(review.id)
            self.assertIn('Nothing is written today', preview['pbs_when'])
            with spy_writes(PAY_TABLES) as seen:
                answer = self.Reviews.apply(review.id)
                self.env.flush_all()
            self.assertEqual(seen, [], "nothing on a contract or payslip before the day")
            self.assertTrue(answer['scheduled'])
            self.assertIn('nothing changes until then', answer['sentence'])
            self.assertEqual(review.state, 'applied')
            rows = review.apply_ids
            self.assertEqual(set(rows.mapped('state')), {'scheduled'})
            self.assertEqual(sorted(rows.mapped('old_wage')), [10_000_000.0, 20_000_000.0])
            self.assertEqual([c.wage for c in contracts], [10_000_000.0, 20_000_000.0])
            self.assertFalse(self._changes(contracts))
            card = answer['card']
            self.assertTrue(card['state_label'].startswith('Applies on'))
            self.assertEqual(card['pbs_waits']['count'], 2)
            self.assertTrue(answer['actions']['undo'], "take it back until the day")
            self.assertFalse(answer['actions']['close'])
            # the job before the day does nothing
            with spy_writes(PAY_TABLES) as seen:
                self.assertFalse({k: v for k, v in self.Raise._cron_apply_due().items()
                                  if k.startswith('review_')})
                self.env.flush_all()
            self.assertEqual(seen, [])
        with self._on(start):
            tally = self.Raise._cron_apply_due()
            self.assertEqual(tally.get('review_started'), 1)
            self.env.invalidate_all()
            self.assertEqual([c.wage for c in contracts], [10_500_000.0, 21_000_000.0])
            self.assertEqual(set(review.apply_ids.mapped('state')), {'applied'})
            changes = self._changes(contracts)
            self.assertEqual(len(changes), 2, "one dated record each")
            self.assertEqual(set(changes.mapped('effective_date')), {start})
            self.assertEqual(set(changes.mapped('change_source')), {'pay_review'})
            self.assertEqual(set(changes.mapped('advantage_template_code')), {'BASIC'})
            self.assertEqual(sorted((c.old_amount, c.new_amount) for c in changes),
                             [(10_000_000.0, 10_500_000.0), (20_000_000.0, 21_000_000.0)])
            self.assertFalse(self.Reviews._card(review).get('pbs_waits'))
            # the job again: nothing
            with spy_writes(PAY_TABLES) as seen:
                self.Raise._cron_apply_due()
                self.env.flush_all()
            self.assertEqual(seen, [], "twice is once")
        # the take-back window closed on the day
        with self.assertRaises(UserError):
            self.Reviews.undo(review.id)

    # ================================================================ V2
    def test_v2_today_and_past_dates_are_golden(self):
        for start in (self.today, self.today - timedelta(days=40)):
            crowd = self._crowd()
            contracts = self.env['hr.contract'].browse([c.id for _e, c, _w in crowd])
            review = self._review(start, crowd)
            golden = self._old_answer(review)
            self.assertEqual(sorted(golden.values()), [10_500_000.0, 21_000_000.0])
            with self._on(self.today):
                answer = self.Reviews.apply(review.id)
            self.assertFalse(answer.get('scheduled'))
            self.env.invalidate_all()
            self.assertEqual({c.id: c.wage for c in contracts}, golden,
                             "the same final wages as the old Apply")
            rows = review.apply_ids
            self.assertEqual(set(rows.mapped('state')), {'applied'})
            self.assertTrue(all(r.undo_until for r in rows), "the 24-hour take-back stays")
            changes = self._changes(contracts)
            self.assertEqual(len(changes), 2)
            self.assertEqual(set(changes.mapped('effective_date')), {start},
                             "dated the review's own start date")
            self.assertEqual(set(rows.mapped('pbs_change_id').ids), set(changes.ids))
            # take it back within the day: old wages, and the way back is dated too
            with self._on(self.today):
                self.Reviews.undo(review.id)
            self.env.invalidate_all()
            self.assertEqual(sorted(c.wage for c in contracts), [10_000_000.0, 20_000_000.0])
            self.assertEqual(review.state, 'approved')
            back = self._changes(contracts) - changes
            self.assertEqual(sorted((c.old_amount, c.new_amount) for c in back),
                             [(10_500_000.0, 10_000_000.0), (21_000_000.0, 20_000_000.0)])
            self.assertEqual(set(back.mapped('effective_date')), {start})

    def test_v2b_no_wage_input_no_dated_record(self):
        crowd = self._crowd()
        contracts = self.env['hr.contract'].browse([c.id for _e, c, _w in crowd])
        review = self._review(self.today, crowd)
        with self._on(self.today, code=''):
            self.Reviews.apply(review.id)
        self.assertEqual(sorted(c.wage for c in contracts), [10_500_000.0, 21_000_000.0])
        self.assertFalse(self._changes(contracts))

    # ================================================================ V3
    def test_v3_take_back_before_the_day(self):
        crowd = self._crowd()
        contracts = self.env['hr.contract'].browse([c.id for _e, c, _w in crowd])
        start = self.today + timedelta(days=5)
        review = self._review(start, crowd)
        with self._on(self.today):
            self.Reviews.apply(review.id)
            with spy_writes(PAY_TABLES) as seen:
                answer = self.Reviews.undo(review.id)
                self.env.flush_all()
            self.assertEqual(seen, [])
            self.assertIn("Nobody's pay changed", answer['sentence'])
            self.assertEqual(review.state, 'approved')
            self.assertEqual(set(review.apply_ids.mapped('state')), {'undone'})
        with self._on(start):
            self.Raise._cron_apply_due()
        self.env.invalidate_all()
        self.assertEqual(sorted(c.wage for c in contracts), [10_000_000.0, 20_000_000.0],
                         "a taken-back review is never written")
        # applied again, then too late to take back
        with self._on(self.today):
            self.Reviews.apply(review.id)
            review.sudo().undo_until = fields.Datetime.now() - timedelta(minutes=1)
            with self.assertRaises(UserError) as caught:
                self.Reviews.undo(review.id)
            self.assertIn('can no longer be taken back', str(caught.exception))

    # ================================================================ V4
    def test_v4_idempotent_and_moved_since(self):
        crowd = self._crowd()
        (emp_a, con_a, _na), (emp_b, con_b, _nb) = crowd
        start = self.today + timedelta(days=3)
        review = self._review(start, crowd)
        with self._on(self.today):
            self.Reviews.apply(review.id)
            with spy_writes(PAY_TABLES + ('pb_pay_apply',)) as seen:
                with self.assertRaises(UserError):
                    self.Reviews.apply(review.id)
                self.env.flush_all()
            self.assertEqual(seen, [], "Apply twice changes nothing")
            with self.assertRaises(UserError):
                review.action_close()
        # somebody changed B's pay in between
        con_b.sudo().write({'wage': 22_000_000.0})
        with self._on(start):
            self.Raise._cron_apply_due()
            self.env.invalidate_all()
            self.assertEqual(con_a.wage, 10_500_000.0)
            self.assertEqual(con_b.wage, 22_000_000.0, "never overwritten")
            row_b = review.apply_ids.filtered(lambda r: r.employee_id == emp_b)
            self.assertEqual(row_b.state, 'skipped')
            self.assertIn('changed since', row_b.note)
            card = self.Reviews._card(review)
            self.assertEqual(card['pbs_skipped']['count'], 1)
            self.assertEqual(len(self._changes(con_a | con_b)), 1)
            with spy_writes(PAY_TABLES) as seen:
                self.Raise._cron_apply_due()
                self.env.flush_all()
            self.assertEqual(seen, [])
            review.action_close()
            self.assertEqual(review.state, 'closed')

    # ================================================================ V5
    def test_v5_month_already_paid_offers_the_rework(self):
        if 'pb.retro.review' not in self.env:
            self.skipTest('Past-month re-work not installed')
        from odoo.addons.pb_retro.tests import test_retro as base
        B = base.TestW2d1Retro
        holder = type('H', (), {'_seq': 700})()
        holder.env = self.env
        holder.company = self.company
        holder.calendar = self.company.resource_calendar_id or self.env['resource.calendar'].create(
            {'name': 'W3B Hours', 'company_id': self.company.id})
        holder.cat = {
            'earning': self.env.ref('om_hr_payroll.BASIC'),
            'deduction': self.env.ref('om_hr_payroll.DED'),
            'net': self.env.ref('om_hr_payroll.NET'),
            'employer_cost': self.env.ref('om_hr_payroll.COMP'),
        }
        for name in ('_scheme', '_rule', '_progressive', '_run', '_slip'):
            setattr(holder, name, getattr(B, name).__get__(holder))
        cfg = holder._progressive()
        emp, contract = self._person(44_000_000.0)
        emp.sudo().write({'pb_paid_by_id': cfg.id})
        slips = [holder._slip(cfg, emp, contract, p, {'BASICPAY': 44_000_000, 'LOANINST': 0.0})
                 for p in (base.SEP, base.OCT)]
        stored = {s.id: sorted((l.code, l.total) for l in s.line_ids) for s in slips}
        review = self._review(base.SEP[0], [(emp, contract, 48_400_000.0)])
        now = base.OCT[1] + timedelta(days=5)
        with self._on(now, code='BASICPAY'):
            answer = self.Reviews.apply(review.id)
        self.assertIn('month already paid', answer['note'])
        contract.invalidate_recordset()
        self.assertEqual(contract.wage, 48_400_000.0)
        card = self.Reviews._card(review)
        paid = card['pbs_paid']
        self.assertEqual(paid['sentence'], "This change starts in a month already paid.")
        self.assertEqual(paid['people'], 1)
        self.assertTrue(paid['can_rework'])
        self.assertFalse(self.env['hr.payroll.retro.adjustment'].sudo().search(
            [('original_payslip_id', 'in', [s.id for s in slips])]), "C-6: no back-pay input")
        # the dated record was entered after the payslips were worked out
        self.Change.sudo().search([('contract_id', '=', contract.id)]).write(
            {'changed_at': fields.Datetime.now() + timedelta(days=1)})
        opened = self.Reviews.pbs_open_rework(review.id)
        rework = self.env['pb.retro.review'].browse(opened['review_id'])
        self.assertEqual(rework.state, 'draft')
        self.assertEqual(rework.employee_ids, emp)
        rework.action_work_out()
        diff = sum(line.diff for row in rework.slip_ids for line in row.line_ids
                   if line.code == 'BASICPAY')
        self.assertAlmostEqual(diff, 8_800_000.0, delta=1.0,
                               msg="Sep + Oct at +4,400,000 each")
        for s in slips:
            s.invalidate_recordset()
            self.assertEqual(sorted((l.code, l.total) for l in s.line_ids), stored[s.id])
        self.assertEqual(self.Reviews.pbs_open_rework(review.id)['review_id'], rework.id)
        self.assertTrue(self.Reviews._card(review)['pbs_paid']['rework_made'])
        # without the re-work module: a calm note, and the door says so
        with patch.object(type(self.Raise), '_retro_installed', lambda s: False):
            note = self.Reviews._card(review)['pbs_paid']
            self.assertFalse(note['can_rework'])
            self.assertIn('by hand on the next pay run', note['note'])
            with self.assertRaises(UserError):
                self.Reviews.pbs_open_rework(review.id)

    # ================================================================ V6
    def test_v6_no_start_date_is_golden(self):
        crowd = self._crowd()
        contracts = self.env['hr.contract'].browse([c.id for _e, c, _w in crowd])
        review = self._review(self.today + timedelta(days=9), crowd)
        # The field is required today; force the "no date" shape on this copy.
        self.env.flush_all()
        self.env.cr.execute('ALTER TABLE pb_pay_review ALTER COLUMN effective_date '
                            'DROP NOT NULL')
        self.env.cr.execute('UPDATE pb_pay_review SET effective_date = NULL WHERE id = %s',
                            [review.id])
        self.env.invalidate_all()
        self.assertFalse(review.effective_date)
        golden = self._old_answer(review)
        with self._on(self.today):
            self.Apply.apply_review(review.id)
        self.env.invalidate_all()
        self.assertEqual({c.id: c.wage for c in contracts}, golden)
        self.assertEqual(set(review.apply_ids.mapped('state')), {'applied'})
        self.assertFalse(self._changes(contracts), "no dated record without a date")

    # ================================================================ V7
    def test_v7_group_review_two_currencies(self):
        vn = self._person(10_000_000.0)
        sg = self._person(4_000.0, company=self.company2)
        start = self.today + timedelta(days=7)
        review = self._review(start, [(vn[0], vn[1], 10_600_000.0),
                                      (sg[0], sg[1], 4_200.0)],
                              companies=self.company | self.company2)
        with self._on(self.today):
            answer = self.Reviews.apply(review.id)
        rows = review.apply_ids
        self.assertEqual({r.employee_id.id: r.currency_id for r in rows},
                         {vn[0].id: self.vnd, sg[0].id: self.usd})
        waits = answer['card']['pbs_waits']
        self.assertEqual(set(waits), {'day', 'label', 'count', 'note'},
                         "a count and a date, never an added-up amount")
        with self._on(start):
            self.Raise._cron_apply_due()
        self.env.invalidate_all()
        self.assertEqual((vn[1].wage, sg[1].wage), (10_600_000.0, 4_200.0))
        changes = self._changes(vn[1] | sg[1])
        self.assertEqual(sorted(changes.mapped('new_amount')), [4_200.0, 10_600_000.0])

    # ================================================================ V8
    def test_v8_a_review_applied_before_is_untouched(self):
        crowd = self._crowd()
        contracts = self.env['hr.contract'].browse([c.id for _e, c, _w in crowd])
        review = self._review(self.today + timedelta(days=20), crowd)
        OldApply.apply_review(self.Apply, review.id)          # the old code, at once
        self.env.flush_all()
        with self._on(self.today + timedelta(days=20)):
            with spy_writes(PAY_TABLES + ('pb_pay_apply',)) as seen:
                self.Raise._cron_apply_due()
                self.env.flush_all()
            self.assertEqual(seen, [], "the job never reads an old review")
        self.assertEqual(self.Reviews._card(review).get('pbs_waits'), None)
        with self._on(self.today):
            self.Reviews.undo(review.id)
        self.assertEqual(sorted(c.wage for c in contracts), [10_000_000.0, 20_000_000.0])
        self.assertFalse(self._changes(contracts), "no dated record for an old review")
