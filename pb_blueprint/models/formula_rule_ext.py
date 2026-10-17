# -*- coding: utf-8 -*-
"""Where a component's rule came from — the sentence, or somebody's Excel.

BP-R3. A component built from the guided sentence carries the sentence itself
(``bp_recipe_json``) and the exact formula that sentence produced
(``bp_generated_formula``). Regeneration is then safe: it rewrites only rules
whose formula is still the one it wrote.

The moment ANYBODY writes a different formula — the components grid, a bulk
save, a workbook import, a script — the rule flips to ``manual`` and no
regeneration will ever touch it again. That flip lives in ``write()`` rather
than in the guided setup's own save path on purpose: a guard that only the
guided setup honours is a guard that the grid walks straight past, and the
person who typed the formula would silently lose it.

This mirrors ``column_role_source`` / ``value_kind_source``
(``formula_rule.py:660-664, 722-727``, guard ``:1682-1690``) — one contract,
enforced at the one place every writer passes through.
"""
import json

from odoo import fields, models


class HrFormulaRuleBlueprint(models.Model):
    _inherit = 'hr.formula.rule'

    bp_recipe_json = fields.Text(
        string='Guided Rule (JSON)', copy=True,
        help="The plain-language rule this component was built from. Empty "
             "means the component was never built from a sentence.")

    bp_generated_formula = fields.Char(
        string='Generated Formula', copy=True,
        help="The formula the sentence produced, as it was written. Used to "
             "tell a generated formula apart from one somebody typed.")

    bp_generated_revision = fields.Integer(
        string='Generated Revision', default=0, copy=True,
        help="Bumped every time the sentence produced a different formula.")

    bp_formula_source = fields.Selection([
        ('generated', 'Generated from the sentence'),
        ('manual', 'Written as Excel'),
    ], string='Formula Source', default='manual', required=True, copy=True,
        index=True,
        help="Generated formulas are rewritten whenever the sentence or "
             "anything it depends on changes. A formula somebody typed is "
             "never rewritten.")

    bp_template_key = fields.Char(
        string='Came From Starter', copy=True, index=True,
        help="Which starting point this component was seeded from, so it can "
             "be restored after it is removed.")

    def write(self, vals):
        """A formula that is not the generated one belongs to a person.

        Deliberately per-record: one ``write`` call can carry several rules and
        only the ones whose formula actually drifts from what the sentence
        produced may flip. An explicit ``bp_formula_source`` in the same call
        wins — that is the guided setup writing its own generated formula.
        """
        if not vals or 'excel_formula' not in vals or 'bp_formula_source' in vals:
            return super().write(vals)
        incoming = self._normalize_excel_formula(vals.get('excel_formula') or '') or ''
        drifted = self.filtered(
            lambda r: (self._normalize_excel_formula(r.bp_generated_formula or '') or '')
            != incoming)
        result = super().write(vals)
        if drifted:
            # A second, tiny write: `bp_formula_source` is not a versioned
            # field, so this adds no row to the formula history.
            super(HrFormulaRuleBlueprint, drifted).write(
                {'bp_formula_source': 'manual'})
        return result

    def bp_recipe(self):
        """The stored sentence as a dict, or None. Never raises."""
        self.ensure_one()
        raw = self.bp_recipe_json
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None
