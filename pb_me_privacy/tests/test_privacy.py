# -*- coding: utf-8 -*-
"""WDGAP S6-A item 3 — consent for personal data (owner ruling E3).

P-numbers match the phase report. The door is walked over HTTP as a real
PORTAL login: nothing is asked while no notice is published; once one is,
the first My Payobook page (a deep link included) shows it; both answers
continue to the page asked for; the same version never asks twice; a new
version asks again.
"""
import re
from urllib.parse import unquote

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged


def _fixture(cls, login):
    cls.company = cls.env.company
    Users = cls.env['res.users'].with_context(no_reset_password=True)
    common = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
    cls.portal = Users.create(dict(common, name='S6A Privacy Portal', login=login,
                                   password=login,
                                   group_ids=[(6, 0, [cls.env.ref('base.group_portal').id])]))
    cls.hr = Users.create(dict(common, name='S6A Privacy HR', login=login + '_hr',
                               group_ids=[(6, 0, [cls.env.ref('hr.group_hr_user').id])]))
    cls.manager = Users.create(dict(common, name='S6A Privacy Manager',
                                    login=login + '_mgr',
                                    group_ids=[(6, 0, [cls.env.ref('base.group_user').id])]))
    Emp = cls.env['hr.employee']
    cls.boss = Emp.create({'name': 'S6A Boss', 'company_id': cls.company.id,
                           'user_id': cls.manager.id})
    cls.emp = Emp.create({'name': 'S6A Privacy Person', 'company_id': cls.company.id,
                          'user_id': cls.portal.id, 'parent_id': cls.boss.id})
    cls.nologin = Emp.create({'name': 'S6A No Login', 'company_id': cls.company.id})
    cls.Notice = cls.env['pb.privacy.notice']
    cls.Consent = cls.env['pb.privacy.consent']
    # Silent install: no notice may exist for this company before the test.
    cls.Notice.sudo().search([('company_id', '=', cls.company.id),
                              ('state', '=', 'published')]).with_context(
        pb_privacy_sys=True).write({'state': 'replaced'})


@tagged('post_install', '-at_install')
class TestS6aPrivacy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _fixture(cls, 's6a_priv_tc')

    def _publish(self, body='<p>Our notice v1</p>'):
        notice = self.Notice.with_user(self.hr).create({
            'company_id': self.company.id, 'body': body})
        notice.with_user(self.hr).action_publish()
        return notice

    # P1 — silent: nothing published, nobody asked
    def test_p1_silent_install(self):
        self.assertEqual(self.Consent._pb_pending(self.portal), (None, None))
        board = self.env['pb.privacy.board'].with_user(self.hr).get_board()
        self.assertIsNone(board['notice'])
        self.assertEqual(sum(board['counts'].values()), 0)

    # P2 — publish: versioned, words locked, the person is asked
    def test_p2_publish_versions_and_locks(self):
        notice = self._publish()
        self.assertEqual(notice.state, 'published')
        self.assertEqual(notice.version, 1)
        with self.assertRaises(UserError):
            notice.with_user(self.hr).write({'body': '<p>changed</p>'})
        pending, emp = self.Consent._pb_pending(self.portal)
        self.assertEqual(pending, notice)
        self.assertEqual(emp, self.emp)
        with self.assertRaises(AccessError):
            self.Notice.with_user(self.manager).create({'company_id': self.company.id})

    # P3 — an answer is kept with the exact words, per employee
    def test_p3_answer_recorded_with_wording(self):
        notice = self._publish('<p>Exact words here</p>')
        rows = self.Consent.with_user(self.portal)._pb_record_screen(
            self.portal, notice, 'agree', lang='en_US')
        self.assertEqual(rows.employee_id, self.emp)
        self.assertIn('Exact words here', rows.wording)
        self.assertEqual(rows.version, 1)
        self.assertEqual(rows.user_id, self.portal)
        self.assertEqual(rows.how, 'screen')
        self.assertEqual(self.Consent._pb_pending(self.portal), (None, None))
        with self.assertRaises(UserError):
            rows.with_user(self.hr).write({'answer': 'disagree'})
        with self.assertRaises(AccessError):
            self.Consent.with_user(self.hr).create({
                'employee_id': self.emp.id, 'company_id': self.company.id,
                'notice_id': notice.id, 'answer': 'agree'})

    # P4 — a new version asks again; the old answer is kept
    def test_p4_new_version_asks_again(self):
        notice = self._publish()
        self.Consent._pb_record_screen(self.portal, notice, 'agree')
        draft_action = notice.with_user(self.hr).action_new_version()
        v2 = self.Notice.browse(draft_action['res_id'])
        v2.with_user(self.hr).write({'body': '<p>Version two</p>'})
        v2.with_user(self.hr).action_publish()
        self.assertEqual(v2.version, 2)
        self.assertEqual(notice.state, 'replaced')
        pending, _emp = self.Consent._pb_pending(self.portal)
        self.assertEqual(pending, v2)
        self.assertEqual(self.Consent.search_count(
            [('employee_id', '=', self.emp.id), ('notice_id', '=', notice.id)]), 1)

    # P5 — HR's board: four places, paper consent with who and when
    def test_p5_board_and_paper_consent(self):
        notice = self._publish()
        self.Consent._pb_record_screen(self.portal, notice, 'disagree')
        Board = self.env['pb.privacy.board']
        data = Board.with_user(self.hr).get_board(company_id=self.company.id)
        st = {r['employee_id']: r['status'] for r in data['rows']}
        self.assertEqual(st[self.emp.id], 'declined')
        self.assertEqual(st[self.nologin.id], 'not_yet')
        self.assertEqual(sum(data['counts'].values()), data['total'])
        Board.with_user(self.hr).record_paper(self.nologin.id, 'agree')
        data = Board.with_user(self.hr).get_board(company_id=self.company.id,
                                                  status='paper')
        row = [r for r in data['rows'] if r['employee_id'] == self.nologin.id][0]
        self.assertEqual(row['status'], 'paper')
        self.assertEqual(row['by'], self.hr.name)
        self.assertTrue(row['when'])

    # P6 — managers and the employee's own manager see nothing
    def test_p6_managers_see_nothing(self):
        notice = self._publish()
        self.Consent._pb_record_screen(self.portal, notice, 'agree')
        self.assertFalse(self.env['pb.privacy.board'].with_user(
            self.manager).get_board()['allowed'])
        with self.assertRaises(AccessError):
            self.Consent.with_user(self.manager).search([])
        with self.assertRaises(AccessError):
            self.Consent.with_user(self.portal).search([])
        with self.assertRaises(AccessError):
            self.env['pb.privacy.board'].with_user(self.manager).record_paper(
                self.nologin.id)

    # P7 — an employee in two companies answers each company's notice
    def test_p7_two_companies(self):
        other = self.env['res.company'].create({'name': 'S6A Second Co'})
        self.portal.sudo().company_ids = [(4, other.id)]
        emp2 = self.env['hr.employee'].sudo().create({
            'name': 'S6A Privacy Person', 'company_id': other.id,
            'user_id': self.portal.id})
        n1 = self._publish()
        self.hr.sudo().company_ids = [(4, other.id)]
        n2 = self.Notice.with_user(self.hr).with_context(
            allowed_company_ids=[other.id]).create({'company_id': other.id})
        n2.with_user(self.hr).with_context(allowed_company_ids=[other.id]).action_publish()
        self.Consent._pb_record_screen(self.portal, n1, 'agree')
        pending, emp = self.Consent._pb_pending(self.portal)
        self.assertEqual(pending, n2)
        self.assertEqual(emp, emp2)


