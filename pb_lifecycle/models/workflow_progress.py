"""Permission-checked runtime views shared by every business module."""
import copy
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from .workflow_models import internal
from . import workflow_definition as D

VIEW = 'pb_lifecycle.group_workflow_viewer'


class WorkflowProgress(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    def _can_view_progress(self):
        return self._can_design() or self.env.user.has_group(VIEW)

    def _progress_permission(self):
        self._staff()
        if not self._can_view_progress():
            raise AccessError(_('You need permission to view workflow progress.'))

    @api.model
    def bootstrap(self):
        result = super().bootstrap()
        result['can_view_progress'] = self._can_view_progress()
        return result

    def _resolve_owner(self, run, owner):
        kind = owner.get('kind')
        if kind == 'user':
            return owner.get('id')
        if kind == 'initiator':
            return run.initiator_id.id
        source = run._source()
        if kind == 'field':
            field = next((f for f in self._source_fields(run.source_model) if f['key'] == owner.get('field')), {})
            if field.get('type') != 'many2one' or field.get('relation') != 'res.users':
                raise UserError(_('Choose an available person field on this record.'))
            return source[owner['field']].id
        if kind == 'manager':
            employee = source if source._name == 'hr.employee' else source.employee_id if 'employee_id' in source._fields else self.env['hr.employee'].search([
                ('user_id', '=', run.initiator_id.id), ('company_id', '=', run.company_id.id)], limit=1)
            manager = employee.parent_id.user_id if employee else None
            if not manager:
                raise UserError(_('Name the employee’s manager and link their user account in People.'))
            return manager.id
        if kind == 'role':
            role = self.env['biz.approval.role'].sudo().browse(owner.get('id', 0)).exists()
            if not role or role.is_pool:
                raise UserError(_('Choose a single-person responsibility from People & backups.'))
            scopes = source._approval_context().get('scope_keys', ['']) if hasattr(source, '_approval_context') else ['']
            row, _via = self.env['biz.approval.responsibility'].resolve(run.company_id, role, scopes)
            if not row or not row.user_id:
                raise UserError(_('Nobody is named for %s in People & backups.', role.name))
            # These are ordinary tasks. Approval-only cover is deliberately
            # applied by the approval engine when an actual approval is raised.
            return row.user_id.id
        raise UserError(_('Choose who does this step.'))

    @api.model
    def record_runs(self, model, record_id):
        """Cheap form hook: empty for users without permission, never a grant."""
        self._staff()
        if not self._can_view_progress():
            return {'runs': [], 'approvals': [], 'can_design': False, 'record_stages': []}
        source = self._source(model, record_id)
        domain = [('source_model', '=', model), ('source_id', '=', int(record_id)),
                  ('company_id', '=', self.env.company.id)]
        runs = self.env['pb.workflow.run'].search(domain, limit=50)
        # Native approval history is reused even for records predating Studio.
        approvals = self.env['biz.approval.request'].search([
            ('res_model', '=', model), ('res_id', '=', int(record_id)),
            ('company_id', '=', self.env.company.id)], order='id desc', limit=50)
        approvals -= runs.sudo().mapped('step_ids.approval_id').with_env(self.env)
        return {'can_design': self._can_design() and model in {row['key'] for row in self._models()},
                'record_stages': self._record_stages(model, source),
                'record_name': source.display_name,
                'runs': [{'id': r.id, 'name': r.name, 'state': r.state,
                          'started': str(r.create_date)} for r in runs],
                'approvals': [{'id': a.id, 'name': a.title, 'state': a.state,
                               'started': str(a.submitted_at or a.create_date)} for a in approvals]}

    @api.model
    def progress(self, run_id):
        self._progress_permission()
        run = self._run(run_id)
        srun = run.sudo()
        definition = srun.version_id.definition
        # A progress viewer never receives form schemas/answers, conditions,
        # email addresses, secrets, execution identities or configuration.
        graph = {'name': srun.name, 'stages': definition['stages'],
                 'order': definition['order'], 'nodes': []}
        for node in definition['nodes']:
            safe = {key: node[key] for key in ('id', 'type', 'title', 'stage', 'join', 'steps') if key in node}
            if 'branches' in node:
                safe['branches'] = [{k: b[k] for k in ('id', 'label', 'steps')} for b in node['branches']]
            graph['nodes'].append(safe)
        rows = []
        for step in srun.step_ids:
            reason = ''
            if step.state == 'waiting':
                reason = {'task': _('Waiting for the assigned person'), 'input': _('Waiting for information'),
                          'matrix': _('Waiting for approval'), 'email': _('Waiting for the mail service'),
                          'wait': _('Waiting until the set time')}.get(step.kind, _('Waiting'))
            if step.state == 'waiting' and step.kind == 'matrix' and not step.approval_id:
                reason = _('Waiting for this record to be sent for approval.')
            if step.state == 'failed':
                reason = step.error if self._can_design() else _('This step needs attention from the workflow owner.')
            if step.state == 'skipped':
                reason = step.error or _('Another path was selected.')
            if step.state == 'waiting' and step.kind == 'wait' and step.config.get('wait_for'):
                reason = _('Waiting for matching conditions; the shown time is the deadline.')
            approval = None
            if step.approval_id:
                try:
                    approval = self.approval_progress(step.approval_id.id)
                except (AccessError, UserError):
                    pass
            rows.append({'id': step.id, 'key': step.key, 'state': step.state,
                         'owner': step.assignee_id.name or '', 'reason': reason,
                         'started': str(step.started_at) if step.started_at else '',
                         'finished': str(step.done_at) if step.done_at else '',
                         'due': str(step.activity_id.date_deadline) if step.activity_id else '',
                         'wake_at': str(step.wake_at) if step.wake_at else '',
                         'approval': approval})
        return {'id': run.id, 'name': run.name, 'state': run.state,
                'version': srun.version_id.number, 'graph': graph, 'steps': rows,
                'source_model': run.source_model or '', 'source_id': run.source_id,
                'started': str(run.create_date), 'refreshed': str(fields.Datetime.now()),
                'can_manage': self._can_design(),
                'workflow_id': srun.workflow_id.id if self._can_design() else None,
                'record_stages': self._record_stages(run.source_model, self._source(run.source_model, run.source_id)) if run.source_model else [],
                'can_read_submission': self._can_design() or run.initiator_id.id == self.env.uid or self.env.uid in srun.step_ids.mapped('approval_id.seat_ids.acting_user_id').ids,
                'tasks': self.tasks(run_id=run.id)}

    @api.model
    def approval_progress(self, request_id):
        self._progress_permission()
        request = self.env['biz.approval.request'].browse(int(request_id)).exists()
        if not request:
            raise UserError(_('This approval is not available.'))
        request.check_access('read')
        source = self._source(request.res_model, request.res_id)
        data = self.env['biz.approval.engine'].get_request(request.id)
        return {'id': request.id, 'name': data['title'], 'state': data['state'],
                'source_model': request.res_model, 'source_id': request.res_id,
                'can_manage': self._can_design(),
                'record_stages': self._record_stages(request.res_model, source),
                'version': data['version'], 'current': data['current_step_key'],
                'reason': data.get('block_reason', ''),
                'steps': [{'key': s['key'], 'name': s['title'], 'state': s['status'],
                           'included': s['included'], 'reason': s.get('block_reason', ''),
                           'due': s.get('due_at', ''),
                           'owners': [u['acting_name'] or u['name'] for u in s.get('seats', [])]}
                          for s in data.get('steps', [])]}

    @api.model
    def submission(self, run_id, request_id=None):
        """Full answers require a business role, not merely progress viewing."""
        run = self._run(run_id)
        request = self.env['biz.approval.request'].browse(int(request_id)).exists() if request_id else self.env['biz.approval.request'].search([
            ('res_model', '=', 'pb.workflow.run'), ('res_id', '=', run.id)], order='id desc', limit=1)
        own = run.initiator_id.id == self.env.uid or self._can_design()
        if request:
            request.check_access('read')
            if request.res_model != 'pb.workflow.run' or request.res_id != run.id:
                raise AccessError(_('This approval belongs to another record.'))
            approver = self.env.uid in request.sudo().seat_ids.mapped('acting_user_id').ids
        else:
            approver = False
        if not own and not approver:
            raise AccessError(_('Viewing progress does not include permission to read submitted answers.'))
        import json
        sections = []
        for step in run.sudo().step_ids.filtered(lambda s: s.kind == 'input'):
            rows = []
            for field in step.config['form']['fields']:
                key = 'step.%s.%s' % (step.key, field['id'])
                if field['type'] == 'section':
                    continue
                if request:
                    if key not in (request.facts or {}):
                        continue
                    value = request.facts[key]['value']
                    if field['type'] in ('file', 'rows', 'multiselect'):
                        value = json.loads(value)
                else:
                    if field['id'] not in (step.answers or {}):
                        continue
                    value = step.answers[field['id']]
                if field['type'] == 'file':
                    visible = self.env['ir.attachment'].search([('id', 'in', value),
                        ('res_model', '=', 'pb.workflow.step'), ('res_id', '=', step.id)])
                    value = [{'id': a.id, 'name': a.name} for a in visible]
                if field['type'] == 'lookup':
                    try:
                        value = self._source(field['lookup_model'], value).display_name
                    except (AccessError, UserError):
                        value = _('Record not available')
                rows.append({'label': field['label'], 'type': field['type'], 'value': value})
            sections.append({'title': step.name, 'rows': rows})
        return {'id': run.id, 'name': run.name, 'state': run.state, 'sections': sections,
                'snapshot': bool(request), 'attempt': request.attempt if request else None}

    @api.model
    def lookup(self, task_id, field_id, term=''):
        task = self._task(task_id)
        field = next((f for f in task.config.get('form', {}).get('fields', [])
                      if f['id'] == field_id and f['type'] == 'lookup'), None)
        if not field:
            raise UserError(_('Choose a record field in this task.'))
        model = field['lookup_model']
        records = self.env[model].search([('company_id', '=', task.company_id.id),
                    ('display_name', 'ilike', str(term)[:100])], limit=30)
        return [{'id': r.id, 'name': r.display_name} for r in records]

    @api.model
    def revise_information(self, run_id):
        run = self._run(run_id).sudo()
        if run.initiator_id.id != self.env.uid and not self._can_design():
            raise AccessError(_('Only the person who started this request or its workflow owner can reopen information.'))
        run._lock()
        failed = run.step_ids.filtered(lambda s: s.kind == 'matrix' and s.state == 'failed' and s.approval_attempt > 0)
        if not failed or run.source_model:
            raise UserError(_('Correct the original record, then ask the workflow owner to retry approval.'))
        graph = run.version_id.definition
        before = graph['order'][:graph['order'].index(failed.key)]
        forms = [key for key in before if next(n for n in graph['nodes'] if n['id'] == key)['type'] == 'input']
        if not forms:
            raise UserError(_('There is no information form to reopen.'))
        key = forms[-1]
        # Re-evaluating a decision after external effects would be misleading.
        between = before[before.index(key)+1:]
        if any(next(n for n in graph['nodes'] if n['id'] == k)['type'] not in ('reference', 'wait') for k in between):
            raise UserError(_('Later work depends on these answers. Cancel this run and start a corrected request to follow a fresh route.'))
        form = run.step_ids.filtered(lambda s: s.key == key)
        internal(form).write({'state': 'pending', 'done_at': False})
        internal(failed).write({'state': 'pending', 'error': False})
        internal(run).write({'state': 'running'})
        run._log(_('Information reopened after approval was returned.'), form)
        run._advance()
        return {'task_id': form.id, 'run_id': run.id}

    @api.model
    def failed_events(self, workflow_id):
        w = self._workflow(workflow_id)
        return [{'id': e.id, 'error': e.error, 'at': str(e.create_date)}
                for e in self.env['pb.workflow.event'].sudo().search([
                    ('workflow_id', '=', w.id), ('state', '=', 'failed')], limit=50)]

    @api.model
    def retry_event(self, event_id):
        self._design()
        event = self.env['pb.workflow.event'].sudo().browse(int(event_id)).exists()
        if not event:
            raise UserError(_('This event no longer exists.'))
        self._workflow(event.workflow_id.id)
        if event.source_model:
            self._source(event.source_model, event.source_id)
        if event.state != 'failed':
            raise UserError(_('This event does not need retrying.'))
        internal(event).write({'state': 'pending', 'error': False})
        event._process()
        return {'state': event.state, 'run_id': event.run_id.id or None, 'error': event.error or ''}


class WorkflowRunScreens(models.Model):
    _inherit = 'pb.workflow.run'

    def action_view_submission(self):
        self.ensure_one()
        self.env['pb.workflow.studio'].submission(self.id)
        return {'type': 'ir.actions.client', 'tag': 'pb_workflow_studio', 'name': _('Submitted information'),
                'context': {'pb_workflow_submission_id': self.id}}

    def action_view_progress(self):
        self.ensure_one()
        self.env['pb.workflow.studio'].progress(self.id)
        return {'type': 'ir.actions.client', 'tag': 'pb_workflow_studio', 'name': _('Workflow progress'),
                'context': {'pb_workflow_run_id': self.id}}
