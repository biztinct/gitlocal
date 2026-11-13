# -*- coding: utf-8 -*-
"""RECRUIT P3 — roles without friction: the handover's numbered cases 1–11.

Each test is named for the promise it keeps, and the docstring says which
test case (§5) it is. The route is laid on a company made for the test, with
its own Head of HR, so the engine path is deterministic on any database (a
live company may have chosen "No approval needed" for hiring requests, which
is its right and not what these tests are about).
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from .test_hiring import _src


class P3Case(TransactionCase):
    """A fresh company with the new route, a Head of HR, a recruiter, a
    talent lead, a department and a manager (with an internal login)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.co = env['res.company'].create({'name': 'P3 Test Company',
                                            'email': 'hiring@p3test.example'})
        Users = env['res.users'].with_context(no_reset_password=True)

        def user(login, groups):
            return Users.create({
                'name': login.split('@')[0].replace('.', ' ').title(),
                'login': login, 'email': login,
                'company_id': cls.co.id, 'company_ids': [(6, 0, [cls.co.id])],
                'group_ids': [(6, 0, [env.ref(g).id for g in groups])],
            })
        cls.recruiter = user('p3.recruiter@example.com',
                             ['base.group_user', 'pb_hiring.group_hiring_user'])
        cls.lead = user('p3.lead@example.com',
                        ['base.group_user', 'pb_hiring.group_hiring_manager'])
        cls.hr = user('p3.hr@example.com', ['base.group_user'])
        cls.boss_user = user('p3.budi@example.com', ['base.group_user'])
        cls.stranger = user('p3.stranger@example.com', ['base.group_user'])
        Emp = env['hr.employee'].sudo()
        cls.manager = Emp.create({'name': 'Budi Santoso', 'company_id': cls.co.id,
                                  'user_id': cls.boss_user.id,
                                  'work_email': 'p3.budi@example.com'})
        cls.head = Emp.create({'name': 'Stranger Head', 'company_id': cls.co.id,
                               'user_id': cls.stranger.id})
        cls.dept = env['hr.department'].sudo().create({
            'name': 'P3 Sales', 'company_id': cls.co.id,
            'manager_id': cls.head.id})
        cls.country = env.ref('base.id')
        Req = env['pb.hiring.requisition']
        # the route, and who holds the Head of HR seat
        role = env['biz.approval.role'].sudo().search([('key', '=', 'hr_lead')],
                                                      limit=1)
        Resp = env['biz.approval.responsibility'].sudo().with_context(
            active_test=False)
        held = Resp.search([('company_id', '=', cls.co.id),
                            ('role_id', '=', role.id), ('scope_key', '=', '')])
        if held:
            held.write({'user_id': cls.hr.id, 'backup_user_id': False,
                        'active': True})
        else:
            Resp.create({
                'company_id': cls.co.id, 'role_id': role.id, 'scope_key': '',
                'scope_label': cls.co.name, 'user_id': cls.hr.id,
                'date_from': fields.Date.today() - timedelta(days=1)})
        Req._approval_seed_default(cls.co)

    def _role(self, **extra):
        vals = {'title': 'Territory Manager', 'department_id': self.dept.id,
                'company_id': self.co.id, 'country_id': self.country.id,
                'headcount': 1}
        vals.update(extra)
        return self.env['pb.hiring.requisition'].sudo().create(vals)

    def _complete(self, req, **extra):
        vals = {'reporting_manager_id': self.manager.id, 'budget_cost': 100.0,
                'pb_target_close_date': fields.Date.today() + timedelta(days=30),
                'requirements': 'Grow the territory.', 'location': 'Jakarta',
                'pb_role_level': 'Senior'}
        vals.update(extra)
        req.sudo().write(vals)
        return req

    def _facade(self, user):
        return self.env['pb.hiring'].with_user(user).with_company(self.co)


