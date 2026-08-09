# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTenantOverride(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Override = cls.env['learn.tenant.override']
        cls.company = cls.env.company
        cls.other = cls.env['res.company'].create({'name': 'Second Company (test)'})

    def test_01_defaults_are_shipped_and_resolve(self):
        declared = self.Override.declared_keys()
        self.assertTrue(declared, "no tenant slots shipped at all")
        tokens = self.Override.resolved_tokens()
        for key in declared:
            self.assertIn(key, tokens)
            self.assertTrue(tokens[key]['en'], "slot %s has no English default" % key)
            self.assertTrue(tokens[key]['vi'], "slot %s has no Vietnamese value" % key)

    def test_02_override_wins_over_default(self):
        key = 'hrTierName'
        before = self.Override.resolved_tokens()[key]['en']
        self.Override.create({
            'key': key, 'value': 'People Ops check', 'company_id': self.company.id,
        })
        after = self.Override.resolved_tokens()[key]['en']
        self.assertNotEqual(before, after)
        self.assertEqual(after, 'People Ops check')

    def test_03_unknown_key_is_refused(self):
        """An override may only FILL a slot, never introduce one.

        Without this the typo is inert: the admin sees a row they filled in,
        the learner sees the shipped default, and nothing says why.
        """
        with self.assertRaises(ValidationError):
            self.Override.create({
                'key': 'hrTierNamee',   # one letter out
                'value': 'anything',
                'company_id': self.company.id,
            })

    def test_04_one_companys_override_is_invisible_to_another(self):
        key = 'payrollSupportContact'
        self.Override.create({
            'key': key, 'value': 'the Hanoi payroll desk', 'company_id': self.other.id,
        })
        mine = self.Override.with_company(self.company).resolved_tokens()[key]['en']
        theirs = self.Override.with_company(self.other).resolved_tokens()[key]['en']
        self.assertNotEqual(mine, 'the Hanoi payroll desk')
        self.assertEqual(theirs, 'the Hanoi payroll desk')

    def test_05_overrides_cannot_carry_prose(self):
        """The hard rule, asserted rather than trusted.

        Slots are short facts — a pay day, a tier name, a cut-off. If one ever
        grows into a sentence, the next step is a tenant editing a lesson, and
        then no check can guard any of them.
        """
        long_slots = [
            (r.key, len(r.value or ''))
            for r in self.Override.sudo().search([('company_id', '=', False)])
            if len(r.value or '') > 60
        ]
        self.assertFalse(long_slots, "Tenant slots long enough to be prose: %s" % long_slots)
