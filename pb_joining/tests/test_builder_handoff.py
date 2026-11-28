from datetime import timedelta
from unittest.mock import patch
from unittest import SkipTest

from odoo import fields
from odoo.tests import tagged
from odoo.addons.pb_new_hire.tests.test_new_hire import NewHireCommon
from ..models.pay_builder import _JOINING_PAY
from odoo.addons.pb_pay_builder.tests.common import make_scheme


@tagged('post_install', '-at_install', 'paybuilder', 'paybuilder_offer')
class TestOfferHandoff(NewHireCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'pbpb_values' not in cls.env['pb.hiring.offer']._fields:
            raise SkipTest('The optional offer package is not installed')
        co = cls.company
        cls.builder = cls.env['pb.pay.builder'].with_company(co)
        cls.scheme = make_scheme(cls.env, co, 'WAGE')
        cls.maker.write({'group_ids': [(4, cls.env.ref('pb_hiring.group_hiring_user').id)]})
        name = 'DEMO Signed Pay'
        app = cls.env['hr.applicant'].sudo().create({'partner_name': name, 'email_from': 'demo.signed.pay@example.invalid',
                                                     'company_id': co.id})
        req = cls.env['pb.hiring.requisition'].sudo().create({'title': 'DEMO Offer Handoff', 'department_id': cls.ops.id,
            'company_id': co.id, 'headcount': 1, 'budget_cost': 1, 'requirements': 'DEMO', 'selected_applicant_id': app.id,
            'state': 'open', 'request_state': 'agreed', 'requested_by_id': cls.boss.id, 'reporting_manager_id': cls.boss.id})
        app.pb_requisition_id = req.id
        cls.offer = cls.env['pb.hiring.offer'].sudo().with_company(co).create({'requisition_id': req.id, 'applicant_id': app.id,
            'start_date': fields.Date.today() + timedelta(days=30), 'currency_id': cls.scheme.currency_id.id, 'job_title': 'DEMO Analyst'})
        cls.builder.offer_builder_use(cls.offer.id, cls.scheme.id, {'wage': 30000000, 'PHONE': 500000, 'LUNCH': 0})
        cls.offer.write({'state': 'signed', 'join_status': 'pending', 'expected_join_date': cls.offer.start_date})

    def test_47_signed_draft(self):
        draft = self.studio().offer_draft(self.offer.id)['draft']
        self.assertEqual(draft['scheme_id'], self.scheme.id)
        self.assertEqual(draft['wage'], 30000000)
        self.assertEqual(draft['usual'], {'PHONE': 500000, 'LUNCH': 0})
        self.assertEqual(set(draft['from_offer']), {'PHONE', 'LUNCH', 'wage'})

    def test_48_ineligible_offer(self):
        self.offer.currency_id = self.env.ref('base.USD')
        result = self.studio().offer_draft(self.offer.id)
        self.assertTrue(result['wage_note'])
        self.assertNotIn('usual', result['draft'])
        self.offer.currency_id = self.scheme.currency_id
        self.scheme.state = 'archived'
        self.assertNotIn('usual', self.studio().offer_draft(self.offer.id)['draft'])

    def test_49_hr_joining_without_hiring(self):
        j = self.env['pb.joining'].sudo().with_company(self.company).search([('offer_id', '=', self.offer.id)], limit=1)
        if not j:
            j = self.env['pb.joining'].sudo().with_company(self.company).create({'name': 'DEMO Signed Pay',
                 'offer_id': self.offer.id, 'origin': 'hiring', 'job_title': 'DEMO Analyst', 'first_day': self.offer.start_date, 'payroll_country': 'VN',
                 'email': 'demo.signed.pay@example.invalid'})
        j.write({'state': 'to_check', 'submitted_at': fields.Datetime.now(), 'day_opened': True})
        j.item_ids.write({'state': 'later'})
        self.assertFalse(self.approver.has_group('pb_hiring.group_hiring_user'))
        self.assertEqual(self.studio(self.approver).joining_draft(j.id)['draft']['usual'], {'PHONE': 500000, 'LUNCH': 0})

    def test_50_only_studio_writes_contract_lines(self):
        data = self.studio().offer_draft(self.offer.id)['draft']
        answer = self.studio().send(self.draft(**dict(data, open_case=False, login_mode='none', trial_on=False,
                                                      letter=False, work_email='', job_id=False)))
        self.assertTrue(answer.get('pending'), answer)
        with patch.object(type(self.offer), '_pbpk_contract_lines', autospec=True) as legacy:
            self.approve(answer)
            legacy.assert_not_called()
        self.assertEqual(self.offer.state, 'joined')
        lines = self.offer.contract_id.advantages_ids
        for code, value in (('LUNCH', 0), ('PHONE', 500000)):
            match = lines.filtered(lambda line: line.advantage_template_id.code == code)
            self.assertEqual(len(match), 1)
            self.assertEqual(match.amount, value)

    def test_58b_signed_offer_is_used_only_after_approval(self):
        j = self.env['pb.joining'].sudo().search([('offer_id', '=', self.offer.id)], limit=1)
        if not j:
            j = self.env['pb.joining'].sudo().with_company(self.company).create({
                'name': 'DEMO Signed Pay', 'offer_id': self.offer.id, 'origin': 'hiring',
                'job_title': 'DEMO Analyst', 'first_day': self.offer.start_date, 'payroll_country': 'VN'})
        self.assertFalse(self.builder._joining_card(j, _JOINING_PAY))
        j.state = 'added'
        card = self.builder._joining_card(j, _JOINING_PAY)
        self.assertTrue(card)
        self.assertIn('DEMO Phone allowance', [row['name'] for group in card['sections'] for row in group['rows']])
        self.assertFalse(any(group['label'] == 'Paid by the company' for group in card['sections']))
        self.offer.currency_id = self.env.ref('base.USD')
        self.assertFalse(self.builder._joining_card(j, _JOINING_PAY))