# =========================================================================
#  1. The migration
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestTheMigration(TransactionCase):

    def test_every_old_state_pair_maps_as_the_handover_says(self):
        """Case 1: draft → setup/writing … refused → setup/not_approved."""
        import importlib.util
        from odoo.modules.module import get_module_path
        path = get_module_path('pb_hiring') + \
            '/migrations/19.0.2.2.0/post-10_request_facet.py'
        spec = importlib.util.spec_from_file_location('p3mig', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.MAP['draft'], ('setup', 'writing'))
        self.assertEqual(mod.MAP['submitted'], ('setup', 'sent_in'))
        self.assertEqual(mod.MAP['manager_ok'], ('setup', 'sent_in'))
        self.assertEqual(mod.MAP['hr_ok'], ('setup', 'hr_ok'))
        self.assertEqual(mod.MAP['open'], ('open', 'agreed'))
        self.assertEqual(mod.MAP['filled'], ('filled', 'agreed'))
        self.assertEqual(mod.MAP['refused'], ('setup', 'not_approved'))
        # and it really runs the mapping on a row carrying an old status
        req = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'Old one', 'department_id': self.env['hr.department']
            .sudo().create({'name': 'P3 Mig'}).id})
        self.env.flush_all()
        cr = self.env.cr
        cr.execute("ALTER TABLE pb_hiring_requisition ADD COLUMN IF NOT EXISTS "
                   "pb_p3_old_state varchar")
        cr.execute("UPDATE pb_hiring_requisition SET pb_p3_old_state = NULL")
        cr.execute("UPDATE pb_hiring_requisition SET pb_p3_old_state = 'open', "
                   "opened_on = now() WHERE id = %s", (req.id,))
        mod._map_states(cr)
        req.invalidate_recordset()
        self.assertEqual((req.state, req.request_state), ('open', 'agreed'))
        self.assertTrue(req.agreed_on)

    def test_the_hiring_jd_route_is_retired(self):
        """Case 1/8: no route is registered for adverts any more."""
        from odoo.addons.biz_approval_workflow.models.chain_shim import (
            CHAIN_PROCESS_KEYS)
        self.assertNotIn('pb.hiring.jd', CHAIN_PROCESS_KEYS)
        spec = CHAIN_PROCESS_KEYS['pb.hiring.requisition']
        self.assertEqual(spec['state_field'], 'request_state')
        self.assertEqual(spec['submit_state'], 'sent_in')
        self.assertEqual(spec['driven'], ('hr_ok', 'agreed'))

    def test_the_route_has_no_finance_step(self):
        """Case 1/6: one Head of HR step; the named approver only when set."""
        from odoo.addons.pb_hiring.models.requisition_approval import (
            hiring_route)
        steps = hiring_route()['steps']
        self.assertEqual([s['key'] for s in steps], ['hr', 'mgr'])
        self.assertEqual(steps[0]['who']['role'], 'hr_lead')
        self.assertIsNone(steps[0]['condition'])
        self.assertEqual(steps[1]['condition']['fact'], 'named_approver')
        self.assertFalse(any((s.get('who') or {}).get('role') == 'finance'
                             for s in steps))

    def test_the_customer_name_is_gone_from_the_seed(self):
        src = _src('models', 'journey.py')
        self.assertNotIn('Dhruv', src)


# =========================================================================
#  2. Open a role
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestOpenARole(P3Case):

    def test_open_a_role_is_setup_with_no_request_and_its_defaults(self):
        """Case 2: five fields make a role; stages and form pre-filled."""
        res = self._facade(self.recruiter)._act_new_role({
            'title': 'Field Officer', 'department_id': self.dept.id,
            'country_id': self.country.id, 'headcount': 2})
        req = self.env['pb.hiring.requisition'].browse(res['id'])
        self.assertEqual((req.state, req.request_state), ('setup', 'none'))
        self.assertTrue(req.pb_visible_stage_ids, 'stages pre-filled')
        self.assertTrue(req.pb_form_id, 'application form pre-filled')

    def test_open_for_candidates_needs_no_request(self):
        """Case 2: job made, recruiter by country, referrals opened."""
        self.env['pb.hiring.country.rule'].sudo().create({
            'company_id': self.co.id, 'country_id': self.country.id,
            'recruiter_id': self.recruiter.id})
        req = self._role()
        self.assertEqual(req.recruiter_id, self.recruiter,
                         'the rule names the recruiter at creation (G-16)')
        self._facade(self.recruiter)._act_open_role({'requisition_id': req.id})
        self.assertEqual(req.state, 'open')
        self.assertEqual(req.request_state, 'none')
        self.assertTrue(req.job_id)
        self.assertTrue(req.referral_open)

    def test_a_confidential_role_does_not_open_to_referrals(self):
        req = self._role(is_confidential=True)
        req._open_for_candidates()
        self.assertFalse(req.referral_open)

    def test_publishing_a_role_being_set_up_opens_it_and_writes_the_advert(self):
        """No dead end: Publish on a new role opens it and writes the advert
        from the family template."""
        from odoo.addons.pb_hiring.models.requests_p3 import seed_p3
        seed_p3(self.env)
        req = self._role()
        self.env['pb.hiring.posting'].with_user(self.recruiter).with_company(
            self.co).publish_for(req.id)
        self.assertEqual(req.state, 'open')
        self.assertTrue(req.published)
        self.assertEqual(req.jd_current_id.state, 'final')
        self.assertIn('Sales', req.jd_current_id.template_id.name or 'Sales')


