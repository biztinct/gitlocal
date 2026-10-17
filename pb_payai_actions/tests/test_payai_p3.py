# -*- coding: utf-8 -*-
"""PAYAI P3 — the live-walk fixes P3-W1…W6 (this file's first class) and the
Red tier (approve / send back / reject with a typed word) with the Learn
tie-in: numbered tests 1–13 of P3_HANDOVER.md.

Same rules as P1/P2: every gate is judged for an explicit user (PA12), no AI
provider is reached (the phrase table carries every sentence), fixtures use
2031 so a shared clone's own runs never collide (PA40).
"""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_payai_actions.payai import runner
from odoo.addons.pb_payai_actions.payai.registry import ACTIONS
from odoo.addons.pb_payai_actions.payai.runner import Ctx

DOORS = [
    {'id': 'payhub_run', 'label': 'Run Payroll', 'sublabel': 'Pay Run', 'group': '',
     'groups': [], 'kind': 'lens'},
    {'id': 'payhub_runs', 'label': 'Pay Runs', 'sublabel': 'Pay Run', 'group': '',
     'groups': [], 'kind': 'lens'},
    {'id': 'payhub_deliver', 'label': 'Pay & Deliver', 'sublabel': 'Pay Run', 'group': '',
     'groups': [], 'kind': 'lens'},
    {'id': 'homehub_approvals', 'label': 'Approvals', 'sublabel': 'Home', 'group': '',
     'groups': [], 'kind': 'lens'},
    {'id': 'peoplehub_records', 'label': 'Records', 'sublabel': 'People', 'group': '',
     'groups': [], 'kind': 'lens'},
]

JUNE = ('2031-06-01', '2031-06-30')


class _P3Case(TransactionCase):
    """Shared fixtures: two Retail schemes, three people the run covers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'payai_tier_look': True, 'payai_tier_prepare': True,
                           'payai_tier_decide': True, 'payai_voice_go_ahead': False})
        g = cls.env.ref
        cls.g_base = g('base.group_user').id
        cls.g_officer = g('pb_hr_payroll_base.group_payroll_base_officer').id
        cls.g_pay_user = g('om_hr_payroll.group_hr_payroll_user').id
        cls.g_pay_mgr = g('om_hr_payroll.group_hr_payroll_manager').id
        cls.officer = cls._user('P3 Officer', [cls.g_officer, cls.g_pay_user])
        cls.manager = cls._user('P3 Manager', [cls.g_pay_mgr, cls.g_pay_user])

        Config = cls.env.get('hr.formula.config')
        cls.has_schemes = Config is not None
        if cls.has_schemes:
            def cfg(name, code):
                return Config.create({'name': name, 'code': code, 'country_code': 'VN',
                                      'state': 'active', 'company_id': cls.company.id})
            cls.retail_end = cfg('Payai Retail End-Month', 'PAYAIRETEND')
            cls.retail_mid = cfg('Payai Retail Mid-Month', 'PAYAIRETMID')
        Emp = cls.env['hr.employee']
        cls.e1 = Emp.create({'name': 'Payai Linh Nguyen', 'company_id': cls.company.id})
        cls.e2 = Emp.create({'name': 'Payai Linh Tran', 'company_id': cls.company.id})
        cls.chi = Emp.create({'name': 'Vũ Khánh Chi', 'company_id': cls.company.id})
        for emp in (cls.e1, cls.e2, cls.chi):
            cls.env['hr.contract'].create({
                'name': '%s contract' % emp.name, 'employee_id': emp.id, 'wage': 1000.0,
                'state': 'open', 'date_start': '2020-01-01', 'company_id': cls.company.id})

    @classmethod
    def _user(cls, name, groups):
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': name, 'login': '%s@p3.test.invalid' % name.lower().replace(' ', '.'),
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.g_base] + list(groups))]})

    def setUp(self):
        super().setUp()
        if not self.has_schemes:
            self.skipTest('This database has no payroll schemes.')
        Wizard = self.registry['pb.payrun.wizard']
        ours = {self.e1.id, self.e2.id, self.chi.id}
        real = Wizard._eligible_employees
        self.real_eligible = real

        def eligible(self_, statuses=None, employee_ids=None, formula_config_id=None,
                     date_start=None, date_end=None):
            # The stub scopes the POPULATION to our three people only (the
            # status filter is part of that: a clone's feed knows nothing of
            # ours). A shortlist is the wizard's own filter (P3:test-13): the
            # real method answers it, narrowed to ours (a shared clone's
            # other people never leak in).
            if employee_ids:
                return [e for e in real(self_, statuses=None, employee_ids=employee_ids,
                                        formula_config_id=formula_config_id,
                                        date_start=date_start, date_end=date_end)
                        if e in ours]
            return sorted(ours)
        for p in (patch.object(Wizard, '_eligible_employees', eligible),
                  patch.object(Wizard, '_scheme_population',
                               lambda self_, config_id, base: (list(base), [])),
                  patch.object(self.registry['payroll.ai.config'], 'get_active_config',
                               lambda self_, *a, **k: self_.browse())):
            p.start()
            self.addCleanup(p.stop)

    # -------------------------------------------------------------- helpers
    def _session(self, user):
        Conv = self.env['payroll.ai.conversation'].with_user(user)
        session = Conv.create({'name': 'PayAI P3 test', 'user_id': user.id})
        Conv.rpc_register_doors(session.id, DOORS)
        return session

    def _send(self, user, text, session=None, resolve=None, voice=False):
        session = session or self._session(user)
        out = self.env['payroll.ai.conversation'].with_user(user).rpc_send_message(
            text, session.id, None, resolve=resolve, voice=voice)
        return out['card'], session

    def _pick(self, user, card, session, label):
        chip = next(c for c in card['chips'] if c['label'] == label)
        return self._send(user, label, session, resolve={
            'task_id': card['task_id'], 'slot': card['chip_slot'], 'value': chip['value']})[0]

    def _conv(self, user):
        return self.env['payroll.ai.conversation'].with_user(user)

    def _task(self, card):
        task = self.env['payai.task'].sudo().browse(card['task_id'])
        task.invalidate_recordset()
        return task

    def _run_with_slip(self, config, name, dates=JUNE, employee=None):
        run = self.env['hr.payslip.run'].create({
            'name': name, 'date_start': dates[0], 'date_end': dates[1],
            'pb_formula_config_id': config.id})
        emp = employee or self.e1
        self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': '%s slip' % name,
            'contract_id': self.env['hr.contract'].search(
                [('employee_id', '=', emp.id)], limit=1).id,
            'payslip_run_id': run.id, 'date_from': dates[0], 'date_to': dates[1],
            'company_id': self.company.id, 'formula_config_id': config.id})
        return run

    def _drive(self, user, card):
        """Do it, then the browser's run driver played as the person."""
        out = self._conv(user).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertEqual(out['state'], 'running', out)
        vals = out['drive']['vals']
        W = self.env['pb.payrun.wizard'].with_user(user)
        prep = W.prepare_run(dict(vals))
        self.assertFalse(prep.get('blocked') or prep.get('needs_confirmation'), prep)
        ids = prep.get('emp_ids') or []
        for i in range(0, len(ids), 40):
            W.compute_batch({'run_id': prep['run_id'], 'name': prep['name'],
                             'date_start': prep['date_start'], 'date_end': prep['date_end'],
                             'division': prep.get('division'), 'emp_ids': ids[i:i + 40]})
        summary = W.get_summary(prep['run_id'])
        res = self._conv(user).rpc_task_result(
            card['task_id'], prep['run_id'],
            {'stage': 'done', 'done': len(ids), 'total': len(ids), 'exceptions': 0})['card']
        return vals, prep, summary, res


