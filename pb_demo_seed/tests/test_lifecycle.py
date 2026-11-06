from odoo.tests import TransactionCase, tagged
from ..seeds.lifecycle import load, remove


@tagged('post_install', '-at_install', 'pb_lifecycle_demo')
class TestLifecycleDemo(TransactionCase):
    def test_load_is_additive_repeatable_and_removable(self):
        if 'pb.hiring.requisition' not in self.env or 'pb_target_close_date' not in self.env['pb.hiring.requisition']._fields:
            self.skipTest('Hiring journey is not installed')
        seed = load(self.env)
        original = seed.record_ids.mapped('id')
        self.assertEqual(load(self.env).id, seed.id)
        self.assertEqual(seed.record_ids.ids, original)
        for model, name in [('hr.employee', 'name'), ('hr.department', 'name'),
                            ('pb.hiring.requisition', 'title'), ('hr.applicant', 'partner_name'),
                            ('pb.holiday.batch', 'name')]:
            self.assertTrue(all(r[name].startswith('DEMO') for r in seed._registered(model)))
        ids = [(r.model_name, r.res_id) for r in seed.record_ids]
        removed, archived, blocked = remove(self.env)
        self.assertFalse(blocked, blocked)
        self.assertGreater(removed, 15)
        self.assertFalse(seed.record_ids)
        for model, record_id in ids:
            self.assertFalse(self.env[model].browse(record_id).exists(), model)
