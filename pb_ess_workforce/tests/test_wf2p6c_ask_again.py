# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P6c (D36) — My Leave: "Sent back" and "Ask again".

For an internal login (ESS Alpha) and an EMPLOYEE login (portal tier):

* a request the approver sent back shows "Sent back" (en / vi / id), the
  reason, and "Ask again"; a refused one keeps "Refused" and no button;
* "Ask again" fills the existing request form from the old request (kind,
  days, part of the day, note) — the facade's prefill;
* sending it makes a NEW request, waiting for approval, linked both ways;
  the old one's button disappears; a second "ask again" is refused;
* every normal rule runs on the new request (here: the balance — a request
  over it is refused and nothing is linked);
* someone else's request cannot be asked again.

Plus one HTTP pass for the employee login: the page, the prefilled form and
the plain POST (no script).

Run alone: ``--test-tags /pb_ess_workforce:TestWf2p6cAskAgain``.
"""

import re
import secrets
from datetime import date, timedelta

from odoo import http
from odoo.exceptions import UserError
from odoo.tests import HttpCase
from odoo.tests.common import tagged
from odoo.tools import config

from .common import EssWorkforceCase


def _raises(case, exc, fn, *args, **kw):
    """assertRaises for one class at a time (ledger G75), in a savepoint."""
    try:
        with case.env.cr.savepoint():
            fn(*args, **kw)
    except exc as error:
        return error
    case.fail('%s was not raised' % exc.__name__)


class _SentBackFixture:

    @classmethod
    def _fixture(cls):
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.boss_user = Users.create({
            'name': 'P6c Boss', 'login': 'p6c.boss@example.invalid',
            'email': 'p6c.boss@example.invalid',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.boss = cls.env['hr.employee'].create({
            'name': 'P6c Boss', 'user_id': cls.boss_user.id,
            'company_id': cls.company.id})
        # the company runs time off through the approval engine
        cls.env['hr.leave']._approval_seed_default(cls.company)
        Type = cls.env['hr.leave.type']
        cls.t_half = Type.create({
            'name': 'P6c Half days', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'request_unit': 'half_day',
            'company_id': cls.company.id})
        cls.t_counted = Type.create({
            'name': 'P6c Counted', 'requires_allocation': True,
            'leave_validation_type': 'manager', 'request_unit': 'day',
            'allocation_validation_type': 'hr', 'company_id': cls.company.id})
        anchor = date.today() + timedelta(days=21)
        cls.mon = anchor - timedelta(days=anchor.weekday())

    @classmethod
    def _grant(cls, emp, days=2):
        alloc = cls.env['hr.leave.allocation'].sudo().create({
            'name': 'P6c grant', 'employee_id': emp.id,
            'holiday_status_id': cls.t_counted.id, 'number_of_days': days,
            'allocation_type': 'regular',
            'date_from': date.today() - timedelta(days=30)})
        alloc.action_approve()

    def _decide(self, leave, action, reason):
        leave = leave.sudo()
        request = leave.approval_request_id
        self.assertTrue(request, 'the request went to the route')
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.boss_user).decide(
            request.id, step.key, action, reason=reason)
        self.env.invalidate_all()
        return leave


@tagged('post_install', '-at_install', 'wf2p6c')
class TestWf2p6cAskAgain(_SentBackFixture, EssWorkforceCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.emp_a.write({'parent_id': cls.boss.id,
                         'leave_manager_id': cls.boss_user.id})
        cls.emp_b.write({'parent_id': cls.boss.id,
                         'leave_manager_id': cls.boss_user.id})
        cls.user_p = Users.create({
            'name': 'P6c Portal', 'login': 'p6c.portal@example.invalid',
            'email': 'p6c.portal@example.invalid', 'tz': cls.tz,
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.emp_p = cls.env['hr.employee'].create({
            'name': 'P6c Portal', 'user_id': cls.user_p.id,
            'company_id': cls.company.id, 'tz': cls.tz,
            'parent_id': cls.boss.id, 'leave_manager_id': cls.boss_user.id})
        for emp in (cls.emp_a, cls.emp_p):
            cls._grant(emp, 2)

    def _apply(self, user, lt, start, end=None, **kw):
        res = self._as(user).apply_leave(
            lt.id, start.isoformat(), (end or start).isoformat(),
            kw.pop('note', 'P6c note'), **kw)
        return self.env['hr.leave'].sudo().browse(res['id'])

    def _rows(self, user, lang=None):
        Ess = self._as(user)
        if lang:
            Ess = Ess.with_context(lang=lang)
        return {r['id']: r for r in Ess.get_my_leave()['requests']}

    def test_01_sent_back_row_labels(self):
        for n, user in enumerate((self.user_a, self.user_p)):
            day = self.mon + timedelta(days=n)
            back = self._decide(self._apply(user, self.t_half, day,
                                            period_from='am'),
                                'return', 'P6c: the afternoon instead')
            turned = self._decide(self._apply(
                user, self.t_half, day + timedelta(days=7)), 'reject', 'P6c no')
            self.assertEqual(back.state, 'refuse')
            rows = self._rows(user)
            row = rows[back.id]
            self.assertEqual(row['state_label'], 'Sent back')
            self.assertEqual(row['badge'], 'sent_back')
            self.assertEqual(row['reason'], 'P6c: the afternoon instead')
            self.assertTrue(row['can_ask_again'])
            self.assertEqual(row['again_url'],
                             '/my/work/leave?again=%s#pbew-ask' % back.id)
            self.assertFalse(row['can_withdraw'] or row['can_cancel'])
            row = rows[turned.id]
            self.assertEqual(row['state_label'], 'Refused')
            self.assertFalse(row['can_ask_again'])
            self.assertEqual(self._rows(user, 'vi_VN')[back.id]['state_label'],
                             'Đã bị trả lại')
            self.assertEqual(self._rows(user, 'id_ID')[back.id]['state_label'],
                             'Dikembalikan')

    def test_02_prefill_from_the_old_request(self):
        back = self._decide(self._apply(self.user_p, self.t_half, self.mon,
                                        period_from='pm', note='Dentist'),
                            'return', 'P6c: morning please')
        data = self._as(self.user_p).get_my_leave(again=back.id)
        form = data['again']
        self.assertFalse(data['again_error'])
        self.assertEqual(form['id'], back.id)
        self.assertEqual(form['type_id'], self.t_half.id)
        self.assertEqual(form['date_from'], self.mon.isoformat())
        self.assertEqual(form['date_to'], self.mon.isoformat())
        self.assertEqual(form['period_from'], 'pm')
        self.assertEqual(form['note'], 'Dentist')
        self.assertEqual(form['reason'], 'P6c: morning please')
        # someone else's request: nothing to fill in, a plain sentence
        data = self._as(self.user_b).get_my_leave(again=back.id)
        self.assertFalse(data['again'])
        self.assertEqual(data['again_error'], 'We could not find that request.')
        # a request that was refused, not sent back
        turned = self._decide(self._apply(
            self.user_p, self.t_half, self.mon + timedelta(days=1)),
            'reject', 'P6c no')
        data = self._as(self.user_p).get_my_leave(again=turned.id)
        self.assertFalse(data['again'])
        self.assertIn('Only a request that was sent back', data['again_error'])

    def test_03_ask_again_new_request_linked_once(self):
        for n, user in enumerate((self.user_a, self.user_p)):
            day = self.mon + timedelta(days=14 + n)
            back = self._decide(self._apply(user, self.t_half, day,
                                            period_from='pm'),
                                'return', 'P6c: morning please')
            new = self._apply(user, self.t_half, day, period_from='am',
                              note='P6c again', again_of=back.id)
            self.assertEqual(new.state, 'confirm')
            self.assertTrue(new.approval_request_id, 'it went to the route')
            self.assertEqual(new.request_date_from_period, 'am')
            self.assertEqual(new.pb_again_of_id, back)
            rows = self._rows(user)
            self.assertEqual(rows[new.id]['state_label'], 'Waiting approval')
            self.assertEqual(rows[new.id]['again_of']['id'], back.id)
            self.assertTrue(rows[new.id]['again_of']['label'].startswith(
                'Asked again after the request for'))
            self.assertFalse(rows[back.id]['can_ask_again'],
                             'the old one loses its button')
            self.assertEqual(rows[back.id]['again_as']['id'], new.id)
            self.assertTrue(rows[back.id]['again_as']['label'].startswith(
                'Asked again on'))
            self.assertTrue(self._rows(user, 'vi_VN')[back.id]['again_as']
                            ['label'].startswith('Đã gửi lại vào'))
            self.assertTrue(self._rows(user, 'id_ID')[back.id]['again_as']
                            ['label'].startswith('Diajukan lagi pada'))
            error = _raises(self, UserError, self._apply, user, self.t_half,
                            day + timedelta(days=1), again_of=back.id)
            self.assertIn('already asked again', str(error))

    def test_04_ask_again_runs_the_normal_rules(self):
        """2 days granted; asked again for 5 → the balance rule refuses it."""
        for user in (self.user_a, self.user_p):
            back = self._decide(self._apply(user, self.t_counted, self.mon),
                                'return', 'P6c: shorter')
            before = self.env['hr.leave'].sudo().search_count([])
            error = _raises(self, Exception, self._apply, user,
                            self.t_counted, self.mon,
                            self.mon + timedelta(days=4), again_of=back.id)
            self.assertNotIsInstance(error, AssertionError)
            self.assertEqual(self.env['hr.leave'].sudo().search_count([]),
                             before, 'nothing was created')
            back.invalidate_recordset()
            self.assertTrue(back._pb_can_ask_again(), 'nothing was linked')
            # a fitting one goes through
            new = self._apply(user, self.t_counted, self.mon,
                              again_of=back.id)
            self.assertEqual(new.pb_again_of_id, back)

    def test_05_someone_elses_request(self):
        back = self._decide(self._apply(self.user_a, self.t_half,
                                        self.mon + timedelta(days=3)),
                            'return', 'P6c: x')
        error = _raises(self, UserError, self._apply, self.user_p,
                        self.t_half, self.mon + timedelta(days=3),
                        again_of=back.id)
        self.assertIn('We could not find that request', str(error))
        self.assertTrue(back._pb_can_ask_again())


@tagged('post_install', '-at_install', 'wf2p6c')
class TestWf2p6cAskAgainHttp(_SentBackFixture, HttpCase):
    """The employee login (portal tier), through the real pages."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        previous = config['dbfilter']
        config['dbfilter'] = '^%s$' % re.escape(cls.env.cr.dbname)
        cls.addClassCleanup(config.__setitem__, 'dbfilter', previous)
        cls._fixture()
        cls.password = secrets.token_urlsafe(18)
        cls.user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'P6c Http', 'login': 'p6c_http_portal',
                'password': cls.password,
                'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.emp = cls.env['hr.employee'].create({
            'name': 'P6c Http', 'user_id': cls.user.id,
            'company_id': cls.company.id, 'parent_id': cls.boss.id,
            'leave_manager_id': cls.boss_user.id})

    def _post(self, url, data=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, timeout=60)

    def test_http_page_ask_again(self):
        back = self.env['pb.ess.workforce'].with_user(self.user).apply_leave(
            self.t_half.id, self.mon.isoformat(), self.mon.isoformat(),
            'Dentist', period_from='pm')
        back = self._decide(self.env['hr.leave'].browse(back['id']),
                            'return', 'P6c: morning please')
        self.authenticate(self.user.login, self.password)
        page = self.url_open('/my/work/leave', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('pbme-badge--sent_back', page.text)
        self.assertIn('P6c: morning please', page.text)
        self.assertIn('/my/work/leave?again=%s#pbew-ask' % back.id, page.text)
        self.assertIn('pbew-lv-%s' % back.id, page.text)
        # WF2 P6d: the employee home's "Needs you" reminder leads to Ask again
        home = self.url_open('/my', timeout=60)
        self.assertEqual(home.status_code, 200)
        self.assertIn('1 time off request sent back — ask again', home.text)
        self.assertIn('/my/work/leave?again=%s#pbew-ask' % back.id, home.text)

        form = self.url_open('/my/work/leave?again=%s' % back.id, timeout=60)
        self.assertEqual(form.status_code, 200)
        self.assertIn('name="again_of" value="%s"' % back.id, form.text)
        self.assertIn('Filled in from your request that was sent back',
                      form.text)
        self.assertIn('Documents are not copied', form.text)
        self.assertIn('value="%s"' % self.mon.isoformat(), form.text)
        self.assertIn('value="Dentist"', form.text)
        self.assertRegex(form.text, r'<option value="pm"[^>]*selected')
        self.assertNotIn(' style="', form.text.split('pbew-lvform')[1][:20000],
                         'portal CSP: no inline styles (ledger G95)')

        # the plain POST, as with scripts off
        resp = self._post('/my/work/leave/apply', {
            'type_id': self.t_half.id, 'date_from': self.mon.isoformat(),
            'date_to': self.mon.isoformat(), 'period_from': 'am',
            'period_to': 'full', 'note': 'Dentist', 'again_of': back.id})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('done=leave_again', resp.url)
        self.assertIn('Asked again. Your new request is waiting for approval.',
                      resp.text)
        new = self.env['hr.leave'].sudo().search(
            [('pb_again_of_id', '=', back.id)])
        self.assertEqual(len(new), 1)
        self.assertEqual(new.state, 'confirm')
        self.assertEqual(new.employee_id, self.emp)
        self.assertNotIn('/my/work/leave?again=%s' % back.id, resp.text,
                         'the old one no longer offers "Ask again"')
        home = self.url_open('/my', timeout=60)
        self.assertEqual(home.status_code, 200)
        self.assertNotIn('time off request sent back', home.text,
                         'asked again: the home reminder is gone (P6d)')