@tagged('post_install', '-at_install', 'payai')
class TestPayaiP3Walk(_P3Case):
    """P3-W1…W6 — the findings of Fable's live walk of P2 (test 13)."""

    # ============================================================ P3-W1
    def test_w1_people_split_and_one_person_run(self):
        ctx = Ctx(self.env['payroll.ai.engine'].with_user(self.officer), {})
        texts = ACTIONS['run_payroll'].normalise_texts(
            ctx, {'period': 'December 2031',
                  'scheme': 'Retail End-Month for Vũ Khánh Chi only'})
        self.assertEqual((texts['scheme'], texts['people']),
                         ('Retail End-Month', 'Vũ Khánh Chi only'))
        # The month riding in the scheme and the people after it.
        texts = ACTIONS['run_payroll'].normalise_texts(
            ctx, {'scheme': 'Payai Retail End-Month for December 2031 for Vũ Khánh Chi only'})
        self.assertEqual((texts['scheme'], texts['people']),
                         ('Payai Retail End-Month', 'Vũ Khánh Chi only'))
        # "Retail only" is a scheme, never a person.
        texts = ACTIONS['run_payroll'].normalise_texts(ctx, {'scheme': 'Payai Retail End-Month only'})
        self.assertFalse(texts.get('people'))
        # The question never reads a name back as part of a scheme's name.
        cands = [{'label': 'Payai Retail End-Month'}, {'label': 'Payai Retail Mid-Month'}]
        self.assertEqual(runner._echo_word('Retail', cands), 'Retail')
        self.assertEqual(runner._echo_word('Retail End-Month for Vũ Khánh Chi only', cands), '')
        self.assertEqual(runner._echo_word('Vũ Khánh Chi', cands), '')

        # The walk's own sentence, end to end.
        card, session = self._send(
            self.officer, 'Run December 2031 payroll for Retail End-Month for Vũ Khánh Chi only')
        if card['kind'] == 'clarify':
            # Another "Retail End-Month" on this database: the question echoes
            # the scheme words only, never the person.
            self.assertNotIn('Chi', card['title'])
            card = self._pick(self.officer, card, session, 'Payai Retail End-Month')
        self.assertEqual(card['kind'], 'plan', card)
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['scheme']['value_label'], 'Payai Retail End-Month')
        self.assertIn(slots['scheme']['origin'], ('said', 'assumed', 'chose'))
        self.assertEqual(slots['people']['value_label'], 'Vũ Khánh Chi (1 of 3)')
        self.assertEqual(slots['people']['origin'], 'said')
        vals = json.loads(self._task(card).params_json)['vals']
        self.assertEqual(vals['employee_ids'], [self.chi.id])
        # The wizard's own shortlist (not the stub's) keeps exactly her.
        W = self.env['pb.payrun.wizard'].with_user(self.officer)
        self.assertEqual(self.real_eligible(W, employee_ids=[self.chi.id]), [self.chi.id])
        # Do it: exactly one payslip, for her.
        _v, prep, summary, res = self._drive(self.officer, card)
        self.assertEqual(summary['count'], 1, summary)
        run = self.env['hr.payslip.run'].browse(prep['run_id'])
        self.assertEqual(run.slip_ids.employee_id, self.chi)
        self.assertEqual(res['state'], 'done', res)

    def test_w1b_people_ambiguous_and_unknown(self):
        card, session = self._send(
            self.officer, 'Run June 2031 payroll for Payai Retail End-Month for Payai Linh only')
        self.assertEqual(card['kind'], 'clarify', card)
        self.assertEqual(card['title'], 'Which person do you mean?')
        self.assertEqual({c['label'] for c in card['chips']},
                         {'Payai Linh Nguyen', 'Payai Linh Tran'})
        card = self._pick(self.officer, card, session, 'Payai Linh Tran')
        self.assertEqual(card['kind'], 'plan', card)
        people = next(s for s in card['slots'] if s['key'] == 'people')
        self.assertEqual((people['value_label'], people['origin']),
                         ('Payai Linh Tran (1 of 3)', 'chose'))
        card, _s = self._send(
            self.officer, 'Run June 2031 payroll for Payai Retail End-Month for Zyxq Nobody only')
        self.assertNotEqual(card['kind'], 'plan', card)
        self.assertIn('could not find', json.dumps(card))

    # ============================================================ P3-W2
    def test_w2_no_article_before_a_month(self):
        self._run_with_slip(self.retail_end, 'Payai October', dates=('2031-10-01', '2031-10-31'))
        card, _s = self._send(self.officer, 'Run October 2031 payroll for Payai Retail End-Month')
        self.assertEqual(card['kind'], 'blocked', card)
        self.assertEqual(card['title'], 'Payai Retail End-Month already has a run for October 2031')
        self.assertNotIn('A October', json.dumps(card))

    # ============================================================ P3-W3
    def test_w3_unknown_pay_value_offers_the_closest(self):
        if 'pb.records.desk' not in self.env:
            self.skipTest('Records Desk not installed.')
        if 'pb.scheme.map' in self.env:
            p = patch.object(self.registry['pb.scheme.map'], 'resolve',
                             lambda self_, employee, cycle_type='any', on_date=None: {
                                 'config_id': self.retail_end.id, 'config_name': '',
                                 'rung': 'test', 'via': ''})
            p.start()
            self.addCleanup(p.stop)
        self.env['hr.formula.rule'].create({
            'config_id': self.retail_end.id, 'name': 'Payai Meal allowance',
            'code': 'PAYAIMEAL', 'column_type': 'input', 'sequence': 1,
            'default_value': 0.0, 'is_contract_component': True})
        hr_user = self._user('P3 Records', [self.env.ref('hr.group_hr_user').id,
                                            self.g_officer, self.g_pay_user])
        card, session = self._send(
            hr_user, 'Give Payai Linh Nguyen a Payai Lunch stipend of 500,000')
        self.assertEqual(card['kind'], 'clarify', card)
        self.assertLessEqual(len(card['chips']), 6)
        chip = next((c for c in card['chips'] if c['label'] == 'Payai Meal allowance'), None)
        self.assertTrue(chip, card['chips'])
        self.assertTrue(chip['sublabel'].startswith(('now ', 'not set')), chip)
        self.assertIn('could not find', json.dumps(card))
        ids = [a['id'] for a in card['actions']]
        self.assertIn('cancel', ids)
        self.assertIn('peoplehub_records', [a.get('door_id') for a in card['actions']])
        card = self._pick(hr_user, card, session, 'Payai Meal allowance')
        self.assertEqual(card['kind'], 'plan', card)

    # ============================================================ P3-W4
    def test_w4_send_payslips_offers_approved_runs_only(self):
        if 'pb.pay.delivery' not in self.env:
            self.skipTest('Pay & Deliver not installed.')
        self._run_with_slip(self.retail_end, 'Payai W4 Draft')
        done = self._run_with_slip(self.retail_mid, 'Payai W4 Done', employee=self.e2)
        self.env.cr.execute("UPDATE hr_payslip SET state = 'done' WHERE payslip_run_id = %s",
                            (done.id,))
        self.env.cr.execute("UPDATE hr_payslip_run SET state = 'done' WHERE id = %s", (done.id,))
        self.env.invalidate_all()
        card, _s = self._send(self.manager, 'Send the June 2031 payslips')
        self.assertNotIn('Payai W4 Draft', json.dumps(card))
        self.assertEqual(card['kind'], 'plan', card)
        run = next(s for s in card['slots'] if s['key'] == 'run')
        self.assertEqual(run['value_label'], 'Payai W4 Done')

    # ============================================================ P3-W5
    def test_w5_cancel_a_question(self):
        card, _s = self._send(self.officer, 'Run June 2031 payroll for Retail')
        self.assertEqual(card['kind'], 'clarify', card)
        self.assertIn('cancel', [a['id'] for a in card['actions']])
        self.assertEqual(self._task(card).state, 'clarify')
        out = self._conv(self.officer).rpc_cancel_task(card['task_id'])['card']
        self.assertEqual(out['kind'], 'cancelled', out)
        self.assertIn('Recorded: cancelled by P3 Officer', out['audit_line'])
        self.assertEqual(self._task(card).state, 'cancelled')
        # Cancelled twice: the same card, still cancelled.
        again = self._conv(self.officer).rpc_cancel_task(card['task_id'])['card']
        self.assertEqual(again['kind'], 'cancelled')

    # ============================================================ P3-W6
    def test_w6_expired_reads_plainly_in_the_audit(self):
        card, _s = self._send(self.officer, 'Run June 2031 payroll for Retail')
        task = self._task(card)
        task.write({'state': 'expired'})
        rows = self.env['pb.audit.console']._fetch_payai({}, 50)
        row = next(r for r in rows if r['key'] == 'payai-%s' % task.id)
        self.assertIn('Not answered in time', row['title'])
        self.assertNotIn('Expired', row['title'])


