"""Versioned orchestration records; existing services own business effects."""
import hashlib
import copy
import json
import logging
from datetime import timedelta
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from . import workflow_definition as D

_logger = logging.getLogger(__name__)
INTERNAL = object()


def internal(records):
    return records.sudo().with_context(_pb_workflow_internal=INTERNAL)


def is_internal(records):
    return records.env.su or records.env.context.get('_pb_workflow_internal') is INTERNAL


class WorkflowProtected(models.AbstractModel):
    _name = 'pb.workflow.protected'
    _description = 'Protected workflow records'

    def _check_access(self, operation):
        result = super()._check_access(operation)
        if result or self.env.su or self._name not in ('pb.workflow.run', 'pb.workflow.step', 'pb.workflow.log'):
            return result
        runs = self.sudo() if self._name == 'pb.workflow.run' else self.sudo().mapped('run_id')
        for run in runs:
            if run.source_model:
                try:
                    self.env['pb.workflow.studio'].with_company(run.company_id)._source(run.source_model, run.source_id)
                except (AccessError, UserError):
                    return self, lambda: AccessError(_('You no longer have access to this workflow record.'))
        return None

    def _read_format(self, fnames, load='_classic_read'):
        if not self.env.su and self._name in ('pb.workflow.run', 'pb.workflow.step', 'pb.workflow.log'):
            self.check_access('read')
        return super()._read_format(fnames, load)

    @api.model_create_multi
    def create(self, vals_list):
        if not is_internal(self):
            raise AccessError(_('Use Workflow Studio to make this change.'))
        return super().create(vals_list)

    def write(self, vals):
        if not is_internal(self):
            raise AccessError(_('Use Workflow Studio to make this change.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(_('Workflow history is retained. Archive the workflow instead.'))
        return super().unlink()


class Workflow(models.Model):
    _name = 'pb.workflow'
    _description = 'Workflow'
    _inherit = ['pb.workflow.protected']
    _order = 'write_date desc, id desc'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    module_label = fields.Char(default='Other')
    source_model = fields.Char()
    process_id = fields.Many2one('biz.approval.process', ondelete='restrict')
    draft = fields.Json(default=dict)
    revision = fields.Integer(default=1)
    version_ids = fields.One2many('pb.workflow.version', 'workflow_id')
    published_id = fields.Many2one('pb.workflow.version', ondelete='restrict')
    active = fields.Boolean(default=True)
    enabled = fields.Boolean(default=False, index=True)
    execution_user_id = fields.Many2one('res.users', required=True)
    automation_id = fields.Many2one('base.automation', ondelete='set null')
    last_approval_event_id = fields.Integer(default=0)
    component = fields.Boolean(default=False)
    notes = fields.Text()
    starter_group_ids = fields.Many2many('res.groups', string='Who can start this workflow')

    def _lock(self):
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM pb_workflow WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()

    def _sync_automation(self):
        self.ensure_one()
        if self.automation_id:
            self.automation_id.sudo().write({'active': False})
        if not self.enabled or not self.published_id:
            return
        d = self.published_id.definition
        t = d['trigger']
        kind = t['kind']
        if kind in ('manual', 'approval_applied'):
            return
        model = self.env['ir.model'].sudo()._get(self.source_model)
        if not model:
            raise UserError(_('Choose the record this workflow follows.'))
        trigger = {'created': 'on_create', 'changed': 'on_write', 'date': 'on_time'}[kind]
        vals = {'name': 'Workflow Studio · %s' % self.name, 'model_id': model.id,
                'trigger': trigger, 'active': True,
                'filter_domain': repr([('company_id', '=', self.company_id.id)])}
        F = self.env['ir.model.fields'].sudo()
        if kind == 'changed':
            vals['trigger_field_ids'] = [(6, 0, F.search([
                ('model_id', '=', model.id), ('name', 'in', t['fields'])]).ids)]
            # Exclude creation: a changed-field workflow starts on edits only.
            vals['filter_pre_domain'] = repr([('id', '!=', False)])
        if kind == 'date':
            f = F.search([('model_id', '=', model.id), ('name', '=', t['date_field'])], limit=1)
            vals.update(trg_date_id=f.id, trg_date_range=t.get('delay', 0),
                        trg_date_range_mode=t.get('mode', 'after'),
                        trg_date_range_type=t.get('unit', 'day'))
        rule = self.automation_id.sudo()
        if rule:
            rule.write(vals)
        else:
            rule = self.env['base.automation'].sudo().create(vals)
            internal(self).write({'automation_id': rule.id})
        code = "env['pb.workflow.studio']._capture(%d, records)" % self.id
        actions = rule.action_server_ids
        values = {'name': 'Start %s' % self.name, 'model_id': model.id,
                  'state': 'code', 'code': code, 'base_automation_id': rule.id}
        if actions:
            actions[:1].sudo().write(values)
            actions[1:].sudo().unlink()
        else:
            self.env['ir.actions.server'].sudo().create(values)


class WorkflowVersion(models.Model):
    _name = 'pb.workflow.version'
    _description = 'Published Workflow Version'
    _inherit = ['pb.workflow.protected']
    _order = 'number desc, id desc'
    workflow_id = fields.Many2one('pb.workflow', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='workflow_id.company_id', store=True)
    number = fields.Integer(required=True)
    definition = fields.Json(required=True)
    process_id = fields.Many2one('biz.approval.process', ondelete='restrict')
    execution_user_id = fields.Many2one('res.users')
    starter_group_ids = fields.Many2many('res.groups', string='Who may start this version')
    published_by = fields.Many2one('res.users', required=True)
    published_at = fields.Datetime(default=fields.Datetime.now, required=True)
    note = fields.Char()
    _unique_version = models.Constraint('unique(workflow_id, number)', 'This version already exists.')

    def write(self, vals):
        raise UserError(_('A published version cannot be changed. Save a new version.'))

    def unlink(self):
        if not self.env.context.get('module_uninstall'):
            raise UserError(_('Published workflow versions are retained.'))
        return super().unlink()


class WorkflowEvent(models.Model):
    _name = 'pb.workflow.event'
    _description = 'Workflow Event'
    _inherit = ['pb.workflow.protected']
    _order = 'id desc'
    workflow_id = fields.Many2one('pb.workflow', required=True, ondelete='restrict')
    version_id = fields.Many2one('pb.workflow.version', required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True)
    source_model = fields.Char()
    source_id = fields.Integer()
    initiator_id = fields.Many2one('res.users', required=True)
    execution_user_id = fields.Many2one('res.users', required=True)
    key = fields.Char(required=True, index=True)
    state = fields.Selection([('pending', 'Waiting'), ('done', 'Started'),
                              ('excluded', 'Filtered out'), ('failed', 'Needs attention')], default='pending', index=True)
    error = fields.Text()
    run_id = fields.Many2one('pb.workflow.run', ondelete='restrict')
    approval_request_id = fields.Many2one('biz.approval.request', ondelete='restrict')
    initial_values = fields.Json(default=dict)
    _unique_event = models.Constraint('unique(key)', 'This event has already been captured.')

    def _process(self):
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM pb_workflow_event WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.state != 'pending':
            return self.run_id
        try:
            with self.env.cr.savepoint():
                actor = self.execution_user_id
                if not actor.active or self.company_id not in actor.company_ids:
                    raise AccessError(_('The execution user no longer has access to this company.'))
                service = self.env['pb.workflow.studio'].with_user(actor).with_context(
                    allowed_company_ids=[self.company_id.id])
                source = service._source(self.source_model, self.source_id) if self.source_model else None
                facts = service._facts(source) if source is not None else dict(self.initial_values or {})
                d = self.version_id.definition
                checks = [D.matches(r, facts) for r in d['scope']['rules']]
                if checks and not (all(checks) if d['scope']['match'] == 'all' else any(checks)):
                    internal(self).write({'state': 'excluded'})
                    return self.env['pb.workflow.run']
                run = internal(self.env['pb.workflow.run']).create({
                    'name': self.workflow_id.name,
                    'workflow_id': self.workflow_id.id, 'version_id': self.version_id.id,
                    'company_id': self.company_id.id, 'source_model': self.source_model,
                    'source_id': self.source_id, 'initiator_id': self.initiator_id.id,
                    'execution_user_id': actor.id, 'facts': facts,
                    'source_approval_id': self.approval_request_id.id})
                internal(self).write({'state': 'done', 'run_id': run.id, 'error': False})
                run._initialize()
                run._advance()
                return run
        except Exception as exc:
            _logger.exception('Workflow event %s could not start', self.id)
            internal(self).write({'state': 'failed', 'error': str(exc)[:1000]})
            return self.env['pb.workflow.run']


class WorkflowRun(models.Model):
    _name = 'pb.workflow.run'
    _description = 'Workflow Run'
    _inherit = ['pb.workflow.protected', 'mail.thread', 'mail.activity.mixin',
                'biz.approval.adapter.mixin']
    _order = 'id desc'
    _approval_process_key = 'workflow_studio'

    name = fields.Char(required=True)
    workflow_id = fields.Many2one('pb.workflow', required=True, ondelete='restrict')
    version_id = fields.Many2one('pb.workflow.version', required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True)
    source_model = fields.Char()
    source_id = fields.Integer()
    initiator_id = fields.Many2one('res.users', required=True, index=True)
    execution_user_id = fields.Many2one('res.users', required=True)
    state = fields.Selection([('running', 'Running'), ('waiting', 'Waiting'),
        ('held', 'On hold'), ('done', 'Finished'), ('failed', 'Needs attention'),
        ('cancelled', 'Cancelled'), ('rejected', 'Rejected')], default='running', index=True)
    facts = fields.Json(default=dict, groups='base.group_system')
    step_ids = fields.One2many('pb.workflow.step', 'run_id')
    log_ids = fields.One2many('pb.workflow.log', 'run_id')
    source_approval_id = fields.Many2one('biz.approval.request', ondelete='restrict')
    ended_at = fields.Datetime()
    checked_at = fields.Datetime(default=fields.Datetime.now, index=True)

    def _lock(self):
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM pb_workflow_run WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        self.step_ids.invalidate_recordset()

    def _log(self, text, step=None):
        internal(self.env['pb.workflow.log']).create({
            'run_id': self.id, 'company_id': self.company_id.id,
            'step_key': step.key if step else False, 'message': text,
            'actor_id': self.env.uid})

    def _service(self):
        if not self.execution_user_id.active or self.company_id not in self.execution_user_id.company_ids:
            raise AccessError(_('The execution user no longer has access to this company.'))
        return self.env['pb.workflow.studio'].with_user(self.execution_user_id).with_context(
            allowed_company_ids=[self.company_id.id], _pb_workflow_internal=INTERNAL,
            _pb_workflow_origin=self.workflow_id.id)

    def _source(self):
        return self._service()._source(self.source_model, self.source_id) if self.source_model else self._service().env['pb.workflow.run'].browse(self.id)

    def _initialize(self):
        self.ensure_one()
        internal(self.env['pb.workflow.step']).create([{
            'run_id': self.id, 'company_id': self.company_id.id,
            'key': n['id'], 'name': n['title'], 'kind': n['type'],
            'config': copy.deepcopy(n), 'state': 'pending', 'position': i,
        } for i, n in enumerate(self.version_id.definition['nodes'])])
        self._log(_('Started version %s.', self.version_id.number))

    def _values(self):
        result = dict(self.sudo().facts or {})
        for s in self.sudo().step_ids.filtered(lambda x: x.state == 'done'):
            for key, value in (s.answers or {}).items():
                result['step.%s.%s' % (s.key, key)] = value
            for field in s.config.get('form', {}).get('fields', []):
                if field.get('bind') and field['id'] in (s.answers or {}):
                    result[field['bind']] = s.answers[field['id']]
        return result

    def _advance(self):
        self.ensure_one()
        self._lock()
        if self.state in ('held', 'done', 'cancelled', 'rejected'):
            return
        d, steps = self.version_id.definition, {s.key: s for s in self.sudo().step_ids}
        def skip(ids):
            for key in ids:
                for child in D.descendants(d, key):
                    s = steps[child]
                    if s.state not in ('done', 'skipped'):
                        s._cancel_activity()
                        internal(s).write({'state': 'skipped'})
        def sequence(ids):
            for key in ids:
                if not visit(key):
                    return False
            return True
        def visit(key):
            s, n = steps[key], steps[key].config
            if s.state in ('done', 'skipped'):
                return True
            if s.state in ('waiting', 'failed'):
                return False
            if n['type'] == 'branch':
                if not s.choice:
                    b = next(b for b in n['branches'] if not b.get('condition') or D.matches(b['condition'], self._values()))
                    internal(s).write({'choice': b['id'], 'state': 'active'})
                    skip([x for other in n['branches'] if other['id'] != b['id'] for x in other['steps']])
                    self._log(_('Path: %s.', b['label']), s)
                b = next(b for b in n['branches'] if b['id'] == s.choice)
                if sequence(b['steps']):
                    s._finish()
                    return True
                return False
            if n['type'] == 'parallel':
                internal(s).write({'state': 'active'})
                done = []
                for b in n['branches']:
                    done.append(sequence(b['steps']))
                    if n.get('join') == 'any' and done[-1]:
                        skip([x for other in n['branches'] if other['id'] != b['id'] for x in other['steps']])
                        s._finish()
                        return True
                if all(done):
                    s._finish()
                    return True
                return False
            if n['type'] == 'subprocess':
                internal(s).write({'state': 'active'})
                if sequence(n['steps']):
                    s._finish()
                    return True
                return False
            try:
                with self.env.cr.savepoint():
                    s._execute()
            except Exception as exc:
                _logger.exception('Workflow step %s failed', s.id)
                internal(s).write({'state': 'failed', 'error': str(exc)[:1000], 'attempts': s.attempts+1})
                self._log(_('Needs attention: %s', str(exc)[:400]), s)
            return s.state == 'done'
        complete = sequence(d['order'])
        state = 'done' if complete else 'failed' if any(s.state == 'failed' for s in steps.values()) else 'waiting'
        internal(self).write({'state': state, 'ended_at': fields.Datetime.now() if complete else False})
        if complete:
            self._log(_('Workflow finished.'))

    def _approval_process_key_for(self):
        self.ensure_one()
        return self.sudo().version_id.process_id.key

    def _approval_context(self):
        self.ensure_one()
        vals = self._values()
        return {'company_id': self.company_id.id, 'title': self.name,
                'scope_keys': [''], 'kind_key': 'any',
                'facts': {k: {'value': v if type(v) in (str, int, float, bool) else json.dumps(v), 'unit': ''} for k, v in vals.items()},
                'amount': vals.get('amount', 0), 'currency_id': self.company_id.currency_id.id,
                'maker_uids': [self.initiator_id.id], 'subject_uids': [self.initiator_id.id],
                'submitter_uid': self.initiator_id.id,
                'source_revision': self._approval_revision_of(vals), 'evidence': []}

    def _approval_detail(self, request):
        self.ensure_one()
        request.check_access('read')
        if request.res_model != self._name or request.res_id != self.id:
            raise AccessError(_('This approval belongs to another record.'))
        rows = []
        for node in self.sudo().version_id.definition['nodes']:
            for field in node.get('form', {}).get('fields', []):
                key = 'step.%s.%s' % (node['id'], field['id'])
                if key in (request.facts or {}):
                    value = request.facts[key]['value']
                    if field['type'] == 'boolean':
                        value = _('Yes') if value else _('No')
                    if field['type'] == 'file':
                        value = _('%s attached files', len(json.loads(value)))
                    rows.append({'head': field['label'], 'sub': node['title'], 'cells': [str(value)]})
        return {'title': _('Submitted information'), 'columns': [_('Answer')], 'rows': rows,
                'note': _('Answers frozen when this approval was submitted.')}

    @api.model
    def _approval_capabilities(self):
        return {'facts': {'amount': {'type': 'decimal', 'label': _('Amount'), 'unit': 'currency'},
                          'urgent': {'type': 'bool', 'label': _('Urgent'), 'unit': 'bool'}},
                'kinds': [{'key': 'any', 'label': _('Any request')}],
                'evidence': [], 'scope_levels': [_('Whole company')], 'manager_mode': True}

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_keys': [''], 'scope_key': '', 'label': company.name,
                 'kind_key': 'any', 'headcount': 0}]

    def _approval_validate(self):
        self.ensure_one()
        if not self.env.context.get('_pb_workflow_internal') is INTERNAL:
            raise UserError(_('Start approval from the waiting workflow step.'))
        if self.state in ('done', 'cancelled', 'rejected'):
            raise UserError(_('This workflow is already closed.'))

    def _approval_apply(self, request):
        self.ensure_one()
        if request.source_revision != self._approval_revision_of(self._values()):
            raise UserError(_('The answers changed. Request a fresh approval.'))
        return True