# =========================================================================
#  3. Ask a manager, the page, send in
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestAskAManager(P3Case):

    def test_asking_mints_a_token_mails_from_the_sender_and_leaves_a_todo(self):
        """Case 3."""
        req = self._role()
        Mail = self.env['mail.mail'].sudo()
        before = Mail.search([]).ids
        res = self._facade(self.recruiter)._act_ask_manager({
            'requisition_id': req.id, 'employee_id': self.manager.id,
            'message': 'Please by Friday'})
        self.assertIn('email', res['note'])
        self.assertEqual(req.request_state, 'asked')
        self.assertTrue(req.sudo().request_token)
        self.assertEqual(req.asked_user_id, self.boss_user)
        mail = Mail.search([('id', 'not in', before),
                            ('email_to', '=', 'p3.budi@example.com')])
        self.assertTrue(mail, 'the ask went out')
        self.assertIn('hiring@p3test.example', mail[0].email_from)
        self.assertIn('/hiring/r/', mail[0].body_html)
        todo = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'pb.hiring.requisition'),
            ('res_id', '=', req.id), ('user_id', '=', self.boss_user.id)])
        self.assertTrue(todo)

    def test_autosave_writes_only_whitelisted_fields(self):
        req = self._role()
        req._ask(self.manager)
        req._page_save({'location': 'Surabaya', 'headcount': '3',
                        'budget_cost': '120,000', 'recruiter_id': 1,
                        'state': 'open', 'focus_1': 'Territory planning'})
        self.assertEqual(req.location, 'Surabaya')
        self.assertEqual(req.headcount, 3)
        self.assertEqual(req.budget_cost, 120000.0)
        self.assertEqual(req.state, 'setup', 'status is never page-writable')
        self.assertEqual(req.request_state, 'writing')
        self.assertIn('Territory planning', req.step_ids.mapped('notes'))

    def test_send_in_with_a_missing_answer_names_it(self):
        req = self._role()
        req._ask(self.manager)
        with self.assertRaises(UserError) as err:
            req.with_user(self.boss_user).sudo()._request_send_in(
                by_employee=self.manager)
        self.assertIn('who they would report to', str(err.exception))
        self.assertIn('expected budget', str(err.exception))

    def test_send_in_is_the_managers_agreement_and_starts_the_route(self):
        """Case 3: sent_in + manager agreement + route + recruiter."""
        self.env['pb.hiring.country.rule'].sudo().create({
            'company_id': self.co.id, 'recruiter_id': self.recruiter.id})
        req = self._complete(self._role(country_id=False))
        req.sudo().write({'recruiter_id': False, 'country_id': self.country.id})
        req._ask(self.manager)
        req.with_user(self.boss_user).sudo()._request_send_in(
            by_employee=self.manager)
        self.assertEqual(req.request_state, 'sent_in')
        self.assertEqual(req.manager_agreed_by_id, self.manager)
        self.assertTrue(req.manager_agreed_on)
        self.assertTrue(req.approval_request_id, 'the route started')
        self.assertIn(self.hr, req.sudo().seat_user_ids,
                      'the Head of HR holds the seat')
        self.assertEqual(req.recruiter_id, self.recruiter,
                         'recruiter assigned on send-in (G-16)')

    def test_a_portal_manager_is_asked_and_sends_in_without_a_login_hunt(self):
        """A line manager may be a PORTAL user (P3 non-negotiable)."""
        portal = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Portal Manager', 'login': 'p3.portal@example.com',
                'email': 'p3.portal@example.com', 'company_id': self.co.id,
                'company_ids': [(6, 0, [self.co.id])],
                'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        emp = self.env['hr.employee'].sudo().create({
            'name': 'Portal Manager', 'company_id': self.co.id,
            'user_id': portal.id})
        req = self._complete(self._role())
        out = req._ask(emp)
        self.assertTrue(out['mailed'])
        req.with_user(portal).sudo()._request_send_in(by_employee=emp)
        self.assertEqual(req.request_state, 'sent_in')
        self.assertEqual(req.manager_agreed_by_id, emp)

    def test_nobody_can_write_the_request_status_by_hand(self):
        """The one gate reads `request_state`; only the system writes it."""
        req = self._role()
        with self.assertRaises(AccessError):
            req.with_user(self.recruiter).with_context(
                biz_chain_engine_write=True).write({'request_state': 'agreed'})


