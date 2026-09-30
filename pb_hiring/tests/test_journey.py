from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install', 'pb_journey')
class TestHiringJourney(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env['hr.recruitment.stage']._ensure_journey_stages()
        self.company = self.env.company
        self.job = self.env['hr.job'].create({'name': 'QA journey role', 'company_id': self.company.id})
        self.applicant = self.env['hr.applicant'].create({'partner_name': 'QA Candidate', 'job_id': self.job.id,
            'company_id': self.company.id, 'email_from': 'qa@example.invalid'})

    def test_stage_seed_and_next_stage(self):
        Stage = self.env['hr.recruitment.stage']
        # RECRUIT P1: 17 stages — Shortlist and Post-offer are new.
        self.assertEqual(Stage.search_count([('pb_key', '!=', False)]), 17)
        Stage._ensure_journey_stages()
        self.assertEqual(Stage.search_count([('pb_key', '!=', False)]), 17)
        self.assertEqual(self.applicant.stage_id.pb_key, 'screening')
        self.applicant.stage_id = Stage._pb_stage('phone')
        # No role behind this candidate: every stage shown except the ones
        # hidden by default, so Recruiter review -> Assignment.
        self.assertEqual(self.applicant._pb_next_stage().pb_key, 'assignment')
        self.applicant.stage_id = Stage._pb_stage('cv_reject')
        self.assertFalse(self.applicant._pb_next_stage())

    def test_moves_are_not_gated_except_joined(self):
        """RC-D5: on hold needs no date, offer is allowed; joined is set
        from the offer."""
        facade = self.env['pb.hiring']
        for key in ['on_hold', 'offer', 'post_offer']:
            facade._act_journey_stage({'applicant_ids': [self.applicant.id], 'key': key})
            self.assertEqual(self.applicant.stage_id.pb_key, key)
        with self.assertRaises(UserError):
            facade._act_journey_stage({'applicant_ids': [self.applicant.id], 'key': 'joined'})
        self.assertEqual(self.applicant.stage_id.pb_key, 'post_offer')

    def test_direct_stage_write_is_not_gated(self):
        for key in ('offer', 'joined'):
            stage = self.env['hr.recruitment.stage']._pb_stage(key)
            self.applicant.write({'stage_id': stage.id})
            self.assertEqual(self.applicant.stage_id.pb_key, key)

    def test_request_options_include_countries_without_existing_roles(self):
        options = self.env['pb.hiring'].journey_options()
        self.assertIn(self.env.ref('base.sg').id, [c['id'] for c in options['countries']])
        self.assertTrue(all(c['name'] for c in options['countries']))

    def test_templates_validate_placeholders(self):
        template = self.env['pb.hiring.message.template'].create({'name': 'QA', 'company_id': self.company.id,
            'key': 'phone', 'subject': '{{role}} at {{brand}}', 'body': 'Hi {{first_name}}. {{scheduling_link}}'})
        with self.assertRaises(UserError):
            template._render(self.applicant)
        result = template._render(self.applicant, {'scheduling_link': 'https://example.invalid/book'})
        self.assertIn('QA', result['body'])
        self.assertNotIn('{{', result['body'])
        self.assertIn(self.company._hiring_brand(), result['subject'])

    def test_referral_requires_consent(self):
        with self.assertRaises(ValueError):
            self.env['pb.hiring.referral'].sudo().refer(0, 0, {'name': 'QA'})
