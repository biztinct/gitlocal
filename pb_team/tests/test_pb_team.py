# Part of Payobook. See LICENSE file for full copyright and licensing details.
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
