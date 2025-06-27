# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class GratuityPaymentWizard(models.TransientModel):
    _name = 'gratuity.payment.wizard'
    _description = 'Gratuity Payment Wizard for India'
    
    employee_ids = fields.Many2many('hr.employee', string='Employees', 
                                    domain="[('contract_ids.struct_id.name', '=', 'India Salary Structure')]")
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True)
    reason = fields.Selection([
        ('resignation', 'Resignation'),
        ('retirement', 'Retirement'),
        ('termination', 'Termination'),
        ('death', 'Death'),
        ('disability', 'Disability')
    ], string='Reason for Payment', default='resignation', required=True)
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Get active employee if called from employee form
        if self.env.context.get('active_model') == 'hr.employee' and self.env.context.get('active_id'):
            res['employee_ids'] = [(6, 0, [self.env.context['active_id']])]
        
        return res
    
    def calculate_gratuity(self, employee):
        """Calculate gratuity amount for an employee"""
        if not employee.contract_id:
            raise UserError(f"No active contract found for employee {employee.name}")
        
        contract = employee.contract_id
        
        # Check if employee is eligible for gratuity (minimum 5 years service)
        if not contract.date_start:
            raise UserError(f"Contract start date not found for employee {employee.name}")
        
        # Calculate years of service
        end_date = self.payment_date
        start_date = contract.date_start
        service_period = relativedelta(end_date, start_date)
        years_of_service = service_period.years
        months_of_service = service_period.months
        
        # Round up if more than 6 months
        if months_of_service >= 6:
            years_of_service += 1
        
        # Minimum 5 years service required for gratuity
        if years_of_service < 5:
            return 0, years_of_service
        
        # Get last drawn salary (basic + DA if applicable)
        # For simplicity, using basic salary from advantages
        basic_adv = contract.advantage_ids.filtered(lambda a: a.advantage_template_id.code == 'BASIC')
        basic_salary = basic_adv[0].amount if basic_adv else contract.wage * 0.5
        
        # Gratuity calculation: (Basic Salary × 15 days × Years of Service) / 26
        # 15 days for each completed year of service
        gratuity_days = contract.gratuity_rate if hasattr(contract, 'gratuity_rate') else 15
        gratuity_amount = (basic_salary * gratuity_days * years_of_service) / 26
        
        # Maximum gratuity limit as per Indian law (currently ₹20,00,000)
        max_gratuity = 2000000
        if gratuity_amount > max_gratuity:
            gratuity_amount = max_gratuity
        
        return gratuity_amount, years_of_service
    
    def process_gratuity_payment(self):
        """Process gratuity payment for selected employees"""
        if not self.employee_ids:
            raise UserError("Please select at least one employee.")
        
        gratuity_payments = []
        
        for employee in self.employee_ids:
            try:
                gratuity_amount, years_of_service = self.calculate_gratuity(employee)
                
                if gratuity_amount > 0:
                    # Create a special payslip for gratuity
                    payslip_data = {
                        'employee_id': employee.id,
                        'name': f"Gratuity Payment - {employee.name}",
                        'date_from': self.payment_date,
                        'date_to': self.payment_date,
                        'contract_id': employee.contract_id.id,
                        'struct_id': employee.contract_id.struct_id.id,
                    }
                    
                    payslip = self.env['hr.payslip'].create(payslip_data)
                    
                    # Add gratuity payment line manually
                    payslip_line_data = {
                        'slip_id': payslip.id,
                        'name': 'Gratuity Payment',
                        'code': 'GRATUITY',
                        'category_id': self.env.ref('om_hr_payroll.ALW').id,
                        'sequence': 1,
                        'amount': gratuity_amount,
                        'total': gratuity_amount,
                        'quantity': 1,
                        'rate': 100,
                    }
                    
                    self.env['hr.payslip.line'].create(payslip_line_data)
                    
                    gratuity_payments.append({
                        'employee': employee.name,
                        'years_of_service': years_of_service,
                        'gratuity_amount': gratuity_amount,
                        'payslip_id': payslip.id
                    })
                else:
                    gratuity_payments.append({
                        'employee': employee.name,
                        'years_of_service': years_of_service,
                        'gratuity_amount': 0,
                        'message': 'Not eligible (less than 5 years service)'
                    })
                    
            except Exception as e:
                gratuity_payments.append({
                    'employee': employee.name,
                    'error': str(e)
                })
        
        # Return summary
        message = "Gratuity Processing Summary:\n\n"
        for payment in gratuity_payments:
            if 'error' in payment:
                message += f"❌ {payment['employee']}: Error - {payment['error']}\n"
            elif payment['gratuity_amount'] > 0:
                message += f"✅ {payment['employee']}: ₹{payment['gratuity_amount']:,.2f} ({payment['years_of_service']} years)\n"
            else:
                message += f"⚠️ {payment['employee']}: {payment.get('message', 'No gratuity')}\n"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Gratuity Payment Processed',
                'message': message,
                'type': 'success',
                'sticky': True,
            }
        }