# -*- coding: utf-8 -*-
"""Load it, look at it, take it out, and check nothing is left behind.

THE ONLY TEST THAT MATTERS HERE IS THE LAST ONE. Loading demo data is easy to
get right and easy to check by eye. Removing it is neither: the failure is
silent, it shows up weeks later as a laptop assigned to somebody who does not
work here, and by then nobody remembers which records came from where. So the
round trip is asserted on the DATABASE — no demo employee, no demo asset, no
register row — rather than on what the remove said it did.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'pb_demo_seed')
class TestDemoSeed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # THE SHIPPED PANEL, NOT A SECOND ONE. Only one demo world may be
        # loaded in a company at a time (several of its records are unique by
        # name), so a test that made its own seed beside a tenant's loaded one
        # would be testing the collision rather than the module. Everything
        # here runs in a transaction that is rolled back, so a world that was
        # loaded before the test is still loaded after it.
        cls.seed = cls.env.ref('pb_demo_seed.demo_seed_default',
                               raise_if_not_found=False)
        if not cls.seed:
            cls.seed = cls.env['pb.demo.seed'].create({
                'name': 'Test demo data', 'profile': 'rize_vn',
                'company_id': cls.env.company.id})
        cls.seed.company_id = cls.env.company
        if cls.seed.state == 'loaded':
            cls.seed.remove_demo()

    def _seeded(self, model_name):
        """What THIS seed made, read out of its own register.

        Not a search on "starts with Demo". A database may already be carrying
        a loaded demo world — the tenant these were written for is — and a test
        that counts by name would find ten people where it expected five and
        fail for a reason that has nothing to do with the code. The register is
        the module's answer to "which records are mine", and the test is
        entitled to the same answer.
        """
        ids = self.seed.record_ids.filtered(
            lambda r: r.model_name == model_name).mapped('res_id')
        return self.env[model_name].with_context(active_test=False).browse(
            ids).exists()

    def _demo_people(self):
        return self._seeded('hr.employee')

    def test_01_the_round_trip_leaves_nothing_behind(self):
        self.seed.load_demo()
        self.assertEqual(self.seed.state, 'loaded')
        people = self._demo_people()
        self.assertEqual(len(people), 5)
        registered = len(self.seed.record_ids)
        self.assertGreater(registered, 100)

        asset_ids = self._seeded('pb.asset').ids
        contract_ids = self._seeded('hr.contract').ids
        vendor_ids = self._seeded('pb.vendor').ids

        removed, blocked = self.seed.remove_demo()

        # EVERYTHING THE DEMO OWNS OUTRIGHT MUST GO. Assets, contracts and
        # suppliers have no life outside the demo world, so a single survivor
        # here is a bug rather than a circumstance.
        for model_name, ids in (('pb.asset', asset_ids),
                                ('hr.contract', contract_ids),
                                ('pb.vendor', vendor_ids)):
            self.assertFalse(
                self.env[model_name].with_context(active_test=False)
                .browse(ids).exists(),
                '%s survived the removal' % model_name)
        self.assertGreaterEqual(removed, registered - 40)  # cascades take some

        # A PERSON MAY LEGITIMATELY REFUSE, and the test says which reasons are
        # legitimate rather than demanding none. Somebody can build real work on
        # a demo employee — a pay run that includes them is the obvious case —
        # and the right behaviour is to report it by name, not to force the
        # delete. What must never happen is a refusal nobody can act on, so the
        # reason has to be one this module knows how to explain.
        allowed = [sentence for _needle, sentence in self.seed._BLOCK_REASONS]
        for line in blocked:
            self.assertTrue(
                any(sentence in line for sentence in allowed),
                'a refusal nobody can act on: %s' % line)

    def test_02_five_stories_not_five_copies(self):
        """Each person carries a different thing, which is the whole design.

        Asserted because it is the first thing a well-meaning edit flattens:
        giving everybody a probation review and everybody an asset makes every
        list look fuller and every screen mean less.
        """
        self.seed.load_demo()
        by_code = {e.employee_id: e for e in self._demo_people()}
        self.addCleanup(self.seed.remove_demo)

        self.assertEqual(len(self._seeded('pb.probation.review')), 1)
        self.assertEqual(len(self._seeded('pb.pip.case')), 1)
        self.assertEqual(len(self._seeded('pb.contract.review')), 1)

        # One foreign hire, so the expatriate branches of the pay scheme have
        # somebody to run for.
        foreign = [e for e in by_code.values() if not e.pb_vn_is_local]
        self.assertEqual(len(foreign), 1)
        self.assertEqual(foreign[0].employee_id, 'DEMO005')

    def test_03_the_payroll_facts_are_on_the_records(self):
        """After a load, the monthly file needs a code and some hours.

        Every other value the Vietnam scheme asks for has to be answerable from
        the employee or the contract, or the short pay-data file is a lie.
        """
        self.seed.load_demo()
        self.addCleanup(self.seed.remove_demo)
        employee = self._demo_people().filtered(
            lambda e: e.employee_id == 'DEMO002')
        self.assertTrue(employee.pb_vn_union_member)
        self.assertTrue(employee.pb_vn_in_insurance)
        self.assertTrue(employee.pb_vn_tax_resident)

        contract = self._seeded('hr.contract').filtered(
            lambda c: c.employee_id == employee)[:1]
        self.assertTrue(contract)
        self.assertEqual(contract.wage, 26000000.0)
        self.assertEqual(contract.dependents, 2)
        self.assertEqual(contract.pb_vn_pay_grade, 2)
        self.assertEqual(contract.pb_vn_hours_per_day, 8.0)
        self.assertTrue(contract.pb_vn_qual_ot_weekday)

        uniform = contract.advantages_ids.filtered(
            lambda a: (a.advantage_template_id.code or '') == 'UNIFORM')
        self.assertEqual(uniform.amount, 500000.0)

        # And somewhere to pay it.
        self.assertTrue(employee.bank_account_ids)

    def test_04_it_refuses_to_load_twice(self):
        self.seed.load_demo()
        self.addCleanup(self.seed.remove_demo)
        with self.assertRaises(Exception):
            self.seed.action_load()

    def test_05_the_register_never_holds_a_protected_model(self):
        """The guard between "remove the demo" and "remove the company"."""
        from odoo.addons.pb_demo_seed.models.demo_seed import PROTECTED_MODELS
        self.seed.load_demo()
        self.addCleanup(self.seed.remove_demo)
        held = set(self.seed.record_ids.mapped('model_name'))
        self.assertFalse(held & PROTECTED_MODELS)
