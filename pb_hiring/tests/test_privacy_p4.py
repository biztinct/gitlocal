# -*- coding: utf-8 -*-
"""RECRUIT P4 — private until shared: shares, money locks, recruiter notes,
the Resume bank, retention.

Numbered as in `docs/handovers/recruit/RECRUIT_P4_PRIVACY.md` §5 (tests
1–10; 11 is the rest of the suite).
"""

import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged

from ..models.privacy_p4 import REMOVED, _user_of
from .test_interviews import InterviewCase

PDF = b'%PDF-1.4\n% a tiny RECRUIT P4 test file\n'


class PrivacyCase(InterviewCase):

    def setUp(self):
        super().setUp()
        self.facade = self.env['pb.hiring']
        stamp = fields.Datetime.now().timestamp()
        # The line manager: the person who asked for the role.
        self.lm = self.env['res.users'].sudo().create({
            'name': 'RECRUIT P4 Line Manager', 'login': 'recruit.p4.lm.%s' % stamp,
            'email': 'recruit.p4.lm@example.com',
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('base.group_user').id)]})
        self.head.sudo().write({'user_id': self.lm.id})
        # the stored "who asked, as a login" follows the employee's new login
        # (in real life the login exists before the request is raised)
        req = self.req.sudo()
        self.env.add_to_compute(req._fields['requested_by_user_id'], req)
        req._recompute_recordset(['requested_by_user_id'])
        self.assertEqual(req.requested_by_user_id, self.lm)
        self.stranger = self.env['res.users'].sudo().create({
            'name': 'RECRUIT P4 Stranger', 'login': 'recruit.p4.str.%s' % stamp,
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('base.group_user').id)]})
        self.lead = self.env['res.users'].sudo().create({
            'name': 'RECRUIT P4 Talent Lead', 'login': 'recruit.p4.lead.%s' % stamp,
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('pb_hiring.group_hiring_manager').id)]})
        self.other_recruiter = self.env['res.users'].sudo().create({
            'name': 'RECRUIT P4 Other Recruiter', 'login': 'recruit.p4.rec2.%s' % stamp,
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('pb_hiring.group_hiring_user').id)]})
        # Nothing is shared by default in these tests unless a test says so.
        self.req.sudo().write({'default_share_with': 'nobody'})
        self.app = self.applicant
        self.cv = self.env['ir.attachment'].sudo().create({
            'name': 'RECRUIT P4 CV.pdf', 'datas': base64.b64encode(PDF),
            'mimetype': 'application/pdf', 'res_model': 'hr.applicant',
            'res_id': self.app.id, 'public': False})
        self.other_file = self.env['ir.attachment'].sudo().create({
            'name': 'RECRUIT P4 certificate.png', 'datas': base64.b64encode(b'\x89PNG....'),
            'mimetype': 'image/png', 'res_model': 'hr.applicant',
            'res_id': self.app.id, 'public': False})

    def share(self, parts, user=None, apps=None):
        return self.facade.act('share', {
            'applicant_ids': (apps or self.app).ids,
            'targets': [{'user_id': (user or self.lm).id}], 'parts': parts})

    def offer(self):
        self.req.sudo().write({'selected_applicant_id': self.app.id})
        offer = self.env['pb.hiring.offer'].draft_for(self.req.id)
        self.env['pb.hiring.offer.line'].sudo().create({
            'offer_id': offer.id, 'name': 'RECRUIT P4 Basic pay', 'kind': 'earning',
            'amount': 25000000, 'period': 'monthly'})
        offer.invalidate_recordset()
        return offer


