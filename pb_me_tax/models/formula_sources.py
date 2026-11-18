# -*- coding: utf-8 -*-
"""Approved tax details as application sources a pay scheme CAN read.

Registered in the engine's typed-source seam
(`hr.formula.config._application_source_catalogue` /
`_application_domain_values`, the precedent of pb_time_pay's late minutes).
A source answers ONLY for a component that somebody mapped to it
(`hr.formula.rule.application_source_key`); this module maps nothing, so no
existing scheme reads anything new and every payslip computes exactly as
before (S2-D item 4, test 8).

Values are the stored codes ("K/1", "new", "cdac"), never the translated
labels, so a formula compares the same text in every language. Reads keep
the engine's rule: the payroll actor's own rights, no sudo fallback
(`application_domain_sources`), and "missing" is never zero.
"""

import logging

from odoo import models
from odoo.exceptions import AccessError, MissingError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.pb_hr_payroll_formula.models.application_domain_sources import (
        source_result)
    from odoo.addons.pb_hr_payroll_formula.models.application_payroll_source import (
        checked_read, readable_field)
except Exception:  # pragma: no cover — the engine is a dependency
    source_result = checked_read = readable_field = None

#: key -> (catalogue label, unit, employee field)
TAX_SOURCES = {
    'tax.id_ptkp_status': ('Indonesia PTKP status (approved)', 'text',
                           'pb_id_ptkp_status'),
    'tax.in_pan_number': ('India PAN (approved)', 'text', 'pb_in_pan_number'),
    'tax.in_tax_regime': ('India tax regime (approved)', 'text',
                          'pb_in_tax_regime'),
    'tax.sg_shg_fund': ('Singapore self-help group fund (approved)', 'text',
                        'pb_sg_shg_fund'),
    'tax.vn_confirmed_dependants': ('Vietnam tax dependants confirmed by HR',
                                    'integer', 'vn_eligible_dependent_count'),
}


class HrFormulaConfigTaxSources(models.Model):
    _inherit = 'hr.formula.config'

    def _application_source_catalogue(self):
        result = dict(super()._application_source_catalogue())
        Employee = self.env['hr.employee']
        for key, (label, unit, field) in TAX_SOURCES.items():
            if field not in Employee._fields:
                continue
            result[key] = {
                'label': label, 'unit': unit, 'model': 'hr.employee',
                'field': field, 'writable': False, 'available': True,
                'effective_date': 'current_record_snapshot',
            }
        return result

    def _application_domain_values(self, employee, contract, date_from, date_to):
        result = dict(super()._application_domain_values(
            employee, contract, date_from, date_to))
        if source_result is None:
            return result
        self.ensure_one()
        wanted = {(r.application_source_key or '').strip()
                  for r in self.sudo().rule_ids
                  if r.column_type == 'input'} & set(TAX_SOURCES)
        for key in sorted(wanted):
            try:
                result[key] = self._pbtx_source_value(key, employee)
            except (AccessError, MissingError):
                result[key] = source_result(reason='source_not_accessible',
                                            key=key)
            except Exception:                           # noqa: BLE001
                _logger.exception('pb_me_tax: source %s failed for %s', key,
                                  employee.id)
                result[key] = source_result(
                    status='conflict', reason='The tax detail could not be read.')
        return result

    def _pbtx_source_value(self, key, employee):
        _label, unit, field = TAX_SOURCES[key]
        record = employee.sudo(False)
        if not record or record.company_id != self.company_id \
                or field not in record._fields:
            return source_result(reason='field_not_available')
        checked_read(record)
        if not readable_field(record, field):
            raise AccessError('This source field is restricted.')
        value = record[field]
        if unit == 'integer':
            return source_result(int(value or 0), 'resolved', record,
                                 field=field, snapshot='current_master_record')
        if not value:
            return source_result(reason='not_on_record', field=field)
        return source_result(str(value), 'resolved', record, field=field,
                             snapshot='current_master_record')
