# -*- coding: utf-8 -*-
"""What the Form builder knows about one field beyond the field itself.

One row per custom field the engine made (and, later, per standard field a
host lets the administrator relabel). The ORM-facing visibility lives on the
field row (`ir.model.fields.pbfs_groups`, see ir_model_fields.py); `vis` here
is the administrator's choice in screen words, and the two are written
together by the facade only.
"""
from odoo import fields, models

VIS = [('all', 'Everyone, including the employee'),
       ('hr', 'HR staff and administrators'),
       ('admin', 'Administrators only')]


class PbFormFieldMeta(models.Model):
    _name = 'pb.form.field.meta'
    _description = 'Form builder field settings'
    _order = 'model, id'

    field_id = fields.Many2one('ir.model.fields', required=True, index=True,
                               ondelete='cascade')
    model = fields.Char(related='field_id.model', store=True, index=True)
    name = fields.Char(related='field_id.name', store=True)
    custom = fields.Boolean(default=True,
                            help='Made by the Form builder (can be deleted).')
    vis = fields.Selection(VIS, string='Who can see it', default='hr', required=True)
    is_required = fields.Boolean(string='Required')
    list_ok = fields.Boolean(string='Show in lists')
    formula_ok = fields.Boolean(string='Use in pay formulas')
    # R10 — empty means "All countries".
    country_ids = fields.Many2many('res.country', 'pb_form_field_meta_country_rel',
                                   'meta_id', 'country_id', string='Countries of work')
    # The host that made it, so the Field library can say where it came from.
    host_key = fields.Char()
    # R14 — My Payobook, per field (standard fields get a row only for these
    # flags; no field is created for them). Set through
    # `pb.form.studio.update_portal` / `update_field`, which refuse what the
    # host's `_pbfs_portal_hidden` / `_pbfs_portal_locked` forbid.
    portal_show = fields.Boolean(string='Show on My Payobook')
    portal_edit = fields.Boolean(string='Employee can change it')
    portal_mode = fields.Selection([('approve', 'HR approves the change'),
                                    ('instant', 'Saves at once')],
                                   string='When the employee changes it',
                                   default='approve', required=True)

    _field_uniq = models.Constraint('UNIQUE (field_id)',
                                    'A field has one set of Form builder settings.')