@tagged('post_install', '-at_install', 'recruit_p4')
class TestRecruitPrivacy(PrivacyCase):

    # ------------------------------------------------------------- test 1
    def test_01_parts_for(self):
        Share = self.env['pb.hiring.share']
        self.assertEqual(Share.parts_for(self.app, self.recruiter) - {'card'},
                         {'profile', 'cv', 'portfolio', 'assignment', 'attachments',
                          'answers', 'scorecards', 'expected_pay'})
        self.assertEqual(Share.parts_for(self.app, self.lm), {'card'})
        self.assertEqual(Share.parts_for(self.app, self.stranger), set())
        self.share(['profile', 'cv'])
        self.assertEqual(Share.parts_for(self.app, self.lm), {'card', 'profile', 'cv'})
        # an employee's login: the internal one, else the portal one
        portal = self.env['res.users'].sudo().create({
            'name': 'RECRUIT P4 Portal', 'login': 'recruit.p4.portal.%s' % fields.Datetime.now().timestamp(),
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        emp = self.env['hr.employee'].sudo().create({'name': 'RECRUIT P4 Portal Emp',
                                                    'company_id': self.company.id})
        self.assertFalse(_user_of(emp))
        if 'pb_portal_user_id' in emp._fields:
            emp.write({'pb_portal_user_id': portal.id})
            self.assertEqual(_user_of(emp), portal)
            Share._grant(self.app, _user_of(emp), 'cv', employee=emp)
            self.assertIn('cv', Share.parts_for(self.app, portal))
        self.assertEqual(_user_of(self.head), self.lm)

    # ------------------------------------------------------------- test 2
    def test_02_the_manager_sees_the_card_and_a_sentence_until_shared(self):
        cand = self.facade.with_user(self.lm).get_candidate(self.app.id)
        self.assertTrue(cand['locked'])
        self.assertIn('has not shared', cand['locked_text'])
        for key in ('email', 'phone', 'location', 'source', 'applied_on'):
            self.assertFalse(cand[key], key)
        self.assertEqual(cand['documents'], [])
        self.assertEqual(cand['answers'], [])
        self.assertEqual(cand['scorecards'], [])
        self.assertIsNone(cand['money'])
        self.assertEqual(cand['name'], self.app.partner_name)
        self.share(['cv'])
        cand = self.facade.with_user(self.lm).get_candidate(self.app.id)
        self.assertFalse(cand['locked'])
        self.assertEqual([d['id'] for d in cand['documents']], [self.cv.id])
        self.assertIn('access_token=', cand['documents'][0]['url'])
        self.assertTrue(any(lk['key'] == 'profile' for lk in cand['locks']))
        # the board card: name, stage, interview dates — and the share in words
        cards = self.facade.with_user(self.lm).get_requisition(self.req.id)['candidates_list']
        card = [c for c in cards if c['id'] == self.app.id][0]
        self.assertEqual(card['email'], '')
        self.assertEqual(card['chips'], [])
        self.assertIn('CV', card['sub'])
        # the recruiter's card says who it is shared with
        cards = self.facade.get_requisition(self.req.id)['candidates_list']
        card = [c for c in cards if c['id'] == self.app.id][0]
        # P6 names people by their given name on buttons and chips (`_short_name`).
        self.assertIn(self.facade._short_name(self.lm.name), card['shared'])

    def test_02b_unsharing_regenerates_the_file_tokens(self):
        self.share(['cv'])
        url = self.facade.with_user(self.lm).get_candidate(self.app.id)['documents'][0]['url']
        token = url.split('access_token=')[1]
        share = self.env['pb.hiring.share'].sudo().search([('applicant_id', '=', self.app.id)])
        self.facade.act('unshare', {'share_ids': share.ids})
        self.cv.invalidate_recordset()
        self.assertTrue(self.cv.sudo().access_token)
        self.assertNotEqual(self.cv.sudo().access_token, token)
        cand = self.facade.with_user(self.lm).get_candidate(self.app.id)
        self.assertTrue(cand['locked'])

    # ------------------------------------------------------------- test 3
    def test_03_money_is_never_shared_by_accident(self):
        self.app.sudo().write({'salary_expected': 28000000})
        self.share(['profile', 'cv'])
        self.assertIsNone(self.facade.with_user(self.lm).get_candidate(self.app.id)['money'])
        self.share(['profile', 'cv', 'expected_pay'])
        money = self.facade.with_user(self.lm).get_candidate(self.app.id)['money']
        self.assertEqual(money['expected'], 28000000)
        self.assertIn(self.facade._short_name(self.lm.name),
                      self.facade.get_candidate(self.app.id)['money_who'])
        # the role's budget, on the board row and the role page
        self.req.sudo().write({'budget_cost': 600000000})
        row = self.facade.with_user(self.lm).get_requisition(self.req.id)
        self.assertEqual(row['budget_cost'], 0.0)
        self.assertEqual(row['budget_status'], 'hidden')
        self.assertEqual(self.facade.get_requisition(self.req.id)['budget_cost'], 600000000)
        # the offer's figures
        offer = self.offer()
        lm_offers = self.facade.with_user(self.lm).get_requisition(self.req.id)['offers']
        self.assertTrue(lm_offers)
        self.assertIsNone(lm_offers[0]['monthly_total'])
        self.assertTrue(all(ln['amount'] is None for ln in lm_offers[0]['lines']))
        rec_offers = self.facade.get_requisition(self.req.id)['offers']
        self.assertEqual(rec_offers[0]['monthly_total'], 25000000)
        # a seat holder with no hiring group still reads the amounts in the
        # approval inbox: the inbox reads the record as the system
        seat = self.env['pb.hiring.offer'].with_user(self.lm).sudo().browse(offer.id)
        detail = seat._approval_detail(False)
        self.assertTrue(any('25' in (row[1] or '') for row in detail['rows']))
        # ...and the route's stamp reads as the system too
        self.assertTrue(self.env['pb.hiring.offer'].with_user(self.lm).browse(offer.id)
                        ._chain_revision_values()['lines'])

    # ------------------------------------------------------------- test 4
    def test_04_the_timeline_outside_the_team(self):
        app = self.app
        app.message_post(body='RECRUIT P4 a recruiter note', message_type='comment',
                         subtype_xmlid='mail.mt_note')
        app.message_post(subject='RECRUIT P4 an email', body='Hello', message_type='email')
        self.facade.act('journey_stage', {'applicant_ids': [app.id], 'key': 'phone'})
        self.offer()
        mine = self.facade.with_user(self.lm).get_timeline(app.id)
        kinds = {i['kind'] for i in mine}
        self.assertIn('move', kinds)
        self.assertFalse(kinds & {'email', 'offer'})
        self.assertFalse([i for i in mine if 'RECRUIT P4 a recruiter note' in i['text']])
        # the manager's own note stays theirs to read
        self.facade.with_user(self.lm).act('candidate_note', {'applicant_id': app.id,
                                                             'body': 'RECRUIT P4 from the manager'})
        mine = self.facade.with_user(self.lm).get_timeline(app.id)
        self.assertTrue([i for i in mine if 'from the manager' in i['text']])
        theirs = self.facade.get_timeline(app.id)
        self.assertTrue({'note', 'email', 'offer'} <= {i['kind'] for i in theirs})

    # ------------------------------------------------------------- test 5
    def test_05_recruiter_notes(self):
        F = self.facade
        messages = self.env['mail.message'].sudo().search_count(
            [('model', '=', 'hr.applicant'), ('res_id', '=', self.app.id)])
        res = F.with_user(self.recruiter).act('note_add', {'applicant_id': self.app.id,
                                                          'body': 'Comfortable at 28m.'})
        note = self.env['pb.hiring.note'].sudo().browse(res['id'])
        self.assertEqual(self.env['mail.message'].sudo().search_count(
            [('model', '=', 'hr.applicant'), ('res_id', '=', self.app.id)]), messages,
            'a recruiter note went into the chatter')
        self.assertEqual(len(F.with_user(self.recruiter).get_notes(self.app.id)['rows']), 1)
        self.assertEqual(F.with_user(self.other_recruiter).get_notes(self.app.id)['rows'], [])
        self.assertFalse(self.env['pb.hiring.note'].with_user(self.other_recruiter).search(
            [('id', '=', note.id)]), 'the record rule let another recruiter read it')
        self.assertEqual(len(F.with_user(self.lead).get_notes(self.app.id)['rows']), 1)
        # the manager sees nothing until this one note is shared with them
        self.assertEqual(F.with_user(self.lm).get_candidate(self.app.id)['notes']['rows'], [])
        F.with_user(self.recruiter).act('note_share', {'note_id': note.id, 'user_ids': [self.lm.id]})
        rows = F.with_user(self.lm).get_candidate(self.app.id)['notes']['rows']
        self.assertEqual([r['id'] for r in rows], [note.id])
        self.assertFalse(rows[0]['can_edit'])
        with self.assertRaises(AccessError):
            F.with_user(self.other_recruiter).act('note_delete', {'note_id': note.id})
        with self.assertRaises(AccessError):
            F.with_user(self.other_recruiter).act('note_edit', {'note_id': note.id, 'body': 'x'})
        F.with_user(self.recruiter).act('note_edit', {'note_id': note.id, 'body': 'Would move for 30m.'})
        self.assertIn('30m', note.body)
        res = F.with_user(self.lead).act('note_delete', {'note_id': note.id})
        self.assertFalse(note.exists())
        F.with_user(self.lead).act('note_restore', {'saved': res['saved']})
        self.assertEqual(len(F.with_user(self.recruiter).get_notes(self.app.id)['rows']), 1)

    # ------------------------------------------------------------- test 6
    def test_06_role_defaults_apply_to_new_candidates_only(self):
        self.req.sudo().write({'default_share_with': 'hiring_manager',
                               'default_share_parts': 'profile,cv'})
        Share = self.env['pb.hiring.share'].sudo()
        self.assertFalse(Share.search([('applicant_id', '=', self.app.id)]),
                         'a default reached a candidate who was already there')
        manual = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P4 Manual', 'email_from': 'recruit.p4.manual@example.com',
            'job_id': self.req.job_id.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id})
        share = Share.search([('applicant_id', '=', manual.id), ('user_id', '=', self.lm.id)])
        self.assertEqual(share.parts, 'profile,cv')
        # changing the default does not change what was shared
        self.facade.act('role_share_defaults', {'requisition_id': self.req.id,
                                                'parts': ['cv', 'scorecards']})
        self.assertEqual(share.parts, 'profile,cv')
        # the public application path
        Form = self.env['pb.hiring.form'].sudo()
        Form._ensure_templates(self.company)
        form = self.req.sudo().pb_form_id or Form.search([('company_id', '=', self.company.id)], limit=1)
        public = form._pb_make_applicant(self.req.job_id, self.req, {
            'partner_name': 'RECRUIT P4 Public', 'email_from': 'recruit.p4.public@example.com'},
            {}, [], 'en_US')
        share = Share.search([('applicant_id', '=', public.id), ('user_id', '=', self.lm.id)])
        self.assertEqual(share.parts, 'cv,scorecards')
        # a bank copy
        other = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'RECRUIT P4 Second role', 'department_id': self.dept.id,
            'company_id': self.company.id, 'requested_by_id': self.head.id,
            'headcount': 1, 'requirements': 'x', 'default_share_parts': 'answers',
            'default_share_with': 'hiring_manager'})
        other._chain_state_write('open')
        other._on_opened()
        self.app.sudo().write({'pb_screen': 'future_fit'})
        res = self.facade.act('bank_add_to_role', {'applicant_ids': [self.app.id],
                                                   'requisition_id': other.id})
        copy = self.env['hr.applicant'].sudo().browse(res['added'][0])
        share = Share.search([('applicant_id', '=', copy.id), ('user_id', '=', self.lm.id)])
        self.assertEqual(share.parts, 'answers')
        # nobody: nothing at all
        self.req.sudo().write({'default_share_with': 'nobody'})
        quiet = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P4 Quiet', 'job_id': self.req.job_id.id,
            'company_id': self.company.id, 'pb_requisition_id': self.req.id})
        self.assertFalse(Share.search([('applicant_id', '=', quiet.id)]))

    # ------------------------------------------------------------- test 7
    def test_07_bulk_share_is_idempotent(self):
        second = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P4 Second', 'job_id': self.req.job_id.id,
            'company_id': self.company.id, 'pb_requisition_id': self.req.id})
        both = self.app | second
        self.share(['profile'], apps=both)
        res = self.share(['profile', 'cv'], apps=both)
        shares = self.env['pb.hiring.share'].sudo().search([('applicant_id', 'in', both.ids)])
        self.assertEqual(len(shares), 2)
        self.assertEqual(set(shares.mapped('parts')), {'profile,cv'})
        self.assertEqual(len(res['before']), 2)
        self.facade.act('share_restore', {'before': res['before']})
        self.assertEqual(set(shares.mapped('parts')), {'profile'})
        with self.assertRaises(AccessError):
            self.facade.with_user(self.lm).act('share', {
                'applicant_ids': both.ids, 'targets': [{'user_id': self.stranger.id}],
                'parts': ['cv']})

    # ------------------------------------------------------------- test 8
    def test_08_the_resume_bank(self):
        F = self.facade
        with self.assertRaises(AccessError):
            F.with_user(self.lm).search_bank({})
        self.assertFalse(F.with_user(self.lm).get_board().get('can_bank'))
        app = self.app
        app.sudo().write({'stage_id': self.env['hr.recruitment.stage']._pb_stage('screening').id})
        app.action_pb_screen('future_fit')
        res = F.search_bank({})
        self.assertIn(app.id, [r['id'] for r in res['rows']])
        everyone = F.search_bank({'include_all': True})
        self.assertGreaterEqual(everyone['total'], res['total'])
        hit = F.search_bank({'q': 'rize w2 a2 candidate'})
        self.assertIn(app.id, [r['id'] for r in hit['rows']])
        self.assertNotIn(app.id, [r['id'] for r in F.search_bank({'q': 'nobody-at-all-p4'})['rows']])
        # tags, facets
        F.act('bank_tag', {'applicant_ids': [app.id], 'new_tag': 'RECRUIT P4 Keep in touch'})
        tag = self.env['hr.applicant.category'].sudo().search([('name', '=', 'RECRUIT P4 Keep in touch')])
        res = F.search_bank({'tag_ids': [tag.id]})
        self.assertEqual([r['id'] for r in res['rows']], [app.id])
        facet = [f for f in res['facets']['tags'] if f['id'] == tag.id]
        self.assertEqual(facet[0]['count'], 1)
        if F._skills_on():
            Type = self.env['hr.skill.type'].sudo()
            stype = Type.create({'name': 'RECRUIT P4 Languages',
                                 'skill_ids': [(0, 0, {'name': 'RECRUIT P4 Bahasa'})],
                                 'skill_level_ids': [(0, 0, {'name': 'Fluent', 'level_progress': 100,
                                                             'default_level': True})]})
            F.act('bank_skills', {'applicant_ids': [app.id], 'skill_ids': stype.skill_ids.ids})
            self.assertIn(app.id, [r['id'] for r in F.search_bank({'q': 'bahasa'})['rows']])
            self.assertIn(app.id, [r['id'] for r in F.search_bank({'skill_ids': stype.skill_ids.ids})['rows']])
        # add to a role
        other = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'RECRUIT P4 Bank role', 'department_id': self.dept.id,
            'company_id': self.company.id, 'headcount': 1, 'requirements': 'x'})
        other._chain_state_write('open')
        other._on_opened()
        res = F.act('bank_add_to_role', {'applicant_ids': [app.id], 'requisition_id': other.id})
        copy = self.env['hr.applicant'].sudo().browse(res['added'][0])
        self.assertEqual(copy.job_id, other.job_id)
        self.assertEqual(copy.stage_id.pb_key, 'screening')
        self.assertEqual(copy.pb_origin_applicant_id, app)
        self.assertEqual(copy.partner_name, app.partner_name)
        self.assertTrue(self.env['ir.attachment'].sudo().search_count(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', copy.id)]))
        again = F.act('bank_add_to_role', {'applicant_ids': [app.id], 'requisition_id': other.id})
        self.assertFalse(again['added'])

    def test_08b_keep_in_touch_pool_is_per_company(self):
        other_co = self.env['res.company'].sudo().create({'name': self.company.name + ' P4 twin'})
        name = 'Worth keeping in touch with — %s' % self.company.name
        foreign = self.env['hr.talent.pool'].sudo().create({'name': name, 'company_id': other_co.id})
        self.app._pb_keep_in_touch()
        self.assertTrue(self.app.talent_pool_ids)
        self.assertNotIn(foreign, self.app.talent_pool_ids)
        self.assertEqual(self.app.talent_pool_ids.company_id, self.company)

    # ------------------------------------------------------------- test 9
    def test_09_retention(self):
        Rule = self.env['pb.hiring.retention.rule'].sudo()
        app = self.app
        consent = fields.Datetime.now() - timedelta(days=500)
        app.sudo().write({'pb_consent_on': consent, 'pb_country_id': self.env.ref('base.vn').id})
        self.company.sudo().write({'pb_retention_months': 12})
        self.assertEqual(app.pb_retention_until, (consent + timedelta(days=0)).date().replace(
            year=consent.year + 1))
        rule = Rule.create({'company_id': self.company.id, 'country_id': self.env.ref('base.vn').id,
                            'months': 6})
        app.invalidate_recordset(['pb_retention_until'])
        self.assertEqual(app.pb_retention_until.month, (consent.month + 6 - 1) % 12 + 1)
        # an open-stage candidate is never touched; a closed one is due
        self.assertEqual(app._pb_retention_protected(), 'open')
        preview = self.facade.get_retention_preview()
        vn = [m for m in preview['markets'] if m['country_id'] == self.env.ref('base.vn').id][0]
        self.assertGreaterEqual(vn['kept'], 1)
        self.facade.act('journey_stage', {'applicant_ids': [app.id], 'key': 'cv_reject'})
        self.assertEqual(app._pb_retention_protected(), '')
        preview = self.facade.get_retention_preview()
        vn = [m for m in preview['markets'] if m['country_id'] == self.env.ref('base.vn').id][0]
        self.assertGreaterEqual(vn['due'], 1)
        if vn['due'] <= 5:
            self.assertIn(app.id, [x['id'] for x in vn['sample']])
        # a hired person past the date is kept
        hired = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P4 Hired', 'job_id': self.req.job_id.id,
            'company_id': self.company.id, 'pb_requisition_id': self.req.id})
        hired.write({'pb_consent_on': consent, 'pb_country_id': self.env.ref('base.vn').id,
                     'stage_id': self.env['hr.recruitment.stage']._pb_stage('joined').id})
        self.assertEqual(hired._pb_retention_protected(), 'hired')
        # extend once, written down
        with self.assertRaises(AccessError):
            self.facade.with_user(self.lm).act('retention_extend', {'applicant_id': app.id})
        before = app.pb_retention_until
        self.facade.with_user(self.recruiter).act('retention_extend', {'applicant_id': app.id})
        self.assertEqual(app.pb_retention_extended_by_id, self.recruiter)
        self.assertGreater(app.pb_retention_until, before)
        with self.assertRaises(Exception):
            self.facade.act('retention_extend', {'applicant_id': app.id})
        # the leg: only the due, closed, non-hired; delete mode anonymises
        app.sudo().write({'pb_retention_extended_on': False, 'pb_retention_extended_by_id': False})
        rule.write({'purge_mode': 'delete'})
        self.share(['cv'])
        self.facade.with_user(self.recruiter).act('note_add', {'applicant_id': app.id, 'body': 'x'})
        stage_logs = self.env['pb.hiring.stage.log'].sudo().search_count([('applicant_id', '=', app.id)])
        with self.assertRaises(AccessError):
            self.facade.with_user(self.recruiter).act('retention_run', {})
        res = self.facade.act('retention_run', {})
        self.assertGreaterEqual(res['counts']['anonymised'], 1)
        self.assertTrue(app.exists())
        self.assertEqual(app.partner_name, REMOVED)
        self.assertFalse(app.email_from)
        self.assertTrue(app.pb_anonymised_on)
        self.assertFalse(app.pb_note_ids)
        self.assertFalse(self.env['pb.hiring.share'].sudo().with_context(active_test=False).search(
            [('applicant_id', '=', app.id)]))
        self.assertFalse(self.env['ir.attachment'].sudo().search_count(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id)]))
        self.assertEqual(self.env['pb.hiring.stage.log'].sudo().search_count(
            [('applicant_id', '=', app.id)]), stage_logs, 'the numbers lost their history')
        self.assertNotEqual(hired.partner_name, REMOVED)
        # the night leg is off by default
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'pb_hiring.retention_enabled')]).unlink()
        self.assertEqual(self.env['pb.hiring.automation'].run_now().get('retention'), 0)

    # ------------------------------------------------------------ test 10
    def test_10_offer_money_fields_carry_groups(self):
        offer = self.offer()
        Offer = self.env['pb.hiring.offer']
        self.assertIn('monthly_total', Offer.with_user(self.recruiter).fields_get())
        self.assertNotIn('monthly_total', Offer.with_user(self.lm).fields_get())
        self.assertNotIn('amount', self.env['pb.hiring.offer.line'].with_user(self.lm).fields_get())
        arch = Offer.with_user(self.recruiter).get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('monthly_total', arch)
        arch = Offer.with_user(self.lm).get_views([(False, 'form')])['views']['form']['arch']
        self.assertNotIn('name="monthly_total"', arch)
        with self.assertRaises(AccessError):
            Offer.with_user(self.lm).browse(offer.id).read(['monthly_total'])
        self.assertEqual(Offer.with_user(self.recruiter).browse(offer.id).monthly_total, 25000000)

    def test_a_share_opens_the_candidate_to_somebody_off_the_role(self):
        with self.assertRaises(AccessError):
            self.facade.with_user(self.stranger).get_candidate(self.app.id)
        self.assertFalse(self.facade.with_user(self.stranger).can_open())
        self.share(['profile'], user=self.stranger)
        self.assertTrue(self.facade.with_user(self.stranger).can_open())
        board = self.facade.with_user(self.stranger).get_board()
        self.assertTrue(board['allowed'])
        self.assertEqual([s['applicant_id'] for s in board['shared_with_me']], [self.app.id])
        cand = self.facade.with_user(self.stranger).get_candidate(self.app.id)
        self.assertEqual(cand['parts'], ['profile'])

    def test_the_consent_sentence_says_the_market_months(self):
        Form = self.env['pb.hiring.form'].sudo()
        Form._ensure_templates(self.company)
        form = Form.search([('company_id', '=', self.company.id), ('is_template', '=', True)], limit=1)
        self.env['pb.hiring.retention.rule'].sudo().create({
            'company_id': self.company.id, 'country_id': self.env.ref('base.id').id, 'months': 7})
        if '{months}' in (form.consent_text or ''):
            self.assertIn('7', form._pb_consent_sentence(self.company, self.env.ref('base.id')))


@tagged('post_install', '-at_install', 'recruit_p4')
class TestRecruitPrivacyFiles(HttpCase, PrivacyCase):
    """Test 2 over HTTP: the token link opens for whoever holds it, a link
    without the token does not, and an old link stops working on unshare."""

    def test_02_tokenised_cv_link(self):
        self.share(['cv'])
        url = self.facade.with_user(self.lm).get_candidate(self.app.id)['documents'][0]['url']
        self.authenticate(None, None)
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content.startswith(b'%PDF'))
        bare = self.url_open('/web/content/%s' % self.cv.id)
        self.assertIn(bare.status_code, (403, 404))
        wrong = self.url_open('/web/content/%s?access_token=not-the-token' % self.cv.id)
        self.assertIn(wrong.status_code, (403, 404))
        share = self.env['pb.hiring.share'].sudo().search([('applicant_id', '=', self.app.id)])
        self.facade.act('unshare', {'share_ids': share.ids})
        old = self.url_open(url)
        self.assertIn(old.status_code, (403, 404))
        # the other file was never shared and was never given a token
        self.assertFalse(self.other_file.sudo().access_token)
