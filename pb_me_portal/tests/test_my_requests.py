# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3a — the home hooks and "My requests" (handover
docs/handovers/tiers/T3A_HANDOVER.md, tests T3.6–T3.9).

T3.6 the sources (one row per record, label/tone/url, newest first, a broken
source skipped), T3.7 the page over HTTP, T3.8 the generic needs-you row,
T3.9 the two new tiles.
"""
import logging
import re
from datetime import date, timedelta
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import http
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_me_portal.models import pb_me_home

from .test_portal_accounts import _make_share, _pin_dbfilter
from .test_portal_only import PASSWORD as T1_PASSWORD, _make_people

_logger = logging.getLogger(__name__)

PASSWORD = 'tiers-t3a-requests-probe-2026'
_HOME_LOGGER = 'odoo.addons.pb_me_portal.models.pb_me_home'


def _make_requests(env, emp):
    """One record of every installed source for ``emp``, created under sudo
    with minimal fields. ``{source key: record}``; a source whose module is
    absent (or whose create this database refuses) is skipped and logged."""
    made = {}
    today = date.today()
    monday = today + timedelta(days=(7 - today.weekday()) % 7 + 21)

    def leave():
        kind = env['hr.leave.type'].sudo().create({
            'name': 'T3 Probe Leave', 'requires_allocation': False,
            'company_id': emp.company_id.id})
        return env['hr.leave'].sudo().create({
            'employee_id': emp.id, 'holiday_status_id': kind.id,
            'request_date_from': monday, 'request_date_to': monday})

    def timesheet_fix():
        return env['hr.attendance.correction'].sudo().create({
            'employee_id': emp.id, 'date': today - timedelta(days=2),
            'reason': 'T3 probe', 'correction_type': 'create'})

    def profile():
        return env['pb.profile.change.request'].sudo().create({
            'employee_id': emp.id, 'x_phone': '0912 000 333',
            'company_id': emp.company_id.id})

    def asset():
        cat = env.ref('pb_assets.cat_laptop', raise_if_not_found=False) or \
            env['pb.asset.category'].sudo().search([], limit=1)
        return env['pb.asset.request'].sudo().create({
            'employee_id': emp.id, 'category_id': cat.id,
            'needed_by': today + timedelta(days=10)})

    def resignation():
        return env['pb.resignation'].sudo().create({
            'employee_id': emp.id, 'reason_text': 'T3 probe',
            'requested_lwd': today + timedelta(days=40)})

    def overtime():
        return env['hr.overtime.request'].sudo().create({
            'employee_id': emp.id, 'date': today - timedelta(days=5),
            'planned_hours': 2.0, 'reason': 'T3 probe'})

    makers = (('leave', 'hr.leave', leave),
              ('timesheet_fix', 'hr.attendance.correction', timesheet_fix),
              ('profile', 'pb.profile.change.request', profile),
              ('asset', 'pb.asset.request', asset),
              ('resignation', 'pb.resignation', resignation),
              ('overtime', 'hr.overtime.request', overtime))
    for key, model, make in makers:
        if model not in env:
            _logger.info('T3.6 | source %s skipped: %s not installed', key, model)
            continue
        try:
            with env.cr.savepoint():
                made[key] = make()
        except Exception as exc:        # noqa: BLE001 — a fixture, reported
            _logger.warning('T3.6 | source %s fixture refused here: %s', key, exc)
    return made


@tagged('post_install', '-at_install')
class TestMyRequestsModel(TransactionCase):
    """T3.6, T3.8, T3.9 (registry) — as an employee login."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3a_req_share', 'Quinn Requests Share')
        cls.Home = cls.env['pb.me.home'].with_user(cls.share)

    # T3.6
    def test_t3_6_one_row_per_record_newest_first(self):
        made = _make_requests(self.env, self.share_emp)
        self.assertGreaterEqual(len(made), 4, 'most sources exist on this build: %s' % list(made))
        data = self.Home.get_my_requests(self.share_emp)
        rows = data['rows']
        sources = {s['key']: s for s in self.Home._my_requests_sources()}
        for key, rec in made.items():
            mine = [r for r in rows if r['key'] == key]
            self.assertEqual(len(mine), 1, key)
            row, src = mine[0], sources[key]
            rec.invalidate_recordset()
            label, tone = src['states'].get(rec.state) or (rec.state, 'off')
            self.assertEqual(row['state_label'], label, key)
            self.assertEqual(row['tone'], tone, key)
            self.assertEqual(row['url'], src['url'](rec), key)
            self.assertEqual(row['kind'], src['label'], key)
            self.assertTrue(row['title'], key)
            self.assertEqual(row['bucket'], pb_me_home.REQUEST_BUCKETS[tone], key)
        stamps = [r['date'] for r in rows]
        self.assertEqual(stamps, sorted(stamps, reverse=True), 'newest first')
        counts = data['counts']
        self.assertEqual(counts['all'], len(rows))
        self.assertEqual(counts['act'] + counts['wait'] + counts['done'], len(rows))
        # the filter keeps one bucket, the counts stay whole
        wait = self.Home.get_my_requests(self.share_emp, 'wait')
        self.assertTrue(all(r['bucket'] == 'wait' for r in wait['rows']))
        self.assertEqual(wait['counts'], counts)
        _logger.info('T3.6 | sources with a row: %s', sorted(made))

    def test_t3_6b_a_broken_source_is_skipped(self):
        made = _make_requests(self.env, self.share_emp)
        self.assertIn('profile', made)
        Home = type(self.env['pb.me.home'])
        original = Home._my_requests_sources

        def broken(this):
            out = original(this)
            for src in out:
                if src['key'] == 'profile':
                    src['title'] = lambda rec: 1 / 0
            return out

        with patch.object(Home, '_my_requests_sources', broken), \
                self.assertLogs(_HOME_LOGGER, 'WARNING') as logs:
            data = self.Home.get_my_requests(self.share_emp)
        keys = {r['key'] for r in data['rows']}
        self.assertNotIn('profile', keys)
        self.assertEqual(keys, set(made) - {'profile'})
        self.assertTrue(any('pb.profile.change.request' in line for line in logs.output))

    def test_t3_6c_somebody_elses_employee_is_refused(self):
        other, other_emp = _make_share(self.env, 'test_t3a_req_other', 'Rowan Req Other')
        self.assertIsNone(self.Home.get_my_requests(other_emp))
        self.assertIsNone(self.Home.get_my_requests(self.env['res.partner']))

    # T3.8
    def test_t3_8_generic_needs_you_row(self):
        Home = type(self.env['pb.me.home'])

        def extra(this, emp, put):
            put('t3_probe', 1, '/my/requests', label='Probe', sub='x', icon='bell')
            put('t3_odd_tone', 2, '/my/requests', label='Odd', tone='neon')
            put('t3_zero', 0, '/my/requests', label='Never')

        with patch.object(Home, '_pbme_needs_extra', extra):
            data = self.Home.get_home_data(self.share_emp)
        needs = data['needs_you']
        keys = [n['key'] for n in needs]
        self.assertEqual(keys[-2:], ['t3_probe', 't3_odd_tone'], 'unknown keys come last, in order')
        self.assertNotIn('t3_zero', keys)
        self.assertEqual(needs[-1]['tone'], 'slate', 'a tone outside the kit falls back')
        probe = needs[-2]
        row = str(self.env['ir.qweb']._render('pb_me_portal.pbme_need_row', {'it': probe}))
        self.assertIn('Probe', row)
        self.assertIn('pbme-need-d', row)
        self.assertIn('pbme-badge--slate', row)
        sentence = str(self.env['ir.qweb']._render('pb_me_portal.pbme_need_sentence',
                                                   {'it': probe}))
        self.assertIn('Probe', sentence)
        # the known rows are untouched by the generic branch
        known = str(self.env['ir.qweb']._render('pb_me_portal.pbme_need_row', {
            'it': {'key': 'profile_waiting', 'n': 1, 'url': '/my/profile'}}))
        self.assertIn('Profile change with HR', known)

    def test_t3_8b_a_broken_extra_never_blanks_the_home(self):
        Home = type(self.env['pb.me.home'])

        def extra(this, emp, put):
            raise RuntimeError('T3 probe')

        with patch.object(Home, '_pbme_needs_extra', extra), \
                self.assertLogs(_HOME_LOGGER, 'WARNING'):
            data = self.Home.get_home_data(self.share_emp)
        self.assertIsInstance(data, dict)
        self.assertIn('needs_you', data)

    # T3.9 (registry half)
    def test_t3_9_tile_meta(self):
        ask = self.Home.tile_meta('/my/ask-hr')
        self.assertEqual((ask['group'], ask['icon']), ('people', 'message-circle-question'))
        req = self.Home.tile_meta('/my/requests')
        self.assertEqual((req['group'], req['icon']), ('me', 'list-checks'))
        self.assertEqual(req['title'], 'My requests')


