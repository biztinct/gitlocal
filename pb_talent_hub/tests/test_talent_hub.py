# -*- coding: utf-8 -*-
"""pb_talent_hub (NAV P2) — the GROW › Talent entry and its three tabs.

The hub ships no lens of its own; the boards register themselves from their
modules. So most of what can go wrong is a board still registering into the
hub it LEFT (People, the Lifecycle hub, Learn — and since LEARNING L0,
Training registering here after it moved to GROW › Learning), or the entry
not being where the revised menu puts it — all checked here.
"""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (module, palette file, lens key, sequence) — the three tabs, in rail order.
# LEARNING L0: Training (30) left for GROW › Learning.
TABS = [
    ('pb_goals', 'goals_palette.js', 'goals', 10),
    ('pb_pip', 'pip_palette.js', 'pip', 20),
    ('pb_rnr', 'rnr_palette.js', 'praise', 40),
]
_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestTalentHub(TransactionCase):

    def test_the_entry_sits_above_learn_in_grow(self):
        item = self.env.ref('pb_talent_hub.item_talent')
        self.assertTrue(item.active)
        self.assertEqual(item.section_id, self.env.ref('pb_learn.sec_learn'))
        self.assertEqual(item.sequence, 5)
        # LEARNING L0: Learning took the cap; Talent is the target.
        self.assertEqual(item.icon, 'target')
        self.assertNotIn('pb_training_board',
                         (item.match_action_tags or '').split(','))
        for model in ('pb.training', 'pb.training.assignment'):
            self.assertNotIn(model, (item.match_models or '').split(','))
        self.assertEqual(item.action_tag, 'pb_talent_hub')
        learn = self.env.ref('pb_learn.item_learn_journey')
        self.assertLess(item.sequence, learn.sequence)
        self.assertIn(self.env.ref('hr.group_hr_user'), item.groups_id)

    def test_the_hub_action_exists(self):
        act = self.env.ref('pb_talent_hub.action_pb_talent_hub')
        self.assertEqual(act._name, 'ir.actions.client')
        self.assertEqual(act.tag, 'pb_talent_hub')

    def test_the_icon_is_in_the_closed_rail_set(self):
        js = _read(os.path.join(get_module_path('pb_sidebar'), 'static', 'src',
                                'js', 'pb_sidebar.js'))
        self.assertRegex(js, r'\n\s+"?target"?:\s*\'<')

    def test_every_tab_registers_into_talent_and_not_its_old_hub(self):
        installed = set(self.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))
        for module, fname, key, seq in TABS:
            if module not in installed:
                continue
            src = _read(os.path.join(get_module_path(module), 'static', 'src',
                                     'js', fname))
            m = re.search(r'registry\.category\((\w+)\)\.add\("%s", \{(.*?)\}, '
                          r'\{ sequence: (\d+) \}\);' % key, src, re.S)
            self.assertTrue(m, '%s: no lens registration for %s' % (module, key))
            self.assertEqual(m.group(1), 'TALENT_LENSES', module)
            self.assertEqual(int(m.group(3)), seq, module)
            self.assertIn('pb_talent_hub', ast.literal_eval(_read(os.path.join(
                get_module_path(module), '__manifest__.py')))['depends'], module)

    def test_the_growth_tab_keeps_its_gate_probe_and_switch(self):
        src = _read(os.path.join(get_module_path('pb_pip'), 'static', 'src',
                                 'js', 'pip_palette.js'))
        block = src.split('registry.category(TALENT_LENSES).add("pip"', 1)[1]
        block = block.split('});', 1)[0]
        self.assertIn('label: _t("Growth")', block)
        self.assertIn('groups: PIP_GATE', block)
        self.assertIn('probe: { model: "pb.pip", method: "can_open" }', block)
        self.assertIn('feature: "lifecycle"', block)

    def test_every_asset_on_disk_is_in_the_bundle(self):
        manifest = ast.literal_eval(_read(os.path.join(HERE, '__manifest__.py')))
        bundle = set(manifest['assets']['web.assets_backend'])
        on_disk = set()
        for sub in ('js', 'xml'):
            d = os.path.join(HERE, 'static', 'src', sub)
            for f in os.listdir(d):
                on_disk.add('pb_talent_hub/static/src/%s/%s' % (sub, f))
        self.assertEqual(on_disk, bundle)

    def test_templates_parse_and_js_has_no_python_style_concatenation(self):
        for f in os.listdir(os.path.join(HERE, 'static', 'src', 'xml')):
            ElementTree.parse(os.path.join(HERE, 'static', 'src', 'xml', f))
        for f in os.listdir(os.path.join(HERE, 'static', 'src', 'js')):
            src = _read(os.path.join(HERE, 'static', 'src', 'js', f))
            self.assertFalse(_RE_ADJACENT_STRINGS.search(src), f)

    def test_no_user_visible_string_says_odoo(self):
        for sub in ('js', 'xml'):
            d = os.path.join(HERE, 'static', 'src', sub)
            for f in os.listdir(d):
                src = _read(os.path.join(d, f))
                for s in re.findall(r'_t\("([^"]*)"\)', src):
                    self.assertNotIn('odoo', s.lower(), f)

    # ---------------------------------------------------- LEARNING L0 (T9)
    def test_training_is_not_a_talent_tab_any_more(self):
        installed = set(self.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))
        if 'pb_training' not in installed:
            return
        src = _read(os.path.join(get_module_path('pb_training'), 'static',
                                 'src', 'js', 'training_palette.js'))
        self.assertNotIn('TALENT_LENSES', src)
        self.assertNotIn('pb_talent_hub', ast.literal_eval(_read(os.path.join(
            get_module_path('pb_training'), '__manifest__.py')))['depends'])

    def test_an_old_training_link_is_sent_to_learning_courses(self):
        src = _read(os.path.join(HERE, 'static', 'src', 'js',
                                 'talent_hub.js'))
        self.assertIn('xmlid: "pb_learning_hub.action_pb_learning_hub"', src)
        self.assertIn('lens: "courses"', src)
        self.assertIn('ctx.pb_lens === "training"', src)
        self.assertRegex(src, r'onMounted\(\(\) => openHub\(this\.actionService, \{\s+'
                              r'\.\.\.TRAINING_REDIRECT')
        self.assertIn('brand: { label: _t("Talent"), icon: "target" }', src)
        xml = _read(os.path.join(HERE, 'static', 'src', 'xml',
                                 'talent_hub.xml'))
        self.assertIn('t-if="redirecting"', xml)

    def test_the_blurb_no_longer_says_training(self):
        src = _read(os.path.join(HERE, 'static', 'src', 'js',
                                 'talent_hub_palette.js'))
        self.assertIn('sublabel: _t("Goals, growth and praise")', src)
        # R10: the old word still finds a door (it lists Learning too).
        self.assertIn('"training"', src)
        po = _read(os.path.join(HERE, 'i18n', 'vi_VN.po'))
        self.assertIn('msgid "Goals, growth and praise"\n'
                      'msgstr "Mục tiêu, phát triển và khen ngợi"', po)
        self.assertNotIn('Goals, growth, training and praise', po)
