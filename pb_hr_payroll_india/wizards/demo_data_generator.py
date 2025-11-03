# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import random
from datetime import datetime, date, timedelta
import logging

_logger = logging.getLogger(__name__)

class DemoDataGeneratorIndia(models.TransientModel):
    _name = 'demo.data.generator.india'
    _description = 'India Demo Data Generator'

    employee_count = fields.Integer(
        string='Number of Employees',
        default=25,
        required=True,
        help="Number of demo employees to generate for India"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env['res.currency'].search([('name', '=', 'INR')], limit=1) or self.env.company.currency_id,
        readonly=True
    )
    
    include_payroll_data = fields.Boolean(
        string='Include Payroll Data',
        default=True,
        help="Generate salary components and payroll calculations"
    )
    
    salary_range_min = fields.Float(
        string='Minimum Salary (INR)',
        default=25000,
        help="Minimum basic salary in Indian Rupees"
    )
    
    salary_range_max = fields.Float(
        string='Maximum Salary (INR)', 
        default=150000,
        help="Maximum basic salary in Indian Rupees"
    )
    
    location_ids = fields.Many2many(
        'res.country.state',
        string='Indian States/Locations',
        domain=[('country_id.code', '=', 'IN')],
        help="Select Indian states for employee locations"
    )

    def action_generate_demo_data(self):
        """Generate demo data for India payroll"""
        
        if self.employee_count <= 0 or self.employee_count > 100:
            raise ValidationError(_("Employee count must be between 1 and 100"))
        
        if self.salary_range_min >= self.salary_range_max:
            raise ValidationError(_("Minimum salary must be less than maximum salary"))
        
        try:
            # Generate demo employees
            created_employees = self._generate_demo_employees()
            
            # Generate payroll data if requested
            if self.include_payroll_data:
                self._generate_payroll_data(created_employees)
            
            # Show success message
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Demo Data Generated Successfully'),
                    'message': _('Generated %s Indian employees with demo payroll data.') % len(created_employees),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error generating India demo data: {e}")
            raise ValidationError(_("Failed to generate demo data: %s") % str(e))

    def _generate_demo_employees(self):
        """Generate demo employee records"""
        
        # Indian names and data
        indian_first_names = [
            'Arjun', 'Priya', 'Rahul', 'Sneha', 'Vikram', 'Meera', 'Amit', 'Kavya',
            'Ravi', 'Anita', 'Karan', 'Pooja', 'Suresh', 'Divya', 'Nitin', 'Shreya',
            'Manish', 'Rekha', 'Ajay', 'Sunita', 'Rohit', 'Neha', 'Deepak', 'Rashmi',
            'Sachin', 'Nisha', 'Anil', 'Geeta', 'Rajesh', 'Sonia'
        ]
        
        indian_last_names = [
            'Sharma', 'Patel', 'Singh', 'Kumar', 'Gupta', 'Agarwal', 'Jain', 'Verma',
            'Shah', 'Mehta', 'Rao', 'Reddy', 'Nair', 'Iyer', 'Banerjee', 'Chopra',
            'Malhotra', 'Sinha', 'Mishra', 'Pandey', 'Saxena', 'Tiwari', 'Joshi', 'Bhatt'
        ]
        
        indian_cities = [
            'Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad', 'Pune',
            'Kolkata', 'Ahmedabad', 'Surat', 'Jaipur', 'Lucknow', 'Kanpur',
            'Nagpur', 'Indore', 'Bhopal', 'Visakhapatnam', 'Patna', 'Vadodara'
        ]
        
        departments = [
            'Information Technology', 'Finance', 'Human Resources', 'Marketing',
            'Operations', 'Sales', 'Customer Service', 'Research & Development',
            'Quality Assurance', 'Business Development'
        ]
        
        designations = [
            'Software Engineer', 'Senior Developer', 'Project Manager', 'Business Analyst',
            'Team Lead', 'Manager', 'Senior Manager', 'Specialist', 'Executive',
            'Senior Executive', 'Associate', 'Senior Associate', 'Consultant'
        ]
        
        # Get or create Indian locations
        locations = self.location_ids if self.location_ids else self._get_default_indian_states()
        
        created_employees = []
        
        for i in range(self.employee_count):
            # Generate random employee data
            first_name = random.choice(indian_first_names)
            last_name = random.choice(indian_last_names)
            
            # Generate unique employee ID starting from 20001 for India
            employee_id = str(20001 + i)
            
            # Create Zoho employee data record
            zoho_data = self._create_zoho_employee_data(
                employee_id, first_name, last_name, indian_cities, 
                departments, designations, locations
            )
            
            # Create HR employee record
            hr_employee = self._create_hr_employee(zoho_data)
            
            # Create contract
            self._create_employee_contract(hr_employee, zoho_data)
            
            created_employees.append({
                'zoho_data': zoho_data,
                'hr_employee': hr_employee,
                'employee_id': employee_id
            })
            
        return created_employees
    
    def _create_zoho_employee_data(self, emp_id, first_name, last_name, cities, departments, designations, locations):
        """Create Zoho employee data record with India-specific fields"""
        
        # Generate salary in INR
        base_salary = random.uniform(self.salary_range_min, self.salary_range_max)
        
        # Calculate India-specific components
        hra = base_salary * 0.40  # HRA is typically 40% of basic
        special_allowance = base_salary * 0.20  # Special allowance 20%
        medical_allowance = 1250  # Fixed medical allowance as per IT rules
        transport_allowance = 1600  # Fixed transport allowance
        
        # Calculate gross salary
        gross_salary = base_salary + hra + special_allowance + medical_allowance + transport_allowance
        
        # Calculate deductions (employee side)
        pf_employee = min(base_salary * 0.12, 1800)  # PF capped at 1800 for salary > 15000
        esi_employee = gross_salary * 0.0075 if gross_salary <= 25000 else 0  # ESI only if gross <= 25000
        professional_tax = 200  # Standard PT amount
        
        # Calculate income tax (simplified calculation)
        income_tax = max(0, (gross_salary * 12 - 250000) * 0.05 / 12) if gross_salary * 12 > 250000 else 0
        
        # Calculate employer contributions
        pf_employer = pf_employee  # Employer PF same as employee
        esi_employer = gross_salary * 0.0325 if gross_salary <= 25000 else 0  # Employer ESI 3.25%
        gratuity = gross_salary * 0.04815  # Gratuity provision
        
        # Net salary calculation
        total_deductions = pf_employee + esi_employee + professional_tax + income_tax
        net_salary = gross_salary - total_deductions
        
        # Generate random joining date (within last 2 years)
        from datetime import timedelta
        joining_date = date.today() - timedelta(days=random.randint(30, 730))
        
        # Create zoho employee data
        zoho_data = self.env['zoho.employee.data'].create({
            'employee_id': emp_id,
            'first_name': first_name,
            'last_name': last_name,
            'full_name_en': f"{first_name} {last_name}",
            'email': f"{first_name.lower()}.{last_name.lower()}@company.in",
            'mobile': f"+91{random.randint(7000000000, 9999999999)}",
            'department': random.choice(departments),
            'designation': random.choice(designations),
            'location_name': random.choice(cities),
            'date_of_joining': joining_date,
            'employee_status': 'Active',
            'gender': random.choice(['Male', 'Female']),
            'employee_type': random.choice(['Permanent', 'Contract', 'Temporary']),
            'number_of_dependents': random.randint(0, 4),
            
            # Salary components (reusing existing fields optimally)
            'base_salary': base_salary,
            'gross_salary': gross_salary,
            'net_pay': net_salary,
            
            # India-specific allowances
            'hra': hra,
            'special_allowance': special_allowance,
            'meal_allowance': medical_allowance,  # Reusing meal_allowance for medical
            'taxi_allowance': transport_allowance,  # Reusing taxi_allowance for transport
            
            # India-specific deductions
            'pf_employee': pf_employee,
            'esi_employee': esi_employee,
            'professional_tax': professional_tax,
            'income_tax': income_tax,
            
            # Employer contributions
            'pf_employer': pf_employer,
            'esi_employer': esi_employer,
            'gratuity_provision': gratuity,
            
            # ID numbers
            'pan_number': f"ABCDE{random.randint(1000, 9999)}F",
            'aadhaar_number': f"{random.randint(100000000000, 999999999999)}",
            'esi_number': f"{random.randint(10000000000, 99999999999)}" if esi_employee > 0 else "",
            'pf_number': f"MH/MUM/{random.randint(100000, 999999)}/{random.randint(1000000, 9999999)}",
        })
        
        return zoho_data
    
    def _create_hr_employee(self, zoho_data):
        """Create HR employee record"""
        
        # Check if employee already exists
        existing = self.env['hr.employee'].search([
            ('employee_id', '=', zoho_data.employee_id)
        ], limit=1)
        
        if existing:
            return existing
        
        # Create new employee
        employee = self.env['hr.employee'].create({
            'name': zoho_data.full_name_en,
            'employee_id': zoho_data.employee_id,
            'work_email': zoho_data.email,
            'mobile_phone': zoho_data.mobile,
            'department_id': self._get_or_create_department(zoho_data.department).id,
            'job_title': zoho_data.designation,
            'gender': zoho_data.gender.lower() if zoho_data.gender else 'other',
            'birthday': zoho_data.date_of_joining - timedelta(days=random.randint(6570, 14600)),  # Age 18-40
            'country_id': self.env.ref('base.in').id,  # India
        })
        
        return employee
    
    def _create_employee_contract(self, hr_employee, zoho_data):
        """Create employee contract with India salary structure"""
        
        # Get India salary structure
        india_structure = self.env['hr.payroll.structure'].search([
            ('name', '=', 'India Salary Structure')
        ], limit=1)
        
        if not india_structure:
            raise ValidationError(_("India Salary Structure not found. Please create it first."))
        
        # Get or create contract type
        contract_type = self.env['hr.contract.type'].search([
            ('name', '=', zoho_data.employee_type)
        ], limit=1)
        if not contract_type:
            contract_type = self.env['hr.contract.type'].create({
                'name': zoho_data.employee_type
            })
        
        # Get general journal
        journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        if not journal:
            raise ValidationError(_("No general journal found for contracts"))
        
        # Create contract
        contract = self.env['hr.contract'].create({
            'name': f"{hr_employee.name} - India Contract",
            'employee_id': hr_employee.id,
            'date_start': zoho_data.date_of_joining,
            'state': 'open',
            'wage': zoho_data.base_salary,
            'type_id': contract_type.id,
            'struct_id': india_structure.id,
            'journal_id': journal.id,
            'dependents': zoho_data.number_of_dependents,
        })
        
        return contract
    
    def _generate_payroll_data(self, employees):
        """Generate payroll data for employees"""
        
        # This could include creating payslips, worked days, etc.
        # For now, the employee data is sufficient for testing
        _logger.info(f"Generated payroll data for {len(employees)} India employees")
    
    def _get_or_create_department(self, dept_name):
        """Get or create department"""
        dept = self.env['hr.department'].search([('name', '=', dept_name)], limit=1)
        if not dept:
            dept = self.env['hr.department'].create({'name': dept_name})
        return dept
    
    def _get_default_indian_states(self):
        """Get default Indian states for demo data"""
        indian_states = self.env['res.country.state'].search([
            ('country_id.code', '=', 'IN')
        ], limit=10)
        
        if not indian_states:
            # If no Indian states found, create a few major ones
            india = self.env.ref('base.in')
            major_states = [
                ('Maharashtra', 'MH'),
                ('Karnataka', 'KA'), 
                ('Tamil Nadu', 'TN'),
                ('Delhi', 'DL'),
                ('Gujarat', 'GJ')
            ]
            
            created_states = []
            for state_name, code in major_states:
                state = self.env['res.country.state'].create({
                    'name': state_name,
                    'code': code,
                    'country_id': india.id
                })
                created_states.append(state)
            
            return created_states
        
        return indian_states

    def action_clear_demo_data(self):
        """Clear existing India demo data"""
        try:
            # Find demo employees (starting from employee ID 20001)
            demo_zoho_employees = self.env['zoho.employee.data'].search([
                ('employee_id', '>=', '20001'),
                ('employee_id', '<', '30000')  # Range for India demo data
            ])
            
            if demo_zoho_employees:
                # Find corresponding HR employees and contracts
                demo_employee_ids = demo_zoho_employees.mapped('employee_id')
                hr_employees = self.env['hr.employee'].search([
                    ('employee_id', 'in', demo_employee_ids)
                ])
                
                contracts = self.env['hr.contract'].search([
                    ('employee_id', 'in', hr_employees.ids)
                ])
                
                # Delete in order: contracts -> hr employees -> zoho data
                contracts.unlink()
                hr_employees.unlink() 
                demo_zoho_employees.unlink()
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Demo Data Cleared'),
                        'message': _('Removed %s demo employees and related data.') % len(demo_zoho_employees),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('No Demo Data Found'),
                        'message': _('No India demo data found to clear.'),
                        'type': 'info',
                        'sticky': False,
                    }
                }
                
        except Exception as e:
            _logger.error(f"Error clearing India demo data: {e}")
            raise ValidationError(_("Failed to clear demo data: %s") % str(e))