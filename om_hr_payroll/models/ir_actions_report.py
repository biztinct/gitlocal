# -*- coding: utf-8 -*-

import logging
from collections import defaultdict
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

    def _render_template(self, template, values):
        """
        Override to provide safe dictionary access for payslip report values.
        This prevents KeyError when salary codes are missing from payslips.
        """
        _logger.info(f"=== _render_template called ===")
        _logger.info(f"Template: {template}")
        _logger.info(f"Values keys: {list(values.keys())}")
        for key, value in values.items():
            if isinstance(value, dict):
                _logger.info(f"  {key} is dict with keys: {list(value.keys())}")
            elif isinstance(value, (list, tuple)):
                _logger.info(f"  {key} is {type(value).__name__} with {len(value)} items")
            else:
                _logger.info(f"  {key} = {value}")

        # Make dsal a SafeDict if it exists in values
        if 'dsal' in values and isinstance(values['dsal'], dict):
            safe_dsal = SafeDict(values['dsal'])
            values['dsal'] = safe_dsal
            _logger.info(f"Converted dsal to SafeDict with {len(safe_dsal)} keys: {list(safe_dsal.keys())}")

        return super()._render_template(template, values)
