# -*- coding: utf-8 -*-
"""LEARNREV P3 — the Library's server halves (handover §5 T2) and S10.

  (a) `learn.guide.rpc_index` covers every manifest screen, in English and in
      Vietnamese, both spellings on every row, one short line each
  (b) every station lands in exactly one menu group (no orphan)
  (c) the Library's MENU_ORDER is the rail's order on this database
  (d) `bootstrap` still serves skill_tree / streak / next_best (contract kept;
      the page draws none of the first two)
  (e) the Learn hub's texts and every string the Library draws no longer say
      the retired page words, in either language
  (f) the truth gate fails a manifest column that is split by a tag (LR30)
  (g) S10: with the composer AND the Guide on, Explain on a manifest screen
      is the Guide's answer verbatim, never a model rewrite; a screen without
      a manifest is still rewritten
  + the Library's node suite (tests/js/library.test.mjs)
"""
import json
import os
import re
import shutil
import subprocess
from unittest.mock import patch

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_learn.models import learn_guide as guide_mod
from odoo.addons.pb_learn.models import learn_intent as intent_mod

from . import guide_truth as gt
from .test_guide_truth import EXPECTED, load_vi

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDE_FLAG = guide_mod.GUIDE_FLAG
COMPOSE_FLAG = intent_mod.COMPOSE_FLAG

#: The words of the Learning page P3 retired (G9, G11, G13, G14, owner
#: decision 2026-10-17). The `retired_labels` list for the Learn hub itself:
#: none may be said by the hub's texts or by anything the Library draws.
RETIRED_PAGE_WORDS = {
    'en': ['Your journey', 'Overall', 'badge', 'Not on your path', 'Show me how',
           'Practice missions', 'Reduce motion'],
    'vi': ['Hành trình của bạn', 'Tiến độ chung', 'huy hiệu', 'Không thuộc lộ trình',
           'Chỉ tôi cách làm', 'Nhiệm vụ thực hành', 'Giảm chuyển động'],
}
#: Chrome keys the Library's own pages read besides its `T("…")` calls: the
#: outline / player back button, the search box, the guided-practice button.
PAGE_KEYS = ('yourJourney', 'search', 'missions', 'hubTitle', 'nbRequired', 'nbTitle')


def _read(module, rel):
    with open(os.path.join(get_module_path(module), rel), encoding='utf-8') as fh:
        return fh.read()


def _library_src():
    return _read('pb_learn', 'static/src/journey/library.js')


def menu_order():
    """[(group key, rail item xml-id, [hub tags])] as library.js declares it."""
    src = _library_src()
    block = re.search(r'export const MENU_ORDER = \[(.*?)\n\];', src, re.S).group(1)
    out = []
    for m in re.finditer(r'\{ key: "([a-z]+)", item: "([a-z_.]+)", tags: \[([^\]]*)\]', block):
        out.append((m.group(1), m.group(2), re.findall(r'"([a-z_]+)"', m.group(3))))
    return out


def line_groups():
    src = _library_src()
    block = re.search(r'export const LINE_GROUP = \{(.*?)\};', src, re.S).group(1)
    return dict(re.findall(r'(\w+): "([a-z]+)"', block))


