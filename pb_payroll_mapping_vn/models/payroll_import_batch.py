# -*- coding: utf-8 -*-
"""A writeback may only write to a field that can be written to.

THE DEFECT THIS CLOSES. `_get_mapping_updates` builds `{field: value}` from
every mapping whose column the pay-data file happened to carry, and hands it to
`write()`. It checks that the field EXISTS on the record. It does not check that
the field can be SET. Until this module there was no mapped field that could
not: every destination was a stored, writable column.

Two of this profile's destinations are computed — months on the contract, days
of service this year — because they are arithmetic on dates and nobody should
restate them. If a file ever carried a column called "Months on this contract",
the writeback would reach `write()` with a computed field and raise, and it
would raise in the middle of a pay run, on somebody's payslip, for a value the
run had already worked out correctly for itself.

SO THE GUARD IS GENERIC AND NOT A SPECIAL CASE. Any non-storable or readonly
destination is dropped, whoever mapped it and whatever it is called. A mapping
that cannot be written is still perfectly good at being READ — that is what
rank 4 is — so dropping it here costs nothing and the pay run keeps its value.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class HrPayrollImportBatch(models.Model):
    _inherit = 'hr.payroll.import.batch'

    def _get_mapping_updates(self, record, raw_data, mappings=None, line=None,
                             contract=None, employee=None):
        updates = super()._get_mapping_updates(
            record, raw_data, mappings=mappings, line=line, contract=contract,
            employee=employee)
        if not updates:
            return updates
        writable = {}
        for name, value in updates.items():
            field = record._fields.get(name)
            if field is None:
                continue
            if not field.store or field.readonly:
                _logger.info(
                    "VN mapping: %s.%s is worked out rather than stored; the "
                    "pay-data file's value is ignored.", record._name, name)
                continue
            writable[name] = value
        return writable
