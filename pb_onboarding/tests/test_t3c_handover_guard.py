# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3c — the buddy stand-in is an active colleague of the joiner's own
company (found during the T3b browser walk: a crafted temp_id reached any
employee, another company's or an archived one)."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestT3cHandoverGuard(TransactionCase):

    def test_t3c_stand_in_must_be_an_active_colleague_of_the_same_company(self):
        Emp = self.env['hr.employee']
        co = self.env.company
        other = self.env['res.company'].sudo().create({'name': 'T3c Other'})
        joiner = Emp.create({'name': 'T3c Joiner', 'company_id': co.id})
        colleague = Emp.create({'name': 'T3c Colleague', 'company_id': co.id})
        foreign = Emp.create({'name': 'T3c Foreign', 'company_id': other.id})
        gone = Emp.create({'name': 'T3c Gone', 'company_id': co.id,
                           'active': False})

        with self.assertRaises(UserError):
            joiner.set_temp_buddy(foreign.id)
        with self.assertRaises(UserError):
            joiner.set_temp_buddy(gone.id)
        self.assertFalse(joiner.buddy_temp_id)

        joiner.set_temp_buddy(colleague.id)
        self.assertEqual(joiner.buddy_temp_id, colleague)