@tagged('post_install', '-at_install')
class TestMyRequestsPage(HttpCase):
    """T3.7 and T3.9 (page half) — over HTTP as an employee login and as a
    full-account employee."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3a_reqp_share', 'Quinn Requests Page', PASSWORD)
        cls.plain, cls.plain_emp, _lead, _staff = _make_people(
            cls.env, 'test_t3a_reqp', password=T1_PASSWORD)

    def _rows(self, text):
        return len(re.findall(r'class="pbme-rq-row ', text))

    def _walk(self, login, password, emp):
        self.authenticate(login, password)
        empty = self.url_open('/my/requests', timeout=60)
        self.assertEqual(empty.status_code, 200)
        self.assertIn('Nothing asked yet', empty.text)

        Req = self.env['pb.profile.change.request'].sudo()
        waiting = Req.with_user(emp.user_id).sudo().create({
            'employee_id': emp.id, 'x_phone': '0912 111 222',
            'company_id': emp.company_id.id})
        waiting.action_submit()
        self.assertEqual(waiting.state, 'hr_review')
        Req.create({'employee_id': emp.id, 'x_phone': '0912 333 444',
                    'company_id': emp.company_id.id})          # a draft

        page = self.url_open('/my/requests', timeout=60)
        self.assertEqual(page.status_code, 200)
        text = page.text
        strip = re.search(r'class="pbme-rq-strip".*?</p>', text, re.S).group(0)
        nums = [int(n) for n in re.findall(r'<b>(\d+)</b>', strip)]
        self.assertEqual(nums, [0, 1, 1], 'waiting on you / with someone / done')
        self.assertEqual(self._rows(text), 2)
        self.assertIn('pbme-rq-month-h', text)
        self.assertIn('Profile change', text)
        self.assertIn('/my/profile/request/%s' % waiting.id, text)

        wait = self.url_open('/my/requests?filter=wait', timeout=60)
        self.assertEqual(self._rows(wait.text), 1)
        self.assertIn('/my/profile/request/%s' % waiting.id, wait.text)
        act = self.url_open('/my/requests?filter=act', timeout=60)
        self.assertEqual(act.status_code, 200)
        self.assertEqual(self._rows(act.text), 0)
        self.assertIn('Nothing is waiting on you', act.text)
        odd = self.url_open('/my/requests?filter=x&page=abc', timeout=60)
        self.assertEqual(odd.status_code, 200)
        self.assertEqual(self._rows(odd.text), 2)

    # T3.7
    def test_t3_7_my_requests_for_an_employee_login(self):
        self._walk(self.share.login, PASSWORD, self.share_emp)

    def test_t3_7b_my_requests_for_a_full_account(self):
        self._walk(self.plain.login, T1_PASSWORD, self.plain_emp)

    # T3.9 (page half)
    def test_t3_9b_home_shows_the_requests_tile_in_me(self):
        self.authenticate(self.share.login, PASSWORD)
        page = self.url_open('/my', timeout=60)
        self.assertEqual(page.status_code, 200)
        doc = lxml_html.fromstring(page.text)
        groups = doc.xpath("//div[contains(@class, 'o_portal_index_card')]"
                           "[.//a[@href='/my/requests']]/@data-pbme-group")
        self.assertEqual(groups, ['me'])
