# Part of Payobook. See LICENSE file for full copyright and licensing details.
import datetime

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPbTeam(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        Emp = cls.env['hr.employee']

        att_mgr = cls.env.ref('hr_attendance.group_hr_attendance_manager', raise_if_not_found=False)
        hr_user = cls.env.ref('hr.group_hr_user')
        internal = cls.env.ref('base.group_user')

        gids = [internal.id, hr_user.id]
        if att_mgr:
            gids.append(att_mgr.id)
        cls.manager_user = Users.create({
            'name': 'Team Manager', 'login': 'test_team_mgr',
            'group_ids': [(6, 0, gids)]})
        cls.plain_user = Users.create({
            'name': 'Plain Report', 'login': 'test_team_plain',
            'group_ids': [(6, 0, [internal.id])]})

        cls.manager = Emp.create({
            'name': 'Manager Emp', 'user_id': cls.manager_user.id,
            'company_id': cls.company.id})
        cls.report = Emp.create({
            'name': 'Report Emp', 'parent_id': cls.manager.id,
            'user_id': cls.plain_user.id, 'company_id': cls.company.id})
        cls.outsider = Emp.create({
            'name': 'Outsider Emp', 'company_id': cls.company.id})

        cls.ot_report = cls._make_ot(cls.report)
        cls.ot_outsider = cls._make_ot(cls.outsider)

    @classmethod
    def _make_ot(cls, emp):
        ot = cls.env['hr.overtime.request'].sudo().create({
            'employee_id': emp.id, 'company_id': cls.env.company.id,
            'date': fields.Date.context_today(cls.env['hr.overtime.request']),
            'planned_hours': 2.0, 'overtime_type': 'weekday',
            'reason': 'test OT'})
        ot.action_submit()
        return ot

    # ------------------------------------------------------------- team
    def test_01_my_team_direct(self):
        team = self.env['pb.team'].with_user(self.manager_user)._my_team()
        self.assertIn(self.report, team)
        self.assertNotIn(self.outsider, team)

    def test_02_no_team_empty_state(self):
        data = self.env['pb.team'].with_user(self.plain_user).get_team_data()
        self.assertFalse(data['has_team'])
        self.assertEqual(data['team_size'], 0)
        # a friendly empty payload, never an error
        self.assertEqual(data['queues']['items'], [])

    # ------------------------------------------------------------ queues
    def test_03_queue_scoping(self):
        data = self.env['pb.team'].with_user(self.manager_user).get_team_data()
        ids = [(it['model'], it['res_id']) for it in data['queues']['items']]
        self.assertIn(('hr.overtime.request', self.ot_report.id), ids)
        self.assertNotIn(('hr.overtime.request', self.ot_outsider.id), ids)

    # -------------------------------------------------------------- act
    def test_04_act_whitelist_raises(self):
        Team = self.env['pb.team'].with_user(self.manager_user)
        with self.assertRaises(AccessError):
            Team.act('res.users', self.manager_user.id, 'approve')
        with self.assertRaises(AccessError):
            Team.act('hr.overtime.request', self.ot_report.id, 'frobnicate')

    def test_05_act_approve_ot(self):
        res = self.env['pb.team'].with_user(self.manager_user).act(
            'hr.overtime.request', self.ot_report.id, 'approve')
        self.assertTrue(res['ok'])
        self.assertEqual(self.ot_report.state, 'approved')

    def test_06_act_non_team_scope(self):
        # a non-HR user with no team cannot act on someone else's request
        with self.assertRaises(AccessError):
            self.env['pb.team'].with_user(self.plain_user).act(
                'hr.overtime.request', self.ot_outsider.id, 'approve')

    def test_07_refusal_surfaces(self):
        # a model refusal (not a crash) is caught and returned as a message.
        # A plain report trying to refuse an OT they don't own via the facade:
        # HR-scope is False and it's not their team → scope raise; instead we
        # prove the caught path with the manager refusing then re-refusing a
        # decided request (the model rejects the second refuse).
        Team = self.env['pb.team'].with_user(self.manager_user)
        r1 = Team.act('hr.overtime.request', self.ot_report.id, 'refuse', 'no')
        self.assertTrue(r1['ok'])
        self.assertEqual(self.ot_report.state, 'refused')
        # OT action_refuse only affects submitted rows; a second refuse is a
        # silent no-op at the model, so the facade reports ok with no change —
        # never a crash.
        r2 = Team.act('hr.overtime.request', self.ot_report.id, 'refuse')
        self.assertIn('ok', r2)

    # ------------------------------------ combined-review fixes (G–M pass)
    def test_08_groupless_line_manager_gets_a_board(self):
        """Review I-H1 (C18.65): a supervisor with reports and NO HR/attendance
        group must get their queue, not an AccessError — the queue reads are
        sudo behind the server-derived team scope."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        bare_mgr_user = Users.create({
            'name': 'Bare Manager', 'login': 'test_team_bare',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        bare_mgr = self.env['hr.employee'].create({
            'name': 'Bare Manager Emp', 'user_id': bare_mgr_user.id,
            'company_id': self.company.id})
        self.report.sudo().write({'parent_id': bare_mgr.id})
        data = self.env['pb.team'].with_user(bare_mgr_user).get_team_data()
        self.assertTrue(data['has_team'])
        sources = {i['source'] for i in data['queues']['items']}
        self.assertIn('ot', sources,
                      "the team's OT queue must be visible to a bare manager")
        names = {i['employee']['name'] for i in data['queues']['items']}
        self.assertIn('Report Emp', names)

    # =============================================== P3b T1 — the dock contract
    # Everything below is ADDITIVE. The standalone cockpit passes neither new
    # argument and must keep the payload it has always had; the dock needs four
    # things the payload did not carry.

    def test_09_total_is_always_present_even_with_no_team(self):
        """The dock's header renders `queues.total` directly. The key was only
        emitted on the has_team branch, so a user with no reports rendered
        "Needs you · undefined" — a missing key is not a zero."""
        for user in (self.manager_user, self.plain_user):
            data = self.env['pb.team'].with_user(user).get_team_data()
            self.assertIn('total', data['queues'],
                          'total must be present for %s' % user.name)
            self.assertIsInstance(data['queues']['total'], int)
        empty = self.env['pb.team'].with_user(self.plain_user).get_team_data()
        self.assertFalse(empty['has_team'])
        self.assertEqual(empty['queues']['total'], 0)
        self.assertEqual(empty['queues']['counts'], {})
        self.assertEqual(empty['queues']['has_more'], {})

    def test_10_when_iso_is_parseable_and_agrees_with_the_display_twin(self):
        """`when` is a `%d %b` display string — locale-shaped, year-less and
        un-sortable. `when_iso` is the same day as ISO-8601, produced beside it
        so the two can never describe different dates."""
        data = self.env['pb.team'].with_user(self.manager_user).get_team_data()
        rows = [i for i in data['queues']['items']
                if i['model'] == 'hr.overtime.request']
        self.assertTrue(rows, 'the OT fixture must be in the queue')
        for it in rows:
            self.assertIn('when_iso', it)
            parsed = datetime.date.fromisoformat(it['when_iso'])
            self.assertEqual(parsed, self.ot_report.date)
            # the display twin is the same day, rendered
            self.assertEqual(it['when'], parsed.strftime('%d %b'))

    def test_11_each_source_is_capped_and_counts_stay_true(self):
        """The four searches were UNBOUNDED. Capping the LIST must never
        understate the BACKLOG, or the dock's header would shrink as the queue
        grew past the cap — so `counts` is a search_count and `has_more` says
        the list was cut."""
        Team = self.env['pb.team'].with_user(self.manager_user)
        # 3 OT rows, read with a cap of 2
        extra = [self._make_ot(self.report) for _ in range(2)]
        self.assertEqual(len(extra), 2)
        queues = Team._build_queues(Team._my_team(), limit=2)
        ot_items = [i for i in queues['items'] if i['source'] == 'ot']
        self.assertEqual(len(ot_items), 2, 'the list must honour the cap')
        self.assertEqual(queues['counts']['ot'], 3, 'counts must be the TRUTH')
        self.assertTrue(queues['has_more']['ot'])
        self.assertEqual(queues['total'], 3,
                         'total sums the true counts, not the capped list')
        # ... and an uncapped read of the same queue returns everything
        full = Team._build_queues(Team._my_team(), limit=80)
        self.assertEqual(len([i for i in full['items'] if i['source'] == 'ot']), 3)
        self.assertFalse(full['has_more']['ot'])

    def test_12_the_default_cap_is_twenty_per_source(self):
        """A default nobody passes is a default nobody notices changing."""
        from odoo.addons.pb_team.models.pb_team import _SOURCE_CAP
        self.assertEqual(_SOURCE_CAP, 20)

    # ------------------------------------------------------------ org scope
    def test_13_org_scope_is_refused_for_a_plain_line_manager(self):
        """`can_org` is a visibility hint; this is the gate. A client that sends
        scope='org' anyway gets an AccessError, not a wider queue (W12)."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        line_user = Users.create({
            'name': 'Line Only', 'login': 'test_team_line',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        line_mgr = self.env['hr.employee'].create({
            'name': 'Line Only Emp', 'user_id': line_user.id,
            'company_id': self.company.id})
        self.env['hr.employee'].create({
            'name': 'Line Report', 'parent_id': line_mgr.id,
            'company_id': self.company.id})
        Team = self.env['pb.team'].with_user(line_user)
        self.assertFalse(Team._can_org())
        self.assertFalse(Team.get_team_data()['can_org'],
                         'the dock must not offer a toggle this user cannot use')
        with self.assertRaises(AccessError):
            Team.get_team_data(scope='org')

    def test_14_org_scope_reads_other_managers_teams(self):
        """The whole point: an HR manager sees the request of somebody who does
        not report to them, which team scope by construction cannot show."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        hr_mgr_user = Users.create({
            'name': 'HR Manager', 'login': 'test_team_hrmgr',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_manager').id])]})
        self.env['hr.employee'].create({
            'name': 'HR Manager Emp', 'user_id': hr_mgr_user.id,
            'company_id': self.company.id})
        Team = self.env['pb.team'].with_user(hr_mgr_user)
        self.assertTrue(Team.get_team_data()['can_org'])

        # they manage nobody, so team scope is empty…
        team = Team.get_team_data()
        self.assertFalse(team['has_team'])
        self.assertEqual(team['queues']['total'], 0)
        self.assertEqual(team['scope'], 'team')

        # … and org scope carries the OUTSIDER's request, which belongs to no
        # team of theirs at all.
        org = Team.get_team_data(scope='org')
        self.assertEqual(org['scope'], 'org')
        self.assertTrue(org['has_team'])
        ids = [(i['model'], i['res_id']) for i in org['queues']['items']]
        self.assertIn(('hr.overtime.request', self.ot_outsider.id), ids)
        self.assertIn(('hr.overtime.request', self.ot_report.id), ids)

    def test_15_org_scope_never_builds_the_roster_or_the_metrics(self):
        """Org scope is a QUEUE scope. The roster and metric builders walk the
        whole population (OT ceilings, shift compliance, the exception engine);
        across a company that is minutes of work, four times a minute, for a
        rail nobody asked for. Same SHAPE, no work."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        hr_mgr_user = Users.create({
            'name': 'HR Manager 2', 'login': 'test_team_hrmgr2',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_manager').id])]})
        org = self.env['pb.team'].with_user(hr_mgr_user).get_team_data(scope='org')
        self.assertEqual(org['roster'], [])
        self.assertEqual(set(org['metrics']),
                         {'headcount', 'compliance', 'ot', 'exceptions',
                          'upcoming_leaves'},
                         'the metrics SHAPE must survive, empty')
        self.assertEqual(org['metrics']['ot'], {})

    def test_16_queues_only_skips_the_roster_on_team_scope_too(self):
        """The dock polls every 60 s and never renders a roster rail."""
        Team = self.env['pb.team'].with_user(self.manager_user)
        full = Team.get_team_data()
        light = Team.get_team_data(queues_only=True)
        self.assertTrue(full['roster'], 'the cockpit still gets its roster')
        self.assertEqual(light['roster'], [])
        # the QUEUE is identical either way — that is the part the dock uses
        self.assertEqual([i['res_id'] for i in full['queues']['items']],
                         [i['res_id'] for i in light['queues']['items']])

    def test_17_the_cockpits_payload_shape_is_unchanged(self):
        """P3b is additive. The standalone cockpit calls get_team_data() with no
        arguments; every key it reads must still be there, with the same type."""
        data = self.env['pb.team'].with_user(self.manager_user).get_team_data()
        for key in ('has_team', 'is_hr', 'recursive', 'me', 'team_size',
                    'queues', 'metrics', 'roster'):
            self.assertIn(key, data, '%s disappeared from the payload' % key)
        self.assertEqual(set(data['queues']) - {'has_more'},
                         {'items', 'counts', 'total'})
        item = data['queues']['items'][0]
        for key in ('model', 'res_id', 'source', 'title', 'subtitle', 'when',
                    'employee', 'age', 'can_approve', 'can_refuse'):
            self.assertIn(key, item, '%s disappeared from a queue item' % key)
        # …plus the new ones the dock needs
        self.assertIn('when_iso', item)
        self.assertIn('takes_note', item)
        self.assertIn('can_org', data)
        self.assertIn('scope', data)

    def test_19_takes_note_mirrors_the_act_whitelist_exactly(self):
        """W42. Two of the four refuse actions record a note; two have no note
        parameter at all. A surface that makes the field REQUIRED has to know
        which is which, or it demands a reason and then throws it away — so the
        flag is DERIVED from the same map `act()` dispatches on rather than
        written down twice."""
        from odoo.addons.pb_team.models.pb_team import _ACT_MAP, _takes_note
        expected = {'hr.overtime.request': False, 'hr.leave': False,
                    'pb.business.trip': True, 'hr.attendance.correction': True}
        for model, keeps in expected.items():
            self.assertEqual(_takes_note(model), keeps, model)
            self.assertEqual(_ACT_MAP[model]['refuse']['note'], keeps,
                             '%s: the flag and the dispatch must agree' % model)
        # an unknown model is not a note-taker (and does not raise)
        self.assertFalse(_takes_note('res.users'))

        data = self.env['pb.team'].with_user(self.manager_user).get_team_data()
        ot = [i for i in data['queues']['items']
              if i['model'] == 'hr.overtime.request']
        self.assertTrue(ot)
        self.assertFalse(ot[0]['takes_note'],
                         'OT refusal keeps no note, so the dock must not '
                         'demand one')

    def test_18_act_still_refuses_what_the_real_user_cannot_do(self):
        """Org scope widens the READ. It must not widen the WRITE: `act` is
        unchanged, still real-user, still scope-checked (W12)."""
        # a plain report cannot approve their own team-mate's request
        with self.assertRaises(AccessError):
            self.env['pb.team'].with_user(self.plain_user).act(
                'hr.overtime.request', self.ot_outsider.id, 'approve')
        # and the whitelist still bites, whatever the scope
        with self.assertRaises(AccessError):
            self.env['pb.team'].with_user(self.manager_user).act(
                'res.users', self.manager_user.id, 'approve')
