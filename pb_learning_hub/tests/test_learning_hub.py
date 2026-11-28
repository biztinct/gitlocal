# -*- coding: utf-8 -*-
"""pb_learning_hub (LEARNING L0) — the GROW › Learning entry and its rail.

The hub ships no lens of its own; the training module registers eight. So
most of what can go wrong is the entry not being where the owner's menu puts
it (between Talent and Help, open to everybody), a tab still registering into
Talent, or a white-label slip in the few words this module owns — all checked
here (handover tests T1 and T3).
"""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")
# Pictographs and dingbats; a Lucide icon is an SVG path, never a character.
_RE_EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿⭐✅]')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestLearningHub(TransactionCase):

    def _installed(self, name):
        return bool(self.env['ir.module.module'].sudo().search_count(
            [('name', '=', name), ('state', '=', 'installed')]))

    # ------------------------------------------------------------ T1
    def test_t1_the_entry_sits_between_talent_and_help_in_grow(self):
        item = self.env.ref('pb_learning_hub.item_learning')
        self.assertTrue(item.active)
        self.assertEqual(item.section_id, self.env.ref('pb_learn.sec_learn'))
        self.assertEqual(item.sequence, 7)
        self.assertEqual(item.icon, 'graduation-cap')
        self.assertEqual(item.action_tag, 'pb_learning_hub')
        self.assertEqual(item.action_xmlid,
                         'pb_learning_hub.action_pb_learning_hub')
        self.assertEqual(item.name, 'Learning')
        # Everybody's, like Home and Help: every member of staff has
        # "My learning"; the training team's tabs gate themselves.
        self.assertFalse(item.groups_id)
        help_item = self.env.ref('pb_learn.item_learn_journey')
        self.assertLess(item.sequence, help_item.sequence)
        talent = self.env.ref('pb_talent_hub.item_talent',
                              raise_if_not_found=False)
        if talent:
            self.assertLess(talent.sequence, item.sequence)

    def test_t1_the_entry_claims_the_training_boards(self):
        item = self.env.ref('pb_learning_hub.item_learning')
        tags = item.match_action_tags.split(',')
        for tag in ('pb_learning_hub', 'pb_training_board',
                    'pb_training_numbers'):
            self.assertIn(tag, tags)
        models = item.match_models.split(',')
        for model in ('pb.training', 'pb.training.assignment',
                      'slide.channel', 'survey.survey'):
            self.assertIn(model, models)

    def test_t1_an_employee_with_no_training_group_sees_the_entry(self):
        user = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO Learner Entry',
                'login': 'demo.learner.entry@example.com',
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            })
        data = self.env['pb.sidebar.item'].with_user(user).get_sidebar_data()
        names = [i['name'] for s in data for i in s['items']]
        self.assertIn('Learning', names)

    # ------------------------------------------------------------ T3
    def test_t3_the_hub_action_exists(self):
        act = self.env.ref('pb_learning_hub.action_pb_learning_hub')
        self.assertEqual(act._name, 'ir.actions.client')
        self.assertEqual(act.tag, 'pb_learning_hub')
        self.assertEqual(act.name, 'Learning')

    def test_t3_the_icon_is_in_the_closed_rail_set(self):
        js = _read(os.path.join(get_module_path('pb_sidebar'), 'static', 'src',
                                'js', 'pb_sidebar.js'))
        self.assertIn('"graduation-cap":', js)

    def test_t3_the_hub_registers_its_lens_gates_and_registry(self):
        src = _read(os.path.join(HERE, 'static', 'src', 'js',
                                 'learning_hub.js'))
        self.assertIn('export const LEARNING_LENSES = "pb_learning_hub_lens";',
                      src)
        self.assertIn('registry.category("actions").add("pb_learning_hub"',
                      src)
        self.assertIn('registry.category(HUB_LENS_GATES).add("pb_learning_hub"',
                      src)
        self.assertIn('defaultLens: "overview"', src)
        # W21: the lens list is resolved once in setup(), never in a getter.
        self.assertIn('lenses: this.extraLenses()', src)
        self.assertNotIn('get lenses', src)

    def test_t3_every_asset_on_disk_is_in_the_bundle(self):
        manifest = ast.literal_eval(_read(os.path.join(HERE,
                                                       '__manifest__.py')))
        bundle = set(manifest['assets']['web.assets_backend'])
        on_disk = set()
        for sub in ('js', 'xml'):
            d = os.path.join(HERE, 'static', 'src', sub)
            for f in os.listdir(d):
                on_disk.add('pb_learning_hub/static/src/%s/%s' % (sub, f))
        self.assertEqual(on_disk, bundle)

    def test_t3_templates_parse_and_js_has_no_python_style_concatenation(self):
        for f in os.listdir(os.path.join(HERE, 'static', 'src', 'xml')):
            ElementTree.parse(os.path.join(HERE, 'static', 'src', 'xml', f))
        for f in os.listdir(os.path.join(HERE, 'static', 'src', 'js')):
            src = _read(os.path.join(HERE, 'static', 'src', 'js', f))
            self.assertFalse(_RE_ADJACENT_STRINGS.search(src), f)

    def test_t3_no_user_visible_string_says_odoo_or_carries_an_emoji(self):
        visible = []
        for sub in ('js', 'xml'):
            d = os.path.join(HERE, 'static', 'src', sub)
            for f in os.listdir(d):
                visible += re.findall(r'_t\("([^"]*)"\)',
                                      _read(os.path.join(d, f)))
        for f in ('views/pb_learning_hub_action.xml', 'data/pb_sidebar.xml'):
            body = re.sub(r'<!--.*?-->', '', _read(os.path.join(HERE, f)),
                          flags=re.S)
            visible += re.findall(r'<field name="name">([^<]*)<', body)
        manifest = ast.literal_eval(_read(os.path.join(HERE,
                                                       '__manifest__.py')))
        visible += [manifest['name'], manifest['summary'],
                    manifest['description'].strip().splitlines()[0]]
        for po in re.findall(r'msgstr "([^"]*)"',
                             _read(os.path.join(HERE, 'i18n', 'vi_VN.po'))):
            visible.append(po)
        for s in visible:
            self.assertNotIn('odoo', s.lower(), s)
            self.assertFalse(_RE_EMOJI.search(s), s)

    def test_t3_every_word_has_its_vietnamese(self):
        po = _read(os.path.join(HERE, 'i18n', 'vi_VN.po'))
        for word, vi in (('Learning', 'Học tập'),
                         ('Courses, tests and certificates',
                          'Khóa học, bài kiểm tra và chứng chỉ')):
            self.assertIn('msgid "%s"\nmsgstr "%s"' % (word, vi), po)
        # A11: every entry starts with its module line.
        for block in po.split('\n\n')[1:]:
            if 'msgid' in block:
                self.assertTrue(block.startswith('#. module: pb_learning_hub'),
                                block)

    def test_t3_training_registers_into_learning_and_not_talent(self):
        if not self._installed('pb_training'):
            return
        src = _read(os.path.join(get_module_path('pb_training'), 'static',
                                 'src', 'js', 'training_palette.js'))
        self.assertIn('registry.category(LEARNING_LENSES)', src)
        self.assertNotIn('TALENT_LENSES', src)
        depends = ast.literal_eval(_read(os.path.join(
            get_module_path('pb_training'), '__manifest__.py')))['depends']
        self.assertIn('pb_learning_hub', depends)
        self.assertNotIn('pb_talent_hub', depends)
