# -*- coding: utf-8 -*-
"""NAV P3c — Home › TEAM (`pb.home.team`).

The promises, in the order the handover lists them:

  * the tab is offered to somebody with an active direct report and to
    nobody else;
  * "my team" is the direct reports and only them — a fourth employee under
    another manager never appears, in any section;
  * the hero's buckets add up to the people strip;
  * "Waiting on you" is the inbox's own My turn count, split by tile;
  * probation and goals rows are the reader's own (`manager_user_id = me`)
    even when the reader sits in the goals HR group;
  * training is `pb.my.training.team()`'s own answer;
  * hiring rows carry no budget word and no confidential role that is not
    theirs;
  * a section whose module is absent is absent, not zero;
  * and no amount, salary, wage, budget, cost, growth-plan or red-flag key
    exists anywhere in the payload (walked recursively).
"""
import os
import re
from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)

#: Any key containing one of these words fails the payload walk.
FORBIDDEN = ('amount', 'salary', 'wage', 'budget', 'cost', 'money',
             'currency', 'pay_', 'pip', 'growth', 'red_flag', 'flag',
             'training_pending', 'score', 'rating', 'verdict')


def _walk_keys(value, path=''):
    """Every (path, key) in a nested dict/list payload."""
    if isinstance(value, dict):
        for key, inner in value.items():
            yield path, str(key)
            yield from _walk_keys(inner, '%s.%s' % (path, key))
    elif isinstance(value, (list, tuple)):
        for i, inner in enumerate(value):
            yield from _walk_keys(inner, '%s[%s]' % (path, i))