@tagged('post_install', '-at_install')
class TestS6aPrivacyDoor(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _fixture(cls, 's6a_priv_http')

    def _publish(self, body='<p>Door notice words</p>'):
        notice = self.Notice.with_user(self.hr).create({
            'company_id': self.company.id, 'body': body})
        notice.with_user(self.hr).action_publish()
        return notice

    def _answer(self, page, answer):
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        notice_id = re.search(r'name="notice_id" value="(\d+)"', page.text).group(1)
        nxt = re.search(r'name="next" value="([^"]*)"', page.text).group(1)
        return self.url_open('/my/privacy/answer', data={
            'csrf_token': token, 'notice_id': notice_id, 'answer': answer,
            'next': nxt.replace('&amp;', '&')}, allow_redirects=False)

    # P8 — no notice: /my opens straight away
    def test_p8_no_notice_no_door(self):
        self.authenticate('s6a_priv_http', 's6a_priv_http')
        res = self.url_open('/my', allow_redirects=False)
        self.assertEqual(res.status_code, 200)

    # P9 — the door on a deep link; "I do not agree" still continues
    def test_p9_door_on_deep_link_and_disagree_continues(self):
        self._publish()
        self.authenticate('s6a_priv_http', 's6a_priv_http')
        res = self.url_open('/my/payslips', allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertIn('/my/privacy/notice', res.headers['Location'])
        self.assertIn('/my/payslips', unquote(res.headers['Location']))
        door = self.url_open(res.headers['Location'])
        self.assertEqual(door.status_code, 200)
        self.assertIn('Door notice words', door.text)
        self.assertIn('I do not agree', door.text)
        done = self._answer(door, 'disagree')
        self.assertIn(done.status_code, (302, 303))
        self.assertIn('/my/payslips', done.headers['Location'])
        row = self.Consent.sudo().search([('employee_id', '=', self.emp.id)])
        self.assertEqual(row.answer, 'disagree')
        # answered: the next page opens without the door
        res = self.url_open('/my', allow_redirects=False)
        self.assertEqual(res.status_code, 200)

    # P10 — agree once: never asked again for the same version
    def test_p10_agree_once_then_new_version(self):
        notice = self._publish()
        self.authenticate('s6a_priv_http', 's6a_priv_http')
        door = self.url_open('/my')
        self.assertIn('I have read and agree', door.text)
        self._answer(door, 'agree')
        self.assertEqual(self.url_open('/my', allow_redirects=False).status_code, 200)
        self.assertEqual(self.url_open('/my/privacy').status_code, 200)
        v2 = self.Notice.browse(notice.with_user(self.hr).action_new_version()['res_id'])
        v2.with_user(self.hr).action_publish()
        res = self.url_open('/my', allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertIn('/my/privacy/notice', res.headers['Location'])

    # P11 — the door can never be pointed off the site
    def test_p11_next_stays_on_my_payobook(self):
        self._publish()
        self.authenticate('s6a_priv_http', 's6a_priv_http')
        door = self.url_open('/my/privacy/notice?next=https://evil.example/x')
        self.assertIn('name="next" value="/my"', door.text)
