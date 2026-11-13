# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ETP E3 — the pages over HTTP (handover E3.7 pages, E3.9 over JSON-RPC,
E3.10), as an employee login AND as a full account (T-R6)."""
import logging
import re
from datetime import timedelta

from odoo import http
from odoo.tests import HttpCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import _pin_dbfilter
from odoo.addons.pb_me_project_time.models.project_time import PARAM

from .common import MONDAY, PASSWORD, lines_of, setup_e3

_logger = logging.getLogger(__name__)


def _text(html):
    """The page as a person reads it: tags out, spaces folded."""
    html = re.sub(r'<(script|style)\b.*?</\1>', ' ', html or '', flags=re.S)
    return ' '.join(re.sub(r'<[^>]+>', ' ', html).replace('&#39;', "'").split())


@tagged('post_install', '-at_install')
class TestE3ProjectTimePages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        setup_e3(cls, 'test_e3_http', password=PASSWORD)

    def _post(self, url, data=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, timeout=60)

    def _flow(self, user, emp):
        self.authenticate(user.login, PASSWORD)
        week = MONDAY.isoformat()
        page = self.url_open('/my/project-time?week=%s' % week, timeout=60)
        self.assertEqual(page.status_code, 200)
        text = _text(page.text)
        self.assertIn('Nothing logged this week yet.', text)
        self.assertIn('Add a project and type your hours', text)
        self.assertEqual(len(re.findall(r'<th[^>]*class="pbpt-h pbpt-c', page.text)), 7,
                         'the seven day headers')
        self.assertRegex(page.text, r'data-pbpt-ring-logged="">0</b>\s*<small>of 40 h</small>')
        self.assertIn('0 of 40 h', text)
        self.assertIn('Add a project', text)
        self.assertIn('Looking for when you clocked in and out?', text)
        self.assertIn('href="/my/work/timesheet"', page.text)
        self.assertIn('name="csrf_token"', page.text)
        # Monday is index 0: a falsy t-att value must still be drawn
        self.assertIn('data-i="0"', page.text)
        self.assertIn('data-pbpt-tab="0"', page.text)

        # jsonrpc: add a row, then 8 on Monday
        added = self.make_jsonrpc_request('/my/project-time/row/add', {
            'project_id': self.proj.id, 'task_id': self.task_a.id,
            'week': week, 'rows': ''})
        self.assertTrue(added['ok'], added)
        key = '%s-%s' % (self.proj.id, self.task_a.id)
        self.assertEqual(added['rows'], key)
        self.assertIn('data-key="%s"' % key, added['html'])
        cell = self.make_jsonrpc_request('/my/project-time/cell', {
            'project_id': self.proj.id, 'task_id': self.task_a.id,
            'date': week, 'hours': '8',
            # E3.9: an employee_id in the request is swallowed, never used
            'employee_id': self.other_emp.id})
        self.assertTrue(cell['ok'], cell)
        self.assertEqual(cell['week_total'], 8.0)
        self.assertEqual(cell['hours_text'], '8')
        line = lines_of(self, emp)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.employee_id, emp)
        self.assertEqual(line.create_uid, user)
        self.assertFalse(lines_of(self, self.other_emp))
        refused = self.make_jsonrpc_request('/my/project-time/cell', {
            'project_id': self.other_proj.id, 'task_id': 0, 'date': week, 'hours': '1'})
        self.assertFalse(refused['ok'])
        self.assertIn('cannot log time on that project', refused['error'])

        page = self.url_open('/my/project-time?week=%s' % week, timeout=60)
        text = _text(page.text)
        self.assertIn('E3 Website refresh', text)
        self.assertIn('E3 Design', text)
        self.assertIn('name="h-%s-%s" value="8"' % (key, week), page.text)
        self.assertIn('8 of 40 h', text)
        self.assertNotIn('Nothing logged this week yet.', text)

        # the no-JS form with two cells → both saved, then the redirect
        tue = (MONDAY + timedelta(days=1)).isoformat()
        wed = (MONDAY + timedelta(days=2)).isoformat()
        posted = self._post('/my/project-time', {
            'week': week, 'rows': '', 'op': 'save',
            'h-%s-%s' % (key, tue): '7:30',
            'n-%s-%s' % (key, tue): 'Logo review',
            'h-%s-%s' % (key, wed): '6',
            'h-%s-%s' % (key, week): '8',
        })
        self.assertEqual(posted.status_code, 200)
        self.assertIn('done=saved', posted.url)
        self.assertIn('Your week is saved.', _text(posted.text))
        hours = {l.date.isoformat(): (l.unit_amount, l.name) for l in lines_of(self, emp)}
        self.assertEqual(hours[tue], (7.5, 'Logo review'))
        self.assertEqual(hours[wed][0], 6.0)
        self.assertEqual(hours[week][0], 8.0)
        self.assertIn('21.5 of 40 h', _text(posted.text))

        # a refused cell in the form: the page says which and why
        bad = self._post('/my/project-time', {
            'week': week, 'rows': '', 'op': 'save',
            'h-%s-%s' % (key, wed): '30'})
        self.assertEqual(bad.status_code, 200)
        self.assertIn('Some hours did not save.', _text(bad.text))
        self.assertIn('24 hours at most', _text(bad.text))

        # ?week= the previous week
        prev = self.url_open('/my/project-time?week=%s' % (MONDAY - timedelta(days=3)).isoformat(),
                             timeout=60)
        self.assertIn('/my/project-time?week=%s' % week, prev.text, 'its next week is ours')
        self.assertIn('data-week="%s"' % (MONDAY - timedelta(days=7)).isoformat(), prev.text)

        # copy last week into the next one, no script
        nxt = (MONDAY + timedelta(days=7)).isoformat()
        copied = self._post('/my/project-time', {'week': nxt, 'op': 'copy'})
        self.assertIn('done=copied', copied.url)
        self.assertIn('3 cells copied from last week.', _text(copied.text))

        # the home: the tile, and (after the lines) the card
        home = self.url_open('/my', timeout=60)
        self.assertEqual(home.status_code, 200)
        self.assertIn('href="/my/project-time"', home.text)
        self.assertIn('Project time', home.text)
        _logger.info('E3.10 | %s: empty → add → cell → reload → form → copy → home',
                     user.login)
        return home

    def test_e3_10_flow_for_an_employee_login(self):
        self._flow(self.share, self.share_emp)

    def test_e3_10b_flow_for_a_full_account(self):
        self._flow(self.plain, self.plain_emp)

    def test_e3_10c_home_card_this_week(self):
        """The card appears once the person has logged project time lately
        (this test logs it in the CURRENT week, so it holds on any date)."""
        self.authenticate(self.share.login, PASSWORD)
        home = self.url_open('/my', timeout=60)
        self.assertNotIn('Project time this week', home.text, 'quiet at zero')
        Pt = self.env['pb.me.project.time'].with_user(self.share)
        today = Pt._today(self.share_emp)
        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, today, '3')
        home = self.url_open('/my', timeout=60)
        self.assertIn('Project time this week', home.text)
        self.assertIn('Open the week', home.text)
        self.assertIn('pbme-b-pt', home.text)

    def test_e3_7_switch_off_pages(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM % self.company.id, '0')
        self.authenticate(self.share.login, PASSWORD)
        page = self.url_open('/my/project-time', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Project time is switched off for your company', _text(page.text))
        self.assertNotIn('pbpt-t', page.text)
        posted = self._post('/my/project-time', {
            'week': MONDAY.isoformat(),
            'h-%s-%s-%s' % (self.proj.id, self.task_a.id, MONDAY.isoformat()): '4'})
        self.assertEqual(posted.status_code, 200)
        self.assertIn('switched off for your company', _text(posted.text))
        self.assertFalse(lines_of(self, self.share_emp))
        cell = self.make_jsonrpc_request('/my/project-time/cell', {
            'project_id': self.proj.id, 'task_id': self.task_a.id,
            'date': MONDAY.isoformat(), 'hours': '4'})
        self.assertFalse(cell['ok'])
        home = self.url_open('/my', timeout=60)
        self.assertNotIn('href="/my/project-time"', home.text, 'no tile')
        self.assertNotIn('Project time this week', home.text, 'no card')

    def test_e3_10d_no_employee_and_get_only_actions(self):
        from odoo.addons.pb_me_portal.tests.test_portal_accounts import _make_share
        nobody, _none = _make_share(self.env, 'test_e3_http_nobody', 'E3 Nobody',
                                    PASSWORD, employee=False)
        self.authenticate(nobody.login, PASSWORD)
        page = self.url_open('/my/project-time', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Project time is not set up for you yet', _text(page.text))
        res = self.make_jsonrpc_request('/my/project-time/cell', {
            'project_id': self.proj.id, 'task_id': 0, 'date': MONDAY.isoformat(),
            'hours': '1'})
        self.assertFalse(res['ok'])

    def test_e3_10e_add_without_script_and_vietnamese(self):
        self.authenticate(self.share.login, PASSWORD)
        key = '%s-%s' % (self.proj.id, self.task_b.id)
        page = self.url_open('/my/project-time?week=%s&rows=&add=%s'
                             % (MONDAY.isoformat(), key), timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-key="%s"' % key, page.text)
        self.assertIn('pbpt-r is-new', page.text)
        self.assertIn('data-rows="%s"' % key, page.text)
        # the time-off task is never in the picker
        if self.leave_task:
            self.assertNotIn('data-key="%s-%s"' % (self.leave_task.project_id.id,
                                                   self.leave_task.id), page.text)
        website = self.env['website'].search([], limit=1) if 'website' in self.env else None
        if website and 'vi_VN' in website.language_ids.mapped('code'):
            vi = self.url_open('/vi/my/project-time?week=%s&rows=' % MONDAY.isoformat(),
                               timeout=60)
            self.assertEqual(vi.status_code, 200)
            text = _text(vi.text)
            self.assertNotIn('Nothing logged this week yet.', text)
            self.assertIn('Giờ theo dự án', text)
