# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Approval Matrix P6 — Q07: whose queue is being asked for.

Three scopes, and the rule that matters is the same for all of them: a wider
scope is a way of LOOKING. Nothing here may hand anybody a decision they do
not hold a seat for, and nothing may show a manager somebody else's team.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInboxScopes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Inbox = cls.env['pb.approval.inbox']
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')

        cls.boss_user = Users.create({
            'name': 'Scope Boss', 'login': 'p6_scope_boss',
            'group_ids': [(6, 0, [internal.id])]})
        cls.other_boss = Users.create({
            'name': 'Other Boss', 'login': 'p6_scope_other',
            'group_ids': [(6, 0, [internal.id])]})
        cls.staff_user = Users.create({
            'name': 'Scope Staff', 'login': 'p6_scope_staff',
            'group_ids': [(6, 0, [internal.id])]})
        cls.deep_user = Users.create({
            'name': 'Scope Deep', 'login': 'p6_scope_deep',
            'group_ids': [(6, 0, [internal.id])]})

        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'Scope Boss',
                               'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({'name': 'Scope Staff',
                                'user_id': cls.staff_user.id,
                                'parent_id': cls.boss.id,
                                'company_id': cls.company.id})
        # somebody two levels down: "my team" is the whole branch, not one row
        cls.deep = Emp.create({'name': 'Scope Deep',
                               'user_id': cls.deep_user.id,
                               'parent_id': cls.staff.id,
                               'company_id': cls.company.id})
        Emp.create({'name': 'Other Boss', 'user_id': cls.other_boss.id,
                    'company_id': cls.company.id})

    def _ask(self, about_user):
        """One request about somebody, through the engine's own object."""
        record = self.env['biz.approval.generic.request'].sudo().create({
            'name': 'P6 scope request',
            'company_id': self.company.id,
            'requester_user_id': about_user.id,
        })
        request = self.env['biz.approval.engine'].sudo().submit(record)
        row = self.env['biz.approval.request'].sudo().browse(request['id'])
        # the engine's own object is about its requester; the scope reads the
        # link, so this is the one thing the fixture has to state
        row.write({'subject_user_ids': [(6, 0, [about_user.id])],
                   'subject_uids': [about_user.id]})
        return row

    # ==================================================================
    def test_q07a_my_team_is_the_whole_branch_under_me(self):
        team = self.Inbox.with_user(self.boss_user)._my_team_user_ids()
        self.assertIn(self.staff_user.id, team)
        self.assertIn(self.deep_user.id, team,
                      'a manager of managers sees their whole area')
        self.assertNotIn(self.boss_user.id, team,
                         'my own requests are "mine", not "my team\'s"')

    def test_q07b_a_manager_sees_their_team_and_nobody_else(self):
        mine = self._ask(self.staff_user)
        theirs = self._ask(self.other_boss)
        data = self.Inbox.with_user(self.boss_user).list_requests(
            tab='all', scope='team')
        ids = {card['id'] for card in data['cards']}
        self.assertIn(mine.id, ids)
        self.assertNotIn(theirs.id, ids,
                         'the team scope must never reach outside the team')
        self.assertEqual(data['scope'], 'team')

    def test_q07c_watching_is_not_deciding(self):
        self._ask(self.staff_user)
        data = self.Inbox.with_user(self.boss_user).list_requests(
            tab='all', scope='team')
        for card in data['cards']:
            self.assertFalse(card['mine'],
                             'a wider queue is a read, never a seat')

    def test_q07d_the_whole_company_is_refused_to_an_ordinary_person(self):
        with self.assertRaises(AccessError):
            self.Inbox.with_user(self.staff_user).list_requests(
                tab='all', scope='org')

    def test_q07e_somebody_with_nobody_under_them_is_offered_no_team(self):
        data = self.Inbox.with_user(self.deep_user).list_requests(
            tab='all', scope='me')
        self.assertFalse(data['has_team'])

    def test_q07f_the_drawer_opens_for_a_request_in_my_team_queue(self):
        mine = self._ask(self.staff_user)
        payload = self.Inbox.with_user(self.boss_user).get_request(
            mine.id, 'team')
        self.assertEqual(payload['id'], mine.id)
        self.assertFalse(payload['can_decide'],
                         'opening it is not being asked to decide it')

    # ------------------------------------------------------------ the dock
    def test_q07g_the_dock_reads_the_same_queue(self):
        mine = self._ask(self.staff_user)
        data = self.Inbox.with_user(self.boss_user).get_team_data(
            recursive=True, scope='team', queues_only=True)
        rows = data['queues']['items']
        self.assertTrue(data['has_team'])
        self.assertIn(mine.res_id, [row['res_id'] for row in rows])
        for row in rows:
            for key in ('model', 'res_id', 'source', 'title', 'employee',
                        'age', 'can_approve', 'can_refuse', 'takes_note',
                        'is_clean'):
                self.assertIn(key, row, 'the dock needs %s' % key)
            self.assertFalse(row['can_approve'],
                             'the dock offers a decision only to the seat')

    def test_q07h_every_kind_of_request_reaches_the_dock(self):
        """The old queue knew four kinds by name. This one knows none."""
        self._ask(self.staff_user)
        data = self.Inbox.with_user(self.boss_user).get_team_data(
            recursive=True, scope='team', queues_only=True)
        sources = {row['source'] for row in data['queues']['items']}
        self.assertTrue(sources <= {'ot', 'trip', 'correction', 'leave',
                                    'other'})
        self.assertIn('other', sources,
                      'a request that is none of the old four must still be '
                      'in the queue')
