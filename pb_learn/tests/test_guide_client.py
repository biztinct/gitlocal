# -*- coding: utf-8 -*-
"""LEARNREV P2 — the Guide panel's browser half, run in node (T1 + T2).

`tests/js/guide_panel.test.mjs` loads the REAL renderer (coach/guide_panel.js),
the REAL (i) layer (coach/field_info.js) and the REAL drawer (coach/coach.js)
with only the server stubbed, and renders the six sections from the real
Component treatment Guide (`tests/data/guide_treatment_en.json`, P1's own
output). Same runner as pb_payai_actions `test_onechat_client.py`.
"""
import os
import re
import shutil
import subprocess

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.abspath(__file__))
JS_DIR = os.path.join(HERE, 'js')


@tagged('post_install', '-at_install', 'learnrev')
class TestGuideClient(TransactionCase):

    def test_01_the_guide_panel_runs_in_node(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed here; run '
                          'pb_learn/tests/js/guide_panel.test.mjs by hand.')
        version = subprocess.run([node, '--version'], capture_output=True, text=True,
                                 check=False).stdout.strip()
        major = re.match(r'v(\d+)', version)
        if not major or int(major.group(1)) < 18:
            self.skipTest('node %s is too old for the Guide test (18+).' % version)
        root = os.path.dirname(get_module_path('pb_learn'))
        if not os.path.isdir(os.path.join(root, 'pb_hub')):
            self.skipTest('pb_hub is not beside pb_learn on this addons path')
        env = dict(os.environ, PB_SRC_ROOT=root)
        out = subprocess.run(
            [node, os.path.join(JS_DIR, 'guide_panel.test.mjs')],
            capture_output=True, text=True, timeout=180, env=env, check=False)
        self.assertEqual(out.returncode, 0, out.stdout[-4000:] + out.stderr[-2000:])
        self.assertRegex(out.stdout, r'\d+ passed, 0 failed')
