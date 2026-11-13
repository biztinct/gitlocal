# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Engine-level tests for biz_audit_trail (no HR models needed).

The mixin-in-anger tests (a real dept/wage change logging an entry) live in
pb_employee_vault, which supplies the consumer models. Here we prove the
invariants that stand alone: append-only, forced actor/stamp, the ormcached
rule lookup + its invalidation, and the retention vacuum.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAuditEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Entry = cls.env['biz.audit.entry']
        cls.Rule = cls.env['biz.audit.rule']
        # a plain internal user (no system) to prove append-only + forced actor
        cls.user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Audit Tester', 'login': 'audit_tester',
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})

    def _mk_entry(self):
        return self.Entry.sudo().create({
            'model_name': 'res.partner', 'res_id': 1, 'res_display': 'ACME',
            'field_name': 'name', 'field_label': 'Name',
            'old_value': 'Old', 'new_value': 'New'})

    # 4a — append-only: a non-system user cannot edit or delete an entry
    def test_append_only(self):
        entry = self._mk_entry()
        with self.assertRaises(AccessError):
            entry.with_user(self.user).write({'new_value': 'Forged'})
        with self.assertRaises(AccessError):
            entry.with_user(self.user).unlink()

    # actor/stamp are forced server-side, never client-supplied
    def test_forced_actor_and_stamp(self):
        backdated = fields.Datetime.now() - timedelta(days=999)
        entry = self.Entry.with_user(self.user).sudo().create({
            'model_name': 'res.partner', 'res_id': 2, 'field_name': 'name',
            'field_label': 'Name', 'old_value': 'A', 'new_value': 'B',
            'user_id': self.env.ref('base.user_admin').id,   # a forgery attempt
            'stamp': backdated})
        # sudo() keeps env.uid as the real caller → the actor is that user
        self.assertEqual(entry.user_id, self.user)
        self.assertGreater(entry.stamp, backdated)

    # 3 — ormcached rule lookup + invalidation on toggle
    def test_watched_fields_cache_invalidation(self):
        self.assertNotIn('name', self.Rule._watched_fields('res.partner'))
        rule = self.Rule.create({
            'name': 'Partner name', 'model_name': 'res.partner',
            'field_names': 'name, email'})
        self.assertEqual(
            self.Rule._watched_fields('res.partner'), frozenset({'name', 'email'}))
        rule.active = False
        self.assertEqual(
            self.Rule._watched_fields('res.partner'), frozenset())

    # 4b — retention vacuum keys on write_date; young rows survive
    def test_gc_vacuum_by_write_date(self):
        old = self._mk_entry()
        young = self._mk_entry()
        # age one row past a 1-day window (write_date is auto; force it in SQL)
        aged = fields.Datetime.now() - timedelta(days=30)
        self.env.cr.execute(
            "UPDATE biz_audit_entry SET write_date = %s WHERE id = %s",
            (aged, old.id))
        old.invalidate_recordset(['write_date'])
        self.env['ir.config_parameter'].sudo().set_param(
            'biz_audit_trail.retention_days', '1')
        self.Entry._gc_vacuum()
        self.assertFalse(old.exists())
        self.assertTrue(young.exists())
