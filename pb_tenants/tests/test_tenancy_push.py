# -*- coding: utf-8 -*-
"""FLEET P2A — the one door out, and the databases it will not open.

T6. Everything past the refusals is a write on another database and lives
behind the pure functions (rail R6), so what a suite can prove here is the
important half: the door refuses the platform's own database, refuses a name
that is not a customer's, and refuses to address a message to something with no
readers.
"""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPushTenancy(TransactionCase):

    def setUp(self):
        super().setUp()
        self.svc = self.env['pb.tenants']
        self.cls = type(self.svc)

    # ------------------------------------------------------------- refusals
    def test_t6_01_the_master_is_never_a_destination(self):
        with self.assertRaises(UserError):
            self.svc.push_tenancy(self.env.cr.dbname, {'pb_tenancy.notice': ''})

    def test_t6_02_a_never_listed_name_is_refused(self):
        # The literal names a customer's database never gets. Whichever guard
        # catches them first, the answer must be "no" and it must be by name.
        for name in ('pb_tenants', 'pb_demo', 'pb_demo_portal', 'pb_website',
                     'pb_platform_anything'):
            with self.assertRaises(UserError, msg="%s was not refused" % name):
                self.svc.push_tenancy(name, {'pb_tenancy.notice': ''})

    def test_t6_03_a_name_that_is_nobody_is_refused(self):
        with self.assertRaises(UserError):
            self.svc.push_tenancy('some-other-database', {})

    def test_t6_04_a_customer_with_no_database_is_a_skip_not_a_crash(self):
        t = self.env['pb.tenant'].sudo().create({
            'name': 'Ghost Ltd', 'slug': 'ghostltd2026', 'state': 'live'})
        res = self.svc.push_tenancy(t.id, {'pb_tenancy.notice': ''})
        self.assertFalse(res['ok'])
        self.assertIn('ghostltd2026', res['reason'])

    def test_t6_05_a_customer_without_the_link_is_told_what_to_do(self):
        t = self.env['pb.tenant'].sudo().create({
            'name': 'Coldstart', 'slug': 'coldstart2026', 'state': 'live'})
        with patch.object(self.cls, '_db_exists', return_value=True), \
             patch.object(self.cls, '_installed_on', return_value={'web': '19.0.1.0'}):
            res = self.svc.push_tenancy(t.id, {'pb_tenancy.notice': ''})
        self.assertFalse(res['ok'])
        self.assertIn('Bring it in step', res['reason'])
        self.assertNotIn('Odoo', res['reason'])

    # ------------------------------------------------------------- notices
    def test_t6_06_a_notice_cannot_be_addressed_to_the_template(self):
        with self.assertRaises(UserError):
            self.svc.notice_send('template', 'info', 'Hello', '', '', '')

    def test_t6_07_a_bad_message_is_refused_before_anything_is_written(self):
        with patch.object(self.cls, 'push_tenancy') as pushed:
            with self.assertRaises(UserError):
                self.svc.notice_send('all', 'info', '', '', '', '')
        pushed.assert_not_called()

    def test_t6_08_the_same_message_reaches_everybody_identically(self):
        """One composition, one id, one wording — never two versions of it."""
        live = self.env['pb.tenant'].sudo().create([
            {'name': 'A Co', 'slug': 'acotest2026', 'state': 'live'},
            {'name': 'B Co', 'slug': 'bcotest2026', 'state': 'live'},
        ])
        seen = []

        def fake_push(target, values):
            seen.append(values.get('pb_tenancy.notice'))
            return {'ok': True, 'database': 'x', 'label': 'x', 'reason': ''}

        with patch.object(self.cls, 'push_tenancy', side_effect=fake_push), \
             patch.object(self.cls, '_log_line', return_value=''):
            res = self.svc.notice_send(
                'all', 'maintenance', 'Update tonight', 'Short pause.',
                '2026-09-03 22:00:00', '2026-09-04 01:00:00')
        self.assertGreaterEqual(len(seen), 2)
        self.assertEqual(len(set(seen)), 1,
                         "Two customers must never be looking at two versions "
                         "of the same announcement.")
        self.assertIn('A Co', res['sent'])
        self.assertIn('B Co', res['sent'])
        live.unlink()

    def test_t6_09_the_release_stamp_is_only_pushed_to_a_database_that_is_on_it(self):
        calls = []
        with patch.object(self.cls, 'push_tenancy',
                          side_effect=lambda t, v: calls.append(t) or {'ok': True}):
            self.svc._push_release_stamp('template', {'release_state': 'behind'},
                                         self.env['pb.release'].browse(), lambda *a, **k: '')
        self.assertEqual(calls, [],
                         "A database that came out behind must not be told it "
                         "is on the release.")
