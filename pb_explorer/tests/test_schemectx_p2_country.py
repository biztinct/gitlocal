# -*- coding: utf-8 -*-
"""SCHEMECTX P2, case 14 — Country means the SCHEME's country.

A fact row carries no country of its own. It used to be read off the row's
company, so an India scheme run inside a Vietnamese company was filed under
Vietnam — which is the one thing the Country dimension exists to prevent.

The row's scheme now answers first and the company only answers for a row that
has no scheme. Both halves of the board are derived that way, because a chart
that groups one way and filters another is worse than either.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxP2Country(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Explorer = cls.env['pb.explorer']
        cls.Config = cls.env.get('hr.formula.config')
        cls.company = cls.env.company

    def test_14a_a_scheme_decides_the_country_of_its_rows(self):
        if self.Config is None:
            self.skipTest("no formula engine on this database")
        india = self.Config.create({
            'name': 'EXP2 India', 'code': 'EXP2IN', 'country_code': 'IN',
            'state': 'active', 'company_id': self.company.id})
        viet = self.Config.create({
            'name': 'EXP2 Vietnam', 'code': 'EXP2VN', 'country_code': 'VN',
            'state': 'active', 'company_id': self.company.id})
        countries = self.Explorer._scheme_countries([india.id, viet.id])
        self.assertEqual(countries.get(india.id), india.country_id.id)
        self.assertNotEqual(countries.get(india.id), countries.get(viet.id),
                            "two schemes in different countries answered the "
                            "same country")

        # the GROUPING: a row with a scheme is remapped onto the scheme's
        # country, a row without one onto its company's
        rows = [('%s:%s' % (india.id, self.company.id), 'm', 1, 100.0),
                ('0:%s' % self.company.id, 'm', 1, 50.0)]
        merged = self.Explorer._dim_remap({'dimension': 'country'}, rows)
        keys = {row[0] for row in merged}
        self.assertIn(india.country_id.id, keys,
                      "an India scheme's money did not land under India")
        self.assertIn(self.company.country_id.id or None, keys,
                      "a row with no scheme stopped following its company")
        self.assertEqual(sum(row[3] for row in merged), 150.0,
                         "money went missing in the remap")

    def test_14b_the_filter_agrees_with_the_grouping(self):
        if self.Config is None:
            self.skipTest("no formula engine on this database")
        india = self.Config.create({
            'name': 'EXP2 India Two', 'code': 'EXP2IN2', 'country_code': 'IN',
            'state': 'active', 'company_id': self.company.id})
        self.assertTrue(india.country_id, "the scheme has no country")
        found = self.Explorer._configs_for_country([india.country_id.id])
        self.assertIn(india.id, found)
        self.assertIn(india.id, self.Explorer._configs_for_country(['IN']))

        sql, params = self.Explorer._country_clause([india.country_id.id])
        self.assertIn('config_id IN', sql,
                      "the country filter still only looks at the company")
        self.assertTrue(params)
        # and the drill's aliased form addresses the two tables it really has
        sql, _params = self.Explorer._country_clause(
            [india.country_id.id], fact='fe', slip='p')
        self.assertIn('fe.config_id', sql)

    def test_14c_a_country_nothing_matches_returns_no_rows(self):
        sql, params = self.Explorer._country_clause(['ZZ'])
        self.assertIn('company_id IN', sql)
        self.assertEqual(params, [(0,)],
                         "an unmatched country quietly dropped its filter")
