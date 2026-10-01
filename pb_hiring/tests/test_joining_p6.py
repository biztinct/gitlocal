# -*- coding: utf-8 -*-
"""RECRUIT P6 — from signed to joined.

Numbered as in `docs/handovers/recruit/RECRUIT_P6_JOINING.md` §5 (1–11;
test 5, the declined offer, lives in `test_offer.TestSendingIt`; test 12 is
the rest of the suite).

The Google chat test mocks Google exactly as P5 does (ledger RC64): nothing
leaves the box.
"""

import io
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged

from .test_offer import OfferCase

MEET = 'https://meet.google.com/pbj-oinp-six'


def _migration(name):
    import importlib.util
    from odoo.modules.module import get_module_path
    path = '%s/migrations/19.0.2.5.0/%s.py' % (get_module_path('pb_hiring'), name)
    spec = importlib.util.spec_from_file_location('pb_hiring_p6_%s' % name.replace('-', '_'), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class JoiningCase(OfferCase):

    def setUp(self):
        super().setUp()
        Users = self.env['res.users'].sudo()
        stamp = fields.Datetime.now().timestamp()
        self.recruiter = Users.create({
            'name': 'DEMO P6 Recruiter', 'login': 'recruit.p6.rec.%s' % stamp,
            'email': 'recruit.p6.rec@example.com',
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('base.group_user').id),
                          (4, self.env.ref('pb_hiring.group_hiring_user').id)]})
        self.boss.sudo().write({'work_email': 'demo.p6.boss@example.com'})
        self.req.sudo().write({'recruiter_id': self.recruiter.id})
        self.facade = self.env['pb.hiring'].with_user(self.recruiter)
        self.today = fields.Date.context_today(self.env.user)

    def _signed(self, start=None):
        offer = self._offer()
        if start:
            offer.sudo().write({'start_date': start})
        offer.sudo().write({'state': 'hr_ok'})
        self._complete_documents(offer)
        offer.action_send_to_candidate()
        offer.record_decision('accepted')
        offer.action_record_signed(filename='signed.pdf', content=b'%PDF-1.4 signed',
                                   mimetype='application/pdf')
        return offer

    def _mails(self, before):
        return self.env['mail.mail'].sudo().search([('id', 'not in', before)])

    def _item(self, offer, kind):
        return offer.prejoin_ids.filtered(lambda i: i.kind == kind)[:1]

    def tearDown(self):
        try:
            self.env['mail.mail'].sudo().search(
                [('state', '=', 'outgoing')]).write({'state': 'cancel'})
        except Exception:               # noqa: BLE001 — never fail a teardown
            pass
        super().tearDown()