@tagged('post_install', '-at_install', 'recruit_p3')
class TestTheRequestPage(HttpCase, P3Case):

    def test_the_token_page_renders_saves_and_refuses_a_stranger(self):
        """Case 3 over HTTP: the page renders, autosave writes, a wrong key
        reads "closed"."""
        req = self._role()
        req._ask(self.manager)
        token = req.sudo().request_token
        self.env.flush_all()
        page = self.url_open('/hiring/r/%s' % token)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Send in', page.text)
        self.assertIn('Territory Manager', page.text)
        res = self.url_open('/hiring/r/%s/save' % token,
                            data='{"location": "Medan"}',
                            headers={'Content-Type': 'application/json'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['ok'])
        req.invalidate_recordset()
        self.assertEqual(req.location, 'Medan')
        bad = self.url_open('/hiring/r/%s' % ('x' * 32))
        self.assertIn('This link has closed', bad.text)


# =========================================================================
#  4. Reminders and escalation
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestReminders(P3Case):

    def _aged(self, req, days, reminded=None):
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE pb_hiring_requisition SET asked_on = now() - %s * "
            "interval '1 day', last_reminded_on = %s WHERE id = %s",
            (days, reminded, req.id))
        self.env.invalidate_all()

    def test_working_days_skip_the_weekend(self):
        Req = self.env['pb.hiring.requisition']
        friday = fields.Datetime.to_datetime('2026-10-02 09:00:00')
        monday = fields.Datetime.to_datetime('2026-10-05 09:00:00')
        self.co.sudo().resource_calendar_id = False
        self.assertEqual(Req._working_days_between(self.co, friday, monday), 1)

    def test_the_cadence_escalation_and_the_stop(self):
        """Case 4: a reminder on the cadence; the talent lead told after
        three working days; nothing after send-in."""
        req = self._complete(self._role())
        req._ask(self.manager)
        Auto = self.env['pb.hiring.automation']
        # Counted on THIS role only: other roles on the database may be due.
        Auto._remind_requests()
        self.assertEqual(req.remind_count, 0, 'not due yet')
        self._aged(req, 7)
        Auto._remind_requests()
        self.assertEqual(req.remind_count, 1)
        Auto._escalate_requests()
        self.assertTrue(req.escalated_on)
        todo = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'pb.hiring.requisition'), ('res_id', '=', req.id),
            ('user_id', '=', self.lead.id)])
        self.assertEqual(len(todo), 1, 'the talent lead has the to-do')
        Auto._escalate_requests()
        self.assertEqual(len(self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'pb.hiring.requisition'), ('res_id', '=', req.id),
            ('user_id', '=', self.lead.id)])), 1, 'once only')
        req.with_user(self.boss_user).sudo()._request_send_in(
            by_employee=self.manager)
        self._aged(req, 14)
        Auto._remind_requests()
        self.assertEqual(req.remind_count, 1, 'stops after send-in')

    def test_remind_now_never_twice_in_an_hour(self):
        req = self._role()
        req._ask(self.manager)
        f = self._facade(self.recruiter)
        f._act_remind_now({'requisition_id': req.id})
        with self.assertRaises(UserError):
            f._act_remind_now({'requisition_id': req.id})


