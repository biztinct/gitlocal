"""WF2 P5c: run this phase's Studio tests (or a chosen subset) in the
selected database.

    odoo-bin shell -d <db> --no-http < tools/workflow_studio/run_p5c.py
    P5C_TESTS=test_wf2p5c_t1 odoo-bin shell …      (name prefixes, comma-separated)

Rolls back. Prints one WORKFLOW_TEST_RESULT line (same shape as run_suite.py).
"""
import importlib
import json
import os
import unittest

from odoo.tools import config

config['test_enable'] = True
module = importlib.import_module('odoo.addons.pb_lifecycle.tests.test_workflow_studio')
prefixes = [p for p in (os.environ.get('P5C_TESTS') or 'test_wf2p5c_').split(',') if p]
loader = unittest.defaultTestLoader
suite = unittest.TestSuite()
for name in loader.getTestCaseNames(module.TestWorkflowStudio):
    if any(name.startswith(p) for p in prefixes):
        suite.addTest(module.TestWorkflowStudio(name))
result = unittest.TextTestRunner(verbosity=2).run(suite)
print('WORKFLOW_TEST_RESULT=' + json.dumps({
    'tests': result.testsRun, 'successful': result.wasSuccessful(),
    'failures': len(result.failures), 'errors': len(result.errors)}))
env.cr.rollback()
