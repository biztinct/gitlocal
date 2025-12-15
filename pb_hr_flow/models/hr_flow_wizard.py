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

    name = fields.Char(string='Flow Dashboard', default=lambda self: self._default_name(), readonly=True)

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

    def action_open_government_panel(self):
        """No-op handler to satisfy button name; JS opens the tertiary panel."""
        return False

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

    # ==========================================
    # Tertiary actions resolver (server-side to avoid private RPC)
    # ==========================================

    @api.model
    def get_tertiary_action(self, key):
        """
        Return a full action dict for a tertiary tile.
        Uses server-side xmlid resolution so the client can simply do-action.
        """
        # Map keys to action xmlid and optional menu xmlid
        mapping = {
            # Overtime
            'overtime-request': ('hr_attendance.hr_attendance_overtime_action',
                                 'hr_attendance.menu_hr_attendance_attendances_overview'),
            'overtime-approve': ('hr_attendance.hr_attendance_action_overview',
                                 'hr_attendance.menu_hr_attendance_attendances_overview'),
            'overtime-rules': ('hr_attendance_reason.action_hr_attendance_reason',
                               'hr_attendance.hr_attendance_reason_menu'),
            'overtime-schedules': ('resource.action_resource_calendar_form',
                                   'hr_employee_shift.menu_shift'),
            'overtime-analytics': ('hr_attendance.hr_attendance_action_overview',
                                   'hr_attendance.menu_hr_attendance_attendances_overview'),
            'overtime-settings': ('hr_attendance.action_hr_attendance_settings',
                                  'hr_attendance.menu_hr_attendance_settings'),
            # Shift
            'shift-calendar': ('resource.action_resource_calendar_form',
                               'hr_employee_shift.menu_shift'),
            'shift-templates': ('resource.action_resource_calendar_form',
                                'hr_employee_shift.menu_conf_shift'),
            'shift-swap': ('hr_employee_shift.generate_schedule_action_window',
                           'hr_employee_shift.menu_shift_schedule_generate_id_menu'),
            'shift-compliance': ('hr_attendance.hr_attendance_action',
                                 'hr_attendance.menu_hr_attendance_view_attendances'),
            'shift-attendance': ('hr_attendance.hr_attendance_action_employee',
                                 'hr_attendance.menu_hr_attendance_view_attendances'),
            'shift-settings': ('hr_attendance.action_hr_attendance_settings',
                               'hr_attendance.menu_hr_attendance_settings'),
            # Timesheet
            'timesheet-mine': ('hr_timesheet.act_hr_timesheet_line',
                               'hr_timesheet.timesheet_menu_root'),
            'timesheet-approvals': ('hr_timesheet_sheet.act_hr_timesheet_sheet_to_review',
                                    'hr_timesheet.menu_hr_to_review'),
            'timesheet-reports': ('hr_timesheet.act_hr_timesheet_report',
                                  'hr_timesheet.menu_hr_time_tracking'),
            'timesheet-settings': ('hr_timesheet.act_hr_timesheet_line',
                                   'hr_timesheet.menu_hr_time_tracking'),
            # Payroll
            'payroll-connector': ('pb_hr_payroll_formula.action_integration_connector', False),
            'payroll-config': ('pb_hr_payroll_formula.action_formula_config', False),
            'payroll-test': ('pb_hr_payroll_formula.action_sample_data', False),
            'payroll-batch': ('pb_hr_payroll_formula.action_payroll_import_batch', False),
            'payroll-payslip': ('om_hr_payroll.action_view_hr_payslip_form', False),
            'payroll-draft-posted': ('om_hr_payroll.action_view_hr_payslip_form', False),
            # Approval (reuse analytics approval dashboard)
            'approval-pending': ('payroll_analytics_approval.action_payroll_analytics_dashboard', False),
            'approval-history': ('payroll_analytics_approval.action_payroll_analytics_dashboard', False),
            'approval-rules': ('payroll_analytics_approval.action_payroll_analytics_dashboard', False),
            # Pay Salary
            'pay-salary-bank': ('om_hr_payroll_account.action_hr_payslip_run', False),
            'pay-salary-payments': ('account.action_account_payments', False),
            'pay-salary-journals': ('account.action_move_journal_line', False),
            # Government reports (xlsx)
            'govt-bhxh630': ('pb_hr_govt.action_pb_govt_report_wizard', False),
            'govt-bhxhdstk01': ('pb_hr_govt.action_pb_govt_report_wizard', False),
            'govt-d01': ('pb_hr_govt.action_pb_govt_report_wizard', False),
            'govt-tang': ('pb_hr_govt.action_pb_govt_report_wizard', False),
            'govt-giam': ('pb_hr_govt.action_pb_govt_report_wizard', False),
        }
        action_xmlid, menu_xmlid = mapping.get(key, (False, False))
        if not action_xmlid:
            return {'type': 'ir.actions.act_window_close'}

        try:
            action = self.env['ir.actions.actions']._for_xml_id(action_xmlid)
        except Exception:
            return {'type': 'ir.actions.act_window_close'}

        # open full-screen so breadcrumbs and full controls show
        action['target'] = 'current'

        # Apply contextual defaults for special cases
        if key == 'payroll-draft-posted':
            action.setdefault('context', {})
            action['context'] = dict(action['context'], search_default_draft=1, search_default_done=1)
        if key.startswith('govt-'):
            report_type = key.replace('govt-', '')
            action.setdefault('context', {})
            action['context'] = dict(action['context'], default_report_type=report_type)

        # Resolve menu id if present
        if menu_xmlid:
            menu = self.env.ref(menu_xmlid, raise_if_not_found=False)
            if menu:
                action['menu_id'] = menu.id
        return action

    # ==========================================
    # Defaults / helpers
    # ==========================================

    @api.model
    def _default_name(self):
        """Ensure the control panel title is always meaningful (no 'New')."""
        return _('Flow Dashboard')

    @api.model
    def default_get(self, fields_list):
        """Guarantee name is set even if context/defaults are missing."""
        res = super().default_get(fields_list)
        if 'name' in fields_list:
            res.setdefault('name', self._default_name())
        return res
