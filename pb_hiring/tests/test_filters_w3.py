# -*- coding: utf-8 -*-
"""FILTER wave 3 — the four Hiring lists on the shared filter panel.

What is checked: every list answers the kit (layout, counts with no failed
section, a page), the counts and the pages agree with each other, the steps
add up, the Overview's offer figures equal the Offers views, and a reader
outside the hiring team is offered nothing the privacy mask hides from them.

Every assertion is scoped to the records this case makes where the database
may hold other people's.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .test_interviews import InterviewCase


@tagged('post_install', '-at_install', 'filter_w3')
class TestFiltersW3(InterviewCase):

    def setUp(self):
        super().setUp()
        self.facade = self.env['pb.hiring']
        self.Stage = self.env['hr.recruitment.stage']
        self.dept2 = self.env['hr.department'].create({
            'name': 'FILTER W3 Elsewhere', 'company_id': self.company.id})
        self.req2 = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'FILTER W3 Second role', 'department_id': self.dept2.id,
            'company_id': self.company.id, 'requested_by_id': self.boss.id,
            'recruiter_id': self.recruiter.id, 'headcount': 2,
            'requirements': 'Able to do the job.'})
        self.req2._chain_state_write('open')
        self.req2._on_opened()
        self.people = self.env['hr.applicant'].sudo()
        for i, (req, key) in enumerate(((self.req, 'shortlist'), (self.req2, 'screening'),
                                        (self.req2, 'cv_reject'))):
            app = self.env['hr.applicant'].sudo().create({
                'partner_name': 'FILTER W3 Person %s' % i,
                'email_from': 'filter.w3.%s@example.com' % i,
                'job_id': req.job_id.id, 'company_id': self.company.id,
                'pb_requisition_id': req.id})
            app.write({'stage_id': self.Stage._pb_stage(key).id})
            self.people |= app

    # ------------------------------------------------------------- helpers
    def _kind(self, kind, user=None):
        f = self.facade.with_user(user) if user else self.facade
        return f.with_context(pbf_ctx={'kind': kind})

    def _line_manager(self):
        user = self.env['res.users'].sudo().create({
            'name': 'FILTER W3 Line Manager',
            'login': 'filter.w3.lm.%s' % fields.Datetime.now().timestamp(),
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('base.group_user').id)]})
        self.head.sudo().write({'user_id': user.id})
        return user

    def _no_failed_section(self, me):
        counts = me.pbf_counts({}, '', None)
        failed = [k for k, v in counts['sections'].items() if v.get('error')]
        self.assertFalse(failed, 'sections that could not be counted: %s' % failed)
        return counts

    # ---------------------------------------------------------------- 1
    def test_01_every_list_answers_the_kit(self):
        for kind, first in (('roles', 'all'), ('interviews', 'all'),
                            ('applicants', 'all'), ('offers', 'all')):
            me = self._kind(kind)
            layout = me.pbf_layout()
            self.assertNotIn('refused', layout)
            self.assertEqual(layout['screen'], 'hiring:%s' % kind)
            self.assertEqual(layout['views'][0]['key'], first)
            pinned = [s['key'] for s in layout['sections'] if s.get('pinned')]
            self.assertLessEqual(len(pinned), 3, '%s pins more than three sections' % kind)
            counts = self._no_failed_section(me)
            self.assertEqual(counts['matched'], layout['total'])

    def test_02_roles_page_steps_add_up_and_filters_narrow(self):
        f = self.facade
        page = f.get_roles_page({}, '', 'attention', 0, 500)
        self.assertTrue(page['allowed'])
        ids = [r['id'] for r in page['rows']]
        self.assertIn(self.req.id, ids)
        self.assertIn(self.req2.id, ids)
        self.assertEqual(len(ids), len(set(ids)), 'the attention order repeats a role')
        me = self._kind('roles')
        Req = self.env['pb.hiring.requisition']
        live = Req.search_count(me.pbf_domain({'status': ['setup', 'open', 'filled']}, ''))
        self.assertEqual(sum(page['steps'].values()), live,
                         'a role is at exactly one step, so the steps add up')
        only = f.get_roles_page({'department': [self.dept2.id]}, '', None, 0, 500)
        self.assertIn(self.req2.id, [r['id'] for r in only['rows']])
        self.assertNotIn(self.req.id, [r['id'] for r in only['rows']])
        self.assertTrue(all(r['department_id'] == self.dept2.id for r in only['rows']))
        found = f.get_roles_page({}, 'FILTER W3 Second', None, 0, 50)
        self.assertEqual([r['id'] for r in found['rows']], [self.req2.id])
        # the page and the kit agree on how many there are
        self.assertEqual(only['total'], me.pbf_counts({'department': [self.dept2.id]}, '')['matched'])

    def test_03_applicants_page_is_the_register_cards_in_the_panel_order(self):
        f = self.facade
        page = f.get_applicants_page({}, 'FILTER W3 Person', 'name', 0, 120)
        self.assertEqual([c['id'] for c in page['cards']], self.people.sorted('partner_name').ids)
        for c in page['cards']:
            self.assertTrue(c['role'] and c['stage_key'])
        self.assertEqual(sum(col['count'] for col in page['columns']), page['total'])
        closed = f.get_applicants_page({'family': ['closed']}, 'FILTER W3 Person', None, 0, 120)
        self.assertEqual({c['id'] for c in closed['cards']},
                         {a.id for a in self.people if a.stage_id.pb_family == 'closed'})
        two = f.get_applicants_page({'role': [self.req2.id]}, 'FILTER W3 Person', None, 0, 120)
        self.assertTrue(all(c['role_id'] == self.req2.id for c in two['cards']))
        self.assertTrue(page['glance']['team'])

    def test_04_a_line_manager_is_offered_nothing_the_mask_hides(self):
        lm = self._line_manager()
        me = self._kind('applicants', lm)
        keys = {s['key'] for s in me.pbf_layout()['sections']}
        for hidden in ('screen', 'source', 'authorisation', 'applied', 'hold'):
            self.assertNotIn(hidden, keys)
        views = [v['key'] for v in me.pbf_layout()['views']]
        self.assertNotIn('waiting', views)
        self.assertNotIn('dup', views)
        # the email is masked on their cards, so it does not search either
        page = self.facade.with_user(lm).get_applicants_page({}, 'filter.w3.0@example', None, 0, 50)
        self.assertEqual(page['total'], 0)
        page = self.facade.with_user(lm).get_applicants_page({}, '', None, 0, 200)
        self.assertNotIn(self.req2.id, {c['role_id'] for c in page['cards']},
                         'a role that is not theirs leaked')
        self.assertFalse(page['glance']['team'])
        offers = {s['key'] for s in self._kind('offers', lm).pbf_layout()['sections']}
        self.assertFalse({'docs', 'check', 'monthly'} & offers)
        roles = {s['key'] for s in self._kind('roles', lm).pbf_layout()['sections']}
        self.assertNotIn('budget', roles)

    def test_05_overview_offer_figures_equal_the_offers_views(self):
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.docreq_trigger', 'on_accept')
        self.req.sudo().write({'request_state': 'agreed', 'selected_applicant_id': self.applicant.id})
        offer = self.env['pb.hiring.offer'].draft_for(self.req.id)
        today = fields.Date.context_today(self.env.user)
        offer.sudo().write({'state': 'signed', 'expected_join_date': today + timedelta(days=5)})
        kpis = self.facade.get_board()['kpis']
        layout = self._kind('offers').pbf_layout()
        views = {v['key']: v['n'] for v in layout['views']}
        self.assertEqual(kpis['joining_soon'], views['joining'])
        self.assertGreaterEqual(views['joining'], 1)
        self.assertEqual(kpis['joined_month'], views['joined'])
        page = self.facade.get_offers_page({'attention': ['joining_soon']}, '', None, 0, 200)
        self.assertIn(offer.id, [r['id'] for r in page['rows']])
        self.assertEqual(page['total'], views['joining'])
        self.assertEqual(sum(page['steps'].values()), page['total'])

    def test_06_interviews_page_and_a_reader_without_hiring_access(self):
        page = self.facade.get_interviews_page({}, '', None, 0, 60)
        self.assertTrue(page['allowed'])
        self.assertEqual(page['total'], self._kind('interviews').pbf_counts({}, '')['matched'])
        stranger = self.env['res.users'].sudo().create({
            'name': 'FILTER W3 Stranger', 'login': 'filter.w3.x.%s' % fields.Datetime.now().timestamp(),
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('base.group_user').id)]})
        me = self._kind('applicants', stranger)
        if not me._can_read():
            self.assertIn('refused', me.pbf_layout())
            self.assertEqual(me.pbf_counts({}, ''), {'sections': {}, 'matched': 0})
            self.assertFalse(self.facade.with_user(stranger).get_applicants_page()['allowed'])
