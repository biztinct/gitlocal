# -*- coding: utf-8 -*-
"""DOCSTUDIO close Z item 2 (owner ruling 2026-11-26): the three PDFs whose
page designs were never written are hidden, not deleted.

Run: odoo-bin -u pb_hr_payroll_analytics --test-enable --test-tags /pb_hr_payroll_analytics
"""
from odoo.tests import TransactionCase, tagged

REPORTS = {
    'action_report_personnel_costs': 'hr.analytics.personnel.costs',
    'action_report_statutory_contrib': 'hr.analytics.statutory.contrib',
    'action_report_headcount': 'hr.analytics.headcount',
}


@tagged('post_install', '-at_install', 'pb_hr_payroll_analytics')
class TestHiddenPdfs(TransactionCase):

    def test_01_actions_kept_but_on_no_print_menu(self):
        for xid, model in REPORTS.items():
            with self.subTest(report=xid):
                rep = self.env.ref('pb_hr_payroll_analytics.%s' % xid, raise_if_not_found=False)
                self.assertTrue(rep, 'the xml id stays so nothing naming it breaks')
                self.assertEqual(rep.model, model)
                self.assertFalse(rep.binding_model_id, 'no Print menu entry')

    def test_02_record_pages_render_without_them(self):
        for xid, model in REPORTS.items():
            with self.subTest(model=model):
                rep = self.env.ref('pb_hr_payroll_analytics.%s' % xid)
                views = self.env[model].get_views([(False, 'list'), (False, 'form')],
                                                  {'toolbar': True})
                for kind in ('list', 'form'):
                    toolbar = views['views'][kind].get('toolbar') or {}
                    printed = [a.get('id') for a in toolbar.get('print', [])]
                    self.assertNotIn(rep.id, printed, '%s %s' % (model, kind))

    def test_03_dashboard_has_no_export_button(self):
        wizard = self.env.ref('pb_hr_payroll_analytics.action_hr_analytics_export_wizard')
        self.assertTrue(wizard, 'the export window action is kept')
        arch = self.env['hr.analytics.dashboard'].get_views(
            [(self.env.ref('pb_hr_payroll_analytics.view_hr_analytics_dashboard_form').id, 'form')]
        )['views']['form']['arch']
        self.assertNotIn('name="%s"' % wizard.id, arch)
        self.assertIn('action_refresh_all_analytics', arch, 'the rest of the header renders')
