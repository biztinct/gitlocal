# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class PbMultisheetWizard(models.AbstractModel):
    """Bespoke powder shell for the multi-sheet Excel import:
    upload -> analyze -> select sheets -> select columns, then hands the
    transient record off to the native form for the fragile drag-reorder /
    missing-field / confirm steps (no cross-sheet logic reimplemented)."""
    _name = 'pb.import.multisheet.wizard'
    _description = 'Payobook guided multi-sheet import (shell)'

    _MODEL = 'hr.formula.multisheet.import.wizard'

    @api.model
    def get_defaults(self):
        configs = [{'id': c.id, 'name': c.name}
                   for c in self.env['hr.formula.config'].search([], limit=100)]
        return {'configs': configs,
                'default_config_id': configs[0]['id'] if configs else False}

    def _serialize(self, rec):
        return {
            'wizard_id': rec.id, 'state': rec.state,
            'main_sheet_name': rec.main_sheet_name or '',
            'sheets': [{
                'id': s.id, 'name': s.sheet_name or '',
                'selected': bool(s.is_selected), 'is_main': bool(s.is_main_sheet),
                'rows': s.row_count, 'cols': s.column_count,
                'header_row': s.detected_header_row,
            } for s in rec.available_sheet_ids],
            'error': None,
        }

    @api.model
    def start(self, vals):
        cvals = {'import_file': vals['file_b64'],
                 'import_filename': vals.get('file_name') or 'workbook.xlsx'}
        if vals.get('config_id'):
            cvals['config_id'] = int(vals['config_id'])
        rec = self.env[self._MODEL].create(cvals)
        err = None
        try:
            rec.action_analyze_file()
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Could not analyze the file.'
            _logger.warning("Multisheet analyze failed: %s", e)
        out = self._serialize(rec)
        out['error'] = err
        return out

    @api.model
    def save_sheet(self, line_id, is_selected):
        line = self.env['hr.formula.multisheet.sheet.line'].browse(int(line_id))
        line.write({'is_selected': bool(is_selected)})
        return self._serialize(line.wizard_id)

    @api.model
    def set_main_sheet(self, wizard_id, line_id):
        rec = self.env[self._MODEL].browse(int(wizard_id))
        for s in rec.available_sheet_ids:
            s.is_main_sheet = (s.id == int(line_id))
            if s.id == int(line_id):
                s.is_selected = True
        rec.main_sheet_name = self.env['hr.formula.multisheet.sheet.line'].browse(int(line_id)).sheet_name
        return self._serialize(rec)

    @api.model
    def to_native(self, wizard_id):
        """Hand the analyzed wizard off to the native form, which owns the
        primary-key choice, column selection, drag-reorder, missing-field
        mapping and confirm steps (workbook-specific cross-sheet logic we
        deliberately don't reimplement). The sheet selections made in the
        powder shell are already persisted on the records."""
        rec = self.env[self._MODEL].browse(int(wizard_id))
        # mirror the native wizard's own _return_wizard_action: a TransientModel
        # form must open as a dialog (target:new), not target:current.
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._MODEL, 'res_id': rec.id,
            'views': [[False, 'form']], 'view_mode': 'form', 'target': 'new',
        }
