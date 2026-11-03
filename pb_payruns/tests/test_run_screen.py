# -*- coding: utf-8 -*-
"""PRS P1 — the pay run screen's one payload (`pb.payruns.get_run_screen`).

docs/handovers/payrunscreen/PRS_P1_HANDOVER.md, test cases T1–T13. These pin
the payload the redesigned pay run screen is built on: the journey, the ONE
next step, the four checks, who signs it off, the people table and what the
menus offer — in each of the moments the approved mock-up draws.

WHAT HAD TO BE FABRICATED. A test database has no payroll, so each case builds
the minimum by hand: a run, payslips with category-coded lines (gross, the
deductions and take-home), and — where the route matters — a published
two-step approval route built through the engine's own public API, exactly as
`test_approval_engine` does. Nothing here touches a real tenant.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


def _route(steps):
    return {
        'schema_version': 1,
        'steps': steps,
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': {
            'independent': False,
            'self_exception': {'enabled': False},
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'none', 'days': 1, 'day': 15, 'calendar_id': None},
            'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
        },
    }


def _step(key, role, title, kind='approve'):
    return {'key': key, 'kind': kind, 'title': title,
            'who': {'mode': 'role', 'role': role, 'scope': 'company'},
            'min_amount': 0, 'condition': None}


def _strings(value):
    """Every string anywhere in a payload."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)


