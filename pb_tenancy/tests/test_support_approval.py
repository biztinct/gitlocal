# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Approval Matrix P6 — Q10: nobody gets in until the customer says so.

A support link used to be spendable the moment it was issued. Now issuing one
also asks, and the claim refuses anything that has not been approved — with
its own sentence, because "this link has expired" about a link that is in date
sends its holder to ask for another one that would do exactly the same thing
(ledger AM78).
"""

import hashlib

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_tenancy.models.support_approval import (
    SUPPORT_PROCESS_KEY,
)


@tagged('post_install', '-at_install')
class TestSupportApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Support = cls.env['pb.support.access']
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.approver = Users.create({
            'name': 'Account Admin', 'login': 'p6_support_admin',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})

        cls.Support._approval_seed_default(cls.company)
        role = cls.env['biz.approval.role'].search(
            [('key', '=', 'approver')], limit=1)
        cls.env['biz.approval.responsibility'].search([
            ('company_id', '=', cls.company.id),
            ('role_id', '=', role.id)]).write({'active': False})
        cls.env['biz.approval.responsibility'].create({
            'company_id': cls.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.company.name,
            'user_id': cls.approver.id})
        cls.env['pb.tenancy'].sudo().support_set_allowed(True)

    def _issue(self, token='p6-support-token'):
        digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
        row = self.Support.issue(digest, 'Looking at a failed pay run',
                                 'Support Engineer', 60)
        return token, row

    # ==================================================================
    def test_q10a_issuing_a_link_asks_the_customer(self):
        _token, row = self._issue()
        request = row.approval_request_id
        self.assertTrue(request, 'the customer must be asked')
        self.assertEqual(request.state, 'pending')
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.assertEqual(step.seat_ids.acting_user_id, self.approver)

    def test_q10b_the_link_cannot_be_spent_before_it_is_approved(self):
        token, row = self._issue('p6-early')
        found, verdict = self.Support.claim(token, '10.0.0.1')
        self.assertEqual(verdict, 'not_approved')
        row.invalidate_recordset()
        self.assertEqual(row.state, 'issued',
                         'an unapproved session must not be left half open')
        self.assertFalse(row.used_at)

    def test_q10c_the_refusal_has_its_own_sentence(self):
        from odoo.addons.pb_tenancy.models.support import REFUSAL_TEXT
        self.assertIn('not_approved', REFUSAL_TEXT)
        text = str(REFUSAL_TEXT['not_approved']).lower()
        self.assertNotIn('expired', text)
        self.assertNotIn('odoo', text)

    def test_q10d_approving_it_lets_the_link_through(self):
        token, row = self._issue('p6-approved')
        request = row.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.approver).decide(
            request.id, step.key, 'approve')
        row.invalidate_recordset()
        self.assertTrue(row.approved_at)
        found, verdict = self.Support.claim(token, '10.0.0.1')
        self.assertEqual(verdict, 'ok')
        self.assertEqual(found.state, 'active')

    def test_q10e_turning_it_down_refuses_the_session_with_a_reason(self):
        token, row = self._issue('p6-refused')
        request = row.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.approver).decide(
            request.id, step.key, 'reject', 'We would rather not today.')
        row.invalidate_recordset()
        self.assertEqual(row.state, 'refused')
        self.assertIn('rather not', row.refused_reason or '')
        _found, verdict = self.Support.claim(token, '10.0.0.1')
        self.assertNotEqual(verdict, 'ok')

    def test_q10f_the_catalogue_row_names_the_record(self):
        process = self.env['biz.approval.process']._by_key(
            SUPPORT_PROCESS_KEY)
        self.assertEqual(process.model_name, 'pb.support.access')
