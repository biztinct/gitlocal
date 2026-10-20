# -*- coding: utf-8 -*-
"""LEARNREV P5b — thumbs on every lesson step and walkthrough card, every
lesson and walkthrough in the four lines, the feedback card's words in the
content plane.

  (a) a lesson step / walkthrough card is rated through the field cards' seam
      (`learn.guide.rpc_feedback`, `lesson.<L>.<i>` / `walk.<sc>.<step>`): one
      `guide_feedback` row under the STEP'S OWN screen, no text; a step the
      content does not have writes nothing; what the client says the screen
      is, is ignored
  (b) the Learn › Settings report lists a rated step as "<lesson> · Step n:
      <title>" (kind `step`) beside the screen's field rows, in both languages,
      and the CSV carries it
  (c) the shipped content: every lesson step and every live walkthrough step
      reads Look at · It means · It affects (no legacy body left), `press`
      never on a practice-copy anchor, every non-manifest lesson step names
      the template it was written from (data.js `source:` comments)
  (d) the feedback card reads its words from the content plane (chrome keys,
      both languages), not from bilingual pairs in learn_settings.js
  + the lesson panel's node suite (tests/js/lesson_panel.test.mjs: thumbs)
"""
import json
import os
import re
import shutil
import subprocess

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.abspath(__file__))


def _read(module, rel):
    with open(os.path.join(get_module_path(module), rel), encoding='utf-8') as fh:
        return fh.read()


def _content():
    return json.loads(_read('pb_learn', 'static/content/learn_content.json'))