@tagged('post_install', '-at_install')
class TestRunScreen(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Run = cls.env['hr.payslip.run']
        cls.board = cls.env['pb.payruns']
        cls.engine = cls.env['biz.approval.engine']
        cls.process = cls.env['biz.approval.process']._by_key('payrun')
        cls.rule = cls.env['hr.salary.rule'].search([], limit=1)
        cls.agro = cls.env['hr.department'].create(
            {'name': 'PRS Agronomy', 'company_id': cls.company.id})
        cls.fin = cls.env['hr.department'].create(
            {'name': 'PRS Finance', 'company_id': cls.company.id})
        cls.preparer = cls._user('prs_preparer', 'Tran Thu Ha')
        cls.hr = cls._user('prs_hr', 'Pham Minh Anh')
        cls.finance = cls._user('prs_finance', 'Lan Nguyen')
        cls.outsider = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'PRS Outsider', 'login': 'prs_outsider',
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.emp_a = cls._employee('PRS Alpha Nguyen', cls.agro)
        cls.emp_b = cls._employee('PRS Bravo Tran', cls.agro)
        cls.emp_c = cls._employee('PRS Charlie Le', cls.fin)
        Config = cls.env['hr.formula.config']
        values = {'name': 'PRS Viet scheme', 'code': 'PRSVIET',
                  'country_code': 'VN', 'company_id': cls.company.id}
        if 'state' in Config._fields:
            values['state'] = 'active'
        cls.viet = Config.create(values)

    @classmethod
    def _user(cls, login, name):
        groups = [cls.env.ref('base.group_user').id]
        officer = cls.env.ref('pb_hr_payroll_base.group_payroll_base_officer',
                              raise_if_not_found=False)
        if officer:
            groups.append(officer.id)
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': name, 'login': login, 'email': '%s@example.com' % login,
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, groups)]})

    @classmethod
    def _employee(cls, name, department):
        employee = cls.env['hr.employee'].create({
            'name': name, 'company_id': cls.company.id,
            'department_id': department.id})
        cls.env['hr.contract'].create({
            'name': '%s contract' % name, 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': cls.company.id})
        return employee

    # ------------------------------------------------------------ fixtures
    def _cat(self, code):
        found = self.env['hr.salary.rule.category'].search(
            [('code', '=', code)], limit=1)
        if not found:
            self.skipTest("no '%s' salary-rule category in this database" % code)
        return found

    def _run(self, name='PRS September 2026', start='2026-09-01',
             end='2026-09-30', config=None):
        values = {'name': name, 'date_start': start, 'date_end': end}
        if config is not None:
            values['pb_formula_config_id'] = config.id
        return self.Run.create(values)

    def _slip(self, run, employee, net=9000.0, ded=1000.0, gross=None,
              lines=True, **extra):
        contract = self.env['hr.contract'].search(
            [('employee_id', '=', employee.id)], limit=1)
        values = {
            'employee_id': employee.id, 'name': 'PRS slip %s' % employee.name,
            'contract_id': contract.id,
            'date_from': run.date_start, 'date_to': run.date_end,
            'company_id': self.company.id, 'payslip_run_id': run.id}
        values.update(extra)
        slip = self.env['hr.payslip'].create(values)
        if lines:
            gross = net + ded if gross is None else gross
            for code, amount in (('GROSS', gross), ('DED', ded), ('NET', net)):
                self._line(slip, code, code, amount)
        return slip

    def _line(self, slip, code, category_code, amount, role=None, detail=False):
        vals = {
            'slip_id': slip.id, 'name': code, 'code': code,
            'amount': amount, 'quantity': 1.0, 'rate': 100.0,
            'employee_id': slip.employee_id.id,
            'contract_id': slip.contract_id.id,
            'category_id': self._cat(category_code).id,
            'salary_rule_id': self.rule.id}
        Line = self.env['hr.payslip.line']
        if role:
            if 'pay_role' not in Line._fields:
                self.skipTest('the formula engine is not installed here')
            vals['pay_role'] = role
        if detail:
            if 'component_detail' not in Line._fields:
                self.skipTest('the formula engine is not installed here')
            vals['component_detail'] = True
        return Line.create(vals)

    def _hold(self, role_key, user):
        role = self.env['biz.approval.role'].search([('key', '=', role_key)],
                                                    limit=1)
        if not role:
            self.skipTest("the '%s' responsibility is not in this database"
                          % role_key)
        Resp = self.env['biz.approval.responsibility'].sudo()
        existing = Resp.search([
            ('company_id', '=', self.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', ''), ('active', '=', True)], limit=1)
        if existing:
            existing.write({'user_id': user.id})
            return existing
        return Resp.create({
            'company_id': self.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': self.company.name,
            'user_id': user.id})

    def _route_two_steps(self):
        """HR review (Pham Minh Anh), then Finance (Lan Nguyen), company-wide."""
        if not self.process:
            self.skipTest('the approval catalogue is not installed here')
        self._hold('hr_lead', self.hr)
        self._hold('finance', self.finance)
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('active', '=', True)]).write({'active': False})
        workflow = self.env['biz.approval.workflow'].sudo().create({
            'name': 'PRS route', 'company_id': self.company.id,
            'process_id': self.process.id, 'owner_user_id': self.env.user.id})
        version = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': workflow.id, 'revision': 1, 'status': 'draft',
            'definition': _route([
                _step('s1', 'hr_lead', 'HR review', kind='review'),
                _step('s2', 'finance', 'Finance approval')])})
        checks = self.engine.validate_for_publish(version.id)
        self.assertFalse(checks['errors'], checks['errors'])
        self.engine.publish(version.id, version.draft_revision, None, 'test',
                            [w['code'] for w in checks['warnings']])
        Binding.create({
            'company_id': self.company.id, 'process_id': self.process.id,
            'scope_key': '', 'scope_label': self.company.name,
            'kind_key': 'any', 'workflow_id': workflow.id, 'mode': 'follow'})
        return workflow

    def _screen(self, run, user=None):
        board = self.board.with_user(user) if user else self.board
        run.invalidate_recordset()
        return board.get_run_screen(run.id)

    def _ready_draft(self):
        self._route_two_steps()
        run = self._run()
        self._slip(run, self.emp_a, net=9000.0)
        self._slip(run, self.emp_b, net=7000.0)
        return run

    # ================================================================= T1
    def test_t1_a_good_draft_is_ready_to_send(self):
        run = self._ready_draft()
        screen = self._screen(run)
        self.assertEqual(screen['run']['id'], run.id)
        self.assertEqual(screen['header']['status']['key'], 'draft')
        self.assertEqual(screen['header']['people'], 2)
        self.assertEqual(screen['primary']['kind'], 'submit')
        self.assertEqual(screen['primary']['method'], 'action_approval_submit')
        self.assertEqual(screen['primary']['warn'], 0)
        self.assertFalse(screen['primary']['confirm']['danger'])
        self.assertIn('Pham Minh Anh', screen['primary']['confirm']['body'])
        self.assertEqual([j['state'] for j in screen['journey']],
                         ['done', 'done', 'now', 'later', 'later'])
        self.assertEqual([j['key'] for j in screen['journey']],
                         ['prepare', 'check', 'approve', 'pay', 'deliver'])
        checks = screen['checks']
        self.assertEqual(checks['verdict'], 'ok')
        self.assertEqual([i['key'] for i in checks['items']],
                         ['data', 'balance', 'calculated', 'route'])
        self.assertTrue(all(i['ok'] for i in checks['items']), checks['items'])
        # who signs it off, previewed exactly as Submit would resolve it
        route = screen['route']
        self.assertEqual(route['mode'], 'preview')
        self.assertFalse(route['error'])
        self.assertEqual([s['name'] for s in route['seats']],
                         ['Pham Minh Anh', 'Lan Nguyen'])
        self.assertEqual([s['status'] for s in route['seats']], ['later', 'later'])
        # the money, from the board's own card
        money = screen['money']
        self.assertEqual(money['net'], 16000.0)
        self.assertEqual(money['gross'], 18000.0)
        self.assertEqual(money['deductions'], 2000.0)
        self.assertIn('2 people take home', money['sentence'])
        # the people table and its teams
        people = screen['people']
        self.assertEqual(people['total'], 2)
        self.assertEqual(people['rows'][0]['net'], 9000.0)
        self.assertEqual(people['rows'][0]['team'], 'PRS Agronomy')
        self.assertEqual(people['teams'], [
            {'name': 'PRS Agronomy', 'count': 2, 'net': 16000.0}])
        self.assertEqual(people['counts'], {'all': 2, 'flagged': 0, 'changed': 0})
        self.assertTrue(screen['settings_editable'])
        self.assertTrue(screen['bulk']['delete'])
        # nothing was written: still a draft with no request
        run.invalidate_recordset()
        self.assertEqual(run.state, 'draft')
        self.assertFalse(run.approval_request_id)

    # ================================================================= T2
    def test_t2_an_empty_draft_asks_for_payslips(self):
        run = self._run()
        screen = self._screen(run)
        self.assertEqual(screen['primary']['kind'], 'make')
        self.assertEqual(screen['primary']['action'],
                         'om_hr_payroll.action_hr_payslip_by_employees')
        self.assertEqual(screen['primary']['context']['active_id'], run.id)
        self.assertEqual(screen['journey'][0]['state'], 'now')
        self.assertEqual(screen['people']['rows'], [])
        for key in ('net', 'gross', 'deductions', 'employer_cost', 'total_cost'):
            self.assertEqual(screen['money'][key], 0.0)
        self.assertIsNone(screen['compare'])
        self.assertEqual(screen['checks']['verdict'], 'wait')
        self.assertEqual(screen['checks']['items'], [])
        self.assertEqual(screen['route']['mode'], 'none')
        self.assertEqual(screen['actions']['downloads'], [])
        self.assertFalse(screen['bulk']['pdf'])

    # ================================================================= T3
    def test_t3_two_problems_make_a_bad_verdict_and_a_warning(self):
        Slip = self.env['hr.payslip']
        if 'pb_sourced_inputs' not in Slip._fields:
            self.skipTest('the formula engine is not installed here')
        self._route_two_steps()
        run = self._run()
        nodata = self._slip(
            run, self.emp_a, net=9000.0, calculation_method='formula',
            formula_input_sources='{"BASE": {"src": "none", "via": "default"}}',
            pb_sourced_inputs=0)
        # ₫4,000 of this slip's gross is in no band at all
        self._slip(run, self.emp_b, net=5000.0, ded=1000.0, gross=10000.0)
        screen = self._screen(run)
        checks = screen['checks']
        self.assertEqual(checks['verdict'], 'bad')
        self.assertEqual({i['key']: i['ok'] for i in checks['items']},
                         {'data': False, 'balance': False, 'calculated': True,
                          'route': True})
        data = checks['items'][0]
        self.assertEqual(data['title'], '1 payslip has no source data')
        self.assertEqual(data['door']['kind'], 'flagged')
        self.assertEqual(screen['primary']['warn'], 2)
        self.assertTrue(screen['primary']['confirm'])
        self.assertTrue(screen['primary']['confirm']['danger'])
        self.assertEqual(screen['journey'][1]['state'], 'warn')
        self.assertEqual(screen['journey'][2]['state'], 'later')
        row = next(r for r in screen['people']['rows']
                   if r['slip_id'] == nodata.id)
        self.assertEqual(row['flag']['kind'], 'rose')
        self.assertEqual(screen['people']['counts']['flagged'], 1)

    def test_t3b_a_payslip_with_no_lines_is_not_calculated(self):
        self._route_two_steps()
        run = self._run()
        self._slip(run, self.emp_a)
        empty = self._slip(run, self.emp_b, lines=False)
        screen = self._screen(run)
        calculated = next(i for i in screen['checks']['items']
                          if i['key'] == 'calculated')
        self.assertFalse(calculated['ok'])
        row = next(r for r in screen['people']['rows'] if r['slip_id'] == empty.id)
        self.assertEqual(row['flag'], {'kind': 'rose',
                                       'text': 'Not calculated yet'})

    # ================================================================= T4
    def test_t4_a_run_sent_back_is_sent_again(self):
        run = self._ready_draft()
        run.write({'pb_return_note': 'Overtime for Operations looks doubled',
                   'pb_return_uid': self.hr.id})
        screen = self._screen(run)
        self.assertEqual(screen['header']['status']['key'], 'sent_back')
        self.assertEqual(screen['primary']['kind'], 'resubmit')
        self.assertEqual(screen['primary']['label'], 'Send again')
        self.assertEqual(screen['journey'][1]['state'], 'warn')
        self.assertEqual(screen['journey'][2]['state'], 'later')

    # ================================================================= T5
    def test_t5_a_pending_run_shows_live_seats_and_who_acts(self):
        run = self._ready_draft()
        self.engine.with_user(self.preparer).submit(run.with_user(self.preparer))
        run.invalidate_recordset()
        self.assertEqual(run.state, 'approval_pending')

        approver = self._screen(run, user=self.hr)
        self.assertEqual(approver['header']['status']['key'], 'pending')
        self.assertEqual(approver['primary']['kind'], 'decide')
        route = approver['route']
        self.assertEqual(route['mode'], 'live')
        self.assertEqual([s['status'] for s in route['seats']], ['now', 'later'])
        self.assertEqual(route['seats'][0]['name'], 'Pham Minh Anh')
        self.assertEqual(approver['journey'][2]['state'], 'now')
        self.assertIn('Pham Minh Anh', approver['journey'][2]['sub'])
        self.assertEqual(approver['checks']['verdict'], 'wait')
        self.assertFalse(approver['settings_editable'])
        # the approver reads names past an employee record they may not open
        self.assertEqual(approver['people']['total'], 2)
        self.assertTrue(all(r['name'] for r in approver['people']['rows']))

        preparer = self._screen(run, user=self.preparer)
        self.assertEqual(preparer['primary']['kind'], 'approvals')
        self.assertIsNone(preparer['primary']['method'])

    # ================================================================= T6
    def test_t6_an_approved_unpaid_run_is_paid_and_delivered_next(self):
        run = self._ready_draft()
        run.state = 'done'
        screen = self._screen(run)
        self.assertEqual(screen['header']['status']['key'], 'done')
        if callable(getattr(self.Run, 'action_pb_pay_deliver', None)):
            self.assertEqual(screen['primary']['kind'], 'paydeliver')
            self.assertEqual(screen['primary']['method'], 'action_pb_pay_deliver')
        else:
            self.assertEqual(screen['primary']['kind'], 'none')
        steps = screen['delivery']['steps']
        self.assertEqual([s['key'] for s in steps],
                         ['approved', 'bank_file', 'paid', 'sent', 'journals'])
        self.assertEqual(steps[0]['state'], 'done')
        self.assertEqual(steps[1]['state'], 'now')
        self.assertEqual(screen['delivery']['left'], 4)
        self.assertEqual([j['state'] for j in screen['journey']],
                         ['done', 'done', 'done', 'now', 'later'])
        self.assertEqual(screen['checks']['verdict'], 'done')
        self.assertTrue(all(r['flag']['text'] == 'Approved'
                            for r in screen['people']['rows']))

    # ================================================================= T7
    def test_t7_compared_with_the_run_before_on_the_same_scheme(self):
        august = self._run('PRS August 2026', '2026-08-01', '2026-08-31',
                           config=self.viet)
        self._slip(august, self.emp_a, net=9000000.0)
        self._slip(august, self.emp_b, net=5000000.0)
        september = self._run('PRS September 2026', config=self.viet)
        self._slip(september, self.emp_a, net=9000000.0)
        b = self._slip(september, self.emp_b, net=6000000.0)
        c = self._slip(september, self.emp_c, net=4000000.0)

        first = self._screen(august)
        self.assertIsNone(first['compare'])
        self.assertEqual(first['compare_none'],
                         'This is the first run on this scheme, so there is '
                         'nothing to compare with yet.')
        self.assertFalse(first['people']['changed_available'])

        screen = self._screen(september)
        compare = screen['compare']
        self.assertTrue(compare)
        self.assertIsNone(screen['compare_none'])
        self.assertEqual(compare['run_id'], august.id)
        self.assertEqual(compare['label'], 'August 2026')
        self.assertEqual(compare['people'], 2)
        self.assertEqual(compare['change_pct'], 35.7)   # 19m against 14m
        self.assertIn('35.7% more take-home than August 2026',
                      compare['sentence'])
        self.assertIn('2 people were paid then', compare['sentence'])
        flags = {r['slip_id']: r['flag'] for r in screen['people']['rows']}
        self.assertEqual(flags[b.id], {'kind': 'p', 'text': '+20% vs August'})
        self.assertEqual(flags[c.id], {'kind': 'p', 'text': 'New since August'})
        self.assertEqual(screen['people']['counts']['changed'], 2)
        self.assertTrue(screen['people']['changed_available'])

    def test_t7b_another_scheme_is_not_last_month(self):
        august = self._run('PRS August 2026', '2026-08-01', '2026-08-31')
        self._slip(august, self.emp_a)
        september = self._run('PRS September 2026', config=self.viet)
        self._slip(september, self.emp_a)
        screen = self._screen(september)
        self.assertIsNone(screen['compare'])
        self.assertTrue(screen['compare_none'])

    # ================================================================= T8
    def test_t8_a_name_naming_another_month_is_called_out(self):
        run = self._run('Payroll · October 2026')
        self._slip(run, self.emp_a)
        mismatch = self._screen(run)['date_mismatch']
        self.assertEqual(
            mismatch['text'],
            'The name says October 2026, but the dates are 1 – 30 Sep 2026. '
            'Check the dates before sending it.')
        run.name = 'Payroll · September 2026'
        self.assertIsNone(self._screen(run)['date_mismatch'])
        run.name = 'Monthly payroll'
        self.assertIsNone(self._screen(run)['date_mismatch'])

    def test_t8b_vietnamese_names_and_spanning_periods(self):
        run = self._run('Lương Tháng 10/2026')
        self.assertTrue(self.board._screen_date_mismatch(run))
        run.name = 'Bảng lương tháng 9 năm 2026'
        self.assertIsNone(self.board._screen_date_mismatch(run))
        # 16 Sep – 15 Oct: 15 days of each, so the later month names it
        spanning = self._run('Payroll Oct 2026', '2026-09-16', '2026-10-15')
        self.assertIsNone(self.board._screen_date_mismatch(spanning))
        self.assertEqual(self.board._screen_work_dates(
            spanning.date_start, spanning.date_end), '16 Sep – 15 Oct 2026')

    # ================================================================= T9
    def test_t9_money_carries_its_own_decimals(self):
        run = self._run(config=self.viet)
        self._slip(run, self.emp_a, net=15500000.0, ded=1250000.0)
        screen = self._screen(run)
        self.assertEqual(screen['header']['currency_name'], 'VND')
        self.assertEqual(screen['header']['decimals'], 0)
        for text in _strings(screen):
            self.assertNotIn('.00', text, text)
        self.assertIn('15.5 million', screen['money']['sentence'])

        usd = self._run('PRS USD September 2026')
        self._slip(usd, self.emp_b, net=1234.5, ded=100.0)
        usd.invalidate_recordset()
        if usd.pb_currency_id.name != 'USD':
            self.skipTest('this database does not keep its books in USD')
        screen = self._screen(usd)
        self.assertEqual(screen['header']['decimals'], 2)
        self.assertEqual(
            self.board._screen_money(1234.5, usd.pb_currency_id), '$1,234.50')

    def test_t9b_short_money_never_shows_trailing_zeros(self):
        vnd = self.viet.currency_id
        money = self.board._screen_money
        self.assertEqual(money(2000000000, vnd, short=True), '₫2 billion')
        self.assertEqual(money(1624000000, vnd, short=True), '₫1.62 billion')
        self.assertEqual(money(3500000, vnd, short=True), '₫3.5 million')
        self.assertEqual(money(1250000, vnd), '₫1,250,000')

    # ================================================================ T10
    def test_t10_payslip_money_adds_up_to_the_run_exactly(self):
        """C3: the people table and the run's figures are one source."""
        shapes = []
        plain = self._run('PRS shape plain')
        self._slip(plain, self.emp_a, net=8500.0, ded=1000.0)
        self._slip(plain, self.emp_b, net=7000.0, ded=900.0)
        shapes.append((plain, {'gross': 17400.0, 'deductions': 1900.0,
                               'net': 15500.0}))

        parts = self._run('PRS shape basic and allowances')
        slip = self._slip(parts, self.emp_a, lines=False)
        self._line(slip, 'BASIC', 'BASIC', 9000.0)
        self._line(slip, 'ALW', 'ALW', 500.0)
        shapes.append((parts, {'gross': 9500.0}))

        signed = self._run('PRS shape signed both ways')
        legacy = self._slip(signed, self.emp_a, lines=False)
        self._line(legacy, 'GROSS', 'GROSS', 10000.0)
        self._line(legacy, 'INSURANCE', 'DED', -900.0, role='deduction')
        self._line(legacy, 'ADVANCE', 'DED', 600.0, role='deduction')
        self._line(legacy, 'TAKEHOME', 'NET', 8500.0, role='net')
        refund = self._slip(signed, self.emp_b, lines=False)
        self._line(refund, 'GROSS', 'GROSS', 10000.0)
        self._line(refund, 'ANNUALREFUND', 'DED', -1000.0, role='deduction')
        self._line(refund, 'TAKEHOME', 'NET', 11000.0, role='net')
        self._line(refund, 'ERSI', 'COMP', 1575.0, role='employer_cost')
        shapes.append((signed, {'gross': 20000.0, 'deductions': 500.0,
                                'net': 19500.0, 'employer_cost': 1575.0}))

        folded = self._run('PRS shape folded detail')
        slip = self._slip(folded, self.emp_a, lines=False)
        self._line(slip, 'NET', 'NET', 8500.0)
        self._line(slip, 'DEDAGG', 'DED', 1000.0)
        self._line(slip, 'SIAMT', 'DED', 945.0, detail=True)
        shapes.append((folded, {'deductions': 1000.0, 'net': 8500.0}))

        runs = self.Run.browse([r.id for r, _ in shapes])
        runs.invalidate_recordset()
        per_slip = self.Run._pb_slip_totals(runs.ids)
        for run, expected in shapes:
            mine = [v for v in per_slip.values() if v['run_id'] == run.id]
            summed = {k: sum(v[k] for v in mine)
                      for k in ('gross', 'deductions', 'net', 'employer_cost')}
            self.assertEqual(summed['gross'], run.pb_total_gross, run.name)
            self.assertEqual(summed['deductions'], run.pb_total_deductions,
                             run.name)
            self.assertEqual(summed['net'], run.pb_total_net, run.name)
            self.assertEqual(summed['employer_cost'],
                             run.pb_total_employer_cost, run.name)
            for key, value in expected.items():
                self.assertEqual(summed[key], value, '%s %s' % (run.name, key))
            # and the screen's rows are those same figures
            rows = self._screen(run)['people']['rows']
            self.assertEqual(sum(r['net'] for r in rows), run.pb_total_net)

    # ================================================================ T11
    def test_t11_a_reader_without_access_is_refused(self):
        run = self._run()
        self._slip(run, self.emp_a)
        with self.assertRaises(AccessError):
            self._screen(run, user=self.outsider)

    def test_t11b_a_run_that_is_gone_says_so(self):
        with self.assertRaises(UserError):
            self.board.get_run_screen(0)

    # ================================================================ T12
    def test_t12_menus_offer_only_what_applies(self):
        run = self._ready_draft()
        draft = self._screen(run)
        keys = {a['key'] for a in draft['actions']['more']}
        self.assertIn('cleardraft', keys)
        self.assertIn('reject', keys)
        self.assertNotIn('email', keys)
        self.assertNotIn('redraft', keys)
        # one scheme, one part of the business: nothing to split
        self.assertNotIn('split', keys)
        clear = next(a for a in draft['actions']['more']
                     if a['key'] == 'cleardraft')
        self.assertTrue(clear['danger'])
        self.assertEqual(clear['confirm']['title'],
                         'Delete all 2 draft payslips?')
        if not callable(getattr(self.Run, 'action_open_source_atlas', None)):
            self.assertNotIn('atlas', keys)
        if not callable(getattr(self.Run, 'action_input_changes', None)):
            self.assertNotIn('changes', keys)
        downloads = {a['key'] for a in draft['actions']['downloads']}
        self.assertIn('xlsx', downloads)
        self.assertIn('pdf', downloads)
        if not callable(getattr(self.Run, 'action_open_payroll_report', None)):
            self.assertNotIn('report', downloads)

        run.state = 'done'
        done = self._screen(run)
        keys = {a['key'] for a in done['actions']['more']}
        for gone in ('cleardraft', 'split', 'recalc', 'reject'):
            self.assertNotIn(gone, keys)
        self.assertIn('redraft', keys)
        self.assertFalse(done['bulk']['delete'])
        self.assertFalse(done['bulk']['recalc'])
        self.assertFalse(done['settings_editable'])

    def test_t12b_split_is_offered_only_when_there_is_something_to_split(self):
        self._route_two_steps()
        other = self.env['hr.formula.config'].create({
            'name': 'PRS second scheme', 'code': 'PRSSECOND',
            'country_code': 'VN', 'company_id': self.company.id})
        run = self._run()
        self._slip(run, self.emp_a, formula_config_id=self.viet.id)
        self._slip(run, self.emp_b, formula_config_id=other.id)
        screen = self._screen(run)
        keys = {a['key'] for a in screen['actions']['more']}
        self.assertIn('split', keys)
        # two groups have two routes: the preview says why it cannot be sent
        route = next(i for i in screen['checks']['items'] if i['key'] == 'route')
        self.assertFalse(route['ok'])
        self.assertIn('Split into review groups', route['detail'])
        self.assertEqual(screen['checks']['verdict'], 'bad')

    def test_t12c_a_rejected_run_reads_as_rejected(self):
        run = self._ready_draft()
        run.with_context(pb_reject_note='Wrong month').action_payslip_run_cancel()
        screen = self._screen(run)
        self.assertEqual(screen['header']['status']['key'], 'rejected')
        self.assertEqual(screen['primary']['kind'], 'none')
        self.assertEqual(screen['checks']['verdict'], 'bad')
        self.assertEqual(screen['checks']['sub'], 'Wrong month')
        self.assertEqual(screen['journey'][2]['state'], 'warn')
        self.assertTrue(all(r['flag']['kind'] == 'muted'
                            for r in screen['people']['rows']))
        self.assertNotIn('reject', {a['key'] for a in screen['actions']['more']})
        self.assertEqual(screen['actions']['downloads'], [])

    # ================================================================ T13
    def test_t13_no_screen_string_names_the_platform(self):
        # A run made by the system account says "Prepared by <its name>". On
        # every live database biz_debrand renames that account to the brand
        # (res_config_settings: "OdooBot → brand bot"); this test database
        # has no biz_debrand, so the rename is mirrored here. What is under
        # test is that no sentence the screen BUILDS carries the vendor name.
        self.env.ref('base.partner_root').name = 'Payobook'
        run = self._ready_draft()
        payloads = [self._screen(run), self._screen(self._run('PRS empty'))]
        self.engine.with_user(self.preparer).submit(run.with_user(self.preparer))
        payloads.append(self._screen(run, user=self.hr))
        for payload in payloads:
            for text in _strings(payload):
                self.assertNotIn('odoo', text.lower(), text)

    def test_the_groups_cache_cannot_be_forged_from_a_client(self):
        """Only the screen's own cache object is honoured: a plain dict in
        the context (all a JSON client can send) is ignored, so nobody can
        steer which route a run is sent to."""
        run = self._run()
        slip = self._slip(run, self.emp_a)
        forged = {run.id: 'forged'}
        groups = run.with_context(pb_review_groups_memo=forged)._pb_review_groups()
        self.assertIsInstance(groups, list)
        self.assertEqual(groups[0]['slip_ids'], slip.ids)
        self.assertEqual(forged, {run.id: 'forged'})

    def test_overtime_is_read_off_the_codes_as_before(self):
        """`_pb_overtime_included` now reads the distinct codes in one
        grouped read; the answer is the one the line-by-line loop gave."""
        run = self._run()
        slip = self._slip(run, self.emp_a)
        self.assertFalse(run._pb_overtime_included())
        self._line(slip, 'TANG_CA', 'BASIC', 100.0)
        self.assertTrue(run._pb_overtime_included())
        other = self._run('PRS other')
        cancelled = self._slip(other, self.emp_b)
        self._line(cancelled, 'OT-150', 'BASIC', 100.0)
        cancelled.state = 'cancel'
        self.assertFalse(other._pb_overtime_included())
        self.assertFalse(self._run('PRS empty')._pb_overtime_included())

    # ======================================================= the bulk bar
    def test_bulk_refuses_payslips_from_another_run(self):
        run = self._run()
        mine = self._slip(run, self.emp_a)
        other = self._run('PRS other')
        theirs = self._slip(other, self.emp_b)
        with self.assertRaises(UserError):
            run.action_pb_slips('delete', [mine.id, theirs.id])
        self.assertTrue(mine.exists())
        self.assertTrue(theirs.exists())

    def test_bulk_deletes_picked_drafts_and_keeps_the_run(self):
        run = self._run()
        gone = self._slip(run, self.emp_a)
        kept = self._slip(run, self.emp_b)
        run.action_pb_slips('delete', [gone.id])
        self.assertFalse(gone.exists())
        self.assertTrue(kept.exists())
        self.assertTrue(run.exists())

    def test_bulk_never_deletes_an_approved_payslip(self):
        run = self._run()
        slip = self._slip(run, self.emp_a)
        slip.state = 'done'
        with self.assertRaises(UserError):
            run.action_pb_slips('delete', slip.ids)
        self.assertTrue(slip.exists())