@tagged('post_install', '-at_install', 'recruit_p6')
class TestRecruitJoining(JoiningCase):

    # ------------------------------------------------------------- test 1
    def test_01_migration_closed_becomes_joined_and_the_copy_a_document(self):
        offer = self._signed()
        offer.action_confirm_joined()
        req = self.req
        filled = req.filled_count
        # Put the offer back the way 19.0.2.4.0 left it.
        offer.document_ids.unlink()
        self.env.cr.execute(
            "UPDATE pb_hiring_offer SET state='closed', joined_on=NULL, "
            "join_status=NULL, expected_join_date=NULL WHERE id=%s", (offer.id,))
        offer.invalidate_recordset()
        pre, post = _migration('pre-10_offer_states'), _migration('post-10_joining')
        pre.migrate(self.env.cr, '19.0.2.4.0')
        offer.invalidate_recordset()
        self.assertEqual(offer.state, 'joined')
        post.migrate(self.env.cr, '19.0.2.4.0')
        offer.invalidate_recordset()
        self.assertEqual(offer.join_status, 'confirmed')
        self.assertEqual(offer.joined_on, offer.start_date)
        self.assertEqual(len(offer.document_ids), 1)
        self.assertEqual(offer.document_ids.attachment_id, offer.signed_attachment_id)
        self.assertTrue(offer.document_ids.vault_doc_id,
                        'the copy the old closure filed is found, not filed twice')
        req.invalidate_recordset(['filled_count'])
        self.assertEqual(req.filled_count, filled)
        # a second run changes nothing
        post.migrate(self.env.cr, '19.0.2.4.0')
        self.assertEqual(len(offer.document_ids), 1)

    # ------------------------------------------------------------- test 2
    def test_02_signing_keeps_a_candidate_and_lays_out_the_list(self):
        before = self.env['mail.mail'].sudo().search([]).ids
        offer = self._signed()
        app = self.applicant.with_context(active_test=False)
        self.assertEqual(offer.state, 'signed')
        self.assertEqual(app.stage_id.pb_key, 'post_offer')
        self.assertEqual(offer.expected_join_date, offer.start_date)
        self.assertEqual(offer.join_status, 'pending')
        self.assertFalse(offer.employee_id or offer.contract_id or offer.comp_id
                         or offer.case_id or offer.login_user_id)
        self.assertFalse(self.env['hr.employee'].sudo().search(
            [('applicant_ids', 'in', app.ids)]))
        items = offer.prejoin_ids.sorted('sequence')
        self.assertEqual(items.mapped('kind'), ['buddy', 'laptop', 'chat', 'todo'])
        for item, days in zip(items, (-10, -10, -5, -2)):
            self.assertEqual(item.due_date, offer.expected_join_date + timedelta(days=days))
        self.assertIn(self.boss.name, items[0].title)
        self.assertEqual(len(offer.document_ids), 1)
        self.assertEqual(offer.document_ids.kind, 'offer_letter')
        mails = self._mails(before)
        signed = mails.filtered(lambda m: 'signed' in (m.subject or ''))
        self.assertIn('demo.p6.boss@example.com', signed.mapped('email_to'))
        # the drawer and the card say it
        cand = self.facade.get_candidate(app.id)
        self.assertEqual(cand['joining']['state'], 'signed')
        self.assertEqual(cand['joining']['total'], 4)
        self.assertIn('countdown', cand['next'])
        self.assertTrue(cand['next'].get('verb'))
        card = self.facade._card(app, [], 0, self.req, fields.Datetime.now(), self.today, True)
        self.assertTrue(card['joining'])
        self.assertTrue(card['chips'][0]['label'].startswith('Joining'))
        # a manual move to Joined is still refused
        with self.assertRaises(UserError):
            self.facade.act('journey_stage', {'applicant_ids': [app.id], 'key': 'joined'})

    # ------------------------------------------------------------- test 3
    def test_03_confirm_joined_on_another_day_hands_everything_over(self):
        offer = self._signed()
        buddy = self.env['hr.employee'].sudo().create(
            {'name': 'DEMO P6 Buddy', 'company_id': self.company.id,
             'parent_id': self.boss.id, 'work_email': 'demo.p6.buddy@example.com'})
        second = self.env['hr.employee'].sudo().create(
            {'name': 'DEMO P6 Second Buddy', 'company_id': self.company.id})
        self._item(offer, 'buddy').submit_buddy([buddy.id, second.id], why='Same desk')
        self._item(offer, 'laptop').submit_laptop(
            {'kind': 'mac', 'keyboard': 'us', 'screen': 'small', 'extras': ['mouse'],
             'note': 'Left-handed'})
        self.facade.act('doc_add', {
            'offer_id': offer.id, 'kind': 'employment_agreement',
            'data': 'JVBERi0xLjQgYWdyZWVtZW50', 'filename': 'agreement.pdf',
            'mimetype': 'application/pdf'})
        later = offer.expected_join_date + timedelta(days=3)
        res = self.facade.act('confirm_joined', {'offer_id': offer.id,
                                                 'joined_on': str(later)})
        self.assertIn('has joined', res['note'])
        self.assertEqual(offer.state, 'joined')
        self.assertEqual(offer.joined_on, later)
        self.assertEqual(offer.join_status, 'confirmed')
        app = self.applicant.with_context(active_test=False)
        self.assertEqual(app.stage_id.pb_key, 'joined')
        self.assertEqual(app.date_closed.date(), later)
        self.assertEqual(offer.contract_id.sudo().date_start, later)
        self.assertEqual(offer.comp_id.sudo().effective_date, later)
        self.assertTrue(offer.case_id)
        emp = offer.employee_id.sudo()
        if 'buddy_id' in emp._fields:
            self.assertEqual(emp.buddy_id, buddy, 'the first named is the buddy on day one')
            step = offer.case_id.task_ids.filtered(lambda t: t.automation_key == 'buddy_invite')
            if step:
                self.assertEqual(step.state, 'done')
            laptop = offer.case_id.task_ids.filtered(lambda t: t.automation_key == 'asset_laptop')
            if laptop:
                self.assertIn('Mac', laptop.note or '')
        docs = self.env['pb.employee.document'].sudo().search([('employee_id', '=', emp.id)])
        cats = {d.name: d.category_id for d in docs}
        self.assertTrue(any('Signed offer' in n for n in cats))
        labour = self.env.ref('pb_employee_vault.cat_labor_contract', raise_if_not_found=False)
        if labour:
            self.assertIn(labour, docs.mapped('category_id'))
        self.assertTrue(all(offer.document_ids.mapped('vault_doc_id')))
        # idempotent
        emp_id, contract, n_docs = emp.id, offer.contract_id, len(docs)
        offer.action_confirm_joined()
        self.assertEqual(offer.employee_id.id, emp_id)
        self.assertEqual(offer.contract_id, contract)
        self.assertEqual(self.env['pb.employee.document'].sudo().search_count(
            [('employee_id', '=', emp_id)]), n_docs)
        self.req.invalidate_recordset(['filled_count'])
        self.assertEqual(self.req.filled_count, 1)

    def test_03b_confirm_on_the_default_and_an_earlier_day(self):
        offer = self._signed(start=self.today + timedelta(days=10))
        offer.action_confirm_joined()
        self.assertEqual(offer.joined_on, offer.expected_join_date)
        self.assertEqual(offer.contract_id.sudo().date_start, offer.expected_join_date)
        # and an earlier one, on a second person
        second = self.env['hr.applicant'].create({
            'partner_name': 'DEMO P6 Early', 'email_from': 'demo.p6.early@example.com',
            'job_id': self.job.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id})
        self.req.sudo().write({'selected_applicant_id': second.id})
        early_offer = self._signed(start=self.today + timedelta(days=10))
        early = self.today + timedelta(days=2)
        early_offer.action_confirm_joined(joined_on=early)
        self.assertEqual(early_offer.contract_id.sudo().date_start, early)

    def test_03c_no_onboarding_skips_the_buddy_cleanly(self):
        offer = self._signed()
        buddy = self.env['hr.employee'].sudo().create(
            {'name': 'DEMO P6 Lone Buddy', 'company_id': self.company.id})
        self._item(offer, 'buddy').submit_buddy([buddy.id])
        Offer = type(self.env['pb.hiring.offer'])
        with patch.object(Offer, '_onboarding_ready', return_value=False):
            offer.action_confirm_joined()
            self.assertEqual(offer._hand_over_buddy(), 'skipped')
        self.assertEqual(offer.state, 'joined', 'a missing module never stops a joiner')

    def test_03d_only_a_signed_offer_can_be_confirmed(self):
        offer = self._offer()
        with self.assertRaises(UserError):
            offer.action_confirm_joined()

    # ------------------------------------------------------------- test 4
    def test_04_did_not_join_is_an_offer_drop_and_the_role_stays_open(self):
        offer = self._signed()
        chat = self._item(offer, 'chat')
        chat.schedule_chat({'start': fields.Datetime.now() + timedelta(days=2),
                            'minutes': 30, 'mode': 'in_person', 'where': 'Level 3',
                            'people_ids': [self.boss.id]})
        event = chat.event_id
        self.assertTrue(event)
        before = self.env['mail.mail'].sudo().search([]).ids
        res = self.facade.act('did_not_join', {'offer_id': offer.id,
                                               'reason': 'counter_offer', 'note': 'Matched'})
        self.assertIn('offer drop', res['note'])
        self.assertEqual(offer.state, 'dropped')
        self.assertEqual(offer.join_status, 'dropped')
        app = self.applicant.with_context(active_test=False)
        self.assertEqual(app.stage_id.pb_key, 'offer_drop_out')
        self.assertFalse(app.active)
        self.assertEqual(app.refuse_reason_id,
                         self.env.ref('pb_hiring.refuse_reason_did_not_join'))
        self.assertIn('counter-offer', (app.pb_stage_reason or '').lower())
        self.assertTrue(all(i.state in ('cancelled', 'done', 'skipped') for i in offer.prejoin_ids))
        self.assertFalse(event.active, 'the chat is called off')
        self.assertTrue(self._mails(before).filtered(lambda m: 'will not join' in (m.subject or '')))
        self.req.invalidate_recordset(['filled_count'])
        self.assertEqual(self.req.filled_count, 0)
        self.assertEqual(self.req.state, 'open')
        self.assertFalse(offer.employee_id)
        # moving them back reactivates them, as for any outcome
        self.facade.act('journey_stage', {'applicant_ids': [app.id], 'key': 'offer'})
        self.assertTrue(app.active)

    # ------------------------------------------------------------- test 6
    def test_06_changing_the_date_moves_the_list_tells_people_and_rearms(self):
        offer = self._signed(start=self.today + timedelta(days=5))
        offer.sudo().write({'week_before_sent_at': fields.Datetime.now()})
        buddy = self._item(offer, 'buddy')
        due = buddy.due_date
        before = self.env['mail.mail'].sudo().search([]).ids
        new = self.today + timedelta(days=20)
        self.facade.act('change_join_date', {'offer_id': offer.id, 'date': str(new),
                                             'reason': 'Notice period extended'})
        self.assertEqual(offer.expected_join_date, new)
        self.assertEqual(offer.join_status, 'changed')
        self.assertEqual(buddy.due_date, due + (new - (self.today + timedelta(days=5))))
        change = offer.join_change_ids[:1]
        self.assertEqual((change.old_date, change.new_date), (self.today + timedelta(days=5), new))
        self.assertEqual(change.reason, 'Notice period extended')
        self.assertFalse(offer.week_before_sent_at, 'more than a week away: the email re-arms')
        self.assertTrue(self._mails(before).filtered(lambda m: 'now joins on' in (m.subject or '')))
        timeline = self.facade.get_timeline(self.applicant.id)
        self.assertTrue(any('Joining date moved' in t['text'] for t in timeline))
        with self.assertRaises(UserError):
            offer.action_change_join_date(new)

    # ------------------------------------------------------------- test 7
    def test_07_the_week_before_fires_once_and_its_answers_work(self):
        Auto = self.env['pb.hiring.automation']
        offer = self._signed(start=self.today + timedelta(days=7))
        before = self.env['mail.mail'].sudo().search([]).ids
        self.assertGreaterEqual(Auto._week_before_join(), 1)
        asks = offer.join_ask_ids
        self.assertTrue(asks)
        self.assertIn('recruiter', asks.mapped('role'))
        self.assertIn('manager', asks.mapped('role'))
        week = self._mails(before).filtered(
            lambda m: 'still on?' in (m.subject or '') and offer.candidate_name in (m.subject or ''))
        self.assertEqual(len(week), len(asks))
        Auto._week_before_join()
        self.assertEqual(offer.join_ask_ids, asks, 'once')
        Ask = self.env['pb.hiring.join.ask']
        ask = asks[0]
        self.assertEqual(Ask._request_for_token(ask.token)[1], 'ok')
        offer.answer_week(ask, 'still_on')
        self.assertEqual(offer.week_answer, 'still_on')
        self.assertEqual(Ask._request_for_token(ask.token)[1], 'used')
        self.assertEqual(Ask._request_for_token(asks[-1].token)[1], 'used',
                         'one answer from anybody is enough')
        self.assertEqual(Ask._request_for_token('x' * 30)[1], 'invalid')

    def test_07b_a_date_set_inside_the_window_fires_and_date_changed_works(self):
        Auto = self.env['pb.hiring.automation']
        offer = self._signed(start=self.today + timedelta(days=3))
        Auto._week_before_join()
        self.assertTrue(offer.week_before_sent_at, 'a date inside the window fires at once')
        ask = offer.join_ask_ids[:1]
        new = self.today + timedelta(days=30)
        offer.answer_week(ask, 'changed', new_date=new, reason='Visa')
        self.assertEqual(offer.expected_join_date, new)
        self.assertEqual(offer.join_change_ids[:1].source, 'email')
        self.assertFalse(offer.week_before_sent_at, 're-armed for the new date')

    def test_07c_did_not_join_from_the_week_before_page(self):
        offer = self._signed(start=self.today + timedelta(days=4))
        self.env['pb.hiring.automation']._week_before_join()
        ask = offer.join_ask_ids[:1]
        offer.answer_week(ask, 'dropped', reason='Took another job', drop_reason='other_offer')
        self.assertEqual(offer.state, 'dropped')
        self.assertEqual(offer.drop_reason, 'other_offer')
        self.assertEqual(self.env['pb.hiring.join.ask']._request_for_token(ask.token)[1], 'closed')

    # ------------------------------------------------------------- test 8
    def test_08_buddy_and_laptop_answers_tick_the_list(self):
        offer = self._signed()
        buddy_item = self._item(offer, 'buddy')
        before = self.env['mail.mail'].sudo().search([]).ids
        res = self.facade.act('prejoin_send', {'item_id': buddy_item.id})
        self.assertIn('buddy question', res['note'])
        ask = self._mails(before).filtered(lambda m: 'look after' in (m.subject or ''))
        self.assertEqual(ask.email_to, 'demo.p6.boss@example.com')
        self.assertIn(buddy_item.pb_link_url, str(ask.body_html))
        self.assertNotIn(buddy_item.token, str(res), 'never the token on a payload')
        Item = self.env['pb.hiring.prejoin']
        self.assertEqual(Item._request_for_token(buddy_item.token, 'buddy')[1], 'ok')
        self.assertEqual(Item._request_for_token(buddy_item.token, 'laptop')[1], 'invalid')
        one = self.env['hr.employee'].sudo().create({'name': 'DEMO P6 One', 'company_id': self.company.id})
        two = self.env['hr.employee'].sudo().create({'name': 'DEMO P6 Two', 'company_id': self.company.id})
        before = self.env['mail.mail'].sudo().search([]).ids
        buddy_item.submit_buddy([two.id, one.id], why='Knows the area')
        self.assertEqual(buddy_item.state, 'done')
        self.assertEqual(offer.buddy_employee_ids[:1], two, 'the order the manager chose')
        told = self._mails(before).filtered(lambda m: m.email_to == 'recruit.p6.rec@example.com')
        self.assertTrue(told, 'the recruiter is told')
        self.assertEqual(Item._request_for_token(buddy_item.token, 'buddy')[1], 'used')
        # laptop, in the language they applied in
        self.applicant.sudo().write({'pb_lang': 'vi_VN'})
        laptop = self._item(offer, 'laptop')
        prefs = laptop.submit_laptop({'kind': 'windows', 'keyboard': 'vi', 'extras': ['headset', 'bogus']})
        self.assertEqual(prefs['extras'], ['headset'])
        self.assertEqual(laptop.state, 'done')
        self.assertIn('Windows', laptop.pb_answer_words)
        with self.assertRaises(UserError):
            self._item(offer, 'laptop').submit_laptop({'kind': 'linux'})
        cand = self.facade.get_candidate(self.applicant.id)
        self.assertEqual(cand['joining']['done'], 2)
        self.assertTrue(cand['joining']['laptop'])

    def test_08b_the_laptop_email_goes_in_the_candidates_language(self):
        lang = self.env['res.lang'].sudo().search([('code', '=', 'vi_VN'), ('active', '=', True)])
        offer = self._signed()
        self.applicant.sudo().write({'pb_lang': 'vi_VN'})
        before = self.env['mail.mail'].sudo().search([]).ids
        item = self._item(offer, 'laptop')
        self.facade.act('prejoin_send', {'item_id': item.id})
        mail = self._mails(before).filtered(lambda m: m.email_to == self.applicant.email_from)
        self.assertTrue(mail)
        self.assertIn(item.pb_link_url, str(mail.body_html))
        if lang:
            self.assertIn('Máy tính', mail.subject or '', 'the Vietnamese text is used')

    # ------------------------------------------------------------- test 9
    def test_09_a_chat_goes_in_the_diary_through_the_shared_helper(self):
        offer = self._signed()
        item = self._item(offer, 'chat')
        before = self.env['mail.mail'].sudo().search([]).ids
        with patch.object(type(self.env['calendar.event']), '_pb_quiet_create',
                          autospec=True,
                          side_effect=type(self.env['calendar.event'])._pb_quiet_create) as helper:
            res = self.facade.act('chat_save', {
                'offer_id': offer.id, 'item_id': item.id,
                'start': str(fields.Datetime.now() + timedelta(days=2)), 'minutes': 30,
                'mode': 'in_person', 'where': 'Level 3 kitchen', 'people_ids': [self.boss.id]})
        self.assertTrue(helper.called, 'the chat uses the one helper interviews use')
        self.assertIn('diary', res['note'])
        self.assertEqual(item.event_id.pb_prejoin_id, item)
        mails = self._mails(before).filtered(lambda m: 'Meet the team' in (m.subject or ''))
        self.assertIn(self.applicant.email_from, mails.mapped('email_to'))
        self.assertTrue(all(m.attachment_ids.filtered(lambda a: a.mimetype == 'text/calendar')
                            for m in mails))
        self.assertIn(b'BEGIN:VCALENDAR', item._ics())
        # the time passes: done by itself
        item.sudo().write({'chat_start': fields.Datetime.now() - timedelta(hours=2)})
        self.env['pb.hiring.automation']._chats_tick()
        self.assertEqual(item.state, 'done')

    def test_09b_google_meet_for_a_chat_mocked(self):
        from odoo.addons.google_calendar.models.google_sync import GoogleCalendarSync
        from odoo.addons.google_calendar.utils.google_calendar import GoogleCalendarService
        settings = self.env['res.users.settings'].sudo()._find_or_create_for_user(self.recruiter)
        settings.write({'google_calendar_rtoken': 'refresh-p6', 'google_calendar_token': 'token-p6',
                        'google_calendar_token_validity': fields.Datetime.now() + timedelta(hours=1),
                        'google_synchronization_stopped': False})
        offer = self._signed()
        item = self._item(offer, 'chat')
        out = item.schedule_chat({'start': fields.Datetime.now() + timedelta(days=2), 'minutes': 30,
                                  'mode': 'video', 'where': '', 'people_ids': [self.boss.id]})
        self.assertTrue(out['waits'], 'the invitations wait for the Meet link')
        event = item.event_id
        self.assertFalse(event.location)
        values = event._google_values()
        self.assertIn('conferenceData', values)

        def answer(vals, **kw):
            vals['id'] = vals.get('id') or 'pbp6chat001'
            return dict(vals, hangoutLink=MEET, conferenceData={
                'entryPoints': [{'entryPointType': 'video', 'uri': MEET}]})
        service = GoogleCalendarService(self.env['google.service'])
        Users = type(self.env['res.users'])
        before = self.env['mail.mail'].sudo().search([]).ids
        with patch.object(GoogleCalendarService, 'insert', side_effect=answer), \
                patch.object(Users, '_get_google_calendar_token', return_value='token-p6'):
            GoogleCalendarSync._google_insert.__wrapped__(
                event.with_user(self.recruiter).with_context(send_updates=False), service, values)
        self.assertEqual(item.videocall_url, MEET)
        self.assertFalse(item.invites_pending)
        bodies = ' '.join(str(m.body_html) for m in self._mails(before))
        self.assertIn(MEET, bodies)

    # ------------------------------------------------------------ test 10
    def test_10_several_documents_and_the_countrys_set(self):
        vn = self.env.ref('base.vn')
        self.req.sudo().write({'country_id': vn.id})
        offer = self._signed()
        hint = offer._doc_set()
        self.assertEqual([r['kind'] for r in hint['rows']], ['offer_letter', 'probation_letter'])
        self.assertTrue(hint['rows'][0]['have'])
        self.assertFalse(hint['rows'][1]['have'])
        self.facade.act('doc_add', {'offer_id': offer.id, 'kind': 'probation_letter',
                                    'data': 'JVBERi0xLjQgcHJvYmF0aW9u', 'filename': 'p.pdf',
                                    'mimetype': 'application/pdf'})
        self.assertEqual(len(offer.document_ids), 2)
        self.assertTrue(all(r['have'] for r in offer._doc_set()['rows']))
        with self.assertRaises(UserError):
            self.facade.act('doc_add', {'offer_id': offer.id, 'kind': 'other',
                                        'data': 'aGVsbG8=', 'filename': 'x.exe',
                                        'mimetype': 'application/x-msdownload'})
        doc = offer.document_ids.filtered(lambda d: d.kind == 'probation_letter')
        self.facade.act('doc_remove', {'offer_id': offer.id, 'doc_id': doc.id})
        self.assertEqual(len(offer.document_ids), 1)
        idn = self.env.ref('base.id')
        self.req.sudo().write({'country_id': idn.id})
        self.assertEqual([r['kind'] for r in offer._doc_set()['rows']],
                         ['offer_letter', 'employment_agreement'])

    # ------------------------------------------------------------ test 11
    def test_11_the_numbers_filters_funnel_ageing_leadership_and_exports(self):
        A = self.env['pb.hiring.analytics']
        joined = self._signed()
        joined.action_confirm_joined()
        # a second candidate who signs and does not join, a third who declines
        for name, end in (('DEMO P6 Drop', 'drop'), ('DEMO P6 Decline', 'decline')):
            app = self.env['hr.applicant'].create({
                'partner_name': name, 'email_from': '%s@example.com' % name.replace(' ', '.').lower(),
                'job_id': self.job.id, 'company_id': self.company.id,
                'pb_requisition_id': self.req.id})
            self.req.sudo().write({'selected_applicant_id': app.id})
            offer = self._offer()
            offer.sudo().write({'state': 'hr_ok'})
            self._complete_documents(offer)
            offer.action_send_to_candidate()
            if end == 'decline':
                offer.record_decision('declined', comment='Too far to travel')
                continue
            offer.record_decision('accepted')
            offer.action_record_signed(filename='s.pdf', content=b'%PDF', mimetype='application/pdf')
            offer.action_did_not_join('other_offer', 'Bank job')
        start, end = self.today - timedelta(days=90), self.today
        fun = A.get_funnel(start, end, department_id=self.dept.id)
        self.assertGreaterEqual(fun['offered'], 3)
        self.assertGreaterEqual(fun['joined'], 1)
        self.assertGreaterEqual(fun['declined'], 1)
        self.assertGreaterEqual(fun['dropped'], 1)
        reasons = {r['key']: r for r in fun['reasons']}
        self.assertIn('declined', reasons)
        self.assertIn('other_offer', reasons)
        self.assertIn('Bank job', reasons['other_offer']['examples'])
        # the filters narrow every metric
        other = self.env['hr.department'].create({'name': 'DEMO P6 Elsewhere',
                                                  'company_id': self.company.id})
        board = A.get_board(start, end, department_id=other.id)
        self.assertTrue(board['empty'])
        self.assertFalse((A.get_funnel(start, end, department_id=other.id))['offered'])
        board = A.get_board(start, end, department_id=self.dept.id)
        self.assertFalse(board['empty'])
        # the market filter (a role with no country of its own takes the
        # company's) — `res.company.country_id` is not stored
        country = self.company.partner_id.country_id or self.env.ref('base.vn')
        self.req.sudo().write({'country_id': country.id})
        self.assertFalse(A.get_board(start, end, country_id=country.id)['empty'])
        self.req.sudo().write({'country_id': False})
        if self.company.partner_id.country_id:
            self.assertFalse(A.get_board(start, end, country_id=country.id)['empty'])
        self.assertIn('joined', [t['key'] for t in board['tiles']])
        self.assertTrue(board['options']['departments'])
        # ageing: somebody parked for three weeks is stalled
        waiting = self.env['hr.applicant'].create({
            'partner_name': 'DEMO P6 Parked', 'email_from': 'demo.p6.parked@example.com',
            'job_id': self.job.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id})
        self.env.cr.execute("UPDATE hr_applicant SET date_last_stage_update = now() - interval '21 days' "
                            "WHERE id = %s", (waiting.id,))
        waiting.invalidate_recordset()
        if self.req.state not in ('setup', 'open'):
            self.req.sudo().write({'state': 'open'})
        age = A.get_ageing(department_id=self.dept.id)
        row = [r for r in age['rows'] if r['applicant_id'] == waiting.id]
        self.assertTrue(row and row[0]['stalled'] and row[0]['days'] >= 21)
        self.assertGreaterEqual(age['stalled'], 1)
        # leadership
        lead = A.get_leadership(start, end, department_id=self.dept.id)
        self.assertGreaterEqual(lead['agreed'], 1)
        self.assertEqual(len(lead['months']), 12)
        self.assertTrue(lead['headcount'])
        # each export kind is a workbook with its sheets
        import openpyxl
        expect = {'funnel': 'Offer funnel', 'ageing': 'Ageing', 'leadership': 'Leadership',
                  'roles': 'Roles', 'stages': 'Time in stage'}
        for kind, sheet in expect.items():
            out = A.export_xlsx(start, end, kind, department_id=self.dept.id)
            import base64
            wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(out['file_b64'])))
            self.assertIn(sheet, wb.sheetnames, kind)
        everything = A.export_xlsx(start, end, 'all')
        self.assertGreaterEqual(len(everything['sheets']), 10)

    # --------------------------------------------- the screens and the rules
    def test_12_setup_list_verbs_and_white_label(self):
        lead = self.env['res.users'].sudo().create({
            'name': 'DEMO P6 Lead', 'login': 'recruit.p6.lead.%s' % fields.Datetime.now().timestamp(),
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('base.group_user').id),
                          (4, self.env.ref('pb_hiring.group_hiring_manager').id)]})
        F = self.env['pb.hiring'].with_user(lead)
        setup = F.get_setup()
        self.assertIn('prejoin', [c['key'] for c in setup['cards']])
        self.assertEqual(len(setup['prejoin']['items']), 4)
        added = F.act('prejoin_tpl_add', {'kind': 'todo'})
        F.act('prejoin_tpl_save', {'id': added['id'], 'title': 'Order their badge', 'days': -7})
        offer = self._signed()
        self.assertIn('Order their badge', offer.prejoin_ids.mapped('title'))
        self.assertEqual(offer.prejoin_ids.filtered(
            lambda i: i.title == 'Order their badge').due_offset_days, -7)
        with self.assertRaises(Exception):
            self.facade.act('prejoin_tpl_add', {'kind': 'todo'})
        # no "Odoo" in anything a user reads
        import re
        from .test_offer import _src
        for parts in (('views', 'joining_pages.xml'), ('data', 'mail_template_p6.xml'),
                      ('static', 'src', 'xml', 'hiring_p6.xml'),
                      ('static', 'src', 'xml', 'hiring_numbers.xml')):
            src = re.sub(r'<!--.*?-->', '', _src(*parts), flags=re.S)
            self.assertNotIn('Odoo', src, parts[-1])
            self.assertFalse(re.search(r'\w\(s\)', src), '%s has a bracketed plural' % parts[-1])


