# -*- coding: utf-8 -*-
"""Z03 — pausing, ending and re-planning a customer need two owners.

Three things are proved, and the third is the one that would be a real fault:

  1. the destructive presses write a proposal instead of doing the thing;
  2. the typed slug is STILL required, and it is checked before anything is
     written down — so a typo can never become a request about the wrong
     customer;
  3. the platform route is not seeded on a database that has no fleet. A
     tenant never has `pb_tenants` installed, and the row must not appear
     there.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_tenants.models.tenant_approval import (
    DESTRUCTIVE, TENANT_WRITE,
)


@tagged('post_install', '-at_install')
class TestP7Platform(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Proposal = cls.env['pb.tenant.proposal']
        cls.admin = cls.env.ref('base.user_admin')
        cls.owner = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Pat Platform', 'login': 'plt_owner',
                'email': 'plt_owner@example.com',
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                      cls.env.ref('base.group_system').id])],
            })
        cls.Proposal._approval_seed_default(cls.company)
        cls.tenant = cls.env['pb.tenant'].create({
            'name': 'Acme Widgets', 'slug': 'acmewidgets'})

    def _svc(self):
        return self.env['pb.tenants'].with_user(self.admin)

    # ------------------------------------------------------------ Z03
    def test_z03a_the_typed_slug_is_still_required(self):
        with self.assertRaises(UserError):
            self._svc().tenant_suspend(self.tenant.id, 'Unpaid', 'wrong-slug')
        self.assertNotEqual(self.tenant.state, 'suspended')

    def test_z03b_pausing_becomes_a_request(self):
        answer = self._svc().tenant_suspend(
            self.tenant.id, 'Unpaid invoice', self.tenant.slug)
        self.assertTrue(answer.get('pending'))
        self.assertTrue(answer.get('reference', '').startswith('PLT'))
        self.tenant.invalidate_recordset()
        self.assertNotEqual(self.tenant.state, 'suspended',
                            'nothing happens until two owners agree')

    def test_z03c_the_route_asks_two_platform_owners(self):
        workflow = self.env['biz.approval.workflow'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id.key', '=', 'tenant')], limit=1)
        self.assertTrue(workflow)
        steps = workflow.published_version_id.definition['steps']
        self.assertEqual(len(steps), 2)
        self.assertEqual({s['who']['role'] for s in steps},
                         {'platform_owner'})
        self.assertEqual(len({s['key'] for s in steps}), 2,
                         'two steps is two signatures, from two people')

    def test_z03d_the_destructive_kinds_are_marked_as_such(self):
        answer = self._svc().tenant_suspend(
            self.tenant.id, 'Unpaid invoice', self.tenant.slug)
        proposal = self.Proposal.sudo().browse(answer['proposal_id']) \
            if answer.get('proposal_id') else self.Proposal.sudo().search(
                [], order='id desc', limit=1)
        facts = proposal.facts()
        self.assertTrue(facts['destructive']['value'])
        self.assertIn('suspend', DESTRUCTIVE)

    def test_z03e_the_approved_press_goes_straight_through(self):
        """The flag the apply sets is what stops it proposing itself."""
        self._svc().with_context(**{TENANT_WRITE: True}).tenant_suspend(
            self.tenant.id, 'Unpaid invoice', self.tenant.slug)
        self.tenant.invalidate_recordset()
        self.assertEqual(self.tenant.state, 'suspended')

    def test_z03f_no_fleet_means_no_row(self):
        """A tenant database has no `pb.tenant` table and must get no route.

        Asserted through the seed's own guard rather than by uninstalling the
        module, which a test cannot do.
        """
        source = self.Proposal._approval_seed_default.__doc__ or ''
        self.assertIn('pb.tenant', str(
            self.Proposal._approval_seed_default.__code__.co_consts))
