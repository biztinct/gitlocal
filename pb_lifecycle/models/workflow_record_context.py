"""The module owns record stages; Studio reads them and orchestrates around them."""
from lxml import etree
from odoo import api, models, _
from odoo.exceptions import AccessError, UserError

from .workflow_models import internal


class WorkflowRecordContext(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    def _record_stages(self, model, record=None):
        if not model:
            return []
        obj = self.env[model]
        visible = obj.fields_get(attributes=['string', 'type', 'selection', 'relation'])
        bars = {}
        try:
            arch = etree.fromstring(obj.get_view(view_type='form')['arch'])
            for field in arch.xpath('//field[@widget="statusbar"]'):
                key = field.get('name')
                if key not in visible or key == 'approval_state':
                    continue
                values = field.get('statusbar_visible', '').split(',')
                bars.setdefault(key, []).append([v for v in values if v])
        except (AccessError, UserError):
            pass
        if not bars:
            bars = {key: [[]] for key in ('stage_id', 'state') if key in visible}
        spec = obj._chain_spec() if hasattr(obj, '_chain_spec') else None
        result = []
        for key, variants in bars.items():
            info = visible[key]
            if info['type'] not in ('selection', 'many2one'):
                continue
            current = record[key] if record is not None else None
            if info['type'] == 'selection':
                options = [{'key': value, 'name': label} for value, label in info['selection']]
                # Conditional statusbars can differ. Do not guess which applies.
                shown = variants[0] if all(v == variants[0] for v in variants) else []
            elif hasattr(obj, '_workflow_stage_options') and self._declared(model).get('stage_field') == key:
                # Stages that are rows the module owns (Hiring): the module
                # says which apply to this record and who may rename them.
                if current:
                    current.check_access('read')
                design = self._can_design()
                options = [{'key': s['id'], 'name': s['name'],
                            'can_rename': bool(design and s.get('renamable')),
                            'revision': s.get('revision') if design and s.get('renamable') else None}
                           for s in obj._workflow_stage_options(record) if s.get('id')]
                current = current.id if current else None
                shown = []
            else:
                stages = self.env[info['relation']]
                if not stages.has_access('read'):
                    continue
                domain = []
                if 'company_id' in stages._fields:
                    domain += [('company_id', 'in', [False, self.env.company.id])]
                available = stages.search(domain, limit=100)
                if current:
                    current.check_access('read')
                    available |= current
                options = [{'key': s.id, 'name': s.display_name,
                            'can_rename': False, 'revision': None} for s in available]
                current = current.id if current else None
                shown = []
            waiting = spec.get('submit_state') if spec and spec.get('state_field', 'state') == key else None
            result.append({'field': key, 'label': info['string'], 'type': info['type'],
                           'options': options, 'visible': shown,
                           'current': current, 'approval_value': waiting,
                           'fixed': info['type'] == 'selection'})
        return result

    @api.model
    def rename_record_stage(self, workflow_id, field, stage_id, name, revision):
        """Kept for the shipped Stages dialog: an alias of
        `stage_rename_shared`, which asks the module that owns the stages."""
        w = self._workflow(workflow_id)
        if not w.source_model or field != self._declared(w.source_model).get('stage_field'):
            raise UserError(_('Manage these stages through the module that owns them.'))
        self.stage_rename_shared(w.source_model, stage_id, name, revision)
        return self.metadata(w.source_model, w.id)

    @api.model
    def metadata(self, model='', workflow_id=None):
        result = super().metadata(model, workflow_id)
        result['record_stages'] = self._record_stages(model)
        return result

    @api.model
    def record_setup(self, model, record_id=None):
        """Design authority never grants access to the source record/module."""
        self._design()
        if model not in {row['key'] for row in self._models()}:
            raise AccessError(_('Workflow setup is not available for this record type.'))
        source = self._source(model, record_id) if record_id else None
        workflows = self.env['pb.workflow'].sudo().search([
            ('source_model', '=', model), ('company_id', '=', self.env.company.id), ('component', '=', False)])
        return {'model': model, 'module': self.env[model]._description,
                'record_id': source.id if source is not None else None,
                'record_name': source.display_name if source is not None else '',
                'workflows': [self._row(w) for w in workflows],
                'record_stages': self._record_stages(model, source), 'owners': self._ownership(model)}

    @api.model
    def create_for_record(self, model, record_id, name, only_this_record=False):
        setup = self.record_setup(model, record_id)
        if only_this_record and not record_id:
            raise UserError(_('Save the record before creating a workflow just for it.'))
        result = self.create_workflow(name, model, setup['module'])
        if only_this_record:
            w = self._workflow(result['id'])
            definition = dict(w.draft)
            definition['scope'] = {'match': 'all', 'rules': [
                {'field': 'id', 'op': 'eq', 'value': int(record_id)}]}
            internal(w).write({'draft': definition})
            result = self.get_workflow(w.id)
        return result
