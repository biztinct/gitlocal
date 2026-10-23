"""Provider boundaries are mocked: no candidate messages or external uploads."""
import hashlib
from html import unescape
from datetime import timedelta
from unittest.mock import patch, Mock

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from .test_offer import OfferCase
from .test_interviews import InterviewCase


@tagged('post_install', '-at_install', 'recruit_connect')
class TestConnections(OfferCase):
    def _user(self, label, group='group_hiring_manager'):
        return self.env['res.users'].sudo().create({'name': label, 'login': 'connect.' + label,
            'email': label + '@example.com', 'company_id': self.company.id,
            'company_ids': [(6,0,self.company.ids)],
            'group_ids': [(6,0,[self.env.ref(group if '.' in group else 'pb_hiring.' + group).id])]})

    def _connection(self, provider='documenso'):
        conn = self.env['pb.hiring.connection']._for_company(provider, self.company)
        if not conn:
            conn = self.env['pb.hiring.connection'].create({'provider': provider})
        conn.write({'enabled': True, 'check_ok': True, 'settings': {'url':'https://sign.example.invalid'}})
        return conn

    def test_setup_secrets_and_role_gate(self):
        lead = self._user('setup')
        facade = self.env['pb.hiring'].with_user(lead)
        card = facade.connection_save('cv', {'url':'https://cv.example.invalid','api_key':'secret-for-test'})
        self.assertNotIn('secret-for-test', str(card))
        conn = self.env['pb.hiring.connection']._for_company('cv', self.company)
        self.assertNotIn('secret-for-test', conn.credentials)
        self.assertEqual(conn._secret('api_key'), 'secret-for-test')
        facade.connection_save('cv', {'api_key':''})
        self.assertEqual(conn._secret('api_key'), 'secret-for-test')
        with self.assertRaises(UserError):
            facade.connection_enable('cv', True)
        recruiter = self._user('recruiter', 'group_hiring_user')
        with self.assertRaises(AccessError):
            self.env['pb.hiring'].with_user(recruiter).connection_save('cv', {})
        with self.assertRaises(AccessError):
            conn.with_user(lead).read(['credentials'])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            facade.connection_save('cv', {'url':'http://cv.example.invalid'})

    def test_failed_check_does_not_enable(self):
        conn = self._connection('cv')
        with patch.object(type(conn), '_check', side_effect=UserError('Service not ready')):
            result = self.env['pb.hiring'].connection_check('cv')
        self.assertFalse(result['enabled'])
        self.assertFalse(result['check_ok'])

    def test_provider_configuration_is_company_scoped(self):
        conn = self._connection('cv')
        other = self.env['res.company'].create({'name':'Connect isolated company'})
        self.assertFalse(self.env['pb.hiring.connection']._for_company('cv', other))
        user = self._user('company')
        outsider = self.env['pb.hiring.connection'].create({'provider':'cv','company_id':other.id})
        with self.assertRaises(AccessError):
            outsider.with_user(user).read(['enabled'])
        self.assertTrue(conn.with_user(user).read(['enabled']))

    def test_cv_extract_then_review_preserves_existing_history(self):
        conn = self._connection('cv')
        attachment = self.env['ir.attachment'].create({'name':'resume.pdf','raw':b'%PDF-test',
            'mimetype':'application/pdf','res_model':'hr.applicant','res_id':self.applicant.id,'pb_form_key':'cv'})
        self.assertEqual(self.applicant.pb_cv_state, 'queued')
        result = {'contract':'payobook-cv-v1', 'text':'Rare CV skill', 'skill_ids':[],
                  'experience':'Extracted job history', 'education':'Extracted education'}
        with patch.object(type(conn), '_http', return_value=Mock(json=lambda:result)):
            action = self.applicant.action_extract_cv()
        self.assertEqual(self.applicant.pb_cv_state,'review')
        self.assertEqual(attachment.index_content, 'Rare CV skill')
        self.applicant.pb_cv_experience = 'Existing recruiter assessment'
        wizard = self.env['pb.hiring.cv.review'].browse(action['res_id'])
        wizard.action_apply()
        self.assertEqual(self.applicant.pb_cv_experience,'Existing recruiter assessment')
        self.assertEqual(self.applicant.pb_cv_education,'Extracted education')
        self.assertEqual(self.applicant.pb_cv_state,'applied')

    def test_signing_checks_recipient_and_files_once(self):
        offer = self._offer()
        conn = self._connection()
        offer.sudo().write({'state':'sent','pb_envelope_id':'env-test', 'pb_sign_connection_id':conn.id,'pb_sign_status':'pending'})
        doc = {'id':'env-test','externalId':offer._sign_reference(), 'status':'COMPLETED',
            'recipients':[{'id':1,'role':'SIGNER','email':offer.candidate_email,'signingStatus':'SIGNED'}],
            'envelopeItems':[{'id':'item-test'}]}
        with patch.object(type(conn), '_http', return_value=Mock(content=b'%PDF-1.4\n%%EOF')) as call:
            offer._sync_esign(doc)
            att = offer.signed_attachment_id
            self.assertTrue(att)
            self.assertEqual(offer.state,'signed')
            offer._sync_esign(doc)
            self.assertEqual(offer.signed_attachment_id,att)
            self.assertEqual(call.call_count,1)
        self.assertFalse(offer.employee_id)
        bad = dict(doc, externalId='another-company-offer')
        with self.assertRaises(UserError): offer._sync_esign(bad)

    def test_unsigned_or_wrong_signer_cannot_complete(self):
        offer = self._offer()
        conn = self._connection()
        offer.sudo().write({'state':'sent','pb_envelope_id':'env-test','pb_sign_connection_id':conn.id,'pb_sign_status':'pending'})
        doc = {'id':'env-test','externalId':offer._sign_reference(),'status':'COMPLETED',
               'recipients':[{'role':'SIGNER','email':'other@example.com','signingStatus':'SIGNED'}]}
        with self.assertRaises(UserError): offer._sync_esign(doc)
        self.assertFalse(offer.signed_attachment_id)

    def test_signature_freezes_lines_and_cancel_allows_revision(self):
        offer = self._offer()
        conn = self._connection()
        offer.write({'pb_envelope_id':'env-test','pb_sign_connection_id':conn.id,'pb_sign_status':'draft'})
        with self.assertRaises(UserError): offer.line_ids[:1].write({'amount':1})
        with self.assertRaises(UserError): offer.line_ids[:1].unlink()
        with self.assertRaises(UserError): offer.action_add_line({'name':'extra','amount':1,'kind':'earning','period':'monthly'})
        reference = offer._sign_reference()
        doc = {'id':'env-test','externalId':reference,'status':'DRAFT'}
        with patch.object(type(offer), '_envelope', return_value=doc), patch.object(type(conn), '_http', return_value=Mock()):
            offer.action_cancel_esign()
        offer.action_restart_esign()
        self.assertNotEqual(reference,offer._sign_reference())
        offer.line_ids[:1].write({'amount':1})

    def test_cover_routes_to_lead_then_dated_hr_fallback(self):
        lead, fallback, recruiter = self._user('lead'), self._user('hr'), self._user('requester')
        self.company.country_id = self.env.ref('base.vn')
        rule = self.env['pb.hiring.country.rule'].create({'company_id':self.company.id,
            'country_id':self.company.country_id.id, 'recruiter_id':recruiter.id,
            'ta_lead_id':lead.id,'cover_hr_fallback_id':fallback.id})
        cover = self.env['pb.hiring.cover'].create({'recruiter_id':recruiter.id,'cover_user_id':lead.id,
            'date_from':fields.Date.today(),'date_to':fields.Date.today()+timedelta(days=2),'reason':'Test'})
        self.assertEqual(cover._resolve_approver(),(lead,'ta_lead'))
        rule.write({'ta_absent_from':fields.Date.today(),'ta_absent_until':fields.Date.today()+timedelta(days=1)})
        self.assertEqual(cover._resolve_approver(),(fallback,'hr_fallback'))
        rule.cover_hr_fallback_id = recruiter
        self.assertFalse(cover._resolve_approver()[0])

    def test_employer_cost_uses_formula_and_invalidates_after_line_change(self):
        self.company.country_id = self.env.ref('base.vn')
        config = self.env['hr.formula.config'].create({'name':'Connect cost test', 'code':'CONNECT_COST_TEST',
            'company_id':self.company.id, 'country_code':'VN'})
        gross = self.env['hr.formula.rule'].create({'config_id':config.id, 'name':'Monthly gross',
            'code':'CONNECTGROSS','column_type':'input','sequence':1})
        contribution = self.env['hr.formula.rule'].create({'config_id':config.id, 'name':'Employer test contribution',
            'code':'CONNECTER','column_type':'formula','sequence':2,'excel_formula':'=A1*0.1'})
        profile = self.env['pb.hiring.cost.profile'].create({'name':'Test approved profile','company_id':self.company.id,
            'country_id':config.country_id.id,'config_id':config.id,'gross_input_id':gross.id,
            'employer_rule_ids':[(6,0,contribution.ids)],'effective_from':fields.Date.today()-timedelta(days=1)})
        offer = self._offer()
        offer.write({'currency_id':config.currency_id.id,'pb_cost_profile_id':profile.id})
        offer.action_calculate_employer_cost()
        self.assertTrue(offer.pb_cost_result)
        self.assertIn('Employer test contribution',offer.pb_cost_result)
        self.assertIn(offer._money(29_700_000), unescape(str(offer.pb_cost_result)))
        self.assertIn(offer._money(366_400_000), unescape(str(offer.pb_cost_result)))
        offer.line_ids[:1].write({'amount':1000})
        self.assertFalse(offer.pb_cost_result)
        extra = self.env['hr.formula.rule'].create({'config_id':config.id,'name':'Required input',
            'code':'CONNECTMISSING','column_type':'input','sequence':3})
        with self.assertRaises(UserError): offer.action_calculate_employer_cost()
        self.assertFalse(offer.pb_cost_result)

    def test_policy_replaces_shares_and_expires_attachment_tokens(self):
        manager = self._user('manager-reader','base.group_user')
        self.boss.user_id = manager
        self.applicant.stage_id = self.env['hr.recruitment.stage']._pb_stage('screening')
        self.env['pb.hiring.share'].create({'applicant_id':self.applicant.id,'user_id':manager.id,'parts':'profile,cv,expected_pay'})
        att = self.env['ir.attachment'].create({'name':'cv.pdf','raw':b'%PDF-test','res_model':'hr.applicant','res_id':self.applicant.id,'access_token':'old-link'})
        policy = self.env['pb.hiring.visibility.policy'].create({'stage_id':self.applicant.stage_id.id,'audience':'manager','cv':True})
        self.assertFalse(att.access_token)
        self.assertEqual(self.env['pb.hiring.share'].parts_for(self.applicant,manager),{'cv','card'})
        policy.cv = False
        self.assertEqual(self.env['pb.hiring.share'].parts_for(self.applicant,manager),{'card'})


