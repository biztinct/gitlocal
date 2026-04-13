# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import re
import logging

_logger = logging.getLogger(__name__)

# Auto-detection heuristics for WFP categories
_CODE_PATTERNS = {
    'base_salary': [
        r'^BASIC$', r'^BASE$', r'^WAGE$', r'^BASE.?SALARY$',
        r'^BASESALARY$', r'^BASEWAGE$',
    ],
    'gross': [
        r'^GROSS$', r'^GROSS.?PAY$', r'^TOTAL.?EARNINGS$',
        r'^GROSSPAY$', r'^TOTALGROSS$',
    ],
    'net': [
        r'^NET$', r'^NET.?PAY$', r'^NETPAY$', r'^TAKE.?HOME$',
        r'^NETSALARY$',
    ],
    'employer_cost': [
        r'_COMP$', r'_ER$', r'^BPJS.*COMP', r'^CPF.?ER',
        r'^EPF.?ER', r'^PF.?COMP', r'^SI.?COMP', r'^HI.?COMP',
        r'^UI.?COMP', r'^SOCSO.?COMP', r'^EIS.?ER', r'^SDL.?ER',
        r'^SSF.?ER', r'^NSSF.?COMP', r'^TU.?COMP',
        r'EMPLOYER', r'^BPJS_JKK$', r'^BPJS_JKM$',
    ],
    'deduction': [
        r'^PIT$', r'^TAX$', r'^INCOME.?TAX', r'^SI.?EE', r'^HI.?EE',
        r'^UI.?EE', r'^TU.?EE', r'^BPJS.*EE', r'^CPF.?EE',
        r'^EPF.?EE', r'^PF.?EE', r'^ESI.?EE', r'^SSF.?EE',
        r'^SOCSO.?EE', r'^EIS.?EE', r'^NSSF.?EE',
    ],
    'allowance': [
        r'^HRA$', r'^DA$', r'^TA$', r'^MA$', r'^MEAL',
        r'^TRANSPORT', r'^TRAVEL', r'^FOOD', r'^MEDICAL',
        r'^HOUSING', r'^PHONE', r'^OTHER.?ALW',
    ],
    'bonus': [
        r'^BONUS', r'^13TH', r'^INCENTIVE', r'^VARIABLE',
        r'^COMMISSION',
    ],
}

_COMPONENT_TYPE_MAP = {
    'employer': 'employer_cost',
    'employer cost': 'employer_cost',
    'employer contribution': 'employer_cost',
    'company cost': 'employer_cost',
    'deduction': 'deduction',
    'deductions': 'deduction',
    'allowance': 'allowance',
    'allowances': 'allowance',
    'earning': 'allowance',
    'earnings': 'allowance',
    'benefit': 'allowance',
    'benefits': 'allowance',
}

_CATEGORY_CODE_MAP = {
    'BASIC': 'base_salary',
    'ALW': 'allowance',
    'DED': 'deduction',
    'GROSS': 'gross',
    'NET': 'net',
}


class WfpTaggingWizard(models.TransientModel):
    """Wizard to auto-tag formula rules with WFP categories."""
    _name = 'wfp.tagging.wizard'
    _description = 'WFP Component Tagging Wizard'

    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        required=True,
        domain="[('state', '=', 'active')]",
    )
    line_ids = fields.One2many(
        'wfp.tagging.wizard.line',
        'wizard_id',
        string='Components',
    )

    def action_load_rules(self):
        """Load formula rules and auto-detect WFP categories."""
        self.ensure_one()
        self.line_ids.unlink()

        rules = self.formula_config_id.rule_ids.sorted(
            key=lambda r: r.sequence
        )
        line_vals = []
        for rule in rules:
            detected = self._detect_category(rule)
            line_vals.append({
                'wizard_id': self.id,
                'formula_rule_id': rule.id,
                'rule_code': rule.code,
                'rule_name': rule.name,
                'column_letter': rule.column_letter,
                'column_type': rule.column_type,
                'component_type': rule.component_type or '',
                'category_code': (
                    rule.category_id.code if rule.category_id else ''
                ),
                'current_wfp_category': rule.wfp_category or '',
                'detected_wfp_category': detected,
                'wfp_category': detected or rule.wfp_category or '',
                'excel_formula': rule.excel_formula or '',
            })

        self.env['wfp.tagging.wizard.line'].create(line_vals)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wfp.tagging.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply_tags(self):
        """Save the WFP categories to formula rules."""
        self.ensure_one()
        updated = 0
        for line in self.line_ids:
            if line.wfp_category and line.formula_rule_id:
                if line.formula_rule_id.wfp_category != line.wfp_category:
                    line.formula_rule_id.wfp_category = line.wfp_category
                    updated += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('WFP Categories Applied'),
                'message': _(
                    '%d formula rules tagged for workforce planning.'
                ) % updated,
                'type': 'success',
                'sticky': False,
            }
        }

    def _detect_category(self, rule):
        """Auto-detect WFP category from rule metadata.

        Priority:
        1. Existing wfp_category (if already tagged)
        2. category_id.code mapping
        3. component_type string matching
        4. Code pattern matching
        """
        # Already tagged?
        if rule.wfp_category:
            return rule.wfp_category

        code = (rule.code or '').upper()

        # Category ID mapping
        if rule.category_id:
            cat_code = rule.category_id.code
            if cat_code in _CATEGORY_CODE_MAP:
                return _CATEGORY_CODE_MAP[cat_code]

        # Component type string matching (from Excel merged headers)
        comp_type = (rule.component_type or '').lower().strip()
        if comp_type in _COMPONENT_TYPE_MAP:
            return _COMPONENT_TYPE_MAP[comp_type]

        # Code pattern matching
        for wfp_cat, patterns in _CODE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    return wfp_cat

        # Constants that are rates (e.g., 0.175 for 17.5%) are likely info
        if rule.column_type == 'constant':
            return 'exclude'

        return ''


class WfpTaggingWizardLine(models.TransientModel):
    """Individual line in the tagging wizard."""
    _name = 'wfp.tagging.wizard.line'
    _description = 'WFP Tagging Wizard Line'
    _order = 'column_letter'

    wizard_id = fields.Many2one(
        'wfp.tagging.wizard',
        string='Wizard',
        ondelete='cascade',
    )
    formula_rule_id = fields.Many2one(
        'hr.formula.rule',
        string='Formula Rule',
    )
    column_letter = fields.Char(string='Col')
    rule_code = fields.Char(string='Code')
    rule_name = fields.Char(string='Name')
    column_type = fields.Char(string='Type')
    component_type = fields.Char(string='Component Type')
    category_code = fields.Char(string='Category')
    excel_formula = fields.Char(string='Formula')
    current_wfp_category = fields.Char(string='Current Tag')
    detected_wfp_category = fields.Char(string='Auto-Detected')

    wfp_category = fields.Selection([
        ('base_salary', 'Base Salary'),
        ('allowance', 'Allowance'),
        ('deduction', 'Employee Deduction'),
        ('employer_cost', 'Employer Cost / Contribution'),
        ('gross', 'Gross Pay'),
        ('net', 'Net Pay'),
        ('bonus', 'Bonus / Variable Pay'),
        ('info', 'Informational Only'),
        ('exclude', 'Exclude from Planning'),
    ], string='WFP Category')
