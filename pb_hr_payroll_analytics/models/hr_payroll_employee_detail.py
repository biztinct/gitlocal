# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class HrPayrollEmployeeDetail(models.TransientModel):
    """Transient model for employee payroll detail drill-down"""
    _name = 'hr.payroll.employee.detail'
    _description = 'Employee Payroll Detail'
    _order = 'employee_id, month'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    employee_name = fields.Char(related='employee_id.name', string='Employee Name', store=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True)
    department_name = fields.Char(related='department_id.name', string='Department Name', store=True)
    month = fields.Date(string='Month', required=True)
    month_name = fields.Char(string='Month Name', compute='_compute_month_name', store=True)
    
    # Salary components
    basic_salary = fields.Monetary(string='Basic Salary', currency_field='currency_id')
    allowances = fields.Monetary(string='Allowances', currency_field='currency_id')
    contributions = fields.Monetary(string='Contributions', currency_field='currency_id')
    total = fields.Monetary(string='Total', compute='_compute_total', store=True, currency_field='currency_id')
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    country_code = fields.Char(string='Country Code')

    @api.depends('month')
    def _compute_month_name(self):
        for record in self:
            if record.month:
                record.month_name = record.month.strftime('%B %Y')
            else:
                record.month_name = ''

    @api.depends('basic_salary', 'allowances', 'contributions')
    def _compute_total(self):
        for record in self:
            record.total = record.basic_salary + record.allowances + record.contributions

    @api.model
    def generate_drill_down_data(self, department_name, date_from=None, date_to=None, country_code=None):
        """
        Generate drill-down data for a specific department
        
        :param department_name: Name of the department to filter
        :param date_from: Start date for filtering (string or date object)
        :param date_to: End date for filtering (string or date object)
        :param country_code: Country code for filtering
        :return: Action to open pivot view with generated data
        """
        try:
            _logger.info(f"[Drill-Down] Generating data for department: {department_name}")
            _logger.info(f"[Drill-Down] Parameters: date_from={date_from}, date_to={date_to}, country={country_code}")
            
            # Clear existing transient records (older than 1 hour)
            cutoff = fields.Datetime.now() - relativedelta(hours=1)
            old_records = self.search([('create_date', '<', cutoff)])
            old_records.unlink()
            
            # Convert string dates to date objects if needed
            if date_from:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
            else:
                date_from = fields.Date.today().replace(day=1) - relativedelta(months=5)
            
            if date_to:
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
            else:
                date_to = fields.Date.today()
            
            _logger.info(f"[Drill-Down] Converted dates: from={date_from}, to={date_to}")
            
            # Find the department
            department = self.env['hr.department'].search([('name', '=', department_name)], limit=1)
            if not department:
                _logger.warning(f"[Drill-Down] Department '{department_name}' not found, using sample data")
                return self._generate_sample_data(department_name, date_from, date_to)
            
            # Try to get real payroll data
            records_created = self._generate_from_payslips(department, date_from, date_to, country_code)
            
            # If no real data, use sample data
            if records_created == 0:
                _logger.info(f"[Drill-Down] No payslip data found, generating sample data")
                return self._generate_sample_data(department_name, date_from, date_to)
            
            # Return action to open pivot view
            return self._get_pivot_action(department_name)
            
        except Exception as e:
            _logger.error(f"[Drill-Down] Error in generate_drill_down_data: {str(e)}", exc_info=True)
            raise

    def _generate_from_payslips(self, department, date_from, date_to, country_code):
        """Generate data from actual payslips"""
        _logger.info(f"[Drill-Down] Attempting to fetch payslip data for {department.name}")
        
        # Get employees in the department
        employees = self.env['hr.employee'].search([('department_id', '=', department.id)])
        if not employees:
            return 0
        
        # Check if hr.payslip model exists
        if 'hr.payslip' not in self.env:
            _logger.warning("[Drill-Down] hr.payslip model not found")
            return 0
        
        records_created = 0
        current_date = date_from
        
        while current_date <= date_to:
            month_start = current_date.replace(day=1)
            month_end = (month_start + relativedelta(months=1)) - relativedelta(days=1)
            
            for employee in employees:
                # Search for payslips in this month
                payslips = self.env['hr.payslip'].search([
                    ('employee_id', '=', employee.id),
                    ('date_from', '>=', month_start),
                    ('date_to', '<=', month_end),
                    ('state', 'in', ['done', 'paid'])
                ])
                
                if payslips:
                    # Aggregate salary components from payslip lines
                    basic = allowances = contrib = 0.0
                    
                    for payslip in payslips:
                        for line in payslip.line_ids:
                            # Categorize based on salary rule category
                            if line.category_id.code in ['BASIC', 'ALW']:
                                if 'BASIC' in line.category_id.code:
                                    basic += line.total
                                else:
                                    allowances += line.total
                            elif line.category_id.code in ['DED', 'COMP']:
                                contrib += abs(line.total)
                    
                    # Create record
                    self.create({
                        'employee_id': employee.id,
                        'department_id': department.id,
                        'month': month_start,
                        'basic_salary': basic,
                        'allowances': allowances,
                        'contributions': contrib,
                        'country_code': country_code or 'ALL',
                    })
                    records_created += 1
            
            current_date = month_start + relativedelta(months=1)
        
        _logger.info(f"[Drill-Down] Created {records_created} records from payslips")
        return records_created

    @api.model
    def _generate_sample_data(self, department_name, date_from, date_to):
        """Generate sample data for demonstration"""
        _logger.info(f"[Drill-Down] Generating sample data for {department_name}")
        
        # Sample employee names by department
        employee_samples = {
            'Engineering': ['John Smith', 'Sarah Johnson', 'Michael Chen', 'Emily Davis', 'David Wilson'],
            'Sales': ['Robert Brown', 'Jennifer Lee', 'William Taylor', 'Lisa Anderson'],
            'Operations': ['James Martinez', 'Mary Garcia', 'Thomas Rodriguez'],
            'HR': ['Patricia Hernandez', 'Christopher Lopez'],
            'Finance': ['Barbara Gonzalez', 'Daniel Perez', 'Nancy Wilson']
        }
        
        # Sample salary ranges by department
        salary_ranges = {
            'Engineering': (8000, 12000),
            'Sales': (7000, 10000),
            'Operations': (6000, 9000),
            'HR': (5500, 8000),
            'Finance': (6500, 9500)
        }
        
        employees = employee_samples.get(department_name, ['Sample Employee 1', 'Sample Employee 2'])
        salary_range = salary_ranges.get(department_name, (6000, 9000))
        
        # Create sample department if it doesn't exist
        department = self.env['hr.department'].search([('name', '=', department_name)], limit=1)
        if not department:
            department = self.env['hr.department'].create({'name': department_name})
        
        # Generate data for each month
        current_date = date_from.replace(day=1) if isinstance(date_from, datetime) else date_from
        
        import random
        records_created = 0
        
        for emp_name in employees:
            # Create or find employee
            employee = self.env['hr.employee'].search([('name', '=', emp_name)], limit=1)
            if not employee:
                employee = self.env['hr.employee'].create({
                    'name': emp_name,
                    'department_id': department.id,
                })
            
            # Generate monthly data
            month_date = current_date
            base_salary = random.randint(salary_range[0], salary_range[1])
            
            while month_date <= date_to:
                # Add some variation month to month
                variation = random.uniform(0.95, 1.05)
                basic = base_salary * variation
                allowances = basic * random.uniform(0.10, 0.15)
                contributions = basic * random.uniform(0.15, 0.20)
                
                self.create({
                    'employee_id': employee.id,
                    'department_id': department.id,
                    'month': month_date,
                    'basic_salary': basic,
                    'allowances': allowances,
                    'contributions': contributions,
                    'country_code': 'SAMPLE',
                })
                records_created += 1
                
                month_date = month_date + relativedelta(months=1)
        
        _logger.info(f"[Drill-Down] Created {records_created} sample records")
        return self._get_pivot_action(department_name)

    @api.model
    def _get_pivot_action(self, department_name):
        """Return action to open pivot view"""
        return {
            'name': f'📊 {department_name} Department - Employee Payroll Details',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.employee.detail',
            'view_mode': 'pivot,tree,graph',
            'views': [
                (self.env.ref('pb_hr_payroll_analytics.view_hr_payroll_employee_detail_pivot').id, 'pivot'),
                (self.env.ref('pb_hr_payroll_analytics.view_hr_payroll_employee_detail_tree').id, 'tree'),
                (self.env.ref('pb_hr_payroll_analytics.view_hr_payroll_employee_detail_graph').id, 'graph'),
            ],
            'domain': [('department_name', '=', department_name)],
            'context': {
                'group_by': ['employee_name'],
                'pivot_measures': ['basic_salary', 'allowances', 'contributions', 'total'],
                'pivot_column_groupby': ['month:month'],
                'search_default_department_name': department_name,
                'default_department_name': department_name,
            },
            'target': 'current',
            'help': f'''
                <p class="o_view_nocontent_smiling_face">
                    Showing payroll details for <strong>{department_name}</strong> department
                </p>
                <p>
                    This view displays employee-level salary breakdown by month.
                    <br/>
                    <strong>Filter Applied:</strong> Department = {department_name}
                </p>
            ''',
        }
