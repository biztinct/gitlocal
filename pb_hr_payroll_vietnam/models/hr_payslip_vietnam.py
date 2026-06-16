# -*- coding: utf-8 -*-

from collections import defaultdict
import json
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import formatLang
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import base64
import io
import zipfile
import logging

_logger = logging.getLogger(__name__)


class HrPayslipVietnam(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip']

    # Add currency_id field if it doesn't exist in base model
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)

    # Vietnam-specific fields
    vietnam_region = fields.Selection([
        ('region1', 'Region I (Hanoi, Ho Chi Minh City)'),
        ('region2', 'Region II (Can Tho, Da Nang, Hai Phong)'),
        ('region3', 'Region III (Bien Hoa, Vung Tau, Nha Trang)'),
        ('region4', 'Region IV (Other provinces)'),
    ], string='Vietnam Region', help='Minimum wage region in Vietnam')
    
    vietnam_tax_code = fields.Char(string='Vietnam Tax Code', help='Personal Income Tax code')
    vietnam_social_insurance_number = fields.Char(string='Social Insurance Number')
    vietnam_dependents = fields.Integer(string='Number of Dependents', default=0)
    
    # Vietnam salary components
    vietnam_basic_salary = fields.Monetary(string='Basic Salary (VND)', currency_field='currency_id')
    vietnam_allowances = fields.Monetary(string='Allowances (VND)', currency_field='currency_id')
    vietnam_overtime_amount = fields.Monetary(string='Overtime Amount (VND)', currency_field='currency_id')
    vietnam_bonus = fields.Monetary(string='Bonus/13th Month (VND)', currency_field='currency_id')
    
    # Vietnam deductions
    vietnam_personal_income_tax = fields.Monetary(string='Personal Income Tax (VND)', currency_field='currency_id')
    vietnam_social_insurance_employee = fields.Monetary(string='Social Insurance - Employee (VND)', currency_field='currency_id')
    vietnam_health_insurance_employee = fields.Monetary(string='Health Insurance - Employee (VND)', currency_field='currency_id')
    vietnam_unemployment_insurance_employee = fields.Monetary(string='Unemployment Insurance - Employee (VND)', currency_field='currency_id')
    
    # Employer contributions
    vietnam_social_insurance_employer = fields.Monetary(string='Social Insurance - Employer (VND)', currency_field='currency_id')
    vietnam_health_insurance_employer = fields.Monetary(string='Health Insurance - Employer (VND)', currency_field='currency_id')
    vietnam_unemployment_insurance_employer = fields.Monetary(string='Unemployment Insurance - Employer (VND)', currency_field='currency_id')
    vietnam_accident_insurance_employer = fields.Monetary(string='Accident Insurance - Employer (VND)', currency_field='currency_id')

    @api.model
    def _get_vietnam_minimum_wage(self, region, date_from):
        """Get minimum wage based on Vietnam region and date"""
        # Vietnam minimum wage rates (example - should be updated with current rates)
        minimum_wages = {
            'region1': 4680000,  # VND per month for Region I
            'region2': 4160000,  # VND per month for Region II  
            'region3': 3640000,  # VND per month for Region III
            'region4': 3250000,  # VND per month for Region IV
        }
        return minimum_wages.get(region, 3250000)

    @api.depends('vietnam_basic_salary', 'vietnam_allowances', 'vietnam_overtime_amount', 'vietnam_bonus')
    def _compute_vietnam_gross_salary(self):
        """Compute gross salary for Vietnam"""
        for payslip in self:
            payslip.vietnam_gross_salary = (
                payslip.vietnam_basic_salary + 
                payslip.vietnam_allowances + 
                payslip.vietnam_overtime_amount + 
                payslip.vietnam_bonus
            )

    vietnam_gross_salary = fields.Monetary(
        string='Gross Salary (VND)', 
        currency_field='currency_id',
        compute='_compute_vietnam_gross_salary',
        store=True
    )

    def action_get_employee_data_vn(self):
        """Vietnam-specific employee data import from Zoho"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Vietnam Employee Data'),
            'res_model': 'vietnam.employee.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_country': 'vietnam'}
        }

    def action_edit_spreadsheet_vn(self):
        """Vietnam-specific spreadsheet editing"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vietnam Payroll Spreadsheet'),
            'res_model': 'spreadsheet.spreadsheet',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_country': 'vietnam',
                'default_currency': 'VND'
            }
        }

    def _vietnam_calculate_personal_income_tax(self):
        """Calculate Vietnam Personal Income Tax based on progressive rates"""
        for payslip in self:
            # Taxable income = Gross - Social Insurance - Dependent deductions
            social_insurance_total = (
                payslip.vietnam_social_insurance_employee +
                payslip.vietnam_health_insurance_employee +
                payslip.vietnam_unemployment_insurance_employee
            )
            
            # Personal deduction: 11,000,000 VND + 4,400,000 VND per dependent
            personal_deduction = 11000000 + (payslip.vietnam_dependents * 4400000)
            
            taxable_income = payslip.vietnam_gross_salary - social_insurance_total - personal_deduction
            
            # Progressive tax rates for Vietnam
            tax_amount = 0
            if taxable_income <= 5000000:
                tax_amount = taxable_income * 0.05
            elif taxable_income <= 10000000:
                tax_amount = 250000 + (taxable_income - 5000000) * 0.10
            elif taxable_income <= 18000000:
                tax_amount = 750000 + (taxable_income - 10000000) * 0.15
            elif taxable_income <= 32000000:
                tax_amount = 1950000 + (taxable_income - 18000000) * 0.20
            elif taxable_income <= 52000000:
                tax_amount = 4750000 + (taxable_income - 32000000) * 0.25
            elif taxable_income <= 80000000:
                tax_amount = 9750000 + (taxable_income - 52000000) * 0.30
            else:
                tax_amount = 18150000 + (taxable_income - 80000000) * 0.35
                
            payslip.vietnam_personal_income_tax = max(0, tax_amount)

    # ── Report helper methods ──────────────────────────────────────────

    @staticmethod
    def _report_to_number(value):
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
        raw_computed = getattr(self, 'formula_computed_values', '') or ''
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
        raw_inputs = getattr(self, 'formula_input_values', '') or ''
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
            'code': code_totals, 'name': name_totals,
            'code_norm': code_norm, 'name_norm': name_norm,
            'computed': computed_totals, 'computed_norm': computed_norm,
            'input': input_totals, 'input_norm': input_norm,
            'input_raw': input_raw, 'input_raw_norm': input_raw_norm,
            'work': work_totals, 'work_norm': work_norm,
        }

    def _report_get_value_for_key(self, key):
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
        self.ensure_one()
        for key in keys or []:
            value = self._report_get_value_for_key(key)
            if value:
                return value
        return 0.0

    def _report_get_line_total_sum(self, *keys):
        self.ensure_one()
        total = 0.0
        for key in keys or []:
            total += self._report_get_value_for_key(key)
        return total

    def _report_get_work_value(self, *keys):
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
        try:
            return "{:,.0f}".format(value or 0)
        except Exception:
            return "0"

    def _report_fmt_percent(self, value):
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
        self.ensure_one()
        if self.struct_id and self.struct_id.name and 'vietnam' in self.struct_id.name.lower():
            return 'pb_hr_payroll_vietnam.report_payslip_vietnam'
        return 'om_hr_payroll.report_payslip'

    def action_print_payslip(self):
        self.ensure_one()
        report_name = self._get_report_name()
        _logger.info("Printing payslip for %s, Structure: %s, Template: %s",
                      self.employee_id.name, self.struct_id.name, report_name)
        return {
            'type': 'ir.actions.report',
            'report_name': report_name,
            'report_type': 'qweb-pdf',
            'data': {},
            'context': self.env.context,
        }

    @api.model
    def get_payslip_report_action(self, payslip_ids):
        payslips = self.browse(payslip_ids)
        structures = payslips.mapped('struct_id.name')
        if len(set(structures)) > 1:
            raise UserError(_('Cannot print payslips with different structures together. Please select payslips with the same structure.'))
        if any(s and 'vietnam' in s.lower() for s in structures):
            report_ref = 'pb_hr_payroll_vietnam.action_report_payslip_vietnam'
        else:
            report_ref = 'om_hr_payroll.action_report_payslip'
        return self.env.ref(report_ref).report_action(payslips)

    # ── End report helpers ───────────────────────────────────────────

    def _vietnam_calculate_social_insurance(self):
        """Calculate Vietnam Social Insurance contributions"""
        for payslip in self:
            # Base salary for social insurance calculation (capped)
            si_base = min(payslip.vietnam_basic_salary, 29800000)  # Max SI base salary
            
            # Employee contributions
            payslip.vietnam_social_insurance_employee = si_base * 0.08      # 8%
            payslip.vietnam_health_insurance_employee = si_base * 0.015     # 1.5%
            payslip.vietnam_unemployment_insurance_employee = si_base * 0.01 # 1%
            
            # Employer contributions  
            payslip.vietnam_social_insurance_employer = si_base * 0.175     # 17.5%
            payslip.vietnam_health_insurance_employer = si_base * 0.03      # 3%
            payslip.vietnam_unemployment_insurance_employer = si_base * 0.01 # 1%
            payslip.vietnam_accident_insurance_employer = si_base * 0.005   # 0.5%


