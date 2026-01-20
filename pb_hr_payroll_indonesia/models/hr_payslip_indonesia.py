# -*- coding: utf-8 -*-

from collections import defaultdict
import json
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import formatLang
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

    @staticmethod
    def _report_normalize_key(value):
        return ''.join(ch for ch in (value or '').upper() if ch.isalnum())

    def _report_get_cache(self):
        """Build cached totals for report rendering."""
        self.ensure_one()
        code_totals = defaultdict(float)
        name_totals = defaultdict(float)
        code_norm = defaultdict(float)
        name_norm = defaultdict(float)
        for line in self.line_ids:
            if line.code:
                code_key = line.code.strip().upper()
                code_totals[code_key] += line.total or 0.0
                normalized = self._report_normalize_key(code_key)
                if normalized:
                    code_norm[normalized] += line.total or 0.0
            if line.name:
                name_key = line.name.strip().upper()
                name_totals[name_key] += line.total or 0.0
                normalized = self._report_normalize_key(name_key)
                if normalized:
                    name_norm[normalized] += line.total or 0.0

        computed_totals = defaultdict(float)
        computed_norm = defaultdict(float)
        raw_computed = self.formula_computed_values or ''
        if raw_computed:
            try:
                computed_values = json.loads(raw_computed)
                if isinstance(computed_values, dict):
                    for key, value in computed_values.items():
                        key_name = str(key).strip().upper()
                        amount = self._report_to_number(value)
                        computed_totals[key_name] += amount
                        normalized = self._report_normalize_key(key_name)
                        if normalized:
                            computed_norm[normalized] += amount
            except Exception:
                pass

        input_totals = defaultdict(float)
        input_norm = defaultdict(float)
        input_raw = {}
        input_raw_norm = {}
        raw_inputs = self.formula_input_values or ''
        if raw_inputs:
            try:
                input_values = json.loads(raw_inputs)
                if isinstance(input_values, dict):
                    for key, value in input_values.items():
                        key_name = str(key).strip().upper()
                        amount = self._report_to_number(value)
                        input_totals[key_name] += amount
                        normalized = self._report_normalize_key(key_name)
                        if normalized:
                            input_norm[normalized] += amount
                        if value is None:
                            continue
                        if isinstance(value, float) and value.is_integer():
                            raw_value = str(int(value))
                        elif isinstance(value, (int, bool)):
                            raw_value = str(int(value)) if isinstance(value, bool) else str(value)
                        else:
                            raw_value = str(value).strip()
                        if raw_value:
                            input_raw[key_name] = raw_value
                            if normalized and normalized not in input_raw_norm:
                                input_raw_norm[normalized] = raw_value
            except Exception:
                pass

        work_totals = defaultdict(float)
        work_norm = defaultdict(float)
        for wd in self.worked_days_line_ids:
            key = (wd.code or '').strip().upper()
            if not key:
                continue
            work_totals[key] += wd.number_of_days if wd.number_of_days else (wd.number_of_hours or 0.0)
            normalized = self._report_normalize_key(key)
            if normalized:
                work_norm[normalized] += wd.number_of_days if wd.number_of_days else (wd.number_of_hours or 0.0)

        return {
            'code': code_totals,
            'name': name_totals,
            'code_norm': code_norm,
            'name_norm': name_norm,
            'computed': computed_totals,
            'computed_norm': computed_norm,
            'input': input_totals,
            'input_norm': input_norm,
            'input_raw': input_raw,
            'input_raw_norm': input_raw_norm,
            'work': work_totals,
            'work_norm': work_norm,
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
        normalized = self._report_normalize_key(k)
        if normalized:
            if normalized in cache['code_norm']:
                return cache['code_norm'][normalized]
            if normalized in cache['name_norm']:
                return cache['name_norm'][normalized]
            if normalized in cache['computed_norm']:
                return cache['computed_norm'][normalized]
            if normalized in cache['input_norm']:
                return cache['input_norm'][normalized]
        return 0.0

    def _report_get_raw_value(self, *keys):
        """Return raw (string) input value for the first matching key."""
        self.ensure_one()
        cache = self._report_get_cache()
        for key in keys or []:
            if not key:
                continue
            key_name = str(key).strip().upper()
            if key_name in cache['input_raw']:
                return cache['input_raw'][key_name]
            normalized = self._report_normalize_key(key_name)
            if normalized and normalized in cache['input_raw_norm']:
                return cache['input_raw_norm'][normalized]
        return ''

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
            normalized = self._report_normalize_key(k)
            if normalized and normalized in cache['work_norm']:
                return cache['work_norm'][normalized]
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

    @staticmethod
    def _report_is_numeric_string(value):
        if not isinstance(value, str):
            return False
        cleaned = value.strip()
        if not cleaned:
            return False
        return bool(re.fullmatch(r'[-+]?[\d\s,\.]+%?', cleaned))

    @staticmethod
    def _report_is_percentage_name(name):
        if not name:
            return False
        cleaned = name.strip().lower()
        if '%' in cleaned:
            return True
        if 'percent' in cleaned:
            return True
        return cleaned.startswith('percentage') or cleaned.endswith('percentage')

    def _report_should_hide_identifier_value(self, value):
        if value in (None, '', False):
            return True
        if isinstance(value, (int, float)):
            return abs(value) < 1e-9
        if isinstance(value, bool):
            return not value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return True
            if self._report_is_numeric_string(stripped):
                return abs(self._report_to_number(stripped.replace('%', ''))) < 1e-9
        return False

    def _report_format_identifier_value(self, value, name=None):
        if value is None:
            return ''
        if isinstance(value, bool):
            value = float(value)
        if isinstance(value, (int, float)):
            if self._report_is_percentage_name(name):
                return self._report_fmt_percent(value)
            return formatLang(self.env, value or 0.0, currency_obj=self.currency_id)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return ''
            if '%' in stripped:
                return stripped
            if self._report_is_numeric_string(stripped):
                num = self._report_to_number(stripped)
                if self._report_is_percentage_name(name):
                    return self._report_fmt_percent(num)
                return formatLang(self.env, num or 0.0, currency_obj=self.currency_id)
            return stripped
        return str(value)

    @staticmethod
    def _report_format_identifier_value_raw(value):
        if value is None:
            return ''
        if isinstance(value, bool):
            return '1' if value else '0'
        if isinstance(value, (int, float)):
            if isinstance(value, float) and abs(value - int(value)) < 1e-9:
                return str(int(value))
            raw = ('%f' % value).rstrip('0').rstrip('.')
            return raw or '0'
        if isinstance(value, str):
            return value.strip()
        return str(value)

    def _report_get_identifier_sections(self):
        """Build dynamic payslip sections from identifier payload."""
        self.ensure_one()
        if 'payslip_identifier_payload' not in self._fields:
            return None
        if 'hr.payslip.config' not in self.env:
            return None
        raw_payload = self.payslip_identifier_payload or ''
        if not raw_payload:
            return None
        try:
            payload = json.loads(raw_payload)
        except Exception:
            return None
        if not isinstance(payload, list):
            return None

        grouped = {}
        identifiers = set()
        for item in payload:
            identifier = (item or {}).get('identifier')
            if not identifier:
                continue
            identifiers.add(identifier)
            grouped.setdefault(identifier, []).append(item)

        if not grouped:
            return None

        configs = self.env['hr.payslip.config'].search(
            [('identifier', 'in', list(identifiers))],
            order='sequence, identifier'
        )
        config_map = {config.identifier: config for config in configs}

        def _identifier_sort_key(identifier):
            config = config_map.get(identifier)
            if config:
                return (config.sequence or 0, identifier)
            return (9999, identifier)

        sections = []
        for identifier in sorted(grouped.keys(), key=_identifier_sort_key):
            items = grouped.get(identifier, [])
            lines = []
            for item in sorted(items, key=lambda x: (x.get('sequence') or 0, x.get('name') or '')):
                value = item.get('value')
                if self._report_should_hide_identifier_value(value):
                    continue
                if identifier == 'H':
                    display_value = self._report_format_identifier_value_raw(value)
                else:
                    display_value = self._report_format_identifier_value(value, item.get('name'))
                if display_value == '':
                    continue
                lines.append({
                    'name': (item.get('name') or '').strip(),
                    'value': display_value,
                })
            if not lines:
                continue
            config = config_map.get(identifier)
            title = (config.label or config.identifier) if config else identifier
            sections.append({
                'identifier': identifier,
                'title': title,
                'lines': lines,
            })

        return sections

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
