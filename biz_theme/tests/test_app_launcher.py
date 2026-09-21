# -*- coding: utf-8 -*-
"""The app launcher earns its place only when there is a choice to make."""

import os

from lxml import etree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSingleAppLauncher(TransactionCase):

    def test_navbar_calls_the_launcher_only_for_more_than_one_app(self):
        path = os.path.join(get_module_path('biz_theme'),
                            'static/src/webclient/apps_menu.xml')
        tree = etree.parse(path)
        nodes = tree.xpath(
            "//t[@t-inherit='web.NavBar']//t[@t-call='web.NavBar.AppsMenu']")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].get('t-if'),
                         'menuService.getApps().length > 1')
