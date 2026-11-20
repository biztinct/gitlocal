# -*- coding: utf-8 -*-
"""FS-9 follow-on C — the old Bank / Account Number boxes are no longer
OFFERED as Mapping destinations.

They are off every screen (Full details, side panel), and nothing pays from
them: bank details go to the "Bank" lane (the employee's bank account, through
the approval hold). The Mapping catalogue (`pb_formula_studio`
`_ec_right_items`, `ec_model_fields`, `ec_search_fields`) stops listing them,
and `employee_mapping_create` refuses a NEW mapping into them.

Truthful catalogue (MAPFIX E2 / F3): a mapping SAVED before this keeps working
unchanged — `_ec_is_mappable` still says yes, so the import still writes the
box and `employee_mapping_data` still draws the wire and its card (its own
"keep a wired field visible" path) — and that card, only where it is wired,
says "No longer shown — use Bank account". Live count of such mappings on the
five sites: 0 (FS9_FACTS.md §4).
"""

from odoo import api, models

#: (model, field) -> nothing; the boxes FS-9 took off the screens
RETIRED = {('hr.employee', 'bank_name'), ('hr.employee', 'account_number')}


class PbFormulaStudioRetiredBank(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    @api.model
    def _ec_retired(self, model, fname):
        return (model, fname) in RETIRED

    @api.model
    def _ec_retired_note(self):
        _ = self.env._
        return {
            'text': _("No longer shown — use Bank account"),
            'title': _("This box is no longer on any screen and nothing is paid from it. The mapping saved here keeps working; for bank details, send the column to the Bank lane (the employee's bank account) instead."),  # noqa: E501 — one msgid per line (S2C-3)
            'tone': 'warn',
        }

    @api.model
    def _ec_drop_retired(self, items):
        out = []
        for item in items or []:
            meta = item.get('meta') or {}
            if self._ec_retired(meta.get('model'), meta.get('field')):
                continue
            out.append(item)
        return out

    @api.model
    def _ec_right_items(self, q=''):
        return self._ec_drop_retired(super()._ec_right_items(q))

    @api.model
    def ec_model_fields(self, model):
        res = super().ec_model_fields(model)
        if isinstance(res, dict) and res.get('fields'):
            res = dict(res, fields=self._ec_drop_retired(res['fields']))
        return res

    @api.model
    def _ec_field_item(self, fld, lane=None, lane_order=None, notes=None):
        item = super()._ec_field_item(fld, lane=lane, lane_order=lane_order, notes=notes)
        if self._ec_retired(fld.model, fld.name):
            item['meta'] = dict(item.get('meta') or {}, note=self._ec_retired_note(),
                                retired=True)
        return item

    @api.model
    def employee_mapping_create(self, config_id, context_id, component_id, target_spec):
        spec = self._ec_spec(target_spec)
        parts = spec.split(':')
        if len(parts) == 3 and parts[0] == 'f' and self._ec_retired(parts[1], parts[2]):
            return {'ok': False, 'msg': self._ec_retired_note()['text'] + '. ' + self.env._(
                "Send bank details to the Bank lane instead.")}
        return super().employee_mapping_create(config_id, context_id, component_id, target_spec)
