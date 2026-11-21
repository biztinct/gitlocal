# -*- coding: utf-8 -*-
"""Form-builder fields as payroll sources a pay scheme CAN read (FS-5 item 1).

Cloned from `pb_me_tax/models/formula_sources.py` (the engine's typed-source
seam: `hr.formula.config._application_source_catalogue` /
`_application_domain_values`).

* Catalogue: ONLY fields marked "Use in pay formulas" (number, money, yes/no,
  choice, date) that the reader may see — `pb.form.studio.fields_for(model,
  'formula')`, so a hidden field is not even named to somebody who may not
  see it. Keys: `custom.employee.<field>` / `custom.contract.<field>`.
* Values: answered ONLY for a component somebody mapped to such a key; this
  module maps nothing, so every existing scheme computes exactly as before
  (FS-5 test 1c, payslip identical). Read with the payroll actor's own rights
  (`checked_read` / `readable_field`, no sudo fallback). A field limited to
  other countries of work answers "not for this country" — an empty value,
  never somebody else's number (R10). "Missing" is never zero.
* A choice answers its ENGLISH label, so a formula compares the same text in
  every language (the stored keys `opt_1` mean nothing to a formula writer).
"""
import logging

from odoo import models
from odoo.exceptions import AccessError, MissingError

from odoo.addons.pb_form_studio.models.form_studio import FORMULA_TTYPES

from .common import CON, EMP, REACH_MODELS, SOURCE_PREFIX, parse_source_key, source_key

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.pb_hr_payroll_formula.models.application_domain_sources import (
        source_result)
    from odoo.addons.pb_hr_payroll_formula.models.application_payroll_source import (
        checked_read, readable_field)
except Exception:  # pragma: no cover — the engine is a dependency
    source_result = checked_read = readable_field = None


class HrFormulaConfigFormBuilderSources(models.Model):
    _inherit = 'hr.formula.config'

    def _application_source_catalogue(self):
        result = dict(super()._application_source_catalogue())
        Studio = self.env['pb.form.studio']
        for model in REACH_MODELS:
            for spec in Studio.fields_for(model, 'formula'):
                key = source_key(model, spec['name'])
                if not key:
                    continue
                result[key] = {
                    'label': self.env._('Company details: %s', spec['label']),
                    'unit': spec['type'], 'model': model, 'field': spec['name'],
                    'writable': False, 'available': True,
                    'effective_date': 'current_record_snapshot',
                    'form_builder': True,
                }
        return result

    def _application_domain_values(self, employee, contract, date_from, date_to):
        result = dict(super()._application_domain_values(
            employee, contract, date_from, date_to))
        if source_result is None:
            return result
        self.ensure_one()
        wanted = {(r.application_source_key or '').strip()
                  for r in self.sudo().rule_ids if r.column_type == 'input'}
        wanted = {k for k in wanted if k.startswith(SOURCE_PREFIX)}
        if not wanted:
            return result
        employee = employee.sudo(False)
        if not employee or employee.company_id != self.company_id:
            # the engine's own rule for every record source
            return result
        memo = {}
        for key in sorted(wanted):
            try:
                result[key] = self._pbfr_source_value(key, employee, contract, memo)
            except (AccessError, MissingError):
                result[key] = source_result(reason='source_not_accessible', key=key)
            except Exception:                           # noqa: BLE001
                _logger.exception('pb_form_studio_reach: source %s failed for %s',
                                  key, employee.id)
                result[key] = source_result(
                    status='conflict', reason='The company detail could not be read.')
        return result

    def _pbfr_source_value(self, key, employee, contract, memo):
        model, name = parse_source_key(key)
        if not model:
            return source_result(reason='field_not_available')
        record = (employee if model == EMP else contract).sudo(False)
        Studio = self.env['pb.form.studio']
        meta = Studio._pbfs_meta(model, [name]).get(name)
        if not record or not meta or not meta.custom or not meta.formula_ok \
                or name not in record._fields \
                or record._fields[name].type not in FORMULA_TTYPES:
            return source_result(reason='field_not_available')
        if model == CON and (record.employee_id != employee
                             or record.company_id != self.company_id):
            return source_result(status='conflict', reason='contract_scope_mismatch')
        checked_read(record)
        if not readable_field(record, name):
            raise AccessError('This source field is restricted.')
        if not Studio._pbfr_applies(record, name, memo):
            return source_result(reason='not_for_this_country_of_work', field=name)
        field = record._fields[name]
        value = record[name]
        snap = {'field': name, 'snapshot': 'current_master_record'}
        if field.type in ('integer', 'float', 'monetary'):
            return source_result(float(value or 0.0), 'resolved', record, **snap)
        if field.type == 'boolean':
            return source_result(bool(value), 'resolved', record, **snap)
        if not value:
            return source_result(reason='not_on_record', field=name)
        if field.type == 'selection':
            labels = dict(field._description_selection(record.with_context(lang='en_US').env))
            return source_result(labels.get(value, value), 'resolved', record, **snap)
        return source_result(value, 'resolved', record, **snap)   # date → ISO text