class HrPayslipRunVietnam(models.Model):
    _inherit = 'hr.payslip.run'

    def action_print_payslips_zip(self):
        self.ensure_one()
        payslips = self.slip_ids.filtered(lambda slip: slip.state in ['done', 'level1', 'level2'])
        if not payslips:
            raise UserError(_('No confirmed payslips found to print.'))

        zip_buffer = io.BytesIO()
        failed_payslips = []

        def _safe_filename(value):
            return re.sub(r'[^A-Za-z0-9_.-]+', '_', (value or '').strip()) or 'payslip'

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for payslip in payslips:
                try:
                    report_name = payslip._get_report_name()
                    report = self.env['ir.actions.report']._get_report_from_name(report_name)
                    if not report:
                        report = self.env.ref('om_hr_payroll.action_report_payslip')
                    pdf_content, _ = report._render_qweb_pdf(report.report_name, res_ids=[payslip.id])
                except Exception as exc:
                    _logger.warning("Failed to render payslip %s: %s", payslip.id, exc)
                    failed_payslips.append(payslip)
                    continue
                if not pdf_content:
                    failed_payslips.append(payslip)
                    continue
                filename = _safe_filename(payslip.employee_id.name or payslip.name)
                filename = f"{filename}-{payslip.date_to or ''}.pdf"
                zip_file.writestr(filename, pdf_content)

        if zip_buffer.tell() == 0 or zip_buffer.getbuffer().nbytes == 0:
            employee_names = [p.employee_id.name for p in failed_payslips]
            raise UserError(_(
                "Could not generate PDF for any payslips. "
                "Please check that the payslip template is correctly configured.\n\n"
                "Affected employees: %s"
            ) % ', '.join(employee_names))

        zip_buffer.seek(0)
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name or 'payslips'}-zip",
            'type': 'binary',
            'datas': base64.b64encode(zip_buffer.read()),
            'res_model': 'hr.payslip.run',
            'res_id': self.id,
            'mimetype': 'application/zip',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_print_payslips(self):
        payslips = self.slip_ids.filtered(lambda slip: slip.state in ['done', 'level1', 'level2'])
        if not payslips:
            raise UserError(_('No confirmed payslips found to print.'))

        structure_groups = {}
        for payslip in payslips:
            struct_name = payslip.struct_id.name if payslip.struct_id else 'Unknown'
            if struct_name not in structure_groups:
                structure_groups[struct_name] = self.env['hr.payslip']
            structure_groups[struct_name] |= payslip

        if len(structure_groups) == 1:
            struct_name, group_payslips = list(structure_groups.items())[0]
            return group_payslips.get_payslip_report_action(group_payslips.ids)

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