# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P6a (D28, trips): a trip sent back by an approver → one email to
the employee with the reason and a button, in their own language; the
engine's "Sent back to you" stops for the person who sent it in; no address →
the engine keeps it; switch off → the engine's copy is back (the email still
goes). Same cases as P5a's time off T3. Also the trip's cost lines door for
"Repeat for each…" (read only)."""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

TEMPLATE = 'pb_business_trip.mail_template_trip_returned'


@tagged('post_install', '-at_install')
class TestWf2p6aTripReturned(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        cls.boss_user = Users.create({
            'name': 'P6a Trip Boss', 'login': 'p6a_trip_boss',
            'email': 'p6a_trip_boss@example.com', 'group_ids': [(6, 0, [internal.id])]})
        cls.staff_user = Users.create({
            'name': 'P6a Traveller', 'login': 'p6a_trip_staff',
            'email': 'p6a_trip_staff@example.com', 'group_ids': [(6, 0, [internal.id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P6a Trip Boss', 'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({'name': 'P6a Traveller', 'user_id': cls.staff_user.id,
                                'work_email': 'p6a.traveller@example.com', 'parent_id': cls.boss.id,
                                'company_id': cls.company.id})

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)
        self.sn_route('trip', self.boss_user)

    def _trip(self, weeks=1, lines=0):
        start = date.today() + timedelta(days=7 * weeks)
        trip = self.env['pb.business.trip'].with_user(self.staff_user).create({
            'employee_id': self.staff.id, 'purpose': 'P6a visit', 'destination_city': 'Hanoi',
            'date_from': start, 'date_to': start + timedelta(days=2),
            'line_ids': [(0, 0, {'description': 'P6a cost %s' % (i + 1), 'amount': 10.0 * (i + 1),
                                 'date': start + timedelta(days=i)}) for i in range(lines)]})
        trip.with_user(self.staff_user).action_submit()
        self.sn_settle()
        return trip.sudo()

    def _send_back(self, trip, reason):
        request = trip.approval_request_id
        self.assertTrue(request, 'a live route sends the trip in')
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.boss_user).decide(
            request.id, step.key, 'return', reason=reason)
        self.env.invalidate_all()

    def _mails(self, trip):
        return self.sn_mails(trip, TEMPLATE)

    def test_wf2p6a_e1_trip_sent_back_email(self):
        trip = self._trip()
        self._send_back(trip, 'P6a: add the hotel')
        self.assertEqual(trip.state, 'draft')
        mail = self._mails(trip)
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.email_to, 'p6a.traveller@example.com')
        self.assertIn('P6a: add the hotel', mail.body_html)
        self.assertIn('Open your trip', mail.body_html)
        self.assertIn('res_id=%s' % trip.id, mail.body_html)
        self.assertIn('Hanoi', mail.body_html)
        self.assertNotIn('odoo', ('%s %s' % (mail.subject, mail.body_html)).lower().replace('/odoo/', ''))
        self.assertFalse(self.sn_requester(trip, 'returned'), 'the engine leaves its own copy out')
        # a retry of the hook never sends twice
        trip._approval_return(trip.approval_request_id, 'again')
        self.assertEqual(len(self._mails(trip)), 1)
        # sent in again and sent back again → told again
        trip.with_user(self.staff_user).action_submit()
        self.sn_settle()
        self._send_back(trip, 'P6a: and the taxi')
        self.assertEqual(len(self._mails(trip)), 2)

    def test_wf2p6a_e2_employee_home_login_goes_to_their_page(self):
        trip = self._trip(weeks=2)
        self.staff_user.group_ids = [(6, 0, [self.env.ref('base.group_portal').id])]
        self.assertTrue(self.staff_user.share)
        self._send_back(trip, 'P6a: other dates')
        mail = self._mails(trip)
        self.assertEqual(len(mail), 1)
        page = '/my/trips/%s' % trip.id if self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'pb_me_trip'), ('state', '=', 'installed')]) else '/my'
        self.assertIn(page, mail.body_html)

    def test_wf2p6a_e3_no_address_engine_keeps_it(self):
        self.staff.work_email = False
        self.staff_user.partner_id.email = False
        self.staff.work_contact_id.email = False
        trip = self._trip(weeks=3)
        self._send_back(trip, 'P6a: no')
        self.assertFalse(self._mails(trip))
        self.assertEqual(len(self.sn_requester(trip, 'returned')), 1)

    def test_wf2p6a_e4_switch_off_engine_copy_back(self):
        self.sn_switch(False)
        trip = self._trip(weeks=4)
        self._send_back(trip, 'P6a: switch off')
        self.assertEqual(len(self.sn_requester(trip, 'returned')), 1)
        self.assertEqual(len(self._mails(trip)), 1)

    def test_wf2p6a_e5_in_the_employee_language(self):
        langs = self.env['res.lang'].sudo().search([('code', 'in', ['vi_VN', 'id_ID']), ('active', '=', True)])
        if not langs:
            self.skipTest('Vietnamese and Indonesian are not installed here')
        expected = {'vi_VN': 'Yêu cầu công tác của bạn đã bị trả lại', 'id_ID': 'Permintaan perjalanan dinas Anda dikembalikan'}
        for i, lang in enumerate(langs):
            self.staff_user.lang = lang.code
            trip = self._trip(weeks=5 + i)
            self._send_back(trip, 'P6a: %s' % lang.code)
            mail = self.sn_mails(trip)  # any subject: it is not the English one
            self.assertEqual(len(mail), 1)
            self.assertEqual(mail.subject, expected[lang.code])
            self.assertIn('P6a: %s' % lang.code, mail.body_html)

    def test_wf2p6a_l1_cost_lines_door(self):
        caps = self.env['pb.business.trip']._workflow_capabilities()
        self.assertEqual([l['key'] for l in caps['lines']], ['costs'])
        self.assertNotIn('stages', caps, 'trips declare nothing but their lines')
        trip = self._trip(weeks=6, lines=3)
        rows = trip._workflow_lines('costs')
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[0]['name'].startswith('P6a cost 1'))
        self.assertEqual(rows[1]['values']['amount'], 20.0)
        self.assertFalse(rows[0]['values']['has_receipt'])
        self.assertEqual(trip._workflow_line('costs', rows[2]['id'])['values']['amount'], 30.0)
        self.assertIsNone(trip._workflow_line('costs', 0))
        self.assertEqual(trip._workflow_lines('other'), [])
