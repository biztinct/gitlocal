# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP QF3 — leave on My Payobook: half days and hours, withdraw, cancel,
documents and the "after this request" preview.

Numbered after the handover's test cases (`docs/handovers/wdgap/
WDGAP_QF3_HANDOVER.md` §5). Every case runs for an internal login (the
fixture's ESS Alpha) and, where the path differs, for an EMPLOYEE login
(portal tier) — the one that holds no right on hr.leave at all and reaches
everything through the facade's sudo after its ownership guard.

Run alone: ``--test-tags /pb_ess_workforce:TestWdgapQf3`` (or the tag
``wdgap_qf3``).
"""

from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.pb_timeoff.models.hr_leave_approval import (
    ENGINE_APPLY, LEAVE_PROCESS_KEY,
)

from .common import EssWorkforceCase

PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
JPEG = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' + b'\x00' * 64
EXE = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00' + b'\x00' * 64


@tagged('post_install', '-at_install', 'wdgap_qf3')
class TestWdgapQf3(EssWorkforceCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.boss_user = Users.create({
            'name': 'QF3 Boss', 'login': 'qf3.boss@example.invalid',
            'email': 'qf3.boss@example.invalid', 'tz': cls.tz,
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.boss = cls.env['hr.employee'].create({
            'name': 'QF3 Boss', 'user_id': cls.boss_user.id,
            'company_id': cls.company.id, 'tz': cls.tz})
        cls.emp_a.write({'parent_id': cls.boss.id,
                         'leave_manager_id': cls.boss_user.id})
        # an EMPLOYEE login: portal tier only (TIERS), linked to an employee
        cls.user_p = Users.create({
            'name': 'QF3 Portal', 'login': 'qf3.portal@example.invalid',
            'email': 'qf3.portal@example.invalid', 'tz': cls.tz,
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.emp_p = cls.env['hr.employee'].create({
            'name': 'QF3 Portal', 'user_id': cls.user_p.id,
            'company_id': cls.company.id, 'tz': cls.tz,
            'parent_id': cls.boss.id, 'leave_manager_id': cls.boss_user.id})

        # the company runs time off through the approval engine (the default
        # route: their manager, then the HR lead)
        cls.env['hr.leave']._approval_seed_default(cls.company)
        Type = cls.env['hr.leave.type']
        cls.t_day = Type.create({
            'name': 'QF3 Whole days', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'request_unit': 'day',
            'company_id': cls.company.id})
        cls.t_half = Type.create({
            'name': 'QF3 Half days', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'request_unit': 'half_day',
            'support_document': True, 'company_id': cls.company.id})
        cls.t_hour = Type.create({
            'name': 'QF3 Hours', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'request_unit': 'hour',
            'company_id': cls.company.id})
        cls.t_alloc = Type.create({
            'name': 'QF3 Counted', 'requires_allocation': True,
            'leave_validation_type': 'manager', 'request_unit': 'half_day',
            'allocation_validation_type': 'hr', 'company_id': cls.company.id})
        cls.t_auto = Type.create({
            'name': 'QF3 Auto', 'requires_allocation': True,
            'leave_validation_type': 'no_validation',
            'request_unit': 'day', 'allocation_validation_type': 'hr',
            'company_id': cls.company.id})
        for emp in (cls.emp_a, cls.emp_p):
            for lt in (cls.t_alloc, cls.t_auto):
                alloc = cls.env['hr.leave.allocation'].sudo().create({
                    'name': 'QF3 grant', 'employee_id': emp.id,
                    'holiday_status_id': lt.id, 'number_of_days': 10,
                    'allocation_type': 'regular',
                    'date_from': date.today() - timedelta(days=30)})
                alloc.action_approve()
        # a weekday-anchored FUTURE Monday (a fixed date stops being future)
        anchor = date.today() + timedelta(days=14)
        cls.mon = anchor - timedelta(days=anchor.weekday())

    # ------------------------------------------------------------- helpers
    def _apply(self, user, lt, start, end=None, **kw):
        return self._as(user).apply_leave(
            lt.id, start.isoformat(), (end or start).isoformat(),
            kw.pop('note', 'QF3'), **kw)

    def _leave(self, res):
        return self.env['hr.leave'].sudo().browse(res['id'])

    def _past_leave(self, emp, lt, start, state='confirm'):
        """A leave in the past, entered by HR (the only way one exists)."""
        leave = self.env['hr.leave'].sudo().with_context(
            leave_skip_state_check=True, mail_create_nolog=True).create({
                'employee_id': emp.id, 'holiday_status_id': lt.id,
                'request_date_from': start, 'request_date_to': start,
                'name': 'QF3 past'})
        if state != leave.state:
            leave.with_context(**{ENGINE_APPLY: True}).write({'state': state})
        return leave

    def _seats_open_for(self, user, request):
        return request.step_ids.seat_ids.filtered(
            lambda s: s.status == 'open'
            and user in (s.user_id | s.acting_user_id))

    def _approve(self, leave):
        leave.with_user(self.boss_user).action_approve()
        leave.invalidate_recordset()
        self.assertEqual(leave.state, 'validate')

    # ================================================================== 1
    def test_01_whole_day_apply_keeps_the_old_signature(self):
        res = self._as(self.user_a).apply_leave(
            self.t_day.id, self.mon.isoformat(), self.mon.isoformat(), 'old')
        leave = self._leave(res)
        self.assertEqual(leave.employee_id, self.emp_a)
        self.assertEqual(leave.number_of_days, 1)
        self.assertEqual(leave.state, 'confirm')
        self.assertTrue(leave.approval_request_id, 'it went to the route')

    # ================================================================== 2
    def test_02_half_day_morning(self):
        for user in (self.user_a, self.user_p):
            day = self.mon + timedelta(days=1 if user == self.user_a else 2)
            leave = self._leave(self._apply(user, self.t_half, day,
                                            period_from='am'))
            self.assertEqual(leave.number_of_days, 0.5)
            self.assertEqual(leave.request_date_from_period, 'am')
            self.assertEqual(leave.request_date_to_period, 'am')
            self.assertEqual(leave._pb_day_part_label(), 'Half day, morning')
        # afternoon, and several days that start in the afternoon and end in
        # the morning
        pm = self._leave(self._apply(self.user_a, self.t_half,
                                     self.mon + timedelta(days=3),
                                     period_from='pm'))
        self.assertEqual(pm.number_of_days, 0.5)
        self.assertEqual(pm.request_date_from_period, 'pm')
        span = self._leave(self._apply(
            self.user_a, self.t_half, self.mon + timedelta(days=7),
            self.mon + timedelta(days=9), period_from='pm', period_to='am'))
        self.assertEqual(span.number_of_days, 2)
        self.assertEqual(span._pb_day_part_label(),
                         'Starts in the afternoon, ends in the morning')
        full = self._leave(self._apply(self.user_a, self.t_half,
                                       self.mon + timedelta(days=4),
                                       period_from='full'))
        self.assertEqual(full.number_of_days, 1)
        self.assertEqual(full._pb_day_part_label(), '')

    # ================================================================== 3
    def test_03_part_day_on_a_whole_day_kind_is_refused_plainly(self):
        Leave = self.env['hr.leave'].sudo()
        before = Leave.search_count([('employee_id', '=', self.emp_a.id)])
        with self.assertRaises(UserError) as caught:
            self._apply(self.user_a, self.t_day, self.mon, period_from='am')
        self.assertIn('taken in whole days', caught.exception.args[0])
        with self.assertRaises(UserError):
            self._apply(self.user_a, self.t_day, self.mon,
                        hour_from='09:00', hour_to='11:00')
        self.assertEqual(
            Leave.search_count([('employee_id', '=', self.emp_a.id)]), before)
        # "Full day" and empty times (what the form sends without scripts)
        # are simply the whole-day request
        leave = self._leave(self._apply(self.user_a, self.t_day, self.mon,
                                        period_from='full', period_to='full',
                                        hour_from='', hour_to=''))
        self.assertEqual(leave.number_of_days, 1)
        # several days of a half-day kind: the first day cannot be "morning"
        with self.assertRaises(UserError):
            self._apply(self.user_a, self.t_half, self.mon,
                        self.mon + timedelta(days=1), period_from='am')

    # ================================================================== 4
    def test_04_hours(self):
        day = self.mon + timedelta(days=1)
        leave = self._leave(self._apply(self.user_p, self.t_hour, day,
                                        hour_from='09:00', hour_to='11:00'))
        self.assertTrue(leave.request_unit_hours)
        self.assertAlmostEqual(leave.number_of_hours, 2.0, places=2)
        self.assertEqual(leave._pb_day_part_label(), '09:00 to 11:00')
        for start, end in (('11:00', '09:00'), ('10:00', '10:00')):
            with self.assertRaises(UserError) as caught:
                self._apply(self.user_p, self.t_hour, day + timedelta(days=1),
                            hour_from=start, hour_to=end)
            self.assertIn('end time must be after', caught.exception.args[0])
        with self.assertRaises(UserError):
            self._apply(self.user_p, self.t_hour, day, day + timedelta(days=1),
                        hour_from='09:00', hour_to='11:00')
        with self.assertRaises(UserError):
            self._apply(self.user_p, self.t_hour, day + timedelta(days=2))

    # ================================================================== 5
    def test_05_preview_counts_what_the_request_counts_and_writes_nothing(self):
        Leave = self.env['hr.leave'].sudo()
        Att = self.env['ir.attachment'].sudo()
        day = self.mon + timedelta(days=2)
        before = (Leave.search_count([]), Att.search_count([]))
        ess = self._as(self.user_a)
        prev = ess.preview_leave(self.t_alloc.id, day.isoformat(),
                                 day.isoformat(), period_from='pm')
        self.assertEqual((Leave.search_count([]), Att.search_count([])),
                         before, 'the preview wrote something')
        self.assertTrue(prev['ok'])
        self.assertEqual(prev['amount'], 0.5)
        row = self.env['pb.ess.workforce']._allocation_row(
            self.t_alloc, self.emp_a, day)
        self.assertEqual(prev['after'],
                         round(row['virtual_remaining_leaves'] - 0.5, 2))
        self.assertEqual(prev['after'], 9.5)
        self.assertEqual(prev['after_label'],
                         'After this request: 9.5 days left')
        leave = self._leave(self._apply(self.user_a, self.t_alloc, day,
                                        period_from='pm'))
        self.assertEqual(leave.number_of_days, prev['amount'])
        # the request now waits, so the next preview starts from 9.5
        nxt = ess.preview_leave(self.t_alloc.id, self.mon.isoformat(),
                                (self.mon + timedelta(days=1)).isoformat())
        self.assertEqual(nxt['amount'], 2)
        self.assertEqual(nxt['after'], 7.5)
        # hours and whole days preview through the same count
        hours = ess.preview_leave(self.t_hour.id, day.isoformat(),
                                  day.isoformat(), hour_from='13:00',
                                  hour_to='16:00')
        self.assertEqual((hours['amount'], hours['unit']), (3.0, 'hour'))
        self.assertIsNone(hours['after'], 'a kind that is not counted')
        # more than is left: a calm warning, and (this kind does not allow
        # going below zero) the honest "cannot be sent"
        over = ess.preview_leave(self.t_alloc.id, self.mon.isoformat(),
                                 (self.mon + timedelta(days=11)).isoformat())
        self.assertTrue(over['over'])
        self.assertTrue(over['blocked'])
        self.assertIn('more than you have left', over['warning'])
        self.t_alloc.write({'allows_negative': True,
                            'max_allowed_negative': 20})
        over = ess.preview_leave(self.t_alloc.id, self.mon.isoformat(),
                                 (self.mon + timedelta(days=11)).isoformat())
        self.assertTrue(over['over'])
        self.assertFalse(over['blocked'])
        self.assertIn('You can still send it', over['warning'])
        # a bad request is a sentence, not an exception
        bad = ess.preview_leave(self.t_day.id, day.isoformat(),
                                day.isoformat(), period_from='am')
        self.assertFalse(bad['ok'])
        self.assertTrue(bad['error'])
        self.assertEqual((Leave.search_count([]) - 1, Att.search_count([])),
                         before)

    # ================================================================== 6
    def test_06_a_past_date_from_the_employee_pages(self):
        """Closes the hole: sudo made a portal apply look like HR's own entry,
        so pb_timeoff's past-date refusal never fired."""
        ICP = self.env['ir.config_parameter'].sudo()
        past = date.today() - timedelta(days=7)
        past -= timedelta(days=past.weekday())          # a Monday
        ICP.set_param('pb_timeoff.lock_past', '1')
        for user in (self.user_a, self.user_p):
            with self.assertRaises(UserError) as caught:
                self._apply(user, self.t_day, past)
            self.assertIn('can only be entered by HR', caught.exception.args[0])
        # a kind that may be asked for afterwards (sick leave) is allowed,
        # flagged, and HR is told
        self.t_half.pb_backdate_ok = True
        sick = self._leave(self._apply(self.user_p, self.t_half, past))
        self.assertTrue(sick.pb_backdated)
        # the switch off puts the old behaviour back
        ICP.set_param('pb_timeoff.lock_past', '0')
        leave = self._leave(self._apply(self.user_p, self.t_day,
                                        past + timedelta(days=1)))
        self.assertTrue(leave.exists())
        self.assertTrue(leave.pb_backdated)

    # ================================================================== 7
    def test_07_withdraw_closes_the_approval(self):
        for user, emp in ((self.user_a, self.emp_a), (self.user_p, self.emp_p)):
            leave = self._leave(self._apply(user, self.t_half, self.mon,
                                            period_from='am'))
            request = leave.approval_request_id
            self.assertEqual(request.state, 'pending')
            self.assertTrue(self._seats_open_for(self.boss_user, request))
            res = self._as(user).withdraw_leave(leave.id)
            leave.invalidate_recordset()
            request.invalidate_recordset()
            self.assertEqual(res['state'], 'cancel')
            self.assertEqual(leave.state, 'cancel')
            self.assertTrue(leave.exists(), 'history is kept')
            self.assertEqual(request.state, 'cancelled')
            self.assertFalse(self._seats_open_for(self.boss_user, request),
                             "it is still in the approver's inbox")
            todo = self.env['mail.activity'].sudo().search([
                ('res_model', '=', 'hr.leave'), ('res_id', '=', leave.id)])
            self.assertFalse(todo, 'the approver still has a to-do')
            # the page offers nothing more on it
            row = next(r for r in self._as(user).get_my_leave()['requests']
                       if r['id'] == leave.id)
            self.assertFalse(row['can_withdraw'] or row['can_cancel'])

    def test_07b_withdraw_without_a_leave_route(self):
        process = self.env['biz.approval.process']._by_key(LEAVE_PROCESS_KEY)
        self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', process.id)]).write({'active': False})
        leave = self._leave(self._apply(self.user_p, self.t_day, self.mon))
        self.assertFalse(leave._leave_engine_managed())
        self.assertFalse(leave._leave_open_request())
        self._as(self.user_p).withdraw_leave(leave.id)
        leave.invalidate_recordset()
        self.assertEqual(leave.state, 'cancel')

    # ================================================================== 8
    def test_08_withdraw_refusals(self):
        mine = self._leave(self._apply(self.user_b, self.t_day, self.mon))
        for user in (self.user_a, self.user_p):
            with self.assertRaises(UserError) as caught:
                self._as(user).withdraw_leave(mine.id)
            self.assertIn('could not find', caught.exception.args[0])
        mine.invalidate_recordset()
        self.assertEqual(mine.state, 'confirm', "someone else's leave moved")
        # a garbage id is the same refusal
        with self.assertRaises(UserError):
            self._as(self.user_a).withdraw_leave('nope')
        # started (HR entered it in the past)
        past = date.today() - timedelta(days=3)
        started = self._past_leave(self.emp_a, self.t_day, past)
        with self.assertRaises(UserError) as caught:
            self._as(self.user_a).withdraw_leave(started.id)
        self.assertIn('already started', caught.exception.args[0])
        # approved: "use Cancel"
        approved = self._leave(self._apply(self.user_a, self.t_day,
                                           self.mon + timedelta(days=1)))
        self._approve(approved)
        with self.assertRaises(UserError) as caught:
            self._as(self.user_a).withdraw_leave(approved.id)
        self.assertIn('Use Cancel', caught.exception.args[0])

    # ================================================================== 9
    def test_09_cancel_an_approved_leave(self):
        for user, emp in ((self.user_a, self.emp_a), (self.user_p, self.emp_p)):
            day = self.mon + timedelta(days=1)
            leave = self._leave(self._apply(user, self.t_alloc, day))
            self._approve(leave)
            data = self._as(user).get_my_leave()
            tile = next(b for b in data['balances'] if b['id'] == self.t_alloc.id)
            self.assertEqual(tile['balance'], 9)
            row = next(r for r in data['requests'] if r['id'] == leave.id)
            self.assertTrue(row['can_cancel'])
            self.assertFalse(row['can_withdraw'])
            with self.assertRaises(UserError) as caught:
                self._as(user).cancel_leave(leave.id, '   ')
            self.assertIn('Say why', caught.exception.args[0])
            self._as(user).cancel_leave(leave.id, 'Plans changed')
            leave.invalidate_recordset()
            self.assertEqual(leave.state, 'cancel')
            self.assertFalse(leave._leave_open_request(),
                             'an approval is still open')
            self.assertFalse(
                leave.approval_request_id.state in ('pending', 'blocked'))
            bodies = ' '.join(leave.message_ids.mapped('body'))
            self.assertIn('Plans changed', bodies)
            tile = next(b for b in self._as(user).get_my_leave()['balances']
                        if b['id'] == self.t_alloc.id)
            self.assertEqual(tile['balance'], 10, 'the day came back')
        # waiting → "use Withdraw"; started → refused
        waiting = self._leave(self._apply(self.user_a, self.t_day, self.mon))
        with self.assertRaises(UserError) as caught:
            self._as(self.user_a).cancel_leave(waiting.id, 'x')
        self.assertIn('Use Withdraw', caught.exception.args[0])
        past = date.today() - timedelta(days=3)
        started = self._past_leave(self.emp_a, self.t_auto, past,
                                   state='validate')
        with self.assertRaises(UserError) as caught:
            self._as(self.user_a).cancel_leave(started.id, 'x')
        self.assertIn('already started', caught.exception.args[0])
        other = self._leave(self._apply(self.user_b, self.t_day, self.mon))
        with self.assertRaises(UserError):
            self._as(self.user_a).cancel_leave(other.id, 'x')

    # ================================================================= 10
    def test_10_withdrawn_from_the_approvals_screen_cancels_the_leave(self):
        leave = self._leave(self._apply(self.user_a, self.t_day, self.mon))
        request = leave.approval_request_id
        self.assertTrue(request)
        # the submitter's own "withdraw" on the approvals screen is the
        # engine's cancel, as that person
        self.env['biz.approval.engine'].with_user(self.user_a).cancel(
            request.id, 'Not needed')
        leave.invalidate_recordset()
        self.assertEqual(leave.state, 'cancel')
        self.assertFalse(self._seats_open_for(self.boss_user, request))

    # ================================================================= 11
    def test_11_documents(self):
        Att = self.env['ir.attachment'].sudo()
        leave = self._leave(self._apply(
            self.user_p, self.t_half, self.mon, period_from='am',
            files=[('C:\\Users\\me\\note.pdf', PDF, 'application/pdf'),
                   ('../../photo.jpg', JPEG, 'image/jpeg')]))
        atts = Att.search([('res_model', '=', 'hr.leave'),
                           ('res_id', '=', leave.id)], order='id')
        self.assertEqual(atts.mapped('name'), ['note.pdf', 'photo.jpg'])
        self.assertEqual(atts.mapped('mimetype'),
                         ['application/pdf', 'image/jpeg'])
        # the Leave Command Center already shows the leave's papers
        self.assertEqual(len(leave.supported_attachment_ids), 2)
        row = next(r for r in self._as(self.user_p).get_my_leave()['requests']
                   if r['id'] == leave.id)
        self.assertEqual(len(row['files']), 2)
        self.assertIn('access_token=', row['files'][0]['url'])
        self.assertTrue(row['can_add_document'])
        ess = self._as(self.user_p)
        # an .exe renamed .pdf: refused by its first bytes
        with self.assertRaises(UserError) as caught:
            ess.add_leave_document(leave.id, [('x.pdf', EXE, 'application/pdf')])
        self.assertIn('photo (JPG, PNG or WEBP) or a PDF', caught.exception.args[0])
        # 11 MB: refused
        big = b'%PDF' + b'0' * (11 * 1024 * 1024)
        with self.assertRaises(UserError) as caught:
            ess.add_leave_document(leave.id, [('big.pdf', big, 'application/pdf')])
        self.assertIn('over 10 MB', caught.exception.args[0])
        # three more = 5; the sixth is refused
        ess.add_leave_document(leave.id, [('a.pdf', PDF, ''), ('b.pdf', PDF, ''),
                                          ('c.pdf', PDF, '')])
        with self.assertRaises(UserError) as caught:
            ess.add_leave_document(leave.id, [('f.pdf', PDF, '')])
        self.assertIn('up to 5', caught.exception.args[0])
        self.assertEqual(Att.search_count([('res_model', '=', 'hr.leave'),
                                           ('res_id', '=', leave.id)]), 5)
        # a refused file on apply creates nothing at all
        count = self.env['hr.leave'].sudo().search_count([])
        with self.assertRaises(UserError):
            self._apply(self.user_p, self.t_day, self.mon + timedelta(days=3),
                        files=[('x.pdf', EXE, 'application/pdf')])
        self.assertEqual(self.env['hr.leave'].sudo().search_count([]), count)
        # somebody else's leave
        with self.assertRaises(UserError):
            self._as(self.user_a).add_leave_document(leave.id,
                                                     [('a.pdf', PDF, '')])
        # a cancelled request takes no more papers
        self._as(self.user_p).withdraw_leave(leave.id)
        with self.assertRaises(UserError):
            ess.add_leave_document(leave.id, [('z.pdf', PDF, '')])

    def test_11b_the_approvals_screen_says_half_day_and_documents(self):
        leave = self._leave(self._apply(
            self.user_a, self.t_half, self.mon, period_from='pm',
            files=[('note.pdf', PDF, '')]))
        detail = leave._approval_detail(leave.approval_request_id)
        chips = {c['label']: c['value'] for c in detail['chips']}
        self.assertEqual(chips.get('Part of the day'), 'Half day, afternoon')
        self.assertEqual(chips.get('Documents'), '1 document attached')
        self.assertEqual(leave._approval_card_count(None), 'Half a day')

    # ======================================================= the page data
    def test_page_flags_and_pending_line(self):
        data = self._as(self.user_p).get_my_leave()
        kinds = {t['id']: t for t in data['types']}
        self.assertEqual(kinds[self.t_half.id]['unit'], 'half_day')
        self.assertTrue(kinds[self.t_half.id]['needs_document'])
        self.assertEqual(kinds[self.t_hour.id]['unit'], 'hour')
        self.assertTrue(data['has_half_day'] and data['has_hours'])
        self._apply(self.user_p, self.t_alloc, self.mon, period_from='am')
        tile = next(b for b in self._as(self.user_p).get_my_leave()['balances']
                    if b['id'] == self.t_alloc.id)
        self.assertEqual(tile['pending'], 0.5)
        self.assertEqual(tile['pending_label'], '0.5 days waiting for approval')
        self.assertEqual(tile['balance'], 10, 'waiting is not taken')

