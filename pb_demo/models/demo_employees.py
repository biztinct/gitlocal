# -*- coding: utf-8 -*-
"""Employee & contract population (extends pb.demo.generator) — single Vietnam.

Division is stored as the KHOI key on hr.employee.division (the Formula Engine
input that drives division-specific allowances). Contracts carry NO struct_id —
payroll is computed by the formula configs, not salary structures.
"""
import logging
import random
from datetime import datetime, date, time, timedelta

from dateutil.relativedelta import relativedelta
from pytz import timezone, utc

from odoo import api, fields, models

from . import demo_catalog as cat
from .demo_history import _HISTORY_YEAR, _OPEN_MONTH

_logger = logging.getLogger(__name__)

# Two persistent under-18 demo employees for the Young Worker Guard story.
# Ages are anchored to `today` (never absolute), so the 17- and 14-year-old
# never age out of their VN bands. Each is seeded one over-week-cap attendance
# week: weekly hours = days × week_hours EXCEEDS the band cap (40 h for 15–<18,
# 20 h for <15) while every single day stays under the daily cap + grace, so the
# hard per-day attendance constraint accepts the punches and check_period still
# reports a `week_cap` violation.
_YW_DEMOS = [
    {'name': 'Demo Minor 17 (Young Worker)', 'years': 17, 'sex': 'male',
     'wage': 5000000, 'week_hours': 7.0, 'days': 6},   # 42 h > 40 h week cap
    {'name': 'Demo Minor 14 (Young Worker)', 'years': 14, 'sex': 'female',
     'wage': 4000000, 'week_hours': 4.0, 'days': 6},   # 24 h > 20 h week cap
]

_SURNAMES = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Huỳnh', 'Phan', 'Vũ', 'Võ',
             'Đặng', 'Bùi', 'Đỗ', 'Hồ', 'Ngô', 'Dương', 'Lý', 'Đào', 'Đoàn', 'Vương', 'Trịnh']
_MID_M = ['Văn', 'Hữu', 'Đức', 'Minh', 'Quang', 'Thanh', 'Công', 'Xuân', 'Bá', 'Đình', 'Tiến', 'Mạnh', 'Ngọc', 'Thành', 'Anh']
_MID_F = ['Thị', 'Thu', 'Thanh', 'Ngọc', 'Kim', 'Hồng', 'Phương', 'Mỹ', 'Diễm', 'Quỳnh', 'Bích', 'Hà', 'Lan', 'Yến', 'Khánh']
_GIVEN_M = ['An', 'Bình', 'Cường', 'Dũng', 'Hải', 'Hùng', 'Khoa', 'Long', 'Nam', 'Phúc', 'Quân', 'Sơn', 'Tâm', 'Tuấn', 'Việt', 'Hoàng', 'Bảo', 'Đạt', 'Khang', 'Trí']
_GIVEN_F = ['Anh', 'Chi', 'Dung', 'Hà', 'Hương', 'Lan', 'Linh', 'Mai', 'Ngân', 'Như', 'Oanh', 'Phương', 'Quyên', 'Thảo', 'Trang', 'Vy', 'Yến', 'Hằng', 'Nhi', 'Trâm']
_BANKS = ['Vietcombank', 'BIDV', 'VietinBank', 'Techcombank', 'MB Bank', 'ACB', 'VPBank', 'Sacombank', 'TPBank', 'Agribank']


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)
    pb_grade = fields.Char(string='Grade')
    pb_performance_rating = fields.Selection([
        ('1', '1 - Needs Improvement'), ('2', '2 - Developing'), ('3', '3 - Meets Expectations'),
        ('4', '4 - Exceeds Expectations'), ('5', '5 - Outstanding'),
    ], string='Performance Rating')


