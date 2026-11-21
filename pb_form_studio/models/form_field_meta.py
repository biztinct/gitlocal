# -*- coding: utf-8 -*-
"""What the Form builder knows about one field beyond the field itself.

One row per custom field the engine made, and one per standard field the
administrator ticked for My Payobook (R14) or hid / relabelled (R23). The ORM-facing visibility lives on the
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

    # R23 (FS-7) — a STANDARD field's screen rule, set by the administrator
    # (`pb.form.studio.update_standard`). A SCREEN rule only: the field, its
    # values and every reader (formulas, imports, Mapping, reports) are
    # untouched; nothing is written on `ir.model.fields` (its label would leak
    # into Mapping, Updates sheets and exports, and be reset by upgrades).
    std_hidden = fields.Boolean(string='Hidden for everyone')
    std_country_ids = fields.Many2many(
        'res.country', 'pb_form_field_meta_std_country_rel', 'meta_id', 'country_id',
        string='Hidden for these Countries of Work')
    # {lang code: label}. A language with no entry shows the built-in label —
    # deliberately not a translated field, which would show the English text
    # in Vietnamese until somebody typed a Vietnamese one.
    std_labels = fields.Json(string='Own labels')

    # R31 (FS-15) — the countries a STANDARD field shows for, as ONE choice
    # that replaces the product's built-in setting (TIDY-E's "Only Vietnam"
    # or "taken off the screens"). Empty `std_show` = the built-in setting.
    # The two FS-7 fields above are still read (an older row is shown and
    # applied exactly as before, `_pbfs_std_override`); every new save writes
    # these three and clears those.
    std_show = fields.Selection([('all', 'All countries'),
                                 ('only', 'Only these Countries of Work'),
                                 ('none', 'Hidden for everyone')], string='Shown for')
    std_show_country_ids = fields.Many2many(
        'res.country', 'pb_form_field_meta_std_show_rel', 'meta_id', 'country_id',
        string='Shown for these Countries of Work')
    std_show_unset = fields.Boolean(string='Also people with no Country of Work')

    _field_uniq = models.Constraint('UNIQUE (field_id)',
                                    'A field has one set of Form builder settings.')