@tagged('post_install', '-at_install', 'learnrev')
class TestLearnrevP3(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Guide = cls.env['learn.guide']
        cls.Intent = cls.env['learn.intent']
        cls.Content = cls.env['learn.content']
        cls.content = cls.Content.tree()

    # ------------------------------------------------------------- (a)
    def test_a_the_field_index_covers_every_manifest_in_both_languages(self):
        manifests = self.Guide._manifests()
        if not EXPECTED <= set(manifests):
            self.skipTest('not every manifest module is installed here: %s'
                          % sorted(EXPECTED - set(manifests)))
        en = self.Guide.with_context(lang='en_US').rpc_index()
        self.assertEqual({r['screen'] for r in en}, set(manifests),
                         'the index misses a screen that has a manifest')
        for row in en:
            for key in ('screen', 'screen_name', 'key', 'column', 'columns', 'line'):
                self.assertIn(key, row, row)
            self.assertTrue(row['column'], row)
            self.assertLessEqual(len(row['line']), guide_mod.INDEX_LINE_MAX, row)
            self.assertNotRegex(row['line'], r'(?i)odoo')
        pay_role = [r for r in en if r['screen'] == 'treatment' and r['key'] == 'pay_role']
        self.assertEqual(len(pay_role), 1)
        self.assertEqual(pay_role[0]['column'], 'Pay role')
        self.assertEqual(pay_role[0]['screen_name'], 'Component treatment')

        load_vi(self.env, {man['_module'] for man in manifests.values()} | {'pb_learn'})
        vi = self.Guide.with_context(lang='vi_VN').rpc_index()
        self.assertEqual({r['screen'] for r in vi}, set(manifests))
        cols = {(m['_module'], k): {f['key']: f.get('column') or {} for f in m.get('fields') or ()}
                for k, m in manifests.items()}
        for row in vi:
            man = manifests[row['screen']]
            authored = cols[(man['_module'], row['screen'])].get(row['key']) or {}
            self.assertEqual(row['column'], authored.get('vi'),
                             'asked in Vietnamese, the column is the Vietnamese one: %s' % row)
            self.assertEqual(len(row['columns']), 2, 'both spellings on every row: %s' % row)
            self.assertIn(authored.get('en'), row['columns'])
            self.assertEqual(len(row['screen_names']), 2, row)
        self.assertEqual(len(vi), len(en), 'the same rows in both languages')

    def test_a2_first_sentence_is_the_guides_row_rule(self):
        f = guide_mod.first_sentence
        self.assertEqual(f('One. Two.'), 'One.')
        self.assertEqual(f('No stop here'), 'No stop here')
        long_ = 'x' * 200
        self.assertEqual(len(f(long_)), guide_mod.INDEX_LINE_MAX)
        self.assertTrue(f(long_).endswith('…'))
        self.assertEqual(f('  spaced   out.  More'), 'spaced out.')

    # ------------------------------------------------------------- (b)
    def test_b_every_station_lands_in_one_menu_group(self):
        order = menu_order()
        self.assertEqual(len(order), 8, order)
        tag_group = {t: g for g, _item, tags in order for t in tags}
        lines = line_groups()
        groups = {g for g, _i, _t in order}
        self.assertTrue(set(lines.values()) <= groups, lines)
        screens = {s['key']: s for s in self.content['screens']}
        orphans = []
        placed = {}
        for st in self.content['stations']:
            count = {}
            for place in (screens.get(st['key']) or {}).get('places') or ():
                tag = place.split(':', 1)[0]
                if tag in tag_group:
                    count[tag_group[tag]] = count.get(tag_group[tag], 0) + 1
            group = max(count, key=count.get) if count else lines.get(st['line'])
            if group not in groups:
                orphans.append(st['key'])
            placed[st['key']] = group
        self.assertFalse(orphans, 'stations in no menu group: %s' % orphans)
        self.assertEqual(len(placed), len(self.content['stations']))
        for key in ('formula', 'mapping', 'treatment', 'matrix', 'statutory'):
            self.assertEqual(placed.get(key), 'settings', key)
        # Every line of the content plane has a group (the chapters' old test).
        self.assertTrue(set(self.content['line_order']) <= set(lines),
                        set(self.content['line_order']) - set(lines))

    # ------------------------------------------------------------- (c)
    def test_c_menu_order_is_the_rails_order(self):
        if 'pb.sidebar.item' not in self.env:
            self.skipTest('the rail module is not installed here')
        order = menu_order()
        found = []
        for group, xmlid, _tags in order:
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec:
                found.append((group, rec))
        if len(found) < 2:
            self.skipTest('the hub modules are not installed here')
        for group, rec in found:
            self.assertEqual(rec._name, 'pb.sidebar.item', rec)
            self.assertTrue(rec.active, '%s (%s) is not on the rail' % (group, rec.name))
        rail = sorted(found, key=lambda gr: (gr[1].section_id.sequence, gr[1].section_id.id,
                                             gr[1].sequence, gr[1].id))
        self.assertEqual([g for g, _r in rail], [g for g, _r in found],
                         'the Library lists the menu groups in another order than the rail: '
                         'rail %s' % [(g, r.name) for g, r in rail])

    # ------------------------------------------------------------- (d)
    def test_d_bootstrap_keeps_its_contract(self):
        b = self.env['learn.runtime'].bootstrap()
        for key in ('skill_tree', 'streak', 'next_best', 'path', 'progress',
                    'visible_stations', 'demo_world', 'guide'):
            self.assertIn(key, b, key)
        page = _read('pb_learn', 'static/src/journey/journey.js') + _library_src()
        code = re.sub(r'/\*.*?\*/', '', page, flags=re.S)
        code = re.sub(r'(?<!:)//[^\n]*', '', code)
        for gone in ('_streakHTML', 'tierOf(', 'badgeEarned', '_lineRingHTML', '_lifeTrailHTML',
                     'T("overall")', 'T("badge")', 'T("offPath")', 'T("scenarios")',
                     'T("reduceMotion")', 'toggleMotion'):
            self.assertNotIn(gone, code, 'the Learning page still draws %s' % gone)

    # ------------------------------------------------------------- (e)
    def test_e_no_retired_page_word_on_the_learn_hub_or_the_library(self):
        texts = []
        hub = next(s for s in self.content['screens'] if s['key'] == 'hub_learn')
        for node in (hub.get('name'), hub.get('blurb'), hub.get('next_step'),
                     (hub.get('hub') or {}).get('tabs')):
            texts.extend(('hub_learn', p) for p in gt.content_pairs(node))
        keys = set(re.findall(r'\bT\("([A-Za-z0-9_.]+)"\)', _library_src())) | set(PAGE_KEYS)
        chrome = self.content['chrome']
        missing = sorted(k for k in keys if k not in chrome and not k.startswith('lines.'))
        self.assertFalse(missing, 'the Library reads chrome keys that do not exist: %s' % missing)
        texts.extend(('chrome %s' % k, chrome[k]) for k in sorted(keys) if k in chrome)
        for intent in self.content.get('intents') or ():
            for p in gt.content_pairs(intent.get('blocks')):
                if 'Learn ›' in (p.get('en') or ''):
                    texts.append(('help answer %s' % intent.get('key'), p))
        bad = []
        for where, pair in texts:
            for lang in ('en', 'vi'):
                value = pair.get(lang) or ''
                for word in RETIRED_PAGE_WORDS[lang]:
                    if word.lower() in value.lower():
                        bad.append('%s (%s): "%s" in %s' % (where, lang, word, value[:100]))
                if re.search(r'(?i)odoo', value):
                    bad.append('%s (%s) says the brand word' % (where, lang))
            self.assertTrue(pair.get('en') and pair.get('vi'), '%s has one language only' % where)
        self.assertFalse(bad, '\n'.join(bad))

    # ------------------------------------------------------------- (f)
    def test_f_the_gate_fails_a_column_split_by_a_tag(self):
        fake = {'templates': ['x/t.xml'], 'model': 'x', 'path': {'xmlid': 'x.y'},
                'purpose': {'en': 'p', 'vi': 'p'},
                'fields': [{'key': 'k', 'field': 'f',
                            'column': {'en': 'Included in another total', 'vi': 'v'}}]}
        anchors = json.loads(_read('pb_learn', 'static/src/anchors.json'))
        split = gt.check_files('treatment', fake,
                               lambda rel: ('<th>Included in<br/>another total</th>'
                                            if rel == 'x/t.xml' else None),
                               self.content, anchors, lambda m: {})
        self.assertTrue(any('split by a tag' in e for e in split), split)
        whole = gt.check_files('treatment', fake,
                               lambda rel: ('<th class="pct-th-wrap">Included in another total</th>'
                                            if rel == 'x/t.xml' else None),
                               self.content, anchors, lambda m: {})
        self.assertFalse([e for e in whole if 'split by a tag' in e], whole)

    # ------------------------------------------------------------- (g) S10
    def test_g_explain_from_the_guide_is_never_rewritten(self):
        if not self.Guide.manifest('treatment') or 'hr.formula.rule' not in self.env:
            self.skipTest('the treatment manifest is not installed here')
        param = self.env['ir.config_parameter'].sudo()
        param.set_param(GUIDE_FLAG, 'True')
        param.set_param(COMPOSE_FLAG, 'True')
        composed = 'COMPOSED BY A MODEL, NOT THE GUIDE'

        class Provider:
            calls = 0

            def generate_text(self, prompt, **kw):
                Provider.calls += 1
                return composed

        with patch.object(type(self.Intent), '_provider', lambda self_: Provider()):
            answer = self.Intent.explain_screen('treatment', 'en_US')
            self.assertTrue(answer.get('guide_door'), answer)
            self.assertNotEqual(answer.get('source_kind'), 'composed')
            text = json.dumps(answer, ensure_ascii=False)
            self.assertNotIn(composed, text, 'the Guide answer was rewritten by the model')
            purpose = self.Guide.manifest('treatment')['purpose']['en']
            self.assertEqual(answer['blocks'][0]['body']['en'], purpose,
                             'the purpose is the manifest sentence, verbatim')
            steps = [s['text']['en'] for b in answer['blocks'] if b['kind'] == 'steps'
                     for s in b['steps']]
            self.assertIn('You are here: Mapping › Component treatment', steps)
            self.assertEqual(Provider.calls, 0, 'the composer was even asked')
            # A covered screen WITHOUT a manifest is still the composer's.
            plain = next((s['key'] for s in self.content['screens']
                          if not s.get('hub') and not self.Guide.manifest(s['key'])
                          and self.Intent._explain_floor(s['key'])), None)
            if plain:
                other = self.Intent.explain_screen(plain, 'en_US')
                self.assertEqual(other.get('source_kind'), 'composed', plain)
                self.assertIn(composed, json.dumps(other, ensure_ascii=False))
        # Guide off: the composer may rewrite treatment again (as before P2).
        param.set_param(GUIDE_FLAG, 'False')
        with patch.object(type(self.Intent), '_provider', lambda self_: Provider()):
            off = self.Intent.explain_screen('treatment', 'en_US')
            self.assertEqual(off.get('source_kind'), 'composed')

    # ------------------------------------------------------------- T1 runner
    def test_h_the_library_runs_in_node(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed here; run '
                          'pb_learn/tests/js/library.test.mjs by hand.')
        version = subprocess.run([node, '--version'], capture_output=True, text=True,
                                 check=False).stdout.strip()
        major = re.match(r'v(\d+)', version)
        if not major or int(major.group(1)) < 18:
            self.skipTest('node %s is too old for the Library test (18+).' % version)
        root = os.path.dirname(get_module_path('pb_learn'))
        if not os.path.isdir(os.path.join(root, 'pb_hub')):
            self.skipTest('pb_hub is not beside pb_learn on this addons path')
        env = dict(os.environ, PB_SRC_ROOT=root)
        out = subprocess.run([node, os.path.join(HERE, 'js', 'library.test.mjs')],
                             capture_output=True, text=True, timeout=180, env=env, check=False)
        self.assertEqual(out.returncode, 0, out.stdout[-4000:] + out.stderr[-2000:])
        self.assertRegex(out.stdout, r'\d+ passed, 0 failed')
