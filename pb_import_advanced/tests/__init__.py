# -*- coding: utf-8 -*-
# Every name here MUST be a file that exists: the import runs inside
# `odoo/tests/loader.py::get_test_modules`, before any test executes and
# regardless of `--test-tags`, so a missing sibling exits the WHOLE run 255 and
# reports it as a circular import (see pb_hr_payroll_formula/tests/__init__.py).
from . import test_connector_cockpit
from . import test_feed_configuration
