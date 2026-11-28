import ast
import re
from pathlib import Path

import polib
from lxml import etree
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from .test_phone import TAG

ROOT = Path(get_module_path('pb_joining'))
BUNDLE = ROOT / 'static' / 'src'


def phrases():
    for folder in ('controllers', 'models'):
        for path in sorted((ROOT / folder).glob('*.py')):
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                name = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
                if (
                    name == '_'
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    yield node.args[0].value, 'python', path
    for path in sorted(BUNDLE.rglob('*.js')):
        for match in re.finditer(r"""\b_t\(\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""", path.read_text()):
            yield ast.literal_eval(match[1]), 'javascript', path


@tagged(*TAG)
class TestStatic(TransactionCase):
    def test_t65_brand_on_every_surface(self):
        manifest = ast.literal_eval((ROOT / '__manifest__.py').read_text())
        texts = [manifest['name'], manifest['summary']]
        texts.extend(term for term, lang, path in phrases())
        for directory in (ROOT / 'data', ROOT / 'views', BUNDLE / 'xml'):
            for path in directory.glob('*.xml'):
                tree = etree.parse(str(path))
                texts.extend(tree.xpath('//text() | //@title | //@alt | //@aria-label | //@placeholder'))
        for path in (ROOT / 'i18n').glob('*.po'):
            texts.extend(e.msgstr for e in polib.pofile(str(path)))
        self.assertFalse([s for s in texts if 'odoo' in s.lower()])

    def test_t66_icons_belong_to_shared_registry(self):
        shared = (Path(get_module_path('pb_import_kit')) / 'static/src/js/import_icons.js').read_text()
        known = set(re.findall(r'^    (\w+):', shared, re.M))
        extensions = (BUNDLE / 'js/joining_icons.js').read_text()
        for key, alias in re.findall(r'IC\.(\w+) \?\?= IC\.(\w+)', extensions):
            self.assertIn(alias, known)
        known.update(re.findall(r'IC\.(\w+) \?\?=', extensions))
        icons = {row[2] for row in self.env['pb.joining']._section_info()}
        for path in [*BUNDLE.rglob('*.js'), *BUNDLE.rglob('*.xml')]:
            icons.update(re.findall(r"""\bic\(\s*['"](\w+)['"]""", path.read_text()))
            icons.update(re.findall(r"""\bicon:\s*['"](\w+)['"]""", path.read_text()))
        for country in ('VN', 'ID', 'IN', 'SG'):
            icons.update(item['icon'] for item in self.env['pb.new.hire']._detail_items(country, 'DEMO'))
        board = ast.parse((ROOT/'models/board_review.py').read_text())
        for call in ast.walk(board):
            if isinstance(call, ast.Call) and getattr(call.func, 'id', '') in ('choice', 'chip'):
                value = call.args[2 if call.func.id == 'choice' else 1]
                if isinstance(value, ast.Constant):
                    icons.add(value.value)
        self.assertFalse(icons - known, str(icons - known))
        self.assertIn('ic(element.dataset.joiningIcon', (BUNDLE / 'js/phone_icons.js').read_text())

    def test_t67_no_emoji(self):
        emoji = re.compile('[\U0001f1e6-\U0001f1ff\U0001f300-\U0001faff\u2600-\u27bf]\ufe0f?|\ufe0f')
        for path in ROOT.rglob('*'):
            if (
                path.suffix not in ('.py', '.js', '.xml', '.scss', '.po')
                or 'tests' in path.relative_to(ROOT).parts
            ):
                continue
            self.assertIsNone(emoji.search(path.read_text()), str(path))

    def test_t68_translated_literals_and_locations(self):
        catalogues = [
            polib.pofile(str(ROOT / 'i18n' / name)) for name in ('pb_joining.pot', 'vi_VN.po', 'id_ID.po')
        ]
        for term, family, path in phrases():
            occurrence = ('code:addons/pb_joining/' + str(path.relative_to(ROOT)), '0')
            for catalog in catalogues:
                entry = catalog.find(term)
                self.assertTrue(entry is not None, (term, path.name))
                self.assertIn('module: pb_joining', entry.comment)
                self.assertIn('odoo-' + family, entry.comment, term)
                self.assertIn(occurrence, entry.occurrences, term)
                if catalog is not catalogues[0]:
                    self.assertTrue(entry.msgstr.strip(), term)
        for entry in catalogues[0]:
            for catalog in catalogues[1:]:
                translated = catalog.find(entry.msgid)
                self.assertTrue(translated and translated.msgstr.strip(), entry.msgid)
