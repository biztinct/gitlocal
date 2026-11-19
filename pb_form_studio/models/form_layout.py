# -*- coding: utf-8 -*-
"""Published layouts, per-administrator drafts and the append-only audit.

A layout belongs to a HOST (one screen) and a company. Only OPEN sections are
stored; locked sections are the host's and are never written here, so a
stored layout can never put a field in a zone the screen draws itself.
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError


class PbFormLayout(models.Model):
    _name = 'pb.form.layout'
    _description = 'Form builder published layout'
    _order = 'host_key, company_id'

    host_key = fields.Char(required=True, index=True)
    model = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 ondelete='cascade')
    version = fields.Integer(default=0)
    sections = fields.Json(default=list)
    published_by = fields.Many2one('res.users', ondelete='set null')
    published_at = fields.Datetime()

    _host_company_uniq = models.Constraint(
        'UNIQUE (host_key, company_id)',
        'A screen has one published layout per company.')


class PbFormLayoutDraft(models.Model):
    _name = 'pb.form.layout.draft'
    _description = 'Form builder draft'

    host_key = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    base_version = fields.Integer(help='Layout version the draft was started from.')
    payload = fields.Json(default=dict)

    _draft_uniq = models.Constraint(
        'UNIQUE (host_key, company_id, user_id)',
        'One draft per person per screen.')


class PbFormAudit(models.Model):
    """Append-only, like `biz.audit.entry` — but kept here because that
    model's retention clean-up would delete the values export attached to a
    field deletion, and that export is the only copy of the values left."""
    _name = 'pb.form.audit'
    _description = 'Form builder history'
    _order = 'stamp desc, id desc'
    _rec_name = 'summary'

    stamp = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    user_id = fields.Many2one('res.users', default=lambda s: s.env.uid,
                              ondelete='set null')
    company_id = fields.Many2one('res.company', ondelete='set null')
    host_key = fields.Char(index=True)
    model = fields.Char(index=True)
    action = fields.Selection([
        ('publish', 'Published a layout'),
        ('create_field', 'Added a field'),
        ('update_field', 'Changed a field'),
        ('delete_field', 'Deleted a field'),
        ('portal_change', 'Changed on My Payobook'),
    ], required=True)
    res_id = fields.Integer(string='Record', help='The record a My Payobook change was saved on.')
    field_name = fields.Char()
    summary = fields.Char()
    detail = fields.Json()
    attachment_id = fields.Many2one('ir.attachment', ondelete='set null',
                                    string='Values saved before deletion')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError(self.env._('Only the administrator can change forms.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(self.env._('The Form builder history cannot be changed.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(self.env._('The Form builder history cannot be changed.'))
        return super().unlink()
