# -*- coding: utf-8 -*-
"""WDGAP W2-B — payments to funds and tax offices (cases T1–T18).

Fixture: one company paying in VND with a pay scheme typed the way the
product types components (pay roles), a second scheme in another currency,
finished payslips of October 2026 in a regular run and an Extra run, one of
them on hold. Lines are written directly (the reading is under test, not the
formula engine), carrying the pay role a computed payslip would carry.
"""
import base64
import io
import json
from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger

from odoo.addons.pb_fund_payments.models.fund_approval import seed_all
from odoo.addons.pb_fund_payments.models.fund_payee import code_stem, name_stem
from odoo.addons.pb_fund_payments.models.fund_payment import TOKEN

OCT = date(2026, 10, 1)


class FundFixture(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.sgd = cls.env.ref('base.SGD')
        cls.sgd.active = True
        cls.company = cls.env['res.company'].create(
            {'name': 'W2B Funds Co', 'currency_id': cls.vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        # Most cases want an approved row in one press; the route itself is
        # walked in T8 on a company of its own.
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, 'fundpay')
        cls.Payee = cls.env['pb.fund.payee']
        cls.Pay = cls.env['pb.fund.payment']
        cls.Board = cls.env['pb.fund.payments']
        cls.category = cls.env.ref('om_hr_payroll.NET')
        # the vestigial category a line would carry, by pay role (the run's
        # own totals skip a "counted in a total" line unless it is NET)
        cls.cat_by_role = {
            'earning': cls.env.ref('om_hr_payroll.BASIC'),
            'deduction': cls.env.ref('om_hr_payroll.DED'),
            'net': cls.env.ref('om_hr_payroll.NET'),
            'employer_cost': cls.env.ref('om_hr_payroll.COMP'),
        }
        cls.salary_rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'W2B Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'W2B Kind'})

        cls.vn = cls._config('W2B Vietnam', 'W2BVN', 'VN')
        cls.r = {}
        for name, code, role, extra in (
                ('Basic salary', 'BASIC', 'earning', {}),
                ('Social Insurance (EE)', 'SIEMP', 'deduction', {}),
                ('Health Insurance (EE)', 'HIEMP', 'deduction', {}),
                ('Personal Income Tax', 'PIT', 'deduction', {}),
                ('Net pay', 'NETPAY', 'net', {}),
                ('Social Insurance (ER)', 'SICOMP', 'employer_cost', {}),
                ('Health Insurance (ER)', 'HICOMP', 'employer_cost', {}),
                # never suggested: a part of a total, a working figure, off the payslip
                ('Union fee part', 'UNIONPART', 'deduction', {'net_role_detail': True}),
                ('Insurance base', 'INSBASE', 'info', {}),
                ('Hidden levy', 'HIDDEN', 'deduction', {'appears_on_payslip': False}),
        ):
            cls.r[code] = cls._rule(cls.vn, name, code, role, **extra)
        cls.sg = cls._config('W2B Singapore', 'W2BSG', 'SG')
        cls.sg_basic = cls._rule(cls.sg, 'Basic salary', 'BASIC', 'earning')
        cls.sg_cpf = cls._rule(cls.sg, 'Social Insurance (EE)', 'SIEMP', 'deduction')
        cls.sg_net = cls._rule(cls.sg, 'Net pay', 'NETPAY', 'net')

        cls.ann = cls._person('W2B Ann', 'W2B001')
        cls.bob = cls._person('W2B Bob', 'W2B002')
        cls.cai = cls._person('W2B Cai', 'W2B003')
        cls.dee = cls._person('W2B Dee', 'W2B004')

        cls.regular = cls._run('W2B October', OCT, date(2026, 10, 31), 'regular')
        cls.extra = cls._run('W2B October extra', OCT, date(2026, 10, 31), 'extra')
        cls.sg_run = cls._run('W2B October SG', OCT, date(2026, 10, 31), 'regular', cls.sg)
        # Ann and Bob: a full month. Bob's pay is on hold — still owed.
        cls.slip_ann = cls._slip(cls.ann, cls.regular, cls.vn, cls._month_lines(20_000_000))
        cls.slip_bob = cls._slip(cls.bob, cls.regular, cls.vn, cls._month_lines(10_000_000))
        cls.slip_bob.sudo().write({'pb_pay_hold': True, 'pb_hold_reason': 'W2B documents'})
        # Cai: one Extra-run payslip (a bonus, tax only).
        cls.slip_cai = cls._slip(cls.cai, cls.extra, cls.vn, {
            'BASIC': 5_000_000, 'PIT': -250_000, 'NETPAY': 4_750_000})
        # Dee: paid in SGD on the other scheme.
        cls.slip_dee = cls._slip(cls.dee, cls.sg_run, cls.sg, {
            'BASIC': 6_000, 'SIEMP': -1_200, 'NETPAY': 4_800})
        # A draft payslip never counts (its own run, so the run totals of T15
        # are the finished ones).
        cls.draft_run = cls._run('W2B October draft', OCT, date(2026, 10, 31), 'regular')
        cls.slip_draft = cls._slip(cls._person('W2B Eve', 'W2B005'), cls.draft_run, cls.vn,
                                   cls._month_lines(9_000_000), state='draft')

    # ------------------------------------------------------------ fixtures
    @classmethod
    def _config(cls, name, code, country):
        return cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': 'end_cycle', 'country_code': country,
            'company_id': cls.company.id, 'state': 'active'})

    @classmethod
    def _rule(cls, cfg, name, code, role, **extra):
        vals = {'config_id': cfg.id, 'name': name, 'code': code, 'column_type': 'input',
                'sequence': 10 + len(cfg.rule_ids), 'default_value': 0.0,
                'value_kind': 'money', 'net_role': role, 'appears_on_payslip': True,
                'category_id': cls.category.id}
        vals.update(extra)
        return cls.env['hr.formula.rule'].create(vals)

    @classmethod
    def _person(cls, name, code):
        emp = cls.env['hr.employee'].create({
            'name': name, 'barcode': code, 'company_id': cls.company.id,
            'work_email': '%s@w2b.example' % code.lower()})
        cls.env['hr.contract'].create({
            'name': 'W2B %s' % name, 'employee_id': emp.id, 'company_id': cls.company.id,
            'wage': 1000.0, 'state': 'open', 'date_start': '2026-01-01',
            'resource_calendar_id': cls.calendar.id, 'type_id': cls.kind.id})
        return emp

    @classmethod
    def _run(cls, name, ds, de, kind, cfg=None):
        Run = cls.env['hr.payslip.run']
        vals = {'name': name, 'date_start': ds, 'date_end': de}
        if 'pb_formula_config_id' in Run._fields:
            vals['pb_formula_config_id'] = (cfg or cls.vn).id
        if 'company_id' in Run._fields:
            vals['company_id'] = cls.company.id
        if 'pb_run_kind' in Run._fields:
            vals['pb_run_kind'] = kind
        return Run.create(vals)

    @staticmethod
    def _month_lines(basic):
        si, hi = round(basic * 0.08), round(basic * 0.015)
        pit = round(basic * 0.05)
        return {'BASIC': basic, 'SIEMP': -si, 'HIEMP': -hi, 'PIT': -pit,
                'NETPAY': basic - si - hi - pit,
                'SICOMP': round(basic * 0.175), 'HICOMP': round(basic * 0.03),
                'UNIONPART': -10_000, 'INSBASE': basic}

    @classmethod
    def _slip(cls, emp, run, cfg, lines, state='done', ds=None, de=None):
        contract = cls.env['hr.contract'].search([('employee_id', '=', emp.id)], limit=1)
        slip = cls.env['hr.payslip'].create({
            'name': 'W2B %s %s' % (emp.name, run.name), 'employee_id': emp.id,
            'contract_id': contract.id, 'payslip_run_id': run.id,
            'date_from': ds or run.date_start, 'date_to': de or run.date_end,
            'company_id': cls.company.id, 'formula_config_id': cfg.id})
        rules = {r.code: r for r in cfg.rule_ids}
        vals = []
        for code, amount in lines.items():
            rule = rules.get(code)
            vals.append({
                'slip_id': slip.id, 'salary_rule_id': cls.salary_rule.id,
                'employee_id': emp.id, 'contract_id': contract.id,
                'category_id': cls.cat_by_role.get(rule.net_role if rule else '',
                                                   cls.cat_by_role['earning']).id,
                'name': rule.name if rule else code,
                'code': code, 'amount': amount, 'quantity': 1.0, 'rate': 100.0,
                'pay_role': (rule.net_role if rule else False) or False,
                'component_detail': bool(rule and rule.net_role_detail)})
        cls.env['hr.payslip.line'].create(vals)
        if state != 'draft':
            slip.write({'state': state})
        return slip

    def payee(self, name, items, **extra):
        vals = {'name': name, 'company_id': self.company.id, 'currency_id': self.vnd.id,
                'item_ids': [(0, 0, {'rule_id': rule.id, 'share': share})
                             for rule, share in items]}
        vals.update(extra)
        return self.Payee.create(vals)

    def social(self):
        return self.payee('W2B Social insurance office', [
            (self.r['SIEMP'], 'employee'), (self.r['HIEMP'], 'employee'),
            (self.r['SICOMP'], 'employer'), (self.r['HICOMP'], 'employer')])

    def tax(self):
        return self.payee('W2B Tax office', [(self.r['PIT'], 'employee')])

    def row(self, payee, currency=None, month=OCT):
        return self.Pay.search([('payee_id', '=', payee.id), ('month', '=', month),
                                ('currency_id', '=', (currency or self.vnd).id),
                                ('state', '!=', 'cancelled')])

    def approve(self, rec):
        rec.action_submit()
        rec.invalidate_recordset()
        self.assertEqual(rec.state, 'approved', "no-approval route: approved at once")
        return rec

    def receipt(self, rec, name='receipt.pdf'):
        return self.Pay.pb_attach_evidence(rec.id, name, base64.b64encode(b'%PDF-1.4 w2b'),
                                           'application/pdf')['id']


