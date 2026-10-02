# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# DISABLED — and this file is the only place the reason can be recorded.
#
# `test_payslip_flow.py` is an Odoo-11 leftover that has never run on 19, and
# it did not fail quietly: importing it raised
#
#     ModuleNotFoundError: No module named 'odoo.addons.om_om_hr_payroll'
#
# INSIDE `odoo/tests/loader.py::get_test_modules`, which runs before any test
# executes and over every installed module. So a single unimportable test
# package took down the ENTIRE test run of the database — every pb_* suite in
# this repo, whatever `--test-tags` asked for — with exit 255 and a traceback
# that names a module nobody has ever heard of. That is why nothing in this
# repository could be tested end to end until Workforce P7 tried.
#
# The cause is a doubled-prefix find/replace (`om_hr_payroll` -> `om_om_hr_-
# payroll`) that also hit `common.py`'s six xmlids, plus Odoo-11 API this
# version does not have (`odoo.tools.test_reports`, `report.render()`). The
# suite cannot be repaired by fixing the import: it would then import cleanly
# and fail on six missing xmlids and a removed method. Repairing it properly is
# a payroll-engine job with its own review, not something a housekeeping phase
# gets to do on the way past.
#
# It is therefore taken out of the loader rather than "fixed" into a different
# kind of red. Nothing is deleted — `test_payslip_flow.py` and `common.py` stay
# on disk for whoever ports them — and restoring the suite is one line, once
# those tests describe this decade's payslip flow.
#
# from . import test_payslip_flow
