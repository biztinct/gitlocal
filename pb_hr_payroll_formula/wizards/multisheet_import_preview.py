# -*- coding: utf-8 -*-
# Import Confidence (Feature 3) — a MIXIN over the multi-sheet import wizard.
# T3.1 is scaffold only: new fields + the preview-line model + security. The
# resolution-capture logic (S2), confidence scoring and fix actions land in
# T3.2–T3.5. Everything lives here so the 3,814-line base wizard is never grown.

from odoo import fields, models


class MultisheetImportPreview(models.TransientModel):
    _inherit = 'hr.formula.multisheet.import.wizard'

    # Side-by-side original→resolved preview built after the resolution step.
    preview_line_ids = fields.One2many(
        'hr.formula.import.preview.line', 'wizard_id',
        string='Resolution Preview')
    # Raw JSON kept for the client gauge / AI review (populated in T3.2/T3.3).
    resolution_preview_json = fields.Text(string='Resolution Preview (JSON)')
    confidence_score = fields.Float(string='Confidence', readonly=True)
    confidence_breakdown_json = fields.Text(string='Confidence Breakdown', readonly=True)


class HrFormulaImportPreviewLine(models.TransientModel):
    _name = 'hr.formula.import.preview.line'
    _description = 'Import resolution preview line (original vs resolved formula)'
    _order = 'sheet_name, component_code'

    wizard_id = fields.Many2one(
        'hr.formula.multisheet.import.wizard',
        string='Wizard', required=True, ondelete='cascade', index=True)

    sheet_name = fields.Char(string='Sheet')
    component_code = fields.Char(string='Component Code')
    component_name = fields.Char(string='Component Name')

    original_excel_formula = fields.Text(string='Original Formula')
    resolved_formula = fields.Text(string='Resolved Formula')

    status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Warning'),
        ('broken', 'Broken'),
    ], string='Status', default='ok')

    # Why a line is not OK. Empty for OK lines.
    issue_type = fields.Selection([
        ('unresolved_xref', 'Unresolved cross-sheet reference'),
        ('unknown_column', 'Unknown column'),
        ('becomes_zero', 'Reference became 0'),
        ('circular', 'Circular reference'),
        ('primary_key_miss', 'Primary key not matched'),
    ], string='Issue Type')
    issue_detail = fields.Text(string='Issue Detail')

    # The remediation the user chose for a problem line (applied in T3.5).
    fix_action = fields.Selection([
        ('map_component', 'Map to component'),
        ('convert_to_input', 'Convert to input'),
        ('acknowledge_zero', 'Acknowledge zero'),
        ('skip', 'Skip this component'),
    ], string='Fix Action')
    fix_target_rule_code = fields.Char(string='Fix Target Component Code')
