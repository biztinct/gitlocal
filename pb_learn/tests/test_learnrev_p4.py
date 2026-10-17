# -*- coding: utf-8 -*-
"""LEARNREV P4 — T3: checked Try, country, the replica gate, source pins.

  (a) `learn.scenario.check` — sc_treatment on the demo fixture: not ok →
      the person sets a pay role and saves → ok, naming the row and the role;
      another user's change does not count; recompute agrees with Right now;
      sc_payrun reuses the live predicate; sc_records counts only this
      user's bank change on a demo employee. Outside a demo session: refused,
      and no step is offered as checked.
  (b) `bootstrap.country` follows the active company; the Guide carries the
      open scheme's country.
  (c) the replica-truth gate: 0 errors on every manifest, and it FAILS on a
      synthetic drift (a copy saying a retired header, a column left out).
  (d) source pins: `.pct-empty` is a refusal box; Watch keeps the drawer;
      the spotlight no longer touches the Guide's `lrn-docked`; the panel
      player's node suite runs (tests/js/lesson_panel.test.mjs).
"""
import os
import re
import shutil
import subprocess

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from . import guide_truth as gt
from .test_guide_truth import read_rel

DEMO_COMPANY = 'Payobook Vietnam JSC'
OFFICER = 'pb_hr_payroll_base.group_payroll_base_officer'


def _src(module, rel):
    with open(os.path.join(get_module_path(module), rel), encoding='utf-8') as fh:
        return fh.read()


def _code(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?<!:)//[^\n]*', '', src)


