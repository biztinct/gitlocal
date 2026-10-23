# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3b — the notice board (handover T3B_HANDOVER.md, tests T3b.6 and
T3b.7).

T3b.6 the facade over pb_hr_comm's delivery rows (own rows only, sent only,
read receipts once), T3b.7 the pages and the home over HTTP as an employee
login.
"""
import base64
import logging
from datetime import datetime, timedelta

from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import (
    _make_share, _pin_dbfilter,
)

_logger = logging.getLogger(__name__)

PASSWORD = 'tiers-t3b-notices-probe-2026'

# a 1×1 PNG
_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGA'
    'hKmMIQAAAABJRU5ErkJggg==')


def _post(env, subject, body='<p>Everybody in the canteen at four.</p>',
          sent=True, poster=False):
    """An announcement through pb_hr_comm's own state door (`_hc_move`, as its
    own tests do). ``sent=False`` leaves it scheduled."""
    vals = {
        'subject': subject,
        'body_html': body,
        'company_id': env.company.id,
        'audience_kind': 'everyone',
        'send_at': datetime.now() + timedelta(days=5),
    }
    post = env['pb.hr.comm.post'].sudo().create(vals)
    if poster:
        att = env['ir.attachment'].sudo().create({
            'name': 'poster.png', 'datas': base64.b64encode(_PNG),
            'mimetype': 'image/png'})
        post.write({'poster_ids': [(6, 0, att.ids)]})
    post._hc_move('scheduled')
    if sent:
        post._hc_move('sending')
        post._hc_move('sent')
    return post


def _deliver(env, post, emp):
    return env['pb.hr.comm.delivery'].sudo().create(
        {'post_id': post.id, 'employee_id': emp.id, 'email': 'probe@example.invalid'})


@tagged('post_install', '-at_install')
class TestT3bNoticesModel(TransactionCase):
    """T3b.6 — as an employee login."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3b_notice_share', 'Quinn Notice Share')
        cls.other, cls.other_emp = _make_share(
            cls.env, 'test_t3b_notice_other', 'Rowan Notice Other')
        cls.Notices = cls.env['pb.me.notices'].with_user(cls.share)

    # T3b.6
    def test_t3b_6_own_sent_rows_and_read_receipts(self):
        mine = _post(self.env, 'T3b Town hall', poster=True)
        theirs = _post(self.env, 'T3b Theirs only')
        _deliver(self.env, mine, self.share_emp)
        _deliver(self.env, theirs, self.other_emp)
        scheduled = _post(self.env, 'T3b Not out yet', sent=False)
        _deliver(self.env, scheduled, self.share_emp)

        rows = self.Notices.get_my_notices(self.share_emp)
        self.assertEqual([r['post_id'] for r in rows], [mine.id],
                         'own delivery rows of sent announcements only')
        row = rows[0]
        self.assertFalse(row['read'])
        self.assertEqual(row['subject'], 'T3b Town hall')
        self.assertEqual(row['excerpt'], 'Everybody in the canteen at four.')
        self.assertTrue(row['has_poster'])
        self.assertIn('access_token=', row['poster_url'])
        self.assertTrue(row['sent_on'])
        self.assertEqual(self.Notices.unread_count(self.share_emp), 1)
        self.assertEqual(self.Notices.notice_counts(self.share_emp),
                         {'total': 1, 'unread': 1})

        self.assertTrue(self.Notices.mark_read(self.share_emp, mine.id))
        self.assertTrue(self.Notices.get_my_notices(self.share_emp)[0]['read'])
        self.assertEqual(self.Notices.unread_count(self.share_emp), 0)
        self.assertTrue(self.Notices.mark_read(self.share_emp, mine.id), 'again: no error')
        Read = self.env['pb.me.notice.read'].sudo()
        self.assertEqual(Read.search_count([('post_id', '=', mine.id),
                                            ('employee_id', '=', self.share_emp.id)]), 1)
        # the constraint path itself: a raced second writer is swallowed
        self.assertFalse(self.Notices._notice_read_create(mine.id, self.share_emp))
        self.assertEqual(Read.search_count([('post_id', '=', mine.id),
                                            ('employee_id', '=', self.share_emp.id)]), 1)
        read = Read.search([('post_id', '=', mine.id)])
        self.assertEqual(read.create_uid, self.share, 'sudo keeps env.uid')

        # not theirs, not sent, not the caller's own employee: nothing
        self.assertFalse(self.Notices.mark_read(self.share_emp, theirs.id))
        self.assertFalse(self.Notices.mark_read(self.share_emp, scheduled.id))
        self.assertIsNone(self.Notices.get_my_notice(self.share_emp, theirs.id))
        self.assertIsNone(self.Notices.get_my_notice(self.share_emp, scheduled.id))
        self.assertEqual(self.Notices.get_my_notices(self.other_emp), [],
                         'another person\'s employee is refused (M-R4)')
        self.assertEqual(self.Notices.unread_count(self.other_emp), 0)
        self.assertFalse(self.Notices.mark_read(self.other_emp, theirs.id))

    def test_t3b_6b_unread_first_page_and_needs_row(self):
        older = _post(self.env, 'T3b Older')
        newer = _post(self.env, 'T3b Newer')
        d1 = _deliver(self.env, older, self.share_emp)
        d2 = _deliver(self.env, newer, self.share_emp)
        d1.sudo().write({'sent_on': datetime.now() - timedelta(days=3)})
        d2.sudo().write({'sent_on': datetime.now() - timedelta(hours=2)})
        rows = self.Notices.get_my_notices(self.share_emp)
        self.assertEqual([r['subject'] for r in rows], ['T3b Newer', 'T3b Older'])
        self.assertEqual(rows[1]['ago']['unit'], 'd')
        one = self.Notices.get_my_notice(self.share_emp, older.id)
        self.assertEqual(one['newer_url'], '/my/notices/%s' % newer.id)
        self.assertIsNone(one['older_url'])
        self.assertIn('canteen', one['body_html'])

        Home = self.env['pb.me.home'].with_user(self.share)
        data = Home.get_home_data(self.share_emp)
        cards = {c['key']: c for c in data['extra_cards']}
        self.assertIn('notices', cards)
        self.assertEqual(cards['notices']['data']['unread'], 2)
        self.assertEqual(len(cards['notices']['data']['rows']), 2)
        needs = {n['key']: n for n in data['needs_you']}
        self.assertEqual(needs['notices_unread']['n'], 2)
        self.assertEqual(needs['notices_unread']['label'], '2 unread notices')
        self.assertEqual(needs['notices_unread']['tone'], 'slate')
        self.assertEqual(needs['notices_unread']['url'], '/my/notices')

    def test_t3b_6c_an_archived_announcement_is_gone(self):
        post = _post(self.env, 'T3b Archived')
        _deliver(self.env, post, self.share_emp)
        post.sudo().write({'active': False})
        self.assertEqual(self.Notices.get_my_notices(self.share_emp), [])

    def test_t3b_6d_no_portal_acl(self):
        acl = self.env['ir.model.access'].sudo().search([
            ('model_id.model', '=', 'pb.me.notice.read'),
            ('group_id', '=', self.env.ref('base.group_portal').id)])
        self.assertFalse(acl)


