# -*- coding: utf-8 -*-
"""A saved contract document remembers the contract it was printed for and
its running version ("Employment contract · v2 · 22 Nov 2026"). Earlier
versions are never replaced: every save is a new document in the vault (the
letter engine's `_file_in_vault` early return is not used, FACTS gotcha 6)."""
from odoo import fields, models


class PbEmployeeDocument(models.Model):
    _inherit = 'pb.employee.document'

    pbdc_contract_id = fields.Many2one(
        'hr.contract', string='Printed for contract', index=True,
        ondelete='set null', copy=False)
    pbdc_version = fields.Integer(string='Contract document version', copy=False)
