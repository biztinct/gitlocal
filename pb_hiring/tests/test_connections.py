"""Provider boundaries are mocked: no candidate messages or external uploads."""
import hashlib
import pytz
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
    def _identity_booking(self, provider='google'):
        conn = self.env['pb.hiring.connection']._for_company(provider, self.company)
        if not conn:
            conn = self.env['pb.hiring.connection'].create({'provider': provider, 'company_id': self.company.id})
        conn.write({'enabled': True, 'check_ok': True})
        return self.env['pb.hiring.booking'].create({'applicant_id': self.applicant.id,
            'organiser_id': self.panel_user.id, 'provider': provider,
            'panel_ids': [(6, 0, (self.panel_one | self.panel_two).ids)]})

    def test_google_organiser_uses_connected_primary_not_payobook_email(self):
        booking = self._identity_booking()
        self.panel_one.work_email = 'different-work-address@example.com'
        start = self._tomorrow()
        busy = [(start, start + timedelta(minutes=30))]
        with patch.object(type(booking), '_provider_busy', return_value=busy) as query:
            self.assertEqual(booking._busy(start, start + timedelta(hours=1)), busy)
        provider, user, calendars, *_ = query.call_args.args
        self.assertEqual(provider, 'google')
        self.assertEqual(user, self.panel_user)
        self.assertEqual(calendars, ['primary', self.panel_two.work_email])
        self.assertNotIn(self.panel_user.email, calendars)
        self.assertNotIn(self.panel_one.work_email, calendars)

    def test_google_own_panel_needs_no_work_email_but_other_panel_still_does(self):
        booking = self._identity_booking()
        self.panel_one.work_email = False
        with patch.object(type(booking), '_provider_busy', return_value=[]) as query:
            booking._busy(self._tomorrow(), self._tomorrow() + timedelta(hours=1))
        self.assertEqual(query.call_args.args[2], ['primary', self.panel_two.work_email])
        self.panel_two.work_email = False
        with self.assertRaises(UserError):
            booking._busy(self._tomorrow(), self._tomorrow() + timedelta(hours=1))

    def test_same_email_does_not_turn_another_panellist_into_organiser(self):
        booking = self._identity_booking()
        self.panel_two.work_email = self.panel_user.email
        with patch.object(type(booking), '_provider_busy', return_value=[]) as query:
            booking._busy(self._tomorrow(), self._tomorrow() + timedelta(hours=1))
        self.assertEqual(query.call_args.args[2], ['primary', self.panel_user.email])

    def test_microsoft_calendar_identifiers_are_unchanged(self):
        booking = self._identity_booking('microsoft')
        self.panel_one.work_email = 'separate-address@example.com'
        with patch.object(type(booking), '_provider_busy', return_value=[]) as query:
            booking._busy(self._tomorrow(), self._tomorrow() + timedelta(hours=1))
        self.assertEqual(set(query.call_args.args[2]),
                         {self.panel_user.email, self.panel_one.work_email, self.panel_two.work_email})

    def test_connection_check_uses_google_primary_and_keeps_microsoft_email(self):
        Booking = self.env['pb.hiring.booking']
        for provider, expected in [('google', 'primary'), ('microsoft', self.env.user.email)]:
            booking = self._identity_booking(provider)
            conn = self.env['pb.hiring.connection']._for_company(provider, self.company)
            with patch.object(type(Booking), '_provider_busy', return_value=[]) as query:
                conn._check()
            self.assertEqual(query.call_args.args[2], [expected])

    def test_inaccessible_panel_calendar_never_becomes_free_slots(self):
        booking = self._identity_booking()
        with patch.object(type(booking), '_provider_busy', side_effect=UserError('Calendar access denied')):
            with self.assertRaises(UserError): booking.action_find_slots()
        self.assertFalse(booking.slot_ids)
        self.assertEqual(booking.state, 'draft')

    def test_booking_preserves_existing_user_timezone_alias(self):
        # Odoo accepts aliases such as Asia/Calcutta; the booking form must
        # include that default in its selection instead of displaying blank.
        self.env.user.tz = 'Asia/Calcutta'
        Booking = self.env['pb.hiring.booking']
        default = Booking.default_get(['tz'])['tz']
        self.assertIn(default, dict(Booking.fields_get(['tz'])['tz']['selection']))
        invitation = Booking.create({'applicant_id': self.applicant.id,
            'panel_ids': [(6, 0, self.boss.ids)]})
        self.assertEqual(invitation.tz, default)
        with patch.object(type(invitation), '_busy', return_value=[]):
            invitation.action_find_slots()
        local = pytz.utc.localize(invitation.slot_ids[0].start).astimezone(pytz.timezone(default))
        self.assertEqual(local.hour, invitation.hour_from)

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


