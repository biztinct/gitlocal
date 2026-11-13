"""WF2 P2b: run this phase's transactional tests in the selected database.

    odoo-bin shell -d <db> --no-http < tools/workflow_studio/run_p2b.py
    P2B_TESTS=odoo.addons.pb_pay.tests.test_wf2p2b_pay odoo-bin shell …

Rolls back. Prints one WORKFLOW_TEST_RESULT line (same shape as run_suite.py).
"""
import importlib
import json
import os
import unittest

from odoo.tools import config

config['test_enable'] = True
DEFAULT = [
    'odoo.addons.biz_approval_workflow.tests.test_wf2p2b_single_notice',
    'odoo.addons.pb_pay.tests.test_wf2p2b_pay',
    'odoo.addons.pb_hr_workforce.tests.test_wf2p2b_overtime',
    'odoo.addons.pb_contract_lifecycle.tests.test_wf2p2b_extension',
    'odoo.addons.pb_orgchart.tests.test_wf2p2b_orgplan',
    'odoo.addons.pb_offboarding.tests.test_wf2p2b_resignation',
    'odoo.addons.pb_goals.tests.test_wf2p2b_goals',
    'odoo.addons.pb_timeoff.tests.test_wf2p2b_timeoff',
    'odoo.addons.pb_me_expense.tests.test_wf2p2b_expense_messages',
    'odoo.addons.pb_hiring.tests.test_wf2p2b_joining',
]
names = [n for n in (os.environ.get('P2B_TESTS') or '').split(',') if n] or DEFAULT
suite = unittest.TestSuite()
missing = []
for name in names:
    try:
        module = importlib.import_module(name)
    except ImportError as exc:
        missing.append('%s (%s)' % (name, exc))
        continue
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
result = unittest.TextTestRunner(verbosity=2).run(suite)
print('P2B_MISSING=' + json.dumps(missing))
print('WORKFLOW_TEST_RESULT=' + json.dumps({
    'tests': result.testsRun, 'successful': result.wasSuccessful() and not missing,
    'failures': len(result.failures), 'errors': len(result.errors)}))
env.cr.rollback()
