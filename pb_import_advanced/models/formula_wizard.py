# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

SOURCES = [
    {'id': 'salary_rules', 'label': 'Salary rules'},
    {'id': 'structure', 'label': 'Payroll structure'},
    {'id': 'json', 'label': 'JSON file'},
    {'id': 'excel', 'label': 'Excel file'},
]


class PbFormulaWizard(models.AbstractModel):
    """Bespoke guided wrapper around hr.formula.import.wizard (single action)."""
    _name = 'pb.import.formula.wizard'
    _description = 'Payobook guided formula-config import'

    @api.model
    def get_defaults(self, config_id=False):
        Config = self.env['hr.formula.config']
        configs = [{'id': c.id, 'name': c.name} for c in Config.search([], limit=100)]
        structures = [{'id': s.id, 'name': s.name}
                      for s in self.env['hr.payroll.structure'].search([], limit=100)]
        default_cfg = config_id or (configs[0]['id'] if configs else False)
        return {
            'configs': configs, 'structures': structures, 'sources': SOURCES,
            'default_config_id': default_cfg,
        }

    @api.model
    def get_rules(self, term='', limit=80):
        term = (term or '').strip()
        dom = []
        if term:
            dom = ['|', ('name', 'ilike', term), ('code', 'ilike', term)]
        return [{'id': r.id, 'name': r.name, 'code': r.code or ''}
                for r in self.env['hr.salary.rule'].search(dom, limit=limit)]

    @api.model
    def get_structure_rules(self, structure_id):
        s = self.env['hr.payroll.structure'].browse(int(structure_id))
        return [{'id': r.id, 'name': r.name, 'code': r.code or ''} for r in s.rule_ids]

    @api.model
    def run_import(self, vals):
        Wiz = self.env['hr.formula.import.wizard']
        src = vals.get('import_source') or 'salary_rules'
        cvals = {
            'config_id': int(vals['config_id']),
            'import_source': src,
            'create_input_columns': bool(vals.get('create_input_columns', True)),
            'preserve_existing': bool(vals.get('preserve_existing', True)),
            'map_categories': bool(vals.get('map_categories', True)),
        }
        if src == 'salary_rules' and vals.get('salary_rule_ids'):
            cvals['salary_rule_ids'] = [(6, 0, [int(i) for i in vals['salary_rule_ids']])]
        if src == 'structure' and vals.get('structure_id'):
            cvals['structure_id'] = int(vals['structure_id'])
        if src in ('json', 'excel') and vals.get('file_b64'):
            cvals['import_file'] = vals['file_b64']
            cvals['import_filename'] = vals.get('file_name') or (
                'import.json' if src == 'json' else 'import.xlsx')

        rec = Wiz.create(cvals)
        ok, err, msg = True, None, 'Import complete.'
        try:
            res = rec.action_import()
            try:
                msg = res['params']['message']
            except Exception:
                pass
        except Exception as e:
            ok = False
            err = str(getattr(e, 'name', None) or e) or 'Import failed.'
            _logger.warning("Formula import failed: %s", e)
        cfg = self.env['hr.formula.config'].browse(int(vals['config_id']))
        return {'ok': ok, 'error': err, 'message': msg,
                'rule_count': len(cfg.rule_ids), 'config_id': cfg.id,
                'config_name': cfg.name}

    @api.model
    def download_template(self, config_id):
        rec = self.env['hr.formula.import.wizard'].create(
            {'config_id': int(config_id), 'import_source': 'excel'})
        try:
            return rec.action_download_template()
        except Exception as e:
            _logger.debug("download_template failed: %s", e)
            return False
