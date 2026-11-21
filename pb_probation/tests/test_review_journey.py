import json
from datetime import date
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError
from ..models.review_journey import SOP_QUESTIONS


@tagged('post_install', '-at_install', 'pb_journey')
class TestReviewJourney(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('pb_probation.probation_mail','0')
        self.company = self.env.company
        self.employee = self.env['hr.employee'].create({'name':'QA review employee', 'company_id':self.company.id, 'employee_type':'employee'})
        self.review = self.env['pb.probation.review'].create({'employee_id':self.employee.id, 'kind':'probation',
            'trial_end':date(2090,1,31), 'company_id':self.company.id})

    def test_manager_cannot_bypass_review_gate(self):
        with self.assertRaises(UserError):
            self.review.with_context(pb_verdict_approved_write=True).action_verdict('pass')
        self.assertNotEqual(self.review.state, 'closed')

    def test_peer_policy_and_validation(self):
        policy = self.env['pb.probation.policy'].create({'name':'QA policy','company_id':self.company.id,'sequence':-100})
        self.assertEqual(policy.peer_max,4)
        peers = self.env['hr.employee'].create([{'name':'QA peer %s'%i, 'company_id':self.company.id, 'work_email':'qa%s@example.invalid'%i} for i in range(5)])
        with self.assertRaises(UserError):
            self.review.action_confirm_nominees(peers.ids)
        result = self.review.action_confirm_nominees(peers[:3].ids)
        self.assertEqual(result['sent'],3)
        request = self.review.feedback_request_ids[0]
        self.assertIn('sop_frequency', request.questions_json)
        with self.assertRaises(UserError):
            request.submit_answers({})
        answers={q['key']:{'label':q['label'],'value':q.get('options',['Example'])[0]} for q in SOP_QUESTIONS}
        request.submit_answers(answers)
        html, average = self.review._build_report()
        self.assertEqual(average,1)
        self.assertIn('/ 4',str(html))
        self.assertFalse(self.review._write_performance_rating())

    def test_recommendation_waits_for_hr_and_records_approval(self):
        from unittest.mock import patch
        self.review.sudo().write({'state':'verdict', 'pb_manager_quality':'3', 'pb_manager_culture':'3',
                                 'pb_manager_adaptability':'3', 'pb_manager_initiative':'3'})
        self.review._ensure_one_on_one()
        self.review.one_on_one_checkin_id.sudo().write({'state':'done'})
        with patch.object(type(self.review), '_verdict_pass', return_value={'ok':True}) as apply:
            result = self.review.action_verdict('pass', strengths='Reliable delivery', improvements='Improve documentation')
            self.assertTrue(result['pending'])
            self.assertEqual(self.review.pb_gate,'hr')
            apply.assert_not_called()
            self.review.action_pb_review('approve')
            apply.assert_called_once()
        self.assertEqual(self.review.pb_gate,'approved')
        self.assertEqual(self.review.state,'closed')

    def test_drawer_rpc_and_recommendation_preview(self):
        from odoo.service.model import call_kw
        result = call_kw(self.env['pb.probation'], 'get_person', [self.employee.id], {})
        self.assertEqual(result['sop']['gate'], 'manager')
        preview = self.review.verdict_preview('pass')
        self.assertEqual(preview['label'], 'Submit recommendation')
        self.assertIn('HR lead', preview['lines'][0])
