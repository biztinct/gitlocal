# -*- coding: utf-8 -*-
"""FLEET P2A — what a customer's database says about the platform.

Three things a suite can reach and should: the state a page is built from, the
fact that it rides in with the session, and the fact that the route behind the
poll is not open to the world.
"""
import json
from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.pb_tenancy.models.tenancy import (
    P_NOTICE, P_PUSHED_AT, P_RELEASE, P_RELEASE_DATE, P_RELEASES, P_SLUG,
    live_notice,
)


def _notice(title="Planned update", ends=None, kind='maintenance', nid='n1'):
    return json.dumps({
        'id': nid, 'kind': kind, 'title': title,
        'text': "You may notice a short pause.",
        'starts_at': fields.Datetime.to_string(
            fields.Datetime.now() - timedelta(hours=1)),
        'ends_at': fields.Datetime.to_string(ends) if ends else '',
    })


@tagged('post_install', '-at_install')
class TestTenancyState(TransactionCase):
    """T1 — the payload every page is drawn from."""

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.svc = self.env['pb.tenancy']

    def _set(self, **kw):
        for key, val in kw.items():
            self.icp.set_param(key, val)

    # ---------------------------------------------------------------- notices
    def test_t1_01_an_expired_notice_is_not_returned(self):
        self._set(**{P_NOTICE: _notice(
            ends=fields.Datetime.now() - timedelta(minutes=1))})
        self.assertIsNone(self.svc.state()['notice'],
                          "A window that has closed must stop being on screen "
                          "whether or not anybody cleared it.")

    def test_t1_02_a_live_notice_is_returned_whole(self):
        self._set(**{P_NOTICE: _notice(
            ends=fields.Datetime.now() + timedelta(hours=3))})
        n = self.svc.state()['notice']
        self.assertEqual(n['title'], "Planned update")
        self.assertEqual(n['kind'], 'maintenance')
        self.assertEqual(n['id'], 'n1')

    def test_t1_03_a_notice_with_no_end_stands_until_cleared(self):
        self._set(**{P_NOTICE: _notice(ends=None, kind='info')})
        self.assertIsNotNone(self.svc.state()['notice'])

    def test_t1_04_damage_is_no_notice_rather_than_a_crash(self):
        for bad in ('{not json', '[]', '{}', '{"kind":"info"}', 'null'):
            self._set(**{P_NOTICE: bad})
            self.assertIsNone(self.svc.state()['notice'],
                              "A malformed message must never take a page down: %s" % bad)

    def test_t1_05_an_unknown_kind_is_read_as_information(self):
        raw = json.loads(_notice(ends=None))
        raw['kind'] = 'shouting'
        self._set(**{P_NOTICE: json.dumps(raw)})
        self.assertEqual(self.svc.state()['notice']['kind'], 'info')

    def test_t1_06_live_notice_is_pure(self):
        """The decision itself, reachable without a database (rail R6)."""
        now = fields.Datetime.now()
        past = json.dumps({'title': 'x', 'ends_at': fields.Datetime.to_string(
            now - timedelta(seconds=1))})
        future = json.dumps({'title': 'x', 'ends_at': fields.Datetime.to_string(
            now + timedelta(hours=1))})
        self.assertIsNone(live_notice(past, now=now))
        self.assertIsNotNone(live_notice(future, now=now))
        self.assertIsNone(live_notice(''))
        self.assertIsNone(live_notice(None))

    # ---------------------------------------------------------------- master
    def test_t1_07_no_subdomain_means_this_is_the_master(self):
        self.icp.set_param(P_SLUG, '')
        self.assertTrue(self.svc.state()['is_master'])

    def test_t1_08_a_subdomain_means_this_is_a_customer(self):
        self.icp.set_param(P_SLUG, 'abm')
        self.assertFalse(self.svc.state()['is_master'])

    # ---------------------------------------------------------------- release
    def test_t1_09_the_release_and_its_history_come_back(self):
        self._set(**{
            P_RELEASE: '2026.09.03',
            P_RELEASE_DATE: '2026-09-03',
            P_RELEASES: json.dumps([
                {'name': '2026.09.03', 'date': '2026-09-03', 'notes': 'First.'},
            ]),
            P_PUSHED_AT: '2026-09-03 12:00:00',
        })
        s = self.svc.state()
        self.assertEqual(s['release'], '2026.09.03')
        self.assertEqual(s['release_date'], '2026-09-03')
        self.assertEqual(len(s['releases']), 1)
        self.assertEqual(s['releases'][0]['notes'], 'First.')
        self.assertEqual(s['pushed_at'], '2026-09-03 12:00:00')

    def test_t1_10_a_database_nobody_has_pushed_to_answers_empty(self):
        for key in (P_RELEASE, P_RELEASE_DATE, P_RELEASES, P_NOTICE, P_PUSHED_AT):
            self.icp.set_param(key, '')
        s = self.svc.state()
        self.assertEqual(s['release'], '')
        self.assertEqual(s['releases'], [])
        self.assertIsNone(s['notice'])

    def test_t1_11_a_damaged_release_list_is_an_empty_list(self):
        self._set(**{P_RELEASES: 'not json at all'})
        self.assertEqual(self.svc.state()['releases'], [])


