# -*- coding: utf-8 -*-
"""WDGAP S9-B — /my/letters as REAL portal users, over HTTP."""

import re

from odoo.tests import HttpCase, tagged

from .common import make_fixture


@tagged('post_install', '-at_install', 'pb_conduct')
class TestConductPortalHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_fixture(cls)

    def _page(self, url):
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200, url)
        return res.text

    def _post(self, url, data):
        data = dict(data, csrf_token=self.csrf_token())
        return self.url_open(url, data=data, allow_redirects=False)

    def csrf_token(self):
        """The session's token, read from the page as a browser would."""
        html = self.url_open('/my/letters').text
        m = (re.search(r'name="csrf_token" value="([^"]+)"', html)
             or re.search(r'csrf_token["\']?\s*[:=]\s*["\']([^"\']+)', html))
        return m.group(1) if m else ''

    def test_50_employee_page_shows_own_finished_letters_only(self):
        self.authenticate('s9b_subject', 's9b_subject')
        html = self._page('/my/letters')
        self.assertIn(self.decision.title, html)
        self.assertIn(self.invite.title, html)
        for secret in ('SECRET-DRAFT-TITLE', 'SECRET-SUMMARY', 'SECRET-NOTE',
                       'SECRET-MINUTES', 'SECRET-FILE', 'Shift lead'):
            self.assertNotIn(secret, html)
        self.assertNotIn('Odoo', html.split('<body', 1)[-1].replace('odoo', ''))
        # the home renders, with the entry and the needs-you row
        home = self._page('/my')
        self.assertIn('/my/letters', home)

    def test_51_employee_reads_replies_and_downloads(self):
        self.authenticate('s9b_subject', 's9b_subject')
        res = self._post('/my/letters/%s/read' % self.invite.id, {})
        self.assertIn(res.status_code, (302, 303))
        res = self._post('/my/letters/%s/reply' % self.decision.id,
                         {'reply': 'DEMO reply from Sam'})
        self.assertIn('done=reply', res.headers.get('Location', ''))
        self.env.invalidate_all()
        self.assertEqual(self.decision.reply, 'DEMO reply from Sam')
        self.assertTrue(self.invite.read_on)
        pdf = self.url_open('/my/letters/%s/pdf' % self.decision.id)
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content)

    def test_52_another_employee_cannot_reach_it(self):
        self.authenticate('s9b_other', 's9b_other')
        html = self._page('/my/letters')
        self.assertNotIn(self.decision.title, html)
        self.assertEqual(self.url_open('/my/letters/%s/pdf' % self.decision.id).status_code, 404)
        res = self._post('/my/letters/%s/reply' % self.decision.id, {'reply': 'HIJACK'})
        self.assertIn('error=reply', res.headers.get('Location', ''))
        self._post('/my/letters/%s/read' % self.decision.id, {})
        self.env.invalidate_all()
        self.assertFalse(self.decision.reply)
        self.assertFalse(self.decision.read_on)
        # a draft letter of the subject is never served, not even by id
        self.authenticate('s9b_subject', 's9b_subject')
        self.assertEqual(self.url_open('/my/letters/%s/pdf' % self.draft.id).status_code, 404)

    def test_54_a_decision_waiting_for_the_second_sign_off_is_never_served(self):
        """W3-A (CD1), as the real portal employee: while the second sign-off
        is outstanding the letter is not on the page and its PDF is 404; once
        the second named person confirms, it is."""
        cid = self.F.create_case({'employee_id': self.e_subject.id, 'reason_id': self.reason.id,
                                  'summary': 'W3A-SECRET-SUMMARY'})['id']
        self.F.move(cid, 'skip_hearing', {'why': 'x'})
        self.F.move(cid, 'decide', {'outcome': 'final',
                                    'summary': 'W3A-SECRET-DECISION final warning'})
        self.F.move(cid, 'ask_signoff')
        letter = self.env['pb.conduct.case'].browse(cid).letter_ids
        self.authenticate('s9b_subject', 's9b_subject')
        html = self._page('/my/letters')
        for secret in ('W3A-SECRET', letter.title):
            self.assertNotIn(secret, html)
        self.assertEqual(self.url_open('/my/letters/%s/pdf' % letter.id).status_code, 404)
        res = self._post('/my/letters/%s/reply' % letter.id, {'reply': 'early'})
        self.assertIn('error=reply', res.headers.get('Location', ''))
        # the second named person confirms: now it is there
        self.F2.move(cid, 'confirm_signoff')
        html = self._page('/my/letters')
        self.assertIn('W3A-SECRET-DECISION', html)
        self.assertNotIn('W3A-SECRET-SUMMARY', html)

    def test_53_unnamed_hr_board_call_is_refused_over_rpc(self):
        self.authenticate('s9b_hr', 's9b_hr')
        res = self.make_jsonrpc_request('/web/dataset/call_kw/pb.conduct/get_board', {
            'model': 'pb.conduct', 'method': 'get_board', 'args': [], 'kwargs': {}})
        self.assertFalse(res['allowed'])
        self.assertEqual(set(res), {'allowed', 'why'})
