# -*- coding: utf-8 -*-
"""WDGAP PR-B — loans and salary advances (handover §4, T1–T14).

A company of its own (VND, smallest unit ₫1), with one month-end scheme:

    PRB Monthly (end of month):
        PRBBASE   input    earning   (basic pay, from the contract wage)
        PRBLOANIN input    deduction (receives the instalment — the setting)
        HOLGIFT  input    earning   (a one-off pay item, for T12)
        PRBLOANREP formula =-PRBLOANIN        (the scheme decides the sign)
        PRBNET     formula =BASIC+HOLGIFT+PRBLOANREP   (net)
    PRB Second (end of month): the same shape, for "another scheme" (T5)
    PRB Advance (mid-month): never takes an instalment

Every payslip is computed through the real seams (`compute_sheet`, the pay
data file through `pb.payrun.wizard.attach_spreadsheet`,
`action_recompute_formula_lines`).
"""
import base64
import io
import json

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

try:
    import openpyxl
except ImportError:            # pragma: no cover
    openpyxl = None

MAR = '2026-03-01'


def xlsx_b64(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


class LoansFixture(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        vnd.active = True
        cls.vnd = vnd
        cls.company = cls.env['res.company'].create(
            {'name': 'PRB Loans Co', 'currency_id': vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        for process in ('loan', 'runonly', 'loads', 'records', 'schememap'):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, process)
            except Exception:   # noqa: BLE001
                pass
        cls.Loan = cls.env['pb.loan']
        cls.Line = cls.env['pb.loan.repayment']
        cls.Board = cls.env['pb.loans']
        cls.category = cls.env['hr.salary.rule.category'].search([], limit=1)
        cls.monthly = cls._scheme('PRB Monthly', 'PRBMONTHLY', 'end_cycle')
        cls.second = cls._scheme('PRB Second', 'PRBSECOND', 'end_cycle')
        cls.advance = cls._config('PRB Advance', 'PRBADVANCE', 'mid_cycle')
        cls._rule(cls.advance, 'PRB Basic salary', 'BASIC', 'earning', 1)
        cls._rule(cls.advance, 'PRB Loan instalment', 'PRBLOANIN', 'deduction', 2)
        cls.advance.pb_loan_rule_id = cls.advance.rule_ids.filtered(
            lambda r: r.code == 'PRBLOANIN')
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'PRB Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'PRB Kind'})
        cls.ann = cls._person('PRB Ann', 'PRB0001')
        cls.bob = cls._person('PRB Bob', 'PRB0002')
        cls.contracts = {p.id: cls._contract(p, 10_000_000.0) for p in (cls.ann, cls.bob)}

    # ------------------------------------------------------------ fixtures
    @classmethod
    def _config(cls, name, code, cycle):
        return cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': cycle, 'country_code': 'VN',
            'company_id': cls.company.id, 'state': 'active'})

    @classmethod
    def _rule(cls, cfg, name, code, role, seq, column_type='input', formula=None):
        vals = {'config_id': cfg.id, 'name': name, 'code': code, 'column_type': column_type,
                'sequence': seq, 'default_value': 0.0, 'value_kind': 'money',
                'net_role': role, 'appears_on_payslip': True,
                'category_id': cls.category.id}
        if formula:
            vals['excel_formula'] = formula
        return cls.env['hr.formula.rule'].create(vals)

    @classmethod
    def _scheme(cls, name, code, cycle):
        cfg = cls._config(name, code, cycle)
        cls._rule(cfg, 'PRB Basic salary', 'BASIC', 'earning', 1)
        loan_in = cls._rule(cfg, 'PRB Loan instalment', 'PRBLOANIN', 'deduction', 2)
        cls._rule(cfg, 'Holiday gift', 'HOLGIFT', 'earning', 3)
        cls._rule(cfg, 'PRB Loan repayment', 'PRBLOANREP', 'deduction', 10, 'formula',
                  '=-PRBLOANIN')
        cls._rule(cfg, 'PRB Net pay', 'PRBNET', 'net', 20, 'formula',
                  '=BASIC+HOLGIFT+PRBLOANREP')
        cfg.pb_loan_rule_id = loan_in
        return cfg

    @classmethod
    def _person(cls, name, code):
        return cls.env['hr.employee'].create({
            'name': name, 'barcode': code, 'company_id': cls.company.id,
            'work_email': '%s@prb.example' % code.lower()})

    @classmethod
    def _contract(cls, employee, wage):
        return cls.env['hr.contract'].create({
            'name': 'PRB contract %s' % employee.name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'wage': wage, 'state': 'open',
            'date_start': '2026-01-01', 'resource_calendar_id': cls.calendar.id,
            'type_id': cls.kind.id})

    # ------------------------------------------------------------ helpers
    def loan(self, employee=None, amount=6_000_000, each=1_000_000, months=None,
             first=MAR, approve=True, **extra):
        vals = {'employee_id': (employee or self.ann).id, 'amount': amount,
                'currency_id': self.vnd.id, 'reason': 'PRB test loan',
                'first_month': first, 'company_id': self.company.id}
        if months:
            vals.update(plan_mode='months', plan_months=months)
        else:
            vals.update(plan_mode='amount', plan_amount=each)
        vals.update(extra)
        loan = self.Loan.create(vals)
        if approve:
            loan.action_submit()
            self.assertEqual(loan.state, 'running', "no-approval route: running at once")
        return loan

    def make_run(self, cfg=None, ds='2026-03-01', de='2026-03-31', name='PRB March',
                 kind='regular'):
        Run = self.env['hr.payslip.run']
        vals = {'name': name, 'date_start': ds, 'date_end': de,
                'pb_formula_config_id': (cfg or self.monthly).id}
        if 'company_id' in Run._fields:
            vals['company_id'] = self.company.id
        if 'pb_run_kind' in Run._fields:
            vals['pb_run_kind'] = kind
        return Run.create(vals)

    def slip(self, employee, run, cfg=None, compute=True):
        slip = self.env['hr.payslip'].create({
            'name': 'PRB %s' % employee.name, 'employee_id': employee.id,
            'contract_id': self.contracts[employee.id].id, 'payslip_run_id': run.id,
            'date_from': run.date_start, 'date_to': run.date_end,
            'company_id': self.company.id, 'formula_config_id': (cfg or self.monthly).id,
            'calculation_method': 'formula'})
        if compute:
            slip.compute_sheet()
        return slip

    def inputs(self, slip):
        slip.invalidate_recordset()
        return (json.loads(slip.formula_input_values or '{}'),
                json.loads(slip.formula_input_sources or '{}'))

    def line(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def live(self, loan):
        return loan.repayment_ids.filtered(lambda l: l.state in ('reserved', 'paid'))


@tagged('post_install', '-at_install', 'pb_loans')
class TestLoans(LoansFixture):

    # ================================================================ T1
    def test_T1_plan_maths(self):
        L = self.Loan
        self.assertEqual(L._plan_numbers(6_000_000, 'amount', 1_000_000, 0, self.vnd),
                         (1_000_000, 6, 1_000_000))
        self.assertEqual(L._plan_numbers(6_500_000, 'amount', 1_000_000, 0, self.vnd),
                         (1_000_000, 7, 500_000), "last instalment takes the remainder")
        self.assertEqual(L._plan_numbers(10_000_000, 'months', 0, 3, self.vnd),
                         (3_333_334, 3, 3_333_332), "rounded UP to ₫1, last smaller")
        usd = self.env.ref('base.USD')
        self.assertEqual(L._plan_numbers(100.0, 'months', 0, 3, usd), (33.34, 3, 33.32))
        self.assertEqual(L._plan_numbers(500, 'amount', 1_000, 0, self.vnd), (500, 1, 500))
        loan = self.loan(amount=10_000_000, months=3, approve=False)
        self.assertEqual((loan.plan_amount, loan.plan_months), (3_333_334, 3))
        loan2 = self.loan(amount=6_500_000, each=1_000_000, approve=False)
        self.assertEqual(loan2.plan_months, 7)
        self.assertEqual(loan2.balance, 6_500_000)
        self.assertEqual(str(loan2.first_month), MAR)
        loan3 = self.loan(first='2026-03-17', approve=False)
        self.assertEqual(str(loan3.first_month), MAR, "a month, not a day")
        with self.assertRaises(ValidationError):
            self.loan(each=0, approve=False)
        preview = self.Board.plan_preview({'amount': 6_500_000, 'plan_mode': 'amount',
                                           'plan_amount': 1_000_000, 'first_month': MAR,
                                           'currency_id': self.vnd.id})
        self.assertTrue(preview['ok'])
        self.assertEqual(preview['months'], 7)
        self.assertTrue(preview['rows'][-1]['last'])
        self.assertNotIn('Odoo', preview['sentence'])

    # ================================================================ T2
    def test_T2_approval(self):
        seed = self.env['biz.approval.seed'].sudo()
        manager = new_test_user(self.env, login='prb_mgr', company_id=self.company.id,
                                groups='base.group_user,pb_hr_payroll_base.group_payroll_base_manager')
        officer = new_test_user(self.env, login='prb_off', company_id=self.company.id,
                                groups='base.group_user,pb_hr_payroll_base.group_payroll_base_officer')
        # a company made now gets the default route (one step, the Head of
        # pay) from the res.company create hook — the fixture's own company
        # was switched to "No approval needed".
        comp = self.env['res.company'].create({'name': 'PRB Route Co',
                                               'currency_id': self.vnd.id})
        for user in (manager, officer, self.env.user):
            user.sudo().company_ids = [(4, comp.id)]
        process = self.env['biz.approval.process']._by_key('loan')
        self.assertTrue(process.money)
        self.assertFalse(process.bulk_ok)
        Binding = self.env['biz.approval.binding'].sudo()
        if not Binding.search_count([('company_id', '=', comp.id),
                                     ('process_id', '=', process.id), ('active', '=', True)]):
            self.env['pb.loan'].sudo()._approval_seed_default(comp)
        self.assertTrue(Binding.search_count([('company_id', '=', comp.id),
                                              ('process_id', '=', process.id),
                                              ('active', '=', True)]),
                        "every company gets the default loan route")
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'pay_head')], limit=1)
        held = self.env['biz.approval.responsibility'].sudo().with_context(
            active_test=False).search([('company_id', '=', comp.id), ('role_id', '=', role.id)])
        held.write({'user_id': manager.id, 'active': True})
        self.assertTrue(held)
        cara = self.env['hr.employee'].create({'name': 'PRB Cara', 'company_id': comp.id})
        loan = self.Loan.with_context(allowed_company_ids=[comp.id]).create({
            'employee_id': cara.id, 'amount': 6_000_000, 'currency_id': self.vnd.id,
            'reason': 'PRB route loan', 'first_month': MAR, 'company_id': comp.id,
            'plan_mode': 'amount', 'plan_amount': 1_000_000})
        loan = loan.with_user(officer).with_context(allowed_company_ids=[comp.id])
        self.company = comp
        loan.action_submit()
        self.assertEqual(loan.state, 'waiting')
        request = loan.sudo().approval_request_id
        self.assertTrue(request)
        card = self.env['pb.approval.inbox'].with_user(manager).with_company(
            self.company)._card(request)
        seats = [(s.step_id.key, s.status, s.acting_user_id.login, s.user_id.login)
                 for s in request.sudo().step_ids.seat_ids]
        self.assertTrue(card['mine'], (request.state, seats, manager.login))
        self.assertFalse(card['can_bulk'], "a money process is approved on its own")
        detail = loan.sudo()._approval_detail(request)
        self.assertNotIn('Odoo', json.dumps(detail))
        loan.with_user(manager).action_approve()
        self.assertEqual(loan.sudo().state, 'running')
        # refused
        other = loan.sudo().copy({'reason': 'PRB second route loan'})
        other = other.with_user(officer).with_context(allowed_company_ids=[comp.id])
        other.action_submit()
        self.assertEqual(other.sudo().state, 'waiting')
        other.with_user(manager).action_refuse(note='Not this month')
        self.assertEqual(other.sudo().state, 'refused')
        self.assertFalse(seed is None)

    # ================================================================ T3
    def test_T3_regular_run_takes_one_instalment(self):
        loan = self.loan()
        run = self.make_run()
        slip = self.slip(self.ann, run)
        values, sources = self.inputs(slip)
        self.assertEqual(values['PRBLOANIN'], 1_000_000.0)
        self.assertEqual(sources['PRBLOANIN']['via'], 'loan_repayment')
        self.assertEqual(self.line(slip, 'PRBLOANREP').total, -1_000_000.0,
                         "the scheme's formula makes it a deduction")
        self.assertEqual(self.line(slip, 'PRBNET').total, 9_000_000.0)
        lines = self.live(loan)
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines.state, lines.payslip_id, lines.amount),
                         ('reserved', slip, 1_000_000))
        self.assertEqual(loan.balance, 6_000_000, "balance drops only when the slip is done")
        self.assertEqual(loan.in_payrun, 1_000_000)
        slip.write({'state': 'done'})
        self.assertEqual(lines.state, 'paid')
        self.assertEqual(loan.balance, 5_000_000)
        flags = run.pb_review_flags()
        self.assertIn('1,000,000', flags[slip.id]['loan_note'])
        self.assertIn('5,000,000', flags[slip.id]['loan_note'])
        self.assertFalse(flags[slip.id]['flag'])

    def test_T3b_no_loan_is_byte_identical(self):
        run = self.make_run()
        slip = self.slip(self.bob, run)
        values, sources = self.inputs(slip)
        self.assertNotEqual((sources.get('PRBLOANIN') or {}).get('via'), 'loan_repayment')
        self.assertFalse(slip.pb_loan_issue)
        self.assertFalse(self.Line.search([('employee_id', '=', self.bob.id)]))

    # ================================================================ T4
    def test_T4_recompute_delete_cancel(self):
        loan = self.loan()
        run = self.make_run()
        slip = self.slip(self.ann, run)
        slip.compute_sheet()
        slip.action_recompute_formula_lines()
        self.assertEqual(len(self.live(loan)), 1, "recompute reuses the reservation")
        self.assertEqual(self.live(loan).payslip_id, slip)
        slip.unlink()
        self.assertFalse(self.live(loan), "delete releases")
        self.assertEqual(loan.repayment_ids.state, 'released')
        slip2 = self.slip(self.ann, run)
        self.assertEqual(self.live(loan).payslip_id, slip2, "taken again after release")
        slip2.write({'state': 'cancel'})
        self.assertFalse(self.live(loan), "cancel releases")
        slip3 = self.slip(self.ann, run)
        slip3.write({'state': 'done'})
        self.assertEqual(loan.balance, 5_000_000)
        slip3.write({'state': 'cancel'})
        self.assertEqual(loan.balance, 6_000_000, "the balance comes back")
        run2 = self.make_run(name='PRB March again')
        slip4 = self.slip(self.ann, run2)
        self.assertEqual(self.live(loan).payslip_id, slip4)
        run2.unlink()
        self.assertFalse(self.live(loan), "deleting the run releases")
        # paused after reservation, recompute drops it
        slip5 = self.slip(self.ann, self.make_run(name='PRB March 3'))
        loan.action_pause('Holiday month')
        slip5.action_recompute_formula_lines()
        values, _src = self.inputs(slip5)
        self.assertEqual(values['PRBLOANIN'], 0.0, "no stale instalment kept")
        self.assertFalse(self.live(loan))

    # ================================================================ T5
    def test_T5_second_regular_run_same_month(self):
        loan = self.loan()
        slip = self.slip(self.ann, self.make_run())
        other = self.slip(self.ann, self.make_run(self.second, name='PRB March B'), self.second)
        values, _src = self.inputs(other)
        self.assertEqual(values.get('PRBLOANIN') or 0.0, 0.0)
        self.assertEqual(len(self.live(loan)), 1)
        self.assertEqual(self.live(loan).payslip_id, slip)
        # Clean & Run: the first run's payslips are deleted, the new one takes it
        slip.payslip_run_id.unlink()
        again = self.slip(self.ann, self.make_run(name='PRB March clean'))
        self.assertEqual(self.live(loan).payslip_id, again)
        # a second, same-scheme payslip with the first still there: not twice
        dup = self.slip(self.ann, self.make_run(name='PRB March dup'))
        self.assertEqual(self.inputs(dup)[0].get('PRBLOANIN') or 0.0, 0.0)
        self.assertEqual(len(self.live(loan)), 1)

    # ================================================================ T6
    def test_T6_topup_and_advance_take_nothing(self):
        loan = self.loan()
        top = self.slip(self.ann, self.make_run(name='PRB top-up', kind='topup'))
        self.assertEqual(self.inputs(top)[0].get('PRBLOANIN') or 0.0, 0.0)
        adv = self.slip(self.ann, self.make_run(self.advance, de='2026-03-15',
                                                name='PRB mid'), self.advance)
        self.assertEqual(self.inputs(adv)[0].get('PRBLOANIN') or 0.0, 0.0)
        self.assertFalse(self.live(loan))
        self.assertFalse(top.pb_loan_issue)

    # ================================================================ T7
    def test_T7_two_loans_paused_closed(self):
        one = self.loan(amount=3_000_000, each=1_000_000)
        two = self.loan(amount=500_000, each=400_000, kind='advance')
        slip = self.slip(self.ann, self.make_run())
        self.assertEqual(self.inputs(slip)[0]['PRBLOANIN'], 1_400_000.0, "one summed input")
        self.assertEqual(len(self.live(one)), 1)
        self.assertEqual(len(self.live(two)), 1)
        slip.write({'state': 'done'})
        self.assertEqual(two.balance, 100_000)
        # April: the advance takes only what is left, then closes itself
        two.action_pause('Asked to skip April')
        apr = self.slip(self.ann, self.make_run(ds='2026-04-01', de='2026-04-30', name='PRB April'))
        self.assertEqual(self.inputs(apr)[0]['PRBLOANIN'], 1_000_000.0, "paused → skipped")
        apr.write({'state': 'done'})
        two.action_resume()
        may = self.slip(self.ann, self.make_run(ds='2026-05-01', de='2026-05-31', name='PRB May'))
        self.assertEqual(self.inputs(may)[0]['PRBLOANIN'], 1_100_000.0, "never more than owed")
        may.write({'state': 'done'})
        self.assertEqual((one.state, one.balance), ('closed', 0.0))
        self.assertEqual((two.state, two.balance), ('closed', 0.0))
        self.assertTrue(one.closed_on)
        jun = self.slip(self.ann, self.make_run(ds='2026-06-01', de='2026-06-30', name='PRB June'))
        self.assertEqual(self.inputs(jun)[0].get('PRBLOANIN') or 0.0, 0.0)
        # a paid payslip taken back re-opens the loan
        may.write({'state': 'cancel'})
        self.assertEqual(one.state, 'running')
        self.assertEqual(one.balance, 1_000_000)

    # ================================================================ T8
    def test_T8_leaving_month(self):
        rest = self.loan(amount=6_000_000, each=1_000_000)
        bob_loan = self.loan(self.bob, amount=6_000_000, each=1_000_000,
                             on_leaving='leave_open')
        for emp in (self.ann, self.bob):
            emp.departure_date = '2026-03-20'
        run = self.make_run()
        ann = self.slip(self.ann, run)
        bob = self.slip(self.bob, run)
        self.assertEqual(self.inputs(ann)[0]['PRBLOANIN'], 6_000_000.0, "the whole balance")
        self.assertEqual(self.inputs(bob)[0]['PRBLOANIN'], 1_000_000.0, "a normal instalment")
        self.assertEqual(self.line(ann, 'PRBNET').total, 4_000_000.0)
        flags = run.pb_review_flags()
        self.assertNotIn("take-home", flags[ann.id]['reason'] or '',
                         "₫10m pay, ₫6m taken: take-home stays above zero")
        bob.write({'state': 'done'})
        self.assertEqual((bob_loan.state, bob_loan.balance), ('running', 5_000_000),
                         "left open: never closes silently")
        ann.write({'state': 'done'})
        self.assertEqual(rest.state, 'closed')

    # ================================================================ T9
    def test_T9_no_setting_and_more_than_take_home(self):
        self.loan()
        self.monthly.pb_loan_rule_id = False
        run = self.make_run()
        slip = self.slip(self.ann, run)
        values, _src = self.inputs(slip)
        self.assertEqual(values.get('PRBLOANIN') or 0.0, 0.0, "nothing fed")
        self.assertEqual(slip.pb_loan_issue, 'no_item')
        flags = run.pb_review_flags()
        self.assertTrue(flags[slip.id]['flag'])
        self.assertIn('no pay item for loan repayments', flags[slip.id]['reason'])
        notes = run.pb_loan_notes()
        self.assertEqual(len(notes), 1)
        self.assertIn('1 person has a loan instalment due', notes[0])
        board = self.Board.get_board()
        self.assertEqual(board['setup']['missing'], 1)
        self.assertTrue(board['notes'])
        # setting it and calculating again clears the flag
        self.monthly.pb_loan_rule_id = self.monthly.rule_ids.filtered(
            lambda r: r.code == 'PRBLOANIN')
        slip.compute_sheet()
        self.assertFalse(slip.pb_loan_issue)
        # instalment bigger than the month's take-home
        big = self.loan(self.bob, amount=30_000_000, each=15_000_000)
        bslip = self.slip(self.bob, run)
        self.assertEqual(self.inputs(bslip)[0]['PRBLOANIN'], 15_000_000.0, "amount NOT changed")
        flags = run.pb_review_flags()
        self.assertTrue(flags[bslip.id]['flag'])
        self.assertIn("more than this month's take-home", flags[bslip.id]['reason'])
        self.assertEqual(big.in_payrun, 15_000_000)

    def test_T9b_currency_and_other_source(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        loan = self.loan(amount=600, each=100, currency_id=usd.id)
        slip = self.slip(self.ann, self.make_run())
        self.assertEqual(slip.pb_loan_issue, 'currency')
        self.assertFalse(self.live(loan))
        flags = slip.payslip_run_id.pb_review_flags()
        self.assertIn('another currency', flags[slip.id]['reason'])
        loan.action_cancel('Wrong currency')
        self.assertEqual(loan.state, 'cancelled')
        # another source answering a different amount for the loan pay item
        plan = {'code': 'PRBLOANIN', 'items': [{'loan': loan, 'amount': 100.0}],
                'total': 100.0, 'issue': False, 'held': False, 'month': None,
                'currency': usd}
        values = {'PRBLOANIN': 250.0}
        prov = {'PRBLOANIN': {'src': 'contract_component', 'via': 'contract'}}
        used = {}
        self.Loan._merge(plan, values, prov, used)
        self.assertEqual(values['PRBLOANIN'], 250.0, "never one or the other silently")
        self.assertEqual((used['issue'], used['lines']), ('other_source', {}))

    # ================================================================ T10
    def test_T10_application_source(self):
        cfg = self.monthly
        catalogue = cfg._application_source_catalogue()
        self.assertIn('loans.instalment', catalogue)
        loan_in = cfg.rule_ids.filtered(lambda r: r.code == 'PRBLOANIN')
        loan_in.write({'application_source_key': 'loans.instalment'})
        loan = self.loan()
        answer = cfg._application_domain_values(self.ann, self.contracts[self.ann.id],
                                                '2026-03-01', '2026-03-31')
        fact = answer['loans.instalment']
        self.assertEqual((fact['status'], fact['value']), ('resolved', 1_000_000.0))
        self.assertEqual(fact['evidence']['pb_loan_amounts'], {str(loan.id): 1_000_000.0})
        self.assertFalse(fact['evidence'].get('consumption_required'),
                         "the engine blocks consumption_required unconditionally (report)")
        # the reservation is made from the resolved sources, and honoured
        slip = self.slip(self.ann, self.make_run(), compute=False)
        self.Line._sync_slip(slip, {'lines': {loan.id: 1_000_000.0}, 'month': slip.date_to.replace(day=1),
                                    'issue': False, 'seen': True})
        self.assertEqual(self.live(loan).payslip_id, slip)
        again = cfg.with_context(pb_application_payslip_id=slip.id + 999)._application_domain_values(
            self.ann, self.contracts[self.ann.id], '2026-03-01', '2026-03-31')
        self.assertEqual(again['loans.instalment']['value'], 0.0,
                         "another payroll cannot take a reserved instalment")
        own = cfg.with_context(pb_application_payslip_id=slip.id)._application_domain_values(
            self.ann, self.contracts[self.ann.id], '2026-03-01', '2026-03-31')
        self.assertEqual(own['loans.instalment']['value'], 1_000_000.0)
        # the regular seam leaves an application-keyed scheme to the source
        self.assertEqual(cfg._pb_loan_rule(), loan_in)
        values = slip.with_context(pb_application_data_mode=True)._get_formula_input_values(cfg)
        self.assertNotEqual(values.get('PRBLOANIN'), 2_000_000.0)

    # ================================================================ T11
    def test_T11_pay_data_file_path(self):
        if openpyxl is None or 'pb.payrun.wizard' not in self.env:
            self.skipTest('needs the pay run wizard and openpyxl')
        loan = self.loan()
        run = self.make_run()
        res = self.env['pb.payrun.wizard'].attach_spreadsheet(
            run.id, self.monthly.id,
            xlsx_b64([['Employee code', 'Name', 'PRB Basic salary', 'Holiday gift'],
                      ['PRB0001', 'PRB Ann', 10_000_000, 0]]),
            'prb-pay-data.xlsx', str(run.date_start), str(run.date_end), one_time=True)
        self.assertTrue(res['ok'], res.get('msg'))
        slip = self.env['hr.payslip'].search([('payslip_run_id', '=', run.id),
                                              ('employee_id', '=', self.ann.id)])
        self.assertEqual(len(slip), 1)
        values, sources = self.inputs(slip)
        self.assertEqual(values['PRBLOANIN'], 1_000_000.0)
        self.assertEqual(sources['PRBLOANIN']['via'], 'loan_repayment')
        self.assertEqual(self.live(loan).payslip_id, slip)
        self.assertEqual(self.line(slip, 'PRBNET').total, 9_000_000.0,
                         (values, {k: (v or {}).get("src") for k, v in sources.items()}))
        slip.action_recompute_formula_lines()
        self.assertEqual(len(self.live(loan)), 1)
        # a file carrying ANOTHER amount for the loan pay item: not taken, flagged
        run2 = self.make_run(name='PRB March file 2')
        slip.unlink()
        res = self.env['pb.payrun.wizard'].attach_spreadsheet(
            run2.id, self.monthly.id,
            xlsx_b64([['Employee code', 'Name', 'PRB Basic salary', 'Holiday gift', 'PRB Loan instalment'],
                      ['PRB0001', 'PRB Ann', 10_000_000, 0, 250_000]]),
            'prb-pay-data-2.xlsx', str(run2.date_start), str(run2.date_end), one_time=True)
        self.assertTrue(res['ok'], res.get('msg'))
        slip2 = self.env['hr.payslip'].search([('payslip_run_id', '=', run2.id),
                                               ('employee_id', '=', self.ann.id)])
        self.assertEqual(self.inputs(slip2)[0]['PRBLOANIN'], 250_000.0, "the file's amount")
        self.assertEqual(slip2.pb_loan_issue, 'other_source')
        self.assertFalse(self.live(loan), "never twice: the loan line is not taken")

    # ================================================================ T12
    def test_T12_with_a_oneoff_from_updates(self):
        if 'pb.updates.oneoff' not in self.env:
            self.skipTest('pb_updates is not installed')
        loan = self.loan()
        batch = self.env['pb.updates.batch'].sudo().create(
            {'name': 'PRB one-offs', 'company_id': self.company.id})
        oneoff = self.env['pb.updates.oneoff'].sudo().create({
            'employee_id': self.ann.id, 'company_id': self.company.id, 'code': 'HOLGIFT',
            'label': 'PRB Bonus', 'period_month': MAR, 'amount': 500_000.0,
            'net_role': 'earning', 'config_id': self.monthly.id, 'batch_id': batch.id,
            'state': 'approved', 'currency_id': self.vnd.id})
        slip = self.slip(self.ann, self.make_run())
        values, sources = self.inputs(slip)
        self.assertEqual(values['HOLGIFT'], 500_000.0)
        self.assertEqual(values['PRBLOANIN'], 1_000_000.0)
        self.assertEqual(self.line(slip, 'PRBNET').total, 9_500_000.0)
        self.assertEqual((oneoff.state, oneoff.reserved_slip_id), ('reserved', slip))
        self.assertEqual(self.live(loan).payslip_id, slip)
        slip.action_recompute_formula_lines()
        self.assertEqual(self.line(slip, 'PRBNET').total, 9_500_000.0, "both applied once")
        slip.write({'state': 'done'})
        self.assertEqual(oneoff.state, 'paid')
        self.assertEqual(loan.balance, 5_000_000)

    # ================================================================ T13
    def test_T13_rights(self):
        loan = self.loan()
        other_co = self.env['res.company'].create({'name': 'PRB Other Co',
                                                   'currency_id': self.vnd.id})
        stranger = self.env['hr.employee'].create({'name': 'PRB Stranger',
                                                   'company_id': other_co.id})
        hidden = self.Loan.sudo().create({
            'employee_id': stranger.id, 'company_id': other_co.id, 'amount': 100,
            'currency_id': self.vnd.id, 'reason': 'x', 'first_month': MAR,
            'plan_mode': 'amount', 'plan_amount': 100})
        plain = new_test_user(self.env, login='prb_plain', company_id=self.company.id,
                              groups='base.group_user')
        bob_user = new_test_user(self.env, login='prb_bob', company_id=self.company.id,
                                 groups='base.group_portal')
        self.bob.sudo().user_id = bob_user
        with self.assertRaises(AccessError):
            loan.with_user(plain).read(['amount'])
        with self.assertRaises(AccessError):
            self.Board.with_user(plain).get_loan(loan.id)
        self.assertFalse(self.Board.with_user(plain).get_board()['allowed'])
        # the portal method: only the caller's own
        self.assertIsNone(self.Loan.with_user(bob_user).my_loans(self.ann))
        mine = self.Loan.with_user(bob_user).my_loans(self.bob)
        self.assertEqual(mine['loans'], [])
        self.loan(self.bob)
        mine = self.Loan.with_user(bob_user).my_loans(self.bob)
        self.assertEqual(len(mine['loans']), 1)
        self.assertIn('1,000,000', mine['next_label'])
        self.assertNotIn('Odoo', json.dumps(mine))
        cards = self.env['pb.me.home'].with_user(bob_user)._pbme_extra_cards(self.bob)
        self.assertIn('loans', [c['key'] for c in cards])
        # the other company's loan is hidden from this company's pay team
        officer = new_test_user(self.env, login='prb_off2', company_id=self.company.id,
                                groups='base.group_user,pb_hr_payroll_base.group_payroll_base_officer')
        seen = self.Loan.with_user(officer).search([])
        self.assertIn(loan, seen)
        self.assertNotIn(hidden, seen)
        # a repayment line cannot be written by hand
        line = self.Line.sudo().create({'loan_id': loan.id, 'pay_month': MAR, 'amount': 1,
                                        'kind': 'manual', 'state': 'released'})
        with self.assertRaises(AccessError):
            line.with_user(officer).write({'state': 'paid'})

    # ================================================================ T14
    def test_T14_manual_repayment_and_settle(self):
        loan = self.loan()
        with self.assertRaises(UserError):
            loan.action_record_repayment(7_000_000, 'Too much')
        with self.assertRaises(UserError):
            loan.action_record_repayment(1_000, '')
        loan.action_record_repayment(1_500_000, 'Paid in cash', 'R-17')
        self.assertEqual(loan.balance, 4_500_000)
        slip = self.slip(self.ann, self.make_run())
        self.assertEqual(loan.in_payrun, 1_000_000)
        with self.assertRaises(UserError):
            loan.action_record_repayment(4_000_000, 'More than is free')
        loan.action_settle('Settled on leaving early')
        self.assertEqual(loan.balance, 1_000_000, "the pay run's instalment is still held")
        self.assertEqual(loan.state, 'running')
        slip.write({'state': 'done'})
        self.assertEqual((loan.state, loan.balance), ('closed', 0.0))
        with self.assertRaises(UserError):
            loan.action_settle('again')
        # cancel refuses while an instalment is in an unfinished pay run
        other = self.loan(self.bob)
        bslip = self.slip(self.bob, self.make_run(name='PRB March bob'))
        with self.assertRaises(UserError):
            other.action_cancel('Changed our mind')
        bslip.unlink()
        other.action_cancel('Changed our mind')
        self.assertEqual(other.state, 'cancelled')
        # what was agreed cannot be changed once sent
        with self.assertRaises(UserError):
            other.write({'amount': 1})

    # ================================================================ board
    def test_B1_board(self):
        loan = self.loan()
        board = self.Board.get_board()
        self.assertTrue(board['allowed'])
        self.assertEqual(board['kpis']['running'], 1)
        page = self.Board.get_loans_page({}, '', None, 0, 60)
        self.assertEqual(page['total'], 1)
        self.assertEqual(page['steps'].get('running'), 1)
        detail = self.Board.get_loan(loan.id)
        self.assertTrue(detail['can']['pause'])
        self.assertTrue(detail['schedule'])
        res = self.Board.move(loan.id, 'pause', reason='Leave month')
        self.assertEqual(res['state'], 'paused')
        made = self.Board.create_loan({'employee_id': self.bob.id, 'amount': 2_000_000,
                                       'first_month': MAR, 'plan_mode': 'months',
                                       'plan_months': 4, 'reason': 'Car repair',
                                       'kind': 'advance'}, send=True)
        self.assertEqual(made['state'], 'running')
        self.assertEqual(self.Board.employee_options('PRB B')[0]['id'], self.bob.id)
        layout = self.Board.pbf_layout()
        self.assertFalse(layout.get('refused'))
        for text in (json.dumps(board), json.dumps(detail, default=str)):
            self.assertNotIn('Odoo', text)
