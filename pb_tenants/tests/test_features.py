# -*- coding: utf-8 -*-
"""FLEET P4 · T5 — flipping a switch writes it down AND tells the customer.

WHAT A SUITE CAN PROVE HERE. The write is on this database and is provable; the
delivery is on somebody else's and is not, so `push_tenancy` is captured and
what would have gone out is inspected. That split is the same one P2A's own
tests make, and it is rail R6 in practice.

F28 applies: this runs on the live platform's database inside a transaction, so
the fleet is stood down in `setUp` — a real customer joining a `search()` turns
"the one tenant I made" into two and every count wrong.
"""
import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenants.models.feature_rules import T_FEATURES


@tagged('post_install', '-at_install')
class TestFeatures(TransactionCase):

    def setUp(self):
        super().setUp()
        self.svc = self.env['pb.tenants']
        self.cls = type(self.svc)
        # F28. Stand the real fleet down INSIDE the transaction, which is
        # rolled back and never reaches them.
        self.env['pb.tenant'].sudo().search(
            [('state', '!=', 'decommissioned')]).write(
                {'state': 'decommissioned'})
        self.tenant = self.env['pb.tenant'].sudo().create({
            'name': 'Switchco', 'slug': 'switchco2026', 'state': 'live'})
        self.feature = self.env['pb.feature'].sudo().search(
            [('key', '=', 'insights')], limit=1)
        self.assertTrue(self.feature, "The catalogue must be seeded.")
        self.pushes = []

        def fake_push(inner_self, target, values):
            self.pushes.append((target, values))
            return {'ok': True, 'database': 'switchco2026',
                    'label': 'Switchco', 'reason': ''}

        self.push_patch = patch.object(self.cls, 'push_tenancy', fake_push)
        self.push_patch.start()
        self.addCleanup(self.push_patch.stop)
        # Nothing in this suite may reach out to another database.
        self.installed_patch = patch.object(
            self.cls, '_installed_on', return_value={'pb_tenancy': '19.0.1.2.0'})
        self.installed_patch.start()
        self.addCleanup(self.installed_patch.stop)

    def _last_payload(self):
        self.assertTrue(self.pushes, "Nothing was sent to the customer.")
        return json.loads(self.pushes[-1][1][T_FEATURES])

    # ------------------------------------------------- writing and sending
    def test_t5_01_a_switch_is_written_down_and_delivered(self):
        self.svc.features_set(self.tenant.id, 'insights', False, 'not sold')
        row = self.env['pb.tenant.feature'].sudo().search(
            [('tenant_id', '=', self.tenant.id),
             ('feature_id', '=', self.feature.id)])
        self.assertEqual(len(row), 1)
        self.assertFalse(row.on)
        self.assertEqual(row.reason, 'not sold')
        self.assertEqual(row.source, 'manual')
        self.assertEqual(row.changed_by, self.env.user)
        payload = self._last_payload()
        self.assertFalse(payload['insights']['on'])
        self.assertTrue(payload['learn']['on'],
                        "Everything else must be sent unchanged, or the one "
                        "push would be a partial answer.")

    def test_t5_02_the_delivery_stamps_when_it_happened(self):
        self.assertFalse(self.tenant.features_pushed_at,
                         "A new customer here has never been told.")
        self.svc.features_set(self.tenant.id, 'insights', False, '')
        self.assertTrue(self.tenant.features_pushed_at)

    def test_t5_03_flipping_it_back_reuses_the_one_row(self):
        self.svc.features_set(self.tenant.id, 'insights', False, '')
        self.svc.features_set(self.tenant.id, 'insights', True, 'sold it')
        rows = self.env['pb.tenant.feature'].sudo().search(
            [('tenant_id', '=', self.tenant.id)])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows.on)
        self.assertEqual(rows.reason, 'sold it')

    def test_t5_04_putting_it_back_removes_the_customers_answer(self):
        self.svc.features_set(self.tenant.id, 'insights', False, '')
        self.svc.features_reset(self.tenant.id, 'insights')
        self.assertFalse(self.env['pb.tenant.feature'].sudo().search(
            [('tenant_id', '=', self.tenant.id)]),
            "Put back means FOLLOW THE CATALOGUE again — including when the "
            "catalogue changes later. Writing the default down would freeze it.")
        self.assertTrue(self._last_payload()['insights']['on'])

    # ------------------------------------------------------------ refusals
    def test_t5_05_a_decommissioned_customer_is_refused_by_name(self):
        gone = self.env['pb.tenant'].sudo().create({
            'name': 'Gone Ltd', 'slug': 'goneltd2026',
            'state': 'decommissioned'})
        with self.assertRaises(UserError) as e:
            self.svc.features_set(gone.id, 'insights', False, '')
        self.assertIn('Gone Ltd', str(e.exception))

    def test_t5_06_a_feature_nobody_has_defined_is_refused(self):
        with self.assertRaises(UserError):
            self.svc.features_set(self.tenant.id, 'no_such_feature', False, '')

    def test_t5_07_a_customer_that_is_not_there_is_refused(self):
        with self.assertRaises(UserError):
            self.svc.features_set(999999999, 'insights', False, '')

    # --------------------------------------------------------------- bulk
    def test_t5_08_one_feature_many_customers_one_push_each(self):
        other = self.env['pb.tenant'].sudo().create({
            'name': 'Second Ltd', 'slug': 'secondltd2026', 'state': 'live'})
        res = self.svc.features_bulk(
            'learn', False, [self.tenant.id, other.id], 'not in their plan')
        self.assertEqual(len(res['sent']), 2)
        self.assertFalse(res['failed'])
        self.assertEqual(len(self.pushes), 2,
                         "One push per customer — never one broadcast.")
        self.assertEqual(self.env['pb.tenant.feature'].sudo().search_count(
            [('key', '=', 'learn'), ('on', '=', False)]), 2)

    def test_t5_09_bulk_leaves_a_decommissioned_customer_out(self):
        gone = self.env['pb.tenant'].sudo().create({
            'name': 'Gone Two', 'slug': 'gonetwo2026', 'state': 'decommissioned'})
        res = self.svc.features_bulk('learn', False, [self.tenant.id, gone.id], '')
        self.assertEqual(len(res['sent']), 1)

    def test_t5_10_bulk_with_nobody_is_refused_rather_than_silent(self):
        with self.assertRaises(UserError):
            self.svc.features_bulk('learn', False, [], '')

    # ----------------------------------------------------------- the screen
    def test_t5_11_the_screen_reads_without_touching_a_customer(self):
        self.svc.features_set(self.tenant.id, 'insights', False, 'no')
        data = self.svc.features_data()
        row = next(r for r in data['tenants'] if r['id'] == self.tenant.id)
        self.assertFalse(row['on']['insights'])
        self.assertEqual(row['source']['insights'], 'manual')
        self.assertEqual(row['source']['learn'], 'default')
        self.assertEqual(row['custom'], 1)
        self.assertFalse(row['never_pushed'])
        self.assertTrue(data['defaults']['on']['insights'],
                        "The template row is the catalogue's defaults, not any "
                        "customer's answers.")
        self.assertEqual(data['custom_tenants'], 1)

    def test_t5_12_the_master_keeps_every_feature_on(self):
        """Whatever the catalogue's defaults say. The owner has to be able to
        see the whole product to sell it."""
        self.feature.write({'default_on': False})
        payload = self.svc._push_features_here()
        self.assertTrue(all(v['on'] for v in payload.values()))
        stored = json.loads(self.env['ir.config_parameter'].sudo().get_param(
            T_FEATURES, '{}'))
        self.assertTrue(stored['insights']['on'])

    # ----------------------------------------------------------- catalogue
    def test_t5_13_editing_the_catalogue_tells_every_live_customer(self):
        self.svc.feature_save(self.feature.id,
                              {'default_on': False, 'mode': 'lock'})
        self.assertFalse(self.feature.default_on)
        self.assertTrue(self.pushes, "A catalogue change moves what customers "
                                     "see, so they have to be told.")
        self.assertFalse(self._last_payload()['insights']['on'])

    def test_t5_14_the_catalogue_refuses_nonsense(self):
        with self.assertRaises(UserError):
            self.svc.feature_save(self.feature.id, {'mode': 'sometimes'})
        with self.assertRaises(UserError):
            self.svc.feature_save(self.feature.id, {'name': '  '})

    def test_t5_15_the_key_can_never_be_edited(self):
        """Customers' databases are written in terms of the key. A rename would
        silently switch the feature back on everywhere it was off."""
        self.svc.feature_save(self.feature.id, {'key': 'insights_v2'})
        self.assertEqual(self.feature.key, 'insights')

    # ------------------------------------------------------ plain English
    def test_t5_16_nothing_the_owner_reads_says_odoo(self):
        data = self.svc.features_data()
        blob = json.dumps(data).lower()
        for word in ('odoo', 'param', 'ormcache'):
            self.assertNotIn(word, blob,
                             '"%s" reached a string on the screen' % word)
