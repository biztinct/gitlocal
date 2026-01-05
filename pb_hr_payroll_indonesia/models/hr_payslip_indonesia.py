# -*- coding: utf-8 -*-

from collections import defaultdict
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrPayslipIndonesia(models.Model):
    _inherit = 'hr.payslip'

    @staticmethod
    def _report_to_number(value):
        """Normalize report values to floats; non-numeric values become 0."""
        if value is None or value == '':
            return 0.0
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(' ', '')
            if not cleaned:
                return 0.0
            try:
                if ',' in cleaned and '.' in cleaned:
                    if cleaned.rfind(',') > cleaned.rfind('.'):
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                    else:
                        cleaned = cleaned.replace(',', '')
                elif ',' in cleaned:
                    parts = cleaned.split(',')
                    if all(len(p) == 3 for p in parts[1:]):
                        cleaned = ''.join(parts)
                    else:
                        cleaned = cleaned.replace(',', '.')
                elif '.' in cleaned:
                    parts = cleaned.split('.')
                    if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                        cleaned = ''.join(parts)
                return float(cleaned)
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    def _report_get_cache(self):
        """Build cached totals for report rendering."""
        self.ensure_one()
        code_totals = defaultdict(float)
        name_totals = defaultdict(float)
        for line in self.line_ids:
            if line.code:
                code_totals[line.code.strip().upper()] += line.total or 0.0
            if line.name:
                name_totals[line.name.strip().upper()] += line.total or 0.0

        computed_totals = defaultdict(float)
        raw_computed = self.formula_computed_values or ''
        if raw_computed:
            try:
                computed_values = json.loads(raw_computed)
                if isinstance(computed_values, dict):
                    for key, value in computed_values.items():
                        computed_totals[str(key).strip().upper()] += self._report_to_number(value)
            except Exception:
                pass

        input_totals = defaultdict(float)
        raw_inputs = self.formula_input_values or ''
        if raw_inputs:
            try:
                input_values = json.loads(raw_inputs)
                if isinstance(input_values, dict):
                    for key, value in input_values.items():
                        input_totals[str(key).strip().upper()] += self._report_to_number(value)
            except Exception:
                pass

        work_totals = defaultdict(float)
        for wd in self.worked_days_line_ids:
            key = (wd.code or '').strip().upper()
            if not key:
                continue
            work_totals[key] += wd.number_of_days if wd.number_of_days else (wd.number_of_hours or 0.0)

        return {
            'code': code_totals,
            'name': name_totals,
            'computed': computed_totals,
            'input': input_totals,
            'work': work_totals,
        }

    def _report_get_value_for_key(self, key):
        """Return best available value for a key from lines, computed, or inputs."""
        self.ensure_one()
        cache = self._report_get_cache()
        k = (key or '').strip().upper()
        if not k:
            return 0.0
        if k in cache['code']:
            return cache['code'][k]
        if k in cache['name']:
            return cache['name'][k]
        if k in cache['computed']:
            return cache['computed'][k]
        if k in cache['input']:
            return cache['input'][k]
        return 0.0

    def _report_get_line_total_by_keys(self, *keys):
        """Return first matching total by code or name."""
        self.ensure_one()
        for key in keys or []:
            value = self._report_get_value_for_key(key)
            if value:
                return value
        return 0.0

    def _report_get_line_total_sum(self, *keys):
        """Sum totals for the given codes or names."""
        self.ensure_one()
        total = 0.0
        for key in keys or []:
            total += self._report_get_value_for_key(key)
        return total

    def _report_get_work_value(self, *keys):
        """Return first matching worked days/hours value."""
        self.ensure_one()
        cache = self._report_get_cache()
        for key in keys or []:
            k = (key or '').strip().upper()
            if not k:
                continue
            if k in cache['work']:
                return cache['work'][k]
        return 0.0

    def _report_fmt_amount(self, value):
        """Format amounts with thousand separators and no decimals."""
        try:
            return "{:,.0f}".format(value or 0)
        except Exception:
            return "0"

    def _report_fmt_percent(self, value):
        """Format percent values, supporting ratios (0-1)."""
        try:
            val = value or 0
            if val <= 1:
                val *= 100
            return "{:,.0f}%".format(val)
        except Exception:
            return "0%"

    def _get_report_name(self):
        """Determine which report template to use based on payroll structure"""
        self.ensure_one()
        
        if self.struct_id and self.struct_id.name == 'Indonesia Salary Structure':
            return 'pb_hr_payroll_indonesia.report_payslip_indonesia'
        if self.struct_id and self.struct_id.name and 'vietnam' in self.struct_id.name.lower():
            return 'pb_hr_payroll_indonesia.report_payslip_vietnam'
        # Use default template for all other structures
        return 'om_hr_payroll.report_payslip'
    
    def action_print_payslip(self):
        """Override print action to use country-specific template"""
        self.ensure_one()
        
        report_name = self._get_report_name()
        
        # Debug logging
        _logger.info(f"Printing payslip for {self.employee_id.name}, Structure: {self.struct_id.name}, Using template: {report_name}")
        
        return {
            'type': 'ir.actions.report',
            'report_name': report_name,
            'report_type': 'qweb-pdf',
            'data': {},
            'context': self.env.context,
        }
    
    @api.model
    def get_payslip_report_action(self, payslip_ids):
        """Get the appropriate report action for given payslips"""
        payslips = self.browse(payslip_ids)
        
        # Check if all payslips use the same structure
        structures = payslips.mapped('struct_id.name')
        
        if len(set(structures)) > 1:
            raise UserError(_('Cannot print payslips with different structures together. Please select payslips with the same structure.'))
        
        # Determine report based on structure
        if 'Indonesia Salary Structure' in structures:
            report_ref = 'pb_hr_payroll_indonesia.action_report_payslip_indonesia'
        elif any(s and 'vietnam' in s.lower() for s in structures):
            report_ref = 'pb_hr_payroll_indonesia.action_report_payslip_vietnam'
        else:
            report_ref = 'om_hr_payroll.action_report_payslip'
        
        return self.env.ref(report_ref).report_action(payslips)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'
    
    def action_print_payslips(self):
        """Override to use country-specific templates"""
        payslips = self.slip_ids.filtered(lambda slip: slip.state in ['done', 'level1', 'level2'])
        
        if not payslips:
            raise UserError(_('No confirmed payslips found to print.'))
        
        # Group payslips by structure
        structure_groups = {}
        for payslip in payslips:
            struct_name = payslip.struct_id.name if payslip.struct_id else 'Unknown'
            if struct_name not in structure_groups:
                structure_groups[struct_name] = self.env['hr.payslip']
            structure_groups[struct_name] |= payslip
        
        # If only one structure, print directly
        if len(structure_groups) == 1:
            struct_name, group_payslips = list(structure_groups.items())[0]
            return group_payslips.get_payslip_report_action(group_payslips.ids)
        
        # Multiple structures - show selection wizard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Payslip Structure to Print',
            'res_model': 'payslip.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payslip_run_id': self.id,
                'structure_groups': {k: v.ids for k, v in structure_groups.items()}
            }
        }


class PayslipPrintWizard(models.TransientModel):
    _name = 'payslip.print.wizard'
    _description = 'Payslip Print Structure Selector'
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Run', required=True)
    structure_name = fields.Selection([], string='Payroll Structure', required=True)
    
    @api.model
    def default_get(self, fields_list):
        """Populate structure options based on payslips in the run"""
        res = super().default_get(fields_list)
        
        if 'structure_name' in fields_list and self.env.context.get('structure_groups'):
            structure_groups = self.env.context['structure_groups']
            options = [(name, f"{name} ({len(ids)} payslips)") for name, ids in structure_groups.items()]
            
            # Update field selection dynamically
            self._fields['structure_name'].selection = options
            
        return res
    
    def action_print_selected_structure(self):
        """Print payslips for selected structure"""
        structure_groups = self.env.context.get('structure_groups', {})
        payslip_ids = structure_groups.get(self.structure_name, [])
        
        if not payslip_ids:
            raise UserError(_('No payslips found for selected structure.'))
        
        payslips = self.env['hr.payslip'].browse(payslip_ids)
        return payslips.get_payslip_report_action(payslip_ids)
