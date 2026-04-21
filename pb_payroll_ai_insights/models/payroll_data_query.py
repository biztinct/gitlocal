# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging

_logger = logging.getLogger(__name__)


class PayrollDataQuery(models.Model):
    """
    Data query layer for PayAI.
    Translates user intent into ORM queries against payroll data.
    Returns structured data suitable for chart generation.
    """

    _name = 'payroll.data.query'
    _description = 'PayAI Data Query Engine'

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

        # Payroll periods/months/batches (must be before salary which matches 'pay')
        if any(kw in msg_lower for kw in ['how many month', 'months payroll', 'payroll generated',
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
    # Query Methods
    # =========================================================================

    def _query_salary_data(self, message, context):
        """Query salary/compensation data grouped by department."""
        Contract = self.env['hr.contract'].sudo()

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
        }

    def _query_headcount_data(self, message, context):
        """Query headcount data."""
        Employee = self.env['hr.employee'].sudo()

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
        }

    def _query_overtime_data(self, message, context):
        """Query overtime data from payslip lines."""
        PayslipLine = self.env['hr.payslip.line'].sudo()

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
        }

    def _query_deduction_data(self, message, context):
        """Query deduction/contribution data."""
        PayslipLine = self.env['hr.payslip.line'].sudo()

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
        }

    def _query_payroll_cost_data(self, message, context):
        """Query total payroll cost data."""
        Payslip = self.env['hr.payslip'].sudo()

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
        }

    def _query_trend_data(self, message, context):
        """Query trend data — delegates to payroll cost trend."""
        return self._query_payroll_cost_data(message, context)

    def _query_department_data(self, message, context):
        """Query department-level summary."""
        salary_data = self._query_salary_data(message, context)
        headcount_data = self._query_headcount_data(message, context)

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
        }

    def _query_individual_data(self, message, context):
        """Query individual employee data."""
        Employee = self.env['hr.employee'].sudo()
        Contract = self.env['hr.contract'].sudo()

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
        }

    def _query_payroll_periods(self, message, context):
        """Query payroll periods — which months have payslips been generated."""
        Payslip = self.env['hr.payslip'].sudo()

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
        }

    def _query_general_summary(self, context):
        """Generate a general payroll summary."""
        Employee = self.env['hr.employee'].sudo()
        Contract = self.env['hr.contract'].sudo()

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
        }
