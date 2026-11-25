# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WFSETUP P10b — "Built-in extra hours count: On / Off" (owner ruling R12,
proposal WFSETUP_P10A §7, §9 case 16)."""

import json
from datetime import datetime, timedelta

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from .test_golive import GoLiveFixture


@tagged('post_install', '-at_install', 'wfsetup', 'wfsetup_p10b')
class TestP10bExtraHours(GoLiveFixture, TransactionCase):

    def _rules(self):
        return self.env['pb.workforce.setup'].with_user(self.manager).with_company(self.company)

    def test_01_off_removes_and_on_restores_exactly(self):
        studio = self._rules()
        rulesets = studio._extra_rulesets()
        before = sorted((r.ruleset_id.id, r.name, r.base_off, r.timing_type, r.quantity_period,
                         r.expected_hours_from_contract, r.paid, r.amount_rate)
                        for r in rulesets.mapped('rule_ids'))
        self.assertTrue(before, 'the stock default rules are expected on a fresh database')
        state = studio.rules()['extra_hours']
        self.assertTrue(state['on'])
        res = studio.extra_hours_off()
        self.assertEqual(res['removed'], len(before))
        self.assertFalse(rulesets.mapped('rule_ids'))
        self.assertFalse(res['rules']['extra_hours']['on'])
        self.assertTrue(res['rules']['extra_hours']['saved'])
        # with no rules the stock count makes no extra-hours lines
        emp = self.people[0]
        start = datetime.combine(self.monday - timedelta(days=7), datetime.min.time()).replace(hour=1)
        att = self.env['hr.attendance'].create({'employee_id': emp.id, 'check_in': start,
                                                'check_out': start + timedelta(hours=14)})
        Line = self.env.get('hr.attendance.overtime.line')
        if Line is not None:
            self.assertFalse(Line.sudo().search([('employee_id', '=', emp.id)]))
        res = studio.extra_hours_on()
        self.assertEqual(res['restored'], len(before))
        after = sorted((r.ruleset_id.id, r.name, r.base_off, r.timing_type, r.quantity_period,
                        r.expected_hours_from_contract, r.paid, r.amount_rate)
                       for r in rulesets.mapped('rule_ids'))
        self.assertEqual(before, after)
        self.assertFalse(self.company.sudo().pb_wfs_extra_hours_saved)
        self.assertTrue(att.exists())

    def test_02_officer_refused(self):
        with self.assertRaises(AccessError):
            self.env['pb.workforce.setup'].with_user(self.officer).with_company(self.company).extra_hours_off()
