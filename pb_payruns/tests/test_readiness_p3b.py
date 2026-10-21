# -*- coding: utf-8 -*-
"""NAV P3b — readiness on the run cards (docs/handovers/NAV_P3B_PAYROLL_READINESS.md).

Every open card answers "can this run move, and who must act": a checklist
with an owner on each line, the month's two dates on the hero, and an
attendance-close line that advises and never blocks. These tests pin the
payload; the walk covers the pixels.

pb_comp_ben (the Payroll calendar) and pb_close (day locks) are NOT
dependencies of pb_payruns. The tests that need them skip when the model is
absent, so this file runs on any database pb_payruns installs on.
"""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReadinessP3b(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Readiness P3b Co'})
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'P3b Calendar', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) or \
            cls.env['hr.contract.type'].create({'name': 'P3b Type'})
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': cls.company.id,
                  'company_ids': [(6, 0, [cls.company.id])]}
        cls.preparer = Users.create(dict(common, name='Tran Linh Preparer',
                                         login='p3b_preparer'))
        cls.returner = Users.create(dict(common, name='Nguyen Thi Hoa',
                                         login='p3b_returner'))
        cls.payroll_mgr = Users.create(dict(common, name='Pham Van Payroll',
                                            login='p3b_payroll'))
        cls.att_mgr = Users.create(dict(common, name='Le Thu Attendance',
                                        login='p3b_attendance'))
        cls.board = cls.env['pb.payruns'].with_company(cls.company)
        cls.today = fields.Date.context_today(cls.board)
        cls.first = cls.today.replace(day=1)
        cls.last = cls.first + relativedelta(months=1, days=-1)
        # A database may already hold a SHARED calendar row for this month
        # (company empty), which every company reads; start from none.
        Cal = cls.env.get('pb.payroll.calendar')
        if Cal is not None:
            Cal.sudo().search([('month', '=', cls.first),
                               ('company_id', '=', False)]).unlink()

    # ------------------------------------------------------------ helpers
    @classmethod
    def _run(cls, name, start=None, end=None, n=1, manager=None):
        start, end = start or cls.first, end or cls.last
        run = cls.env['hr.payslip.run'].create({
            'name': name, 'date_start': start, 'date_end': end})
        for i in range(n):
            employee = cls.env['hr.employee'].create({
                'name': '%s person %s' % (name, i), 'company_id': cls.company.id,
                'attendance_manager_id': manager.id if manager else False})
            contract = cls.env['hr.contract'].create({
                'name': 'Contract %s %s' % (name, i), 'employee_id': employee.id,
                'company_id': cls.company.id, 'date_start': '2026-01-01',
                'wage': 1000.0, 'type_id': cls.ctype.id,
                'resource_calendar_id': cls.calendar.id,
            })
            cls.env['hr.payslip'].create({
                'name': 'Slip %s %s' % (name, i), 'employee_id': employee.id,
                'date_from': start, 'date_to': end,
                'payslip_run_id': run.id, 'company_id': cls.company.id,
                'contract_id': contract.id,
            })
        return run

    def _card(self, run):
        data = self.board.get_board_data()
        return data, next(b for b in data['batches'] if b['id'] == run.id)

    def _checks(self, run, **kw):
        """`_run_checks` straight, so the health figures can be set without
        computing payslips."""
        readiness = self.board._readiness_context(
            run, {run.id: self.company.id})
        args = dict(unsourced=0, balance_ok=True, balance_gap=0.0, symbol='₫')
        args.update(kw)
        state = args.pop('state', run.state or 'draft')
        nxt = 'submit' if state == 'draft' else 'decide'
        return self.board._run_checks(run, state, nxt, self.company.id,
                                      readiness, **args)

    def _give_payroll_mgr(self, user):
        Role = self.env['biz.approval.role']
        role = Role.search([('key', '=', 'payroll_mgr')], limit=1)
        if not role:
            self.skipTest('no payroll_mgr responsibility on this database')
        self.env['biz.approval.responsibility'].create({
            'company_id': self.company.id, 'role_id': role.id,
            'scope_key': '', 'user_id': user.id,
            'date_from': self.today - timedelta(days=30)})

    def _lock(self, days):
        Lock = self.env['pb.wf.lock'].sudo()
        Lock.create([{'company_id': self.company.id, 'date': d,
                      'state': 'locked'} for d in days])

    # ------------------------------------------------------------ 1. hero dates
    def test_01_period_carries_the_four_deadline_keys_without_a_calendar(self):
        period = self.board.get_board_data()['period']
        for key in ('cutoff', 'pay_date', 'cutoff_in_days', 'pay_in_days'):
            self.assertIn(key, period)
            self.assertIsNone(period[key], '%s must be None with no row' % key)

    def test_02_calendar_row_gives_dates_and_days_ahead(self):
        Cal = self.env.get('pb.payroll.calendar')
        if Cal is None:
            self.skipTest('pb_comp_ben is not installed')
        cutoff = self.today + timedelta(days=4)
        pay = self.today + timedelta(days=10)
        Cal.create({'month': self.first, 'company_id': self.company.id,
                    'cutoff_date': cutoff, 'pay_date': pay})
        period = self.board.get_board_data()['period']
        self.assertEqual(period['cutoff'], cutoff.isoformat())
        self.assertEqual(period['pay_date'], pay.isoformat())
        self.assertEqual(period['cutoff_in_days'], 4)
        self.assertEqual(period['pay_in_days'], 10)
        self.assertTrue(period['cutoff_label'])
        self.assertTrue(period['pay_label'])

    def test_03_past_dates_count_negative_and_company_row_beats_shared(self):
        Cal = self.env.get('pb.payroll.calendar')
        if Cal is None:
            self.skipTest('pb_comp_ben is not installed')
        Cal.create({'month': self.first, 'company_id': False,
                    'cutoff_date': self.today + timedelta(days=20),
                    'pay_date': self.today + timedelta(days=25)})
        period = self.board.get_board_data()['period']
        self.assertEqual(period['cutoff_in_days'], 20, 'the shared row is used')
        Cal.create({'month': self.first, 'company_id': self.company.id,
                    'cutoff_date': self.today - timedelta(days=3),
                    'pay_date': self.today - timedelta(days=1)})
        period = self.board.get_board_data()['period']
        self.assertEqual(period['cutoff_in_days'], -3, 'the company row wins')
        self.assertEqual(period['pay_in_days'], -1)

    # ------------------------------------------------------------ 2. checklist
    def test_04_every_card_carries_checks_and_ready(self):
        run = self._run('P3b Shape')
        _, card = self._card(run)
        for key in ('checks', 'ready', 'close_weeks',
                    'unsourced', 'balance_ok', 'balance_gap', 'return_note'):
            self.assertIn(key, card)
        for c in card['checks']:
            self.assertEqual(
                {'key', 'tone', 'text', 'owner', 'next', 'advisory'} - set(c),
                set(), 'a line is missing a key')

    def test_05_sent_back_line_names_the_preparer_as_owner(self):
        run = self._run('P3b Back')
        run.sudo().write({'pb_prepared_uid': self.preparer.id,
                          'pb_return_note': 'Overtime reads 46 hours',
                          'pb_return_uid': self.returner.id,
                          'pb_return_date': fields.Datetime.now()})
        checks, ready, _w = self._checks(run)
        self.assertEqual(checks[0]['key'], 'sent_back')
        self.assertEqual(checks[0]['tone'], 'amber')
        self.assertIn('Overtime reads 46 hours', checks[0]['text'])
        self.assertIn('Hoa', checks[0]['text'], 'given name of who sent it back')
        self.assertIn('Nguyen Thi Hoa', checks[0]['full'])
        self.assertEqual(checks[0]['owner']['uid'], self.preparer.id)
        self.assertFalse(ready, 'a sent-back draft is not ready to send in')

    def test_06_three_lines_three_owners_in_the_spec_order(self):
        """Sent back + no source data + an open week: three lines, and the
        owners are the preparer (twice) and the attendance manager."""
        if 'pb.wf.lock' not in self.env:
            self.skipTest('pb_close is not installed')
        run = self._run('P3b Three', date(2026, 8, 3), date(2026, 8, 9),
                        manager=self.att_mgr)
        run.sudo().write({'pb_prepared_uid': self.preparer.id,
                          'pb_return_note': 'Fix NV0203',
                          'pb_return_uid': self.returner.id})
        checks, ready, weeks = self._checks(run, unsourced=3)
        self.assertEqual([c['key'] for c in checks],
                         ['sent_back', 'unsourced', 'close_week'])
        self.assertEqual(checks[1]['tone'], 'rose')
        self.assertIn('3 payslips', checks[1]['text'])
        self.assertEqual(checks[1]['next']['key'], 'run')
        self.assertEqual(checks[2]['owner']['uid'], self.att_mgr.id)
        self.assertTrue(checks[2]['advisory'])
        self.assertEqual(weeks, {'closed': 0, 'total': 1})
        self.assertFalse(ready)

    def test_07_owner_falls_back_to_payroll_manager_then_the_team(self):
        # A new company may be seeded a holder from the officer group
        # (approval_seed); end it so the team fallback is what is tested.
        Resp = self.env.get('biz.approval.responsibility')
        if Resp is not None:
            Resp.search([('company_id', '=', self.company.id),
                         ('role_key', '=', 'payroll_mgr')]).write({'active': False})
        run = self._run('P3b Owner')
        checks, _r, _w = self._checks(run, unsourced=1)
        owner = checks[0]['owner']
        self.assertTrue(owner['team'])
        self.assertFalse(owner['uid'])
        self.assertEqual(owner['name'], 'Payroll team')
        self._give_payroll_mgr(self.payroll_mgr)
        checks, _r, _w = self._checks(run, unsourced=1)
        self.assertEqual(checks[0]['owner']['uid'], self.payroll_mgr.id)
        self.assertEqual(checks[0]['owner']['short'], 'Payroll',
                         'a three-word name is called by its last word')

    def test_08_balance_line_says_the_gap(self):
        run = self._run('P3b Gap')
        checks, ready, _w = self._checks(run, balance_ok=False,
                                         balance_gap=1200000)
        line = next(c for c in checks if c['key'] == 'balance')
        self.assertEqual(line['tone'], 'rose')
        self.assertIn('1,200,000', line['text'])
        self.assertFalse(ready)

    def test_09_me_is_marked_on_my_own_line(self):
        run = self._run('P3b Me')
        run.sudo().write({'pb_prepared_uid': self.env.uid})
        checks, _r, _w = self._checks(run, unsourced=2)
        self.assertTrue(checks[0]['owner']['me'])

    # ------------------------------------------------------------ 3. close line
    def test_10_close_weeks_follow_pb_close_rule(self):
        """Mondays overlapping the period; a week counts only its own days in
        the period, so a week with no day inside is never listed."""
        weeks = self.board._close_weeks(date(2026, 8, 2), date(2026, 8, 31))
        self.assertEqual(weeks[0][0], date(2026, 7, 27))
        self.assertEqual(weeks[0][1], [date(2026, 8, 2)],
                         'only Sunday 2 Aug belongs to this period')
        self.assertEqual(weeks[-1][0], date(2026, 8, 31))
        self.assertEqual(len(weeks), 6)
        for _monday, days in weeks:
            self.assertTrue(days)
        self.assertEqual(self.board._close_weeks(date(2026, 8, 9), date(2026, 8, 1)), [])

    def test_11_close_line_max_two_then_more_and_gone_when_locked(self):
        if 'pb.wf.lock' not in self.env:
            self.skipTest('pb_close is not installed')
        ds, de = date(2026, 8, 3), date(2026, 8, 30)       # four whole weeks
        run = self._run('P3b Weeks', ds, de)
        checks, ready, weeks = self._checks(run)
        close = [c for c in checks if c['key'] == 'close_week']
        self.assertEqual(len(close), 2, 'at most two lines')
        self.assertEqual(close[-1]['more'], '+2 more weeks')
        self.assertEqual(close[0]['owner']['name'], 'Attendance team')
        self.assertEqual(weeks, {'closed': 0, 'total': 4})
        self.assertTrue(ready, 'advice never makes a clean draft unready')
        # lock three weeks: one line left, no "more"
        self._lock([ds + timedelta(days=i) for i in range(21)])
        checks, _r, weeks = self._checks(run)
        close = [c for c in checks if c['key'] == 'close_week']
        self.assertEqual(len(close), 1)
        self.assertEqual(close[0]['week'], '2026-08-24')
        self.assertEqual(close[0]['more'], '')
        self.assertEqual(weeks, {'closed': 3, 'total': 4})
        # lock the last week: the line is gone, the count stays for the peek
        self._lock([ds + timedelta(days=i) for i in range(21, 28)])
        checks, _r, weeks = self._checks(run)
        self.assertFalse([c for c in checks if c['key'] == 'close_week'])
        self.assertEqual(weeks, {'closed': 4, 'total': 4})

    def test_12_a_reopened_day_opens_its_week_again(self):
        if 'pb.wf.lock' not in self.env:
            self.skipTest('pb_close is not installed')
        ds, de = date(2026, 8, 3), date(2026, 8, 9)
        run = self._run('P3b Reopen', ds, de)
        self._lock([ds + timedelta(days=i) for i in range(7)])
        self.assertFalse([c for c in self._checks(run)[0]
                          if c['key'] == 'close_week'])
        self.env['pb.wf.lock'].sudo().search(
            [('company_id', '=', self.company.id), ('date', '=', ds)]).write(
            {'state': 'open', 'reason': 'Late punch'})
        self.assertTrue([c for c in self._checks(run)[0]
                         if c['key'] == 'close_week'])

    # ------------------------------------------------------------ 4. ready
    def test_13_ready_only_for_a_clean_draft(self):
        run = self._run('P3b Ready', date(2026, 8, 3), date(2026, 8, 9))
        _, card = self._card(run)
        self.assertTrue(card['ready'])
        self.assertEqual(self._checks(run, unsourced=1)[1], False)
        self.assertEqual(self._checks(run, balance_ok=False,
                                      balance_gap=5.0)[1], False)
        self.assertEqual(self._checks(run, state='approval_pending')[1], False)
        checks, ready, weeks = self._checks(run, state='done', unsourced=4)
        self.assertEqual((checks, ready, weeks), ([], False, None),
                         'Done cards keep the delivery rail only')

    def test_14_submit_still_works_with_an_open_week(self):
        """Advice never blocks: the card still offers Submit."""
        if 'pb.wf.lock' not in self.env:
            self.skipTest('pb_close is not installed')
        run = self._run('P3b Submit', date(2026, 8, 3), date(2026, 8, 9))
        _, card = self._card(run)
        self.assertTrue([c for c in card['checks'] if c['key'] == 'close_week'])
        self.assertEqual(card['next_action'], 'submit')
        self.assertEqual(card['can_act'], self.env['hr.payslip.run'].has_access('write'))

    def test_15_learn_right_now_still_reads_the_board(self):
        """Learn's own "ready" rule is unchanged (non-goal): a clean draft is
        still offered as one to submit."""
        run = self._run('P3b Learn', date(2026, 8, 3), date(2026, 8, 9))
        items = self.board.learn_right_now()
        submit = [i for i in items if i.get('key') == 'submit']
        self.assertTrue(submit, 'Learn no longer offers the clean draft')
        self.assertIn(run.name, submit[0]['names'] + [run.name])
