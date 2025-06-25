# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import csv
import io
import base64
import logging

_logger = logging.getLogger(__name__)


class PayrollBankExportWizard(models.TransientModel):
    _name = 'payroll.bank.export.wizard'
    _description = 'Bank Export Wizard'
    
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
    include_headers = fields.Boolean(string='Include Headers', default=True)
    
    # Preview fields - NEW
    preview_data = fields.Text(string='Preview Data', readonly=True)
    preview_record_count = fields.Integer(string='Preview Record Count', readonly=True)
    preview_total_amount = fields.Monetary(string='Preview Total Amount', readonly=True)
    
    # Export file
    export_file = fields.Binary(string='Export File', readonly=True)
    export_filename = fields.Char(string='Filename', readonly=True)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    
    @api.model
    def default_get(self, fields_list):
        """Set defaults based on context"""
        res = super().default_get(fields_list)
        
        if self.env.context.get('default_country'):
            res['country'] = self.env.context['default_country']
        
        # Set current month dates
        import datetime
        today = datetime.date.today()
        first_day = today.replace(day=1)
        if today.month == 12:
            last_day = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            last_day = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)
        
        res['date_from'] = first_day
        res['date_to'] = last_day
        
        return res

    def action_preview_export(self):
        """Preview the export data - NEW METHOD"""
        self.ensure_one()
        
        try:
            # Get payslip data for preview
            export_data = self._prepare_export_data()
            
            if not export_data:
                raise UserError(_('No payslip data found for the selected period and country.'))
            
            # Calculate preview statistics
            total_amount = sum(row.get('Amount', 0) for row in export_data)
            record_count = len(export_data)
            
            # Create preview text (first 10 records)
            preview_lines = []
            if self.include_headers and export_data:
                headers = list(export_data[0].keys())
                preview_lines.append('\t'.join(headers))
            
            for i, row in enumerate(export_data[:10]):  # Show first 10 records
                preview_lines.append('\t'.join(str(v) for v in row.values()))
            
            if len(export_data) > 10:
                preview_lines.append(f"... and {len(export_data) - 10} more records")
            
            # Update preview fields
            self.write({
                'preview_data': '\n'.join(preview_lines),
                'preview_record_count': record_count,
                'preview_total_amount': total_amount,
            })
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'payroll.bank.export.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': self.env.context
            }
            
        except Exception as e:
            raise UserError(_('Error generating preview: %s') % str(e))

    def action_generate_export(self):
        """Generate bank export file"""
        self.ensure_one()
        
        try:
            # Get export data
            export_data = self._prepare_export_data()
            
            if not export_data:
                raise UserError(_('No payslip data found for the selected period and country.'))
            
            # Generate file based on format
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
            
            # Create export log record
            self._create_export_log(export_data, filename)
            
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
            
        except Exception as e:
            raise UserError(_('Error generating export: %s') % str(e))

    def action_download_export(self):
        """Download the generated export file - NEW METHOD"""
        self.ensure_one()
        
        if not self.export_file:
            raise UserError(_('No export file available. Please generate the export first.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/payroll.bank.export.wizard/{self.id}/export_file/{self.export_filename}?download=true',
            'target': 'self',
        }

    def action_reset_wizard(self):
        """Reset wizard to initial state - NEW METHOD"""
        self.ensure_one()
        
        self.write({
            'preview_data': False,
            'preview_record_count': 0,
            'preview_total_amount': 0,
            'export_file': False,
            'export_filename': False,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.bank.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }

    def _prepare_export_data(self):
        """Prepare data for export"""
        self.ensure_one()
        
        # Get payslip runs for the period
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '>=', self.date_from),
            ('date_end', '<=', self.date_to),
            ('state', '=', 'done')
        ])
        
        # Filter by country if needed (this depends on your payroll structure setup)
        # You might need to adjust this based on how country is determined in your payslips
        
        export_data = []
        
        for run in payslip_runs:
            for payslip in run.slip_ids:
                # Get net pay
                net_pay_line = payslip.line_ids.filtered(lambda l: l.code == 'NETPAY')
                net_pay = net_pay_line[0].total if net_pay_line else 0
                
                if net_pay <= 0:
                    continue  # Skip employees with no net pay
                
                # Get bank account
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
        """Create Excel file (simplified - would need xlsxwriter for full implementation)"""
        # For now, return CSV with .xlsx extension
        # In production, implement proper Excel generation
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

    def _create_export_log(self, export_data, filename):
        """Create export log record"""
        try:
            total_amount = sum(row.get('Amount', 0) for row in export_data)
            
            self.env['bank.export.log'].create({
                'period_name': f"{self.date_from.strftime('%B %Y')}",
                'country': self.country,
                'export_date': fields.Datetime.now(),
                'total_records': len(export_data),
                'total_amount': total_amount,
                'export_format': self.export_format,
                'filename': filename,
                'export_file': self.export_file,
                'export_details': f"Exported {len(export_data)} records with total amount {total_amount}",
                'created_by': self.env.user.id,
            })
        except Exception as e:
            _logger.warning(f"Could not create export log: {e}")
            # Don't fail the export if log creation fails