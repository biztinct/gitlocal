# -*- coding: utf-8 -*-
"""HOME P1 — `pb.dashboard.get_home_data()`, tests 1–12 of the handover.

The clone these run on (`p0clone`, a copy of the golden template) has no
payroll at all, so every money / scope / people case seeds its own records and
asserts on DELTAS or on the seeded rows, never on what the database happened to
hold. Run states are set with one UPDATE because the pay run's state machine
refuses a plain write (pb_payruns C18.24) and these tests are about what Home
reads, not about the approval engine.
"""
import ast
import logging
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.addons.pb_dashboard.models import home_data as home_module
from odoo.tests.common import TransactionCase, tagged

from .test_activation import (
    HOME_MODELS, HOME_PY, OPTIONAL_MODELS, _guarded_env_reads, _read,
    names_forbidden_module)

#: Models pb_dashboard's own depends provide (web, om_hr_payroll ->
#: hr_contract, pb_hr_payroll_base): the only ones read without a guard.
CORE_MODELS = {'hr.employee', 'hr.contract', 'hr.payslip', 'hr.payslip.run'}

TOP_KEYS = ('user', 'company', 'currency', 'today', 'period', 'needs_you',
            'approvals_total', 'months', 'runs', 'steps', 'upcoming', 'people',
            'hiring', 'learn', 'schemes', 'activation', 'timing_ms')
PERIOD_KEYS = ('key', 'date_start', 'date_end', 'stage', 'total', 'run_count',
               'delivered_count', 'cutoff', 'payday', 'prepared', 'expected',
               'net_so_far', 'awaiting_me', 'awaiting_run', 'now_run')
MONTH_KEYS = ('key', 'year_mark', 'people', 'net', 'gross', 'ded', 'er',
              'total', 'avg', 'runs', 'balance_ok', 'done', 'latest',
              'inprogress', 'approved', 'delivered', 'note', 'foreign_runs')
TIMING_KEYS = ('period', 'needs_you', 'months', 'runs', 'people', 'hiring',
               'learn', 'schemes', 'total')
NEEDS_ORDER = ('runs_to_approve', 'leave_to_approve', 'other_to_approve',
               'settlements_to_check', 'renewals_to_start', 'writeups_overdue')