# =========================================================================
#  5. Budget
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestBudget(P3Case):

    def test_over_the_confirmed_figure_tells_the_people_and_blocks_nothing(self):
        """Case 5."""
        self.co.sudo().pb_budget_flag_user_ids = [(6, 0, [self.lead.id])]
        req = self._complete(self._role(), budget_cost=150.0,
                             budget_confirmed=100.0)
        req._refresh_budget()
        self.assertEqual(req.budget_status, 'over')
        req._ask(self.manager)
        req.with_user(self.boss_user).sudo()._request_send_in(
            by_employee=self.manager)
        self.assertEqual(req.request_state, 'sent_in', 'nothing blocked')
        todo = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'pb.hiring.requisition'), ('res_id', '=', req.id),
            ('user_id', '=', self.lead.id), ('summary', 'ilike', 'Over budget')])
        self.assertTrue(todo)
        sig = req.budget_flag_sig
        req._flag_budget()
        self.assertEqual(req.budget_flag_sig, sig, 'no second flag unchanged')
        req.sudo().write({'budget_cost': 170.0})
        self.assertNotEqual(req.budget_flag_sig, sig, 're-flagged on a change')

    def test_nobody_named_says_so_and_tells_the_head_of_hiring(self):
        self.co.sudo().pb_budget_flag_user_ids = [(5,)]
        admin = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'P3 Head of hiring', 'login': 'p3.hoh@example.com',
                'company_id': self.co.id, 'company_ids': [(6, 0, [self.co.id])],
                'group_ids': [(6, 0, [self.env.ref(
                    'pb_hiring.group_hiring_admin').id])]})
        req = self._complete(self._role(), budget_cost=150.0,
                             budget_confirmed=100.0)
        req._refresh_budget()
        req._ask(self.manager)
        req.with_user(self.boss_user).sudo()._request_send_in(
            by_employee=self.manager)
        bodies = ' '.join(req.message_ids.mapped('body'))
        self.assertIn('Nobody is set to be told about over-budget requests',
                      bodies)
        self.assertTrue(self.env['mail.activity'].sudo().search_count([
            ('res_id', '=', req.id), ('user_id', '=', admin.id),
            ('res_model', '=', 'pb.hiring.requisition')]))

    def test_the_page_says_the_gentle_sentence(self):
        req = self._complete(self._role(), budget_cost=150.0,
                             budget_confirmed=100.0)
        req._refresh_budget()
        tone, note = req._page_budget_note()
        self.assertEqual(tone, 'over')
        self.assertIn('Nothing stops', note)
        req.sudo().write({'budget_confirmed': 0, 'department_id': self.dept.id})
        req._refresh_budget()
        tone, note = req._page_budget_note()
        self.assertIn('No budget to compare with', note)


# =========================================================================
#  6. The route
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestTheRoute(P3Case):

    def _sent(self):
        req = self._complete(self._role())
        req._ask(self.manager)
        req.with_user(self.boss_user).sudo()._request_send_in(
            by_employee=self.manager)
        return req

    def test_the_head_of_hr_agrees_and_it_is_agreed(self):
        """Case 6."""
        req = self._sent()
        self._facade(self.hr)._act_request_agree({'requisition_id': req.id})
        req.invalidate_recordset()
        self.assertEqual(req.request_state, 'agreed')
        self.assertTrue(req.agreed_on)
        self.assertEqual(req._offer_block_reason(), '')

    def test_not_approved_keeps_the_reason_and_the_role(self):
        req = self._sent()
        req._open_for_candidates()
        self._facade(self.hr)._act_request_decline(
            {'requisition_id': req.id, 'note': 'Not this quarter'})
        req.invalidate_recordset()
        self.assertEqual(req.request_state, 'not_approved')
        self.assertEqual(req.not_approved_reason, 'Not this quarter')
        self.assertEqual(req.state, 'open', 'the role stays usable')

    def test_somebody_without_the_seat_cannot_agree(self):
        req = self._sent()
        with self.assertRaises(Exception):
            self._facade(self.stranger)._act_request_agree(
                {'requisition_id': req.id})

    def test_a_named_approver_adds_a_second_step(self):
        self.co.sudo().pb_mr_approver_id = self.lead
        req = self._sent()
        self._facade(self.hr)._act_request_agree({'requisition_id': req.id})
        req.invalidate_recordset()
        self.assertEqual(req.request_state, 'hr_ok')
        self.assertIn('Ask %s' % self.lead.name, req._offer_block_reason())
        self._facade(self.lead)._act_request_agree({'requisition_id': req.id})
        req.invalidate_recordset()
        self.assertEqual(req.request_state, 'agreed')


