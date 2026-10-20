# -*- coding: utf-8 -*-
"""PAYAI P2 — the Amber tier: numbered tests 1–12 of P2_HANDOVER.md, plus the
P2-F1 door ranking and the scheme resolver unit tests.

The browser's part of "Run payroll" (the shared run driver) is played here by
the same server calls in the same order, AS THE PERSON: `prepare_run`, then
`compute_batch` in chunks of 40, then `get_summary` — exactly what
`run_driver.js` sends, with the `vals` the server handed out at Do it.

Every gate is judged for an explicit user (ledger PA12). No AI provider is
reached: the phrase table needs none.
"""
import json
import os
import re
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_payai_actions.payai import resolve
from odoo.addons.pb_payai_actions.payai.actions_green import money
from odoo.addons.pb_payai_actions.payai.registry import ACTIONS
from odoo.addons.pb_payai_actions.payai.runner import Ctx
from odoo.addons.pb_payroll_ai_insights.tests.common import payai_group_ids

DOORS = [
    {'id': 'payhub', 'label': 'Pay Run', 'sublabel': 'Payroll operations', 'group': '',
     'groups': ['om_hr_payroll.group_hr_payroll_user'], 'kind': 'mission'},
    {'id': 'payhub_run', 'label': 'Run Payroll', 'sublabel': 'Pay Run', 'group': '',
     'groups': ['om_hr_payroll.group_hr_payroll_user'], 'kind': 'lens'},
    {'id': 'payhub_runs', 'label': 'Pay Runs', 'sublabel': 'Pay Run', 'group': '',
     'groups': ['om_hr_payroll.group_hr_payroll_user'], 'kind': 'lens'},
    {'id': 'payhub_deliver', 'label': 'Pay & Deliver', 'sublabel': 'Pay Run', 'group': '',
     'groups': [], 'kind': 'lens'},
    {'id': 'payruns', 'label': 'Pay Runs', 'sublabel': 'Pay Run', 'group': 'Surfaces',
     'groups': [], 'kind': 'link'},
    {'id': 'learn.station.runs', 'label': 'Runs', 'sublabel': 'Lesson · 7 min · how to',
     'group': 'Learn', 'groups': [], 'kind': 'learn'},
    {'id': 'homehub_approvals', 'label': 'Approvals', 'sublabel': 'Home', 'group': '',
     'groups': [], 'kind': 'lens'},
    {'id': 'wf_approvals', 'label': 'Approvals', 'sublabel': 'Mission Control', 'group': '',
     'groups': [], 'kind': 'lens'},
    {'id': 'peoplehub_records', 'label': 'Records', 'sublabel': 'People', 'group': '',
     'groups': [], 'kind': 'lens'},
    {'id': 'cmphub_filings', 'label': 'Government filings', 'sublabel': 'Compliance',
     'group': '', 'groups': [], 'kind': 'lens'},
]

JUNE = ('2031-06-01', '2031-06-30')


