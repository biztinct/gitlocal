# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for the Leave Command Center facade (``pb.timeoff``).

Handover §6: 1 (non-officer AccessError on every RPC), 2 (queue lists
confirm+validate1 org-wide, other-company excluded), 3 (approve advances,
refuse-without-note raises), 4 (apply_on_behalf → confirm; overlap → core error,
no record), 5 (balance math; non-allocation types absent).
"""

from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTimeoff(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Leave = cls.env['hr.leave']
        cls.Alloc = cls.env['hr.leave.allocation']

        # a DEDICATED company so the org-wide board is deterministic on the shared
        # live DB — the queue/balance scope is exactly this one company. Reuse the
        # company's auto-created Standard 40h calendar (a bare calendar has no
        # working hours → leaves compute 0 days → core refuses to validate).
        cls.company = cls.env['res.company'].create({'name': 'K Timeoff Co'})
        cls.cal = cls.company.resource_calendar_id or cls.env.ref(
            'resource.resource_calendar_std', raise_if_not_found=False)
        # THE OFFICER THESE CASES ACT AS IS THE ADMINISTRATOR, NOT THE TEST
        # ENVIRONMENT'S OWN USER. That one is the platform's background account,
        # which is not active — and a route refuses a decision from an account
        # that is no longer in use, whoever it is (ledger AM102). Leaves are
        # still filed as the background account, so the person deciding them
        # is never the person who sent them in.
        cls.officer = cls.env.ref('base.user_admin')
        cls.officer.write({'company_ids': [(4, cls.company.id)]})
        # pin the facade to this company (env.companies drives the C18.11 scope)
        cls.TO = cls.env['pb.timeoff'].with_user(cls.officer).with_context(
            allowed_company_ids=[cls.company.id]).with_company(cls.company)

        cls.unpaid = cls.env['hr.leave.type'].create({
            'name': 'K Unpaid', 'requires_allocation': False,
            'leave_validation_type': 'hr', 'company_id': cls.company.id})
        cls.annual = cls.env['hr.leave.type'].create({
            'name': 'K Annual', 'requires_allocation': True,
            'leave_validation_type': 'hr', 'allocation_validation_type': 'hr',
            'company_id': cls.company.id})

        cls.emp = cls.env['hr.employee'].create({
            'name': 'Leave Emp', 'company_id': cls.company.id,
            'resource_calendar_id': cls.cal.id if cls.cal else False})

        # A weekday-anchored FUTURE window for the queue leaves, worked out
        # from today rather than written down. It used to be a fixed date in
        # August 2026, which stopped being the future in August 2026: an
        # allocation starts the day it is made, so a leave in the past is a
        # leave with no allocation covering it, and `test_05` failed with
        # "You do not have any allocation for this time off type" for a reason
        # that had nothing to do with the balance arithmetic it was testing.
        anchor = date.today() + timedelta(days=7)
        cls.mon = anchor - timedelta(days=anchor.weekday())

        # PHASE 6: time off travels a published route now, and this suite's
        # own officer is the person that route asks. The seed names whoever
        # held the officer group when the company was made — which, for a
        # company made a line ago, is nobody. Name the person these cases act
        # as, so `act()` is deciding a step that is really theirs.
        role = cls.env['biz.approval.role'].sudo().search(
            [('key', '=', 'hr_lead')], limit=1)
        if role:
            cls.env['biz.approval.responsibility'].sudo().search([
                ('company_id', '=', cls.company.id),
                ('role_id', '=', role.id)]).write({'active': False})
            cls.env['biz.approval.responsibility'].sudo().create({
                'company_id': cls.company.id, 'role_id': role.id,
                'scope_key': '', 'scope_label': cls.company.name,
                'user_id': cls.officer.id,
            })

    def _confirm_leave(self, emp=None, dfrom=None, dto=None, ltype=None):
        return self.Leave.create({
            'employee_id': (emp or self.emp).id,
            'holiday_status_id': (ltype or self.unpaid).id,
            'request_date_from': dfrom or self.mon,
            'request_date_to': dto or (self.mon + timedelta(days=1)),
            'name': 'x'})

    # ------------------------------------------------------------- §6.1 gate
    def test_01_non_officer_blocked(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Plain TO', 'login': 'to_plain',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        TO = self.TO.with_user(user)
        with self.assertRaises(AccessError):
            TO.get_board()
        with self.assertRaises(AccessError):
            TO.act(1, 'approve')
        with self.assertRaises(AccessError):
            TO.apply_on_behalf(self.emp.id, self.annual.id,
                               self.mon.isoformat(), self.mon.isoformat())
        with self.assertRaises(AccessError):
            TO.search_employees('a')

    # ------------------------------------------------------------- §6.2 queue
    def test_02_queue_scope(self):
        lv = self._confirm_leave()
        # another company's leave must be excluded (C18.11/18)
        co2 = self.env['res.company'].create({'name': 'K Co2'})
        emp2 = self.env['hr.employee'].create({
            'name': 'Other Co Emp', 'company_id': co2.id,
            'resource_calendar_id': (co2.resource_calendar_id or self.cal).id})
        # emp2's leave uses co2's own type (its type is company-scoped)
        t2 = self.env['hr.leave.type'].create({
            'name': 'Co2 Unpaid', 'requires_allocation': False,
            'leave_validation_type': 'hr', 'company_id': co2.id})
        self._confirm_leave(emp=emp2, ltype=t2)
        board = self.TO.get_board(self.mon.strftime('%Y-%m'))
        ids = [q['id'] for q in board['queue']]
        self.assertIn(lv.id, ids)
        self.assertTrue(all(q['employee']['id'] != emp2.id for q in board['queue']))
        # queue items carry state + card
        item = next(q for q in board['queue'] if q['id'] == lv.id)
        self.assertEqual(item['state'], 'confirm')
        self.assertEqual(item['employee']['name'], 'Leave Emp')

    # ------------------------------------------------------------- §6.3 act
    def test_03_approve_and_refuse(self):
        lv = self._confirm_leave()
        res = self.TO.act(lv.id, 'approve')
        self.assertTrue(res['ok'])
        self.assertIn(lv.state, ('validate', 'validate1'))
        # refuse requires a note
        lv2 = self._confirm_leave(dfrom=self.mon + timedelta(days=7),
                                  dto=self.mon + timedelta(days=8))
        with self.assertRaises(UserError):
            self.TO.act(lv2.id, 'refuse', note='')
        out = self.TO.act(lv2.id, 'refuse', note='Not this week')
        self.assertTrue(out['ok'])
        self.assertEqual(lv2.state, 'refuse')

    # ------------------------------------------------------------- §6.4 apply
    def test_04_apply_on_behalf(self):
        res = self.TO.apply_on_behalf(
            self.emp.id, self.unpaid.id,
            (self.mon + timedelta(days=14)).isoformat(),
            (self.mon + timedelta(days=15)).isoformat(), note='Filed')
        self.assertTrue(res['ok'])
        self.assertEqual(res['state'], 'confirm')
        before = self.Leave.search_count([('employee_id', '=', self.emp.id)])
        # an overlapping second leave → core raises, no new record. The savepoint
        # keeps the test cursor usable if the raise happens at SQL flush.
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.TO.apply_on_behalf(
                    self.emp.id, self.unpaid.id,
                    (self.mon + timedelta(days=14)).isoformat(),
                    (self.mon + timedelta(days=15)).isoformat())
        after = self.Leave.search_count([('employee_id', '=', self.emp.id)])
        self.assertEqual(before, after)

    # ------------------------------------------------------------- §6.5 balance
    def test_05_balance_math(self):
        alloc = self.Alloc.create({
            'name': 'K alloc', 'employee_id': self.emp.id,
            'holiday_status_id': self.annual.id, 'number_of_days': 12.0})
        alloc.action_approve()
        taken = self.Leave.create({
            'employee_id': self.emp.id, 'holiday_status_id': self.annual.id,
            'request_date_from': self.mon, 'request_date_to': self.mon + timedelta(days=2),
            'name': 'taken'})
        for _ in range(2):
            if taken.state == 'validate':
                break
            taken.with_user(self.officer).action_approve()
        taken_days = taken.number_of_days
        data = self.TO._balances(0)
        type_ids = [t['id'] for t in data['types']]
        self.assertIn(self.annual.id, type_ids)
        self.assertNotIn(self.unpaid.id, type_ids)   # non-allocation type absent
        # the balance board is paged — walk pages until the test employee shows
        row, page = None, 0
        while row is None:
            row = next((r for r in data['rows'] if r['id'] == self.emp.id), None)
            if row is not None or not data.get('has_more'):
                break
            page += 1
            data = self.TO._balances(page)
        self.assertIsNotNone(row)
        cell = row['cells'][self.annual.id]
        self.assertAlmostEqual(cell['allocated'], 12.0)
        self.assertAlmostEqual(cell['taken'], taken_days)
        self.assertAlmostEqual(cell['balance'], round(12.0 - taken_days, 2))
