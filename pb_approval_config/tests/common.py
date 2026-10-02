# -*- coding: utf-8 -*-
"""Shared fixtures for the configuration and inbox facades.

Every case runs against `biz.approval.generic.request` — the reference adapter
the engine ships — so what is proved here is the contract a later adapter has
to meet, not a stub written to make the tests pass.

The company is a FRESH one rather than the database's own, so the seed's own
work is visible and the test's people belong to exactly one place.
"""

from odoo.tests import TransactionCase


class MatrixCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Matrix = cls.env['pb.approval.matrix']
        cls.Inbox = cls.env['pb.approval.inbox']
        cls.engine = cls.env['biz.approval.engine']
        cls.Generic = cls.env['biz.approval.generic.request']
        cls.process = cls.env.ref('biz_approval_workflow.process_generic')
        cls.role_approver = cls.env.ref('biz_approval_workflow.role_approver')
        cls.role_hr_lead = cls.env.ref('pb_approval_config.role_hr_lead')
        cls.role_finance = cls.env.ref('pb_approval_config.role_finance')

        cls.company = cls.env['res.company'].create({'name': 'AM Alpha'})
        cls.currency = cls.company.currency_id
        # the test env's own user must be inside the company, or every record
        # rule below hides the fixtures from the fixture builder
        cls.env.user.write({'company_ids': [(4, cls.company.id)],
                            'company_id': cls.company.id})
        # A COMPANY WHOSE SEATS ARE STILL EMPTY, WHICH IS WHAT THESE CASES ARE
        # ABOUT. Phase 6 gives a new company a first holder for every
        # responsibility its default routes name, taken from whoever holds the
        # group that job used to be done by — and where nobody does, the
        # administrator. That is right for a real company and wrong for a suite
        # whose subject is filling a seat for the first time and finding the
        # gaps before it is filled. The engine's own "Approver" seat is left
        # exactly as the seed made it: the default "Other request" route uses
        # it, and one case here is about that seed.
        cls.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', cls.company.id),
            ('role_id', '!=', cls.role_approver.id)]).write({'active': False})

        cls.boss = cls._user('am_boss', 'Bea Boss', groups=[
            'base.group_user',
            'biz_approval_workflow.group_approval_admin'])
        cls.officer = cls._user('am_officer', 'Olly Officer', groups=[
            'base.group_user',
            'biz_approval_workflow.group_approval_config'])
        cls.hr = cls._user('am_hr', 'Hana HR')
        cls.fin = cls._user('am_fin', 'Fred Finance')
        cls.asker = cls._user('am_asker', 'Ash Asker')

    @classmethod
    def _user(cls, login, name, groups=('base.group_user',)):
        group_ids = [cls.env.ref(g).id for g in groups]
        return cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, group_ids)],
            })

    # ------------------------------------------------------------- helpers
    def as_admin(self, model):
        """The facade, called by somebody who is allowed to set things up."""
        return self.env[model].with_user(self.boss).with_company(self.company)

    def hold(self, role, user, scope_key='', backup=None):
        """Name a person for a seat — replacing whoever is there.

        One seat, one holder at a time, is the engine's rule. A product
        installed beside it may already have named somebody when the company
        was created, so naming a person here ENDS what was there rather than
        colliding with it. That is what the screen does too.
        """
        self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', role.id),
            ('scope_key', '=', scope_key or ''),
            ('active', '=', True)]).write({'active': False})
        return self.env['biz.approval.responsibility'].create({
            'company_id': self.company.id,
            'role_id': role.id,
            'scope_key': scope_key,
            'scope_label': scope_key or self.company.name,
            'user_id': user.id,
            'backup_user_id': backup.id if backup else False,
        })

    def seeded_workflow(self):
        """The default "Other request" route the install hook created."""
        return self.env['biz.approval.workflow'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id)], limit=1)

    def ask(self, user=None, name='A sign-off please', amount=0.0):
        user = user or self.asker
        return self.Inbox.with_user(user).with_company(self.company).ask({
            'name': name, 'amount': amount,
        })
