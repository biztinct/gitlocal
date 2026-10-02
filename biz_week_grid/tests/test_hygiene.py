# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Dependency-hygiene tests for the generic WeekGrid.

biz_week_grid is a REUSABLE front-end-only engine (C18.1): it must carry zero
product dependencies and define no server models, so any app — HR, timesheets,
roster hours — can consume <WeekGrid/> without pulling Payobook/HR in. These
tests fail loudly the day someone adds a Python model or an HR dependency.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWeekGridHygiene(TransactionCase):

    def test_01_depends_only_on_web(self):
        mod = self.env['ir.module.module'].search(
            [('name', '=', 'biz_week_grid')], limit=1)
        self.assertTrue(mod, 'biz_week_grid module record not found')
        self.assertEqual(mod.state, 'installed')
        self.assertEqual(mod.dependencies_id.mapped('name'), ['web'])

    def test_02_defines_no_server_models(self):
        # a front-end-only module owns no ir.model records
        owned = self.env['ir.model.data'].search([
            ('module', '=', 'biz_week_grid'), ('model', '=', 'ir.model')])
        self.assertFalse(
            owned, 'biz_week_grid must not define server models: %s'
            % owned.mapped('name'))
