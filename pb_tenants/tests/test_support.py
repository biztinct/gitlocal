# -*- coding: utf-8 -*-
"""FLEET P6 — what the platform is allowed to ask for.

RAIL R6 AGAIN. Everything `support_open` actually DOES happens on another
database, so the suite proves the decisions and captures the write rather than
performing it: `_tenant_env` is replaced with a fake that records what would
have been written. The real cross-database write is proved on a restored copy at
deploy time and reported (rail R4), exactly as every phase before this one.
"""
from contextlib import contextmanager
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenants.models.support_rules import (
    ALLOWED_MINUTES, DEFAULT_MINUTES, DURATIONS, customer_blocker,
    session_sentence, support_refusal,
)

REASON = "their October overtime line is showing a zero"


# =============================================================================
@tagged('post_install', '-at_install')
class TestSupportRules(TransactionCase):
    """T6a — the refusals, as pure functions."""

    def test_t6_01_a_healthy_customer_is_not_refused(self):
        self.assertIsNone(
            support_refusal('live', True, True, REASON, DEFAULT_MINUTES))

    def test_t6_02_no_reason_is_refused_before_anything_else(self):
        why = support_refusal('decommissioned', False, False, '', 120)
        self.assertIn('Say what you need', why,
                      "Telling somebody the customer is closed when they "
                      "simply have not typed anything answers a question they "
                      "did not ask.")

    def test_t6_03_a_shrug_is_refused(self):
        self.assertIn('too short',
                      support_refusal('live', True, True, 'fix', 120))

    def test_t6_04_the_customers_switch_is_quoted_back(self):
        why = support_refusal('live', True, False, REASON, 120)
        self.assertIn('switched support access off', why)
        self.assertIn('Nobody here can turn it back on', why,
                      "The refusal has to say there is no override, because "
                      "there is not one.")

    def test_t6_05_a_customer_who_is_not_linked_gets_the_next_step(self):
        why = support_refusal('live', False, True, REASON, 120)
        self.assertIn('In step with master', why)

    def test_t6_06_a_closed_customer_is_refused(self):
        for state in ('decommissioned', 'draft', 'provisioning', 'error'):
            self.assertIn('no live database',
                          support_refusal(state, True, True, REASON, 120),
                          state)

    def test_t6_07_a_customer_on_their_way_out_can_still_be_helped(self):
        """`pending_deletion` still has a database, and their last month is a
        real thing to need help with."""
        self.assertIsNone(
            support_refusal('pending_deletion', True, True, REASON, 120))

    def test_t6_08_a_length_nobody_offered_is_refused(self):
        self.assertIn('one of the three',
                      support_refusal('live', True, True, REASON, 4321))

    def test_t6_09_the_three_lengths_are_the_three_buttons(self):
        self.assertEqual(ALLOWED_MINUTES, tuple(m for m, _l, _b in DURATIONS))
        self.assertIn(DEFAULT_MINUTES, ALLOWED_MINUTES)

    def test_t6_10_the_screen_and_the_server_print_the_same_sentence(self):
        """`customer_blocker` is what the row shows; `support_refusal` is what
        the button raises. They must not drift."""
        for state, linked, allowed in (('live', True, False),
                                       ('live', False, True),
                                       ('decommissioned', True, True)):
            self.assertEqual(
                customer_blocker(state, linked, allowed),
                support_refusal(state, linked, allowed, REASON, 120))

    def test_t6_11_no_word_of_the_framework_reaches_a_screen(self):
        """Rail R7 (ledger F43), over every sentence this file can print."""
        sentences = [customer_blocker(s, l, a)
                     for s in ('live', 'decommissioned')
                     for l in (True, False) for a in (True, False)]
        sentences += [support_refusal('live', True, True, '', 120),
                      support_refusal('live', True, True, 'x', 120),
                      support_refusal('live', True, True, REASON, 9),
                      session_sentence("Ash", "AB Mauri", 120)]
        for s in sentences:
            if s:
                self.assertNotIn('odoo', s.lower(), s)

    def test_t6_12_the_sentence_names_who_what_and_how_long(self):
        line = session_sentence("Ash", "AB Mauri", 120)
        self.assertIn("Ash", line)
        self.assertIn("AB Mauri", line)
        self.assertIn("2 hours", line)


