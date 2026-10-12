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
