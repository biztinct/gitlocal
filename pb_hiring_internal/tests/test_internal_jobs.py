# -*- coding: utf-8 -*-
"""S6-B item 4 — staff apply for internal roles (model level).

Numbered as in docs/handovers/wdgap/WDGAP_S6B_REPORT.md (B1–B16).
"""
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hiring_internal.models import requisition as req_mod

from .common import make_world, stage


@tagged('post_install', '-at_install', 'wdgap_s6b')
class TestInternalJobs(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_world(cls, 'wdgap_s6b_jobs')
        cls.Req = cls.env['pb.hiring.requisition']

    def _apply(self, role=None, note='', cv=None):
        return self.App.with_user(self.share).sudo()._pbhi_apply(
            self.mover, role or self.role_both, note=note, cv=cv)

    # B1 — silent install: every role is "Outside candidates only" by default
    def test_b01_default_is_outside_only(self):
        fresh = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'DEMO S6B Fresh role', 'department_id': self.dept_new.id,
            'company_id': self.company.id, 'headcount': 1})
        self.assertEqual(fresh.pb_staff_posting, 'outside')
        others = self.Req.sudo().search([('id', 'not in', (
            self.role_both | self.role_staff | self.role_outside | self.role_secret
            | self.role_quiet | fresh).ids)])
        self.assertFalse(others.filtered(lambda r: r.pb_staff_posting != 'outside'),
                         'B1: no existing role is open to staff after install')

    # B2 — which roles staff see
    def test_b02_roles_staff_see(self):
        seen = self.Req._pbhi_roles_for(self.mover)
        self.assertIn(self.role_both, seen)
        self.assertIn(self.role_staff, seen)
        for hidden in (self.role_outside, self.role_secret, self.role_quiet):
            self.assertNotIn(hidden, seen, hidden.title)
        self.role_both.sudo().write({'state': 'filled'})
        self.assertNotIn(self.role_both, self.Req._pbhi_roles_for(self.mover),
                         'B2: a role that is no longer open is not shown')

    def test_b02b_other_company_never_shown(self):
        other = self.env['res.company'].create({'name': 'DEMO S6B Other Co'})
        dept = self.env['hr.department'].create({'name': 'DEMO S6B Other dept',
                                                 'company_id': other.id})
        far = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'DEMO S6B Far role', 'department_id': dept.id,
            'company_id': other.id, 'headcount': 1, 'state': 'open',
            'pb_staff_posting': 'both'})
        self.assertNotIn(far, self.Req._pbhi_roles_for(self.mover))
        with self.assertRaises(UserError):
            self._apply(far)

    # B3 — contract C-2, without the probed field (this database)
    def test_b03_pause_probe_without_field(self):
        self.assertFalse(req_mod.job_paused(self.role_both.job_id))
        self.assertTrue(self.role_both._pbhi_open_for_staff())

    # B3b — contract C-2, with the field present and on (simulated: the probe
    # is pointed at a boolean the job has, set to True)
    def test_b03b_pause_probe_with_field(self):
        job = self.role_both.job_id
        job.sudo().write({'website_published': True})
        with patch.object(req_mod, 'PAUSED_FIELD', 'website_published'):
            self.assertTrue(req_mod.job_paused(job))
            self.assertNotIn(self.role_both, self.Req._pbhi_roles_for(self.mover),
                             'B3b: a paused role is hidden from staff')
            with self.assertRaises(UserError):
                self._apply()
        self.assertIn(self.role_both, self.Req._pbhi_roles_for(self.mover))

    # B4 — applying uses the existing record, never a new employee
    def test_b04_apply_with_own_record(self):
        employees = self.env['hr.employee'].sudo().search_count([])
        partner = self.mover.work_contact_id
        app = self._apply(note='I ran the night shift last year.')
        self.assertTrue(app.pb_internal)
        self.assertEqual(app.employee_id, self.mover)
        self.assertEqual(app.pb_requisition_id, self.role_both)
        self.assertEqual(app.job_id, self.role_both.job_id)
        self.assertEqual(app.source_id.name, 'Internal')
        self.assertEqual(app.email_from, 'demo.s6b.mover@example.com')
        self.assertIn('night shift', app.applicant_notes or '')
        self.assertEqual(self.env['hr.employee'].sudo().search_count([]), employees,
                         'B4: no employee record is made by applying')
        self.assertNotEqual(app.partner_id, partner,
                            'B4: the application has its own contact')
        self.assertEqual(app._pbhi_state(), 'received')

    # B5 — one application per role in play
    def test_b05_twice_refused(self):
        self._apply()
        with self.assertRaises(UserError):
            self._apply()

    # B6 — E4: before an offer is near the current manager sees nothing
    def test_b06_manager_sees_nothing_before_offer(self):
        manager = self.manager_user
        partner = manager.partner_id
        Notif = self.env['mail.notification'].sudo()
        Act = self.env['mail.activity'].sudo()
        Request = self.env['biz.approval.request'].sudo() \
            if 'biz.approval.request' in self.env else None
        before = (Notif.search_count([('res_partner_id', '=', partner.id)]),
                  Act.search_count([('user_id', '=', manager.id)]),
                  Request.with_user(manager).search_count([]) if Request is not None else 0)
        app = self._apply()
        # moving through the working stages is still "before an offer"
        for key in ('shortlist', 'discussion_1', 'discussion_2'):
            if stage(self.env, key):
                app.write({'stage_id': stage(self.env, key).id})
        self.env.flush_all()
        self.env.invalidate_all()
        after = (Notif.search_count([('res_partner_id', '=', partner.id)]),
                 Act.search_count([('user_id', '=', manager.id)]),
                 Request.with_user(manager).search_count([]) if Request is not None else 0)
        self.assertEqual(before, after, 'B6: no note, activity or approval reaches the manager')
        self.assertNotIn(partner, app.message_partner_ids)
        self.assertFalse(app.pb_manager_told_on)
        # the candidate record itself: refused, or simply not found
        try:
            found = self.env['hr.applicant'].with_user(manager).search_count(
                [('id', '=', app.id)])
        except AccessError:
            found = 0
        self.assertEqual(found, 0, 'B6: the manager cannot read the application')
        with self.assertRaises(AccessError):
            self.env['pb.hiring.internal'].with_user(manager).get_board()
        # their own home: no "may move" row, no moves page rows
        Home = self.env['pb.me.home'].with_user(manager)
        self.assertFalse(Home._pbhi_team_moves(self.manager))
        rows = []
        Home._pbme_needs_extra(self.manager, lambda key, n, url, **kw: rows.append(key))
        self.assertNotIn('pbhi_team_move', rows)

    # B7 — E4: told once, when an offer is near
    def test_b07_manager_told_when_offer_near(self):
        partner = self.manager_user.partner_id
        Notif = self.env['mail.notification'].sudo()
        before = Notif.search_count([('res_partner_id', '=', partner.id)])
        app = self._apply()
        app.write({'stage_id': stage(self.env, 'offer').id})
        self.assertTrue(app.pb_manager_told_on)
        self.assertEqual(app.pb_manager_told_id, self.manager)
        self.assertEqual(Notif.search_count([('res_partner_id', '=', partner.id)]),
                         before + 1, 'B7: one note in the manager inbox')
        note = Notif.search([('res_partner_id', '=', partner.id)], order='id desc', limit=1)
        self.assertIn('DEMO S6B Mover', note.mail_message_id.body)
        self.assertIn('DEMO S6B Shift lead', note.mail_message_id.body)
        self.assertNotIn('night', note.mail_message_id.body or '')
        # a second move does not tell them again
        app.write({'stage_id': stage(self.env, 'post_offer').id})
        self.assertEqual(Notif.search_count([('res_partner_id', '=', partner.id)]),
                         before + 1, 'B7: told once only')
        rows = []
        self.env['pb.me.home'].with_user(self.manager_user)._pbme_needs_extra(
            self.manager, lambda key, n, url, **kw: rows.append((key, n, url)))
        self.assertIn(('pbhi_team_move', 1, '/my/jobs/moves'), rows)

    def test_b07b_offer_drafted_tells_manager(self):
        app = self._apply()
        self.role_both.sudo().write({'selected_applicant_id': app.id})
        bgv = self.env['pb.hiring.bgv'].open_for(self.role_both.id)
        bgv.item_ids.sudo().write({'result': 'ok'})
        offer = self.env['pb.hiring.offer'].draft_for(self.role_both.id)
        self.assertTrue(offer)
        self.assertTrue(app.pb_manager_told_on, 'B7b: a drafted offer is an offer near')

    # B8 — the manager on the role's hiring team: the employee is told first
    def test_b08_manager_on_hiring_team(self):
        self.assertFalse(self.role_both._pbhi_manager_on_team(self.mover))
        self.role_both.sudo().write({'reporting_manager_id': self.manager.id})
        self.assertTrue(self.role_both._pbhi_manager_on_team(self.mover))
        self.role_both.sudo().write({'reporting_manager_id': self.boss.id,
                                     'recruiter_id': self.manager_user.id})
        self.assertTrue(self.role_both._pbhi_manager_on_team(self.mover))

    # B9 — withdrawing before an offer; refused from the offer on
    def test_b09_withdraw(self):
        app = self._apply()
        self.assertTrue(app._pbhi_can_withdraw())
        app._pbhi_withdraw()
        self.assertEqual(app._pbhi_state(), 'withdrawn')
        self.assertEqual(app.stage_id.pb_key, 'drop_out')
        again = self._apply()          # a new application after withdrawing
        again.write({'stage_id': stage(self.env, 'offer').id})
        self.assertFalse(again._pbhi_can_withdraw())
        with self.assertRaises(UserError):
            again._pbhi_withdraw()

    # B10 — the employee's words, never the hiring team's stage names
    def test_b10_employee_words(self):
        app = self._apply()
        self.assertEqual(app._pbhi_state(), 'received')
        app.write({'stage_id': stage(self.env, 'discussion_1').id})
        self.assertEqual(app._pbhi_state(), 'considered')
        app.write({'stage_id': stage(self.env, 'interview_reject').id})
        self.assertEqual(app._pbhi_state(), 'closed')
        Home = self.env['pb.me.home'].with_user(self.share)
        got = Home.get_my_requests(self.mover)
        rows = [r for r in got['rows'] if r['key'] == 'pbhi_internal_role']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['state_label'], 'Not this time')
        self.assertEqual(rows[0]['url'], '/my/jobs/%s' % self.role_both.id)

    def test_b10b_outside_hire_row_not_listed(self):
        """An outside hire's old candidate row points at their employee too;
        it is not a staff application and never shows in My requests."""
        self.App.create({'partner_name': 'DEMO S6B Old candidate',
                         'job_id': self.role_both.job_id.id,
                         'company_id': self.company.id,
                         'employee_id': self.mover.id})
        got = self.env['pb.me.home'].with_user(self.share).get_my_requests(self.mover)
        self.assertFalse([r for r in got['rows'] if r['key'] == 'pbhi_internal_role'])

    # B11 — "fits another role" keeps who they are
    def test_b11_copy_keeps_the_person(self):
        app = self._apply()
        copy = app._pb_move_role(self.role_staff.job_id.id)
        self.assertTrue(copy.pb_internal)
        self.assertEqual(copy.employee_id, self.mover)

    # B12 — staff-only roles never reach the careers page
    def test_b12_staff_only_off_careers_page(self):
        website = self.env['website'].sudo().search(
            [('company_id', '=', self.company.id)], limit=1) \
            or self.env['website'].sudo().search([], limit=1)
        job = self.role_both.job_id
        job.sudo().write({'website_published': True,
                          'website_id': website.id if website else False})
        self.role_both.sudo().write({'published': True})
        if website and website.company_id == job.company_id:
            self.assertTrue(job.pb_hiring_accepts_applications(website))
        self.role_both.sudo().write({'pb_staff_posting': 'staff'})
        self.assertFalse(job.website_published, 'B12: taken off the careers page')
        self.assertFalse(self.role_both.published)
        if website:
            self.assertFalse(job.pb_hiring_accepts_applications(website))
        with self.assertRaises(UserError):
            self.env['pb.hiring.posting'].publish_for(self.role_both.id)

    # B13 — the retention clean-up never takes a staff application
    def test_b13_retention_never_takes_staff(self):
        app = self._apply()
        app.write({'stage_id': stage(self.env, 'cv_reject').id})
        self.assertEqual(app._pb_retention_protected(), 'hired')

    # B14 — Staff moves: the hiring team only
    def test_b14_staff_moves_gate(self):
        self._apply()
        Board = self.env['pb.hiring.internal']
        self.assertFalse(Board.with_user(self.manager_user).can_open())
        with self.assertRaises(AccessError):
            Board.with_user(self.manager_user).set_posting(self.role_outside.id, 'both')
        with self.assertRaises(AccessError):
            Board.with_user(self.share).get_board()
        data = Board.with_user(self.recruiter).get_board()
        names = [a['name'] for a in data['applications']]
        self.assertIn('DEMO S6B Mover', names)
        self.assertFalse(data['applications'][0]['manager_told_on'])
        Board.with_user(self.recruiter).set_posting(self.role_outside.id, 'staff')
        self.assertEqual(self.role_outside.pb_staff_posting, 'staff')
        with self.assertRaises(UserError):
            Board.with_user(self.recruiter).set_posting(self.role_outside.id, 'everybody')
