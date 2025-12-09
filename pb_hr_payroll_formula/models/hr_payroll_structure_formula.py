# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrPayrollStructureFormula(models.Model):
    """
    Extends hr.payroll.structure to support formula-based configuration.
    """
    _inherit = 'hr.payroll.structure'

    # ==========================================
    # FORMULA CONFIGURATION LINK
    # ==========================================
    formula_config_ids = fields.One2many(
        'hr.formula.config',
        'structure_id',
        string='Formula Configurations'
    )

    formula_config_count = fields.Integer(
        string='Formula Configs',
        compute='_compute_formula_config_count'
    )

    active_formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Active Formula Config',
        compute='_compute_active_formula_config',
        help="The currently active formula configuration for this structure"
    )

    use_formula_computation = fields.Boolean(
        string='Use Formula Computation',
        default=False,
        help="Use formula-based computation instead of standard salary rules"
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('formula_config_ids')
    def _compute_formula_config_count(self):
        for record in self:
            record.formula_config_count = len(record.formula_config_ids)

    @api.depends('formula_config_ids.state')
    def _compute_active_formula_config(self):
        for record in self:
            active_config = record.formula_config_ids.filtered(
                lambda c: c.state == 'active'
            )[:1]
            record.active_formula_config_id = active_config

    # ==========================================
    # ACTIONS
    # ==========================================
    def action_view_formula_configs(self):
        """View formula configurations for this structure"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Formula Configurations'),
            'res_model': 'hr.formula.config',
            'view_mode': 'tree,form',
            'domain': [('structure_id', '=', self.id)],
            'context': {
                'default_structure_id': self.id,
                'default_name': _('%s Formula Config') % self.name,
                'default_code': f'{self.code}_FORMULA',
            },
        }

    def action_create_formula_config(self):
        """Create a new formula configuration from this structure"""
        self.ensure_one()

        # Create new config
        config = self.env['hr.formula.config'].create({
            'name': _('%s Formula Configuration') % self.name,
            'code': f'{self.code}_FORMULA',
            'structure_id': self.id,
            'company_id': self.company_id.id,
            'state': 'draft',
        })

        # Import rules from structure
        for salary_rule in self.rule_ids:
            self.env['hr.formula.rule'].create({
                'config_id': config.id,
                'salary_rule_id': salary_rule.id,
                'name': salary_rule.name,
                'code': salary_rule.code,
                'sequence': salary_rule.sequence,
                'category_id': salary_rule.category_id.id,
                'column_type': 'formula',
                'appears_on_payslip': salary_rule.appears_on_payslip,
            })

        return {
            'type': 'ir.actions.act_window',
            'name': config.name,
            'res_model': 'hr.formula.config',
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_formula_grid(self):
        """Open the Excel-like formula grid for active config"""
        self.ensure_one()
        if not self.active_formula_config_id:
            raise UserError(_(
                "No active formula configuration found. "
                "Please create and activate a formula configuration first."
            ))

        return self.active_formula_config_id.action_open_excel_grid()
