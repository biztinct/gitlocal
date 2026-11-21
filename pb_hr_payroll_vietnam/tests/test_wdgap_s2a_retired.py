# -*- coding: utf-8 -*-
"""WDGAP S2-A test 10 — the Vietnamese false-claim doors are retired.

The tax report wizard said "Vietnam tax report has been generated
successfully" and made nothing; the dashboard's social-insurance button opened
a model that does not exist. Each now says plainly that nothing was made and
where the real one is; none of them claims a file. The other countries'
wizards (SG/TH/KH/MY) live in modules that cannot be installed on this
version; their source is checked instead.
"""
import os
import re

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CLAIMS = re.compile(r'(generated|imported) successfully', re.I)


@tagged('post_install', '-at_install', 'wdgap_s2a')
class TestS2ARetiredDoors(TransactionCase):

    def _says_nothing_was_made(self, call):
        with self.assertRaises(UserError) as caught:
            call()
        message = str(caught.exception.args[0] if caught.exception.args else caught.exception)
        self.assertRegex(message, r'nothing was (made|imported)')
        self.assertNotRegex(message, CLAIMS)

    def test_s2a_10a_vietnam_doors(self):
        wizard = self.env['vietnam.tax.report.wizard'].create({})
        self._says_nothing_was_made(wizard.action_generate_report)
        employee = self.env['hr.employee'].create({'name': 'DEMO S2A Retired'})
        self._says_nothing_was_made(employee.action_vietnam_generate_tax_report)
        Dashboard = self.env.get('vietnam.payroll.dashboard')
        if Dashboard is not None:
            dash = Dashboard.new({})
            self._says_nothing_was_made(dash.action_generate_vietnam_tax_report)
            self._says_nothing_was_made(dash.action_generate_vietnam_social_insurance_report)

    def test_s2a_10b_other_countries_claim_nothing_in_their_source(self):
        doors = {
            'pb_hr_payroll_singapore/wizards/cpf_submission_wizard.py': 'action_generate_cpf_file',
            'pb_hr_payroll_thailand/wizards/social_security_wizard.py': 'action_generate_ssf_file',
            'pb_hr_payroll_cambodia/wizards/nssf_wizard.py': 'action_generate_nssf_file',
            'pb_hr_payroll_malaysia/wizards/epf_wizard.py': 'action_generate_epf_file',
            'pb_hr_payroll_malaysia/wizards/payroll_import_wizard.py': 'action_import_malaysia_data',
            'pb_hr_payroll_cambodia/wizards/payroll_import_wizard.py': 'action_import_cambodia_data',
            'pb_hr_payroll_vietnam/wizards/vietnam_tax_report_wizard.py': 'action_generate_report',
        }
        for rel, method in doors.items():
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                continue
            src = open(path, encoding='utf-8').read()
            self.assertNotRegex(src, CLAIMS, rel)
            body = re.search(r'def %s\(self[^)]*\):(.*?)(?=\n    def |\Z)' % method, src, re.S)
            self.assertTrue(body, '%s: %s missing' % (rel, method))
            self.assertIn('raise UserError', body.group(1), rel)
            self.assertNotIn('display_notification', body.group(1), rel)