def _read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestTeamP3c(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')

        def user(login, name):
            return Users.create({
                'name': name, 'login': login, 'email': '%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [internal.id])],
            })

        cls.mgr_user = user('p3c_mgr', 'DEMO Trần Minh Quân')
        cls.other_user = user('p3c_other', 'DEMO Lê Văn Bình')
        cls.r1_user = user('p3c_r1', 'DEMO Nguyễn Thị Hoa')
        cls.asker = user('p3c_asker', 'DEMO Phạm Văn Hỏi')

        Emp = cls.env['hr.employee'].with_context(tracking_disable=True)
        base = {'company_id': cls.company.id}
        cls.mgr = Emp.create(dict(base, name='DEMO Trần Minh Quân',
                                  user_id=cls.mgr_user.id))
        cls.other = Emp.create(dict(base, name='DEMO Lê Văn Bình',
                                    user_id=cls.other_user.id))
        cls.r1 = Emp.create(dict(base, name='DEMO Nguyễn Thị Hoa',
                                 user_id=cls.r1_user.id, parent_id=cls.mgr.id))
        cls.r2 = Emp.create(dict(base, name='DEMO Đỗ Văn Nam',
                                 parent_id=cls.mgr.id))
        cls.r3 = Emp.create(dict(base, name='DEMO Vũ Thu Linh',
                                 parent_id=cls.mgr.id))
        # the fourth employee, under somebody else
        cls.r4 = Emp.create(dict(base, name='DEMO Hoàng Văn Khác',
                                 parent_id=cls.other.id))
        # an archived report counts for nothing
        cls.gone = Emp.create(dict(base, name='DEMO Đã Nghỉ',
                                   parent_id=cls.mgr.id))
        cls.gone.write({'active': False})
        # nobody's working calendar decides "off" in these cases
        (cls.r1 | cls.r2 | cls.r3 | cls.r4).write(
            {'resource_calendar_id': False})

        cls.Team = cls.env['pb.home.team']

    def team(self, user=None):
        return self.Team.with_user(user or self.mgr_user).with_company(
            self.company).get_team()

    # ================================================================ who
    def test_01_can_open_follows_direct_reports(self):
        self.assertTrue(self.Team.with_user(self.mgr_user).can_open())
        self.assertTrue(self.Team.with_user(self.other_user).can_open())
        self.assertFalse(self.Team.with_user(self.r1_user).can_open(),
                         'somebody with no report is not offered the tab')
        self.assertFalse(self.Team.with_user(self.asker).can_open())

    def test_02_three_reports_and_never_the_fourth(self):
        data = self.team()
        ids = {p['id'] for p in data['people']}
        self.assertEqual(ids, {self.r1.id, self.r2.id, self.r3.id})
        self.assertEqual(data['size'], 3)
        self.assertNotIn(self.gone.id, ids, 'an archived report is not team')
        # the fourth employee belongs to the other manager
        theirs = {p['id'] for p in self.team(self.other_user)['people']}
        self.assertEqual(theirs, {self.r4.id})

    def test_03_today_buckets_add_up_to_the_strip(self):
        today = fields.Date.context_today(self.Team.with_user(self.mgr_user))
        now = fields.Datetime.now()
        if 'hr.attendance' in self.env:
            self.env['hr.attendance'].sudo().create({
                'employee_id': self.r1.id,
                'check_in': max(now - timedelta(minutes=30),
                                datetime.combine(today, datetime.min.time())
                                + timedelta(minutes=1)),
            })
        leave_ok = False
        if 'hr.leave' in self.env:
            leave_ok = self._leave(self.r2, today)
        data = self.team()
        by_id = {p['id']: p for p in data['people']}
        counts = data['counts']
        self.assertEqual(
            counts['in'] + counts['on_leave'] + counts['not_started']
            + counts['off'], data['size'],
            'every person is in exactly one bucket')
        if 'hr.attendance' in self.env:
            self.assertEqual(by_id[self.r1.id]['bucket'], 'in')
            self.assertIn(by_id[self.r1.id]['status'], ('in', 'late'))
        if leave_ok:
            self.assertEqual(by_id[self.r2.id]['bucket'], 'on_leave')
            self.assertEqual(by_id[self.r2.id]['status'], 'on_leave')
        self.assertEqual(by_id[self.r3.id]['bucket'], 'not_started')
        for p in data['people']:
            self.assertTrue(p['words'], 'every face has a tooltip sentence')

    def test_03b_a_planned_shift_makes_lateness_the_today_boards_word(self):
        """With the Today board installed, its own row builder decides who
        is late: a shift that started two hours ago and no punch is "late,
        not in yet" — amber, still counted under not started."""
        if 'pb.today' not in self.env or 'hr.shift.planning' not in self.env:
            self.skipTest('the Today board is not installed')
        template = self.env['hr.shift.template'].sudo().search([], limit=1)
        if not template:
            self.skipTest('no shift template on this database')
        today = fields.Date.context_today(self.Team.with_user(self.mgr_user))
        now = fields.Datetime.now()
        start = max(now - timedelta(hours=2),
                    datetime.combine(today, datetime.min.time())
                    + timedelta(minutes=1))
        self.env['hr.shift.planning'].sudo().with_context(
            tracking_disable=True).create({
                'employee_id': self.r3.id, 'shift_template_id': template.id,
                'date': today, 'start_datetime': start,
                'end_datetime': start + timedelta(hours=8),
                'state': 'published', 'company_id': self.company.id})
        grace = self.env['pb.attendance.rule']._grace_for_company(
            self.company)[0] if 'pb.attendance.rule' in self.env else 0
        if (now - start).total_seconds() / 60.0 <= (grace or 0) + 1:
            self.skipTest('too close to midnight to be late yet')
        row = next(p for p in self.team()['people'] if p['id'] == self.r3.id)
        self.assertEqual(row['status'], 'late')
        self.assertEqual(row['bucket'], 'not_started')
        self.assertGreater(row['minutes_late'], 0)

    def _leave(self, employee, day):
        """One approved day of leave, written as the system (the approval
        route is not what is under test). False when this database's leave
        rules refuse a bare fixture — the bucket test then skips that row."""
        Type = self.env['hr.leave.type'].sudo()
        vals = {'name': 'DEMO P3c leave', 'company_id': self.company.id}
        if 'requires_allocation' in Type._fields:
            vals['requires_allocation'] = False if isinstance(
                Type._fields['requires_allocation'],
                fields.Boolean) else 'no'
        try:
            with self.env.cr.savepoint():
                kind = Type.create(vals)
                leave = self.env['hr.leave'].sudo().with_context(
                    leave_skip_state_check=True, mail_create_nolog=True,
                    tracking_disable=True).create({
                        'employee_id': employee.id,
                        'holiday_status_id': kind.id,
                        'request_date_from': day,
                        'request_date_to': day,
                    })
                leave.sudo().write({'state': 'validate'})
            return True
        except Exception:                               # noqa: BLE001
            return False

    # ============================================================ decisions
    def _seat_for(self, user):
        role = self.env.ref('biz_approval_workflow.role_approver')
        Resp = self.env['biz.approval.responsibility'].sudo()
        Resp.search([('company_id', '=', self.company.id),
                     ('role_id', '=', role.id),
                     ('active', '=', True)]).write({'active': False})
        Resp.create({'company_id': self.company.id, 'role_id': role.id,
                     'scope_key': '', 'scope_label': self.company.name,
                     'user_id': user.id})

    def _ask(self, name):
        return self.env['pb.approval.inbox'].with_user(self.asker).with_company(
            self.company).ask({'name': name})

    def test_04_decisions_are_my_turn_split_by_tile(self):
        self._seat_for(self.mgr_user)
        self._ask('DEMO P3c one')
        self._ask('DEMO P3c two')
        inbox = self.env['pb.approval.inbox'].with_user(
            self.mgr_user).with_company(self.company).list_requests('mine')
        dec = self.team()['decisions']
        self.assertEqual(dec['total'], inbox['counts']['mine'])
        self.assertEqual(dec['total'], 2)
        tiles = {t['key']: t for t in dec['tiles']}
        self.assertEqual(sum(t['n'] for t in dec['tiles']), dec['total'],
                         'each card lands on exactly one tile')
        self.assertEqual(tiles['other']['n'], 2)
        self.assertEqual(tiles['other']['area'], 'other')
        # the same two cards, once the process is a "time" one
        process = self.env.ref('biz_approval_workflow.process_generic')
        process.sudo().write({'area': 'time'})
        tiles = {t['key']: t for t in self.team()['decisions']['tiles']}
        self.assertEqual(tiles['overtime']['n'], 2)
        self.assertEqual(tiles['overtime']['area'], 'time')
        self.assertEqual(tiles['other']['n'], 0)
        # nothing waits on somebody who holds no seat
        self.assertEqual(self.team(self.other_user)['decisions']['total'], 0)

    def test_05_decisions_never_ask_for_the_team_scope(self):
        calls = []
        Inbox = type(self.env['pb.approval.inbox'])
        original = Inbox.list_requests

        def spy(this, *args, **kwargs):
            calls.append((args, kwargs))
            return original(this, *args, **kwargs)

        with patch.object(Inbox, 'list_requests', spy):
            self.team()
        self.assertTrue(calls)
        for args, kwargs in calls:
            self.assertEqual(kwargs.get('scope', 'me'), 'me')
            self.assertEqual(kwargs.get('tab', args[0] if args else 'mine'),
                             'mine')

    # ============================================================ probation
    def test_06_probation_rows_are_mine_and_my_reports_only(self):
        if 'pb.probation.review' not in self.env:
            self.skipTest('pb_probation is not installed')
        Review = self.env['pb.probation.review'].sudo().with_context(
            tracking_disable=True, mail_create_nolog=True)
        soon = date.today() + timedelta(days=5)
        mine = Review.create({'employee_id': self.r1.id, 'state': 'one_on_one',
                              'manager_user_id': self.mgr_user.id,
                              'trial_end': soon})
        # my report, but the review names another manager
        Review.create({'employee_id': self.r2.id, 'state': 'verdict',
                       'manager_user_id': self.other_user.id,
                       'trial_end': soon})
        # names me, but not my report
        Review.create({'employee_id': self.r4.id, 'state': 'verdict',
                       'manager_user_id': self.mgr_user.id,
                       'trial_end': soon})
        # my report, not at my step yet
        Review.create({'employee_id': self.r3.id, 'state': 'feedback',
                       'manager_user_id': self.mgr_user.id,
                       'trial_end': soon})
        prob = self.team()['probation']
        self.assertEqual([r['review_id'] for r in prob['rows']], [mine.id])
        self.assertEqual(prob['total'], 1)
        self.assertEqual(prob['door'], '',
                         'a plain manager has no probation screen to open')

    # ================================================================ goals
    def _goal_sheet(self, employee):
        Cycle = self.env['pb.goal.cycle'].sudo()
        cycle = Cycle.search([('company_id', '=', self.company.id),
                              ('state', '=', 'open')], limit=1)
        if not cycle:
            today = date.today()
            cycle = Cycle.create({
                'name': 'DEMO P3c year', 'company_id': self.company.id,
                'date_start': today - timedelta(days=200),
                'date_end': today + timedelta(days=165),
                'mid_year_date': today - timedelta(days=20),
                'submission_days': 14,
            })
            cycle.action_open()
        Set = self.env['pb.goal.set'].sudo()
        sheet = Set.search([('employee_id', '=', employee.id),
                            ('cycle_id', '=', cycle.id)], limit=1)
        return sheet or Set.create({
            'employee_id': employee.id, 'cycle_id': cycle.id,
            'company_id': self.company.id,
            'deadline': date.today() + timedelta(days=14)})

    def test_07_goal_rows_are_mine_even_for_an_hr_goals_user(self):
        if 'pb.goal.checkin' not in self.env:
            self.skipTest('pb_goals is not installed')
        hr_group = self.env.ref('pb_goals.group_goals_manager',
                                raise_if_not_found=False)
        if hr_group:
            self.mgr_user.sudo().write({'group_ids': [(4, hr_group.id)]})
        today = date.today()
        Checkin = self.env['pb.goal.checkin'].sudo()
        mine = Checkin.create({
            'set_id': self._goal_sheet(self.r1).id,
            'month': today.replace(day=1),
            'scheduled_date': today - timedelta(days=6), 'state': 'planned'})
        theirs = Checkin.create({
            'set_id': self._goal_sheet(self.r4).id,
            'month': today.replace(day=1),
            'scheduled_date': today - timedelta(days=6), 'state': 'planned'})
        self.assertEqual(theirs.manager_user_id, self.other_user)
        goals = self.team()['goals']
        ids = [(r['kind'], r['id']) for r in goals['rows']]
        self.assertIn(('checkin', mine.id), ids)
        self.assertNotIn(('checkin', theirs.id), ids,
                         'the HR goals group never widens TEAM')
        row = next(r for r in goals['rows'] if r['id'] == mine.id)
        self.assertTrue(row['late'])
        self.assertIn('6', row['when'])

    # ============================================================= training
    def test_08_training_is_the_managers_own_page(self):
        if 'pb.my.training' not in self.env:
            self.skipTest('pb_training is not installed')
        team = self.env['pb.my.training'].with_user(self.mgr_user).team()
        data = self.team()['training']
        self.assertEqual(data['overdue'], team['overdue'])
        self.assertEqual(data['due'], team['due'])
        self.assertEqual(data['done'], team['done'])
        overdue_people = {r['employee_id'] for r in team['rows']
                          if r['state'] == 'overdue'}
        self.assertEqual(data['overdue_people'], len(overdue_people))

    # =============================================================== hiring
    def test_09_hiring_rows_are_mine_and_carry_no_budget(self):
        if 'pb.hiring.requisition' not in self.env:
            self.skipTest('pb_hiring is not installed')
        Req = self.env['pb.hiring.requisition'].sudo().with_context(
            tracking_disable=True, mail_create_nolog=True)
        if 'request_state' not in Req._fields:
            self.skipTest('no hiring requests on this database')
        dept = self.env['hr.department'].sudo().create(
            {'name': 'DEMO P3c dept', 'company_id': self.company.id})
        base = {'department_id': dept.id, 'company_id': self.company.id}
        asked = Req.create(dict(base, title='DEMO Field agronomist',
                                request_state='asked',
                                asked_user_id=self.mgr_user.id))
        sent = Req.create(dict(base, title='DEMO Store lead',
                               request_state='sent_in',
                               requested_by_id=self.mgr.id))
        secret = Req.create(dict(base, title='DEMO Secret role',
                                 request_state='sent_in', is_confidential=True,
                                 requested_by_id=self.other.id))
        done = Req.create(dict(base, title='DEMO Agreed role',
                               request_state='agreed',
                               requested_by_id=self.mgr.id))
        asked.sudo().write({'request_token': 'p3c-token-abcdefghijkl'})
        sent.sudo().write({'request_token': 'p3c-token-not-mine-to-write'})
        hiring = self.team()['hiring']
        ids = [r['id'] for r in hiring['rows']]
        by_id = {r['id']: r for r in hiring['rows']}
        self.assertEqual(by_id[asked.id]['write_url'],
                         '/hiring/r/p3c-token-abcdefghijkl',
                         'the request to write opens the page it is written on')
        self.assertEqual(by_id[sent.id]['write_url'], '',
                         'a sent-in request never hands out its link')
        self.assertIn(asked.id, ids)
        self.assertIn(sent.id, ids)
        self.assertNotIn(secret.id, ids, 'a confidential role not mine')
        self.assertNotIn(done.id, ids, 'an agreed request is not in flight')
        first = hiring['rows'][0]
        self.assertEqual(first['id'], asked.id, 'waiting on me comes first')
        self.assertTrue(first['on_me'])
        self.assertEqual(hiring['on_me'], 1)
        for row in hiring['rows']:
            for key in row:
                self.assertNotIn('budget', key)

    # ======================================================= absent modules
    def test_10_an_absent_module_is_an_absent_section(self):
        Team = type(self.Team)
        missing = {'pb.probation.review', 'pb.goal.checkin',
                   'pb.my.training', 'pb.hiring.requisition',
                   'pb.approval.inbox'}
        real = Team._model

        def fake(this, name):
            return None if name in missing else real(this, name)

        with patch.object(Team, '_model', fake):
            data = self.team()
        for key in ('probation', 'goals', 'training', 'hiring', 'decisions'):
            self.assertNotIn(key, data, '%s must be absent, not zero' % key)
        self.assertEqual(data['size'], 3, 'the people strip still draws')

    # ============================================================ no money
    def test_11_no_money_word_anywhere_in_the_payload(self):
        self._seat_for(self.mgr_user)
        self._ask('DEMO P3c amount check')
        payload = self.team()
        bad = []
        for path, key in _walk_keys(payload):
            low = key.lower()
            if any(word in low for word in FORBIDDEN):
                bad.append('%s.%s' % (path, key))
        self.assertFalse(bad, 'money or private words in TEAM: %s' % bad)

    def test_12_the_walker_really_walks(self):
        """The forbidden-key walk would pass on an empty generator; prove it
        finds a key three levels down and inside a list."""
        sample = {'a': [{'b': {'salary_band': 1}}]}
        keys = [k for _p, k in _walk_keys(sample)]
        self.assertIn('salary_band', keys)

    # ============================================================== static
    def test_13_no_hard_dependency_was_added(self):
        manifest = _read(HERE, '__manifest__.py')
        for module in ('pb_today', 'pb_probation', 'pb_goals', 'pb_training',
                       'pb_hiring', 'pb_employee_vault', 'hr_attendance',
                       'hr_holidays', 'pb_pip'):
            self.assertNotIn("'%s'" % module, manifest)
        src = _read(HERE, 'models', 'team_facade.py')
        self.assertNotIn('pb.pip', src, 'TEAM reads nothing from growth plans')
        self.assertNotRegex(src, r"self\.env\['pb\.(today|probation|goals|"
                                 r"hiring|people|attendance)")

    def test_14_the_lens_is_registered_with_its_probe(self):
        src = _read(HERE, 'static', 'src', 'js', 'team_lens.js')
        self.assertIn('registry.category(HOME_LENSES).add("team"', src)
        self.assertIn('probe: { model: "pb.home.team", method: "can_open" }',
                      src)
        self.assertIn('{ sequence: 12 }', src)
        self.assertIn('from "@pb_import_kit/js/import_icons"', src)
        xml = _read(HERE, 'static', 'src', 'xml', 'team_lens.xml')
        for anchor in ('tm-hero', 'tm-waiting', 'tm-conversations',
                       'tm-learning', 'tm-hiring'):
            self.assertIn('data-coach="%s"' % anchor, xml)
        # R9: no vendor name in anything a person reads — the _t() words
        # and the template's text, never the import paths.
        words = re.findall(r'_t\("([^"]*)"', src)
        body = re.sub(r'<!--.*?-->', '', xml, flags=re.S)
        words += re.findall(r'>([^<]+)<', body)
        words += re.findall(r'(?:title|aria-label|placeholder)="([^"]*)"',
                            body)
        self.assertTrue(words)
        for word in words:
            self.assertNotIn('odoo', word.lower(), word)

    def test_15_the_doors_land_filtered(self):
        """Each door names the screen and the filter it lands on."""
        src = _read(HERE, 'static', 'src', 'js', 'team_lens.js')
        self.assertIn('"area:" + area', src)
        self.assertIn('"person:" + row.employee_id', src)
        self.assertNotIn('"pb.probation.review"', src,
                         'the review form refuses a plain manager: no door to it')
        self.assertIn('"tab:" +', src)
        self.assertIn('/my/training/team', src)
        self.assertIn('pb_role_id: row.id', src)
        self.assertIn('/my/hiring', src, 'a plain manager has a door too')
        inbox = _read(ROOT, 'pb_approval_config', 'static', 'src', 'js',
                      'inbox.js')
        self.assertIn('export function focusArea', inbox)
        self.assertIn('this.state.area = area', inbox)
        prob = _read(ROOT, 'pb_probation', 'static', 'src', 'js',
                     'probation_board.js')
        self.assertIn('person:(\\d+)', prob)
        goals = _read(ROOT, 'pb_goals', 'static', 'src', 'js',
                      'goals_board.js')
        self.assertIn('tab:(checkins|reviews)', goals)
