import json
from datetime import datetime, timedelta
import pytz
from types import SimpleNamespace
from unittest.mock import patch
from odoo import Command, fields
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, AccessError


@tagged('post_install', '-at_install')
class TestPolicy(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'Policy test worker', 'barcode': '991234567',
            'company_id': cls.env.company.id, 'pb_attendance_category': 'worker'})
        cls.template = cls.env['hr.shift.template'].create({'name': 'Policy test long day', 'code': 'TEST-POLICY',
            'company_id': cls.env.company.id, 'start_hour': 7.5, 'end_hour': 20.5, 'break_duration': 1., 'shift_type': 'morning'})
        cls.policy = cls.env['pb.attendance.policy'].create({'name': 'Policy test', 'company_id': cls.env.company.id,
            'tz': 'Asia/Ho_Chi_Minh', 'shift_ids': [Command.create({'template_id': cls.template.id,
            'normal_end_offset': 9., 'break_start_offset': 4., 'break_hours': 1.})],
            'band_ids': [Command.create({'category': category, 'minimum': 0, 'maximum': 10, 'hours': 0, 'confirmed': True}) for category in ('worker','manager')]
            + [Command.create({'category': category, 'minimum': 10, 'open_ended': True, 'hours': hours, 'confirmed': True}) for category,hours in [('worker',4),('manager',1)]]})
        cls.employee.pb_attendance_policy_id = cls.policy
        cls.day = fields.Date.today()-timedelta(days=fields.Date.today().weekday()+7)
        cls.zone = pytz.timezone('Asia/Ho_Chi_Minh')
        cls.start_local = datetime.combine(cls.day, datetime.min.time()).replace(hour=7, minute=30)
        cls.start = cls.zone.localize(cls.start_local).astimezone(pytz.utc).replace(tzinfo=None)
        cls.roster = cls.env['hr.shift.planning'].create({'employee_id': cls.employee.id, 'company_id': cls.env.company.id,
            'shift_template_id': cls.template.id, 'date': cls.day, 'start_datetime': cls.start,
            'end_datetime': cls.start+timedelta(hours=13), 'pb_policy_id': cls.policy.id})
        cls.connector = cls.env['pb.clock.connector'].create({'name': 'Policy test PC', 'company_id': cls.env.company.id,
            'source_group': 'policy-test', 'tz': 'Asia/Ho_Chi_Minh', 'history_from': cls.day})
        for number, dt in enumerate([cls.start_local, cls.start_local+timedelta(hours=13)]):
            cls.env['pb.clock.connector.event'].sudo().create({'connector_id': cls.connector.id,
                'row_hash': 'policy-test-'+str(number), 'state': 'ready', 'user_code': cls.employee.barcode,
                'punch_local': dt, 'raw_json': '{}'})

    def test_preview_and_activation_gate(self):
        self.roster.action_preview_calculation()
        self.assertEqual(self.roster.pb_normal_hours, 8)
        self.assertEqual(self.roster.pb_overtime_hours, 4)
        self.assertFalse(self.roster.pb_attendance_id)
        with self.assertRaises(UserError): self.roster.action_recalculate()
        self.policy.band_ids[0].confirmed = False
        with self.assertRaises(UserError): self.policy.action_activate()

    def test_calculation_weekly_handoff_and_no_double_deduction(self):
        self.policy.action_activate(); self.roster.action_publish(); self.roster.action_recalculate()
        a = self.roster.pb_attendance_id
        self.assertTrue(a)
        self.assertEqual(a.check_in, self.start)
        self.assertEqual(a.check_out, self.start+timedelta(hours=13))
        self.assertEqual(self.env['hr.attendance.weekentry']._att_hours(a), 8)
        self.assertTrue(a._pb_policy_valid(self.day))
        ot = self.env['hr.overtime.request'].search([('pb_policy_roster_id', '=', self.roster.id)])
        self.assertEqual(ot.planned_hours, 4)
        self.assertEqual(ot.state, 'draft')
        self.roster.action_recalculate()
        self.assertEqual(self.env['hr.attendance'].search_count([('pb_policy_roster_id', '=', self.roster.id)]), 1)
        self.assertEqual(self.env['hr.overtime.request'].search_count([('pb_policy_roster_id', '=', self.roster.id)]), 1)
        with self.assertRaises(UserError): a.write({'check_out': a.check_out+timedelta(minutes=1)})
        with self.assertRaises(UserError): self.policy.band_ids[0].write({'hours': 2})
        with self.assertRaises(UserError): self.roster.write({'date': self.day+timedelta(days=1)})

    def test_worker_penalty_and_missing_band(self):
        event = self.env['pb.clock.connector.event'].sudo().search([('connector_id','=',self.connector.id)],order='punch_local',limit=1)
        event.write({'punch_local': self.start_local+timedelta(minutes=10)})
        self.roster.action_preview_calculation()
        self.assertAlmostEqual(self.roster.pb_normal_hours, 8-10/60-4)
        self.assertEqual(self.roster.pb_deduction_hours, 4)

    def test_old_grid_behavior_unchanged(self):
        a = self.env['hr.attendance'].create({'employee_id':self.employee.id,
            'check_in':self.start-timedelta(days=2), 'check_out':self.start-timedelta(days=2)+timedelta(hours=9)})
        self.assertEqual(self.env['hr.attendance.weekentry']._att_hours(a), 9)

    def test_overlapping_roster_rejected(self):
        self.roster.copy({'start_datetime':self.start+timedelta(hours=12), 'end_datetime':self.start+timedelta(hours=20)})
        self.assertIn('overlaps', self.roster._policy_calculate()['error'])

    def test_state_cannot_be_forged(self):
        with self.assertRaises(UserError): self.policy.with_context(_policy_state_action=True).write({'state':'active'})
        with self.assertRaises(AccessError): self.roster.write({'pb_normal_hours':99})

    def test_overnight_payroll_handoff_and_changed_punch_block(self):
        self.template.write({'start_hour': 19.5, 'end_hour': 7.5, 'is_overnight': True})
        start = self.start + timedelta(hours=12)
        self.roster.write({'start_datetime': start, 'end_datetime': start+timedelta(hours=12)})
        events = self.env['pb.clock.connector.event'].search([('connector_id','=',self.connector.id)], order='punch_local')
        events[0].punch_local = self.start_local+timedelta(hours=12)
        events[1].punch_local = self.start_local+timedelta(hours=24)
        self.policy.action_activate(); self.roster.action_publish(); self.roster.action_recalculate()
        a = self.roster.pb_attendance_id
        self.assertEqual(a._pb_local_day(), self.day)
        self.assertEqual(self.roster.pb_normal_hours, 8)
        self.assertEqual(self.roster.pb_overtime_hours, 3)
        ot = self.env['hr.overtime.request'].search([('pb_policy_roster_id','=',self.roster.id)])
        ot.sudo().write({'state': 'approved', 'approved_hours': 3})
        config = self.env['hr.formula.config'].create({'name':'Night handoff test', 'code':'NIGHTHANDOFF',
            'country_code':'VN', 'company_id':self.env.company.id, 'payroll_basis':'timesheet'})
        contract = self.env['hr.contract'].create({'name':'Policy payroll test', 'employee_id':self.employee.id,
            'company_id':self.env.company.id, 'date_start':self.day, 'state':'open', 'wage':2200,
            'resource_calendar_id':self.employee.resource_calendar_id.id})
        cells = [{'date':str(self.day), 'reg':8., 'attendance_ids':a.ids,
            'ot':{'weekday':{'id':ot.id,'hours':3.,'state':'approved'}}}]
        packet = SimpleNamespace(id=999, write_date=datetime.now(), approved_hash='agreed', week_start=self.day,
            _live_stamp=lambda:'agreed', days=lambda:cells)
        cert = {'channels':dict.fromkeys(['leave','overtime','timesheets','adjustments'],True)}
        with patch.object(type(self.env['pb.timesheet.packet']), 'search', return_value=[packet]):
            facts = config._application_time_values(self.employee, contract, self.day, self.day, cert)
            self.assertEqual(facts['period.regular_work_hours']['value'],8)
            self.assertEqual(facts['period.ot.weekday.approved_hours']['value'],3)
            self.assertEqual(facts['period.paid_day_equivalents']['status'],'resolved',facts)
            events[1].punch_local += timedelta(minutes=1)
            facts = config._application_time_values(self.employee, contract, self.day, self.day, cert)
            self.assertEqual(facts['period.paid_day_equivalents']['status'],'conflict')

    def test_sanctioned_correction_recalculates_and_retains_raw(self):
        from odoo.addons.pb_attendance_flow.models.hr_attendance import PB_ATT_CORRECTION_CTX, _CORR_TOKEN
        self.policy.action_activate(); self.roster.action_publish(); self.roster.action_recalculate()
        a = self.roster.pb_attendance_id
        a.with_context(**{PB_ATT_CORRECTION_CTX:_CORR_TOKEN}).write({'check_in':self.start+timedelta(minutes=10)})
        self.assertAlmostEqual(self.roster.pb_normal_hours,8-10/60-4)
        self.assertEqual(a.pb_entry_source,'correction')
        self.assertTrue(a._pb_policy_valid())
        events = self.env['pb.clock.connector.event'].search([('connector_id','=',self.connector.id)],order='punch_local')
        self.assertEqual(events[0].punch_local,self.start_local)
