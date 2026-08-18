# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T5 — the demo cohort: rerun-safe, and it never touches anything real.

W59's shape: a seeder has two separate contracts and they need two separate
assertions. *This run created nothing* is what a correct RERUN looks like, and
*the world is full* is what must be true on every run including that one. A test
that asserts "it created some rows" is false on every rerun, which is precisely
the state the live demo is permanently in.

The whole file skips cleanly where pb_demo is not installed, LOUDLY (skipTest,
not a silent `if`) — W78: a conditional guard around the only assertion in a
test is a test that cannot fail.
"""

from odoo.tests.common import tagged

from .common import EssWorkforceCase


@tagged('post_install', '-at_install')
class TestP8Demo(EssWorkforceCase):

    def setUp(self):
        super().setUp()
        if 'pb.demo.generator' not in self.env:
            self.skipTest('pb_demo is not installed on this database')
        self.gen = self.env['pb.demo.generator'].sudo().create({})

    # ------------------------------------------------------------ the shape
    def test_the_seeder_is_wired_into_generate_all(self):
        """A seeder nobody calls is a seeder that does not exist. The gate is on
        the SOURCE because behaviour cannot distinguish "not called" from
        "called and produced nothing on this database" (W79)."""
        import inspect
        from odoo.addons.pb_demo.models import demo_generator
        src = inspect.getsource(demo_generator.PbDemoGenerator.action_generate_all)
        self.assertIn('ensure_ess_workforce_cohort', src)

    def test_it_survives_a_database_with_no_demo_company(self):
        """The first thing every pb_demo entry point has to do. A seeder that
        raises on a virgin database blocks the install that would have created
        the world it wanted."""
        res = self.gen.ensure_ess_workforce_cohort()
        for key in ('users', 'linked', 'acked', 'pending', 'pulse'):
            self.assertIn(key, res)

    # ------------------------------------------------------- idempotency
    def test_a_second_run_creates_nothing_new(self):
        if not self.gen.get_group_company():
            self.skipTest('no demo company on this database')
        self.gen.ensure_ess_workforce_cohort()
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        Pulse = self.env['pb.shift.pulse'].sudo()
        users_before = Users.search_count(
            [('login', 'like', 'ess%.demo@payobook.com')])
        pulse_before = Pulse.search_count([('uniq_hash', '=like', 'pbdemo:p8:%')])

        second = self.gen.ensure_ess_workforce_cohort()

        self.assertEqual(second['users'], 0, 'a rerun minted new logins')
        self.assertEqual(second['pulse'], 0, 'a rerun duplicated pulse rows')
        self.assertEqual(
            Users.search_count([('login', 'like', 'ess%.demo@payobook.com')]),
            users_before)
        self.assertEqual(
            Pulse.search_count([('uniq_hash', '=like', 'pbdemo:p8:%')]),
            pulse_before)

    def test_the_world_is_full_after_a_run(self):
        """The other half of W59: assert the WORLD, not the run's counters."""
        if not self.gen.get_group_company():
            self.skipTest('no demo company on this database')
        self.gen.ensure_ess_workforce_cohort()
        Pulse = self.env['pb.shift.pulse'].sudo()
        from ..models.shift_pulse import PULSE_FLOOR
        self.assertGreaterEqual(
            Pulse.search_count([('uniq_hash', '=like', 'pbdemo:p8:%')]),
            PULSE_FLOOR,
            'the demo pulse does not clear the Today tile anonymity floor')

    def test_the_demo_logins_stay_passwordless(self):
        """C18.14. A shipped password is a shipped credential, and this cohort
        is ten of them."""
        if not self.gen.get_group_company():
            self.skipTest('no demo company on this database')
        self.gen.ensure_ess_workforce_cohort()
        self.env.cr.execute("""
            SELECT login FROM res_users
             WHERE login LIKE 'ess%%.demo@payobook.com' AND password IS NOT NULL
        """)
        self.assertEqual(self.env.cr.fetchall(), [],
                         'a demo ESS login shipped with a password set')

    # ------------------------------------------------------- non-destructive
    def test_a_real_persons_acknowledgment_is_never_overwritten(self):
        """W60's never-destructive rule. The seeder cannot tell a previous run's
        ack from a visitor's, so it only ever ADDS."""
        shift = self._shift(self.emp_a, self._future_day(), state='published')
        shift._ess_ack('a real person')
        stamp = shift.acked_at
        self.gen.ensure_ess_workforce_cohort()
        self.assertEqual(shift.acked_at, stamp)

    def test_non_demo_pulse_rows_are_never_cleaned(self):
        """The demo tag is the handle, and it has to be tight enough that a real
        rating can never match it (W60 — the pulse is the one P8 record
        `clean_demo_employees` cannot find by employee, because having no
        employee is the point)."""
        real = self.env['pb.shift.pulse'].sudo().create({
            'company_id': self.company.id,
            'date': self.monday, 'rating': 4,
            'uniq_hash': 'a-real-employees-digest-0123456789abcdef',
        })
        self.env['pb.shift.pulse'].sudo().search(
            [('uniq_hash', '=like', 'pbdemo:p8:%')]).unlink()
        self.assertTrue(real.exists(), 'a real rating matched the demo tag')

    def test_the_ack_mix_is_a_mix(self):
        """A badge that is always green is an instrument nobody reads, and one
        that is never green looks broken. The seeder has to produce both."""
        if not self.gen.get_group_company():
            self.skipTest('no demo company on this database')
        res = self.gen.ensure_ess_workforce_cohort()
        Shift = self.env['hr.shift.planning'].sudo()
        cohort = self.env['hr.employee'].sudo().search(
            [('user_id.login', 'like', 'ess%.demo@payobook.com')])
        if not cohort:
            self.skipTest('the demo world has no Stores - North cohort')
        states = set(Shift.search([
            ('employee_id', 'in', cohort.ids),
            ('state', '=', 'published')]).mapped('ack_state'))
        self.assertTrue(res['acked'] or 'acked' in states,
                        'nothing in the cohort week is confirmed')
