from odoo import api, fields, models, _
from odoo.exceptions import UserError
import csv
import io
import base64
import logging
import datetime

_logger = logging.getLogger(__name__)


class PayrollBankExportWizardStandalone(models.TransientModel):
    _name = 'payroll.bank.export.wizard'
    _description = 'Standalone Bank Export Wizard'
    
    analytics_id = fields.Many2one('payroll.analytics', string='Analytics')
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True)
    date_from = fields.Date(string='Date From', required=True, default=fields.Date.today)
    date_to = fields.Date(string='Date To', required=True, default=fields.Date.today)
    export_format = fields.Selection([
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('txt', 'Text File')
    ], string='Export Format', default='csv')
    include_header = fields.Boolean(string='Include Headers', default=True)
    
    # Export file
    export_file = fields.Binary(string='Export File', readonly=True)
    export_filename = fields.Char(string='Filename', readonly=True)
    
    # Preview fields - THESE WERE MISSING
    preview_record_count = fields.Integer(string='Preview Record Count', readonly=True)
    preview_total_amount = fields.Monetary(string='Preview Total Amount', readonly=True, 
                                           currency_field='currency_id')
    preview_data = fields.Text(string='Preview Data', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)
    
    @api.model
    def default_get(self, fields_list):
        """Set defaults based on context"""
        res = super().default_get(fields_list)
        
        if self.env.context.get('default_country'):
            res['country'] = self.env.context['default_country']
        
        # Set current month dates
        today = datetime.date.today()
        first_day = today.replace(day=1)
        if today.month == 12:
            last_day = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            last_day = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)
        
        res.update({
            'date_from': first_day,
            'date_to': last_day
        })
        
        return res
    
    @api.onchange('date_from', 'date_to', 'country')
    def _onchange_generate_preview(self):
        """Generate preview when dates or country change"""
        if self.date_from and self.date_to and self.country:
            self._generate_preview()
    
    def _generate_preview(self):
        """Generate preview of export data"""
        try:
            # Get payslips for preview
            payslips = self._get_payslips_for_export()
            
            # Calculate totals
            total_amount = 0
            preview_lines = []
            
            for payslip in payslips:
                net_pay_line = payslip.line_ids.filtered(lambda l: l.code == 'NETPAY')
                net_pay = net_pay_line[0].total if net_pay_line else 0
                total_amount += net_pay
                
                preview_lines.append(f"{payslip.employee_id.name}: {net_pay}")
            
            # Update preview fields
            self.preview_record_count = len(payslips)
            self.preview_total_amount = total_amount
            self.preview_data = '\n'.join(preview_lines[:10])  # Show first 10 lines
            
        except Exception as e:
            self.preview_record_count = 0
            self.preview_total_amount = 0
            self.preview_data = f"Error generating preview: {str(e)}"
    
    def _get_payslips_for_export(self):
        """Get payslips for export based on criteria"""
        domain = [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', '=', 'done')
        ]
        
        # Filter by country structure
        country_structure_map = {
            'VN': 'Vietnam Salary Structure',
            'ID': 'Indonesia Salary Structure',
            'IN': 'India Salary Structure'
        }
        structure_name = country_structure_map.get(self.country)
        
        payslips = self.env['hr.payslip'].search(domain)
        
        if structure_name:
            structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
            if structure:
                payslips = payslips.filtered(lambda p: p.struct_id.id == structure.id)
        
        return payslips
    
    def action_generate_export(self):
        """Generate bank export file"""
        self.ensure_one()
        
        # Get approved payslips for the period and country
        payslips = self._get_payslips_for_export()
        
        if not payslips:
            raise UserError(_('No approved payslips found for the selected period and country'))
        
        # Generate export data
        export_data = self._prepare_export_data(payslips)
        
        # Create file based on format
        if self.export_format == 'csv':
            file_content, filename = self._create_csv_file(export_data)
        elif self.export_format == 'excel':
            file_content, filename = self._create_excel_file(export_data)
        else:
            file_content, filename = self._create_txt_file(export_data)
        
        # Update wizard with file
        self.write({
            'export_file': base64.b64encode(file_content),
            'export_filename': filename
        })
        
        # Update analytics state if linked
        if self.analytics_id:
            self.analytics_id.write({'state': 'exported'})
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.bank.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }
    
    def _prepare_export_data(self, payslips):
        """Prepare data for export"""
        export_data = []
        
        for payslip in payslips:
            net_pay_line = payslip.line_ids.filtered(lambda l: l.code == 'NETPAY')
            net_pay = net_pay_line[0].total if net_pay_line else 0
            
            bank_account = payslip.employee_id.bank_account_id
            
            export_data.append({
                'Employee ID': payslip.employee_id.employee_id or '',
                'Employee Name': payslip.employee_id.name,
                'Bank Name': bank_account.bank_id.name if bank_account and bank_account.bank_id else '',
                'Account Number': bank_account.acc_number if bank_account else '',
                'Amount': net_pay,
                'Currency': payslip.company_id.currency_id.name,
                'Reference': payslip.number,
                'Date': payslip.date_to.strftime('%Y-%m-%d'),
                'Department': payslip.employee_id.department_id.name if payslip.employee_id.department_id else '',
                'Job Position': payslip.employee_id.job_id.name if payslip.employee_id.job_id else ''
            })
        
        return export_data
    
    def _create_csv_file(self, data):
        """Create CSV file"""
        output = io.StringIO()
        if data:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            
            if self.include_headers:
                writer.writeheader()
            
            for row in data:
                writer.writerow(row)
        
        filename = f"bank_export_{self.country}_{self.date_from.strftime('%Y%m%d')}.csv"
        return output.getvalue().encode('utf-8'), filename
    
    def _create_excel_file(self, data):
        """Create Excel file (simplified implementation)"""
        # For now, return CSV with .xlsx extension
        # In production, implement proper Excel generation with xlsxwriter
        content, _ = self._create_csv_file(data)
        filename = f"bank_export_{self.country}_{self.date_from.strftime('%Y%m%d')}.xlsx"
        return content, filename
    
    def _create_txt_file(self, data):
        """Create text file"""
        lines = []
        if self.include_headers and data:
            headers = list(data[0].keys())
            lines.append('\t'.join(headers))
        
        for row in data:
            lines.append('\t'.join(str(v) for v in row.values()))
        
        filename = f"bank_export_{self.country}_{self.date_from.strftime('%Y%m%d')}.txt"
        return '\n'.join(lines).encode('utf-8'), filename
    
    def action_preview_export(self):
        """Generate preview of export data"""
        self.ensure_one()
        self._generate_preview()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.bank.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }
    
    def action_download_export(self):
        """Download the generated export file"""
        self.ensure_one()
        
        if not self.export_file:
            raise UserError(_('No export file available. Please generate the export first.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/export_file/{self.export_filename}?download=true',
            'target': 'self',
        }
    
    def action_reset_wizard(self):
        """Reset the wizard to initial state"""
        self.ensure_one()
        
        self.write({
            'export_file': False,
            'export_filename': False,
            'preview_record_count': 0,
            'preview_total_amount': 0,
            'preview_data': False,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.bank.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }