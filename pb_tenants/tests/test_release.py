# -*- coding: utf-8 -*-
"""FLEET P1 — cutting a release, and refusing to point the button at the master.

The two things here that a suite CAN reach: the record a release cut leaves
behind on this database, and the refusals that happen before any other database
is opened. Everything past those refusals is a cross-database write and lives
behind the pure functions in `test_sync_rules.py` (rail R6).
"""
import json
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

#: A master small enough to reason about. `have` is what the master database has
#: applied, `file` is what is sitting on the server's disk.
FAKE_MASTER = {
    'pb_assets': {'label': 'Assets', 'have': '19.0.1.2.0', 'file': '1.2.0'},
    'hr': {'label': 'Employees', 'have': '19.0.1.0.0', 'file': '1.0.0'},
}
FAKE_MASTER_BEHIND = dict(
    FAKE_MASTER,
    pb_assets={'label': 'Assets', 'have': '19.0.1.2.0', 'file': '1.3.0'},
)


@tagged('post_install', '-at_install')
class TestReleaseCut(TransactionCase):
    """T8 — the photograph, and when it must not be taken."""

    def setUp(self):
        super().setUp()
        self.svc = self.env['pb.tenants']
        self.cls = type(self.svc)

    def test_t8_01_a_cut_creates_the_record_and_makes_it_current(self):
        with patch.object(self.cls, '_master_modules',
                          return_value=dict(FAKE_MASTER)):
            self.svc.release_cut(notes='First one.')
        rel = self.env['pb.release'].search([], order='id desc', limit=1)
        self.assertTrue(rel)
        self.assertTrue(rel.is_current)
        self.assertEqual(rel.module_count, 2)
        self.assertEqual(rel.notes, 'First one.')
        self.assertEqual(json.loads(rel.snapshot),
                         {'pb_assets': '19.0.1.2.0', 'hr': '19.0.1.0.0'})
        self.assertEqual(rel.cut_by, self.env.user)

    def test_t8_02_only_one_release_is_ever_current(self):
        with patch.object(self.cls, '_master_modules',
                          return_value=dict(FAKE_MASTER)):
            self.svc.release_cut()
            first = self.env['pb.release'].search([], order='id desc', limit=1)
            self.svc.release_cut()
        second = self.env['pb.release'].search([], order='id desc', limit=1)
        self.assertNotEqual(first, second)
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(
            self.env['pb.release'].search_count([('is_current', '=', True)]), 1)

    def test_t8_03_the_second_cut_of_a_day_gets_its_own_name(self):
        """Two cuts on one day are two records, not a unique-key error.

        The suffix is NOT asserted to be `-2`: this runs on the live master,
        where a release cut for real earlier today is already sitting in the
        table, so the next free number is whatever it is. What matters is that
        both names share today's date and that the second one is new.
        """
        today = fields.Date.today().strftime('%Y.%m.%d')
        with patch.object(self.cls, '_master_modules',
                          return_value=dict(FAKE_MASTER)):
            self.svc.release_cut()
            self.svc.release_cut()
        names = self.env['pb.release'].search([], order='id desc', limit=2).mapped('name')
        self.assertEqual(len(set(names)), 2, names)
        for name in names:
            self.assertTrue(name.startswith(today), names)
        self.assertRegex(names[0], r'-\d+$')

    def test_t8_04_a_master_behind_its_own_files_cannot_be_photographed(self):
        """Rail R3. A master halfway through applying itself is a mixture."""
        before = self.env['pb.release'].search_count([])
        with patch.object(self.cls, '_master_modules',
                          return_value=dict(FAKE_MASTER_BEHIND)):
            with self.assertRaises(UserError) as err:
                self.svc.release_cut()
        self.assertIn('pb_assets', str(err.exception))
        self.assertEqual(self.env['pb.release'].search_count([]), before,
                         "a release was written despite the refusal")

    def test_t8_05_the_refusal_says_nothing_an_owner_would_have_to_look_up(self):
        with patch.object(self.cls, '_master_modules',
                          return_value=dict(FAKE_MASTER_BEHIND)):
            with self.assertRaises(UserError) as err:
                self.svc.release_cut()
        said = str(err.exception).lower()
        for word in ('odoo', 'registry', 'manifest', 'latest_version', 'addon'):
            self.assertNotIn(word, said, 'the refusal says "%s"' % word)


@tagged('post_install', '-at_install')
class TestBringInStepRefusals(TransactionCase):
    """T9 — where the button will not point."""

    def setUp(self):
        super().setUp()
        self.svc = self.env['pb.tenants']

    def test_t9_01_the_master_is_never_a_destination(self):
        with self.assertRaises(UserError) as err:
            self.svc.sync_bring_in_step(self.env.cr.dbname, dry_run=True)
        self.assertIn('master', str(err.exception).lower())

    def test_t9_02_a_name_that_is_nobody_is_refused_by_name(self):
        with self.assertRaises(UserError) as err:
            self.svc.sync_bring_in_step('not-a-customer', dry_run=True)
        self.assertIn('not-a-customer', str(err.exception))

    def test_t9_03_a_rehearsal_copy_that_does_not_exist_is_named(self):
        """Rail R4's entry point still has to refuse an absent database."""
        self.env['pb.tenant'].create({'name': 'Zed Test', 'slug': 'zzfleetp1'})
        with self.assertRaises(UserError) as err:
            self.svc.sync_bring_in_step('zzfleetp1-staging', dry_run=True)
        self.assertIn('zzfleetp1-staging', str(err.exception))

    def test_t9_04_a_rehearsal_copy_of_nobody_is_refused(self):
        with self.assertRaises(UserError) as err:
            self.svc.sync_bring_in_step('someoneelse-staging', dry_run=True)
        self.assertIn('someoneelse-staging', str(err.exception))

    def test_t9_05_a_customer_that_is_gone_is_refused(self):
        with self.assertRaises(UserError):
            self.svc.sync_bring_in_step(987654321, dry_run=True)

    def test_t9_06_a_closed_down_customer_is_refused_by_name(self):
        t = self.env['pb.tenant'].create({
            'name': 'Closed Co', 'slug': 'zzclosed', 'state': 'decommissioned'})
        with self.assertRaises(UserError) as err:
            self.svc.sync_bring_in_step(t.id, dry_run=True)
        self.assertIn('Closed Co', str(err.exception))
