# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Static gates for the Patterns lens (WDGAP S5-C).

S1  the lens joins Mission Control through the registry, spelled as
    pb_mission exports it, and never imports pb_mission back
S2  the palette rows are XMLID doors with a presence probe
S3  no "Odoo" in anything a person can read (templates, labels, msgstr)
S4  vi_VN and id_ID translations parse and carry every screen sentence
S5  the Schedule is extended by inheritance only (no pb_schedule file edit)
"""

import os
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = os.path.dirname(HERE)


def _src(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as f:
        return f.read()


def _code(text):
    """JS without comments, so a word in a comment proves nothing."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'(^|\s)//[^\n]*', r'\1', text)


@tagged('post_install', '-at_install', 'wdgap_s5c')
class TestPatternsStatic(TransactionCase):

    def _mission(self):
        path = os.path.join(ADDONS, 'pb_mission', 'static', 'src', 'js', 'pb_mission.js')
        if not os.path.exists(path):
            self.skipTest('pb_mission is not on this addons path')
        return _code(_src(path))

    def test_s1_the_lens_joins_through_the_registry(self):
        match = re.search(r'export const MISSION_LENSES = "([^"]+)"', self._mission())
        self.assertTrue(match, 'pb_mission must export MISSION_LENSES')
        mine = _code(_src(HERE, 'static', 'src', 'js', 'patterns_palette.js'))
        self.assertIn('const MISSION_LENSES = "%s"' % match.group(1), mine,
                      'the two spellings of the lens registry have drifted')
        self.assertIn('registry.category(MISSION_LENSES).add("patterns"', mine)
        for name in os.listdir(os.path.join(HERE, 'static', 'src', 'js')):
            self.assertNotIn('@pb_mission/', _code(_src(HERE, 'static', 'src', 'js', name)),
                             '%s must not import pb_mission' % name)

    def test_s2_palette_rows_are_xmlid_doors_with_a_probe(self):
        mine = _code(_src(HERE, 'static', 'src', 'js', 'patterns_palette.js'))
        rows = re.findall(r'palette\.add\("([a-z_]+)"', mine)
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(mine.count('requires: "pb_shift_patterns"'), len(rows))
        self.assertEqual(mine.count('xmlid: "pb_mission.action_pb_workforce"'), len(rows))
        self.assertIn('lensKey: "pb_shell_lens"', mine)
        self.assertNotIn('tag: "pb_workforce"', mine)

    def test_s3_no_vendor_name_on_screen(self):
        bad = re.compile(r'odoo', re.I)
        allowed = re.compile(r'@odoo-module|@odoo/owl|</?odoo[ >]|odoo-javascript|odoo-python|'
                             r'from odoo|import odoo|odoo\.')
        for folder in ('static', 'views', 'security'):
            for root, _dirs, files in os.walk(os.path.join(HERE, folder)):
                for name in files:
                    for n, line in enumerate(_src(root, name).splitlines(), 1):
                        if bad.search(allowed.sub('', line)):
                            self.fail('%s:%s names the vendor: %s' % (name, n, line.strip()))
        for po in ('vi_VN.po', 'id_ID.po'):
            with open(os.path.join(HERE, 'i18n', po), 'rb') as f:
                for row in PoFileReader(f):
                    self.assertNotRegex(row['value'] or '', bad, po)
        man = _src(HERE, '__manifest__.py')
        name = re.search(r"'name': '([^']+)'", man).group(1)
        summary = re.search(r"'summary': ([^\n]+\n[^\n]+)", man).group(1)
        self.assertNotRegex(name + summary, bad)

    def test_s4_translations_parse_and_cover_the_screen(self):
        for po in ('vi_VN.po', 'id_ID.po'):
            with open(os.path.join(HERE, 'i18n', po), 'rb') as f:
                rows = list(PoFileReader(f))
            self.assertGreater(len(rows), 50, po)
            msgids = {r['src'] for r in rows if r['value']}
            for must in ('Shift patterns', 'Make drafts', 'Make draft shifts',
                         'Patterns', 'Every day the patterns ask for is covered.'):
                self.assertIn(must, msgids, '%s lacks "%s"' % (po, must))

    def test_s5_the_schedule_is_extended_not_edited(self):
        patch = _src(HERE, 'static', 'src', 'xml', 'schedule_patch.xml')
        self.assertIn('t-inherit="pb_schedule.PbSchedule"', patch)
        self.assertIn('t-inherit-mode="extension"', patch)
        js = _code(_src(HERE, 'static', 'src', 'js', 'schedule_patch.js'))
        self.assertIn('patch(PbSchedule.prototype', js)
