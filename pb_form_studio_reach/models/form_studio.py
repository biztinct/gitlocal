# -*- coding: utf-8 -*-
"""The engine, extended from outside (FS-5). `pb_form_studio` is not edited.

* `_pbfr_refs_formulas` — a delete blocker and a "Used by" line: payroll
  components that read the field as a payroll source. (Pay-data import
  mappings, saved views and saved searches are the engine's own finders.)
* `update_field` — "Use in pay formulas" cannot be switched off while a
  pay formula reads the field (the formula would silently lose its input).
* Two small helpers the other surfaces share: which custom fields the caller
  may NOT read, and whether a field applies to one record's Country of Work.
"""
from odoo import api, models
from odoo.exceptions import UserError

from .common import REACH_MODELS, source_key


class PbFormStudioReach(models.AbstractModel):
    _inherit = 'pb.form.studio'

    # ------------------------------------------------------------ finders
    @api.model
    def _pbfs_reference_finders(self):
        return super()._pbfs_reference_finders() + ['_pbfr_refs_formulas']

    @api.model
    def _pbfr_formula_rules(self, model, name):
        # `hr.formula.rule` is a dependency (pb_hr_payroll_formula).
        Rule = self.env['hr.formula.rule'].sudo().with_context(active_test=False)
        key = source_key(model, name)
        if not key:
            return Rule.browse()
        return Rule.search([('application_source_key', '=', key)])

    @api.model
    def _pbfr_refs_formulas(self, model, name):
        rules = self._pbfr_formula_rules(model, name)
        if not rules:
            return []
        names = ['%s · %s' % (r.config_id.display_name or '', r.name or r.code or '')
                 for r in rules]
        return [self._pbfs_ref('formula', self.env._('Pay formulas'), names,
                               count=len(rules))]

    # ------------------------------------------------------------- guards
    @api.model
    def update_field(self, model, name, vals):
        vals = dict(vals or {})
        if 'formula_ok' in vals and not vals['formula_ok'] and model in REACH_MODELS:
            self._pbfs_check_admin()
            rules = self._pbfr_formula_rules(model, name)
            if rules:
                raise UserError(self.env._(
                    'Pay formulas read this field: %s. Choose another source for them '
                    'first, then switch "Use in pay formulas" off.',
                    ', '.join(rules.mapped('name')[:5])))
        return super().update_field(model, name, vals)

    # ------------------------------------------------------------ helpers
    @api.model
    def _pbfr_hidden_names(self, model):
        """Custom fields of `model` the caller may NOT read (labels and values
        of these never reach a surface built by this bridge)."""
        if model not in self.env or model not in self._pbfs_host_models():
            return set()
        readable = {s['name'] for s in self.fields_for(model, 'all')}
        return set(self._pbfs_custom_names(model)) - readable

    @api.model
    def _pbfr_applies(self, record, name, memo=None):
        """R10 — does custom field `name` apply to `record`'s Country of Work?
        `memo` (optional dict) keeps the country of each record and the
        settings of each field for one call."""
        if not record:
            return False
        memo = memo if memo is not None else {}
        mkey = ('pbfr_meta', record._name, name)
        if mkey not in memo:
            memo[mkey] = self._pbfs_meta(record._name, [name]).get(name)
        meta = memo[mkey]
        if not meta or not meta.country_ids:
            return True
        ckey = ('pbfr_country', record._name, record.id)
        if ckey not in memo:
            memo[ckey] = self._pbfs_record_countries(record).get(record.id)
        return self._pbfs_applies(meta, memo[ckey])
