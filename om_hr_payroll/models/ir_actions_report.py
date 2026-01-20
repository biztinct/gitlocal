# -*- coding: utf-8 -*-

import io
import logging
from odoo import models, _
from odoo.exceptions import UserError

try:
    from PyPDF2.errors import EmptyFileError
except ImportError:
    EmptyFileError = Exception

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
        Also handles empty PDF streams to prevent PyPDF2 EmptyFileError during merge.
        """
        # For hr.payslip reports, validate that all res_ids actually exist
        if self.model == 'hr.payslip' and res_ids:
            # Check which payslips actually exist in the database
            valid_payslips = self.env['hr.payslip'].search([('id', 'in', res_ids)])
            valid_ids = valid_payslips.ids

            # Only use valid IDs for rendering
            if set(valid_ids) != set(res_ids):
                _logger.warning(f"Filtering out invalid payslip IDs. Original: {res_ids}, Valid: {valid_ids}")
                res_ids = valid_ids

                # If all IDs are invalid, raise an error
                if not res_ids:
                    raise UserError(_("No valid payslips found to print."))

        # Call super to get the streams
        collected_streams = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

        # For payslip reports, filter out empty streams to prevent EmptyFileError
        if self.model == 'hr.payslip' and collected_streams:
            empty_payslip_ids = []
            valid_streams = {}

            for record_id, stream_data in collected_streams.items():
                stream = stream_data.get('stream')
                if stream:
                    # Check if stream has content
                    if isinstance(stream, io.BytesIO):
                        stream.seek(0, 2)  # Seek to end
                        size = stream.tell()
                        stream.seek(0)  # Reset to beginning
                        if size > 0:
                            valid_streams[record_id] = stream_data
                        else:
                            empty_payslip_ids.append(record_id)
                    elif hasattr(stream, 'read'):
                        # For other file-like objects
                        content = stream.read()
                        if content:
                            stream.seek(0)
                            valid_streams[record_id] = stream_data
                        else:
                            empty_payslip_ids.append(record_id)
                    else:
                        # Assume valid if we can't check
                        valid_streams[record_id] = stream_data
                else:
                    empty_payslip_ids.append(record_id)

            if empty_payslip_ids:
                # Get employee names for better error message
                empty_payslips = self.env['hr.payslip'].browse(empty_payslip_ids)
                employee_names = empty_payslips.mapped('employee_id.name')
                _logger.warning(f"Skipping {len(empty_payslip_ids)} payslips with empty PDF content: {employee_names}")

                if not valid_streams:
                    raise UserError(_(
                        "Could not generate PDF for any payslips. "
                        "Please check that the payslip template is correctly configured.\n\n"
                        "Affected employees: %s"
                    ) % ', '.join(employee_names))

            return valid_streams

        return collected_streams

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
