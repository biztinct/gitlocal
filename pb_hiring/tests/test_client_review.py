from datetime import timedelta
import runpy

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.modules.module import get_module_path

from .test_offer import OfferCase
from .test_interviews import InterviewCase


@tagged('post_install', '-at_install', 'recruit_review')
class TestClientReview(OfferCase):
    def test_demo_migration_is_scoped_and_idempotent(self):
        lead = self.env['res.users'].sudo().search([('login', '=', 'demo.talentlead@example.com')], limit=1)
        if not lead:
            self.skipTest('The named payobook demonstration account is not installed')
        migration = runpy.run_path(get_module_path('pb_hiring') + '/migrations/19.0.2.11.0/post-review.py')
        migration['_review_demo'](self.env(su=True))
        migration['_review_demo'](self.env(su=True))
        self.assertTrue(lead.has_group('pb_hiring.group_hiring_only'))
        presets = self.env['pb.hiring.stage.preset'].sudo().search([
            ('company_id', '=', lead.company_id.id), ('name', 'in',
             ['DEMO Field roles', 'DEMO Tech roles', 'DEMO Commercial roles'])])
        self.assertEqual(len(presets), 3)
        self.assertEqual(self.req.state, 'open', 'Unrelated roles must stay untouched')
        demo = self.env['pb.hiring.requisition'].sudo().search([
            ('company_id', '=', lead.company_id.id), ('title', '=', 'DEMO Territory Manager')])
        for role in demo:
            if len(role.offer_ids.filtered(lambda o: o.state in ('signed', 'joined'))) >= role.headcount:
                self.assertEqual(role.state, 'filled')

    def test_final_signature_closes_role_and_keeps_other_candidates(self):
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.auto_close_finalists', '1')
        self.req.sudo().write({'headcount': 1})
        other = self.applicant.copy({'partner_name': 'DEMO review other',
                                     'stage_id': self.env['hr.recruitment.stage']._pb_stage('screening').id})
        offer = self._offer()
        offer.sudo().write({'state': 'signed'})
        offer._on_signed()
        self.assertEqual(self.req.state, 'filled')
        self.assertFalse(self.req.referral_open)
        self.assertEqual(self.req.filled_count, 0, 'Signing must not create a joiner')
        self.assertFalse(offer.employee_id)
        self.assertEqual(other.pb_screen, 'future_fit')
        self.assertEqual(other.stage_id.pb_key, 'on_hold')
        self.assertTrue(other.active, 'Keep the CV for future roles')
        closed = self.req.filled_on
        offer._on_signed()
        self.assertEqual(self.req.filled_on, closed)

    def test_first_signature_does_not_close_multiple_openings(self):
        offer = self._offer()
        offer.sudo().write({'state': 'signed'})
        offer._on_signed()
        self.assertEqual(self.req.state, 'open')

    def test_agency_credit_follows_joined_candidate(self):
        vendor = self.env['pb.vendor'].sudo().create({'name': 'DEMO review agency',
                                                     'company_id': self.company.id})
        self.req.sudo().write({'agency_vendor_ids': [(4, vendor.id)]})
        offer = self._offer()
        offer.sudo().write({'state': 'joined', 'joined_on': fields.Date.today()})
        analytics = self.env['pb.hiring.analytics']
        rows = {r['key']: r for r in analytics._agency_split(self.req)}
        self.assertEqual(rows['agency']['filled'], 0)
        self.assertEqual(rows['inhouse']['filled'], 1)
        self.applicant.sudo().write({'pb_agency_vendor_id': vendor.id})
        rows = {r['key']: r for r in analytics._agency_split(self.req)}
        self.assertEqual(rows['agency']['filled'], 1)
        self.assertEqual(rows['inhouse']['filled'], 0)

    def test_talent_lead_owns_rules_and_retention_but_recruiter_does_not(self):
        for tier, expected in [('manager', True), ('user', False)]:
            user = self.env['res.users'].sudo().create({
                'name': 'DEMO review ' + tier, 'login': 'demo.review.' + tier,
                'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)],
                'group_ids': [(6, 0, [self.env.ref('pb_hiring.group_hiring_' + tier).id])]})
            facade = self.env['pb.hiring'].with_user(user)
            self.assertEqual(facade.get_retention_preview()['can_run'], expected)
            if expected:
                facade._act_retention_switch({'on': False})
                rule = self.env['pb.hiring.country.rule'].with_user(user).create({
                    'company_id': self.company.id, 'country_id': self.env.ref('base.au').id,
                    'recruiter_id': user.id})
                rule.write({'note': 'DEMO verified'})
            else:
                with self.assertRaises(AccessError):
                    facade._act_retention_switch({'on': False})

    def test_internal_candidate_has_honest_source(self):
        candidate = self.env['hr.applicant'].create({
            'partner_name': 'DEMO review source', 'job_id': self.job.id,
            'pb_requisition_id': self.req.id, 'company_id': self.company.id})
        self.assertEqual(candidate.source_id.name, 'Manual entry / import')

    def test_hiring_only_cannot_read_access_directory(self):
        user = self.env['res.users'].sudo().create({
            'name': 'DEMO review restricted lead', 'login': 'demo.review.restricted',
            'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)],
            'group_ids': [(6, 0, [self.env.ref('pb_hiring.group_hiring_manager').id,
                                  self.env.ref('pb_hiring.group_hiring_only').id])]})
        with self.assertRaises(AccessError):
            self.env['pb.access'].with_user(user).get_board()
        self.assertFalse(self.env['pb.role.profile'].with_user(user).search([]))
        sidebar = self.env['pb.sidebar.item'].with_user(user).get_sidebar_data()
        self.assertEqual([item['id'] for section in sidebar for item in section['items']],
                         [self.env.ref('pb_hiring.item_hiring').id])
        preview = self.env['pb.sidebar.item'].visibility_for(user)
        self.assertEqual([key for key, state in preview['items'].items() if state == 'on'],
                         [self.env.ref('pb_hiring.item_hiring').id])
        for model in ['hr.payslip', 'hr.contract', 'res.partner.bank']:
            self.assertFalse(self.env['ir.model.access'].with_user(user).check(model, 'write', False))

    def test_background_check_does_not_block_draft(self):
        offer = self.env['pb.hiring.offer'].draft_for(self.req.id)
        self.assertTrue(offer)
        self.assertFalse(offer.bgv_id.check_ready()[0])

    def test_resume_bank_searches_indexed_cv_text(self):
        self.applicant.sudo().write({'pb_screen': 'future_fit'})
        att = self.env['ir.attachment'].sudo().create({
            'name': 'DEMO review CV.txt', 'type': 'binary', 'raw': b'rareagronomyskills',
            'res_model': 'hr.applicant', 'res_id': self.applicant.id, 'pb_form_key': 'cv',
            'mimetype': 'text/plain'})
        att.sudo().write({'index_content': 'rareagronomyskills'})
        rows = self.env['pb.hiring'].search_bank({'q': 'rareagronomyskills'})['rows']
        self.assertIn(self.applicant.id, [r['id'] for r in rows])


