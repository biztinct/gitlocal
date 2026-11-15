# -*- coding: utf-8 -*-
"""WDGAP W2 merge — seams between PR-E, W2-A and W2-C (deploy handover §1).

b  W2-A's running totals (``history.ytd`` / ``history.mtd``) read the loan
   instalment as it stands on the finished payslip: when PR-E cut it so
   take-home is not below zero, the total carries the CUT amount.
c  W2-C's take-home calculator on a person with a running loan takes the
   loan input exactly as the payslip had it (the cut amount): no second
   reduction pass inside the solver, no loan plan read, no reservation
   touched, nothing written.
d  W2-A's deliberate change (an Extra-run payslip counts once in the
   year-to-date chain instead of stopping it) holds with PR-D's Extra run
   made the ordinary way (the run's kind set on create) and the payslips
   computed by the real engine.

PR-B's fixture (``LoansFixture``): one month-end scheme in ₫,
PRBNET = BASIC + HOLGIFT − PRBLOANIN, BASIC = contract wage.
"""
import re
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from odoo.sql_db import Cursor
from odoo.tests import tagged

from .test_loans import LoansFixture


@tagged('post_install', '-at_install', 'pb_loans', 'wdgap_w2m')
class TestW2MergeSeams(LoansFixture):

    def _ask(self, key, employee, start, cfg=None):
        cfg = cfg or self.monthly
        if not hasattr(cfg, '_pb_tax_year_bounds'):
            self.skipTest('running totals follow the tax year only with W2-A')
        contract = self.contracts[employee.id]
        with cfg._application_memo():
            return cfg._application_history_value(key, employee, contract, start)

    def _done(self, slip):
        slip.write({'state': 'done'})
        slip.invalidate_recordset()
        return slip

    # ================================================================ b
    def test_b_ytd_reads_the_cut_instalment(self):
        self.bob.date_of_joining = date(2026, 3, 1)
        loan = self.loan(self.bob, amount=30_000_000, each=15_000_000)
        slip = self.slip(self.bob, self.make_run())
        self.assertEqual(self.inputs(slip)[0]['PRBLOANIN'], 10_000_000.0, "PR-E cut it")
        self.assertEqual(slip.pb_net_amount(), 0.0)
        self._done(slip)
        self.assertEqual(loan.balance, 20_000_000)
        ytd = self._ask('history.ytd.PRBLOANIN', self.bob, date(2026, 4, 1))
        self.assertEqual((ytd['status'], ytd['value']), ('resolved', 10_000_000.0),
                         "the year-to-date total reads what the payslip took")
        rep = self._ask('history.ytd.PRBLOANREP', self.bob, date(2026, 4, 1))
        self.assertEqual((rep['status'], rep['value']), ('resolved', -10_000_000.0))
        net = self._ask('history.ytd.PRBNET', self.bob, date(2026, 4, 1))
        self.assertEqual((net['status'], net['value']), ('resolved', 0.0))
        # month-to-date for an Extra-run payslip of March reads the same
        mtd = self._ask('history.mtd.PRBLOANIN', self.bob, date(2026, 3, 1))
        self.assertEqual((mtd['status'], mtd['value']), ('resolved', 10_000_000.0))

    # ================================================================ c
    @contextmanager
    def _no_writes(self):
        seen = []
        real = Cursor.execute

        def spy(cr, query, params=None, log_exceptions=True):
            text = query.code if hasattr(query, 'code') else str(query)
            if re.match(r'\s*(INSERT|UPDATE|DELETE)\b', text, re.I):
                seen.append(text[:160])
            return real(cr, query, params, log_exceptions)

        self.env.flush_all()
        with patch.object(Cursor, 'execute', spy):
            yield seen
            self.env.flush_all()

    def test_c_take_home_calculator_takes_the_loan_as_the_payslip_had_it(self):
        Studio = self.env['pb.formula.studio'] if 'pb.formula.studio' in self.env else None
        if Studio is None or not hasattr(Studio, 'take_home_solve'):
            self.skipTest('the take-home calculator (W2-C) is not installed')
        loan = self.loan(self.bob, amount=30_000_000, each=15_000_000)
        slip = self.slip(self.bob, self.make_run())
        self.assertEqual(self.inputs(slip)[0]['PRBLOANIN'], 10_000_000.0)
        lines = loan.repayment_ids
        before = [(l.id, l.state, l.amount, l.payslip_id.id) for l in lines]
        stamps = (slip.write_date, slip.formula_input_values, slip.pb_loan_cut,
                  loan.write_date)
        Plan = type(self.env['pb.loan'])
        real_plan = Plan._plan_for_slip
        plan_calls = []

        def counting(model, *args, **kwargs):
            plan_calls.append(args[:1])
            return real_plan(model, *args, **kwargs)

        with self._no_writes() as seen, patch.object(Plan, '_plan_for_slip', counting):
            ctx = Studio.take_home_open(self.monthly.id, payslip_id=slip.id)
            out = Studio.take_home_solve(self.monthly.id, 5_000_000, 'BASIC',
                                         payslip_id=slip.id)
        self.assertEqual(seen, [], "nothing written by the calculator")
        self.assertEqual(plan_calls, [], "the loan plan is never asked again")
        self.assertTrue(ctx.get('ok', True), ctx)
        # with the instalment as the payslip had it (₫10,000,000 after the
        # cut) take-home 5,000,000 needs BASIC 15,000,000; a second floor
        # pass or a fresh plan (₫15,000,000) would answer 20,000,000.
        self.assertEqual(out['outcome'], 'exact', out)
        self.assertEqual(out['value'], 15_000_000.0)
        self.env.invalidate_all()
        self.assertEqual(before, [(l.id, l.state, l.amount, l.payslip_id.id)
                                  for l in loan.repayment_ids])
        self.assertEqual(stamps, (slip.write_date, slip.formula_input_values,
                                  slip.pb_loan_cut, loan.write_date))
        self.assertEqual(self.live(loan).amount, 10_000_000.0, "reservation unchanged")

    # ================================================================ d
    def test_d_extra_run_counts_once_in_the_year_to_date_chain(self):
        if 'extra' not in [k for k, _l in (self.env['hr.payslip.run']._fields[
                'pb_run_kind'].selection or [])]:
            self.skipTest('pb_payruns has no Extra run kind')
        self.ann.date_of_joining = date(2026, 3, 1)
        march = self._done(self.slip(self.ann, self.make_run()))
        extra_run = self.make_run(name='W2M extra March', kind='extra')
        self.assertEqual(extra_run.pb_run_kind, 'extra')
        extra = self.slip(self.ann, extra_run)
        self.assertEqual(self.inputs(extra)[0].get('PRBLOANIN') or 0.0, 0.0)
        self._done(extra)
        april = self._done(self.slip(self.ann, self.make_run(
            ds='2026-04-01', de='2026-04-30', name='W2M April')))
        basic = lambda s: s.line_ids.filtered(lambda l: l.code == 'BASIC').total  # noqa: E731
        expected = basic(march) + basic(extra) + basic(april)
        self.assertEqual(expected, 30_000_000.0)
        ytd = self._ask('history.ytd.BASIC', self.ann, date(2026, 5, 1))
        self.assertEqual((ytd['status'], ytd['value']), ('resolved', expected),
                         "the Extra-run payslip counts once and does not break the chain")
        self.assertEqual(ytd['evidence'].get('additional_payslips'), 1)
        # a second REGULAR payslip for March still stops the chain
        self._done(self.slip(self.ann, self.make_run(name='W2M March again')))
        ytd = self._ask('history.ytd.BASIC', self.ann, date(2026, 5, 1))
        self.assertEqual(ytd['status'], 'conflict')
