# -*- coding: utf-8 -*-
"""W65 — Mapping templates (user-authored, reusable across configs/connectors).

A *mapping template* is a saved snapshot of a mapping board — the accepted wires
of one adapter (API field mapping or cycle carryover) — stored as CODES/PATHS,
never record ids, so it can be re-applied to a different configuration or
connector (the bureau workflow: wire one client, save, apply to the next).

This is a NEW, lean user-save surface (D-I5). It is deliberately separate from
``hr.integration.mapping.template`` — that is the VENDOR-seeded canonical table
applied by the onboarding wizard and must stay untouched.

C1 boundary: the models live here (engine, headless). All save/apply/list/delete
RPCs live in ``pb_formula_studio`` (studio facade). Company-scoping is enforced
from day one (D-I5 — do NOT repeat the W104 snippet gap where writes were not
company-scoped): a template's ``company_id`` defaults to the creating company;
an empty company means "shared", and the RPC layer rejects delete of another
company's non-shared template server-side, not just in the UI.
"""
from odoo import api, fields, models


class HrFormulaMappingTemplate(models.Model):
    _name = 'hr.formula.mapping.template'
    _description = 'Mapping Board Template (user-authored)'
    _order = 'name, id'

    name = fields.Char(required=True)
    adapter = fields.Selection([
        ('api', 'API field mapping'),
        ('cycle', 'Cycle carryover'),
    ], required=True, default='api', index=True,
        help="Which mapping surface this template was captured from. API templates "
             "carry per-wire transforms; cycle templates carry pairs only.")
    connector_type = fields.Char(
        help="Optional hint — the source connector type this API template was captured "
             "from. Purely informational; templates apply by code/path, not by connector.")
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company,
        help="Owning company. Leave empty to share the template across every company.")
    line_ids = fields.One2many(
        'hr.formula.mapping.template.line', 'template_id', string='Lines')
    line_count = fields.Integer(compute='_compute_line_count')
    note = fields.Char()
    active = fields.Boolean(default=True)

    @api.depends('line_ids')
    def _compute_line_count(self):
        for t in self:
            t.line_count = len(t.line_ids)


class HrFormulaMappingTemplateLine(models.Model):
    _name = 'hr.formula.mapping.template.line'
    _description = 'Mapping Board Template Line'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'hr.formula.mapping.template', required=True, ondelete='cascade', index=True)
    # CODES / PATHS, never ids — a template must apply across configs (D-I5).
    source_key = fields.Char(
        required=True,
        help="API source-field path (api templates) or mid-cycle component CODE (cycle).")
    target_code = fields.Char(
        required=True,
        help="Target input component CODE (api) or end-cycle component CODE (cycle).")
    # transforms are copied for API lines only (cycle carries no transform — D-I1)
    transformation_type = fields.Selection([
        ('direct', 'Direct Copy'),
        ('multiply', 'Multiply by Factor'),
        ('divide', 'Divide by Factor'),
        ('add', 'Add Value'),
        ('subtract', 'Subtract Value'),
        ('round', 'Round to Decimals'),
        ('abs', 'Absolute Value'),
        ('default_if_empty', 'Use Default if Empty'),
        ('python', 'Python Expression'),
    ], default='direct')
    transformation_value = fields.Float(default=0.0)
    transformation_decimals = fields.Integer(default=2)
    sequence = fields.Integer(default=10)
