# -*- coding: utf-8 -*-
"""UPDATES P6 — tests M4 and M5 (`UPDATES_P6_HANDOVER.md` §4).

M4. A client's admin may now edit the bank-details route. The second-person
rails are the code's, not the route's (P3a, P3c): a route edited BY A TENANT
ADMIN, THROUGH THE SCREEN'S OWN CALLS, to "No approval needed", to "the
proposer approves" (alone, with the platform support login and a demo login
beside them, independence off), and a Finance seat given to the proposer —
nothing is ever written without somebody other than the proposer, never the
support login or a demo login, saying yes. P3a F4-F7 and P3c K1-K4 themselves
run unchanged in `pb_updates` (M6); here they are re-asked under each edited
route.

M5. "Nobody else in <company> can approve bank details yet — add one in
Access" (and the named-route twin) carries a way out in the approvals inbox:
for the tenant admin, links to the places they can add that person; for
somebody who cannot, a plain sentence saying who to ask. Following the link
and adding the person lets the waiting change be approved by them.

Built on the P3a/P3c fixture (a company of its own, the proposer, a second
person holding Finance, the support login named by the platform's setting).
Skipped where the Updates module is not installed.
"""
import unittest

from odoo.exceptions import AccessError, UserError
from odoo.modules.registry import Registry
from odoo.tests import tagged
from odoo.tests.common import get_db_name

try:
    from odoo.addons.pb_updates.tests.test_updates_p3c import P3cCommon
    from odoo.addons.pb_updates.tests.test_updates_p3a import ACC
except ImportError:                                   # pragma: no cover
    P3cCommon = None
    ACC = 'b:acc_number'

TA_XMLID = 'pb_vendor_access.role_tenant_administrator'

if P3cCommon is None:                                 # pragma: no cover
    class _Base(unittest.TestCase):
        pass
else:
    _Base = P3cCommon