# =========================================================================
#  7. The offer rule, checks, papers
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestTheOfferRule(P3Case):

    def _picked(self, req):
        req._open_for_candidates()
        app = self.env['hr.applicant'].sudo().create({
            'partner_name': 'Nguyen Thi Lan', 'email_from': 'p3.lan@example.com',
            'job_id': req.job_id.id, 'pb_requisition_id': req.id,
            'company_id': self.co.id})
        req.sudo().write({'selected_applicant_id': app.id})
        return app

    def test_draft_without_a_check_and_the_sentence_with_names(self):
        """Case 7: drafting needs no background check; sending refuses with
        the names until the request is agreed; then it goes."""
        req = self._complete(self._role())
        self._picked(req)
        offer = self.env['pb.hiring.offer'].draft_for(req.id)
        self.assertTrue(offer, 'drafted with the check still open')
        offer.sudo()._chain_state_write('hr_ok')
        with self.assertRaises(UserError) as err:
            offer.action_send_to_candidate()
        self.assertIn('no agreed hiring request', str(err.exception))
        req._ask(self.manager)
        req.with_user(self.boss_user).sudo()._request_send_in(
            by_employee=self.manager)
        with self.assertRaises(UserError) as err:
            offer.action_send_to_candidate()
        self.assertIn(self.hr.name, str(err.exception))
        self.assertIn('press Agree', str(err.exception))
        self._facade(self.hr)._act_request_agree({'requisition_id': req.id})
        # the letter is the A3 machinery's business; give it one ready
        offer.sudo().attachment_id = self.env['ir.attachment'].sudo().create(
            {'name': 'offer.pdf', 'raw': b'%PDF-1.4', 'mimetype':
             'application/pdf'})
        offer.action_send_to_candidate()
        self.assertEqual(offer.state, 'sent', 'papers never gate the send')

    def test_the_papers_go_at_the_moment_chosen(self):
        req = self._complete(self._role())
        self._picked(req)
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('pb_hiring.docreq_trigger', 'before_offer')
        offer = self.env['pb.hiring.offer'].draft_for(req.id)
        self.assertTrue(offer.docreq_id.sent_on, 'asked when drafted')

    def test_the_papers_wait_for_a_clear_check_by_default(self):
        req = self._complete(self._role())
        self._picked(req)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_hiring.docreq_trigger', 'on_check_clear')
        offer = self.env['pb.hiring.offer'].draft_for(req.id)
        self.assertFalse(offer.docreq_id.sent_on if offer.docreq_id else False)
        for item in offer.bgv_id.item_ids:
            item.action_set('ok')
        offer.invalidate_recordset()
        self.assertTrue(offer.docreq_id.sent_on, 'asked on a clear check')

    def test_an_adverse_result_tells_the_head_of_hr_once(self):
        req = self._complete(self._role())
        self._picked(req)
        offer = self.env['pb.hiring.offer'].draft_for(req.id)
        item = offer.bgv_id.item_ids[:1]
        item.action_set('flag', note='Dates do not match')
        item.action_set('flag', note='Still wrong')
        todos = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'pb.hiring.requisition'), ('res_id', '=', req.id),
            ('user_id', '=', self.hr.id), ('summary', 'ilike', 'Background')])
        self.assertEqual(len(todos), 1)


# =========================================================================
#  8. The advert
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestTheAdvert(P3Case):

    def test_share_comment_final(self):
        """Case 8: share mails + token page; a comment lands on the timeline
        and as a to-do; final versions and pushes the advert text."""
        from odoo.addons.pb_hiring.models.requests_p3 import seed_p3
        seed_p3(self.env)
        tpls = self.env['pb.hiring.jd.template'].sudo().search(
            [('company_id', '=', self.co.id)])
        self.assertEqual(len(tpls), 4, 'four templates per company')
        req = self._role(recruiter_id=self.recruiter.id)
        req._open_for_candidates()
        f = self._facade(self.recruiter)
        res = f._act_jd_from_template({'requisition_id': req.id,
                                       'template_id': tpls[0].id})
        jd = self.env['pb.hiring.jd'].browse(res['jd_id'])
        self.assertEqual(jd.state, 'draft')
        req.sudo().asked_employee_id = self.manager
        f._act_share_jd({'jd_id': jd.id})
        self.assertTrue(jd.sudo().share_token)
        self.assertEqual(jd.shared_with_id, self.manager)
        jd.sudo()._receive_comment('Mention the motorbike', name='Budi')
        self.assertIn('Mention the motorbike', jd.comment_ids.body)
        self.assertTrue(self.env['mail.activity'].sudo().search_count([
            ('res_model', '=', 'pb.hiring.requisition'), ('res_id', '=', req.id),
            ('user_id', '=', self.recruiter.id)]))
        f._act_make_final({'jd_id': jd.id})
        self.assertEqual(jd.state, 'final')
        self.assertEqual(req.jd_current_id, jd)
        self.assertEqual(req.job_id.sudo().website_description, jd.body)


