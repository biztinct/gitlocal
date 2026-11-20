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
from odoo.addons.base.models.res_bank import sanitize_account_number

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

    def ensure_demo_bank_details(self):
        """Pay & Deliver and the bank file read the Vietnam bank fields; the
        generator writes the bank and account number to the formula engine's
        `bank_name` / `account_number` only, so every demo run showed
        "Total net ₫0" with everybody left out. Copy them across for demo
        employees whose Vietnam fields are empty. Adds, never overwrites;
        idempotent; a no-op without the Vietnam pack."""
        Employee = self.env['hr.employee']
        needed = ('vietnam_bank_name', 'vietnam_bank_account_number',
                  'vietnam_bank_account_name', 'bank_name', 'account_number')
        if not all(f in Employee._fields for f in needed):
            return 0
        self.env.flush_all()
        self.env.cr.execute("""
            UPDATE hr_employee
               SET vietnam_bank_name = bank_name,
                   vietnam_bank_account_number = account_number,
                   vietnam_bank_account_name = COALESCE(NULLIF(vietnam_bank_account_name, ''), name)
             WHERE is_demo
               AND COALESCE(vietnam_bank_name, '') = ''
               AND COALESCE(vietnam_bank_account_number, '') = ''
               AND COALESCE(bank_name, '') <> ''
               AND COALESCE(account_number, '') <> ''
        """)
        count = self.env.cr.rowcount
        Employee.invalidate_model(['vietnam_bank_name', 'vietnam_bank_account_number',
                                   'vietnam_bank_account_name'])
        _logger.info('pb_demo: bank details copied for %s demo employees.', count)
        return count

    # ------------------------------------------- FS-9 follow-on B: one number
    # A demo person used to carry TWO account numbers: the Vietnamese bank
    # file's (copied from the generator's old box, above) and, since a one-off
    # on 2026-11-18, a linked bank account with a DIFFERENT random number (the
    # one the payment list and the side panel read). The side panel now says
    # so on every demo person. Both steps below are DEMO-ONLY:
    #   guard 1 — the code lives in pb_demo, which is installed on the demo
    #             site only (payobook; uninstalled on payobook_template, p0clone,
    #             rize, sudima);
    #   guard 2 — only employees carrying the generator's own world marker
    #             `hr_employee.is_demo = TRUE`;
    #   guard 3 — an account also linked to a non-demo employee is never
    #             touched, nor one whose new number would collide on the same
    #             contact.
    # Direction: the bank ACCOUNT takes the Vietnamese bank file's number, so
    # the Vietnamese bank file (which reads only the four vietnam_bank_*
    # fields) builds byte for byte as before. Nothing is deleted; no approval
    # request, no message, no mail (plain SQL on the account row, the same way
    # ensure_demo_bank_details writes the employee).

    def _demo_bank_mismatches(self):
        """[(account id, new number)] — demo people whose first bank account
        (the one every reader pays, `bank_account_ids[:1]`) differs from their
        Vietnamese bank file number."""
        Employee = self.env['hr.employee']
        if 'vietnam_bank_account_number' not in Employee._fields \
                or 'bank_account_ids' not in Employee._fields:
            return []
        self.env.flush_all()
        self.env.cr.execute("""
            WITH firsts AS (
                SELECT DISTINCT ON (r.employee_id) r.employee_id, b.id AS account_id,
                       b.partner_id, b.acc_number
                  FROM employee_bank_account_rel r
                  JOIN res_partner_bank b ON b.id = r.bank_account_id
                 ORDER BY r.employee_id, b.sequence, b.id
            )
            SELECT f.account_id, e.vietnam_bank_account_number, f.partner_id
              FROM hr_employee e
              JOIN firsts f ON f.employee_id = e.id
             WHERE e.is_demo
               AND COALESCE(e.vietnam_bank_account_number, '') <> ''
               AND regexp_replace(f.acc_number, '\\D', '', 'g')
                   <> regexp_replace(e.vietnam_bank_account_number, '\\D', '', 'g')
               AND NOT EXISTS (
                   SELECT 1 FROM employee_bank_account_rel r2
                     JOIN hr_employee e2 ON e2.id = r2.employee_id
                    WHERE r2.bank_account_id = f.account_id
                      AND NOT COALESCE(e2.is_demo, FALSE))
        """)
        out = []
        for account_id, number, partner_id in self.env.cr.fetchall():
            sanitized = sanitize_account_number(number)
            self.env.cr.execute(
                "SELECT 1 FROM res_partner_bank WHERE partner_id = %s AND id <> %s "
                "AND sanitized_acc_number = %s LIMIT 1", (partner_id, account_id, sanitized))
            if self.env.cr.fetchone():
                continue                    # guard 3: would collide on the contact
            out.append((account_id, number, sanitized))
        return out

    def ensure_demo_bank_accounts_agree(self):
        """One-off, idempotent: the demo bank ACCOUNT takes the Vietnamese bank
        file's number where the two differ (guards above). Returns how many
        accounts were brought into agreement; a second run returns 0."""
        rows = self._demo_bank_mismatches()
        for account_id, number, sanitized in rows:
            self.env.cr.execute(
                "UPDATE res_partner_bank SET acc_number = %s, sanitized_acc_number = %s "
                "WHERE id = %s", (number, sanitized, account_id))
        self.env['res.partner.bank'].invalidate_model(['acc_number', 'sanitized_acc_number'])
        _logger.info('pb_demo: %s demo bank accounts now carry the bank file number.', len(rows))
        return len(rows)

    def ensure_demo_bank_accounts(self):
        """Generator: every demo person with a Vietnamese bank file account and
        no linked bank account gets ONE, with the SAME number, bank and holder —
        so a regenerated world never carries two numbers per person. Adds only;
        idempotent; demo people only."""
        Employee = self.env['hr.employee'].sudo()
        if 'vietnam_bank_account_number' not in Employee._fields \
                or 'bank_account_ids' not in Employee._fields:
            return 0
        Bank = self.env['res.bank'].sudo()
        PartnerBank = self.env['res.partner.bank'].sudo().with_context(**self._GEN_CTX)
        made = 0
        for emp in Employee.search([('is_demo', '=', True),
                                    ('vietnam_bank_account_number', 'not in', (False, '')),
                                    ('bank_account_ids', '=', False)]):
            partner = emp.work_contact_id
            if not partner:
                continue
            number = emp.vietnam_bank_account_number
            if PartnerBank.search_count([('partner_id', '=', partner.id),
                                         ('sanitized_acc_number', '=',
                                          sanitize_account_number(number))]):
                continue
            bank = Bank.browse()
            if emp.vietnam_bank_name:
                bank = Bank.search([('name', '=ilike', emp.vietnam_bank_name)], limit=1) \
                    or Bank.create({'name': emp.vietnam_bank_name})
            account = PartnerBank.create({
                'acc_number': number, 'partner_id': partner.id,
                'bank_id': bank.id or False,
                'acc_holder_name': emp.vietnam_bank_account_name or emp.name,
            })
            emp.with_context(**self._GEN_CTX).bank_account_ids = [(4, account.id)]
            made += 1
        _logger.info('pb_demo: %s demo bank accounts made from the bank file number.', made)
        return made

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
        self.ensure_demo_bank_details()
        # FS-9 follow-on B: one number per person (bank file = bank account)
        self.ensure_demo_bank_accounts()
        self.ensure_demo_bank_accounts_agree()

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