@tagged('post_install', '-at_install', 'recruit_connect')
class TestCVProfile(OfferCase):
    _connection = TestConnections._connection
    def _parsed(self, text='Unique agronomist history', employment=None, skills=None):
        conn = self._connection('cv')
        attachment = self.env['ir.attachment'].create({'name': 'cv.pdf', 'raw': b'%PDF-synthetic',
            'mimetype': 'application/pdf', 'res_model': 'hr.applicant', 'res_id': self.applicant.id, 'pb_form_key': 'cv'})
        result = {'contract': 'payobook-cv-v1', 'text': text, 'skill_ids': skills or [],
                  'experience': 'Agronomist at Acme', 'education': 'BSc', 'employment': employment or []}
        with patch.object(type(conn), '_http', return_value=Mock(json=lambda: result)):
            action = self.applicant.action_extract_cv()
        return attachment, self.env['pb.hiring.cv.review'].browse(action['res_id'])

    def test_review_is_invalid_after_replacement_or_new_extraction(self):
        att, wizard = self._parsed()
        att.write({'raw': b'%PDF-replacement'})
        with self.assertRaises(UserError): wizard.action_apply()
        att, wizard = self._parsed()
        newer = self.applicant.action_review_cv()
        self.env['pb.hiring.cv.review'].browse(newer['res_id']).action_apply()
        with self.assertRaises(UserError): wizard.action_apply()

    def test_deleting_cv_clears_extraction_and_prevents_apply(self):
        att, wizard = self._parsed()
        att.unlink()
        self.assertFalse(self.applicant.pb_cv_result)
        self.assertFalse(self.applicant.pb_cv_search_text)
        with self.assertRaises(UserError): wizard.action_apply()

    def test_reviewed_skills_are_searchable_without_inventing_proficiency(self):
        skill_type = self.env['hr.skill.type'].create({'name': 'CV test type'})
        skill = self.env['hr.skill'].create({'name': 'Agronomy CV test', 'skill_type_id': skill_type.id})
        self.env['hr.skill.level'].create({'name': 'Beginner', 'skill_type_id': skill_type.id, 'level_progress': 10})
        att, wizard = self._parsed(skills=skill.ids, employment=[{'employer': 'Acme', 'title': 'Agronomist', 'start': '2020', 'end': '2023-12', 'source': 'Acme 2020-2023'}])
        wizard.action_apply()
        self.assertIn(skill, self.applicant.pb_cv_skill_ids)
        self.assertNotIn(skill, self.applicant.skill_ids)
        self.assertEqual(self.applicant.pb_cv_employment[0]['start'], '2020')
        bank = self.env['pb.hiring'].search_bank({'q': 'Agronomy CV test', 'include_all': True, 'skill_ids': skill.ids})
        self.assertIn(self.applicant.id, [r['id'] for r in bank['rows']])
        bank = self.env['pb.hiring'].search_bank({'q': 'Unique agronomist history', 'include_all': True})
        self.assertIn(self.applicant.id, [r['id'] for r in bank['rows']])

    def test_bad_dates_cannot_be_applied_and_source_is_escaped(self):
        att, wizard = self._parsed(employment=[{'employer': '<script>bad()</script>', 'title': 'Engineer', 'start': '2025-12', 'end': '2021-01'}])
        with self.assertRaises(ValidationError): wizard.action_apply()
        wizard.employment_ids.end = '2026-01'
        wizard.action_apply()
        self.assertNotIn('<script>', str(self.applicant.pb_cv_employment_html))
        self.assertIn('&lt;script&gt;', str(self.applicant.pb_cv_employment_html))

    def test_paused_connection_invalidates_current_review(self):
        att, wizard = self._parsed()
        self._connection('cv').enabled = False
        att.raw = b'%PDF-new-disabled'
        self.assertEqual(self.applicant.pb_cv_state, 'none')
        self.assertFalse(self.applicant.pb_cv_result)
        with self.assertRaises(UserError): wizard.action_apply()

    def test_anonymisation_clears_extraction_and_review_wizards(self):
        att, wizard = self._parsed(employment=[{'employer': 'Private employer', 'title': 'Engineer'}])
        wizard.action_apply()
        self.applicant._pb_anonymise()
        for field in ('pb_cv_result', 'pb_cv_employment', 'pb_cv_search_text', 'pb_cv_experience', 'pb_cv_education', 'pb_cv_skill_ids'):
            self.assertFalse(self.applicant[field], field)
        self.assertFalse(wizard.exists())
        with self.assertRaises(UserError): self.applicant._extract_cv()

    def test_invalid_service_response_does_not_apply(self):
        att, wizard = self._parsed()
        conn = self._connection('cv')
        for result in [[], {'contract': 'payobook-cv-v1', 'text': 12},
                       {'contract': 'payobook-cv-v1', 'text': 'hello', 'employment': ['not a row']}]:
            with patch.object(type(conn), '_http', return_value=Mock(json=lambda: result)):
                with self.assertRaises(UserError): self.applicant._extract_cv()

    def test_custom_cv_key_and_latest_document_search(self):
        form = self.env['pb.hiring.form'].create({'name': 'CV custom form', 'field_ids': [(0, 0, {
            'kind': 'cv', 'key': 'q_professional_history', 'label': 'Professional history'})]})
        self.applicant.pb_form_id = form
        conn = self._connection('cv')
        first = self.env['ir.attachment'].create({'name': 'document.pdf', 'raw': b'%PDF-first',
            'mimetype': 'application/pdf', 'res_model': 'hr.applicant', 'res_id': self.applicant.id,
            'pb_form_key': 'q_professional_history', 'index_content': 'Obsolete unique employer'})
        self.assertEqual(self.applicant.pb_cv_state, 'queued')
        second = self.env['ir.attachment'].create({'name': 'document-new.pdf', 'raw': b'%PDF-second',
            'mimetype': 'application/pdf', 'res_model': 'hr.applicant', 'res_id': self.applicant.id,
            'pb_form_key': 'q_professional_history', 'index_content': 'Current unique employer'})
        first.write({'index_content': 'Obsolete unique employer'})
        second.write({'index_content': 'Current unique employer'})
        self.assertEqual(self.applicant._current_cv(), second)
        for term, expected in [('Obsolete unique employer', False), ('Current unique employer', True)]:
            result = self.env['pb.hiring'].search_bank({'q': term, 'include_all': True})
            self.assertEqual(self.applicant.id in [r['id'] for r in result['rows']], expected)

    def test_busy_parser_keeps_cv_queued_for_retry(self):
        from ..models.connections import CVParserBusy
        att, wizard = self._parsed()
        self.applicant.pb_cv_state = 'queued'
        # Isolate the CV leg; other providers are disabled in this fixture.
        with patch.object(type(self.applicant), '_extract_cv', side_effect=CVParserBusy('Busy')):
            self.env['pb.hiring.connection.jobs']._run()
        self.assertEqual(self.applicant.pb_cv_state, 'queued')
        self.assertIn('queued', self.applicant.pb_cv_note)

    def test_busy_http_status_is_retryable_only_for_cv(self):
        from ..models.connections import CVParserBusy
        conn = self._connection('cv')
        response = Mock(status_code=429, content=b'busy')
        with patch('odoo.addons.pb_hiring.models.connections.requests.request', return_value=response):
            with self.assertRaises(CVParserBusy): conn._http('POST', '/extract')
        response.status_code = 503
        with patch('odoo.addons.pb_hiring.models.connections.requests.request', return_value=response):
            with self.assertRaises(CVParserBusy): conn._http('POST', '/extract')