class PbDemoGenerator(models.TransientModel):
    _inherit = 'pb.demo.generator'

    def _ensure_foundation(self):
        if not self.resolve_config('retail', 'end'):
            self.action_build_foundation()

    def _ensure_contract_type(self):
        CT = self.env['hr.contract.type'].sudo()
        return (CT.search([('name', '=', 'Permanent')], limit=1) or CT.search([], limit=1)
                or CT.create({'name': 'Permanent'}))

    def _ensure_jobs(self, company, dept, titles):
        Job = self.env['hr.job'].sudo()
        jobs = {}
        for t in titles:
            j = Job.search([('name', '=', t), ('company_id', '=', company.id)], limit=1) \
                or Job.create({'name': t, 'company_id': company.id, 'department_id': dept.id})
            jobs[t] = j
        return jobs

    def _person(self, rnd, female):
        surname = rnd.choice(_SURNAMES)
        mid, given = (rnd.choice(_MID_F), rnd.choice(_GIVEN_F)) if female else (rnd.choice(_MID_M), rnd.choice(_GIVEN_M))
        return '%s %s %s' % (surname, mid, given)

    def _grade_index(self, rnd, n):
        weights = [40, 28, 18, 9, 5][:n]
        weights += [max(2, weights[-1] // 2)] * (n - len(weights))
        return rnd.choices(range(n), weights=weights[:n])[0]

    # -------------------------------------------------------------- generation
    def generate_employees(self):
        self = self.with_context(**self._GEN_CTX)
        self._ensure_foundation()
        self.clean_demo_employees()
        ct = self._ensure_contract_type()
        Employee = self.env['hr.employee'].sudo()
        Contract = self.env['hr.contract'].sudo()
        Loan = self.env['hr.loan'].sudo()
        today = fields.Date.context_today(self)
        group = self.get_group_company()
        vn_calendar = self.get_calendar(group)
        vn_country = self.env.ref('base.vn').id
        total = 0

        for key, dv in cat.DIVISIONS.items():
            rnd = random.Random('pb_demo_%s' % key)
            count = max(1, int(round(dv['headcount'] * (self.headcount_factor or 1.0))))
            parent_dept = self.get_division_dept(group, key)
            jobs = self._ensure_jobs(group, parent_dept, dv['jobs'])
            cc_depts = {cc: self.get_cost_centre_dept(parent_dept, cc) for cc in dv['cost_centres']}
            grades = dv['grades']
            female_ratio = cat.FEMALE_RATIO.get(key, 0.4)
            managers, created = [], []
            for i in range(count):
                female = rnd.random() < female_ratio
                gi = self._grade_index(rnd, len(grades))
                gname, wmin, wmax = grades[gi]
                wage = round(rnd.uniform(wmin, wmax) / 100000) * 100000
                cc = rnd.choice(dv['cost_centres'])
                title = dv['jobs'][min(gi, len(dv['jobs']) - 1)]
                join = today - relativedelta(months=rnd.randint(1, 84), days=rnd.randint(0, 27))
                full_name = self._person(rnd, female)
                ins_code = 'VN%s' % ''.join(rnd.choice('0123456789') for _ in range(10))
                emp = Employee.create({
                    'name': full_name, 'sex': 'female' if female else 'male',
                    'birthday': today - relativedelta(years=rnd.randint(21, 57), days=rnd.randint(0, 364)),
                    'company_id': group.id, 'department_id': cc_depts[cc].id,
                    'job_id': jobs[title].id, 'job_title': title, 'country_id': vn_country,
                    'is_demo': True, 'pb_grade': gname,
                    'pb_performance_rating': str(rnd.choices(range(1, 6), weights=[5, 15, 45, 25, 10])[0]),
                    'division': key,  # KHOI input value
                    'date_of_joining': join, 'bank_name': rnd.choice(_BANKS),
                    'account_number': ''.join(rnd.choice('0123456789') for _ in range(12)),
                    'insurance_code': ins_code, 'subject_to_pit': 'YES',
                })
                Contract.create({
                    'name': 'Contract - %s' % full_name, 'employee_id': emp.id,
                    'company_id': group.id, 'wage': wage, 'struct_id': False,
                    'date_start': join, 'state': 'open',
                    'resource_calendar_id': vn_calendar.id, 'type_id': ct.id,
                    'schedule_pay': 'monthly', 'costcenter': cc,
                    'dependents': rnd.choices([0, 1, 2, 3], weights=[45, 30, 18, 7])[0],
                    'social_security_number': ins_code,
                    'tax_identification_number': ''.join(rnd.choice('0123456789') for _ in range(10)),
                })
                created.append((emp, gi))
                if gi >= 3:
                    managers.append(emp)
                if rnd.random() < 0.14:
                    principal = round(rnd.uniform(20000000, 120000000) / 1000000) * 1000000
                    mths = rnd.choice([6, 12, 18, 24, 36])
                    # keep the monthly installment realistic — never let a loan swallow
                    # more than 30% of basic pay (otherwise net can go negative).
                    raw_inst = round(principal / mths / 100000) * 100000
                    inst = min(raw_inst, round(wage * 0.30 / 100000) * 100000)
                    Loan.create({'employee_id': emp.id, 'company_id': group.id,
                                 'loan_type': rnd.choice(['personal', 'housing', 'vehicle', 'emergency', 'education']),
                                 'principal_amount': principal,
                                 'installment_amount': inst,
                                 'total_months': mths, 'paid_months': rnd.randint(0, mths - 1),
                                 'date_start': join + relativedelta(months=rnd.randint(0, 12)), 'is_demo': True})
            if managers:
                for emp, gi in created:
                    if gi < 3:
                        emp.parent_id = rnd.choice(managers).id
                parent_dept.manager_id = managers[-1].id
            total += count
            _logger.info('pb_demo: %s employees for division %s', count, key)
            self.env.cr.commit()
            self.env.invalidate_all()

        self.ensure_young_worker_demos()

        _logger.info('pb_demo: total ~%s employees generated.', total)
        return total

    # ---------------------------------------------------- young-worker demos
    def ensure_young_worker_demos(self):
        """Create/adopt the two named under-18 demo employees (Retail division).

        Idempotent and name-keyed: it ADOPTS any pre-existing hand-made record of
        the same name (flipping it to is_demo=True so a regen owns and rebuilds
        it) or creates it fresh. Each gets a running contract — so they enter the
        Retail division run — and one seeded over-week-cap attendance week in the
        open payroll month, which surfaces both in the Guard cockpit feed and the
        Run Payroll advisory step. Called from generate_employees(); safe to call
        standalone.
        """
        self = self.with_context(**self._GEN_CTX)
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        Contract = self.env['hr.contract'].sudo().with_context(active_test=False)
        Att = self.env['hr.attendance'].sudo()
        today = fields.Date.context_today(self)
        group = self.get_group_company()
        vn_calendar = self.get_calendar(group)
        # tz the young-worker checker reads a punch's local day in (calendar first)
        tz = timezone(vn_calendar.tz or 'Asia/Ho_Chi_Minh')
        vn_country = self.env.ref('base.vn').id
        ct = self._ensure_contract_type()
        key = 'retail'
        parent_dept = self.get_division_dept(group, key)
        cc = cat.DIVISIONS[key]['cost_centres'][0]
        dept = self.get_cost_centre_dept(parent_dept, cc) or parent_dept
        contract_start = date(_HISTORY_YEAR, 1, 1)
        # Monday of a fully-past complete ISO week inside the open payroll month
        # (June 8 2026 = Monday of ISO week 24). All seeded days stay in one week.
        week_monday = date(_HISTORY_YEAR, _OPEN_MONTH, 8)

        created = Employee.browse()
        for spec in _YW_DEMOS:
            vals = {
                'name': spec['name'], 'sex': spec['sex'],
                'birthday': today - relativedelta(years=spec['years'], months=6),
                'company_id': group.id, 'department_id': dept.id,
                'job_title': 'Trainee', 'country_id': vn_country,
                'is_demo': True, 'active': True, 'division': key,
                'date_of_joining': contract_start, 'subject_to_pit': 'YES',
            }
            emp = Employee.search([('name', '=', spec['name'])], limit=1)
            if emp:
                emp.write(vals)
            else:
                emp = Employee.create(vals)
            created |= emp

            if not Contract.search_count([('employee_id', '=', emp.id)]):
                Contract.create({
                    'name': 'Contract - %s' % spec['name'], 'employee_id': emp.id,
                    'company_id': group.id, 'wage': spec['wage'], 'struct_id': False,
                    'date_start': contract_start, 'state': 'open',
                    'resource_calendar_id': vn_calendar.id, 'type_id': ct.id,
                    'schedule_pay': 'monthly', 'costcenter': cc,
                })

            # One over-week-cap week — each day legal, week total over cap.
            for off in range(spec['days']):
                d = week_monday + timedelta(days=off)
                ci = tz.localize(datetime.combine(d, time(9, 0))).astimezone(utc).replace(tzinfo=None)
                co = ci + timedelta(hours=spec['week_hours'])
                if not Att.search_count([('employee_id', '=', emp.id), ('check_in', '=', ci)]):
                    Att.create({'employee_id': emp.id, 'check_in': ci, 'check_out': co})

        _logger.info('pb_demo: ensured %s young-worker demo employees.', len(created))
        return created

    # ----------------------------------------------------------------- cleanup
    def clean_demo_employees(self):
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        emps = Employee.search([('is_demo', '=', True)])
        if emps:
            slips = self.env['hr.payslip'].sudo().search([('employee_id', 'in', emps.ids)])
            runs = slips.mapped('payslip_run_id')
            if slips:
                slips.write({'state': 'cancel'})
                slips.unlink()
            if runs:
                runs.write({'state': 'draft'})
                runs.with_context(active_test=False).unlink()
            self.env['hr.loan'].sudo().search([('is_demo', '=', True)]).unlink()
            self.env['hr.contract'].sudo().with_context(active_test=False).search(
                [('employee_id', 'in', emps.ids)]).unlink()
            # Phase-I demo residue tied to these employees — a required
            # employee_id would otherwise block the unlink (OT requests), and
            # self-service records should not survive a regen.
            # Phase-K workforce residue: shifts + business trips carry a REQUIRED
            # employee_id (ondelete restrict), so they must be unlinked before
            # the employees. Attendance cascades on the employee unlink.
            for _model in ('hr.overtime.request', 'pb.profile.change.request',
                           'pb.employee.document', 'hr.shift.planning',
                           'pb.business.trip'):
                if _model in self.env:
                    self.env[_model].sudo().with_context(active_test=False).search(
                        [('employee_id', 'in', emps.ids)]).unlink()
            # Phase-K: leaves + allocations reference a REQUIRED employee_id, so
            # they must go before the employee unlink (hr.leave.unlink has no
            # state guard — validated demo leaves unlink cleanly).
            for _model in ('hr.leave', 'hr.leave.allocation'):
                if _model in self.env:
                    self.env[_model].sudo().with_context(active_test=False).search(
                        [('employee_id', 'in', emps.ids)]).unlink()
            emps.unlink()
            _logger.info('pb_demo: cleaned %s demo employees.', len(emps))
        # Remove the OLD (wrong) structure-based demo artefacts so they stop
        # cluttering the (now hidden) Salary Structures view.
        self.env['hr.payroll.structure'].sudo().with_context(active_test=False).search(
            [('is_demo', '=', True)]).unlink()
        return True
