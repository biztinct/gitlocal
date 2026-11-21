# -*- coding: utf-8 -*-
"""Mapping (FS-5 item 3): a "Company details" lane on the board.

The board is already dynamic — every writable `ir.model.fields` row of the
employee and the contract is a destination (`_ec_right_items`), so a
Form-builder field already appeared under "Other employee fields", but only
through the board's search, because the normal board shows the CURATED
lanes (`employee_mapping_data` keeps cards whose `(model, field)` is in
`_ec_lane_index`). The clean seam is `_ec_lane_index` + `_ec_lane_label`:
custom fields the reader may see become a curated lane of their own,
between the bank lane and "Other employee fields".

And one rail: `_ec_is_mappable` — the board's single inclusion rule, asked
both when the catalogue is drawn and when a wire is CREATED — refuses a
custom field the reader may not see, so its label is never offered and a
forged call cannot wire it (which would carry its value into a payslip).
Files are never destinations (not in `_EC_TTYPES`).
"""
from odoo import api, models, tools

from .common import CON, EMP, PREFIX

LANE = 'company_details'


class FormulaStudioMappingLane(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    @api.model
    def _ec_lane_label(self, key):
        if key == LANE:
            return self.env._("Company details")
        return super()._ec_lane_label(key)

    @api.model
    def _ec_is_mappable(self, model, fname):
        if not super()._ec_is_mappable(model, fname):
            return False
        if fname.startswith(PREFIX):
            Model = self.env[model]
            return Model._has_field_access(Model._fields[fname], 'read')
        return True

    @api.model
    def _ec_lane_index(self):
        pos_of, order_of = super()._ec_lane_index()
        names = self._pbfr_lane_fields()
        if not names:
            return pos_of, order_of
        pos_of, order_of = dict(pos_of), dict(order_of)
        # Just before "Other employee fields" (a half step: lane orders are
        # only ever compared, never used as list indexes).
        n = order_of.get('other_employee', len(order_of)) - 0.5
        order_of[LANE] = n
        for pos, pair in enumerate(names):
            pos_of.setdefault(pair, (n, LANE, pos))
        return pos_of, order_of

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.su', 'self.env.lang')
    def _pbfr_lane_fields(self):
        """`((model, field), …)` in label order: the custom fields of the
        employee and the contract this reader may see. Asked once per card by
        the board, so cached; the cache is cleared by every registry setup,
        which is what adding, deleting or re-permissioning a field runs."""
        Studio = self.env['pb.form.studio']
        rows = []
        for model in (EMP, CON):
            for spec in Studio.fields_for(model, 'all'):
                if spec['type'] != 'binary':
                    rows.append((spec['label'].lower(), model, spec['name']))
        rows.sort()
        return tuple((m, n) for _l, m, n in rows)