@tagged('post_install', '-at_install')
class TestTenancyRequestSeams(HttpCase):
    """T2/T3 — it rides in with the page, and the route is behind the door."""

    #: A login of our own. The administrator's password on a live database is
    #: not `admin`, and a suite that assumes it is fails on the only databases
    #: that matter.
    LOGIN = 'pb_tenancy_probe'
    PASSWORD = 'pbTenancyProbe!2026'

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(
            P_RELEASE, '2026.09.03-test')
        self.probe = self.env['res.users'].sudo().create({
            'name': "Platform link probe",
            'login': self.LOGIN,
            'password': self.PASSWORD,
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.env.cr.flush()

    def _json(self, url, payload=None):
        return self.url_open(url, data=json.dumps({
            'jsonrpc': '2.0', 'method': 'call', 'params': payload or {},
        }), headers={'Content-Type': 'application/json'})

    def _body(self, res):
        """The JSON, or a failure that says what actually came back."""
        try:
            return res.json()
        except ValueError:
            self.fail("%s answered %s (%s): %s"
                      % (res.url, res.status_code,
                         res.headers.get('Content-Type'), res.text[:400]))

    def test_t2_01_session_info_carries_the_platform_state(self):
        self.authenticate(self.LOGIN, self.PASSWORD)
        res = self._json('/web/session/get_session_info')
        body = self._body(res)
        self.assertIn('result', body, "the session route answered: %s" % body)
        self.assertIn('pb_tenancy', body['result'],
                      "The banner must render on the first paint, which means "
                      "the state travels with the session.")
        self.assertEqual(body['result']['pb_tenancy']['release'],
                         '2026.09.03-test')

    def test_t3_01_the_poll_route_answers_a_logged_in_user(self):
        self.authenticate(self.LOGIN, self.PASSWORD)
        body = self._body(self._json('/pb_tenancy/state'))
        self.assertIn('result', body, "the poll route answered: %s" % body)
        self.assertEqual(body['result']['release'], '2026.09.03-test')

    def test_t3_02_the_poll_route_refuses_a_stranger(self):
        """Nobody logged in gets a refusal, not the platform state.

        NOTE FOR ANYONE RUNNING THIS. These three need `--db-filter=.*` on the
        command line. The live configuration picks the database out of the
        HOSTNAME (`dbfilter = ^%d$`), and a test client calls itself on
        `127.0.0.1`, which resolves to a database called `127` — so every route
        answers 404 and the failure looks like a broken controller.
        """
        self.authenticate(None, None)
        res = self._json('/pb_tenancy/state')
        self.assertNotIn('2026.09.03-test', res.text,
                         "An anonymous caller must not be told anything about "
                         "this customer's platform state.")
        body = self._body(res)
        self.assertNotIn('result', body)
        self.assertIn('error', body)
