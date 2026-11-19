# -*- coding: utf-8 -*-
"""Visibility for Form-builder fields, enforced by the ORM.

FS-1 FINDING (V1 in the report): on this build `ir.model.fields.groups` is an
unimplemented column — core marks it "CLEANME unimplemented field (empty
table)" (odoo/addons/base/models/ir_model.py:562) and `_instanciate_attrs`
(:1293) never reads it. Writing groups there restricts NOTHING.

So the engine keeps its own column, `pbfs_groups`, on the field row itself.
`_all_manual_field_data` is a `SELECT *` over `ir_model_fields` (:1276), so the
row handed to `_instanciate_attrs` already carries it, and the override below
turns it into the field's real `groups=` attribute. From then on core does
the enforcing everywhere: `fields_get` leaves the field out, `read` /
`search_read` / `web_read` / `write` of it raise AccessError, a plain `read()`
without a field list skips it (`_has_field_access`, odoo/orm/models.py:3375).

Changing it is a write on `ir.model.fields`, which re-runs
`_setup_models__` and so sets `registry_invalidated` — every other worker
reloads its registry on its next request (no restart).

Only fields the engine made (`x_pbfs_` prefix) are ever touched.
"""
from odoo import api, fields, models

PREFIX = 'x_pbfs_'


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    pbfs_groups = fields.Char(
        string='Form builder visibility',
        help='Technical: the permission list the Form builder applies to '
             'this field. Empty means everyone who may open the record.')

    @api.model
    def _instanciate_attrs(self, field_data):
        attrs = super()._instanciate_attrs(field_data)
        if attrs is not None and (field_data.get('name') or '').startswith(PREFIX):
            groups = field_data.get('pbfs_groups')
            if groups:
                attrs['groups'] = groups
        return attrs