# =============================================================================
@tagged('post_install', '-at_install')
class TestSupportService(TransactionCase):
    """T6b — the facade, with the other database faked out.

    The fleet on a live master is real (ledger F28), so this suite makes its own
    customer inside the transaction and stands the real ones down where it has
    to. Nothing here reaches another database: `_tenant_env` is replaced.
    """

    def setUp(self):
        super().setUp()
        self.svc = self.env['pb.tenants']
        self.tenant = self.env['pb.tenant'].sudo().create({
            'name': "Probe Ltd", 'slug': 'p6probe', 'state': 'live',
        })
        self.written = []

    @contextmanager
    def _fake_env(self, dbname):
        """Stands in for the customer's database. Records, writes nothing."""
        self.written.append(('env', dbname))
        outer = self

        class FakeRows:
            def issue(self, digest, reason, name, minutes):
                outer.written.append(('issue', digest, reason, name, minutes))
                return True

        class FakeEnv(dict):
            def __getitem__(self, key):
                if key == 'pb.support.access':
                    return FakeRows()
                raise KeyError(key)

        yield FakeEnv()

    def _patched(self, allowed=True, linked=True):
        return [
            patch.object(type(self.svc), '_tenant_env', self._fake_env),
            patch.object(type(self.svc), '_ensure_break_glass',
                         lambda s, env, say: say("recovery account checked")),
            patch.object(type(self.svc), '_tenancy_installed',
                         lambda s, db: linked),
            patch.object(type(self.svc), '_support_allowed_on',
                         lambda s, db: allowed),
            patch.object(type(self.svc), '_support_rows_on',
                         lambda s, db, limit=25: []),
        ]

    def _run(self, fn, allowed=True, linked=True):
        patches = self._patched(allowed=allowed, linked=linked)
        for p in patches:
            p.start()
        try:
            return fn()
        finally:
            for p in patches:
                p.stop()

    # ------------------------------------------------------------- refusals
    def test_t6_20_a_switched_off_customer_is_refused_by_the_server_too(self):
        with self.assertRaises(UserError) as e:
            self._run(lambda: self.svc.support_open(
                self.tenant.id, REASON, 120), allowed=False)
        self.assertIn('switched support access off', str(e.exception))

    def test_t6_21_an_empty_reason_is_refused_by_the_server_too(self):
        with self.assertRaises(UserError):
            self._run(lambda: self.svc.support_open(self.tenant.id, '   ', 120))

    def test_t6_22_a_customer_with_no_link_is_refused(self):
        with self.assertRaises(UserError):
            self._run(lambda: self.svc.support_open(
                self.tenant.id, REASON, 120), linked=False)

    # -------------------------------------------------------- what it writes
    def test_t6_23_opening_writes_a_hashed_row_and_returns_a_live_link(self):
        res = self._run(lambda: self.svc.support_open(
            self.tenant.id, REASON, 120))
        self.assertTrue(res['ok'])
        issued = [w for w in self.written if w[0] == 'issue']
        self.assertEqual(len(issued), 1)
        digest, reason, _name, minutes = issued[0][1:]
        self.assertEqual(len(digest), 64, "only the hash is written")
        self.assertEqual(reason, REASON)
        self.assertEqual(minutes, 120)
        # The token is in the URL and nowhere else, and it is not the hash.
        token = res['url'].rsplit('/', 1)[-1]
        self.assertTrue(token)
        self.assertNotEqual(token, digest)
        self.assertIn('/pb_tenancy/support/', res['url'])

    def test_t6_24_two_sessions_never_share_a_token(self):
        first = self._run(lambda: self.svc.support_open(
            self.tenant.id, REASON, 120))
        second = self._run(lambda: self.svc.support_open(
            self.tenant.id, REASON, 120))
        self.assertNotEqual(first['url'], second['url'])

    def test_t6_25_the_recovery_account_is_made_sure_of_first(self):
        """abm was adopted, not provisioned: the account was genuinely absent."""
        self._run(lambda: self.svc.support_open(self.tenant.id, REASON, 120))
        log = self.tenant.provision_log or ''
        self.assertIn('recovery account checked', log)

    def test_t6_26_it_is_written_in_the_customers_own_log(self):
        self._run(lambda: self.svc.support_open(self.tenant.id, REASON, 480))
        log = self.tenant.provision_log or ''
        self.assertIn(REASON, log)
        self.assertIn('8 hours', log)

    def test_t6_27_it_raises_an_alert_so_it_reaches_the_daily_summary(self):
        self._run(lambda: self.svc.support_open(self.tenant.id, REASON, 120))
        alert = self.env['pb.alert'].sudo().search(
            [('key', '=', 'support_session:p6probe'),
             ('state', '=', 'open')], limit=1)
        self.assertTrue(alert, "Access to a customer's payroll is never quiet.")
        self.assertEqual(alert.severity, 'info',
                         "It is not a fault; it is a thing that happened.")
        self.assertNotIn('odoo', (alert.text or '').lower())
        self.assertIn(REASON, alert.text or '')

    def test_t6_28_the_alert_is_never_closed_by_the_sweep(self):
        """No reading can see a support session, so the fifteen-minute job must
        not be allowed to decide it is over."""
        from odoo.addons.pb_tenants.models.alert_rules import SELF_MANAGED_KINDS
        self.assertIn('support_session', SELF_MANAGED_KINDS)

    def test_t6_29_ending_it_closes_the_alert(self):
        self._run(lambda: self.svc.support_open(self.tenant.id, REASON, 120))

        @contextmanager
        def _end_env(_self, dbname):
            class Rows:
                def browse(self, _id):
                    return self

                def search(self, _dom):
                    return self

                def exists(self):
                    return self

                def filtered(self, _fn):
                    return self

                def end(self, why):
                    return True

                def sudo(self):
                    return self

                def __len__(self):
                    return 1
            yield {'pb.support.access': Rows()}

        with patch.object(type(self.svc), '_tenant_env', _end_env), \
                patch.object(type(self.svc), '_tenancy_installed',
                             lambda s, db: True), \
                patch.object(type(self.svc), '_support_allowed_on',
                             lambda s, db: True), \
                patch.object(type(self.svc), '_support_rows_on',
                             lambda s, db, limit=25: []):
            self.svc.support_end(self.tenant.id)
        alert = self.env['pb.alert'].sudo().search(
            [('key', '=', 'support_session:p6probe'),
             ('state', '=', 'open')])
        self.assertFalse(alert)

    def test_t6_30_the_platforms_own_database_is_refused_by_name(self):
        """Rail R2, re-asked on the literal database about to be written."""
        self.tenant.sudo().write({'slug': self.env.cr.dbname})
        with self.assertRaises(UserError) as e:
            self._run(lambda: self.svc.support_open(
                self.tenant.id, REASON, 120))
        self.assertIn("platform's own database", str(e.exception))

    def test_t6_31_an_unreadable_switch_reads_as_no(self):
        """The ONE read in this programme that fails closed.

        Everything about a customer's standing fails open, because being wrong
        locks a payroll office out. Being wrong here opens somebody's data
        against their wishes.
        """
        with patch.object(type(self.svc), '_pg_cursor',
                          lambda s, db='postgres': (_ for _ in ()).throw(
                              Exception("no such database"))):
            self.assertFalse(self.svc._support_allowed_on('nowhere'))
