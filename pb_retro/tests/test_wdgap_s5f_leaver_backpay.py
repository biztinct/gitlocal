# -*- coding: utf-8 -*-
"""WDGAP S5-F — a leaver's back pay goes into their final payslip (owner
rulings BP1 and BP2, 2026-11-16).

Every case sends the re-work as of 20 November 2026 (frozen only around the
send, so the fixtures' own timestamps stay real); the leaver's last day is
15 November 2026, after the re-worked months August–October.

F01 a leaver with a final payslip still to come: payable ("final"), the
    approval says "Final payslip", the screen "Will be paid in their final
    payslip"; the November (final) payslip takes the back pay exactly like
    anyone's (lines, take-home); finished -> paid, the re-work closes
F02 a negative difference that fits: taken, lowers take-home, paid
F03 a negative difference that does NOT fit (BP2 whole months): the oldest
    months that fit are taken, the rest waits; the run review and the screen
    say the final payslip does not take all of it — settle it by hand; the
    rest can be cancelled with a reason
F04 no payslip to come -> "not paid automatically", reason "Has left":
    left inside the re-worked months; their own final payslip already
    finished; the scheme's run of their last month finished without them;
    archived with nothing made. Archived WITH an unfinished regular payslip
    made -> paid in it
F05 the check is live: payable while the final payslip is to come, "Has
    left" once it is finished (what approval re-checks before making entries)
F06 the paid-once matrix for the leaver: compute / recompute (identical) /
    a second regular payslip of the month (nothing) / done -> paid / set back
    -> held / cancel -> open (still to come) / taken again / delete -> open /
    run delete -> open
F07 Extra and top-up payslips of a leaver never take it
F08 golden: a leaver with no back pay -> payslip byte-identical with the
    back-pay seam switched off, nothing written
F09 the people who have not left are untouched ("next pay run")
"""
from datetime import date

from freezegun import freeze_time

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.formula_engine.excel_semantics import excel_round
from odoo.addons.pb_retro.tests import test_retro as base
from odoo.addons.pb_retro.tests import test_wdgap_w2d2_backpay as w2d2

AUG, SEP, OCT = base.AUG, base.SEP, base.OCT
NOV = w2d2.NOV
hand = base.hand
B = base.TestW2d1Retro
W = w2d2.TestW2d2Backpay
LEFT_ON = date(2026, 11, 15)
SEND_ON = '2026-11-20 09:00:00'
SETTLE = "The final payslip does not take all of it"