@tagged('post_install', '-at_install', 'learnrev')
class TestLearnrevP5b(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref('base.group_user')
        cls.person = cls.env['res.users'].create({
            'name': 'LR P5b Reader', 'login': 'lr_p5b_reader',
            'group_ids': [(6, 0, [group_user.id])],
        })
        cls.admin = cls.env['res.users'].create({
            'name': 'LR P5b Admin', 'login': 'lr_p5b_admin',
            'group_ids': [(6, 0, [group_user.id, cls.env.ref('base.group_system').id])],
        })
        cls.env.cr.execute("DELETE FROM learn_event WHERE kind = 'guide_feedback'")
        tree = _content()
        cls.lesson = next(l for st in tree['stations'] for l in st.get('lessons') or ()
                          if l['key'] == 'L10')
        cls.scenario = next(s for s in tree['scenarios'] if s['key'] == 'sc_matrix')

    def _rate(self, ref, up, screen='dashboard'):
        return self.env['learn.guide'].with_user(self.person).rpc_feedback(screen, ref, up)

    def _rows(self):
        return self.env['learn.event'].sudo().search(
            [('kind', '=', 'guide_feedback'), ('user_id', '=', self.person.id)])

    # ---------------------------------------------------------------- (a)
    def test_a_lesson_step_is_rated_under_its_own_screen(self):
        step = self.lesson['steps'][1]
        self.assertTrue(self._rate('lesson.L10.1', False, screen='dashboard'))
        row = self._rows()
        self.assertEqual(len(row), 1)
        self.assertEqual(row.screen, step['screen'], 'the step\'s own screen, not the client\'s')
        self.assertEqual(row.detail, 'lesson.L10.1:down')

    def test_a2_walkthrough_card(self):
        step = self.scenario['steps'][0]
        self.assertTrue(self._rate('walk.sc_matrix.%s' % step['key'], True, screen=''))
        row = self._rows()
        self.assertEqual(row.screen, step['screen'] or self.scenario['screens'][0])
        self.assertEqual(row.detail, 'walk.sc_matrix.%s:up' % step['key'])

    def test_a3_unknown_steps_write_nothing(self):
        n = len(self.lesson['steps'])
        for ref in ('lesson.L10.%d' % n, 'lesson.L10.x', 'lesson.NOPE.0', 'lesson.L10',
                    'walk.sc_matrix.nope', 'walk.nope.hero', 'walk.', 'step.L10.1',
                    'lesson..0'):
            self.assertFalse(self._rate(ref, False), ref)
        self.assertFalse(self._rows())

    def test_a4_field_cards_unchanged(self):
        self.assertTrue(self._rate('pay_role', False, screen='treatment'))
        self.assertFalse(self._rate('pay_role', False, screen='dashboard'))
        self.assertEqual(self._rows().mapped('detail'), ['pay_role:down'])

    # ---------------------------------------------------------------- (b)
    def test_b_report_names_the_step(self):
        step = self.lesson['steps'][1]
        self._rate('lesson.L10.1', False)
        self._rate('lesson.L10.1', False)
        self._rate('walk.sc_matrix.%s' % self.scenario['steps'][0]['key'], True)
        for lang, tag in (('en', 'en'), ('vi', 'vi')):
            r = self.env['learn.feedback'].with_user(self.admin).report(30, lang)
            rows = [f for t in r['thumbs'] for f in t['fields'] if f['kind'] == 'step']
            mine = next(f for f in rows if f['key'] == 'lesson.L10.1')
            self.assertEqual(mine['down'], 2)
            self.assertIn(step['title'][tag], mine['label'])
            self.assertIn(self.lesson['name'][tag], mine['label'])
            self.assertIn('2', mine['label'], 'the step number a reader counts (index + 1)')
            screen = next(t for t in r['thumbs'] if any(f['key'] == 'lesson.L10.1' for f in t['fields']))
            self.assertEqual(screen['screen'], step['screen'])
        csv = self.env['learn.feedback'].with_user(self.admin).export_csv(30, 'en')['csv']
        self.assertIn(step['title']['en'], csv)

    # ---------------------------------------------------------------- (c)
    def test_c_every_step_in_the_four_lines(self):
        tree = _content()
        legacy, press = [], []
        for st in tree['stations']:
            for lesson in st.get('lessons') or ():
                for i, s in enumerate(lesson['steps']):
                    g = (s.get('variants') or {}).get('generic') or {}
                    look = s.get('look') or g.get('look')
                    means = s.get('means') or g.get('means')
                    affects = s.get('affects') or g.get('affects')
                    if not (look and means and affects) or (s.get('body') or {}).get('en'):
                        legacy.append('%s#%d' % (lesson['key'], i + 1))
                    if s.get('press') and str(s.get('anchor') or '').startswith('rep-'):
                        press.append('%s#%d' % (lesson['key'], i + 1))
        for sc in tree['scenarios']:
            if sc.get('retired'):
                continue
            for s in sc['steps']:
                if not (s.get('look') and s.get('means') and s.get('affects')) \
                        or (s.get('body') or {}).get('en'):
                    legacy.append('%s.%s' % (sc['key'], s.get('key')))
                if s.get('press') and str(s.get('anchor') or '').startswith('rep-'):
                    press.append('%s.%s' % (sc['key'], s.get('key')))
        self.assertFalse(legacy, 'steps not in the four lines: %s' % legacy)
        self.assertFalse(press, 'Press on a practice-copy step: %s' % press)

    def test_c2_vietnamese_for_every_line(self):
        tree = _content()
        missing = []
        for st in tree['stations']:
            for lesson in st.get('lessons') or ():
                for i, s in enumerate(lesson['steps']):
                    for line in ('look', 'means', 'affects', 'press'):
                        p = s.get(line)
                        if p and p.get('en') and not (p.get('vi') or '').strip():
                            missing.append('%s#%d %s' % (lesson['key'], i + 1, line))
        self.assertFalse(missing)

    def test_c3_brand_word_never_in_a_step(self):
        blob = _read('pb_learn', 'static/content/learn_content.json')
        self.assertIsNone(re.search(r'\bodoo\b', blob, re.I))

    # ---------------------------------------------------------------- (d)
    def test_d_feedback_card_words_in_the_content_plane(self):
        js = _read('pb_learn', 'static/src/hub/learn_settings.js')
        self.assertNotRegex(js, r'\{\s*en:\s*"', 'the card reads chrome keys, not bilingual pairs')
        chrome = _content()['chrome']
        keys = set(re.findall(r'"(fbk[A-Za-z0-9]+)"', js))
        self.assertTrue(keys, 'the card names its chrome keys')
        for k in keys:
            self.assertIn(k, chrome, k)
            self.assertTrue(chrome[k].get('en') and chrome[k].get('vi'), k)
            self.assertNotEqual(chrome[k]['en'], chrome[k]['vi'], k)

    # ---------------------------------------------------------------- node
    def test_n_lesson_panel_node_suite(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed here')
        out = subprocess.run([node, os.path.join(HERE, 'js', 'lesson_panel.test.mjs')],
                             capture_output=True, text=True, timeout=300)
        tail = (out.stdout or '')[-1500:] + (out.stderr or '')[-800:]
        self.assertEqual(out.returncode, 0, tail)
        self.assertRegex(out.stdout, r'\d+ passed, 0 failed')
