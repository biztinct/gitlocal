# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ETP E2 — business trips on My Payobook (handover
docs/handovers/etp/E2_HANDOVER.md).

E2.1 preview = the record's computes · E2.2 new_trip as an employee login ·
E2.3 policy_for and the card's words · E2.4 send → the route → authorised /
refused → fix and resend · E2.5 overlaps · E2.6 take back · E2.7 ownership ·
E2.8 the pages over HTTP as an employee login AND a full account (T-R6) ·
E2.9 the "Claim receipts" link follows the expenses module.

The route: every suite lays the trip module's own default route for its
company (`_approval_seed_default`, idempotent — a suite never depends on which
migration ran, ledger AM70) and seats its own finance approver and HR lead.
"""
from datetime import date, timedelta
from urllib.parse import urlparse

from lxml import html as lxml_html

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import (
    _make_share, _pin_dbfilter,
)
from odoo.addons.pb_me_portal.tests.test_portal_only import (
    PASSWORD as T1_PASSWORD, _make_people,
)

PASSWORD = 'etp-e2-trip-probe-2026'

# Tuesday–Thursday, far enough ahead that no fixture on a clone collides
D1 = date(2027, 3, 9)
D3 = date(2027, 3, 11)


class _TripCommon:

    @classmethod
    def _fixtures(cls, prefix, password=None):
        env = cls.env
        cls.company = env.company
        Users = env['res.users'].with_context(no_reset_password=True)
        internal = env.ref('base.group_user')

        def user(login, name, *groups):
            # the route's finance approver and HR lead hold the groups the
            # default route seeds them from (pb_business_trip_approval.py):
            # a seat alone is a READ (trip_rule_seat), and following the route
            # writes the trip's status as the person deciding
            ids = [internal.id] + [env.ref(g).id for g in groups]
            vals = {'name': name, 'login': login, 'group_ids': [(6, 0, ids)]}
            if password:
                vals['password'] = password
            return Users.create(vals)

        cls.share, cls.share_emp = _make_share(env, '%s_share' % prefix, 'Quinn Trip Share', password)
        cls.plain, cls.plain_emp, _lead, _staff = _make_people(
            env, prefix, password=T1_PASSWORD if password else None)
        cls.mgr_user = user('%s_mgr' % prefix, 'Lan Trip Manager')
        cls.fin_user = user('%s_fin' % prefix, 'Minh Trip Finance',
                            'om_hr_payroll.group_hr_payroll_manager')
        cls.hr_user = user('%s_hrl' % prefix, 'Hoa Trip HR Lead', 'hr.group_hr_manager')
        Emp = env['hr.employee']
        cls.mgr_emp = Emp.create({'name': 'Lan Trip Manager', 'user_id': cls.mgr_user.id,
                                  'company_id': cls.company.id})
        (cls.share_emp | cls.plain_emp).write({'parent_id': cls.mgr_emp.id})

        # the route, laid explicitly, with this suite's own role holders
        env['pb.business.trip']._approval_seed_default(cls.company)
        Resp = env['biz.approval.responsibility'].sudo()
        for key, holder in (('finance', cls.fin_user), ('hr_lead', cls.hr_user)):
            role = env['biz.approval.role'].sudo().search([('key', '=', key)], limit=1)
            Resp.search([('company_id', '=', cls.company.id), ('role_id', '=', role.id)]).write(
                {'active': False})
            Resp.create({'company_id': cls.company.id, 'role_id': role.id, 'scope_key': '',
                         'scope_label': cls.company.name, 'user_id': holder.id})

        cls.vn = env.ref('base.vn')
        cls.cat_lodging = env.ref('pb_business_trip.cat_lodging')
        cls.cat_transport = env.ref('pb_business_trip.cat_transport')
        cls.Trips = env['pb.me.trip']

    def _values(self, d_from=D1, d_to=D3, city='Đà Nẵng', country=None, **extra):
        values = {
            'destination_country_id': str((country or self.vn).id),
            'destination_city': city,
            'date_from': d_from.isoformat(),
            'date_to': d_to.isoformat(),
            'purpose': 'Meet the client team and run the quarterly review.',
            'advance_amount': '2000000',
        }
        values.update(extra)
        return values

    def _lines(self):
        return [
            {'category_id': str(self.cat_lodging.id), 'amount': '1200000', 'description': 'Hotel, 2 nights'},
            {'category_id': str(self.cat_transport.id), 'amount': '1750000', 'description': 'Flights'},
            {'category_id': '', 'amount': '', 'description': ''},     # an empty row is dropped
        ]

    def _as(self, user):
        return self.Trips.with_user(user)

    def _new(self, user, emp, **kw):
        lines = kw.pop('lines', None)
        return self._as(user).new_trip(emp, self._values(**kw),
                                       self._lines() if lines is None else lines)

    def _approve_all(self, trip):
        trip.with_user(self.mgr_user).action_manager_approve()
        trip.with_user(self.fin_user).action_finance_approve()
        trip.with_user(self.hr_user).action_hr_approve()

    def _bindings(self):
        process = self.env['biz.approval.process']._by_key('trip')
        return self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id), ('process_id', '=', process.id)])


@tagged('post_install', '-at_install')
class TestMeTripModel(_TripCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixtures('test_e2_model')

    # E2.1
    def test_e2_1_preview_equals_the_record(self):
        trip = self._new(self.share, self.share_emp)
        policy = self._as(self.share).policy_for(self.share_emp, self.vn.id, False)
        pre = self.Trips.preview({'date_from': D1, 'date_to': D3, 'per_diem_rate': policy['rate'],
                                  'line_amounts': [1200000, 1750000], 'advance_amount': 2000000})
        self.assertEqual(pre['days'], 3)
        self.assertEqual(pre['days'], trip.duration_days)
        self.assertEqual(pre['rate'], trip.per_diem_rate)
        self.assertAlmostEqual(pre['allowance'], trip.per_diem_total)
        self.assertAlmostEqual(pre['estimated'], trip.estimated_total)
        self.assertAlmostEqual(pre['lines_total'], sum(trip.line_ids.mapped('amount')))
        self.assertAlmostEqual(pre['advance'], trip.advance_amount)
        card = self._as(self.share).card(trip)
        self.assertEqual(card['money']['allowance'],
                         self.Trips.fmt_money(trip.per_diem_total, trip.currency_id))
        self.assertEqual(card['money']['estimated'],
                         self.Trips.fmt_money(trip.estimated_total, trip.currency_id))

    # E2.2
    def test_e2_2_new_trip_as_an_employee_login(self):
        trip = self._as(self.share).new_trip(
            self.share_emp,
            self._values(state='approved', employee_id=str(self.plain_emp.id),
                         manager_id=str(self.plain_emp.id), name='FORGED', per_diem_rate='999',
                         company_id='999'),
            self._lines())
        self.assertEqual(trip.employee_id, self.share_emp)
        self.assertEqual(trip.company_id, self.share_emp.company_id)
        self.assertTrue(trip.name.startswith('BT/'), trip.name)
        self.assertEqual(trip.create_uid, self.share, 'sudo keeps the uid')
        self.assertEqual(trip.state, 'draft', 'state is never taken from the request')
        self.assertEqual(len(trip.line_ids), 2)
        self.assertEqual(trip.line_ids.mapped('date'), [D1, D1])
        self.assertEqual(trip.policy_id.country_id, self.vn)
        self.assertNotEqual(trip.per_diem_rate, 999)
        self.assertEqual(trip.manager_id, self.mgr_emp)
        Trip = self.env['pb.business.trip']
        before = Trip.search_count([('employee_id', '=', self.share_emp.id)])
        with self.assertRaises(UserError) as caught:
            self._as(self.share).new_trip(self.share_emp, self._values(d_from=D3, d_to=D1), [])
        self.assertIn('cannot end before it starts', str(caught.exception))
        for bad, words in (({'purpose': '  '}, 'why you are travelling'),
                           ({'destination_city': ''}, 'city'),
                           ({'destination_country_id': ''}, 'country')):
            with self.assertRaises(UserError) as caught:
                self._as(self.share).new_trip(self.share_emp, self._values(**bad), [])
            self.assertIn(words, str(caught.exception))
        with self.assertRaises(UserError) as caught:
            self._as(self.share).new_trip(self.share_emp, self._values(), [
                {'category_id': str(self.cat_lodging.id), 'amount': '', 'description': 'Hotel'}])
        self.assertIn('needs an amount', str(caught.exception))
        self.assertEqual(Trip.search_count([('employee_id', '=', self.share_emp.id)]), before)
        # somebody else's employee is refused outright
        with self.assertRaises(AccessError):
            self._as(self.share).new_trip(self.plain_emp, self._values(), [])

    # E2.3
    def test_e2_3_policy_for_and_the_card_words(self):
        Policy = self.env['pb.trip.policy']
        as_share = self._as(self.share)
        tier1 = as_share.policy_for(self.share_emp, self.vn.id, True)
        other = as_share.policy_for(self.share_emp, self.vn.id, False)
        self.assertEqual(tier1['policy'], Policy._match(self.vn, self.company, 'tier1'))
        self.assertEqual(other['policy'], Policy._match(self.vn, self.company, False))
        self.assertTrue(tier1['has_tier1'])
        self.assertEqual(tier1['tier'], 'tier1')
        if not Policy.search_count([('country_id', '=', self.vn.id), ('company_id', '=', self.company.id)]):
            # the shipped global seeds (pb_trip_policy_data.xml)
            self.assertEqual(tier1['policy'], self.env.ref('pb_business_trip.policy_vn_tier1'))
            self.assertEqual(tier1['rate'], 200000)
            self.assertEqual(other['policy'], self.env.ref('pb_business_trip.policy_vn_other'))
            self.assertEqual(other['rate'], 150000)
            self.assertEqual(other['channel'], 'payroll')
        # a country no policy names → the global fallback (or none)
        nowhere = self.env.ref('base.aq')
        fallback = as_share.policy_for(self.share_emp, nowhere.id, True)
        self.assertEqual(fallback['policy'], Policy._match(nowhere, self.company, False))
        self.assertFalse(fallback['has_tier1'], 'the tier counts only where a tier-1 rate exists')
        if not fallback['policy']:
            self.assertEqual((fallback['rate'], fallback['channel']), (0.0, 'none'))
            self.assertEqual(fallback['currency'], self.company.currency_id)
        # the words follow per_diem_channel
        fr = self.env.ref('base.fr')
        Policy.create({'name': 'E2 France', 'country_id': fr.id, 'per_diem_rate': 60.0,
                       'currency_id': self.company.currency_id.id,
                       'per_diem_channel': 'expense', 'company_id': self.company.id})
        paris = self._new(self.share, self.share_emp, city='Paris', country=fr, lines=[])
        vn_trip = self._new(self.share, self.share_emp, d_from=D1 + timedelta(days=30),
                            d_to=D3 + timedelta(days=30), lines=[])
        QWeb = self.env['ir.qweb']
        words = {}
        for trip in (paris, vn_trip):
            html = str(QWeb._render('pb_me_trip.pbtr_card', {
                'card': as_share.card(trip), 'live': False, 'status': None, 'done': None}))
            words[trip.id] = html
        self.assertIn('Claimed as an expense after the trip', words[paris.id])
        self.assertNotIn('Paid with your salary', words[paris.id])
        self.assertIn('Paid with your salary', words[vn_trip.id])
        self.assertNotIn('Claimed as an expense', words[vn_trip.id])
        self.assertEqual(paris.per_diem_rate, 60.0)
        self.assertEqual(paris.currency_id, self.company.currency_id)
        # the live card's facts carry the same answers
        facts = as_share.policy_map(self.share_emp)
        self.assertEqual(facts['countries'][str(fr.id)]['base']['channel'], 'expense')
        self.assertIsNone(facts['countries'][str(fr.id)]['tier1'])
        self.assertEqual(facts['countries'][str(self.vn.id)]['tier1']['rate'], tier1['rate'])

    # E2.4
    def test_e2_4_send_route_authorised(self):
        as_share = self._as(self.share)
        trip = self._new(self.share, self.share_emp)
        draft = as_share.status(trip)
        self.assertEqual(draft['label'], 'Draft')
        self.assertTrue(draft['can']['send'] and draft['can']['edit'])
        self.assertEqual([s['state'] for s in draft['steps']], ['todo'] * len(draft['steps']),
                         'a draft shows who will be asked')
        as_share.send(trip)
        self.assertEqual(trip.state, 'submitted')
        req = trip.approval_request_id
        self.assertTrue(req, 'with a route, sending makes ONE request')
        self.assertEqual(self.env['biz.approval.request'].search_count(
            [('res_model', '=', 'pb.business.trip'), ('res_id', '=', trip.id)]), 1)
        self.assertEqual(req.state, 'pending')
        self.assertEqual(req.submitter_uid, self.share, 'the submitter is the employee login')
        steps = req.step_ids.filtered('included').sorted('sequence')
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0].seat_ids.acting_user_id, self.mgr_user)
        self.assertEqual(steps[1].seat_ids.acting_user_id, self.fin_user)
        self.assertEqual(steps[2].seat_ids.acting_user_id, self.hr_user)
        st = as_share.status(trip)
        self.assertEqual((st['label'], st['tone']), ('Waiting approval', 'wait'))
        self.assertEqual([s['name'] for s in st['steps']],
                         ['Sent in'] + steps.mapped('title') + ['Approved'])
        self.assertEqual(st['steps'][1]['who'], self.mgr_user.name)
        self.assertEqual(st['steps'][1]['state'], 'current')
        self.assertEqual(st['current']['who'], self.mgr_user.name)
        self.assertTrue(st['can']['withdraw'])
        self.assertFalse(st['can']['edit'])

        trip.with_user(self.mgr_user).action_manager_approve()
        self.assertEqual(trip.state, 'manager_approved')
        self.assertEqual(as_share.status(trip)['label'], 'With finance')
        trip.with_user(self.fin_user).action_finance_approve()
        self.assertEqual(trip.state, 'finance_approved')
        self.assertEqual(as_share.status(trip)['label'], 'With HR')
        trip.with_user(self.hr_user).action_hr_approve()
        self.assertEqual(trip.state, 'approved')
        st = as_share.status(trip)
        self.assertEqual((st['label'], st['tone']), ('Authorised', 'ok'))
        self.assertEqual(st['attendance_sentence'],
                         'Your attendance is marked automatically for every trip day.')
        self.assertEqual([s['state'] for s in st['steps']], ['done'] * 5)
        self.assertFalse(st['can']['withdraw'])
        self.assertTrue(st['can']['ask_hr_cancel'])

    def test_e2_4b_refuse_fix_and_resend(self):
        as_share = self._as(self.share)
        trip = self._new(self.share, self.share_emp)
        as_share.send(trip)
        trip.with_user(self.mgr_user).action_refuse_chain(note='Too close to the quarter end.')
        self.assertEqual(trip.state, 'refused')
        st = as_share.status(trip)
        self.assertEqual((st['label'], st['tone']), ('Refused — your turn', 'act'))
        self.assertEqual(st['reason'], 'Too close to the quarter end.')
        self.assertEqual(st['reason_by'], self.mgr_user.name)
        self.assertEqual(st['steps'][1]['state'], 'stopped')
        self.assertTrue(st['can']['reopen'])
        with self.assertRaises(UserError):
            as_share.update_trip(trip, self._values(city='Huế'), [])
        as_share.reopen(trip)
        self.assertEqual(trip.state, 'draft')
        as_share.update_trip(trip, self._values(city='Huế', d_from=D1 + timedelta(days=7),
                                                d_to=D3 + timedelta(days=7)), [])
        self.assertEqual(trip.destination_city, 'Huế')
        self.assertFalse(trip.line_ids, 'a list replaces the lines')
        as_share.send(trip)
        self.assertEqual(trip.state, 'submitted')
        self.assertEqual(trip.approval_request_id.attempt, 2)
        self.assertEqual(trip.approval_request_id.state, 'pending')
        with self.assertRaises(UserError):
            as_share.reopen(trip)

    def test_e2_4c_fixed_ladder_without_a_route(self):
        self._bindings().write({'active': False})
        try:
            as_share = self._as(self.share)
            trip = self._new(self.share, self.share_emp)
            as_share.send(trip)
            self.assertEqual(trip.state, 'submitted')
            self.assertFalse(trip.approval_request_id, 'no route, no request')
            st = as_share.status(trip)
            self.assertEqual([s['name'] for s in st['steps']],
                             ['Sent in', 'Their manager', 'Finance approver', 'HR lead', 'Approved'])
            self.assertEqual(st['steps'][1]['who'], self.mgr_emp.name)
            self.assertEqual(st['steps'][1]['state'], 'current')
            trip.with_user(self.mgr_user).action_manager_approve()
            self.assertEqual(as_share.status(trip)['steps'][1]['state'], 'done')
        finally:
            self._bindings().write({'active': True})

    def test_e2_4d_a_blocked_route_says_so(self):
        """Nobody holds Finance approver → the request is stuck: the page says
        it in words, offers Ask HR (template) and take back (E-R4)."""
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'finance')], limit=1)
        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id), ('role_id', '=', role.id)])
        held.write({'active': False})
        as_share = self._as(self.share)
        trip = self._new(self.share, self.share_emp)
        as_share.send(trip)
        self.assertEqual(trip.state, 'submitted')
        self.assertEqual(trip.approval_request_id.state, 'blocked')
        st = as_share.status(trip)
        self.assertEqual((st['key'], st['label'], st['tone']), ('blocked', 'Nobody to approve yet', 'act'))
        self.assertTrue(st['block_reason'])
        self.assertIn('blocked', [s['state'] for s in st['steps']])
        self.assertTrue(st['can']['withdraw'])
        as_share.withdraw(trip)
        self.assertEqual(trip.state, 'cancelled')
        self.assertEqual(trip.approval_request_id.state, 'cancelled')

    # E2.5
    def test_e2_5_overlaps(self):
        as_share = self._as(self.share)
        first = self._new(self.share, self.share_emp)
        as_share.send(first)
        second = self._new(self.share, self.share_emp, city='Hội An',
                           d_from=D1 + timedelta(days=1), d_to=D3 + timedelta(days=1))
        with self.assertRaises(UserError) as caught:
            as_share.send(second)
        message = str(caught.exception)
        self.assertIn(self.Trips.dates_label(D1, D3), message, 'the reason names the dates')
        self.assertIn('Đà Nẵng', message, 'and the other trip')
        self.assertEqual(second.state, 'draft')

        leave_type = self.env['hr.leave.type'].sudo().create(
            {'name': 'E2 Trip Leave', 'requires_allocation': False})
        d5, d6 = D1 + timedelta(days=14), D1 + timedelta(days=15)
        leave = self.env['hr.leave'].sudo().create({
            'name': 'x', 'holiday_status_id': leave_type.id, 'employee_id': self.share_emp.id,
            'request_date_from': d5, 'request_date_to': d6})
        leave.sudo().write({'state': 'validate'})
        third = self._new(self.share, self.share_emp, city='Huế', d_from=d5, d_to=d6, lines=[])
        as_share.send(third)
        self.assertEqual(third.state, 'submitted', 'a leave over the days never blocks')
        self.assertEqual(as_share.status(third)['leave_overlap'], 'E2 Trip Leave')
        self.assertTrue(third.message_ids.filtered(lambda m: 'overlaps an approved leave' in (m.body or '')),
                        'stock still posts its note for HR')

    # E2.6
    def test_e2_6_take_back(self):
        as_share = self._as(self.share)
        trip = self._new(self.share, self.share_emp)
        as_share.send(trip)
        req = trip.approval_request_id
        with self.assertRaises(UserError):
            as_share.update_trip(trip, self._values(city='Huế'), [])
        as_share.withdraw(trip)
        self.assertEqual(trip.state, 'cancelled')
        req.invalidate_recordset()
        self.assertNotEqual(req.state, 'pending', 'the request is withdrawn with the trip')
        self.assertEqual(req.state, 'cancelled')
        st = as_share.status(trip)
        self.assertEqual((st['label'], st['tone']), ('Taken back', 'off'))
        with self.assertRaises(UserError):
            as_share.withdraw(trip)

        approved = self._new(self.share, self.share_emp, d_from=D1 + timedelta(days=40),
                             d_to=D3 + timedelta(days=40), lines=[])
        as_share.send(approved)
        self._approve_all(approved)
        with self.assertRaises(UserError) as caught:
            as_share.withdraw(approved)
        self.assertIn('Ask HR to cancel it', str(caught.exception))
        self.assertEqual(approved.state, 'approved')

    def test_e2_6b_withdrawn_in_the_inbox_is_shown_truthfully(self):
        as_share = self._as(self.share)
        trip = self._new(self.share, self.share_emp)
        as_share.send(trip)
        # the inbox's "Withdraw" (engine.cancel) leaves the trip "submitted"
        self.env['biz.approval.engine'].with_user(self.share).sudo().cancel(
            trip.approval_request_id.id, 'Changed my mind')
        self.assertEqual(trip.state, 'submitted')
        st = as_share.status(trip)
        self.assertEqual(st['key'], 'withdrawn')
        self.assertEqual(st['label'], 'Taken back from Approvals')
        self.assertTrue(st['can']['reopen'])
        as_share.reopen(trip)
        self.assertEqual(trip.state, 'draft')

    # E2.7
    def test_e2_7_ownership(self):
        theirs = self._new(self.plain, self.plain_emp)
        as_share = self._as(self.share)
        self.assertIsNone(as_share.status(theirs))
        self.assertIsNone(as_share.card(theirs))
        self.assertEqual(as_share.lines(theirs), [])
        self.assertFalse(as_share.get_trip(self.share_emp, theirs.id))
        for call in (lambda: as_share.send(theirs), lambda: as_share.withdraw(theirs),
                     lambda: as_share.reopen(theirs),
                     lambda: as_share.update_trip(theirs, self._values(), []),
                     lambda: as_share.add_line(theirs, {'amount': '5'}),
                     lambda: as_share.remove_line(theirs, theirs.line_ids[:1].id)):
            with self.assertRaises(AccessError):
                call()
        self.assertEqual(theirs.state, 'draft')
        self.assertEqual(len(theirs.line_ids), 2)
        self.assertNotIn(theirs.id, [r['id'] for r in as_share.own_trips(self.share_emp)['rows']])
        # the employee login has no ACL of its own on trips (E-R2)
        with self.assertRaises(AccessError):
            self.env['pb.business.trip'].with_user(self.share).search([])
        portal = self.env.ref('base.group_portal')
        self.assertFalse(self.env['ir.model.access'].sudo().search([
            ('model_id.model', 'in', ('pb.business.trip', 'pb.business.trip.line')),
            ('group_id', '=', portal.id)]))

    # D7 — the home hooks
    def test_e2_d7_home_hooks(self):
        as_share = self._as(self.share)
        trip = self._new(self.share, self.share_emp)
        as_share.send(trip)
        Home = self.env['pb.me.home'].with_user(self.share)
        rows = [r for r in Home.get_my_requests(self.share_emp)['rows'] if r['key'] == 'trip']
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['state_label'], rows[0]['tone']), ('Waiting approval', 'wait'))
        self.assertEqual(rows[0]['url'], '/my/trips/%s' % trip.id)
        self.assertEqual(rows[0]['title'], 'Trip · Đà Nẵng · %s' % self.Trips.dates_label(D1, D3))
        trip.with_user(self.mgr_user).action_refuse_chain(note='No budget')
        row = [r for r in Home.get_my_requests(self.share_emp)['rows'] if r['key'] == 'trip'][0]
        self.assertEqual((row['state_label'], row['tone']), ('Refused — your turn', 'act'))
        needs = Home.get_home_data(self.share_emp)['needs_you']
        need = [n for n in needs if n['key'] == 'trip_refused']
        self.assertEqual(len(need), 1)
        self.assertEqual(need[0]['label'], '1 trip request refused — fix and resend')
        self.assertEqual(need[0]['url'], '/my/trips/%s' % trip.id)
        # quiet at zero: no "next trip" card without an authorised trip soon
        cards = Home.get_home_data(self.share_emp)['extra_cards']
        self.assertFalse([c for c in cards if c['key'] == 'next_trip'])
        today = self.Trips._today(self.share_emp)
        soon = self._new(self.share, self.share_emp, d_from=today + timedelta(days=6),
                         d_to=today + timedelta(days=8), lines=[])
        as_share.send(soon)
        self.assertFalse([c for c in Home.get_home_data(self.share_emp)['extra_cards']
                          if c['key'] == 'next_trip'], 'not before it is authorised')
        self._approve_all(soon)
        cards = [c for c in Home.get_home_data(self.share_emp)['extra_cards'] if c['key'] == 'next_trip']
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['data']['in_days'], 6)
        self.assertEqual(cards[0]['template'], 'pb_me_trip.pbme_card_next_trip')
        far = self._new(self.share, self.share_emp, d_from=today + timedelta(days=60),
                        d_to=today + timedelta(days=61), lines=[])
        as_share.send(far)
        self._approve_all(far)
        nxt = as_share.next_trip(self.share_emp)
        self.assertEqual(nxt['id'], soon.id, 'the nearest one within 14 days')


@tagged('post_install', '-at_install')
class TestMeTripPages(_TripCommon, HttpCase):
    """E2.7 (routes), E2.8, E2.9 — over HTTP, as an employee login and as a
    full account (T-R6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls._fixtures('test_e2_http', PASSWORD)

    def _post(self, url, data=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, timeout=60)

    def _text(self, response):
        return (response.text or '').replace('&#39;', "'").replace('&amp;', '&')

    def _form(self, d_from=D1, d_to=D3, action='send', **extra):
        data = {
            'destination_country_id': str(self.vn.id),
            'destination_city': 'Đà Nẵng',
            'date_from': d_from.isoformat(),
            'date_to': d_to.isoformat(),
            'purpose': 'Meet the client team and run the quarterly review.',
            'line-0-category': str(self.cat_lodging.id),
            'line-0-amount': '1200000',
            'line-0-note': 'Hotel, 2 nights',
            'advance_amount': '2000000',
            'action': action,
        }
        data.update(extra)
        return data

    def _flow(self, user, password, emp):
        self.authenticate(user.login, password)
        Trip = self.env['pb.business.trip']
        page = self.url_open('/my/trips', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('No trips yet', page.text)
        self.assertIn('When you need to travel for work, ask here and your manager sees it at once.',
                      self._text(page))

        new = self.url_open('/my/trips/new', timeout=60)
        self.assertEqual(new.status_code, 200)
        for field in ('name="destination_country_id"', 'name="destination_city"', 'name="date_from"',
                      'name="date_to"', 'name="purpose"', 'name="line-0-amount"',
                      'name="line-0-category"', 'name="advance_amount"', 'data-pbtr-card="1"',
                      'data-pbtr-facts='):
            self.assertIn(field, new.text)
        self.assertIn('Leave blank if you do not need money up front.', new.text)

        # the no-script path: "Add a line" redraws with one more row, writes nothing
        more = self._post('/my/trips/new', self._form(action='add_line'))
        self.assertEqual(more.status_code, 200)
        self.assertIn('name="line-1-amount"', more.text)
        self.assertIn('value="1200000"', more.text, 'what was typed is kept')
        self.assertFalse(Trip.search([('employee_id', '=', emp.id)]))

        # a refused answer comes back with its reason, nothing created
        bad = self._post('/my/trips/new', self._form(d_from=D3, d_to=D1))
        self.assertEqual(bad.status_code, 200)
        self.assertIn('cannot end before it starts', self._text(bad))
        self.assertFalse(Trip.search([('employee_id', '=', emp.id)]))

        response = self._post('/my/trips/new', self._form(
            employee_id=str(self.plain_emp.id if emp != self.plain_emp else self.share_emp.id),
            state='approved'))
        self.assertEqual(response.status_code, 200)
        trip = Trip.search([('employee_id', '=', emp.id)])
        self.assertEqual(len(trip), 1)
        self.assertEqual(trip.create_uid, user)
        self.assertEqual(trip.state, 'submitted')
        self.assertEqual(trip.approval_request_id.submitter_uid, user)
        parsed = urlparse(response.url)
        self.assertEqual(parsed.path, '/my/trips/%s' % trip.id)
        self.assertIn('done=sent', parsed.query)
        text = self._text(response)
        Trips = self.env['pb.me.trip']
        for amount in (trip.per_diem_total, trip.estimated_total, trip.advance_amount):
            self.assertIn(Trips.fmt_money(amount, trip.currency_id), text, 'the card shows the record')
        self.assertIn('pbtr-steps', text)
        self.assertIn('pbtr-step is-current', text)
        self.assertIn('Waiting approval', text)
        self.assertIn('Sent for approval', text)
        self.assertIn(self.mgr_user.name, text, 'the live name from the route')
        self.assertIn('Paid with your salary', text)

        listing = self.url_open('/my/trips', timeout=60)
        self.assertIn('pbtr-tc is-wait', listing.text)
        self.assertIn('Đà Nẵng', listing.text)
        counters = self.make_jsonrpc_request('/my/counters', {'counters': ['trip_count']})
        self.assertEqual(counters.get('trip_count'), 0)
        requests_page = self._text(self.url_open('/my/requests', timeout=60))
        self.assertIn('pbme-rq-pill pbme-rq-pill--wait', requests_page)
        self.assertIn('Trip · Đà Nẵng', requests_page)

        trip.with_user(self.mgr_user).action_refuse_chain(note='Please go in April instead.')
        page = self._text(self.url_open('/my/trips/%s' % trip.id, timeout=60))
        self.assertIn('Refused — your turn', page)
        self.assertIn('Please go in April instead.', page)
        self.assertIn('Fix and resend', page)
        counters = self.make_jsonrpc_request('/my/counters', {'counters': ['trip_count']})
        self.assertEqual(counters.get('trip_count'), 1)
        requests_page = self._text(self.url_open('/my/requests', timeout=60))
        self.assertIn('pbme-rq-pill pbme-rq-pill--act', requests_page)
        home = self._text(self.url_open('/my', timeout=60))
        self.assertIn('1 trip request refused — fix and resend', home)
        self.assertNotIn('Your next trip', home)

        # fix and resend: reopen → the form → send again
        reopened = self._post('/my/trips/%s/reopen' % trip.id)
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(urlparse(reopened.url).path, '/my/trips/%s/edit' % trip.id)
        trip.invalidate_recordset()
        self.assertEqual(trip.state, 'draft')
        resent = self._post('/my/trips/%s/edit' % trip.id, self._form(
            d_from=D1 + timedelta(days=21), d_to=D3 + timedelta(days=21), destination_city='Huế'))
        self.assertEqual(resent.status_code, 200)
        trip.invalidate_recordset()
        self.assertEqual((trip.state, trip.destination_city), ('submitted', 'Huế'))
        self.assertEqual(trip.approval_request_id.attempt, 2)

        # take it back
        taken = self._post('/my/trips/%s/withdraw' % trip.id)
        self.assertEqual(taken.status_code, 200)
        trip.invalidate_recordset()
        self.assertEqual(trip.state, 'cancelled')
        self.assertIn('Ask again with these details', self._text(taken))

        # the next trip: on /my only once authorised and within 14 days
        today = Trips._today(emp)
        soon = self._post('/my/trips/new', self._form(
            d_from=today + timedelta(days=6), d_to=today + timedelta(days=8), destination_city='Hà Nội'))
        self.assertEqual(soon.status_code, 200)
        soon_trip = Trip.search([('employee_id', '=', emp.id), ('state', '=', 'submitted')])
        self.assertEqual(len(soon_trip), 1)
        self.assertNotIn('Your next trip', self._text(self.url_open('/my', timeout=60)))
        self._approve_all(soon_trip)
        home = self._text(self.url_open('/my', timeout=60))
        self.assertIn('Your next trip', home)
        self.assertIn('in 6 days', home)
        approved_page = self._text(self.url_open('/my/trips/%s' % soon_trip.id, timeout=60))
        self.assertIn('Your attendance is marked automatically for every trip day.', approved_page)
        self.assertIn('Ask HR to cancel an authorised trip', approved_page)
        # E2.9 — the receipts link follows the expenses module
        if 'pb.expense.claim' in self.env:
            self.assertIn('/my/expenses/new?trip=%s' % soon_trip.id, approved_page)
        else:
            self.assertNotIn('Claim receipts for this trip', approved_page)
            self.assertNotIn('/my/expenses/new', approved_page)
        board = self._text(self.url_open('/my/trips', timeout=60))
        self.assertIn('pbtr-next', board)
        self.assertIn('next trip', board)

    # E2.8 (+ E2.9)
    def test_e2_8_flow_for_an_employee_login(self):
        self._flow(self.share, PASSWORD, self.share_emp)

    def test_e2_8b_flow_for_a_full_account(self):
        self._flow(self.plain, T1_PASSWORD, self.plain_emp)

    def test_e2_8c_home_tile_in_time(self):
        self.authenticate(self.share.login, PASSWORD)
        page = self.url_open('/my', timeout=60)
        doc = lxml_html.fromstring(page.text)
        groups = doc.xpath("//div[contains(@class, 'o_portal_index_card')]"
                           "[.//a[@href='/my/trips']]/@data-pbme-group")
        self.assertEqual(groups, ['time'])
        counters = self.make_jsonrpc_request('/my/counters', {'counters': ['trip_count']})
        self.assertEqual(counters.get('trip_count'), 0)

    def test_e2_8d_line_routes_and_errors(self):
        self.authenticate(self.share.login, PASSWORD)
        trip = self._as(self.share).new_trip(self.share_emp, self._values(), self._lines())
        url = '/my/trips/%s' % trip.id
        added = self._post(url + '/line/add', {'category_id': str(self.cat_lodging.id),
                                               'amount': '300000', 'description': 'Taxi'})
        self.assertEqual(added.status_code, 200)
        self.assertEqual(len(trip.line_ids), 3)
        self.assertIn('Cost added', added.text)
        bad = self._post(url + '/line/add', {'amount': '-5'})
        self.assertEqual(bad.status_code, 200)
        self.assertIn('cannot be below zero', self._text(bad))
        removed = self._post(url + '/line/%s/remove' % trip.line_ids[0].id)
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(len(trip.line_ids), 2)
        # an overlap is refused with the other trip's words, on the trip page
        first = self._as(self.share).new_trip(self.share_emp, self._values(city='Hội An'), [])
        self._as(self.share).send(first)
        clash = self._post(url + '/send')
        self.assertEqual(clash.status_code, 200)
        self.assertIn('Hội An', self._text(clash))
        self.assertIn('That did not go through.', clash.text)
        trip.invalidate_recordset()
        self.assertEqual(trip.state, 'draft')

    # E2.7 — routes
    def test_e2_7_routes_are_404_for_another_persons_trip(self):
        theirs = self._as(self.plain).new_trip(self.plain_emp, self._values(), self._lines())
        self.authenticate(self.share.login, PASSWORD)
        for path in ('/my/trips/%s' % theirs.id, '/my/trips/%s/edit' % theirs.id):
            response = self.url_open(path, timeout=60)
            self.assertEqual(response.status_code, 404, path)
            self.assertIn('We could not find that trip', response.text)
            self.assertNotIn('Đà Nẵng', response.text)
        for action in ('send', 'withdraw', 'reopen', 'edit', 'line/add',
                       'line/%s/remove' % theirs.line_ids[0].id):
            response = self._post('/my/trips/%s/%s' % (theirs.id, action), self._form())
            self.assertEqual(response.status_code, 404, action)
        theirs.invalidate_recordset()
        self.assertEqual(theirs.state, 'draft')
        self.assertEqual(len(theirs.line_ids), 2)
        self.assertEqual(theirs.destination_city, 'Đà Nẵng')
        self.assertEqual(self.url_open('/my/trips/999999999', timeout=60).status_code, 404)
