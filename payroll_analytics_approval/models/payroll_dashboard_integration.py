# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PayrollDashboardAnalytics(models.Model):
    _inherit = 'payroll.dashboard'
    
    def action_open_analytics_dashboard(self):
        """Open analytics dashboard for the country"""
        country = self.country
        
        # Get current month analytics
        import datetime
        today = datetime.date.today()
        first_day = today.replace(day=1)
        if today.month == 12:
            last_day = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            last_day = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)
        
        # Search for existing analytics
        analytics = self.env['payroll.analytics'].search([
            ('country', '=', country),
            ('date_from', '>=', first_day),
            ('date_to', '<=', last_day)
        ], limit=1)
        
        if analytics:
            # Open existing analytics
            return {
                'type': 'ir.actions.act_window',
                'name': f'{country} Payroll Analytics',
                'res_model': 'payroll.analytics',
                'res_id': analytics.id,
                'view_mode': 'form',
                'view_id': self.env.ref('payroll_analytics_approval.view_payroll_analytics_dashboard').id,
                'target': 'current',
            }
        else:
            # Generate new analytics
            try:
                analytics = self.env['payroll.analytics'].generate_analytics(country, first_day, last_day)
                analytics.write({'state': 'ready'})
                
                return {
                    'type': 'ir.actions.act_window',
                    'name': f'{country} Payroll Analytics',
                    'res_model': 'payroll.analytics',
                    'res_id': analytics.id,
                    'view_mode': 'form',
                    'view_id': self.env.ref('payroll_analytics_approval.view_payroll_analytics_dashboard').id,
                    'target': 'current',
                }
            except Exception as e:
                raise UserError(_('Error generating analytics: %s') % str(e))
    
    def action_export_bank_file(self):
        """Open bank export wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Export Bank File',
            'res_model': 'payroll.bank.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_country': self.country,
            }
        }
    
    @api.model
    def get_analytics_stats(self, country):
        """Get analytics statistics for dashboard tiles"""
        stats = {
            'pending_approvals': 0,
            'ready_exports': 0,
            'last_approval_date': None,
            'total_employees_current': 0,
            'total_payroll_current': 0
        }
        
        try:
            # Pending approvals
            stats['pending_approvals'] = self.env['payroll.analytics'].search_count([
                ('country', '=', country),
                ('state', '=', 'ready')
            ])
            
            # Ready exports
            stats['ready_exports'] = self.env['payroll.analytics'].search_count([
                ('country', '=', country),
                ('state', '=', 'approved')
            ])
            
            # Latest analytics for current month
            import datetime
            today = datetime.date.today()
            first_day = today.replace(day=1)
            
            latest_analytics = self.env['payroll.analytics'].search([
                ('country', '=', country),
                ('date_from', '>=', first_day)
            ], limit=1, order='date_from desc')
            
            if latest_analytics:
                stats['total_employees_current'] = latest_analytics.total_employees
                stats['total_payroll_current'] = latest_analytics.total_payroll
                
                if latest_analytics.state == 'approved':
                    stats['last_approval_date'] = latest_analytics.write_date
            
        except Exception as e:
            _logger.error(f"Error getting analytics stats: {e}")
        
        return stats


class HrPayslipRunAnalytics(models.Model):
    _inherit = 'hr.payslip.run'
    
    analytics_id = fields.Many2one('payroll.analytics', string='Analytics', readonly=True)
    
    def write(self, vals):
        """Auto-generate analytics when reaching level2"""
        result = super().write(vals)
        
        if vals.get('state') == 'level2':
            for record in self:
                if not record.analytics_id:
                    # Determine country from payslip structure
                    country_map = {
                        'Vietnam Salary Structure': 'VN',
                        'Indonesia Salary Structure': 'ID',
                        'India Salary Structure': 'IN'
                    }
                    
                    country = 'VN'  # Default
                    if record.slip_ids:
                        structure_name = record.slip_ids[0].struct_id.name
                        country = country_map.get(structure_name, 'VN')
                    
                    # Generate analytics
                    try:
                        analytics = self.env['payroll.analytics'].generate_analytics(
                            country, record.date_start, record.date_end
                        )
                        analytics.write({'state': 'ready'})
                        record.analytics_id = analytics.id
                        
                        # Send notification email
                        template = self.env.ref('payroll_analytics_approval.payroll_analytics_approval_needed_template', raise_if_not_found=False)
                        if template:
                            template.send_mail(analytics.id, force_send=True)
                            
                    except Exception as e:
                        _logger.error(f"Error auto-generating analytics: {e}")
        
        return result