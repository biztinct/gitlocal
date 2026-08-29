# -*- coding: utf-8 -*-
"""The audit trail the Records Desk writes, and the only thing Undo trusts.

Two models, deliberately stored rather than derived:

  * `pb.records.apply` — one row per Apply. Who, when, which scheme, the note
    they typed, and the two counts the toast quotes back at them.
  * `pb.records.change` — one row per VALUE actually written, carrying the
    before and the after as JSON.

Undo reads `pb.records.change`, not the desk's screen state, and it compares the
record's CURRENT value against `new_json` before writing `old_json` back. That
comparison is the whole reason the after-value is stored: a value somebody else
changed in the meantime is reported as skipped rather than silently clobbered,
and an audit trail that cannot say "this one is no longer mine to undo" is an
audit trail that quietly loses other people's work.

An undo is itself an apply (`source='undo'`), so undoing is as auditable as
applying. Nothing here is ever deleted by the desk.
"""
from odoo import api, fields, models


class PbRecordsApply(models.Model):
    _name = 'pb.records.apply'
    _description = 'Records Desk Apply'
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, readonly=True)
    user_id = fields.Many2one(
        'res.users', string='Changed By', readonly=True,
        default=lambda self: self.env.user)
    date = fields.Datetime(
        string='Changed At', readonly=True, default=fields.Datetime.now)
    note = fields.Text(string='Why')
    source = fields.Selection([
        ('desk', 'Records Desk'),
        ('undo', 'Undo'),
    ], string='Source', default='desk', required=True, readonly=True)
    # Setup metadata, not payroll history — a scheme that is removed must not be
    # held hostage by the audit rows that mention it (the mapping model's own
    # `ondelete='cascade'` reasoning, one step softer because losing the whole
    # audit row would be worse than losing the scheme reference).
    config_id = fields.Many2one(
        'hr.formula.config', string='Pay Scheme', ondelete='set null',
        readonly=True)
    count_people = fields.Integer(string='People', readonly=True)
    count_values = fields.Integer(string='Values', readonly=True)
    undone = fields.Boolean(string='Undone', readonly=True)
    undone_date = fields.Datetime(string='Undone At', readonly=True)
    undone_by_id = fields.Many2one(
        'res.users', string='Undone By', readonly=True)
    change_ids = fields.One2many(
        'pb.records.change', 'apply_id', string='Values')

    @api.model
    def _next_name(self):
        return self.env['ir.sequence'].next_by_code('pb.records.apply') \
            or fields.Datetime.to_string(fields.Datetime.now())


class PbRecordsChange(models.Model):
    _name = 'pb.records.change'
    _description = 'Records Desk Value Change'
    _order = 'id asc'

    apply_id = fields.Many2one(
        'pb.records.apply', string='Apply', required=True, ondelete='cascade',
        index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', ondelete='set null', index=True)
    employee_name = fields.Char(string='Person', readonly=True)
    # The technical model/id the value actually landed on. A contract field's
    # `res_id` is the CONTRACT, not the employee, which is what makes Undo able
    # to write back to the same row even after a newer contract exists.
    model = fields.Char(string='Record Type', readonly=True)
    res_id = fields.Integer(string='Record', readonly=True)
    # The desk's own card id: `f:<model>:<field>`, `b:<role>` or `c:<CODE>`.
    field_key = fields.Char(string='Field Key', required=True, readonly=True)
    field_label = fields.Char(string='Field', readonly=True)
    old_json = fields.Text(string='Before', readonly=True)
    new_json = fields.Text(string='After', readonly=True)
    old_label = fields.Char(string='Before (shown)', readonly=True)
    new_label = fields.Char(string='After (shown)', readonly=True)
