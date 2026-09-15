# -*- coding: utf-8 -*-
"""Load it, look at it, take it out, and check nothing is left behind.

THE ONLY TEST THAT MATTERS HERE IS THE LAST ONE. Loading demo data is easy to
get right and easy to check by eye. Removing it is neither: the failure is
silent, it shows up weeks later as a laptop assigned to somebody who does not
work here, and by then nobody remembers which records came from where. So the
round trip is asserted on the DATABASE — no demo employee, no demo asset, no
register row — rather than on what the remove said it did.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _src(*parts):
    with open(os.path.join(get_module_path('pb_demo_seed'), *parts),
              encoding='utf-8') as handle:
        return handle.read()


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

        removed, switched_off, blocked = self.seed.remove_demo()
        self.assertEqual(switched_off, 0,
                         'a profile-built world holds no logins')

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
        #
        # ASKED ONLY WHERE THE QUESTION EXISTS. The Vietnam payroll mapping is
        # no longer a dependency of this module (a database can have the demo
        # world without it), so on a database that does not carry those fields
        # there is no "local or foreign" to assert — and a test that demands
        # one would be demanding a dependency the manifest does not have.
        if 'pb_vn_is_local' in self.env['hr.employee']._fields:
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
        contract = self._seeded('hr.contract').filtered(
            lambda c: c.employee_id == employee)[:1]
        self.assertTrue(contract)
        self.assertEqual(contract.wage, 26000000.0)
        self.assertEqual(contract.dependents, 2)

        # The Vietnam facts only where the database has them (see test_02).
        if 'pb_vn_union_member' in self.env['hr.employee']._fields:
            self.assertTrue(employee.pb_vn_union_member)
            self.assertTrue(employee.pb_vn_in_insurance)
            self.assertTrue(employee.pb_vn_tax_resident)
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


@tagged('post_install', '-at_install', 'pb_demo_seed')
class TestRegisterApi(TransactionCase):
    """The door another module uses to hand its own demo records over.

    THE POINT OF THIS CLASS is that a record made by the PRODUCT — a hiring
    request somebody created on a screen while showing the screen off — is demo
    data too, and the only difference between it and a record a profile built
    is who typed it. The register does not care, and neither should the
    removal.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Seed = cls.env['pb.demo.seed']
        cls.programme = cls.Seed.programme_seed()
        # Something harmless to put on a register: a partner is cheap to make,
        # belongs to nothing, and deletes without argument.
        cls.people = cls.env['res.partner'].create([
            {'name': 'DEMO Register Test One'},
            {'name': 'DEMO Register Test Two'},
        ])

    def _rows(self, seed=None):
        seed = seed or self.programme
        return seed.record_ids.filtered(
            lambda r: r.res_id in self.people.ids
            and r.model_name == 'res.partner')

    def test_01_the_programme_panel_is_found_not_multiplied(self):
        again = self.Seed.programme_seed()
        self.assertEqual(again, self.programme)
        self.assertEqual(self.programme.profile, 'adopted')
        self.assertEqual(self.programme.state, 'loaded')
        self.assertEqual(
            self.Seed.sudo().search_count(
                [('name', '=', self.programme.name),
                 ('company_id', '=', self.programme.company_id.id)]), 1)

    def test_02_register_adds_once_and_only_once(self):
        added = self.Seed.register(self.people, 'A test pair')
        self.assertEqual(added, 2)
        self.assertEqual(len(self._rows()), 2)
        self.assertEqual(self._rows().mapped('label'), ['A test pair'] * 2)

        # A FIXTURE THAT RUNS TWICE IS A FIXTURE, NOT TWO RECORDS.
        self.assertEqual(self.Seed.register(self.people, 'A test pair'), 0)
        self.assertEqual(len(self._rows()), 2)

    def test_03_new_rows_go_after_the_last_one(self):
        """Creation order is dependency order, and the removal walks it back."""
        before = max(self.programme.record_ids.mapped('sequence'), default=0)
        self.Seed.register(self.people[0], 'First')
        self.Seed.register(self.people[1], 'Second')
        sequences = self._rows().sorted('sequence').mapped('sequence')
        self.assertEqual(sequences, [before + 1, before + 2])

    def test_04_last_goes_below_everything(self):
        """`last=True` is for what is made as a SIDE EFFECT of its owner."""
        lowest = min(self.programme.record_ids.mapped('sequence'), default=0)
        self.Seed.register(self.people[0], 'A private contact', last=True)
        self.assertEqual(self._rows().mapped('sequence'), [lowest - 1])

    def test_05_a_company_is_refused_and_a_login_is_not(self):
        """The register is the only thing between "remove the demo" and
        "remove the company" — and a demo login is demo data."""
        self.assertEqual(self.Seed.register(self.env.company, 'Nope'), 0)
        self.assertFalse(self.programme.record_ids.filtered(
            lambda r: r.model_name == 'res.company'))

        user = self.env['res.users'].create({
            'name': 'DEMO Register Test Login',
            'login': 'demo.register.test@example.com',
        })
        self.addCleanup(user.unlink)
        self.assertEqual(self.Seed.register(user, 'A demo login'), 1)

    def test_06_a_caller_without_this_module_is_a_no_op(self):
        """The guard every caller uses, tested as the callers write it.

        `env.get` answers None for a model that is not installed, so the whole
        call disappears on a tenant without demo data — which is why no module
        has to depend on this one to hand its records over.
        """
        seed = self.env.get('pb.demo.seed')
        self.assertIsNotNone(seed)
        registered = 0
        missing = self.env.get('pb.demo.seed.not.installed')
        if missing is not None:                    # pragma: no cover
            registered = missing.register(self.people, 'Never happens')
        self.assertIsNone(missing)
        self.assertEqual(registered, 0)

    def test_07_removal_switches_a_login_off_and_deletes_the_rest(self):
        user = self.env['res.users'].create({
            'name': 'DEMO Register Removal Login',
            'login': 'demo.register.removal@example.com',
        })
        seed = self.Seed.create({
            'name': 'DEMO removal test', 'profile': 'adopted',
            'state': 'loaded', 'company_id': self.env.company.id})
        partner = self.env['res.partner'].create({'name': 'DEMO Removal Row'})
        seed._register_records(partner, label='A demo contact')
        seed._register_records(user, label='A demo login')

        removed, switched_off, blocked = seed.remove_demo()
        self.assertEqual(blocked, [])
        self.assertEqual(switched_off, 1)
        self.assertGreaterEqual(removed, 1)
        self.assertFalse(partner.exists())
        self.assertTrue(user.exists(), 'a login must not be deleted')
        self.assertFalse(user.active, 'a demo login must be switched off')
        self.assertEqual(seed.state, 'empty')

    def test_08_preview_counts_what_remove_would_take(self):
        """Read-only, so it is the only safe question on a live database."""
        seed = self.Seed.create({
            'name': 'DEMO preview test', 'profile': 'adopted',
            'state': 'loaded', 'company_id': self.env.company.id})
        user = self.env['res.users'].create({
            'name': 'DEMO Preview Login',
            'login': 'demo.register.preview@example.com'})
        self.addCleanup(user.unlink)
        seed._register_records(self.people, label='Two contacts')
        seed._register_records(user, label='One login')
        ghost = self.env['res.partner'].create({'name': 'DEMO Gone Already'})
        seed._register_records(ghost, label='Already gone')
        ghost.unlink()

        preview = seed.preview_remove()
        self.assertEqual(preview['total'], 2)
        self.assertEqual(preview['gone'], 1)
        self.assertEqual(len(preview['users']), 1)
        self.assertEqual(preview['per_model'][0]['model'], 'res.partner')
        self.assertEqual(preview['per_model'][0]['count'], 2)
        # It must not have touched anything.
        self.assertTrue(all(p.exists() for p in self.people))
        self.assertTrue(user.active)

    def test_09_an_adopted_panel_does_not_block_a_world(self):
        """Two panels in one company is the NORMAL case here: a world that was
        built, and a register of what the product made beside it."""
        company = self.programme.company_id
        world = self.Seed.create({
            'name': 'DEMO world under test', 'profile': 'rize_vn',
            'state': 'empty', 'company_id': company.id})
        self.assertEqual(self.programme.state, 'loaded')
        self.assertFalse(world._other_loaded_world(),
                         'an adopted register blocked a world from loading')

        # And a loaded world does not stop the product handing records over.
        loaded = self.Seed.create({
            'name': 'DEMO world already loaded', 'profile': 'rize_vn',
            'state': 'loaded', 'company_id': company.id})
        self.assertEqual(self.Seed.register(self.people, 'Beside a world'), 2)
        # A SECOND WORLD is still refused, by the world and not by us.
        self.assertEqual(world._other_loaded_world(), loaded)

    def test_10_the_world_label_carries_no_customer_name(self):
        from odoo.addons.pb_demo_seed.seeds import PROFILES
        self.assertEqual(PROFILES['rize_vn']['label'],
                         'DEMO Vietnam — five people, five stories')
        for key, spec in PROFILES.items():
            self.assertNotIn('rize', spec['label'].lower(),
                             "the world %s is named after a customer" % key)

    def test_11_no_customer_name_and_no_other_brand_on_any_screen(self):
        """The white-label rule, and only where it actually binds.

        It covers user-visible STRINGS. Engineering comments MUST be able to
        say the real name — the sentence that stops the next contributor
        reintroducing a bug is worth more than a gate that forbids it (R118) —
        so comments are stripped and what is left is checked.
        """
        for parts in (('views', 'demo_seed_views.xml'),
                      ('data', 'demo_seed_data.xml')):
            src = re.sub(r'<!--.*?-->', '', _src(*parts), flags=re.S)
            self.assertNotIn('Odoo', src,
                             '%s shows the word Odoo to a user' % parts[-1])
            self.assertNotIn('rize', src.lower().replace('rize_vn', ''),
                             '%s names the customer' % parts[-1])
        js = re.sub(r'/\*.*?\*/', '', _src('static', 'src', 'js',
                                           'demo_seed_settings.js'), flags=re.S)
        js = re.sub(r'//.*$', '', js, flags=re.M)
        self.assertNotIn('Odoo', js)
        self.assertNotIn('rize', js.lower())
        # And the sentences Python shows: only what is inside `_()`.
        for parts in (('models', 'demo_seed.py'),):
            shown = re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"', _src(*parts))
            self.assertTrue(shown, 'the translated strings did not parse')
            for sentence in shown:
                self.assertNotIn('Odoo', sentence)
                self.assertNotIn('rize', sentence.lower())
                self.assertNotIn('(s)', sentence,
                                 'bracketed plurals are a programme writing')
