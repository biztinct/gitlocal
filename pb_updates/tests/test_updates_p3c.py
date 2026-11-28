# -*- coding: utf-8 -*-
"""UPDATES P3c — who may approve bank details (owner decisions D13-D15,
tests K1-K4 and K7 in UPDATES_P3C_HANDOVER.md §4; K5 lives in pb_tenants,
K6 is the P3a suite run unchanged).

The platform support login is recognised the way the platform names it in
every tenant database: the `pb_tenancy.recovery_login` setting (default
`platform.recovery@payobook.com`). A demo login is recognised only by the demo
role `pb_demo.group_payobook_demo`; a login that merely LOOKS like a demo one
(`…@demo`) is an ordinary person to the code (rize's `indo@demo` is handled
by rize's own bank route, D14).
"""
import inspect
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.pb_records.models import records_approval as RA

from . import test_updates_p3a as p3a
from .test_updates_p3a import ACC, P3aCommon

SUPPORT_LOGIN = 'p3c.support@example.com'


class P3cCommon(P3aCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The platform names its support login per database; the code must
        # read that setting, not a hard-coded address.
        cls.env['ir.config_parameter'].sudo().set_param(
            'pb_tenancy.recovery_login', SUPPORT_LOGIN)
        cls.support = cls._user(SUPPORT_LOGIN, (
            'base.group_user', 'base.group_system',
            'hr.group_hr_manager',
            'pb_hr_payroll_base.group_payroll_base_manager'), cls.company)

    def lone_company(self, name, finance=None):
        """A company where only the proposer and (optionally) the support
        login work — the template's and p0clone's shape."""
        co = self._company(name)
        self.env.user.company_ids = [(3, co.id)]
        self.env['biz.approval.responsibility'].sudo().search(
            [('company_id', '=', co.id)]).write({'active': False})
        proposer = self._user('%s.proposer' % name.lower().replace(' ', '.'), (
            'base.group_user', 'hr.group_hr_user',
            'pb_hr_payroll_base.group_payroll_base_officer',
            'pb_records.group_records_editor'), co)
        if finance is not None:
            finance.company_ids = [(4, co.id)]
            self._hold(co, 'finance', finance)
        upd = self.env(user=proposer, context=dict(
            self.env.context, allowed_company_ids=[co.id]))['pb.updates.desk']
        return co, proposer, upd

    def demo_group(self):
        """The demo role. `pb_demo` is not installed on the test database, so
        the group is laid under the same external id the code looks for."""
        group = self.env.ref(RA.DEMO_GROUP_XMLID, raise_if_not_found=False)
        if group:
            return group
        group = self.env['res.groups'].create({'name': 'P3C Demo User'})
        self.env['ir.model.data'].create({
            'module': 'pb_demo', 'name': 'group_payobook_demo',
            'model': 'res.groups', 'res_id': group.id, 'noupdate': True})
        return group


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3c')
class TestUpdatesP3cBankApprovers(P3cCommon):

    # ------------------------------------------------------------ K1
    def test_K1_support_login_alone_is_never_seated(self):
        co, proposer, upd = self.lone_company('P3C Lone Co', finance=self.support)
        dee = self._person('P3C Dee', 'P3CU01', co)
        rows = [['Code', 'Account'], ['P3CU01', '4445556667']]
        outlook = upd.lane_outlook([{'emp_id': dee.id, 'field_id': ACC,
                                     'value': '4445556667'}])['lanes']
        self.assertEqual(outlook[0]['outcome'], 'nobody')
        self.assertIn('Nobody else in P3C Lone Co can approve bank details '
                      'yet — add one in Access.', outlook[0]['line'])
        bank = self.parts(self.send(rows, {2: ACC}, upd=upd))['bank']
        request = bank.approval_request_id
        seated = request.seat_ids.mapped('acting_user_id') | \
            request.seat_ids.mapped('user_id')
        self.assertNotIn(self.support, seated)
        self.assertEqual(request.state, 'blocked')
        self.assertIn('Nobody else in P3C Lone Co can approve bank details yet '
                      '— add one in Access.', request.block_reason)
        self.assertEqual(bank.state, 'pending')
        self.assertEqual(self.account(dee), '')

    def test_K1b_support_named_on_a_route_is_left_out(self):
        own = {'schema_version': 1, 'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'Named', 'who': {
                'mode': 'people', 'user_ids': [self.support.id, self.second.id],
                'all': False}, 'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {'independent': True}}
        self.publish_route(self.company, 'records_bank', own)
        bank = self.parts(self.mixed())['bank']
        self.assertEqual(self.seat_users(bank), self.second)

    def test_K1c_support_as_finance_backup_is_left_out(self):
        role = self.env['biz.approval.role'].sudo().search(
            [('key', '=', 'finance')], limit=1)
        self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', '')]).write({'user_id': self.proposer.id,
                                            'backup_user_id': self.support.id})
        bank = self.parts(self.mixed())['bank']
        seats = self.seat_users(bank)
        self.assertNotIn(self.support, seats)
        self.assertNotIn(self.proposer, seats)
        self.assertIn(self.second, seats, 'a records manager stands in')

    def test_K1d_the_support_login_from_the_default_setting(self):
        """No setting written on the database: the platform's default name."""
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenancy.recovery_login', '')
        # The tenant databases already carry this login (p0clone, template).
        default = self.env['res.users'].sudo().with_context(active_test=False).search(
            [('login', '=', RA.RECOVERY_LOGIN_DEFAULT)], limit=1) or self._user(
                RA.RECOVERY_LOGIN_DEFAULT, ('base.group_user', 'base.group_system'),
                self.company)
        Apply = self.env['pb.records.apply']
        self.assertEqual(Apply._bank_excluded(default), 'support')
        self.assertEqual(Apply._bank_excluded(self.second), '')

    # ------------------------------------------------------------ K2
    def test_K2_support_login_cannot_decide_by_direct_call(self):
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        # no seat: refused
        with self.assertRaisesRegex(UserError, 'This login cannot approve bank details'):
            self.Engine.with_user(self.support).decide(request.id, step.key, 'approve')
        # moved onto the support login by an approvals admin: still refused
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.Engine.sudo().reassign(request.id, seat.key, self.support.id, 'P3C test')
        with self.assertRaisesRegex(UserError, 'This login cannot approve bank details'):
            self.Engine.with_user(self.support).decide(request.id, step.key, 'approve')
        inbox = self.env['pb.approval.inbox'].with_user(self.support) \
            if 'pb.approval.inbox' in self.env else None
        if inbox is not None:
            with self.assertRaisesRegex(UserError, 'This login cannot approve'):
                inbox.act('pb.records.apply', bank.id, 'approve')
        self.fresh(bank)
        self.assertFalse(bank.applied)
        self.assertEqual(self.account(self.ann), '')

    def test_K2b_a_support_yes_never_writes(self):
        """Fail closed: even if a support login's yes got recorded (the
        decide check bypassed), the write refuses — that yes does not count
        as the second person."""
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.Engine.sudo().reassign(request.id, seat.key, self.support.id, 'P3C test')
        with patch.object(type(bank), '_approval_may_decide', lambda *a, **k: None):
            self.Engine.with_user(self.support).decide(request.id, step.key, 'approve', 'x')
        self.fresh(bank)
        self.assertFalse(bank.applied)
        self.assertIn('second person', bank.approval_request_id.block_reason or '')
        self.assertEqual(self.account(self.ann), '')

    def test_K2c_proposer_sentence_still_first(self):
        """The proposer keeps P3a's own sentence (F4), unchanged."""
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        with self.assertRaisesRegex(UserError, 'You proposed this change'):
            self.Engine.with_user(self.proposer).decide(request.id, step.key, 'approve')

    # ------------------------------------------------------------ K4
    def test_K4_demo_role_login_is_never_seated(self):
        demo = self._user('p3c.demo', ('base.group_user',), self.company)
        demo.group_ids = [(4, self.demo_group().id)]
        self._hold(self.company, 'finance', demo)
        self.assertEqual(self.env['pb.records.apply']._bank_excluded(demo), 'demo')
        bank = self.parts(self.mixed())['bank']
        seats = self.seat_users(bank)
        self.assertNotIn(demo, seats)
        self.assertIn(self.second, seats, 'a records manager stands in')
        request = bank.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        # Without a seat a plain login cannot even open the request; moved
        # onto the demo login by an approvals admin, it is refused by name.
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.Engine.sudo().reassign(request.id, seat.key, demo.id, 'P3C test')
        with self.assertRaisesRegex(UserError, 'This login cannot approve bank details'):
            self.Engine.with_user(demo).decide(request.id, step.key, 'approve')
        self.fresh(bank)
        self.assertFalse(bank.applied)

    def test_K4b_a_demo_looking_name_is_not_a_marker(self):
        """No guessing from a login: `…@demo` without the demo role is an
        ordinary person to the code (rize's indo@demo is set up, D14)."""
        lookalike = self._user('p3c.finance@demo', ('base.group_user',), self.company)
        self._hold(self.company, 'finance', lookalike)
        self.assertEqual(self.env['pb.records.apply']._bank_excluded(lookalike), '')
        bank = self.parts(self.mixed())['bank']
        self.assertEqual(self.seat_users(bank), lookalike)

    # ------------------------------------------- D14 — a route that names people
    def rize_route(self, people):
        return {'schema_version': 1, 'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'A second person', 'who': {
                'mode': 'people', 'user_ids': [p.id for p in people],
                'all': False}, 'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {'independent': True}}

    def test_D14_named_route_asks_only_the_named_people(self):
        third = self._user('p3c.third', ('base.group_user',), self.company)
        # a "records manager" who is NOT named — rize's indo@demo shape
        outsider = self._user('p3c.outsider@demo', (
            'base.group_user', 'pb_hr_payroll_base.group_payroll_base_manager'),
            self.company)
        self.publish_route(self.company, 'records_bank',
                           self.rize_route([self.proposer, self.second, third]))
        bank = self.parts(self.mixed())['bank']
        seats = self.seat_users(bank)
        self.assertEqual(set(seats.ids), {self.second.id, third.id})
        self.assertNotIn(outsider, seats)
        self.assertNotIn(self.support, seats)

    def test_D14_named_route_never_widens(self):
        """Only the proposer is named: the request waits and says the route
        is the fix — it never falls back to Finance or a records manager."""
        self.publish_route(self.company, 'records_bank',
                           self.rize_route([self.proposer]))
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        self.assertEqual(request.state, 'blocked')
        self.assertIn('add a person to the bank details route', request.block_reason)
        self.assertNotIn(self.second, request.seat_ids.mapped('acting_user_id'))

    def test_D13_still_one_second_person(self):
        """D13: one person other than the proposer is enough (P3a)."""
        third = self._user('p3c.third2', ('base.group_user',), self.company)
        self.publish_route(self.company, 'records_bank',
                           self.rize_route([self.proposer, self.second, third]))
        bank = self.parts(self.mixed())['bank']
        self.approve(bank, third)
        self.fresh(bank)
        self.assertTrue(bank.applied, bank.approval_request_id.block_reason)
        self.assertEqual(self.account(self.ann), '9988776655')


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3c')
class TestUpdatesP3cOtherProcessesInert(P3cCommon):
    """K3 — the support login in another process's route: unchanged. The
    P3a F12 harness (one run with the seams, one with them bypassed),
    borrowed rather than inherited so F12's own cases do not run twice."""

    _flow = p3a.TestUpdatesP3aEngineInert._flow
    _both = p3a.TestUpdatesP3aEngineInert._both

    def test_K3_support_on_another_route_is_seated_and_decides(self):
        definition = {'schema_version': 1, 'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'Support',
             'who': {'mode': 'people', 'user_ids': [self.support.id]},
             'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {'independent': True}}
        a, b = self._both(definition)
        self.assertEqual(a['seats'], [self.support.id])
        self.assertEqual(a['state'], 'applied')
        self.assertEqual(a, b)

    def test_K3b_support_holding_a_role_elsewhere(self):
        self._hold(self.company, 'hr_lead', self.support)
        definition = {'schema_version': 1, 'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'HR lead',
             'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'company'},
             'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {'independent': True}}
        a, b = self._both(definition)
        self.assertEqual(a['seats'], [self.support.id])
        self.assertEqual(a, b)


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3c')
class TestUpdatesP3cStrings(P3cCommon):
    """K7 (part) — no vendor name in the new sentences."""

    def test_K7_no_vendor_name(self):
        apply = self.env['pb.records.apply']
        for text in (apply._nobody_named_sentence(self.company),
                     apply._nobody_else_sentence(self.company)):
            self.assertNotIn('Odoo', text)
        for line in inspect.getsource(RA).splitlines():
            if '_(' in line or '_("' in line:
                self.assertNotIn('Odoo', line, line)
