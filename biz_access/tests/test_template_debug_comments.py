"""Access templates must survive Odoo's developer-mode inheritance comments."""
import json
import unittest
from pathlib import Path

from lxml import etree


class TestTemplateDebugComments(unittest.TestCase):
    XML = Path(__file__).resolve().parents[1] / 'static' / 'src' / 'xml'

    def test_inheritance_metadata_is_valid_xml_comment(self):
        # web/core/template_inheritance.js copies operation attributes verbatim
        # into a comment in debug mode. XMLSerializer permits a double hyphen,
        # but reparsing the resulting template rejects it before OWL can render.
        count = 0
        for path in sorted(self.XML.glob('*.xml')):
            for op in etree.parse(str(path)).xpath('//xpath'):
                with self.subTest(file=path.name, expr=op.get('expr')):
                    attrs = ' ; '.join(f'{key}={json.dumps(value)}' for key, value in op.attrib.items())
                    comment = f' From file: /biz_access/static/src/xml/{path.name} ; {attrs} '
                    etree.fromstring(('<t><!--' + comment + '--></t>').encode())
                    count += 1
        self.assertGreater(count, 0)

    def test_role_search_selector_still_matches_exact_original_target(self):
        board = etree.parse(str(self.XML / 'access_board.xml'))
        studio = etree.parse(str(self.XML / 'access_studio.xml'))
        exprs = studio.xpath('//xpath/@expr')
        selectors = [expr for expr in exprs if 'pbva-field-' in expr]
        self.assertEqual(len(selectors), 1)
        original = board.xpath("//div[@class='pbva-bar']/label[contains(@class, 'pbva-field--search')]")
        self.assertEqual(len(original), 1)
        self.assertEqual(board.xpath(selectors[0]), original)
