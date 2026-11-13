# -*- coding: utf-8 -*-
"""SCHEMECTX P1 — a scheme pays in the money of its own country.

THE DEFECT. On the reference tenant a payroll configuration with country India
told the Run Payroll wizard its currency was VND, and every amount on the
screen carried a dong sign. The cause was one search: `res.currency` was looked
up by name with the default active filter, and base data ships every currency
but the company's own as `active=False`. INR was therefore "not found", the
code fell through to `or self.env.company.currency_id`, and the scheme was
stamped dong. Because `currency_id` is a STORED compute that depends on the
country and the country never changes again, the wrong value never healed.

WHAT IS ASSERTED:

  * the resolver finds an INACTIVE currency, and leaves it inactive — never
    activate one, that flips the multi-currency switch for every user;
  * an unmapped country falls back to what `res.country` itself says;
  * with no answer at all the scheme takes ITS OWN company's money, not the
    money of whoever happens to be looking at it;
  * `currency_by_country()` answers for every country on the picker and writes
    nothing — the guided journey calls it on every keystroke of the Country
    select.

Test numbers 1, 2, 3, 4 and 13 of the phase handover.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxCurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.Currency = cls.env['res.currency']

    def _currency(self, name):
        return self.Currency.with_context(active_test=False).search(
            [('name', '=', name)], limit=1)

    # -- 1 --------------------------------------------------------------
    def test_01_india_scheme_pays_in_rupees(self):
        """An India configuration resolves INR even though INR is inactive."""
        inr = self._currency('INR')
        self.assertTrue(inr, "base data has no INR row — fixture is wrong")
        if inr.active:
            inr.with_context(active_test=False).active = False
            self.env.flush_all()
        cfg = self.Config.create({
            'name': 'SC India', 'code': 'SCINDIA',
            'country_code': 'IN', 'state': 'draft',
        })
        self.assertEqual(cfg.currency_id.name, 'INR')
        self.assertEqual(cfg.currency_id, inr)
        # and the dict the screens format from says the same thing
        payload = cfg.scheme_currency()
        self.assertEqual(payload['name'], 'INR')
        self.assertTrue(payload['symbol'])

    # -- 2 --------------------------------------------------------------
    def test_02_nothing_was_activated(self):
        """Resolving a currency must not switch it on for the whole database."""
        inr = self._currency('INR')
        inr.with_context(active_test=False).active = False
        self.env.flush_all()
        groups_before = sorted(self.env.user.group_ids.ids)
        self.Config.create({
            'name': 'SC India 2', 'code': 'SCINDIA2',
            'country_code': 'IN', 'state': 'draft',
        })
        inr.invalidate_recordset(['active'])
        self.assertFalse(
            self._currency('INR').active,
            "the resolver activated INR — never do that (ledger rule 9)")
        self.assertEqual(sorted(self.env.user.group_ids.ids), groups_before,
                         "a group membership moved while resolving a currency")

    # -- 3 --------------------------------------------------------------
    def test_03_unmapped_country_asks_the_country(self):
        """No entry in the map → whatever `res.country` carries."""
        country = self.env['res.country'].with_context(
            active_test=False).search([('code', '=', 'FR')], limit=1)
        if not country or not country.currency_id:
            self.skipTest('this database has no France row with a currency')
        found = self.Config._currency_for_country('FR')
        self.assertEqual(found, country.currency_id)

    # -- 4 --------------------------------------------------------------
    def test_04_company_fallback_is_the_schemes_own_company(self):
        """With no country the scheme takes its OWN company's money."""
        other = self.env['res.company'].create({'name': 'SC Second Company'})
        usd = self._currency('USD')
        self.assertTrue(usd, 'base data has no USD row')
        other.currency_id = usd.id
        cfg = self.Config.create({
            'name': 'SC Fallback', 'code': 'SCFALLBK',
            'country_code': 'VN', 'state': 'draft',
            'company_id': other.id,
        })
        # Country wins while there is one.
        self.assertEqual(cfg.currency_id.name, 'VND')
        self.assertNotEqual(self.env.company.currency_id, usd,
                            'fixture is degenerate — pick another currency')
        # With no country there is nothing to resolve, and the record's OWN
        # company answers — not `env.company`, which is still the main one
        # here. `country_code` is required on the table, so this is exercised
        # on an in-memory record, which is exactly where the compute runs.
        blank = self.Config.new({'company_id': other.id})
        self.assertFalse(blank.country_code)
        self.assertEqual(blank.currency_id, usd)

    # -- 5 --------------------------------------------------------------
    def test_05_stored_rows_are_healed(self):
        """A row stamped with the wrong money is re-stamped; a right one is not."""
        india = self.Config.create({
            'name': 'SC Heal India', 'code': 'SCHEALIN',
            'country_code': 'IN', 'state': 'draft',
        })
        viet = self.Config.create({
            'name': 'SC Heal Viet', 'code': 'SCHEALVN',
            'country_code': 'VN', 'state': 'draft',
        })
        self.env.flush_all()
        vnd = self._currency('VND')
        # Put the defect back, underneath the ORM, exactly as the live rows
        # carried it.
        self.env.cr.execute(
            "UPDATE hr_formula_config SET currency_id=%s WHERE id=%s",
            (vnd.id, india.id))
        india.invalidate_recordset(['currency_id'])
        self.assertEqual(india.currency_id, vnd, 'fixture did not take')
        viet_before = viet.currency_id

        # The two lines the upgrade script runs, verbatim.
        configs = self.Config.with_context(active_test=False).search([])
        configs._compute_currency_id()
        configs.flush_recordset(['currency_id'])

        india.invalidate_recordset(['currency_id'])
        viet.invalidate_recordset(['currency_id'])
        self.assertEqual(india.currency_id.name, 'INR')
        self.assertEqual(viet.currency_id, viet_before,
                         'the heal moved a configuration that was already right')

    # -- 13 -------------------------------------------------------------
    def test_13_currency_by_country_is_a_pure_read(self):
        """Eight countries answered, and not one row written."""
        cfg = self.Config.create({
            'name': 'SC Read Only', 'code': 'SCREADON',
            'country_code': 'VN', 'state': 'draft',
        })
        self.env.flush_all()
        stamp_before = cfg.write_date
        answer = self.Config.currency_by_country()
        selection = dict(self.Config._fields['country_code'].selection)
        self.assertEqual(set(answer), set(selection))
        self.assertEqual(len(answer), 8)
        self.assertEqual(answer['IN']['name'], 'INR')
        self.assertEqual(answer['VN']['name'], 'VND')
        for code, row in answer.items():
            self.assertTrue(row['name'], 'no currency answered for %s' % code)
            self.assertIn(row['position'], ('before', 'after'))
        self.env.flush_all()
        cfg.invalidate_recordset(['write_date'])
        self.assertEqual(cfg.write_date, stamp_before,
                         'reading the currency map wrote to a configuration')
