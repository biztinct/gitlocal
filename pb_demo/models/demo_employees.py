# -*- coding: utf-8 -*-
"""Employee & contract population (extends pb.demo.generator) — single Vietnam.

Division is stored as the KHOI key on hr.employee.division (the Formula Engine
input that drives division-specific allowances). Contracts carry NO struct_id —
payroll is computed by the formula configs, not salary structures.
"""
import logging
import random
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from . import demo_catalog as cat

_logger = logging.getLogger(__name__)

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

        _logger.info('pb_demo: total ~%s employees generated.', total)
        return total

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
            emps.unlink()
            _logger.info('pb_demo: cleaned %s demo employees.', len(emps))
        # Remove the OLD (wrong) structure-based demo artefacts so they stop
        # cluttering the (now hidden) Salary Structures view.
        self.env['hr.payroll.structure'].sudo().with_context(active_test=False).search(
            [('is_demo', '=', True)]).unlink()
        return True
