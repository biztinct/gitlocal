# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HRFlowWizard(models.TransientModel):
    """
    Interactive circular workflow wizard for HR operations.
    Provides a modern, animated interface for accessing various HR functions.
    """
    _name = 'hr.flow.wizard'
    _description = 'HR Workflow Flow Dashboard'

    name = fields.Char(string='Flow Dashboard', default='HR Workflow', readonly=True)

    # ==========================================
    # PRIMARY LEVEL ACTIONS
    # ==========================================

    def action_open_attendance(self):
        """Open attendance management"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Attendance'),
                'message': _('Attendance action will be configured here'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_payroll(self):
        """Open payroll management"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payroll'),
                'message': _('Payroll action will be configured here'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_approval(self):
        """Open salary approval workflow"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Salary Approval'),
                'message': _('Salary approval action will be configured here'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_pay_salary(self):
        """Open pay salary processing"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Pay Salary'),
                'message': _('Pay salary action will be configured here'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_government_reports(self):
        """Open government reports"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Government Reports'),
                'message': _('Government reports action will be configured here'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_analytics(self):
        """Open HR analytics"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Analytics'),
                'message': _('Analytics action will be configured here'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_employee(self):
        """Open employee list (center button)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Employees'),
            'res_model': 'hr.employee',
            'view_mode': 'kanban,tree,form',
            'target': 'current',
            'context': {'create': True},
        }

    # ==========================================
    # SECONDARY LEVEL ACTIONS (Attendance submenu)
    # ==========================================

    def action_open_overtime(self):
        """Open overtime management"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Overtime'),
                'message': _('Overtime action will be configured here'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_shift(self):
        """Open shift management"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shift'),
                'message': _('Shift action will be configured here'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_timesheet(self):
        """Open timesheet management"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Timesheet'),
                'message': _('Timesheet action will be configured here'),
                'type': 'info',
                'sticky': False,
            }
        }