@tagged('post_install', '-at_install', 'learnrev')
class TestLearnrevP4(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Scenario = cls.env['learn.scenario']
        cls.demo_company = cls.env['res.company'].search([('name', '=', DEMO_COMPANY)], limit=1)
        cls.demo_group = cls.env.ref('pb_demo.group_payobook_demo', raise_if_not_found=False)
        officer = cls.env.ref(OFFICER, raise_if_not_found=False)
        cls.demo_users = []
        if cls.demo_company and cls.demo_group:
            groups = [cls.env.ref('base.group_user').id, cls.demo_group.id] + ([officer.id] if officer else [])
            for n in (1, 2):
                cls.demo_users.append(cls.env['res.users'].create({
                    'name': 'LRP4 demo %d' % n,
                    'login': 'lrp4.demo.%d@example.com' % n,
                    'company_id': cls.demo_company.id,
                    'company_ids': [(6, 0, [cls.demo_company.id])],
                    'group_ids': [(6, 0, groups)],
                }))

    def _as(self, user):
        return self.Scenario.with_user(user).with_company(self.demo_company)

    def _demo_config(self):
        Config = self.env['hr.formula.config']
        dom = [('company_id', '=', self.demo_company.id)]
        if 'is_demo' in Config._fields:
            dom.append(('is_demo', '=', True))
        for cfg in Config.search(dom, order='id'):
            rule = cfg.rule_ids.filtered(lambda r: (r.value_kind or 'amount') in ('amount', 'money', False)
                                         and r.net_role not in ('net',))[:1]
            if rule:
                return cfg, rule
        return None, None

    # ------------------------------------------------------------- (a)
    def test_a1_outside_a_demo_session_nothing_is_checked(self):
        plain = self.env['res.users'].create({
            'name': 'LRP4 plain', 'login': 'lrp4.plain@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        S = self.Scenario.with_user(plain)
        self.assertEqual(S.checked_steps(), {})
        res = S.check('sc_treatment', 'fix', {})
        self.assertFalse(res['ok'])
        self.assertTrue(res['note']['en'] and res['note']['vi'])

    def test_a2_the_three_walkthroughs_are_declared(self):
        table = self.Scenario._checks()
        for ref in ('sc_treatment.fix', 'sc_treatment.recompute', 'sc_payrun.compute',
                    'sc_payrun.next', 'sc_records.review'):
            self.assertIn(ref, table)
        steps = {s['key']: {st['key'] for st in s['steps']}
                 for s in self.env['learn.content'].scenarios()}
        for ref in table:
            key, _dot, step = ref.partition('.')
            self.assertIn(step, steps.get(key, ()), '%s names no walkthrough step' % ref)
        # An unknown step is said as such, never a pass.
        if self.demo_users:
            res = self._as(self.demo_users[0]).check('sc_treatment', 'no_such_step', {})
            self.assertFalse(res['ok'])

    def test_a3_treatment_fix_counts_only_my_own_change(self):
        if not self.demo_users:
            self.skipTest('no demo world on this database')
        cfg, rule = self._demo_config()
        if not cfg:
            self.skipTest('no demo scheme with an amount rule')
        me, other = self.demo_users
        self.assertEqual(self._as(me).checked_steps().get('sc_treatment'), ['fix', 'recompute'])
        args = {'config_id': cfg.id}
        before = self._as(me).check('sc_treatment', 'fix', args)
        self.assertFalse(before['ok'], before)
        # Someone else answers a row: it is not my work.
        role = 'deduction' if rule.net_role != 'deduction' else 'earning'
        cfg.with_user(other).with_company(self.demo_company).set_component_setup(
            {rule.code: {'pay_role': role}})
        self.assertFalse(self._as(me).check('sc_treatment', 'fix', args)['ok'],
                         "another user's change counted as mine")
        # Now I do it, on the board's own write path.
        role2 = 'earning' if role == 'deduction' else 'deduction'
        cfg.with_user(me).with_company(self.demo_company).set_component_setup(
            {rule.code: {'pay_role': role2}})
        after = self._as(me).check('sc_treatment', 'fix', args)
        self.assertTrue(after['ok'], after)
        self.assertIn(rule.name or rule.code, after['note']['en'])
        self.assertTrue(after['note']['vi'])
        # Without a scheme the step says what to open — never "no access".
        nocfg = self._as(me).check('sc_treatment', 'fix', {})
        self.assertFalse(nocfg['ok'])
        self.assertIn('Component treatment', nocfg['note']['en'])

    def test_a4_treatment_recompute_agrees_with_right_now(self):
        if not self.demo_users:
            self.skipTest('no demo world on this database')
        cfg, _rule = self._demo_config()
        if not cfg:
            self.skipTest('no demo scheme')
        me = self.demo_users[0]
        res = self._as(me).check('sc_treatment', 'recompute', {'config_id': cfg.id})
        items = self.env['hr.formula.config'].with_user(me).with_company(self.demo_company) \
            .learn_right_now({'config_id': cfg.id})
        items = items.get('items') if isinstance(items, dict) else items
        stale = any(i.get('key') == 'recompute' for i in items or ())
        self.assertEqual(res['ok'], not stale, res)

    def test_a5_payrun_reuses_the_live_predicates(self):
        if not self.demo_users:
            self.skipTest('no demo world on this database')
        me = self.demo_users[0]
        live = self.env['learn.live'].with_user(me).with_company(self.demo_company)
        self.assertEqual(self._as(me).check('sc_payrun', 'compute', {}),
                         live.check('june_run_computed'))
        self.assertEqual(self._as(me).check('sc_payrun', 'next', {}),
                         live.check('june_run_submitted'))

    def test_a6_records_counts_my_bank_change_on_a_demo_employee(self):
        if not self.demo_users or 'pb.records.change' not in self.env:
            self.skipTest('no demo world / Records Desk here')
        Emp = self.env['hr.employee']
        if 'is_demo' not in Emp._fields:
            self.skipTest('no demo employees')
        emp = Emp.search([('is_demo', '=', True), ('company_id', '=', self.demo_company.id)], limit=1)
        if not emp:
            self.skipTest('no demo employee')
        me, other = self.demo_users
        self.assertFalse(self._as(me).check('sc_records', 'review', {})['ok'])

        def change(user):
            # with_user(...).sudo() keeps the uid, so create_uid is the user —
            # the shape the desk's own apply writes.
            Apply = self.env['pb.records.apply'].with_user(user).sudo()
            app = Apply.create({'name': 'LRP4 %s' % user.login})
            return self.env['pb.records.change'].with_user(user).sudo().create({
                'apply_id': app.id, 'employee_id': emp.id, 'employee_name': emp.name,
                'model': 'res.partner.bank', 'res_id': 1, 'field_key': 'b:acc_number',
                'field_label': 'Account number', 'old_json': '"1"', 'new_json': '"2"'})

        change(other)
        self.assertFalse(self._as(me).check('sc_records', 'review', {})['ok'],
                         "another user's bank change counted as mine")
        change(me)
        res = self._as(me).check('sc_records', 'review', {})
        self.assertTrue(res['ok'], res)
        self.assertIn(emp.name, res['note']['en'])

    def test_a7_the_seam_never_elevates_or_writes(self):
        src = _src('pb_learn', 'models/learn_scenario.py')
        code = re.sub(r'""".*?"""', '', src, flags=re.S)
        self.assertNotIn('sudo(', code)
        for verb in ('.write(', '.create(', '.unlink('):
            self.assertNotIn(verb, code)
        treat = _src('pb_formula_studio', 'models/learn_right_now.py')
        body = treat.split('def learn_check_treatment', 1)[1].split('\n    def _learn_stale_runs', 1)[0]
        self.assertNotIn('sudo(', body)

    # ------------------------------------------------------------- (b)
    def test_b1_bootstrap_carries_the_company_country(self):
        company = self.env.company
        vn = self.env.ref('base.vn')
        idn = self.env.ref('base.id')
        company.country_id = idn
        self.assertEqual(self.env['learn.runtime'].bootstrap()['country'], 'ID')
        company.country_id = vn
        self.assertEqual(self.env['learn.runtime'].bootstrap()['country'], 'VN')
        company.country_id = False
        self.assertEqual(self.env['learn.runtime'].bootstrap()['country'], '')

    def test_b2_the_open_scheme_country_rides_on_the_guide(self):
        cfg = self.env['hr.formula.config'].search([('country_code', '!=', False)], limit=1)
        if not cfg:
            self.skipTest('no pay scheme here')
        g = self.env['learn.guide'].guide('treatment', {'config_id': cfg.id})
        self.assertEqual(g['screen']['country'], cfg.country_code.upper())
        self.assertEqual(self.env['learn.guide'].guide('treatment')['screen']['country'], '')

    # ------------------------------------------------------------- (c)
    def test_c1_practice_copies_say_what_the_screens_say(self):
        from odoo.addons.pb_learn.models.learn_guide import discover
        mans = discover(self.env.registry._init_modules, strict=True)
        errors = []
        for key, man in sorted(mans.items()):
            errors += gt.check_replica(key, man, read_rel)
        self.assertFalse(errors, '\n'.join(errors))
        self.assertIn('treatment', mans)
        self.assertIsNotNone(gt.replica_region(read_rel(gt.REPLICA_FILE), 'treatment'))

    def test_c2_the_gate_fails_on_a_synthetic_drift(self):
        from odoo.addons.pb_learn.models.learn_guide import discover
        man = discover(self.env.registry._init_modules, strict=True)['treatment']
        real = read_rel(gt.REPLICA_FILE)
        drifted = real.replace('B("Report group", "Nhóm báo cáo")', 'B("Group", "Nhóm")') \
                      .replace('B("Run signal", "Tín hiệu cho đợt lương")', 'B("Tells the run", "Báo cho đợt lương")')
        self.assertNotEqual(drifted, real, 'the synthetic drift changed nothing')

        def read(rel):
            return drifted if rel == gt.REPLICA_FILE else read_rel(rel)
        errs = gt.check_replica('treatment', man, read)
        self.assertTrue(any('header "Group"' in e for e in errs), errs)
        self.assertTrue(any('column "Run signal"' in e for e in errs), errs)

    # ------------------------------------------------------------- (d)
    def test_d1_a_board_refusal_ends_the_walkthrough(self):
        overlay = _src('pb_learn', 'static/src/scenario/scenario_overlay.js')
        boxes = overlay.split('const REFUSAL_BOXES = [', 1)[1].split('].join', 1)[0]
        self.assertIn('".pct-empty"', boxes)

    def test_d2_watch_keeps_the_drawer(self):
        coach = _code(_src('pb_learn', 'static/src/coach/coach.js'))
        body = coach.split('async startScenario(key, mode, stepKey) {', 1)[1].split('\n    }\n', 1)[0]
        self.assertNotIn('this.close()', body)

    def test_d3_the_spotlight_leaves_the_guide_dock_alone(self):
        spot = _code(_src('pb_learn', 'static/src/engine/spotlight.js'))
        self.assertNotRegex(spot, r'["\']lrn-docked["\']')
        self.assertIn('"lrn-spot-docked"', spot)
        scss = _src('pb_learn', 'static/src/journey/journey.scss')
        self.assertIn('body.lrn-spot-docked .lrn-screen', scss)

    def test_d4_slow_is_not_no_access(self):
        svc = _code(_src('pb_learn', 'static/src/scenario/scenario_service.js'))
        once = svc.split('async function navigateOnce(ref) {', 1)[1].split('\n        }\n', 1)[0]
        self.assertIn('reachable(screen) === false', once)
        self.assertIn('"slow"', once)
        overlay = _code(_src('pb_learn', 'static/src/scenario/scenario_overlay.js'))
        self.assertIn('scSlowBody', overlay)
        self.assertIn('data-act="s-retry"', overlay)

    def test_d5_the_lesson_panel_runs_in_node(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed here')
        version = subprocess.run([node, '--version'], capture_output=True, text=True,
                                 check=False).stdout.strip()
        major = re.match(r'v(\d+)', version)
        if not major or int(major.group(1)) < 18:
            self.skipTest('node %s is too old (18+)' % version)
        root = os.path.dirname(get_module_path('pb_learn'))
        if not os.path.isdir(os.path.join(root, 'pb_hub')):
            self.skipTest('pb_hub is not beside pb_learn on this addons path')
        env = dict(os.environ, PB_SRC_ROOT=root)
        here = os.path.dirname(os.path.abspath(__file__))
        out = subprocess.run([node, os.path.join(here, 'js', 'lesson_panel.test.mjs')],
                             capture_output=True, text=True, timeout=180, env=env, check=False)
        self.assertEqual(out.returncode, 0, out.stdout[-4000:] + out.stderr[-2000:])
        self.assertRegex(out.stdout, r'\d+ passed, 0 failed')
