# -*- coding: utf-8 -*-
"""Access (FS-5 item 6): custom fields in the Access catalogue.

`biz_access` keeps a static, reviewed catalogue of fields per record type
(`RESOURCES`). FS-5 added ONE generic hook there, `pb.access.
_studio_extra_fields(model)` (manual fields only), used to list extra fields
under their record type in the role-policy editor and to enforce a field
rule set on one exactly like a catalogue field's. This module answers it with
the Form-builder fields of the employee and the contract. A field nobody has
set a rule on keeps today's default (follows the record rules).
"""
from odoo import api, models, tools

from .common import CON, EMP, PREFIX


class AccessExtraFormBuilderFields(models.AbstractModel):
    _inherit = 'pb.access'

    @api.model
    def _studio_extra_fields(self, model):
        return list(super()._studio_extra_fields(model)) + list(self._pbfr_extra(model))

    @api.model
    @tools.ormcache('model')
    def _pbfr_extra(self, model):
        """Read off the registry (no query); cleared by every registry setup,
        which is what adding or deleting a field runs."""
        if model not in (EMP, CON) or model not in self.env:
            return ()
        return tuple(sorted(n for n, f in self.env[model]._fields.items()
                            if n.startswith(PREFIX) and f.manual))
