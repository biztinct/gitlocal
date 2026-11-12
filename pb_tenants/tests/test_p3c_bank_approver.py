# -*- coding: utf-8 -*-
"""UPDATES P3c, K5 (owner decision D15) — a new client's own administrator
approves the client's bank details; the platform support login does not.

Provisioning writes into ANOTHER database, so the step is exercised here on
this test database standing in for the new tenant: `_seat_bank_approver`
takes the tenant's environment as an argument, exactly as `_step_admin`
hands it over. The whole `_step_admin` is also run against a real clone of
the golden template at deploy time (UPDATES_P3C_REPORT.md).
"""
from odoo.tests import TransactionCase, tagged

SUPPORT = 'p3c.k5.support@example.com'


@tagged('post_install', '-at_install')
class TestP3cTenantBankApprover(TransactionCase):

    def setUp(self):
        super().setUp()
        if 'biz.approval.responsibility' not in self.env:
            self.skipTest('the approval engine is not on this database')
        self.svc = self.env['pb.tenants']
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenants.break_glass_login', SUPPORT)
        self.role = self.env['biz.approval.role'].sudo().search(
            [('key', '=', 'finance')], limit=1)
        if not self.role:
            self.skipTest('no Finance responsibility on this database')
        self.Resp = self.env['biz.approval.responsibility'].sudo()
        self.co = self.env['res.company'].create({'name': 'P3C K5 Client'})
        self.Resp.search([('company_id', '=', self.co.id)]).write({'active': False})
        self.support = self._user(SUPPORT, ('base.group_user', 'base.group_system'))
        self.admin = self._user('p3c.k5.admin@example.com', (
            'base.group_user', 'hr.group_hr_manager'))
        # The golden template's shape: Finance held by the support login.
        self.row = self.Resp.create({
            'company_id': self.co.id, 'role_id': self.role.id, 'scope_key': '',
            'user_id': self.support.id})
        self.said = []

    def _user(self, login, groups):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login.split('@')[0], 'login': login,
            'company_id': self.co.id, 'company_ids': [(6, 0, [self.co.id])],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])]})

    def say(self, line, level='info'):
        self.said.append((level, line))

    def finance(self, company=None):
        return self.Resp.search([('company_id', '=', (company or self.co).id),
                                 ('role_id', '=', self.role.id),
                                 ('scope_key', '=', ''), ('active', '=', True)])

    def test_K5_the_client_admin_becomes_the_bank_approver(self):
        self.row.backup_user_id = self.support
        self.svc._seat_bank_approver(self.env, self.admin, self.say)
        row = self.finance()
        self.assertEqual(row.user_id, self.admin)
        self.assertFalse(row.backup_user_id)
        self.assertNotIn(self.support, row.pool_user_ids)
        self.assertTrue(any('approves bank details' in line for _l, line in self.said))
        if 'pb.records.apply' not in self.env:
            return
        Apply = self.env['pb.records.apply']
        # the support login proposes: the client's admin is asked
        users, _via = Apply._second_people(self.co, self.support)
        self.assertEqual(users, self.admin)
        self.assertEqual(Apply._bank_excluded(self.support), 'support')
        # the admin proposes: nobody else (D15 — the "add one in Access" line)
        users, _via = Apply._second_people(self.co, self.admin)
        self.assertFalse(users)

    def test_K5b_a_company_with_no_finance_seat_gets_one(self):
        self.row.unlink()
        self.svc._seat_bank_approver(self.env, self.admin, self.say)
        self.assertEqual(self.finance().user_id, self.admin)

    def test_K5c_a_real_person_holding_finance_is_left_alone(self):
        real = self._user('p3c.k5.cfo@example.com', ('base.group_user',))
        self.row.user_id = real
        self.svc._seat_bank_approver(self.env, self.admin, self.say)
        self.assertEqual(self.finance().user_id, real)
        self.assertTrue(any(level == 'warn' and 'P3C K5 Client (p3c.k5.cfo@example.com)'
                            in line for level, line in self.said), self.said)

    def test_K5d_step_admin_calls_it(self):
        """`_step_admin` seats the administrator after the rails."""
        import inspect
        source = inspect.getsource(type(self.svc)._step_admin)
        self.assertIn('_seat_bank_approver(env, admin, say)', source)
        self.assertLess(source.index('_apply_rails_to'),
                        source.index('_seat_bank_approver'))
