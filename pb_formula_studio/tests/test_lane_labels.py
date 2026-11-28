# -*- coding: utf-8 -*-
"""LEARNREV P0 T4 (G21, ledger LR2) — every lane the server emits has words.

The Component treatment board prints `LANE_LABELS[lane] || lane`: a lane the
server returns that has no key in LANE_LABELS reaches the screen as the raw
key ("calculated"). The convention is "the keys match `_value_kind_lane`
exactly"; this test is what keeps it.
"""
import inspect
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLaneLabels(TransactionCase):

    def _js_lane_keys(self):
        path = os.path.join(get_module_path('pb_formula_studio'),
                            'static', 'src', 'js', 'component_treatment.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        block = re.search(r'const LANE_LABELS = \{(.*?)\n\};', src, re.S)
        self.assertTrue(block, 'LANE_LABELS not found in component_treatment.js')
        return set(re.findall(r'^\s*([a-z_]+)\s*:\s*_t\(', block.group(1), re.M))

    def _server_lanes(self):
        method = type(self.env['hr.formula.config'])._value_kind_lane
        src = inspect.getsource(method)
        lanes = set(re.findall(r"return\s+'([a-z_]+)'", src))
        self.assertTrue(lanes, '_value_kind_lane returns no literal lane any more')
        return lanes

    def test_01_every_server_lane_has_a_label(self):
        missing = self._server_lanes() - self._js_lane_keys()
        self.assertFalse(
            missing,
            'Lanes the server can return with no words on the board: %s' % sorted(missing))

    def test_02_calculated_reads_in_plain_words(self):
        path = os.path.join(get_module_path('pb_formula_studio'),
                            'static', 'src', 'js', 'component_treatment.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn('calculated: _t("Calculated by a formula")', src)
