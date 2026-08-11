# -*- coding: utf-8 -*-
"""PayAI's data query layer — and the boundary it now respects.

WHAT CHANGED IN PHASE D1 AND WHY
--------------------------------
NOTE TO THE NEXT READER: ``tests/test_data_access.py`` pins the ABSENCE of the
superuser-escalation call from this file, and it greps the whole file, prose
included. Do not write that literal here even to explain it — say "the
escalation", as everything below does.

Every query below used to run under superuser rights. That made PayAI a way to read
payroll data the asking user is not allowed to read: a chat box that answers
"what does everyone earn" for somebody whose sidebar deliberately has no wage
roster in it. Worse, ``_query_individual_data`` posted employee names, job
titles and salaries to an EXTERNAL model provider on behalf of any user who
typed the word "name".

The queries now run as the asker. Two consequences are deliberate:

* Record rules apply, so a multi-company user sees the companies in their
  ACTIVE company selection rather than every company on the database. A
  figure PayAI reports is now the same figure the corresponding cockpit
  reports for that user — which it demonstrably was not before.
* A user with no read access at all gets a REFUSAL rather than a traceback,
  and the refusal names who can see the data instead of pretending it does
  not exist. Refusals never reach the model provider: the engine
  short-circuits on ``access_refused`` (payroll_ai_engine.py), so a user who
  cannot read the data does not spend a token asking about it either.

The individual-salary path carries a second, stricter gate on top of the ORM:
reading a named person's pay needs the Payroll Manager or Payroll Final
Approver group. Below that the aggregate answer is returned with the gate
note attached — the same payroll, no names.
"""

from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import functools
import json
import logging

_logger = logging.getLogger(__name__)

# The groups that may see ONE NAMED PERSON's pay. Not a claim about the ORM —
# the ORM gate is the ORM's job and still runs; this is the product's own
# statement about individually-identifying salary data leaving for a provider.
INDIVIDUAL_SALARY_GROUPS = (
    'pb_hr_payroll_base.group_payroll_base_manager',
    'pb_hr_payroll_base.group_payroll_final_approver',
)

# Optional modules, and the model whose PRESENCE IN THE REGISTRY proves the
# module is installed. The old check read ``ir.module.module`` under sudo,
# which is a privilege escalation for a question the registry already answers —
# and answers better: what the query actually needs is for ``self.env[model]``
# not to raise, which is exactly what this tests.
_OPTIONAL_MODULE_MODELS = {
    'hr_attendance': ('hr.attendance', None),
    'hr_holidays': ('hr.leave', None),
    'hr_recruitment': ('hr.applicant', None),
    # account.analytic.line exists without hr_timesheet; the employee link is
    # what that module adds, and what _query_timesheet_data reads.
    'hr_timesheet': ('account.analytic.line', 'employee_id'),
}