class WorkflowStep(models.Model):
    _name = 'pb.workflow.step'
    _description = 'Workflow Step Progress'
    _inherit = ['pb.workflow.protected']
    _order = 'position, id'
    run_id = fields.Many2one('pb.workflow.run', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    key = fields.Char(required=True)
    name = fields.Char(required=True)
    kind = fields.Char(required=True)
    position = fields.Integer()
    config = fields.Json(required=True, groups='base.group_system')
    state = fields.Selection([('pending', 'Not started'), ('active', 'In progress'),
        ('waiting', 'Waiting'), ('done', 'Done'), ('skipped', 'Skipped'),
        ('failed', 'Needs attention')], default='pending', index=True)
    assignee_id = fields.Many2one('res.users', index=True)
    activity_id = fields.Many2one('mail.activity', ondelete='set null')
    approval_id = fields.Many2one('biz.approval.request', ondelete='restrict')
    mail_id = fields.Many2one('mail.mail', ondelete='set null')
    answers = fields.Json(default=dict, groups='base.group_system')
    wake_at = fields.Datetime(index=True)
    choice = fields.Char()
    error = fields.Text()
    attempts = fields.Integer(default=0)
    approval_attempt = fields.Integer(default=0)
    done_at = fields.Datetime()
    started_at = fields.Datetime()
    _unique_step = models.Constraint('unique(run_id,key)', 'This step already exists in this run.')

    def _cancel_activity(self):
        if self.activity_id:
            internal(self.activity_id).unlink()

    def _finish(self, answers=None):
        if self.state == 'done':
            return
        self._cancel_activity()
        internal(self).write({'state': 'done', 'done_at': fields.Datetime.now(),
                             'error': False, **({'answers': answers} if answers is not None else {})})
        self.run_id._log(_('%s — done.', self.name), self)

    def _execute(self):
        self.ensure_one()
        n, run = self.sudo().config, self.run_id.sudo()
        service = run._service()
        source = run._source()
        if not self.started_at:
            internal(self).write({'started_at': fields.Datetime.now()})
        if self.kind in ('trigger', 'reference'):
            self._finish()
        elif self.kind in ('task', 'input'):
            uid = service._resolve_owner(run, n.get('owner', {}))
            user = self.env['res.users'].sudo().browse(uid).exists()
            if not user or not user.active or user.share or run.company_id not in user.company_ids:
                raise UserError(_('Choose an active person who belongs to this company.'))
            if run.source_model:
                service.with_user(user)._source(run.source_model, run.source_id)
            activity = self.activity_id
            if not activity:
                days = n.get('due', 2)
                deadline = fields.Date.today() + timedelta(days=days)
                if n.get('due_kind', 'working') == 'working':
                    calendar = run.company_id.resource_calendar_id
                    if not calendar:
                        raise UserError(_('Set the company working calendar before assigning this task.'))
                    planned = calendar.plan_days(days + 1, pytz.utc.localize(fields.Datetime.now()), compute_leaves=True)
                    if not planned:
                        raise UserError(_('The company calendar has no available working days.'))
                    deadline = planned.astimezone(pytz.timezone(calendar.tz or 'UTC')).date()
                activity = internal(self.env['mail.activity']).create({
                    'res_model_id': self.env['ir.model']._get_id('pb.workflow.run'),
                    'res_id': run.id, 'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'user_id': uid, 'summary': n['title'],
                    'note': _('Open Workflow Studio → My tasks to complete this step.'),
                    'date_deadline': deadline,
                    'workflow_step_id': self.id})
            internal(self).write({'state': 'waiting', 'assignee_id': uid, 'activity_id': activity.id})
            run._log(_('Waiting for %s.', user.name), self)
        elif self.kind == 'wait':
            internal(self).write({'state': 'waiting', 'wake_at': fields.Datetime.now() + timedelta(hours=n['hours'])})
            run._log(_('Waiting for the set time.'), self)
        elif self.kind == 'matrix':
            if self.approval_id:
                request = self.approval_id
            else:
                if source._approval_process().id != run.version_id.process_id.id:
                    raise UserError(_('This record uses a different approval process. Check the workflow’s selected process.'))
                existing = source.approval_request_id
                if existing and existing.state in ('pending', 'blocked', 'approved'):
                    existing.check_access('read')
                    internal(self).write({'approval_id': existing.id, 'state': 'waiting'})
                    run._log(_('Following the approval already open for this record.'), self)
                    return
                engine = service.env['biz.approval.engine'].with_context(_pb_workflow_internal=INTERNAL)
                result = engine.submit(source.with_context(_pb_workflow_internal=INTERNAL),
                    idempotency_key='workflow:%s:%s:%s' % (run.id, self.key, self.approval_attempt))
                request = self.env['biz.approval.request'].sudo().browse(result['id'])
                internal(self).write({'approval_id': request.id})
            if request.state == 'applied':
                self._finish()
            else:
                internal(self).write({'state': 'waiting'})
                run._log(_('Following the existing Approval Matrix route.'), self)
        elif self.kind == 'email':
            template = service._mail_template(n['template_id'], source._name)
            if not self.mail_id:
                mail_id = template.send_mail(source.id, force_send=False, email_values={'auto_delete': False})
                internal(self).write({'mail_id': mail_id})
            elif self.mail_id.state in ('exception', 'cancel'):
                self.mail_id.sudo().write({'state': 'outgoing', 'failure_reason': False})
            internal(self).write({'state': 'waiting'})
            run._log(_('Message queued in the existing mail service.'), self)
        elif self.kind == 'action':
            service._execute_action(source, n)
            self._finish()


class WorkflowLog(models.Model):
    _name = 'pb.workflow.log'
    _description = 'Workflow History'
    _inherit = ['pb.workflow.protected']
    _order = 'id'
    run_id = fields.Many2one('pb.workflow.run', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True)
    step_key = fields.Char()
    message = fields.Char(required=True)
    actor_id = fields.Many2one('res.users', required=True)

    def write(self, vals):
        raise UserError(_('Workflow history cannot be changed.'))


class WorkflowActivity(models.Model):
    _inherit = 'mail.activity'
    workflow_step_id = fields.Many2one('pb.workflow.step', ondelete='cascade', index=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not is_internal(self) and any(v.get('workflow_step_id') for v in vals_list):
            raise AccessError(_('Workflow tasks are created by their workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        if not is_internal(self) and (self.filtered('workflow_step_id') or 'workflow_step_id' in vals):
            raise UserError(_('Manage this task in Workflow Studio so progress stays in sync.'))
        return super().write(vals)

    def _action_done(self, *args, **kwargs):
        if self.filtered('workflow_step_id') and not is_internal(self):
            raise UserError(_('Open Workflow Studio → My tasks to complete this step.'))
        return super()._action_done(*args, **kwargs)

    def action_feedback(self, feedback=False, attachment_ids=None):
        linked = self.filtered('workflow_step_id')
        if linked and not is_internal(self):
            raise UserError(_('Complete this step in Workflow Studio → My tasks so its required information is checked.'))
        return super().action_feedback(feedback=feedback, attachment_ids=attachment_ids)

    def unlink(self):
        if self.filtered('workflow_step_id') and not is_internal(self):
            raise UserError(_('Cancel or complete this task from Workflow Studio.'))
        return super().unlink()


class WorkflowApprovalProcess(models.Model):
    _inherit = 'biz.approval.process'

    def _compute_connected(self):
        super()._compute_connected()
        for rec in self.filtered(lambda p: p.model_name == 'pb.workflow.run'):
            rec.connected = bool(self.env['pb.workflow'].sudo().search_count([('process_id', '=', rec.id)]))
