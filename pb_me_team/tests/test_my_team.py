# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""MYTEAM — the manager's area on the employee home.

MT1 the team is the direct reports, nobody else; MT2 today's board reads
leave; MT3 the calendar flags a busy day; MT4 an employee-only login sees no
approvals and no error; MT5 the home card and rows only for a manager; MT6
the pages over HTTP for a manager, and the "nobody reports to you" page for
somebody else.
"""
from datetime import date, timedelta

from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import (
    _make_share, _pin_dbfilter,
)

PASSWORD = 'myteam-probe-2026-11'


def _staff(env, login, name, password=None):
    vals = {'name': name, 'login': login,
            'group_ids': [(6, 0, [env.ref('base.group_user').id])]}
    if password:
        vals['password'] = password
    user = env['res.users'].with_context(no_reset_password=True).create(vals)
    emp = env['hr.employee'].create({
        'name': name, 'user_id': user.id, 'company_id': env.company.id})
    return user, emp


def _leave_type(env):
    return env['hr.leave.type'].create({
        'name': 'MT Probe Leave', 'requires_allocation': False,
        'company_id': env.company.id})


def _leave(env, emp, lt, start, end, state='validate'):
    leave = env['hr.leave'].with_context(
        leave_skip_state_check=True, mail_create_nolog=True,
        tracking_disable=True).sudo().create({
            'employee_id': emp.id, 'holiday_status_id': lt.id,
            'request_date_from': start, 'request_date_to': end})
    leave.sudo().write({'state': state})
    return leave


@tagged('post_install', '-at_install')
class TestMyTeamFacts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.boss, cls.boss_emp = _staff(cls.env, 'test_mt_boss', 'MT Boss')
        cls.a = cls.env['hr.employee'].create(
            {'name': 'MT Ana', 'parent_id': cls.boss_emp.id})
        cls.b = cls.env['hr.employee'].create(
            {'name': 'MT Bao', 'parent_id': cls.boss_emp.id})
        cls.c = cls.env['hr.employee'].create(
            {'name': 'MT Chi', 'parent_id': cls.a.id})
        cls.lt = _leave_type(cls.env)
        cls.Team = cls.env['pb.me.team'].with_user(cls.boss)

    def test_mt1_team_is_direct_reports(self):
        self.assertEqual(set(self.Team.team(self.boss_emp).ids),
                         {self.a.id, self.b.id})
        self.assertTrue(self.Team.is_manager(self.boss_emp))
        self.assertFalse(self.Team.team(self.b))

    def test_mt2_today_reads_leave(self):
        today = self.Team._local_now(self.boss_emp).date()
        _leave(self.env, self.a, self.lt, today, today + timedelta(days=2))
        rows = {r['id']: r for r in self.Team.today(self.boss_emp)['rows']}
        self.assertEqual(rows[self.a.id]['status'], 'leave')
        self.assertEqual(rows[self.a.id]['leave_type'], 'MT Probe Leave')
        self.assertNotEqual(rows[self.b.id]['status'], 'leave')

    def test_mt3_calendar_flags_a_busy_day(self):
        day = self.Team._local_now(self.boss_emp).date() + timedelta(days=3)
        _leave(self.env, self.a, self.lt, day, day)
        _leave(self.env, self.b, self.lt, day, day, state='confirm')
        cal = self.Team.calendar(self.boss_emp)
        self.assertEqual(len(cal['days']), 28)
        self.assertIn(day, [c['date'] for c in cal['clashes']])
        cells = {r['id']: r['cells'][3] for r in cal['rows']}
        self.assertEqual(cells, {self.a.id: 'away', self.b.id: 'asked'})

    def test_mt4_employee_login_sees_no_approvals(self):
        share, share_emp = _make_share(self.env, 'test_mt_share', 'MT Share')
        Team = self.env['pb.me.team'].with_user(share)
        self.assertEqual(Team.my_turn_count(), 0)
        ap = Team.approvals('mine')
        self.assertFalse(ap['can_read'])
        self.assertEqual(ap['cards'], [])
        self.assertIsNone(Team.approval(share_emp, 1))

    def test_mt5_home_card_only_for_a_manager(self):
        Home = self.env['pb.me.home'].with_user(self.boss)
        keys = [c['key'] for c in Home._pbme_extra_cards(self.boss_emp)]
        self.assertIn('my_team', keys)
        share, share_emp = _make_share(self.env, 'test_mt_share2', 'MT Share 2')
        Home = self.env['pb.me.home'].with_user(share)
        keys = [c['key'] for c in Home._pbme_extra_cards(share_emp)]
        self.assertNotIn('my_team', keys)

    def test_mt7_chart_counts_reports_of_reports(self):
        chart = self.Team.chart(self.boss_emp)
        counts = {r['id']: r['reports'] for r in chart['reports']}
        self.assertEqual(counts, {self.a.id: 1, self.b.id: 0})
        self.assertEqual(chart['me']['id'], self.boss_emp.id)

    def test_mt8_handover_is_mine_and_can_stop(self):
        cover, _emp = _staff(self.env, 'test_mt_cover', 'MT Cover')
        today = self.Team._local_now(self.boss_emp).date()
        hid = self.Team.set_handover(cover.id, today, today + timedelta(days=3),
                                     'Annual leave')
        rows = self.Team.handover(self.boss_emp)['rows']
        self.assertEqual([r['id'] for r in rows], [hid])
        self.assertTrue(rows[0]['live'])
        Del = self.env['biz.approval.delegation']
        self.assertEqual(Del.covering(self.boss, self.env.company), cover)
        # somebody else cannot stop it
        other = self.env['pb.me.team'].with_user(cover)
        with self.assertRaises(Exception):
            other.end_handover(hid)
        self.Team.end_handover(hid)
        self.assertFalse(self.Team.handover(self.boss_emp)['rows'])

    def test_mt8b_handover_refuses_a_bad_choice(self):
        from odoo.exceptions import UserError
        today = self.Team._local_now(self.boss_emp).date()
        with self.assertRaises(UserError):
            self.Team.set_handover(self.boss.id, today, today, '')
        share, _e = _make_share(self.env, 'test_mt_share3', 'MT Share 3')
        with self.assertRaises(UserError):
            self.Team.set_handover(share.id, today, today, '')

    def test_mt9_sections_do_not_fail(self):
        for name in ('overtime', 'gaps', 'balances', 'joiners', 'probation',
                     'moments'):
            getattr(self.Team, name)(self.boss_emp)

    def test_mt9b_joiner_is_listed(self):
        today = self.Team._local_now(self.boss_emp).date()
        if 'first_contract_date' not in self.b._fields:
            self.skipTest('no first contract date on this build')
        self.b.sudo().version_id.write({'contract_date_start': today - timedelta(days=10)})
        self.b.invalidate_recordset()
        if self.b.first_contract_date != today - timedelta(days=10):
            self.skipTest('first contract date is not the version start here')
        names = [r['id'] for r in self.Team.joiners(self.boss_emp)]
        self.assertIn(self.b.id, names)

    def test_mt5b_yearly_dates(self):
        nxt = self.env['pb.me.team']._next_yearly
        self.assertEqual(nxt(date(1990, 2, 28), date(2026, 3, 1)),
                         date(2027, 2, 28))
        self.assertEqual(nxt(date(1992, 2, 29), date(2026, 1, 1)),
                         date(2026, 2, 28))
        self.assertIsNone(nxt(False, date(2026, 1, 1)))


@tagged('post_install', '-at_install')
class TestMyTeamPages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls.boss, cls.boss_emp = _staff(cls.env, 'test_mt_page_boss',
                                        'MT Page Boss', password=PASSWORD)
        cls.env['hr.employee'].create(
            {'name': 'MT Page Ana', 'parent_id': cls.boss_emp.id})
        cls.loner, _emp = _staff(cls.env, 'test_mt_page_loner',
                                 'MT Page Loner', password=PASSWORD)

    def test_mt6_pages_for_a_manager(self):
        self.authenticate(self.boss.login, PASSWORD)
        home = self.url_open('/my', timeout=60)
        self.assertEqual(home.status_code, 200)
        self.assertIn('pbmt-card', home.text)
        team = self.url_open('/my/team', timeout=60)
        self.assertEqual(team.status_code, 200)
        self.assertIn('MT Page Ana', team.text)
        ap = self.url_open('/my/team/approvals', timeout=60)
        self.assertEqual(ap.status_code, 200)
        self.assertIn('pbmt-tabs', ap.text)
        gone = self.url_open('/my/team/approvals/999999999', timeout=60)
        self.assertEqual(gone.status_code, 404)

    def test_mt6b_not_a_manager(self):
        self.authenticate(self.loner.login, PASSWORD)
        home = self.url_open('/my', timeout=60)
        self.assertNotIn('pbmt-card', home.text)
        page = self.url_open('/my/team', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Nobody reports to you', page.text)
