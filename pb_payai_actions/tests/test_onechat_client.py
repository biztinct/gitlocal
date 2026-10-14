# -*- coding: utf-8 -*-
"""ONECHAT OC2 — the one chat's browser halves, run in node.

`tests/js/onechat_oc2.test.mjs` loads the REAL drawer (pb_learn coach.js with
its runtime and glossary), the REAL embedded chat (pb_payroll_ai_insights) and
the REAL PayAI patches (chat_patch.js, coach_patch.js), wired the way the
browser wires them, with only the server stubbed. It covers handover §11 2.3
(spoken provenance and the send kwargs), 2.4 (the route dispatch table), 2.5
(card chips bypass the router), 2.6 (a language flip re-renders past turns),
2.7 (close/reopen keeps answers; a fresh page gets markers) and 2.8 (the
queue), plus the Escape ladder, the More menu and the figures rule (Q2).

The static facts sit in pb_learn `tests/test_onechat_ui.py`.
"""
import os
import re
import shutil
import subprocess

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.abspath(__file__))
JS_DIR = os.path.join(HERE, 'js')


@tagged('post_install', '-at_install', 'payai', 'onechat')
class TestOneChatClient(TransactionCase):

    def test_01_the_one_chat_runs_in_node(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed here; run '
                          'pb_payai_actions/tests/js/onechat_oc2.test.mjs by hand.')
        version = subprocess.run([node, '--version'], capture_output=True, text=True,
                                 check=False).stdout.strip()
        major = re.match(r'v(\d+)', version)
        if not major or int(major.group(1)) < 18:
            self.skipTest('node %s is too old for the one-chat test (18+: Blob, btoa).' % version)
        root = os.path.dirname(get_module_path('pb_payai_actions'))
        for module in ('pb_learn', 'pb_payroll_ai_insights', 'pb_hub'):
            if not os.path.isdir(os.path.join(root, module)):
                self.skipTest('%s is not beside pb_payai_actions on this addons path' % module)
        env = dict(os.environ, PB_SRC_ROOT=root)
        out = subprocess.run(
            [node, os.path.join(JS_DIR, 'onechat_oc2.test.mjs')],
            capture_output=True, text=True, timeout=180, env=env, check=False)
        self.assertEqual(out.returncode, 0, out.stdout[-4000:] + out.stderr[-2000:])
        self.assertRegex(out.stdout, r'\d+ passed, 0 failed')