@tagged('post_install', '-at_install', 'pb_fund_payments')
class TestFundPayments(FundFixture):

    # ============================================================ T1
    def test_T1_suggest_from_typed_components(self):
        self.assertEqual(name_stem('Social Insurance (EE) 8%'), 'social insurance')
        self.assertEqual(name_stem('BHXH - NLĐ'), name_stem('BHXH - DN'))
        self.assertEqual(code_stem('SIEMP'), code_stem('SICOMP'))
        props = self.Payee._pb_suggest(self.company)
        by_name = {p['name']: p for p in props}
        self.assertIn('Social Insurance', by_name, list(by_name))
        social = by_name['Social Insurance']
        self.assertTrue(social['paired'])
        shares = {(i['code'], i['scheme'], i['share']) for i in social['items']}
        self.assertIn(('SIEMP', 'W2B Vietnam', 'employee'), shares)
        self.assertIn(('SICOMP', 'W2B Vietnam', 'employer'), shares)
        # the other scheme's same-named item joins the same proposal
        self.assertIn(('SIEMP', 'W2B Singapore', 'employee'), shares)
        self.assertTrue(by_name['Health Insurance']['paired'])
        pit = by_name['Personal Income Tax']
        self.assertFalse(pit['paired'])
        # WDGAP W2-F (F-3): the "untick it" note is gone — loan repayments and
        # the advance are left out by the schemes' own settings instead
        self.assertFalse(pit['note'])
        codes = {i['code'] for p in props for i in p['items']}
        for never in ('UNIONPART', 'INSBASE', 'HIDDEN', 'BASIC', 'NETPAY'):
            self.assertNotIn(never, codes, never)
        self.assertNotIn('Odoo', json.dumps(props))
        # accept: Health goes in with Social, the tax office on its own
        payload = []
        for p in props:
            payload.append(dict(p, into=by_name['Social Insurance']['key']
                                if p['name'] == 'Health Insurance' else '',
                                items=[dict(i, on=True) for i in p['items']]))
        res = self.Board.create_from_suggestions(payload)
        self.assertEqual(res['made'], 2)
        social_payee = self.Payee.search([('name', '=', 'Social Insurance')])
        self.assertEqual(len(social_payee.item_ids), 5)
        self.assertFalse(self.Payee._pb_suggest(self.company),
                         "nothing loose is left to suggest")

    # ============================================================ T2–T4
    def test_T2_owed_is_employee_plus_employer(self):
        social = self.social()
        stats = self.Pay.pb_work_out(OCT)
        self.assertEqual(stats['created'], 1)
        rec = self.row(social)
        # Ann 20m and Bob 10m: SI 8% + HI 1.5% / SI 17.5% + HI 3%
        self.assertAlmostEqual(rec.amount_employee, 1_600_000 + 300_000 + 800_000 + 150_000)
        self.assertAlmostEqual(rec.amount_employer, 3_500_000 + 600_000 + 1_750_000 + 300_000)
        self.assertAlmostEqual(rec.amount_owed, rec.amount_employee + rec.amount_employer)
        self.assertEqual(rec.head_count, 2)
        self.assertEqual(rec.state, 'to_pay')
        self.assertEqual(rec.due_date, date(2026, 11, 15))
        breakdown = {(b['code'], b['share']): b['amount'] for b in rec._breakdown()}
        self.assertAlmostEqual(breakdown[('SICOMP', 'employer')], 5_250_000)
        self.assertNotIn(self.slip_draft, rec.slip_ids, "a draft payslip never counts")

    def test_T3_extra_run_counts(self):
        tax = self.tax()
        self.Pay.pb_work_out(OCT)
        rec = self.row(tax)
        self.assertIn(self.slip_cai, rec.slip_ids)
        self.assertAlmostEqual(rec.amount_owed, 1_000_000 + 500_000 + 250_000)
        self.assertEqual(rec.head_count, 3)

    def test_T4_held_payslip_counts(self):
        social = self.social()
        self.Pay.pb_work_out(OCT)
        rec = self.row(social)
        self.assertTrue(self.slip_bob.pb_pay_hold)
        self.assertIn(self.slip_bob, rec.slip_ids, "the contribution is owed for held pay")

    # ============================================================ T5
    def test_T5_two_currencies_two_rows(self):
        both = self.payee('W2B Insurance', [(self.r['SIEMP'], 'employee'),
                                            (self.sg_cpf, 'employee')])
        self.Pay.pb_work_out(OCT)
        vnd_row, sgd_row = self.row(both, self.vnd), self.row(both, self.sgd)
        self.assertTrue(vnd_row and sgd_row)
        self.assertAlmostEqual(vnd_row.amount_owed, 2_400_000)
        self.assertAlmostEqual(sgd_row.amount_owed, 1_200)
        board = self.Board.get_board(OCT)
        self.assertEqual(sorted(t['currency'] for t in board['totals']), ['SGD', 'VND'])

    # ============================================================ T6
    def test_T6_work_out_twice_is_idempotent(self):
        social, tax = self.social(), self.tax()
        self.Pay.pb_work_out(OCT)
        before = self.Pay.search([('month', '=', OCT)])
        stats = self.Pay.pb_work_out(OCT)
        self.assertEqual(stats['created'], 0)
        self.assertEqual(stats['unchanged'], 2)
        self.assertEqual(self.Pay.search([('month', '=', OCT)]), before)
        # the unique index among live rows (R4)
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.Pay.with_context(**{TOKEN: True}).create({
                'payee_id': social.id, 'company_id': self.company.id,
                'currency_id': self.vnd.id, 'month': OCT})
            self.env.flush_all()
        res = self.Board.work_out(OCT)
        self.assertIn('nothing changed', res['msg'])
        self.assertTrue(tax)

    # ============================================================ T7
    def test_T7_figures_changed_after_approval(self):
        social = self.social()
        self.Pay.pb_work_out(OCT)
        rec = self.approve(self.row(social))
        owed = rec.amount_owed
        # a late joiner's payslip is finished after the approval
        fay = self._person('W2B Fay', 'W2B006')
        self._slip(fay, self.regular, self.vn, self._month_lines(10_000_000))
        stats = self.Pay.pb_work_out(OCT)
        self.assertEqual(stats['changed'], 1)
        self.assertEqual(stats['created'], 0)
        rec.invalidate_recordset()
        self.assertEqual(rec.state, 'approved')
        self.assertAlmostEqual(rec.amount_owed, owed, msg="approved figures never move (R3)")
        self.assertTrue(rec.figures_changed)
        self.assertAlmostEqual(rec.live_diff, 950_000 + 2_050_000)
        row = self.Board._row(rec)
        self.assertTrue(row['changed'])
        self.assertIn('+', row['changed_label'])

    # ============================================================ T8
    def test_T8_approval_route_never_bulk(self):
        process = self.env['biz.approval.process']._by_key('fundpay')
        self.assertTrue(process.money)
        self.assertFalse(process.bulk_ok)
        self.assertTrue(process.connected)
        with self.assertRaises(ValidationError):
            process.write({'bulk_ok': True})
        g_mgr = 'om_hr_payroll.group_hr_payroll_manager,om_hr_payroll.group_hr_payroll_user'
        comp = self.env['res.company'].create({'name': 'W2B Route Co',
                                               'currency_id': self.vnd.id})
        officer = new_test_user(self.env, login='w2b_off', company_id=comp.id,
                                groups='base.group_user,' + g_mgr)
        # WDGAP W2-F (F-2): ONE signature, the Head of pay. The seat holder
        # here holds NO payroll role on purpose: the seat alone lets them read
        # (ledger W2B-2 — the engine applies as the last decider).
        director = new_test_user(self.env, login='w2b_dir', company_id=comp.id,
                                 groups='base.group_user')
        self.env.user.company_ids = [(4, comp.id)]
        for key, user in (('pay_head', director),):
            role = self.env['biz.approval.role'].sudo().search([('key', '=', key)], limit=1)
            held = self.env['biz.approval.responsibility'].sudo().with_context(
                active_test=False).search([('company_id', '=', comp.id),
                                           ('role_id', '=', role.id), ('scope_key', '=', '')],
                                          limit=1)
            if held:
                held.write({'user_id': user.id, 'active': True})
            else:
                self.env['biz.approval.responsibility'].sudo().create({
                    'company_id': comp.id, 'role_id': role.id, 'scope_key': '',
                    'scope_label': comp.name, 'user_id': user.id,
                    'date_from': date(2020, 1, 1)})
        seed_all(self.env)
        Binding = self.env['biz.approval.binding'].sudo()
        self.assertTrue(Binding.search_count([('company_id', '=', comp.id),
                                              ('process_id', '=', process.id),
                                              ('active', '=', True)]),
                        "every company gets the default fund-payment route")
        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'W2B Route scheme', 'code': 'W2BRT', 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'company_id': comp.id, 'state': 'active'})
        pit = self.env['hr.formula.rule'].sudo().create({
            'config_id': cfg.id, 'name': 'Personal Income Tax', 'code': 'PIT',
            'column_type': 'input', 'value_kind': 'money', 'net_role': 'deduction',
            'appears_on_payslip': True, 'category_id': self.category.id})
        emp = self.env['hr.employee'].sudo().create({'name': 'W2B Gil', 'company_id': comp.id})
        contract = self.env['hr.contract'].sudo().create({
            'name': 'W2B Gil', 'employee_id': emp.id, 'company_id': comp.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2026-01-01', 'type_id': self.kind.id,
            'resource_calendar_id': (comp.resource_calendar_id or self.calendar).id})
        slip = self.env['hr.payslip'].sudo().create({
            'name': 'W2B Gil', 'employee_id': emp.id, 'company_id': comp.id,
            'contract_id': contract.id,
            'date_from': OCT, 'date_to': date(2026, 10, 31), 'formula_config_id': cfg.id})
        self.env['hr.payslip.line'].sudo().create({
            'contract_id': contract.id,
            'slip_id': slip.id, 'salary_rule_id': self.salary_rule.id, 'employee_id': emp.id,
            'category_id': self.category.id, 'name': 'PIT', 'code': 'PIT',
            'amount': -700_000, 'quantity': 1, 'rate': 100, 'pay_role': 'deduction'})
        slip.write({'state': 'done'})
        payee = self.Payee.sudo().create({
            'name': 'W2B Route tax office', 'company_id': comp.id,
            'item_ids': [(0, 0, {'rule_id': pit.id, 'share': 'employee'})]})
        Pay = self.Pay.with_user(officer).with_context(allowed_company_ids=[comp.id])
        Pay.pb_work_out(OCT)
        rec = Pay.search([('payee_id', '=', payee.id)])
        self.assertEqual(rec.worked_out_by, officer)
        rec.action_submit()
        self.assertEqual(rec.state, 'waiting')
        request = rec.sudo().approval_request_id
        self.assertEqual(request.process_id, process)
        self.assertAlmostEqual(request.amount, 700_000)
        # never approve-selected: a money process
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat_user = step.seat_ids.filtered(lambda s: s.status == 'open')[:1].acting_user_id
        card = self.env['pb.approval.inbox'].with_user(seat_user).with_context(
            allowed_company_ids=[comp.id])._card(request)
        self.assertFalse(card['can_bulk'], "a money process is approved on its own")
        detail = rec.sudo()._approval_detail(request)
        self.assertIn('700,000', detail['rows'][0]['cells'][0].replace('\xa0', ' '))
        self.assertNotIn('Odoo', json.dumps(detail))
        deciders = set()
        for _guard in range(4):
            request.invalidate_recordset()
            if request.state not in ('pending', 'blocked'):
                break
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.assertTrue(seat, request.block_reason or request.state)
            deciders.add(seat.acting_user_id.id)
            # only the deciding person's own companies (ledger QF2-G1)
            self.env['biz.approval.engine'].with_user(seat.acting_user_id).with_context(
                allowed_company_ids=[comp.id]).decide(request.id, step.key, 'approve', 'ok')
        rec.invalidate_recordset()
        self.assertEqual(deciders, {director.id}, "one signature, the Head of pay")
        steps = request.step_ids
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps.title, 'Head of pay')
        self.assertEqual(rec.sudo().state, 'approved')
        self.assertIn(director, rec.sudo().seat_user_ids)
        # the director reads the one payment they were asked to decide — no other
        self.assertEqual(self.Pay.with_user(director).with_context(
            allowed_company_ids=[comp.id]).search([]), rec)

    # ============================================================ T9–T10
    def test_T9_mark_paid_needs_the_receipt(self):
        tax = self.tax()
        self.Pay.pb_work_out(OCT)
        rec = self.row(tax)
        with self.assertRaises(UserError):
            rec.action_mark_paid(attachment_id=self.receipt(rec))   # not approved yet
        self.approve(rec)
        with self.assertRaises(UserError):
            rec.action_mark_paid()
        stranger = self.env['ir.attachment'].create({
            'name': 'other.pdf', 'datas': base64.b64encode(b'x'),
            'res_model': 'res.partner', 'res_id': self.env.user.partner_id.id})
        with self.assertRaises(UserError):
            rec.action_mark_paid(attachment_id=stranger.id)
        att = self.receipt(rec)
        rec.action_mark_paid(paid_on='2026-11-10', reference='TAX-OCT', attachment_id=att)
        self.assertEqual(rec.state, 'paid')
        self.assertAlmostEqual(rec.paid_amount, rec.amount_owed)
        self.assertEqual(rec.evidence_attachment_id.id, att)
        self.assertFalse(rec.paid_difference)

    def test_T10_a_difference_needs_a_note(self):
        tax = self.tax()
        self.Pay.pb_work_out(OCT)
        rec = self.approve(self.row(tax))
        att = self.receipt(rec)
        with self.assertRaises(UserError):
            rec.action_mark_paid(paid_amount=rec.amount_owed - 1000, attachment_id=att)
        with self.assertRaises(UserError):
            rec.action_mark_paid(paid_amount=rec.amount_owed, attachment_id=att,
                                 paid_on='2099-01-01')
        rec.action_mark_paid(paid_amount=rec.amount_owed - 1000, attachment_id=att,
                             note='The office rounded down')
        self.assertAlmostEqual(rec.paid_difference, -1000)
        self.assertEqual(rec.difference_note, 'The office rounded down')
        self.assertTrue(self.Board._row(rec)['diff_label'])

    # ============================================================ T11
    def test_T11_late_flag(self):
        june = date(2026, 6, 1)
        run = self._run('W2B June', june, date(2026, 6, 30), 'regular')
        self._slip(self.ann, run, self.vn, self._month_lines(20_000_000))
        jan = date(2027, 1, 1)
        run_jan = self._run('W2B January', jan, date(2027, 1, 31), 'regular')
        self._slip(self.ann, run_jan, self.vn, self._month_lines(20_000_000))
        tax = self.tax()
        self.Pay.pb_work_out(june)
        self.Pay.pb_work_out(jan)
        old, new = self.row(tax, month=june), self.row(tax, month=jan)
        self.assertEqual(old.due_date, date(2026, 7, 15))
        self.assertTrue(old.is_late)
        self.assertFalse(new.is_late)
        board = self.Board.get_board(jan)
        self.assertEqual(board['kpis']['late'], 1)
        self.assertEqual(board['kpis']['late_month'], '2026-06-01')
        page = self.Board.with_context(pbf_ctx={'month': '2026-06-01'}).get_page(
            filters={'late': ['late']})
        self.assertEqual([r['id'] for r in page['rows']], [old.id])
        # paid before the due date → on time; after it → paid late
        self.approve(old)
        old.action_mark_paid(paid_on='2026-07-10', attachment_id=self.receipt(old))
        self.assertFalse(old.is_late)
        old.action_reopen('W2B wrong date')
        self.approve(old)
        old.action_mark_paid(paid_on='2026-07-20', attachment_id=self.receipt(old))
        self.assertTrue(old.is_late)
        self.assertTrue(self.Board._row(old)['paid_late'])

    # ============================================================ T12
    def test_T12_reopen(self):
        social = self.social()
        self.Pay.pb_work_out(OCT)
        rec = self.approve(self.row(social))
        rec.action_mark_paid(attachment_id=self.receipt(rec))
        self._slip(self._person('W2B Hal', 'W2B007'), self.regular, self.vn,
                   self._month_lines(10_000_000))
        self.Pay.pb_work_out(OCT)
        self.assertTrue(rec.figures_changed)
        with self.assertRaises(UserError):
            rec.action_reopen('')
        rec.action_reopen('A late joiner was left out')
        self.assertEqual(rec.state, 'to_pay')
        self.assertFalse(rec.paid_on or rec.evidence_attachment_id or rec.paid_amount)
        self.assertFalse(rec.figures_changed)
        self.assertEqual(rec.head_count, 3, "worked out again from the payslips")
        self.assertEqual(rec.reopen_reason, 'A late joiner was left out')
        with self.assertRaises(UserError):
            rec.action_mark_paid(attachment_id=0)       # "to pay": not approved
        self.approve(rec)       # back through approval
        self.assertEqual(rec.approval_request_id.attempt, 2)
        bodies = ' '.join(rec.message_ids.mapped('body'))
        self.assertIn('Reopened', bodies)

    # ============================================================ T13
    def test_T13_rights_and_company_rule(self):
        social = self.social()
        self.Pay.pb_work_out(OCT)
        rec = self.row(social)
        plain = new_test_user(self.env, login='w2b_plain', company_id=self.company.id,
                              groups='base.group_user')
        reader = new_test_user(self.env, login='w2b_reader', company_id=self.company.id,
                               groups='base.group_user,om_hr_payroll.group_hr_payroll_user')
        manager = new_test_user(
            self.env, login='w2b_mgr', company_id=self.company.id,
            groups='base.group_user,om_hr_payroll.group_hr_payroll_manager')
        ctx = {'allowed_company_ids': [self.company.id]}
        # a plain employee: refused by the board, no row readable
        self.assertFalse(self.Board.with_user(plain).with_context(**ctx).get_board(OCT)['allowed'])
        self.assertFalse(self.Pay.with_user(plain).with_context(**ctx).search([]))
        with self.assertRaises(AccessError):
            self.Board.with_user(plain).with_context(**ctx).get_payment(rec.id)
        # a payroll user reads but cannot act
        board = self.Board.with_user(reader).with_context(**ctx).get_board(OCT)
        self.assertTrue(board['allowed'])
        self.assertFalse(board['can_write'])
        self.assertTrue(self.Board.with_user(reader).with_context(**ctx).get_payment(rec.id))
        with self.assertRaises(AccessError):
            self.Board.with_user(reader).with_context(**ctx).work_out(OCT)
        with self.assertRaises(AccessError):
            self.Board.with_user(reader).with_context(**ctx).move(rec.id, 'submit')
        # a payroll manager acts
        res = self.Board.with_user(manager).with_context(**ctx).work_out(OCT)
        self.assertIn('worked out', res['msg'])
        # another company's payments are invisible
        other = self.env['res.company'].create({'name': 'W2B Other Co',
                                                'currency_id': self.vnd.id})
        manager.sudo().company_ids = [(4, other.id)]
        self.assertFalse(self.Pay.with_user(manager).with_context(
            allowed_company_ids=[other.id]).search([]))
        self.assertTrue(self.Pay.with_user(manager).with_context(**ctx).search([]))

    # ============================================================ T14
    def test_T14_export_one_block_per_currency(self):
        from openpyxl import load_workbook
        self.payee('W2B Insurance', [(self.r['SIEMP'], 'employee'), (self.sg_cpf, 'employee')])
        self.Pay.pb_work_out(OCT)
        res = self.Board.export_xlsx(OCT)
        self.assertTrue(res['ok'])
        self.assertEqual(res['rows'], 2)
        wb = load_workbook(io.BytesIO(base64.b64decode(res['file_b64'])))
        cells = [str(c.value) for row in wb.active.iter_rows() for c in row if c.value is not None]
        self.assertIn('Amounts in SGD', cells)
        self.assertIn('Amounts in VND', cells)
        self.assertEqual(cells.count('Total'), 2)
        self.assertFalse([c for c in cells if 'Odoo' in c])

    # ============================================================ T15
    def test_T15_R6_identity_with_the_run_totals(self):
        """A payee holding every deduction item (employee share) and every
        employer cost (employer share) owes exactly what the month's runs say
        they took off and what they cost the employer."""
        counted = self.vn.rule_ids.filtered(
            lambda r: r.net_role in ('deduction', 'employer_cost') and not r.net_role_detail
            and r.appears_on_payslip)
        everything = self.payee('W2B Everything', [
            (r, 'employee' if r.net_role == 'deduction' else 'employer') for r in counted])
        self.Pay.pb_work_out(OCT)
        rec = self.row(everything)
        runs = self.regular | self.extra
        self.env.flush_all()
        runs.invalidate_recordset()
        runs._compute_pb_totals()
        self.assertAlmostEqual(rec.amount_employee, sum(runs.mapped('pb_total_deductions')),
                               places=2)
        self.assertAlmostEqual(rec.amount_employer, sum(runs.mapped('pb_total_employer_cost')),
                               places=2)
        # and the same identity per payslip, through the one pay-band helper
        slips = rec.slip_ids
        totals = slips.mapped('line_ids').pb_pay_totals()
        self.assertAlmostEqual(rec.amount_employee, totals['deductions'], places=2)
        self.assertAlmostEqual(rec.amount_employer, totals['employer_cost'], places=2)

    # ============================================================ T16
    def test_T16_no_write_path_types_a_figure(self):
        tax = self.tax()
        self.Pay.pb_work_out(OCT)
        rec = self.row(tax)
        for vals in ({'amount_owed': 1}, {'amount_employee': 1}, {'state': 'paid'},
                     {'paid_amount': 5}, {'head_count': 9}):
            with self.assertRaises(UserError):
                rec.write(vals)
        with self.assertRaises(UserError):
            self.Pay.create({'payee_id': tax.id, 'company_id': self.company.id,
                             'currency_id': self.vnd.id, 'month': date(2026, 9, 1)})
        # a payee can own an item only once
        with self.assertRaises(ValidationError):
            self.payee('W2B Duplicate', [(self.r['PIT'], 'employee')])
        # a "to pay" row nothing is owed on any more is cancelled, not left at 0
        tax.write({'item_ids': [(2, i.id) for i in tax.item_ids]})
        stats = self.Pay.pb_work_out(OCT)
        self.assertEqual(stats['cancelled'], 1)
        self.assertEqual(rec.state, 'cancelled')

    # ============================================================ T17
    def test_T17_board_surface(self):
        social = self.social()
        res = self.Board.work_out(OCT)
        self.assertIn('1 new', res['msg'])
        board = self.Board.get_board(OCT)
        self.assertEqual(board['kpis']['to_pay'], 1)
        self.assertEqual(board['payees'], 1)
        self.assertEqual(board['month_label'], 'October 2026')
        page = self.Board.with_context(pbf_ctx={'month': '2026-10-01'}).get_page()
        self.assertEqual(len(page['rows']), 1)
        self.assertEqual(page['steps'].get('to_pay'), 1)
        other_month = self.Board.with_context(pbf_ctx={'month': '2026-09-01'}).get_page()
        self.assertFalse(other_month['rows'])
        rec = self.row(social)
        drawer = self.Board.get_payment(rec.id)
        self.assertEqual(len(drawer['items']), 4)
        self.assertEqual(len(drawer['people_rows']['rows']), 2)
        self.assertTrue(drawer['can']['submit'])
        action = self.Board.open_lines(rec.id)
        lines = self.env['hr.payslip.line'].search(action['domain'])
        self.assertEqual(len(lines), 8)
        self.assertEqual(action['views'][0][1], 'list')
        layout = self.Board.with_context(pbf_ctx={'month': '2026-10-01'}).pbf_layout()
        self.assertTrue(layout['sections'])
        setup = self.Board.get_payees()
        self.assertEqual(setup['payees'][0]['employee_items'], 2)
        opts = self.Board.item_options('')
        self.assertTrue(any(o['code'] == 'PIT' for o in opts))
        self.assertEqual(next(o for o in opts if o['code'] == 'SIEMP'
                              and o['scheme'] == 'W2B Vietnam')['taken_by'], social.name)
        saved = self.Board.save_payee({'id': social.id, 'name': 'W2B Social', 'due_day': 20,
                                       'items': [{'rule_id': self.r['SIEMP'].id,
                                                  'share': 'employee'}]})
        self.assertTrue(saved['ok'])
        self.assertEqual(len(social.item_ids), 1)
        self.assertEqual(social.due_day, 20)
        self.Board.move(rec.id, 'submit')
        self.assertEqual(rec.state, 'approved')
        for payload in (board, page, drawer, setup, opts, res):
            self.assertNotIn('Odoo', json.dumps(payload, default=str))


