from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, UserError


@tagged('post_install', '-at_install', 'pb_journey')
class TestHiringJourney(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env['hr.recruitment.stage']._ensure_journey_stages()
        self.company = self.env.company
        self.job = self.env['hr.job'].create({'name': 'QA journey role', 'company_id': self.company.id})
        self.applicant = self.env['hr.applicant'].create({'partner_name': 'QA Candidate', 'job_id': self.job.id,
            'company_id': self.company.id, 'email_from': 'qa@example.invalid'})

    def test_stage_seed_and_optional_assignment(self):
        Stage = self.env['hr.recruitment.stage']
        self.assertEqual(Stage.search_count([('pb_key', '!=', False)]), 15)
        Stage._ensure_journey_stages()
        self.assertEqual(Stage.search_count([('pb_key', '!=', False)]), 15)
        self.assertEqual(self.applicant.stage_id.pb_key, 'screening')
        self.applicant.stage_id = Stage.search([('pb_key', '=', 'phone')], limit=1)
        self.assertEqual(self.applicant._pb_next_stage().pb_key, 'discussion_1')
        self.applicant.stage_id = Stage.search([('pb_key', '=', 'reference')], limit=1)
        self.assertFalse(self.applicant._pb_next_stage())

    def test_hold_and_offer_gates(self):
        facade = self.env['pb.hiring']
        for key in ['on_hold', 'offer', 'joined']:
            stage = self.env['hr.recruitment.stage'].search([('pb_key', '=', key)], limit=1)
            with self.assertRaises(UserError):
                facade._act_journey_stage({'applicant_id': self.applicant.id, 'stage_id': stage.id})
        self.assertEqual(self.applicant.stage_id.pb_key, 'screening')

    def test_direct_stage_write_keeps_offer_gates(self):
        for key in ('offer', 'joined'):
            stage = self.env['hr.recruitment.stage'].search([('pb_key', '=', key)], limit=1)
            with self.assertRaises(UserError):
                self.applicant.write({'stage_id': stage.id})
        self.assertEqual(self.applicant.stage_id.pb_key, 'screening')

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
