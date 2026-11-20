# -*- coding: utf-8 -*-
"""FS-10 — the save points of the things that really read a standard field.

The Form builder locks a standard employee / contract field from hiding only
while something on this database really reads it (architect ruling, FS-10):
a pay scheme component bound to it (`hr.formula.rule.application_source_key`)
in a scheme that is not archived, or a pay data file column that fills it
(`hr.payslip.import.mapping.target_field_id`). The answer is cached per
database with the screen designs (`pb.form.studio._pbfs_std_used`).

Every save that can change that answer calls ONE shared helper,
`pb.form.studio._pbfs_std_readers_changed`: it forgets the cached answer
(the registry tells every worker) and, if a field that was hidden is now
used, shows it again at that moment with a history line and a notice to the
administrators. Nothing else is touched; a save that changes nothing that
matters does not call it.
"""
from odoo import api, models

#: the fields of a component that decide what it reads
RULE_KEYS = ('application_source_key', 'config_id', 'column_type')
MAPPING_KEYS = ('target_field_id', 'target_model_id', 'salary_structure_id')


def _changed(env):
    env['pb.form.studio'].sudo()._pbfs_std_readers_changed()


class HrFormulaRuleStdReaders(models.Model):
    _inherit = 'hr.formula.rule'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any(v.get('application_source_key') for v in vals_list):
            _changed(self.env)
        return records

    def write(self, vals):
        before = any(r.application_source_key for r in self) if set(vals) & set(RULE_KEYS) else False
        res = super().write(vals)
        if set(vals) & set(RULE_KEYS) and (before or any(r.application_source_key for r in self)):
            _changed(self.env)
        return res

    def unlink(self):
        used = any(r.application_source_key for r in self)
        res = super().unlink()
        if used:
            _changed(self.env)
        return res


class HrFormulaConfigStdReaders(models.Model):
    _inherit = 'hr.formula.config'

    def write(self, vals):
        res = super().write(vals)
        if 'active' in vals:            # a scheme archived or restored
            _changed(self.env)
        return res

    def unlink(self):
        res = super().unlink()
        _changed(self.env)
        return res


class PayslipImportMappingStdReaders(models.Model):
    _inherit = 'hr.payslip.import.mapping'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any(v.get('target_field_id') for v in vals_list):
            _changed(self.env)
        return records

    def write(self, vals):
        before = any(r.target_field_id for r in self) if set(vals) & set(MAPPING_KEYS) else False
        res = super().write(vals)
        if set(vals) & set(MAPPING_KEYS) and (before or any(r.target_field_id for r in self)):
            _changed(self.env)
        return res

    def unlink(self):
        used = any(r.target_field_id for r in self)
        res = super().unlink()
        if used:
            _changed(self.env)
        return res
