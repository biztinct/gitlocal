# -*- coding: utf-8 -*-
"""NAV P3a — the Applicants and Offers registers on the Hiring hub.

Numbered as in `docs/handovers/NAV_P3A_HIRING_REGISTERS.md` §5 (tests 1–7;
test 8 is the existing suites, run alongside).

Every assertion is scoped to the two roles this case makes: a test database
may already hold other people's roles, and a register reads all of them.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .test_interviews import InterviewCase


@tagged('post_install', '-at_install', 'nav_p3a')
class TestRegistersP9(InterviewCase):

    def setUp(self):
        super().setUp()
        self.Stage = self.env['hr.recruitment.stage']
        self.facade = self.env['pb.hiring']
        # A second role, in another part of the business, recruited by the
        # same recruiter.
        self.dept2 = self.env['hr.department'].create({
            'name': 'NAV P3a Elsewhere', 'company_id': self.company.id})
        self.req2 = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'NAV P3a Second role', 'department_id': self.dept2.id,
            'company_id': self.company.id, 'requested_by_id': self.boss.id,
            'recruiter_id': self.recruiter.id, 'headcount': 1,
            'requirements': 'Able to do the job.'})
        self.req2._chain_state_write('open')
        self.req2._on_opened()
        self.one = self.env['hr.applicant'].sudo()
        for i, key in enumerate(('shortlist', 'phone')):
            app = self._person('NAV P3a One %s' % i, self.req)
            app.write({'stage_id': self.Stage._pb_stage(key).id})
            self.one |= app
        self.two = self.env['hr.applicant'].sudo()
        for i, key in enumerate(('screening', 'cv_reject')):
            app = self._person('NAV P3a Two %s' % i, self.req2)
            app.write({'stage_id': self.Stage._pb_stage(key).id})
            self.two |= app

    # ------------------------------------------------------------- helpers
    def _person(self, name, req):
        return self.env['hr.applicant'].sudo().create({
            'partner_name': name,
            'email_from': '%s@example.com' % name.lower().replace(' ', '.'),
            'job_id': req.job_id.id, 'company_id': self.company.id,
            'pb_requisition_id': req.id})

    def _ours(self, data):
        mine = (self.req.id, self.req2.id)
        return [c for c in data['cards'] if c['role_id'] in mine]

    def _line_manager(self):
        user = self.env['res.users'].sudo().create({
            'name': 'NAV P3a Line Manager',
            'login': 'nav.p3a.lm.%s' % fields.Datetime.now().timestamp(),
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('base.group_user').id)]})
        self.head.sudo().write({'user_id': user.id})
        return user

    def _offer(self):
        """An offer on role one for the first candidate, the check answered.
        The papers are asked for by hand here (the automatic moment is set to
        the latest one, as test_offer.py does)."""
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_hiring.docreq_trigger', 'on_accept')
        self.req.sudo().write({'request_state': 'agreed',
                               'selected_applicant_id': self.applicant.id})
        bgv = self.env['pb.hiring.bgv'].open_for(self.req.id)
        bgv.item_ids.sudo().write({'result': 'ok'})
        bgv.invalidate_recordset(['state', 'pending_count', 'flag_count'])
        offer = self.env['pb.hiring.offer'].draft_for(self.req.id)
        offer.action_add_line({'name': 'Basic pay', 'kind': 'earning',
                               'amount': 1000.0, 'period': 'monthly'})
        offer.invalidate_recordset(['monthly_total', 'annual_total'])
        return offer

    def _row(self, data, offer):
        rows = [r for r in data['rows'] if r['id'] == offer.id]
        self.assertEqual(len(rows), 1, 'the offer is not on the register')
        return rows[0]

    # ------------------------------------------------------------- test 1
    def test_01_cards_from_two_roles_in_journey_order_and_counts_add_up(self):
        data = self.facade.get_applicants()
        self.assertTrue(data['allowed'])
        cards = self._ours(data)
        self.assertEqual({c['role_id'] for c in cards}, {self.req.id, self.req2.id})
        self.assertEqual(len(cards), 5)
        for c in cards:
            self.assertTrue(c['role'], 'a register card names its role')
            self.assertTrue(c['stage_key'])
            self.assertIn(c['family'], ('open', 'done', 'closed'))
        seqs = [self.Stage.browse(col['id']).sequence for col in data['columns']]
        self.assertEqual(seqs, sorted(seqs), 'the columns are not in journey order')
        self.assertEqual(sum(col['count'] for col in data['columns']), len(data['cards']))
        for req in (self.req, self.req2):
            mine = [c for c in cards if c['role_id'] == req.id and c['active']]
            by_stage = {}
            for c in mine:
                by_stage[c['stage_id']] = by_stage.get(c['stage_id'], 0) + 1
            pipeline = {p['id']: p['count'] for p in self.facade._pipeline(req)}
            self.assertEqual(by_stage, pipeline,
                             'the register disagrees with the role row for %s' % req.title)
        role_ids = {r['id'] for r in data['roles']}
        self.assertTrue({self.req.id, self.req2.id} <= role_ids)

    # ------------------------------------------------------------- test 2
    def test_02_a_requester_sees_only_their_role_and_masked_cards(self):
        lm = self._line_manager()
        data = self.facade.with_user(lm).get_applicants()
        self.assertTrue(data['allowed'])
        role_ids = {c['role_id'] for c in data['cards']}
        self.assertIn(self.req.id, role_ids)
        self.assertNotIn(self.req2.id, role_ids, 'a role that is not theirs leaked')
        self.assertFalse(data['can_move'])
        for c in data['cards']:
            self.assertFalse(c['can_move'])
            self.assertEqual(c['email'], '', 'a masked card carries the email')
            self.assertEqual(c['chips'], [])
            self.assertEqual(c['opinions'], {'in': 0, 'total': 0, 'late': 0})
            self.assertTrue(set(c['flags']) <= {'iv'})
            self.assertTrue(c['name'] and c['stage'])
            self.assertNotIn('salary_expected', c)

    # ------------------------------------------------------------- test 3
    def test_03_filters_and_the_cap(self):
        f = self.facade
        closed = self._ours(f.get_applicants({'family': 'closed'}))
        self.assertEqual([c['id'] for c in closed], [self.two[1].id])
        play = self._ours(f.get_applicants({'family': 'play'}))
        self.assertEqual({c['id'] for c in play},
                         {self.applicant.id, *self.one.ids, self.two[0].id})
        only_two = f.get_applicants({'role_id': self.req2.id})
        self.assertEqual({c['id'] for c in only_two['cards']}, set(self.two.ids))
        by_rec = self._ours(f.get_applicants({'recruiter_id': self.recruiter.id}))
        self.assertEqual(len(by_rec), 5)
        nobody = f.get_applicants({'recruiter_id': self.panel_user.id})
        self.assertFalse([c for c in nobody['cards'] if c['role_id'] in (self.req.id, self.req2.id)])
        # "Waiting on you": a first look still owed (the role page's own words)
        waiting = self._ours(f.get_applicants({'flags': ['waiting_mine']}))
        self.assertTrue(waiting)
        self.assertTrue(all('waiting' in c['flags'] for c in waiting))
        self.assertIn(self.two[0].id, [c['id'] for c in waiting])
        everyone = f.get_applicants()
        self.assertEqual(len(f.get_applicants({'flags': ['waiting_mine']})['cards']),
                         everyone['glance']['waiting_mine'])
        late = f.get_applicants({'late': True})
        self.assertEqual(len(late['cards']), everyone['glance']['opinions_late'])
        hit = f.get_applicants({'q': 'NAV P3a Two 0'})
        self.assertEqual([c['id'] for c in hit['cards']], [self.two[0].id])
        by_role_word = self._ours(f.get_applicants({'q': 'Second role'}))
        self.assertEqual({c['id'] for c in by_role_word}, set(self.two.ids))
        # the cap: the newest N, said as "N of total"
        with patch('odoo.addons.pb_hiring.models.registers_p9.APPLICANTS_CAP', 2):
            capped = f.get_applicants({'role_id': self.req.id})
        self.assertEqual(len(capped['cards']), 2)
        self.assertEqual(capped['total'], 3)
        self.assertTrue(capped['capped'])
        self.assertFalse(f.get_applicants({'role_id': self.req.id})['capped'])

    # ------------------------------------------------------------- test 4
    def test_04_moving_from_the_register_and_the_mixed_refusal(self):
        f = self.facade
        res = f.act('journey_stage', {'applicant_ids': [self.two[0].id],
                                      'key': 'shortlist', 'register': True})
        self.assertEqual(len(res['moved']), 1)
        self.assertEqual(self.two[0].stage_id.pb_key, 'shortlist')
        with self.assertRaises(UserError) as caught:
            f.act('journey_stage', {'applicant_ids': [self.two[0].id],
                                    'key': 'joined', 'register': True})
        self.assertIn('from their offer', str(caught.exception))
        # Role one uses Assignment; role two does not.
        assignment = self.Stage._pb_stage('assignment')
        self.req.sudo().write({'pb_visible_stage_ids': [(4, assignment.id)]})
        self.req2.sudo().write({'pb_visible_stage_ids': [(3, assignment.id)]})
        a, b = self.one[0], self.two[0]
        before = (a.stage_id.id, b.stage_id.id)
        with self.assertRaises(UserError) as caught:
            f.act('journey_stage', {'applicant_ids': [a.id, b.id],
                                    'key': 'assignment', 'register': True})
        words = str(caught.exception)
        self.assertIn('is not a stage on', words)
        self.assertIn('NAV P3a Second role', words)
        self.assertEqual(words.count('.'), 2, 'the refusal is not one short sentence pair')
        self.assertEqual((a.stage_id.id, b.stage_id.id), before, 'somebody moved anyway')
        # the same pair to an outcome every role has goes through
        res = f.act('journey_stage', {'applicant_ids': [a.id, b.id],
                                      'key': 'on_hold', 'register': True})
        self.assertEqual(len(res['moved']), 2)
        # a role page's own move (no register flag) is untouched by the rule
        f.act('journey_stage', {'applicant_ids': [b.id], 'key': 'assignment'})
        self.assertEqual(b.stage_id.pb_key, 'assignment')

    # ------------------------------------------------------------- test 5
    def test_05_offers_steps_seats_papers_check_joining_and_money(self):
        f = self.facade
        offer = self._offer()
        data = f.get_offers()
        self.assertTrue(data['allowed'])
        row = self._row(data, offer)
        self.assertEqual(row['step'], 'approval')
        self.assertEqual([s['key'] for s in data['steps']],
                         ['approval', 'candidate', 'signing', 'joined', 'closed'])
        self.assertEqual(sum(s['count'] for s in data['steps']), len(data['rows']))
        self.assertFalse(row['waiting_mine'], 'a draft waits on nobody')
        self.assertEqual(row['bgv']['state'], 'complete')
        self.assertIsNone(row['docreq'])
        self.assertEqual(row['recruiter_id'], self.recruiter.id)

        # waiting on me = my open seat on the offer's route
        try:
            offer.action_submit()
        except UserError:
            # a database with no published offer route: the ladder state only
            offer.sudo().write({'state': 'submitted'})
        self.assertEqual(offer.state, 'submitted')
        seat_user = self.env['res.users']
        if offer.approval_request_id:
            step = offer.sudo()._chain_active_step()
            seat_user = step.sudo().seat_ids.filtered(lambda s: s.status == 'open')[:1].acting_user_id
        if seat_user and seat_user.has_group('pb_hiring.group_hiring_user'):
            self.assertTrue(self._row(f.with_user(seat_user).get_offers(), offer)['waiting_mine'],
                            'the person whose seat is open is not told it waits on them')
        Offer = type(self.env['pb.hiring.offer'])
        with patch.object(Offer, '_chain_my_seat', lambda rec: rec.browse(rec.id)):
            self.assertTrue(self._row(f.get_offers(), offer)['waiting_mine'])
            mine = f.get_offers({'flags': ['waiting_mine']})
            self.assertIn(offer.id, [r['id'] for r in mine['rows']])
        with patch.object(Offer, '_chain_my_seat', lambda rec: rec.browse()):
            self.assertFalse(self._row(f.get_offers(), offer)['waiting_mine'])

        # the papers: asked for, and past the date
        docreq = self.env['pb.hiring.docreq'].open_for(offer.id)
        docreq.sudo().write({'sent_on': fields.Datetime.now(),
                             'deadline': fields.Date.context_today(self.env.user) - timedelta(days=1)})
        row = self._row(f.get_offers(), offer)
        self.assertEqual(row['docreq']['wanted'], docreq.wanted_count)
        self.assertEqual(row['docreq']['in'], docreq.in_count)
        self.assertTrue(row['docreq']['overdue'])
        self.assertIn(offer.id, [r['id'] for r in f.get_offers({'flags': ['docs_overdue']})['rows']])

        # joining soon: today to 30 days, inclusive
        today = fields.Date.context_today(self.env.user)
        offer.sudo().write({'state': 'signed', 'expected_join_date': today + timedelta(days=30)})
        row = self._row(f.get_offers(), offer)
        self.assertEqual(row['step'], 'signing')
        self.assertTrue(row['joining_soon'])
        self.assertEqual(row['joining_days'], 30)
        offer.sudo().write({'expected_join_date': today + timedelta(days=31)})
        self.assertFalse(self._row(f.get_offers(), offer)['joining_soon'])
        offer.sudo().write({'expected_join_date': today})
        self.assertTrue(self._row(f.get_offers(), offer)['joining_soon'])

        # money: the hiring team sees it, a requester does not
        self.assertTrue(data['show_money'])
        self.assertEqual(self._row(f.get_offers(), offer)['monthly_total'], 1000.0)
        lm = self._line_manager()
        theirs = f.with_user(lm).get_offers()
        self.assertFalse(theirs['show_money'])
        for r in theirs['rows']:
            self.assertIsNone(r['monthly_total'])
            self.assertIsNone(r['annual_total'])
            self.assertIsNone(r['bgv'], 'the check is the hiring team\'s')
            self.assertIsNone(r['docreq'])

    # ------------------------------------------------------------- test 6
    def test_06_the_overview_tiles_equal_the_register_counts(self):
        offer = self._offer()
        today = fields.Date.context_today(self.env.user)
        offer.sudo().write({'state': 'signed', 'expected_join_date': today + timedelta(days=5)})
        kpis = self.facade.get_board()['kpis']
        counts = self.facade.get_offers()['counts']
        self.assertEqual(kpis['offers_waiting_mine'], counts['waiting_mine'])
        self.assertEqual(kpis['joining_soon'], counts['joining_soon'])
        self.assertGreaterEqual(kpis['joining_soon'], 1)
        self.assertEqual(kpis['joined_month'], counts['joined_month'])
        self.assertEqual(
            len(self.facade.get_offers({'flags': ['joining_soon']})['rows']),
            kpis['joining_soon'])

    # ------------------------------------------------------------- test 7
    def test_07_the_joined_filter_matches_the_joined_state(self):
        view = self.env.ref('pb_hiring.view_pb_hiring_offer_search')
        self.assertIn("('state', '=', 'joined')", view.arch_db)
        with open(get_module_path('pb_hiring') + '/views/offer_views.xml',
                  encoding='utf-8') as fh:
            source = fh.read()
        self.assertNotIn("'closed'", source,
                         'an offer view still tests the old state name')
        offer = self._offer()
        offer.sudo().write({'state': 'joined'})
        hits = self.env['pb.hiring.offer'].search([('state', '=', 'joined')])
        self.assertIn(offer, hits)

    # ------------------------------------------------- the lens contract
    def test_08_the_hub_names_the_two_registers_between_overview_and_interviews(self):
        with open(get_module_path('pb_hiring') + '/static/src/js/hiring_hub.js',
                  encoding='utf-8') as fh:
            source = fh.read()
        at = [source.index('key: "%s"' % k) for k in
              ('overview', 'applicants', 'offers', 'interviews', 'bank')]
        self.assertEqual(at, sorted(at), 'the rail order is not OVERVIEW · APPLICANTS · OFFERS · INTERVIEWS · TALENT POOL')
        self.assertIn('startTab: "applicants"', source)
        self.assertIn('startTab: "offers"', source)
