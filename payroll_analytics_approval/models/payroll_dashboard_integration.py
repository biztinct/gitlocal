# Add these methods to your PayrollDashboardAnalytics model in models/payroll_dashboard_integration.py

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import datetime

_logger = logging.getLogger(__name__)


class PayrollDashboardAnalytics(models.Model):
    _inherit = 'payroll.dashboard'
    
    def action_open_analytics_dashboard(self):
        """Open analytics dashboard for the country"""
        # Handle both direct calls and web calls
        try:
            # If called as method on recordset, get country from record
            if self and hasattr(self, 'country') and self.country:
                country = self.country
            else:
                # If called from web interface or as model method, try context
                country = self.env.context.get('default_country')
                if not country:
                    # Try to get from active record if available
                    active_id = self.env.context.get('active_id')
                    if active_id:
                        dashboard_record = self.browse(active_id)
                        if dashboard_record.exists() and dashboard_record.country:
                            country = dashboard_record.country
            
            # If still no country, try to infer from user access or default to VN
            if not country:
                # Default to Vietnam for now, or could be made configurable
                country = 'VN'
                _logger.warning("No country specified, defaulting to VN")
                
        except Exception as e:
            _logger.error(f"Error getting country in action_open_analytics_dashboard: {e}")
            country = 'VN'  # Fallback
        
        if not country:
            raise UserError(_('Unable to determine country for analytics dashboard'))
        
        # Get current month analytics
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
        
        # Force regeneration to get fresh data and debug info
        if analytics:
            _logger.info(f"Found existing analytics record for {country}, regenerating...")
            analytics.unlink()
            analytics = None
        
        # Generate new analytics
        try:
            analytics = self.env['payroll.analytics'].generate_analytics(country, first_day, last_day)
            analytics.write({'state': 'ready'})
            
            return {
                'type': 'ir.actions.act_window',
                'name': f'{country} Payroll Analytics Dashboard',
                'res_model': 'payroll.analytics',
                'res_id': analytics.id,
                'view_mode': 'form',
                'view_id': self.env.ref('payroll_analytics_approval.view_payroll_analytics_dashboard').id,
                'target': 'current',
                'context': {'create': False, 'edit': False}
            }
        except Exception as e:
            _logger.error(f"Error generating analytics for {country}: {e}")
            # Fall back to showing analytics list
            return {
                'type': 'ir.actions.act_window',
                'name': f'{country} Payroll Analytics',
                'res_model': 'payroll.analytics',
                'view_mode': 'tree,form',
                'domain': [('country', '=', country)],
                'context': {'default_country': country, 'search_default_ready': 1},
                'target': 'current',
            }
    
    def action_export_bank_file(self):
        """Open bank export wizard for approved payroll"""
        # Handle both direct calls and web calls - same logic as analytics
        try:
            if self and hasattr(self, 'country') and self.country:
                country = self.country
            else:
                country = self.env.context.get('default_country')
                if not country:
                    active_id = self.env.context.get('active_id')
                    if active_id:
                        dashboard_record = self.browse(active_id)
                        if dashboard_record.exists() and dashboard_record.country:
                            country = dashboard_record.country
            
            if not country:
                country = 'VN'  # Fallback
                _logger.warning("No country specified in export, defaulting to VN")
                
        except Exception as e:
            _logger.error(f"Error getting country in action_export_bank_file: {e}")
            country = 'VN'
        
        if not country:
            raise UserError(_('Unable to determine country for bank export'))
        
        # Check if there are approved analytics for export
        approved_analytics = self.env['payroll.analytics'].search([
            ('country', '=', country),
            ('state', '=', 'approved')
        ], limit=1)
        
        if approved_analytics:
            # Open bank export wizard with pre-filled data
            return {
                'type': 'ir.actions.act_window',
                'name': f'Export Bank File - {country}',
                'res_model': 'payroll.bank.export.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_country': country,
                    'default_analytics_id': approved_analytics.id,
                    'default_date_from': approved_analytics.date_from,
                    'default_date_to': approved_analytics.date_to,
                }
            }
        else:
            # Show message and redirect to approval queue
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Data Available'),
                    'message': _('No approved payroll data available for export. Please approve payroll analytics first.'),
                    'type': 'warning',
                    'sticky': False,
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
            # Pending approvals (analytics in ready state)
            pending = self.env['payroll.analytics'].search([
                ('country', '=', country),
                ('state', '=', 'ready')
            ])
            stats['pending_approvals'] = len(pending)
            
            # Ready for export (approved analytics)
            ready_exports = self.env['payroll.analytics'].search([
                ('country', '=', country),
                ('state', '=', 'approved')
            ])
            stats['ready_exports'] = len(ready_exports)
            
            # Last approval date
            last_approved = self.env['payroll.analytics'].search([
                ('country', '=', country),
                ('state', '=', 'approved')
            ], order='write_date desc', limit=1)
            
            if last_approved:
                stats['last_approval_date'] = last_approved.write_date.strftime('%Y-%m-%d')
            
            # Current month stats
            today = datetime.date.today()
            first_day = today.replace(day=1)
            
            current_analytics = self.env['payroll.analytics'].search([
                ('country', '=', country),
                ('date_from', '>=', first_day),
                ('state', 'in', ['ready', 'approved'])
            ], limit=1)
            
            if current_analytics:
                stats['total_employees_current'] = current_analytics.total_employees
                stats['total_payroll_current'] = current_analytics.total_payroll
                
        except Exception as e:
            _logger.error(f"Error getting analytics stats for {country}: {e}")
        
        return stats