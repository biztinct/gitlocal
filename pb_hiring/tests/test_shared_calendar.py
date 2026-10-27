"""End-to-end source permissions; test transactions and mail are rolled back."""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from .test_interviews import InterviewCase


@tagged('post_install', '-at_install', 'shared_calendar')
class TestSharedCalendar(InterviewCase):
    def setUp(self):
        super().setUp()
        self.start = self._tomorrow().replace(hour=0)
        self.stop = self.start + timedelta(days=7)
        self.employee = self._person_user('employee', ['base.group_user'])
        self.payroll = self._person_user('payroll', ['base.group_user',
            'om_hr_payroll.group_hr_payroll_user', 'pb_hr_payroll_formula.group_formula_user'])
        self.other_payroll = self._person_user('payroll2', ['base.group_user', 'om_hr_payroll.group_hr_payroll_user'])
        self.Dates = self.env['pb.payroll.calendar.date']
        self.deadline = self.Dates.create({'name': 'Restricted payroll approval',
            'date': self.start.date(), 'company_id': self.company.id,
            'user_ids': [(6, 0, self.payroll.ids)], 'kind': 'approval'})

    def _person_user(self, name, groups):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Calendar test '+name, 'login': 'calendar.test.'+name,
            'company_id': self.company.id, 'company_ids': [(6,0,self.company.ids)],
            'group_ids': [(6,0,[self.env.ref(g).id for g in groups])]})

    def _api(self, user):
        return self.env['pb.shared.calendar'].with_user(user).with_context(allowed_company_ids=self.company.ids)

    def _events(self, user):
        return self._api(user).events(str(self.start), str(self.stop))['events']

    def _meeting(self, owner=None, attendees=None):
        owner = owner or self.employee
        return self.env['calendar.event'].with_context(dont_notify=True, no_mail_to_attendees=True).create({
            'name': 'Private finance discussion', 'start': self.start + timedelta(hours=10),
            'stop': self.start + timedelta(hours=11), 'user_id': owner.id, 'privacy': 'private',
            'partner_ids': [(6,0,(attendees or owner).partner_id.ids)]})

    def test_recruiter_has_no_payroll_source_or_records(self):
        self.assertFalse(self._api(self.recruiter).capabilities()['payroll'])
        self.assertFalse(any(e['source'] == 'payroll' for e in self._events(self.recruiter)))
        for op in [lambda: self._api(self.recruiter).open_record('deadline:%s' % self.deadline.id),
                   lambda: self._api(self.recruiter).payroll_dates_action(),
                   lambda: self.deadline.with_user(self.recruiter).read(['name']),
                   lambda: self.Dates.with_user(self.recruiter).search_count([])]:
            with self.assertRaises(AccessError): op()

    def test_payroll_named_team(self):
        self.assertIn('deadline:%s' % self.deadline.id, [e['key'] for e in self._events(self.payroll)])
        self.assertNotIn('deadline:%s' % self.deadline.id, [e['key'] for e in self._events(self.other_payroll)])
        with self.assertRaises(AccessError): self.deadline.with_user(self.other_payroll).read(['name'])

    def test_company_payroll_audience_does_not_mean_all_employees(self):
        self.deadline.company_wide = True
        self.assertIn('deadline:%s' % self.deadline.id, [e['key'] for e in self._events(self.other_payroll)])
        self.assertNotIn('deadline:%s' % self.deadline.id, [e['key'] for e in self._events(self.employee)])

    def test_cross_company_deadline_hidden_even_if_assigned(self):
        other = self.env['res.company'].create({'name': 'Calendar other company'})
        self.deadline.company_id = other
        self.assertNotIn('deadline:%s' % self.deadline.id, [e['key'] for e in self._events(self.payroll)])
        with self.assertRaises(AccessError): self._api(self.payroll).open_record('deadline:%s' % self.deadline.id)

    def test_employee_cannot_create_payroll_deadline(self):
        with self.assertRaises(AccessError): self.Dates.with_user(self.employee).create({'name':'Leak','date':self.start.date()})

    def test_no_empty_payroll_audience(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.Dates.create({'name':'No audience','date':self.start.date(),'user_ids':[(5,0,0)]})

    def test_interview_visible_to_panel_but_not_unrelated_employee(self):
        iv = self._schedule(start=self.start + timedelta(hours=10))
        key = 'interview:%s' % iv.id
        self.assertIn(key, [e['key'] for e in self._events(self.panel_user)])
        self.assertIn(key, [e['key'] for e in self._events(self.recruiter)])
        self.assertNotIn(key, [e['key'] for e in self._events(self.employee)])
        self.assertNotIn(key, [e['key'] for e in self._events(self.payroll)])
        with self.assertRaises(AccessError): self._api(self.employee).open_record(key)

    def test_linked_interview_not_duplicated_as_meeting(self):
        iv = self._schedule(start=self.start + timedelta(hours=10))
        rows = self._events(self.recruiter)
        self.assertEqual(sum(e['key'] == 'interview:%s' % iv.id for e in rows), 1)
        self.assertFalse(any(e['key'] == 'event:%s' % iv.event_id.id for e in rows))

    def test_private_meeting_hidden_in_feed_and_raw_rpc(self):
        event = self._meeting()
        self.assertNotIn('event:%s' % event.id,[e['key'] for e in self._events(self.recruiter)])
        self.assertFalse(event.with_user(self.recruiter).search([('id','=',event.id)]))
        with self.assertRaises(AccessError): event.with_user(self.recruiter).read(['name'])
        with self.assertRaises(AccessError): self._api(self.recruiter).open_record('event:%s' % event.id)

    def test_invitee_reads_but_cannot_write_meeting(self):
        event = self._meeting(attendees=self.employee | self.recruiter)
        row = next(e for e in self._events(self.recruiter) if e['key'] == 'event:%s' % event.id)
        self.assertFalse(row['editable'])
        with self.assertRaises(AccessError): event.with_user(self.recruiter).write({'name':'Changed'})
        with self.assertRaises(AccessError): event.with_user(self.recruiter).unlink()
        event.with_user(self.employee).write({'name':'Owner edit'})
        self.assertEqual(event.name,'Owner edit')

    def test_attendee_metadata_not_discoverable(self):
        event = self._meeting()
        attendees = self.env['calendar.attendee'].with_user(self.recruiter).search([('event_id','=',event.id)])
        self.assertFalse(attendees)

    def test_payroll_dates_never_generate_external_events(self):
        before = self.env['calendar.event'].search_count([])
        self._events(self.payroll)
        self.assertEqual(before,self.env['calendar.event'].search_count([]))

    def test_direct_unknown_and_large_range_rejected(self):
        with self.assertRaises(UserError): self._api(self.employee).events('2026-01-01','2027-01-01')
        with self.assertRaises(UserError): self._api(self.employee).open_record('hr.payslip:1')
        with self.assertRaises(UserError): self._api(self.employee).events(str(self.stop),str(self.start))

    def test_portal_refused(self):
        portal = self._person_user('portal',['base.group_portal'])
        for method in [lambda: self._api(portal).capabilities(),lambda:self._events(portal),lambda:self._api(portal).new_event()]:
            with self.assertRaises(AccessError):method()

    def test_provider_setup_not_for_recruiter(self):
        with self.assertRaises(AccessError): self._api(self.recruiter).settings_action()
        with self.assertRaises(UserError): self._api(self.employee).provider_action('anything','resume')

    def test_connection_status_has_no_secrets(self):
        payload = self._api(self.employee).capabilities()
        self.assertEqual(set(payload['connections']),{'google_calendar','microsoft_calendar'})
        self.assertNotIn('token',json.dumps(payload));self.assertNotIn('secret',json.dumps(payload))

    def test_two_active_sync_destinations_refused(self):
        with patch.object(type(self.env.user),'check_synchronization_status',return_value={'google_calendar':'sync_stopped','microsoft_calendar':'sync_active'}):
            with self.assertRaises(UserError): self._api(self.employee).provider_action('google','resume')

    def test_new_meeting_defaults_to_self_and_private(self):
        action = self._api(self.employee).new_event()
        self.assertEqual(action['context']['default_user_id'],self.employee.id)
        self.assertEqual(action['context']['default_privacy'],'private')

    def test_calendar_available_to_hiring_only(self):
        self.recruiter.write({'group_ids':[(4,self.env.ref('pb_hiring.group_hiring_only').id)]})
        visibility = self.env['pb.sidebar.item'].visibility_for(self.recruiter)
        self.assertEqual(visibility['items'][self.env.ref('pb_hiring.item_shared_calendar').id],'on')

    def test_local_date_only_payroll_boundary(self):
        rows = self._api(self.payroll).events(str(self.start-timedelta(hours=11)),str(self.stop-timedelta(hours=11)),str(self.start.date()),str(self.stop.date()))['events']
        self.assertIn('deadline:%s' % self.deadline.id,[e['key'] for e in rows])
        with self.assertRaises(UserError): self._api(self.payroll).events(str(self.start),str(self.stop),'2020-01-01','2020-01-07')

    def test_saved_payroll_rules_only(self):
        if 'pb.formula.blueprint' not in self.env:self.skipTest('Payroll blueprint not installed')
        config = self.env['hr.formula.config'].create({'name':'Calendar scheme','code':'CAL_TEST','country_code':'VN','company_id':self.company.id})
        # Fixture bypasses publish workflow, not runtime permissions.
        self.env.cr.execute('UPDATE hr_formula_config SET state=%s WHERE id=%s',['active',config.id]);config.invalidate_recordset(['state'])
        bp = self.env['pb.formula.blueprint'].create({'config_id':config.id,'token':'calendar-test','calendar_json':'{}'})
        api = self._api(self.payroll)
        rows = api.events('2026-11-01','2026-12-01')['events']
        self.assertFalse(any(e['key'].startswith('scheme:%s:'%config.id) for e in rows))
        bp.calendar_json = json.dumps({'calendar':{'payday_rule':'fixed','payday_day':25,'cutoff_rule':'fixed','cutoff_day':20}})
        rows = api.events('2026-11-01','2026-12-01')['events']
        own = [e for e in rows if e['key'].startswith('scheme:%s:'%config.id)]
        self.assertEqual(len(own),2)
        self.assertTrue(all(e['source']=='payroll' for e in own))
        self.assertFalse(any(e['key'].startswith('scheme:%s:'%config.id) for e in self._api(self.recruiter).events('2026-11-01','2026-12-01')['events']))

    def test_all_day_end_is_exclusive_for_calendar_renderer(self):
        event = self._meeting()
        event.write({'allday':True,'start_date':self.start.date(),'stop_date':(self.start+timedelta(days=2)).date()})
        row = next(e for e in self._events(self.employee) if e['key']=='event:%s'%event.id)
        self.assertEqual(row['start'],str(self.start.date()))
        self.assertEqual(row['stop'],str((self.start+timedelta(days=3)).date()))
        self.assertTrue(row['allday'])