@tagged('post_install', '-at_install', 'recruit_connect')
class TestPanelBooking(InterviewCase):
    def test_booking_rechecks_busy_and_rejects_reuse(self):
        Booking = self.env['pb.hiring.booking']
        invitation = Booking.create({'applicant_id':self.applicant.id,'organiser_id':self.env.uid,
            'panel_ids':[(6,0,(self.boss|self.head).ids)],'tz':'UTC'})
        with patch.object(type(invitation), '_busy', return_value=[]):
            invitation.action_find_slots()
        self.assertTrue(invitation.slot_ids)
        slot = invitation.slot_ids[0]
        with patch.object(type(invitation), '_busy', return_value=[(slot.start,slot.stop)]):
            with self.assertRaises(UserError): invitation._book(slot.id)
        self.assertEqual(invitation.state,'ready')
        with patch.object(type(invitation), '_busy', return_value=[]):
            interview = invitation._book(slot.id)
        self.assertEqual(interview.start,slot.start)
        self.assertEqual(invitation.state,'booked')
        with self.assertRaises(UserError): invitation._book(slot.id)

    def test_changed_panel_invalidates_old_link(self):
        invitation = self.env['pb.hiring.booking'].create({'applicant_id':self.applicant.id,
            'panel_ids':[(6,0,self.boss.ids)]})
        with patch.object(type(invitation),'_busy',return_value=[]): invitation.action_find_slots()
        old = invitation.sudo().token
        invitation.write({'duration':60})
        self.assertNotEqual(old,invitation.sudo().token)
        self.assertFalse(invitation.slot_ids)
        self.assertEqual(invitation.state,'draft')

    def test_whatsapp_requires_specific_consent_and_deduplicates(self):
        conn = self.env['pb.hiring.connection'].create({'provider':'whatsapp','enabled':True,'check_ok':True})
        interview = self._schedule()
        interview._remind('24h')
        self.assertFalse(interview.pb_delivery_ids)
        self.applicant.write({'pb_whatsapp_opt_in':True,'pb_whatsapp_consent_note':'Candidate opted in on application'})
        interview._remind('24h')
        interview._remind('24h')
        self.assertEqual(len(interview.pb_delivery_ids),1)
        self.assertEqual(interview.pb_delivery_ids.connection_id,conn)

    def test_calendar_time_change_keeps_audited_interview(self):
        interview = self._schedule()
        event = interview.event_id
        moved = interview.start + timedelta(days=2)
        event.write({'start':moved,'stop':moved+timedelta(minutes=45)})
        self.assertEqual(interview.state,'rescheduled')
        self.assertEqual(interview.rescheduled_to_id.start,moved)
        self.assertEqual(interview.rescheduled_to_id.event_id,event)
        event.write({'active':False})
        self.assertEqual(interview.rescheduled_to_id.state,'cancelled')
