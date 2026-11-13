# -*- coding: utf-8 -*-
"""SCHEMECTX P1 — every scheme card says what it pays in.

The Scope panel used to read one currency for the whole screen, taken from the
company, so picking an India scheme left "VND" sitting there. Each card now
carries its own money and the panel follows the card.

Test number 6 of the phase handover.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxWizardCurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['pb.payrun.wizard']
        cls.Config = cls.env['hr.formula.config']
        cls.india = cls.Config.create({
            'name': 'SC Wiz India', 'code': 'SCWIZIN',
            'country_code': 'IN', 'state': 'active',
            'company_id': cls.env.company.id,
        })
        cls.viet = cls.Config.create({
            'name': 'SC Wiz Viet', 'code': 'SCWIZVN',
            'country_code': 'VN', 'state': 'active',
            'company_id': cls.env.company.id,
        })

    # -- 6 --------------------------------------------------------------
    def test_06_every_card_carries_its_money(self):
        cards = self.Wizard._scheme_cards()
        self.assertTrue(cards, 'no scheme cards on this database')
        for card in cards:
            self.assertIn('currency', card,
                          'a scheme card lost its currency')
            money = card['currency']
            self.assertTrue(money.get('name'),
                            'card %s has no currency name' % card['id'])
            self.assertTrue(money.get('symbol'))
            self.assertIn(money.get('position'), ('before', 'after'))
        by_id = {c['id']: c['currency'] for c in cards}
        self.assertEqual(by_id[self.india.id]['name'], 'INR')
        self.assertEqual(by_id[self.india.id]['symbol'],
                         self.india.currency_id.symbol or 'INR')
        self.assertEqual(by_id[self.viet.id]['name'], 'VND')

    def test_06b_the_payload_opens_on_a_currency_dict(self):
        """The Scope panel's opening answer is a dict, never a bare name."""
        defaults = self.Wizard.get_defaults()
        money = defaults.get('currency')
        self.assertIsInstance(money, dict,
                              'the wizard payload still ships a bare currency name')
        self.assertTrue(money.get('name'))
        self.assertTrue(money.get('symbol'))