def _guarded(topic):
    """Turn an AccessError into an answer.

    Dropping the escalation means the ORM can now say no, and it says no by
    raising — which in PayAI's chat surfaced as "I apologize, but I
    encountered an error: ..." with an Odoo exception string in it. Every
    query path is wrapped so that the refusal is a normal response in the
    normal shape, in the reader's language, naming who can see the data.
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            try:
                return fn(self, *args, **kwargs)
            except AccessError:
                _logger.info(
                    "PayAI: refused '%s' for uid %s — the asker's access rights "
                    "do not cover it.", topic, self.env.uid)
                return self._access_refused_response(topic)
        return wrapper
    return deco


class PayrollDataQuery(models.Model):
    """
    Data query layer for PayAI.
    Translates user intent into ORM queries against payroll data.
    Returns structured data suitable for chart generation.

    Every query runs with the ASKER's access rights. See the module docstring.
    """

    _name = 'payroll.data.query'
    _description = 'PayAI Data Query Engine'

    # --- Soft Dependency Helper ---

    @api.model
    def _is_module_installed(self, module_name):
        """Check if an Odoo module is installed (soft dependency).

        Answered from the registry, not from ``ir.module.module`` — see
        ``_OPTIONAL_MODULE_MODELS``. An unknown module name is reported as not
        installed, which is the safe direction: the caller then returns the
        "install it from Apps" response instead of touching a model that may
        not exist.
        """
        model_name, needs_field = _OPTIONAL_MODULE_MODELS.get(
            module_name, (None, None))
        if not model_name or model_name not in self.env:
            return False
        if needs_field and needs_field not in self.env[model_name]._fields:
            return False
        return True

    # --- Refusals ---

    def _refusal_topic(self, topic):
        """The thing that was asked for, named in the reader's language.

        Built inside the method so every literal is a real ``_()`` call the
        translation tooling can extract — a dict of bare strings wrapped at
        the call site is invisible to it.
        """
        return {
            'attendance': _('attendance records'),
            'leave': _('leave and time-off records'),
            'recruitment': _('the recruitment pipeline'),
            'timesheet': _('timesheet entries'),
            'salary': _('the wages on employment contracts'),
            'headcount': _('the employee list'),
            'overtime': _('the overtime lines on payslips'),
            'deduction': _('the deduction and contribution lines on payslips'),
            'cost': _('payslip totals'),
            'periods': _('the payslip history'),
            'department': _('the department-level payroll summary'),
            'individual': _('individual employee salaries'),
            'summary': _('the payroll overview'),
            'forecast': _('the payroll history a forecast is built from'),
        }.get(topic) or _('that payroll data')

    def _access_refused_response(self, topic):
        """A refusal in the normal answer shape.

        Honest about what happened, and it names who CAN see the data rather
        than leaving the reader to guess whether the figure exists.
        """
        # The topic is deliberately the OBJECT of the sentence, never its
        # subject: "individual employee salaries" and "attendance records" are
        # plural and "the payroll overview" is singular, and a template that
        # makes any of them the subject gets the verb wrong for the others in
        # both languages. Nothing capitalises the fragment either.
        return {
            'query_type': 'access_refused',
            'title': _('Not available with your access'),
            'data': [],
            'access_refused': True,
            'message': _(
                "I can't answer that one for you — your role is not allowed to "
                "read %(topic)s, and PayAI answers with your own access rights "
                "rather than around them.\n\n"
                "In Payobook this data sits behind the payroll roles — a "
                "Payroll Officer, a Payroll Manager or a Payroll Super "
                "Administrator can see it. Ask one of them for the figure, or "
                "ask whoever administers roles in your company to add you."
            ) % {'topic': self._refusal_topic(topic)},
            'suggested_chart': None,
        }

    def _individual_gate_note(self):
        """The note that rides along with the aggregate answer.

        Not a refusal — the question was answered, one level up. Saying so is
        the difference between a gate and a silent substitution.
        """
        return _(
            "One thing I left out: I can't list individual salaries for your "
            "role. Reading a named person's pay needs the Payroll Manager or "
            "the Payroll Final Approver group; below that I answer in "
            "aggregate only. What you have above is the same payroll, without "
            "the names."
        )

    def _module_not_installed_response(self, module_name, feature_name):
        """Return a helpful response when a required module is not installed."""
        return {
            'query_type': 'module_not_installed',
            'title': f'{feature_name} — Module Not Installed',
            'data': [],
            'message': (
                f'The {feature_name} feature requires the \'{module_name}\' module '
                f'to be installed. Please install it from Apps to enable '
                f'{feature_name.lower()} queries in PayAI.'
            ),
            'suggested_chart': None,
        }

    # --- Main Router ---

    @api.model
    def query_for_message(self, message, context=None):
        """
        Analyze the user message and fetch relevant payroll data.

        Args:
            message (str): User's natural language query
            context (dict): Optional context (employee_id, department_id, etc.)

        Returns:
            dict: Structured data with metadata
        """
        context = context or {}
        msg_lower = message.lower()

        # Route to appropriate query based on keywords
        # IMPORTANT: More specific routes must come BEFORE generic ones

        # --- Soft-dependency routes (optional modules) ---

        # Attendance (hr_attendance)
        if any(kw in msg_lower for kw in ['attendance', 'check in', 'check out', 'checkin',
                                           'checkout', 'present', 'absent', 'late arrival',
                                           'working hours', 'clock in', 'clock out']):
            if not self._is_module_installed('hr_attendance'):
                return self._module_not_installed_response('hr_attendance', 'Attendance')
            return self._query_attendance_data(msg_lower, context)

        # Leaves (hr_holidays)
        elif any(kw in msg_lower for kw in ['leave', 'absence', 'time off', 'vacation',
                                             'sick leave', 'annual leave', 'holiday',
                                             'leave balance', 'days off']):
            if not self._is_module_installed('hr_holidays'):
                return self._module_not_installed_response('hr_holidays', 'Leaves / Time Off')
            return self._query_leave_data(msg_lower, context)

        # Recruitment (hr_recruitment)
        elif any(kw in msg_lower for kw in ['recruit', 'applicant', 'hiring', 'candidate',
                                             'vacancy', 'job opening', 'interview',
                                             'application', 'onboarding', 'new hire']):
            if not self._is_module_installed('hr_recruitment'):
                return self._module_not_installed_response('hr_recruitment', 'Recruitment')
            return self._query_recruitment_data(msg_lower, context)

        # Timesheets (hr_timesheet)
        elif any(kw in msg_lower for kw in ['timesheet', 'hours logged', 'time spent',
                                             'project hours', 'time tracking', 'logged hours',
                                             'billable hours', 'time entry']):
            if not self._is_module_installed('hr_timesheet'):
                return self._module_not_installed_response('hr_timesheet', 'Timesheets')
            return self._query_timesheet_data(msg_lower, context)

        # --- Core routes (always available) ---

        # Forecast / Prediction (must come before trend, cost, etc.)
        elif any(kw in msg_lower for kw in ['forecast', 'predict', 'projection', 'next month',
                                             'next quarter', 'next year', 'future',
                                             'estimate', 'projected', 'what will']):
            return self._query_forecast_data(msg_lower, context)

        # Payroll periods/months/batches (must be before salary which matches 'pay')
        elif any(kw in msg_lower for kw in ['how many month', 'months payroll', 'payroll generated',
                                             'payroll run', 'payslip', 'pay period', 'batch',
                                             'months generated', 'payroll period', 'payroll month',
                                             'which month', 'processed payroll']):
            return self._query_payroll_periods(msg_lower, context)
        elif any(kw in msg_lower for kw in ['salary', 'wage', 'compensation', 'ctc', 'earning',
                                             'salary distribution']):
            return self._query_salary_data(msg_lower, context)
        elif any(kw in msg_lower for kw in ['headcount', 'employee count', 'how many employee',
                                             'number of employee', 'staff count']):
            return self._query_headcount_data(msg_lower, context)
        elif any(kw in msg_lower for kw in ['overtime', 'ot ', 'extra hours']):
            return self._query_overtime_data(msg_lower, context)
        elif any(kw in msg_lower for kw in ['deduction', 'tax', 'statutory', 'contribution',
                                             'social security', 'insurance', 'provident']):
            return self._query_deduction_data(msg_lower, context)
        elif any(kw in msg_lower for kw in ['cost', 'expense', 'spend', 'budget', 'total payroll']):
            return self._query_payroll_cost_data(msg_lower, context)
        elif any(kw in msg_lower for kw in ['trend', 'monthly', 'over time', 'history',
                                             'last year', 'last month', 'growth']):
            return self._query_trend_data(msg_lower, context)
        elif any(kw in msg_lower for kw in ['department', 'team', 'division', 'unit']):
            return self._query_department_data(msg_lower, context)
        elif any(kw in msg_lower for kw in ['individual', 'specific employee', 'person',
                                             'name']):
            return self._query_individual_data(msg_lower, context)
        elif any(kw in msg_lower for kw in ['pay', 'payroll']):
            # Generic pay/payroll catch-all (after more specific routes)
            return self._query_salary_data(msg_lower, context)
        else:
            # Default: return a general payroll summary
            return self._query_general_summary(context)

    # =========================================================================
    # Soft-Dependency Query Methods (optional modules)
    # =========================================================================

    @_guarded('attendance')
    def _query_attendance_data(self, message, context):
        """Query attendance data — check-ins, working hours, late arrivals."""
        Attendance = self.env['hr.attendance']

        # Default to last 30 days to keep data volume manageable
        today = fields.Date.today()
        date_from = today - timedelta(days=30)

        domain = [('check_in', '>=', date_from)]
        if context.get('department_id'):
            domain.append(('employee_id.department_id', '=', context['department_id']))

        attendances = Attendance.search(domain, order='check_in desc')

        # Group by department
        dept_data = {}
        for att in attendances:
            dept = att.employee_id.department_id.name or 'Unassigned'
            if dept not in dept_data:
                dept_data[dept] = {'total_hours': 0, 'count': 0, 'employees': set()}
            if att.worked_hours:
                dept_data[dept]['total_hours'] += att.worked_hours
            dept_data[dept]['count'] += 1
            dept_data[dept]['employees'].add(att.employee_id.id)

        result = []
        for dept, data in sorted(dept_data.items(), key=lambda x: x[1]['total_hours'], reverse=True):
            avg_hours = data['total_hours'] / data['count'] if data['count'] else 0
            result.append({
                'department': dept,
                'total_hours': round(data['total_hours'], 1),
                'records': data['count'],
                'unique_employees': len(data['employees']),
                'avg_hours_per_day': round(avg_hours, 1),
            })

        return {
            'query_type': 'attendance_by_department',
            'title': f'Attendance Summary (Last 30 Days)',
            'data': result,
            'total_records': sum(d['records'] for d in result),
            'total_hours': round(sum(d['total_hours'] for d in result), 1),
            'date_range': f'{date_from} to {today}',
            'suggested_chart': 'bar',
            'drilldown_model': 'hr.attendance',
        }

    @_guarded('leave')
    def _query_leave_data(self, message, context):
        """Query leave/time-off data — by type, department, status."""
        Leave = self.env['hr.leave']

        # Get all leaves from this year
        year_start = fields.Date.today().replace(month=1, day=1)
        domain = [('date_from', '>=', year_start)]
        if context.get('department_id'):
            domain.append(('employee_id.department_id', '=', context['department_id']))

        leaves = Leave.search(domain)

        # Group by leave type
        type_data = {}
        for leave in leaves:
            lt = leave.holiday_status_id.name if leave.holiday_status_id else 'Other'
            if lt not in type_data:
                type_data[lt] = {'count': 0, 'days': 0, 'approved': 0, 'pending': 0}
            type_data[lt]['count'] += 1
            type_data[lt]['days'] += leave.number_of_days or 0
            if leave.state == 'validate':
                type_data[lt]['approved'] += 1
            elif leave.state in ('draft', 'confirm'):
                type_data[lt]['pending'] += 1

        result = [
            {
                'leave_type': lt,
                'count': d['count'],
                'total_days': round(d['days'], 1),
                'approved': d['approved'],
                'pending': d['pending'],
            }
            for lt, d in sorted(type_data.items(), key=lambda x: x[1]['days'], reverse=True)
        ]

        return {
            'query_type': 'leave_by_type',
            'title': f'Leave Summary ({fields.Date.today().year})',
            'data': result,
            'total_leaves': sum(d['count'] for d in result),
            'total_days': round(sum(d['total_days'] for d in result), 1),
            'suggested_chart': 'doughnut',
            'drilldown_model': 'hr.leave',
        }

    @_guarded('recruitment')
    def _query_recruitment_data(self, message, context):
        """Query recruitment pipeline — applicants by stage, department."""
        Applicant = self.env['hr.applicant']

        applicants = Applicant.search([])

        # Group by stage
        stage_data = {}
        dept_data = {}
        for app in applicants:
            stage = app.stage_id.name if app.stage_id else 'New'
            dept = app.department_id.name if app.department_id else 'Unassigned'

            stage_data.setdefault(stage, 0)
            stage_data[stage] += 1

            dept_data.setdefault(dept, 0)
            dept_data[dept] += 1

        stages = [
            {'stage': s, 'count': c}
            for s, c in sorted(stage_data.items(), key=lambda x: x[1], reverse=True)
        ]

        departments = [
            {'department': d, 'applicants': c}
            for d, c in sorted(dept_data.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            'query_type': 'recruitment_pipeline',
            'title': 'Recruitment Pipeline',
            'data': stages,
            'departments': departments,
            'total_applicants': len(applicants),
            'total_stages': len(stage_data),
            'suggested_chart': 'bar',
            'drilldown_model': 'hr.applicant',
        }

    @_guarded('timesheet')
    def _query_timesheet_data(self, message, context):
        """Query timesheet data — hours by project and employee."""
        Timesheet = self.env['account.analytic.line']

        # Last 30 days
        today = fields.Date.today()
        date_from = today - timedelta(days=30)

        domain = [
            ('date', '>=', date_from),
            ('project_id', '!=', False),  # Only project timesheets
        ]
        if context.get('department_id'):
            domain.append(('employee_id.department_id', '=', context['department_id']))

        lines = Timesheet.search(domain)

        # Group by project
        project_data = {}
        for line in lines:
            proj = line.project_id.name if line.project_id else 'No Project'
            if proj not in project_data:
                project_data[proj] = {'hours': 0, 'entries': 0, 'employees': set()}
            project_data[proj]['hours'] += line.unit_amount or 0
            project_data[proj]['entries'] += 1
            if line.employee_id:
                project_data[proj]['employees'].add(line.employee_id.id)

        result = [
            {
                'project': proj,
                'total_hours': round(d['hours'], 1),
                'entries': d['entries'],
                'unique_employees': len(d['employees']),
            }
            for proj, d in sorted(project_data.items(), key=lambda x: x[1]['hours'], reverse=True)
        ]

        return {
            'query_type': 'timesheet_by_project',
            'title': f'Timesheet Hours by Project (Last 30 Days)',
            'data': result,
            'total_hours': round(sum(d['total_hours'] for d in result), 1),
            'total_entries': sum(d['entries'] for d in result),
            'date_range': f'{date_from} to {today}',
            'suggested_chart': 'bar',
            'drilldown_model': 'account.analytic.line',
        }

    # =========================================================================
    # Core Query Methods (always available)
    # =========================================================================

    @_guarded('salary')
    def _query_salary_data(self, message, context):
        """Query salary/compensation data grouped by department."""
        Contract = self.env['hr.contract']

        domain = [('state', '=', 'open')]
        if context.get('department_id'):
            domain.append(('department_id', '=', context['department_id']))

        contracts = Contract.search(domain)

        # Group by department
        dept_data = {}
        for contract in contracts:
            dept_name = contract.department_id.name or 'Unassigned'
            if dept_name not in dept_data:
                dept_data[dept_name] = {'total': 0, 'count': 0, 'min': float('inf'), 'max': 0}
            dept_data[dept_name]['total'] += contract.wage
            dept_data[dept_name]['count'] += 1
            dept_data[dept_name]['min'] = min(dept_data[dept_name]['min'], contract.wage)
            dept_data[dept_name]['max'] = max(dept_data[dept_name]['max'], contract.wage)

        # Calculate averages
        result = []
        for dept, data in sorted(dept_data.items()):
            avg = data['total'] / data['count'] if data['count'] > 0 else 0
            result.append({
                'department': dept,
                'employee_count': data['count'],
                'total_salary': round(data['total'], 2),
                'average_salary': round(avg, 2),
                'min_salary': round(data['min'], 2) if data['min'] != float('inf') else 0,
                'max_salary': round(data['max'], 2),
            })

        return {
            'query_type': 'salary_by_department',
            'title': 'Salary Data by Department',
            'data': result,
            'total_employees': sum(d['employee_count'] for d in result),
            'overall_average': round(
                sum(d['total_salary'] for d in result) /
                max(sum(d['employee_count'] for d in result), 1), 2
            ),
            'currency': self.env.company.currency_id.symbol or '$',
            'suggested_chart': 'bar',
            'drilldown_model': 'hr.contract',
        }

    @_guarded('headcount')
    def _query_headcount_data(self, message, context):
        """Query headcount data."""
        Employee = self.env['hr.employee']

        domain = [('active', '=', True)]
        if context.get('department_id'):
            domain.append(('department_id', '=', context['department_id']))

        # Group by department
        groups = Employee.read_group(domain, ['department_id'], ['department_id'])

        result = []
        for group in groups:
            dept_name = group['department_id'][1] if group['department_id'] else 'Unassigned'
            result.append({
                'department': dept_name,
                'headcount': group['department_id_count'],
            })

        return {
            'query_type': 'headcount_by_department',
            'title': 'Headcount by Department',
            'data': sorted(result, key=lambda x: x['headcount'], reverse=True),
            'total_headcount': sum(d['headcount'] for d in result),
            'department_count': len(result),
            'suggested_chart': 'bar',
            'drilldown_model': 'hr.employee',
        }

    @_guarded('overtime')
    def _query_overtime_data(self, message, context):
        """Query overtime data from payslip lines."""
        PayslipLine = self.env['hr.payslip.line']

        # Look for overtime-related salary rules
        today = fields.Date.today()
        first_of_month = today.replace(day=1)

        domain = [
            ('slip_id.state', 'in', ['done', 'paid']),
            ('slip_id.date_from', '>=', first_of_month - relativedelta(months=3)),
            ('category_id.code', 'in', ['OT', 'OVERTIME', 'ALW']),
        ]

        lines = PayslipLine.search(domain)

        dept_ot = {}
        for line in lines:
            dept = line.slip_id.employee_id.department_id.name or 'Unassigned'
            if dept not in dept_ot:
                dept_ot[dept] = 0
            dept_ot[dept] += line.total

        result = [
            {'department': dept, 'overtime_cost': round(total, 2)}
            for dept, total in sorted(dept_ot.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            'query_type': 'overtime_by_department',
            'title': 'Overtime Costs by Department (Last 3 Months)',
            'data': result,
            'total_overtime': round(sum(d['overtime_cost'] for d in result), 2),
            'currency': self.env.company.currency_id.symbol or '$',
            'suggested_chart': 'bar',
            'drilldown_model': 'hr.payslip.line',
        }

    @_guarded('deduction')
    def _query_deduction_data(self, message, context):
        """Query deduction/contribution data."""
        PayslipLine = self.env['hr.payslip.line']

        today = fields.Date.today()
        first_of_month = today.replace(day=1)

        domain = [
            ('slip_id.state', 'in', ['done', 'paid']),
            ('slip_id.date_from', '>=', first_of_month),
            ('category_id.code', 'in', ['DED', 'DEDUCTION', 'COMP']),
        ]

        lines = PayslipLine.search(domain)

        rule_data = {}
        for line in lines:
            rule_name = line.salary_rule_id.name or line.name or 'Other'
            if rule_name not in rule_data:
                rule_data[rule_name] = 0
            rule_data[rule_name] += abs(line.total)

        result = [
            {'deduction_type': rule, 'amount': round(total, 2)}
            for rule, total in sorted(rule_data.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            'query_type': 'deductions_by_type',
            'title': 'Deductions by Type (Current Month)',
            'data': result,
            'total_deductions': round(sum(d['amount'] for d in result), 2),
            'currency': self.env.company.currency_id.symbol or '$',
            'suggested_chart': 'doughnut',
            'drilldown_model': 'hr.payslip.line',
        }

    @_guarded('cost')
    def _query_payroll_cost_data(self, message, context):
        """Query total payroll cost data."""
        Payslip = self.env['hr.payslip']

        today = fields.Date.today()
        first_of_month = today.replace(day=1)

        domain = [
            ('state', 'in', ['done', 'paid']),
            ('date_from', '>=', first_of_month - relativedelta(months=6)),
        ]

        payslips = Payslip.search(domain)

        month_data = {}
        for slip in payslips:
            month_key = slip.date_from.strftime('%Y-%m')
            month_label = slip.date_from.strftime('%b %Y')
            if month_key not in month_data:
                month_data[month_key] = {'label': month_label, 'gross': 0, 'net': 0, 'count': 0}

            # Get NET from payslip lines
            for line in slip.line_ids:
                if line.category_id.code == 'NET':
                    month_data[month_key]['net'] += line.total
                elif line.category_id.code in ('GROSS', 'BASIC'):
                    month_data[month_key]['gross'] += line.total
            month_data[month_key]['count'] += 1

        result = [
            {
                'month': v['label'],
                'gross_cost': round(v['gross'], 2),
                'net_cost': round(v['net'], 2),
                'payslip_count': v['count'],
            }
            for k, v in sorted(month_data.items())
        ]

        return {
            'query_type': 'payroll_cost_trend',
            'title': 'Payroll Cost Trend (Last 6 Months)',
            'data': result,
            'currency': self.env.company.currency_id.symbol or '$',
            'suggested_chart': 'line',
            'drilldown_model': 'hr.payslip',
        }

    def _query_trend_data(self, message, context):
        """Query trend data — delegates to payroll cost trend.

        Deliberately NOT guarded: it owns no query of its own, and the
        delegate is guarded. Wrapping it would only mean a refusal named
        after the wrong topic.
        """
        return self._query_payroll_cost_data(message, context)

    @_guarded('department')
    def _query_department_data(self, message, context):
        """Query department-level summary."""
        salary_data = self._query_salary_data(message, context)
        headcount_data = self._query_headcount_data(message, context)

        # A refused half must not be merged as an empty one: two zeroes in a
        # department table read as "nobody works here", which is a different
        # and much worse answer than "you may not see this".
        for part in (salary_data, headcount_data):
            if part.get('access_refused'):
                return part

        # Merge data
        dept_map = {}
        for item in salary_data['data']:
            dept_map[item['department']] = {
                'department': item['department'],
                'headcount': 0,
                'total_salary': item['total_salary'],
                'average_salary': item['average_salary'],
            }
        for item in headcount_data['data']:
            if item['department'] in dept_map:
                dept_map[item['department']]['headcount'] = item['headcount']
            else:
                dept_map[item['department']] = {
                    'department': item['department'],
                    'headcount': item['headcount'],
                    'total_salary': 0,
                    'average_salary': 0,
                }

        return {
            'query_type': 'department_summary',
            'title': 'Department-wise Payroll Summary',
            'data': list(dept_map.values()),
            'total_departments': len(dept_map),
            'suggested_chart': 'bar',
            'drilldown_model': 'hr.employee',
        }

    @_guarded('individual')
    def _query_individual_data(self, message, context):
        """Query individual employee data — NAMES, TITLES AND SALARIES.

        This is the one path in PayAI that sends individually-identifying pay
        to an external model provider, so it carries a group gate on top of
        the ORM's. Below the gate the caller gets the aggregate answer plus a
        note saying what was withheld and why — a substitution the reader can
        see is better than a shorter list they cannot account for.
        """
        if not any(self.env.user.has_group(g) for g in INDIVIDUAL_SALARY_GROUPS):
            aggregate = self._query_salary_data(message, context)
            if aggregate.get('access_refused'):
                # The harder refusal wins: they may not see the wage table at
                # all, so there is no aggregate to fall back to.
                return aggregate
            aggregate = dict(aggregate)
            aggregate['individual_data_withheld'] = True
            aggregate['access_note'] = self._individual_gate_note()
            _logger.info(
                "PayAI: individual salary detail withheld from uid %s — "
                "neither payroll manager nor final approver.", self.env.uid)
            return aggregate

        Employee = self.env['hr.employee']
        Contract = self.env['hr.contract']

        # Try to extract employee name from message
        employees = Employee.search([('active', '=', True)], limit=20)

        result = []
        for emp in employees:
            contract = Contract.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'open'),
            ], limit=1)

            if contract:
                result.append({
                    'employee': emp.name,
                    'department': emp.department_id.name or 'N/A',
                    'job_title': emp.job_title or emp.job_id.name or 'N/A',
                    'salary': round(contract.wage, 2),
                })

        return {
            'query_type': 'individual_employees',
            'title': 'Employee Salary Details',
            'data': sorted(result, key=lambda x: x['salary'], reverse=True),
            'total_employees': len(result),
            'currency': self.env.company.currency_id.symbol or '$',
            'suggested_chart': 'bar',
            'drilldown_model': 'hr.employee',
        }

    @_guarded('periods')
    def _query_payroll_periods(self, message, context):
        """Query payroll periods — which months have payslips been generated."""
        Payslip = self.env['hr.payslip']

        payslips = Payslip.search([], order='date_from asc')

        # Group by month and state
        month_data = {}
        for slip in payslips:
            month_key = slip.date_from.strftime('%Y-%m')
            month_label = slip.date_from.strftime('%b %Y')
            if month_key not in month_data:
                month_data[month_key] = {
                    'month': month_label,
                    'draft': 0,
                    'done': 0,
                    'paid': 0,
                    'total': 0,
                }
            state = slip.state or 'draft'
            if state in ('done', 'paid'):
                month_data[month_key]['done'] += 1
            else:
                month_data[month_key]['draft'] += 1
            month_data[month_key]['total'] += 1

        result = [v for k, v in sorted(month_data.items())]

        return {
            'query_type': 'payroll_periods',
            'title': 'Payroll Periods Generated',
            'data': result,
            'total_months': len(result),
            'total_payslips': sum(d['total'] for d in result),
            'total_done': sum(d['done'] for d in result),
            'total_draft': sum(d['draft'] for d in result),
            'suggested_chart': 'bar',
            'drilldown_model': 'hr.payslip',
        }

    @_guarded('summary')
    def _query_general_summary(self, context):
        """Generate a general payroll summary."""
        Employee = self.env['hr.employee']
        Contract = self.env['hr.contract']

        active_employees = Employee.search_count([('active', '=', True)])
        active_contracts = Contract.search_count([('state', '=', 'open')])

        # Get department breakdown
        dept_groups = Employee.read_group(
            [('active', '=', True)],
            ['department_id'], ['department_id']
        )

        departments = [
            {
                'department': g['department_id'][1] if g['department_id'] else 'Unassigned',
                'count': g['department_id_count'],
            }
            for g in dept_groups
        ]

        # Get total wage from contracts
        contracts = Contract.search([('state', '=', 'open')])
        total_wage = sum(c.wage for c in contracts)

        return {
            'query_type': 'general_summary',
            'title': 'Payroll Overview',
            'data': {
                'active_employees': active_employees,
                'active_contracts': active_contracts,
                'total_monthly_wage': round(total_wage, 2),
                'average_wage': round(total_wage / max(active_contracts, 1), 2),
                'departments': departments,
            },
            'currency': self.env.company.currency_id.symbol or '$',
            'suggested_chart': 'doughnut',
            'drilldown_model': 'hr.employee',
        }

    # =========================================================================
    # Forecast / Prediction Query
    # =========================================================================

    @_guarded('forecast')
    def _query_forecast_data(self, message, context):
        """
        Gather 12 months of historical payroll cost data for AI-powered forecasting.
        The AI engine will use this data to predict the next 3 months.
        """
        Payslip = self.env['hr.payslip']

        today = fields.Date.today()
        # Get data for last 12 months
        date_from = today - relativedelta(months=12)
        date_from = date_from.replace(day=1)  # Start of month

        domain = [
            ('state', 'in', ['done', 'paid']),
            ('date_from', '>=', date_from),
        ]
        if context.get('department_id'):
            domain.append(('employee_id.department_id', '=', context['department_id']))

        payslips = Payslip.search(domain)

        # Aggregate by month
        monthly_data = {}
        for ps in payslips:
            month_key = ps.date_from.strftime('%Y-%m')
            month_label = ps.date_from.strftime('%b %Y')
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    'month': month_key,
                    'label': month_label,
                    'total_cost': 0,
                    'employee_count': 0,
                    'employees_seen': set(),
                }
            monthly_data[month_key]['total_cost'] += sum(
                line.total for line in ps.line_ids if line.total > 0
            ) if ps.line_ids else 0
            monthly_data[month_key]['employees_seen'].add(ps.employee_id.id)

        # Convert to sorted list
        result = []
        for key in sorted(monthly_data.keys()):
            data = monthly_data[key]
            result.append({
                'month': data['month'],
                'label': data['label'],
                'total_cost': round(data['total_cost'], 2),
                'employee_count': len(data['employees_seen']),
                'avg_cost_per_employee': round(
                    data['total_cost'] / max(len(data['employees_seen']), 1), 2
                ),
            })

        # Determine what the user wants to forecast
        forecast_focus = 'total payroll cost'
        if 'headcount' in message:
            forecast_focus = 'headcount'
        elif 'salary' in message or 'wage' in message:
            forecast_focus = 'average salary'

        return {
            'query_type': 'forecast',
            'title': f'Payroll Forecast — {forecast_focus.title()}',
            'data': result,
            'forecast_months': 3,
            'forecast_focus': forecast_focus,
            'currency': self.env.company.currency_id.symbol or '$',
            'suggested_chart': 'line',
            'is_forecast': True,
            'instructions': (
                'Based on the historical data provided, PREDICT the next 3 months values. '
                'In the chart, use a SOLID line for historical data and a DASHED line '
                'with a lighter color/opacity for the forecasted period. '
                'Add a fill/shaded area under the forecast to indicate uncertainty. '
                'Include your confidence level and reasoning in the insights.'
            ),
            'drilldown_model': 'hr.payslip',
        }

