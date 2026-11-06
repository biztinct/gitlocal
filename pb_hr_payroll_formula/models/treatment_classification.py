# -*- coding: utf-8 -*-
"""One ordered classification pass for schema import and Component treatment.

Excel evidence stores counts and format hints, never employee sample values.
The original Excel band is kept independently of the report grouping. No salary
rule categories, stored payslips or formulas are changed by this process.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import value_kind_classifier

REPORT_GROUPS = {
    'earning': 'Earnings', 'deduction': 'Deductions', 'net': 'Net pay',
    'employer_cost': 'Employer costs', 'info': 'Information', 'mixed': 'Mixed',
}


class FormulaRuleTreatment(models.Model):
    _inherit = 'hr.formula.rule'

    schema_value_shape = fields.Json(copy=True)
    schema_format_kind = fields.Selection([
        ('date', 'Date'), ('rate', 'Percentage'), ('text', 'Text'),
    ], copy=True)
    imported_component_type = fields.Char(help='Original section label in the Excel schema.')
    component_type_source = fields.Selection([
        ('auto', 'Automatic'), ('user', 'Set by you'), ('legacy', 'Saved group (kept)'),
    ], default='auto', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for values in vals_list:
            values = dict(values)
            if 'component_type' in values and 'component_type_source' not in values:
                values['component_type_source'] = 'user' if values['component_type'] else 'auto'
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        values = dict(values)
        if 'component_type' in values and 'component_type_source' not in values:
            values['component_type_source'] = 'user' if values['component_type'] else 'auto'
        return super().write(values)

    @api.model
    def _schema_type_evidence(self, values, number_formats=()):
        """Persist only type evidence; blank/unformatted cells do not vote."""
        from openpyxl.styles.numbers import is_date_format
        formats = [str(fmt) for fmt in number_formats if fmt and fmt != 'General']
        kind = False
        if formats and all(is_date_format(fmt) for fmt in formats):
            kind = 'date'
        elif formats and all('%' in fmt for fmt in formats):
            kind = 'rate'
        elif formats and all(fmt == '@' for fmt in formats):
            kind = 'text'
        return {
            'schema_value_shape': value_kind_classifier.sample_shape(values),
            'schema_format_kind': kind,
        }


class FormulaConfigTreatment(models.Model):
    _inherit = 'hr.formula.config'

    def _classify_report_groups(self):
        self.ensure_one()
        for rule in self.rule_ids:
            if rule.component_type_source in ('user', 'legacy'):
                continue
            group = REPORT_GROUPS.get(rule.net_role, 'Needs review')
            if rule.component_type != group:
                rule.with_context(skip_formula_version=True).write({
                    'component_type': group, 'component_type_source': 'auto',
                })

    def _classify_component_treatment(self, strict=False):
        """Types first (so hours cannot become earnings), then graph and groups.

        Manual choices survive on each axis. The explicit action is atomic: a
        rejected graph classification rolls back its preceding type changes.
        Import can retain type evidence when the scheme still needs a net-pay
        component, but never bypasses the existing accounting safety rail.
        """
        self.ensure_one()
        tracked = ('value_kind', 'net_role', 'net_role_detail', 'component_type')
        before = {r.id: tuple(r[f] for f in tracked) for r in self.rule_ids}
        with self.env.cr.savepoint():
            self.classify_value_kinds()
            summary = (self.classify_net_roles() or {}).get(self.id) or {}
            if summary.get('error') and (strict or summary.get('blocked')):
                raise UserError(_("This scheme could not be re-classified: %(why)s",
                                  why=summary['error']))
            self._classify_report_groups()
        changed = [r.code for r in self.rule_ids
                   if before[r.id] != tuple(r[f] for f in tracked)]
        return dict(summary, changed=len(changed), changed_codes=changed,
                    kept=len(self.rule_ids.filtered(
                        lambda r: r.value_kind_source == 'user'
                        or r.net_role_source == 'user'
                        or r.component_type_source in ('user', 'legacy'))),
                    gated=len(summary.get('gated') or []))

