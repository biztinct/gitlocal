# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3a — Ask HR (handover docs/handovers/tiers/T3A_HANDOVER.md).

T3.1 the model, T3.2 HR's "Send message" vs a note, T3.5 the HR owner
setting, T3.6 (this module's source on My requests), T3.10 the backend queue
and access, T3.3 / T3.4 the portal pages over HTTP (T-R6), T3.9 the tile.
"""
import logging
import re
from datetime import timedelta

from lxml import html as lxml_html

from odoo import fields, http
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import (
    _PDF, _make_share, _pin_dbfilter,
)
from odoo.addons.pb_me_portal.tests.test_portal_only import (
    PASSWORD as T1_PASSWORD, _make_people,
)

_logger = logging.getLogger(__name__)

PASSWORD = 'tiers-t3a-ask-hr-probe-2026'


def _make_hr(env, login, password=None):
    vals = {'name': 'T3 HR Officer', 'login': login,
            'group_ids': [(6, 0, [env.ref('base.group_user').id,
                                  env.ref('hr.group_hr_user').id])]}
    if password:
        vals['password'] = password
    return env['res.users'].with_context(no_reset_password=True).create(vals)


class _AskHrCommon:

    @classmethod
    def _fixtures(cls, prefix, password=None):
        cls.share, cls.share_emp = _make_share(
            cls.env, '%s_share' % prefix, 'Quinn Ask Share', password)
        cls.other, cls.other_emp = _make_share(
            cls.env, '%s_other' % prefix, 'Rowan Ask Other', password)
        cls.plain, cls.plain_emp, _lead, _staff = _make_people(
            cls.env, prefix, password=T1_PASSWORD if password else None)
        cls.hr = _make_hr(cls.env, '%s_hr' % prefix, password)
        cls.Ticket = cls.env['pb.ask.hr.ticket']

    def _ask(self, user, emp, subject='T3 missing overtime', text='Line one\nLine two',
             category='pay'):
        """What the portal route does: sudo after the guard, as the user."""
        return self.Ticket.with_user(user).sudo()._portal_create(emp, category, subject, text)


@tagged('post_install', '-at_install')
class TestAskHrModel(_AskHrCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixtures('test_t3a_model')
        cls.param = 'pb_ask_hr.owner_uid.%s' % cls.env.company.id
        cls.env['ir.config_parameter'].sudo().set_param(cls.param, False)

    # T3.1
    def test_t3_1_lifecycle(self):
        ticket = self._ask(self.share, self.share_emp)
        self.assertEqual(ticket.state, 'new')
        self.assertTrue(ticket.number.startswith('ASK-'), ticket.number)
        self.assertEqual(ticket.create_uid, self.share, 'sudo keeps the uid')
        self.assertIn(self.share.partner_id, ticket.message_partner_ids)
        self.assertIn('<p>Line one<br>Line two</p>', str(ticket.description).replace('<br/>', '<br>'))
        self.assertEqual(ticket.access_url, '/my/ask-hr/%s' % ticket.id)

        ticket._pb_on_public_message(True)
        self.assertEqual(ticket.state, 'with_hr')
        ticket._pb_on_public_message(False)
        self.assertEqual(ticket.state, 'answered')
        self.assertTrue(ticket.answered_on)

        ticket.with_user(self.hr).action_close()
        self.assertEqual((ticket.state, ticket.closed_by), ('closed', 'hr'))
        self.assertTrue(ticket.closed_on)
        self.assertTrue(ticket._portal_reopen())
        self.assertEqual(ticket.state, 'with_hr')
        self.assertFalse(ticket.closed_on)
        self.assertFalse(ticket._portal_reopen(), 'not closed: nothing to reopen')

        self.assertTrue(ticket._portal_close())
        self.assertEqual(ticket.closed_by, 'employee')
        self.assertFalse(ticket._portal_close(), 'a second close is a no-op')
        ticket.sudo().write({'closed_on': fields.Datetime.now() - timedelta(days=15)})
        with self.assertRaises(UserError) as caught:
            ticket._portal_reopen()
        self.assertIn('more than 14 days ago', str(caught.exception))
        self.assertIn('Ask a new question', str(caught.exception))
        with self.assertRaises(UserError):
            ticket._portal_reply('late reply')

    def test_t3_1b_a_reply_to_a_closed_question_reopens_it(self):
        ticket = self._ask(self.share, self.share_emp)
        ticket._portal_close()
        ticket.with_user(self.share).sudo()._portal_reply('One more thing')
        self.assertEqual(ticket.state, 'with_hr')
        self.assertFalse(ticket.closed_by)

    def test_t3_1c_a_subject_is_required(self):
        with self.assertRaises(UserError):
            self._ask(self.share, self.share_emp, subject='   ')

    # T3.2
    def test_t3_2_hr_comment_answers_and_mails_a_note_does_not(self):
        ticket = self._ask(self.share, self.share_emp)
        msg = ticket.with_user(self.hr).message_post(
            body='It will be paid in the next run.', message_type='comment',
            subtype_xmlid='mail.mt_comment')
        self.assertEqual(ticket.state, 'answered')
        notified = self.env['mail.notification'].sudo().search([
            ('mail_message_id', '=', msg.id),
            ('res_partner_id', '=', self.share.partner_id.id)])
        self.assertTrue(notified, 'the employee is notified (they follow the ticket)')
        self.assertEqual(notified.notification_type, 'email')
        self.assertEqual(ticket.last_public_by, 'hr')

        note = ticket.with_user(self.hr).message_post(
            body='Internal: check with payroll', message_type='comment',
            subtype_xmlid='mail.mt_note')
        self.assertEqual(ticket.state, 'answered', 'a note changes nothing')
        ids = [m['id'] for m in ticket._portal_messages()]
        self.assertIn(msg.id, ids)
        self.assertNotIn(note.id, ids)
        self.assertFalse(self.env['mail.notification'].sudo().search([
            ('mail_message_id', '=', note.id),
            ('res_partner_id', '=', self.share.partner_id.id)]))
        # the employee's reply hands it back
        reply = ticket.with_user(self.share).sudo()._portal_reply('Thanks, one more question')
        self.assertEqual(ticket.state, 'with_hr')
        self.assertEqual(reply.author_id, self.share.partner_id)
        self.assertEqual(ticket.last_public_by, 'employee')
        thread = ticket._portal_messages()
        self.assertEqual([m['is_employee'] for m in thread], [False, True])
        self.assertEqual(thread[0]['initials'], 'TO')

    # T3.5
    def test_t3_5_hr_owner_setting(self):
        self.env['ir.config_parameter'].sudo().set_param(self.param, str(self.hr.id))
        ticket = self._ask(self.share, self.share_emp)
        self.assertEqual(ticket.user_id, self.hr)
        todo = ticket.activity_ids
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo.user_id, self.hr)
        self.assertIn(self.hr.partner_id, ticket.message_partner_ids)
        # answering finishes the owner's to-do
        ticket.with_user(self.hr).message_post(
            body='Done', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertFalse(ticket.activity_ids)

        self.env['ir.config_parameter'].sudo().set_param(self.param, False)
        bare = self._ask(self.share, self.share_emp, subject='No owner')
        self.assertFalse(bare.user_id)
        self.assertFalse(bare.activity_ids)
        # a portal account is never an owner
        self.env['ir.config_parameter'].sudo().set_param(self.param, str(self.other.id))
        self.assertFalse(self._ask(self.share, self.share_emp, subject='Bad owner').user_id)

    def test_t3_5b_settings_read_and_write_the_parameter(self):
        settings = self.env['res.config.settings'].create({'pb_ask_hr_owner_id': self.hr.id})
        settings.execute()
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param(self.param),
                         str(self.hr.id))
        self.assertEqual(self.env['res.config.settings'].create({}).pb_ask_hr_owner_id, self.hr)

    # T3.6 — this module's source on My requests
    def test_t3_6_ask_hr_on_my_requests(self):
        ticket = self._ask(self.share, self.share_emp)
        Home = self.env['pb.me.home'].with_user(self.share)
        rows = [r for r in Home.get_my_requests(self.share_emp)['rows'] if r['key'] == 'ask_hr']
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['state_label'], rows[0]['tone']), ('Sent', 'wait'))
        self.assertEqual(rows[0]['url'], '/my/ask-hr/%s' % ticket.id)
        ticket.with_user(self.hr).message_post(
            body='Answer', message_type='comment', subtype_xmlid='mail.mt_comment')
        row = [r for r in Home.get_my_requests(self.share_emp)['rows'] if r['key'] == 'ask_hr'][0]
        self.assertEqual((row['state_label'], row['tone'], row['bucket']),
                         ('Answered — your turn', 'act', 'act'))
        needs = Home.get_home_data(self.share_emp)['needs_you']
        self.assertEqual(needs[-1]['key'], 'ask_hr_answered')
        self.assertEqual(needs[-1]['label'], 'HR answered your question')
        self.assertEqual(needs[-1]['url'], '/my/ask-hr/%s' % ticket.id)

    # T3.10
    def test_t3_10_backend_queue_and_access(self):
        action = self.env['ir.actions.act_window'].with_user(self.hr)._for_xml_id(
            'pb_ask_hr.action_pb_ask_hr_ticket')
        self.assertEqual(action['res_model'], 'pb.ask.hr.ticket')
        self.assertTrue(action['view_mode'].startswith('kanban'))
        views = self.Ticket.with_user(self.hr).get_views(
            [(False, 'kanban'), (False, 'list'), (False, 'form'), (False, 'search')])
        for kind in ('kanban', 'list', 'form', 'search'):
            self.assertIn(kind, views['views'])
        self.assertIn('Reply with Send message', views['views']['form']['arch'])
        groups = self.Ticket.with_user(self.hr).with_context(
            read_group_expand=True).formatted_read_group([], ['state'], ['__count'])
        self.assertEqual([g['state'] for g in groups], ['new', 'with_hr', 'answered', 'closed'],
                         'every state is a column, even empty')

        ticket = self._ask(self.share, self.share_emp)
        ticket.with_user(self.hr).action_take()
        self.assertEqual(ticket.user_id, self.hr)
        self.assertEqual(ticket.state, 'with_hr')
        self.assertIn(self.hr.partner_id, ticket.message_partner_ids)

        own = self._ask(self.plain, self.plain_emp, subject='Plain question')
        as_plain = self.Ticket.with_user(self.plain)
        self.assertEqual(as_plain.browse(own.id).read(['name'])[0]['name'], 'Plain question')
        with self.assertRaises(AccessError):
            as_plain.browse(ticket.id).read(['name'])
        with self.assertRaises(AccessError):
            as_plain.browse(own.id).write({'name': 'Changed'})
        self.assertEqual(as_plain.search([]).ids, [own.id])
        # D3: an employee login has no ACL at all on this model
        with self.assertRaises(AccessError):
            self.Ticket.with_user(self.share).search([])
        portal = self.env.ref('base.group_portal')
        self.assertFalse(self.env['ir.model.access'].sudo().search([
            ('model_id.model', '=', 'pb.ask.hr.ticket'), ('group_id', '=', portal.id)]))

    def test_t3_10b_sidebar_and_menu(self):
        menu = self.env.ref('pb_ask_hr.menu_pb_ask_hr_ticket')
        self.assertEqual(menu.parent_id, self.env.ref('hr.menu_hr_root'))
        if 'pb.sidebar.item' in self.env:
            item = self.env.ref('pb_ask_hr.item_ask_hr')
            self.assertTrue(item.active)
            self.assertIn(self.env.ref('hr.group_hr_user'), item.groups_id)


@tagged('post_install', '-at_install')
class TestAskHrPages(_AskHrCommon, HttpCase):
    """T3.3, T3.4, T3.9 — over HTTP, as an employee login and as a full
    account (T-R6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls._fixtures('test_t3a_http', PASSWORD)
        cls.env['ir.config_parameter'].sudo().set_param(
            'pb_ask_hr.owner_uid.%s' % cls.env.company.id, False)

    def _post(self, url, data=None, files=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, files=files, timeout=60)

    def _text(self, response):
        return (response.text or '').replace('&#39;', "'")

    def _flow(self, user, password, emp):
        self.authenticate(user.login, password)
        page = self.url_open('/my/ask-hr', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Nothing asked yet', page.text)
        self.assertIn('When you ask HR a question, it lives here with their answer.', self._text(page))
        new = self.url_open('/my/ask-hr/new', timeout=60)
        self.assertEqual(new.status_code, 200)
        self.assertIn('they usually answer within a working day', new.text)
        self.assertEqual(len(re.findall(r'class="pbah-cat-input"', new.text)), 6)
        # the three fields are drawn (an empty t-out drops its element)
        for field in ('name="subject"', 'name="text"', 'name="attachments"'):
            self.assertIn(field, new.text)

        # a missing subject comes back with the reason, nothing created
        refused = self._post('/my/ask-hr/new', {'category': 'pay', 'subject': ' '})
        self.assertEqual(refused.status_code, 200)
        self.assertIn('Add a subject so HR knows', refused.text)
        self.assertFalse(self.Ticket.sudo().search([('employee_id', '=', emp.id)]))

        response = self._post(
            '/my/ask-hr/new',
            {'category': 'pay', 'subject': 'T3 missing overtime', 'text': 'Line one\nLine two',
             'employee_id': self.other_emp.id},            # ignored: never a form value
            files={'attachments': ('t3-proof.pdf', _PDF, 'application/pdf')})
        self.assertEqual(response.status_code, 200)
        ticket = self.Ticket.sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(len(ticket), 1)
        self.assertFalse(self.Ticket.sudo().search([('employee_id', '=', self.other_emp.id)]))
        self.assertEqual(ticket.create_uid, user)
        self.assertEqual(ticket.category, 'pay')
        self.assertEqual(len(ticket.attachment_ids), 1)
        self.assertEqual(ticket.attachment_ids.res_model, 'pb.ask.hr.ticket')
        self.assertEqual(ticket.attachment_ids.res_id, ticket.id)
        self.assertEqual(urlparse_path(response.url), '/my/ask-hr/%s' % ticket.id)
        text = self._text(response)
        self.assertIn('Line one', text)
        self.assertIn('pbah-pill--new', text)
        self.assertIn('Sent to HR', text)
        link = re.search(r'/web/content/(\d+)\?download=true(?:&amp;|&)access_token=([\w-]+)', text)
        self.assertTrue(link, 'the file link carries its token')
        file = self.url_open('/web/content/%s?download=true&access_token=%s'
                             % (link.group(1), link.group(2)), timeout=60)
        self.assertEqual(file.status_code, 200)
        self.assertEqual(file.content, _PDF)

        url = '/my/ask-hr/%s' % ticket.id
        empty = self._post(url + '/reply', {'body': '  '})
        self.assertEqual(empty.status_code, 200)
        self.assertIn('Write a message, or attach a file', self._text(empty))
        reply = self._post(url + '/reply', {'body': 'Any news on this?'})
        self.assertEqual(reply.status_code, 200)
        ticket.invalidate_recordset()
        self.assertEqual(ticket.state, 'with_hr')
        self.assertIn('Any news on this?', reply.text)
        self.assertIn('Reply sent', reply.text)

        ticket.with_user(self.hr).message_post(
            body='It goes out with the next pay run.', message_type='comment',
            subtype_xmlid='mail.mt_comment')
        ticket.with_user(self.hr).message_post(
            body='PRIVATE NOTE FOR HR', message_type='comment', subtype_xmlid='mail.mt_note')
        page = self.url_open(url, timeout=60)
        text = self._text(page)
        self.assertIn('It goes out with the next pay run.', text)
        self.assertNotIn('PRIVATE NOTE FOR HR', text)
        self.assertIn('pbah-msg is-hr', text)
        self.assertIn('pbah-pill--answered', text)
        self.assertIn('Did that answer it?', text)
        listing = self.url_open('/my/ask-hr', timeout=60)
        self.assertIn('pbah-row is-unread', listing.text)
        home = self.url_open('/my', timeout=60)
        self.assertIn('HR answered your question', self._text(home))

        closed = self._post(url + '/close')
        self.assertEqual(closed.status_code, 200)
        ticket.invalidate_recordset()
        self.assertEqual((ticket.state, ticket.closed_by), ('closed', 'employee'))
        self.assertIn('pbah-pill--closed', closed.text)
        self.assertIn('Marked as solved', closed.text)
        again = self._post(url + '/close')
        self.assertEqual(again.status_code, 200)
        self.assertIn('Already closed', again.text)
        reopened = self._post(url + '/reopen')
        self.assertEqual(reopened.status_code, 200)
        ticket.invalidate_recordset()
        self.assertEqual(ticket.state, 'with_hr')
        self.assertIn('Reopened', reopened.text)

        # somebody else's question: a 404 page, never a 500, nothing changed
        theirs = self._ask(self.other, self.other_emp, subject='Theirs')
        for path in ('/my/ask-hr/%s' % theirs.id,):
            response = self.url_open(path, timeout=60)
            self.assertEqual(response.status_code, 404)
            self.assertIn('We could not find that question', response.text)
            self.assertNotIn('Theirs', response.text)
        for action in ('reply', 'close', 'reopen'):
            response = self._post('/my/ask-hr/%s/%s' % (theirs.id, action), {'body': 'x'})
            self.assertEqual(response.status_code, 404, action)
        theirs.invalidate_recordset()
        self.assertEqual(theirs.state, 'new')
        self.assertFalse(theirs._portal_messages())
        missing = self.url_open('/my/ask-hr/999999999', timeout=60)
        self.assertEqual(missing.status_code, 404)

    # T3.3
    def test_t3_3_flow_for_an_employee_login(self):
        self._flow(self.share, PASSWORD, self.share_emp)

    def test_t3_3b_flow_for_a_full_account(self):
        self._flow(self.plain, T1_PASSWORD, self.plain_emp)

    def test_t3_3c_a_wrong_file_is_refused_with_its_reason(self):
        self.authenticate(self.share.login, PASSWORD)
        response = self._post(
            '/my/ask-hr/new', {'category': 'other', 'subject': 'With a script'},
            files={'attachments': ('evil.html', b'<script>1</script>', 'text/html')})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Files can be PDF, JPG or PNG', response.text)
        self.assertIn('With a script', response.text, 'what was typed is kept')
        self.assertIn('name="text"', response.text)
        self.assertFalse(self.Ticket.sudo().search([('employee_id', '=', self.share_emp.id)]))

    # T3.4
    def test_t3_4_access_token(self):
        ticket = self._ask(self.share, self.share_emp, subject='Token probe')
        token = ticket.sudo()._portal_ensure_token()
        url = '/my/ask-hr/%s' % ticket.id
        self.authenticate(self.share.login, PASSWORD)
        mine = self.url_open(url + '?access_token=wrong', timeout=60)
        self.assertEqual(mine.status_code, 200, 'the session owns it')
        self.assertIn('pbah-composer', mine.text)
        self.authenticate(self.other.login, PASSWORD)
        shared = self.url_open('%s?access_token=%s' % (url, token), timeout=60)
        self.assertEqual(shared.status_code, 200)
        self.assertIn('Token probe', shared.text)
        self.assertIn('shared link', shared.text)
        self.assertNotIn('pbah-composer', shared.text, 'only the owner can reply')
        wrong = self.url_open(url + '?access_token=wrong', timeout=60)
        self.assertEqual(wrong.status_code, 404)
        bare = self.url_open(url, timeout=60)
        self.assertEqual(bare.status_code, 404)

    # T3.9 (the tile)
    def test_t3_9_home_tile_in_people(self):
        self.authenticate(self.share.login, PASSWORD)
        page = self.url_open('/my', timeout=60)
        doc = lxml_html.fromstring(page.text)
        groups = doc.xpath("//div[contains(@class, 'o_portal_index_card')]"
                           "[.//a[@href='/my/ask-hr']]/@data-pbme-group")
        self.assertEqual(groups, ['people'])
        counters = self.make_jsonrpc_request('/my/counters', {'counters': ['askhr_count']})
        self.assertEqual(counters.get('askhr_count'), 0)


def urlparse_path(url):
    from urllib.parse import urlparse
    return urlparse(url).path