@tagged('post_install', '-at_install', 'pb_approval_config', 'p6')
class TestP6BankRails(_Base):

    @classmethod
    def setUpClass(cls):
        if P3cCommon is None or 'pb.updates.desk' not in Registry(
                get_db_name()):
            raise unittest.SkipTest('the Updates module is not installed')
        super().setUpClass()
        role = cls.env.ref(TA_XMLID, raise_if_not_found=False)
        if not role:
            raise unittest.SkipTest('no Tenant administrator role here')
        cls.ta_groups = role.sudo().group_ids | cls.env.ref('base.group_user')
        cls.ta = cls._ta('p6.tenant.admin', cls.company)
        cls.demo = cls._user('p6.demo', ('base.group_user',), cls.company)

    @classmethod
    def _ta(cls, login, company):
        return cls.env['res.users'].with_context(
            no_reset_password=True, mail_create_nosubscribe=True).create({
                'name': 'Tia Tenant', 'login': login,
                'email': '%s@example.com' % login,
                'company_id': company.id,
                'company_ids': [(6, 0, [company.id])],
                'group_ids': [(6, 0, cls.ta_groups.ids)]})

    def setUp(self):
        super().setUp()
        self.demo.group_ids = [(4, self.demo_group().id)]

    # ------------------------------------------------------------ helpers
    def _as(self, model, user, company):
        company = company or self.company
        return self.env[model].with_user(user).with_context(
            allowed_company_ids=[company.id])

    def matrix(self, user=None, company=None):
        return self._as('pb.approval.matrix', user or self.ta, company)

    def inbox(self, user, company=None):
        return self._as('pb.approval.inbox', user, company)

    def edit_bank_route(self, steps, independent=True, company=None,
                        user=None):
        """What the tenant admin does on the screen: open the bank-details
        row, change its draft, publish it."""
        company = company or self.company
        m = self.matrix(user, company)
        rows = {r['process_key']: r for a in m.get_matrix(company.id)['areas']
                for r in a['rows']}
        self.assertIn('records_bank', rows)
        wf = m.get_workflow(rows['records_bank']['workflow_id'])
        definition = wf['draft']['definition']
        definition['steps'] = steps
        definition['safeguards']['independent'] = independent
        saved = m.save_draft(wf['draft']['version_id'],
                             wf['draft']['draft_revision'], definition)
        self.assertFalse(saved['errors'], saved['errors'])
        preview = m.publication_preview(wf['draft']['version_id'])
        return m.publish(wf['draft']['version_id'], saved['draft_revision'],
                         None, 'P6 tenant admin edit',
                         [w['code'] for w in preview['warnings']])

    def people_step(self, users):
        return [{'key': 's1', 'kind': 'approve', 'title': 'Bank check',
                 'who': {'mode': 'people', 'user_ids': [u.id for u in users],
                         'all': False},
                 'min_amount': 0, 'condition': None}]

    def nothing_written(self, bank):
        self.fresh(bank)
        self.assertFalse(bank.applied)
        self.assertEqual(self.account(self.ann), '')

    def refused(self, bank, user):
        """`user` approving this bank change is refused — by the engine's
        call, and by the inbox's own Approve path."""
        request = bank.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        # AccessError is a UserError (one class per assertRaises, G43)
        with self.assertRaises(UserError):
            self.Engine.with_user(user).decide(request.id, step.key or 's1',
                                               'approve')
        with self.assertRaises(UserError):
            self.inbox(user).act('pb.records.apply', bank.id, 'approve')

    # ================================================================ M4
    def test_M4a_no_approval_needed_set_by_the_tenant_admin(self):
        res = self.matrix().set_no_approval_bulk(
            ['records_bank'], self.company.id, True, 'P6',
            ['money_fast'])
        self.assertEqual([d['process_key'] for d in res['done']],
                         ['records_bank'])
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        # F5b: approved by the route, carried out by nobody
        self.assertEqual(request.state, 'approved')
        self.assertIn('second person', request.block_reason or '')
        self.nothing_written(bank)
        # "Try again" by the proposer: the write still refuses (fail closed)
        self.Engine.with_user(self.proposer).retry_apply(request.id)
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        self.assertIn('second person', request.block_reason or '')
        self.nothing_written(bank)
        # the tenant admin's drawer offers no "Try again" that would fail
        drawer = self.inbox(self.ta).get_request(request.id, 'org')
        self.assertFalse(drawer['can_repair'])
        self.assertFalse(drawer['can_cancel'])
        # the personal details and pay lanes were not touched by this
        self.assertEqual(bank.lane, 'bank')

    def test_M4b_proposer_alone_on_the_route(self):
        self.edit_bank_route(self.people_step([self.proposer]),
                             independent=False)
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        # never widened, never the proposer (D14 + F4)
        self.assertEqual(request.state, 'blocked')
        self.assertIn('add a person to the bank details route',
                      request.block_reason)
        self.assertNotIn(self.proposer,
                         request.seat_ids.mapped('acting_user_id'))
        self.assertIn('second person',
                      bank._approval_may_decide(request, self.proposer))
        self.assertIn('second person', bank._bank_refusal(request))
        self.nothing_written(bank)

    def test_M4c_proposer_support_and_demo_named(self):
        self.edit_bank_route(
            self.people_step([self.proposer, self.demo]),
            independent=False)
        # the support login cannot even be named by the tenant admin
        with self.assertRaises(UserError):
            self.edit_bank_route(
                self.people_step([self.proposer, self.support]),
                independent=False)
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        seated = request.seat_ids.mapped('acting_user_id')
        for nobody in (self.proposer, self.demo, self.support):
            self.assertNotIn(nobody, seated)
        self.assertEqual(request.state, 'blocked')
        self.nothing_written(bank)

    def test_M4d_finance_given_to_the_proposer(self):
        """"The proposer approves" through the seat instead: F5c holds."""
        self.matrix().set_responsibility(self.company.id, 'finance', '',
                                         self.proposer.id)
        bank = self.parts(self.mixed())['bank']
        seats = self.seat_users(bank)
        self.assertNotIn(self.proposer, seats)
        self.assertIn(self.second, seats, 'a records manager stands in')
        # F4 — moved onto the proposer, still refused
        request = bank.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.Engine.sudo().reassign(request.id, seat.key, self.proposer.id,
                                    'P6 test')
        with self.assertRaisesRegex(UserError, 'second person'):
            self.Engine.with_user(self.proposer).decide(
                request.id, step.key, 'approve')
        self.nothing_written(bank)

    def test_M4e_support_and_demo_on_a_tenant_admin_route(self):
        """K2/K4 after the tenant admin's edit: seated by an approvals
        administrator anyway, their yes is refused by name."""
        self.edit_bank_route(self.people_step([self.proposer, self.second]),
                             independent=False)
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.assertEqual(self.seat_users(bank), self.second)
        for outsider in (self.support, self.demo):
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.Engine.sudo().reassign(request.id, seat.key, outsider.id,
                                        'P6 test')
            with self.assertRaisesRegex(UserError,
                                        'This login cannot approve'):
                self.Engine.with_user(outsider).decide(
                    request.id, step.key, 'approve')
        self.nothing_written(bank)

    def test_M4f_a_real_second_person_still_writes(self):
        """D13 on a tenant admin's route: one person other than the proposer
        is enough — the rails do not over-block."""
        self.edit_bank_route(self.people_step([self.proposer, self.second]),
                             independent=False)
        bank = self.parts(self.mixed())['bank']
        self.refused(bank, self.proposer)
        self.approve(bank, self.second)
        self.fresh(bank)
        self.assertTrue(bank.applied, bank.approval_request_id.block_reason)
        self.assertEqual(self.account(self.ann), '9988776655')

    def test_M4g_dated_change_on_a_fast_route(self):
        """F7 under "No approval needed": a dated bank change is not even
        scheduled without the second person."""
        self.matrix().set_no_approval_bulk(['records_bank'], self.company.id,
                                           True, 'P6', ['money_fast'])
        answer = self.mixed(start_date='2026-12-01', hold_scope='all')
        bank = self.parts(answer)['bank']
        self.fresh(bank)
        self.assertNotEqual(bank.state, 'scheduled')
        self.assertEqual(self.account(self.ann), '')

    # ================================================================ M5
    def lone(self):
        """K1's shape: only the proposer (and the support login holding
        Finance) work there when the change is sent. The tenant admin's
        login is made afterwards — a client admin is a records manager, so
        while they work there they are the second person themselves (the
        sentence then appears only for their OWN bank changes, D15)."""
        co, proposer, upd = self.lone_company('P6 Lone Co',
                                              finance=self.support)
        dee = self._person('P6 Dee', 'P6U01', co)
        bank = self.parts(self.send([['Code', 'Account'],
                                     ['P6U01', '4445556667']],
                                    {2: ACC}, upd=upd))['bank']
        self.assertEqual(bank.approval_request_id.state, 'blocked')
        ta = self._ta('p6.lone.admin', co)
        return co, proposer, ta, dee, bank

    def test_M5a_nobody_else_links_for_the_tenant_admin(self):
        co, proposer, ta, dee, bank = self.lone()
        request = bank.approval_request_id
        self.assertEqual(request.state, 'blocked')
        drawer = self.inbox(ta, co).get_request(request.id, 'org')
        fix = drawer['second_person_fix']
        self.assertEqual(fix['kind'], 'access')
        keys = [link['key'] for link in fix['links']]
        self.assertEqual(keys, ['access', 'people'])
        access = fix['links'][0]['action']
        self.assertEqual(access['tag'], 'pb_access_board')
        self.assertEqual(access['context'].get('pb_lens'), 'people')
        people = fix['links'][1]['action']
        self.assertEqual(people['tag'], 'pb_approval_matrix')
        self.assertEqual(people['params'], {'tab': 'people',
                                            'role_key': 'finance'})
        self.assertFalse(fix['ask'])
        # following it: the admin names a Finance approver of their own …
        fin = self._user('p6.lone.finance', ('base.group_user',), co)
        self.matrix(ta, co).set_responsibility(co.id, 'finance', '', fin.id)
        # … presses "Try again now it is set up" …
        self.assertTrue(drawer['can_repair'])
        mended = self.inbox(ta, co).repair(request.id)
        self.assertEqual(mended['state'], 'pending')
        self.assertNotIn(self.support,
                         request.seat_ids.mapped('acting_user_id'))
        # … and that person approves the waiting change
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self._as('biz.approval.engine', fin, co).decide(
            request.id, step.key, 'approve', 'ok')
        bank.invalidate_recordset()
        self.assertTrue(bank.applied, request.block_reason)
        self.assertEqual(self.account(dee), '4445556667')

    def test_M5b_nobody_else_without_the_right(self):
        co, proposer, ta, dee, bank = self.lone()
        drawer = self.inbox(proposer, co).get_request(
            bank.approval_request_id.id)
        fix = drawer['second_person_fix']
        self.assertEqual(fix['kind'], 'access')
        self.assertEqual(fix['links'], [])
        self.assertIn('Ask them to add one', fix['ask'])
        self.assertFalse(drawer['can_repair'])

    def test_M5c_named_route_twin(self):
        self.edit_bank_route(self.people_step([self.proposer]),
                             independent=False)
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        fix = self.inbox(self.ta).get_request(request.id, 'org')[
            'second_person_fix']
        self.assertEqual(fix['kind'], 'route')
        self.assertEqual([link['key'] for link in fix['links']], ['route'])
        params = fix['links'][0]['action']['params']
        self.assertEqual(params['workflow_id'],
                         request.version_id.workflow_id.id)
        self.assertEqual(params['process_key'], 'records_bank')
        mine = self.inbox(self.proposer).get_request(request.id)[
            'second_person_fix']
        self.assertEqual(mine['links'], [])
        self.assertTrue(mine['ask'])

    def test_M5d_other_stuck_requests_get_no_link(self):
        """Only these two sentences: a request stuck for another reason, or
        not stuck, offers nothing."""
        bank = self.parts(self.mixed())['bank']
        drawer = self.inbox(self.ta).get_request(
            bank.approval_request_id.id, 'org')
        self.assertIsNone(drawer['second_person_fix'])