# =========================================================================
#  9. Confidential
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestConfidential(P3Case):

    def test_hidden_from_referrals_careers_lists_and_outsiders(self):
        """Case 9."""
        req = self._role(requested_by_id=self.manager.id)
        req._open_for_candidates()
        self.assertTrue(req.referral_open)
        self._facade(self.recruiter)._act_set_confidential(
            {'requisition_id': req.id, 'on': True})
        self.assertFalse(req.referral_open)
        website = self.env['website'].sudo().search([], limit=1)
        if website:
            self.assertFalse(req.job_id.pb_hiring_accepts_applications(website))
        self.assertNotIn(req.job_id.id, [j['id'] for j in self.env[
            'hr.applicant'].pb_open_jobs([self.co.id])])
        with self.assertRaises(UserError):
            self.env['pb.hiring.referral'].sudo().refer(
                req.id, self.head.id, {'name': 'x'})
        Req = self.env['pb.hiring.requisition']
        # the department's head is not the person it is for
        self.assertFalse(Req.with_user(self.stranger).with_company(
            self.co).search([('id', '=', req.id)]))
        # the person it is for still sees it
        self.assertTrue(Req.with_user(self.boss_user).with_company(
            self.co).search([('id', '=', req.id)]))
        with self.assertRaises(UserError):
            self.env['pb.hiring.posting'].publish_for(req.id)


# =========================================================================
#  10. The sender
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestTheSender(P3Case):

    def test_every_hiring_template_sends_from_the_hiring_sender(self):
        """Case 10: never empty, even when the acting user has no email."""
        data = self.env['ir.model.data'].sudo().search(
            [('module', '=', 'pb_hiring'), ('model', '=', 'mail.template')])
        templates = self.env['mail.template'].sudo().browse(data.mapped('res_id'))
        self.assertTrue(templates)
        for tpl in templates:
            self.assertIn('pb_hiring_sender', tpl.email_from or '',
                          '%s does not use the hiring sender' % tpl.name)
        nomail = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'No Mail', 'login': 'p3.nomail', 'company_id': self.co.id,
                'company_ids': [(6, 0, [self.co.id])],
                'group_ids': [(6, 0, [self.env.ref(
                    'pb_hiring.group_hiring_user').id])]})
        req = self._role()
        tpl = self.env.ref('pb_hiring.mail_template_request_ask')
        rendered = tpl.with_user(nomail).sudo()._render_field(
            'email_from', req.ids)[req.id]
        self.assertIn('hiring@p3test.example', rendered)

    def test_the_parameter_wins(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_hiring.sender', 'talent@p3test.example')
        self.assertIn('talent@p3test.example',
                      self.env['pb.hiring']._sender(self.co))


# =========================================================================
#  11 and the board payload
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p3')
class TestTheBoardPayload(P3Case):

    def test_the_row_and_the_role_page_carry_the_request(self):
        req = self._role()
        req._ask(self.manager)
        f = self._facade(self.recruiter)
        row = f._row(req)
        self.assertEqual(row['request_state'], 'asked')
        self.assertEqual(row['request_label'], 'Waiting on Budi Santoso')
        self.assertTrue(row['offer_block_reason'])
        self.assertFalse(row['can_send_offer'])
        full = f.get_requisition(req.id)
        self.assertTrue(full['request']['can_remind'])
        self.assertEqual(full['request']['asked']['name'], 'Budi Santoso')
        self.assertTrue(full['advert']['templates'] is not None)

    def test_setup_gives_who_does_what(self):
        res = self._facade(self.lead).get_setup()
        self.assertIn('who', res)
        self.assertIn('docreq_triggers', res['who'])
        self._facade(self.lead)._act_set_budget_people(
            {'user_ids': [self.hr.id]})
        self.assertEqual(self.co.sudo().pb_budget_flag_user_ids, self.hr)
