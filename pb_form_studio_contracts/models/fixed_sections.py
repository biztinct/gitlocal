# -*- coding: utf-8 -*-
"""FS-11 (owner ruling R29) — what each FIXED section of the contract side
panel really shows, field by field.

THE MAP is the panel's own terms table (`pb_contracts/models/
pb_contract_360.py` `_TERMS`), read at run time and grouped the way the
panel groups it (`_TERM_GROUPS`: The money · Dates · Where they sit ·
Payroll rules). A field whose module is not installed is skipped, exactly as
the panel skips it (`_cd_terms`). `test_fs11_fixed.py` proves map = screen.
"""
from odoo import api, models

from odoo.addons.pb_contracts.models.pb_contract_360 import _TERMS

from .form_studio_host import HOST, MODEL


class PbFormStudioContractFixed(models.AbstractModel):
    _inherit = 'pb.form.studio'

    @api.model
    def _pbfs_contract_panel_map(self):
        """`{panel group: [item]}` in the panel's own order."""
        Model = self.env[MODEL]
        out = {}
        for group, name, label, _kind, _hint, _optional in _TERMS:
            if name not in Model._fields:
                continue
            out.setdefault(group, []).append({
                'key': name, 'name': name, 'label': str(label), 'group': '', 'country': ''})
        return out

    @api.model
    def _pbfs_fixed_items(self, host_key, surface='panel'):
        out = dict(super()._pbfs_fixed_items(host_key, surface) or {})
        if host_key == HOST and surface != 'full' and MODEL in self.env:
            out.update(self._pbfs_contract_panel_map())
        return out
