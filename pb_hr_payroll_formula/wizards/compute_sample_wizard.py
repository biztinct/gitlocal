# -*- coding: utf-8 -*-
"""
Wizard to run Sync & Compute for a sample after ensuring the record is saved.

Purpose: avoid inline editable tree losing the last edit by moving the action
into a transient form. Opening the wizard commits the sample record; running it
calls the existing sample action to sync inputs and compute values, then
refreshes the form.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrFormulaComputeWizard(models.TransientModel):
    _name = "hr.formula.compute.wizard"
    _description = "Run Sync & Compute"

    sample_id = fields.Many2one(
        "hr.formula.sample.data",
        string="Sample",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )

    config_id = fields.Many2one(
        related="sample_id.config_id",
        string="Configuration",
        readonly=True,
    )

    note = fields.Text(
        default=lambda self: _(
            "The input values you enter here are computed for testing only. "
            "This does not impact any live or posted payroll data."
        ),
        readonly=True,
    )

    def action_run(self):
        self.ensure_one()
        if not self.sample_id:
            raise UserError(_("No sample selected."))

        # Call existing sample method (it recomputes values after syncing inputs)
        self.sample_id.action_sync_input_to_json()

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
