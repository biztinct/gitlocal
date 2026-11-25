"""WFSETUP P10b — hours from the clocks into pay (proposal WFSETUP_P10A §9).

One synthetic week, Monday to Sunday two weeks ago, stands in for a month:

  Mon  on time 07:30-16:30                      -> 8 h normal, 1 day
  Tue  15 min late 07:45-16:30 (band >=10 = 4 h) -> 3.75 h normal, 0.46875 day
  Wed  on time, out 20:30                        -> 8 h normal + 4 h weekday overtime
  Thu  public holiday, rostered, not worked      -> holiday day 1
  Fri  paid annual leave, rostered, not worked   -> leave day 1
  Sat  on time                                   -> 8 h normal, 1 day
  Sun  rest-day shift worked 07:30-16:30         -> 8 h rest-day overtime,
                                                    4 h within the daily limit
Expected: days worked 3.46875 + leave 1 + holiday 1 = paid days 5.46875;
overtime within the limit 4 + 4 = 8 h; premium 4 x 0.5 + 4 x 1.0 = 6 h;
above the limit 4 h; late 15 min; deducted 4 h; paid normal 27.75 h;
actual 8 + 7.75 + 12 + 8 + 8 = 43.75 h.
"""
import hashlib
import json
from datetime import datetime, time, timedelta

import pytz

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models import clock_source

TZ = 'Asia/Ho_Chi_Minh'