@tagged('post_install', '-at_install', 'pb_retro', 'wdgap_s5f')
class TestS5fLeaverBackpay(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.company = cls.env['res.company'].create({'name': 'S5F Leaver Co',
                                                     'currency_id': cls.vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        cls.Review = cls.env['pb.retro.review']
        cls.Board = cls.env['pb.retro.board']
        cls.Entry = cls.env['pb.retro.backpay']
        cls.cat = {
            'earning': cls.env.ref('om_hr_payroll.BASIC'),
            'deduction': cls.env.ref('om_hr_payroll.DED'),
            'net': cls.env.ref('om_hr_payroll.NET'),
            'employer_cost': cls.env.ref('om_hr_payroll.COMP'),
        }
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'S5F Hours', 'company_id': cls.company.id})
        cls._seq = 0
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, 'backpay')

    # the D1 / D2 fixtures, borrowed (ledger W2BM-3: functions, not the class)
    _scheme = B._scheme
    _rule = B._rule
    _progressive = B._progressive
    _person = B._person
    _run = B._run
    _slip = B._slip
    _change = B._change
    _row = B._row
    _review = W._review
    _rise = W._rise
    _current = W._current
    _compute = W._compute
    _snap = W._snap
    _bp = W._bp
    _own = W._own
    _writes = W._writes

    # ------------------------------------------------------------ helpers
    def _send(self, review):
        with freeze_time(SEND_ON):
            review.action_send_for_payment()
        review.invalidate_recordset()
        return review

    def _check(self, review):
        with freeze_time(SEND_ON):
            return {c['employee'].id: (c['status'], c['why']) for c in review._pb_pay_check()}

    def _leave(self, emp, on=LEFT_ON, archive=False):
        emp.departure_date = on
        if archive:
            emp.active = False

    def _person_row(self, review, emp):
        pay = self.Board.get_review(review.id)['payment']
        return next(p for p in pay['people'] if p['employee_id'] == emp.id)

    def _simple(self):
        cfg = self._scheme()
        b = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning').column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s' % b, role='net', seq=30)
        return cfg

    # =====================================================================
    def test_F01_leaver_paid_in_the_final_payslip(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._leave(emp)
        self._send(review)
        self.assertEqual(review.pay_state, 'approved')
        person = review.person_ids
        self.assertEqual((person.status, person.why), ('payable', 'final'))
        detail = review._approval_detail(None)
        self.assertEqual(detail['rows'][0]['cells'][1], 'Final payslip')
        self.assertEqual(self._person_row(review, emp)['where'],
                         'Will be paid in their final payslip')
        entries = review.backpay_ids
        self.assertEqual(set(entries.mapped('state')), {'open'})
        final = self._current(cfg, emp, contract)
        old, new = hand(44_000_000), hand(50_000_000)
        for code in ('BASICPAY', 'SIEMP', 'PITAX', 'SICOMP'):
            self.assertAlmostEqual(self._bp(final, code).total,
                                   3 * excel_round(new[code] - old[code]), places=2, msg=code)
        back_net = 3 * excel_round(new['NETPAY'] - old['NETPAY'])
        self.assertAlmostEqual(final.pb_backpay_net, back_net, places=2)
        self.assertAlmostEqual(final.pb_net_amount(),
                               excel_round(hand(50_000_000)['NETPAY']) + back_net, places=2)
        self.assertEqual(set(entries.mapped('state')), {'reserved'})
        self.assertIn(final.payslip_run_id.name, self._person_row(review, emp)['where'])
        final.write({'state': 'done'})
        self.assertEqual(set(entries.mapped('state')), {'paid'})
        review.invalidate_recordset()
        self.assertEqual((review.pay_state, review.state), ('paid', 'closed'))

    def test_F02_negative_difference_that_fits(self):
        cfg, people, review = self._rise(old=30_000_000, new=27_000_000)
        (emp, contract, _slips), = people
        self._leave(emp)
        self._send(review)
        self.assertEqual(review.person_ids.why, 'final')
        final = self._current(cfg, emp, contract, inputs={'BASICPAY': 30_000_000,
                                                          'LOANINST': 0.0})
        old, new = hand(30_000_000), hand(27_000_000)
        net = 3 * excel_round(new['NETPAY'] - old['NETPAY'])
        self.assertLess(net, 0)
        self.assertAlmostEqual(final.pb_backpay_net, net, places=2)
        self.assertGreaterEqual(final.pb_net_amount(), 0)
        self.assertEqual(set(review.backpay_ids.mapped('state')), {'reserved'})
        final.write({'state': 'done'})
        self.assertEqual(set(review.backpay_ids.mapped('state')), {'paid'})

    def test_F03_negative_that_does_not_fit_is_settled_by_hand(self):
        cfg = self._simple()
        emp, contract = self._person()
        for p in (AUG, SEP, OCT):
            self._slip(cfg, emp, contract, p, {'BASICPAY': 10_000_000})
        self._change(contract, 'BASICPAY', 10_000_000, 6_000_000, AUG[0])
        review = self._review(cfg, AUG[0], OCT[0])
        review.action_work_out()
        self._leave(emp)
        self._send(review)
        self.assertEqual(review.person_ids.why, 'final')
        final = self._current(cfg, emp, contract, inputs={'BASICPAY': 9_000_000})
        entries = review.backpay_ids
        took = entries.filtered(lambda e: e.state == 'reserved')
        self.assertEqual(sorted(set(took.mapped('month'))), [AUG[0], SEP[0]],
                         'whole months, oldest first, while take-home stays at or above zero')
        self.assertAlmostEqual(final.pb_net_amount(), 1_000_000, places=2)
        rest = entries.filtered(lambda e: e.state == 'open')
        self.assertEqual(set(rest.mapped('month')), {OCT[0]})
        note = final.payslip_run_id.pb_review_flags()[final.id].get('note', '')
        self.assertIn('does not fit in this final payslip', note)
        self.assertNotIn('waits for the next pay run', note)
        final.write({'state': 'done'})
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'partly')
        self.assertFalse(review._pb_final_payslip_to_come(emp))
        row = self._person_row(review, emp)
        self.assertTrue(row['where'].startswith(SETTLE), row['where'])
        self.assertTrue(row['can_cancel'])
        review.action_cancel_backpay('Settled by hand in the leaving papers',
                                     employee_ids=[emp.id])
        self.assertEqual(set(rest.mapped('state')), {'cancelled'})
        self.assertEqual(set(took.mapped('state')), {'paid'})
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'paid')

    def test_F04_no_payslip_to_come_stays_not_payable(self):
        cfg, people, review = self._rise(people=5)
        (e1, _c1, _s1), (e2, c2, _s2), (e3, _c3, _s3), (e4, _c4, _s4), (e5, c5, _s5) = people
        # e1 left inside the re-worked months
        self._leave(e1, on=date(2026, 10, 20))
        # e2's own final payslip (November) is already finished
        self._leave(e2)
        self._slip(cfg, e2, c2, NOV, {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
        # e3: archived, nothing made
        self._leave(e3, archive=True)
        # e5: archived, but an unfinished regular November payslip is made
        self._leave(e5, archive=True)
        draft = self._current(cfg, e5, c5)
        self.assertFalse(draft.line_ids.filtered('pb_backpay'))
        check = self._check(review)
        self.assertEqual(check[e1.id], ('not_payable', 'left'))
        self.assertEqual(check[e2.id], ('not_payable', 'left'))
        self.assertEqual(check[e3.id], ('not_payable', 'left'))
        self.assertEqual(check[e4.id], ('payable', False))
        self.assertEqual(check[e5.id], ('payable', 'final'))
        self.assertEqual(review._pb_why_text('left'), 'Has left — not paid automatically')
        # the scheme's November run finished without the leaver: nothing to come
        cfg2, people2, r2 = self._rise()
        (e6, _c6, _s6), = people2
        self._leave(e6)
        self.assertEqual(self._check(r2)[e6.id], ('payable', 'final'))
        stranger, sc = self._person()
        self._slip(cfg2, stranger, sc, NOV, {'BASICPAY': 1.0, 'LOANINST': 0.0})
        self.assertEqual(self._check(r2)[e6.id], ('not_payable', 'left'))

    def test_F05_the_check_is_live(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._leave(emp)
        self.assertEqual(self._check(review)[emp.id], ('payable', 'final'))
        final = self._current(cfg, emp, contract)
        self.assertEqual(self._check(review)[emp.id], ('payable', 'final'),
                         'an unfinished final payslip will still take it')
        final.write({'state': 'done'})
        self.assertEqual(self._check(review)[emp.id], ('not_payable', 'left'),
                         'finished without it: approval would make no entry for them')

    def test_F06_reservation_matrix_for_a_leaver(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._leave(emp)
        self._send(review)
        entries = review.backpay_ids
        final = self._current(cfg, emp, contract)
        first = self._snap(final)
        self.assertEqual(entries.mapped('payslip_id'), final)
        self._compute(final, {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
        self.assertEqual(self._snap(final), first, 'recompute replaces, never doubles')
        dup = self._current(cfg, emp, contract)
        self.assertFalse(dup.line_ids.filtered('pb_backpay'))
        dup.unlink()
        final.write({'state': 'done'})
        self.assertEqual(set(entries.mapped('state')), {'paid'})
        final.write({'state': 'draft'})
        self.assertEqual(set(entries.mapped('state')), {'reserved'})
        self._compute(final, {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
        self.assertEqual(self._snap(final), first)
        final.write({'state': 'cancel'})
        self.assertEqual(set(entries.mapped('state')), {'open'})
        self.assertTrue(review._pb_final_payslip_to_come(emp))
        self.assertEqual(self._person_row(review, emp)['where'],
                         'Will be paid in their final payslip')
        again = self._current(cfg, emp, contract)
        self.assertEqual(entries.mapped('payslip_id'), again)
        again.unlink()
        self.assertEqual(set(entries.mapped('state')), {'open'})
        third = self._current(cfg, emp, contract)
        run = third.payslip_run_id
        self.assertEqual(set(entries.mapped('state')), {'reserved'})
        run.slip_ids.write({'state': 'draft'})
        run.unlink()
        self.assertEqual(set(entries.mapped('state')), {'open'})

    def test_F07_extra_and_topup_never_take_it(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._leave(emp)
        self._send(review)
        for kind in ('extra', 'topup'):
            slip = self._current(cfg, emp, contract, kind=kind)
            self.assertFalse(slip.line_ids.filtered('pb_backpay'), kind)
            self.assertFalse(slip.pb_backpay_net, kind)
        self.assertEqual(set(review.backpay_ids.mapped('state')), {'open'})

    def test_F08_golden_leaver_without_back_pay(self):
        from unittest.mock import patch
        cfg = self._progressive()
        emp, contract = self._person()
        self._leave(emp)
        slip = self._current(cfg, emp, contract)
        with_seam = (self._snap(slip), slip.pb_backpay_net, slip.pb_backpay_note,
                     slip.line_ids.pb_pay_totals())
        with patch.object(type(self.env['hr.payslip']), '_pb_backpay_apply',
                          lambda self, fresh=True: None):
            self._compute(slip, {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
            without = (self._snap(slip), slip.pb_backpay_net, slip.pb_backpay_note,
                       slip.line_ids.pb_pay_totals())
        self.assertEqual(with_seam, without)
        with self._writes() as seen:
            slip._pb_backpay_apply(fresh=True)
        self.assertFalse([t for t in seen if t[1] in ('hr_payslip', 'hr_payslip_line',
                                                      'pb_retro_backpay')], seen)

    def test_F09_people_who_have_not_left_are_untouched(self):
        cfg, people, review = self._rise(people=2)
        (stay, _c1, _s1), (go, _c2, _s2) = people
        self._leave(go)
        self._send(review)
        by = {p.employee_id: p for p in review.person_ids}
        self.assertEqual((by[stay].status, by[stay].why), ('payable', False))
        self.assertEqual((by[go].status, by[go].why), ('payable', 'final'))
        self.assertEqual(self._person_row(review, stay)['where'],
                         'Will be paid in the next pay run')
        # a leaving date still ahead is not "has left": as before
        cfg2, people2, r2 = self._rise()
        (later, _c, _s), = people2
        self._leave(later, on=date(2026, 12, 31))
        self.assertEqual(self._check(r2)[later.id], ('payable', False))
