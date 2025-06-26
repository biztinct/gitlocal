# Add these fields and methods to your existing PayrollBankExportWizard model

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import csv
import io
import base64
import json
from datetime import datetime

class PayrollBankExportWizard(models.TransientModel):
    _name = 'payroll.bank.export.wizard'
    _description = 'Payroll Bank Export Wizard'
    
    # Basic Information
    name = fields.Char(
        string='Export Name', 
        required=True, 
        default=lambda self: f"Bank Export {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    # Configuration Fields
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True)
    
    analytics_id = fields.Many2one(
        'payroll.analytics', 
        string='Analytics Record'
    )
    
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    
    # Export Settings
    export_format = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File'),
        ('txt', 'Text File (Bank Format)')
    ], string='Export Format', default='csv', required=True)
    
    # NOTE: This should be 'include_header' (singular) not 'include_headers' (plural)
    include_header = fields.Boolean(
        string='Include Header Row', 
        default=True
    )
    
    separator = fields.Selection([
        (',', 'Comma (,)'),
        (';', 'Semicolon (;)'),
        ('|', 'Pipe (|)'),
        ('\t', 'Tab')
    ], string='Field Separator', default=',')
    
    # Preview and Output
    preview_data = fields.Text(
        string='Data Preview', 
        readonly=True,
        help="Preview of the export data that will be generated"
    )
    
    # Export Results
    export_file = fields.Binary(string='Export File', readonly=True)
    export_filename = fields.Char(string='Export Filename', readonly=True)
    
    # State Management
    state = fields.Selection([
        ('draft', 'Configure'),
        ('done', 'Completed')
    ], string='State', default='draft')
    
    @api.model
    def _default_name(self):
        return f"Bank Export {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    @api.onchange('export_format', 'include_header', 'separator')
    def _onchange_format_settings(self):
        """Update preview when format settings change"""
        self._update_preview_data()
    
    @api.model
    def default_get(self, fields_list):
        """Set defaults and generate preview"""
        res = super().default_get(fields_list)
        
        # Set defaults from context
        if self.env.context.get('default_country'):
            res['country'] = self.env.context['default_country']
        if self.env.context.get('default_analytics_id'):
            res['analytics_id'] = self.env.context['default_analytics_id']
        if self.env.context.get('default_date_from'):
            res['date_from'] = self.env.context['default_date_from']
        if self.env.context.get('default_date_to'):
            res['date_to'] = self.env.context['default_date_to']
        
        return res
    
    @api.model
    def create(self, vals):
        """Generate preview data on create"""
        record = super().create(vals)
        record._update_preview_data()
        return record
    
    def _update_preview_data(self):
        """Update the preview data field"""
        if not self.country or not self.date_from or not self.date_to:
            self.preview_data = "Please configure country and date range to see preview."
            return
        
        try:
            # Get sample payslips for preview
            payslips = self._get_payslips_for_export()
            
            if not payslips:
                self.preview_data = f"No approved payslips found for {self.country} from {self.date_from} to {self.date_to}."
                return
            
            # Generate preview data (limit to first 10 records for performance)
            sample_payslips = payslips[:10]
            export_data = self._prepare_export_data(sample_payslips)
            
            if not export_data:
                self.preview_data = "No data available for export."
                return
            
            # Format preview based on export format
            if self.export_format == 'csv':
                preview_text = self._format_csv_preview(export_data)
            elif self.export_format == 'excel':
                preview_text = self._format_excel_preview(export_data)
            else:
                preview_text = self._format_txt_preview(export_data)
            
            # Add summary information
            total_records = len(payslips)
            total_amount = sum(data.get('Amount', 0) for data in export_data)
            
            summary = f"EXPORT SUMMARY:\n"
            summary += f"Total Records: {total_records}\n"
            summary += f"Preview Showing: {len(export_data)} records\n"
            summary += f"Total Amount: {total_amount:,.2f}\n"
            summary += f"Format: {self.export_format.upper()}\n"
            summary += f"Date Range: {self.date_from} to {self.date_to}\n"
            summary += f"Country: {self.country}\n"
            summary += "\n" + "="*80 + "\n\n"
            
            self.preview_data = summary + preview_text
            
        except Exception as e:
            self.preview_data = f"Error generating preview: {str(e)}"
    
    def _format_csv_preview(self, data):
        """Format data as CSV preview"""
        if not data:
            return "No data to preview."
        
        output = io.StringIO()
        fieldnames = list(data[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=self.separator)
        
        if self.include_header:
            writer.writeheader()
        
        for row in data:
            writer.writerow(row)
        
        return output.getvalue()
    
    def _format_excel_preview(self, data):
        """Format data as Excel preview (tab-separated)"""
        if not data:
            return "No data to preview."
        
        lines = []
        
        if self.include_header and data:
            headers = list(data[0].keys())
            lines.append('\t'.join(headers))
        
        for row in data:
            lines.append('\t'.join(str(v) for v in row.values()))
        
        return '\n'.join(lines)
    
    def _format_txt_preview(self, data):
        """Format data as fixed-width text preview"""
        if not data:
            return "No data to preview."
        
        lines = []
        
        # Fixed-width format
        for row in data:
            line = f"{str(row.get('Employee ID', '')):<12}"
            line += f"{str(row.get('Employee Name', '')):<30}"
            line += f"{str(row.get('Account Number', '')):<20}"
            line += f"{row.get('Amount', 0):>15.2f}"
            line += f"{str(row.get('Reference', '')):<20}"
            lines.append(line)
        
        # Add header if needed
        if self.include_header:
            header = f"{'Employee ID':<12}{'Employee Name':<30}{'Account Number':<20}{'Amount':>15}{'Reference':<20}"
            separator = "-" * len(header)
            lines.insert(0, separator)
            lines.insert(0, header)
        
        return '\n'.join(lines)
    
    def _get_payslips_for_export(self):
        """Get payslips for export"""
        # Map countries to salary structures
        country_structure_map = {
            'VN': 'Vietnam Salary Structure',
            'ID': 'Indonesia Salary Structure',
            'IN': 'India Salary Structure'
        }
        
        structure_name = country_structure_map.get(self.country)
        if not structure_name:
            return self.env['hr.payslip']
        
        structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
        if not structure:
            return self.env['hr.payslip']
        
        # Get approved payslips
        payslips = self.env['hr.payslip'].search([
            ('struct_id', '=', structure.id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', '=', 'done')
        ])
        
        return payslips
    
    def _prepare_export_data(self, payslips):
        """Prepare data for export"""
        export_data = []
        
        for payslip in payslips:
            net_pay_line = payslip.line_ids.filtered(lambda l: l.code == 'NETPAY')
            net_pay = net_pay_line.total if net_pay_line else 0
            
            bank_account = payslip.employee_id.bank_account_id
            
            export_data.append({
                'Employee ID': payslip.employee_id.employee_id or '',
                'Employee Name': payslip.employee_id.name or '',
                'Bank Name': bank_account.bank_id.name if bank_account and bank_account.bank_id else '',
                'Account Number': bank_account.acc_number if bank_account else '',
                'Amount': net_pay,
                'Currency': payslip.company_id.currency_id.name or '',
                'Reference': payslip.number or '',
                'Date': payslip.date_to.strftime('%Y-%m-%d') if payslip.date_to else '',
                'Department': payslip.employee_id.department_id.name if payslip.employee_id.department_id else '',
                'Job Position': payslip.employee_id.job_id.name if payslip.employee_id.job_id else ''
            })
        
        return export_data
    
    def action_generate_export(self):
        """Generate the actual export file"""
        self.ensure_one()
        
        if not self.analytics_id:
            raise UserError(_('Please select an analytics record to export'))
        
        if self.analytics_id.state != 'approved':
            raise UserError(_('Only approved analytics can be exported'))
        
        # Get all payslips for export
        payslips = self._get_payslips_for_export()
        
        if not payslips:
            raise UserError(_('No payslip data found for the selected period'))
        
        # Generate export file
        export_data = self._prepare_export_data(payslips)
        
        if self.export_format == 'csv':
            file_data, filename = self._generate_csv_export(export_data)
        elif self.export_format == 'excel':
            file_data, filename = self._generate_excel_export(export_data)
        else:
            file_data, filename = self._generate_txt_export(export_data)
        
        # Save file data
        self.write({
            'export_file': file_data,
            'export_filename': filename,
            'state': 'done'
        })
        
        # Mark analytics as exported
        if self.analytics_id:
            self.analytics_id.write({'state': 'exported'})
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.bank.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def _generate_csv_export(self, export_data):
        """Generate CSV export file"""
        output = io.StringIO()
        if export_data:
            fieldnames = list(export_data[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=self.separator)
            
            if self.include_header:
                writer.writeheader()
            
            for row in export_data:
                writer.writerow(row)
        
        file_content = output.getvalue().encode('utf-8')
        file_data = base64.b64encode(file_content)
        filename = f"bank_export_{self.country}_{self.date_from}_{self.date_to}.csv"
        
        return file_data, filename
    
    def _generate_excel_export(self, export_data):
        """Generate Excel export file"""
        # For now, use CSV format with .xlsx extension
        # In production, implement proper Excel generation with xlsxwriter
        file_data, _ = self._generate_csv_export(export_data)
        filename = f"bank_export_{self.country}_{self.date_from}_{self.date_to}.xlsx"
        return file_data, filename
    
    def _generate_txt_export(self, export_data):
        """Generate text export file"""
        lines = []
        
        for row in export_data:
            line = f"{str(row.get('Employee ID', '')):<12}"
            line += f"{str(row.get('Employee Name', '')):<30}"
            line += f"{str(row.get('Account Number', '')):<20}"
            line += f"{row.get('Amount', 0):>15.2f}"
            line += f"{str(row.get('Reference', '')):<20}"
            lines.append(line)
        
        file_content = '\n'.join(lines).encode('utf-8')
        file_data = base64.b64encode(file_content)
        filename = f"bank_export_{self.country}_{self.date_from}_{self.date_to}.txt"
        
        return file_data, filename