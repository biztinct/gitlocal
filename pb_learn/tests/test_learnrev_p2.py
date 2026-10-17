# -*- coding: utf-8 -*-
"""LEARNREV P2 — the server halves of the Guide panel (handover §9 T3).

  (a) Explain this screen from the Guide (switch on) / unchanged (switch off)
  (b) "What should I do next here?" answers from the screen's Right now
  (c) the router sends the whatnext words to the guide on every screen,
      PayAI available (LR5)
  (d) the switch: `bootstrap()['guide']`, Learn › Settings
  (e) Mapping's Learn screen starts at Connections
  (f) every right-now action is filter | open | open_record in the §6 shape
  (g) the Access ruling: no manifest door into Access and delegations, and
      the Guide drops one if a manifest ever names it
  + the field card thumbs write one bounded event row, no free text
"""
import json
import os
import re
from unittest.mock import patch

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_learn.models import learn_guide as guide_mod
from odoo.addons.pb_learn.models import learn_intent as intent_mod

from .test_guide_truth import load_vi

FLAG = guide_mod.GUIDE_FLAG
ACTION_KINDS = {'filter', 'open', 'open_record'}


@tagged('post_install', '-at_install', 'learnrev')
class TestLearnrevP2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Guide = cls.env['learn.guide']
        cls.Intent = cls.env['learn.intent']
        cls.Helper = cls.env['learn.helper']
        cls.Content = cls.env['learn.content']
        cls.has_formula = 'hr.formula.config' in cls.env
        if cls.has_formula:
            load_vi(cls.env, {'pb_hr_payroll_formula', 'pb_formula_studio', 'pb_learn'})
            cls.config = cls.env['hr.formula.config'].create({
                'name': 'P2 Scheme', 'code': 'PTWOSCHEME', 'country_code': 'VN'})

            def rule(code, name, letter, **kw):
                vals = {'config_id': cls.config.id, 'code': code, 'name': name,
                        'column_letter': letter, 'forced_column_letter': letter,
                        'column_type': 'input'}
                vals.update(kw)
                return cls.env['hr.formula.rule'].create(vals)

            rule('PTBASIC', 'Basic Salary', 'A', value_kind='money',
                 net_role='earning', net_role_confidence='certain')
            rule('PTLOAN', 'Loan Installment', 'B', value_kind='money')
            rule('PTHRS', 'Overtime Hours', 'C', value_kind='quantity',
                 net_role='earning', net_role_confidence='certain')
            rule('PTTAKE', 'Take Home', 'D', value_kind='money',
                 net_role='net', net_role_confidence='certain')

    def _flag(self, on):
        self.env['ir.config_parameter'].sudo().set_param(FLAG, 'True' if on else 'False')

    def _need_formula(self):
        if not self.has_formula:
            self.skipTest('the formula engine is not installed here')

    # ------------------------------------------------------------- (a)
    def test_a_explain_from_the_guide(self):
        self._need_formula()
        self._flag(False)
        tree = self.Content.tree()
        screen = self.Content.screen('treatment')
        off = self.Intent.explain_screen('treatment')
        self.assertEqual(off['blocks'], intent_mod.explain_blocks(
            tree, 'treatment', self.env['learn.runtime'].next_step_live(screen)),
            'switch off: Explain is exactly what shipped before')
        self.assertNotIn('guide_door', off)

        self._flag(True)
        on = self.Intent.explain_screen('treatment')
        kinds = [b['kind'] for b in on['blocks']]
        self.assertEqual(kinds[0], 'p')
        self.assertEqual(kinds[1], 'steps')
        self.assertEqual(kinds[-1], 'source')
        self.assertNotIn('ok', kinds, 'treatment has a live list: no static next sentence')
        cols = [b for b in on['blocks'][2:-1] if b['kind'] == 'p']
        self.assertTrue(1 <= len(cols) <= 3, cols)
        self.assertIn('<b>Comes from</b>', cols[0]['body']['en'])
        self.assertIn('Tell the pay scheme what each component is', on['blocks'][0]['body']['en'])
        steps = [s['text']['en'] for s in on['blocks'][1]['steps']]
        self.assertEqual(steps[0], 'You are here: Mapping › Component treatment')
        self.assertEqual(steps[1], 'Next: Pay Run › Run')
        vi_steps = [s['text']['vi'] for s in on['blocks'][1]['steps']]
        self.assertTrue(vi_steps[0].startswith('Bạn đang ở đây: '), vi_steps)
        self.assertTrue(on['guide_door'])
        self.assertTrue(on['matched'])
        # A screen with a manifest and NO live list keeps the next sentence.
        slip = self.Intent.explain_screen('payslips')
        if self.Guide.manifest('payslips') and self.Content.screen('payslips').get('next_step'):
            self.assertIn('ok', [b['kind'] for b in slip['blocks']])

    # ------------------------------------------------------------- (b)
    def test_b_whatnext_reads_right_now(self):
        self._need_formula()
        self._flag(True)
        Intent = self.Intent.with_context(pb_guide_args={'config_id': self.config.id})
        answer = Intent.answer_for('whatnext', 'treatment')
        self.assertTrue(answer['matched'])
        self.assertEqual(answer['blocks'][0]['kind'], 'steps', answer['blocks'])
        texts = [s['text']['en'] for s in answer['blocks'][0]['steps']]
        self.assertTrue(any('Loan Installment' in t for t in texts), texts)
        self.assertTrue(any('Overtime Hours' in t for t in texts), texts)
        vi = [s['text']['vi'] for s in answer['blocks'][0]['steps']]
        self.assertTrue(any('Vai trò trong lương' in t for t in vi), vi)
        self.assertTrue(answer['guide_door'])
        # No scheme in the context: the reason, never an empty answer.
        none = self.Intent.answer_for('whatnext', 'treatment')
        self.assertTrue(none['matched'])
        self.assertIn('No scheme selected', none['blocks'][0]['body']['en'])
        # Switch off: the static sentence, as before.
        self._flag(False)
        old = Intent.answer_for('whatnext', 'treatment')
        self.assertEqual(old['blocks'][0]['kind'], 'p')
        self.assertFalse(old['guide_door'])

    # ------------------------------------------------------------- (c)
    def test_c_router_sends_whatnext_to_the_guide_everywhere(self):
        self._flag(True)
        intent = self.Content.intent('whatnext')
        labels = [intent['label']['en'], intent['label']['vi']]
        self.assertEqual(labels, ['What should I do next here?', 'Tôi nên làm gì tiếp theo ở đây?'])
        H = type(self.Helper)
        bad = []
        with patch.object(H, '_payai_available', lambda s: True), \
                patch.object(H, '_can_act', lambda s: True), \
                patch.object(H, '_route_payai_state', lambda s, t, session_id=None: None):
            for screen in self.Content.screens():
                for label in labels:
                    out = self.Helper.route(label, screen['key'], 'vi' if label == labels[1] else 'en')
                    if out.get('route') != 'guide' or (out.get('answer') or {}).get('key') != 'whatnext':
                        bad.append('%s / %s -> %s %s' % (screen['key'], label, out.get('route'),
                                                         out.get('why')))
        self.assertFalse(bad, '\n'.join(bad[:20]))

    # ------------------------------------------------------------- (d)
    def test_d_the_switch(self):
        param = self.env['ir.config_parameter'].sudo()
        param.set_param(FLAG, False)
        self.assertIs(self.env['learn.runtime'].bootstrap()['guide'], False)
        keys = [s['key'] for s in self.env['learn.settings'].get_switches()]
        self.assertIn('guide', keys)
        self.env['learn.settings'].set_switch('guide', True)
        self.assertIs(self.env['learn.runtime'].bootstrap()['guide'], True)
        self.env['learn.settings'].set_switch('guide', False)
        self.assertIs(self.env['learn.runtime'].bootstrap()['guide'], False)

    # ------------------------------------------------------------- (e)
    def test_e_mapping_starts_at_connections(self):
        mapping = self.Content.screen('mapping')
        self.assertEqual(mapping['places'][0], 'pb_mapping_studio:desk')
        self.assertIn('pb_mapping_studio:journey', mapping['places'])
        self.assertIn('Connect', mapping['blurb']['en'])
        man = self.Guide.manifest('mapping')
        if man:
            self.assertEqual(man['path'], {'tag': 'pb_mapping_studio', 'lens': 'desk'})

    # ------------------------------------------------------------- (f)
    def _check_action(self, a, where):
        self.assertIn(a['kind'], ACTION_KINDS, where)
        self.assertNotIn('ids', a, where)
        self.assertNotIn('config_id', a, where)
        if a['kind'] == 'open':
            self.assertTrue(a.get('xmlid'), where)
            self.assertIn('focus', a, where)
            self.assertIsInstance(a.get('context'), dict, where)
        elif a['kind'] == 'open_record':
            self.assertTrue(a.get('res_model') and a.get('res_id'), where)
        else:
            self.assertIn(a.get('value'), ('review', 'conflict', 'drift'), where)

    def test_f_provider_actions_have_the_panel_shape(self):
        if self.has_formula:
            for item in self.env['hr.formula.config'].learn_right_now({'config_id': self.config.id}):
                if item.get('action'):
                    self._check_action(item['action'], 'treatment %s' % item['key'])
        if 'pb.payruns' in self.env:
            for item in self.env['pb.payruns'].learn_right_now({}):
                if item.get('action'):
                    self._check_action(item['action'], 'payruns %s' % item['key'])
        # And the source: no provider spells the old keys.
        for module, rel in (('pb_formula_studio', 'models/learn_right_now.py'),
                            ('pb_payruns', 'models/pb_payruns_learn.py')):
            base = get_module_path(module)
            if not base:
                continue
            with open(os.path.join(base, rel), encoding='utf-8') as fh:
                src = fh.read()
            self.assertNotRegex(src, r"'ids'\s*:", rel)
            self.assertNotRegex(src, r"'(model|id)'\s*:", rel)

    # ------------------------------------------------------------- (g)
    def test_g_never_a_door_into_access(self):
        for key, man in self.Guide._manifests().items():
            p = man.get('path') or {}
            self.assertFalse(guide_mod.is_access_target(tag=p.get('tag'), lens=p.get('lens')),
                             '%s: its path goes to Access and delegations' % key)
            for side in ('before', 'after'):
                for item in man.get(side) or ():
                    other = self.Content.screen(item.get('screen')) or {}
                    places = [guide_mod.parse_place(pl) for pl in other.get('places') or ()]
                    places = [pp for pp in places if pp]
                    self.assertFalse(places and all(guide_mod.is_access_target(tag=t, lens=l)
                                                    for t, l in places),
                                     '%s: %s %s is behind the Access ruling' % (key, side, item))
        fake = {'model': None, 'purpose': {'en': 'x', 'vi': 'x'},
                'path': {'tag': 'pb_settings_hub', 'lens': 'access'}, '_module': 'pb_learn'}
        with patch.object(type(self.Guide), 'manifest', lambda s, k: fake):
            out = self.Guide.guide('treatment')
        self.assertEqual(out['screen']['path'], [])
        self.assertIn('path: not offered here', out['missing'])
        self.assertTrue(guide_mod.is_access_target(
            {'xmlid': 'pb_settings.action_pb_settings_hub', 'lens': 'nav'}))
        self.assertFalse(guide_mod.is_access_target(
            {'xmlid': 'pb_settings.action_pb_settings_hub', 'lens': 'formula'}))

    # ------------------------------------------------------------- extras
    def test_h_feedback_is_one_bounded_event(self):
        self._need_formula()
        Event = self.env['learn.event']
        before = Event.search_count([('kind', '=', 'guide_feedback')])
        self.assertTrue(self.Guide.rpc_feedback('treatment', 'pay_role', True))
        row = Event.search([('kind', '=', 'guide_feedback')], limit=1)
        self.assertEqual((row.screen, row.detail), ('treatment', 'pay_role:up'))
        self.assertFalse(self.Guide.rpc_feedback('treatment', 'why is Lan paid 4m', False),
                         'free text is never written')
        self.assertFalse(self.Guide.rpc_feedback('nowhere', 'pay_role', False))
        self.assertEqual(Event.search_count([('kind', '=', 'guide_feedback')]), before + 1)

    def test_i_cards_carry_both_spellings_and_provider_flag(self):
        self._need_formula()
        out = self.Guide.with_context(lang='en_US').guide('treatment', {'config_id': self.config.id})
        role = next(f for f in out['fields'] if f['key'] == 'pay_role')
        self.assertEqual(role['columns'], ['Pay role', 'Vai trò trong lương'])
        self.assertTrue(out['right_now']['provider'])
        rollup = next(f for f in out['fields'] if f['key'] == 'rollup')
        self.assertEqual(rollup['label'], 'Included in another total')
        bare = self.Guide.guide('payslips')
        self.assertFalse(bare['right_now'].get('provider'))

    def test_j_new_strings_never_say_the_brand(self):
        chrome = self.Content.chrome()
        keys = [k for k in chrome if re.match(r'^(g[A-Z]|swGuide|explainField)', k)]
        self.assertGreaterEqual(len(keys), 40)
        blob = json.dumps({k: chrome[k] for k in keys}, ensure_ascii=False)
        self.assertNotRegex(blob, r'(?i)odoo')
        for k in keys:
            self.assertTrue(chrome[k].get('en') and chrome[k].get('vi'), k)