@tagged('post_install', '-at_install', 'recruit_review')
class TestReviewFeedback(InterviewCase):
    def test_escalates_at_due_time_and_counts_candidates_once(self):
        interview = self._schedule()
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.lead_late_days', '0')
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.auto_chase', '1')
        self.applicant.sudo().write({
            'stage_id': self.env['hr.recruitment.stage']._pb_stage('discussion_1').id})
        feedback = interview.feedback_ids
        feedback.sudo().write({'due_at': fields.Datetime.now() - timedelta(minutes=1)})
        self.env['pb.hiring.automation']._tell_lead_late_feedback()
        self.assertTrue(all(feedback.mapped('lead_told_at')))
        stamps = feedback.mapped('lead_told_at')
        self.env['pb.hiring.automation']._tell_lead_late_feedback()
        self.assertEqual(stamps, feedback.mapped('lead_told_at'))
        cards = self.env['pb.hiring']._candidates(self.req)
        card = next(c for c in cards if c['id'] == self.applicant.id)
        self.assertEqual(card['opinions']['late'], len(feedback))
        # A closed candidate with unrecorded attendance stays visibly flagged.
        interview.sudo().write({'start': fields.Datetime.now() - timedelta(days=1)})
        self.applicant.sudo().write({
            'stage_id': self.env['hr.recruitment.stage']._pb_stage('joined').id})
        cards = self.env['pb.hiring']._candidates(self.req)
        card = next(c for c in cards if c['id'] == self.applicant.id)
        self.assertEqual(card['opinions']['late'], 0)
        self.assertIn('waiting', card['flags'])
