#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# DISABLED — the sibling of om_hr_payroll's dead suite, same story, same cost.
#
# `test_hr_payroll_account.py` opens with
#
#     from odoo.modules.module import get_module_resource
#
# which was removed from Odoo years ago. As with om_hr_payroll, the import
# happens inside `odoo/tests/loader.py::get_test_modules` — before any test
# runs, over every installed module, and regardless of `--test-tags` — so this
# one file was enough to exit the whole run at 255 and take every other suite on
# the database with it. Workforce P7 hit them one after the other while trying
# to produce its own test evidence.
#
# Not deleted and not "fixed": swapping the import would leave an Odoo-11 test
# body running against a 19 payroll-account bridge, which is a different kind of
# red and a payroll-engine job with its own review. The file stays on disk; the
# line below is what to restore once it has been ported.
#
# from . import test_hr_payroll_account
