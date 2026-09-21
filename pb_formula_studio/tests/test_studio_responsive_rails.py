# -*- coding: utf-8 -*-
"""Regression coverage for Formula Studio's responsive card-view rails."""
import os

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStudioResponsiveRails(TransactionCase):

    def test_card_rails_follow_viewport_and_keep_editor_flexible(self):
        path = os.path.join(
            get_module_path('pb_formula_studio'),
            'static', 'src', 'scss', 'studio.scss',
        )
        with open(path, encoding='utf-8') as source:
            scss = source.read()

        self.assertIn('clamp(280px, 20vw, 380px)', scss)
        self.assertIn('minmax(0, 1fr)', scss)
        self.assertIn('clamp(340px, 22vw, 420px)', scss)

    def test_small_screens_still_replace_rails_with_drawers(self):
        path = os.path.join(
            get_module_path('pb_formula_studio'),
            'static', 'src', 'scss', 'studio_responsive.scss',
        )
        with open(path, encoding='utf-8') as source:
            responsive = source.read()

        self.assertIn('@include biz-down($biz-bp-md)', responsive)
        self.assertIn('.pbfs-work:not(.pbfs-work--full)', responsive)
        self.assertIn('grid-template-columns: 1fr', responsive)
        self.assertIn('@include pbfs-drawer-panels', responsive)
