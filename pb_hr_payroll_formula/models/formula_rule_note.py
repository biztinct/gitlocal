# -*- coding: utf-8 -*-
"""F15 — Comments & annotations.

A lightweight per-component note thread. A note flagged as a *review note*
surfaces in the Problems rail (F15) until it is resolved; resolving clears it
from the rail but keeps it in the component's history (nothing is deleted).
This is the pragmatic cockpit-native 80% — full mail.thread chatter is deferred
(the OWL client action renders these notes in its own side panel).
"""
from odoo import api, fields, models


class HrFormulaRuleNote(models.Model):
    _name = 'hr.formula.rule.note'
    _description = 'Formula Component Note'
    _order = 'create_date desc, id desc'

    rule_id = fields.Many2one('hr.formula.rule', required=True,
                              ondelete='cascade', index=True)
    config_id = fields.Many2one('hr.formula.config', related='rule_id.config_id',
                                store=True, index=True)
    body = fields.Text(required=True)
    author_id = fields.Many2one('res.users', default=lambda s: s.env.user,
                                readonly=True, index=True)
    # a review note is an actionable "please fix" that shows in the Problems rail
    is_review = fields.Boolean(string='Review note', default=False, index=True)
    resolved = fields.Boolean(default=False, index=True)
    resolved_by_id = fields.Many2one('res.users', readonly=True)
    resolved_date = fields.Datetime(readonly=True)

    def action_resolve(self):
        self.write({'resolved': True,
                    'resolved_by_id': self.env.user.id,
                    'resolved_date': fields.Datetime.now()})

    def action_reopen(self):
        self.write({'resolved': False, 'resolved_by_id': False, 'resolved_date': False})