@tagged('post_install', '-at_install', 'recruit_p6')
class TestRecruitJoiningPages(HttpCase, JoiningCase):
    """The three pages over HTTP: they render, they answer, a spent link says so."""

    def test_pages_render_and_answer(self):
        offer = self._signed(start=fields.Date.context_today(self.env.user) + timedelta(days=6))
        buddy = offer.prejoin_ids.filtered(lambda i: i.kind == 'buddy')
        laptop = offer.prejoin_ids.filtered(lambda i: i.kind == 'laptop')
        page = self.url_open('/hiring/b/%s' % buddy.token)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Who will look after', page.text)
        person = self.env['hr.employee'].sudo().create(
            {'name': 'DEMO P6 Page Buddy', 'company_id': self.company.id})
        res = self.url_open('/hiring/b/%s/answer' % buddy.token,
                            data={'emp': str(person.id), 'order': str(person.id), 'why': 'Kind'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(buddy.state, 'done')
        self.assertIn('Already answered', self.url_open('/hiring/b/%s' % buddy.token).text)
        # the laptop page in Vietnamese when they applied in it
        self.applicant.sudo().write({'pb_lang': 'vi_VN'})
        page = self.url_open('/hiring/l/%s' % laptop.token)
        self.assertEqual(page.status_code, 200)
        vi = self.env['res.lang'].sudo().search_count([('code', '=', 'vi_VN'), ('active', '=', True)])
        self.assertIn('Máy tính xách tay của bạn' if vi else 'Your laptop', page.text)
        res = self.url_open('/hiring/l/%s/answer' % laptop.token,
                            data={'kind': 'mac', 'keyboard': 'vi', 'screen': 'any'})
        self.assertEqual(laptop.state, 'done')
        # the week-before page: still on
        self.env['pb.hiring.automation']._week_before_join()
        ask = offer.join_ask_ids[:1]
        page = self.url_open('/hiring/w/%s?a=still_on' % ask.token)
        self.assertIn('still joining', page.text)
        self.url_open('/hiring/w/%s/answer' % ask.token, data={'answer': 'still_on'})
        self.assertEqual(offer.week_answer, 'still_on')
        self.assertIn('Already answered', self.url_open('/hiring/w/%s' % ask.token).text)
        self.assertIn('This link has closed', self.url_open('/hiring/w/%s' % ('z' * 32)).text)
