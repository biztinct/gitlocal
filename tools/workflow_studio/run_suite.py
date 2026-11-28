"""Run only this release's transactional tests against the selected Odoo DB."""
import importlib
import json
import unittest
from odoo.tools import config
config['test_enable'] = True
module = importlib.import_module('odoo.addons.pb_lifecycle.tests.test_workflow_studio')
suite = unittest.defaultTestLoader.loadTestsFromModule(module)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print('WORKFLOW_TEST_RESULT='+json.dumps({'tests': result.testsRun, 'successful': result.wasSuccessful(), 'failures': len(result.failures), 'errors': len(result.errors)}))
env.cr.rollback()
