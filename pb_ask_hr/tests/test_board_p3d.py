# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""NAV P3d — Home › Ask HR as a Payobook board (docs/handovers/NAV_P3D_ASK_HR_BOARD.md §5).

The facade `pb.ask.hr` is read AS THE READER: the HR team sees every
question, an employee only their own — through the record rules, never sudo.
Every change goes through the model methods the native form calls.
"""
import json
import os
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

BOARD_JS = ('static', 'src', 'js', 'askhr_lens.js')
BOARD_XML = ('static', 'src', 'xml', 'askhr_lens.xml')


def _read(*parts):
    with open(os.path.join(get_module_path('pb_ask_hr'), *parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestAskHrBoardP3d(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # nobody is the default owner: the queue is the discovery
        env['ir.config_parameter'].sudo().set_param(
            'pb_ask_hr.owner_uid.%s' % env.company.id, False)
        Users = env['res.users'].with_context(no_reset_password=True)
        internal = env.ref('base.group_user')
        hr = env.ref('hr.group_hr_user')

        def user(login, name, groups):
            return Users.create({
                'name': name, 'login': login, 'lang': 'en_US', 'tz': 'UTC',
                'email': '%s@example.com' % login,
                'company_id': env.company.id, 'company_ids': [(6, 0, [env.company.id])],
                'group_ids': [(6, 0, [g.id for g in groups])]})

        cls.hr1 = user('p3d_hr1', 'P3d HR One', [internal, hr])
        cls.hr2 = user('p3d_hr2', 'P3d HR Two', [internal, hr])
        cls.plain = user('p3d_plain', 'P3d Plain Employee', [internal])
        cls.other = user('p3d_other', 'P3d Other Employee', [internal])
        cls.lonely = user('p3d_lonely', 'P3d Lonely Employee', [internal])
        Emp = env['hr.employee']
        dept = env['hr.department'].create({'name': 'P3d Shop floor'})
        cls.plain_emp = Emp.create({'name': 'P3d Plain Employee', 'user_id': cls.plain.id,
                                    'department_id': dept.id, 'company_id': env.company.id})
        cls.other_emp = Emp.create({'name': 'P3d Other Employee', 'user_id': cls.other.id,
                                    'company_id': env.company.id})
        Emp.create({'name': 'P3d Lonely Employee', 'user_id': cls.lonely.id,
                    'company_id': env.company.id})
        cls.Ticket = env['pb.ask.hr.ticket']
        cls.Board = env['pb.ask.hr']

    # ------------------------------------------------------------ helpers
    def _ask(self, user, emp, subject, category='pay', days_ago=0):
        ticket = self.Ticket.with_user(user).sudo()._portal_create(emp, category, subject, 'Text of ' + subject)
        if days_ago:
            when = fields.Datetime.now() - timedelta(days=days_ago)
            self.env.cr.execute('UPDATE pb_ask_hr_ticket SET create_date = %s WHERE id = %s',
                                (when, ticket.id))
            ticket.invalidate_recordset(['create_date'])
        return ticket.sudo(False).with_env(self.env)

    def _as(self, user):
        # the words are built in the reader's language; these tests read English
        return self.Board.with_user(user).with_context(lang='en_US')

    def _board(self, user):
        return self._as(user).get_board()

    def _hr_says(self, ticket, user, text='An answer'):
        ticket.with_user(user).message_post(
            body=text, message_type='comment', subtype_xmlid='mail.mt_comment')

    def _person_says(self, ticket, text='A reply'):
        ticket.with_user(ticket.employee_id.user_id).sudo()._portal_reply(text)

    # ---------------------------------------------------- 1. the numbers
    def test_01_glance_and_step_counts_add_up(self):
        a = self._ask(self.plain, self.plain_emp, 'P3d new fresh')
        self._ask(self.plain, self.plain_emp, 'P3d new old', days_ago=6)
        b = self._ask(self.other, self.other_emp, 'P3d with hr')
        b.with_user(self.hr1).action_take()
        c = self._ask(self.other, self.other_emp, 'P3d answered')
        self._hr_says(c, self.hr1)
        d = self._ask(self.plain, self.plain_emp, 'P3d closed', category='leave')
        d.with_user(self.hr1).action_close()
        board = self._board(self.hr1)
        everything = self.Ticket.search([])
        counts = board['counts']
        self.assertEqual(sum(counts.values()), len(everything), 'every question is at one step')
        self.assertEqual(board['total'], len(everything))
        for state in ('new', 'with_hr', 'answered', 'closed'):
            self.assertEqual(counts[state], self.Ticket.search_count([('state', '=', state)]))
        mine = {c['id']: c for c in board['cards']}
        self.assertEqual(mine[a.id]['state'], 'new')
        self.assertEqual(mine[b.id]['state'], 'with_hr')
        self.assertTrue(mine[b.id]['mine'])
        self.assertEqual(board['mine_with_hr'], sum(
            1 for x in board['cards'] if x['mine'] and x['state'] == 'with_hr'))
        # amber only for a NEW question older than two working days
        late = [x for x in board['cards'] if x['late']]
        self.assertIn('P3d new old', [x['subject'] for x in late])
        self.assertNotIn('P3d new fresh', [x['subject'] for x in late])
        self.assertTrue(all(x['state'] == 'new' for x in late))
        self.assertEqual(board['new_late'], len(late))
        # answered this week counts what HR answered since Monday
        self.assertGreaterEqual(board['answered_week'], 1)
        self.assertTrue(mine[c.id]['answered_week'])
        self.assertFalse(mine[a.id]['answered_week'])
        self.assertTrue(board['can_act'])
        self.assertIn('median', board)
        self.assertTrue(board['last_answered_words'].startswith('Last question answered'))

    def test_02_cards_carry_what_the_board_draws(self):
        t = self._ask(self.plain, self.plain_emp, 'P3d card fields', category='documents')
        card = next(c for c in self._board(self.hr1)['cards'] if c['id'] == t.id)
        self.assertEqual(card['number'], t.number)
        self.assertEqual(card['person'], 'P3d Plain Employee')
        self.assertEqual(card['department'], 'P3d Shop floor')
        self.assertEqual(card['category'], 'documents')
        self.assertTrue(card['category_label'])
        self.assertEqual(card['owner_id'], 0, 'nobody has it yet')
        self.assertIn('Text of P3d card fields', card['line'])
        self.assertTrue(card['age'])

    # --------------------------------------------- 2. own questions only
    def test_03_an_employee_sees_only_their_own_questions(self):
        own = self._ask(self.plain, self.plain_emp, 'P3d plain own')
        theirs = self._ask(self.other, self.other_emp, 'P3d secret of another')
        self._hr_says(theirs, self.hr1, 'P3d private answer to another')
        board = self._board(self.plain)
        self.assertFalse(board['can_act'])
        self.assertNotIn('median', board, 'the HR team number is not on an employee board')
        ids = {c['id'] for c in board['cards']}
        self.assertIn(own.id, ids)
        self.assertNotIn(theirs.id, ids)
        self.assertEqual({c['employee_id'] for c in board['cards']}, {self.plain_emp.id})
        self.assertEqual(board['total'], self.Ticket.with_user(self.plain).search_count([]))
        blob = json.dumps(board, default=str)
        self.assertNotIn('secret of another', blob, 'nothing of another person leaks')
        self.assertNotIn('Other Employee', blob)
        self.assertTrue(board['can_ask'])

    def test_04_an_employee_who_asked_nothing(self):
        board = self._board(self.lonely)
        self.assertEqual(board['total'], 0)
        self.assertEqual(board['cards'], [])
        self.assertTrue(board['can_ask'])

    def test_05_an_employee_cannot_act(self):
        t = self._ask(self.plain, self.plain_emp, 'P3d employee tries')
        for verb, payload in (('take', {'ids': [t.id]}),
                              ('hand', {'ids': [t.id], 'user_id': self.hr1.id}),
                              ('close', {'ids': [t.id], 'note': 'x'})):
            with self.assertRaises(AccessError):
                self._as(self.plain).act(verb, payload)
        with self.assertRaises(AccessError):
            self._as(self.plain).get_owners()
        self.assertEqual(t.state, 'new')
        self.assertFalse(t.user_id)

    def test_05b_the_facade_never_reaches_past_the_rules(self):
        src = _read('models', 'askhr_board.py')
        code = re.sub(r'""".*?"""', '', src, flags=re.S)
        self.assertNotIn('.sudo(', code, 'the board reads as the reader, never sudo')

    # -------------------------------------------- 3. the verbs = the form
    def test_06_take_it_moves_exactly_as_the_form(self):
        by_board = self._ask(self.plain, self.plain_emp, 'P3d take board')
        by_form = self._ask(self.plain, self.plain_emp, 'P3d take form')
        res = self._as(self.hr1).act('take', {'ids': [by_board.id]})
        by_form.with_user(self.hr1).action_take()
        self.assertEqual(res['done'], 1)
        for t in (by_board, by_form):
            self.assertEqual(t.state, 'with_hr')
            self.assertEqual(t.user_id, self.hr1)
            self.assertIn(self.hr1.partner_id, t.message_partner_ids)

    def test_07_hand_to_somebody_in_hr(self):
        t = self._ask(self.plain, self.plain_emp, 'P3d hand')
        res = self._as(self.hr1).act('hand', {'ids': [t.id], 'user_id': self.hr2.id})
        self.assertEqual(res['done'], 1)
        self.assertEqual(t.user_id, self.hr2)
        self.assertEqual(t.state, 'with_hr')
        self.assertIn(self.hr2.partner_id, t.message_partner_ids)
        todo = t.activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref('mail.mail_activity_data_todo'))
        self.assertEqual(todo.user_id, self.hr2, 'the person receiving it gets the to-do')
        # handed on again: the to-do moves, it is not doubled
        self._as(self.hr2).act('hand', {'ids': [t.id], 'user_id': self.hr1.id})
        todo = t.activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref('mail.mail_activity_data_todo'))
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo.user_id, self.hr1)
        # never to somebody who cannot read the queue
        with self.assertRaises(UserError):
            self._as(self.hr1).act('hand', {'ids': [t.id], 'user_id': self.plain.id})
        owners = self._as(self.hr1).get_owners()
        ids = [o['id'] for o in owners]
        self.assertIn(self.hr2.id, ids)
        self.assertNotIn(self.plain.id, ids)
        self.assertEqual(owners[0]['id'], self.hr1.id, 'you first')

    def test_08_close_with_a_note_told_or_kept_inside(self):
        told = self._ask(self.plain, self.plain_emp, 'P3d close told')
        kept = self._ask(self.plain, self.plain_emp, 'P3d close kept')
        bare = self._ask(self.plain, self.plain_emp, 'P3d close bare')
        bare.with_user(self.hr1).action_close()
        res = self._as(self.hr1).act(
            'close', {'ids': [told.id, bare.id], 'note': 'Sorted at the town hall', 'tell': True})
        self.assertEqual((res['done'], res['skipped']), (1, 1))
        self.assertIn('already closed', res['message'])
        self._as(self.hr1).act(
            'close', {'ids': [kept.id], 'note': 'Internal only', 'tell': False})
        for t in (told, kept):
            self.assertEqual(t.state, 'closed')
            self.assertEqual(t.closed_by, 'hr')
            self.assertTrue(t.closed_on)
        public = told._pb_public_messages()
        self.assertTrue(any('town hall' in (m.body or '') for m in public),
                        'told: the person reads it on their page')
        self.assertFalse(any('Internal only' in (m.body or '') for m in kept._pb_public_messages()),
                         'kept: a note never reaches the person')
        notes = kept.message_ids.filtered(lambda m: 'Internal only' in (m.body or ''))
        self.assertTrue(notes and notes.subtype_id.internal)

    def test_09_unknown_verb_and_unreadable_ids(self):
        with self.assertRaises(UserError):
            self._as(self.hr1).act('delete', {'ids': [1]})
        with self.assertRaises(UserError):
            self._as(self.hr1).act('take', {'ids': [999999999]})

    # ---------------------------------------------------- 4. the median
    def test_10_median_first_reply_over_the_window(self):
        # wipe the window so only this test's questions count
        self.env.cr.execute("UPDATE pb_ask_hr_ticket SET create_date = create_date - interval '400 days'")
        self.Ticket.invalidate_model(['create_date'])
        two = self._ask(self.plain, self.plain_emp, 'P3d med two', days_ago=2)
        self._hr_says(two, self.hr1)
        four = self._ask(self.plain, self.plain_emp, 'P3d med four', days_ago=4)
        four.with_user(self.hr1).action_answer_done()
        six = self._ask(self.plain, self.plain_emp, 'P3d med six', days_ago=6)
        self._person_says(six, 'Any news?')   # the person's own words are not an answer
        self._hr_says(six, self.hr1)
        self._hr_says(six, self.hr1, 'A second answer')
        old = self._ask(self.plain, self.plain_emp, 'P3d med outside', days_ago=40)
        self._hr_says(old, self.hr1)
        self._ask(self.plain, self.plain_emp, 'P3d med waiting', days_ago=1)
        med = self._board(self.hr1)['median']
        self.assertEqual(med['n'], 3, 'answered questions asked in the last 30 days')
        self.assertAlmostEqual(med['seconds'] / 86400, 4, delta=0.01)
        self.assertEqual(med['words'], '4 days')

    def test_10b_first_reply_is_the_first_not_the_last(self):
        t = self._ask(self.plain, self.plain_emp, 'P3d first reply', days_ago=3)
        self._hr_says(t, self.hr1)
        first = self._as(self.hr1)._first_replies(t)[t.id]
        self.env.cr.execute('UPDATE pb_ask_hr_ticket SET answered_on = %s WHERE id = %s',
                            (fields.Datetime.now() + timedelta(days=5), t.id))
        t.invalidate_recordset(['answered_on'])
        self.assertEqual(self._as(self.hr1)._first_replies(t)[t.id], first)

    # ------------------------------------------------ 5. dots and filters
    def test_11_new_reply_dot_for_whoever_is_next(self):
        t = self._ask(self.plain, self.plain_emp, 'P3d dot')
        self._hr_says(t, self.hr1)
        card = next(c for c in self._board(self.plain)['cards'] if c['id'] == t.id)
        self.assertTrue(card['unread'], 'the person: HR answered')
        hr_card = next(c for c in self._board(self.hr1)['cards'] if c['id'] == t.id)
        self.assertFalse(hr_card['unread'])
        self._person_says(t)
        hr_card = next(c for c in self._board(self.hr1)['cards'] if c['id'] == t.id)
        self.assertTrue(hr_card['unread'], 'HR: the person replied')
        self.assertEqual(hr_card['state'], 'with_hr')

    def test_12_filters_have_what_they_filter_on(self):
        a = self._ask(self.plain, self.plain_emp, 'P3d filter leave', category='leave')
        b = self._ask(self.plain, self.plain_emp, 'P3d filter pay', category='pay')
        b.with_user(self.hr1).action_take()
        board = self._board(self.hr1)
        cards = {c['id']: c for c in board['cards']}
        self.assertTrue(cards[b.id]['mine'])
        self.assertFalse(cards[a.id]['mine'])
        self.assertEqual(cards[a.id]['owner_id'], 0)
        self.assertEqual(board['unowned'], sum(
            1 for c in board['cards'] if not c['owner_id'] and c['state'] != 'closed'))
        keys = [c['key'] for c in board['categories']]
        self.assertEqual(keys, ['pay', 'leave', 'documents', 'benefits', 'equipment', 'other'])
        src = _read(*BOARD_JS)
        self.assertIn('"pbhub.askhr.filters.v1"', src)
        for word in ('state.mine', 'state.nobody', 'state.cat', 'state.q'):
            self.assertIn(word, src)

    # -------------------------------------------- 6. the screen and words
    def test_13_the_home_tab_is_the_board(self):
        src = _read(*BOARD_JS)
        self.assertIn('registry.category(HOME_LENSES).add("askhr"', src)
        self.assertIn('{ sequence: 15 }', src)
        self.assertNotIn('@web/views/view', src, 'the stock kanban is no longer embedded')
        self.assertIn('"pb.ask.hr", "get_board"', src)
        self.assertIn('"pb.ask.hr", "act"', src)
        self.assertIn('"/my/ask-hr/new"', src)
        xml = _read(*BOARD_XML)
        for anchor in ('ah-glance', 'ah-steps', 'ah-card', 'ah-take'):
            self.assertIn('data-coach="%s"' % anchor, xml)
        self.assertIn('pb_import_kit.QuietGlance', xml)
        self.assertIn('pb_import_kit.QuietSteps', xml)
        text = re.sub(r'<!--.*?-->', '', xml, flags=re.S)
        self.assertNotRegex(text.lower(), r'\bodoo\b')
        # the native screens stay as the off-menu fallback
        for xmlid in ('view_pb_ask_hr_ticket_kanban', 'view_pb_ask_hr_ticket_list',
                      'view_pb_ask_hr_ticket_form', 'action_pb_ask_hr_ticket'):
            self.assertTrue(self.env.ref('pb_ask_hr.%s' % xmlid))

    def test_14_the_owner_words_in_vietnamese(self):
        po = _read('i18n', 'vi_VN.po')
        for en, vi in (('With HR', 'Nhân sự đang xử lý'), ('Nobody has it yet', 'Chưa ai nhận'),
                       ('Take it', 'Nhận xử lý'), ('Hand to…', 'Chuyển cho…'),
                       ('Mine', 'Của tôi'), ('Ask a new question', 'Đặt câu hỏi mới'),
                       ('Nothing is waiting.', 'Không có gì đang chờ.'),
                       ('New', 'Mới'), ('Answered', 'Đã trả lời'), ('Closed', 'Đã đóng')):
            self.assertIn('msgid "%s"\nmsgstr "%s"' % (en, vi), po)
        self.assertIn('thời gian trả lời đầu tiên (trung vị)', po)

    def test_15_the_new_question_page_is_not_shadowed(self):
        """pb_me_expense's portal controller has `_render_new(emp, …)`; the
        Ask HR helper of the same name was overridden by it and the page
        answered 403 wherever Expenses is installed (found in the P3d walk)."""
        src = _read('controllers', 'portal.py')
        self.assertNotIn('def _render_new(', src)
        self.assertIn('def _ask_hr_render_new(', src)
        from odoo.addons.pb_ask_hr.controllers.portal import PbAskHrPortal
        self.assertTrue(hasattr(PbAskHrPortal, "_ask_hr_render_new"))

    def test_16_median_words_use_the_readers_decimal_mark(self):
        board = self.Board.with_user(self.hr1)
        self.assertEqual(board.with_context(lang='en_US')._median_words(1.5 * 86400), '1.5 days')
        self.assertEqual(board.with_context(lang='en_US')._median_words(3 * 3600), '3 hours')
        if self.env['res.lang']._get_data(code='vi_VN'):
            self.assertEqual(board.with_context(lang='vi_VN')._median_words(1.5 * 86400), '1,5 ngày')
