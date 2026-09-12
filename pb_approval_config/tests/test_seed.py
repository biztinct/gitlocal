# -*- coding: utf-8 -*-
"""U12 — day one behaves the same as day zero, however many times it runs."""

from odoo.tests import tagged

from .common import MatrixCase


@tagged('post_install', '-at_install')
class TestSeed(MatrixCase):

    def test_u12_a_new_company_gets_its_default_route(self):
        """The `res.company.create` hook: a company made after install is not
        left unable to ask for anything."""
        workflow = self.seeded_workflow()
        self.assertTrue(workflow, 'a new company got no default route')
        self.assertTrue(workflow.published_version_id,
                        'the default route was left as a draft')

        binding = self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('scope_key', '=', ''), ('active', '=', True)])
        self.assertEqual(len(binding), 1)
        self.assertEqual(binding.workflow_id, workflow)

        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_approver.id),
            ('active', '=', True)])
        self.assertEqual(len(held), 1, 'nobody holds the default seat')
        self.assertTrue(held.user_id, 'the default seat names no person')

    def test_u12_running_the_seed_again_creates_nothing_new(self):
        """Idempotent three times over: the hook, the migration and the company
        hook all run the same function, and an upgrade runs two of them."""
        from odoo.addons.pb_approval_config.models.seed import seed_all

        def counts():
            return (
                self.env['biz.approval.workflow'].sudo().search_count([]),
                self.env['biz.approval.workflow.version'].sudo(
                ).search_count([]),
                self.env['biz.approval.binding'].sudo().search_count([]),
                self.env['biz.approval.responsibility'].sudo().search_count([]),
            )

        before = counts()
        seed_all(self.env)
        seed_all(self.env)
        self.assertEqual(counts(), before,
                         'running the seed again created something')

    def test_u12_the_default_route_really_resolves(self):
        """A seed that creates rows nothing can use is not a seed. The proof is
        the engine's own resolver, not the presence of the records."""
        answer = self.env['biz.approval.engine'].sudo().resolve_binding(
            self.company.id, 'generic', [''], 'any')
        self.assertFalse(answer['error'], answer['error'])
        self.assertTrue(answer['version_id'])

    def test_the_payobook_responsibilities_are_all_there(self):
        keys = set(self.env['biz.approval.role'].sudo().search([]).mapped('key'))
        for key in ('hr_lead', 'finance', 'payroll_mgr', 'director',
                    'scheme_owner', 'budget', 'signatory', 'access'):
            self.assertIn(key, keys)
        # the two the engine ships stay, because the default route uses one
        self.assertIn('approver', keys)

    def test_the_catalogue_covers_every_area_of_the_product(self):
        Process = self.env['biz.approval.process'].sudo()
        rows = Process.search([])
        self.assertGreaterEqual(len(rows), 39,
                                'the process catalogue lost rows')
        areas = set(rows.mapped('area'))
        for area in ('pay', 'money', 'data', 'people', 'time', 'setup',
                     'platform'):
            self.assertIn(area, areas, 'no process in the %s area' % area)
        # a row may never claim to be wired up when it is not: `connected` is
        # computed from the business object, never stored
        for row in rows:
            if row.connected:
                self.assertTrue(
                    getattr(self.env[row.model_name], '_approval_process_key',
                            None),
                    '%s says it is wired up and is not' % row.key)