@tagged('post_install', '-at_install')
class TestHomeData(TransactionCase):

    def setUp(self):
        super().setUp()
        self.D = self.env['pb.dashboard']
        self.company = self.env.company
        self.data = self.home()
        self.period = self.data['period']
        self.p_first = fields.Date.to_date(self.period['date_start'])
        self.p_last = fields.Date.to_date(self.period['date_end'])
        self.today = fields.Date.context_today(self.D)

    # ------------------------------------------------------------- fixtures
    def home(self, user=None, companies=None):
        model = self.env['pb.dashboard']
        if user is not None:
            model = model.with_user(user)
        if companies is not None:
            model = model.with_context(allowed_company_ids=companies.ids)
        return model.get_home_data()

    def _employee(self, name, company=None, contract=True, start='2020-01-01',
                  end=False):
        company = company or self.company
        emp = self.env['hr.employee'].create(
            {'name': name, 'company_id': company.id})
        if contract:
            self.env['hr.contract'].create({
                'name': '%s contract' % name, 'employee_id': emp.id,
                'wage': 10000.0, 'state': 'open', 'date_start': start,
                'date_end': end, 'company_id': company.id})
        return emp

    def _run(self, name, start, end):
        return self.env['hr.payslip.run'].create(
            {'name': name, 'date_start': start, 'date_end': end})

    def _category(self, code):
        cat = self.env['hr.salary.rule.category'].search(
            [('code', '=', code)], limit=1)
        if not cat:
            self.skipTest("no '%s' salary-rule category on this database" % code)
        return cat

    def _slip(self, run, emp, amounts=None, company=None):
        company = company or self.company
        rule = self.env['hr.salary.rule'].search([], limit=1)
        if not rule:
            self.skipTest('no salary rule on this database to hang lines off')
        contract = self.env['hr.contract'].search(
            [('employee_id', '=', emp.id)], limit=1)
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': 'Home slip %s' % emp.name,
            'contract_id': contract.id,
            'date_from': run.date_start, 'date_to': run.date_end,
            'company_id': company.id, 'payslip_run_id': run.id})
        for code, amount in (amounts or {'NET': 1000.0}).items():
            self.env['hr.payslip.line'].create({
                'slip_id': slip.id, 'name': code, 'code': code,
                'amount': amount, 'quantity': 1.0, 'rate': 100.0,
                'employee_id': emp.id, 'contract_id': contract.id,
                'category_id': self._category(code).id,
                'salary_rule_id': rule.id})
        return slip

    def _set_state(self, run, state):
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE hr_payslip_run SET state = %s WHERE id = %s", (state, run.id))
        self.env.invalidate_all()

    def _month(self, back):
        first = self.p_first - relativedelta(months=back)
        return first, first + relativedelta(months=1, days=-1)

    def _calendar(self, cutoff, payday):
        if 'pb.payroll.calendar' not in self.env:
            self.skipTest('the payroll calendar (pb_comp_ben) is not installed')
        Cal = self.env['pb.payroll.calendar']
        row = Cal.search([('month', '=', self.p_first),
                          ('company_id', '=', self.company.id)], limit=1)
        vals = {'cutoff_date': cutoff, 'pay_date': payday}
        if row:
            row.write(vals)
        else:
            Cal.create(dict(vals, month=self.p_first,
                            company_id=self.company.id))

    def _leave(self, emp, day, validate):
        """A one-day leave on `day`, or a skip naming why it could not be
        made (leave types and calendars differ per database)."""
        if 'hr.leave' not in self.env:
            self.skipTest('hr.leave is not installed')
        Type = self.env['hr.leave.type']
        vals = {'name': 'Home test leave'}
        field = Type._fields.get('requires_allocation')
        if field is not None:
            vals['requires_allocation'] = (
                False if field.type == 'boolean' else 'no')
        try:
            with self.env.cr.savepoint():
                kind = Type.create(vals)
                leave = self.env['hr.leave'].create({
                    'employee_id': emp.id, 'holiday_status_id': kind.id,
                    'request_date_from': day, 'request_date_to': day})
                if validate:
                    for method in ('action_approve', 'action_validate'):
                        if leave.state == 'validate':
                            break
                        if hasattr(leave, method):
                            try:
                                getattr(leave.sudo(), method)()
                            except Exception:          # noqa: BLE001
                                pass
                    if leave.state != 'validate':
                        leave.sudo().write({'state': 'validate'})
                self.env.flush_all()
        except Exception as exc:                       # noqa: BLE001
            self.skipTest('a leave could not be created here: %s' % exc)
        return leave

    # =============================================================== test 1
    def test_01_shape(self):
        for key in TOP_KEYS:
            self.assertIn(key, self.data, 'payload lacks %s' % key)
        for key in PERIOD_KEYS:
            self.assertIn(key, self.period, 'period lacks %s' % key)
        self.assertEqual(self.period['total'], 5)
        self.assertEqual(self.period['key'], self.p_first.strftime('%Y-%m'))
        months = self.data['months']
        self.assertEqual(len(months), 12)
        keys = [m['key'] for m in months]
        self.assertEqual(keys, sorted(keys), 'months are not oldest first')
        self.assertEqual(len(set(keys)), 12)
        self.assertEqual(keys[-1], self.period['key'])
        for index, month in enumerate(months):
            for key in MONTH_KEYS:
                self.assertIn(key, month)
            self.assertEqual(month['year_mark'],
                             index == 0 or month['key'].endswith('-01'),
                             'year mark wrong on %s' % month['key'])
        self.assertEqual([s['key'] for s in self.data['steps']],
                         ['setup', 'prepare', 'approve', 'pay', 'deliver'])
        for step in self.data['steps']:
            self.assertIn(step['state'], ('done', 'now', 'wait', 'todo'))
        self.assertLessEqual(
            sum(1 for s in self.data['steps'] if s['state'] == 'now'), 1)
        for key in TIMING_KEYS:
            self.assertIsInstance(self.data['timing_ms'][key], int)
        for item in self.data['needs_you']:
            self.assertEqual(set(item), {'key', 'n'})
            self.assertGreater(item['n'], 0)
        order = [i['key'] for i in self.data['needs_you']]
        self.assertEqual(order, [k for k in NEEDS_ORDER if k in order])
        self.assertEqual(self.data['today'], self.today.isoformat())
        self.assertIn(self.data['currency']['position'], ('before', 'after'))

    # =============================================================== test 2
    def test_02_money_comes_from_the_stored_run_totals(self):
        Run = self.env['hr.payslip.run']
        if 'pb_total_net' not in Run._fields:
            self.skipTest('pb_payruns (the stored run totals) is not installed')
        first, last = self._month(1)
        a = self._employee('Home Money A')
        b = self._employee('Home Money B')
        run_a = self._run('Home money A', first, last)
        run_b = self._run('Home money B', first, last)
        self._slip(run_a, a, {'GROSS': 12000.0, 'DED': 2000.0, 'NET': 10000.0})
        self._slip(run_b, b, {'GROSS': 9000.0, 'DED': 1500.0, 'NET': 7500.0})
        self.env.flush_all()

        month = self.home()['months'][-2]
        self.assertEqual(month['key'], first.strftime('%Y-%m'))
        runs = Run.search([('date_end', '>=', first), ('date_end', '<=', last),
                           ('state', '!=', 'cancel')])
        self.assertIn(run_a, runs)
        self.assertIn(run_b, runs)
        self.assertEqual(month['runs'], len(runs))
        self.assertGreater(month['net'], 0, 'the seeded runs carry no net pay')
        self.assertAlmostEqual(month['net'], sum(runs.mapped('pb_total_net')), 2)
        self.assertAlmostEqual(month['gross'],
                               sum(runs.mapped('pb_total_gross')), 2)
        self.assertAlmostEqual(month['ded'],
                               sum(runs.mapped('pb_total_deductions')), 2)
        self.assertAlmostEqual(month['er'],
                               sum(runs.mapped('pb_total_employer_cost')), 2)
        self.assertAlmostEqual(month['total'], month['gross'] + month['er'], 2)
        self.assertEqual(month['people'], len(runs.slip_ids.filtered(
            lambda s: s.state != 'cancel').employee_id))
        self.assertAlmostEqual(month['avg'], month['net'] / month['people'], 4)
        self.assertEqual(month['balance_ok'], all(runs.mapped('pb_balance_ok')))
        self.assertFalse(month['done'], 'draft runs made a month done')

    def test_02b_a_person_in_two_runs_of_a_month_counts_once(self):
        """H32: an advance run and the end-month run pay the same people;
        People paid counts each of them once."""
        first, last = self._month(1)
        before = self.home()['months'][-2]['people']
        a = self._employee('Home Twice A')
        advance = self._run('Home twice advance', first, last)
        end = self._run('Home twice end', first, last)
        self._slip(advance, a, {'GROSS': 5000.0, 'DED': 0.0, 'NET': 5000.0})
        self._slip(end, a, {'GROSS': 7000.0, 'DED': 1000.0, 'NET': 6000.0})
        self.env.flush_all()
        self.assertEqual(self.home()['months'][-2]['people'], before + 1)

    def test_02c_an_account_number_on_the_employee_is_a_bank_account(self):
        """H31: the pay data keeps the account on the employee; a person with
        one is not counted as having no bank account."""
        Employee = self.env['hr.employee']
        if 'account_number' not in Employee._fields:
            self.skipTest('this build keeps no account number on the employee')
        first, last = self._month(0)
        with_acct = self._employee('Home Acct Yes')
        with_acct.account_number = '0123456789'
        without = self._employee('Home Acct No')
        run = self._run('Home bank run', first, last)
        self._slip(run, with_acct, {'GROSS': 1.0, 'DED': 0.0, 'NET': 1.0})
        self._slip(run, without, {'GROSS': 1.0, 'DED': 0.0, 'NET': 1.0})
        self.env.flush_all()
        Dash = self.env['pb.dashboard']
        cos = [self.company.id]
        self.assertEqual(Dash._home_no_bank(run.ids, cos).get(run.id, 0),
                         0 if without.bank_account_ids else 1)

    # =============================================================== test 3
    def test_03_another_company_s_run_is_not_mine(self):
        other = self.env['res.company'].create({'name': 'Home Other Co'})
        self.env.user.company_ids |= other
        mine = self.company
        emp = self._employee('Home Elsewhere', company=other)
        run = self._run('Home other company run', self.p_first, self.p_last)
        self._slip(run, emp, {'NET': 5000.0}, company=other)
        self.env.flush_all()

        before = self.home(companies=mine)
        data = self.home(companies=mine)
        self.assertNotIn(run.id, [r['id'] for r in data['runs']])
        self.assertEqual(data['period']['prepared'],
                         before['period']['prepared'])
        self.assertEqual(data['months'][-1]['runs'],
                         before['months'][-1]['runs'])
        # ... and the control: the same run IS visible from its own company.
        theirs = self.home(companies=other)
        self.assertIn(run.id, [r['id'] for r in theirs['runs']])
        self.assertEqual(theirs['period']['prepared'], 1)

    def test_03b_run_scope_counts_my_slips_only(self):
        other = self.env['res.company'].create({'name': 'Home Mixed Co'})
        self.env.user.company_ids |= other
        here = self._employee('Home Mixed Here')
        there = self._employee('Home Mixed There', company=other)
        run = self._run('Home mixed run', self.p_first, self.p_last)
        self._slip(run, here)
        self._slip(run, there, company=other)
        self.env.flush_all()
        row = next(r for r in self.home(companies=self.company)['runs']
                   if r['id'] == run.id)
        self.assertEqual(row['slips'], 1)

    # =============================================================== test 4
    def test_04_period(self):
        if 'pb.pay.hub' in self.env:
            self.assertEqual(self.period['stage'],
                             self.env['pb.pay.hub'].get_period_state()['stage'])
        else:
            self.assertIsNone(self.period['stage'])
        groups = self.env['hr.contract']._read_group(
            [('state', '=', 'open'),
             ('company_id', 'in', self.env.companies.ids)], ['employee_id'])
        self.assertEqual(self.period['expected'], len(groups))

        cutoff = min(self.today + relativedelta(days=2), self.p_last)
        self._calendar(cutoff, self.p_last)
        data = self.home()
        self.assertEqual(data['period']['cutoff'], cutoff.isoformat())
        self.assertEqual(data['period']['payday'], self.p_last.isoformat())

    # =============================================================== test 5
    def test_05_in_progress_and_latest(self):
        two_first, two_last = self._month(2)
        one_first, one_last = self._month(1)
        a = self._employee('Home Done A')
        b = self._employee('Home Draft B')
        done_run = self._run('Home done run', two_first, two_last)
        draft_run = self._run('Home draft run', one_first, one_last)
        self._slip(done_run, a)
        self._slip(draft_run, b)
        self._set_state(done_run, 'done')

        months = self.home()['months']
        self.assertTrue(months[-1]['inprogress'])
        self.assertFalse(any(m['inprogress'] for m in months[:-1]))
        self.assertTrue(months[-3]['done'])
        self.assertFalse(months[-2]['done'], 'a month with a draft run is done')
        self.assertTrue(months[-3]['latest'])
        self.assertEqual(sum(1 for m in months if m['latest']), 1)
        for month in months:
            if month['runs'] == 0:
                self.assertFalse(month['done'], 'an empty month reads done')

    # =============================================================== test 6
    def test_06a_nothing_waiting_is_an_empty_line(self):
        lone = self.env['res.company'].create({'name': 'Home Quiet Co'})
        groups = [self.env.ref('base.group_user').id]
        officer = self.env.ref('pb_hr_payroll_base.group_payroll_base_officer',
                               raise_if_not_found=False)
        if officer:
            groups.append(officer.id)
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Home Quiet Reader', 'login': 'home-quiet-reader',
            'company_id': lone.id, 'company_ids': [(6, 0, [lone.id])],
            'group_ids': [(6, 0, groups)]})
        data = self.home(user=user)
        self.assertEqual(data['needs_you'], [])
        if 'pb.approval.inbox' in self.env:
            # proves the inbox was actually read, not skipped by a fallback
            self.assertEqual(data['approvals_total'], 0)

    def test_06b_a_run_waiting_on_my_seat_comes_first(self):
        Run = self.env['hr.payslip.run']
        if not hasattr(Run, '_pb_runs_awaiting') \
                or 'biz.approval.engine' not in self.env:
            self.skipTest('pay runs are not on the approval engine here')
        process = self.env['biz.approval.process']._by_key('payrun')
        if not process:
            self.skipTest('the payrun approval process is not seeded here')
        groups = [self.env.ref('base.group_user').id]
        officer = self.env.ref('pb_hr_payroll_base.group_payroll_base_officer',
                               raise_if_not_found=False)
        if officer:
            groups.append(officer.id)
        approver = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Home Approver Person', 'login': 'home-approver',
                'email': 'home-approver@example.com',
                'company_id': self.company.id,
                'company_ids': [(6, 0, [self.company.id])],
                'group_ids': [(6, 0, groups)]})
        engine = self.env['biz.approval.engine']
        definition = {
            'schema_version': 1,
            'steps': [{'key': 's1', 'kind': 'approve', 'title': 'Home check',
                       'who': {'mode': 'people', 'user_ids': [approver.id]},
                       'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {
                'independent': False,
                'self_exception': {'enabled': False},
                'repeated': 'different', 'evidence': [],
                'due': {'kind': 'none', 'days': 1, 'day': 15,
                        'calendar_id': None},
                'late': {'remind_days': 1, 'escalate_days': 2,
                         'reassign': False},
            },
        }
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([('company_id', '=', self.company.id),
                        ('process_id', '=', process.id),
                        ('scope_key', '=', ''), ('kind_key', '=', 'any'),
                        ('active', '=', True)]).write({'active': False})
        workflow = self.env['biz.approval.workflow'].sudo().create({
            'name': 'Home route', 'company_id': self.company.id,
            'process_id': process.id, 'owner_user_id': self.env.user.id})
        version = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': workflow.id, 'revision': 1, 'status': 'draft',
            'definition': definition})
        checks = engine.validate_for_publish(version.id)
        if checks['errors']:
            self.skipTest('the one-person route does not validate here: %s'
                          % checks['errors'])
        engine.publish(version.id, version.draft_revision, None, 'test',
                       [w['code'] for w in checks['warnings']])
        Binding.create({
            'company_id': self.company.id, 'process_id': process.id,
            'scope_key': '', 'scope_label': self.company.name,
            'kind_key': 'any', 'workflow_id': workflow.id, 'mode': 'follow'})

        emp = self._employee('Home Waiting Person')
        run = self._run('Home waiting run', self.p_first, self.p_last)
        self._slip(run, emp, {'NET': 4200.0})
        engine.submit(run)
        run.invalidate_recordset()
        self.assertEqual(run.state, 'approval_pending')

        data = self.home(user=approver)
        self.assertEqual(data['needs_you'][0],
                         {'key': 'runs_to_approve', 'n': 1})
        self.assertEqual(data['period']['awaiting_me'], 1)
        self.assertEqual(data['period']['awaiting_run']['id'], run.id)
        self.assertTrue(data['period']['awaiting_run']['submitted_by'])
        self.assertTrue(next(r for r in data['runs']
                             if r['id'] == run.id)['awaiting_me'])
        approve = next(s for s in data['steps'] if s['key'] == 'approve')
        self.assertEqual(approve['state'], 'wait')
        self.assertEqual(approve['run'], run.name)

    def test_06c_a_leave_waiting_for_approval(self):
        emp = self._employee('Home Leave Asker')
        self._leave(emp, self.today, validate=False)
        data = self.home()
        got = {i['key']: i['n'] for i in data['needs_you']}
        if 'pb.approval.inbox' in self.env:
            # With the approvals inbox the chip is "leave I must decide",
            # read off my own cards — the same list the inbox shows.
            cards = self.env['pb.approval.inbox'].list_requests(
                tab='mine')['cards']
            want = sum(1 for c in cards if c.get('process_key') == 'leave')
            self.assertEqual(got.get('leave_to_approve', 0), want)
        else:
            self.assertGreaterEqual(got.get('leave_to_approve', 0), 1)
        self.assertGreaterEqual(data['people']['leave_pending'] or 0, 1)

    # =============================================================== test 7
    def test_07_people(self):
        before = self.home()['people']
        joiner = self._employee('Home Joiner', start=self.p_first)
        if joiner.first_contract_date != self.p_first:
            joiner.first_contract_date = self.p_first
        self._employee('Home Leaver', start='2020-01-01', end=self.p_last)
        self._employee('Home No Contract', contract=False)
        self.env.flush_all()
        after = self.home()['people']
        self.assertEqual(after['headcount'] - before['headcount'], 3)
        self.assertEqual(after['active_contracts'] - before['active_contracts'], 2)
        self.assertEqual(after['joined'] - before['joined'], 1)
        self.assertEqual(after['leaving'] - before['leaving'], 1)
        self.assertEqual(after['no_contract'] - before['no_contract'], 1)

    def test_07b_out_today(self):
        if self.today.weekday() >= 5:
            self.skipTest('today is a weekend; a one-day leave has no length')
        before = self.home()['people']
        if before['out_today'] is None:
            self.skipTest('hr.leave is not installed')
        emp = self._employee('Home Out Today')
        leave = self._leave(emp, self.today, validate=True)
        self.assertEqual(leave.state, 'validate')
        after = self.home()['people']
        self.assertEqual(after['out_today'] - before['out_today'], 1)
        self.assertEqual(after['week'][0]['n'] - before['week'][0]['n'], 1)
        self.assertEqual(after['week'][0]['date'], self.today.isoformat())
        self.assertEqual(len(after['week']), 7)
        self.assertLessEqual(len(after['out_breakdown']), 3)

    # =============================================================== test 8
    def test_08_upcoming(self):
        cutoff = min(self.today + relativedelta(days=2), self.p_last)
        self._calendar(cutoff, self.p_last)
        items = self.home()['upcoming']
        dates = [i['date'] for i in items]
        self.assertEqual(dates, sorted(dates))
        self.assertTrue(all(d >= self.today.isoformat() for d in dates))
        self.assertLessEqual(len(items), 6)
        kinds = {i['kind']: i for i in items}
        self.assertIn('cutoff', kinds)
        self.assertEqual(kinds['cutoff']['date'], cutoff.isoformat())
        for item in items:
            self.assertIn(item['kind'], ('cutoff', 'payday', 'contracts_end',
                                         'holiday', 'interviews'))
            self.assertIsInstance(item['extra'], dict)

    # =============================================================== test 9
    def test_09_every_foreign_read_is_guarded_and_no_line_table(self):
        src = _read(HOME_PY)
        guarded, unguarded = _guarded_env_reads(src)
        self.assertFalse(unguarded - CORE_MODELS,
                         'home_data reads %s outside optional()'
                         % sorted(unguarded - CORE_MODELS))
        self.assertEqual(guarded, HOME_MODELS,
                         'the guarded set drifted from HOME_MODELS: %s'
                         % sorted(guarded ^ HOME_MODELS))
        self.assertTrue(HOME_MODELS <= OPTIONAL_MODELS)
        # The pay band rule: no token of the payslip line table at all.
        for token in ('hr_payslip' + '_line', 'hr.payslip' + '.line'):
            self.assertNotIn(token, src)
        # every optional() call names a literal model
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') \
                    == 'optional':
                self.assertIsInstance(node.args[0], ast.Constant)

    # ============================================================== test 10
    def test_10_the_kit_may_be_named_the_two_modules_may_not(self):
        self.assertFalse(names_forbidden_module('pb_import_kit'))
        self.assertFalse(names_forbidden_module(
            "from odoo.addons.pb_import_kit.static import ic"))
        self.assertTrue(names_forbidden_module('pb_import'))
        self.assertTrue(names_forbidden_module('import odoo.addons.pb_learn'))

    # ============================================================== test 11
    def test_11_timing(self):
        # `assertLogs` sees nothing under the platform's test logging, so the
        # log call itself is observed (HOME ledger H17).
        with patch.object(home_module._logger, 'info',
                          wraps=home_module._logger.info) as info:
            data = self.home()
        lines = [call.args[0] % call.args[1:] for call in info.call_args_list]
        self.assertTrue(any(line.startswith('home_data %d ms'
                                            % data['timing_ms']['total'])
                            for line in lines), lines)
        timing = data['timing_ms']
        # For the phase report: the clone's timing and which sections are
        # absent here (None), in one line.
        logging.getLogger(__name__).info(
            'HOME P1 clone: timing=%s none=%s upcoming=%s', timing,
            sorted(k for k, v in data.items() if v is None),
            [i['kind'] for i in data['upcoming']])
        self.assertLess(timing['total'], 1500, timing)
        for key in TIMING_KEYS:
            self.assertLess(timing[key], 600, '%s: %s' % (key, timing))
        parts = sum(timing[k] for k in TIMING_KEYS if k != 'total')
        self.assertLessEqual(parts, timing['total'] + 5, timing)

    # ============================================================== test 12
    def test_12_activation_is_the_same_checklist(self):
        self.assertEqual(self.D.get_home_data()['activation'],
                         self.D.get_dashboard_data()['activation'])