@tagged('post_install', '-at_install', 'wfsetup_p10b')
class TestClockPayroll(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company
        cls.zone = pytz.timezone(TZ)
        cal = cls.company.resource_calendar_id
        cal.tz = TZ
        cls.employee = env['hr.employee'].create({
            'name': 'Clock pay worker', 'barcode': '0770123', 'company_id': cls.company.id,
            'pb_attendance_category': 'worker', 'resource_calendar_id': cal.id, 'tz': TZ})
        cls.template = env['hr.shift.template'].create({
            'name': 'Clock pay day', 'code': 'TEST-CLOCKPAY', 'company_id': cls.company.id,
            'start_hour': 7.5, 'end_hour': 16.5, 'break_duration': 1., 'shift_type': 'morning'})
        bands = []
        for cat, hours in (('worker', 4.), ('manager', 1.)):
            bands += [Command.create({'category': cat, 'minimum': 0, 'maximum': 10, 'hours': 0, 'confirmed': True}),
                      Command.create({'category': cat, 'minimum': 10, 'open_ended': True, 'hours': hours,
                                      'confirmed': True})]
        cls.policy = env['pb.attendance.policy'].create({
            'name': 'Clock pay rules', 'company_id': cls.company.id, 'tz': TZ,
            'capture_before': 2., 'capture_after': 6.,
            'shift_ids': [Command.create({'template_id': cls.template.id, 'normal_end_offset': 9.,
                                          'break_start_offset': 4., 'break_hours': 1.})],
            'band_ids': bands})
        cls.employee.pb_attendance_policy_id = cls.policy
        # explicit rates and limits for this company (most specific row wins)
        Rate = env['hr.overtime.config']
        for kind, mult in (('weekday', 1.5), ('weekend', 2.0), ('holiday', 3.0)):
            Rate.create({'name': 'Clock pay %s' % kind, 'company_id': cls.company.id,
                         'overtime_type': kind, 'rate_multiplier': mult})
        env['pb.ot.ceiling'].create({'name': 'Clock pay limits', 'company_id': cls.company.id,
                                     'daily_cap': 4, 'monthly_cap': 40, 'annual_cap': 200})
        today = fields.Date.today()
        cls.monday = today - timedelta(days=today.weekday() + 14)
        cls.sunday = cls.monday + timedelta(days=6)
        cls.connector = env['pb.clock.connector'].create({
            'name': 'Clock pay PC', 'company_id': cls.company.id, 'source_group': 'clock-pay-test',
            'tz': TZ, 'history_from': cls.monday - timedelta(days=7)})
        cls._n = 0
        cls.shifts = {}
        for offset in range(7):
            day = cls.monday + timedelta(days=offset)
            kind = 'weekend' if offset == 6 else 'weekday'
            cls.shifts[offset] = cls._shift(day, kind)
        cls._punch(0, (7, 30), (16, 30))
        cls._punch(1, (7, 45), (16, 30))
        cls._punch(2, (7, 30), (20, 30))
        cls._punch(5, (7, 30), (16, 30))
        cls._punch(6, (7, 30), (16, 30))
        # Thursday is a public holiday, Friday paid annual leave
        cls.thursday = cls.monday + timedelta(days=3)
        cls.friday = cls.monday + timedelta(days=4)
        env['pb.holidays'].sudo()._create_row(cls.company, cal, 'Clock pay holiday',
                                              cls.thursday, cls.thursday)
        cls.leave_type = env['hr.leave.type'].create({
            'name': 'Clock pay annual leave', 'requires_allocation': False,
            'leave_validation_type': 'no_validation', 'request_unit': 'day',
            'pb_pay_treatment': 'paid', 'pb_pay_funding': 'employer'})
        cls.leave = env['hr.leave'].with_context(leave_skip_state_check=True).create({
            'employee_id': cls.employee.id, 'holiday_status_id': cls.leave_type.id,
            'request_date_from': cls.friday, 'request_date_to': cls.friday})
        if cls.leave.state != 'validate':
            cls.leave.sudo().write({'state': 'validate'})
        cls.policy.action_activate()
        shifts = env['hr.shift.planning'].browse([s.id for s in cls.shifts.values()])
        shifts.action_publish()
        for s in shifts:
            s.action_recalculate()
        reqs = env['hr.overtime.request'].search([('employee_id', '=', cls.employee.id)])
        reqs.action_submit()
        cls.reqs = reqs
        cls.config = cls._scheme()

    # ------------------------------------------------------------ fixtures
    @classmethod
    def _shift(cls, day, kind='weekday'):
        start = cls.zone.localize(datetime.combine(day, time(7, 30))).astimezone(pytz.utc).replace(tzinfo=None)
        return cls.env['hr.shift.planning'].create({
            'employee_id': cls.employee.id, 'company_id': cls.company.id,
            'shift_template_id': cls.template.id, 'date': day, 'start_datetime': start,
            'end_datetime': start + timedelta(hours=9), 'pb_policy_id': cls.policy.id,
            'pb_day_kind': kind})

    @classmethod
    def _event(cls, local_dt, code=None):
        cls._n += 1
        return cls.env['pb.clock.connector.event'].sudo().create({
            'connector_id': cls.connector.id, 'row_hash': 'clock-pay-%s' % cls._n, 'state': 'ready',
            'user_code': code or '770123', 'punch_local': local_dt, 'raw_json': '{}'})

    @classmethod
    def _punch(cls, offset, t_in, t_out):
        day = cls.monday + timedelta(days=offset)
        cls._event(datetime.combine(day, time(*t_in)))
        cls._event(datetime.combine(day, time(*t_out)))

    @classmethod
    def _scheme(cls):
        Rule = cls.env['hr.formula.rule']
        config = cls.env['hr.formula.config'].create({
            'name': 'Clock pay scheme', 'code': 'CLOCKPAYT', 'country_code': 'VN',
            'company_id': cls.company.id})
        spec = [('VNBASIS', 0), ('VNBASE', 250000), ('VNRESP', 20000), ('VNPOS', 0),
                ('VNDIVISOR', 26), ('VNHOURSDAY', 8), ('VNPAIDDAYS', 0), ('VNOTHOURS', 0),
                ('VNPREMHOURS', 0), ('VNSUNDAYHOURS', 0)]
        seq = 10
        cls.rules = {}
        for code, default in spec:
            cls.rules[code] = Rule.create({'config_id': config.id, 'name': code, 'code': code,
                                           'column_type': 'input', 'default_value': default,
                                           'sequence': seq, 'net_role': 'info',
                                           'appears_on_payslip': False})
            seq += 10
        L = {c: r.column_letter for c, r in cls.rules.items()}
        formulas = [
            ('VNDAYRATE', '=IF({VNBASIS}2=1,({VNBASE}2+{VNRESP}2+{VNPOS}2)/{VNDIVISOR}2,{VNBASE}2+{VNRESP}2+{VNPOS}2)'),
            ('VNBASEHOUR', '=IF({VNBASIS}2=1,{VNBASE}2/{VNDIVISOR}2,{VNBASE}2)/{VNHOURSDAY}2'),
        ]
        for code, f in formulas:
            cls.rules[code] = Rule.create({'config_id': config.id, 'name': code, 'code': code,
                                           'column_type': 'formula', 'sequence': seq,
                                           'excel_formula': f.format(**L)})
            seq += 10
            L[code] = cls.rules[code].column_letter
        for code, f in (('VNREGULAR', '={VNDAYRATE}2*{VNPAIDDAYS}2'),
                        ('VNOTPAY', '={VNBASEHOUR}2*{VNOTHOURS}2'),
                        ('VNPREMPAY', '={VNBASEHOUR}2*{VNPREMHOURS}2'),
                        ('VNSUNPAY', '={VNDAYRATE}2/{VNHOURSDAY}2*{VNSUNDAYHOURS}2')):
            cls.rules[code] = Rule.create({'config_id': config.id, 'name': code, 'code': code,
                                           'column_type': 'formula', 'sequence': seq,
                                           'excel_formula': f.format(**L), 'net_role': 'earning'})
            seq += 10
        for code, key in (('VNPAIDDAYS', 'clock.paid_days'), ('VNOTHOURS', 'clock.ot_hours'),
                          ('VNPREMHOURS', 'clock.ot_premium_hours'), ('VNSUNDAYHOURS', 'clock.empty')):
            cls.rules[code].set_source_binding('clock', key)
        for key in ('clock.worked_days', 'clock.paid_leave_days', 'clock.holiday_days',
                    'clock.paid_normal_hours', 'clock.actual_hours', 'clock.late_minutes',
                    'clock.over_limit_hours', 'clock.deduction_hours'):
            config.pb_clock_bind(key, 'new')
        cls.codes = {r.pb_clock_key: r.code for r in config.rule_ids if r.pb_clock_key}
        return config

    def _decide(self, refuse=()):
        for r in self.reqs:
            if r.state != 'submitted':
                continue
            (r.action_refuse if r.date in refuse else r.action_approve)()

    def _batch(self, date_from, date_to):
        return self.env['hr.payroll.import.batch'].create({
            'name': 'Clock pay batch', 'source_type': 'excel', 'formula_config_id': self.config.id,
            'payroll_period': 'custom', 'date_from': date_from, 'date_to': date_to})

    def _raw(self, **extra):
        row = {'VNBASIS': 0, 'VNBASE': 250000, 'VNRESP': 20000, 'VNPOS': 0, 'VNDIVISOR': 26,
               'VNHOURSDAY': 8, 'VNPAIDDAYS': 26, 'VNOTHOURS': 12, 'VNPREMHOURS': 6, 'VNSUNDAYHOURS': ''}
        row.update(extra)
        return row

    def _transform(self, date_from, date_to, raw=None):
        prov = {}
        values = self._batch(date_from, date_to)._transform_data_to_formula_inputs(
            raw or self._raw(), employee=self.employee, provenance=prov)
        return values, prov

    def _clock(self):
        self.config.pb_clock_from = self.monday

    # ------------------------------------------------------------ 1 neutrality
    def test_01_neutral_without_date_and_before_it(self):
        self._decide()
        before = clock_source.BRANCH_COUNTER['entered']
        v0, p0 = self._transform(self.monday, self.sunday)          # no clock date
        self.config.pb_clock_from = self.sunday + timedelta(days=1)   # period before the date
        v1, p1 = self._transform(self.monday, self.sunday)
        keys = self.config.rule_ids.filtered('pb_clock_key')
        for r in keys:
            r.clear_source_binding('clock')                         # no clock keys at all
        self.config.pb_clock_from = False
        v2, p2 = self._transform(self.monday, self.sunday)
        md5 = lambda v, p: hashlib.md5(json.dumps([v, p], sort_keys=True, default=str).encode()).hexdigest()
        self.assertEqual(md5(v0, p0), md5(v1, p1))
        self.assertEqual(md5(v0, p0), md5(v2, p2))
        self.assertEqual(v0['VNPAIDDAYS'], 26)
        self.assertEqual(clock_source.BRANCH_COUNTER['entered'], before, 'clock branch must not be entered')

    # ------------------------------------------------------------ 2 + 3 + 14 the worked week
    def test_02_worked_week_and_file_values_shown_beside(self):
        self._decide()
        self._clock()
        values, prov = self._transform(self.monday, self.sunday)
        c = self.codes
        self.assertAlmostEqual(values['VNPAIDDAYS'], 5.46875)
        self.assertAlmostEqual(values[c['clock.worked_days']], 3.46875)
        self.assertAlmostEqual(values[c['clock.paid_leave_days']], 1.0)
        self.assertAlmostEqual(values[c['clock.holiday_days']], 1.0)
        self.assertAlmostEqual(values['VNOTHOURS'], 8.0)            # within the limit only (R14)
        self.assertAlmostEqual(values['VNPREMHOURS'], 6.0)
        self.assertAlmostEqual(values[c['clock.over_limit_hours']], 4.0)
        self.assertAlmostEqual(values[c['clock.late_minutes']], 15.0)
        self.assertAlmostEqual(values[c['clock.deduction_hours']], 4.0)
        self.assertAlmostEqual(values[c['clock.paid_normal_hours']], 27.75)
        self.assertAlmostEqual(values[c['clock.actual_hours']], 43.75)
        entry = prov['VNPAIDDAYS']
        self.assertEqual((entry['src'], entry['key'], entry['via']), ('employee_field', 'clock.paid_days', 'clock'))
        self.assertEqual(entry['ignored']['value'], 26)              # the file's number, kept beside
        self.assertEqual(prov['VNOTHOURS']['ignored']['value'], 12)
        # the pay: day rate 270,000 x 5.46875; hourly 31,250 x 8 and x 6
        slip = self.env['hr.payslip'].new({'employee_id': self.employee.id})
        rules = self.config.rule_ids.sorted('sequence')
        out, _log = slip._evaluate_rules_with_dependencies(rules, dict(values))
        self.assertAlmostEqual(out['VNREGULAR'], 270000 * 5.46875)
        self.assertAlmostEqual(out['VNOTPAY'], 31250 * 8)
        self.assertAlmostEqual(out['VNPREMPAY'], 31250 * 6)
        self.assertAlmostEqual(out['VNSUNPAY'], 0.0)

    # ------------------------------------------------------------ 4 crossing
    def test_04_period_crossing_the_date_refused(self):
        self.config.pb_clock_from = self.monday + timedelta(days=2)
        with self.assertRaisesRegex(UserError, 'Split it at that date'):
            self._transform(self.monday, self.sunday)

    # ------------------------------------------------------------ 5 + 6 overtime decisions
    def test_05_undecided_overtime_refused_then_computes(self):
        self._clock()
        with self.assertRaisesRegex(UserError, 'Overtime waiting for a decision'):
            self._transform(self.monday, self.sunday)
        self._decide(refuse=(self.monday + timedelta(days=6),))     # refuse Sunday's
        values, _prov = self._transform(self.monday, self.sunday)
        self.assertAlmostEqual(values['VNOTHOURS'], 4.0)            # refused = 0, not a blocker
        self.assertAlmostEqual(values['VNPREMHOURS'], 2.0)
        self.assertAlmostEqual(values[self.codes['clock.over_limit_hours']], 0.0)

    # ------------------------------------------------------------ 7 one punch / none
    def test_07_one_punch_refused_zero_punches_absent(self):
        self._decide()
        self._clock()
        extra = self._shift(self.monday - timedelta(days=7))           # outside the period: ignored
        extra.action_publish()
        values, _p = self._transform(self.monday, self.sunday)
        self.assertAlmostEqual(values['VNPAIDDAYS'], 5.46875)
        self._event(datetime.combine(self.friday, time(7, 31)))          # one punch on the leave day
        with self.assertRaises(UserError) as cm:
            self._transform(self.monday, self.sunday)
        self.assertIn('Only one clock-in on a shift', str(cm.exception))
        facts = self.env['pb.clock.payroll'].facts_many(self.employee, self.monday, self.sunday)
        self.assertIn(str(self.thursday), facts[self.employee.id]['absent'])

    # ------------------------------------------------------------ 8 + 9 punches with no shift, loose attendance
    def test_08_punches_without_shift_refused(self):
        self._decide()
        self._clock()
        self._event(datetime.combine(self.monday + timedelta(days=2), time(23, 50)))   # after Wed's window
        facts = self.env['pb.clock.payroll'].facts_many(self.employee, self.monday, self.sunday)
        codes = [b['code'] for b in facts[self.employee.id]['blockers']]
        self.assertIn('no_shift_punch', codes)

    def test_09_attendance_outside_a_shift_refused(self):
        self._decide()
        self._clock()
        start = self.zone.localize(datetime.combine(self.monday, time(23, 0))).astimezone(pytz.utc).replace(tzinfo=None)
        self.env['hr.attendance'].create({'employee_id': self.employee.id, 'check_in': start,
                                          'check_out': start + timedelta(minutes=30)})
        with self.assertRaisesRegex(UserError, 'Clock hours outside a shift'):
            self._transform(self.monday, self.sunday)

    # ------------------------------------------------------------ 10 Sunday column
    def test_10_sunday_column_must_be_empty(self):
        self._decide()
        self._clock()
        with self.assertRaisesRegex(UserError, 'must be empty in months paid from the clocks'):
            self._transform(self.monday, self.sunday, raw=self._raw(VNSUNDAYHOURS=8))

    # ------------------------------------------------------------ 11 information stays information
    def test_11_info_never_in_a_formula_and_no_late_column(self):
        info = self.config.rule_ids.filtered(lambda r: r.pb_clock_key == 'clock.actual_hours')
        with self.assertRaises(ValidationError):
            self.env['hr.formula.rule'].create({
                'config_id': self.config.id, 'name': 'Bad', 'code': 'BADUSE', 'column_type': 'formula',
                'sequence': 999, 'excel_formula': '=%s2*2' % info.column_letter})
        with self.assertRaises(ValidationError):
            info.write({'net_role': 'earning'})
        self._clock()
        with self.assertRaisesRegex(ValidationError, 'Late minutes are already taken off'):
            self.env['hr.formula.rule'].create({'config_id': self.config.id, 'name': 'Late', 'code': 'LATEMIN',
                                                'column_type': 'input', 'sequence': 998})

    # ------------------------------------------------------------ 12 stamp
    def test_12_stamp_refuses_approval_after_a_change(self):
        self._decide()
        self._clock()
        values, prov = self._transform(self.monday, self.sunday)
        slip = self.env['hr.payslip'].create({
            'name': 'Clock pay slip', 'employee_id': self.employee.id, 'date_from': self.monday,
            'date_to': self.sunday, 'formula_config_id': self.config.id,
            'formula_input_values': json.dumps(values), 'formula_input_sources': json.dumps(prov)})
        self.assertTrue(slip.pb_clock_stamp)
        slip.write({'state': 'verify'})                               # unchanged: allowed
        slip.write({'state': 'draft'})
        ot = self.reqs.filtered(lambda r: r.date == self.monday + timedelta(days=2))
        ot._ot_chain().write({'approved_hours': 3.0})                 # hours changed after computing
        with self.assertRaisesRegex(UserError, 'Clock hours changed after these payslips were computed'):
            slip.write({'state': 'verify'})

    # ------------------------------------------------------------ 13 period edges
    def test_13_shift_before_period_not_counted(self):
        self._decide()
        self._clock()
        values, _p = self._transform(self.monday + timedelta(days=1), self.sunday)
        self.assertAlmostEqual(values[self.codes['clock.worked_days']], 2.46875)  # Monday left out

    # ------------------------------------------------------------ 18 file-less recompute
    def test_18_file_less_resolver_applies_clock(self):
        self._decide()
        self._clock()
        slip = self.env['hr.payslip'].create({
            'name': 'Clock pay slip 2', 'employee_id': self.employee.id, 'date_from': self.monday,
            'date_to': self.sunday, 'formula_config_id': self.config.id})
        prov = {}
        values = slip._get_formula_input_values(self.config, provenance=prov)
        self.assertAlmostEqual(values['VNPAIDDAYS'], 5.46875)
        self.assertEqual(prov['VNPAIDDAYS']['via'], 'clock')
        self.assertNotIn('ignored', prov['VNPAIDDAYS'])

    # ------------------------------------------------------------ readiness + leave rules
    def test_19_readiness_groups_and_leave_on_a_worked_day(self):
        self._clock()
        panel = self.env['pb.clock.payroll'].readiness(self.config, self.employee, self.monday, self.sunday)
        self.assertTrue(panel['active'])
        self.assertEqual(panel['attention'], 1)
        self.assertEqual([g['code'] for g in panel['groups']], ['ot_pending'])
        text = self.env['pb.clock.payroll'].refusal_text(panel)
        self.assertIn("can't be worked out yet", text)
        self._decide()
        panel = self.env['pb.clock.payroll'].readiness(self.config, self.employee, self.monday, self.sunday)
        self.assertEqual((panel['ready'], panel['attention']), (1, 0))
        # time off on a day with clock-ins
        leave2 = self.env['hr.leave'].with_context(leave_skip_state_check=True).create({
            'employee_id': self.employee.id, 'holiday_status_id': self.leave_type.id,
            'request_date_from': self.monday, 'request_date_to': self.monday})
        if leave2.state != 'validate':
            leave2.sudo().write({'state': 'validate'})
        facts = self.env['pb.clock.payroll'].facts_many(self.employee, self.monday, self.sunday)
        self.assertIn('leave_worked', [b['code'] for b in facts[self.employee.id]['blockers']])

    def test_20_unconfigured_leave_type_blocks(self):
        self._decide()
        self._clock()
        self.leave_type.write({'pb_pay_treatment': 'unconfigured', 'pb_pay_funding': 'unconfigured'})
        with self.assertRaisesRegex(UserError, 'Time off type not set as paid or unpaid'):
            self._transform(self.monday, self.sunday)

    def test_late_day_source_counts_days_not_minutes(self):
        self._decide()
        self._clock()
        facts=self.env['pb.clock.payroll'].facts_many(self.employee,self.monday,self.sunday,live=True)
        self.assertEqual(facts[self.employee.id]['facts']['clock.late_days']['value'],1)
        self.assertEqual(clock_source.CLOCK_USE['clock.late_days'],'pay')
        rule=self.env['hr.formula.rule'].create({'config_id':self.config.id,'name':'Late days for allowance',
            'code':'LATEDAYS','column_type':'input','net_role':'info','appears_on_payslip':False})
        self.config.pb_clock_bind('clock.late_days',rule.id)
        values,_=self._transform(self.monday,self.sunday)
        self.assertEqual(values['LATEDAYS'],1)
