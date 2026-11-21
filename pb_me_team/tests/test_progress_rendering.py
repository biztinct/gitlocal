"""Render the installed XML, since module import processes percent escapes."""
from copy import deepcopy
from lxml import etree, html
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTeamProgressRendering(TransactionCase):
    def test_installed_percentage_bars_render_in_each_language(self):
        for lang in ('en_US', 'vi_VN', 'id_ID'):
            if not self.env['res.lang'].search_count([('code', '=', lang), ('active', '=', True)]):
                continue
            view = self.env.ref('pb_me_team.portal_my_team').with_context(lang=lang)
            tree = etree.fromstring(view.arch_db.encode())
            nodes = tree.xpath("//span[contains(@class,'pbmt-progress-bar')]/i | //span[contains(@class,'pbmt-hrs-bar')]/* | //span[contains(@t-att-class,'pbmt-meter')]/i")
            self.assertEqual(len(nodes), 4)
            fragment = etree.Element('div')
            for node in nodes:
                clone = deepcopy(node)
                clone.attrib.pop('t-if', None)
                fragment.append(clone)
            probe = self.env['ir.ui.view'].create({
                'name': 'Installed team progress probe', 'type': 'qweb',
                'arch_db': etree.tostring(fragment, encoding='unicode')})
            for share in (0, 50, 100):
                with self.subTest(lang=lang, share=share):
                    output = self.env['ir.qweb'].with_context(lang=lang)._render(probe.id, {
                        'r': {'done': share, 'total': 100, 'share': share},
                        'h': {'share': share, 'mark': share, 'planned': 100}})
                    styles = html.fromstring(str(output)).xpath('//*[@style]/@style')
                    self.assertEqual(styles, ['width: %s%%' % share, 'width: %s%%' % share,
                                              'left: %s%%' % share, 'width: %s%%' % share])
