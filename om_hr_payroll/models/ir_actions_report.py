# -*- coding: utf-8 -*-

import logging
from odoo import models

_logger = logging.getLogger(__name__)


class SafeDict(dict):
    """Dictionary that returns 0 for missing keys instead of raising KeyError"""
    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            return 0

    def __sub__(self, other):
        """Support subtraction operations like dsal['ATI'] - dsal['TAXIN']"""
        if isinstance(other, (int, float)):
            return 0 - other
        return 0


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        """
        Override to filter out invalid payslip records before rendering.
        This prevents errors when dashboard passes phantom active_id values.
        """
        # For hr.payslip reports, validate that all res_ids actually exist
        if self.model == 'hr.payslip' and res_ids:
            _logger.info(f"=== Validating payslip IDs: {res_ids} ===")

            # Check which payslips actually exist in the database
            valid_payslips = self.env['hr.payslip'].search([('id', 'in', res_ids)])
            valid_ids = valid_payslips.ids

            _logger.info(f"Valid payslip IDs: {valid_ids}")
            _logger.info(f"Invalid payslip IDs: {set(res_ids) - set(valid_ids)}")

            # Only use valid IDs for rendering
            if valid_ids != res_ids:
                _logger.warning(f"Filtering out invalid payslip IDs. Original: {res_ids}, Valid: {valid_ids}")
                res_ids = valid_ids

                # If all IDs are invalid, raise an error
                if not res_ids:
                    from odoo.exceptions import ValidationError
                    raise ValidationError("No valid payslips found to print.")

        return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

    def _render_template(self, template, values):
        """
        Override to provide safe dictionary access for payslip report values.
        This prevents KeyError when salary codes are missing from payslips.
        """
        # Make dsal a SafeDict if it exists in values
        if 'dsal' in values and isinstance(values['dsal'], dict):
            safe_dsal = SafeDict(values['dsal'])
            values['dsal'] = safe_dsal

        return super()._render_template(template, values)
