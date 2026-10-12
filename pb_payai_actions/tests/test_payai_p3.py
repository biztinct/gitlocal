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

        def eligible(self_, statuses=None, employee_ids=None, formula_config_id=None,
                     date_start=None, date_end=None):
            out = sorted(ours)
            if employee_ids:
                out = [e for e in out if e in {int(x) for x in employee_ids}]
            return out
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

    def _submitted(self, name='Payai P3 Retail June'):
        run = self._run_with_slip(self.retail_end, name)
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
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        self.assertEqual((card['kind'], card['tier'], card['state']), ('plan', 'decide', 'planned'), card)
        self.assertEqual(card['title'], 'Approve %s' % request.title)
        self.assertIn('PayAI cannot undo it', card['subtitle'])
        self.assertIn('HR Manager check', card['subtitle'])
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['item']['value_label'], request.title)
        self.assertIn(slots['item']['origin'], ('said', 'assumed'))
        self.assertTrue(slots['figures']['value_label'].startswith('1 person · '),
                        slots['figures'])
        self.assertTrue(slots['figures']['value_label'].endswith(' net'))
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
        self.assertEqual(calls, ['payai-task-%s' % card['task_id']])
        self.assertEqual(again['state'], 'done')
        mine = self._decisions(request, self.approver)
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine.idempotency_key, 'payai-task-%s' % card['task_id'])
        self.assertEqual(mine.reason, 'Checked the totals')
        self.assertFalse(self._decisions(request) - mine)
        # The plan's promise is what happened: Finance release, Finance Payai.
        request.invalidate_recordset()
        live = request.step_ids.filtered(lambda s: s.status == 'active')
        self.assertEqual(live.title, 'Finance release')
        self.assertEqual(plan_next, '%s · %s' % (live.title, ', '.join(
            live.seat_ids.filtered(lambda s: s.status == 'open').acting_user_id.mapped('name'))))
        note = done['notes'][0]['text']
        self.assertIn('Approved as HR Manager check. It moves to Finance release (Finance Payai).',
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
        out = self._confirm(self.approver, card, word='APPROVE')
        self.assertNotEqual(out['task_id'], card['task_id'])
        self.assertIn('Things changed', json.dumps(out))
        self.assertEqual(out['kind'], 'refused', out)
        self.assertIn('Backup Payai', json.dumps(out))
        self.assertEqual(self._task(card).state, 'expired')
        self.assertFalse(self._decisions(request))

    # ================================================================ 6
    def test_06_independence_rule(self):
        # The preparer holds the first seat themselves and has no backup: the
        # engine keeps them on it and refuses their approval — so does PayAI.
        self._two_steps(first=[self.preparer])
        run, request = self._submitted()
        card, _s = self._plan_approve(self.preparer)
        self.assertEqual(card['kind'], 'refused', card)
        self.assertEqual(card['title'], 'Somebody else has to decide this')
        self.assertIn('You were part of preparing or sending this in, so you cannot also '
                      'approve it', json.dumps(card))
        self.assertNotIn('typed', [a['id'] for a in card['actions']])
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
        out = self._confirm(self.approver, card, word='REJECT')
        self.assertEqual(out['state'], 'done', out)
        request.invalidate_recordset()
        run.invalidate_recordset()
        self.assertEqual((request.state, request.return_note), ('rejected', 'it was paid twice'))
        self.assertEqual(run.state, 'cancel')
        self.assertIn('Rejected. The run and its payslips are cancelled', json.dumps(out))

    # ================================================================ 9
    def test_09_lock_revision_moved(self):
        self._lay([_people_step('both', [self.approver, self.joint], 'Joint check', 'joint'),
                   _people_step('finance', [self.finance], 'Finance release')])
        run, request = self._submitted()
        card, _s = self._plan_approve()
        self.assertIn('Joint Payai', next(s for s in card['slots'] if s['key'] == 'next')['value_label'])
        # The other half of the joint step decides meanwhile.
        self.env['biz.approval.engine'].with_user(self.joint).decide(request.id, 'both', 'approve')
        out = self._confirm(self.approver, card, word='APPROVE')
        self.assertIn('Things changed', json.dumps(out))
        self.assertNotEqual(out['task_id'], card['task_id'])
        self.assertEqual(out['state'], 'planned', out)
        self.assertFalse(self._decisions(request, self.approver))
        # The very last instant: the lock moves inside Do it. Nothing decided.
        Inbox = self.registry['pb.approval.inbox']
        real = Inbox.decide

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
        self.assertEqual([a['scenario'] for a in learn], ['sc_payslips'])
        # Run payroll and send for approval: the run walkthrough.
        card, _s = self._send(self.officer, 'Run August 2031 payroll for Payai Retail End-Month')
        _v, prep, _sum, res = self._drive(self.officer, card)
        self.assertEqual([a['scenario'] for a in res['actions'] if a['id'] == 'learn'],
                         ['sc_payrun'])
        self._run_with_slip(self.retail_mid, 'Payai P3 July', dates=('2031-07-01', '2031-07-31'))
        sub, _s = self._send(self.preparer, 'Send the July 2031 run for approval')
        self.assertEqual(sub['kind'], 'plan', sub)
        sent = self._conv(self.preparer).rpc_confirm_task(sub['task_id'], 'tap')['card']
        self.assertEqual([a['scenario'] for a in sent['actions'] if a['id'] == 'learn'],
                         ['sc_payrun'])
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

    # =============================================================== 12
    def test_12_no_back_door(self):
        from odoo.addons.pb_payai_actions.payai import gate
        self._two_steps()
        run, request = self._submitted()
        action = ACTIONS['approve_item']
        self.assertEqual(gate.allowed(self.env, self.approver, action), (True, ''))
        item = gate.screen_item(self.env, action)
        self.assertTrue(item, 'no Home screen on this database')
        Item = self.registry['pb.sidebar.item']
        real = Item.visibility_for

        def locked(self_, user):
            out = real(self_, user)
            out['items'][item.id] = 'locked'
            return out
        with patch.object(Item, 'visibility_for', locked):
            for text in ('Approve the June 2031 Payai Retail run',
                         'Reject the June 2031 Payai Retail run because it is wrong'):
                card, _s = self._send(self.approver, text)
                self.assertEqual(card['kind'], 'refused', card)
                self.assertIn('not switched on for you', json.dumps(card))
                self.assertEqual(self._task(card).error, 'screen_off')
        # A plan made while the screen was on is refused at Do it once it is not.
        card, _s = self._plan_approve()
        self.assertEqual(card['kind'], 'plan', card)
        with patch.object(Item, 'visibility_for', locked):
            out = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(out['kind'], 'refused', out)
        self.assertFalse(self._decisions(request))