def _people_step(key, users, title, kind='approve'):
    return {'key': key, 'kind': kind, 'title': title,
            'who': {'mode': 'people', 'user_ids': [u.id for u in users],
                    'all': kind == 'joint'},
            'min_amount': 0, 'condition': None}


@tagged('post_install', '-at_install', 'payai')
class TestPayaiP3Red(_P3Case):
    """The Red tier — tests 1–12 of P3_HANDOVER.md. A two-step pay run route
    of our own (HR Manager check → Finance release) replaces the company's
    for the length of each test (rolled back)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        officer = [cls.g_officer, cls.g_pay_user]
        cls.preparer = cls._user('Prep Payai', [cls.g_pay_mgr, cls.g_pay_user, cls.g_officer])
        cls.approver = cls._user('Minh Payai', officer)
        cls.finance = cls._user('Finance Payai', officer)
        cls.joint = cls._user('Joint Payai', officer)
        cls.backup = cls._user('Backup Payai', officer)
        cls.lan = cls._user('Lan Payai', [cls.g_pay_mgr, cls.g_pay_user])
        cls.plain = cls._user('Bao Payai', [])
        cls.process = cls.env['biz.approval.process']._by_key('payrun')

    def setUp(self):
        super().setUp()
        if not self.process or 'pb.approval.inbox' not in self.env:
            self.skipTest('No pay run approval process here.')

    # -------------------------------------------------------------- route
    def _lay(self, steps):
        """Publish and bind a route for pay runs, company-wide, ending every
        other one (inside this test's transaction only)."""
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([('company_id', '=', self.company.id),
                        ('process_id', '=', self.process.id)]).write({'active': False})
        flow = self.env['biz.approval.workflow'].sudo().create({
            'name': 'Payai P3 route %s' % len(steps), 'company_id': self.company.id,
            'process_id': self.process.id, 'owner_user_id': self.env.uid})
        definition = {
            'schema_version': 1, 'steps': steps,
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {
                'independent': True, 'self_exception': {'enabled': False},
                'repeated': 'different', 'evidence': [],
                'due': {'kind': 'none', 'days': 1, 'day': 15, 'calendar_id': None},
                'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False}}}
        version = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': flow.id, 'revision': 1, 'status': 'draft', 'definition': definition})
        engine = self.env['biz.approval.engine'].with_context(approval_skip_coverage=True)
        checks = engine.validate_for_publish(version.id)
        self.assertFalse(checks['errors'], checks['errors'])
        engine.publish(version.id, version.draft_revision, None, 'P3 test',
                       [w['code'] for w in checks['warnings']])
        Binding.create({'company_id': self.company.id, 'process_id': self.process.id,
                        'scope_key': '', 'scope_label': self.company.name, 'kind_key': 'any',
                        'workflow_id': flow.id, 'mode': 'follow'})
        return flow

    def _two_steps(self, first=None):
        return self._lay([_people_step('hr_check', first or [self.approver], 'HR Manager check'),
                          _people_step('finance', [self.finance], 'Finance release')])

    def _net_line(self, run, amount):
        """A NET line on the run's payslip, so the frozen net is a real
        figure (P3:test-1), counted by the one pay-band rule."""
        category = self.env['hr.salary.rule.category'].search([('code', '=', 'NET')], limit=1)
        rule = self.env['hr.salary.rule'].search([], limit=1)
        if not category or not rule:
            self.skipTest('No NET category or salary rule on this database.')
        slip = run.slip_ids[:1]
        Line = self.env['hr.payslip.line']
        vals = {'slip_id': slip.id, 'name': 'NET', 'code': 'NET', 'amount': amount,
                'quantity': 1.0, 'rate': 100.0, 'employee_id': slip.employee_id.id,
                'contract_id': slip.contract_id.id, 'category_id': category.id,
                'salary_rule_id': rule.id}
        if 'pay_role' in Line._fields:
            vals['pay_role'] = 'net'
        Line.create(vals)
        run.invalidate_recordset()

    def _submitted(self, name='Payai P3 Retail June', net=None):
        run = self._run_with_slip(self.retail_end, name)
        if net is not None:
            self._net_line(run, net)
        out = self.env['biz.approval.engine'].with_user(self.preparer).submit(
            run.with_user(self.preparer))
        request = self.env['biz.approval.request'].browse(out['id'])
        self.assertEqual(request.state, 'pending', out)
        run.invalidate_recordset()
        self.assertEqual(run.state, 'approval_pending')
        return run, request

    def _decisions(self, request, user=None):
        dom = [('request_id', '=', request.id), ('action', 'in', ('approve', 'return', 'reject'))]
        if user:
            dom.append(('user_id', '=', user.id))
        return self.env['biz.approval.decision'].sudo().search(dom)

    def _confirm(self, user, card, how='typed', word=None, note=None):
        return self._conv(user).rpc_confirm_task(card['task_id'], how, word, note)['card']

    def _plan_approve(self, user=None, text='Approve the June 2031 Payai Retail run'):
        card, session = self._send(user or self.approver, text)
        return card, session

    # ================================================================ 1
    def test_01_plan_card_for_the_seat_holder(self):
        from odoo.addons.pb_payai_actions.payai.actions_green import money
        self._two_steps()
        run, request = self._submitted(net=1234567.0)
        card, _s = self._plan_approve()
        self.assertEqual((card['kind'], card['tier'], card['state']), ('plan', 'decide', 'planned'), card)
        self.assertEqual(card['title'], 'Approve %s' % request.title)
        self.assertIn('PayAI cannot undo it', card['subtitle'])
        self.assertIn('HR Manager check', card['subtitle'])
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['item']['value_label'], request.title)
        self.assertIn(slots['item']['origin'], ('said', 'assumed'))
        # The FROZEN net (request facts), which is the run band's net by the
        # one pay-band rule — and a real figure, not 0 (P3:test-1).
        frozen = request.facts['net_total']['value']
        self.assertEqual(frozen, run.slip_ids.pb_pay_totals()['net'])
        self.assertEqual(frozen, 1234567.0)
        symbol = request.currency_id.symbol or request.currency_id.name or ''
        self.assertEqual(slots['figures']['value_label'], '1 person · %s net' % money(frozen, symbol))
        self.assertEqual(slots['step']['value_label'], 'HR Manager check, 1 of 2')
        self.assertEqual(slots['next']['value_label'], 'Finance release · Finance Payai')
        typed = next(a for a in card['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['word'], 'APPROVE')
        self.assertIn('Type APPROVE to confirm', typed['hint'])
        self.assertTrue(typed.get('note'), 'approve carries an optional note field')
        ids = [a['id'] for a in card['actions']]
        self.assertNotIn('do', ids)          # no one-tap Do it on a Red card
        self.assertIn('cancel', ids)
        task = self._task(card)
        vals = json.loads(task.params_json)['vals']
        self.assertEqual((vals['request_id'], vals['step_key'], vals['lock_revision']),
                         (request.id, 'hr_check', request.lock_revision))
        self.assertEqual((task.tier, task.state), ('decide', 'planned'))
        self.assertFalse(self._decisions(request))

    # ================================================================ 2
    def test_02_not_the_approver(self):
        self._two_steps()
        run, request = self._submitted()
        for who in (self.preparer, self.lan):
            card, session = self._plan_approve(who)
            self.assertEqual(card['kind'], 'refused', card)
            self.assertEqual(card['title'], 'This is not waiting for you')
            text = json.dumps(card)
            self.assertIn('Minh Payai', text)
            self.assertIn('homehub_approvals', [a.get('door_id') for a in card['actions']])
            self.assertEqual([c['label'] for c in card['chips']], ['Remind Minh'])
        # Remind them: the engine's own reminder, once a day, nothing decided.
        Outbox = self.env['biz.approval.outbox'].sudo()
        before = Outbox.search_count([('request_id', '=', request.id), ('kind', '=', 'reminder')])
        chip = card['chips'][0]
        out = self._send(self.lan, chip['label'], session, resolve={
            'task_id': card['task_id'], 'slot': card['chip_slot'], 'value': chip['value'],
            'action': card['chip_action']})[0]
        self.assertTrue(out.get('transient'), out)
        self.assertEqual(out['title'], 'Reminded Minh Payai')
        rows = Outbox.search([('request_id', '=', request.id), ('kind', '=', 'reminder')])
        self.assertEqual(len(rows), before + 1)
        self.assertEqual(rows.sorted('id')[-1:].user_id, self.approver)
        event = self.env['biz.approval.event'].sudo().search(
            [('request_id', '=', request.id), ('kind', '=', 'reminded')])
        self.assertTrue(event and 'Lan Payai' in event[0].summary, event.mapped('summary'))
        again = self._send(self.lan, chip['label'], session, resolve={
            'task_id': card['task_id'], 'slot': card['chip_slot'], 'value': chip['value'],
            'action': card['chip_action']})[0]
        self.assertIn('already reminded', json.dumps(again))
        self.assertEqual(Outbox.search_count([('request_id', '=', request.id),
                                              ('kind', '=', 'reminder')]), before + 1)
        # A value the card did not offer is refused.
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self._send(self.lan, 'x', session, resolve={
                'task_id': card['task_id'], 'slot': 'item',
                'value': '%s:%s' % (request.id, self.lan.id), 'action': 'remind'})
        # Somebody who cannot see the request learns nothing about it.
        card, _s = self._plan_approve(self.plain)
        self.assertNotIn('Minh Payai', json.dumps(card))
        self.assertNotEqual(card.get('state'), 'planned')
        request.invalidate_recordset()
        self.assertEqual(request.state, 'pending')
        self.assertFalse(self._decisions(request))

    # ================================================================ 3
    def test_03_typed_word_mismatch_then_match_then_twice(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        out = self._confirm(self.approver, card, word='aprove')
        self.assertTrue(out.get('inline'), out)
        self.assertIn('Type APPROVE exactly', json.dumps(out))
        self.assertEqual(self._task(card).state, 'planned')
        self.assertFalse(self._decisions(request))
        plan_next = next(s for s in card['slots'] if s['key'] == 'next')['value_label']
        Inbox = self.registry['pb.approval.inbox']
        real = Inbox.decide
        calls = []

        def spy(self_, *args, **kwargs):
            calls.append(kwargs.get('idempotency_key'))
            return real(self_, *args, **kwargs)
        with patch.object(Inbox, 'decide', spy):
            done = self._confirm(self.approver, card, word='  approve ', note='Checked the totals')
            self.assertEqual(done['state'], 'done', done)
            again = self._confirm(self.approver, card, word='APPROVE')
        # FIX-1 final: the key is the task's, tied to the request, with a
        # secret part nobody else can guess (actions_red._decision_key).
        self.assertEqual(len(calls), 1, calls)
        self.assertTrue(calls[0].startswith('payai-task-%s-%s-' % (card['task_id'], request.id)),
                        calls)
        self.assertGreater(len(calls[0]), len('payai-task-%s-%s-' % (card['task_id'], request.id)) + 16)
        self.assertEqual(again['state'], 'done')
        mine = self._decisions(request, self.approver)
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine.idempotency_key, calls[0])
        self.assertEqual(mine.reason, 'Checked the totals')
        self.assertFalse(self._decisions(request) - mine)
        # The plan's promise is what happened: Finance release, Finance Payai.
        request.invalidate_recordset()
        live = request.step_ids.filtered(lambda s: s.status == 'active')
        self.assertEqual(live.title, 'Finance release')
        self.assertEqual(plan_next, '%s · %s' % (live.title, ', '.join(
            live.seat_ids.filtered(lambda s: s.status == 'open').acting_user_id.mapped('name'))))
        note = done['notes'][0]['text']
        self.assertIn('Approved at HR Manager check. It moves to Finance release (Finance Payai).',
                      note)
        self.assertIn('Nobody has been paid yet.', note)
        self.assertFalse((done.get('undo') or {}).get('can'))

    # ================================================================ 4
    def test_04_tap_voice_and_switch(self):
        self._two_steps()
        run, request = self._submitted()
        card, session = self._send(self.approver, 'Approve the June 2031 Payai Retail run',
                                   voice=True)
        self.assertIn('type the word APPROVE', card.get('speak') or '')
        self.assertIn('This one needs typing', json.dumps(card))
        for how in ('tap', 'voice'):
            out = self._confirm(self.approver, card, how=how, word='APPROVE')
            self.assertIn('This one needs typing', out['title'])
            self.assertEqual(self._task(card).state, 'planned')
        # A spoken "go ahead" (switch on, even) never counts for Red.
        self.company.payai_voice_go_ahead = True
        out, _s = self._send(self.approver, 'Go ahead', session, voice=True)
        self.assertIn('never counts', json.dumps(out))
        self.assertEqual(self._task(card).state, 'planned')
        # The company switch off: refused, even with the right word.
        self.company.payai_tier_decide = False
        out = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(out['kind'], 'refused', out)
        self.assertIn('Settings › PayAI can act', json.dumps(out, ensure_ascii=False))
        self.assertEqual(self._task(card).state, 'refused')
        card, _s = self._plan_approve()
        self.assertEqual(card['kind'], 'refused', card)
        self.assertFalse(self._decisions(request))

    # ================================================================ 5
    def test_05_seat_moved_between_plan_and_confirm(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        seat = step.seat_ids.filtered(lambda s: s.acting_user_id == self.approver)
        self.env['pb.approval.inbox'].move_it(request.id, seat.key, self.backup.id,
                                              'Away this week')
        # PayAI's own seat re-check refuses BEFORE the inbox is asked to
        # decide — not the engine's backstop (P3:test-5).
        Inbox = self.registry['pb.approval.inbox']
        real = Inbox.decide
        calls = []

        def spy(self_, *args, **kwargs):
            calls.append(args)
            return real(self_, *args, **kwargs)
        with patch.object(Inbox, 'decide', spy):
            out = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(calls, [])
        self.assertNotEqual(out['task_id'], card['task_id'])
        self.assertIn('Things changed', json.dumps(out))
        self.assertEqual(out['kind'], 'refused', out)
        self.assertIn('Backup Payai', json.dumps(out))
        # FIX-1 (P3 wf-10): changed under the plan reads 'replanned', not 'expired'.
        self.assertEqual(self._task(card).state, 'replanned')
        self.assertFalse(self._decisions(request))

    # ================================================================ 6
    def test_06_independence_rule(self):
        # The preparer holds the first seat themselves and has no backup: the
        # engine keeps them on it and refuses their approval — so does PayAI.
        self._two_steps(first=[self.preparer])
        run, request = self._submitted()
        Inbox = self.registry['pb.approval.inbox']
        real = Inbox.decide
        calls = []

        def spy(self_, *args, **kwargs):
            calls.append(kwargs.get('use_exception'))
            return real(self_, *args, **kwargs)
        # The drawer's own words for THIS request (P3:test-6, ux-7).
        conflict = self.env['pb.approval.inbox'].with_user(self.preparer).get_request(
            request.id)['conflict']
        self.assertEqual(conflict['text'], 'You sent this in.')
        with patch.object(Inbox, 'decide', spy):
            card, _s = self._plan_approve(self.preparer)
        self.assertEqual(card['kind'], 'refused', card)
        self.assertEqual(card['title'], 'Somebody else has to decide this')
        text = json.dumps(card)
        self.assertIn(conflict['text'], text)
        self.assertIn(conflict['note'], text)
        # Never the engine's copied sentence ("you were part of preparing").
        self.assertNotIn('You were part of preparing', text)
        self.assertNotIn('typed', [a['id'] for a in card['actions']])
        self.assertFalse(self._decisions(request))
        # An exception in force: still refused here, with PayAI's one line;
        # the inbox is never asked to use it.
        self.env['biz.approval.exception.grant'].sudo().create({
            'company_id': self.company.id, 'process_id': self.process.id,
            'user_ids': [(6, 0, [self.preparer.id])],
            'conflicts': ['maker', 'submitter', 'subject'], 'reason': 'Payai test grant'})
        conflict = self.env['pb.approval.inbox'].with_user(self.preparer).get_request(
            request.id)['conflict']
        self.assertTrue(conflict['grant_id'], conflict)
        with patch.object(Inbox, 'decide', spy):
            card, _s = self._plan_approve(self.preparer)
            self.assertEqual(card['kind'], 'refused', card)
            self.assertIn('PayAI never uses an exception', json.dumps(card))
            self.assertNotIn('typed', [a['id'] for a in card['actions']])
            self._confirm(self.preparer, card, word='APPROVE')
        self.assertEqual(calls, [])
        self.assertFalse(self._decisions(request))

    # ================================================================ 7
    def test_07_send_back_asks_for_the_reason(self):
        self._two_steps()
        run, request = self._submitted()
        card, session = self._send(self.approver, 'Send the June 2031 Payai Retail run back')
        self.assertEqual(card['kind'], 'clarify', card)
        self.assertEqual(card['title'], 'What should change? Type the reason.')
        self.assertEqual(self._task(card).state, 'clarify')
        # The reason is the person's words, even when they read like an order.
        reason = 'Approve the overtime first, then send it again'
        card2, session = self._send(self.approver, reason, session)
        self.assertEqual(card2['task_id'], card['task_id'])
        self.assertEqual(card2['kind'], 'plan', card2)
        slots = {s['key']: s for s in card2['slots']}
        self.assertEqual(slots['reason']['value_label'], reason)
        self.assertEqual(slots['next']['value_label'], 'Back to Prep Payai')
        typed = next(a for a in card2['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['word'], 'SEND BACK')
        self.assertFalse(typed.get('note'))
        out = self._confirm(self.approver, card2, word='send  back')
        self.assertEqual(out['state'], 'done', out)
        request.invalidate_recordset()
        run.invalidate_recordset()
        self.assertEqual((request.state, request.return_note), ('returned', reason))
        self.assertEqual(run.state, 'draft')
        self.assertIn('Sent back to Prep Payai with your reason. The run is a draft again.',
                      json.dumps(out))

    # ================================================================ 8
    def test_08_reject_with_reason(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._send(self.approver,
                              'Reject the June 2031 Payai Retail run because it was paid twice')
        self.assertEqual(card['kind'], 'plan', card)
        self.assertIn('every payslip in it is cancelled', json.dumps(card))
        typed = next(a for a in card['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['word'], 'TURN DOWN')
        self.assertIn('REJECT', typed['words'])      # the word P3 shipped still counts
        out = self._confirm(self.approver, card, word='REJECT')
        self.assertEqual(out['state'], 'done', out)
        request.invalidate_recordset()
        run.invalidate_recordset()
        self.assertEqual((request.state, request.return_note), ('rejected', 'it was paid twice'))
        self.assertEqual(run.state, 'cancel')
        # The inbox's own words for the act (P3:ux-4).
        self.assertEqual(out['title'], 'Turned down')
        self.assertIn('Turned down. The run and its payslips are cancelled', json.dumps(out))

    # ================================================================ 9
    def test_09_lock_revision_moved(self):
        self._lay([_people_step('both', [self.approver, self.joint], 'Joint check', 'joint'),
                   _people_step('finance', [self.finance], 'Finance release')])
        run, request = self._submitted()
        card, _s = self._plan_approve()
        self.assertIn('Joint Payai', next(s for s in card['slots'] if s['key'] == 'next')['value_label'])
        # The other half of the joint step decides meanwhile.
        self.env['biz.approval.engine'].with_user(self.joint).decide(request.id, 'both', 'approve')
        # The lock-revision fingerprint catches it at re-plan: the inbox is
        # never asked to decide (P3:test-9; part 2 is the engine backstop).
        Inbox = self.registry['pb.approval.inbox']
        real = Inbox.decide
        calls = []

        def spy(self_, *args, **kwargs):
            calls.append(args)
            return real(self_, *args, **kwargs)
        with patch.object(Inbox, 'decide', spy):
            out = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(calls, [])
        self.assertIn('Things changed', json.dumps(out))
        self.assertNotEqual(out['task_id'], card['task_id'])
        self.assertEqual(out['state'], 'planned', out)
        self.assertFalse(self._decisions(request, self.approver))
        # The very last instant: the lock moves inside Do it. Nothing decided.
        def racing(self_, request_id, *args, **kwargs):
            self_.env['biz.approval.request'].sudo().browse(request_id)._bump_lock()
            return real(self_, request_id, *args, **kwargs)
        with patch.object(Inbox, 'decide', racing):
            out2 = self._confirm(self.approver, out, word='APPROVE')
        self.assertIn('Things changed', json.dumps(out2))
        self.assertFalse(self._decisions(request, self.approver))
        # The fresh card is good: one decision, the request moves on.
        out3 = self._confirm(self.approver, out2, word='APPROVE')
        self.assertEqual(out3['state'], 'done', out3)
        self.assertEqual(len(self._decisions(request, self.approver)), 1)

    def test_09b_lock_revision_alone_moved(self):
        """P3:test-9 — the lock revision on its own is part of the plan's
        fingerprint. Only the lock moves between the plan and Do it: the
        step, the request's state and the open seats stay exactly as they
        were, so nothing but the lock revision can tell the plans apart.
        Dropping it from the fingerprint lets this confirm reach the inbox."""
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        self.assertEqual(card['kind'], 'plan', card)
        Inbox = self.env['pb.approval.inbox'].with_user(self.approver)

        def shape(pay):
            current = next((s for s in pay.get('steps') or [] if s.get('status') == 'active'),
                           {})
            seats = sorted(s.get('key') or '' for s in current.get('seats') or []
                           if s.get('status') == 'open')
            return pay.get('state'), current.get('key'), seats
        before = Inbox.get_request(request.id)
        request.sudo()._bump_lock()
        request.invalidate_recordset()
        after = Inbox.get_request(request.id)
        self.assertEqual(after['lock_revision'], before['lock_revision'] + 1)
        self.assertEqual(shape(after), shape(before))
        # The two fingerprints differ in the lock revision and nothing else.
        old_fp = json.loads(json.loads(self._task(card).params_json)['fingerprint'])
        Registry = self.registry['pb.approval.inbox']
        real = Registry.decide
        calls = []

        def spy(self_, *args, **kwargs):
            calls.append(args)
            return real(self_, *args, **kwargs)
        with patch.object(Registry, 'decide', spy):
            out = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(calls, [])
        self.assertIn('Things changed', json.dumps(out))
        self.assertNotEqual(out['task_id'], card['task_id'])
        self.assertEqual(out['state'], 'planned', out)
        self.assertEqual(self._task(card).state, 'replanned')
        self.assertFalse(self._decisions(request))
        new_fp = json.loads(json.loads(self._task(out).params_json)['fingerprint'])
        self.assertEqual(len(old_fp), len(new_fp))
        self.assertEqual([i for i, (a, b) in enumerate(zip(old_fp, new_fp)) if a != b], [1])
        # The fresh card carries the new lock: Do it on it decides once.
        out2 = self._confirm(self.approver, out, word='APPROVE')
        self.assertEqual(out2['state'], 'done', out2)
        self.assertEqual(len(self._decisions(request, self.approver)), 1)

    # =============================================================== 10
    def test_10_learn_doors_carry_real_scenario_keys(self):
        import os
        from odoo.modules.module import get_module_path
        path = os.path.join(get_module_path('pb_learn'), 'static', 'content', 'learn_content.json')
        with open(path, encoding='utf-8') as fh:
            scenarios = {s['key']: s for s in json.load(fh)['scenarios']}
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        done = self._confirm(self.approver, card, word='APPROVE')
        learn = [a for a in done['actions'] if a['id'] == 'learn']
        # The scenario, in watch mode (P3:test-10), named for what it
        # teaches: reading the run, not approving it (P3:ux-5).
        self.assertEqual([(a['scenario'], a['mode']) for a in learn], [('sc_payslips', 'watch')])
        self.assertEqual(learn[0]['label'], 'Learn to read a pay run')
        # Run payroll and send for approval: the run walkthrough.
        card, _s = self._send(self.officer, 'Run August 2031 payroll for Payai Retail End-Month')
        _v, prep, _sum, res = self._drive(self.officer, card)
        self.assertEqual([(a['scenario'], a['mode']) for a in res['actions'] if a['id'] == 'learn'],
                         [('sc_payrun', 'watch')])
        self._run_with_slip(self.retail_mid, 'Payai P3 July', dates=('2031-07-01', '2031-07-31'))
        sub, _s = self._send(self.preparer, 'Send the July 2031 run for approval')
        self.assertEqual(sub['kind'], 'plan', sub)
        sent = self._conv(self.preparer).rpc_confirm_task(sub['task_id'], 'tap')['card']
        self.assertEqual([(a['scenario'], a['mode']) for a in sent['actions']
                          if a['id'] == 'learn'], [('sc_payrun', 'watch')])
        for key in ('sc_payslips', 'sc_payrun'):
            self.assertIn(key, scenarios)
            self.assertIn('watch', scenarios[key]['modes'])
            self.assertFalse(scenarios[key].get('retired'))

    # =============================================================== 11
    def test_11_audit_under_the_persons_own_name(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        done = self._confirm(self.approver, card, word='APPROVE')
        task = self._task(card)
        self.assertEqual((task.state, task.confirm_kind), ('done', 'typed'))
        self.assertTrue(done['audit_line'].startswith(
            'Recorded: approved by Minh Payai via PayAI, typed confirmation, '), done['audit_line'])
        decision = self._decisions(request)
        self.assertEqual(decision.user_id, self.approver)
        self.assertEqual(decision.create_uid, self.approver)
        events = self.env['biz.approval.event'].sudo().search(
            [('request_id', '=', request.id), ('kind', '=', 'decided')])
        self.assertTrue(events and events[0].summary.startswith('Minh Payai approved'),
                        events.mapped('summary'))
        self.assertNotIn('PayAI', ' '.join(events.mapped('summary')))
        rows = self.env['pb.audit.console']._fetch_payai({}, 50)
        row = next(r for r in rows if r['key'] == 'payai-%s' % task.id)
        self.assertEqual((row.get('badge') or {}).get('label'), 'Typed confirmation')
        self.assertEqual(row['actor']['name'], 'Minh Payai')
        # An Amber row never carries the badge.
        amber, _s = self._send(self.officer, 'Run July 2031 payroll for Payai Retail End-Month')
        self._conv(self.officer).rpc_cancel_task(amber['task_id'])
        rows = self.env['pb.audit.console']._fetch_payai({}, 50)
        row = next(r for r in rows if r['key'] == 'payai-%s' % amber['task_id'])
        self.assertFalse(row.get('badge'))

    def test_11b_no_sudo_inside_an_action(self):
        """PA-R2, pinned (P3:test-11): `.sudo()` keeps the uid, so "the
        decision is under their own name" cannot tell a sudo call apart. No
        Action module calls sudo at all; bookkeeping lives in the runner."""
        import os
        import re
        from odoo.modules.module import get_module_path
        folder = os.path.join(get_module_path('pb_payai_actions'), 'payai')
        for name in sorted(os.listdir(folder)):
            if not (name.startswith('actions_') and name.endswith('.py')):
                continue
            with open(os.path.join(folder, name), encoding='utf-8') as fh:
                code = [line.split('#', 1)[0] for line in fh]
            hits = [n + 1 for n, line in enumerate(code) if re.search(r'\.sudo\(', line)]
            self.assertEqual(hits, [], '%s calls sudo() on lines %s' % (name, hits))

    def test_11c_approver_who_lost_read_on_the_run(self):
        """The seat holder can no longer read the pay run (a record rule):
        Do it is refused, nothing is decided, and it is not a "things
        changed" loop. A sudo() inside the Action would decide it."""
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        self.assertEqual(card['kind'], 'plan', card)
        self.env['ir.rule'].create({
            'name': 'Payai P3 hide one run', 'model_id': self.env['ir.model']._get_id(
                'hr.payslip.run'),
            'domain_force': "[('id', '!=', %d)]" % run.id})
        out = self._confirm(self.approver, card, word='APPROVE')
        self.assertNotEqual(out.get('state'), 'done', out)
        self.assertNotIn('Things changed', json.dumps(out))
        self.assertFalse(self._decisions(request))
        request.invalidate_recordset()
        self.assertEqual(request.state, 'pending')

    # =============================================================== 12
    def _lock_home(self, item, restricted=False):
        """FIX-1b (P3:sec-4): lock the screen the way the Access home does —
        a permission written on the menu entry (real data, no patch). The
        approver does not hold it; `restricted` shows it padlocked."""
        group = self.env['res.groups'].sudo().create({'name': 'Payai Home gate 2031'})
        item.sudo().write({'groups_id': [(6, 0, group.ids)], 'restricted': restricted})
        self.env.invalidate_all()
        return group

    def test_12_no_back_door(self):
        from odoo.addons.pb_payai_actions.payai import gate
        self._two_steps()
        run, request = self._submitted()
        action = ACTIONS['approve_item']
        self.assertEqual(gate.allowed(self.env, self.approver, action), (True, ''))
        item = gate.screen_item(self.env, action)
        self.assertTrue(item, 'no Home screen on this database')
        # A plan made while the screen was on ...
        card, _s = self._plan_approve()
        self.assertEqual(card['kind'], 'plan', card)
        # ... and then Home is locked for the approver in the Access home.
        # Nothing else is sent in between (a newer request would close the
        # plan as replaced): the screen gate itself refuses it at Do it.
        group = self._lock_home(item)
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'hidden')
        self.assertEqual(self._task(card).state, 'planned')
        out = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(out['kind'], 'refused', out)
        self.assertIn('not switched on for you', json.dumps(out))
        self.assertEqual((self._task(card).state, self._task(card).error),
                         ('refused', 'screen_off'))
        self.assertFalse(self._decisions(request))
        # New requests are refused too, before any plan is made.
        for text in ('Approve the June 2031 Payai Retail run',
                     'Reject the June 2031 Payai Retail run because it is wrong'):
            refused, _s = self._send(self.approver, text)
            self.assertEqual(refused['kind'], 'refused', refused)
            self.assertIn('not switched on for you', json.dumps(refused))
            self.assertEqual(self._task(refused).error, 'screen_off')
        self.assertFalse(self._decisions(request))
        # Lending the approver that permission (a lent role arrives as its
        # permissions) opens it again: the rule is the menu's own.
        self.approver.sudo().write({'group_ids': [(4, group.id)]})
        self.env.invalidate_all()
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'on')