@tagged('post_install', '-at_install')
class TestT3bNoticesPages(HttpCase):
    """T3b.7 — over HTTP, as an employee login (T-R6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3b_notice_http', 'Quinn Notice Http', PASSWORD)
        cls.other, cls.other_emp = _make_share(
            cls.env, 'test_t3b_notice_http2', 'Rowan Notice Http', PASSWORD)

    def _text(self, response):
        return (response.text or '').replace('&#39;', "'")

    # T3b.7
    def test_t3b_7_board_notice_and_home(self):
        self.authenticate(self.share.login, PASSWORD)
        empty = self.url_open('/my/notices', timeout=60)
        self.assertEqual(empty.status_code, 200)
        self.assertIn('No notices yet', empty.text)
        self.assertIn('When HR posts one, it lands here.', empty.text)
        home = self.url_open('/my', timeout=60)
        self.assertIn('pbme-b-notices', home.text)
        self.assertIn('When HR posts one, it lands here.', home.text)
        self.assertIn('href="/my/notices"', home.text, 'the Notices tile')

        post = _post(self.env, 'T3b Canteen reopens', poster=True)
        _deliver(self.env, post, self.share_emp)
        theirs = _post(self.env, 'T3b Not for Quinn')
        _deliver(self.env, theirs, self.other_emp)

        board = self.url_open('/my/notices', timeout=60)
        self.assertEqual(board.status_code, 200)
        self.assertIn('T3b Canteen reopens', board.text)
        self.assertNotIn('T3b Not for Quinn', board.text)
        self.assertIn('pbnb-hero is-unread', board.text)
        self.assertIn('pbnb-newtag', board.text)

        home = self.url_open('/my', timeout=60)
        self.assertIn('T3b Canteen reopens', home.text, 'the Notices card')
        self.assertIn('1 unread notice', home.text, 'the needs-you row')
        self.assertIn('pbnb-card is-unread', home.text)

        page = self.url_open('/my/notices/%s' % post.id, timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('T3b Canteen reopens', page.text)
        self.assertIn('Everybody in the canteen at four.', page.text)
        self.assertIn('pbnb-dot is-fading', page.text, 'the dot fades once')
        self.assertIn('access_token=', page.text, 'the poster opens for an employee login')

        board = self.url_open('/my/notices', timeout=60)
        self.assertNotIn('is-unread', board.text, 'the dot is gone')
        again = self.url_open('/my/notices/%s' % post.id, timeout=60)
        self.assertNotIn('is-fading', again.text)

        missing = self.url_open('/my/notices/%s' % theirs.id, timeout=60)
        self.assertEqual(missing.status_code, 404)
        self.assertIn('We could not find that notice', missing.text)
        self.assertEqual(self.url_open('/my/notices/999999999', timeout=60).status_code, 404)

        home = self.url_open('/my', timeout=60)
        self.assertNotIn('unread notice', home.text)
        _logger.info('T3b.7 | board → home → notice → read → 404')
