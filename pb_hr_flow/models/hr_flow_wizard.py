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
            'overtime-request': ('ohrms_overtime.hr_overtime_action', False),
            'overtime-approve': ('_overtime_approve', False),  # Custom action with domain filter
            'overtime-rules': ('ohrms_overtime.hr_overtime_type_action', False),
            'overtime-analytics': ('hr_attendance.hr_attendance_report_action', False),
            'overtime-settings': ('hr_attendance.action_hr_attendance_settings',
                                  'hr_attendance.menu_hr_attendance_settings'),
            # Shift - Updated to use hr_shift module actions
            'shift-calendar': ('hr_shift.shift_planning_action', False),
            'shift-templates': ('hr_shift.shift_template_action', False),
            'shift-planning': ('hr_shift.shift_planning_action', False),
            'shift-my-calendar': ('hr_shift.my_shifts_planning_action', False),
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
            # Leaves
            'leaves-dashboard': ('hr_holidays.hr_leave_action_new_request', False),
            'leaves-accrual': ('hr_holidays.open_view_accrual_plans', False),
            'leaves-public-holidays': ('hr_holidays_public.open_holidays_public_view', False),
            'leaves-approvals': ('hr_holidays.hr_leave_action_action_approve_department', False),
            # Payroll - Updated with correct kanban actions
            'payroll-connector': ('pb_hr_payroll_formula.action_integration_connector_kanban', False),
            'payroll-config': ('pb_hr_payroll_formula.action_formula_config_kanban', False),
            'payroll-payslip-config': ('pb_hr_payroll_formula.action_payslip_config', False),
            'payroll-test': ('pb_hr_payroll_formula.action_sample_data', False),
            'payroll-batch': ('pb_hr_payroll_formula.action_payroll_import_batch', False),
            'payroll-batch-workflow': ('om_hr_payroll.action_hr_payslip_run_tree', False),
            'payroll-payslip': ('om_hr_payroll.action_view_hr_payslip_form', False),
            'payroll-full-and-final': ('pb_hr_fullandfinal.action_full_and_final_employees', False),
            'payroll-salary-analytics': ('pb_hr_flow.action_hr_payslip_line_analytics', False),
            # Approval - Updated to use Approval Queue action
            'approval-pending': ('payroll_analytics_approval.action_payroll_approval_queue', False),
            'approval-history': ('payroll_analytics_approval.action_payroll_approval_queue', False),
            'approval-rules': ('payroll_analytics_approval.action_payroll_approval_queue', False),
            # Pay Salary - Bank Export uses wizard action
            'pay-salary-bank': ('payroll_analytics_approval.action_payroll_bank_export_wizard', False),
            'pay-salary-payments': ('account.action_account_payments', False),
            'pay-salary-journals': ('account.action_move_journal_line', False),
            # Government reports - Handled separately via _get_govt_report_action
            'govt-bhxh630': ('_govt_report', 'bhxh630'),
            'govt-bhxhdstk01': ('_govt_report', 'bhxhdstk01'),
            'govt-d01': ('_govt_report', 'd01'),
            'govt-tang': ('_govt_report', 'tang_ld'),
            'govt-giam': ('_govt_report', 'giam_ld'),
            'govt-monthly-bhxh630': ('pb_hr_govt.action_govt_monthly_bhxh630', False),
            'govt-monthly-bhxhdstk01': ('pb_hr_govt.action_govt_monthly_bhxhdstk01', False),
            'govt-monthly-d01': ('pb_hr_govt.action_govt_monthly_bangke_d01', False),
            'govt-monthly-giam': ('pb_hr_govt.action_govt_monthly_giam_ld', False),
            'govt-monthly-tang': ('pb_hr_govt.action_govt_monthly_tang_ld', False),
            # Analytics - Uses server action to prepare dashboard
            'analytics-dashboard': ('pb_hr_payroll_analytics.action_prepare_hr_analytics_dashboard', False),
        }

        action_xmlid, menu_xmlid = mapping.get(key, (False, False))
        if not action_xmlid:
            return {'type': 'ir.actions.act_window_close', 'context': {}}

        # Handle government reports specially - open the report wizard directly
        if action_xmlid == '_govt_report':
            return self._get_govt_report_action(menu_xmlid)

        # Handle overtime approval queue - open with domain filter for pending approvals
        if action_xmlid == '_overtime_approve':
            return self._get_overtime_approve_action()

        try:
            action = self.env['ir.actions.actions']._for_xml_id(action_xmlid)
        except Exception:
            return {'type': 'ir.actions.act_window_close', 'context': {}}

        # open full-screen so breadcrumbs and full controls show
        if action.get('target') != 'new':
            action['target'] = 'current'
        action.setdefault('context', {})

        # No special context handling needed for current routes

        # Resolve menu id if present
        if menu_xmlid:
            menu = self.env.ref(menu_xmlid, raise_if_not_found=False)
            if menu:
                action['menu_id'] = menu.id
        return action

    @api.model
    def _get_govt_report_action(self, report_type):
        """
        Return action to directly open the government report wizard.
        The report_type determines which report will be pre-selected.
        Skips the selector dashboard and opens the report wizard directly.
        """
        try:
            view_id = self.env.ref('pb_hr_govt.view_pb_govt_report_wizard_form').id
        except Exception:
            view_id = False

        return {
            'name': _('Vietnam Government XLS Reports'),
            'type': 'ir.actions.act_window',
            'res_model': 'pb.govt.report.wizard',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'default_report_type': report_type,
            },
        }

    @api.model
    def _get_overtime_approve_action(self):
        """
        Return action to open overtime requests pending approval (Manager Approval Queue).
        Filters to show only requests in 'f_approve' state.
        """
        try:
            # Try to get the view IDs
            tree_view_id = self.env.ref('ohrms_overtime.hr_overtime_tree_view').id
            form_view_id = self.env.ref('ohrms_overtime.hr_overtime_form_view').id
        except Exception:
            tree_view_id = False
            form_view_id = False

        return {
            'name': _('Overtime Approval Queue'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.overtime',
            'view_mode': 'tree,form',
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('state', '=', 'f_approve')],
            'target': 'current',
            'context': {},
        }

    def action_open_approval_dashboard(self):
        """Open the payroll approval queue dashboard"""
        self.ensure_one()
        try:
            action = self.env['ir.actions.actions']._for_xml_id(
                'payroll_analytics_approval.action_payroll_approval_queue'
            )
            action['target'] = 'current'
            return action
        except Exception:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Approval Dashboard'),
                    'message': _('Approval module not installed or configured'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    def action_open_bank_export(self):
        """Open the bank export wizard"""
        self.ensure_one()
        try:
            action = self.env['ir.actions.actions']._for_xml_id(
                'payroll_analytics_approval.action_payroll_bank_export_wizard'
            )
            action['target'] = 'new'
            return action
        except Exception:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Bank Export'),
                    'message': _('Bank export module not installed or configured'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    def action_open_analytics_dashboard(self):
        """Open the HR Analytics Dashboard"""
        self.ensure_one()
        try:
            # Use server action to ensure dashboard record exists
            action = self.env['ir.actions.actions']._for_xml_id(
                'pb_hr_payroll_analytics.action_prepare_hr_analytics_dashboard'
            )
            return action
        except Exception:
            # Fallback - try direct window action
            try:
                action = self.env['ir.actions.actions']._for_xml_id(
                    'pb_hr_payroll_analytics.action_open_hr_analytics_dashboard'
                )
                action['target'] = 'current'
                return action
            except Exception:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Analytics Dashboard'),
                        'message': _('Analytics module not installed or configured'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }

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