@tagged('post_install', '-at_install', 'pb_fund_payments')
class TestFundPaymentsInstall(TransactionCase):
    """T18 — R5: the install is silent. Nothing but the catalogue row, the
    default routes, the rules and the screens."""

    def test_T18_install_is_silent(self):
        # Judged on what the MODULE ships (its ir.model.data), not on a count
        # of rows: a database people have already used holds their own payees.
        data = self.env['ir.model.data'].sudo().search([('module', '=', 'pb_fund_payments')])
        self.assertFalse(data.filtered(lambda d: d.model in (
            'pb.fund.payee', 'pb.fund.payee.item', 'pb.fund.payment')),
            "no payee or payment is shipped")
        allowed = {'ir.model', 'ir.model.fields', 'ir.model.fields.selection',
                   'ir.model.access', 'ir.rule', 'ir.ui.view', 'ir.actions.client',
                   'ir.actions.act_window', 'biz.approval.process', 'ir.model.constraint',
                   'ir.model.inherit',
                   'ir.module.module'}
        self.assertFalse(set(data.mapped('model')) - allowed,
                         set(data.mapped('model')) - allowed)
        self.assertFalse(self.env['ir.cron'].sudo().with_context(active_test=False).search([
            ('model_id.model', 'like', 'pb.fund.')]), "no scheduled job")
        self.assertFalse(self.env['mail.template'].sudo().search([
            ('model_id.model', 'like', 'pb.fund.')]), "no email")
        self.assertFalse(self.env['mail.mail'].sudo().search([
            ('model', 'like', 'pb.fund.')]), "nothing queued to send")
        process = self.env['biz.approval.process']._by_key('fundpay')
        self.assertTrue(process and process.money and not process.bulk_ok)