@tagged('post_install', '-at_install', 'payai')
class TestPayaiP2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'payai_tier_look': True, 'payai_tier_prepare': True,
                           'payai_tier_decide': True, 'payai_voice_go_ahead': False})
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g = cls.env.ref
        base = g('base.group_user').id
        officer = g('pb_hr_payroll_base.group_payroll_base_officer').id
        pay_user = g('om_hr_payroll.group_hr_payroll_user').id
        pay_mgr = g('om_hr_payroll.group_hr_payroll_manager').id

        # Every fixture user talks to PayAI, so each holds it (a role since
        # 2026-10-20 — not inherited from being an internal user).
        payai = payai_group_ids(cls.env)

        def user(name, groups):
            return Users.create({
                'name': name, 'login': '%s@p2.test.invalid' % name.lower().replace(' ', '.'),
                'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [base] + payai + groups)]})
        cls.officer = user('P2 Officer', [officer, pay_user])
        cls.manager = user('P2 Manager', [pay_mgr, pay_user])
        cls.hr_user = user('P2 Records', [g('hr.group_hr_user').id, officer, pay_user])
        cls.filer_no_govt = user('P2 Filer Two', [officer, pay_mgr, pay_user])
        govt = g('pb_hr_govt.group_pb_hr_govt_user', raise_if_not_found=False)
        cls.filer = user('P2 Filer', [officer, pay_mgr, pay_user] + ([govt.id] if govt else []))

        Config = cls.env.get('hr.formula.config')
        cls.has_schemes = Config is not None
        if cls.has_schemes:
            def cfg(name, code):
                return Config.create({'name': name, 'code': code, 'country_code': 'VN',
                                      'state': 'active', 'company_id': cls.company.id})
            cls.retail_end = cfg('Payai Retail End-Month', 'PAYAIRETEND')
            cls.retail_mid = cfg('Payai Retail Mid-Month', 'PAYAIRETMID')
        cls.e1 = cls.env['hr.employee'].create({'name': 'Payai Linh Nguyen',
                                                'company_id': cls.company.id})
        cls.e2 = cls.env['hr.employee'].create({'name': 'Payai Linh Tran',
                                                'company_id': cls.company.id})
        for emp in (cls.e1, cls.e2):
            cls.env['hr.contract'].create({
                'name': '%s contract' % emp.name, 'employee_id': emp.id, 'wage': 1000.0,
                'state': 'open', 'date_start': '2020-01-01', 'company_id': cls.company.id})

    # -------------------------------------------------------------- helpers
    def setUp(self):
        super().setUp()
        if not self.has_schemes:
            self.skipTest('This database has no payroll schemes.')
        Wizard = self.registry['pb.payrun.wizard']
        ours = {self.e1.id, self.e2.id}

        def eligible(self_, statuses=None, employee_ids=None, formula_config_id=None,
                     date_start=None, date_end=None):
            out = sorted(ours)
            if employee_ids:
                out = [e for e in out if e in {int(x) for x in employee_ids}]
            return out
        # The test company's own people are many and not ours: the run covers
        # exactly the two fixtures, and the scheme map covers both of them.
        self._patches = [
            patch.object(Wizard, '_eligible_employees', eligible),
            patch.object(Wizard, '_scheme_population',
                         lambda self_, config_id, base: (list(base), [])),
            patch.object(self.registry['payroll.ai.config'], 'get_active_config',
                         lambda self_, *a, **k: self_.browse()),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _session(self, user):
        Conv = self.env['payroll.ai.conversation'].with_user(user)
        session = Conv.create({'name': 'PayAI P2 test', 'user_id': user.id})
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
        return self.env['payai.task'].sudo().browse(card['task_id'])

    def _plan_june(self, user, scheme_label='Payai Retail End-Month'):
        card, session = self._send(user, 'Run June 2031 payroll for Retail')
        if card['kind'] == 'clarify':
            card = self._pick(user, card, session, scheme_label)
        return card, session

    def _drive(self, user, vals):
        """The browser's run driver, played as the person: same calls, same order."""
        self.assertNotIn('force_clean', vals)
        W = self.env['pb.payrun.wizard'].with_user(user)
        prep = W.prepare_run(dict(vals))
        self.assertFalse(prep.get('blocked') or prep.get('needs_confirmation'), prep)
        exceptions = []
        ids = prep.get('emp_ids') or []
        for i in range(0, len(ids), 40):
            r = W.compute_batch({'run_id': prep['run_id'], 'name': prep['name'],
                                 'date_start': prep['date_start'], 'date_end': prep['date_end'],
                                 'division': prep.get('division'), 'emp_ids': ids[i:i + 40]})
            exceptions += r.get('exceptions') or []
            self._conv(user).rpc_task_progress(self._last_task, min(len(ids), i + 40), len(ids))
        summary = W.get_summary(prep['run_id'])
        return prep, summary, exceptions

    def _do_and_drive(self, user, card):
        out = self._conv(user).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertEqual(out['state'], 'running', out)
        self._last_task = card['task_id']
        prep, summary, exc = self._drive(user, out['drive']['vals'])
        self._last_exceptions = exc
        res = self._conv(user).rpc_task_result(
            card['task_id'], prep['run_id'],
            {'stage': 'done', 'done': len(prep['emp_ids']), 'total': len(prep['emp_ids']),
             'exceptions': len(exc)})['card']
        return out, prep, summary, res

    def _run_with_slip(self, config, name='Existing June', employee=None):
        run = self.env['hr.payslip.run'].create({
            'name': name, 'date_start': JUNE[0], 'date_end': JUNE[1],
            'pb_formula_config_id': config.id})
        emp = employee or self.e1
        self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': '%s slip' % name,
            'contract_id': self.env['hr.contract'].search(
                [('employee_id', '=', emp.id)], limit=1).id,
            'payslip_run_id': run.id, 'date_from': JUNE[0], 'date_to': JUNE[1],
            'company_id': self.company.id, 'formula_config_id': config.id})
        return run

    # ============================================================= P2-F1
    def test_00_f1_door_ranking(self):
        card, s = self._send(self.officer, 'Open runs')
        self.assertEqual(card['kind'], 'done', card)
        self.assertEqual([a['door_id'] for a in card['actions'] if a['id'] == 'door'],
                         ['payhub_runs'])
        card, s = self._send(self.officer, 'Open the runs lesson', s)
        self.assertEqual(card['kind'], 'done', card)
        self.assertEqual([a['door_id'] for a in card['actions'] if a['id'] == 'door'],
                         ['learn.station.runs'])
        card, s = self._send(self.officer, 'Open approvals', s)
        self.assertEqual(card['kind'], 'clarify', card)
        self.assertTrue(2 <= len(card['chips']) <= 6)
        self.assertEqual({c['value'] for c in card['chips']} & {'homehub_approvals', 'wf_approvals'},
                         {'homehub_approvals', 'wf_approvals'})

    def test_00b_scheme_resolver(self):
        ctx = Ctx(self.env['payroll.ai.engine'].with_user(self.officer), {})
        r = resolve.resolve_scheme(ctx, 'Retail')
        self.assertEqual(r['status'], 'ambiguous', r)
        self.assertTrue({self.retail_end.id, self.retail_mid.id}
                        <= {c['value'] for c in r['candidates']})
        r = resolve.resolve_scheme(ctx, 'Payai Retail End-Month')
        self.assertEqual((r['status'], r['value']), ('resolved', self.retail_end.id), r)
        self.assertEqual(r['origin'], 'said')
        r = resolve.resolve_scheme(ctx, 'Zzmarketingzz')
        self.assertEqual(r['status'], 'missing', r)
        # The note names the schemes the person can run (the first six, in the
        # wizard's own order — a clone with many schemes may list others first).
        self.assertIn('The schemes you can run are', r['note'])
        self.assertEqual(resolve.parse_amount('500,000'), 500000.0)
        self.assertEqual(resolve.parse_amount('1.5m'), 1500000.0)

    # ================================================================ 1
    def test_01_run_payroll_plan(self):
        card, session = self._send(self.officer, 'Run June 2031 payroll for Retail')
        self.assertEqual(card['kind'], 'clarify', card)
        self.assertEqual(card['title'], 'Which Retail scheme do you mean?')
        labels = {c['label'] for c in card['chips']}
        self.assertTrue({'Payai Retail End-Month', 'Payai Retail Mid-Month'} <= labels, labels)
        self.assertLessEqual(len(card['chips']), 6)
        card = self._pick(self.officer, card, session, 'Payai Retail End-Month')
        self.assertEqual(card['kind'], 'plan', card)
        self.assertEqual(card['state'], 'planned')
        origins = {s['key']: s['origin'] for s in card['slots']}
        self.assertEqual(origins['period'], 'said')
        self.assertEqual(origins['scheme'], 'chose')
        self.assertEqual(origins['company'], 'default')
        self.assertEqual(origins['people'], 'default')
        self.assertIn('do', [a['id'] for a in card['actions']])
        self.assertIn('prefill', [a['id'] for a in card['actions']])
        preview = self.env['pb.payrun.wizard'].with_user(self.officer).scheme_preview(
            {'formula_config_id': self.retail_end.id, 'date_start': JUNE[0],
             'date_end': JUNE[1]})
        people = next(s for s in card['slots'] if s['key'] == 'people')['value_label']
        self.assertIn('{:,}'.format(preview['covered']), people)
        task = self._task(card)
        self.assertEqual(task.state, 'planned')
        self.assertEqual(json.loads(task.params_json)['vals']['formula_config_id'],
                         self.retail_end.id)
        # A unique name: no question at all.
        card, _s = self._send(self.officer, 'Run June 2031 payroll for Payai Retail End-Month')
        self.assertEqual(card['kind'], 'plan', card)
        self.assertEqual({s['key']: s['origin'] for s in card['slots']}['scheme'], 'said')
        # One covered, one not: both counts on the card, exactly as the
        # wizard's scheme card counts them.
        Wizard = self.registry['pb.payrun.wizard']
        with patch.object(Wizard, '_scheme_population',
                          lambda self_, config_id, base: (list(base)[:1], list(base)[1:])):
            preview = self.env['pb.payrun.wizard'].with_user(self.officer).scheme_preview(
                {'formula_config_id': self.retail_end.id, 'date_start': JUNE[0],
                 'date_end': JUNE[1]})
            card, _s = self._send(self.officer,
                                  'Run June 2031 payroll for Payai Retail End-Month')
        self.assertEqual((preview['covered'], preview['not_covered']), (1, 1), preview)
        self.assertEqual(card['kind'], 'plan', card)
        people = next(s for s in card['slots'] if s['key'] == 'people')['value_label']
        self.assertEqual(people, 'All 1 covered by this scheme')
        notes = [n['text'] for n in card['notes']]
        self.assertIn('1 person in this company is not covered by this scheme and stays '
                      'out of this run.', notes)

    # ================================================================ 2
    def test_02_existing_run_blocked_and_never_force_clean(self):
        self._run_with_slip(self.retail_end)
        card, _s = self._plan_june(self.officer)
        self.assertEqual(card['kind'], 'blocked', card)
        # P3-W2: never "A October 2026 run …" — the scheme leads.
        self.assertEqual(card['title'], 'Payai Retail End-Month already has a run for June 2031')
        doors = [a for a in card['actions'] if a['id'] == 'door']
        self.assertTrue(doors and doors[0]['door_id'] == 'payhub_runs')
        self.assertNotIn('force_clean', json.dumps(card))
        # No payload PayAI hands the browser carries it, and the chat never
        # sends it: the driver call site and the chat patch never name it.
        card, _s = self._plan_june(self.officer, 'Payai Retail Mid-Month')
        task = self._task(card)
        self.assertNotIn('force_clean', task.params_json)
        out = self._conv(self.officer).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertNotIn('force_clean', json.dumps(out))
        self.assertNotIn('force_clean', out['drive']['vals'])
        # Nowhere in this module's code but these tests: the server half, the
        # models and every script the browser loads.
        root = get_module_path('pb_payai_actions')
        hits = []
        for sub in ('payai', 'models', os.path.join('static', 'src', 'js')):
            for dirpath, _dirs, files in os.walk(os.path.join(root, sub)):
                for name in files:
                    if not name.endswith(('.py', '.js', '.xml')):
                        continue
                    path = os.path.join(dirpath, name)
                    with open(path, encoding='utf-8') as fh:
                        if 'force_clean' in fh.read():
                            hits.append(os.path.relpath(path, root))
        self.assertEqual(hits, [])

    # ================================================================ 3
    def test_03_do_it_drives_and_closes(self):
        card, _s = self._plan_june(self.officer)
        out, prep, summary, res = self._do_and_drive(self.officer, card)
        task = self._task(card)
        self.assertEqual(task.state, 'done', res)
        self.assertEqual(task.confirm_kind, 'tap')
        self.assertEqual(json.loads(task.result_json)['ref']['run_id'], prep['run_id'])
        tiles = {t['label']: t['value'] for t in res['result']}
        self.assertEqual(tiles['payslips in draft'], '{:,}'.format(summary['count']))
        extra = json.loads(task.params_json).get('extra') or {}
        self.assertEqual(tiles['net to pay'],
                         money(summary.get('total_net'), extra.get('currency') or ''))
        self.assertEqual(tiles['need a look'], '{:,}'.format(
            int(summary.get('flagged') or 0) + len(self._last_exceptions)))
        ids = [a['id'] for a in res['actions']]
        self.assertTrue({'door', 'followup', 'learn'} <= set(ids), ids)
        run = self.env['hr.payslip.run'].browse(prep['run_id'])
        self.assertEqual(run.pb_formula_config_id, self.retail_end)
        self.assertEqual(run.pb_prepared_via, 'payai')

    def test_03b_one_driver_for_screen_and_card(self):
        # The server half above plays the driver; this pins that the browser's
        # driver really sends those calls, in that order, by 40 — and that the
        # wizard runs payroll only through it.
        root = get_module_path('pb_payrun_wizard')
        js = os.path.join(root, 'static', 'src', 'js')
        with open(os.path.join(js, 'run_driver.js'), encoding='utf-8') as fh:
            driver = fh.read()
        self.assertIn('export const CHUNK = 40;', driver)
        self.assertIn('i += CHUNK', driver)
        calls = re.findall(r'"pb\.payrun\.wizard",\s*"(\w+)"', driver)
        self.assertEqual(calls, ['sync_plan', 'sync_step', 'prepare_run', 'attach_spreadsheet',
                                 'discard_empty_run', 'compute_batch', 'get_summary'])
        self.assertNotIn('force_clean:', driver)
        with open(os.path.join(js, 'payrun_wizard.js'), encoding='utf-8') as fh:
            wizard = fh.read()
        self.assertRegex(wizard, r'import \{[^}]*\brunPayroll\b[^}]*\} from '
                                 r'"@pb_payrun_wizard/js/run_driver"')
        self.assertIn('runPayroll(this.orm', wizard)
        for name in ('compute_batch', 'prepare_run'):
            self.assertNotRegex(wizard, r'["\']%s["\']' % name)

    # ================================================================ 4
    def test_04_undo(self):
        # A manager may delete a draft run: Undo deletes it.
        card, _s = self._plan_june(self.manager)
        _o, prep, _sum, res = self._do_and_drive(self.manager, card)
        self.assertTrue(res['undo']['can'], res['undo'])
        out = self._conv(self.manager).rpc_task_undo(card['task_id'])['card']
        self.assertEqual(out['state'], 'undone', out)
        self.assertFalse(self.env['hr.payslip.run'].browse(prep['run_id']).exists())
        self.assertEqual(self._task(card).state, 'undone')
        # An officer may not: no Undo button, and the sentence says who can.
        card, _s = self._plan_june(self.officer, 'Payai Retail Mid-Month')
        _o, prep, _sum, res = self._do_and_drive(self.officer, card)
        self.assertFalse(res['undo']['can'])
        self.assertIn('Ask a payroll manager', res['undo']['note'])
        self.assertTrue(self.env['hr.payslip.run'].browse(prep['run_id']).exists())
        # After ten minutes: "too late".
        self.env['hr.payslip.run'].browse(prep['run_id']).sudo().unlink()
        card, _s = self._plan_june(self.manager)
        _o, prep, _sum, res = self._do_and_drive(self.manager, card)
        self._task(card).write({'undo_until': fields.Datetime.now() - timedelta(minutes=1)})
        out = self._conv(self.manager).rpc_task_undo(card['task_id'])['card']
        self.assertIn('Too late', out['title'])
        self.assertTrue(self.env['hr.payslip.run'].browse(prep['run_id']).exists())

    # ================================================================ 5
    def test_05_revalidated_at_do_it(self):
        card, _s = self._plan_june(self.officer)
        before = self.env['hr.payslip.run'].search_count([])
        self._run_with_slip(self.retail_end, name='Made meanwhile')
        out = self._conv(self.officer).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertNotEqual(out['task_id'], card['task_id'])
        self.assertIn('Things changed', json.dumps(out))
        self.assertEqual(out['kind'], 'blocked', out)
        self.assertNotIn('drive', out)
        # FIX-1 (P3 wf-10): changed under the plan reads 'replanned', not 'expired'.
        self.assertEqual(self._task(card).state, 'replanned')
        self.assertEqual(self.env['hr.payslip.run'].search_count([]), before + 1)
        # An expired plan is never acted on.
        card, _s = self._plan_june(self.officer, 'Payai Retail Mid-Month')
        self._task(card).write({'expires_at': fields.Datetime.now() - timedelta(minutes=1)})
        out = self._conv(self.officer).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertIn('expired', out['title'])
        # Somebody else cannot press another person's Do it.
        card, _s = self._plan_june(self.officer, 'Payai Retail Mid-Month')
        with self.assertRaises(AccessError):
            self._conv(self.manager).rpc_confirm_task(card['task_id'], 'tap')

    def test_05b_progress_and_result_need_your_own_go_ahead(self):
        Run = self.env['hr.payslip.run']
        card, _s = self._plan_june(self.officer)
        before = Run.search_count([])
        # A plan nobody said yes to: no progress, no result, nothing made.
        with self.assertRaises(AccessError):
            self._conv(self.officer).rpc_task_progress(card['task_id'], 1, 2)
        with self.assertRaises(AccessError):
            self._conv(self.officer).rpc_task_result(
                card['task_id'], 0, {'stage': 'done', 'done': 2, 'total': 2})
        task = self._task(card)
        task.invalidate_recordset()
        self.assertEqual(task.state, 'planned')
        self.assertFalse(task.confirmed_at)
        self.assertEqual(Run.search_count([]), before)
        # Confirmed by its owner: still nobody else's to report on.
        out = self._conv(self.officer).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertEqual(out['state'], 'running', out)
        with self.assertRaises(AccessError):
            self._conv(self.manager).rpc_task_result(
                card['task_id'], 0, {'stage': 'done', 'done': 2, 'total': 2})
        with self.assertRaises(AccessError):
            self._conv(self.manager).rpc_task_progress(card['task_id'], 1, 2)
        task.invalidate_recordset()
        self.assertEqual(task.state, 'confirmed')
        self.assertFalse(task.result_json)

    def _confirmed_june(self, scheme_label='Payai Retail End-Month'):
        card, _s = self._plan_june(self.officer, scheme_label)
        self.assertEqual(card['kind'], 'plan', card)
        out = self._conv(self.officer).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertEqual(out['state'], 'running', out)
        return card, out['drive']['vals']

    def _assert_not_taken(self, card, run):
        res = self._conv(self.officer).rpc_task_result(
            card['task_id'], run.id, {'stage': 'done', 'done': 2, 'total': 2})['card']
        self.assertEqual(res['state'], 'failed', res)
        self.assertNotEqual(res['title'], 'Run prepared: %s' % run.name)
        run.invalidate_recordset()
        self.assertFalse(run.pb_prepared_via)
        task = self._task(card)
        task.invalidate_recordset()
        self.assertEqual(task.state, 'failed')
        ref = json.loads(task.result_json or '{}').get('ref') or {}
        self.assertFalse(ref.get('run_id'), ref)
        self.assertNotIn('"run_id": %s' % run.id, task.result_json or '')

    def test_05c_result_takes_only_the_run_this_task_made(self):
        Run = self.env['hr.payslip.run']
        # A run for the same month and scheme that somebody ELSE made after
        # Do it: the browser cannot hand it over as this task's run (PA-R3).
        card, vals = self._confirmed_june()
        foreign = Run.with_user(self.manager).sudo().create({
            'name': 'Payai Made By Hand', 'date_start': vals['date_start'],
            'date_end': vals['date_end'],
            'pb_formula_config_id': vals['formula_config_id']})
        self.assertEqual(foreign.create_uid, self.manager)
        self._assert_not_taken(card, foreign)
        # The person's OWN run, but made before they pressed Do it: refused too.
        card, vals = self._confirmed_june()
        task = self._task(card)
        older = Run.with_user(self.officer).sudo().create({
            'name': 'Payai Made Earlier', 'date_start': vals['date_start'],
            'date_end': vals['date_end'],
            'pb_formula_config_id': vals['formula_config_id']})
        self.assertEqual(older.create_uid, self.officer)
        self.env.cr.execute('UPDATE hr_payslip_run SET create_date = %s WHERE id = %s',
                            (task.confirmed_at - timedelta(hours=1), older.id))
        older.invalidate_recordset()
        self._assert_not_taken(card, older)

    # ================================================================ 6
    def test_06_submit_run(self):
        # Two schemes in one run: the run's own refusal, in its own words.
        mixed = self._run_with_slip(self.retail_end, name='Payai Mixed')
        self.env['hr.payslip'].create({
            'employee_id': self.e2.id, 'name': 'mixed 2',
            'contract_id': self.env['hr.contract'].search(
                [('employee_id', '=', self.e2.id)], limit=1).id,
            'payslip_run_id': mixed.id, 'date_from': JUNE[0], 'date_to': JUNE[1],
            'company_id': self.company.id, 'formula_config_id': self.retail_mid.id})
        card, _s = self._send(self.manager, 'Send the Payai Mixed June 2031 run for approval')
        self.assertEqual(card['kind'], 'blocked', card)
        self.assertIn('different groups', json.dumps(card))
        mixed.slip_ids.unlink()
        mixed.unlink()

        run = self._run_with_slip(self.retail_end, name='Payai Submit')
        card, _s = self._send(self.manager, 'Send the Payai Submit June 2031 run for approval')
        if card['kind'] == 'blocked':
            self.skipTest('No pay run approval route here: %s' % json.dumps(card['notes']))
        self.assertEqual(card['kind'], 'plan', card)
        out = self._conv(self.manager).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertEqual(out['state'], 'done', out)
        ref = json.loads(self._task(card).result_json)['ref']
        self.assertTrue(ref.get('request_id'))
        request = self.env['biz.approval.request'].browse(ref['request_id'])
        self.assertEqual(request.idempotency_key, 'payai-task-%s' % card['task_id'])
        run.invalidate_recordset()
        if run.state != 'approval_pending':
            # The route approved it on the spot: nothing to withdraw, so the
            # card offers no Undo — and the withdraw path is not exercised.
            self.assertFalse((out.get('undo') or {}).get('can'), out)
            self.assertFalse(self._task(card).undo_until)
            self.skipTest('The pay run route here approves straight away (run is %s); '
                          'Withdraw not exercised.' % run.state)
        if run.state == 'approval_pending':
            self.assertTrue(out['undo']['can'])
            undone = self._conv(self.manager).rpc_task_undo(card['task_id'])['card']
            self.assertEqual(undone['state'], 'undone', undone)
            run.invalidate_recordset()
            self.assertEqual(run.state, 'draft')
            self.assertEqual(request.state, 'cancelled')

    # ================================================================ 7
    def _records_fixture(self):
        if 'pb.records.desk' not in self.env:
            self.skipTest('Records Desk not installed.')
        if 'pb.scheme.map' in self.env:
            # Whose scheme pays these two: ours (the template's map knows them not).
            p = patch.object(self.registry['pb.scheme.map'], 'resolve',
                             lambda self_, employee, cycle_type='any', on_date=None: {
                                 'config_id': self.retail_end.id, 'config_name': '',
                                 'rung': 'test', 'via': ''})
            p.start()
            self.addCleanup(p.stop)
        rule = self.env['hr.formula.rule'].create({
            'config_id': self.retail_end.id, 'name': 'Payai Meal allowance',
            'code': 'PAYAIMEAL', 'column_type': 'input', 'sequence': 1,
            'default_value': 0.0, 'is_contract_component': True})
        return rule

    def _plan_meal(self, session=None):
        card, session = self._send(
            self.hr_user, 'Give Payai Linh Nguyen a Payai Meal allowance of 500,000', session)
        return card, session

    def test_07_update_pay_data(self):
        self._records_fixture()
        Desk = self.env['pb.records.desk'].with_user(self.hr_user)
        seed = self.env['biz.approval.seed'].sudo()
        seed.set_no_approval_needed(self.company, 'records')
        # Two people called Linh → one question with chips.
        card, session = self._send(
            self.hr_user, 'Give Payai Linh a Payai Meal allowance of 500,000')
        self.assertEqual(card['kind'], 'clarify', card)
        self.assertEqual(len(card['chips']), 2)
        card, session = self._plan_meal(session)
        self.assertEqual(card['kind'], 'plan', card)
        # The plan says up front what the route will do; here no approval is
        # needed, so it must never promise an approver.
        plan_text = json.dumps(card)
        self.assertNotIn('This change needs approval', plan_text)
        task = self._task(card)
        vals = json.loads(task.params_json)['vals']
        preview = Desk.preview_changes(vals['config_id'], vals['changes'])
        item = preview['items'][0]
        shown = {s['key']: s['value_label'] for s in card['slots']}
        self.assertEqual(shown['today'], item['old_label'] or '(not set)')
        self.assertEqual(item['status'], 'ok')
        out = self._conv(self.hr_user).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertEqual(out['state'], 'done', out)
        ref = json.loads(self._task(card).result_json)['ref']
        self.assertTrue(ref['apply_id'])
        self.assertFalse(ref['pending'])
        # Undo puts it back.
        undone = self._conv(self.hr_user).rpc_task_undo(card['task_id'])['card']
        self.assertEqual(undone['state'], 'undone', undone)
        # A value somebody moved meanwhile: refused, the desk's own sentence.
        card, session = self._plan_meal(session)
        self._conv(self.hr_user).rpc_confirm_task(card['task_id'], 'tap')
        vals = json.loads(self._task(card).params_json)['vals']
        Desk.sudo().apply_changes(vals['config_id'], [dict(vals['changes'][0], value=777000)])
        refused = self._conv(self.hr_user).rpc_task_undo(card['task_id'])['card']
        self.assertIn('changed by somebody else', json.dumps(refused))
        # Refused means refused: the other person's 777,000 stays, nothing was
        # put back, and the task is still done with its undo window intact.
        task = self._task(card)
        task.invalidate_recordset()
        self.assertEqual(task.state, 'done')
        self.assertTrue(task.undo_until)
        live = Desk.preview_changes(vals['config_id'], [dict(vals['changes'][0], value=777000)])
        self.assertEqual(live['items'][0]['status'], 'same', live)

    def test_07b_update_pay_data_routed(self):
        self._records_fixture()
        approver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'P2 HR Lead', 'login': 'p2.hrlead@test.invalid',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_user').id]
                          + payai_group_ids(self.env))]})
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'hr_lead')], limit=1)
        if not role:
            self.skipTest('No HR lead role here.')
        Resp = self.env['biz.approval.responsibility'].sudo()
        held = Resp.search([('company_id', '=', self.company.id), ('role_id', '=', role.id),
                            ('scope_key', '=', '')], limit=1)
        if held:
            held.write({'user_id': approver.id, 'active': True})
        else:
            Resp.create({'company_id': self.company.id, 'role_id': role.id, 'scope_key': '',
                         'scope_label': self.company.name, 'user_id': approver.id,
                         'date_from': '2020-01-01'})
        self.env['pb.records.apply']._approval_seed_default(self.company)
        card, _s = self._plan_meal()
        plan_text = json.dumps(card)
        out = self._conv(self.hr_user).rpc_confirm_task(card['task_id'], 'tap')['card']
        ref = json.loads(self._task(card).result_json)['ref']
        if not ref['pending']:
            self.assertNotIn('This change needs approval', plan_text)
            self.skipTest('The records route here needs no approval.')
        # Routed: the plan never said it would be saved straight away.
        self.assertNotIn('need no approval', plan_text)
        self.assertIn('approval', json.dumps(out).lower())
        undone = self._conv(self.hr_user).rpc_task_undo(card['task_id'])['card']
        self.assertEqual(undone['state'], 'undone', undone)
        self.assertEqual(self.env['biz.approval.request'].browse(ref['request_id']).state,
                         'cancelled')

    # ================================================================ 8
    def test_08_send_payslips(self):
        if 'pb.pay.delivery' not in self.env:
            self.skipTest('Pay & Deliver not installed.')
        run = self._run_with_slip(self.retail_end, name='Payai Deliver')
        card, _s = self._send(self.manager, 'Send the Payai Deliver June 2031 payslips')
        # P3-W4: a draft is never offered — "No approved run for <month> yet"
        # with the Runs board door, and no chip naming the draft.
        self.assertEqual(card['kind'], 'blocked', card)
        self.assertIn('No approved run for June 2031 yet', json.dumps(card))
        self.assertFalse(card['chips'] and any('Payai Deliver' in c['label'] for c in card['chips']))
        self.assertIn('payhub_runs', [a.get('door_id') for a in card['actions']])
        self.env.cr.execute("UPDATE hr_payslip SET state = 'done' WHERE payslip_run_id = %s",
                            (run.id,))
        self.env.cr.execute("UPDATE hr_payslip_run SET state = 'done' WHERE id = %s", (run.id,))
        self.env.invalidate_all()
        Batch = self.registry['pb.payslip.delivery.batch']
        with patch.object(Batch, '_do_send', lambda self_, force_all=False: True):
            card, _s = self._send(self.manager, 'Send the Payai Deliver June 2031 payslips')
            self.assertEqual(card['kind'], 'plan', card)
            self.assertIn('cannot be undone', json.dumps(card))
            out = self._conv(self.manager).rpc_confirm_task(card['task_id'], 'tap')['card']
        if out.get('state') == 'failed':
            self.skipTest('No payslip send-out route here: %s' % json.dumps(out['notes']))
        self.assertEqual(out['state'], 'done', out)
        batch = self.env['pb.pay.delivery']._batch(run)
        self.assertTrue(batch and batch.approval_request_id, 'no routed request')
        self.assertFalse(out.get('undo'))

    # ================================================================ 9
    def test_09_filing_prepare(self):
        if 'pb.filing.flow' not in self.env:
            self.skipTest('Government filings not installed.')
        board = self.env['pb.filing.flow'].with_user(self.filer).start()
        if not board.get('is_covered') and 'VN' in (board.get('covered') or []):
            # The clone's company is not in a covered country (p0clone is US):
            # the test company files as Vietnam, inside this transaction only.
            self.company.country_id = self.env.ref('base.vn')
            board = self.env['pb.filing.flow'].with_user(self.filer).start()
        if not board.get('is_covered') or not board.get('filings'):
            self.skipTest('No covered filing country here.')
        Flow = self.registry['pb.filing.flow']
        done = {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'message': 'ok'}}
        first = board['filings'][0]

        def ask(who):
            card, session = self._send(who, 'Prepare the June 2031 %s filing' % first['label'])
            if card['kind'] == 'clarify':
                card = self._send(who, card['chips'][0]['label'], session, resolve={
                    'task_id': card['task_id'], 'slot': card['chip_slot'],
                    'value': card['chips'][0]['value']})[0]
            return card

        # PA-R1 method half: without the Government Reports permission the
        # filing's own form cannot be made, so the refusal comes at plan time
        # in plain words (no model name), never as a failed Do it.
        spec = self.env['pb.filing.flow']._adapter(board.get('country_code') or 'VN')
        if not self.env[spec['model']].with_user(self.filer_no_govt).has_access('create'):
            card = ask(self.filer_no_govt)
            self.assertNotEqual(card.get('state'), 'planned', card)
            self.assertIn('Government Reports permission', json.dumps(card))
            self.assertNotIn(spec['model'], json.dumps(card))
        pressed = []

        def press(self_, w, c, k):
            pressed.append(((c or '').upper(), k))
            return done
        with patch.object(Flow, '_press', press):
            card = ask(self.filer)
            self.assertEqual(card['kind'], 'plan', card)
            self.assertIn('Nothing is sent to the authority', json.dumps(card))
            out = self._conv(self.filer).rpc_confirm_task(card['task_id'], 'tap')['card']
        if out.get('state') == 'failed':
            self.skipTest('No filing route here: %s' % json.dumps(out['notes']))
        self.assertEqual(out['state'], 'done', out)
        ref = json.loads(self._task(card).result_json)['ref']
        self.assertTrue(ref.get('proposal_id'))
        self.assertTrue(self.env['pb.filing.proposal'].browse(ref['proposal_id']).exists())
        self.assertIn('cmphub_filings', [a.get('door_id') for a in out['actions']])
        task = self._task(card)
        vals = json.loads(task.params_json)['vals']
        if out['title'] == 'Waiting for approval':
            self.assertEqual(pressed, [])       # the approver produces it later
        else:
            # Produced once, for exactly the filing and country on the plan.
            self.assertEqual(pressed, [((vals['country'] or '').upper(), vals['filing_key'])])
            self.assertEqual(vals['filing_key'], first['key'])

    # =============================================================== 10
    def test_10_voice_go_ahead(self):
        card, session = self._plan_june(self.officer)
        task = self._task(card)
        # Switch off: the spoken go-ahead is a note, nothing happens.
        out, session = self._send(self.officer, 'Go ahead', session, voice=True)
        self.assertTrue(out.get('transient'), out)
        self.assertIn('switched off', json.dumps(out))
        self.assertEqual(task.state, 'planned')
        # Typed, it never counts.
        out, session = self._send(self.officer, 'yes, do it', session)
        self.assertIn('Typing it does not count', json.dumps(out))
        self.assertEqual(task.state, 'planned')
        # Switch on + Amber: it is the Do-it tap.
        self.company.payai_voice_go_ahead = True
        out, session = self._send(self.officer, 'Go ahead', session, voice=True)
        self.assertEqual(out['state'], 'running', out)
        self.assertTrue(out['drive']['vals'])
        task.invalidate_recordset()
        self.assertEqual(task.confirm_kind, 'voice')
        # The plan read back on the device when the ask was spoken.
        card, s2 = self._send(self.officer, 'Run June 2031 payroll for Payai Retail Mid-Month',
                              voice=True)
        self.assertIn('say go ahead', card.get('speak') or '')
        # Red: a spoken yes never counts.
        red = self.env['payai.task'].sudo().create({
            'user_id': self.officer.id, 'company_id': self.company.id,
            'session_id': s2.id, 'action_key': 'approve_item', 'tier': 'decide',
            'state': 'planned', 'expires_at': fields.Datetime.now() + timedelta(minutes=10)})
        out, _s = self._send(self.officer, 'Go ahead', s2, voice=True)
        self.assertIn('never counts', json.dumps(out))
        red.invalidate_recordset()
        self.assertEqual(red.state, 'planned')

    # =============================================================== 11
    def test_11_history_and_audit(self):
        card, _s = self._plan_june(self.officer)
        _o, prep, _sum, _res = self._do_and_drive(self.officer, card)
        run = self.env['hr.payslip.run'].browse(prep['run_id'])
        story = self.env['pb.payruns']._history(run, {}, {})
        self.assertIn('through PayAI', story[0][0])
        self.assertIn(self.officer.name, story[0][0])
        task = self._task(card)
        self.assertEqual(json.loads(task.result_json)['ref']['run_id'], run.id)
        rows = self.env['pb.audit.console']._fetch_payai({}, 50)
        row = next((r for r in rows if r['key'] == 'payai-%s' % task.id), None)
        self.assertTrue(row, [r['key'] for r in rows])
        self.assertIn('Run payroll', row['title'])
        self.assertEqual(row['actor']['name'], self.officer.name)
        # A run nobody asked PayAI for never claims to have come through it.
        by_hand = self._run_with_slip(self.retail_mid, name='Payai By Hand')
        self.assertFalse(by_hand.pb_prepared_via)
        story = self.env['pb.payruns']._history(by_hand, {}, {})
        self.assertNotIn('through PayAI', json.dumps(story, default=str))

    # =============================================================== 12
    def test_12_no_back_door(self):
        action = ACTIONS['run_payroll']
        from odoo.addons.pb_payai_actions.payai import gate
        self.assertEqual(gate.allowed(self.env, self.officer, action), (True, ''))
        item = gate.screen_item(self.env, action)
        Item = self.registry['pb.sidebar.item']
        real = Item.visibility_for

        def locked(self_, user):
            out = real(self_, user)
            out['items'][item.id] = 'locked'
            return out
        with patch.object(Item, 'visibility_for', locked):
            card, _s = self._send(self.officer, 'Run June 2031 payroll for Retail')
        self.assertEqual(card['kind'], 'refused', card)
        self.assertIn('not switched on for you', json.dumps(card))
        self.assertFalse(self.env['payai.task'].sudo().search(
            [('user_id', '=', self.officer.id), ('state', '=', 'planned')]))

        # The METHOD half: the screen reads 'on' for somebody who holds no
        # payroll right at all. Still refused, in the no-right words, with no
        # plan made. (Take method_ok out of gate.allowed() and this fails.)
        plain = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'P2 Plain', 'login': 'p2.plain@p2.test.invalid',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id]
                          + payai_group_ids(self.env))]})

        def on(self_, user):
            out = real(self_, user)
            out['items'][item.id] = 'on'
            return out
        with patch.object(Item, 'visibility_for', on):
            for key, text in (('run_payroll', 'Run June 2031 payroll for Retail'),
                              ('submit_run', 'Send the June 2031 run for approval')):
                self.assertEqual(gate.screen_state(self.env, plain, ACTIONS[key]), 'on')
                self.assertEqual(gate.allowed(self.env, plain, ACTIONS[key]),
                                 (False, 'no_right'))
                card, _s = self._send(plain, text)
                self.assertEqual(card['kind'], 'refused', card)
                self.assertIn('is for payroll staff', json.dumps(card))
                task = self._task(card)
                self.assertEqual((task.action_key, task.state, task.error),
                                 (key, 'refused', 'no_right'))
        self.assertFalse(self.env['payai.task'].sudo().search(
            [('user_id', '=', plain.id), ('state', 'in', ('planned', 'confirmed', 'running'))]))
