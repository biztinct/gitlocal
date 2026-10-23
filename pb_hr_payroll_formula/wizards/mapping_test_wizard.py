# -*- coding: utf-8 -*-
# "Test against employee" dialog (T4.5) — runs every active mapping for a
# connector against one employee's stored payload via test_mappings_batch and
# shows raw → transformed values, with explicit errors for broken paths.

from odoo import api, fields, models


class HrIntegrationMappingTestWizard(models.TransientModel):
    _name = 'hr.integration.mapping.test.wizard'
    _description = 'Field Mapping Test'

    connector_id = fields.Many2one(
        'hr.integration.connector', string='Connector', required=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee',
        help="Test the mappings against this employee's most recent stored payload.")
    line_ids = fields.One2many(
        'hr.integration.mapping.test.line', 'wizard_id', string='Results')
    error_count = fields.Integer(compute='_compute_error_count')

    @api.depends('line_ids.error')
    def _compute_error_count(self):
        for w in self:
            w.error_count = len(w.line_ids.filtered('error'))

    def action_run(self):
        self.ensure_one()
        FM = self.env['hr.integration.field.mapping']
        mappings = FM.search([('connector_id', '=', self.connector_id.id), ('active', '=', True)])
        results = FM.test_mappings_batch(mappings.ids, self.employee_id.id or False)
        self.line_ids.unlink()
        self.env['hr.integration.mapping.test.line'].create([{
            'wizard_id': self.id,
            'source_field': r['source_field'],
            'target': r['target'],
            'raw_value': '' if r['raw'] is None else str(r['raw']),
            'transformed_value': '' if r['transformed'] is None else str(r['transformed']),
            'error': r['error'] or False,
        } for r in results])
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }


class HrIntegrationMappingTestLine(models.TransientModel):
    _name = 'hr.integration.mapping.test.line'
    _description = 'Field Mapping Test Line'

    wizard_id = fields.Many2one(
        'hr.integration.mapping.test.wizard', ondelete='cascade', required=True)
    source_field = fields.Char(string='Source Field')
    target = fields.Char(string='Target')
    raw_value = fields.Char(string='Raw')
    transformed_value = fields.Char(string='Transformed')
    error = fields.Char(string='Error')
